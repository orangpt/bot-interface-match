from app.models import Client
import httpx
from bs4 import BeautifulSoup
import json
import re


class ClientService:
    @staticmethod
    def link_client_hh_tg(telegram_id: int, link: str):
        
        resume = ClientService._parse_hh_resume(link)
        client = Client(telegram_id=telegram_id, hh_resume_link=link, resume_ontology=resume).save()
        return client

    @staticmethod
    def _parse_hh_resume(link: str) -> dict:
        try:
            elems = HHResumeParserService.parse_resume_by_url(link)
            
            # Сохраняем основную информацию в temp_dp.json
            ClientService._save_to_temp_file(elems)
            
            return elems
        except Exception as e:
            print(f"Ошибка при парсинге резюме {link}: {e}")
            # Возвращаем пустую структуру в случае ошибки
            return {
                "personal_info": {},
                "position": {},
                "location": {},
                "experience": [],
                "education": [],
                "skills": [],
                "languages": [],
                "contacts": {},
                "additional_info": {},
                "raw_json": {}
            }
    
    @staticmethod
    def _save_to_temp_file(data: dict):
        """Сохраняет основную информацию в temp_dp.json с накоплением данных"""
        import os
        import json
        from datetime import datetime
        
        try:
            # Основная информация для сохранения с безопасным извлечением
            main_info = {
                "timestamp": datetime.now().isoformat(),
                "personal_info": data.get("personal_info", {}),
                "position": data.get("position", {}),
                "location": data.get("location", {}),
                "experience": data.get("experience", []),  # Полный список опыта работы
                "education": data.get("education", []),   # Полный список образования
                "skills": data.get("skills", []),         # Полный список навыков
                "languages": data.get("languages", []),
                "contacts": data.get("contacts", {}),
                "additional_info": data.get("additional_info", {}),
                "experience_summary": {
                    "total_experience": data.get("additional_info", {}).get("total_experience"),
                    "experience_count": len(data.get("experience", []))
                },
                "education_summary": {
                    "education_count": len(data.get("education", [])),
                    "education_level": data.get("education", [{}])[0].get("level") if data.get("education") else None
                },
                "skills_summary": {
                    "skills_count": len(data.get("skills", [])),
                    "key_skills": [skill.get("name") for skill in data.get("skills", []) if isinstance(skill, dict) and skill.get("type") == "key"][:5]  # Первые 5 ключевых навыков
                },
                "resume_id": data.get("additional_info", {}).get("id"),
                "resume_hash": data.get("additional_info", {}).get("hash")
            }
            
            # Путь к файлу
            temp_file = "temp_dp.json"
            
            # Читаем существующие данные
            existing_data = []
            if os.path.exists(temp_file):
                try:
                    with open(temp_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = []
                except (json.JSONDecodeError, FileNotFoundError):
                    existing_data = []
            
            # Добавляем новую запись
            existing_data.append(main_info)
            
            # Сохраняем обновленные данные
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
            print(f"Данные сохранены в {temp_file}. Всего записей: {len(existing_data)}")
            
        except Exception as e:
            print(f"Ошибка при сохранении в temp_dp.json: {e}")
            # Создаем минимальную запись об ошибке
            try:
                error_info = {
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                    "personal_info": {},
                    "position": {},
                    "location": {},
                    "experience_summary": {"total_experience": None, "experience_count": 0},
                    "education_summary": {"education_count": 0, "education_level": None},
                    "skills_summary": {"skills_count": 0, "key_skills": []},
                    "languages": [],
                    "contacts": {},
                    "resume_id": None,
                    "resume_hash": None
                }
                
                temp_file = "temp_dp.json"
                existing_data = []
                if os.path.exists(temp_file):
                    try:
                        with open(temp_file, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        if not isinstance(existing_data, list):
                            existing_data = []
                    except:
                        existing_data = []
                
                existing_data.append(error_info)
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=2)
                    
                print(f"Запись об ошибке сохранена в {temp_file}")
            except:
                print("Не удалось сохранить даже запись об ошибке")


class HHResumeParserService:
    """
    Сервис парсинга резюме с hh.ru
    """

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
        """Загружает HTML-страницу"""
        with httpx.Client(follow_redirects=True, headers=cls.HEADERS, timeout=15) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    @classmethod
    def parse_resume(cls, html: str) -> dict:
        """Парсит данные из HTML-страницы"""
        soup = BeautifulSoup(html, "html.parser")

        # Проверка на скрытое или удалённое резюме
        if "резюме скрыто" in soup.get_text().lower():
            raise ValueError("Резюме скрыто или удалено")

        # Извлекаем JSON данные из HH-Lux-InitialState
        json_data = cls._extract_json_data(soup)
        
        # Структурированные данные с обработкой ошибок
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
        
        data["raw_json"] = json_data  # Сохраняем сырые JSON данные для отладки

        return data

    @classmethod
    def _extract_json_data(cls, soup):
        """Извлекает JSON данные из HH-Lux-InitialState"""
        try:
            json_script = soup.find("template", {"id": "HH-Lux-InitialState"})
            if json_script:
                json_text = json_script.get_text()
                return json.loads(json_text)
        except (json.JSONDecodeError, AttributeError):
            pass
        return {}

    @classmethod
    def _extract_personal_info(cls, soup, json_data):
        """Извлекает личную информацию"""
        personal_info = {}
        
        # Имя из title или JSON
        title = soup.find("title")
        if title:
            title_text = title.get_text()
            if "Резюме" in title_text:
                name = title_text.replace("Резюме", "").strip()
                personal_info["name"] = name
        
        # Извлекаем данные из JSON
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Извлекаем ФИО
            if "firstName" in resume_data and "value" in resume_data["firstName"]:
                personal_info["first_name"] = resume_data["firstName"]["value"]
            if "lastName" in resume_data and "value" in resume_data["lastName"]:
                personal_info["last_name"] = resume_data["lastName"]["value"]
            if "middleName" in resume_data and "value" in resume_data["middleName"]:
                personal_info["middle_name"] = resume_data["middleName"]["value"]
            
            # Полное имя
            if "fio" in resume_data:
                import urllib.parse
                personal_info["full_name"] = urllib.parse.unquote(resume_data["fio"])
            
            # Возраст и дата рождения
            if "age" in resume_data and "value" in resume_data["age"]:
                personal_info["age"] = resume_data["age"]["value"]
            if "birthday" in resume_data and "value" in resume_data["birthday"]:
                personal_info["birth_date"] = resume_data["birthday"]["value"]
            
            # Пол
            if "gender" in resume_data and "value" in resume_data["gender"]:
                personal_info["gender"] = resume_data["gender"]["value"]
            
            # Готовность к переезду
            if "relocation" in resume_data and "value" in resume_data["relocation"]:
                personal_info["relocation"] = resume_data["relocation"]["value"]
            
            # Готовность к командировкам
            if "businessTripReadiness" in resume_data and "value" in resume_data["businessTripReadiness"]:
                personal_info["business_trip_readiness"] = resume_data["businessTripReadiness"]["value"]
        
        return personal_info

    @classmethod
    def _extract_position(cls, soup, json_data):
        """Извлекает информацию о должности"""
        position_info = {}
        
        # Из JSON данных
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Должность
            if "title" in resume_data and "value" in resume_data["title"]:
                position_info["title"] = resume_data["title"]["value"]
            
            # Зарплата
            if "salary" in resume_data and "value" in resume_data["salary"]:
                salary = resume_data["salary"]["value"]
                if salary:  # Проверяем, что salary не None
                    currency = salary.get("currency")
                    currency_title = None
                    if currency:
                        if isinstance(currency, dict):
                            currency_title = currency.get("title")
                        elif isinstance(currency, str):
                            currency_title = currency
                    
                    position_info["salary"] = {
                        "amount": salary.get("amount"),
                        "currency": currency_title,
                        "gross": salary.get("gross")
                    }
            
            # Тип занятости
            if "employment" in resume_data and "value" in resume_data["employment"]:
                employment = resume_data["employment"]["value"]
                if isinstance(employment, list) and len(employment) > 0:
                    position_info["employment"] = [emp.get("string") for emp in employment if isinstance(emp, dict)]
                else:
                    position_info["employment"] = employment
            
            # График работы
            if "schedule" in resume_data and "value" in resume_data["schedule"]:
                schedule = resume_data["schedule"]["value"]
                if isinstance(schedule, list) and len(schedule) > 0:
                    position_info["schedule"] = [sch.get("string") for sch in schedule if isinstance(sch, dict)]
                else:
                    position_info["schedule"] = schedule
        
        return position_info

    @classmethod
    def _extract_location(cls, soup, json_data):
        """Извлекает информацию о местоположении"""
        location_info = {}
        
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Город/область
            if "area" in resume_data and "value" in resume_data["area"]:
                area = resume_data["area"]["value"]
                if isinstance(area, dict):
                    location_info["city"] = area.get("title")
                    location_info["city_id"] = area.get("id")
            
            # Метро
            if "metro" in resume_data and "value" in resume_data["metro"]:
                metro = resume_data["metro"]["value"]
                if metro:
                    location_info["metro"] = metro
            
            # Район проживания
            if "residenceDistrict" in resume_data and "value" in resume_data["residenceDistrict"]:
                district = resume_data["residenceDistrict"]["value"]
                if district:
                    location_info["district"] = district
            
            # Гражданство
            if "citizenship" in resume_data and "value" in resume_data["citizenship"]:
                citizenship = resume_data["citizenship"]["value"]
                if isinstance(citizenship, list) and len(citizenship) > 0:
                    location_info["citizenship"] = [cit.get("title") for cit in citizenship if isinstance(cit, dict)]
                else:
                    location_info["citizenship"] = citizenship
        
        return location_info

    @classmethod
    def _extract_experience(cls, soup, json_data):
        """Извлекает опыт работы"""
        experience = []
        
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Опыт работы
            if "experience" in resume_data and "value" in resume_data["experience"]:
                for exp in resume_data["experience"]["value"]:
                    if isinstance(exp, dict):
                        exp_info = {
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
                            "profession": exp.get("professionName")
                        }
                        experience.append(exp_info)
            
            # Общий опыт работы
            if "totalExperience" in resume_data:
                total_exp = resume_data["totalExperience"]
                if isinstance(total_exp, dict):
                    experience.append({
                        "type": "total",
                        "years": total_exp.get("years"),
                        "months": total_exp.get("months")
                    })
        
        return experience

    @classmethod
    def _extract_education(cls, soup, json_data):
        """Извлекает информацию об образовании"""
        education = []
        
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Уровень образования
            if "educationLevel" in resume_data and "value" in resume_data["educationLevel"]:
                education.append({
                    "type": "level",
                    "level": resume_data["educationLevel"]["value"]
                })
            
            # Основное образование
            if "primaryEducation" in resume_data and "value" in resume_data["primaryEducation"]:
                for edu in resume_data["primaryEducation"]["value"]:
                    if isinstance(edu, dict):
                        edu_info = {
                            "type": "primary",
                            "id": edu.get("id"),
                            "institution": edu.get("name"),
                            "faculty": edu.get("organization"),
                            "specialization": edu.get("result"),
                            "year": edu.get("year"),
                            "level": edu.get("educationLevel")
                        }
                        education.append(edu_info)
            
            # Дополнительное образование
            if "additionalEducation" in resume_data and "value" in resume_data["additionalEducation"]:
                for edu in resume_data["additionalEducation"]["value"]:
                    if isinstance(edu, dict):
                        edu_info = {
                            "type": "additional",
                            "institution": edu.get("name"),
                            "organization": edu.get("organization"),
                            "result": edu.get("result"),
                            "year": edu.get("year")
                        }
                        education.append(edu_info)
            
            # Аттестация
            if "attestationEducation" in resume_data and "value" in resume_data["attestationEducation"]:
                for edu in resume_data["attestationEducation"]["value"]:
                    if isinstance(edu, dict):
                        edu_info = {
                            "type": "attestation",
                            "institution": edu.get("name"),
                            "organization": edu.get("organization"),
                            "result": edu.get("result"),
                            "year": edu.get("year")
                        }
                        education.append(edu_info)
        
        return education

    @classmethod
    def _extract_skills(cls, soup, json_data):
        """Извлекает навыки"""
        skills = []
        
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Ключевые навыки
            if "keySkills" in resume_data and "value" in resume_data["keySkills"]:
                for skill in resume_data["keySkills"]["value"]:
                    if isinstance(skill, dict):
                        skill_info = {
                            "type": "key",
                            "name": skill.get("string"),
                            "id": skill.get("id"),
                            "general": skill.get("general", False)
                        }
                        skills.append(skill_info)
            
            # Продвинутые навыки
            if "advancedKeySkills" in resume_data and "value" in resume_data["advancedKeySkills"]:
                for skill in resume_data["advancedKeySkills"]["value"]:
                    if isinstance(skill, dict):
                        skill_info = {
                            "type": "advanced",
                            "name": skill.get("name"),
                            "id": skill.get("id"),
                            "general": skill.get("general", False)
                        }
                        skills.append(skill_info)
            
            # Навыки из блока опыта
            if "skills" in resume_data and "value" in resume_data["skills"]:
                skills_data = resume_data["skills"]["value"]
                if isinstance(skills_data, list):
                    for skill in skills_data:
                        if isinstance(skill, dict):
                            skill_info = {
                                "type": "experience",
                                "name": skill.get("name"),
                                "id": skill.get("id"),
                                "general": skill.get("general", False)
                            }
                            skills.append(skill_info)
        
        return skills

    @classmethod
    def _extract_languages(cls, soup, json_data):
        """Извлекает информацию о языках"""
        languages = []
        
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Языки
            if "language" in resume_data and "value" in resume_data["language"]:
                for lang in resume_data["language"]["value"]:
                    if isinstance(lang, dict):
                        lang_info = {
                            "id": lang.get("id"),
                            "name": lang.get("title"),
                            "level": lang.get("degree")
                        }
                        languages.append(lang_info)
        
        return languages

    @classmethod
    def _extract_contacts(cls, soup, json_data):
        """Извлекает контактную информацию"""
        contacts = {}
        
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Поиск контактной информации в различных полях
            contact_fields = ["email", "phone", "skype", "homepage", "contact"]
            for field in contact_fields:
                if field in resume_data:
                    if isinstance(resume_data[field], dict) and "value" in resume_data[field]:
                        contacts[field] = resume_data[field]["value"]
                    else:
                        contacts[field] = resume_data[field]
        
        return contacts

    @classmethod
    def _extract_additional_info(cls, soup, json_data):
        """Извлекает дополнительную информацию"""
        additional_info = {}
        
        if "resume" in json_data:
            resume_data = json_data.get("resume", {})
            
            # Основная информация о резюме
            additional_info.update({
                "id": resume_data.get("id"),
                "hash": resume_data.get("hash"),
                "status": resume_data.get("status"),
                "percent": resume_data.get("percent"),
                "created_at": resume_data.get("created_at"),
                "updated_at": resume_data.get("updated_at"),
                "permission": resume_data.get("permission"),
                "source": resume_data.get("source")
            })
            
            # Общий опыт работы
            if "totalExperience" in resume_data:
                total_exp = resume_data["totalExperience"]
                if isinstance(total_exp, dict):
                    additional_info["total_experience"] = {
                        "years": total_exp.get("years"),
                        "months": total_exp.get("months")
                    }
            
            # Специализации
            if "specializations" in resume_data and "value" in resume_data["specializations"]:
                specializations = resume_data["specializations"]["value"]
                if isinstance(specializations, list):
                    additional_info["specializations"] = [spec.get("name") for spec in specializations if isinstance(spec, dict)]
            
            # Водительские права
            if "driverLicenseTypes" in resume_data and "value" in resume_data["driverLicenseTypes"]:
                additional_info["driver_license"] = resume_data["driverLicenseTypes"]["value"]
            
            # Наличие автомобиля
            if "hasVehicle" in resume_data and "value" in resume_data["hasVehicle"]:
                additional_info["has_vehicle"] = resume_data["hasVehicle"]["value"]
            
            # Портфолио
            if "portfolio" in resume_data and "value" in resume_data["portfolio"]:
                additional_info["portfolio"] = resume_data["portfolio"]["value"]
            
            # Рекомендации
            if "recommendation" in resume_data and "value" in resume_data["recommendation"]:
                additional_info["recommendations"] = resume_data["recommendation"]["value"]
        
        return additional_info

    @classmethod
    def _extract_text(cls, soup, tag, attrs):
        el = soup.find(tag, attrs=attrs)
        return el.text.strip() if el else None

    @classmethod
    def _safe_get(cls, data, key, default=None):
        """Безопасное извлечение значения из словаря"""
        if not isinstance(data, dict):
            return default
        return data.get(key, default)

    @classmethod
    def _safe_get_nested(cls, data, keys, default=None):
        """Безопасное извлечение вложенного значения"""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @classmethod
    def parse_resume_by_url(cls, url: str) -> dict:
        """Главная точка входа"""
        html = cls.fetch_html(url)
        with open("resuem.html", "w", encoding="utf-8") as f:
            f.write(html)
        return cls.parse_resume(html)