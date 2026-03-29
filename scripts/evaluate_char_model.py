"""
Script đánh giá chi tiết model CNN (YOLOv8-cls) nhận diện ký tự biển số xe.
Thực hiện:
1. Hiển thị cấu trúc layer (summary)
2. Tính toán Confusion Matrix và vẽ biểu đồ.
3. Chạy inference thử nghiệm 1 ảnh.
4. Kiểm tra phần cứng (RTX 3060/CPU) và Latency.
5. Xuất báo cáo bảng kết quả.
"""

import os
import time
import torch
import cv2
import numpy as np
import matplotlib.pyplot as plt
from ultralytics import YOLO

# Cấu hình đường dẫn
MODEL_PATH = "data/models/char_model/weights/best.pt"
VAL_DATA_DIR = "data/datasets/chars_36/val"
IMG_SIZE = 32

def print_model_summary(model):
    print("\n" + "="*30)
    print("1. CẤU TRÚC LAYER MODEL")
    print("="*30)
    # YOLOv8 không có summary() giống Keras, ta dùng info() và print model
    model.info() 
    print("\nChi tiết các lớp chính:")
    # Hiển thị vài lớp đầu và cuối để mô phỏng summary
    for i, (name, module) in enumerate(model.model.named_modules()):
        if i < 5 or "head" in name.lower():
            print(f"Layer: {name:<20} | Type: {type(module).__name__}")
    print("="*60)

def plot_confusion_matrix(y_true, y_pred, classes):
    # Tính Confusion Matrix bằng numpy
    n_classes = len(classes)
    cm = np.zeros((n_classes, n_classes), dtype=int)
    
    # Map class name to index
    class_to_idx = {name: i for i, name in enumerate(classes)}
    
    for true, pred in zip(y_true, y_pred):
        if true in class_to_idx and pred in class_to_idx:
            cm[class_to_idx[true], class_to_idx[pred]] += 1

    plt.figure(figsize=(15, 12))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion Matrix - Character Recognition')
    plt.colorbar()
    tick_marks = np.arange(n_classes)
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    # Thêm số lượng vào từng ô
    thresh = cm.max() / 2.
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            if cm[i, j] > 0:
                plt.text(j, i, format(cm[i, j], 'd'),
                         ha="center", va="center",
                         color="white" if cm[i, j] > thresh else "black")

    plt.tight_layout()
    plt.ylabel('Thực tế (Actual)')
    plt.xlabel('Dự đoán (Predicted)')
    plt.savefig('evaluation_results/confusion_matrix.png')
    print("\n\u2705 Đã lưu Confusion Matrix tại: evaluation_results/confusion_matrix.png")
    # plt.show() # Tắt để chạy background mượt hơn

def run_inference_test(model, img_path):
    """Hàm nhận diện thử nghiệm 1 ảnh đơn lẻ"""
    start_time = time.time()
    results = model.predict(img_path, imgsz=IMG_SIZE, verbose=False)
    latency = (time.time() - start_time) * 1000 # ms
    
    if not results:
        return None, 0, latency
    
    probs = results[0].probs
    if probs is None: return None, 0, latency
    
    top1_idx = int(probs.top1)
    top1_conf = float(probs.top1conf)
    char_name = model.names[top1_idx]
    
    return char_name, top1_conf, latency

def main():
    # 0. Khởi tạo thư mục kết quả
    os.makedirs('evaluation_results', exist_ok=True)

    # 1. Load Model & Kiểm tra phần cứng
    if not os.path.exists(MODEL_PATH):
        print(f"\u274c Không tìm thấy model tại: {MODEL_PATH}")
        return

    print(f"\n[INFO] Đang tải model từ: {MODEL_PATH}")
    model = YOLO(MODEL_PATH)
    
    device_name = "CPU"
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
    
    print("\n" + "="*30)
    print("2. TỐI ƯU HÓA PHẦN CỨNG")
    print("="*30)
    print(f"Thiết thiết bị đang chạy: {device_name}")
    print("="*60)

    # 2. Hiển thị Summary
    print_model_summary(model)

    # 3. Đánh giá trên tập Validation
    if not os.path.exists(VAL_DATA_DIR):
        print(f"\u274c Không tìm thấy thư mục validation: {VAL_DATA_DIR}")
        return

    print(f"\n[INFO] Đang đánh giá trên tập dữ liệu: {VAL_DATA_DIR}...")
    y_true = []
    y_pred = []
    report_data = []
    latencies = []

    # Duyệt qua các thư mục class trong val/
    classes = sorted(os.listdir(VAL_DATA_DIR))
    class_names = list(model.names.values())
    
    count = 0
    max_test = 200 # Giới hạn số lượng test case
    
    for cls_name in classes:
        cls_dir = os.path.join(VAL_DATA_DIR, cls_name)
        if not os.path.isdir(cls_dir): continue
        
        images = os.listdir(cls_dir)
        # Lấy một số lượng ảnh nhất định để test nhanh
        test_images = images[:10] 
        
        for img_name in test_images:
            img_path = os.path.join(cls_dir, img_name)
            
            pred_char, conf, latency = run_inference_test(model, img_path)
            
            if pred_char is None: continue
            
            y_true.append(cls_name)
            y_pred.append(pred_char)
            latencies.append(latency)
            
            status = "Đúng" if cls_name == pred_char else "SAI"
            if count < max_test:
                report_data.append([cls_name, pred_char, f"{conf:.1%}", status])
            count += 1

    # 4. Hiển thị báo cáo bảng (Dạng Table)
    print("\n" + "="*80)
    print(f"{'THỰC TẾ':<12} | {'DỰ ĐOÁN':<12} | {'ĐỘ TIN CẬY':<12} | {'TRẠNG THÁI':<12}")
    print("-" * 80)
    for row in report_data[:30]: # In 30 dòng đầu làm mẫu
        print(f"{row[0]:<12} | {row[1]:<12} | {row[2]:<12} | {row[3]:<12}")
    
    if len(report_data) > 30:
        print(f"... (Đã kiểm tra tổng cộng {len(report_data)} ảnh kÝ tự) ...")
    print("="*80)

    # 5. Thống kê hiệu năng
    if latencies:
        avg_latency = np.mean(latencies)
        print(f"\n⚡ Tốc độ xử lý trung bình (Latency): {avg_latency:.2f} ms/ký tự")
    
    # 6. Vẽ Confusion Matrix
    if y_true:
        plot_confusion_matrix(y_true, y_pred, class_names)
    
    print("\n\u2705 Hoàn tất đánh giá!")

if __name__ == "__main__":
    main()
