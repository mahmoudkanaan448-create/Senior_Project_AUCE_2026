"""Simple in-memory API rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

_HITS: Dict[str, Deque[float]] = defaultdict(deque)
_MAX = 120
_WINDOW = 60.0


def allow(key: str, max_hits: int = _MAX, window: float = _WINDOW) -> bool:
    now = time.time()
    q = _HITS[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_hits:
        return False
    q.append(now)
    return True
