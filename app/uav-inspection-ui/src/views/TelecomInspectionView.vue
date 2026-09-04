<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { telecomApi, type TelecomDetectResult, type TelecomTaskItem } from '../api1/telecom'
import { findTelemetry, parseSrt, type TelemetryFrame } from '../utils/srtParser'
import InspectionHeader from '../components/common/InspectionHeader.vue'
import DetectionVideoFrame from '../components/common/DetectionVideoFrame.vue'
import FloatingNotice from '../components/common/FloatingNotice.vue'

interface PersistedTask {
  id: string
  taskName: string
  videoName: string
  videoUrl: string
  srtName: string
  srtUrl: string
  srtText: string
}

type NoticeTone = 'info' | 'success' | 'error'

const supportedVideoSuffixes = ['.mp4', '.avi', '.mov', '.mkv'] as const
const supportedSubtitleSuffixes = ['.srt', '.txt', '.vtt'] as const
const supportedVideoFormatText = 'MP4、AVI、MOV、MKV'
const supportedSubtitleFormatText = 'SRT、TXT、VTT'

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const currentVideoUrl = ref('')
const currentVideoName = ref('')
const persistedTasks = ref<PersistedTask[]>([])
const backendOnline = ref(false)
const inferenceReady = ref(false)
const loading = ref(false)
const detecting = ref(false)
const isPlaying = ref(false)
const videoCurrentTime = ref(0)
const videoDuration = ref(0)
const apiLatency = ref(0)
const currentStats = ref({ Station: 0, Antenna: 0 })
const detections = ref<TelecomDetectResult['detections']>([])
const confThreshold = ref(0.35)
const iouThreshold = ref(0.45)
const lastDetectBucket = ref(-1)
const message = ref('请上传一个视频和对应字幕开始演示。')
const noticeTone = ref<NoticeTone>('info')
const showTaskPicker = ref(false)
const showUploadPanel = ref(false)
const showControlPanel = ref(false)
const exportingReport = ref(false)
const uploadVideoFile = ref<File | null>(null)
const uploadSrtFile = ref<File | null>(null)
const uploadingTask = ref(false)
const renamingTaskId = ref('')
const deletingTaskId = ref('')
const srtFrames = ref<TelemetryFrame[]>([])
const currentTelemetryIndex = ref(-1)
const uavInfo = ref({
  relAlt: 0,
  absAlt: 0,
  gbYaw: 0,
  gbPitch: 0,
  gbRoll: 0,
  iso: 0,
  focalLen: 0,
  lat: 0,
  lng: 0,
  shutter: '',
  fnum: 0,
  frameCnt: 0,
  datetime: '',
})
let healthTimer: number | null = null
let telemetryAnimationFrame: number | null = null

const canPlay = computed(() => Boolean(currentVideoUrl.value))
const subtitleCount = computed(() => srtFrames.value.length)
const uploadReady = computed(() => Boolean(uploadVideoFile.value && uploadSrtFile.value))
const currentTask = computed(() => persistedTasks.value.find((task) => task.videoUrl === currentVideoUrl.value) || null)
function setMessage(value: string, tone: NoticeTone = 'info') {
  message.value = value
  noticeTone.value = tone
}

function getFileSuffix(file: File) {
  const dotIndex = file.name.lastIndexOf('.')
  return dotIndex >= 0 ? file.name.slice(dotIndex).toLowerCase() : ''
}

function isSupportedVideoFile(file: File) {
  return supportedVideoSuffixes.includes(getFileSuffix(file) as (typeof supportedVideoSuffixes)[number])
}

function isSupportedSubtitleFile(file: File) {
  return supportedSubtitleSuffixes.includes(getFileSuffix(file) as (typeof supportedSubtitleSuffixes)[number])
}

function extractApiErrorMessage(error: unknown, fallback: string) {
  const responseData = (error as { response?: { data?: { detail?: string; message?: string } } }).response?.data
  return responseData?.detail || responseData?.message || fallback
}

async function refreshHealth() {
  try {
    const result = await telecomApi.getHealth()
    backendOnline.value = true
    inferenceReady.value = result.data.inference_available ?? result.data.status === 'ready'
  } catch {
    backendOnline.value = false
    inferenceReady.value = false
  }
}

function mapTask(item: TelecomTaskItem, srtText: string): PersistedTask {
  return {
    id: item.task_id,
    taskName: item.task_name,
    videoName: item.video_name,
    videoUrl: item.video_url,
    srtName: item.srt_name,
    srtUrl: item.srt_url,
    srtText,
  }
}

async function loadPersistedTasks() {
  try {
    const result = await telecomApi.getTasks()
    const tasks: PersistedTask[] = []
    for (const item of result.data.tasks) {
      const srtResponse = await fetch(item.srt_url)
      const srtText = srtResponse.ok ? await srtResponse.text() : ''
      tasks.push(mapTask(item, srtText))
    }
    persistedTasks.value = tasks
    if (!currentVideoUrl.value && tasks.length > 0) {
      selectTask(tasks[0])
    }
  } catch {
    setMessage('任务记录加载失败，请检查后端任务接口。', 'error')
  }
}

function resetDetectionState() {
  currentStats.value = { Station: 0, Antenna: 0 }
  detections.value = []
  apiLatency.value = 0
  lastDetectBucket.value = -1
  clearCanvas()
}

function resetUavInfo() {
  currentTelemetryIndex.value = -1
  uavInfo.value = {
    relAlt: 0,
    absAlt: 0,
    gbYaw: 0,
    gbPitch: 0,
    gbRoll: 0,
    iso: 0,
    focalLen: 0,
    lat: 0,
    lng: 0,
    shutter: '',
    fnum: 0,
    frameCnt: 0,
    datetime: '',
  }
}

function stopVideo() {
  const video = videoRef.value
  if (!video) return
  video.pause()
  video.currentTime = 0
  isPlaying.value = false
}

function selectTask(task: PersistedTask) {
  stopVideo()
  currentVideoUrl.value = task.videoUrl
  currentVideoName.value = task.videoName
  const parsedFrames = parseSrt(task.srtText)
  srtFrames.value = parsedFrames
  resetDetectionState()
  resetUavInfo()
  showTaskPicker.value = false
  setMessage(`已选择任务：${task.taskName}，已加载 ${parsedFrames.length} 条状态记录。`, 'success')
}

function openUploadPanel() {
  showUploadPanel.value = true
}

function closeUploadPanel() {
  showUploadPanel.value = false
}

function toggleControlPanel() {
  showControlPanel.value = !showControlPanel.value
}

function closeControlPanel() {
  showControlPanel.value = false
}

function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function buildReportHtml() {
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false })
  const task = currentTask.value
  const statsRows = [
    ['基站目标', currentStats.value.Station],
    ['天线目标', currentStats.value.Antenna],
    ['接口延迟', `${apiLatency.value} ms`],
    ['字幕条目', subtitleCount.value],
    ['置信度阈值', confThreshold.value.toFixed(2)],
    ['IOU 阈值', iouThreshold.value.toFixed(2)],
  ]
  const telemetryRows = [
    ['相对高度', `${uavInfo.value.relAlt.toFixed(1)} m`],
    ['绝对高度', `${uavInfo.value.absAlt.toFixed(1)} m`],
    ['偏航角', `${uavInfo.value.gbYaw.toFixed(1)}°`],
    ['俯仰角', `${uavInfo.value.gbPitch.toFixed(1)}°`],
    ['横滚角', `${uavInfo.value.gbRoll.toFixed(1)}°`],
    ['当前帧', uavInfo.value.frameCnt],
    ['纬度', uavInfo.value.lat.toFixed(6)],
    ['经度', uavInfo.value.lng.toFixed(6)],
    ['拍摄参数', `ISO ${uavInfo.value.iso || '--'} / 快门 ${uavInfo.value.shutter || '--'} / F ${uavInfo.value.fnum || '--'} / 焦距 ${uavInfo.value.focalLen || '--'}`],
    ['时间戳', uavInfo.value.datetime || '--'],
  ]
  const detectionRows = detections.value.map((item, index) => `
    <tr>
      <td>${index + 1}</td>
      <td>${escapeHtml(item.cn || item.name)}</td>
      <td>${Math.round(item.conf * 100)}%</td>
      <td>${escapeHtml(item.bbox.map((point) => Math.round(point)).join(', '))}</td>
    </tr>
  `).join('') || '<tr><td colspan="4">当前画面暂无检测目标。</td></tr>'

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(currentVideoName.value || '通信基站巡检')}报告</title>
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; color: #0f172a; background: #f8fafc; }
    .page { max-width: 1080px; margin: 0 auto; padding: 40px 28px 56px; }
    .hero { border-radius: 8px; background: linear-gradient(135deg, #0369a1, #0891b2); color: white; padding: 30px; }
    h1 { margin: 0 0 10px; font-size: 30px; }
    h2 { margin: 28px 0 12px; font-size: 20px; }
    .meta { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
    .chip { border: 1px solid rgba(255,255,255,.28); background: rgba(255,255,255,.14); border-radius: 999px; padding: 6px 10px; font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .card { border: 1px solid #e2e8f0; border-radius: 8px; background: white; padding: 16px; box-shadow: 0 12px 30px rgba(15,23,42,.06); }
    .label { color: #64748b; font-size: 13px; }
    .value { margin-top: 8px; font-size: 24px; font-weight: 800; }
    table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
    th, td { padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: left; font-size: 14px; }
    th { background: #f1f5f9; color: #475569; }
    tr:last-child td { border-bottom: 0; }
    .footer { margin-top: 30px; color: #94a3b8; text-align: center; font-size: 12px; }
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <h1>通信基站巡检报告</h1>
      <p>基于当前演示任务的无人机遥测、基站/天线识别与巡检状态自动生成。</p>
      <div class="meta">
        <span class="chip">任务: ${escapeHtml(task?.taskName || currentVideoName.value || '未命名任务')}</span>
        <span class="chip">视频: ${escapeHtml(currentVideoName.value || '--')}</span>
        <span class="chip">生成时间: ${escapeHtml(generatedAt)}</span>
        <span class="chip">后端状态: ${backendOnline.value ? '在线' : '离线'}</span>
      </div>
    </section>

    <h2>识别摘要</h2>
    <section class="grid">
      ${statsRows.map(([label, value]) => `<div class="card"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div></div>`).join('')}
    </section>

    <h2>无人机状态</h2>
    <table>
      <tbody>
        ${telemetryRows.map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`).join('')}
      </tbody>
    </table>

    <h2>当前画面检测目标</h2>
    <table>
      <thead><tr><th>#</th><th>类型</th><th>置信度</th><th>边界框</th></tr></thead>
      <tbody>${detectionRows}</tbody>
    </table>

    <div class="footer">低空智能巡检与决策平台 · 通信基站巡检报告自动生成</div>
  </main>
</body>
</html>`
}

function exportReport() {
  if (!canPlay.value || exportingReport.value) return
  exportingReport.value = true
  try {
    const html = buildReportHtml()
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')
    link.href = url
    link.download = `通信基站巡检报告_${stamp}.html`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    setMessage('报告已导出。', 'success')
  } finally {
    exportingReport.value = false
  }
}

function onVideoFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  if (file && !isSupportedVideoFile(file)) {
    input.value = ''
    uploadVideoFile.value = null
    setMessage(`不支持的视频格式，请上传 ${supportedVideoFormatText} 文件。`, 'error')
    return
  }
  uploadVideoFile.value = file
  if (file) setMessage(`已选择视频：${file.name}`, 'info')
}

function onSrtFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  if (file && !isSupportedSubtitleFile(file)) {
    input.value = ''
    uploadSrtFile.value = null
    setMessage(`不支持的字幕格式，请上传 ${supportedSubtitleFormatText} 文件。`, 'error')
    return
  }
  uploadSrtFile.value = file
  if (file) setMessage(`已选择字幕：${file.name}`, 'info')
}

async function confirmUploadTask() {
  if (!uploadVideoFile.value || !uploadSrtFile.value) {
    setMessage('请同时选择视频文件和字幕文件。', 'error')
    return
  }
  if (!isSupportedVideoFile(uploadVideoFile.value)) {
    setMessage(`不支持的视频格式，请上传 ${supportedVideoFormatText} 文件。`, 'error')
    return
  }
  if (!isSupportedSubtitleFile(uploadSrtFile.value)) {
    setMessage(`不支持的字幕格式，请上传 ${supportedSubtitleFormatText} 文件。`, 'error')
    return
  }

  const form = new FormData()
  form.append('task_name', uploadVideoFile.value.name)
  form.append('video', uploadVideoFile.value)
  form.append('srt', uploadSrtFile.value)

  uploadingTask.value = true
  setMessage('任务上传中，请稍候。', 'info')
  try {
    await telecomApi.uploadTask(form)
    uploadVideoFile.value = null
    uploadSrtFile.value = null
    showUploadPanel.value = false
    await loadPersistedTasks()
    showTaskPicker.value = true
    setMessage('上传成功，任务已写入记录，可在任务卡片中加载。', 'success')
  } catch (error) {
    setMessage(extractApiErrorMessage(error, '上传失败，请检查后端任务保存接口。'), 'error')
  } finally {
    uploadingTask.value = false
  }
}

async function renamePersistedTask(task: PersistedTask) {
  if (renamingTaskId.value || deletingTaskId.value) return
  const nextName = window.prompt('请输入新的任务名称', task.taskName)
  if (nextName === null) return

  const taskName = nextName.trim()
  if (!taskName) {
    setMessage('任务名称不能为空。', 'error')
    return
  }
  if (taskName === task.taskName) return

  renamingTaskId.value = task.id
  try {
    await telecomApi.renameTask(task.id, taskName)
    await loadPersistedTasks()
    setMessage(`任务“${task.taskName}”已重命名为“${taskName}”。`, 'success')
  } catch (error) {
    setMessage(extractApiErrorMessage(error, '重命名失败，请检查后端任务记录。'), 'error')
  } finally {
    renamingTaskId.value = ''
  }
}

async function deletePersistedTask(task: PersistedTask) {
  if (deletingTaskId.value || renamingTaskId.value) return
  if (!window.confirm(`确认删除任务“${task.taskName}”吗？删除后无法从任务记录中重新加载。`)) return

  const removedCurrentTask = currentTask.value?.id === task.id
  deletingTaskId.value = task.id
  try {
    await telecomApi.deleteTask(task.id)
    if (removedCurrentTask) {
      currentVideoUrl.value = ''
      currentVideoName.value = ''
      srtFrames.value = []
      resetDetectionState()
      resetUavInfo()
      stopVideo()
    }
    await loadPersistedTasks()
    setMessage(`任务“${task.taskName}”已删除。`, 'success')
  } catch (error) {
    setMessage(extractApiErrorMessage(error, '删除失败，请检查后端任务记录目录。'), 'error')
  } finally {
    deletingTaskId.value = ''
  }
}

function toggleTaskPicker() {
  showTaskPicker.value = !showTaskPicker.value
}

async function chooseUploadedTask(task: PersistedTask) {
  selectTask(task)
  if (!backendOnline.value) return
  await togglePlay()
}

function closeTaskPicker() {
  showTaskPicker.value = false
}

async function togglePlay() {
  const video = videoRef.value
  if (!video || !canPlay.value || !backendOnline.value) return

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
    setMessage('视频播放失败，请重新点击播放或刷新页面后重试。', 'error')
  }
}

function replayVideo() {
  const video = videoRef.value
  if (!video) return
  video.currentTime = 0
  videoCurrentTime.value = 0
  lastDetectBucket.value = -1
  void togglePlay()
}

function seekVideo(seconds: number) {
  const video = videoRef.value
  if (!video) return
  video.currentTime = seconds
  videoCurrentTime.value = seconds
  syncUav(seconds)
}

function applyTelemetryFrame(frame: TelemetryFrame) {
  currentTelemetryIndex.value = frame.frameCnt
  uavInfo.value = {
    relAlt: frame.relAlt,
    absAlt: frame.absAlt,
    gbYaw: frame.gbYaw,
    gbPitch: frame.gbPitch,
    gbRoll: frame.gbRoll,
    iso: frame.iso,
    focalLen: frame.focalLen,
    lat: frame.latitude,
    lng: frame.longitude,
    shutter: frame.shutter,
    fnum: frame.fnum,
    frameCnt: frame.frameCnt,
    datetime: frame.datetime,
  }
}

function syncUav(timeSec: number) {
  const frame = findTelemetry(srtFrames.value, timeSec)
  if (!frame) return
  if (frame.frameCnt === currentTelemetryIndex.value && frame.datetime === uavInfo.value.datetime) return
  applyTelemetryFrame(frame)
}

function stopTelemetryLoop() {
  if (telemetryAnimationFrame !== null) {
    cancelAnimationFrame(telemetryAnimationFrame)
    telemetryAnimationFrame = null
  }
}

function startTelemetryLoop() {
  stopTelemetryLoop()
  const run = () => {
    if (!videoRef.value || videoRef.value.paused || videoRef.value.ended) {
      telemetryAnimationFrame = null
      return
    }
    syncUav(videoRef.value.currentTime)
    telemetryAnimationFrame = requestAnimationFrame(run)
  }
  telemetryAnimationFrame = requestAnimationFrame(run)
}

function onPlay() {
  isPlaying.value = true
  startTelemetryLoop()
  setMessage('正在进行通信基站巡检演示。', 'info')
}

function onPause() {
  isPlaying.value = false
  stopTelemetryLoop()
}

function onEnded() {
  isPlaying.value = false
  stopTelemetryLoop()
  setMessage('演示播放完成，可以重新播放继续展示。', 'success')
}

function onVideoError() {
  isPlaying.value = false
  setMessage('视频无法播放，请重新选择任务。', 'error')
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
}

function onVideoLoadedMetadata() {
  videoDuration.value = Number.isFinite(videoRef.value?.duration) ? videoRef.value?.duration || 0 : 0
  syncCanvasSize()
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

function onConfidenceInput(event: Event) {
  confThreshold.value = Number((event.target as HTMLInputElement).value)
}

function onIouInput(event: Event) {
  iouThreshold.value = Number((event.target as HTMLInputElement).value)
}

async function onTimeUpdate() {
  const video = videoRef.value
  if (!video) return

  videoCurrentTime.value = video.currentTime
  syncUav(video.currentTime)
  if (!inferenceReady.value || detecting.value) return

  const bucket = Math.floor(video.currentTime * 3)
  if (bucket === lastDetectBucket.value) return
  lastDetectBucket.value = bucket
  await detectCurrentFrame()
}

async function detectCurrentFrame() {
  if (!inferenceReady.value) return
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
    const result = await telecomApi.detectFrame(image, confThreshold.value, iouThreshold.value)
    apiLatency.value = Math.round(performance.now() - startedAt)
    detections.value = result.data.detections
    currentStats.value = result.data.stats
    drawDetections(width, height)
  } catch {
    setMessage('检测失败，请确认后端模型已经正常加载。', 'error')
  } finally {
    detecting.value = false
  }
}

function drawDetections(captureWidth: number, captureHeight: number) {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas) return
  syncCanvasSize()
  const ctx = canvas.getContext('2d')
  if (!ctx) return
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
  const colors: Record<string, string> = { Station: '#16a34a', Antenna: '#ea580c' }
  ctx.font = '14px sans-serif'
  ctx.textBaseline = 'top'

  for (const item of detections.value) {
    const [x1, y1, x2, y2] = item.bbox
    const x = x1 * scaleX + offsetX
    const y = y1 * scaleY + offsetY
    const width = (x2 - x1) * scaleX
    const height = (y2 - y1) * scaleY
    const color = colors[item.name] || '#0284c7'

    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, width, height)

    const label = `${item.cn} ${Math.round(item.conf * 100)}%`
    const labelWidth = ctx.measureText(label).width + 12
    ctx.fillStyle = color
    ctx.fillRect(x, Math.max(0, y - 24), labelWidth, 20)
    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, x + 6, Math.max(0, y - 22))
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([refreshHealth(), loadPersistedTasks()])
  loading.value = false
  healthTimer = window.setInterval(refreshHealth, 10000)
  window.addEventListener('resize', syncCanvasSize)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
  window.removeEventListener('resize', syncCanvasSize)
  stopTelemetryLoop()
  stopVideo()
})
</script>

<template>
  <div class="mobile-page relative min-h-screen overflow-x-hidden bg-slate-50 text-slate-800 xl:flex xl:h-screen xl:min-h-0 xl:flex-col xl:overflow-hidden">
    <div class="pointer-events-none absolute top-[-10%] right-[-5%] h-[40%] w-[40%] rounded-full bg-blue-300/20 blur-[120px]"></div>
    <div class="pointer-events-none absolute bottom-[-10%] left-[-5%] h-[40%] w-[40%] rounded-full bg-indigo-300/20 blur-[120px]"></div>
    <div class="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgwLCAwLCAwLCAwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')]"></div>

    <div class="relative z-10 px-4 pt-4 md:px-6 xl:shrink-0">
      <InspectionHeader title="通信基站巡检" :task-name="currentTask?.taskName || currentVideoName" :online="backendOnline">
        <template #actions>
            <button
              class="rounded-2xl border border-blue-200 bg-blue-50 px-5 py-3 text-sm font-medium text-blue-700 shadow-[0_10px_25px_-18px_rgba(14,165,233,0.45)] transition hover:border-blue-300 hover:bg-blue-100"
              @click="toggleControlPanel"
            >
              实时控制
            </button>
          <button
            class="rounded-2xl bg-gradient-to-r from-indigo-500 to-blue-500 px-5 py-3 text-sm font-medium text-white shadow-[0_10px_25px_-15px_rgba(14,165,233,0.9)] transition hover:from-indigo-600 hover:to-blue-600"
            @click="openUploadPanel"
          >
            上传任务
          </button>
          <button
            class="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-medium text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            :disabled="persistedTasks.length === 0"
            @click="toggleTaskPicker"
          >
            加载任务
          </button>
          <button
            class="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-3 text-sm font-medium text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            :disabled="!canPlay || exportingReport"
            @click="exportReport"
          >
            {{ exportingReport ? '导出中...' : '导出报告' }}
          </button>
        </template>
      </InspectionHeader>
    </div>

    <FloatingNotice :message="message" :tone="noticeTone" :duration="3500" centered />

    <main class="relative z-10 grid min-h-[calc(100vh-104px)] grid-cols-1 px-4 pb-4 pt-2 md:px-6 md:pb-5 xl:min-h-0 xl:flex-1 xl:grid-cols-[400px_minmax(0,1fr)] xl:pb-3" data-testid="telecom-viewport-layout">
      <aside class="flex flex-col border-b border-slate-200/80 bg-white/72 p-5 backdrop-blur-xl xl:min-h-0 xl:overflow-hidden xl:border-b-0 xl:border-r">
        <section class="rounded-[28px] border border-white bg-white/82 p-5 shadow-[0_12px_40px_-20px_rgba(14,165,233,0.2)]">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-lg font-semibold text-slate-900">无人机状态</h2>
            <span class="flex items-center gap-2 text-sm text-slate-600">
              <span class="h-2.5 w-2.5 rounded-full" :class="backendOnline ? 'bg-emerald-400' : 'bg-red-400'"></span>
              {{ backendOnline ? '后端在线' : '后端离线' }}
            </span>
          </div>

          <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">相对高度</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.relAlt.toFixed(1) }} m</div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">绝对高度</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.absAlt.toFixed(1) }} m</div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">偏航角</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.gbYaw.toFixed(1) }}°</div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">俯仰角</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.gbPitch.toFixed(1) }}°</div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">横滚角</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.gbRoll.toFixed(1) }}°</div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">当前帧</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.frameCnt }}</div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">纬度</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.lat.toFixed(6) }}</div>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">经度</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.lng.toFixed(6) }}</div>
            </div>
            <div class="col-span-2 rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">拍摄参数</div>
              <div class="mt-1 flex flex-wrap gap-4 font-semibold text-slate-900">
                <span>ISO {{ uavInfo.iso || '--' }}</span>
                <span>快门 {{ uavInfo.shutter || '--' }}</span>
                <span>F {{ uavInfo.fnum || '--' }}</span>
                <span>焦距 {{ uavInfo.focalLen || '--' }}</span>
              </div>
            </div>
            <div class="col-span-2 rounded-2xl border border-slate-200 bg-slate-50/90 p-3">
              <div class="text-slate-500">时间戳</div>
              <div class="mt-1 font-semibold text-slate-900">{{ uavInfo.datetime || '--' }}</div>
            </div>
          </div>
        </section>

        <div class="mt-5 grid grid-cols-2 gap-3">
          <div class="rounded-3xl border border-white bg-white/85 p-4 shadow-[0_10px_35px_-18px_rgba(14,165,233,0.35)]">
            <div class="text-xs uppercase tracking-[0.25em] text-emerald-600">基站</div>
            <div class="mt-3 text-4xl font-semibold text-slate-900">{{ currentStats.Station }}</div>
          </div>
          <div class="rounded-3xl border border-white bg-white/85 p-4 shadow-[0_10px_35px_-18px_rgba(249,115,22,0.28)]">
            <div class="text-xs uppercase tracking-[0.25em] text-orange-600">天线</div>
            <div class="mt-3 text-4xl font-semibold text-slate-900">{{ currentStats.Antenna }}</div>
          </div>
          <div class="rounded-3xl border border-white bg-white/85 p-4 shadow-[0_10px_35px_-18px_rgba(34,211,238,0.35)]">
            <div class="text-xs uppercase tracking-[0.25em] text-indigo-600">接口延迟</div>
            <div class="mt-3 text-3xl font-semibold text-slate-900">{{ apiLatency }} <span class="text-base text-slate-500">ms</span></div>
          </div>
          <div class="rounded-3xl border border-white bg-white/85 p-4 shadow-[0_10px_35px_-18px_rgba(15,23,42,0.12)]">
            <div class="text-xs uppercase tracking-[0.25em] text-slate-500">字幕条目</div>
            <div class="mt-3 text-3xl font-semibold text-slate-900">{{ subtitleCount }}</div>
          </div>
        </div>

      </aside>

      <div
        v-if="showUploadPanel"
        class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
        @click.self="closeUploadPanel"
      >
        <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(14,165,233,0.35)]">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h3 class="text-lg font-semibold text-slate-900">上传视频与字幕</h3>
              <p class="mt-1 text-sm text-slate-500">上传后会写入后端任务记录，后续刷新页面仍然可见。</p>
            </div>
            <button
              class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
              @click="closeUploadPanel"
            >
              关闭
            </button>
          </div>

          <div class="mt-4 space-y-4">
            <div class="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-700">
              支持的视频格式：{{ supportedVideoFormatText }}；支持的字幕格式：{{ supportedSubtitleFormatText }}。
            </div>

            <label class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <div class="mb-2 font-medium text-slate-900">选择视频文件</div>
              <input type="file" accept=".mp4,.avi,.mov,.mkv" @change="onVideoFileSelect" />
              <div class="mt-2 text-xs text-slate-500">{{ uploadVideoFile?.name || '尚未选择视频' }}</div>
            </label>

            <label class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <div class="mb-2 font-medium text-slate-900">选择字幕文件</div>
              <input type="file" accept=".srt,.txt,.vtt" @change="onSrtFileSelect" />
              <div class="mt-2 text-xs text-slate-500">{{ uploadSrtFile?.name || '尚未选择字幕' }}</div>
            </label>

            <button
              class="w-full rounded-2xl bg-gradient-to-r from-indigo-500 to-blue-500 px-4 py-3 text-sm font-semibold text-white transition hover:from-indigo-600 hover:to-blue-600 disabled:bg-slate-200 disabled:text-slate-400"
              :disabled="!uploadReady || uploadingTask"
              @click="confirmUploadTask"
            >
              {{ uploadingTask ? '上传中...' : '确认上传' }}
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="showTaskPicker"
        class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
        @click.self="closeTaskPicker"
      >
        <div class="w-full max-w-md rounded-[28px] border border-white bg-white/95 p-5 shadow-[0_24px_80px_-24px_rgba(14,165,233,0.35)]">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h3 class="text-lg font-semibold text-slate-900">任务记录</h3>
              <p class="mt-1 text-sm text-slate-500">刷新页面后，这些任务记录依然可以重新加载和检测。</p>
            </div>
            <button
              class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
              @click="closeTaskPicker"
            >
              关闭
            </button>
          </div>

          <div class="mt-4 max-h-[60vh] space-y-3 overflow-y-auto pr-1">
            <div
              v-for="task in persistedTasks"
              :key="task.id"
              class="rounded-2xl border px-4 py-3 transition"
              :class="currentTask?.id === task.id ? 'border-blue-300 bg-blue-50 text-blue-700' : 'border-slate-200 bg-slate-50 text-slate-700'"
              :data-testid="`telecom-task-card-${task.id}`"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate font-semibold text-slate-900">{{ task.taskName }}</div>
                  <div class="mt-1 truncate text-xs text-slate-500">视频：{{ task.videoName }}</div>
                  <div class="mt-0.5 truncate text-xs text-slate-500">字幕：{{ task.srtName }}</div>
                </div>
                <span
                  v-if="currentTask?.id === task.id"
                  class="shrink-0 rounded-full border border-blue-200 bg-white px-2 py-0.5 text-xs font-semibold text-blue-700"
                >
                  当前
                </span>
              </div>

              <div class="mt-3 grid grid-cols-3 gap-2">
                <button
                  class="rounded-xl border border-blue-200 bg-white px-3 py-2 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                  :disabled="deletingTaskId === task.id || renamingTaskId === task.id"
                  @click="chooseUploadedTask(task)"
                >
                  加载
                </button>
                <button
                  class="rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs font-semibold text-amber-700 transition hover:bg-amber-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                  :disabled="deletingTaskId === task.id || Boolean(renamingTaskId)"
                  @click="renamePersistedTask(task)"
                >
                  {{ renamingTaskId === task.id ? '处理中' : '重命名' }}
                </button>
                <button
                  class="rounded-xl border border-rose-200 bg-white px-3 py-2 text-xs font-semibold text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                  :disabled="renamingTaskId === task.id || Boolean(deletingTaskId)"
                  @click="deletePersistedTask(task)"
                >
                  {{ deletingTaskId === task.id ? '删除中' : '删除' }}
                </button>
              </div>
            </div>
            <div v-if="persistedTasks.length === 0" class="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
              暂无已保存任务，请先上传视频和字幕。
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="showControlPanel"
        class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
        @click.self="closeControlPanel"
      >
        <div class="w-full max-w-md rounded-[28px] border border-blue-100 bg-white/96 p-5 shadow-[0_24px_80px_-24px_rgba(14,165,233,0.35)] backdrop-blur-xl">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-slate-900">实时控制</h3>
            <button
              class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
              @click="closeControlPanel"
            >
              关闭
            </button>
          </div>

          <div class="mt-4 rounded-2xl border border-slate-200 bg-slate-50/90 p-4">
            <div class="mb-3 flex items-center justify-between text-sm text-slate-600">
              <span>置信度</span>
              <span>{{ confThreshold.toFixed(2) }}</span>
            </div>
            <input
              :value="confThreshold"
              type="range"
              min="0.1"
              max="0.9"
              step="0.01"
              class="w-full accent-blue-500"
              @input="onConfidenceInput"
            />

            <div class="mb-3 mt-5 flex items-center justify-between text-sm text-slate-600">
              <span>IOU</span>
              <span>{{ iouThreshold.toFixed(2) }}</span>
            </div>
            <input
              :value="iouThreshold"
              type="range"
              min="0.1"
              max="0.9"
              step="0.01"
              class="w-full accent-blue-500"
              @input="onIouInput"
            />
          </div>
        </div>
      </div>

      <section class="flex min-h-0 flex-col pt-0 xl:h-full xl:pl-8">
        <DetectionVideoFrame
          class="h-[62vh] min-h-[360px] max-h-[680px] sm:min-h-[500px] xl:h-full xl:min-h-0 xl:max-h-none"
          data-testid="telecom-video-frame"
          label="YOLO 基站实时检测"
          :status="!inferenceReady && backendOnline ? (isPlaying ? '仅播放 · AI 未启用' : '基础模式 · AI 未启用') : detecting ? '帧分析中' : isPlaying ? '实时播放' : '等待启动'"
          :playing="isPlaying"
          :disabled="!canPlay || !backendOnline"
          :current-time="videoCurrentTime"
          :duration="videoDuration"
          :empty="!currentVideoUrl && !loading"
          empty-text="请先上传视频和字幕，或从任务记录中选择一个已有任务。"
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
      </section>
    </main>
  </div>
</template>

