"""
core/preprocessor.py — Image Pre-processing Module
====================================================
Module tiền xử lý ảnh cho pipeline ALPR v4.0:
  1. check_image_quality: Laplacian Variance để đo độ nét frame
  2. deskew_plate: Perspective Transform để căn chỉnh biển số nghiêng

Thông số cấu hình:
  BLUR_THRESHOLD = 100.0  (Cân bằng cho camera VGA ESP32-CAM)
"""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger("core.preprocessor")

# ─── Ngưỡng cấu hình ────────────────────────────────────────────────────────
BLUR_THRESHOLD = 100.0  # Laplacian variance — 100.0 cân bằng cho VGA


# ─── Module 1A: Kiểm tra chất lượng ảnh ─────────────────────────────────────

def check_image_quality(
    frame: np.ndarray,
    threshold: float = BLUR_THRESHOLD,
) -> Tuple[bool, float]:
    """
    Đo độ nét của frame bằng Laplacian Variance.

    Laplacian operator tính đạo hàm bậc 2 của ảnh — ảnh nét có phương sai
    cao do nhiều cạnh gradient mạnh; ảnh mờ có phương sai thấp.

    Args:
        frame    : Frame BGR (hoặc grayscale) từ ESP32-CAM
        threshold: Ngưỡng tối thiểu (100.0 phù hợp VGA)

    Returns:
        (is_sharp, score):
          - is_sharp = True nếu frame đủ nét để xử lý
          - score    = giá trị Laplacian variance thực tế
    """
    if frame is None or frame.size == 0:
        logger.warning("[BLUR] Frame rỗng")
        return False, 0.0

    # Chuyển sang grayscale nếu cần
    gray = (
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if len(frame.shape) == 3
        else frame
    )

    score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_sharp = score >= threshold

    if not is_sharp:
        logger.debug(
            f"[BLUR] Frame skipped — Laplacian={score:.1f} < threshold={threshold:.1f}"
        )
    else:
        logger.debug(f"[QUALITY] Frame OK — Laplacian={score:.1f}")

    return is_sharp, score


# ─── Module 1B: Căn chỉnh biển số (Deskewing) ───────────────────────────────

def deskew_plate(plate_crop: np.ndarray) -> np.ndarray:
    """
    Căn chỉnh biển số nghiêng bằng Perspective Transform.

    Pipeline:
      1. Grayscale + Otsu threshold
      2. Tìm contour lớn nhất (toàn bộ biển số)
      3. Xấp xỉ tứ giác (approxPolyDP)
      4. warpPerspective về hình chữ nhật kích thước gốc

    Fallback: trả về ảnh gốc không thay đổi nếu:
      - Không tìm được đúng 4 điểm góc
      - Contour quá nhỏ (< 30% diện tích ảnh)
      - Xảy ra bất kỳ lỗi nào

    Args:
        plate_crop: Ảnh BGR của vùng biển số đã crop bởi YOLO

    Returns:
        Ảnh biển số đã deskew (hoặc ảnh gốc nếu thất bại)
    """
    if plate_crop is None or plate_crop.size == 0:
        return plate_crop

    h, w = plate_crop.shape[:2]

    # Ảnh quá nhỏ → không đủ thông tin để deskew
    if h < 12 or w < 24:
        return plate_crop

    try:
        # Chuyển sang grayscale
        gray = (
            cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
            if len(plate_crop.shape) == 3
            else plate_crop.copy()
        )

        # Tăng tương phản (CLAHE) trước threshold
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        gray = clahe.apply(gray)

        # Nhị phân hóa Otsu
        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # Tìm contours
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return plate_crop

        # Contour lớn nhất phải chiếm ≥ 30% diện tích ảnh
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 0.30 * h * w:
            logger.debug("[DESKEW] Contour quá nhỏ — bỏ qua")
            return plate_crop

        # Xấp xỉ tứ giác
        epsilon = 0.02 * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)

        if len(approx) != 4:
            logger.debug(f"[DESKEW] Không phải tứ giác ({len(approx)} điểm) — bỏ qua")
            return plate_crop

        # Sắp xếp 4 điểm theo thứ tự chuẩn
        pts = approx.reshape(4, 2).astype(np.float32)
        src_pts = _order_points(pts)

        # Kích thước đích bằng kích thước gốc (giữ tỷ lệ)
        dst_pts = np.array(
            [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]],
            dtype=np.float32,
        )

        # Thực hiện Perspective Transform
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(plate_crop, M, (w, h))

        logger.debug(f"[DESKEW] ✅ Transform applied (src corners: {src_pts.tolist()})")
        return warped

    except Exception as e:
        logger.warning(f"[DESKEW] Lỗi: {e} — trả về ảnh gốc")
        return plate_crop


def _order_points(pts: np.ndarray) -> np.ndarray:
    """
    Sắp xếp 4 điểm tứ giác theo thứ tự:
    [top-left, top-right, bottom-right, bottom-left]

    Thuật toán:
      - top-left     = điểm có tổng (x+y) nhỏ nhất
      - bottom-right = điểm có tổng (x+y) lớn nhất
      - top-right    = điểm có hiệu (x-y) nhỏ nhất
      - bottom-left  = điểm có hiệu (x-y) lớn nhất
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()

    rect[0] = pts[np.argmin(s)]     # top-left
    rect[2] = pts[np.argmax(s)]     # bottom-right
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left

    return rect
