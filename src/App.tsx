import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Car, LogIn, LogOut, Activity, LayoutDashboard, Settings,
  Bell, Search, CheckCircle2, Clock, Video, Download,
  Camera, Cpu, Save, Filter, XCircle, Users, AlertTriangle,
  Wifi, WifiOff, RefreshCw, Plus, Trash2, Shield,
  Gamepad2, Info, Server, Database, Edit, LayoutGrid,
  Banknote, TrendingUp, Zap, Calendar, MapPin
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

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
  entry_image?: string; // Ảnh lúc vào để so sánh
  gate_id?: number;
  gate_name?: string;
};

type ParkingSlot = {
  slot_id: number;
  slot_name: string;
  status: boolean; // true: occupied, false: free
};

type Resident = {
  id: number;
  bien_so_xe: string;
  ten_chu_xe: string;
  so_can_ho: string;
  so_dien_thoai: string;
  da_thanh_toan: boolean;
  anh_dang_ky?: string;
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
  const [activeTab, setActiveTab] = useState<'dashboard' | 'history' | 'residents' | 'settings' | 'revenue' | 'parking_map'>(() => {
    return (localStorage.getItem('smartpark_active_tab') as any) || 'dashboard';
  });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<Stats>({ inside: 0, entries_today: 0, exits_today: 0, strangers_today: 0 });
  const [residents, setResidents] = useState<Resident[]>([]);
  const [apiStatus, setApiStatus] = useState<'connecting' | 'online' | 'offline'>('connecting');
  const [latestDetection, setLatestDetection] = useState<DetectionResult | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logFilter, setLogFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  // New resident form
  const [newResident, setNewResident] = useState({ id: null as number | null, bien_so_xe: '', ten_chu_xe: '', so_can_ho: '', so_dien_thoai: '', da_thanh_toan: false, anh_dang_ky: '', phi_thang: 500000 });
  const [selectedResident, setSelectedResident] = useState<Resident | null>(null);
  const [addingResident, setAddingResident] = useState(false);
  const [scanningForRegistration, setScanningForRegistration] = useState(false);
  const [addError, setAddError] = useState('');
  const [cameraMode, setCameraMode] = useState<'webcam' | 'esp32'>('esp32');
  const [gate1Ip, setGate1Ip] = useState(() => localStorage.getItem('smartpark_gate1_ip') || '192.168.0.102');
  const [gate2Ip, setGate2Ip] = useState(() => localStorage.getItem('smartpark_gate2_ip') || '192.168.0.102');
  const [esp8266Ip, setEsp8266Ip] = useState(() => localStorage.getItem('smartpark_esp8266_ip') || '192.168.0.105');
  const [sensorStates, setSensorStates] = useState<number[]>([0, 0, 0, 0, 0]);
  const [parkingSlots, setParkingSlots] = useState<ParkingSlot[]>([
    { slot_id: 1, slot_name: 'Ô số 1', status: false },
    { slot_id: 2, slot_name: 'Ô số 2', status: false },
    { slot_id: 3, slot_name: 'Ô số 3', status: false },
  ]);
  const [lastDetections, setLastDetections] = useState<Record<number, DetectionResult>>({});
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);
  const [revenueStats, setRevenueStats] = useState({ today: 0, month: 0, visitors_today: 0 });
  const [revenueHistory, setRevenueHistory] = useState<any[]>([]);
  const [revenueChart, setRevenueChart] = useState<any[]>([]);
  const [revenuePie, setRevenuePie] = useState<any[]>([]);
  // Visitor alert (xe khách vãng lai cần thu phí)
  const [visitorAlert, setVisitorAlert] = useState<{ plate: string; image: string; gate_id: number } | null>(null);
  const [visitorFeeDetail, setVisitorFeeDetail] = useState<{ fee: number; hours: number; entry_time: string } | null>(null);
  const [visitorFee, setVisitorFee] = useState(20000); // Mặc định 20k/lượt
  const [payingVisitor, setPayingVisitor] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

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

  // Toast helper
  const showToast = useCallback((msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const normalizePlateHelper = (plate: string) => {
    return (plate || "").toUpperCase().replace(/[.\-\s_]/g, "");
  };

  const findResidentName = (plate: string) => {
    const norm = normalizePlateHelper(plate);
    const res = residents.find(r => normalizePlateHelper(r.bien_so_xe) === norm);
    return res ? res.ten_chu_xe : "Khách lạ";
  };


  // Handle visitor payment
  const handleVisitorPay = useCallback(async () => {
    if (!visitorAlert) return;
    setPayingVisitor(true);
    try {
      const res = await apiFetch<{ success: boolean; so_tien: number }>('/visitor/pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bien_so_xe: visitorAlert.plate, gate_id: visitorAlert.gate_id }),
      });
      if (res.success) {
        showToast(`✅ Đã thu ${res.so_tien.toLocaleString()}đ — Mở cổng vào!`);
        setVisitorAlert(null);
        fetchRevenueData();
        loadLogs();
      }
    } catch (e: any) {
      showToast('❌ Lỗi thu phí: ' + e.message, 'error');
    } finally {
      setPayingVisitor(false);
    }
  }, [visitorAlert, showToast]);

  // Load visitor fee from server on mount
  useEffect(() => {
    apiFetch<{ visitor_fee: number }>('/config/fees').then(d => setVisitorFee(d.visitor_fee)).catch(() => { });
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

        // 0. Visitor alert — xe khách tại cổng vào hoặc cổng ra cần thu phí
        if (msg.visitor_alert && msg.plate) {
          setVisitorAlert({ plate: msg.plate, image: msg.image || '', gate_id: msg.gate_id });

          // Nếu ở cổng ra (gate 2), tự động gọi API tính phí
          if (msg.gate_id === 2) {
            apiFetch<{ fee: number; hours: number; entry_time: string }>(`/visitor/calculate_fee/${msg.plate}`)
              .then(data => setVisitorFeeDetail(data))
              .catch(() => setVisitorFeeDetail({ fee: 5000, hours: 1, entry_time: 'N/A' }));
          }
        }

        // 1. Nhận diện biển số
        if (msg.processed && msg.gate_id) {
          setLastDetections(prev => ({ ...prev, [msg.gate_id]: msg }));
          setLatestDetection(msg);
          loadLogs();
          loadStats();
        }

        // visitor_paid — bảo vệ vừa xác nhận thu phí
        if (msg.type === 'visitor_paid') {
          setVisitorAlert(null);
          setVisitorFeeDetail(null);
          loadLogs();
          fetchRevenueData();
        }

        // 2. Tín hiệu làm mới thống kê (Real-time stats)
        if (msg.type === 'refresh_stats') {
          loadStats();
          loadLogs(logFilter);
        }

        // 3. Trạng thái cảm biến & Ô đỗ (Từ Hardware API broadcast)
        if (msg.type === 'hardware_update') {
          setSensorStates(msg.sensors);
          // Cập nhật parking slots dựa trên bit cảm biến 3, 4, 5 (index 2,3,4)
          setParkingSlots(prev => prev.map((slot, idx) => ({
            ...slot,
            status: !!msg.sensors[idx + 2]
          })));
        }
      } catch (err) {
        console.warn("WS Message error:", err);
      }
    };
    ws.onopen = () => setApiStatus('online');
    ws.onclose = () => setTimeout(setupWebSocket, 3000);
    ws.onerror = () => setApiStatus('offline');
    wsRef.current = ws;
  }, [loadStats, loadLogs]);

  // ── Camera setup ──────────────────────────────────────────────────────────
  useEffect(() => {
    let active = true;

    const syncWithBackend = async () => {
      try {
        await apiFetch('/config/camera_source', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: cameraMode }),
        });
      } catch (err) {
        console.error('Failed to sync camera source with backend:', err);
      }
    };

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

    syncWithBackend();

    if (activeTab === 'dashboard' && cameraMode === 'webcam') startCamera();
    return () => {
      active = false;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
    };
  }, [activeTab, cameraMode]);

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

  // Ghi nhớ Tab khi thay đổi
  useEffect(() => {
    localStorage.setItem('smartpark_active_tab', activeTab);
  }, [activeTab]);

  // ── Initial data load ─────────────────────────────────────────────────────
  const fetchRevenueData = async () => {
    try {
      const stats = await apiFetch<any>('/revenue/stats');
      setRevenueStats(stats);
      const history = await apiFetch<any[]>('/revenue/history?limit=30');
      setRevenueHistory(history);
      const chart = await apiFetch<any[]>('/revenue/chart');
      setRevenueChart(chart);
      const pie = await apiFetch<any[]>('/revenue/by_type');
      setRevenuePie(pie);
    } catch (err) {
      console.error("Lỗi fetch revenue:", err);
    }
  };

  // ── Khởi tạo dữ liệu ban đầu (Chỉ chạy 1 lần khi mở Web) ───────────────────
  useEffect(() => {
    checkHealth();
    loadStats();
    loadLogs();
    loadResidents();
    setupWebSocket();

    // Interval nạp lại stats 
    const statInterval = setInterval(() => {
      loadStats();
      checkHealth();
    }, 15_000);

    return () => {
      clearInterval(statInterval);
      wsRef.current?.close();
    };
  }, [checkHealth, loadStats, loadLogs, setupWebSocket]);

  // Tải dữ liệu riêng cho từng Tab khi chuyển sang
  useEffect(() => {
    if (activeTab === 'revenue') fetchRevenueData();
    if (activeTab === 'residents') loadResidents();
    if (activeTab === 'history') loadLogs(logFilter);
  }, [activeTab, logFilter, loadResidents, loadLogs]);

  const handleManualOpen = async (gateId: number) => {
    try {
      await apiFetch(`/hardware/open_manual/${gateId}`, { method: 'POST' });
      showToast('Đã phát lệnh mở cổng thủ công!');
    } catch (err: any) {
      console.error("Lỗi mở cổng:", err);
      showToast('❌ Mở cổng thất bại: ' + err.message, 'error');
    }
  };

  const saveSystemConfig = async () => {
    setIsUpdatingConfig(true);
    try {
      await apiFetch('/config/system', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gate1_ip: gate1Ip, gate2_ip: gate2Ip, esp8266_ip: esp8266Ip }),
      });
      localStorage.setItem('smartpark_gate1_ip', gate1Ip);
      localStorage.setItem('smartpark_gate2_ip', gate2Ip);
      localStorage.setItem('smartpark_esp8266_ip', esp8266Ip);
      alert("Đã lưu cấu hình Hệ thống V2 thành công!");
    } catch (err: any) {
      alert("Lỗi khi lưu cấu hình: " + err.message);
    } finally {
      setIsUpdatingConfig(false);
    }
  };


  const handleDeleteRevenue = async (id: number) => {
    if (!confirm('Xóa giao dịch này?')) return;
    try {
      await apiFetch(`/revenue/${id}`, { method: 'DELETE' });
      showToast('✅ Đã xóa giao dịch');
      fetchRevenueData();
    } catch (e: any) {
      showToast('❌ Lỗi xóa: ' + e.message, 'error');
    }
  };


  const handleAddResident = async () => {
    if (!newResident.bien_so_xe || !newResident.ten_chu_xe) {
      setAddError('Biển số và tên chủ xe là bắt buộc');
      return;
    }
    setAddingResident(true);
    setAddError('');
    try {
      if (newResident.id) {
        // Cập nhật
        await apiFetch(`/residents/${newResident.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newResident),
        });
      } else {
        // Thêm mới
        await apiFetch('/residents', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newResident),
        });
      }
      setNewResident({ id: null, bien_so_xe: '', ten_chu_xe: '', so_can_ho: '', so_dien_thoai: '', da_thanh_toan: false, anh_dang_ky: '', phi_thang: 500000 });
      loadResidents();
    } catch (e: any) {
      setAddError(e.message);
    } finally {
      setAddingResident(false);
    }
  };

  const startEditResident = (r: Resident) => {
    setNewResident({
      id: r.id,
      bien_so_xe: r.bien_so_xe,
      ten_chu_xe: r.ten_chu_xe,
      so_can_ho: r.so_can_ho,
      so_dien_thoai: r.so_dien_thoai || '',
      da_thanh_toan: r.da_thanh_toan,
      anh_dang_ky: r.anh_dang_ky || ''
    });
    setAddError('');
  };

  const handleTogglePayment = async (id: number) => {
    try {
      const res = await apiFetch<{ success: boolean, da_thanh_toan: boolean }>(`/residents/${id}/toggle_payment`, { method: 'POST' });
      if (res.success) {
        setResidents(prev => prev.map(r => r.id === id ? { ...r, da_thanh_toan: res.da_thanh_toan } : r));
        if (selectedResident && selectedResident.id === id) {
          setSelectedResident(prev => prev ? { ...prev, da_thanh_toan: res.da_thanh_toan } : null);
        }
        // Tự động cập nhật lại dashboard doanh thu ngay lập tức
        fetchRevenueData();
      }
    } catch (e) {
      console.error("Toggle payment failed:", e);
    }
  };

  const handleScanResidentPlate = async () => {
    setScanningForRegistration(true);
    setAddError('');
    try {
      const result: { plate: string, plate_crop: string, detected: boolean } = await apiFetch('/scan_registration');
      if (result.detected) {
        setNewResident(prev => ({
          ...prev,
          bien_so_xe: result.plate,
          anh_dang_ky: result.plate_crop
        }));
      } else {
        setAddError("Không tìm thấy biển số trong khung hình camera");
      }
    } catch (e: any) {
      setAddError("Lỗi khi quét: " + e.message);
    } finally {
      setScanningForRegistration(false);
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
    const matchesSearch = !searchQuery || l.bien_so_xe.toLowerCase().includes(searchQuery.toLowerCase());
    
    let matchesFilter = false;
    if (logFilter === 'all') {
      matchesFilter = true;
    } else if (logFilter === 'stranger') {
      // Logic lọc khách lạ: Tên chủ xe là "Khách lạ"
      matchesFilter = findResidentName(l.bien_so_xe) === "Khách lạ";
    } else {
      // Lọc theo trạng thái Vao/Ra/Tu choi
      matchesFilter = l.trang_thai === logFilter;
    }
    
    return matchesSearch && matchesFilter;
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
    <div className="flex h-screen bg-slate-50 font-sans text-slate-900 overflow-hidden">
      {/* Hidden canvas dùng để capture frame */}
      <canvas ref={canvasRef} className="hidden" />

      {/* ── Sidebar ── */}
      <aside className="w-64 glass-sidebar flex flex-col shrink-0 z-40 relative">
        <div className="p-5 flex items-center gap-3 border-b border-slate-100">
          <div className="w-10 h-10 bg-indigo-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-indigo-100">
            <Car size={22} strokeWidth={2.5} />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight text-slate-800">SmartPark</h1>
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Hệ thống AI v2.1</p>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto">
          <NavItem icon={<LayoutDashboard size={19} />} label="Hệ Thống" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
          <NavItem icon={<Activity size={19} />} label="Lịch Sử Ra Vào" active={activeTab === 'history'} onClick={() => setActiveTab('history')} />
          <NavItem icon={<Users size={19} />} label="Cư Dân" active={activeTab === 'residents'} onClick={() => setActiveTab('residents')} />
          <NavItem icon={<TrendingUp size={19} />} label="Doanh Thu" active={activeTab === 'revenue'} onClick={() => setActiveTab('revenue')} />
          <NavItem icon={<MapPin size={19} />} label="Sơ Đồ Bãi Xe" active={activeTab === 'parking_map'} onClick={() => setActiveTab('parking_map')} />
          <NavItem icon={<Settings size={19} />} label="Cài Đặt" active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} />
        </nav>

        {/* API Status */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/30">
          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl text-[11px] font-bold ${apiStatus === 'online' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' :
            apiStatus === 'offline' ? 'bg-red-50 text-red-700 border border-red-100' : 'bg-amber-50 text-amber-700 border border-amber-100'
            }`}>
            {apiStatus === 'online' ? <Wifi size={14} /> : apiStatus === 'offline' ? <WifiOff size={14} /> : <RefreshCw size={14} className="animate-spin" />}
            {apiStatus === 'online' ? 'Hệ thống Sẵn sàng' : apiStatus === 'offline' ? 'Mất kết nối Server' : 'Đang kết nối...'}
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-14 bg-white/50 backdrop-blur-md border-b border-white/20 flex items-center justify-between px-8 shrink-0 z-30 relative">
          <h2 className="text-lg font-semibold tracking-tight">
            {activeTab === 'dashboard' && 'Giám sát Trực tiếp'}
            {activeTab === 'history' && 'Lịch sử Ra Vào'}
            {activeTab === 'residents' && 'Quản lý Cư dân'}
            {activeTab === 'revenue' && 'Doanh thu'}
            {activeTab === 'parking_map' && 'Sơ đồ bãi xe'}
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

          {/* ══════════ DASHBOARD (HỆ THỐNG) ══════════ */}
          {activeTab === 'dashboard' && (
            <div className="flex flex-col gap-6 h-full overflow-y-auto pr-2 custom-scrollbar">

              {/* ══ VISITOR ALERT BANNER ══ */}
              {visitorAlert && (
                <div className="shrink-0 flex items-center gap-5 p-5 rounded-[2rem] bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-2xl shadow-amber-200 border border-amber-400/30 animate-in slide-in-from-top-4 duration-500">
                  {visitorAlert.image && (
                    <img src={visitorAlert.image} className="w-24 h-14 object-cover rounded-2xl border-2 border-white/30 shrink-0" alt={visitorAlert.plate} />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-black uppercase tracking-[0.15em] text-white/70 mb-1">
                      Xe khách {visitorAlert.gate_id === 1 ? 'VÀO' : 'RA'} — {visitorAlert.gate_id === 1 ? 'Ghi nhận' : 'Đối chiếu & Thu phí'}
                    </p>
                    <p className="text-2xl font-bold font-mono tracking-widest">{visitorAlert.plate}</p>
                    {visitorAlert.gate_id === 2 && visitorFeeDetail ? (
                      <div className="flex items-center gap-4 mt-2">
                        <div className="flex flex-col gap-1">
                          <span className="text-[8px] font-black uppercase opacity-60">Lúc vào</span>
                          {visitorAlert.entry_image ? (
                            <img src={visitorAlert.entry_image} className="w-24 h-14 object-cover rounded-lg border border-white/20" alt="Entry" />
                          ) : (
                            <div className="w-24 h-14 bg-white/10 rounded-lg flex items-center justify-center text-[8px] font-bold">Không có ảnh</div>
                          )}
                        </div>
                        <div className="w-px h-10 bg-white/20" />
                        <div className="flex flex-col gap-1">
                          <span className="text-[8px] font-black uppercase opacity-60">Lúc ra (Hiện tại)</span>
                          <img src={visitorAlert.image} className="w-24 h-14 object-cover rounded-lg border border-white/20" alt="Exit" />
                        </div>
                        <div className="ml-2">
                          <p className="text-[10px] font-black">THỜI GIAN: <span className="text-white text-xs">{visitorFeeDetail.hours}h</span></p>
                          <p className="text-[10px] font-black">PHÍ: <span className="text-white text-sm">{visitorFeeDetail.fee.toLocaleString()}đ</span></p>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs font-bold text-white/80 mt-1">Lối {visitorAlert.gate_id === 1 ? 'Vào' : 'Ra'}</p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {visitorAlert.gate_id === 2 ? (
                      <button
                        onClick={handleVisitorPay}
                        disabled={payingVisitor}
                        className="flex items-center gap-2 bg-white text-amber-600 px-5 py-3 rounded-2xl font-black text-sm hover:bg-amber-50 transition-all shadow-lg active:scale-95 disabled:opacity-60"
                      >
                        {payingVisitor ? <RefreshCw size={16} className="animate-spin" /> : <Banknote size={16} />}
                        Xác nhận thu {visitorFeeDetail?.fee.toLocaleString() || '...'}đ & Mở cổng
                      </button>
                    ) : (
                      <div className="px-4 py-2 bg-white/20 rounded-xl text-xs font-bold">Đang vào...</div>
                    )}
                    <button
                      onClick={() => { setVisitorAlert(null); setVisitorFeeDetail(null); }}
                      className="p-3 bg-white/20 hover:bg-white/30 rounded-2xl transition-all"
                      title="Đóng"
                    >
                      <XCircle size={18} />
                    </button>
                  </div>
                </div>
              )}

              {/* V4 ROW 1: TOP STATS BAR */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 shrink-0">
                <StatCard title="Trong bãi" value={stats.inside} icon={<Car size={22} />} color="indigo" />
                <StatCard title="Vào hôm nay" value={stats.entries_today} icon={<LogIn size={22} />} color="emerald" />
                <StatCard title="Ra hôm nay" value={stats.exits_today} icon={<LogOut size={22} />} color="orange" />
                <StatCard title="Người lạ" value={stats.strangers_today} icon={<AlertTriangle size={22} />} color="red" />
              </div>

              {/* V4 ROW 2: MAIN WORKSPACE (70:30 Split) */}
              <div className="flex-1 grid grid-cols-10 gap-6 min-h-0">

                {/* LEFT: DOMINANT ACTIVITY TIMELINE (7/10) */}
                <div className="col-span-7 bg-white rounded-[2.5rem] border border-slate-200/60 shadow-xl overflow-hidden flex flex-col">
                  <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                    <div>
                      <h3 className="text-xl font-black text-slate-800 flex items-center gap-3">
                        <Activity size={24} className="text-indigo-500" /> GIÁM SÁT LỊCH SỬ RA VÀO THỜI GIAN THỰC
                      </h3>
                      <p className="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] mt-1">Dữ liệu thông minh ghi nhận trực tiếp từ Camera</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 text-emerald-600 rounded-xl border border-emerald-100/50">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-[10px] font-black uppercase">Online</span>
                      </div>
                      <span className="bg-indigo-600 text-white text-[10px] font-black px-3 py-1.5 rounded-xl shadow-lg shadow-indigo-100 uppercase tracking-widest">Live Feed</span>
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar bg-slate-50/30">
                    {logs.length > 0 ? (
                      logs.slice(0, 15).map((log, index) => (
                        <div
                          key={log.id}
                          className="flex items-center gap-6 p-5 rounded-[2rem] bg-white border border-slate-100 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all cursor-default group"
                        >
                          <div className="w-24 h-14 bg-slate-900 rounded-2xl overflow-hidden border-2 border-slate-100 shrink-0 group-hover:border-indigo-200 transition-colors">
                            <img src={`data:image/jpeg;base64,${log.hinh_anh}`} className="w-full h-full object-cover" alt="Plate" />
                          </div>

                          <div className="flex-1 grid grid-cols-3 gap-4">
                            <div>
                              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Biển số</p>
                              <p className="text-xl font-black font-mono text-slate-900">{log.bien_so_xe}</p>
                            </div>
                            <div>
                              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Trạng thái</p>
                              <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${log.trang_thai === 'Vao' ? 'bg-emerald-100 text-emerald-700' :
                                log.trang_thai === 'Ra' ? 'bg-orange-100 text-orange-700' : 'bg-red-100 text-red-700'
                                }`}>
                                {log.trang_thai === 'Vao' ? <LogIn size={12} /> : log.trang_thai === 'Ra' ? <LogOut size={12} /> : <AlertTriangle size={12} />}
                                {log.trang_thai === 'Vao' ? 'Đã Vào' : log.trang_thai === 'Ra' ? 'Đã Ra' : 'Từ Chối'}
                              </span>
                            </div>
                            <div className="text-right">
                              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Chủ xe / Thời gian</p>
                              <p className="text-xs font-bold text-slate-700 truncate mb-1">
                                {findResidentName(log.bien_so_xe)}
                              </p>
                              <p className="text-[10px] font-black text-indigo-500 font-mono">
                                {new Date(log.thoi_gian).toLocaleTimeString('vi-VN')}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-slate-300 py-20">
                        <Cpu size={64} strokeWidth={1} className="mb-4 opacity-20" />
                        <p className="text-xs font-black uppercase tracking-[0.3em] opacity-30">Chờ tín hiệu xe...</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* RIGHT: COMPACT MONITORING (3/10) */}
                <div className="col-span-3 space-y-6">
                  {/* Gate 1 Feed */}
                  <div className="glass-card rounded-[2.5rem] p-5 border border-slate-200/60 shadow-sm">
                    <div className="flex items-center justify-between mb-3 px-1">
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-emerald-600 flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        LÀN VÀO (GATE 1)
                      </h3>
                      <button onClick={() => handleManualOpen(1)} className="bg-emerald-50 text-emerald-600 px-3 py-1.5 rounded-xl text-[9px] font-black uppercase hover:bg-emerald-100 transition-all border border-emerald-100">Bấm Mở</button>
                    </div>
                    <div className="aspect-video bg-slate-900 rounded-3xl overflow-hidden relative shadow-inner border-2 border-slate-50">
                      <img src={cameraMode === 'esp32' ? `http://${gate1Ip}:81/stream` : '/api/video_feed'} className="w-full h-full object-cover" alt="Gate 1" />
                    </div>
                  </div>

                  {/* Gate 2 Feed */}
                  <div className="glass-card rounded-[2.5rem] p-5 border border-slate-200/60 shadow-sm">
                    <div className="flex items-center justify-between mb-3 px-1">
                      <h3 className="text-[10px] font-black uppercase tracking-widest text-orange-600 flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
                        LÀN RA (GATE 2)
                      </h3>
                      <button onClick={() => handleManualOpen(2)} className="bg-orange-50 text-orange-600 px-3 py-1.5 rounded-xl text-[9px] font-black uppercase hover:bg-orange-100 transition-all border border-orange-100">Bấm Mở</button>
                    </div>
                    <div className="aspect-video bg-slate-900 rounded-3xl overflow-hidden relative shadow-inner border-2 border-slate-50">
                      <img src={cameraMode === 'esp32' ? `http://${gate2Ip}:81/stream` : '/api/video_feed'} className="w-full h-full object-cover" alt="Gate 2" />
                    </div>
                  </div>

                  {/* System Pulse Card */}
                  <div className="p-6 rounded-[2.5rem] bg-slate-900 text-white shadow-2xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/20 rounded-full -mr-10 -mt-10 blur-2xl" />
                    <h4 className="text-[10px] font-black uppercase tracking-[0.2em] mb-4 text-slate-400 border-b border-slate-800 pb-3">Hệ thống Trực tuyến</h4>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-400">Server API</span>
                        <div className={`px-2 py-1 rounded text-[10px] font-black ${apiStatus === 'online' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                          {apiStatus.toUpperCase()}
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-400">AI Worker (Dual)</span>
                        <div className="px-2 py-1 rounded text-[10px] font-black bg-indigo-500/10 text-indigo-400">
                          STABLE
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ══════════ PARKING MAP (TRANG RIÊNG) ══════════ */}
          {activeTab === 'parking_map' && (
            <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)]">
              <div className="w-full max-w-4xl">
                <div className="mb-8 text-center">
                  <h3 className="text-3xl font-black text-slate-800 mb-2">GIÁM SÁT Ô ĐỖ THỜI GIAN THỰC</h3>
                  <p className="text-slate-400 font-bold uppercase tracking-widest text-xs">Hệ thống đồng bộ trực tiếp từ cảm biến</p>
                </div>

                <div className="grid grid-cols-1 gap-8">
                  <div className="col-span-1">
                    <ParkingMap slots={parkingSlots} />
                  </div>
                </div>
              </div>
            </div>
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
                    <option value="Vao">Xe vào</option>
                    <option value="Ra">Xe ra</option>
                    <option value="Tu choi">Xe bị từ chối</option>
                    <option value="stranger">Khách lạ</option>
                  </select>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => loadLogs(logFilter)}
                    className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-all"
                  >
                    <RefreshCw size={13} /> Làm mới
                  </button>
                  <button
                    onClick={async () => {
                      if (window.confirm("Bạn có chắc chắn muốn xóa TOÀN BỘ lịch sử ra vào không?")) {
                        try {
                          // Gọi API xóa toàn bộ lịch sử
                          const res = await apiFetch<{ success: boolean; message: string }>('/logs/all', { method: 'DELETE' });
                          if (res.success) {
                            showToast("✅ " + res.message);
                            loadLogs(logFilter);
                            loadStats();
                          }
                        } catch (e) {
                          showToast("❌ Không tìm thấy lệnh xóa trên Server. Bạn vui lòng khởi động lại Backend nhé!", "error");
                        }
                      }
                    }}
                    className="flex items-center gap-1.5 text-xs font-semibold text-red-600 bg-red-50 border border-red-100 px-3 py-1.5 rounded-lg hover:bg-red-100 transition-all"
                  >
                    <Trash2 size={13} /> Xóa sạch
                  </button>
                </div>
                <span className="ml-auto text-xs text-slate-500">{filteredLogs.length} bản ghi</span>
              </div>

              <div className="flex-1 overflow-auto">
                <table className="w-full text-left">
                  <thead className="sticky top-0 bg-white border-b border-slate-200">
                    <tr className="text-slate-500 text-xs uppercase tracking-wider">
                      <th className="px-5 py-3 font-medium">Biển số</th>
                      <th className="px-5 py-3 font-medium text-indigo-500">Chủ xe</th>
                      <th className="px-5 py-3 font-medium">Thời gian</th>
                      <th className="px-5 py-3 font-medium">Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 text-sm">
                    {filteredLogs.map(log => (
                      <tr key={log.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3 font-mono font-bold text-slate-900 border-b border-slate-100">
                          {log.bien_so_xe}
                        </td>
                        <td className="px-5 py-3 text-[11px] font-black uppercase text-indigo-600 border-b border-slate-100">
                          {findResidentName(log.bien_so_xe)}
                        </td>
                        <td className="px-5 py-3 text-slate-600 text-xs border-b border-slate-100">
                          {new Date(log.thoi_gian).toLocaleString('vi-VN')}
                        </td>
                        <td className="px-5 py-3 border-b border-slate-100">
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
              {/* Add/Edit form */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 overflow-hidden">
                <div className="flex justify-between items-start gap-6">
                  <div className="flex-1">
                    <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                      {newResident.id ? <Edit size={18} className="text-orange-500" /> : <Plus size={18} className="text-indigo-600" />}
                      {newResident.id ? 'Cập nhật cư dân' : 'Thêm cư dân mới'}
                    </h3>
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1">Họ tên chủ xe *</label>
                        <input
                          type="text"
                          placeholder="Họ tên đầy đủ"
                          value={newResident.ten_chu_xe}
                          onChange={e => setNewResident(p => ({ ...p, ten_chu_xe: e.target.value }))}
                          className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1">Số điện thoại</label>
                        <input
                          type="text"
                          placeholder="09xx..."
                          value={newResident.so_dien_thoai}
                          onChange={e => setNewResident(p => ({ ...p, so_dien_thoai: e.target.value }))}
                          className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1">Biển số xe *</label>
                        <input
                          type="text"
                          placeholder="VD: 30A-12345"
                          value={newResident.bien_so_xe}
                          onChange={e => setNewResident(p => ({ ...p, bien_so_xe: e.target.value.toUpperCase() }))}
                          className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 font-mono font-bold"
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
                      <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1">Phí gửi tháng (VNĐ)</label>
                        <input
                          type="number"
                          placeholder="500000"
                          value={newResident.phi_thang}
                          onChange={e => setNewResident(p => ({ ...p, phi_thang: parseInt(e.target.value) || 0 }))}
                          className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
                        />
                      </div>
                    </div>
                    {addError && <p className="text-red-600 text-[11px] mb-3 font-bold">{addError}</p>}
                    <div className="flex gap-2">
                      <button
                        onClick={handleAddResident}
                        disabled={addingResident}
                        className={`flex items-center gap-2 ${newResident.id ? 'bg-orange-500 hover:bg-orange-600' : 'bg-indigo-600 hover:bg-indigo-700'} text-white px-5 py-2.5 rounded-xl text-xs font-bold transition-all disabled:opacity-50`}
                      >
                        {addingResident ? <RefreshCw size={14} className="animate-spin" /> : (newResident.id ? <Save size={14} /> : <Plus size={14} />)}
                        {newResident.id ? 'Cập nhật' : 'Lưu cư dân'}
                      </button>

                      {newResident.id && (
                        <button
                          onClick={() => setNewResident({ id: null, bien_so_xe: '', ten_chu_xe: '', so_can_ho: '', so_dien_thoai: '', da_thanh_toan: false, anh_dang_ky: '', phi_thang: 0 })}
                          className="text-slate-500 hover:bg-slate-100 px-4 py-2.5 rounded-xl text-xs font-bold transition-all"
                        >
                          Hủy bỏ
                        </button>
                      )}

                      {!newResident.id && (
                        <button
                          onClick={handleScanResidentPlate}
                          disabled={scanningForRegistration}
                          className="flex items-center gap-2 bg-emerald-50 text-emerald-600 border border-emerald-100 px-4 py-2.5 rounded-xl text-xs font-bold hover:bg-emerald-100 transition-all disabled:opacity-50 ml-auto"
                        >
                          {scanningForRegistration ? <RefreshCw size={14} className="animate-spin" /> : <Camera size={14} />}
                          Quét từ Camera
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Camera Preview for registration */}
                  <div className="w-56 h-40 bg-slate-100 rounded-2xl border-2 border-dashed border-slate-200 flex flex-col items-center justify-center relative overflow-hidden group">
                    {newResident.anh_dang_ky ? (
                      <img src={`data:image/jpeg;base64,${newResident.anh_dang_ky}`} className="w-full h-full object-cover" />
                    ) : (
                      cameraMode === 'esp32' ? (
                        <img src={`/api/video_feed?t=${Date.now()}`} className="w-full h-full object-cover opacity-50" />
                      ) : (
                        <div className="text-center p-4">
                          <Camera size={24} className="mx-auto text-slate-300 mb-2" />
                          <p className="text-[10px] font-bold text-slate-400">Xem trước đăng ký</p>
                        </div>
                      )
                    )}
                    {newResident.anh_dang_ky && (
                      <button
                        onClick={() => setNewResident(p => ({ ...p, anh_dang_ky: '' }))}
                        className="absolute top-2 right-2 bg-white/80 backdrop-blur-sm p-1 rounded-full text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 size={12} />
                      </button>
                    )}
                    <div className="absolute top-2 left-2 px-1.5 py-0.5 bg-black/50 backdrop-blur-sm rounded text-[8px] text-white font-bold uppercase tracking-widest">
                      Preview
                    </div>
                  </div>
                </div>
              </div>

              {/* List */}
              <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden flex-1 flex flex-col min-h-0">
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2">
                    <Shield size={18} className="text-slate-500" />
                    Danh sách cư dân ({residents.length})
                  </h3>
                  <button onClick={loadResidents} className="text-xs text-indigo-600 font-bold hover:underline px-3 py-1 bg-white border border-slate-200 rounded-lg shadow-sm">
                    Làm mới
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b border-slate-100 sticky top-0 bg-white/95 backdrop-blur-md">
                      <tr className="text-slate-400 text-[10px] uppercase tracking-widest font-bold">
                        <th className="px-6 py-3 text-left">Chủ xe / SĐT</th>
                        <th className="px-6 py-3 text-left">Biển số / Căn hộ</th>
                        <th className="px-6 py-3 text-center">Phí tháng</th>
                        <th className="px-6 py-3 text-right pr-12">Đăng ký</th>
                        <th className="px-6 py-3 text-right">Hành động</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {residents.map(r => (
                        <tr key={r.id} className="hover:bg-slate-50 transition-colors group">
                          <td className="px-6 py-4 cursor-pointer" onClick={() => setSelectedResident(r)}>
                            <p className="text-slate-900 font-bold group-hover:text-indigo-600 transition-colors">{r.ten_chu_xe}</p>
                            <p className="text-[10px] font-bold text-slate-400">{r.so_dien_thoai || 'Chưa cập nhật SĐT'}</p>
                          </td>
                          <td className="px-6 py-4">
                            <span className="font-mono font-bold text-slate-800 bg-slate-100 px-2 py-1 rounded border border-slate-200 mr-2">{r.bien_so_xe}</span>
                            <span className="text-xs font-bold text-slate-500">{r.so_can_ho || '—'}</span>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <div className="flex flex-col items-center">
                              <span onClick={(e) => { e.stopPropagation(); handleTogglePayment(r.id); }} className={`cursor-pointer inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest shadow-sm mb-1 ${r.da_thanh_toan ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' : 'bg-red-100 text-red-700 hover:bg-red-200'
                                }`}>
                                {r.da_thanh_toan ? <CheckCircle2 size={10} /> : <XCircle size={10} />}
                                {r.da_thanh_toan ? 'Đã Đóng' : 'Nợ Phí'}
                              </span>
                              <span className="text-[10px] font-bold text-slate-400">{(r.phi_thang || 500000).toLocaleString()} VNĐ</span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-right pr-12">
                            {r.anh_dang_ky ? (
                              <img
                                onClick={(e) => { e.stopPropagation(); setSelectedResident(r); }}
                                src={`data:image/jpeg;base64,${r.anh_dang_ky}`}
                                className="inline-block w-10 h-6 object-cover rounded shadow-sm border border-slate-100 hover:scale-[3] transition-transform origin-right z-10 relative cursor-zoom-in"
                              />
                            ) : (
                              <span className="text-[10px] text-slate-300 italic font-bold">No Image</span>
                            )}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex justify-end gap-1">
                              <button
                                onClick={(e) => { e.stopPropagation(); startEditResident(r); }}
                                className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
                                title="Sửa thông tin"
                              >
                                <RefreshCw size={14} />
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleDeleteResident(r.id); }}
                                className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                                title="Xóa cư dân"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {residents.length === 0 && (
                        <tr>
                          <td colSpan={4} className="text-center py-20 text-slate-400 italic">
                            Chưa có cư dân nào trong hệ thống
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}


          {/* ══════════ SETTINGS ══════════ */}
          {activeTab === 'settings' && (
            <div className="max-w-2xl space-y-5">
              <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-4">
                  <div className="w-10 h-10 rounded-2xl bg-indigo-100 flex items-center justify-center text-indigo-600">
                    <Camera size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">Cấu hình Hardware & Camera</h3>
                    <p className="text-xs text-slate-500">Thiết lập kết nối IP với ESP8266 và Camera</p>
                  </div>
                </div>
                <div className="p-6 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5 ml-1">IP Làn VÀO (Gate 1)</label>
                      <input
                        type="text"
                        value={gate1Ip}
                        onChange={e => setGate1Ip(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 transition-all font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5 ml-1">IP Làn RA (Gate 2)</label>
                      <input
                        type="text"
                        value={gate2Ip}
                        onChange={e => setGate2Ip(e.target.value)}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 transition-all font-mono"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5 ml-1">IP Điều khiển Barrier (ESP8266)</label>
                    <input
                      type="text"
                      value={esp8266Ip}
                      onChange={e => setEsp8266Ip(e.target.value)}
                      className="w-full bg-indigo-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 transition-all font-mono text-indigo-600 font-bold"
                      placeholder="VD: 192.168.0.105"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <div className="flex-1 max-w-xs">
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5 ml-1">Phí khách vãng lai (VNĐ/lượt)</label>
                  <div className="flex gap-2">
                    <input
                      type="number"
                      value={visitorFee}
                      onChange={e => setVisitorFee(parseInt(e.target.value) || 0)}
                      className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-amber-100 focus:border-amber-400 transition-all font-mono font-bold text-amber-600"
                    />
                    <button
                      onClick={async () => {
                        try {
                          await apiFetch('/config/fees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visitor_fee: visitorFee }) });
                          showToast('✅ Đã cập nhật phí khách');
                        } catch { showToast('❌ Lỗi cập nhật', 'error'); }
                      }}
                      className="px-4 py-2.5 bg-amber-500 text-white rounded-xl text-xs font-bold hover:bg-amber-600 transition-all"
                    >Lưu</button>
                  </div>
                </div>
                <div className="flex items-end">
                  <button
                    onClick={saveSystemConfig}
                    disabled={isUpdatingConfig}
                    className="flex items-center gap-2 bg-indigo-600 text-white px-6 py-3 rounded-2xl text-sm font-bold hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100 active:scale-95 disabled:opacity-50"
                  >
                    {isUpdatingConfig ? <RefreshCw size={18} className="animate-spin" /> : <Save size={18} />}
                    Lưu cấu hình
                  </button>
                </div>
              </div>

            </div>
          )}

          {/* ══════════ REVENUE (DOANH THU) ══════════ */}
          {activeTab === 'revenue' && (
            <RevenueView
              stats={revenueStats}
              history={revenueHistory}
              chart={revenueChart}
              pieChart={revenuePie}
              onRefresh={fetchRevenueData}
              onDelete={handleDeleteRevenue}
              visitorFee={visitorFee}
            />
          )}

          {/* Toast Notification */}
          {toast && (
            <div className={`fixed bottom-6 right-6 z-[200] flex items-center gap-3 px-5 py-3.5 rounded-2xl shadow-2xl text-sm font-bold text-white animate-in slide-in-from-bottom-4 duration-300 ${toast.type === 'success' ? 'bg-emerald-600' : 'bg-red-600'
              }`}>
              {toast.msg}
            </div>
          )}
        </div>
      </main>

      {/* ══════════ RESIDENT PROFILE MODAL ══════════ */}
      <AnimatePresence>
        {selectedResident && (
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
            onClick={() => setSelectedResident(null)}
          >
            <div
              className="bg-white rounded-[2.5rem] shadow-2xl w-full max-w-4xl overflow-hidden border border-slate-100 flex h-[500px]"
              onClick={e => e.stopPropagation()}
            >
              {/* LEFT SIDE: Info */}
              <div className="w-2/5 flex flex-col border-r border-slate-100 bg-slate-50/30">
                {/* Modal Header/Top Cover */}
                <div className="h-32 bg-indigo-600 relative shrink-0">
                  <div className="absolute inset-0 bg-gradient-to-br from-indigo-500 to-purple-700 opacity-90" />
                  <div className="absolute -bottom-10 left-6 p-1 bg-white rounded-2xl shadow-xl">
                    <div className="w-20 h-20 bg-slate-100 rounded-xl overflow-hidden border-2 border-slate-50 flex items-center justify-center">
                      {selectedResident.anh_dang_ky ? (
                        <img src={`data:image/jpeg;base64,${selectedResident.anh_dang_ky}`} className="w-full h-full object-cover" />
                      ) : (
                        <Car size={32} className="text-slate-300" />
                      )}
                    </div>
                  </div>
                </div>

                <div className="pt-12 px-6 flex-1 flex flex-col justify-between pb-6">
                  <div>
                    <div className="mb-6">
                      <h2 className="text-xl font-black text-slate-800 leading-tight">{selectedResident.ten_chu_xe}</h2>
                      <p className="text-indigo-600 text-sm font-black font-mono tracking-wider">{selectedResident.bien_so_xe}</p>

                      <div className="mt-3">
                        <span className={`px-3 py-1.5 rounded-xl text-[9px] font-black uppercase tracking-widest flex items-center gap-2 w-fit ${selectedResident.da_thanh_toan ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' : 'bg-red-50 text-red-600 border border-red-100'
                          }`}>
                          <div className={`w-1.5 h-1.5 rounded-full ${selectedResident.da_thanh_toan ? 'bg-emerald-500' : 'bg-red-500 animate-pulse'}`} />
                          {selectedResident.da_thanh_toan ? 'Đã đóng phí' : 'Nợ phí tháng'}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="space-y-1">
                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Căn hộ</p>
                        <div className="flex items-center gap-2 text-slate-700">
                          <LayoutGrid size={14} className="text-slate-300" />
                          <span className="text-sm font-bold">{selectedResident.so_can_ho || 'N/A'}</span>
                        </div>
                      </div>
                      <div className="space-y-1">
                        <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Phí tháng</p>
                        <div className="flex items-center gap-2 text-slate-700">
                          <Banknote size={14} className="text-slate-300" />
                          <span className="text-sm font-bold text-emerald-600">{(selectedResident.phi_thang || 500000).toLocaleString()} VNĐ</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2 mt-8">
                    <button
                      onClick={() => handleTogglePayment(selectedResident.id)}
                      className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-black text-xs transition-all shadow-lg active:scale-95 ${selectedResident.da_thanh_toan
                        ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                        : 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-emerald-100'
                        }`}
                    >
                      <CheckCircle2 size={16} />
                      {selectedResident.da_thanh_toan ? 'Hủy thu' : 'Thu phí'}
                    </button>
                    <button
                      onClick={() => { startEditResident(selectedResident); setSelectedResident(null); }}
                      className="p-3 rounded-xl bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-all active:scale-95"
                    >
                      <Edit size={16} />
                    </button>
                  </div>
                </div>
              </div>

              {/* RIGHT SIDE: Large Image */}
              <div className="w-3/5 bg-slate-900 relative group flex items-center justify-center">
                {selectedResident.anh_dang_ky ? (
                  <img src={`data:image/jpeg;base64,${selectedResident.anh_dang_ky}`} className="w-full h-full object-contain" />
                ) : (
                  <div className="text-center">
                    <Activity size={48} className="text-slate-700 mx-auto mb-4 opacity-20" />
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-600">Không có ảnh đăng ký</p>
                  </div>
                )}
                <div className="absolute top-6 left-6 px-3 py-1.5 bg-black/40 backdrop-blur-md rounded-xl border border-white/10 text-[9px] text-white font-black uppercase tracking-widest">
                  HÌNH ẢNH BIỂN SỐ GHI NHẬN
                </div>
                <button
                  onClick={() => setSelectedResident(null)}
                  className="absolute top-6 right-6 bg-white/10 hover:bg-white/20 backdrop-blur-md p-2 rounded-full text-white transition-all border border-white/10"
                >
                  <XCircle size={20} />
                </button>
              </div>
            </div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function ParkingMap({ slots }: { slots: ParkingSlot[] }) {
  return (
    <div className="glass-card rounded-[2.5rem] p-6 border border-slate-200/60 shadow-sm">
      <div className="flex items-center justify-between mb-5 px-1">
        <h3 className="text-[10px] font-black uppercase tracking-widest text-indigo-600 flex items-center gap-2">
          <MapPin size={14} /> SƠ ĐỒ BÃI XE (REAL-TIME)
        </h3>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-[9px] font-bold text-slate-400 uppercase">Trống</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-[9px] font-bold text-slate-400 uppercase">Đầy</span>
          </div>
        </div>
      </div>

      {/* PARKING GRID LAYOUT */}
      <div className="grid grid-cols-3 gap-4">
        {slots.map((slot) => (
          <div
            key={slot.slot_id}
            className={`relative aspect-[3/4] rounded-2xl border-2 flex flex-col items-center justify-center gap-2 transition-all duration-500 overflow-hidden ${slot.status
              ? 'bg-red-50 border-red-200 shadow-[inset_0_0_20px_rgba(239,68,68,0.05)]'
              : 'bg-emerald-50/30 border-emerald-100 border-dashed hover:border-emerald-300'
              }`}
          >
            <div className="absolute top-2 left-2 text-[8px] font-black text-slate-300 uppercase leading-none">#{slot.slot_id}</div>

            {slot.status ? (
              <motion.div
                initial={{ scale: 0, rotate: -20 }}
                animate={{ scale: 1, rotate: 0 }}
                className="flex flex-col items-center"
              >
                <div className="p-3 bg-red-500 rounded-xl shadow-lg shadow-red-200 text-white mb-1">
                  <Car size={20} />
                </div>
                <span className="text-[9px] font-black text-red-600 uppercase tracking-wider">Có xe</span>
              </motion.div>
            ) : (
              <div className="flex flex-col items-center opacity-40">
                <div className="p-3 bg-slate-100 rounded-xl mb-1 text-slate-400">
                  <Car size={20} className="grayscale" />
                </div>
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-wider">Trống</span>
              </div>
            )}

            {/* Vạch kẻ đường mô phỏng */}
            <div className="absolute bottom-0 left-0 w-full h-1 bg-slate-100" />
            <div className="absolute top-0 right-0 h-full w-0.5 bg-slate-50/50" />
          </div>
        ))}
      </div>

    </div>
  );
}

const PieChart = ({ data }: { data: any[] }) => {
  if (!data || data.length === 0) return (
    <div className="h-48 flex items-center justify-center text-slate-300 text-[10px] font-black uppercase tracking-widest">
      Thiếu dữ liệu
    </div>
  );

  const total = data.reduce((acc, curr) => acc + Number(curr.total), 0);
  let accumulatedPercent = 0;

  // Màu sắc cho các loại phí
  const colors: Record<string, string> = {
    'MONTHLY': '#6366f1', // indigo-500
    'VISITOR': '#3b82f6', // blue-500
    'GUEST': '#3b82f6'
  };

  const gradients = data.map((item) => {
    const percent = (Number(item.total) / total) * 100;
    const start = accumulatedPercent;
    accumulatedPercent += percent;
    return `${colors[item.loai_phi] || '#cbd5e1'} ${start}% ${accumulatedPercent}%`;
  }).join(', ');

  return (
    <div className="flex flex-col items-center gap-6">
      <div
        className="w-40 h-40 rounded-full shadow-2xl relative flex items-center justify-center group"
        style={{ background: `conic-gradient(${gradients})` }}
      >
        {/* Inner circle for donut look */}
        <div className="w-28 h-28 bg-white rounded-full flex flex-col items-center justify-center shadow-inner">
          <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Tổng</p>
          <p className="text-sm font-black text-slate-800">{(total / 1000).toFixed(1)}k</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 w-full">
        {data.map((item, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colors[item.loai_phi] || '#cbd5e1' }} />
            <div className="min-w-0">
              <p className="text-[9px] font-black text-slate-400 uppercase tracking-tighter truncate">
                {item.loai_phi === 'MONTHLY' ? 'Cư dân' : 'Khách vãng lai'}
              </p>
              <p className="text-[10px] font-black text-slate-700">{Math.round((item.total / total) * 100)}%</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const RevenueView = ({ stats, history, chart, pieChart, onRefresh, onDelete }: any) => {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h2 className="text-2xl font-black text-slate-800 tracking-tight">Thống Kê Doanh Thu</h2>
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">Quản lý dòng tiền thông minh</p>
        </div>
        <button
          onClick={onRefresh}
          className="p-3 bg-white border border-slate-100 rounded-2xl text-slate-500 hover:text-indigo-600 hover:border-indigo-100 transition-all shadow-sm"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-[2.5rem] border border-slate-100 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-[0.03] group-hover:scale-110 transition-transform duration-700">
            <Banknote size={80} />
          </div>
          <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] mb-2">Phí thu hôm nay</p>
          <h3 className="text-3xl font-black text-slate-800 tracking-tight">
            {stats.today.toLocaleString()} <span className="text-sm font-bold text-slate-400">VNĐ</span>
          </h3>
          <div className="mt-4 flex items-center gap-2 text-emerald-600 text-xs font-bold">
            <TrendingUp size={14} />
            <span>Thu nhập trực tiếp</span>
          </div>
        </div>

        <div className="bg-indigo-600 p-6 rounded-[2.5rem] shadow-xl shadow-indigo-100 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:scale-110 transition-transform duration-700 text-white">
            <Calendar size={80} />
          </div>
          <p className="text-[10px] font-black text-white/60 uppercase tracking-[0.15em] mb-2">Doanh thu tháng này</p>
          <h3 className="text-3xl font-black text-white tracking-tight">
            {stats.month.toLocaleString()} <span className="text-sm font-bold text-white/60">VNĐ</span>
          </h3>
          <div className="mt-4 px-3 py-1 bg-white/10 rounded-full w-fit text-[10px] text-white font-bold">
            Cập nhật thời gian thực
          </div>
        </div>

        <div className="bg-white p-6 rounded-[2.5rem] border border-slate-100 shadow-sm relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-[0.03] group-hover:scale-110 transition-transform duration-700">
            <Users size={80} />
          </div>
          <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] mb-2">Lượt khách thăm hôm nay</p>
          <h3 className="text-3xl font-black text-slate-800 tracking-tight">
            {stats.visitors_today} <span className="text-sm font-bold text-slate-400">Lượt</span>
          </h3>
          <div className="mt-4 flex items-center gap-2 text-indigo-600 text-xs font-bold">
            <Car size={14} />
            <span>Ghi nhận xe ngoài vào bãi</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-6 gap-6">
        {/* Bar Chart */}
        <div className="lg:col-span-4 bg-white p-8 rounded-[3rem] border border-slate-100 shadow-sm flex flex-col">
          <div className="flex items-center justify-between mb-8">
            <h4 className="font-black text-slate-800 tracking-tight">Xu hướng thu phí (7 ngày)</h4>
            <div className="flex items-center gap-4 text-[10px] font-bold text-slate-400">
              <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-full bg-indigo-500" /> Doanh thu</div>
            </div>
          </div>

          <div className="h-48 flex items-end justify-between gap-4 px-2 mt-auto">
            {chart.map((item: any, i: number) => {
              const maxVal = Math.max(...chart.map((d: any) => d.total), 1);
              const height = (item.total / maxVal) * 100;
              return (
                <div key={i} className="flex-1 flex flex-col items-center group gap-3 h-full justify-end">
                  <div className="w-full relative flex items-end justify-center flex-1">
                    <div
                      className="w-full max-w-[40px] bg-slate-100 rounded-t-2xl group-hover:bg-indigo-50 transition-colors duration-300 absolute bottom-0"
                      style={{ height: '100%', opacity: 0.3 }}
                    />
                    <motion.div
                      initial={{ height: 0 }}
                      animate={{ height: `${height}%` }}
                      transition={{ delay: i * 0.1, duration: 1, ease: "easeOut" }}
                      className="w-full max-w-[40px] bg-gradient-to-t from-indigo-500 to-indigo-400 rounded-t-2xl shadow-lg shadow-indigo-100 relative z-10"
                    />
                  </div>
                  <span className="text-[10px] font-black text-slate-400 group-hover:text-indigo-600 transition-colors uppercase tracking-tighter">{item.day}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Pie Chart Breakdown */}
        <div className="lg:col-span-2 bg-white p-8 rounded-[3rem] border border-slate-100 shadow-sm">
          <h4 className="font-black text-slate-800 tracking-tight mb-8">Tỷ trọng doanh thu</h4>
          <PieChart data={pieChart} />
        </div>
      </div>

      <div className="bg-white rounded-[3rem] border border-slate-100 shadow-sm overflow-hidden flex flex-col">
        <div className="p-6 border-b border-slate-50 flex items-center justify-between">
          <h4 className="font-black text-slate-800 tracking-tight">Lịch sử thu phí gần đây</h4>
          <div className="flex gap-2">
            <span className="flex items-center gap-1 text-[9px] font-black text-slate-400 uppercase tracking-widest">
              <div className="w-2 h-2 rounded-full bg-emerald-500" /> Cư dân
            </span>
            <span className="flex items-center gap-1 text-[9px] font-black text-slate-400 uppercase tracking-widest">
              <div className="w-2 h-2 rounded-full bg-blue-500" /> Khách
            </span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-50">
                <th className="px-6 py-4">Biển số</th>
                <th className="px-6 py-4">Chủ xe / Loại xe</th>
                <th className="px-6 py-4">Loại phí</th>
                <th className="px-6 py-4">Thời gian</th>
                <th className="px-6 py-4 text-right">Số tiền</th>
                <th className="px-6 py-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {history.length === 0 ? (
                <tr><td colSpan={6} className="py-12 text-center text-slate-300 text-xs font-bold">Chưa có giao dịch nào</td></tr>
              ) : (
                history.map((tx: any) => (
                  <tr key={tx.id} className="hover:bg-slate-50/50 transition-colors group">
                    <td className="px-6 py-4 font-mono font-bold text-slate-900">{tx.bien_so_xe}</td>
                    <td className="px-6 py-4 text-xs font-bold text-slate-600">
                      {tx.loai_phi === 'VISITOR' ? 'Khách vãng lai' : (tx.ten_chu_xe || 'Cư dân')}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`text-[8px] font-black uppercase tracking-widest px-2 py-1 rounded-lg ${tx.loai_phi === 'VISITOR' ? 'bg-blue-50 text-blue-600' : 'bg-emerald-50 text-emerald-600'
                        }`}>
                        {tx.loai_phi === 'VISITOR' ? 'Theo giờ' : 'Tháng'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-[10px] font-bold text-slate-400">
                      {new Date(tx.ngay_thanh_toan).toLocaleString('vi-VN')}
                    </td>
                    <td className={`px-6 py-4 text-right text-sm font-black ${tx.loai_phi === 'VISITOR' ? 'text-blue-600' : 'text-emerald-600'}`}>
                      +{tx.so_tien.toLocaleString()}đ
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => onDelete(tx.id)}
                        className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                        title="Xóa giao dịch"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-2xl transition-all duration-300 ${active
        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-100 translate-x-1'
        : 'text-slate-500 hover:bg-slate-50 hover:text-indigo-600'
        }`}
    >
      <span className={active ? 'text-white' : 'text-slate-400'}>{icon}</span>
      <span className="font-bold text-sm tracking-tight">{label}</span>
    </button>
  );
}

function StatCard({ title, value, icon, color }: { title: string; value: number | string; icon: React.ReactNode; color: 'indigo' | 'emerald' | 'orange' | 'red' }) {
  const colors = {
    indigo: 'bg-indigo-50 text-indigo-600 border-indigo-100',
    emerald: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    orange: 'bg-orange-50 text-orange-600 border-orange-100',
    red: 'bg-red-50 text-red-600 border-red-100'
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-5 rounded-3xl border shadow-sm ${colors[color]} flex flex-col gap-3 group hover:scale-[1.02] transition-all`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black uppercase tracking-widest opacity-70">{title}</span>
        {icon}
      </div>
      <p className="text-3xl font-black">{value}</p>
    </motion.div>
  );
}

function HardwareStatus({ label, icon, status }: { label: string; icon: React.ReactNode; status: 'online' | 'offline' | 'simulated' }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 rounded-xl transition-all hover:bg-white/50">
      <div className={`p-1.5 rounded-lg ${status === 'online' ? 'bg-emerald-50 text-emerald-600' :
        status === 'simulated' ? 'bg-blue-50 text-blue-600' : 'bg-slate-100 text-slate-400'
        }`}>
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-bold text-slate-800 truncate">{label}</p>
        <p className={`text-[8px] font-black uppercase tracking-widest ${status === 'online' ? 'text-emerald-500' :
          status === 'simulated' ? 'text-blue-500' : 'text-slate-400'
          }`}>
          {status === 'online' ? 'Online' : status === 'simulated' ? 'Simulated' : 'Offline'}
        </p>
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

function AnimatedBarrier({ isOpen }: { isOpen: boolean }) {
  return (
    <div className="relative w-8 h-8 flex items-center justify-center">
      <div className={`absolute inset-0 rounded-lg ${isOpen ? 'bg-emerald-100' : 'bg-slate-100'} transition-colors duration-500`} />
      <motion.div
        initial={false}
        animate={{ rotate: isOpen ? -90 : 0 }}
        transition={{ type: "spring", stiffness: 100, damping: 10 }}
        className="w-1.5 h-6 bg-slate-800 rounded-full origin-bottom"
        style={{ marginBottom: -12 }}
      />
      <div className="absolute bottom-1 w-3 h-1 bg-slate-400 rounded-full" />
    </div>
  );
}

function ScanningOverlay() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl">
      <div className="w-full h-full bg-indigo-500/10" />
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-indigo-400 to-transparent shadow-[0_0_15px_rgba(99,102,241,0.8)] animate-scan" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(99,102,241,0.1)_0%,transparent_100%)]" />
    </div>
  );
}

function BBoxOverlay({ detection, videoRef, isIPCam = false }: {
  detection: DetectionResult;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  isIPCam?: boolean;
}) {
  if (!detection.bbox) return null;
  const vw = isIPCam ? 640 : (videoRef.current?.videoWidth || 1280);
  const vh = isIPCam ? 480 : (videoRef.current?.videoHeight || 720);
  const [x1, y1, x2, y2] = detection.bbox;
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
