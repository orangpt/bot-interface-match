"""Парсинг резюме с hh.ru."""
import json
import urllib.parse

import httpx
from bs4 import BeautifulSoup


class HHResumeParserService:
    """Сервис парсинга резюме с hh.ru."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    @classmethod
    def fetch_html(cls, url: str) -> str:
        """Загружает HTML-страницу."""
        with httpx.Client(follow_redirects=True, headers=cls.HEADERS, timeout=15) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    @classmethod
    def parse_resume(cls, html: str) -> dict:
        """Парсит данные из HTML-страницы."""
        soup = BeautifulSoup(html, "html.parser")

        if "резюме скрыто" in soup.get_text().lower():
            raise ValueError("Резюме скрыто или удалено")

        json_data = cls._extract_json_data(soup)
        data = {}

        try:
            data["personal_info"] = cls._extract_personal_info(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении личной информации: {e}")
            data["personal_info"] = {}

        try:
            data["position"] = cls._extract_position(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении должности: {e}")
            data["position"] = {}

        try:
            data["location"] = cls._extract_location(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении местоположения: {e}")
            data["location"] = {}

        try:
            data["experience"] = cls._extract_experience(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении опыта: {e}")
            data["experience"] = []

        try:
            data["education"] = cls._extract_education(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении образования: {e}")
            data["education"] = []

        try:
            data["skills"] = cls._extract_skills(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении навыков: {e}")
            data["skills"] = []

        try:
            data["languages"] = cls._extract_languages(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении языков: {e}")
            data["languages"] = []

        try:
            data["contacts"] = cls._extract_contacts(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении контактов: {e}")
            data["contacts"] = {}

        try:
            data["additional_info"] = cls._extract_additional_info(soup, json_data)
        except Exception as e:
            print(f"Ошибка при извлечении дополнительной информации: {e}")
            data["additional_info"] = {}

        data["raw_json"] = json_data
        return data

    @classmethod
    def _extract_json_data(cls, soup):
        try:
            json_script = soup.find("template", {"id": "HH-Lux-InitialState"})
            if json_script:
                return json.loads(json_script.get_text())
        except (json.JSONDecodeError, AttributeError):
            pass
        return {}

    @classmethod
    def _extract_personal_info(cls, soup, json_data):
        personal_info = {}
        title = soup.find("title")
        if title:
            title_text = title.get_text()
            if "Резюме" in title_text:
                personal_info["name"] = title_text.replace("Резюме", "").strip()

        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            if "firstName" in resume_data and "value" in resume_data["firstName"]:
                personal_info["first_name"] = resume_data["firstName"]["value"]
            if "lastName" in resume_data and "value" in resume_data["lastName"]:
                personal_info["last_name"] = resume_data["lastName"]["value"]
            if "middleName" in resume_data and "value" in resume_data["middleName"]:
                personal_info["middle_name"] = resume_data["middleName"]["value"]
            if "fio" in resume_data:
                personal_info["full_name"] = urllib.parse.unquote(resume_data["fio"])
            if "age" in resume_data and "value" in resume_data["age"]:
                personal_info["age"] = resume_data["age"]["value"]
            if "birthday" in resume_data and "value" in resume_data["birthday"]:
                personal_info["birth_date"] = resume_data["birthday"]["value"]
            if "gender" in resume_data and "value" in resume_data["gender"]:
                personal_info["gender"] = resume_data["gender"]["value"]
            if "relocation" in resume_data and "value" in resume_data["relocation"]:
                personal_info["relocation"] = resume_data["relocation"]["value"]
            if "businessTripReadiness" in resume_data and "value" in resume_data["businessTripReadiness"]:
                personal_info["business_trip_readiness"] = resume_data["businessTripReadiness"]["value"]

        return personal_info

    @classmethod
    def _extract_position(cls, soup, json_data):
        position_info = {}
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            if "title" in resume_data and "value" in resume_data["title"]:
                position_info["title"] = resume_data["title"]["value"]
            if "salary" in resume_data and "value" in resume_data["salary"]:
                salary = resume_data["salary"]["value"]
                if salary:
                    currency = salary.get("currency")
                    currency_title = currency.get("title") if isinstance(currency, dict) else currency
                    position_info["salary"] = {
                        "amount": salary.get("amount"),
                        "currency": currency_title,
                        "gross": salary.get("gross"),
                    }
            if "employment" in resume_data and "value" in resume_data["employment"]:
                employment = resume_data["employment"]["value"]
                if isinstance(employment, list) and employment:
                    position_info["employment"] = [e.get("string") for e in employment if isinstance(e, dict)]
                else:
                    position_info["employment"] = employment
            if "schedule" in resume_data and "value" in resume_data["schedule"]:
                schedule = resume_data["schedule"]["value"]
                if isinstance(schedule, list) and schedule:
                    position_info["schedule"] = [s.get("string") for s in schedule if isinstance(s, dict)]
                else:
                    position_info["schedule"] = schedule
        return position_info

    @classmethod
    def _extract_location(cls, soup, json_data):
        location_info = {}
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            if "area" in resume_data and "value" in resume_data["area"]:
                area = resume_data["area"]["value"]
                if isinstance(area, dict):
                    location_info["city"] = area.get("title")
                    location_info["city_id"] = area.get("id")
            if "metro" in resume_data and "value" in resume_data["metro"]:
                location_info["metro"] = resume_data["metro"]["value"]
            if "residenceDistrict" in resume_data and "value" in resume_data["residenceDistrict"]:
                location_info["district"] = resume_data["residenceDistrict"]["value"]
            if "citizenship" in resume_data and "value" in resume_data["citizenship"]:
                citizenship = resume_data["citizenship"]["value"]
                if isinstance(citizenship, list) and citizenship:
                    location_info["citizenship"] = [c.get("title") for c in citizenship if isinstance(c, dict)]
                else:
                    location_info["citizenship"] = citizenship
        return location_info

    @classmethod
    def _extract_experience(cls, soup, json_data):
        experience = []
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            if "experience" in resume_data and "value" in resume_data["experience"]:
                for exp in resume_data["experience"]["value"]:
                    if isinstance(exp, dict):
                        experience.append({
                            "id": exp.get("id"),
                            "company": exp.get("companyName") or (exp.get("company", {}).get("name") if isinstance(exp.get("company"), dict) else exp.get("company")),
                            "position": exp.get("position"),
                            "description": exp.get("description"),
                            "start_date": exp.get("startDate"),
                            "end_date": exp.get("endDate"),
                            "current": exp.get("current", False),
                            "area": exp.get("area", {}).get("name") if isinstance(exp.get("area"), dict) else exp.get("area"),
                            "company_id": exp.get("companyId"),
                            "company_url": exp.get("companyUrl"),
                            "company_industry": exp.get("companyIndustries", []),
                            "profession": exp.get("professionName"),
                        })
            if "totalExperience" in resume_data:
                total_exp = resume_data["totalExperience"]
                if isinstance(total_exp, dict):
                    experience.append({
                        "type": "total",
                        "years": total_exp.get("years"),
                        "months": total_exp.get("months"),
                    })
        return experience

    @classmethod
    def _extract_education(cls, soup, json_data):
        education = []
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            if "educationLevel" in resume_data and "value" in resume_data["educationLevel"]:
                education.append({"type": "level", "level": resume_data["educationLevel"]["value"]})
            if "primaryEducation" in resume_data and "value" in resume_data["primaryEducation"]:
                for edu in resume_data["primaryEducation"]["value"]:
                    if isinstance(edu, dict):
                        education.append({
                            "type": "primary",
                            "id": edu.get("id"),
                            "institution": edu.get("name"),
                            "faculty": edu.get("organization"),
                            "specialization": edu.get("result"),
                            "year": edu.get("year"),
                            "level": edu.get("educationLevel"),
                        })
            if "additionalEducation" in resume_data and "value" in resume_data["additionalEducation"]:
                for edu in resume_data["additionalEducation"]["value"]:
                    if isinstance(edu, dict):
                        education.append({
                            "type": "additional",
                            "institution": edu.get("name"),
                            "organization": edu.get("organization"),
                            "result": edu.get("result"),
                            "year": edu.get("year"),
                        })
            if "attestationEducation" in resume_data and "value" in resume_data["attestationEducation"]:
                for edu in resume_data["attestationEducation"]["value"]:
                    if isinstance(edu, dict):
                        education.append({
                            "type": "attestation",
                            "institution": edu.get("name"),
                            "organization": edu.get("organization"),
                            "result": edu.get("result"),
                            "year": edu.get("year"),
                        })
        return education

    @classmethod
    def _extract_skills(cls, soup, json_data):
        skills = []
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            if "keySkills" in resume_data and "value" in resume_data["keySkills"]:
                for skill in resume_data["keySkills"]["value"]:
                    if isinstance(skill, dict):
                        skills.append({
                            "type": "key",
                            "name": skill.get("string"),
                            "id": skill.get("id"),
                            "general": skill.get("general", False),
                        })
            if "advancedKeySkills" in resume_data and "value" in resume_data["advancedKeySkills"]:
                for skill in resume_data["advancedKeySkills"]["value"]:
                    if isinstance(skill, dict):
                        skills.append({
                            "type": "advanced",
                            "name": skill.get("name"),
                            "id": skill.get("id"),
                            "general": skill.get("general", False),
                        })
            if "skills" in resume_data and "value" in resume_data["skills"]:
                for skill in resume_data["skills"]["value"] or []:
                    if isinstance(skill, dict):
                        skills.append({
                            "type": "experience",
                            "name": skill.get("name"),
                            "id": skill.get("id"),
                            "general": skill.get("general", False),
                        })
        return skills

    @classmethod
    def _extract_languages(cls, soup, json_data):
        languages = []
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            if "language" in resume_data and "value" in resume_data["language"]:
                for lang in resume_data["language"]["value"]:
                    if isinstance(lang, dict):
                        languages.append({
                            "id": lang.get("id"),
                            "name": lang.get("title"),
                            "level": lang.get("degree"),
                        })
        return languages

    @classmethod
    def _extract_contacts(cls, soup, json_data):
        contacts = {}
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            for field in ["email", "phone", "skype", "homepage", "contact"]:
                if field in resume_data:
                    val = resume_data[field]
                    contacts[field] = val["value"] if isinstance(val, dict) and "value" in val else val
        return contacts

    @classmethod
    def _extract_additional_info(cls, soup, json_data):
        additional_info = {}
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            additional_info.update({
                "id": resume_data.get("id"),
                "hash": resume_data.get("hash"),
                "status": resume_data.get("status"),
                "percent": resume_data.get("percent"),
                "created_at": resume_data.get("created_at"),
                "updated_at": resume_data.get("updated_at"),
                "permission": resume_data.get("permission"),
                "source": resume_data.get("source"),
            })
            if "totalExperience" in resume_data:
                te = resume_data["totalExperience"]
                if isinstance(te, dict):
                    additional_info["total_experience"] = {"years": te.get("years"), "months": te.get("months")}
            if "specializations" in resume_data and "value" in resume_data["specializations"]:
                spec_val = resume_data["specializations"]["value"]
                if isinstance(spec_val, list):
                    additional_info["specializations"] = [s.get("name") for s in spec_val if isinstance(s, dict)]
            if "driverLicenseTypes" in resume_data and "value" in resume_data["driverLicenseTypes"]:
                additional_info["driver_license"] = resume_data["driverLicenseTypes"]["value"]
            if "hasVehicle" in resume_data and "value" in resume_data["hasVehicle"]:
                additional_info["has_vehicle"] = resume_data["hasVehicle"]["value"]
            if "portfolio" in resume_data and "value" in resume_data["portfolio"]:
                additional_info["portfolio"] = resume_data["portfolio"]["value"]
            if "recommendation" in resume_data and "value" in resume_data["recommendation"]:
                additional_info["recommendations"] = resume_data["recommendation"]["value"]
        return additional_info

    @classmethod
    def parse_resume_by_url(cls, url: str) -> dict:
        """Загружает страницу по URL и парсит резюме."""
        html = cls.fetch_html(url)
        return cls.parse_resume(html)
