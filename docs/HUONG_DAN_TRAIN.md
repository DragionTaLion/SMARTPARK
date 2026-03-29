# 🚀 Hướng dẫn huấn luyện Model YOLOv8n

## ✅ Đã chuẩn bị xong:
- ✅ Dataset: `Vietnam-license-plate-1/` (2,384 ảnh)
- ✅ File cấu hình: `Vietnam-license-plate-1/data.yaml`
- ✅ Script huấn luyện: `train_yolo.py`
- ✅ Thư viện: `ultralytics` đã được cài đặt

## 🎯 Chạy huấn luyện:

### Cách 1: Chạy trực tiếp
```bash
py train_yolo.py
```

### Cách 2: Sử dụng Python
```bash
python train_yolo.py
```

## ⚙️ Cấu hình GPU (Nếu có GPU NVIDIA):

### Kiểm tra GPU:
```bash
py -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### Nếu GPU không được phát hiện:

1. **Cài đặt CUDA Toolkit:**
   - Tải từ: https://developer.nvidia.com/cuda-downloads
   - Cài đặt phiên bản phù hợp với GPU của bạn

2. **Cài đặt PyTorch với CUDA:**
   ```bash
   # Ví dụ cho CUDA 11.8
   py -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

3. **Kiểm tra lại:**
   ```bash
   py -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
   ```

## 📊 Theo dõi quá trình huấn luyện:

### Thời gian dự kiến:
- **Với GPU (Legion 7)**: ~30-60 phút
- **Với CPU**: ~2-4 giờ

### Dấu hiệu GPU đang hoạt động:
- ✅ Quạt tản nhiệt chạy mạnh
- ✅ Task Manager hiển thị GPU usage cao
- ✅ Console hiển thị: "✅ GPU được phát hiện: [Tên GPU]"

### Kết quả sau khi huấn luyện:
```
HeThongBarrier/
└── Plate_Detection_v1/
    ├── weights/
    │   ├── best.pt      ← Model tốt nhất (dùng để inference)
    │   └── last.pt      ← Model cuối cùng
    ├── results.png      ← Biểu đồ kết quả
    ├── confusion_matrix.png
    └── ...
```

## 🔧 Tùy chỉnh tham số:

Mở file `train_yolo.py` và chỉnh sửa:

```python
epochs=50,      # Tăng nếu muốn model chính xác hơn (100, 150...)
imgsz=640,      # Giảm nếu hết RAM (416, 320...)
batch=16,       # Giảm nếu hết RAM (8, 4, 2...)
```

## ⚠️ Xử lý lỗi:

### Lỗi: "CUDA out of memory"
**Giải pháp:**
- Giảm `batch` size: `batch=8` hoặc `batch=4`
- Giảm `imgsz`: `imgsz=416` hoặc `imgsz=320`

### Lỗi: "FileNotFoundError: data.yaml"
**Giải pháp:**
- Đảm bảo file `Vietnam-license-plate-1/data.yaml` tồn tại
- Kiểm tra đường dẫn trong script

### Lỗi: "ModuleNotFoundError: No module named 'ultralytics'"
**Giải pháp:**
```bash
py -m pip install ultralytics
```

## 📝 Lưu ý:

1. **Không tắt máy** trong quá trình huấn luyện
2. **Đảm bảo đủ dung lượng ổ cứng** (ít nhất 5GB trống)
3. **Kết nối internet ổn định** (để tải model pre-trained lần đầu)
4. Model sẽ tự động lưu checkpoint, có thể tiếp tục từ checkpoint nếu bị gián đoạn

## 🎉 Sau khi huấn luyện xong:

Model `best.pt` sẽ được sử dụng cho:
- Nhận diện biển số từ webcam
- Tích hợp với EasyOCR để đọc chữ
- Kiểm tra với database PostgreSQL

---

**Chúc bạn huấn luyện thành công! 🚀**
