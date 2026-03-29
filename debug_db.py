import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

def debug():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("--- Checking Tables ---")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables: {tables}")
        
        if "lichsuravao" in tables:
            print("\n--- Recent History ---")
            cur.execute("SELECT bien_so_xe, thoi_gian, trang_thai FROM lichsuravao ORDER BY thoi_gian DESC LIMIT 5")
            for row in cur.fetchall():
                print(row)
        else:
            print("\n❌ Table 'lichsuravao' MISSION!")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug()
