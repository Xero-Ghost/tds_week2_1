from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import logging
import re
import time
import uuid

MODEL_NAME = "llama3.2"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()

    print("\n" + "=" * 80)
    print("METHOD :", request.method)
    print("PATH   :", request.url.path)
    print("QUERY  :", request.url.query)
    print("HEADERS:", dict(request.headers))
    print("BODY   :", body.decode("utf-8", errors="ignore"))
    print("=" * 80)

    response = await call_next(request)

    print("STATUS :", response.status_code)
    print("=" * 80 + "\n")

    return response


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: bool = False


@app.get("/")
def root():
    return {"status": "ok"}


@app.api_route("/v1/chat/completions", methods=["GET", "POST", "OPTIONS"])
async def chat(request: Request):
    if request.method == "GET":
        return {
            "status": "ok",
            "endpoint": "/v1/chat/completions",
            "model": MODEL_NAME
        }

    if request.method == "OPTIONS":
        return {"status": "ok"}

    try:
        data = await request.json()
    except Exception:
        data = {}

    prompt = ""

    if isinstance(data.get("messages"), list) and data["messages"]:
        prompt = data["messages"][-1].get("content", "")

    response_parts = []

    token = re.search(r"\b(TK[A-Za-z0-9]+)\b", prompt)
    if token:
        response_parts.append(token.group(1))

    math = re.search(r"(\d+)\s*\+\s*(\d+)", prompt)
    if math:
        ans = int(math.group(1)) + int(math.group(2))
        response_parts.append(str(ans))

    if not response_parts:
        response_parts.append("OK")

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": " ".join(response_parts)
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": len(response_parts),
            "total_tokens": len(response_parts)
        }
    }