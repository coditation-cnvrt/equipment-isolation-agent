import { useEffect, useRef, useState } from 'react'

import type { AssuranceReason, DownstreamImpactWarning, IsolationPlan, IsolationPoint, IsolationRunStatus, SavedIsolationPlan } from './api'

type IsolationPlanPanelProps = {
  run: IsolationRunStatus | null
  plan: IsolationPlan | null
  error: string
  selectedPointId: string | null
  selectedImpactId: string | null
  selectedReasonId: string | null
  onPointSelect: (point: IsolationPoint) => void
  onImpactSelect: (warning: DownstreamImpactWarning) => void
  onReasonSelect: (reason: AssuranceReason) => void
  onReset: () => void
  savedPlan: SavedIsolationPlan | null
  planSaving: boolean
  planSaveError: string
  onSavePlan: (areaCode?: string) => Promise<void>
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

function assuranceLabel(status: string): string {
  return status === 'not_isolated' ? 'Isolation not demonstrated' : humanize(status)
}

const CHECK_LABELS: Record<string, string> = {
  find_bypass_paths: 'Check for bypasses or alternate routes around the selected barriers.',
  find_blinds_spades_flanges: 'Confirm the positive-isolation devices required by the work scope.',
  find_bleeds_vents_drains: 'Confirm a bleed, vent, or drain for stored-energy release.',
  find_pressure_indicators: 'Locate a pressure indicator or approved zero-energy test point.',
  confirm_zero_pressure: 'Use the located pressure indicator to confirm zero pressure, a stable hold, and no reaccumulation.',
}

function reasonTitle(reason: AssuranceReason): string {
  if (reason.code === 'boundary_path_without_barrier') {
    const label = String(reason.boundary_label || '').trim()
    if (label && label !== String(reason.boundary_component_id || '')) return label
    const drawingReference = reason.terminal?.display_text?.find((value) => /^PID[-_ ]/i.test(value.trim()))
    if (drawingReference) return `Off-page path to ${drawingReference}`
    if (label) return `Boundary path from component ${label}`
    return 'Unidentified boundary path'
  }
  if (reason.code === 'no_isolation_candidates') return 'No isolation candidates found'
  if (reason.code === 'no_deterministic_barrier') return 'No accepted isolation barrier'
  if (reason.code === 'conditional_device_manual_review') return 'Conditional device requires review'
  if (reason.code === 'zero_energy_verification_missing') return 'Zero-energy verification is missing'
  if (reason.code === 'evidence_check_incomplete') return 'Required evidence check'
  return humanize(reason.code)
}

function reasonDescription(reason: AssuranceReason): string {
  if (reason.code === 'boundary_path_without_barrier') {
    if (reason.boundary_count && !reason.boundary_label) return `${reason.boundary_count} boundary path(s) have no identified isolation barrier.`
    if (reason.terminal?.terminal_reason === 'unresolved_off_page_connector') {
      const mapping = reason.terminal.partner_mapping_status
      return mapping === 'missing'
        ? 'No isolation barrier was found before this path reached an off-page connector. The connector has no exact partner mapping, so topology beyond this drawing cannot be checked.'
        : 'No isolation barrier was found before this path reached an off-page connector.'
    }
    if (reason.terminal?.terminal_reason === 'topology_search_limit_reached') return 'No isolation barrier was found before the deterministic topology search limit was reached.'
    return 'No isolation barrier was found on this known boundary path.'
  }
  if (reason.code === 'no_isolation_candidates') return 'The deterministic candidate search returned no isolation devices for this equipment.'
  if (reason.code === 'no_deterministic_barrier') return 'Candidates were found, but none met the deterministic barrier rules.'
  if (reason.code === 'conditional_device_manual_review') return 'A selected conditional device must be confirmed before it can be accepted as a barrier.'
  if (reason.code === 'zero_energy_verification_missing') return 'The available evidence does not include proof of zero or safe energy.'
  if (reason.code === 'evidence_check_incomplete') return CHECK_LABELS[reason.check_name || ''] || `Complete the ${humanize(reason.check_name)} check.`
  return 'Additional deterministic evidence is required.'
}

function requiredAction(reason: AssuranceReason): string | null {
  if (reason.required_action === 'resolve_connector_mapping_and_rerun_validation') return 'Resolve the connector mapping, then rerun validation to identify or confirm the boundary barrier.'
  if (reason.required_action === 'traverse_partner_connector_and_rerun_validation') return 'Load and traverse the mapped partner drawing, then rerun validation.'
  if (reason.required_action === 'extend_topology_search_and_rerun_validation') return 'Extend the topology search, then rerun validation.'
  if (reason.required_action === 'identify_or_confirm_boundary_barrier_and_rerun_validation') return 'Identify or confirm a barrier on this path, then rerun validation.'
  if (reason.required_action === 'confirm_conditional_device_in_field') return 'Confirm the device type and isolation function in the field.'
  if (reason.required_action === 'provide_zero_energy_verification_evidence') return 'Provide an approved zero-energy verification method.'
  return null
}

type DownstreamImpactGroup = {
  id: string
  warning: DownstreamImpactWarning
  routeCount: number
  sourceTags: string[]
  shortestPathHops: number | null
}

function groupDownstreamImpacts(warnings: Array<DownstreamImpactWarning | string>): DownstreamImpactGroup[] {
  const grouped = new Map<string, DownstreamImpactWarning[]>()
  warnings.forEach((item, index) => {
    const warning = typeof item === 'string'
      ? { severity: 'possible', affected_id: '', affected_tag: item, affected_type: 'legacy impact record' }
      : item
    const key = String(warning.affected_id || `${warning.affected_tag || 'unknown'}:${warning.affected_class || ''}:${index}`)
    grouped.set(key, [...(grouped.get(key) ?? []), warning])
  })
  return [...grouped.entries()].map(([id, routes]) => {
    const warning = routes.find((route) => route.severity === 'likely') ?? routes[0]
    const sourceTags = [...new Set(routes.map((route) => String(route.source_tag || route.source_candidate_tag || '').trim()).filter(Boolean))].sort()
    const hops = routes.map((route) => Number(route.path_hops)).filter(Number.isFinite)
    return {
      id,
      warning,
      routeCount: routes.length,
      sourceTags,
      shortestPathHops: hops.length ? Math.min(...hops) : null,
    }
  }).sort((left, right) => {
    const severity = Number(left.warning.severity !== 'likely') - Number(right.warning.severity !== 'likely')
    return severity || String(left.warning.affected_tag || left.id).localeCompare(String(right.warning.affected_tag || right.id))
  })
}

function impactDescription(warning: DownstreamImpactWarning): string {
  if (warning.impact_type === 'loss_of_feed_or_pressure') return 'Potential loss of feed or pressure'
  if (warning.impact_type === 'instrument_reading_or_control_affected') return 'Instrument reading or control may be affected'
  if (warning.impact_type === 'off_page_or_terminal_path_affected') return 'Connected off-page or terminal path may be affected'
  if (warning.impact_type === 'relief_or_vent_context_affected') return 'Relief or vent context may be affected'
  return humanize(warning.impact_type || 'Potential downstream effect')
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
  const active = status === 'queued' || status === 'running'
  return (
    <div className="p-5">
      <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">AGENT RUN</p>
      <div aria-live="polite" className="mt-4 border-l-2 border-blue-600 bg-blue-50 p-4" role="status">
        <div className="flex items-center gap-2">
          {active && <span aria-hidden="true" className="size-4 shrink-0 animate-spin rounded-full border-2 border-blue-200 border-t-blue-700 motion-reduce:animate-none" />}
          <p className="font-mono text-xs font-semibold uppercase text-blue-900">{humanize(status)}</p>
        </div>
        <p className="mt-2 text-sm leading-5 text-blue-950">
          {status === 'queued' && 'The isolation request is waiting for an agent worker.'}
          {status === 'running' && `${stage}.`}
          {status === 'failed' && (error || run?.error?.message || 'The isolation run failed.')}
        </p>
        {active && <>
          <div aria-label="Agent run in progress" className="mt-4 h-1 overflow-hidden bg-blue-200" role="progressbar">
            <div className="agent-progress-indeterminate h-full w-1/3 bg-blue-700" />
          </div>
          <p className="mt-3 text-xs leading-5 text-blue-800">This may take a few minutes. Keep this page open.</p>
        </>}
        {run?.run_id && <p className="mt-3 break-all font-mono text-[10px] text-blue-700">RUN {run.run_id}</p>}
      </div>
      {status === 'failed' && <button className="mt-4 w-full border border-slate-400 px-3 py-2 text-xs hover:bg-slate-100" onClick={onReset} type="button">Return to work scope</button>}
    </div>
  )
}

export default function IsolationPlanPanel({ run, plan, error, selectedPointId, selectedImpactId, selectedReasonId, onPointSelect, onImpactSelect, onReasonSelect, onReset, savedPlan, planSaving, planSaveError, onSavePlan }: IsolationPlanPanelProps) {
  const [saveOpen, setSaveOpen] = useState(false)
  const [areaCode, setAreaCode] = useState('')
  const selectedReasonElementRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!selectedReasonId) return
    const frame = window.requestAnimationFrame(() => selectedReasonElementRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }))
    return () => window.cancelAnimationFrame(frame)
  }, [selectedReasonId])

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
  const explanation = validation.assurance_explanation
  const primaryReasons = explanation?.primary_reasons ?? []
  const outstandingRequirements = explanation?.outstanding_requirements ?? []
  const structuredExplanation = Boolean(explanation)
  const blockerCount = explanation?.summary.primary_reason_count
    ?? (plan.assurance_status === 'not_isolated' ? Math.max(missingBoundaryCount, 1) : 0)
  const notIsolated = plan.assurance_status === 'not_isolated'
  const primaryReasonLabel = notIsolated ? 'PRIMARY BLOCKER' : 'DETERMINING REQUIREMENT'
  const primaryReasonTone = notIsolated
    ? { label: 'text-red-700', border: 'border-red-500', background: 'bg-red-50', heading: 'text-red-950', body: 'text-red-900', detail: 'text-red-800' }
    : { label: 'text-amber-700', border: 'border-amber-500', background: 'bg-amber-50', heading: 'text-amber-950', body: 'text-amber-900', detail: 'text-amber-800' }
  const reliefCandidates = plan.relief_candidates?.items ?? []
  const downstreamWarnings = plan.downstream_impact?.warnings ?? []
  const downstreamGroups = groupDownstreamImpacts(downstreamWarnings)
  const likelyImpactCount = downstreamGroups.filter((group) => group.warning.severity === 'likely').length
  const phases = plan.loto_procedure?.phases ?? []
  const acceptedPointCount = points.filter((point) => point.validation_state === 'barrier' || point.validation_state === 'positive').length
  const allRejected = points.length > 0 && acceptedPointCount === 0

  return (
    <div className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">{savedPlan ? 'SAVED ADVISORY PLAN' : 'ADVISORY PLAN RESULT'}</p>
          {savedPlan ? <>
            <p className="mt-1 font-mono text-xs font-semibold text-slate-900">{savedPlan.plan_number} · v{savedPlan.latest_version.version_no}</p>
            <p className="mt-1 font-mono text-[9px] uppercase text-purple-800">{savedPlan.lifecycle_state} · {savedPlan.mode} · no active version</p>
          </> : <p className="mt-1 font-mono text-[10px] text-slate-500">RUN {run?.run_id?.slice(0, 12) ?? '—'}</p>}
        </div>
        <button className="border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100" onClick={onReset} type="button">New run</button>
      </div>

      {run?.agent?.orchestration_error && <div className="mt-4 border-l-2 border-amber-500 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
        Gemini orchestration became unavailable. The deterministic guardrail completed the advisory payload; review the audit trace before use.
      </div>}

      <section className={`mt-4 border-l-4 p-4 ${assuranceStyle(plan.assurance_status)}`}>
        <p className="font-mono text-[10px] tracking-[0.1em]">AUTHORITATIVE VALIDATOR STATUS</p>
        <h3 className="mt-2 text-base font-semibold">{assuranceLabel(plan.assurance_status)}</h3>
        {validation.rationale && <p className="mt-2 text-xs leading-5">{validation.rationale}</p>}
      </section>

      <dl className="mt-4 grid grid-cols-3 gap-px bg-slate-200 text-center">
        <div className="bg-slate-50 p-3"><dt className="font-mono text-[9px] text-slate-500">POINTS</dt><dd className="mt-1 text-lg font-medium">{points.length}</dd></div>
        <div className="bg-slate-50 p-3"><dt className="font-mono text-[9px] text-slate-500">COVERAGE</dt><dd className="mt-1 text-lg font-medium">{coveredBoundaryCount}/{expectedBoundaryCount}</dd></div>
        <div className="bg-slate-50 p-3"><dt className="font-mono text-[9px] text-slate-500">{notIsolated ? 'BLOCKERS' : 'REQUIREMENTS'}</dt><dd className="mt-1 text-lg font-medium">{blockerCount}</dd></div>
      </dl>

      {structuredExplanation && (primaryReasons.length > 0 || outstandingRequirements.length > 0) && <section className="mt-6 border-y border-slate-200 py-4" aria-label="Deterministic assurance explanation">
        <h3 className="font-mono text-[10px] font-semibold tracking-[0.12em] text-slate-700">WHY THIS STATUS</h3>
        {primaryReasons.length > 0 && <div className="mt-3 space-y-3">
          <p className={`font-mono text-[9px] ${primaryReasonTone.label}`}>{primaryReasonLabel}{primaryReasons.length === 1 ? '' : 'S'} · {primaryReasons.length}</p>
          {primaryReasons.map((reason) => {
            const evidenceTargets = reason.evidence_targets ?? []
            const locatable = Boolean(reason.terminal?.entity_id || reason.path_node_ids?.length || evidenceTargets.some((target) => target.entity_id || target.bbox?.length === 4 || target.path_node_ids?.length))
            const selected = selectedReasonId === reason.reason_id
            const selectedTone = notIsolated ? 'bg-red-100 ring-red-300' : 'bg-amber-100 ring-amber-300'
            return <article className={`border-l-2 px-3 py-2 ${primaryReasonTone.border} ${selected ? `${selectedTone} ring-1 ring-inset` : primaryReasonTone.background}`} key={reason.reason_id} ref={selected ? selectedReasonElementRef : undefined}>
              <h4 className={`text-xs font-semibold ${primaryReasonTone.heading}`}>{reasonTitle(reason)}</h4>
              {reason.boundary_component_id && <p className={`mt-0.5 font-mono text-[9px] ${primaryReasonTone.detail}`}>BOUNDARY SOURCE {reason.boundary_component_id}</p>}
              <p className={`mt-1 text-xs leading-5 ${primaryReasonTone.body}`}>{reasonDescription(reason)}</p>
              {evidenceTargets.length > 0 && <div className="mt-2 border border-amber-200 bg-white/70 p-2"><p className="font-mono text-[9px] font-semibold text-amber-900">DRAWING EVIDENCE CANDIDATES · {evidenceTargets.length}</p><ul className="mt-1 space-y-1 text-[10px] leading-4 text-amber-950">{evidenceTargets.slice(0, 6).map((target, index) => <li key={`${target.entity_id}-${index}`}><span>• {target.tag || humanize(target.role || target.entity_class || target.entity_id)} · {humanize(target.acceptance || 'review required')}</span>{target.verification_instruction && <span className="mt-0.5 block pl-2 text-amber-800">{target.verification_instruction}</span>}</li>)}</ul>{evidenceTargets.length > 6 && <p className="mt-1 text-[9px] text-amber-800">+ {evidenceTargets.length - 6} additional topology paths</p>}</div>}
              {reason.path_node_classes?.length ? <p className={`mt-2 text-[10px] leading-4 ${primaryReasonTone.detail}`}><span className="font-semibold">Known path:</span> {reason.path_node_classes.map(humanize).join(' → ')}</p> : null}
              {(reason.encountered_devices?.length ?? 0) > 0 && <div className="mt-2 border border-red-200 bg-white/70 p-2"><p className="font-mono text-[9px] font-semibold text-red-800">ENCOUNTERED · NOT ACCEPTED AS ISOLATION</p><ul className="mt-1 space-y-1 text-[10px] leading-4 text-red-900">{reason.encountered_devices?.map((device) => <li key={device.entity_id}>• {device.tag || device.entity_id} · {humanize(device.entity_class || device.entity_type)} · context only under the configured isolation policy</li>)}</ul></div>}
              {reason.terminal?.display_text?.length ? <p className={`mt-1 text-[10px] leading-4 ${primaryReasonTone.detail}`}>Drawing label: {reason.terminal.display_text.join(' · ')}. Label shown for context only; it is not connectivity proof.</p> : null}
              {requiredAction(reason) && <p className={`mt-2 text-[10px] font-medium leading-4 ${primaryReasonTone.heading}`}>Required resolution: {requiredAction(reason)}</p>}
              {locatable && <button className={`mt-2 border bg-white px-2 py-1 font-mono text-[9px] font-semibold ${notIsolated ? 'border-red-400 text-red-800 hover:bg-red-50' : 'border-amber-400 text-amber-900 hover:bg-amber-50'}`} onClick={() => onReasonSelect(reason)} type="button">{selected ? 'SHOWN ON DRAWING' : reason.code === 'evidence_check_incomplete' ? 'REVIEW EVIDENCE ON DRAWING' : 'VIEW PATH ON DRAWING'}</button>}
              {!locatable && <p className="mt-2 font-mono text-[9px] text-amber-800">No exact drawing evidence candidate is recorded. A field method or corrected drawing evidence is required.</p>}
              <details className={`mt-2 text-[9px] ${primaryReasonTone.detail}`}><summary className="cursor-pointer">Technical details</summary><dl className="mt-1 space-y-0.5 font-mono"><div><dt className="inline">Reason: </dt><dd className="inline">{reason.code}</dd></div>{reason.boundary_id && <div><dt className="inline">Boundary: </dt><dd className="inline break-all">{reason.boundary_id}</dd></div>}{reason.terminal?.entity_id && <div><dt className="inline">Terminal entity: </dt><dd className="inline break-all">{reason.terminal.entity_id}</dd></div>}</dl></details>
            </article>
          })}
        </div>}
        {outstandingRequirements.length > 0 && <details className="mt-4">
          <summary className="cursor-pointer font-mono text-[9px] font-semibold text-amber-800">OUTSTANDING REQUIREMENTS · {outstandingRequirements.length}</summary>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-slate-600">{outstandingRequirements.map((reason) => <li key={reason.reason_id}>{reasonDescription(reason)}</li>)}</ul>
        </details>}
      </section>}

      {reliefCandidates.length > 0 && <section className="mt-6 border-l-2 border-cyan-600 bg-cyan-50 p-3" aria-label="Relief and energy-release context">
        <div className="flex items-baseline justify-between gap-3"><h3 className="font-mono text-[10px] font-semibold tracking-[0.12em] text-cyan-950">RELIEF / ENERGY-RELEASE CONTEXT</h3><span className="font-mono text-[9px] text-cyan-800">{reliefCandidates.length}</span></div>
        <p className="mt-2 text-xs leading-5 text-cyan-950">These devices are not accepted as isolation barriers. Safe discharge, operability, and an approved zero-energy verification method must still be confirmed.</p>
        <ul className="mt-2 space-y-2">{reliefCandidates.map((candidate) => <li className="border border-cyan-200 bg-white/70 p-2" key={candidate.id}><p className="text-xs font-medium text-cyan-950">{candidate.tag || candidate.id}</p><p className="mt-0.5 text-[10px] text-cyan-800">{humanize(candidate.entity_class || candidate.relief_type)} · context only</p></li>)}</ul>
      </section>}

      <section className="mt-6">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">{allRejected ? 'CANDIDATE LOCATIONS · NOT ACCEPTED AS ISOLATION' : plan.assurance_status === 'not_isolated' ? 'PROPOSED ISOLATION POINTS · PLAN INCOMPLETE' : 'PROPOSED ISOLATION POINTS'}</h3>
          <span className="text-[10px] text-slate-500">Click to select on drawing</span>
        </div>
        <ol className="mt-2 space-y-2">
          {points.map((point, index) => {
            const selectionId = point.selection_id || ''
            const canLocate = Boolean(point.drawing_entity_id || point.bbox?.length === 4)
            const selected = Boolean(canLocate && selectionId && selectedPointId === selectionId)
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
        {!structuredExplanation && <details className="py-3" open={blockerCount > 0}>
          <summary className="cursor-pointer font-mono text-[10px] font-semibold tracking-[0.1em] text-slate-700">LEGACY VALIDATION DETAILS</summary>
          <div className="mt-3 space-y-2 text-xs leading-5 text-slate-600">
            <p className="border-l-2 border-amber-500 bg-amber-50 px-2 py-1 text-amber-900">Detailed deterministic reasons were not recorded for this historical run.</p>
            <p>{missingBoundaryCount} missing boundary path{missingBoundaryCount === 1 ? '' : 's'}.</p>
            <p>{unselectedSources.length} unselected boundary source{unselectedSources.length === 1 ? '' : 's'}.</p>
            <p>{manualChecks.length} manual visual check{manualChecks.length === 1 ? '' : 's'}.</p>
            <p>{unresolvedObligations.length} unresolved isolation obligation{unresolvedObligations.length === 1 ? '' : 's'}.</p>
            <p>{unresolvedEvidence.length} unresolved evidence check{unresolvedEvidence.length === 1 ? '' : 's'}.</p>
            <p>{missingEvidence.length} legacy evidence note{missingEvidence.length === 1 ? '' : 's'}.</p>
          </div>
        </details>}

        <details className="py-3" open={downstreamGroups.length > 0}>
          <summary className="cursor-pointer font-mono text-[10px] font-semibold tracking-[0.1em] text-slate-700">DOWNSTREAM IMPACT · {downstreamGroups.length} TARGET{downstreamGroups.length === 1 ? '' : 'S'}</summary>
          <div className="mt-3 text-xs leading-5 text-slate-600">
            {plan.downstream_impact?.status === 'unavailable' && <p className="border-l-2 border-amber-500 bg-amber-50 px-2 py-1 text-amber-900">Downstream analysis was unavailable{plan.downstream_impact.error ? `: ${plan.downstream_impact.error}` : '.'}</p>}
            {downstreamGroups.length > 0 ? <>
              <div className="grid grid-cols-3 gap-px bg-slate-200 text-center">
                <div className="bg-slate-50 p-2"><p className="font-mono text-[8px] text-slate-500">TARGETS</p><p className="mt-0.5 text-sm font-medium text-slate-900">{downstreamGroups.length}</p></div>
                <div className="bg-slate-50 p-2"><p className="font-mono text-[8px] text-slate-500">PATHS</p><p className="mt-0.5 text-sm font-medium text-slate-900">{downstreamWarnings.length}</p></div>
                <div className="bg-slate-50 p-2"><p className="font-mono text-[8px] text-slate-500">LIKELY</p><p className="mt-0.5 text-sm font-medium text-slate-900">{likelyImpactCount}</p></div>
              </div>
              <p className="mt-3 text-[10px] leading-4">Affected targets are derived from HILT connectivity. “Possible” means the path is connected but flow direction is unknown or weak.</p>
              <ol className="mt-3 space-y-2">
                {downstreamGroups.map((group, index) => {
                  const warning = group.warning
                  const selected = selectedImpactId === group.id
                  const locatable = Boolean(warning.affected_id || warning.affected_bbox?.length === 4)
                  return <li key={group.id}>
                    <button
                      className={`w-full border-l-2 p-3 text-left transition-colors ${selected ? 'border-orange-600 bg-orange-100' : warning.severity === 'likely' ? 'border-red-500 bg-red-50 hover:bg-red-100' : 'border-orange-400 bg-orange-50 hover:bg-orange-100'} disabled:cursor-default`}
                      disabled={!locatable}
                      onClick={() => onImpactSelect(warning)}
                      type="button"
                    >
                      <span className="flex items-start justify-between gap-2">
                        <span className="min-w-0">
                          <span className="block break-words text-xs font-semibold text-slate-950">{warning.affected_tag || warning.affected_id || `Affected target ${index + 1}`}</span>
                          <span className="mt-0.5 block text-[10px] capitalize text-slate-600">{humanize(warning.affected_type || warning.affected_class || 'downstream target')}</span>
                        </span>
                        <span className={`shrink-0 px-1.5 py-0.5 font-mono text-[8px] font-semibold uppercase ${warning.severity === 'likely' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'}`}>{warning.severity || 'possible'}</span>
                      </span>
                      <span className="mt-2 block text-[11px] font-medium text-slate-800">{impactDescription(warning)}</span>
                      <span className="mt-1 block text-[10px] leading-4 text-slate-600">
                        {group.sourceTags.length ? `From ${group.sourceTags.join(', ')}` : 'Source isolation point not labelled'}
                        {group.shortestPathHops !== null ? ` · ${group.shortestPathHops} hop${group.shortestPathHops === 1 ? '' : 's'}` : ''}
                        {group.routeCount > 1 ? ` · ${group.routeCount} paths` : ''}
                      </span>
                      {locatable && <span className="mt-2 block font-mono text-[9px] font-semibold text-orange-800">{selected ? 'SHOWN ON DRAWING' : 'VIEW ON DRAWING'}</span>}
                    </button>
                  </li>
                })}
              </ol>
            </> : plan.downstream_impact?.status !== 'unavailable' && <p>No downstream targets were identified by this run.</p>}
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

      {!savedPlan && run?.status === 'succeeded' && <section className="mt-5 border border-slate-300 bg-slate-50 p-3">
        {!saveOpen ? <button className="w-full border border-blue-700 bg-white px-3 py-2 font-mono text-[10px] font-semibold tracking-wide text-blue-800 hover:bg-blue-50" disabled={planSaving} onClick={() => setSaveOpen(true)} type="button">SAVE AS DRAFT PLAN</button> : <form onSubmit={(event) => { event.preventDefault(); void onSavePlan(areaCode).then(() => setSaveOpen(false)).catch(() => undefined) }}>
          <p className="text-xs font-medium text-slate-900">Save advisory plan</p>
          <p className="mt-1 text-[10px] leading-4 text-slate-600">Creates an immutable advisory draft. It does not authorise isolation or perform plant action.</p>
          <label className="mt-3 block text-[10px] font-medium text-slate-700" htmlFor="plan-area-code">Area code (optional)<input className="mt-1 block w-full border border-slate-300 bg-white px-2 py-1.5 text-xs outline-none focus:border-blue-700" id="plan-area-code" maxLength={100} onChange={(event) => setAreaCode(event.target.value)} placeholder="Area 12" value={areaCode} /></label>
          <div className="mt-3 flex justify-end gap-2"><button className="border border-slate-300 px-3 py-1.5 text-[10px] hover:bg-white" disabled={planSaving} onClick={() => setSaveOpen(false)} type="button">CANCEL</button><button className="bg-blue-700 px-3 py-1.5 font-mono text-[10px] text-white disabled:bg-slate-300" disabled={planSaving} type="submit">{planSaving ? 'SAVING…' : 'SAVE DRAFT'}</button></div>
        </form>}
        {planSaveError && <p className="mt-2 border-l-2 border-red-500 bg-red-50 px-2 py-1 text-[10px] text-red-900">{planSaveError}</p>}
      </section>}

      <p className="mt-5 border-l-2 border-slate-400 pl-3 text-[10px] leading-4 text-slate-500">Agent-derived decision support. The deterministic validator status is authoritative for this payload. No plant action or authorisation is performed.</p>
    </div>
  )
}
