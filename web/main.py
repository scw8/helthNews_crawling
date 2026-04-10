import json
import logging
import os

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="건강 유튜브 스크립트 생성기")
templates = Jinja2Templates(directory="web/templates")

TOPICS = [
    "당뇨", "고혈압", "고지혈증", "관절", "치매", "영양제", "면역력", "저속노화",
    "치아", "불면증", "두통", "피부미용", "국가정책",
]

SOURCE_LABELS = {
    "kdca": "질병관리청",
    "nhis": "국민건강보험공단",
    "snuh": "서울대학교병원",
    "pubmed": "PubMed (국제 논문)",
    "who": "WHO",
    "sciencedaily": "ScienceDaily",
    "health_chosun": "헬스조선",
    "mdtoday": "메디컬투데이",
    "kormedi": "코메디닷컴",
}

# pubmed / sciencedaily = 논문 계열
PAPER_SOURCES = {"pubmed", "sciencedaily"}

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "topics": TOPICS,
        "source_labels": SOURCE_LABELS,
    })


@app.get("/generate")
async def generate(
    topic: str,
    days: int = 60,
    limit: int = 15,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    from generator.prompt_builder import build

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        async def error_stream():
            yield f"data: {json.dumps({'error': 'ANTHROPIC_API_KEY가 설정되지 않았습니다.'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # 날짜 범위 or days 방식으로 기사 조회
    from storage.supabase_client import get_articles_by_topic
    articles = get_articles_by_topic(
        topic, days=days, limit=limit,
        start_date=start_date, end_date=end_date,
    )

    if not articles:
        async def no_articles_stream():
            yield f"data: {json.dumps({'error': f'{topic} 관련 기사가 없습니다. 크롤러를 먼저 실행하세요.'})}\n\n"
        return StreamingResponse(no_articles_stream(), media_type="text/event-stream")

    prompt = build(topic, articles)
    article_count = len(articles)

    async def stream():
        yield f"data: {json.dumps({'meta': {'topic': topic, 'article_count': article_count}})}\n\n"

        client = anthropic.AsyncAnthropic(api_key=api_key)
        full_text = ""

        try:
            async with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            ) as s:
                async for text in s.text_stream:
                    full_text += text
                    yield f"data: {json.dumps({'text': text})}\n\n"

            yield f"data: {json.dumps({'done': True, 'full_text': full_text})}\n\n"

        except Exception as e:
            logger.error(f"Claude API 오류: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/articles")
async def get_articles_api(
    topic: Optional[str] = None,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    type: Optional[str] = None,   # "paper" | "article"
    limit: int = 50,
    offset: int = 0,
):
    from storage.supabase_client import get_articles

    # type 필터 → source 목록으로 변환
    source_filter = None
    if type == "paper":
        source_filter = list(PAPER_SOURCES)
    elif type == "article":
        source_filter = [s for s in SOURCE_LABELS if s not in PAPER_SOURCES]

    rows = get_articles(
        topic=topic,
        sources=source_filter if source_filter else None,
        source=source if not source_filter else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    # source 라벨 변환 + 논문 여부 플래그
    for row in rows:
        src = row.get("source", "")
        row["source_label"] = SOURCE_LABELS.get(src, src)
        row["is_paper"] = src in PAPER_SOURCES

    # type 필터가 있으면 Python 단에서 추가 필터링
    if type == "paper":
        rows = [r for r in rows if r["is_paper"]]
    elif type == "article":
        rows = [r for r in rows if not r["is_paper"]]

    return JSONResponse({"items": rows, "count": len(rows)})
