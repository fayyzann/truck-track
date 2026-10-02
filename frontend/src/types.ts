import type { Feature, LineString } from 'geojson'

export type DutyStatus = 'off_duty' | 'sleeper' | 'driving' | 'on_duty'

export interface LocationResult {
  label: string
  coordinate: [number, number]
  provider_id: string
}

export interface LogMetadata {
  driver_name?: string
  carrier_name?: string
  carrier_address?: string
  vehicle_numbers?: string
  shipping_document?: string
}

export interface TripPlanRequest {
  current_location: string
  pickup_location: string
  dropoff_location: string
  cycle_hours_used: number
  departure_at: string
  terminal_timezone: string
  log_metadata: LogMetadata
}

export interface ScheduleEvent {
  status: DutyStatus
  reason: 'driving' | 'pickup' | 'dropoff' | 'fuel' | 'break' | 'sleeper' | 'cycle_restart'
  title: string
  start: string
  end: string
  duration_minutes: number
  start_mile: number
  end_mile: number
  distance_miles: number
  coordinate: [number, number]
  location: string
}

export interface LogSegment {
  status: DutyStatus
  start_minute: number
  end_minute: number
  duration_minutes: number
  label: string
}

export interface DailyLog {
  date: string
  from: string
  to: string
  total_miles: number
  segments: LogSegment[]
  totals: Record<DutyStatus, number>
  display_segments?: LogSegment[]
  display_totals?: Record<DutyStatus, number>
  remarks: Array<{ time: string; text: string }>
  metadata: LogMetadata
}

export interface TripPlan {
  route: {
    geojson: Feature<LineString>
    distance_miles: number
    duration_minutes: number
    locations: LocationResult[]
    legs: Array<{
      start: string
      end: string
      distance_miles: number
      duration_minutes: number
    }>
    instructions: Array<{
      leg_index: number
      instruction: string
      name: string
      distance_miles: number
      duration_minutes: number
    }>
  }
  events: ScheduleEvent[]
  stops: ScheduleEvent[]
  daily_logs: DailyLog[]
  compliance: {
    trip_start: string
    trip_end: string
    driving_hours: number
    on_duty_hours: number
    planned_rest_hours: number
    cycle_hours_at_completion: number
    cycle_restarts: number
    is_compliant: boolean
  }
  assumptions: string[]
  warnings: string[]
}

export interface ApiErrorShape {
  error: {
    code: string
    message: string | Record<string, string[]>
  }
}
