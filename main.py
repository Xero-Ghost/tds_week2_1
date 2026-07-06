import os
from collections import defaultdict
from decimal import Decimal
from typing import List

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


API_KEY = "ak_ha2x9m4d0u1rehezohgqrzk1"
EMAIL = os.getenv("24f3004321@ds.study.iitm.ac.in", "your_email_here")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Event(BaseModel):
    user: str
    amount: float
    ts: int


class AnalyticsRequest(BaseModel):
    events: List[Event] = Field(default_factory=list)


@app.post("/analytics")
def analytics(payload: AnalyticsRequest, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    total_events = len(payload.events)
    unique_users = len({event.user for event in payload.events})

    revenue = Decimal("0")
    user_totals = defaultdict(lambda: Decimal("0"))

    for event in payload.events:
        amount = Decimal(str(event.amount))
        if amount > 0:
            revenue += amount
            user_totals[event.user] += amount

    if user_totals:
        top_user = max(user_totals.items(), key=lambda item: item[1])[0]
    else:
        top_user = ""

    return {
        "email": EMAIL,
        "total_events": total_events,
        "unique_users": unique_users,
        "revenue": float(revenue),
        "top_user": top_user,
    }