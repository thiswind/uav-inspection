<script setup lang="ts">
import { computed } from 'vue'
import { moduleThemes, type ModuleThemeKey } from '../config/moduleThemes'

const props = defineProps<{
  title: string
  theme: ModuleThemeKey
}>()

const themeConfig = computed(() => moduleThemes[props.theme])
</script>

<template>
  <div class="mobile-page min-h-screen bg-slate-50 text-slate-800">
    <div class="border-b bg-white/95 shadow-sm" :class="themeConfig.badge">
      <div class="mx-auto flex min-h-20 max-w-[1500px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:h-20 sm:px-8 sm:py-0">
        <div>
          <div
            class="inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]"
            :class="themeConfig.badge"
          >
            Demo Module
          </div>
          <h1 class="mt-2 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{{ title }}</h1>
        </div>
        <div class="h-12 w-12 rounded-lg bg-gradient-to-br shadow-sm" :class="themeConfig.gradient"></div>
      </div>
    </div>

    <main class="mx-auto flex min-h-[calc(100vh-80px)] max-w-[1500px] items-center justify-center px-4 sm:px-8">
      <section class="w-full max-w-xl rounded-lg border bg-white p-5 text-center shadow-sm sm:p-8" :class="[themeConfig.ring, themeConfig.soft]">
        <div class="mx-auto mb-5 h-16 w-16 rounded-lg bg-gradient-to-br shadow-sm" :class="themeConfig.gradient"></div>
        <h2 class="text-2xl font-bold text-slate-900">模块建设中</h2>
        <p class="mt-3 text-base leading-7 text-slate-600">
          该功能已预留入口和主题色，后续接入业务页面后会保持当前主题一致。
        </p>
      </section>
    </main>
  </div>
</template>
