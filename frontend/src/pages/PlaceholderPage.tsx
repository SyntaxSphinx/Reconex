export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="page">
      <div className="page-header">
        <h1>{title}</h1>
      </div>
      <div className="placeholder-content">
        <p className="text-secondary">This section is not yet implemented.</p>
      </div>
    </div>
  )
}
