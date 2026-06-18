<template>
  <div id="app-root">
    <Sidebar
      v-if="!isInterviewRoute"
      :collapsed="collapsed"
      @update:collapsed="collapsed = $event"
    />
    <main
      :class="{ 'main-fullscreen': isInterviewRoute }"
      :style="{ marginLeft: isInterviewRoute ? '0px' : sidebarOffset, '--sidebar-offset': isInterviewRoute ? '0px' : sidebarOffset }"
    >
      <header v-if="!isInterviewRoute" class="topbar">
        <div class="topbar-left">
          <div class="brand" @click="go('/')">{{ collapsed ? 'AI' : 'AI 面试平台' }}</div>
          <div class="route-hint">{{ currentSectionLabel }}</div>
        </div>
        <div class="topbar-right">
          <button class="theme-toggle" type="button" :aria-label="isDark ? '切换为浅色' : '切换为深色'" @click="toggleTheme">
            <svg v-if="!isDark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="theme-icon" aria-hidden="true">
              <path fill="currentColor" d="M12 3.5a1 1 0 0 1 1 1v1.6a1 1 0 1 1-2 0V4.5a1 1 0 0 1 1-1Zm0 12a3.5 3.5 0 1 0 0-7a3.5 3.5 0 0 0 0 7Zm0 2a1 1 0 0 1 1 1v1.6a1 1 0 1 1-2 0v-1.6a1 1 0 0 1 1-1Zm8.5-6a1 1 0 0 1 1 1a1 1 0 0 1-1 1h-1.6a1 1 0 1 1 0-2h1.6Zm-12.9 0a1 1 0 0 1 1 1a1 1 0 0 1-1 1H4.5a1 1 0 1 1 0-2h1.1Zm9.26-5.16a1 1 0 0 1 1.41 0l1.13 1.13a1 1 0 1 1-1.41 1.41l-1.13-1.13a1 1 0 0 1 0-1.41Zm-10.12 0a1 1 0 0 1 1.41 1.41L7.02 8.88a1 1 0 1 1-1.41-1.41l1.13-1.13ZM16.84 15.1a1 1 0 0 1 1.41 0l1.13 1.13a1 1 0 1 1-1.41 1.41l-1.13-1.13a1 1 0 0 1 0-1.41Zm-10.12 0a1 1 0 0 1 1.41 1.41l-1.13 1.13a1 1 0 1 1-1.41-1.41l1.13-1.13Z"/>
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="theme-icon" aria-hidden="true">
              <path fill="currentColor" d="M20.2 14.5a1 1 0 0 0-1.12-.3a7 7 0 0 1-9.28-9.28a1 1 0 0 0-1.42-1.12A9 9 0 1 0 20.2 14.5Z"/>
            </svg>
          </button>
          <button class="avatar-button" type="button" aria-label="进入个人中心" @click="go('/profile')">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="avatar-icon" aria-hidden="true">
              <path fill="currentColor" d="M12 12a4 4 0 1 0-4-4a4 4 0 0 0 4 4Zm0 2c-4.2 0-7.5 2.1-7.5 4.7a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1C19.5 16.1 16.2 14 12 14Z"/>
            </svg>
          </button>
        </div>
      </header>
      <div class="page-content" :class="{ 'full-page-chat': isInterviewRoute }">
        <router-view v-slot="{ Component, route }">
          <transition name="page-switch" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'
import { getCurrentUser } from './services/authStore'
export default {
  components: { Sidebar },
  setup(){
    const collapsed = ref(false)
    const width = 220
    const collapsedWidth = 64
    const router = useRouter()
    const route = useRoute()
    const currentUser = ref(getCurrentUser())
    const isInterviewRoute = computed(() => route.path === '/interviews' || route.path === '/interviews/practice')
    const currentSectionLabel = computed(() => {
      const p = route.path || '/'
      if (p.startsWith('/interviews')) return '面试训练'
      if (p.startsWith('/questions')) return '题库管理'
      if (p.startsWith('/profile')) return '个人中心'
      return '数据总览'
    })
    const displayUserName = computed(() => currentUser.value?.name || currentUser.value?.email || '游客')
    const displayUserLetter = computed(() => String(displayUserName.value || 'U').slice(0, 1).toUpperCase())
    const sidebarOffset = computed(() => (collapsed.value ? collapsedWidth : width) + 'px')
    function go(p){ router.push(p) }

    const isDark = ref(false)
    const applyTheme = () => {
      const root = document.documentElement
      const themeValue = isDark.value ? 'dark' : 'light'
      root.setAttribute('data-theme', themeValue)
      document.body.setAttribute('data-theme', themeValue)
      try {
        window.localStorage.setItem('theme', themeValue)
      } catch (e) {}
    }
    const toggleTheme = () => {
      isDark.value = !isDark.value
    }

    const refreshUser = () => { currentUser.value = getCurrentUser() }
    onMounted(() => {
      window.addEventListener('storage', refreshUser)
      window.addEventListener('focus', refreshUser)

      try {
        const saved = window.localStorage.getItem('theme')
        if (saved === 'dark') isDark.value = true
        if (saved === 'light') isDark.value = false
        if (!saved && window.matchMedia) {
          isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
        }
      } catch (e) {}
      applyTheme()
    })
    onBeforeUnmount(() => {
      window.removeEventListener('storage', refreshUser)
      window.removeEventListener('focus', refreshUser)
    })

    watch(isDark, () => {
      applyTheme()
    })

    return { collapsed, width, collapsedWidth, isInterviewRoute, currentSectionLabel, displayUserName, displayUserLetter, sidebarOffset, go, isDark, toggleTheme }
  }
}
</script>

<style>
main{padding:20px 0;transition:margin-left .25s cubic-bezier(.22,1,.36,1)}
.main-fullscreen{padding:0;min-height:100vh}
#app-root{display:block}
.topbar-left{display:flex;flex-direction:row;align-items:baseline;gap:10px;line-height:1.2}
.topbar-left .brand{cursor:pointer}
.route-hint{font-size:13px;color:var(--muted);margin-top:0;white-space:nowrap}

.page-switch-enter-active,
.page-switch-leave-active{
  transition: opacity .22s ease, transform .22s ease;
}
.page-switch-enter-from,
.page-switch-leave-to{
  opacity: 0;
  transform: translateY(8px);
}
</style>
