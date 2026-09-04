import { http, request } from '../utils/request'

export interface WallVideoItem {
  id?: string
  name: string
  task_name?: string
  created_at?: string
  source?: 'system' | 'upload'
  url: string
  start_at?: number
  subtitle_name?: string
  subtitle_url?: string
  has_subtitle?: boolean
}

export interface WallDetectionItem {
  class: number
  name: 'Crack' | 'Seepage' | 'TileSpalling' | 'Hollowing'
  cn: string
  bbox: [number, number, number, number]
  conf: number
}

export interface WallStats {
  Crack: number
  Seepage: number
  TileSpalling: number
  Hollowing: number
}

export interface WallDetectResult {
  detections: WallDetectionItem[]
  count: number
  stats: WallStats
  annotated_image: string
  inference_ms: number
  image_size?: {
    width: number
    height: number
  }
}

export interface WallTaskAnnotationFrame {
  frame: number
  time: number
  detections: WallDetectionItem[]
}

export interface WallTaskAnnotationsResult {
  fps: number
  start_frame: number
  frames: WallTaskAnnotationFrame[]
  count: number
}

export interface WallInfoResult {
  system: {
    cuda_available: boolean
    device: string
  }
  model: {
    name: string
    classes: string[]
  }
  config: {
    confidence: number
    iou: number
  }
  capabilities: {
    video_file: boolean
    single_frame_detection: boolean
  }
}

export interface WallTaskMutationResult {
  id: string
  name: string
  task_name: string
  created_at: string
  url: string
  task_id?: string
  video_name?: string
  source?: 'system' | 'upload'
  start_at?: number
  subtitle_name?: string
  subtitle_url?: string
  has_subtitle?: boolean
}

export interface WallTelemetryData {
  frameCnt?: number
  time?: number
  datetime?: string
  latitude?: number
  longitude?: number
  relAlt?: number
  absAlt?: number
  gbYaw?: number
  gbPitch?: number
  gbRoll?: number
}

export interface WallDetectionLogItem {
  id: string
  time: number
  detections: WallDetectionItem[]
  image_size: { width?: number; height?: number }
  telemetry: WallTelemetryData
  image_file: string
  image_url: string
  created_at: string
}

export interface WallAssessmentResult {
  log_count: number
  detection_count: number
  stats: WallStats
  average_confidence: number
  score: number
  level: string
  title: string
  summary: string
  actions: string[]
  zones: Array<{ name: string; count: number }>
  gps_points: Array<{ time: number; latitude: number; longitude: number; rel_alt: number; abs_alt: number }>
  location_summary: string
}

export const wallApi = {
  getHealth() {
    return request<{ status: string; inference_available?: boolean; model?: string; error?: string }>({ url: '/wall/health', method: 'GET' })
  },
  getVideos() {
    return request<{ videos: WallVideoItem[] }>({ url: '/wall/videos', method: 'GET' })
  },
  uploadTask(form: FormData) {
    return request<WallTaskMutationResult>({
      url: '/wall/tasks/upload',
      method: 'POST',
      data: form,
      timeout: 600000,
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  importTaskFromPath(payload: { task_name: string; video_path: string; subtitle_path: string }) {
    return request<WallTaskMutationResult>({
      url: '/wall/tasks/import-path',
      method: 'POST',
      data: payload,
      timeout: 600000,
    })
  },
  renameTask(taskId: string, taskName: string) {
    return http.post<WallTaskMutationResult>(`/wall/tasks/${taskId}/rename`, { task_name: taskName })
  },
  deleteTask(taskId: string) {
    return http.delete<WallTaskMutationResult>(`/wall/tasks/${taskId}`)
  },
  getTaskAnnotations(taskId: string) {
    return request<WallTaskAnnotationsResult>({ url: `/wall/tasks/${taskId}/annotations`, method: 'GET' })
  },
  getTaskLogs(taskId: string) {
    return request<{ logs: WallDetectionLogItem[]; assessment: WallAssessmentResult }>({
      url: `/wall/tasks/${taskId}/logs`,
      method: 'GET',
    })
  },
  createTaskLog(taskId: string, payload: {
    time: number
    detections: WallDetectionItem[]
    annotated_image: string
    image_size?: { width: number; height: number }
    telemetry?: WallTelemetryData | null
  }) {
    return request<WallDetectionLogItem>({
      url: `/wall/tasks/${taskId}/logs`,
      method: 'POST',
      data: payload,
      timeout: 30000,
    })
  },
  getTaskAssessment(taskId: string) {
    return request<WallAssessmentResult>({ url: `/wall/tasks/${taskId}/assessment`, method: 'GET' })
  },
  getInfo() {
    return request<WallInfoResult>({ url: '/wall/info', method: 'GET' })
  },
  detectFrame(image: string, conf?: number, iou?: number) {
    return request<WallDetectResult>({
      url: '/wall/detect',
      method: 'POST',
      data: { image, conf, iou },
    })
  },
  updateConfig(confidence?: number, iou?: number) {
    return request<{ confidence: number; iou: number }>({
      url: '/wall/config',
      method: 'POST',
      data: { confidence, iou },
    })
  },
}
