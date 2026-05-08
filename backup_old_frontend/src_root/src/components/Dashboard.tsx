/**
 * Dashboard — Command Center chính của SmartPark ALPR
 *
 * Thay đổi so với phiên bản Velorah gốc:
 * - Video: MJPEG stream thật từ ESP32-CAM (qua CameraFeed component)
 * - Bounding box: Tọa độ thật từ YOLO detection
 * - Event Log: Dữ liệu thật từ bảng lichsuravao (qua SmartParkContext)
 * - Stats: Thống kê thật từ /api/stats
 * - Tab Residents: CRUD bảng cudan
 * - Nút OPEN GATE: Gửi lệnh tới /api/iot/trigger → ESP8266 → Servo
 *
 * Giữ nguyên: glassmorphism liquid-glass, motion animations, color palette Velorah
 */

import { motion, AnimatePresence } from 'motion/react';
import {
  Shield, Activity, Globe, Settings, Terminal,
  Zap, Users, DoorOpen, Loader2, Wifi, WifiOff,
  RefreshCw, ChevronRight
} from 'lucide-react';
import { useState, useCallback } from 'react';
import { useSmartPark } from '../context/SmartParkContext';
import CameraFeed from './CameraFeed';
import StatsPanel from './StatsPanel';
import ResidentTable from './ResidentTable';

type SideTab = 'logs' | 'residents';

export default function Dashboard({ setView }: { setView: (view: string) => void, key?: string }) {
  const {
    logs,
    wsConnected,
    systemStatus,
    latestDetection,
    triggerBarrier,
    isLoading,
    refreshLogs,
  } = useSmartPark();

  const [sideTab, setSideTab]           = useState<SideTab>('logs');
  const [barrierState, setBarrierState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [barrierMsg, setBarrierMsg]     = useState('');

  // ── Điều khiển Barrier ──────────────────────────────────────────────────
  const handleOpenBarrier = useCallback(async () => {
    if (barrierState === 'loading') return;
    setBarrierState('loading');
    setBarrierMsg('');
    try {
      const result = await triggerBarrier();
      if (result.success || result.barrier_opened) {
        setBarrierState('success');
        setBarrierMsg(result.plate
          ? `Mở cổng: ${result.matched_plate || result.plate}`
          : 'Đã gửi lệnh mở cổng');
      } else {
        setBarrierState('error');
        setBarrierMsg(result.reason || result.error || 'Không mở được cổng');
      }
    } catch (e: any) {
      setBarrierState('error');
      setBarrierMsg(e.message || 'Lỗi kết nối server');
    } finally {
      setTimeout(() => { setBarrierState('idle'); setBarrierMsg(''); }, 4000);
    }
  }, [barrierState, triggerBarrier]);

  // ── Helper: màu trang thái ─────────────────────────────────────────────
  const statusColor = (ts: string) => {
    if (ts === 'Vao') return '#38BDF8';
    if (ts === 'Ra')  return '#4ADE80';
    return '#F87171';
  };

  const statusLabel = (ts: string) => {
    if (ts === 'Vao') return 'VÀO';
    if (ts === 'Ra')  return 'RA';
    return 'TỪ CHỐI';
  };

  // ── Format thời gian ───────────────────────────────────────────────────
  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString('vi-VN', { hour12: false });
    } catch { return iso; }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="h-screen w-full bg-midnight flex overflow-hidden text-ghost"
    >
      {/* ═══ Sidebar trái ═══════════════════════════════════════════════════ */}
      <motion.aside
        initial={{ x: -50, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.8, ease: 'easeOut' }}
        className="w-20 border-r border-white/10 liquid-glass flex flex-col items-center py-8 gap-8 z-10"
      >
        {/* Logo */}
        <div
          className="w-10 h-10 rounded-xl bg-electric/20 flex items-center justify-center border border-electric/50 shadow-[0_0_15px_rgba(56,189,248,0.3)] cursor-pointer"
          onClick={() => setView('home')}
        >
          <Zap className="w-5 h-5 text-electric" />
        </div>

        <nav className="flex flex-col gap-4 mt-4">
          {/* Live Stream tab */}
          <button
            onClick={() => setSideTab('logs')}
            className={`p-3 rounded-lg border transition-colors relative group
              ${sideTab === 'logs'
                ? 'bg-white/5 text-electric border-electric/30'
                : 'text-white/50 hover:text-white hover:bg-white/5 border-transparent'}`}
          >
            <Activity className="w-5 h-5" />
            <span className="absolute left-full ml-4 px-2 py-1 bg-midnight border border-white/10 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
              Live Log
            </span>
          </button>

          {/* Residents tab */}
          <button
            onClick={() => setSideTab('residents')}
            className={`p-3 rounded-lg border transition-colors relative group
              ${sideTab === 'residents'
                ? 'bg-white/5 text-electric border-electric/30'
                : 'text-white/50 hover:text-white hover:bg-white/5 border-transparent'}`}
          >
            <Users className="w-5 h-5" />
            <span className="absolute left-full ml-4 px-2 py-1 bg-midnight border border-white/10 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
              Cư dân
            </span>
          </button>

          {/* System status */}
          <button className="p-3 rounded-lg text-white/50 hover:text-white hover:bg-white/5 border border-transparent transition-colors relative group">
            <Globe className="w-5 h-5" />
            <span className="absolute left-full ml-4 px-2 py-1 bg-midnight border border-white/10 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
              {systemStatus ? `DB: ${systemStatus.db.startsWith('connected') ? '✅' : '❌'}` : 'Hệ thống'}
            </span>
          </button>
        </nav>

        {/* Open Gate Button */}
        <div className="mt-auto flex flex-col items-center gap-2">
          <motion.button
            onClick={handleOpenBarrier}
            disabled={barrierState === 'loading'}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`w-12 h-12 rounded-xl flex items-center justify-center border transition-all shadow-lg relative group
              ${barrierState === 'loading'  ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400' :
                barrierState === 'success'  ? 'bg-green-500/20 border-green-500/50 text-green-400' :
                barrierState === 'error'    ? 'bg-red-500/20 border-red-500/50 text-red-400' :
                'bg-electric/10 border-electric/40 text-electric hover:bg-electric/20'}`}
          >
            {barrierState === 'loading'
              ? <Loader2 className="w-5 h-5 animate-spin" />
              : <DoorOpen className="w-5 h-5" />}
            <span className="absolute left-full ml-3 px-2 py-1 bg-midnight border border-white/10 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
              {barrierState === 'idle'    ? 'Mở cổng thủ công' :
               barrierState === 'loading' ? 'Đang xử lý...' :
               barrierState === 'success' ? 'Thành công!' : 'Thất bại'}
            </span>
          </motion.button>

          {/* Barrier status message */}
          <AnimatePresence>
            {barrierMsg && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className={`absolute left-20 bottom-24 ml-2 px-3 py-2 rounded-lg text-xs font-mono max-w-48 z-50 border
                  ${barrierState === 'success'
                    ? 'bg-green-900/80 border-green-500/30 text-green-300'
                    : 'bg-red-900/80 border-red-500/30 text-red-300'}`}
              >
                {barrierMsg}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Settings */}
          <button className="p-3 rounded-lg text-white/50 hover:text-white hover:bg-white/5 transition-colors relative group">
            <Settings className="w-5 h-5" />
            <span className="absolute left-full ml-3 px-2 py-1 bg-midnight border border-white/10 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
              Cài đặt
            </span>
          </button>
        </div>
      </motion.aside>

      {/* ═══ Main Content ════════════════════════════════════════════════════ */}
      <main className="flex-1 relative flex flex-col p-6 gap-4 overflow-hidden">
        {/* Header */}
        <header className="flex justify-between items-center flex-shrink-0">
          <div>
            <h1 className="font-serif text-3xl tracking-wide">SmartPark ALPR</h1>
            <p className="text-white/50 text-sm font-mono mt-1">
              {systemStatus
                ? `DB: ${systemStatus.db.startsWith('connected') ? 'ONLINE' : 'OFFLINE'} // YOLO: ${systemStatus.yolo.toUpperCase()} // GPU: ${systemStatus.gpu ? 'CUDA' : 'CPU'}`
                : 'LOADING SYSTEM STATUS...'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* WS indicator */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono liquid-glass
              ${wsConnected ? 'border-electric/30' : 'border-red-500/30'}`}>
              {wsConnected
                ? <><div className="w-2 h-2 rounded-full bg-electric animate-pulse" /> LIVE</>
                : <><WifiOff className="w-3 h-3 text-red-400" /> OFFLINE</>}
            </div>

            {/* Latest plate badge */}
            {latestDetection?.plate && (
              <motion.div
                key={latestDetection.plate}
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="px-3 py-1.5 rounded-full liquid-glass border border-electric/20 text-xs font-mono text-electric"
              >
                🚗 {latestDetection.matched_plate || latestDetection.plate}
                {latestDetection.owner && <span className="text-white/50 ml-1">— {latestDetection.owner}</span>}
              </motion.div>
            )}

            <button
              className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 transition-colors text-sm"
              onClick={() => setView('auth')}
            >
              Sign Out
            </button>
          </div>
        </header>

        {/* Stats Row */}
        <div className="flex-shrink-0">
          <StatsPanel />
        </div>

        {/* Camera Feed — chiếm hầu hết diện tích còn lại */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.8, ease: 'easeOut' }}
          className="flex-1 rounded-2xl overflow-hidden border border-white/10 shadow-2xl min-h-0"
        >
          <CameraFeed />
        </motion.div>
      </main>

      {/* ═══ Sidebar phải — Event Log / Residents ═══════════════════════════ */}
      <motion.aside
        initial={{ x: 50, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ delay: 0.6, duration: 0.8, ease: 'easeOut' }}
        className="w-80 border-l border-white/10 liquid-glass flex flex-col z-10"
      >
        {/* Tab Header */}
        <div className="flex border-b border-white/10 flex-shrink-0">
          <button
            onClick={() => setSideTab('logs')}
            className={`flex-1 py-3 text-xs font-mono uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5
              ${sideTab === 'logs' ? 'text-electric border-b-2 border-electric' : 'text-white/40 hover:text-white'}`}
          >
            <Terminal className="w-3.5 h-3.5" /> Live Log
          </button>
          <button
            onClick={() => setSideTab('residents')}
            className={`flex-1 py-3 text-xs font-mono uppercase tracking-wider transition-colors flex items-center justify-center gap-1.5
              ${sideTab === 'residents' ? 'text-electric border-b-2 border-electric' : 'text-white/40 hover:text-white'}`}
          >
            <Users className="w-3.5 h-3.5" /> Cư dân
          </button>
        </div>

        {/* Tab Content */}
        <AnimatePresence mode="wait">
          {sideTab === 'logs' ? (
            <motion.div
              key="logs"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className="flex-1 flex flex-col overflow-hidden"
            >
              {/* Log toolbar */}
              <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 flex-shrink-0">
                <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">
                  Lịch sử ra vào ({logs.length})
                </span>
                <button
                  onClick={refreshLogs}
                  className="p-1 rounded hover:bg-white/5 text-white/30 hover:text-white transition-colors"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>

              {/* Log entries */}
              <div className="flex-1 overflow-y-auto p-3 space-y-1.5 font-mono text-xs scrollbar-hide">
                {isLoading ? (
                  <div className="flex items-center justify-center h-16">
                    <Loader2 className="w-5 h-5 animate-spin text-electric/40" />
                  </div>
                ) : logs.length === 0 ? (
                  <div className="flex items-center justify-center h-16 text-white/20">
                    Chưa có lịch sử
                  </div>
                ) : (
                  <AnimatePresence initial={false}>
                    {logs.map((log, i) => (
                      <motion.div
                        key={`${log.id}-${log.thoi_gian}`}
                        initial={{ opacity: 0, x: 20, height: 0 }}
                        animate={{ opacity: 1, x: 0, height: 'auto' }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.25, delay: i === 0 ? 0 : 0 }}
                        className="p-2.5 rounded-lg bg-white/3 border border-white/5 hover:bg-white/5 transition-colors cursor-default"
                      >
                        {/* Top row: time + status */}
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-white/40 text-[9px]">
                            {formatTime(log.thoi_gian)}
                          </span>
                          <span
                            className="text-[8px] px-1.5 py-0.5 rounded font-bold"
                            style={{
                              backgroundColor: `${statusColor(log.trang_thai)}22`,
                              color: statusColor(log.trang_thai),
                              border: `1px solid ${statusColor(log.trang_thai)}44`,
                            }}
                          >
                            {statusLabel(log.trang_thai)}
                          </span>
                        </div>

                        {/* Biển số */}
                        <div className="flex items-center gap-1.5">
                          <ChevronRight className="w-3 h-3 text-electric/50 flex-shrink-0" />
                          <span className="text-electric font-bold text-[11px] tracking-wider">
                            {log.bien_so_xe}
                          </span>
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                )}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="residents"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
              className="flex-1 overflow-hidden"
            >
              <ResidentTable />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.aside>
    </motion.div>
  );
}
