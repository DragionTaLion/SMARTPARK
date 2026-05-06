/**
 * CameraFeed — Component hiển thị luồng MJPEG từ ESP32-CAM
 *
 * - Dùng <img> tag thay vì <video> vì MJPEG không phải định dạng HTML5 video
 * - Hiển thị bounding box thật từ YOLO khi có latestDetection
 * - Giữ nguyên Velorah animations (scanning pulse, glassmorphism overlay)
 */

import { motion, AnimatePresence } from 'motion/react';
import { useRef, useState, useEffect, useCallback } from 'react';
import { useSmartPark } from '../context/SmartParkContext';
import { API } from '../api/config';
import { Wifi, WifiOff, Camera, AlertTriangle } from 'lucide-react';

interface BBox {
  x1: number; y1: number;
  x2: number; y2: number;
}

export default function CameraFeed() {
  const { latestDetection, wsConnected } = useSmartPark();
  const imgRef    = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [imgError, setImgError] = useState(false);
  const [scaledBBox, setScaledBBox] = useState<BBox | null>(null);
  const [imgDims, setImgDims] = useState({ w: 1, h: 1, natW: 1, natH: 1 });

  // ── Scale bbox coordinates từ nhận diện YOLO → pixel màn hình ─────────────
  const recalcBBox = useCallback(() => {
    if (!latestDetection?.bbox || !imgRef.current || !containerRef.current) {
      setScaledBBox(null);
      return;
    }

    const img = imgRef.current;
    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();

    // Kích thước ảnh hiển thị thực tế (object-cover)
    const natW = img.naturalWidth  || 640;
    const natH = img.naturalHeight || 480;
    const dispW = containerRect.width;
    const dispH = containerRect.height;

    // object-cover: scale để ảnh lấp đầy container, cắt 2 cạnh dư ra
    const scaleX = dispW / natW;
    const scaleY = dispH / natH;
    const scale  = Math.max(scaleX, scaleY);

    // Offset để căn giữa (phần bị cắt)
    const offsetX = (dispW - natW * scale) / 2;
    const offsetY = (dispH - natH * scale) / 2;

    const [x1, y1, x2, y2] = latestDetection.bbox;
    setScaledBBox({
      x1: x1 * scale + offsetX,
      y1: y1 * scale + offsetY,
      x2: x2 * scale + offsetX,
      y2: y2 * scale + offsetY,
    });
    setImgDims({ w: dispW, h: dispH, natW, natH });
  }, [latestDetection]);

  useEffect(() => {
    recalcBBox();
  }, [recalcBBox]);

  // Recalc khi resize cửa sổ
  useEffect(() => {
    const ro = new ResizeObserver(recalcBBox);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [recalcBBox]);

  // Xoá bbox sau 8 giây (biển số đã qua)
  useEffect(() => {
    if (!latestDetection?.bbox) { setScaledBBox(null); return; }
    const timer = setTimeout(() => setScaledBBox(null), 8000);
    return () => clearTimeout(timer);
  }, [latestDetection]);

  const isResident = latestDetection?.is_resident;
  const bboxColor  = isResident ? '#38BDF8' : '#EF4444'; // electric hoặc đỏ

  return (
    <div ref={containerRef} className="w-full h-full relative overflow-hidden bg-black">
      {/* ── MJPEG stream từ FastAPI ─────────────────────────────────────── */}
      {!imgError ? (
        <img
          ref={imgRef}
          src={`${API.videoFeed}?t=${Date.now()}`}
          className="w-full h-full object-cover opacity-90"
          alt="ESP32-CAM Live Stream"
          onError={() => setImgError(true)}
          onLoad={(e) => {
            setImgError(false);
            // Trigger recalc sau khi ảnh load xong
            const img = e.currentTarget;
            if (img.naturalWidth) recalcBBox();
          }}
          // MJPEG: browser tự liên tục reload frame
          style={{ imageRendering: 'auto' }}
        />
      ) : (
        /* ── Fallback: No Camera ─────────────────────────────────────────── */
        <div className="w-full h-full flex flex-col items-center justify-center gap-4 bg-midnight/80">
          <motion.div
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <Camera className="w-16 h-16 text-white/20" />
          </motion.div>
          <p className="text-white/30 font-mono text-sm">CAMERA OFFLINE</p>
          <p className="text-white/20 font-mono text-xs">Kiểm tra kết nối ESP32-CAM</p>
          {/* Nút thử lại */}
          <button
            onClick={() => setImgError(false)}
            className="mt-2 px-4 py-1.5 text-xs font-mono border border-white/20 rounded hover:bg-white/5 text-white/50 hover:text-white transition-colors"
          >
            THỬ LẠI
          </button>
        </div>
      )}

      {/* ── Velorah Scanning Pulse (giữ nguyên animation gốc) ─────────────── */}
      <motion.div
        animate={{ y: ['0%', '100%', '0%'] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
        className="absolute left-0 right-0 h-[2px] bg-electric/50 shadow-[0_0_20px_rgba(56,189,248,0.8)] z-20 pointer-events-none"
      />

      {/* ── Real Bounding Box từ YOLO ───────────────────────────────────────── */}
      <AnimatePresence>
        {scaledBBox && (
          <motion.div
            key={latestDetection?.plate}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.3 }}
            className="absolute pointer-events-none z-30"
            style={{
              left: scaledBBox.x1,
              top:  scaledBBox.y1,
              width:  scaledBBox.x2 - scaledBBox.x1,
              height: scaledBBox.y2 - scaledBBox.y1,
              border: `2px solid ${bboxColor}`,
              boxShadow: `0 0 12px ${bboxColor}88`,
              backgroundColor: `${bboxColor}12`,
            }}
          >
            {/* Label biển số */}
            <div
              className="absolute -top-6 left-0 px-2 py-0.5 text-[10px] font-mono whitespace-nowrap"
              style={{
                backgroundColor: bboxColor,
                color: isResident ? '#0B1120' : '#fff',
              }}
            >
              {latestDetection?.matched_plate || latestDetection?.plate}
              {latestDetection?.confidence && (
                <span className="ml-1 opacity-70">
                  {(latestDetection.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>
            {/* Corner decorations */}
            {['top-0 left-0', 'top-0 right-0', 'bottom-0 left-0', 'bottom-0 right-0'].map((pos, i) => (
              <div key={i} className={`absolute w-3 h-3 ${pos}`}
                style={{
                  borderTop:    pos.includes('top')    ? `2px solid ${bboxColor}` : 'none',
                  borderBottom: pos.includes('bottom') ? `2px solid ${bboxColor}` : 'none',
                  borderLeft:   pos.includes('left')   ? `2px solid ${bboxColor}` : 'none',
                  borderRight:  pos.includes('right')  ? `2px solid ${bboxColor}` : 'none',
                }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Status Indicators (góc phải trên) ─────────────────────────────── */}
      <div className="absolute top-3 right-3 flex flex-col items-end gap-1.5 z-30 pointer-events-none">
        {/* WebSocket status */}
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-mono
          ${wsConnected ? 'bg-electric/20 text-electric border border-electric/30'
                        : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
          {wsConnected
            ? <><Wifi className="w-3 h-3" /></>
            : <><WifiOff className="w-3 h-3" /></>}
          {wsConnected ? 'WS LIVE' : 'WS OFF'}
        </div>

        {/* Biển số nhận diện mới nhất */}
        {latestDetection?.plate && (
          <motion.div
            key={latestDetection.plate}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            className="px-2 py-1 rounded text-[10px] font-mono bg-midnight/80 border border-white/10"
            style={{ color: bboxColor }}
          >
            {latestDetection.matched_plate || latestDetection.plate}
            {latestDetection.owner && (
              <span className="text-white/50 ml-1">— {latestDetection.owner}</span>
            )}
          </motion.div>
        )}
      </div>

      {/* ── IoT Processing Indicator ───────────────────────────────────────── */}
      {latestDetection && !latestDetection.detected && !latestDetection.plate && (
        <div className="absolute bottom-16 left-3 flex items-center gap-2 px-2 py-1 rounded bg-yellow-500/20 border border-yellow-500/30 text-yellow-400 text-[10px] font-mono z-30">
          <AlertTriangle className="w-3 h-3" />
          Không phát hiện biển số
        </div>
      )}

      {/* ── Camera Label (bottom left) ─────────────────────────────────────── */}
      <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-midnight/80 to-transparent pointer-events-none z-20">
        <div className="text-[10px] font-mono text-white/40">
          CAM_ESP32 // STREAM: MJPEG // {imgDims.natW}×{imgDims.natH}
        </div>
      </div>
    </div>
  );
}
