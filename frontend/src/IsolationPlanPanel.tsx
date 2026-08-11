import type { IsolationPlan, IsolationPoint, IsolationRunStatus } from './api'

type IsolationPlanPanelProps = {
  run: IsolationRunStatus | null
  plan: IsolationPlan | null
  error: string
  selectedPointId: string | null
  onPointSelect: (point: IsolationPoint) => void
  onReset: () => void
}

function humanize(value: unknown): string {
  return String(value ?? 'unknown').replaceAll('_', ' ')
}

function pointLabel(point: IsolationPoint): string {
  return String(point.tag_number || point.source_component_tag || point.entity_class || point.uuid || 'Unlabelled point')
}

function assuranceStyle(status: string): string {
  if (status === 'not_isolated') return 'border-red-500 bg-red-50 text-red-950'
  if (status.includes('provisional') || status.includes('unproven')) return 'border-amber-500 bg-amber-50 text-amber-950'
  return 'border-blue-600 bg-blue-50 text-blue-950'
}

const TOOL_STAGE: Record<string, string> = {
  fetch_boundary: 'Reading equipment boundary',
  find_candidates: 'Finding isolation candidates',
  resolve_bboxes: 'Locating points on the drawing',
  analyze_isolation_obligations: 'Checking isolation obligations',
  analyze_isolation_schemes_and_relief: 'Analysing schemes and relief paths',
  build_evidence: 'Building assurance evidence',
  analyze_instrument_context: 'Reviewing instrument context',
  validate: 'Running authoritative validation',
  analyze_downstream_impact: 'Checking downstream impact',
  build_loto_procedure: 'Building regulatory LOTO sequence',
  finalize_plan: 'Finalising advisory plan',
}

function RunProgress({ run, error, onReset }: Pick<IsolationPlanPanelProps, 'run' | 'error' | 'onReset'>) {
  const status = run?.status ?? (error ? 'failed' : 'queued')
  const currentTool = run?.agent?.progress?.tool || ''
  const stage = TOOL_STAGE[currentTool] || 'Gathering graph evidence and running deterministic checks'
  return (
    <div className="p-5">
      <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">AGENT RUN</p>
      <div className="mt-4 border-l-2 border-blue-600 bg-blue-50 p-4">
        <p className="font-mono text-xs font-semibold uppercase text-blue-900">{humanize(status)}</p>
        <p className="mt-2 text-sm leading-5 text-blue-950">
          {status === 'queued' && 'The isolation request is waiting for an agent worker.'}
          {status === 'running' && `${stage}.`}
          {status === 'failed' && (error || run?.error?.message || 'The isolation run failed.')}
        </p>
        {run?.run_id && <p className="mt-3 break-all font-mono text-[10px] text-blue-700">RUN {run.run_id}</p>}
      </div>
      {status === 'failed' && <button className="mt-4 w-full border border-slate-400 px-3 py-2 text-xs hover:bg-slate-100" onClick={onReset} type="button">Return to work scope</button>}
    </div>
  )
}

export default function IsolationPlanPanel({ run, plan, error, selectedPointId, onPointSelect, onReset }: IsolationPlanPanelProps) {
  if (!plan) return <RunProgress error={error} onReset={onReset} run={run} />

  const validation = plan.isolation_validation ?? {}
  const points = plan.isolation_points ?? []
  const missingBoundaryCount = Number(validation.missing_boundary_count ?? 0)
  const expectedBoundaryCount = Number(validation.expected_boundary_count ?? points.length)
  const coveredBoundaryCount = Number(validation.covered_boundary_source_count ?? 0)
  const unselectedSources = plan.unselected_boundary_sources ?? validation.unselected_boundary_sources ?? []
  const manualChecks = plan.manual_visual_isolation_checks ?? []
  const unresolvedObligations = validation.unresolved_isolation_obligations ?? []
  const unresolvedEvidence = validation.unresolved_evidence_checks ?? []
  const missingEvidence = validation.missing_evidence ?? []
  const downstreamWarnings = plan.downstream_impact?.warnings ?? []
  const phases = plan.loto_procedure?.phases ?? []
  const gaps = missingBoundaryCount + unselectedSources.length + manualChecks.length + unresolvedObligations.length + unresolvedEvidence.length + missingEvidence.length
  const acceptedPointCount = points.filter((point) => point.validation_state === 'barrier' || point.validation_state === 'positive').length
  const allRejected = points.length > 0 && acceptedPointCount === 0

  return (
    <div className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">ADVISORY PLAN RESULT</p>
          <p className="mt-1 font-mono text-[10px] text-slate-500">RUN {run?.run_id?.slice(0, 12) ?? '—'}</p>
        </div>
        <button className="border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100" onClick={onReset} type="button">New run</button>
      </div>

      {run?.agent?.orchestration_error && <div className="mt-4 border-l-2 border-amber-500 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
        Gemini orchestration became unavailable. The deterministic guardrail completed the advisory payload; review the audit trace before use.
      </div>}

      <section className={`mt-4 border-l-4 p-4 ${assuranceStyle(plan.assurance_status)}`}>
        <p className="font-mono text-[10px] tracking-[0.1em]">AUTHORITATIVE VALIDATOR STATUS</p>
        <h3 className="mt-2 text-base font-semibold capitalize">{humanize(plan.assurance_status)}</h3>
        {validation.rationale && <p className="mt-2 text-xs leading-5">{validation.rationale}</p>}
      </section>

      <dl className="mt-4 grid grid-cols-3 gap-px bg-slate-200 text-center">
        <div className="bg-slate-50 p-3"><dt className="font-mono text-[9px] text-slate-500">POINTS</dt><dd className="mt-1 text-lg font-medium">{points.length}</dd></div>
        <div className="bg-slate-50 p-3"><dt className="font-mono text-[9px] text-slate-500">COVERAGE</dt><dd className="mt-1 text-lg font-medium">{coveredBoundaryCount}/{expectedBoundaryCount}</dd></div>
        <div className="bg-slate-50 p-3"><dt className="font-mono text-[9px] text-slate-500">GAPS</dt><dd className="mt-1 text-lg font-medium">{gaps}</dd></div>
      </dl>

      <section className="mt-6">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">{allRejected ? 'CANDIDATE LOCATIONS · NOT ACCEPTED AS ISOLATION' : plan.assurance_status === 'not_isolated' ? 'PROPOSED ISOLATION POINTS · PLAN INCOMPLETE' : 'PROPOSED ISOLATION POINTS'}</h3>
          <span className="text-[10px] text-slate-500">Click to select on drawing</span>
        </div>
        <ol className="mt-2 space-y-2">
          {points.map((point, index) => {
            const visualId = point.visual_id || ''
            const canLocate = point.bbox?.length === 4
            const selected = Boolean(canLocate && visualId && selectedPointId === visualId)
            const pointRejected = point.validation_state === 'rejected'
            return <li key={`${point.uuid}-${index}`}>
              <button
                className={`w-full border p-3 text-left ${selected ? 'border-purple-700 bg-purple-50' : 'border-slate-200 bg-white hover:border-slate-400'}`}
                disabled={!canLocate}
                onClick={() => onPointSelect(point)}
                type="button"
              >
                <span className="flex items-start gap-3">
                  <span className={`flex size-7 shrink-0 items-center justify-center font-mono text-[10px] font-semibold text-white ${pointRejected ? 'bg-amber-700' : 'bg-purple-700'}`}>{pointRejected ? `C${index + 1}` : index + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block break-words text-sm font-medium">{pointLabel(point)}</span>
                    <span className="mt-0.5 block text-xs capitalize text-slate-500">{humanize(point.entity_class)} · {humanize(point.isolation_method)}</span>
                    {pointRejected && <span className="mt-1 block text-[10px] font-medium text-red-800">Rejected by deterministic validation</span>}
                    {point.validation_state === 'positive' && <span className="mt-1 block text-[10px] font-medium text-purple-800">Positive-isolation candidate</span>}
                    {!canLocate && <span className="mt-1 block text-[10px] text-amber-800">Candidate has no drawing bbox</span>}
                  </span>
                </span>
                {(point.requires_manual_review || point.positive_isolation_requires_field_confirmation) && <span className="mt-2 flex flex-wrap gap-1 pl-10">
                  {point.requires_manual_review && <span className="bg-amber-100 px-1.5 py-0.5 font-mono text-[9px] text-amber-900">MANUAL REVIEW</span>}
                  {point.positive_isolation_requires_field_confirmation && <span className="bg-purple-100 px-1.5 py-0.5 font-mono text-[9px] text-purple-900">FIELD CONFIRMATION</span>}
                </span>}
              </button>
            </li>
          })}
        </ol>
      </section>

      <div className="mt-6 divide-y divide-slate-200 border-y border-slate-200">
        <details className="py-3" open={gaps > 0}>
          <summary className="cursor-pointer font-mono text-[10px] font-semibold tracking-[0.1em] text-slate-700">GAPS AND REQUIRED CHECKS · {gaps}</summary>
          <div className="mt-3 space-y-2 text-xs leading-5 text-slate-600">
            <p>{missingBoundaryCount} missing boundary source{missingBoundaryCount === 1 ? '' : 's'}.</p>
            <p>{unselectedSources.length} unselected boundary source{unselectedSources.length === 1 ? '' : 's'}.</p>
            <p>{manualChecks.length} manual visual check{manualChecks.length === 1 ? '' : 's'}.</p>
            <p>{unresolvedObligations.length} unresolved isolation obligation{unresolvedObligations.length === 1 ? '' : 's'}.</p>
            <p>{unresolvedEvidence.length} unresolved evidence check{unresolvedEvidence.length === 1 ? '' : 's'}.</p>
            <p>{missingEvidence.length} missing evidence item{missingEvidence.length === 1 ? '' : 's'}.</p>
            {validation.terminal === false && <p className="border-l-2 border-amber-500 bg-amber-50 px-2 py-1 text-amber-900">Validation is non-terminal; unresolved evidence remains.</p>}
          </div>
        </details>

        <details className="py-3">
          <summary className="cursor-pointer font-mono text-[10px] font-semibold tracking-[0.1em] text-slate-700">DOWNSTREAM IMPACT · {downstreamWarnings.length}</summary>
          <div className="mt-3 text-xs leading-5 text-slate-600">
            <p>Status: <span className="capitalize text-slate-900">{humanize(plan.downstream_impact?.status)}</span></p>
            {downstreamWarnings.length ? <ul className="mt-2 list-disc space-y-1 pl-4">{downstreamWarnings.map((warning, index) => <li key={index}>{typeof warning === 'string' ? warning : JSON.stringify(warning)}</li>)}</ul> : <p className="mt-2">No downstream warnings were returned by this run.</p>}
          </div>
        </details>

        <details className="py-3">
          <summary className="cursor-pointer font-mono text-[10px] font-semibold tracking-[0.1em] text-slate-700">LOTO SEQUENCE · {phases.length} PHASES</summary>
          <ol className="mt-3 space-y-3">
            {phases.map((phase, index) => <li className="border-l-2 border-slate-300 pl-3" key={`${phase.phase ?? index}-${phase.title ?? ''}`}>
              <p className="font-mono text-[9px] text-slate-500">PHASE {phase.phase ?? index + 1} · {phase.ref ?? ''}</p>
              <p className="mt-1 text-xs font-medium text-slate-900">{phase.title ?? 'Untitled phase'}</p>
              {phase.objective && <p className="mt-1 text-xs leading-5 text-slate-600">{phase.objective}</p>}
              {(phase.field_action_required?.length ?? 0) > 0 && <p className="mt-1 text-[10px] text-amber-800">{phase.field_action_required?.length} field action{phase.field_action_required?.length === 1 ? '' : 's'} required</p>}
            </li>)}
          </ol>
        </details>
      </div>

      <p className="mt-5 border-l-2 border-slate-400 pl-3 text-[10px] leading-4 text-slate-500">Agent-derived decision support. The deterministic validator status is authoritative for this payload. No plant action or authorisation is performed.</p>
    </div>
  )
}
