import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'

import {
  createIsolationPlanFromRun,
  createIsolationRun,
  getCollections,
  getDrawings,
  getEquipment,
  getEquipmentBBox,
  getHiltGraph,
  getHiltSymbols,
  getIsolationPlan,
  getIsolationPlans,
  getIsolationResult,
  getIsolationRun,
  getIsolationRuns,
  getProjects,
  getUniGraphProjects,
  streamIsolationRunEvents,
  type AssuranceReason,
  type Collection,
  type DownstreamImpactWarning,
  type Drawing,
  type Equipment,
  type IsolationPoint,
  type IsolationResult,
  type IsolationRunStatus,
  type Project,
  type SavedIsolationPlan,
  type UniGraphProject,
} from './api'
import { type HiltGraphInput, type HiltSelection, type HiltSymbol } from '@coditation-cnvrt/p360-hitl-viewer'
import ContextBreadcrumbs from './ContextBreadcrumbs'
import DrawingModeSummary from './DrawingModeSummary'
import IsolationMapSidebar from './IsolationMapSidebar'
import IsolationPlanPanel from './IsolationPlanPanel'
import { DEFAULT_ISOLATION_MAP_LAYERS, type IsolationMapLayer, type IsolationViewMode } from './isolation-map'
import PlanningSidebar from './PlanningSidebar'
import Skeleton from './Skeleton'
import { useUser } from './auth-context'
import p360Logo from './assets/p360logo.png'

const Workspace = lazy(() => import('./Workspace'))

const RUN_STAGE_LABELS: Record<string, string> = {
  fetch_boundary: 'Reading the equipment boundary',
  find_candidates: 'Finding isolation candidates',
  resolve_bboxes: 'Locating points on the drawing',
  analyze_isolation_obligations: 'Checking isolation obligations',
  analyze_isolation_schemes_and_relief: 'Analysing schemes and relief paths',
  build_evidence: 'Building assurance evidence',
  analyze_instrument_context: 'Reviewing instrument context',
  validate: 'Running authoritative validation',
  analyze_downstream_impact: 'Checking downstream impact',
  build_loto_procedure: 'Building the regulatory LOTO sequence',
  finalize_plan: 'Finalising the advisory plan',
}

type RunTimelineStage = {
  label: string
  tools: string[]
  milestones: string[]
  completeOnRunSuccess?: boolean
}

const RUN_TIMELINE: RunTimelineStage[] = [
  { label: 'Boundary and candidates', tools: ['fetch_boundary', 'find_candidates', 'resolve_bboxes'], milestones: ['resolve_bboxes'] },
  { label: 'Isolation topology', tools: ['analyze_isolation_obligations', 'analyze_isolation_schemes_and_relief', 'list_unselected_sources', 'investigate_source'], milestones: ['analyze_isolation_schemes_and_relief'] },
  { label: 'Evidence and instruments', tools: ['build_evidence', 'analyze_instrument_context'], milestones: ['build_evidence', 'analyze_instrument_context'] },
  { label: 'Authoritative validation', tools: ['validate'], milestones: ['validate'] },
  { label: 'Downstream impact', tools: ['analyze_downstream_impact'], milestones: ['analyze_downstream_impact'] },
  { label: 'LOTO sequence and final plan', tools: ['get_osha_guidance', 'build_loto_procedure', 'set_isolation_order', 'finalize_plan'], milestones: [], completeOnRunSuccess: true },
]

function ContextLoadingOverlay({ stage }: { stage: string }) {
  return <div className="fixed inset-0 z-[105] flex items-center justify-center bg-slate-950/35 p-5 backdrop-blur-[2px]" role="status" aria-live="polite">
    <div className="w-full max-w-sm border border-slate-300 bg-white p-6 shadow-2xl">
      <div className="flex items-center gap-4">
        <span aria-hidden="true" className="size-7 shrink-0 animate-spin rounded-full border-[3px] border-blue-200 border-t-blue-700 motion-reduce:animate-none" />
        <div><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-blue-700">Planning context</p><h2 className="mt-1 text-lg font-medium text-slate-950">Preparing workspace</h2></div>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-600">{stage}</p>
      <div aria-label="Planning context loading" className="mt-5 h-1.5 overflow-hidden bg-blue-100" role="progressbar">
        <div className="agent-progress-indeterminate h-full w-1/3 bg-blue-700" />
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-500">Context actions will become available when the required authenticated data is ready.</p>
    </div>
  </div>
}

function IsolationRunOverlay({ submitting, run, completedTools }: { submitting: boolean; run: IsolationRunStatus | null; completedTools: string[] }) {
  const status = submitting ? 'Starting isolation analysis' : run?.status === 'queued' ? 'Waiting for an agent worker' : 'Isolation analysis in progress'
  const tool = run?.agent?.progress?.tool || ''
  const stage = submitting
    ? 'Submitting the selected equipment and work scope.'
    : run?.status === 'queued'
      ? 'The request will begin as soon as a worker is available.'
      : `${RUN_STAGE_LABELS[tool] || 'Gathering graph evidence and running deterministic checks'}.`
  const completed = new Set(completedTools)
  const stageIsComplete = (item: RunTimelineStage) => item.completeOnRunSuccess
    ? run?.status === 'succeeded'
    : item.milestones.every((milestone) => completed.has(milestone))
  const completedStageCount = RUN_TIMELINE.filter(stageIsComplete).length
  return <div className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/40 p-5 backdrop-blur-[2px]" role="status" aria-live="polite">
    <div className="w-full max-w-3xl border border-slate-300 bg-white p-6 shadow-2xl">
      <div className="flex items-center gap-4">
        <span aria-hidden="true" className="size-7 shrink-0 animate-spin rounded-full border-[3px] border-blue-200 border-t-blue-700 motion-reduce:animate-none" />
        <div><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-blue-700">Advisory isolation plan</p><h2 className="mt-1 text-lg font-medium text-slate-950">{status}</h2></div>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-600">{stage}</p>
      <div aria-label="Agent run in progress" className="mt-5 h-1.5 overflow-hidden bg-blue-100" role="progressbar">
        <div className="agent-progress-indeterminate h-full w-1/3 bg-blue-700" />
      </div>
      <div className="mt-5 border-y border-slate-200 py-3">
        <div className="mb-3 flex items-baseline justify-between gap-3"><p className="font-mono text-[9px] font-semibold tracking-[0.12em] text-slate-500">RUN TIMELINE</p><p className="font-mono text-[9px] text-slate-500">{completedStageCount} OF {RUN_TIMELINE.length} COMPLETE</p></div>
        <div className="overflow-x-auto pb-1">
          <ol className="grid min-w-[42rem] grid-cols-6 px-2">
            {RUN_TIMELINE.map((item, index) => {
              const done = stageIsComplete(item)
              const active = !done && item.tools.includes(tool)
              return <li className="relative min-w-0 text-center" key={item.label}>
                {index < RUN_TIMELINE.length - 1 && <span aria-hidden="true" className={`absolute left-1/2 top-2.5 h-0.5 w-full ${done ? 'bg-emerald-500' : 'bg-slate-200'}`} />}
                <span className={`relative z-10 mx-auto flex size-5 items-center justify-center rounded-full border font-mono text-[9px] font-semibold ${done ? 'border-emerald-600 bg-emerald-600 text-white' : active ? 'border-blue-700 bg-blue-700 text-white ring-4 ring-blue-100' : 'border-slate-200 bg-white text-slate-400'}`}>{done ? '✓' : index + 1}</span>
                <span className={`mx-auto mt-2 block max-w-24 text-[10px] leading-4 ${done ? 'font-medium text-slate-700' : active ? 'font-semibold text-blue-900' : 'text-slate-400'}`}>{item.label}</span>
                <span aria-hidden={!active} className={`mt-1 block h-3 font-mono text-[8px] font-semibold ${active ? 'text-blue-700' : 'invisible'}`}>{active ? 'IN PROGRESS' : 'STATUS'}</span>
              </li>
            })}
          </ol>
        </div>
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-500">This timeline reports completed tool stages only; it does not estimate time or physical isolation progress. Keep this page open while analysis completes.</p>
    </div>
  </div>
}

function getSymbolProjectId(graphInput: HiltGraphInput, fallback: string): string {
  let value: unknown = graphInput
  for (let depth = 0; depth < 4 && typeof value === 'object' && value !== null; depth += 1) {
    const record = value as Record<string, unknown>
    if (typeof record.jobData === 'object' && record.jobData !== null) {
      const jobData = record.jobData as Record<string, unknown>
      return String(jobData.projectID ?? jobData.project_id ?? fallback)
    }
    value = record.hilt_graph ?? record.graph
  }
  return fallback
}

function App() {
  const { logout, user } = useUser()
  const [projects, setProjects] = useState<Project[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [drawings, setDrawings] = useState<Drawing[]>([])
  const [unigraphProjects, setUnigraphProjects] = useState<UniGraphProject[]>([])
  const [equipment, setEquipment] = useState<Equipment[]>([])
  const [equipmentLoading, setEquipmentLoading] = useState(false)
  const [projectId, setProjectId] = useState('')
  const [collectionId, setCollectionId] = useState('')
  const [drawingId, setDrawingId] = useState('')
  const [unigraphProjectId, setUnigraphProjectId] = useState('')
  const [equipmentId, setEquipmentId] = useState('')
  const [equipmentBBox, setEquipmentBBox] = useState<number[]>([])
  const [bboxLoading, setBBoxLoading] = useState(false)
  const [hiltGraph, setHiltGraph] = useState<HiltGraphInput | null>(null)
  const [hiltSymbols, setHiltSymbols] = useState<HiltSymbol[]>([])
  const [drawingLoading, setDrawingLoading] = useState(false)
  const [drawingError, setDrawingError] = useState('')
  const [drawingSelection, setDrawingSelection] = useState<HiltSelection | null>(null)
  const [intrusiveWork, setIntrusiveWork] = useState(true)
  const [highRiskService, setHighRiskService] = useState(true)
  const [scopeNote, setScopeNote] = useState('')
  const [isolationRun, setIsolationRun] = useState<IsolationRunStatus | null>(null)
  const [completedRunTools, setCompletedRunTools] = useState<string[]>([])
  const [isolationResult, setIsolationResult] = useState<IsolationResult | null>(null)
  const [isolationError, setIsolationError] = useState('')
  const [isolationSubmitting, setIsolationSubmitting] = useState(false)
  const [selectedIsolationPointId, setSelectedIsolationPointId] = useState<string | null>(null)
  const [selectedDownstreamImpactId, setSelectedDownstreamImpactId] = useState<string | null>(null)
  const [selectedAssuranceReasonId, setSelectedAssuranceReasonId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<IsolationViewMode>('drawing')
  const [mapLayers, setMapLayers] = useState({ ...DEFAULT_ISOLATION_MAP_LAYERS })
  const [pastRuns, setPastRuns] = useState<IsolationRunStatus[]>([])
  const [pastRunsLoading, setPastRunsLoading] = useState(false)
  const [pastRunsError, setPastRunsError] = useState('')
  const [savedPlans, setSavedPlans] = useState<SavedIsolationPlan[]>([])
  const [savedPlansLoading, setSavedPlansLoading] = useState(false)
  const [savedPlansError, setSavedPlansError] = useState('')
  const [selectedSavedPlan, setSelectedSavedPlan] = useState<SavedIsolationPlan | null>(null)
  const [planSaving, setPlanSaving] = useState(false)
  const [planSaveError, setPlanSaveError] = useState('')
  const [pendingHistoricalEquipmentTag, setPendingHistoricalEquipmentTag] = useState('')
  const [historicalNavigation, setHistoricalNavigation] = useState<{ kind: 'plan' | 'run'; label: string; runId: string; waitForContext: boolean } | null>(null)
  const [initialBootstrapPending, setInitialBootstrapPending] = useState(true)
  const [loading, setLoading] = useState('projects')
  const [error, setError] = useState('')
  const didLoadProjects = useRef(false)
  const historicalNavigationLock = useRef(false)
  const preloadedDrawingKey = useRef('')
  const preloadedBBoxKey = useRef('')

  const selectedProject = projects.find((item) => item.id === projectId)
  const selectedCollection = collections.find((item) => item.id === collectionId)
  const selectedDrawing = drawings.find((item) => item.id === drawingId)
  const selectedUniGraph = unigraphProjects.find((item) => item.id === unigraphProjectId)
  const selectedEquipment = equipment.find((item) => item.id === equipmentId)
  const isolationPlan = isolationResult?.data?.[0] ?? null
  const isolationPoints = useMemo(() => {
    const validation = isolationPlan?.isolation_validation
    const barriers = new Set((validation?.barrier_candidate_ids ?? []).map(String))
    const positives = new Set((validation?.positive_candidate_ids ?? []).map(String))
    const manual = new Set((validation?.manual_review_candidate_ids ?? []).map(String))
    return (isolationPlan?.isolation_points ?? []).map((point, index) => {
      const id = String(point.uuid)
      return {
        ...point,
        selection_id: `candidate:${id}:${index}`,
        validation_state: barriers.has(id) ? 'barrier' as const
          : positives.has(id) ? 'positive' as const
            : manual.has(id) ? 'manual' as const
              : 'rejected' as const,
      }
    })
  }, [isolationPlan])
  const displayedIsolationPlan = useMemo(
    () => isolationPlan ? { ...isolationPlan, isolation_points: isolationPoints } : null,
    [isolationPlan, isolationPoints],
  )
  const downstreamImpacts = (displayedIsolationPlan?.downstream_impact?.warnings ?? [])
    .filter((warning): warning is DownstreamImpactWarning => typeof warning !== 'string')
  const assuranceExplanation = displayedIsolationPlan?.isolation_validation?.assurance_explanation
  const assuranceReasons = [
    ...(assuranceExplanation?.primary_reasons ?? []),
    ...(assuranceExplanation?.outstanding_requirements ?? []),
  ]
  const selectedAssuranceReason = assuranceReasons.find((reason) => reason.reason_id === selectedAssuranceReasonId) ?? null
  const runInProgress = isolationRun?.status === 'queued' || isolationRun?.status === 'running'
  const historyDisabled = Boolean(historicalNavigation || runInProgress || loading || equipmentLoading || drawingLoading)
  const contextLoadingStage = loading === 'projects'
    ? 'Loading the projects available to your CNVRT account.'
    : loading === 'collections'
      ? 'Loading collections for the selected project.'
      : loading === 'unigraph'
        ? 'Loading drawings and UniGraph exports for the selected collection.'
        : equipmentLoading
          ? 'Loading equipment from the selected UniGraph.'
          : drawingLoading
            ? 'Loading the selected equipment’s authoritative source drawing.'
            : initialBootstrapPending
              ? 'Loading saved plans and recent isolation runs.'
              : ''
  const historyDisabledReason = historicalNavigation
    ? `Opening ${historicalNavigation.label}…`
    : runInProgress
      ? 'Wait for the current isolation run to finish before opening history.'
      : 'Planning context is loading. Saved plans and recent runs will be available shortly.'
  const ready = Boolean(selectedProject && selectedCollection && selectedUniGraph)
  const projectOptions = projects.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const collectionOptions = collections.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const unigraphOptions = unigraphProjects.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const equipmentOptions = equipment.map((item) => ({
    value: item.id,
    label: `${item.tag || item.name} (${item.entity_class})`,
    searchText: `${item.tag} ${item.name} ${item.entity_class} ${item.job_name}`,
  }))
  const contextBreadcrumbItems = [
    { key: 'project', label: 'Project', value: projectId, placeholder: 'Choose project', options: projectOptions, loading: loading === 'projects', onChange: (value: string) => { void selectProject(value) } },
    { key: 'collection', label: 'Collection', value: collectionId, placeholder: 'Choose collection', options: collectionOptions, disabled: !projectId, loading: loading === 'collections', onChange: (value: string) => { void selectCollection(value) } },
    { key: 'graph', label: 'UniGraph', value: unigraphProjectId, placeholder: 'Choose graph', options: unigraphOptions, disabled: !collectionId, loading: loading === 'unigraph', onChange: (value: string) => { void selectUniGraph(value) } },
    { key: 'equipment', label: 'Equipment', value: equipmentId, placeholder: 'Choose equipment', options: equipmentOptions, disabled: !unigraphProjectId, loading: equipmentLoading, onChange: selectEquipment, onClear: clearEquipmentSelection },
  ]

  useEffect(() => {
    if (didLoadProjects.current) return
    didLoadProjects.current = true
    void loadProjects()
  }, [])

  useEffect(() => {
    if (!initialBootstrapPending || loading || savedPlansLoading || pastRunsLoading) return
    setInitialBootstrapPending(false)
  }, [initialBootstrapPending, loading, pastRunsLoading, savedPlansLoading])

  useEffect(() => {
    const bboxKey = selectedEquipment && drawingId ? `${drawingId}:${selectedEquipment.node_id}` : ''
    if (bboxKey && preloadedBBoxKey.current === bboxKey) {
      preloadedBBoxKey.current = ''
      setBBoxLoading(false)
      return
    }
    if (!selectedEquipment || !drawingId) {
      setEquipmentBBox([])
      setBBoxLoading(false)
      return
    }
    let active = true
    setBBoxLoading(true)
    void getEquipmentBBox(drawingId, selectedEquipment.node_id).then((bbox) => {
      if (active) {
        setEquipmentBBox(bbox)
        setBBoxLoading(false)
      }
    })
    return () => { active = false }
  }, [drawingId, selectedEquipment])

  useEffect(() => {
    setDrawingSelection(null)
    const drawingKey = projectId && drawingId ? `${projectId}:${drawingId}` : ''
    if (drawingKey && preloadedDrawingKey.current === drawingKey) {
      preloadedDrawingKey.current = ''
      setDrawingLoading(false)
      return
    }
    if (!projectId || !drawingId) {
      setHiltGraph(null)
      setHiltSymbols([])
      setDrawingLoading(false)
      setDrawingError('')
      return
    }
    let active = true
    setDrawingLoading(true)
    setDrawingError('')
    void (async () => {
      try {
        const nextGraph = await getHiltGraph(drawingId)
        const nextSymbols = await getHiltSymbols(getSymbolProjectId(nextGraph, projectId))
        if (!active) return
        setHiltGraph(nextGraph)
        setHiltSymbols(nextSymbols)
      } catch (reason: unknown) {
        if (!active) return
        setHiltGraph(null)
        setHiltSymbols([])
        setDrawingError(reason instanceof Error ? reason.message : 'Unable to load the HILT drawing.')
      } finally {
        if (active) setDrawingLoading(false)
      }
    })()
    return () => { active = false }
  }, [drawingId, projectId])

  useEffect(() => {
    if (historicalNavigationLock.current) return
    let active = true
    setSavedPlansLoading(true)
    setSavedPlansError('')
    const filters = selectedEquipment && projectId && collectionId && drawingId && unigraphProjectId ? {
      equipmentTag: selectedEquipment.tag || selectedEquipment.name,
      jobId: drawingId,
      cnvrtProjectId: projectId,
      collectionId,
      unigraphProjectId,
      limit: 20,
    } : { limit: 20 }
    void getIsolationPlans(filters).then((plans) => {
      if (active) setSavedPlans(plans)
    }).catch((reason: unknown) => {
      if (active) {
        setSavedPlans([])
        setSavedPlansError(reason instanceof Error ? reason.message : 'Unable to load saved plans.')
      }
    }).finally(() => {
      if (active) setSavedPlansLoading(false)
    })
    return () => { active = false }
  }, [collectionId, drawingId, projectId, selectedEquipment, unigraphProjectId])

  useEffect(() => {
    if (historicalNavigationLock.current) return
    let active = true
    setPastRunsLoading(true)
    setPastRunsError('')
    const filters = selectedEquipment && projectId && collectionId && drawingId && unigraphProjectId ? {
      equipmentTag: selectedEquipment.tag || selectedEquipment.name,
      jobId: drawingId,
      cnvrtProjectId: projectId,
      collectionId,
      unigraphProjectId,
      limit: 20,
    } : { limit: 20 }
    void getIsolationRuns(filters).then((runs) => {
      if (active) setPastRuns(runs)
    }).catch((reason: unknown) => {
      if (active) {
        setPastRuns([])
        setPastRunsError(reason instanceof Error ? reason.message : 'Unable to load previous runs.')
      }
    }).finally(() => {
      if (active) setPastRunsLoading(false)
    })
    return () => { active = false }
  }, [collectionId, drawingId, projectId, selectedEquipment, unigraphProjectId])

  useEffect(() => {
    if (!pendingHistoricalEquipmentTag || drawingLoading || equipmentLoading) return
    const wanted = pendingHistoricalEquipmentTag.trim().toLowerCase()
    const match = equipment.find((item) => [item.tag, item.name].some((value) => value.trim().toLowerCase() === wanted))
    if (match) setEquipmentId(match.id)
    else setIsolationError(`The saved equipment “${pendingHistoricalEquipmentTag}” is not present in the restored drawing.`)
    setPendingHistoricalEquipmentTag('')
  }, [drawingLoading, equipment, equipmentLoading, pendingHistoricalEquipmentTag])

  useEffect(() => {
    const runId = isolationRun?.run_id
    if (!runId || !['queued', 'running'].includes(isolationRun.status)) return
    const controller = new AbortController()
    let active = true
    let reconnectTimer: number | null = null

    const reconcile = async () => {
      const nextRun = await getIsolationRun(runId)
      if (!active) return
      setIsolationRun(nextRun)
      if (nextRun.status === 'failed') setIsolationError(nextRun.error?.message || 'The isolation run failed.')
    }

    const connect = async () => {
      try {
        let terminalEventReceived = false
        await streamIsolationRunEvents(runId, {
          onEvent: (event) => {
            if (!active || !['tool_call', 'tool_result'].includes(event.kind)) return
            const tool = String(event.payload?.name ?? '')
            if (!tool) return
            setIsolationRun((current) => current?.run_id === runId ? {
              ...current,
              status: 'running',
              agent: {
                ...current.agent,
                progress: { kind: event.kind, tool, updated_at: Date.now() / 1000 },
              },
            } : current)
            if (event.kind === 'tool_call') {
              setCompletedRunTools((current) => current.filter((completedTool) => completedTool !== tool))
            } else if (event.kind === 'tool_result') {
              setCompletedRunTools((current) => current.includes(tool) ? current : [...current, tool])
            }
          },
          onDone: () => { terminalEventReceived = true },
        }, controller.signal)
        if (active) {
          await reconcile()
          if (!terminalEventReceived) throw new Error('Run event stream ended before a terminal event.')
        }
      } catch {
        if (!active || controller.signal.aborted) return
        try {
          await reconcile()
        } catch {
          // A transient stream/status failure is retried without declaring the run failed.
        }
        if (active) reconnectTimer = window.setTimeout(() => { void connect() }, 2000)
      }
    }

    void connect()
    return () => {
      active = false
      controller.abort()
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
    }
  }, [isolationRun?.run_id, isolationRun?.status])

  useEffect(() => {
    if (!isolationRun?.run_id || !['succeeded', 'failed'].includes(isolationRun.status)) return
    setPastRuns((current) => [isolationRun, ...current.filter((item) => item.run_id !== isolationRun.run_id)].slice(0, 20))
  }, [isolationRun])

  useEffect(() => {
    if (displayedIsolationPlan) setViewMode('isolation')
  }, [displayedIsolationPlan])

  useEffect(() => {
    if (!isolationRun?.run_id || isolationRun.status !== 'succeeded' || isolationResult) return
    let active = true
    void getIsolationResult(isolationRun.run_id).then((result) => {
      if (!active) return
      setIsolationResult(result)
      setIsolationError('')
    }).catch((reason: unknown) => {
      if (!active) return
      setIsolationError(reason instanceof Error ? reason.message : 'The run succeeded, but its result could not be loaded.')
      historicalNavigationLock.current = false
      setHistoricalNavigation((current) => current?.runId === isolationRun.run_id ? null : current)
    })
    return () => { active = false }
  }, [isolationResult, isolationRun?.run_id, isolationRun?.status])

  useEffect(() => {
    if (!historicalNavigation || isolationRun?.run_id !== historicalNavigation.runId || !isolationResult) return
    if (historicalNavigation.waitForContext && (drawingLoading || (pendingHistoricalEquipmentTag && !drawingError))) return
    historicalNavigationLock.current = false
    setHistoricalNavigation(null)
  }, [drawingError, drawingLoading, historicalNavigation, isolationResult, isolationRun?.run_id, pendingHistoricalEquipmentTag])

  async function loadProjects() {
    setLoading('projects')
    setError('')
    try {
      setProjects(await getProjects())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load CNVRT projects.')
    } finally {
      setLoading('')
    }
  }

  function retryPlanningContext() {
    if (!projectId) {
      void loadProjects()
      return
    }
    if (!collectionId) {
      void selectProject(projectId)
      return
    }
    if (!unigraphProjectId) {
      void selectCollection(collectionId)
      return
    }
    void selectUniGraph(unigraphProjectId)
  }

  async function selectProject(nextProjectId: string) {
    resetIsolationRun()
    setProjectId(nextProjectId)
    setCollectionId('')
    setDrawingId('')
    setUnigraphProjectId('')
    setEquipmentId('')
    setEquipmentBBox([])
    setCollections([])
    setDrawings([])
    setUnigraphProjects([])
    setEquipment([])
    setEquipmentLoading(false)
    setError('')
    if (!nextProjectId) return
    setLoading('collections')
    try {
      setCollections(await getCollections(nextProjectId))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load collections.')
    } finally {
      setLoading('')
    }
  }

  async function selectCollection(nextCollectionId: string) {
    resetIsolationRun()
    setCollectionId(nextCollectionId)
    setDrawingId('')
    setUnigraphProjectId('')
    setEquipmentId('')
    setEquipmentBBox([])
    setDrawings([])
    setUnigraphProjects([])
    setEquipment([])
    setEquipmentLoading(false)
    setError('')
    if (!projectId || !nextCollectionId) return
    setLoading('unigraph')
    try {
      const [nextDrawings, nextUniGraphProjects] = await Promise.all([
        getDrawings(projectId, nextCollectionId),
        getUniGraphProjects(projectId, nextCollectionId),
      ])
      setDrawings(nextDrawings)
      setUnigraphProjects(nextUniGraphProjects)
      if (nextUniGraphProjects.length === 1) {
        const graphId = nextUniGraphProjects[0].id
        setUnigraphProjectId(graphId)
        await loadEquipmentForGraph(nextCollectionId, graphId)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load the collection planning context.')
    } finally {
      setLoading('')
    }
  }

  async function loadEquipmentForGraph(nextCollectionId: string, nextUniGraphProjectId: string) {
    if (!projectId || !nextCollectionId || !nextUniGraphProjectId) return
    setEquipmentLoading(true)
    try {
      const collectionName = collections.find((item) => item.id === nextCollectionId)?.name ?? ''
      setEquipment(await getEquipment(projectId, nextCollectionId, nextUniGraphProjectId, collectionName))
    } catch (reason) {
      setEquipment([])
      throw reason
    } finally {
      setEquipmentLoading(false)
    }
  }

  async function selectUniGraph(nextUniGraphProjectId: string) {
    resetIsolationRun()
    setUnigraphProjectId(nextUniGraphProjectId)
    setDrawingId('')
    setHiltGraph(null)
    setHiltSymbols([])
    setEquipmentId('')
    setEquipment([])
    setError('')
    if (!nextUniGraphProjectId) return
    try {
      await loadEquipmentForGraph(collectionId, nextUniGraphProjectId)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load equipment from UniGraph.')
    }
  }

  function resetIsolationRun() {
    setIsolationRun(null)
    setCompletedRunTools([])
    setIsolationResult(null)
    setIsolationError('')
    setIsolationSubmitting(false)
    setSelectedIsolationPointId(null)
    setSelectedDownstreamImpactId(null)
    setSelectedAssuranceReasonId(null)
    setViewMode('drawing')
    setMapLayers({ ...DEFAULT_ISOLATION_MAP_LAYERS })
    setSelectedSavedPlan(null)
    setPlanSaving(false)
    setPlanSaveError('')
  }

  function clearEquipmentSelection() {
    resetIsolationRun()
    setEquipmentId('')
    setEquipmentBBox([])
    setBBoxLoading(false)
    setDrawingSelection(null)
    setIntrusiveWork(true)
    setHighRiskService(true)
    setScopeNote('')
  }

  function selectEquipment(nextEquipmentId: string) {
    resetIsolationRun()
    setDrawingSelection(null)
    setEquipmentId(nextEquipmentId)
    setIntrusiveWork(true)
    setHighRiskService(true)
    setScopeNote('')
    const nextEquipment = equipment.find((item) => item.id === nextEquipmentId)
    if (!nextEquipment) return
    if (!nextEquipment.job_id) {
      setDrawingId('')
      setHiltGraph(null)
      setHiltSymbols([])
      setError(`No exact source P&ID is recorded for ${nextEquipment.tag || nextEquipment.name}.`)
      return
    }
    const sourceDrawing = drawings.find((item) => item.id === nextEquipment.job_id)
    if (!sourceDrawing) {
      setDrawingId('')
      setHiltGraph(null)
      setHiltSymbols([])
      setError(`The source P&ID for ${nextEquipment.tag || nextEquipment.name} is not available in this collection.`)
      return
    }
    setError('')
    setDrawingId(sourceDrawing.id)
  }

  async function startIsolationRun() {
    if (!selectedEquipment || !selectedProject || !selectedCollection || !selectedDrawing || !selectedUniGraph) return
    resetIsolationRun()
    setIsolationError('')
    setIsolationSubmitting(true)
    try {
      const accepted = await createIsolationRun({
        equipmentTag: selectedEquipment.tag || selectedEquipment.name,
        equipmentHiltEntityId: selectedEquipment.node_id,
        equipmentEntityClass: selectedEquipment.entity_class,
        jobName: selectedDrawing.name,
        jobId: selectedDrawing.id,
        cnvrtProjectId: selectedProject.id,
        collectionId: selectedCollection.id,
        collectionName: selectedCollection.name,
        unigraphProjectId: selectedUniGraph.id,
        intrusiveWork,
        highRiskService,
      })
      setIsolationRun({
        run_id: accepted.run_id,
        status: accepted.status,
        equipment_tag: selectedEquipment.tag || selectedEquipment.name,
        runner: 'agentic',
        created_at: Date.now() / 1000,
      })
    } catch (reason) {
      setIsolationError(reason instanceof Error ? reason.message : 'Unable to start the isolation run.')
      setIsolationRun({
        run_id: '',
        status: 'failed',
        equipment_tag: selectedEquipment.tag || selectedEquipment.name,
        runner: 'agentic',
        created_at: Date.now() / 1000,
      })
    } finally {
      setIsolationSubmitting(false)
    }
  }

  async function restorePersistedRun(run: IsolationRunStatus, savedPlan: SavedIsolationPlan | null = null) {
    if (run.status !== 'succeeded') return
    const context = run.request
    if (!context?.cnvrt_project_id || !context.collection_id || !context.job_id || !context.unigraph_project_id) {
      const message = 'The linked run does not contain enough saved planning context to reopen its drawing. Its result remains available.'
      if (savedPlan) setSavedPlansError(message)
      else setPastRunsError(message)
      setIsolationResult(null)
      setIsolationError('')
      setSelectedIsolationPointId(null)
      setSelectedDownstreamImpactId(null)
      setSelectedAssuranceReasonId(null)
      setIsolationRun(run)
      setSelectedSavedPlan(savedPlan)
      return
    }
    setPastRunsLoading(true)
    setPastRunsError('')
    setEquipmentLoading(true)
    setDrawingLoading(true)
    const selectedAssetId = String(context.selected_asset?.hilt_entity_id ?? '').trim()
    const collectionName = String(context.collection_name ?? '')
    const graphBundlePromise = getHiltGraph(context.job_id).then(async (graph) => {
      try {
        const symbols = await getHiltSymbols(getSymbolProjectId(graph, context.cnvrt_project_id!))
        return { graph, symbols, error: '' }
      } catch (reason) {
        return {
          graph,
          symbols: [] as HiltSymbol[],
          error: reason instanceof Error ? reason.message : 'The drawing loaded, but its symbol library did not.',
        }
      }
    }).catch((reason: unknown) => ({
      graph: null as HiltGraphInput | null,
      symbols: [] as HiltSymbol[],
      error: reason instanceof Error ? reason.message : 'Unable to load the HILT drawing.',
    }))
    try {
      const [nextCollections, nextDrawings, nextUniGraphProjects, nextEquipment, graphBundle, result, bbox] = await Promise.all([
        getCollections(context.cnvrt_project_id),
        getDrawings(context.cnvrt_project_id, context.collection_id),
        getUniGraphProjects(context.cnvrt_project_id, context.collection_id),
        getEquipment(context.cnvrt_project_id, context.collection_id, context.unigraph_project_id, collectionName),
        graphBundlePromise,
        getIsolationResult(run.run_id),
        selectedAssetId ? getEquipmentBBox(context.job_id, selectedAssetId).catch(() => []) : Promise.resolve([]),
      ])
      const wantedTag = run.equipment_tag.trim().toLowerCase()
      const nextSelectedEquipment = nextEquipment.find((item) => item.node_id === selectedAssetId)
        ?? nextEquipment.find((item) => [item.tag, item.name].some((value) => value.trim().toLowerCase() === wantedTag))
      preloadedDrawingKey.current = projectId !== context.cnvrt_project_id || drawingId !== context.job_id
        ? `${context.cnvrt_project_id}:${context.job_id}`
        : ''
      preloadedBBoxKey.current = nextSelectedEquipment && selectedAssetId ? `${context.job_id}:${nextSelectedEquipment.node_id}` : ''
      setCollections(nextCollections)
      setDrawings(nextDrawings)
      setUnigraphProjects(nextUniGraphProjects)
      setEquipment(nextEquipment)
      setHiltGraph(graphBundle.graph)
      setHiltSymbols(graphBundle.symbols)
      setDrawingError(graphBundle.error)
      setEquipmentBBox(bbox)
      setProjectId(context.cnvrt_project_id)
      setCollectionId(context.collection_id)
      setDrawingId(context.job_id)
      setUnigraphProjectId(context.unigraph_project_id)
      setEquipmentId(nextSelectedEquipment?.id ?? '')
      setPendingHistoricalEquipmentTag('')
      setIntrusiveWork(context.work_scope?.intrusive_work ?? true)
      setHighRiskService(context.work_scope?.high_risk_service ?? true)
      setDrawingSelection(null)
      setIsolationResult(result)
      setIsolationError(nextSelectedEquipment ? '' : `The saved equipment “${run.equipment_tag}” is not present in the restored UniGraph.`)
      setSelectedIsolationPointId(null)
      setSelectedDownstreamImpactId(null)
      setSelectedAssuranceReasonId(null)
      setIsolationRun(run)
      setSelectedSavedPlan(savedPlan)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'Unable to restore the historical run context.'
      if (savedPlan) setSavedPlansError(message)
      else setPastRunsError(message)
      throw reason
    } finally {
      setEquipmentLoading(false)
      setDrawingLoading(false)
      setBBoxLoading(false)
      setPastRunsLoading(false)
    }
  }

  async function openPastRun(run: IsolationRunStatus) {
    if (historicalNavigationLock.current || runInProgress || Boolean(loading) || equipmentLoading || drawingLoading) return
    const waitForContext = Boolean(run.request?.cnvrt_project_id && run.request.collection_id && run.request.job_id && run.request.unigraph_project_id)
    historicalNavigationLock.current = true
    setHistoricalNavigation({ kind: 'run', label: `${run.equipment_tag} isolation result`, runId: run.run_id, waitForContext })
    try {
      setSelectedSavedPlan(null)
      await restorePersistedRun(run)
    } catch {
      historicalNavigationLock.current = false
      setHistoricalNavigation(null)
    }
  }

  async function openSavedPlan(plan: SavedIsolationPlan) {
    if (historicalNavigationLock.current || runInProgress || Boolean(loading) || equipmentLoading || drawingLoading) return
    const sourceRunId = plan.latest_version.source_run.run_id
    historicalNavigationLock.current = true
    setHistoricalNavigation({ kind: 'plan', label: `${plan.plan_number} · v${plan.latest_version.version_no}`, runId: sourceRunId, waitForContext: true })
    setSavedPlansLoading(true)
    setSavedPlansError('')
    try {
      const [detail, run] = await Promise.all([
        getIsolationPlan(plan.plan_id),
        getIsolationRun(sourceRunId),
      ])
      const waitForContext = Boolean(run.request?.cnvrt_project_id && run.request.collection_id && run.request.job_id && run.request.unigraph_project_id)
      setHistoricalNavigation({ kind: 'plan', label: `${plan.plan_number} · v${plan.latest_version.version_no}`, runId: run.run_id, waitForContext })
      await restorePersistedRun(run, detail)
    } catch (reason) {
      setSavedPlansError(reason instanceof Error ? reason.message : 'Unable to open the saved plan.')
      historicalNavigationLock.current = false
      setHistoricalNavigation(null)
    } finally {
      setSavedPlansLoading(false)
    }
  }

  async function saveCurrentRunAsPlan(areaCode?: string) {
    if (!isolationRun?.run_id || isolationRun.status !== 'succeeded') return
    setPlanSaving(true)
    setPlanSaveError('')
    try {
      const plan = await createIsolationPlanFromRun(isolationRun.run_id, areaCode)
      setSelectedSavedPlan(plan)
      setSavedPlans((current) => [plan, ...current.filter((item) => item.plan_id !== plan.plan_id)].slice(0, 20))
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'Unable to save the draft plan.'
      setPlanSaveError(message)
      throw reason
    } finally {
      setPlanSaving(false)
    }
  }

  function selectIsolationPoint(point: IsolationPoint) {
    const selectionId = point.selection_id
    if (!selectionId) return
    setDrawingSelection(null)
    setViewMode('isolation')
    setMapLayers((current) => ({ ...current, points: true }))
    setSelectedDownstreamImpactId(null)
    setSelectedAssuranceReasonId(null)
    setSelectedIsolationPointId(selectionId)
  }

  function selectDownstreamImpact(warning: DownstreamImpactWarning) {
    const impactId = String(warning.affected_id || '').trim()
    if (!impactId) return
    setDrawingSelection(null)
    setViewMode('isolation')
    setMapLayers((current) => ({ ...current, downstream: true }))
    setSelectedIsolationPointId(null)
    setSelectedAssuranceReasonId(null)
    setSelectedDownstreamImpactId(impactId)
  }

  function selectAssuranceReason(reason: AssuranceReason) {
    if (!reason.reason_id) return
    setDrawingSelection(null)
    setViewMode('isolation')
    setMapLayers((current) => ({ ...current, blockers: true }))
    setSelectedIsolationPointId(null)
    setSelectedDownstreamImpactId(null)
    setSelectedAssuranceReasonId(reason.reason_id)
  }

  function changeMapLayer(layer: IsolationMapLayer, visible: boolean) {
    setMapLayers((current) => ({ ...current, [layer]: visible }))
  }

  function selectDrawingEntity(nextSelection: HiltSelection | null) {
    const resultPoint = nextSelection && (
      isolationPoints.find((point) => point.selection_id === selectedIsolationPointId && (point.drawing_entity_id || point.uuid) === nextSelection.id)
      ?? isolationPoints.find((point) => (point.drawing_entity_id || point.uuid) === nextSelection.id)
    )
    if (resultPoint) {
      selectIsolationPoint(resultPoint)
      setDrawingSelection(nextSelection)
      return
    }
    const resultImpact = nextSelection && downstreamImpacts.find((impact) => impact.affected_id === nextSelection.id)
    if (resultImpact) {
      selectDownstreamImpact(resultImpact)
      setDrawingSelection(nextSelection)
      return
    }
    const resultReason = nextSelection && assuranceReasons.find((reason) =>
      reason.terminal?.entity_id === nextSelection.id || reason.path_node_ids?.includes(nextSelection.id),
    )
    if (resultReason) {
      selectAssuranceReason(resultReason)
      setDrawingSelection(nextSelection)
      return
    }
    if (isolationRun) {
      setDrawingSelection(nextSelection)
      return
    }
    if (!nextSelection || nextSelection.kind !== 'node') {
      if (equipmentId) clearEquipmentSelection()
      setDrawingSelection(nextSelection)
      return
    }
    if (String(nextSelection.payload.entity_type ?? '').toLowerCase() !== 'equipment') {
      if (equipmentId) clearEquipmentSelection()
      setDrawingSelection(nextSelection)
      return
    }

    const identifiers = new Set(
      [nextSelection.id, nextSelection.payload.id, nextSelection.payload.source_id]
        .filter((value) => value !== null && value !== undefined && value !== '')
        .map(String),
    )
    const drawingEquipment = equipment.filter((item) => item.job_id === drawingId)
    let match = drawingEquipment.find((item) => identifiers.has(item.node_id) || identifiers.has(item.id))

    if (!match) {
      const tagAttribute = (nextSelection.payload.attributes ?? []).find((attribute) =>
        ['tag', 'tag number', 'equipment name'].includes(String(attribute.name ?? '').trim().toLowerCase()),
      )
      const selectedTag = String(tagAttribute?.value ?? '').trim().toLowerCase()
      if (selectedTag) {
        match = drawingEquipment.find((item) =>
          [item.tag, item.name].some((value) => value.trim().toLowerCase() === selectedTag),
        )
      }
    }

    if (match) {
      setDrawingSelection(null)
      if (match.id !== equipmentId) selectEquipment(match.id)
      return
    }
    if (equipmentId) clearEquipmentSelection()
    setDrawingSelection(nextSelection)
  }

  return (
    <div aria-busy={Boolean(historicalNavigation || isolationSubmitting || runInProgress || contextLoadingStage)} className="h-screen overflow-hidden bg-[#f7f8fa] text-slate-950">
      {!historicalNavigation && !isolationSubmitting && !runInProgress && contextLoadingStage && <ContextLoadingOverlay stage={contextLoadingStage} />}
      {!historicalNavigation && (isolationSubmitting || runInProgress) && <IsolationRunOverlay completedTools={completedRunTools} run={isolationRun} submitting={isolationSubmitting} />}
      {historicalNavigation && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/30 backdrop-blur-[2px]" role="status">
        <div className="w-80 border border-slate-300 bg-white p-5 shadow-2xl">
          <div className="flex items-center gap-3"><span aria-hidden="true" className="size-5 shrink-0 animate-spin rounded-full border-2 border-blue-200 border-t-blue-700" /><div><p className="font-mono text-[10px] uppercase tracking-[0.12em] text-blue-700">Opening saved {historicalNavigation.kind}</p><p className="mt-1 truncate text-sm font-medium text-slate-900">{historicalNavigation.label}</p></div></div>
          <p className="mt-3 text-xs leading-5 text-slate-600">Restoring its project, drawing, UniGraph, equipment, and immutable result. Other navigation is temporarily unavailable.</p>
        </div>
      </div>}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-4"><img alt="Plant360.ai" className="h-5 w-auto shrink-0" src={p360Logo} /><span className="hidden h-5 w-px bg-slate-700 sm:block" /><span className="truncate font-mono text-xs text-slate-300">ISOLATION PLANNING</span></div>
        <div className="flex items-center gap-3"><span className="hidden max-w-52 truncate text-xs text-slate-300 sm:inline">{user?.profile?.email}</span><button className="font-mono text-[10px] font-semibold tracking-wide text-slate-300 hover:text-white" onClick={logout} type="button">LOGOUT</button></div>
      </header>
      <ContextBreadcrumbs items={contextBreadcrumbItems} />
      <main className="grid h-[calc(100vh-6.5rem)] min-h-0 grid-cols-1 overflow-hidden xl:grid-cols-[20rem_minmax(0,1fr)_26rem]">
        <aside className="overflow-y-auto border-b border-slate-300 bg-slate-50 xl:border-b-0 xl:border-r">
          {displayedIsolationPlan && viewMode === 'isolation' ? <IsolationMapSidebar
            assuranceStatus={displayedIsolationPlan.assurance_status}
            impacts={downstreamImpacts}
            layers={mapLayers}
            onImpactSelect={selectDownstreamImpact}
            onLayerChange={changeMapLayer}
            onOpenPlan={(plan) => { void openSavedPlan(plan) }}
            onOpenRun={(run) => { void openPastRun(run) }}
            onPointSelect={selectIsolationPoint}
            onReasonSelect={selectAssuranceReason}
            pastRuns={pastRuns}
            points={isolationPoints}
            reasons={assuranceReasons}
            savedPlans={savedPlans}
            selectedImpactId={selectedDownstreamImpactId}
            selectedPointId={selectedIsolationPointId}
            selectedReasonId={selectedAssuranceReasonId}
          /> : <PlanningSidebar
            collectionLabel={selectedCollection?.name ?? ''}
            equipmentLabel={selectedEquipment ? selectedEquipment.tag || selectedEquipment.name : ''}
            graphLabel={selectedUniGraph?.name ?? ''}
            onOpenPlan={(plan) => { void openSavedPlan(plan) }}
            onOpenRun={(run) => { void openPastRun(run) }}
            onRetryContext={retryPlanningContext}
            pastRuns={pastRuns}
            contextError={error}
            plansError={savedPlansError}
            plansLoading={savedPlansLoading}
            projectLabel={selectedProject?.name ?? ''}
            runsError={pastRunsError}
            runsLoading={pastRunsLoading}
            historyDisabled={historyDisabled}
            historyDisabledReason={historyDisabledReason}
            savedPlans={savedPlans}
          />}
        </aside>
        <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border-b border-slate-300 bg-slate-200 xl:border-b-0">
          <div className="border-b border-slate-300 bg-white px-5 py-3"><p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">DRAWING WORKSPACE</p></div>
          <div className="min-h-0 flex-1">
            {ready && drawingId ? <Suspense fallback={<div className="h-full bg-white p-8"><Skeleton className="h-5 w-48" /><Skeleton className="mt-8 h-full w-full" /></div>}><Workspace assuranceReasons={assuranceReasons} downstreamImpacts={downstreamImpacts} drawingError={drawingError} drawingLoading={drawingLoading} drawingName={selectedDrawing?.name ?? ''} drawingSelection={drawingSelection} graph={hiltGraph} graphName={selectedUniGraph?.name ?? ''} isolationPoints={isolationPoints} mapLayers={mapLayers} onDrawingSelectionChange={selectDrawingEntity} onViewModeChange={setViewMode} selectedAssuranceReason={selectedAssuranceReason} selectedDownstreamImpactId={selectedDownstreamImpactId} selectedEntityId={selectedEquipment?.node_id ?? null} selectedIsolationPointId={selectedIsolationPointId} symbols={hiltSymbols} viewMode={viewMode} /></Suspense>
              : <div className="flex h-full items-center justify-center bg-white p-8 text-center"><div><h2 className="text-lg font-medium">{ready ? 'Select equipment' : 'Complete context selection'}</h2><p className="mt-2 max-w-sm text-sm leading-5 text-slate-600">{ready ? 'Choose equipment from the selected UniGraph. Its source P&ID will open automatically.' : 'Select a project, collection, and UniGraph before choosing equipment.'}</p></div></div>}
          </div>
        </section>
        <aside className="flex min-h-0 flex-col overflow-hidden bg-white xl:border-l xl:border-slate-300">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="border-b border-slate-300 p-5">
              <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">REVIEW STATUS</p>
              <div className="mt-3 flex items-start justify-between gap-3">
                <h2 className="text-xl font-medium">{selectedEquipment ? selectedEquipment.tag || selectedEquipment.name : ready ? 'Select equipment' : 'Context required'}</h2>
                {selectedEquipment && <button className="shrink-0 border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100" onClick={clearEquipmentSelection} type="button">View drawing only</button>}
              </div>
              {selectedEquipment && <p className="mt-1 text-sm text-slate-600">{selectedEquipment.entity_class.replaceAll('_', ' ')}</p>}
            </div>

            {isolationRun ? runInProgress && !displayedIsolationPlan ? null : displayedIsolationPlan && viewMode === 'drawing' ? <DrawingModeSummary
              onNewRun={resetIsolationRun}
              onOpenMap={() => setViewMode('isolation')}
              plan={displayedIsolationPlan}
            /> : <IsolationPlanPanel
              error={isolationError}
              onImpactSelect={selectDownstreamImpact}
              onPointSelect={selectIsolationPoint}
              onReasonSelect={selectAssuranceReason}
              onReset={resetIsolationRun}
              onSavePlan={saveCurrentRunAsPlan}
              plan={displayedIsolationPlan}
              planSaveError={planSaveError}
              planSaving={planSaving}
              run={isolationRun}
              savedPlan={selectedSavedPlan}
              selectedImpactId={selectedDownstreamImpactId}
              selectedPointId={selectedIsolationPointId}
              selectedReasonId={selectedAssuranceReasonId}
            /> : <div className="p-5 text-sm leading-6 text-slate-600">
              {selectedEquipment ? <>
                <dl className="grid grid-cols-2 gap-px bg-slate-200">
                  <div className="bg-slate-50 p-3"><dt className="font-mono text-[10px] text-slate-500">DRAWING</dt><dd className="mt-1 break-words text-slate-800">{selectedDrawing?.name}</dd><dd className="font-mono text-xs text-slate-500">job {drawingId}</dd></div>
                  <div className="bg-slate-50 p-3"><dt className="font-mono text-[10px] text-slate-500">UNIGRAPH</dt><dd className="mt-1 break-words text-slate-800">{selectedUniGraph?.name}</dd><dd className="font-mono text-xs text-slate-500">project {unigraphProjectId}</dd></div>
                  <div className="col-span-2 bg-slate-50 p-3"><dt className="font-mono text-[10px] text-slate-500">DRAWING LOCATION</dt><dd className="mt-1 text-slate-800">{bboxLoading ? 'Resolving bbox...' : equipmentBBox.length === 4 ? 'Located on selected drawing' : 'Not located on selected drawing'}</dd></div>
                </dl>
                <fieldset className="mt-6 border-t border-slate-200 pt-5">
                  <legend className="font-mono text-[10px] tracking-[0.12em] text-slate-500">WORK SCOPE</legend>
                  <label className="mt-3 flex cursor-pointer items-start gap-3"><input checked={intrusiveWork} className="mt-1 size-4 accent-blue-700" onChange={(event) => setIntrusiveWork(event.target.checked)} type="checkbox" /><span><span className="block text-slate-800">Intrusive work</span><span className="block text-xs leading-5 text-slate-500">Requires opening or entering equipment.</span></span></label>
                  <label className="mt-3 flex cursor-pointer items-start gap-3"><input checked={highRiskService} className="mt-1 size-4 accent-blue-700" onChange={(event) => setHighRiskService(event.target.checked)} type="checkbox" /><span><span className="block text-slate-800">High-risk service</span><span className="block text-xs leading-5 text-slate-500">Apply the stricter isolation policy.</span></span></label>
                  <label className="mt-4 block text-xs font-medium text-slate-700" htmlFor="scope-note">Scope note<textarea className="mt-1.5 block min-h-20 w-full resize-y border border-slate-300 bg-white p-2 text-sm font-normal text-slate-800 outline-none focus:border-blue-700" id="scope-note" onChange={(event) => setScopeNote(event.target.value)} placeholder="Optional planning note (not yet submitted to the agent)" value={scopeNote} /></label>
                </fieldset>
              </> : ready ? 'Select equipment to review its source-drawing location and prepare work scope.' : 'Select the complete source context before equipment, plan, or drawing data is requested.'}
            </div>}
          </div>

          {!isolationRun && <div className="shrink-0 border-t border-slate-300 bg-white p-4 shadow-[0_-8px_20px_rgba(15,23,42,0.06)]">
            {isolationError && <p className="mb-3 border-l-2 border-red-500 bg-red-50 px-3 py-2 text-xs leading-5 text-red-900" role="alert">{isolationError}</p>}
            <button className="w-full bg-blue-700 px-4 py-3 font-mono text-xs font-semibold tracking-[0.08em] text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500" disabled={!selectedEquipment || isolationSubmitting || runInProgress} onClick={() => void startIsolationRun()} type="button">{isolationSubmitting ? 'SUBMITTING…' : 'ISOLATE'}</button>
            <p className="mt-2 text-center font-mono text-[9px] tracking-wide text-slate-500">ADVISORY PLAN · NO PLANT ACTION</p>
          </div>}
        </aside>
      </main>
    </div>
  )
}

export default App
