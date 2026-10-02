import {
  AttributionControl,
  LngLatBounds,
  Map,
  Marker,
  NavigationControl,
  Popup,
  setWorkerUrl,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useEffect, useRef } from 'react'
import type { TripPlan } from '../types'

setWorkerUrl(workerUrl)

interface RouteMapProps {
  plan?: TripPlan
}

export function RouteMap({ plan }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const map = new Map({
      container: containerRef.current,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: [-98.5, 39.5],
      zoom: 3.1,
      attributionControl: false,
    })
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right')

    if (plan) {
      map.on('load', () => {
        map.addSource('truck-route', { type: 'geojson', data: plan.route.geojson })
        map.addLayer({
          id: 'truck-route-shadow',
          type: 'line',
          source: 'truck-route',
          paint: { 'line-color': '#ffffff', 'line-width': 8, 'line-opacity': 0.9 },
        })
        map.addLayer({
          id: 'truck-route',
          type: 'line',
          source: 'truck-route',
          paint: { 'line-color': '#147dad', 'line-width': 5 },
        })

        const bounds = new LngLatBounds()
        for (const coordinate of plan.route.geojson.geometry.coordinates) {
          bounds.extend(coordinate as [number, number])
        }
        map.fitBounds(bounds, { padding: 70, maxZoom: 11, duration: 0 })

        plan.route.locations.forEach((location, index) => {
          const element = document.createElement('div')
          element.className = `route-pin route-pin-${index}`
          element.textContent = String(index + 1)
          element.setAttribute('aria-label', location.label)
          new Marker({ element })
            .setLngLat(location.coordinate)
            .setPopup(new Popup({ offset: 18 }).setText(location.label))
            .addTo(map)
        })

        plan.stops
          .filter((stop) => !['pickup', 'dropoff'].includes(stop.reason))
          .forEach((stop) => {
            const element = document.createElement('div')
            element.className = `stop-pin stop-pin-${stop.reason}`
            element.title = stop.title
            const popupContent = document.createElement('div')
            const title = document.createElement('strong')
            title.textContent = stop.title
            popupContent.append(title, document.createElement('br'), document.createTextNode(stop.location))
            new Marker({ element })
              .setLngLat(stop.coordinate)
              .setPopup(new Popup({ offset: 12 }).setDOMContent(popupContent))
              .addTo(map)
          })
      })
    }

    return () => map.remove()
  }, [plan])

  return <div className="route-map" ref={containerRef} aria-label="Trip route map" />
}
