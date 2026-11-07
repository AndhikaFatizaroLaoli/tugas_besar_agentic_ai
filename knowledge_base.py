"""Knowledge Base internal sederhana (tanpa dependensi tambahan).

Retriever memakai pembobotan IDF. Dua ukuran dipisahkan sesuai materi Minggu 2:
- cakupan  : seberapa besar bobot kata query yang tercakup dokumen -> menentukan
             status FOUND / NOT_FOUND (bukan sekadar "ada dokumen yang mirip").
- kemiripan: cosine TF-IDF -> hanya dipakai untuk mengurutkan dokumen yang seimbang.
"""
import math
import re
from collections import Counter

from kb_data import KB_DOCS

_STOPWORDS = {
    "the", "a", "an", "of", "to", "is", "in", "on", "and", "or", "by", "not", "can", "only",
    "yang", "dan", "di", "ke", "dari", "pada", "untuk", "dengan", "atau", "ini", "itu", "adalah", "ada",
}


def tokenize(text: str) -> list:
    """Lowercase + pecah CamelCase (ZeroDivisionError -> zero, division, error)."""
    tokens = []
    for word in re.findall(r"[A-Za-z_]+", text):
        parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", word)
        pieces = [word.lower()] + ([p.lower() for p in parts] if len(parts) > 1 else [])
        tokens.extend(p for p in pieces if len(p) >= 2 and p not in _STOPWORDS)
    return tokens


class KnowledgeBase:
    def __init__(self, docs=None, threshold: float = 0.6, top_k: int = 2):
        self.docs = docs if docs is not None else KB_DOCS
        self.threshold = threshold
        self.top_k = top_k
        self._doc_tokens = []
        for d in self.docs:
            text = f"{d['title']} {d['title']} {d['keywords']} {d['keywords']} {d['content']}"
            self._doc_tokens.append(Counter(tokenize(text)))
        n = len(self.docs)
        df = Counter()
        for counts in self._doc_tokens:
            df.update(counts.keys())
        self._df = df
        self._n = n

    def _idf(self, token: str) -> float:
        return math.log((self._n + 1) / (self._df.get(token, 0) + 1)) + 1.0

    def _score(self, q_counts: Counter, d_counts: Counter):
        q_tokens = list(q_counts)
        total = sum(self._idf(t) for t in q_tokens)
        covered = sum(self._idf(t) for t in q_tokens if t in d_counts)
        coverage = covered / total if total else 0.0
        # cosine TF-IDF (hanya untuk tie-break)
        dot = sum(q_counts[t] * self._idf(t) * d_counts[t] * self._idf(t) for t in q_tokens if t in d_counts)
        nq = math.sqrt(sum((q_counts[t] * self._idf(t)) ** 2 for t in q_tokens))
        nd = math.sqrt(sum((c * self._idf(t)) ** 2 for t, c in d_counts.items()))
        cosine = dot / (nq * nd) if nq and nd else 0.0
        return coverage, cosine

    def search(self, query: str) -> dict:
        q_counts = Counter(tokenize(query))
        ranked = []
        for doc, d_counts in zip(self.docs, self._doc_tokens):
            coverage, cosine = self._score(q_counts, d_counts)
            ranked.append((coverage, cosine, doc))
        ranked.sort(key=lambda r: (r[0], r[1]), reverse=True)
        best = ranked[0][0] if ranked else 0.0
        if not q_counts or best < self.threshold:
            return {"status": "NOT_FOUND", "query": query, "best_score": round(best, 2), "results": []}
        results = [
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "score": round(cov, 2),
                "content": d["content"],
            }
            for cov, _cos, d in ranked[: self.top_k]
            if cov >= self.threshold
        ]
        return {"status": "FOUND", "query": query, "best_score": round(best, 2), "results": results}
