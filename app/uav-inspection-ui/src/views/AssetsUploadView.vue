<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, FolderOpen, HardDriveUpload, RefreshCw, UploadCloud } from 'lucide-vue-next'
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

interface UploadResult {
  category: string
  dir: string
  saved: { name: string; size: number }[]
  skipped: { name: string; reason: string }[]
}

const router = useRouter()
const categories = ref<CategoryOption[]>([])
const category = ref('')
const subdir = ref('')
const overwrite = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const pickedFiles = ref<File[]>([])
const busy = ref(false)
const message = reactive({ kind: '' as '' | 'ok' | 'err', text: '' })
const files = ref<FileEntry[]>([])
const filesRoot = ref('')

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
  pickedFiles.value = Array.from(input.files ?? [])
}

async function submitUpload() {
  if (!category.value) {
    message.kind = 'err'
    message.text = '请选择素材分类'
    return
  }
  if (!pickedFiles.value.length) {
    message.kind = 'err'
    message.text = '请先选择文件'
    return
  }
  const form = new FormData()
  form.append('category', category.value)
  form.append('subdir', subdir.value.trim())
  form.append('overwrite', overwrite.value ? 'true' : 'false')
  pickedFiles.value.forEach(file => form.append('files', file, file.name))
  busy.value = true
  message.kind = ''
  message.text = ''
  try {
    const res = await http.postForm<UploadResult>('/assets/upload', form)
    const data = res.data
    const skippedNote = data.skipped.length ? `，跳过 ${data.skipped.length} 个（重名未覆盖）` : ''
    message.kind = 'ok'
    message.text = `已保存 ${data.saved.length} 个文件到 ${data.dir}${skippedNote}`
    pickedFiles.value = []
    if (fileInput.value) fileInput.value.value = ''
    await refreshFiles()
  } catch (error) {
    message.kind = 'err'
    message.text = `上传失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    busy.value = false
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
          <HardDriveUpload :size="18" /> 演示素材灌入 · 二阶段
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
          <input ref="fileInput" type="file" multiple class="hidden" @change="onPick" />
          <FolderOpen :size="34" class="mx-auto text-slate-400 mb-2" />
          <p v-if="!pickedFiles.length" class="text-sm text-slate-500">
            点击选择文件（可多选：视频 / 模型 / 图片 / 测量数据）
          </p>
          <p v-else class="text-sm text-slate-700 font-medium">
            已选 {{ pickedFiles.length }} 个文件：
            <span class="font-mono text-xs">{{ pickedFiles.map(f => f.name).join('、') }}</span>
          </p>
        </label>

        <div class="flex items-center gap-4">
          <button
            class="px-5 py-2.5 rounded-md bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            :disabled="busy"
            @click="submitUpload"
          >
            {{ busy ? '上传中…' : '开始上传' }}
          </button>
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
