import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'

import {
  createIsolationRun,
  getCollections,
  getDrawings,
  getEquipmentBBox,
  getHiltGraph,
  getHiltSymbols,
  getIsolationResult,
  getIsolationRun,
  getIsolationRuns,
  getProjects,
  getUniGraphProjects,
  type Collection,
  type Drawing,
  type Equipment,
  type IsolationPoint,
  type IsolationResult,
  type IsolationRunStatus,
  type Project,
  type UniGraphProject,
} from './api'
import { getHiltEntityId, normalizeHiltGraph, type HiltGraphInput, type HiltSelection, type HiltSymbol } from '@coditation-cnvrt/p360-hitl-viewer'
import DrawingSelectionInspector from './DrawingSelectionInspector'
import IsolationPlanPanel from './IsolationPlanPanel'
import Skeleton from './Skeleton'
import SearchableSelect from './SearchableSelect'

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
  const [pastRuns, setPastRuns] = useState<IsolationRunStatus[]>([])
  const [pastRunsLoading, setPastRunsLoading] = useState(false)
  const [pastRunsError, setPastRunsError] = useState('')
  const [pendingHistoricalEquipmentTag, setPendingHistoricalEquipmentTag] = useState('')
  const [loading, setLoading] = useState('projects')
  const [error, setError] = useState('')
  const didLoadProjects = useRef(false)

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
        visual_id: `candidate:${id}:${index}`,
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
  const runInProgress = isolationRun?.status === 'queued' || isolationRun?.status === 'running'
  const ready = Boolean(selectedProject && selectedCollection && selectedDrawing && selectedUniGraph)
  const projectOptions = projects.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const collectionOptions = collections.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const drawingOptions = drawings.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const unigraphOptions = unigraphProjects.map((item) => ({ value: item.id, label: `${item.name} (${item.id})`, searchText: `${item.name} ${item.id}` }))
  const equipmentOptions = equipment
    .filter((item) => item.job_id === drawingId)
    .map((item) => ({ value: item.id, label: `${item.tag || item.name} (${item.entity_class})`, searchText: `${item.tag} ${item.name} ${item.entity_class}` }))

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
    if (!pendingHistoricalEquipmentTag || !equipment.length) return
    const wanted = pendingHistoricalEquipmentTag.trim().toLowerCase()
    const match = equipment.find((item) => [item.tag, item.name].some((value) => value.trim().toLowerCase() === wanted))
    if (!match) return
    setEquipmentId(match.id)
    setPendingHistoricalEquipmentTag('')
  }, [equipment, pendingHistoricalEquipmentTag])

  useEffect(() => {
    if (!isolationRun || !['queued', 'running'].includes(isolationRun.status)) return
    let active = true
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const nextRun = await getIsolationRun(isolationRun.run_id)
          if (!active) return
          setIsolationRun(nextRun)
          if (nextRun.status === 'failed') {
            setIsolationError(nextRun.error?.message || 'The isolation run failed.')
          }
        } catch (reason) {
          if (!active) return
          setIsolationError(reason instanceof Error ? reason.message : 'Unable to read isolation run status.')
          setIsolationRun((current) => current ? { ...current, status: 'failed' } : current)
        }
      })()
    }, 1000)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [isolationRun])

  useEffect(() => {
    if (!isolationRun?.run_id || !['succeeded', 'failed'].includes(isolationRun.status)) return
    setPastRuns((current) => [isolationRun, ...current.filter((item) => item.run_id !== isolationRun.run_id)].slice(0, 20))
  }, [isolationRun])

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
    })
    return () => { active = false }
  }, [isolationResult, isolationRun?.run_id, isolationRun?.status])

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
      setUnigraphProjects(await getUniGraphProjects(projectId, collectionId))
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
  }

  function clearEquipmentSelection() {
    resetIsolationRun()
    setEquipmentId('')
    setEquipmentBBox([])
    setBBoxLoading(false)
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

  async function openPastRun(run: IsolationRunStatus) {
    if (run.status !== 'succeeded') return
    const context = run.request
    if (!context?.cnvrt_project_id || !context.collection_id || !context.job_id || !context.unigraph_project_id) {
      setPastRunsError('This historical run does not contain enough saved planning context to reopen its drawing.')
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
      setIsolationRun(run)
    } catch (reason) {
      setPastRunsError(reason instanceof Error ? reason.message : 'Unable to restore the historical run context.')
    } finally {
      setPastRunsLoading(false)
    }
  }

  function selectIsolationPoint(point: IsolationPoint) {
    const visualId = point.visual_id
    if (!visualId) return
    setDrawingSelection(null)
    setSelectedIsolationPointId(visualId)
  }

  function selectDrawingEntity(nextSelection: HiltSelection | null) {
    const resultPoint = nextSelection && isolationPoints.find((point) => point.visual_id === nextSelection.id)
    if (resultPoint) {
      selectIsolationPoint(resultPoint)
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
    <div className="h-screen overflow-hidden bg-[#f7f8fa] text-slate-950">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-300 bg-white px-4 sm:px-6">
        <div className="flex items-center gap-4"><span className="text-sm font-semibold">Plant360</span><span className="font-mono text-xs text-slate-600">ISOLATION PLANNING</span></div>
        <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 font-mono text-[10px] text-amber-900">ADVISORY ONLY</span>
      </header>
      <main className="grid h-[calc(100vh-3.5rem)] min-h-0 grid-cols-1 overflow-hidden xl:grid-cols-[20rem_minmax(0,1fr)_26rem]">
        <aside className="overflow-y-auto border-b border-slate-300 bg-slate-50 xl:border-b-0 xl:border-r">
          <div className="border-b border-slate-300 p-5"><p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">PLANNING CONTEXT</p><h1 className="mt-3 text-xl font-medium">Select a drawing</h1><p className="mt-2 text-sm leading-5 text-slate-600">A CNVRT project, collection, drawing, and UniGraph project are required.</p></div>
          <div className="space-y-4 p-5">
            {loading === 'projects' ? <div><span className="text-xs font-medium text-slate-700">CNVRT project</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect label="CNVRT project" onChange={(value) => void selectProject(value)} options={projectOptions} placeholder="Select project" searchPlaceholder="Filter by name or ID, e.g. 277" value={projectId} />}
            {projectId && (loading === 'collections' ? <div><span className="text-xs font-medium text-slate-700">Collection</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect label="Collection" onChange={(value) => void selectCollection(value)} options={collectionOptions} placeholder="Select collection" searchPlaceholder="Filter by collection name or ID" value={collectionId} />)}
            {collectionId && (loading === 'drawings' ? <div><span className="text-xs font-medium text-slate-700">Drawing</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect label="Drawing" onChange={(value) => void selectDrawing(value)} options={drawingOptions} placeholder="Select drawing" searchPlaceholder="Filter by drawing name or ID" value={drawingId} />)}
            {drawingId && (loading === 'unigraph' ? <div><span className="text-xs font-medium text-slate-700">UniGraph project</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect disabled={!unigraphOptions.length} emptyLabel="No graph project available" label="UniGraph project" onChange={(value) => void selectUniGraph(value)} options={unigraphOptions} placeholder="Select graph project" searchPlaceholder="Filter by graph name or ID" value={unigraphProjectId} />)}
            {unigraphProjectId && <SearchableSelect disabled={drawingLoading || !equipmentOptions.length} emptyLabel={drawingLoading ? 'Reading drawing equipment' : 'No drawing equipment available'} label="Equipment" onChange={selectEquipment} options={equipmentOptions} placeholder="Select equipment" searchPlaceholder="Filter by tag, name, or class" value={equipmentId} />}
            {error && <div className="border-l-2 border-red-500 bg-red-50 p-3 text-xs text-red-900" role="alert"><p>{error}</p>{!projects.length && <button className="mt-2 underline" onClick={() => void loadProjects()} type="button">Retry project load</button>}</div>}
          </div>
          <section className="border-t border-slate-300 p-5" aria-label="Previous isolation runs">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">{selectedEquipment ? 'MATCHING RUNS' : 'RECENT RUNS'}</h2>
              {pastRunsLoading && <span className="text-[10px] text-slate-500">Loading…</span>}
            </div>
            {pastRunsError && <p className="mt-2 border-l-2 border-red-500 bg-red-50 px-2 py-1 text-xs text-red-900">{pastRunsError}</p>}
            {!pastRunsLoading && !pastRunsError && !pastRuns.length && <p className="mt-2 text-xs text-slate-500">No persisted runs are available.</p>}
            {pastRuns.length > 0 && <ol className="mt-2 space-y-2">
              {pastRuns.map((run) => <li key={run.run_id}>
                <button className="w-full border border-slate-200 bg-white p-2 text-left hover:border-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50" disabled={run.status !== 'succeeded' || pastRunsLoading} onClick={() => void openPastRun(run)} type="button">
                  <span className="flex items-center justify-between gap-2"><span className="truncate text-xs font-medium text-slate-900">{run.equipment_tag}</span><span className="font-mono text-[9px] uppercase text-slate-600">{run.status}</span></span>
                  <span className="mt-1 flex items-center justify-between gap-2 text-[9px] text-slate-500"><span className="font-mono">{run.run_id.slice(0, 12)}</span><span>{new Date(run.created_at * 1000).toLocaleString()}</span></span>
                </button>
              </li>)}
            </ol>}
            <p className="mt-2 text-[10px] leading-4 text-slate-500">Opening a persisted result does not call Gemini.</p>
          </section>
        </aside>
        <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border-b border-slate-300 bg-slate-200 xl:border-b-0"><div className="border-b border-slate-300 bg-white px-5 py-3"><p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">DRAWING WORKSPACE</p></div><div className="min-h-0 flex-1">{ready ? <Suspense fallback={<div className="h-full bg-white p-8"><Skeleton className="h-5 w-48" /><Skeleton className="mt-8 h-full w-full" /></div>}><Workspace drawingError={drawingError} drawingLoading={drawingLoading} drawingName={selectedDrawing?.name ?? ''} drawingSelection={drawingSelection} graph={hiltGraph} graphName={selectedUniGraph?.name ?? ''} isolationPoints={isolationPoints} onDrawingSelectionChange={selectDrawingEntity} selectedEntityId={selectedEquipment?.node_id ?? null} selectedIsolationPointId={selectedIsolationPointId} symbols={hiltSymbols} /></Suspense> : <div className="flex h-full items-center justify-center bg-white p-8 text-center"><div><h2 className="text-lg font-medium">Complete context selection</h2><p className="mt-2 max-w-sm text-sm leading-5 text-slate-600">No CNVRT drawing content is loaded until all required selections are complete.</p></div></div>}</div></section>
        <aside className="flex min-h-0 flex-col overflow-hidden bg-white xl:border-l xl:border-slate-300">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="border-b border-slate-300 p-5">
              <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">REVIEW STATUS</p>
              <div className="mt-3 flex items-start justify-between gap-3">
                <h2 className="text-xl font-medium">{selectedEquipment ? selectedEquipment.tag || selectedEquipment.name : ready ? 'Select equipment' : 'Context required'}</h2>
                {selectedEquipment && !isolationRun && <button className="border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100" onClick={clearEquipmentSelection} type="button">Clear</button>}
              </div>
              {selectedEquipment && <p className="mt-1 text-sm text-slate-600">{selectedEquipment.entity_class.replaceAll('_', ' ')}</p>}
            </div>

            {drawingSelection && !isolationRun && <DrawingSelectionInspector onClear={() => setDrawingSelection(null)} selection={drawingSelection} />}

            {isolationRun ? <IsolationPlanPanel
              error={isolationError}
              onPointSelect={selectIsolationPoint}
              onReset={resetIsolationRun}
              plan={displayedIsolationPlan}
              run={isolationRun}
              selectedPointId={selectedIsolationPointId}
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
