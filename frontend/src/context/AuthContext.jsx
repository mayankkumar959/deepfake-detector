import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem('fortexa_user')
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(false)
  const [initializing, setInitializing] = useState(false)

  // Restore session from stored token
  const fetchMe = useCallback(async () => {
    const token = localStorage.getItem('fortexa_token')
    if (!token) return null
    try {
      const { data } = await api.get('/auth/me')
      setUser(data)
      localStorage.setItem('fortexa_user', JSON.stringify(data))
      return data
    } catch {
      localStorage.removeItem('fortexa_token')
      localStorage.removeItem('fortexa_user')
      setUser(null)
      return null
    }
  }, [])

  useEffect(() => {
    if (localStorage.getItem('fortexa_token')) {
      setInitializing(true)
      fetchMe().finally(() => setInitializing(false))
    }
  }, [fetchMe])

  const login = async (email, password) => {
    setLoading(true)
    try {
      const { data } = await api.post('/auth/login', { email, password })
      localStorage.setItem('fortexa_token', data.access_token)
      setUser(data.user)
      localStorage.setItem('fortexa_user', JSON.stringify(data.user))
      return { ok: true, user: data.user }
    } catch (err) {
      return { ok: false, error: err.response?.data?.detail || 'Login failed' }
    } finally {
      setLoading(false)
    }
  }

  const register = async (payload) => {
    setLoading(true)
    try {
      const { data } = await api.post('/auth/register', payload)
      localStorage.setItem('fortexa_token', data.access_token)
      setUser(data.user)
      localStorage.setItem('fortexa_user', JSON.stringify(data.user))
      return { ok: true, user: data.user }
    } catch (err) {
      return { ok: false, error: err.response?.data?.detail || 'Registration failed' }
    } finally {
      setLoading(false)
    }
  }

  const logout = () => {
    localStorage.removeItem('fortexa_token')
    localStorage.removeItem('fortexa_user')
    setUser(null)
  }

  const updateUser = (next) => {
    setUser(next)
    localStorage.setItem('fortexa_user', JSON.stringify(next))
  }

  const value = {
    user,
    setUser: updateUser,
    login,
    register,
    logout,
    loading,
    initializing,
    isAdmin: user?.role === 'admin',
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}