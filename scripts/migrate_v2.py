import psycopg2
import sys

def migrate():
    conn_params = "dbname=nhan_dien_bien_so_xe user=postgres password=postgres host=localhost"
    try:
        conn = psycopg2.connect(conn_params)
        cur = conn.cursor()
        
        print("[DB-V2] Đang kiểm tra cấu hình Database...")

        # 1. Thêm cột gate_id vào bảng lichsuravao nếu chưa có
        cur.execute("""
            DO $$ 
            BEGIN 
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='lichsuravao' AND column_name='gate_id') THEN
                    ALTER TABLE lichsuravao ADD COLUMN gate_id INTEGER DEFAULT 1;
                    COMMENT ON COLUMN lichsuravao.gate_id IS 'ID của cổng (1: Vào, 2: Ra)';
                END IF;
            END $$;
        """)
        print("  ✅ Đã cập nhật cột gate_id cho bảng lichsuravao")

        # 2. Tạo bảng parking_slots để quản lý 3 ô đỗ
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parking_slots (
                id SERIAL PRIMARY KEY,
                slot_id INTEGER UNIQUE NOT NULL, -- 1, 2, 3
                slot_name VARCHAR(50),
                status BOOLEAN DEFAULT FALSE,    -- FALSE: Trống, TRUE: Có xe
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Thêm 3 ô đỗ mẫu nếu chưa có
        for i in range(1, 4):
            cur.execute("""
                INSERT INTO parking_slots (slot_id, slot_name, status)
                VALUES (%s, %s, FALSE)
                ON CONFLICT (slot_id) DO NOTHING;
            """, (i, f"Ô số {i}"))
            
        print("  ✅ Đã khởi tạo bảng parking_slots (3 ô đỗ mẫu)")

        conn.commit()
        cur.close()
        conn.close()
        print("\n[SUCCESS] Migration V2 hoàn tất thành công!")
        
    except Exception as e:
        print(f"\n[ERROR] Migration thất bại: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
