import psycopg2
import sys
import io

# Fix encoding for Windows console (emojis in prints)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

def fix():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Tạo bảng lịch sử nếu thiếu
        print("Checking/Creating table 'lichsuravao'...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lichsuravao (
                id SERIAL PRIMARY KEY,
                bien_so_xe VARCHAR(20) NOT NULL,
                thoi_gian TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                anh_bien_so TEXT, -- Base64 image
                trang_thai VARCHAR(10) NOT NULL
            )
        """)
        
        # Kiểm tra nếu cột 'anh_bien_so' tồn tại, nếu chưa có thì đổi tên từ 'hinh_anh' hoặc thêm mới
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='lichsuravao'")
        columns = [r[0] for r in cur.fetchall()]
        
        if 'hinh_anh' in columns and 'anh_bien_so' not in columns:
            print("Renaming column 'hinh_anh' to 'anh_bien_so'...")
            cur.execute("ALTER TABLE lichsuravao RENAME COLUMN hinh_anh TO anh_bien_so")
            cur.execute("ALTER TABLE lichsuravao ALTER COLUMN anh_bien_so TYPE TEXT")
        elif 'anh_bien_so' not in columns:
            print("Adding missing column 'anh_bien_so'...")
            cur.execute("ALTER TABLE lichsuravao ADD COLUMN anh_bien_so TEXT")

        # Tạo lại index
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lich_su_bien_so ON lichsuravao(bien_so_xe)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lich_su_thoi_gian ON lichsuravao(thoi_gian)")
        
        conn.commit()
        print("✅ Đã kiểm tra và sửa lỗi bảng 'lichsuravao'!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix()
