<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Activity,
  ArrowLeft,
  Bot,
  CalendarDays,
  Camera,
  ChevronRight,
  CircleCheck,
  ClipboardList,
  Database,
  Droplets,
  Flower2,
  Gauge,
  Leaf,
  MapPinned,
  Route,
  ScanLine,
  ShieldAlert,
  Sprout,
  Sun,
  ThermometerSun,
  TriangleAlert,
  Wind,
} from 'lucide-vue-next'

interface RoseTask {
  id: string
  title: string
  owner: string
  time: string
  status: 'ready' | 'running' | 'pending'
}

interface RosePlot {
  id: string
  name: string
  variety: string
  phase: string
  status: 'healthy' | 'watch' | 'urgent'
  area: number
  plantCount: number
  bloomRate: number
  health: number
  moisture: number
  pestRisk: number
  predictedYield: number
  temperature: number
  wind: number
  lastFlight: string
  x: number
  y: number
  w: number
  h: number
  color: string
  note: string
  trend: number[]
  tasks: RoseTask[]
}

const router = useRouter()
const selectedPlotId = ref('A1')

const plots: RosePlot[] = [
  {
    id: 'A1',
    name: 'A1 晨露区',
    variety: '卡罗拉',
    phase: '盛花期',
    status: 'healthy',
    area: 12.8,
    plantCount: 3680,
    bloomRate: 82,
    health: 96,
    moisture: 63,
    pestRisk: 8,
    predictedYield: 1460,
    temperature: 24.6,
    wind: 2.1,
    lastFlight: '09:30',
    x: 7,
    y: 10,
    w: 37,
    h: 34,
    color: '#e11d48',
    note: '冠层密度稳定，花苞转开比例高，适合安排采收复核。',
    trend: [62, 66, 68, 71, 75, 79, 82],
    tasks: [
      { id: 'T-1021', title: '采摘窗口复核', owner: 'AI 调度', time: '10:20', status: 'ready' },
      { id: 'T-1014', title: '低空正射更新', owner: '无人机 02', time: '09:30', status: 'running' },
    ],
  },
  {
    id: 'A2',
    name: 'A2 云锦区',
    variety: '粉佳人',
    phase: '初花期',
    status: 'watch',
    area: 9.6,
    plantCount: 2810,
    bloomRate: 54,
    health: 88,
    moisture: 47,
    pestRisk: 22,
    predictedYield: 980,
    temperature: 25.2,
    wind: 2.4,
    lastFlight: '09:46',
    x: 49,
    y: 10,
    w: 28,
    h: 34,
    color: '#db2777',
    note: '土壤水分略低，东侧两列长势偏慢，建议追加一次滴灌。',
    trend: [38, 41, 43, 46, 50, 52, 54],
    tasks: [
      { id: 'T-1030', title: '滴灌策略确认', owner: '园艺组', time: '11:00', status: 'pending' },
      { id: 'T-1029', title: '花期样方拍照', owner: '无人机 01', time: '10:45', status: 'ready' },
    ],
  },
  {
    id: 'B1',
    name: 'B1 风铃区',
    variety: '自由精神',
    phase: '营养生长期',
    status: 'healthy',
    area: 14.2,
    plantCount: 4120,
    bloomRate: 31,
    health: 92,
    moisture: 68,
    pestRisk: 12,
    predictedYield: 1210,
    temperature: 23.9,
    wind: 1.8,
    lastFlight: '08:58',
    x: 7,
    y: 52,
    w: 31,
    h: 35,
    color: '#059669',
    note: '新梢生长一致，冠幅扩张良好，短期以养护观察为主。',
    trend: [22, 23, 25, 27, 29, 30, 31],
    tasks: [
      { id: 'T-1018', title: '长势指数归档', owner: '数字档案', time: '09:05', status: 'ready' },
      { id: 'T-1017', title: '叶面颜色复测', owner: 'AI 调度', time: '明日', status: 'pending' },
    ],
  },
  {
    id: 'B2',
    name: 'B2 星河区',
    variety: '朱丽叶',
    phase: '盛花期',
    status: 'urgent',
    area: 10.4,
    plantCount: 3050,
    bloomRate: 76,
    health: 79,
    moisture: 58,
    pestRisk: 36,
    predictedYield: 1045,
    temperature: 26.1,
    wind: 2.9,
    lastFlight: '10:08',
    x: 44,
    y: 53,
    w: 33,
    h: 34,
    color: '#f59e0b',
    note: '南侧边界出现病害疑似点，需优先复飞并触发人工确认。',
    trend: [58, 60, 64, 68, 71, 74, 76],
    tasks: [
      { id: 'T-1042', title: '病害疑似点复飞', owner: '无人机 03', time: '10:40', status: 'running' },
      { id: 'T-1041', title: '人工巡检派单', owner: '园艺组', time: '11:30', status: 'pending' },
    ],
  },
  {
    id: 'C1',
    name: 'C1 月影区',
    variety: '蜜桃雪山',
    phase: '采后恢复',
    status: 'healthy',
    area: 8.2,
    plantCount: 2460,
    bloomRate: 18,
    health: 90,
    moisture: 72,
    pestRisk: 10,
    predictedYield: 620,
    temperature: 23.4,
    wind: 1.5,
    lastFlight: '08:42',
    x: 82,
    y: 21,
    w: 12,
    h: 63,
    color: '#0ea5e9',
    note: '采后恢复平稳，水肥状态充足，可进入下轮修剪排程。',
    trend: [41, 36, 31, 26, 22, 19, 18],
    tasks: [
      { id: 'T-1008', title: '采后恢复记录', owner: '数字档案', time: '08:50', status: 'ready' },
      { id: 'T-1007', title: '修剪计划生成', owner: 'AI 调度', time: '明日', status: 'pending' },
    ],
  },
]

const selectedPlot = computed(() => plots.find((plot) => plot.id === selectedPlotId.value) ?? plots[0])

const gardenTotals = computed(() => {
  const area = plots.reduce((sum, plot) => sum + plot.area, 0)
  const yieldTotal = plots.reduce((sum, plot) => sum + plot.predictedYield, 0)
  const health = Math.round(plots.reduce((sum, plot) => sum + plot.health, 0) / plots.length)
  const riskCount = plots.filter((plot) => plot.status !== 'healthy').length
  return { area, yieldTotal, health, riskCount }
})

const selectedTrend = computed(() => {
  const max = Math.max(...selectedPlot.value.trend)
  return selectedPlot.value.trend.map((value) => ({
    value,
    height: Math.max(18, Math.round((value / max) * 100)),
  }))
})

const statusText = {
  healthy: '稳定',
  watch: '关注',
  urgent: '优先',
} as const

const statusClass = {
  healthy: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  watch: 'border-amber-200 bg-amber-50 text-amber-700',
  urgent: 'border-rose-200 bg-rose-50 text-rose-700',
} as const

const taskStatusClass = {
  ready: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  running: 'border-sky-200 bg-sky-50 text-sky-700',
  pending: 'border-slate-200 bg-slate-50 text-slate-600',
} as const

const taskStatusText = {
  ready: '已就绪',
  running: '执行中',
  pending: '待排程',
} as const

const mapStyle = (plot: RosePlot) => ({
  left: `${plot.x}%`,
  top: `${plot.y}%`,
  width: `${plot.w}%`,
  height: `${plot.h}%`,
  '--plot-color': plot.color,
})

const metricBars = computed(() => [
  { label: '开花率', value: selectedPlot.value.bloomRate, color: 'bg-rose-500' },
  { label: '健康度', value: selectedPlot.value.health, color: 'bg-emerald-500' },
  { label: '土壤水分', value: selectedPlot.value.moisture, color: 'bg-sky-500' },
  { label: '病害风险', value: selectedPlot.value.pestRisk, color: 'bg-amber-500' },
])

const allTasks = computed(() => plots.flatMap((plot) => plot.tasks.map((task) => ({ ...task, plot: plot.name }))))
</script>

<template>
  <div class="min-h-screen bg-slate-100 text-slate-900">
    <header class="border-b border-slate-200 bg-white">
      <div class="mx-auto flex min-h-16 max-w-[1500px] flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-8">
        <div class="flex min-w-0 items-center gap-3">
          <button
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
            title="返回首页"
            @click="router.push('/')"
          >
            <ArrowLeft :size="18" />
          </button>
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700">
                <Database :size="14" />
                内置示例档案
              </span>
              <span class="inline-flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                <CircleCheck :size="14" />
                {{ plots.length }} 个示例地块
              </span>
            </div>
            <h1 class="mt-1 text-2xl font-bold text-slate-950">数字玫瑰园</h1>
            <p class="mt-1 text-xs text-slate-500">演示数据，不代表实时监测结果；无需视频数据包即可浏览。</p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div class="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <div class="text-xs text-slate-500">总面积</div>
            <div class="font-semibold">{{ gardenTotals.area.toFixed(1) }} 亩</div>
          </div>
          <div class="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <div class="text-xs text-slate-500">预测产量</div>
            <div class="font-semibold">{{ gardenTotals.yieldTotal }} kg</div>
          </div>
          <div class="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <div class="text-xs text-slate-500">健康均值</div>
            <div class="font-semibold">{{ gardenTotals.health }}%</div>
          </div>
          <div class="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <div class="text-xs text-slate-500">待关注</div>
            <div class="font-semibold">{{ gardenTotals.riskCount }} 块</div>
          </div>
        </div>
      </div>
    </header>

    <main class="mx-auto grid max-w-[1500px] gap-4 px-4 py-4 md:px-8 xl:grid-cols-[300px_minmax(0,1fr)_340px]">
      <aside class="flex flex-col gap-3">
        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 flex items-center justify-between">
            <div class="flex items-center gap-2 font-semibold">
              <MapPinned :size="18" class="text-rose-600" />
              地块列表
            </div>
            <span class="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-500">示例档案</span>
          </div>
          <div class="grid gap-2">
            <button
              v-for="plot in plots"
              :key="plot.id"
              :data-testid="`plot-list-${plot.id}`"
              class="rounded-lg border p-3 text-left transition hover:border-rose-200 hover:bg-rose-50"
              :class="selectedPlot.id === plot.id ? 'border-rose-300 bg-rose-50 shadow-sm' : 'border-slate-200 bg-white'"
              @click="selectedPlotId = plot.id"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: plot.color }"></span>
                    <span class="truncate font-semibold text-slate-900">{{ plot.name }}</span>
                  </div>
                  <div class="mt-1 text-xs text-slate-500">{{ plot.variety }} · {{ plot.phase }}</div>
                </div>
                <span class="shrink-0 rounded-lg border px-2 py-0.5 text-xs font-semibold" :class="statusClass[plot.status]">{{ statusText[plot.status] }}</span>
              </div>
              <div class="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div class="text-slate-400">开花</div>
                  <div class="font-semibold">{{ plot.bloomRate }}%</div>
                </div>
                <div>
                  <div class="text-slate-400">健康</div>
                  <div class="font-semibold">{{ plot.health }}%</div>
                </div>
                <div>
                  <div class="text-slate-400">风险</div>
                  <div class="font-semibold">{{ plot.pestRisk }}%</div>
                </div>
              </div>
            </button>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 flex items-center gap-2 font-semibold">
            <Bot :size="18" class="text-sky-600" />
            AI 建议
          </div>
          <div class="rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm leading-6 text-slate-700">
            {{ selectedPlot.note }}
          </div>
          <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <div class="text-slate-500">最近航拍</div>
              <div class="mt-1 font-semibold text-slate-900">{{ selectedPlot.lastFlight }}</div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <div class="text-slate-500">档案编号</div>
              <div class="mt-1 font-semibold text-slate-900">RG-{{ selectedPlot.id }}</div>
            </div>
          </div>
        </div>
      </aside>

      <section class="flex min-w-0 flex-col gap-4">
        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <div class="flex items-center gap-2 font-semibold">
                <Route :size="18" class="text-emerald-600" />
                园区态势图
              </div>
              <div class="mt-1 text-sm text-slate-500">{{ selectedPlot.name }} · {{ selectedPlot.variety }} · {{ selectedPlot.phase }}</div>
            </div>
            <div class="flex flex-wrap gap-2">
              <span class="inline-flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                <ScanLine :size="14" />
                低空巡检
              </span>
              <span class="inline-flex items-center gap-1 rounded-lg border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
                <Camera :size="14" />
                正射更新
              </span>
            </div>
          </div>

          <div class="relative min-h-[420px] overflow-hidden rounded-lg border border-slate-200 bg-[#e7efe7]">
            <div class="absolute inset-0 opacity-60 [background-image:linear-gradient(90deg,rgba(15,23,42,0.06)_1px,transparent_1px),linear-gradient(rgba(15,23,42,0.06)_1px,transparent_1px)] [background-size:40px_40px]"></div>
            <div class="absolute left-[3%] top-[47%] h-[6%] w-[74%] rounded-lg bg-slate-300/70"></div>
            <div class="absolute left-[78%] top-[8%] h-[80%] w-[2.5%] rounded-lg bg-slate-300/70"></div>
            <div class="absolute left-[4%] top-[8%] h-[82%] w-[2%] rounded-lg bg-emerald-900/20"></div>
            <div class="absolute bottom-[6%] left-[8%] right-[7%] h-[3%] rounded-lg bg-emerald-900/20"></div>

            <button
              v-for="plot in plots"
              :key="plot.id"
              :data-testid="`map-plot-${plot.id}`"
              class="absolute flex flex-col justify-between rounded-lg border-2 bg-white/80 p-3 text-left shadow-sm transition hover:scale-[1.01]"
              :class="selectedPlot.id === plot.id ? 'border-rose-500 ring-4 ring-rose-100' : 'border-white/90'"
              :style="mapStyle(plot)"
              @click="selectedPlotId = plot.id"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="truncate text-sm font-bold text-slate-950">{{ plot.name }}</div>
                  <div class="mt-0.5 truncate text-xs text-slate-600">{{ plot.variety }}</div>
                </div>
                <span class="h-3 w-3 shrink-0 rounded-full" :style="{ backgroundColor: plot.color }"></span>
              </div>
              <div class="grid grid-cols-2 gap-1 text-xs text-slate-700">
                <span>开花 {{ plot.bloomRate }}%</span>
                <span>健康 {{ plot.health }}%</span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-slate-200">
                <div class="h-full rounded-full" :style="{ width: `${plot.health}%`, backgroundColor: plot.color }"></div>
              </div>
            </button>

            <div class="absolute left-[12%] top-[39%] flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm">
              <Activity :size="15" class="text-emerald-600" />
              UAV-02
            </div>
            <div class="absolute left-[28%] top-[41%] h-1 w-[28%] rounded-full bg-emerald-500"></div>
            <div class="absolute left-[54%] top-[38%] h-4 w-4 rounded-full border-4 border-white bg-emerald-500 shadow"></div>
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-4">
          <div v-for="bar in metricBars" :key="bar.label" class="rounded-lg border border-slate-200 bg-white p-4">
            <div class="flex items-center justify-between text-sm">
              <span class="text-slate-500">{{ bar.label }}</span>
              <span class="font-bold">{{ bar.value }}%</span>
            </div>
            <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
              <div class="h-full rounded-full transition-all" :class="bar.color" :style="{ width: `${bar.value}%` }"></div>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 flex items-center justify-between">
            <div class="flex items-center gap-2 font-semibold">
              <ClipboardList :size="18" class="text-slate-700" />
              近期任务
            </div>
            <span class="text-xs text-slate-500">{{ allTasks.length }} 条记录</span>
          </div>
          <div class="grid gap-2 lg:grid-cols-2">
            <div v-for="task in allTasks" :key="task.id" class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate font-semibold text-slate-900">{{ task.title }}</div>
                  <div class="mt-1 text-xs text-slate-500">{{ task.plot }} · {{ task.owner }} · {{ task.time }}</div>
                </div>
                <span class="shrink-0 rounded-lg border px-2 py-0.5 text-xs font-semibold" :class="taskStatusClass[task.status]">{{ taskStatusText[task.status] }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <aside class="flex flex-col gap-4">
        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 flex items-center justify-between">
            <div class="flex items-center gap-2 font-semibold">
              <Flower2 :size="18" class="text-rose-600" />
              地块档案
            </div>
            <span class="rounded-lg border px-2 py-0.5 text-xs font-semibold" :class="statusClass[selectedPlot.status]">{{ statusText[selectedPlot.status] }}</span>
          </div>
          <div class="grid gap-3">
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="text-xs text-slate-500">地块名称</div>
              <div class="mt-1 text-lg font-bold">{{ selectedPlot.name }}</div>
              <div class="mt-1 text-sm text-slate-600">{{ selectedPlot.variety }} · {{ selectedPlot.phase }}</div>
            </div>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div class="rounded-lg border border-slate-200 p-3">
                <div class="flex items-center gap-1 text-slate-500"><Sprout :size="15" /> 株数</div>
                <div class="mt-1 font-bold">{{ selectedPlot.plantCount }}</div>
              </div>
              <div class="rounded-lg border border-slate-200 p-3">
                <div class="flex items-center gap-1 text-slate-500"><Gauge :size="15" /> 面积</div>
                <div class="mt-1 font-bold">{{ selectedPlot.area }} 亩</div>
              </div>
              <div class="rounded-lg border border-slate-200 p-3">
                <div class="flex items-center gap-1 text-slate-500"><ThermometerSun :size="15" /> 温度</div>
                <div class="mt-1 font-bold">{{ selectedPlot.temperature }} ℃</div>
              </div>
              <div class="rounded-lg border border-slate-200 p-3">
                <div class="flex items-center gap-1 text-slate-500"><Wind :size="15" /> 风速</div>
                <div class="mt-1 font-bold">{{ selectedPlot.wind }} m/s</div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 flex items-center gap-2 font-semibold">
            <Leaf :size="18" class="text-emerald-600" />
            生长曲线
          </div>
          <div class="flex h-36 items-end gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div v-for="(point, index) in selectedTrend" :key="index" class="flex flex-1 flex-col items-center gap-2">
              <div class="w-full rounded-t bg-rose-500 transition-all" :style="{ height: `${point.height}%` }"></div>
              <span class="text-[11px] text-slate-500">{{ point.value }}</span>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 flex items-center gap-2 font-semibold">
            <ShieldAlert :size="18" class="text-amber-600" />
            风险与环境
          </div>
          <div class="grid gap-2">
            <div class="flex items-center justify-between rounded-lg border border-slate-200 p-3">
              <div class="flex items-center gap-2 text-sm text-slate-600"><Droplets :size="16" class="text-sky-600" /> 土壤水分</div>
              <div class="font-bold">{{ selectedPlot.moisture }}%</div>
            </div>
            <div class="flex items-center justify-between rounded-lg border border-slate-200 p-3">
              <div class="flex items-center gap-2 text-sm text-slate-600"><TriangleAlert :size="16" class="text-amber-600" /> 病害风险</div>
              <div class="font-bold">{{ selectedPlot.pestRisk }}%</div>
            </div>
            <div class="flex items-center justify-between rounded-lg border border-slate-200 p-3">
              <div class="flex items-center gap-2 text-sm text-slate-600"><Sun :size="16" class="text-orange-500" /> 预计产量</div>
              <div class="font-bold">{{ selectedPlot.predictedYield }} kg</div>
            </div>
          </div>
        </div>

        <button
          class="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-left font-semibold text-rose-700 transition hover:bg-rose-100"
          @click="router.push('/rose-yield')"
        >
          <span class="flex items-center gap-2"><CalendarDays :size="18" /> 产量预测</span>
          <ChevronRight :size="18" />
        </button>
      </aside>
    </main>
  </div>
</template>
