import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host": "localhost",
    "port": 54321,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

def check():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check total logs
        cur.execute("SELECT COUNT(*) as count FROM lichsuravao")
        print(f"Total logs: {cur.fetchone()['count']}")
        
        # Check logs for today
        cur.execute("SELECT COUNT(*) as count FROM lichsuravao WHERE DATE(thoi_gian) = CURRENT_DATE")
        print(f"Today's logs: {cur.fetchone()['count']}")
        
        # Check breakdown for today
        cur.execute("SELECT trang_thai, COUNT(*) as count FROM lichsuravao WHERE DATE(thoi_gian) = CURRENT_DATE GROUP BY trang_thai")
        print("Today's breakdown:")
        for row in cur.fetchall():
            print(f"  {row['trang_thai']}: {row['count']}")
            
        # Check residents
        cur.execute("SELECT COUNT(*) as count FROM cudan")
        print(f"Total residents: {cur.fetchone()['count']}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
