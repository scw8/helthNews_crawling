import json
import logging
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Rate Limiter 설정 ──
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="건강 유튜브 스크립트 생성기")
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, _exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."},
    )

templates = Jinja2Templates(directory="web/templates")

# ── 세션 서명 설정 ──
SECRET_KEY = os.getenv("APP_SECRET_KEY", "change-this-in-production")
SESSION_COOKIE = "session_token"
SESSION_MAX_AGE = 60 * 60 * 24  # 24시간
serializer = URLSafeTimedSerializer(SECRET_KEY)

APP_PASSWORD = os.getenv("APP_PASSWORD", "")

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

PAPER_SOURCES = {"pubmed", "sciencedaily"}
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


# ── 인증 헬퍼 ──

def _is_authenticated(request: Request) -> bool:
    """세션 쿠키 검증. 유효하면 True."""
    if not APP_PASSWORD:
        return True  # 비밀번호 미설정 시 인증 스킵 (로컬 개발용)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    try:
        serializer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def _make_session_token() -> str:
    return serializer.dumps("authenticated")


# ── 라우트 ──

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if not APP_PASSWORD or password == APP_PASSWORD:
        token = _make_session_token()
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            httponly=True,
            samesite="lax",
            max_age=SESSION_MAX_AGE,
        )
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "topics": TOPICS,
        "source_labels": SOURCE_LABELS,
    })


@app.get("/generate")
@limiter.limit("10/hour;30/day")
async def generate(
    request: Request,
    topic: str,
    format: str = "longform",
    days: int = 60,
    limit: int = 15,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    if not _is_authenticated(request):
        async def auth_error():
            yield f"data: {json.dumps({'error': '인증이 필요합니다.'})}\n\n"
        return StreamingResponse(auth_error(), media_type="text/event-stream")

    # limit 값 서버에서 강제 제한 (20건 초과 방지)
    limit = min(limit, 20)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        async def error_stream():
            yield f"data: {json.dumps({'error': 'ANTHROPIC_API_KEY가 설정되지 않았습니다.'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    from generator.prompt_builder import build
    from storage.supabase_client import get_articles_by_topic

    articles = get_articles_by_topic(
        topic, days=days, limit=limit,
        start_date=start_date, end_date=end_date,
    )

    if not articles:
        async def no_articles_stream():
            yield f"data: {json.dumps({'error': f'{topic} 관련 기사가 없습니다. 크롤러를 먼저 실행하세요.'})}\n\n"
        return StreamingResponse(no_articles_stream(), media_type="text/event-stream")

    prompt = build(topic, articles, format=format)
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
@limiter.limit("60/minute")
async def get_articles_api(
    request: Request,
    topic: Optional[str] = None,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    if not _is_authenticated(request):
        return JSONResponse(status_code=401, content={"error": "인증이 필요합니다."})

    limit = min(limit, 100)

    from storage.supabase_client import get_articles

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

    for row in rows:
        src = row.get("source", "")
        row["source_label"] = SOURCE_LABELS.get(src, src)
        row["is_paper"] = src in PAPER_SOURCES

    if type == "paper":
        rows = [r for r in rows if r["is_paper"]]
    elif type == "article":
        rows = [r for r in rows if not r["is_paper"]]

    return JSONResponse({"items": rows, "count": len(rows)})
