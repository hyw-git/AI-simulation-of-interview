from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Any
import uuid
import os
import json
import requests
import asyncio
import csv
import random
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from backend.app.services.embedding_service import FakeEmbeddingService
from backend.app.services.ai_service import AIService
from backend.app.services.vector_store import VectorStore
from backend.app.services.repo_analyzer import analyze_repo as analyze_git_repo
from backend.app.services.code_runner import run_python, run_code, run_tests, detect_runtimes
from backend.app.api.auth import optional_current_user
from fastapi import UploadFile, File

router = APIRouter()

ai_service = AIService()
emb_service = FakeEmbeddingService()

# 内存会话：DB 写入失败或 WS 读配置失败时仍能维持策略、轮次与代码实战状态
_INTERVIEW_SESSIONS: dict[str, dict] = {}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _db_conn():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        return None
    return psycopg2.connect(db_url)


def _valid_uuid(value: str | None) -> str | None:
    if not value or value == 'guest':
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError):
        return None


def _serialize_report_row(row: dict) -> dict:
    rj = row.get('report_json') or {}
    if isinstance(rj, str):
        try:
            rj = json.loads(rj)
        except json.JSONDecodeError:
            rj = {}
    meta = rj.get('_meta') or {}
    report = {k: v for k, v in rj.items() if k != '_meta'}
    generated_at = row.get('generated_at')
    return {
        'id': str(row.get('id')),
        'interview_id': str(row.get('interview_id')),
        'generated_at': generated_at.isoformat() if generated_at else None,
        'role': meta.get('role'),
        'focus': meta.get('focus'),
        'mode': meta.get('mode'),
        'difficulty': meta.get('difficulty'),
        'time_limit': meta.get('time_limit'),
        'transcript': meta.get('transcript') or [],
        'report': report,
    }


def _load_rag_store() -> VectorStore:
    root = _project_root()
    csvpath = os.getenv('RAG_CSV_PATH') or str(root / 'data' / 'questions' / 'interview_questions_rag.csv')
    default_vec_dir = root / 'backend' / '.cache'
    default_vec_dir.mkdir(parents=True, exist_ok=True)
    vecpath = os.getenv('RAG_VEC_PATH') or str(default_vec_dir / 'vecstore.json')
    vs = VectorStore(vecpath)
    vs.load()

    if not vs.items and os.path.exists(csvpath):
        items = []
        with open(csvpath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title') or row.get('question') or ''
                body = row.get('body') or row.get('question') or ''
                text_for_emb = (title + '\n' + body)[:10000]
                items.append({
                    'id': row.get('id') or row.get('qid') or '',
                    'title': title,
                    'body': body,
                    'role': row.get('role') or row.get('language') or '',
                    'standard_answer': row.get('standard_answer') or row.get('answer') or '',
                    'scoring': row.get('scoring') or '',
                    'embedding': emb_service.embed_text(text_for_emb),
                })
        if items:
            vs.build_from_list(items)
            try:
                vs.save()
            except OSError:
                pass

    return vs


def _compute_core_rounds(mode: str | None, difficulty: int | None) -> int:
    """难度对应的核心追问轮次；达到后进入八股/项目拓展阶段（不结束面试）。"""
    try:
        diff = int(difficulty or 3)
    except (TypeError, ValueError):
        diff = 3
    diff = max(1, min(5, diff))
    by_diff = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7}
    base = by_diff.get(diff, 5)
    if (mode or 'practice') == 'test':
        base = max(3, base - 1)
    return base


def _has_resume_context(
    use_resume: bool | None,
    resume_summary: str | None,
    resume_keywords: list | None,
) -> bool:
    if not use_resume:
        return False
    if (resume_summary or '').strip():
        return True
    return bool(resume_keywords)


def _resolve_interview_strategy(
    mode: str | None,
    focus: str | None,
    difficulty: int | None,
    use_resume: bool | None,
    resume_summary: str | None,
    resume_keywords: list | None,
    repo_analysis: dict | None = None,
    seed_question_id: str | None = None,
) -> dict:
    """根据面试设置决定开场与追问策略（优先级：题库带入 > 仓库 > 简历 > 默认）。"""
    if seed_question_id:
        return {
            'id': 'seed_question',
            'label': '题库带入',
            'opening': 'seed',
            'description': '从题库指定题目开始，再按配置深度追问',
        }
    if repo_analysis and repo_analysis.get('summary') and not repo_analysis.get('error'):
        return {
            'id': 'repo_led',
            'label': '仓库驱动',
            'opening': 'repo',
            'description': '基于 Git 仓库结构与 README 提问，核心阶段不随机抽题库首题',
        }
    if _has_resume_context(use_resume, resume_summary, resume_keywords):
        return {
            'id': 'resume_led',
            'label': '简历驱动',
            'opening': 'resume',
            'description': '先基于简历项目与经历提问，核心阶段不随机抽题库首题',
        }
    focus_key = (focus or '综合').strip()
    if focus_key == '技术深度':
        return {
            'id': 'tech_depth',
            'label': '技术深挖',
            'opening': 'rag',
            'description': '以岗位题库为主，侧重原理与实现细节',
        }
    if focus_key == '项目实践':
        return {
            'id': 'project_focus',
            'label': '项目导向',
            'opening': 'rag',
            'description': '题库选题偏工程实践，追问关注落地与排障',
        }
    if (mode or 'practice') == 'test':
        return {
            'id': 'assessment',
            'label': '测评模式',
            'opening': 'rag',
            'description': '结构化抽题与评分，节奏更紧凑',
        }
    return {
        'id': 'standard',
        'label': '题库驱动',
        'opening': 'rag',
        'description': '从岗位题库抽首题，再按难度深度追问',
    }


def _resolve_interview_phase(current_round: int, core_rounds: int, strategy_id: str | None = None) -> str:
    """resume=简历驱动核心阶段；core=题库核心；bagu/project=拓展阶段交替。"""
    sid = strategy_id or 'standard'
    if current_round <= core_rounds:
        if sid == 'repo_led':
            return 'repo'
        if sid == 'resume_led':
            return 'resume'
        return 'core'
    ext = current_round - core_rounds
    return 'bagu' if ext % 2 == 1 else 'project'


def _phase_label(phase: str) -> str:
    return {
        'resume': '简历深挖',
        'repo': '仓库深挖',
        'core': '核心追问',
        'bagu': '拓展·八股基础',
        'project': '拓展·项目实践',
    }.get(phase, '核心追问')


def _load_user_resume(conn, user_id: str) -> dict | None:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            'SELECT text_content, summary, keywords, file_name FROM user_resumes WHERE user_id = %s',
            [user_id],
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        cur.close()


_BAGU_HINTS = ('原理', '源码', '机制', 'HashMap', '并发', 'JVM', '索引', '事务', 'HTTP', '渲染', '算法', '复杂度', '底层', '数据结构')
_PROJECT_HINTS = ('项目', '实践', '上线', '部署', '优化', '高并发', '架构', '工程', '监控', '测试', '迭代', '协作')


def _pick_extended_rag_item(role: str | None, phase: str, exclude_ids: set | None = None) -> dict | None:
    try:
        vs = _load_rag_store()
    except Exception:
        return None
    if not vs.items:
        return None

    role_key = (role or '').strip()
    candidates = [
        it for it in vs.items
        if not role_key or (it.get('role') or '').strip() == role_key
    ]
    if not candidates:
        candidates = list(vs.items)

    hints = _BAGU_HINTS if phase == 'bagu' else _PROJECT_HINTS
    filtered = []
    for it in candidates:
        text = f"{it.get('title', '')} {it.get('body', '')}"
        if any(h in text for h in hints):
            filtered.append(it)
    if not filtered:
        filtered = candidates

    exclude = exclude_ids or set()
    pool = [it for it in filtered if str(it.get('id') or '') not in exclude]
    if not pool:
        pool = [it for it in candidates if str(it.get('id') or '') not in exclude] or candidates
    return random.choice(pool)


def _rag_top_k(difficulty: str | int | None) -> int:
    try:
        diff = int(difficulty or 3)
    except (TypeError, ValueError):
        diff = 3
    return {1: 2, 2: 3, 3: 3, 4: 4, 5: 5}.get(max(1, min(5, diff)), 3)


def _load_interview_config(conn, interview_id: str) -> dict:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT parsed_json, content FROM interview_messages "
            "WHERE interview_id = %s AND sender = 'system' AND role = 'config' "
            "ORDER BY created_at ASC LIMIT 1",
            [interview_id],
        )
        row = cur.fetchone()
        if not row:
            return {}
        cfg = row.get('parsed_json')
        if isinstance(cfg, dict) and cfg:
            return cfg
        raw = row.get('content')
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    finally:
        cur.close()
    return {}


def _save_session_config(interview_id: str, config: dict) -> None:
    sess = _INTERVIEW_SESSIONS.setdefault(interview_id, {})
    sess.update(config)
    sess.setdefault('candidate_rounds', 0)
    sess.setdefault('coding_prompted', False)


def _merge_session_config(interview_id: str, db_cfg: dict | None = None, ws_overrides: dict | None = None) -> dict:
    base = dict(db_cfg or {})
    mem = dict(_INTERVIEW_SESSIONS.get(interview_id) or {})
    merged = {**base, **mem}
    if ws_overrides:
        for key, val in ws_overrides.items():
            if val is not None and val != '':
                merged[key] = val
    return merged


def _bump_candidate_round(interview_id: str, conn=None) -> int:
    sess = _INTERVIEW_SESSIONS.setdefault(interview_id, {})
    db_count = 0
    if conn:
        try:
            db_count = _count_candidate_rounds(conn, interview_id)
        except Exception:
            db_count = 0
    mem_count = int(sess.get('candidate_rounds') or 0) + 1
    current = max(mem_count, db_count)
    sess['candidate_rounds'] = current
    return current


def _coding_trigger_round(cfg: dict) -> int:
    role = (cfg.get('role') or '').strip()
    try:
        diff = int(cfg.get('difficulty') or 3)
    except (TypeError, ValueError):
        diff = 3
    if 'Python' in role or '算法' in role:
        return 2
    if diff >= 4:
        return 2
    return 3


def _should_prompt_coding(cfg: dict, current_round: int, phase: str) -> bool:
    if not cfg.get('enable_coding'):
        return False
    if cfg.get('coding_prompted'):
        return False
    if phase not in ('repo', 'resume', 'core'):
        return False
    return current_round >= _coding_trigger_round(cfg)


def _count_candidate_rounds(conn, interview_id: str) -> int:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*)::int FROM interview_messages "
            "WHERE interview_id = %s AND sender = 'candidate'",
            [interview_id],
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        cur.close()


def _record_round(cur, interview_id: str, round_index: int) -> None:
    cur.execute(
        'INSERT INTO interview_rounds (interview_id, round_index, question_id) VALUES (%s, %s, NULL)',
        [interview_id, round_index],
    )


def _pick_opening_from_rag(role: str | None, difficulty: int | None = 3) -> dict | None:
    try:
        vs = _load_rag_store()
    except Exception:
        return None
    if not vs.items:
        return None

    role_key = (role or '').strip()
    candidates = [
        it for it in vs.items
        if not role_key or (it.get('role') or '').strip() == role_key
    ]
    if not candidates:
        candidates = list(vs.items)

    try:
        diff = int(difficulty or 3)
    except (TypeError, ValueError):
        diff = 3

    if diff >= 4 and len(candidates) > 8:
        pool = candidates[: max(8, len(candidates) // 2)]
    else:
        pool = candidates

    return random.choice(pool)


def _find_rag_item_by_id(item_id: str | None) -> dict | None:
    if not item_id:
        return None
    try:
        vs = _load_rag_store()
        for it in vs.items:
            if str(it.get('id') or '') == str(item_id):
                return it
    except Exception:
        pass
    return None


def _get_session_config(interview_id: str) -> dict:
    db_cfg: dict = {}
    conn = _db_conn()
    if conn:
        try:
            db_cfg = _load_interview_config(conn, interview_id)
        finally:
            conn.close()
    return _merge_session_config(interview_id, db_cfg)


def _build_role_from_text(text: str) -> str | None:
    t = (text or '').lower()
    if 'java' in t or '后端' in t:
        return 'Java后端'
    if '前端' in t or 'web' in t or 'vue' in t or 'react' in t:
        return 'Web前端'
    if 'python' in t or '算法' in t:
        return 'Python算法'
    return None


class CreateInterviewIn(BaseModel):
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    role: Optional[str] = None
    focus: Optional[str] = None
    mode: Optional[str] = 'practice'
    difficulty: Optional[int] = 3
    time_limit: Optional[int] = None
    use_resume: Optional[bool] = False
    resume_summary: Optional[str] = None
    resume_keywords: Optional[List[str]] = None
    seed_question_id: Optional[str] = None
    repo_url: Optional[str] = None
    enable_coding: Optional[bool] = None


class AnalyzeRepoIn(BaseModel):
    url: str


class CodeRunIn(BaseModel):
    code: str
    language: Optional[str] = 'python'
    stdin: Optional[str] = ''


class CodingChallengeIn(BaseModel):
    refresh: Optional[bool] = False


class CodeSubmitIn(BaseModel):
    code: str
    challenge: dict
    language: Optional[str] = 'python'
    stdin: Optional[str] = ''


class CodeTestIn(BaseModel):
    code: str
    language: Optional[str] = 'python'
    test_cases: Optional[List[dict]] = None


class ReportPatchIn(BaseModel):
    role: Optional[str] = None
    focus: Optional[str] = None
    mode: Optional[str] = None
    difficulty: Optional[int] = None
    time_limit: Optional[int] = None
    score: Optional[float] = None
    summary: Optional[str] = None


class OpeningOut(BaseModel):
    text: str
    role: Optional[str] = None
    question_title: Optional[str] = None
    question_id: Optional[str] = None
    rag_sourced: bool = False
    strategy: Optional[str] = 'standard'
    strategy_label: Optional[str] = '题库驱动'
    enable_coding: Optional[bool] = False


class CreateInterviewOut(BaseModel):
    id: str
    opening: Optional[OpeningOut] = None
    max_rounds: int = 5
    enable_coding: bool = False
    repo_analysis: Optional[dict] = None


@router.get('/capabilities')
async def interview_capabilities():
    runtimes = detect_runtimes()
    return {
        'llm': ai_service.use_openai,
        'speech_to_text': ai_service.transcription_available,
        'speech_browser_fallback': True,
        'code_runner': True,
        'repo_analyzer': True,
        'coding_runtimes': runtimes,
    }


@router.post('/analyze-repo')
async def analyze_repo_endpoint(payload: AnalyzeRepoIn):
    try:
        return analyze_git_repo((payload.url or '').strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'仓库分析失败：{e}')


@router.post('/', response_model=CreateInterviewOut)
async def create_interview(
    payload: CreateInterviewIn,
    authorization: Optional[str] = Header(default=None),
):
    interview_id = str(uuid.uuid4())
    user = optional_current_user(authorization)
    uid = user['id'] if user else _valid_uuid(payload.user_id)
    job_id = _valid_uuid(payload.job_id)

    max_rounds = _compute_core_rounds(payload.mode, payload.difficulty)

    resume_summary = (payload.resume_summary or '').strip()
    resume_keywords = list(payload.resume_keywords or [])
    use_resume = bool(payload.use_resume)

    conn = _db_conn()
    if conn and uid and use_resume and not resume_summary and not resume_keywords:
        stored = _load_user_resume(conn, uid)
        if stored:
            resume_summary = (stored.get('summary') or stored.get('text_content') or '')[:800]
            kw = stored.get('keywords')
            if isinstance(kw, list):
                resume_keywords = kw

    repo_analysis = None
    if (payload.repo_url or '').strip():
        try:
            repo_analysis = analyze_git_repo(payload.repo_url.strip())
        except Exception as e:
            repo_analysis = {'error': str(e), 'summary': ''}

    strategy = _resolve_interview_strategy(
        payload.mode,
        payload.focus,
        payload.difficulty,
        use_resume,
        resume_summary,
        resume_keywords,
        repo_analysis=repo_analysis,
        seed_question_id=payload.seed_question_id,
    )

    try:
        diff_n = int(payload.difficulty or 3)
    except (TypeError, ValueError):
        diff_n = 3
    enable_coding = payload.enable_coding
    if enable_coding is None:
        enable_coding = (payload.role or '') == 'Python算法' or diff_n >= 4

    opening_item = None
    opening_style = strategy.get('opening')
    if opening_style == 'seed':
        opening_item = _find_rag_item_by_id(payload.seed_question_id) or _pick_opening_from_rag(
            payload.role, payload.difficulty
        )
        opening_text = ai_service.generate_opening_message(
            title=(opening_item or {}).get('title') or '',
            body=(opening_item or {}).get('body') or '',
            role=payload.role,
            focus=payload.focus,
            mode=payload.mode,
            resume_keywords=resume_keywords or None,
        )
    elif opening_style == 'repo':
        opening_text = ai_service.generate_repo_opening_message(
            role=payload.role,
            focus=payload.focus,
            mode=payload.mode,
            difficulty=str(payload.difficulty) if payload.difficulty is not None else None,
            repo_analysis=repo_analysis,
            resume_keywords=resume_keywords,
        )
    elif opening_style == 'resume':
        opening_text = ai_service.generate_resume_opening_message(
            role=payload.role,
            focus=payload.focus,
            mode=payload.mode,
            difficulty=str(payload.difficulty) if payload.difficulty is not None else None,
            resume_summary=resume_summary,
            resume_keywords=resume_keywords,
        )
    else:
        opening_item = _pick_opening_from_rag(payload.role, payload.difficulty)
        opening_text = ai_service.generate_opening_message(
            title=(opening_item or {}).get('title') or '',
            body=(opening_item or {}).get('body') or '',
            role=payload.role,
            focus=payload.focus,
            mode=payload.mode,
            resume_keywords=resume_keywords or None,
        )

    opening_out = OpeningOut(
        text=opening_text,
        role=payload.role,
        question_title=(opening_item or {}).get('title'),
        question_id=(opening_item or {}).get('id'),
        rag_sourced=bool(opening_item),
        strategy=strategy.get('id'),
        strategy_label=strategy.get('label'),
        enable_coding=bool(enable_coding),
    )

    if conn:
        cur = conn.cursor()
        try:
            cur.execute(
                'INSERT INTO interviews (id, user_id, job_id, status, started_at) VALUES (%s, %s, %s, %s, now())',
                [interview_id, uid, job_id, 'in_progress'],
            )
            config = {
                'role': payload.role,
                'focus': payload.focus,
                'mode': payload.mode,
                'difficulty': payload.difficulty,
                'time_limit': payload.time_limit,
                'max_rounds': max_rounds,
                'opening_question_id': (opening_item or {}).get('id'),
                'strategy': strategy.get('id'),
                'strategy_label': strategy.get('label'),
                'use_resume': use_resume,
                'resume_summary': resume_summary[:800] if resume_summary else '',
                'resume_keywords': resume_keywords,
                'seed_question_id': payload.seed_question_id,
                'repo_url': (payload.repo_url or '').strip() or None,
                'repo_analysis': repo_analysis,
                'enable_coding': bool(enable_coding),
            }
            msg_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO interview_messages (id, interview_id, sender, role, content, parsed_json) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                [msg_id, interview_id, 'system', 'config', json.dumps(config, ensure_ascii=False), Json(config)],
            )
            ai_id = str(uuid.uuid4())
            opening_meta = {
                'question_id': (opening_item or {}).get('id'),
                'question_title': (opening_item or {}).get('title'),
                'rag_sourced': bool(opening_item),
                'strategy': strategy.get('id'),
                'strategy_label': strategy.get('label'),
            }
            cur.execute(
                'INSERT INTO interview_messages (id, interview_id, sender, role, content, parsed_json) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                [ai_id, interview_id, 'ai', payload.role, opening_text, Json(opening_meta)],
            )
            cur.execute(
                'INSERT INTO interview_rounds (interview_id, round_index, question_id) VALUES (%s, %s, NULL)',
                [interview_id, 0],
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    _save_session_config(interview_id, {
        'role': payload.role,
        'focus': payload.focus,
        'mode': payload.mode,
        'difficulty': payload.difficulty,
        'time_limit': payload.time_limit,
        'max_rounds': max_rounds,
        'opening_question_id': (opening_item or {}).get('id'),
        'strategy': strategy.get('id'),
        'strategy_label': strategy.get('label'),
        'use_resume': use_resume,
        'resume_summary': resume_summary[:800] if resume_summary else '',
        'resume_keywords': resume_keywords,
        'seed_question_id': payload.seed_question_id,
        'repo_url': (payload.repo_url or '').strip() or None,
        'repo_analysis': repo_analysis,
        'enable_coding': bool(enable_coding),
        'candidate_rounds': 0,
        'coding_prompted': False,
    })

    return {
        'id': interview_id,
        'opening': opening_out,
        'max_rounds': max_rounds,
        'enable_coding': bool(enable_coding),
        'repo_analysis': repo_analysis,
    }


@router.get('/')
async def list_interviews(
    authorization: Optional[str] = Header(default=None),
    user_id: Optional[str] = None,
):
    conn = _db_conn()
    if not conn:
        return []

    user = optional_current_user(authorization)
    uid = user['id'] if user else _valid_uuid(user_id)
    if not uid:
        return []

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            'SELECT id::text AS id, user_id::text AS user_id, job_id::text AS job_id, '
            'status, started_at, ended_at FROM interviews WHERE user_id = %s '
            'ORDER BY started_at DESC LIMIT 200',
            [uid],
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        cur.close()
        conn.close()


class AnswerIn(BaseModel):
    question_id: str
    answer_text: str


class EvaluateIn(BaseModel):
    transcript: Optional[str] = None
    role: Optional[str] = None
    focus: Optional[str] = None
    mode: Optional[str] = None
    difficulty: Optional[int] = None
    time_limit: Optional[int] = None
    messages: Optional[List[Any]] = None


@router.post('/{interview_id}/answers')
async def submit_answer(interview_id: str, payload: AnswerIn):
    emb = emb_service.embed_text(payload.answer_text)
    return {'interview_id': interview_id, 'question_id': payload.question_id, 'embedding_dim': len(emd)}


@router.websocket('/ws/interviews/{interview_id}')
async def interview_ws(websocket: WebSocket, interview_id: str):
    await websocket.accept()
    conn = _db_conn()
    cur = None
    session_config: dict = _merge_session_config(interview_id)
    if conn:
        try:
            cur = conn.cursor()
            db_cfg = _load_interview_config(conn, interview_id)
            session_config = _merge_session_config(interview_id, db_cfg)
        except Exception:
            conn.close()
            conn = None

    asked_rag_ids: set[str] = set()
    opening_qid = session_config.get('opening_question_id')
    if opening_qid:
        asked_rag_ids.add(str(opening_qid))

    try:
        while True:
            data = await websocket.receive_text()
            obj = json.loads(data)
            if obj.get('type') == 'user_message':
                content = obj.get('content', '')
                requested_role = obj.get('role') or session_config.get('role')
                focus = obj.get('focus') or session_config.get('focus')
                resume_summary = obj.get('resume_summary') or session_config.get('resume_summary')
                resume_keywords = obj.get('resume_keywords') or session_config.get('resume_keywords')
                difficulty = obj.get('difficulty') or session_config.get('difficulty')
                mode = obj.get('mode') or session_config.get('mode')
                time_limit = obj.get('time_limit') if obj.get('time_limit') is not None else session_config.get('time_limit')
                core_rounds = int(
                    session_config.get('max_rounds')
                    or _compute_core_rounds(mode, difficulty)
                )

                ws_overrides = {
                    'strategy': obj.get('strategy'),
                    'strategy_label': obj.get('strategy_label'),
                    'repo_analysis': obj.get('repo_analysis'),
                    'enable_coding': obj.get('enable_coding'),
                    'max_rounds': obj.get('max_rounds'),
                }
                session_config = _merge_session_config(interview_id, session_config, ws_overrides)

                msg_id = str(uuid.uuid4())
                emb = emb_service.embed_text(content)
                emb_literal = '[' + ','.join(str(float(x)) for x in emb) + ']'
                if conn and cur:
                    try:
                        cur.execute(
                            'INSERT INTO interview_messages (id, interview_id, sender, content, embedding) '
                            'VALUES (%s,%s,%s,%s,%s::vector)',
                            (msg_id, interview_id, 'candidate', content, emb_literal),
                        )
                        conn.commit()
                    except Exception:
                        conn.rollback()
                current_round = _bump_candidate_round(interview_id, conn)

                inferred_role = requested_role or _build_role_from_text(content)
                strategy_id = session_config.get('strategy', 'standard')
                phase = _resolve_interview_phase(current_round, core_rounds, strategy_id)
                effective_focus = focus
                if phase in ('resume', 'repo'):
                    effective_focus = focus or '项目实践'
                elif phase == 'bagu':
                    effective_focus = '技术深度'
                elif phase == 'project':
                    effective_focus = '项目实践'

                rag_chunks = []
                primary_rag_id = None
                extended_item = None
                try:
                    vs = _load_rag_store()
                    if vs.items and phase not in ('resume', 'repo'):
                        if phase == 'core':
                            top_k = _rag_top_k(difficulty)
                            r = vs.query(emb, role=inferred_role, top_k=top_k)
                            for x in r:
                                item = x.get('item', {})
                                if not primary_rag_id:
                                    primary_rag_id = item.get('id')
                                rag_chunks.append(
                                    f"题目:{item.get('title') or item.get('body')}\n"
                                    f"标准回答:{item.get('standard_answer', '')}\n"
                                    f"评分标准:{item.get('scoring', '')}"
                                )
                        else:
                            extended_item = _pick_extended_rag_item(inferred_role, phase, asked_rag_ids)
                            if extended_item:
                                primary_rag_id = extended_item.get('id')
                                rag_chunks.append(
                                    f"题目:{extended_item.get('title') or extended_item.get('body')}\n"
                                    f"标准回答:{extended_item.get('standard_answer', '')}\n"
                                    f"评分标准:{extended_item.get('scoring', '')}"
                                )
                except Exception:
                    rag_chunks = []

                if primary_rag_id:
                    asked_rag_ids.add(str(primary_rag_id))

                ctx_summary = resume_summary
                if phase == 'repo':
                    repo_sum = (session_config.get('repo_analysis') or {}).get('summary') or ''
                    if repo_sum:
                        ctx_summary = f"{resume_summary or ''}\n【Git仓库】{repo_sum}".strip()

                reply_text = ai_service.generate_interview_reply(
                    content,
                    role=inferred_role,
                    focus=effective_focus,
                    rag_chunks=rag_chunks,
                    resume_summary=ctx_summary,
                    resume_keywords=resume_keywords,
                    difficulty=str(difficulty) if difficulty is not None else None,
                    mode=mode,
                    time_limit=time_limit,
                    phase=phase,
                    core_rounds=core_rounds,
                    current_round=current_round,
                    extended_item=extended_item,
                )

                chunk_size = 40
                for i in range(0, len(reply_text), chunk_size):
                    chunk = reply_text[i:i + chunk_size]
                    await websocket.send_text(json.dumps({'type': 'ai_stream', 'chunk': chunk}))
                    await asyncio.sleep(0.06)

                ai_id = str(uuid.uuid4())
                emb_ai = emb_service.embed_text(reply_text)
                emb_ai_literal = '[' + ','.join(str(float(x)) for x in emb_ai) + ']'
                ai_meta = Json({
                    'round_index': current_round,
                    'max_rounds': core_rounds,
                    'core_rounds': core_rounds,
                    'phase': phase,
                    'strategy': strategy_id,
                    'rag_question_id': primary_rag_id,
                    'rag_context_count': len(rag_chunks),
                })
                if conn and cur:
                    try:
                        cur.execute(
                            'INSERT INTO interview_messages (id, interview_id, sender, role, content, embedding, parsed_json) '
                            'VALUES (%s,%s,%s,%s,%s,%s::vector,%s)',
                            (ai_id, interview_id, 'ai', inferred_role, reply_text, emb_ai_literal, ai_meta),
                        )
                        _record_round(cur, interview_id, current_round)
                        conn.commit()
                    except Exception:
                        conn.rollback()

                followups = ai_service.suggest_followups(content, phase=phase)

                coding_offer = None
                if _should_prompt_coding(session_config, current_round, phase):
                    challenge = ai_service.generate_coding_challenge(
                        role=session_config.get('role'),
                        difficulty=str(session_config.get('difficulty') or 3),
                        resume_keywords=session_config.get('resume_keywords'),
                        repo_analysis=session_config.get('repo_analysis'),
                        phase=phase,
                        recent_answer=content,
                    )
                    coding_offer = {'auto_open': True, 'challenge': challenge}
                    session_config['coding_prompted'] = True
                    _save_session_config(interview_id, {
                        'coding_prompted': True,
                        'pending_coding_challenge': challenge,
                    })

                await websocket.send_text(json.dumps({
                    'type': 'ai_done',
                    'text': reply_text,
                    'followups': followups,
                    'role': inferred_role,
                    'rag_context_count': len(rag_chunks),
                    'round_index': current_round,
                    'max_rounds': core_rounds,
                    'core_rounds': core_rounds,
                    'phase': phase,
                    'phase_label': _phase_label(phase),
                    'strategy': strategy_id,
                    'strategy_label': session_config.get('strategy_label'),
                    'round_limit_reached': False,
                    'coding_offer': coding_offer,
                }, ensure_ascii=False))

            elif obj.get('type') == 'ping':
                await websocket.send_text(json.dumps({'type': 'pong'}))

    except WebSocketDisconnect:
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


@router.post('/{interview_id}/coding/challenge')
async def get_coding_challenge(interview_id: str, payload: CodingChallengeIn | None = None):
    cfg = _get_session_config(interview_id)
    if not cfg.get('enable_coding'):
        raise HTTPException(status_code=400, detail='本场面试未启用代码实战')
    refresh = bool(payload.refresh) if payload else False
    pending = cfg.get('pending_coding_challenge')
    if not refresh and isinstance(pending, dict) and pending.get('title'):
        return pending
    excluded = [pending.get('title')] if isinstance(pending, dict) and pending.get('title') else []
    challenge = ai_service.generate_coding_challenge(
        role=cfg.get('role'),
        difficulty=str(cfg.get('difficulty') or 3),
        resume_keywords=cfg.get('resume_keywords'),
        repo_analysis=cfg.get('repo_analysis'),
        phase=cfg.get('phase'),
        exclude_titles=excluded if refresh else None,
    )
    _save_session_config(interview_id, {'pending_coding_challenge': challenge})
    return challenge


@router.post('/{interview_id}/coding/run')
async def run_interview_code(interview_id: str, payload: CodeRunIn):
    return run_code(payload.language or 'python', payload.code or '', payload.stdin or '')


@router.post('/{interview_id}/coding/test')
async def test_interview_code(interview_id: str, payload: CodeTestIn):
    cfg = _get_session_config(interview_id)
    if not cfg.get('enable_coding'):
        raise HTTPException(status_code=400, detail='本场面试未启用代码实战')
    return run_tests(payload.language or 'python', payload.code or '', payload.test_cases or [])


@router.post('/{interview_id}/coding/submit')
async def submit_interview_code(interview_id: str, payload: CodeSubmitIn):
    lang = payload.language or (payload.challenge or {}).get('language') or 'python'
    run_result = run_code(lang, payload.code or '', payload.stdin or '')
    evaluation = ai_service.evaluate_code_submission(
        payload.challenge or {},
        payload.code or '',
        run_result,
    )
    _save_session_config(interview_id, {'pending_coding_challenge': None})
    return {'run_result': run_result, 'evaluation': evaluation}


@router.post('/{interview_id}/followups')
async def generate_followups(interview_id: str, payload: dict):
    answer = payload.get('answer')
    if not answer:
        raise HTTPException(status_code=400, detail='answer required')
    suggestions = ai_service.suggest_followups(answer)
    return suggestions


@router.post('/{interview_id}/transcribe')
async def transcribe_audio(interview_id: str, file: UploadFile = File(...)):
    if not ai_service.transcription_available:
        raise HTTPException(
            status_code=503,
            detail={
                'code': 'SPEECH_NOT_CONFIGURED',
                'message': (
                    '语音转写需要配置 OPENAI_API_KEY。'
                    '请改用文字输入，或在项目根目录 .env.llm 中配置 API Key 后重启后端。'
                ),
            },
        )

    contents = await file.read()
    try:
        text = ai_service.transcribe_audio(contents, file.filename)
    except Exception as e:
        err = str(e)
        if 'SPEECH_NOT_CONFIGURED' in err:
            raise HTTPException(
                status_code=503,
                detail={
                    'code': 'SPEECH_NOT_CONFIGURED',
                    'message': err.split(':', 1)[-1].strip(),
                },
            )
        if 'SPEECH_ENDPOINT_NOT_FOUND' in err:
            raise HTTPException(
                status_code=503,
                detail={
                    'code': 'SPEECH_ENDPOINT_NOT_FOUND',
                    'message': err.split(':', 1)[-1].strip(),
                },
            )
        if 'SPEECH_AUTH_FAILED' in err:
            raise HTTPException(
                status_code=503,
                detail={
                    'code': 'SPEECH_AUTH_FAILED',
                    'message': err.split(':', 1)[-1].strip(),
                },
            )
        if err.startswith('SPEECH_'):
            raise HTTPException(
                status_code=503,
                detail={
                    'code': 'SPEECH_FAILED',
                    'message': err.split(':', 1)[-1].strip() if ':' in err else err,
                },
            )
        raise HTTPException(status_code=500, detail=f'transcription failed: {e}')

    conn = _db_conn()
    if conn:
        try:
            cur = conn.cursor()
            msg_id = str(uuid.uuid4())
            emb = emb_service.embed_text(text)
            emb_literal = '[' + ','.join(str(float(x)) for x in emb) + ']'
            cur.execute(
                'INSERT INTO interview_messages (id, interview_id, sender, content, embedding) '
                'VALUES (%s,%s,%s,%s,%s::vector)',
                (msg_id, interview_id, 'candidate', text, emb_literal),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

    return {'transcript': text}


@router.post('/{interview_id}/evaluate')
async def evaluate_interview(interview_id: str, payload: EvaluateIn | None = None):
    transcript = (payload.transcript or '') if payload else ''
    conn = _db_conn()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                'SELECT sender, content, created_at FROM interview_messages '
                'WHERE interview_id = %s AND sender IN (%s, %s) ORDER BY created_at ASC',
                [interview_id, 'candidate', 'ai'],
            )
            rows = cur.fetchall()
            parts = []
            for r in rows:
                parts.append(f"[{r['sender']}] {r['content']}")
            if parts:
                transcript = '\n'.join(parts)
            cur.close()
            conn.close()
        except Exception:
            if not transcript:
                transcript = ''

    eval_mode = payload.mode if payload else None
    eval_res = ai_service.evaluate_interview(transcript, mode=eval_mode)

    meta = {
        'role': payload.role if payload else None,
        'focus': payload.focus if payload else None,
        'mode': payload.mode if payload else None,
        'difficulty': payload.difficulty if payload else None,
        'time_limit': payload.time_limit if payload else None,
        'max_rounds': _compute_core_rounds(
            payload.mode if payload else None,
            payload.difficulty if payload else None,
        ) if payload else None,
        'transcript': payload.messages if payload and payload.messages else None,
    }
    report_payload = {**eval_res, '_meta': meta}

    conn = _db_conn()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            summary = f"score:{eval_res.get('score')}; strengths:{','.join(eval_res.get('strengths', []))}"
            emb = emb_service.embed_text(summary)
            emb_literal = '[' + ','.join(str(float(x)) for x in emb) + ']'
            cur.execute(
                'INSERT INTO reports (interview_id, generated_at, status, report_json, embedding) '
                'VALUES (%s, now(), %s, %s, %s::vector) RETURNING id',
                (interview_id, 'done', Json(report_payload), emb_literal),
            )
            row = cur.fetchone()
            cur.execute(
                'UPDATE interviews SET status = %s, ended_at = now() WHERE id = %s',
                ('ended', interview_id),
            )
            conn.commit()
            if row:
                eval_res['_report_id'] = str(row['id'])
            cur.close()
            conn.close()
        except Exception:
            pass

    return eval_res


@router.get('/reports')
async def list_reports(
    authorization: Optional[str] = Header(default=None),
    user_id: Optional[str] = None,
):
    conn = _db_conn()
    if not conn:
        return []

    user = optional_current_user(authorization)
    uid = user['id'] if user else _valid_uuid(user_id)
    if not uid:
        return []

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            'SELECT r.id, r.interview_id, r.generated_at, r.report_json '
            'FROM reports r JOIN interviews i ON i.id = r.interview_id '
            'WHERE i.user_id = %s ORDER BY r.generated_at DESC LIMIT 200',
            [uid],
        )
        rows = cur.fetchall()
        return [_serialize_report_row(dict(r)) for r in rows]
    except Exception:
        return []
    finally:
        cur.close()
        conn.close()


@router.patch('/reports/{report_id}')
async def update_report(
    report_id: str,
    payload: ReportPatchIn,
    authorization: Optional[str] = Header(default=None),
):
    rid = _valid_uuid(report_id)
    if not rid:
        raise HTTPException(status_code=400, detail='invalid report id')
    user = optional_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail='请先登录')
    conn = _db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail='数据库不可用')

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            'SELECT r.id, r.interview_id, r.generated_at, r.report_json '
            'FROM reports r JOIN interviews i ON i.id = r.interview_id '
            'WHERE r.id = %s AND i.user_id = %s',
            [rid, user['id']],
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='报告不存在')

        report_json = row.get('report_json') or {}
        if isinstance(report_json, str):
            report_json = json.loads(report_json)
        meta = report_json.get('_meta') or {}

        for key in ('role', 'focus', 'mode', 'difficulty', 'time_limit'):
            value = getattr(payload, key)
            if value is not None:
                meta[key] = value
        if payload.score is not None:
            report_json['score'] = max(0, min(100, float(payload.score)))
        if payload.summary is not None:
            report_json['summary'] = payload.summary
        report_json['_meta'] = meta

        cur.execute(
            'UPDATE reports SET report_json = %s WHERE id = %s RETURNING id, interview_id, generated_at, report_json',
            [Json(report_json), rid],
        )
        updated = cur.fetchone()
        conn.commit()
        return _serialize_report_row(dict(updated))
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.delete('/reports/{report_id}')
async def delete_report(
    report_id: str,
    authorization: Optional[str] = Header(default=None),
):
    rid = _valid_uuid(report_id)
    if not rid:
        raise HTTPException(status_code=400, detail='invalid report id')
    user = optional_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail='请先登录')
    conn = _db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail='数据库不可用')

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            'DELETE FROM reports r USING interviews i '
            'WHERE r.interview_id = i.id AND r.id = %s AND i.user_id = %s RETURNING r.id',
            [rid, user['id']],
        )
        deleted = cur.fetchone()
        if not deleted:
            raise HTTPException(status_code=404, detail='报告不存在')
        conn.commit()
        return {'deleted': True, 'id': str(deleted['id'])}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
