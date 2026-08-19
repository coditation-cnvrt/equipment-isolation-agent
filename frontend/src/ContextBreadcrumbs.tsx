import { useEffect, useRef, useState } from 'react'

import type { SearchableSelectOption } from './SearchableSelect'

type BreadcrumbItem = {
  key: string
  label: string
  value: string
  placeholder: string
  options: SearchableSelectOption[]
  disabled?: boolean
  loading?: boolean
  onChange: (value: string) => void
  onClear?: () => void
}

type ContextBreadcrumbsProps = {
  items: BreadcrumbItem[]
}

function BreadcrumbPicker({ item, first }: { item: BreadcrumbItem; first: boolean }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const selected = item.options.find((option) => option.value === item.value)
  const filtered = item.options.filter((option) => option.searchText.toLowerCase().includes(query.trim().toLowerCase()))

  useEffect(() => {
    if (item.loading) {
      setOpen(false)
      setQuery('')
    }
  }, [item.loading])

  useEffect(() => {
    function closeOnOutsidePointer(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOnOutsidePointer)
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer)
  }, [])

  function choose(value: string) {
    setOpen(false)
    setQuery('')
    item.onChange(value)
  }

  return <div className={`relative ${first ? '' : '-ml-2'}`} ref={rootRef}>
    <button
      aria-busy={item.loading || undefined}
      aria-expanded={open}
      className={`flex h-10 max-w-64 items-center bg-slate-100 text-left transition hover:bg-blue-50 disabled:text-slate-400 ${item.loading ? 'disabled:cursor-wait' : 'disabled:cursor-not-allowed'} ${item.onClear && selected ? 'pr-11' : 'pr-7'} ${first ? 'pl-3' : 'pl-6'}`}
      disabled={item.disabled || item.loading}
      onClick={() => setOpen((current) => !current)}
      style={{ clipPath: first ? 'polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%)' : 'polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%, 12px 50%)' }}
      type="button"
    >
      <span className="min-w-0">
        <span className="block font-mono text-[8px] uppercase tracking-wide text-slate-400">{item.label}</span>
        <span className={`flex items-center gap-1.5 truncate text-xs ${selected && !item.loading ? 'font-medium text-slate-800' : 'font-medium text-blue-700'}`}>
          {item.loading && <span aria-hidden="true" className="inline-block size-3 shrink-0 animate-spin rounded-full border-2 border-blue-200 border-t-blue-700" />}
          <span className="truncate">{item.loading ? `Loading ${item.label.toLowerCase()}…` : selected?.label ?? item.placeholder}</span>
        </span>
      </span>
    </button>
    {item.onClear && selected && <button
      aria-label={`Clear ${item.label.toLowerCase()} selection`}
      className="absolute right-4 top-1/2 z-10 flex size-5 -translate-y-1/2 items-center justify-center rounded-full text-sm text-slate-500 hover:bg-white hover:text-slate-900"
      onClick={(event) => { event.stopPropagation(); setOpen(false); item.onClear?.() }}
      title={`Clear ${item.label.toLowerCase()} selection`}
      type="button"
    >×</button>}
    {open && <div className="absolute left-0 z-50 mt-1 w-80 border border-slate-300 bg-white p-2 shadow-xl">
      <input
        autoFocus
        className="w-full border border-slate-300 px-2.5 py-2 text-xs outline-none focus:border-blue-600"
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false)
          if (event.key === 'Enter' && filtered[0]) {
            event.preventDefault()
            choose(filtered[0].value)
          }
        }}
        placeholder={`Search ${item.label.toLowerCase()}`}
        type="search"
        value={query}
      />
      <div className="mt-2 max-h-64 overflow-y-auto border-t border-slate-200 pt-1">
        {filtered.length ? filtered.map((option) => <button
          className={`block w-full px-2.5 py-2 text-left text-xs hover:bg-slate-100 ${option.value === item.value ? 'bg-blue-50 text-blue-800' : 'text-slate-700'}`}
          key={option.value}
          onClick={() => choose(option.value)}
          type="button"
        >{option.label}</button>) : <p className="px-2.5 py-3 text-xs text-slate-500">{query.trim() ? 'No matching options' : `No ${item.label.toLowerCase()} options available`}</p>}
      </div>
    </div>}
  </div>
}

export default function ContextBreadcrumbs({ items }: ContextBreadcrumbsProps) {
  return <nav aria-label="Planning context" className="flex h-12 items-center overflow-visible border-b border-slate-300 bg-white px-4">
    <span className="mr-3 hidden font-mono text-[9px] tracking-[0.12em] text-slate-400 2xl:inline">CONTEXT</span>
    {items.map((item, index) => <BreadcrumbPicker first={index === 0} item={item} key={item.key} />)}
  </nav>
}
