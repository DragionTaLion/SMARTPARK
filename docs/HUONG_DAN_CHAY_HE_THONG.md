# 🚀 Hướng dẫn chạy hệ thống hoàn chỉnh

## ✅ Trạng thái hiện tại

Tất cả dependencies đã được cài đặt:
- ✅ EasyOCR
- ✅ pyserial (cho Arduino)
- ✅ Database đang chạy
- ✅ Dữ liệu mẫu đã có trong DB

## 📋 Các bước để chạy hệ thống

### Bước 1: Train Model YOLO (Nếu chưa có)

```bash
py train_yolo.py
```

**Thời gian:** 2-4 giờ (CPU) hoặc 30-60 phút (GPU)

**Kết quả:** Model sẽ được lưu tại:
```
HeThongBarrier/Plate_Detection_v1/weights/best.pt
```

### Bước 2: Nạp code cho Arduino

1. Mở **Arduino IDE**
2. Copy nội dung file `arduino_barrier.ino`
3. Kết nối Arduino vào máy tính
4. Chọn đúng **Board** và **Port** trong Tools
5. Click **Upload** để nạp code

**Kết nối Servo:**
- Signal (Cam) → D9
- VCC (Đỏ) → 5V
- GND (Nâu/Đen) → GND

### Bước 3: Tìm COM Port của Arduino

**Cách 1: Device Manager**
1. Mở Device Manager
2. Vào **Ports (COM & LPT)**
3. Tìm **Arduino Uno** hoặc **USB Serial Port**
4. Ghi nhớ số COM (VD: COM3, COM5, COM6)

**Cách 2: Python**
```python
import serial.tools.list_ports

ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"{port.device}: {port.description}")
```

### Bước 4: Chạy hệ thống

#### Chạy với Webcam:
```bash
py main_system.py --com COM3 --camera 0
```

**Tham số:**
- `--com`: COM port của Arduino (VD: COM3, COM5)
- `--camera`: ID webcam (0 là mặc định)
- `--model`: Đường dẫn model (mặc định: `HeThongBarrier/Plate_Detection_v1/weights/best.pt`)

#### Chạy với ảnh (test):
```bash
py main_system.py --image test_image.jpg --com COM3
```

#### Chỉ định model khác:
```bash
py main_system.py --model path/to/model.pt --com COM3
```

### Bước 5: Điều khiển khi chạy

Khi hệ thống đang chạy:
- **Nhấn 'q'**: Thoát
- **Nhấn 's'**: Chụp và lưu ảnh hiện tại

## 🎯 Flow hoạt động

```
1. Webcam capture frame
   ↓
2. YOLO detect biển số
   ↓
3. EasyOCR đọc text từ vùng biển số
   ↓
4. Kiểm tra trong database (bảng cudan)
   ↓
5a. CÓ trong DB → Mở barrier + Ghi log 'Vao'
5b. KHÔNG có → KHÔNG mở barrier + Ghi log 'Tu choi'
```

## 📊 Xem kết quả

### Xem lịch sử trong Database:

**Qua pgAdmin:**
1. Mở: http://localhost:5050
2. Login: `admin@admin.com` / `admin`
3. Kết nối server `postgres`
4. Chạy query:
```sql
SELECT bien_so_xe, trang_thai, thoi_gian 
FROM lichsuravao 
ORDER BY thoi_gian DESC 
LIMIT 20;
```

**Qua Python:**
```python
from barrier_db_logic import get_conn
import psycopg2

conn = get_conn()
cur = conn.cursor()
cur.execute("""
    SELECT bien_so_xe, trang_thai, thoi_gian 
    FROM lichsuravao 
    ORDER BY thoi_gian DESC 
    LIMIT 20
""")
for row in cur.fetchall():
    print(row)
cur.close()
conn.close()
```

## ⚠️ Troubleshooting

### Lỗi: "No module named 'ultralytics'"
```bash
py -m pip install ultralytics
```

### Lỗi: "Model not found"
- Đảm bảo đã train model: `py train_yolo.py`
- Hoặc chỉ định đường dẫn model: `--model path/to/model.pt`

### Lỗi: "Cannot open webcam"
- Kiểm tra webcam đã kết nối chưa
- Thử đổi camera ID: `--camera 1`

### Lỗi: "Arduino không nhận lệnh"
- Kiểm tra COM port đúng chưa
- Kiểm tra Arduino đã nạp code chưa
- Kiểm tra baud rate: Phải là 9600
- Kiểm tra driver CH340/CP2102

### Lỗi: "Database connection failed"
```bash
# Kiểm tra containers
docker-compose ps

# Nếu không chạy, khởi động lại
docker-compose up -d
```

## 🔧 Tùy chỉnh

### Thay đổi thời gian mở barrier:
Sửa trong `arduino_barrier.ino`:
```cpp
const int OPEN_DURATION = 5000; // 5 giây thay vì 3 giây
```

### Thay đổi cooldown (tránh xử lý trùng):
Sửa trong `main_system.py`:
```python
self.cooldown_seconds = 10  # 10 giây thay vì 5 giây
```

### Thay đổi confidence threshold:
Sửa trong `main_system.py`:
```python
results = self.model(frame, conf=0.7, verbose=False)  # 0.7 thay vì 0.5
```

## 📝 Ghi chú

- Hệ thống sẽ tự động tránh xử lý cùng 1 biển số nhiều lần trong vòng 5 giây (cooldown)
- Mỗi frame được xử lý mỗi 5 frame để tăng tốc độ
- Barrier sẽ tự động đóng sau 3 giây mở
- Tất cả xe (kể cả xe lạ) đều được ghi log vào database

---

**Hệ thống đã sẵn sàng! Chúc bạn thành công! 🎉**
