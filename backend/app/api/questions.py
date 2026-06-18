from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import csv
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import random
from backend.app.services.embedding_service import FakeEmbeddingService
from backend.app.services.vector_store import VectorStore

router = APIRouter()
emb_service = FakeEmbeddingService()


def _project_root() -> Path:
    # backend/app/api/questions.py -> Project/
    return Path(__file__).resolve().parents[3]


def _rag_paths() -> tuple[str, str]:
    root = _project_root()
    csv_path = os.getenv('RAG_CSV_PATH') or str(root / 'data' / 'questions' / 'interview_questions_rag.csv')
    default_vec_dir = root / 'backend' / '.cache'
    default_vec_dir.mkdir(parents=True, exist_ok=True)
    vec_path = os.getenv('RAG_VEC_PATH') or str(default_vec_dir / 'vecstore.json')
    return csv_path, vec_path


class Question(BaseModel):
    id: str
    title: str
    body: str
    type: Optional[str] = None


class StartAttemptIn(BaseModel):
    user_id: Optional[str]
    job_id: Optional[str]
    mode: str  # 'practice' or 'test'
    question_count: int = 5


class StartAttemptOut(BaseModel):
    attempt_id: str
    questions: List[Question]


class SubmitAnswer(BaseModel):
    question_id: str
    answer_text: Optional[str] = None
    time_spent_seconds: Optional[int] = 0


class SubmitAttemptIn(BaseModel):
    user_id: Optional[str]
    answers: List[SubmitAnswer]


def _load_rag_items() -> list:
    csv_path, vec_path = _rag_paths()

    vs = VectorStore(vec_path)
    vs.load()

    vec_exists = os.path.exists(vec_path)
    csv_exists = os.path.exists(csv_path)
    if vs.items and vec_exists and csv_exists:
        try:
            vec_mtime = os.path.getmtime(vec_path)
            csv_mtime = os.path.getmtime(csv_path)
            if vec_mtime >= csv_mtime:
                return vs.items
        except OSError:
            # Fall through to CSV reload if file metadata cannot be read.
            pass

    if vs.items and not csv_exists:
        return vs.items

    if not os.path.exists(csv_path):
        return []

    items = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get('title') or ''
            body = row.get('body') or ''
            items.append({
                'id': row.get('id') or '',
                'title': title,
                'body': body,
                'role': row.get('role') or '',
                'standard_answer': row.get('standard_answer') or '',
                'scoring': row.get('scoring') or '',
                'embedding': emb_service.embed_text((title + '\n' + body)[:10000])
            })

    if items:
        vs.build_from_list(items)
        try:
            vs.save()
        except OSError:
            # Keep serving data even if index cache cannot be written.
            pass

    return items


@router.get('/rag/roles')
async def rag_roles():
    items = _load_rag_items()
    roles = sorted(list({(x.get('role') or '').strip() for x in items if (x.get('role') or '').strip()}))
    return {'roles': roles}


@router.get('/rag')
async def rag_questions(role: Optional[str] = None):
    items = _load_rag_items()
    if role:
        items = [x for x in items if (x.get('role') or '').strip() == role.strip()]

    clean = []
    for it in items:
        clean.append({
            'id': it.get('id'),
            'title': it.get('title'),
            'body': it.get('body'),
            'role': it.get('role'),
            'standard_answer': it.get('standard_answer'),
            'scoring': it.get('scoring'),
        })
    return {'items': clean}


@router.get('/', response_model=List[Question])
async def list_questions(job_id: Optional[str] = None, qtype: Optional[str] = None, limit: int = 100):
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        sample = [
            {"id": "q1", "title": "Java 基础：HashMap 原理", "body": "请解释 HashMap 的底层实现。", "type": "technical"},
            {"id": "q2", "title": "行为题：团队冲突", "body": "描述一次你处理团队冲突的经历。", "type": "behavioral"}
        ]
        return sample[:limit]

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if job_id:
            sql = '''SELECT q.* FROM questions q JOIN job_questions jq ON jq.question_id = q.id WHERE jq.job_id = %s'''
            params = [job_id]
        else:
            sql = 'SELECT * FROM questions'
            params = []

        if qtype:
            sql += ' WHERE type = %s' if not job_id else ' AND q.type = %s'
            params.append(qtype)

        sql += ' ORDER BY RANDOM() LIMIT %s'
        params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        raise HTTPException(status_code=500, detail='数据库查询失败')


@router.get('/jobs')
async def list_jobs():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        return [{"id":"job1","title":"后端工程师"},{"id":"job2","title":"数据科学家"}]
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT id, title, description FROM jobs ORDER BY created_at DESC LIMIT 200')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        raise HTTPException(status_code=500, detail='无法读取职位列表')


@router.post('/attempts', response_model=StartAttemptOut)
async def start_attempt(payload: StartAttemptIn):
    """Create an attempt (practice/test) and return selected questions."""
    db_url = os.getenv('DATABASE_URL')
    # if no DB, return fake attempt with sample questions
    if not db_url:
        attempt_id = 'a-' + str(random.randint(1000,9999))
        sample = [
            {"id": "q1", "title": "Java 基础：HashMap 原理", "body": "请解释 HashMap 的底层实现。", "type": "technical"},
            {"id": "q2", "title": "行为题：团队冲突", "body": "描述一次你处理团队冲突的经历。", "type": "behavioral"}
        ]
        return {"attempt_id": attempt_id, "questions": sample[:payload.question_count]}

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # pick questions
        if payload.job_id:
            cur.execute('SELECT q.* FROM questions q JOIN job_questions jq ON jq.question_id = q.id WHERE jq.job_id = %s ORDER BY RANDOM() LIMIT %s', [payload.job_id, payload.question_count])
        else:
            cur.execute('SELECT * FROM questions ORDER BY RANDOM() LIMIT %s', [payload.question_count])
        questions = cur.fetchall()

        # create attempt
        insert_sql = 'INSERT INTO attempts (user_id, job_id, mode, question_count, started_at) VALUES (%s, %s, %s, %s, now()) RETURNING id'
        cur.execute(insert_sql, [payload.user_id, payload.job_id, payload.mode, len(questions)])
        row = cur.fetchone()
        attempt_id = row['id'] if row else None
        conn.commit()

        cur.close()
        conn.close()

        return {"attempt_id": str(attempt_id), "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/attempts/{attempt_id}/submit')
async def submit_attempt(attempt_id: str, payload: SubmitAttemptIn):
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        # simple scoring: 0 for all
        return {"attempt_id": attempt_id, "score": 0, "saved": False}

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        total = 0.0
        max_total = 0.0

        for a in payload.answers:
            # try to get question meta.correct_answer as reference scoring
            cur.execute('SELECT meta FROM questions WHERE id = %s', [a.question_id])
            q = cur.fetchone()
            is_correct = None
            score = None
            if q and q.get('meta') and isinstance(q.get('meta'), dict):
                correct = q['meta'].get('correct_answer')
                if correct is not None and a.answer_text is not None:
                    is_correct = (str(a.answer_text).strip() == str(correct).strip())
                    score = 1.0 if is_correct else 0.0
            if score is None:
                score = 0.0
            total += float(score)
            max_total += 1.0

            cur.execute('INSERT INTO attempt_answers (attempt_id, question_id, answer_text, is_correct, score, time_spent_seconds, submitted_at) VALUES (%s,%s,%s,%s,%s,%s,now())', [attempt_id, a.question_id, a.answer_text, is_correct, score, a.time_spent_seconds])

        final_score = (total / max_total) * 100.0 if max_total > 0 else 0.0
        cur.execute('UPDATE attempts SET ended_at = now(), score = %s, duration_seconds = COALESCE(duration_seconds,0) + 0 WHERE id = %s', [final_score, attempt_id])
        conn.commit()
        cur.close()
        conn.close()

        return {"attempt_id": attempt_id, "score": final_score, "saved": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/attempts')
async def list_attempts(user_id: Optional[str] = None):
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        return []
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if user_id:
            cur.execute('SELECT * FROM attempts WHERE user_id = %s ORDER BY started_at DESC LIMIT 200', [user_id])
        else:
            cur.execute('SELECT * FROM attempts ORDER BY started_at DESC LIMIT 200')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

