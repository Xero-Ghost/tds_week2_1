# main.py
from datetime import datetime, timezone
from typing import Optional

import jwt
from jwt import InvalidTokenError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-gj0ocjgl.apps.exam.local"
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""


class VerifyRequest(BaseModel):
    token: str


@app.get("/")
def health():
    return {"ok": True}


@app.post("/verify")
def verify_token(payload: VerifyRequest):
    try:
        claims = jwt.decode(
            payload.token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={
                "require": ["exp", "iss", "aud", "sub"],
            },
        )

        email = claims.get("email")
        sub = claims.get("sub")
        aud = claims.get("aud")

        return {
            "valid": True,
            "email": email,
            "sub": sub,
            "aud": aud,
        }

    except InvalidTokenError:
        raise HTTPException(status_code=401, detail={"valid": False})
    except Exception:
        raise HTTPException(status_code=401, detail={"valid": False})