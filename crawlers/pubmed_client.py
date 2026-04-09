import os
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def search_ids(query: str, max_results: int, api_key: Optional[str]) -> list[str]:
    """검색어로 PubMed ID 목록 반환"""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": "pub+date",
        "retmode": "json",
    }
    if api_key:
        params["api_key"] = api_key

    try:
        resp = requests.get(PUBMED_ESEARCH, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()["esearchresult"]["idlist"]
    except Exception as e:
        logger.warning(f"[pubmed] 검색 실패: {query} - {e}")
        return []


def fetch_abstracts(pmids: list[str], api_key: Optional[str]) -> list[dict]:
    """PubMed ID 목록으로 초록 데이터 반환"""
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    if api_key:
        params["api_key"] = api_key

    try:
        from bs4 import BeautifulSoup
        resp = requests.get(PUBMED_EFETCH, params=params, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, features="xml")

        articles = []
        for article in soup.find_all("PubmedArticle"):
            pmid = article.find("PMID")
            title = article.find("ArticleTitle")
            # AbstractText가 여러 개인 경우 전부 이어붙임
            abstract_tags = article.find_all("AbstractText")
            pub_date = article.find("PubDate")

            if not (pmid and title and abstract_tags):
                continue

            abstract_text = " ".join(t.get_text(strip=True) for t in abstract_tags)

            # 발행일 파싱
            published_at = None
            if pub_date:
                year = pub_date.find("Year")
                month = pub_date.find("Month")
                try:
                    year_int = int(year.text) if year else 2000
                    month_int = _month_str_to_int(month.text if month else "1")
                    published_at = datetime(year_int, month_int, 1, tzinfo=timezone.utc)
                except Exception:
                    pass

            articles.append({
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid.text}/",
                "title": title.get_text(strip=True),
                "content": abstract_text,
                "published_at": published_at,
            })

        return articles

    except Exception as e:
        logger.warning(f"[pubmed] 초록 수집 실패: {e}")
        return []


def _month_str_to_int(month: str) -> int:
    months = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
    }
    try:
        return int(month)
    except ValueError:
        return months.get(month[:3], 1)


def run() -> list[dict]:
    """PubMed 크롤러 실행. RawArticle 형태의 dict 리스트 반환."""
    config = load_config()
    api_config = next((s for s in config["sources"]["api"] if s["name"] == "pubmed"), None)

    if not api_config or not api_config.get("enabled"):
        return []

    api_key = os.environ.get("PUBMED_API_KEY") or None
    max_results = api_config.get("max_results_per_query", 10)
    search_terms = api_config.get("search_terms", [])

    all_articles = []
    seen_urls = set()

    for term in search_terms:
        logger.info(f"[pubmed] 검색: {term}")
        pmids = search_ids(term, max_results, api_key)
        articles = fetch_abstracts(pmids, api_key)

        for article in articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                article["source"] = "pubmed"
                all_articles.append(article)

        time.sleep(0.5)  # PubMed API 요청 간격

    logger.info(f"[pubmed] 완료: {len(all_articles)}건 수집")
    return all_articles
