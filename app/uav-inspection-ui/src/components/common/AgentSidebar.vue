<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { Bot, User, Send, ChevronRight } from 'lucide-vue-next'

const isCollapsed = ref(false)

interface Message {
  id: number
  role: 'agent' | 'user'
  content: string
  type: 'info' | 'warning' | 'action'
}

const chatHistory = ref<Message[]>([
  { id: 1, role: 'agent', content: '巡检系统已就位，当前算力节点：Jetson Orin Nano。', type: 'info' }
])

const userInput = ref('')
const chatContainer = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const sendMessage = () => {
  if (!userInput.value.trim()) return
  
  chatHistory.value.push({ id: Date.now(), role: 'user', content: userInput.value, type: 'info' })
  const currentInput = userInput.value
  userInput.value = ''
  scrollToBottom()

  setTimeout(() => {
    chatHistory.value.push({
      id: Date.now(),
      role: 'agent',
      content: `已收到指令：“${currentInput}”。正在协同边缘计算节点调整策略...`,
      type: 'info'
    })
    scrollToBottom()
  }, 800)
}

onMounted(() => {
  setTimeout(() => {
    chatHistory.value.push({
      id: Date.now(),
      role: 'agent',
      content: '【视觉异常告警】检测到疑似高危病害聚集。但当前视角下叶片遮挡率达 42%。',
      type: 'warning'
    })
    scrollToBottom()
  }, 3000)
})
</script>

<template>
  <aside 
    class="relative z-10 min-h-[420px] w-full shrink-0 transition-all duration-300 ease-in-out lg:h-full lg:min-h-0"
    :class="isCollapsed ? 'lg:w-[64px]' : 'lg:w-[320px]'"
  >
    <button 
      @click="isCollapsed = !isCollapsed"
      class="absolute -left-3.5 top-1/2 z-20 hidden h-14 w-7 -translate-y-1/2 items-center justify-center rounded-l-xl border border-slate-200 bg-white text-slate-400 shadow-md transition-colors hover:bg-slate-50 hover:text-rose-600 lg:flex"
    >
      <ChevronRight v-if="isCollapsed" :size="18" />
      <ChevronRight v-else :size="18" class="rotate-180" />
    </button>

    <div class="w-full h-full bg-white border border-slate-200 rounded-xl shadow-lg flex flex-col overflow-hidden relative">
      
      <div 
        v-if="isCollapsed" 
        class="flex-1 flex flex-col items-center py-6 gap-6 cursor-pointer overflow-hidden" 
        @click="isCollapsed = false"
      >
        <div class="relative mt-2">
          <div class="w-10 h-10 bg-rose-50 text-rose-600 rounded-full flex items-center justify-center shadow-sm">
            <Bot :size="20" />
          </div>
          <span class="absolute top-0 right-0 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-white animate-pulse"></span>
        </div>
        <div class="text-xs font-bold text-slate-400 tracking-[0.3em] uppercase" style="writing-mode: vertical-rl;">
          Agent 决策舱
        </div>
      </div>

      <div v-else class="flex h-full w-full shrink-0 flex-1 flex-col overflow-hidden animate-[fadeIn_0.3s_ease-in] lg:w-[320px]">
        <div class="bg-slate-50 p-4 border-b border-slate-200 rounded-t-xl shrink-0 flex items-center gap-2">
          <Bot :size="18" class="text-rose-600"/>
          <h2 class="text-slate-800 font-black text-sm">指挥舱 Agent 助手</h2>
        </div>

        <div ref="chatContainer" class="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">
          <div 
            v-for="msg in chatHistory" 
            :key="msg.id"
            class="flex gap-3"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1" :class="msg.role === 'agent' ? 'bg-rose-100 text-rose-600' : 'bg-slate-100 text-slate-600'">
              <Bot v-if="msg.role === 'agent'" :size="18" />
              <User v-else :size="18" />
            </div>
            <div class="max-w-[85%] text-sm p-3 rounded-2xl shadow-sm border" :class="{'bg-rose-600 text-white border-rose-700 rounded-tr-sm': msg.role === 'user', 'bg-white text-slate-700 border-slate-200 rounded-tl-sm': msg.role === 'agent' && msg.type === 'info', 'bg-red-50 text-red-700 border-red-200 rounded-tl-sm font-medium': msg.role === 'agent' && msg.type === 'warning'}">
              {{ msg.content }}
            </div>
          </div>
        </div>

        <div class="p-3 border-t border-slate-100 bg-slate-50 shrink-0 rounded-b-xl">
          <div class="relative flex items-center">
            <input v-model="userInput" @keyup.enter="sendMessage" type="text" placeholder="输入调度指令..." class="w-full pl-4 pr-10 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-rose-500 shadow-sm" />
            <button @click="sendMessage" class="absolute right-2 text-rose-500 hover:bg-rose-50 p-1.5 rounded-lg"><Send :size="18" /></button>
          </div>
        </div>
      </div>
    </div>

  </aside>
</template>

<style scoped>

</style>
