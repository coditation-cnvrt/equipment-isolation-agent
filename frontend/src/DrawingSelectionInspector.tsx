import type { HiltAttribute, HiltSelection } from '@coditation-cnvrt/p360-hitl-viewer'

type DrawingSelectionInspectorProps = {
  selection: HiltSelection
  onClear: () => void
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

function attributeRows(attributes: HiltAttribute[] = []) {
  return attributes
    .filter((attribute) => attribute.name && attribute.value !== null && attribute.value !== undefined && attribute.value !== '')
    .map((attribute) => ({ name: String(attribute.name), value: displayValue(attribute.value) }))
}

export default function DrawingSelectionInspector({ selection, onClear }: DrawingSelectionInspectorProps) {
  const payload = selection.payload
  const attributes = attributeRows(payload.attributes)
  const textValues = (payload.text ?? []).map((text) => text.value).filter(Boolean).join(' · ')
  const systemId = payload.piping_network_system?.id
  const segmentId = payload.piping_network_segment?.id

  return (
    <section className="border-b border-slate-300 bg-blue-50/40 p-5" aria-label="Selected drawing entity details">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[10px] tracking-[0.12em] text-blue-700">DRAWING SELECTION · {selection.kind.toUpperCase()}</p>
          <h3 className="mt-2 break-words text-base font-medium text-slate-950">
            {textValues || String(payload.entity_class ?? payload.entity_type ?? 'Unclassified entity').replaceAll('_', ' ')}
          </h3>
        </div>
        <button className="shrink-0 border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-100" onClick={onClear} type="button">Clear</button>
      </div>

      <dl className="mt-4 grid grid-cols-[5rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-xs leading-5">
        <dt className="font-mono text-[10px] text-slate-500">ID</dt>
        <dd className="break-all font-mono text-slate-800">{selection.id}</dd>
        <dt className="font-mono text-[10px] text-slate-500">CLASS</dt>
        <dd className="capitalize text-slate-800">{displayValue(payload.entity_class).replaceAll('_', ' ')}</dd>
        <dt className="font-mono text-[10px] text-slate-500">TYPE</dt>
        <dd className="capitalize text-slate-800">{displayValue(payload.entity_type).replaceAll('_', ' ')}</dd>
        {systemId && <><dt className="font-mono text-[10px] text-slate-500">SYSTEM</dt><dd className="break-all font-mono text-slate-800">{systemId}</dd></>}
        {segmentId && <><dt className="font-mono text-[10px] text-slate-500">SEGMENT</dt><dd className="break-all font-mono text-slate-800">{segmentId}</dd></>}
      </dl>

      {attributes.length > 0 && <div className="mt-5 border-t border-blue-200 pt-4">
        <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">ATTRIBUTES</p>
        <dl className="mt-2 max-h-64 divide-y divide-slate-200 overflow-y-auto border-y border-slate-200 bg-white/80">
          {attributes.map((attribute, index) => <div className="grid grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] gap-3 px-2 py-2 text-xs" key={`${attribute.name}-${index}`}>
            <dt className="break-words text-slate-500">{attribute.name.replaceAll('_', ' ')}</dt>
            <dd className="break-words text-slate-900">{attribute.value}</dd>
          </div>)}
        </dl>
      </div>}
    </section>
  )
}
