"""
Script chẩn đoán toàn bộ pipeline nhận dạng biển số xe.
Kiểm tra từng bước: YOLO detect → Segmentation → CNN Classify
Chạy: py debug_pipeline.py --image <duong_dan_anh>
"""

import cv2
import sys
import os
import argparse
import numpy as np

def test_yolo(model_path: str, frame):
    """Kiểm tra YOLO có phát hiện biển số không"""
    from ultralytics import YOLO
    print(f"\n--- [1] YOLO DETECT ---")
    print(f"    Model: {model_path}")
    
    if not os.path.exists(model_path):
        print(f"    ❌ KHÔNG TÌM THẤY FILE MODEL: {model_path}")
        return None

    model = YOLO(model_path)
    results = model(frame, conf=0.25, verbose=False)  # conf thấp để debug
    
    detections = []
    for r in results:
        if r.boxes is not None and len(r.boxes) > 0:
            for box in r.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                detections.append((conf, cls, (x1, y1, x2, y2)))
                print(f"    ✅ Phát hiện: class={cls}, conf={conf:.2f}, box=({x1},{y1},{x2},{y2})")

    if not detections:
        print(f"    ❌ KHÔNG PHÁT HIỆN GÌ trong ảnh này.")
        print(f"       (conf ngưỡng đang là 0.25 — nếu vẫn trống có thể sai model hoặc ảnh không có biển số)")
    
    return detections


def test_segmentation(plate_crop):
    """Kiểm tra OpenCV có cắt được ký tự không"""
    print(f"\n--- [2] SEGMENTATION ---")
    from core.segmentation import segment_characters, preprocess_plate, find_char_contours
    
    binary = preprocess_plate(plate_crop)
    boxes = find_char_contours(binary)
    print(f"    Số contour tìm được (trước lọc): {len(boxes)}")
    
    chars = segment_characters(plate_crop, two_rows=True, target_size=32)
    print(f"    Số ký tự sau lọc: {len(chars)}")
    
    if len(chars) == 0:
        print("    ❌ KHÔNG CẮT ĐƯỢC ký tự nào!")
        print("       Nguyên nhân có thể: ảnh biển số quá nhỏ, nhiễu cao hoặc contrast kém")
        h, w = plate_crop.shape[:2]
        print(f"       Kích thước biển số crop: {w}x{h}px")
        if h < 20 or w < 60:
            print("       → Ảnh quá nhỏ! YOLO cần phát hiện biển số rõ hơn.")
    
    return chars


def test_cnn(char_model_path: str, char_images):
    """Kiểm tra CNN có nhận diện từng ký tự không"""
    print(f"\n--- [3] CNN CLASSIFY ---")
    print(f"    Model: {char_model_path}")
    
    if not os.path.exists(char_model_path):
        print(f"    ❌ KHÔNG TÌM THẤY FILE MODEL: {char_model_path}")
        return ""
    
    from core.char_recognizer import load_char_model, predict_character
    char_model = load_char_model(char_model_path)
    
    text = ""
    for i, cimg in enumerate(char_images):
        pred = predict_character(char_model, cimg, conf_threshold=0.1)  # ngưỡng thấp để debug
        print(f"    Ký tự [{i}]: {pred if pred else '???'}")
        if pred:
            text += pred
    
    print(f"    Kết quả tổng hợp: '{text}'")
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True, help="Đường dẫn ảnh cần test")
    parser.add_argument("--model", type=str, default="data/models/yolov8n.pt", help="YOLO model for plate detection")
    parser.add_argument("--char-model", type=str, default="data/models/char_model/weights/best.pt", help="CNN char model")
    args = parser.parse_args()
    
    print("=" * 60)
    print("PIPELINE DIAGNOSTICS")
    print("=" * 60)
    print(f"Ảnh test: {args.image}")
    
    frame = cv2.imread(args.image)
    if frame is None:
        print(f"❌ Không đọc được ảnh: {args.image}")
        return
    
    h, w = frame.shape[:2]
    print(f"Kích thước ảnh: {w}x{h}px")
    
    # --- Bước 1: YOLO ---
    detections = test_yolo(args.model, frame)
    
    # --- Bước 2 & 3: Segmentation + CNN trên vùng phát hiện ---
    if detections:
        best_det = max(detections, key=lambda d: d[0])
        conf, cls, (x1, y1, x2, y2) = best_det
        plate_crop = frame[y1:y2, x1:x2]
        
        char_images = test_segmentation(plate_crop)
        
        if char_images:
            test_cnn(args.char_model, char_images)
    else:
        print("\n⚠️  Bỏ qua Segmentation và CNN vì YOLO không phát hiện được gì.")
    
    print("\n" + "=" * 60)
    print("CHẨN ĐOÁN XONG!")
    print("=" * 60)

if __name__ == "__main__":
    main()
