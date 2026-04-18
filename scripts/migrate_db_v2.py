import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

def migrate():
    print("Starting database migration: adding 'anh_dang_ky' to 'Cudan'...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Check if column exists
        cur.execute("""
            SELECT count(*) 
            FROM information_schema.columns 
            WHERE table_name='cudan' AND column_name='anh_dang_ky'
        """)
        exists = cur.fetchone()[0]
        
        if not exists:
            cur.execute("ALTER TABLE Cudan ADD COLUMN anh_dang_ky TEXT;")
            print("✅ Column 'anh_dang_ky' added successfully.")
        else:
            print("ℹ️ Column 'anh_dang_ky' already exists.")
            
        conn.commit()
        cur.close()
        conn.close()
        print("Database migration completed.")
    except Exception as e:
        print(f"❌ Migration FAILED: {e}")

if __name__ == "__main__":
    migrate()
