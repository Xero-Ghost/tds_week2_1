from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

DEFAULTS: dict[str, Any] = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_key(raw_key: str) -> str:
    key = raw_key.strip()

    if key == "NUM_WORKERS":
        return "workers"

    if key.startswith("APP_"):
        key = key[4:]

    return key.lower()


def coerce_value(key: str, value: Any) -> Any:
    if key in {"port", "workers"}:
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "on"}

    return str(value)


def apply_layer(base: dict[str, Any], layer: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for raw_key, raw_value in layer.items():
        key = normalize_key(str(raw_key))
        if key in DEFAULTS:
            out[key] = coerce_value(key, raw_value)
    return out


def load_yaml_layer() -> dict[str, Any]:
    path = Path("config.development.yaml")
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def load_env_file_layer() -> dict[str, Any]:
    path = Path(".env")
    if not path.exists():
        return {}
    values = dotenv_values(path)
    out: dict[str, Any] = {}
    for raw_key, raw_value in values.items():
        if raw_value is None:
            continue
        key = normalize_key(raw_key)
        if key in DEFAULTS:
            out[key] = coerce_value(key, raw_value)
    return out


def load_os_env_layer() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw_key, raw_value in os.environ.items():
        if not raw_key.startswith("APP_"):
            continue
        key = normalize_key(raw_key)
        if key in DEFAULTS:
            out[key] = coerce_value(key, raw_value)
    return out


def apply_query_overrides(cfg: dict[str, Any], overrides: list[str]) -> dict[str, Any]:
    out = dict(cfg)
    for item in overrides:
        key_part, sep, value_part = item.partition("=")
        if not sep:
            continue
        key = normalize_key(key_part)
        if key in DEFAULTS:
            out[key] = coerce_value(key, value_part)
    return out


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default_factory=list)) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    cfg = apply_layer(cfg, load_yaml_layer())
    cfg = apply_layer(cfg, load_env_file_layer())
    cfg = apply_layer(cfg, load_os_env_layer())
    cfg = apply_query_overrides(cfg, set)

    cfg["api_key"] = "****"
    return cfg