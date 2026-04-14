import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from crawlers.base_crawler import BaseCrawler
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

# 소스명 → 전용 크롤러 클래스 등록
# 새 크롤러 추가 시 여기에 한 줄만 추가하면 됨
CRAWLER_REGISTRY: dict[str, type[BaseCrawler]] = {
    "kdca": KDCACrawler,
    "who": WHOCrawler,
    "nhis": NHISCrawler,
    "snuh": SNUHCrawler,
    "mohw": MOHWCrawler,
}


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def process_articles(raw_articles: list, min_score: float) -> tuple[int, int]:
    """수집된 기사 필터링 후 Supabase에 저장. 반환: (저장된 수, 건너뛴 수)"""
    saved = 0
    skipped = 0

    for raw in raw_articles:
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

        title_hash = make_title_hash(title)
        if is_duplicate(url, title_hash):
            skipped += 1
            continue

        # 1단계: 키워드 분류 (제목 중심)
        topic, keywords, keyword_score = classify(title, content)
        if not topic:
            skipped += 1
            continue

        # 2단계: HF Zero-shot으로 시니어 관련성 검증
        if not is_senior_relevant(topic, title, content):
            skipped += 1
            continue

        score = quality_score(source, content, published_at, keyword_score)
        if score < min_score:
            skipped += 1
            continue

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

    total_saved = 0
    total_skipped = 0

    # RSS + HTML 소스 통합 처리
    all_sources = config["sources"]["rss"] + config["sources"]["html"]
    for source in all_sources:
        if not source.get("enabled"):
            continue
        saved, skipped = run_source(source, min_score)
        total_saved += saved
        total_skipped += skipped

    # PubMed API (별도 클라이언트)
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
