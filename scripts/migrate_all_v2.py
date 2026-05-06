"""
scripts/migrate_all_v2.py — SmartPark Database Migration tổng hợp
==================================================================
Chạy lần lượt tất cả migration cần thiết để nâng cấp lên v2.1 Pro:
  1. Thêm cột anh_dang_ky, so_dien_thoai, da_thanh_toan, phi_thang vào cudan
  2. Thêm cột gate_id vào lichsuravao + tạo bảng parking_slots
  3. Tạo bảng doanh_thu
  4. Tạo bảng parking_slots (3 ô đỗ mẫu)

Chạy: python scripts/migrate_all_v2.py
"""

import psycopg2
import psycopg2.extras
import sys

DB_CONFIG = {
    "host": "localhost",
    "port": 54321,  # Docker container port
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


def run_migrations():
    if sys.stdout.encoding.lower() != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("\n" + "=" * 60)
    print("  SMARTPARK DB MIGRATION — v2.1 Pro")
    print("=" * 60)

    try:
        conn = get_conn()
        cur = conn.cursor()

        # ── Migration 1: Cột mở rộng cho bảng cudan ──────────────
        print("\n[1/5] Nâng cấp bảng cudan...")
        for col, defn in [
            ("anh_dang_ky",   "TEXT DEFAULT ''"),
            ("so_dien_thoai", "TEXT DEFAULT ''"),
            ("da_thanh_toan", "BOOLEAN DEFAULT FALSE"),
            ("phi_thang",     "INTEGER DEFAULT 500000"),
            ("updated_at",    "TIMESTAMP"),
        ]:
            cur.execute(f"""
                ALTER TABLE cudan ADD COLUMN IF NOT EXISTS {col} {defn}
            """)
        print("  ✅ Bảng cudan đã được nâng cấp")

        # ── Migration 2: Cột gate_id cho lichsuravao ──────────────
        print("\n[2/5] Thêm cột gate_id vào lichsuravao...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_name='lichsuravao' AND column_name='gate_id') THEN
                    ALTER TABLE lichsuravao ADD COLUMN gate_id INTEGER DEFAULT 1;
                    COMMENT ON COLUMN lichsuravao.gate_id IS 'ID cổng: 1=Vào, 2=Ra';
                    RAISE NOTICE 'Đã thêm cột gate_id';
                ELSE
                    RAISE NOTICE 'Cột gate_id đã tồn tại';
                END IF;
            END $$;
        """)
        print("  ✅ Cột gate_id đã được thêm/xác nhận")

        # ── Migration 3: Bảng parking_slots ──────────────────────
        print("\n[3/5] Tạo bảng parking_slots...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parking_slots (
                id          SERIAL PRIMARY KEY,
                slot_id     INTEGER UNIQUE NOT NULL,
                slot_name   VARCHAR(50) DEFAULT 'Ô đỗ',
                status      BOOLEAN DEFAULT FALSE,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for i in range(1, 4):
            cur.execute("""
                INSERT INTO parking_slots (slot_id, slot_name, status)
                VALUES (%s, %s, FALSE)
                ON CONFLICT (slot_id) DO NOTHING
            """, (i, f"Ô số {i}"))
        print("  ✅ Bảng parking_slots đã tạo (3 ô đỗ mẫu)")

        # ── Migration 4: Bảng doanh_thu ──────────────────────────
        print("\n[4/5] Tạo bảng doanh_thu...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS doanh_thu (
                id              SERIAL PRIMARY KEY,
                resident_id     INTEGER REFERENCES cudan(id) ON DELETE SET NULL,
                bien_so_xe      TEXT NOT NULL,
                so_tien         BIGINT NOT NULL DEFAULT 0,
                loai_phi        TEXT DEFAULT 'MONTHLY',
                ngay_thanh_toan TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        print("  ✅ Bảng doanh_thu đã tạo")

        # ── Migration 5: Index tối ưu hoá ────────────────────────
        print("\n[5/5] Tạo index tối ưu...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_lichsuravao_thoi_gian ON lichsuravao(thoi_gian DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_lichsuravao_bien_so ON lichsuravao(bien_so_xe)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_doanh_thu_ngay ON doanh_thu(ngay_thanh_toan DESC)
        """)
        print("  ✅ Index đã tạo")

        conn.commit()
        cur.close()
        conn.close()

        print("\n" + "=" * 60)
        print("  ✅ MIGRATION HOÀN TẤT THÀNH CÔNG!")
        print("=" * 60 + "\n")

    except psycopg2.OperationalError as e:
        print(f"\n  ❌ Không thể kết nối Database: {e}")
        print("  → Đảm bảo Docker container đang chạy: docker-compose up -d")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ❌ Migration thất bại: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_migrations()
