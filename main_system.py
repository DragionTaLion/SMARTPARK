"""
Hệ thống nhận diện biển số xe tự động
- Chế độ 1: YOLO + EasyOCR (mặc định)
- Chế độ 2: YOLO + OpenCV Segmentation + CNN phân loại ký tự (khi có --char-model)
"""

import cv2
import sys
import io
from typing import Optional, Tuple
from core.database import process_vehicle_entry
from core.detection import load_yolo_model, detect_license_plates, get_best_plate_box

# Fix encoding cho Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass


class LicensePlateSystem:
    """Hệ thống nhận diện và xử lý biển số xe"""
    
    def __init__(self, model_path: str, com_port: str = "COM3", camera_id: int = 0, char_model_path: str = None, demo_mode: bool = False):
        """
        Khởi tạo hệ thống
        Args:
            model_path      : Đường dẫn model YOLO detect biển số
            com_port        : Cổng COM của Arduino
            camera_id       : ID webcam
            char_model_path : Model CNN phân loại ký tự (tùy chọn)
        """
        print("="*60)
        print("KHOI TAO HE THONG NHAN DIEN BIEN SO XE")
        print("="*60)

        # Load YOLO detect biển số
        print(f"\n[1/3] Dang tai model YOLO: {model_path}")
        try:
            self.model = load_yolo_model(model_path)
            print("   ✅ Model da duoc tai thanh cong")
        except Exception as e:
            print(f"   ❌ Loi khi tai model: {e}")
            raise

        # Chế độ OCR: CNN hoặc EasyOCR
        self.use_cnn = False
        self.char_model = None
        self.reader = None

        if char_model_path:
            print(f"\n[2/3] Dang tai model CNN ki tu: {char_model_path}")
            try:
                from core.char_recognizer import load_char_model
                self.char_model = load_char_model(char_model_path)
                self.use_cnn = True
                print("   ✅ CNN Character Model da san sang (che do CNN)")
            except Exception as e:
                print(f"   ⚠️  Loi khi tai CNN model: {e} — Fallback sang EasyOCR")

        if not self.use_cnn:
            print("\n[2/3] Dang khoi tao EasyOCR...")
            try:
                from core.ocr import init_easyocr
                self.reader = init_easyocr()
                print("   ✅ EasyOCR da san sang (che do EasyOCR)")
            except Exception as e:
                print(f"   ❌ Loi khi khoi tao EasyOCR: {e}")
                raise

        # Cấu hình
        self.com_port = com_port
        self.camera_id = camera_id
        self.demo_mode = demo_mode
        self.last_processed_plate = None
        self.last_processed_time = 0
        self.cooldown_seconds = 5

        ocr_mode = "CNN" if self.use_cnn else "EasyOCR"
        hw_mode = "DEMO (khong can phan cung)" if demo_mode else f"COM: {com_port}"
        print(f"\n[3/3] Cau hinh:")
        print(f"   - COM Port  : {hw_mode}")
        print(f"   - Camera ID : {camera_id}")
        print(f"   - OCR Mode  : {ocr_mode}")
        print(f"   - Cooldown  : {self.cooldown_seconds} giay")

        print("\n" + "="*60)
        print("HE THONG DA SAN SANG!")
        print("="*60)
        print("\nNhan 'q' de thoat")
        print("Nhan 's' de chup anh va luu")
        print("-"*60)
    
    def detect_and_read_plate(self, frame) -> Optional[Tuple[str, float, Tuple[int, int, int, int]]]:
        """
        Nhận diện và đọc biển số từ frame
        
        Returns:
            (plate_number, confidence, bbox) hoặc None
        """
        # Detect biển số
        results = detect_license_plates(self.model, frame)
        best_plate = get_best_plate_box(results)

        if best_plate:
            confidence, (x1, y1, x2, y2) = best_plate
            plate_crop = frame[y1:y2, x1:x2]

            try:
                if self.use_cnn:
                    # --- Chế độ CNN ---
                    from core.segmentation import segment_characters
                    from core.char_recognizer import predict_plate_text
                    char_images = segment_characters(plate_crop, two_rows=None, target_size=32)
                    plate_number = predict_plate_text(self.char_model, char_images)
                else:
                    # --- Chế độ EasyOCR ---
                    from core.ocr import read_license_plate_2_lines
                    ocr_result = read_license_plate_2_lines(self.reader, frame, (x1, y1, x2, y2))
                    if ocr_result['confidence'] > 0.5:
                        plate_number = (ocr_result['line1'] + ocr_result['line2']).strip()
                    else:
                        plate_number = ""

                if plate_number:
                    return (plate_number, confidence, (x1, y1, x2, y2))
            except Exception as e:
                print(f"   ⚠️  Loi khi doc text: {e}")
        
        return None
    
    def process_frame(self, frame) -> dict:
        """
        Xử lý một frame
        
        Returns:
            dict với thông tin kết quả
        """
        import time
        
        # Detect và đọc biển số
        result = self.detect_and_read_plate(frame)
        
        if result is None:
            return {'detected': False}
        
        plate_number, confidence, bbox = result
        
        # Biển số hợp lệ phải có ít nhất 4 ký tự
        if len(plate_number) < 4:
            return {'detected': False}
        
        # Cooldown: Tránh xử lý cùng 1 biển số nhiều lần
        current_time = time.time()
        if (plate_number == self.last_processed_plate and 
            current_time - self.last_processed_time < self.cooldown_seconds):
            return {
                'detected': True,
                'plate': plate_number,
                'confidence': confidence,
                'bbox': bbox,
                'processed': False,
                'reason': 'cooldown'
            }
        
        # Cập nhật cooldown
        self.last_processed_plate = plate_number
        self.last_processed_time = current_time

        # Toggle trạng thái Ra/Vào dựa trên lần cuối xử lý
        last_status = getattr(self, '_plate_last_status', {})
        prev_status = last_status.get(plate_number, 'Ra')  # mặc định lần đầu là "Vào"
        next_status = 'Vao' if prev_status == 'Ra' else 'Ra'
        last_status[plate_number] = next_status
        self._plate_last_status = last_status
        
        # --- Đối chiếu Database (cả demo lẫn live) ---
        try:
            from core.database import check_plate_in_db, insert_history, get_all_residents, normalize_plate
            import difflib

            # 1. Thử khớp chính xác trước
            owner = check_plate_in_db(plate_number)
            matched_plate = plate_number
            is_fuzzy = False

            # 2. Nếu không khớp chính xác, thử Fuzzy Matching
            if not owner:
                residents = get_all_residents() # [(norm, orig, owner), ...]
                norm_detected = normalize_plate(plate_number)
                
                best_ratio = 0
                for norm_res, orig_res, owner_name in residents:
                    # Tính tỉ lệ tương đồng Levenshtein/difflib
                    ratio = difflib.SequenceMatcher(None, norm_detected, norm_res).ratio()
                    if ratio > 0.8 and ratio > best_ratio: # Ngưỡng 80%
                        best_ratio = ratio
                        owner = owner_name
                        matched_plate = orig_res
                        is_fuzzy = True

            if owner:
                # Xe cư dân — ghi lịch sử ra/vào
                # Nếu khớp mờ, ta ghi biển số đúng trong DB vào log để dễ quản lý
                insert_history(matched_plate, trang_thai=next_status)
                
                # Mở barrier (chỉ trong chế độ live và khi xe Vào)
                if not self.demo_mode and next_status == 'Vao':
                    try:
                        from core.database import open_barrier_via_arduino
                        open_barrier_via_arduino(self.com_port)
                    except Exception:
                        pass
                
                status_label = "Vao" if next_status == "Vao" else "Ra"
                fuzzy_tag = "(Fuzzy) " if is_fuzzy else ""
                msg = f"[{'DEMO' if self.demo_mode else 'LIVE'}] {fuzzy_tag}Cu dan: {owner} | {matched_plate} | {status_label}"
                print(f"   \u2705 {msg}")
                
                db_result = {
                    'success': True,
                    'owner': owner,
                    'trang_thai': next_status,
                    'matched_plate': matched_plate,
                    'is_fuzzy': is_fuzzy,
                    'message': msg
                }
            else:
                # Xe lạ — ghi log "Tu choi"
                insert_history(plate_number, trang_thai='Tu choi')
                msg = f"[{'DEMO' if self.demo_mode else 'LIVE'}] Xe la! Bien so: {plate_number} | Khong co trong he thong"
                print(f"   \u26a0\ufe0f  {msg}")
                
                db_result = {
                    'success': False,
                    'owner': None,
                    'trang_thai': 'Tu choi',
                    'message': msg
                }
        except Exception as e:
            print(f"   \u274c Loi DB: {e}")
            db_result = {'success': False, 'owner': None, 'trang_thai': 'Loi DB', 'message': str(e)}

        
        # Ghi thêm CSV trong chế độ demo
        if self.demo_mode:
            try:
                from core.logger import log_plate_to_csv
                log_plate_to_csv(plate_number, confidence, status=db_result.get('trang_thai', 'Unknown'))
            except Exception:
                pass
        
        return {
            'detected': True,
            'plate': plate_number,
            'confidence': confidence,
            'bbox': bbox,
            'processed': True,
            'db_result': db_result
        }
    
    def draw_result(self, frame, result: dict) -> None:
        """Vẽ kết quả lên frame"""
        h, w = frame.shape[:2]

        # --- Banner trạng thái ở góc trên trái ---
        ocr_label = "CNN" if self.use_cnn else "EasyOCR"
        mode_label = "[DEMO]" if self.demo_mode else "[LIVE]"
        banner = f"{mode_label} OCR: {ocr_label}"
        cv2.rectangle(frame, (0, 0), (300, 30), (30, 30, 30), -1)
        cv2.putText(frame, banner, (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2)

        if not result.get('detected'):
            cv2.putText(frame, "Dang tim bien so...", (8, h - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
            return

        plate      = result.get('plate', '')
        confidence = result.get('confidence', 0)
        bbox       = result.get('bbox')
        db_result  = result.get('db_result', {})
        trang_thai = db_result.get('trang_thai', '')
        owner      = db_result.get('owner')
        matched_p  = db_result.get('matched_plate', '')
        is_fuzzy   = db_result.get('is_fuzzy', False)
        processed  = result.get('processed', False)

        # Màu sắc: xanh lá = cư dân, đỏ = xe lạ/lỗi
        is_known = bool(owner)
        box_color = (0, 220, 60) if is_known else (0, 50, 220)

        if bbox:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)

            # Dòng 1: Biển số + trạng thái
            if is_known:
                status_str = "VAO" if trang_thai == "Vao" else "RA"
                p_text = matched_p if is_fuzzy else plate
                fuzzy_mark = "*" if is_fuzzy else ""
                line1 = f"{p_text}{fuzzy_mark} [{status_str}]"
            else:
                line1 = f"{plate} [XE LA!]"

            font = cv2.FONT_HERSHEY_SIMPLEX
            fs, th = 0.75, 2
            (lw, lh), _ = cv2.getTextSize(line1, font, fs, th)
            label_y = max(y1 - 14, lh + 6)
            cv2.rectangle(frame, (x1, label_y - lh - 6), (x1 + lw + 10, label_y + 4), (20, 20, 20), -1)
            cv2.putText(frame, line1, (x1 + 5, label_y), font, fs, box_color, th)

            # Dòng 2: Tên chủ xe hoặc cảnh báo
            if is_known:
                line2 = f"Chu xe: {owner}"
                if is_fuzzy:
                    line2 += f" (OCR: {plate})"
                cv2.putText(frame, line2, (x1, y2 + 20), font, 0.5, (0, 220, 60), 1)
            else:
                line2 = "Khong co trong he thong!"
                cv2.putText(frame, line2, (x1, y2 + 20), font, 0.5, (0, 80, 255), 2)


            # Dòng 3: Confidence YOLO
            cv2.putText(frame, f"Conf: {confidence:.0%}", (x1, y2 + 40),
                        font, 0.4, (180, 180, 180), 1)

        # Footer
        footer = "DB: PostgreSQL  |  Log: data/detection_log.csv  |  Nhan Q de thoat"
        cv2.rectangle(frame, (0, h - 28), (w, h), (20, 20, 20), -1)
        cv2.putText(frame, footer, (8, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 210, 160), 1)


    def run(self, use_webcam: bool = True, image_path: Optional[str] = None):
        """
        Chạy hệ thống
        
        Args:
            use_webcam: True để dùng webcam, False để xử lý ảnh
            image_path: Đường dẫn ảnh (nếu use_webcam=False)
        """
        if use_webcam:
            # Mở webcam — thử DSHOW trước trên Windows để tránh lỗi MSMF
            cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.camera_id)
            if not cap.isOpened():
                print(f"❌ Khong the mo webcam (ID: {self.camera_id})")
                print("   Thu thu cong: doi cac ung dung khac dang dung camera (Teams, Zoom, ...)")
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            print("\n🎥 Bat dau nhan dien tu webcam...")

            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # Xử lý mỗi 5 frame để tăng tốc
                if frame_count % 5 == 0:
                    result = self.process_frame(frame)
                    self.draw_result(frame, result)
                
                # Hiển thị
                cv2.imshow('He thong nhan dien bien so xe', frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    # Lưu ảnh
                    cv2.imwrite(f'capture_{frame_count}.jpg', frame)
                    print(f"   💾 Da luu anh: capture_{frame_count}.jpg")
            
            cap.release()
        else:
            # Xử lý ảnh
            if not image_path:
                print("❌ Can duong dan anh")
                return
            
            print(f"\n📷 Xu ly anh: {image_path}")
            frame = cv2.imread(image_path)
            if frame is None:
                print(f"❌ Khong the doc anh: {image_path}")
                return
            
            result = self.process_frame(frame)
            self.draw_result(frame, result)
            
            # Hiển thị và lưu kết quả
            cv2.imshow('Ket qua', frame)
            output_path = image_path.replace('.jpg', '_result.jpg').replace('.png', '_result.png')
            cv2.imwrite(output_path, frame)
            print(f"   💾 Da luu ket qua: {output_path}")
            
            cv2.waitKey(0)
        
        cv2.destroyAllWindows()
        print("\n✅ Da thoat he thong")


def main():
    """Hàm chính"""
    import argparse

    parser = argparse.ArgumentParser(description='He thong nhan dien bien so xe')
    parser.add_argument(
        '--model',
        type=str,
        default='data/models/plate_detect.pt',
        help='Duong dan den file model YOLO phat hien bien so (.pt)'
    )
    parser.add_argument(
        '--char-model',
        type=str,
        default=None,
        help='Duong dan den model CNN phan loai ky tu (neu co, dung CNN thay EasyOCR)'
    )
    parser.add_argument(
        '--com',
        type=str,
        default='COM3',
        help='COM port cua Arduino'
    )
    parser.add_argument(
        '--camera',
        type=int,
        default=0,
        help='Camera ID (0 la webcam mac dinh)'
    )
    parser.add_argument(
        '--image',
        type=str,
        default=None,
        help='Duong dan anh de xu ly (neu khong dung webcam)'
    )
    parser.add_argument(
        '--demo',
        action='store_true',
        default=False,
        help='Che do demo: chi hien thi bien so, khong can Arduino hay Database'
    )

    args = parser.parse_args()

    # Kiểm tra model có tồn tại không
    import os
    if not os.path.exists(args.model):
        print(f"❌ Khong tim thay model: {args.model}")
        print("\nBan can train model truoc:")
        print("  py scripts/train_yolo.py")
        return

    # Khởi tạo và chạy hệ thống
    try:
        system = LicensePlateSystem(
            model_path=args.model,
            com_port=args.com,
            camera_id=args.camera,
            char_model_path=args.char_model,
            demo_mode=args.demo,
        )

        use_webcam = args.image is None
        system.run(use_webcam=use_webcam, image_path=args.image)
    except KeyboardInterrupt:
        print("\n\n⚠️  Da dung boi nguoi dung")
    except Exception as e:
        print(f"\n❌ Loi: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
