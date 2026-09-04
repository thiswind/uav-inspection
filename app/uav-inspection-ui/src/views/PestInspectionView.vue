<script setup lang="ts">
// 这里是逻辑控制区 (TypeScript)
import { computed, onMounted, onUnmounted, ref } from 'vue'
import TelemetryPanel from '../components/pest/TelemetryPanel.vue'
import FunctionalArea from '../components/pest/FunctionalArea.vue'
import LiveVideoFeed from '../components/pest/LiveVideoFeed.vue'
import AgentSidebar from '../components/common/AgentSidebar.vue'
import TaskProgressBar from '../components/common/TaskProgressBar.vue'
import SystemLogStream from '../components/common/SystemLogStream.vue'
import InspectionHeader from '../components/common/InspectionHeader.vue'
import FloatingNotice from '../components/common/FloatingNotice.vue'
import { pestApi, type MissionDetail, type RouteItem, type VisionModelItem } from '../api1/pest'

// 页面顶部系统时钟与视频时间戳（用于遥测同步）
const systemTime = ref(new Date().toLocaleTimeString('en-US', { hour12: false }))
const videoTimeSec = ref(0)
const isPaused = ref(true)
const routeInfo = ref<RouteItem | null>(null)
const modelInfo = ref<VisionModelItem | null>(null)
const missionInfo = ref<MissionDetail | null>(null)
const missionStartAt = ref<number | null>(null)
const elapsedSec = ref(0)
const noticeMessage = ref('请选择巡检航线与识别模型后创建任务。')
const noticeTone = ref<'info' | 'success' | 'error'>('info')
let missionTimer: number | undefined

// 简单的定时器，每秒更新时间，体现“状态驱动”
setInterval(() => {
  systemTime.value = new Date().toLocaleTimeString('en-US', { hour12: false })
}, 1000)

const totalDurationSec = computed(() => (routeInfo.value?.duration_min ?? 0) * 60)
const progress = computed(() => {
  if (!totalDurationSec.value) return 0
  return Math.min(1, elapsedSec.value / totalDurationSec.value)
})
const currentWaypoint = computed(() => {
  const total = routeInfo.value?.waypoints ?? 0
  if (!total) return 0
  return Math.min(total, Math.floor(progress.value * total))
})
const remainingSec = computed(() => Math.max(0, totalDurationSec.value - elapsedSec.value))
const statusText = computed(() => {
  if (!missionInfo.value) return 'STANDBY'
  if (progress.value >= 1) return 'COMPLETED'
  return isPaused.value ? 'PAUSED' : 'RUNNING'
})

const startMissionTimer = () => {
  if (missionTimer) return
  missionTimer = window.setInterval(() => {
    if (isPaused.value || !missionStartAt.value) return
    elapsedSec.value = Math.floor((Date.now() - missionStartAt.value) / 1000)
    videoTimeSec.value = elapsedSec.value
  }, 1000)
}

const stopMissionTimer = () => {
  if (missionTimer) {
    window.clearInterval(missionTimer)
    missionTimer = undefined
  }
}

const handleRouteActivated = (route: RouteItem) => {
  routeInfo.value = route
}

const handleModelActivated = (model: VisionModelItem) => {
  modelInfo.value = model
}

const handleMissionCreated = (mission: MissionDetail, route: RouteItem | null, model: VisionModelItem | null) => {
  missionInfo.value = mission
  if (route) routeInfo.value = route
  if (model) modelInfo.value = model
  missionStartAt.value = Date.now()
  elapsedSec.value = 0
  isPaused.value = false
  noticeMessage.value = `任务已启动：${mission.name || route?.name || '病虫害巡检任务'}`
  noticeTone.value = 'success'
  startMissionTimer()
}

const handleTogglePause = async () => {
  isPaused.value = !isPaused.value
  noticeMessage.value = isPaused.value ? '巡检视频已暂停。' : '巡检视频已继续播放。'
  noticeTone.value = 'info'
  if (!isPaused.value) {
    if (!missionStartAt.value) {
      missionStartAt.value = Date.now()
    } else {
      missionStartAt.value = Date.now() - elapsedSec.value * 1000
    }
    startMissionTimer()
  }

  if (!missionInfo.value) return
  try {
    await pestApi.controlMission({
      command: isPaused.value ? 'pause' : 'start',
      params: { mission_id: missionInfo.value.id }
    })
  } catch (error) {
    console.warn('Mission control failed', error)
    noticeMessage.value = '任务控制失败，请检查后端服务。'
    noticeTone.value = 'error'
  }
}

const handleGenerateReport = async () => {
  if (!missionInfo.value) return
  try {
    await pestApi.controlMission({
      command: 'report',
      params: { mission_id: missionInfo.value.id }
    })
    noticeMessage.value = '报告生成任务已提交。'
    noticeTone.value = 'success'
  } catch (error) {
    console.warn('Report generation request failed', error)
    noticeMessage.value = '报告生成请求失败，请稍后重试。'
    noticeTone.value = 'error'
  }
}

onMounted(() => {
  startMissionTimer()
})

onUnmounted(() => {
  stopMissionTimer()
})
</script>

<template>
  <div class="flex min-h-screen w-full flex-col gap-4 overflow-x-hidden bg-slate-50 p-4 font-sans text-slate-700 antialiased selection:bg-rose-200 lg:h-screen lg:w-screen lg:overflow-hidden">
    <InspectionHeader title="病虫害低空智能巡检" :task-name="missionInfo?.name || routeInfo?.name || ''" :online="true">
      <template #actions>
        <button class="border border-rose-200 bg-rose-50 text-sm font-medium text-rose-700" @click="handleTogglePause">
          {{ isPaused ? '继续巡检' : '暂停巡检' }}
        </button>
        <button class="border border-slate-200 bg-white text-sm font-medium text-slate-700" :disabled="!missionInfo" @click="handleGenerateReport">
          生成报告
        </button>
        <span class="px-2 font-mono text-sm text-slate-500">{{ systemTime }}</span>
      </template>
    </InspectionHeader>

    <FloatingNotice :message="noticeMessage" :tone="noticeTone" />

    <main class="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)_auto]">
      
      <aside class="order-2 flex min-h-0 flex-col gap-4 lg:order-none">
        <div class="flex-[3] bg-white border border-slate-200 rounded-xl p-4 shadow-sm relative min-h-0">
          <TelemetryPanel :videoTimeSec="videoTimeSec" />
        </div>
        <div class="flex-[2] bg-white border border-slate-200 rounded-xl p-4 shadow-sm relative min-h-0">
          <FunctionalArea
            @mission-created="handleMissionCreated"
            @route-activated="handleRouteActivated"
            @model-activated="handleModelActivated"
          />
        </div>
      </aside>

      <section class="order-1 flex min-h-[680px] min-w-0 flex-col gap-4 lg:order-none lg:min-h-0">
        <div class="flex-[5] relative min-h-0">
          <LiveVideoFeed :isPaused="isPaused" :routeId="routeInfo?.id" @toggle-pause="handleTogglePause" />
        </div>
        <div class="h-16 bg-white border border-slate-200 rounded-xl shadow-sm shrink-0 overflow-hidden relative">
          <TaskProgressBar
            :isPaused="isPaused"
            :progress="progress"
            :routeName="routeInfo?.name ?? ''"
            :waypoints="routeInfo?.waypoints ?? 0"
            :currentWaypoint="currentWaypoint"
            :remainingSec="remainingSec"
            :statusText="statusText"
            @toggle-pause="handleTogglePause"
            @generate-report="handleGenerateReport"
          />
        </div>
        <div class="flex-[1.5] rounded-xl shadow-sm relative min-h-0">
          <SystemLogStream />
        </div>
      </section>

      <AgentSidebar class="order-3 lg:order-none" />

    </main>
  </div>
</template>

<style scoped>
/* 由于全盘使用了 Tailwind 的原子类，这里不需要写任何 CSS 代码 */
</style>
