"""
2단계 관련성 검증: Hugging Face Zero-shot Classification API
1단계(키워드 분류) 통과한 기사에 대해 시니어 관련성 판단.
"""

import logging
import os
import requests

logger = logging.getLogger(__name__)

HF_API_URL = "https://api-inference.huggingface.co/models/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

# 판단 기준 점수: 이 이상이면 시니어 관련 있다고 판단
RELEVANCE_THRESHOLD = 0.6


def is_senior_relevant(topic: str, title: str, content: str) -> bool:
    """
    HF Zero-shot API로 시니어 관련성을 판단합니다.

    2가지를 순서대로 검증:
    1. 기사의 메인 주제가 해당 토픽인가?
    2. 중장년·시니어에게도 도움이 되는 정보인가?

    API 키 없거나 호출 실패 시 True 반환 (보수적 허용).
    """
    hf_token = os.getenv("HF_API_TOKEN")

    # HF 토큰 없으면 스킵 (키워드 필터만으로 운영)
    if not hf_token:
        return True

    # 입력 텍스트: 제목 + 본문 앞 300자
    text = f"{title}. {content[:300]}"

    headers = {"Authorization": f"Bearer {hf_token}"}

    # ── 1차: 메인 주제 검증 ──
    main_topic_result = _classify(
        text=text,
        candidate_labels=[
            f"{topic}이 핵심 주제인 글",
            f"{topic}이 부수적으로 언급된 글",
        ],
        headers=headers,
    )
    if main_topic_result is None:
        return True  # API 실패 → 허용

    top_label = main_topic_result["labels"][0]
    top_score = main_topic_result["scores"][0]

    # 메인 주제가 아닌 것으로 판단되면 탈락
    if "부수적" in top_label and top_score >= RELEVANCE_THRESHOLD:
        logger.info(f"[relevance] 1차 탈락 (부수적 언급): {title[:40]}")
        return False

    # ── 2차: 시니어 유용성 검증 ──
    senior_result = _classify(
        text=text,
        candidate_labels=[
            "중장년·시니어에게 유용한 건강 정보",
            "특정 연령층(소아·임산부·청년)에 국한된 정보",
        ],
        headers=headers,
    )
    if senior_result is None:
        return True  # API 실패 → 허용

    top_label = senior_result["labels"][0]
    top_score = senior_result["scores"][0]

    if "소아" in top_label or "임산부" in top_label or "청년" in top_label:
        if top_score >= RELEVANCE_THRESHOLD:
            logger.info(f"[relevance] 2차 탈락 (비시니어 한정): {title[:40]}")
            return False

    return True


def _classify(text: str, candidate_labels: list[str], headers: dict) -> dict | None:
    """
    HF Inference API 호출. 실패 시 None 반환.
    """
    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json={
                "inputs": text,
                "parameters": {"candidate_labels": candidate_labels},
            },
            timeout=10,
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 503:
            # 모델 로딩 중 (콜드스타트) → 허용
            logger.warning("[relevance] HF 모델 로딩 중, 이번 기사는 허용 처리")
            return None
        else:
            logger.warning(f"[relevance] HF API 오류 {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"[relevance] HF API 호출 실패: {e}")
        return None
