<template>
  <div
    class="w-full h-10 bg-slate-900/90 backdrop-blur-sm flex items-center px-4 relative group cursor-pointer select-none"
    @mousedown="handleMouseDown"
    @mousemove="handleHover"
    @mouseleave="handleLeave"
  >
    <div class="w-full relative flex items-center h-full">

      <div ref="trackRef" class="w-full bg-slate-700/50 rounded-full relative group-hover:h-1.5 h-[2px] overflow-hidden">
        <div
          class="absolute top-0 left-0 h-full bg-gradient-to-r from-sky-500 to-cyan-300 shadow-[0_0_8px_rgba(6,182,212,0.8)] pointer-events-none"
          :style="{ width: `${progressPercent}%` }"
        ></div>
      </div>

      <div
        v-if="hoverRatio !== null"
        class="absolute top-1/2 -translate-y-1/2 w-0.5 h-4 bg-white/70 pointer-events-none shadow-[0_0_5px_rgba(255,255,255,0.5)] z-20"
        :style="{ left: `${hoverRatio * 100}%` }"
      ></div>

      <div class="absolute top-1/2 left-0 w-full h-0 z-10 pointer-events-none">
        <div
          v-for="alert in alerts"
          :key="alert.id"
          class="absolute top-1/2 -translate-y-1/2 rounded-full cursor-pointer pointer-events-auto transition-all duration-300 border border-slate-900"
          :class="[
            'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]',
            'w-1.5 h-1.5 group-hover:w-2.5 group-hover:h-2.5 hover:!scale-[1.8] hover:bg-red-400 hover:z-30'
          ]"
          :style="{ left: `${getAlertLeft(alert)}%` }"
          :title="`${alert.timestamp} | 告警: ${alert.count}人`"
          @mouseenter="handleAlertHover(alert)"
          @mouseleave="handleAlertLeave"
          @click.stop="emit('seek-to-alert', alert)"
        ></div>
      </div>

      <div
        v-if="hoverAlert"
        class="absolute -top-[110px] z-30 w-48 bg-slate-900/95 border border-slate-700 rounded-lg shadow-xl p-2 text-xs text-slate-100"
        :style="{ left: `calc(${hoverLeft}% - 96px)` }"
      >
        <div class="flex gap-2">
          <div class="w-16 h-12 bg-slate-800 rounded overflow-hidden shrink-0">
            <img v-if="hoverAlert.snapshotUrl" :src="hoverAlert.snapshotUrl" class="w-full h-full object-cover" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="font-semibold truncate">{{ hoverAlert.timestamp }}</div>
            <div class="text-slate-300 mt-1">人数: {{ hoverAlert.count }} / {{ hoverAlert.threshold }}</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { AlertRecord } from '../../../types/patrol';

const props = defineProps<{
  currentFrame: number;
  totalFrames: number;
  alerts: AlertRecord[];
}>();

const emit = defineEmits(['seek', 'seek-to-alert']);
const trackRef = ref<HTMLElement | null>(null);
const hoverRatio = ref<number | null>(null);
const hoverAlert = ref<AlertRecord | null>(null);
const hoverLeft = ref(0);
const isDragging = ref(false);

const progressPercent = computed(() => {
  if (props.totalFrames === 0) return 0;
  return Math.min(100, Math.max(0, (props.currentFrame / props.totalFrames) * 100));
});

const getRatioFromX = (clientX: number) => {
  if (!trackRef.value) return 0;
  const rect = trackRef.value.getBoundingClientRect();
  const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
  return x / rect.width;
};

const handleHover = (e: MouseEvent) => {
  hoverRatio.value = getRatioFromX(e.clientX);
};

const handleLeave = () => {
  if (!isDragging.value) {
    hoverRatio.value = null;
  }
  hoverAlert.value = null;
};

const handleMouseDown = (e: MouseEvent) => {
  e.preventDefault();
  isDragging.value = true;
  const ratio = getRatioFromX(e.clientX);
  const targetFrame = Math.floor(ratio * props.totalFrames);
  emit('seek', targetFrame);
};

const handleMouseMove = (e: MouseEvent) => {
  if (isDragging.value) {
    hoverRatio.value = getRatioFromX(e.clientX);
    const ratio = getRatioFromX(e.clientX);
    const targetFrame = Math.floor(ratio * props.totalFrames);
    emit('seek', targetFrame);
  }
};

const handleMouseUp = () => {
  isDragging.value = false;
};

const handleAlertHover = (alert: AlertRecord) => {
  hoverAlert.value = alert;
  hoverLeft.value = getAlertLeft(alert);
};

const handleAlertLeave = () => {
  hoverAlert.value = null;
};

const getAlertLeft = (alert: AlertRecord) => {
  if (props.totalFrames <= 0) return 0;
  return (alert.frameId / props.totalFrames) * 100;
};

onMounted(() => {
  window.addEventListener('mousemove', handleMouseMove);
  window.addEventListener('mouseup', handleMouseUp);
});

onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouseMove);
  window.removeEventListener('mouseup', handleMouseUp);
});
</script>
