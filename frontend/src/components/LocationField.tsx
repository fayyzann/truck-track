import { MapPin } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { searchLocations } from '../api'
import type { LocationResult } from '../types'

interface LocationFieldProps {
  label: string
  value: string
  placeholder: string
  onChange: (value: string) => void
}

export function LocationField({ label, value, placeholder, onChange }: LocationFieldProps) {
  const id = useId()
  const [suggestions, setSuggestions] = useState<LocationResult[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (value.trim().length < 3 || !open) {
      setSuggestions([])
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      searchLocations(value, controller.signal)
        .then(setSuggestions)
        .catch(() => setSuggestions([]))
    }, 300)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [value, open])

  return (
    <div className="field location-field">
      <label htmlFor={id}>{label}</label>
      <div className="input-with-icon">
        <MapPin aria-hidden="true" size={17} />
        <input
          id={id}
          value={value}
          placeholder={placeholder}
          autoComplete="off"
          required
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onChange={(event) => onChange(event.target.value)}
          aria-autocomplete="list"
          aria-expanded={open && suggestions.length > 0}
          aria-controls={`${id}-suggestions`}
        />
      </div>
      {open && suggestions.length > 0 && (
        <ul className="suggestions" id={`${id}-suggestions`} role="listbox">
          {suggestions.map((suggestion) => (
            <li key={`${suggestion.provider_id}-${suggestion.label}`}>
              <button
                type="button"
                role="option"
                onMouseDown={() => {
                  onChange(suggestion.label)
                  setOpen(false)
                }}
              >
                {suggestion.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
