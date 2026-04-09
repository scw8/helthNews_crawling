import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urljoin

import feedparser

from crawlers.base_crawler import BaseCrawler

logger = logging.getLogger(__name__)


class NIHCrawler(BaseCrawler):
    """
    미국 국립보건원 (NIH) RSS 크롤러.
    https://www.nih.gov/news-events/news-releases
    """

    FEED_URL = "https://www.nih.gov/news-events/news-releases/feed"
    BASE_URL = "https://www.nih.gov"

    def __init__(self):
        super().__init__("nih")

    def fetch_list(self) -> list[dict]:
        feed = feedparser.parse(self.FEED_URL)
        items = []

        for entry in feed.entries:
            items.append({
                "url": entry.get("link", ""),
                "title": entry.get("title", "").strip(),
                "published_at": self._parse_date(entry),
            })

        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None

        body = (
            soup.select_one(".news-release-content")
            or soup.select_one("article")
            or soup.select_one(".field-items")
        )
        if not body:
            return None

        for unwanted in body.select("script, style, .share-this, .related-links"):
            unwanted.decompose()

        lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
        return "\n".join(lines)

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


class CDCCrawler(BaseCrawler):
    """
    미국 질병통제예방센터 (CDC) RSS 크롤러.
    https://www.cdc.gov/media/dpk/index.html
    """

    FEED_URL = "https://tools.cdc.gov/api/v2/resources/media/316422.rss"
    BASE_URL = "https://www.cdc.gov"

    def __init__(self):
        super().__init__("cdc")

    def fetch_list(self) -> list[dict]:
        feed = feedparser.parse(self.FEED_URL)
        items = []

        for entry in feed.entries:
            items.append({
                "url": entry.get("link", ""),
                "title": entry.get("title", "").strip(),
                "published_at": self._parse_date(entry),
            })

        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None

        body = (
            soup.select_one(".syndicate")
            or soup.select_one("#content")
            or soup.select_one("article")
            or soup.select_one(".card-body")
        )
        if not body:
            return None

        for unwanted in body.select("script, style, nav, .social-share"):
            unwanted.decompose()

        lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
        return "\n".join(lines)

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


class WHOCrawler(BaseCrawler):
    """
    세계보건기구 (WHO) RSS 크롤러.
    https://www.who.int/news
    """

    FEED_URL = "https://www.who.int/rss-feeds/news-english.xml"
    BASE_URL = "https://www.who.int"

    def __init__(self):
        super().__init__("who")

    def fetch_list(self) -> list[dict]:
        feed = feedparser.parse(self.FEED_URL)
        items = []

        for entry in feed.entries:
            items.append({
                "url": entry.get("link", ""),
                "title": entry.get("title", "").strip(),
                "published_at": self._parse_date(entry),
            })

        return items

    def fetch_content(self, url: str) -> Optional[str]:
        soup = self.get(url)
        if not soup:
            return None

        body = (
            soup.select_one(".sf-detail-body-wrapper")
            or soup.select_one(".content-wrapper")
            or soup.select_one("article")
        )
        if not body:
            return None

        for unwanted in body.select("script, style, .share-block, .tags-block"):
            unwanted.decompose()

        lines = [line.strip() for line in body.get_text().splitlines() if line.strip()]
        return "\n".join(lines)

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
