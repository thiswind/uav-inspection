import { ref, onUnmounted } from 'vue';
import type { PatrolTask } from '../types/patrol';
import { getTaskStatus } from '../api1/heatmap/task';

export function useTaskSync() {
  const currentTask = ref<PatrolTask | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  
  let pollingTimer: number | null = null;
  let onUpdate: ((data: {
    taskId: string;
    status: PatrolTask['status'];
    progress: number;
    error?: string | null;
    isCompleted: boolean;
  }) => void) | null = null;

  const fetchTaskStatus = async (taskId: string) => {
    try {
      const data = await getTaskStatus(taskId);
      currentTask.value = {
        taskId: data.taskId,
        taskName: currentTask.value?.taskName || '巡检分析',
        uploadTime: currentTask.value?.uploadTime || new Date().toISOString(),
        status: data.status,
        progress: data.progress
      };

      if (onUpdate) {
        onUpdate(data);
      }

      if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        stopPolling();
      }
    } catch (err) {
      error.value = '获取任务状态失败';
      stopPolling();
    }
  };

  const startTaskPolling = (
    taskId: string,
    onStatusUpdate?: (data: {
      taskId: string;
      status: PatrolTask['status'];
      progress: number;
      error?: string | null;
      isCompleted: boolean;
    }) => void,
    interval = 3000,
    timeout = 300000
  ) => {
    isLoading.value = true;
    error.value = null;
    onUpdate = onStatusUpdate || null;
    
    // 立即执行一次
    fetchTaskStatus(taskId);

    // 开启轮询
    pollingTimer = window.setInterval(() => {
      fetchTaskStatus(taskId);
    }, interval);

    // 设置总体超时防死循环 (5分钟)
    setTimeout(() => {
      if (pollingTimer) {
        stopPolling();
        error.value = '任务处理超时';
      }
    }, timeout);
  };

  const stopPolling = () => {
    if (pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }
    isLoading.value = false;
    onUpdate = null;
  };

  // 保证逻辑闭环：组件卸载时必须清除定时器
  onUnmounted(() => {
    stopPolling();
  });

  return {
    currentTask,
    isLoading,
    error,
    startTaskPolling,
    stopPolling
  };
}