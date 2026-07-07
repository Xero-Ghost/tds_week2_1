"""
API Engineering: Idempotency + Pagination + Rate Limit

Run locally:
    pip install fastapi uvicorn --break-system-packages
    uvicorn main:app --host 0.0.0.0 --port 12000

Expose publicly for the grader:
    cloudflared tunnel --url http://localhost:12000
    # or: ngrok http 12000

Then submit: <tunnel-url>/orders as the base URL.
"""

import base64
import itertools
import math
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

# ---------------- Assigned values ----------------
TOTAL_ORDERS = 46      # T
RATE_LIMIT_MAX = 18    # R requests
RATE_LIMIT_WINDOW = 10.0  # seconds

app = FastAPI()

# ---------------- Fixed catalog (IDs 1..T) ----------------
CATALOG = [
    {
        "id": i,
        "item": f"item-{i}",
        "quantity": (i % 5) + 1,
        "amount": round(i * 9.99, 2),
    }
    for i in range(1, TOTAL_ORDERS + 1)
]


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return 0


# ---------------- Idempotent POST /orders ----------------
idempotency_store: Dict[str, dict] = {}
_id_counter = itertools.count(TOTAL_ORDERS + 1)  # new orders get ids beyond the catalog


@app.post("/orders", status_code=201)
async def create_order(
    request: Request,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}

    if idempotency_key and idempotency_key in idempotency_store:
        response.status_code = 200  # replay, not a new creation
        return idempotency_store[idempotency_key]

    new_id = next(_id_counter)
    order = {"id": new_id, "status": "created", **body}
    order["id"] = new_id  # ensure body can't overwrite the generated id

    if idempotency_key:
        idempotency_store[idempotency_key] = order

    return order


# ---------------- Cursor-paginated GET /orders ----------------
@app.get("/orders")
async def list_orders(limit: int = 10, cursor: Optional[str] = None):
    offset = decode_cursor(cursor) if cursor else 0
    limit = max(1, limit)

    page = CATALOG[offset: offset + limit]
    next_offset = offset + limit
    next_cursor = encode_cursor(next_offset) if next_offset < len(CATALOG) else None

    return {
        "items": page,
        "orders": page,       # alias
        "next_cursor": next_cursor,
        "next": next_cursor,  # alias
    }


# ---------------- Per-client rate limiting ----------------
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

        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            retry_after = max(1, math.ceil(self.window_seconds - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return await call_next(request)


# ---------------- Assemble stack ----------------
# Last added = outermost. CORS must be outermost so preflight (OPTIONS)
# is handled before it ever reaches the rate limiter.
app.add_middleware(
    RateLimitMiddleware,
    max_requests=RATE_LIMIT_MAX,
    window_seconds=RATE_LIMIT_WINDOW,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Idempotency-Key", "X-Client-Id", "Content-Type"],
    expose_headers=["Retry-After"],
)