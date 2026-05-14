import sys
with open('d:/SMARTPARK/api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Thêm log cho OCR và fix lỗi thiếu ảnh khi OCR thất bại
old_ocr_logic = """        if not plate_text:
            return {
                "detected": True,
                "plate": "",
                "confidence": best_conf,
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "processed": False,
                "reason": "OCR không đọc được",
            }"""

new_ocr_logic = """        # Encode ảnh crop ngay cả khi OCR thất bại để debug
        _, buffer = cv2.imencode('.jpg', plate_crop)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        if not plate_text:
            print(f"  ⚠️ OCR thất bại cho biển số tại [{x1}, {y1}, {x2}, {y2}]")
            return {
                "detected": True,
                "plate": "",
                "confidence": best_conf,
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "processed": False,
                "reason": "OCR không đọc được",
                "plate_crop_base64": img_base64
            }"""

if old_ocr_logic in content:
    content = content.replace(old_ocr_logic, new_ocr_logic)

# 2. Thêm log vào phần gọi segmentation
old_seg_call = "char_images = segment_characters(plate_crop, target_size=32)"
new_seg_call = """char_images = segment_characters(plate_crop, target_size=32)
            print(f"  🔍 Segmentation: tìm thấy {len(char_images) if char_images else 0} ký tự")"""

if old_seg_call in content:
    content = content.replace(old_seg_call, new_seg_call)

with open('d:/SMARTPARK/api_server.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done enhancing api_server.py")
