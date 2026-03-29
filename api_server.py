"""
FastAPI Backend Server — Hệ thống nhận diện biển số xe thông minh
=================================================================
Endpoints:
  POST /api/detect         — Nhận ảnh base64/multipart, chạy YOLO+OCR, ghi DB
  GET  /api/logs           — Lịch sử ra vào từ bảng lichsuravao
  GET  /api/stats          — Thống kê: xe trong bãi, lượt vào/ra hôm nay
  GET  /api/residents      — Danh sách cư dân từ bảng cudan
  POST /api/residents      — Thêm cư dân mới
  DELETE /api/residents/{id} — Xóa cư dân
  GET  /api/health         — Kiểm tra trạng thái DB + model
  WS   /ws/live            — WebSocket push kết quả real-time tới tất cả clients

GPU: Tự động dùng CUDA (RTX 3060) nếu có, fallback CPU.
"""

import asyncio
import base64
import difflib
import io
import os
import sys
import time
import traceback
from contextlib import asynccontextmanager
from typing import List, Optional

import cv2
import numpy as np
import psycopg2
import psycopg2.extras
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    HTTPException, UploadFile, File, Form
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import threading
import serial

# ─── Fix encoding Windows ───────────────────────────────────────────────────

# ─── Fix encoding Windows ───────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

# ─── Cấu hình ──────────────────────────────────────────────────────────────
MODEL_PATH = "runs/detect/HeThongBarrier/Plate_Detection_v12/weights/best.pt"
CHAR_MODEL_PATH = "runs/classify/data/models/char_model/weights/best.pt"
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}
COOLDOWN_SECONDS = 5
CONFIDENCE_THRESHOLD = 0.45
# URLs are now dynamic based on state.camera_ip


# ─── State toàn cục ────────────────────────────────────────────────────────
class AppState:
    # Cooldown per plate
    last_plate_time: dict = {}
    yolo_model = None
    easyocr_reader = None
    use_cuda: bool = False
    
    # ESP32
    camera_ip: str = "172.20.10.2"
    latest_frame: Optional[np.ndarray] = None
    esp32_running: bool = False
    
    # Serial Port (Arduino)
    ser: Optional[serial.Serial] = None
    serial_port: str = "COM3"
    
    # Active WebSockets
    active_connections: List[WebSocket] = []
    
    # Detection state
    last_processed_plate: str = ""
    last_process_time: float = 0


state = AppState()


# ─── ESP32-CAM Capture Worker ──────────────────────────────────────────────
def esp32_worker():
    """Background task to fetch frames from ESP32-CAM"""
    print(f"[ESP32] Starting capture from http://{state.camera_ip}:81/stream...")
    state.esp32_running = True
    
    # Try MJPEG stream first via OpenCV
    cap = cv2.VideoCapture(f"http://{state.camera_ip}:81/stream")
    # Set buffer size to 1 to avoid "frozen" old frames
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    while state.esp32_running:
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                state.latest_frame = frame
                # Very short sleep to allow maximum throughput
                time.sleep(0.005)
            else:
                # Try fallback if stream fails
                try:
                    resp = requests.get(f"http://{state.camera_ip}/capture", timeout=1.0)
                    if resp.status_code == 200:
                        nparr = np.frombuffer(resp.content, np.uint8)
                        decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if decoded is not None:
                            state.latest_frame = decoded
                    time.sleep(0.05)
                except Exception:
                    print(f"[ESP32] Stream read failed. Retrying in 2s...")
                    cap.release()
                    time.sleep(2.0)
                    cap = cv2.VideoCapture(f"http://{state.camera_ip}:81/stream")
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            # Re-open stream
            cap = cv2.VideoCapture(ESP32_CAM_URL)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            time.sleep(2)


# ─── Lifespan: khởi tạo model khi startup ──────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 60)
    print("  KHOI DONG FASTAPI SERVER")
    print("=" * 60)
    
    # Kiểm tra GPU
    try:
        import torch
        state.use_cuda = torch.cuda.is_available()
        if state.use_cuda:
            gpu_name = torch.cuda.get_device_name(0)
            print(f"  ✅ GPU: {gpu_name}")
        else:
            print("  ⚠️  GPU không khả dụng — chạy trên CPU")
    except ImportError:
        print("  ⚠️  PyTorch không tìm thấy")

    # Khởi tạo Serial (Arduino)
    print(f"\n  [0/2] Đang kết nối Arduino tại {state.serial_port}...")
    try:
        state.ser = serial.Serial(state.serial_port, 9600, timeout=1)
        print(f"  ✅ Arduino đã kết nối tại {state.serial_port}")
    except Exception as e:
        print(f"  ⚠️ Không thể kết nối Arduino: {e} (Chế độ mô phỏng)")

    # Load YOLO model
    print(f"\n  [1/2] Đang tải YOLO model: {MODEL_PATH}")
    if os.path.exists(MODEL_PATH):
        try:
            from ultralytics import YOLO
            device = "cuda" if state.use_cuda else "cpu"
            state.yolo_model = YOLO(MODEL_PATH)
            state.yolo_model.to(device)
            print(f"  ✅ YOLO model đã tải (device={device})")
        except Exception as e:
            print(f"  ❌ Lỗi tải YOLO: {e}")
    else:
        print(f"  ❌ Không tìm thấy model tại: {MODEL_PATH}")

    # Khởi tạo EasyOCR
    print("\n  [2/2] Đang khởi tạo EasyOCR...")
    try:
        from core.ocr import init_easyocr
        state.easyocr_reader = init_easyocr()
        print("  ✅ EasyOCR đã sẵn sàng")
    except Exception as e:
        print(f"  ❌ Lỗi EasyOCR: {e}")

    print("\n  ✅ Server đã sẵn sàng tại http://localhost:8000")
    print("  📋 Swagger UI: http://localhost:8000/docs\n")
    
    # Start Workers
    threading.Thread(target=esp32_worker, daemon=True).start()
    threading.Thread(target=detect_worker, daemon=True).start() # Auto-pilot detection
    
    yield
    state.esp32_running = False
    if state.ser and state.ser.is_open:
        state.ser.close()
    print("\n  👋 Server đang tắt...")


# ─── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartPark ALPR API",
    description="API nhận diện biển số xe thông minh",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helpers DB ────────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


def normalize_plate(raw: str) -> str:
    s = (raw or "").strip().upper()
    for ch in [" ", ".", "-", "_"]:
        s = s.replace(ch, "")
    return s


def check_plate_in_db(plate: str) -> Optional[dict]:
    """Trả về dict {owner, can_ho, so_dien_thoai, ...} hoặc None"""
    norm = normalize_plate(plate)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ten_chu_xe, so_can_ho, bien_so_xe
                    FROM cudan
                    WHERE REPLACE(REPLACE(REPLACE(UPPER(bien_so_xe),' ',''),'-',''),'.','') = %s
                    """,
                    (norm,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"[DB] check_plate error: {e}")
        return None


def get_all_residents_for_fuzzy() -> list:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bien_so_xe, ten_chu_xe, so_can_ho FROM cudan")
                rows = cur.fetchall()
                return [(normalize_plate(r["bien_so_xe"]), r["bien_so_xe"], r["ten_chu_xe"]) for r in rows]
    except Exception as e:
        print(f"[DB] get_all_residents error: {e}")
        return []


def insert_history(plate: str, trang_thai: str, img_base64: Optional[str] = None) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lichsuravao (bien_so_xe, thoi_gian, trang_thai, anh_bien_so)
                    VALUES (%s, NOW(), %s, %s)
                    """,
                    (normalize_plate(plate), trang_thai, img_base64),
                )
                conn.commit()
    except Exception as e:
        print(f"[DB] insert_history error: {e}")


def open_arduino(com_port: str = "COM3", baud: int = 9600) -> bool:
    try:
        import serial
        with serial.Serial(com_port, baud, timeout=1) as ser:
            ser.write(b"O")
        return True
    except Exception as e:
        print(f"[Arduino] Không thể mở barrier: {e}")
        return False


# ─── Core: xử lý frame ─────────────────────────────────────────────────────
def process_frame_core(frame: np.ndarray, demo_mode: bool = True) -> dict:
    """
    Nhận numpy frame → YOLO detect → OCR → DB lookup → ghi lịch sử
    Trả về dict kết quả để gửi về frontend
    """
    if state.yolo_model is None:
        return {"detected": False, "error": "Model chưa được tải"}

    # YOLO detect
    try:
        results = state.yolo_model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
    except Exception as e:
        return {"detected": False, "error": f"YOLO lỗi: {e}"}

    best_conf = 0
    best_box = None
    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf > best_conf:
                best_conf = conf
                best_box = box.xyxy[0].cpu().numpy().astype(int)

    if best_box is None:
        return {"detected": False}

    x1, y1, x2, y2 = best_box
    plate_crop = frame[y1:y2, x1:x2]

    # OCR
    plate_text = ""
    try:
        if state.easyocr_reader is not None:
            from core.ocr import read_license_plate_2_lines
            ocr_result = read_license_plate_2_lines(state.easyocr_reader, frame, (x1, y1, x2, y2))
            if ocr_result.get("confidence", 0) > 0.3:
                plate_text = (ocr_result.get("line1", "") + ocr_result.get("line2", "")).strip()
        
        if not plate_text:
            return {
                "detected": True,
                "plate": "",
                "confidence": best_conf,
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "processed": False,
                "reason": "OCR không đọc được",
            }
    except Exception as e:
        return {"detected": True, "plate": "", "confidence": best_conf,
                "bbox": [int(x1), int(y1), int(x2), int(y2)], "error": f"OCR lỗi: {e}"}

    if len(plate_text) < 4:
        return {
            "detected": True,
            "plate": plate_text,
            "confidence": best_conf,
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "processed": False,
            "reason": "Biển số quá ngắn",
        }

    # Cooldown
    now = time.time()
    if (plate_text == state.last_plate_time.get("plate") and
            now - state.last_plate_time.get("ts", 0) < COOLDOWN_SECONDS):
        return {
            "detected": True,
            "plate": plate_text,
            "confidence": best_conf,
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "processed": False,
            "reason": "cooldown",
        }
    state.last_plate_time = {"plate": plate_text, "ts": now}

    # Toggle Vào/Ra
    prev_status = state.last_plate_status.get(plate_text, "Ra")
    next_status = "Vao" if prev_status == "Ra" else "Ra"
    state.last_plate_status[plate_text] = next_status

    # DB lookup — exact match trước
    resident = check_plate_in_db(plate_text)
    matched_plate = plate_text
    is_fuzzy = False

    if not resident:
        residents = get_all_residents_for_fuzzy()
        norm_det = normalize_plate(plate_text)
        best_ratio = 0
        for norm_r, orig_r, owner_name in residents:
            ratio = difflib.SequenceMatcher(None, norm_det, norm_r).ratio()
            if ratio > 0.82 and ratio > best_ratio:
                best_ratio = ratio
                resident = {"ten_chu_xe": owner_name, "bien_so_xe": orig_r}
                matched_plate = orig_r
                is_fuzzy = True

    if resident:
        owner = resident["ten_chu_xe"]
        insert_history(matched_plate, next_status, owner)

        # Mở Arduino nếu là xe vào và không phải demo
        barrier_opened = False
        if not demo_mode and next_status == "Vao":
            barrier_opened = open_arduino("COM3")

        return {
            "detected": True,
            "processed": True,
            "plate": plate_text,
            "matched_plate": matched_plate,
            "confidence": best_conf,
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "owner": owner,
            "can_ho": resident.get("so_can_ho", ""),
            "trang_thai": next_status,
            "is_fuzzy": is_fuzzy,
            "barrier_opened": barrier_opened,
            "is_resident": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    else:
        insert_history(plate_text, "Tu choi")
        return {
            "detected": True,
            "processed": True,
            "plate": plate_text,
            "confidence": best_conf,
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "owner": None,
            "trang_thai": "Tu choi",
            "is_resident": False,
            "barrier_opened": False,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


# ─── WebSocket Manager ──────────────────────────────────────────────────────
async def broadcast_detection(data: dict):
    """Gửi kết quả nhận diện tới tất cả clients qua WebSocket"""
    if not state.active_connections:
        return
    
    # Convert image paths if any to absolute URLs or relative to static
    dead_connections = []
    for ws in state.active_connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead_connections.append(ws)
    
    for ws in dead_connections:
        if ws in state.active_connections:
            state.active_connections.remove(ws)


def open_barrier():
    """Gửi lệnh mở cổng tới Arduino"""
    if state.ser and state.ser.is_open:
        try:
            state.ser.write(b'OPEN\n')
            print("[SERIAL] Đã gửi lệnh OPEN tới Arduino")
            return True
        except Exception as e:
            print(f"[SERIAL] Lỗi gửi lệnh: {e}")
    return False


def detect_worker():
    """Luồng nhận diện tự động từ ESP32 stream"""
    print("[AI-WORKER] Bắt đầu tự động nhận diện...")
    
    while state.esp32_running:
        if state.latest_frame is None or state.yolo_model is None:
            time.sleep(0.5)
            continue
            
        now = time.time()
        # Sub-500ms requirement: 200ms interval (5 FPS AI) is ideal for RTX3060
        if now - state.last_process_time < 0.2:
            time.sleep(0.05)
            continue
            
        # 1. Chạy YOLO
        frame = state.latest_frame.copy()
        try:
            results = state.yolo_model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)
            if not results or len(results[0].boxes) == 0:
                state.last_process_time = now
                continue
                
            # 2. Xử lý kết quả
            box = results[0].boxes[0]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            # Đảm bảo box trong khung hình
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = frame[y1:y2, x1:x2]
            
            # 3. OCR (sử dụng EasyOCR)
            plate_text = ""
            if state.easyocr_reader:
                ocr_results = state.easyocr_reader.readtext(crop)
                plate_text = "".join([res[1] for res in ocr_results]).upper()
                plate_text = "".join([c for c in plate_text if c.isalnum()])
            
            if not plate_text or len(plate_text) < 4:
                continue

            # 4. Kiểm tra Database & Điều khiển
            resident = check_plate_in_db(plate_text)
            
            # Fuzzy matching nếu không khớp trực tiếp
            if not resident:
                all_res = get_all_residents_for_fuzzy()
                for norm, original, owner in all_res:
                    ratio = difflib.SequenceMatcher(None, normalize_plate(plate_text), norm).ratio()
                    if ratio > 0.8:
                        resident = {"bien_so_xe": original, "ten_chu_xe": owner}
                        plate_text = original
                        break

            # 5. Broadcast & Log & Control
            # Cooldown để tránh spam 1 xe liên tục (vd: 10 giây)
            if plate_text != state.last_processed_plate or (now - state.last_process_time > 10):
                is_resident = resident is not None
                
                # Encode crop to base64 for logging
                _, buffer = cv2.imencode('.jpg', crop)
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Mở cổng nếu là cư dân
                barrier_opened = False
                if is_resident:
                    barrier_opened = open_barrier()
                
                # Log vào DB kèm ảnh x mảnh
                insert_history(plate_text, "Vao" if is_resident else "Tu Choi", img_base64)
                
                # Build JSON data
                detection_result = {
                    "detected": True,
                    "plate": plate_text,
                    "matched_plate": resident["bien_so_xe"] if resident else None,
                    "owner": resident["ten_chu_xe"] if resident else "Người lạ",
                    "can_ho": resident["so_can_ho"] if resident else "N/A",
                    "is_resident": is_resident,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float(box.conf[0]),
                    "processed": True,
                    "barrier_opened": barrier_opened,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "image": f"data:image/jpeg;base64,{img_base64}"
                }
                
                # Broadcast tới Web qua WebSocket
                asyncio.run(broadcast_detection(detection_result))
                
                state.last_processed_plate = plate_text
                print(f"[AI-WORKER] Phát hiện: {plate_text} (Resident: {is_resident}) - Barrier: {barrier_opened}")
            
            state.last_process_time = now
            
        except Exception as e:
            print(f"[AI-WORKER] Lỗi: {e}")
            traceback.print_exc()
            time.sleep(1)
        except ValueError:
            pass


# ═══════════════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
async def health():
    db_ok = False
    db_error = None
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_ok = True
    except Exception as e:
        db_error = str(e)

    return {
        "status": "ok",
        "db": "connected" if db_ok else f"error: {db_error}",
        "yolo": "loaded" if state.yolo_model is not None else "not loaded",
        "ocr": "loaded" if state.easyocr_reader is not None else "not loaded",
        "gpu": state.use_cuda,
    }


# ── Detect — nhận frame và xử lý ────────────────────────────────────────────
@app.post("/api/detect", tags=["Detection"])
async def detect_plate(
    image: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
    demo_mode: bool = Form(True),
):
    """
    Nhận frame từ frontend (multipart file hoặc base64 string),
    chạy YOLO + OCR, ghi DB, trả về kết quả JSON.
    """
    # Decode image
    img_bytes = None
    if image is not None:
        img_bytes = await image.read()
    elif image_base64:
        # Loại bỏ prefix data URL nếu có
        b64 = image_base64
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            img_bytes = base64.b64decode(b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Base64 decode lỗi: {e}")
    else:
        raise HTTPException(status_code=400, detail="Cần truyền 'image' (file) hoặc 'image_base64'")

    # Chuyển bytes → numpy array
    try:
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Không decode được ảnh")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi decode ảnh: {e}")

    # Xử lý qua AI
    try:
        result = process_frame_core(frame, demo_mode=demo_mode)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý AI: {e}")

    # Broadcast kết quả qua WebSocket nếu đã xử lý
    if result.get("processed"):
        await broadcast({"type": "detection", "data": result})

    return result


@app.get("/api/video_feed", tags=["System"])
async def video_feed():
    """Proxy stream từ ESP32 cho frontend hiển thị"""
    if state.latest_frame is None:
        return JSONResponse({"status": "error", "message": "Camera not ready"}, status_code=503)

    from fastapi.responses import StreamingResponse
    
    def gen():
        while True:
            if state.latest_frame is not None:
                # Encode with optimization (quality 80 is good for ALPR)
                _, jpeg = cv2.imencode('.jpg', state.latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            # Increase proxy speed (10ms ~ 100 FPS potential, limited by source)
            time.sleep(0.01) 

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.post("/api/detect_current", tags=["Detection"])
async def detect_current(demo_mode: bool = Form(True)):
    """Xử lý frame hiện tại đang có trong buffer của server"""
    if state.latest_frame is None:
        raise HTTPException(status_code=503, detail="Camera chưa sẵn sàng")
    
    try:
        result = process_frame_core(state.latest_frame, demo_mode=demo_mode)
        if result.get("processed"):
            await broadcast({"type": "detection", "data": result})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Logs ─────────────────────────────────────────────────────────────────────
@app.get("/api/logs", tags=["Logs"])
async def get_logs(limit: int = 50, status: str = "all", date: str = "all"):
    """
    Lấy lịch sử xe ra vào từ bảng lichsuravao.
    - status: 'all' | 'Vao' | 'Ra' | 'Tu choi'
    - date: 'all' | 'today' | 'week'
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                conditions = []
                params = []

                if status != "all":
                    conditions.append("trang_thai = %s")
                    params.append(status)

                if date == "today":
                    conditions.append("DATE(thoi_gian) = CURRENT_DATE")
                elif date == "week":
                    conditions.append("thoi_gian >= NOW() - INTERVAL '7 days'")

                where = "WHERE " + " AND ".join(conditions) if conditions else ""
                cur.execute(
                    f"""
                    SELECT id, bien_so_xe, thoi_gian, trang_thai, hinh_anh
                    FROM lichsuravao
                    {where}
                    ORDER BY thoi_gian DESC
                    LIMIT %s
                    """,
                    params + [limit],
                )
                rows = cur.fetchall()
                # Chuyển datetime sang ISO string
                result = []
                for row in rows:
                    r = dict(row)
                    if r.get("thoi_gian"):
                        r["thoi_gian"] = r["thoi_gian"].isoformat()
                    result.append(r)
                return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")


# ── Stats ────────────────────────────────────────────────────────────────────
@app.get("/api/stats", tags=["Stats"])
async def get_stats():
    """Thống kê: xe đang trong bãi, lượt vào/ra hôm nay"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Lượt vào hôm nay
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao WHERE trang_thai='Vao' AND DATE(thoi_gian)=CURRENT_DATE"
                )
                entries_today = cur.fetchone()["cnt"]

                # Lượt ra hôm nay
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao WHERE trang_thai='Ra' AND DATE(thoi_gian)=CURRENT_DATE"
                )
                exits_today = cur.fetchone()["cnt"]

                # Xe lạ hôm nay
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao WHERE trang_thai='Tu choi' AND DATE(thoi_gian)=CURRENT_DATE"
                )
                strangers_today = cur.fetchone()["cnt"]

                # Ước tính xe đang trong bãi = vào - ra (tuy chưa chính xác 100%)
                estimated_inside = max(0, entries_today - exits_today)

                return {
                    "inside": estimated_inside,
                    "entries_today": entries_today,
                    "exits_today": exits_today,
                    "strangers_today": strangers_today,
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")


# ── Residents ────────────────────────────────────────────────────────────────
@app.get("/api/residents", tags=["Residents"])
async def get_residents():
    """Danh sách cư dân từ bảng cudan"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, bien_so_xe, ten_chu_xe, so_can_ho FROM cudan ORDER BY ten_chu_xe"
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")


class ResidentCreate(BaseModel):
    bien_so_xe: str
    ten_chu_xe: str
    so_can_ho: str = ""


@app.post("/api/residents", tags=["Residents"])
async def add_resident(body: ResidentCreate):
    """Thêm cư dân mới"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho) VALUES (%s, %s, %s) RETURNING id",
                    (body.bien_so_xe.upper(), body.ten_chu_xe, body.so_can_ho),
                )
                new_id = cur.fetchone()["id"]
                conn.commit()
                return {"success": True, "id": new_id, "message": f"Đã thêm cư dân: {body.ten_chu_xe}"}
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail=f"Biển số {body.bien_so_xe} đã tồn tại")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")


@app.delete("/api/residents/{resident_id}", tags=["Residents"])
async def delete_resident(resident_id: int):
    """Xóa cư dân theo ID"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM cudan WHERE id=%s RETURNING ten_chu_xe", (resident_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Không tìm thấy cư dân")
                conn.commit()
                return {"success": True, "message": f"Đã xóa: {row['ten_chu_xe']}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")


# ── WebSocket Live ───────────────────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket endpoint: push kết quả nhận diện real-time tới client"""
    await websocket.accept()
    state.active_connections.append(websocket)
    print(f"[WS] Client kết nối. Tổng: {len(state.active_connections)}")
    try:
        # Keep-alive: ping mỗi 15 giây
        while True:
            await asyncio.sleep(15)
            await websocket.send_json({"type": "ping", "ts": time.time()})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            state.active_connections.remove(websocket)
        except ValueError:
            pass
        print(f"[WS] Client ngắt kết nối. Còn: {len(state.active_connections)}")


# ── Config ──────────────────────────────────────────────────────────────────
class ConfigIP(BaseModel):
    ip: str

@app.post("/api/config/camera_ip", tags=["Config"])
async def set_camera_ip(body: ConfigIP):
    """Cập nhật IP của ESP32-CAM từ giao diện"""
    state.camera_ip = body.ip
    print(f"[CONFIG] Đã cập nhật ESP32 IP thành: {state.camera_ip}")
    return {"success": True, "message": f"Đã cập nhật IP: {state.camera_ip}"}


# ─── Chạy server ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,          # Tắt reload khi production/GPU
        log_level="info",
    )
