<template>
  <section class="profile-wrap">
    <article class="card intro-card">
      <span class="tag">Profile Center</span>
      <h2>账号管理</h2>
      <p class="muted">集中管理个人资料、密码和登录状态，所有信息改动将同步到首页展示。</p>
    </article>

    <section class="account-grid">
      <article class="card info-card">
        <div class="card-head">
          <div>
            <h3>个人信息</h3>
            <p class="muted">维护昵称、邮箱与学校信息。</p>
          </div>
          <button type="button" class="ghost" :disabled="savingProfile" @click="saveProfile">
            {{ savingProfile ? '保存中...' : '保存资料' }}
          </button>
        </div>

        <form class="form-grid" @submit.prevent="saveProfile">
          <label>昵称</label>
          <input v-model.trim="profile.name" placeholder="请输入昵称" />

          <label>邮箱</label>
          <input v-model.trim="profile.email" type="email" placeholder="you@example.com" />

          <label>年级</label>
          <input v-model.number="profile.year" type="number" min="1" max="6" placeholder="例如：3" />

          <label>专业</label>
          <input v-model.trim="profile.major" placeholder="例如：软件工程" />
        </form>
      </article>

      <article class="card pwd-card">
        <div class="card-head">
          <div>
            <h3>密码管理与登录</h3>
            <p class="muted">建议定期更新，提高账号安全性。</p>
          </div>
          <button type="button" :disabled="savingPwd" @click="changePwd">
            {{ savingPwd ? '提交中...' : '更新密码' }}
          </button>
        </div>


        <form class="form-grid" @submit.prevent="changePwd">
          <label>旧密码</label>
          <input v-model="pwd.old_password" type="password" required />

          <label>新密码</label>
          <input v-model="pwd.new_password" type="password" required minlength="6" />
        </form>

        <div class="auth-actions">
          <button class="ghost" @click="goAuth">去登录页</button>
          <button class="danger" @click="doLogout">退出登录</button>
        </div>
      </article>
    </section>

    <article v-if="message" class="card msg-bar">
      <p class="msg">{{ message }}</p>
    </article>
  </section>
</template>

<script>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authChangePassword, authLogout, authMe, authUpdateMe } from '../services/api'
import { getCurrentUser, getRefreshToken, isLoggedIn, logout, setCurrentUser } from '../services/authStore'

export default {
  name: 'Profile',
  setup() {
    const router = useRouter()
    const currentUser = ref(getCurrentUser())
    const profile = reactive({ name: '', email: '', year: null, major: '' })
    const pwd = reactive({ old_password: '', new_password: '' })
    const savingProfile = ref(false)
    const savingPwd = ref(false)
    const message = ref('')

    function fillProfile(user) {
      profile.name = user?.name || ''
      profile.email = user?.email || ''
      profile.year = user?.year ?? null
      profile.major = user?.major || ''
    }

    async function loadMe() {
      if (!isLoggedIn()) {
        message.value = '当前未登录，请先登录。'
        return
      }
      try {
        const me = await authMe()
        setCurrentUser(me)
        currentUser.value = me
        fillProfile(me)
      } catch {
        fillProfile(currentUser.value)
      }
    }

    async function saveProfile() {
      if (!isLoggedIn()) {
        message.value = '请先登录后再修改资料。'
        return
      }

      savingProfile.value = true
      message.value = ''
      try {
        const yearValue = profile.year === '' || profile.year === null ? null : Number(profile.year)
        const updated = await authUpdateMe({
          name: profile.name,
          email: profile.email,
          year: Number.isNaN(yearValue) ? null : yearValue,
          major: profile.major || null
        })
        setCurrentUser(updated)
        currentUser.value = updated
        fillProfile(updated)
        message.value = '资料已保存。'
      } catch (err) {
        message.value = `保存失败：${err.message || err}`
      } finally {
        savingProfile.value = false
      }
    }

    async function changePwd() {
      if (!isLoggedIn()) {
        message.value = '请先登录后再修改密码。'
        return
      }

      savingPwd.value = true
      message.value = ''
      try {
        await authChangePassword({ old_password: pwd.old_password, new_password: pwd.new_password })
        pwd.old_password = ''
        pwd.new_password = ''
        message.value = '密码已更新。'
      } catch (err) {
        message.value = `修改失败：${err.message || err}`
      } finally {
        savingPwd.value = false
      }
    }

    async function doLogout() {
      const refreshToken = getRefreshToken()
      if(refreshToken){
        try {
          await authLogout({ refresh_token: refreshToken })
        } catch {
          // ignore logout API errors
        }
      }
      logout()
      currentUser.value = null
      profile.name = ''
      profile.email = ''
      profile.year = null
      profile.major = ''
      message.value = '已退出登录。'
    }


    function goAuth() {
      router.push('/auth')
    }

    onMounted(async () => {
      if (currentUser.value) fillProfile(currentUser.value)
      await loadMe()
    })

    return {
      currentUser,
      profile,
      pwd,
      savingProfile,
      savingPwd,
      message,
      saveProfile,
      changePwd,
      doLogout,
      goAuth
    }
  }
}
</script>

<style scoped>
.profile-wrap {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(12, minmax(0, 1fr));
}
.card { background: #fff; border-radius: 14px; padding: 18px; border: 1px solid rgba(37, 89, 214, 0.12); }
.intro-card { grid-column: span 12; background: linear-gradient(130deg, #eef5ff, #fff); }
.account-grid {
  grid-column: span 12;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(12, minmax(0, 1fr));
}
.info-card { grid-column: span 7; }
.pwd-card { grid-column: span 5; }
.msg-bar {
  grid-column: span 12;
  padding: 12px 18px;
}
.auth-actions { display: grid; gap: 10px; margin-top: 12px; }
.auth-actions button { width: 100%; }
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.card-head h3 { margin: 0; color: #1a4699; }
.form-grid {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 10px 12px;
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
h2 { margin: 0; color: #1a4699; }
.muted { color: #587091; font-size: 13px; }
.form { display: grid; gap: 8px; margin-top: 8px; }
label { font-size: 13px; color: #4f6688; }
input { border: 1px solid rgba(37, 89, 214, 0.2); border-radius: 10px; padding: 10px 12px; }
.actions { display: flex; gap: 10px; }
.ghost { background: #fff; color: #1f4fb9; border: 1px solid rgba(37, 89, 214, 0.18); }
.danger { background: #b2323a; }
.msg { min-height: 20px; color: #2151b3; font-size: 13px; }

@media (max-width: 960px) {
  .info-card,
  .pwd-card {
    grid-column: span 12;
  }
  .status-bar {
    grid-template-columns: 1fr;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
