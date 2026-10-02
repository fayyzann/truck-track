import { AlertCircle, ArrowRight, ShieldCheck } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { ApiError, planTrip } from './api'
import { DailyLogs } from './components/DailyLogs'
import { PlannerForm } from './components/PlannerForm'
import { TripResults } from './components/TripResults'
import type { TripPlan, TripPlanRequest } from './types'

const RouteMap = lazy(() =>
  import('./components/RouteMap').then((module) => ({ default: module.RouteMap })),
)

export function App() {
  const [plan, setPlan] = useState<TripPlan>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>()

  async function handlePlan(request: TripPlanRequest) {
    setLoading(true)
    setError(undefined)
    try {
      const result = await planTrip(request)
      setPlan(result)
      window.setTimeout(() => document.getElementById('trip-results')?.scrollIntoView({ behavior: 'smooth' }), 50)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'The trip could not be planned. Check the API connection and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <section className="app-shell">
        <aside className="planning-rail">
          <PlannerForm loading={loading} onSubmit={handlePlan} />
        </aside>
        <div className="workspace">
          {!plan && !loading && (
            <section className="empty-workspace">
              <Suspense fallback={<div className="route-map map-fallback" />}>
                <RouteMap />
              </Suspense>
              <div className="empty-copy">
                <span><ShieldCheck aria-hidden="true" /></span>
                <p>HOS-aware planning</p>
                <h2>See the road and the clock together.</h2>
                <p>Enter the three locations and your current cycle. TruckTrack will place the pickup, delivery, fuel, breaks, sleeper periods, and restart on one operational timeline.</p>
                <div className="empty-flow" aria-label="Planning flow">
                  <span>Route</span><ArrowRight aria-hidden="true" /><span>Schedule</span><ArrowRight aria-hidden="true" /><span>Logs</span>
                </div>
              </div>
            </section>
          )}
          {loading && <LoadingState />}
          {error && (
            <div className="error-banner" role="alert">
              <AlertCircle aria-hidden="true" />
              <div><strong>Trip plan not created</strong><p>{error}</p></div>
            </div>
          )}
          {plan && (
            <div id="trip-results">
              <TripResults plan={plan} />
              <DailyLogs logs={plan.daily_logs} />
            </div>
          )}
        </div>
      </section>
      <footer className="app-footer no-print">
        <span>TruckTrack</span>
        <p>Assessment-grade planning aid · Standard property-carrier HOS assumptions</p>
      </footer>
    </main>
  )
}

function LoadingState() {
  return (
    <section className="loading-state" aria-live="polite">
      <div className="loading-road"><i /><i /><i /></div>
      <p>Geocoding stops, routing the truck, and balancing the HOS clocks…</p>
      <div className="loading-map" />
      <div className="loading-lines"><i /><i /><i /></div>
    </section>
  )
}
