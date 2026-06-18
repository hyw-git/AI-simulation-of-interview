import os
import psycopg2
from fastapi import APIRouter
from backend.app.api.questions import _load_rag_items
from backend.app.services.ai_service import AIService

router = APIRouter()
_ai = AIService()


@router.get('/health', tags=['health'])
async def health():
    result = {
        'status': 'ok',
        'database': 'not_configured',
        'llm_configured': _ai.use_openai,
        'speech_to_text_configured': _ai.transcription_available,
        'rag_questions': 0,
    }

    try:
        items = _load_rag_items()
        result['rag_questions'] = len(items) if items else 0
    except Exception:
        result['rag_questions'] = 0

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        return result

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.close()
        conn.close()
        result['database'] = 'ok'
    except Exception:
        result['status'] = 'degraded'
        result['database'] = 'error'

    return result
