import os
import logging

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


def write(prompt: str) -> str:
    """
    Claude API를 호출하여 스크립트를 생성합니다.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key)

    logger.info(f"[script_writer] Claude API 호출 중 (model={MODEL})")

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    script = message.content[0].text
    logger.info(f"[script_writer] 스크립트 생성 완료 ({len(script)}자)")
    return script
