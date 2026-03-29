"""
Tích hợp Database (PostgreSQL Docker) + Arduino (Serial) cho hệ thống barrier.

DB (docker-compose.yml):
- Host: localhost
- Port: 55432
- DB: nhan_dien_bien_so_xe
- User/Pass: postgres/postgres

Schema:
- cudan(bien_so_xe, ten_chu_xe, so_can_ho, ...)
- lichsuravao(bien_so_xe, thoi_gian, hinh_anh, trang_thai)
"""

import time
from typing import Optional

import psycopg2

import sys
import io

# Fix encoding cho Windows console (tránh UnicodeEncodeError khi in tiếng Việt)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

try:
    import serial  # pyserial
except Exception:  # pragma: no cover
    serial = None


DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}


def normalize_plate(raw: str) -> str:
    """Chuẩn hoá biển số: bỏ khoảng trắng, chấm, gạch; viết hoa."""
    s = (raw or "").strip().upper()
    for ch in [" ", ".", "-", "_"]:
        s = s.replace(ch, "")
    return s


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def check_plate_in_db(plate_number: str) -> Optional[str]:
    """
    Trả về ten_chu_xe nếu biển số có trong bảng cudan, ngược lại None.
    Lưu ý: cột đúng là bien_so_xe (không phải bien_so).
    """
    plate = normalize_plate(plate_number)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ten_chu_xe FROM cudan WHERE REPLACE(REPLACE(REPLACE(UPPER(bien_so_xe), ' ', ''), '-', ''), '.', '') = %s",
                (plate,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def get_all_residents() -> list:
    """
    Lấy danh sách tất cả cư dân dể phục vụ Fuzzy Matching.
    Trả về list of tuples: [(normalized_plate, original_plate, owner_name), ...]
    """
    residents = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bien_so_xe, ten_chu_xe FROM cudan")
                rows = cur.fetchall()
                for row in rows:
                    orig_plate = row[0]
                    owner = row[1]
                    norm_plate = normalize_plate(orig_plate)
                    residents.append((norm_plate, orig_plate, owner))
    except Exception as e:
        print(f"Loi khi lay danh sach cu dan: {e}")
    return residents


def insert_history(plate_number: str, trang_thai: str, hinh_anh: Optional[str] = None) -> None:
    """Ghi lịch sử vào bảng lichsuravao."""
    plate = normalize_plate(plate_number)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lichsuravao (bien_so_xe, thoi_gian, hinh_anh, trang_thai)
                VALUES (%s, %s, %s, %s)
                """,
                (plate, time.strftime("%Y-%m-%d %H:%M:%S"), hinh_anh, trang_thai),
            )
            conn.commit()


def open_barrier_via_arduino(com_port: str = "COM3", baud: int = 9600) -> bool:
    """
    Gửi lệnh 'O' để mở barrier.
    Trả về True nếu gửi được.
    """
    if serial is None:
        print("Chưa cài pyserial. Cài bằng: py -m pip install pyserial")
        return False
    try:
        with serial.Serial(com_port, baud, timeout=1) as ser:
            ser.write(b"O")
        return True
    except Exception as e:
        print(f"Không gửi được lệnh Arduino ({com_port}): {e}")
        return False


def process_vehicle_entry(plate_number: str, com_port: str = "COM3", hinh_anh: Optional[str] = None, status: str = "Vao") -> dict:
    """
    Xử lý xe vào/ra:
    - Check DB xem có trong danh sách cư dân không
    - Nếu có -> mở barrier (nếu vào) + ghi lịch sử
    - Nếu không -> ghi lịch sử 'Tu choi' (xe lạ)
    
    Args:
        plate_number: Biển số xe
        com_port: Cổng COM của Arduino
        hinh_anh: Đường dẫn ảnh (nếu có)
        status: 'Vao' hoặc 'Ra'
    
    Returns:
        dict: {
            'success': bool,
            'owner': str hoặc None,
            'message': str,
            'trang_thai': 'Vào', 'Ra', hoặc 'Tu choi'
        }
    """
    # Fix encoding cho Windows console
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        except Exception:
            pass
    
    owner = check_plate_in_db(plate_number)
    
    if owner:
        # Xe có trong danh sách cư dân
        trang_thai = "Vao" if status.lower() == "vao" else "Ra"
        
        # Chỉ mở barrier khi vào
        if status.lower() == "vao":
            ok = open_barrier_via_arduino(com_port=com_port)
            if ok:
                print(f"Da gui lenh mo barrier cho {owner}")
            else:
                print(f"Khong the gui lenh Arduino (co the Arduino chua ket noi)")
        
        # Ghi lịch sử
        insert_history(plate_number, trang_thai=trang_thai, hinh_anh=hinh_anh)
        
        message = f"Chao mung {owner}! Bien so: {plate_number} - Trang thai: {trang_thai}"
        print(message)
        
        return {
            'success': True,
            'owner': owner,
            'message': message,
            'trang_thai': trang_thai
        }
    else:
        # Xe lạ - KHÔNG mở barrier nhưng VẪN ghi log
        insert_history(plate_number, trang_thai="Tu choi", hinh_anh=hinh_anh)
        
        message = f"Canh bao: Xe la hoac chua dang ky! Bien so: {plate_number} - Da ghi log 'Tu choi'"
        print(message)
        
        return {
            'success': False,
            'owner': None,
            'message': message,
            'trang_thai': 'Tu choi'
        }


def demo_flow(plate_number: str, com_port: str = "COM3", hinh_anh: Optional[str] = None) -> None:
    """
    Demo logic xử lý xe vào (wrapper cho process_vehicle_entry).
    """
    result = process_vehicle_entry(plate_number, com_port=com_port, hinh_anh=hinh_anh, status="Vao")
    return result


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        except Exception:
            pass
    # Ví dụ chạy nhanh (đổi biển số/COM cho phù hợp)
    demo_flow("30A-12345", com_port="COM3")

