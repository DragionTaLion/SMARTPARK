from ultralytics import YOLO
import torch

# Kiểm tra GPU
if torch.cuda.is_available():
    device = 0  # Sử dụng GPU
    print(f"✅ GPU được phát hiện: {torch.cuda.get_device_name(0)}")
    print(f"   Sử dụng GPU để tăng tốc huấn luyện!")
else:
    device = 'cpu'  # Sử dụng CPU
    print("⚠️  GPU không được phát hiện, sẽ sử dụng CPU (chậm hơn)")
    print("   Nếu bạn có GPU, hãy cài đặt PyTorch với CUDA support")

# Batch mặc định: CPU dùng nhỏ để tránh tràn RAM
batch = 16 if device != 'cpu' else 4

print("\n📥 Đang tải model YOLOv8n pre-trained...")
model = YOLO('data/models/yolov8n.pt') 

# 2. Bắt đầu huấn luyện
print("\n🚀 Bắt đầu huấn luyện model...")
print("="*60)
results = model.train(
    data='data/datasets/vietnam_license_plate/data.yaml', # Đường dẫn file cấu hình
    epochs=50,                # Chạy 50 vòng để model đủ thông minh
    imgsz=640,                # Kích thước ảnh chuẩn
    device=device,            # Tự động phát hiện GPU hoặc dùng CPU
    project='data/models/HeThongBarrier', # Tên dự án
    name='Plate_Detection_v1', # Tên phiên bản huấn luyện
    batch=batch,              # Batch size (CPU mặc định 4)
    patience=10,              # Early stopping nếu không cải thiện
    save=True,                # Lưu checkpoint
    plots=True                # Tạo biểu đồ kết quả
)

print("\n" + "="*50)
print("HUẤN LUYỆN HOÀN TẤT!")
print("="*50)
print(f"Model tốt nhất được lưu tại: data/models/HeThongBarrier/Plate_Detection_v1/weights/best.pt")
print(f"Model cuối cùng được lưu tại: data/models/HeThongBarrier/Plate_Detection_v1/weights/last.pt")
