<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-vue-next'

type NoticeTone = 'info' | 'success' | 'warning' | 'error'

const props = withDefaults(defineProps<{
  message?: string
  tone?: NoticeTone
  duration?: number
  trigger?: string | number
  centered?: boolean
}>(), {
  message: '',
  tone: 'info',
  duration: 3000,
  trigger: 0,
  centered: false,
})

const visible = ref(false)
let hideTimer: number | null = null

const noticeClass = computed(() => ({
  'floating-notice--success': props.tone === 'success',
  'floating-notice--warning': props.tone === 'warning',
  'floating-notice--error': props.tone === 'error',
  'floating-notice--info': props.tone === 'info',
}))

function dismiss() {
  visible.value = false
  if (hideTimer !== null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }
}

function present() {
  if (!props.message) {
    dismiss()
    return
  }
  if (hideTimer !== null) window.clearTimeout(hideTimer)
  visible.value = true
  hideTimer = window.setTimeout(dismiss, props.duration)
}

watch(() => [props.message, props.trigger], present, { immediate: true })
onBeforeUnmount(dismiss)
</script>

<template>
  <Teleport to="body">
    <Transition name="floating-notice">
      <div
        v-if="visible"
        class="floating-notice"
        :class="[noticeClass, { 'floating-notice--centered': centered }]"
        role="status"
        aria-live="polite"
        data-testid="floating-notice"
      >
        <CheckCircle2 v-if="tone === 'success'" :size="19" />
        <AlertTriangle v-else-if="tone === 'warning' || tone === 'error'" :size="19" />
        <Info v-else :size="19" />
        <span class="floating-notice__message">{{ message }}</span>
        <button type="button" class="floating-notice__close" title="关闭提示" aria-label="关闭提示" @click="dismiss">
          <X :size="16" />
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.floating-notice {
  position: fixed;
  z-index: 1000;
  top: 20px;
  right: 22px;
  display: grid;
  width: min(380px, calc(100vw - 32px));
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: start;
  gap: 10px;
  border: 1px solid;
  border-radius: 8px;
  padding: 13px 12px 13px 14px;
  box-shadow: 0 18px 45px -18px rgb(15 23 42 / 0.42);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  backdrop-filter: blur(18px);
}

.floating-notice--centered {
  right: auto;
  left: 50%;
  transform: translateX(-50%);
}

.floating-notice--info {
  border-color: #bae6fd;
  background: rgb(240 249 255 / 0.96);
  color: #0369a1;
}

.floating-notice--success {
  border-color: #a7f3d0;
  background: rgb(236 253 245 / 0.96);
  color: #047857;
}

.floating-notice--warning {
  border-color: #fde68a;
  background: rgb(255 251 235 / 0.96);
  color: #a16207;
}

.floating-notice--error {
  border-color: #fecdd3;
  background: rgb(255 241 242 / 0.96);
  color: #be123c;
}

.floating-notice__message {
  overflow-wrap: anywhere;
}

.floating-notice__close {
  display: inline-flex;
  width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: currentColor;
  cursor: pointer;
  opacity: 0.72;
}

.floating-notice__close:hover {
  background: rgb(255 255 255 / 0.7);
  opacity: 1;
}

.floating-notice-enter-active,
.floating-notice-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.floating-notice-enter-from,
.floating-notice-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.floating-notice--centered.floating-notice-enter-from,
.floating-notice--centered.floating-notice-leave-to {
  transform: translate(-50%, -8px);
}

@media (max-width: 620px) {
  .floating-notice {
    top: auto;
    right: 16px;
    bottom: 12px;
  }

  .floating-notice--centered {
    top: 16px;
    right: auto;
    bottom: auto;
    left: 50%;
  }
}
</style>
