"""本地代码运行：Python / Java / JavaScript，带超时与基础安全限制。"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

_PYTHON_BLOCKED = ('import os', 'import subprocess', 'import shutil', 'open(', '__import__', 'eval(', 'exec(')
_JAVA_BLOCKED = ('runtime.getruntime', 'processbuilder', 'java.io.file', 'files.write')
_JS_BLOCKED = ('child_process', 'require("fs")', "require('fs')", 'eval(')


def detect_runtimes() -> dict[str, bool]:
    return {
        'python': True,
        'java': bool(shutil.which('javac') and shutil.which('java')),
        'javascript': bool(shutil.which('node')),
    }


def _check_blocked(src: str, tokens: tuple[str, ...]) -> str | None:
    lowered = src.lower()
    for token in tokens:
        if token in lowered:
            return f'出于安全考虑，禁止使用：{token}'
    return None


def _normalize_output(text: str) -> str:
    return re.sub(r'\s+', '', (text or '').strip())


def _match_expected(actual: str, expected: str) -> bool:
    exp = (expected or '').strip()
    act = (actual or '').strip()
    if not exp:
        return bool(act)
    return _normalize_output(act) == _normalize_output(exp) or exp in act


def run_python(code: str, stdin: str = '', timeout: int = 5) -> dict:
    src = (code or '').strip()
    if not src:
        return _result('', '代码为空', 1, False, 'python')
    blocked = _check_blocked(src, _PYTHON_BLOCKED)
    if blocked:
        return _result('', blocked, 1, False, 'python')
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'main.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(src)
        return _exec_subprocess([sys.executable, path], stdin, timeout, tmp, 'python')


def _result(stdout: str, stderr: str, code: int, timed_out: bool, language: str) -> dict:
    return {
        'stdout': (stdout or '')[:8000],
        'stderr': (stderr or '')[:4000],
        'exit_code': code,
        'timed_out': timed_out,
        'language': language,
    }


def _exec_subprocess(cmd: list[str], stdin: str, timeout: int, cwd: str, language: str) -> dict:
    try:
        proc = subprocess.run(
            cmd,
            input=stdin or '',
            capture_output=True,
            text=True,
            timeout=max(1, min(timeout, 15)),
            cwd=cwd,
            env={'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''), 'PATH': os.environ.get('PATH', '')},
        )
        return _result(proc.stdout, proc.stderr, proc.returncode, False, language)
    except subprocess.TimeoutExpired:
        return _result('', f'运行超时（>{timeout}s）', -1, True, language)
    except Exception as e:
        return _result('', str(e), -1, False, language)


def _java_has_main(src: str) -> bool:
    return bool(re.search(r'public\s+static\s+void\s+main\s*\(', src))


def _compile_and_run_java(java_src: str, main_class: str, stdin: str = '', timeout: int = 8) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'Main.java')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(java_src)
        try:
            cp = subprocess.run(
                ['javac', '-encoding', 'UTF-8', path],
                capture_output=True,
                text=True,
                timeout=max(2, min(timeout, 12)),
                cwd=tmp,
            )
            if cp.returncode != 0:
                return _result(cp.stdout, cp.stderr or '编译失败', cp.returncode, False, 'java')
            return _exec_subprocess(['java', '-cp', tmp, main_class], stdin, timeout, tmp, 'java')
        except subprocess.TimeoutExpired:
            return _result('', f'运行超时（>{timeout}s）', -1, True, 'java')
        except Exception as e:
            return _result('', str(e), -1, False, 'java')


def run_java(code: str, stdin: str = '', timeout: int = 8) -> dict:
    src = (code or '').strip()
    if not src:
        return _result('', '代码为空', 1, False, 'java')
    if not detect_runtimes()['java']:
        return _result(
            '',
            '当前环境未安装 JDK（javac/java）。请重建 Docker 镜像（含 openjdk）或在本机安装 JDK 后重启后端。',
            1,
            False,
            'java',
        )
    blocked = _check_blocked(src, _JAVA_BLOCKED)
    if blocked:
        return _result('', blocked, 1, False, 'java')

    if _java_has_main(src):
        for cls in ('Solution', 'Main'):
            if re.search(rf'class\s+{cls}\b', src):
                return _compile_and_run_java(src, cls, stdin, timeout)
        return _compile_and_run_java(src, 'Solution', stdin, timeout)

    wrapped = (
        f'{src.rstrip()}\n\n'
        'class __Runner {\n'
        '    public static void main(String[] args) {\n'
        '        System.out.println("请实现 Solution 并包含 main，或使用「测试样例」验证。");\n'
        '    }\n'
        '}\n'
    )
    return _compile_and_run_java(wrapped, '__Runner', stdin, timeout)


def run_javascript(code: str, stdin: str = '', timeout: int = 5) -> dict:
    src = (code or '').strip()
    if not src:
        return _result('', '代码为空', 1, False, 'javascript')
    if not detect_runtimes()['javascript']:
        return _result(
            '',
            '当前环境未安装 Node.js。请重建 Docker 镜像（含 nodejs）或在本机安装 Node 后重启后端。',
            1,
            False,
            'javascript',
        )
    blocked = _check_blocked(src, _JS_BLOCKED)
    if blocked:
        return _result('', blocked, 1, False, 'javascript')

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'main.js')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(src)
        return _exec_subprocess(['node', path], stdin, timeout, tmp, 'javascript')


def run_code(language: str, code: str, stdin: str = '', timeout: int = 5) -> dict:
    lang = (language or 'python').strip().lower()
    if lang == 'java':
        return run_java(code, stdin, timeout=timeout + 3)
    if lang in ('javascript', 'js'):
        return run_javascript(code, stdin, timeout=timeout)
    return run_python(code, stdin, timeout=timeout)


def _snippet_for_lang(test_case: dict, language: str) -> str:
    lang = (language or 'python').strip().lower()
    snippets = test_case.get('snippets') or {}
    if isinstance(snippets, dict) and snippets.get(lang):
        return snippets[lang]
    if lang == 'java':
        return test_case.get('run_snippet_java') or ''
    if lang in ('javascript', 'js'):
        return test_case.get('run_snippet_js') or ''
    return test_case.get('run_snippet') or ''


def run_tests(language: str, code: str, test_cases: list | None, timeout: int = 5) -> dict:
    lang = (language or 'python').strip().lower()
    cases = list(test_cases or [])
    if not cases:
        return {'results': [], 'passed_count': 0, 'total': 0, 'message': '本题暂无自动测试用例，请使用「运行」手动验证。', 'language': lang}
    if not (code or '').strip():
        return {'results': [], 'passed_count': 0, 'total': len(cases), 'message': '代码为空', 'language': lang}

    results = []
    passed_count = 0
    for idx, tc in enumerate(cases):
        label = tc.get('label') or f'用例 {idx + 1}'
        snippet = _snippet_for_lang(tc, lang)
        expected = str(tc.get('expected', ''))
        if not snippet:
            results.append({'label': label, 'passed': False, 'expected': expected, 'actual': '', 'stderr': f'缺少 {lang} 测试片段'})
            continue

        if lang == 'java':
            java_src = (
                f'{code.rstrip()}\n\n'
                'class __AutoTest {\n'
                '    public static void main(String[] args) {\n'
                f'        {snippet.strip()}\n'
                '    }\n'
                '}\n'
            )
            run_result = _compile_and_run_java(java_src, '__AutoTest', '', timeout + 3)
        elif lang in ('javascript', 'js'):
            combined = f'{code.rstrip()}\n\n// --- auto test ---\n{snippet}\n'
            run_result = run_javascript(combined, '', timeout=timeout)
        else:
            combined = f'{code.rstrip()}\n\n# --- auto test ---\n{snippet}\n'
            run_result = run_python(combined, '', timeout=timeout)

        actual = (run_result.get('stdout') or '').strip()
        stderr = (run_result.get('stderr') or '').strip()
        ok = run_result.get('exit_code') == 0 and not stderr and _match_expected(actual, expected)
        if ok:
            passed_count += 1
        results.append({'label': label, 'passed': ok, 'expected': expected, 'actual': actual, 'stderr': stderr})

    return {
        'results': results,
        'passed_count': passed_count,
        'total': len(cases),
        'message': f'通过 {passed_count}/{len(cases)} 个样例',
        'language': lang,
    }
