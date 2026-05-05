/**
 * SmartPark ALPR — Typed API Client
 * Cung cấp các typed fetch helpers cho toàn bộ ứng dụng.
 */

import { API } from './config';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface LogEntry {
  id: number;
  bien_so_xe: string;
  thoi_gian: string;        // ISO 8601 string từ backend
  trang_thai: 'Vao' | 'Ra' | 'Tu choi';
  hinh_anh?: string | null; // base64 ảnh biển số (có thể null)
}

export interface Stats {
  inside: number;
  entries_today: number;
  exits_today: number;
  strangers_today: number;
}

export interface Resident {
  id: number;
  bien_so_xe: string;
  ten_chu_xe: string;
  so_can_ho: string;
}

export interface DetectionResult {
  detected: boolean;
  processed?: boolean;
  plate?: string;
  matched_plate?: string | null;
  confidence?: number;
  bbox?: [number, number, number, number]; // [x1, y1, x2, y2]
  owner?: string | null;
  can_ho?: string;
  trang_thai?: string;
  is_resident?: boolean;
  is_fuzzy?: boolean;
  barrier_opened?: boolean;
  plate_image?: string;      // data:image/jpeg;base64,...
  timestamp?: string;
  processing_ms?: number;    // Thời gian xử lý (ms)
  reason?: string;
  triggered?: boolean;
  action?: 'OPEN' | 'DENY'; // V1 barrier command
}

export interface SystemHealth {
  status: string;
  db: string;
  yolo: string;
  char_model: string;
  ocr: string;
  gpu: boolean;
  camera_ip: string;
  esp8266_ip: string;
  usb_mode: boolean;
  camera_connected: boolean;
  iot_processing: boolean;
}

export interface ResidentCreate {
  bien_so_xe: string;
  ten_chu_xe: string;
  so_can_ho: string;
}

// ─── Generic Fetch Helper ─────────────────────────────────────────────────────

async function apiFetch<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`[API ${res.status}] ${detail}`);
  }
  return res.json() as Promise<T>;
}

// ─── API Methods ──────────────────────────────────────────────────────────────

/** Lấy trạng thái sức khỏe hệ thống */
export const fetchHealth = (): Promise<SystemHealth> =>
  apiFetch<SystemHealth>(API.health);

/**
 * Lấy lịch sử xe ra vào
 * @param limit   Số bản ghi (default 50)
 * @param status  'all' | 'Vao' | 'Ra' | 'Tu choi'
 * @param date    'all' | 'today' | 'week'
 */
export const fetchLogs = (
  limit = 50,
  status = 'all',
  date = 'all',
): Promise<LogEntry[]> =>
  apiFetch<LogEntry[]>(
    `${API.logs}?limit=${limit}&status=${status}&date=${date}`,
  );

/** Lấy thống kê xe */
export const fetchStats = (): Promise<Stats> =>
  apiFetch<Stats>(API.stats);

/** Lấy danh sách cư dân */
export const fetchResidents = (): Promise<Resident[]> =>
  apiFetch<Resident[]>(API.residents);

/** Thêm cư dân mới */
export const addResident = (data: ResidentCreate): Promise<{ success: boolean; id: number; message: string }> =>
  apiFetch(API.addResident, {
    method: 'POST',
    body: JSON.stringify(data),
  });

/** Xóa cư dân theo ID */
export const deleteResident = (id: number): Promise<{ success: boolean; message: string }> =>
  apiFetch(API.deleteResident(id), { method: 'DELETE' });

/**
 * Gửi lệnh kích hoạt barrier thủ công
 * Backend sẽ chụp frame từ ESP32-CAM → YOLO → báo kết quả qua WS
 */
export const triggerBarrier = (): Promise<DetectionResult> =>
  apiFetch<DetectionResult>(API.iotTrigger, {
    method: 'POST',
    body: JSON.stringify({}),
  });

/** Cập nhật IP của ESP32-CAM */
export const setCameraIp = (ip: string): Promise<{ success: boolean; camera_ip: string }> =>
  apiFetch(API.cameraIp, {
    method: 'POST',
    body: JSON.stringify({ ip }),
  });

/** Cập nhật IP của ESP8266 */
export const setEsp8266Ip = (ip: string): Promise<{ success: boolean; esp8266_ip: string }> =>
  apiFetch(API.esp8266Ip, {
    method: 'POST',
    body: JSON.stringify({ ip }),
  });

/** V1: Gửi entry-request thủ công từ frontend */
export const triggerEntryRequest = (): Promise<DetectionResult> =>
  apiFetch<DetectionResult>(API.entryRequest, {
    method: 'POST',
    body: JSON.stringify({}),
  });
