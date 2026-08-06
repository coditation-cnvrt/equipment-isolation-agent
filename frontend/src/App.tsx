import { lazy, Suspense, useEffect, useRef, useState } from 'react'

import {
  getCollections,
  getDrawings,
  getEquipmentBBox,
  getEquipment,
  getProjects,
  getUniGraphProjects,
  drawingImageUrl,
  type Collection,
  type Drawing,
  type Equipment,
  type Project,
  type UniGraphProject,
} from './api'
import Skeleton from './Skeleton'
import SearchableSelect from './SearchableSelect'

const Workspace = lazy(() => import('./Workspace'))

function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [drawings, setDrawings] = useState<Drawing[]>([])
  const [unigraphProjects, setUnigraphProjects] = useState<UniGraphProject[]>([])
  const [equipment, setEquipment] = useState<Equipment[]>([])
  const [projectId, setProjectId] = useState('')
  const [collectionId, setCollectionId] = useState('')
  const [drawingId, setDrawingId] = useState('')
  const [unigraphProjectId, setUnigraphProjectId] = useState('')
  const [equipmentId, setEquipmentId] = useState('')
  const [equipmentBBox, setEquipmentBBox] = useState<number[]>([])
  const [loading, setLoading] = useState('projects')
  const [error, setError] = useState('')
  const didLoadProjects = useRef(false)

  const selectedProject = projects.find((item) => item.id === projectId)
  const selectedCollection = collections.find((item) => item.id === collectionId)
  const selectedDrawing = drawings.find((item) => item.id === drawingId)
  const selectedUniGraph = unigraphProjects.find((item) => item.id === unigraphProjectId)
  const selectedEquipment = equipment.find((item) => item.id === equipmentId)
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
      return
    }
    let active = true
    void getEquipmentBBox(drawingId, selectedEquipment.node_id).then((bbox) => {
      if (active) setEquipmentBBox(bbox)
    })
    return () => { active = false }
  }, [drawingId, selectedEquipment])

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
    setProjectId(nextProjectId)
    setCollectionId('')
    setDrawingId('')
    setUnigraphProjectId('')
    setEquipmentId('')
    setEquipmentBBox([])
    setEquipment([])
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
    setCollectionId(nextCollectionId)
    setDrawingId('')
    setUnigraphProjectId('')
    setEquipmentId('')
    setEquipmentBBox([])
    setEquipment([])
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
    setDrawingId(nextDrawingId)
    setUnigraphProjectId('')
    setUnigraphProjects([])
    setEquipmentId('')
    setEquipment([])
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

  async function selectUniGraph(nextUniGraphProjectId: string) {
    setUnigraphProjectId(nextUniGraphProjectId)
    setEquipmentId('')
    setEquipment([])
    setError('')
    if (!projectId || !collectionId || !selectedCollection || !nextUniGraphProjectId) return
    setLoading('equipment')
    try {
      setEquipment(await getEquipment(projectId, collectionId, nextUniGraphProjectId, selectedCollection.name))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load equipment.')
    } finally {
      setLoading('')
    }
  }

  return (
    <div className="h-screen overflow-hidden bg-[#f7f8fa] text-slate-950">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-300 bg-white px-4 sm:px-6">
        <div className="flex items-center gap-4"><span className="text-sm font-semibold">Plant360</span><span className="font-mono text-xs text-slate-600">ISOLATION PLANNING</span></div>
        <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 font-mono text-[10px] text-amber-900">ADVISORY ONLY</span>
      </header>
      <main className="grid h-[calc(100vh-3.5rem)] min-h-0 grid-cols-1 overflow-hidden xl:grid-cols-[20rem_minmax(0,1fr)_20rem]">
        <aside className="overflow-y-auto border-b border-slate-300 bg-slate-50 xl:border-b-0 xl:border-r">
          <div className="border-b border-slate-300 p-5"><p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">PLANNING CONTEXT</p><h1 className="mt-3 text-xl font-medium">Select a drawing</h1><p className="mt-2 text-sm leading-5 text-slate-600">A CNVRT project, collection, drawing, and UniGraph project are required.</p></div>
          <div className="space-y-4 p-5">
            {loading === 'projects' ? <div><span className="text-xs font-medium text-slate-700">CNVRT project</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect label="CNVRT project" onChange={(value) => void selectProject(value)} options={projectOptions} placeholder="Select project" searchPlaceholder="Filter by name or ID, e.g. 277" value={projectId} />}
            {projectId && (loading === 'collections' ? <div><span className="text-xs font-medium text-slate-700">Collection</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect label="Collection" onChange={(value) => void selectCollection(value)} options={collectionOptions} placeholder="Select collection" searchPlaceholder="Filter by collection name or ID" value={collectionId} />)}
            {collectionId && (loading === 'drawings' ? <div><span className="text-xs font-medium text-slate-700">Drawing</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect label="Drawing" onChange={(value) => void selectDrawing(value)} options={drawingOptions} placeholder="Select drawing" searchPlaceholder="Filter by drawing name or ID" value={drawingId} />)}
            {drawingId && (loading === 'unigraph' ? <div><span className="text-xs font-medium text-slate-700">UniGraph project</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect disabled={!unigraphOptions.length} emptyLabel="No graph project available" label="UniGraph project" onChange={(value) => void selectUniGraph(value)} options={unigraphOptions} placeholder="Select graph project" searchPlaceholder="Filter by graph name or ID" value={unigraphProjectId} />)}
            {unigraphProjectId && (loading === 'equipment' ? <div><span className="text-xs font-medium text-slate-700">Equipment</span><Skeleton className="mt-1.5 h-10 w-full" /></div> : <SearchableSelect disabled={!equipmentOptions.length} emptyLabel="No equipment available" label="Equipment" onChange={setEquipmentId} options={equipmentOptions} placeholder="Select equipment" searchPlaceholder="Filter by tag, name, or class" value={equipmentId} />)}
            {error && <div className="border-l-2 border-red-500 bg-red-50 p-3 text-xs text-red-900" role="alert"><p>{error}</p>{!projects.length && <button className="mt-2 underline" onClick={() => void loadProjects()} type="button">Retry project load</button>}</div>}
          </div>
        </aside>
        <section className="flex min-h-0 min-w-0 flex-col overflow-hidden border-b border-slate-300 bg-slate-200 xl:border-b-0"><div className="border-b border-slate-300 bg-white px-5 py-3"><p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">DRAWING WORKSPACE</p></div><div className="min-h-0 flex-1">{ready ? <Suspense fallback={<div className="h-full bg-white p-8"><Skeleton className="h-5 w-48" /><Skeleton className="mt-8 h-full w-full" /></div>}><Workspace bbox={equipmentBBox} drawingName={selectedDrawing?.name ?? ''} graphName={selectedUniGraph?.name ?? ''} imageUrl={drawingImageUrl(projectId, collectionId, drawingId)} /></Suspense> : <div className="flex h-full items-center justify-center bg-white p-8 text-center"><div><h2 className="text-lg font-medium">Complete context selection</h2><p className="mt-2 max-w-sm text-sm leading-5 text-slate-600">No CNVRT drawing content is loaded until all required selections are complete.</p></div></div>}</div></section>
        <aside className="overflow-y-auto bg-white xl:border-l xl:border-slate-300"><div className="border-b border-slate-300 p-5"><p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">REVIEW STATUS</p><h2 className="mt-3 text-xl font-medium">{ready ? 'Context ready' : 'Context required'}</h2></div><div className="p-5 text-sm leading-6 text-slate-600">{ready ? <dl className="space-y-3"><div><dt className="font-mono text-[10px] text-slate-500">DRAWING</dt><dd>{selectedDrawing?.name}</dd></div><div><dt className="font-mono text-[10px] text-slate-500">UNIGRAPH</dt><dd>{selectedUniGraph?.name}</dd></div></dl> : 'Select the complete source context before equipment, plan, or drawing data is requested.'}</div></aside>
      </main>
    </div>
  )
}

export default App
