<script setup lang="ts">
import { ref, onMounted, onUnmounted, shallowRef, watch } from 'vue'
import { Battery, Navigation, Activity, PieChart, Gauge, Satellite } from 'lucide-vue-next'
import * as echarts from 'echarts'
import { pestApi, type PestStatItem } from '../../api1/pest'

const props = defineProps<{
  videoTimeSec: number
}>()

// 1. 遥测状态
const uavState = ref({
  battery: 78,
  signal: 92,
  altitude: 15.4,
  speed: 4.2,      
  satellites: 24,  
  mode: '3D FIX', 
})

// 2. 业务统计数据
const pestData = ref<PestStatItem[]>([])

let statsStream: number
const chartRef = ref<HTMLElement | null>(null)
const chartInstance = shallowRef<echarts.ECharts | null>(null)
const lastRequestedSec = ref(-1)

// 3. 初始化饼图（环形模式）
const initChart = () => {
  if (!chartRef.value) return
  chartInstance.value = echarts.init(chartRef.value)
  
  const option = {
    // 颜色方案：科技蓝、琥珀黄、玫瑰红
    color: ['#3b82f6', '#fbbf24', '#f43f5e'],
    tooltip: { 
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      borderColor: '#e2e8f0',
      textStyle: { color: '#1e293b', fontSize: 11 }
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'center',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { fontSize: 10, color: '#64748b' }
    },
    series: [
      {
        name: '病害占比',
        type: 'pie',
        // 环形设计：[内半径, 外半径]
        radius: ['50%', '80%'],
        center: ['65%', '50%'], // 偏右显示，给左侧图例留空间
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false, // 侧边栏空间有限，通过图例和 Tooltip 展示文字
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 12,
            fontWeight: 'bold',
            formatter: '{b}\n{d}%' // 悬浮显示名称和百分比
          }
        },
        data: pestData.value
      }
    ]
  }
  chartInstance.value.setOption(option)
}

const handleResize = () => {
  chartInstance.value?.resize()
}

// 根据视频秒数拉取遥测数据
const refreshTelemetry = async (timeSec: number) => {
  try {
    const response = await pestApi.getTelemetry(timeSec)
    uavState.value = { ...uavState.value, ...response.data }
  } catch (error) {
    console.warn('Telemetry fetch failed', error)
  }
}

// 定时刷新病害统计并更新图表
const refreshStatistics = async () => {
  try {
    const response = await pestApi.getStatistics()
    pestData.value = response.data
    if (chartInstance.value) {
      chartInstance.value.setOption({
        series: [{ data: pestData.value }]
      })
    }
  } catch (error) {
    console.warn('Statistics fetch failed', error)
  }
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)

  refreshStatistics()
  statsStream = setInterval(refreshStatistics, 10000)
})

onUnmounted(() => {
  clearInterval(statsStream)
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
})

watch(
  () => props.videoTimeSec,
  (value) => {
    if (value === lastRequestedSec.value) return
    lastRequestedSec.value = value
    refreshTelemetry(value)
  }
)
</script>

<template>
  <div class="h-full flex flex-col">
    <h2 class="text-rose-700 font-bold mb-4 flex items-center justify-between text-base border-b border-slate-100 pb-2 shrink-0">
      <div class="flex items-center gap-2">
        <Activity :size="18" /> 实时遥测链路
      </div>
      <div class="flex items-center gap-1.5 bg-rose-50 px-2 py-1 rounded text-xs font-mono font-bold text-rose-500">
        <span class="w-1.5 h-1.5 bg-rose-500 rounded-full animate-pulse"></span>
        MAVLink v2.0
      </div>
    </h2>
    
    <div class="grid grid-cols-2 gap-3 shrink-0">

      <div class="flex flex-col bg-slate-50 border border-slate-100 p-3 rounded-xl">
        <div class="flex items-center gap-2 text-slate-500 mb-1.5">
          <Battery :size="16" class="text-emerald-500"/> <span class="text-xs font-bold">动力电量</span>
        </div>
        <div class="font-mono text-slate-800 font-bold text-lg">
          {{ uavState.battery }}% <span class="text-xs text-slate-400 ml-1">~24m</span>
        </div>
      </div>

      <div class="flex flex-col bg-slate-50 border border-slate-100 p-3 rounded-xl">
        <div class="flex items-center gap-2 text-slate-500 mb-1.5">
          <Satellite :size="16" class="text-rose-500"/> <span class="text-xs font-bold">搜星数量</span>
        </div>
        <div class="font-mono text-slate-800 font-bold text-lg">
          {{ uavState.satellites }} <span class="text-xs text-slate-400 ml-1">GNSS</span>
        </div>
      </div>

      <div class="flex flex-col bg-slate-50 border border-slate-100 p-3 rounded-xl">
        <div class="flex items-center gap-2 text-slate-500 mb-1.5">
          <Navigation :size="16" class="text-purple-500"/> <span class="text-xs font-bold">相对高度</span>
        </div>
        <div class="font-mono text-slate-800 font-bold text-lg">
          {{ uavState.altitude }} <span class="text-xs text-slate-400 ml-1">m</span>
        </div>
      </div>

      <div class="flex flex-col bg-slate-50 border border-slate-100 p-3 rounded-xl">
        <div class="flex items-center gap-2 text-slate-500 mb-1.5">
          <Gauge :size="16" class="text-amber-500"/> <span class="text-xs font-bold">飞行速度</span>
        </div>
        <div class="font-mono text-slate-800 font-bold text-lg">
          {{ uavState.speed }} <span class="text-xs text-slate-400 ml-1">m/s</span>
        </div>
      </div>

    </div>

    <div class="mt-4 flex-1 flex flex-col min-h-0 border-t border-slate-100 pt-3">
      <h3 class="text-slate-600 font-bold mb-2 flex items-center justify-between text-sm shrink-0">
        <div class="flex items-center gap-2"><PieChart :size="16" class="text-rose-500" /> AI 病害分布占比</div>
      </h3>
      <div class="flex-1 bg-white rounded-lg relative min-h-[140px]">
        <div ref="chartRef" class="absolute inset-0 w-full h-full"></div>
      </div>
    </div>
  </div>
</template>
