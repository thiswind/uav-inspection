<template>
  <div class="min-h-screen w-full bg-slate-50 relative text-slate-800 flex flex-col font-sans overflow-x-hidden lg:h-screen lg:overflow-hidden">
    <!-- 背景装饰 -->
    <div class="absolute top-[-10%] right-[-5%] w-[40%] h-[40%] bg-cyan-300/20 rounded-full blur-[120px] pointer-events-none"></div>
    <div class="absolute bottom-[-10%] left-[-5%] w-[40%] h-[40%] bg-sky-300/20 rounded-full blur-[120px] pointer-events-none"></div>
    <div class="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgwLCAwLCAwLCAwLjAyKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] pointer-events-none z-0"></div>
    
    <div class="z-20 px-4 pt-4 md:px-6">
      <InspectionHeader title="热力客流监测" :task-name="currentTaskName">
        <template #actions>
        <TaskSelector 
          :tasks="taskList" 
          v-model="activeTaskId" 
          :busy-task-id="taskActionBusyId"
          @change="handleTaskChange" 
          @rename="handleTaskRename"
          @delete="handleTaskDelete"
        />
          <button class="border border-violet-200 bg-violet-50 text-sm font-medium text-violet-700" @click="isPredictModalVisible = true">客流预测</button>
          <button class="border border-sky-200 bg-sky-50 text-sm font-medium text-sky-700" @click="isUploadModalVisible = true">新建任务</button>
          <button class="border border-slate-200 bg-white text-sm font-medium text-slate-700" :disabled="!activeTaskId" @click="isExportModalVisible = true">导出报告</button>
        </template>
      </InspectionHeader>
    </div>

    <FloatingNotice :message="noticeMessage" :tone="noticeTone" :duration="3500" centered />

    <main class="z-10 flex flex-1 flex-col gap-6 overflow-visible p-4 md:p-6 lg:flex-row lg:overflow-hidden">
      <!-- 左侧边栏 -->
      <aside class="order-2 flex w-full flex-col gap-6 lg:order-none lg:w-[16%] lg:min-w-[180px]">
        <CounterBoard
          title="当前视野总人数"
          :value="currentHeadcount"
          :trend="headcountTrend"
          :alertLevel="counterAlertLevel"
          class="bg-white/70 backdrop-blur-xl border border-white shadow-[0_8px_40px_-12px_rgba(14,165,233,0.15)] rounded-2xl"
        />
        <!-- 无人机遥测信息面板 -->
        <div class="bg-white/70 backdrop-blur-xl border border-white shadow-[0_8px_40px_-12px_rgba(14,165,233,0.15)] rounded-2xl p-4 flex flex-col gap-3">
          <div class="flex items-center gap-2 text-slate-700 font-semibold text-sm">
            <svg class="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
            无人机状态
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="bg-slate-50 rounded-lg p-2 border border-slate-100">
              <div class="text-slate-400 mb-0.5">飞行高度</div>
              <div class="text-slate-700 font-mono font-semibold">{{ videoGIS.currentTelemetry.value?.altitude?.toFixed(1) || '--' }} <span class="text-slate-400 font-normal">m</span></div>
            </div>
            <div class="bg-slate-50 rounded-lg p-2 border border-slate-100">
              <div class="text-slate-400 mb-0.5">俯仰角</div>
              <div class="text-slate-700 font-mono font-semibold">{{ videoGIS.currentTelemetry.value?.pitch?.toFixed(1) || '--' }}<span class="text-slate-400 font-normal">°</span></div>
            </div>
            <div class="bg-slate-50 rounded-lg p-2 border border-slate-100">
              <div class="text-slate-400 mb-0.5">偏航角</div>
              <div class="text-slate-700 font-mono font-semibold">{{ videoGIS.currentTelemetry.value?.yaw?.toFixed(1) || '--' }}<span class="text-slate-400 font-normal">°</span></div>
            </div>
            <div class="bg-slate-50 rounded-lg p-2 border border-slate-100">
              <div class="text-slate-400 mb-0.5">横滚角</div>
              <div class="text-slate-700 font-mono font-semibold">{{ videoGIS.currentTelemetry.value?.roll?.toFixed(1) || '--' }}<span class="text-slate-400 font-normal">°</span></div>
            </div>
            <div class="bg-slate-50 rounded-lg p-2 border border-slate-100">
              <div class="text-slate-400 mb-0.5">纬度 LAT</div>
              <div class="text-slate-700 font-mono font-semibold">{{ videoGIS.currentTelemetry.value?.latitude?.toFixed(6) || '--' }}</div>
            </div>
            <div class="bg-slate-50 rounded-lg p-2 border border-slate-100">
              <div class="text-slate-400 mb-0.5">经度 LON</div>
              <div class="text-slate-700 font-mono font-semibold">{{ videoGIS.currentTelemetry.value?.longitude?.toFixed(6) || '--' }}</div>
            </div>
          </div>
        </div>

        <!-- 预警规则面板 -->
        <AlertRulePanel
          v-model:rules="alertRules"
          :currentCount="currentHeadcount"
          :alertLevel="alertState.level"
        />

      </aside>

      <section class="order-1 flex min-w-0 flex-1 flex-col gap-6 lg:order-none">
        <div class="flex min-h-0 flex-1 flex-col gap-6 lg:flex-row">
          
          <div class="relative flex min-h-[520px] w-full flex-col overflow-hidden rounded-lg border border-slate-700/50 bg-slate-900 shadow-[0_12px_40px_-12px_rgba(0,0,0,0.3)] lg:min-h-0 lg:w-1/2">
            <div class="pointer-events-none absolute left-4 top-14 z-30 flex flex-col gap-2">
              <div class="bg-black/50 backdrop-blur-md border border-cyan-500/30 text-cyan-400 text-xs font-mono px-3 py-1.5 rounded-lg shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                FRAME <span class="text-white ml-2">{{ videoGIS.currentFrameId.value || 0 }}</span>
              </div>
              <div class="bg-black/50 backdrop-blur-md border border-cyan-500/30 text-cyan-400 text-xs font-mono px-3 py-1.5 rounded-lg shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                FPS <span class="text-white ml-2">{{ videoFps }}</span>
              </div>
            </div>
            
            <div class="flex-1 relative bg-black">
               <VideoPlayer 
                  ref="videoPlayerRef"
                  :videoUrl="currentVideoUrl" 
                  :targets="frozenTargets"
                  @play="handlePlayState(true)"
                  @pause="handlePlayState(false)"
                />
            </div>
          </div>

          <div class="relative min-h-[520px] w-full overflow-hidden rounded-lg border border-white bg-white/70 p-1.5 shadow-[0_8px_30px_-12px_rgba(14,165,233,0.15)] backdrop-blur-xl lg:min-h-0 lg:w-1/2">
            <div class="w-full h-full rounded-xl overflow-hidden bg-slate-100 relative">
              <div class="absolute top-3 right-3 z-[400] bg-white/90 backdrop-blur border border-slate-200 rounded-lg shadow-sm px-3 py-2 flex flex-col gap-2 text-xs font-medium text-slate-600">
                <div
                  v-if="preloadStatus !== 'idle'"
                  class="min-w-36 rounded-md border px-2.5 py-2"
                  :class="preloadStatusClass"
                >
                  <div class="flex items-center justify-between gap-3">
                    <span class="inline-flex items-center gap-1.5">
                      <span
                        class="h-2 w-2 rounded-full"
                        :class="preloadStatus === 'loading' ? 'bg-sky-500 animate-pulse' : preloadStatus === 'completed' ? 'bg-emerald-500' : 'bg-red-500'"
                      ></span>
                      {{ preloadStatusText }}
                    </span>
                    <span class="font-mono">{{ preloadProgress }}%</span>
                  </div>
                  <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-white/70">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="preloadStatus === 'failed' ? 'bg-red-500' : preloadStatus === 'completed' ? 'bg-emerald-500' : 'bg-sky-500'"
                      :style="{ width: `${preloadProgress}%` }"
                    ></div>
                  </div>
                </div>
                <label class="flex items-center gap-2 cursor-pointer hover:text-cyan-600 transition-colors"><input type="checkbox" v-model="isFollowMode" class="accent-cyan-500 w-3.5 h-3.5"> 地图视角跟随</label>
                <label class="flex items-center gap-2 cursor-pointer hover:text-cyan-600 transition-colors"><input type="checkbox" v-model="showBaseLayer" class="accent-cyan-500 w-3.5 h-3.5"> 卫星影像底图</label>
                <label class="flex items-center gap-2 cursor-pointer hover:text-cyan-600 transition-colors"><input type="checkbox" v-model="showHeatLayer" class="accent-cyan-500 w-3.5 h-3.5"> 客流热力图层</label>
              </div>
              <HeatMapView
                :targets="heatmapTargets"
                :center="mapCenter"
                :zoom="mapZoom"
                :showBaseLayer="showBaseLayer"
                :showHeatLayer="showHeatLayer"
              />
            </div>
          </div>
        </div>
      </section>
    </main>

    <UploadModal 
      v-model:visible="isUploadModalVisible" 
      @submit-success="handleUploadSuccess" 
    />
    <ExportModal
      v-model:visible="isExportModalVisible"
      @confirm="handleExportConfirm"
    />
    <PredictModal
      v-model:visible="isPredictModalVisible"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';

// --- 1. 导入组件 ---
import TaskSelector from '../components/heatmap/TopBar/TaskSelector.vue';
import UploadModal from '../components/heatmap/TopBar/UploadModal.vue';
import ExportModal from '../components/heatmap/TopBar/ExportModal.vue';
import PredictModal from '../components/heatmap/PredictModal.vue';
import CounterBoard from '../components/heatmap/Statistics/CounterBoard.vue';
import VideoPlayer from '../components/heatmap/Visual/VideoPlayer.vue';
import HeatMapView from '../components/heatmap/Visual/HeatMapView.vue';
import AlertRulePanel from '../components/heatmap/Alert/AlertRulePanel.vue';
import InspectionHeader from '../components/common/InspectionHeader.vue';
import FloatingNotice from '../components/common/FloatingNotice.vue';

// --- 2. 导入 Hooks 与类型 ---
import { useVideoGISLink } from '../hooks/useVideoGISLink';
import { useTaskSync } from '../hooks/useTaskSync';
import type { PatrolTask, TelemetryFrame, TrackTarget, AlertRule, AlertState, WSFrameMessage } from '../types/patrol';
import { deleteTask, exportTaskReport, getTaskList, getTaskResult, renameTask } from '../api1/heatmap/task';
import { useInferenceSocket } from '../hooks/useWebSocket';

const inferenceSocket = useInferenceSocket();

// --- 3. 组件引用 ---
const videoPlayerRef = ref<InstanceType<typeof VideoPlayer> | null>(null);
const isLiveMode = ref(false);
const isDetectionPaused = ref(false);

// 暂停检测时冻结的目标数据
const frozenTargets = computed(() => {
  if (isDetectionPaused.value) {
    return lastTargets;
  }
  return videoGIS.currentTargets.value;
});
let lastTargets: TrackTarget[] = [];

// 处理播放/暂停
const handlePlayState = (state: boolean) => {
  if (state) {
    videoGIS.startSync();
  }
};

// --- 4. 业务状态初始化 ---
const isUploadModalVisible = ref(false);
const isExportModalVisible = ref(false);
const isPredictModalVisible = ref(false);
const taskList = ref<PatrolTask[]>([]);
const activeTaskId = ref<string | null>(null);
const taskActionBusyId = ref<string | null>(null);
const currentTaskName = computed(() => taskList.value.find(task => task.taskId === activeTaskId.value)?.taskName || '尚未选择任务');
const noticeMessage = ref('请选择或新建一个客流检测任务。');
const noticeTone = ref<'info' | 'success' | 'warning' | 'error'>('info');
const isFollowMode = ref(true);
const showBaseLayer = ref(true);
const showHeatLayer = ref(true);

const currentVideoUrl = ref('');
const mapCenter = ref<[number, number]>([30.5594, 104.0657]);
const mapZoom = ref(18);
const videoFps = ref(30);

const currentHeadcount = ref(0);
const headcountTrend = ref(0);

type PreloadStatus = 'idle' | 'loading' | 'completed' | 'failed';
const preloadStatus = ref<PreloadStatus>('idle');
const preloadProgress = ref(0);

const preloadStatusText = computed(() => {
  switch (preloadStatus.value) {
    case 'loading':
      return '预加载中';
    case 'completed':
      return '预加载完成';
    case 'failed':
      return '预加载失败';
    default:
      return '等待预加载';
  }
});

const preloadStatusClass = computed(() => {
  switch (preloadStatus.value) {
    case 'loading':
      return 'border-sky-200 bg-sky-50/90 text-sky-700';
    case 'completed':
      return 'border-emerald-200 bg-emerald-50/90 text-emerald-700';
    case 'failed':
      return 'border-red-200 bg-red-50/90 text-red-700';
    default:
      return 'border-slate-200 bg-slate-50/90 text-slate-600';
  }
});

const setPreloadProgress = (value: number) => {
  preloadProgress.value = Math.min(100, Math.max(0, Math.round(value)));
};

const hasValidTelemetry = (telemetry: Partial<TelemetryFrame> | null | undefined): telemetry is TelemetryFrame => {
  return Number.isFinite(telemetry?.latitude) && Number.isFinite(telemetry?.longitude);
};

const cachePreloadFrame = (frameData: WSFrameMessage) => {
  if (!Number.isFinite(frameData.frameId)) return;
  if (Array.isArray(frameData.targets)) {
    trackingData.value[frameData.frameId] = frameData.targets;
  }
  if (frameData.fps) videoFps.value = frameData.fps;
  if (frameData.totalFrames) {
    setPreloadProgress(Math.max(preloadProgress.value, (frameData.frameId / frameData.totalFrames) * 100));
  }
};

const getCurrentVideoSize = () => {
  const exposed = (videoPlayerRef.value as any)?.videoElement;
  const videoEl: HTMLVideoElement | null = exposed?.value ?? exposed ?? null;
  return {
    width: videoEl?.videoWidth || 3840,
    height: videoEl?.videoHeight || 2160,
  };
};

const pixelToWgs84 = (
  bbox: TrackTarget['bbox'],
  telemetry: TelemetryFrame,
  imgWidth: number,
  imgHeight: number,
  hfovDeg = 80,
): [number, number] | null => {
  const lat = Number(telemetry.latitude);
  const lon = Number(telemetry.longitude);
  const alt = Number(telemetry.altitude);
  const pitchDeg = Number(telemetry.pitch ?? -90);
  const yawDeg = Number(telemetry.yaw ?? 0);
  const rollDeg = Number(telemetry.roll ?? 0);

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (alt <= 0 || imgWidth <= 0 || imgHeight <= 0) return [lat, lon];

  const xCenter = (bbox[0] + bbox[2]) / 2;
  const yCenter = (bbox[1] + bbox[3]) / 2;
  const hfov = (hfovDeg * Math.PI) / 180;
  const vfov = 2 * Math.atan(Math.tan(hfov / 2) * (imgHeight / imgWidth));
  const fx = (imgWidth / 2) / Math.tan(hfov / 2);
  const fy = (imgHeight / 2) / Math.tan(vfov / 2);

  const xCam = (xCenter - imgWidth / 2) / fx;
  const yCam = (yCenter - imgHeight / 2) / fy;
  const vBody = [1, xCam, yCam];

  const yaw = (yawDeg * Math.PI) / 180;
  const pitch = (pitchDeg * Math.PI) / 180;
  const roll = (rollDeg * Math.PI) / 180;

  const rRoll = [
    [1, 0, 0],
    [0, Math.cos(roll), -Math.sin(roll)],
    [0, Math.sin(roll), Math.cos(roll)],
  ];
  const rPitch = [
    [Math.cos(pitch), 0, Math.sin(pitch)],
    [0, 1, 0],
    [-Math.sin(pitch), 0, Math.cos(pitch)],
  ];
  const rYaw = [
    [Math.cos(yaw), -Math.sin(yaw), 0],
    [Math.sin(yaw), Math.cos(yaw), 0],
    [0, 0, 1],
  ];

  const matMul = (a: number[][], b: number[][]) => a.map((row) => (
    b[0].map((_, col) => row.reduce((sum, value, idx) => sum + value * b[idx][col], 0))
  ));
  const matVecMul = (m: number[][], v: number[]) => m.map((row) => row.reduce((sum, value, idx) => sum + value * v[idx], 0));

  const world = matVecMul(matMul(rYaw, matMul(rPitch, rRoll)), vBody);
  if (world[2] <= 0) return [lat, lon];

  const scale = alt / world[2];
  const north = world[0] * scale;
  const east = world[1] * scale;
  const metersPerDegLat = 111319.9;
  const metersPerDegLon = metersPerDegLat * Math.cos((lat * Math.PI) / 180) || 1;

  return [lat + north / metersPerDegLat, lon + east / metersPerDegLon];
};

// --- 预警相关 ---
const alertRules = ref<AlertRule[]>([
  { enabled: true, level: 'yellow', value: 50,  label: '黄色注意' },
  { enabled: true, level: 'orange', value: 100, label: '橙色警告' },
  { enabled: true, level: 'red',    value: 150, label: '红色危险' },
]);
const alertState = ref<AlertState>({ active: false, level: null, message: '' });
watch(() => alertState.value.message, (message) => {
  if (!message) return;
  noticeMessage.value = message;
  noticeTone.value = 'warning';
});
let alertCooldown = false; // 防止频繁触发

// 传给 CounterBoard 的当前预警级别（null 为正常）
const counterAlertLevel = computed(() => alertState.value.level);

// --- 5. 实例化 Hooks ---
const telemetryData = ref<TelemetryFrame[]>([]);
const trackingData = ref<Record<number, TrackTarget[]>>({});
const videoGIS = useVideoGISLink(videoPlayerRef as any, telemetryData, trackingData, videoFps, isDetectionPaused);
const taskSync = useTaskSync();

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '') || import.meta.env.BASE_URL.replace(/\/$/, '');

const heatmapTargets = computed<TrackTarget[]>(() => {
  const telemetry = videoGIS.currentTelemetry.value;
  if (!hasValidTelemetry(telemetry)) return frozenTargets.value;

  const { width, height } = getCurrentVideoSize();
  return frozenTargets.value.map((target) => {
    if (Number.isFinite(target.geoLat) && Number.isFinite(target.geoLon)) return target;

    const projected = pixelToWgs84(target.bbox, telemetry, width, height);
    if (!projected) return target;

    return {
      ...target,
      geoLat: projected[0],
      geoLon: projected[1],
    };
  });
});

// --- 6. 核心联动逻辑 ---
watch(videoGIS.currentTargets, (newTargets) => {
  // 暂停检测时不更新人数统计和地图中心
  if (isDetectionPaused.value) return;
  const newCount = newTargets.length;
  headcountTrend.value = newCount - currentHeadcount.value;
  currentHeadcount.value = newCount;

  const telemetry = videoGIS.currentTelemetry.value;
  if (hasValidTelemetry(telemetry) && isFollowMode.value) {
    mapCenter.value = [telemetry.latitude, telemetry.longitude];
  }
});

// --- 预警判断逻辑 ---
const evaluateAlert = (count: number) => {
  // 从高到低检查规则
  const levelOrder: Array<'red' | 'orange' | 'yellow'> = ['red', 'orange', 'yellow'];
  for (const level of levelOrder) {
    const rule = alertRules.value.find(r => r.level === level && r.enabled);
    if (rule && count >= rule.value) {
      return { active: true, level: level as AlertState['level'], message: `${rule.label}：当前 ${count} 人，超过阈值 ${rule.value} 人` };
    }
  }
  return { active: false, level: null, message: '' };
};

watch(currentHeadcount, (newCount) => {
  if (alertCooldown) return;
  const result = evaluateAlert(newCount);
  // 只在状态变化或首次触发时更新
  if (result.level !== alertState.value.level) {
    alertState.value = result;
    if (result.active) {
      // 触发后冷却 10 秒，避免重复
      alertCooldown = true;
      setTimeout(() => {
        alertCooldown = false;
        // 冷却结束后重新评估
        const reEval = evaluateAlert(currentHeadcount.value);
        if (!reEval.active) {
          alertState.value = reEval;
        }
      }, 10000);
    }
  }
});

const updateTaskListStatus = (taskId: string, status: PatrolTask['status'], progress: number) => {
  const index = taskList.value.findIndex(item => item.taskId === taskId);
  if (index >= 0) {
    taskList.value[index] = { ...taskList.value[index], status, progress };
  }
};

const loadHistoryData = async (taskId: string) => {
  try {
    const res = await getTaskResult(taskId);
    videoFps.value = res.fps || 30;
    telemetryData.value = res.telemetryData || [];
    trackingData.value = res.trackingData || {};

    const firstTelemetry = telemetryData.value[0] || null;
    if (firstTelemetry) {
      const initialFrameId = firstTelemetry.frameId || 0;
      videoGIS.currentFrameId.value = initialFrameId;
      videoGIS.currentTelemetry.value = firstTelemetry;
      videoGIS.currentTargets.value = trackingData.value[initialFrameId] || trackingData.value[initialFrameId + 1] || [];
      mapCenter.value = [firstTelemetry.latitude, firstTelemetry.longitude];
    } else {
      videoGIS.currentFrameId.value = 0;
      videoGIS.currentTelemetry.value = null;
      videoGIS.currentTargets.value = [];
    }
  } catch (error) {
    preloadStatus.value = 'failed';
    console.error('历史数据加载失败', error);
  }
};

const handleTaskChange = async (task: PatrolTask) => {
  if (!task) return;
  noticeMessage.value = `已加载任务：${task.taskName}`;
  noticeTone.value = 'success';
  taskSync.stopPolling();

  currentVideoUrl.value = resolveMediaUrl(task.videoUrl, task.taskId);
  inferenceSocket.disconnect(); 
  telemetryData.value = [];
  trackingData.value = {};
  currentHeadcount.value = 0;
  headcountTrend.value = 0;
  isDetectionPaused.value = false;
  lastTargets = [];
  isLiveMode.value = task.status === 'PROCESSING' || task.status === 'PENDING';
  videoGIS.currentFrameId.value = 0;
  videoGIS.currentTelemetry.value = null;
  videoGIS.currentTargets.value = [];
  preloadStatus.value = isLiveMode.value ? 'loading' : task.status === 'COMPLETED' ? 'completed' : 'idle';
  setPreloadProgress(task.status === 'COMPLETED' ? 100 : task.progress || 0);

  if (isLiveMode.value) {
    console.log('接入实时分析流...');
    
    inferenceSocket.connect(task.taskId, (frameData) => {
      cachePreloadFrame(frameData);
    });

    taskSync.startTaskPolling(task.taskId, async (statusData) => {
      updateTaskListStatus(statusData.taskId, statusData.status, statusData.progress);
      preloadStatus.value = statusData.status === 'FAILED'
        ? 'failed'
        : statusData.status === 'COMPLETED'
          ? 'completed'
          : 'loading';
      setPreloadProgress(statusData.status === 'COMPLETED' ? 100 : statusData.progress || preloadProgress.value);
      if (statusData.status === 'COMPLETED') {
        inferenceSocket.disconnect();
        isLiveMode.value = false;
        await loadHistoryData(task.taskId);
      }
      if (statusData.status === 'FAILED') {
        preloadStatus.value = 'failed';
        console.error('任务处理失败', statusData.error);
      }
    });
    
  } else if (task.status === 'COMPLETED') {
    preloadStatus.value = 'completed';
    setPreloadProgress(100);
    console.log('加载历史分析数据...');
    await loadHistoryData(task.taskId);
  }
};

const resetActiveTaskView = () => {
  taskSync.stopPolling();
  inferenceSocket.disconnect();

  const exposed = (videoPlayerRef.value as any)?.videoElement;
  const videoEl: HTMLVideoElement | null = exposed?.value ?? exposed ?? null;
  videoEl?.pause();

  activeTaskId.value = null;
  currentVideoUrl.value = '';
  telemetryData.value = [];
  trackingData.value = {};
  currentHeadcount.value = 0;
  headcountTrend.value = 0;
  isDetectionPaused.value = false;
  isLiveMode.value = false;
  lastTargets = [];
  videoGIS.currentFrameId.value = 0;
  videoGIS.currentTelemetry.value = null;
  videoGIS.currentTargets.value = [];
  preloadStatus.value = 'idle';
  setPreloadProgress(0);
  alertState.value = { active: false, level: null, message: '' };
};

const handleTaskRename = async ({ task, taskName }: { task: PatrolTask; taskName: string }) => {
  taskActionBusyId.value = task.taskId;
  try {
    const result = await renameTask(task.taskId, taskName);
    const index = taskList.value.findIndex(item => item.taskId === task.taskId);
    if (index >= 0) {
      taskList.value[index] = { ...taskList.value[index], taskName: result.taskName };
    }
    noticeMessage.value = `任务已重命名为：${result.taskName}`;
    noticeTone.value = 'success';
  } catch (error) {
    console.error('任务重命名失败', error);
    noticeMessage.value = '任务重命名失败，请稍后重试。';
    noticeTone.value = 'error';
  } finally {
    taskActionBusyId.value = null;
  }
};

const handleTaskDelete = async (task: PatrolTask) => {
  taskActionBusyId.value = task.taskId;
  try {
    await deleteTask(task.taskId);
    taskList.value = taskList.value.filter(item => item.taskId !== task.taskId);
    if (activeTaskId.value === task.taskId) resetActiveTaskView();
    noticeMessage.value = `任务已删除：${task.taskName}`;
    noticeTone.value = 'success';
  } catch (error) {
    console.error('任务删除失败', error);
    noticeMessage.value = '任务删除失败，请稍后重试。';
    noticeTone.value = 'error';
  } finally {
    taskActionBusyId.value = null;
  }
};

const handleUploadSuccess = async (taskId: any) => {
  // taskId 可能是字符串、对象或嵌套对象，统一提取
  const realTaskId = typeof taskId === 'string'
    ? taskId
    : taskId?.data?.taskId || taskId?.taskId || '';

  if (!realTaskId) {
    console.error('上传成功但未获取到 taskId', taskId);
    noticeMessage.value = '任务已上传，但未能读取任务编号。';
    noticeTone.value = 'error';
    return;
  }

  // 刷新任务列表并自动切换到新任务（进入实时分析模式）
  const res = await getTaskList();
  taskList.value = res;
  activeTaskId.value = realTaskId;
  const task = res.find(item => item.taskId === realTaskId) || {
    taskId: realTaskId,
    taskName: '最新分析任务',
    status: 'PROCESSING',
    uploadTime: new Date().toLocaleString('zh-CN'),
  };
  handleTaskChange(task as PatrolTask);
  noticeMessage.value = `任务创建成功：${task.taskName}`;
  noticeTone.value = 'success';
};

const handleExportConfirm = async (options: { includeMinute: boolean; includeAlerts: boolean }) => {
  if (!activeTaskId.value) return;
  try {
    const blob = await exportTaskReport(activeTaskId.value, options);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `巡检报告_${activeTaskId.value}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    noticeMessage.value = '巡检报告已导出。';
    noticeTone.value = 'success';
  } catch (error) {
    console.error('导出失败', error);
    noticeMessage.value = '报告导出失败，请稍后重试。';
    noticeTone.value = 'error';
  }
};

onMounted(async () => {
  try {
    const res = await getTaskList();
    taskList.value = res; 
  } catch (error) {
    console.error('获取任务列表失败', error);
  }
});

const resolveMediaUrl = (videoUrl?: string, taskId?: string) => {
  if (videoUrl && videoUrl.startsWith('http')) return videoUrl;
  if (videoUrl && apiBase && videoUrl.startsWith(apiBase)) return videoUrl; // 后端已带部署前缀
  if (videoUrl) return `${apiBase}${videoUrl}`;
  if (taskId) return `${apiBase}/api/v1/media/${taskId}.mp4`;
  return '';
};

onUnmounted(() => {
  inferenceSocket.disconnect();
  taskSync.stopPolling();
  console.log('组件卸载：已清理 WebSocket 连接与全局状态');
});
</script>

<style scoped>
</style>
