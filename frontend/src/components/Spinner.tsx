export function FullScreenSpinner({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status" aria-live="polite">
      {label}
    </div>
  )
}
