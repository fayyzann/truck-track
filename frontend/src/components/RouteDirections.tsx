import { ChevronDown, ListTree } from 'lucide-react'
import type { TripPlan } from '../types'
import { formatDuration } from '../utils'

type RouteData = TripPlan['route']

export function RouteDirections({ route }: { route: RouteData }) {
  if (route.instructions.length === 0) return null

  const legs = route.legs
    .map((leg, legIndex) => ({
      leg,
      legIndex,
      steps: route.instructions.filter((step) => step.leg_index === legIndex),
    }))
    .filter(({ steps }) => steps.length > 0)

  return (
    <details className="directions-panel">
      <summary>
        <span className="directions-summary-icon" aria-hidden="true"><ListTree /></span>
        <span className="directions-summary-copy">
          <strong>Turn-by-turn directions</strong>
          <small>{legs.length} route {legs.length === 1 ? 'leg' : 'legs'}</small>
        </span>
        <span className="directions-count">
          {route.instructions.length} {route.instructions.length === 1 ? 'maneuver' : 'maneuvers'}
        </span>
        <ChevronDown className="directions-chevron" aria-hidden="true" />
      </summary>

      <div className="directions-route-book">
        {legs.map(({ leg, legIndex, steps }) => (
          <section
            className="directions-leg"
            aria-labelledby={`directions-leg-${legIndex}`}
            key={`${leg.start}-${leg.end}-${legIndex}`}
          >
            <header>
              <span>Leg {legIndex + 1}</span>
              <div>
                <h3 id={`directions-leg-${legIndex}`}>{leg.start} to {leg.end}</h3>
                <p>{leg.distance_miles.toLocaleString()} mi · {formatDuration(leg.duration_minutes)}</p>
              </div>
            </header>
            <ol>
              {steps.map((step, stepIndex) => (
                <li key={`${step.instruction}-${stepIndex}`}>
                  <span className="direction-index" aria-hidden="true">{stepIndex + 1}</span>
                  <div>
                    <strong>{step.instruction}</strong>
                    {step.name && <p>{step.name}</p>}
                  </div>
                  <small>
                    {step.distance_miles.toLocaleString()} mi · {formatDuration(step.duration_minutes)}
                  </small>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </details>
  )
}
