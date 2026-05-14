from ultralytics import YOLO
import cv2
from core.segmentation import segment_characters
from core.char_recognizer import predict_plate_text, load_char_model

# 1. Load các mô hình
plate_model = YOLO("data/models/plate_detect.pt")
char_model = load_char_model("data/models/char_model/weights/best.pt")

# 2. Đọc ảnh (đảm bảo file test_image.jpg có thật trong thư mục nhé)
img = cv2.imread("test_image.jpg") 
if img is None:
    print("❌ Không tìm thấy file test_image.jpg")
    exit()

# 3. Chạy YOLO tìm biển số
results = plate_model.predict(img, conf=0.5)

for r in results:
    for box in r.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        plate_crop = img[y1:y2, x1:x2]
        
        # --- BƯỚC QUAN TRỌNG: Gọi CNN để đọc chữ ---
        char_images = segment_characters(plate_crop, target_size=32)
        plate_text = predict_plate_text(char_model, char_images)
        
        print(f"✅ Kết quả nhận diện: {plate_text}")
        cv2.imshow(f"Bien so: {plate_text}", plate_crop)
        cv2.waitKey(0)
