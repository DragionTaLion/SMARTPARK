from typing import Optional, Tuple, List
from ultralytics import YOLO
import torch

def load_yolo_model(model_path: str):
    """Load YOLO model from path"""
    return YOLO(model_path)

def detect_license_plates(model, frame, conf: float = 0.5) -> List:
    """Detect license plates in a frame"""
    results = model(frame, conf=conf, verbose=False)
    return results

def get_best_plate_box(results) -> Optional[Tuple[float, Tuple[int, int, int, int]]]:
    """Get the bounding box with highest confidence from YOLO results"""
    for result in results:
        boxes = result.boxes
        if len(boxes) == 0:
            continue
        
        # Lấy box có confidence cao nhất
        best_box = boxes[0]
        confidence = float(best_box.conf[0])
        x1, y1, x2, y2 = map(int, best_box.xyxy[0].cpu().numpy())
        return (confidence, (x1, y1, x2, y2))
    
    return None
