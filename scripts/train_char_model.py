"""
Bước 2: Train model phân loại ký tự bằng YOLOv8 Classify
- Sử dụng YOLOv8n-cls (phiên bản nano, nhẹ và nhanh)
- Dataset: data/datasets/chars_36/ (36 lớp: 0-9 và A-Z)
- Tự động phát hiện GPU (RTX 3060 sẽ chạy trên device=0)
- Lưu model tại: data/models/char_model/
"""

from multiprocessing import freeze_support
from ultralytics import YOLO
import torch
import os


def main():
    # --- Kiểm tra GPU ---
    if torch.cuda.is_available():
        device = 0
        print(f"✅ GPU: {torch.cuda.get_device_name(0)} — Sử dụng GPU để tăng tốc!")
    else:
        device = 'cpu'
        print("⚠️  Không có GPU, dùng CPU (chậm hơn).")

    # --- Kiểm tra dataset ---
    DATASET_DIR = "data/datasets/chars_36"
    if not os.path.exists(DATASET_DIR):
        print(f"❌ Dataset chưa được chuẩn bị: {DATASET_DIR}")
        print("   Hãy chạy trước: py scripts/prepare_char_dataset.py")
        exit(1)

    # --- Cấu hình training ---
    MODEL_BASE = "yolov8n-cls.pt"
    OUTPUT_DIR = "data/models"
    RUN_NAME   = "char_model"

    print("\n" + "="*60)
    print("TRAINING MODEL PHÂN LOẠI KÝ TỰ BIỂN SỐ (36 LỚP)")
    print("="*60)
    print(f"  Model nền  : {MODEL_BASE}")
    print(f"  Dataset    : {DATASET_DIR}")
    print(f"  Kích thước : 32x32 px")
    print(f"  Epochs     : 50")
    print(f"  Device     : {'GPU' if device == 0 else 'CPU'}")
    print(f"  Output     : {OUTPUT_DIR}/{RUN_NAME}")
    print("="*60 + "\n")

    # --- Load và train ---
    model = YOLO(MODEL_BASE)

    results = model.train(
        data=DATASET_DIR,
        epochs=50,
        imgsz=32,
        device=device,
        project=OUTPUT_DIR,
        name=RUN_NAME,
        batch=64 if device == 0 else 16,
        patience=10,
        save=True,
        plots=True,
        exist_ok=True,
        workers=0,        # Tắt multiprocessing trên Windows
    )

    print("\n" + "="*60)
    print("TRAINING HOÀN TẤT!")
    print("="*60)
    best_model_path = f"{OUTPUT_DIR}/{RUN_NAME}/weights/best.pt"
    print(f"✅ Model tốt nhất: {best_model_path}")
    print()
    print("Bước tiếp theo - Tích hợp vào hệ thống:")
    print(f"  py main_system.py --char-model {best_model_path} --com COM3 --camera 0")


if __name__ == '__main__':
    freeze_support()
    main()
