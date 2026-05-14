import sys
with open('d:/SMARTPARK/api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Sửa hàm open_manual để lấy ảnh toàn cảnh nếu không tìm thấy biển số
old_open_manual_logic = """        res = process_frame_core(frame)
        plate = res.get("plate") or "[THỦ CÔNG]"
        img_base64 = res.get("plate_crop_base64") or ""
        
        insert_history(plate, trang_thai, img_base64, gate_id=gate_id)"""

new_open_manual_logic = """        res = process_frame_core(frame)
        plate = res.get("plate") or "[THỦ CÔNG]"
        img_base64 = res.get("plate_crop_base64")
        
        # Nếu AI không tìm thấy biển số (res rỗng), dùng ảnh toàn cảnh làm log
        if not img_base64:
            h, w = frame.shape[:2]
            small_frame = cv2.resize(frame, (640, int(h * 640 / w)))
            _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            res["plate_crop_base64"] = img_base64 # Để lát nữa gửi WebSocket
        
        insert_history(plate, trang_thai, img_base64, gate_id=gate_id)"""

if old_open_manual_logic in content:
    content = content.replace(old_open_manual_logic, new_open_manual_logic)
else:
    print("Could not find old_open_manual_logic")

with open('d:/SMARTPARK/api_server.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done patching open_manual")
