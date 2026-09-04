<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  taskName?: string
  taskLabel?: string
  online?: boolean | null
}>(), {
  taskName: '',
  taskLabel: '当前任务',
  online: null,
})
</script>

<template>
  <header class="inspection-header">
    <div class="inspection-header__identity">
      <div class="min-w-0">
        <div class="inspection-header__platform">低空智能巡检与决策平台</div>
        <h1 class="inspection-header__title">{{ title }}</h1>
      </div>

      <div class="inspection-header__task">
        <div class="inspection-header__task-label">{{ taskLabel }}</div>
        <div class="inspection-header__task-name">{{ taskName || '尚未选择任务' }}</div>
      </div>

      <div v-if="online !== null" class="inspection-header__status">
        <span class="inspection-header__status-dot" :class="online ? 'bg-emerald-500' : 'bg-rose-500'"></span>
        {{ online ? '服务在线' : '服务离线' }}
      </div>
    </div>

    <div class="inspection-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.inspection-header {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border: 1px solid rgb(226 232 240 / 0.95);
  border-radius: 8px;
  background: rgb(255 255 255 / 0.92);
  padding: 14px 18px;
  box-shadow: 0 10px 32px -24px rgb(15 23 42 / 0.45);
  backdrop-filter: blur(16px);
}

.inspection-header__identity {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 20px;
}

.inspection-header__platform,
.inspection-header__task-label {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
}

.inspection-header__title {
  margin-top: 5px;
  overflow: hidden;
  color: #0f172a;
  font-size: 21px;
  font-weight: 700;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inspection-header__task {
  min-width: 210px;
  max-width: 340px;
  border-left: 1px solid #e2e8f0;
  padding-left: 20px;
}

.inspection-header__task-name {
  margin-top: 5px;
  overflow: hidden;
  color: #0f172a;
  font-size: 15px;
  font-weight: 650;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inspection-header__status {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 7px;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.inspection-header__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.inspection-header__actions {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  overflow-x: auto;
  padding: 2px;
  scrollbar-width: thin;
  white-space: nowrap;
}

.inspection-header__actions :slotted(button),
.inspection-header__actions :slotted(a) {
  display: inline-flex !important;
  min-height: 40px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: 8px !important;
  padding: 9px 14px !important;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .inspection-header {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }

  .inspection-header__actions {
    justify-content: flex-start;
  }
}

@media (max-width: 620px) {
  .inspection-header__identity {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
  }

  .inspection-header__task {
    width: 100%;
    min-width: 0;
    max-width: none;
    border-left: 0;
    border-top: 1px solid #e2e8f0;
    padding-top: 10px;
    padding-left: 0;
  }
}
</style>
