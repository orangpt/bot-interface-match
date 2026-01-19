# app/services/hh_market_service.py
import requests
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import gudhi
import time
from scipy.spatial.distance import cosine


GET_VACANCIES = "https://api.hh.ru/vacancies"
BEARER_TOKEN = "USERP1RTNDAV0Q3592PIAA92TRL0H4CJTIIRN9SGTHFN3FVGBF16GN2HHL1RD6J5"


class HHMarketService:
    def __init__(self):
        self._hh = self._HHClient()

    # ================= PRIVATE =================
    class _HHClient:
        def __init__(self):
            self.headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}

        def get_vacancies(self, text="Java backend developer", limit=100):
            vacancies = []
            page = 0
            while len(vacancies) < limit:
                resp = requests.get(
                    GET_VACANCIES,
                    headers=self.headers,
                    params={"text": text, "per_page": 50, "page": page}
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                vacancies.extend(items)
                page += 1
                if len(vacancies) >= limit or page >= data.get("pages", 1):
                    break
            return vacancies[:limit]

        def get_vacancy_skills(self, vacancy_id):
            url = f"https://api.hh.ru/vacancies/{vacancy_id}"
            resp = requests.get(url, headers=self.headers)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [s["name"] for s in data.get("key_skills", [])]

    def _extract_resume_title(self, description: str) -> str:
        return description.split(",")[0].strip()

    def _prepare_vacancy_df(self, resume_title: str, candidate_description: str) -> pd.DataFrame:
        all_vacancies = self._hh.get_vacancies(text=resume_title, limit=350)
        if not all_vacancies:
            return pd.DataFrame()

        rows = []
        for v in all_vacancies:
            skills = self._hh.get_vacancy_skills(v["id"])
            rows.append({
                "id": v["id"],
                "name": v["name"],
                "snippet": (v.get("snippet") or {}).get("responsibility") or "",
                "salary_from": (v.get("salary") or {}).get("from"),
                "salary_to": (v.get("salary") or {}).get("to"),
                "currency": (v.get("salary") or {}).get("currency"),
                "skills": ", ".join(skills)
            })
            time.sleep(0.05)

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        rates = {"USD": 100, "EUR": 110, "RUR": 1}
        df["salary"] = df.apply(
            lambda x: np.mean([x["salary_from"], x["salary_to"]]) * rates.get(x["currency"], 1)
            if pd.notnull(x["salary_from"]) or pd.notnull(x["salary_to"]) else np.nan,
            axis=1
        )
        df["salary"].fillna(df["salary"].median(), inplace=True)
        return df

    def _cluster_vacancies(self, df: pd.DataFrame, candidate_description: str):
        vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
        vacancy_vectors = vectorizer.fit_transform(df["snippet"].fillna("")).toarray()
        candidate_vector = vectorizer.transform([candidate_description]).toarray()[0]

        combined_vectors = np.vstack([vacancy_vectors, candidate_vector])
        scaled_vectors = StandardScaler().fit_transform(combined_vectors)

        # 🔧 исправлено:
        n_clusters = min(15, len(combined_vectors))
        if n_clusters < 2:
            n_clusters = 2  # чтобы не падал при 1 вакансии
        elif n_clusters > 15:
            n_clusters = 15

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(scaled_vectors)


        df["cluster"] = clusters[:-1]
        candidate_cluster = clusters[-1]
        df["same_cluster_as_candidate"] = df["cluster"] == candidate_cluster

        return df, candidate_cluster, candidate_vector

    def _extract_hidden_skills(self, df: pd.DataFrame, candidate_description: str) -> dict:
        candidate_skills = set(map(str.lower, candidate_description.replace(",", " ").split()))
        similar_vacancies = df[df["same_cluster_as_candidate"] & df["skills"].notna()]
        skill_freq = {}
        for skills_str in similar_vacancies["skills"]:
            for skill in map(str.lower, skills_str.split(", ")):
                skill_freq[skill] = skill_freq.get(skill, 0) + 1
        hidden_skills = {s: c for s, c in skill_freq.items() if s not in candidate_skills and len(s) > 2}
        return hidden_skills

    # ================= PUBLIC =================
    def analyze_candidate(self, candidate_description: str) -> dict:
        """
        Публичная функция. Принимает описание кандидата и возвращает словарь скрытых навыков с количеством.
        """
        resume_title = self._extract_resume_title(candidate_description)
        df = self._prepare_vacancy_df(resume_title, candidate_description)
        if df.empty:
            return {}

        df, candidate_cluster, candidate_vector = self._cluster_vacancies(df, candidate_description)
        print("candidate_description", candidate_description)
        hidden_skills = self._extract_hidden_skills(df, candidate_description)
        print("hidden_skills", hidden_skills)
        return hidden_skills

    def get_target_vacancies(self, candidate_description: str, limit=10):
        """Возвращает список вакансий для карьерного роста на основе кандидата"""
        resume_title = self._extract_resume_title(candidate_description)
        df = self._prepare_vacancy_df(resume_title, candidate_description)
        if df.empty:
            return []

        # Берём вакансии с наибольшей зарплатой как proxy 'цели'
        df = df.sort_values("salary", ascending=False).head(limit)
        target_vacancies = []
        for _, row in df.iterrows():
            skills = set(row["skills"].split(", ")) if pd.notnull(row["skills"]) else set()
            target_vacancies.append({"id": row["id"], "name": row["name"], "skills": skills,
                                     "salary": f'{row["salary_from"]} - {row["salary_to"]}'
                                     })
        return target_vacancies