<template>
  <section class="q-wrap">
    <header class="hero card">
      <div>
        <span class="tag">Question Bank</span>
        <h1>岗位题库</h1>
        <p>题目来源于 RAG 题库 CSV，按岗位分类展示，可收藏后在收藏页集中背诵与练习。</p>
      </div>
      <div class="hero-actions">
        <button :class="{ ghost: activeTab !== 'browse' }" @click="goTab('browse')">题库浏览</button>
        <button :class="{ ghost: activeTab !== 'favorites' }" @click="goTab('favorites')">收藏页</button>
      </div>
    </header>

    <section v-if="activeTab === 'browse'" class="browse-layout">
      <aside class="role-panel card">
        <h3>面试岗位</h3>
        <ul>
          <li
            v-for="r in roles"
            :key="r"
            :class="{ active: selectedRole === r }"
            @click="selectedRole = r"
          >
            <span>{{ r }}</span>
            <b>{{ grouped[r]?.length || 0 }}</b>
          </li>
        </ul>
      </aside>

      <div class="content-panel">
        <div class="toolbar card">
          <div>
            <h2>{{ selectedRole || '全部岗位' }}</h2>
            <p>共 {{ displayQuestions.length }} 题</p>
          </div>
          <div class="toolbar-actions">
            <button class="ghost" @click="selectedRole = ''">查看全部</button>
            <button @click="goPractice">进入面试练习</button>
          </div>
        </div>

        <section class="cards-grid">
          <article
            v-for="(q, idx) in displayQuestions"
            :key="q.id"
            class="q-card card stagger-observe"
            :style="staggerStyle(idx)"
          >
            <div class="q-head">
              <div>
                <span class="role-chip">{{ q.role }}</span>
                <h3>{{ q.title }}</h3>
              </div>
              <div class="q-actions">
                <button class="icon-btn fav-btn preview-btn" @click="openPreview(q)" aria-label="放大查看">
                  <MagnifyingGlassIcon class="icon" />
                </button>
                <button class="icon-btn fav-btn" @click="toggleFav(q)" :aria-pressed="isFav(q.id)" :title="isFav(q.id) ? '已收藏' : '收藏'">
                  <StarSolid v-if="isFav(q.id)" class="icon fav-on" />
                  <StarOutline v-else class="icon fav-off" />
                </button>
              </div>
            </div>

            <p class="q-body">{{ q.body }}</p>

            <details>
              <summary>查看标准回答与评分标准</summary>
              <div class="answer">
                <h4>标准回答样例</h4>
                <p>{{ q.standard_answer }}</p>
                <h4>评分标准</h4>
                <p>{{ q.scoring }}</p>
              </div>
            </details>
            <button class="ghost bring-btn" type="button" @click="goPracticeWithQuestion(q)">带入模拟面试</button>
          </article>

          <div v-if="!displayQuestions.length" class="empty card">暂无题目，请确认后端已读取 CSV 题库。</div>
        </section>
      </div>
    </section>

    <section v-else class="favorites-layout">
      <div class="toolbar card">
        <div>
          <h2>收藏题目</h2>
          <p>共 {{ favoriteQuestions.length }} 题，可用于集中背诵。</p>
        </div>
        <div class="toolbar-actions">
          <button class="ghost" @click="clearFavorites" :disabled="!favoriteQuestions.length">清空收藏</button>
          <button @click="goPractice">进入练习</button>
        </div>
      </div>
      <section class="cards-grid">
        <article
          v-for="(q, idx) in favoriteQuestions"
          :key="q.id"
          class="q-card card stagger-observe"
          :style="staggerStyle(idx)"
        >
          <div class="q-head">
            <div>
              <span class="role-chip">{{ q.role }}</span>
              <h3>{{ q.title }}</h3>
            </div>
            <div class="q-actions">
              <button class="icon-btn fav-btn preview-btn" @click="openPreview(q)" aria-label="放大查看">
                <MagnifyingGlassIcon class="icon" />
              </button>
              <button class="icon-btn fav-btn on" @click="toggleFav(q)" title="取消收藏">
                <StarSolid class="icon fav-on" />
              </button>
            </div>
          </div>
          <p class="q-body">{{ q.body }}</p>
          <details>
            <summary>查看标准回答与评分标准</summary>
            <div class="answer">
              <h4>标准回答样例</h4>
              <p>{{ q.standard_answer }}</p>
              <h4>评分标准</h4>
              <p>{{ q.scoring }}</p>
            </div>
          </details>
          <button class="ghost bring-btn" type="button" @click="goPracticeWithQuestion(q)">带入模拟面试</button>
        </article>

        <div v-if="!favoriteQuestions.length" class="empty card">你还没有收藏题目，先去“题库浏览”添加吧。</div>
      </section>
    </section>

    <div v-if="selectedQuestion" class="preview-mask" @click="onPreviewMaskClick">
      <article class="preview-dialog card" @click.stop>
        <header class="preview-head">
          <div>
            <span class="role-chip">{{ selectedQuestion.role }}</span>
            <h2>{{ selectedQuestion.title }}</h2>
          </div>
          <button class="preview-close" @click="closePreview">关闭</button>
        </header>

        <section class="preview-content">
          <h4>题目内容</h4>
          <p>{{ selectedQuestion.body }}</p>
          <h4>标准回答样例</h4>
          <p>{{ selectedQuestion.standard_answer }}</p>
          <h4>评分标准</h4>
          <p>{{ selectedQuestion.scoring }}</p>
        </section>
        <footer class="preview-actions">
          <button type="button" @click="goPracticeWithQuestion(selectedQuestion)">以此题开始模拟面试</button>
        </footer>
      </article>
    </div>
  </section>
</template>

<script>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchRagQuestions, fetchRagRoles } from '../services/api'
import { MagnifyingGlassIcon } from '@heroicons/vue/24/outline'
import { StarIcon as StarOutline } from '@heroicons/vue/24/outline'
import { StarIcon as StarSolid } from '@heroicons/vue/24/solid'

const FAV_KEY = 'question_favorites_v1'

export default {
  components: { MagnifyingGlassIcon, StarOutline, StarSolid },
  name: 'Questions',
  setup() {
    const router = useRouter()
    const route = useRoute()

    const roles = ref([])
    const questions = ref([])
    const selectedRole = ref('')
    const loading = ref(false)

    const favorites = ref({})
    const observerRef = ref(null)
    const selectedQuestion = ref(null)

    const activeTab = computed(() => route.path === '/questions/favorites' ? 'favorites' : 'browse')

    const grouped = computed(() => {
      const m = {}
      for (const q of questions.value) {
        const role = q.role || '未分类'
        if (!m[role]) m[role] = []
        m[role].push(q)
      }
      return m
    })

    const displayQuestions = computed(() => {
      if (!selectedRole.value) return questions.value
      return questions.value.filter(q => q.role === selectedRole.value)
    })

    const favoriteQuestions = computed(() => {
      const ids = new Set(Object.keys(favorites.value).filter(k => favorites.value[k]))
      return questions.value.filter(q => ids.has(String(q.id)))
    })

    function goTab(tab) {
      if (tab === 'favorites') router.push('/questions/favorites')
      else router.push('/questions/browse')
    }

    function loadFavs() {
      try {
        const raw = localStorage.getItem(FAV_KEY)
        favorites.value = raw ? JSON.parse(raw) : {}
      } catch {
        favorites.value = {}
      }
    }

    function saveFavs() {
      localStorage.setItem(FAV_KEY, JSON.stringify(favorites.value))
    }

    function isFav(id) {
      return Boolean(favorites.value[String(id)])
    }

    function toggleFav(q) {
      const k = String(q.id)
      favorites.value[k] = !favorites.value[k]
      saveFavs()
    }

    function clearFavorites() {
      favorites.value = {}
      saveFavs()
    }

    function goPractice() {
      const q = selectedRole.value ? { role: selectedRole.value } : {}
      router.push({ path: '/interviews/practice', query: q })
    }

    function goPracticeWithQuestion(q) {
      if (!q) return
      router.push({
        path: '/interviews/practice',
        query: { role: q.role || selectedRole.value || undefined, question_id: q.id }
      })
    }

    function openPreview(q) {
      selectedQuestion.value = q
    }

    function closePreview() {
      selectedQuestion.value = null
    }

    function onPreviewMaskClick(evt) {
      if (evt.target === evt.currentTarget) {
        closePreview()
      }
    }

    function onEsc(evt) {
      if (evt.key === 'Escape') {
        closePreview()
      }
    }

    function staggerStyle(index) {
      return { '--stagger-index': String(index % 8) }
    }

    async function observeCards() {
      await nextTick()
      const cards = Array.from(document.querySelectorAll('.q-wrap .stagger-observe'))
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

    async function loadQuestions() {
      loading.value = true
      try {
        const [roleRes, qRes] = await Promise.all([fetchRagRoles(), fetchRagQuestions()])
        roles.value = Array.isArray(roleRes?.roles) ? roleRes.roles : []
        questions.value = Array.isArray(qRes?.items) ? qRes.items : []
        if (!selectedRole.value && roles.value.length) selectedRole.value = roles.value[0]
      } finally {
        loading.value = false
      }
    }

    onMounted(async () => {
      window.addEventListener('keydown', onEsc)
      loadFavs()
      await loadQuestions()
      observeCards()
    })

    watch(
      () => [activeTab.value, selectedRole.value, displayQuestions.value.length, favoriteQuestions.value.length],
      () => {
        observeCards()
      }
    )

    onBeforeUnmount(() => {
      window.removeEventListener('keydown', onEsc)
      if (observerRef.value) observerRef.value.disconnect()
    })

    return {
      roles,
      questions,
      grouped,
      loading,
      selectedRole,
      displayQuestions,
      favoriteQuestions,
      activeTab,
      isFav,
      toggleFav,
      clearFavorites,
      goTab,
      goPractice,
      goPracticeWithQuestion,
      staggerStyle,
      selectedQuestion,
      openPreview,
      closePreview,
      onPreviewMaskClick
    }
  }
}
</script>

<style scoped>
.q-wrap { display: grid; gap: 14px; }
.hero { display: flex; justify-content: space-between; align-items: center; gap: 12px; background: linear-gradient(120deg, #eff5ff, #fff); }
.tag { display: inline-flex; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #1f4fb9; background: #e7efff; border-radius: 999px; padding: 4px 10px; }
.hero h1 { margin: 8px 0 0; font-size: 30px; color: #18459a; }
.hero p { margin: 8px 0 0; color: #52698c; }
.hero-actions { display: flex; gap: 8px; }
.ghost { background: #fff; color: #1f4fb9; border: 1px solid rgba(37, 89, 214, 0.2); }

.browse-layout { display: grid; grid-template-columns: 280px 1fr; gap: 12px; }
.role-panel h3 { margin: 0 0 8px; color: #18459a; }
.role-panel ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.role-panel li { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 10px; background: #edf3ff; cursor: pointer; transition: background .2s ease, transform .16s ease; }
.role-panel li:hover { background: #e4eeff; transform: translateX(2px); }
.role-panel li.active { background: #d8e7ff; font-weight: 700; color: #1b4ca8; }
.role-panel b { color: #1f4fb9; }

.content-panel { display: grid; gap: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; }
.toolbar h2 { margin: 0; color: #18459a; }
.toolbar p { margin: 6px 0 0; color: #5d7395; font-size: 13px; }
.toolbar-actions { display: flex; gap: 8px; }

.cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
.q-card { min-height: 240px; display: grid; gap: 10px; align-content: start; }
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
.q-head { display: flex; justify-content: space-between; align-items: start; gap: 8px; }
.q-actions { display: flex; gap: 8px; align-items: center; }
.role-chip { font-size: 12px; color: #1f4fb9; background: #e7efff; border-radius: 999px; padding: 4px 8px; display: inline-flex; }
.q-card h3 { margin: 8px 0 0; color: #18479e; font-size: 18px; }
.icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 10px; background: transparent; cursor: pointer; border: none; color: inherit; }
.icon { width: 16px; height: 16px; }
.icon-btn svg path { fill: currentColor; }
.preview-btn .icon {
  width: 16px;
  height: 16px;
  stroke: currentColor;
  stroke-width: 2.2;
}
.fav-btn { background: transparent; border: none; padding: 0; }
.fav-off { color: #1f4fb9; }
.fav-on { color: #f6c000; }
.q-body { margin: 0; color: #4f6587; line-height: 1.7; }
details { background: #f4f8ff; border-radius: 10px; padding: 8px 10px; }
summary { cursor: pointer; color: #1c4ea9; font-weight: 600; }
.answer h4 { margin: 10px 0 6px; color: #1b4a9f; font-size: 13px; }
.answer p { margin: 0; color: #52698d; font-size: 13px; line-height: 1.6; }
.empty { color: #5d7191; }

.favorites-layout { display: grid; gap: 12px; }

.preview-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 34, 71, 0.48);
  display: grid;
  place-items: center;
  z-index: 80;
  padding: 20px;
}

.preview-dialog {
  width: min(920px, 96vw);
  max-height: 86vh;
  overflow: auto;
  display: grid;
  gap: 14px;
}

.preview-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.preview-head h2 {
  margin: 10px 0 0;
  color: #183f90;
  font-size: 26px;
}

.preview-close {
  background: #fff;
  color: #1f4fb9;
  border: 1px solid rgba(37, 89, 214, 0.24);
}

.preview-content {
  display: grid;
  gap: 10px;
}

.preview-content h4 {
  margin: 0;
  color: #1a478f;
}

.preview-content p {
  margin: 0;
  line-height: 1.8;
  color: #4c6282;
}

.bring-btn {
  width: 100%;
  justify-self: start;
  font-size: 13px;
  padding: 8px 12px;
}

.preview-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid rgba(37, 89, 214, 0.12);
}

.preview-actions button {
  background: #1f4fb9;
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 14px;
  cursor: pointer;
}

.preview-actions button:hover {
  background: #18459a;
}

@media (max-width: 980px) {
  .browse-layout { grid-template-columns: 1fr; }
  .hero { flex-direction: column; align-items: flex-start; }
  .toolbar { flex-direction: column; align-items: flex-start; gap: 10px; }
  .q-actions { flex-wrap: wrap; justify-content: end; }
  .preview-dialog { width: min(96vw, 96vw); max-height: 90vh; }
  .preview-head h2 { font-size: 22px; }
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
:global([data-theme="dark"]) .role-panel li,
:global([data-theme="dark"]) .toolbar,
:global([data-theme="dark"]) .q-card {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
  color: #ffffff;
}
:global([data-theme="dark"]) .role-panel li:hover {
  background: rgba(31, 43, 68, 0.7);
}
:global([data-theme="dark"]) .role-panel li.active {
  background: rgba(47, 99, 223, 0.22);
  color: #cdd9ff;
}
:global([data-theme="dark"]) .fav-off,
:global([data-theme="dark"]) .preview-btn {
  color: #ffffff;
}
:global([data-theme="dark"]) .role-panel b,
:global([data-theme="dark"]) .role-chip,
:global([data-theme="dark"]) .q-card h3,
:global([data-theme="dark"]) summary {
  color: #ffffff;
}
:global([data-theme="dark"]) .role-chip {
  background: #0f172a;
}
:global([data-theme="dark"]) .q-body,
:global([data-theme="dark"]) .answer p,
:global([data-theme="dark"]) .hero p,
:global([data-theme="dark"]) .toolbar p {
  color: #ffffff;
}
:global([data-theme="dark"]) details {
  background: #0f172a;
}
:global([data-theme="dark"]) .preview-mask {
  background: rgba(2, 6, 12, 0.7);
}
:global([data-theme="dark"]) .preview-dialog {
  background: #121a26;
  border-color: rgba(122, 162, 255, 0.18);
  color: #ffffff;
}
:global([data-theme="dark"]) .preview-head h2,
:global([data-theme="dark"]) .preview-content h4 {
  color: #ffffff;
}
:global([data-theme="dark"]) .preview-content p {
  color: #ffffff;
}
:global([data-theme="dark"]) .preview-close {
  background: #0f172a;
  color: #ffffff;
  border-color: rgba(122, 162, 255, 0.22);
}
</style>
