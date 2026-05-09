import logging
import sys
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

from crawlers.base_crawler import BaseCrawler, RawArticle
from crawlers.rss_crawler import RSSCrawler
from crawlers.html_crawler import KDCACrawler, NHISCrawler, SNUHCrawler, MOHWCrawler
from crawlers.international_crawler import WHOCrawler
from crawlers.pubmed_client import run as pubmed_run
from filters.keyword_filter import classify, make_title_hash, quality_score
from filters.relevance_checker import is_senior_relevant
from storage.supabase_client import save_article, is_duplicate, Article

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

CRAWLER_REGISTRY: dict[str, type[BaseCrawler]] = {
    "kdca": KDCACrawler,
    "who": WHOCrawler,
    "nhis": NHISCrawler,
    "snuh": SNUHCrawler,
    "mohw": MOHWCrawler,
}


@lru_cache(maxsize=1)
def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def process_articles(raw_articles: list[RawArticle], min_score: float) -> tuple[int, int]:
    """수집된 기사 필터링 후 Supabase에 저장. 반환: (저장된 수, 건너뛴 수)"""
    saved = skipped = 0

    for raw in raw_articles:
        if not raw.url or not raw.title:
            skipped += 1
            continue

        title_hash = make_title_hash(raw.title)
        if is_duplicate(raw.url, title_hash):
            skipped += 1
            continue

        topic, keywords, keyword_score_val = classify(raw.title, raw.content)
        if not topic:
            skipped += 1
            continue

        if not is_senior_relevant(topic, raw.title, raw.content):
            skipped += 1
            continue

        score = quality_score(raw.source, raw.content, raw.published_at, keyword_score_val)
        if score < min_score:
            skipped += 1
            continue

        article = Article(
            url=raw.url,
            title=raw.title,
            content=raw.content,
            source=raw.source,
            topic_category=topic,
            keywords=keywords,
            quality_score=score,
            published_at=raw.published_at,
            title_hash=title_hash,
        )
        if save_article(article):
            saved += 1
        else:
            skipped += 1

    return saved, skipped


def run_source(source: dict, min_score: float) -> tuple[int, int]:
    """단일 소스를 크롤링하고 결과를 반환."""
    name = source["name"]
    crawler_cls = CRAWLER_REGISTRY.get(name)
    crawler = crawler_cls() if crawler_cls else RSSCrawler(source_name=name, feed_url=source.get("url", ""))
    raw_articles = crawler.run()
    saved, skipped = process_articles(raw_articles, min_score)
    logger.info(f"[{name}] 저장: {saved}건 / 건너뜀: {skipped}건")
    return saved, skipped


def main():
    config = load_config()
    min_score = config["quality"]["min_score"]
    total_saved = total_skipped = 0

    for source in config["sources"]["rss"] + config["sources"]["html"]:
        if not source.get("enabled"):
            continue
        saved, skipped = run_source(source, min_score)
        total_saved += saved
        total_skipped += skipped

    pubmed_enabled = any(
        s.get("enabled") for s in config["sources"]["api"] if s["name"] == "pubmed"
    )
    if pubmed_enabled:
        saved, skipped = process_articles(pubmed_run(), min_score)
        total_saved += saved
        total_skipped += skipped
        logger.info(f"[pubmed] 저장: {saved}건 / 건너뜀: {skipped}건")

    logger.info(f"=== 크롤링 완료: 총 저장 {total_saved}건 / 건너뜀 {total_skipped}건 ===")


if __name__ == "__main__":
    main()
