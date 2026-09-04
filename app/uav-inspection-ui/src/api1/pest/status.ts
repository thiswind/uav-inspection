import { pestHttp, type ApiResponse } from './request'

export interface TelemetryData {
	battery: number
	signal: number
	altitude: number
	speed: number
	satellites: number
	mode: string
}

export interface PestStatItem {
	name: string
	value: number
}

// 获取视频同步的遥测数据
export const getTelemetry = (videoTimeSec: number): Promise<ApiResponse<TelemetryData>> =>
	pestHttp.get<TelemetryData>('/telemetry', { video_time: videoTimeSec })

// 获取病害统计数据
export const getStatistics = (): Promise<ApiResponse<PestStatItem[]>> =>
	pestHttp.get<PestStatItem[]>('/statistics')
