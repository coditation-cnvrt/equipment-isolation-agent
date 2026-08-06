import { useState } from 'react'

export type SearchableSelectOption = {
  value: string
  label: string
  searchText: string
}

type SearchableSelectProps = {
  disabled?: boolean
  emptyLabel?: string
  label: string
  onChange: (value: string) => void
  options: SearchableSelectOption[]
  placeholder: string
  searchPlaceholder: string
  value: string
}

function SearchableSelect({
  disabled = false,
  emptyLabel = 'No matching options',
  label,
  onChange,
  options,
  placeholder,
  searchPlaceholder,
  value,
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const selected = options.find((option) => option.value === value)
  const filtered = options.filter((option) => option.searchText.toLowerCase().includes(query.trim().toLowerCase()))

  function choose(nextValue: string) {
    setOpen(false)
    setQuery('')
    onChange(nextValue)
  }

  return (
    <div className="relative">
      <span className="text-xs font-medium text-slate-700">{label}</span>
      <button
        aria-expanded={open}
        className="mt-1.5 flex w-full items-center justify-between rounded-sm border border-slate-300 bg-white px-3 py-2.5 text-left text-sm shadow-sm outline-none transition hover:border-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className={selected ? 'text-slate-900' : 'text-slate-500'}>{selected?.label ?? placeholder}</span>
        <span aria-hidden="true" className="text-slate-500">⌄</span>
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-sm border border-slate-300 bg-white p-2 shadow-xl">
          <input
            autoFocus
            className="w-full rounded-sm border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && filtered[0]) {
                event.preventDefault()
                choose(filtered[0].value)
              }
            }}
            placeholder={searchPlaceholder}
            type="search"
            value={query}
          />
          <div className="mt-2 max-h-56 overflow-y-auto border-t border-slate-200 py-1">
            {filtered.length ? filtered.map((option) => (
              <button
                className="block w-full rounded-sm px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 focus:bg-slate-100 focus:outline-none"
                key={option.value}
                onClick={() => choose(option.value)}
                type="button"
              >
                {option.label}
              </button>
            )) : <p className="px-3 py-3 text-sm text-slate-500">{emptyLabel}</p>}
          </div>
        </div>
      )}
    </div>
  )
}

export default SearchableSelect
