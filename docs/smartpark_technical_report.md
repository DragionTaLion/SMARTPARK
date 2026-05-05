# Báo cáo Kỹ thuật: Hệ thống SmartPark

Tài liệu này giải thích cấu trúc và cơ chế hoạt động của phần mềm Web trong dự án SmartPark để phục vụ việc bảo vệ đồ án.

---

## 🏗️ 1. Kiến trúc Hệ thống (System Architecture)

Hệ thống hoạt động theo mô hình **Client-Server-Hardware**, trong đó Phần Web đóng vai trò trung tâm điều phối.

### A. Luồng dữ liệu Đầu vào (Input Flow)
1. **Hình ảnh**: ESP32-CAM truyền luồng MJPEG về Backend. Backend sử dụng OpenCV để "bắt" các khung hình (frames) từ luồng này đưa vào bộ nhớ đệm (Buffer).
2. **Cảm biến**: Cảm biến siêu âm trên ESP8266 phát hiện vật cản (< 15cm) và gửi một yêu cầu `HTTP POST` đến endpoint `/api/trigger` của Backend.

### B. Luồng xử lý Trung tâm (Processing Flow)
1. **AI Detection**: Khi nhận tín hiệu Trigger, Backend lấy frame mới nhất từ Buffer đưa vào mô hình **YOLOv8** để định vị biển số.
2. **AI Recognition**: Vùng chứa biển số được cắt ra và đưa vào **EasyOCR** để chuyển từ ảnh sang văn bản (Text).
3. **Business Logic**: Backend truy vấn **PostgreSQL** để so khớp biển số vừa đọc được với danh sách cư dân (có sử dụng thuật toán Fuzzy Match để tăng độ chính xác).

### C. Luồng phản hồi Đầu ra (Output Flow)
1. **Phần cứng**: Backend trả về phản hồi JSON cho ESP8266. Nếu khớp cư dân, lệnh `open` được gửi đi để quay Servo.
2. **Giao diện**: Kết quả (Ảnh, Tên chủ xe, Biển số) được đẩy ngay lập tức lên Dashboard thông qua kết nối **WebSocket**.

---

## 🛠️ 2. Công nghệ sử dụng (Tech Stack)

### Frontend: React.js
- **Lý do**: Sử dụng Virtual DOM giúp cập nhật các dòng Log và số liệu thống kê liên tục mà không làm lag trình duyệt.
- **Thư viện**: Lucide Icons (Biểu tượng), Motion (Hiệu ứng mượt), Tailwind CSS (Giao diện cao cấp).

### Backend: FastAPI (Python)
- **Lý do**: Tốc độ xử lý tương đương Go và NodeJS. Hỗ trợ `async/await` giúp xử lý đồng thời hàng chục kết nối từ Camera và Cảm biến mà không bị nghẽn (Blocking).

### Database: PostgreSQL
- **Lý do**: Cơ sở dữ liệu quan hệ mạnh mẽ, lưu trữ dữ liệu có cấu trúc tốt, hỗ trợ tốt cho các báo cáo thống kê phức tạp sau này.

---

## 📡 3. Các giao thức giao tiếp (Communication Protocols)

| Giao thức | Hướng truyền | Vai trò |
| :--- | :--- | :--- |
| **HTTP (REST)** | Hardware -> Backend | ESP8266 gửi tín hiệu Trigger và nhận lệnh mở Barrier. |
| **MJPEG** | Camera -> Backend | Truyền hình ảnh thời gian thực để AI xử lý. |
| **WebSocket** | Backend -> Browser | Đẩy kết quả nhận diện lên màn hình tức thì. |
| **SQL** | Backend -> DB | Truy vấn thông tin cư dân và lưu nhật ký ra vào. |

---

## 💡 4. Giải thích thuật ngữ (Glossary for Defense)

- **Region of Interest (ROI)**: Vùng chứa biển số mà YOLO tìm thấy.
- **Fuzzy Matching**: Tìm kiếm "xấp xỉ", giúp nhận diện đúng xe dù AI đọc sai một vài chữ cái do bụi bẩn trên biển số.
- **Base64 Encoding**: Chuyển đổi hình ảnh thành chuỗi ký tự để có thể lưu trực tiếp vào Database hoặc truyền qua mạng một cách dễ dàng.
