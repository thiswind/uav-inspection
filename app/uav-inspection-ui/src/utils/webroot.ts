// src/utils/webroot.ts
// 子路径部署支持：把「根绝对路径」转换为带部署前缀的路径。
// 开发/根部署时 BASE_URL 为 '/'，各函数原样返回，行为不变；
// 挂子路径（如 /uav/）构建时 VITE_BASE 传入，index.html 与运行时路径自动带前缀。
export const BASE_URL: string = (import.meta as any).env?.BASE_URL || '/'

function stripSlashes(p: string): string {
  return p.replace(/^\/+/, '').replace(/\/+$/, '')
}

// 根绝对路径 → 带前缀路径；传入非根相对/完整 URL 原样返回
export function webPath(absolutePath: string): string {
  if (!absolutePath) return absolutePath
  if (/^(https?:|data:|blob:)/i.test(absolutePath)) return absolutePath
  if (!absolutePath.startsWith('/')) return absolutePath
  return `/${stripSlashes(BASE_URL)}/${stripSlashes(absolutePath)}`.replace(/\/+$/, '/')
}

// WebSocket：根绝对路径 → 带前缀的 ws(s) 完整 URL
export function wsPath(absolutePath: string): string {
  const proto = location.protocol.replace('http', 'ws')
  return `${proto}//${location.host}${webPath(absolutePath)}`
}
