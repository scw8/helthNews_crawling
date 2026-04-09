"""
Part 2: 유튜브 스크립트 생성기

사용법:
    python generate.py --topic 치매
    python generate.py --topic 당뇨 --days 30
    python generate.py --topic 고혈압 --limit 10
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

from generator.retriever import retrieve
from generator.prompt_builder import build
from generator.script_writer import write
from generator.vrew_formatter import save


def main():
    parser = argparse.ArgumentParser(description="건강 유튜브 스크립트 생성기")
    parser.add_argument("--topic", required=True, help="스크립트 주제 (예: 치매, 당뇨, 고혈압)")
    parser.add_argument("--days", type=int, default=60, help="최근 N일 이내 기사 사용 (기본: 60)")
    parser.add_argument("--limit", type=int, default=15, help="최대 참고 기사 수 (기본: 15)")
    args = parser.parse_args()

    topic = args.topic
    print(f"\n[1/4] '{topic}' 관련 기사 조회 중 (최근 {args.days}일, 최대 {args.limit}건)...")

    articles = retrieve(topic, days=args.days, limit=args.limit)

    if not articles:
        print(f"\n기사가 없어 스크립트를 생성할 수 없습니다.")
        print(f"먼저 python crawl.py 를 실행하여 기사를 수집하세요.")
        sys.exit(1)

    print(f"  → {len(articles)}건 조회 완료")

    print(f"\n[2/4] Claude 프롬프트 구성 중...")
    prompt = build(topic, articles)
    print(f"  → 프롬프트 구성 완료 ({len(prompt)}자)")

    print(f"\n[3/4] Claude API로 스크립트 생성 중...")
    script = write(prompt)
    print(f"  → 스크립트 생성 완료 ({len(script)}자)")

    print(f"\n[4/4] 파일 저장 중...")
    filepath = save(topic, script)
    print(f"  → 저장 완료: {filepath}")

    print(f"\n완료! Vrew에 {filepath} 파일을 붙여넣으세요.\n")


if __name__ == "__main__":
    main()
