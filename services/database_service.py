"""
services/database_service.py — Database Operations Service v4.0
================================================================
Tách biệt toàn bộ logic DB khỏi API layer.
Cung cấp các hàm CRUD chuyên biệt cho hệ thống ALPR.

Thay đổi v4.0:
  - ThreadedConnectionPool (minconn=2, maxconn=10) thay thế per-query connection
  - Fuzzy threshold: 0.82 → 0.85 (chặt hơn, giảm false positive)
  - Context manager get_conn() tự động trả về pool sau khi dùng
"""

import difflib
import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger("database_service")

# ─── Config ───────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 55432,
    "dbname": "nhan_dien_bien_so_xe",
    "user": "postgres",
    "password": "postgres",
}

# ─── Connection Pool (v4.0) ───────────────────────────────────────────────────
# ThreadedConnectionPool an toàn khi dùng từ nhiều thread đồng thời
# minconn=2: luôn giữ sẵn 2 kết nối
# maxconn=10: tối đa 10 kết nối đồng thời (đủ cho ~10 xe vào cùng lúc)

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Khởi tạo pool lần đầu (lazy init), tái sử dụng pool ở các lần sau."""
    global _pool
    if _pool is None or _pool.closed:
        logger.info("[DB] Khởi tạo connection pool (min=2, max=10)...")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            cursor_factory=psycopg2.extras.RealDictCursor,
            **DB_CONFIG,
        )
        logger.info("[DB] ✅ Connection pool sẵn sàng")
    return _pool


@contextmanager
def get_conn():
    """
    Context manager lấy connection từ pool.
    Tự động:
      - Lấy conn từ pool khi vào block
      - commit nếu thành công
      - rollback nếu có exception
      - Trả conn về pool khi thoát (kể cả khi có lỗi)

    Dùng như:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def check_connection() -> tuple:
    """Kiểm tra trạng thái kết nối DB. Returns (ok, error_message)."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True, ""
    except Exception as e:
        return False, str(e)


# ─── Plate Normalization ──────────────────────────────────────────────────────

def normalize_plate(raw: str) -> str:
    """Chuẩn hóa biển số: IN HOA, bỏ ký tự đặc biệt."""
    s = (raw or "").strip().upper()
    for ch in [" ", ".", "-", "_"]:
        s = s.replace(ch, "")
    return s


# ─── Resident Operations ──────────────────────────────────────────────────────

def find_resident_exact(plate: str) -> Optional[dict]:
    """
    Tìm cư dân theo biển số (so khớp chính xác, sau chuẩn hóa).
    Returns dict {ten_chu_xe, so_can_ho, bien_so_xe} hoặc None.
    """
    norm = normalize_plate(plate)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ten_chu_xe, so_can_ho, bien_so_xe
                    FROM cudan
                    WHERE REPLACE(REPLACE(REPLACE(UPPER(bien_so_xe),' ',''),'-',''),'.','') = %s
                    """,
                    (norm,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.error(f"[DB] find_resident_exact error: {e}")
        return None


def find_resident_fuzzy(
    plate: str,
    threshold: float = 0.85,  # v4.0: tăng từ 0.82 → 0.85
) -> Optional[tuple]:
    """
    Fuzzy matching để bù lỗi OCR (~85% similarity).
    Threshold 0.85 (v4.0): chặt hơn 0.82 để giảm false positive.

    Returns (resident_dict, matched_plate, ratio) hoặc (None, None, 0).
    """
    norm_det = normalize_plate(plate)
    best_ratio, best_resident, best_plate = 0.0, None, None

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bien_so_xe, ten_chu_xe, so_can_ho FROM cudan")
                rows = cur.fetchall()
                for row in rows:
                    norm_r = normalize_plate(row["bien_so_xe"])
                    ratio = difflib.SequenceMatcher(None, norm_det, norm_r).ratio()
                    if ratio > threshold and ratio > best_ratio:
                        best_ratio = ratio
                        best_resident = dict(row)
                        best_plate = row["bien_so_xe"]
    except Exception as e:
        logger.error(f"[DB] find_resident_fuzzy error: {e}")

    if best_resident:
        logger.info(
            f"[DB] Fuzzy match: '{plate}' → '{best_plate}' (ratio={best_ratio:.2%})"
        )

    return best_resident, best_plate, best_ratio


def get_all_residents() -> list:
    """Lấy toàn bộ danh sách cư dân."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, bien_so_xe, ten_chu_xe, so_can_ho FROM cudan ORDER BY ten_chu_xe"
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"[DB] get_all_residents error: {e}")
        return []


def add_resident(bien_so_xe: str, ten_chu_xe: str, so_can_ho: str = "") -> dict:
    """Thêm cư dân mới. Raises ValueError nếu biển số đã tồn tại."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO cudan (bien_so_xe, ten_chu_xe, so_can_ho) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (bien_so_xe.upper(), ten_chu_xe, so_can_ho),
                )
                new_id = cur.fetchone()["id"]
                return {"success": True, "id": new_id}
    except psycopg2.errors.UniqueViolation:
        raise ValueError(f"Biển số {bien_so_xe} đã tồn tại")
    except Exception as e:
        logger.error(f"[DB] add_resident error: {e}")
        raise


def remove_resident(resident_id: int) -> str:
    """Xóa cư dân theo ID. Raises ValueError nếu không tìm thấy."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cudan WHERE id=%s RETURNING ten_chu_xe",
                    (resident_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Không tìm thấy cư dân")
                return row["ten_chu_xe"]
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"[DB] remove_resident error: {e}")
        raise


# ─── History Operations ───────────────────────────────────────────────────────

def insert_history(
    plate: str, trang_thai: str, img_base64: Optional[str] = None
) -> None:
    """Ghi lịch sử xe ra vào kèm ảnh biển số."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lichsuravao (bien_so_xe, thoi_gian, trang_thai, anh_bien_so)
                    VALUES (%s, NOW(), %s, %s)
                    """,
                    (normalize_plate(plate), trang_thai, img_base64),
                )
        logger.info(f"[DB] Ghi lịch sử: {plate} — {trang_thai}")
    except Exception as e:
        logger.error(f"[DB] insert_history error: {e}")


def get_history(limit: int = 50, status: str = "all", date: str = "all") -> list:
    """Lấy lịch sử xe ra vào với filter."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                conditions, params = [], []
                if status != "all":
                    conditions.append("trang_thai = %s")
                    params.append(status)
                if date == "today":
                    conditions.append("DATE(thoi_gian) = CURRENT_DATE")
                elif date == "week":
                    conditions.append("thoi_gian >= NOW() - INTERVAL '7 days'")
                where = "WHERE " + " AND ".join(conditions) if conditions else ""
                cur.execute(
                    f"""
                    SELECT id, bien_so_xe, thoi_gian, trang_thai, anh_bien_so as hinh_anh
                    FROM lichsuravao {where}
                    ORDER BY thoi_gian DESC LIMIT %s
                    """,
                    params + [limit],
                )
                result = []
                for row in cur.fetchall():
                    r = dict(row)
                    if r.get("thoi_gian"):
                        r["thoi_gian"] = r["thoi_gian"].isoformat()
                    result.append(r)
                return result
    except Exception as e:
        logger.error(f"[DB] get_history error: {e}")
        raise


def get_stats() -> dict:
    """Thống kê: xe trong bãi, lượt vào/ra/từ chối hôm nay."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao "
                    "WHERE trang_thai='Vao' AND DATE(thoi_gian)=CURRENT_DATE"
                )
                entries = cur.fetchone()["cnt"]
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao "
                    "WHERE trang_thai='Ra' AND DATE(thoi_gian)=CURRENT_DATE"
                )
                exits = cur.fetchone()["cnt"]
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM lichsuravao "
                    "WHERE trang_thai='Tu choi' AND DATE(thoi_gian)=CURRENT_DATE"
                )
                strangers = cur.fetchone()["cnt"]
                return {
                    "inside": max(0, entries - exits),
                    "entries_today": entries,
                    "exits_today": exits,
                    "strangers_today": strangers,
                }
    except Exception as e:
        logger.error(f"[DB] get_stats error: {e}")
        raise
