// src/utils/request.ts
import axios, { type AxiosRequestConfig } from 'axios'
import { BASE_URL } from './webroot'

// 走 Vite proxy，生产环境由 Nginx 反代；子路径部署时带 BASE_URL 前缀
const BASE_URL_API = `${BASE_URL}api/v1`

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

const httpClient = axios.create({
  baseURL: BASE_URL_API,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export async function request<T>(config: AxiosRequestConfig): Promise<ApiResponse<T>> {
  const response = await httpClient.request<ApiResponse<T>>(config)
  return response.data
}

export const http = {
  get: <T>(url: string, params?: Record<string, any>) =>
    request<T>({ url, method: 'GET', params }),
  post: <T>(url: string, data: any) =>
    request<T>({ url, method: 'POST', data }),
  delete: <T>(url: string) =>
    request<T>({ url, method: 'DELETE' }),
  postForm: <T>(url: string, data: FormData, config?: AxiosRequestConfig) =>
    request<T>({ url, method: 'POST', data, headers: { 'Content-Type': 'multipart/form-data' }, ...config })
}
