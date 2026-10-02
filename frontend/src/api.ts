import type { ApiErrorShape, LocationResult, TripPlan, TripPlanRequest } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const apiError = data as ApiErrorShape | null
    const rawMessage = apiError?.error?.message
    const message =
      typeof rawMessage === 'string'
        ? rawMessage
        : rawMessage
          ? Object.values(rawMessage).flat().join(' ')
          : 'The request could not be completed.'
    throw new ApiError(apiError?.error?.code || 'request_error', message)
  }
  return data as T
}

export async function searchLocations(query: string, signal?: AbortSignal): Promise<LocationResult[]> {
  const response = await fetch(`${API_BASE}/api/v1/locations?q=${encodeURIComponent(query)}`, { signal })
  const data = await parseResponse<{ results: LocationResult[] }>(response)
  return data.results
}

export async function planTrip(payload: TripPlanRequest): Promise<TripPlan> {
  const response = await fetch(`${API_BASE}/api/v1/trips/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse<TripPlan>(response)
}
