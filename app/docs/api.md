# UAV Inspection API (Pest)

## Base
- Base URL: http://127.0.0.1:8000/api/v1
- Content-Type: application/json
- Response envelope:

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

## 1. Implemented and Used

### 1.1 Get Telemetry (video-synced)
- Method: GET
- Path: /pest/telemetry
- Query:
  - video_time: int, seconds
- Response data:

```json
{
  "battery": 78.0,
  "signal": 92,
  "altitude": 15.4,
  "speed": 4.2,
  "satellites": 24,
  "mode": "3D FIX"
}
```

### 1.2 Get Pest Statistics
- Method: GET
- Path: /pest/statistics
- Response data:

```json
[
  { "name": "茶尺蠖", "value": 12 },
  { "name": "叶片病斑", "value": 6 },
  { "name": "异物遮挡", "value": 3 }
]
```

### 1.3 Video Stream
- Method: GET
- Path: /pest/video
- Response: video/mp4 stream

### 1.4 Video Frames (MJPEG)
- Method: GET
- Path: /pest/video/frames
- Response: multipart/x-mixed-replace; boundary=frame

### 1.5 Push Video Frame (JPEG)
- Method: POST
- Path: /pest/video/push
- Body: image/jpeg raw bytes or multipart form-data `frame`
- Response data:

```json
{ "size": 123456 }
```

### 1.6 Mission Control
- Method: POST
- Path: /pest/mission/control
- Body:

```json
{
  "command": "start",
  "params": { "route_id": "route_a" }
}
```

- Response data:

```json
{ "status": "processing" }
```

## 2. Proposed (UI-aligned)

### 2.1 Routes
- GET /pest/routes
  - Returns list of routes
- POST /pest/routes/{id}/activate
  - Activate a route

Route item:

```json
{
  "id": "route_a",
  "name": "A区茶园自主巡检航线",
  "waypoints": 35,
  "duration_min": 24,
  "area_mu": 20,
  "status": "running"
}
```

### 2.2 Vision Models
- GET /pest/models
- POST /pest/models/{id}/activate

Model item:

```json
{
  "id": "yolo_v8_edge",
  "name": "YOLO-v8 目标检测模型",
  "runtime": "edge",
  "status": "active"
}
```

### 2.3 Reports
- GET /pest/reports
- GET /pest/reports/{id}/download

Report item:

```json
{
  "id": "rep_20260429_a",
  "title": "20260429_A区茶园病虫害评估报告",
  "generated_at": "2026-05-06T14:30:00+08:00",
  "format": "pdf",
  "attachment_count": 12
}
```

### 2.4 Missions
- POST /pest/missions
- GET /pest/missions/{id}
- POST /pest/missions/{id}/cancel

Mission detail:

```json
{
  "id": "mis_001",
  "name": "A区茶园巡检任务",
  "status": "running",
  "route_id": "route_a",
  "model_id": "yolo_v8_edge",
  "created_at": "2026-05-06T12:00:00+08:00",
  "scheduled_at": "2026-05-06T12:10:00+08:00"
}
```

## 3. WebSocket (optional)

### 3.1 Agent Chat
- WS: ws://127.0.0.1:8000/ws/v1/agent/chat

Inbound:

```json
{ "role": "user", "content": "查看当前异常点" }
```

Outbound:

```json
{ "role": "agent", "content": "已检索异常点位，建议调整视角。", "type": "info" }
```

### 3.2 System Logs
- WS: ws://127.0.0.1:8000/ws/v1/system/logs

Outbound:

```json
{
  "time": "12:32:52",
  "level": "WARNING",
  "tag": "视点决策",
  "message": "目标区域叶片遮挡度 > 30%"
}
```

### 3.3 Telemetry Stream
- WS: ws://127.0.0.1:8000/ws/v1/pest/telemetry

Outbound:

```json
{
  "video_time": 128,
  "battery": 78,
  "signal": 92,
  "altitude": 15.4,
  "speed": 4.2,
  "satellites": 24,
  "mode": "3D FIX"
}
```
