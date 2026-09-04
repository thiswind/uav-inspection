import { pestHttp, type ApiResponse } from './request'

export interface MissionCommandRequest {
	command: string
	params?: Record<string, any>
}

export interface MissionCommandResult {
	status: string
}

export interface RouteItem {
	id: string
	name: string
	waypoints: number
	duration_min: number
	area_mu?: number
	status?: 'running' | 'idle' | 'standby'
}

export interface MissionCreateRequest {
	route_id: string
	model_id: string
	name?: string
	scheduled_at?: string
	params?: Record<string, any>
}

export interface MissionDetail {
	id: string
	name: string
	status: string
	route_id: string
	model_id: string
	created_at?: string
	scheduled_at?: string
}

// 下发任务/云台控制指令
export const controlMission = (
	payload: MissionCommandRequest
): Promise<ApiResponse<MissionCommandResult>> =>
	pestHttp.post<MissionCommandResult>('/mission/control', payload)

// 获取航线列表
export const listRoutes = (): Promise<ApiResponse<RouteItem[]>> =>
	pestHttp.get<RouteItem[]>('/routes')

// 激活指定航线
export const activateRoute = (routeId: string): Promise<ApiResponse<RouteItem>> =>
	pestHttp.post<RouteItem>(`/routes/${routeId}/activate`, {})

// 创建巡检任务
export const createMission = (
	payload: MissionCreateRequest
): Promise<ApiResponse<MissionDetail>> =>
	pestHttp.post<MissionDetail>('/missions', payload)

// 获取任务详情
export const getMission = (missionId: string): Promise<ApiResponse<MissionDetail>> =>
	pestHttp.get<MissionDetail>(`/missions/${missionId}`)

// 取消任务
export const cancelMission = (missionId: string): Promise<ApiResponse<MissionDetail>> =>
	pestHttp.post<MissionDetail>(`/missions/${missionId}/cancel`, {})
