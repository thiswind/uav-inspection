import { ref, type Ref, watch } from 'vue';
import type { TelemetryFrame, TrackTarget } from '../types/patrol';

interface VideoPlayerInstance {
  videoElement: HTMLVideoElement | null;
}

export function useVideoGISLink(
  videoComponentRef: Ref<VideoPlayerInstance | null>,
  telemetryData: Ref<TelemetryFrame[]>, // 存储全量或缓存数据
  trackingData: Ref<Record<number, TrackTarget[]>>,
  fpsRef: Ref<number>,
  pausedRef?: Ref<boolean>
) {
  const currentFrameId = ref(0);
  const currentTelemetry = ref<TelemetryFrame | null>(null);
  const currentTargets = ref<TrackTarget[]>([]);
  const telemetryIndex = ref<Map<number, TelemetryFrame>>(new Map());
  const lastTelemetry = ref<TelemetryFrame | null>(null);
  let videoFrameCallbackId: number | null = null;

  watch(telemetryData, (data) => {
    const map = new Map<number, TelemetryFrame>();
    data.forEach(item => map.set(item.frameId, item));
    telemetryIndex.value = map;
  }, { deep: true, immediate: true });

  // 核心同步函数：由 requestVideoFrameCallback 驱动
  const onVideoFrameUpdate = (_now: number, metadata: VideoFrameCallbackMetadata) => {
    videoFrameCallbackId = null;
    // 暂停检测时不更新目标数据，但仍继续递归监听（保持帧号同步）
    const isPaused = pausedRef?.value ?? false;

    const exposed = videoComponentRef.value?.videoElement as any;
    const videoEl: HTMLVideoElement | null = exposed?.value ?? exposed ?? null;

    // 根据视频播放时间精确计算当前帧号
    const fps = fpsRef.value || 30;
    const frameId = Math.floor(metadata.mediaTime * fps);
    currentFrameId.value = frameId;

    if (videoEl && !videoEl.paused && !videoEl.ended) {
      scheduleNextVideoFrame(videoEl);
    }

    if (isPaused) return; // 暂停时只更新帧号，不更新遥测和目标数据

    // --- 数据检索闭环 ---
    // 无论是实时推来的(存入ref了)还是历史API拉取的，都从这里找
    const telemetry = telemetryIndex.value.get(frameId) || lastTelemetry.value;
    currentTelemetry.value = telemetry || null;
    if (telemetry) {
      lastTelemetry.value = telemetry;
    }
    currentTargets.value = trackingData.value[frameId] || [];
  };

  // 暂停时停止帧同步回调，恢复时重新启动
  watch(() => pausedRef?.value, (paused) => {
    if (paused) {
      // 不再递归注册，回调自然停止
    }
  });

  const scheduleNextVideoFrame = (videoEl: HTMLVideoElement) => {
    if (!('requestVideoFrameCallback' in videoEl) || videoFrameCallbackId !== null) return;
    videoFrameCallbackId = videoEl.requestVideoFrameCallback(onVideoFrameUpdate);
  };

  const startSync = () => {
    const exposed = videoComponentRef.value?.videoElement as any;
    const videoEl: HTMLVideoElement | null = exposed?.value ?? exposed ?? null;
    if (videoEl) {
      scheduleNextVideoFrame(videoEl);
    }
  };

  return {
    currentFrameId,
    currentTelemetry,
    currentTargets,
    startSync
  };
}
