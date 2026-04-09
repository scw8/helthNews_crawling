SOURCE_LABELS = {
    "kdca": "질병관리청",
    "nhis": "국민건강보험공단",
    "snuh": "서울대학교병원",
    "pubmed": "국제 의학 논문 (PubMed)",
    "who": "세계보건기구 (WHO)",
    "sciencedaily": "ScienceDaily",
    "health_chosun": "헬스조선",
    "mdtoday": "메디컬투데이",
    "kormedi": "코메디닷컴",
}

SCRIPT_STRUCTURE = """
[0:00~0:45]   훅 - 시청자가 끝까지 볼 이유를 첫 문장에 담기. 공포 또는 호기심 자극.
[0:45~2:30]   공감 & 문제 제기 - 시청자의 실제 경험처럼 시작. "이런 적 있으시죠?"
[2:30~5:00]   원인 설명 - 어려운 의학 개념을 비유로 설명. 인포그래픽 삽입 언급 가능.
[5:00~9:00]   핵심 정보 - 3~5가지로 번호 매기기. 중간에 "잠깐, 퀴즈 하나 드릴게요" 삽입.
[9:00~11:30]  실생활 적용법 - 오늘부터 바로 할 수 있는 것. 구체적 숫자 사용.
[11:30~13:30] 주의사항 & 오해 바로잡기 - "많은 분들이 잘못 알고 계신 게 있는데요"
[13:30~14:30] 요약 - 핵심 3줄 반복 (시니어는 반복을 좋아함)
[14:30~15:00] 아웃트로 & CTA - 좋아요/구독 요청 + 다음 영상 예고
"""

LANGUAGE_GUIDE = """
- "어르신" 호칭 금지 → "여러분", "선생님" 사용
- 문장은 짧고 천천히. 핵심은 2회 이상 반복
- 의학 용어는 반드시 쉬운 말로 재설명
- 구어체로 작성 (Vrew AI 음성으로 읽힘)
- 숫자는 구체적으로: "적당히" → "하루 30분"
- 영상 자막 크기 고려: 한 자막당 최대 2줄
"""


def build(topic: str, articles: list[dict]) -> str:
    """
    수집된 기사들을 Claude 프롬프트로 조립.
    """
    # 참고 자료 섹션 구성
    references = ""
    for i, article in enumerate(articles, 1):
        source_label = SOURCE_LABELS.get(article.get("source", ""), article.get("source", ""))
        title = article.get("title", "")
        content = article.get("content", "")
        # 본문이 너무 길면 앞 1000자만 사용
        content_preview = content[:1000] + "..." if len(content) > 1000 else content

        references += f"""
[참고 자료 {i}]
출처: {source_label}
제목: {title}
내용: {content_preview}
"""

    prompt = f"""당신은 55~70세 시니어를 대상으로 한 건강 유튜브 채널의 전문 작가입니다.

## 오늘의 주제
{topic}

## 언어 및 톤 가이드
{LANGUAGE_GUIDE}

## 영상 구성 (총 15분 기준)
{SCRIPT_STRUCTURE}

## 참고 자료 ({len(articles)}건)
아래 공신력 있는 자료를 바탕으로 스크립트를 작성하세요.
내용을 그대로 옮기지 말고, 시니어가 이해하기 쉽게 재구성하세요.
{references}

## 작성 지침
1. 위 구성 형식을 반드시 따르고 각 섹션 앞에 [훅 - 0:00] 형태로 타임코드를 표시하세요.
2. 스크립트 맨 끝에 참고한 출처 목록을 추가하세요.
3. 마지막 줄에 반드시 면책 고지를 포함하세요:
   "본 영상의 내용은 일반적인 건강 정보이며, 개인의 건강 상태에 따라 다를 수 있습니다. 구체적인 치료나 복약은 반드시 담당 의사와 상담하세요."

이제 스크립트를 작성해주세요.
"""
    return prompt
