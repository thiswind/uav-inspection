import { http, type ApiResponse } from '../../utils/request'
import { BASE_URL } from '../../utils/webroot'

// 后端 API 基础配置（统一走 Vite proxy；子路径部署时带前缀）
export const API_BASE_URL = `${BASE_URL}api/v1`
export const PEST_BASE_PATH = '/pest'

// 生成病虫害模块的完整 URL
export const buildPestUrl = (path: string) => `${API_BASE_URL}${PEST_BASE_PATH}${path}`

export const pestHttp = {
	get: <T>(path: string, params?: Record<string, any>) =>
		http.get<T>(`${PEST_BASE_PATH}${path}`, params),
	post: <T>(path: string, data?: Record<string, any>) =>
		http.post<T>(`${PEST_BASE_PATH}${path}`, data ?? {})
}

export type { ApiResponse }
