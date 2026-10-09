"""Canonical JSON hashing excludes volatile timestamps and job identifiers."""
import hashlib
import json
from typing import Any

def canonical_digest(document: Any) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
