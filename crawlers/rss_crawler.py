import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
from bs4 import BeautifulSoup

from crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class RSSCrawler(BaseCrawler):
    """
    RSS 피드 기반 크롤러.
    헬스조선, 메디컬투데이, 코메디닷컴 등 RSS 제공 사이트용.
    """

    def __init__(self, source_name: str, feed_url: str, request_delay: float = 2.0):
        super().__init__(source_name, request_delay)
        self.feed_url = feed_url

    def fetch_list(self) -> list[dict]:
        feed = feedparser.parse(self.feed_url)
        items = []

        for entry in feed.entries:
            published_at = self._parse_date(entry)
            items.append({
                "url": entry.get("link", ""),
                "title": entry.get("title", "").strip(),
                "published_at": published_at,
            })

        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None

        # 사이트별 본문 선택자 순서대로 시도
        selectors = [
            "article",
            "[class*='article-body']",
            "[class*='article_body']",
            "[class*='content-body']",
            "[class*='news-body']",
            "[class*='view-content']",
            "[id*='article-body']",
            "[id*='news_body']",
        ]

        for selector in selectors:
            body = soup.select_one(selector)
            if body and len(body.get_text(strip=True)) > 200:
                return self._clean_text(body)

        return None

    def _parse_date(self, entry) -> Optional[datetime]:
        for field in ["published", "updated"]:
            value = entry.get(field)
            if value:
                try:
                    dt = parsedate_to_datetime(value)
                    return dt.astimezone(timezone.utc).replace(tzinfo=timezone.utc)
                except Exception:
                    continue
        return None

    def _clean_text(self, tag) -> str:
        # 광고, 관련기사 등 불필요한 태그 제거
        for unwanted in tag.select("script, style, .ad, .advertisement, .related, figure"):
            unwanted.decompose()
        lines = [line.strip() for line in tag.get_text().splitlines() if line.strip()]
        return "\n".join(lines)
