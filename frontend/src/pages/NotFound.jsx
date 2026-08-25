import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ScanFace } from 'lucide-react'
import Logo from '../components/layout/Logo'

export default function NotFound() {
  return (
    <div className="bg-hero-glow relative flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <div className="bg-grid absolute inset-0" />
      <div className="relative">
        <div className="mb-6 flex justify-center">
          <Logo />
        </div>
        <p className="text-7xl font-extrabold text-gradient">404</p>
        <h1 className="mt-4 text-2xl font-bold">Page not found</h1>
        <p className="mt-2 max-w-md text-fortexa-muted">
          The page you are looking for doesn't exist or has been moved.
        </p>
        <Link to="/" className="btn-primary mt-8">
          <ScanFace size={16} /> Back to Home
        </Link>
      </div>
    </div>
  )
}