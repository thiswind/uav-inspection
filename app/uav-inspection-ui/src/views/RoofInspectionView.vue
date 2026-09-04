<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import InspectionHeader from '../components/common/InspectionHeader.vue'
import DetectionVideoFrame from '../components/common/DetectionVideoFrame.vue'
import FloatingNotice from '../components/common/FloatingNotice.vue'
import { webPath } from '../utils/webroot'

const API_BASE = webPath('/api/v1/roof')

interface RoofTask {
  id: string
  name: string
  status: string
  progress: number
  defect_count: number
  video_url: string
  report_url: string
  duration_sec: number
  video_name: string
  source: 'backend' | 'upload'
}

interface RoofDefect {
  id: string
  class_name: string
  severity: string
  confidence: number
  latitude: number
  longitude: number
  frame_index: number
  video_time_ms: number
  screenshot_path?: string
  review_status: string
}

interface RoofStatistics {
  total: number
  by_severity: Record<string, number>
  by_type: Record<string, number>
  by_status: Record<string, number>
}

interface TelemetryItem {
  longitude: number
  latitude: number
  altitude: number
  yaw: number
}

const currentTime = ref('')
const backendOnline = ref(false)
const backendTasks = ref<RoofTask[]>([])
const uploadedTasks = ref<RoofTask[]>([])
const activeTaskId = ref('')
const defects = ref<RoofDefect[]>([])
const selectedDefect = ref<RoofDefect | null>(null)
const statistics = ref<RoofStatistics>({ total: 0, by_severity: {}, by_type: {}, by_status: {} })
const telemetry = ref<TelemetryItem[]>([])
const isPlaying = ref(false)
const videoRef = ref<HTMLVideoElement | null>(null)
const showUploadPanel = ref(false)
const showTaskPicker = ref(false)
const showControlPanel = ref(false)
const showDefectListPanel = ref(false)
const uploadTaskName = ref('')
const uploadVideoFile = ref<File | null>(null)
const uploadingTask = ref(false)
const message = ref('请选择一个屋顶巡检任务开始演示。')
const playbackRate = ref(1)
const severityFilter = ref<'all' | 'high' | 'medium' | 'low'>('all')
const currentVideoTimeMs = ref(0)
const videoDurationSec = ref(0)
let clockTimer: number | null = null
let healthTimer: number | null = null

const tasks = computed(() => [...uploadedTasks.value, ...backendTasks.value])
const activeTask = computed(() => tasks.value.find((item) => item.id === activeTaskId.value) || null)
const currentTaskName = computed(() => activeTask.value?.name || '未选择任务')
const currentVideoName = computed(() => activeTask.value?.video_name || '尚未选择视频')
const canPlay = computed(() => Boolean(activeTask.value?.video_url))
const uploadReady = computed(() => Boolean(uploadVideoFile.value))
const brokenScreenshotIds = ref<Record<string, true>>({})
const filteredDefects = computed(() => {
  if (severityFilter.value === 'all') return defects.value
  return defects.value.filter((item) => item.severity === severityFilter.value)
})
const displayedDefects = computed(() => filteredDefects.value.filter((item) => hasVisibleScreenshot(item)))
const sortedDisplayedDefects = computed(() => [...displayedDefects.value].sort((left, right) => left.video_time_ms - right.video_time_ms))
const revealedDefects = computed(() => sortedDisplayedDefects.value.filter((item) => item.video_time_ms <= currentVideoTimeMs.value + 250))
const activeVideoUrl = computed(() => activeTask.value?.video_url || '')
const startPoint = computed(() => {
  const first = telemetry.value[0]
  return first ? `${first.latitude.toFixed(6)}, ${first.longitude.toFixed(6)}` : '--'
})
const endPoint = computed(() => {
  const last = telemetry.value[telemetry.value.length - 1]
  return last ? `${last.latitude.toFixed(6)}, ${last.longitude.toFixed(6)}` : '--'
})
const avgAltitude = computed(() => {
  if (!telemetry.value.length) return 0
  return telemetry.value.reduce((sum, item) => sum + item.altitude, 0) / telemetry.value.length
})
const yawRange = computed(() => {
  if (!telemetry.value.length) return '--'
  const yaws = telemetry.value.map((item) => item.yaw)
  return `${Math.min(...yaws).toFixed(1)}° ~ ${Math.max(...yaws).toFixed(1)}°`
})
const playbackTimelineText = computed(() => `${formatRoofTime(currentVideoTimeMs.value / 1000)} / ${formatRoofTime(videoDurationSec.value || activeTask.value?.duration_sec || 0)}`)

watch(playbackRate, (value) => {
  if (videoRef.value) {
    videoRef.value.playbackRate = value
  }
})

watch(revealedDefects, (items) => {
  if (!selectedDefect.value || !items.some((item) => item.id === selectedDefect.value?.id)) {
    selectedDefect.value = items[0] || null
  }
})

function updateClock() {
  currentTime.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

async function refreshHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) })
    backendOnline.value = response.ok
  } catch {
    backendOnline.value = false
  }
}

function mapBackendTask(raw: Omit<RoofTask, 'source'>): RoofTask {
  return {
    ...raw,
    source: 'backend',
  }
}

async function loadBackendTasks() {
  try {
    const response = await fetch(`${API_BASE}/tasks`, { signal: AbortSignal.timeout(4000) })
    backendOnline.value = response.ok
    if (!response.ok) return
    const data = await response.json()
    backendTasks.value = Array.isArray(data.tasks) ? data.tasks.map(mapBackendTask) : []
    if (!activeTaskId.value && tasks.value.length > 0) {
      await selectTask(tasks.value[0].id)
    }
  } catch {
    backendOnline.value = false
  }
}

async function loadDefects(taskId: string) {
  const response = await fetch(`${API_BASE}/tasks/${taskId}/defects`)
  if (!response.ok) return
  const data = await response.json()
  brokenScreenshotIds.value = {}
  defects.value = Array.isArray(data.defects) ? data.defects : []
}

async function loadStatistics(taskId: string) {
  const response = await fetch(`${API_BASE}/tasks/${taskId}/statistics`)
  if (!response.ok) return
  statistics.value = await response.json()
}

async function loadTelemetry(taskId: string) {
  const response = await fetch(`${API_BASE}/tasks/${taskId}/telemetry`)
  if (!response.ok) return
  const data = await response.json()
  telemetry.value = Array.isArray(data.telemetry) ? data.telemetry : []
}

function resetLocalState() {
  defects.value = []
  telemetry.value = []
  statistics.value = { total: 0, by_severity: {}, by_type: {}, by_status: {} }
  selectedDefect.value = null
  brokenScreenshotIds.value = {}
  currentVideoTimeMs.value = 0
  videoDurationSec.value = 0
  showDefectListPanel.value = false
}

function resolveScreenshotUrl(path?: string) {
  return path ? encodeURI(path) : ''
}

function hasVisibleScreenshot(defect: RoofDefect) {
  return Boolean(defect.screenshot_path) && !brokenScreenshotIds.value[defect.id]
}

function markScreenshotBroken(defectId: string) {
  if (brokenScreenshotIds.value[defectId]) return
  brokenScreenshotIds.value = {
    ...brokenScreenshotIds.value,
    [defectId]: true,
  }
}

async function selectTask(taskId: string) {
  activeTaskId.value = taskId
  showTaskPicker.value = false
  const task = tasks.value.find((item) => item.id === taskId)
  if (!task) return

  message.value = `已加载任务：${task.name}`
  resetLocalState()
  videoDurationSec.value = task.duration_sec || 0

  if (task.source === 'upload') {
    return
  }

  await Promise.all([loadDefects(taskId), loadStatistics(taskId), loadTelemetry(taskId)])
}

function togglePlay() {
  if (!videoRef.value || !activeVideoUrl.value) return
  if (videoRef.value.paused) {
    videoRef.value.playbackRate = playbackRate.value
    void videoRef.value.play()
  } else {
    videoRef.value.pause()
  }
}

function replayVideo() {
  if (!videoRef.value) return
  videoRef.value.currentTime = 0
  currentVideoTimeMs.value = 0
  void videoRef.value.play()
}

function seekVideo(seconds: number) {
  if (!videoRef.value) return
  videoRef.value.currentTime = seconds
  currentVideoTimeMs.value = Math.round(seconds * 1000)
}

function onVideoPlay() {
  isPlaying.value = true
  message.value = '屋顶巡检演示正在播放。'
}

function onVideoPause() {
  isPlaying.value = false
}

function onVideoEnded() {
  isPlaying.value = false
  if (videoRef.value) {
    currentVideoTimeMs.value = Math.round(videoRef.value.currentTime * 1000)
  }
  message.value = '视频播放完成，可以重新播放继续查看。'
}

function onVideoError() {
  isPlaying.value = false
  message.value = '视频无法播放，请重新选择任务。'
}

function onVideoLoadedMetadata() {
  if (!videoRef.value) return
  const duration = Number.isFinite(videoRef.value.duration) ? videoRef.value.duration : 0
  videoDurationSec.value = duration || activeTask.value?.duration_sec || 0
}

function onVideoTimeUpdate() {
  if (!videoRef.value) return
  currentVideoTimeMs.value = Math.round(videoRef.value.currentTime * 1000)
}

function selectDefect(defect: RoofDefect) {
  selectedDefect.value = defect
  showDefectListPanel.value = false
  if (videoRef.value) {
    videoRef.value.currentTime = defect.video_time_ms / 1000
    currentVideoTimeMs.value = defect.video_time_ms
  }
}

function severityLabel(value: string) {
  if (value === 'high') return '高风险'
  if (value === 'medium') return '中风险'
  if (value === 'low') return '低风险'
  return '未分类'
}

function severityClass(value: string) {
  if (value === 'high') return 'bg-rose-100 text-rose-700'
  if (value === 'medium') return 'bg-amber-100 text-amber-700'
  return 'bg-emerald-100 text-emerald-700'
}

function openUploadPanel() {
  showUploadPanel.value = true
}

function closeUploadPanel() {
  showUploadPanel.value = false
}

function toggleTaskPicker() {
  showTaskPicker.value = !showTaskPicker.value
}

function closeTaskPicker() {
  showTaskPicker.value = false
}

function toggleControlPanel() {
  showControlPanel.value = !showControlPanel.value
}

function closeControlPanel() {
  showControlPanel.value = false
}

function toggleDefectListPanel() {
  showDefectListPanel.value = !showDefectListPanel.value
}

function formatRoofTime(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  const secs = safeSeconds % 60
  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function onVideoFileSelect(event: Event) {
  uploadVideoFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

function clearUploadDraft() {
  uploadTaskName.value = ''
  uploadVideoFile.value = null
}

async function persistUploadTask() {
  if (!uploadVideoFile.value) {
    message.value = '请先选择一个视频文件。'
    return
  }

  const file = uploadVideoFile.value
  const taskName = uploadTaskName.value.trim() || file.name.replace(/\.[^/.]+$/, '')
  const form = new FormData()
  form.append('task_name', taskName)
  form.append('video', file)

  uploadingTask.value = true
  try {
    const response = await fetch(`${API_BASE}/tasks/upload`, {
      method: 'POST',
      body: form,
    })
    if (!response.ok) {
      throw new Error('upload failed')
    }
    const data = await response.json()
    clearUploadDraft()
    closeUploadPanel()
    await loadBackendTasks()
    if (data.task_id) {
      await selectTask(data.task_id)
    }
    message.value = `任务已上传并写入记录：${taskName}`
  } catch {
    message.value = '上传失败，请检查后端上传接口。'
  } finally {
    uploadingTask.value = false
  }
}

function confirmUploadTask() {
  if (!uploadVideoFile.value) {
    message.value = '请先选择一个视频文件。'
    return
  }

  const file = uploadVideoFile.value
  const task: RoofTask = {
    id: `upload-${Date.now()}`,
    name: uploadTaskName.value.trim() || file.name.replace(/\.[^/.]+$/, ''),
    status: '本地演示',
    progress: 100,
    defect_count: 0,
    video_url: URL.createObjectURL(file),
    report_url: '',
    duration_sec: 0,
    video_name: file.name,
    source: 'upload',
  }
  uploadedTasks.value.unshift(task)
  clearUploadDraft()
  closeUploadPanel()
  void selectTask(task.id)
}

void confirmUploadTask

onMounted(async () => {
  updateClock()
  await Promise.all([refreshHealth(), loadBackendTasks()])
  clockTimer = window.setInterval(updateClock, 1000)
  healthTimer = window.setInterval(refreshHealth, 10000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (healthTimer) clearInterval(healthTimer)
  for (const task of uploadedTasks.value) {
    URL.revokeObjectURL(task.video_url)
  }
})
</script>

<template>
  <div class="relative min-h-screen overflow-hidden bg-slate-50 text-slate-800">
    <div class="pointer-events-none absolute top-[-10%] right-[-6%] h-[40%] w-[40%] rounded-full bg-cyan-300/18 blur-[120px]"></div>
    <div class="pointer-events-none absolute bottom-[-12%] left-[-6%] h-[40%] w-[40%] rounded-full bg-sky-300/16 blur-[120px]"></div>
    <div class="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgwLCAwLCAwLCAwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')]"></div>

    <div class="relative z-10 px-4 pt-4 md:px-6">
      <InspectionHeader title="建筑屋顶巡检" :task-name="currentTaskName" :online="backendOnline">
        <template #actions>
          <button
            class="rounded-2xl border border-cyan-200 bg-cyan-50 px-5 py-3 text-sm font-medium text-cyan-700 shadow-[0_10px_25px_-18px_rgba(34,211,238,0.35)] transition hover:border-cyan-300 hover:bg-cyan-100"
            @click="toggleControlPanel"
          >
            实时控制
          </button>
          <button
            class="rounded-2xl bg-gradient-to-r from-cyan-400 to-sky-400 px-5 py-3 text-sm font-medium text-slate-950 shadow-[0_10px_25px_-15px_rgba(34,211,238,0.8)] transition hover:from-cyan-300 hover:to-sky-300"
            @click="openUploadPanel"
          >
            上传任务
          </button>
          <button
            class="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-medium text-slate-700 transition hover:border-cyan-300 hover:bg-cyan-50"
            @click="toggleTaskPicker"
          >
            加载任务
          </button>
        </template>
      </InspectionHeader>
    </div>

    <FloatingNotice :message="message" :tone="backendOnline ? 'info' : 'warning'" :duration="3500" centered />

    <main class="relative z-10 grid min-h-[calc(100vh-104px)] grid-cols-1 gap-5 px-4 pb-4 pt-2 md:px-6 md:pb-6 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
      <aside class="space-y-4" data-testid="roof-left-summary">
        <section class="rounded-2xl border border-white bg-white/88 p-4 shadow-[0_12px_40px_-20px_rgba(34,211,238,0.18)]">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold text-slate-900">任务概览</h2>
            <span class="flex items-center gap-1.5 text-xs text-slate-600">
              <span class="h-2 w-2 rounded-full" :class="backendOnline ? 'bg-emerald-400' : 'bg-red-400'"></span>
              {{ backendOnline ? '后端在线' : '后端离线' }}
            </span>
          </div>

          <div class="mt-3 space-y-2 text-xs text-slate-600">
            <div class="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div class="text-[11px] text-slate-500">当前视频</div>
              <div class="mt-0.5 truncate text-sm font-semibold text-slate-900">{{ currentVideoName }}</div>
            </div>
            <div class="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div class="text-[11px] text-slate-500">任务来源</div>
              <div class="mt-0.5 text-sm font-semibold text-slate-900">{{ activeTask?.source === 'upload' ? '本地上传' : '后端任务' }}</div>
            </div>
            <div class="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div class="text-[11px] text-slate-500">系统时间</div>
              <div class="mt-0.5 font-mono text-sm font-semibold text-slate-900">{{ currentTime }}</div>
            </div>
          </div>
        </section>

        <section class="rounded-2xl border border-white bg-white/88 p-4 shadow-[0_12px_40px_-20px_rgba(34,211,238,0.18)]" data-testid="roof-statistics-compact">
          <h2 class="text-base font-semibold text-slate-900">统计概览</h2>
          <div class="mt-3 grid grid-cols-2 gap-2">
            <div class="rounded-xl bg-slate-50 px-3 py-2.5"><div class="text-[11px] text-slate-500">总缺陷</div><div class="mt-0.5 text-xl font-bold text-slate-900">{{ statistics.total }}</div></div>
            <div class="rounded-xl bg-rose-50 px-3 py-2.5"><div class="text-[11px] text-rose-500">高风险</div><div class="mt-0.5 text-xl font-bold text-rose-600">{{ statistics.by_severity.high || 0 }}</div></div>
            <div class="rounded-xl bg-amber-50 px-3 py-2.5"><div class="text-[11px] text-amber-600">中风险</div><div class="mt-0.5 text-xl font-bold text-amber-600">{{ statistics.by_severity.medium || 0 }}</div></div>
            <div class="rounded-xl bg-emerald-50 px-3 py-2.5"><div class="text-[11px] text-emerald-600">低风险</div><div class="mt-0.5 text-xl font-bold text-emerald-600">{{ statistics.by_severity.low || 0 }}</div></div>
          </div>
          <div v-if="Object.keys(statistics.by_type).length" class="mt-3 space-y-2 border-t border-slate-100 pt-3">
            <div v-for="(count, name) in statistics.by_type" :key="name">
              <div class="flex items-center justify-between text-[11px] text-slate-500"><span>{{ name }}</span><span>{{ count }}</span></div>
              <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200"><div class="h-full rounded-full bg-cyan-400" :style="{ width: `${Math.max(8, Math.round((count / Math.max(1, statistics.total)) * 100))}%` }"></div></div>
            </div>
          </div>
        </section>

        <section class="rounded-2xl border border-white bg-white/88 p-4 shadow-[0_12px_40px_-20px_rgba(34,211,238,0.18)]" data-testid="roof-flight-compact">
          <h2 class="text-base font-semibold text-slate-900">飞行概况</h2>
          <div class="mt-3 space-y-2">
            <div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"><div class="text-[11px] text-slate-500">起点坐标</div><div class="mt-0.5 truncate font-mono text-xs text-cyan-700" :title="startPoint">{{ startPoint }}</div></div>
            <div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"><div class="text-[11px] text-slate-500">终点坐标</div><div class="mt-0.5 truncate font-mono text-xs text-cyan-700" :title="endPoint">{{ endPoint }}</div></div>
            <div class="grid grid-cols-2 gap-2">
              <div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5"><div class="text-[11px] text-slate-500">平均高度</div><div class="mt-0.5 text-base font-bold text-slate-900">{{ avgAltitude.toFixed(1) }} m</div></div>
              <div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5"><div class="text-[11px] text-slate-500">偏航范围</div><div class="mt-0.5 truncate text-sm font-bold text-slate-900" :title="yawRange">{{ yawRange }}</div></div>
            </div>
          </div>
        </section>
      </aside>

      <section class="space-y-5">
        <div class="rounded-[28px] border border-white bg-white/88 p-4 shadow-[0_12px_40px_-20px_rgba(34,211,238,0.18)]">
          <div class="mb-3 flex items-center justify-between gap-4">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">任务视频</h2>
            </div>
            <div class="flex flex-wrap items-center gap-3">
              <a
                v-if="activeTask?.source === 'backend' && activeTask.report_url"
                :href="activeTask.report_url"
                target="_blank"
                class="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-cyan-300 hover:bg-cyan-50"
              >
                查看报告
              </a>
            </div>
          </div>

          <DetectionVideoFrame
            class="h-[calc(100vh-190px)] min-h-[600px] max-h-[900px]"
            label="YOLO 屋顶缺陷检测"
            :status="isPlaying ? '实时检测中' : '等待启动'"
            :playing="isPlaying"
            :disabled="!canPlay"
            :current-time="currentVideoTimeMs / 1000"
            :duration="videoDurationSec"
            :empty="!canPlay"
            empty-text="请先上传任务或加载一个已有任务。"
            @toggle="togglePlay"
            @replay="replayVideo"
            @seek="seekVideo"
          >
            <video
              ref="videoRef"
              class="h-full w-full object-contain"
              :src="activeVideoUrl"
              @loadedmetadata="onVideoLoadedMetadata"
              @timeupdate="onVideoTimeUpdate"
              @play="onVideoPlay"
              @pause="onVideoPause"
              @ended="onVideoEnded"
              @error="onVideoError"
            ></video>
          </DetectionVideoFrame>
        </div>
      </section>

      <aside class="space-y-5">
        <section class="rounded-[28px] border border-white bg-white/88 p-5 shadow-[0_12px_40px_-20px_rgba(34,211,238,0.18)]">
          <button
            class="relative w-full rounded-[24px] border border-slate-200 bg-slate-50/90 p-4 text-left transition hover:border-cyan-300 hover:bg-cyan-50"
            @click="toggleDefectListPanel"
          >
            <span class="absolute -right-2 -top-2 flex min-h-7 min-w-7 items-center justify-center rounded-full bg-cyan-500 px-2 text-xs font-semibold text-white shadow-[0_10px_25px_-15px_rgba(6,182,212,0.85)]">
              {{ revealedDefects.length }}
            </span>
            <div class="flex items-center justify-between gap-3">
              <div>
                <div class="text-lg font-semibold text-slate-900">缺陷列表</div>
                <div class="mt-1 text-sm text-slate-500">点击后查看随视频进度实时更新的缺陷项</div>
              </div>
              <span class="rounded-full border border-cyan-200 bg-white px-3 py-1 text-xs font-semibold text-cyan-700">
                {{ showDefectListPanel ? '收起' : '展开' }}
              </span>
            </div>
            <div class="mt-3 flex items-center justify-end text-xs text-slate-500">
              <span>{{ playbackTimelineText }}</span>
            </div>
          </button>
          <div v-if="showDefectListPanel" class="mt-4 max-h-[560px] space-y-3 overflow-y-auto pr-1">
            <p v-if="displayedDefects.length === 0" class="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-400">
              当前没有可展示的缺陷截图。
            </p>
            <p v-else-if="revealedDefects.length === 0" class="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-400">
              播放视频后，缺陷项会按视频进度逐步出现。
            </p>
            <button
              v-for="defect in revealedDefects"
              :key="defect.id"
              class="w-full rounded-2xl border p-3 text-left transition"
              :class="selectedDefect?.id === defect.id ? 'border-cyan-300 bg-cyan-50' : 'border-slate-200 bg-slate-50 hover:border-cyan-200'"
              @click="selectDefect(defect)"
            >
              <div class="flex gap-3">
                <img
                  :src="resolveScreenshotUrl(defect.screenshot_path)"
                  class="h-16 w-16 rounded-xl object-cover"
                  alt="defect"
                  loading="lazy"
                  @error="markScreenshotBroken(defect.id)"
                />
                <div
                  v-if="false"
                  class="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-100 text-[11px] text-slate-400"
                >
                  截图缺失
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center justify-between gap-2">
                    <div class="truncate font-medium text-slate-900">{{ defect.class_name }}</div>
                    <span class="rounded-full px-2 py-0.5 text-[11px]" :class="severityClass(defect.severity)">
                      {{ severityLabel(defect.severity) }}
                    </span>
                  </div>
                  <div class="mt-1 text-xs text-slate-500">视频时间 {{ formatRoofTime(defect.video_time_ms / 1000) }} | 置信度 {{ Math.round(defect.confidence * 100) }}%</div>
                  <div class="mt-1 text-xs text-slate-400">{{ defect.latitude.toFixed(5) }}, {{ defect.longitude.toFixed(5) }}</div>
                </div>
              </div>
            </button>
          </div>
        </section>

      </aside>
    </main>

    <div
      v-if="showUploadPanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeUploadPanel"
    >
      <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(34,211,238,0.32)]">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">上传任务</h3>
            <p class="mt-1 text-sm text-slate-500">支持上传一个本地屋顶巡检视频，作为当前页面的演示任务。</p>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="closeUploadPanel"
          >
            关闭
          </button>
        </div>

        <div class="mt-4 space-y-4">
          <label class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">任务名称</div>
            <input
              v-model="uploadTaskName"
              type="text"
              placeholder="例如：综合楼屋顶巡检任务"
              class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-cyan-300"
            />
          </label>

          <label class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">选择视频文件</div>
            <input type="file" accept="video/*" @change="onVideoFileSelect" />
            <div class="mt-2 text-xs text-slate-500">{{ uploadVideoFile?.name || '尚未选择视频' }}</div>
          </label>

          <button
            class="w-full rounded-2xl bg-gradient-to-r from-cyan-400 to-sky-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:from-cyan-300 hover:to-sky-300 disabled:bg-slate-200 disabled:text-slate-400"
            :disabled="!uploadReady || uploadingTask"
            @click="persistUploadTask"
          >
            确认上传
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="showTaskPicker"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeTaskPicker"
    >
      <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(34,211,238,0.32)]">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">加载任务</h3>
            <p class="mt-1 text-sm text-slate-500">可切换后端屋顶任务，也可加载当前会话中上传的本地任务。</p>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="closeTaskPicker"
          >
            关闭
          </button>
        </div>

        <div v-if="tasks.length > 0" class="mt-4 max-h-[60vh] space-y-2 overflow-y-auto pr-1">
          <button
            v-for="task in tasks"
            :key="task.id"
            class="w-full rounded-2xl border px-4 py-3 text-left transition"
            :class="activeTaskId === task.id ? 'border-cyan-300 bg-cyan-50 text-cyan-700' : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-cyan-300 hover:bg-cyan-50/60'"
            @click="selectTask(task.id)"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="font-medium">{{ task.name }}</div>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">
                {{ task.source === 'upload' ? '本地上传' : task.status }}
              </span>
            </div>
            <div class="mt-1 text-xs text-slate-500">{{ task.video_name }}</div>
          </button>
        </div>
        <div v-else class="mt-4 rounded-2xl border border-dashed border-cyan-200 bg-cyan-50/60 px-4 py-10 text-center text-sm text-slate-600">
          暂无可加载任务，请先上传本地任务，或启动后端后再刷新任务列表。
        </div>
      </div>
    </div>

    <div
      v-if="showControlPanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeControlPanel"
    >
      <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(34,211,238,0.32)]">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">实时控制</h3>
            <p class="mt-1 text-sm text-slate-500">调整播放速度和缺陷筛选条件，便于快速核查屋顶任务。</p>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="closeControlPanel"
          >
            关闭
          </button>
        </div>

        <div class="mt-4 space-y-4">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div class="mb-3 flex items-center justify-between text-sm text-slate-600">
              <span>播放速度</span>
              <span>{{ playbackRate.toFixed(1) }} x</span>
            </div>
            <input v-model="playbackRate" type="range" min="0.5" max="2" step="0.1" class="w-full accent-cyan-500" />
          </div>

          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div class="mb-3 text-sm text-slate-600">缺陷筛选</div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="item in ['all', 'high', 'medium', 'low']"
                :key="item"
                class="rounded-full px-3 py-1 text-xs font-semibold"
                :class="severityFilter === item ? 'bg-cyan-100 text-cyan-700' : 'bg-white text-slate-600 ring-1 ring-slate-200'"
                @click="severityFilter = item as 'all' | 'high' | 'medium' | 'low'"
              >
                {{ item === 'all' ? '全部' : severityLabel(item) }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
