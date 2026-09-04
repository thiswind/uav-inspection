<template>
  <div class="bg-white/70 backdrop-blur-sm border border-cyan-100 rounded-xl p-5 shadow-sm flex flex-col items-center justify-center relative overflow-hidden group">
    <!-- 科技感背景光晕 -->
    <div class="absolute -top-10 -right-10 w-24 h-24 bg-sky-200 rounded-full blur-3xl opacity-50 group-hover:opacity-80 transition-opacity"></div>
    <div class="absolute -bottom-10 -left-10 w-20 h-20 bg-cyan-200 rounded-full blur-2xl opacity-40 group-hover:opacity-70 transition-opacity"></div>

    <h2 class="text-slate-500 text-sm font-medium mb-1 z-10">{{ title }}</h2>
    
    <div class="flex items-baseline gap-1 z-10">
      <!-- 数字跳动动画区 -->
      <div
        class="text-5xl font-bold font-mono tracking-tight"
        :class="valueClass"
      >
        {{ animatedValue }}
      </div>
      <span class="text-slate-400 text-sm font-medium">{{ unit }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';

const props = withDefaults(defineProps<{
  title: string;
  value: number;
  unit?: string;
  alertLevel?: 'yellow' | 'orange' | 'red' | null;
  trend?: number; // 变化趋势，正数上升，负数下降
}>(), {
  unit: '人',
  alertLevel: null,
  trend: 0
});

const valueClass = computed(() => {
  switch (props.alertLevel) {
    case 'red':    return 'text-red-500    drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]';
    case 'orange': return 'text-orange-500 drop-shadow-[0_0_8px_rgba(249,115,22,0.5)]';
    case 'yellow': return 'text-amber-500  drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]';
    default:       return 'text-sky-600    drop-shadow-[0_0_8px_rgba(14,165,233,0.3)]';
  }
});

// 简单的数字缓动动画 (从旧值滚动到新值)
const animatedValue = ref(props.value);

watch(() => props.value, (newVal, oldVal) => {
  if (newVal === oldVal) return;
  const duration = 500; // 动画时长 500ms
  const start = performance.now();
  
  const step = (timestamp: number) => {
    const progress = Math.min((timestamp - start) / duration, 1);
    // 使用 easeOutQuart 缓动函数
    const easeProgress = 1 - Math.pow(1 - progress, 4); 
    animatedValue.value = Math.floor(oldVal + (newVal - oldVal) * easeProgress);
    
    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      animatedValue.value = newVal;
    }
  };
  requestAnimationFrame(step);
});
</script>