import { useEffect, useMemo, useRef, useState } from 'react'
import {
  HiltViewer,
  type HiltGraphInput,
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
  const highlights = useMemo(
    () => selectedEntityId ? [{ entityId: selectedEntityId, color: '#2563eb', label: 'TARGET' }] : [],
    [selectedEntityId],
  )
  const bboxHighlights = useMemo(() => {
    const selectedIndex = isolationPoints.findIndex((point) => point.visual_id === selectedIsolationPointId)
    const point = selectedIndex >= 0 ? isolationPoints[selectedIndex] : null
    if (!point?.bbox || point.bbox.length !== 4) return []
    return [{
      id: point.visual_id || `candidate-${selectedIndex}`,
      bbox: point.bbox as [number, number, number, number],
      color: point.validation_state === 'rejected' || point.validation_state === 'manual' || point.requires_manual_review ? '#b45309' : '#6d28d9',
      label: `${point.validation_state === 'rejected' ? 'C' : 'P'}-${String(selectedIndex + 1).padStart(2, '0')}`,
    }]
  }, [isolationPoints, selectedIsolationPointId])

  useEffect(() => {
    setContextMenu(null)
  }, [graph])

  useEffect(() => {
    if (!selectedIsolationPointId) return
    const point = isolationPoints.find((item) => item.visual_id === selectedIsolationPointId)
    if (!point?.bbox || point.bbox.length !== 4) return
    viewerRef.current?.panToBBox(point.bbox as [number, number, number, number])
  }, [isolationPoints, selectedIsolationPointId])

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
