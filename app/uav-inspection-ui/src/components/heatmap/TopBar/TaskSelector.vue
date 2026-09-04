<template>
  <div>
    <button
      type="button"
      class="flex h-10 w-64 items-center justify-between gap-3 rounded-lg border border-cyan-200 bg-slate-50 px-4 text-left shadow-sm transition-all hover:border-cyan-400 hover:bg-white"
      aria-haspopup="dialog"
      :aria-expanded="isOpen"
      data-testid="task-selector-trigger"
      @click="isOpen = true"
    >
      <span class="flex min-w-0 items-center gap-2">
        <span class="h-2 w-2 shrink-0 rounded-full" :class="statusColor(currentTask?.status) || 'bg-slate-300'"></span>
        <span class="truncate text-sm font-medium text-slate-700">{{ currentTask?.taskName || '选择分析任务' }}</span>
      </span>
      <svg class="h-4 w-4 shrink-0 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h8M8 12h8M8 17h5" /></svg>
    </button>

    <Teleport to="body">
      <Transition name="task-dialog">
        <div
          v-if="isOpen"
          class="fixed inset-0 z-[1200] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
          data-testid="task-selector-dialog"
          @mousedown.self="close"
        >
          <section
            class="flex max-h-[min(680px,calc(100vh-32px))] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="task-selector-title"
          >
            <header class="flex items-start justify-between gap-4 border-b border-slate-200 bg-gradient-to-r from-cyan-50 to-white px-5 py-4">
              <div>
                <h2 id="task-selector-title" class="text-lg font-semibold text-slate-900">任务管理</h2>
                <p class="mt-1 text-xs text-slate-500">加载任务，或对已有任务进行重命名和删除</p>
              </div>
              <button type="button" class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-white hover:text-slate-700" title="关闭任务选择" aria-label="关闭任务选择" @click="close">
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18 18 6M6 6l12 12" /></svg>
              </button>
            </header>

            <div v-if="tasks.length" class="min-h-0 flex-1 overflow-y-auto p-3" data-testid="task-selector-list">
              <article
                v-for="task in tasks"
                :key="task.taskId"
                class="mb-2 rounded-xl border p-3 transition last:mb-0"
                :class="currentTask?.taskId === task.taskId ? 'border-cyan-300 bg-cyan-50 ring-1 ring-cyan-200' : 'border-slate-200 bg-white hover:border-cyan-200'"
                :data-task-id="task.taskId"
                :data-testid="`heatmap-task-card-${task.taskId}`"
              >
                <div class="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
                  <button
                    type="button"
                    class="min-w-0 rounded-lg px-1 py-1 text-left transition hover:bg-cyan-50 disabled:cursor-wait disabled:opacity-60"
                    :disabled="busyTaskId === task.taskId"
                    :data-testid="`heatmap-task-load-${task.taskId}`"
                    @click="selectTask(task)"
                  >
                    <span class="flex items-center gap-2"><span class="h-2 w-2 shrink-0 rounded-full" :class="statusColor(task.status)"></span><span class="truncate text-sm font-semibold text-slate-800">{{ task.taskName }}</span></span>
                    <span class="mt-1.5 block truncate pl-4 text-xs text-slate-400">{{ task.uploadTime }}</span>
                    <span v-if="task.status === 'PROCESSING'" class="mt-2 block pl-4"><span class="block h-1.5 overflow-hidden rounded-full bg-sky-100"><span class="block h-full rounded-full bg-sky-500" :style="{ width: `${task.progress || 0}%` }"></span></span></span>
                  </button>

                  <div class="flex items-center gap-2">
                    <span class="rounded-md border px-2 py-1 text-[11px] font-medium" :class="statusBadge(task.status)">{{ statusText(task.status) }}</span>
                    <button
                      type="button"
                      class="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs font-semibold text-amber-700 transition hover:bg-amber-100 disabled:cursor-wait disabled:opacity-50"
                      :disabled="busyTaskId === task.taskId"
                      :data-testid="`heatmap-task-rename-${task.taskId}`"
                      @click="beginRename(task)"
                    >重命名</button>
                    <button
                      type="button"
                      class="rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-wait disabled:opacity-50"
                      :disabled="busyTaskId === task.taskId"
                      :data-testid="`heatmap-task-delete-${task.taskId}`"
                      @click="beginDelete(task)"
                    >删除</button>
                  </div>
                </div>

                <form
                  v-if="editingTaskId === task.taskId"
                  class="mt-3 flex items-center gap-2 border-t border-amber-100 pt-3"
                  :data-testid="`heatmap-task-rename-form-${task.taskId}`"
                  @submit.prevent="submitRename(task)"
                >
                  <input
                    v-model="renameDraft"
                    type="text"
                    maxlength="80"
                    class="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                    aria-label="新任务名称"
                    :disabled="busyTaskId === task.taskId"
                  />
                  <button type="submit" class="rounded-lg bg-amber-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-amber-600 disabled:opacity-50" :disabled="!renameDraft.trim() || busyTaskId === task.taskId">保存</button>
                  <button type="button" class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50" @click="cancelInlineAction">取消</button>
                </form>

                <div
                  v-if="deleteCandidateId === task.taskId"
                  class="mt-3 flex items-center justify-between gap-3 border-t border-rose-100 pt-3"
                  :data-testid="`heatmap-task-delete-confirm-${task.taskId}`"
                >
                  <p class="text-xs text-rose-700">确认删除该任务及其视频、字幕？此操作无法撤销。</p>
                  <div class="flex shrink-0 items-center gap-2">
                    <button type="button" class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50" @click="cancelInlineAction">取消</button>
                    <button type="button" class="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-rose-700 disabled:opacity-50" :disabled="busyTaskId === task.taskId" @click="confirmDelete(task)">确认删除</button>
                  </div>
                </div>
              </article>
            </div>

            <div v-else class="flex min-h-52 flex-col items-center justify-center px-8 text-center">
              <div class="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400"><svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M9 17v-6m3 6V7m3 10v-3M5 21h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2Z" /></svg></div>
              <div class="mt-4 text-sm font-semibold text-slate-800">暂无可选择任务</div>
              <div class="mt-1 text-xs text-slate-500">请关闭弹窗后使用页头“新建任务”上传检测视频</div>
            </div>

            <footer class="border-t border-slate-200 bg-slate-50 px-5 py-3 text-right text-xs text-slate-500">共 {{ tasks.length }} 条任务</footer>
          </section>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { PatrolTask } from '../../../types/patrol'

const props = withDefaults(defineProps<{
  tasks: PatrolTask[]
  modelValue: string | null
  busyTaskId?: string | null
}>(), { busyTaskId: null })
const emit = defineEmits<{
  'update:modelValue': [taskId: string]
  change: [task: PatrolTask]
  rename: [payload: { task: PatrolTask; taskName: string }]
  delete: [task: PatrolTask]
}>()

const isOpen = ref(false)
const editingTaskId = ref('')
const deleteCandidateId = ref('')
const renameDraft = ref('')
const currentTask = computed(() => props.tasks.find((task) => task.taskId === props.modelValue) || null)

function cancelInlineAction() {
  editingTaskId.value = ''
  deleteCandidateId.value = ''
  renameDraft.value = ''
}
function close() {
  cancelInlineAction()
  isOpen.value = false
}
function selectTask(task: PatrolTask) {
  emit('update:modelValue', task.taskId)
  emit('change', task)
  close()
}
function beginRename(task: PatrolTask) {
  deleteCandidateId.value = ''
  editingTaskId.value = task.taskId
  renameDraft.value = task.taskName
}
function submitRename(task: PatrolTask) {
  const taskName = renameDraft.value.trim()
  if (!taskName) return
  if (taskName !== task.taskName) emit('rename', { task, taskName })
  cancelInlineAction()
}
function beginDelete(task: PatrolTask) {
  editingTaskId.value = ''
  renameDraft.value = ''
  deleteCandidateId.value = task.taskId
}
function confirmDelete(task: PatrolTask) {
  emit('delete', task)
  cancelInlineAction()
}
function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape') return
  if (editingTaskId.value || deleteCandidateId.value) cancelInlineAction()
  else close()
}

function statusColor(status?: string) {
  const map: Record<string, string> = { PENDING: 'bg-yellow-400', PROCESSING: 'bg-sky-400 animate-pulse', COMPLETED: 'bg-emerald-500', FAILED: 'bg-red-500' }
  return status ? map[status] : ''
}
function statusBadge(status: string) {
  const map: Record<string, string> = {
    PENDING: 'border-yellow-200 bg-yellow-50 text-yellow-700', PROCESSING: 'border-sky-200 bg-sky-50 text-sky-700',
    COMPLETED: 'border-emerald-200 bg-emerald-50 text-emerald-700', FAILED: 'border-red-200 bg-red-50 text-red-700',
  }
  return map[status] || 'border-slate-200 text-slate-600'
}
function statusText(status: string) {
  const map: Record<string, string> = { PENDING: '队列中', PROCESSING: '分析中', COMPLETED: '已完成', FAILED: '失败' }
  return map[status] || '未知'
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
.task-dialog-enter-active,
.task-dialog-leave-active { transition: opacity 180ms ease; }
.task-dialog-enter-active section,
.task-dialog-leave-active section { transition: opacity 180ms ease, transform 180ms ease; }
.task-dialog-enter-from,
.task-dialog-leave-to,
.task-dialog-enter-from section,
.task-dialog-leave-to section { opacity: 0; }
.task-dialog-enter-from section,
.task-dialog-leave-to section { transform: translateY(8px) scale(0.98); }
</style>
