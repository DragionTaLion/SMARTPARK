# 📚 Hướng dẫn sử dụng hệ thống Barrier tự động

## 🗄️ Database Configuration

### Thông tin kết nối từ Python:
- **Host**: `localhost`
- **Port**: `55432` (đã đổi để tránh conflict với PostgreSQL local)
- **Database**: `nhan_dien_bien_so_xe`
- **User/Password**: `postgres` / `postgres`

### Kết nối pgAdmin:
- **URL**: http://localhost:5050
- **Login pgAdmin**: `admin@admin.com` / `admin`

Khi đăng ký Server trong pgAdmin:
- **Host**: `postgres` (tên service trong docker-compose.yml)
- **Port**: `5432` (port nội bộ trong container)
- **User/Password**: `postgres` / `postgres`
- **Maintenance DB**: `nhan_dien_bien_so_xe`

## 🔧 Cài đặt Dependencies

### 1. Cài đặt EasyOCR
```bash
py -m pip install easyocr
```

### 2. Cài đặt pyserial (cho Arduino)
```bash
py -m pip install pyserial
```

### 3. Cài đặt tất cả dependencies
```bash
py -m pip install -r requirements.txt
```

## 🚗 Logic xử lý xe vào/ra

### Trạng thái trong bảng `lichsuravao`:
- **'Vào'**: Xe có trong danh sách cư dân, được phép vào → **Mở barrier**
- **'Ra'**: Xe có trong danh sách cư dân, đang ra
- **'Tu choi'**: Xe lạ hoặc chưa đăng ký → **KHÔNG mở barrier** nhưng **VẪN ghi log**

### Flow xử lý:

```
1. Nhận diện biển số (YOLO + EasyOCR)
   ↓
2. Kiểm tra trong bảng `cudan`
   ↓
3a. CÓ trong DB → Mở barrier + Ghi log 'Vào'/'Ra'
3b. KHÔNG có → KHÔNG mở barrier + Ghi log 'Tu choi'
```

## 💻 Sử dụng Python API

### Import module:
```python
from barrier_db_logic import process_vehicle_entry, check_plate_in_db
```

### Xử lý xe vào:
```python
result = process_vehicle_entry(
    plate_number="30A-12345",
    com_port="COM3",  # Thay bằng COM port thực tế của bạn
    hinh_anh="path/to/image.jpg",  # Optional
    status="Vao"
)

print(result)
# {
#     'success': True/False,
#     'owner': 'Nguyễn Văn A' hoặc None,
#     'message': '...',
#     'trang_thai': 'Vào', 'Ra', hoặc 'Tu choi'
# }
```

### Xử lý xe ra:
```python
result = process_vehicle_entry(
    plate_number="30A-12345",
    com_port="COM3",
    status="Ra"  # Không mở barrier khi ra
)
```

### Chỉ kiểm tra biển số (không ghi log):
```python
owner = check_plate_in_db("30A-12345")
if owner:
    print(f"Xe của: {owner}")
else:
    print("Xe lạ")
```

## 🔌 Tìm COM Port của Arduino

### Trên Windows:
1. Mở **Device Manager**
2. Vào **Ports (COM & LPT)**
3. Tìm **Arduino Uno** hoặc **USB Serial Port** → Ghi nhớ số COM (VD: COM3, COM5, COM6)

### Kiểm tra bằng Python:
```python
import serial.tools.list_ports

ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"{port.device}: {port.description}")
```

## 📝 Thêm dữ liệu mẫu vào Database

### Cách 1: Qua pgAdmin
1. Mở pgAdmin: http://localhost:5050
2. Kết nối đến server `postgres`
3. Mở database `nhan_dien_bien_so_xe`
4. Click chuột phải vào bảng `cudan` → **View/Edit Data** → **Add New Row**
5. Điền:
   - `bien_so_xe`: VD `30A-12345`
   - `ten_chu_xe`: VD `Nguyễn Văn A`
   - `so_can_ho`: VD `A101`

### Cách 2: Qua SQL
```sql
INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho) 
VALUES ('30A-12345', 'Nguyễn Văn A', 'A101');
```

### Cách 3: Qua Python
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=55432,
    dbname="nhan_dien_bien_so_xe",
    user="postgres",
    password="postgres"
)
cur = conn.cursor()
cur.execute(
    "INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho) VALUES (%s, %s, %s)",
    ("30A-12345", "Nguyễn Văn A", "A101")
)
conn.commit()
cur.close()
conn.close()
```

## 🧪 Test hệ thống

### Test 1: Xe có trong DB
```bash
py -c "from barrier_db_logic import process_vehicle_entry; process_vehicle_entry('30A-12345', status='Vao')"
```

Kết quả mong đợi:
- ✅ Tìm thấy chủ xe
- ✅ Gửi lệnh mở barrier (nếu Arduino kết nối)
- ✅ Ghi log với trạng thái 'Vào'

### Test 2: Xe lạ
```bash
py -c "from barrier_db_logic import process_vehicle_entry; process_vehicle_entry('99Z-99999', status='Vao')"
```

Kết quả mong đợi:
- ⚠️ Không tìm thấy trong DB
- ❌ KHÔNG mở barrier
- ✅ Ghi log với trạng thái 'Tu choi'

### Test 3: Xem lịch sử
```sql
SELECT bien_so_xe, trang_thai, thoi_gian 
FROM lichsuravao 
ORDER BY thoi_gian DESC 
LIMIT 10;
```

## 🔄 Tích hợp với YOLO + EasyOCR

Sau khi có model `best.pt`, bạn sẽ tích hợp như sau:

```python
from ultralytics import YOLO
from prepare_easyocr import init_easyocr, read_license_plate_2_lines
from barrier_db_logic import process_vehicle_entry
import cv2

# Load model
model = YOLO('HeThongBarrier/Plate_Detection_v1/weights/best.pt')

# Khởi tạo EasyOCR
reader = init_easyocr()

# Đọc ảnh từ webcam hoặc file
img = cv2.imread('test_image.jpg')

# Detect biển số
results = model(img)
for result in results:
    boxes = result.boxes
    for box in boxes:
        # Lấy tọa độ
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        
        # Đọc text từ vùng biển số
        ocr_result = read_license_plate_2_lines(reader, img, (int(x1), int(y1), int(x2), int(y2)))
        plate_number = ocr_result['line1'] + ocr_result['line2']
        
        # Xử lý vào/ra
        process_vehicle_entry(plate_number, com_port="COM3", status="Vao")
```

## ⚠️ Troubleshooting

### Lỗi: "connection to server failed"
- Kiểm tra Docker containers đang chạy: `docker-compose ps`
- Nếu không chạy: `docker-compose up -d`
- Kiểm tra port: Phải là `55432` (không phải `5432`)

### Lỗi: "No module named 'serial'"
```bash
py -m pip install pyserial
```

### Lỗi: "Arduino không nhận lệnh"
- Kiểm tra COM port đúng chưa
- Kiểm tra Arduino đã nạp code chưa
- Kiểm tra baud rate: Phải là `9600`
- Kiểm tra driver CH340/CP2102 đã cài chưa

### Lỗi: "CHECK constraint violation"
- Đảm bảo `trang_thai` chỉ có: `'Vào'`, `'Ra'`, hoặc `'Tu choi'`
- Đã cập nhật schema, nếu vẫn lỗi: Chạy lại `docker-compose up -d`

## 📊 Xem thống kê

### Số lượng xe vào/ra hôm nay:
```sql
SELECT trang_thai, COUNT(*) 
FROM lichsuravao 
WHERE DATE(thoi_gian) = CURRENT_DATE 
GROUP BY trang_thai;
```

### Danh sách xe lạ:
```sql
SELECT bien_so_xe, thoi_gian 
FROM lichsuravao 
WHERE trang_thai = 'Tu choi' 
ORDER BY thoi_gian DESC;
```

---

**Hệ thống đã sẵn sàng! Chúc bạn thành công! 🚀**
