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

import type { AssuranceReason, DownstreamImpactWarning, IsolationPoint } from './api'
import type { IsolationMapLayers, IsolationViewMode } from './isolation-map'
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
  downstreamImpacts: DownstreamImpactWarning[]
  assuranceReasons: AssuranceReason[]
  selectedIsolationPointId: string | null
  selectedDownstreamImpactId: string | null
  selectedAssuranceReason: AssuranceReason | null
  viewMode: IsolationViewMode
  mapLayers: IsolationMapLayers
  onViewModeChange: (mode: IsolationViewMode) => void
  onDrawingSelectionChange: (selection: HiltSelection | null) => void
}

type ContextMenuState = {
  selection: HiltSelection
  pointer: HiltPointerContext
}

function selectionAttribute(selection: HiltSelection, ...names: string[]): string {
  const wanted = new Set(names.map((name) => name.toLowerCase()))
  const attribute = (selection.payload.attributes ?? []).find((item) => wanted.has(String(item.name ?? '').trim().toLowerCase()))
  return String(attribute?.value ?? '').trim()
}

function selectionTitle(selection: HiltSelection): string {
  const tag = selectionAttribute(selection, 'tag', 'tag number', 'equipment code', 'kks code')
  if (tag) return tag
  const text = (selection.payload.text ?? []).map((item) => String(item.value ?? '').trim()).filter(Boolean)
  return text[0] || String(selection.payload.name ?? selection.id)
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
  downstreamImpacts,
  assuranceReasons,
  selectedIsolationPointId,
  selectedDownstreamImpactId,
  selectedAssuranceReason,
  viewMode,
  mapLayers,
  onViewModeChange,
  onDrawingSelectionChange,
}: WorkspaceProps) {
  const viewerRef = useRef<HiltViewerHandle>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [missingSymbols, setMissingSymbols] = useState<string[]>([])
  const activeId = drawingSelection?.id ?? selectedEntityId
  const mapVisible = viewMode === 'isolation'
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
  const mappedImpacts = useMemo(() => {
    const unique = new Map<string, DownstreamImpactWarning>()
    for (const impact of downstreamImpacts) {
      const impactId = String(impact.affected_id || '').trim()
      if (impactId && !unique.has(impactId)) unique.set(impactId, impact)
    }
    return [...unique.entries()].map(([impactId, impact], index) => ({
      impact,
      impactId,
      index,
      drawingEntityId: drawingNodeIds.has(impactId) ? impactId : null,
    }))
  }, [downstreamImpacts, drawingNodeIds])
  const selectedNodeContext = useMemo(() => {
    if (!drawingSelection) return null
    const entityId = drawingSelection.id
    const point = mappedPoints.find((item) => item.drawingEntityId === entityId)?.point
    if (point) return {
      role: point.validation_state === 'rejected' ? 'Rejected isolation candidate' : 'Isolation point',
      tone: 'text-purple-800 bg-purple-50 border-purple-300',
      explanation: point.validation_state === 'rejected' ? 'Located on the drawing but not accepted by deterministic validation.' : 'Included as a proposed isolation location.',
    }
    const impact = downstreamImpacts.find((item) => item.affected_id === entityId)
    if (impact) return {
      role: `${impact.severity === 'likely' ? 'Likely' : 'Possible'} downstream target`,
      tone: 'text-orange-800 bg-orange-50 border-orange-300',
      explanation: impact.basis || 'Identified by deterministic HILT downstream traversal.',
    }
    const evidenceReason = assuranceReasons.find((reason) => reason.evidence_targets?.some((target) => target.entity_id === entityId || target.path_node_ids?.includes(entityId)))
    const evidence = evidenceReason?.evidence_targets?.find((target) => target.entity_id === entityId || target.path_node_ids?.includes(entityId))
    if (evidence) return {
      role: evidenceReason?.loto_phase ? `Field verification point — Phase ${evidenceReason.loto_phase}` : 'Evidence candidate — confirmation required',
      tone: 'text-amber-900 bg-amber-50 border-amber-300',
      explanation: evidence.verification_instruction || evidence.basis || `${String(evidence.role || 'Evidence candidate').replaceAll('_', ' ')} located on the drawing; location alone does not complete the evidence check.`,
    }
    const blocker = assuranceReasons.find((reason) => reason.terminal?.entity_id === entityId || reason.path_node_ids?.includes(entityId))
    if (blocker) {
      const encountered = blocker.encountered_devices?.find((device) => device.entity_id === entityId)
      if (encountered) return {
        role: 'Context device — not accepted as isolation',
        tone: 'text-red-800 bg-red-50 border-red-300',
        explanation: `${String(encountered.entity_class || encountered.entity_type || 'Device').replaceAll('_', ' ')} encountered on this path, but not accepted by the configured deterministic isolation policy.`,
      }
      const terminal = blocker.terminal?.entity_id === entityId
      return {
        role: terminal ? 'Blocker terminal' : 'Blocker path node',
        tone: 'text-red-800 bg-red-50 border-red-300',
        explanation: terminal ? 'The known path reaches this terminal without a qualifying isolation barrier.' : 'This entity lies on a deterministically recorded unresolved boundary path.',
      }
    }
    if (entityId === selectedEntityId) return {
      role: 'Selected equipment',
      tone: 'text-blue-800 bg-blue-50 border-blue-300',
      explanation: 'Target equipment for the current planning context.',
    }
    return { role: 'Drawing entity', tone: 'text-slate-700 bg-slate-50 border-slate-300', explanation: 'No isolation-plan role is assigned to this entity.' }
  }, [assuranceReasons, downstreamImpacts, drawingSelection, mappedPoints, selectedEntityId])
  const highlights = useMemo(() => {
    const pointHighlights = new Map<string, HiltHighlight & { selected: boolean }>()
    for (const { point, index, drawingEntityId } of mappedPoints) {
      if (!mapVisible || !mapLayers.points || !drawingEntityId) continue
      const selected = Boolean(point.selection_id && point.selection_id === selectedIsolationPointId)
      const rejected = point.validation_state === 'rejected'
      const highlight = {
        entityId: drawingEntityId,
        color: rejected || point.validation_state === 'manual' || point.requires_manual_review ? '#b45309' : '#6d28d9',
        label: `${rejected ? 'C' : 'P'}-${String(index + 1).padStart(2, '0')}`,
        badgeVariant: selected ? 'flag' as const : undefined,
        className: selected ? 'isolation-point-highlight--selected' : 'isolation-point-highlight--muted',
        selected,
      }
      const existing = pointHighlights.get(drawingEntityId)
      if (!existing || selected) pointHighlights.set(drawingEntityId, highlight)
    }
    const result = [...pointHighlights.values()]
      .sort((left, right) => Number(left.selected) - Number(right.selected))
      .map(({ selected: _selected, ...highlight }) => highlight)
    for (const { impact, impactId, index, drawingEntityId } of mappedImpacts) {
      if (!mapVisible || !mapLayers.downstream || !drawingEntityId) continue
      const selected = impactId === selectedDownstreamImpactId
      result.push({
        entityId: drawingEntityId,
        color: impact.severity === 'likely' ? '#dc2626' : '#ea580c',
        label: `D-${String(index + 1).padStart(2, '0')}`,
        badgeVariant: 'flag',
        className: selected ? 'downstream-impact-highlight--selected' : 'downstream-impact-highlight--muted',
      })
    }
    if (mapVisible && mapLayers.blockers && selectedAssuranceReason) {
      const evidenceTargets = selectedAssuranceReason.evidence_targets ?? []
      if (selectedAssuranceReason.code === 'evidence_check_incomplete' && evidenceTargets.length) {
        for (const target of evidenceTargets) {
          const ids = new Set([...(target.path_node_ids ?? []), target.entity_id].filter(Boolean))
          for (const entityId of ids) {
            if (!drawingNodeIds.has(entityId)) continue
            const candidate = entityId === target.entity_id
            result.push({
              entityId,
              color: '#d97706',
              label: candidate ? selectedAssuranceReason.loto_phase ? `PHASE ${selectedAssuranceReason.loto_phase} HOLD` : 'EVIDENCE' : undefined,
              badgeVariant: candidate ? 'flag' : undefined,
              className: candidate ? 'evidence-candidate-highlight--selected' : 'evidence-path-highlight',
            })
          }
        }
      } else {
        const terminalId = String(selectedAssuranceReason.terminal?.entity_id || '').trim()
        const pathIds = new Set([...(selectedAssuranceReason.path_node_ids ?? []), terminalId].filter(Boolean))
        for (const entityId of pathIds) {
          if (!drawingNodeIds.has(entityId)) continue
          const terminal = entityId === terminalId
          result.push({
            entityId,
            color: '#dc2626',
            label: terminal ? 'BLOCKER' : undefined,
            badgeVariant: terminal ? 'flag' : undefined,
            className: terminal ? 'assurance-blocker-terminal-highlight' : 'assurance-blocker-path-highlight',
          })
        }
      }
    }
    if (mapVisible && mapLayers.target && selectedEntityId) result.push({ entityId: selectedEntityId, color: '#0f62fe', label: 'SELECTED', badgeVariant: 'flag', className: 'equipment-target-highlight' })
    return result
  }, [drawingNodeIds, mapLayers, mapVisible, mappedImpacts, mappedPoints, selectedAssuranceReason, selectedDownstreamImpactId, selectedEntityId, selectedIsolationPointId])
  const bboxHighlights = useMemo(() => {
    const points = mappedPoints
      .map(({ point, index, drawingEntityId }) => {
        if (!mapVisible || !mapLayers.points || drawingEntityId || !point.bbox || point.bbox.length !== 4) return null
        const selected = Boolean(point.selection_id && point.selection_id === selectedIsolationPointId)
        return {
          id: `${point.selection_id || point.uuid || 'candidate'}-${index}`,
          bbox: point.bbox as [number, number, number, number],
          color: point.validation_state === 'rejected' || point.validation_state === 'manual' || point.requires_manual_review ? '#b45309' : '#6d28d9',
          label: `${point.validation_state === 'rejected' ? 'C' : 'P'}-${String(index + 1).padStart(2, '0')}`,
          badgeVariant: selected ? 'flag' as const : undefined,
          className: selected ? 'isolation-point-highlight--selected' : 'isolation-point-highlight--muted',
          selected,
        }
      })
      .filter((highlight): highlight is NonNullable<typeof highlight> => highlight !== null)
    const impacts = mappedImpacts
      .map(({ impact, impactId, index, drawingEntityId }) => {
        if (!mapVisible || !mapLayers.downstream || drawingEntityId || impact.affected_bbox?.length !== 4) return null
        const selected = impactId === selectedDownstreamImpactId
        return {
          id: `downstream-${impactId}`,
          bbox: impact.affected_bbox as [number, number, number, number],
          color: impact.severity === 'likely' ? '#dc2626' : '#ea580c',
          label: `D-${String(index + 1).padStart(2, '0')}`,
          className: selected ? 'downstream-impact-highlight--selected' : 'downstream-impact-highlight--muted',
          selected,
        }
      })
      .filter((highlight): highlight is NonNullable<typeof highlight> => highlight !== null)
    const evidence = selectedAssuranceReason?.code === 'evidence_check_incomplete'
      ? (selectedAssuranceReason.evidence_targets ?? []).map((target, index) => {
        if (!mapVisible || !mapLayers.blockers || drawingNodeIds.has(target.entity_id) || target.bbox?.length !== 4) return null
        return {
          id: `evidence-${target.entity_id}-${index}`,
          bbox: target.bbox as [number, number, number, number],
          color: '#d97706',
          label: selectedAssuranceReason.loto_phase ? `PHASE ${selectedAssuranceReason.loto_phase} HOLD` : 'EVIDENCE',
          className: 'evidence-candidate-highlight--selected',
          selected: true,
        }
      }).filter((highlight): highlight is NonNullable<typeof highlight> => highlight !== null)
      : []
    return [...points, ...impacts, ...evidence]
      .sort((left, right) => Number(left.selected) - Number(right.selected))
      .map(({ selected: _selected, ...highlight }) => highlight)
  }, [drawingNodeIds, mapLayers, mapVisible, mappedImpacts, mappedPoints, selectedAssuranceReason, selectedDownstreamImpactId, selectedIsolationPointId])

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

  useEffect(() => {
    if (!selectedDownstreamImpactId) return
    const mapped = mappedImpacts.find(({ impactId }) => impactId === selectedDownstreamImpactId)
    if (!mapped) return
    if (mapped.drawingEntityId && viewerRef.current?.panToEntity?.(mapped.drawingEntityId)) return
    if (mapped.impact.affected_bbox?.length !== 4) return
    viewerRef.current?.panToBBox(mapped.impact.affected_bbox as [number, number, number, number])
  }, [mappedImpacts, selectedDownstreamImpactId])

  useEffect(() => {
    if (!selectedAssuranceReason) return
    const evidenceTarget = selectedAssuranceReason.evidence_targets?.find((target) => drawingNodeIds.has(target.entity_id) || target.bbox?.length === 4)
    if (evidenceTarget) {
      if (drawingNodeIds.has(evidenceTarget.entity_id) && viewerRef.current?.panToEntity?.(evidenceTarget.entity_id)) return
      if (evidenceTarget.bbox?.length === 4) {
        viewerRef.current?.panToBBox(evidenceTarget.bbox as [number, number, number, number])
        return
      }
    }
    const terminalId = String(selectedAssuranceReason.terminal?.entity_id || '').trim()
    if (terminalId && drawingNodeIds.has(terminalId) && viewerRef.current?.panToEntity?.(terminalId)) return
    const fallbackId = [...(selectedAssuranceReason.path_node_ids ?? [])].reverse().find((entityId) => drawingNodeIds.has(entityId))
    if (fallbackId) viewerRef.current?.panToEntity?.(fallbackId)
  }, [drawingNodeIds, selectedAssuranceReason])

  return (
    <div className="flex h-full min-h-0 w-full flex-col bg-white">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-medium">{drawingName}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden font-mono text-[10px] text-slate-500 2xl:inline">UNIGRAPH {graphName}</span>
          <div className="flex border border-slate-300" role="group" aria-label="Drawing view mode">
            <button className={`px-2 py-1.5 font-mono text-[9px] ${viewMode === 'drawing' ? 'bg-slate-800 text-white' : 'bg-white text-slate-600 hover:bg-slate-100'}`} onClick={() => onViewModeChange('drawing')} type="button">DRAWING</button>
            <button className={`border-l border-slate-300 px-2 py-1.5 font-mono text-[9px] disabled:cursor-not-allowed disabled:text-slate-300 ${viewMode === 'isolation' ? 'bg-blue-700 text-white' : 'bg-white text-slate-600 hover:bg-slate-100'}`} disabled={!isolationPoints.length && !assuranceReasons.length && !downstreamImpacts.length} onClick={() => onViewModeChange('isolation')} type="button">ISOLATION MAP</button>
          </div>
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
          panAnimationDuration={520}
          panButton="both"
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

        {drawingSelection && selectedNodeContext && graph && <aside aria-label="Selected drawing entity" className="absolute right-3 top-3 z-30 w-[min(21rem,calc(100%-1.5rem))] border border-slate-300 bg-white/98 shadow-xl backdrop-blur-sm">
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 p-3">
            <div className="min-w-0">
              <p className="font-mono text-[9px] uppercase tracking-[0.1em] text-slate-500">{drawingSelection.kind}</p>
              <h3 className="mt-1 break-words text-sm font-semibold text-slate-950">{selectionTitle(drawingSelection)}</h3>
              <p className="mt-0.5 text-xs capitalize text-slate-500">{String(drawingSelection.payload.entity_class || drawingSelection.payload.entity_type || 'unclassified').replaceAll('_', ' ')}</p>
            </div>
            <button aria-label="Close entity details" className="shrink-0 px-1 text-lg leading-none text-slate-400 hover:text-slate-800" onClick={() => onDrawingSelectionChange(null)} type="button">×</button>
          </div>
          <div className="p-3">
            <div className={`border px-2.5 py-2 ${selectedNodeContext.tone}`}>
              <p className="font-mono text-[9px] font-semibold uppercase">{selectedNodeContext.role}</p>
              <p className="mt-1 text-[10px] leading-4">{selectedNodeContext.explanation}</p>
            </div>
            {(drawingSelection.payload.attributes?.length ?? 0) > 0 && <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-[10px]">
              {drawingSelection.payload.attributes?.slice(0, 6).map((attribute, index) => <div className="contents" key={`${String(attribute.name)}-${index}`}><dt className="text-slate-500">{String(attribute.name || 'Attribute')}</dt><dd className="break-words text-slate-800">{String(attribute.value ?? '—')}</dd></div>)}
            </dl>}
            <div className="mt-3 flex gap-2">
              <button className="border border-slate-300 px-2 py-1 font-mono text-[9px] text-slate-700 hover:bg-slate-50" onClick={() => viewerRef.current?.panToEntity?.(drawingSelection.id)} type="button">FOCUS</button>
            </div>
            <details className="mt-3 border-t border-slate-200 pt-2 text-[9px] text-slate-600">
              <summary className="cursor-pointer font-mono font-semibold">TECHNICAL DETAILS</summary>
              <dl className="mt-2 space-y-1 font-mono"><div><dt className="inline text-slate-400">Entity ID: </dt><dd className="inline break-all">{drawingSelection.id}</dd></div><div><dt className="inline text-slate-400">Entity type: </dt><dd className="inline">{String(drawingSelection.payload.entity_type || 'unknown')}</dd></div>{(drawingSelection.payload.attributes?.length ?? 0) > 6 && <div><dt className="block text-slate-400">Additional attributes</dt>{drawingSelection.payload.attributes?.slice(6).map((attribute, index) => <dd className="mt-0.5 break-words" key={`${String(attribute.name)}-extra-${index}`}>{String(attribute.name)}: {String(attribute.value ?? '—')}</dd>)}</div>}</dl>
            </details>
          </div>
        </aside>}

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
