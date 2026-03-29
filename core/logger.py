"""
Module ghi log biển số nhận diện ra file CSV
Dùng thay thế Database khi chạy chế độ Demo (không có Docker)
"""

import csv
import os
from datetime import datetime


LOG_FILE = "data/detection_log.csv"
HEADERS = ["Thoi_gian", "Bien_so", "Do_chuan_xac", "Trang_thai"]


def log_plate_to_csv(plate_number: str, confidence: float, status: str = "DEMO") -> dict:
    """
    Ghi thông tin biển số nhận diện vào file CSV.

    Args:
        plate_number : Chuỗi biển số xe
        confidence   : Độ chính xác của YOLO (0-1)
        status       : Trạng thái (mặc định 'DEMO')

    Returns:
        dict kết quả với trang_thai và owner
    """
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    # Tạo header nếu file chưa tồn tại
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "Thoi_gian": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Bien_so": plate_number,
            "Do_chuan_xac": f"{confidence:.2f}",
            "Trang_thai": status,
        })

    return {
        "trang_thai": status,
        "owner": "Demo Mode",
        "message": f"Da ghi log: {plate_number}"
    }
