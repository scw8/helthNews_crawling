import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

from crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class KDCACrawler(BaseCrawler):
    """질병관리청 보도자료 크롤러"""

    BASE_URL = "https://www.kdca.go.kr"
    LIST_URL = "https://www.kdca.go.kr/board/board.es?mid=a20501000000&bid=0015"

    def __init__(self):
        super().__init__("kdca")

    def fetch_list(self) -> list[dict]:
        soup = self.get(self.LIST_URL)
        if not soup:
            return []

        items = []
        rows = soup.select(".board-list tbody tr")

        for row in rows:
            a_tag = row.select_one(".subject a")
            if not a_tag:
                continue

            href = a_tag.get("href", "")
            url = urljoin(self.BASE_URL, href)
            title = a_tag.get_text(strip=True)

            date_td = row.select_one("td:last-child")
            published_at = self._parse_date(date_td.get_text(strip=True) if date_td else "")

            items.append({"url": url, "title": title, "published_at": published_at})

        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None

        body = soup.select_one(".board-view-content") or soup.select_one(".view-content")
        if not body:
            return None

        for unwanted in body.select("script, style, .file-list"):
            unwanted.decompose()

        lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
        return "\n".join(lines)

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None


class NHISCrawler(BaseCrawler):
    """국민건강보험공단 건강정보 크롤러"""

    BASE_URL = "https://www.nhis.or.kr"
    LIST_URL = "https://www.nhis.or.kr/nhis/together/wbhaec07100m01.do"

    def __init__(self):
        super().__init__("nhis")

    def fetch_list(self) -> list[dict]:
        soup = self.get(self.LIST_URL)
        if not soup:
            return []

        items = []
        rows = soup.select(".board_list tbody tr, .list-wrap li")

        for row in rows:
            a_tag = row.select_one("a")
            if not a_tag:
                continue

            href = a_tag.get("href", "")
            url = urljoin(self.BASE_URL, href)
            title = a_tag.get_text(strip=True)

            if not title:
                continue

            items.append({"url": url, "title": title, "published_at": None})

        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None

        selectors = [".view-content", ".board-view", ".content-area", "article"]
        for selector in selectors:
            body = soup.select_one(selector)
            if body and len(body.get_text(strip=True)) > 200:
                for unwanted in body.select("script, style"):
                    unwanted.decompose()
                lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
                return "\n".join(lines)

        return None


class SNUHCrawler(BaseCrawler):
    """서울대학교병원 건강정보 크롤러"""

    BASE_URL = "https://www.snuh.org"
    LIST_URL = "https://www.snuh.org/health/nMedInfo/nList.do"

    def __init__(self):
        super().__init__("snuh")

    def fetch_list(self) -> list[dict]:
        soup = self.get(self.LIST_URL)
        if not soup:
            return []

        items = []
        links = soup.select(".list-wrap a, .board-list a")

        for a_tag in links:
            href = a_tag.get("href", "")
            if not href or "nView" not in href:
                continue

            url = urljoin(self.BASE_URL, href)
            title = a_tag.get_text(strip=True)

            if not title:
                continue

            items.append({"url": url, "title": title, "published_at": None})

        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None

        body = soup.select_one(".health-content, .view-content, .content")
        if not body:
            return None

        for unwanted in body.select("script, style"):
            unwanted.decompose()

        lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
        return "\n".join(lines)
