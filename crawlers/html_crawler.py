import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import feedparser

from crawlers.base_crawler import BaseCrawler, parse_rss_date

logger = logging.getLogger(__name__)

# 한국 공공기관에서 자주 쓰는 날짜 형식: YYYY.MM.DD / YYYY-MM-DD / YYYY/MM/DD
_DATE_RE = re.compile(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})')


def _parse_date_from_text(text: str) -> Optional[datetime]:
    """문자열에서 날짜 패턴(YYYY.MM.DD 등) 추출."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _extract_date_from_row(row) -> Optional[datetime]:
    """테이블 행의 모든 td를 순회해 날짜 패턴이 있는 셀 반환."""
    for td in row.find_all("td"):
        dt = _parse_date_from_text(td.get_text(strip=True))
        if dt:
            return dt
    return None


class KDCACrawler(BaseCrawler):
    """질병관리청 보도자료 크롤러 - RSS 방식"""

    RSS_URL = "https://www.kdca.go.kr/bbs/kdca/41/rssList.do?row=50"
    BASE_URL = "https://www.kdca.go.kr"

    def __init__(self):
        super().__init__("kdca")

    def fetch_list(self) -> list[dict]:
        feed = feedparser.parse(self.RSS_URL)
        items = []
        for entry in feed.entries:
            title = re.sub(r'\(\d+\.\d+\.[\w]+\)\}?$', '', entry.get("title", "").strip()).strip()
            items.append({
                "url": entry.get("link", ""),
                "title": title,
                "published_at": parse_rss_date(entry),
            })
        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None
        body = (
            soup.select_one("#contentsEditHtml")
            or soup.select_one("article._contentBuilder")
            or soup.select_one(".board-view-content")
            or soup.select_one(".view-content")
            or soup.select_one(".artcl-view")
            or soup.select_one("#artclView")
        )
        if not body:
            return None
        for unwanted in body.select("script, style, .file-list, .btn-wrap"):
            unwanted.decompose()
        lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
        return "\n".join(lines)


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
        for row in soup.select("table tbody tr"):
            a_tag = row.select_one("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if not href or "download" in href:
                continue
            url = (self.LIST_URL + href) if href.startswith("?") else urljoin(self.BASE_URL, href)
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            items.append({"url": url, "title": title, "published_at": _extract_date_from_row(row)})
        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None
        for selector in [".view-content", ".board-view", ".artcl-view", "#artclView", ".content-area"]:
            body = soup.select_one(selector)
            if body and len(body.get_text(strip=True)) > 200:
                for unwanted in body.select("script, style"):
                    unwanted.decompose()
                lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
                return "\n".join(lines)
        return None


class SNUHCrawler(BaseCrawler):
    """서울대학교병원 건강정보 크롤러 (건강백과, 날짜 없음)"""

    BASE_URL = "https://www.snuh.org"
    LIST_URL = "https://www.snuh.org/health/nMedInfo/nList.do"

    def __init__(self):
        super().__init__("snuh")

    def fetch_list(self) -> list[dict]:
        soup = self.get(self.LIST_URL)
        if not soup:
            return []
        items = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            if "nView.do" not in href:
                continue
            url = urljoin(self.BASE_URL + "/health/nMedInfo/", href)
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            items.append({"url": url, "title": title, "published_at": None})
        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None
        for selector in [".health-content", ".view-content", ".nMedInfo-view", ".content", "#content"]:
            body = soup.select_one(selector)
            if body and len(body.get_text(strip=True)) > 100:
                for unwanted in body.select("script, style"):
                    unwanted.decompose()
                lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
                return "\n".join(lines)
        return None


class MOHWCrawler(BaseCrawler):
    """보건복지부 보도자료 크롤러"""

    BASE_URL = "https://www.mohw.go.kr"
    LIST_URL = "https://www.mohw.go.kr/board.es?mid=a10503010100&bid=0027"

    def __init__(self):
        super().__init__("mohw")

    def fetch_list(self) -> list[dict]:
        soup = self.get(self.LIST_URL)
        if not soup:
            return []
        items = []
        for row in soup.select("table tbody tr"):
            a_tag = row.select_one("td.title a, td a[href*='act=view']")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if not href or "act=view" not in href:
                continue
            url = urljoin(self.BASE_URL, href) if href.startswith("/") else href
            title = a_tag.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            items.append({"url": url, "title": title, "published_at": _extract_date_from_row(row)})
        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None
        for selector in [
            ".board-view-content", ".bdvContent", ".view_content",
            "#contentsArea .view-content", ".brd-body", "div.view-content",
            "#artclView", ".cont_inner",
        ]:
            body = soup.select_one(selector)
            if body and len(body.get_text(strip=True)) > 100:
                for unwanted in body.select("script, style, .file-list, .btn-wrap"):
                    unwanted.decompose()
                lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
                return "\n".join(lines)
        return None
