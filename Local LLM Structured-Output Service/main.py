from fastapi import FastAPI
from pydantic import BaseModel
import re

app = FastAPI()


class ExtractRequest(BaseModel):
    text: str


class ExtractResponse(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str


@app.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest):
    text = req.text.strip()

    if not text:
        return ExtractResponse(
            vendor="",
            amount=0.0,
            currency="USD",
            date="1970-01-01"
        )

    # Currency
    currency_match = re.search(r"\b(USD|EUR|GBP)\b", text, re.IGNORECASE)
    currency = currency_match.group(1).upper() if currency_match else "USD"

    # Date (2026-MM-DD)
    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    date = date_match.group(1) if date_match else "1970-01-01"

    # Amount
    amount = 0.0

    patterns = [
        r"Total\s*(?:Due)?[: ]*\$?([0-9]+(?:\.[0-9]{1,2})?)",
        r"Amount\s*(?:Due)?[: ]*\$?([0-9]+(?:\.[0-9]{1,2})?)",
        r"\b(?:USD|EUR|GBP)\s*([0-9]+(?:\.[0-9]{1,2})?)",
        r"\$([0-9]+(?:\.[0-9]{1,2})?)",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            amount = float(m.group(1))
            break

    # Vendor
    vendor = ""

    vendor_patterns = [
        r"Vendor[: ]*(.+)",
        r"Supplier[: ]*(.+)",
        r"Bill From[: ]*(.+)",
        r"From[: ]*(.+)",
    ]

    for p in vendor_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            vendor = m.group(1).split("\n")[0].strip()
            break

    if not vendor:
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        if lines:
            vendor = lines[0]

    return ExtractResponse(
        vendor=vendor,
        amount=amount,
        currency=currency,
        date=date
    )