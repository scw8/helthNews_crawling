import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class RawArticle:
    """크롤링 직후 원본 데이터 (필터링 전)"""
    url: str
    title: str
    content: str
    source: str
    published_at: Optional[datetime] = None


class BaseCrawler(ABC):
    def __init__(self, source_name: str, request_delay: float = 2.0, timeout: int = 15):
        self.source_name = source_name
        self.request_delay = request_delay
        self.timeout = timeout
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })
        return session

    def get(self, url: str) -> Optional[BeautifulSoup]:
        """HTTP GET 요청 + BeautifulSoup 반환. 실패 시 None."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            logger.warning(f"[{self.source_name}] GET 실패: {url} - {e}")
            return None

    @abstractmethod
    def fetch_list(self) -> list[dict]:
        """기사 목록 수집. 각 항목은 url, title, published_at 포함."""
        pass

    @abstractmethod
    def fetch_content(self, url: str) -> Optional[str]:
        """기사 본문 텍스트 수집."""
        pass

    def run(self) -> list[RawArticle]:
        """크롤러 실행. 목록 수집 → 본문 수집 → RawArticle 리스트 반환."""
        logger.info(f"[{self.source_name}] 크롤링 시작")
        items = self.fetch_list()
        articles = []

        for item in items:
            try:
                content = self.fetch_content(item["url"])
                if not content:
                    continue

                articles.append(RawArticle(
                    url=item["url"],
                    title=item.get("title", ""),
                    content=content,
                    source=self.source_name,
                    published_at=item.get("published_at"),
                ))
                time.sleep(self.request_delay)

            except Exception as e:
                logger.warning(f"[{self.source_name}] 기사 수집 실패: {item.get('url')} - {e}")
                continue

        logger.info(f"[{self.source_name}] 완료: {len(articles)}건 수집")
        return articles
