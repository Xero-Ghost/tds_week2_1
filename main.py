"""
Middleware Stack: Rate-Limit + CORS + Request Context
------------------------------------------------------
Composes three middleware layers around a single GET /ping endpoint:

  1. RequestContextMiddleware  -> propagates / generates X-Request-ID
  2. RateLimitMiddleware       -> per X-Client-Id sliding-window limiter
  3. CORSMiddleware            -> scoped allow-list, no wildcards

IMPORTANT — fill these in before deploying:
  - EMAIL            : your logged-in email address returned by /ping
  - EXAM_PAGE_ORIGIN  : the origin of the grader/exam page (so its
                        browser-based fetch() calls aren't blocked by CORS)

Middleware registration order matters. Starlette treats the *last*
middleware added via app.add_middleware(...) as the OUTERMOST layer
(it runs first on the way in, last on the way out). We want:

    CORS (outermost)  ->  RateLimit  ->  RequestContext  ->  endpoint

so that CORS headers are attached even to 429 responses (otherwise the
browser would report a CORS error instead of surfacing the 429), and
Request-Context is closest to the endpoint so it can freely read/set
request.state and stamp the response header last on the way out.
"""

import os
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

# --------------------------------------------------------------------------
# Configuration — EDIT THESE TWO VALUES
# --------------------------------------------------------------------------
EMAIL = os.environ.get("PING_EMAIL", "24f3004321@ds.study.iitm.ac.in")

ASSIGNED_ORIGIN = "https://app-cv9rm8.example.com"
EXAM_PAGE_ORIGIN = os.environ.get("EXAM_PAGE_ORIGIN", "https://app-cv9rm8.example.com")

# Explicit allow-list only. No "*" wildcard is ever used, so the ACAO
# header is only ever emitted for these exact origins (Starlette's
# CORSMiddleware reflects back the *matching* origin, never "*").
ALLOWED_ORIGINS = [ASSIGNED_ORIGIN, EXAM_PAGE_ORIGIN]

RATE_LIMIT_MAX_REQUESTS = 8   # bucket size B
RATE_LIMIT_WINDOW_SECONDS = 10  # window in seconds


# --------------------------------------------------------------------------
# Middleware 1: Request context propagation
# --------------------------------------------------------------------------
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming_id = request.headers.get("X-Request-ID")
        request_id = incoming_id if incoming_id else str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# --------------------------------------------------------------------------
# Middleware 2: Per-client rate limiting (sliding window, in-memory)
# --------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = RATE_LIMIT_MAX_REQUESTS,
                 window_seconds: float = RATE_LIMIT_WINDOW_SECONDS):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.buckets: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client_id = request.headers.get("X-Client-Id", "anonymous")
        now = time.monotonic()
        bucket = self.buckets[client_id]

        # Evict timestamps that have aged out of the window.
        while bucket and (now - bucket[0]) > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Please retry later."},
                status_code=429,
            )

        bucket.append(now)
        return await call_next(request)


# --------------------------------------------------------------------------
# App + middleware registration (order = innermost added first)
# --------------------------------------------------------------------------
app = FastAPI()

app.add_middleware(RequestContextMiddleware)   # innermost
app.add_middleware(RateLimitMiddleware)        # middle
app.add_middleware(                            # outermost
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.get("/ping")
async def ping(request: Request):
    return {"email": EMAIL, "request_id": request.state.request_id}