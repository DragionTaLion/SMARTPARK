"""
Bước 1: Chuẩn bị dữ liệu ký tự cho CNN
- Lọc 36 lớp cần thiết từ bộ Chars74K (Sample001–Sample036)
- Ánh xạ Sample001→'0', Sample002→'1', ..., Sample010→'9', Sample011→'A', ...
- Chia tỷ lệ 80% train / 20% val
- Resize toàn bộ ảnh về 32x32 Grayscale
- Output: data/datasets/chars_36/train/<class>/ và data/datasets/chars_36/val/<class>/
"""

import os
import shutil
import random
import cv2
import sys

# Cấu hình
SRC_DIR = "data/datasets/characters/Fnt"
DST_DIR = "data/datasets/chars_36"
IMG_SIZE = 32
TRAIN_RATIO = 0.8
SEED = 42

# Ánh xạ: Sample001 = '0', Sample002 = '1', ..., Sample010 = '9'
#                    Sample011 = 'A', ..., Sample036 = 'Z'
def get_class_label(sample_idx: int) -> str:
    """Chuyển đổi chỉ số Sample (1-based) thành ký tự biển số xe"""
    if 1 <= sample_idx <= 10:
        return str(sample_idx - 1)     # Sample001='0', ..., Sample010='9'
    elif 11 <= sample_idx <= 36:
        return chr(ord('A') + (sample_idx - 11))  # Sample011='A', ..., Sample036='Z'
    return None


def preprocess_image(img_path: str, size: int) -> 'np.ndarray':
    """Đọc ảnh, chuyển grayscale, resize về kích thước cố định"""
    import numpy as np
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    img = cv2.resize(img, (size, size))
    return img


def prepare_dataset():
    """Hàm chính: Lọc, xử lý và chia tập dữ liệu"""
    random.seed(SEED)

    print("=" * 60)
    print("CHUẨN BỊ DỮ LIỆU KÝ TỰ CHO CNN (36 LỚP)")
    print("=" * 60)
    print(f"  Nguồn    : {SRC_DIR}")
    print(f"  Đích     : {DST_DIR}")
    print(f"  Kích thước: {IMG_SIZE}x{IMG_SIZE} px (Grayscale)")
    print(f"  Chia     : {int(TRAIN_RATIO*100)}% train / {int((1-TRAIN_RATIO)*100)}% val")
    print()

    total_train = 0
    total_val = 0

    # Duyệt 36 lớp đầu tiên (Sample001 -> Sample036)
    for sample_idx in range(1, 37):
        folder_name = f"Sample{sample_idx:03d}"
        label = get_class_label(sample_idx)
        src_folder = os.path.join(SRC_DIR, folder_name)

        if not os.path.exists(src_folder):
            print(f"  ⚠️  Không tìm thấy {folder_name}, bỏ qua.")
            continue

        # Lấy danh sách ảnh
        images = [
            f for f in os.listdir(src_folder)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        random.shuffle(images)

        # Chia train/val
        n_train = int(len(images) * TRAIN_RATIO)
        train_imgs = images[:n_train]
        val_imgs = images[n_train:]

        # Tạo thư mục đích
        for split, imgs in [('train', train_imgs), ('val', val_imgs)]:
            dst_folder = os.path.join(DST_DIR, split, label)
            os.makedirs(dst_folder, exist_ok=True)

            for fname in imgs:
                src_path = os.path.join(src_folder, fname)
                img = preprocess_image(src_path, IMG_SIZE)
                if img is None:
                    continue

                # Lưu file với tên giữ nguyên
                dst_path = os.path.join(dst_folder, fname)
                cv2.imwrite(dst_path, img)

        print(f"  ✅  {folder_name} → '{label}' | train: {len(train_imgs)} | val: {len(val_imgs)}")
        total_train += len(train_imgs)
        total_val += len(val_imgs)

    print()
    print("=" * 60)
    print(f"HOÀN TẤT! Tổng: {total_train} train / {total_val} val")
    print(f"Dataset lưu tại: {DST_DIR}")
    print("=" * 60)
    print()
    print("Bước tiếp theo - Train model CNN:")
    print("  yolo classify train model=yolov8n-cls.pt \\")
    print(f"       data={DST_DIR} \\")
    print("       epochs=50 imgsz=32 device=0")


if __name__ == "__main__":
    # Đảm bảo chạy từ thư mục gốc D:\PBL5
    if not os.path.exists(SRC_DIR):
        print(f"❌ Không tìm thấy: {SRC_DIR}")
        print("   Hãy chạy script này từ thư mục gốc D:\\PBL5")
        sys.exit(1)

    prepare_dataset()
