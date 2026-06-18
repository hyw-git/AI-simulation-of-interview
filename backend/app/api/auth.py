from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
import os
import time
import hashlib
import hmac
import secrets
import jwt
import re
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor, Json

router = APIRouter()

TOKEN_SECRET = os.getenv('AUTH_TOKEN_SECRET', 'dev-secret-change-me')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('AUTH_ACCESS_TOKEN_EXPIRE_SECONDS', '3600'))  # 1 hour
REFRESH_TOKEN_EXPIRE_SECONDS = int(os.getenv('AUTH_REFRESH_TOKEN_EXPIRE_SECONDS', '2592000'))  # 30 days
PBKDF2_ITERATIONS = 210000


def _db_conn():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise HTTPException(status_code=500, detail='DATABASE_URL 未配置')
    return psycopg2.connect(db_url)


def _normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def _hash_password(password: str) -> str:
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail='密码至少 6 位')
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}'


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iterations, salt, stored = password_hash.split('$', 3)
        if algo != 'pbkdf2_sha256':
            return False
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(dk.hex(), stored)
    except Exception:
        return False

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_access_token(user_id: str, email: str) -> str:
    payload = {
        'sub': str(user_id),
        'email': email,
        'iat': int(time.time()),
        'exp': int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, TOKEN_SECRET, algorithm='HS256')


def _verify_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, TOKEN_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='token 已过期')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail='无效 token')


def _hash_refresh_token(token: str) -> str:
    return hmac.new(TOKEN_SECRET.encode('utf-8'), token.encode('utf-8'), hashlib.sha256).hexdigest()


def _issue_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _resume_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    resume_dir = root / 'data' / 'resumes'
    resume_dir.mkdir(parents=True, exist_ok=True)
    return resume_dir


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r'[^a-zA-Z0-9._-]+', '_', name or 'resume')
    return safe[:120] or 'resume'


def _extract_text_from_upload(file_bytes: bytes, filename: str) -> str:
    suffix = (Path(filename).suffix or '').lower()
    if suffix in ('.txt', '.md'):
        try:
            return file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return file_bytes.decode('utf-8', errors='ignore')

    if suffix == '.pdf':
        from pdfminer.high_level import extract_text
        tmp_path = _resume_dir() / f'_tmp_{secrets.token_hex(8)}.pdf'
        tmp_path.write_bytes(file_bytes)
        try:
            return extract_text(str(tmp_path))
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    if suffix in ('.docx',):
        from docx import Document
        tmp_path = _resume_dir() / f'_tmp_{secrets.token_hex(8)}.docx'
        tmp_path.write_bytes(file_bytes)
        try:
            doc = Document(str(tmp_path))
            return '\n'.join(p.text for p in doc.paragraphs if p.text)
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    raise HTTPException(status_code=400, detail='不支持的简历格式，请上传 pdf/docx/txt')


def _analyze_resume(text: str) -> dict:
    clean = (text or '').strip()
    if not clean:
        return {'summary': '', 'keywords': []}

    summary = clean[:400]
    tokens = re.findall(r'[A-Za-z]{2,}|[\u4e00-\u9fff]{2,}', clean)
    stop = {
        'and','the','for','with','that','this','from','are','was','were','you','your','our','have','has','had','using','use',
        '项目','负责','参与','熟悉','掌握','能力','工作','经验','团队','开发','设计','实现','优化','系统','平台','技术','相关','具备'
    }
    freq = {}
    for t in tokens:
        k = t.lower() if t.isascii() else t
        if k in stop:
            continue
        freq[k] = freq.get(k, 0) + 1
    keywords = [k for k, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:12]]
    return {'summary': summary, 'keywords': keywords}


def _upsert_resume(cur, user_id: str, text: str, summary: str, keywords: list,
                   file_name: str | None = None, file_path: str | None = None) -> dict:
    cur.execute(
        'INSERT INTO user_resumes (user_id, text_content, summary, keywords, file_name, file_path, updated_at) '
        'VALUES (%s,%s,%s,%s,%s,%s, now()) '
        'ON CONFLICT (user_id) DO UPDATE SET '
        'text_content = EXCLUDED.text_content, summary = EXCLUDED.summary, keywords = EXCLUDED.keywords, '
        'file_name = COALESCE(EXCLUDED.file_name, user_resumes.file_name), '
        'file_path = COALESCE(EXCLUDED.file_path, user_resumes.file_path), updated_at = now() '
        'RETURNING user_id::text AS user_id, text_content, summary, keywords, file_name, file_path, updated_at',
        [user_id, text, summary, Json(keywords), file_name, file_path]
    )
    return dict(cur.fetchone())


def _get_resume(cur, user_id: str) -> dict | None:
    cur.execute(
        'SELECT user_id::text AS user_id, text_content, summary, keywords, file_name, file_path, updated_at '
        'FROM user_resumes WHERE user_id = %s',
        [user_id]
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail='缺少 Authorization')
    parts = authorization.split(' ', 1)
    if len(parts) != 2 or parts[0].lower() != 'bearer' or not parts[1].strip():
        raise HTTPException(status_code=401, detail='Authorization 格式错误')
    return parts[1].strip()


def _current_user(authorization: str | None) -> dict:
    token = _extract_bearer(authorization)
    payload = _verify_access_token(token)
    uid = payload.get('sub')
    if not uid:
        raise HTTPException(status_code=401, detail='token 缺少用户标识')

    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('SELECT id::text AS id, email, name, year, major, created_at FROM users WHERE id = %s', [uid])
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail='用户不存在')
        return dict(row)
    finally:
        cur.close()
        conn.close()


def optional_current_user(authorization: str | None) -> dict | None:
    """Return current user from Bearer token, or None if missing/invalid."""
    if not authorization:
        return None
    try:
        return _current_user(authorization)
    except HTTPException:
        return None

class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None
    year: int | None = None
    major: str | None = None

class RegisterOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    year: int | None = None
    major: str | None = None

@router.post('/register', response_model=RegisterOut)
async def register(payload: RegisterIn):
    email = _normalize_email(payload.email)
    password_hash = _hash_password(payload.password)

    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('SELECT id FROM users WHERE email = %s', [email])
        if cur.fetchone():
            raise HTTPException(status_code=409, detail='邮箱已注册')

        cur.execute(
            'INSERT INTO users (email, password_hash, name, year, major) VALUES (%s,%s,%s,%s,%s) '
            'RETURNING id::text AS id, email, name, year, major',
            [email, password_hash, payload.name, payload.year, payload.major]
        )
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        cur.close()
        conn.close()

class LoginIn(BaseModel):
    email: EmailStr
    password: str

@router.post('/login')
async def login(payload: LoginIn):
    email = _normalize_email(payload.email)

    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('SELECT id::text AS id, email, password_hash, name, year, major FROM users WHERE email = %s', [email])
        row = cur.fetchone()
        if not row or not _verify_password(payload.password, row['password_hash']):
            raise HTTPException(status_code=401, detail='invalid credentials')

        access_token = _issue_access_token(row['id'], row['email'])
        refresh_token = _issue_refresh_token()
        expires_at = _now() + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)

        cur.execute(
            'INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s,%s,%s)',
            [row['id'], _hash_refresh_token(refresh_token), expires_at]
        )
        conn.commit()
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'bearer',
            'user': {
                'id': row['id'],
                'email': row['email'],
                'name': row.get('name'),
                'year': row.get('year'),
                'major': row.get('major')
            }
        }
    finally:
        cur.close()
        conn.close()


class RefreshIn(BaseModel):
    refresh_token: str


@router.post('/refresh')
async def refresh_token(payload: RefreshIn):
    token_hash = _hash_refresh_token(payload.refresh_token)
    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            'SELECT id, user_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash = %s',
            [token_hash]
        )
        row = cur.fetchone()
        now = _now()
        if not row or row.get('revoked_at') or row.get('expires_at') <= now:
            raise HTTPException(status_code=401, detail='refresh token 无效')

        cur.execute(
            'SELECT id::text AS id, email, name, year, major FROM users WHERE id = %s',
            [row['user_id']]
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail='用户不存在')

        cur.execute('UPDATE refresh_tokens SET revoked_at = now() WHERE id = %s', [row['id']])
        new_refresh = _issue_refresh_token()
        new_expires_at = now + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)
        cur.execute(
            'INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES (%s,%s,%s)',
            [user['id'], _hash_refresh_token(new_refresh), new_expires_at]
        )
        conn.commit()

        access_token = _issue_access_token(user['id'], user['email'])
        return {
            'access_token': access_token,
            'refresh_token': new_refresh,
            'token_type': 'bearer'
        }
    finally:
        cur.close()
        conn.close()


class LogoutIn(BaseModel):
    refresh_token: str | None = None


@router.post('/logout')
async def logout_user(payload: LogoutIn):
    if not payload.refresh_token:
        return {'status': 'ok'}

    token_hash = _hash_refresh_token(payload.refresh_token)
    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = %s', [token_hash])
        conn.commit()
        return {'status': 'ok'}
    finally:
        cur.close()
        conn.close()


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


@router.post('/change_password')
async def change_password(payload: ChangePasswordIn, authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    new_hash = _hash_password(payload.new_password)

    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute('SELECT password_hash FROM users WHERE id = %s', [user['id']])
        row = cur.fetchone()
        if not row or not _verify_password(payload.old_password, row['password_hash']):
            raise HTTPException(status_code=400, detail='旧密码错误')

        cur.execute('UPDATE users SET password_hash = %s WHERE id = %s', [new_hash, user['id']])
        cur.execute('UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL', [user['id']])
        conn.commit()
        return {'status': 'ok'}
    finally:
        cur.close()
        conn.close()


@router.get('/me')
async def get_me(authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    return {
        'id': user['id'],
        'email': user['email'],
        'name': user.get('name'),
        'year': user.get('year'),
        'major': user.get('major'),
        'role': 'user'
    }


class UpdateMeIn(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    year: int | None = None
    major: str | None = None


@router.put('/me')
async def update_me(payload: UpdateMeIn, authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    new_email = _normalize_email(payload.email) if payload.email else user['email']
    new_name = payload.name if payload.name is not None else user.get('name')
    new_year = payload.year if payload.year is not None else user.get('year')
    new_major = payload.major if payload.major is not None else user.get('major')

    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if new_email != user['email']:
            cur.execute('SELECT id FROM users WHERE email = %s AND id <> %s', [new_email, user['id']])
            if cur.fetchone():
                raise HTTPException(status_code=409, detail='邮箱已被占用')

        cur.execute(
            'UPDATE users SET email = %s, name = %s, year = %s, major = %s WHERE id = %s '
            'RETURNING id::text AS id, email, name, year, major',
            [new_email, new_name, new_year, new_major, user['id']]
        )
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        cur.close()
        conn.close()


class ResumeTextIn(BaseModel):
    text: str


@router.get('/resume')
async def get_resume(authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _get_resume(cur, user['id'])
        if not row:
            return {'text': '', 'summary': '', 'keywords': [], 'file_name': None, 'updated_at': None}
        return {
            'text': row.get('text_content') or '',
            'summary': row.get('summary') or '',
            'keywords': row.get('keywords') or [],
            'file_name': row.get('file_name'),
            'updated_at': row.get('updated_at')
        }
    finally:
        cur.close()
        conn.close()


@router.put('/resume')
async def update_resume_text(payload: ResumeTextIn, authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    analysis = _analyze_resume(payload.text)
    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _upsert_resume(cur, user['id'], payload.text, analysis['summary'], analysis['keywords'])
        conn.commit()
        return {
            'text': row.get('text_content') or '',
            'summary': row.get('summary') or '',
            'keywords': row.get('keywords') or [],
            'file_name': row.get('file_name'),
            'updated_at': row.get('updated_at')
        }
    finally:
        cur.close()
        conn.close()


@router.post('/resume/upload')
async def upload_resume(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail='文件为空')

    text = _extract_text_from_upload(contents, file.filename or 'resume')
    analysis = _analyze_resume(text)

    safe_name = _sanitize_filename(file.filename or 'resume')
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    resume_dir = _resume_dir() / str(user['id'])
    resume_dir.mkdir(parents=True, exist_ok=True)
    stored_path = resume_dir / f'{stamp}_{safe_name}'
    stored_path.write_bytes(contents)

    conn = _db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        row = _upsert_resume(
            cur,
            user['id'],
            text,
            analysis['summary'],
            analysis['keywords'],
            file_name=file.filename,
            file_path=str(stored_path)
        )
        conn.commit()
        return {
            'text': row.get('text_content') or '',
            'summary': row.get('summary') or '',
            'keywords': row.get('keywords') or [],
            'file_name': row.get('file_name'),
            'updated_at': row.get('updated_at')
        }
    finally:
        cur.close()
        conn.close()

