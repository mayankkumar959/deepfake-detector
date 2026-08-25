export default function Gauge({ value, size = 180, label = 'Fake Probability' }) {
  const pct = Math.round(value * 100)
  const radius = (size - 20) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (pct / 100) * circumference
  const color = value >= 0.6 ? '#ef4444' : value >= 0.4 ? '#f59e0b' : '#22c55e'

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={14}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={14}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
        <text
          x="50%"
          y="48%"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size / 5}
          fontWeight={800}
          fill={color}
        >
          {pct}%
        </text>
        <text x="50%" y="63%" textAnchor="middle" dominantBaseline="central" fontSize={11} fill="#94a3b8">
          {label}
        </text>
      </svg>
    </div>
  )
}