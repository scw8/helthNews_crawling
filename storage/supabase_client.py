import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


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
    """
    기사 저장. URL 중복이면 저장하지 않고 False 반환.
    """
    client = get_client()
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
        client.table("articles").insert(data).execute()
        return True
    except Exception:
        # URL unique 제약 위반 = 중복 기사
        return False


def is_duplicate(url: str, title_hash: str) -> bool:
    """
    URL 또는 제목 해시가 이미 DB에 있으면 True.
    """
    client = get_client()

    # URL 체크
    result = client.table("articles").select("id").eq("url", url).execute()
    if result.data:
        return True

    # 제목 해시 체크
    result = client.table("articles").select("id").eq("title_hash", title_hash).execute()
    if result.data:
        return True

    return False


def get_articles_by_topic(topic: str, days: int = 60, limit: int = 15) -> list[dict]:
    """
    스크립트 생성 시 사용. 주제별 기사를 품질 점수 높은 순으로 조회.
    """
    from datetime import timedelta
    client = get_client()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    result = (
        client.table("articles")
        .select("id, title, content, source, keywords, quality_score, published_at")
        .eq("topic_category", topic)
        .gte("crawled_at", since)
        .order("quality_score", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def save_script(topic: str, script_content: str, source_ids: list[int], file_path: str):
    """
    생성된 스크립트 이력 저장.
    """
    client = get_client()
    client.table("generated_scripts").insert({
        "topic": topic,
        "script_content": script_content,
        "source_ids": source_ids,
        "file_path": file_path,
    }).execute()
