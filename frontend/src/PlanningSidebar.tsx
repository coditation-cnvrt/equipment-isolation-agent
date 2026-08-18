import type { IsolationRunStatus, SavedIsolationPlan } from './api'

function formatRunTime(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return 'Time unavailable'
  return new Date(value * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

type PlanningSidebarProps = {
  projectLabel: string
  collectionLabel: string
  drawingLabel: string
  graphLabel: string
  equipmentLabel: string
  savedPlans: SavedIsolationPlan[]
  pastRuns: IsolationRunStatus[]
  plansLoading: boolean
  runsLoading: boolean
  plansError: string
  runsError: string
  onOpenPlan: (plan: SavedIsolationPlan) => void
  onOpenRun: (run: IsolationRunStatus) => void
}

export default function PlanningSidebar({
  projectLabel,
  collectionLabel,
  drawingLabel,
  graphLabel,
  equipmentLabel,
  savedPlans,
  pastRuns,
  plansLoading,
  runsLoading,
  plansError,
  runsError,
  onOpenPlan,
  onOpenRun,
}: PlanningSidebarProps) {
  const steps = [
    { label: 'Project', value: projectLabel },
    { label: 'Collection', value: collectionLabel },
    { label: 'Drawing', value: drawingLabel },
    { label: 'UniGraph', value: graphLabel },
    { label: 'Equipment', value: equipmentLabel },
  ]
  const nextStep = steps.find((step) => !step.value)

  return <div className="min-h-full bg-slate-50">
    <div className="border-b border-slate-300 p-5">
      <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">PLANNING CONTEXT</p>
      <h1 className="mt-2 text-lg font-medium">{nextStep ? `Choose ${nextStep.label.toLowerCase()}` : 'Context ready'}</h1>
      <p className="mt-2 text-xs leading-5 text-slate-600">Use the editable breadcrumb path above the workspace. You can also select equipment directly from the drawing.</p>
    </div>

    <section className="border-b border-slate-300 p-5">
      <h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">SELECTION PROGRESS</h2>
      <ol className="mt-3 space-y-2">
        {steps.map((step, index) => <li className="flex items-start gap-2" key={step.label}>
          <span className={`mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full font-mono text-[8px] ${step.value ? 'bg-emerald-600 text-white' : nextStep?.label === step.label ? 'bg-blue-700 text-white' : 'bg-slate-200 text-slate-500'}`}>{step.value ? '✓' : index + 1}</span>
          <span className="min-w-0"><span className="block font-mono text-[9px] uppercase text-slate-400">{step.label}</span><span className={`block truncate text-xs ${step.value ? 'text-slate-800' : 'text-slate-400'}`}>{step.value || 'Not selected'}</span></span>
        </li>)}
      </ol>
    </section>

    <section className="border-b border-slate-300 p-5" aria-label="Saved isolation plans">
      <div className="flex items-baseline justify-between gap-2"><h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">SAVED PLANS</h2>{plansLoading && <span className="text-[9px] text-slate-400">Loading…</span>}</div>
      {plansError && <p className="mt-2 border-l-2 border-amber-500 bg-amber-50 px-2 py-1 text-[10px] text-amber-900">{plansError}</p>}
      {!plansLoading && !plansError && !savedPlans.length && <p className="mt-2 text-xs text-slate-500">No matching saved plans.</p>}
      <ol className="mt-2 space-y-1.5">
        {savedPlans.slice(0, 8).map((plan) => <li key={plan.plan_id}><button className="w-full border border-slate-200 bg-white p-2 text-left hover:border-blue-400" onClick={() => onOpenPlan(plan)} type="button"><span className="flex items-center justify-between gap-2"><span className="truncate font-mono text-[10px] font-semibold">{plan.plan_number} · v{plan.latest_version.version_no}</span><span className="font-mono text-[8px] uppercase text-purple-700">{plan.lifecycle_state}</span></span><span className="mt-1 block truncate text-[9px] text-slate-500">{plan.latest_version.source_run.equipment_tag} · {String(plan.latest_version.source_run.assurance_status || 'unknown').replaceAll('_', ' ')}</span></button></li>)}
      </ol>
    </section>

    <section className="p-5" aria-label="Previous isolation runs">
      <div className="flex items-baseline justify-between gap-2"><h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">RECENT RUNS</h2>{runsLoading && <span className="text-[9px] text-slate-400">Loading…</span>}</div>
      {runsError && <p className="mt-2 border-l-2 border-red-500 bg-red-50 px-2 py-1 text-[10px] text-red-900">{runsError}</p>}
      {!runsLoading && !runsError && !pastRuns.length && <p className="mt-2 text-xs text-slate-500">No matching previous runs.</p>}
      <ol className="mt-2 space-y-1.5">
        {pastRuns.slice(0, 8).map((run) => <li key={run.run_id}><button className="w-full border border-slate-200 bg-white p-2 text-left hover:border-blue-400 disabled:cursor-not-allowed disabled:text-slate-400" disabled={run.status !== 'succeeded'} onClick={() => onOpenRun(run)} type="button"><span className="flex items-center justify-between gap-2"><span className="truncate text-xs font-medium">{run.equipment_tag}</span><span className="font-mono text-[8px] uppercase">{run.status}</span></span><span className="mt-1 block text-[9px] text-slate-400">{formatRunTime(run.created_at)}</span></button></li>)}
      </ol>
    </section>
  </div>
}
