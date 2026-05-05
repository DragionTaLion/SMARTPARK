/**
 * SmartPark Context — State đồng bộ toàn cục
 *
 * - Mount WebSocket /ws/live một lần duy nhất ở đây
 * - Poll /api/stats mỗi 30s, /api/logs mỗi 10s (fallback khi WS không push logs)
 * - Cung cấp: stats, logs, residents, latestDetection, systemStatus, triggerBarrier
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { WS_URL, POLL_STATS_INTERVAL, POLL_LOGS_INTERVAL } from '../api/config';
import {
  fetchStats,
  fetchLogs,
  fetchResidents,
  fetchHealth,
  triggerBarrier as apiTriggerBarrier,
  addResident as apiAddResident,
  deleteResident as apiDeleteResident,
  type Stats,
  type LogEntry,
  type Resident,
  type DetectionResult,
  type SystemHealth,
  type ResidentCreate,
} from '../api/client';

// ─── Context Type ─────────────────────────────────────────────────────────────

interface SmartParkContextType {
  // Data
  stats: Stats | null;
  logs: LogEntry[];
  residents: Resident[];
  latestDetection: DetectionResult | null;
  systemStatus: SystemHealth | null;

  // Connection state
  wsConnected: boolean;
  isLoading: boolean;

  // Actions
  triggerBarrier: () => Promise<DetectionResult>;
  addResident: (data: ResidentCreate) => Promise<void>;
  deleteResident: (id: number) => Promise<void>;
  refreshLogs: () => void;
  refreshResidents: () => void;
}

const SmartParkContext = createContext<SmartParkContextType | null>(null);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function SmartParkProvider({ children }: { children: React.ReactNode }) {
  const [stats, setStats]                     = useState<Stats | null>(null);
  const [logs, setLogs]                       = useState<LogEntry[]>([]);
  const [residents, setResidents]             = useState<Resident[]>([]);
  const [latestDetection, setLatestDetection] = useState<DetectionResult | null>(null);
  const [systemStatus, setSystemStatus]       = useState<SystemHealth | null>(null);
  const [wsConnected, setWsConnected]         = useState(false);
  const [isLoading, setIsLoading]             = useState(true);

  const wsRef         = useRef<WebSocket | null>(null);
  const reconnectRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Fetch helpers ──────────────────────────────────────────────────────────

  const loadStats = useCallback(async () => {
    try {
      const s = await fetchStats();
      setStats(s);
    } catch (e) {
      console.warn('[SmartPark] fetchStats error:', e);
    }
  }, []);

  const loadLogs = useCallback(async () => {
    try {
      const l = await fetchLogs(50);
      setLogs(l);
    } catch (e) {
      console.warn('[SmartPark] fetchLogs error:', e);
    }
  }, []);

  const loadResidents = useCallback(async () => {
    try {
      const r = await fetchResidents();
      setResidents(r);
    } catch (e) {
      console.warn('[SmartPark] fetchResidents error:', e);
    }
  }, []);

  const loadHealth = useCallback(async () => {
    try {
      const h = await fetchHealth();
      setSystemStatus(h);
    } catch (e) {
      console.warn('[SmartPark] fetchHealth error:', e);
    }
  }, []);

  // ── Initial Load ───────────────────────────────────────────────────────────

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await Promise.allSettled([loadStats(), loadLogs(), loadResidents(), loadHealth()]);
      setIsLoading(false);
    };
    init();
  }, [loadStats, loadLogs, loadResidents, loadHealth]);

  // ── Polling (fallback & stats refresh) ────────────────────────────────────

  useEffect(() => {
    const statsTimer = setInterval(loadStats,   POLL_STATS_INTERVAL);
    const logsTimer  = setInterval(loadLogs,    POLL_LOGS_INTERVAL);
    const hlthTimer  = setInterval(loadHealth,  60_000);
    return () => {
      clearInterval(statsTimer);
      clearInterval(logsTimer);
      clearInterval(hlthTimer);
    };
  }, [loadStats, loadLogs, loadHealth]);

  // ── WebSocket ──────────────────────────────────────────────────────────────

  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    console.log('[WS] Đang kết nối tới', WS_URL);
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[WS] Đã kết nối');
      setWsConnected(true);
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string);

        // Bỏ qua ping message
        if (data.type === 'ping') return;

        // Kết quả nhận diện mới — cập nhật UI ngay lập tức
        if (data.detected && data.plate) {
          setLatestDetection(data as DetectionResult);

          // Thêm vào đầu danh sách log (kể cả khi processed=false — auto detect)
          const newLog: LogEntry = {
            id: Date.now(),
            bien_so_xe: data.matched_plate || data.plate,
            thoi_gian: data.timestamp || new Date().toISOString(),
            trang_thai: (data.trang_thai as LogEntry['trang_thai']) || 'Tu choi',
            hinh_anh: data.plate_image || null,
          };
          setLogs(prev => [newLog, ...prev].slice(0, 100));

          // Cập nhật stats — chỉ khi đã hoàn tất pipeline (processed=true)
          if (data.processed) {
            loadStats();
            // Reload log từ server để đảm bảo đồng bộ DB
            loadLogs();
          }
        }
      } catch (e) {
        console.warn('[WS] Parse error:', e);
      }
    };

    ws.onerror = () => {
      console.warn('[WS] Lỗi kết nối');
      setWsConnected(false);
    };

    ws.onclose = () => {
      console.warn('[WS] Mất kết nối — thử lại sau 5s');
      setWsConnected(false);
      wsRef.current = null;
      reconnectRef.current = setTimeout(connectWS, 5000);
    };
  }, [loadStats]);

  useEffect(() => {
    connectWS();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connectWS]);

  // ── Actions ────────────────────────────────────────────────────────────────

  const triggerBarrier = useCallback(async (): Promise<DetectionResult> => {
    const result = await apiTriggerBarrier();
    if (result.processed) {
      await loadStats();
      await loadLogs();
    }
    return result;
  }, [loadStats, loadLogs]);

  const addResident = useCallback(async (data: ResidentCreate): Promise<void> => {
    await apiAddResident(data);
    await loadResidents();
  }, [loadResidents]);

  const deleteResident = useCallback(async (id: number): Promise<void> => {
    await apiDeleteResident(id);
    await loadResidents();
  }, [loadResidents]);

  return (
    <SmartParkContext.Provider value={{
      stats,
      logs,
      residents,
      latestDetection,
      systemStatus,
      wsConnected,
      isLoading,
      triggerBarrier,
      addResident,
      deleteResident,
      refreshLogs: loadLogs,
      refreshResidents: loadResidents,
    }}>
      {children}
    </SmartParkContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useSmartPark(): SmartParkContextType {
  const ctx = useContext(SmartParkContext);
  if (!ctx) throw new Error('useSmartPark must be used inside <SmartParkProvider>');
  return ctx;
}
