from __future__ import annotations

import math
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import requests

from config import settings

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_HF_MODEL = settings.hf_similarity_model or _DEFAULT_MODEL
_HF_API_URL = f"https://api-inference.huggingface.co/models/{_HF_MODEL}"
_HF_TIMEOUT = max(3, int(settings.hf_timeout_seconds))


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def _mean_pool(token_vectors: list[list[float]]) -> list[float] | None:
    valid_rows = [row for row in token_vectors if isinstance(row, list) and row and all(_is_number(x) for x in row)]
    if not valid_rows:
        return None

    dims = len(valid_rows[0])
    if dims == 0:
        return None

    sums = [0.0] * dims
    row_count = 0
    for row in valid_rows:
        if len(row) != dims:
            continue
        for i, value in enumerate(row):
            sums[i] += float(value)
        row_count += 1

    if row_count == 0:
        return None

    return [value / row_count for value in sums]


def _extract_vector(payload_item: Any) -> list[float] | None:
    if isinstance(payload_item, list) and payload_item and all(_is_number(x) for x in payload_item):
        return [float(x) for x in payload_item]

    if (
        isinstance(payload_item, list)
        and payload_item
        and all(isinstance(row, list) for row in payload_item)
    ):
        return _mean_pool(payload_item)

    return None


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return max(0.0, min(1.0, dot / (norm1 * norm2)))


def _lexical_fallback(text1: str, text2: str) -> float:
    seq_ratio = SequenceMatcher(None, text1, text2).ratio()

    tokens1 = set(text1.split())
    tokens2 = set(text2.split())
    if not tokens1 or not tokens2:
        return max(0.0, min(1.0, float(seq_ratio)))

    jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
    return max(0.0, min(1.0, (seq_ratio + jaccard) / 2.0))


@lru_cache(maxsize=512)
def _remote_similarity(text1: str, text2: str) -> float | None:
    if not settings.hf_use_remote_inference:
        return None

    headers = {"Content-Type": "application/json"}
    if settings.hf_token:
        headers["Authorization"] = f"Bearer {settings.hf_token}"

    payload = {
        "inputs": [text1, text2],
        "options": {"wait_for_model": True, "use_cache": True},
    }

    try:
        response = requests.post(_HF_API_URL, headers=headers, json=payload, timeout=_HF_TIMEOUT)
        if response.status_code >= 400:
            return None

        data = response.json()
        if isinstance(data, dict) and data.get("error"):
            return None

        if not isinstance(data, list) or len(data) < 2:
            return None

        vector1 = _extract_vector(data[0])
        vector2 = _extract_vector(data[1])
        if not vector1 or not vector2:
            return None

        return _cosine_similarity(vector1, vector2)
    except Exception:
        return None


def calculate_nlp_score(text1: str, text2: str) -> float:
    text1 = _normalize(text1)
    text2 = _normalize(text2)

    if not text1 or not text2:
        return 0.5

    base_sim = _remote_similarity(text1, text2)
    if base_sim is None:
        base_sim = _lexical_fallback(text1, text2)

    boosted_score = min(1.0, max(0.0, float(base_sim)) * 1.3)
    return round(boosted_score, 4)
