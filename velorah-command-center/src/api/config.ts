/**
 * SmartPark ALPR — API Configuration
 * Tập trung toàn bộ endpoint URLs để dễ bảo trì.
 *
 * Khi chạy `npm run dev`, Vite proxy sẽ forward /api → localhost:8000
 * Khi deploy production (Apache), reverse proxy sẽ xử lý.
 */

// Base URL — Vite proxy xử lý trong dev, empty string = relative URL
export const BASE_URL = '';

// REST Endpoints
export const API = {
  /** GET  — Kiểm tra trạng thái hệ thống (DB, YOLO, camera) */
  health: `${BASE_URL}/api/health`,

  /** GET  — Lịch sử xe ra vào từ bảng lichsuravao */
  logs: `${BASE_URL}/api/logs`,

  /** GET  — Thống kê: xe trong bãi, lượt vào/ra hôm nay */
  stats: `${BASE_URL}/api/stats`,

  /** GET  — Danh sách cư dân từ bảng cudan */
  residents: `${BASE_URL}/api/residents`,

  /** POST — Thêm cư dân mới */
  addResident: `${BASE_URL}/api/residents`,

  /** DELETE /api/residents/:id — Xóa cư dân theo ID */
  deleteResident: (id: number) => `${BASE_URL}/api/residents/${id}`,

  /** GET  — MJPEG stream từ ESP32-CAM (proxy qua FastAPI) */
  videoFeed: `${BASE_URL}/api/video_feed`,

  /** POST — Gửi lệnh điều khiển barrier từ frontend */
  iotTrigger: `${BASE_URL}/api/iot/trigger`,

  /** POST — Cập nhật IP của ESP32-CAM */
  cameraIp: `${BASE_URL}/api/config/camera_ip`,

  /** POST — Cập nhật IP của ESP8266 */
  esp8266Ip: `${BASE_URL}/api/config/esp8266_ip`,

  /** POST — V1 entry request (gọi từ frontend thủ công) */
  entryRequest: `${BASE_URL}/api/v1/entry-request`,

  /** POST — Xử lý frame hiện tại đang có trong buffer server */
  detectCurrent: `${BASE_URL}/api/detect_current`,
} as const;

// WebSocket URL — KHÔNG đi qua Vite proxy, cần URL đầy đủ
export const WS_URL = 'ws://localhost:8000/ws/live';

// Polling intervals (ms)
export const POLL_STATS_INTERVAL = 10_000;   // 10 giây
export const POLL_LOGS_INTERVAL  = 5_000;    // 5 giây (fallback khi WS offline)
