import request from './request';
import type { PatrolTask } from '../../types/patrol'; // 确保路径正

// 1. 获取任务列表
export const getTaskList = () => {
  return request<any, PatrolTask[]>({
    url: '/tasks', // 这里路径不需要改，因为 request.ts 已经有了 baseURL: '/api/v1'
    method: 'get'
  });
};

// 2. 上传视频与 SRT 文件 (带进度回调，SRT 可选)
export const uploadPatrolTask = (
  videoFile: File, 
  srtFile: File | null, 
  onProgress: (percent: number) => void
) => {
  const formData = new FormData();
  formData.append('video', videoFile);
  if (srtFile) formData.append('srt', srtFile);

  return request<any, { taskId: string }>({
    url: '/tasks/upload',
    method: 'post',
    data: formData,
    timeout: 600000, // 10 分钟，视频文件上传需要较长时间
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total) {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      }
    }
  });
};

// 3. 获取已完成任务的完整分析结果 (历史回放)
export const getTaskResult = (taskId: string) => {
  return request<any, {
    fps: number;
    totalFrames: number;
    telemetryData: any[]; // 完整的遥测数组
    trackingData: Record<number, any[]>; // 完整的轨迹字典
    alerts: any[]; // 历史告警记录
    historyChartData: number[]; // 折线图历史
    predictChartData: (number | null)[]; // 折线图预测
    isCompleted: boolean;
  }>({
    url: `/tasks/${taskId}/result`,
    method: 'get'
  });
};

// 4. 查询任务状态与进度
export const getTaskStatus = (taskId: string) => {
  return request<any, {
    taskId: string;
    status: PatrolTask['status'];
    progress: number;
    error?: string | null;
    isCompleted: boolean;
  }>({
    url: `/tasks/${taskId}/status`,
    method: 'get'
  });
};

// 5. 重命名任务
export const renameTask = (taskId: string, taskName: string) => {
  return request<any, { taskId: string; taskName: string }>({
    url: `/tasks/${taskId}/rename`,
    method: 'post',
    data: { taskName }
  });
};

// 6. 删除任务及其视频、字幕和名称元数据
export const deleteTask = (taskId: string) => {
  return request<any, { taskId: string }>({
    url: `/tasks/${taskId}`,
    method: 'delete'
  });
};

// 7. 导出分析报告 (直接下载文件)
export const exportTaskReport = (
  taskId: string,
  options?: { includeMinute?: boolean; includeAlerts?: boolean }
) => {
  const params = {
    include_minute: options?.includeMinute ?? true,
    include_alerts: options?.includeAlerts ?? true
  };
  // 通常导出接口会返回文件流，或者返回一个下载链接
  return request<any, Blob>({
    url: `/tasks/${taskId}/export`,
    method: 'get',
    params,
    responseType: 'blob' // 告诉 axios 接收二进制文件
  });
};
