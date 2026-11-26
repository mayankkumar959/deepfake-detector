import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react'

const config = {
  fake: {
    label: 'Likely AI-generated',
    icon: ShieldAlert,
    classes: 'bg-red-50 text-red-700 border border-red-200',
  },
  real: {
    label: 'Likely real photo',
    icon: ShieldCheck,
    classes: 'bg-emerald-50 text-emerald-800 border border-emerald-200',
  },
  inconclusive: {
    label: 'Inconclusive',
    icon: ShieldQuestion,
    classes: 'bg-amber-50 text-amber-800 border border-amber-200',
  },
}

export default function VerdictBadge({ verdict, size = 'md' }) {
  const c = config[verdict] || config.inconclusive
  const Icon = c.icon
  const pad = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : size === 'lg' ? 'px-4 py-2 text-lg' : 'px-3 py-1 text-xs'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-medium ${c.classes} ${pad}`}>
      <Icon size={size === 'sm' ? 12 : size === 'lg' ? 20 : 14} />
      {c.label}
    </span>
  )
}
