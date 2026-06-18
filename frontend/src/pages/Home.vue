<template>
  <section class="home-wrap">
    <header class="hero card stagger-item" style="--i: 0">
      <div class="hero-copy">
        <span class="tag">Dashboard</span>
        <h1>欢迎回来，{{ displayName }}</h1>
        <p>这里是你的面试训练仪表盘：快捷入口、近期报告和能力维度一览。</p>
      </div>
      <div class="hero-actions">
        <button @click="go('/interviews/practice')">开始面试练习</button>
        <button class="ghost" @click="go('/interviews/history')">查看历史报告</button>
      </div>
    </header>

    <section class="stats">
      <article class="card stat stagger-item" style="--i: 1">
        <span>总用户</span>
        <b>{{ stats.users }}</b>
      </article>
      <article class="card stat stagger-item" style="--i: 2">
        <span>题目数量</span>
        <b>{{ stats.questions }}</b>
      </article>
      <article class="card stat stagger-item" style="--i: 3">
        <span>面试场次</span>
        <b>{{ stats.interviews }}</b>
      </article>
      <article class="card stat stagger-item" style="--i: 4">
        <span>岗位数</span>
        <b>{{ stats.jobs }}</b>
      </article>
    </section>

    <section class="section-title">快捷入口</section>
    <section class="quick-grid">
      <article class="card quick stagger-item" style="--i: 5" @click="go('/interviews/practice')">
        <h3>面试练习</h3>
        <p>进入 AI 面试官对话，支持文字和语音输入。</p>
      </article>
      <article class="card quick stagger-item" style="--i: 6" @click="go('/questions')">
        <h3>题库浏览</h3>
        <p>查看岗位题目与知识点，结合训练计划复盘。</p>
      </article>
      <article class="card quick stagger-item" style="--i: 7" @click="go('/profile')">
        <h3>个人资料</h3>
        <p>维护账号资料、修改密码与管理登录状态。</p>
      </article>
      <article class="card quick stagger-item" style="--i: 8" @click="go('/interviews/history')">
        <h3>历史报告</h3>
        <p>回看近期面试评估，支持对话上下文回放。</p>
      </article>
    </section>

    <section class="section-title">近期分析</section>
    <section class="insights">
      <article class="card recent stagger-item" style="--i: 9">
        <div class="section-head">
          <h2>近期面试记录</h2>
          <button class="ghost" @click="go('/interviews/history')">更多</button>
        </div>

        <div v-if="!recentReports.length" class="empty">暂无记录，先去完成一次面试练习。</div>
        <ul v-else class="recent-list">
          <li v-for="(item, idx) in recentReports" :key="item.id" :style="{ '--i': idx + 10 }" @click="openReplay(item)">
            <span class="role">{{ item.role || '未标注岗位' }}</span>
            <span class="time">{{ formatTime(item.createdAt) }}</span>
            <b class="score">{{ item.report?.score ?? 0 }}</b>
          </li>
        </ul>
      </article>

      <article class="card radar-card stagger-item" style="--i: 10">
        <div class="section-head">
          <h2>近期评分维度雷达图</h2>
        </div>
        <div v-if="latestRadar.length">
          <RadarChart :data="latestRadar" :size="280" />
        </div>
        <div v-else class="empty">暂无评分数据。</div>
      </article>
    </section>
  </section>
</template>

<script>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import RadarChart from '../components/RadarChart.vue'
import { fetchDashboard, health } from '../services/api'
import { getCurrentUser } from '../services/authStore'
import { computeRadarDimensions, loadReportsMerged } from '../services/reportStore'

export default {
  name: 'Home',
  components: { RadarChart },
  setup() {
    const router = useRouter()
    const currentUser = ref(getCurrentUser())
    const displayName = ref(currentUser.value?.name || currentUser.value?.email || '同学')
    const stats = reactive({ users: 0, questions: 0, interviews: 0, jobs: 0 })
    const recentReports = ref([])
    const latestRadar = ref([])

    function go(path) {
      router.push(path)
    }

    function formatTime(t) {
      if (!t) return '-'
      const d = new Date(t)
      if (Number.isNaN(d.getTime())) return String(t)
      return d.toLocaleString('zh-CN', { hour12: false })
    }

    function openReplay(item) {
      router.push({ path: '/interviews/practice', query: { replay: item.id } })
    }

    async function loadStats() {
      try {
        const d = await fetchDashboard()
        stats.users = Number(d.users ?? 0)
        stats.questions = Number(d.questions ?? 0)
        stats.interviews = Number(d.interviews ?? 0)
        stats.jobs = Number(d.jobs ?? 0)
      } catch {
        try {
          const h = await health()
          if (Number.isFinite(Number(h?.rag_questions))) {
            stats.questions = Number(h.rag_questions)
          }
        } catch {
          // keep fallback zeros
        }
      }
    }

    async function loadRecent() {
      const reports = await loadReportsMerged()
      recentReports.value = reports.slice(0, 5)
      if (reports.length > 0) {
        const latest = reports[0]
        latestRadar.value = latest.radar || computeRadarDimensions(latest.report || {})
      }
    }

    onMounted(async () => {
      await loadStats()
      await loadRecent()
    })

    return {
      displayName,
      stats,
      recentReports,
      latestRadar,
      go,
      formatTime,
      openReplay
    }
  }
}
</script>

<style scoped>
.home-wrap { display: grid; gap: 18px; }
.hero {
  display: grid;
  grid-template-columns: 1.2fr auto;
  align-items: center;
  gap: 14px;
  min-height: 180px;
  background:
    radial-gradient(circle at 84% 18%, rgba(37, 89, 214, 0.2), transparent 45%),
    linear-gradient(120deg, #f2f7ff, #ffffff);
}
.hero-copy { max-width: 760px; }
.tag {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #1f4fb9;
  background: #e7efff;
  border-radius: 999px;
  padding: 4px 10px;
}
.hero h1 { margin: 10px 0 0; font-size: clamp(28px, 4.4vw, 42px); line-height: 1.1; color: #153d93; }
.hero p { margin: 10px 0 0; color: #4f6587; max-width: 66ch; }
.hero-actions { display: grid; gap: 10px; min-width: 180px; }
.ghost { background: #fff; color: #1f4fb9; border: 1px solid rgba(37, 89, 214, 0.2); }
.section-title {
  font-size: 14px;
  color: #5c7397;
  letter-spacing: .05em;
  text-transform: uppercase;
  margin-top: 2px;
}
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.stat { min-height: 120px; display: flex; flex-direction: column; justify-content: space-between; }
.stat span { color: #5f7392; font-size: 13px; }
.stat b { display: block; margin-top: 8px; color: #183d8d; font-size: 34px; line-height: 1; }
.quick-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.quick { cursor: pointer; transition: transform .16s ease, box-shadow .16s ease; }
.quick:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(26, 58, 112, 0.14); }
.quick h3 { margin: 0; color: #1b489f; font-size: 20px; }
.quick p { margin: 8px 0 0; color: #526a8d; line-height: 1.6; }
.insights { display: grid; grid-template-columns: 1.3fr 1fr; gap: 12px; }
.section-head { display: flex; justify-content: space-between; align-items: center; }
.section-head h2 { margin: 0; font-size: 18px; color: #194695; }
.empty { color: #5c7191; font-size: 13px; padding: 12px 0; }
.recent-list { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 8px; }
.recent-list li { display: grid; grid-template-columns: 1.2fr 1fr auto; gap: 10px; align-items: center; padding: 11px 12px; border-radius: 12px; background: #edf3ff; cursor: pointer; opacity: 0; transform: translateY(12px); animation: rise-in .52s cubic-bezier(.22,1,.36,1) forwards; animation-delay: calc(var(--i) * 52ms); }
.recent-list li:hover { background: #e4eeff; }
.role { color: #1e4fae; font-weight: 600; }
.time { color: #5a7091; font-size: 12px; }
.score { color: #1b4397; font-size: 20px; }
.radar-card { min-height: 340px; }

.stagger-item {
  opacity: 0;
  transform: translateY(14px);
  animation: rise-in .55s cubic-bezier(.22,1,.36,1) forwards;
  animation-delay: calc(var(--i) * 52ms + 30ms);
}

@keyframes rise-in {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .stagger-item,
  .recent-list li {
    animation: none;
    opacity: 1;
    transform: none;
  }
}

@media (max-width: 980px) {
  .hero { grid-template-columns: 1fr; }
  .hero-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .quick-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .insights { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .hero-actions { grid-template-columns: 1fr; width: 100%; }
  .stats { grid-template-columns: 1fr; }
  .quick-grid { grid-template-columns: 1fr; }
}

:global([data-theme="dark"]) .hero {
  background:
    radial-gradient(circle at 84% 18%, rgba(122, 162, 255, 0.18), transparent 45%),
    linear-gradient(120deg, #121a26, #0f1620);
}
:global([data-theme="dark"]) .recent-list li {
  background: #121a26;
  color: #ffffff;
  border: 1px solid rgba(122, 162, 255, 0.14);
}
:global([data-theme="dark"]) .recent-list li:hover {
  background: #162234;
}
:global([data-theme="dark"]) .role,
:global([data-theme="dark"]) .time,
:global([data-theme="dark"]) .score,
:global([data-theme="dark"]) .empty {
  color: #ffffff;
}
:global([data-theme="dark"]) .tag {
  color: #ffffff;
  background: #1d2a40;
}
:global([data-theme="dark"]) .hero h1,
:global([data-theme="dark"]) .hero p,
:global([data-theme="dark"]) .section-title,
:global([data-theme="dark"]) .stat span,
:global([data-theme="dark"]) .stat b,
:global([data-theme="dark"]) .quick h3,
:global([data-theme="dark"]) .quick p,
:global([data-theme="dark"]) .section-head h2,
:global([data-theme="dark"]) .empty,
:global([data-theme="dark"]) .role,
:global([data-theme="dark"]) .time,
:global([data-theme="dark"]) .score {
  color: #ffffff;
}
:global([data-theme="dark"]) .recent-list li {
  background: #1d2a40;
}
:global([data-theme="dark"]) .recent-list li:hover {
  background: #24324a;
}
:global([data-theme="dark"]) .ghost {
  background: #1d2a40;
  color: #ffffff;
  border-color: rgba(122, 162, 255, 0.28);
}
</style>
