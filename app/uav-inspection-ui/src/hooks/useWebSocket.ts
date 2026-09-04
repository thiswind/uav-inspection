import { ref, onUnmounted } from 'vue';
import type { WSFrameMessage } from '../types/patrol';

/**
 * 巡检任务实时推理 WebSocket Hook
 * 支持自动重连、心跳检测
 */
export function useInferenceSocket() {
  // 存储 WebSocket 实例
  const socket = ref<WebSocket | null>(null);

  // 连接状态
  const isConnected = ref(false);

  // 错误信息
  const error = ref<string | null>(null);

  // 重连相关状态
  let reconnectTimer: number | null = null;
  let heartbeatTimer: number | null = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 1000; // 1s
  const maxReconnectDelay = 30000; // 30s
  let currentTaskId: string | null = null;
  let messageCallback: ((data: WSFrameMessage) => void) | null = null;

  /**
   * 计算指数退避延迟
   */
  const getReconnectDelay = (): number => {
    const delay = Math.min(
      baseReconnectDelay * Math.pow(2, reconnectAttempts),
      maxReconnectDelay
    );
    // 添加 ±20% 随机抖动
    return delay * (0.8 + Math.random() * 0.4);
  };

  /**
   * 清理所有定时器
   */
  const clearTimers = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
  };

  /**
   * 启动心跳 (每 15 秒 ping 一次)
   */
  const startHeartbeat = () => {
    stopHeartbeat();
    heartbeatTimer = window.setInterval(() => {
      if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        try {
          socket.value.send(JSON.stringify({ type: 'ping' }));
        } catch (_) {
          // ping 发送失败，忽略
        }
      }
    }, 15000);
  };

  const stopHeartbeat = () => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
  };

  /**
   * 断开连接 (清理所有资源)
   */
  const disconnect = () => {
    clearTimers();
    stopHeartbeat();
    reconnectAttempts = 0;
    currentTaskId = null;
    messageCallback = null;
    if (socket.value) {
      socket.value.onopen = null;
      socket.value.onmessage = null;
      socket.value.onerror = null;
      socket.value.onclose = null;
      if (socket.value.readyState === WebSocket.OPEN || socket.value.readyState === WebSocket.CONNECTING) {
        socket.value.close(1000, 'Client disconnect');
      }
      socket.value = null;
    }
    isConnected.value = false;
  };

  /**
   * 建立连接
   * @param taskId 任务ID
   * @param onMessage 收到数据后的回调函数
   */
  const connect = (taskId: string, onMessage: (data: WSFrameMessage) => void) => {
    // 如果已有连接且是同一任务，不重复连接
    if (socket.value && currentTaskId === taskId && socket.value.readyState === WebSocket.OPEN) {
      return;
    }

    // 断开旧连接
    if (socket.value) {
      disconnect();
    }

    currentTaskId = taskId;
    messageCallback = onMessage;
    reconnectAttempts = 0;

    doConnect();
  };

  /**
   * 执行实际的 WebSocket 连接
   */
  const doConnect = () => {
    if (!currentTaskId) return;

    const explicitBase = (import.meta as any).env?.VITE_API_BASE_URL;
    // 开发模式：走 Vite proxy 自动转发；生产模式：使用环境变量
    const apiBase = explicitBase || '';
    let wsBase: string;
    if (apiBase) {
      wsBase = apiBase.replace(/^http/, 'ws').replace(/\/$/, '');
    } else if ((import.meta as any).env?.BASE_URL && (import.meta as any).env.BASE_URL !== '/') {
      // 子路径部署：ws(s)://<host><BASE_URL>（前缀由 BASE_URL 提供）
      wsBase = `${location.protocol.replace('http', 'ws')}//${location.host}${(import.meta as any).env.BASE_URL.replace(/\/$/, '')}`;
    } else {
      wsBase = `${location.protocol.replace('http', 'ws')}//${location.host}`;
    }
    const wsUrl = `${wsBase}/api/v1/ws/inference/${currentTaskId}`;

    console.log(`[WebSocket] 连接: ${wsUrl} (尝试 #${reconnectAttempts + 1})`);

    try {
      socket.value = new WebSocket(wsUrl);

      socket.value.onopen = () => {
        isConnected.value = true;
        error.value = null;
        reconnectAttempts = 0;
        startHeartbeat();
        console.log(`[WebSocket] 任务 ${currentTaskId} 推理流已连接`);
      };

      socket.value.onmessage = (event) => {
        try {
          const data: WSFrameMessage = JSON.parse(event.data);
          // 过滤心跳响应
          if (data.taskId && messageCallback) {
            messageCallback(data);
          }
        } catch (e) {
          console.error('[WebSocket] 数据解析错误:', e);
        }
      };

      socket.value.onerror = (_event) => {
        error.value = 'WebSocket 连接发生错误';
        console.error('[WebSocket] Error');
      };

      socket.value.onclose = (event) => {
        isConnected.value = false;
        stopHeartbeat();
        console.log(`[WebSocket] 连接已关闭: code=${event.code} reason=${event.reason}`);

        // 非主动关闭时，尝试重连
        if (event.code !== 1000 && currentTaskId) {
          attemptReconnect();
        }
      };
    } catch (e) {
      error.value = '无法创建 WebSocket 连接';
      console.error('[WebSocket] 创建失败:', e);
      // 连接创建失败也尝试重连
      if (currentTaskId) {
        attemptReconnect();
      }
    }
  };

  /**
   * 尝试重连 (指数退避)
   */
  const attemptReconnect = () => {
    if (reconnectAttempts >= maxReconnectAttempts) {
      console.warn(`[WebSocket] 已达最大重连次数 (${maxReconnectAttempts})，放弃重连`);
      error.value = '连接失败，已达最大重试次数';
      return;
    }

    const delay = getReconnectDelay();
    reconnectAttempts++;
    console.log(`[WebSocket] 将在 ${(delay / 1000).toFixed(1)}s 后重连...`);

    reconnectTimer = window.setTimeout(() => {
      if (currentTaskId) {
        doConnect();
      }
    }, delay);
  };

  // 保证逻辑闭环：组件卸载时自动销毁连接
  onUnmounted(() => {
    disconnect();
  });

  return {
    socket,
    isConnected,
    error,
    connect,
    disconnect,
  };
}