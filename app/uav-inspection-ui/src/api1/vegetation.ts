import { http } from '../utils/request'

export interface ClassMetric {
  precision: number
  recall: number
  f1: number
  support: number
}

export interface VegetationModel {
  name: string
  algorithm: string
  description: string
  accuracy: number
  macro_f1: number
  classes: Record<string, ClassMetric>
  confusion_matrix: number[][]
  training_samples: number
  validation_samples: number
  status: string
  badge: string
  validation_title: string
  validation_note: string
  data_note: string
  confusion_url: string
}

export interface VegetationTask {
  key: string
  name: string
  uuid: string
  images: number
  status: string
  epsg: number
  tree_count: number
  tree_points: number
  unassigned_tree_points: number
  average_height_m: number
  median_height_m: number
  max_height_m: number
  shrub_area_m2: number
  shrub_patch_count: number
  largest_shrub_patch_m2: number
  shrub_mean_height_m: number
  green_area_m2: number
  green_patch_count: number
  largest_green_patch_m2: number
  green_coverage_ratio: number
  green_mean_confidence: number
  tree_preview_url: string
  shrub_preview_url: string
  green_preview_url: string
  webodm_url: string
}

export interface TreeMeasurement {
  tree_id: number
  points: number
  height_m: number
  crown_width_m: number
  crown_area_m2: number
  centroid_x: number
  centroid_y: number
  x_min: number
  x_max: number
  y_min: number
  y_max: number
  z_min: number
  z_max: number
}

export interface PointCloudBounds {
  minx: number
  maxx: number
  miny: number
  maxy: number
  minz: number
  maxz: number
}

export interface GreenAreaPointModel {
  version: string
  feature_names: string[]
  class_names: string[]
  means: number[][]
  variances: number[][]
  priors: number[]
  probability_threshold: number
}

export interface PointCloudScene {
  task_key: string
  source_file: string
  source_points: number
  display_points: number
  decimation_step: number
  epsg: number
  origin: { x: number; y: number; z: number }
  source_bounds: PointCloudBounds
  local_bounds: PointCloudBounds
  dimensions: string[]
  point_cloud_url: string
  green_model: GreenAreaPointModel
}

export interface VegetationOverview {
  model: VegetationModel | null
  models: Record<'height' | 'area', VegetationModel | null> | null
  tasks: VegetationTask[]
  totals: { tasks: number; trees: number; shrub_area_m2: number; green_area_m2: number; images: number }
}

export function getVegetationOverview() {
  return http.get<VegetationOverview>('/vegetation/overview')
}

export function getTreeMeasurements(taskKey: string, params: {
  query?: string
  minimum_height?: number
  sort_by?: string
  descending?: boolean
}) {
  return http.get<{ items: TreeMeasurement[]; total: number }>(`/vegetation/tasks/${taskKey}/trees`, params)
}

export function getPointCloudScene(taskKey: string) {
  return http.get<PointCloudScene>(`/vegetation/tasks/${taskKey}/scene`)
}
