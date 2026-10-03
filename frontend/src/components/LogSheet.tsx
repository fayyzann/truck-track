import { Download } from 'lucide-react'
import { exportLogPng } from '../logExport'
import { forwardRef } from 'react'
import type { DailyLog, DutyStatus } from '../types'

const ROW_Y: Record<DutyStatus, number> = {
  off_duty: 193,
  sleeper: 210,
  driving: 228,
  on_duty: 245,
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
  const remarkStep = Math.min(11, 96 / Math.max(1, log.remarks.length - 1))
  const remarkFontSize = Math.max(3.6, Math.min(5.5, remarkStep * 0.6))

  async function downloadPng() {
    const node = document.getElementById(`daily-log-${index}`)
    if (!node) return
    const dataUrl = await exportLogPng(node)
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
        <img src="/blank-paper-log.svg" alt="Driver daily log form" />
        <svg viewBox="0 0 513 518" aria-label={`Completed driver log for ${dateText}`}>
          {/* Export clones SVG children without copying their CSS. Keep all drawing styles inline. */}
          <g style={{ fill: '#112b44', fontFamily: 'Arial, sans-serif', fontWeight: 600, fontSize: 5.8 }}>
            <text x="187" y="17" textAnchor="middle">{String(date.getMonth() + 1).padStart(2, '0')}</text>
            <text x="229" y="17" textAnchor="middle">{String(date.getDate()).padStart(2, '0')}</text>
            <text x="272" y="17" textAnchor="middle">{date.getFullYear()}</text>
            <text x="88" y="44">{trimText(log.from, 31)}</text>
            <text x="278" y="44">{trimText(log.to, 31)}</text>
            <text x="94" y="79" textAnchor="middle">{log.total_miles}</text>
            <text x="178" y="79" textAnchor="middle">{Math.round(log.total_miles)}</text>
            <text x="347" y="76" textAnchor="middle">{trimText(metadata.carrier_name || '', 34)}</text>
            <text x="347" y="97" textAnchor="middle">{trimText(metadata.carrier_address || '', 34)}</text>
            <text x="134" y="113" textAnchor="middle">{trimText(metadata.vehicle_numbers || '', 23)}</text>
          </g>
          <path d={path} style={{ fill: 'none', stroke: '#0879b5', strokeWidth: 2, strokeLinecap: 'square', strokeLinejoin: 'miter' }} />
          <g style={{ fill: '#102a43', fontFamily: 'Arial, sans-serif', fontWeight: 700, fontSize: 7 }} textAnchor="middle">
            <text x="480" y="198">{formatHours(displayTotals.off_duty)}</text>
            <text x="480" y="215">{formatHours(displayTotals.sleeper)}</text>
            <text x="480" y="233">{formatHours(displayTotals.driving)}</text>
            <text x="480" y="250">{formatHours(displayTotals.on_duty)}</text>
            <text x="480" y="281">24</text>
          </g>
          <text style={{ fill: '#112b44', fontFamily: 'Arial, sans-serif', fontSize: 5.8 }} x="25" y="350">{trimText(metadata.shipping_document || '', 18)}</text>
          <g style={{ fill: '#102a43', fontFamily: 'Arial, sans-serif', fontWeight: 500, fontSize: remarkFontSize }}>
            {log.remarks.map((remark, remarkIndex) => (
              <text key={`${remark.time}-${remarkIndex}`} x="100" y={302 + remarkIndex * remarkStep}>
                {remark.time}  {trimText(remark.text, 66)}
              </text>
            ))}
          </g>
          {metadata.driver_name && <text style={{ fill: '#102a43', fontFamily: 'Arial, sans-serif', fontSize: 7 }} x="347" y="142" textAnchor="middle">Driver: {trimText(metadata.driver_name, 34)}</text>}
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
