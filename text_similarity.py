# Text similarity metrics: Jaccard, cosine, and others.
from __future__ import annotations
import math
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    return re.findall(r'\w+', text.lower())


def jaccard_similarity(a: str, b: str) -> float:
    sa, sb = set(_tokenize(a)), set(_tokenize(b))
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def cosine_similarity(a: str, b: str) -> float:
    ca, cb = Counter(_tokenize(a)), Counter(_tokenize(b))
    if not ca and not cb:
        return 1.0
    vocab = set(ca) | set(cb)
    dot = sum(ca[w] * cb[w] for w in vocab)
    mag_a = math.sqrt(sum(v * v for v in ca.values()))
    mag_b = math.sqrt(sum(v * v for v in cb.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return round(dot / (mag_a * mag_b), 10)


def overlap_coefficient(a: str, b: str) -> float:
    sa, sb = set(_tokenize(a)), set(_tokenize(b))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def dice_coefficient(a: str, b: str) -> float:
    sa, sb = set(_tokenize(a)), set(_tokenize(b))
    if not sa and not sb:
        return 1.0
    return 2 * len(sa & sb) / (len(sa) + len(sb)) if (sa or sb) else 0.0
