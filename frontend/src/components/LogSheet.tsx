import { Download } from 'lucide-react'
import { toPng } from 'html-to-image'
import { forwardRef } from 'react'
import type { DailyLog, DutyStatus } from '../types'

const ROW_Y: Record<DutyStatus, number> = {
  off_duty: 179,
  sleeper: 198,
  driving: 218,
  on_duty: 237,
}
const GRID_START = 65
const GRID_WIDTH = 389

interface LogSheetProps {
  log: DailyLog
  index: number
}

export const LogSheet = forwardRef<HTMLDivElement, LogSheetProps>(function LogSheet({ log, index }, ref) {
  const displaySegments = log.display_segments || log.segments
  const displayTotals = log.display_totals || log.totals
  const path = displaySegments
    .map((segment, segmentIndex) => {
      const xStart = GRID_START + (segment.start_minute / 1440) * GRID_WIDTH
      const xEnd = GRID_START + (segment.end_minute / 1440) * GRID_WIDTH
      const y = ROW_Y[segment.status]
      const previousY = segmentIndex ? ROW_Y[displaySegments[segmentIndex - 1].status] : y
      return `${segmentIndex ? `V ${y}` : `M ${xStart} ${previousY}`} H ${xEnd}`
    })
    .join(' ')

  const date = new Date(`${log.date}T12:00:00`)
  const dateText = new Intl.DateTimeFormat('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' }).format(date)
  const metadata = log.metadata

  async function downloadPng() {
    const node = document.getElementById(`daily-log-${index}`)
    if (!node) return
    const dataUrl = await toPng(node, { pixelRatio: 2, cacheBust: true, backgroundColor: '#ffffff' })
    const link = document.createElement('a')
    link.download = `driver-log-${log.date}.png`
    link.href = dataUrl
    link.click()
  }

  return (
    <article className="log-article">
      <div className="log-toolbar no-print">
        <div><strong>Log {index + 1}</strong><span>{dateText}</span></div>
        <button type="button" onClick={() => void downloadPng()}><Download size={16} aria-hidden="true" /> PNG</button>
      </div>
      <div className="log-sheet" id={`daily-log-${index}`} ref={ref}>
        <img src="/blank-paper-log.png" alt="Driver daily log form" />
        <svg viewBox="0 0 513 518" aria-label={`Completed driver log for ${dateText}`}>
          <g className="log-fill log-fill-small">
            <text x="185" y="28" textAnchor="middle">{dateText}</text>
            <text x="69" y="50">{trimText(log.from, 31)}</text>
            <text x="275" y="50">{trimText(log.to, 31)}</text>
            <text x="87" y="100" textAnchor="middle">{log.total_miles}</text>
            <text x="174" y="100" textAnchor="middle">{Math.round(log.total_miles)}</text>
            <text x="340" y="79" textAnchor="middle">{trimText(metadata.carrier_name || '', 34)}</text>
            <text x="340" y="102" textAnchor="middle">{trimText(metadata.carrier_address || '', 34)}</text>
            <text x="340" y="124" textAnchor="middle">{trimText(metadata.carrier_address || '', 34)}</text>
            <text x="134" y="126" textAnchor="middle">{trimText(metadata.vehicle_numbers || '', 23)}</text>
          </g>
          <path d={path} className="log-duty-line" />
          <g className="log-totals">
            <text x="477" y="182">{formatHours(displayTotals.off_duty)}</text>
            <text x="477" y="202">{formatHours(displayTotals.sleeper)}</text>
            <text x="477" y="222">{formatHours(displayTotals.driving)}</text>
            <text x="477" y="242">{formatHours(displayTotals.on_duty)}</text>
            <text x="477" y="287">24</text>
          </g>
          <text className="log-fill log-fill-small" x="72" y="368">{trimText(metadata.shipping_document || '', 26)}</text>
          <g className="log-remarks">
            {log.remarks.slice(0, 7).map((remark, remarkIndex) => (
              <text key={`${remark.time}-${remarkIndex}`} x="72" y={302 + remarkIndex * 11}>
                {remark.time}  {trimText(remark.text, 66)}
              </text>
            ))}
          </g>
          {metadata.driver_name && <text className="log-signature" x="381" y="146" textAnchor="middle">{metadata.driver_name}</text>}
        </svg>
      </div>
    </article>
  )
})

function trimText(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

function formatHours(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, '')
}
