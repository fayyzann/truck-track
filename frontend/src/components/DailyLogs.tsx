import { Download, Printer } from 'lucide-react'
import { exportLogPng } from '../logExport'
import JSZip from 'jszip'
import { useRef } from 'react'
import type { DailyLog } from '../types'
import { LogSheet } from './LogSheet'

export function DailyLogs({ logs }: { logs: DailyLog[] }) {
  const refs = useRef<Array<HTMLDivElement | null>>([])

  async function downloadAll() {
    const zip = new JSZip()
    for (let index = 0; index < refs.current.length; index += 1) {
      const node = refs.current[index]
      if (!node) continue
      const dataUrl = await exportLogPng(node)
      zip.file(`driver-log-${logs[index].date}.png`, dataUrl.split(',')[1], { base64: true })
    }
    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'trucktrack-daily-logs.zip'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="logs-section" aria-labelledby="logs-heading">
      <div className="section-heading-row no-print">
        <div>
          <p className="section-kicker">Record of duty status</p>
          <h2 id="logs-heading">Daily log sheets</h2>
        </div>
        <div className="log-actions">
          <button type="button" onClick={() => window.print()}><Printer size={17} aria-hidden="true" /> Print / save PDF</button>
          <button type="button" onClick={() => void downloadAll()}><Download size={17} aria-hidden="true" /> Download all PNGs</button>
        </div>
      </div>
      <div className="log-stack">
        {logs.map((log, index) => (
          <LogSheet
            key={log.date}
            log={log}
            index={index}
            ref={(node) => { refs.current[index] = node }}
          />
        ))}
      </div>
    </section>
  )
}
