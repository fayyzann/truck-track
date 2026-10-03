import { ChevronDown, LoaderCircle, Route } from 'lucide-react'
import { useId, useState } from 'react'
import type { LogMetadata, TripPlanRequest } from '../types'
import { nextQuarterHourLocal } from '../utils'
import { LocationField } from './LocationField'

interface PlannerFormProps {
  loading: boolean
  onSubmit: (request: TripPlanRequest) => Promise<void>
}

const initialMetadata: LogMetadata = {
  driver_name: '',
  carrier_name: '',
  carrier_address: '',
  vehicle_numbers: '',
  shipping_document: '',
}

export function PlannerForm({ loading, onSubmit }: PlannerFormProps) {
  const [current, setCurrent] = useState('')
  const [pickup, setPickup] = useState('')
  const [dropoff, setDropoff] = useState('')
  const [cycle, setCycle] = useState('0')
  const [departure, setDeparture] = useState(nextQuarterHourLocal)
  const [metadata, setMetadata] = useState<LogMetadata>(initialMetadata)

  const updateMetadata = (key: keyof LogMetadata, value: string) => {
    setMetadata((previous) => ({ ...previous, [key]: value }))
  }

  return (
    <form
      className="planner-form"
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit({
          current_location: current,
          pickup_location: pickup,
          dropoff_location: dropoff,
          cycle_hours_used: Number(cycle),
          departure_at: new Date(departure).toISOString(),
          terminal_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Chicago',
          log_metadata: metadata,
        })
      }}
    >
      <div className="form-heading">
        <span className="route-mark" aria-hidden="true"><i /><i /><i /></span>
        <div>
          <p>Dispatch plan</p>
          <h1>TruckTrack</h1>
        </div>
      </div>
      <p className="form-intro">Build a legal route plan and daily logs before the wheels turn.</p>

      <div className="route-fields">
        <LocationField
          label="Current location"
          value={current}
          placeholder="e.g. Chicago, IL"
          onChange={setCurrent}
        />
        <LocationField
          label="Pickup location"
          value={pickup}
          placeholder="Where is the load?"
          onChange={setPickup}
        />
        <LocationField
          label="Drop-off location"
          value={dropoff}
          placeholder="Final destination"
          onChange={setDropoff}
        />
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="cycle-hours">Cycle used</label>
          <div className="input-suffix">
            <input
              id="cycle-hours"
              type="number"
              min="0"
              max="70"
              step="0.01"
              inputMode="decimal"
              value={cycle}
              onChange={(event) => setCycle(event.target.value)}
              required
            />
            <span>hrs / 70</span>
          </div>
        </div>
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            onChange={(event) => setDeparture(event.target.value)}
            required
          />
        </div>
      </div>

      <details className="log-details">
        <summary>
          <span>Log details</span>
          <small>Optional</small>
          <ChevronDown aria-hidden="true" size={17} />
        </summary>
        <div className="details-grid">
          <TextField label="Driver name" value={metadata.driver_name} onChange={(value) => updateMetadata('driver_name', value)} />
          <TextField label="Carrier name" value={metadata.carrier_name} onChange={(value) => updateMetadata('carrier_name', value)} />
          <TextField label="Carrier address" value={metadata.carrier_address} onChange={(value) => updateMetadata('carrier_address', value)} />
          <TextField label="Vehicle numbers" value={metadata.vehicle_numbers} onChange={(value) => updateMetadata('vehicle_numbers', value)} />
          <TextField label="Shipping document" value={metadata.shipping_document} onChange={(value) => updateMetadata('shipping_document', value)} />
        </div>
      </details>

      <button className="plan-button" type="submit" disabled={loading}>
        {loading ? <LoaderCircle className="spin" aria-hidden="true" size={19} /> : <Route aria-hidden="true" size={19} />}
        {loading ? 'Building plan…' : 'Plan compliant trip'}
      </button>
      <p className="form-footnote">Planning aid only. Not a certified ELD.</p>
    </form>
  )
}

function TextField({ label, value = '', onChange }: { label: string; value?: string; onChange: (value: string) => void }) {
  const id = useId()
  return (
    <div className="field compact-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}
