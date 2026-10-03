import { toPng } from 'html-to-image'

// Export at a consistent resolution, independent of the viewport or mobile screen.
export function exportLogPng(node: HTMLElement) {
  return toPng(node, {
    canvasWidth: 1026,
    canvasHeight: 1036,
    style: { boxShadow: 'none' },
    pixelRatio: 2,
    cacheBust: true,
    backgroundColor: '#ffffff',
  })
}
