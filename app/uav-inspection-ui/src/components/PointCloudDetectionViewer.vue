<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js'
import type { PointCloudScene, TreeMeasurement } from '../api1/vegetation'

const props = defineProps<{
  sceneData: PointCloudScene | null
  detections: TreeMeasurement[]
  showDetections: boolean
  selectedTreeId: number | null
  viewMode: 'boxes' | 'single'
  pointSize: number
  colorMode?: 'rgb' | 'green'
}>()

const emit = defineEmits<{
  loaded: [points: number]
  error: [message: string]
  selectTree: [treeId: number]
}>()

const container = ref<HTMLDivElement | null>(null)
const loading = ref(false)
const progress = ref(0)
const pointCount = ref(0)
const selectedTree = computed(() => props.detections.find((tree) => tree.tree_id === props.selectedTreeId) ?? null)

let renderer: THREE.WebGLRenderer | null = null
let threeScene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let pointCloud: THREE.Points | null = null
let singleTreeCloud: THREE.Points | null = null
let detectionGroup: THREE.Group | null = null
let grid: THREE.GridHelper | null = null
let resizeObserver: ResizeObserver | null = null
let animationFrame = 0
let loadVersion = 0
let pointerStart: { x: number; y: number } | null = null

function disposeObject(object: THREE.Object3D | null) {
  if (!object) return
  object.traverse((child) => {
    const mesh = child as THREE.Mesh
    mesh.geometry?.dispose()
    if (Array.isArray(mesh.material)) mesh.material.forEach((material) => material.dispose())
    else mesh.material?.dispose()
  })
  object.removeFromParent()
}

function localBounds(tree: TreeMeasurement) {
  const origin = props.sceneData?.origin
  if (!origin) return null
  return new THREE.Box3(
    new THREE.Vector3(tree.x_min - origin.x, tree.y_min - origin.y, tree.z_min - origin.z),
    new THREE.Vector3(tree.x_max - origin.x, tree.y_max - origin.y, tree.z_max - origin.z),
  )
}

function sceneBox() {
  const bounds = props.sceneData?.local_bounds
  if (!bounds) return null
  return new THREE.Box3(
    new THREE.Vector3(bounds.minx, bounds.miny, bounds.minz),
    new THREE.Vector3(bounds.maxx, bounds.maxy, bounds.maxz),
  )
}

function fitCamera(box: THREE.Box3, padding = 1.1) {
  if (!camera || !controls) return
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const span = Math.max(size.x, size.y, size.z * 2, 10)
  camera.near = Math.max(span / 1000, 0.02)
  camera.far = span * 30
  camera.position.set(center.x + span * 0.72 * padding, center.y - span * 0.92 * padding, center.z + span * 0.72 * padding)
  camera.up.set(0, 0, 1)
  camera.updateProjectionMatrix()
  controls.target.copy(center)
  controls.minDistance = span * 0.03
  controls.maxDistance = span * 8
  controls.update()
}

function resetView() {
  const box = props.viewMode === 'single' && selectedTree.value ? localBounds(selectedTree.value) : sceneBox()
  if (box) fitCamera(box)
}

function resize() {
  if (!container.value || !renderer || !camera) return
  const { width, height } = container.value.getBoundingClientRect()
  if (!width || !height) return
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}

function buildGrid() {
  if (!threeScene || !props.sceneData) return
  disposeObject(grid)
  const bounds = props.sceneData.local_bounds
  const span = Math.max(bounds.maxx - bounds.minx, bounds.maxy - bounds.miny)
  grid = new THREE.GridHelper(span * 1.25, 12, 0x35536d, 0x1a3144)
  grid.rotation.x = Math.PI / 2
  grid.position.z = bounds.minz
  ;(grid.material as THREE.LineBasicMaterial).transparent = true
  ;(grid.material as THREE.LineBasicMaterial).opacity = 0.5
  threeScene.add(grid)
}

function rebuildBoxes() {
  if (!threeScene) return
  disposeObject(detectionGroup)
  detectionGroup = new THREE.Group()
  detectionGroup.name = 'tree-detection-boxes'
  if (props.showDetections && props.viewMode === 'boxes') {
    for (const tree of props.detections) {
      const bounds = localBounds(tree)
      if (!bounds) continue
      const selected = tree.tree_id === props.selectedTreeId
      const helper = new THREE.Box3Helper(bounds, selected ? 0xfbbf24 : 0x2dd4bf)
      helper.userData.treeId = tree.tree_id
      const material = helper.material as THREE.LineBasicMaterial
      material.transparent = true
      material.opacity = selected ? 1 : 0.78
      detectionGroup.add(helper)
    }
  }
  threeScene.add(detectionGroup)
}

function rebuildSingleTree() {
  if (!threeScene || !pointCloud) return
  disposeObject(singleTreeCloud)
  singleTreeCloud = null
  const tree = selectedTree.value
  const bounds = tree ? localBounds(tree) : null
  if (props.viewMode !== 'single' || !bounds) {
    pointCloud.visible = true
    if (grid) grid.visible = true
    return
  }

  const source = pointCloud.geometry
  const positions = source.getAttribute('position')
  const colors = source.getAttribute('color')
  const selectedPositions: number[] = []
  const selectedColors: number[] = []
  for (let index = 0; index < positions.count; index += 1) {
    const x = positions.getX(index)
    const y = positions.getY(index)
    const z = positions.getZ(index)
    if (x < bounds.min.x || x > bounds.max.x || y < bounds.min.y || y > bounds.max.y || z < bounds.min.z || z > bounds.max.z) continue
    selectedPositions.push(x, y, z)
    if (colors) selectedColors.push(colors.getX(index), colors.getY(index), colors.getZ(index))
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(selectedPositions, 3))
  if (selectedColors.length) geometry.setAttribute('color', new THREE.Float32BufferAttribute(selectedColors, 3))
  const material = new THREE.PointsMaterial({
    size: Math.max(props.pointSize * 1.7, 0.18),
    sizeAttenuation: true,
    vertexColors: Boolean(selectedColors.length),
    color: selectedColors.length ? 0xffffff : 0x34d399,
  })
  singleTreeCloud = new THREE.Points(geometry, material)
  singleTreeCloud.name = 'selected-tree-points'
  threeScene.add(singleTreeCloud)
  pointCloud.visible = false
  if (grid) grid.visible = false
  fitCamera(bounds, 1.25)
}

function updatePointSize() {
  if (pointCloud) (pointCloud.material as THREE.PointsMaterial).size = props.pointSize
  if (singleTreeCloud) (singleTreeCloud.material as THREE.PointsMaterial).size = Math.max(props.pointSize * 1.7, 0.18)
}

function gaussianScore(features: number[], classId: number) {
  const model = props.sceneData?.green_model
  if (!model) return Number.NEGATIVE_INFINITY
  let score = Math.log(Math.max(model.priors[classId] ?? 0, 1e-12))
  for (let index = 0; index < features.length; index += 1) {
    const variance = Math.max(model.variances[classId]?.[index] ?? 0, 1e-6)
    const difference = features[index] - (model.means[classId]?.[index] ?? 0)
    score += -0.5 * (Math.log(2 * Math.PI * variance) + difference * difference / variance)
  }
  return score
}

function applyPointColors() {
  if (!pointCloud) return
  const geometry = pointCloud.geometry
  const colorAttribute = geometry.getAttribute('color')
  if (!colorAttribute) return
  let original = geometry.userData.originalColors as Float32Array | undefined
  if (!original || original.length !== colorAttribute.count * 3) {
    original = new Float32Array(colorAttribute.count * 3)
    for (let index = 0; index < colorAttribute.count; index += 1) {
      const offset = index * 3
      original[offset] = colorAttribute.getX(index)
      original[offset + 1] = colorAttribute.getY(index)
      original[offset + 2] = colorAttribute.getZ(index)
    }
    geometry.userData.originalColors = original
  }
  if (props.colorMode !== 'green' || !props.sceneData?.green_model) {
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(original.slice(), 3))
    return
  }

  const model = props.sceneData.green_model
  const thresholdLogit = Math.log(model.probability_threshold / (1 - model.probability_threshold))
  const colors = new Float32Array(original.length)
  for (let offset = 0; offset < original.length; offset += 3) {
    const red = original[offset]
    const green = original[offset + 1]
    const blue = original[offset + 2]
    const total = red + green + blue + 1e-6
    const redRatio = red / total
    const greenRatio = green / total
    const blueRatio = blue / total
    const maximum = Math.max(red, green, blue)
    const minimum = Math.min(red, green, blue)
    const features = [
      redRatio,
      greenRatio,
      blueRatio,
      2 * greenRatio - redRatio - blueRatio,
      (green - red) / (green + red + 1e-6),
      (green - blue) / (green + blue + 1e-6),
      (red + green + blue) / 3,
      (maximum - minimum) / (maximum + 1e-6),
    ]
    const isGreen = gaussianScore(features, 1) - gaussianScore(features, 0) >= thresholdLogit
    if (isGreen) {
      colors[offset] = red * 0.25 + 0.06
      colors[offset + 1] = green * 0.35 + 0.64
      colors[offset + 2] = blue * 0.2 + 0.08
    } else {
      const luminance = red * 0.22 + green * 0.62 + blue * 0.16
      colors[offset] = luminance * 0.42
      colors[offset + 1] = luminance * 0.48
      colors[offset + 2] = luminance * 0.54
    }
  }
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
}

function loadPointCloud() {
  if (!props.sceneData || !threeScene) return
  const version = ++loadVersion
  loading.value = true
  progress.value = 0
  pointCount.value = 0
  disposeObject(pointCloud)
  disposeObject(singleTreeCloud)
  pointCloud = null
  singleTreeCloud = null
  rebuildBoxes()
  buildGrid()

  new PLYLoader().load(
    props.sceneData.point_cloud_url,
    (geometry) => {
      if (version !== loadVersion || !threeScene) {
        geometry.dispose()
        return
      }
      const sourcePositions = geometry.getAttribute('position')
      if (!(sourcePositions.array instanceof Float32Array)) {
        const positions = new Float32Array(sourcePositions.count * 3)
        for (let index = 0; index < sourcePositions.count; index += 1) {
          const offset = index * 3
          positions[offset] = sourcePositions.getX(index)
          positions[offset + 1] = sourcePositions.getY(index)
          positions[offset + 2] = sourcePositions.getZ(index)
        }
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      }
      geometry.computeBoundingBox()
      const hasColors = Boolean(geometry.getAttribute('color'))
      const material = new THREE.PointsMaterial({
        size: props.pointSize,
        sizeAttenuation: true,
        vertexColors: hasColors,
        color: hasColors ? 0xffffff : 0x8dd3b5,
      })
      pointCloud = new THREE.Points(geometry, material)
      pointCloud.name = 'full-site-point-cloud'
      threeScene.add(pointCloud)
      applyPointColors()
      pointCount.value = geometry.getAttribute('position').count
      loading.value = false
      progress.value = 100
      resetView()
      rebuildSingleTree()
      emit('loaded', pointCount.value)
    },
    (event) => {
      if (event.total) progress.value = Math.min(99, Math.round(event.loaded / event.total * 100))
    },
    (error) => {
      if (version !== loadVersion) return
      loading.value = false
      emit('error', error instanceof Error ? error.message : '点云加载失败')
    },
  )
}

function selectNearestTree(event: PointerEvent) {
  if (!camera || !renderer || !props.showDetections || props.viewMode !== 'boxes' || !props.detections.length) return
  const rect = renderer.domElement.getBoundingClientRect()
  const pointer = new THREE.Vector2(event.clientX - rect.left, event.clientY - rect.top)
  let nearestId: number | null = null
  let nearestDistance = 24
  for (const tree of props.detections) {
    const bounds = localBounds(tree)
    if (!bounds) continue
    const projected = bounds.getCenter(new THREE.Vector3()).project(camera)
    if (projected.z < -1 || projected.z > 1) continue
    const x = (projected.x * 0.5 + 0.5) * rect.width
    const y = (-projected.y * 0.5 + 0.5) * rect.height
    const distance = Math.hypot(pointer.x - x, pointer.y - y)
    if (distance < nearestDistance) {
      nearestDistance = distance
      nearestId = tree.tree_id
    }
  }
  if (nearestId !== null) emit('selectTree', nearestId)
}

function onPointerDown(event: PointerEvent) {
  pointerStart = { x: event.clientX, y: event.clientY }
}

function onPointerUp(event: PointerEvent) {
  if (!pointerStart || Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 5) return
  selectNearestTree(event)
  pointerStart = null
}

onMounted(() => {
  if (!container.value) return
  threeScene = new THREE.Scene()
  threeScene.background = new THREE.Color(0x07121d)
  threeScene.fog = new THREE.FogExp2(0x07121d, 0.0012)
  camera = new THREE.PerspectiveCamera(45, 1, 0.05, 5000)
  camera.up.set(0, 0, 1)
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.domElement.className = 'absolute inset-0 h-full w-full touch-none'
  renderer.domElement.setAttribute('data-testid', 'point-cloud-canvas')
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  container.value.appendChild(renderer.domElement)
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.screenSpacePanning = true
  controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE
  controls.mouseButtons.RIGHT = THREE.MOUSE.PAN
  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(container.value)
  resize()
  const animate = () => {
    controls?.update()
    if (renderer && threeScene && camera) renderer.render(threeScene, camera)
    animationFrame = requestAnimationFrame(animate)
  }
  animate()
  loadPointCloud()
})

watch(() => props.sceneData?.task_key, loadPointCloud)
watch(() => [props.showDetections, props.selectedTreeId, props.detections.length, props.viewMode], () => {
  rebuildBoxes()
  rebuildSingleTree()
})
watch(() => props.pointSize, updatePointSize)
watch(() => props.colorMode, applyPointColors)

onBeforeUnmount(() => {
  loadVersion += 1
  cancelAnimationFrame(animationFrame)
  resizeObserver?.disconnect()
  controls?.dispose()
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('pointerup', onPointerUp)
    renderer.dispose()
    renderer.domElement.remove()
  }
  disposeObject(pointCloud)
  disposeObject(singleTreeCloud)
  disposeObject(detectionGroup)
  disposeObject(grid)
})

defineExpose({ resetView })
</script>

<template>
  <div ref="container" class="relative h-full min-h-[520px] w-full overflow-hidden bg-[#07121d]" data-testid="point-cloud-viewer">
    <div class="pointer-events-none absolute left-4 top-4 z-10 flex flex-wrap gap-2 text-[11px] text-slate-200">
      <span class="border border-white/15 bg-slate-950/75 px-2 py-1">{{ pointCount.toLocaleString('zh-CN') }} 显示点</span>
      <span v-if="sceneData" class="border border-white/15 bg-slate-950/75 px-2 py-1">EPSG:{{ sceneData.epsg }}</span>
      <span v-if="colorMode === 'green'" class="border border-lime-400/40 bg-lime-950/80 px-2 py-1 text-lime-200">绿化模型着色</span>
      <span v-if="showDetections" class="border border-emerald-400/40 bg-emerald-950/80 px-2 py-1 text-emerald-200">{{ detections.length }} 个检测框</span>
    </div>
    <div v-if="loading" class="absolute inset-0 z-20 flex items-center justify-center bg-[#07121d]/90">
      <div class="w-64 text-center text-sm text-slate-200">
        <div class="mb-3 h-1 overflow-hidden bg-slate-700"><div class="h-full bg-emerald-400 transition-all" :style="{ width: `${Math.max(progress, 4)}%` }"></div></div>
        正在加载全场点云 {{ progress }}%
      </div>
    </div>
    <div v-if="viewMode === 'single' && selectedTree" class="pointer-events-none absolute bottom-4 left-4 z-10 border-l-2 border-amber-400 bg-slate-950/80 px-3 py-2 text-xs text-white">
      单木点云 T-{{ selectedTree.tree_id }} · {{ selectedTree.height_m.toFixed(2) }} m
    </div>
  </div>
</template>
