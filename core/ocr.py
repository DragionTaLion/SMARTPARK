"""
Script chuẩn bị và test EasyOCR cho đọc biển số xe Việt Nam
Biển số Việt Nam thường có 2 dòng: Dòng trên (số) và dòng dưới (chữ)
"""

import easyocr
import cv2
import numpy as np
from PIL import Image
import os

def init_easyocr():
    """
    Khởi tạo EasyOCR reader cho tiếng Việt và số
    """
    print("📚 Đang khởi tạo EasyOCR...")
    print("   (Lần đầu chạy sẽ tải model, có thể mất vài phút)")
    
    # Khởi tạo reader với tiếng Anh và số (biển số VN chủ yếu là số và chữ Latin)
    reader = easyocr.Reader(['en'], gpu=True)  # gpu=True nếu có GPU, False nếu không
    
    print("✅ EasyOCR đã sẵn sàng!")
    return reader


def read_license_plate_2_lines(reader, image_path, crop_box=None):
    """
    Đọc biển số xe Việt Nam (2 dòng)
    
    Args:
        reader: EasyOCR reader object
        image_path: Đường dẫn đến ảnh hoặc numpy array
        crop_box: (x1, y1, x2, y2) - Vùng cắt từ YOLO detection
    
    Returns:
        dict: {
            'full_text': '30A-12345\nABC',
            'line1': '30A-12345',  # Dòng trên
            'line2': 'ABC',         # Dòng dưới
            'confidence': 0.95
        }
    """
    # Đọc ảnh
    if isinstance(image_path, str):
        img = cv2.imread(image_path)
    else:
        img = image_path
    
    # Cắt vùng biển số nếu có crop_box
    if crop_box:
        x1, y1, x2, y2 = crop_box
        img = img[y1:y2, x1:x2]
    
    # Chuyển sang grayscale để tăng độ tương phản
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Tăng độ tương phản
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Đọc text
    results = reader.readtext(enhanced)
    
    if not results:
        return {
            'full_text': '',
            'line1': '',
            'line2': '',
            'confidence': 0.0
        }
    
    # Phân loại text vào 2 dòng dựa trên tọa độ Y
    texts = []
    for (bbox, text, confidence) in results:
        # Lấy tọa độ Y trung bình của bounding box
        y_center = np.mean([point[1] for point in bbox])
        texts.append({
            'text': text.strip(),
            'y': y_center,
            'confidence': confidence
        })
    
    # Sắp xếp theo Y (từ trên xuống dưới)
    texts.sort(key=lambda x: x['y'])
    
    # Phân chia thành 2 dòng
    if len(texts) == 0:
        return {
            'full_text': '',
            'line1': '',
            'line2': '',
            'confidence': 0.0
        }
    elif len(texts) == 1:
        # Chỉ có 1 dòng
        return {
            'full_text': texts[0]['text'],
            'line1': texts[0]['text'],
            'line2': '',
            'confidence': texts[0]['confidence']
        }
    else:
        # Có nhiều dòng, phân chia thành 2 nhóm
        mid_y = np.median([t['y'] for t in texts])
        
        line1_texts = [t['text'] for t in texts if t['y'] < mid_y]
        line2_texts = [t['text'] for t in texts if t['y'] >= mid_y]
        
        line1 = ' '.join(line1_texts)
        line2 = ' '.join(line2_texts)
        full_text = f"{line1}\n{line2}" if line2 else line1
        
        avg_confidence = np.mean([t['confidence'] for t in texts])
        
        return {
            'full_text': full_text,
            'line1': line1,
            'line2': line2,
            'confidence': avg_confidence
        }


def test_easyocr():
    """
    Test EasyOCR với ảnh mẫu (nếu có)
    """
    print("\n" + "="*60)
    print("🧪 TEST EASYOCR")
    print("="*60)
    
    reader = init_easyocr()
    
    # Test với ảnh mẫu nếu có
    test_image = "test_license_plate.jpg"
    
    if os.path.exists(test_image):
        print(f"\n📷 Đang test với ảnh: {test_image}")
        result = read_license_plate_2_lines(reader, test_image)
        
        print(f"\n📋 Kết quả:")
        print(f"   Dòng 1: {result['line1']}")
        print(f"   Dòng 2: {result['line2']}")
        print(f"   Độ tin cậy: {result['confidence']:.2%}")
        print(f"   Full text:\n{result['full_text']}")
    else:
        print(f"\n⚠️  Không tìm thấy ảnh test: {test_image}")
        print("   Bạn có thể thêm ảnh biển số để test")
    
    return reader


if __name__ == "__main__":
    print("="*60)
    print("CHUẨN BỊ EASYOCR CHO ĐỌC BIỂN SỐ XE VIỆT NAM")
    print("="*60)
    
    # Test EasyOCR
    reader = test_easyocr()
    
    print("\n✅ EasyOCR đã sẵn sàng để sử dụng!")
    print("\n💡 Sử dụng trong code:")
    print("   from prepare_easyocr import init_easyocr, read_license_plate_2_lines")
    print("   reader = init_easyocr()")
    print("   result = read_license_plate_2_lines(reader, image_path, crop_box)")
