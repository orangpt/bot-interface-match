from app.models import Client
import httpx
from bs4 import BeautifulSoup


class ClientService:
    @staticmethod
    def link_client_hh_tg(telegram_id: int, link: str):
        
        resume = ClientService._parse_hh_resume(link)
        client = Client(telegram_id=telegram_id, hh_resume_link=link).save()
        return client

    @staticmethod
    def _parse_hh_resume(link: str) -> None:
        elems = HHResumeParserService.parse_resume_by_url(link)
        print(elems)


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

        data = {
            "name": cls._extract_text(soup, "h1", {"data-qa": "resume-personal-name"}),
            "position": cls._extract_text(soup, "span", {"data-qa": "resume-block-title-position"}),
            "city": cls._extract_text(soup, "span", {"data-qa": "resume-personal-address"}),
            "experience": cls._extract_experience(soup),
        }

        # Проверка на скрытое или удалённое резюме
        if "резюме скрыто" in soup.get_text().lower():
            raise ValueError("Резюме скрыто или удалено")

        return data

    @classmethod
    def _extract_text(cls, soup, tag, attrs):
        el = soup.find(tag, attrs=attrs)
        return el.text.strip() if el else None

    @classmethod
    def _extract_experience(cls, soup):
        exp_block = soup.find("div", {"data-qa": "resume-block-experience"})
        if exp_block:
            return exp_block.get_text("\n", strip=True)
        return None

    @classmethod
    def parse_resume_by_url(cls, url: str) -> dict:
        """Главная точка входа"""
        html = cls.fetch_html(url)
        return cls.parse_resume(html)
