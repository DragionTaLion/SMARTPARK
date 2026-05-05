# Phân tích Chuyên sâu: Công nghệ & Giao thức Hệ thống SmartPark

Tài liệu này cung cấp cái nhìn chi tiết về cơ sở hạ tầng kỹ thuật của dự án, giải thích lý do lựa chọn và cơ chế vận hành của các công nghệ lõi.

---

## 🏗️ 1. Phân tích Công nghệ sử dụng (Tech Stack Deep-Dive)

### A. Backend: FastAPI (Python 3.10+)
*   **Tại sao chọn?**: AI (YOLO, EasyOCR) chủ yếu chạy trên ngôn ngữ Python. FastAPI là framework cho phép tích hợp AI mượt mà nhất mà vẫn đảm bảo hiệu năng cực cao nhờ cơ chế xử lý bất đồng bộ (Asynchronous logic).
*   **Cơ chế**: FastAPI chạy trên máy chủ Uvicorn (ASGI), cho phép xử lý hàng trăm request cùng lúc mà không gây nghẽn cổ chai (Blocking). Điều này cực kỳ quan trọng khi hệ thống phải xử lý luồng ảnh Camera liên tục.

### B. Frontend: React.js (Vite)
*   **Cơ chế State Management**: Hệ thống sử dụng Hooks (`useState`, `useEffect`) để quản lý dữ liệu. Khi có biến số mới từ WebSocket, React chỉ thực hiện "Re-render" (vẽ lại) đúng phần tử đó trên màn hình thay vì toàn bộ trang web.
*   **Hiệu năng**: Vite giúp quá trình đóng gói code cực nhanh, làm cho trải nghiệm người dùng trên dashboard mượt mà, không có độ trễ.

### C. Database: PostgreSQL
*   **Đặc tính**: Là hệ quản trị cơ sở dữ liệu quan hệ (RDBMS) ổn định nhất thế giới. 
*   **Vai trò**: Lưu trữ dữ liệu cư dân dưới dạng cấu trúc, giúp việc quản lý hàng nghìn phương tiện trở nên dễ dàng và hỗ trợ tốt cho việc trích xuất báo cáo thống kê lượt ra/vào.

---

## 📡 2. Giao thức Giao tiếp (Communication Protocols)

Hệ thống là sự kết hợp của 4 loại giao thức chính, tạo nên một mạng lưới thông tin thông bạt từ Hardware đến người dùng cuối:

### A. Giao thức HTTP (REST API) - Định dạng dữ liệu: JSON
*   **Vai trò**: Dùng cho các hành động mang tính chất "Yêu cầu - Phản hồi" (Request-Response).
*   **Ứng dụng**: ESP8266 gửi tín hiệu Trigger; Web gửi lệnh thêm/sửa cư dân.
*   **Ưu điểm**: Dễ triển khai, tương thích tốt với mọi thiết bị IoT.

### B. Giao thức WebSocket (ws://) - Giao tiếp song công (Full-duplex)
*   **Vai trò**: Tạo kết nối vĩnh viễn giữa Browser và Server.
*   **Ứng dụng**: Khi AI nhận diện xong biển số xe, Backend sẽ chủ động "đẩy" (Push) dữ liệu lên trình duyệt ngay lập tức mà Web không cần phải hỏi.
*   **Tại sao dùng?**: Để đạt được trải nghiệm thời gian thực (Real-time dashboard).

### C. Giao thức MJPEG (Motion JPEG) over HTTP
*   **Vai trò**: Truyền tải luồng video dưới dạng các tấm ảnh JPG nối tiếp nhau.
*   **Cơ chế**: ESP32-CAM hoạt động như một Server, Backend kết nối vào URL `/stream` để nhận các frame ảnh. 
*   **Ưu điểm**: Không cần giải mã (decode) video phức tạp như H.264, giúp tiết kiệm CPU cho máy chủ để tập trung chạy AI.

### D. Giao thức Serial Communication (Dự phòng)
*   **Vai trò**: Truyền dữ liệu qua cổng USB.
*   **Ứng dụng**: Dùng trong quá trình nạp code (Upload) từ máy tính vào bo mạch hoặc khi kết nối trực tiếp Arduino vào PC.

---

## 🛡️ 3. Lưu ý cho buổi bảo vệ (Key Takeaways)

1.  **Tính đồng nhất**: Hệ thống sử dụng **JSON** làm "ngôn ngữ chung" để trao đổi dữ liệu giữa Hardware, Backend và Frontend.
2.  **Tính bảo mật**: Mọi truy vấn vào Database đều thông qua **SQL Parameterized Queries** để chống tấn công SQL Injection.
3.  **Tính mở rộng**: Kiến trúc này cho phép bạn dễ dàng thêm nhiều Camera hoặc nhiều bốt bảo vệ khác nhau mà không cần sửa lại mã nguồn lõi.

---
*Tài liệu này được biên soạn để làm căn cứ cho phần giải trình kỹ thuật trong báo cáo và slide thuyết trình.*
