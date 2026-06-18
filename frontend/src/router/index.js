import { createRouter, createWebHistory } from 'vue-router'
import Home from '../pages/Home.vue'
import Auth from '../pages/Auth.vue'
import Interviews from '../pages/Interviews.vue'
import InterviewsHistory from '../pages/InterviewsHistory.vue'
import Questions from '../pages/Questions.vue'
import Profile from '../pages/Profile.vue'
import Resume from '../pages/Resume.vue'
import { isLoggedIn } from '../services/authStore'

const routes = [
  { path: '/', component: Home },
  { path: '/auth', component: Auth, meta: { guestOnly: true } },
  { path: '/profile', redirect: '/profile/info' },
  { path: '/profile/info', component: Profile, meta: { requiresAuth: true } },
  { path: '/profile/resume', component: Resume, meta: { requiresAuth: true } },
  { path: '/interviews', redirect: '/interviews/practice' },
  { path: '/interviews/practice', component: Interviews },
  { path: '/interviews/history', component: InterviewsHistory },
  { path: '/questions', redirect: '/questions/browse' },
  { path: '/questions/browse', component: Questions },
  { path: '/questions/favorites', component: Questions },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !isLoggedIn()) {
    return { path: '/auth', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && isLoggedIn() && to.path === '/auth') {
    return { path: '/' }
  }
  return true
})

export default router
