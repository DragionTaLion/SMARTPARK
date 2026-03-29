import psycopg2

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lichsuravao (
                id SERIAL PRIMARY KEY,
                bien_so_xe VARCHAR(20) NOT NULL,
                thoi_gian TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hinh_anh VARCHAR(255),
                trang_thai VARCHAR(10) NOT NULL
            )
        """)
        
        # Tạo lại index
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lich_su_bien_so ON lichsuravao(bien_so_xe)")
        
        conn.commit()
        print("✅ Da kiem tra va sua loi bang lichsuravao!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix()
