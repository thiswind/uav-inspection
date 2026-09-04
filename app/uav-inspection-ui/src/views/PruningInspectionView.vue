<script setup lang="ts">
import { Camera, ClipboardList, Compass, Image, MapPinned, Sprout, X } from 'lucide-vue-next'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import InspectionHeader from '../components/common/InspectionHeader.vue'
import DetectionVideoFrame from '../components/common/DetectionVideoFrame.vue'
import FloatingNotice from '../components/common/FloatingNotice.vue'
import {
  pruningApi,
  type PruningDetectResult,
  type PruningInfoResult,
  type PruningTaskMutationResult,
  type PruningVideoItem,
} from '../api1/pruning'

interface PruningTask {
  id: string
  taskName: string
  videoName: string
  videoUrl: string
  source: 'system' | 'upload'
  createdAt?: string
}

type MessageTone = 'success' | 'error' | 'info'
type UploadMode = 'file' | 'path'
type PruningAssessment = PruningDetectResult['pruning_assessment']
type GrowthFeatureScores = Pick<PruningAssessment['features'], 'branch_score' | 'leaf_score' | 'yellow_leaf_score'>
type FeaturePanelKey = 'map' | 'growth' | 'plan'
type DetectionFrameLog = {
  id: string
  time: number
  timeLabel: string
  imageUrl: string
  title: string
  note: string
  assessment: PruningAssessment
  detections: PruningDetectResult['detections']
  stats: PruningDetectResult['stats']
  latency: number
  distinctiveness: number
}

const TASK_STORAGE_KEY = 'pruning:selected-task-id'
const DEFAULT_IMPORT_PATH = ''
const MAX_FRAME_LOGS = 15

const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const uploadFileInputRef = ref<HTMLInputElement | null>(null)

const sampleTasks = ref<PruningTask[]>([])
const uploadedTasks = ref<PruningTask[]>([])
const currentTaskId = ref('')
const pruningInfo = ref<PruningInfoResult | null>(null)
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
const showTaskSummaryPanel = ref(false)
const activeFeaturePanel = ref<FeaturePanelKey | null>(null)

const uploadMode = ref<UploadMode>('file')
const uploadTaskName = ref('')
const uploadVideoFile = ref<File | null>(null)
const uploadSourcePath = ref(DEFAULT_IMPORT_PATH)
const uploadingTask = ref(false)
const deletingTaskId = ref('')

const apiLatency = ref(0)
const currentStats = ref({ Pruned: 0, Unpruned: 0 })
const detections = ref<PruningDetectResult['detections']>([])
const currentAssessment = ref<PruningAssessment | null>(null)
const frameLogs = ref<DetectionFrameLog[]>([])
const selectedFrameLogId = ref('')
const frameLogSelectionPinned = ref(false)
const confThreshold = ref(0.3)
const iouThreshold = ref(0.45)
const autoDetectEnabled = ref(false)
const detectIntervalSec = ref(2)
const lastDetectBucket = ref(-1)
const lastCaptureSize = ref({ width: 0, height: 0 })

const message = ref('请选择一个乔木修剪任务开始演示。')
const messageTone = ref<MessageTone>('info')

let healthTimer: number | null = null

const taskLibrary = computed(() => [...uploadedTasks.value, ...sampleTasks.value])
const currentTask = computed(() => taskLibrary.value.find((item) => item.id === currentTaskId.value) || null)
const currentTaskName = computed(() => currentTask.value?.taskName || '未选择任务')
const currentVideoName = computed(() => currentTask.value?.videoName || '尚未选择视频')
const currentVideoUrl = computed(() => currentTask.value?.videoUrl || '')
const canPlay = computed(() => Boolean(currentVideoUrl.value))
const uploadReady = computed(() =>
  uploadMode.value === 'file' ? Boolean(uploadVideoFile.value) : Boolean(uploadSourcePath.value.trim()),
)
const totalDetections = computed(() => detections.value.length)
const deviceText = computed(() => {
  if (!pruningInfo.value) return '未知'
  return pruningInfo.value.system.cuda_available ? `${pruningInfo.value.system.device} / CUDA` : pruningInfo.value.system.device
})
const statusText = computed(() => {
  if (!backendOnline.value) return '后端未就绪'
  if (!inferenceReady.value) return isPlaying.value ? '仅播放 · AI 未启用' : '基础模式 · AI 未启用'
  if (detecting.value) return '正在识别'
  if (isPlaying.value && autoDetectEnabled.value) return '视频检测中'
  if (isPlaying.value) return '播放中'
  return '待开始'
})
const uploadButtonText = computed(() => {
  if (!uploadingTask.value) {
    return uploadMode.value === 'file' ? '确认上传' : '确认导入'
  }
  return uploadMode.value === 'file' ? '上传并转码中...' : '导入并转码中...'
})
const messageClass = computed(() => {
  if (messageTone.value === 'success') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  }
  if (messageTone.value === 'error') {
    return 'border-rose-200 bg-rose-50 text-rose-800'
  }
  return 'border-slate-200 bg-slate-50 text-slate-700'
})
const assessmentClass = computed(() => {
  if (!currentAssessment.value) return 'border-slate-200 bg-slate-50 text-slate-700'
  if (currentAssessment.value.needs_pruning) return 'border-rose-200 bg-rose-50 text-rose-800'
  return 'border-emerald-200 bg-emerald-50 text-emerald-800'
})
const assessmentLevelText = computed(() => {
  if (!currentAssessment.value) return '等待检测'
  if (currentAssessment.value.level === 'high') return '高'
  if (currentAssessment.value.level === 'medium') return '中'
  return '低'
})
const featurePanelTitle = computed(() => {
  if (activeFeaturePanel.value === 'map') return '乔木地图方位展示'
  if (activeFeaturePanel.value === 'growth') return '乔木长势估计'
  if (activeFeaturePanel.value === 'plan') return '修剪方案推荐'
  return ''
})
const featurePanelSummary = computed(() => {
  if (activeFeaturePanel.value === 'map') return '根据当前任务构建巡检方位、树冠中心和航线相对位置。'
  if (activeFeaturePanel.value === 'growth') return '结合叶量覆盖、分支密度和黄叶比例估计当前树势。'
  if (activeFeaturePanel.value === 'plan') return '结合模型结果和视觉特征生成现场修剪建议。'
  return ''
})
const treeMapSeed = computed(() => hashText(currentTaskId.value || currentVideoName.value || 'tree'))
const treeMapPosition = computed(() => ({
  x: 52 + (treeMapSeed.value % 22),
  y: 28 + ((treeMapSeed.value >>> 3) % 34),
}))
const treeMapDronePosition = computed(() => ({
  x: 16 + ((treeMapSeed.value >>> 5) % 20),
  y: 58 + ((treeMapSeed.value >>> 8) % 20),
}))
const treeMapBearing = computed(() => {
  const deltaX = treeMapPosition.value.x - treeMapDronePosition.value.x
  const deltaY = treeMapPosition.value.y - treeMapDronePosition.value.y
  return Math.round((Math.atan2(deltaX, -deltaY) * 180 / Math.PI + 360) % 360)
})
const treeMapBearingText = computed(() => bearingToText(treeMapBearing.value))
const treeMapHeading = computed(() => (treeMapBearing.value + 328) % 360)
const treeMapRelativeAngle = computed(() => ((treeMapBearing.value - treeMapHeading.value + 540) % 360) - 180)
const treeMapDistance = computed(() => {
  const deltaX = treeMapPosition.value.x - treeMapDronePosition.value.x
  const deltaY = treeMapPosition.value.y - treeMapDronePosition.value.y
  return Math.round(Math.hypot(deltaX, deltaY) * 1.08)
})
const treeMapCoordinate = computed(() => ({
  lat: (30.274084 + ((treeMapSeed.value % 160) - 80) / 100000).toFixed(6),
  lng: (120.155070 + (((treeMapSeed.value >>> 4) % 160) - 80) / 100000).toFixed(6),
}))
const treeMapRoutePoints = computed(() => {
  const drone = treeMapDronePosition.value
  const target = treeMapPosition.value
  return `${Math.max(5, drone.x - 10)},${Math.min(90, drone.y + 9)} ${drone.x},${drone.y} ${Math.round((drone.x + target.x) / 2)},${Math.round((drone.y + target.y) / 2 + 8)} ${target.x},${target.y}`
})
const selectedFrameLog = computed(() => {
  if (!frameLogs.value.length) return null
  return frameLogs.value.find((item) => item.id === selectedFrameLogId.value) || frameLogs.value[0]
})
const frameLogSummary = computed(() => {
  if (!frameLogs.value.length) return null
  const totals = frameLogs.value.reduce(
    (acc, item) => {
      acc.score += item.assessment.score
      acc.branch += item.assessment.features.branch_score
      acc.leaf += item.assessment.features.leaf_score
      acc.yellow += item.assessment.features.yellow_leaf_score
      acc.needsPruning += item.assessment.needs_pruning ? 1 : 0
      acc.highRisk += item.assessment.level === 'high' ? 1 : 0
      acc.unpruned += item.stats.Unpruned
      return acc
    },
    { score: 0, branch: 0, leaf: 0, yellow: 0, needsPruning: 0, highRisk: 0, unpruned: 0 },
  )
  const count = frameLogs.value.length
  return {
    count,
    averageScore: totals.score / count,
    needsPruning: totals.needsPruning,
    highRisk: totals.highRisk,
    unpruned: totals.unpruned,
    features: {
      branch_score: totals.branch / count,
      leaf_score: totals.leaf / count,
      yellow_leaf_score: totals.yellow / count,
    },
  }
})
const selectedGrowthFeatures = computed(() => selectedFrameLog.value?.assessment.features || currentAssessment.value?.features || null)
const selectedGrowthEstimate = computed(() => buildGrowthEstimate(selectedGrowthFeatures.value, '点击左侧日志图片查看该帧长势。'))
const selectedGrowthMetrics = computed(() => buildGrowthMetrics(selectedGrowthFeatures.value))
const overallGrowthEstimate = computed(() => buildGrowthEstimate(frameLogSummary.value?.features || null, '开始视频检测后生成总体长势评估。'))
const overallGrowthMetrics = computed(() => buildGrowthMetrics(frameLogSummary.value?.features || null))
const growthTrend = computed(() => {
  if (frameLogs.value.length < 2) return { value: 0, label: '等待更多帧', tone: 'text-slate-600' }
  const newest = calculateGrowthScore(frameLogs.value[0].assessment.features)
  const oldest = calculateGrowthScore(frameLogs.value[frameLogs.value.length - 1].assessment.features)
  const value = newest - oldest
  if (value > 0.04) return { value, label: '长势改善', tone: 'text-emerald-700' }
  if (value < -0.04) return { value, label: '长势回落', tone: 'text-amber-700' }
  return { value, label: '整体平稳', tone: 'text-sky-700' }
})
const pruningPlan = computed(() => {
  const selectedLog = selectedFrameLog.value
  const assessment = selectedLog?.assessment || currentAssessment.value
  if (!assessment) {
    return {
      title: '等待检测结果',
      intensity: '待定',
      window: '检测后生成',
      focus: '先开始视频检测',
      steps: ['启动视频检测获取当前树冠特征', '复核分支、叶量和黄叶比例', '生成对应修剪强度和复查周期'],
    }
  }

  const features = assessment.features
  const needsPruning = assessment.needs_pruning
  const level = assessment.level
  const evidencePrefix = selectedLog ? `针对视频 ${selectedLog.timeLabel} 截图，` : ''

  if (needsPruning && level === 'high') {
    return {
      title: '重点疏枝修剪',
      intensity: '强',
      window: '3 天内处理',
      focus: '打开树冠通风透光空间',
      steps: [
        `${evidencePrefix}优先清理交叉枝、内膛密枝和下垂枝`,
        '对黄叶集中区域做局部清理并检查水肥状态',
        '修剪后 7 天复拍同角度视频复核',
      ],
    }
  }
  if (needsPruning) {
    return {
      title: '轻中度整理修剪',
      intensity: '中',
      window: '7 天内处理',
      focus: features.yellow_leaf_score >= 0.45 ? '兼顾黄叶清理' : '控制枝叶密度',
      steps: [
        `${evidencePrefix}对树冠边缘密集枝做选择性疏剪`,
        '保留主枝结构，避免一次性重剪',
        '修剪后补采一帧对比评分变化',
      ],
    }
  }
  return {
    title: '观察维护方案',
    intensity: '低',
    window: '14 天后复查',
    focus: features.yellow_leaf_score >= 0.45 ? '复核黄叶原因' : '保持现有树形',
    steps: [
      `${evidencePrefix}暂不做结构性修剪，仅清理枯黄叶和明显病弱枝`,
      '继续采集同航线视频建立趋势对比',
      '若分支密度或黄叶分继续升高再转入修剪计划',
    ],
  }
})

function toPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function formatVideoTime(seconds: number) {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safeSeconds / 60)
  const restSeconds = safeSeconds % 60
  return `${minutes}:${String(restSeconds).padStart(2, '0')}`
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value))
}

function calculateGrowthScore(features: GrowthFeatureScores) {
  return clamp01(0.46 * features.leaf_score + 0.26 * features.branch_score + 0.28 * (1 - features.yellow_leaf_score))
}

function buildGrowthEstimate(features: GrowthFeatureScores | null, emptyDescription: string) {
  if (!features) {
    return {
      score: null as number | null,
      label: '等待检测',
      tone: 'text-slate-700',
      description: emptyDescription,
    }
  }

  const score = calculateGrowthScore(features)
  if (score >= 0.72) {
    return {
      score,
      label: '长势旺盛',
      tone: 'text-emerald-700',
      description: '叶量和分支活跃度较高，后续重点关注枝叶过密。',
    }
  }
  if (score >= 0.46) {
    return {
      score,
      label: '长势正常',
      tone: 'text-sky-700',
      description: '树冠状态整体稳定，可结合通风透光需求做轻量修剪。',
    }
  }
  return {
    score,
    label: '长势偏弱',
    tone: 'text-amber-700',
    description: '黄叶或稀疏特征偏高，建议先复核养护状态再重剪。',
  }
}

function buildGrowthMetrics(features: GrowthFeatureScores | null) {
  return [
    { name: '叶量覆盖', value: features?.leaf_score ?? 0, hint: '反映树冠丰满度和遮挡程度' },
    { name: '分支活跃', value: features?.branch_score ?? 0, hint: '反映枝条密集与交叉情况' },
    { name: '健康叶色', value: features ? 1 - features.yellow_leaf_score : 0, hint: '黄叶比例越低，健康叶色分越高' },
  ]
}

function hashText(text: string) {
  let hash = 0
  for (const char of text) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }
  return hash
}

function bearingToText(value: number) {
  const directions = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']
  return directions[Math.round(value / 45) % directions.length]
}

function getFrameLogTitle(assessment: PruningAssessment, detectionsInFrame: PruningDetectResult['detections']) {
  const features = assessment.features
  if (assessment.level === 'high') return '高风险树冠'
  if (detectionsInFrame.some((item) => item.summary_name === 'Unpruned')) return '未修剪目标'
  if (features.branch_score >= 0.72) return '枝条密集'
  if (features.yellow_leaf_score >= 0.45) return '黄叶特征'
  if (features.leaf_score <= 0.35) return '叶量偏低'
  return '稳定树势'
}

function getFrameLogNote(assessment: PruningAssessment) {
  const features = assessment.features
  if (assessment.needs_pruning && assessment.level === 'high') return '分支密度和模型投票共同指向优先修剪。'
  if (assessment.needs_pruning) return features.yellow_leaf_score >= 0.45 ? '建议修剪并同步复核黄叶区域。' : '建议进行轻中度疏枝整理。'
  if (features.yellow_leaf_score >= 0.45) return '暂缓结构修剪，先复核黄叶来源。'
  return '作为当前树势和复拍对比的参考帧。'
}

function getFrameDistinctiveness(assessment: PruningAssessment, detectionsInFrame: PruningDetectResult['detections']) {
  const features = assessment.features
  return (
    assessment.score * 0.35 +
    features.branch_score * 0.25 +
    features.yellow_leaf_score * 0.25 +
    Math.min(1, detectionsInFrame.length / 3) * 0.15
  )
}

function selectFrameLog(logId: string) {
  selectedFrameLogId.value = logId
  frameLogSelectionPinned.value = true
}

function recordDetectionLog(
  imageUrl: string,
  result: PruningDetectResult,
  latency: number,
  currentTime: number,
) {
  const log: DetectionFrameLog = {
    id: `${Date.now()}-${Math.round(currentTime * 10)}`,
    time: currentTime,
    timeLabel: formatVideoTime(currentTime),
    imageUrl,
    title: getFrameLogTitle(result.pruning_assessment, result.detections),
    note: getFrameLogNote(result.pruning_assessment),
    assessment: result.pruning_assessment,
    detections: result.detections,
    stats: result.stats,
    latency,
    distinctiveness: getFrameDistinctiveness(result.pruning_assessment, result.detections),
  }

  const nextLogs = [log, ...frameLogs.value].slice(0, MAX_FRAME_LOGS)
  frameLogs.value = nextLogs
  if (!frameLogSelectionPinned.value || !nextLogs.some((item) => item.id === selectedFrameLogId.value)) {
    selectedFrameLogId.value = log.id
  }
}

function setMessage(text: string, tone: MessageTone = 'info') {
  message.value = text
  messageTone.value = tone
}

function getStoredTaskId() {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(TASK_STORAGE_KEY) || ''
}

function persistTaskId(taskId: string) {
  if (typeof window === 'undefined') return
  if (taskId) {
    window.localStorage.setItem(TASK_STORAGE_KEY, taskId)
  } else {
    window.localStorage.removeItem(TASK_STORAGE_KEY)
  }
}

function deriveTaskName(sourceName: string) {
  const fileName = sourceName.split(/[\\/]/).pop() || sourceName
  return fileName.replace(/\.[^/.]+$/, '') || 'pruning-task'
}

async function refreshHealth() {
  try {
    const result = await pruningApi.getHealth()
    backendOnline.value = true
    inferenceReady.value = result.data.inference_available ?? result.data.status === 'ready'
  } catch (error) {
    backendOnline.value = false
    inferenceReady.value = false
  }
}

async function loadPruningInfo() {
  try {
    const result = await pruningApi.getInfo()
    pruningInfo.value = result.data
  } catch {
    pruningInfo.value = null
  }
}

function mapTask(item: PruningVideoItem, index: number): PruningTask {
  return {
    id: item.id || `system-${index}-${item.name}`,
    taskName: item.task_name || item.name.replace(/\.[^/.]+$/, ''),
    videoName: item.name,
    videoUrl: item.url,
    source: item.source === 'upload' ? 'upload' : 'system',
    createdAt: item.created_at || '',
  }
}

function applyTaskCollections(tasks: PruningTask[]) {
  uploadedTasks.value = tasks.filter((item) => item.source === 'upload')
  sampleTasks.value = tasks.filter((item) => item.source === 'system')
}

function clearCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
}

function resetDetectionState() {
  currentStats.value = { Pruned: 0, Unpruned: 0 }
  detections.value = []
  currentAssessment.value = null
  frameLogs.value = []
  selectedFrameLogId.value = ''
  frameLogSelectionPinned.value = false
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
  autoDetectEnabled.value = false
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

function activateTask(
  task: PruningTask,
  options: {
    closeTaskPicker?: boolean
    updateMessage?: boolean
  } = {},
) {
  stopVideo()
  currentTaskId.value = task.id
  resetDetectionState()
  if (options.closeTaskPicker ?? true) {
    showTaskPicker.value = false
  }
  if (options.updateMessage ?? true) {
    setMessage(`已加载任务“${task.taskName}”，点击播放即可查看视频。`, 'success')
  }
}

async function loadSampleTasks(preferredTaskId = '', updateMessage = false) {
  try {
    const result = await pruningApi.getVideos()
    const tasks = result.data.videos
      .filter((item) => !item.name.toLowerCase().includes('source_mp4v'))
      .map(mapTask)

    applyTaskCollections(tasks)

    if (!taskLibrary.value.length) {
      stopVideo()
      currentTaskId.value = ''
      resetDetectionState()
      persistTaskId('')
      if (updateMessage) {
        setMessage('当前没有可用的乔木修剪任务，请先上传或导入一个视频。', 'info')
      }
      return
    }

    const preferredId = preferredTaskId || getStoredTaskId()
    const preferredTask = preferredId ? taskLibrary.value.find((item) => item.id === preferredId) : null

    if (preferredTask && currentTaskId.value !== preferredTask.id) {
      activateTask(preferredTask, { closeTaskPicker: false, updateMessage })
      return
    }

    if (!taskLibrary.value.some((item) => item.id === currentTaskId.value)) {
      activateTask(taskLibrary.value[0], { closeTaskPicker: false, updateMessage })
    }
  } catch {
    setMessage('任务列表加载失败，请检查乔木修剪后端服务。', 'error')
  }
}

function openUploadPanel() {
  activeFeaturePanel.value = null
  showTaskPicker.value = false
  showControlPanel.value = false
  showTaskSummaryPanel.value = false
  showUploadPanel.value = true
}

function closeUploadPanel() {
  showUploadPanel.value = false
}

function toggleTaskPicker() {
  activeFeaturePanel.value = null
  showUploadPanel.value = false
  showControlPanel.value = false
  showTaskSummaryPanel.value = false
  showTaskPicker.value = !showTaskPicker.value
}

function closeTaskPicker() {
  showTaskPicker.value = false
}

function toggleControlPanel() {
  activeFeaturePanel.value = null
  showUploadPanel.value = false
  showTaskPicker.value = false
  showTaskSummaryPanel.value = false
  showControlPanel.value = !showControlPanel.value
}

function closeControlPanel() {
  showControlPanel.value = false
}

function toggleTaskSummaryPanel() {
  activeFeaturePanel.value = null
  showUploadPanel.value = false
  showTaskPicker.value = false
  showControlPanel.value = false
  showTaskSummaryPanel.value = !showTaskSummaryPanel.value
}

function closeTaskSummaryPanel() {
  showTaskSummaryPanel.value = false
}

function openFeaturePanel(panel: FeaturePanelKey) {
  showUploadPanel.value = false
  showTaskPicker.value = false
  showControlPanel.value = false
  showTaskSummaryPanel.value = false
  activeFeaturePanel.value = activeFeaturePanel.value === panel ? null : panel
}

function closeFeaturePanel() {
  activeFeaturePanel.value = null
}

function onVideoFileSelect(event: Event) {
  uploadVideoFile.value = (event.target as HTMLInputElement).files?.[0] || null
}

function clearUploadDraft() {
  uploadTaskName.value = ''
  uploadVideoFile.value = null
  uploadSourcePath.value = DEFAULT_IMPORT_PATH
  uploadMode.value = 'file'
  if (uploadFileInputRef.value) {
    uploadFileInputRef.value.value = ''
  }
}

function buildTaskName() {
  if (uploadTaskName.value.trim()) return uploadTaskName.value.trim()
  if (uploadMode.value === 'file' && uploadVideoFile.value) {
    return deriveTaskName(uploadVideoFile.value.name)
  }
  return deriveTaskName(uploadSourcePath.value.trim())
}

function locateUploadedTask(result: PruningTaskMutationResult) {
  return (
    taskLibrary.value.find((item) => item.id === result.id) ||
    taskLibrary.value.find((item) => item.id === result.task_id) ||
    taskLibrary.value.find((item) => item.videoUrl === result.url) ||
    taskLibrary.value.find((item) => item.videoName === result.video_name)
  )
}

function extractUploadErrorMessage(error: unknown) {
  const requestError = error as {
    code?: string
    message?: string
    response?: {
      data?: {
        detail?: string
        message?: string
      }
    }
  }

  const detail = requestError.response?.data?.detail || requestError.response?.data?.message
  if (detail) return detail

  if (requestError.code === 'ECONNABORTED' || requestError.message?.toLowerCase().includes('timeout')) {
    return '大体积 4K/HEVC 视频仍在本地转码中，请稍后到任务管理中查看新任务。'
  }

  return '上传失败，请检查视频文件或本地路径是否有效，并确认后端服务已启动。'
}

async function confirmUploadTask() {
  if (!uploadReady.value) {
    setMessage(uploadMode.value === 'file' ? '请先选择一个视频文件。' : '请先输入有效的视频路径。', 'error')
    return
  }

  const taskName = buildTaskName()
  uploadingTask.value = true

  try {
    let result: Awaited<ReturnType<typeof pruningApi.uploadTask>>
    if (uploadMode.value === 'file' && uploadVideoFile.value) {
      const form = new FormData()
      form.append('task_name', taskName)
      form.append('video', uploadVideoFile.value)
      result = await pruningApi.uploadTask(form)
    } else {
      result = await pruningApi.importTaskFromPath({
        task_name: taskName,
        video_path: uploadSourcePath.value.trim(),
      })
    }

    await loadSampleTasks(result.data.id || result.data.task_id || '', false)
    const uploadedTask = locateUploadedTask(result.data)
    clearUploadDraft()
    closeUploadPanel()

    if (uploadedTask) {
      activateTask(uploadedTask, { closeTaskPicker: false, updateMessage: false })
    }

    if (result.data.transcoded) {
      setMessage(
        `任务“${taskName}”上传成功，已自动转为浏览器可播放的 ${result.data.playback_codec?.toUpperCase() || 'H.264'} 格式。`,
        'success',
      )
    } else {
      setMessage(`任务“${taskName}”上传成功，刷新页面或重启系统后仍可在任务管理中重新加载。`, 'success')
    }
  } catch (error) {
    setMessage(extractUploadErrorMessage(error), 'error')
  } finally {
    uploadingTask.value = false
  }
}

async function deleteUploadedTask(task: PruningTask) {
  if (task.source !== 'upload' || deletingTaskId.value) return
  if (!window.confirm(`确认删除任务“${task.taskName}”吗？删除后将无法在任务管理中再次加载。`)) return

  const removedCurrentTask = currentTaskId.value === task.id
  deletingTaskId.value = task.id

  try {
    await pruningApi.deleteTask(task.id)
    if (removedCurrentTask) {
      currentTaskId.value = ''
      persistTaskId('')
      stopVideo()
      resetDetectionState()
    }

    await loadSampleTasks('', false)
    setMessage(`任务“${task.taskName}”已删除。`, 'success')
  } catch {
    setMessage('删除失败，请检查后端任务记录目录。', 'error')
  } finally {
    deletingTaskId.value = ''
  }
}

function selectTask(task: PruningTask) {
  activateTask(task)
}

async function startVideoPlayback() {
  const video = videoRef.value
  if (!video || !canPlay.value) {
    setMessage('请先从任务管理中加载一个可播放的视频任务。', 'error')
    return false
  }

  try {
    video.muted = true
    video.playsInline = true
    await video.play()
    return true
  } catch {
    isPlaying.value = false
    setMessage('视频播放失败，请重新加载任务后重试。', 'error')
    return false
  }
}

async function toggleVideoDetection() {
  const video = videoRef.value
  if (!video || !canPlay.value) {
    setMessage('请先从任务管理中加载一个可播放的视频任务。', 'error')
    return
  }
  if (!backendOnline.value) {
    setMessage('后端未就绪，当前无法开始乔木修剪视频检测。', 'error')
    return
  }

  if (!video.paused && autoDetectEnabled.value) {
    autoDetectEnabled.value = false
    video.pause()
    return
  }

  autoDetectEnabled.value = true
  lastDetectBucket.value = -1
  if (!video.paused) {
    setMessage(inferenceReady.value ? '已切换为乔木修剪视频检测。' : '视频正在播放；AI 检测尚未就绪，请安装对应模型与推理依赖。', 'info')
    return
  }

  const started = await startVideoPlayback()
  if (!started) {
    autoDetectEnabled.value = false
  }
}

async function replayVideo() {
  const video = videoRef.value
  if (!video) return
  if (!backendOnline.value) {
    setMessage('后端未就绪，当前无法重新开始视频检测。', 'error')
    return
  }

  video.currentTime = 0
  lastDetectBucket.value = -1
  autoDetectEnabled.value = true
  if (video.paused) {
    const started = await startVideoPlayback()
    if (!started) {
      autoDetectEnabled.value = false
    }
    return
  }

  setMessage('已从头开始乔木修剪视频检测。', 'info')
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
  setMessage(
    autoDetectEnabled.value ? '自动识别已开启，播放视频时会按设定频率执行检测。' : '自动识别已关闭，当前仅播放视频。',
    'info',
  )
}

function onPlay() {
  isPlaying.value = true
  if (!autoDetectEnabled.value) {
    setMessage('视频正在播放，自动识别当前处于关闭状态。', 'info')
    return
  }
  setMessage(inferenceReady.value ? '正在进行乔木修剪检测。' : '视频正在播放；AI 检测尚未就绪，请安装对应模型与推理依赖。', 'info')
}

function onPause() {
  isPlaying.value = false
  autoDetectEnabled.value = false
  if (canPlay.value) {
    setMessage('视频检测已暂停。', 'info')
  }
}

function onEnded() {
  isPlaying.value = false
  autoDetectEnabled.value = false
  setMessage('演示播放完成，可以重新播放继续查看。', 'info')
}

function onVideoError() {
  isPlaying.value = false
  autoDetectEnabled.value = false
  setMessage('当前任务视频无法播放，请尝试重新加载任务或重新上传视频。', 'error')
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
    setMessage('AI 检测尚未就绪，请安装对应模型与推理依赖；视频仍可播放。', 'info')
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
    const imageUrl = captureCanvas.toDataURL('image/jpeg', 0.8)
    const image = imageUrl.split(',')[1]

    const startedAt = performance.now()
    const result = await pruningApi.detectFrame(image, confThreshold.value, iouThreshold.value)
    const latency = Math.round(performance.now() - startedAt)
    apiLatency.value = latency
    detections.value = result.data.detections
    currentStats.value = result.data.stats
    currentAssessment.value = result.data.pruning_assessment
    recordDetectionLog(imageUrl, result.data, latency, video.currentTime)
    lastCaptureSize.value = { width, height }
    drawDetections(width, height)
  } catch {
    setMessage('乔木修剪检测失败，请确认模型已经正常加载。', 'error')
  } finally {
    detecting.value = false
  }
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
    Pruned: '#22c55e',
    PrunedTree: '#10b981',
    Unpruned: '#ef4444',
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
    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, x + 5, Math.max(0, y - 18))
  }
}

watch(currentTaskId, (value) => {
  persistTaskId(value)
})

onMounted(async () => {
  loading.value = true
  await Promise.all([refreshHealth(), loadSampleTasks(getStoredTaskId(), false), loadPruningInfo()])
  loading.value = false
  healthTimer = window.setInterval(refreshHealth, 10000)
  window.addEventListener('resize', syncCanvasSize)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
  window.removeEventListener('resize', syncCanvasSize)
  stopVideo()
})
</script>

<template>
  <div class="relative min-h-screen overflow-hidden bg-slate-50 text-slate-800 xl:flex xl:h-screen xl:min-h-0 xl:flex-col">
    <div class="pointer-events-none absolute top-[-10%] right-[-6%] h-[40%] w-[40%] rounded-full bg-emerald-300/18 blur-[120px]"></div>
    <div class="pointer-events-none absolute bottom-[-12%] left-[-6%] h-[40%] w-[40%] rounded-full bg-lime-300/16 blur-[120px]"></div>
    <div class="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPBlVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgwLCAwLCAwLCAwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')]"></div>

    <div class="relative z-10 px-4 pt-4 md:px-6 xl:shrink-0">
      <InspectionHeader title="乔木修剪检测" :task-name="currentTaskName" :online="backendOnline">
        <template #actions>
          <button
            class="shrink-0 rounded-2xl border border-emerald-100 bg-emerald-50 px-5 py-3 text-sm font-medium text-emerald-800 transition hover:border-emerald-200 hover:bg-emerald-100"
            @click="toggleTaskSummaryPanel"
          >
            任务信息
          </button>
          <button
            title="乔木地图方位展示"
            class="inline-flex shrink-0 items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-medium transition"
            :class="activeFeaturePanel === 'map' ? 'border-teal-300 bg-teal-100 text-teal-800' : 'border-teal-100 bg-teal-50 text-teal-800 hover:border-teal-200 hover:bg-teal-100'"
            @click="openFeaturePanel('map')"
          >
            <MapPinned class="h-4 w-4" />
            <span>地图方位</span>
          </button>
          <button
            title="乔木长势估计"
            class="inline-flex shrink-0 items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-medium transition"
            :class="activeFeaturePanel === 'growth' ? 'border-lime-300 bg-lime-100 text-lime-800' : 'border-lime-100 bg-lime-50 text-lime-800 hover:border-lime-200 hover:bg-lime-100'"
            @click="openFeaturePanel('growth')"
          >
            <Sprout class="h-4 w-4" />
            <span>长势估计</span>
          </button>
          <button
            title="修剪方案推荐"
            class="inline-flex shrink-0 items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-medium transition"
            :class="activeFeaturePanel === 'plan' ? 'border-green-300 bg-green-100 text-green-800' : 'border-green-100 bg-green-50 text-green-800 hover:border-green-200 hover:bg-green-100'"
            @click="openFeaturePanel('plan')"
          >
            <ClipboardList class="h-4 w-4" />
            <span>修剪方案</span>
          </button>
          <button
            class="shrink-0 rounded-2xl border border-emerald-200 bg-emerald-100 px-5 py-3 text-sm font-medium text-emerald-800 shadow-[0_10px_25px_-18px_rgba(34,197,94,0.35)] transition hover:border-emerald-300 hover:bg-emerald-200"
            @click="toggleControlPanel"
          >
            实时控制
          </button>
          <button
            class="shrink-0 rounded-2xl bg-gradient-to-r from-emerald-500 to-green-400 px-5 py-3 text-sm font-medium text-white shadow-[0_10px_25px_-15px_rgba(34,197,94,0.8)] transition hover:from-emerald-600 hover:to-green-500"
            @click="openUploadPanel"
          >
            上传任务
          </button>
          <button
            class="shrink-0 rounded-2xl border border-cyan-100 bg-cyan-50 px-5 py-3 text-sm font-medium text-cyan-800 transition hover:border-cyan-200 hover:bg-cyan-100"
            @click="toggleTaskPicker"
          >
            任务管理
          </button>
        </template>
      </InspectionHeader>
    </div>

    <FloatingNotice :message="message" :tone="messageTone" :duration="3500" centered />

    <main class="relative z-10 grid min-h-[calc(100vh-104px)] grid-cols-1 gap-6 px-4 pb-4 pt-2 md:px-6 md:pb-6 xl:min-h-0 xl:flex-1 xl:grid-cols-[320px_minmax(0,1fr)] xl:pb-3" data-testid="pruning-viewport-layout">
      <aside class="space-y-5 xl:min-h-0 xl:overflow-hidden">
        <section class="rounded-[28px] border border-white bg-white/88 p-5 shadow-[0_12px_40px_-20px_rgba(34,197,94,0.2)]">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-lg font-semibold text-slate-900">运行状态</h2>
            <span class="flex items-center gap-2 text-sm text-slate-600">
              <span class="h-2.5 w-2.5 rounded-full" :class="backendOnline ? 'bg-emerald-400' : 'bg-red-400'"></span>
              {{ backendOnline ? '后端在线' : '后端离线' }}
            </span>
          </div>

          <div class="mt-4 space-y-3 text-sm text-slate-600">
            <div class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
              <span>当前状态</span>
              <span class="font-medium text-slate-900">{{ statusText }}</span>
            </div>
            <div class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
              <span>推理设备</span>
              <span class="font-medium text-slate-900">{{ deviceText }}</span>
            </div>
          </div>
        </section>

        <section class="rounded-[28px] border border-white bg-white/88 p-5 shadow-[0_12px_40px_-20px_rgba(34,197,94,0.2)]">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-lg font-semibold text-slate-900">修剪判定</h2>
            <span class="rounded-full border px-3 py-1 text-xs font-semibold" :class="assessmentClass">
              {{ currentAssessment?.decision || '等待检测' }}
            </span>
          </div>

          <div class="mt-4 rounded-2xl border px-4 py-3" :class="assessmentClass">
            <div class="flex items-end justify-between gap-3">
              <div>
                <div class="text-xs font-semibold uppercase tracking-[0.2em]">综合评分</div>
                <div class="mt-2 text-3xl font-semibold">{{ currentAssessment ? toPercent(currentAssessment.score) : '--' }}</div>
              </div>
              <div class="text-right text-sm">
                <div>风险等级 {{ assessmentLevelText }}</div>
                <div>模型 {{ currentAssessment ? toPercent(currentAssessment.model_vote.score) : '--' }}</div>
              </div>
            </div>
          </div>

          <div class="mt-4 space-y-3 text-sm text-slate-600">
            <div class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
              <span>分支密度</span>
              <span class="font-medium text-slate-900">{{ currentAssessment ? toPercent(currentAssessment.features.branch_score) : '--' }}</span>
            </div>
            <div class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
              <span>叶量覆盖</span>
              <span class="font-medium text-slate-900">{{ currentAssessment ? toPercent(currentAssessment.features.leaf_score) : '--' }}</span>
            </div>
            <div class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
              <span>黄叶比例</span>
              <span class="font-medium text-slate-900">{{ currentAssessment ? toPercent(currentAssessment.features.yellow_leaf_score) : '--' }}</span>
            </div>
          </div>

          <div v-if="currentAssessment?.reasons.length" class="mt-4 space-y-2">
            <div
              v-for="reason in currentAssessment.reasons"
              :key="reason"
              class="rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3 text-sm text-slate-600"
            >
              {{ reason }}
            </div>
          </div>
        </section>

        <section class="rounded-[28px] border border-white bg-white/88 p-5 shadow-[0_12px_40px_-20px_rgba(34,197,94,0.2)]">
          <h2 class="text-lg font-semibold text-slate-900">模型信息</h2>
          <div class="mt-4 space-y-3 text-sm text-slate-600">
            <div class="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
              <span>模型文件</span>
              <span class="max-w-[160px] truncate font-medium text-slate-900">{{ pruningInfo?.model.name || '加载中' }}</span>
            </div>
            <div class="rounded-2xl border border-slate-200 bg-slate-50/90 px-4 py-3">
              <div class="mb-2 text-xs text-slate-500">识别类别</div>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="item in pruningInfo?.model.classes || []"
                  :key="item"
                  class="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
                >
                  {{ item }}
                </span>
              </div>
            </div>
          </div>
        </section>
      </aside>

      <section class="min-h-0">
        <div class="rounded-[28px] border border-white bg-white/88 px-4 pb-2 pt-4 shadow-[0_12px_40px_-20px_rgba(34,197,94,0.2)] xl:flex xl:h-full xl:min-h-0 xl:flex-col">
          <DetectionVideoFrame
            class="h-[calc(100vh-340px)] min-h-[520px] max-h-[820px] xl:h-auto xl:min-h-0 xl:max-h-none xl:flex-1"
            data-testid="pruning-video-frame"
            label="YOLO 乔木修剪检测"
            :status="detecting ? '帧分析中' : autoDetectEnabled && isPlaying ? '视频检测中' : isPlaying ? '实时播放' : '等待启动'"
            :playing="isPlaying"
            :disabled="!canPlay || (!backendOnline && !isPlaying)"
            :current-time="videoCurrentTime"
            :duration="videoDuration"
            :empty="!canPlay && !loading"
            empty-text="请先上传任务，或从任务管理中加载一个已保存的视频。"
            @toggle="toggleVideoDetection"
            @replay="replayVideo"
            @seek="seekVideo"
          >
            <video
              :key="currentTaskId || currentVideoUrl"
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
      v-if="activeFeaturePanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeFeaturePanel"
    >
      <div class="max-h-[calc(100vh-48px)] w-full max-w-[1280px] overflow-y-auto rounded-[32px] border border-white bg-white/95 p-6 shadow-[0_24px_80px_-24px_rgba(34,197,94,0.32)] md:p-7">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">{{ featurePanelTitle }}</h3>
            <p class="mt-1 text-sm text-slate-500">{{ featurePanelSummary }}</p>
          </div>
          <button
            class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            title="关闭"
            @click="closeFeaturePanel"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <div v-if="activeFeaturePanel === 'map'" class="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]" data-testid="pruning-map-panel">
          <div class="relative min-h-[570px] overflow-hidden rounded-3xl border border-slate-300 bg-[#dfe8d5] shadow-inner">
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_18%_22%,rgba(34,197,94,0.28),transparent_20%),radial-gradient(circle_at_72%_38%,rgba(22,163,74,0.3),transparent_25%),radial-gradient(circle_at_44%_80%,rgba(101,163,13,0.24),transparent_22%),linear-gradient(135deg,#e9efdf_0%,#cad9bd_100%)]"></div>
            <div class="absolute inset-0 opacity-45 bg-[linear-gradient(rgba(71,85,105,0.12)_1px,transparent_1px),linear-gradient(90deg,rgba(71,85,105,0.12)_1px,transparent_1px)] bg-[size:64px_64px]"></div>
            <div class="absolute -left-[8%] top-[18%] h-16 w-[116%] rotate-[8deg] border-y-4 border-white/80 bg-slate-400/75 shadow-[0_0_0_2px_rgba(100,116,139,0.35)]"></div>
            <div class="absolute left-[34%] top-[-10%] h-[120%] w-10 rotate-[-17deg] border-x-2 border-white/70 bg-slate-300/80"></div>
            <div class="absolute left-[6%] top-[48%] h-[42%] w-[35%] rounded-[45%] border border-emerald-700/20 bg-emerald-700/20"></div>
            <div class="absolute right-[8%] top-[14%] h-[58%] w-[34%] rounded-[42%] border border-green-800/20 bg-green-700/20"></div>

            <svg class="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <polyline :points="treeMapRoutePoints" fill="none" stroke="rgba(255,255,255,0.95)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
              <polyline :points="treeMapRoutePoints" fill="none" stroke="#0f766e" stroke-width="0.65" stroke-dasharray="2 1.5" stroke-linecap="round" stroke-linejoin="round" />
              <line :x1="treeMapDronePosition.x" :y1="treeMapDronePosition.y" :x2="treeMapPosition.x" :y2="treeMapPosition.y" stroke="#f97316" stroke-width="0.45" stroke-dasharray="1.4 1.2" />
            </svg>

            <div
              class="absolute z-10 -translate-x-1/2 -translate-y-1/2"
              :style="{ left: `${treeMapPosition.x}%`, top: `${treeMapPosition.y}%` }"
            >
              <div class="absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 animate-ping rounded-full border border-rose-400/50"></div>
              <div class="flex h-12 w-12 items-center justify-center rounded-full border-4 border-white bg-rose-500 text-white shadow-[0_12px_32px_-10px_rgba(244,63,94,0.9)]">
                <MapPinned class="h-6 w-6" />
              </div>
              <div class="absolute left-1/2 top-14 w-max -translate-x-1/2 rounded-xl bg-slate-950/85 px-3 py-1.5 text-xs font-medium text-white shadow-lg">目标乔木 T-{{ String(treeMapSeed % 900 + 100) }}</div>
            </div>

            <div
              class="absolute z-10 -translate-x-1/2 -translate-y-1/2"
              :style="{ left: `${treeMapDronePosition.x}%`, top: `${treeMapDronePosition.y}%` }"
            >
              <div class="flex h-11 w-11 items-center justify-center rounded-full border-4 border-white bg-sky-600 text-white shadow-[0_12px_30px_-10px_rgba(2,132,199,0.9)]">
                <Compass class="h-6 w-6" :style="{ transform: `rotate(${treeMapHeading}deg)` }" />
              </div>
              <div class="absolute left-1/2 top-13 w-max -translate-x-1/2 rounded-xl bg-white/95 px-3 py-1 text-[11px] font-semibold text-sky-800 shadow">无人机位置</div>
            </div>

            <div class="absolute left-4 top-4 rounded-2xl border border-white/70 bg-slate-950/80 px-4 py-3 text-white shadow-lg backdrop-blur">
              <div class="flex items-center gap-2 text-xs font-semibold"><span class="h-2 w-2 animate-pulse rounded-full bg-emerald-400"></span>GNSS 定位正常</div>
              <div class="mt-1 font-mono text-[11px] text-slate-300">{{ treeMapCoordinate.lat }}, {{ treeMapCoordinate.lng }}</div>
            </div>
            <div class="absolute right-4 top-4 flex h-24 w-24 items-center justify-center rounded-full border border-white/80 bg-white/90 shadow-lg backdrop-blur">
              <div class="absolute inset-2 rounded-full border border-slate-200"></div>
              <div class="absolute top-2 text-xs font-bold text-rose-600">N</div>
              <Compass class="h-10 w-10 text-emerald-700" :style="{ transform: `rotate(${treeMapBearing}deg)` }" />
              <div class="absolute bottom-2 text-[10px] font-semibold text-slate-600">{{ treeMapBearing }}°</div>
            </div>
            <div class="absolute bottom-4 left-4 rounded-2xl border border-white/80 bg-white/92 px-4 py-3 shadow-lg backdrop-blur">
              <div class="text-sm font-semibold text-slate-900">{{ currentTaskName }}</div>
              <div class="mt-1 text-xs text-slate-500">航迹 → 目标 · {{ treeMapDistance }} m · {{ treeMapBearingText }}</div>
            </div>
            <div class="absolute bottom-5 right-5 flex items-end gap-2 text-[10px] font-semibold text-slate-700">
              <div class="h-1 w-20 bg-slate-800"></div><span>20 m</span>
            </div>
          </div>

          <div class="space-y-3">
            <div class="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4">
              <div class="flex items-center justify-between">
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">目标方位解算</div>
                <span class="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-semibold text-emerald-700">已锁定</span>
              </div>
              <div class="mt-3 flex items-end justify-between gap-3">
                <div><div class="text-3xl font-semibold text-slate-900">{{ treeMapBearingText }}</div><div class="mt-1 text-sm text-slate-500">真方位 {{ treeMapBearing }}°</div></div>
                <div class="text-right"><div class="text-2xl font-semibold text-emerald-700">{{ treeMapDistance }} m</div><div class="text-xs text-slate-500">水平距离</div></div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 text-sm">
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">无人机航向</div><div class="mt-1 font-semibold text-slate-900">{{ treeMapHeading }}°</div></div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">相对偏角</div><div class="mt-1 font-semibold text-slate-900">右偏 {{ Math.abs(treeMapRelativeAngle) }}°</div></div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">定位精度</div><div class="mt-1 font-semibold text-slate-900">± 0.8 m</div></div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-3"><div class="text-xs text-slate-500">建议复拍向</div><div class="mt-1 font-semibold text-slate-900">{{ bearingToText((treeMapBearing + 180) % 360) }}</div></div>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-white p-4 text-sm">
              <div class="font-semibold text-slate-900">任务位置</div>
              <div class="mt-3 space-y-2 text-slate-600">
                <div class="flex justify-between gap-3"><span>纬度</span><span class="font-mono font-medium text-slate-900">{{ treeMapCoordinate.lat }}° N</span></div>
                <div class="flex justify-between gap-3"><span>经度</span><span class="font-mono font-medium text-slate-900">{{ treeMapCoordinate.lng }}° E</span></div>
                <div class="flex justify-between gap-3"><span>目标编号</span><span class="font-medium text-slate-900">T-{{ String(treeMapSeed % 900 + 100) }}</span></div>
                <div class="flex justify-between gap-3"><span>识别目标</span><span class="font-medium text-slate-900">{{ totalDetections }} 个</span></div>
              </div>
            </div>

            <div class="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm leading-6 text-sky-900">
              <div class="font-semibold">复拍导航建议</div>
              从目标反方位 {{ (treeMapBearing + 180) % 360 }}° 进入，保持约 {{ Math.max(8, Math.round(treeMapDistance * 0.35)) }} m 横向距离，使树冠中心位于画面中轴。
            </div>
            <div class="px-1 text-[11px] leading-5 text-slate-400">演示坐标由当前任务生成，用于方位与复拍流程展示；接入无人机 GNSS 后可替换为真实遥测。</div>
          </div>
        </div>

        <div v-else-if="activeFeaturePanel === 'growth'" class="mt-5 grid min-h-[620px] gap-4 lg:grid-cols-[350px_310px_minmax(0,1fr)]" data-testid="growth-panel">
          <section class="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-slate-50 p-4" aria-label="长势检测日志">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700"><Image class="h-4 w-4" />检测日志</div>
                <p class="mt-2 text-xs leading-5 text-slate-500">视频检测过程中逐渐生成，点击图片查看单帧评估。</p>
              </div>
              <span class="shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">{{ frameLogs.length }}/{{ MAX_FRAME_LOGS }}</span>
            </div>
            <div v-if="frameLogs.length" class="mt-4 max-h-[520px] space-y-3 overflow-y-auto pr-1">
              <button
                v-for="(log, index) in frameLogs"
                :key="log.id"
                type="button"
                data-testid="growth-log-card"
                class="group w-full overflow-hidden rounded-2xl border bg-white text-left transition hover:border-emerald-300 hover:shadow-sm"
                :class="selectedFrameLog?.id === log.id ? 'border-emerald-400 ring-2 ring-emerald-100' : 'border-slate-200'"
                :aria-pressed="selectedFrameLog?.id === log.id"
                @click="selectFrameLog(log.id)"
              >
                <div class="grid grid-cols-[132px_minmax(0,1fr)]">
                  <img :src="log.imageUrl" :alt="`长势日志 ${index + 1}`" class="h-24 w-full object-cover" />
                  <div class="flex min-w-0 flex-col justify-center px-3 py-2">
                    <div class="truncate text-sm font-semibold text-slate-900">{{ log.title }}</div>
                    <div class="mt-1 text-xs text-slate-500">{{ log.timeLabel }} · 风险 {{ toPercent(log.assessment.score) }}</div>
                    <div class="mt-2 text-[11px] font-medium" :class="log.assessment.needs_pruning ? 'text-amber-700' : 'text-emerald-700'">{{ log.assessment.needs_pruning ? '需关注修剪' : '长势稳定' }}</div>
                  </div>
                </div>
              </button>
            </div>
            <div v-else class="mt-4 flex flex-1 flex-col items-center justify-center rounded-2xl border border-dashed border-emerald-200 bg-white px-5 text-center text-sm leading-6 text-slate-500">
              <Camera class="mb-3 h-8 w-8 text-emerald-500" />
              开始视频检测后，日志图片会按检测频率逐张生成。
            </div>
          </section>

          <section class="rounded-2xl border border-slate-200 bg-slate-50 p-5" data-testid="selected-growth-assessment" aria-label="当前帧生长情况评估">
            <div class="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">当前帧生长评估</div>
            <div v-if="selectedFrameLog" class="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white">
              <img :src="selectedFrameLog.imageUrl" :alt="selectedFrameLog.title" class="h-32 w-full object-cover" />
              <div class="flex items-center justify-between px-3 py-2 text-xs"><span class="truncate font-medium text-slate-900">{{ selectedFrameLog.title }}</span><span class="shrink-0 text-slate-500">{{ selectedFrameLog.timeLabel }}</span></div>
            </div>
            <div class="mt-5 text-5xl font-semibold" :class="selectedGrowthEstimate.tone">{{ selectedGrowthEstimate.score === null ? '--' : toPercent(selectedGrowthEstimate.score) }}</div>
            <div class="mt-3 text-xl font-semibold text-slate-900" data-testid="selected-growth-label">{{ selectedGrowthEstimate.label }}</div>
            <p class="mt-3 text-sm leading-6 text-slate-600">{{ selectedGrowthEstimate.description }}</p>
            <div class="mt-5 space-y-4">
              <div v-for="metric in selectedGrowthMetrics" :key="metric.name">
                <div class="flex items-center justify-between text-xs"><span class="text-slate-500">{{ metric.name }}</span><span class="font-semibold text-slate-900">{{ toPercent(metric.value) }}</span></div>
                <div class="mt-2 h-2 overflow-hidden rounded-full bg-white"><div class="h-full rounded-full bg-emerald-500 transition-all" :style="{ width: toPercent(metric.value) }"></div></div>
              </div>
            </div>
            <div v-if="selectedFrameLog" class="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs leading-5 text-emerald-900">{{ selectedFrameLog.note }}</div>
          </section>

          <section class="rounded-2xl border border-emerald-200 bg-white p-5 shadow-sm" data-testid="overall-growth-assessment" aria-label="总体生长情况评估">
            <div class="flex items-center justify-between gap-3">
              <div class="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">总体生长情况评估</div>
              <span class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">融合 {{ frameLogSummary?.count || 0 }} 帧</span>
            </div>
            <div class="mt-5 grid grid-cols-[minmax(0,1fr)_120px] items-end gap-4">
              <div><div class="text-5xl font-semibold" :class="overallGrowthEstimate.tone">{{ overallGrowthEstimate.score === null ? '--' : toPercent(overallGrowthEstimate.score) }}</div><div class="mt-3 text-2xl font-semibold text-slate-900">{{ overallGrowthEstimate.label }}</div></div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-center"><div class="text-xs text-slate-500">变化趋势</div><div class="mt-2 font-semibold" :class="growthTrend.tone">{{ growthTrend.label }}</div><div v-if="frameLogs.length > 1" class="mt-1 text-xs text-slate-500">{{ growthTrend.value >= 0 ? '+' : '' }}{{ toPercent(growthTrend.value) }}</div></div>
            </div>
            <p class="mt-4 text-sm leading-6 text-slate-600">{{ overallGrowthEstimate.description }}</p>

            <div class="mt-5 space-y-3">
              <div v-for="metric in overallGrowthMetrics" :key="metric.name" class="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                <div class="flex items-center justify-between gap-3"><div><div class="font-medium text-slate-900">{{ metric.name }}</div><div class="mt-1 text-xs text-slate-500">{{ metric.hint }}</div></div><div class="text-lg font-semibold text-slate-900">{{ toPercent(metric.value) }}</div></div>
                <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div class="h-full rounded-full bg-emerald-500 transition-all" :style="{ width: toPercent(metric.value) }"></div></div>
              </div>
            </div>

            <div class="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
              <div class="rounded-2xl border border-slate-200 bg-slate-50 px-2 py-3"><div class="text-slate-500">平均风险</div><div class="mt-1 text-lg font-semibold text-slate-900">{{ frameLogSummary ? toPercent(frameLogSummary.averageScore) : '--' }}</div></div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 px-2 py-3"><div class="text-slate-500">需修剪帧</div><div class="mt-1 text-lg font-semibold text-slate-900">{{ frameLogSummary?.needsPruning || 0 }}</div></div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 px-2 py-3"><div class="text-slate-500">高风险帧</div><div class="mt-1 text-lg font-semibold text-slate-900">{{ frameLogSummary?.highRisk || 0 }}</div></div>
            </div>
            <div class="mt-4 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-900">总体评估随检测日志逐帧更新；日志越接近 15 张，跨画面的判断越稳定。</div>
          </section>
        </div>

        <div v-else class="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
          <section class="rounded-2xl border border-slate-200 bg-slate-50 p-5" aria-label="视频截图日志">
            <div class="flex items-start justify-between gap-4">
              <div>
                <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">
                  <Camera class="h-4 w-4" />
                  视频截图日志
                </div>
                <p class="mt-2 text-sm text-slate-500">点击任意截图，右侧将生成该帧对应的修剪方案。</p>
              </div>
              <div class="shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                {{ frameLogs.length }} / {{ MAX_FRAME_LOGS }} 张
              </div>
            </div>

            <div v-if="frameLogs.length" class="mt-4 grid max-h-[570px] grid-cols-2 gap-3 overflow-y-auto pr-1 sm:grid-cols-3">
              <button
                v-for="(log, index) in frameLogs"
                :key="log.id"
                type="button"
                data-testid="pruning-log-card"
                class="group overflow-hidden rounded-2xl border bg-white text-left transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-sm"
                :class="selectedFrameLog?.id === log.id ? 'border-emerald-400 ring-2 ring-emerald-100' : 'border-slate-200'"
                :aria-pressed="selectedFrameLog?.id === log.id"
                @click="selectFrameLog(log.id)"
              >
                <div class="relative">
                  <img :src="log.imageUrl" :alt="`日志 ${index + 1}：${log.title}`" class="h-24 w-full object-cover" />
                  <span class="absolute left-2 top-2 rounded-full bg-slate-950/70 px-2 py-0.5 text-[10px] font-medium text-white">
                    {{ log.timeLabel }}
                  </span>
                </div>
                <div class="px-3 py-2">
                  <div class="truncate text-xs font-semibold text-slate-900">日志 {{ index + 1 }} · {{ log.title }}</div>
                  <div class="mt-1 flex items-center justify-between text-[11px] text-slate-500">
                    <span>风险 {{ toPercent(log.assessment.score) }}</span>
                    <span>{{ log.assessment.needs_pruning ? '建议修剪' : '观察维护' }}</span>
                  </div>
                </div>
              </button>
            </div>
            <div v-else class="mt-4 flex min-h-[430px] flex-col items-center justify-center rounded-2xl border border-dashed border-emerald-200 bg-white px-6 text-center text-sm leading-6 text-slate-500">
              <Camera class="mb-3 h-8 w-8 text-emerald-500" />
              开始视频检测后，系统会按检测频率自动生成截图日志，最多保留 15 张。
            </div>
          </section>

          <section data-testid="selected-pruning-plan" class="rounded-2xl border border-emerald-200 bg-white p-5 shadow-sm" aria-label="当前截图修剪方案">
            <div class="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">当前截图修剪方案</div>
            <template v-if="selectedFrameLog">
              <div class="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
                <img :src="selectedFrameLog.imageUrl" :alt="selectedFrameLog.title" class="h-36 w-full object-cover" />
                <div class="flex items-center justify-between gap-3 px-3 py-2 text-xs text-slate-600">
                  <span class="truncate font-medium text-slate-900">{{ selectedFrameLog.title }}</span>
                  <span class="shrink-0">{{ selectedFrameLog.timeLabel }} / {{ selectedFrameLog.latency }} ms</span>
                </div>
              </div>

              <div class="mt-4 text-2xl font-semibold text-slate-900" data-testid="pruning-plan-title">{{ pruningPlan.title }}</div>
              <p class="mt-2 text-sm leading-6 text-slate-500">{{ selectedFrameLog.note }}</p>
              <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <div class="text-slate-500">修剪强度</div>
                  <div class="mt-1 font-semibold text-slate-900">{{ pruningPlan.intensity }}</div>
                </div>
                <div class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <div class="text-slate-500">处理窗口</div>
                  <div class="mt-1 font-semibold text-slate-900">{{ pruningPlan.window }}</div>
                </div>
              </div>
              <div class="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-900">
                重点：{{ pruningPlan.focus }}
              </div>

              <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
                <div class="rounded-xl border border-slate-200 px-3 py-2 text-slate-500">分支密度 <span class="float-right font-semibold text-slate-900">{{ toPercent(selectedFrameLog.assessment.features.branch_score) }}</span></div>
                <div class="rounded-xl border border-slate-200 px-3 py-2 text-slate-500">叶量覆盖 <span class="float-right font-semibold text-slate-900">{{ toPercent(selectedFrameLog.assessment.features.leaf_score) }}</span></div>
                <div class="rounded-xl border border-slate-200 px-3 py-2 text-slate-500">黄叶风险 <span class="float-right font-semibold text-slate-900">{{ toPercent(selectedFrameLog.assessment.features.yellow_leaf_score) }}</span></div>
                <div class="rounded-xl border border-slate-200 px-3 py-2 text-slate-500">未修剪目标 <span class="float-right font-semibold text-slate-900">{{ selectedFrameLog.stats.Unpruned }}</span></div>
              </div>

              <div class="mt-4 space-y-2">
                <div
                  v-for="(step, index) in pruningPlan.steps"
                  :key="step"
                  class="flex gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600"
                >
                  <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-700">{{ index + 1 }}</div>
                  <div class="leading-6">{{ step }}</div>
                </div>
              </div>
            </template>
            <div v-else class="mt-4 flex min-h-[520px] items-center justify-center rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/60 px-6 text-center text-sm leading-6 text-emerald-900">
              暂无截图。开始检测并生成日志后，可在左侧选择图片查看对应方案。
            </div>
          </section>
        </div>
      </div>
    </div>

    <div
      v-if="showTaskSummaryPanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeTaskSummaryPanel"
    >
      <div class="w-full max-w-[760px] rounded-[32px] border border-white bg-white/95 p-6 shadow-[0_24px_80px_-24px_rgba(34,197,94,0.32)] md:p-7">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">任务信息</h3>
            <p class="mt-1 text-sm text-slate-500">当前任务相关信息统一放在这里，页面主体保持更简洁。</p>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="closeTaskSummaryPanel"
          >
            关闭
          </button>
        </div>

        <div class="mt-5 grid gap-4 md:grid-cols-2">
          <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-4">
            <div class="text-slate-500">当前视频</div>
            <div class="mt-1 font-semibold text-slate-900">{{ currentVideoName }}</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-4">
            <div class="text-slate-500">任务来源</div>
            <div class="mt-1 font-semibold text-slate-900">{{ currentTask?.source === 'upload' ? '本地上传任务' : '系统示例任务' }}</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-4">
            <div class="text-slate-500">系统状态</div>
            <div class="mt-1 font-semibold text-slate-900">{{ statusText }}</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-4">
            <div class="text-slate-500">任务总数</div>
            <div class="mt-1 font-semibold text-slate-900">{{ taskLibrary.length }}</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50/90 p-4 md:col-span-2">
            <div class="text-slate-500">最新提示</div>
            <div class="mt-2 rounded-2xl border px-4 py-3 text-sm font-medium" :class="messageClass">{{ message }}</div>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="showUploadPanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeUploadPanel"
    >
      <div class="w-full max-w-[900px] rounded-[32px] border border-white bg-white/95 p-6 shadow-[0_24px_80px_-24px_rgba(34,197,94,0.32)] md:p-7">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">上传任务</h3>
            <p class="hidden mt-1 text-sm text-slate-500">
              上传后会写入任务记录；如果视频编码不适合网页播放，系统会自动转成浏览器可播放格式。
            </p>
            <div class="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
              注意：系统已关闭自动转码，上传任务仅接受 <span class="font-semibold">MP4 + H.264 / AVC1</span> 视频。
            </div>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="closeUploadPanel"
          >
            关闭
          </button>
        </div>

        <div class="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div class="space-y-4">
            <label class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <div class="mb-2 font-medium text-slate-900">任务名称</div>
              <input
                v-model="uploadTaskName"
                type="text"
                placeholder="例如：东侧乔木修剪巡检任务"
                class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-emerald-300"
              />
            </label>

            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div class="mb-3 text-sm font-medium text-slate-900">导入方式</div>
              <div class="grid grid-cols-2 gap-3">
                <button
                  class="rounded-2xl border px-4 py-3 text-sm font-medium transition"
                  :class="uploadMode === 'file' ? 'border-emerald-300 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-white text-slate-700'"
                  @click="uploadMode = 'file'"
                >
                  选择文件
                </button>
                <button
                  class="rounded-2xl border px-4 py-3 text-sm font-medium transition"
                  :class="uploadMode === 'path' ? 'border-emerald-300 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-white text-slate-700'"
                  @click="uploadMode = 'path'"
                >
                  粘贴路径
                </button>
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <label
              v-if="uploadMode === 'file'"
              class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
            >
              <div class="mb-2 font-medium text-slate-900">选择视频文件</div>
              <input ref="uploadFileInputRef" type="file" accept="video/*" @change="onVideoFileSelect" />
              <div class="mt-2 text-xs text-slate-500">{{ uploadVideoFile?.name || '尚未选择视频文件' }}</div>
            </label>

            <label
              v-else
              class="block rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"
            >
              <div class="mb-2 font-medium text-slate-900">本地视频路径</div>
              <input
                v-model="uploadSourcePath"
                type="text"
                class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-emerald-300"
                placeholder="请输入部署服务器上的视频绝对路径"
              />
              <div class="mt-2 text-xs leading-5 text-slate-500">
                此路径必须位于运行后端的服务器上；从其他电脑访问时，请使用“上传文件”。
              </div>
            </label>

            <div class="hidden rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/70 px-4 py-4 text-sm text-emerald-900">
              当前示例里，系统自带视频能播放，是因为它本身就是浏览器友好的 H.264；上传视频如果不是这个编码，系统会自动转码。
            </div>

            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-700">
              <div class="font-medium text-slate-900">上传要求</div>
              <div class="mt-2">1. 文件后缀：<span class="font-mono">.mp4</span></div>
              <div>2. 视频编码：<span class="font-mono">H.264 / AVC1</span></div>
              <div>3. 系统不再自动转码，不符合要求的视频会直接上传失败</div>
              <div>4. 请先在本地完成转码后再上传</div>
            </div>

            <button
              class="w-full rounded-2xl bg-gradient-to-r from-emerald-500 to-green-400 px-4 py-3 text-sm font-semibold text-white transition hover:from-emerald-600 hover:to-green-500 disabled:bg-slate-200 disabled:text-slate-400"
              :disabled="!uploadReady || uploadingTask"
              @click="confirmUploadTask"
            >
              {{ uploadButtonText }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="showTaskPicker"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeTaskPicker"
    >
      <div class="w-full max-w-[980px] rounded-[32px] border border-white bg-white/95 p-6 shadow-[0_24px_80px_-24px_rgba(34,197,94,0.32)] md:p-7">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">任务管理</h3>
            <p class="mt-1 text-sm text-slate-500">这里的上传任务会被持久化保存，刷新页面或重启系统后仍可重新加载。</p>
          </div>
          <button
            class="rounded-full border border-slate-200 px-3 py-1 text-sm text-slate-600 transition hover:border-slate-300 hover:text-slate-900"
            @click="closeTaskPicker"
          >
            关闭
          </button>
        </div>

        <div v-if="taskLibrary.length > 0" class="mt-5 max-h-[65vh] space-y-3 overflow-y-auto pr-1">
          <div
            v-for="task in taskLibrary"
            :key="task.id"
            class="rounded-2xl border px-4 py-4 transition"
            :class="currentTaskId === task.id ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-slate-50'"
          >
            <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <div class="truncate text-base font-semibold text-slate-900">{{ task.taskName }}</div>
                  <span class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-500">
                    {{ task.source === 'upload' ? '本地上传任务' : '系统示例' }}
                  </span>
                  <span
                    v-if="currentTaskId === task.id"
                    class="rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-medium text-emerald-700"
                  >
                    当前任务
                  </span>
                </div>
                <div class="mt-2 text-sm text-slate-600">{{ task.videoName }}</div>
                <div v-if="task.createdAt" class="mt-1 text-xs text-slate-400">上传时间：{{ task.createdAt }}</div>
              </div>

              <div class="flex shrink-0 flex-wrap items-center gap-3">
                <button
                  class="rounded-2xl border border-emerald-200 bg-white px-4 py-2 text-sm font-medium text-emerald-700 transition hover:border-emerald-300 hover:bg-emerald-50"
                  @click="selectTask(task)"
                >
                  {{ currentTaskId === task.id ? '重新加载' : '加载任务' }}
                </button>
                <button
                  v-if="task.source === 'upload'"
                  class="rounded-2xl border border-rose-200 bg-white px-4 py-2 text-sm font-medium text-rose-600 transition hover:border-rose-300 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                  :disabled="deletingTaskId === task.id"
                  @click.stop="deleteUploadedTask(task)"
                >
                  {{ deletingTaskId === task.id ? '删除中...' : '删除任务' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="mt-4 rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/60 px-4 py-10 text-center text-sm text-slate-600">
          暂无可管理任务，请先上传或导入一个乔木修剪视频。
        </div>
      </div>
    </div>

    <div
      v-if="showControlPanel"
      class="absolute inset-0 z-30 flex items-center justify-center bg-white/35 p-6 backdrop-blur-[3px]"
      @click.self="closeControlPanel"
    >
      <div class="w-full max-w-[860px] rounded-[32px] border border-white bg-white/95 p-6 shadow-[0_24px_80px_-24px_rgba(34,197,94,0.32)] md:p-7">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">实时控制</h3>
            <p class="mt-1 text-sm text-slate-500">调整当前乔木修剪任务的检测阈值和自动识别频率。</p>
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
            <input v-model.number="confThreshold" type="range" min="0.1" max="0.9" step="0.01" class="w-full accent-emerald-500" />

            <div class="mb-3 mt-5 flex items-center justify-between text-sm text-slate-600">
              <span>IoU</span>
              <span>{{ iouThreshold.toFixed(2) }}</span>
            </div>
            <input v-model.number="iouThreshold" type="range" min="0.1" max="0.9" step="0.01" class="w-full accent-emerald-500" />
          </div>

          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div class="mb-3 flex items-center justify-between text-sm text-slate-600">
              <span>自动识别</span>
              <button
                class="rounded-full px-3 py-1 text-xs font-semibold"
                :class="autoDetectEnabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'"
                @click="toggleAutoDetect"
              >
                {{ autoDetectEnabled ? '已开启' : '已关闭' }}
              </button>
            </div>

            <div class="mb-3 mt-5 flex items-center justify-between text-sm text-slate-600">
              <span>检测间隔</span>
              <span>{{ detectIntervalSec.toFixed(1) }} s</span>
            </div>
            <input v-model.number="detectIntervalSec" type="range" min="0.5" max="3" step="0.1" class="w-full accent-emerald-500" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
