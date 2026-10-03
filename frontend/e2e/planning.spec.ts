import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import JSZip from 'jszip'

const event = (status: string, reason: string, title: string, start: string, end: string) => ({
  status,
  reason,
  title,
  start,
  end,
  duration_minutes: (new Date(end).getTime() - new Date(start).getTime()) / 60000,
  start_mile: 0,
  end_mile: status === 'driving' ? 200 : 0,
  distance_miles: status === 'driving' ? 200 : 0,
  coordinate: [-96.8, 32.78],
  location: reason === 'pickup' ? 'St. Louis, MO' : 'Dallas, TX',
})

const planResponse = {
  route: {
    geojson: {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[-87.63, 41.88], [-90.2, 38.63], [-96.8, 32.78]] },
      properties: {},
    },
    distance_miles: 920,
    duration_minutes: 900,
    locations: [
      { label: 'Chicago, IL', coordinate: [-87.63, 41.88], provider_id: '1' },
      { label: 'St. Louis, MO', coordinate: [-90.2, 38.63], provider_id: '2' },
      { label: 'Dallas, TX', coordinate: [-96.8, 32.78], provider_id: '3' },
    ],
    legs: [],
    instructions: [],
  },
  events: [
    event('driving', 'driving', 'Drive toward St. Louis, MO', '2026-01-05T14:00:00Z', '2026-01-05T19:00:00Z'),
    event('on_duty', 'pickup', 'Pickup service', '2026-01-05T19:00:00Z', '2026-01-05T20:00:00Z'),
    event('driving', 'driving', 'Drive toward Dallas, TX', '2026-01-05T20:00:00Z', '2026-01-06T02:00:00Z'),
    event('sleeper', 'sleeper', '10-hour sleeper period', '2026-01-06T02:00:00Z', '2026-01-06T12:00:00Z'),
    event('driving', 'driving', 'Drive toward Dallas, TX', '2026-01-06T12:00:00Z', '2026-01-06T16:00:00Z'),
    event('on_duty', 'dropoff', 'Drop-off service', '2026-01-06T16:00:00Z', '2026-01-06T17:00:00Z'),
  ],
  stops: [],
  daily_logs: [
    {
      date: '2026-01-05', from: 'Chicago, IL', to: 'En route', total_miles: 672,
      segments: [
        { status: 'off_duty', start_minute: 0, end_minute: 480, duration_minutes: 480, label: 'Off duty' },
        { status: 'driving', start_minute: 480, end_minute: 780, duration_minutes: 300, label: 'Driving' },
        { status: 'on_duty', start_minute: 780, end_minute: 840, duration_minutes: 60, label: 'Pickup' },
        { status: 'driving', start_minute: 840, end_minute: 1200, duration_minutes: 360, label: 'Driving' },
        { status: 'sleeper', start_minute: 1200, end_minute: 1440, duration_minutes: 240, label: 'Sleeper' },
      ],
      totals: { off_duty: 8, sleeper: 4, driving: 11, on_duty: 1 },
      remarks: [{ time: '08:00', text: 'Driving — Chicago, IL' }, { time: '13:00', text: 'Pickup service — St. Louis, MO' }],
      metadata: { driver_name: 'Alex Morgan', carrier_name: 'Northstar Freight', carrier_address: '123 Main Street', vehicle_numbers: 'ABC123', shipping_document: 'LOAD-123' },
    },
    {
      date: '2026-01-06', from: 'En route', to: 'Dallas, TX', total_miles: 248,
      segments: [
        { status: 'sleeper', start_minute: 0, end_minute: 360, duration_minutes: 360, label: 'Sleeper' },
        { status: 'driving', start_minute: 360, end_minute: 600, duration_minutes: 240, label: 'Driving' },
        { status: 'on_duty', start_minute: 600, end_minute: 660, duration_minutes: 60, label: 'Drop-off' },
        { status: 'off_duty', start_minute: 660, end_minute: 1440, duration_minutes: 780, label: 'Off duty' },
      ],
      totals: { off_duty: 13, sleeper: 6, driving: 4, on_duty: 1 }, remarks: [], metadata: {},
    },
  ],
  compliance: {
    trip_start: '2026-01-05T14:00:00Z', trip_end: '2026-01-06T17:00:00Z', driving_hours: 15,
    on_duty_hours: 17, planned_rest_hours: 10, cycle_hours_at_completion: 35.5, cycle_restarts: 0,
    is_compliant: true,
  },
  assumptions: [],
  warnings: ['Planned stops are approximate route positions.'],
}

test('iPhone-size form keeps all controls inside the visible rail', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 440, height: 956 })
  await page.route('**/api/v1/locations**', (route) => route.fulfill({ json: { results: [] } }))
  await page.goto('/')
  await page.getByLabel('Current location').fill('Chicago, IL, USA')
  await page.getByLabel('Pickup location').fill('Housten Cemetery, Collin County, TX, USA')
  await page.getByLabel('Drop-off location').fill('Austin, TX, USA')
  await page.getByLabel('Cycle used').fill('20')
  await page.getByLabel('Departure').fill('2026-10-10T12:00')
  for (const label of ['Current location', 'Pickup location', 'Drop-off location', 'Cycle used', 'Departure']) {
    await page.getByLabel(label).focus()
    const metrics = await page.locator('.planner-form').evaluate((node) => ({
      width: node.clientWidth, scrollWidth: node.scrollWidth, scrollLeft: node.scrollLeft,
    }))
    expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.width)
    expect(metrics.scrollLeft).toBe(0)
  }
  await page.getByRole('button', { name: 'Plan compliant trip' }).scrollIntoViewIfNeeded()
  await expect(page.getByRole('button', { name: 'Plan compliant trip' })).toBeInViewport()
  await page.locator('.planning-rail').screenshot({ path: testInfo.outputPath('iphone-form.png') })
})

test('location suggestions cover later fields and remain selectable', async ({ page }) => {
  await page.route('**/api/v1/locations**', (route) => route.fulfill({ json: { results: [
    { label: 'Chicago, IL, USA', coordinate: [-87.63, 41.88], provider_id: 'chicago' },
    { label: 'Chicago Heights, IL, USA', coordinate: [-87.63, 41.5], provider_id: 'heights' },
    { label: 'Chicago Ridge, IL, USA', coordinate: [-87.78, 41.7], provider_id: 'ridge' },
    { label: 'Chicago Park, CA, USA', coordinate: [-120.97, 39.14], provider_id: 'park' },
    { label: 'Chicago, WI, USA', coordinate: [-88, 42], provider_id: 'wi' },
  ] } }))
  await page.goto('/')
  const input = page.getByLabel('Current location')
  await input.fill('chicago')
  await expect(page.getByRole('listbox')).toBeVisible()
  await expect(page.getByRole('option')).toHaveCount(5)
  const pickup = await page.getByLabel('Pickup location').boundingBox()
  expect(pickup).not.toBeNull()
  const dropdownIsOnTop = await page.evaluate(({ x, y }) => {
    return Boolean(document.elementFromPoint(x, y)?.closest('.suggestions'))
  }, { x: pickup!.x + 15, y: pickup!.y + 15 })
  expect(dropdownIsOnTop).toBe(true)
  await page.getByRole('option', { name: 'Chicago Heights, IL, USA', exact: true }).click()
  await expect(input).toHaveValue('Chicago Heights, IL, USA')
  await expect(page.getByRole('listbox')).toHaveCount(0)
})

test('fits narrow phones, tablets and desktop widths', async ({ page }) => {
  await page.route('**/api/v1/locations**', (route) => route.fulfill({ json: { results: [] } }))
  await page.route('**/api/v1/trips/plan', (route) => route.fulfill({ json: planResponse }))
  await page.goto('/')
  for (const width of [320, 390, 768, 1024, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
  await page.getByLabel('Current location').fill('Chicago, IL')
  await page.getByLabel('Pickup location').fill('St. Louis, MO')
  await page.getByLabel('Drop-off location').fill('Dallas, TX')
  await page.getByRole('button', { name: 'Plan compliant trip' }).click()
  await expect(page.locator('.log-sheet')).toHaveCount(2)
  for (const width of [320, 390, 768, 1024, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const button = page.getByRole('button', { name: 'Plan compliant trip' })
    expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(44)
  }
})

test('plans a trip and renders multi-day logs', async ({ page }, testInfo) => {
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(message.text())
  })
  await page.route('**/api/v1/locations**', (route) => route.fulfill({ json: { results: [] } }))
  await page.route('**/api/v1/trips/plan', (route) => route.fulfill({ json: planResponse }))
  await page.goto('/')

  await page.getByLabel('Current location').fill('Chicago, IL')
  await page.getByLabel('Pickup location').fill('St. Louis, MO')
  await page.getByLabel('Drop-off location').fill('Dallas, TX')
  await page.getByLabel('Cycle used').fill('18.5')
  await page.getByRole('button', { name: 'Plan compliant trip' }).click()

  await expect(page.getByRole('heading', { name: /Chicago, IL to Dallas, TX/ })).toBeVisible()
  await expect(page.getByText('Compliant plan')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Daily log sheets' })).toBeVisible()
  await expect(page.locator('.log-sheet')).toHaveCount(2)
  await expect(page).toHaveScreenshot('planned-trip.png', {
    fullPage: true,
    animations: 'disabled',
    maxDiffPixelRatio: 0.02,
  })
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'PNG', exact: true }).first().click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('driver-log-2026-01-05.png')
  const outputPath = testInfo.outputPath('exported-log.png')
  await download.saveAs(outputPath)
  const png = await readFile(outputPath)
  expect(png.readUInt32BE(16)).toBe(2052)
  expect(png.readUInt32BE(20)).toBe(2072)
  expect(png).toMatchSnapshot('exported-log.png', { maxDiffPixelRatio: 0.01 })

  // Verify the actual raster contains the blue duty line, not an unstyled black polygon.
  const bluePixels = await page.evaluate(async (dataUrl) => {
    const img = new Image()
    img.src = dataUrl
    await img.decode()
    const canvas = document.createElement('canvas')
    canvas.width = img.width
    canvas.height = img.height
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(img, 0, 0)
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data
    let blue = 0
    for (let i = 0; i < pixels.length; i += 4) {
      if (pixels[i] < 40 && pixels[i + 1] > 90 && pixels[i + 1] < 150 && pixels[i + 2] > 150) blue++
    }
    return blue
  }, `data:image/png;base64,${png.toString('base64')}`)
  expect(bluePixels).toBeGreaterThan(500)

  const zipPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download all PNGs' }).click()
  const zipDownload = await zipPromise
  const zipPath = testInfo.outputPath('daily-logs.zip')
  await zipDownload.saveAs(zipPath)
  const zip = await JSZip.loadAsync(await readFile(zipPath))
  expect(Object.keys(zip.files)).toEqual(['driver-log-2026-01-05.png', 'driver-log-2026-01-06.png'])
  expect(await zip.file('driver-log-2026-01-05.png')!.async('nodebuffer')).toEqual(png)
  expect(browserErrors).toEqual([])
})
