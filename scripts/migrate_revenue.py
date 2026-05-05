import psycopg2
import os

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

def migrate():
    print("--- MIGRATION: REVENUE TABLE ---")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Create table doanh_thu
        # loai_phi: 'MONTHLY' (Cư dân), 'GUEST' (Vãng lai)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS doanh_thu (
                id SERIAL PRIMARY KEY,
                resident_id INTEGER REFERENCES cudan(id) ON DELETE SET NULL,
                bien_so_xe TEXT NOT NULL,
                so_tien BIGINT NOT NULL,
                ngay_thanh_toan TIMESTAMP DEFAULT NOW(),
                loai_phi TEXT NOT NULL -- 'MONTHLY', 'GUEST'
            );
        """)
        
        print("[SUCCESS] Da tao bang 'doanh_thu' thanh cong.")
        
        conn.commit()
        cur.close()
        conn.close()
        print("--- Hoan tat Migration ---")
    except Exception as e:
        print(f"[ERROR] Loi migration: {e}")

if __name__ == "__main__":
    migrate()
