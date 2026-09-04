<script setup lang="ts">
import { computed, ref } from 'vue'
import { Pause, Play, CheckCircle2, Crosshair, FileOutput, Clock } from 'lucide-vue-next'

const props = defineProps<{
  isPaused: boolean
  progress: number
  routeName: string
  waypoints: number
  currentWaypoint: number
  remainingSec: number
  statusText: string
}>()

const emit = defineEmits<{
  (event: 'toggle-pause'): void
  (event: 'generate-report'): void
}>()

// 视点优化引擎的独立状态 (默认关闭)
const isOptActive = ref(false)

const toggleOpt = () => {
  isOptActive.value = !isOptActive.value
}

const progressPercent = computed(() => Math.min(100, Math.max(0, props.progress * 100)))

const formatTime = (seconds: number) => {
  const safe = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safe / 60)
  const remain = safe % 60
  return `${String(minutes).padStart(2, '0')}:${String(remain).padStart(2, '0')}`
}
</script>

<template>
  <div class="w-full h-full flex items-center justify-between bg-white px-4">

    <div class="flex items-center gap-3 shrink-0 mr-4">
      
      <button 
        @click="emit('toggle-pause')"
        class="w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 shadow-sm active:scale-90"
        :class="props.isPaused ? 'bg-amber-50 text-amber-500 hover:bg-amber-100' : 'bg-rose-50 text-rose-500 hover:bg-rose-100'"
      >
        <Play v-if="props.isPaused" :size="16" fill="currentColor" class="translate-x-[1px]" />
        <Pause v-else :size="16" fill="currentColor" />
      </button>
      
      <button 
        @click="toggleOpt"
        class="h-9 px-3 rounded-xl border flex items-center gap-1.5 transition-all relative group shadow-sm active:scale-95"
        :class="isOptActive 
          ? 'bg-emerald-50 border-emerald-100 text-emerald-600 hover:bg-emerald-100' 
          : 'bg-slate-50 border-slate-200 text-slate-500 hover:bg-slate-100'"
      >
        <Crosshair 
          :size="16" 
          class="transition-transform duration-500" 
          :class="isOptActive ? 'rotate-90 text-emerald-500' : 'group-hover:rotate-45'" 
        />
        <span class="text-xs font-bold">视点优化</span>
        <span 
          class="w-1.5 h-1.5 rounded-full ml-1 transition-colors" 
          :class="isOptActive ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'"
        ></span>
      </button>

    </div>

    <div class="flex-1 flex flex-col justify-center min-w-0 px-4 transition-opacity duration-300" :class="props.isPaused ? 'opacity-80' : 'opacity-100'">
      <div class="flex justify-between items-end mb-2">
        <span class="text-base font-bold text-slate-800 truncate">{{ props.routeName || '未选择航线' }}</span>
        
        <div class="text-xs text-slate-500 font-mono flex items-center gap-3 tracking-wide">
          <span>
            航点: <span class="text-slate-700 font-bold">{{ String(props.currentWaypoint).padStart(2, '0') }}/{{ String(props.waypoints).padStart(2, '0') }}</span>
          </span>
          <span class="text-slate-200">|</span>
          <span v-if="!props.isPaused">剩余: <span class="text-slate-700 font-bold">{{ formatTime(props.remainingSec) }}</span></span>
          <span v-else class="text-amber-500 font-bold animate-pulse">航线已载入，等待起飞指令...</span>
        </div>
      </div>
      
      <div class="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden">
        <div class="h-full rounded-full transition-all duration-500 relative" 
             :class="props.isPaused ? 'bg-amber-400' : 'bg-rose-500'" 
             :style="{ width: `${progressPercent}%` }">
          <div v-if="!props.isPaused" class="absolute top-0 right-0 bottom-0 w-10 bg-gradient-to-r from-transparent to-white/30 rounded-full"></div>
        </div>
      </div>
    </div>

    <div class="flex items-center shrink-0 ml-4">
      
      <div class="flex flex-col items-end justify-center px-4 border-l border-slate-100 transition-colors duration-300">
        <span class="text-xl font-black tracking-tighter leading-none mb-1" 
              :class="props.isPaused ? 'text-amber-500' : 'text-rose-600'">
          {{ progressPercent.toFixed(1) }}%
        </span>
        <div class="flex items-center gap-1.5 mt-1">
          <Clock v-if="props.isPaused" :size="12" class="text-amber-500" />
          <CheckCircle2 v-else :size="12" class="text-emerald-500" />
          
          <div class="flex items-center gap-1 text-xs font-black leading-none uppercase tracking-wider" 
               :class="props.isPaused ? 'text-amber-500' : 'text-slate-400'">
            <span>STATUS:</span>
            <span :class="props.isPaused ? 'text-amber-500' : 'text-slate-600'">
              {{ props.statusText }}
            </span>
          </div>
        </div>
      </div>

      <button
        class="h-9 px-4 ml-2 rounded-xl bg-gradient-to-r from-rose-500 to-rose-600 text-white flex items-center gap-1.5 hover:from-rose-600 hover:to-rose-700 shadow-md shadow-rose-500/20 transition-all active:scale-95 group"
        @click="emit('generate-report')"
      >
        <FileOutput :size="16" class="group-hover:-translate-y-0.5 transition-transform" />
        <span class="text-xs font-bold">生成报告</span>
      </button>

    </div>

  </div>
</template>
