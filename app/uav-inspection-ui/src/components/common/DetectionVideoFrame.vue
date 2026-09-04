<script setup lang="ts">
import { computed } from 'vue'
import { Pause, Play, RotateCcw } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  label?: string
  status?: string
  playing?: boolean
  disabled?: boolean
  currentTime?: number
  duration?: number
  showControls?: boolean
  showReplay?: boolean
  empty?: boolean
  emptyText?: string
}>(), {
  label: 'YOLO LIVE DETECTION',
  status: '等待启动',
  playing: false,
  disabled: false,
  currentTime: 0,
  duration: 0,
  showControls: true,
  showReplay: true,
  empty: false,
  emptyText: '请先选择一个视频检测任务。',
})

const emit = defineEmits<{
  toggle: []
  replay: []
  seek: [seconds: number]
}>()

const safeDuration = computed(() => Number.isFinite(props.duration) && props.duration > 0 ? props.duration : 0)
const safeCurrentTime = computed(() => Math.min(safeDuration.value, Math.max(0, props.currentTime || 0)))

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return '00:00'
  const minutes = Math.floor(seconds / 60)
  const remainder = Math.floor(seconds % 60)
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
}

function onSeek(event: Event) {
  emit('seek', Number((event.target as HTMLInputElement).value))
}
</script>

<template>
  <div class="inspection-video-frame">
    <slot />

    <div class="inspection-video-frame__hud">
      <span class="inspection-video-frame__badge">{{ label }}</span>
      <span class="inspection-video-frame__badge inspection-video-frame__status">
        <span class="inspection-video-frame__pulse" :class="playing ? 'bg-emerald-400' : 'bg-slate-400'"></span>
        {{ status }}
      </span>
    </div>

    <div v-if="empty" class="inspection-video-frame__empty">
      <Play :size="30" />
      <span>{{ emptyText }}</span>
    </div>

    <div v-if="showControls && !empty" class="inspection-video-frame__controls">
      <button
        type="button"
        class="inspection-video-frame__icon-button inspection-video-frame__play"
        :disabled="disabled"
        :title="playing ? '暂停视频' : '播放视频'"
        :aria-label="playing ? '暂停视频' : '播放视频'"
        @click="emit('toggle')"
      >
        <Pause v-if="playing" :size="19" fill="currentColor" />
        <Play v-else :size="19" fill="currentColor" />
      </button>

      <button
        v-if="showReplay"
        type="button"
        class="inspection-video-frame__icon-button"
        :disabled="disabled"
        title="重新播放"
        aria-label="重新播放"
        @click="emit('replay')"
      >
        <RotateCcw :size="18" />
      </button>

      <span class="inspection-video-frame__time">{{ formatTime(safeCurrentTime) }} / {{ formatTime(safeDuration) }}</span>
      <input
        class="inspection-video-frame__progress"
        type="range"
        min="0"
        :max="safeDuration || 1"
        step="0.01"
        :value="safeCurrentTime"
        :disabled="disabled || !safeDuration"
        aria-label="视频播放进度"
        @input="onSeek"
      />

      <div class="inspection-video-frame__actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.inspection-video-frame {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 260px;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid #0f172a;
  border-radius: 8px;
  background: #020617;
  box-shadow: 0 20px 70px -30px rgb(15 23 42 / 0.65);
}

.inspection-video-frame :deep(video),
.inspection-video-frame :deep(img) {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.inspection-video-frame__hud {
  pointer-events: none;
  position: absolute;
  z-index: 5;
  top: 0;
  right: 0;
  left: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 28px;
  background: linear-gradient(to bottom, rgb(2 6 23 / 0.82), transparent);
}

.inspection-video-frame__badge {
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 0.22);
  border-radius: 6px;
  background: rgb(15 23 42 / 0.62);
  padding: 5px 9px;
  color: #fff;
  font-size: 11px;
  font-weight: 650;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
  backdrop-filter: blur(10px);
}

.inspection-video-frame__status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.inspection-video-frame__pulse {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 999px;
}

.inspection-video-frame__empty {
  position: absolute;
  z-index: 4;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 12px;
  padding: 32px;
  color: #94a3b8;
  font-size: 14px;
  text-align: center;
}

.inspection-video-frame__controls {
  position: absolute;
  z-index: 7;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  min-height: 54px;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  background: rgb(2 6 23 / 0.8);
  backdrop-filter: blur(12px);
}

.inspection-video-frame__icon-button {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: none;
  align-items: center;
  justify-content: center;
  border: 1px solid rgb(255 255 255 / 0.18);
  border-radius: 7px;
  background: rgb(255 255 255 / 0.08);
  color: #fff;
  cursor: pointer;
  transition: background-color 150ms ease, border-color 150ms ease;
}

.inspection-video-frame__icon-button:hover:not(:disabled) {
  border-color: rgb(255 255 255 / 0.42);
  background: rgb(255 255 255 / 0.18);
}

.inspection-video-frame__icon-button:disabled {
  cursor: not-allowed;
  opacity: 0.38;
}

.inspection-video-frame__play {
  border-color: rgb(56 189 248 / 0.7);
  background: #0284c7;
}

.inspection-video-frame__time {
  width: 92px;
  flex: none;
  color: #cbd5e1;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  text-align: center;
}

.inspection-video-frame__progress {
  min-width: 70px;
  flex: 1;
  accent-color: #38bdf8;
  cursor: pointer;
}

.inspection-video-frame__progress:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.inspection-video-frame__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
}

.inspection-video-frame__actions :slotted(button),
.inspection-video-frame__actions :slotted(a) {
  display: inline-flex !important;
  min-height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 7px !important;
  white-space: nowrap;
}

@media (max-width: 620px) {
  .inspection-video-frame__hud {
    padding: 10px 10px 24px;
  }

  .inspection-video-frame__controls {
    gap: 7px;
    padding: 8px;
  }

  .inspection-video-frame__time {
    display: none;
  }
}
</style>
