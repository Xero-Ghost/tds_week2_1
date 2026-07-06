from __future__ import annotations

import os
import time
import uuid
import json
import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, Response, PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST


EMAIL = "24f3004321@ds.study.iitm.ac.in"

app = FastAPI()

START_TIME = time.monotonic()

# Prometheus counter visible at /metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by this service",
    ["path", "method", "status"],
)

# Structured log storage
LOGS: deque[dict[str, Any]] = deque(maxlen=2000)
LOG_LOCK = Lock()


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_log(level: str, path: str, request_id: str, **extra: Any) -> None:
    entry = {
        "level": level,
        "ts": utc_ts(),
        "path": path,
        "request_id": request_id,
        **extra,
    }
    with LOG_LOCK:
        LOGS.append(entry)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id

    start = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 3)

        HTTP_REQUESTS_TOTAL.labels(
            path=request.url.path,
            method=request.method,
            status=str(status_code),
        ).inc()

        add_log(
            "info" if status_code < 400 else "error",
            request.url.path,
            request_id,
            method=request.method,
            status_code=status_code,
            duration_ms=duration_ms,
        )


@app.get("/work")
async def work(n: int = Query(..., ge=0)):
    # Simulate real work
    total = 0
    for i in range(n):
        total += i * i

    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def healthz():
    uptime_s = time.monotonic() - START_TIME
    return {"status": "ok", "uptime_s": float(uptime_s)}


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(10, ge=1, le=200)):
    with LOG_LOCK:
        tail = list(LOGS)[-limit:]
    return JSONResponse(tail)