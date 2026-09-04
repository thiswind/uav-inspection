import { pestHttp, type ApiResponse } from './request'

export interface VisionModelItem {
	id: string
	name: string
	runtime: 'edge' | 'cloud'
	status?: 'active' | 'standby'
	description?: string
}

// 获取视觉模型列表
export const listModels = (): Promise<ApiResponse<VisionModelItem[]>> =>
	pestHttp.get<VisionModelItem[]>('/models')

// 激活指定模型
export const activateModel = (modelId: string): Promise<ApiResponse<VisionModelItem>> =>
	pestHttp.post<VisionModelItem>(`/models/${modelId}/activate`, {})
