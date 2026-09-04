<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-3 backdrop-blur-sm sm:p-4">
    <div class="flex max-h-[calc(100dvh-24px)] w-full max-w-[420px] flex-col overflow-y-auto rounded-xl border border-cyan-100 bg-white shadow-2xl">
      <div class="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-gradient-to-r from-sky-50 to-white">
        <h3 class="text-lg font-bold text-slate-800">导出巡检报告</h3>
        <button @click="close" class="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
      </div>

      <div class="flex flex-col gap-4 p-4 sm:p-6">
        <label class="flex items-center gap-3 text-sm text-slate-700">
          <input type="checkbox" v-model="includeMinute" class="accent-cyan-500 w-4 h-4" />
          人流统计（分钟级）
        </label>
        <label class="flex items-center gap-3 text-sm text-slate-700">
          <input type="checkbox" v-model="includeAlerts" class="accent-cyan-500 w-4 h-4" />
          告警信息记录
        </label>
        <div v-if="!canConfirm" class="text-xs text-red-500">
          至少选择一项导出内容
        </div>
      </div>

      <div class="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-3">
        <button @click="close" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-200 rounded-md transition-colors">取消</button>
        <button
          @click="confirm"
          :disabled="!canConfirm"
          class="px-4 py-2 text-sm text-white bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-300 rounded-md transition-colors"
        >
          导出
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits(['update:visible', 'confirm']);

const includeMinute = ref(true);
const includeAlerts = ref(true);

const canConfirm = computed(() => includeMinute.value || includeAlerts.value);

const close = () => {
  emit('update:visible', false);
};

const confirm = () => {
  if (!canConfirm.value) return;
  emit('confirm', { includeMinute: includeMinute.value, includeAlerts: includeAlerts.value });
  close();
};

watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    includeMinute.value = true;
    includeAlerts.value = true;
  }
});
</script>
