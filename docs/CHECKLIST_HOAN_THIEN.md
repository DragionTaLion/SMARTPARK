# ✅ Checklist hoàn thiện hệ thống

## 🎯 Trạng thái hiện tại: ~70% hoàn thành

### ✅ Đã hoàn thành:

1. **Database & Docker** ✅
   - PostgreSQL chạy trên port `55432`
   - pgAdmin chạy trên port `5050`
   - Schema đã cập nhật: Hỗ trợ trạng thái 'Vao', 'Ra', 'Tu choi'
   - Logic ghi log cả xe lạ đã hoạt động

2. **Dataset & Training Script** ✅
   - Dataset: 2,083 train + 200 valid images
   - Script `train_yolo.py` đã sẵn sàng
   - Tự động phát hiện GPU/CPU
   - Batch size tự điều chỉnh (4 cho CPU, 16 cho GPU)

3. **Logic tích hợp DB + Arduino** ✅
   - File `barrier_db_logic.py` đã hoàn chỉnh
   - Hỗ trợ xử lý xe vào/ra/xe lạ
   - Ghi log đầy đủ vào database

4. **EasyOCR Preparation** ✅
   - File `prepare_easyocr.py` sẵn sàng
   - Hỗ trợ đọc biển số 2 dòng (Việt Nam)

## 📋 Các bước tiếp theo:

### Bước 1: Cài đặt EasyOCR (5-10 phút)
```bash
py -m pip install easyocr
```
**Lưu ý**: Lần đầu chạy sẽ tải model (~500MB), mất vài phút.

### Bước 2: Bắt đầu Training (30 phút - 4 giờ)
```bash
py train_yolo.py
```

**Thời gian dự kiến:**
- Với CPU (batch=4): ~2-4 giờ
- Với GPU (nếu cài CUDA): ~30-60 phút

**Kết quả:**
- Model sẽ được lưu tại: `HeThongBarrier/Plate_Detection_v1/weights/best.pt`

### Bước 3: Cài đặt pyserial (cho Arduino)
```bash
py -m pip install pyserial
```

### Bước 4: Tìm COM Port của Arduino
1. Mở **Device Manager**
2. Vào **Ports (COM & LPT)**
3. Ghi nhớ số COM (VD: COM3, COM5, COM6)

### Bước 5: Thêm dữ liệu mẫu vào Database

**Qua pgAdmin:**
1. Mở: http://localhost:5050
2. Login: `admin@admin.com` / `admin`
3. Kết nối server `postgres`
4. Mở database `nhan_dien_bien_so_xe`
5. Thêm dữ liệu vào bảng `cudan`:
   ```sql
   INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho) 
   VALUES ('30A-12345', 'Nguyễn Văn A', 'A101');
   ```

**Hoặc qua Python:**
```python
from barrier_db_logic import get_conn
import psycopg2

conn = get_conn()
cur = conn.cursor()
cur.execute(
    "INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho) VALUES (%s, %s, %s)",
    ("30A-12345", "Nguyễn Văn A", "A101")
)
conn.commit()
cur.close()
conn.close()
```

### Bước 6: Test logic DB + Arduino

**Test xe có trong DB:**
```bash
py -c "from barrier_db_logic import process_vehicle_entry; process_vehicle_entry('30A-12345', com_port='COM3', status='Vao')"
```

**Test xe lạ:**
```bash
py -c "from barrier_db_logic import process_vehicle_entry; process_vehicle_entry('99Z-99999', com_port='COM3', status='Vao')"
```

**Kiểm tra log:**
```sql
SELECT bien_so_xe, trang_thai, thoi_gian 
FROM lichsuravao 
ORDER BY thoi_gian DESC 
LIMIT 10;
```

### Bước 7: Lắp ráp Hardware

**Arduino + Servo:**
- Dây Signal (Cam) → D9
- Dây VCC (Đỏ) → 5V
- Dây GND (Nâu/Đen) → GND

**Nạp code Arduino:**
```cpp
#include <Servo.h>
Servo myservo;

void setup() {
  myservo.attach(9);
  Serial.begin(9600);
  myservo.write(0); // Đóng barrier
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    if (command == 'O') {
      myservo.write(90); // Mở barrier
      delay(3000);
      myservo.write(0);  // Đóng lại sau 3 giây
    }
  }
}
```

### Bước 8: Tích hợp YOLO + EasyOCR + DB

Sau khi có `best.pt`, tạo file `main_system.py`:

```python
from ultralytics import YOLO
from prepare_easyocr import init_easyocr, read_license_plate_2_lines
from barrier_db_logic import process_vehicle_entry
import cv2

# Load model
model = YOLO('HeThongBarrier/Plate_Detection_v1/weights/best.pt')
reader = init_easyocr()

# Capture từ webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Detect biển số
    results = model(frame)
    
    for result in results:
        boxes = result.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            
            # Đọc text
            ocr_result = read_license_plate_2_lines(
                reader, frame, 
                (int(x1), int(y1), int(x2), int(y2))
            )
            plate_number = ocr_result['line1'] + ocr_result['line2']
            
            # Xử lý
            process_vehicle_entry(plate_number, com_port="COM3", status="Vao")
    
    cv2.imshow('Frame', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

## 🎯 Mục tiêu cuối cùng:

- ✅ Nhận diện biển số từ webcam
- ✅ Đọc chữ bằng EasyOCR
- ✅ Kiểm tra trong database
- ✅ Mở barrier nếu có trong DB
- ✅ Ghi log đầy đủ (cả xe lạ)

## 📊 Kiểm tra tiến độ:

```bash
# Test hệ thống
py test_system.py

# Test DB connection
py -c "from barrier_db_logic import check_plate_in_db; print(check_plate_in_db('30A-12345'))"

# Xem lịch sử
docker exec postgres_nhan_dien_bien_so psql -U postgres -d nhan_dien_bien_so_xe -c "SELECT COUNT(*) FROM lichsuravao;"
```

---

**Chúc bạn hoàn thành dự án thành công! 🚀**
