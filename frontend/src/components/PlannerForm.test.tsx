import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PlannerForm } from './PlannerForm'

describe('PlannerForm', () => {
  it('submits the four required trip inputs and departure context', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<PlannerForm loading={false} onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('Current location'), 'Chicago, IL')
    await user.type(screen.getByLabelText('Pickup location'), 'St. Louis, MO')
    await user.type(screen.getByLabelText('Drop-off location'), 'Dallas, TX')
    const cycle = screen.getByLabelText('Cycle used')
    await user.clear(cycle)
    await user.type(cycle, '18.35')
    expect(cycle).toBeValid()
    await user.click(screen.getByRole('button', { name: 'Plan compliant trip' }))

    expect(onSubmit).toHaveBeenCalledOnce()
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      current_location: 'Chicago, IL',
      pickup_location: 'St. Louis, MO',
      dropoff_location: 'Dallas, TX',
      cycle_hours_used: 18.35,
    })
    expect(onSubmit.mock.calls[0][0].departure_at).toMatch(/Z$/)
    expect(onSubmit.mock.calls[0][0].terminal_timezone).toBeTruthy()
  })

  it('disables planning while a request is in progress', () => {
    render(<PlannerForm loading onSubmit={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Building plan…' })).toBeDisabled()
  })
})
