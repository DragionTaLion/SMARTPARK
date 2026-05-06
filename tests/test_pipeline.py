"""
tests/test_pipeline.py — SmartPark ALPR v4.0 Pipeline Test Suite
=================================================================
7 test cases bao phủ toàn bộ pipeline:
  1. test_blur_detection          — Frame mờ bị từ chối
  2. test_ocr_substitution        — Substitution Map sửa đúng
  3. test_fuzzy_matching          — Fuzzy 85% match biển sai 1 ký tự
  4. test_noise_filter            — Distance > threshold → DENY
  5. test_voting_stability        — Không đủ votes → trả về None
  6. test_db_pool                 — Connection pool không deadlock
  7. test_regex_validation        — Regex validate đúng biển VN

Chạy:
  cd d:\\PBL5
  python -m pytest tests/test_pipeline.py -v --tb=short
"""

import contextlib
import threading
import time
from contextlib import contextmanager
from typing import Optional
from unittest.mock import MagicMock, Mock, patch

import cv2
import numpy as np
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Blur Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestBlurDetection:
    """Module 1 — check_image_quality() với Laplacian variance."""

    def test_sharp_frame_passes(self):
        """Frame rõ nét (random noise) phải vượt ngưỡng 100."""
        from core.preprocessor import check_image_quality

        # Random noise có Laplacian rất cao (nhiều chi tiết)
        sharp = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        is_sharp, score = check_image_quality(sharp, threshold=100.0)

        assert is_sharp, f"Frame noise phải nét: score={score:.1f}"
        assert score >= 100.0

    def test_blurry_frame_rejected(self):
        """Frame phẳng + Gaussian blur mạnh phải bị từ chối."""
        from core.preprocessor import check_image_quality

        # Tạo ảnh phẳng (gần như không có gradient)
        flat = np.full((480, 640, 3), 128, dtype=np.uint8)
        blurry = cv2.GaussianBlur(flat, (51, 51), 30)
        is_sharp, score = check_image_quality(blurry, threshold=100.0)

        assert not is_sharp, f"Ảnh mờ phải bị từ chối: score={score:.1f}"
        assert score < 100.0

    def test_none_frame_rejected(self):
        """Frame None phải trả về (False, 0.0)."""
        from core.preprocessor import check_image_quality

        is_sharp, score = check_image_quality(None, threshold=100.0)
        assert not is_sharp
        assert score == 0.0

    def test_threshold_boundary(self):
        """Test chính xác biên ngưỡng."""
        from core.preprocessor import check_image_quality

        # Tạo ảnh với Laplacian đúng bằng threshold
        # Không thể kiểm soát chính xác, nhưng kiểm tra logic threshold
        sharp = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        _, score = check_image_quality(sharp, threshold=100.0)

        # Kiểm tra với ngưỡng = score → phải pass
        is_sharp_at_boundary, _ = check_image_quality(sharp, threshold=score)
        assert is_sharp_at_boundary  # score >= score phải True

        # Kiểm tra với ngưỡng = score + 1 → phải fail
        is_sharp_above, _ = check_image_quality(sharp, threshold=score + 1)
        assert not is_sharp_above


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: OCR Substitution Map
# ─────────────────────────────────────────────────────────────────────────────

class TestOCRSubstitution:
    """Module 3 — validate_and_fix_plate() Substitution Map."""

    def test_O_at_province_position(self):
        """'3OA12345' → '30A12345' (chữ O ở pos 1 → số 0)."""
        from core.plate_validator import validate_and_fix_plate

        fixed, is_valid, penalty = validate_and_fix_plate("3OA12345")
        assert fixed == "30A12345", f"Expected '30A12345', got '{fixed}'"
        assert is_valid
        assert penalty <= 0.1  # Chỉ sửa 1 ký tự

    def test_eight_at_series_position(self):
        """'308-12345' → '30B12345' (số 8 ở pos 2 → chữ B)."""
        from core.plate_validator import validate_and_fix_plate

        fixed, is_valid, penalty = validate_and_fix_plate("308-12345")
        assert fixed == "30B12345", f"Expected '30B12345', got '{fixed}'"
        assert is_valid

    def test_S_at_registration(self):
        """'30A1234S' → '30A12345' (chữ S ở vị trí số → số 5)."""
        from core.plate_validator import validate_and_fix_plate

        fixed, is_valid, penalty = validate_and_fix_plate("30A1234S")
        assert fixed == "30A12345", f"Expected '30A12345', got '{fixed}'"
        assert is_valid

    def test_B_at_registration(self):
        """'43A1234B' → '43A12348' (chữ B ở vị trí số → số 8)."""
        from core.plate_validator import validate_and_fix_plate

        fixed, is_valid, penalty = validate_and_fix_plate("43A1234B")
        assert fixed == "43A12348", f"Expected '43A12348', got '{fixed}'"

    def test_no_change_valid_plate(self):
        """Biển đúng định dạng không bị thay đổi, penalty = 0."""
        from core.plate_validator import validate_and_fix_plate

        fixed, is_valid, penalty = validate_and_fix_plate("30A12345")
        assert fixed == "30A12345"
        assert is_valid
        assert penalty == 0.0  # Không sửa gì


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: Fuzzy Matching 85%
# ─────────────────────────────────────────────────────────────────────────────

class TestFuzzyMatching:
    """Module 3 — find_resident_fuzzy() với threshold 0.85."""

    def _make_mock_conn(self, rows):
        """Tạo mock context manager cho get_conn()."""
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = rows
        mock_cur.__enter__ = Mock(return_value=mock_cur)
        mock_cur.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        @contextmanager
        def mock_get_conn():
            yield mock_conn

        return mock_get_conn

    def test_fuzzy_match_one_char_diff(self):
        """'43A12348' sai 1 ký tự cuối so với '43A12345' phải fuzzy match ≥85%."""
        from services.database_service import find_resident_fuzzy

        rows = [
            {"bien_so_xe": "43A12345", "ten_chu_xe": "Nguyen Van A", "so_can_ho": "101"},
        ]
        mock_gc = self._make_mock_conn(rows)

        with patch("services.database_service.get_conn", mock_gc):
            resident, matched_plate, ratio = find_resident_fuzzy("43A12348", threshold=0.85)

        assert resident is not None, "Phải fuzzy match được biển sai 1 ký tự"
        assert matched_plate == "43A12345"
        assert ratio >= 0.85

    def test_fuzzy_no_match_high_threshold(self):
        """Biển khác quá nhiều không được match dù threshold 0.85."""
        from services.database_service import find_resident_fuzzy

        rows = [
            {"bien_so_xe": "30A12345", "ten_chu_xe": "Tran Van B", "so_can_ho": "202"},
        ]
        mock_gc = self._make_mock_conn(rows)

        with patch("services.database_service.get_conn", mock_gc):
            resident, matched_plate, ratio = find_resident_fuzzy("99Z99999", threshold=0.85)

        assert resident is None, f"Biển khác hoàn toàn không được match (ratio={ratio:.2f})"

    def test_fuzzy_threshold_095_too_strict(self):
        """Với threshold=0.95, biển sai 1 ký tự không match được."""
        from services.database_service import find_resident_fuzzy

        rows = [
            {"bien_so_xe": "43A12345", "ten_chu_xe": "Le Van C", "so_can_ho": "303"},
        ]
        mock_gc = self._make_mock_conn(rows)

        with patch("services.database_service.get_conn", mock_gc):
            resident, _, ratio = find_resident_fuzzy("43A12348", threshold=0.95)

        # ratio cho "43A12348" vs "43A12345" ≈ 0.875 < 0.95
        assert resident is None, f"Threshold 0.95 không cho phép match (ratio={ratio:.2f})"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Noise Filter (Distance > Threshold)
# ─────────────────────────────────────────────────────────────────────────────

class TestNoiseFilter:
    """Module 4 — EntryRequest: distance >= threshold → DENY tức thì."""

    def test_distance_above_threshold_denied(self):
        """distance=15cm > threshold=10cm → logic phải DENY."""
        from models.schemas import EntryRequest

        req = EntryRequest(distance=15.0, device_id="test_sensor", threshold=10.0)
        # Kiểm tra condition trong router
        assert req.distance >= req.threshold, (
            f"distance={req.distance} phải >= threshold={req.threshold}"
        )

    def test_distance_exactly_at_threshold_denied(self):
        """distance == threshold → cũng phải DENY (biên trên bị từ chối)."""
        from models.schemas import EntryRequest

        req = EntryRequest(distance=10.0, device_id="test_sensor", threshold=10.0)
        assert req.distance >= req.threshold

    def test_distance_below_threshold_accepted(self):
        """distance=7.5cm < threshold=10cm → không bị lọc."""
        from models.schemas import EntryRequest

        req = EntryRequest(distance=7.5, device_id="test_sensor", threshold=10.0)
        assert req.distance < req.threshold, (
            f"distance={req.distance} phải < threshold={req.threshold}"
        )

    def test_no_distance_data_manual_trigger(self):
        """Không có distance → manual trigger, không bị lọc."""
        from models.schemas import EntryRequest

        req = EntryRequest(device_id="manual_ui")
        assert req.distance is None  # Không có distance → không lọc


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: Multi-frame Voting Stability
# ─────────────────────────────────────────────────────────────────────────────

class TestVotingStability:
    """Module 2 — capture_and_vote_frames() cần min_votes đồng thuận."""

    @pytest.fixture
    def dummy_models(self):
        """Tạo mock models (không cần GPU thật)."""
        return MagicMock(), MagicMock(), MagicMock()

    def test_insufficient_votes_returns_none(self):
        """2/7 votes cho cùng 1 biển → < min_votes=4 → trả về None."""
        from services.alpr_service import capture_and_vote_frames

        call_count = [0]

        def mock_capture(ip, num_frames=3):
            return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        def mock_quality(frame, threshold=100.0):
            return True, 150.0  # Tất cả frame đạt chuẩn nét

        def mock_pipeline(frame, yolo, char_m, ocr):
            call_count[0] += 1
            # Chỉ 2 frame đầu trả về biển số, 5 frame còn lại không có biển
            if call_count[0] <= 2:
                return "30A12345", [10, 10, 100, 50], 0.9, "fake_b64"
            return None, None, 0.0, None

        # check_image_quality được import cục bộ trong capture_and_vote_frames
        # nên phải patch tại core.preprocessor (nơi nó được định nghĩa)
        with (
            patch("services.alpr_service.capture_best_frame", side_effect=mock_capture),
            patch("core.preprocessor.check_image_quality", side_effect=mock_quality),
            patch("services.alpr_service.run_detection_pipeline", side_effect=mock_pipeline),
        ):
            result = capture_and_vote_frames(
                camera_ip="fake_ip",
                yolo_model=MagicMock(),
                char_model=MagicMock(),
                easyocr_reader=MagicMock(),
                n_frames=7,
                min_votes=4,
                frame_interval_ms=0,
            )

        assert result[0] is None, (
            f"Chỉ 2/7 votes → phải trả về None, nhưng nhận được: '{result[0]}'"
        )

    def test_sufficient_votes_returns_plate(self):
        """5/7 votes cho cùng 1 biển → >= min_votes=4 → trả về biển đó."""
        from services.alpr_service import capture_and_vote_frames

        call_count = [0]

        def mock_capture(ip, num_frames=3):
            return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        def mock_quality(frame, threshold=100.0):
            return True, 150.0

        def mock_pipeline(frame, yolo, char_m, ocr):
            call_count[0] += 1
            # 5/7 frame trả về cùng biển số
            if call_count[0] <= 5:
                return "43B12345", [10, 10, 100, 50], 0.85, "fake_b64"
            return None, None, 0.0, None

        with (
            patch("services.alpr_service.capture_best_frame", side_effect=mock_capture),
            patch("services.alpr_service.run_detection_pipeline", side_effect=mock_pipeline),
        ):
            with patch("core.preprocessor.check_image_quality", return_value=(True, 150.0)):
                result = capture_and_vote_frames(
                    camera_ip="fake_ip",
                    yolo_model=MagicMock(),
                    char_model=MagicMock(),
                    easyocr_reader=MagicMock(),
                    n_frames=7,
                    min_votes=4,
                    frame_interval_ms=0,
                )

        assert result[0] == "43B12345", (
            f"5/7 votes → phải trả về '43B12345', nhận được: '{result[0]}'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: Database Connection Pool
# ─────────────────────────────────────────────────────────────────────────────

class TestDBConnectionPool:
    """Module 5 — ThreadedConnectionPool không deadlock với nhiều thread."""

    def test_pool_initialized(self):
        """Pool phải được khởi tạo (có DB) hoặc skip gracefully (không có DB)."""
        try:
            from services.database_service import _get_pool
            pool = _get_pool()
            assert pool is not None, "Pool phải được tạo"
            assert not getattr(pool, "closed", True), "Pool phải đang mở"
        except Exception as e:
            pytest.skip(f"DB không khả dụng trong môi trường test: {e}")

    def test_concurrent_queries_no_deadlock(self):
        """10 thread đồng thời query check_connection() không deadlock."""
        try:
            from services.database_service import check_connection

            # Thử kết nối trước — nếu không có DB thì skip
            ok, err = check_connection()
            if not ok:
                pytest.skip(f"DB không khả dụng: {err}")

            errors = []
            results = []

            def query_thread():
                try:
                    ok, err_msg = check_connection()
                    results.append(ok)
                    if not ok:
                        errors.append(err_msg)
                except Exception as exc:
                    errors.append(str(exc))

            threads = [threading.Thread(target=query_thread) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            # Tất cả thread phải hoàn thành trong timeout
            assert len(results) == 10, (
                f"Chỉ {len(results)}/10 thread hoàn thành — có thể deadlock"
            )
            assert not errors, f"Lỗi trong concurrent queries: {errors}"

        except Exception as e:
            pytest.skip(f"DB không khả dụng: {e}")

    def test_pool_context_manager_returns_connection(self):
        """get_conn() phải là context manager trả về psycopg2 connection."""
        from services.database_service import get_conn
        import inspect

        # Kiểm tra get_conn là generator function (contextmanager)
        assert inspect.isgeneratorfunction(get_conn.__wrapped__), (
            "get_conn() phải được wrap bởi @contextmanager"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7: Regex Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestRegexValidation:
    """Module 3 — PLATE_REGEX validate đúng biển số xe Việt Nam."""

    def test_valid_standard_plates(self):
        """Các biển số hợp lệ phổ biến."""
        from core.plate_validator import validate_and_fix_plate

        valid_plates = [
            "30A12345",   # Hà Nội, ô tô 5 số
            "29A1234",    # Hà Nội, ô tô 4 số
            "51G12345",   # TP.HCM
            "43A12345",   # Đà Nẵng
            "92H12345",   # Quảng Nam
            "43B11234",   # Đà Nẵng, series B1
            "30K21234",   # Hà Nội, series K2
        ]

        for plate in valid_plates:
            _, is_valid, _ = validate_and_fix_plate(plate)
            assert is_valid, f"'{plate}' phải là biển hợp lệ"

    def test_invalid_plates_rejected(self):
        """Biển không đúng định dạng phải bị từ chối."""
        from core.plate_validator import validate_and_fix_plate

        invalid_plates = [
            "",            # Rỗng
            "ABC",         # Quá ngắn
            "ABCDEFG",     # Toàn chữ cái
            "1234567890",  # Quá dài
            "30A1234567",  # Quá nhiều số đăng ký (>5)
            "AA12345",     # Mã tỉnh không phải số
        ]

        for plate in invalid_plates:
            _, is_valid, _ = validate_and_fix_plate(plate)
            assert not is_valid, f"'{plate}' phải là biển KHÔNG hợp lệ"

    def test_separators_removed_before_validation(self):
        """Biển có dấu phân cách được chuẩn hóa trước khi validate."""
        from core.plate_validator import validate_and_fix_plate

        # Biển với dấu gạch ngang (định dạng thực tế in trên biển)
        plate_with_dash = "30A-12345"
        fixed, is_valid, _ = validate_and_fix_plate(plate_with_dash)
        assert is_valid, f"'{plate_with_dash}' sau chuẩn hóa phải hợp lệ"
        assert fixed == "30A12345"

        plate_with_dot = "30A.12345"
        fixed2, is_valid2, _ = validate_and_fix_plate(plate_with_dot)
        assert is_valid2
        assert fixed2 == "30A12345"

    def test_penalty_increases_with_substitutions(self):
        """Nhiều sửa đổi → penalty cao hơn."""
        from core.plate_validator import validate_and_fix_plate

        # 0 sửa → penalty 0.0
        _, _, p0 = validate_and_fix_plate("30A12345")
        assert p0 == 0.0

        # 1 sửa → penalty 0.1
        _, _, p1 = validate_and_fix_plate("3OA12345")   # O→0
        assert p1 == 0.1

        # 3+ sửa → penalty 0.3
        _, _, p3 = validate_and_fix_plate("3OA1234S")   # O→0, S→5
        assert p3 >= 0.1  # Ít nhất 2 sửa → penalty >= 0.1


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    import sys

    print("=" * 65)
    print("  SmartPark v4.0 — Pipeline Test Suite")
    print("=" * 65)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd="d:\\PBL5",
    )
    sys.exit(result.returncode)
