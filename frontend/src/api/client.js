import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

let memorySession
function scanSession() {
  let saved
  try { saved = localStorage.getItem('fortexa_scan_session') } catch { /* Private browsing */ }
  if (saved && /^[a-f0-9]{64}$/.test(saved)) return saved
  if (!memorySession) {
    const bytes = crypto.getRandomValues(new Uint8Array(32))
    memorySession = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
    try { localStorage.setItem('fortexa_scan_session', memorySession) } catch { /* Memory fallback */ }
  }
  return memorySession
}

api.interceptors.request.use(config => {
  config.headers['X-Scan-Session'] = scanSession()
  let token
  try { token = localStorage.getItem('fortexa_token') } catch { /* Storage unavailable */ }
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export function mediaUrl(scan, filename = 'original') {
  const base = api.defaults.baseURL.replace(/\/$/, '')
  return `${base}/scans/${encodeURIComponent(scan.id)}/media/${encodeURIComponent(filename)}?token=${encodeURIComponent(scan.media_token || '')}`
}

export function handleError(error) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg).join(', ')
  }
  return detail || error.message || 'Something went wrong'
}

export default api
