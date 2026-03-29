import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

def check_schema():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'lichsuravao'")
        cols = cur.fetchall()
        print("Columns in lichsuravao:")
        for col in cols:
            print(f"- {col[0]} ({col[1]})")
        
        # Check if 'anh_bien_so' exists
        if not any(col[0] == 'anh_bien_so' for col in cols):
            print("\nUpdating schema: Adding 'anh_bien_so' column...")
            cur.execute("ALTER TABLE lichsuravao ADD COLUMN anh_bien_so TEXT")
            conn.commit()
            print("  ✅ Column 'anh_bien_so' added.")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
