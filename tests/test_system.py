"""
Script kiểm tra toàn bộ hệ thống trước khi chạy
"""

import sys
import os

def check_python_version():
    """Kiểm tra phiên bản Python"""
    print("🐍 Kiểm tra Python...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor} - Cần Python 3.8+")
        return False


def check_torch():
    """Kiểm tra PyTorch và CUDA"""
    print("\n🔥 Kiểm tra PyTorch...")
    try:
        import torch
        print(f"   ✅ PyTorch {torch.__version__}")
        
        if torch.cuda.is_available():
            print(f"   ✅ CUDA available: {torch.cuda.get_device_name(0)}")
            return True, True
        else:
            print("   ⚠️  CUDA không khả dụng - Sẽ dùng CPU")
            return True, False
    except ImportError:
        print("   ❌ PyTorch chưa được cài đặt")
        return False, False


def check_ultralytics():
    """Kiểm tra Ultralytics"""
    print("\n🎯 Kiểm tra Ultralytics...")
    try:
        from ultralytics import YOLO
        print("   ✅ Ultralytics đã được cài đặt")
        return True
    except ImportError:
        print("   ❌ Ultralytics chưa được cài đặt")
        print("      Chạy: py -m pip install ultralytics")
        return False


def check_easyocr():
    """Kiểm tra EasyOCR"""
    print("\n📚 Kiểm tra EasyOCR...")
    try:
        import easyocr
        print("   ✅ EasyOCR đã được cài đặt")
        return True
    except ImportError:
        print("   ⚠️  EasyOCR chưa được cài đặt")
        print("      Chạy: py -m pip install easyocr")
        return False


def check_opencv():
    """Kiểm tra OpenCV"""
    print("\n📷 Kiểm tra OpenCV...")
    try:
        import cv2
        print(f"   ✅ OpenCV {cv2.__version__}")
        return True
    except ImportError:
        print("   ❌ OpenCV chưa được cài đặt")
        print("      Chạy: py -m pip install opencv-python")
        return False


def check_database():
    """Kiểm tra kết nối database"""
    print("\n🗄️  Kiểm tra Database...")
    try:
        import psycopg2
        print("   ✅ psycopg2 đã được cài đặt")
        
        # Thử kết nối
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=55432,
                database="nhan_dien_bien_so_xe",
                user="postgres",
                password="postgres"
            )
            conn.close()
            print("   ✅ Kết nối database thành công")
            return True
        except Exception as e:
            print(f"   ⚠️  Không thể kết nối database: {e}")
            print("      Kiểm tra Docker containers đang chạy")
            return False
    except ImportError:
        print("   ⚠️  psycopg2 chưa được cài đặt")
        print("      Chạy: py -m pip install psycopg2-binary")
        return False


def check_dataset():
    """Kiểm tra dataset"""
    print("\n📦 Kiểm tra Dataset...")
    dataset_path = "data/datasets/vietnam_license_plate"
    data_yaml = os.path.join(dataset_path, "data.yaml")
    
    if os.path.exists(dataset_path) and os.path.exists(data_yaml):
        print(f"   ✅ Dataset tại: {dataset_path}")
        
        # Đếm số ảnh
        train_images = len([f for f in os.listdir(os.path.join(dataset_path, "train", "images")) 
                           if f.endswith(('.jpg', '.png'))])
        val_images = len([f for f in os.listdir(os.path.join(dataset_path, "valid", "images")) 
                         if f.endswith(('.jpg', '.png'))])
        
        print(f"   ✅ Train images: {train_images}")
        print(f"   ✅ Valid images: {val_images}")
        return True
    else:
        print(f"   ❌ Dataset không tìm thấy tại: {dataset_path}")
        return False


def check_model():
    """Kiểm tra model đã train"""
    print("\n🤖 Kiểm tra Model...")
    model_path = "data/models/HeThongBarrier/Plate_Detection_v1/weights/best.pt"
    
    if os.path.exists(model_path):
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        print(f"   ✅ Model đã được train: {model_path}")
        print(f"   ✅ Kích thước: {size_mb:.2f} MB")
        return True
    else:
        print("   ⚠️  Model chưa được train")
        print("      Chạy: py scripts/train_yolo.py")
        return False


def main():
    """Hàm chính"""
    import sys
    import io
    # Fix encoding cho Windows
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("="*60)
    print("KIEM TRA HE THONG")
    print("="*60)
    
    results = {
        'python': check_python_version(),
        'torch': check_torch()[0],
        'cuda': check_torch()[1],
        'ultralytics': check_ultralytics(),
        'easyocr': check_easyocr(),
        'opencv': check_opencv(),
        'database': check_database(),
        'dataset': check_dataset(),
        'model': check_model()
    }
    
    print("\n" + "="*60)
    print("TOM TAT")
    print("="*60)
    
    critical = ['python', 'torch', 'ultralytics', 'opencv', 'dataset']
    optional = ['cuda', 'easyocr', 'database', 'model']
    
    all_critical_ok = all(results[key] for key in critical)
    
    for key in critical:
        status = "✅" if results[key] else "❌"
        print(f"{status} {key.upper()}")
    
    print("\nTùy chọn:")
    for key in optional:
        status = "✅" if results[key] else "⚠️"
        print(f"{status} {key.upper()}")
    
    if all_critical_ok:
        print("\nHe thong da san sang de chay!")
    else:
        print("\nMot so thanh phan can duoc cai dat")
    
    return all_critical_ok


if __name__ == "__main__":
    main()
