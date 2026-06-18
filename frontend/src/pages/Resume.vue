<template>
  <section class="resume-wrap">
    <article class="card hero">
      <span class="tag">Resume Center</span>
      <h2>简历管理</h2>
      <p class="muted">系统提供规范模板，支持直接填写、上传并自动生成摘要与关键词。</p>
    </article>

    <section class="resume-grid">
      <article class="card editor">
        <header class="card-head">
          <div>
            <h3>简历内容</h3>
            <p class="muted">在模板基础上填写，或切换为自由编辑。</p>
          </div>
          <label class="toggle">
            <input v-model="useTemplate" type="checkbox" />
            <span>使用模板预填</span>
          </label>
        </header>

        <textarea v-model.trim="resumeText" rows="16" placeholder="在此填写你的简历内容"></textarea>

        <div class="editor-actions">
          <div class="left-actions">
            <button class="ghost" type="button" :disabled="uploadingResume" @click="pickResumeFile">上传简历文件</button>
            <button class="ghost" type="button" :disabled="savingResume" @click="clearResume">清空内容</button>
          </div>
          <button type="button" :disabled="savingResume" @click="saveResumeText">{{ savingResume ? '保存中...' : '保存简历' }}</button>
        </div>

        <input ref="resumeInputRef" type="file" accept=".pdf,.docx,.txt,.md" class="hidden" @change="onResumeSelected" />
      </article>

      <article class="card template">
        <header class="card-head">
          <div>
            <h3>标准模板</h3>
            <p class="muted">结构清晰、适用于校招与实习场景。</p>
          </div>
          <button class="ghost" type="button" :disabled="savingResume" @click="copyTemplate">复制模板</button>
        </header>
        <div class="template-box">
          <pre>{{ resumeTemplate }}</pre>
        </div>
      </article>

      <article class="card analysis">
        <header class="card-head">
          <div>
            <h3>简历分析</h3>
            <p class="muted">上传或保存后会自动更新摘要与关键词。</p>
          </div>
        </header>
        <div class="analysis-grid">
          <div class="analysis-item">
            <span class="analysis-label">文件</span>
            <p class="analysis-value">{{ resumeFileName || '未上传' }}</p>
          </div>
          <div class="analysis-item span-2">
            <span class="analysis-label">摘要</span>
            <p class="analysis-value summary">{{ resumeSummary || '暂无摘要，请上传或保存简历后自动生成。' }}</p>
          </div>
        </div>
        <div class="keyword-panel">
          <span class="keyword-label">关键词</span>
          <div v-if="resumeKeywords.length" class="keyword-chips">
            <span v-for="kw in resumeKeywords" :key="kw" class="keyword-chip">{{ kw }}</span>
          </div>
          <p v-else class="keyword-empty muted">暂无关键词</p>
        </div>
        <p v-if="message" class="msg">{{ message }}</p>
      </article>
    </section>
  </section>
</template>

<script>
import { onMounted, ref, watch } from 'vue'
import { authGetResume, authUpdateResume, authUploadResume } from '../services/api'
import { isLoggedIn } from '../services/authStore'

export default {
  name: 'Resume',
  setup() {
    const savingResume = ref(false)
    const uploadingResume = ref(false)
    const message = ref('')

    const resumeText = ref('')
    const resumeSummary = ref('')
    const resumeKeywords = ref([])
    const resumeFileName = ref('')
    const resumeInputRef = ref(null)
    const useTemplate = ref(true)

    const resumeTemplate = ref(
      '【基本信息】\n' +
      '姓名：\n' +
      '邮箱：\n' +
      '电话：\n' +
      '求职方向：\n\n' +
      '【教育背景】\n' +
      '学校：\n' +
      '专业/年级：\n' +
      '主修课程：\n\n' +
      '【项目经历】\n' +
      '1. 项目名称：\n' +
      '   背景/目标：\n' +
      '   角色与职责：\n' +
      '   技术栈：\n' +
      '   成果/指标：\n\n' +
      '2. 项目名称：\n' +
      '   背景/目标：\n' +
      '   角色与职责：\n' +
      '   技术栈：\n' +
      '   成果/指标：\n\n' +
      '【实习/实践】\n' +
      '公司/组织：\n' +
      '岗位：\n' +
      '职责与产出：\n\n' +
      '【技能清单】\n' +
      '语言：\n' +
      '框架：\n' +
      '工具：\n\n' +
      '【证书/奖项】\n' +
      '证书：\n' +
      '奖项：\n'
    )

    function applyTemplateIfNeeded(force = false) {
      if (useTemplate.value && (force || !resumeText.value.trim())) {
        resumeText.value = resumeTemplate.value
      }
    }

    async function loadResume() {
      if (!isLoggedIn()) return
      try {
        const res = await authGetResume()
        resumeText.value = res?.text || ''
        resumeSummary.value = res?.summary || ''
        resumeKeywords.value = Array.isArray(res?.keywords) ? res.keywords : []
        resumeFileName.value = res?.file_name || ''
      } catch {
        // ignore
      }
      applyTemplateIfNeeded()
    }

    function pickResumeFile() {
      resumeInputRef.value && resumeInputRef.value.click()
    }

    async function onResumeSelected(evt) {
      const file = evt.target.files && evt.target.files[0]
      evt.target.value = ''
      if (!file) return
      if (!isLoggedIn()) {
        message.value = '请先登录后再上传简历。'
        return
      }

      uploadingResume.value = true
      message.value = ''
      try {
        const res = await authUploadResume(file)
        resumeText.value = res?.text || resumeText.value
        resumeSummary.value = res?.summary || ''
        resumeKeywords.value = Array.isArray(res?.keywords) ? res.keywords : []
        resumeFileName.value = res?.file_name || ''
        message.value = '简历已上传并分析。'
      } catch (err) {
        message.value = `上传失败：${err.message || err}`
      } finally {
        uploadingResume.value = false
      }
    }

    async function saveResumeText() {
      if (!isLoggedIn()) {
        message.value = '请先登录后再保存简历。'
        return
      }

      savingResume.value = true
      message.value = ''
      try {
        const res = await authUpdateResume({ text: resumeText.value })
        resumeSummary.value = res?.summary || ''
        resumeKeywords.value = Array.isArray(res?.keywords) ? res.keywords : []
        resumeFileName.value = res?.file_name || resumeFileName.value
        message.value = '简历已保存并分析。'
      } catch (err) {
        message.value = `保存失败：${err.message || err}`
      } finally {
        savingResume.value = false
      }
    }

    function clearResume() {
      resumeText.value = ''
      applyTemplateIfNeeded()
    }

    async function copyTemplate() {
      try {
        await navigator.clipboard.writeText(resumeTemplate.value)
        message.value = '模板已复制到剪贴板。'
      } catch {
        message.value = '复制失败，请手动选中模板。'
      }
    }

    watch(useTemplate, () => {
      applyTemplateIfNeeded()
    })

    onMounted(async () => {
      await loadResume()
    })

    return {
      savingResume,
      uploadingResume,
      message,
      resumeText,
      resumeSummary,
      resumeKeywords,
      resumeFileName,
      resumeInputRef,
      resumeTemplate,
      useTemplate,
      pickResumeFile,
      onResumeSelected,
      saveResumeText,
      clearResume,
      copyTemplate
    }
  }
}
</script>

<style scoped>
.resume-wrap {
  display: grid;
  gap: 14px;
}

.hero {
  background:
    radial-gradient(circle at 84% 18%, rgba(37, 89, 214, 0.16), transparent 45%),
    linear-gradient(130deg, #eef5ff, #ffffff);
}

.tag {
  display: inline-flex;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--primary-strong, #1f4fb9);
  background: var(--primary-soft, #e7efff);
  border-radius: 999px;
  padding: 4px 10px;
}

h2 {
  margin: 8px 0 0;
  color: #1a4699;
  font-size: clamp(24px, 3vw, 30px);
  line-height: 1.2;
}

.muted {
  color: #587091;
  font-size: 13px;
  line-height: 1.6;
}

.resume-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 12px;
}

.editor {
  grid-column: span 8;
  display: grid;
  gap: 12px;
}

.template {
  grid-column: span 4;
  display: grid;
  gap: 12px;
}

.analysis {
  grid-column: span 12;
  display: grid;
  gap: 14px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.card-head h3 {
  margin: 0;
  color: #1a4699;
  font-size: 18px;
}

.card-head p {
  margin: 4px 0 0;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #4f6688;
}

textarea {
  border: 1px solid rgba(37, 89, 214, 0.2);
  border-radius: 12px;
  padding: 12px 14px;
  width: 100%;
  min-height: 340px;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text, #1a2636);
}

.editor-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.left-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.template-box {
  border: 1px dashed rgba(37, 89, 214, 0.22);
  border-radius: 14px;
  padding: 14px;
  background: #f7faff;
  max-height: 520px;
  overflow: auto;
}

.template-box pre {
  margin: 0;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.65;
  color: #3b5674;
  white-space: pre-wrap;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.analysis-item {
  padding: 14px 16px;
  border-radius: 14px;
  background: var(--primary-soft, #eff6ff);
  border: 1px solid rgba(37, 89, 214, 0.12);
}

.analysis-item.span-2 {
  grid-column: span 2;
}

.analysis-label {
  display: block;
  font-size: 12px;
  letter-spacing: .04em;
  color: #587091;
}

.analysis-value {
  margin: 6px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: #1a2636;
}

.analysis-value.summary {
  font-size: 14px;
}

.keyword-panel {
  padding: 14px 16px;
  border-radius: 14px;
  background: #f8fbff;
  border: 1px solid rgba(37, 89, 214, 0.1);
}

.keyword-label {
  display: block;
  font-size: 12px;
  color: #587091;
  margin-bottom: 8px;
}

.keyword-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.keyword-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: #1d4ed8;
  background: #fff;
  border: 1px solid rgba(37, 99, 235, 0.22);
}

.keyword-empty {
  margin: 0;
  font-size: 13px;
}

.msg {
  min-height: 20px;
  font-size: 13px;
  color: #2151b3;
  margin: 0;
}

.ghost {
  background: #fff;
  color: #1f4fb9;
  border: 1px solid rgba(37, 89, 214, 0.18);
}

.hidden {
  display: none;
}

@media (max-width: 980px) {
  .editor,
  .template {
    grid-column: span 12;
  }

  .analysis-grid {
    grid-template-columns: 1fr;
  }

  .analysis-item.span-2 {
    grid-column: span 1;
  }
}

:global([data-theme="dark"]) .hero {
  background:
    radial-gradient(circle at 84% 18%, rgba(122, 162, 255, 0.14), transparent 45%),
    linear-gradient(120deg, #121a26, #0f1620);
}
:global([data-theme="dark"]) h2,
:global([data-theme="dark"]) .card-head h3 {
  color: #ffffff;
}
:global([data-theme="dark"]) .muted,
:global([data-theme="dark"]) .analysis-label,
:global([data-theme="dark"]) .keyword-label {
  color: rgba(255, 255, 255, 0.78);
}
:global([data-theme="dark"]) .template-box {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.2);
}
:global([data-theme="dark"]) .template-box pre,
:global([data-theme="dark"]) .analysis-value {
  color: #ffffff;
}
:global([data-theme="dark"]) .analysis-item,
:global([data-theme="dark"]) .keyword-panel {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
}
:global([data-theme="dark"]) .keyword-chip {
  background: #1d2a40;
  color: #ffffff;
  border-color: rgba(122, 162, 255, 0.28);
}
:global([data-theme="dark"]) textarea {
  background: rgba(18, 26, 38, 0.7);
  color: #ffffff;
  border-color: rgba(122, 162, 255, 0.28);
}
:global([data-theme="dark"]) .msg {
  color: #ffffff;
}
</style>
