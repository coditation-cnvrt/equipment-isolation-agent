import type { IsolationRunStatus, SavedIsolationPlan } from './api'

type HistoryModalProps = {
  kind: 'plans' | 'runs'
  savedPlans: SavedIsolationPlan[]
  pastRuns: IsolationRunStatus[]
  loading: boolean
  error: string
  onClose: () => void
  onOpenPlan: (plan: SavedIsolationPlan) => void
  onOpenRun: (run: IsolationRunStatus) => void
  onRefresh: () => void
}

function formatRunTime(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return 'Time unavailable'
  return new Date(value * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

export default function HistoryModal({
  kind,
  savedPlans,
  pastRuns,
  loading,
  error,
  onClose,
  onOpenPlan,
  onOpenRun,
  onRefresh,
}: HistoryModalProps) {
  const plans = kind === 'plans'
  const title = plans ? 'Saved Plans' : 'Recent Runs'
  const emptyMessage = plans ? 'No matching saved plans.' : 'No matching recent runs.'
  const empty = plans ? savedPlans.length === 0 : pastRuns.length === 0

  return <div
    aria-labelledby="history-modal-title"
    aria-modal="true"
    className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-[2px]"
    onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}
    role="dialog"
  >
    <section className="flex max-h-[80vh] w-full max-w-2xl flex-col border border-slate-300 bg-white shadow-2xl">
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-300 p-5">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-blue-700">Isolation planning history</p>
          <h2 className="mt-1 text-xl font-medium text-slate-950" id="history-modal-title">{title}</h2>
          <p className="mt-1 text-xs text-slate-500">Filtered to the current planning context when all context selections are complete.</p>
        </div>
        <button aria-label={`Close ${title}`} className="flex size-8 shrink-0 items-center justify-center border border-slate-300 text-lg text-slate-600 hover:bg-slate-100" onClick={onClose} type="button">×</button>
      </header>

      <div className="min-h-40 flex-1 overflow-y-auto p-5" aria-busy={loading}>
        {loading && <div className="flex min-h-32 items-center justify-center gap-3 text-sm text-slate-600" role="status"><span aria-hidden="true" className="size-5 animate-spin rounded-full border-2 border-blue-200 border-t-blue-700" />Loading {title.toLowerCase()}…</div>}
        {!loading && error && <div className="border-l-2 border-red-500 bg-red-50 p-3 text-xs leading-5 text-red-900" role="alert">{error}</div>}
        {!loading && !error && empty && <p className="py-12 text-center text-sm text-slate-500">{emptyMessage}</p>}

        {!loading && !error && plans && <ol className="space-y-2">
          {savedPlans.map((plan) => <li key={plan.plan_id}><button className="w-full border border-slate-200 bg-white p-3 text-left hover:border-blue-500 hover:bg-blue-50" onClick={() => onOpenPlan(plan)} type="button"><span className="flex items-center justify-between gap-3"><span className="truncate font-mono text-xs font-semibold text-slate-900">{plan.plan_number} · v{plan.latest_version.version_no}</span><span className="shrink-0 font-mono text-[9px] uppercase text-purple-700">{plan.lifecycle_state}</span></span><span className="mt-1 block truncate text-xs text-slate-500">{plan.latest_version.source_run.equipment_tag} · {String(plan.latest_version.source_run.assurance_status || 'unknown').replaceAll('_', ' ')}</span></button></li>)}
        </ol>}

        {!loading && !error && !plans && <ol className="space-y-2">
          {pastRuns.map((run) => <li key={run.run_id}><button className="w-full border border-slate-200 bg-white p-3 text-left enabled:hover:border-blue-500 enabled:hover:bg-blue-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400" disabled={run.status !== 'succeeded'} onClick={() => onOpenRun(run)} type="button"><span className="flex items-center justify-between gap-3"><span className="truncate text-sm font-medium">{run.equipment_tag}</span><span className="shrink-0 font-mono text-[9px] uppercase">{run.status}</span></span><span className="mt-1 block text-xs text-slate-500">{formatRunTime(run.created_at)}</span></button></li>)}
        </ol>}
      </div>

      <footer className="flex shrink-0 justify-end gap-2 border-t border-slate-300 bg-slate-50 p-4">
        <button className="border border-slate-300 bg-white px-3 py-2 font-mono text-[10px] font-semibold hover:bg-slate-100 disabled:cursor-wait disabled:text-slate-400" disabled={loading} onClick={onRefresh} type="button">REFRESH</button>
        <button className="bg-slate-900 px-3 py-2 font-mono text-[10px] font-semibold text-white hover:bg-slate-800" onClick={onClose} type="button">CLOSE</button>
      </footer>
    </section>
  </div>
}
