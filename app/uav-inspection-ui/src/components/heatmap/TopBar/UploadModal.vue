<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm">
    <div class="w-[500px] bg-white rounded-xl shadow-2xl border border-cyan-100 overflow-hidden flex flex-col">
      <div class="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-gradient-to-r from-sky-50 to-white">
        <h3 class="text-lg font-bold text-slate-800">新建巡检分析任务</h3>
        <button @click="close" :disabled="uploadStatus === 'uploading'" class="text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-50">✕</button>
      </div>

      <div class="p-6 flex flex-col gap-5">
        <!-- 拖拽上传区 -->
        <div
          class="border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer"
          :class="isDragging ? 'border-cyan-500 bg-cyan-50' : 'border-slate-300 hover:border-cyan-400'"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <div class="text-4xl text-sky-500 mb-2">📥</div>
          <p class="text-slate-600 font-medium">将视频与SRT遥测文件拖拽至此处</p>
          <p class="text-slate-400 text-xs mt-1">支持格式: .mp4, .srt | SRT 遥测文件可选</p>

          <div class="mt-4 flex justify-center gap-2 text-sm flex-wrap">
            <span v-if="videoFile" class="bg-sky-100 text-sky-700 px-2 py-1 rounded">🎥 {{ videoFile.name }}</span>
            <span v-if="srtFile" class="bg-teal-100 text-teal-700 px-2 py-1 rounded">📄 {{ srtFile.name }}</span>
          </div>

          <input
            ref="fileInputRef"
            type="file"
            accept=".mp4,.MP4,.srt,.SRT"
            multiple
            class="hidden"
            @change="handleFileSelect"
          />
        </div>

        <!-- 进度展示区 -->
        <div v-if="uploadStatus !== 'idle'" class="w-full">
          <div class="flex justify-between text-xs text-slate-600 mb-1">
            <span>{{ statusText }}</span>
            <span>{{ uploadProgress }}%</span>
          </div>
          <div class="w-full bg-slate-100 rounded-full h-2">
            <div
              class="bg-gradient-to-r from-sky-500 to-cyan-400 h-2 rounded-full transition-all duration-300"
              :style="{ width: `${uploadProgress}%` }"
            ></div>
          </div>
        </div>

        <!-- 错误提示 -->
        <div v-if="errorMsg" class="text-red-500 text-sm bg-red-50 px-3 py-2 rounded-lg">
          {{ errorMsg }}
        </div>
      </div>

      <div class="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-3">
        <button @click="close" :disabled="uploadStatus === 'uploading'" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-200 rounded-md transition-colors disabled:opacity-50">取消</button>
        <button @click="submit" :disabled="!canSubmit" class="px-4 py-2 text-sm text-white bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-300 rounded-md transition-colors disabled:cursor-not-allowed">
          开始分析
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { uploadPatrolTask } from '../../../api1/heatmap/task';
const props = defineProps<{ visible: boolean }>();
const emit = defineEmits(['update:visible', 'submit-success']);

const isDragging = ref(false);
const videoFile = ref<File | null>(null);
const srtFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);

const uploadStatus = ref<'idle' | 'uploading' | 'starting' | 'done'>('idle');
const uploadProgress = ref(0);
const errorMsg = ref('');

// 只要有 MP4 就可以提交，SRT 可选
const canSubmit = computed(() => videoFile.value && uploadStatus.value === 'idle');

const statusText = computed(() => {
  const map: Record<string, string> = {
    idle: '',
    uploading: '正在上传视频文件...',
    starting: '后端正在启动推理引擎...',
    done: '任务已创建，正在进入分析...'
  };
  return map[uploadStatus.value];
});

const close = () => {
  if (uploadStatus.value === 'uploading') return;
  emit('update:visible', false);
  reset();
};

const reset = () => {
  videoFile.value = null;
  srtFile.value = null;
  uploadStatus.value = 'idle';
  uploadProgress.value = 0;
  errorMsg.value = '';
};

const handleDrop = (e: DragEvent) => {
  isDragging.value = false;
  const files = Array.from(e.dataTransfer?.files || []);
  processFiles(files);
};

const handleFileSelect = (e: Event) => {
  const input = e.target as HTMLInputElement;
  if (input.files) {
    processFiles(Array.from(input.files));
    input.value = '';
  }
};

const triggerFileInput = () => {
  fileInputRef.value?.click();
};

const processFiles = (files: File[]) => {
  files.forEach(file => {
    const lower = file.name.toLowerCase();
    if (lower.endsWith('.mp4')) videoFile.value = file;
    else if (lower.endsWith('.srt')) srtFile.value = file;
  });
};

const submit = async () => {
  if (!canSubmit.value || !videoFile.value) return;
  uploadStatus.value = 'uploading';
  errorMsg.value = '';

  try {
    // 1. 上传文件到后端（后端会自动保存并启动推理）
    const res = await uploadPatrolTask(
      videoFile.value,
      srtFile.value,
      (percent) => {
        uploadProgress.value = percent;
      }
    );

    uploadStatus.value = 'starting';
    uploadProgress.value = 100;

    // 2. 上传成功，通知主页面切换到新任务（立即开始实时分析）
    const taskId = res?.taskId || res;
    emit('submit-success', taskId);
    uploadStatus.value = 'done';

    // 3. 短暂延迟后关闭弹窗，让用户看到"任务已创建"提示
    setTimeout(() => {
      close();
    }, 600);

  } catch (error: any) {
    console.error('上传失败:', error);
    uploadStatus.value = 'idle';
    uploadProgress.value = 0;

    if (error?.code === 'ECONNABORTED') {
      errorMsg.value = '上传超时，请检查网络连接或尝试较小的视频文件';
    } else if (error?.response) {
      errorMsg.value = `服务器错误: ${error.response.status} ${error.response.statusText}`;
    } else {
      errorMsg.value = '上传失败，请确认后端服务正在运行（端口 8001）';
    }
  }
};
</script>
