<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  BoxSelect, CheckCircle2, CircleDot, Focus, LoaderCircle, LocateFixed,
  Play, RotateCcw, Ruler, ScanSearch, SlidersHorizontal, TreePine,
} from 'lucide-vue-next'
import {
  getPointCloudScene, getTreeMeasurements,
  type PointCloudScene, type TreeMeasurement, type VegetationTask,
} from '../api1/vegetation'
import PointCloudDetectionViewer from './PointCloudDetectionViewer.vue'

const props = defineProps<{ task: VegetationTask }>()

const viewer = ref<InstanceType<typeof PointCloudDetectionViewer> | null>(null)
const sceneData = ref<PointCloudScene | null>(null)
const sceneError = ref('')
const sceneReady = ref(false)
const detections = ref<TreeMeasurement[]>([])
const selectedTreeId = ref<number | null>(null)
const detectionStatus = ref<'idle' | 'running' | 'complete' | 'error'>('idle')
const detectionProgress = ref(0)
const detectionTotal = ref(0)
const detectionError = ref('')
const viewMode = ref<'boxes' | 'single'>('boxes')
const pointSize = ref(0.28)
let requestVersion = 0
let detectionRunVersion = 0

const selectedTree = computed(() => detections.value.find((tree) => tree.tree_id === selectedTreeId.value) ?? null)
const averageDetectedHeight = computed(() => {
  if (!detections.value.length) return 0
  return detections.value.reduce((sum, tree) => sum + tree.height_m, 0) / detections.value.length
})
const maxDetectedHeight = computed(() => Math.max(...detections.value.map((tree) => tree.height_m), 0))

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function wait(milliseconds: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds))
}

async function loadScene() {
  const version = ++requestVersion
  detectionRunVersion += 1
  sceneData.value = null
  sceneReady.value = false
  sceneError.value = ''
  detections.value = []
  selectedTreeId.value = null
  detectionStatus.value = 'idle'
  detectionProgress.value = 0
  detectionTotal.value = 0
  viewMode.value = 'boxes'
  try {
    const response = await getPointCloudScene(props.task.key)
    if (version === requestVersion) sceneData.value = response.data
  } catch (reason) {
    if (version === requestVersion) sceneError.value = reason instanceof Error ? reason.message : '场景数据加载失败'
  }
}

async function startDetection() {
  if (!sceneReady.value || detectionStatus.value === 'running') return
  const runVersion = ++detectionRunVersion
  detectionStatus.value = 'running'
  detectionProgress.value = 0
  detectionTotal.value = props.task.tree_count
  detectionError.value = ''
  detections.value = []
  selectedTreeId.value = null
  viewMode.value = 'boxes'
  try {
    const response = await getTreeMeasurements(props.task.key, { sort_by: 'height_m', descending: true })
    if (runVersion !== detectionRunVersion) return

    const pendingTrees = response.data.items
    detectionTotal.value = response.data.total
    const revealInterval = Math.min(420, Math.max(55, Math.round(14000 / Math.max(pendingTrees.length, 1))))

    await wait(280)
    for (let index = 0; index < pendingTrees.length; index += 1) {
      if (runVersion !== detectionRunVersion) return
      const tree = pendingTrees[index]
      if (!tree) continue

      detections.value.push(tree)
      selectedTreeId.value = tree.tree_id
      detectionProgress.value = Math.round(((index + 1) / pendingTrees.length) * 100)
      await nextTick()
      if (index < pendingTrees.length - 1) await wait(revealInterval)
    }

    detectionProgress.value = 100
    await wait(260)
    if (runVersion !== detectionRunVersion) return
    detectionStatus.value = 'complete'
  } catch (reason) {
    if (runVersion !== detectionRunVersion) return
    detectionStatus.value = 'error'
    detectionError.value = reason instanceof Error ? reason.message : '检测结果读取失败'
  }
}

function selectTree(treeId: number) {
  selectedTreeId.value = treeId
}

function setViewMode(mode: 'boxes' | 'single') {
  if (!detections.value.length) return
  viewMode.value = mode
  if (mode === 'single' && selectedTreeId.value === null) selectedTreeId.value = detections.value[0]?.tree_id ?? null
}

watch(() => props.task.key, loadScene, { immediate: true })
onBeforeUnmount(() => { detectionRunVersion += 1 })
</script>

<template>
  <div class="overflow-hidden border border-slate-200 bg-white shadow-sm" data-testid="height-detection-workspace">
    <div class="grid min-h-[680px] xl:h-[calc(100vh-230px)] xl:min-h-[680px] xl:grid-cols-[minmax(0,1fr)_340px]">
      <section class="relative min-h-[580px] overflow-hidden bg-[#07121d] xl:min-h-0">
        <PointCloudDetectionViewer
          v-if="sceneData"
          ref="viewer"
          :scene-data="sceneData"
          :detections="detections"
          :show-detections="detections.length > 0"
          :selected-tree-id="selectedTreeId"
          :view-mode="viewMode"
          :point-size="pointSize"
          @loaded="sceneReady = true"
          @error="sceneError = $event"
          @select-tree="selectTree"
        />

        <div v-else class="flex h-full min-h-[580px] items-center justify-center bg-[#07121d] text-sm text-slate-300">
          <LoaderCircle v-if="!sceneError" class="mr-2 h-5 w-5 animate-spin text-emerald-400" />
          <span>{{ sceneError || '正在读取点云场景' }}</span>
        </div>

        <div class="absolute right-3 top-3 z-30 flex max-w-[calc(100%-1.5rem)] flex-wrap justify-end gap-2">
          <div class="flex h-10 items-center gap-2 border border-white/15 bg-slate-950/85 px-3 text-xs text-slate-200 backdrop-blur">
            <SlidersHorizontal class="h-4 w-4 text-slate-400" />
            <span>点大小</span>
            <input v-model.number="pointSize" aria-label="点大小" type="range" min="0.08" max="0.8" step="0.02" class="w-20 accent-emerald-400" />
          </div>
          <button type="button" title="重置视角" class="flex h-10 w-10 items-center justify-center border border-white/15 bg-slate-950/85 text-white transition hover:bg-slate-800 disabled:opacity-40" :disabled="!sceneReady" @click="viewer?.resetView()"><LocateFixed class="h-4 w-4" /></button>
          <button
            type="button"
            data-testid="start-detection"
            class="flex h-10 min-w-[124px] items-center justify-center gap-2 bg-emerald-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            :disabled="!sceneReady || detectionStatus === 'running'"
            @click="startDetection"
          >
            <LoaderCircle v-if="detectionStatus === 'running'" class="h-4 w-4 animate-spin" />
            <RotateCcw v-else-if="detectionStatus === 'complete'" class="h-4 w-4" />
            <Play v-else class="h-4 w-4 fill-current" />
            {{ detectionStatus === 'running' ? '检测中' : detectionStatus === 'complete' ? '重新检测' : '开始检测' }}
          </button>
        </div>

        <div v-if="sceneData" class="pointer-events-none absolute bottom-3 right-3 z-10 max-w-[calc(100%-1.5rem)] bg-slate-950/80 px-3 py-2 text-right text-[11px] leading-5 text-slate-300">
          <div>全场源点 {{ formatNumber(sceneData.source_points) }} · 显示点 {{ formatNumber(sceneData.display_points) }}</div>
          <div>浏览优化步长 1:{{ sceneData.decimation_step }}</div>
        </div>
      </section>

      <aside class="flex h-[620px] min-h-0 flex-col border-t border-slate-200 bg-white xl:h-auto xl:border-l xl:border-t-0" data-testid="detection-results">
        <div class="border-b border-slate-200 px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-2"><ScanSearch class="h-4 w-4 text-emerald-600" /><h3 class="text-sm font-semibold text-slate-950">树木检测结果</h3></div>
              <p class="mt-1 text-xs text-slate-500">{{ task.name }} · P99 高度</p>
            </div>
            <span
              v-if="detectionStatus === 'running' || detectionStatus === 'complete'"
              class="border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold tabular-nums text-emerald-700"
              data-testid="detected-tree-count"
            >
              {{ detectionStatus === 'running' ? `${detections.length} / ${detectionTotal}` : detections.length }} 棵
            </span>
          </div>
        </div>

        <div v-if="detectionStatus === 'idle'" class="flex min-h-[300px] flex-1 flex-col items-center justify-center px-8 text-center">
          <div class="flex h-12 w-12 items-center justify-center border border-slate-200 bg-slate-50 text-slate-400"><ScanSearch class="h-6 w-6" /></div>
          <div class="mt-4 text-sm font-semibold text-slate-800">尚未生成检测结果</div>
          <div class="mt-2 text-xs text-slate-500">场景就绪后可执行单木检测</div>
        </div>

        <div v-else-if="detectionStatus === 'running' && !detections.length" class="flex min-h-[300px] flex-1 flex-col items-center justify-center px-8">
          <div class="relative flex h-16 w-16 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-emerald-600"><ScanSearch class="h-7 w-7" /><span class="absolute inset-0 animate-ping rounded-full border border-emerald-300"></span></div>
          <div class="mt-5 text-sm font-semibold text-slate-900">正在扫描树木实例</div>
          <div class="mt-2 text-xs text-slate-500">检测到目标后将逐棵显示检测框与树高</div>
          <div class="mt-4 h-1.5 w-full max-w-56 overflow-hidden bg-slate-100"><div class="h-full bg-emerald-500 transition-all" :style="{ width: `${detectionProgress}%` }"></div></div>
          <div class="mt-2 text-xs tabular-nums text-slate-500">{{ detectionProgress }}%</div>
        </div>

        <div v-else-if="detectionStatus === 'error'" class="flex min-h-[300px] flex-1 flex-col items-center justify-center px-8 text-center">
          <CircleDot class="h-8 w-8 text-rose-500" /><div class="mt-3 text-sm font-semibold text-slate-900">检测未完成</div><div class="mt-2 text-xs text-slate-500">{{ detectionError }}</div>
        </div>

        <template v-else>
          <div v-if="detectionStatus === 'running'" class="border-b border-emerald-200 bg-emerald-50 px-4 py-3" data-testid="live-detection-progress">
            <div class="flex items-center justify-between gap-3 text-xs font-medium text-emerald-800">
              <span class="flex items-center gap-2"><LoaderCircle class="h-4 w-4 animate-spin" />正在逐棵检测</span>
              <span class="tabular-nums">{{ detectionProgress }}%</span>
            </div>
            <div class="mt-2 h-1.5 overflow-hidden bg-emerald-100"><div class="h-full bg-emerald-500 transition-[width] duration-150" :style="{ width: `${detectionProgress}%` }"></div></div>
          </div>

          <div class="grid grid-cols-3 gap-px border-b border-slate-200 bg-slate-200">
            <div class="bg-slate-50 px-3 py-3"><div class="text-[11px] text-slate-500">检测数量</div><div class="mt-1 text-lg font-semibold text-slate-950">{{ detections.length }}</div></div>
            <div class="bg-slate-50 px-3 py-3"><div class="text-[11px] text-slate-500">平均高度</div><div class="mt-1 text-lg font-semibold text-slate-950">{{ averageDetectedHeight.toFixed(2) }}<span class="ml-0.5 text-xs font-normal text-slate-400">m</span></div></div>
            <div class="bg-slate-50 px-3 py-3"><div class="text-[11px] text-slate-500">最大高度</div><div class="mt-1 text-lg font-semibold text-emerald-700">{{ maxDetectedHeight.toFixed(2) }}<span class="ml-0.5 text-xs font-normal text-slate-400">m</span></div></div>
          </div>

          <div class="border-b border-slate-200 p-3">
            <div class="grid grid-cols-2 gap-1 border border-slate-200 bg-slate-50 p-1" aria-label="检测展示方式">
              <button type="button" class="flex h-8 items-center justify-center gap-2 text-xs font-medium transition" :class="viewMode === 'boxes' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-white'" @click="setViewMode('boxes')"><BoxSelect class="h-4 w-4" />检测框</button>
              <button type="button" class="flex h-8 items-center justify-center gap-2 text-xs font-medium transition" :class="viewMode === 'single' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-white'" @click="setViewMode('single')"><Focus class="h-4 w-4" />单木点云</button>
            </div>
          </div>

          <div v-if="selectedTree" :key="selectedTree.tree_id" class="tree-height-reveal grid grid-cols-2 gap-px border-b border-slate-200 bg-slate-200" data-testid="current-tree-height">
            <div class="bg-amber-50 px-4 py-3"><div class="flex items-center gap-1.5 text-[11px] text-amber-700"><TreePine class="h-3.5 w-3.5" />当前树木</div><div class="mt-1 text-base font-semibold text-slate-950">T-{{ selectedTree.tree_id }}</div></div>
            <div class="bg-amber-50 px-4 py-3"><div class="flex items-center gap-1.5 text-[11px] text-amber-700"><Ruler class="h-3.5 w-3.5" />检测高度</div><div class="mt-1 text-base font-semibold text-slate-950">{{ selectedTree.height_m.toFixed(2) }} m</div></div>
          </div>

          <div class="min-h-[280px] flex-1 overflow-auto" data-testid="tree-result-list">
            <button
              v-for="tree in detections"
              :key="tree.tree_id"
              type="button"
              class="grid h-16 w-full grid-cols-[52px_minmax(0,1fr)_72px] items-center border-b border-slate-100 px-4 text-left transition hover:bg-emerald-50"
              :class="selectedTreeId === tree.tree_id ? 'bg-amber-50' : ''"
              @click="selectTree(tree.tree_id)"
            >
              <span class="text-xs font-semibold text-slate-900">T-{{ tree.tree_id }}</span>
              <span class="min-w-0"><span class="block truncate text-xs text-slate-500">冠幅 {{ tree.crown_width_m.toFixed(2) }} m</span><span class="mt-1 block text-[11px] text-slate-400">{{ formatNumber(tree.points) }} 点</span></span>
              <span class="text-right text-sm font-semibold tabular-nums text-emerald-700">{{ tree.height_m.toFixed(2) }} m</span>
            </button>
          </div>

          <div v-if="detectionStatus === 'running'" class="flex items-center gap-2 border-t border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-700"><LoaderCircle class="h-4 w-4 animate-spin" />正在检测第 {{ detections.length }} / {{ detectionTotal }} 棵，树高已同步</div>
          <div v-else class="flex items-center gap-2 border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500"><CheckCircle2 class="h-4 w-4 text-emerald-500" />检测结果已加载</div>
        </template>
      </aside>
    </div>
  </div>
</template>

<style scoped>
@keyframes tree-height-reveal {
  0% { opacity: 0.35; transform: translateY(-4px); }
  100% { opacity: 1; transform: translateY(0); }
}

.tree-height-reveal {
  animation: tree-height-reveal 220ms ease-out;
}
</style>
