<template>
  <section class="iv-wrap">
    <div v-if="configVisible" class="config-mask">
      <article class="config-card">
        <header class="config-head">
          <div class="config-head-text">
            <h2>面试预设</h2>
            <p>选择模式、难度与岗位后开始面试，可选用简历进行个性化追问。</p>
          </div>
          <button class="ghost config-exit-btn" type="button" @click="exitConfig">退出</button>
        </header>

        <div class="config-grid">
          <label>
            面试模式
            <select v-model="interviewMode">
              <option value="practice">练习</option>
              <option value="test">测评</option>
            </select>
          </label>
          <label>
            难度等级
            <select v-model.number="difficulty">
              <option :value="1">1</option>
              <option :value="2">2</option>
              <option :value="3">3</option>
              <option :value="4">4</option>
              <option :value="5">5</option>
            </select>
          </label>
          <label>
            岗位
            <select v-model="selectedRole">
              <option value="Java后端">Java后端</option>
              <option value="Web前端">Web前端</option>
              <option value="Python算法">Python算法</option>
            </select>
          </label>
          <label>
            关注重点
            <select v-model="focusArea">
              <option value="综合">综合</option>
              <option value="技术深度">技术深度</option>
              <option value="项目实践">项目实践</option>
              <option value="表达逻辑">表达逻辑</option>
              <option value="行为动机">行为动机</option>
            </select>
          </label>
          <label>
            时间限制（分钟）
            <input v-model.number="timeLimit" type="number" min="5" max="120" />
          </label>
        </div>

        <section class="resume-block">
          <div class="resume-head">
            <div>
              <h3>简历分析</h3>
              <p class="resume-desc">开启后采用<strong>简历驱动</strong>策略：先基于简历项目提问，核心阶段不随机抽题库首题。</p>
            </div>
            <label class="toggle">
              <input v-model="useResume" type="checkbox" />
              <span>使用简历进行个性化追问</span>
            </label>
          </div>
          <div class="resume-actions">
            <button class="ghost" type="button" :disabled="resumeUploading" @click="pickResumeFile">上传简历文件</button>
            <span class="muted">仅支持 pdf/docx/txt</span>
          </div>
          <input ref="resumeInputRef" type="file" accept=".pdf,.docx,.txt,.md" class="hidden" @change="onResumeSelected" />
          <div class="resume-meta">
            <div class="resume-meta-item">
              <span class="resume-meta-label">文件</span>
              <span class="resume-meta-value">{{ resumeFileName || '未上传' }}</span>
            </div>
            <div class="resume-meta-item full">
              <span class="resume-meta-label">摘要</span>
              <span class="resume-meta-value">{{ resumeSummary || '暂无' }}</span>
            </div>
            <div class="resume-meta-item full">
              <span class="resume-meta-label">关键词</span>
              <div v-if="resumeKeywords.length" class="resume-keyword-chips">
                <span v-for="kw in resumeKeywords" :key="kw" class="resume-keyword-chip">{{ kw }}</span>
              </div>
              <span v-else class="resume-meta-value">暂无</span>
            </div>
          </div>
        </section>

        <section class="repo-block">
          <h3>Git 仓库（可选）</h3>
          <p class="resume-desc">填写公开仓库链接后，面试官将先分析 README 与项目结构再提问。</p>
          <div class="repo-actions">
            <input v-model.trim="repoUrl" type="url" class="repo-input" placeholder="https://github.com/owner/repo" />
            <button class="ghost" type="button" :disabled="repoAnalyzing || !repoUrl" @click="analyzeRepoPreview">
              {{ repoAnalyzing ? '分析中...' : '分析仓库' }}
            </button>
          </div>
          <div v-if="repoAnalysis?.name" class="resume-meta-item full">
            <span class="resume-meta-label">仓库</span>
            <span class="resume-meta-value">{{ repoAnalysis.name }} · {{ repoAnalysis.language_text || '未知语言' }}</span>
          </div>
          <div v-if="repoAnalysis?.summary" class="resume-meta-item full">
            <span class="resume-meta-label">分析摘要</span>
            <span class="resume-meta-value">{{ repoAnalysis.summary }}</span>
          </div>
          <p v-if="repoAnalysis?.error" class="repo-error">{{ repoAnalysis.error }}</p>
        </section>

        <label class="toggle coding-toggle">
          <input v-model="enableCoding" type="checkbox" />
          <span>启用代码实战侧栏（Python 手敲运行与提交）</span>
        </label>

        <p v-if="seedQuestionId" class="seed-hint">
          已从题库带入题目：<b>{{ seedQuestionTitle || seedQuestionId }}</b>
        </p>

        <p v-if="!speechAvailable" class="speech-hint config-hint">
          服务端语音转写未配置。若使用 Chrome/Edge，面试中仍可用<strong>浏览器语音识别</strong>（无需 OpenAI Key）。
        </p>
        <p v-else-if="speechMode === 'browser'" class="speech-hint config-hint muted-hint">
          将使用浏览器内置语音识别（Chrome/Edge），无需 OpenAI Key。
        </p>
        <p v-else-if="!llmAvailable" class="speech-hint config-hint muted-hint">
          当前为离线兜底模式：追问与评分使用规则引擎，配置 API Key 后可启用完整 AI 能力。
        </p>

        <div class="config-actions">
          <button class="ghost" type="button" @click="exitConfig">退出</button>
          <div class="config-actions-right">
            <button class="ghost" type="button" @click="skipConfig">暂不使用简历</button>
            <button class="report-btn" type="button" :disabled="connecting" @click="confirmConfig">开始面试</button>
          </div>
        </div>
      </article>
    </div>

    <header class="iv-header">
      <div>
        <h1>AI 面试官</h1>
        <p>可文字或语音输入，系统会结合岗位知识库进行追问。</p>
      </div>
      <div class="iv-controls">
        <div
          v-if="interviewStrategyLabel && configConfirmed"
          class="strategy-badge"
        >
          {{ interviewStrategyLabel }}
        </div>
        <div
          v-if="maxRounds > 0 && configConfirmed"
          class="round-badge"
          :class="{ extended: ['bagu', 'project'].includes(interviewPhase), resume: interviewPhase === 'resume', repo: interviewPhase === 'repo' }"
        >
          <template v-if="interviewPhase === 'resume'">
            简历深挖 {{ currentRound }} / {{ maxRounds }}
          </template>
          <template v-else-if="interviewPhase === 'repo'">
            仓库深挖 {{ currentRound }} / {{ maxRounds }}
          </template>
          <template v-else-if="interviewPhase === 'core'">
            核心追问 {{ currentRound }} / {{ maxRounds }}
          </template>
          <template v-else>
            {{ phaseLabel }} · 第 {{ currentRound }} 轮
          </template>
        </div>
        <div
          v-if="remainingSeconds > 0 && configConfirmed"
          class="timer-badge"
          :class="{ urgent: remainingSeconds <= 60, expired: timeExpired }"
        >
          {{ timeExpired ? '时间到' : `剩余 ${formatCountdown(remainingSeconds)}` }}
        </div>
        <button class="close-btn" @click="$router.back()">关闭</button>
        <label>
          岗位
          <select v-model="selectedRole" :disabled="connecting || sending || generatingReport || interviewEnded || !configConfirmed">
            <option value="Java后端">Java后端</option>
            <option value="Web前端">Web前端</option>
            <option value="Python算法">Python算法</option>
          </select>
        </label>
        <label>
          关注重点
          <select v-model="focusArea" :disabled="connecting || sending || generatingReport || interviewEnded || !configConfirmed">
            <option value="综合">综合</option>
            <option value="技术深度">技术深度</option>
            <option value="项目实践">项目实践</option>
            <option value="表达逻辑">表达逻辑</option>
            <option value="行为动机">行为动机</option>
          </select>
        </label>
        <button class="ghost" :disabled="connecting || sending || generatingReport || !configConfirmed" @click="configVisible = true">配置面试</button>
        <button :disabled="connecting || sending || generatingReport" @click="restartInterview">重置会话</button>
        <button
          v-if="interviewReport"
          class="ghost"
          :disabled="connecting || sending || generatingReport"
          @click="reportVisible = !reportVisible"
        >
          {{ reportVisible ? '收起报告' : '展开报告' }}
        </button>
        <button
          v-if="enableCoding && configConfirmed && interviewId"
          class="ghost coding-btn"
          :class="{ active: codingVisible, pending: codingChallenge && !codingCompleted && !codingVisible }"
          :disabled="connecting || generatingReport"
          @click="codingVisible = !codingVisible"
        >
          {{ codingVisible ? '收起代码' : (codingChallenge && !codingCompleted ? '代码题待完成' : '代码实战') }}
        </button>
        <button
          class="report-btn"
          :disabled="connecting || sending || streaming || generatingReport || !interviewId"
          @click="endInterviewAndGenerateReport"
        >
          {{ generatingReport ? '生成中...' : '结束面试并生成报告' }}
        </button>
      </div>
    </header>

    <CodingPanel
      :visible="codingVisible && enableCoding"
      :interview-id="interviewId"
      :external-challenge="codingChallenge"
      @close="codingVisible = false"
      @submitted="onCodingSubmitted"
      @challenge-changed="onCodingChallengeChanged"
    />

    <main ref="scrollRef" class="iv-messages" :class="{ 'with-report': reportVisible }">
      <article v-for="m in messages" :key="m.id" class="msg" :class="m.sender">
        <div class="bubble">
          <div class="meta">
            <span>{{ m.sender === 'ai' ? 'AI面试官' : '我' }}</span>
            <span class="small">{{ m.time }}</span>
          </div>
          <p>{{ m.text }}</p>
          <div v-if="m.sender === 'ai' && m.role" class="trace">岗位：{{ m.role }} · RAG片段：{{ m.ragCount || 0 }}</div>
        </div>
      </article>
      <div v-if="streaming" class="typing">AI 正在输入...</div>
      <div v-if="lastFollowups.length && !interviewEnded" class="followup-panel">
        <span class="followup-label">参考追问方向</span>
        <div class="followup-chips">
          <button
            v-for="(f, idx) in lastFollowups"
            :key="idx"
            type="button"
            class="followup-chip"
            @click="applyFollowup(f.text)"
          >
            {{ f.text }}
          </button>
        </div>
      </div>
    </main>

    <aside v-if="reportVisible && interviewReport" class="report-panel" role="complementary" aria-label="面试报告">
      <div class="report-head">
        <h2>面试评分报告</h2>
        <button class="ghost" @click="reportVisible = false">收起</button>
      </div>

      <div class="score-block">
        <div class="score-label">综合得分</div>
        <div class="score-value">{{ interviewReport.score }}</div>
        <div class="score-sub">/ 100</div>
      </div>

      <section class="report-group">
        <h3>评分维度雷达图</h3>
        <RadarChart :data="radarData" :size="250" />
      </section>

      <section class="report-group">
        <h3>评估摘要</h3>
        <p class="summary-text">{{ interviewReport.summary || '暂无' }}</p>
      </section>

      <section class="report-group">
        <details class="dimension-toggle" open>
          <summary>维度详解</summary>
          <div class="dimension-grid">
            <article v-for="d in dimensionItems(interviewReport)" :key="d.key" class="dimension-card">
              <header class="dimension-head">
                <strong>{{ d.label }}</strong>
                <div class="dimension-meta">
                  <span class="dimension-score">{{ d.score }}</span>
                  <span v-if="d.weight !== undefined" class="dimension-weight">权重 {{ Math.round(d.weight * 100) }}%</span>
                </div>
              </header>
              <div class="dimension-body">
                <div class="dimension-col">
                  <h4>证据</h4>
                  <ul>
                    <li v-for="(x, i) in d.evidence" :key="`e-${d.key}-${i}`">{{ x }}</li>
                  </ul>
                </div>
                <div class="dimension-col">
                  <h4>风险</h4>
                  <ul>
                    <li v-for="(x, i) in d.risks" :key="`r-${d.key}-${i}`">{{ x }}</li>
                  </ul>
                </div>
                <div class="dimension-col">
                  <h4>建议</h4>
                  <ul>
                    <li v-for="(x, i) in d.suggestions" :key="`g-${d.key}-${i}`">{{ x }}</li>
                  </ul>
                </div>
              </div>
            </article>
          </div>
        </details>
      </section>

      <section class="report-group">
        <h3>优点</h3>
        <ul>
          <li v-for="(item, idx) in interviewReport.strengths" :key="`s-${idx}`">{{ item }}</li>
        </ul>
      </section>

      <section class="report-group">
        <h3>待改进点</h3>
        <ul>
          <li v-for="(item, idx) in interviewReport.weaknesses" :key="`w-${idx}`">{{ item }}</li>
        </ul>
      </section>

      <section class="report-group">
        <h3>提升建议</h3>
        <ul>
          <li v-for="(item, idx) in interviewReport.suggestions" :key="`g-${idx}`">{{ item }}</li>
        </ul>
      </section>
    </aside>

    <footer class="iv-input">
      <div class="row">
        <textarea
          v-model="inputText"
          rows="3"
          placeholder="输入你的回答，Enter 发送，Shift+Enter 换行"
          @keydown.enter.exact.prevent="sendText"
          :disabled="connecting || sending || generatingReport || interviewEnded"
        />
      </div>
      <div class="row actions">
        <button
          class="ghost"
          :disabled="connecting || sending || generatingReport || interviewEnded || !speechAvailable"
          :title="speechMode === 'browser' ? '浏览器语音识别（无需 OpenAI）' : '录音并转写'"
          @click="toggleRecord"
        >
          {{ recording ? '停止录音并转写' : (speechMode === 'browser' ? '开始语音输入' : '开始录音') }}
        </button>
        <button :disabled="connecting || sending || generatingReport || interviewEnded || !inputText.trim()" @click="sendText">发送</button>
      </div>
      <div class="hint">{{ statusText }}</div>
    </footer>
  </section>
</template>

<script>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RadarChart from '../components/RadarChart.vue'
import CodingPanel from '../components/CodingPanel.vue'
import {
  createInterview,
  evaluateInterview,
  fetchInterviewCapabilities,
  openInterviewWs,
  transcribeAudioFile,
  authGetResume,
  authUploadResume,
  analyzeRepo,
  fetchRagQuestions
} from '../services/api'
import { computeRadarDimensions, findReportByIdMerged, saveInterviewReport } from '../services/reportStore'
import { getCurrentUser, isLoggedIn } from '../services/authStore'
import { createBrowserSpeechRecognizer, isBrowserSpeechSupported } from '../utils/browserSpeech'

function fmtTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function uid() {
  return Math.random().toString(36).slice(2)
}

function asTextArray(v) {
  if (Array.isArray(v)) return v.map(x => String(x))
  if (typeof v === 'string' && v.trim()) return [v.trim()]
  return []
}

function parseApiDetail(err) {
  const raw = err?.message || String(err || '')
  try {
    const obj = JSON.parse(raw)
    if (obj?.detail?.code || obj?.detail?.message) return obj.detail
    if (typeof obj?.detail === 'string') return { message: obj.detail, code: null }
  } catch {
    // not json
  }
  return { message: raw, code: null }
}

function formatCountdown(secs) {
  const n = Math.max(0, Number(secs) || 0)
  const m = Math.floor(n / 60)
  const s = n % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function dimensionItemsFromReport(report) {
  const dims = report?.dimensions || {}
  const weights = report?.weights || {}
  const config = [
    { key: 'technical_depth', label: '技术深度' },
    { key: 'problem_solving', label: '问题分析' },
    { key: 'communication', label: '表达清晰' },
    { key: 'engineering', label: '工程实践' },
    { key: 'potential', label: '综合潜力' }
  ]

  return config.map((item) => {
    const dim = dims?.[item.key] || {}
    const score = Number.isFinite(Number(dim.score)) ? Number(dim.score) : 0
    const evidence = asTextArray(dim.evidence)
    const risks = asTextArray(dim.risks)
    const suggestions = asTextArray(dim.suggestions)
    return {
      key: item.key,
      label: item.label,
      score,
      weight: weights?.[item.key],
      evidence: evidence.length ? evidence : ['暂无'],
      risks: risks.length ? risks : ['暂无'],
      suggestions: suggestions.length ? suggestions : ['暂无']
    }
  })
}

export default {
  name: 'Interviews',
  components: { RadarChart, CodingPanel },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const selectedRole = ref('Java后端')
    const focusArea = ref('综合')
    const interviewMode = ref('practice')
    const difficulty = ref(3)
    const timeLimit = ref(30)
    const configVisible = ref(true)
    const configConfirmed = ref(false)
    const inputText = ref('')
    const messages = ref([])

    const speechAvailable = ref(false)
    const serverSpeechAvailable = ref(false)
    const browserSpeechAvailable = ref(isBrowserSpeechSupported())
    const speechMode = ref('none') // server | browser | none
    const llmAvailable = ref(false)
    const remainingSeconds = ref(0)
    const timerInterval = ref(null)
    const timeExpired = ref(false)
    const timeWarned = ref(false)
    const maxRounds = ref(5)
    const currentRound = ref(0)
    const interviewPhase = ref('core')
    const phaseLabel = ref('核心追问')
    const interviewStrategyLabel = ref('')
    const interviewStrategy = ref('')
    const codingChallenge = ref(null)
    const lastFollowups = ref([])
    const repoUrl = ref('')
    const repoAnalysis = ref(null)
    const repoAnalyzing = ref(false)
    const enableCoding = ref(false)
    const codingVisible = ref(false)
    const codingCompleted = ref(false)
    const seedQuestionId = ref('')
    const seedQuestionTitle = ref('')

    const statusText = ref('正在准备会话...')
    const connecting = ref(false)
    const sending = ref(false)
    const streaming = ref(false)

    const interviewId = ref('')
    const wsRef = ref(null)
    const aiBuffer = ref('')
    const aiStreamingMessageId = ref('')

    const scrollRef = ref(null)

    const recording = ref(false)
    const browserRecognizerRef = ref(null)
    const liveTranscript = ref('')
    const recorderRef = ref(null)
    const chunksRef = ref([])

    const resumeSummary = ref('')
    const resumeKeywords = ref([])
    const resumeFileName = ref('')
    const resumeUploading = ref(false)
    const resumeInputRef = ref(null)
    const useResume = ref(true)

    const currentUser = ref(getCurrentUser())

    const generatingReport = ref(false)
    const interviewEnded = ref(false)
    const reportVisible = ref(false)
    const interviewReport = ref(null)
    const radarData = ref([])

    function closeWs() {
      if (wsRef.value) {
        wsRef.value.close()
        wsRef.value = null
      }
    }

    function stopTimer() {
      if (timerInterval.value) {
        clearInterval(timerInterval.value)
        timerInterval.value = null
      }
    }

    function startTimer() {
      stopTimer()
      timeExpired.value = false
      timeWarned.value = false
      const limit = Number(timeLimit.value)
      if (!Number.isFinite(limit) || limit <= 0) {
        remainingSeconds.value = 0
        return
      }
      remainingSeconds.value = Math.floor(limit * 60)
      timerInterval.value = setInterval(() => {
        if (interviewEnded.value || generatingReport.value) {
          stopTimer()
          return
        }
        if (remainingSeconds.value <= 0) {
          stopTimer()
          onTimeExpired()
          return
        }
        remainingSeconds.value -= 1
        if (remainingSeconds.value === 60 && !timeWarned.value) {
          timeWarned.value = true
          statusText.value = '还剩 1 分钟，请准备收尾你的回答。'
        }
      }, 1000)
    }

    async function onTimeExpired() {
      if (timeExpired.value || interviewEnded.value || generatingReport.value) return
      timeExpired.value = true
      statusText.value = '时间到，正在自动生成报告...'
      await endInterviewAndGenerateReport()
    }

    function applyOpeningMessage(opening) {
      if (!opening?.text) {
        messages.value = [{
          id: uid(),
          sender: 'ai',
          text: '你好，我是你的 AI 面试官。请开始作答，我会根据你的回答继续追问。',
          time: fmtTime(),
          role: selectedRole.value,
          ragCount: 0
        }]
        return
      }
      messages.value = [{
        id: uid(),
        sender: 'ai',
        text: opening.text,
        time: fmtTime(),
        role: opening.role || selectedRole.value,
        ragCount: opening.rag_sourced ? 1 : 0
      }]
    }

    function refreshSpeechMode() {
      if (serverSpeechAvailable.value) {
        speechMode.value = 'server'
        speechAvailable.value = true
      } else if (browserSpeechAvailable.value) {
        speechMode.value = 'browser'
        speechAvailable.value = true
      } else {
        speechMode.value = 'none'
        speechAvailable.value = false
      }
    }

    async function loadCapabilities() {
      try {
        const cap = await fetchInterviewCapabilities()
        serverSpeechAvailable.value = Boolean(cap?.speech_to_text)
        llmAvailable.value = Boolean(cap?.llm)
      } catch {
        serverSpeechAvailable.value = false
        llmAvailable.value = false
      }
      browserSpeechAvailable.value = isBrowserSpeechSupported()
      refreshSpeechMode()
    }

    async function scrollToBottom() {
      await nextTick()
      const el = scrollRef.value
      if (el) el.scrollTop = el.scrollHeight
    }

    function onWsMessage(data) {
      if (data.type === 'ai_stream') {
        streaming.value = true
        aiBuffer.value += data.chunk || ''

        if (!aiStreamingMessageId.value) {
          const id = uid()
          aiStreamingMessageId.value = id
          messages.value.push({
            id,
            sender: 'ai',
            text: aiBuffer.value,
            time: fmtTime(),
            role: null,
            ragCount: 0
          })
        } else {
          const i = messages.value.findIndex(x => x.id === aiStreamingMessageId.value)
          if (i >= 0) messages.value[i].text = aiBuffer.value
        }
        scrollToBottom()
        return
      }

      if (data.type === 'ai_done') {
        streaming.value = false
        const i = messages.value.findIndex(x => x.id === aiStreamingMessageId.value)
        if (i >= 0) {
          messages.value[i].text = data.text || aiBuffer.value
          messages.value[i].role = data.role || null
          messages.value[i].ragCount = data.rag_context_count || 0
        }

        applyRoundState(data)
        lastFollowups.value = Array.isArray(data.followups) ? data.followups : []

        if (data.coding_offer?.challenge) {
          codingChallenge.value = data.coding_offer.challenge
          codingCompleted.value = false
          if (data.coding_offer.auto_open) {
            codingVisible.value = true
          }
          const cTitle = data.coding_offer.challenge.title || '代码题'
          messages.value.push({
            id: uid(),
            sender: 'ai',
            text: `根据当前面试进度，请完成一道代码题：「${cTitle}」。右侧代码面板已打开，请选择语言、编写代码，可先「测试样例」再「提交评估」。`,
            time: fmtTime(),
            role: selectedRole.value,
            ragCount: 0
          })
        }

        aiStreamingMessageId.value = ''
        aiBuffer.value = ''
        refreshStatusText()
        sending.value = false
        scrollToBottom()
      }
    }

    function applyFollowup(text) {
      if (!text || interviewEnded.value) return
      inputText.value = text
    }

    function applyRoundState(data) {
      if (Number.isFinite(Number(data.round_index))) {
        currentRound.value = Number(data.round_index)
      }
      if (Number.isFinite(Number(data.max_rounds))) {
        maxRounds.value = Number(data.max_rounds)
      }
      if (data.strategy) {
        interviewStrategy.value = data.strategy
      }
      if (data.strategy_label) {
        interviewStrategyLabel.value = data.strategy_label
      }
      if (data.phase) {
        interviewPhase.value = data.phase
      } else if (interviewStrategy.value === 'repo_led' && currentRound.value <= maxRounds.value) {
        interviewPhase.value = 'repo'
      } else if (interviewStrategy.value === 'resume_led' && currentRound.value <= maxRounds.value) {
        interviewPhase.value = 'resume'
      }
      if (data.phase_label) {
        phaseLabel.value = data.phase_label
      } else if (interviewPhase.value === 'repo') {
        phaseLabel.value = '仓库深挖'
      } else if (interviewPhase.value === 'resume') {
        phaseLabel.value = '简历深挖'
      }
    }

    function refreshStatusText() {
      if (interviewPhase.value === 'resume') {
        statusText.value = `简历深挖 ${currentRound.value}/${maxRounds.value} 轮，请结合项目经历作答。`
      } else if (interviewPhase.value === 'repo') {
        statusText.value = `仓库深挖 ${currentRound.value}/${maxRounds.value} 轮，请结合仓库与项目作答。`
      } else if (interviewPhase.value === 'core') {
        statusText.value = `核心追问 ${currentRound.value}/${maxRounds.value} 轮，可继续回答。`
      } else {
        statusText.value = `${phaseLabel.value} · 第 ${currentRound.value} 轮，可继续回答或主动结束面试。`
      }
    }

    function parseApiError(err) {
      const raw = err?.message || String(err)
      try {
        const parsed = JSON.parse(raw)
        if (typeof parsed.detail === 'string') return parsed.detail
        if (Array.isArray(parsed.detail)) {
          return parsed.detail.map(d => d.msg || JSON.stringify(d)).join('；')
        }
      } catch {
        /* not JSON */
      }
      return raw
    }

    async function analyzeRepoPreview() {
      const url = repoUrl.value.trim()
      if (!url) return
      repoAnalyzing.value = true
      try {
        repoAnalysis.value = await analyzeRepo(url)
      } catch (err) {
        const msg = parseApiError(err)
        repoAnalysis.value = {
          error: err?.status === 404
            ? '仓库分析接口不可用，请重启或重建后端（docker compose build backend && docker compose up -d backend）'
            : msg
        }
      } finally {
        repoAnalyzing.value = false
      }
    }

    function onCodingSubmitted(payload) {
      codingChallenge.value = null
      codingCompleted.value = true
      const ev = payload?.evaluation || {}
      const title = payload?.challenge?.title || '代码题'
      const score = ev.score != null ? ev.score : '-'
      messages.value.push({
        id: uid(),
        sender: 'user',
        text: `【代码实战提交】${title}\n运行评估：${ev.feedback || '已提交'}\n得分：${score}`,
        time: fmtTime()
      })
      messages.value.push({
        id: uid(),
        sender: 'ai',
        text: ev.feedback
          ? `收到你的代码提交（${title}，${score} 分）。${ev.feedback}`
          : `收到你的代码提交（${title}）。`,
        time: fmtTime(),
        role: selectedRole.value,
        ragCount: 0
      })
      scrollToBottom()
    }

    function onCodingChallengeChanged(challenge) {
      codingChallenge.value = challenge || null
      if (challenge?.title) {
        codingCompleted.value = false
      }
    }

    async function startInterview() {
      connecting.value = true
      statusText.value = '正在创建面试会话...'
      try {
        const userId = currentUser.value?.id || undefined
        const res = await createInterview({
          user_id: userId,
          role: selectedRole.value,
          focus: focusArea.value,
          mode: interviewMode.value,
          difficulty: Number(difficulty.value) || 3,
          time_limit: Number(timeLimit.value) || null,
          use_resume: useResume.value,
          resume_summary: useResume.value ? (resumeSummary.value || undefined) : undefined,
          resume_keywords: useResume.value && resumeKeywords.value.length
            ? resumeKeywords.value
            : undefined,
          seed_question_id: seedQuestionId.value || undefined,
          repo_url: repoUrl.value.trim() || undefined,
          enable_coding: enableCoding.value
        })
        interviewId.value = res.id
        maxRounds.value = Number(res.max_rounds) || 5
        currentRound.value = 0
        enableCoding.value = Boolean(res.enable_coding ?? res.opening?.enable_coding)
        codingVisible.value = false
        codingCompleted.value = false
        if (res.repo_analysis && !res.repo_analysis.error) {
          repoAnalysis.value = res.repo_analysis
        }
        interviewStrategyLabel.value = res.opening?.strategy_label || ''
        interviewStrategy.value = res.opening?.strategy || ''
        codingChallenge.value = null
        codingCompleted.value = false
        const st = res.opening?.strategy
        if (st === 'resume_led') {
          interviewPhase.value = 'resume'
          phaseLabel.value = '简历深挖'
        } else if (st === 'repo_led') {
          interviewPhase.value = 'repo'
          phaseLabel.value = '仓库深挖'
        } else {
          interviewPhase.value = 'core'
          phaseLabel.value = '核心追问'
        }
        lastFollowups.value = []
        applyOpeningMessage(res.opening)
        startTimer()

        closeWs()
        wsRef.value = openInterviewWs(interviewId.value, {
          onOpen: () => {
            if (st === 'resume_led') {
              statusText.value = '连接成功，面试官将先基于你的简历提问。'
            } else if (st === 'repo_led') {
              statusText.value = '连接成功，面试官将先基于你的 Git 仓库提问。'
            } else if (st === 'seed_question') {
              statusText.value = '连接成功，已从题库带入指定首题。'
            } else if (res.opening?.rag_sourced) {
              statusText.value = '连接成功，已为你抽取岗位首题。'
            } else {
              statusText.value = '连接成功，开始对话。'
            }
            connecting.value = false
          },
          onClose: () => {
            statusText.value = '连接已断开。'
          },
          onError: () => {
            statusText.value = '连接错误，请稍后重试。'
            connecting.value = false
          },
          onMessage: onWsMessage
        })
      } catch (err) {
        connecting.value = false
        statusText.value = `会话创建失败：${err.message || err}`
      }
    }

    async function loadResumeForUser() {
      if (!isLoggedIn()) return
      try {
        const res = await authGetResume()
        resumeSummary.value = res?.summary || ''
        resumeKeywords.value = Array.isArray(res?.keywords) ? res.keywords : []
        resumeFileName.value = res?.file_name || ''
      } catch {
        // ignore
      }
    }

    function pickResumeFile() {
      resumeInputRef.value && resumeInputRef.value.click()
    }

    async function onResumeSelected(evt) {
      const file = evt.target.files && evt.target.files[0]
      evt.target.value = ''
      if (!file) return
      if (!isLoggedIn()) {
        statusText.value = '请先登录后再上传简历。'
        return
      }

      resumeUploading.value = true
      try {
        const res = await authUploadResume(file)
        resumeSummary.value = res?.summary || ''
        resumeKeywords.value = Array.isArray(res?.keywords) ? res.keywords : []
        resumeFileName.value = res?.file_name || ''
      } catch (err) {
        statusText.value = `简历上传失败：${err.message || err}`
      } finally {
        resumeUploading.value = false
      }
    }

    async function confirmConfig() {
      configConfirmed.value = true
      configVisible.value = false
      if (useResume.value) {
        await loadResumeForUser()
      }
      await startInterview()
      scrollToBottom()
    }

    function skipConfig() {
      useResume.value = false
      confirmConfig()
    }

    function exitConfig() {
      if (connecting.value) return
      closeWs()
      stopTimer()
      if (window.history.length > 1) {
        router.back()
      } else {
        router.push('/')
      }
    }

    async function restartInterview() {
      stopTimer()
      interviewEnded.value = false
      generatingReport.value = false
      reportVisible.value = false
      interviewReport.value = null
      radarData.value = []
      timeExpired.value = false
      interviewPhase.value = 'core'
      phaseLabel.value = '核心追问'
      interviewStrategyLabel.value = ''
      interviewStrategy.value = ''
      codingChallenge.value = null
      codingVisible.value = false
      codingCompleted.value = false
      currentRound.value = 0
      lastFollowups.value = []
      messages.value = []
      aiBuffer.value = ''
      aiStreamingMessageId.value = ''
      await startInterview()
    }

    async function endInterviewAndGenerateReport() {
      if (!interviewId.value || generatingReport.value) return

      generatingReport.value = true
      statusText.value = '正在结束面试并生成报告...'

      try {
        stopTimer()
        if (wsRef.value && wsRef.value.readyState === WebSocket.OPEN) {
          closeWs()
        }

        const transcript = messages.value
          .map(m => `[${m.sender}] ${m.text}`)
          .join('\n')
        const res = await evaluateInterview(interviewId.value, {
          transcript,
          role: selectedRole.value,
          focus: focusArea.value,
          mode: interviewMode.value,
          difficulty: Number(difficulty.value) || 3,
          time_limit: Number(timeLimit.value) || null,
          messages: messages.value.map(m => ({
            sender: m.sender,
            text: m.text,
            time: m.time,
            role: m.role || null,
            ragCount: m.ragCount || 0
          }))
        })
        const score = Number.isFinite(Number(res?.score)) ? Number(res.score) : 0
        const strengths = asTextArray(res?.strengths)
        const weaknesses = asTextArray(res?.weaknesses)
        const suggestions = asTextArray(res?.suggestions)

        interviewReport.value = {
          score,
          strengths: strengths.length ? strengths : ['暂无'],
          weaknesses: weaknesses.length ? weaknesses : ['暂无'],
          suggestions: suggestions.length ? suggestions : ['暂无'],
          dimensions: res?.dimensions || {},
          weights: res?.weights || {},
          summary: res?.summary || '',
          evaluation_source: res?.evaluation_source || ''
        }

        radarData.value = computeRadarDimensions(interviewReport.value)

        const reportId = res?._report_id ? String(res._report_id) : `${Date.now()}-${interviewId.value}`
        saveInterviewReport({
          id: reportId,
          interviewId: interviewId.value,
          role: selectedRole.value,
          focus: focusArea.value,
          mode: interviewMode.value,
          difficulty: Number(difficulty.value) || 3,
          timeLimit: Number(timeLimit.value) || null,
          createdAt: new Date().toISOString(),
          transcript: messages.value.map(m => ({
            sender: m.sender,
            text: m.text,
            time: m.time,
            role: m.role || null,
            ragCount: m.ragCount || 0
          })),
          report: interviewReport.value,
          radar: radarData.value
        })

        reportVisible.value = true
        interviewEnded.value = true

        messages.value.push({
          id: uid(),
          sender: 'ai',
          text: `面试已结束。你的综合得分为 ${score} 分，结构化报告已生成。`,
          time: fmtTime(),
          role: selectedRole.value,
          ragCount: 0
        })
        statusText.value = '报告已生成。可点击“重置会话”开始新一轮面试。'
        scrollToBottom()
      } catch (err) {
        statusText.value = `生成报告失败：${err.message || err}`
      } finally {
        generatingReport.value = false
      }
    }

    function sendPayloadByWs(content) {
      if (!wsRef.value || wsRef.value.readyState !== WebSocket.OPEN) {
        throw new Error('WebSocket 未连接')
      }
      wsRef.value.send(JSON.stringify({
        type: 'user_message',
        role: selectedRole.value,
        focus: focusArea.value,
        mode: interviewMode.value,
        difficulty: String(difficulty.value),
        time_limit: Number(timeLimit.value) || null,
        resume_summary: useResume.value ? resumeSummary.value : null,
        resume_keywords: useResume.value ? resumeKeywords.value : null,
        strategy: interviewStrategy.value || undefined,
        strategy_label: interviewStrategyLabel.value || undefined,
        repo_analysis: repoAnalysis.value || undefined,
        enable_coding: enableCoding.value,
        max_rounds: maxRounds.value,
        content
      }))
    }

    async function sendText() {
      const text = inputText.value.trim()
      if (!text || sending.value || connecting.value || generatingReport.value || interviewEnded.value) return

      messages.value.push({
        id: uid(),
        sender: 'user',
        text,
        time: fmtTime()
      })
      inputText.value = ''
      sending.value = true
      statusText.value = 'AI 思考中...'
      scrollToBottom()

      try {
        sendPayloadByWs(text)
      } catch (err) {
        sending.value = false
        statusText.value = `发送失败：${err.message || err}`
      }
    }

    async function submitTranscriptText(text) {
      const trimmed = (text || '').trim()
      if (!trimmed || !interviewId.value || interviewEnded.value) {
        sending.value = false
        statusText.value = trimmed ? statusText.value : '未识别到语音内容。'
        return
      }
      messages.value.push({
        id: uid(),
        sender: 'user',
        text: trimmed,
        time: fmtTime()
      })
      statusText.value = '已转写，AI 思考中...'
      scrollToBottom()
      sendPayloadByWs(trimmed)
    }

    function stopBrowserRecognition() {
      if (browserRecognizerRef.value) {
        try {
          browserRecognizerRef.value.stop()
        } catch {
          browserRecognizerRef.value.abort()
        }
      }
    }

    async function handleAudioBlob(blob, filename = 'record.wav') {
      if (!interviewId.value || interviewEnded.value) return
      sending.value = true
      statusText.value = '语音转写中...'

      try {
        const file = new File([blob], filename, { type: blob.type || 'audio/wav' })
        const res = await transcribeAudioFile(interviewId.value, file)
        const text = (res.transcript || '').trim()

        if (!text) {
          sending.value = false
          statusText.value = '未识别到语音内容。'
          return
        }

        await submitTranscriptText(text)
      } catch (err) {
        sending.value = false
        const detail = parseApiDetail(err)
        if (detail.code === 'SPEECH_NOT_CONFIGURED' || err?.status === 503) {
          serverSpeechAvailable.value = false
          refreshSpeechMode()
          statusText.value = detail.message || '服务端语音未配置，可尝试浏览器语音输入。'
        } else if (detail.code === 'SPEECH_ENDPOINT_NOT_FOUND' || detail.code === 'SPEECH_AUTH_FAILED') {
          serverSpeechAvailable.value = false
          refreshSpeechMode()
          statusText.value = detail.message || '服务端语音不可用，可尝试浏览器语音输入。'
        } else {
          statusText.value = `语音处理失败：${detail.message || err.message || err}`
        }
      }
    }

    async function toggleRecord() {
      if (recording.value) {
        recording.value = false
        if (speechMode.value === 'browser') {
          stopBrowserRecognition()
          sending.value = true
          statusText.value = '语音识别收尾中...'
          const text = browserRecognizerRef.value?.getFinalText() || liveTranscript.value
          browserRecognizerRef.value = null
          liveTranscript.value = ''
          await submitTranscriptText(text)
          return
        }
        if (recorderRef.value && recorderRef.value.state !== 'inactive') recorderRef.value.stop()
        return
      }

      if (!speechAvailable.value) {
        statusText.value = '当前浏览器不支持语音识别，请使用文字输入。'
        return
      }

      if (speechMode.value === 'browser') {
        const recognizer = createBrowserSpeechRecognizer({
          onPartial: ({ display }) => {
            liveTranscript.value = display
            if (display) statusText.value = `识别中：${display.slice(0, 40)}${display.length > 40 ? '…' : ''}`
          },
          onError: (code) => {
            if (code === 'not-allowed') {
              statusText.value = '请允许麦克风权限后重试。'
            } else if (code !== 'aborted') {
              statusText.value = `语音识别失败：${code}`
            }
            recording.value = false
            browserRecognizerRef.value = null
          }
        })
        if (!recognizer) {
          statusText.value = '当前浏览器不支持 Web Speech API，请使用 Chrome 或 Edge。'
          return
        }
        browserRecognizerRef.value = recognizer
        liveTranscript.value = ''
        try {
          recognizer.start()
          recording.value = true
          statusText.value = '正在听写（浏览器识别，无需 OpenAI）… 说完后点击停止。'
        } catch (err) {
          browserRecognizerRef.value = null
          statusText.value = `无法启动语音识别：${err.message || err}`
        }
        return
      }

      if (!navigator.mediaDevices || !window.MediaRecorder) {
        statusText.value = '当前浏览器不支持录音，请使用文字输入。'
        return
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const rec = new MediaRecorder(stream)
        recorderRef.value = rec
        chunksRef.value = []

        rec.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) chunksRef.value.push(e.data)
        }

        rec.onstop = async () => {
          stream.getTracks().forEach(t => t.stop())
          const blob = new Blob(chunksRef.value, { type: 'audio/webm' })
          await handleAudioBlob(blob, 'record.webm')
        }

        rec.start()
        recording.value = true
        statusText.value = '录音中，点击“停止录音并转写”提交。'
      } catch (err) {
        statusText.value = `无法开始录音：${err.message || err}`
      }
    }

    onMounted(async () => {
      const replayId = route.query?.replay
      if (replayId) {
        const record = await findReportByIdMerged(String(replayId))
        if (record) {
          configConfirmed.value = true
          configVisible.value = false
          selectedRole.value = record.role || selectedRole.value
          focusArea.value = record.focus || focusArea.value
          interviewMode.value = record.mode || interviewMode.value
          difficulty.value = Number(record.difficulty || difficulty.value)
          timeLimit.value = Number(record.timeLimit || timeLimit.value)
          const transcript = Array.isArray(record.transcript) ? record.transcript : []
          if (transcript.length) {
            messages.value = transcript.map((m, idx) => ({
              id: uid() + idx,
              sender: m.sender || 'ai',
              text: m.text || '',
              time: m.time || fmtTime(),
              role: m.role || null,
              ragCount: m.ragCount || 0
            }))
          }

          interviewReport.value = record.report || null
          radarData.value = record.radar || computeRadarDimensions(record.report || {})
          reportVisible.value = Boolean(record.report)
          interviewEnded.value = true
          statusText.value = '已回放历史上下文。点击“重置会话”可开始新一轮面试。'
          await scrollToBottom()
          return
        }
      }
      await loadCapabilities()
      const presetRole = route.query?.role
      if (typeof presetRole === 'string' && presetRole.trim()) {
        selectedRole.value = presetRole.trim()
      }
      const qid = route.query?.question_id
      if (typeof qid === 'string' && qid.trim()) {
        seedQuestionId.value = qid.trim()
        try {
          const items = await fetchRagQuestions({ role: selectedRole.value })
          const found = (items || []).find(x => String(x.id) === seedQuestionId.value)
          if (found) {
            seedQuestionTitle.value = found.title || found.body?.slice(0, 40) || ''
            if (found.role) selectedRole.value = found.role
          }
        } catch {
          // ignore
        }
      }
      if (selectedRole.value === 'Python算法' || Number(difficulty.value) >= 4) {
        enableCoding.value = true
      }
      configVisible.value = true
    })

    onBeforeUnmount(() => {
      stopTimer()
      stopBrowserRecognition()
      closeWs()
    })

    return {
      selectedRole,
      focusArea,
      interviewMode,
      difficulty,
      timeLimit,
      configVisible,
      configConfirmed,
      inputText,
      messages,
      statusText,
      connecting,
      sending,
      streaming,
      generatingReport,
      interviewEnded,
      reportVisible,
      interviewReport,
      radarData,
      interviewId,
      scrollRef,
      recording,
      resumeSummary,
      resumeKeywords,
      resumeFileName,
      resumeUploading,
      resumeInputRef,
      useResume,
      restartInterview,
      endInterviewAndGenerateReport,
      sendText,
      confirmConfig,
      skipConfig,
      exitConfig,
      pickResumeFile,
      onResumeSelected,
      toggleRecord,
      dimensionItems: dimensionItemsFromReport,
      speechAvailable,
      serverSpeechAvailable,
      speechMode,
      llmAvailable,
      remainingSeconds,
      timeExpired,
      formatCountdown,
      maxRounds,
      currentRound,
      interviewPhase,
      phaseLabel,
      interviewStrategyLabel,
      repoUrl,
      repoAnalysis,
      repoAnalyzing,
      enableCoding,
      codingVisible,
      codingCompleted,
      seedQuestionId,
      seedQuestionTitle,
      analyzeRepoPreview,
      onCodingSubmitted,
      onCodingChallengeChanged,
      lastFollowups,
      applyFollowup
    }
  }
}
</script>

<style scoped>
.iv-wrap {
  position: fixed;
  inset: 0;
  z-index: 1200;
  width: 100vw;
  height: 100vh;
  display: grid;
  grid-template-rows: auto 1fr auto;
  grid-template-columns: 1fr;
  gap: 12px;
  padding: 18px 20px 22px;
  background:
    radial-gradient(circle at 85% 12%, rgba(20, 184, 166, 0.12), transparent 42%),
    radial-gradient(circle at 12% 90%, rgba(14, 165, 233, 0.12), transparent 45%),
    linear-gradient(180deg, #f5fcff 0%, #ffffff 100%);
}

.config-mask {
  position: fixed;
  inset: 0;
  z-index: 1300;
  background: rgba(10, 42, 54, 0.38);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 24px 18px;
}

.config-card {
  width: min(720px, 94vw);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  overscroll-behavior: contain;
  background: #fff;
  border-radius: 18px;
  border: 1px solid rgba(37, 89, 214, 0.16);
  box-shadow: 0 18px 50px rgba(26, 58, 112, 0.12);
  padding: 18px 20px;
  display: grid;
  gap: 12px;
  font-family: inherit;
  margin: auto 0;
}

.config-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.config-head-text {
  flex: 1;
  min-width: 0;
}

.config-exit-btn {
  flex-shrink: 0;
}

.config-card h2 {
  margin: 0;
  font-size: 18px;
  color: #1a4699;
}

.config-card p {
  margin: 4px 0 0;
  color: #587091;
  font-size: 13px;
  line-height: 1.6;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.config-grid label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: #4f6688;
}

.config-grid input,
.config-grid select {
  border: 1px solid rgba(37, 89, 214, 0.2);
  border-radius: 10px;
  padding: 8px 10px;
  font-family: inherit;
  font-size: 14px;
}

.resume-block {
  border: 1px solid rgba(37, 89, 214, 0.14);
  border-radius: 14px;
  padding: 14px 16px;
  background: #f7faff;
  display: grid;
  gap: 12px;
}

.resume-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.resume-head h3 {
  margin: 0;
  font-size: 16px;
  color: #1a4699;
}

.resume-desc {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: #587091;
}

.toggle {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #4f6688;
  white-space: nowrap;
}

.resume-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.resume-actions .muted {
  font-size: 12px;
  color: #5f7392;
}

.resume-hint {
  font-size: 12px;
  color: #5f7392;
}

.repo-block {
  border: 1px solid rgba(37, 89, 214, 0.14);
  border-radius: 14px;
  padding: 14px 16px;
  background: #f7faff;
  display: grid;
  gap: 12px;
}

.repo-block h3 {
  margin: 0;
  font-size: 16px;
  color: #1a4699;
}

.repo-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.repo-input {
  flex: 1;
  min-width: 200px;
  border: 1px solid rgba(37, 89, 214, 0.2);
  border-radius: 10px;
  padding: 8px 10px;
  font-family: inherit;
  font-size: 14px;
}

.repo-error {
  margin: 0;
  font-size: 12px;
  color: #b42318;
}

.seed-hint {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: #edf3ff;
  border: 1px solid rgba(37, 89, 214, 0.16);
  font-size: 13px;
  color: #4f6688;
}

.seed-hint b {
  color: #1a4699;
}

.coding-toggle {
  padding: 10px 12px;
  border-radius: 10px;
  background: #f7faff;
  border: 1px solid rgba(37, 89, 214, 0.12);
}

.resume-meta {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) minmax(0, 2fr);
  gap: 10px;
}

.resume-meta-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #edf3ff;
  border: 1px solid rgba(37, 89, 214, 0.12);
}

.resume-meta-item.full {
  grid-column: span 2;
}

.resume-meta-label {
  font-size: 12px;
  letter-spacing: .04em;
  color: #587091;
}

.resume-meta-value {
  font-size: 14px;
  line-height: 1.6;
  color: #1a2636;
  word-break: break-word;
}

.resume-keyword-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.resume-keyword-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: #1d4ed8;
  background: #fff;
  border: 1px solid rgba(37, 99, 235, 0.22);
}

.config-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.config-actions-right {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-left: auto;
}

.speech-hint {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.5;
}

.config-hint {
  background: #fff7ed;
  border: 1px solid rgba(234, 88, 12, 0.25);
  color: #9a3412;
}

.muted-hint {
  background: #eff6ff;
  border-color: rgba(37, 89, 214, 0.18);
  color: #1d4ed8;
}

.timer-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  background: #ecfdf5;
  color: #0f766e;
  border: 1px solid rgba(15, 118, 110, 0.25);
  white-space: nowrap;
}

.timer-badge.urgent {
  background: #fff7ed;
  color: #c2410c;
  border-color: rgba(234, 88, 12, 0.35);
  animation: timer-pulse 1.2s ease infinite;
}

.timer-badge.expired {
  background: #fef2f2;
  color: #b91c1c;
  border-color: rgba(220, 38, 38, 0.35);
}

.strategy-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: #e7efff;
  color: #1a4699;
  border: 1px solid rgba(37, 89, 214, 0.2);
  white-space: nowrap;
}

.round-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid rgba(37, 99, 235, 0.22);
  white-space: nowrap;
}

.round-badge.extended {
  background: #f0fdf4;
  color: #15803d;
  border-color: rgba(22, 163, 74, 0.3);
}

.round-badge.resume {
  background: #fdf4ff;
  color: #7e22ce;
  border-color: rgba(126, 34, 206, 0.28);
}

.round-badge.repo {
  background: #fff7ed;
  color: #c2410c;
  border-color: rgba(194, 65, 12, 0.28);
}

.coding-btn.pending {
  border-color: #f59e0b;
  color: #b45309;
  animation: coding-pulse 1.6s ease-in-out infinite;
}

@keyframes coding-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.2); }
  50% { box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.18); }
}

.followup-panel {
  margin: 8px 12px 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f0f9ff;
  border: 1px solid rgba(14, 116, 144, 0.16);
}

.followup-label {
  display: block;
  font-size: 12px;
  color: #4f6b7b;
  margin-bottom: 8px;
}

.followup-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.followup-chip {
  background: #fff;
  color: #0f766e;
  border: 1px solid rgba(15, 118, 110, 0.25);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}

.followup-chip:hover {
  background: #ecfdf5;
}

@keyframes timer-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.72; }
}

.iv-header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 12px;
}

.iv-header h1 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0.3px;
}

.iv-header p {
  margin: 4px 0 0;
  color: #4f6b7b;
  font-size: 13px;
}

.iv-controls {
  display: flex;
  align-items: end;
  gap: 10px;
}

.close-btn {
  background: transparent;
  border: 1px solid rgba(13, 148, 136, 0.24);
  color: #0f766e;
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-right: 8px;
}

.report-btn {
  background: linear-gradient(90deg, #0f766e, #0891b2);
  color: #fff;
  border: 0;
  border-radius: 10px;
  padding: 8px 14px;
}

.iv-controls label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: #4f6b7b;
}

.iv-controls select {
  min-width: 150px;
}

.report-panel {
  position: fixed;
  right: 20px;
  top: 86px;
  bottom: 130px;
  width: min(390px, 94vw);
  background: #fff;
  border: 1px solid rgba(13, 148, 136, 0.18);
  border-radius: 14px;
  box-shadow: 0 16px 44px rgba(14, 116, 144, 0.18);
  padding: 14px;
  overflow: auto;
}

.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.report-head h2 {
  margin: 0;
  font-size: 18px;
}

.score-block {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: end;
  gap: 8px;
  border: 1px solid rgba(13, 148, 136, 0.14);
  border-radius: 12px;
  padding: 10px;
  margin-bottom: 10px;
}

.score-label {
  color: #4f6b7b;
  font-size: 13px;
}

.score-value {
  font-size: 36px;
  font-weight: 700;
  color: #0f766e;
  line-height: 1;
}

.score-sub {
  color: #5f7a8c;
  font-size: 13px;
  padding-bottom: 4px;
}

.report-group {
  margin-top: 10px;
}

.report-group h3 {
  margin: 0 0 6px;
  font-size: 14px;
  color: #0f766e;
}

.dimension-toggle {
  border: 1px solid rgba(13, 148, 136, 0.14);
  border-radius: 12px;
  padding: 8px 10px;
  background: #fff;
}

.dimension-toggle summary {
  cursor: pointer;
  list-style: none;
  font-weight: 600;
  color: #0f766e;
}

.dimension-toggle summary::-webkit-details-marker {
  display: none;
}

.dimension-toggle summary::before {
  content: '▸';
  display: inline-block;
  margin-right: 6px;
  transition: transform 0.2s ease;
}

.dimension-toggle[open] summary::before {
  transform: rotate(90deg);
}

.summary-text {
  margin: 0;
  color: #3a5665;
  line-height: 1.5;
}

.dimension-grid {
  display: grid;
  gap: 10px;
}

.dimension-card {
  border: 1px solid rgba(13, 148, 136, 0.16);
  border-radius: 12px;
  padding: 10px;
  background: #fff;
}

.dimension-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  color: #0f766e;
}

.dimension-meta {
  display: inline-flex;
  gap: 8px;
  align-items: baseline;
}

.dimension-score {
  font-size: 16px;
  font-weight: 700;
  color: #0f766e;
}

.dimension-weight {
  font-size: 12px;
  color: #5f7a8c;
}

.dimension-body {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.dimension-col h4 {
  margin: 0 0 4px;
  font-size: 12px;
  color: #4f6b7b;
}

.dimension-col ul {
  margin: 0;
  padding-left: 18px;
}

.report-group ul {
  margin: 0;
  padding-left: 18px;
}

.report-group li {
  color: #3a5665;
  margin-bottom: 5px;
  line-height: 1.5;
}

.iv-messages {
  overflow: auto;
  padding: 18px 12px 8px 12px;
  scroll-behavior: smooth;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.iv-messages.with-report {
  padding: 18px min(420px, 36vw) 8px 12px;
}

.msg {
  display: flex;
}

.msg.user {
  justify-content: flex-end;
}

.msg.ai {
  justify-content: flex-start;
}

.bubble {
  max-width: min(72ch, 76%);
  border-radius: 14px;
  padding: 12px 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg.ai .bubble {
  background: #ffffff;
  border: 1px solid rgba(13, 148, 136, 0.16);
}

.msg.user .bubble {
  background: linear-gradient(135deg, #0f766e 0%, #0891b2 100%);
  color: #fff;
}

.meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  opacity: 0.85;
}

.small {
  opacity: 0.75;
}

.trace {
  margin-top: 4px;
  font-size: 12px;
  color: #4f6b7b;
}

.typing {
  font-size: 13px;
  color: #4f6b7b;
  margin: 6px 4px;
  animation: pulse 1.1s ease infinite;
}

.iv-input {
  border-top: 1px solid rgba(13, 148, 136, 0.12);
  padding-top: 12px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.6), rgba(255, 255, 255, 0.9));
}

.row {
  display: flex;
  gap: 10px;
}

textarea {
  width: 100%;
  border-radius: 12px;
  border: 1px solid rgba(13, 148, 136, 0.22);
  background: #fff;
  padding: 10px 12px;
}

.iv-input .actions button:last-child {
  background: linear-gradient(90deg, #0f766e, #0891b2);
  color: #fff;
  border: none;
  padding: 8px 14px;
  border-radius: 10px;
}

.actions {
  margin-top: 10px;
  justify-content: flex-end;
}

button.ghost {
  background: #fff;
  color: #0f766e;
  border: 1px solid rgba(13, 148, 136, 0.22);
}

.hidden {
  display: none;
}

.hint {
  margin-top: 8px;
  color: #4f6b7b;
  font-size: 12px;
}

@keyframes pulse {
  0% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.45;
  }
}

@media (max-width: 860px) {
  .iv-wrap {
    height: 100vh;
    padding: 8px;
  }

  .iv-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .iv-controls {
    width: 100%;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .bubble {
    max-width: 95%;
  }

  .report-panel {
    position: fixed;
    left: 8px;
    right: 8px;
    width: auto;
    top: 70px;
    bottom: 90px;
  }

  .iv-messages {
    padding: 12px 8px;
  }
  .config-grid {
    grid-template-columns: 1fr;
  }

  .resume-meta {
    grid-template-columns: 1fr;
  }

  .resume-meta-item.full {
    grid-column: span 1;
  }
}

:global([data-theme="dark"]) .iv-wrap {
  background:
    radial-gradient(circle at 85% 12%, rgba(61, 214, 198, 0.12), transparent 42%),
    radial-gradient(circle at 12% 90%, rgba(122, 162, 255, 0.12), transparent 45%),
    linear-gradient(180deg, #0b111a 0%, #101826 100%);
}
:global([data-theme="dark"]) .config-mask { background: rgba(6, 12, 18, 0.66); }
:global([data-theme="dark"]) .config-card,
:global([data-theme="dark"]) .report-panel {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
  color: #ffffff;
}
:global([data-theme="dark"]) .config-card p,
:global([data-theme="dark"]) .iv-header p,
:global([data-theme="dark"]) .report-group li,
:global([data-theme="dark"]) .summary-text {
  color: #ffffff;
}
:global([data-theme="dark"]) .config-grid input,
:global([data-theme="dark"]) .config-grid select,
:global([data-theme="dark"]) textarea {
  background: rgba(18, 26, 38, 0.7);
  color: #e5e7eb;
  border-color: rgba(122, 162, 255, 0.28);
}
:global([data-theme="dark"]) .config-card h2,
:global([data-theme="dark"]) .resume-head h3 {
  color: #ffffff;
}
:global([data-theme="dark"]) .resume-block,
:global([data-theme="dark"]) .repo-block,
:global([data-theme="dark"]) .coding-toggle {
  background: rgba(18, 26, 38, 0.8);
  border-color: rgba(122, 162, 255, 0.2);
}
:global([data-theme="dark"]) .repo-block h3,
:global([data-theme="dark"]) .seed-hint b {
  color: #ffffff;
}
:global([data-theme="dark"]) .seed-hint {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
  color: rgba(255, 255, 255, 0.82);
}
:global([data-theme="dark"]) .repo-input {
  background: rgba(18, 26, 38, 0.7);
  color: #e5e7eb;
  border-color: rgba(122, 162, 255, 0.28);
}
:global([data-theme="dark"]) .resume-meta-item {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
}
:global([data-theme="dark"]) .resume-meta-label,
:global([data-theme="dark"]) .resume-meta-value,
:global([data-theme="dark"]) .resume-actions .muted,
:global([data-theme="dark"]) .toggle {
  color: rgba(255, 255, 255, 0.82);
}
:global([data-theme="dark"]) .resume-keyword-chip {
  background: #1d2a40;
  color: #ffffff;
  border-color: rgba(122, 162, 255, 0.28);
}
:global([data-theme="dark"]) .msg.ai .bubble {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.22);
  color: #ffffff;
}
:global([data-theme="dark"]) .msg.user .bubble {
  background: #0f172a;
  color: #ffffff;
}
:global([data-theme="dark"]) .trace,
:global([data-theme="dark"]) .typing,
:global([data-theme="dark"]) .hint {
  color: #ffffff;
}
:global([data-theme="dark"]) .score-value { color: #ffffff; }
:global([data-theme="dark"]) .dimension-card {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
}
:global([data-theme="dark"]) .dimension-head,
:global([data-theme="dark"]) .dimension-score {
  color: #ffffff;
}
:global([data-theme="dark"]) .dimension-toggle {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
}
:global([data-theme="dark"]) .dimension-toggle summary { color: #cdd9ff; }
</style>
