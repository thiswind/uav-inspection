import { http, request } from '../utils/request'

export interface PruningVideoItem {
  id?: string
  name: string
  task_name?: string
  created_at?: string
  source?: 'system' | 'upload'
  url: string
}

export interface PruningDetectionItem {
  class: number
  name: string
  summary_name: 'Pruned' | 'Unpruned'
  cn: string
  bbox: [number, number, number, number]
  conf: number
}

export interface PruningDetectResult {
  detections: PruningDetectionItem[]
  count: number
  stats: {
    Pruned: number
    Unpruned: number
  }
  pruning_assessment: {
    needs_pruning: boolean
    decision: string
    level: 'low' | 'medium' | 'high'
    score: number
    feature_score: number
    model_vote: {
      score: number
      pruned_conf: number
      unpruned_conf: number
    }
    features: {
      branch_density: number
      leaf_coverage: number
      yellow_leaf_ratio: number
      branch_score: number
      leaf_score: number
      yellow_leaf_score: number
    }
    reasons: string[]
  }
  annotated_image: string
  inference_ms: number
}

export interface PruningInfoResult {
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
    segmentation_overlay: boolean
    feature_fusion?: boolean
  }
}

export interface PruningTaskMutationResult {
  id: string
  task_name: string
  url: string
  task_id?: string
  video_name?: string
  created_at?: string
  source?: 'system' | 'upload'
  name?: string
  transcoded?: boolean
  playback_codec?: string
}

export const pruningApi = {
  getHealth: () => http.get<{ status: string; inference_available?: boolean; model?: string; error?: string }>('/pruning/health'),
  getVideos: () => http.get<{ videos: PruningVideoItem[] }>('/pruning/videos'),
  uploadTask: (form: FormData) =>
    request<PruningTaskMutationResult>({
      url: '/pruning/tasks/upload',
      method: 'POST',
      data: form,
      timeout: 120000,
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  importTaskFromPath: (payload: { task_name: string; video_path: string }) =>
    request<PruningTaskMutationResult>({
      url: '/pruning/tasks/import-path',
      method: 'POST',
      data: payload,
      timeout: 120000,
    }),
  deleteTask: (taskId: string) =>
    http.delete<{
      task_id: string
      task_name: string
      video_name: string
    }>(`/pruning/tasks/${taskId}`),
  getInfo: () => http.get<PruningInfoResult>('/pruning/info'),
  detectFrame: (image: string, conf?: number, iou?: number) =>
    http.post<PruningDetectResult>('/pruning/detect', { image, conf, iou }),
}
