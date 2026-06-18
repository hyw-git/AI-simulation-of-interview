<template>
  <aside v-if="visible" class="coding-panel" role="complementary" aria-label="代码实战">
    <header class="coding-head">
      <div>
        <h2>代码实战</h2>
        <p class="muted">{{ panelHint }}</p>
      </div>
      <button class="ghost" type="button" @click="$emit('close')">收起</button>
    </header>

    <section v-if="loading" class="state-block">
      <p class="muted">正在加载题目...</p>
    </section>

    <template v-else-if="challenge">
      <section class="challenge-block">
        <div class="challenge-meta">
          <span class="diff-chip">难度 {{ challenge.difficulty || '-' }}</span>
          <span v-if="challenge.language" class="lang-chip">{{ activeLangLabel }}</span>
        </div>
        <h3>{{ challenge.title }}</h3>
        <p class="challenge-desc">{{ challenge.description }}</p>
        <ul v-if="challenge.test_cases?.length" class="sample-list">
          <li v-for="(tc, i) in challenge.test_cases" :key="i">
            <b>{{ tc.label || `样例 ${i + 1}` }}</b>
            <span v-if="tc.expected">期望：{{ tc.expected }}</span>
          </li>
        </ul>
      </section>

      <section class="lang-row">
        <span class="code-label">编程语言</span>
        <div class="lang-options">
          <button
            v-for="lang in languageOptions"
            :key="lang.id"
            type="button"
            class="lang-btn"
            :class="{ active: selectedLang === lang.id, unavailable: !lang.runnable }"
            :title="lang.runnable ? '支持在线运行' : '环境未就绪，可书写并提交'"
            @click="selectLang(lang.id)"
          >
            {{ lang.label }}
            <span v-if="lang.default" class="default-tag">推荐</span>
            <span v-if="!lang.runnable" class="soon">不可运行</span>
          </button>
        </div>
      </section>

      <section class="editor-block">
        <label class="code-label">代码编辑</label>
        <textarea
          v-model="code"
          class="code-editor"
          rows="12"
          spellcheck="false"
          :disabled="busy"
          :placeholder="editorPlaceholder"
        />
      </section>

      <section v-if="canRunSelected" class="stdin-block">
        <label class="code-label">标准输入（可选，用于「运行」）</label>
        <textarea v-model="stdin" class="stdin-box" rows="2" :disabled="busy" />
      </section>

      <div class="coding-actions">
        <button class="ghost" type="button" :disabled="busy || !interviewId" @click="reloadChallenge">换一题</button>
        <button
          class="ghost"
          type="button"
          :disabled="busy || !code.trim() || !canRunSelected"
          @click="runCode"
        >
          运行
        </button>
        <button
          class="ghost"
          type="button"
          :disabled="busy || !code.trim() || !canRunSelected || !hasTests"
          @click="runTests"
        >
          测试样例
        </button>
        <button type="button" :disabled="busy || !code.trim()" @click="submitCode">提交评估</button>
      </div>

      <section v-if="runOutput" class="output-block">
        <h4>运行输出</h4>
        <pre>{{ runOutput }}</pre>
      </section>

      <section v-if="testResults.length" class="test-block">
        <h4>测试结果 · {{ testSummary }}</h4>
        <ul>
          <li v-for="(r, i) in testResults" :key="i" :class="{ pass: r.passed, fail: !r.passed }">
            <b>{{ r.label }}</b>
            <span>{{ r.passed ? '通过' : '未通过' }}</span>
            <div v-if="!r.passed" class="test-detail">
              期望 {{ r.expected || '-' }}，实际 {{ r.actual || '-' }}
              <span v-if="r.stderr">（{{ r.stderr }}）</span>
            </div>
          </li>
        </ul>
      </section>

      <section v-if="evaluation" class="eval-block">
        <h4>评估 {{ evaluation.score != null ? `· ${evaluation.score} 分` : '' }}</h4>
        <p>{{ evaluation.feedback }}</p>
        <ul v-if="evaluation.hints?.length">
          <li v-for="(h, i) in evaluation.hints" :key="i">{{ h }}</li>
        </ul>
      </section>
    </template>

    <section v-else class="state-block">
      <p class="error-text">{{ loadError || '暂无题目' }}</p>
      <button v-if="interviewId" type="button" :disabled="busy" @click="reloadChallenge">重新加载</button>
    </section>
  </aside>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { fetchCodingChallenge, runInterviewCode, submitInterviewCode, testInterviewCode } from '../services/api'

export default {
  name: 'CodingPanel',
  props: {
    visible: { type: Boolean, default: false },
    interviewId: { type: String, default: '' },
    externalChallenge: { type: Object, default: null }
  },
  emits: ['close', 'submitted'],
  setup(props, { emit }) {
    const challenge = ref(null)
    const loading = ref(false)
    const loadError = ref('')
    const selectedLang = ref('python')
    const code = ref('')
    const stdin = ref('')
    const busy = ref(false)
    const runOutput = ref('')
    const testResults = ref([])
    const testSummary = ref('')
    const evaluation = ref(null)

    const languageOptions = computed(() => {
      const list = challenge.value?.languages
      if (Array.isArray(list) && list.length) return list
      return [{ id: 'python', label: 'Python', runnable: true }]
    })

    const selectedLangMeta = computed(() =>
      languageOptions.value.find(l => l.id === selectedLang.value) || null
    )

    const canRunSelected = computed(() => Boolean(selectedLangMeta.value?.runnable))

    const activeLangLabel = computed(() => selectedLangMeta.value?.label || selectedLang.value)

    const panelHint = computed(() => {
      if (canRunSelected.value) {
        return `当前语言：${activeLangLabel.value}。支持运行、样例测试与提交评估。`
      }
      return `${activeLangLabel.value} 运行环境未就绪，可书写代码并提交评估，或切换其他语言。`
    })

    const editorPlaceholder = computed(() => {
      if (selectedLang.value === 'java') return '// 在此编写 Java 代码（建议实现 Solution 类）'
      if (selectedLang.value === 'javascript') return '// 在此编写 JavaScript 代码'
      return '# 在此编写 Python 代码'
    })

    function testCasesForLang() {
      const cases = challenge.value?.test_cases || []
      const lang = selectedLang.value
      return cases.filter(tc => {
        const snippets = tc.snippets || {}
        return snippets[lang] || tc.run_snippet || tc.run_snippet_java || tc.run_snippet_js
      })
    }

    const hasTests = computed(() => testCasesForLang().length > 0)

    function applyChallenge(c) {
      if (!c) return
      challenge.value = c
      selectedLang.value = c.language || 'python'
      const starters = c.starter_codes || {}
      code.value = starters[selectedLang.value] || c.starter_code || ''
      stdin.value = ''
      runOutput.value = ''
      testResults.value = []
      testSummary.value = ''
      evaluation.value = null
      loadError.value = ''
    }

    function selectLang(langId) {
      const lang = languageOptions.value.find(l => l.id === langId)
      if (!lang) return
      selectedLang.value = langId
      const starters = challenge.value?.starter_codes || {}
      if (starters[langId]) {
        code.value = starters[langId]
      }
      runOutput.value = ''
      testResults.value = []
      testSummary.value = ''
    }

    async function reloadChallenge() {
      if (!props.interviewId) return
      loading.value = true
      loadError.value = ''
      try {
        const c = await fetchCodingChallenge(props.interviewId)
        applyChallenge(c)
      } catch (err) {
        loadError.value = err.message || String(err)
        challenge.value = null
      } finally {
        loading.value = false
      }
    }

    async function runCode() {
      if (!props.interviewId || !canRunSelected.value) return
      busy.value = true
      try {
        const res = await runInterviewCode(props.interviewId, {
          code: code.value,
          stdin: stdin.value,
          language: selectedLang.value
        })
        const parts = []
        if (res.stdout) parts.push(`[stdout]\n${res.stdout}`)
        if (res.stderr) parts.push(`[stderr]\n${res.stderr}`)
        parts.push(`exit: ${res.exit_code}${res.timed_out ? ' (超时)' : ''}`)
        runOutput.value = parts.join('\n\n')
      } catch (err) {
        runOutput.value = `运行失败：${err.message || err}`
      } finally {
        busy.value = false
      }
    }

    async function runTests() {
      if (!props.interviewId || !hasTests.value) return
      busy.value = true
      try {
        const res = await testInterviewCode(props.interviewId, {
          code: code.value,
          language: selectedLang.value,
          test_cases: challenge.value.test_cases
        })
        testResults.value = res.results || []
        testSummary.value = res.message || ''
      } catch (err) {
        testSummary.value = `测试失败：${err.message || err}`
        testResults.value = []
      } finally {
        busy.value = false
      }
    }

    async function submitCode() {
      if (!props.interviewId || !challenge.value) return
      busy.value = true
      try {
        const payloadChallenge = {
          ...challenge.value,
          language: selectedLang.value,
          submitted_code: code.value
        }
        const res = await submitInterviewCode(props.interviewId, {
          code: code.value,
          stdin: stdin.value,
          language: selectedLang.value,
          challenge: payloadChallenge
        })
        if (res.run_result) {
          runOutput.value = `[stdout]\n${res.run_result.stdout || ''}\n[stderr]\n${res.run_result.stderr || ''}`
        }
        evaluation.value = res.evaluation || null
        emit('submitted', {
          challenge: payloadChallenge,
          code: code.value,
          evaluation: evaluation.value,
          run_result: res.run_result
        })
      } catch (err) {
        runOutput.value = `提交失败：${err.message || err}`
      } finally {
        busy.value = false
      }
    }

    watch(
      () => props.externalChallenge,
      (c) => {
        if (c && c.title) {
          loading.value = false
          applyChallenge(c)
        }
      },
      { immediate: true, deep: true }
    )

    watch(
      () => [props.visible, props.interviewId, props.externalChallenge],
      ([vis, id, ext]) => {
        if (!vis || !id) return
        if (ext && ext.title) return
        if (!challenge.value && !loading.value) reloadChallenge()
      },
      { immediate: true }
    )

    return {
      challenge,
      loading,
      loadError,
      selectedLang,
      languageOptions,
      selectedLangMeta,
      canRunSelected,
      hasTests,
      activeLangLabel,
      panelHint,
      editorPlaceholder,
      code,
      stdin,
      busy,
      runOutput,
      testResults,
      testSummary,
      evaluation,
      selectLang,
      reloadChallenge,
      runCode,
      runTests,
      submitCode
    }
  }
}
</script>

<style scoped>
.coding-panel {
  position: fixed;
  top: 70px;
  right: 16px;
  bottom: 100px;
  width: min(460px, 94vw);
  z-index: 1250;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid rgba(37, 89, 214, 0.16);
  border-radius: 16px;
  box-shadow: 0 18px 48px rgba(26, 58, 112, 0.14);
  overflow: auto;
  font-family: inherit;
}
.coding-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  flex-shrink: 0;
}
.coding-head h2 { margin: 0; font-size: 17px; color: #1a4699; }
.muted { margin: 4px 0 0; font-size: 12px; color: #587091; line-height: 1.5; }
.state-block { padding: 8px 0; }
.error-text { color: #b42318; font-size: 13px; margin: 0 0 8px; }
.challenge-block {
  padding: 12px;
  border-radius: 12px;
  background: #f7faff;
  border: 1px solid rgba(37, 89, 214, 0.12);
}
.challenge-meta { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.diff-chip, .lang-chip {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #e7efff;
  color: #1a4699;
}
.challenge-block h3 { margin: 0 0 6px; font-size: 15px; color: #183d8d; }
.challenge-desc { margin: 0; font-size: 13px; line-height: 1.65; color: #334155; white-space: pre-wrap; }
.sample-list { margin: 10px 0 0; padding-left: 18px; font-size: 12px; color: #4f6688; }
.sample-list li { margin-bottom: 4px; }
.lang-row { display: grid; gap: 6px; }
.lang-options { display: flex; gap: 8px; flex-wrap: wrap; }
.lang-btn {
  border: 1px solid rgba(37, 89, 214, 0.2);
  background: #fff;
  color: #1f4fb9;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
}
.lang-btn.active { background: #1f4fb9; color: #fff; border-color: #1f4fb9; }
.lang-btn.unavailable { opacity: 0.72; }
.default-tag { font-size: 10px; margin-left: 4px; color: #15803d; }
.soon { font-size: 10px; margin-left: 4px; }
.code-label { font-size: 12px; color: #5f7392; font-weight: 600; }
.code-editor, .stdin-box {
  width: 100%;
  font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid rgba(37, 89, 214, 0.2);
  border-radius: 10px;
  padding: 10px;
  resize: vertical;
  box-sizing: border-box;
}
.coding-actions { display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }
.output-block, .eval-block, .test-block {
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fbff;
  border: 1px solid rgba(37, 89, 214, 0.1);
  font-size: 13px;
}
.output-block pre { margin: 6px 0 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; }
.test-block ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 6px; }
.test-block li {
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
  display: grid;
  gap: 4px;
}
.test-block li.pass { background: #ecfdf3; color: #166534; }
.test-block li.fail { background: #fef2f2; color: #991b1b; }
.test-detail { font-size: 11px; opacity: 0.9; }
.eval-block h4, .test-block h4, .output-block h4 { margin: 0 0 6px; color: #1a4699; font-size: 13px; }
.eval-block ul { margin: 6px 0 0; padding-left: 18px; }
.ghost { background: #fff; color: #1f4fb9; border: 1px solid rgba(37, 89, 214, 0.18); }
button[type="button"]:not(.ghost):not(.lang-btn) {
  background: #1f4fb9;
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 8px 14px;
  cursor: pointer;
}
</style>
