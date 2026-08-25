import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import Spinner from '../ui/Spinner'

export default function ProtectedRoute({ children, adminOnly = false }) {
  const { user, initializing } = useAuth()

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-fortexa-primary">
          <Spinner size={32} />
        </div>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && user.role !== 'admin') return <Navigate to="/app" replace />
  return children
}