-- Tạo database cho hệ thống nhận diện biển số xe chung cư
-- Database sẽ được tạo tự động bởi POSTGRES_DB trong docker-compose.yml

-- Tạo bảng Cudan (Cư dân)
CREATE TABLE IF NOT EXISTS Cudan (
    id SERIAL PRIMARY KEY,
    bien_so_xe VARCHAR(20) NOT NULL UNIQUE,
    ten_chu_xe VARCHAR(100) NOT NULL,
    so_can_ho VARCHAR(20) NOT NULL,
    ngay_dang_ky TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tạo bảng LichSuRaVao (Lịch sử ra vào)
CREATE TABLE IF NOT EXISTS LichSuRaVao (
    id SERIAL PRIMARY KEY,
    bien_so_xe VARCHAR(20) NOT NULL,
    thoi_gian TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hinh_anh VARCHAR(255),
    trang_thai VARCHAR(10) NOT NULL CHECK (trang_thai IN ('Vao', 'Ra', 'Tu choi')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Bỏ FOREIGN KEY để cho phép ghi log cả xe lạ (không có trong bảng cudan)
    -- FOREIGN KEY (bien_so_xe) REFERENCES Cudan(bien_so_xe) ON DELETE CASCADE
);

-- Tạo index để tối ưu truy vấn
CREATE INDEX idx_lich_su_bien_so ON LichSuRaVao(bien_so_xe);
CREATE INDEX idx_lich_su_thoi_gian ON LichSuRaVao(thoi_gian);
CREATE INDEX idx_cudan_bien_so ON Cudan(bien_so_xe);

-- Thêm dữ liệu mẫu (tùy chọn)
INSERT INTO Cudan (bien_so_xe, ten_chu_xe, so_can_ho) VALUES
('30A-12345', 'Nguyễn Văn A', 'A101'),
('30B-67890', 'Trần Thị B', 'B205'),
('29C-11111', 'Lê Văn C', 'C301')
ON CONFLICT (bien_so_xe) DO NOTHING;

-- Tạo comment cho các bảng
COMMENT ON TABLE Cudan IS 'Bảng lưu thông tin cư dân và biển số xe';
COMMENT ON TABLE LichSuRaVao IS 'Bảng lưu lịch sử ra vào của các xe';

COMMENT ON COLUMN Cudan.bien_so_xe IS 'Biển số xe của cư dân';
COMMENT ON COLUMN Cudan.ten_chu_xe IS 'Tên chủ xe';
COMMENT ON COLUMN Cudan.so_can_ho IS 'Số căn hộ';
COMMENT ON COLUMN Cudan.ngay_dang_ky IS 'Ngày đăng ký biển số xe';

COMMENT ON COLUMN LichSuRaVao.bien_so_xe IS 'Biển số xe';
COMMENT ON COLUMN LichSuRaVao.thoi_gian IS 'Thời gian ra/vào';
COMMENT ON COLUMN LichSuRaVao.hinh_anh IS 'Đường dẫn đến hình ảnh chụp lại';
COMMENT ON COLUMN LichSuRaVao.trang_thai IS 'Trạng thái: Vào, Ra hoặc Tu choi (xe lạ)';
