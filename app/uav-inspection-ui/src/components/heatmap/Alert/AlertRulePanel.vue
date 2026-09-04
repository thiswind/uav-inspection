<template>
  <div class="bg-white/70 backdrop-blur-xl border border-white shadow-[0_8px_40px_-12px_rgba(14,165,233,0.15)] rounded-2xl p-4 flex flex-col gap-3">
    <!-- 标题 + 全局开关 -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2 text-slate-700 font-semibold text-sm">
        <svg class="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        预警规则
      </div>
      <!-- 状态指示灯 -->
      <div class="flex items-center gap-1.5">
        <span
          class="w-2.5 h-2.5 rounded-full animate-pulse"
          :class="statusDotClass"
        ></span>
        <span class="text-[10px] font-medium" :class="statusTextClass">{{ statusText }}</span>
      </div>
    </div>

    <!-- 规则列表 -->
    <div class="flex flex-col gap-2">
      <div
        v-for="(rule, idx) in rules"
        :key="idx"
        class="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 border border-slate-100 group hover:border-slate-200 transition-colors"
      >
        <div class="flex items-center gap-2">
          <span
            class="w-2 h-2 rounded-full shrink-0"
            :class="dotColorMap[rule.level]"
          ></span>
          <span class="text-xs text-slate-600">{{ rule.label }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs font-mono text-slate-500">≥</span>
          <input
            type="number"
            v-model.number="rule.value"
            min="1"
            class="w-14 text-xs font-mono text-center bg-white border border-slate-200 rounded-md px-1 py-0.5 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/30 transition-all"
            :disabled="!rule.enabled"
          />
          <span class="text-[10px] text-slate-400">人</span>
          <button
            @click="rule.enabled = !rule.enabled"
            class="w-7 h-4 rounded-full relative transition-colors shrink-0"
            :class="rule.enabled ? 'bg-cyan-500' : 'bg-slate-300'"
          >
            <span
              class="absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-transform"
              :class="rule.enabled ? 'left-[14px]' : 'left-0.5'"
            ></span>
          </button>
        </div>
      </div>
    </div>

    <!-- 当前人数提示 -->
    <div class="text-[10px] text-slate-400 text-center">
      当前人数: <span class="font-mono font-semibold text-slate-600">{{ currentCount }}</span> 人
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { AlertRule } from '../../../types/patrol';

const props = withDefaults(defineProps<{
  currentCount: number;
  alertLevel: 'yellow' | 'orange' | 'red' | null;
}>(), {
  currentCount: 0,
  alertLevel: null,
});

const rules = defineModel<AlertRule[]>('rules', { required: true });

const dotColorMap: Record<string, string> = {
  yellow: 'bg-amber-400',
  orange: 'bg-orange-500',
  red: 'bg-red-500',
};

const statusDotClass = computed(() => {
  switch (props.alertLevel) {
    case 'red': return 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]';
    case 'orange': return 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)]';
    case 'yellow': return 'bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.6)]';
    default: return 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]';
  }
});

const statusTextClass = computed(() => {
  switch (props.alertLevel) {
    case 'red': return 'text-red-500';
    case 'orange': return 'text-orange-500';
    case 'yellow': return 'text-amber-500';
    default: return 'text-emerald-500';
  }
});

const statusText = computed(() => {
  switch (props.alertLevel) {
    case 'red': return '危险';
    case 'orange': return '警告';
    case 'yellow': return '注意';
    default: return '正常';
  }
});
</script>
