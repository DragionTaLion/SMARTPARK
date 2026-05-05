"""
api/v1/router.py — V1 API Router v4.0
======================================
Tất cả endpoints v1 của hệ thống ALPR.
Mount vào app tại prefix /api/v1.

Thay đổi v4.0:
  - Dùng capture_and_vote_frames thay vì capture đơn + detect đơn
  - WebSocket stage broadcasts: triggered → verifying → processing → success/denied
  - validate_and_fix_plate tích hợp vào pipeline
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse

from core.websocket import ws_manager
from models.schemas import (
    EntryRequest, BarrierCommand, ResidentCreate, CameraIPUpdate, ESP8266IPUpdate
)
from services import alpr_service, database_service

logger = logging.getLogger("api.v1")

router = APIRouter(prefix="/api/v1", tags=["V1"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _broadcast_status(stage: str, message: str, **extra):
    """
    Broadcast trạng thái xử lý tức thời lên tất cả WebSocket clients.
    Dùng trong async context (không cần threadsafe wrapper).

    Payload format:
        {
            "type": "iot_status",
            "stage": "triggered|verifying|processing|success|denied",
            "message": "...",
            "ts": float,
            ...extra fields
        }
    """
    payload = {
        "type": "iot_status",
        "stage": stage,
        "message": message,
        "ts": time.time(),
        **extra,
    }
    try:
        await ws_manager.broadcast(payload)
    except Exception as e:
        logger.warning(f"[WS] Broadcast lỗi (stage={stage}): {e}")


# ─── Entry Request (IoT Core) ─────────────────────────────────────────────────

@router.post("/entry-request", response_model=None, summary="ESP8266 Trigger")
async def entry_request(
    body: Optional[EntryRequest] = None, request: Request = None
):
    """
    🚗 [CORE ENDPOINT] ESP8266 gửi POST tới đây khi cảm biến phát hiện xe.

    Luồng xử lý v4.0:
      1. Xác nhận khoảng cách < threshold (10cm mặc định)
      2. [WS] Broadcast stage="triggered"
      3. Multi-frame Voting: chụp 7 frame, lọc blur, AI trên từng frame
      4. Cần ≥4/7 vote đồng thuận → lấy kết quả tốt nhất
      5. [WS] Broadcast stage="verifying" với biển số nhận diện được
      6. validate_and_fix_plate: Substitution Map + Regex
      7. Cooldown check 5s
      8. DB lookup (exact → fuzzy 85%)
      9. Ghi lịch sử, broadcast full DetectionResult
      10. [WS] Broadcast stage="success"/"denied"
      11. Trả về BarrierCommand {"action": "OPEN"/"DENY"} cho ESP8266
    """
    state = request.app.state.smartpark
    client_host = request.client.host if request.client else "unknown"
    device_id = body.device_id if body else "unknown"
    logger.info(f"[V1] RECEIVE entry-request from {client_host} (device={device_id})")

    # ── Bước 1: Kiểm tra ngưỡng khoảng cách ─────────────────────────────────
    if body and body.distance is not None:
        if body.distance >= body.threshold:
            logger.debug(
                f"[V1] Noise filter: distance={body.distance:.1f}cm "
                f">= threshold={body.threshold:.1f}cm — DENY"
            )
            return JSONResponse({
                "action": "DENY",
                "reason": (
                    f"Khoảng cách {body.distance:.1f}cm >= ngưỡng {body.threshold}cm"
                ),
                "triggered": False,
            })
        logger.info(
            f"[V1] IoT Trigger: {device_id} distance={body.distance:.1f}cm ✅"
        )
    else:
        logger.info("[V1] Manual trigger (no distance data)")

    # ── Kiểm tra lock — tránh xử lý 2 xe song song ──────────────────────────
    if state.iot_processing:
        return JSONResponse(
            {
                "action": "DENY",
                "reason": "Hệ thống đang xử lý xe trước, vui lòng đợi",
                "triggered": False,
            },
            status_code=429,
        )

    state.iot_processing = True
    t_start = time.time()

    try:
        # ── [WS] Stage 1: Triggered ──────────────────────────────────────────
        await _broadcast_status(
            stage="triggered",
            message="🚗 Xe phát hiện — Đang khởi động camera...",
            device_id=device_id,
        )

        loop = asyncio.get_event_loop()

        # ── Bước 2: Multi-frame Voting (v4.0) ────────────────────────────────
        # Thay thế hai bước riêng biệt (capture + detect) bằng một hàm tổng hợp.
        # Chạy trong thread executor vì đây là blocking I/O + blocking GPU inference.
        plate_text, bbox, confidence, plate_img_b64 = await loop.run_in_executor(
            None,
            lambda: alpr_service.capture_and_vote_frames(
                state.camera_ip,
                state.yolo_model,
                state.char_model,
                state.easyocr_reader,
            ),
        )

        # ── [WS] Stage 2: verifying hoặc denied (camera/blur/votes thất bại) ─
        if plate_text is None:
            await _broadcast_status(
                stage="denied",
                message="❌ Không đọc được biển số (không đủ votes đa khung hình)",
            )
            logger.info("[V1] Multi-frame voting thất bại — DENY")
            return JSONResponse({
                "action": "DENY",
                "reason": "Không đọc được biển số sau 7 frame (< 4 votes đồng thuận)",
                "detected": False,
            })

        # ── [WS] Stage 3: Đang tra cứu DB ────────────────────────────────────
        await _broadcast_status(
            stage="verifying",
            message=f"🔎 Biển số: {plate_text} — Đang tra cứu...",
            plate=plate_text,
        )

        logger.info(f"[V1] Biển số nhận diện: '{plate_text}' (conf={confidence:.2f})")

        # ── Bước 3: Cooldown check ────────────────────────────────────────────
        now = time.time()
        cooldown_info = state.plate_cooldown.get(plate_text, {})
        if now - cooldown_info.get("ts", 0) < 5.0:
            await _broadcast_status(
                stage="denied",
                message=f"⏳ Cooldown — {plate_text} vừa được xử lý",
                plate=plate_text,
            )
            return JSONResponse({
                "action": "DENY",
                "reason": "Cooldown — xe này vừa được xử lý",
                "plate": plate_text,
            })
        state.plate_cooldown[plate_text] = {"ts": now}

        # ── Bước 4: DB Lookup (Exact → Fuzzy 85%) ────────────────────────────
        resident = database_service.find_resident_exact(plate_text)
        matched_plate, is_fuzzy = plate_text, False

        if not resident:
            resident, matched_plate, ratio = database_service.find_resident_fuzzy(
                plate_text
            )
            if resident:
                is_fuzzy = True
                logger.info(
                    f"[V1] Fuzzy match: '{plate_text}' → '{matched_plate}' "
                    f"({ratio:.0%})"
                )

        # Toggle Vào/Ra
        prev = state.plate_status.get(plate_text, "Ra")
        trang_thai = "Vao" if prev == "Ra" else "Ra"
        state.plate_status[plate_text] = trang_thai

        # ── Bước 5: Ghi DB + Xây dựng kết quả ───────────────────────────────
        # Lưu ý: ESP8266 là HTTP client, KHÔNG có HTTP server.
        # Barrier mở do ESP8266 tự xử lý khi nhận response action=OPEN.
        barrier_opened = False
        processing_ms = (time.time() - t_start) * 1000

        if resident:
            use_plate = matched_plate or plate_text
            database_service.insert_history(use_plate, trang_thai, plate_img_b64)
            barrier_opened = True
            logger.info(
                f"[V1] ✅ Chấp nhận ({trang_thai}): "
                f"{resident['ten_chu_xe']} — {use_plate}"
            )

            # Xây dựng full DetectionResult để broadcast
            result = alpr_service.build_detection_result(
                plate_text, bbox, confidence, plate_img_b64,
                resident, matched_plate, trang_thai, is_fuzzy,
                barrier_opened, processing_ms,
            )

            # [WS] Stage 4: Thành công — broadcast full detection result
            await ws_manager.broadcast(result.model_dump())

            # [WS] Stage 5: Status thành công (hiển thị banner trên Dashboard)
            await _broadcast_status(
                stage="success",
                message=f"✅ Thành công — {resident['ten_chu_xe']} ({trang_thai})",
                plate=plate_text,
                matched_plate=matched_plate,
                owner=resident["ten_chu_xe"],
                can_ho=resident.get("so_can_ho", ""),
                trang_thai=trang_thai,
                is_fuzzy=is_fuzzy,
                processing_ms=round(processing_ms, 1),
            )

        else:
            # Xe lạ — Silent Mode: không ghi DB, không báo Dashboard
            logger.info(f"[V1] ℹ️ Xe lạ: '{plate_text}' — Silent Mode")
            barrier_opened = False

            # [WS] Stage 4: Từ chối
            await _broadcast_status(
                stage="denied",
                message=f"❌ Từ chối — {plate_text} không trong danh sách cư dân",
                plate=plate_text,
            )

        # ── Bước 6: Trả kết quả về ESP8266 ──────────────────────────────────
        action = "OPEN" if barrier_opened else "DENY"
        response_data = {
            "action": action,
            "plate": plate_text,
            "matched_plate": matched_plate,
            "owner": resident["ten_chu_xe"] if resident else None,
            "is_resident": bool(resident),
            "trang_thai": trang_thai if resident else "Tu choi",
            "barrier_opened": barrier_opened,
            "processing_ms": round(processing_ms, 1),
        }
        logger.info(f"[V1] → Trả về ESP8266: {response_data}")
        return response_data

    except Exception as e:
        logger.exception(f"[V1] Pipeline error: {e}")
        await _broadcast_status(
            stage="denied",
            message=f"❌ Lỗi hệ thống: {str(e)[:80]}",
        )
        raise HTTPException(status_code=500, detail=f"Pipeline lỗi: {e}")

    finally:
        state.iot_processing = False
