#!/usr/bin/env python3
"""Small CLI to trigger CSV -> vecstore ingestion using backend utilities.

Usage: python build_vector_store.py [csv_path] [out_path]
"""
import sys
import os
import json

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
ROOT = os.path.abspath(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'backend'))

from app.services.embedding_service import FakeEmbeddingService
from app.services.vector_store import VectorStore

def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'data', 'questions', 'interview_questions.csv')
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'data', 'questions', 'vecstore.json')

    if not os.path.exists(csv_path):
        print('CSV not found:', csv_path)
        return

    embed = FakeEmbeddingService()
    items = []
    import csv
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = row.get('id') or row.get('Id') or ''
            title = row.get('title') or ''
            body = row.get('body') or ''
            role = row.get('role') or ''
            standard = row.get('standard_answer') or ''
            scoring = row.get('scoring') or ''
            emb = embed.embed_text((title + '\n' + body)[:10000])
            items.append({'id': qid, 'title': title, 'body': body, 'role': role, 'standard_answer': standard, 'scoring': scoring, 'embedding': emb})

    vs = VectorStore(out_path)
    vs.build_from_list(items)
    vs.save()
    print('Saved', len(items), 'items to', out_path)

if __name__ == '__main__':
    main()
