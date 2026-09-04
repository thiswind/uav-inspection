<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Maximize2, Crosshair, Map, Navigation } from 'lucide-vue-next'
import { pestApi } from '../../api1/pest'
import DetectionVideoFrame from '../common/DetectionVideoFrame.vue'

const props = defineProps<{
  isPaused: boolean
  routeId?: string | null
}>()

const emit = defineEmits<{
  togglePause: []
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const streamKey = ref(Date.now())
const videoUrl = computed(() => {
  const params = new URLSearchParams()
  if (props.routeId) params.set('route_id', props.routeId)
  params.set('ts', String(streamKey.value))
  return `${pestApi.videoUrl}?${params.toString()}`
})

// 模拟 YOLO 识别框数据
const detectedObjects = ref([
  { id: 1, label: '疑似茶尺蠖', confidence: 98, x: 30, y: 40, width: 15, height: 20, color: 'border-rose-500', text: 'text-rose-500' },
  { id: 2, label: '叶片病斑', confidence: 85, x: 65, y: 60, width: 12, height: 15, color: 'border-amber-500', text: 'text-amber-500' }
])

const isStreamReady = ref(false)
const streamError = ref<string | null>(null)
const currentTime = ref(0)
const duration = ref(0)

const handleLoaded = () => {
  isStreamReady.value = true
  duration.value = Number.isFinite(videoRef.value?.duration) ? videoRef.value?.duration || 0 : 0
  if (!props.isPaused) {
    syncPlayback(false)
  }
}

const handleTimeUpdate = () => {
  currentTime.value = videoRef.value?.currentTime || 0
}

const replayVideo = async () => {
  if (!videoRef.value) return
  videoRef.value.currentTime = 0
  currentTime.value = 0
  if (props.isPaused) emit('togglePause')
  else await syncPlayback(false)
}

const seekVideo = (seconds: number) => {
  if (!videoRef.value) return
  videoRef.value.currentTime = seconds
  currentTime.value = seconds
}

const syncPlayback = async (paused: boolean) => {
  const player = videoRef.value
  if (!player) return
  if (paused) {
    player.pause()
    return
  }
  try {
    await player.play()
  } catch (error) {
    console.warn('Video play failed', error)
  }
}

watch(
  () => props.isPaused,
  (paused) => {
    syncPlayback(paused)
  }
)

watch(
  () => props.routeId,
  () => {
    streamKey.value = Date.now()
    isStreamReady.value = false
    streamError.value = null
  }
)

onMounted(() => {
  if (!props.isPaused) {
    syncPlayback(false)
  }
})
</script>

<template>
  <DetectionVideoFrame
    class="group/video h-full w-full"
    label="YOLO 病虫害实时检测"
    :status="streamError ? '暂无可播放视频' : props.isPaused ? '已暂停' : '实时检测中'"
    :playing="!props.isPaused"
    :disabled="!isStreamReady || Boolean(streamError)"
    :current-time="currentTime"
    :duration="duration"
    @toggle="emit('togglePause')"
    @replay="replayVideo"
    @seek="seekVideo"
  >

    <video
      ref="videoRef"
      class="absolute inset-0 w-full h-full object-cover"
      :src="videoUrl"
      muted
      loop
      playsinline
      @loadeddata="handleLoaded"
      @timeupdate="handleTimeUpdate"
      @error="streamError = '暂无可播放视频。请安装可选数据包；若已安装，请检查视频文件和服务连接。'"
    ></video>

    <div
      v-if="!isStreamReady && !streamError"
      class="absolute inset-0 flex items-center justify-center text-slate-400 text-xs font-mono"
    >
      正在加载视频流...
    </div>

    <div
      v-if="streamError"
      class="absolute inset-0 flex items-center justify-center text-rose-200 text-xs font-mono bg-black/40"
    >
      {{ streamError }}
    </div>

    <div
      v-if="props.isPaused"
      class="absolute inset-0 flex items-center justify-center text-white text-xs font-mono bg-black/20"
    >
      暂停中
    </div>
    
    <div class="absolute inset-0 opacity-20 pointer-events-none" style="background-image: repeating-linear-gradient(0deg, transparent, transparent 2px, #1e293b 2px, #1e293b 4px); background-size: 100% 4px;"></div>
    
    <Crosshair :size="40" class="text-emerald-500/30 absolute z-0" stroke-width="1" />

    <div v-for="obj in (isStreamReady && !streamError ? detectedObjects : [])" :key="obj.id" 
         class="absolute border-2 bg-black/10 backdrop-blur-sm transition-all duration-300"
         :class="obj.color"
         :style="{ left: obj.x + '%', top: obj.y + '%', width: obj.width + '%', height: obj.height + '%' }">
      <div class="absolute -top-6 left-[-2px] bg-black/80 px-2 py-1 text-[10px] font-bold border" :class="[obj.color, obj.text]">
        {{ obj.label }} {{ obj.confidence }}%
      </div>
      <div class="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2" :class="obj.color"></div>
      <div class="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2" :class="obj.color"></div>
    </div>

    <div class="absolute bottom-20 right-6 w-56 h-36 bg-[#020617]/90 backdrop-blur-md rounded-xl border border-slate-700 shadow-2xl overflow-hidden group">
      
      <div class="absolute top-0 left-0 w-full px-2 py-1.5 bg-slate-800/80 flex items-center justify-between z-10 border-b border-slate-700">
        <div class="flex items-center gap-1.5">
          <Map :size="10" class="text-rose-400" />
          <span class="text-[9px] text-slate-200 font-bold tracking-widest">实时航迹预估</span>
        </div>
        <Maximize2 :size="10" class="text-slate-400 hover:text-white cursor-pointer" />
      </div>
      
      <div class="w-full h-full pip-map-grid relative mt-6">
        
        <svg class="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <path d="M 10 90 Q 30 70 50 60 T 80 30" fill="none" stroke="rgba(59, 130, 246, 0.5)" stroke-width="2" stroke-dasharray="3 3" />
          <path d="M 80 30 L 90 20" fill="none" stroke="rgba(16, 185, 129, 0.8)" stroke-width="2" />
        </svg>
        
        <div class="absolute top-[90%] left-[10%] -translate-x-1/2 -translate-y-1/2 flex items-center justify-center">
          <div class="w-2 h-2 bg-amber-500 rounded-full"></div>
          <span class="absolute top-3 text-[8px] text-amber-500/80 font-mono scale-75">HOME</span>
        </div>

        <div class="absolute top-[20%] left-[90%] -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
          <div class="w-6 h-6 bg-emerald-500/30 rounded-full animate-ping absolute"></div>
          <Navigation :size="14" class="text-emerald-400 relative z-10 drop-shadow-[0_0_8px_rgba(16,185,129,0.8)] rotate-45" fill="currentColor" />
        </div>
      </div>
    </div>
    <div class="absolute bottom-20 left-6 flex flex-col gap-2 opacity-60 group-hover/video:opacity-100 transition-opacity">
      <div class="bg-black/50 backdrop-blur px-3 py-1.5 rounded-lg border border-slate-700 text-[10px] text-white flex items-center gap-2">
        <span class="text-slate-400">PITCH</span> <span class="font-mono text-emerald-400">-45°</span>
      </div>
      <div class="bg-black/50 backdrop-blur px-3 py-1.5 rounded-lg border border-slate-700 text-[10px] text-white flex items-center gap-2">
        <span class="text-slate-400">YAW</span> <span class="font-mono text-emerald-400">12°</span>
      </div>
    </div>

  </DetectionVideoFrame>
</template>

<style scoped>
/* 绘制画中画的科技感雷达网格底纹 */
.pip-map-grid {
  background-color: #020617;
  background-image: 
    linear-gradient(rgba(59, 130, 246, 0.15) 1px, transparent 1px),
    linear-gradient(90deg, rgba(59, 130, 246, 0.15) 1px, transparent 1px);
  background-size: 20px 20px;
  background-position: center center;
}
</style>
