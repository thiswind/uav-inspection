<script setup lang="ts">
import { ref, watch } from 'vue'
import DeploymentNotice from './components/common/DeploymentNotice.vue'

const noticeVisible = ref(false)

watch(noticeVisible, (v) => {
  document.body.classList.toggle('notice-visible', v)
})
</script>

<template>
  <div class="router-host">
    <router-view></router-view>
  </div>
  <DeploymentNotice @visibility-change="noticeVisible = $event" />
</template>

<style>
/* 部署提示悬浮时为页面底部预留空间，防止遮挡正文（移动端尤其明显） */
body.notice-visible .router-host {
  padding-bottom: 140px;
}
</style>
