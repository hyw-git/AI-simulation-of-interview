from fastapi import APIRouter
import os
from backend.app.api.questions import _load_rag_items
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter()


def _rag_stats() -> dict:
    """题目与岗位数以 RAG CSV 为准（非 DB questions/jobs 表）。"""
    try:
        items = _load_rag_items()
    except Exception:
        items = []

    if not items:
        return {"questions": 0, "jobs": 0}

    roles = {(x.get('role') or '').strip() for x in items if (x.get('role') or '').strip()}
    return {"questions": len(items), "jobs": len(roles)}


def _db_count(db_url: str, table: str) -> int:
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f'SELECT COUNT(*)::int AS cnt FROM {table}')
        row = cur.fetchone()
        return int(row['cnt']) if row and row.get('cnt') is not None else 0
    except Exception:
        return 0
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@router.get('/', tags=['dashboard'])
async def dashboard():
    """仪表盘统计：用户数/面试场次来自 DB；题目数/岗位数来自 RAG 题库。"""
    rag = _rag_stats()
    result = {
        "users": 0,
        "interviews": 0,
        "questions": rag["questions"],
        "jobs": rag["jobs"],
    }

    db_url = os.getenv('DATABASE_URL')
    if db_url:
        result["users"] = _db_count(db_url, 'users')
        result["interviews"] = _db_count(db_url, 'interviews')

    return result
