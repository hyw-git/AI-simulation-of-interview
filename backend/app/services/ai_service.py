"""
AI service wrapper.

Usage:
- Set environment variable `OPENAI_API_KEY` to your OpenAI API key (or other model's key)
    for real model calls. Place it in a .env.llm or your environment. Example:

    OPENAI_API_KEY=sk-xxxx

  The code will fallback to a simple rule/template generator when no key is present.

Replace or extend this file to support other providers or streaming.
"""
import os
import json
import random
import re
import typing

import requests

from backend.app.services.code_runner import detect_runtimes

OPENAI_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'deepseek-chat')
OPENAI_WHISPER_API_KEY = os.getenv('OPENAI_WHISPER_API_KEY') or OPENAI_KEY
OPENAI_WHISPER_BASE_URL = (os.getenv('OPENAI_WHISPER_BASE_URL') or 'https://api.openai.com/v1').rstrip('/')
OPENAI_WHISPER_MODEL = os.getenv('OPENAI_WHISPER_MODEL', 'whisper-1')

INTERVIEW_SYSTEM_PROMPT = (
    "你是企业级校招/实习面试官，风格专业、友好、较严格。"
    "目标是通过多轮追问评估候选人的技术能力、表达能力、逻辑思维与项目实践。"
    "严格遵守以下规则："
    "1) 只输出1-2个追问，每个追问不超过一行；"
    "2) 追问必须基于候选人回答与提供的RAG上下文；"
    "3) 不给出完整答案，只提示方向或关键点；"
    "4) 若信息不足，先澄清再深入；"
    "5) 使用简体中文，口吻像真实面试官。"
)

try:
    import openai
    openai_available = True
    if OPENAI_KEY:
        openai.api_key = OPENAI_KEY
    if OPENAI_BASE_URL:
        openai.api_base = OPENAI_BASE_URL
except Exception:
    openai_available = False


class AIService:
    def __init__(self):
        self.use_openai = openai_available and bool(OPENAI_KEY)

    @property
    def transcription_available(self) -> bool:
        if not openai_available:
            return False
        whisper_key = os.getenv('OPENAI_WHISPER_API_KEY') or OPENAI_KEY
        if not whisper_key:
            return False
        # 聊天走 DeepSeek 等第三方时，默认 Whisper 不可用，除非单独配置 Whisper Key/Base
        if os.getenv('OPENAI_WHISPER_API_KEY') or os.getenv('OPENAI_WHISPER_BASE_URL'):
            return True
        if OPENAI_BASE_URL and 'openai.com' not in OPENAI_BASE_URL.lower():
            return False
        return True

    def _chat_completion(self, messages: list, max_tokens: int, temperature: float) -> str | None:
        model_name = OPENAI_MODEL if hasattr(openai, 'ChatCompletion') else 'deepseek-chat'
        resp = openai.ChatCompletion.create(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if isinstance(resp, dict) and resp.get('choices'):
            return resp['choices'][0]['message']['content']
        return None

    def generate_reply(self, prompt: str, context: typing.List[str] | None = None, system_prompt: str | None = None,
                       max_tokens: int = 512, temperature: float = 0.2) -> str:
        """Generate a reply given prompt and optional context. Returns final text (non-streaming).

        NOTE: For production you may want to stream tokens; this simple implementation
        returns the whole answer and the caller may stream it piecemeal.
        """
        full_prompt = ''
        if context:
            full_prompt += '\n'.join(context[-8:]) + '\n'
        full_prompt += prompt

        if self.use_openai:
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": full_prompt})
                text = self._chat_completion(messages, max_tokens=max_tokens, temperature=temperature)
                if text:
                    return text
            except Exception as e:
                return f"[AI service error: {e}]"

        return self._fallback_generator(prompt)

    def suggest_followups(self, answer: str, phase: str = 'core') -> typing.List[typing.Dict[str, str]]:
        """Return list of followup suggestion dicts: {text, intent}."""
        phase_hint = {
            'bagu': '当前为八股/基础原理拓展阶段，追问应偏底层机制与概念辨析。',
            'project': '当前为项目/工程实践拓展阶段，追问应偏落地细节、协作与线上问题。',
        }.get(phase or 'core', '')
        if self.use_openai:
            try:
                prompt = (
                    "请基于候选人回答生成三条简短追问（中文），分别聚焦技术细节、行为补充、动机。"
                    "每条不超过30字，返回 JSON 数组，每项包含 text 与 intent。回答只返回 JSON。\n"
                    f"{phase_hint}\n"
                    f"回答：{answer}"
                )
                text = self._chat_completion(
                    [{"role": "user", "content": prompt}],
                    max_tokens=200,
                    temperature=0.3,
                )
                import json
                return json.loads(text or '[]')
            except Exception:
                pass

        return self._fallback_followups(answer, phase=phase)

    def generate_opening_message(
        self,
        title: str,
        body: str,
        role: str | None = None,
        focus: str | None = None,
        mode: str | None = None,
        resume_keywords: typing.List[str] | None = None,
    ) -> str:
        role_text = role or '技术'
        focus_text = focus or '综合'
        mode_text = '测评' if mode == 'test' else '练习'

        if self.use_openai:
            try:
                kw = '、'.join((resume_keywords or [])[:5]) or '无'
                prompt = (
                    f"你是{role_text}岗位面试官，正在进行{mode_text}面试，考察重点：{focus_text}。\n"
                    f"候选人简历关键词：{kw}\n"
                    f"首题标题：{title}\n首题内容：{body}\n\n"
                    "请用简体中文输出开场白：先简短问候（1句），说明面试形式（1句），"
                    "然后原样抛出首题（保留题目要点），不要给出答案。总字数 80-160 字。"
                )
                text = self._chat_completion(
                    [{"role": "user", "content": prompt}],
                    max_tokens=280,
                    temperature=0.4,
                )
                if text:
                    return text.strip()
            except Exception:
                pass

        return self._fallback_opening(title, body, role_text, focus_text, mode_text, resume_keywords)

    def generate_resume_opening_message(
        self,
        role: str | None = None,
        focus: str | None = None,
        mode: str | None = None,
        difficulty: str | None = None,
        resume_summary: str | None = None,
        resume_keywords: typing.List[str] | None = None,
    ) -> str:
        """简历驱动开场：先基于简历提问，不从题库随机抽首题。"""
        role_text = role or '技术'
        focus_text = focus or '综合'
        mode_text = '测评' if mode == 'test' else '练习'
        diff_text = difficulty or '3'
        summary = (resume_summary or '').strip()[:600] or '（暂无摘要）'
        kw = '、'.join((resume_keywords or [])[:6]) or '暂无'

        if self.use_openai:
            try:
                prompt = (
                    f"你是{role_text}岗位面试官，正在进行{mode_text}面试，考察重点：{focus_text}，难度：{diff_text}/5。\n"
                    f"候选人简历摘要：{summary}\n"
                    f"简历关键词：{kw}\n\n"
                    "请用简体中文输出开场白（100-180字），严格遵守：\n"
                    "1) 简短问候并说明已阅读简历；\n"
                    "2) 点出 1-2 个简历中的项目/技能作为切入点；\n"
                    "3) 请候选人先做简短自我介绍，再重点讲一个与岗位最匹配的项目（背景、职责、技术栈、结果）；\n"
                    "4) 不要从题库抽题，不要出八股题，不要给答案。"
                )
                text = self._chat_completion(
                    [{"role": "user", "content": prompt}],
                    max_tokens=320,
                    temperature=0.45,
                )
                if text:
                    return text.strip()
            except Exception:
                pass

        return self._fallback_resume_opening(
            role_text, focus_text, mode_text, diff_text, resume_summary, resume_keywords
        )

    def generate_repo_opening_message(
        self,
        role: str | None = None,
        focus: str | None = None,
        mode: str | None = None,
        difficulty: str | None = None,
        repo_analysis: dict | None = None,
        resume_keywords: typing.List[str] | None = None,
    ) -> str:
        """仓库驱动开场：基于 Git 仓库摘要提问，不随机抽题库首题。"""
        role_text = role or '技术'
        focus_text = focus or '综合'
        mode_text = '测评' if mode == 'test' else '练习'
        repo = repo_analysis or {}
        summary = (repo.get('summary') or repo.get('description') or '')[:800]
        readme = (repo.get('readme_excerpt') or '')[:400]
        name = repo.get('name') or '该项目'
        langs = repo.get('language_text') or '未知'

        if self.use_openai:
            try:
                prompt = (
                    f"你是{role_text}岗位面试官，{mode_text}模式，考察重点：{focus_text}，难度：{difficulty or 3}/5。\n"
                    f"候选人提供的 Git 仓库：{name}\n仓库摘要：{summary}\nREADME 片段：{readme}\n技术栈：{langs}\n\n"
                    "请用简体中文输出开场白（120-200字）：\n"
                    "1) 说明已浏览仓库结构与 README；\n"
                    "2) 点出 1-2 个值得深挖的模块或技术点；\n"
                    "3) 请候选人介绍该项目的目标、个人贡献与核心架构；\n"
                    "4) 不要直接抛八股题库题，不要给答案。"
                )
                text = self._chat_completion(
                    [{"role": "user", "content": prompt}],
                    max_tokens=340,
                    temperature=0.45,
                )
                if text:
                    return text.strip()
            except Exception:
                pass

        return (
            f"你好，欢迎参加{role_text}岗位的{mode_text}面试。我已浏览你提供的仓库「{name}」（{langs}）。\n\n"
            f"请先介绍该项目的背景与你的职责，再说明核心架构与技术选型。"
            f"我会结合代码仓库结构继续追问实现细节与工程取舍。"
        )

    def _default_coding_language(self, role: str | None) -> str:
        role_key = (role or '').strip()
        if 'Java' in role_key:
            return 'java'
        if '前端' in role_key or 'Web' in role_key:
            return 'javascript'
        return 'python'

    def _coding_languages_for_role(self, role: str | None) -> list[dict]:
        runtimes = detect_runtimes()
        role_key = (role or '').strip()
        default_id = self._default_coding_language(role)

        def lang(id_: str, label: str) -> dict:
            return {
                'id': id_,
                'label': label,
                'runnable': bool(runtimes.get(id_)),
                'default': id_ == default_id,
            }

        if 'Java' in role_key:
            return [lang('java', 'Java'), lang('python', 'Python')]
        if '前端' in role_key or 'Web' in role_key:
            return [lang('javascript', 'JavaScript'), lang('python', 'Python')]
        if 'Python' in role_key or '算法' in role_key:
            return [lang('python', 'Python'), lang('java', 'Java'), lang('javascript', 'JavaScript')]
        return [lang('python', 'Python'), lang('java', 'Java'), lang('javascript', 'JavaScript')]

    def _coding_challenge_specs(self) -> dict:
        """各难度题目：含多语言模板与测试片段。"""
        return {
            1: {
                'title': '两数之和',
                'description': '给定整数数组 nums 和目标值 target，返回两数之和等于 target 的下标（恰好一组解）。',
                'starters': {
                    'python': 'def two_sum(nums, target):\n    # 返回 [i, j]\n    pass\n',
                    'java': (
                        'import java.util.Arrays;\n\n'
                        'class Solution {\n'
                        '    public int[] twoSum(int[] nums, int target) {\n'
                        '        // 返回下标数组\n'
                        '        return new int[0];\n'
                        '    }\n\n'
                        '    public static void main(String[] args) {\n'
                        '        Solution s = new Solution();\n'
                        '        System.out.println(Arrays.toString(s.twoSum(new int[]{2, 7, 11, 15}, 9)));\n'
                        '    }\n'
                        '}\n'
                    ),
                    'javascript': (
                        'function twoSum(nums, target) {\n'
                        '  // 返回下标数组\n'
                        '  return [];\n'
                        '}\n\n'
                        'console.log(JSON.stringify(twoSum([2, 7, 11, 15], 9)));\n'
                    ),
                },
                'test_cases': [
                    {
                        'label': '样例 1',
                        'expected': '[0, 1]',
                        'snippets': {
                            'python': 'print(two_sum([2,7,11,15], 9))',
                            'java': 'Solution s = new Solution(); System.out.println(java.util.Arrays.toString(s.twoSum(new int[]{2,7,11,15}, 9)));',
                            'javascript': 'console.log(JSON.stringify(twoSum([2,7,11,15], 9)));',
                        },
                    },
                ],
            },
            2: {
                'title': '有效括号',
                'description': '给定只包含 ()[]{} 的字符串，判断括号是否有效匹配。',
                'starters': {
                    'python': 'def is_valid(s: str) -> bool:\n    pass\n',
                    'java': (
                        'class Solution {\n'
                        '    public boolean isValid(String s) {\n'
                        '        return false;\n'
                        '    }\n\n'
                        '    public static void main(String[] args) {\n'
                        '        Solution sol = new Solution();\n'
                        '        System.out.println(sol.isValid("()[]{}"));\n'
                        '    }\n'
                        '}\n'
                    ),
                    'javascript': (
                        'function isValid(s) {\n'
                        '  return false;\n'
                        '}\n\n'
                        'console.log(isValid("()[]{}"));\n'
                    ),
                },
                'test_cases': [
                    {
                        'label': '样例 1',
                        'expected': 'True',
                        'snippets': {
                            'python': 'print(is_valid("()[]{}"))',
                            'java': 'Solution sol = new Solution(); System.out.println(sol.isValid("()[]{}"));',
                            'javascript': 'console.log(isValid("()[]{}"));',
                        },
                    },
                    {
                        'label': '样例 2',
                        'expected': 'False',
                        'snippets': {
                            'python': 'print(is_valid("(]"))',
                            'java': 'Solution sol = new Solution(); System.out.println(sol.isValid("(]"));',
                            'javascript': 'console.log(isValid("(]"));',
                        },
                    },
                ],
            },
            3: {
                'title': 'LRU 缓存',
                'description': '设计 LRU 缓存，实现 get/put，要求均摊 O(1)。可先实现核心逻辑。',
                'starters': {
                    'python': (
                        'class LRUCache:\n'
                        '    def __init__(self, capacity: int):\n'
                        '        pass\n'
                        '    def get(self, key: int) -> int:\n'
                        '        pass\n'
                        '    def put(self, key: int, value: int) -> None:\n'
                        '        pass\n'
                    ),
                    'java': (
                        'class LRUCache {\n'
                        '    public LRUCache(int capacity) {}\n'
                        '    public int get(int key) { return -1; }\n'
                        '    public void put(int key, int value) {}\n'
                        '}\n'
                    ),
                    'javascript': (
                        'class LRUCache {\n'
                        '  constructor(capacity) {}\n'
                        '  get(key) { return -1; }\n'
                        '  put(key, value) {}\n'
                        '}\n'
                    ),
                },
                'test_cases': [],
            },
            4: {
                'title': '合并区间',
                'description': '给定区间列表 intervals，合并所有重叠区间并返回结果。',
                'starters': {
                    'python': 'def merge(intervals):\n    pass\n',
                    'java': (
                        'import java.util.Arrays;\n\n'
                        'class Solution {\n'
                        '    public int[][] merge(int[][] intervals) {\n'
                        '        return new int[0][0];\n'
                        '    }\n\n'
                        '    public static void main(String[] args) {\n'
                        '        Solution s = new Solution();\n'
                        '        System.out.println(Arrays.deepToString(s.merge(new int[][]{{1,3},{2,6},{8,10},{15,18}})));\n'
                        '    }\n'
                        '}\n'
                    ),
                    'javascript': (
                        'function merge(intervals) {\n'
                        '  return [];\n'
                        '}\n\n'
                        'console.log(JSON.stringify(merge([[1,3],[2,6],[8,10],[15,18]])));\n'
                    ),
                },
                'test_cases': [
                    {
                        'label': '样例 1',
                        'expected': '[[1, 6], [8, 10], [15, 18]]',
                        'snippets': {
                            'python': 'print(merge([[1,3],[2,6],[8,10],[15,18]]))',
                            'java': 'Solution s = new Solution(); System.out.println(java.util.Arrays.deepToString(s.merge(new int[][]{{1,3},{2,6},{8,10},{15,18}})));',
                            'javascript': 'console.log(JSON.stringify(merge([[1,3],[2,6],[8,10],[15,18]])));',
                        },
                    },
                ],
            },
            5: {
                'title': '单源最短路',
                'description': '在带权有向图中求单源最短路（无负权环），返回距离数组。',
                'starters': {
                    'python': 'def shortest_path(n, edges, src):\n    pass\n',
                    'java': (
                        'import java.util.Arrays;\n\n'
                        'class Solution {\n'
                        '    public int[] shortestPath(int n, int[][] edges, int src) {\n'
                        '        return new int[n];\n'
                        '    }\n'
                        '}\n'
                    ),
                    'javascript': 'function shortestPath(n, edges, src) {\n  return Array(n).fill(Infinity);\n}\n',
                },
                'test_cases': [],
            },
        }

    def generate_coding_challenge(
        self,
        role: str | None = None,
        difficulty: str | None = None,
        resume_keywords: typing.List[str] | None = None,
        repo_analysis: dict | None = None,
        phase: str | None = None,
        recent_answer: str | None = None,
        exclude_titles: typing.List[str] | None = None,
    ) -> dict:
        """生成算法/代码实战题（侧栏手敲）。"""
        diff = 3
        try:
            diff = int(difficulty or 3)
        except (TypeError, ValueError):
            pass
        kw_hint = (resume_keywords or [''])[0]
        repo_name = (repo_analysis or {}).get('name') or ''
        langs = (repo_analysis or {}).get('language_text') or ''

        specs = self._coding_challenge_specs()
        level = min(5, max(1, diff))
        excluded = {str(t).strip() for t in (exclude_titles or []) if str(t).strip()}
        if excluded:
            candidates = [
                (lv, sp) for lv, sp in specs.items()
                if sp.get('title') not in excluded and abs(lv - level) <= 2
            ] or [
                (lv, sp) for lv, sp in specs.items()
                if sp.get('title') not in excluded
            ]
            if candidates:
                level, spec = random.choice(candidates)
            else:
                spec = specs.get(level, specs[3])
        else:
            spec = specs.get(level, specs[3])
        body = spec['description']
        if repo_name and phase == 'repo':
            body += f'\n\n结合你刚才介绍的仓库「{repo_name}」：请思考其中{langs or "核心模块"}相关的数据结构与算法取舍。'
        elif repo_name and diff >= 3:
            body += f'\n\n（可与仓库「{repo_name}」中的实际场景结合思考）'
        if kw_hint:
            body += f'\n（提示：可联系项目中的「{kw_hint}」）'
        if recent_answer and len((recent_answer or '').strip()) > 20:
            body += '\n\n请基于你上一轮的表述，给出可运行的核心实现思路。'

        languages = self._coding_languages_for_role(role)
        default_lang = self._default_coding_language(role)
        starters = dict(spec.get('starters') or {})
        if default_lang not in starters and starters:
            default_lang = next(iter(starters.keys()))

        return {
            'title': spec['title'],
            'description': body,
            'language': default_lang,
            'languages': languages,
            'starter_code': starters.get(default_lang, ''),
            'starter_codes': starters,
            'test_cases': spec.get('test_cases') or [],
            'difficulty': level,
        }

    def evaluate_code_submission(
        self,
        challenge: dict,
        code: str,
        run_result: dict | None = None,
    ) -> dict:
        """对代码提交给出简短点评。"""
        stdout = (run_result or {}).get('stdout', '')
        stderr = (run_result or {}).get('stderr', '')
        exit_code = (run_result or {}).get('exit_code', 1)
        passed = exit_code == 0 and not stderr.strip()

        if self.use_openai:
            try:
                prompt = (
                    f"题目：{challenge.get('title')}\n描述：{challenge.get('description')}\n"
                    f"候选人代码：\n{code[:3000]}\n"
                    f"运行结果 stdout={stdout[:500]} stderr={stderr[:500]} exit={exit_code}\n"
                    "请用 JSON 返回：{\"passed\":bool,\"score\":0-100,\"feedback\":string,\"hints\":[string]}"
                )
                text = self._chat_completion(
                    [{"role": "user", "content": prompt}],
                    max_tokens=280,
                    temperature=0.2,
                )
                import json
                return json.loads(text or '{}')
            except Exception:
                pass

        score = 75 if passed else (40 if code.strip() else 0)
        feedback = '代码可运行，逻辑基本正确，可继续优化边界与复杂度。' if passed else (
            f'运行未通过：{stderr[:120] or "请检查语法与逻辑"}'
        )
        return {
            'passed': passed,
            'score': score,
            'feedback': feedback,
            'hints': ['考虑边界用例', '说明时间/空间复杂度'],
        }

    def transcribe_audio(self, file_bytes: bytes, filename: str = "audio.wav") -> str:
        """使用 OpenAI Whisper API 转写（独立于聊天 LLM 的 Base URL）。"""
        if not self.transcription_available:
            raise RuntimeError(
                'SPEECH_NOT_CONFIGURED: 语音转写需要 OpenAI Whisper。'
                '若聊天使用 DeepSeek 等第三方，请在 .env.llm 额外配置 '
                'OPENAI_WHISPER_API_KEY 与 OPENAI_WHISPER_BASE_URL=https://api.openai.com/v1'
            )

        whisper_key = os.getenv('OPENAI_WHISPER_API_KEY') or OPENAI_KEY
        url = f'{OPENAI_WHISPER_BASE_URL}/audio/transcriptions'
        mime = 'audio/wav'
        lower = (filename or '').lower()
        if lower.endswith('.webm'):
            mime = 'audio/webm'
        elif lower.endswith('.mp3'):
            mime = 'audio/mpeg'
        elif lower.endswith('.m4a'):
            mime = 'audio/mp4'
        elif lower.endswith('.ogg'):
            mime = 'audio/ogg'

        try:
            resp = requests.post(
                url,
                headers={'Authorization': f'Bearer {whisper_key}'},
                files={'file': (filename or 'audio.wav', file_bytes, mime)},
                data={'model': OPENAI_WHISPER_MODEL},
                timeout=90,
            )
            if resp.status_code == 404:
                raise RuntimeError(
                    'SPEECH_ENDPOINT_NOT_FOUND: 语音转写接口返回 404。'
                    '当前 OPENAI_BASE_URL 可能不支持 Whisper（如 DeepSeek）。'
                    '请在 .env.llm 配置 OPENAI_WHISPER_API_KEY（OpenAI Key）'
                    '和 OPENAI_WHISPER_BASE_URL=https://api.openai.com/v1 后重启后端。'
                )
            if resp.status_code == 401:
                raise RuntimeError('SPEECH_AUTH_FAILED: Whisper API Key 无效或已过期，请检查 OPENAI_WHISPER_API_KEY。')
            resp.raise_for_status()
            data = resp.json()
            text = (data.get('text') or '').strip()
            if not text:
                raise RuntimeError('SPEECH_EMPTY: 未识别到语音内容，请重试或改用文字输入。')
            return text
        except RuntimeError:
            raise
        except requests.RequestException as e:
            raise RuntimeError(f'SPEECH_REQUEST_FAILED: 语音转写请求失败：{e}') from e
        except Exception as e:
            raise RuntimeError(f'SPEECH_FAILED: {e}') from e

    def evaluate_interview(self, transcript: str, mode: str | None = None) -> dict:
        """Return an evaluation dict with score(0-100), strengths, weaknesses, suggestions.

        Tries to use the model to produce a JSON object. Falls back to a simple heuristic.
        mode='test' 时兜底评分略严格。
        """
        if self.use_openai:
            try:
                prompt = (
                    "请基于下面的面试记录给出结构化评估。评分维度权重：技术深度30%，问题分析20%，表达清晰20%，工程实践20%，学习潜力10%。"
                    "请严格按候选人的实际回答打分，不要默认给高分。分数标尺："
                    "0-39=几乎未回答或严重跑题；40-59=内容浅、缺少有效细节；60-74=基本合格但深度不足；"
                    "75-84=较好，有清晰思路和部分细节；85-92=优秀，有充分证据、取舍和工程结果；93-100=非常罕见。"
                    "综合分必须由五个维度加权得到，若证据不足应低于70分。"
                    "80分以上必须同时满足：回答覆盖多轮核心问题、有具体实现细节、有问题分析或技术取舍、有项目结果或验证证据。"
                    "若候选人只是泛泛而谈、重复概念或主要是面试官在输出内容，综合分应在40-65之间。"
                    "输出严格的 JSON（不要额外文本）："
                    "{"
                    "\"score\":number,"
                    "\"weights\":{\"technical_depth\":0.3,\"problem_solving\":0.2,\"communication\":0.2,\"engineering\":0.2,\"potential\":0.1},"
                    "\"dimensions\":{"
                    "\"technical_depth\":{\"score\":number,\"evidence\":[...],\"risks\":[...],\"suggestions\":[...]},"
                    "\"problem_solving\":{\"score\":number,\"evidence\":[...],\"risks\":[...],\"suggestions\":[...]},"
                    "\"communication\":{\"score\":number,\"evidence\":[...],\"risks\":[...],\"suggestions\":[...]},"
                    "\"engineering\":{\"score\":number,\"evidence\":[...],\"risks\":[...],\"suggestions\":[...]},"
                    "\"potential\":{\"score\":number,\"evidence\":[...],\"risks\":[...],\"suggestions\":[...]}"
                    "},"
                    "\"strengths\":[...],"
                    "\"weaknesses\":[...],"
                    "\"suggestions\":[...],"
                    "\"summary\":string"
                    "}。"
                    "\n面试记录：\n" + transcript
                )
                text = self._chat_completion(
                    [{"role": "user", "content": prompt}],
                    max_tokens=900,
                    temperature=0.2,
                )
                parsed = self._parse_json_object(text or '')
                return self._normalize_evaluation(parsed, source='ai', transcript=transcript)
            except Exception:
                pass

        return self._fallback_evaluation(transcript, mode=mode)

    def _parse_json_object(self, text: str) -> dict:
        raw = (text or '').strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            start = raw.find('{')
            end = raw.rfind('}')
            if start >= 0 and end > start:
                obj = json.loads(raw[start:end + 1])
                return obj if isinstance(obj, dict) else {}
            raise

    def _candidate_response_profile(self, transcript: str) -> dict:
        txt = transcript or ''
        candidate_parts = []
        for line in txt.splitlines():
            stripped = line.strip()
            if stripped.startswith('[candidate]') or stripped.startswith('[user]'):
                candidate_parts.append(re.sub(r'^\[(candidate|user)\]\s*', '', stripped))
        candidate_txt = '\n'.join(candidate_parts).strip() or txt
        answer_count = len([p for p in candidate_parts if p.strip()]) or (1 if candidate_txt else 0)

        def count_hits(kws: list[str]) -> int:
            return sum(1 for k in kws if k in candidate_txt)

        tech_kw = ['原理', '设计', '实现', '算法', '架构', '性能', '优化']
        solve_kw = ['分析', '定位', '排查', '权衡', '方案', '取舍']
        comm_kw = ['条理', '表达', '沟通', '总结', '说明']
        eng_kw = ['项目', '工程', '测试', '部署', '监控', '上线']
        pot_kw = ['学习', '复盘', '改进', '成长', '好奇']
        depth_kw = ['复杂度', '源码', '瓶颈', '边界', '数据', '指标', '对比', '方案']
        structure_kw = ['首先', '其次', '最后', '第一', '第二', '因为', '所以']

        return {
            'text': candidate_txt,
            'length': len(candidate_txt),
            'answer_count': answer_count,
            'tech_hits': count_hits(tech_kw),
            'solve_hits': count_hits(solve_kw),
            'comm_hits': count_hits(comm_kw),
            'eng_hits': count_hits(eng_kw),
            'pot_hits': count_hits(pot_kw),
            'depth_hits': count_hits(depth_kw),
            'structure_hits': count_hits(structure_kw),
        }

    def _score_cap_from_profile(self, profile: dict) -> int:
        length = int(profile.get('length') or 0)
        answer_count = int(profile.get('answer_count') or 0)
        evidence_hits = (
            int(profile.get('tech_hits') or 0)
            + int(profile.get('solve_hits') or 0)
            + int(profile.get('eng_hits') or 0)
            + int(profile.get('depth_hits') or 0)
        )
        if length <= 0:
            return 0
        if length < 80:
            return 35
        if length < 200:
            return 50
        if length < 400:
            return 62
        if length < 800:
            return 72
        if length < 1400:
            cap = 78
        else:
            cap = 84
        if answer_count >= 4 and evidence_hits >= 8:
            cap += 4
        if answer_count >= 5 and evidence_hits >= 12 and int(profile.get('depth_hits') or 0) >= 3:
            cap += 4
        return min(92, cap)

    def _normalize_evaluation(self, data: dict, source: str, transcript: str = '') -> dict:
        weights = data.get('weights') or {
            "technical_depth": 0.3,
            "problem_solving": 0.2,
            "communication": 0.2,
            "engineering": 0.2,
            "potential": 0.1
        }
        dims = data.get('dimensions') or {}

        def clamp_score(v, default=0) -> int:
            try:
                return max(0, min(100, int(round(float(v)))))
            except (TypeError, ValueError):
                return default

        dim_keys = ("technical_depth", "problem_solving", "communication", "engineering", "potential")
        normalized_dims = {}
        for key in dim_keys:
            block = dims.get(key) if isinstance(dims, dict) else {}
            if not isinstance(block, dict):
                block = {}
            normalized_dims[key] = {
                "score": clamp_score(block.get('score')),
                "evidence": list(block.get('evidence') or [])[:3],
                "risks": list(block.get('risks') or [])[:3],
                "suggestions": list(block.get('suggestions') or [])[:3],
            }
        weighted = sum(normalized_dims[k]["score"] * float(weights.get(k, 0)) for k in dim_keys)
        raw_score = data.get('score')
        score = clamp_score(raw_score, default=int(round(weighted)))
        if source == 'ai' and any(normalized_dims[k]["score"] for k in dim_keys):
            score = clamp_score(weighted)
        if transcript:
            cap = self._score_cap_from_profile(self._candidate_response_profile(transcript))
            score = min(score, cap)
            for key in dim_keys:
                normalized_dims[key]["score"] = min(normalized_dims[key]["score"], cap + 4)
        return {
            "score": score,
            "weights": weights,
            "dimensions": normalized_dims,
            "strengths": list(data.get('strengths') or [])[:3],
            "weaknesses": list(data.get('weaknesses') or [])[:3],
            "suggestions": list(data.get('suggestions') or [])[:3],
            "summary": data.get('summary') or '',
            "evaluation_source": source,
        }

    def generate_interview_reply(
        self,
        answer_text: str,
        role: str | None = None,
        focus: str | None = None,
        rag_chunks: typing.List[str] | None = None,
        resume_summary: str | None = None,
        resume_keywords: typing.List[str] | None = None,
        difficulty: str | None = None,
        mode: str | None = None,
        time_limit: int | None = None,
        phase: str = 'core',
        core_rounds: int | None = None,
        current_round: int | None = None,
        extended_item: dict | None = None,
    ) -> str:
        focus_text = focus or '综合'
        rag_text = '\n\n'.join(rag_chunks or []) or '无'
        resume_text = resume_summary or '无'
        keyword_text = '、'.join(resume_keywords or []) or '无'
        diff_text = difficulty or '3'
        mode_text = mode or 'practice'
        time_text = f"{time_limit} 分钟" if time_limit else '不限'
        phase_text = phase or 'core'
        phase_instructions = {
            'resume': (
                '当前为简历驱动核心阶段。请基于候选人简历与上一轮回答追问，'
                '聚焦项目背景、个人职责、技术选型、难点与量化结果。'
                '不要随机抛出题库新题；难度越高追问越深（可触及原理与取舍）。'
            ),
            'repo': (
                '当前为 Git 仓库驱动核心阶段。请结合仓库结构、README 与候选人回答追问，'
                '关注架构模块、关键代码路径、工程实践与线上问题。不要随机抛题库新题。'
            ),
            'core': '当前为核心追问阶段，请基于候选人回答做 1-2 条深入追问。',
            'bagu': (
                '核心追问阶段已结束。请切换到八股/基础原理方向：'
                '从 RAG 参考中选题或换角度，考察底层机制、概念辨析与常见考点。'
                '若本轮是拓展首题，先用一句话说明阶段切换，再给出新题。'
            ),
            'project': (
                '请从项目与工程实践方向继续：'
                '结合 RAG 参考考察落地细节、架构取舍、协作流程、线上问题与优化。'
                '可换一道未问过的项目相关题。'
            ),
        }
        phase_instruction = phase_instructions.get(phase_text, phase_instructions['core'])
        prompt = (
            f"岗位: {role or '通用'}\n"
            f"关注重点: {focus_text}\n"
            f"面试模式: {mode_text}\n"
            f"难度等级: {diff_text}\n"
            f"时间限制: {time_text}\n"
            f"面试阶段: {phase_text}\n"
            f"核心轮次: {core_rounds or '未知'}，当前第 {current_round or '未知'} 轮\n"
            f"候选人简历摘要: {resume_text}\n"
            f"简历关键词: {keyword_text}\n"
            f"候选人回答: {answer_text}\n"
            f"RAG参考内容:\n{rag_text}\n\n"
            f"{phase_instruction}"
        )
        if self.use_openai:
            return self.generate_reply(prompt, system_prompt=INTERVIEW_SYSTEM_PROMPT, max_tokens=300, temperature=0.3)
        return self._fallback_interview_reply(
            answer_text,
            role,
            focus,
            rag_chunks,
            resume_keywords,
            difficulty,
            phase=phase_text,
            core_rounds=core_rounds,
            current_round=current_round,
            extended_item=extended_item,
        )

    def _extract_rag_title(self, rag_chunks: typing.List[str] | None) -> str:
        if not rag_chunks:
            return ''
        first = rag_chunks[0]
        for line in first.split('\n'):
            if line.startswith('题目:'):
                return line.replace('题目:', '').strip()
        return ''

    def _fallback_opening(
        self,
        title: str,
        body: str,
        role: str,
        focus: str,
        mode_text: str,
        resume_keywords: typing.List[str] | None,
    ) -> str:
        greeting = f"你好，欢迎参加{role}岗位的{mode_text}面试。"
        if focus and focus != '综合':
            greeting += f"今天我会重点从「{focus}」角度提问。"
        if resume_keywords:
            greeting += f"我已浏览你的简历，注意到{'、'.join(resume_keywords[:3])}等关键词。"
        question_title = title or '基础知识'
        question_body = body or '请做一个简短自我介绍，并说明你最熟悉的一个项目。'
        return (
            f"{greeting}\n\n"
            f"我们从题库中的第一道题开始：\n【{question_title}】\n{question_body}\n\n"
            "请条理清晰地作答，我会根据你的回答继续追问。"
        )

    def _fallback_resume_opening(
        self,
        role: str,
        focus: str,
        mode_text: str,
        difficulty: str,
        resume_summary: str | None,
        resume_keywords: typing.List[str] | None,
    ) -> str:
        greeting = f"你好，欢迎参加{role}岗位的{mode_text}面试。"
        if focus and focus != '综合':
            greeting += f"今天我会从「{focus}」角度了解你的经历。"
        greeting += "我已阅读你的简历。"
        anchor = ''
        if resume_keywords:
            anchor = f"注意到你简历中的「{'、'.join(resume_keywords[:3])}」等经历，"
        elif resume_summary:
            anchor = '结合你简历中的项目与实践，'
        try:
            diff = int(difficulty or 3)
        except (TypeError, ValueError):
            diff = 3
        depth = '请尽量结合数据与具体案例' if diff >= 4 else '请条理清晰地说明'
        return (
            f"{greeting}\n\n"
            f"{anchor}请先做一个 1 分钟左右的自我介绍，然后重点介绍一个与{role}最匹配的项目："
            f"包括背景目标、你的职责、技术方案、遇到的挑战与最终结果。{depth}。"
        )

    def _fallback_interview_reply(
        self,
        answer_text: str,
        role: str | None,
        focus: str | None,
        rag_chunks: typing.List[str] | None,
        resume_keywords: typing.List[str] | None,
        difficulty: str | None,
        phase: str = 'core',
        core_rounds: int | None = None,
        current_round: int | None = None,
        extended_item: dict | None = None,
    ) -> str:
        answer = (answer_text or '').strip()
        role_text = role or '该岗位'
        rag_title = self._extract_rag_title(rag_chunks)
        ext_title = (extended_item or {}).get('title') or rag_title
        ext_body = (extended_item or {}).get('body') or ''

        if phase in ('resume', 'repo'):
            kw0 = (resume_keywords or [None])[0]
            project_hint = f"「{kw0}」相关项目" if kw0 else ('该仓库项目' if phase == 'repo' else '你刚才提到的项目')
            if len(answer) < 40:
                q1 = f"请补充{project_hint}的背景、你的具体职责，以及你独立负责的部分。"
            elif len(answer) < 150:
                q1 = f"在{project_hint}中，关键技术选型是什么？为什么这样选，有过哪些备选方案？"
            else:
                q1 = f"继续深挖{project_hint}：如果流量或数据量扩大 10 倍，架构上你会如何演进？"
            q2 = '该项目最终的业务/性能指标如何？你在其中最关键的贡献是什么？'
            try:
                diff = int(difficulty or 3)
            except (TypeError, ValueError):
                diff = 3
            if diff >= 4:
                q2 = '请从底层实现或源码层面，解释你在该项目中用到的核心技术机制。'
            prefix = '仓库与项目' if phase == 'repo' else '简历与回答'
            return f"好的，我根据你的{prefix}继续追问：\n1) {q1}\n2) {q2}"

        if phase in ('bagu', 'project'):
            is_first_extended = (
                core_rounds is not None
                and current_round is not None
                and current_round == core_rounds + 1
            )
            if phase == 'bagu':
                transition = (
                    f"核心追问（{core_rounds} 轮）已完成，我们切换到八股/基础原理方向。"
                    if is_first_extended else '继续八股/基础方向：'
                )
                q1 = f"请系统讲解「{ext_title or '本题考点'}」的底层原理与常见追问点。"
                q2 = '它与相关数据结构/机制相比，优缺点与适用场景分别是什么？'
            else:
                transition = (
                    f"接下来从项目与工程实践角度继续考察。"
                    if is_first_extended else '继续项目实践方向：'
                )
                q1 = f"结合「{ext_title or '你的项目'}」，说明你在其中的职责、关键决策与量化结果。"
                q2 = '若线上出现故障或性能回退，你的排查路径与复盘改进是什么？'
            body_line = f"\n【{ext_title}】\n{ext_body}\n" if ext_title and ext_body else ''
            return f"{transition}{body_line}\n1) {q1}\n2) {q2}"

        rag_prefix = f"围绕「{rag_title}」" if rag_title else '针对刚才的问题'

        if len(answer) < 30:
            q1 = f"{rag_prefix}，你的回答偏简略，请补充关键步骤、技术选型理由与个人贡献。"
        elif len(answer) < 120:
            q1 = f"{rag_prefix}，请再展开核心原理，并说明你是如何验证方案可行性的。"
        else:
            q1 = f"{rag_prefix}，请深入一个技术细节：如果规模扩大 10 倍，瓶颈会在哪里？"

        focus_questions = {
            '技术深度': '底层数据结构/时间复杂度分别是多少？有没有更优实现？',
            '项目实践': '落地过程中遇到过哪些线上问题，你如何定位并修复？',
            '表达逻辑': '能否按「背景 → 方案 → 结果」重新组织你的回答？',
            '行为动机': '你为什么选择该方案，对比过哪些备选？取舍依据是什么？',
        }
        q2 = focus_questions.get(focus or '', '如果需求变更，你的设计如何保持可扩展？')

        if resume_keywords:
            q2 = f"你简历中提到「{resume_keywords[0]}」，它与本题的技术点有什么关联？"

        try:
            diff = int(difficulty or 3)
        except (TypeError, ValueError):
            diff = 3
        if diff >= 4:
            q2 += '（请结合具体数据或线上案例说明）'

        return f"收到。作为{role_text}面试官，我继续追问：\n1) {q1}\n2) {q2}"

    def _fallback_followups(self, answer: str, phase: str = 'core') -> typing.List[typing.Dict[str, str]]:
        txt = answer or ''
        if phase in ('resume', 'repo'):
            return [
                {'text': '你在该项目中的职责边界与产出是什么？', 'intent': 'behavioral'},
                {'text': '当时最大的技术难点是什么，如何解决的？', 'intent': 'technical'},
                {'text': '如果重做，你会改进架构或流程的哪一环？', 'intent': 'motivation'},
            ]
        technical = '能画一下核心流程或架构图并讲解吗？'
        behavioral = '当时团队协作中最大的分歧是什么，你如何推动共识？'
        motivation = '如果重做一遍，你会改变哪个关键决策？'

        if any(k in txt for k in ('原理', '算法', '实现', '源码', '并发')):
            technical = '这个实现的时间/空间复杂度是多少，有做过压测吗？'
        if any(k in txt for k in ('项目', '负责', '团队', '冲突')):
            behavioral = '你在该项目中的具体职责边界是什么？'
        if any(k in txt for k in ('因为', '选择', '方案', '对比')):
            motivation = '当时为什么没有选择其他主流方案？'

        return [
            {'text': technical, 'intent': 'technical'},
            {'text': behavioral, 'intent': 'behavioral'},
            {'text': motivation, 'intent': 'motivation'},
        ]

    def _fallback_generator(self, prompt: str) -> str:
        return (
            "谢谢你的回答。请进一步说明："
            "1) 核心实现细节与关键代码路径；"
            "2) 遇到的主要挑战与解决过程；"
            "3) 该方案相对其他备选的优势。"
        )

    def _fallback_evaluation(self, transcript: str, mode: str | None = None) -> dict:
        profile = self._candidate_response_profile(transcript)
        length = int(profile['length'])
        answer_count = int(profile['answer_count'])
        tech_hits = int(profile['tech_hits'])
        solve_hits = int(profile['solve_hits'])
        comm_hits = int(profile['comm_hits'])
        eng_hits = int(profile['eng_hits'])
        pot_hits = int(profile['pot_hits'])
        depth_hits = int(profile['depth_hits'])
        structure_hits = int(profile['structure_hits'])

        def clamp(v: float) -> int:
            return max(0, min(92, int(round(v))))

        if length == 0:
            dim_scores = {
                "technical_depth": 0,
                "problem_solving": 0,
                "communication": 0,
                "engineering": 0,
                "potential": 0
            }
        else:
            volume = min(14, length / 80)
            rounds = min(6, answer_count * 1.5)
            dim_scores = {
                "technical_depth": clamp(18 + volume + rounds + tech_hits * 4 + depth_hits * 3),
                "problem_solving": clamp(18 + volume * 0.8 + rounds + solve_hits * 5 + depth_hits * 2),
                "communication": clamp(28 + min(12, length / 100) + comm_hits * 4 + structure_hits * 3),
                "engineering": clamp(16 + volume + eng_hits * 6 + min(8, depth_hits * 2)),
                "potential": clamp(24 + min(10, length / 120) + pot_hits * 5 + min(6, structure_hits * 2)),
            }
            cap = self._score_cap_from_profile(profile)
            dim_scores = {k: min(v, cap) for k, v in dim_scores.items()}

        weights = {
            "technical_depth": 0.3,
            "problem_solving": 0.2,
            "communication": 0.2,
            "engineering": 0.2,
            "potential": 0.1
        }
        score = int(round(sum(dim_scores[k] * weights[k] for k in weights)))
        if mode == 'test':
            score = max(0, score - 5)
            dim_scores = {k: max(0, v - 5) for k, v in dim_scores.items()}

        strengths = []
        if dim_scores["communication"] >= 70:
            strengths.append("表达结构较清晰")
        if dim_scores["technical_depth"] >= 70:
            strengths.append("能够覆盖技术实现或原理")
        if dim_scores["engineering"] >= 70:
            strengths.append("有一定项目与工程实践描述")
        strengths = strengths or ["能完成基础作答", "态度积极"]

        weaknesses = []
        if length < 400:
            weaknesses.append("回答篇幅和有效信息偏少")
        if dim_scores["technical_depth"] < 70:
            weaknesses.append("技术细节与底层原理证据不足")
        if dim_scores["problem_solving"] < 70:
            weaknesses.append("问题分析过程和取舍说明不够完整")
        weaknesses = weaknesses or ["仍可补充更多量化结果和边界案例"]

        suggestions = [
            "按背景、方案、取舍、结果组织核心项目回答",
            "补充关键实现、复杂度、边界条件和验证方式",
            "准备可量化的线上指标、测试或优化案例"
        ]

        def dim_block(score_value: int, evidence: list[str], risks: list[str], sugg: list[str]) -> dict:
            return {
                "score": score_value,
                "evidence": evidence[:3],
                "risks": risks[:3],
                "suggestions": sugg[:3]
            }

        dimensions = {
            "technical_depth": dim_block(
                dim_scores["technical_depth"],
                ["涉及原理或架构描述", "提到实现或性能优化"] if tech_hits > 0 else ["有一定技术关键词"],
                ["技术细节不够具体"],
                ["补充关键实现与复杂度说明"]
            ),
            "problem_solving": dim_block(
                dim_scores["problem_solving"],
                ["描述了问题分析或定位思路"] if solve_hits > 0 else ["有基础问题描述"],
                ["缺少清晰的分析步骤"],
                ["按因果链路复盘问题分析"]
            ),
            "communication": dim_block(
                dim_scores["communication"],
                ["表达较清晰"],
                ["结构化表达仍可提升"],
                ["先结论后要点，突出关键数据"]
            ),
            "engineering": dim_block(
                dim_scores["engineering"],
                ["提到项目或工程实践"] if eng_hits > 0 else ["有基础项目描述"],
                ["工程化细节不充分"],
                ["补充测试、发布或监控环节"]
            ),
            "potential": dim_block(
                dim_scores["potential"],
                ["表现出学习或复盘意识"] if pot_hits > 0 else ["态度积极"],
                ["成长目标不够明确"],
                ["设定下一阶段学习计划"]
            )
        }

        return {
            "score": score,
            "weights": weights,
            "dimensions": dimensions,
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "suggestions": suggestions[:3],
            "summary": "本报告由规则兜底评分生成，仅基于回答长度、关键词和结构化证据估算；建议配置大模型后获得更准确的评估。",
            "evaluation_source": "fallback"
        }


__all__ = ["AIService"]
