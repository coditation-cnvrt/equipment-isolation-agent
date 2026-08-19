type PlanningSidebarProps = {
  projectLabel: string
  collectionLabel: string
  drawingLabel: string
  graphLabel: string
  equipmentLabel: string
  contextError: string
  onRetryContext: () => void
}

export default function PlanningSidebar({
  projectLabel,
  collectionLabel,
  drawingLabel,
  graphLabel,
  equipmentLabel,
  contextError,
  onRetryContext,
}: PlanningSidebarProps) {
  const steps = [
    { label: 'Project', value: projectLabel },
    { label: 'Collection', value: collectionLabel },
    { label: 'P&ID Drawing', value: drawingLabel },
    { label: 'UniGraph', value: graphLabel },
    { label: 'Equipment', value: equipmentLabel },
  ]
  const nextStep = steps.find((step) => !step.value)

  return <div className="min-h-full bg-slate-50">
    <div className="border-b border-slate-300 p-5">
      <p className="font-mono text-[10px] tracking-[0.12em] text-slate-500">PLANNING CONTEXT</p>
      <h1 className="mt-2 text-lg font-medium">{nextStep ? `Choose ${nextStep.label.toLowerCase()}` : 'Context ready'}</h1>
      <p className="mt-2 text-xs leading-5 text-slate-600">Select a project, collection, P&amp;ID drawing, UniGraph, and equipment to prepare an advisory isolation plan.</p>
      {contextError && <div className="mt-3 border-l-2 border-red-500 bg-red-50 p-2 text-[10px] leading-4 text-red-900" role="alert"><p>{contextError}</p><button className="mt-2 border border-red-400 bg-white px-2 py-1 font-mono text-[9px] font-semibold hover:bg-red-100" onClick={onRetryContext} type="button">RETRY CONTEXT</button></div>}
    </div>

    <section className="border-b border-slate-300 p-5">
      <h2 className="font-mono text-[10px] tracking-[0.12em] text-slate-500">SELECTION PROGRESS</h2>
      <ol className="mt-3 space-y-2">
        {steps.map((step, index) => <li className="flex items-start gap-2" key={step.label}>
          <span className={`mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full font-mono text-[8px] ${step.value ? 'bg-emerald-600 text-white' : nextStep?.label === step.label ? 'bg-blue-700 text-white' : 'bg-slate-200 text-slate-500'}`}>{step.value ? '✓' : index + 1}</span>
          <span className="min-w-0"><span className="block font-mono text-[9px] uppercase text-slate-400">{step.label}</span><span className={`block truncate text-xs ${step.value ? 'text-slate-800' : 'text-slate-400'}`}>{step.value || 'Not selected'}</span></span>
        </li>)}
      </ol>
    </section>

    <div className="p-5 text-xs leading-5 text-slate-500">
      Saved plans and recent runs are loaded only when opened from the header.
    </div>
  </div>
}
