<template>
  <div class="mobile-page min-h-screen w-full bg-slate-50 relative text-slate-800 flex flex-col font-sans overflow-x-hidden lg:h-screen lg:overflow-hidden">
    <div class="absolute top-[-10%] right-[-5%] w-[40%] h-[40%] bg-pink-300/20 rounded-full blur-[120px] pointer-events-none"></div>
    <div class="absolute bottom-[-10%] left-[-5%] w-[40%] h-[40%] bg-rose-300/20 rounded-full blur-[120px] pointer-events-none"></div>

    <div class="z-20 px-4 pt-4 md:px-6">
      <InspectionHeader title="玫瑰花产量预测" :task-name="currentTaskName" :online="backendOnline">
        <template #actions>
          <button class="border border-pink-200 bg-pink-50 text-sm font-medium text-pink-700" @click="showTaskModal = true">上传任务</button>
          <button class="border border-sky-200 bg-sky-50 text-sm font-medium text-sky-700" @click="showTaskList = true">加载任务</button>
          <button class="border border-violet-200 bg-violet-50 text-sm font-medium text-violet-700" @click="showYieldModal = true">产量预测</button>
          <button class="border border-slate-200 bg-white text-sm font-medium text-slate-700" @click="showParkModal = true">园区概况</button>
          <span class="px-2 font-mono text-sm text-slate-500">{{ currentTime }}</span>
        </template>
      </InspectionHeader>
    </div>

    <FloatingNotice :message="noticeMessage" :tone="noticeTone" :duration="3500" centered />

    <main class="z-10 flex min-h-0 flex-1 flex-col gap-4 overflow-visible p-4 lg:flex-row lg:overflow-hidden">

      <!-- ========== 左侧：无人机状态 + 检测统计 ========== -->
      <aside class="order-2 flex w-full flex-col gap-3 overflow-visible lg:order-none lg:w-[22%] lg:min-w-[200px] lg:overflow-y-auto">
        <!-- 无人机状态 -->
        <div class="bg-white/80 backdrop-blur border border-white shadow-sm rounded-2xl p-4 shrink-0">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2 text-slate-700 font-semibold text-sm">
              <svg class="w-4 h-4 text-pink-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <circle cx="12" cy="12" r="2"/><path d="M5 5l2.5 2.5M16.5 7.5L19 5M5 19l2.5-2.5M16.5 16.5L19 19"/><path d="M3 5a2 2 0 012-2h1a2 2 0 012 2v1a2 2 0 01-2 2H5a2 2 0 01-2-2V5zM16 5a2 2 0 012-2h1a2 2 0 012 2v1a2 2 0 01-2 2h-1a2 2 0 01-2-2V5zM3 18a2 2 0 012-2h1a2 2 0 012 2v1a2 2 0 01-2 2H5a2 2 0 01-2-2v-1zM16 18a2 2 0 012-2h1a2 2 0 012 2v1a2 2 0 01-2 2h-1a2 2 0 01-2-2v-1z"/>
              </svg>
              无人机状态 (SRT实时)
            </div>
            <span v-if="srtFrameCount > 0" class="rounded-full bg-pink-50 px-2 py-0.5 font-mono text-[11px] font-semibold text-pink-600">
              {{ srtUpdateCount }}/{{ srtFrameCount }}
            </span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="bg-slate-50 rounded-xl p-2.5 border border-slate-100">
              <div class="text-slate-400 mb-1">飞行高度</div>
              <div class="text-slate-700 font-mono font-bold">{{ uavInfo.relAlt.toFixed(1) }}<span class="text-slate-400 font-normal">m</span></div>
            </div>
            <div class="bg-slate-50 rounded-xl p-2.5 border border-slate-100">
              <div class="text-slate-400 mb-1">绝对高度</div>
              <div class="text-slate-700 font-mono font-bold">{{ uavInfo.absAlt.toFixed(1) }}<span class="text-slate-400 font-normal">m</span></div>
            </div>
            <div class="bg-slate-50 rounded-xl p-2.5 border border-slate-100">
              <div class="text-slate-400 mb-1">偏航角</div>
              <div class="text-sky-600 font-mono font-bold">{{ uavInfo.gbYaw.toFixed(1) }}<span class="text-slate-400 font-normal">°</span></div>
            </div>
            <div class="bg-slate-50 rounded-xl p-2.5 border border-slate-100">
              <div class="text-slate-400 mb-1">俯仰角</div>
              <div class="text-slate-700 font-mono font-bold">{{ uavInfo.gbPitch.toFixed(1) }}<span class="text-slate-400 font-normal">°</span></div>
            </div>
            <div class="bg-slate-50 rounded-xl p-2.5 border border-slate-100">
              <div class="text-slate-400 mb-1">ISO</div>
              <div class="text-slate-700 font-mono font-bold">{{ uavInfo.iso }}</div>
            </div>
            <div class="bg-slate-50 rounded-xl p-2.5 border border-slate-100">
              <div class="text-slate-400 mb-1">焦距</div>
              <div class="text-slate-700 font-mono font-bold">{{ uavInfo.focalLen }}<span class="text-slate-400 font-normal">mm</span></div>
            </div>
            <div class="bg-slate-50 rounded-xl p-2.5 border border-slate-100 col-span-2">
              <div class="text-slate-400 mb-1">GPS坐标</div>
              <div class="text-slate-600 font-mono text-[11px]">{{ uavInfo.lat.toFixed(6) }}, {{ uavInfo.lng.toFixed(6) }}</div>
            </div>
          </div>
        </div>

        <!-- 当前帧检测 -->
        <div class="bg-gradient-to-br from-pink-500/10 to-rose-500/5 border border-pink-200/50 shadow-sm rounded-2xl p-4 shrink-0">
          <div class="flex items-center gap-2 text-pink-600 text-sm font-semibold mb-2">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
            当前帧检测
          </div>
          <div class="text-4xl font-bold text-slate-800 mb-1">{{ currentFrameCount }}</div>
          <div class="text-xs text-slate-500">朵玫瑰花</div>
          <div class="mt-3 flex items-center gap-2 text-xs text-slate-500"><span>本次累计：</span><span class="text-pink-600 font-bold text-base">{{ totalDetectedCount }}</span><span>朵</span></div>
        </div>

        <!-- 品种分布 -->
        <div class="bg-white/80 backdrop-blur border border-white shadow-sm rounded-2xl p-4 shrink-0">
          <div class="flex items-center gap-2 text-slate-700 font-semibold text-sm mb-3">
            <svg class="w-4 h-4 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" /></svg>
            品种分布 (实时)
          </div>
          <div class="space-y-2.5">
            <div v-for="v in varietyStats" :key="v.name" class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full shrink-0" :style="{ background: v.color }"></span>
              <span class="text-xs text-slate-600 w-16 shrink-0">{{ v.name }}</span>
              <div class="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden"><div class="h-full rounded-full transition-all duration-700" :style="{ width: v.percent + '%', background: v.color }"></div></div>
              <span class="text-xs font-mono text-slate-600 w-8 text-right shrink-0">{{ v.count }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- ========== 区域1：中间视频+检测 ========== -->
      <section class="order-1 flex min-h-[440px] min-w-0 flex-1 flex-col gap-3 sm:min-h-[560px] lg:order-none lg:min-h-0">
        <div class="flex-1 bg-slate-900 rounded-2xl overflow-hidden relative shadow-lg min-h-0 flex flex-col">
          <div class="absolute top-14 left-3 right-3 z-20 flex items-start justify-between pointer-events-none">
            <div class="flex flex-col gap-1.5">
              <div class="bg-black/60 backdrop-blur border border-pink-500/30 text-pink-400 text-xs font-mono px-2.5 py-1 rounded-lg">FRAME <span class="text-white ml-1">{{ currentFrame }}</span></div>
              <div class="bg-black/60 backdrop-blur border border-pink-500/30 text-pink-400 text-xs font-mono px-2.5 py-1 rounded-lg">ALT <span class="text-white ml-1">{{ uavInfo.relAlt.toFixed(1) }}m</span></div>
            </div>
            <div class="flex flex-col items-end gap-1.5">
              <div class="bg-black/60 backdrop-blur border border-pink-500/30 text-pink-400 text-xs font-mono px-2.5 py-1 rounded-lg">{{ uavInfo.lat.toFixed(4) }}, {{ uavInfo.lng.toFixed(4) }}</div>
              <div v-if="isDetecting" class="bg-pink-500/80 backdrop-blur text-white text-xs font-bold px-2.5 py-1 rounded-lg flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>检测中</div>
            </div>
          </div>

          <DetectionVideoFrame
            class="flex-1 min-h-0"
            label="YOLO 玫瑰花实时检测"
            :status="!inferenceReady && backendOnline ? (isPlaying ? '仅播放 · AI 未启用' : '基础模式 · AI 未启用') : isDetecting ? '帧分析中' : isPlaying ? '实时播放' : '等待启动'"
            :playing="isPlaying"
            :disabled="!videoSrc"
            :current-time="videoCurrentTime"
            :duration="videoDurationSec"
            :empty="!videoSrc"
            empty-text="请上传任务或从历史任务中选择视频。"
            @toggle="togglePlay"
            @replay="replayVideo"
            @seek="seekVideo"
          >
            <video ref="videoRef" class="w-full h-full object-contain" :src="videoSrc" crossorigin="anonymous"
              @timeupdate="onTimeUpdate" @loadedmetadata="onLoadedMetadata"
              @play="onPlay" @pause="onPause" @ended="onPause"></video>
            <canvas ref="detectionCanvas" class="absolute inset-0 w-full h-full pointer-events-none"></canvas>
          </DetectionVideoFrame>
        </div>
      </section>

      <!-- ========== 右侧：园区概况 + 本次巡检 ========== -->
      <aside class="order-3 flex w-full max-w-none flex-col gap-3 overflow-visible lg:order-none lg:w-[18%] lg:min-w-[180px] lg:max-w-[220px] lg:overflow-y-auto">
        <!-- 园区概况按钮 -->
        <button
          @click="showParkModal = true"
          class="w-full bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white rounded-xl px-3 py-3 flex items-center gap-2 shadow-md shadow-pink-200 transition-all active:scale-[0.98] shrink-0 group"
        >
          <div class="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center shrink-0">
            <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" /></svg>
          </div>
          <div class="text-left flex-1">
            <div class="font-bold text-sm">园区概况</div>
            <div class="text-white/70 text-[11px] mt-0.5">共 3 块地 · 查看详情</div>
          </div>
          <svg class="w-4 h-4 text-white/60 group-hover:translate-x-0.5 transition-transform shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
        </button>

        <!-- 本次巡检 -->
        <div class="bg-white/80 backdrop-blur border border-white shadow-sm rounded-2xl p-4 shrink-0">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2 text-slate-700 font-semibold text-sm">
              <svg class="w-4 h-4 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>本次巡检
            </div>
            <button @click="showLogModal = true" class="flex items-center gap-1 px-2.5 py-1 bg-pink-50 hover:bg-pink-100 border border-pink-200 text-pink-600 text-xs font-medium rounded-lg cursor-pointer transition-all">
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>检测日志
              <span v-if="detectionLog.length > 0" class="ml-0.5 px-1 py-0.5 rounded-full bg-pink-500 text-white text-[10px] leading-none font-bold">{{ detectionLog.length }}</span>
            </button>
          </div>
          <div class="space-y-2 text-xs">
            <div class="flex items-center justify-between py-1 border-b border-slate-50"><span class="text-slate-400">视频时长</span><span class="font-mono text-slate-700">{{ videoDuration }}</span></div>
            <div class="flex items-center justify-between py-1 border-b border-slate-50"><span class="text-slate-400">已处理帧</span><span class="font-mono text-slate-700">{{ processedFrames }}</span></div>
            <div class="flex items-center justify-between py-1 border-b border-slate-50"><span class="text-slate-400">API延迟</span><span class="font-mono text-slate-700">{{ apiLatency }}ms</span></div>
            <div class="flex items-center justify-between py-1"><span class="text-slate-400">状态</span><span class="flex items-center gap-1 font-medium" :class="isDetecting ? 'text-pink-600' : 'text-slate-400'"><span v-if="isDetecting" class="w-1.5 h-1.5 rounded-full bg-pink-400 animate-pulse"></span>{{ isDetecting ? '检测中' : '待机' }}</span></div>
          </div>
        </div>

        <!-- 功能区按钮组 -->
        <div class="flex flex-col gap-2.5 shrink-0">
          <!-- 上传任务 - 暖色渐变 -->
          <button @click="showTaskModal = true" class="w-full bg-gradient-to-br from-pink-500 via-rose-500 to-rose-600 hover:from-pink-600 hover:via-rose-600 hover:to-rose-700 rounded-xl px-3 py-3 flex items-center gap-2 transition-all active:scale-[0.98] group shadow-md shadow-pink-300/40">
            <div class="w-8 h-8 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center shrink-0">
              <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
            </div>
            <div class="text-left flex-1">
              <div class="text-sm font-semibold text-white">上传任务</div>
              <div class="text-[11px] text-white/70 mt-0.5">视频 + SRT 字幕</div>
            </div>
            <svg class="w-4 h-4 text-white/60 group-hover:translate-x-0.5 transition-transform shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
          </button>

          <!-- 任务记录 - 海洋渐变 -->
          <button @click="showTaskList = true" class="w-full bg-gradient-to-r from-sky-600 via-blue-600 to-indigo-600 hover:from-sky-700 hover:via-blue-700 hover:to-indigo-700 rounded-xl px-3 py-3 flex items-center gap-2 transition-all active:scale-[0.98] group shadow-md shadow-blue-300/40">
            <div class="w-8 h-8 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center shrink-0">
              <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
            </div>
            <div class="text-left flex-1">
              <div class="text-sm font-semibold text-white">任务记录</div>
              <div class="text-[11px] text-white/70 mt-0.5">{{ taskRecords.length > 0 ? `${taskRecords.length} 条记录` : '暂无记录' }}</div>
            </div>
            <svg class="w-4 h-4 text-white/60 group-hover:translate-x-0.5 transition-transform shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
          </button>

          <!-- 产量预测 - 紫晶渐变 -->
          <button @click="showYieldModal = true" class="w-full bg-gradient-to-r from-purple-600 via-violet-600 to-fuchsia-600 hover:from-purple-700 hover:via-violet-700 hover:to-fuchsia-700 rounded-xl px-3 py-3 flex items-center gap-2 transition-all active:scale-[0.98] group shadow-md shadow-purple-300/40">
            <div class="w-8 h-8 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center shrink-0">
              <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
            </div>
            <div class="text-left flex-1">
              <div class="text-sm font-semibold text-white">产量预算</div>
              <div class="text-[11px] text-white/70 mt-0.5">AI 智能预估</div>
            </div>
            <svg class="w-4 h-4 text-white/60 group-hover:translate-x-0.5 transition-transform shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
          </button>
        </div>
      </aside>

      <!-- 上传任务弹窗 -->
      <Teleport to="body">
        <Transition name="modal">
          <div v-if="showTaskModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showTaskModal = false"></div>
            <div class="relative w-full max-w-md bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col">
              <div class="bg-gradient-to-r from-pink-500 to-rose-500 px-6 py-4 flex items-center justify-between shrink-0">
                <h2 class="text-white font-bold text-base tracking-tight">上传巡检任务</h2>
                <button @click="showTaskModal = false" class="w-7 h-7 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center text-white transition-colors">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div class="p-6 space-y-4">
                <div>
                  <label class="block text-xs text-slate-500 mb-1.5">任务名称</label>
                  <input v-model="newTaskName" type="text" placeholder="例如：2026-05-20 一号地巡检" class="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-pink-300 focus:border-pink-300" />
                </div>
                <div>
                  <label class="block text-xs text-slate-500 mb-1.5">巡检视频</label>
                  <label class="flex items-center gap-2 px-3 py-2 bg-pink-50 border border-pink-200 text-pink-700 text-sm rounded-xl cursor-pointer hover:bg-pink-100 transition-all">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                    {{ newTaskVideoName || '选择视频文件' }}
                    <input type="file" accept="video/*" class="hidden" @change="onNewTaskVideoSelect" />
                  </label>
                </div>
                <div>
                  <label class="block text-xs text-slate-500 mb-1.5">SRT 字幕文件</label>
                  <label class="flex items-center gap-2 px-3 py-2 bg-sky-50 border border-sky-200 text-sky-700 text-sm rounded-xl cursor-pointer hover:bg-sky-100 transition-all">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    {{ newTaskSrtName || '选择 SRT 文件' }}
                    <input type="file" accept=".srt" class="hidden" @change="onNewTaskSrtSelect" />
                  </label>
                </div>
                <div class="flex gap-3 pt-2">
                  <button @click="showTaskModal = false" class="flex-1 py-2 bg-slate-100 text-slate-600 text-sm font-medium rounded-xl hover:bg-slate-200 transition-all">取消</button>
                  <button @click="confirmUploadTask" :disabled="!canUploadTask || uploading" class="flex-1 py-2 bg-gradient-to-r from-pink-500 to-rose-500 text-white text-sm font-medium rounded-xl hover:from-pink-600 hover:to-rose-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed">{{ uploading ? '上传中...' : '确认上传' }}</button>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- 任务记录弹窗 -->
      <Teleport to="body">
        <Transition name="modal">
          <div v-if="showTaskList" class="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showTaskList = false"></div>
            <div class="relative w-full max-w-lg bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
              <div class="bg-gradient-to-r from-sky-500 to-blue-500 px-6 py-4 flex items-center justify-between shrink-0">
                <h2 class="text-white font-bold text-base tracking-tight">任务记录</h2>
                <button @click="showTaskList = false" class="w-7 h-7 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center text-white transition-colors">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div class="flex-1 overflow-y-auto p-4 space-y-2">
                <div v-if="taskRecords.length === 0" class="text-center text-sm text-slate-400 py-8">暂无任务记录</div>
                <div v-for="(task, idx) in taskRecords" :key="task.id" class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-100 hover:border-pink-200 transition-all group">
                  <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-pink-400 to-rose-500 flex items-center justify-center text-white text-xs font-bold shrink-0">{{ idx + 1 }}</div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-semibold text-slate-700 truncate">{{ task.name }}</div>
                    <div class="text-xs text-slate-400 mt-0.5">{{ task.videoName }} + {{ task.srtName }}</div>
                    <div class="text-[10px] text-slate-300 mt-0.5">{{ task.createdAt }}</div>
                  </div>
                  <button @click="loadTask(task)" class="px-3 py-1.5 bg-pink-500 text-white text-xs font-medium rounded-lg hover:bg-pink-600 transition-all shrink-0">加载</button>
                  <button @click="deleteTask(task.id)" class="w-7 h-7 flex items-center justify-center text-slate-300 hover:text-rose-500 transition-colors shrink-0">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>

      <!-- 园区概况弹窗 -->
      <Teleport to="body">
        <Transition name="modal">
          <div v-if="showParkModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showParkModal = false"></div>
            <div class="relative w-full max-w-4xl bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
              <div class="bg-gradient-to-r from-pink-500 to-rose-500 px-6 py-5 flex items-center justify-between shrink-0">
                <div>
                  <h2 class="text-white font-bold text-lg tracking-tight"> 云南大马士革玫瑰园</h2>
                  <p class="text-white/70 text-xs mt-0.5">园区分区概况  共 3 块种植地</p>
                </div>
                <button @click="showParkModal = false" class="w-8 h-8 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center text-white transition-colors">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <div class="flex gap-2 px-6 pt-4 shrink-0">
                <button
                  v-for="(plot, idx) in parkPlots"
                  :key="idx"
                  @click="activePlotIndex = idx"
                  class="flex-1 py-2 rounded-xl text-sm font-semibold transition-all border"
                  :class="activePlotIndex === idx
                    ? 'bg-gradient-to-r from-pink-500 to-rose-500 text-white border-transparent shadow-md shadow-pink-200'
                    : 'bg-slate-50 text-slate-500 border-slate-200 hover:border-pink-300 hover:text-pink-600'"
                >{{ plot.name }}</button>
              </div>
              <div class="flex-1 px-6 pb-6 pt-4 overflow-y-auto">
                <div v-if="parkPlots[activePlotIndex]" class="flex flex-col gap-4">
                  <div class="w-full h-72 rounded-2xl overflow-hidden bg-slate-100 relative shadow-sm">
                    <img
                      v-if="!missingPlotImages[activePlotIndex]"
                      :key="activePlotIndex"
                      :src="parkPlots[activePlotIndex].img"
                      :alt="parkPlots[activePlotIndex].name"
                      class="w-full h-full object-cover"
                      @error="missingPlotImages[activePlotIndex] = true"
                    />
                    <div v-else class="flex h-full items-center justify-center px-8 text-center text-sm leading-6 text-slate-500">未安装此地块的照片。照片属于可选数据包，不影响页面和任务功能。</div>
                    <div class="absolute top-3 left-3 bg-black/50 backdrop-blur text-white text-xs font-bold px-3 py-1 rounded-full">
                      {{ parkPlots[activePlotIndex].name }}
                    </div>
                    <div class="absolute bottom-3 right-3 bg-pink-500/80 text-white text-xs px-2.5 py-1 rounded-full font-medium">
                      {{ parkPlots[activePlotIndex].status }}
                    </div>
                  </div>
                  <div class="grid grid-cols-3 gap-3">
                    <div v-for="stat in parkPlots[activePlotIndex].stats" :key="stat.label"
                      class="bg-gradient-to-br from-pink-50 to-rose-50 rounded-2xl p-3 border border-pink-100 text-center">
                      <div class="text-lg font-extrabold text-rose-600">{{ stat.value }}</div>
                      <div class="text-xs text-slate-500 mt-0.5">{{ stat.label }}</div>
                    </div>
                  </div>
                  <div class="bg-slate-50 rounded-2xl p-4 space-y-2.5 border border-slate-100">
                    <div v-for="item in parkPlots[activePlotIndex].details" :key="item.label"
                      class="flex items-center justify-between text-sm">
                      <span class="text-slate-400">{{ item.label }}</span>
                      <span class="text-slate-700 font-medium text-right max-w-[60%]">{{ item.value }}</span>
                    </div>
                  </div>
                  <p class="text-sm text-slate-500 leading-relaxed bg-pink-50/60 rounded-xl p-3 border border-pink-100">
                    {{ parkPlots[activePlotIndex].desc }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>
    </main>

    <!-- 产量预测弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showYieldModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showYieldModal = false"></div>
          <div class="relative w-full max-w-xl bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div class="bg-gradient-to-r from-purple-500 to-violet-500 px-6 py-5 flex items-center justify-between shrink-0">
              <div>
                <h2 class="text-white font-bold text-lg tracking-tight"> 玫瑰产量预算</h2>
                <p class="text-white/70 text-xs mt-0.5">基于 AI 模型的智能预估</p>
              </div>
              <button @click="showYieldModal = false" class="w-8 h-8 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center text-white transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div class="flex-1 overflow-y-auto p-6 space-y-5">
              <!-- 总体预测 -->
              <div class="bg-gradient-to-br from-purple-50 to-violet-50 rounded-2xl p-5 border border-purple-100">
                <div class="text-xs text-purple-500 font-medium mb-2">总产量预估（本季）</div>
                <div class="text-4xl font-extrabold text-purple-700 mb-1">123<span class="text-lg font-normal text-purple-500"> 吨</span></div>
                <div class="flex items-center gap-2 text-sm">
                  <span class="text-emerald-600 font-semibold flex items-center gap-0.5"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>+12.5%</span>
                  <span class="text-slate-400">较去年同期</span>
                </div>
              </div>

              <!-- 分地块预测 -->
              <div class="space-y-3">
                <div class="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <svg class="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" /></svg>
                  分地块预测详情
                </div>
                <div v-for="(yp, idx) in yieldPredictions" :key="idx" class="bg-white border border-slate-100 rounded-2xl p-4 hover:shadow-md transition-shadow">
                  <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                      <div class="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold text-white" :class="idx === 0 ? 'bg-pink-500' : idx === 1 ? 'bg-sky-500' : 'bg-amber-500'">{{ yp.plot }}</div>
                      <span class="text-sm font-semibold text-slate-700">{{ yp.name }}</span>
                    </div>
                    <span class="text-lg font-bold" :class="idx === 0 ? 'text-pink-600' : idx === 1 ? 'text-sky-600' : 'text-amber-600'">{{ yp.forecast }}<span class="text-xs font-normal text-slate-400"> 吨</span></span>
                  </div>
                  <!-- 进度条 -->
                  <div class="mb-2">
                    <div class="flex justify-between text-xs text-slate-400 mb-1"><span>完成度</span><span class="font-mono">{{ yp.progress }}%</span></div>
                    <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div class="h-full rounded-full transition-all duration-700" :style="{ width: yp.progress + '%', background: yp.color }"></div>
                    </div>
                  </div>
                  <div class="grid grid-cols-3 gap-2 text-xs mt-3">
                    <div class="bg-slate-50 rounded-xl p-2 text-center">
                      <div class="text-slate-400 mb-0.5">亩产</div>
                      <div class="text-slate-700 font-bold">{{ yp.perMu }}<span class="text-slate-400 font-normal">kg/亩</span></div>
                    </div>
                    <div class="bg-slate-50 rounded-xl p-2 text-center">
                      <div class="text-slate-400 mb-0.5">株数</div>
                      <div class="text-slate-700 font-bold">{{ yp.plants }}</div>
                    </div>
                    <div class="bg-slate-50 rounded-xl p-2 text-center">
                      <div class="text-slate-400 mb-0.5">品质</div>
                      <div class="text-slate-700 font-bold">{{ yp.quality }}</div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 检测日志弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showLogModal" class="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showLogModal = false"></div>
          <div class="relative w-full max-w-md bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[75vh]">
            <div class="bg-gradient-to-r from-pink-500 to-rose-500 px-6 py-4 flex items-center justify-between shrink-0">
              <div>
                <h2 class="text-white font-bold text-base tracking-tight">检测日志</h2>
                <p class="text-white/70 text-xs mt-0.5">共 {{ detectionLog.length }} 条记录</p>
              </div>
              <div class="flex items-center gap-2">
                <button @click="detectionLog = []" class="px-2.5 py-1 bg-white/20 hover:bg-white/30 text-white text-xs rounded-lg transition-colors">清空</button>
                <button @click="showLogModal = false" class="w-7 h-7 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center text-white transition-colors">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
            </div>
            <div class="flex-1 overflow-y-auto p-4 space-y-1.5 min-h-0">
              <div v-if="detectionLog.length === 0" class="text-sm text-slate-400 text-center py-10">等待检测开始...</div>
              <div v-for="(log, idx) in detectionLog" :key="idx" class="flex items-start gap-3 p-2.5 bg-slate-50 rounded-xl border border-slate-100">
                <span class="text-slate-400 font-mono text-xs shrink-0 pt-0.5">{{ log.time }}</span>
                <span class="flex-1 text-xs text-slate-600 leading-relaxed">{{ log.msg }}</span>
                <span class="shrink-0 px-2 py-1 rounded-lg text-[11px] font-bold bg-pink-100 text-pink-600">{{ log.count }}朵</span>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { parseSrt, type TelemetryFrame } from '../utils/srtParser'
import InspectionHeader from '../components/common/InspectionHeader.vue'
import DetectionVideoFrame from '../components/common/DetectionVideoFrame.vue'
import FloatingNotice from '../components/common/FloatingNotice.vue'
import { BASE_URL } from '../utils/webroot'

const missingPlotImages = ref<Record<number, boolean>>({})

// ==================== 后端地址 ====================
// 开发模式走 Vite proxy，生产环境由 Nginx 反代；子路径部署时带 BASE_URL 前缀
const API_BASE = BASE_URL.replace(/\/$/, '')

// ==================== 时间 ====================
const currentTime = ref('')
let clockTimer: number
const updateClock = () => { currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false }) }

// ==================== 任务上传弹窗 ====================
const showTaskModal = ref(false)
const showTaskList = ref(false)
const newTaskName = ref('')
const newTaskVideoFile = ref<File | null>(null)
const newTaskVideoName = ref('')
const newTaskSrtFile = ref<File | null>(null)
const newTaskSrtName = ref('')
const currentTaskName = ref('')
const uploading = ref(false)
const noticeMessage = ref('请上传任务或从历史任务中选择检测视频。')
const noticeTone = ref<'info' | 'success' | 'error'>('info')

interface TaskRecord {
  id: string
  name: string
  videoName: string
  srtName: string
  videoUrl: string   // 后端静态文件 URL (http://127.0.0.1:8002/api/v1/rose/tasks/...)
  srtText: string     // SRT 原始文本
  createdAt: string
}

const taskRecords = ref<TaskRecord[]>([])
const TASK_STORAGE_KEY = 'rose-yield-tasks'

const canUploadTask = computed(() => newTaskName.value.trim() && newTaskVideoFile.value && newTaskSrtFile.value)

function loadTaskRecords() {
  try {
    const raw = localStorage.getItem(TASK_STORAGE_KEY)
    if (raw) {
      const all = JSON.parse(raw)
      // 过滤掉旧格式记录（没有 videoUrl 或 videoUrl 是 blob: 开头的无效URL）
      taskRecords.value = all.filter((t: any) => {
        if (!t.videoUrl) return false
        if (t.videoUrl.startsWith('blob:')) return false
        return true
      })
    }
  } catch { taskRecords.value = [] }
}

function saveTaskRecords() {
  localStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(taskRecords.value))
}

function onNewTaskVideoSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  newTaskVideoFile.value = file
  newTaskVideoName.value = file.name
}

function onNewTaskSrtSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  newTaskSrtFile.value = file
  newTaskSrtName.value = file.name
}

async function confirmUploadTask() {
  if (!canUploadTask.value || uploading.value) return
  uploading.value = true

  const taskId = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  const videoFile = newTaskVideoFile.value!
  const srtFile = newTaskSrtFile.value!
  const taskName = newTaskName.value.trim()
  const srtText = await srtFile.text()

  // 上传到后端磁盘
  const form = new FormData()
  form.append('task_id', taskId)
  form.append('task_name', taskName)
  form.append('video', videoFile, videoFile.name)
  form.append('srt', new Blob([srtText], { type: 'text/plain' }), srtFile.name || 'subtitle.srt')

  try {
    const res = await fetch(`${API_BASE}/api/v1/rose/tasks/upload`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(`上传失败: ${res.status}`)
    const data = await res.json()
    const videoUrl = `${API_BASE}${data.video_path}`

    // 保存任务记录
    const record: TaskRecord = {
      id: taskId,
      name: taskName,
      videoName: videoFile.name,
      srtName: srtFile.name || 'subtitle.srt',
      videoUrl: videoUrl,
      srtText: srtText,
      createdAt: new Date().toLocaleString('zh-CN'),
    }
    taskRecords.value.unshift(record)
    saveTaskRecords()

    // 加载
    resetStats()
    videoSrc.value = videoUrl
    loadSrtTelemetry(srtText, 0)
    currentTaskName.value = taskName
    noticeMessage.value = `任务上传成功：${taskName}`
    noticeTone.value = 'success'
    console.log(`[Task] 任务已上传: ${taskName}, video=${videoUrl}, SRT=${srtFrames.value.length}帧`)
  } catch (err) {
    console.error('[Task] 上传失败:', err)
    noticeMessage.value = '任务上传失败，请确认后端服务已启动。'
    noticeTone.value = 'error'
  }

  // 重置表单
  newTaskName.value = ''
  newTaskVideoFile.value = null
  newTaskVideoName.value = ''
  newTaskSrtFile.value = null
  newTaskSrtName.value = ''
  showTaskModal.value = false
  uploading.value = false
}

async function loadTask(task: TaskRecord) {
  currentTaskName.value = task.name
  showTaskList.value = false
  resetStats()
  noticeMessage.value = `已加载任务：${task.name}`
  noticeTone.value = 'success'

  // 加载 SRT
  const srtRaw = task.srtText || (task as any).srtPath || ''
  if (srtRaw) {
    loadSrtTelemetry(srtRaw, 0)
  } else {
    srtFrames.value = []
    srtLoaded.value = false
  }

  // 加载视频（直接使用后端 URL）
  if (task.videoUrl) {
    videoSrc.value = task.videoUrl
    console.log(`[Task] 加载: ${task.name}, video=${task.videoUrl}, SRT=${srtFrames.value.length}帧`)
  } else {
    console.warn('[Task] 任务无有效视频URL')
  }
}

function deleteTask(id: string) {
  taskRecords.value = taskRecords.value.filter(t => t.id !== id)
  saveTaskRecords()
}

// ==================== 园区概况弹窗 ====================
const showParkModal = ref(false)
const showLogModal = ref(false)
const showYieldModal = ref(false)
const activePlotIndex = ref(0)

const parkPlots = [
  {
    name: '一号地',
    img: BASE_URL + 'rose-pictures/一号地.JPG',
    status: '盛花期',
    stats: [
      { label: '种植面积', value: '110 亩' },
      { label: '株数', value: '18,000 株' },
      { label: '预计产量', value: '66 吨' }
    ],
    details: [
      { label: '地块位置', value: '园区北侧主种植区' },
      { label: '玫瑰品种', value: '大马士革 No.1（保加利亚原种）' },
      { label: '种植年限', value: '第 5 年（2021年定植）' },
      { label: '海拔高度', value: '约 1,950 m' },
      { label: '灌溉方式', value: '滴灌 + 自动喷淋' },
      { label: '当前花期', value: '盛花期（4月中旬 - 5月中旬）' },
      { label: '土壤类型', value: '红壤，富含火山灰矿物质' }
    ],
    desc: '一号地为园区最早定植区，大马士革玫瑰已进入稳产期。花朵饱满、香气浓郁，是精油萃取的核心原料区。每亩年均可产鲜花约600公斤，精油提取率约0.03%-0.05%。'
  },
  {
    name: '二号地',
    img: BASE_URL + 'rose-pictures/二号地.JPG',
    status: '初花期',
    stats: [
      { label: '种植面积', value: '95 亩' },
      { label: '株数', value: '15,500 株' },
      { label: '预计产量', value: '38 吨' }
    ],
    details: [
      { label: '地块位置', value: '园区东侧坡地种植区' },
      { label: '玫瑰品种', value: '大马士革千叶玫瑰（改良品系）' },
      { label: '种植年限', value: '第 3 年（2023年定植）' },
      { label: '海拔高度', value: '约 1,960 m' },
      { label: '灌溉方式', value: '滴灌为主' },
      { label: '当前花期', value: '初花期（较一号地晚约 1 周）' },
      { label: '土壤类型', value: '红壤，坡地排水良好' }
    ],
    desc: '二号地以改良品系大马士革千叶玫瑰为主，花瓣层叠丰富、色泽粉嫩。地处坡地，光照充足，有利于花香物质积累。目前亩产约400公斤，正处于产量爬升阶段，预计再两年进入稳产期。'
  },
  {
    name: '三号地',
    img: BASE_URL + 'rose-pictures/三号地.JPG',
    status: '花苞期',
    stats: [
      { label: '种植面积', value: '75 亩' },
      { label: '株数', value: '11,500 株' },
      { label: '预计产量', value: '19 吨' }
    ],
    details: [
      { label: '地块位置', value: '园区南侧扩建区' },
      { label: '玫瑰品种', value: '大马士革 No.3（高精油含量品系）' },
      { label: '种植年限', value: '第 2 年（2024年定植）' },
      { label: '海拔高度', value: '约 1,945 m' },
      { label: '灌溉方式', value: '微喷灌溉' },
      { label: '当前花期', value: '花苞期（预计 5 月初进入盛花期）' },
      { label: '土壤类型', value: '红壤改良土，施有机肥' }
    ],
    desc: '三号地为园区最新扩建区域，引进高精油含量的大马士革 No.3 品系。目前植株处于快速生长阶段，亩产约250公斤，多数处于花苞期。预计全面进入盛花期后，精油含量可比传统品系提升约 15%。'
  }
]

// ==================== 产量预测数据 ====================
const yieldPredictions = [
  { plot: '一', name: '一号地', forecast: 66, progress: 78, perMu: 600, plants: '18,000', quality: '优', color: 'linear-gradient(90deg, #ec4899, #f43f5e)' },
  { plot: '二', name: '二号地', forecast: 38, progress: 45, perMu: 400, plants: '15,500', quality: '良', color: 'linear-gradient(90deg, #0ea5e9, #6366f1)' },
  { plot: '三', name: '三号地', forecast: 19, progress: 22, perMu: 250, plants: '11,500', quality: '良', color: 'linear-gradient(90deg, #f59e0b, #f97316)' },
]

// ==================== 后端状态 ====================
const backendOnline = ref(false)
const inferenceReady = ref(false)
const apiLatency = ref(0)
let healthTimer: number | undefined

async function checkBackendHealth() {
  try {
    const t0 = performance.now()
    const resp = await fetch(`${API_BASE}/api/v1/rose/health`, { signal: AbortSignal.timeout(3000) })
    backendOnline.value = resp.ok
    const body = resp.ok ? await resp.json() : null
    const health = body?.data ?? body
    inferenceReady.value = Boolean(resp.ok && (health?.inference_available ?? health?.status === 'ready'))
    isDetecting.value = isPlaying.value && inferenceReady.value
    apiLatency.value = Math.round(performance.now() - t0)
  } catch {
    backendOnline.value = false
    inferenceReady.value = false
    isDetecting.value = false
  }
}

// ==================== SRT 解析 ====================
const srtFrames = ref<TelemetryFrame[]>([])
const srtLoaded = ref(false)
const srtFrameCount = computed(() => srtFrames.value.length)

function loadSrtTelemetry(text: string, syncTime = 0) {
  srtFrames.value = parseSrt(text)
  srtLoaded.value = srtFrames.value.length > 0
  currentSrtIndex.value = -1
  if (srtLoaded.value) syncUavFromSrt(syncTime, true)
}

// ==================== 视频相关 ====================
const videoRef = ref<HTMLVideoElement>()
const detectionCanvas = ref<HTMLCanvasElement>()
const videoSrc = ref('')
const isPlaying = ref(false)
const videoCurrentTime = ref(0)
const videoDurationSec = ref(0)
const videoDuration = ref('00:00')
const currentFrame = ref(0)
const processedFrames = ref(0)
const isDetecting = ref(false)

const formatTime = (sec: number) => {
  const m = Math.floor(sec / 60).toString().padStart(2, '0')
  const s = Math.floor(sec % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function onLoadedMetadata() {
  if (!videoRef.value) return
  videoDurationSec.value = videoRef.value.duration
  videoDuration.value = formatTime(videoRef.value.duration)
}

// ==================== 无人机信息 (SRT同步) ====================
const uavInfo = ref({
  relAlt: 0, absAlt: 0, gbYaw: 0, gbPitch: 0, gbRoll: 0,
  iso: 0, focalLen: 0, lat: 0, lng: 0, shutter: '', fnum: 0,
})
const currentSrtIndex = ref(-1)
const srtUpdateCount = computed(() => currentSrtIndex.value >= 0 ? currentSrtIndex.value + 1 : 0)

function findSrtFrameIndex(timeSec: number) {
  const frames = srtFrames.value
  if (frames.length === 0) return -1
  let lo = 0
  let hi = frames.length - 1

  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (frames[mid].time <= timeSec) lo = mid
    else hi = mid - 1
  }

  return lo
}

function applyUavFrame(frame: TelemetryFrame, index: number) {
  currentSrtIndex.value = index
  uavInfo.value = {
    relAlt: frame.relAlt, absAlt: frame.absAlt,
    gbYaw: frame.gbYaw, gbPitch: frame.gbPitch, gbRoll: frame.gbRoll,
    iso: frame.iso, focalLen: frame.focalLen,
    lat: frame.latitude, lng: frame.longitude,
    shutter: frame.shutter, fnum: frame.fnum,
  }
}

function syncUavFromSrt(timeSec: number, force = false) {
  const targetIndex = findSrtFrameIndex(timeSec)
  if (targetIndex < 0) return

  if (force || currentSrtIndex.value < 0 || targetIndex < currentSrtIndex.value) {
    const frame = srtFrames.value[targetIndex]
    if (frame) applyUavFrame(frame, targetIndex)
    return
  }

  for (let index = currentSrtIndex.value + 1; index <= targetIndex; index++) {
    const frame = srtFrames.value[index]
    if (frame) applyUavFrame(frame, index)
  }
}

// ==================== 实时检测 ====================
interface Detection { class: number; name: string; cn: string; bbox: number[]; conf: number }
const currentDetections = ref<Detection[]>([])
const currentFrameCount = ref(0)
const totalDetectedCount = ref(0)

interface TrackBox {
  id: number
  classId: number
  bbox: number[]
  cx: number
  cy: number
  w: number
  h: number
  lastSeenFrame: number
}

const varietyStats = ref([
  { name: '盛开花', count: 0, color: '#d946ef', percent: 0 },
  { name: '已采摘', count: 0, color: '#f59e0b', percent: 0 },
  { name: '花苞', count: 0, color: '#10b981', percent: 0 },
])

const healthStats = ref({ healthy: 0, warning: 0, diseased: 0 })
interface LogItem { time: string; msg: string; count: number }
const detectionLog = ref<LogItem[]>([])

function resetStats() {
  currentSrtIndex.value = -1
  uavInfo.value = {
    relAlt: 0, absAlt: 0, gbYaw: 0, gbPitch: 0, gbRoll: 0,
    iso: 0, focalLen: 0, lat: 0, lng: 0, shutter: '', fnum: 0,
  }
  totalDetectedCount.value = 0
  currentFrameCount.value = 0
  detectionLog.value = []
  healthStats.value = { healthy: 0, warning: 0, diseased: 0 }
  varietyStats.value.forEach(v => { v.count = 0; v.percent = 0 })
  currentDetections.value = []
  resetTrackingState()
  clearCanvas()
}

// ==================== 后端 API 调用 ====================
// 检测配置：演示精度优先，保留更多小目标细节并过滤低置信度框
const CAPTURE_MAX = 640         // 截帧最大边长
const JPEG_QUALITY = 0.78       // JPEG 质量
const ROSE_CONF_THRESHOLD = 0.65
const ROSE_IOU_THRESHOLD = 0.45
const ESTIMATED_VIDEO_FPS = 25
const EFFECTIVE_MAX_INFLIGHT = 6
const TRACK_TTL_FRAMES = 14
const DETECT_TIMEOUT = 3000     // 请求超时 ms

let lastDetectFrame = -1
let latestAppliedDetectFrame = -1
let lastStatsFrame = -1
let nextTrackId = 1
let roseTracks: TrackBox[] = []
let detectTimer: number | null = null
let rafId: number | null = null
let videoFrameCallbackId: number | null = null
let inflightCount = 0           // 当前在飞请求数（替代严格阻塞）
let lastCaptureW = 320          // 最近一次截帧的实际宽度（用于绘制映射）
let lastCaptureH = 180          // 最近一次截帧的实际高度

type VideoFrameMetadataLike = { presentedFrames?: number; mediaTime?: number }
type FrameAwareVideo = HTMLVideoElement & {
  requestVideoFrameCallback?: (callback: (now: number, metadata: VideoFrameMetadataLike) => void) => number
  cancelVideoFrameCallback?: (handle: number) => void
  getVideoPlaybackQuality?: () => { totalVideoFrames?: number }
}

function resetTrackingState() {
  roseTracks = []
  nextTrackId = 1
  lastDetectFrame = -1
  latestAppliedDetectFrame = -1
  lastStatsFrame = -1
}

function getPresentedFrameKey(video: HTMLVideoElement, metadata?: VideoFrameMetadataLike): number {
  if (metadata?.presentedFrames && Number.isFinite(metadata.presentedFrames)) {
    return metadata.presentedFrames
  }
  const quality = (video as FrameAwareVideo).getVideoPlaybackQuality?.()
  if (quality?.totalVideoFrames && Number.isFinite(quality.totalVideoFrames)) {
    return quality.totalVideoFrames
  }
  return Math.floor(video.currentTime * ESTIMATED_VIDEO_FPS)
}

function detectionMetrics(det: Detection) {
  const [x1, y1, x2, y2] = det.bbox
  const w = Math.max(1, x2 - x1)
  const h = Math.max(1, y2 - y1)
  return { bbox: det.bbox, cx: x1 + w / 2, cy: y1 + h / 2, w, h }
}

function bboxIou(a: number[], b: number[]): number {
  const x1 = Math.max(a[0], b[0])
  const y1 = Math.max(a[1], b[1])
  const x2 = Math.min(a[2], b[2])
  const y2 = Math.min(a[3], b[3])
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1)
  if (inter <= 0) return 0
  const areaA = Math.max(1, a[2] - a[0]) * Math.max(1, a[3] - a[1])
  const areaB = Math.max(1, b[2] - b[0]) * Math.max(1, b[3] - b[1])
  return inter / Math.max(1, areaA + areaB - inter)
}

function classCountKey(classId: number): 'rose' | 'picked' | 'bud' | null {
  if (classId === 0) return 'rose'
  if (classId === 1) return 'picked'
  if (classId === 2) return 'bud'
  return null
}

function updateTrack(track: TrackBox, det: Detection, frameKey: number) {
  const m = detectionMetrics(det)
  track.bbox = m.bbox
  track.cx = m.cx
  track.cy = m.cy
  track.w = m.w
  track.h = m.h
  track.lastSeenFrame = frameKey
}

function countNewDetections(detections: Detection[], frameKey: number) {
  const newCounts = { rose: 0, picked: 0, bud: 0 }
  const usedTracks = new Set<number>()
  roseTracks = roseTracks.filter(track => Math.abs(frameKey - track.lastSeenFrame) <= TRACK_TTL_FRAMES)

  for (const det of [...detections].sort((a, b) => b.conf - a.conf)) {
    const metrics = detectionMetrics(det)
    let bestTrack: TrackBox | null = null
    let bestScore = -Infinity

    for (const track of roseTracks) {
      if (track.classId !== det.class || usedTracks.has(track.id)) continue
      const frameGap = Math.abs(frameKey - track.lastSeenFrame)
      if (frameGap > TRACK_TTL_FRAMES) continue

      const centerDist = Math.hypot(metrics.cx - track.cx, metrics.cy - track.cy)
      const sizeRef = Math.max(18, metrics.w, metrics.h, track.w, track.h)
      const iou = bboxIou(metrics.bbox, track.bbox)
      const isSameTarget = iou >= 0.12 || centerDist <= sizeRef * 0.85
      if (!isSameTarget) continue

      const score = iou * 3 - centerDist / sizeRef - frameGap * 0.02
      if (score > bestScore) {
        bestScore = score
        bestTrack = track
      }
    }

    if (bestTrack) {
      updateTrack(bestTrack, det, frameKey)
      usedTracks.add(bestTrack.id)
      continue
    }

    roseTracks.push({
      id: nextTrackId++,
      classId: det.class,
      bbox: metrics.bbox,
      cx: metrics.cx,
      cy: metrics.cy,
      w: metrics.w,
      h: metrics.h,
      lastSeenFrame: frameKey,
    })
    const key = classCountKey(det.class)
    if (key) newCounts[key] += 1
  }

  return newCounts
}

// 根据视频原始尺寸计算保持比例的截帧尺寸（最大边不超过 CAPTURE_MAX）
function calcCaptureSize(videoW: number, videoH: number): { w: number; h: number } {
  const aspect = videoW / videoH
  if (aspect >= 1) {
    const w = Math.min(CAPTURE_MAX, videoW)
    return { w, h: Math.round(w / aspect) }
  } else {
    const h = Math.min(CAPTURE_MAX, videoH)
    return { w: Math.round(h * aspect), h }
  }
}

async function runDetection(frameKeyArg?: number, mediaTime?: number) {
  if (!videoRef.value || !inferenceReady.value) return
  if (inflightCount >= EFFECTIVE_MAX_INFLIGHT) return // 流水线满了，跳过

  const video = videoRef.value
  const detectFrame = frameKeyArg ?? getPresentedFrameKey(video)
  if (detectFrame === lastDetectFrame) return
  lastDetectFrame = detectFrame

  const t = mediaTime ?? video.currentTime
  const vW = video.videoWidth || video.clientWidth
  const vH = video.videoHeight || video.clientHeight
  if (!vW || !vH) return

  const { w: cW, h: cH } = calcCaptureSize(vW, vH)
  lastCaptureW = cW
  lastCaptureH = cH

  const canvas = document.createElement('canvas')
  canvas.width = cW
  canvas.height = cH
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  try {
    ctx.drawImage(video, 0, 0, cW, cH)
  } catch {
    console.warn('[Detect] Canvas tainted (跨域视频)')
    return
  }
  const b64 = canvas.toDataURL('image/jpeg', JPEG_QUALITY).split(',')[1]

  inflightCount++
  try {
    const t0 = performance.now()
    const resp = await fetch(`${API_BASE}/api/v1/rose/detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: b64, conf: ROSE_CONF_THRESHOLD, iou: ROSE_IOU_THRESHOLD }),
      signal: AbortSignal.timeout(DETECT_TIMEOUT),
    })
    apiLatency.value = Math.round(performance.now() - t0)
    if (!resp.ok) {
      console.warn('[Detect] API error', resp.status, resp.statusText)
      try { const errBody = await resp.json(); console.warn('[Detect] error detail:', errBody) } catch {}
      return
    }

    const result = await resp.json()
    const detections = result.detections || []
    const frameCount = result.count || detections.length

    if (detectFrame >= latestAppliedDetectFrame) {
      currentDetections.value = detections
      currentFrameCount.value = frameCount
      latestAppliedDetectFrame = detectFrame
    }

    const newCounts = detectFrame >= lastStatsFrame
      ? countNewDetections(detections, detectFrame)
      : { rose: 0, picked: 0, bud: 0 }
    if (detectFrame >= lastStatsFrame) lastStatsFrame = detectFrame
    const newCount = newCounts.rose + newCounts.picked + newCounts.bud

    if (newCount > 0) {
      totalDetectedCount.value += newCount

      // 更新品种统计：只累计跨帧跟踪后判定为新增的目标
      varietyStats.value[0].count += newCounts.rose
      varietyStats.value[1].count += newCounts.picked
      varietyStats.value[2].count += newCounts.bud
      const total = varietyStats.value.reduce((s, v) => s + v.count, 0)
      varietyStats.value.forEach(v => { v.percent = total > 0 ? Math.round((v.count / total) * 100) : 0 })

      // 健康状态同样只累计新增目标
      healthStats.value.healthy += newCounts.rose
      healthStats.value.warning += newCounts.picked
      healthStats.value.diseased += newCounts.bud
    }

    // 日志（每 5 秒记录一次）
    if (Math.floor(t) % 5 === 0 && currentFrameCount.value > 0) {
      detectionLog.value.unshift({
        time: formatTime(t),
        msg: `本帧 ${frameCount} 朵，新增 ${newCount} 朵 (盛开花${newCounts.rose} 已采摘${newCounts.picked} 花苞${newCounts.bud})`,
        count: newCount,
      })
      if (detectionLog.value.length > 30) detectionLog.value.pop()
    }
  } catch (e: any) {
    if (e.name !== 'AbortError') console.warn('[Detect] fetch error', e)
  } finally {
    inflightCount--
  }
}

// ==================== Canvas 绘制（rAF 循环驱动，处理黑边） ====================
const CLASS_COLORS: Record<number, string> = { 0: '#d946ef', 1: '#f59e0b', 2: '#10b981' }

function drawRealBoxes() {
  const canvas = detectionCanvas.value
  const video = videoRef.value
  if (!canvas || !video) return

  // Canvas 尺寸始终与视频显示尺寸同步
  const vw = video.clientWidth
  const vh = video.clientHeight
  if (canvas.width !== vw || canvas.height !== vh) {
    canvas.width = vw
    canvas.height = vh
  }
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const videoW = video.videoWidth || vw
  const videoH = video.videoHeight || vh
  if (!videoW || !videoH) return

  // 计算视频在 canvas 中的实际绘制区域（处理 object-contain 黑边）
  // 完全复刻 VideoPlayer.vue 的 drawTargets 逻辑
  const canvasAspect = canvas.width / canvas.height
  const videoAspect = videoW / videoH

  let drawW = canvas.width
  let drawH = canvas.height
  let offsetX = 0
  let offsetY = 0

  if (canvasAspect > videoAspect) {
    drawH = canvas.height
    drawW = canvas.height * videoAspect
    offsetX = (canvas.width - drawW) / 2
  } else {
    drawW = canvas.width
    drawH = canvas.width / videoAspect
    offsetY = (canvas.height - drawH) / 2
  }

  // 缩放比例：基于截帧时的实际尺寸（保持比例后的尺寸）
  const scaleX = drawW / lastCaptureW
  const scaleY = drawH / lastCaptureH

  for (const det of currentDetections.value) {
    const [x1, y1, x2, y2] = det.bbox
    const rx = x1 * scaleX + offsetX
    const ry = y1 * scaleY + offsetY
    const rw = (x2 - x1) * scaleX
    const rh = (y2 - y1) * scaleY

    const color = CLASS_COLORS[det.class] || '#d946ef'

    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.strokeRect(rx, ry, rw, rh)

    // 角线
    const cl = Math.min(10, Math.min(rw, rh) * 0.3)
    ctx.lineWidth = 2.5
    ;[[rx, ry], [rx + rw, ry], [rx, ry + rh], [rx + rw, ry + rh]].forEach(([cx, cy], qi) => {
      const dx = qi % 2 === 0 ? 1 : -1
      const dy = qi < 2 ? 1 : -1
      ctx.beginPath(); ctx.moveTo(cx, cy + dy * cl); ctx.lineTo(cx, cy); ctx.lineTo(cx + dx * cl, cy); ctx.stroke()
    })

    // 标签背景
    const label = `${det.cn} ${(det.conf * 100).toFixed(0)}%`
    const tw = ctx.measureText(label).width + 8
    ctx.fillStyle = color
    ctx.fillRect(rx, ry - 20, tw, 18)
    ctx.fillStyle = '#fff'
    ctx.font = '11px monospace'
    ctx.fillText(label, rx + 4, ry - 6)
  }
}

function requestNextVideoFrameDetection() {
  const video = videoRef.value as FrameAwareVideo | undefined
  if (!video?.requestVideoFrameCallback || videoFrameCallbackId !== null) return

  videoFrameCallbackId = video.requestVideoFrameCallback((_now, metadata) => {
    videoFrameCallbackId = null
    if (isPlaying.value && inferenceReady.value) {
      syncVideoPlaybackState()
      drawRealBoxes()
      runDetection(getPresentedFrameKey(video, metadata), metadata.mediaTime)
    }
    if (isPlaying.value) {
      requestNextVideoFrameDetection()
    }
  })
}

// rAF 循环：视频播放期间持续绘制检测框；支持的浏览器用每个视频帧触发检测
function detectionLoop() {
  if (isPlaying.value) {
    syncVideoPlaybackState()
  }
  if (isPlaying.value && inferenceReady.value) {
    drawRealBoxes()
    const video = videoRef.value as FrameAwareVideo | undefined
    if (!video?.requestVideoFrameCallback) runDetection()
  }
  rafId = requestAnimationFrame(detectionLoop)
}
function startDetectionLoop() {
  if (rafId === null) rafId = requestAnimationFrame(detectionLoop)
  requestNextVideoFrameDetection()
}
function stopDetectionLoop() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  const video = videoRef.value as FrameAwareVideo | undefined
  if (videoFrameCallbackId !== null && video?.cancelVideoFrameCallback) {
    video.cancelVideoFrameCallback(videoFrameCallbackId)
  }
  videoFrameCallbackId = null
}

function clearCanvas() {
  const canvas = detectionCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height)
}

// ==================== 视频事件 ====================
function syncVideoPlaybackState(forceSrt = false) {
  if (!videoRef.value) return
  const currentTime = videoRef.value.currentTime
  videoCurrentTime.value = currentTime
  currentFrame.value = Math.floor(currentTime * ESTIMATED_VIDEO_FPS)
  processedFrames.value = currentFrame.value

  // SRT 遥测同步
  if (srtFrames.value.length > 0) {
    syncUavFromSrt(currentTime, forceSrt)
  }
}

function onTimeUpdate() {
  syncVideoPlaybackState()
  // 检测已由 rAF 循环驱动，不在 onTimeUpdate 中触发
}

function onPlay() {
  isPlaying.value = true
  isDetecting.value = inferenceReady.value
  startDetectionLoop() // 启动 rAF 绘制循环
}
function onPause() {
  isPlaying.value = false
  isDetecting.value = false
  stopDetectionLoop()  // 暂停时停止 rAF 循环，节省 CPU
  clearCanvas()        // 清空检测框
}

function togglePlay() {
  if (!videoRef.value || !videoSrc.value) return
  if (videoRef.value.paused) videoRef.value.play()
  else videoRef.value.pause()
}

function seekVideo(seconds: number) {
  if (!videoRef.value || !videoDurationSec.value) return
  videoRef.value.currentTime = seconds
  syncVideoPlaybackState(true)
  resetTrackingState()
  currentDetections.value = []
  clearCanvas()
}

function replayVideo() {
  if (!videoRef.value) return
  seekVideo(0)
  void videoRef.value.play()
}

// ==================== 生命周期 ====================
async function syncExistingTasks() {
  // 从后端扫描 rose-tasks 目录，自动发现已存在的任务
  try {
    const res = await fetch(`${API_BASE}/api/v1/rose/tasks/list`)
    if (!res.ok) return
    const data = await res.json()
    if (!data.tasks || data.tasks.length === 0) return

    let changed = false
    for (const t of data.tasks) {
      const exists = taskRecords.value.find(r => r.id === t.task_id)
      if (exists) continue

      // 读取 SRT 内容
      let srtText = ''
      if (t.srt_name) {
        try {
          const srtRes = await fetch(`${API_BASE}/api/v1/rose/tasks/${t.task_id}/${t.srt_name}`)
          if (srtRes.ok) srtText = await srtRes.text()
        } catch {}
      }

      const record: TaskRecord = {
        id: t.task_id,
        name: t.name || t.task_id,
        videoName: t.video_name,
        srtName: t.srt_name,
        // 后端返回的 video_url 已带部署前缀，避免重复拼接
        videoUrl: t.video_url.startsWith(API_BASE) ? t.video_url : `${API_BASE}${t.video_url}`,
        srtText: srtText,
        createdAt: new Date().toLocaleString('zh-CN'),
      }
      taskRecords.value.unshift(record)
      changed = true
      console.log(`[Sync] 发现已有任务: ${t.task_id} -> ${t.video_url}`)
    }
    if (changed) saveTaskRecords()
  } catch (err) {
    console.warn('[Sync] 扫描已有任务失败:', err)
  }
}

onMounted(() => {
  updateClock()
  clockTimer = window.setInterval(updateClock, 1000)
  checkBackendHealth()
  healthTimer = window.setInterval(checkBackendHealth, 10000) // 每10秒检查后端
  loadTaskRecords() // 加载历史任务记录
  syncExistingTasks() // 扫描后端已有任务目录
  // 如果视频已在播放（从历史任务加载后自动播放），立即启动绘制循环
  if (videoRef.value && !videoRef.value.paused) {
    isPlaying.value = true
    startDetectionLoop()
  }
})

onUnmounted(() => {
  clearInterval(clockTimer)
  if (healthTimer) clearInterval(healthTimer)
  if (detectTimer) clearInterval(detectTimer)
  stopDetectionLoop()
  if (videoSrc.value.startsWith('blob:')) URL.revokeObjectURL(videoSrc.value)
})
</script>

<style scoped>
video::-webkit-media-controls { display: none !important; }

/* 弹窗动画 */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.25s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .relative.w-full,
.modal-leave-to .relative.w-full {
  transform: scale(0.95) translateY(10px);
}
.modal-enter-active .relative.w-full,
.modal-leave-active .relative.w-full {
  transition: transform 0.25s ease;
}
</style>
