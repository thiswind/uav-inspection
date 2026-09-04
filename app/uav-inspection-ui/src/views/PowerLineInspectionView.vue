<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { powerApi, type PowerDetectResult, type PowerInfoResult, type PowerVideoItem } from '../api1/power'
import InspectionHeader from '../components/common/InspectionHeader.vue'
import DetectionVideoFrame from '../components/common/DetectionVideoFrame.vue'
import FloatingNotice from '../components/common/FloatingNotice.vue'

interface PowerTask {
  id: string
  taskName: string
  videoName: string
  videoUrl: string
  source: 'system' | 'upload'
}

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const sampleTasks = ref<PowerTask[]>([])
const uploadedTasks = ref<PowerTask[]>([])
const currentTaskId = ref('')
const powerInfo = ref<PowerInfoResult | null>(null)
const backendOnline = ref(false)
const inferenceReady = ref(false)
const loading = ref(false)
const detecting = ref(false)
const isPlaying = ref(false)
const videoCurrentTime = ref(0)
const videoDuration = ref(0)
const showTaskPicker = ref(false)
const showUploadPanel = ref(false)
const showControlPanel = ref(false)
const uploadTaskName = ref('')
const uploadVideoFile = ref<File | null>(null)
const uploadingTask = ref(false)
const apiLatency = ref(0)
const currentStats = ref({ Wire: 0, WirePole: 0 })
const detections = ref<PowerDetectResult['detections']>([])
const confThreshold = ref(0.3)
const iouThreshold = ref(0.45)
const autoDetectEnabled = ref(true)
const detectIntervalSec = ref(1)
const lastDetectBucket = ref(-1)
const lastCaptureSize = ref({ width: 0, height: 0 })
const message = ref('请选择一个杆路巡检任务开始演示。')
let healthTimer: number | null = null

const taskLibrary = computed(() => [...uploadedTasks.value, ...sampleTasks.value])
const currentTask = computed(() => taskLibrary.value.find((item) => item.id === currentTaskId.value) || null)
const currentVideoUrl = computed(() => currentTask.value?.videoUrl || '')
const currentVideoName = computed(() => currentTask.value?.videoName || '尚未选择视频')
const currentTaskName = computed(() => currentTask.value?.taskName || '未选择任务')
const canPlay = computed(() => Boolean(currentVideoUrl.value))
const uploadReady = computed(() => Boolean(uploadVideoFile.value))
const totalDetections = computed(() => detections.value.length)
const detectionSummary = computed(() => {
  if (!detections.value.length) return '当前帧暂无识别结果'
  return `当前帧识别 ${detections.value.length} 个目标`
})
const deviceText = computed(() => {
  if (!powerInfo.value) return '未知'
  return powerInfo.value.system.cuda_available ? `${powerInfo.value.system.device} / CUDA` : powerInfo.value.system.device
})
const statusText = computed(() => {
  if (!backendOnline.value) return '后端未就绪'
  if (!inferenceReady.value) return isPlaying.value ? '仅播放 · AI 未启用' : '基础模式 · AI 未启用'
  if (detecting.value) return '正在识别'
  if (isPlaying.value) return '播放中'
  return '待开始'
})

async function refreshHealth() {
  try {
    const result = await powerApi.getHealth()
    backendOnline.value = true
    inferenceReady.value = result.data.inference_available ?? result.data.status === 'ready'
  } catch {
    backendOnline.value = false
    inferenceReady.value = false
  }
}

async function loadPowerInfo() {
  try {
    const result = await powerApi.getInfo()
    powerInfo.value = result.data
  } catch {
    powerInfo.value = null
  }
}

function mapSampleTask(item: PowerVideoItem, index: number): PowerTask {
  return {
    id: item.id || `system-${index}-${item.name}`,
    taskName: item.task_name || item.name.replace(/\.[^/.]+$/, ''),
    videoName: item.name,
    videoUrl: item.url,
    source: 'system',
  }
}

async function loadSampleTasks() {
  try {
    const result = await powerApi.getVideos()
    sampleTasks.value = result.data.videos.map(mapSampleTask)
    if (!currentTaskId.value && sampleTasks.value.length > 0) {
      selectTask(sampleTasks.value[0])
    }
  } catch {
    message.value = '杆路示例视频加载失败，请检查后端媒体目录。'
  }
}

function resetDetectionState() {
  currentStats.value = { Wire: 0, WirePole: 0 }
  detections.value = []
  apiLatency.value = 0
  lastDetectBucket.value = -1
  lastCaptureSize.value = { width: 0, height: 0 }
  clearCanvas()
}

function stopVideo() {
  const video = videoRef.value
  if (!video) return
  video.pause()
  video.currentTime = 0
  isPlaying.value = false
}

function selectTask(task: PowerTask) {
  stopVideo()
  currentTaskId.value = task.id
  resetDetectionState()
  showTaskPicker.value = false
  message.value = `已加载任务：${task.taskName}`
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

function onVideoFileSelect(event: Event) {
  uploadVideoFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

function clearUploadDraft() {
  uploadTaskName.value = ''
  uploadVideoFile.value = null
}

async function confirmUploadTask() {
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
    const result = await powerApi.uploadTask(form)
    await loadSampleTasks()
    const task =
      sampleTasks.value.find((item) => item.id === result.data.id || item.videoUrl === result.data.url) ||
      sampleTasks.value.find((item) => item.videoName === result.data.video_name)

    clearUploadDraft()
    closeUploadPanel()
    if (task) {
      selectTask(task)
    }
    message.value = `任务已上传并写入记录：${taskName}`
  } catch {
    message.value = '上传失败，请检查后端上传接口。'
  } finally {
    uploadingTask.value = false
  }
}

async function togglePlay() {
  const video = videoRef.value
  if (!video || !canPlay.value) {
    message.value = '请先加载一个可播放的视频任务。'
    return
  }

  if (!video.paused) {
    video.pause()
    return
  }

  try {
    video.muted = true
    video.playsInline = true
    await video.play()
  } catch {
    isPlaying.value = false
    message.value = '视频播放失败，请重新点击播放或刷新页面后重试。'
  }
}

function replayVideo() {
  const video = videoRef.value
  if (!video) return
  video.currentTime = 0
  lastDetectBucket.value = -1
  void togglePlay()
}

function seekVideo(seconds: number) {
  if (!videoRef.value) return
  videoRef.value.currentTime = seconds
  videoCurrentTime.value = seconds
  lastDetectBucket.value = -1
}

function onVideoLoadedMetadata() {
  videoDuration.value = Number.isFinite(videoRef.value?.duration) ? videoRef.value?.duration || 0 : 0
  syncCanvasSize()
}

function toggleAutoDetect() {
  autoDetectEnabled.value = !autoDetectEnabled.value
  lastDetectBucket.value = -1
  message.value = autoDetectEnabled.value
    ? '自动识别已开启，播放时将按设定频率执行检测。'
    : '自动识别已关闭，视频将仅播放不检测。'
}

function onPlay() {
  isPlaying.value = true
  if (!autoDetectEnabled.value) {
    message.value = '视频正在播放，自动识别已关闭。'
    return
  }
  message.value = inferenceReady.value ? '正在进行杆路线路巡检识别。' : '视频正在播放；AI 检测尚未就绪，请安装对应模型与推理依赖。'
}

function onPause() {
  isPlaying.value = false
  if (canPlay.value) {
    message.value = '视频已暂停。'
  }
}

function onEnded() {
  isPlaying.value = false
  message.value = '演示播放完成，可以重新播放继续查看。'
}

function onVideoError() {
  isPlaying.value = false
  message.value = '视频无法播放，请重新选择任务。'
}

function clearCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
}

function syncCanvasSize() {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas) return
  const rect = video.getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height
  if (lastCaptureSize.value.width && lastCaptureSize.value.height && detections.value.length) {
    drawDetections(lastCaptureSize.value.width, lastCaptureSize.value.height)
  }
}

function calcCaptureSize(videoWidth: number, videoHeight: number) {
  const maxEdge = 640
  if (videoWidth >= videoHeight) {
    const width = Math.min(maxEdge, videoWidth)
    return { width, height: Math.round((width * videoHeight) / videoWidth) }
  }
  const height = Math.min(maxEdge, videoHeight)
  return { width: Math.round((height * videoWidth) / videoHeight), height }
}

async function onTimeUpdate() {
  const video = videoRef.value
  if (!video) return
  videoCurrentTime.value = video.currentTime
  if (!autoDetectEnabled.value || !inferenceReady.value || detecting.value) return

  const bucket = Math.floor(video.currentTime / Math.max(0.5, detectIntervalSec.value))
  if (bucket === lastDetectBucket.value) return
  lastDetectBucket.value = bucket
  await detectCurrentFrame()
}

async function detectCurrentFrame() {
  if (!inferenceReady.value) {
    message.value = 'AI 检测尚未就绪，请安装对应模型与推理依赖；视频仍可播放。'
    return
  }

  const video = videoRef.value
  if (!video) return
  const videoWidth = video.videoWidth || video.clientWidth
  const videoHeight = video.videoHeight || video.clientHeight
  if (!videoWidth || !videoHeight) return

  detecting.value = true
  try {
    const { width, height } = calcCaptureSize(videoWidth, videoHeight)
    const captureCanvas = document.createElement('canvas')
    captureCanvas.width = width
    captureCanvas.height = height
    const captureCtx = captureCanvas.getContext('2d')
    if (!captureCtx) return

    captureCtx.drawImage(video, 0, 0, width, height)
    const image = captureCanvas.toDataURL('image/jpeg', 0.75).split(',')[1]

    const startedAt = performance.now()
    const result = await powerApi.detectFrame(image, confThreshold.value, iouThreshold.value)
    apiLatency.value = Math.round(performance.now() - startedAt)
    detections.value = result.data.detections
    currentStats.value = result.data.stats
    lastCaptureSize.value = { width, height }
    drawDetections(width, height)
  } catch {
    message.value = '杆路检测失败，请确认后端模型已经正常加载。'
  } finally {
    detecting.value = false
  }
}

async function runManualDetect() {
  if (detecting.value) return
  await detectCurrentFrame()
}

function drawDetections(captureWidth: number, captureHeight: number) {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const rect = video.getBoundingClientRect()
  if (canvas.width !== rect.width || canvas.height !== rect.height) {
    canvas.width = rect.width
    canvas.height = rect.height
  }
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const videoWidth = video.videoWidth || canvas.width
  const videoHeight = video.videoHeight || canvas.height
  const canvasAspect = canvas.width / canvas.height
  const videoAspect = videoWidth / videoHeight

  let drawWidth = canvas.width
  let drawHeight = canvas.height
  let offsetX = 0
  let offsetY = 0

  if (canvasAspect > videoAspect) {
    drawWidth = canvas.height * videoAspect
    offsetX = (canvas.width - drawWidth) / 2
  } else {
    drawHeight = canvas.width / videoAspect
    offsetY = (canvas.height - drawHeight) / 2
  }

  const scaleX = drawWidth / captureWidth
  const scaleY = drawHeight / captureHeight
  const colors: Record<string, string> = {
    Wire: '#facc15',
    WirePole: '#4ade80',
  }

  ctx.font = '12px sans-serif'
  ctx.textBaseline = 'top'

  for (const item of detections.value) {
    const [x1, y1, x2, y2] = item.bbox
    const x = x1 * scaleX + offsetX
    const y = y1 * scaleY + offsetY
    const width = (x2 - x1) * scaleX
    const height = (y2 - y1) * scaleY
    const color = colors[item.name] || '#38bdf8'

    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, width, height)

    const label = `${item.cn} ${Math.round(item.conf * 100)}%`
    const labelWidth = ctx.measureText(label).width + 10
    ctx.fillStyle = color
    ctx.fillRect(x, Math.max(0, y - 20), labelWidth, 18)
    ctx.fillStyle = item.name === 'Wire' ? '#111827' : '#ffffff'
    ctx.fillText(label, x + 5, Math.max(0, y - 18))
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([refreshHealth(), loadSampleTasks(), loadPowerInfo()])
  loading.value = false
  healthTimer = window.setInterval(refreshHealth, 10000)
  window.addEventListener('resize', syncCanvasSize)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
  window.removeEventListener('resize', syncCanvasSize)
  stopVideo()
  for (const task of uploadedTasks.value) {
    URL.revokeObjectURL(task.videoUrl)
  }
})
</script>

<template>
  <div class="mobile-page relative min-h-screen overflow-x-hidden bg-slate-50 text-slate-800 xl:flex xl:h-screen xl:min-h-0 xl:flex-col xl:overflow-hidden">
    <div class="pointer-events-none absolute top-[-10%] right-[-6%] h-[40%] w-[40%] rounded-full bg-amber-300/20 blur-[120px]"></div>
    <div class="pointer-events-none absolute bottom-[-12%] left-[-6%] h-[40%] w-[40%] rounded-full bg-orange-300/16 blur-[120px]"></div>
    <div class="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgwLCAwLCAwLCAwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')]"></div>

    <div class="relative z-10 px-4 pt-4 md:px-6 xl:shrink-0">
      <InspectionHeader title="杆路线路巡检" :task-name="currentTaskName" :online="backendOnline">
        <template #actions>
          <button
            class="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-3 text-sm font-medium text-amber-700 shadow-[0_10px_25px_-18px_rgba(251,191,36,0.42)] transition hover:border-amber-300 hover:bg-amber-100"
            @click="toggleControlPanel"
          >
            实时控制
          </button>
          <button
            class="rounded-2xl bg-gradient-to-r from-amber-400 to-orange-400 px-5 py-3 text-sm font-medium text-slate-950 shadow-[0_10px_25px_-15px_rgba(251,191,36,0.9)] transition hover:from-amber-300 hover:to-orange-300"
            @click="openUploadPanel"
          >
            上传任务
          </button>
          <button
            class="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-medium text-slate-700 transition hover:border-amber-300 hover:bg-amber-50"
            @click="toggleTaskPicker"
          >
            加载任务
          </button>
        </template>
      </InspectionHeader>
    </div>

    <FloatingNotice :message="message" :tone="backendOnline ? 'info' : 'warning'" :duration="3500" centered />

    <main class="relative z-10 grid min-h-[calc(100vh-104px)] grid-cols-1 gap-4 px-4 pb-4 pt-2 md:px-6 md:pb-6 xl:min-h-0 xl:flex-1 xl:grid-cols-[360px_minmax(0,1fr)] xl:pb-3" data-testid="power-viewport-layout">
      <aside class="space-y-2.5 xl:min-h-0 xl:overflow-hidden" data-testid="power-left-panel">
        <section class="rounded-[24px] border border-white bg-white/88 p-3 shadow-[0_12px_40px_-20px_rgba(251,191,36,0.22)]">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold text-slate-900">任务摘要</h2>
            <span class="flex items-center gap-2 text-sm text-slate-600">
              <span class="h-2.5 w-2.5 rounded-full" :class="backendOnline ? 'bg-emerald-400' : 'bg-red-400'"></span>
              {{ backendOnline ? '后端在线' : '后端离线' }}
            </span>
          </div>

          <div class="mt-3 space-y-2 text-sm text-slate-600">
            <div class="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2">
              <div class="text-slate-500">当前视频</div>
              <div class="mt-1 font-semibold text-slate-900">{{ currentVideoName }}</div>
            </div>
            <div class="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2">
              <div class="text-slate-500">任务来源</div>
              <div class="mt-1 font-semibold text-slate-900">{{ currentTask?.source === 'upload' ? '本地上传' : '系统示例' }}</div>
            </div>
            <div class="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2">
              <div class="text-slate-500">系统状态</div>
              <div class="mt-1 font-semibold text-slate-900">{{ statusText }}</div>
            </div>
          </div>
        </section>

        <div class="grid grid-cols-2 gap-2">
          <div class="rounded-2xl border border-white bg-white/88 p-3 shadow-[0_10px_35px_-18px_rgba(251,191,36,0.32)]">
            <div class="text-xs uppercase tracking-[0.25em] text-amber-700">导线</div>
            <div class="mt-2 text-2xl font-semibold text-slate-900">{{ currentStats.Wire }}</div>
          </div>
          <div class="rounded-2xl border border-white bg-white/88 p-3 shadow-[0_10px_35px_-18px_rgba(74,222,128,0.28)]">
            <div class="text-xs uppercase tracking-[0.25em] text-emerald-700">电杆</div>
            <div class="mt-2 text-2xl font-semibold text-slate-900">{{ currentStats.WirePole }}</div>
          </div>
          <div class="rounded-2xl border border-white bg-white/88 p-3 shadow-[0_10px_35px_-18px_rgba(15,23,42,0.12)]">
            <div class="text-xs uppercase tracking-[0.25em] text-slate-500">当前目标</div>
            <div class="mt-2 text-2xl font-semibold text-slate-900">{{ totalDetections }}</div>
          </div>
          <div class="rounded-2xl border border-white bg-white/88 p-3 shadow-[0_10px_35px_-18px_rgba(251,191,36,0.22)]">
            <div class="text-xs uppercase tracking-[0.25em] text-orange-600">接口延迟</div>
            <div class="mt-2 text-2xl font-semibold text-slate-900">{{ apiLatency }} <span class="text-sm text-slate-500">ms</span></div>
          </div>
        </div>

        <section class="rounded-[24px] border border-white bg-white/88 p-3 shadow-[0_12px_40px_-20px_rgba(251,191,36,0.22)]">
          <h2 class="text-base font-semibold text-slate-900">模型信息</h2>
          <div class="mt-2 space-y-2 text-sm text-slate-600">
            <div class="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-1.5">
              <span>推理设备</span>
              <span class="font-medium text-slate-900">{{ deviceText }}</span>
            </div>
            <div class="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-1.5">
              <span>模型文件</span>
              <span class="max-w-[160px] truncate font-medium text-slate-900">{{ powerInfo?.model.name || '加载中' }}</span>
            </div>
            <div class="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-1.5">
              <div class="mb-2 text-xs text-slate-500">识别类别</div>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="item in powerInfo?.model.classes || []"
                  :key="item"
                  class="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
                >
                  {{ item }}
                </span>
              </div>
            </div>
          </div>
        </section>

        <section class="rounded-[24px] border border-white bg-white/88 p-4 shadow-[0_12px_40px_-20px_rgba(251,191,36,0.22)]" data-testid="power-recognition-summary">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-slate-900">识别摘要</h3>
              <p class="mt-1 text-sm leading-5 text-slate-500">{{ detectionSummary }}</p>
            </div>
            <div class="shrink-0 text-right text-[11px] leading-4 text-slate-500">
              <div>{{ autoDetectEnabled ? 'Auto On' : 'Auto Off' }}</div>
              <div>Conf {{ confThreshold.toFixed(2) }}</div>
              <div>IoU {{ iouThreshold.toFixed(2) }}</div>
            </div>
          </div>
        </section>

        <section class="rounded-[24px] border border-white bg-white/88 p-4 shadow-[0_12px_40px_-20px_rgba(251,191,36,0.22)]" data-testid="power-current-targets">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-sm font-semibold text-slate-900">当前帧目标</h3>
            <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{{ detections.length }}</span>
          </div>
          <div v-if="detections.length" class="mt-3 grid grid-cols-2 gap-2">
            <div
              v-for="(item, index) in detections.slice(0, 6)"
              :key="`${item.name}-${index}-${item.conf}`"
              class="flex min-w-0 items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50/90 px-2.5 py-2 text-sm"
            >
              <div class="min-w-0">
                <div class="truncate font-medium text-slate-900">{{ item.cn }}</div>
                <div class="truncate text-[11px] text-slate-500">{{ item.name }}</div>
              </div>
              <div
                class="shrink-0 rounded-full px-2 py-1 text-[11px] font-semibold"
                :class="item.name === 'Wire' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'"
              >
                {{ Math.round(item.conf * 100) }}%
              </div>
            </div>
          </div>
          <div v-else class="mt-3 rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-4 text-center text-sm text-slate-500">
            暂无识别目标
          </div>
        </section>
      </aside>

      <section class="min-h-0">
        <div class="rounded-[28px] border border-white bg-white/88 px-4 pb-2 pt-4 shadow-[0_12px_40px_-20px_rgba(251,191,36,0.22)] xl:flex xl:h-full xl:min-h-0 xl:flex-col">
          <div class="mb-2 flex items-center justify-end gap-4">
            <div class="flex flex-wrap items-center gap-3">
              <button
                class="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-amber-300 hover:bg-amber-50 disabled:text-slate-400"
                :disabled="!canPlay || !inferenceReady || detecting"
                @click="runManualDetect"
              >
                单帧识别
              </button>
            </div>
          </div>

          <DetectionVideoFrame
            class="h-[62vh] min-h-[360px] max-h-[680px] sm:min-h-[500px] xl:h-auto xl:min-h-0 xl:max-h-none xl:flex-1"
            data-testid="power-video-frame"
            label="YOLO 杆路实时检测"
            :status="detecting ? '帧分析中' : isPlaying ? '实时播放' : '等待启动'"
            :playing="isPlaying"
            :disabled="!canPlay"
            :current-time="videoCurrentTime"
            :duration="videoDuration"
            :empty="!canPlay && !loading"
            empty-text="请先上传任务或加载一个已有任务。"
            @toggle="togglePlay"
            @replay="replayVideo"
            @seek="seekVideo"
          >
            <video
              ref="videoRef"
              class="h-full w-full object-contain"
              :src="currentVideoUrl"
              crossorigin="anonymous"
              muted
              playsinline
              preload="auto"
              @play="onPlay"
              @pause="onPause"
              @ended="onEnded"
              @timeupdate="onTimeUpdate"
              @loadedmetadata="onVideoLoadedMetadata"
              @error="onVideoError"
            ></video>
            <canvas ref="canvasRef" class="pointer-events-none absolute inset-0 h-full w-full"></canvas>
          </DetectionVideoFrame>
        </div>

      </section>
    </main>

    <div
      v-if="showUploadPanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeUploadPanel"
    >
      <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(251,191,36,0.35)]">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">上传任务</h3>
            <p class="mt-1 text-sm text-slate-500">支持上传一个本地巡检视频，作为当前页面的演示任务。</p>
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
              placeholder="例如：北区杆路巡检任务"
              class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-amber-300"
            />
          </label>

          <label class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">选择视频文件</div>
            <input type="file" accept="video/*" @change="onVideoFileSelect" />
            <div class="mt-2 text-xs text-slate-500">{{ uploadVideoFile?.name || '尚未选择视频' }}</div>
          </label>

          <button
            class="w-full rounded-2xl bg-gradient-to-r from-amber-400 to-orange-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:from-amber-300 hover:to-orange-300 disabled:bg-slate-200 disabled:text-slate-400"
            :disabled="!uploadReady || uploadingTask"
            @click="confirmUploadTask"
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
      <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(251,191,36,0.35)]">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">加载任务</h3>
            <p class="mt-1 text-sm text-slate-500">可切换系统示例任务，也可加载当前会话中上传的本地任务。</p>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="closeTaskPicker"
          >
            关闭
          </button>
        </div>

        <div v-if="taskLibrary.length > 0" class="mt-4 max-h-[60vh] space-y-2 overflow-y-auto pr-1">
          <button
            v-for="task in taskLibrary"
            :key="task.id"
            class="w-full rounded-2xl border px-4 py-3 text-left transition"
            :class="currentTaskId === task.id ? 'border-amber-300 bg-amber-50 text-amber-700' : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-amber-300 hover:bg-amber-50/60'"
            @click="selectTask(task)"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="font-medium">{{ task.taskName }}</div>
              <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">
                {{ task.source === 'upload' ? '本地上传' : '系统示例' }}
              </span>
            </div>
            <div class="mt-1 text-xs text-slate-500">{{ task.videoName }}</div>
          </button>
        </div>
        <div v-else class="mt-4 rounded-2xl border border-dashed border-amber-200 bg-amber-50/60 px-4 py-10 text-center text-sm text-slate-600">
          暂无可加载任务，请先上传本地任务，或启动后端后再刷新任务列表。
        </div>
      </div>
    </div>

    <div
      v-if="showControlPanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeControlPanel"
    >
      <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(251,191,36,0.35)]">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">实时控制</h3>
            <p class="mt-1 text-sm text-slate-500">调整当前巡检任务的检测阈值和自动识别策略。</p>
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
              <span>置信度</span>
              <span>{{ confThreshold.toFixed(2) }}</span>
            </div>
            <input v-model="confThreshold" type="range" min="0.1" max="0.9" step="0.01" class="w-full accent-amber-400" />

            <div class="mb-3 mt-5 flex items-center justify-between text-sm text-slate-600">
              <span>IOU</span>
              <span>{{ iouThreshold.toFixed(2) }}</span>
            </div>
            <input v-model="iouThreshold" type="range" min="0.1" max="0.9" step="0.01" class="w-full accent-amber-400" />
          </div>

          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div class="mb-3 flex items-center justify-between text-sm text-slate-600">
              <span>自动识别</span>
              <button
                class="rounded-full px-3 py-1 text-xs font-semibold"
                :class="autoDetectEnabled ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-600'"
                @click="toggleAutoDetect"
              >
                {{ autoDetectEnabled ? '已开启' : '已关闭' }}
              </button>
            </div>

            <div class="mb-3 mt-5 flex items-center justify-between text-sm text-slate-600">
              <span>检测间隔</span>
              <span>{{ detectIntervalSec.toFixed(1) }} s</span>
            </div>
            <input v-model="detectIntervalSec" type="range" min="0.5" max="3" step="0.1" class="w-full accent-amber-400" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
