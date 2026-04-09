import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from crawlers.rss_crawler import RSSCrawler
from crawlers.html_crawler import KDCACrawler, NHISCrawler, SNUHCrawler
from crawlers.international_crawler import WHOCrawler
from crawlers.pubmed_client import run as pubmed_run
from crawlers.base_crawler import RawArticle
from filters.keyword_filter import classify, make_title_hash, quality_score
from storage.supabase_client import save_article, is_duplicate, Article

load_dotenv()

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def process_articles(raw_articles: list, min_score: float) -> tuple[int, int]:
    """
    수집된 기사 필터링 후 Supabase에 저장.
    반환: (저장된 수, 건너뛴 수)
    """
    saved = 0
    skipped = 0

    for raw in raw_articles:
        # RawArticle 또는 dict 모두 처리
        if isinstance(raw, dict):
            url = raw.get("url", "")
            title = raw.get("title", "")
            content = raw.get("content", "")
            source = raw.get("source", "")
            published_at = raw.get("published_at")
        else:
            url = raw.url
            title = raw.title
            content = raw.content
            source = raw.source
            published_at = raw.published_at

        if not url or not title:
            skipped += 1
            continue

        # 중복 확인
        title_hash = make_title_hash(title)
        if is_duplicate(url, title_hash):
            skipped += 1
            continue

        # 키워드 분류
        topic, keywords, keyword_score = classify(title, content)
        if not topic:
            skipped += 1
            continue

        # 품질 점수
        score = quality_score(source, content, published_at, keyword_score)
        if score < min_score:
            skipped += 1
            continue

        # Supabase 저장
        article = Article(
            url=url,
            title=title,
            content=content,
            source=source,
            topic_category=topic,
            keywords=keywords,
            quality_score=score,
            published_at=published_at,
            title_hash=title_hash,
        )
        if save_article(article):
            saved += 1
        else:
            skipped += 1

    return saved, skipped


def main():
    config = load_config()
    min_score = config["quality"]["min_score"]
    rss_sources = config["sources"]["rss"]

    total_saved = 0
    total_skipped = 0

    # 1. RSS 크롤러 (국내 + 해외 통합)
    rss_crawler_map = {
        "who": WHOCrawler,
    }

    for source in rss_sources:
        if not source.get("enabled"):
            continue

        name = source["name"]
        url = source.get("url", "")

        # 해외 기관은 전용 크롤러 사용
        if name in rss_crawler_map:
            crawler = rss_crawler_map[name]()
        else:
            crawler = RSSCrawler(source_name=name, feed_url=url)

        raw_articles = crawler.run()
        saved, skipped = process_articles(raw_articles, min_score)
        total_saved += saved
        total_skipped += skipped
        logger.info(f"[{name}] 저장: {saved}건 / 건너뜀: {skipped}건")

    # 2. HTML 크롤러 (국내 공공기관)
    html_crawlers = [KDCACrawler(), NHISCrawler(), SNUHCrawler()]

    html_enabled = {s["name"]: s.get("enabled", True) for s in config["sources"]["html"]}

    for crawler in html_crawlers:
        if not html_enabled.get(crawler.source_name, True):
            continue

        raw_articles = crawler.run()
        saved, skipped = process_articles(raw_articles, min_score)
        total_saved += saved
        total_skipped += skipped
        logger.info(f"[{crawler.source_name}] 저장: {saved}건 / 건너뜀: {skipped}건")

    # 3. PubMed API
    pubmed_enabled = any(
        s.get("enabled") for s in config["sources"]["api"] if s["name"] == "pubmed"
    )
    if pubmed_enabled:
        raw_articles = pubmed_run()
        saved, skipped = process_articles(raw_articles, min_score)
        total_saved += saved
        total_skipped += skipped
        logger.info(f"[pubmed] 저장: {saved}건 / 건너뜀: {skipped}건")

    logger.info(f"=== 크롤링 완료: 총 저장 {total_saved}건 / 건너뜀 {total_skipped}건 ===")


if __name__ == "__main__":
    main()
