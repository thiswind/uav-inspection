import { ref, computed } from 'vue';
import type { AlertRecord } from '../types/patrol';

export function useAlertSystem(densityThreshold: number = 50) {
  const alerts = ref<AlertRecord[]>([]);
  const unreadCount = computed(() => alerts.value.filter(a => !a.isRead).length);

  // 接收实时推送或轮询到的新数据并进行判定
  const processNewDetection = (frameId: number, timestamp: string, currentCount: number, lat: number, lon: number, snapshot: string) => {
    if (currentCount >= densityThreshold) {
      const newAlert: AlertRecord = {
        id: `alert_${Date.now()}_${frameId}`,
        timestamp,
        frameId,
        type: 'CROWD_DENSITY',
        count: currentCount,
        threshold: densityThreshold,
        centerLat: lat,
        centerLon: lon,
        snapshotUrl: snapshot,
        isRead: false
      };
      
      // 将新告警推入队列头部
      alerts.value.unshift(newAlert);
      
      // 可选：限制最大告警数量防止内存溢出
      if (alerts.value.length > 100) {
        alerts.value.pop();
      }
      
      return newAlert; // 返回新告警以供外部触发系统级通知 (如音效)
    }
    return null;
  };

  const markAsRead = (alertId: string) => {
    const alert = alerts.value.find(a => a.id === alertId);
    if (alert) alert.isRead = true;
  };

  const clearAll = () => {
    alerts.value = [];
  };

  const addAlert = (alert: AlertRecord) => {
    alerts.value.unshift({ ...alert, isRead: alert.isRead ?? false });
    if (alerts.value.length > 100) {
      alerts.value.pop();
    }
  };

  const setAlerts = (items: AlertRecord[]) => {
    alerts.value = items.map(item => ({ ...item, isRead: item.isRead ?? false }));
  };

  return {
    alerts,
    unreadCount,
    densityThreshold,
    processNewDetection,
    markAsRead,
    clearAll,
    addAlert,
    setAlerts
  };
}