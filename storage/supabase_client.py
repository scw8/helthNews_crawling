import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# 싱글톤 — 프로세스당 한 번만 생성
_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


@dataclass
class Article:
    url: str
    title: str
    content: str
    source: str
    topic_category: str
    keywords: list[str]
    quality_score: float
    published_at: Optional[datetime] = None
    title_hash: Optional[str] = None


def save_article(article: Article) -> bool:
    """기사 저장. URL 중복이면 저장하지 않고 False 반환."""
    data = {
        "url": article.url,
        "title": article.title,
        "content": article.content,
        "source": article.source,
        "topic_category": article.topic_category,
        "keywords": article.keywords,
        "quality_score": article.quality_score,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "title_hash": article.title_hash,
    }
    try:
        get_client().table("articles").insert(data).execute()
        return True
    except Exception:
        return False


def is_duplicate(url: str, title_hash: str) -> bool:
    """URL 또는 제목 해시가 이미 DB에 있으면 True."""
    client = get_client()
    if client.table("articles").select("id").eq("url", url).execute().data:
        return True
    if client.table("articles").select("id").eq("title_hash", title_hash).execute().data:
        return True
    return False


def get_articles_by_topic(
    topic: str,
    days: int = 60,
    limit: int = 15,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """스크립트 생성용. 주제별 기사를 품질 점수 높은 순으로 조회."""
    query = (
        get_client().table("articles")
        .select("id, title, content, source, keywords, quality_score, published_at")
        .eq("topic_category", topic)
        .order("quality_score", desc=True)
        .limit(limit)
    )
    if start_date and end_date:
        query = query.gte("published_at", start_date).lte("published_at", end_date)
    else:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = query.gte("crawled_at", since)
    return query.execute().data


def get_articles(
    topic: Optional[str] = None,
    source: Optional[str] = None,
    sources: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """기사/논문 리딩 페이지용. 필터 조건에 맞는 기사 목록 조회."""
    query = (
        get_client().table("articles")
        .select("id, title, content, source, topic_category, published_at, quality_score, url")
        .order("published_at", desc=True)
    )
    if topic:
        query = query.eq("topic_category", topic)
    if sources:
        query = query.in_("source", sources)
    elif source:
        query = query.eq("source", source)
    if start_date:
        query = query.gte("published_at", start_date)
    if end_date:
        query = query.lte("published_at", end_date)
    query = query.range(offset, offset + limit - 1)
    return query.execute().data
