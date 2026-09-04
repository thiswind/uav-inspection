import { http, request } from '../utils/request'

export interface PowerVideoItem {
  id?: string
  name: string
  task_name?: string
  created_at?: string
  url: string
}

export interface PowerDetectionItem {
  class: number
  name: string
  cn: string
  bbox: [number, number, number, number]
  conf: number
}

export interface PowerDetectResult {
  detections: PowerDetectionItem[]
  count: number
  stats: {
    Wire: number
    WirePole: number
  }
  annotated_image: string
  inference_ms: number
}

export interface PowerInfoResult {
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

export const powerApi = {
  getHealth() {
    return request<{ status: string; inference_available?: boolean; model?: string; error?: string }>({ url: '/power/health', method: 'GET' })
  },
  getVideos() {
    return request<{ videos: PowerVideoItem[] }>({ url: '/power/videos', method: 'GET' })
  },
  uploadTask(form: FormData) {
    return http.postForm<{
      id: string
      task_id: string
      task_name: string
      video_name: string
      created_at: string
      url: string
    }>('/power/tasks/upload', form)
  },
  getInfo() {
    return request<PowerInfoResult>({ url: '/power/info', method: 'GET' })
  },
  detectFrame(image: string, conf?: number, iou?: number) {
    return request<PowerDetectResult>({
      url: '/power/detect',
      method: 'POST',
      data: { image, conf, iou },
    })
  },
}
