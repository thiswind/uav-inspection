<script setup lang="ts">
import { ref } from 'vue'
import { 
  Layers, Map, Scan, FileClock, ChevronRight, X, 
  MapPin, Play, Cpu, FileText, Download, Activity 
} from 'lucide-vue-next'
import {
  pestApi,
  type MissionDetail,
  type ReportItem,
  type RouteItem,
  type VisionModelItem
} from '../../api1/pest'

const emit = defineEmits<{
  (event: 'mission-created', mission: MissionDetail, route: RouteItem | null, model: VisionModelItem | null): void
  (event: 'route-activated', route: RouteItem): void
  (event: 'model-activated', model: VisionModelItem): void
}>()

// 控制二级业务弹窗的核心状态
const activeModal = ref<string | null>(null)

// 业务数据与状态（航线、模型、报告、任务）
const routes = ref<RouteItem[]>([])
const models = ref<VisionModelItem[]>([])
const reports = ref<ReportItem[]>([])
const selectedRouteId = ref<string | null>(null)
const selectedModelId = ref<string | null>(null)
const missionResult = ref<MissionDetail | null>(null)
const loading = ref({ route: false, model: false, report: false, mission: false })
const errorMessage = ref<string | null>(null)

// 打开弹窗时拉取对应数据
const openModal = async (type: string) => {
  activeModal.value = type
  errorMessage.value = null
  missionResult.value = null

  if (type === 'route') {
    await fetchRoutes()
  }

  if (type === 'model') {
    await fetchModels()
  }

  if (type === 'report') {
    await fetchReports()
  }
}

// 拉取航线列表
const fetchRoutes = async () => {
  loading.value.route = true
  try {
    const response = await pestApi.listRoutes()
    routes.value = response.data
    if (!selectedRouteId.value && routes.value.length > 0) {
      selectedRouteId.value = routes.value[0].id
    }
  } catch (error) {
    errorMessage.value = '航线数据获取失败'
    console.warn('Route fetch failed', error)
  } finally {
    loading.value.route = false
  }
}

// 拉取视觉模型列表
const fetchModels = async () => {
  loading.value.model = true
  try {
    const response = await pestApi.listModels()
    models.value = response.data
    const active = models.value.find((item) => item.status === 'active')
    if (active) {
      selectedModelId.value = active.id
    } else if (!selectedModelId.value && models.value.length > 0) {
      selectedModelId.value = models.value[0].id
    }
  } catch (error) {
    errorMessage.value = '视觉模型获取失败'
    console.warn('Model fetch failed', error)
  } finally {
    loading.value.model = false
  }
}

// 拉取报告列表
const fetchReports = async () => {
  loading.value.report = true
  try {
    const response = await pestApi.listReports()
    reports.value = response.data
  } catch (error) {
    errorMessage.value = '报告列表获取失败'
    console.warn('Report fetch failed', error)
  } finally {
    loading.value.report = false
  }
}

// 激活指定航线
const activateRoute = async (route: RouteItem) => {
  loading.value.route = true
  try {
    const response = await pestApi.activateRoute(route.id)
    routes.value = routes.value.map((item) =>
      item.id === response.data.id
        ? response.data
        : { ...item, status: item.status === 'running' ? 'idle' : item.status }
    )
    selectedRouteId.value = response.data.id
    emit('route-activated', response.data)
  } catch (error) {
    errorMessage.value = '航线载入失败'
    console.warn('Route activate failed', error)
  } finally {
    loading.value.route = false
  }
}

// 激活指定模型
const activateModel = async (model: VisionModelItem) => {
  loading.value.model = true
  try {
    const response = await pestApi.activateModel(model.id)
    models.value = models.value.map((item) =>
      item.id === response.data.id
        ? response.data
        : { ...item, status: 'standby' }
    )
    selectedModelId.value = response.data.id
    emit('model-activated', response.data)
  } catch (error) {
    errorMessage.value = '模型切换失败'
    console.warn('Model activate failed', error)
  } finally {
    loading.value.model = false
  }
}

// 创建巡检任务
const createMission = async () => {
  if (!selectedRouteId.value || !selectedModelId.value) {
    errorMessage.value = '请先选择航线和模型'
    return
  }

  loading.value.mission = true
  errorMessage.value = null

  try {
    const response = await pestApi.createMission({
      route_id: selectedRouteId.value,
      model_id: selectedModelId.value
    })
    missionResult.value = response.data
    const route = routes.value.find((item) => item.id === selectedRouteId.value) || null
    const model = models.value.find((item) => item.id === selectedModelId.value) || null
    emit('mission-created', response.data, route, model)
  } catch (error) {
    errorMessage.value = '任务创建失败'
    console.warn('Mission create failed', error)
  } finally {
    loading.value.mission = false
  }
}

// 打开报告下载链接
const downloadReport = (report: ReportItem) => {
  const url = pestApi.buildReportDownloadUrl(report.id)
  window.open(url, '_blank')
}
</script>

<template>
  <div class="h-full flex flex-col relative">
    
    <div class="flex items-center justify-between mb-5 shrink-0 px-1">
      <div class="flex items-center gap-3">
        <div class="p-1.5 bg-rose-50 rounded-lg border border-rose-100/50 shadow-sm">
          <Layers :size="16" class="text-rose-600" />
        </div>
        <h3 class="font-bold text-slate-800 text-sm tracking-wide">功能</h3>
      </div>
    </div>

    <div class="flex-1 flex flex-col gap-3.5 overflow-y-auto pr-1 pb-2 custom-scrollbar">

    <button @click="openModal('route')" class="w-full group bg-white border border-slate-100 p-4 rounded-2xl flex items-center justify-between transition-all duration-300 hover:border-rose-200 hover:shadow-lg hover:shadow-rose-500/5 hover:-translate-y-0.5">
      <div class="flex items-center gap-3.5">
        <div class="p-2.5 bg-slate-50 text-slate-500 rounded-xl group-hover:bg-rose-50 group-hover:text-rose-600 transition-colors">
          <Map :size="20" />
        </div>
        <span class="text-sm font-bold text-slate-700 group-hover:text-rose-600 transition-colors">航线选择</span>
      </div>
      <ChevronRight :size="18" class="text-slate-300 group-hover:text-rose-400 group-hover:translate-x-0.5 transition-all" />
    </button>

    <button @click="openModal('model')" class="w-full group bg-white border border-slate-100 p-4 rounded-2xl flex items-center justify-between transition-all duration-300 hover:border-purple-200 hover:shadow-lg hover:shadow-purple-500/5 hover:-translate-y-0.5">
      <div class="flex items-center gap-3.5">
        <div class="p-2.5 bg-slate-50 text-slate-500 rounded-xl group-hover:bg-purple-50 group-hover:text-purple-600 transition-colors">
          <Scan :size="20" />
        </div>
        <span class="text-sm font-bold text-slate-700 group-hover:text-purple-600 transition-colors">视觉模型切换</span>
      </div>
      <ChevronRight :size="18" class="text-slate-300 group-hover:text-purple-400 group-hover:translate-x-0.5 transition-all" />
    </button>

    <button @click="openModal('report')" class="w-full group bg-white border border-slate-100 p-4 rounded-2xl flex items-center justify-between transition-all duration-300 hover:border-rose-200 hover:shadow-lg hover:shadow-rose-500/5 hover:-translate-y-0.5">
      <div class="flex items-center gap-3.5">
        <div class="p-2.5 bg-slate-50 text-slate-500 rounded-xl group-hover:bg-rose-50 group-hover:text-rose-600 transition-colors">
          <FileClock :size="20" />
        </div>
        <span class="text-sm font-bold text-slate-700 group-hover:text-rose-600 transition-colors">历史巡检报告</span>
      </div>
      <ChevronRight :size="18" class="text-slate-300 group-hover:text-rose-400 group-hover:translate-x-0.5 transition-all" />
    </button>

    </div>

    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="activeModal" class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/30 p-3 backdrop-blur-sm sm:p-4">
          
          <div class="flex max-h-[calc(100dvh-24px)] w-full max-w-[540px] scale-100 transform flex-col overflow-hidden rounded-2xl border border-white/80 bg-white shadow-2xl transition-all duration-300 sm:max-h-[calc(100dvh-32px)] sm:rounded-[2rem]">
            
            <div class="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 px-4 py-4 sm:px-6">
              <div class="flex items-center gap-2">
                <div class="w-1 h-3 bg-rose-500 rounded-full"></div>
                <h2 class="text-sm font-bold text-slate-800">
                  <span v-if="activeModal === 'route'">航线规划</span>
                  <span v-else-if="activeModal === 'model'">视觉模型</span>
                  <span v-else-if="activeModal === 'report'">报告生成与导出</span>
                </h2>
              </div>
              <button @click="activeModal = null" class="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-xl transition-colors">
                <X :size="18" />
              </button>
            </div>

            <div class="min-h-0 flex-1 overflow-y-auto bg-slate-50/30 p-4 sm:min-h-[300px] sm:max-h-[60vh] sm:p-6">
              <div v-if="errorMessage" class="mb-4 text-xs text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-3 py-2">
                {{ errorMessage }}
              </div>
              
              <div v-if="activeModal === 'route'" class="flex flex-col gap-3">
                <div v-if="loading.route" class="text-xs text-slate-400">航线加载中...</div>
                <div v-else-if="routes.length === 0" class="text-xs text-slate-400">暂无航线数据</div>
                <div
                  v-else
                  v-for="route in routes"
                  :key="route.id"
                  class="bg-white border p-4 rounded-xl shadow-sm flex justify-between items-center transition-all"
                  :class="route.id === selectedRouteId ? 'border-rose-400 shadow-rose-500/10' : 'border-slate-200'"
                  @click="selectedRouteId = route.id"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg" :class="route.id === selectedRouteId ? 'bg-rose-50 text-rose-600' : 'bg-slate-50 text-slate-500'">
                      <MapPin :size="16"/>
                    </div>
                    <div class="flex flex-col">
                      <span class="text-sm font-bold text-slate-800">{{ route.name }}</span>
                      <span class="text-[10px] text-slate-400 mt-1">
                        航点: {{ route.waypoints }} | 预估飞行时长: {{ route.duration_min }}min
                        <span v-if="route.area_mu"> | 覆盖面积: {{ route.area_mu }}亩</span>
                      </span>
                    </div>
                  </div>
                  <button
                    class="px-4 py-1.5 text-xs font-bold rounded-lg shadow-md relative z-10 flex items-center gap-1 transition-colors"
                    :class="route.status === 'running' ? 'bg-rose-500 text-white shadow-rose-500/20' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
                    :disabled="loading.route || route.status === 'running'"
                    @click.stop="activateRoute(route)"
                  >
                    <Activity v-if="route.status === 'running'" :size="12"/>
                    <Play v-else :size="12"/>
                    {{ route.status === 'running' ? '运行中' : '载入' }}
                  </button>
                </div>
              </div>
              
              <div v-else-if="activeModal === 'model'" class="flex flex-col gap-3">
                <div v-if="loading.model" class="text-xs text-slate-400">模型加载中...</div>
                <div v-else-if="models.length === 0" class="text-xs text-slate-400">暂无模型数据</div>
                <div
                  v-else
                  v-for="model in models"
                  :key="model.id"
                  class="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex justify-between items-center"
                  :class="model.id === selectedModelId ? 'border-purple-300' : ''"
                  @click="selectedModelId = model.id"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg" :class="model.id === selectedModelId ? 'bg-purple-50 text-purple-600' : 'bg-slate-50 text-slate-500'">
                      <Scan v-if="model.runtime === 'edge'" :size="16"/>
                      <Cpu v-else :size="16"/>
                    </div>
                    <div class="flex flex-col">
                      <span class="text-sm font-bold text-slate-800">{{ model.name }}</span>
                      <span class="text-[10px] text-slate-400 mt-1 font-mono">
                        算力载体: {{ model.runtime === 'edge' ? '端侧' : '云端' }}
                      </span>
                    </div>
                  </div>
                  <button
                    class="flex items-center gap-1.5 px-2.5 py-1 rounded border text-[10px] font-bold uppercase"
                    :class="model.status === 'active' ? 'bg-emerald-50 border-emerald-100 text-emerald-600' : 'bg-slate-100 border-slate-200 text-slate-500'"
                    :disabled="loading.model || model.status === 'active'"
                    @click.stop="activateModel(model)"
                  >
                    <span class="w-1.5 h-1.5 rounded-full" :class="model.status === 'active' ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'"></span>
                    {{ model.status === 'active' ? 'Active' : 'Standby' }}
                  </button>
                </div>
              </div>
              
              <div v-else-if="activeModal === 'report'" class="flex flex-col gap-3">
                <div v-if="loading.report" class="text-xs text-slate-400">报告加载中...</div>
                <div v-else-if="reports.length === 0" class="text-xs text-slate-400">暂无报告</div>
                <div
                  v-for="report in reports"
                  :key="report.id"
                  class="bg-white border border-slate-200 p-4 rounded-xl shadow-sm flex justify-between items-center group"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 bg-rose-50 text-rose-500 rounded-lg group-hover:bg-rose-500 group-hover:text-white transition-colors">
                      <FileText :size="16"/>
                    </div>
                    <div class="flex flex-col">
                      <span class="text-sm font-bold text-slate-800">{{ report.title }}</span>
                      <span class="text-[10px] text-slate-400 mt-1">
                        生成时间: {{ report.generated_at }} | 格式: {{ report.format.toUpperCase() }}
                        <span v-if="report.attachment_count"> | 包含 {{ report.attachment_count }} 张异常抓拍</span>
                      </span>
                    </div>
                  </div>
                  <button
                    class="w-8 h-8 flex items-center justify-center text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
                    @click="downloadReport(report)"
                  >
                    <Download :size="16"/>
                  </button>
                </div>
              </div>

            </div>

            <div class="flex flex-col items-stretch justify-between gap-3 border-t border-slate-100 bg-white px-4 py-4 sm:flex-row sm:items-center sm:px-6">
              <div class="text-xs text-slate-500">
                <span v-if="errorMessage" class="text-rose-500">{{ errorMessage }}</span>
                <span v-else-if="missionResult" class="text-emerald-600">任务已创建：{{ missionResult.name || missionResult.id }}</span>
                <span v-else>请选择航线与模型后创建任务</span>
              </div>
              <div class="grid grid-cols-2 items-center gap-3 sm:flex">
                <button @click="activeModal = null" class="px-5 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 bg-slate-50 border border-slate-200 rounded-xl transition-colors active:scale-95">关闭窗口</button>
                <button
                  class="px-5 py-2 text-xs font-bold text-white bg-rose-500 hover:bg-rose-600 rounded-xl shadow-md shadow-rose-500/20 transition-all active:scale-95"
                  :disabled="loading.mission"
                  @click="createMission"
                >
                  {{ loading.mission ? '创建中...' : '新建任务' }}
                </button>
              </div>
            </div>
          </div>

        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { display: none; }
.custom-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
.modal-fade-enter-from .bg-white {
  transform: scale(0.95) translateY(10px);
}
</style>
