from storage.supabase_client import get_articles_by_topic


def retrieve(topic: str, days: int = 60, limit: int = 15) -> list[dict]:
    """
    Supabase에서 주제별 기사를 품질 점수 높은 순으로 조회.

    반환 형태:
        [
            {
                "title": "...",
                "content": "...",
                "source": "kdca",
                "quality_score": 0.91,
                "published_at": "2026-04-09T..."
            },
            ...
        ]
    """
    articles = get_articles_by_topic(topic, days=days, limit=limit)

    if not articles:
        print(f"[retriever] '{topic}' 관련 기사가 없습니다. (최근 {days}일 기준)")
        print(f"  → python crawl.py 를 먼저 실행해 정보를 수집하세요.")

    return articles
