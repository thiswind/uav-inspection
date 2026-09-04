<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  CheckCircle2, CircleDot, Layers3, Leaf, LoaderCircle, LocateFixed,
  Play, RotateCcw, ScanSearch, SlidersHorizontal,
} from 'lucide-vue-next'
import {
  getPointCloudScene, type PointCloudScene, type VegetationTask,
} from '../api1/vegetation'
import PointCloudDetectionViewer from './PointCloudDetectionViewer.vue'

const props = defineProps<{ task: VegetationTask; tasks: VegetationTask[] }>()

const viewer = ref<InstanceType<typeof PointCloudDetectionViewer> | null>(null)
const sceneData = ref<PointCloudScene | null>(null)
const sceneError = ref('')
const sceneReady = ref(false)
const analysisStatus = ref<'idle' | 'running' | 'complete' | 'error'>('idle')
const analysisProgress = ref(0)
const analysisError = ref('')
const colorMode = ref<'rgb' | 'green'>('rgb')
const pointSize = ref(0.28)
let requestVersion = 0
let progressTimer: ReturnType<typeof setInterval> | null = null

const maximumArea = computed(() => Math.max(...props.tasks.map((task) => task.green_area_m2), 1))

function formatNumber(value: number, digits = 0) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function clearProgressTimer() {
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = null
}

async function loadScene() {
  const version = ++requestVersion
  clearProgressTimer()
  sceneData.value = null
  sceneError.value = ''
  sceneReady.value = false
  analysisStatus.value = 'idle'
  analysisProgress.value = 0
  analysisError.value = ''
  colorMode.value = 'rgb'
  try {
    const response = await getPointCloudScene(props.task.key)
    if (version === requestVersion) sceneData.value = response.data
  } catch (reason) {
    if (version === requestVersion) sceneError.value = reason instanceof Error ? reason.message : '场景数据加载失败'
  }
}

async function startAnalysis() {
  if (!sceneReady.value || analysisStatus.value === 'running') return
  clearProgressTimer()
  analysisStatus.value = 'running'
  analysisProgress.value = 8
  analysisError.value = ''
  colorMode.value = 'rgb'
  progressTimer = setInterval(() => {
    analysisProgress.value = Math.min(91, analysisProgress.value + Math.max(1, Math.round((95 - analysisProgress.value) / 7)))
  }, 100)
  try {
    await new Promise((resolve) => setTimeout(resolve, 950))
    analysisProgress.value = 100
    colorMode.value = 'green'
    await new Promise((resolve) => setTimeout(resolve, 180))
    analysisStatus.value = 'complete'
  } catch (reason) {
    analysisStatus.value = 'error'
    analysisError.value = reason instanceof Error ? reason.message : '绿化识别未完成'
  } finally {
    clearProgressTimer()
  }
}

watch(() => props.task.key, loadScene, { immediate: true })
onBeforeUnmount(clearProgressTimer)
</script>

<template>
  <div class="overflow-hidden border border-slate-200 bg-white shadow-sm" data-testid="area-detection-workspace">
    <div class="grid min-h-[680px] xl:h-[calc(100vh-230px)] xl:min-h-[680px] xl:grid-cols-[minmax(0,1fr)_340px]">
      <section class="relative min-h-[580px] overflow-hidden bg-[#07121d] xl:min-h-0">
        <PointCloudDetectionViewer
          v-if="sceneData"
          ref="viewer"
          :scene-data="sceneData"
          :detections="[]"
          :show-detections="false"
          :selected-tree-id="null"
          view-mode="boxes"
          :point-size="pointSize"
          :color-mode="colorMode"
          @loaded="sceneReady = true"
          @error="sceneError = $event"
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
            data-testid="start-area-detection"
            class="flex h-10 min-w-[124px] items-center justify-center gap-2 bg-emerald-500 px-4 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            :disabled="!sceneReady || analysisStatus === 'running'"
            @click="startAnalysis"
          >
            <LoaderCircle v-if="analysisStatus === 'running'" class="h-4 w-4 animate-spin" />
            <RotateCcw v-else-if="analysisStatus === 'complete'" class="h-4 w-4" />
            <Play v-else class="h-4 w-4 fill-current" />
            {{ analysisStatus === 'running' ? '识别中' : analysisStatus === 'complete' ? '重新识别' : '开始识别' }}
          </button>
        </div>

        <div v-if="analysisStatus === 'complete'" class="pointer-events-none absolute bottom-3 left-3 z-10 flex flex-wrap gap-2 text-[11px]">
          <span class="flex items-center gap-2 bg-slate-950/80 px-2 py-1 text-lime-200"><span class="h-2.5 w-2.5 bg-lime-400"></span>模型识别绿化</span>
          <span class="flex items-center gap-2 bg-slate-950/80 px-2 py-1 text-slate-300"><span class="h-2.5 w-2.5 bg-slate-500"></span>非绿化点</span>
        </div>

        <div v-if="sceneData" class="pointer-events-none absolute bottom-3 right-3 z-10 max-w-[calc(100%-1.5rem)] bg-slate-950/80 px-3 py-2 text-right text-[11px] leading-5 text-slate-300">
          <div>全场源点 {{ formatNumber(sceneData.source_points) }} · 显示点 {{ formatNumber(sceneData.display_points) }}</div>
          <div>浏览优化步长 1:{{ sceneData.decimation_step }}</div>
        </div>
      </section>

      <aside class="flex h-[620px] min-h-0 flex-col border-t border-slate-200 bg-white xl:h-auto xl:border-l xl:border-t-0" data-testid="area-detection-results">
        <div class="border-b border-slate-200 px-4 py-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-2"><ScanSearch class="h-4 w-4 text-emerald-600" /><h3 class="text-sm font-semibold text-slate-950">绿化面积识别结果</h3></div>
              <p class="mt-1 text-xs text-slate-500">{{ task.name }} · 水平投影</p>
            </div>
            <span v-if="analysisStatus === 'complete'" class="border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">{{ formatPercent(task.green_coverage_ratio) }}</span>
          </div>
        </div>

        <div v-if="analysisStatus === 'idle'" class="flex min-h-[300px] flex-1 flex-col items-center justify-center px-8 text-center">
          <div class="flex h-12 w-12 items-center justify-center border border-slate-200 bg-slate-50 text-slate-400"><Layers3 class="h-6 w-6" /></div>
          <div class="mt-4 text-sm font-semibold text-slate-800">尚未生成识别结果</div>
          <div class="mt-2 text-xs text-slate-500">点云场景已就绪</div>
        </div>

        <div v-else-if="analysisStatus === 'running'" class="flex min-h-[300px] flex-1 flex-col items-center justify-center px-8">
          <div class="relative flex h-16 w-16 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-emerald-600"><Leaf class="h-7 w-7" /><span class="absolute inset-0 animate-ping rounded-full border border-emerald-300"></span></div>
          <div class="mt-5 text-sm font-semibold text-slate-900">正在执行绿化点分类</div>
          <div class="mt-4 h-1.5 w-full max-w-56 overflow-hidden bg-slate-100"><div class="h-full bg-emerald-500 transition-all" :style="{ width: `${analysisProgress}%` }"></div></div>
          <div class="mt-2 text-xs tabular-nums text-slate-500">{{ analysisProgress }}%</div>
        </div>

        <div v-else-if="analysisStatus === 'error'" class="flex min-h-[300px] flex-1 flex-col items-center justify-center px-8 text-center">
          <CircleDot class="h-8 w-8 text-rose-500" /><div class="mt-3 text-sm font-semibold text-slate-900">识别未完成</div><div class="mt-2 text-xs text-slate-500">{{ analysisError }}</div>
        </div>

        <template v-else>
          <div class="grid grid-cols-2 gap-px border-b border-slate-200 bg-slate-200">
            <div class="bg-slate-50 px-3 py-3"><div class="text-[11px] text-slate-500">绿化投影面积</div><div class="mt-1 text-lg font-semibold text-slate-950">{{ formatNumber(task.green_area_m2, 2) }}<span class="ml-0.5 text-xs font-normal text-slate-400">m²</span></div></div>
            <div class="bg-slate-50 px-3 py-3"><div class="text-[11px] text-slate-500">平均置信度</div><div class="mt-1 text-lg font-semibold text-emerald-700">{{ formatPercent(task.green_mean_confidence) }}</div></div>
            <div class="bg-slate-50 px-3 py-3"><div class="text-[11px] text-slate-500">连续区域</div><div class="mt-1 text-lg font-semibold text-slate-950">{{ formatNumber(task.green_patch_count) }}<span class="ml-0.5 text-xs font-normal text-slate-400">片</span></div></div>
            <div class="bg-slate-50 px-3 py-3"><div class="text-[11px] text-slate-500">最大区域</div><div class="mt-1 text-lg font-semibold text-slate-950">{{ formatNumber(task.largest_green_patch_m2, 2) }}<span class="ml-0.5 text-xs font-normal text-slate-400">m²</span></div></div>
          </div>

          <div class="border-b border-slate-200 p-3">
            <div class="grid grid-cols-2 gap-1 border border-slate-200 bg-slate-50 p-1" aria-label="点云着色方式">
              <button type="button" class="flex h-8 items-center justify-center gap-2 text-xs font-medium transition" :class="colorMode === 'rgb' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-white'" @click="colorMode = 'rgb'"><Layers3 class="h-4 w-4" />原始点云</button>
              <button type="button" class="flex h-8 items-center justify-center gap-2 text-xs font-medium transition" :class="colorMode === 'green' ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-white'" @click="colorMode = 'green'"><Leaf class="h-4 w-4" />绿化识别</button>
            </div>
          </div>

          <div class="min-h-[220px] flex-1 overflow-auto px-4 py-3">
            <div class="mb-3 flex items-center justify-between text-xs"><span class="font-semibold text-slate-700">五任务面积对比</span><span class="text-slate-400">m²</span></div>
            <button v-for="item in tasks" :key="item.key" type="button" class="mb-4 block w-full text-left">
              <div class="mb-1.5 flex items-center justify-between gap-3 text-[11px]"><span class="truncate" :class="item.key === task.key ? 'font-semibold text-emerald-700' : 'text-slate-600'">{{ item.name }}</span><span class="font-medium tabular-nums text-slate-800">{{ formatNumber(item.green_area_m2, 1) }}</span></div>
              <div class="h-1.5 overflow-hidden bg-slate-100"><div class="h-full" :class="item.key === task.key ? 'bg-lime-500' : 'bg-emerald-300'" :style="{ width: `${Math.max(2, item.green_area_m2 / maximumArea * 100)}%` }"></div></div>
            </button>
          </div>

          <div class="flex items-center gap-2 border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500"><CheckCircle2 class="h-4 w-4 text-emerald-500" />识别结果已加载</div>
        </template>
      </aside>
    </div>
  </div>
</template>
