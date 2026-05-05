# Đặc tả Chức năng Phần mềm: SmartPark Web V2

Tài liệu này chi tiết hóa các tính năng mà phần Web (Frontend & Backend) sẽ cung cấp cho hệ thống quản lý bãi giữ xe thông minh đa làn.

---

## 🏗️ 1. Giao diện Giám sát (Real-time Dashboard)
- **Multi-Camera Display**: Hiển thị luồng video MJPEG từ 2 Camera ESP32-CAM (Cổng Vào & Cổng Ra).
- **Instant Recognition Results**: Hiển thị biển số xe vừa đọc được kèm ảnh cắt từ AI.
- **Access Control Status**: Báo hiệu bằng màu sắc (Xanh: Cho phép | Đỏ: Từ chối).
- **Parking Slot Counter**: Hiển thị số chỗ trống/tổng chỗ đỗ (VD: 45/50).
- **Remote Control Buttons**: 
    - Nút "Mở Cửa 1" (Cho phép xe vào thủ công).
    - Nút "Mở Cửa 2" (Cho phép xe ra thủ công).
- **WebSockets Live Logs**: Cập nhật danh sách 10 xe gần nhất ra/vào mà không cần tải lại trang.

## 👥 2. Quản lý Cư dân (Resident Management)
- **Smart Registration Flow**: Tích hợp camera chụp ảnh và tự động nhận diện biển số khi đăng ký để giảm thiểu nhập liệu thủ công.
- **RFID UID Linking**: Liên kết mã thẻ từ (đọc từ ESP8266) với hồ sơ cư dân.
- **Identity Verification**: Cơ chế kiểm tra chéo (Cross-check) đảm bảo Thẻ từ trùng khớp với Biển số xe đã đăng ký.
- **Search & Filter**: Tìm kiếm cư dân chuyên nghiệp theo nhiều tiêu chí.

## 📈 3. Quản lý Lịch sử (Logs & Reports)
- **Detailed In/Out Logs**: Ghi nhận thời gian chính xác, ảnh bằng chứng, và gate ID.
- **Excel Export**: Tính năng trích xuất dữ liệu ra file Excel (.xlsx) để phục vụ công tác báo cáo và thanh tra.
- **Auto-Calculated Duration**: Tự động tính toán thời gian xe đã đỗ trong bãi (Hữu ích cho việc tính phí sau này).

## ⚙️ 4. Hệ thống & AI Service
- **System Config Persistence**: Lưu trữ IP Camera, Sức chứa bãi xe vào file `config.json`.
- **Fuzzy Match Engine**: Thuật toán cho phép sai số 1-2 ký tự khi AI đọc biển số để tăng tỷ lệ nhận diện đúng cư dân.
- **System Health Monitor**: Hiển thị trạng thái kết nối của Camera và Phần cứng (Online/Offline).

---
*Tài liệu này được soạn thảo để làm căn cứ cho việc lập trình và kiểm thử hệ thống SmartPark V2.*
