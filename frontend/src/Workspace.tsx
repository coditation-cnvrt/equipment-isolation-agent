import { useRef, useState } from 'react'

type WorkspaceProps = {
  drawingName: string
  graphName: string
  imageUrl: string
}

const MIN_ZOOM = 0.75
const MAX_ZOOM = 4
const DEFAULT_ZOOM = 1.3

function Workspace({ drawingName, graphName, imageUrl }: WorkspaceProps) {
  const [zoom, setZoom] = useState(DEFAULT_ZOOM)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const dragStart = useRef<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null)

  function resetView() {
    setZoom(DEFAULT_ZOOM)
    setOffset({ x: 0, y: 0 })
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col bg-white">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
        <div>
          <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">SELECTED DRAWING</p>
          <h2 className="mt-2 text-lg font-medium">{drawingName}</h2>
        </div>
        <span className="font-mono text-xs text-slate-500">UNIGRAPH {graphName}</span>
      </div>
      <div
        className="relative flex flex-1 cursor-grab items-center justify-center overflow-hidden bg-slate-100 active:cursor-grabbing"
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId)
          dragStart.current = { x: event.clientX, y: event.clientY, offsetX: offset.x, offsetY: offset.y }
        }}
        onPointerMove={(event) => {
          if (!dragStart.current) return
          setOffset({
            x: dragStart.current.offsetX + event.clientX - dragStart.current.x,
            y: dragStart.current.offsetY + event.clientY - dragStart.current.y,
          })
        }}
        onPointerUp={() => { dragStart.current = null }}
        onWheel={(event) => {
          event.preventDefault()
          setZoom((current) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current - event.deltaY * 0.0015)))
        }}
      >
        <img
          alt={drawingName}
          className="max-h-full max-w-full select-none object-contain"
          draggable={false}
          src={imageUrl}
          style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})` }}
        />
        <div className="absolute bottom-3 right-3 flex items-center gap-1 rounded-md border border-slate-300 bg-white/95 p-1 shadow-sm">
          <button aria-label="Zoom out" className="h-8 w-8 text-lg hover:bg-slate-100" onClick={() => setZoom((current) => Math.max(MIN_ZOOM, current - 0.2))} type="button">−</button>
          <button className="min-w-14 px-2 font-mono text-[11px] hover:bg-slate-100" onClick={resetView} type="button">{Math.round(zoom * 100)}%</button>
          <button aria-label="Zoom in" className="h-8 w-8 text-lg hover:bg-slate-100" onClick={() => setZoom((current) => Math.min(MAX_ZOOM, current + 0.2))} type="button">+</button>
        </div>
      </div>
    </div>
  )
}

export default Workspace
