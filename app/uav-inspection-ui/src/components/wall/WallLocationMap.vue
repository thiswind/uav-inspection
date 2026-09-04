<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

interface LocationPoint {
  id: string
  latitude: number
  longitude: number
  time: number
  label: string
  color: string
}

const props = defineProps<{
  points: LocationPoint[]
  current: { latitude: number; longitude: number } | null
}>()

const containerRef = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let overlay: L.LayerGroup | null = null
let resizeObserver: ResizeObserver | null = null

function renderPoints() {
  if (!map || !overlay) return
  overlay.clearLayers()
  const bounds: L.LatLngExpression[] = []

  if (props.points.length > 1) {
    const route = props.points.map((point) => [point.latitude, point.longitude] as L.LatLngTuple)
    L.polyline(route, { color: '#0f766e', weight: 3, opacity: 0.8 }).addTo(overlay)
  }
  for (const point of props.points) {
    const coordinate: L.LatLngTuple = [point.latitude, point.longitude]
    bounds.push(coordinate)
    L.circleMarker(coordinate, {
      radius: 7,
      color: '#ffffff',
      weight: 2,
      fillColor: point.color,
      fillOpacity: 0.95,
    }).bindTooltip(`${point.label} · ${point.time.toFixed(1)}s`).addTo(overlay)
  }
  if (props.current) {
    const coordinate: L.LatLngTuple = [props.current.latitude, props.current.longitude]
    bounds.push(coordinate)
    L.circleMarker(coordinate, {
      radius: 10,
      color: '#0f172a',
      weight: 3,
      fillColor: '#22d3ee',
      fillOpacity: 1,
    }).bindTooltip('无人机当前位置').addTo(overlay)
  }

  if (bounds.length > 1) map.fitBounds(L.latLngBounds(bounds), { padding: [36, 36], maxZoom: 19 })
  else if (bounds.length === 1) map.setView(bounds[0], 18)
}

onMounted(async () => {
  await nextTick()
  if (!containerRef.value) return
  map = L.map(containerRef.value, { zoomControl: true, attributionControl: true }).setView([24.8334, 102.8399], 16)
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 20,
    attribution: 'Esri World Imagery',
  }).addTo(map)
  overlay = L.layerGroup().addTo(map)
  resizeObserver = new ResizeObserver(() => map?.invalidateSize())
  resizeObserver.observe(containerRef.value)
  renderPoints()
})

watch(() => [props.points, props.current], renderPoints, { deep: true })

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  map?.remove()
  map = null
})
</script>

<template>
  <div ref="containerRef" class="h-full min-h-[540px] w-full bg-slate-100"></div>
</template>

<style scoped>
:deep(.leaflet-container) {
  font-family: "Microsoft YaHei", sans-serif;
}
</style>
