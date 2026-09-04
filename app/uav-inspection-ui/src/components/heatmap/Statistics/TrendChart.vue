<template>
  <div ref="chartRef" class="w-full h-full min-h-[200px]"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef } from 'vue';
import * as echarts from 'echarts';

const props = defineProps<{
  historyData: (number | null)[]; 
  predictData: (number | null)[]; 
  timeLabels: string[];  // X轴时间标签
}>();

const chartRef = ref<HTMLElement | null>(null);
const chartInstance = shallowRef<echarts.ECharts | null>(null);

const initChart = () => {
  if (!chartRef.value) return;
  chartInstance.value = echarts.init(chartRef.value);
  updateChart();
};

const updateChart = () => {
  if (!chartInstance.value) return;
  
  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.timeLabels,
      axisLine: { lineStyle: { color: '#94a3b8' } }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
    },
    series: [
      {
        name: '实际客流',
        type: 'line',
        smooth: true,
        data: props.historyData,
        itemStyle: { color: '#0ea5e9' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(14,165,233,0.3)' },
            { offset: 1, color: 'rgba(14,165,233,0.0)' }
          ])
        }
      },
      {
        name: '预测趋势',
        type: 'line',
        smooth: true,
        lineStyle: { type: 'dashed', color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
        data: props.predictData
      }
    ]
  };
  chartInstance.value.setOption(option);
};

// 监听数据变化重绘图表
watch([() => props.historyData, () => props.predictData, () => props.timeLabels], () => {
  updateChart();
}, { deep: true });

// 处理窗口缩放
const handleResize = () => {
  chartInstance.value?.resize();
};

onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (chartInstance.value) {
    chartInstance.value.dispose();
  }
});
</script>