"""
TF-IDF 기반 유사 기사 중복 제거.

같은 연구·뉴스를 여러 매체가 보도한 경우, 그 중 quality_score가 가장 높은
기사 1건만 남기고 나머지를 제거한다.

사용 시점: DB에서 기사를 조회한 뒤, Claude에게 전달하기 직전.
"""

import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# 이 이상이면 동일 기사로 판단하고 중복 제거
SIMILARITY_THRESHOLD = 0.75


def deduplicate(articles: list[dict]) -> list[dict]:
    """
    유사도 기반으로 중복 기사를 제거하고 대표 기사만 반환.

    알고리즘:
    1. quality_score 내림차순 정렬
    2. 높은 점수 기사부터 순서대로 선택
    3. 이미 선택된 기사와 유사도 THRESHOLD 이상이면 스킵

    반환값은 quality_score 내림차순 정렬된 리스트.
    """
    if len(articles) <= 1:
        return articles

    # quality_score 내림차순 정렬 (없으면 0 처리)
    sorted_articles = sorted(articles, key=lambda a: a.get("quality_score", 0), reverse=True)

    texts = [
        (a.get("title", "") + " " + a.get("content", "")[:500])
        for a in sorted_articles
    ]

    try:
        vectorizer = TfidfVectorizer(max_features=500, sublinear_tf=True)
        tfidf_matrix = vectorizer.fit_transform(texts)
        sim_matrix = cosine_similarity(tfidf_matrix)
    except Exception as e:
        logger.warning(f"[deduplicator] TF-IDF 계산 실패, 원본 반환: {e}")
        return sorted_articles

    selected_indices: list[int] = []
    skipped: int = 0

    for i in range(len(sorted_articles)):
        is_duplicate = any(
            sim_matrix[i][j] >= SIMILARITY_THRESHOLD
            for j in selected_indices
        )
        if is_duplicate:
            skipped += 1
        else:
            selected_indices.append(i)

    if skipped:
        logger.info(f"[deduplicator] 유사 기사 {skipped}건 제거 → {len(selected_indices)}건 유지")

    return [sorted_articles[i] for i in selected_indices]
