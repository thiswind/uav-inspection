<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Activity, ArrowLeft, BarChart3, CheckCircle2, ChevronRight,
  ExternalLink, Layers3, LoaderCircle, MapPin,
  RefreshCw, Sprout, Trees, TriangleAlert,
} from 'lucide-vue-next'
import {
  getVegetationOverview, type VegetationOverview, type VegetationTask,
} from '../api1/vegetation'
import TreeHeightWorkspace from '../components/TreeHeightWorkspace.vue'
import GreenAreaWorkspace from '../components/GreenAreaWorkspace.vue'

const props = defineProps<{ mode: 'height' | 'area' }>()
const router = useRouter()
const overview = ref<VegetationOverview | null>(null)
const selectedKey = ref('task_02_xinxixueyuan_2')
const activeTab = ref<'results' | 'model'>('results')
const loading = ref(true)
const error = ref('')

const isHeight = computed(() => props.mode === 'height')
const selectedTask = computed<VegetationTask | null>(() => overview.value?.tasks.find((task) => task.key === selectedKey.value) ?? null)
const title = computed(() => isHeight.value ? '乔木高度测量' : '绿化面积测量')
const activeModel = computed(() => overview.value?.models?.[props.mode] ?? null)
const classMetrics = computed(() => {
  const classes = activeModel.value?.classes
  if (!classes) return []
  const definitions = isHeight.value
    ? [
        { key: 'other', label: '其他', color: 'bg-slate-500' },
        { key: 'tree', label: '乔木', color: 'bg-emerald-600' },
        { key: 'shrub', label: '灌木', color: 'bg-lime-500' },
      ]
    : [
        { key: 'other', label: '非绿化', color: 'bg-slate-500' },
        { key: 'green', label: '绿化', color: 'bg-emerald-500' },
      ]
  return definitions.filter((item) => classes[item.key]).map((item) => ({ ...item, ...classes[item.key] }))
})

function formatNumber(value: number, digits = 0) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
}
function formatPercent(value: number) { return `${(value * 100).toFixed(1)}%` }

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    const response = await getVegetationOverview()
    overview.value = response.data
    if (!response.data.tasks.some((task) => task.key === selectedKey.value)) selectedKey.value = response.data.tasks[0]?.key ?? ''
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '训练与测量结果加载失败'
  } finally {
    loading.value = false
  }
}

function selectTask(task: VegetationTask) {
  selectedKey.value = task.key
  activeTab.value = 'results'
}
function openWebODM() {
  if (selectedTask.value) window.open(selectedTask.value.webodm_url, '_blank', 'noopener,noreferrer')
}
function switchMode(mode: 'height' | 'area') { router.push(mode === 'height' ? '/height' : '/area') }

watch(() => props.mode, () => { activeTab.value = 'results' })
onMounted(loadOverview)
</script>

<template>
  <div class="min-h-screen bg-[#f3f5f7] text-slate-800">
    <header class="border-b border-slate-200 bg-white">
      <div class="mx-auto flex min-h-16 max-w-[1560px] flex-wrap items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <button type="button" title="返回平台首页" class="flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 text-slate-600 transition hover:bg-slate-50" @click="router.push('/')"><ArrowLeft class="h-5 w-5" /></button>
        <div class="min-w-0 basis-[calc(100%-3.5rem)] sm:flex-1 sm:basis-auto">
          <div class="flex items-center gap-2 text-xs font-semibold text-emerald-700"><span class="h-2 w-2 rounded-full bg-emerald-500"></span>农林植保业务</div>
          <h1 class="text-lg font-semibold leading-tight text-slate-950 sm:truncate sm:text-xl">{{ title }}</h1>
        </div>
        <div class="flex h-10 shrink-0 rounded-md border border-slate-200 bg-slate-50 p-1" aria-label="测量模式">
          <button type="button" class="flex items-center gap-2 rounded px-3 text-sm font-medium transition" :class="isHeight ? 'bg-white text-emerald-700 shadow-sm' : 'text-slate-500'" @click="switchMode('height')"><Trees class="h-4 w-4" />乔木高度</button>
          <button type="button" class="flex items-center gap-2 rounded px-3 text-sm font-medium transition" :class="!isHeight ? 'bg-white text-lime-700 shadow-sm' : 'text-slate-500'" @click="switchMode('area')"><Sprout class="h-4 w-4" />绿化面积</button>
        </div>
        <button type="button" class="flex h-10 shrink-0 items-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50" :disabled="!selectedTask" @click="openWebODM"><ExternalLink class="h-4 w-4" />WebODM</button>
      </div>
    </header>

    <main class="mx-auto max-w-[1560px] px-4 py-5 sm:px-6 lg:px-8">
      <div v-if="loading" class="flex min-h-[60vh] items-center justify-center text-slate-500"><LoaderCircle class="mr-3 h-6 w-6 animate-spin text-emerald-600" />正在读取训练与点云测量结果</div>
      <div v-else-if="error" class="mx-auto mt-16 max-w-lg border border-rose-200 bg-white p-7 text-center shadow-sm">
        <TriangleAlert class="mx-auto h-8 w-8 text-rose-500" /><h2 class="mt-3 text-base font-semibold text-slate-900">数据服务未就绪</h2><p class="mt-2 text-sm text-slate-500">{{ error }}</p>
        <button type="button" class="mt-5 inline-flex items-center gap-2 rounded-md border border-slate-200 px-4 py-2 text-sm font-medium" @click="loadOverview"><RefreshCw class="h-4 w-4" />重新加载</button>
      </div>

      <div v-else-if="overview && !overview.tasks.length" class="mx-auto mt-16 max-w-xl rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        <Sprout class="mx-auto h-10 w-10 text-emerald-500" />
        <h2 class="mt-4 text-lg font-semibold text-slate-900">尚未安装测量数据</h2>
        <p class="mt-3 text-sm leading-6 text-slate-500">平台已正常运行。乔木高度与绿化面积的点云、模型和测量成果属于可选数据包；将 02-data 放到 01-app 旁边并按部署说明恢复数据后，即可查看结果。</p>
        <button type="button" class="mt-5 inline-flex items-center gap-2 rounded-md border border-slate-200 px-4 py-2 text-sm font-medium" @click="loadOverview"><RefreshCw class="h-4 w-4" />重新加载</button>
      </div>

      <div v-else-if="overview" class="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside class="min-w-0 border border-slate-200 bg-white shadow-sm">
          <div class="border-b border-slate-200 px-4 py-4"><div class="flex items-center justify-between"><h2 class="text-sm font-semibold text-slate-950">WebODM 任务</h2><span class="text-xs text-slate-400">{{ overview.totals.tasks }} 个</span></div><p class="mt-1 text-xs text-slate-500">EPSG:32648 · 处理完成</p></div>
          <div class="divide-y divide-slate-100">
            <button v-for="task in overview.tasks" :key="task.key" type="button" class="group w-full px-4 py-4 text-left transition" :class="selectedKey === task.key ? 'bg-emerald-50/80' : 'hover:bg-slate-50'" @click="selectTask(task)">
              <div class="flex items-start gap-3"><span class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" :class="selectedKey === task.key ? 'bg-emerald-500' : 'bg-slate-300'"></span><div class="min-w-0 flex-1">
                <div class="flex items-center justify-between gap-2"><span class="truncate text-sm font-semibold text-slate-900">{{ task.name }}</span><ChevronRight class="h-4 w-4 shrink-0 text-slate-300" /></div>
                <div class="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-500"><span>{{ task.tree_count }} 棵乔木</span><span class="text-right">{{ formatNumber(task.green_area_m2, 1) }} m²</span></div>
              </div></div>
            </button>
          </div>
          <div class="border-t border-slate-200 bg-slate-50 px-4 py-4"><div class="flex items-center gap-2 text-xs font-medium text-slate-600"><CheckCircle2 class="h-4 w-4 text-emerald-500" />{{ activeModel ? '模型与成果文件在线' : '测量成果在线，模型评估未安装' }}</div></div>
        </aside>

        <section class="min-w-0 space-y-5">
          <div class="flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div><div class="flex flex-wrap items-center gap-2"><h2 class="text-2xl font-semibold text-slate-950">{{ selectedTask?.name }}</h2><span class="rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">已完成</span></div>
              <div class="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500"><span class="flex items-center gap-1.5"><Layers3 class="h-3.5 w-3.5" />{{ selectedTask?.images }} 张影像</span><span class="flex items-center gap-1.5"><MapPin class="h-3.5 w-3.5" />EPSG:{{ selectedTask?.epsg }}</span></div>
            </div>
            <div class="flex rounded-md border border-slate-200 bg-white p-1"><button type="button" class="rounded px-3 py-1.5 text-sm font-medium" :class="activeTab === 'results' ? 'bg-slate-900 text-white' : 'text-slate-500'" @click="activeTab = 'results'">测量结果</button><button type="button" class="rounded px-3 py-1.5 text-sm font-medium" :class="activeTab === 'model' ? 'bg-slate-900 text-white' : 'text-slate-500'" @click="activeTab = 'model'">模型评估</button></div>
          </div>

          <template v-if="activeTab === 'results' && selectedTask">
            <TreeHeightWorkspace v-if="isHeight" :task="selectedTask" />
            <GreenAreaWorkspace v-else :task="selectedTask" :tasks="overview.tasks" />
          </template>

          <template v-else-if="activeTab === 'model' && activeModel">
            <div class="grid gap-px overflow-hidden border border-slate-200 bg-slate-200 shadow-sm sm:grid-cols-2 lg:grid-cols-4"><div class="bg-white p-5"><div class="flex items-center gap-2 text-xs text-slate-500"><Activity class="h-4 w-4" />验证准确率</div><div class="mt-3 text-3xl font-semibold text-slate-950">{{ formatPercent(activeModel.accuracy) }}</div></div><div class="bg-white p-5"><div class="flex items-center gap-2 text-xs text-slate-500"><BarChart3 class="h-4 w-4" />Macro F1</div><div class="mt-3 text-3xl font-semibold text-slate-950">{{ formatPercent(activeModel.macro_f1) }}</div></div><div class="bg-white p-5"><div class="text-xs text-slate-500">训练样本点</div><div class="mt-3 text-3xl font-semibold text-slate-950">{{ formatNumber(activeModel.training_samples) }}</div></div><div class="bg-white p-5"><div class="text-xs text-slate-500">验证样本点</div><div class="mt-3 text-3xl font-semibold text-slate-950">{{ formatNumber(activeModel.validation_samples) }}</div></div></div>
            <div class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
              <section class="border border-slate-200 bg-white p-5 shadow-sm"><div class="flex flex-wrap items-start justify-between gap-3"><div><div class="flex items-center gap-2"><h3 class="text-base font-semibold text-slate-950">{{ activeModel.name }}</h3><span class="rounded px-2 py-1 text-xs font-medium" :class="activeModel.status === 'trained' ? 'border border-emerald-200 bg-emerald-50 text-emerald-700' : 'border border-amber-200 bg-amber-50 text-amber-700'">{{ activeModel.badge }}</span></div><p class="mt-1 text-xs text-slate-500">{{ activeModel.algorithm }} · {{ activeModel.description }}</p></div></div>
                <div class="mt-7 space-y-5"><div v-for="metric in classMetrics" :key="metric.key"><div class="mb-2 flex items-center justify-between text-sm"><span class="font-medium text-slate-700">{{ metric.label }}</span><span class="font-semibold text-slate-950">F1 {{ formatPercent(metric.f1) }}</span></div><div class="h-2 overflow-hidden bg-slate-100"><div class="h-full" :class="metric.color" :style="{ width: formatPercent(metric.f1) }"></div></div><div class="mt-2 flex flex-wrap gap-5 text-xs text-slate-400"><span>Precision {{ formatPercent(metric.precision) }}</span><span>Recall {{ formatPercent(metric.recall) }}</span><span>{{ formatNumber(metric.support) }} 点</span></div></div></div>
                <div class="mt-7 grid gap-3 border-t border-slate-200 pt-5 sm:grid-cols-2"><div class="border-l-2 border-emerald-500 pl-3"><div class="text-xs font-semibold text-slate-800">{{ activeModel.validation_title }}</div><div class="mt-1 text-xs leading-5 text-slate-500">{{ activeModel.validation_note }}</div></div><div class="border-l-2 border-amber-400 pl-3"><div class="text-xs font-semibold text-slate-800">数据限制</div><div class="mt-1 text-xs leading-5 text-slate-500">{{ activeModel.data_note }}</div></div></div>
              </section>
              <section class="border border-slate-200 bg-white shadow-sm"><div class="border-b border-slate-200 px-4 py-3"><h3 class="text-sm font-semibold text-slate-950">验证集混淆矩阵</h3><p class="mt-0.5 text-xs text-slate-500">行是真值，列是模型预测</p></div><div class="p-4"><img :src="activeModel.confusion_url" alt="模型验证混淆矩阵" class="w-full object-contain" /></div></section>
            </div>
          </template>
          <div v-else-if="activeTab === 'model'" class="rounded-md border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">尚未安装此模块的模型评估数据，已保存的测量结果仍可查看。</div>
        </section>
      </div>
    </main>
  </div>
</template>
