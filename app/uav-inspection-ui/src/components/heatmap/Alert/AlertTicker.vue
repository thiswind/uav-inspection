<template>
  <div 
    ref="scrollContainer"
    class="flex-1 flex gap-3 overflow-x-auto pb-2 scroll-smooth snap-x"
    @mouseenter="pauseAutoScroll"
    @mouseleave="resumeAutoScroll"
  >
    <div 
      v-for="alert in alerts" 
      :key="alert.id"
      :id="`alert-${alert.id}`"
      class="snap-start shrink-0 w-64 bg-white border border-red-200 rounded-lg p-2 cursor-pointer hover:shadow-lg transition-all flex gap-3 relative overflow-hidden"
      @click="triggerLinkage(alert)"
    >
      <!-- 侧边警示条 -->
      <div class="absolute left-0 top-0 bottom-0 w-1 bg-red-500"></div>
      
      <div class="w-16 h-12 bg-slate-900 rounded shrink-0 overflow-hidden relative">
        <img :src="alert.snapshotUrl" class="w-full h-full object-cover opacity-80" />
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-xs text-red-600 font-bold truncate">
          <i class="icon-warning mr-1"></i>{{ alert.type === 'CROWD_DENSITY' ? '人群拥挤' : '区域入侵' }}
        </div>
        <div class="text-slate-600 text-[11px] mt-1 font-mono">{{ alert.timestamp }}</div>
        <div class="text-slate-400 text-[10px] mt-0.5">实测: {{ alert.count }}人 | 限: {{ alert.threshold }}人</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import type { AlertRecord } from '../../../types/patrol';

const props = defineProps<{ alerts: AlertRecord[] }>();
const emit = defineEmits(['linkage']);

const scrollContainer = ref<HTMLElement | null>(null);
let autoScrollTimer: number | null = null;

// 点击告警卡片触发联动 (视频跳转、地图中心移动)
const triggerLinkage = (alert: AlertRecord) => {
  emit('linkage', alert);
};

// 简单的自动向右滚动逻辑
const startAutoScroll = () => {
  autoScrollTimer = window.setInterval(() => {
    if (scrollContainer.value) {
      // 每次滚动一张卡片的宽度及 gap
      scrollContainer.value.scrollLeft += 268; 
    }
  }, 3000);
};

const pauseAutoScroll = () => {
  if (autoScrollTimer) clearInterval(autoScrollTimer);
};

const resumeAutoScroll = () => {
  startAutoScroll();
};

onMounted(() => {
  startAutoScroll();
});

onUnmounted(() => {
  pauseAutoScroll();
});

// 对外暴露滚动到特定告警的方法 (如视频播放到某时刻，联动底部告警高亮)
defineExpose({
  scrollToAlert: (id: string) => {
    const el = document.getElementById(`alert-${id}`);
    if (el && scrollContainer.value) {
      const containerLeft = scrollContainer.value.getBoundingClientRect().left;
      const elLeft = el.getBoundingClientRect().left;
      scrollContainer.value.scrollLeft += (elLeft - containerLeft);
    }
  }
});
</script>

<style scoped>
/* 隐藏原生滚动条，保持UI整洁 */
.overflow-x-auto::-webkit-scrollbar {
  display: none;
}
.overflow-x-auto {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>