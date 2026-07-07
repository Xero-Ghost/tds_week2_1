from fastapi import FastAPI, Request
import logging
import time

app = FastAPI()

# Console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

# In-memory counters
counts = {}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()

    response = await call_next(request)

    duration = (time.time() - start) * 1000

    logging.info(
        "%s %s | Status=%d | %.2f ms",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


@app.post("/hit/{key}")
def hit(key: str):
    counts[key] = counts.get(key, 0) + 1

    logging.info(f"HIT key={key} count={counts[key]}")

    return {
        "key": key,
        "count": counts[key]
    }


@app.get("/count/{key}")
def count(key: str):
    value = counts.get(key, 0)

    logging.info(f"COUNT key={key} -> {value}")

    return {
        "key": key,
        "count": value
    }


@app.get("/healthz")
def health():
    logging.info("HEALTH CHECK")

    return {
        "status": "ok",
        "redis": "up"
    }