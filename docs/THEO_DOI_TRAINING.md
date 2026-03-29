# 📊 Theo dõi quá trình Training

## ✅ Training đã bắt đầu!

Model đang được train ở **background**. Quá trình này sẽ mất:
- **CPU**: ~2-4 giờ
- **GPU**: ~30-60 phút (nếu có CUDA)

## 🔍 Cách theo dõi

### 1. Kiểm tra tiến trình

**Xem Python đang chạy:**
```bash
tasklist | findstr python
```

**Xem thư mục kết quả:**
```bash
dir HeThongBarrier\Plate_Detection_v1
```

### 2. Xem logs real-time

Nếu muốn xem output chi tiết, chạy lại ở foreground:
```bash
py train_yolo.py
```

### 3. Kiểm tra kết quả

**Model sẽ được lưu tại:**
```
HeThongBarrier/Plate_Detection_v1/weights/
├── best.pt    ← Model tốt nhất (dùng để inference)
└── last.pt    ← Model cuối cùng
```

**Các file khác:**
```
HeThongBarrier/Plate_Detection_v1/
├── results.png           ← Biểu đồ kết quả
├── confusion_matrix.png  ← Confusion matrix
├── F1_curve.png
├── PR_curve.png
└── ...
```

## 📈 Các chỉ số quan trọng

Khi training, bạn sẽ thấy:
- **mAP50**: Mean Average Precision @ IoU=0.5 (càng cao càng tốt, >0.8 là tốt)
- **mAP50-95**: Mean Average Precision @ IoU=0.5:0.95 (tổng quát hơn)
- **Precision**: Độ chính xác
- **Recall**: Độ nhạy

## ⏱️ Thời gian dự kiến

Với **2,083 ảnh train** và **batch=4** (CPU):
- Mỗi epoch: ~5-10 phút
- 50 epochs: ~2.5-4 giờ

## 🛑 Dừng training (nếu cần)

Nếu muốn dừng training:
1. Tìm process Python: `tasklist | findstr python`
2. Kill process: `taskkill /PID <PID> /F`

**Lưu ý:** Model sẽ được lưu checkpoint, có thể tiếp tục sau.

## ✅ Khi training xong

1. Kiểm tra file `best.pt` đã được tạo
2. Xem biểu đồ kết quả trong `results.png`
3. Chạy hệ thống:
   ```bash
   py main_system.py --com COM3 --camera 0
   ```

## 🔧 Troubleshooting

### Training bị treo
- Kiểm tra RAM còn đủ không
- Giảm batch size xuống 2 trong `train_yolo.py`

### Lỗi "out of memory"
- Giảm batch size: `batch=2`
- Giảm image size: `imgsz=416`

### Muốn train tiếp từ checkpoint
- Sửa trong `train_yolo.py`: `resume=True`

---

**Training đang chạy! Hãy kiên nhẫn đợi... ⏳**
