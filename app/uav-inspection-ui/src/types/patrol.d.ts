// 预警规则配置
export interface AlertRule {
  enabled: boolean;
  level: 'yellow' | 'orange' | 'red';
  value: number;   // 阈值（人数）
  label: string;   // 显示名称
}

// 当前预警状态
export interface AlertState {
  active: boolean;
  level: 'yellow' | 'orange' | 'red' | null;
  message: string;
}

// 遥测数据帧定义 (SRT解析后的单帧数据)
export interface TelemetryFrame {
  frameId: number;
  timestamp: string | number;
  longitude: number; // 经度 (WGS-84)
  latitude: number;  // 纬度 (WGS-84)
  altitude: number;  // 相对高度 (米)
  pitch: number;     // 俯仰角
  roll: number;      // 横滚角
  yaw: number;       // 偏航角
}

// YOLO+ByteTrack 目标检测与追踪数据
export interface TrackTarget {
  trackId: number;
  classId: number; // 如: 0 为 person
  bbox: [number, number, number, number]; // [x1, y1, x2, y2] 绝对像素坐标
  confidence: number;
  // 以下为前端结合遥测数据实时解算出的地理坐标（可选，通常由后端解算更严谨）
  geoLat?: number;
  geoLon?: number;
}
//WebSocket 实时推理数据包 
export interface WSFrameMessage {
  taskId: string;
  frameId: number;
  timestamp: string;
  totalCount: number;
  telemetry: TelemetryFrame;
  targets: TrackTarget[];
  isAlert: boolean;
  fps?: number;
  totalFrames?: number;
  alert?: AlertRecord;
  snapshot?: string; // 告警时的抓拍图 (Base64 字符串)
}

// 告警信息记录
export interface AlertRecord {
  id: string;
  timestamp: string;
  frameId: number;
  type: 'CROWD_DENSITY' | 'RESTRICTED_AREA';
  count: number;
  threshold: number;
  centerLon: number;
  centerLat: number;
  snapshotUrl: string;
  isRead: boolean;
}

// 巡检任务信息
export interface PatrolTask {
  taskId: string;
  taskName: string;
  uploadTime: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress?: number;
  videoUrl?: string;
  srtUrl?: string;
}

import * as L from 'leaflet';

declare module 'leaflet' {
  // 1. 定义热力图层实例的接口
  interface HeatLayer extends L.Layer {
    setLatLngs(latlngs: L.HeatLatLngTuple[]): this;
    addLatLng(latlng: L.HeatLatLngTuple): this;
    setOptions(options: HeatLayerOptions): this;
    redraw(): this;
  }

  // 2. 定义热力图配置项接口
  interface HeatLayerOptions {
    minOpacity?: number;
    maxZoom?: number;
    max?: number;
    radius?: number;
    blur?: number;
    gradient?: { [key: number]: string };
  }

  // 3. 将 heatLayer 函数挂载到 L 命名空间下
  function heatLayer(
    latlngs: L.HeatLatLngTuple[],
    options?: HeatLayerOptions
  ): HeatLayer;

  // 4. 定义元组类型（经度、纬度、强度）
  type HeatLatLngTuple = [number, number, number];
}

// 声明模块防止 import 报错
declare module 'leaflet.heat';