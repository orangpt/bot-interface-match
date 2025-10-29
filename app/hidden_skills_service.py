import json
import re
from pathlib import Path

class HiddenSkillsService:
    def __init__(self, ontology_file: Path, threshold: float = 0.25):
        self.threshold = threshold
        self.ontology_file = ontology_file
        self.relations = self._load_ontology()
        self.known_terms = self._extract_all_known_skills()

    def _load_ontology(self):
        """Загружает онтологию"""
        if not self.ontology_file.exists():
            raise FileNotFoundError(f"Ontology file not found: {self.ontology_file}")
        with open(self.ontology_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("relations", [])

    def _extract_all_known_skills(self):
        """Формирует словарь всех известных навыков из онтологии"""
        all_skills = set()
        for rel in self.relations:
            all_skills.add(rel["from"].lower())
            all_skills.add(rel["to"].lower())
        return all_skills

    def _parse_resume_skills(self, resume: dict):
        """Парсит навыки из текста резюме (description, experience, education и т.п.)"""
        text = json.dumps(resume, ensure_ascii=False).lower()
        found = set()

        for skill in self.known_terms:
            # ищем точное вхождение (например, 'docker' или 'spring boot')
            pattern = r"\b" + re.escape(skill) + r"\b"
            if re.search(pattern, text):
                found.add(skill)

        return found

    def find_hidden_skills(self, resume: dict):
        """Определяет скрытые навыки на основе связей"""
        known_skills = self._parse_resume_skills(resume)
        suggestions = {}

        for rel in self.relations:
            sim = rel.get("similarity", 0)
            if sim < self.threshold:
                continue

            from_skill = rel["from"].lower()
            to_skill = rel["to"].lower()

            if from_skill in known_skills and to_skill not in known_skills:
                suggestions[to_skill] = max(suggestions.get(to_skill, 0), sim)
            elif to_skill in known_skills and from_skill not in known_skills:
                suggestions[from_skill] = max(suggestions.get(from_skill, 0), sim)

        sorted_skills = sorted(suggestions.items(), key=lambda x: x[1], reverse=True)
        return {
            "known_skills": sorted(list(known_skills)),
            "hidden_skills": [
                {"skill": s, "similarity": round(v, 3)} for s, v in sorted_skills
            ],
        }
