<template>
  <div class="relative w-full h-full rounded-xl overflow-hidden shadow-inner group">
    <div ref="mapContainer" class="w-full h-full z-0 bg-slate-100"></div>

    <div class="absolute bottom-4 right-4 z-[400] flex flex-col bg-white/80 backdrop-blur-xl border border-white shadow-[0_4px_15px_-3px_rgba(14,165,233,0.2)] rounded-lg overflow-hidden opacity-85 group-hover:opacity-100 transition-opacity">
      <button @click="zoomIn" class="w-8 h-8 flex items-center justify-center text-slate-600 hover:text-cyan-600 hover:bg-cyan-50/50 transition-colors" title="放大">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
      </button>
      <div class="h-px w-full bg-gradient-to-r from-transparent via-slate-200 to-transparent"></div>
      <button @click="zoomOut" class="w-8 h-8 flex items-center justify-center text-slate-600 hover:text-cyan-600 hover:bg-cyan-50/50 transition-colors" title="缩小">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" /></svg>
      </button>
    </div>

    <div class="absolute bottom-1 left-2 z-[400] pointer-events-none">
      <span class="text-[9px] text-slate-500/70 font-mono tracking-wider">AERO INTEL GEO SYSTEM</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet.heat'
import type { TrackTarget } from '../../../types/patrol'

const props = defineProps<{
  targets: TrackTarget[]
  center: [number, number]
  zoom: number
  showBaseLayer?: boolean
  showHeatLayer?: boolean
}>()

const mapContainer = ref<HTMLElement | null>(null)
const mapInstance = shallowRef<L.Map | null>(null)
const heatLayer = shallowRef<L.HeatLayer | null>(null)
const baseLayer = shallowRef<L.TileLayer | null>(null)

const zoomIn = () => mapInstance.value?.zoomIn()
const zoomOut = () => mapInstance.value?.zoomOut()

function updateHeatLayer(targets: TrackTarget[]) {
  if (!heatLayer.value) return
  const heatPoints = targets
    .filter((target) => target.geoLat !== undefined && target.geoLon !== undefined)
    .map((target) => [target.geoLat as number, target.geoLon as number, 1] as L.HeatLatLngTuple)
  heatLayer.value.setLatLngs(heatPoints)
}

onMounted(() => {
  if (!mapContainer.value) return

  mapInstance.value = L.map(mapContainer.value, {
    zoomControl: false,
    attributionControl: false,
  }).setView(props.center, props.zoom)

  baseLayer.value = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: '',
    errorTileUrl: 'https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
  })

  heatLayer.value = L.heatLayer([], {
    radius: 28,
    blur: 20,
    maxZoom: 17,
    gradient: { 0.4: '#0ea5e9', 0.6: '#06b6d4', 0.75: '#10b981', 0.9: '#f59e0b', 1: '#ef4444' },
  })

  if (props.showBaseLayer !== false) {
    baseLayer.value.addTo(mapInstance.value)
  }
  if (props.showHeatLayer !== false) {
    heatLayer.value.addTo(mapInstance.value)
    updateHeatLayer(props.targets)
  }
})

watch(() => props.targets, (targets) => {
  if (props.showHeatLayer === false) return
  updateHeatLayer(targets)
}, { deep: true })

watch(() => props.center, (center) => {
  mapInstance.value?.setView(center, mapInstance.value.getZoom(), { animate: false })
}, { deep: true })

watch(() => props.zoom, (zoom) => {
  mapInstance.value?.setZoom(zoom, { animate: false })
})

watch(() => props.showBaseLayer, (show) => {
  if (!mapInstance.value || !baseLayer.value) return
  if (show === false) baseLayer.value.remove()
  else baseLayer.value.addTo(mapInstance.value)
})

watch(() => props.showHeatLayer, (show) => {
  if (!mapInstance.value || !heatLayer.value) return
  if (show === false) {
    heatLayer.value.remove()
    return
  }
  heatLayer.value.addTo(mapInstance.value)
  updateHeatLayer(props.targets)
})

onUnmounted(() => {
  mapInstance.value?.remove()
  mapInstance.value = null
})
</script>

<style scoped>
:deep(.leaflet-container) {
  z-index: 10 !important;
  background-color: #1e293b !important;
}
</style>
