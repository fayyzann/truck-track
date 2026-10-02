import type { ScheduleEvent } from '../types'
import { statusLabel } from '../utils'

const statusY = { off_duty: 14, sleeper: 34, driving: 54, on_duty: 74 }

export function DutyStrip({ events }: { events: ScheduleEvent[] }) {
  if (!events.length) return null
  const start = new Date(events[0].start).getTime()
  const end = new Date(events.at(-1)!.end).getTime()
  const total = Math.max(1, end - start)

  const path = events
    .map((event, index) => {
      const x1 = 116 + ((new Date(event.start).getTime() - start) / total) * 864
      const x2 = 116 + ((new Date(event.end).getTime() - start) / total) * 864
      const y = statusY[event.status]
      const previousY = index ? statusY[events[index - 1].status] : y
      return `${index ? `V ${y}` : `M ${x1} ${previousY}`} H ${x2}`
    })
    .join(' ')

  return (
    <div className="duty-strip">
      <div className="strip-heading">
        <h2>Duty status</h2>
        <p>{events.length} planned changes</p>
      </div>
      <svg viewBox="0 0 1000 90" role="img" aria-label="Duty status across the planned trip">
        {Object.entries(statusY).map(([status, y]) => (
          <g key={status}>
            <text x="0" y={y + 4}>{statusLabel(status)}</text>
            <line x1="116" x2="980" y1={y} y2={y} className="strip-grid" />
          </g>
        ))}
        <path d={path} className="strip-path" />
      </svg>
    </div>
  )
}
