import psycopg2
import sys
import io

# Config
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

# Fix encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

def add_plates():
    plates_to_add = [
        ("99-E1 222.68", "Nguyen Van A", "E1-201"),
        ("30E 777.96", "Tran Thi B", "E7-707"),
        ("75-MDD1 000.19", "Le Van C", "D1-101")
    ]
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        for plate, name, room in plates_to_add:
            try:
                cur.execute(
                    "INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho) VALUES (%s, %s, %s)",
                    (plate, name, room)
                )
                print(f"✅ Da them bien so: {plate}")
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                print(f"⚠️  Bien so {plate} da ton tai trong DB")
                cur = conn.cursor()
            except Exception as e:
                conn.rollback()
                print(f"❌ Loi khi them {plate}: {e}")
                cur = conn.cursor()
        
        conn.commit()
        cur.close()
        conn.close()
        print("\nHoan thanh cap nhat database!")
        
    except Exception as e:
        print(f"❌ Khong the ket noi database: {e}")

if __name__ == "__main__":
    add_plates()
