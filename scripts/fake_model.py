"""Simple script to generate a fake embedding for given text.

Usage:
  python scripts/fake_model.py "some text"

Writes a small JSON with the vector length.
"""
import sys
import json
from backend.app.services.embedding_service import FakeEmbeddingService

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/fake_model.py "some text"')
        sys.exit(1)
    text = sys.argv[1]
    svc = FakeEmbeddingService()
    emb = svc.embed_text(text)
    out = {"len": len(emb), "sample": emb[:8]}
    print(json.dumps(out, ensure_ascii=False))

