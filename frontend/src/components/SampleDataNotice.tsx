type SampleDataNoticeProps = {
  children: string
}

/** Professional page-level notice for intentionally mock surfaces. */
export function SampleDataNotice({ children }: SampleDataNoticeProps) {
  return (
    <aside className="sample-data-notice" role="note">
      <p className="sample-data-notice-label">Sample data</p>
      <p className="sample-data-notice-copy">{children}</p>
    </aside>
  )
}
