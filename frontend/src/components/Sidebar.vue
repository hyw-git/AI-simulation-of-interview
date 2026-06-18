<template>
  <aside :class="['sidebar', { collapsed }]" aria-label="主导航">
    <nav class="sidebar-nav">
      <div v-for="item in links" :key="item.to" class="sidebar-item">
        <router-link :to="item.to" class="sidebar-link" :class="{ selected: isSelected(item.to) }">
          <span class="active-dot" aria-hidden="true"></span>
          <span class="icon"><component :is="item.iconComponent" class="icon-svg" /></span>
          <span v-if="!collapsed" class="label">{{ item.label }}</span>
        </router-link>

            <div v-if="item.children && !collapsed" class="children">
              <router-link v-for="c in item.children" :key="c.to" :to="c.to" class="sidebar-child"
                :class="{ selected: isSelected(c.to) }">
                <span class="child-icon"><component :is="c.iconComponent" class="child-icon-svg" /></span>
                <span class="child-label">{{ c.label }}</span>
              </router-link>
            </div>
      </div>
    </nav>

    <div class="sidebar-bottom">
      <el-button :class="['collapse-btn', { 'no-border': collapsed }]" @click="toggle" type="text">
        <span v-if="collapsed" class="collapse-svg" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
        </span>
        <span v-else class="collapse-svg" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
        </span>
      </el-button>
    </div>
  </aside>
</template>

<script>
import { HomeIcon, PlayIcon, BookOpenIcon, ClockIcon, StarIcon, BookmarkSquareIcon, UserCircleIcon, IdentificationIcon, DocumentTextIcon } from '@heroicons/vue/24/outline'

export default {
  name: 'Sidebar',
  props: { collapsed: { type: Boolean, default: false } },
  emits: ['update:collapsed'],
  data(){
    return {
      links: [
        { to: '/', label: '首页', iconComponent: HomeIcon },
        { to: '/interviews', label: '面试', iconComponent: PlayIcon, children: [ { to: '/interviews/practice', label:'练习', iconComponent: BookmarkSquareIcon }, { to: '/interviews/history', label:'历史', iconComponent: ClockIcon } ] },
        { to: '/questions', label: '题库', iconComponent: BookOpenIcon, children: [ { to: '/questions/browse', label:'浏览', iconComponent: BookOpenIcon }, { to: '/questions/favorites', label:'收藏', iconComponent: StarIcon } ] },
        { to: '/profile', label: '个人中心', iconComponent: UserCircleIcon, children: [ { to: '/profile/info', label:'账号与安全', iconComponent: IdentificationIcon }, { to: '/profile/resume', label:'简历管理', iconComponent: DocumentTextIcon } ] }
      ],
      selectedPath: '/'
    }
  },
  watch: {
    '$route.path': {
      immediate: true,
      handler(path) {
        this.selectedPath = path || '/'
      }
    }
  },
  
  methods: {
    toggle(){ this.$emit('update:collapsed', !this.collapsed) },
    go(p){ this.$router.push(p) },
    isSelected(path){
      if (path === '/') {
        return this.selectedPath === '/'
      }
      return this.selectedPath === path || this.selectedPath.startsWith(path + '/')
    }
  }
}
</script>

<style scoped>
.collapse-btn{border-radius:12px}
.sidebar-top{display:flex;align-items:center;justify-content:space-between;padding:0}
.nav-caption{display:none}
.active-dot{width:6px;height:6px;border-radius:999px;background:transparent;transition:background .2s ease, transform .2s ease}
.sidebar-link.selected .active-dot{background:var(--sidebar-active-text);transform:scale(1.2)}
.icon-svg, .child-icon-svg{width:18px;height:18px;display:inline-block}
.icon-svg path, .child-icon-svg path{stroke:currentColor}

@media (max-width: 920px){
  .nav-caption{display:none}
}
</style>
