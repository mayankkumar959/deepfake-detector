import { Routes, Route } from 'react-router-dom'
import Scanner from './pages/Scanner'
import Results from './pages/Results'
import Terms from './pages/Terms'
import Privacy from './pages/Privacy'
import NotFound from './pages/NotFound'
import { ToastProvider } from './components/ui/Toast'

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/" element={<Scanner />} />
        <Route path="/scan" element={<Scanner />} />
        <Route path="/results/:id" element={<Results />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ToastProvider>
  )
}