"""
core/plate_validator.py — Vietnamese License Plate Validator
=============================================================
Post-processing module cho kết quả OCR biển số Việt Nam:
  1. Substitution Map: sửa lỗi nhầm lẫn OCR dựa theo VỊ TRÍ ký tự
  2. Regex validation: ép về đúng định dạng biển số xe VN
  3. validate_and_fix_plate: pipeline đầy đủ trả về (fixed, is_valid, penalty)

Định dạng biển số Việt Nam (chuẩn hóa, không dấu phân cách):
  Ô tô 1 dòng : [2 số tỉnh] [1 chữ series] [4-5 số đăng ký]
                VD: 30A12345, 51G9999, 43A123456
  Xe máy 2 dòng: [2 số tỉnh] [1 chữ + 1 số series] [4-5 số đăng ký]
                VD: 43B11234, 30K21234

Logic Substitution theo vị trí:
  pos 0,1  → Mã tỉnh      → PHẢI là chữ số  → dùng DIGIT_SUBS
  pos 2    → Series chữ   → PHẢI là chữ cái → dùng LETTER_SUBS
  pos 3    → Series số    → Nếu tổng dài 9 ký tự → có thể là số phụ series
  pos 3+   → Số đăng ký   → PHẢI là chữ số  → dùng DIGIT_SUBS
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("core.plate_validator")

# ─── Substitution Maps ───────────────────────────────────────────────────────

# Vị trí phải là CHỮ SỐ (mã tỉnh pos 0,1 và số đăng ký pos 3+)
# OCR hay đọc nhầm chữ cái trông giống số:
DIGIT_SUBS: dict = {
    "O": "0",   # chữ O → số 0  (hay gặp nhất)
    "D": "0",   # chữ D → số 0
    "Q": "0",   # chữ Q → số 0
    "I": "1",   # chữ I → số 1
    "L": "1",   # chữ L → số 1
    "Z": "2",   # chữ Z → số 2
    "S": "5",   # chữ S → số 5
    "G": "6",   # chữ G → số 6  (hay gặp)
    "B": "8",   # chữ B → số 8  (hay gặp nhất)
    "P": "8",   # chữ P → số 8 (ít gặp)
    "T": "7",   # chữ T → số 7 (ít gặp)
}

# Vị trí phải là CHỮ CÁI (series, pos 2)
# OCR hay đọc nhầm số trông giống chữ:
LETTER_SUBS: dict = {
    "0": "O",   # số 0 → chữ O
    "1": "I",   # số 1 → chữ I  (hoặc L)
    "2": "Z",   # số 2 → chữ Z
    "5": "S",   # số 5 → chữ S
    "6": "G",   # số 6 → chữ G
    "8": "B",   # số 8 → chữ B
}

# ─── Regex Pattern ────────────────────────────────────────────────────────────
# Sau khi chuẩn hóa (không có dấu phân cách):
#   \d{2}       = 2 chữ số mã tỉnh (11..99)
#   [A-Z]       = 1 chữ cái series
#   [0-9]?      = 1 chữ số series tùy chọn (vd: B1, K2)
#   \d{4,5}     = 4 hoặc 5 chữ số đăng ký
PLATE_REGEX = re.compile(r"^(\d{2})([A-Z])([0-9]?)(\d{4,5})$")

# Mã tỉnh hợp lệ của Việt Nam (kiểm tra thêm nếu cần)
VALID_PROVINCE_CODES = {
    "11", "12", "14", "15", "17", "18", "19", "20", "21", "22",
    "23", "24", "25", "26", "27", "28", "29", "30", "31", "32",
    "33", "34", "36", "37", "38", "40", "42", "43", "47", "48",
    "49", "50", "51", "52", "53", "54", "55", "56", "57", "58",
    "59", "60", "61", "62", "63", "64", "65", "66", "67", "68",
    "69", "70", "71", "72", "73", "74", "75", "76", "77", "78",
    "79", "80", "81", "82", "83", "84", "85", "86", "88", "89",
    "90", "92", "93", "94", "95", "97", "98", "99",
}


# ─── Normalize ────────────────────────────────────────────────────────────────

def normalize_raw(raw: str) -> str:
    """Chuẩn hóa biển số thô: IN HOA, bỏ dấu phân cách."""
    s = (raw or "").strip().upper()
    for ch in [" ", ".", "-", "_", "/", "\\"]:
        s = s.replace(ch, "")
    return s


# ─── Core Validator ──────────────────────────────────────────────────────────

def validate_and_fix_plate(raw_text: str) -> Tuple[str, bool, float]:
    """
    Áp dụng Substitution Map + Regex để sửa lỗi OCR và xác thực biển số VN.

    Pipeline:
      1. Chuẩn hóa (normalize_raw)
      2. Kiểm tra độ dài hợp lệ (6–9 ký tự)
      3. Áp dụng Substitution theo vị trí:
           pos 0,1 → DIGIT_SUBS (mã tỉnh phải là số)
           pos 2   → LETTER_SUBS (series phải là chữ)
           pos 3+  → DIGIT_SUBS (số đăng ký phải là số)
      4. Regex validation
      5. Tính confidence penalty dựa trên số lần sửa

    Args:
        raw_text: Biển số thô từ OCR/CNN (vd: "3OA1234S", "43B-1234")

    Returns:
        (fixed_text, is_valid, confidence_penalty)
          - fixed_text        : biển sau khi sửa
          - is_valid          : True nếu đúng định dạng biển VN
          - confidence_penalty: 0.0 (không sửa) / 0.1 (sửa ≤2 ký tự) / 0.3 (sửa nhiều)
    """
    if not raw_text:
        return "", False, 1.0

    text = normalize_raw(raw_text)

    # Kiểm tra độ dài (biển ngắn nhất "29A1234" = 7 ký tự sau chuẩn hóa)
    if len(text) < 6 or len(text) > 9:
        logger.debug(f"[VALIDATE] Độ dài {len(text)} không hợp lệ: '{text}'")
        return text, False, 0.5

    chars = list(text)
    n_changes = 0

    # ── Bước 1: Vị trí 0, 1 — Mã tỉnh (phải là chữ số) ─────────────────────
    for i in [0, 1]:
        if i < len(chars) and not chars[i].isdigit():
            original = chars[i]
            chars[i] = DIGIT_SUBS.get(chars[i], chars[i])
            if chars[i] != original:
                n_changes += 1
                logger.debug(f"[VALIDATE] pos{i}: '{original}' → '{chars[i]}' (digit_sub)")

    # ── Bước 2: Vị trí 2 — Series letter (phải là chữ cái) ──────────────────
    if len(chars) > 2 and not chars[2].isalpha():
        original = chars[2]
        chars[2] = LETTER_SUBS.get(chars[2], chars[2])
        if chars[2] != original:
            n_changes += 1
            logger.debug(f"[VALIDATE] pos2: '{original}' → '{chars[2]}' (letter_sub)")

    # ── Bước 3: Vị trí 3 — Xác định điểm bắt đầu số đăng ký ─────────────────
    # Heuristic: nếu tổng = 9 ký tự VÀ pos3 là chữ cái → đây là phần số series (vd: B1)
    # → số đăng ký bắt đầu từ pos 4
    # Nếu không → số đăng ký bắt đầu từ pos 3
    reg_start = 3
    if len(chars) == 9 and len(chars) > 3 and chars[3].isalpha():
        reg_start = 4  # series có 2 ký tự (letter + digit), e.g. "B1"

    # ── Bước 4: Vị trí reg_start+ — Số đăng ký (phải là chữ số) ─────────────
    for i in range(reg_start, len(chars)):
        if not chars[i].isdigit():
            original = chars[i]
            chars[i] = DIGIT_SUBS.get(chars[i], chars[i])
            if chars[i] != original:
                n_changes += 1
                logger.debug(f"[VALIDATE] pos{i}: '{original}' → '{chars[i]}' (digit_sub reg)")

    fixed = "".join(chars)

    # ── Bước 5: Regex validation ──────────────────────────────────────────────
    is_valid = bool(PLATE_REGEX.match(fixed))

    # ── Bước 6: Confidence penalty ────────────────────────────────────────────
    if n_changes == 0:
        confidence_penalty = 0.0
    elif n_changes <= 2:
        confidence_penalty = 0.1
    else:
        confidence_penalty = 0.3

    # Nếu vẫn không hợp lệ sau substitution → penalty tối thiểu 0.3
    if not is_valid:
        confidence_penalty = max(confidence_penalty, 0.3)

    logger.info(
        f"[VALIDATE] '{raw_text}' → '{fixed}' "
        f"(valid={is_valid}, changes={n_changes}, penalty={confidence_penalty:.1f})"
    )

    return fixed, is_valid, confidence_penalty


def is_valid_province(plate_text: str) -> bool:
    """Kiểm tra mã tỉnh (2 ký tự đầu) có thuộc danh sách hợp lệ không."""
    if len(plate_text) < 2:
        return False
    return plate_text[:2] in VALID_PROVINCE_CODES
