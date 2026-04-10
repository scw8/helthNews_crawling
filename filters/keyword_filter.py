import hashlib
import yaml
from pathlib import Path


def load_keywords() -> dict:
    config_path = Path(__file__).parent.parent / "config.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["keywords"]


def classify(title: str, content: str) -> tuple[str, list[str], float]:
    """
    기사 제목 + 본문을 분석해서 주제 분류 및 관련도 점수 반환.

    1단계: 제목에 primary 키워드가 있으면 메인 주제로 확정 (높은 신뢰도)
    2단계: 제목에 없으면 본문에서 primary 2회 이상 등장해야 분류

    반환값:
        topic_category: 주제 (당뇨, 고혈압 등) - 해당 없으면 빈 문자열
        matched_keywords: 매칭된 키워드 목록
        score: 관련도 점수 0.0 ~ 1.0
    """
    keywords = load_keywords()

    best_topic = ""
    best_score = 0.0
    best_keywords = []

    for topic, data in keywords.items():
        matched = []
        title_primary_hits = 0
        content_primary_hits = 0
        secondary_hits = 0

        for kw in data["primary"]:
            if kw in title:
                title_primary_hits += 1
                matched.append(kw)
            elif kw in content:
                content_primary_hits += 1
                matched.append(kw)

        for kw in data["secondary"]:
            if kw in title or kw in content:
                secondary_hits += 1
                matched.append(kw)

        # 제목에 primary 키워드 있으면 메인 주제로 확정
        if title_primary_hits >= 1:
            score = title_primary_hits * 4.0 + secondary_hits * 1.0
        # 제목에 없으면 본문에서 primary 2회 이상이어야 분류
        elif content_primary_hits >= 2:
            score = content_primary_hits * 1.5 + secondary_hits * 1.0
        else:
            continue  # 기준 미달 → 이 토픽 스킵

        if score > best_score:
            best_score = score
            best_topic = topic
            best_keywords = matched

    if best_score == 0.0:
        return "", [], 0.0

    normalized = min(best_score / 10.0, 1.0)
    return best_topic, best_keywords, normalized


def make_title_hash(title: str) -> str:
    """
    제목 앞 20글자로 해시 생성 (유사 제목 중복 감지용).
    """
    return hashlib.md5(title[:20].encode("utf-8")).hexdigest()


def quality_score(source: str, content: str, published_at, keyword_score: float) -> float:
    """
    최종 품질 점수 계산 (0.0 ~ 1.0).
    소스 신뢰도 + 콘텐츠 길이 + 최신성 + 키워드 관련도 합산.
    """
    source_weights = {
        "kdca": 1.0,
        "nhis": 0.95,
        "hira": 0.95,
        "pubmed": 0.95,
        "snuh": 0.88,
        "health_chosun": 0.70,
        "mdtoday": 0.70,
        "kormedi": 0.65,
    }
    score = source_weights.get(source, 0.5) * 0.4

    # 콘텐츠 길이
    content_len = len(content) if content else 0
    if content_len > 1000:
        score += 0.2
    elif content_len > 300:
        score += 0.1

    # 최신성
    if published_at:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        age = now - published_at
        if age.days < 7:
            score += 0.2
        elif age.days < 30:
            score += 0.1

    # 키워드 관련도
    score += keyword_score * 0.2

    return min(score, 1.0)
