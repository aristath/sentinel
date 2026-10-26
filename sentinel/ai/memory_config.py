"""Shared defaults for Sentinel's dedicated BGE-M3 research memory."""

DEFAULT_EMBED_BASE_URL = "http://127.0.0.1:18200/v1"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
DEFAULT_EMBED_DIMS = 1024
DEFAULT_MEMORY_COLLECTION = "sentinel_memories"
# Preserve the historical owner value when moving records out of the shared table.
DEFAULT_MEMORY_USER_ID = "clara"
