const scopeItems = [
  ['Equipment', 'Not selected'],
  ['Work scope', 'Not defined'],
  ['Plant state', 'Unavailable'],
]

function App() {
  return (
    <div className="min-h-screen bg-[#f7f8fa] text-slate-950">
      <header className="flex min-h-14 items-center justify-between border-b border-slate-300 bg-white px-4 sm:px-6">
        <div className="flex items-center gap-4">
          <span className="text-sm font-semibold tracking-tight">Plant360</span>
          <span className="hidden h-5 w-px bg-slate-300 sm:block" />
          <span className="font-mono text-xs text-slate-600">ISOLATION PLANNING</span>
        </div>
        <span className="rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 font-mono text-[10px] font-medium tracking-wide text-amber-900">
          ADVISORY ONLY
        </span>
      </header>

      <main className="grid min-h-[calc(100vh-3.5rem)] grid-cols-1 xl:grid-cols-[17rem_minmax(0,1fr)_20rem]">
        <aside className="border-b border-slate-300 bg-slate-50 xl:border-b-0 xl:border-r">
          <div className="border-b border-slate-300 p-5">
            <p className="font-mono text-[10px] font-medium tracking-[0.12em] text-slate-500">PLAN INPUTS</p>
            <h1 className="mt-3 text-xl font-medium tracking-tight">Start a review</h1>
            <p className="mt-2 text-sm leading-5 text-slate-600">
              Select equipment and provide the scope before running an isolation analysis.
            </p>
          </div>

          <dl className="divide-y divide-slate-200">
            {scopeItems.map(([label, value]) => (
              <div className="px-5 py-4" key={label}>
                <dt className="font-mono text-[10px] font-medium tracking-[0.1em] text-slate-500">{label}</dt>
                <dd className="mt-1.5 text-sm text-slate-700">{value}</dd>
              </div>
            ))}
          </dl>

          <div className="m-4 border-l-2 border-amber-400 bg-amber-50 px-3 py-3 text-xs leading-5 text-amber-950">
            Plant conditions and valve integrity are not assessed by this system.
          </div>
        </aside>

        <section className="flex min-h-[32rem] min-w-0 flex-col border-b border-slate-300 bg-slate-200 xl:border-b-0">
          <div className="flex items-center justify-between gap-4 border-b border-slate-300 bg-white px-5 py-3">
            <div>
              <p className="font-mono text-[10px] font-medium tracking-[0.12em] text-slate-500">DRAWING WORKSPACE</p>
              <p className="mt-1 text-sm text-slate-700">No equipment selected</p>
            </div>
            <span className="font-mono text-[11px] text-slate-500">P&amp;ID</span>
          </div>

          <div className="flex flex-1 items-center justify-center p-5 sm:p-8">
            <div className="flex aspect-[16/9] w-full max-w-5xl flex-col items-center justify-center border border-slate-300 bg-white p-8 text-center shadow-sm">
              <div className="mb-5 h-12 w-12 border border-slate-400 bg-slate-50" />
              <h2 className="text-lg font-medium">Drawing review area</h2>
              <p className="mt-2 max-w-sm text-sm leading-5 text-slate-600">
                The selected P&amp;ID and isolation boundary will appear here after a run is available.
              </p>
            </div>
          </div>
        </section>

        <aside className="bg-white xl:border-l xl:border-slate-300">
          <div className="border-b border-slate-300 p-5">
            <p className="font-mono text-[10px] font-medium tracking-[0.12em] text-slate-500">REVIEW STATUS</p>
            <div className="mt-3 flex items-center justify-between gap-4">
              <h2 className="text-xl font-medium tracking-tight">No active plan</h2>
              <span className="h-2 w-2 rounded-full bg-slate-400" aria-label="No active plan" />
            </div>
          </div>

          <div className="space-y-5 p-5">
            <section>
              <h3 className="font-mono text-[10px] font-medium tracking-[0.12em] text-slate-500">NEXT STEP</h3>
              <p className="mt-2 text-sm leading-5 text-slate-700">
                Select equipment from the available project context to begin a review.
              </p>
            </section>

            <section className="border-t border-slate-200 pt-5">
              <h3 className="font-mono text-[10px] font-medium tracking-[0.12em] text-slate-500">OUTPUTS</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-500">
                <li>Isolation candidates</li>
                <li>Evidence and warnings</li>
                <li>LOTO procedure</li>
                <li>Agent audit trace</li>
              </ul>
            </section>
          </div>
        </aside>
      </main>
    </div>
  )
}

export default App
