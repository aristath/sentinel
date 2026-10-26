"""Sentinel's BGE-M3 pgvector memory store for the AI research pipeline.

Sentinel uses its own ``sentinel_memories`` collection in the host's PostgreSQL
database. Its payload format preserves the historical mem0 records, but its
1,024-dimensional BGE-M3 vectors are independent of Clara's Go memory store.

Layout:
    sentinel_memories(id uuid PK, vector vector(1024), payload jsonb)

``store`` embeds the *full* compacted content, runs a tag/metadata-scoped similarity
search embedding the *truncated* dedup query, and either reinforces an existing row
(exact-normalized or ``similarity >= ai_dedup_similarity_threshold``) or inserts a new
one. ``fetch`` is an AND-tag + optional ``as_of >= since`` filter ordered by recency.

Ported verbatim where it matters:
- dedup helpers + result shapes from ``~/clara/src/lib/server/memory/dedup.ts``
- metadata normalization from ``~/clara/src/lib/server/memory/provenance.ts``
- record mapping / pgvector SQL from ``.../memory/mem0/{utils.ts,pgvector-inspector.ts}``
- the BM25 lemmatizer + Porter stemmer from the mem0 OSS bundle (``lemmatizeForBm25``)
- embedding request shape + error strings from ``~/clara/src/lib/server/embeddings.ts``
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeGuard

import asyncpg
import httpx

from sentinel.ai.errors import MemoryStoreError
from sentinel.ai.memory_config import (
    DEFAULT_EMBED_BASE_URL,
    DEFAULT_EMBED_DIMS,
    DEFAULT_EMBED_MODEL,
    DEFAULT_MEMORY_COLLECTION,
    DEFAULT_MEMORY_USER_ID,
)

DEFAULT_DUPLICATE_SIMILARITY = 0.96
DEFAULT_EMBED_TIMEOUT_MS = 30_000
DEDUP_SEARCH_TIMEOUT_MS = 5_000

# Payload keys mem0 treats as internal (excluded from the public metadata view).
MEM0_PAYLOAD_INTERNAL_KEYS = frozenset(
    {
        "user_id",
        "agent_id",
        "run_id",
        "hash",
        "data",
        "createdAt",
        "updatedAt",
        "textLemmatized",
        "attributedTo",
        "primary_sector",
        "sector",
    }
)

# --- BM25 lemmatizer (mem0 OSS bundle, verbatim) -----------------------------

STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "get",
        "got",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "just",
        "let's",
        "me",
        "might",
        "more",
        "most",
        "mustn't",
        "must",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shall",
        "shan't",
        "she",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "were",
        "weren't",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)

# --- Porter stemmer (natural npm PorterStemmer, verbatim port) ---------------


def _categorize_groups(token: str) -> str:
    token = re.sub(r"[^aeiouy]+y", "CV", token)
    token = re.sub(r"[aeiou]+", "V", token)
    token = re.sub(r"[^V]+", "C", token)
    return token


def _categorize_chars(token: str) -> str:
    token = re.sub(r"[^aeiouy]y", "CV", token)
    token = re.sub(r"[aeiou]", "V", token)
    token = re.sub(r"[^V]", "C", token)
    return token


def _measure(token: str | None) -> float:
    if not token:
        return -1.0
    s = _categorize_groups(token)
    s = re.sub(r"^C", "", s)
    s = re.sub(r"V$", "", s)
    return len(s) / 2.0


def _ends_with_double_consonant(token: str) -> bool:
    return re.search(r"([^aeiou])\1$", token) is not None


def _attempt_replace(
    token: str,
    pattern: "str | re.Pattern[str]",
    replacement: str,
    callback: Any | None = None,
) -> "str | None":
    result: "str | None" = None
    if isinstance(pattern, str):
        if token.endswith(pattern):
            result = token[: -len(pattern)] + replacement
    else:
        m = pattern.search(token)
        if m:
            result = pattern.sub(replacement, token, count=1)
    if result and callback is not None:
        return callback(result)
    return result


def _attempt_replace_patterns(
    token: str,
    replacements: "list[tuple[str, str, str]]",
    measure_threshold: "float | None",
) -> str:
    replacement = token
    for pattern, intermediate, final in replacements:
        stripped = _attempt_replace(token, pattern, intermediate)
        if measure_threshold is None or _measure(stripped) > measure_threshold:
            replacement = _attempt_replace(replacement, pattern, final) or replacement
    return replacement


def _replace_patterns(
    token: str,
    replacements: "list[tuple[str, str, str]]",
    measure_threshold: float,
) -> str:
    return _attempt_replace_patterns(token, replacements, measure_threshold) or token


def _replace_regex(
    token: str,
    regex: "re.Pattern[str]",
    include_parts: "list[int]",
    minimum_measure: float,
) -> "str | None":
    result = ""
    m = regex.search(token)
    if m:
        for i in include_parts:
            result += m.group(i)
    if _measure(result) > minimum_measure:
        return result
    return None


def _step1a(token: str) -> str:
    if re.search(r"(ss|i)es$", token):
        return re.sub(r"(ss|i)es$", r"\1", token, count=1)
    if len(token) > 2 and token[-1] == "s" and token[-2] != "s":
        return re.sub(r"s?$", "", token, count=1)
    return token


def _step1b(token: str) -> str:
    if token.endswith("eed"):
        if _measure(token[:-3]) > 0:
            return token[:-3] + "ee"
        return token

    def _callback(stripped: str) -> "str | None":
        if "V" in _categorize_groups(stripped):
            result = _attempt_replace_patterns(
                stripped,
                [("at", "", "ate"), ("bl", "", "ble"), ("iz", "", "ize")],
                None,
            )
            if result != stripped:
                return result
            if _ends_with_double_consonant(stripped) and re.search(r"[^lsz]$", stripped):
                return re.sub(r"([^aeiou])\1$", r"\1", stripped, count=1)
            if (
                _measure(stripped) == 1
                and _categorize_chars(stripped)[-3:] == "CVC"
                and re.search(r"[^wxy]$", stripped)
            ):
                return stripped + "e"
            return stripped
        return None

    result = _attempt_replace(token, re.compile(r"(ed|ing)$"), "", _callback)
    if result:
        return result
    return token


def _step1c(token: str) -> str:
    categorized = _categorize_groups(token)
    if token.endswith("y") and "V" in categorized[:-1]:
        return token[:-1] + "i"
    return token


_STEP2: "list[tuple[str, str, str]]" = [
    ("ational", "", "ate"),
    ("tional", "", "tion"),
    ("enci", "", "ence"),
    ("anci", "", "ance"),
    ("izer", "", "ize"),
    ("abli", "", "able"),
    ("bli", "", "ble"),
    ("alli", "", "al"),
    ("entli", "", "ent"),
    ("eli", "", "e"),
    ("ousli", "", "ous"),
    ("ization", "", "ize"),
    ("ation", "", "ate"),
    ("ator", "", "ate"),
    ("alism", "", "al"),
    ("iveness", "", "ive"),
    ("fulness", "", "ful"),
    ("ousness", "", "ous"),
    ("aliti", "", "al"),
    ("iviti", "", "ive"),
    ("biliti", "", "ble"),
    ("logi", "", "log"),
]

_STEP3: "list[tuple[str, str, str]]" = [
    ("icate", "", "ic"),
    ("ative", "", ""),
    ("alize", "", "al"),
    ("iciti", "", "ic"),
    ("ical", "", "ic"),
    ("ful", "", ""),
    ("ness", "", ""),
]

_STEP4_A = re.compile(r"^(.+?)(al|ance|ence|er|ic|able|ible|ant|ement|ment|ent|ou|ism|ate|iti|ous|ive|ize)$")
_STEP4_B = re.compile(r"^(.+?)(s|t)(ion)$")


def _step2(token: str) -> str:
    return _replace_patterns(token, _STEP2, 0)


def _step3(token: str) -> str:
    return _replace_patterns(token, _STEP3, 0)


def _step4(token: str) -> str:
    return _replace_regex(token, _STEP4_A, [1], 1) or _replace_regex(token, _STEP4_B, [1, 2], 1) or token


def _step5a(token: str) -> str:
    m = _measure(re.sub(r"e$", "", token, count=1))
    if m > 1 or (m == 1 and not (_categorize_chars(token)[-4:-1] == "CVC" and re.search(r"[^wxy].$", token))):
        token = re.sub(r"e$", "", token, count=1)
    return token


def _step5b(token: str) -> str:
    if _measure(token) > 1:
        return re.sub(r"ll$", "l", token, count=1)
    return token


def stem_word(token: str) -> str:
    if len(token) < 3:
        return token
    token = token.lower()
    token = _step1a(token)
    token = _step1b(token)
    token = _step1c(token)
    token = _step2(token)
    token = _step3(token)
    token = _step4(token)
    token = _step5a(token)
    return _step5b(token)


def lemmatize_for_bm25(text: str) -> str:
    lower = text.lower()
    words = re.findall(r"[a-z0-9]+", lower)
    if not words:
        return lower
    tokens: list[str] = []
    for word in words:
        if word in STOP_WORDS:
            continue
        stemmed = stem_word(word).lower()
        if stemmed and re.fullmatch(r"[a-z0-9]+", stemmed):
            tokens.append(stemmed)
        if word.endswith("ing") and word != stemmed and re.fullmatch(r"[a-z0-9]+", word):
            tokens.append(word)
    return " ".join(tokens)


# --- dedup helpers (~/clara/src/lib/server/memory/dedup.ts, verbatim) --------


def strip_leading_date(content: str) -> str:
    return re.sub(r"^\s*\d{4}-\d{2}-\d{2}\s*\|\s*", "", content)


def compact_whitespace(content: str) -> str:
    return re.sub(r"\s+", " ", content).strip()


def truncate_content(content: str, limit: int = 600) -> str:
    compact = compact_whitespace(content)
    return compact if len(compact) <= limit else f"{compact[:limit].rstrip()}..."


def first_words(content: str, limit: int) -> str:
    parts = [p for p in compact_whitespace(content).split(" ") if p]
    return " ".join(parts[:limit])


def clamp_similarity(value: Any) -> "float | None":
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return max(0.0, min(1.0, float(value)))


def _is_number(value: Any) -> TypeGuard[int | float]:
    """JS ``typeof value === "number"`` — bools excluded."""
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _is_letter_or_number(ch: str) -> bool:
    return unicodedata.category(ch)[0] in ("L", "N")


def normalize_memory_content(content: str) -> str:
    content = strip_leading_date(content).lower()
    content = re.sub(r"https?://\S+", " ", content)
    content = "".join(ch if _is_letter_or_number(ch) else " " for ch in content)
    content = re.sub(r"\s+", " ", content)
    return content.strip()


def derive_memory_dedup_query(content: str) -> str:
    without_date = strip_leading_date(content)
    parts = [compact_whitespace(p) for p in without_date.split("|")]
    parts = [p for p in parts if p]
    if len(parts) >= 3:
        return first_words(" ".join([parts[0], parts[1], " ".join(parts[2:])]), 24)
    return first_words(without_date, 24)


def format_memory_dedup_candidates(
    records: "list[dict[str, Any]]",
) -> "list[dict[str, Any]]":
    out: list[dict[str, Any]] = []
    for record in records:
        relevance = record.get("relevance")
        similarity = record.get("similarity")
        out.append(
            {
                "id": record.get("id"),
                "content": truncate_content(str(record.get("content") or "")),
                "relevance": relevance if _is_number(relevance) else None,
                "similarity": similarity if _is_number(similarity) else None,
            }
        )
    return out


def find_deterministic_memory_duplicate(
    content: str,
    candidates: "list[dict[str, Any]]",
    min_similarity: float = DEFAULT_DUPLICATE_SIMILARITY,
) -> "dict[str, str] | None":
    normalized = normalize_memory_content(content)
    if not normalized:
        return None
    threshold = clamp_similarity(min_similarity)
    if threshold is None:
        threshold = DEFAULT_DUPLICATE_SIMILARITY
    for candidate in candidates:
        if normalize_memory_content(str(candidate.get("content") or "")) == normalized:
            return {"id": str(candidate.get("id") or ""), "reason": "exact normalized content match"}
        similarity = candidate.get("similarity")
        if _is_number(similarity):
            if similarity >= threshold:
                return {
                    "id": str(candidate.get("id") or ""),
                    "reason": f"high semantic similarity (similarity={similarity:.3f})",
                }
    return None


def _trimmed_string(value: Any) -> "str | None":
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def dedup_metadata_filters(metadata: "dict[str, Any] | None") -> "dict[str, str] | None":
    if not metadata:
        return None
    filters: dict[str, str] = {}
    domain = _trimmed_string(metadata.get("domain"))
    symbol = _trimmed_string(metadata.get("symbol"))
    kind = _trimmed_string(metadata.get("kind"))
    theme = _trimmed_string(metadata.get("theme"))
    if domain:
        filters["domain"] = domain
    if symbol:
        filters["symbol"] = symbol
    else:
        if kind:
            filters["kind"] = kind
        if theme:
            filters["theme"] = theme
    return filters if filters else None


# --- provenance (~/clara/src/lib/server/memory/provenance.ts, verbatim) ------

_PROVENANCE_STRING_FIELDS = (
    "source",
    "sourceUrl",
    "sourceFile",
    "sourceMessageId",
    "sourceRunId",
    "sourceTool",
    "observedAt",
    "verifiedAt",
    "domain",
    "supersededBy",
)


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _clamp_confidence(value: Any) -> "float | None":
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return max(0.0, min(1.0, float(value)))


def normalize_memory_provenance(value: Any) -> "dict[str, Any] | None":
    if not _is_record(value):
        return None
    provenance: dict[str, Any] = {}
    for field_name in _PROVENANCE_STRING_FIELDS:
        normalized = _trimmed_string(value.get(field_name))
        if normalized:
            provenance[field_name] = normalized
    confidence = _clamp_confidence(value.get("confidence"))
    if confidence is not None:
        provenance["confidence"] = confidence
    return provenance if provenance else None


def _unique_strings(values: "list[str]") -> "list[str]":
    seen: list[str] = []
    for value in values:
        trimmed = value.strip()
        if trimmed and trimmed not in seen:
            seen.append(trimmed)
    return seen


def _normalize_tags(value: Any) -> "list[str]":
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        trimmed = _trimmed_string(item)
        if trimmed:
            out.append(trimmed)
    return out


def normalize_memory_store_metadata(
    content: str,
    tags: "list[str] | None",
    metadata: "dict[str, Any] | None",
) -> "dict[str, Any] | None":
    merged: dict[str, Any] = dict(metadata or {})
    merged.pop("primary_sector", None)
    merged.pop("sector", None)
    provenance = normalize_memory_provenance(merged.get("provenance"))
    if provenance:
        merged["provenance"] = provenance
    else:
        merged.pop("provenance", None)
    tag_list = _unique_strings(_normalize_tags(merged.get("tags")) + list(tags or []))
    if tag_list:
        merged["tags"] = tag_list
    else:
        merged.pop("tags", None)
    return merged if merged else None


# --- record mapping (mem0/utils.ts, verbatim) --------------------------------


def to_millis(value: Any) -> "int | None":
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    # Exact integer math — float timestamp()*1000 drifts ±1 ms at epoch scale.
    delta = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def _string_field(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _number_field(value: Any) -> "float | None":
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _public_payload_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in MEM0_PAYLOAD_INTERNAL_KEYS}


def to_pgvector_record(row_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if not _is_record(payload):
        payload = {}
    metadata = _public_payload_metadata(payload)
    last_seen = metadata.get("last_seen_at")
    if last_seen is None:
        last_seen = metadata.get("lastSeenAt")
    return {
        "id": str(row_id or ""),
        "content": _string_field(payload.get("data")),
        "tags": metadata.get("tags"),
        "metadata": metadata,
        "created_at": to_millis(payload.get("createdAt")),
        "updated_at": to_millis(payload.get("updatedAt")),
        "last_seen_at": to_millis(last_seen),
        "salience": _number_field(metadata.get("salience")),
        "decay_lambda": _number_field(metadata.get("decay_lambda")),
        "version": _number_field(metadata.get("version")),
    }


def _normalized_similarity(value: Any) -> float:
    if isinstance(value, bool):
        parsed = float("nan")
    elif isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            parsed = float("nan")
    else:
        parsed = float("nan")
    if not math.isfinite(parsed):
        return 0.0
    return max(0.0, min(1.0, parsed))


def to_pgvector_search_match(
    row_id: Any,
    payload: dict[str, Any],
    similarity: Any,
    similarity_eligible: bool = True,
) -> dict[str, Any]:
    record = to_pgvector_record(row_id, payload)
    sim = _normalized_similarity(similarity)
    match = dict(record)
    match["relevance"] = sim
    match["similarity"] = sim if similarity_eligible else None
    return match


def _payload_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes)):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


# --- pg helpers (mem0/utils.ts, verbatim) ------------------------------------


def _pg_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise MemoryStoreError(f"Invalid pgvector collection name: {name}")
    return f'"{name.lower()}"'


def _pg_json_key(key: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        raise MemoryStoreError(f"Invalid pgvector filter key: {key}")
    return f"'{key}'"


def _pg_vector_literal(vector: "list[float]") -> str:
    if not vector:
        raise MemoryStoreError("Cannot query pgvector with an empty embedding")
    if any(not math.isfinite(v) for v in vector):
        raise MemoryStoreError("Cannot query pgvector with non-finite embedding values")
    return f"[{','.join(repr(float(v)) for v in vector)}]"


def _clamp_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return fallback
    return max(minimum, min(maximum, int(value)))


def _clamp_number(value: float, minimum: float, maximum: float) -> float:
    if not math.isfinite(value):
        return minimum
    return max(minimum, min(maximum, value))


def _is_missing_pgvector_store(exc: BaseException) -> bool:
    return getattr(exc, "sqlstate", None) in ("42P01", "3D000")


def _now_iso_z() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _append_metadata_conditions(
    params: "list[Any]",
    conditions: "list[str]",
    filters: "dict[str, Any] | None",
) -> None:
    for key, raw in (filters or {}).items():
        if key in ("tags", "user_id"):
            continue
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value:
            continue
        column = f"payload->>{_pg_json_key(key)}"
        includes: list[str] = []
        excludes: list[str] = []
        for part in value.split(","):
            term = part.strip()
            if not term:
                continue
            if term.startswith("!"):
                excl = term[1:].strip()
                if excl:
                    excludes.append(excl)
            else:
                includes.append(term)
        if includes:
            placeholders = []
            for item in includes:
                params.append(item)
                placeholders.append(f"${len(params)}")
            conditions.append(f"{column} IN ({', '.join(placeholders)})")
        if excludes:
            placeholders = []
            for item in excludes:
                params.append(item)
                placeholders.append(f"${len(params)}")
            conditions.append(f"({column} IS NULL OR {column} NOT IN ({', '.join(placeholders)}))")
    for tag in (filters or {}).get("tags") or []:
        value = tag.strip() if isinstance(tag, str) else ""
        if not value:
            continue
        params.append(value)
        conditions.append(f"payload->'tags' ? ${len(params)}")


# --- embedding response normalization (embeddings.ts, verbatim) --------------


def _normalize_embedding(value: Any, expected_dims: "int | None", index: int) -> "list[float]":
    if not isinstance(value, list):
        raise MemoryStoreError(f"Embedding response did not include data[{index}].embedding")
    vector: list[float] = []
    for item in value:
        try:
            num = float(item)
        except (TypeError, ValueError):
            num = float("nan")
        vector.append(num)
    if any(not math.isfinite(v) for v in vector):
        raise MemoryStoreError(f"Embedding response data[{index}].embedding included a non-numeric vector value")
    if expected_dims and len(vector) != expected_dims:
        raise MemoryStoreError(f"Embedding dimension mismatch: got {len(vector)}, expected {expected_dims}")
    return vector


# --- the store ----------------------------------------------------------------


@dataclass
class MemoryStore:
    """Direct asyncpg + pgvector client for Sentinel's configured research-memory collection."""

    user_id: str
    collection: str
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str
    embed_base_url: str
    embed_model: str
    embed_dims: int
    dedup_threshold: float = DEFAULT_DUPLICATE_SIMILARITY
    # Injection points (tests / caller-managed lifecycle).
    pool: Any = field(default=None, repr=False)
    session: httpx.AsyncClient | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.embed_base_url = self.embed_base_url.rstrip("/")
        self.pg_port = int(self.pg_port)
        self._owns_pool = self.pool is None
        self._owns_session = self.session is None
        self._http = self.session or httpx.AsyncClient()
        self._pool_lock = asyncio.Lock()

    # -- lifecycle ------------------------------------------------------------

    async def _ensure_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            async with self._pool_lock:
                if self.pool is None:
                    self.pool = await asyncpg.create_pool(
                        host=self.pg_host,
                        port=self.pg_port,
                        user=self.pg_user,
                        password=self.pg_password,
                        database=self.pg_database,
                        min_size=1,
                        max_size=5,
                    )
        return self.pool

    async def connect(self) -> None:
        await self._ensure_pool()

    async def close(self) -> None:
        if self.pool is not None and self._owns_pool:
            await self.pool.close()
            self.pool = None
        if self._owns_session:
            await self._http.aclose()

    # -- config helpers -------------------------------------------------------

    def _table(self) -> str:
        return _pg_identifier(self.collection)

    def _diagnostics(self) -> dict[str, Any]:
        return {"duplicateThreshold": self.dedup_threshold}

    def _duplicate_threshold(self) -> float:
        explicit = clamp_similarity(self.dedup_threshold)
        if explicit is not None:
            return explicit
        fallback = clamp_similarity(self._diagnostics().get("duplicateThreshold"))
        if fallback is not None:
            return fallback
        return DEFAULT_DUPLICATE_SIMILARITY

    # -- embeddings -----------------------------------------------------------

    async def _embed(self, text: str, timeout_ms: int = DEFAULT_EMBED_TIMEOUT_MS) -> "list[float]":
        return (await self.embed_many([text], timeout_ms=timeout_ms))[0]

    async def embed_many(self, texts: list[str], timeout_ms: int = DEFAULT_EMBED_TIMEOUT_MS) -> list[list[float]]:
        """Embed a migration batch in input order, splitting only capacity errors."""
        if not texts:
            return []
        body: dict[str, Any] = {"model": self.embed_model, "input": texts[0] if len(texts) == 1 else texts}
        if self.embed_dims:
            body["dimensions"] = self.embed_dims
        headers = {"Content-Type": "application/json"}
        try:
            response = await self._http.post(
                f"{self.embed_base_url}/embeddings",
                json=body,
                headers=headers,
                timeout=httpx.Timeout(timeout_ms / 1000.0),
            )
        except httpx.HTTPError as exc:
            raise MemoryStoreError(f"Embedding request failed: {exc}") from exc
        response_text = response.text
        if not response.is_success:
            capacity_error = response.status_code == 413 or (
                response.status_code == 400
                and any(s in response_text.lower() for s in ("too large", "too big", "exceed", "too many tokens"))
            )
            if capacity_error and len(texts) > 1:
                middle = (len(texts) + 1) // 2
                return await self.embed_many(texts[:middle], timeout_ms) + await self.embed_many(
                    texts[middle:], timeout_ms
                )
            raise MemoryStoreError(f"Embedding request failed with {response.status_code}: {response_text[:500]}")
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            raise MemoryStoreError("Embedding response was not valid JSON") from None
        rows = payload.get("data") or []
        if len(rows) != len(texts):
            raise MemoryStoreError(f"Embedding response count mismatch: got {len(rows)}, expected {len(texts)}")
        ordered: dict[int, list[float]] = {}
        for position, row in enumerate(rows):
            if not isinstance(row, dict):
                raise MemoryStoreError("Embedding response contained an invalid row")
            index = row.get("index", position)
            if type(index) is not int or index < 0 or index >= len(texts) or index in ordered:
                raise MemoryStoreError("Embedding response contained invalid or duplicate indices")
            ordered[index] = _normalize_embedding(row.get("embedding"), self.embed_dims, index)
        return [ordered[i] for i in range(len(texts))]

    # -- public API -----------------------------------------------------------

    async def store(
        self,
        content: str,
        tags: "list[str] | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> dict[str, Any]:
        """Dedup-then-store. Returns a MemoryDedupResult-shaped dict."""
        memory = compact_whitespace(content)
        if not memory:
            raise MemoryStoreError("Memory content is required")
        query = derive_memory_dedup_query(memory)
        threshold = self._duplicate_threshold()
        try:
            records = await self._search_similar(
                query,
                limit=5,
                min_similarity=threshold,
                filters=dedup_metadata_filters(metadata),
            )
            candidates = format_memory_dedup_candidates(records)
        except Exception as exc:  # noqa: BLE001 - parity: search failures skip, not raise
            return {
                "action": "skipped",
                "status": "search_failed",
                "query": query,
                "candidateCount": 0,
                "reason": "Memory duplicate search failed; skipped store so this can be retried later.",
                "error": str(exc),
                "candidates": [],
            }

        # Parity: duplicate detection runs against the RAW records (untruncated
        # content); ``candidates`` (truncated) only feed the result payload.
        duplicate = find_deterministic_memory_duplicate(memory, records, threshold)
        if duplicate:
            await self._reinforce(duplicate["id"], 0.05)
            return {
                "action": "reinforced",
                "status": "duplicate",
                "query": query,
                "candidateCount": len(candidates),
                "duplicateId": duplicate["id"],
                "reason": duplicate["reason"],
                "candidates": candidates,
            }

        stored = await self._insert(memory, tags, metadata)
        return {
            "action": "stored",
            "status": "stored",
            "query": query,
            "candidateCount": len(candidates),
            "stored": stored,
            "reason": "No high-confidence duplicate found.",
            "candidates": candidates,
        }

    async def fetch(
        self,
        tags: "list[str] | None",
        since: "str | None" = None,
        limit: int = 100,
        offset: int = 0,
    ) -> "list[dict[str, Any]]":
        """AND-tag filter, optional ``as_of >= since`` (ISO date), ordered by recency."""
        table = self._table()
        params: list[Any] = [self.user_id]
        conditions = ["payload->>'user_id' = $1"]
        for tag in tags or []:
            value = tag.strip() if isinstance(tag, str) else ""
            if not value:
                continue
            params.append(value)
            conditions.append(f"payload->'tags' ? ${len(params)}")
        if since is not None:
            params.append(str(since))
            conditions.append(f"payload->>'as_of' >= ${len(params)}")
        params.append(max(0, int(limit)))
        params.append(max(0, int(offset)))
        where = f"WHERE {' AND '.join(conditions)}"
        sql = (
            f"SELECT id::text AS id, payload FROM {table} {where} "  # noqa: S608
            "ORDER BY COALESCE(payload->>'updatedAt', payload->>'createdAt', '') DESC, id::text ASC "
            f"LIMIT ${len(params) - 1} OFFSET ${len(params)}"
        )
        pool = await self._ensure_pool()
        try:
            rows = await pool.fetch(sql, *params)
        except Exception as exc:  # noqa: BLE001
            if _is_missing_pgvector_store(exc):
                return []
            raise
        records: list[dict[str, Any]] = []
        for row in rows:
            record = to_pgvector_record(row["id"], _payload_to_dict(row["payload"]))
            if record["content"].strip():
                records.append(record)
        return records

    async def count(self) -> int:
        table = self._table()
        pool = await self._ensure_pool()
        try:
            row = await pool.fetchrow(
                f"SELECT COUNT(*)::int AS count FROM {table} WHERE payload->>'user_id' = $1",  # noqa: S608
                self.user_id,
            )
        except Exception as exc:  # noqa: BLE001
            if _is_missing_pgvector_store(exc):
                return 0
            raise
        return int(row["count"]) if row and row["count"] is not None else 0

    async def stats(self) -> dict[str, Any]:
        table = self._table()
        pool = await self._ensure_pool()
        try:
            row = await pool.fetchrow(
                f"SELECT COUNT(*)::int AS total, "  # noqa: S608
                "MAX(COALESCE(payload->>'updatedAt', payload->>'createdAt', '')) AS last_stored_at "
                f"FROM {table} WHERE payload->>'user_id' = $1",
                self.user_id,
            )
        except Exception as exc:  # noqa: BLE001
            if _is_missing_pgvector_store(exc):
                return {"findings": 0, "last_stored_at": None}
            raise
        total = int(row["total"]) if row and row["total"] is not None else 0
        return {"findings": total, "last_stored_at": row["last_stored_at"] if row else None}

    # -- internals ------------------------------------------------------------

    async def _search_similar(
        self,
        query: str,
        limit: int = 5,
        min_similarity: "float | None" = None,
        filters: "dict[str, Any] | None" = None,
    ) -> "list[dict[str, Any]]":
        limit = _clamp_int(limit, 1, 20, 5)
        min_similarity = self.dedup_threshold if min_similarity is None else min_similarity
        embedding = await self._embed(query, timeout_ms=DEDUP_SEARCH_TIMEOUT_MS)
        table = self._table()
        params: list[Any] = [_pg_vector_literal(embedding)]
        conditions: list[str] = []
        params.append(self.user_id)
        conditions.append(f"payload->>'user_id' = ${len(params)}")
        _append_metadata_conditions(params, conditions, filters)
        if min_similarity is not None:
            params.append(min_similarity)
            conditions.append(f"1 - (vector <=> $1::vector) >= ${len(params)}")
        params.append(limit)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT id::text AS id, payload, 1 - (vector <=> $1::vector) AS similarity "  # noqa: S608
            f"FROM {table} {where} ORDER BY vector <=> $1::vector ASC LIMIT ${len(params)}"
        )
        pool = await self._ensure_pool()
        try:
            rows = await pool.fetch(sql, *params)
        except Exception as exc:  # noqa: BLE001
            if _is_missing_pgvector_store(exc):
                return []
            raise
        matches: list[dict[str, Any]] = []
        for row in rows:
            match = to_pgvector_search_match(row["id"], _payload_to_dict(row["payload"]), row["similarity"], True)
            if match["content"].strip():
                matches.append(match)
        return matches

    async def _reinforce(self, memory_id: str, boost: float = 0.05) -> None:
        normalized_boost = _clamp_number(float(boost), 0.0, 1.0)
        now = _now_iso_z()
        table = self._table()
        pool = await self._ensure_pool()
        try:
            await pool.execute(
                f"""
                UPDATE {table}
                SET payload = jsonb_set(
                    jsonb_set(
                        jsonb_set(
                            payload,
                            '{{salience}}',
                            to_jsonb(LEAST(1.0, GREATEST(0.0,
                                COALESCE((payload->>'salience')::numeric, 0) + $3::numeric)))
                        ),
                        '{{last_seen_at}}', to_jsonb($4::text)
                    ),
                    '{{updatedAt}}', to_jsonb($4::text)
                )
                WHERE id = $1 AND payload->>'user_id' = $2
                """,  # noqa: S608
                memory_id,
                self.user_id,
                normalized_boost,
                now,
            )
        except Exception as exc:  # noqa: BLE001 - parity: missing store is a no-op
            if not _is_missing_pgvector_store(exc):
                raise

    async def _insert(
        self,
        content: str,
        tags: "list[str] | None",
        metadata: "dict[str, Any] | None",
    ) -> dict[str, Any]:
        embedding = await self._embed(content)
        memory_id = _uuid4_hex()
        normalized = normalize_memory_store_metadata(content, tags, metadata)
        payload: dict[str, Any] = dict(normalized or {})
        payload["user_id"] = self.user_id
        payload["data"] = content
        payload["hash"] = hashlib.md5(content.encode("utf-8")).hexdigest()  # noqa: S324
        payload["textLemmatized"] = lemmatize_for_bm25(content)
        payload["createdAt"] = _now_iso_z()
        table = self._table()
        pool = await self._ensure_pool()
        try:
            await pool.execute(
                f"INSERT INTO {table} (id, vector, payload) VALUES ($1, $2::vector, $3::jsonb)",  # noqa: S608
                memory_id,
                _pg_vector_literal(embedding),
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception as exc:  # noqa: BLE001
            if _is_missing_pgvector_store(exc):
                raise MemoryStoreError(f"pgvector store '{self.collection}' is missing; refusing to create it") from exc
            raise MemoryStoreError(f"Failed to insert memory: {exc}") from exc
        return {
            "id": memory_id,
            "content": content,
            "user_id": self.user_id,
        }


def _uuid4_hex() -> str:
    import uuid

    return str(uuid.uuid4())


async def make_memory_store(settings: Any) -> MemoryStore:
    """Build a MemoryStore from Sentinel settings (mirrors ``LLMClient.from_settings``)."""
    return MemoryStore(
        user_id=str(await settings.get("ai_memory_user_id", DEFAULT_MEMORY_USER_ID)),
        collection=str(await settings.get("ai_memory_collection", DEFAULT_MEMORY_COLLECTION)),
        pg_host=str(await settings.get("ai_pg_host", "127.0.0.1")),
        pg_port=int(await settings.get("ai_pg_port", 5432)),
        pg_database=str(await settings.get("ai_pg_database", "clara_memories")),
        pg_user=str(await settings.get("ai_pg_user", "clara")),
        pg_password=str(await settings.get("ai_pg_password", "")),
        embed_base_url=str(await settings.get("ai_embed_base_url", DEFAULT_EMBED_BASE_URL)),
        embed_model=str(await settings.get("ai_embed_model", DEFAULT_EMBED_MODEL)),
        embed_dims=int(await settings.get("ai_embed_dims", DEFAULT_EMBED_DIMS)),
        dedup_threshold=float(await settings.get("ai_dedup_similarity_threshold", 0.96)),
    )
