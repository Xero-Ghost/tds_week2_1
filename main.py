import time
import uuid

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

EMAIL = "YOUR_LOGIN_EMAIL_HERE"
ALLOWED_ORIGIN = "https://dash-3bg9uz.example.com"

app = FastAPI()

# Strict CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Add required headers to every response
@app.middleware("http")
async def add_custom_headers(request, call_next):
    start = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start

    response.headers["X-Request-ID"] = str(uuid.uuid4())
    response.headers["X-Process-Time"] = f"{process_time:.6f}"

    return response


@app.get("/stats")
async def stats(values: str = Query(...)):
    try:
        nums = [int(x.strip()) for x in values.split(",") if x.strip()]
    except ValueError:
        return {
            "error": "values must be comma-separated integers"
        }

    if not nums:
        return {
            "error": "No values provided"
        }

    total = sum(nums)
    count = len(nums)

    return {
        "email": EMAIL,
        "count": count,
        "sum": total,
        "min": min(nums),
        "max": max(nums),
        "mean": total / count,
    }


@app.get("/")
async def root():
    return {"status": "running"}