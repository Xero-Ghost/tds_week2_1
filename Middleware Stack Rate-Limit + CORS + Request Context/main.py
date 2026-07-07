"""
Middleware Stack: Rate-Limit + CORS + Request Context

Run locally:
    pip install fastapi uvicorn --break-system-packages
    uvicorn app:app --host 0.0.0.0 --port 8000

Then expose it publicly for the grader, e.g.:
    cloudflared tunnel --url http://localhost:8000
    # or: ngrok http 8000
"""

import time
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

# ---------------- Assigned values ----------------
ALLOWED_ORIGINS = [
    "https://app-cv9rm8.example.com",
    "https://exam.sanand.workers.dev",
]
RATE_LIMIT_MAX = 8          # B requests
RATE_LIMIT_WINDOW = 10.0    # seconds
YOUR_EMAIL = "24f3004321@ds.study.iitm.ac.in"

app = FastAPI()


# ---------------- Middleware 1: Request context ----------------
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        request_id = incoming if incoming else str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------- Middleware 3: Per-client rate limiting ----------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int, window_seconds: float):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.buckets: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client_id = request.headers.get("x-client-id", "anonymous")
        now = time.monotonic()
        bucket = self.buckets[client_id]

        # drop timestamps outside the window
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        bucket.append(now)
        return await call_next(request)


# ---------------- Assemble stack ----------------
# app.add_middleware() prepends internally, so the LAST one added ends up
# OUTERMOST. We want:
#   CORS (outermost, handles preflight first)
#   -> RateLimit
#   -> RequestContext (innermost, closest to the route)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=RATE_LIMIT_MAX,
    window_seconds=RATE_LIMIT_WINDOW,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # explicit list -> no wildcard, exact match only
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID"],  # required so browser JS can read the header
)


@app.get("/ping")
async def ping(request: Request):
    return {"email": YOUR_EMAIL, "request_id": request.state.request_id}