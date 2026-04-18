import psycopg2
import sys

DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

def test_db():
    print(f"Checking connection to {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"✅ Connection successful! PostgreSQL version: {version[0]}")
        
        # Check tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cur.fetchall()
        print(f"Found {len(tables)} tables: {[t[0] for t in tables]}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Connection FAILED: {e}")
        print("\nPossible solutions:")
        print("1. Ensure Docker Desktop is running.")
        print("2. Run 'docker-compose up -d' in the project directory.")
        print("3. Check if port 55432 is being used by another application.")

if __name__ == "__main__":
    test_db()
