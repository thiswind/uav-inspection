<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 backdrop-blur-sm p-4">
    <div class="max-h-[calc(100dvh-32px)] w-full max-w-5xl overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl sm:rounded-3xl">
      <div class="flex items-center justify-between border-b border-slate-100 bg-gradient-to-r from-sky-50 to-white px-4 py-4 sm:px-6">
        <div>
          <h3 class="text-lg font-bold text-slate-800">园区客流预测</h3>
          <p class="text-xs text-slate-500 mt-1">按天、按周、按月查看客流趋势与峰值分析</p>
        </div>
        <button @click="close" class="text-slate-400 hover:text-slate-700 text-xl leading-none">&times;</button>
      </div>

      <div class="flex gap-2 overflow-x-auto border-b border-slate-100 bg-slate-50/70 px-4 pt-4 sm:px-6">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          class="px-4 py-2 text-sm rounded-t-xl border transition"
          :class="activeTab === tab.key ? 'bg-white border-slate-200 border-b-white text-sky-600 font-semibold' : 'border-transparent text-slate-500 hover:text-slate-700'"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="grid grid-cols-2 gap-3 bg-slate-50/50 px-4 py-4 sm:gap-4 sm:px-6 md:grid-cols-4">
        <div v-for="metric in metrics" :key="metric.label" class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div class="text-xs text-slate-500">{{ metric.label }}</div>
          <div class="mt-2 text-2xl font-bold text-slate-800">{{ metric.value }}</div>
          <div class="mt-1 text-xs text-slate-400">{{ metric.tip }}</div>
        </div>
      </div>

      <div class="px-4 py-5 sm:px-6">
        <div ref="chartRef" class="h-[280px] w-full sm:h-[360px]"></div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3 px-4 pb-5 text-xs text-slate-500 sm:px-6 sm:pb-6">
        <span>{{ statusText }}</span>
        <button @click="close" class="px-4 py-2 rounded-xl bg-sky-500 text-white hover:bg-sky-600 transition">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, shallowRef, watch } from 'vue'
import * as echarts from 'echarts'
import request from '../../api1/heatmap/request'

type TabKey = 'daily' | 'weekly' | 'monthly'

interface PeakInfo {
  name: string
  center: string
  value: number
}

interface ViewData {
  times: string[]
  actual: number[]
  predicted: number[]
  peaks: PeakInfo[]
  r2: string
}

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [boolean] }>()

const tabs = [
  { key: 'daily' as TabKey, label: '按天预测' },
  { key: 'weekly' as TabKey, label: '按周预测' },
  { key: 'monthly' as TabKey, label: '按月趋势' },
]

const activeTab = ref<TabKey>('daily')
const chartRef = ref<HTMLElement | null>(null)
const chartInstance = shallowRef<echarts.ECharts | null>(null)
const loading = ref(false)

const dailyView = ref<ViewData>({ times: [], actual: [], predicted: [], peaks: [], r2: '--' })
const weeklyView = ref<ViewData>({ times: [], actual: [], predicted: [], peaks: [], r2: '--' })
const monthlyView = ref<ViewData>({ times: [], actual: [], predicted: [], peaks: [], r2: '--' })

const currentView = computed(() => {
  if (activeTab.value === 'weekly') return weeklyView.value
  if (activeTab.value === 'monthly') return monthlyView.value
  return dailyView.value
})

const metrics = computed(() => {
  const peaks = currentView.value.peaks
  return [
    {
      label: '峰值人数',
      value: peaks[0] ? `${peaks[0].value}` : '--',
      tip: peaks[0] ? `${peaks[0].name} ${peaks[0].center}` : '暂无数据',
    },
    {
      label: '平均客流',
      value: currentView.value.actual.length ? `${Math.round(currentView.value.actual.reduce((s, n) => s + n, 0) / currentView.value.actual.length)}` : '--',
      tip: '基于当前时间范围计算',
    },
    {
      label: '拟合 R²',
      value: currentView.value.r2,
      tip: activeTab.value === 'monthly' ? '月趋势使用平滑曲线展示' : '越接近 1 拟合越稳定',
    },
    {
      label: '样本点数',
      value: `${currentView.value.times.length || 0}`,
      tip: '用于当前视图的时间片数量',
    },
  ]
})

const statusText = computed(() => {
  if (loading.value) return '正在加载预测数据...'
  if (!currentView.value.times.length) return '暂无可展示的预测数据'
  return activeTab.value === 'monthly' ? '月趋势为近 30 天平滑客流走势' : '数据来源于 demo 预测接口与本地模拟样本'
})

const close = () => emit('update:visible', false)

function createWeeklyView() {
  const labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const actual = [56, 46, 50, 61, 43, 561, 632]
  const predicted = [52, 48, 49, 60, 54, 518, 645]
  weeklyView.value = {
    times: labels,
    actual,
    predicted,
    peaks: [{ name: '周末高峰', center: '周日', value: 645 }],
    r2: '0.9731',
  }
}

function createMonthlyView() {
  const labels: string[] = []
  const actual: number[] = []
  const predicted: number[] = []
  const now = new Date()
  for (let i = 29; i >= 0; i -= 1) {
    const d = new Date(now)
    d.setDate(now.getDate() - i)
    labels.push(`${d.getMonth() + 1}/${d.getDate()}`)
    const base = i % 7 === 0 || i % 7 === 1 ? 620 : 70 + (29 - i) * 6
    actual.push(base)
    predicted.push(Math.round(base * 0.96 + 18))
  }
  const peak = Math.max(...predicted)
  const peakIndex = predicted.indexOf(peak)
  monthlyView.value = {
    times: labels,
    actual,
    predicted,
    peaks: [{ name: '月度峰值', center: labels[peakIndex], value: peak }],
    r2: '--',
  }
}

async function loadDailyView() {
  loading.value = true
  try {
    const response = await request.get('/predict/footfall')
    const payload = response?.data ?? response
    const peaks = Array.isArray(payload.peaks) ? payload.peaks : []
    dailyView.value = {
      times: Array.isArray(payload.times) ? payload.times : [],
      actual: Array.isArray(payload.actual) ? payload.actual : [],
      predicted: Array.isArray(payload.predicted) ? payload.predicted : [],
      peaks: peaks.map((peak: any) => ({
        name: String(peak.name ?? '高峰'),
        center: String(peak.center ?? '--'),
        value: Number(peak.value ?? 0),
      })),
      r2: payload.gaussParams?.r_squared != null ? Number(payload.gaussParams.r_squared).toFixed(4) : '--',
    }
  } catch (error) {
    console.error('加载客流预测失败:', error)
    dailyView.value = {
      times: ['09:00', '11:00', '13:00', '15:00', '17:00', '19:00'],
      actual: [30, 84, 132, 118, 165, 92],
      predicted: [28, 80, 140, 122, 158, 95],
      peaks: [{ name: '日间高峰', center: '17:00', value: 165 }],
      r2: '0.9480',
    }
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }

  const view = currentView.value
  chartInstance.value.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['实际客流', activeTab.value === 'monthly' ? '趋势曲线' : '预测曲线'] },
    grid: { top: 40, left: 40, right: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: view.times,
      axisLabel: { color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } },
    },
    series: [
      {
        name: '实际客流',
        type: 'line',
        smooth: true,
        data: view.actual,
        symbolSize: 7,
        itemStyle: { color: '#0ea5e9' },
        lineStyle: { color: '#0ea5e9', width: 2 },
      },
      {
        name: activeTab.value === 'monthly' ? '趋势曲线' : '预测曲线',
        type: 'line',
        smooth: true,
        data: view.predicted,
        symbolSize: 6,
        itemStyle: { color: '#f97316' },
        lineStyle: { color: '#f97316', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(249,115,22,0.25)' },
            { offset: 1, color: 'rgba(249,115,22,0.02)' },
          ]),
        },
        markLine: view.peaks.length
          ? {
              symbol: 'none',
              lineStyle: { type: 'dashed', color: '#f97316' },
              data: view.peaks.map((peak) => ({ xAxis: peak.center, label: { formatter: `${peak.name} ${peak.value}` } })),
            }
          : undefined,
      },
    ],
  })
}

watch(activeTab, async () => {
  await nextTick()
  renderChart()
})

watch(() => props.visible, async (visible) => {
  if (!visible) return
  await loadDailyView()
  createWeeklyView()
  createMonthlyView()
  await nextTick()
  renderChart()
})

const handleResize = () => chartInstance.value?.resize()
window.addEventListener('resize', handleResize)

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
  chartInstance.value = null
})
</script>
