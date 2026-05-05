# SmartPark ALPR v2.1 Pro — Training Guide

Tài liệu này hướng dẫn cách huấn luyện lại mô hình AI (Nhận diện biển số và Nhận diện ký tự) cho hệ thống SmartPark.

## 1. Chuẩn bị môi trường
Yêu cầu: Python 3.8+, GPU NVIDIA (khuyên dùng để train nhanh).

```bash
pip install ultralytics easyocr torch torchvision
```

## 2. Huấn luyện mô hình phát hiện biển số (YOLOv8)
Dự án sử dụng YOLOv8 để định vị biển số xe trong khung hình.

### Cấu trúc dữ liệu:
Dữ liệu nên được đặt tại: `data/datasets/vietnam_license_plate/`
- `train/`: Ảnh và label để huấn luyện.
- `valid/`: Ảnh và label để kiểm chứng.
- `data.yaml`: File cấu hình đường dẫn và các lớp (class).

### Lệnh huấn luyện:
Sử dụng script có sẵn hoặc chạy lệnh:
```bash
python scripts/train_yolo.py
```
Hoặc dùng CLI:
```bash
yolo task=detect mode=train model=yolov8n.pt data=data/datasets/vietnam_license_plate/data.yaml epochs=100 imgsz=640
```
*Sau khi train xong, lấy file `best.pt` trong `runs/detect/train/weights/` đưa vào `data/models/plate_detect.pt`.*

---

## 3. Huấn luyện mô hình nhận diện ký tự (CNN)
Dự án sử dụng một mô hình CNN chuyên biệt để đọc chữ số trên biển số sau khi đã cắt.

### Chuẩn bị dữ liệu:
Dữ liệu ký tự được phân loại vào các thư mục theo tên ký tự (0-9, A-Z) tại `data/datasets/characters/`.

### Lệnh huấn luyện:
```bash
python scripts/train_char_model.py
```
Mô hình sẽ thực hiện:
1. Preprocessing (Resize 32x32, Grayscale).
2. Train CNN với kiến trúc 56 layers (ResNet-like).
3. Lưu mô hình tại `data/models/char_model/weights/best.pt`.

---

## 4. Tích hợp mô hình vào hệ thống
Sau khi có các file `.pt` mới, hãy cập nhật đường dẫn trong `api_server.py`:

```python
MODEL_PATH = "path/to/your/new_plate_detect.pt"
CHAR_MODEL_PATH = "path/to/your/new_char_model.pt"
```

## 5. Lưu ý
- **Dataset**: Luôn đảm bảo ảnh biển số Việt Nam đa dạng (biển trắng, biển xanh, biển vàng, biển vuông/dài).
- **Augmentation**: Sử dụng các kỹ thuật xoay, nhiễu để tăng độ chính xác khi camera quay góc chéo.
