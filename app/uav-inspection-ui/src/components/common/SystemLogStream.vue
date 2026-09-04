<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { Terminal } from 'lucide-vue-next'

// 模拟日志数据 (保留了你截图中的真实业务语义)
const logs = ref([
  { id: 1, time: '10:00:01', level: 'INFO', tag: '系统初始化', message: 'FastAPI 边缘网关连接成功。', color: 'text-rose-600' },
  { id: 2, time: '10:00:05', level: 'SUCCESS', tag: '模型加载', message: 'YOLO 目标检测模型权重加载完毕。', color: 'text-emerald-600' },
  { id: 3, time: '12:32:49', level: 'INFO', tag: '空间计算', message: '正在解析 WGS84 坐标系数据...', color: 'text-rose-600' },
  { id: 4, time: '12:32:52', level: 'WARNING', tag: '视点决策', message: '目标区域叶片遮挡度 > 30%，触发 Actor-Critic 决策网络。', color: 'text-amber-500' }
])

const logContainer = ref<HTMLElement | null>(null)

// 自动滚动到最新日志的辅助函数
const scrollToBottom = async () => {
  await nextTick()
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

onMounted(() => {
  scrollToBottom()
  
  // 模拟系统持续运行，偶尔推入新日志 (可选，让页面有存活感)
  setInterval(() => {
    if (Math.random() > 0.8) {
      const now = new Date()
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
      
      logs.value.push({
        id: Date.now(),
        time: timeStr,
        level: 'INFO',
        tag: '强化学习',
        message: '状态空间计算中：当前云台俯仰角 -45°...',
        color: 'text-rose-600'
      })
      scrollToBottom()
    }
  }, 3000)
})
</script>

<template>
  <div class="h-full flex flex-col bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
    
    <div class="px-4 py-2.5 bg-slate-50 border-b border-slate-100 flex items-center gap-2 shrink-0">
      <Terminal :size="16" class="text-slate-500" />
      <span class="text-sm font-bold text-slate-700 tracking-wide">系统日志</span>
    </div>

    <div ref="logContainer" class="flex-1 overflow-y-auto p-4 bg-white font-mono text-xs space-y-1.5 custom-scrollbar scroll-smooth">
      
      <div 
        v-for="log in logs" 
        :key="log.id" 
        class="flex items-start gap-3 hover:bg-slate-50 px-2 py-1.5 rounded transition-colors group"
      >
        <span class="text-slate-400 shrink-0">[{{ log.time }}]</span>
        
        <span class="font-bold shrink-0 w-[60px]" :class="log.color">{{ log.level }}</span>
        
        <span class="text-slate-500 shrink-0">[{{ log.tag }}]</span>
        
        <span class="text-slate-700 break-all group-hover:text-slate-900 transition-colors">{{ log.message }}</span>
      </div>
      
    </div>
  </div>
</template>

<style scoped>

</style>
