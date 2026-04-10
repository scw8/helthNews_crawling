import json
import logging
import os

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="건강 유튜브 스크립트 생성기")
templates = Jinja2Templates(directory="web/templates")

TOPICS = ["당뇨", "고혈압", "고지혈증", "관절", "치매", "영양제", "면역력", "저속노화",
          "치아", "불면증", "두통", "피부미용", "국가정책"]
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "topics": TOPICS})


@app.get("/generate")
async def generate(topic: str, days: int = 60, limit: int = 15):
    """
    Server-Sent Events로 스크립트를 스트리밍합니다.
    """
    from generator.retriever import retrieve
    from generator.prompt_builder import build

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        async def error_stream():
            yield f"data: {json.dumps({'error': 'ANTHROPIC_API_KEY가 설정되지 않았습니다.'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    articles = retrieve(topic, days=days, limit=limit)

    if not articles:
        async def no_articles_stream():
            yield f"data: {json.dumps({'error': f'{topic} 관련 기사가 없습니다. 크롤러를 먼저 실행하세요.'})}\n\n"
        return StreamingResponse(no_articles_stream(), media_type="text/event-stream")

    prompt = build(topic, articles)
    article_count = len(articles)

    async def stream():
        # 메타 정보 먼저 전송
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
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
