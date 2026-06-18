from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import csv
import json
from pathlib import Path

from backend.app.services.embedding_service import FakeEmbeddingService
from backend.app.services.ai_service import AIService
from backend.app.services.vector_store import VectorStore

router = APIRouter()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _rag_paths(csv_path: str | None = None, out_path: str | None = None) -> tuple[str, str]:
    root = _project_root()
    default_vec_dir = root / 'backend' / '.cache'
    default_vec_dir.mkdir(parents=True, exist_ok=True)
    resolved_csv = csv_path or os.getenv('RAG_CSV_PATH') or str(root / 'data' / 'questions' / 'interview_questions_rag.csv')
    resolved_vec = out_path or os.getenv('RAG_VEC_PATH') or str(default_vec_dir / 'vecstore.json')
    return resolved_csv, resolved_vec


class IngestIn(BaseModel):
    csv_path: Optional[str] = None
    out_path: Optional[str] = None


class QueryIn(BaseModel):
    role: Optional[str] = None
    question: str
    top_k: int = 5


@router.post('/ingest')
async def ingest(payload: IngestIn):
    csv_path, out_path = _rag_paths(payload.csv_path, payload.out_path)

    if not os.path.exists(csv_path):
        raise HTTPException(status_code=400, detail=f'CSV not found: {csv_path}')

    embed = FakeEmbeddingService()
    items = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # expects columns: id,title,body,role,standard_answer,scoring
            qid = row.get('id') or row.get('Id') or row.get('question_id') or ''
            title = row.get('title') or row.get('question') or ''
            body = row.get('body') or row.get('prompt') or ''
            role = row.get('role') or row.get('job') or ''
            standard = row.get('standard_answer') or row.get('standard') or ''
            scoring = row.get('scoring') or row.get('meta') or ''
            text_for_emb = (title + '\n' + body)[:10000]
            embedding = embed.embed_text(text_for_emb)
            items.append({
                'id': qid,
                'title': title,
                'body': body,
                'role': role,
                'standard_answer': standard,
                'scoring': scoring,
                'embedding': embedding,
            })

    vs = VectorStore(out_path)
    vs.build_from_list(items)
    vs.save()
    return {'saved': True, 'count': len(items), 'path': out_path}


@router.post('/query')
async def query(payload: QueryIn):
    _, vecpath = _rag_paths(None, None)
    vs = VectorStore(vecpath)
    vs.load()
    if not vs.items:
        raise HTTPException(status_code=400, detail='向量索引为空，请先调用 /rag/ingest')

    embed = FakeEmbeddingService()
    q_emb = embed.embed_text(payload.question)
    results = vs.query(q_emb, role=payload.role, top_k=payload.top_k)

    # assemble context for RAG answer
    contexts = []
    for r in results:
        it = r['item']
        contexts.append(f"题目: {it.get('title')}\n问题: {it.get('body')}\n标准回答: {it.get('standard_answer')}\n评分标准: {it.get('scoring')}")

    ai = AIService()
    prompt = f"基于下面的题库内容，针对提问\n\n问题：{payload.question}\n\n请给出参考回答要点、评分依据（如何按分项打分）和一份简短面试官点评（中文）。"
    answer = ai.generate_reply(prompt, context=contexts)

    return {'answer': answer, 'retrieved': results}
