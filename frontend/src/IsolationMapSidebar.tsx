import type { AssuranceReason, DownstreamImpactWarning, IsolationPoint, IsolationRunStatus, SavedIsolationPlan } from './api'
import type { IsolationMapLayer, IsolationMapLayers } from './isolation-map'

type IsolationMapSidebarProps = {
  assuranceStatus: string
  reasons: AssuranceReason[]
  impacts: DownstreamImpactWarning[]
  points: IsolationPoint[]
  layers: IsolationMapLayers
  selectedReasonId: string | null
  selectedImpactId: string | null
  selectedPointId: string | null
  savedPlans: SavedIsolationPlan[]
  pastRuns: IsolationRunStatus[]
  onLayerChange: (layer: IsolationMapLayer, visible: boolean) => void
  onReasonSelect: (reason: AssuranceReason) => void
  onImpactSelect: (impact: DownstreamImpactWarning) => void
  onPointSelect: (point: IsolationPoint) => void
  onOpenPlan: (plan: SavedIsolationPlan) => void
  onOpenRun: (run: IsolationRunStatus) => void
}

function humanize(value: unknown): string {
  return String(value ?? 'unknown').replaceAll('_', ' ')
}

function reasonLabel(reason: AssuranceReason): string {
  if (reason.code === 'evidence_check_incomplete') {
    const labels: Record<string, string> = {
      find_bleeds_vents_drains: 'Stored-energy release',
      find_pressure_indicators: 'Locate pressure verification point',
      confirm_zero_pressure: 'Confirm zero pressure',
      find_bypass_paths: 'Bypass and alternate routes',
      find_blinds_spades_flanges: 'Positive-isolation evidence',
    }
    return labels[reason.check_name || ''] || 'Required evidence check'
  }
  const label = String(reason.boundary_label || '').trim()
  if (label && label !== String(reason.boundary_component_id || '')) return label
  const drawingReference = reason.terminal?.display_text?.find((value) => /^PID[-_ ]/i.test(value.trim()))
  return drawingReference ? `Path to ${drawingReference}` : label ? `Boundary ${label}` : humanize(reason.code)
}

function impactLabel(impact: DownstreamImpactWarning): string {
  return String(impact.affected_tag || impact.affected_id || 'Unlabelled target')
}

const LAYERS: Array<{ id: IsolationMapLayer; label: string; color: string }> = [
  { id: 'target', label: 'Selected equipment', color: '#0f62fe' },
  { id: 'points', label: 'Isolation points', color: '#6d28d9' },
  { id: 'blockers', label: 'Selected finding / evidence', color: '#d97706' },
  { id: 'downstream', label: 'Downstream targets', color: '#ea580c' },
]

export default function IsolationMapSidebar({
  assuranceStatus,
  reasons,
  impacts,
  points,
  layers,
  selectedReasonId,
  selectedImpactId,
  selectedPointId,
  savedPlans,
  pastRuns,
  onLayerChange,
  onReasonSelect,
  onImpactSelect,
  onPointSelect,
  onOpenPlan,
  onOpenRun,
}: IsolationMapSidebarProps) {
  const uniqueImpacts = [...new Map(impacts.map((impact) => [impact.affected_id, impact])).values()]
  const blockerReasons = reasons.filter((reason) => reason.code !== 'evidence_check_incomplete')
  const evidenceReasons = reasons.filter((reason) => reason.code === 'evidence_check_incomplete')

  return <div className="min-h-full bg-slate-50">
    <div className="border-b border-slate-300 p-5">
      <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">ISOLATION MAP</p>
      <h1 className="mt-2 text-lg font-medium">Map controls</h1>
      <p className="mt-1 text-xs capitalize text-slate-600">Validator: {humanize(assuranceStatus)}</p>
    </div>

    <section className="border-b border-slate-300 p-5">
      <h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">LAYERS</h2>
      <div className="mt-3 space-y-2">
        {LAYERS.map((layer) => <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-700" key={layer.id}>
          <input checked={layers[layer.id]} className="size-4 accent-blue-700" onChange={(event) => onLayerChange(layer.id, event.target.checked)} type="checkbox" />
          <span className="size-2.5 shrink-0" style={{ backgroundColor: layer.color }} />
          <span>{layer.label}</span>
        </label>)}
      </div>
    </section>

    <section className="border-b border-slate-300 p-5">
      <h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">FINDINGS</h2>
      {blockerReasons.length > 0 && <details className="mt-3" open>
        <summary className="cursor-pointer text-xs font-semibold text-red-800">Blocker paths · {blockerReasons.length}</summary>
        <ol className="mt-2 space-y-1.5">
          {blockerReasons.map((reason, index) => <li key={reason.reason_id}><button
            className={`w-full border-l-2 px-2 py-1.5 text-left text-xs ${selectedReasonId === reason.reason_id ? 'border-red-600 bg-red-100 text-red-950' : 'border-red-300 bg-white text-slate-700 hover:bg-red-50'}`}
            onClick={() => onReasonSelect(reason)}
            type="button"
          ><span className="font-mono text-[9px] text-red-700">B-{String(index + 1).padStart(2, '0')}</span><span className="ml-2">{reasonLabel(reason)}</span></button></li>)}
        </ol>
      </details>}

      {evidenceReasons.length > 0 && <details className="mt-3" open>
        <summary className="cursor-pointer text-xs font-semibold text-amber-800">Evidence requirements · {evidenceReasons.length}</summary>
        <ol className="mt-2 space-y-1.5">
          {evidenceReasons.map((reason, index) => <li key={reason.reason_id}><button
            className={`w-full border-l-2 px-2 py-1.5 text-left text-xs ${selectedReasonId === reason.reason_id ? 'border-amber-600 bg-amber-100 text-amber-950' : 'border-amber-300 bg-white text-slate-700 hover:bg-amber-50'}`}
            onClick={() => onReasonSelect(reason)}
            type="button"
          ><span className="font-mono text-[9px] text-amber-700">E-{String(index + 1).padStart(2, '0')}</span><span className="ml-2">{reasonLabel(reason)}</span></button></li>)}
        </ol>
      </details>}

      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-semibold text-purple-800">Isolation points · {points.length}</summary>
        <ol className="mt-2 space-y-1.5">
          {points.map((point, index) => <li key={`${point.selection_id || point.uuid}-${index}`}><button
            className={`w-full border-l-2 px-2 py-1.5 text-left text-xs ${selectedPointId === point.selection_id ? 'border-purple-700 bg-purple-100 text-purple-950' : 'border-purple-300 bg-white text-slate-700 hover:bg-purple-50'}`}
            onClick={() => onPointSelect(point)}
            type="button"
          ><span className="font-mono text-[9px] text-purple-700">P-{String(index + 1).padStart(2, '0')}</span><span className="ml-2">{point.tag_number || point.source_component_tag || humanize(point.entity_class)}</span></button></li>)}
        </ol>
      </details>

      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-semibold text-orange-800">Downstream targets · {uniqueImpacts.length}</summary>
        <ol className="mt-2 space-y-1.5">
          {uniqueImpacts.map((impact, index) => <li key={impact.affected_id}><button
            className={`w-full border-l-2 px-2 py-1.5 text-left text-xs ${selectedImpactId === impact.affected_id ? 'border-orange-600 bg-orange-100 text-orange-950' : 'border-orange-300 bg-white text-slate-700 hover:bg-orange-50'}`}
            onClick={() => onImpactSelect(impact)}
            type="button"
          ><span className="font-mono text-[9px] text-orange-700">D-{String(index + 1).padStart(2, '0')}</span><span className="ml-2 break-words">{impactLabel(impact)}</span></button></li>)}
        </ol>
      </details>
    </section>

    <section className="border-b border-slate-300 p-5">
      <h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">LEGEND</h2>
      <dl className="mt-2 space-y-1 text-[10px] leading-4 text-slate-600">
        <div><dt className="inline font-semibold text-red-700">Blocker:</dt><dd className="inline"> validation cannot establish a qualifying barrier.</dd></div>
        <div><dt className="inline font-semibold text-amber-700">Evidence:</dt><dd className="inline"> drawing candidate requiring review or field confirmation.</dd></div>
        <div><dt className="inline font-semibold text-orange-700">Possible:</dt><dd className="inline"> connected path with unknown or weak flow direction.</dd></div>
        <div><dt className="inline font-semibold text-purple-700">Point:</dt><dd className="inline"> proposed or accepted isolation location.</dd></div>
      </dl>
    </section>

    <section className="p-5">
      <details>
        <summary className="cursor-pointer font-mono text-[10px] tracking-[0.1em] text-slate-600">HISTORY · {savedPlans.length} PLANS · {pastRuns.length} RUNS</summary>
        {savedPlans.length > 0 && <div className="mt-3"><p className="font-mono text-[9px] text-slate-400">SAVED PLANS</p>{savedPlans.slice(0, 5).map((plan) => <button className="mt-1 block w-full truncate border border-slate-200 bg-white px-2 py-1.5 text-left text-[10px] hover:border-blue-400" key={plan.plan_id} onClick={() => onOpenPlan(plan)} type="button">{plan.plan_number} · v{plan.latest_version.version_no}</button>)}</div>}
        {pastRuns.length > 0 && <div className="mt-3"><p className="font-mono text-[9px] text-slate-400">RECENT RUNS</p>{pastRuns.slice(0, 5).map((run) => <button className="mt-1 block w-full border border-slate-200 bg-white px-2 py-1.5 text-left text-[10px] hover:border-blue-400 disabled:text-slate-400" disabled={run.status !== 'succeeded'} key={run.run_id} onClick={() => onOpenRun(run)} type="button"><span>{run.equipment_tag}</span><span className="float-right font-mono">{run.run_id.slice(0, 8)}</span></button>)}</div>}
      </details>
    </section>
  </div>
}
