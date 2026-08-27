from contextlib import asynccontextmanager
import secrets

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

import db
from config import HEALTH_API_KEY, MAX_API_BODY_BYTES
from ingestion import ingest_health_auto_export


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.apply_migrations()
    yield


app = FastAPI(
    title="Personal Health Data API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/v1/health-auto-export")
async def receive_health_auto_export(
    request: Request,
    api_key: str | None = Header(default=None, alias="api-key"),
):
    if not HEALTH_API_KEY:
        raise HTTPException(status_code=503, detail="HEALTH_API_KEY is not configured")
    if api_key is None or not secrets.compare_digest(api_key, HEALTH_API_KEY):
        raise HTTPException(status_code=401, detail="invalid API key")

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_API_BODY_BYTES:
        raise HTTPException(status_code=413, detail="request body is too large")
    body = await request.body()
    if len(body) > MAX_API_BODY_BYTES:
        raise HTTPException(status_code=413, detail="request body is too large")

    try:
        result = ingest_health_auto_export(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="failed to ingest health data") from exc

    return JSONResponse(result)
