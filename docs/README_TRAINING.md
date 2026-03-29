# Hướng dẫn huấn luyện YOLOv8n cho nhận diện biển số xe

## Yêu cầu hệ thống

- Python 3.8 trở lên
- RAM: Tối thiểu 8GB (khuyến nghị 16GB)
- GPU: Không bắt buộc nhưng khuyến nghị (NVIDIA GPU với CUDA)

## Cài đặt

### 1. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 2. Lấy Roboflow API Key

1. Đăng ký tài khoản tại [https://roboflow.com](https://roboflow.com)
2. Truy cập dataset: [https://universe.roboflow.com/vietnam-license/vietnam-license-plate-hjswj](https://universe.roboflow.com/vietnam-license/vietnam-license-plate-hjswj)
3. Lấy API key từ: [https://app.roboflow.com/settings/api](https://app.roboflow.com/settings/api)
4. Mở file `train_yolo.py` và cập nhật:
   ```python
   ROBOFLOW_API_KEY = "YOUR_ROBOFLOW_API_KEY"  # Thay bằng API key của bạn
   ```

## Sử dụng

### Chạy script huấn luyện

```bash
python train_yolo.py
```

### Cấu hình tham số

Bạn có thể chỉnh sửa các tham số trong hàm `train_model()`:

```python
results, model = train_model(
    data_yaml_path=data_yaml_path,
    epochs=100,    # Số epochs (số lần lặp qua toàn bộ dataset)
    imgsz=640,     # Kích thước ảnh đầu vào (640, 416, hoặc 320)
    batch=16       # Batch size (giảm nếu hết RAM: 8, 4, hoặc 2)
)
```

### Sử dụng GPU (nếu có)

Trong file `train_yolo.py`, thay đổi:
```python
device='cpu',  # Thay 'cpu' bằng '0' nếu có GPU
```
thành:
```python
device='0',  # Sử dụng GPU đầu tiên
```

## Cấu trúc thư mục sau khi huấn luyện

```
.
├── dataset/                          # Dataset đã tải về
│   └── vietnam-license-plate-hjswj-1/
│       ├── train/
│       ├── valid/
│       ├── test/
│       └── data.yaml
├── models/                           # Model đã huấn luyện
│   └── license_plate_yolov8n.pt
├── runs/                             # Kết quả huấn luyện
│   └── license_plate_detection/
│       ├── weights/
│       │   ├── best.pt              # Model tốt nhất
│       │   └── last.pt               # Model cuối cùng
│       ├── results.png               # Biểu đồ kết quả
│       └── ...
└── train_yolo.py
```

## Kết quả

Sau khi huấn luyện xong, bạn sẽ có:

1. **best.pt**: Model có độ chính xác tốt nhất (trong quá trình validation)
2. **last.pt**: Model ở epoch cuối cùng
3. **license_plate_yolov8n.pt**: Bản sao của best.pt trong thư mục models/

## Sử dụng model đã huấn luyện

```python
from ultralytics import YOLO

# Load model
model = YOLO('models/license_plate_yolov8n.pt')

# Dự đoán
results = model('path/to/image.jpg')

# Hiển thị kết quả
results[0].show()
```

## Lưu ý

- Quá trình huấn luyện có thể mất nhiều giờ tùy thuộc vào:
  - Số lượng epochs
  - Kích thước dataset
  - Phần cứng (CPU/GPU)
- Nếu gặp lỗi về bộ nhớ (OOM), hãy giảm `batch` size hoặc `imgsz`
- Model sẽ tự động lưu checkpoint mỗi 10 epochs
- Early stopping sẽ dừng huấn luyện nếu không cải thiện trong 50 epochs

## Troubleshooting

### Lỗi: "No module named 'ultralytics'"
```bash
pip install ultralytics
```

### Lỗi: "CUDA out of memory"
- Giảm `batch` size xuống 8, 4, hoặc 2
- Giảm `imgsz` xuống 416 hoặc 320

### Lỗi: "Invalid API key"
- Kiểm tra lại API key từ Roboflow
- Đảm bảo đã cập nhật `ROBOFLOW_API_KEY` trong script
