"""
services/alpr_service.py — AI Pipeline Service v4.0
=====================================================
Đóng gói toàn bộ luồng nhận diện biển số:
  1. capture_and_vote_frames: Multi-frame voting (n=7, min_votes=4)
  2. capture_best_frame     : Capture đơn (snapshot → MJPEG fallback)
  3. run_detection_pipeline : YOLOv8 → Deskew → CNN → EasyOCR fallback → Validate
  4. build_detection_result : Tạo DetectionResult chuẩn

Tính năng mới v4.0:
  - Multi-frame voting: chụp 7 frame, cần ≥4 đồng thuận
  - Blur filter: bỏ qua frame có Laplacian < 100.0
  - Deskew: Perspective Transform trước CNN
  - Post-processing: Substitution Map + Regex validation

Optimized cho RTX 3060 với CUDA FP16.
"""

import difflib
import logging
import time
from collections import Counter
from typing import Optional, Tuple

import base64
import cv2
import numpy as np
import requests

from models.schemas import DetectionResult

logger = logging.getLogger("alpr_service")

# ─── Hằng số ──────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.45   # YOLO detection confidence
COOLDOWN_SECONDS     = 5
FUZZY_THRESHOLD      = 0.85   # Tăng từ 0.82 lên 0.85 (v4.0)

# Multi-frame voting config (v4.0)
VOTE_N_FRAMES    = 7    # Tổng số frame chụp
VOTE_MIN_VOTES   = 4    # Tối thiểu cần để thông qua
VOTE_INTERVAL_MS = 150  # Khoảng cách giữa các frame (ms)

# Blur detection config (v4.0)
BLUR_THRESHOLD = 100.0  # Laplacian variance ngưỡng (cân bằng cho VGA)


# ─── Frame Capture ────────────────────────────────────────────────────────────

def capture_best_frame(camera_source: str, num_frames: int = 3) -> Optional[np.ndarray]:
    """
    Chụp frame sắc nét nhất từ nguồn camera (IP hoặc Local index).
    Nếu camera_source là số (VD: '0') → dùng camera laptop.
    Nếu camera_source là IP (VD: '192.168...') → dùng ESP32-CAM.
    """
    # Trường hợp 1: Camera Local (Laptop Cam)
    if camera_source.isdigit():
        idx = int(camera_source)
        try:
            cap = cv2.VideoCapture(idx)
            if not cap.isOpened():
                logger.error(f"[CAM] ❌ Không thể mở camera local index {idx}")
                return None
            
            # Chụp vài frame để camera tự cân bằng ánh sáng
            frame = None
            for _ in range(5):
                ret, frame = cap.read()
            cap.release()
            
            if frame is not None:
                logger.info(f"[CAM] ✅ Đã lấy frame từ camera local {idx}")
                return frame
        except Exception as e:
            logger.error(f"[CAM] Local cam failed: {e}")
            return None

    # Trường hợp 2: ESP32-CAM (IP)
    camera_ip = camera_source
    # Phương án 1: HTTP Snapshot (nhanh, ổn định)
    try:
        resp = requests.get(f"http://{camera_ip}/capture", timeout=3)
        if resp.status_code == 200:
            arr = np.frombuffer(resp.content, np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is not None:
                logger.info(f"[CAM] ✅ Snapshot OK từ {camera_ip}")
                return frame
    except Exception as e:
        logger.warning(f"[CAM] Snapshot failed: {e}")

    # Phương án 2: MJPEG Stream - lấy frame sắc nhất (Laplacian sharpness)
    best_frame, best_sharpness = None, -1.0
    try:
        cap = cv2.VideoCapture(f"http://{camera_ip}:81/stream")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        collected = 0
        for _ in range(num_frames * 3):
            if collected >= num_frames:
                break
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            if sharpness > best_sharpness:
                best_sharpness = sharpness
                best_frame = frame.copy()
            collected += 1
            time.sleep(0.03)
        cap.release()
        if best_frame is not None:
            logger.info(f"[CAM] ✅ Stream frame OK (sharpness={best_sharpness:.1f})")
    except Exception as e:
        logger.error(f"[CAM] Stream failed: {e}")

    return best_frame


# ─── Multi-frame Voting (v4.0) ────────────────────────────────────────────────

def capture_and_vote_frames(
    camera_ip: str,
    yolo_model,
    char_model,
    easyocr_reader,
    n_frames: int = VOTE_N_FRAMES,
    min_votes: int = VOTE_MIN_VOTES,
    frame_interval_ms: int = VOTE_INTERVAL_MS,
) -> Tuple[Optional[str], Optional[list], float, Optional[str]]:
    """
    Multi-frame Voting Strategy — v4.0 Core Feature.

    Quy trình:
      1. Chụp n_frames = 7 frame, mỗi frame cách nhau frame_interval_ms = 150ms
      2. Mỗi frame: kiểm tra độ nét (Laplacian >= 100.0), bỏ qua nếu mờ
      3. Chạy AI pipeline đầy đủ trên từng frame hợp lệ
      4. Đếm vote: biển số nào xuất hiện >= min_votes=4 lần → trả về kết quả

    Args:
        camera_ip       : IP của ESP32-CAM
        yolo_model      : Model YOLO đã load
        char_model      : Model CNN char đã load
        easyocr_reader  : EasyOCR reader đã init
        n_frames        : Tổng số frame cần chụp (default 7)
        min_votes       : Số vote tối thiểu để thông qua (default 4)
        frame_interval_ms: Khoảng cách giữa các frame (ms, default 150)

    Returns:
        (plate_text, bbox, confidence, plate_img_b64)
        Trả về (None, None, 0.0, None) nếu không đủ votes.
    """
    from core.preprocessor import check_image_quality

    logger.info(
        f"[VOTE] Bắt đầu multi-frame voting: "
        f"n={n_frames}, min_votes={min_votes}, interval={frame_interval_ms}ms"
    )

    # List lưu kết quả nhận diện hợp lệ: [(plate_text, bbox, confidence, img_b64)]
    results_pool = []
    skipped_blur = 0
    skipped_no_plate = 0

    for i in range(n_frames):
        frame_num = i + 1
        t_frame_start = time.time()

        # ── Capture frame ─────────────────────────────────────────────────────
        frame = capture_best_frame(camera_ip, num_frames=1)
        if frame is None:
            logger.warning(f"[VOTE] Frame {frame_num}/{n_frames}: capture thất bại")
            if i < n_frames - 1:
                time.sleep(frame_interval_ms / 1000.0)
            continue

        # ── Kiểm tra độ nét ───────────────────────────────────────────────────
        is_sharp, sharpness_score = check_image_quality(frame, threshold=BLUR_THRESHOLD)
        if not is_sharp:
            logger.debug(
                f"[VOTE] Frame {frame_num}/{n_frames}: BLUR "
                f"(score={sharpness_score:.1f}) — bỏ qua"
            )
            skipped_blur += 1
            if i < n_frames - 1:
                time.sleep(frame_interval_ms / 1000.0)
            continue

        # ── Chạy AI pipeline ──────────────────────────────────────────────────
        plate_text, bbox, confidence, plate_img_b64 = run_detection_pipeline(
            frame, yolo_model, char_model, easyocr_reader
        )

        elapsed_ms = (time.time() - t_frame_start) * 1000

        if plate_text and len(plate_text) >= 4:
            results_pool.append((plate_text, bbox, confidence, plate_img_b64))
            logger.info(
                f"[VOTE] Frame {frame_num}/{n_frames}: ✅ '{plate_text}' "
                f"(conf={confidence:.2f}, {elapsed_ms:.0f}ms)"
            )
        else:
            skipped_no_plate += 1
            logger.debug(f"[VOTE] Frame {frame_num}/{n_frames}: không phát hiện biển số")

        # Chờ trước frame tiếp theo (không chờ sau frame cuối)
        if i < n_frames - 1:
            time.sleep(frame_interval_ms / 1000.0)

    # ── Tổng hợp kết quả ──────────────────────────────────────────────────────
    logger.info(
        f"[VOTE] Tổng kết: {len(results_pool)}/{n_frames} frame có biển số "
        f"(blur={skipped_blur}, no_plate={skipped_no_plate})"
    )

    if not results_pool:
        logger.info("[VOTE] Không có frame hợp lệ nào — DENY")
        return None, None, 0.0, None

    # Đếm vote theo chuỗi biển số (đã qua validate trong pipeline)
    plate_counter = Counter(r[0] for r in results_pool)
    most_common_plate, vote_count = plate_counter.most_common(1)[0]

    logger.info(
        f"[VOTE] Kết quả bỏ phiếu: '{most_common_plate}' "
        f"({vote_count}/{n_frames} votes, cần ≥{min_votes})"
    )

    if vote_count < min_votes:
        logger.info(
            f"[VOTE] ❌ Không đủ votes ({vote_count} < {min_votes}) — DENY"
        )
        return None, None, 0.0, None

    # Lấy kết quả có confidence cao nhất trong nhóm vote thắng
    winning_results = [r for r in results_pool if r[0] == most_common_plate]
    best = max(winning_results, key=lambda r: r[2])  # sort by confidence

    logger.info(
        f"[VOTE] ✅ Thông qua: '{most_common_plate}' "
        f"({vote_count} votes, best_conf={best[2]:.2f})"
    )
    return best


# ─── AI Detection Pipeline ────────────────────────────────────────────────────

def run_detection_pipeline(
    frame: np.ndarray,
    yolo_model,
    char_model,
    easyocr_reader,
) -> Tuple[Optional[str], Optional[list], float, Optional[str]]:
    """
    Pipeline AI đầy đủ trên một frame (v4.0 — tích hợp Deskew + Validate).

    Luồng:
      1. YOLOv8 detect vùng biển số
      2. deskew_plate: căn chỉnh góc nghiêng
      3. CNN 56-layer nhận diện ký tự (ưu tiên)
      4. EasyOCR fallback nếu CNN cho kết quả yếu
      5. validate_and_fix_plate: Substitution Map + Regex

    Returns:
        (plate_text, bbox, confidence, plate_image_b64)
    """
    from core.preprocessor import deskew_plate
    from core.plate_validator import validate_and_fix_plate

    if yolo_model is None:
        raise RuntimeError("YOLO model chưa được nạp")

    t0 = time.time()

    # ── Bước 1: YOLO detect biển số ──────────────────────────────────────────
    results = yolo_model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

    best_conf, best_box = 0.0, None
    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf > best_conf:
                best_conf = conf
                best_box = box.xyxy[0].cpu().numpy().astype(int)

    if best_box is None:
        logger.debug("[AI] Không phát hiện biển số")
        return None, None, 0.0, None

    x1, y1, x2, y2 = best_box
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return None, None, 0.0, None

    plate_crop = frame[y1:y2, x1:x2]

    # ── Bước 2: Deskew — căn chỉnh góc nghiêng (v4.0) ───────────────────────
    plate_crop = deskew_plate(plate_crop)

    # Encode crop thành base64 (dùng ảnh đã deskew)
    _, buf = cv2.imencode(".jpg", plate_crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
    plate_img_b64 = base64.b64encode(buf).decode("utf-8")

    logger.info(
        f"[AI] YOLO detect: conf={best_conf:.2f}, box=({x1},{y1},{x2},{y2})"
    )

    # ── Bước 3: CNN 56-layer nhận diện ký tự ─────────────────────────────────
    raw_plate = ""
    if char_model is not None:
        try:
            from core.segmentation import segment_characters
            from core.char_recognizer import predict_plate_text
            char_imgs = segment_characters(plate_crop, target_size=32)
            if char_imgs:
                raw_plate = predict_plate_text(char_model, char_imgs, conf_threshold=0.25)
                logger.info(f"[AI] CNN Char: '{raw_plate}' ({len(char_imgs)} chars)")
        except Exception as e:
            logger.warning(f"[AI] CNN error: {e}")

    # ── Bước 4: Fallback EasyOCR ─────────────────────────────────────────────
    if (not raw_plate or len(raw_plate) < 4) and easyocr_reader is not None:
        try:
            from core.ocr import read_license_plate_2_lines
            ocr_result = read_license_plate_2_lines(easyocr_reader, frame, (x1, y1, x2, y2))
            if ocr_result.get("confidence", 0) > 0.25:
                raw_plate = (
                    ocr_result.get("line1", "") + ocr_result.get("line2", "")
                ).strip()
                logger.info(f"[AI] EasyOCR fallback: '{raw_plate}'")
        except Exception as e:
            logger.warning(f"[AI] EasyOCR error: {e}")

    # ── Bước 5: Post-process — Substitution Map + Regex validation (v4.0) ────
    plate_text = None
    if raw_plate and len(raw_plate) >= 4:
        fixed_plate, is_valid, confidence_penalty = validate_and_fix_plate(raw_plate)
        if fixed_plate and len(fixed_plate) >= 4:
            plate_text = fixed_plate
            # Điều chỉnh confidence theo penalty
            best_conf = max(0.0, best_conf - confidence_penalty)
            logger.info(
                f"[AI] Post-process: '{raw_plate}' → '{plate_text}' "
                f"(valid={is_valid}, penalty={confidence_penalty:.1f})"
            )
        else:
            logger.debug(f"[AI] Post-process từ chối: '{raw_plate}'")

    elapsed_ms = (time.time() - t0) * 1000
    logger.info(f"[AI] Pipeline complete in {elapsed_ms:.0f}ms")

    bbox = [int(x1), int(y1), int(x2), int(y2)]
    return plate_text or None, bbox, best_conf, plate_img_b64


# ─── Normalize Plate ──────────────────────────────────────────────────────────

def normalize_plate(raw: str) -> str:
    """Chuẩn hóa chuỗi biển số: in hoa, bỏ khoảng trắng và ký tự đặc biệt."""
    s = (raw or "").strip().upper()
    for ch in [" ", ".", "-", "_"]:
        s = s.replace(ch, "")
    return s


# ─── Build Result ─────────────────────────────────────────────────────────────

def build_detection_result(
    plate_text: str,
    bbox: list,
    confidence: float,
    plate_img_b64: str,
    resident: Optional[dict],
    matched_plate: str,
    trang_thai: str,
    is_fuzzy: bool,
    barrier_opened: bool,
    processing_ms: float,
) -> DetectionResult:
    """Tạo DetectionResult chuẩn để trả về cho Frontend và ESP8266."""
    if resident:
        return DetectionResult(
            detected=True,
            processed=True,
            plate=plate_text,
            matched_plate=matched_plate,
            confidence=confidence,
            bbox=bbox,
            owner=resident.get("ten_chu_xe"),
            can_ho=resident.get("so_can_ho", ""),
            trang_thai=trang_thai,
            is_resident=True,
            is_fuzzy=is_fuzzy,
            barrier_opened=barrier_opened,
            plate_image=f"data:image/jpeg;base64,{plate_img_b64}",
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            processing_ms=round(processing_ms, 1),
        )
    else:
        return DetectionResult(
            detected=True,
            processed=True,
            plate=plate_text,
            matched_plate=None,
            confidence=confidence,
            bbox=bbox,
            owner="Xe không xác định",
            trang_thai="Tu choi",
            is_resident=False,
            barrier_opened=False,
            plate_image=f"data:image/jpeg;base64,{plate_img_b64}",
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            processing_ms=round(processing_ms, 1),
        )
