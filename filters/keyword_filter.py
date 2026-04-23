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

    가중치 구성:
      출처 신뢰도  × 0.35
      최신성       × 0.30  (지수 감쇠, 반감기 45일)
      내용 밀도    최대 0.20  (수치·연구 언급·길이 적합성)
      키워드 관련도 × 0.15
    """
    import math
    import re
    from datetime import datetime, timezone

    # ── 1. 출처 신뢰도 ──────────────────────────────────────
    source_weights = {
        "kdca":          1.00,  # 질병관리청
        "mohw":          0.95,  # 보건복지부
        "nhis":          0.95,  # 국민건강보험공단
        "hira":          0.95,  # 건강보험심사평가원
        "pubmed":        0.93,  # 국제 동료 심사 논문
        "snuh":          0.88,  # 서울대학교병원
        "who":           0.85,  # 세계보건기구
        "sciencedaily":  0.75,  # 논문 요약 미디어
        "health_chosun": 0.70,
        "mdtoday":       0.70,
        "kormedi":       0.65,
        "bokjitimes":    0.55,  # 복지 정책 미디어
    }
    source_score = source_weights.get(source, 0.50) * 0.35

    # ── 2. 최신성 — 지수 감쇠 (반감기 45일) ────────────────
    # published_at이 None인 경우 소스 특성에 따라 폴백 점수 부여
    #   뉴스/보도자료 소스: 크롤링 = 현재 존재 증명 → 오늘 기준 75% 점수
    #   정적 콘텐츠 소스(SNUH 건강백과 등): 발행일 개념 없음 → 중립 고정값
    _NEWS_SOURCES = {
        "kdca", "mohw", "nhis", "hira",
        "health_chosun", "mdtoday", "kormedi", "bokjitimes",
        "who", "sciencedaily",
    }
    _STATIC_SOURCES = {"snuh"}

    recency_score = 0.0
    if published_at:
        now = datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        age_days = max((now - published_at).days, 0)
        recency_score = 0.30 * math.exp(-age_days / 45)
    elif source in _NEWS_SOURCES:
        recency_score = 0.30 * 0.75   # ≈ 0.225 (오늘 기준, 날짜 불확실 25% 패널티)
    elif source in _STATIC_SOURCES:
        recency_score = 0.08           # 중립값 (~60일 등가): 오래됐을 수 있지만 가치 있음
    else:
        recency_score = 0.10           # 미분류 소스 기본값

    # ── 3. 내용 밀도 ─────────────────────────────────────────
    text = content or ""
    density_score = 0.0

    # 구체적 수치 포함 여부 (mg, %, mmHg, 만명, 회 등)
    if len(re.findall(r'\d+\s*[%㎎mg㎍ug만명회기개월주년]', text)) >= 2:
        density_score += 0.08

    # 연구·근거 언급
    evidence_keywords = ["연구", "임상", "권고", "가이드라인", "논문", "학회", "분석", "조사"]
    if any(kw in text for kw in evidence_keywords):
        density_score += 0.07

    # 적정 길이 (너무 짧으면 정보 부족, 너무 길면 광고·나열성)
    content_len = len(text)
    if 300 < content_len < 5000:
        density_score += 0.05

    # ── 4. 키워드 관련도 ─────────────────────────────────────
    keyword_contribution = keyword_score * 0.15

    return min(source_score + recency_score + density_score + keyword_contribution, 1.0)
