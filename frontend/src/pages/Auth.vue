<template>
  <section class="auth-wrap">
    <article class="auth-card">
      <div class="intro">
        <span class="tag">Account Center</span>
        <h1>{{ mode === 'login' ? '账号登录' : '注册账号' }}</h1>
        <p>登录后可管理个人资料、同步历史报告，并在首页查看训练看板。</p>
      </div>

      <form @submit.prevent="submit">
        <label>邮箱</label>
        <input v-model.trim="form.email" type="email" required placeholder="you@example.com" />

        <label v-if="mode === 'register'">昵称</label>
        <input v-if="mode === 'register'" v-model.trim="form.name" type="text" placeholder="请输入昵称" />

        <label>密码</label>
        <input v-model="form.password" type="password" required minlength="6" placeholder="至少 6 位" />

        <button type="submit" :disabled="loading">{{ loading ? '提交中...' : (mode === 'login' ? '登录' : '注册并登录') }}</button>
      </form>

      <p class="tip">{{ message }}</p>

      <div class="switch">
        <span>{{ mode === 'login' ? '还没有账号？' : '已有账号？' }}</span>
        <button class="link-btn" @click="toggleMode">{{ mode === 'login' ? '去注册' : '去登录' }}</button>
      </div>
    </article>
  </section>
</template>

<script>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authLogin, authMe, authRegister } from '../services/api'
import { setCurrentUser, setToken, setRefreshToken } from '../services/authStore'

export default {
  name: 'Auth',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const mode = ref('login')
    const loading = ref(false)
    const message = ref('')
    const form = reactive({ email: '', password: '', name: '' })

    function toggleMode() {
      mode.value = mode.value === 'login' ? 'register' : 'login'
      message.value = ''
    }

    async function submit() {
      loading.value = true
      message.value = ''
      try {
        if (mode.value === 'register') {
          await authRegister({ email: form.email, password: form.password, name: form.name || undefined })
        }

        const loginRes = await authLogin({ email: form.email, password: form.password })
        setToken(loginRes.access_token || '')
        setRefreshToken(loginRes.refresh_token || '')

        try {
          const me = await authMe()
          setCurrentUser(me)
        } catch {
          setCurrentUser({ email: form.email, name: form.name || '用户' })
        }

        const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
        message.value = '登录成功，正在跳转...'
        setTimeout(() => router.push(redirect), 250)
      } catch (err) {
        message.value = `操作失败：${err.message || err}`
      } finally {
        loading.value = false
      }
    }

    return { mode, loading, message, form, toggleMode, submit }
  }
}
</script>

<style scoped>
.auth-wrap { min-height: calc(100vh - 90px); display: grid; place-items: center; }
.auth-card {
  width: min(880px, 96%);
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 18px;
  background: #fff;
  border-radius: 18px;
  border: 1px solid rgba(37, 89, 214, 0.16);
  padding: 20px;
}
.intro {
  border-radius: 14px;
  padding: 16px;
  background:
    radial-gradient(circle at 90% 10%, rgba(37, 89, 214, 0.2), transparent 44%),
    linear-gradient(160deg, #eef5ff, #ffffff);
}
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
.auth-card h1 { margin: 8px 0 0; font-size: 30px; color: #18459a; }
.auth-card p { margin: 10px 0 14px; color: #52698c; line-height: 1.6; }
form { display: grid; gap: 10px; align-content: start; }
label { font-size: 13px; color: #4f6688; }
input { border: 1px solid rgba(37, 89, 214, 0.2); border-radius: 10px; padding: 10px 12px; }
button { margin-top: 8px; }
.tip { min-height: 20px; font-size: 13px; color: #2151b3; }
.switch { display: flex; gap: 8px; align-items: center; font-size: 13px; color: #5b7192; }
.link-btn { margin: 0; padding: 0; background: transparent; color: #2151b3; border: none; cursor: pointer; }

@media (max-width: 860px) {
  .auth-card { grid-template-columns: 1fr; }
}
</style>
