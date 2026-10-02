import { AlertTriangle, CalendarDays, CheckCircle2, Clock3, Gauge, MapPin, Moon, Route } from 'lucide-react'
import { lazy, Suspense } from 'react'
import type { ScheduleEvent, TripPlan } from '../types'
import { formatClock, formatDateTime, formatDuration, statusLabel } from '../utils'
import { DutyStrip } from './DutyStrip'

const RouteMap = lazy(() => import('./RouteMap').then((module) => ({ default: module.RouteMap })))

export function TripResults({ plan }: { plan: TripPlan }) {
  return (
    <div className="results">
      <section className="map-panel" aria-labelledby="route-heading">
        <div className="map-header">
          <div>
            <p className="section-kicker">Route ready</p>
            <h2 id="route-heading">{plan.route.locations[0].label} to {plan.route.locations.at(-1)?.label}</h2>
          </div>
          <div className="route-stats" aria-label="Route summary">
            <span><Route size={16} aria-hidden="true" /> {plan.route.distance_miles.toLocaleString()} mi</span>
            <span><Clock3 size={16} aria-hidden="true" /> {formatDuration(plan.route.duration_minutes)}</span>
          </div>
        </div>
        <Suspense fallback={<div className="route-map map-fallback" />}>
          <RouteMap plan={plan} />
        </Suspense>
      </section>

      <section className="summary-band" aria-label="Compliance summary">
        <SummaryMetric icon={<Gauge />} label="Driving" value={`${plan.compliance.driving_hours} hrs`} />
        <SummaryMetric icon={<Clock3 />} label="On duty" value={`${plan.compliance.on_duty_hours} hrs`} />
        <SummaryMetric icon={<Moon />} label="Planned rest" value={`${plan.compliance.planned_rest_hours} hrs`} />
        <SummaryMetric icon={<CalendarDays />} label="Log sheets" value={String(plan.daily_logs.length)} />
        <div className="compliance-stamp"><CheckCircle2 aria-hidden="true" /> Compliant plan</div>
      </section>

      <DutyStrip events={plan.events} />

      <section className="timeline-section" aria-labelledby="timeline-heading">
        <div className="section-heading-row">
          <div>
            <p className="section-kicker">Dispatch timeline</p>
            <h2 id="timeline-heading">Stops and duty changes</h2>
          </div>
          <p>{formatDateTime(plan.compliance.trip_start)} – {formatDateTime(plan.compliance.trip_end)}</p>
        </div>
        <ol className="timeline">
          {plan.events.map((event, index) => (
            <TimelineItem key={`${event.start}-${event.reason}-${index}`} event={event} />
          ))}
        </ol>
      </section>

      {plan.warnings.length > 0 && (
        <section className="warning-panel" aria-labelledby="planning-notes-heading">
          <AlertTriangle aria-hidden="true" />
          <div>
            <h2 id="planning-notes-heading">Planning notes</h2>
            <ul>{plan.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
          </div>
        </section>
      )}
    </div>
  )
}

function SummaryMetric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="summary-metric">
      <span aria-hidden="true">{icon}</span>
      <div><small>{label}</small><strong>{value}</strong></div>
    </div>
  )
}

function TimelineItem({ event }: { event: ScheduleEvent }) {
  return (
    <li className={`timeline-item timeline-${event.status}`}>
      <div className="timeline-time">
        <strong>{formatClock(event.start)}</strong>
        <span>{formatClock(event.end)}</span>
      </div>
      <div className="timeline-node" aria-hidden="true" />
      <div className="timeline-copy">
        <div>
          <h3>{event.title}</h3>
          <span className={`status-chip status-${event.status}`}>{statusLabel(event.status)}</span>
        </div>
        <p><MapPin aria-hidden="true" size={14} /> {event.location}</p>
        <small>{formatDuration(event.duration_minutes)}{event.distance_miles > 0 ? ` · ${Math.round(event.distance_miles)} mi` : ''}</small>
      </div>
    </li>
  )
}
