import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { TripPlan } from '../types'
import { RouteDirections } from './RouteDirections'

const route: TripPlan['route'] = {
  geojson: {
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: [[-87.63, 41.88], [-96.8, 32.78]] },
    properties: {},
  },
  distance_miles: 920,
  duration_minutes: 900,
  locations: [],
  legs: [
    {
      start: 'Chicago, IL',
      end: 'St. Louis, MO',
      distance_miles: 297,
      duration_minutes: 285,
    },
    {
      start: 'St. Louis, MO',
      end: 'Dallas, TX',
      distance_miles: 623,
      duration_minutes: 615,
    },
  ],
  instructions: [
    {
      leg_index: 0,
      instruction: 'Head south on South Lake Shore Drive',
      name: 'South Lake Shore Drive',
      distance_miles: 7.4,
      duration_minutes: 11,
    },
    {
      leg_index: 1,
      instruction: 'Keep left toward Dallas',
      name: 'I-44 West',
      distance_miles: 291.2,
      duration_minutes: 260,
    },
  ],
}

describe('RouteDirections', () => {
  it('groups provider maneuvers by route leg', () => {
    render(<RouteDirections route={route} />)

    expect(screen.getByText('Turn-by-turn directions')).toBeInTheDocument()
    expect(screen.getByText('2 maneuvers')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Chicago, IL to St. Louis, MO' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'St. Louis, MO to Dallas, TX' })).toBeInTheDocument()
    expect(screen.getByText('Head south on South Lake Shore Drive')).toBeInTheDocument()
    expect(screen.getByText('Keep left toward Dallas')).toBeInTheDocument()
  })

  it('does not render an empty directions control', () => {
    const { container } = render(
      <RouteDirections route={{ ...route, instructions: [] }} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
