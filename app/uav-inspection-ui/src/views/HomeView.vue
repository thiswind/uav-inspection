<script setup lang="ts">
import { useRouter } from 'vue-router'
import { moduleThemes, type ModuleThemeKey } from '../config/moduleThemes'
import {
  Antenna,
  Zap,
  Home,
  Building2,
  Bug,
  TreePine,
  ArrowUpDown,
  Maximize,
  Camera,
  LineChart,
  Users,
  HardDriveUpload,
} from 'lucide-vue-next'

const router = useRouter()

const modules = [
  {
    title: '基础设施巡检',
    accent: 'bg-blue-600',
    items: [
      {
        name: '通信基站巡检',
        path: '/telecom',
        theme: 'telecom',
        icon: Antenna,
        desc: ['部件识别', '隐患排查'],
      },
      {
        name: '杆路线路巡检',
        path: '/power',
        theme: 'power',
        icon: Zap,
        desc: ['绝缘破损', '断股检测'],
      },
      {
        name: '建筑屋顶巡检',
        path: '/roof',
        theme: 'roof',
        icon: Home,
        desc: ['防水脱层', '异物检测'],
      },
      {
        name: '建筑外墙巡检',
        path: '/wall',
        theme: 'wall',
        icon: Building2,
        desc: ['裂缝标注', '渗水识别'],
      },
    ],
  },
  {
    title: '农林植保业务',
    accent: 'bg-emerald-500',
    items: [
      {
        name: '病虫害巡检',
        path: '/pest',
        theme: 'pest',
        icon: Bug,
        desc: ['智能监测', '自动告警'],
      },
      {
        name: '乔木修剪检测',
        path: '/pruning',
        theme: 'pruning',
        icon: TreePine,
        desc: ['修剪识别', '状态分析'],
      },
      {
        name: '乔木高度测量',
        path: '/height',
        theme: 'height',
        icon: ArrowUpDown,
        desc: ['点云数据', '精度测算'],
      },
      {
        name: '绿化面积测量',
        path: '/area',
        theme: 'area',
        icon: Maximize,
        desc: ['灌木草坪', '面积统计'],
      },
    ],
  },
  {
    title: '数字园区治理',
    accent: 'bg-purple-500',
    items: [
      {
        name: '数字玫瑰园',
        path: '/rose-digital',
        theme: 'roseDigital',
        icon: Camera,
        desc: ['全息要素', '数字档案'],
      },
      {
        name: '玫瑰花产量预测',
        path: '/rose-yield',
        theme: 'roseYield',
        icon: LineChart,
        desc: ['长序特征', '趋势分析'],
      },
      {
        name: '热力客流监测',
        path: '/heatmap-flow',
        theme: 'roseFlow',
        icon: Users,
        desc: ['人员分布', '聚集预警'],
      },
    ],
  },
  {
    title: '演示素材管理',
    accent: 'bg-slate-600',
    items: [
      {
        name: '素材上传中心',
        path: '/assets',
        theme: 'roseDigital',
        icon: HardDriveUpload,
        desc: ['视频灌入', '模型上传'],
      },
    ],
  },
] as const satisfies ReadonlyArray<{
  title: string
  accent: string
  items: ReadonlyArray<{
    name: string
    path: string
    theme: ModuleThemeKey
    icon: unknown
    desc: readonly [string, string]
  }>
}>

const handleNavigation = async (path: string) => {
  try {
    await router.push(path)
  } catch {
    await router.push('/telecom')
  }
}
</script>

<template>
  <div class="min-h-screen bg-[#f3f4f6] flex flex-col font-sans">
    <header class="w-full bg-gradient-to-r from-blue-700 to-indigo-800 shadow-md">
      <div class="max-w-[1500px] mx-auto px-8 h-20 flex items-center justify-between">
        <h1 class="text-3xl font-bold tracking-widest text-white">低空智能巡检与决策平台</h1>
        <div class="flex items-center gap-6 text-base font-medium text-white/90">
          <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 bg-emerald-400 rounded-full animate-pulse"></span> 边缘算力在线</span>
        </div>
      </div>
    </header>

    <main class="flex-1 max-w-[1500px] mx-auto w-full px-8 py-8">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-7">
        <section v-for="group in modules" :key="group.title" class="bg-white rounded-lg shadow-sm border border-slate-200 p-7 flex flex-col">
          <div class="flex items-center gap-3 mb-7">
            <div class="w-2 h-8 rounded-full" :class="group.accent"></div>
            <h2 class="text-2xl font-bold text-slate-800">{{ group.title }}</h2>
          </div>

          <div class="flex flex-col gap-5">
            <button
              v-for="item in group.items"
              :key="item.name"
              @click="handleNavigation(item.path)"
              class="w-full h-36 border rounded-lg p-5 shadow-[0_8px_24px_rgba(15,23,42,0.05)] hover:shadow-lg hover:-translate-y-1 transition-all flex items-center group text-left"
              :class="[moduleThemes[item.theme].card, moduleThemes[item.theme].hover]"
            >
              <div class="flex flex-col items-center justify-center w-28 shrink-0">
                <div class="mb-3 flex h-16 w-16 items-center justify-center rounded-lg bg-white shadow-sm ring-1" :class="moduleThemes[item.theme].ring">
                  <component :is="item.icon" :size="46" stroke-width="1.6" class="group-hover:scale-110 transition-transform" :class="moduleThemes[item.theme].icon" />
                </div>
                <span class="text-xs font-semibold text-slate-500 text-center leading-snug">{{ item.desc[0] }}<br>{{ item.desc[1] }}</span>
              </div>
              <div class="flex-1 flex flex-col justify-center items-center gap-2 min-w-0">
                <span class="text-xl font-extrabold tracking-wide transition-colors" :class="moduleThemes[item.theme].text">{{ item.name }}</span>
                <span class="rounded-full border px-3 py-1 text-xs font-semibold" :class="moduleThemes[item.theme].badge">进入模块</span>
              </div>
            </button>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

