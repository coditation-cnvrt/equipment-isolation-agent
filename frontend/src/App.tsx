import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'

import {
  createIsolationPlanFromRun,
  createIsolationRun,
  getCollections,
  getDrawings,
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
import { getHiltEntityId, normalizeHiltGraph, type HiltGraphInput, type HiltSelection, type HiltSymbol } from '@coditation-cnvrt/p360-hitl-viewer'
import ContextBreadcrumbs from './ContextBreadcrumbs'
import DrawingModeSummary from './DrawingModeSummary'
import IsolationMapSidebar from './IsolationMapSidebar'
import IsolationPlanPanel from './IsolationPlanPanel'
import { DEFAULT_ISOLATION_MAP_LAYERS, type IsolationMapLayer, type IsolationViewMode } from './isolation-map'
import PlanningSidebar from './PlanningSidebar'
import Skeleton from './Skeleton'
import { useUser } from './auth-context'

const Workspace = lazy(() => import('./Workspace'))

function equipmentFromHiltGraph(graphInput: HiltGraphInput | null, jobId: string, jobName: string): Equipment[] {
  if (!graphInput) return []
  try {
    return normalizeHiltGraph(graphInput).nodes.flatMap((node) => {
      const payload = node.payload
      if (String(payload.entity_type ?? '').toLowerCase() !== 'equipment') return []
      const attributes = payload.attributes ?? []
      const attributeValue = (...names: string[]) => {
        const wanted = new Set(names.map((name) => name.toLowerCase()))
        const match = attributes.find((attribute) => wanted.has(String(attribute.name ?? '').trim().toLowerCase()))
        return String(match?.value ?? '').trim()
      }
      const nodeId = getHiltEntityId(node)
      const tag = attributeValue('tag', 'tag number', 'equipment name', 'system number')
      const name = attributeValue('description', 'equipment description') || tag || String(payload.name ?? nodeId)
      return [{
        id: nodeId,
        tag,
        name,
        entity_class: String(payload.entity_class ?? ''),
        node_id: nodeId,
        job_id: jobId,
        job_name: jobName,
      }]
    }).sort((left, right) => (left.tag || left.name).localeCompare(right.tag || right.name))
  } catch {
    return []
  }
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
  const [loading, setLoading] = useState('projects')
  const [error, setError] = useState('')
  const didLoadProjects = useRef(false)
  const historicalNavigationLock = useRef(false)

  const selectedProject = projects.find((item) => item.id === projectId)
  const selectedCollection = collections.find((item) => item.id === collectionId)
  const selectedDrawing = drawings.find((item) => item.id === drawingId)
  const selectedUniGraph = unigraphProjects.find((item) => item.id === unigraphProjectId)
  const equipment = useMemo(
    () => equipmentFromHiltGraph(hiltGraph, drawingId, selectedDrawing?.name ?? ''),
    [drawingId, hiltGraph, selectedDrawing?.name],
  )
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
  const assuranceReasons = displayedIsolationPlan?.isolation_validation?.assurance_explanation?.primary_reasons ?? []
  const selectedAssuranceReason = assuranceReasons.find((reason) => reason.reason_id === selectedAssuranceReasonId) ?? null
  const runInProgress = isolationRun?.status === 'queued' || isolationRun?.status === 'running'
  const ready = Boolean(selectedProject && selectedCollection && selectedDrawing && selectedUniGraph)
  const projectOptions = projects.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const collectionOptions = collections.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const drawingOptions = drawings.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const unigraphOptions = unigraphProjects.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const equipmentOptions = equipment
    .filter((item) => item.job_id === drawingId)
    .map((item) => ({ value: item.id, label: `${item.tag || item.name} (${item.entity_class})`, searchText: `${item.tag} ${item.name} ${item.entity_class}` }))
  const contextBreadcrumbItems = [
    { key: 'project', label: 'Project', value: projectId, placeholder: 'Choose project', options: projectOptions, onChange: (value: string) => { void selectProject(value) } },
    { key: 'collection', label: 'Collection', value: collectionId, placeholder: 'Choose collection', options: collectionOptions, disabled: !projectId, onChange: (value: string) => { void selectCollection(value) } },
    { key: 'drawing', label: 'Drawing', value: drawingId, placeholder: 'Choose drawing', options: drawingOptions, disabled: !collectionId, onChange: (value: string) => { void selectDrawing(value) } },
    { key: 'graph', label: 'UniGraph', value: unigraphProjectId, placeholder: 'Choose graph', options: unigraphOptions, disabled: !drawingId, onChange: selectUniGraph },
    { key: 'equipment', label: 'Equipment', value: equipmentId, placeholder: drawingLoading ? 'Loading equipment' : 'Choose equipment', options: equipmentOptions, disabled: !unigraphProjectId || drawingLoading, onChange: selectEquipment, onClear: clearEquipmentSelection },
  ]

  useEffect(() => {
    if (didLoadProjects.current) return
    didLoadProjects.current = true
    void loadProjects()
  }, [])

  useEffect(() => {
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
    if (!pendingHistoricalEquipmentTag || drawingLoading || !hiltGraph) return
    const wanted = pendingHistoricalEquipmentTag.trim().toLowerCase()
    const match = equipment.find((item) => [item.tag, item.name].some((value) => value.trim().toLowerCase() === wanted))
    if (match) setEquipmentId(match.id)
    else setIsolationError(`The saved equipment “${pendingHistoricalEquipmentTag}” is not present in the restored drawing.`)
    setPendingHistoricalEquipmentTag('')
  }, [drawingLoading, equipment, hiltGraph, pendingHistoricalEquipmentTag])

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
    setError('')
    if (!projectId || !nextCollectionId) return
    setLoading('drawings')
    try {
      setDrawings(await getDrawings(projectId, nextCollectionId))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load drawings.')
    } finally {
      setLoading('')
    }
  }

  async function selectDrawing(nextDrawingId: string) {
    resetIsolationRun()
    setDrawingId(nextDrawingId)
    setUnigraphProjectId('')
    setUnigraphProjects([])
    setEquipmentId('')
    setError('')
    if (!projectId || !collectionId || !nextDrawingId) return
    setLoading('unigraph')
    try {
      const nextUniGraphProjects = await getUniGraphProjects(projectId, collectionId)
      setUnigraphProjects(nextUniGraphProjects)
      if (nextUniGraphProjects.length === 1) setUnigraphProjectId(nextUniGraphProjects[0].id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load UniGraph projects.')
    } finally {
      setLoading('')
    }
  }

  function selectUniGraph(nextUniGraphProjectId: string) {
    resetIsolationRun()
    setUnigraphProjectId(nextUniGraphProjectId)
    setEquipmentId('')
    setError('')
  }

  function resetIsolationRun() {
    setIsolationRun(null)
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
    try {
      const [nextCollections, nextDrawings, nextUniGraphProjects] = await Promise.all([
        getCollections(context.cnvrt_project_id),
        getDrawings(context.cnvrt_project_id, context.collection_id),
        getUniGraphProjects(context.cnvrt_project_id, context.collection_id),
      ])
      setCollections(nextCollections)
      setDrawings(nextDrawings)
      setUnigraphProjects(nextUniGraphProjects)
      if (projectId !== context.cnvrt_project_id || drawingId !== context.job_id) {
        setHiltGraph(null)
        setHiltSymbols([])
        setDrawingLoading(true)
      }
      setProjectId(context.cnvrt_project_id)
      setCollectionId(context.collection_id)
      setDrawingId(context.job_id)
      setUnigraphProjectId(context.unigraph_project_id)
      setEquipmentId('')
      setPendingHistoricalEquipmentTag(run.equipment_tag)
      setIntrusiveWork(context.work_scope?.intrusive_work ?? true)
      setHighRiskService(context.work_scope?.high_risk_service ?? true)
      setDrawingSelection(null)
      setIsolationResult(null)
      setIsolationError('')
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
      setPastRunsLoading(false)
    }
  }

  async function openPastRun(run: IsolationRunStatus) {
    if (historicalNavigationLock.current || runInProgress || Boolean(loading) || drawingLoading) return
    const waitForContext = Boolean(run.request?.cnvrt_project_id && run.request.collection_id && run.request.job_id && run.request.unigraph_project_id)
    historicalNavigationLock.current = true
    setHistoricalNavigation({ kind: 'run', label: `${run.equipment_tag} · ${run.run_id.slice(0, 12)}`, runId: run.run_id, waitForContext })
    try {
      setSelectedSavedPlan(null)
      await restorePersistedRun(run)
    } catch {
      historicalNavigationLock.current = false
      setHistoricalNavigation(null)
    }
  }

  async function openSavedPlan(plan: SavedIsolationPlan) {
    if (historicalNavigationLock.current || runInProgress || Boolean(loading) || drawingLoading) return
    const sourceRunId = plan.latest_version.source_run.run_id
    historicalNavigationLock.current = true
    setHistoricalNavigation({ kind: 'plan', label: `${plan.plan_number} · v${plan.latest_version.version_no}`, runId: sourceRunId, waitForContext: true })
    setSavedPlansLoading(true)
    setSavedPlansError('')
    try {
      const detail = await getIsolationPlan(plan.plan_id)
      const run = await getIsolationRun(detail.latest_version.source_run.run_id)
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
    <div aria-busy={Boolean(historicalNavigation)} className="h-screen overflow-hidden bg-[#f7f8fa] text-slate-950">
      {historicalNavigation && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/20 backdrop-blur-[1px]" role="status">
        <div className="w-80 border border-slate-300 bg-white p-5 shadow-2xl">
          <div className="flex items-center gap-3"><span aria-hidden="true" className="size-5 shrink-0 animate-spin rounded-full border-2 border-blue-200 border-t-blue-700" /><div><p className="font-mono text-[10px] uppercase tracking-[0.12em] text-blue-700">Opening saved {historicalNavigation.kind}</p><p className="mt-1 truncate text-sm font-medium text-slate-900">{historicalNavigation.label}</p></div></div>
          <p className="mt-3 text-xs leading-5 text-slate-600">Restoring its project, drawing, UniGraph, equipment, and immutable result. Other navigation is temporarily unavailable.</p>
        </div>
      </div>}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-300 bg-white px-4 sm:px-6">
        <div className="flex items-center gap-4"><span className="text-sm font-semibold">Plant360</span><span className="font-mono text-xs text-slate-600">ISOLATION PLANNING</span></div>
        <div className="flex items-center gap-3"><span className="hidden max-w-52 truncate text-xs text-slate-600 sm:inline">{user?.profile?.email}</span><button className="font-mono text-[10px] font-semibold tracking-wide text-slate-600 hover:text-blue-700" onClick={logout} type="button">LOGOUT</button></div>
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
            drawingLabel={selectedDrawing?.name ?? ''}
            equipmentLabel={selectedEquipment ? selectedEquipment.tag || selectedEquipment.name : ''}
            graphLabel={selectedUniGraph?.name ?? ''}
            onOpenPlan={(plan) => { void openSavedPlan(plan) }}
            onOpenRun={(run) => { void openPastRun(run) }}
            pastRuns={pastRuns}
            plansError={savedPlansError || error}
            plansLoading={savedPlansLoading || loading === 'projects' || loading === 'collections' || loading === 'drawings' || loading === 'unigraph'}
            projectLabel={selectedProject?.name ?? ''}
            runsError={pastRunsError}
            runsLoading={pastRunsLoading}
            savedPlans={savedPlans}
          />}
        </aside>
        <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border-b border-slate-300 bg-slate-200 xl:border-b-0"><div className="border-b border-slate-300 bg-white px-5 py-3"><p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">DRAWING WORKSPACE</p></div><div className="min-h-0 flex-1">{ready ? <Suspense fallback={<div className="h-full bg-white p-8"><Skeleton className="h-5 w-48" /><Skeleton className="mt-8 h-full w-full" /></div>}><Workspace assuranceReasons={assuranceReasons} downstreamImpacts={downstreamImpacts} drawingError={drawingError} drawingLoading={drawingLoading} drawingName={selectedDrawing?.name ?? ''} drawingSelection={drawingSelection} graph={hiltGraph} graphName={selectedUniGraph?.name ?? ''} isolationPoints={isolationPoints} mapLayers={mapLayers} onDrawingSelectionChange={selectDrawingEntity} onViewModeChange={setViewMode} selectedAssuranceReason={selectedAssuranceReason} selectedDownstreamImpactId={selectedDownstreamImpactId} selectedEntityId={selectedEquipment?.node_id ?? null} selectedIsolationPointId={selectedIsolationPointId} symbols={hiltSymbols} viewMode={viewMode} /></Suspense> : <div className="flex h-full items-center justify-center bg-white p-8 text-center"><div><h2 className="text-lg font-medium">Complete context selection</h2><p className="mt-2 max-w-sm text-sm leading-5 text-slate-600">No CNVRT drawing content is loaded until all required selections are complete.</p></div></div>}</div></section>
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

            {isolationRun ? displayedIsolationPlan && viewMode === 'drawing' ? <DrawingModeSummary
              onNewRun={resetIsolationRun}
              onOpenMap={() => setViewMode('isolation')}
              plan={displayedIsolationPlan}
              runId={isolationRun.run_id}
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
