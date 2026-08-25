export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="rounded-2xl bg-white/5 border border-white/10 p-6 mb-4">
        {Icon && <Icon size={36} className="text-fortexa-muted" />}
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-fortexa-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}