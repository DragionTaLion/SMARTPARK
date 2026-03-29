"""
Bước 4: Tích hợp CNN Character Recognition vào hệ thống chính
Module này chứa hàm nhận diện ký tự bằng model YOLOv8-cls đã train.
"""

from ultralytics import YOLO
import numpy as np
import cv2
from typing import Optional, List


# Bảng ánh xạ index → ký tự (36 lớp: 0-9, A-Z)
# Tương ứng với thứ tự folder: 0,1,...,9,A,B,...,Z
CHAR_CLASSES = list('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def load_char_model(model_path: str):
    """Load model phân loại ký tự đã train"""
    return YOLO(model_path)


def predict_character(model, char_img: np.ndarray, conf_threshold: float = 0.3) -> Optional[str]:
    """
    Dự đoán ký tự từ ảnh grayscale 32x32.

    Args:
        model      : YOLOv8-cls model đã load
        char_img   : Ảnh grayscale (32x32) của một ký tự
        conf_threshold: Ngưỡng confidence tối thiểu

    Returns:
        Ký tự dự đoán (string), hoặc None nếu confidence quá thấp
    """
    # Chuyển grayscale → 3 channel (YOLO cần RGB)
    if len(char_img.shape) == 2:
        char_rgb = cv2.cvtColor(char_img, cv2.COLOR_GRAY2RGB)
    else:
        char_rgb = char_img

    results = model(char_rgb, verbose=False)

    if not results:
        return None

    probs = results[0].probs
    if probs is None:
        return None

    top1_conf = float(probs.top1conf)
    top1_idx = int(probs.top1)

    if top1_conf < conf_threshold:
        return None

    if top1_idx < len(CHAR_CLASSES):
        return CHAR_CLASSES[top1_idx]

    return None


def predict_plate_text(
    char_model,
    char_images: List[np.ndarray],
    conf_threshold: float = 0.3,
) -> str:
    """
    Ghép kết quả dự đoán từng ký tự thành chuỗi biển số.

    Args:
        char_model  : YOLOv8-cls model đã load
        char_images : Danh sách ảnh ký tự (output của segment_characters)
        conf_threshold: Ngưỡng confidence tối thiểu

    Returns:
        Chuỗi biển số (ví dụ: '30A12345')
    """
    plate_text = ""
    for char_img in char_images:
        char = predict_character(char_model, char_img, conf_threshold)
        if char:
            plate_text += char
    return plate_text
