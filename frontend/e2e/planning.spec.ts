import { expect, test } from '@playwright/test'

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
      totals: { off_duty: 8, sleeper: 4, driving: 11, on_duty: 1 }, remarks: [], metadata: {},
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

test('plans a trip and renders multi-day logs', async ({ page }) => {
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
  expect(browserErrors).toEqual([])
})
