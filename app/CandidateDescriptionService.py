class CandidateDescriptionService:
    @staticmethod
    def build_candidate_description(candidate_dict: dict) -> str:
        """
        Принимает словарь кандидата и возвращает строку candidate description,
        например: "Java backend developer, Spring Boot, Kafka, PostgreSQL, Docker, microservices"
        """
        # --- Берем название позиции ---
        position_title = candidate_dict.get("position", {}).get("title", "").strip()
        if not position_title:
            position_title = "Специалист"

        # --- Берем навыки ---
        skills_list = candidate_dict.get("skills", [])
        skill_names = []
        for s in skills_list:
            # Берем все навыки типа key и advanced, которые явно не general=False (можно менять по логике)
            if s.get("name"):
                skill_names.append(s["name"].strip())

        # --- Формируем строку ---
        candidate_description = position_title
        if skill_names:
            candidate_description += ", " + ", ".join(skill_names)

        return candidate_description