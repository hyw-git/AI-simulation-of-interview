import { fetchReports } from './api'
import { isLoggedIn } from './authStore'

const STORAGE_KEY = 'ai_interview_reports_v1'

export function computeRadarDimensions(report) {
  const dims = report?.dimensions || {}
  if (dims.technical_depth || dims.problem_solving || dims.communication || dims.engineering || dims.potential) {
    const readScore = (key) => {
      const raw = dims?.[key]?.score
      const val = Number(raw)
      return Number.isFinite(val) ? Math.max(0, Math.min(100, val)) : 0
    }
    return [
      { label: '技术深度', value: readScore('technical_depth') },
      { label: '表达清晰', value: readScore('communication') },
      { label: '问题分析', value: readScore('problem_solving') },
      { label: '工程实践', value: readScore('engineering') },
      { label: '综合潜力', value: readScore('potential') }
    ]
  }

  const score = Math.max(0, Math.min(100, Number(report?.score || 0)))
  const strengths = Array.isArray(report?.strengths) ? report.strengths.join(' ') : ''
  const weaknesses = Array.isArray(report?.weaknesses) ? report.weaknesses.join(' ') : ''
  const suggestions = Array.isArray(report?.suggestions) ? report.suggestions.join(' ') : ''
  const text = `${strengths} ${weaknesses} ${suggestions}`

  const has = (kw) => text.includes(kw) ? 1 : 0

  const technical = Math.min(100, Math.round(score * 0.9 + has('技术') * 8 + has('架构') * 6))
  const expression = Math.min(100, Math.round(score * 0.8 + has('表达') * 12 + has('条理') * 8))
  const analysis = Math.min(100, Math.round(score * 0.85 + has('分析') * 10 + has('定位') * 6))
  const engineering = Math.min(100, Math.round(score * 0.88 + has('项目') * 8 + has('实践') * 8 + has('工程') * 6))
  const potential = Math.min(100, Math.round(score * 0.82 + has('建议') * 8 + has('提升') * 10))

  return [
    { label: '技术深度', value: technical },
    { label: '表达清晰', value: expression },
    { label: '问题分析', value: analysis },
    { label: '工程实践', value: engineering },
    { label: '综合潜力', value: potential }
  ]
}

export function mapServerReport(row) {
  const report = row?.report || {}
  const mapped = {
    id: String(row.id || row.interview_id || ''),
    interviewId: String(row.interview_id || ''),
    role: row.role || null,
    focus: row.focus || null,
    mode: row.mode || null,
    difficulty: row.difficulty ?? null,
    timeLimit: row.time_limit ?? null,
    createdAt: row.generated_at || new Date().toISOString(),
    transcript: Array.isArray(row.transcript) ? row.transcript : [],
    report: {
      score: Number(report.score) || 0,
      strengths: report.strengths || [],
      weaknesses: report.weaknesses || [],
      suggestions: report.suggestions || [],
      dimensions: report.dimensions || {},
      weights: report.weights || {},
      summary: report.summary || ''
    },
    source: 'server'
  }
  mapped.radar = computeRadarDimensions(mapped.report)
  return mapped
}

function mergeReports(remote, local) {
  const byKey = new Map()
  for (const r of remote) {
    const key = String(r.interviewId || r.id)
    byKey.set(key, r)
  }
  for (const r of local) {
    const key = String(r.interviewId || r.id)
    if (!byKey.has(key)) {
      byKey.set(key, { ...r, source: r.source || 'local' })
    }
  }
  return Array.from(byKey.values()).sort((a, b) => {
    const ta = new Date(a.createdAt || 0).getTime()
    const tb = new Date(b.createdAt || 0).getTime()
    return tb - ta
  })
}

export function loadInterviewReports() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

export async function loadReportsMerged() {
  const local = loadInterviewReports()
  if (!isLoggedIn()) {
    return local
  }
  try {
    const rows = await fetchReports()
    const remote = Array.isArray(rows) ? rows.map(mapServerReport) : []
    return mergeReports(remote, local)
  } catch {
    return local
  }
}

export function saveInterviewReport(record) {
  const all = loadInterviewReports()
  const next = [record, ...all].slice(0, 100)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  return next
}

export function clearInterviewReports() {
  localStorage.removeItem(STORAGE_KEY)
}

export function findInterviewReportById(id) {
  if (!id) return null
  const all = loadInterviewReports()
  return all.find(x => String(x.id) === String(id)) || null
}

export async function findReportByIdMerged(id) {
  if (!id) return null
  const all = await loadReportsMerged()
  return all.find(x => String(x.id) === String(id)) || null
}
