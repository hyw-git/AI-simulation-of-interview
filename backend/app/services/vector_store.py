import json
import os
import math
from typing import List, Dict, Any


class VectorStore:
    """A simple file-backed vector store using in-memory lists and cosine similarity.

    Stores items as dicts: {id, title, body, role, standard_answer, scoring, embedding}
    """

    def __init__(self, path: str):
        self.path = path
        self.items: List[Dict[str, Any]] = []

    def save(self):
        d = {'items': self.items}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False)

    def load(self):
        if not os.path.exists(self.path):
            self.items = []
            return
        with open(self.path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.items = d.get('items', [])

    @staticmethod
    def _dot(a: List[float], b: List[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    @staticmethod
    def _norm(a: List[float]) -> float:
        return math.sqrt(sum(x * x for x in a))

    def similarity(self, emb, other_emb) -> float:
        da = self._dot(emb, other_emb)
        na = self._norm(emb)
        nb = self._norm(other_emb)
        if na == 0 or nb == 0:
            return 0.0
        return da / (na * nb)

    def query(self, query_emb: List[float], role: str | None = None, top_k: int = 5):
        results = []
        for it in self.items:
            if role and it.get('role') and it.get('role') != role:
                continue
            emb = it.get('embedding')
            if not emb:
                continue
            score = self.similarity(query_emb, emb)
            results.append((score, it))
        results.sort(key=lambda x: x[0], reverse=True)
        return [{'score': float(s), 'item': i} for s, i in results[:top_k]]

    def build_from_list(self, items: List[Dict[str, Any]]):
        self.items = items
