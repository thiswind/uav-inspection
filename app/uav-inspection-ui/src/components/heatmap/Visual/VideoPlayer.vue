<template>
  <DetectionVideoFrame
    class="h-full min-h-[300px] w-full"
    label="YOLO 客流实时检测"
    :status="isPlaying ? '实时检测中' : '等待启动'"
    :playing="isPlaying"
    :disabled="!videoUrl"
    :current-time="currentTime"
    :duration="duration"
    :empty="!videoUrl"
    empty-text="请先选择一个客流检测任务。"
    @toggle="handlePlayButton"
    @replay="handleReplay"
    @seek="handleSeek"
  >
    <video
      ref="videoRef"
      class="pointer-events-none absolute inset-0 z-0 h-full w-full object-contain"
      :src="videoUrl || undefined"
      playsinline
      preload="metadata"
      @play="handlePlay"
      @pause="handlePause"
      @timeupdate="handleTimeUpdate"
      @loadedmetadata="handleLoadedMetadata"
      @error="handleError"
    ></video>

    <canvas
      ref="canvasRef"
      class="pointer-events-none absolute inset-0 z-[1] h-full w-full"
    ></canvas>
  </DetectionVideoFrame>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import type { TrackTarget } from '../../../types/patrol';
import DetectionVideoFrame from '../../common/DetectionVideoFrame.vue';

const props = defineProps<{
  videoUrl: string;
  targets?: TrackTarget[];
  currentStreamData?: any;
  detectionPaused?: boolean;
}>();

const emit = defineEmits(['play', 'pause', 'error', 'loadedmetadata']);

const isPlaying = ref(false);
const currentTime = ref(0);
const duration = ref(0);
const videoRef = ref<HTMLVideoElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);
let resizeObserver: ResizeObserver | null = null;
let frozenSnapshot: TrackTarget[] | null = null;
let rafId: number | null = null;

const handlePlayButton = async () => {
  if (!videoRef.value) return;
  if (isPlaying.value) {
    videoRef.value.pause();
  } else {
    try {
      await videoRef.value.play();
    } catch (error) {
      emit('error', error);
    }
  }
};

const handlePlay = () => {
  isPlaying.value = true;
  emit('play');
};

const handleReplay = async () => {
  if (!videoRef.value) return;
  videoRef.value.currentTime = 0;
  currentTime.value = 0;
  try {
    await videoRef.value.play();
  } catch (error) {
    emit('error', error);
  }
};

const handleSeek = (seconds: number) => {
  if (!videoRef.value) return;
  videoRef.value.currentTime = seconds;
  currentTime.value = seconds;
};

const handleTimeUpdate = () => {
  currentTime.value = videoRef.value?.currentTime || 0;
};

const handlePause = () => {
  isPlaying.value = false;
  emit('pause');
};

const handleLoadedMetadata = () => {
  duration.value = videoRef.value?.duration || 0;
  emit('loadedmetadata', {
    duration: videoRef.value?.duration || 0
  });
  nextTick(() => {
    syncCanvasSize();
    drawTargets();
  });
};

const handleError = () => {
  if (!props.videoUrl) return; // An empty task list is not a video/server failure.
  console.error("视频加载失败或后端未启动");
  isPlaying.value = false;
  emit('error');
};

watch(() => props.videoUrl, () => {
  if (videoRef.value) {
    videoRef.value.pause();
    videoRef.value.currentTime = 0;
  }
  isPlaying.value = false;
  currentTime.value = 0;
  duration.value = 0;
  nextTick(() => {
    syncCanvasSize();
    drawTargets();
  });
});

// 用 rAF 节流 targets 重绘，避免高频更新
watch(() => props.targets, () => {
  if (props.detectionPaused) return;
  if (rafId !== null) return; // 已有待绘制帧，跳过
  rafId = requestAnimationFrame(() => {
    rafId = null;
    drawTargets();
  });
}, { deep: true });

watch(() => props.detectionPaused, (paused) => {
  if (paused) {
    frozenSnapshot = props.targets ? [...props.targets] : null;
    drawTargets();
  } else {
    frozenSnapshot = null;
    drawTargets();
  }
});

const syncCanvasSize = () => {
  if (!videoRef.value || !canvasRef.value) return;
  const rect = videoRef.value.getBoundingClientRect();
  canvasRef.value.width = rect.width;
  canvasRef.value.height = rect.height;
};

const drawTargets = () => {
  if (!canvasRef.value || !videoRef.value) return;
  const ctx = canvasRef.value.getContext('2d');
  if (!ctx) return;

  const targets = frozenSnapshot || props.targets || [];
  ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height);
  if (!targets.length) return;

  const videoWidth = videoRef.value.videoWidth || 0;
  const videoHeight = videoRef.value.videoHeight || 0;
  if (!videoWidth || !videoHeight) return;

  const canvasW = canvasRef.value.width;
  const canvasH = canvasRef.value.height;
  const videoAspect = videoWidth / videoHeight;
  const canvasAspect = canvasW / canvasH;

  let drawW = canvasW;
  let drawH = canvasH;
  let offsetX = 0;
  let offsetY = 0;

  if (canvasAspect > videoAspect) {
    drawH = canvasH;
    drawW = canvasH * videoAspect;
    offsetX = (canvasW - drawW) / 2;
  } else {
    drawW = canvasW;
    drawH = canvasW / videoAspect;
    offsetY = (canvasH - drawH) / 2;
  }

  const scaleX = drawW / videoWidth;
  const scaleY = drawH / videoHeight;

  ctx.strokeStyle = 'rgba(6, 182, 212, 0.9)';
  ctx.lineWidth = 2;
  ctx.font = '12px monospace';
  ctx.textBaseline = 'top';

  targets.forEach(target => {
    const [x1, y1, x2, y2] = target.bbox;
    const x = x1 * scaleX + offsetX;
    const y = y1 * scaleY + offsetY;
    const w = (x2 - x1) * scaleX;
    const h = (y2 - y1) * scaleY;
    ctx.strokeRect(x, y, w, h);

    const confidence = target.confidence ?? null;
    const confText = confidence !== null
      ? `${confidence <= 1 ? Math.round(confidence * 100) : Math.round(confidence)}%`
      : '';
    const trackLabel = target.trackId !== undefined ? String(target.trackId) : '-';
    const label = `ID ${trackLabel}${confText ? ` | ${confText}` : ''}`;
    const padding = 4;
    const textWidth = ctx.measureText(label).width;
    ctx.fillStyle = 'rgba(15, 23, 42, 0.7)';
    ctx.fillRect(x, Math.max(0, y - 18), textWidth + padding * 2, 16);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillText(label, x + padding, Math.max(0, y - 16));
  });
};

onMounted(() => {
  if (videoRef.value) {
    resizeObserver = new ResizeObserver(() => {
      syncCanvasSize();
      drawTargets();
    });
    resizeObserver.observe(videoRef.value);
  }
});

onUnmounted(() => {
  if (resizeObserver && videoRef.value) {
    resizeObserver.unobserve(videoRef.value);
  }
  resizeObserver = null;
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
});

defineExpose({
  isPlaying,
  videoElement: videoRef,
  seekTo: (seconds: number) => {
    if (videoRef.value) {
      videoRef.value.currentTime = Math.max(0, seconds);
    }
  }
});
</script>

<style scoped>
video {
  transform: translateZ(0);
}
</style>
