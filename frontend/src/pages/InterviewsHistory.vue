<template>
  <section class="history-wrap">
    <header class="history-head card hero">
      <div>
        <span class="tag">History</span>
        <h1>面试历史记录</h1>
        <p>支持回看结构化评分与维度雷达图。</p>
      </div>
      <button class="ghost" @click="clearAll">清空本地缓存</button>
    </header>

    <section v-if="trendPoints.length" class="trend-card card">
      <div class="trend-head">
        <div class="trend-title">
          <h3>近期表现</h3>
          <span class="trend-sub">最近 {{ trendPoints.length }} 场 · 综合得分</span>
        </div>
        <div class="trend-stats">
          <span class="stat-chip">均分 <b>{{ trendAverage }}</b></span>
          <span v-if="trendDelta !== null" class="stat-chip">
            变化
            <b :class="trendDelta >= 0 ? 'delta-up' : 'delta-down'">
              {{ trendDelta >= 0 ? '+' : '' }}{{ trendDelta }}
            </b>
          </span>
          <span v-if="trendBest !== null" class="stat-chip">最高 <b>{{ trendBest }}</b></span>
        </div>
      </div>
      <ScoreTrendChart :points="trendPoints" />
    </section>

    <div v-if="!records.length" class="empty">暂无历史报告。请先在面试练习页完成一轮并生成报告。</div>

    <div v-else class="grid">
      <article
        v-for="(item, idx) in records"
        :key="item.id"
        class="card stagger-observe"
        :style="staggerStyle(idx)"
        @click="openDetail(item)"
      >
        <div class="card-row">
          <span class="role">{{ item.role || '未标注岗位' }}</span>
          <b class="score">{{ item.report?.score ?? 0 }}</b>
        </div>
        <div class="meta">{{ formatTime(item.createdAt) }}</div>
        <div class="meta-line">
          <span>模式：{{ formatMode(item.mode) }}</span>
          <span>难度：{{ item.difficulty ?? '-' }}</span>
          <span>时长：{{ formatTimeLimit(item.timeLimit) }}</span>
        </div>
        <div class="dim-chips">
          <span v-for="d in dimensionOverview(item.report)" :key="d.key" class="dim-chip">
            {{ d.label }} {{ d.score }} · {{ d.weightLabel }}
          </span>
        </div>
        <div class="chips">
          <span v-for="(s, idx) in (item.report?.strengths || []).slice(0, 2)" :key="idx" class="chip">{{ s }}</span>
        </div>
        <div class="record-actions">
          <button class="ghost small-btn" type="button" @click.stop="startEdit(item)">编辑</button>
          <button class="danger small-btn" type="button" @click.stop="removeRecord(item)">删除</button>
        </div>
      </article>
    </div>

    <div v-if="selected" class="overlay" @click.self="selected = null">
      <div class="panel">
        <header class="panel-head">
          <h2>{{ selected.role }} · 报告回看</h2>
          <div class="panel-actions">
            <button class="ghost" @click="replayContext(selected)">回放到该次对话上下文</button>
            <button class="ghost" @click="startEdit(selected)">编辑</button>
            <button class="danger" @click="removeRecord(selected)">删除</button>
            <button class="ghost" @click="selected = null">关闭</button>
          </div>
        </header>

        <div class="score-line">
          <span>综合得分</span>
          <b>{{ selected.report?.score ?? 0 }}</b>
        </div>

        <div class="meta-line detail-meta">
          <span>模式：{{ formatMode(selected.mode) }}</span>
          <span>难度：{{ selected.difficulty ?? '-' }}</span>
          <span>时长：{{ formatTimeLimit(selected.timeLimit) }}</span>
        </div>

        <RadarChart :data="selected.radar || computedRadar(selected.report)" :size="280" />

        <section class="group">
          <details class="dimension-toggle" open>
            <summary>维度详解</summary>
            <div class="dimension-grid">
              <article v-for="d in dimensionItems(selected.report)" :key="d.key" class="dimension-card">
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

        <section class="group">
          <h3>优点</h3>
          <ul>
            <li v-for="(x, i) in (selected.report?.strengths || [])" :key="`s-${i}`">{{ x }}</li>
          </ul>
        </section>

        <section class="group">
          <h3>待改进点</h3>
          <ul>
            <li v-for="(x, i) in (selected.report?.weaknesses || [])" :key="`w-${i}`">{{ x }}</li>
          </ul>
        </section>

        <section class="group">
          <h3>提升建议</h3>
          <ul>
            <li v-for="(x, i) in (selected.report?.suggestions || [])" :key="`g-${i}`">{{ x }}</li>
          </ul>
        </section>
      </div>
    </div>

    <div v-if="editing" class="overlay" @click.self="cancelEdit">
      <form class="panel edit-panel" @submit.prevent="saveEdit">
        <header class="panel-head">
          <h2>编辑历史记录</h2>
          <button class="ghost" type="button" @click="cancelEdit">关闭</button>
        </header>

        <div class="edit-grid">
          <label>
            岗位
            <input v-model.trim="editForm.role" type="text" placeholder="例如 Java后端" />
          </label>
          <label>
            模式
            <select v-model="editForm.mode">
              <option value="practice">练习</option>
              <option value="test">测评</option>
            </select>
          </label>
          <label>
            难度
            <input v-model.number="editForm.difficulty" type="number" min="1" max="5" />
          </label>
          <label>
            时长（分钟）
            <input v-model.number="editForm.timeLimit" type="number" min="0" />
          </label>
          <label>
            综合得分
            <input v-model.number="editForm.score" type="number" min="0" max="100" />
          </label>
          <label>
            关注重点
            <input v-model.trim="editForm.focus" type="text" placeholder="综合/技术深度/项目实践" />
          </label>
        </div>

        <label class="summary-field">
          总结
          <textarea v-model.trim="editForm.summary" rows="4" placeholder="补充或修正本次报告总结" />
        </label>

        <p v-if="editError" class="error-text">{{ editError }}</p>
        <div class="panel-actions edit-actions">
          <button class="ghost" type="button" :disabled="savingEdit" @click="cancelEdit">取消</button>
          <button type="submit" :disabled="savingEdit">{{ savingEdit ? '保存中...' : '保存' }}</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script>
import { nextTick, onBeforeUnmount, onMounted, ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import RadarChart from '../components/RadarChart.vue'
import ScoreTrendChart from '../components/ScoreTrendChart.vue'
import {
  clearInterviewReports,
  computeRadarDimensions,
  deleteInterviewReport,
  loadReportsMerged,
  updateInterviewReport
} from '../services/reportStore'

const TREND_LIMIT = 12

export default {
  name: 'InterviewsHistory',
  components: { RadarChart, ScoreTrendChart },
  setup() {
    const router = useRouter()
    const records = ref([])
    const selected = ref(null)
    const observerRef = ref(null)
    const editing = ref(null)
    const editForm = ref({
      role: '',
      focus: '',
      mode: 'practice',
      difficulty: 3,
      timeLimit: 0,
      score: 0,
      summary: ''
    })
    const savingEdit = ref(false)
    const editError = ref('')

    const trendPoints = computed(() => {
      const sorted = [...records.value]
        .filter(r => Number.isFinite(Number(r?.report?.score)))
        .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
      const slice = sorted.slice(-TREND_LIMIT)
      return slice.map((item, idx) => {
        const d = new Date(item.createdAt)
        const valid = !Number.isNaN(d.getTime())
        const shortLabel = valid
          ? d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
          : `#${idx + 1}`
        const fullLabel = [
          valid ? d.toLocaleString('zh-CN', { hour12: false }) : shortLabel,
          item.role || '未标注岗位'
        ].join(' · ')
        return {
          shortLabel,
          fullLabel,
          value: Number(item.report?.score) || 0
        }
      })
    })

    const trendAverage = computed(() => {
      if (!trendPoints.value.length) return '-'
      const sum = trendPoints.value.reduce((acc, p) => acc + p.value, 0)
      return Math.round(sum / trendPoints.value.length)
    })

    const trendBest = computed(() => {
      if (!trendPoints.value.length) return null
      return Math.max(...trendPoints.value.map(p => p.value))
    })

    const trendDelta = computed(() => {
      const pts = trendPoints.value
      if (pts.length < 2) return null
      return pts[pts.length - 1].value - pts[0].value
    })

    function formatTime(t) {
      if (!t) return '-'
      const d = new Date(t)
      if (Number.isNaN(d.getTime())) return String(t)
      return d.toLocaleString('zh-CN', { hour12: false })
    }

    function formatMode(v) {
      if (v === 'practice') return '练习'
      if (v === 'test') return '测评'
      return '-'
    }

    function formatTimeLimit(v) {
      const n = Number(v)
      if (!Number.isFinite(n) || n <= 0) return '不限'
      return `${n} 分钟`
    }

    function openDetail(item) {
      selected.value = item
    }

    function computedRadar(report) {
      return computeRadarDimensions(report)
    }

    function asTextArray(v) {
      if (Array.isArray(v)) return v.map(x => String(x))
      if (typeof v === 'string' && v.trim()) return [v.trim()]
      return []
    }

    function dimensionItems(report) {
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

    function dimensionOverview(report) {
      const dims = report?.dimensions || {}
      const weights = report?.weights || {}
      const config = [
        { key: 'technical_depth', label: '技术深度' },
        { key: 'problem_solving', label: '问题分析' },
        { key: 'communication', label: '表达清晰' },
        { key: 'engineering', label: '工程实践' },
        { key: 'potential', label: '综合潜力' }
      ]

      return config
        .map((item) => {
          const dim = dims?.[item.key] || {}
          const score = Number.isFinite(Number(dim.score)) ? Number(dim.score) : 0
          const weight = weights?.[item.key]
          return {
            key: item.key,
            label: item.label,
            score,
            weight,
            weightLabel: weight !== undefined ? `${Math.round(weight * 100)}%` : '-'
          }
        })
        .slice(0, 2)
    }

    function clearAll() {
      clearInterviewReports()
      records.value = []
      selected.value = null
    }

    function startEdit(item) {
      if (!item) return
      editing.value = item
      editError.value = ''
      editForm.value = {
        role: item.role || '',
        focus: item.focus || '',
        mode: item.mode || 'practice',
        difficulty: Number(item.difficulty) || 3,
        timeLimit: Number(item.timeLimit) || 0,
        score: Number(item.report?.score) || 0,
        summary: item.report?.summary || ''
      }
    }

    function cancelEdit() {
      editing.value = null
      editError.value = ''
    }

    async function saveEdit() {
      if (!editing.value) return
      savingEdit.value = true
      editError.value = ''
      try {
        const score = Math.max(0, Math.min(100, Number(editForm.value.score) || 0))
        const patch = {
          role: editForm.value.role || null,
          focus: editForm.value.focus || null,
          mode: editForm.value.mode || 'practice',
          difficulty: Number(editForm.value.difficulty) || 3,
          time_limit: Number(editForm.value.timeLimit) || null,
          timeLimit: Number(editForm.value.timeLimit) || null,
          report: {
            score,
            summary: editForm.value.summary || ''
          },
          score,
          summary: editForm.value.summary || ''
        }
        await updateInterviewReport(editing.value, patch)
        await loadRecords()
        const updated = records.value.find(r => String(r.id) === String(editing.value.id))
        selected.value = updated || selected.value
        editing.value = null
      } catch (err) {
        editError.value = err.message || String(err)
      } finally {
        savingEdit.value = false
      }
    }

    async function removeRecord(item) {
      if (!item) return
      const ok = window.confirm(`确定删除「${item.role || '未标注岗位'}」这条历史记录吗？`)
      if (!ok) return
      try {
        await deleteInterviewReport(item)
        records.value = records.value.filter(r => String(r.id) !== String(item.id))
        if (selected.value && String(selected.value.id) === String(item.id)) {
          selected.value = null
        }
        if (editing.value && String(editing.value.id) === String(item.id)) {
          editing.value = null
        }
      } catch (err) {
        window.alert(`删除失败：${err.message || err}`)
      }
    }

    function staggerStyle(index) {
      return { '--stagger-index': String(index % 8) }
    }

    async function observeCards() {
      await nextTick()
      const cards = Array.from(document.querySelectorAll('.history-wrap .stagger-observe'))
      if (!cards.length) return

      if (!('IntersectionObserver' in window)) {
        cards.forEach((el) => el.classList.add('in-view'))
        return
      }

      if (observerRef.value) {
        observerRef.value.disconnect()
      }

      observerRef.value = new IntersectionObserver(
        (entries, obs) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('in-view')
              obs.unobserve(entry.target)
            }
          })
        },
        {
          root: null,
          rootMargin: '0px 0px -6% 0px',
          threshold: 0.12,
        }
      )

      cards.forEach((el) => {
        el.classList.remove('in-view')
        observerRef.value.observe(el)
      })
    }

    function replayContext(item) {
      if (!item?.id) return
      selected.value = null
      router.push({ path: '/interviews/practice', query: { replay: item.id } })
    }

    async function loadRecords() {
      records.value = await loadReportsMerged()
    }

    onMounted(async () => {
      await loadRecords()
      observeCards()
    })

    watch(
      () => records.value.length,
      () => {
        observeCards()
      }
    )

    onBeforeUnmount(() => {
      if (observerRef.value) observerRef.value.disconnect()
    })

    return {
      records,
      selected,
      trendPoints,
      trendAverage,
      trendBest,
      trendDelta,
      formatTime,
      formatMode,
      formatTimeLimit,
      openDetail,
      clearAll,
      computedRadar,
      replayContext,
      staggerStyle,
      dimensionItems,
      dimensionOverview,
      editing,
      editForm,
      editError,
      savingEdit,
      startEdit,
      cancelEdit,
      saveEdit,
      removeRecord
    }
  }
}
</script>

<style scoped>
.history-wrap { display: grid; gap: 14px; }
.hero { display: flex; justify-content: space-between; align-items: center; gap: 14px; background: linear-gradient(120deg, #eef5ff, #ffffff); }
.tag {
  display: inline-flex;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: #1f4fb9;
  background: #e7efff;
  border-radius: 999px;
  padding: 4px 10px;
}
.history-head h1 { margin: 8px 0 0; font-size: 30px; }
.history-head p { margin: 8px 0 0; color: #52698c; }
.trend-card {
  padding: 12px 14px;
  background: #fff;
  border: 1px solid rgba(37, 89, 214, 0.12);
  border-radius: 12px;
}
.trend-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.trend-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.trend-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1a4699;
}
.trend-sub {
  font-size: 11px;
  color: #8a9bb5;
}
.trend-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.stat-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #6b7f9a;
  padding: 3px 8px;
  border-radius: 999px;
  background: #f4f8ff;
  border: 1px solid rgba(37, 89, 214, 0.1);
}
.stat-chip b {
  color: #1a4699;
  font-size: 12px;
  font-weight: 600;
}
.delta-up { color: #15803d !important; }
.delta-down { color: #b42318 !important; }
.empty { padding: 30px; border: 1px dashed rgba(37, 89, 214, 0.26); border-radius: 12px; color: #557092; background: #fff; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
.card { background: #fff; border: 1px solid rgba(37, 89, 214, 0.15); border-radius: 14px; padding: 16px; cursor: pointer; min-height: 140px; }
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(26, 58, 112, 0.14); }
.stagger-observe {
  opacity: 0;
  transform: translateY(12px);
  transition:
    opacity .44s cubic-bezier(.22, 1, .36, 1),
    transform .44s cubic-bezier(.22, 1, .36, 1);
  transition-delay: calc(var(--stagger-index, 0) * 44ms);
}
.stagger-observe.in-view {
  opacity: 1;
  transform: translateY(0);
}
.card-row { display: flex; justify-content: space-between; align-items: center; }
.role { color: #1f4fb9; font-weight: 600; }
.score { font-size: 24px; color: #1a4699; }
.meta { font-size: 12px; color: #607595; margin: 4px 0 8px; }
.meta-line { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: #607595; margin-bottom: 8px; }
.detail-meta { margin: 6px 0 2px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font-size: 12px; padding: 4px 8px; border-radius: 999px; background: #eaf2ff; color: #1f4fb9; }
.dim-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.dim-chip { font-size: 12px; padding: 4px 8px; border-radius: 999px; background: #f0f6ff; color: #315c9a; }
.ghost { background: #fff; color: #1f4fb9; border: 1px solid rgba(37, 89, 214, 0.2); }
.danger { background: #fff; color: #b42318; border: 1px solid rgba(180, 35, 24, 0.24); }
.record-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.small-btn { min-height: 30px; padding: 5px 10px; font-size: 12px; }
.overlay { position: fixed; inset: 0; background: rgba(14, 8, 24, 0.5); z-index: 1100; display: flex; justify-content: center; align-items: center; padding: 10px; }
.panel { width: min(820px, 95vw); max-height: 90vh; overflow: auto; border-radius: 14px; background: #fff; padding: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; }
.panel-head h2 { margin: 0; }
.panel-actions { display: flex; gap: 8px; }
.edit-panel { width: min(680px, 95vw); }
.edit-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.edit-grid label,
.summary-field { display: grid; gap: 6px; color: #52698c; font-size: 13px; }
.edit-grid input,
.edit-grid select,
.summary-field textarea {
  border: 1px solid rgba(37, 89, 214, 0.18);
  border-radius: 10px;
  padding: 9px 10px;
  font: inherit;
  color: #1b2b45;
  background: #fff;
}
.summary-field { margin-top: 12px; }
.edit-actions { justify-content: flex-end; margin-top: 12px; }
.error-text { color: #b42318; margin: 10px 0 0; }
.score-line { display: flex; justify-content: space-between; align-items: baseline; margin: 10px 0 4px; }
.score-line b { font-size: 28px; color: #1a4699; }
.group { margin-top: 10px; }
.group h3 { margin: 0 0 6px; color: #1f4fb9; }
.group ul { margin: 0; padding-left: 18px; }
.group li { margin-bottom: 4px; color: #455f7e; }

.dimension-grid { display: grid; gap: 10px; }
.dimension-card { border: 1px solid rgba(37, 89, 214, 0.18); border-radius: 12px; padding: 10px; background: #fff; }
.dimension-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; color: #1f4fb9; }
.dimension-meta { display: inline-flex; gap: 8px; align-items: baseline; }
.dimension-score { font-size: 16px; font-weight: 700; color: #1f4fb9; }
.dimension-weight { font-size: 12px; color: #607595; }
.dimension-body { display: grid; gap: 8px; margin-top: 8px; }
.dimension-col h4 { margin: 0 0 4px; font-size: 12px; color: #607595; }
.dimension-col ul { margin: 0; padding-left: 18px; }
.dimension-toggle { border: 1px solid rgba(37, 89, 214, 0.16); border-radius: 12px; padding: 8px 10px; background: #fff; }
.dimension-toggle summary { cursor: pointer; list-style: none; font-weight: 600; color: #1f4fb9; }
.dimension-toggle summary::-webkit-details-marker { display: none; }
.dimension-toggle summary::before { content: '▸'; display: inline-block; margin-right: 6px; transition: transform 0.2s ease; }
.dimension-toggle[open] summary::before { transform: rotate(90deg); }

@media (max-width: 860px) {
  .hero { flex-direction: column; align-items: flex-start; }
  .trend-head { flex-direction: column; }
  .edit-grid { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .stagger-observe,
  .stagger-observe.in-view {
    transition: none;
    opacity: 1;
    transform: none;
  }
}

:global([data-theme="dark"]) .hero {
  background: linear-gradient(120deg, #121a26, #0f1620);
}
:global([data-theme="dark"]) .card,
:global([data-theme="dark"]) .trend-card {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
  color: #ffffff;
}
:global([data-theme="dark"]) .empty {
  background: #121a26;
  color: rgba(226, 232, 240, 0.7);
  border-color: rgba(122, 162, 255, 0.2);
}
:global([data-theme="dark"]) .stat-chip {
  background: #0f172a;
  border-color: rgba(122, 162, 255, 0.16);
  color: rgba(226, 232, 240, 0.72);
}
:global([data-theme="dark"]) .chip,
:global([data-theme="dark"]) .dim-chip {
  background: #0f172a;
  color: #ffffff;
}
:global([data-theme="dark"]) .role,
:global([data-theme="dark"]) .score,
:global([data-theme="dark"]) .trend-head h3,
:global([data-theme="dark"]) .stat-chip b,
:global([data-theme="dark"]) .group h3,
:global([data-theme="dark"]) .dimension-head,
:global([data-theme="dark"]) .dimension-score,
:global([data-theme="dark"]) .dimension-toggle summary {
  color: #ffffff;
}
:global([data-theme="dark"]) .meta,
:global([data-theme="dark"]) .meta-line,
:global([data-theme="dark"]) .trend-sub,
:global([data-theme="dark"]) .stat-chip,
:global([data-theme="dark"]) .group li,
:global([data-theme="dark"]) .dimension-weight,
:global([data-theme="dark"]) .dimension-col h4 {
  color: #ffffff;
}
:global([data-theme="dark"]) .overlay {
  background: rgba(2, 6, 12, 0.7);
}
:global([data-theme="dark"]) .panel,
:global([data-theme="dark"]) .dimension-card,
:global([data-theme="dark"]) .dimension-toggle {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
}
:global([data-theme="dark"]) .edit-grid input,
:global([data-theme="dark"]) .edit-grid select,
:global([data-theme="dark"]) .summary-field textarea {
  background: #0f172a;
  color: #ffffff;
  border-color: rgba(122, 162, 255, 0.18);
}
</style>
