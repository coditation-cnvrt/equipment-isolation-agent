import { useEffect, useMemo, useRef, useState } from 'react'
import {
  getHiltEntityId,
  HiltViewer,
  normalizeHiltGraph,
  type HiltGraphInput,
  type HiltHighlight,
  type HiltPointerContext,
  type HiltSelection,
  type HiltSymbol,
  type HiltViewerHandle,
} from '@coditation-cnvrt/p360-hitl-viewer'
import '@coditation-cnvrt/p360-hitl-viewer/styles.css'

import type { IsolationPoint } from './api'
import Skeleton from './Skeleton'

type WorkspaceProps = {
  drawingName: string
  graphName: string
  graph: HiltGraphInput | null
  symbols: HiltSymbol[]
  selectedEntityId: string | null
  drawingLoading: boolean
  drawingError: string
  drawingSelection: HiltSelection | null
  isolationPoints: IsolationPoint[]
  selectedIsolationPointId: string | null
  onDrawingSelectionChange: (selection: HiltSelection | null) => void
}

type ContextMenuState = {
  selection: HiltSelection
  pointer: HiltPointerContext
}

function Workspace({
  drawingName,
  graphName,
  graph,
  symbols,
  selectedEntityId,
  drawingLoading,
  drawingError,
  drawingSelection,
  isolationPoints,
  selectedIsolationPointId,
  onDrawingSelectionChange,
}: WorkspaceProps) {
  const viewerRef = useRef<HiltViewerHandle>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [missingSymbols, setMissingSymbols] = useState<string[]>([])
  const activeId = drawingSelection?.id ?? selectedEntityId
  const drawingNodeIds = useMemo(() => {
    if (!graph) return new Set<string>()
    return new Set(normalizeHiltGraph(graph).nodes.map(getHiltEntityId).filter(Boolean))
  }, [graph])
  const mappedPoints = useMemo(() => isolationPoints.map((point, index) => {
    const explicitId = String(point.drawing_entity_id || '').trim()
    const legacyExactId = explicitId ? '' : String(point.uuid || '').trim()
    const drawingEntityId = drawingNodeIds.has(explicitId)
      ? explicitId
      : drawingNodeIds.has(legacyExactId) ? legacyExactId : null
    return { point, index, drawingEntityId }
  }), [drawingNodeIds, isolationPoints])
  const highlights = useMemo(() => {
    const pointHighlights = new Map<string, HiltHighlight & { selected: boolean }>()
    for (const { point, index, drawingEntityId } of mappedPoints) {
      if (!drawingEntityId) continue
      const selected = Boolean(point.selection_id && point.selection_id === selectedIsolationPointId)
      const rejected = point.validation_state === 'rejected'
      const highlight = {
        entityId: drawingEntityId,
        color: rejected || point.validation_state === 'manual' || point.requires_manual_review ? '#b45309' : '#6d28d9',
        label: `${rejected ? 'C' : 'P'}-${String(index + 1).padStart(2, '0')}`,
        className: selected ? 'isolation-point-highlight--selected' : 'isolation-point-highlight--muted',
        selected,
      }
      const existing = pointHighlights.get(drawingEntityId)
      if (!existing || selected) pointHighlights.set(drawingEntityId, highlight)
    }
    const result = [...pointHighlights.values()]
      .sort((left, right) => Number(left.selected) - Number(right.selected))
      .map(({ selected: _selected, ...highlight }) => highlight)
    if (selectedEntityId) result.push({ entityId: selectedEntityId, color: '#0f62fe', label: 'SELECTED', badgeVariant: 'flag', className: 'equipment-target-highlight' })
    return result
  }, [mappedPoints, selectedEntityId, selectedIsolationPointId])
  const bboxHighlights = useMemo(() => mappedPoints
    .map(({ point, index, drawingEntityId }) => {
      if (drawingEntityId || !point.bbox || point.bbox.length !== 4) return null
      const selected = Boolean(point.selection_id && point.selection_id === selectedIsolationPointId)
      return {
        id: `${point.selection_id || point.uuid || 'candidate'}-${index}`,
        bbox: point.bbox as [number, number, number, number],
        color: point.validation_state === 'rejected' || point.validation_state === 'manual' || point.requires_manual_review ? '#b45309' : '#6d28d9',
        label: `${point.validation_state === 'rejected' ? 'C' : 'P'}-${String(index + 1).padStart(2, '0')}`,
        className: selected ? 'isolation-point-highlight--selected' : 'isolation-point-highlight--muted',
        selected,
      }
    })
    .filter((highlight): highlight is NonNullable<typeof highlight> => highlight !== null)
    .sort((left, right) => Number(left.selected) - Number(right.selected))
    .map(({ selected: _selected, ...highlight }) => highlight), [mappedPoints, selectedIsolationPointId])

  useEffect(() => {
    setContextMenu(null)
  }, [graph])

  useEffect(() => {
    if (!selectedIsolationPointId) return
    const mapped = mappedPoints.find(({ point }) => point.selection_id === selectedIsolationPointId)
    if (!mapped) return
    if (mapped.drawingEntityId && viewerRef.current?.panToEntity?.(mapped.drawingEntityId)) return
    if (!mapped.point.bbox || mapped.point.bbox.length !== 4) return
    viewerRef.current?.panToBBox(mapped.point.bbox as [number, number, number, number])
  }, [mappedPoints, selectedIsolationPointId])

  return (
    <div className="flex h-full min-h-0 w-full flex-col bg-white">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-3">
        <div className="min-w-0">
          <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">SELECTED HILT DRAWING</p>
          <h2 className="mt-1 truncate text-base font-medium">{drawingName}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden font-mono text-[10px] text-slate-500 2xl:inline">UNIGRAPH {graphName}</span>
          <button className="border border-slate-300 px-2.5 py-1.5 font-mono text-[10px] hover:bg-slate-100 disabled:opacity-40" disabled={!graph} onClick={() => viewerRef.current?.fitToContent()} type="button">FIT CONTENT</button>
          <button className="border border-slate-300 px-2.5 py-1.5 font-mono text-[10px] hover:bg-slate-100 disabled:opacity-40" disabled={!graph} onClick={() => viewerRef.current?.fitToDrawing()} type="button">FULL DRAWING</button>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-slate-100" onClick={() => setContextMenu(null)}>
        {drawingLoading && <div className="h-full bg-white p-6"><Skeleton className="h-full w-full" /></div>}
        {!drawingLoading && drawingError && <div className="flex h-full items-center justify-center p-8 text-center"><div><h3 className="font-medium text-red-900">HILT drawing unavailable</h3><p className="mt-2 max-w-md text-sm text-red-700">{drawingError}</p></div></div>}
        {!drawingLoading && !drawingError && graph && <HiltViewer
          ref={viewerRef}
          ariaLabel={`${drawingName} HILT drawing`}
          className="border-0"
          graph={graph}
          bboxHighlights={bboxHighlights}
          highlights={highlights}
          selectedId={activeId}
          symbols={symbols}
          onEntityContextMenu={(nextSelection, pointer) => {
            onDrawingSelectionChange(nextSelection)
            setContextMenu({ selection: nextSelection, pointer })
          }}
          onMissingSymbols={setMissingSymbols}
          onSelectionChange={(nextSelection) => {
            onDrawingSelectionChange(nextSelection)
            setContextMenu(null)
          }}
        />}
        {!drawingLoading && !drawingError && !graph && <div className="flex h-full items-center justify-center text-sm text-slate-600">No exported HILT graph is available.</div>}

        {missingSymbols.length > 0 && graph && <div className="pointer-events-none absolute bottom-3 left-3 border border-amber-300 bg-amber-50/95 px-3 py-2 font-mono text-[10px] text-amber-900 shadow-sm">{missingSymbols.length} symbol {missingSymbols.length === 1 ? 'fallback' : 'fallbacks'}</div>}

        {contextMenu && <div
          className="fixed z-50 min-w-56 border border-slate-300 bg-white p-3 text-xs shadow-xl"
          onClick={(event) => event.stopPropagation()}
          style={{ left: contextMenu.pointer.clientX, top: contextMenu.pointer.clientY }}
        >
          <p className="font-mono text-[10px] tracking-wide text-slate-500">{contextMenu.selection.kind.toUpperCase()}</p>
          <p className="mt-1 max-w-72 break-all font-mono text-slate-900">{contextMenu.selection.id}</p>
          <p className="mt-2 capitalize text-slate-600">{String(contextMenu.selection.payload.entity_class ?? 'unclassified').replaceAll('_', ' ')}</p>
          <button className="mt-3 w-full border border-slate-300 px-2 py-1 text-left hover:bg-slate-100" onClick={() => setContextMenu(null)} type="button">Dismiss</button>
        </div>}
      </div>
      <div className="flex items-center justify-between border-t border-slate-200 px-4 py-2 font-mono text-[10px] text-slate-500">
        <span>WHEEL ZOOM · MIDDLE-DRAG PAN · CLICK SELECT · RIGHT-CLICK DETAILS</span>
        <span>{symbols.length} PROJECT SYMBOLS</span>
      </div>
    </div>
  )
}

export default Workspace
