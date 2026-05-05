"""
models/schemas.py — Pydantic Data Models
==========================================
Định nghĩa tất cả schema cho request/response của hệ thống ALPR.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ─── IoT Hardware Schemas ──────────────────────────────────────────────────────

class EntryRequest(BaseModel):
    """Schema nhận tín hiệu từ ESP8266 khi cảm biến phát hiện xe"""
    distance: Optional[float] = Field(None, description="Khoảng cách đo được (cm)")
    device_id: str = Field("esp8266_gate", description="ID thiết bị gửi tín hiệu")
    threshold: float = Field(10.0, description="Ngưỡng phát hiện (cm)")
    timestamp: Optional[str] = Field(None, description="Timestamp từ thiết bị")


class BarrierCommand(BaseModel):
    """Schema lệnh điều khiển barrier trả về cho ESP8266"""
    action: str = Field(..., description="'OPEN' hoặc 'DENY'")
    reason: str = Field("", description="Lý do quyết định")
    plate: Optional[str] = Field(None, description="Biển số đã nhận diện")
    owner: Optional[str] = Field(None, description="Tên chủ xe")


# ─── Detection Result Schemas ──────────────────────────────────────────────────

class DetectionResult(BaseModel):
    """Kết quả đầy đủ của một lần nhận diện biển số"""
    detected: bool
    processed: bool = False                   # True = đã hoàn tất pipeline AI (không phải chỉ detect)
    plate: Optional[str] = None
    matched_plate: Optional[str] = None
    confidence: Optional[float] = None
    bbox: Optional[List[int]] = None          # [x1, y1, x2, y2]
    owner: Optional[str] = None
    can_ho: Optional[str] = None
    trang_thai: Optional[str] = None          # "Vao" | "Ra" | "Tu choi"
    is_resident: bool = False
    is_fuzzy: bool = False
    barrier_opened: bool = False
    plate_image: Optional[str] = None         # base64 JPEG
    timestamp: Optional[str] = None
    processing_ms: Optional[float] = None     # Thời gian xử lý (ms)
    error: Optional[str] = None


class SystemHealth(BaseModel):
    """Trạng thái sức khỏe hệ thống"""
    status: str
    db: str
    yolo: str
    char_model: str
    ocr: str
    gpu: bool
    camera_ip: str
    esp8266_ip: str
    usb_mode: bool
    camera_connected: bool
    iot_processing: bool


# ─── API Schemas ───────────────────────────────────────────────────────────────

class ResidentCreate(BaseModel):
    bien_so_xe: str = Field(..., description="Biển số xe (sẽ được tự động in hoa)")
    ten_chu_xe: str = Field(..., description="Tên chủ xe")
    so_can_ho: str = Field("", description="Số căn hộ")


class CameraIPUpdate(BaseModel):
    ip: str = Field(..., description="IP mới của ESP32-CAM")


class ESP8266IPUpdate(BaseModel):
    ip: str = Field(..., description="IP mới của ESP8266")
