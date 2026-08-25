import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
})

export function handleError(error) {
  const detail = error.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg).join(', ')
  }
  return detail || error.message || 'Something went wrong'
}

export default api