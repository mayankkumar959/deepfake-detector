import { ScanFace } from 'lucide-react'

export default function Logo({ size = 'md', light = false }) {
  const textSize = size === 'lg' ? 'text-2xl' : size === 'sm' ? 'text-base' : 'text-lg'
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-fortexa-primary">
        <ScanFace size={size === 'sm' ? 18 : 20} className="text-white" />
      </div>
      <span className={`${textSize} font-bold tracking-tight ${light ? 'text-white' : ''}`}>
        Forte<span className="text-gradient">xa</span>
      </span>
    </div>
  )
}