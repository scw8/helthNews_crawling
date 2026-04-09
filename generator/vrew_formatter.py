import os
from datetime import date


OUTPUT_DIR = "output/scripts"


def save(topic: str, script: str) -> str:
    """
    생성된 스크립트를 Vrew 호환 텍스트 파일로 저장합니다.

    반환값: 저장된 파일 경로
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    filename = f"{today}_{topic}.txt"
    filepath = os.path.join(OUTPUT_DIR, filename)

    header = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
주제: {topic}
생성일: {today}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + script)

    return filepath
