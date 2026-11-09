"""Small BM25 index (no external services). Used to shortlist concepts for a stuck point and to retrieve
course-note passages for grounded remediation."""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does", "doesn", "don", "for", "from",
    "get", "got", "how", "i", "if", "im", "in", "into", "is", "it", "its", "just", "me", "my", "no", "not",
    "of", "on", "or", "so", "some", "than", "that", "the", "their", "them", "then", "there", "these", "this",
    "to", "too", "up", "us", "was", "we", "what", "when", "where", "which", "while", "who", "why", "will",
    "with", "you", "your", "am", "keep", "keeps", "make", "makes", "sense", "understand", "confused",
    "confuses", "lost", "stuck", "help", "please", "really", "completely", "work", "out", "lab", "question",
    "all", "also", "about", "again", "any", "same", "very", "would", "could", "should", "has", "have", "had",
}


def _stem(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss") and not t.endswith("us"):
        return t[:-1]
    return t


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    toks = [_stem(w) for w in words if w not in STOP and (len(w) > 1 or w.isdigit())]
    bigrams = [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    return toks + bigrams


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(d) for d in docs]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        n = len(self.docs)
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for d, length in zip(self.docs, self.lengths):
            s = 0.0
            for t in set(query):
                f = d.get(t, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * length / (self.avg or 1))
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            out.append(s)
        return out

    def top(self, query: list[str], k: int = 5) -> list[tuple[int, float]]:
        sc = self.scores(query)
        ranked = sorted(range(len(sc)), key=lambda i: sc[i], reverse=True)
        return [(i, sc[i]) for i in ranked[:k] if sc[i] > 0]
