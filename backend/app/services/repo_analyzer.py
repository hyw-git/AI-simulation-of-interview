"""轻量 Git 仓库分析：优先 GitHub API，用于面试前项目解读。"""
from __future__ import annotations

import base64
import os
import re
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_GITHUB_RE = re.compile(
    r'(?:https?://)?(?:www\.)?github\.com[:/](?P<owner>[^/\s#?]+)/(?P<repo>[^/\s#?.]+)',
    re.IGNORECASE,
)
_GITLAB_RE = re.compile(
    r'(?:https?://)?(?:www\.)?gitlab\.com[:/](?P<owner>[^/\s#?]+)/(?P<repo>[^/\s#?.]+)',
    re.IGNORECASE,
)

_NETWORK_HINT = (
    '无法稳定连接 GitHub（SSL/网络中断）。常见原因：国内网络访问 GitHub 不稳定、'
    'Docker 容器未走系统代理。可在 .env.llm 配置 HTTPS_PROXY=http://127.0.0.1:端口 '
    '（Windows 代理端口常见 7890/10809）后执行 docker compose up -d backend；'
    '或稍后重试、在宿主机用 VPN 后再试。'
)


def _github_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.6,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset(['GET']),
    )
    session.mount('https://', HTTPAdapter(max_retries=retry))
    session.mount('http://', HTTPAdapter(max_retries=retry))
    proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy') or os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
    if proxy:
        session.proxies.update({'http': proxy, 'https': proxy})
    return session


_SESSION = _github_session()


def parse_repo_url(url: str) -> dict | None:
    text = (url or '').strip()
    if not text:
        return None
    m = _GITHUB_RE.search(text)
    if m:
        return {'provider': 'github', 'owner': m.group('owner'), 'repo': m.group('repo').removesuffix('.git')}
    m = _GITLAB_RE.search(text)
    if m:
        return {'provider': 'gitlab', 'owner': m.group('owner'), 'repo': m.group('repo').removesuffix('.git')}
    return None


def _github_headers() -> dict[str, str]:
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ai-interview-platform'}
    token = os.getenv('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def _github_get(path: str, timeout: int = 15, retries: int = 3) -> Any:
    url = f'https://api.github.com{path}'
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = _SESSION.get(url, headers=_github_headers(), timeout=timeout)
            if resp.status_code == 404:
                return None
            if resp.status_code in (403, 429):
                token = os.getenv('GITHUB_TOKEN')
                if not token:
                    raise ValueError(
                        'GitHub API 请求频率超限。请在项目根目录 .env.llm 中配置 GITHUB_TOKEN 后执行 '
                        'docker compose up -d backend，或稍后再试。'
                    )
                raise ValueError(f'GitHub API 访问被拒绝（HTTP {resp.status_code}），请检查 GITHUB_TOKEN 是否有效。')
            resp.raise_for_status()
            return resp.json()
        except ValueError:
            raise
        except requests.RequestException as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(1.2 * (attempt + 1))
                continue
    raise last_err  # type: ignore[misc]


def _fetch_readme_raw(owner: str, repo: str) -> str:
    headers = {'User-Agent': 'ai-interview-platform'}
    for branch in ('main', 'master', 'develop'):
        for name in ('README.md', 'Readme.md', 'readme.md', 'README.MD'):
            raw_url = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{name}'
            try:
                resp = _SESSION.get(raw_url, headers=headers, timeout=12)
                if resp.ok and resp.text.strip():
                    return resp.text[:2500]
            except requests.RequestException:
                continue
    return ''


def _analyze_github_lite(owner: str, repo: str, reason: str = '') -> dict:
    readme = _fetch_readme_raw(owner, repo)
    if not readme:
        detail = f'{_NETWORK_HINT}'
        if reason:
            detail = f'{detail}（原始错误：{reason[:200]}）'
        raise ValueError(detail)
    summary = f'仓库 {owner}/{repo}；降级模式：API 不可用，已仅读取 README 摘要'
    return {
        'provider': 'github',
        'owner': owner,
        'repo': repo,
        'name': f'{owner}/{repo}',
        'description': '',
        'languages': [],
        'language_text': '未知（API 不可用）',
        'readme_excerpt': readme,
        'structure': [],
        'summary': summary[:1200],
        'url': f'https://github.com/{owner}/{repo}',
        'degraded': True,
    }


def _analyze_github(owner: str, repo: str) -> dict:
    try:
        meta = _github_get(f'/repos/{owner}/{repo}') or {}
        languages = _github_get(f'/repos/{owner}/{repo}/languages') or {}
        readme = ''
        readme_obj = _github_get(f'/repos/{owner}/{repo}/readme')
        if readme_obj and readme_obj.get('content'):
            try:
                readme = base64.b64decode(readme_obj['content']).decode('utf-8', errors='ignore')
            except Exception:
                readme = ''
        tree_items: list[str] = []
        tree = _github_get(f'/repos/{owner}/{repo}/git/trees/{meta.get("default_branch", "main")}?recursive=1')
        if tree and isinstance(tree.get('tree'), list):
            for node in tree['tree'][:200]:
                path = node.get('path') or ''
                if node.get('type') == 'tree' and path.count('/') <= 1:
                    tree_items.append(path + '/')
                elif node.get('type') == 'blob' and '/' not in path and len(tree_items) < 30:
                    tree_items.append(path)
        lang_sorted = sorted(languages.items(), key=lambda x: -x[1])
        lang_text = '、'.join(f'{k}({v})' for k, v in lang_sorted[:5]) or '未知'
        summary_parts = [
            f'仓库 {owner}/{repo}',
            meta.get('description') or '',
            f'主要语言：{lang_text}',
            f'Stars: {meta.get("stargazers_count", 0)}',
        ]
        if tree_items:
            summary_parts.append('根目录/顶层：' + '、'.join(tree_items[:12]))
        summary = '；'.join(p for p in summary_parts if p)
        return {
            'provider': 'github',
            'owner': owner,
            'repo': repo,
            'name': meta.get('full_name') or f'{owner}/{repo}',
            'description': meta.get('description') or '',
            'languages': lang_sorted[:8],
            'language_text': lang_text,
            'readme_excerpt': (readme or '')[:2500],
            'structure': tree_items[:20],
            'summary': summary[:1200],
            'url': meta.get('html_url') or f'https://github.com/{owner}/{repo}',
        }
    except requests.RequestException as exc:
        return _analyze_github_lite(owner, repo, reason=str(exc))


def analyze_repo(url: str) -> dict:
    """分析公开仓库，返回摘要供 AI 面试使用。"""
    parsed = parse_repo_url(url)
    if not parsed:
        raise ValueError('仅支持 GitHub / GitLab 公开仓库链接，格式如 https://github.com/owner/repo')

    if parsed['provider'] == 'github':
        return _analyze_github(parsed['owner'], parsed['repo'])

    owner, repo = parsed['owner'], parsed['repo']
    return {
        'provider': 'gitlab',
        'owner': owner,
        'repo': repo,
        'name': f'{owner}/{repo}',
        'description': '',
        'languages': [],
        'language_text': '未知',
        'readme_excerpt': '',
        'structure': [],
        'summary': f'GitLab 仓库 {owner}/{repo}（建议配置 GITHUB_TOKEN 或后续扩展 GitLab API）',
        'url': url.strip(),
    }
