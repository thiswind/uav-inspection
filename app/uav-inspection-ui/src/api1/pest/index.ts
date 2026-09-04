import { buildPestUrl } from './request'
import { getTelemetry, getStatistics, type TelemetryData, type PestStatItem } from './status'
import {
  controlMission,
  listRoutes,
  activateRoute,
  createMission,
  getMission,
  cancelMission,
  type MissionCommandRequest,
  type MissionCommandResult,
  type MissionCreateRequest,
  type MissionDetail,
  type RouteItem
} from './mission'
import { listModels, activateModel, type VisionModelItem } from './disease'
import { listReports, buildReportDownloadUrl, type ReportItem } from './report'
import type { AgentMessage, AgentCommand } from './agent'

// 病虫害巡检模块的统一 API 入口
export const pestApi = {
  getTelemetry,
  getStatistics,
  controlMission,
  listRoutes,
  activateRoute,
  createMission,
  getMission,
  cancelMission,
  listModels,
  activateModel,
  listReports,
  buildReportDownloadUrl,
  videoUrl: buildPestUrl('/video'),
  videoFramesUrl: buildPestUrl('/video/frames')
}

export type {
  TelemetryData,
  PestStatItem,
  MissionCommandRequest,
  MissionCommandResult,
  MissionCreateRequest,
  MissionDetail,
  RouteItem,
  VisionModelItem,
  ReportItem,
  AgentMessage,
  AgentCommand
}
