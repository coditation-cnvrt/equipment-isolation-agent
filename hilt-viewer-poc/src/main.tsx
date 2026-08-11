import { useMemo, useRef, useState, type PointerEvent, type WheelEvent } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

type Point = { x: number; y: number }
type Attribute = { name?: string; value?: unknown; data_type?: string }
type TextItem = { value?: string; point?: Point; rotation?: number; width?: number; height?: number; [key: string]: unknown }
type Payload = {
  id: string; entity_type?: string; entity_class?: string; rotation?: number; symbol_flip?: string
  bounding_box_location?: Point; bounding_box_width?: number; bounding_box_height?: number
  text?: TextItem[]
  attributes?: Attribute[]; piping_network_system?: { attributes?: Attribute[] }; piping_network_segment?: { attributes?: Attribute[] }
  contour?: unknown[]
}
type Node = { id: string; payload: Payload }
type Link = { id?: string; payload: { id?: string; entity_class?: string; entity_type?: string; graphical_lines?: Array<{ p1: Point; p2: Point; line_type?: string }>; text?: Payload['text']; arrow?: Array<{ bounding_box_location?: Point; rotation?: number }>; attributes?: Attribute[]; piping_network_system?: { attributes?: Attribute[] }; piping_network_segment?: { attributes?: Attribute[] } } }
type SelectedEntity = Node | Link
const isLink = (entity: SelectedEntity): entity is Link => 'graphical_lines' in entity.payload
const entityId = (entity: SelectedEntity) => entity.id ?? entity.payload.id ?? ''
type Graph = { imageSize: { width: number; height: number }; nodes: Node[]; links: Link[] }
type SymbolDefinition = { pid_entity_type: string; pid_entity_class: string; svg: string }
type ViewBox = { x: number; y: number; width: number; height: number }

const svgUrl = (svg: string) => `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
const LINE_VISUALS: Record<string, { color: string; width: number }> = {
  process_line: { color: 'mediumseagreen', width: 2 },
  main_process_line: { color: 'mediumseagreen', width: 4 },
  secondary_process_line: { color: 'mediumseagreen', width: 2 },
  signal_line: { color: 'teal', width: 2 },
  electrical_signal_line: { color: 'teal', width: 2 },
  hydraulic_signal_line: { color: 'teal', width: 2 },
  pneumatic_signal_line: { color: 'teal', width: 2 },
  data_signal_line: { color: 'teal', width: 2 },
  electromagnetic_sonic_signal_line: { color: 'teal', width: 2 },
  capillary_signal_line: { color: 'teal', width: 2 },
  companion_line: { color: 'dodgerblue', width: 2 },
  piping_to_instrument_line: { color: 'dodgerblue', width: 2 },
  drawing_line: { color: 'red', width: 2 },
  null_edge: { color: 'lightgrey', width: 2 },
  package_line: { color: 'orange', width: 2 },
  leader_line: { color: 'purple', width: 2 },
  unclassified_line: { color: 'black', width: 2 },
}
const lineVisual = (link: Link) => LINE_VISUALS[link.payload.entity_class ?? ''] ?? LINE_VISUALS[link.payload.entity_type ?? ''] ?? { color: 'black', width: 2 }
const attrs = (items: Attribute[] = []) => items.filter((item) => item.name).map((item) => <tr key={item.name}><th>{item.name}</th><td>{String(item.value ?? '')}</td></tr>)

function unwrap(raw: { hilt_graph?: Graph }): Graph {
  if (!raw.hilt_graph?.nodes || !raw.hilt_graph?.links) throw new Error('Fixture is not an exported L2 HILT graph.')
  return raw.hilt_graph
}

function HiltSvg({ graph, symbols, selected, onSelect }: { graph: Graph; symbols: SymbolDefinition[]; selected: SelectedEntity | null; onSelect: (entity: SelectedEntity) => void }) {
  const width = graph.imageSize.width
  const height = graph.imageSize.height
  const initialViewBox = { x: 0, y: 0, width, height }
  const [committedViewBox, setCommittedViewBox] = useState<ViewBox>(initialViewBox)
  const viewBoxRef = useRef<ViewBox>(initialViewBox)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const pointer = useRef<{ startX: number; startY: number; lastX: number; lastY: number; pointerId: number; dragging: boolean } | null>(null)
  const zoomCommitTimer = useRef<number | null>(null)
  const symbolMap = useMemo(() => new Map(symbols.map((symbol) => [`${symbol.pid_entity_type}:${symbol.pid_entity_class}`, { ...symbol, url: svgUrl(symbol.svg) }])), [symbols])
  const toScreen = (point: Point) => ({ x: point.x, y: height - point.y })
  const applyViewBox = (next: ViewBox) => {
    viewBoxRef.current = next
    svgRef.current?.setAttribute('viewBox', `${next.x} ${next.y} ${next.width} ${next.height}`)
  }
  const dragStart = (event: PointerEvent<SVGSVGElement>) => {
    if (event.button !== 1) return
    event.preventDefault()
    pointer.current = { startX: event.clientX, startY: event.clientY, lastX: event.clientX, lastY: event.clientY, pointerId: event.pointerId, dragging: false }
  }
  const drag = (event: PointerEvent<SVGSVGElement>) => {
    const active = pointer.current
    if (!active) return
    if (!active.dragging && Math.hypot(event.clientX - active.startX, event.clientY - active.startY) < 4) return
    if (!active.dragging) {
      active.dragging = true
      event.currentTarget.style.cursor = 'grabbing'
      event.currentTarget.setPointerCapture(event.pointerId)
    }
    const rect = event.currentTarget.getBoundingClientRect()
    const current = viewBoxRef.current
    const dx = (event.clientX - active.lastX) * (current.width / rect.width)
    const dy = (event.clientY - active.lastY) * (current.height / rect.height)
    applyViewBox({ ...current, x: current.x - dx, y: current.y - dy })
    active.lastX = event.clientX
    active.lastY = event.clientY
  }
  const endDrag = (event: PointerEvent<SVGSVGElement>) => {
    const active = pointer.current
    if (active?.dragging && event.currentTarget.hasPointerCapture(active.pointerId)) event.currentTarget.releasePointerCapture(active.pointerId)
    if (active?.dragging) setCommittedViewBox(viewBoxRef.current)
    event.currentTarget.style.cursor = 'default'
    pointer.current = null
  }
  const zoom = (event: WheelEvent<SVGSVGElement>) => {
    event.preventDefault()
    const rect = event.currentTarget.getBoundingClientRect()
    const px = (event.clientX - rect.left) / rect.width
    const py = (event.clientY - rect.top) / rect.height
    const factor = event.deltaY > 0 ? 1.12 : 0.88
    const old = viewBoxRef.current
    const nextWidth = Math.max(width / 12, Math.min(width * 4, old.width * factor))
    const nextHeight = nextWidth * (old.height / old.width)
    applyViewBox({ x: old.x + (old.width - nextWidth) * px, y: old.y + (old.height - nextHeight) * py, width: nextWidth, height: nextHeight })
    if (zoomCommitTimer.current !== null) window.clearTimeout(zoomCommitTimer.current)
    zoomCommitTimer.current = window.setTimeout(() => setCommittedViewBox(viewBoxRef.current), 120)
  }

  return <svg ref={svgRef} className="diagram" viewBox={`${committedViewBox.x} ${committedViewBox.y} ${committedViewBox.width} ${committedViewBox.height}`} onPointerDown={dragStart} onPointerMove={drag} onPointerUp={endDrag} onPointerCancel={endDrag} onWheel={zoom} onAuxClick={(event) => event.preventDefault()} role="application" aria-label="Interactive HILT diagram">
    <g>
      <rect x="0" y="0" width={width} height={height} fill="white" stroke="#cbd5e1" pointerEvents="none" />
      {graph.links.map((link) => { const visual = lineVisual(link); const linkId = entityId(link); return <g className={`link ${selected && entityId(selected) === linkId ? 'selected-link' : ''}`} key={linkId}>{(link.payload.graphical_lines ?? []).map((line, index) => { const p1 = toScreen(line.p1); const p2 = toScreen(line.p2); return <g key={index}><line className="link-line" x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} stroke={visual.color} strokeWidth={visual.width} strokeDasharray={line.line_type === 'dashed' ? '12 8' : undefined} /><line data-hilt-line="true" className="line-hit" x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} onClick={(event) => { event.stopPropagation(); onSelect(link) }} /></g> })}{(link.payload.arrow ?? []).map((arrow, index) => { if (!arrow.bounding_box_location) return null; const point = toScreen(arrow.bounding_box_location); return <path key={index} className="arrow" d="M -13 -8 L 13 0 L -13 8 Z" transform={`translate(${point.x} ${point.y}) rotate(${-Number(arrow.rotation ?? 0)})`} /> })}</g> })}
      {graph.nodes.map((node) => {
        const p = node.payload; const center = p.bounding_box_location; if (!center) return null
        const point = toScreen(center); const w = p.bounding_box_width ?? 16; const h = p.bounding_box_height ?? 16
        const symbol = symbolMap.get(`${p.entity_type}:${p.entity_class}`); const isSelected = selected ? entityId(selected) === entityId(node) : false
        return <g data-hilt-node="true" className={`node ${isSelected ? 'selected' : ''}`} key={node.id} transform={`translate(${point.x} ${point.y}) rotate(${-Number(p.rotation ?? 0)}) translate(${-w / 2} ${-h / 2})`} onClick={(event) => { event.stopPropagation(); onSelect(node) }} tabIndex={0} role="button" aria-label={`${p.entity_class ?? 'unknown'} ${p.id}`}>
          {symbol ? <image href={symbol.url} width={w} height={h} preserveAspectRatio="none" /> : <rect className="unknown" width={w} height={h} />}
          {isSelected && <rect className="selection" x="-12" y="-12" width={w + 24} height={h + 24} />}
        </g>
      })}
      {graph.nodes.flatMap((node) => (node.payload.text ?? []).map((text, index) => { if (!text.point || !text.value) return null; const point = toScreen(text.point); return <text className="label" key={`${entityId(node)}-text-${index}`} x={point.x} y={point.y} transform={`rotate(${-Number(text.rotation ?? 0)} ${point.x} ${point.y})`}>{text.value}</text> }))}
      {graph.links.flatMap((link) => (link.payload.text ?? []).map((text, index) => { if (!text.point || !text.value) return null; const point = toScreen(text.point); return <text className="label line-label" style={{ fill: lineVisual(link).color }} key={`${entityId(link)}-text-${index}`} x={point.x} y={point.y} transform={`rotate(${-Number(text.rotation ?? 0)} ${point.x} ${point.y})`}>{text.value}</text> }))}
    </g>
  </svg>
}

function SelectionDetails({ selected }: { selected: SelectedEntity }) {
  const link = isLink(selected)
  return <>
    <h2>{selected.payload.entity_class?.replaceAll('_', ' ')}</h2>
    <p className="id">{entityId(selected)}</p>
    <dl><dt>Kind</dt><dd>{link ? 'Process line' : 'Node'}</dd><dt>Type</dt><dd>{selected.payload.entity_type}</dd>{!link && <><dt>Rotation</dt><dd>{selected.payload.rotation ?? 0}°</dd></>}</dl>
    <h3>{link ? 'Line' : 'Node'} attributes</h3><table><tbody>{attrs(selected.payload.attributes)}</tbody></table>
    <h3>Pipeline segment</h3><table><tbody>{attrs(selected.payload.piping_network_segment?.attributes)}</tbody></table>
    <details><summary>Original HILT payload</summary><pre>{JSON.stringify(selected.payload, null, 2)}</pre></details>
  </>
}

function App() {
  const [graph, setGraph] = useState<Graph | null>(null); const [symbols, setSymbols] = useState<SymbolDefinition[]>([]); const [selected, setSelected] = useState<SelectedEntity | null>(null); const [error, setError] = useState('')
  const load = async () => { try { setError(''); const hilt = await fetch('/data/hilt-2100.json').then((r) => r.json()); const parsed = unwrap(hilt); const projectId = hilt.hilt_graph?.jobData?.projectID; const library = await fetch(`/data/symbols-${projectId}.json`).then((r) => r.json()); setGraph(parsed); setSymbols(library); setSelected(null) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load fixtures.') } }
  const nodeCount = graph?.nodes.length ?? 0; const rendered = graph ? graph.nodes.filter((node) => symbols.some((s) => s.pid_entity_type === node.payload.entity_type && s.pid_entity_class === node.payload.entity_class)).length : 0
  return <main><header><div><p>HILT VIEWER POC</p><h1>SVG renderer with real HILT + matching project symbols</h1></div><button onClick={load}>Load job 2100</button></header>{error && <p className="error">{error}</p>}<section className="workspace"><div className="canvas">{graph ? <HiltSvg graph={graph} symbols={symbols} selected={selected} onSelect={setSelected} /> : <div className="empty">Load the local fixture to render the P&amp;ID.</div>}</div><aside><p className="eyebrow">{graph ? `${rendered}/${nodeCount} nodes matched to project symbols` : 'NO DOCUMENT LOADED'}</p>{selected ? <SelectionDetails selected={selected} /> : <p className="hint">Click any rendered component or line to inspect its original HILT payload and properties.</p>}</aside></section></main>
}

createRoot(document.getElementById('root')!).render(<App />)
