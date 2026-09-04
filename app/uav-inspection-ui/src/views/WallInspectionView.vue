<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  Check,
  CloudUpload,
  FileDown,
  ListVideo,
  Loader2,
  MapPinned,
  Pencil,
  ShieldAlert,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-vue-next'
import WallLocationMap from '../components/wall/WallLocationMap.vue'
import InspectionHeader from '../components/common/InspectionHeader.vue'
import DetectionVideoFrame from '../components/common/DetectionVideoFrame.vue'
import FloatingNotice from '../components/common/FloatingNotice.vue'
import { findTelemetry, parseSrt, type TelemetryFrame } from '../utils/srtParser'
import { webPath } from '../utils/webroot'
import {
  wallApi,
  type WallAssessmentResult,
  type WallDetectResult,
  type WallDetectionLogItem,
  type WallStats,
  type WallTaskAnnotationFrame,
  type WallVideoItem,
} from '../api1/wall'

type WallTaskSource = 'system' | 'upload'
type UploadMode = 'file' | 'path'
type WallInsightPanel = 'assessment' | 'location'
type WallClassName = WallDetectResult['detections'][number]['name']
type WallDetectionItem = WallDetectResult['detections'][number]
type TaskPreloadState = 'idle' | 'loading' | 'loaded' | 'error'
type WallVideoFrameMetadata = { mediaTime?: number }
type WallVideoFrameCallback = (now: number, metadata: WallVideoFrameMetadata) => void
type WallVideoElement = HTMLVideoElement & {
  requestVideoFrameCallback?: (callback: WallVideoFrameCallback) => number
  cancelVideoFrameCallback?: (handle: number) => void
}

interface WallTask {
  id: string
  taskName: string
  videoName: string
  videoUrl: string
  startAt: number
  source: WallTaskSource
  subtitleName: string
  subtitleUrl: string
  telemetry: TelemetryFrame[]
}

interface WallDetectionSnapshot {
  id?: string
  time: number
  detections: WallDetectionItem[]
  imageUrl?: string
  imageSize?: { width?: number; height?: number }
  telemetry?: TelemetryFrame | null
}

const emptyStats: WallStats = {
  Crack: 0,
  Seepage: 0,
  TileSpalling: 0,
  Hollowing: 0,
}

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const tasks = ref<WallTask[]>([])
const uploadedTaskIds = ref<string[]>([])
const currentTaskId = ref('')
const taskPreloadStates = ref<Record<string, TaskPreloadState>>({})
const backendOnline = ref(false)
const inferenceReady = ref(false)
const loading = ref(false)
const detecting = ref(false)
const isPlaying = ref(false)
const showTaskPicker = ref(false)
const showUploadPanel = ref(false)
const showControlPanel = ref(false)
const activeInsightPanel = ref<WallInsightPanel | null>(null)
const uploadMode = ref<UploadMode>('file')
const uploadTaskName = ref('')
const uploadVideoFile = ref<File | null>(null)
const uploadSubtitleFile = ref<File | null>(null)
const uploadSourcePath = ref('')
const uploadSubtitlePath = ref('')
const uploadingTask = ref(false)
const renamingTaskId = ref('')
const renameTaskName = ref('')
const taskActionBusyId = ref('')
const apiLatency = ref(0)
const currentStats = ref<WallStats>({ ...emptyStats })
const detections = ref<WallDetectResult['detections']>([])
const detectionHistory = ref<WallDetectionSnapshot[]>([])
const persistedAssessment = ref<WallAssessmentResult | null>(null)
const insightTaskId = ref('')
const insightHistory = ref<WallDetectionSnapshot[]>([])
const insightAssessment = ref<WallAssessmentResult | null>(null)
const selectedLogId = ref('')
const insightLoading = ref(false)
const srtFrames = ref<TelemetryFrame[]>([])
const currentTelemetry = ref<TelemetryFrame | null>(null)
const annotationFrames = ref<WallTaskAnnotationFrame[]>([])
const annotationFps = ref(30)
const minObviousConfidence = 0.18
const defaultDemoConfidence = 0.30
const confThreshold = ref(minObviousConfidence)
const iouThreshold = ref(0.45)
const frameDetectionMode = '逐帧'
const lastCaptureSize = ref({ width: 0, height: 0 })
const videoCurrentTime = ref(0)
const videoDuration = ref(0)
const progressValue = ref(0)
const exportingReport = ref(false)
const message = ref('请选择一个建筑外墙巡检任务开始演示。')
let healthTimer: number | null = null
let detectAfterSeek = false
let videoFrameCallbackId: number | null = null
let animationFrameCallbackId: number | null = null
let lastRenderedAnnotationFrame = -1
let lastDetectMediaTime = Number.NEGATIVE_INFINITY
let detectionRequestSerial = 0
let lastSavedLogTime = Number.NEGATIVE_INFINITY
let logSaving = false
const preloadVideos = new Map<string, HTMLVideoElement>()

const currentTask = computed(() => tasks.value.find((item) => item.id === currentTaskId.value) || null)
const currentVideoUrl = computed(() => currentTask.value?.videoUrl || '')
const currentVideoName = computed(() => currentTask.value?.videoName || '尚未选择视频')
const currentTaskName = computed(() => currentTask.value?.taskName || '未选择任务')
const canPlay = computed(() => Boolean(currentVideoUrl.value))
const uploadReady = computed(() => uploadMode.value === 'file'
  ? Boolean(uploadVideoFile.value && uploadSubtitleFile.value)
  : Boolean(uploadSourcePath.value.trim() && uploadSubtitlePath.value.trim()))
const totalDetections = computed(() => detections.value.length)
const detectionSummary = computed(() => {
  if (!detections.value.length) return '当前帧暂无识别结果'
  return `当前帧识别 ${detections.value.length} 个外墙风险目标`
})
const statCards = computed(() => [
  { label: '裂缝', value: currentStats.value.Crack, className: 'text-red-600', barClass: 'bg-red-500' },
  { label: '渗水', value: currentStats.value.Seepage, className: 'text-teal-600', barClass: 'bg-teal-500' },
  { label: '面砖脱落', value: currentStats.value.TileSpalling, className: 'text-amber-600', barClass: 'bg-amber-500' },
])
const assessmentFrames = computed<WallDetectionSnapshot[]>(() => {
  if (activeInsightPanel.value) return insightHistory.value
  if (detectionHistory.value.some((frame) => frame.detections.length > 0)) return detectionHistory.value
  const annotated = annotationFrames.value
    .filter((frame) => frame.detections.length > 0)
    .map((frame) => ({ time: frame.time, detections: frame.detections }))
  if (annotated.length) return annotated
  return detections.value.length ? [{ time: videoCurrentTime.value, detections: detections.value }] : []
})
const assessmentDetections = computed(() => assessmentFrames.value.flatMap((frame) => frame.detections))
const aggregateStats = computed(() => buildStatsFromDetections(assessmentDetections.value))
const averageDetectionConfidence = computed(() => {
  if (!assessmentDetections.value.length) return 0
  return assessmentDetections.value.reduce((sum, item) => sum + item.conf, 0) / assessmentDetections.value.length
})
const defectAssessment = computed(() => {
  const storedAssessment = activeInsightPanel.value ? insightAssessment.value : persistedAssessment.value
  if (storedAssessment && assessmentFrames.value.length) {
    const assessment = storedAssessment
    const high = assessment.level === '高风险'
    const medium = assessment.level === '中风险'
    return {
      score: assessment.score,
      level: assessment.level,
      title: assessment.title,
      summary: assessment.summary,
      actions: assessment.actions,
      tone: high ? 'text-rose-700' : medium ? 'text-amber-700' : 'text-emerald-700',
      panel: high ? 'border-rose-200 bg-rose-50' : medium ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50',
    }
  }
  const stats = aggregateStats.value
  const total = assessmentDetections.value.length
  const score = Math.min(100, Math.round(
    stats.Crack * 10 + stats.Seepage * 14 + stats.TileSpalling * 24 + averageDetectionConfidence.value * 8,
  ))
  if (!total) {
    return {
      score: 0,
      level: '低风险',
      title: '暂未发现明显缺陷',
      tone: 'text-emerald-700',
      panel: 'border-emerald-200 bg-emerald-50',
      summary: '当前任务尚无有效缺陷记录，建议完成整段视频检测后再形成最终结论。',
      actions: ['继续完成全立面视频巡检', '保持相同航线与焦距便于后续复核', '发现异常后补拍近景和侧向画面'],
    }
  }
  if (score >= 60 || stats.TileSpalling >= 2) {
    return {
      score,
      level: '高风险',
      title: '存在重点外墙缺陷',
      tone: 'text-rose-700',
      panel: 'border-rose-200 bg-rose-50',
      summary: '检测记录中包含高权重面砖脱落或多处复合缺陷，应优先安排现场复核和安全隔离。',
      actions: ['立即复核面砖脱落区域并设置地面警戒', '对裂缝端部和渗水边界补拍近景', '形成维修工单并在处置后执行同角度复检'],
    }
  }
  if (score >= 25) {
    return {
      score,
      level: '中风险',
      title: '建议安排专项复核',
      tone: 'text-amber-700',
      panel: 'border-amber-200 bg-amber-50',
      summary: '当前存在局部裂缝、渗水或单处脱落记录，建议结合现场距离和构件位置确认影响范围。',
      actions: ['7 日内安排人工近距离复核', '记录缺陷长度、面积和相邻构件状态', '纳入下一轮无人机巡检重点点位'],
    }
  }
  return {
    score,
    level: '低风险',
    title: '以观察维护为主',
    tone: 'text-teal-700',
    panel: 'border-teal-200 bg-teal-50',
    summary: '仅发现少量低置信度或低权重记录，可先建立基线并持续观察变化。',
    actions: ['保存当前画面作为缺陷基线', '下一巡检周期复拍相同区域', '若置信度或范围上升则转入专项复核'],
  }
})
const insightTask = computed(() => tasks.value.find((item) => item.id === insightTaskId.value) || null)
const detectionLogEntries = computed(() => assessmentFrames.value.filter((item) => item.imageUrl).slice().reverse())
const selectedDetectionLog = computed(() => detectionLogEntries.value.find((item) => item.id === selectedLogId.value) || detectionLogEntries.value[0] || null)
const selectedLogStats = computed(() => buildStatsFromDetections(selectedDetectionLog.value?.detections || []))
const selectedLogAverageConfidence = computed(() => {
  const items = selectedDetectionLog.value?.detections || []
  return items.length ? items.reduce((sum, item) => sum + item.conf, 0) / items.length : 0
})
const selectedLogDamageSummary = computed(() => {
  const stats = selectedLogStats.value
  const parts = [
    stats.Crack ? `裂缝 ${stats.Crack} 处` : '',
    stats.Seepage ? `渗水 ${stats.Seepage} 处` : '',
    stats.TileSpalling ? `面砖脱落/外墙破损 ${stats.TileSpalling} 处` : '',
    stats.Hollowing ? `空鼓风险 ${stats.Hollowing} 处` : '',
  ].filter(Boolean)
  return parts.length
    ? `该日志画面检测到${parts.join('、')}，平均置信度 ${Math.round(selectedLogAverageConfidence.value * 100)}%。`
    : '该日志画面未记录有效缺陷。'
})
const displayedLocationTelemetry = computed(() => selectedDetectionLog.value?.telemetry || currentTelemetry.value)
const geoLocationPoints = computed(() => assessmentFrames.value.flatMap((snapshot) => {
  const telemetry = snapshot.telemetry
  if (!telemetry?.latitude || !telemetry.longitude) return []
  const primary = snapshot.detections[0]
  const labels = Array.from(new Set(snapshot.detections.map((item) => item.cn))).join('、')
  return [{
    id: snapshot.id || `gps-${snapshot.time}`,
    latitude: telemetry.latitude,
    longitude: telemetry.longitude,
    time: snapshot.time,
    label: labels || '检测日志',
    color: detectionColor(primary?.name || 'TileSpalling'),
  }]
}))
const currentMapPoint = computed(() => {
  const selectedTelemetry = selectedDetectionLog.value?.telemetry
  if (activeInsightPanel.value && selectedTelemetry?.latitude && selectedTelemetry.longitude) {
    return { latitude: selectedTelemetry.latitude, longitude: selectedTelemetry.longitude }
  }
  return currentTelemetry.value?.latitude && currentTelemetry.value.longitude
    ? { latitude: currentTelemetry.value.latitude, longitude: currentTelemetry.value.longitude }
    : null
})

async function refreshHealth() {
  try {
    const result = await wallApi.getHealth()
    backendOnline.value = true
    inferenceReady.value = result.data.inference_available ?? result.data.status === 'ready'
  } catch {
    backendOnline.value = false
    inferenceReady.value = false
  }
}

async function loadWallConfig() {
  try {
    const result = await wallApi.getInfo()
    confThreshold.value = Math.max(minObviousConfidence, Math.min(defaultDemoConfidence, result.data.config.confidence || defaultDemoConfidence))
    iouThreshold.value = result.data.config.iou
  } catch {}
}

function mapVideoTask(item: WallVideoItem, index: number, telemetry: TelemetryFrame[] = []): WallTask {
  const id = item.id || `system-${index}-${item.name}`
  const demoStartAt = id === 'wall_demo_damage' || item.name === 'wall_facade_damage_demo.mp4' ? 300 : 0
  return {
    id,
    taskName: item.task_name || item.name.replace(/\.[^/.]+$/, ''),
    videoName: item.name,
    videoUrl: item.url,
    startAt: Math.max(0, Number(item.start_at || demoStartAt)),
    source: item.source === 'upload' || uploadedTaskIds.value.includes(id) ? 'upload' : 'system',
    subtitleName: item.subtitle_name || '',
    subtitleUrl: item.subtitle_url || '',
    telemetry,
  }
}

async function loadVideoTasks() {
  try {
    const result = await wallApi.getVideos()
    tasks.value = await Promise.all(result.data.videos.map(async (item, index) => {
      if (!item.subtitle_url) return mapVideoTask(item, index)
      try {
        const response = await fetch(item.subtitle_url)
        const content = response.ok ? await response.text() : ''
        return mapVideoTask(item, index, parseSrt(content))
      } catch {
        return mapVideoTask(item, index)
      }
    }))
    preloadAllTasks()
    if (currentTaskId.value && !tasks.value.some((item) => item.id === currentTaskId.value)) {
      currentTaskId.value = ''
    }
    if (!currentTaskId.value && tasks.value.length > 0) {
      selectTask(tasks.value.find((item) => item.startAt > 0) || tasks.value[0])
    } else if (!tasks.value.length) {
      message.value = '当前没有外墙巡检视频，可上传一段本地视频开始检测。'
    }
  } catch {
    message.value = '外墙任务列表加载失败，请检查后端服务。'
  }
}

function extractApiErrorMessage(error: unknown, fallback: string) {
  const responseData = (error as { response?: { data?: { detail?: string; message?: string } } }).response?.data
  return responseData?.detail || responseData?.message || fallback
}

function setTaskPreloadState(taskId: string, state: TaskPreloadState) {
  taskPreloadStates.value = { ...taskPreloadStates.value, [taskId]: state }
}

function cleanupPreloadVideos(validTaskIds = new Set<string>()) {
  for (const [taskId, video] of preloadVideos.entries()) {
    if (validTaskIds.has(taskId)) continue
    video.pause()
    video.removeAttribute('src')
    video.load()
    preloadVideos.delete(taskId)
  }

  taskPreloadStates.value = Object.fromEntries(
    Object.entries(taskPreloadStates.value).filter(([taskId]) => validTaskIds.has(taskId)),
  )
}

function preloadTaskVideo(task: WallTask) {
  const state = taskPreloadStates.value[task.id]
  if (state === 'loading' || state === 'loaded') return

  setTaskPreloadState(task.id, 'loading')
  const video = document.createElement('video')
  video.preload = 'auto'
  video.muted = true
  video.playsInline = true
  video.crossOrigin = 'anonymous'

  const markLoaded = () => setTaskPreloadState(task.id, 'loaded')
  const markError = () => setTaskPreloadState(task.id, 'error')
  video.addEventListener('loadeddata', markLoaded, { once: true })
  video.addEventListener('canplaythrough', markLoaded, { once: true })
  video.addEventListener('error', markError, { once: true })

  preloadVideos.set(task.id, video)
  video.src = task.videoUrl
  video.load()
}

function preloadAllTasks() {
  const validTaskIds = new Set(tasks.value.map((task) => task.id))
  cleanupPreloadVideos(validTaskIds)
  tasks.value.forEach(preloadTaskVideo)
}

function preloadStatusText(task: WallTask) {
  const state = taskPreloadStates.value[task.id] || 'idle'
  if (state === 'loaded') return '已加载'
  if (state === 'loading') return '预加载中'
  if (state === 'error') return '加载失败'
  return '待加载'
}

function resetDetectionState() {
  detectionRequestSerial += 1
  detecting.value = false
  currentStats.value = { ...emptyStats }
  detections.value = []
  detectionHistory.value = []
  persistedAssessment.value = null
  annotationFrames.value = []
  annotationFps.value = 30
  apiLatency.value = 0
  resetFrameDetectionCursor()
  lastCaptureSize.value = { width: 0, height: 0 }
  clearCanvas()
}

function resetFrameDetectionCursor() {
  lastRenderedAnnotationFrame = -1
  lastDetectMediaTime = Number.NEGATIVE_INFINITY
  lastSavedLogTime = Number.NEGATIVE_INFINITY
}

function syncTelemetry(time = videoRef.value?.currentTime || 0) {
  currentTelemetry.value = findTelemetry(srtFrames.value, time)
}

function mapDetectionLog(item: WallDetectionLogItem): WallDetectionSnapshot {
  const telemetry = item.telemetry && Object.keys(item.telemetry).length
    ? ({
        frameCnt: Number(item.telemetry.frameCnt || 0),
        time: Number(item.time || 0),
        endTime: Number(item.time || 0),
        datetime: String(item.telemetry.datetime || ''),
        latitude: Number(item.telemetry.latitude || 0),
        longitude: Number(item.telemetry.longitude || 0),
        relAlt: Number(item.telemetry.relAlt || 0),
        absAlt: Number(item.telemetry.absAlt || 0),
        gbYaw: Number(item.telemetry.gbYaw || 0),
        gbPitch: Number(item.telemetry.gbPitch || 0),
        gbRoll: Number(item.telemetry.gbRoll || 0),
        iso: 0,
        shutter: '',
        fnum: 0,
        focalLen: 0,
      } satisfies TelemetryFrame)
    : null
  return {
    id: item.id,
    time: item.time,
    detections: item.detections,
    imageUrl: item.image_url,
    imageSize: item.image_size,
    telemetry,
  }
}

async function loadTaskLogs(task: WallTask) {
  try {
    const result = await wallApi.getTaskLogs(task.id)
    if (currentTaskId.value !== task.id) return
    detectionHistory.value = result.data.logs.map(mapDetectionLog)
    persistedAssessment.value = result.data.assessment
  } catch {
    if (currentTaskId.value === task.id) message.value = `已加载任务：${task.taskName}，检测日志读取失败。`
  }
}

async function loadInsightTask(taskId: string) {
  if (!taskId) return
  insightTaskId.value = taskId
  insightLoading.value = true
  insightHistory.value = []
  insightAssessment.value = null
  selectedLogId.value = ''
  try {
    const result = await wallApi.getTaskLogs(taskId)
    if (insightTaskId.value !== taskId) return
    const logs = result.data.logs.map(mapDetectionLog)
    insightHistory.value = logs
    insightAssessment.value = result.data.assessment
    selectedLogId.value = logs[logs.length - 1]?.id || ''
  } catch {
    if (insightTaskId.value === taskId) message.value = '任务日志读取失败，请检查后端日志目录。'
  } finally {
    if (insightTaskId.value === taskId) insightLoading.value = false
  }
}

function onInsightTaskChange() {
  void loadInsightTask(insightTaskId.value)
}

function stopFrameDetectionLoop() {
  const video = videoRef.value as WallVideoElement | null
  if (videoFrameCallbackId !== null) {
    video?.cancelVideoFrameCallback?.(videoFrameCallbackId)
    videoFrameCallbackId = null
  }
  if (animationFrameCallbackId !== null) {
    cancelAnimationFrame(animationFrameCallbackId)
    animationFrameCallbackId = null
  }
}

function tryDetectRenderedFrame(mediaTime = videoRef.value?.currentTime || 0) {
  const video = videoRef.value
  syncTelemetry(mediaTime)
  if (!video || video.paused || video.ended || video.seeking) return
  if (!inferenceReady.value) {
    refreshDisplayDetectionsForFrame(mediaTime)
    return
  }
  if (detecting.value || mediaTime - lastDetectMediaTime < 0.2) return
  lastDetectMediaTime = mediaTime
  void detectCurrentFrame(mediaTime)
}

function startFrameDetectionLoop() {
  stopFrameDetectionLoop()
  const video = videoRef.value as WallVideoElement | null
  if (!video) return

  if (video.requestVideoFrameCallback) {
    const run: WallVideoFrameCallback = (_now, metadata) => {
      videoFrameCallbackId = null
      const currentVideo = videoRef.value as WallVideoElement | null
      if (!currentVideo || currentVideo.paused || currentVideo.ended) return
      const mediaTime = Number.isFinite(metadata.mediaTime) ? Number(metadata.mediaTime) : currentVideo.currentTime
      tryDetectRenderedFrame(mediaTime)
      videoFrameCallbackId = currentVideo.requestVideoFrameCallback?.(run) ?? null
    }
    videoFrameCallbackId = video.requestVideoFrameCallback(run)
    return
  }

  const run = () => {
    const currentVideo = videoRef.value
    if (!currentVideo || currentVideo.paused || currentVideo.ended) {
      animationFrameCallbackId = null
      return
    }
    tryDetectRenderedFrame(currentVideo.currentTime)
    animationFrameCallbackId = requestAnimationFrame(run)
  }
  animationFrameCallbackId = requestAnimationFrame(run)
}

function stopVideo() {
  const video = videoRef.value
  if (!video) return
  stopFrameDetectionLoop()
  video.pause()
  video.currentTime = 0
  isPlaying.value = false
}

function resetVideoProgress() {
  videoCurrentTime.value = 0
  videoDuration.value = 0
  progressValue.value = 0
}

function selectTask(task: WallTask) {
  stopVideo()
  currentTaskId.value = task.id
  resetDetectionState()
  resetVideoProgress()
  srtFrames.value = task.telemetry
  syncTelemetry(task.startAt)
  preloadTaskVideo(task)
  showTaskPicker.value = false
  cancelRenameTask()
  message.value = `已加载任务：${task.taskName}，字幕定位 ${task.telemetry.length} 条。`
  void loadTaskAnnotations(task)
  void loadTaskLogs(task)
}

async function loadTaskAnnotations(task: WallTask) {
  const startedAt = performance.now()
  try {
    const result = await wallApi.getTaskAnnotations(task.id)
    if (currentTaskId.value !== task.id) return

    apiLatency.value = Math.round(performance.now() - startedAt)
    annotationFrames.value = result.data.frames
    annotationFps.value = result.data.fps || 30
    const markedFrames = annotationFrames.value.filter((frame) => frame.detections.length > 0).length
    message.value = markedFrames
      ? `已加载任务：${task.taskName}，标注帧 ${markedFrames} 组。`
      : `已加载任务：${task.taskName}，暂无标注框。`
    refreshDisplayDetectionsForFrame()
  } catch {
    if (currentTaskId.value !== task.id) return
    annotationFrames.value = []
    message.value = `已加载任务：${task.taskName}，标注数据读取失败。`
    refreshDisplayDetectionsForFrame()
  }
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

function beginRenameTask(task: WallTask) {
  if (taskActionBusyId.value) return
  renamingTaskId.value = task.id
  renameTaskName.value = task.taskName
}

function cancelRenameTask() {
  renamingTaskId.value = ''
  renameTaskName.value = ''
}

async function confirmRenameTask(task: WallTask) {
  const taskName = renameTaskName.value.trim()
  if (!taskName) {
    message.value = '任务名称不能为空。'
    return
  }
  if (taskName === task.taskName) {
    cancelRenameTask()
    return
  }

  taskActionBusyId.value = task.id
  try {
    await wallApi.renameTask(task.id, taskName)
    await loadVideoTasks()
    cancelRenameTask()
    message.value = `任务已重命名为：${taskName}`
  } catch (error) {
    message.value = extractApiErrorMessage(error, '重命名失败，请检查后端任务记录。')
  } finally {
    taskActionBusyId.value = ''
  }
}

async function deleteTask(task: WallTask) {
  if (taskActionBusyId.value) return
  if (!window.confirm(`确认删除任务“${task.taskName}”吗？删除后无法从任务列表中重新加载。`)) return

  const removedCurrentTask = currentTaskId.value === task.id
  taskActionBusyId.value = task.id
  try {
    await wallApi.deleteTask(task.id)
    const preloadedVideo = preloadVideos.get(task.id)
    if (preloadedVideo) {
      preloadedVideo.pause()
      preloadedVideo.removeAttribute('src')
      preloadedVideo.load()
      preloadVideos.delete(task.id)
    }
    if (removedCurrentTask) {
      stopVideo()
      currentTaskId.value = ''
      resetDetectionState()
      resetVideoProgress()
    }
    await loadVideoTasks()
    cancelRenameTask()
    message.value = `任务已删除：${task.taskName}`
  } catch (error) {
    message.value = extractApiErrorMessage(error, '删除失败，请检查后端任务记录目录。')
  } finally {
    taskActionBusyId.value = ''
  }
}

function onVideoFileSelect(event: Event) {
  uploadVideoFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

function onSubtitleFileSelect(event: Event) {
  uploadSubtitleFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

function clearUploadDraft() {
  uploadTaskName.value = ''
  uploadVideoFile.value = null
  uploadSubtitleFile.value = null
  uploadSubtitlePath.value = ''
}

async function confirmUploadTask() {
  if (uploadMode.value === 'file' && (!uploadVideoFile.value || !uploadSubtitleFile.value)) {
    message.value = '请同时选择检测视频和对应的字幕文件。'
    return
  }
  if (uploadMode.value === 'path' && (!uploadSourcePath.value.trim() || !uploadSubtitlePath.value.trim())) {
    message.value = '请输入视频和对应字幕的完整路径。'
    return
  }

  const sourceName = uploadMode.value === 'file'
    ? uploadVideoFile.value!.name
    : uploadSourcePath.value.trim().split(/[\\/]/).pop() || 'wall-task.mp4'
  const taskName = uploadTaskName.value.trim() || sourceName.replace(/\.[^/.]+$/, '')

  uploadingTask.value = true
  try {
    const result = uploadMode.value === 'file'
      ? await (() => {
          const form = new FormData()
          form.append('task_name', taskName)
          form.append('video', uploadVideoFile.value!)
          form.append('subtitle', uploadSubtitleFile.value!)
          return wallApi.uploadTask(form)
        })()
      : await wallApi.importTaskFromPath({
          task_name: taskName,
          video_path: uploadSourcePath.value.trim(),
          subtitle_path: uploadSubtitlePath.value.trim(),
        })
    uploadedTaskIds.value = Array.from(new Set([...uploadedTaskIds.value, result.data.id]))
    await loadVideoTasks()
    const task =
      tasks.value.find((item) => item.id === result.data.id || item.videoUrl === result.data.url) ||
      tasks.value.find((item) => item.videoName === (result.data.video_name || result.data.name))

    clearUploadDraft()
    closeUploadPanel()
    if (task) {
      selectTask(task)
    }
    message.value = uploadMode.value === 'path'
      ? `源文件已保留，任务已复制到 Demo 内部目录：${taskName}`
      : `任务已上传并写入记录：${taskName}`
  } catch (error) {
    message.value = extractApiErrorMessage(error, uploadMode.value === 'path' ? '复制导入失败，请检查文件路径和磁盘空间。' : '上传失败，请检查后端上传接口。')
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
    detectAfterSeek = seekToTaskStartIfNeeded()
    await video.play()
  } catch {
    isPlaying.value = false
    message.value = '视频播放失败，请重新点击播放或刷新页面后重试。'
  }
}

function replayVideo() {
  const video = videoRef.value
  if (!video) return
  video.currentTime = currentTask.value?.startAt || 0
  updateVideoProgress()
  resetFrameDetectionCursor()
  void togglePlay()
}

function seekVideoSeconds(seconds: number) {
  const video = videoRef.value
  if (!video) return
  video.currentTime = seconds
  videoCurrentTime.value = seconds
  progressValue.value = videoDuration.value > 0 ? (seconds / videoDuration.value) * 100 : 0
  detectAfterSeek = !video.paused
  resetFrameDetectionCursor()
}

async function applyConfig() {
  try {
    await wallApi.updateConfig(confThreshold.value, iouThreshold.value)
  } catch {
    message.value = '参数同步失败，当前页面仍会按本地设置发起检测。'
  }
}

function onPlay() {
  isPlaying.value = true
  startFrameDetectionLoop()
  message.value = inferenceReady.value
    ? '正在对视频当前画面进行实时建筑外墙检测。'
    : annotationFrames.value.length
      ? '实时检测尚未就绪，正在按已有标注数据进行建筑外墙巡检展示。'
      : '视频正在播放；实时检测尚未就绪，请安装对应模型与推理依赖。'
  if (detectAfterSeek && videoRef.value?.seeking) return
  detectAfterSeek = false
  resetFrameDetectionCursor()
  tryDetectRenderedFrame()
}

function onPause() {
  isPlaying.value = false
  stopFrameDetectionLoop()
  detectionRequestSerial += 1
  detecting.value = false
  if (canPlay.value) {
    message.value = '视频已暂停。'
  }
}

function onEnded() {
  isPlaying.value = false
  stopFrameDetectionLoop()
  detectionRequestSerial += 1
  detecting.value = false
  message.value = '演示播放完成，可重新播放继续查看。'
}

function onVideoError() {
  if (!currentVideoUrl.value) return
  isPlaying.value = false
  stopFrameDetectionLoop()
  detectionRequestSerial += 1
  detecting.value = false
  message.value = '视频无法播放，请重新选择任务。'
}

function onLoadedMetadata() {
  syncCanvasSize()
  seekToTaskStartIfNeeded(true)
  updateVideoProgress()
  syncTelemetry()
}

function onSeeked() {
  updateVideoProgress()
  syncTelemetry()
  if (!detectAfterSeek || videoRef.value?.paused) return
  detectAfterSeek = false
  resetFrameDetectionCursor()
  tryDetectRenderedFrame()
}

function onTimeUpdate() {
  updateVideoProgress()
  syncTelemetry()
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '00:00'
  const wholeSeconds = Math.floor(seconds)
  const minutes = Math.floor(wholeSeconds / 60)
  const restSeconds = wholeSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(restSeconds).padStart(2, '0')}`
}

function updateVideoProgress() {
  const video = videoRef.value
  if (!video) return
  const duration = Number.isFinite(video.duration) ? video.duration : 0
  videoDuration.value = duration
  videoCurrentTime.value = Number.isFinite(video.currentTime) ? video.currentTime : 0
  progressValue.value = duration > 0 ? Math.min(100, Math.max(0, (videoCurrentTime.value / duration) * 100)) : 0
}

function seekToTaskStartIfNeeded(force = false) {
  const video = videoRef.value
  const startAt = currentTask.value?.startAt || 0
  if (!video || !startAt) return false
  const duration = Number.isFinite(video.duration) ? video.duration : 0
  const target = duration > 0 ? Math.min(startAt, Math.max(0, duration - 0.2)) : startAt
  if (force || video.currentTime < 0.5 || Math.abs(video.currentTime - target) > 3) {
    video.currentTime = target
    resetFrameDetectionCursor()
    return true
  }
  return false
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

function buildStatsFromDetections(items: WallDetectionItem[]): WallStats {
  return items.reduce<WallStats>(
    (stats, item) => {
      stats[item.name] += 1
      return stats
    },
    { ...emptyStats },
  )
}

function recordDetectionHistory(
  taskId: string,
  time: number,
  items: WallDetectionItem[],
  annotatedImage: string,
  imageSize: { width: number; height: number },
) {
  const last = detectionHistory.value[detectionHistory.value.length - 1]
  const snapshot: WallDetectionSnapshot = {
    time,
    detections: items.map((item) => ({ ...item, bbox: [...item.bbox] as [number, number, number, number] })),
    imageSize,
    telemetry: currentTelemetry.value ? { ...currentTelemetry.value } : null,
  }
  if (last && Math.abs(time - last.time) < 0.8) {
    detectionHistory.value = [...detectionHistory.value.slice(0, -1), snapshot]
  } else {
    detectionHistory.value = [...detectionHistory.value, snapshot].slice(-120)
  }

  if (!items.length || logSaving || time - lastSavedLogTime < 2) return
  lastSavedLogTime = time
  logSaving = true
  void wallApi.createTaskLog(taskId, {
    time,
    detections: snapshot.detections,
    annotated_image: annotatedImage,
    image_size: imageSize,
    telemetry: snapshot.telemetry,
  }).then(async (result) => {
    if (currentTaskId.value !== taskId) return
    const persisted = mapDetectionLog(result.data)
    const index = detectionHistory.value.findIndex((item) => Math.abs(item.time - time) < 0.05)
    if (index >= 0) {
      detectionHistory.value = detectionHistory.value.map((item, itemIndex) => itemIndex === index ? persisted : item)
    } else {
      detectionHistory.value = [...detectionHistory.value, persisted].slice(-120)
    }
    const assessment = await wallApi.getTaskAssessment(taskId)
    if (currentTaskId.value === taskId) persistedAssessment.value = assessment.data
  }).catch(() => {
    if (currentTaskId.value === taskId) message.value = '检测已继续，但本帧日志图片保存失败。'
  }).finally(() => {
    logSaving = false
  })
}

function openInsightPanel(panel: WallInsightPanel) {
  activeInsightPanel.value = panel
  const taskId = currentTaskId.value || tasks.value[0]?.id || ''
  if (taskId) void loadInsightTask(taskId)
}

function closeInsightPanel() {
  activeInsightPanel.value = null
}

async function exportWallReport() {
  const taskId = currentTaskId.value
  if (!taskId || exportingReport.value) return
  exportingReport.value = true
  try {
    const response = await fetch(webPath(`/api/v1/wall/tasks/${taskId}/report`), { method: 'POST' })
    if (!response.ok) throw new Error('report export failed')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')
    link.href = url
    link.download = `建筑外墙巡检报告_${stamp}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    message.value = '建筑外墙巡检报告已导出为 PDF。'
  } catch {
    message.value = 'PDF 报告导出失败，请确认后端服务和检测日志可用。'
  } finally {
    exportingReport.value = false
  }
}

async function detectCurrentFrame(mediaTime: number) {
  if (!inferenceReady.value) return
  const video = videoRef.value
  const taskId = currentTaskId.value
  if (!video || !taskId) return

  const videoWidth = video.videoWidth || video.clientWidth
  const videoHeight = video.videoHeight || video.clientHeight
  if (!videoWidth || !videoHeight) return

  const requestSerial = ++detectionRequestSerial
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
    const result = await wallApi.detectFrame(image, confThreshold.value, iouThreshold.value)

    if (
      requestSerial !== detectionRequestSerial
      || currentTaskId.value !== taskId
    ) return

    apiLatency.value = Math.round(performance.now() - startedAt)
    detections.value = result.data.detections
    currentStats.value = buildStatsFromDetections(detections.value)
    lastCaptureSize.value = result.data.image_size || { width, height }
    recordDetectionHistory(
      taskId,
      mediaTime,
      detections.value,
      result.data.annotated_image,
      lastCaptureSize.value,
    )
    drawDetections(lastCaptureSize.value.width, lastCaptureSize.value.height)
  } catch {
    if (requestSerial === detectionRequestSerial && currentTaskId.value === taskId) {
      refreshDisplayDetectionsForFrame(videoRef.value?.currentTime || mediaTime)
      message.value = '实时检测暂不可用，已切换到标注数据展示。'
    }
  } finally {
    if (requestSerial === detectionRequestSerial) detecting.value = false
  }
}
function pickAnnotationFrame(currentFrame: number) {
  if (!annotationFrames.value.length) return null

  let selected: WallTaskAnnotationFrame | null = null
  for (const frame of annotationFrames.value) {
    if (frame.frame > currentFrame) break
    selected = frame
  }

  if (selected) return selected
  const firstFrame = annotationFrames.value[0]
  return firstFrame.frame - currentFrame <= annotationFps.value * 3 ? firstFrame : null
}

function scaleAnnotationDetection(item: WallDetectionItem, captureWidth: number, captureHeight: number): WallDetectionItem {
  const [x1, y1, x2, y2] = item.bbox
  return {
    ...item,
    bbox: [
      x1 * captureWidth,
      y1 * captureHeight,
      x2 * captureWidth,
      y2 * captureHeight,
    ],
  }
}

function refreshDisplayDetectionsForFrame(mediaTime = videoRef.value?.currentTime || 0) {
  const video = videoRef.value
  if (!video || video.readyState < 1) return
  const videoWidth = video.videoWidth || video.clientWidth
  const videoHeight = video.videoHeight || video.clientHeight
  if (!videoWidth || !videoHeight) return

  const { width, height } = calcCaptureSize(videoWidth, videoHeight)
  const currentFrame = Math.round(mediaTime * annotationFps.value)
  const annotationFrame = pickAnnotationFrame(currentFrame)
  const displayDetections = (annotationFrame?.detections || [])
    .map((item) => scaleAnnotationDetection(item, width, height))

  if (annotationFrame?.frame !== lastRenderedAnnotationFrame || width !== lastCaptureSize.value.width || height !== lastCaptureSize.value.height) {
    detections.value = displayDetections
    currentStats.value = buildStatsFromDetections(displayDetections)
    lastRenderedAnnotationFrame = annotationFrame?.frame ?? -1
  }

  lastCaptureSize.value = { width, height }
  drawDetections(width, height)
}

function detectionColor(name: WallClassName) {
  const colors: Record<WallClassName, string> = {
    Crack: '#ef4444',
    Seepage: '#14b8a6',
    TileSpalling: '#f59e0b',
    Hollowing: '#8b5cf6',
  }
  return colors[name] || '#14b8a6'
}

function detectionBadgeClass(name: WallClassName) {
  const classes: Record<WallClassName, string> = {
    Crack: 'bg-red-50 text-red-700 ring-red-100',
    Seepage: 'bg-teal-50 text-teal-700 ring-teal-100',
    TileSpalling: 'bg-amber-50 text-amber-700 ring-amber-100',
    Hollowing: 'bg-violet-50 text-violet-700 ring-violet-100',
  }
  return classes[name] || 'bg-slate-50 text-slate-700 ring-slate-100'
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

  ctx.font = '12px sans-serif'
  ctx.textBaseline = 'top'

  for (const item of detections.value) {
    const [x1, y1, x2, y2] = item.bbox
    const x = x1 * scaleX + offsetX
    const y = y1 * scaleY + offsetY
    const width = (x2 - x1) * scaleX
    const height = (y2 - y1) * scaleY
    const color = detectionColor(item.name)

    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, width, height)

    const label = `${item.cn} ${Math.round(item.conf * 100)}%`
    const labelWidth = ctx.measureText(label).width + 10
    ctx.fillStyle = color
    ctx.fillRect(x, Math.max(0, y - 20), labelWidth, 18)
    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, x + 5, Math.max(0, y - 18))
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([refreshHealth(), loadVideoTasks(), loadWallConfig()])
  loading.value = false
  healthTimer = window.setInterval(refreshHealth, 10000)
  window.addEventListener('resize', syncCanvasSize)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
  window.removeEventListener('resize', syncCanvasSize)
  stopVideo()
  cleanupPreloadVideos()
})
</script>

<template>
  <div class="min-h-screen bg-slate-50 text-slate-800 xl:flex xl:h-screen xl:min-h-0 xl:flex-col xl:overflow-hidden">
    <div class="w-full px-4 pt-4 md:px-5 xl:shrink-0">
      <InspectionHeader title="建筑外墙巡检" :task-name="currentTaskName" :online="backendOnline">
        <template #actions>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm font-medium text-amber-800 transition hover:border-amber-300 hover:bg-amber-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
            :disabled="!canPlay"
            @click="openInsightPanel('assessment')"
          >
            <ShieldAlert :size="17" />
            缺陷情况评估
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3.5 py-2.5 text-sm font-medium text-sky-700 transition hover:border-sky-300 hover:bg-sky-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
            :disabled="!canPlay"
            @click="openInsightPanel('location')"
          >
            <MapPinned :size="17" />
            缺陷方位展示
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm font-medium text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
            :disabled="!canPlay || exportingReport"
            @click="exportWallReport"
          >
            <FileDown :size="17" />
            {{ exportingReport ? '导出中...' : '报告导出' }}
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-teal-200 bg-teal-50 px-3.5 py-2.5 text-sm font-medium text-teal-700 transition hover:border-teal-300 hover:bg-teal-100"
            @click="toggleControlPanel"
          >
            <SlidersHorizontal :size="17" />
            实时控制
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-teal-500 to-emerald-500 px-3.5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:from-teal-400 hover:to-emerald-400"
            @click="openUploadPanel"
          >
            <CloudUpload :size="17" />
            上传任务
          </button>
          <button
            class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-medium text-slate-700 transition hover:border-teal-300 hover:bg-teal-50"
            @click="toggleTaskPicker"
          >
            <ListVideo :size="17" />
            加载任务
          </button>
        </template>
      </InspectionHeader>
    </div>

    <FloatingNotice :message="message" :tone="backendOnline ? 'info' : 'warning'" :duration="3500" centered />

    <main class="grid w-full grid-cols-1 gap-4 px-4 pb-2 pt-4 md:px-5 xl:min-h-0 xl:flex-1 xl:grid-cols-[320px_minmax(0,1fr)]" data-testid="wall-wide-layout">
      <aside class="space-y-4 xl:min-h-0 xl:overflow-hidden" data-testid="wall-left-panel">
        <section class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base font-semibold text-slate-900">任务摘要</h2>
            <span class="rounded-full px-3 py-1 text-xs font-semibold" :class="backendOnline ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'">
              {{ backendOnline ? '后端在线' : '后端离线' }}
            </span>
          </div>

          <div class="mt-3 space-y-2 text-sm text-slate-600">
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="text-slate-500">当前视频</div>
              <div class="mt-1 truncate font-semibold text-slate-900">{{ currentVideoName }}</div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="text-slate-500">任务来源</div>
              <div class="mt-1 font-semibold text-slate-900">{{ currentTask?.source === 'upload' ? '本地上传' : '系统示例' }}</div>
            </div>
            <div class="rounded-lg border border-sky-200 bg-sky-50 p-3">
              <div class="flex items-center justify-between gap-3 text-slate-500"><span>实时字幕定位</span><span class="text-xs">{{ srtFrames.length }} 条</span></div>
              <div v-if="currentTelemetry?.latitude && currentTelemetry.longitude" class="mt-1 font-mono text-sm font-semibold text-slate-900">
                {{ currentTelemetry.latitude.toFixed(6) }}, {{ currentTelemetry.longitude.toFixed(6) }}
              </div>
              <div v-else class="mt-1 font-semibold text-slate-500">暂无有效 GPS 数据</div>
            </div>
          </div>
        </section>

        <section class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 class="text-base font-semibold text-slate-900">风险统计</h2>
          <div class="mt-3 grid grid-cols-2 gap-2">
            <div v-for="item in statCards" :key="item.label" class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em]" :class="item.className">
                <span class="h-2 w-2 rounded-full" :class="item.barClass"></span>
                {{ item.label }}
              </div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">{{ item.value }}</div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-white p-3">
              <div class="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">当前目标</div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">{{ totalDetections }}</div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-white p-3">
              <div class="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">接口延迟</div>
              <div class="mt-2 text-2xl font-semibold text-slate-900">{{ apiLatency }} <span class="text-sm text-slate-500">ms</span></div>
            </div>
          </div>
        </section>

        <section class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid="wall-recognition-summary">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-slate-900">识别摘要</h3>
              <p class="mt-1 text-sm leading-5 text-slate-500">{{ detectionSummary }}</p>
            </div>
            <div class="shrink-0 text-right text-[11px] leading-4 text-slate-500">
              <div>Play Detect</div>
              <div>Conf {{ confThreshold.toFixed(2) }}</div>
              <div>IoU {{ iouThreshold.toFixed(2) }}</div>
            </div>
          </div>
        </section>

        <section class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm" data-testid="wall-current-targets">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-sm font-semibold text-slate-900">当前帧目标</h3>
            <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">{{ detections.length }}</span>
          </div>
          <div v-if="detections.length" class="mt-3 max-h-52 space-y-2 overflow-y-auto pr-1">
            <div
              v-for="(item, index) in detections.slice(0, 8)"
              :key="`${item.name}-${index}-${item.conf}`"
              class="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            >
              <div class="min-w-0">
                <div class="font-medium text-slate-900">{{ item.cn }}</div>
                <div class="truncate text-xs text-slate-500">{{ item.name }}</div>
              </div>
              <div class="rounded-full px-2.5 py-1 text-xs font-semibold ring-1" :class="detectionBadgeClass(item.name)">
                {{ Math.round(item.conf * 100) }}%
              </div>
            </div>
          </div>
          <div v-else class="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-5 text-center text-sm text-slate-500">
            暂无识别目标
          </div>
        </section>
      </aside>

      <section class="min-w-0 xl:min-h-0">
        <div class="rounded-lg border border-slate-200 bg-white px-4 pb-2 pt-4 shadow-sm xl:flex xl:h-full xl:min-h-0 xl:flex-col">
          <div class="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 class="text-lg font-semibold text-slate-900">检测画面</h2>
            </div>
          </div>

          <DetectionVideoFrame
            class="h-[calc(100vh-260px)] min-h-[520px] max-h-[840px] xl:h-auto xl:min-h-0 xl:max-h-none xl:flex-1"
            data-testid="wall-video-frame"
            label="YOLO 外墙缺陷检测"
            :status="detecting ? '帧分析中' : isPlaying ? '实时播放' : '等待启动'"
            :playing="isPlaying"
            :disabled="!canPlay"
            :current-time="videoCurrentTime"
            :duration="videoDuration"
            :empty="!canPlay && !loading"
            empty-text="请先上传任务或加载一个已有任务。"
            @toggle="togglePlay"
            @replay="replayVideo"
            @seek="seekVideoSeconds"
          >
            <video
              ref="videoRef"
              class="h-full w-full object-contain"
              :src="currentVideoUrl || undefined"
              crossorigin="anonymous"
              muted
              playsinline
              preload="auto"
              @play="onPlay"
              @pause="onPause"
              @ended="onEnded"
              @timeupdate="onTimeUpdate"
              @loadedmetadata="onLoadedMetadata"
              @seeked="onSeeked"
              @error="onVideoError"
            ></video>
            <canvas ref="canvasRef" class="pointer-events-none absolute inset-0 h-full w-full"></canvas>
          </DetectionVideoFrame>
        </div>

      </section>
    </main>

    <div
      v-if="activeInsightPanel === 'assessment'"
      class="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/25 p-5 backdrop-blur-[3px]"
      @click.self="closeInsightPanel"
    >
      <div class="max-h-[calc(100vh-40px)] w-full max-w-[1100px] overflow-y-auto rounded-xl border border-white bg-white p-6 shadow-2xl" data-testid="wall-defect-assessment">
        <div class="flex items-start justify-between gap-4">
          <div><h3 class="text-xl font-semibold text-slate-900">缺陷情况评估</h3><p class="mt-1 text-sm text-slate-500">融合当前任务的 {{ assessmentFrames.length }} 个检测帧，按检测记录评估外墙风险。</p></div>
          <button class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50" title="关闭" @click="closeInsightPanel"><X :size="17" /></button>
        </div>

        <div class="mt-5 flex flex-wrap items-end justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
          <label class="min-w-[260px] flex-1 text-sm text-slate-600">
            <span class="mb-1.5 block text-xs font-semibold text-slate-500">选择巡检任务</span>
            <select v-model="insightTaskId" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 outline-none focus:border-teal-400" @change="onInsightTaskChange">
              <option v-for="task in tasks" :key="task.id" :value="task.id">{{ task.taskName }} · {{ task.videoName }}</option>
            </select>
          </label>
          <div class="text-right text-xs leading-5 text-slate-500"><div>{{ insightTask?.subtitleName || '未关联字幕' }}</div><div>{{ detectionLogEntries.length }} 张日志图片</div></div>
        </div>

        <div class="mt-4 grid min-h-[650px] gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <section class="flex min-h-0 flex-col overflow-hidden rounded-lg border border-slate-300 bg-slate-100">
            <div class="border-b border-slate-200 bg-white px-4 py-3"><h4 class="font-semibold text-slate-900">任务日志图片</h4><p class="mt-1 text-xs text-slate-500">拖动右侧滑动条浏览，点击图片查看详情</p></div>
            <div v-if="insightLoading" class="flex flex-1 items-center justify-center text-sm text-slate-500"><Loader2 class="mr-2 animate-spin" :size="17" />正在读取日志</div>
            <div v-else-if="detectionLogEntries.length" class="max-h-[650px] flex-1 space-y-3 overflow-y-scroll p-3 pr-2">
              <button
                v-for="log in detectionLogEntries"
                :key="log.id || log.time"
                type="button"
                class="block w-full overflow-hidden rounded-lg border bg-white text-left transition"
                :class="selectedDetectionLog?.id === log.id ? 'border-teal-400 ring-2 ring-teal-100' : 'border-slate-200 hover:border-slate-300'"
                @click="selectedLogId = log.id || ''"
              >
                <img :src="log.imageUrl" class="aspect-video w-full bg-slate-950 object-contain" alt="缺陷日志缩略图" />
                <div class="flex items-center justify-between gap-3 px-3 py-2.5"><span class="font-semibold text-slate-900">{{ formatTime(log.time) }}</span><span class="text-xs text-slate-500">{{ log.detections.length }} 个缺陷</span></div>
              </button>
            </div>
            <div v-else class="flex flex-1 items-center justify-center px-6 text-center text-sm leading-6 text-slate-500">该任务暂无日志图片。播放检测视频后，系统会按任务自动保存带框图片。</div>
          </section>

          <section class="max-h-[720px] min-h-0 overflow-y-auto rounded-lg border border-slate-200 bg-white p-5">
            <template v-if="selectedDetectionLog">
              <div class="flex flex-wrap items-start justify-between gap-3"><div><h4 class="text-lg font-semibold text-slate-900">日志详细缺陷情况</h4><p class="mt-1 text-sm text-slate-500">{{ insightTask?.taskName }} · {{ formatTime(selectedDetectionLog.time) }}</p></div><span class="rounded-full px-3 py-1 text-xs font-semibold" :class="defectAssessment.panel">{{ defectAssessment.level }} · {{ defectAssessment.score }}</span></div>
              <img :src="selectedDetectionLog.imageUrl" class="mt-4 max-h-[390px] w-full rounded-lg border border-slate-200 bg-slate-950 object-contain" alt="选中的缺陷日志图片" />

              <div class="mt-4 rounded-lg border p-4" :class="defectAssessment.panel">
                <div class="font-semibold text-slate-900">{{ defectAssessment.title }}</div>
                <p class="mt-2 text-sm leading-6 text-slate-700">{{ selectedLogDamageSummary }}</p>
                <p class="mt-1 text-sm leading-6 text-slate-600">{{ defectAssessment.summary }}</p>
              </div>

              <div class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                <div class="rounded-lg border border-red-200 bg-red-50 p-3"><div class="text-xs text-red-700">裂缝</div><div class="mt-1 text-2xl font-semibold text-slate-900">{{ selectedLogStats.Crack }}</div></div>
                <div class="rounded-lg border border-teal-200 bg-teal-50 p-3"><div class="text-xs text-teal-700">渗水</div><div class="mt-1 text-2xl font-semibold text-slate-900">{{ selectedLogStats.Seepage }}</div></div>
                <div class="rounded-lg border border-amber-200 bg-amber-50 p-3"><div class="text-xs text-amber-700">脱落/破损</div><div class="mt-1 text-2xl font-semibold text-slate-900">{{ selectedLogStats.TileSpalling }}</div></div>
                <div class="rounded-lg border border-sky-200 bg-sky-50 p-3"><div class="text-xs text-sky-700">平均置信度</div><div class="mt-1 text-2xl font-semibold text-slate-900">{{ Math.round(selectedLogAverageConfidence * 100) }}%</div></div>
              </div>

              <div class="mt-4 grid gap-3 md:grid-cols-2">
                <div class="rounded-lg border border-slate-200 bg-slate-50 p-4"><div class="text-xs font-semibold text-slate-500">GPS 与飞行姿态</div><div v-if="selectedDetectionLog.telemetry?.latitude && selectedDetectionLog.telemetry.longitude" class="mt-2 space-y-1 text-sm text-slate-700"><div class="font-mono text-sky-700">{{ selectedDetectionLog.telemetry.latitude.toFixed(6) }}, {{ selectedDetectionLog.telemetry.longitude.toFixed(6) }}</div><div>相对高度 {{ selectedDetectionLog.telemetry.relAlt.toFixed(1) }} m · 绝对高度 {{ selectedDetectionLog.telemetry.absAlt.toFixed(1) }} m</div><div>云台偏航 {{ selectedDetectionLog.telemetry.gbYaw.toFixed(1) }}° · 俯仰 {{ selectedDetectionLog.telemetry.gbPitch.toFixed(1) }}°</div></div><div v-else class="mt-2 text-sm text-slate-500">该日志没有有效字幕定位数据</div></div>
                <div class="rounded-lg border border-slate-200 bg-slate-50 p-4"><div class="text-xs font-semibold text-slate-500">画面缺陷明细</div><div class="mt-2 space-y-2"><div v-for="(item, index) in selectedDetectionLog.detections" :key="`${item.name}-${index}`" class="flex items-center justify-between gap-3 text-sm"><span class="text-slate-700">{{ item.cn }}</span><span class="font-semibold text-slate-900">{{ Math.round(item.conf * 100) }}%</span></div></div></div>
              </div>

              <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4"><h5 class="font-semibold text-slate-900">处置建议</h5><div class="mt-2 space-y-2"><div v-for="(action, index) in defectAssessment.actions" :key="action" class="flex gap-2 text-sm leading-6 text-slate-600"><span class="font-semibold text-teal-700">{{ index + 1 }}.</span><span>{{ action }}</span></div></div></div>
            </template>
            <div v-else class="flex h-full min-h-[560px] items-center justify-center text-center text-sm text-slate-500">从左侧选择一张日志图片查看详细缺陷情况</div>
          </section>
        </div>
      </div>
    </div>

    <div
      v-if="activeInsightPanel === 'location'"
      class="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/25 p-5 backdrop-blur-[3px]"
      @click.self="closeInsightPanel"
    >
      <div class="max-h-[calc(100vh-40px)] w-full max-w-[1180px] overflow-y-auto rounded-xl border border-white bg-white p-6 shadow-2xl" data-testid="wall-defect-location">
        <div class="flex items-start justify-between gap-4">
          <div><h3 class="text-xl font-semibold text-slate-900">缺陷方位展示</h3><p class="mt-1 text-sm text-slate-500">根据视频对应字幕实时解析 GPS、飞行高度与云台姿态，并定位检测日志。</p></div>
          <button class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50" title="关闭" @click="closeInsightPanel"><X :size="17" /></button>
        </div>

        <div class="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section class="relative min-h-[590px] overflow-hidden rounded-xl border border-slate-300 bg-slate-100">
            <WallLocationMap :points="geoLocationPoints" :current="currentMapPoint" />
            <div v-if="!insightTask?.telemetry.length && !geoLocationPoints.length" class="absolute inset-0 z-[500] flex items-center justify-center bg-white/90 p-8 text-center text-sm leading-6 text-slate-600">当前任务未加载有效字幕。请上传与视频对应的 SRT、TXT 或 VTT 字幕文件。</div>
          </section>

          <section class="space-y-3">
            <div v-if="selectedDetectionLog?.imageUrl" class="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <img :src="selectedDetectionLog.imageUrl" class="aspect-video w-full bg-slate-950 object-contain" alt="方位对应的检测日志图片" />
              <div class="flex items-center justify-between gap-3 px-3 py-2.5"><span class="font-semibold text-slate-900">{{ Array.from(new Set(selectedDetectionLog.detections.map((item) => item.cn))).join('、') }}</span><span class="text-xs text-slate-500">{{ formatTime(selectedDetectionLog.time) }}</span></div>
            </div>
            <div class="rounded-xl border border-sky-200 bg-sky-50 p-4"><div class="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">日志 GPS</div><div class="mt-2 font-mono text-base font-semibold text-slate-900">{{ displayedLocationTelemetry?.latitude && displayedLocationTelemetry.longitude ? `${displayedLocationTelemetry.latitude.toFixed(6)}, ${displayedLocationTelemetry.longitude.toFixed(6)}` : '等待字幕定位' }}</div><div class="mt-1 text-sm text-slate-500">日志 {{ selectedDetectionLog ? formatTime(selectedDetectionLog.time) : '--' }} / 字幕 {{ insightTask?.telemetry.length || 0 }} 条</div></div>
            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-lg border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">相对高度</div><div class="mt-1 font-semibold text-slate-900">{{ displayedLocationTelemetry ? `${displayedLocationTelemetry.relAlt.toFixed(1)} m` : '--' }}</div></div>
              <div class="rounded-lg border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">绝对高度</div><div class="mt-1 font-semibold text-slate-900">{{ displayedLocationTelemetry ? `${displayedLocationTelemetry.absAlt.toFixed(1)} m` : '--' }}</div></div>
              <div class="rounded-lg border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">云台偏航</div><div class="mt-1 font-semibold text-slate-900">{{ displayedLocationTelemetry ? `${displayedLocationTelemetry.gbYaw.toFixed(1)}°` : '--' }}</div></div>
              <div class="rounded-lg border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">云台俯仰</div><div class="mt-1 font-semibold text-slate-900">{{ displayedLocationTelemetry ? `${displayedLocationTelemetry.gbPitch.toFixed(1)}°` : '--' }}</div></div>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-4">
              <div class="flex items-center justify-between"><h4 class="font-semibold text-slate-900">缺陷定位日志</h4><span class="text-xs text-slate-500">{{ geoLocationPoints.length }} 个 GPS 点</span></div>
              <div v-if="geoLocationPoints.length" class="mt-3 max-h-[255px] space-y-2 overflow-y-auto pr-1">
                <button v-for="(point, index) in geoLocationPoints.slice().reverse()" :key="point.id" type="button" class="block w-full rounded-lg border px-3 py-3 text-left transition" :class="selectedLogId === point.id ? 'border-sky-400 bg-sky-50' : 'border-slate-200 bg-slate-50 hover:border-slate-300'" @click="selectedLogId = point.id">
                  <div class="flex items-center justify-between gap-3"><div class="flex items-center gap-2"><span class="flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-xs font-semibold text-sky-700">{{ index + 1 }}</span><span class="font-medium text-slate-900">{{ point.label }}</span></div><span class="text-xs text-slate-500">{{ formatTime(point.time) }}</span></div>
                  <div class="mt-2 font-mono text-xs text-slate-600">{{ point.latitude.toFixed(6) }}, {{ point.longitude.toFixed(6) }}</div>
                </button>
              </div>
              <div v-else class="mt-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">暂无可定位缺陷记录</div>
            </div>
            <div class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900"><div class="font-semibold">现场复核顺序</div><div class="mt-2">优先从记录最多的立面区域开始，随后复核面砖脱落点及其下方坠落影响区，再检查裂缝与渗水是否连续扩展。</div></div>
            <div class="text-xs leading-5 text-slate-400">地图点位来自对应字幕中的经纬度；检测日志同时保存视频时间、飞行高度和云台姿态，便于现场复核。</div>
          </section>
        </div>
      </div>
    </div>

    <div
      v-if="showUploadPanel"
      class="fixed inset-0 z-30 flex items-center justify-center bg-slate-950/20 p-6 backdrop-blur-[3px]"
      @click.self="closeUploadPanel"
    >
      <div class="w-full max-w-md rounded-lg border border-white bg-white p-5 shadow-2xl">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">导入任务</h3>
            <p class="mt-1 text-sm text-slate-500">同时上传检测视频和对应字幕，用于按视频时间实时定位。</p>
          </div>
          <button
            class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            title="关闭"
            @click="closeUploadPanel"
          >
            <X :size="17" />
          </button>
        </div>

        <div class="mt-4 space-y-4">
          <div class="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
            <button
              type="button"
              class="rounded-md px-3 py-2 text-sm font-medium transition"
              :class="uploadMode === 'file' ? 'bg-white text-teal-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="uploadMode = 'file'"
            >
              上传文件
            </button>
            <button
              type="button"
              class="rounded-md px-3 py-2 text-sm font-medium transition"
              :class="uploadMode === 'path' ? 'bg-white text-teal-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="uploadMode = 'path'"
            >
              服务器路径复制
            </button>
          </div>

          <label class="block rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">任务名称</div>
            <input
              v-model="uploadTaskName"
              type="text"
              placeholder="例如：综合楼南立面巡检任务"
              class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-teal-300"
            />
          </label>

          <label v-if="uploadMode === 'file'" class="block rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">视频文件</div>
            <input type="file" accept="video/*" @change="onVideoFileSelect" />
            <div class="mt-2 text-xs text-slate-500">{{ uploadVideoFile?.name || '尚未选择视频' }}</div>
          </label>

          <label v-if="uploadMode === 'file'" class="block rounded-lg border border-sky-200 bg-sky-50/60 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">对应字幕文件</div>
            <input type="file" accept=".srt,.txt,.vtt" @change="onSubtitleFileSelect" />
            <div class="mt-2 text-xs text-slate-500">{{ uploadSubtitleFile?.name || '尚未选择字幕' }}</div>
          </label>

          <label v-else class="block rounded-lg border border-teal-200 bg-teal-50/60 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">视频完整路径</div>
            <textarea
              v-model="uploadSourcePath"
              rows="3"
              data-testid="wall-import-path"
              placeholder="请输入部署服务器上的视频绝对路径"
              class="w-full resize-none rounded-lg border border-teal-200 bg-white px-3 py-2 font-mono text-xs leading-5 text-slate-700 outline-none focus:border-teal-400"
            ></textarea>
            <div class="mt-2 text-xs leading-5 text-teal-700">路径必须位于运行后端的服务器上；从其他电脑访问时，请使用“上传文件”。后台会复制文件，原始视频保持不变。</div>
          </label>

          <label v-if="uploadMode === 'path'" class="block rounded-lg border border-sky-200 bg-sky-50/60 p-4 text-sm text-slate-600">
            <div class="mb-2 font-medium text-slate-900">字幕完整路径</div>
            <textarea
              v-model="uploadSubtitlePath"
              rows="3"
              placeholder="请输入部署服务器上的字幕绝对路径（可选）"
              class="w-full resize-none rounded-lg border border-sky-200 bg-white px-3 py-2 font-mono text-xs leading-5 text-slate-700 outline-none focus:border-sky-400"
            ></textarea>
          </label>

          <button
            class="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-teal-500 to-emerald-500 px-4 py-3 text-sm font-semibold text-white transition hover:from-teal-400 hover:to-emerald-400 disabled:from-slate-200 disabled:to-slate-200 disabled:text-slate-400"
            :disabled="!uploadReady || uploadingTask"
            @click="confirmUploadTask"
          >
            <CloudUpload :size="17" />
            {{ uploadingTask ? (uploadMode === 'path' ? '正在复制，请稍候...' : '上传中...') : (uploadMode === 'path' ? '确认复制导入' : '确认上传') }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="showTaskPicker"
      class="fixed inset-0 z-30 flex items-center justify-center bg-slate-950/20 p-6 backdrop-blur-[3px]"
      @click.self="closeTaskPicker"
    >
      <div class="w-full max-w-md rounded-lg border border-white bg-white p-5 shadow-2xl">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">加载任务</h3>
            <p class="mt-1 text-sm text-slate-500">切换外墙巡检视频。</p>
          </div>
          <button
            class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            title="关闭"
            @click="closeTaskPicker"
          >
            <X :size="17" />
          </button>
        </div>

        <div v-if="tasks.length > 0" class="mt-4 max-h-[60vh] space-y-3 overflow-y-auto pr-1">
          <div
            v-for="task in tasks"
            :key="task.id"
            class="rounded-lg border px-4 py-3 transition"
            :class="currentTaskId === task.id ? 'border-teal-300 bg-teal-50 text-teal-700' : 'border-slate-200 bg-slate-50 text-slate-700'"
          >
            <div class="flex items-center justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div v-if="renamingTaskId === task.id" class="flex items-center gap-2">
                  <input
                    v-model="renameTaskName"
                    class="min-w-0 flex-1 rounded-lg border border-teal-200 bg-white px-3 py-2 text-sm font-medium text-slate-900 outline-none focus:border-teal-400"
                    @keyup.enter="confirmRenameTask(task)"
                    @keyup.esc="cancelRenameTask"
                  />
                  <button
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-emerald-200 bg-white text-emerald-700 transition hover:bg-emerald-50 disabled:text-slate-400"
                    title="确认重命名"
                    :disabled="taskActionBusyId === task.id"
                    @click="confirmRenameTask(task)"
                  >
                    <Loader2 v-if="taskActionBusyId === task.id" class="animate-spin" :size="16" />
                    <Check v-else :size="16" />
                  </button>
                  <button
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50"
                    title="取消重命名"
                    :disabled="taskActionBusyId === task.id"
                    @click="cancelRenameTask"
                  >
                    <X :size="16" />
                  </button>
                </div>
                <div v-else class="truncate font-medium">{{ task.taskName }}</div>
                <div class="mt-1 truncate text-xs text-slate-500">{{ task.videoName }}</div>
              </div>
              <div class="flex shrink-0 flex-col items-end gap-2">
                <span class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-500">
                  {{ task.source === 'upload' ? '本地上传' : '系统示例' }}
                </span>
                <span
                  class="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                  :class="taskPreloadStates[task.id] === 'loaded' ? 'bg-emerald-50 text-emerald-700' : taskPreloadStates[task.id] === 'error' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-500'"
                >
                  {{ preloadStatusText(task) }}
                </span>
              </div>
            </div>

            <div class="mt-3 grid grid-cols-3 gap-2">
              <button
                class="inline-flex items-center justify-center gap-1.5 rounded-lg border border-teal-200 bg-white px-3 py-2 text-xs font-semibold text-teal-700 transition hover:bg-teal-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                :disabled="taskActionBusyId === task.id"
                @click="selectTask(task)"
              >
                <ListVideo :size="14" />
                加载
              </button>
              <button
                class="inline-flex items-center justify-center gap-1.5 rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-amber-700 transition hover:bg-amber-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                :disabled="Boolean(taskActionBusyId) || renamingTaskId === task.id"
                @click="beginRenameTask(task)"
              >
                <Pencil :size="14" />
                重命名
              </button>
              <button
                class="inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                :disabled="Boolean(taskActionBusyId) || renamingTaskId === task.id"
                @click="deleteTask(task)"
              >
                <Loader2 v-if="taskActionBusyId === task.id && renamingTaskId !== task.id" class="animate-spin" :size="14" />
                <Trash2 v-else :size="14" />
                删除
              </button>
            </div>
          </div>
        </div>
        <div v-else class="mt-4 rounded-lg border border-dashed border-teal-200 bg-teal-50/60 px-4 py-10 text-center text-sm text-slate-600">
          暂无可加载任务。
        </div>
      </div>
    </div>

    <div
      v-if="showControlPanel"
      class="fixed inset-0 z-30 flex items-center justify-center bg-slate-950/20 p-6 backdrop-blur-[3px]"
      @click.self="closeControlPanel"
    >
      <div class="w-full max-w-md rounded-lg border border-white bg-white p-5 shadow-2xl">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">实时控制</h3>
            <p class="mt-1 text-sm text-slate-500">调整当前检测参数。</p>
          </div>
          <button
            class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            title="关闭"
            @click="closeControlPanel"
          >
            <X :size="17" />
          </button>
        </div>

        <div class="mt-4 space-y-4">
          <div class="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div class="mb-3 flex items-center justify-between text-sm text-slate-600">
              <span>置信度</span>
              <span>{{ confThreshold.toFixed(2) }}</span>
            </div>
            <input v-model.number="confThreshold" type="range" :min="minObviousConfidence" max="0.95" step="0.01" class="w-full accent-teal-500" @change="applyConfig" />

            <div class="mb-3 mt-5 flex items-center justify-between text-sm text-slate-600">
              <span>IoU</span>
              <span>{{ iouThreshold.toFixed(2) }}</span>
            </div>
            <input v-model.number="iouThreshold" type="range" min="0.1" max="0.9" step="0.01" class="w-full accent-teal-500" @change="applyConfig" />
          </div>

          <div class="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div class="mb-3 flex items-center justify-between text-sm text-slate-600">
              <span>检测频率</span>
              <span>{{ frameDetectionMode }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
