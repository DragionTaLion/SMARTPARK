"""
Bước 3: Thuật toán cắt ký tự (Character Segmentation) bằng OpenCV
Pipeline:
  1. Tiền xử lý vùng ảnh biển số (Grayscale + CLAHE + Threshold)
  2. Tìm contours từng ký tự đơn lẻ (cv2.findContours)
  3. Lọc nhiễu dựa trên diện tích và tỉ lệ chiều cao/chiều rộng
  4. Xử lý biển số 2 dòng (phân loại theo tọa độ Y)
  5. Sắp xếp ký tự từ trái sang phải (theo tọa độ X)
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional


# ------------------------------------------------------------------
# Cấu hình lọc contour
# ------------------------------------------------------------------
MIN_CHAR_HEIGHT_RATIO = 0.25   # Chiều cao tối thiểu so với chiều cao biển (25%)
MAX_CHAR_HEIGHT_RATIO = 0.95   # Chiều cao tối đa so với chiều cao biển (95%)
MIN_CHAR_ASPECT_RATIO = 0.1    # Tỉ lệ w/h tối thiểu
MAX_CHAR_ASPECT_RATIO = 1.5    # Tỉ lệ w/h tối đa
MIN_CHAR_AREA_RATIO = 0.003    # Diện tích tối thiểu so với diện tích biển


def preprocess_plate(plate_img: np.ndarray) -> np.ndarray:
    """
    Tiền xử lý vùng biển số:
    1. Grayscale
    2. CLAHE: tăng độ tương phản
    3. Gaussian Blur: khử nhiễu nhẹ
    4. Otsu Threshold: nhị phân hóa

    Returns:
        Ảnh nhị phân (binary) đã được xử lý
    """
    if plate_img is None or plate_img.size == 0:
        return np.zeros((32, 64), dtype=np.uint8)

    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY) if len(plate_img.shape) == 3 else plate_img

    # Phóng to ảnh nếu quá nhỏ (tăng độ chính xác segmentation)
    h, w = gray.shape
    if h < 2 or w < 2:
        return np.zeros((32, 64), dtype=np.uint8)
    if h < 40:
        scale = 40 / h
        new_w = max(1, int(w * scale))
        gray = cv2.resize(gray, (new_w, 40), interpolation=cv2.INTER_LINEAR)



    # Tăng tương phản bằng CLAHE
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)

    # Blur nhẹ để giảm nhiễu pixel
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    # Nhị phân hóa bằng Otsu
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morphological closing: lấp lỗ hổng nhỏ bên trong ký tự
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return binary


def find_char_contours(
    binary_img: np.ndarray,
) -> List[Tuple[int, int, int, int]]:
    """
    Tìm và lọc các contour ứng với ký tự biển số.

    Returns:
        Danh sách bounding box (x, y, w, h) đã được lọc nhiễu
    """
    h_plate, w_plate = binary_img.shape

    contours, _ = cv2.findContours(
        binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    char_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)

        # --- Lọc theo tỷ lệ chiều cao ---
        h_ratio = h / h_plate
        if not (MIN_CHAR_HEIGHT_RATIO <= h_ratio <= MAX_CHAR_HEIGHT_RATIO):
            continue

        # --- Lọc theo tỉ lệ chiều rộng/chiều cao ---
        aspect = w / h if h > 0 else 0
        if not (MIN_CHAR_ASPECT_RATIO <= aspect <= MAX_CHAR_ASPECT_RATIO):
            continue

        # --- Lọc theo diện tích ---
        area_ratio = (w * h) / (w_plate * h_plate)
        if area_ratio < MIN_CHAR_AREA_RATIO:
            continue

        char_boxes.append((x, y, w, h))

    return char_boxes


def detect_plate_rows(plate_img: np.ndarray) -> int:
    """
    Tự động nhận diện biển số 1 dòng hay 2 dòng dựa trên tỷ lệ W/H của ảnh.
    - Biển ô tô (1 dòng): tỷ lệ W/H thường > 3.0
    - Biển xe máy (2 dòng): tỷ lệ W/H thường <= 3.0
    Returns: 1 hoặc 2
    """
    if plate_img is None or plate_img.size == 0:
        return 1
    h, w = plate_img.shape[:2]
    if h == 0:
        return 1
    ratio = w / h
    return 2 if ratio <= 3.0 else 1


def split_two_rows(
    boxes: List[Tuple[int, int, int, int]]
) -> Tuple[List, List]:
    """
    Phân chia danh sách bounding box theo 2 dòng dựa trên tọa độ Y.
    Dùng K-Means 2 cụm trên toa dộ Y tâm để chia dòng chính xác hơn.
    """
    if not boxes:
        return [], []

    # Tính Y tâm của mỗi box
    y_centers = np.array([y + h / 2 for (x, y, w, h) in boxes])

    if len(y_centers) < 2:
        return list(boxes), []

    # K-Means 2 cụm trên tọa độ Y
    try:
        from sklearn.cluster import KMeans
        km = KMeans(n_clusters=2, n_init=10, random_state=0)
        labels = km.fit_predict(y_centers.reshape(-1, 1))
        center0 = km.cluster_centers_[0][0]
        center1 = km.cluster_centers_[1][0]
        # Cụm có tâm nhỏ hơn = dòng trên (top)
        top_label = 0 if center0 < center1 else 1
        top_row = [b for b, lbl in zip(boxes, labels) if lbl == top_label]
        bot_row = [b for b, lbl in zip(boxes, labels) if lbl != top_label]
    except Exception:
        # Fallback: dùng median nếu sklearn không có
        median_y = float(np.median(y_centers))
        # Kiểm tra có thực sự 2 dòng rõ ràng không:
        # nếu tất cả y tâm dồn cụm (std < 10% chiều cao biển), coi là 1 dòng
        y_std = float(np.std(y_centers))
        y_range = float(np.max(y_centers) - np.min(y_centers))
        if y_range < 15:  # Không phân tán đủ, coi là 1 dòng
            return list(boxes), []
        top_row = [b for b, yc in zip(boxes, y_centers) if yc <= median_y]
        bot_row = [b for b, yc in zip(boxes, y_centers) if yc > median_y]

    return top_row, bot_row


def segment_characters(
    plate_img: np.ndarray,
    two_rows: bool = None,  # None = tự động phát hiện dựa trên tỷ lệ W/H
    target_size: int = 32,
    debug: bool = False,
) -> List[np.ndarray]:
    """
    Pipeline đầy đủ: từ ảnh biển số → danh sách ảnh ký tự đã resize.

    Args:
        plate_img  : Ảnh RGB/BGR của vùng biển số (đã crop bởi YOLO)
        two_rows   : True = 2 dòng, False = 1 dòng, None = tự phát hiện theo tỷ lệ khủng hình
        target_size: Kích thước ảnh ký tự output (NxN pixels)
        debug      : True để vẽ contour lên ảnh và hiển thị

    Returns:
        Danh sách ảnh grayscale 32x32 (mỗi phần tử là một ký tự)
    """
    # Đảm bảo ảnh màu hợp lệ
    if plate_img is None or plate_img.size == 0:
        return []

    # Tự động phát hiện loại biển nếu không chỉ định rõ
    if two_rows is None:
        two_rows = (detect_plate_rows(plate_img) == 2)

    # Phóng to ảnh biển số nếu quá nhỏ (đảm bảo contour coord khớp)
    work_img = plate_img.copy()
    h_orig, w_orig = work_img.shape[:2]
    if h_orig < 40 and h_orig > 0:
        scale = 40.0 / h_orig
        new_w = max(1, int(w_orig * scale))
        work_img = cv2.resize(work_img, (new_w, 40), interpolation=cv2.INTER_LINEAR)

    binary = preprocess_plate(work_img)
    boxes = find_char_contours(binary)

    if not boxes:
        return []

    if two_rows:
        top_row, bot_row = split_two_rows(boxes)
        # Nếu split_two_rows trả về bot_row rỗng (không đủ khoảng cách Y), coi là 1 dòng
        if not bot_row:
            ordered_boxes = sorted(boxes, key=lambda b: b[0])
        else:
            # Sắp xếp từng dòng theo trục X (trái → phải)
            top_row = sorted(top_row, key=lambda b: b[0])
            bot_row = sorted(bot_row, key=lambda b: b[0])
            ordered_boxes = top_row + bot_row
    else:
        ordered_boxes = sorted(boxes, key=lambda b: b[0])


    # --- Lấy ảnh từng ký tự từ work_img (đã scale) và resize ---
    gray = cv2.cvtColor(work_img, cv2.COLOR_BGR2GRAY) if len(work_img.shape) == 3 else work_img
    h_work, w_work = gray.shape
    char_images = []
    for (x, y, w, h) in ordered_boxes:
        # Clamp tọa độ để tránh crop vượt biên
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w_work, x + w), min(h_work, y + h)
        if x2 <= x1 or y2 <= y1:
            continue
        char_crop = gray[y1:y2, x1:x2]
        if char_crop.size == 0:
            continue
        char_resized = cv2.resize(char_crop, (target_size, target_size))
        char_images.append(char_resized)

    # --- Debug: vẽ bounding box lên ảnh gốc ---
    if debug:
        debug_img = work_img.copy()
        for (x, y, w, h) in ordered_boxes:
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow("Character Segmentation Debug", debug_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return char_images




# ------------------------------------------------------------------
# Quick test khi chạy trực tiếp
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import os
    import glob

    print("=" * 60)
    print("TEST CHARACTER SEGMENTATION")
    print("=" * 60)

    # Lấy ảnh kết quả từ thư mục test (đã được detect bởi YOLO trước đó)
    test_images = glob.glob(
        "data/datasets/vietnam_license_plate/test/images/*.jpg"
    )[:5]

    if not test_images:
        print("❌ Không tìm thấy ảnh test.")
        sys.exit(1)

    for img_path in test_images:
        img = cv2.imread(img_path)
        if img is None:
            continue

        chars = segment_characters(img, two_rows=True, target_size=32, debug=False)
        print(f"  {os.path.basename(img_path)}: {len(chars)} ký tự tìm được")

    print()
    print("✅ Test hoàn tất. Để xem debug ảnh, đặt debug=True")
