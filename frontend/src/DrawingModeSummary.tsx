import type { IsolationPlan } from './api'

type DrawingModeSummaryProps = {
  plan: IsolationPlan
  runId: string
  onOpenMap: () => void
  onNewRun: () => void
}

function statusLabel(status: string): string {
  return status === 'not_isolated' ? 'Isolation not demonstrated' : status.replaceAll('_', ' ')
}

export default function DrawingModeSummary({ plan, runId, onOpenMap, onNewRun }: DrawingModeSummaryProps) {
  const validation = plan.isolation_validation ?? {}
  const points = plan.isolation_points?.length ?? 0
  const covered = Number(validation.covered_boundary_source_count ?? 0)
  const expected = Number(validation.expected_boundary_count ?? points)
  const blockers = Number(validation.assurance_explanation?.summary.primary_reason_count ?? validation.missing_boundary_count ?? 0)
  const notDemonstrated = plan.assurance_status === 'not_isolated'

  return <div className="p-5">
    <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">DRAWING MODE</p>
    <h3 className="mt-3 text-lg font-medium">Isolation overlays hidden</h3>
    <p className="mt-2 text-sm leading-6 text-slate-600">The completed advisory result remains loaded. Open Isolation Map to review blocker paths, isolation points, and downstream targets.</p>

    <div className={`mt-5 border-l-2 p-4 ${notDemonstrated ? 'border-red-500 bg-red-50 text-red-950' : 'border-blue-600 bg-blue-50 text-blue-950'}`}>
      <p className="font-mono text-[9px] uppercase tracking-wide">Authoritative validator status</p>
      <p className="mt-2 font-medium">{statusLabel(plan.assurance_status)}</p>
    </div>

    <dl className="mt-4 grid grid-cols-3 gap-px bg-slate-200 text-center">
      <div className="bg-slate-50 p-3"><dt className="font-mono text-[8px] text-slate-500">POINTS</dt><dd className="mt-1 text-lg">{points}</dd></div>
      <div className="bg-slate-50 p-3"><dt className="font-mono text-[8px] text-slate-500">COVERAGE</dt><dd className="mt-1 text-lg">{covered}/{expected}</dd></div>
      <div className="bg-slate-50 p-3"><dt className="font-mono text-[8px] text-slate-500">BLOCKERS</dt><dd className="mt-1 text-lg">{blockers}</dd></div>
    </dl>

    <button className="mt-5 w-full bg-blue-700 px-4 py-3 font-mono text-xs font-semibold tracking-[0.08em] text-white hover:bg-blue-800" onClick={onOpenMap} type="button">OPEN ISOLATION MAP</button>
    <button className="mt-2 w-full border border-slate-300 px-4 py-2.5 font-mono text-xs hover:bg-slate-50" onClick={onNewRun} type="button">NEW RUN</button>
    <p className="mt-4 break-all font-mono text-[9px] text-slate-400">RUN {runId}</p>
  </div>
}
