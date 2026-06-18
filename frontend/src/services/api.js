import { getToken, setToken, getRefreshToken, setRefreshToken, clearToken, clearRefreshToken } from './authStore'

const baseURL = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

let refreshPromise = null

function buildUrl(path, params){
  const url = new URL(path, baseURL)
  if(params){
    Object.keys(params).forEach(k=>{
      const v = params[k]
      if(v !== undefined && v !== null) url.searchParams.append(k, String(v))
    })
  }
  return url.toString()
}

async function refreshAccessToken(){
  const refreshToken = getRefreshToken()
  if(!refreshToken){
    throw new Error('missing refresh token')
  }
  if(refreshPromise) return refreshPromise

  refreshPromise = fetch(buildUrl('/auth/refresh'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  })
    .then(async (res)=>{
      if(!res.ok){
        const errText = await res.text().catch(()=>res.statusText)
        throw new Error(errText || res.statusText)
      }
      const data = await res.json()
      setToken(data.access_token || '')
      if(data.refresh_token){
        setRefreshToken(data.refresh_token)
      }
      return data.access_token
    })
    .finally(()=>{ refreshPromise = null })

  return refreshPromise
}

async function request(path, { method='GET', params, json, form, headers } = {}, retry = true){
  const url = buildUrl(path, params)
  const opts = { method, headers: { ...(headers||{}) } }
  const token = getToken()
  if(token){
    opts.headers['Authorization'] = `Bearer ${token}`
  }

  if(json !== undefined){
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(json)
  } else if(form instanceof FormData){
    opts.body = form
    // browser will set Content-Type including boundary
  }

  const res = await fetch(url, opts)
  if(res.status === 401 && retry && getRefreshToken()){
    try{
      await refreshAccessToken()
      return request(path, { method, params, json, form, headers }, false)
    } catch {
      clearToken()
      clearRefreshToken()
    }
  }
  const contentType = res.headers.get('content-type') || ''
  if(!res.ok){
    let errText = await res.text().catch(()=>res.statusText)
    const err = new Error(errText || res.statusText)
    err.status = res.status
    throw err
  }

  if(contentType.includes('application/json')){
    return res.json()
  }
  return res.text()
}

export async function health(){ return request('/health') }
export async function fetchInterviews(){ return request('/interviews') }
export async function fetchQuestions(){ return request('/questions') }
export async function fetchRagQuestions(role){ return request('/questions/rag', { params: { role } }) }
export async function fetchRagRoles(){ return request('/questions/rag/roles') }
export async function fetchJobs(){ return request('/questions/jobs') }

export async function authRegister(payload){ return request('/auth/register', { method:'POST', json: payload }) }
export async function authLogin(payload){ return request('/auth/login', { method:'POST', json: payload }) }
export async function authRefresh(payload){ return request('/auth/refresh', { method:'POST', json: payload }) }
export async function authLogout(payload){ return request('/auth/logout', { method:'POST', json: payload }) }
export async function authMe(){ return request('/auth/me') }
export async function authUpdateMe(payload){ return request('/auth/me', { method:'PUT', json: payload }) }
export async function authChangePassword(payload){ return request('/auth/change_password', { method:'POST', json: payload }) }
export async function authGetResume(){ return request('/auth/resume') }
export async function authUpdateResume(payload){ return request('/auth/resume', { method:'PUT', json: payload }) }
export async function authUploadResume(file){
  const fd = new FormData(); fd.append('file', file)
  return request('/auth/resume/upload', { method:'POST', form: fd })
}

export async function startAttempt(payload){ return request('/questions/attempts', { method:'POST', json: payload }) }
export async function submitAttempt(attemptId, payload){ return request(`/questions/attempts/${attemptId}/submit`, { method:'POST', json: payload }) }
export async function fetchAttempts(userId){ return request('/questions/attempts', { params: { user_id: userId } }) }

export async function fetchFollowups(interviewId, answer){ return request(`/interviews/${interviewId}/followups`, { method:'POST', json: { answer } }) }

export async function createInterview(payload){ return request('/interviews', { method:'POST', json: payload }) }
export async function fetchInterviewCapabilities(){ return request('/interviews/capabilities') }
export async function analyzeRepo(url){ return request('/interviews/analyze-repo', { method:'POST', json: { url } }) }
export async function fetchCodingChallenge(interviewId){ return request(`/interviews/${interviewId}/coding/challenge`, { method:'POST', json: {} }) }
export async function runInterviewCode(interviewId, payload){ return request(`/interviews/${interviewId}/coding/run`, { method:'POST', json: payload }) }
export async function testInterviewCode(interviewId, payload){ return request(`/interviews/${interviewId}/coding/test`, { method:'POST', json: payload }) }
export async function submitInterviewCode(interviewId, payload){ return request(`/interviews/${interviewId}/coding/submit`, { method:'POST', json: payload }) }

export function openInterviewWs(interviewId, { onMessage, onOpen, onClose, onError } = {}){
  const wsBase = baseURL.replace(/^http/i, 'ws')
  const ws = new WebSocket(`${wsBase}/interviews/ws/interviews/${interviewId}`)
  ws.onopen = (evt) => { if (onOpen) onOpen(evt) }
  ws.onclose = (evt) => { if (onClose) onClose(evt) }
  ws.onerror = (evt) => { if (onError) onError(evt) }
  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data)
      if (onMessage) onMessage(data)
    } catch {
      if (onMessage) onMessage({ type: 'raw', content: evt.data })
    }
  }
  return ws
}

export async function transcribeAudioFile(interviewId, file){
  const fd = new FormData(); fd.append('file', file)
  return request(`/interviews/${interviewId}/transcribe`, { method:'POST', form: fd })
}

export async function fetchDashboard(){ return request('/dashboard') }
export async function evaluateInterview(interviewId, payload){
  return request(`/interviews/${interviewId}/evaluate`, { method:'POST', json: payload })
}
export async function fetchReports(userId){
  const params = userId ? { user_id: userId } : undefined
  return request('/interviews/reports', { params })
}

export default {
  health, fetchInterviews, fetchQuestions, fetchRagQuestions, fetchRagRoles, fetchJobs,
  authRegister, authLogin, authRefresh, authLogout, authMe, authUpdateMe, authChangePassword, authGetResume, authUpdateResume, authUploadResume, startAttempt, submitAttempt, fetchAttempts,
  fetchFollowups, createInterview, fetchInterviewCapabilities, openInterviewWs, transcribeAudioFile, fetchDashboard, evaluateInterview, fetchReports
}
