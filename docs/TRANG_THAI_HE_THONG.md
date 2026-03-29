# 📊 Trạng thái hệ thống hiện tại

## ✅ Đã sẵn sàng:

1. **Python 3.12.10** ✅
2. **PyTorch 2.9.1** ✅ (CPU version)
3. **Ultralytics** ✅
4. **OpenCV 4.13.0** ✅
5. **Dataset** ✅ (2,083 train + 200 valid images)
6. **Docker & PostgreSQL** ✅ (Containers đang chạy)

## ⚠️ Cần cài đặt:

### 1. EasyOCR (Cho bước đọc chữ biển số)
```bash
py -m pip install easyocr
```

### 2. CUDA Support (Để tăng tốc training 10-20 lần)

#### Bước 1: Kiểm tra GPU NVIDIA
```bash
nvidia-smi
```

#### Bước 2: Cài đặt CUDA Toolkit
- Tải từ: https://developer.nvidia.com/cuda-downloads
- Chọn: Windows > x86_64 > 10/11 > exe (local)
- Cài đặt phiên bản mới nhất (khuyến nghị CUDA 11.8 hoặc 12.1)

#### Bước 3: Cài đặt PyTorch với CUDA
Sau khi cài CUDA Toolkit, chạy:

**Cho CUDA 11.8:**
```bash
py -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**Cho CUDA 12.1:**
```bash
py -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### Bước 4: Kiểm tra lại
```bash
py -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

### 3. psycopg2 (Đã có, nhưng cần kiểm tra kết nối)
```bash
py -m pip install psycopg2-binary
```

## 🚀 Các bước tiếp theo:

### Bước 1: Cài EasyOCR
```bash
py -m pip install easyocr
```

### Bước 2: (Tùy chọn) Cài CUDA để tăng tốc
- Nếu có GPU NVIDIA: Làm theo hướng dẫn trên
- Nếu không có GPU: Có thể train bằng CPU (chậm hơn nhưng vẫn được)

### Bước 3: Bắt đầu training
```bash
py train_yolo.py
```

**Lưu ý khi train bằng CPU:**
- Giảm batch size xuống 4 hoặc 8 trong `train_yolo.py`
- Thời gian train: ~2-4 giờ (thay vì 30-60 phút với GPU)

### Bước 4: Sau khi train xong
- Model sẽ được lưu tại: `HeThongBarrier/Plate_Detection_v1/weights/best.pt`
- Sử dụng model này cho inference

## 📝 Ghi chú:

- **Database**: Đang chạy trên port 5433 (tránh conflict với PostgreSQL local)
- **pgAdmin**: Truy cập tại http://localhost:5050
- **Dataset**: Đã sẵn sàng với 2,384 ảnh

## 🔧 Troubleshooting:

### Lỗi: "CUDA out of memory"
**Giải pháp:** Giảm batch size trong `train_yolo.py`:
```python
batch=4,  # Thay vì 16
```

### Lỗi: "Database connection failed"
**Kiểm tra:**
```bash
docker-compose ps
```
Nếu containers không chạy:
```bash
docker-compose up -d
```

### Lỗi: "ModuleNotFoundError"
**Giải pháp:** Cài đặt tất cả dependencies:
```bash
py -m pip install -r requirements.txt
```

---

**Trạng thái:** ✅ Hệ thống đã sẵn sàng để bắt đầu training!
