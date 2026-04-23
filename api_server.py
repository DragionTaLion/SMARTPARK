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
import json
from datetime import datetime, timedelta, timezone
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
MODEL_PATH = "data/models/plate_detect.pt"
CHAR_MODEL_PATH = "data/models/char_model/weights/best.pt"
# ═══════════════════════════════════════════════════════════════════════════
#  CẤU HÌNH DATABASE & ĐỒNG BỘ GIT-SYNC
# ═══════════════════════════════════════════════════════════════════════════
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

RESIDENTS_SYNC_FILE = os.path.join("data", "residents_sync.json")

def export_residents_to_json():
    """Xuất danh sách cư dân ra file JSON để đồng bộ qua Git."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bien_so_xe, ten_chu_xe, so_can_ho, anh_dang_ky, so_dien_thoai, da_thanh_toan, phi_thang FROM cudan")
                rows = cur.fetchall()
                # Chuyển đổi RealDictRow hoặc dict thành list dict thuần túy
                residents = [dict(r) for r in rows]
                
                os.makedirs(os.path.dirname(RESIDENTS_SYNC_FILE), exist_ok=True)
                with open(RESIDENTS_SYNC_FILE, "w", encoding="utf-8") as f:
                    json.dump(residents, f, ensure_ascii=False, indent=4)
                print(f"[SYNC] Đã sao lưu {len(residents)} cư dân vào {RESIDENTS_SYNC_FILE}")
    except Exception as e:
        print(f"[SYNC] Lỗi sao lưu cư dân: {e}")

def import_residents_from_json():
    """Nạp cư dân từ file JSON vào DB nếu DB đang trống."""
    if not os.path.exists(RESIDENTS_SYNC_FILE):
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as count FROM cudan")
                if cur.fetchone()["count"] > 0:
                    return # Đã có dữ liệu, không ghi đè
                
                with open(RESIDENTS_SYNC_FILE, "r", encoding="utf-8") as f:
                    residents = json.load(f)
                
                if not residents:
                    return
                
                print(f"[SYNC] Phát hiện file đồng bộ. Đang nạp {len(residents)} cư dân vào máy mới...")
                for r in residents:
                    cur.execute(
                        """INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho, anh_dang_ky, so_dien_thoai, da_thanh_toan, phi_thang) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (bien_so_xe) DO NOTHING""",
                        (r["bien_so_xe"], r["ten_chu_xe"], r["so_can_ho"], r["anh_dang_ky"], r["so_dien_thoai"], r["da_thanh_toan"], r.get("phi_thang", 500000))
                    )
                conn.commit()
                print("[SYNC] Nạp cư dân thành công!")
    except Exception as e:
        print(f"[SYNC] Lỗi nạp cư dân: {e}")
PARKING_CAPACITY = 3
COOLDOWN_SECONDS = 5
CONFIDENCE_THRESHOLD = 0.3
MONTHLY_FEE = 500000
VISITOR_FLAT_FEE = 20000 # 20k/lượt
FREE_MINUTES = 30         # Miễn phí 30p đầu

# ─── State toàn cục ────────────────────────────────────────────────────────
class GateState:
    def __init__(self, gate_id: int, ip: str):
        self.gate_id = gate_id
        self.ip = ip
        self.latest_frame: Optional[np.ndarray] = None
        self.last_process_time: float = 0
        self.last_processed_plate: str = ""
        self.camera_active: bool = False

class AppState:
    def __init__(self):
        # Mặc định 2 cổng
        self.gates = {
            1: GateState(1, "192.168.0.102"), # Làn Vào
            2: GateState(2, "192.168.0.102")  # Làn Ra
        }
        self.sensor_states = [0, 0, 0, 0, 0] # Trạng thái 5 cảm biến IR
        
        # AI Models
        self.yolo_model = None
        self.char_model = None
        self.use_cuda: bool = False
        
        # System
        self.is_running: bool = True
        self.active_connections: List[WebSocket] = []
        self.ser: Optional[serial.Serial] = None
        self.com_port: str = "COM3"
        self.esp8266_ip: str = "192.168.0.105"
        self.camera_mode: str = "esp32"
        
        # Cooldown per plate
        self.last_plate_time: dict = {}
        self.last_plate_status: dict = {}  # plate -> 'Vao' | 'Ra'
        
        # Hàng đợi lệnh mở cổng cho ESP (visitor pay)
        self.pending_open_gates: List[int] = []
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

state = AppState()

# Load/Save config
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                conf = json.load(f)
                if "gate1_ip" in conf:
                    state.gates[1].ip = conf["gate1_ip"]
                if "gate2_ip" in conf:
                    state.gates[2].ip = conf["gate2_ip"]
                if "esp8266_ip" in conf:
                    state.esp8266_ip = conf["esp8266_ip"]
                print(f"[CONFIG] Đã tải cấu hình: Gate1={state.gates[1].ip}, Gate2={state.gates[2].ip}, ESP={state.esp8266_ip}")
        except Exception as e:
            print(f"[CONFIG] Lỗi load config: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "gate1_ip": state.gates[1].ip,
                "gate2_ip": state.gates[2].ip,
                "esp8266_ip": state.esp8266_ip
            }, f)
        print("[CONFIG] Đã lưu cấu hình hệ thống.")
    except Exception as e:
        print(f"[CONFIG] Lỗi save config: {e}")

# Apply initial load
load_config()

# ─── Camera Workers ────────────────────────────────────────────────────────
def camera_worker(gate_id: int):
    """Luồng chuyên biệt để lấy frame cho từng cổng"""
    gate = state.gates.get(gate_id)
    if not gate: return
    
    print(f"[CAMERA-{gate_id}] Bắt đầu lấy luồng từ: {gate.ip}")
    gate.camera_active = True
    
    url = f"http://{gate.ip}:81/stream"
    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Giảm trễ
    
    while state.is_running and gate.camera_active:
        if not cap.isOpened():
            print(f"[CAMERA-{gate_id}] Đang thử kết nối lại...")
            time.sleep(2)
            cap = cv2.VideoCapture(url)
            continue
            
        ret, frame = cap.read()
        if ret:
            gate.latest_frame = frame
            time.sleep(0.01) # Tránh nghẽn CPU
        else:
            print(f"[CAMERA-{gate_id}] Mất luồng. Đang thử lại...")
            cap.release()
            time.sleep(1)
            cap = cv2.VideoCapture(url)
    
    if cap: cap.release()

# ─── Lifespan: khởi tạo model khi startup ──────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 60)
    print("  KHOI DONG SMARTPARK V2 SERVER")
    print("=" * 60)
    
    # Lưu event loop chính để dùng trong các thread khác
    state.main_loop = asyncio.get_running_loop()
    
    # Kiểm tra GPU
    try:
        import torch
        state.use_cuda = torch.cuda.is_available()
        if state.use_cuda:
            gpu_name = torch.cuda.get_device_name(0)
            print(f"  ✅ GPU: {gpu_name}")
        else:
            print("  ⚠️ GPU không khả dụng — chạy trên CPU")
    except ImportError:
        print("  ⚠️ PyTorch không tìm thấy")

    # Đã chuyển sang dùng IP (ESP8266), bỏ qua Serial
    print("\n  [0/2] Chế độ điều khiển: IP (Wireless)...")
    
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

    # Load Character YOLO model (Stage 2)
    print(f"  [2/2] Đang tải Character model: {CHAR_MODEL_PATH}")
    if os.path.exists(CHAR_MODEL_PATH):
        try:
            state.char_model = YOLO(CHAR_MODEL_PATH)
            state.char_model.to(device)
            print(f"  ✅ Character model đã tải (device={device})")
        except Exception as e:
            print(f"  ❌ Lỗi tải Character model: {e}")
    else:
        print(f"  ❌ Không tìm thấy model tại: {CHAR_MODEL_PATH}")

    # Khởi chạy các luồng xử lý cho từng cổng (V2 Dual-Gate)
    for gate_id in state.gates.keys():
        # Luồng lấy frame từ camera
        threading.Thread(target=camera_worker, args=(gate_id,), daemon=True, name=f"CameraWorker-{gate_id}").start()
        # Luồng nhận diện biển số (Auto-pilot)
        threading.Thread(target=detect_worker, args=(gate_id,), daemon=True, name=f"DetectWorker-{gate_id}").start()
    
    yield
    state.is_running = False
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


def open_gate_http(gate_id: int):
    """Gửi lệnh mở cổng qua HTTP tới ESP8266"""
    if not state.esp8266_ip: 
        print("[HARDWARE] Chưa cấu hình IP ESP8266")
        return
    
    url = f"http://{state.esp8266_ip}/open?gate={gate_id}"
    print(f"[HARDWARE] Đang gửi lệnh mở cổng {gate_id} tới {url}...")
    
    def send_request():
        try:
            import requests
            requests.get(url, timeout=3)
            print(f"  ✅ Đã gửi lệnh tới ESP8266 thành công.")
        except Exception as e:
            print(f"  ❌ Lỗi gửi lệnh tới ESP8266: {e}")
            
    threading.Thread(target=send_request, daemon=True).start()

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
                    SELECT id, ten_chu_xe, so_can_ho, bien_so_xe, so_dien_thoai, da_thanh_toan, anh_dang_ky
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


def insert_history(plate: str, trang_thai: str, img_base64: Optional[str] = None, ten_chu_xe: Optional[str] = None, gate_id: Optional[int] = None) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Thử thêm cột gate_id vào query nếu tồn tại (để tương lai mở rộng)
                # Hiện tại chỉ focus vào sửa lỗi TypeError
                # Lấy giờ Việt Nam (ICT) ở dạng Naive (để lưu chính xác 14:45 vào DB)
                vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
                insert_query = """
                    INSERT INTO lichsuravao (bien_so_xe, thoi_gian, trang_thai, anh_bien_so)
                    VALUES (%s, %s, %s, %s)
                """
                params = (normalize_plate(plate), vn_now, trang_thai, img_base64)
                
                cur.execute(insert_query, params)
                conn.commit()
                
                # Thông báo cho tất cả Clients làm mới Thống kê (Real-time)
                if state.main_loop and state.main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(broadcast_message({"type": "refresh_stats"}), state.main_loop)
    except Exception as e:
        print(f"[DB] insert_history error: {e}")

def get_current_parking_count() -> int:
    """Đếm số lượng xe hiện đang có trong bãi (có 'Vào' gần nhất mà chưa có 'Ra')"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Logic đơn giản: đếm các xe có trạng thái cuối cùng là 'Vao'
                cur.execute("""
                    WITH last_status AS (
                        SELECT bien_so_xe, trang_thai,
                        ROW_NUMBER() OVER(PARTITION BY bien_so_xe ORDER BY thoi_gian DESC) as rn
                        FROM lichsuravao
                    )
                    SELECT COUNT(*) as count FROM last_status WHERE rn = 1 AND trang_thai = 'Vao'
                """)
                return cur.fetchone()['count']
    except Exception:
        return 0

def get_entry_image(plate: str) -> Optional[str]:
    """Lấy ảnh lúc xe vào gần nhất cho một biển số"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT anh_bien_so FROM lichsuravao 
                    WHERE bien_so_xe = %s AND trang_thai = 'Vao'
                    ORDER BY thoi_gian DESC LIMIT 1
                """, (normalize_plate(plate),))
                row = cur.fetchone()
                return row['anh_bien_so'] if row else None
    except Exception:
        return None


# Legacy bridge for hardware triggers removed. Using /api/hardware/status now.


def is_visitor_in_lot(plate: str) -> bool:
    """Kiểm tra xe khách có đang trong bãi không"""
    try:
        norm = normalize_plate(plate)
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Đếm lượt Vao của khách
                cur.execute("""
                    SELECT COUNT(*) as cnt FROM lichsuravao
                    WHERE bien_so_xe = %s AND trang_thai = 'Vao'
                    AND bien_so_xe NOT IN (SELECT bien_so_xe FROM cudan)
                """, (norm,))
                vao_count = cur.fetchone()['cnt']
                # Đếm lượt Ra tương ứng
                cur.execute("""
                    SELECT COUNT(*) as cnt FROM lichsuravao
                    WHERE bien_so_xe = %s AND trang_thai = 'Ra'
                    AND bien_so_xe NOT IN (SELECT bien_so_xe FROM cudan)
                """, (norm,))
                ra_count = cur.fetchone()['cnt']
                return vao_count > ra_count
    except Exception as e:
        print(f"[DB] is_visitor_in_lot error: {e}")
        return False


def get_visitor_last_entry(plate: str):
    """Tìm thời gian vào gần nhất của xe vãng lai chưa có lượt ra"""
    try:
        norm = normalize_plate(plate)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT thoi_gian FROM lichsuravao
                    WHERE bien_so_xe = %s AND trang_thai = 'Vao'
                    ORDER BY thoi_gian DESC LIMIT 1
                """, (norm,))
                row = cur.fetchone()
                return row['thoi_gian'] if row else None
    except Exception:
        return None


# ─── Core: xử lý frame ─────────────────────────────────────────────────────
def process_frame_core(frame: np.ndarray) -> dict:
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
        
        # Mảnh base64 để lưu log
        _, buffer = cv2.imencode('.jpg', plate_crop)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Trả về kết quả (Việc ghi history sẽ do worker hoặc trigger API đảm nhận)
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
            "barrier_opened": True,
            "is_resident": True,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "plate_crop_base64": img_base64
        }
    else:
        _, buffer = cv2.imencode('.jpg', plate_crop)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
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
            "plate_crop_base64": img_base64
        }


# ─── WebSocket Manager ──────────────────────────────────────────────────────
async def broadcast_message(data: dict):
    """Gửi một message bất kỳ tới tất cả clients qua WebSocket"""
    if not state.active_connections:
        return
    
    dead_connections = []
    for ws in state.active_connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead_connections.append(ws)
    
    for ws in dead_connections:
        if ws in state.active_connections:
            state.active_connections.remove(ws)

async def broadcast_detection(data: dict):
    """Gửi kết quả nhận diện tới tất cả clients qua WebSocket"""
    await broadcast_message(data)


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


# ─── Detection Worker ──────────────────────────────────────────────────────
def detect_worker(gate_id: int):
    """Luồng nhận diện tự động chuyên biệt cho từng cổng"""
    gate = state.gates.get(gate_id)
    if not gate: return
    
    print(f"[AI-WORKER-{gate_id}] Bắt đầu nhận diện cho lối { 'VÀO' if gate_id==1 else 'RA' }")
    
    while state.is_running and gate.camera_active:
        if gate.latest_frame is None or state.yolo_model is None:
            time.sleep(0.5)
            continue
            
        now = time.time()
        # Giới hạn xử lý (VD: 5 FPS per channel)
        if now - gate.last_process_time < 0.2:
            time.sleep(0.05)
            continue
            
        # 💡 [DÀNH CHO MÁY KHÔNG CHẠY AI]: 
        # Nếu máy bạn yếu hoặc không có Card đồ họa, bạn có thể comment đoạn '1. Chạy YOLO' 
        # phía dưới và bỏ comment đoạn giả lập (MOCK) để test luồng giao diện.
        
        # --- ĐOẠN GIẢ LẬP (MOCK) ĐỂ TEST ---
        # if False: # Đổi thành True để test không cần AI
        #     plate_text = "30A12345" # Biển số giả lập
        #     resident = {"bien_so_xe": "30A12345", "ten_chu_xe": "Cư Dân Giả Lập"}
        #     results = [True] # Giả lập có kết quả
        # ----------------------------------

        # 1. Chạy YOLO
        frame = gate.latest_frame.copy()
        try:
            results = state.yolo_model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)
            if not results or len(results[0].boxes) == 0:
                gate.last_process_time = now
                continue
            
            # 2. Xử lý kết quả (Lấy box đầu tiên)
            box = results[0].boxes[0]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = frame[y1:y2, x1:x2]
            
            # 3. Nhận diện ký tự (SỬ DỤNG AI THUẦN YOLO CHO STAGE 2)
            plate_text = ""
            if state.char_model:
                char_results = state.char_model.predict(crop, conf=0.4, verbose=False)
                if len(char_results) > 0:
                    chars = []
                    for c_box in char_results[0].boxes:
                        x1_c, y1_c, x2_c, y2_c = c_box.xyxy[0]
                        cls_idx = int(c_box.cls[0])
                        char_val = state.char_model.names[cls_idx]
                        chars.append({
                            'val': char_val,
                            'x': (x1_c + x2_c) / 2,
                            'y': (y1_c + y2_c) / 2
                        })
                    
                    if chars:
                        # THUẬT TOÁN SẮP XẾP KÝ TỰ THÔNG MINH (Hỗ trợ biển 1 dòng và 2 dòng)
                        # Sắp xếp theo trục Y trước để phân dòng
                        chars.sort(key=lambda c: c['y'])
                        
                        y_coords = [c['y'] for c in chars]
                        min_y, max_y = min(y_coords), max(y_coords)
                        
                        # Nếu khoảng cách Y lớn hơn 1/4 chiều cao ảnh cắt thì khả năng là biển 2 dòng
                        is_two_line = (max_y - min_y) > (crop.shape[0] / 4)
                        
                        if is_two_line:
                            mid_y = (min_y + max_y) / 2
                            line1 = [c for c in chars if c['y'] < mid_y]
                            line2 = [c for c in chars if c['y'] >= mid_y]
                            line1.sort(key=lambda c: c['x'])
                            line2.sort(key=lambda c: c['x'])
                            plate_text = "".join([c['val'] for c in line1]) + "".join([c['val'] for c in line2])
                        else:
                            chars.sort(key=lambda c: c['x'])
                            plate_text = "".join([c['val'] for c in chars])
            
            plate_text = plate_text.upper()
            if not plate_text or len(plate_text) < 4:
                continue

            # 4. Kiểm tra Database
            resident = check_plate_in_db(plate_text)
            
            # Fuzzy matching
            if not resident:
                all_res = get_all_residents_for_fuzzy()
                for norm, original, owner in all_res:
                    ratio = difflib.SequenceMatcher(None, normalize_plate(plate_text), norm).ratio()
                    if ratio > 0.8:
                        resident = {"bien_so_xe": original, "ten_chu_xe": owner}
                        plate_text = original
                        break

            # 5. Xử lý logic Mở Cổng & Ghi nhật ký
            if plate_text != gate.last_processed_plate or (now - gate.last_process_time > 10):
                is_resident = resident is not None
                
                # ── Xác định trạng thái dựa trên gate và loại xe ──
                if gate_id == 1:
                    # CỔNG VÀO: cư dân → Vao, khách → Vao (ghi nhận thời điểm vào để tính tiền lúc ra)
                    trang_thai = "Vao" if is_resident else "Vao" 
                elif gate_id == 2:
                    # CỔNG RA: cư dân → Ra, khách trong bãi → Tu choi (yêu cầu thu phí trước khi cho ra)
                    if is_resident:
                        trang_thai = "Ra"
                    elif is_visitor_in_lot(plate_text):
                        trang_thai = "Tu choi" # Xe khách cần thanh toán mới được chuyển sang 'Ra'
                    else:
                        trang_thai = "Tu choi"

                # ── Gửi lệnh mở cổng nếu là cư dân hợp lệ ──
                if trang_thai in ["Vao", "Ra"] and is_resident:
                    open_gate_http(gate_id)
                    print(f"  >>> MỞ CỔNG {gate_id} (Cư dân)")

                # Encode crop base64
                _, buffer = cv2.imencode('.jpg', crop)
                img_base64 = base64.b64encode(buffer).decode('utf-8')

                # Ghi log vào DB (cư dân vào/ra, khách ra, hoặc từ chối)
                # Khách vào KHÔNG ghi ở đây — ghi khi bảo vệ xác nhận qua /api/visitor/pay
                if not (gate_id == 1 and not is_resident):
                    insert_history(plate_text, trang_thai, img_base64, gate_id=gate_id)

                # Broadcast tới Web
                is_visitor_alert = (not is_resident and ((gate_id == 1) or (gate_id == 2 and is_visitor_in_lot(plate_text))))
                
                # Logic: Cổng 1 vãng lai -> Vào ngay (ghi log), Cổng 2 vãng lai -> Alert
                if gate_id == 1 and not is_resident:
                    insert_history(plate_text, "Vao", img_base64, gate_id=gate_id)
                    trang_thai = "Vao"
                    is_visitor_alert = False # Không cần alert ở cổng vào nữa vì thu tiền ở cổng ra

                # Lấy ảnh lúc vào để đối chiếu nếu là cổng ra và là xe khách
                entry_image_base64 = None
                if gate_id == 2 and not is_resident:
                    entry_image_base64 = get_entry_image(plate_text)

                detection_result = {
                    "gate_id": gate_id,
                    "gate_name": "Làn Vào" if gate_id == 1 else "Làn Ra",
                    "plate": plate_text,
                    "owner": resident["ten_chu_xe"] if (resident and is_resident) else "Khách vãng lai",
                    "is_resident": is_resident,
                    "trang_thai": trang_thai,
                    "processed": True,
                    "visitor_alert": is_visitor_alert,
                    "timestamp": datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None).strftime("%H:%M:%S"),
                    "image": f"data:image/jpeg;base64,{img_base64}",
                    "entry_image": f"data:image/jpeg;base64,{entry_image_base64}" if entry_image_base64 else None
                }
                # Broadcast tới Web (Thread-safe)
                if state.main_loop and state.main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(broadcast_detection(detection_result), state.main_loop)


                gate.last_processed_plate = plate_text
                log_label = "Khách (chờ thu phí)" if is_visitor_alert else trang_thai
                print(f"[AI-{gate_id}] Phát hiện: {plate_text} → {log_label}")

            gate.last_process_time = now
            
        except Exception as e:
            print(f"[AI-WORKER-{gate_id}] Lỗi: {e}")
            time.sleep(1)


# ═══════════════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
async def health():
    db_ok = False
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_ok = True
    except: pass
    return {
        "status": "ok",
        "db": "connected" if db_ok else "error",
        "gpu": state.use_cuda,
        "camera_mode": state.camera_mode
    }

@app.get("/api/video_feed", tags=["System"])
async def video_feed(gate_id: int = 1):
    """Proxy stream từ ESP32 cho frontend hiển thị"""
    gate = state.gates.get(gate_id)
    if not gate or gate.latest_frame is None:
        return JSONResponse({"status": "error", "message": "Camera not ready"}, status_code=503)
    from fastapi.responses import StreamingResponse
    def gen():
        while True:
            if gate.latest_frame is not None:
                _, jpeg = cv2.imencode('.jpg', gate.latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.04)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

# ── Hardware Trigger ────────────────────────────────────────────────────────


@app.post("/api/iot/trigger", tags=["Hardware"])
async def iot_trigger(gate: str = "in"):
    return await hardware_trigger(gate)

@app.post("/api/trigger", tags=["Hardware"])
async def hardware_trigger(gate: str = "in"):
    """Cổng kết nối thực tế dành cho ESP8266/ESP32-CAM"""
    gate_id = 1 if gate == "in" else 2
    gate_obj = state.gates.get(gate_id)
    
    if not gate_obj or gate_obj.latest_frame is None:
        return {"action": "deny", "reason": "Camera chưa sẵn sàng"}

    occupied = get_current_parking_count()
    if gate == "in" and occupied >= PARKING_CAPACITY:
        return {"action": "deny", "reason": "Bãi xe đã đầy"}

    frame = gate_obj.latest_frame.copy()
    result = process_frame_core(frame)

    if not result.get("processed"):
        return {"action": "deny", "reason": "Không nhận diện được"}

    plate = result.get("plate")
    is_resident = result.get("is_resident", False)
    action = "open" if is_resident or gate == "in" else "deny"

    # 💡 LƯU Ý QUAN TRỌNG: 
    # ESP8266 sẽ tự mở cổng nếu nhận được {"action":"open"} trong response của POST này.
    # Do đó chúng ta KHÔNG gọi open_gate_http(gate_id) ở đây để tránh gửi 2 lệnh trùng lặp.
    
    # Đồng bộ UI
    result["gate_id"] = gate_id
    result["visitor_alert"] = (not is_resident and gate == "out")
    await broadcast_detection(result)
    
    # Ghi log
    insert_history(plate, "Vao" if gate == "in" else "Ra", result.get("image", ""), gate_id=gate_id)

    return {"action": action, "plate": plate, "owner": result.get("owner")}

# ── Logs ─────────────────────────────────────────────────────────────────────


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
                    if status == "stranger":
                        # Lọc tất cả khách vãng lai (Không có trong danh sách cư dân)
                        conditions.append(f"""
                            NOT EXISTS (
                                SELECT 1 FROM cudan c 
                                WHERE UPPER(REGEXP_REPLACE(c.bien_so_xe, '[.\\-\\s_]', '', 'g')) = 
                                      UPPER(REGEXP_REPLACE(lichsuravao.bien_so_xe, '[.\\-\\s_]', '', 'g'))
                            )
                        """)
                    else:
                        # Lọc theo trạng thái cụ thể: 'Vao', 'Ra', hoặc 'Tu choi' (Xe bị chặn)
                        conditions.append("trang_thai = %s")
                        params.append(status)

                if date == "today":
                    vn_today = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None).date()
                    conditions.append("DATE(thoi_gian) = %s")
                    params.append(vn_today)
                elif date == "week":
                    vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
                    conditions.append("thoi_gian >= %s - INTERVAL '7 days'")
                    params.append(vn_now)

                where = "WHERE " + " AND ".join(conditions) if conditions else ""
                cur.execute(
                    f"""
                    SELECT id, bien_so_xe, thoi_gian, trang_thai, anh_bien_so as hinh_anh
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
@app.delete("/api/logs/all", tags=["Logs"])
async def delete_all_logs():
    """Xóa toàn bộ lịch sử ra vào (Dùng để test)"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM lichsuravao")
                conn.commit()
                # Reset thanh thống kê ngay lập tức
                await broadcast_message({"type": "refresh_stats"})
                return {"success": True, "message": "Đã xóa toàn bộ lịch sử"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", tags=["Stats"])
async def get_stats():
    """Thống kê: xe đang trong bãi, lượt vào/ra hôm nay"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Lượt vào hôm nay - Dùng khoảng thời gian từ 0h sáng tới hiện tại
                vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
                start_of_today = vn_now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao WHERE trang_thai='Vao' AND thoi_gian >= %s",
                    (start_of_today,)
                )
                entries_today = cur.fetchone()["cnt"]

                # Lượt ra hôm nay
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao WHERE trang_thai='Ra' AND thoi_gian >= %s",
                    (start_of_today,)
                )
                exits_today = cur.fetchone()["cnt"]

                # Đếm người lạ: Số lượng BIỂN SỐ duy nhất không thuộc bảng cudan xuất hiện hôm nay
                cur.execute("""
                    SELECT COUNT(DISTINCT l.bien_so_xe) as cnt 
                    FROM lichsuravao l
                    WHERE l.thoi_gian >= %s
                    AND NOT EXISTS (
                        SELECT 1 FROM cudan c 
                        WHERE UPPER(REGEXP_REPLACE(c.bien_so_xe, '[.\\-\\s_]', '', 'g')) = 
                              UPPER(REGEXP_REPLACE(l.bien_so_xe, '[.\\-\\s_]', '', 'g'))
                    )
                """, (start_of_today,))
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
                    "SELECT id, bien_so_xe, ten_chu_xe, so_can_ho, anh_dang_ky, so_dien_thoai, da_thanh_toan, phi_thang FROM cudan ORDER BY ten_chu_xe"
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")


class ResidentCreate(BaseModel):
    bien_so_xe: str
    ten_chu_xe: str
    so_can_ho: str
    so_dien_thoai: str = ""
    da_thanh_toan: bool = False
    anh_dang_ky: str = ""
    phi_thang: int = 500000
    da_thanh_toan: Optional[bool] = False


@app.post("/api/residents", tags=["Residents"])
async def add_resident(body: ResidentCreate):
    """Thêm cư dân mới"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho, anh_dang_ky, so_dien_thoai, da_thanh_toan, phi_thang) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (body.bien_so_xe.upper(), body.ten_chu_xe, body.so_can_ho, body.anh_dang_ky, body.so_dien_thoai, body.da_thanh_toan, body.phi_thang),
                )
                new_id = cur.fetchone()["id"]
                conn.commit()
                
                # Đồng bộ cư dân ra file sau khi thêm mới
                export_residents_to_json()
                
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
                
                # Đồng bộ cư dân sau khi xóa
                export_residents_to_json()
                
                return {"success": True, "message": f"Đã xóa: {row['ten_chu_xe']}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")

@app.put("/api/residents/{resident_id}", tags=["Residents"])
async def update_resident(resident_id: int, body: ResidentCreate):
    """Cập nhật thông tin cư dân"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cudan 
                    SET bien_so_xe=%s, ten_chu_xe=%s, so_can_ho=%s, anh_dang_ky=%s, so_dien_thoai=%s, da_thanh_toan=%s, phi_thang=%s, updated_at=%s
                    WHERE id=%s
                    """,
                    (body.bien_so_xe.upper(), body.ten_chu_xe, body.so_can_ho, body.anh_dang_ky, body.so_dien_thoai, body.da_thanh_toan, body.phi_thang, datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None), resident_id)
                )
                conn.commit()
                
                # Đồng bộ cư dân sau khi cập nhật
                export_residents_to_json()
                
                return {"success": True, "message": "Cập nhật thành công"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi DB: {e}")

@app.post("/api/residents/{resident_id}/toggle_payment", tags=["Residents"])
async def toggle_payment(resident_id: int):
    """Đổi trạng thái thanh toán nhanh và quản lý doanh thu (SỬA LỖI THU CHỒNG)"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Lấy trạng thái cũ, biển số và MỨC PHÍ RIÊNG của cư dân
                cur.execute("SELECT da_thanh_toan, bien_so_xe, phi_thang FROM cudan WHERE id = %s", (resident_id,))
                res = cur.fetchone()
                if not res:
                    raise HTTPException(status_code=404, detail="Không tìm thấy cư dân")
                
                old_status = res['da_thanh_toan']
                new_status = not old_status
                plate = res['bien_so_xe']
                custom_fee = res['phi_thang']

                # Cập nhật trạng thái cư dân
                cur.execute("UPDATE cudan SET da_thanh_toan = %s WHERE id = %s", (new_status, resident_id))
                
                # Lấy giờ Việt Nam (Naive)
                vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
                vn_today = vn_now.date()

                # Xử lý Doanh Thu
                if new_status:
                    # Chuyển sang ĐÃ THANH TOÁN: Kiểm tra xem tháng này đã có chưa (để tránh thu trùng)
                    # Sử dụng vn_now để so sánh tháng
                    cur.execute("""
                        SELECT id FROM doanh_thu 
                        WHERE resident_id = %s 
                        AND date_trunc('month', ngay_thanh_toan) = date_trunc('month', %s::timestamp)
                        LIMIT 1
                    """, (resident_id, vn_now))
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO doanh_thu (resident_id, bien_so_xe, so_tien, loai_phi, ngay_thanh_toan) VALUES (%s, %s, %s, %s, %s)",
                            (resident_id, plate, custom_fee, 'MONTHLY', vn_now)
                        )
                else:
                    # Chuyển sang CHƯA THANH TOÁN (Hủy thu): Xóa bản ghi thu phí gần nhất của tháng này
                    cur.execute("""
                        DELETE FROM doanh_thu 
                        WHERE id IN (
                            SELECT id FROM doanh_thu 
                            WHERE resident_id = %s 
                            AND date_trunc('month', ngay_thanh_toan) = date_trunc('month', %s::timestamp)
                            ORDER BY ngay_thanh_toan DESC 
                            LIMIT 1
                        )
                    """, (resident_id, vn_now))
                
                conn.commit()
                
                # Đồng bộ cư dân sau khi đổi trạng thái thanh toán
                export_residents_to_json()
                
                return {"success": True, "da_thanh_toan": new_status}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/revenue/{revenue_id}", tags=["Revenue"])
async def delete_revenue(revenue_id: int):
    """Xóa một bản ghi doanh thu (dùng để dọn dẹp dữ liệu giả lập/sai)."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM doanh_thu WHERE id = %s", (revenue_id,))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi doanh thu")
                conn.commit()
                return {"success": True, "message": "Đã xóa bản ghi doanh thu"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/residents/{resident_id}", tags=["Residents"])
async def get_resident_detail(resident_id: int):
    """Lấy thông tin chi tiết cư dân cho modal Profile"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM cudan WHERE id = %s", (resident_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Không tìm thấy cư dân")
                return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scan_registration", tags=["Residents"])
async def scan_registration():
    """Chụp ảnh từ camera cổng vào và nhận diện phục vụ đăng ký"""
    gate = state.gates.get(1) # Luôn lấy từ cổng vào
    if not gate or gate.latest_frame is None:
        raise HTTPException(status_code=503, detail="Camera chưa sẵn sàng")
    
    frame = gate.latest_frame.copy()
    # Chạy xử lý AI (không lưu log ra bảng lịch sử ở giai đoạn đăng ký)
    res = process_frame_core(frame, demo_mode=True)
    
    return {
        "plate": res.get("plate", ""),
        "plate_crop": res.get("plate_crop_base64", ""),
        "detected": res.get("detected", False)
    }


# ─── Revenue Statistics Endpoints ───────────────────────────────────────────
@app.get("/api/revenue/stats", tags=["Revenue"])
async def get_revenue_stats():
    """Thống kê tổng doanh thu"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Lấy thời gian ICT (Naive)
                vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
                vn_today = vn_now.date()

                # Doanh thu hôm nay
                cur.execute("SELECT COALESCE(SUM(so_tien), 0)::BIGINT as total FROM doanh_thu WHERE DATE(ngay_thanh_toan) = %s", (vn_today,))
                today = cur.fetchone()['total']
                
                # Doanh thu tháng này
                cur.execute("SELECT COALESCE(SUM(so_tien), 0)::BIGINT as total FROM doanh_thu WHERE date_trunc('month', ngay_thanh_toan) = date_trunc('month', %s::timestamp)", (vn_now,))
                month = cur.fetchone()['total']
                
                # Số lượt khách thăm (số biển số xe lạ đi vào cổng 1 hôm nay)
                cur.execute("""
                    SELECT COUNT(DISTINCT bien_so_xe) as count 
                    FROM lichsuravao 
                    WHERE trang_thai = 'Vao' 
                    AND bien_so_xe NOT IN (SELECT bien_so_xe FROM cudan) 
                    AND DATE(thoi_gian) = %s
                """, (vn_today,))
                visitors_today = cur.fetchone()['count']

                return {
                    "today": today,
                    "month": month,
                    "visitors_today": visitors_today
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/revenue/history", tags=["Revenue"])
async def get_revenue_history(limit: int = 20):
    """Lịch sử giao dịch gần nhất"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.id, r.bien_so_xe, r.so_tien, r.ngay_thanh_toan, r.loai_phi, c.ten_chu_xe
                    FROM doanh_thu r
                    LEFT JOIN cudan c ON r.resident_id = c.id
                    ORDER BY r.ngay_thanh_toan DESC
                    LIMIT %s
                """, (limit,))
                return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/revenue/chart", tags=["Revenue"])
async def get_revenue_chart():
    """Dữ liệu biểu đồ doanh thu 7 ngày gần nhất"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                vn_today = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None).date()
                cur.execute("""
                    SELECT date(d) as day, COALESCE(SUM(so_tien), 0) as total
                    FROM generate_series(%s - INTERVAL '6 days', %s, '1 day'::interval) d
                    LEFT JOIN doanh_thu ON date(ngay_thanh_toan) = date(d)
                    GROUP BY date(d)
                    ORDER BY date(d)
                """, (vn_today, vn_today))
                rows = cur.fetchall()
                # Chuyển đổi date object sang string để JSON serialize được
                data = [{"day": r['day'].strftime('%d/%m'), "total": int(r['total'])} for r in rows]
                return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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
class ConfigSystem(BaseModel):
    gate1_ip: str = "192.168.0.102"
    gate2_ip: str = "192.168.0.102"
    com_port: str = "COM3"

@app.post("/api/config/system", tags=["Config"])
async def set_config(body: ConfigSystem):
    """Cập nhật toàn bộ cấu hình hệ thống từ giao diện (gate1_ip, gate2_ip, com_port)"""
    state.gates[1].ip = body.gate1_ip
    state.gates[2].ip = body.gate2_ip
    state.com_port = body.com_port
    save_config()  # Lưu xuống file config.json
    print(f"[CONFIG] Đã cập nhật: Gate1={body.gate1_ip}, Gate2={body.gate2_ip}, COM={body.com_port}")
    return {"success": True, "message": "Đã lưu cấu hình hệ thống"}


class ConfigSource(BaseModel):
    source: str # "esp32" or "webcam"

@app.post("/api/config/camera_source", tags=["Config"])
async def set_camera_source(body: ConfigSource):
    """Cập nhật nguồn Camera (ESP32 hoặc Webcam)"""
    if body.source not in ["esp32", "webcam"]:
        raise HTTPException(status_code=400, detail="Nguồn camera không hợp lệ")
    
    state.camera_source = body.source
    print(f"[CONFIG] Đã cập nhật nguồn camera thành: {state.camera_source}")
    return {"success": True, "message": f"Đã chuyển sang: {state.camera_source}"}


# ─── Giao tiếp Phần cứng (ESP8266) ───────────────────────────────────────────
class HardwareStatus(BaseModel):
    sensors: List[int] # [S1, S2, S3, S4, S5] (0: Trống, 1: Có xe)
    gate_trigger: int   # 0: Không, 1: Gate1, 2: Gate2

@app.post("/api/hardware/status", tags=["Hardware"])
async def update_hardware_status(body: HardwareStatus):
    """Cập nhật trạng thái cảm biến và xử lý trigger mở cổng"""
    state.sensor_states = body.sensors
    
    response = {"status": "ok", "open_gate": 0}

    # Kiểm tra hàng đợi lệnh mở cổng từ visitor/pay
    if state.pending_open_gates:
        response["open_gate"] = state.pending_open_gates.pop(0)

    # 1. Phát sóng trạng thái cảm biến tới Frontend ngay lập tức
    await broadcast_detection({
        "type": "hardware_update",
        "sensors": body.sensors,
        "timestamp": time.strftime("%H:%M:%S")
    })

    # 2. Xử lý trigger nhận diện biển số (Mở cổng tự động)
    if body.gate_trigger > 0:
        g_id = body.gate_trigger
        gate = state.gates.get(g_id)
        if gate and gate.latest_frame is not None:
            print(f"[HARDWARE] Nhận Trigger từ Cổng {g_id}. Đang quét biển số...")
            
            # Sử dụng AI worker logic thu gọn để xử lý nhanh
            res = process_frame_core(gate.latest_frame, demo_mode=False)
            
            if res.get("is_resident"):
                print(f"  ✅ Khớp cư dân: {res['plate']}. Gửi lệnh mở cổng!")
                response["open_gate"] = g_id
                
                # Ghi lịch sử kèm Gate ID
                insert_history(res['plate'], res['trang_thai'], res['plate_crop_base64'], gate_id=g_id)
                
                # Gửi thông tin nhận diện tới Dashboard
                await broadcast_detection({
                    **res, 
                    "gate_id": g_id, 
                    "gate_name": "Làn Vào" if g_id == 1 else "Làn Ra",
                    "image": f"data:image/jpeg;base64,{res['plate_crop_base64']}"
                })
            else:
                print(f"  ❌ Từ chối: {res.get('plate') or 'Không nhận diện được'}")
                if res.get("plate"):
                    insert_history(res['plate'], "Tu choi", res['plate_crop_base64'], gate_id=g_id)

    # 3. Cập nhật trạng thái ô đỗ vào DB để lưu trữ lâu dài
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Lấy giờ Việt Nam (ICT) Naive
                vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
                # Cấu trúc Sensors từ ESP gửi lên: [S_Vao, S_Ra, Slot1, Slot2, Slot3]
                # Cảm biến 3, 4, 5 (index 2, 3, 4) tương ứng ô đỗ 1, 2, 3
                for i in range(2, 5): 
                    cur.execute("UPDATE parking_slots SET status=%s, updated_at=%s WHERE slot_id=%s", 
                                (bool(body.sensors[i]), vn_now, i-1))
                conn.commit()
    except Exception as e:
        print(f"[DB] Cập nhật ô đỗ lỗi: {e}")

    return response

@app.post("/api/hardware/open_manual/{gate_id}", tags=["Hardware"])
async def open_manual(gate_id: int):
    """Mở cổng thủ công từ Dashboard (Có quét biển số)"""
    if gate_id not in [1, 2]:
        raise HTTPException(status_code=400, detail="Gate ID không hợp lệ")
    print(f"[LOG] Bảo vệ nhấn nút mở cổng {gate_id} thủ công")

    gate = state.gates.get(gate_id)
    trang_thai = "Vao" if gate_id == 1 else "Ra"
    
    # 1. Thử quét biển số ngay lúc bấm nút để lưu lịch sử
    if gate and gate.latest_frame is not None:
        frame = gate.latest_frame.copy()
        res = process_frame_core(frame)
        plate = res.get("plate") or "[THỦ CÔNG]"
        img_base64 = res.get("plate_crop_base64") or ""
        
        insert_history(plate, trang_thai, img_base64, gate_id=gate_id)
        
        # Đồng bộ Dashboard
        if state.main_loop and state.main_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_detection({
                **res, 
                "gate_id": gate_id,
                "gate_name": "Làn Vào" if gate_id == 1 else "Làn Ra",
                "image": f"data:image/jpeg;base64,{img_base64}" if img_base64 else None
            }), state.main_loop)
            
    # 2. Phát lệnh mở mạch phần cứng
    open_gate_http(gate_id)
    return {"success": True, "message": f"Đã quét biển số và mở cổng {gate_id}"}


# ─── Visitor Management ──────────────────────────────────────────────────────
@app.get("/api/visitor/calculate_fee/{plate}", tags=["Visitors"])
async def calculate_visitor_fee(plate: str):
    """Tính toán thời gian đỗ và số tiền cho xe vãng lai"""
    entry_time = get_visitor_last_entry(plate)
    if not entry_time:
        return {"plate": plate, "duration_minutes": 0, "fee": 0, "entry_time": None}
    
    # Sử dụng giờ Việt Nam (Naive)
    vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
    
    # Nếu entry_time chưa có timezone (naïve), giả định nó là ICT (+7)
    if entry_time.tzinfo is None:
        # Giả định thời gian trong DB đã được lưu ở dạng ICT Naive
        pass
    else:
        # Nếu là aware (cũ), chuyển về naive ICT
        entry_time = entry_time.astimezone(timezone(timedelta(hours=7))).replace(tzinfo=None)
        
    duration = vn_now - entry_time
    duration_minutes = int(duration.total_seconds() / 60)
    
    # Chuyển sang thu phí lượt: 20k/lượt cố định
    fee = VISITOR_FLAT_FEE
        
    return {
        "plate": plate,
        "entry_time": entry_time.strftime("%Y-%m-%d %H:%M:%S"),
        "now": vn_now.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_minutes": duration_minutes,
        "hours": math.ceil(duration_minutes / 60) if duration_minutes > 0 else 0,
        "fee": fee
    }

class VisitorPayRequest(BaseModel):
    bien_so_xe: str
    gate_id: int = 1

@app.post("/api/visitor/pay", tags=["Visitors"])
async def visitor_pay(body: VisitorPayRequest):
    """Thu phí khách vãng lai và mở cổng (Hỗ trợ thu phí theo giờ tại cổng ra)"""
    plate = normalize_plate(body.bien_so_xe)
    if not plate:
        raise HTTPException(status_code=400, detail="Biển số không hợp lệ")
    try:
        # Tính toán phí thực tế
        fee_info = await calculate_visitor_fee(plate)
        fee = fee_info['fee']
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                vn_now = datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
                # Ghi doanh thu
                cur.execute(
                    "INSERT INTO doanh_thu (resident_id, bien_so_xe, so_tien, loai_phi, ngay_thanh_toan) VALUES (NULL, %s, %s, 'VISITOR', %s)",
                    (plate, fee, vn_now)
                )
                # Ghi lịch sử lượt RA (Vì thu tiền lúc ra)
                cur.execute(
                    "INSERT INTO lichsuravao (bien_so_xe, thoi_gian, trang_thai, anh_bien_so) VALUES (%s, %s, 'Ra', '')",
                    (plate, vn_now)
                )
                conn.commit()

        # Đưa lệnh mở cổng vào hàng đợi
        # state.pending_open_gates.append(body.gate_id)
        open_gate_http(body.gate_id) # Gửi trực tiếp

        # Broadcast để cập nhật
        await broadcast_detection({
            "type": "visitor_paid",
            "gate_id": body.gate_id,
            "plate": plate,
            "so_tien": fee,
            "trang_thai": "Ra",
            "processed": True,
            "visitor_alert": False,
            "timestamp": time.strftime("%H:%M:%S"),
        })
        print(f"[VISITOR] Thu phí {fee:,}đ từ xe {plate}. Mở cổng {body.gate_id}.")
        return {"success": True, "so_tien": fee, "bien_so_xe": plate}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/revenue/by_type", tags=["Revenue"])
async def get_revenue_by_type():
    """Tỷ trọng doanh thu theo loại phí (Pie Chart)"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT loai_phi, SUM(so_tien) as total, COUNT(*) as count
                    FROM doanh_thu
                    GROUP BY loai_phi
                """)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FeeConfig(BaseModel):
    visitor_fee: int

@app.get("/api/config/fees", tags=["Config"])
async def get_fees():
    """Lấy cấu hình phí gửi xe"""
    return {"visitor_fee": VISITOR_FLAT_FEE, "monthly_fee": MONTHLY_FEE}

@app.post("/api/config/fees", tags=["Config"])
async def set_fees(body: FeeConfig):
    """Cập nhật phí khách vãng lai (cố định)"""
    global VISITOR_FLAT_FEE
    VISITOR_FLAT_FEE = body.visitor_fee
    print(f"[CONFIG] Phí khách cập nhật: {VISITOR_FLAT_FEE:,}đ/lượt")
    return {"success": True, "visitor_fee": VISITOR_FLAT_FEE}


class ConfigRequest(BaseModel):
    gate1_ip: str
    gate2_ip: str
    esp8266_ip: str

@app.post("/api/config/system", tags=["Config"])
async def update_system_config(body: ConfigRequest):
    """Cập nhật cấu hình hệ thống: IP Camera và IP Hardware (ESP8266)"""
    state.gates[1].ip = body.gate1_ip
    state.gates[2].ip = body.gate2_ip
    state.esp8266_ip = body.esp8266_ip
    save_config()
    return {"success": True, "message": "Đã lưu cấu hình hệ thống"}


# 5. Kiểm tra và nạp cư dân từ Git Sync (nếu có)
import_residents_from_json()

# ─── Chạy server ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
