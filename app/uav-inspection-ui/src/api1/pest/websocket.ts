// WebSocket 基础地址（开发模式走 Vite proxy，生产模式由 Nginx 反代；子路径部署时带前缀）
import { BASE_URL } from '../../utils/webroot'

export const WS_BASE_URL = `${location.protocol.replace('http', 'ws')}//${location.host}${BASE_URL}`

export interface WebSocketOptions {
	protocols?: string | string[]
	onOpen?: (event: Event) => void
	onClose?: (event: CloseEvent) => void
	onError?: (event: Event) => void
	onMessage?: (event: MessageEvent) => void
}

// 拼接 WS 完整路径
export const buildWsUrl = (path: string) => `${WS_BASE_URL}${path}`

// 创建并绑定事件的通用 WS 实例
export const createWebSocket = (url: string, options?: WebSocketOptions): WebSocket => {
	const socket = new WebSocket(url, options?.protocols)

	if (options?.onOpen) socket.addEventListener('open', options.onOpen)
	if (options?.onClose) socket.addEventListener('close', options.onClose)
	if (options?.onError) socket.addEventListener('error', options.onError)
	if (options?.onMessage) socket.addEventListener('message', options.onMessage)

	return socket
}

// Agent 对话通道
export const connectAgentSocket = (options?: WebSocketOptions): WebSocket =>
	createWebSocket(buildWsUrl('/ws/v1/agent/chat'), options)

// 系统日志流通道
export const connectSystemLogSocket = (options?: WebSocketOptions): WebSocket =>
	createWebSocket(buildWsUrl('/ws/v1/system/logs'), options)

// 遥测数据流通道
export const connectTelemetrySocket = (options?: WebSocketOptions): WebSocket =>
	createWebSocket(buildWsUrl('/ws/v1/pest/telemetry'), options)
