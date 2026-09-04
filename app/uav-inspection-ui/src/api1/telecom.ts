import { http, request } from '../utils/request'

export interface TelecomVideoItem {
  name: string
  url: string
}

export interface TelecomHealthData {
  status: string
  inference_available?: boolean
  model?: string
  error?: string
}

export interface TelecomConfig {
  confidence: number
  iou: number
}

export interface TelecomInfo {
  system: {
    cuda_available: boolean
    device: string
  }
  model: {
    name: string
    classes: string[]
  }
  config: TelecomConfig
  capabilities: {
    video_file: boolean
    single_frame_detection: boolean
  }
}

export interface TelecomDetection {
  class: number
  name: string
  cn: string
  bbox: [number, number, number, number]
  conf: number
}

export interface TelecomDetectResult {
  detections: TelecomDetection[]
  count: number
  stats: {
    Station: number
    Antenna: number
  }
  annotated_image: string
  inference_ms: number
}

export interface TelecomTaskItem {
  task_id: string
  task_name: string
  video_name: string
  srt_name: string
  created_at: string
  video_url: string
  srt_url: string
}

export interface TelecomDeletedTask {
  task_id: string
  task_name: string
  video_name: string
  srt_name: string
}

export const telecomApi = {
  getHealth: () => http.get<TelecomHealthData>('/telecom/health'),
  getVideos: () => http.get<{ videos: TelecomVideoItem[] }>('/telecom/videos'),
  getTasks: () => http.get<{ tasks: TelecomTaskItem[] }>('/telecom/tasks'),
  uploadTask: (form: FormData) =>
    request<TelecomTaskItem>({
      url: '/telecom/tasks/upload',
      method: 'POST',
      data: form,
      timeout: 120000,
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  renameTask: (taskId: string, taskName: string) =>
    http.post<TelecomTaskItem>(`/telecom/tasks/${taskId}/rename`, { task_name: taskName }),
  deleteTask: (taskId: string) =>
    http.delete<TelecomDeletedTask>(`/telecom/tasks/${taskId}`),
  getConfig: () => http.get<TelecomConfig>('/telecom/config'),
  updateConfig: (confidence?: number, iou?: number) =>
    http.post<TelecomConfig>('/telecom/config', { confidence, iou }),
  getInfo: () => http.get<TelecomInfo>('/telecom/info'),
  detectFrame: (image: string, conf: number, iou: number) =>
    http.post<TelecomDetectResult>('/telecom/detect', { image, conf, iou }),
}
