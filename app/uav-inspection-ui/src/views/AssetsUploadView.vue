<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import {
  ArrowLeft, CircleCheck, FolderOpen, HardDriveUpload, Pause, Play,
  RefreshCw, RotateCcw, TriangleAlert, UploadCloud,
} from 'lucide-vue-next'
import { http } from '../utils/request'

interface CategoryOption {
  key: string
  label: string
  target: string
}

interface FileEntry {
  path: string
  size: number
  modified: number
}

type TaskStatus = 'waiting' | 'uploading' | 'paused' | 'done' | 'error' | 'skipped'

interface UploadTask {
  key: string
  file: File
  status: TaskStatus
  note: string
  uploaded: number
  total: number
  category: string
  subdir: string
  overwrite: boolean
  uploadId: string
  chunkSize: number
  totalChunks: number
  received: number[]
  controller: AbortController | null
}

interface InitData {
  mode: 'instant' | 'chunked'
  uploadId?: string
  chunkSize?: number
  totalChunks?: number
  received?: number[]
}

interface StatusData {
  uploadId: string
  received: number[]
  chunkSize: number
  totalChunks: number
  filename: string
}

interface CompleteData {
  path: string
  size: number
  chunks?: number
  deduplicated?: string
}

interface BatchData {
  category: string
  dir: string
  saved: { name: string; size: number }[]
  skipped: { name: string; reason: string }[]
}

// 小文件（≤8MB）走原批量直传（多文件一次请求更快），大文件走分片
const SMALL_BATCH_LIMIT = 8 * 1024 * 1024
const CHUNK_TIMEOUT = 120_000
const COMPLETE_TIMEOUT = 120_000

const router = useRouter()
const categories = ref<CategoryOption[]>([])
const category = ref('')
const subdir = ref('')
const overwrite = ref(false)
const tasks = ref<UploadTask[]>([])
const busy = ref(false)
const stopping = ref(false)
const message = reactive({ kind: '' as '' | 'ok' | 'err', text: '' })
const files = ref<FileEntry[]>([])
const filesRoot = ref('')

const activeTask = computed(() => tasks.value.find(t => t.status === 'uploading') ?? null)
const pendingCount = computed(() => tasks.value.filter(t => t.status === 'waiting').length)

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024) return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
  if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

async function loadCategories() {
  const res = await http.get<CategoryOption[]>('/assets/categories')
  categories.value = res.data
  if (!category.value && categories.value.length) category.value = categories.value[0].key
}

async function refreshFiles() {
  if (!category.value) return
  const res = await http.get<{ root: string; count: number; files: FileEntry[] }>('/assets/files', {
    category: category.value,
    subdir: subdir.value,
  })
  files.value = res.data.files
  filesRoot.value = res.data.root
}

function onPick(event: Event) {
  const input = event.target as HTMLInputElement
  for (const file of Array.from(input.files ?? [])) {
    const key = `${file.name}:${file.size}:${file.lastModified}`
    if (tasks.value.some(t => t.key === key && t.status !== 'error')) continue
    tasks.value.push({
      key, file, status: 'waiting', note: '', uploaded: 0, total: file.size,
      category: '', subdir: '', overwrite: false,
      uploadId: '', chunkSize: 0, totalChunks: 0, received: [], controller: null,
    })
  }
  input.value = ''
}

function storageKey(t: UploadTask): string {
  return `uav-up:${t.category}:${t.subdir}:${t.file.name}:${t.file.size}:${t.file.lastModified}`
}

function initForm(t: UploadTask): FormData {
  const form = new FormData()
  form.append('category', t.category)
  form.append('filename', t.file.name)
  form.append('size', String(t.file.size))
  form.append('subdir', t.subdir)
  form.append('overwrite', t.overwrite ? 'true' : 'false')
  return form
}

function pauseTask(t: UploadTask) {
  t.controller?.abort()
}

function pauseAll() {
  stopping.value = true
  for (const t of tasks.value) {
    if (t.status === 'uploading') t.controller?.abort()
  }
}

async function startTask(t: UploadTask) {
  t.status = 'uploading'
  t.note = ''
  t.controller = new AbortController()
  try {
    // 断点续传：本地记有 uploadId 就先问服务端已收分片，不重新 init
    const localKey = storageKey(t)
    if (!t.uploadId) {
      const savedId = localStorage.getItem(localKey)
      if (savedId) {
        try {
          const st = await http.get<StatusData>('/assets/upload/status', { upload_id: savedId })
          t.uploadId = st.data.uploadId
          t.chunkSize = st.data.chunkSize
          t.totalChunks = st.data.totalChunks
          t.received = st.data.received
        } catch {
          localStorage.removeItem(localKey)
        }
      }
    }
    if (!t.uploadId) {
      const res = await http.postForm<InitData>('/assets/upload/init', initForm(t), {
        signal: t.controller.signal,
      })
      if (res.data.mode === 'instant') {
        t.status = 'done'
        t.note = '秒传命中（服务端已有同名同大小文件）'
        t.uploaded = t.total
        localStorage.removeItem(localKey)
        return
      }
      t.uploadId = res.data.uploadId ?? ''
      t.chunkSize = res.data.chunkSize ?? SMALL_BATCH_LIMIT
      t.totalChunks = res.data.totalChunks ?? 1
      t.received = res.data.received ?? []
      localStorage.setItem(localKey, t.uploadId)
    }
    t.uploaded = Math.min(t.total, t.received.length * t.chunkSize)

    for (let i = 0; i < t.totalChunks; i++) {
      if (t.received.includes(i)) continue
      const start = i * t.chunkSize
      const blob = t.file.slice(start, Math.min(start + t.chunkSize, t.total))
      const form = new FormData()
      form.append('upload_id', t.uploadId)
      form.append('index', String(i))
      form.append('file', blob, t.file.name)
      const base = t.received.length * t.chunkSize
      await http.postForm('/assets/upload/chunk', form, {
        timeout: CHUNK_TIMEOUT,
        signal: t.controller.signal,
        onUploadProgress: e => {
          t.uploaded = Math.min(t.total, base + (e.loaded ?? 0))
        },
      })
      t.received.push(i)
      t.uploaded = Math.min(t.total, t.received.length * t.chunkSize)
    }

    const form = new FormData()
    form.append('upload_id', t.uploadId)
    const done = await http.postForm<CompleteData>('/assets/upload/complete', form, {
      timeout: COMPLETE_TIMEOUT,
      signal: t.controller.signal,
    })
    t.status = 'done'
    t.uploaded = t.total
    t.note = done.data.deduplicated ? done.data.deduplicated : `合并完成（${done.data.chunks} 个分片）`
    localStorage.removeItem(localKey)
  } catch (error) {
    if (axios.isCancel(error)) {
      t.status = 'paused'
      t.note = '已暂停，进度已保留'
    } else {
      t.status = 'error'
      t.note = error instanceof Error ? error.message : String(error)
    }
  } finally {
    t.controller = null
  }
}

async function uploadSmallBatch(batch: UploadTask[]) {
  const form = new FormData()
  form.append('category', batch[0].category)
  form.append('subdir', batch[0].subdir)
  form.append('overwrite', batch[0].overwrite ? 'true' : 'false')
  batch.forEach(t => form.append('files', t.file, t.file.name))
  const controller = new AbortController()
  batch.forEach(t => { t.controller = controller })
  try {
    const res = await http.postForm<BatchData>('/assets/upload', form, {
      timeout: CHUNK_TIMEOUT,
      signal: controller.signal,
    })
    const savedNames = new Set(res.data.saved.map(s => s.name))
    const skippedMap = new Map(res.data.skipped.map(s => [s.name, s.reason]))
    for (const t of batch) {
      if (savedNames.has(t.file.name)) {
        t.status = 'done'
        t.uploaded = t.total
        t.note = '已保存'
      } else if (skippedMap.has(t.file.name)) {
        t.status = 'skipped'
        t.note = skippedMap.get(t.file.name) ?? '已跳过'
      } else {
        t.status = 'error'
        t.note = '服务端未确认该文件'
      }
      t.controller = null
    }
  } catch (error) {
    for (const t of batch) {
      t.controller = null
      if (axios.isCancel(error)) {
        t.status = 'waiting'
        t.note = ''
      } else {
        t.status = 'error'
        t.note = error instanceof Error ? error.message : String(error)
      }
    }
  }
}

async function startUpload() {
  if (!category.value) {
    message.kind = 'err'
    message.text = '请选择素材分类'
    return
  }
  const queue = tasks.value.filter(t => t.status === 'waiting')
  if (!queue.length) {
    message.kind = 'err'
    message.text = '没有待上传的文件'
    return
  }
  queue.forEach(t => {
    t.category = category.value
    t.subdir = subdir.value.trim()
    t.overwrite = overwrite.value
  })
  busy.value = true
  stopping.value = false
  message.kind = ''
  message.text = ''
  try {
    const smalls = queue.filter(t => t.file.size <= SMALL_BATCH_LIMIT)
    const larges = queue.filter(t => t.file.size > SMALL_BATCH_LIMIT)
    if (smalls.length && !stopping.value) await uploadSmallBatch(smalls)
    for (const t of larges) {
      if (stopping.value) break
      await startTask(t)
    }
    const done = tasks.value.filter(t => t.status === 'done').length
    const failed = tasks.value.filter(t => t.status === 'error').length
    const paused = tasks.value.filter(t => t.status === 'paused').length
    if (failed) {
      message.kind = 'err'
      message.text = `${done} 个成功，${failed} 个失败（可单点重试）${paused ? `，${paused} 个已暂停` : ''}`
    } else if (paused) {
      message.kind = 'ok'
      message.text = `${done} 个成功，${paused} 个已暂停（点「继续」接着传）`
    } else if (done) {
      message.kind = 'ok'
      message.text = `全部完成：${done} 个文件已保存`
    }
    await refreshFiles()
  } finally {
    busy.value = false
    stopping.value = false
  }
}

function taskBadgeClass(t: UploadTask): string {
  switch (t.status) {
    case 'uploading': return 'bg-blue-50 text-blue-600'
    case 'done': return 'bg-emerald-50 text-emerald-600'
    case 'paused': return 'bg-amber-50 text-amber-600'
    case 'skipped': return 'bg-slate-100 text-slate-500'
    case 'error': return 'bg-red-50 text-red-600'
    default: return 'bg-slate-50 text-slate-400'
  }
}

function taskBadgeText(t: UploadTask): string {
  switch (t.status) {
    case 'uploading': return '上传中'
    case 'done': return '完成'
    case 'paused': return '已暂停'
    case 'skipped': return '跳过'
    case 'error': return '失败'
    default: return '待上传'
  }
}

onMounted(async () => {
  await loadCategories()
  await refreshFiles()
})
</script>

<template>
  <div class="min-h-screen bg-[#f3f4f6] font-sans flex flex-col">
    <header class="w-full bg-gradient-to-r from-blue-700 to-indigo-800 shadow-md">
      <div class="max-w-[1100px] mx-auto px-8 h-20 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <button
            class="flex items-center gap-2 text-white/90 hover:text-white text-sm font-medium px-3 py-1.5 rounded-md border border-white/30 hover:border-white/60 transition-colors"
            @click="router.push('/')"
          >
            <ArrowLeft :size="16" /> 返回首页
          </button>
          <h1 class="text-2xl font-bold tracking-widest text-white">素材上传中心</h1>
        </div>
        <div class="flex items-center gap-2 text-white/90 text-sm font-medium">
          <HardDriveUpload :size="18" /> 大文件分片 · 断点续传
        </div>
      </div>
    </header>

    <main class="flex-1 max-w-[1100px] mx-auto w-full px-8 py-8 flex flex-col gap-6">
      <section class="bg-white rounded-lg shadow-sm border border-slate-200 p-6 flex flex-col gap-5">
        <h2 class="text-lg font-bold text-slate-800 flex items-center gap-2">
          <UploadCloud :size="20" class="text-blue-600" /> 上传素材
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
          <label class="flex flex-col gap-1.5 text-sm font-medium text-slate-600">
            素材分类
            <select
              v-model="category"
              class="border border-slate-300 rounded-md px-3 py-2 text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              @change="refreshFiles()"
            >
              <option v-for="item in categories" :key="item.key" :value="item.key">
                {{ item.label }}
              </option>
            </select>
          </label>
          <label class="flex flex-col gap-1.5 text-sm font-medium text-slate-600">
            子目录（可选，如任务名，留空传到分类根）
            <input
              v-model="subdir"
              type="text"
              placeholder="task-2026/demo"
              class="border border-slate-300 rounded-md px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              @change="refreshFiles()"
            />
          </label>
        </div>

        <label class="flex items-center gap-2 text-sm text-slate-600 select-none cursor-pointer">
          <input v-model="overwrite" type="checkbox" class="h-4 w-4 accent-blue-600" />
          覆盖同名文件（默认关闭：同名文件跳过不覆盖）
        </label>

        <label
          class="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/40 transition-colors"
        >
          <input type="file" multiple class="hidden" @change="onPick" />
          <FolderOpen :size="34" class="mx-auto text-slate-400 mb-2" />
          <p class="text-sm text-slate-500">
            点击选择文件（可多选：视频 / 模型 / 图片 / 测量数据）
          </p>
          <p class="text-xs text-slate-400 mt-1">
            大文件自动分片上传，中断后可继续，刷新页面不丢进度
          </p>
        </label>

        <ul v-if="tasks.length" class="flex flex-col gap-2">
          <li
            v-for="t in tasks"
            :key="t.key"
            class="border border-slate-200 rounded-md px-4 py-3 flex flex-col gap-2"
          >
            <div class="flex items-center justify-between gap-3">
              <span class="font-mono text-sm text-slate-700 break-all">{{ t.file.name }}</span>
              <span class="flex items-center gap-2 whitespace-nowrap">
                <span class="text-xs text-slate-400">{{ formatSize(t.uploaded) }} / {{ formatSize(t.total) }}</span>
                <span class="text-xs font-medium px-2 py-0.5 rounded-full" :class="taskBadgeClass(t)">
                  {{ taskBadgeText(t) }}
                </span>
              </span>
            </div>
            <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :class="t.status === 'error' ? 'bg-red-400' : t.status === 'done' ? 'bg-emerald-500' : 'bg-blue-500'"
                :style="{ width: Math.min(100, (t.uploaded / t.total) * 100) + '%' }"
              />
            </div>
            <div class="flex items-center justify-between gap-3">
              <span class="text-xs" :class="t.status === 'error' ? 'text-red-500' : 'text-slate-400'">
                <template v-if="t.status === 'done'"><CircleCheck :size="12" class="inline -mt-0.5" /> {{ t.note }}</template>
                <template v-else-if="t.status === 'error'"><TriangleAlert :size="12" class="inline -mt-0.5" /> {{ t.note }}</template>
                <template v-else-if="t.totalChunks > 1">分片 {{ t.received.length }} / {{ t.totalChunks }}{{ t.note ? ` · ${t.note}` : '' }}</template>
                <template v-else>{{ t.note }}</template>
              </span>
              <button
                v-if="t.status === 'uploading'"
                class="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-amber-600"
                @click="pauseTask(t)"
              >
                <Pause :size="13" /> 暂停
              </button>
              <button
                v-else-if="t.status === 'paused'"
                class="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"
                :disabled="busy"
                @click="startTask(t)"
              >
                <Play :size="13" /> 继续
              </button>
              <button
                v-else-if="t.status === 'error'"
                class="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"
                @click="startTask(t)"
              >
                <RotateCcw :size="13" /> 重试
              </button>
            </div>
          </li>
        </ul>

        <div class="flex items-center gap-4">
          <button
            class="px-5 py-2.5 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            :disabled="busy ? false : !pendingCount"
            @click="busy ? pauseAll() : startUpload()"
          >
            {{ busy ? '暂停全部' : `开始上传${pendingCount ? `（${pendingCount} 个）` : ''}` }}
          </button>
          <p v-if="activeTask" class="text-xs text-slate-400">
            正在传：{{ activeTask.file.name }}
          </p>
          <p v-if="message.text" :class="message.kind === 'ok' ? 'text-emerald-600' : 'text-red-600'" class="text-sm font-medium">
            {{ message.text }}
          </p>
        </div>
      </section>

      <section class="bg-white rounded-lg shadow-sm border border-slate-200 p-6 flex flex-col gap-4">
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-bold text-slate-800 flex items-center gap-2">
            <FolderOpen :size="20" class="text-emerald-600" /> 当前目录文件
          </h2>
          <button
            class="flex items-center gap-1.5 text-sm text-slate-500 hover:text-blue-600 font-medium"
            @click="refreshFiles()"
          >
            <RefreshCw :size="15" /> 刷新
          </button>
        </div>
        <p class="text-xs text-slate-400 font-mono break-all">{{ filesRoot }}</p>
        <div v-if="!files.length" class="text-sm text-slate-400 py-4 text-center">该目录暂无文件</div>
        <ul v-else class="divide-y divide-slate-100 max-h-72 overflow-y-auto">
          <li v-for="item in files" :key="item.path" class="py-2.5 flex items-center justify-between gap-4 text-sm">
            <span class="font-mono text-slate-700 break-all">{{ item.path }}</span>
            <span class="text-slate-400 whitespace-nowrap">{{ formatSize(item.size) }}</span>
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>
