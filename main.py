import time
import uuid
from typing import Callable, Awaitable

from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

EMAIL = "YOUR_LOGIN_EMAIL_HERE"
ALLOWED_ORIGIN = "https://dash-3bg9uz.example.com"

api = FastAPI()


class SecurityHeadersAndCORS:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        headers = dict(
            (k.decode("latin1").lower(), v.decode("latin1"))
            for k, v in scope.get("headers", [])
        )
        origin = headers.get("origin", "")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))

                process_time = max(time.perf_counter() - start, 0.0)
                response_headers.append((b"x-request-id", request_id.encode()))
                response_headers.append((b"x-process-time", f"{process_time:.6f}".encode()))

                if origin == ALLOWED_ORIGIN:
                    response_headers.append(
                        (b"access-control-allow-origin", ALLOWED_ORIGIN.encode())
                    )
                    response_headers.append((b"vary", b"Origin"))

                message["headers"] = response_headers

            await send(message)

        path = scope.get("path", "")
        method = scope.get("method", "")

        if path == "/stats" and method == "OPTIONS":
            if origin == ALLOWED_ORIGIN:
                req_headers = headers.get("access-control-request-headers", "")
                response_headers = {
                    "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": req_headers if req_headers else "*",
                    "Vary": "Origin",
                }
                response = Response(status_code=200, headers=response_headers)
            else:
                response = Response(status_code=204)

            await response(scope, receive, send_wrapper)
            return

        await self.app(scope, receive, send_wrapper)


@api.get("/stats")
async def stats(values: str = Query(...)):
    nums = [int(x.strip()) for x in values.split(",") if x.strip() != ""]
    if not nums:
        return JSONResponse(
            status_code=400,
            content={"error": "values must contain at least one integer"},
        )

    count = len(nums)
    total = sum(nums)
    mn = min(nums)
    mx = max(nums)
    mean = total / count

    return {
        "email": EMAIL,
        "count": count,
        "sum": total,
        "min": mn,
        "max": mx,
        "mean": mean,
    }


app = SecurityHeadersAndCORS(api)