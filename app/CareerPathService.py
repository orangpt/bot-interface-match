import numpy as np
from scipy.spatial.distance import cosine

class CareerPathService:
    """Строит пошаговый карьерный план на основе вакансий и навыков кандидата."""

    def __init__(self, hh_market_service, youmap_service):
        self.hh_market_service = hh_market_service
        self.youmap_service = youmap_service

    def _calculate_edge_weight(self, current_skills, target_skills, semantic_distance, time_penalty=6):
        """Вес перехода от текущей позиции к цели."""
        skill_gap = len(target_skills - current_skills)
        return semantic_distance + skill_gap + time_penalty

    def _find_shortest_path(self, start_skills, target_vacancies):
        """
        Ищем путь через граф вакансий.
        В этой версии делаем упрощение: greedy выбор следующей вакансии с минимальным весом.
        """
        path = []
        current_skills = set(start_skills)
        visited = set()
        for vacancy in target_vacancies:
            if vacancy["id"] in visited:
                continue
            target_skills = set(vacancy["skills"])
            # семантическое расстояние между навыками
            semantic_distance = 1 - len(current_skills & target_skills) / (len(current_skills | target_skills) + 1e-5)
            weight = self._calculate_edge_weight(current_skills, target_skills, semantic_distance)
            path.append({
                "vacancy": vacancy,
                "missing_skills": list(target_skills - current_skills),
                "weight": weight
            })
            current_skills |= target_skills
            visited.add(vacancy["id"])
        return path

    def _prioritize_skills(self, missing_skills, roi_map):
        """Сортируем навыки по ROI (ценности изучения)"""
        return sorted(missing_skills, key=lambda x: roi_map.get(x, 1.0), reverse=True)

    def generate_growth_plan(self, candidate_description, target_vacancies, roi_map=None):
        """
        public method
        candidate_description: список известных навыков кандидата
        target_vacancies: список вакансий (из HHMarketService)
        roi_map: dict {skill: value} для приоритизации навыков
        """
        if roi_map is None:
            roi_map = {}

        start_skills = set(candidate_description.split(", "))
        path = self._find_shortest_path(start_skills, target_vacancies)

        # Формируем план
        growth_plan = []
        months = 0
        for step in path:
            months += 6  # условный шаг 6 месяцев
            stage = {
                "period": f"{months-6}-{months} мес.",
                "position": step["vacancy"]["name"],
                "learn_skills": self._prioritize_skills(step["missing_skills"], roi_map),
                "weight": step["weight"]
            }
            growth_plan.append(stage)
        return growth_plan
