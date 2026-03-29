import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Car, LogIn, LogOut, Activity, LayoutDashboard, Settings,
  Bell, Search, CheckCircle2, Clock, Video, Download,
  Camera, Cpu, Save, Filter, XCircle, Users, AlertTriangle,
  Wifi, WifiOff, RefreshCw, Plus, Trash2, Shield
} from 'lucide-react';

// ─── Types ──────────────────────────────────────────────────────────────────
type LogEntry = {
  id: number | string;
  bien_so_xe: string;
  thoi_gian: string;
  trang_thai: 'Vao' | 'Ra' | 'Tu choi';
  hinh_anh?: string;
};

type Stats = {
  inside: number;
  entries_today: number;
  exits_today: number;
  strangers_today: number;
};

type DetectionResult = {
  detected: boolean;
  processed?: boolean;
  plate?: string;
  matched_plate?: string;
  confidence?: number;
  bbox?: [number, number, number, number];
  owner?: string;
  can_ho?: string;
  trang_thai?: string;
  is_resident?: boolean;
  barrier_opened?: boolean;
  is_fuzzy?: boolean;
  timestamp?: string;
  error?: string;
  reason?: string;
};

type Resident = {
  id: number;
  bien_so_xe: string;
  ten_chu_xe: string;
  so_can_ho: string;
};

// ─── API Base URL (thông qua Vite proxy) ────────────────────────────────────
const API_BASE = '/api';
const WS_URL = `ws://${window.location.host}/ws/live`;

// ─── API helpers ─────────────────────────────────────────────────────────────
const apiFetch = async <T,>(path: string, options?: RequestInit): Promise<T> => {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
};

// ════════════════════════════════════════════════════════════════════════════
export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'history' | 'residents' | 'settings'>('dashboard');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<Stats>({ inside: 0, entries_today: 0, exits_today: 0, strangers_today: 0 });
  const [residents, setResidents] = useState<Resident[]>([]);
  const [apiStatus, setApiStatus] = useState<'connecting' | 'online' | 'offline'>('connecting');
  const [latestDetection, setLatestDetection] = useState<DetectionResult | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logFilter, setLogFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  // New resident form
  const [newResident, setNewResident] = useState({ bien_so_xe: '', ten_chu_xe: '', so_can_ho: '' });
  const [addingResident, setAddingResident] = useState(false);
  const [addError, setAddError] = useState('');
  const [cameraMode, setCameraMode] = useState<'webcam' | 'esp32'>('esp32');
  const [lowLatency, setLowLatency] = useState(false);
  const [cameraIp, setCameraIp] = useState('172.20.10.2');
  const [isUpdatingIp, setIsUpdatingIp] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const captureIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // ── Health check ──────────────────────────────────────────────────────────
  const checkHealth = useCallback(async () => {
    try {
      await apiFetch('/health');
      setApiStatus('online');
    } catch {
      setApiStatus('offline');
    }
  }, []);

  // ── Load stats ────────────────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    try {
      const data = await apiFetch<Stats>('/stats');
      setStats(data);
    } catch (e) {
      console.warn('Stats fetch fail:', e);
    }
  }, []);

  // ── Load logs ─────────────────────────────────────────────────────────────
  const loadLogs = useCallback(async (status = 'all') => {
    try {
      const data = await apiFetch<LogEntry[]>(`/logs?limit=100&status=${status}&date=all`);
      setLogs(data);
    } catch (e) {
      console.warn('Logs fetch fail:', e);
    }
  }, []);

  // ── Load residents ────────────────────────────────────────────────────────
  const loadResidents = useCallback(async () => {
    try {
      const data = await apiFetch<Resident[]>('/residents');
      setResidents(data);
    } catch (e) {
      console.warn('Residents fetch fail:', e);
    }
  }, []);

  // ── WebSocket setup ───────────────────────────────────────────────────────
  const setupWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(WS_URL);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        // Backend expert worker sends data directly
        if (msg.detected && msg.processed) {
          setLatestDetection(msg);
          loadLogs();
          loadStats();
          
          // Toast or Notification logic can go here
          console.log("Push Detection:", msg.plate);
        }
      } catch (err) {
        console.warn("WS Message error:", err);
      }
    };
    ws.onopen = () => setApiStatus('online');
    ws.onclose = () => setTimeout(setupWebSocket, 3000);
    ws.onerror = () => setApiStatus('offline');
    wsRef.current = ws;
  }, [loadStats]);

  // ── Camera setup ──────────────────────────────────────────────────────────
  useEffect(() => {
    let active = true;
    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720, facingMode: 'environment' }
        });
        if (!active) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error('Camera error:', err);
      }
    };

    if (activeTab === 'dashboard' && cameraMode === 'webcam') startCamera();
    return () => {
      active = false;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
    };
  }, [activeTab]);

  // ── Auto-capture & send frame tới AI ─────────────────────────────────────
  useEffect(() => {
    if (activeTab !== 'dashboard' || apiStatus !== 'online') {
      if (captureIntervalRef.current) clearInterval(captureIntervalRef.current);
      return;
    }

    const sendFrame = async () => {
      // Chỉ chạy polling gửi ảnh nếu đang dùng WEBCAM
      if (cameraMode !== 'webcam') return;
      
      if (!videoRef.current || !canvasRef.current || isProcessing) return;
      // ... keep existing webcam logic
    };

    // Nếu là webcam, poll nhanh (500ms). Nếu là esp32, backend tự đẩy, ko cần poll.
    if (cameraMode === 'webcam') {
        captureIntervalRef.current = setInterval(sendFrame, 1000);
    }
    return () => {
      if (captureIntervalRef.current) clearInterval(captureIntervalRef.current);
    };
  }, [activeTab, apiStatus, isProcessing]);

  // ── Initial data load ─────────────────────────────────────────────────────
  useEffect(() => {
    checkHealth();
    loadStats();
    loadLogs();
    setupWebSocket();
    const statInterval = setInterval(() => { loadStats(); checkHealth(); }, 10_000);
    return () => {
      clearInterval(statInterval);
      wsRef.current?.close();
    };
  }, [checkHealth, loadStats, loadLogs, setupWebSocket]);

  useEffect(() => {
    if (activeTab === 'history') loadLogs(logFilter);
    if (activeTab === 'residents') loadResidents();
  }, [activeTab, logFilter, loadLogs, loadResidents]);

  // ── Add resident ──────────────────────────────────────────────────────────
  const handleAddResident = async () => {
    if (!newResident.bien_so_xe || !newResident.ten_chu_xe) {
      setAddError('Biển số và tên chủ xe là bắt buộc');
      return;
    }
    setAddingResident(true);
    setAddError('');
    try {
      await apiFetch('/residents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newResident),
      });
      setNewResident({ bien_so_xe: '', ten_chu_xe: '', so_can_ho: '' });
      loadResidents();
    } catch (e: any) {
      setAddError(e.message);
    } finally {
      setAddingResident(false);
    }
  };

  // ── Delete resident ───────────────────────────────────────────────────────
  const handleDeleteResident = async (id: number) => {
    if (!confirm('Xóa cư dân này?')) return;
    try {
      await apiFetch(`/residents/${id}`, { method: 'DELETE' });
      loadResidents();
    } catch (e: any) {
      alert('Lỗi xóa: ' + e.message);
    }
  };

  // ── Filtered logs ─────────────────────────────────────────────────────────
  const filteredLogs = logs.filter(l => {
    const q = searchQuery.toLowerCase();
    return !q || l.bien_so_xe.toLowerCase().includes(q);
  });

  // ── Status tag helper ─────────────────────────────────────────────────────
  const TrangThaiTag = ({ trang_thai }: { trang_thai: string }) => {
    if (trang_thai === 'Vao') return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700">
        <LogIn size={11} /> VÀO
      </span>
    );
    if (trang_thai === 'Ra') return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-orange-100 text-orange-700">
        <LogOut size={11} /> RA
      </span>
    );
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-700">
        <XCircle size={11} /> TỪ CHỐI
      </span>
    );
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-slate-50 font-sans text-slate-900">
      {/* Hidden canvas dùng để capture frame */}
      <canvas ref={canvasRef} className="hidden" />

      {/* ── Sidebar ── */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0">
        <div className="p-5 flex items-center gap-3 border-b border-slate-100">
          <div className="w-9 h-9 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-sm">
            <Car size={20} />
          </div>
          <div>
            <h1 className="font-bold text-base tracking-tight">SmartPark</h1>
            <p className="text-[11px] text-slate-500 font-medium">ALPR System v2.0</p>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          <NavItem icon={<LayoutDashboard size={18} />} label="Tổng quan" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
          <NavItem icon={<Activity size={18} />} label="Lịch sử xe" active={activeTab === 'history'} onClick={() => setActiveTab('history')} />
          <NavItem icon={<Users size={18} />} label="Cư dân" active={activeTab === 'residents'} onClick={() => setActiveTab('residents')} />
          <NavItem icon={<Settings size={18} />} label="Cài đặt" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
        </nav>

        {/* API Status */}
        <div className="p-4 border-t border-slate-100">
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold ${
            apiStatus === 'online' ? 'bg-emerald-50 text-emerald-700' :
            apiStatus === 'offline' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'
          }`}>
            {apiStatus === 'online' ? <Wifi size={14} /> : apiStatus === 'offline' ? <WifiOff size={14} /> : <RefreshCw size={14} className="animate-spin" />}
            {apiStatus === 'online' ? 'API: Kết nối' : apiStatus === 'offline' ? 'API: Mất kết nối' : 'Đang kết nối...'}
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-8 shrink-0">
          <h2 className="text-lg font-semibold tracking-tight">
            {activeTab === 'dashboard' && 'Giám sát Trực tiếp'}
            {activeTab === 'history' && 'Lịch sử Ra Vào'}
            {activeTab === 'residents' && 'Quản lý Cư dân'}
            {activeTab === 'settings' && 'Cài đặt Hệ thống'}
          </h2>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Tìm biển số..."
                className="pl-9 pr-4 py-1.5 bg-slate-100 rounded-lg text-sm w-52 outline-none focus:bg-white focus:ring-2 focus:ring-indigo-200 transition-all"
              />
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-auto p-6">

          {/* ══════════ DASHBOARD ══════════ */}
          {activeTab === 'dashboard' && (
            <>
              {/* Stats */}
              <div className="grid grid-cols-4 gap-4 mb-6">
                <StatCard title="Xe trong bãi" value={stats.inside} icon={<Car size={20} className="text-indigo-600" />} color="indigo" />
                <StatCard title="Lượt vào hôm nay" value={stats.entries_today} icon={<LogIn size={20} className="text-emerald-600" />} color="emerald" />
                <StatCard title="Lượt ra hôm nay" value={stats.exits_today} icon={<LogOut size={20} className="text-orange-600" />} color="orange" />
                <StatCard title="Xe lạ hôm nay" value={stats.strangers_today} icon={<AlertTriangle size={20} className="text-red-500" />} color="red" />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Camera */}
                <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
                  <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
                    <h3 className="font-semibold text-slate-800 flex items-center gap-2 text-sm">
                      <Video size={16} className="text-slate-500" />
                      Camera {cameraMode === 'esp32' ? 'ESP32-CAM (IP)' : 'Cổng Chính (Webcam)'}
                    </h3>
                    <div className="flex items-center gap-2">
                      <div className="flex bg-slate-100 p-0.5 rounded-lg mr-2">
                        <button
                          onClick={() => setCameraMode('webcam')}
                          className={`px-2 py-0.5 text-[10px] font-bold rounded-md transition-all ${cameraMode === 'webcam' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                          WEBCAM
                        </button>
                        <button
                          onClick={() => setCameraMode('esp32')}
                          className={`px-2 py-0.5 text-[10px] font-bold rounded-md transition-all ${cameraMode === 'esp32' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                        >
                          ESP32
                        </button>
                      </div>
                      {isProcessing && (
                        <span className="text-xs text-indigo-600 font-medium flex items-center gap-1">
                          <RefreshCw size={12} className="animate-spin" />
                          Đang nhận diện...
                        </span>
                      )}
                      {cameraMode === 'esp32' && (
                        <div className="flex items-center gap-1">
                          <input 
                            type="text" 
                            value={cameraIp}
                            onChange={(e) => setCameraIp(e.target.value)}
                            className="text-[10px] w-20 px-1 py-0.5 rounded border border-slate-200 outline-none focus:border-indigo-400"
                            placeholder="IP Camera"
                          />
                          <button 
                            onClick={async () => {
                              setIsUpdatingIp(true);
                              try {
                                const res = await apiFetch<any>('/config/camera_ip', { 
                                  method: 'POST', 
                                  body: JSON.stringify({ ip: cameraIp }) 
                                });
                                if (res.success) alert("Đã cập nhật IP!");
                              } catch (e) {
                                alert("Lỗi kết nối");
                              } finally {
                                setIsUpdatingIp(false);
                              }
                            }}
                            disabled={isUpdatingIp}
                            className="bg-indigo-600 text-white text-[10px] px-2 py-0.5 rounded font-bold hover:bg-indigo-700 disabled:opacity-50"
                          >
                            SET
                          </button>
                          <button
                            onClick={() => setLowLatency(!lowLatency)}
                            className={`text-[10px] px-2 py-0.5 rounded-full font-bold transition-all ${
                              lowLatency
                                ? 'bg-amber-100 text-amber-700 border border-amber-200'
                                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                            }`}
                          >
                            {lowLatency ? '⚡ LIVE' : '⚡ ?'}
                          </button>
                        </div>
                      )}
                      <span className="relative flex h-2.5 w-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
                      </span>
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Live</span>
                    </div>
                  </div>

                  <div className="relative bg-slate-900 flex-1 min-h-[380px]">
                    {cameraMode === 'webcam' ? (
                      <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        className="absolute inset-0 w-full h-full object-cover"
                      />
                    ) : (
                      <img
                        src={lowLatency ? `http://${cameraIp}:81/stream` : "/api/video_feed"}
                        className="absolute inset-0 w-full h-full object-contain bg-black"
                        alt="ESP32 Stream"
                        onError={(e) => {
                          if (lowLatency) {
                            console.warn("Direct stream failed, falling back to proxy...");
                            setLowLatency(false);
                          } else {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/640x480?text=Camera+Offline';
                          }
                        }}
                      />
                    )}

                    {/* Bounding box overlay khi detect được */}
                    {latestDetection?.detected && latestDetection.bbox && (
                      <BBoxOverlay detection={latestDetection} videoRef={videoRef} isIPCam={cameraMode === 'esp32'} />
                    )}
                    
                    {/* Status overlay góc dưới */}
                    {latestDetection?.processed && (
                      <div className={`absolute bottom-3 left-3 right-3 px-4 py-2.5 rounded-xl backdrop-blur-sm text-white text-sm font-semibold flex items-center gap-3 ${
                        latestDetection.is_resident
                          ? 'bg-emerald-600/85'
                          : 'bg-red-600/85'
                      }`}>
                        {latestDetection.is_resident ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
                        <div className="flex-1">
                          <div className="font-bold font-mono">{latestDetection.matched_plate || latestDetection.plate}</div>
                          <div className="text-xs opacity-90">
                            {latestDetection.is_resident
                              ? `✅ ${latestDetection.owner} — ${latestDetection.trang_thai === 'Vao' ? 'Vào bãi' : 'Ra bãi'}${latestDetection.barrier_opened ? ' · Barrier mở' : ''}`
                              : '⚠️ Xe lạ — Từ chối'}
                          </div>
                        </div>
                        <div className="text-xs opacity-70">
                          {(latestDetection.confidence! * 100).toFixed(0)}%
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Recent logs */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col max-h-[500px]">
                  <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
                    <h3 className="font-semibold text-sm text-slate-800 flex items-center gap-2">
                      <Clock size={15} className="text-slate-500" />
                      Hoạt động gần đây
                    </h3>
                    <button onClick={() => setActiveTab('history')} className="text-xs text-indigo-600 font-semibold hover:underline">
                      Xem tất cả
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto divide-y divide-slate-50">
                    {logs.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-40 text-slate-400">
                        <Activity size={28} className="mb-2 opacity-40" />
                        <p className="text-xs">Chưa có dữ liệu</p>
                      </div>
                    ) : logs.slice(0, 15).map(log => (
                      <React.Fragment key={log.id}>
                        <LogRow log={log} />
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ══════════ HISTORY ══════════ */}
          {activeTab === 'history' && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col" style={{ height: 'calc(100vh - 120px)' }}>
              <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-3 bg-slate-50/50">
                <div className="relative">
                  <Filter className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                  <select
                    value={logFilter}
                    onChange={e => { setLogFilter(e.target.value); }}
                    className="pl-8 pr-6 py-1.5 bg-white border border-slate-200 text-xs rounded-lg outline-none focus:border-indigo-500 font-medium text-slate-700 appearance-none"
                  >
                    <option value="all">Tất cả</option>
                    <option value="Vao">Chỉ xe vào</option>
                    <option value="Ra">Chỉ xe ra</option>
                    <option value="Tu choi">Xe lạ</option>
                  </select>
                </div>
                <button
                  onClick={() => loadLogs(logFilter)}
                  className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50"
                >
                  <RefreshCw size={13} /> Làm mới
                </button>
                <span className="ml-auto text-xs text-slate-500">{filteredLogs.length} bản ghi</span>
              </div>

              <div className="flex-1 overflow-auto">
                <table className="w-full text-left">
                  <thead className="sticky top-0 bg-white border-b border-slate-200">
                    <tr className="text-slate-500 text-xs uppercase tracking-wider">
                      <th className="px-5 py-3 font-medium">Biển số</th>
                      <th className="px-5 py-3 font-medium">Thời gian</th>
                      <th className="px-5 py-3 font-medium">Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 text-sm">
                    {filteredLogs.map(log => (
                      <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3 font-mono font-bold text-slate-900">
                          {log.bien_so_xe}
                        </td>
                        <td className="px-5 py-3 text-slate-600 text-xs">
                          {new Date(log.thoi_gian).toLocaleString('vi-VN')}
                        </td>
                        <td className="px-5 py-3">
                          <TrangThaiTag trang_thai={log.trang_thai} />
                        </td>
                      </tr>
                    ))}
                    {filteredLogs.length === 0 && (
                      <tr>
                        <td colSpan={3} className="text-center py-16 text-slate-400">
                          <Activity size={36} className="mx-auto mb-3 opacity-20" />
                          <p className="text-sm">Không có dữ liệu</p>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ══════════ RESIDENTS ══════════ */}
          {activeTab === 'residents' && (
            <div className="space-y-5">
              {/* Add form */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
                <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                  <Plus size={18} className="text-indigo-600" /> Thêm cư dân mới
                </h3>
                <div className="grid grid-cols-3 gap-3 mb-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Biển số xe *</label>
                    <input
                      type="text"
                      placeholder="VD: 30A-12345"
                      value={newResident.bien_so_xe}
                      onChange={e => setNewResident(p => ({ ...p, bien_so_xe: e.target.value.toUpperCase() }))}
                      className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Tên chủ xe *</label>
                    <input
                      type="text"
                      placeholder="Họ tên đầy đủ"
                      value={newResident.ten_chu_xe}
                      onChange={e => setNewResident(p => ({ ...p, ten_chu_xe: e.target.value }))}
                      className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1">Số căn hộ</label>
                    <input
                      type="text"
                      placeholder="VD: A1-01"
                      value={newResident.so_can_ho}
                      onChange={e => setNewResident(p => ({ ...p, so_can_ho: e.target.value }))}
                      className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                    />
                  </div>
                </div>
                {addError && <p className="text-red-600 text-xs mb-3">{addError}</p>}
                <button
                  onClick={handleAddResident}
                  disabled={addingResident}
                  className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {addingResident ? <RefreshCw size={15} className="animate-spin" /> : <Plus size={15} />}
                  Thêm cư dân
                </button>
              </div>

              {/* List */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <h3 className="font-semibold text-sm text-slate-800 flex items-center gap-2">
                    <Shield size={15} className="text-slate-500" />
                    Danh sách cư dân ({residents.length})
                  </h3>
                  <button onClick={loadResidents} className="text-xs text-indigo-600 font-semibold hover:underline">Làm mới</button>
                </div>
                <table className="w-full text-sm">
                  <thead className="border-b border-slate-100">
                    <tr className="text-slate-400 text-xs uppercase tracking-wider">
                      <th className="px-5 py-3 text-left font-medium">Biển số</th>
                      <th className="px-5 py-3 text-left font-medium">Chủ xe</th>
                      <th className="px-5 py-3 text-left font-medium">Căn hộ</th>
                      <th className="px-5 py-3 text-right font-medium">Hành động</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {residents.map(r => (
                      <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3 font-mono font-bold text-slate-900">{r.bien_so_xe}</td>
                        <td className="px-5 py-3 text-slate-700 font-medium">{r.ten_chu_xe}</td>
                        <td className="px-5 py-3 text-slate-500">{r.so_can_ho || '—'}</td>
                        <td className="px-5 py-3 text-right">
                          <button
                            onClick={() => handleDeleteResident(r.id)}
                            className="text-red-500 hover:text-red-700 hover:bg-red-50 p-1.5 rounded-lg transition-colors"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    ))}
                    {residents.length === 0 && (
                      <tr>
                        <td colSpan={4} className="text-center py-10 text-slate-400 text-sm">
                          Chưa có cư dân nào
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ══════════ SETTINGS ══════════ */}
          {activeTab === 'settings' && (
            <div className="max-w-2xl space-y-5">
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center text-indigo-600">
                    <Camera size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">Cấu hình Camera</h3>
                    <p className="text-xs text-slate-500">Webcam máy tính được sử dụng (không cần Arduino)</p>
                  </div>
                </div>
                <div className="p-5 space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-1.5">Tần suất gửi frame</label>
                    <select className="w-full bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100">
                      <option>Mỗi 2 giây (đang dùng)</option>
                      <option>Mỗi 1 giây</option>
                      <option>Mỗi 3 giây</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-600">
                    <Cpu size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">Thông tin hệ thống</h3>
                    <p className="text-xs text-slate-500">FastAPI tại localhost:8000 · PostgreSQL tại localhost:55432</p>
                  </div>
                </div>
                <div className="p-5 space-y-3 text-sm">
                  <InfoRow label="Backend" value="FastAPI + Uvicorn (localhost:8000)" />
                  <InfoRow label="Model YOLO" value="Plate_Detection_v12/weights/best.pt" />
                  <InfoRow label="OCR Engine" value="EasyOCR (Tiếng Việt)" />
                  <InfoRow label="Database" value="PostgreSQL :55432 / nhan_dien_bien_so_xe" />
                  <InfoRow label="Trạng thái API" value={apiStatus === 'online' ? '🟢 Đang kết nối' : '🔴 Mất kết nối'} />
                </div>
              </div>

              <div className="flex justify-end">
                <button className="flex items-center gap-2 bg-indigo-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors shadow-sm">
                  <Save size={16} /> Lưu cấu hình
                </button>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function NavItem({ icon, label, active = false, onClick }: {
  icon: React.ReactNode; label: string; active?: boolean; onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all ${
        active
          ? 'bg-indigo-50 text-indigo-700 border border-indigo-100 shadow-sm'
          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border border-transparent'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function StatCard({ title, value, icon, color }: {
  title: string; value: number; icon: React.ReactNode; color: string;
}) {
  const bg: Record<string, string> = {
    indigo: 'bg-indigo-50', emerald: 'bg-emerald-50', orange: 'bg-orange-50', red: 'bg-red-50'
  };
  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl ${bg[color] || 'bg-slate-50'} flex items-center justify-center shrink-0`}>
        {icon}
      </div>
      <div>
        <p className="text-xs font-medium text-slate-500 mb-0.5">{title}</p>
        <h4 className="text-2xl font-bold text-slate-900 tracking-tight">{value}</h4>
      </div>
    </div>
  );
}

function LogRow({ log }: { log: LogEntry }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
        log.trang_thai === 'Vao' ? 'bg-emerald-100 text-emerald-600' :
        log.trang_thai === 'Ra' ? 'bg-orange-100 text-orange-600' :
        'bg-red-100 text-red-600'
      }`}>
        {log.trang_thai === 'Vao' ? <LogIn size={15} /> : log.trang_thai === 'Ra' ? <LogOut size={15} /> : <XCircle size={15} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="font-mono font-bold text-slate-900 text-xs bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
            {log.bien_so_xe}
          </span>
          <span className="text-[11px] text-slate-400">
            {new Date(log.thoi_gian).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <p className={`text-[11px] mt-0.5 font-medium ${
          log.trang_thai === 'Vao' ? 'text-emerald-600' :
          log.trang_thai === 'Ra' ? 'text-orange-600' : 'text-red-600'
        }`}>
          {log.trang_thai === 'Vao' ? 'Đã vào bãi' : log.trang_thai === 'Ra' ? 'Đã ra bãi' : 'Xe lạ — Từ chối'}
        </p>
      </div>
    </div>
  );
}

function BBoxOverlay({ detection, videoRef, isIPCam = false }: {
  detection: DetectionResult;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isIPCam?: boolean;
}) {
  if (!detection.bbox) return null;
  
  // ESP32 cam thường có resolution khác, hoặc mirror. 
  // Ở đây ta dùng tỉ lệ dựa trên frame nhận được từ backend.
  const vw = isIPCam ? 640 : (videoRef.current?.videoWidth || 1280);
  const vh = isIPCam ? 480 : (videoRef.current?.videoHeight || 720);
  const [x1, y1, x2, y2] = detection.bbox;
  // Tính % vị trí relative
  const left = `${(x1 / vw * 100).toFixed(2)}%`;
  const top = `${(y1 / vh * 100).toFixed(2)}%`;
  const width = `${((x2 - x1) / vw * 100).toFixed(2)}%`;
  const height = `${((y2 - y1) / vh * 100).toFixed(2)}%`;
  const color = detection.is_resident ? '#10b981' : '#ef4444';

  return (
    <div className="absolute inset-0 pointer-events-none">
      <div style={{ position: 'absolute', left, top, width, height, border: `2px solid ${color}`, borderRadius: 4 }}>
        <div style={{
          position: 'absolute', top: -24, left: 0,
          background: color, color: '#fff', fontSize: 11,
          fontFamily: 'monospace', fontWeight: 700,
          padding: '2px 8px', borderRadius: 3, whiteSpace: 'nowrap'
        }}>
          {detection.matched_plate || detection.plate} · {((detection.confidence || 0) * 100).toFixed(0)}%
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-slate-50 last:border-0">
      <span className="text-slate-500 font-medium text-xs">{label}</span>
      <span className="text-slate-800 font-semibold text-xs text-right">{value}</span>
    </div>
  );
}
