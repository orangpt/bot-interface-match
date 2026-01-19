import json
import re
import numpy as np
from pathlib import Path
import networkx as nx
from openai import OpenAI
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering
from app.service import HHResumeParserService

parser_service = HHResumeParserService()


class CandidateYouMapService:
    def __init__(self, ontology_file: Path, openai_api_key: str, similarity_threshold: float = 0.5):
        self.similarity_threshold = similarity_threshold
        self.ontology_file = ontology_file
        self.relations = self._load_ontology()
        self.known_terms = self._extract_all_known_skills()
        self.client = OpenAI(api_key=openai_api_key)

    # =================== Онтология ===================
    def _load_ontology(self):
        if not self.ontology_file.exists():
            raise FileNotFoundError(f"Ontology file not found: {self.ontology_file}")
        with open(self.ontology_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("relations", [])

    def _extract_all_known_skills(self):
        all_skills = set()
        for rel in self.relations:
            all_skills.add(rel["from"].lower())
            all_skills.add(rel["to"].lower())
        return all_skills

    # =================== Парсинг резюме ===================
    def _parse_resume_skills(self, resume: dict):
        found = set()
        resume_text = " ".join(s["name"] for s in resume.get("skills", [])).lower()
        for skill in self.known_terms:
            if skill.lower() in resume_text:
                found.add(skill.lower())
        return found

    # =================== Выявление скрытых навыков ===================
    def find_hidden_skills(self, resume: dict):
        known_skills = self._parse_resume_skills(resume)
        suggestions = {}

        for rel in self.relations:
            sim = rel.get("similarity", 0)
            if sim < self.similarity_threshold:
                continue
            from_skill = rel["from"].lower()
            to_skill = rel["to"].lower()
            if from_skill in known_skills and to_skill not in known_skills:
                suggestions[to_skill] = max(suggestions.get(to_skill, 0), sim)
            elif to_skill in known_skills and from_skill not in known_skills:
                suggestions[from_skill] = max(suggestions.get(from_skill, 0), sim)

        sorted_skills = sorted(suggestions.items(), key=lambda x: x[1], reverse=True)
        hidden_skills = [{"skill": s, "similarity": round(v, 3)} for s, v in sorted_skills if s not in known_skills]

        return {"known_skills": list(known_skills), "hidden_skills": hidden_skills}

    # =================== You-Map и граф навыков с топологией ===================
    def build_you_map(self, resume: dict):
        skills = resume.get("skills", [])
        if not skills:
            return {"graph": nx.Graph(), "clusters": [], "cluster_map": {}, "bridges": [], "cluster_density": {}}

        skill_names = [s["name"].lower() for s in skills]
        embeddings = self.get_embeddings(skill_names)
        G = nx.Graph()

        # Добавляем вершины
        for skill in skill_names:
            G.add_node(skill, type="known")

        # Добавляем ребра на основе схожести эмбеддингов
        for i, emb_i in enumerate(embeddings):
            for j, emb_j in enumerate(embeddings):
                if i >= j:
                    continue
                sim = float(cosine_similarity([emb_i], [emb_j])[0][0])
                if sim > self.similarity_threshold:
                    G.add_edge(skill_names[i], skill_names[j], weight=sim)

        # Кластеризация навыков (ядра компетенций)
        X = np.array(embeddings)
        clustering = AgglomerativeClustering(n_clusters=None, distance_threshold=1.2)
        labels = clustering.fit_predict(X)
        clusters = defaultdict(list)
        for idx, label in enumerate(labels):
            clusters[label].append(skill_names[idx])
        clusters = list(clusters.values())

        cluster_map = {skill: idx for idx, cluster in enumerate(clusters) for skill in cluster}

        # Связность кластера (плотность)
        cluster_density = {}
        for idx, cluster in enumerate(clusters):
            subgraph = G.subgraph(cluster)
            cluster_density[idx] = nx.density(subgraph)

        # Поиск мостов между кластерами
        bridges = []
        for u, v in G.edges():
            if cluster_map[u] != cluster_map[v]:
                bridges.append((u, v))

        return {
            "graph": G,
            "clusters": clusters,
            "cluster_map": cluster_map,
            "bridges": bridges,
            "cluster_density": cluster_density
        }

    # =================== Генерация онтологии по кандидату ===================
    def generate_candidate_ontology(self, resume: dict):
        known_skills = list(self._parse_resume_skills(resume))
        if not known_skills:
            return {"relations": [], "skills": []}

        embeddings = self.get_embeddings(known_skills)
        sim_matrix = cosine_similarity(embeddings)

        relations = []
        for i, from_skill in enumerate(known_skills):
            for j, to_skill in enumerate(known_skills):
                if i >= j:
                    continue
                sim = float(sim_matrix[i][j])
                if sim < self.similarity_threshold:
                    continue
                relation_type = self._classify_relation(from_skill, to_skill)
                relations.append({"from": from_skill, "to": to_skill, "similarity": round(sim, 3), "type": relation_type})

        return {"skills": known_skills, "relations": relations}

    def _classify_relation(self, a: str, b: str) -> str:
        a, b = a.lower(), b.lower()
        if any(x in b for x in ["framework", "library", "sdk"]) or a in b:
            return "PART_OF"
        if any(x in a for x in ["spring", "django", "flask"]) and "python" in b:
            return "REQUIRES"
        if any(x in a for x in ["java", "python", "go", "php"]) and any(x in b for x in ["backend", "microservices"]):
            return "REQUIRES"
        if abs(len(a) - len(b)) <= 3:
            return "SIMILAR_TO"
        if any(x in a for x in ["docker", "kubernetes", "ci", "cd"]) and any(x in b for x in ["devops", "infra"]):
            return "OFTEN_USED_WITH"
        if any(x in a for x in ["graphql", "api", "rest"]) and any(x in b for x in ["frontend", "backend"]):
            return "BRIDGES"
        if "data" in a and "visualization" in b:
            return "COMPLEMENTS"
        if any(x in b for x in ["architecture", "design", "pattern"]):
            return "LEADS_TO"
        return "RELATED"

    # =================== Рекомендации по прокачке ===================
    def generate_recommendations(self, resume: dict):
        hidden = self.find_hidden_skills(resume)
        you_map = self.build_you_map(resume)
        bridges = you_map["bridges"]

        bridge_skills = set()
        for a, b in bridges:
            if a not in hidden["known_skills"]:
                bridge_skills.add(a)
            if b not in hidden["known_skills"]:
                bridge_skills.add(b)

        recommendations = []
        for skill in hidden["hidden_skills"]:
            if skill["skill"] in bridge_skills:
                recommendations.append({"skill": skill["skill"], "reason": "Мост между кластерами навыков — усиливает ядра компетенций", "priority": "high"})
            else:
                recommendations.append({"skill": skill["skill"], "reason": "Связан с текущими навыками", "priority": "medium"})

        return {
            "known_skills": hidden["known_skills"],
            "hidden_skills": [s["skill"] for s in hidden["hidden_skills"]],
            "bridges": bridges,
            "recommendations": recommendations,
            "clusters": you_map["clusters"],
            "cluster_density": you_map.get("cluster_density", {})
        }

    # =================== Эмбеддинги ===================
    # def get_embeddings(self, texts: list):
    #     response = self.client.embeddings.create(model="text-embedding-3-small", input=texts)
    #     return [item.embedding for item in response.data]
    def get_embeddings(self, texts: list):
        # mock: возвращаем фиктивные эмбеддинги той же длины, что и входные тексты
        return [[0.1, 0.2, 0.3] for _ in texts]
