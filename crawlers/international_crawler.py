import logging
from typing import Optional

import feedparser

from crawlers.base_crawler import BaseCrawler, parse_rss_date

logger = logging.getLogger(__name__)


class WHOCrawler(BaseCrawler):
    """세계보건기구 (WHO) RSS 크롤러."""

    FEED_URL = "https://www.who.int/rss-feeds/news-english.xml"

    def __init__(self):
        super().__init__("who")

    def fetch_list(self) -> list[dict]:
        feed = feedparser.parse(self.FEED_URL)
        return [
            {
                "url": entry.get("link", ""),
                "title": entry.get("title", "").strip(),
                "published_at": parse_rss_date(entry),
            }
            for entry in feed.entries
        ]

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
