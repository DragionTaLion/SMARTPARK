"""
Integrity check for SmartPark datasets.

Checks:
1) Split structure (train/val/test)
2) Split ratios
3) Class balance (0-9, A-Z)
4) Label consistency for classify and YOLO detect datasets
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


CHAR_LABELS = [str(i) for i in range(10)] + [chr(ord("A") + i) for i in range(26)]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def list_images(folder: Path) -> List[Path]:
    return [p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXTS]


def count_char_split(split_dir: Path) -> Dict[str, int]:
    counts = {label: 0 for label in CHAR_LABELS}
    if not split_dir.exists():
        return counts
    for label in CHAR_LABELS:
        cls_dir = split_dir / label
        if cls_dir.exists():
            counts[label] = sum(1 for p in cls_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    return counts


def summarize_balance(counts: Dict[str, int]) -> Dict[str, float]:
    values = [v for v in counts.values() if v > 0]
    if not values:
        return {"min": 0, "max": 0, "mean": 0, "imbalance_ratio": 0}
    min_v = min(values)
    max_v = max(values)
    mean_v = sum(values) / len(values)
    return {
        "min": min_v,
        "max": max_v,
        "mean": round(mean_v, 2),
        "imbalance_ratio": round(max_v / max(min_v, 1), 2),
    }


def check_chars36(chars_dir: Path) -> Dict:
    train_counts = count_char_split(chars_dir / "train")
    val_counts = count_char_split(chars_dir / "val")
    test_counts = count_char_split(chars_dir / "test")

    total_train = sum(train_counts.values())
    total_val = sum(val_counts.values())
    total_test = sum(test_counts.values())
    total = total_train + total_val + total_test

    present_labels_train = [k for k, v in train_counts.items() if v > 0]
    present_labels_val = [k for k, v in val_counts.items() if v > 0]
    missing_train = [l for l in CHAR_LABELS if l not in present_labels_train]
    missing_val = [l for l in CHAR_LABELS if l not in present_labels_val]

    train_ratio = total_train / total if total else 0
    val_ratio = total_val / total if total else 0
    test_ratio = total_test / total if total else 0

    return {
        "dataset": str(chars_dir),
        "exists": chars_dir.exists(),
        "splits": {
            "train": total_train,
            "val": total_val,
            "test": total_test,
            "total": total,
            "ratio_train": round(train_ratio, 4),
            "ratio_val": round(val_ratio, 4),
            "ratio_test": round(test_ratio, 4),
        },
        "label_consistency": {
            "expected_num_classes": 36,
            "train_present_classes": len(present_labels_train),
            "val_present_classes": len(present_labels_val),
            "missing_in_train": missing_train,
            "missing_in_val": missing_val,
        },
        "class_balance": {
            "train": summarize_balance(train_counts),
            "val": summarize_balance(val_counts),
            "train_counts": train_counts,
            "val_counts": val_counts,
        },
    }


def parse_yolo_data_yaml(yaml_path: Path) -> Tuple[Path, str, str, str]:
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    root = Path(data["path"])
    train_rel = data.get("train", "train/images")
    val_rel = data.get("val", "valid/images")
    test_rel = data.get("test", "test/images")
    return root, train_rel, val_rel, test_rel


def check_yolo_labels(images_dir: Path, labels_dir: Path) -> Dict[str, int]:
    image_files = [p for p in images_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
    missing_label = 0
    invalid_lines = 0
    empty_label = 0
    cls_counter = Counter()

    for img in image_files:
        label_path = labels_dir / (img.stem + ".txt")
        if not label_path.exists():
            missing_label += 1
            continue
        lines = label_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        if not lines:
            empty_label += 1
            continue
        for line in lines:
            parts = line.split()
            if len(parts) != 5:
                invalid_lines += 1
                continue
            try:
                cls_id = int(float(parts[0]))
                _ = [float(x) for x in parts[1:]]
                cls_counter[cls_id] += 1
            except ValueError:
                invalid_lines += 1

    return {
        "images": len(image_files),
        "missing_label_files": missing_label,
        "empty_label_files": empty_label,
        "invalid_label_lines": invalid_lines,
        "class_distribution": dict(cls_counter),
    }


def check_yolo_dataset(data_yaml: Path) -> Dict:
    root, train_rel, val_rel, test_rel = parse_yolo_data_yaml(data_yaml)
    train_images = root / train_rel
    val_images = root / val_rel
    test_images = root / test_rel

    train_labels = Path(str(train_images).replace("\\images", "\\labels").replace("/images", "/labels"))
    val_labels = Path(str(val_images).replace("\\images", "\\labels").replace("/images", "/labels"))
    test_labels = Path(str(test_images).replace("\\images", "\\labels").replace("/images", "/labels"))

    train_stats = check_yolo_labels(train_images, train_labels) if train_images.exists() else {}
    val_stats = check_yolo_labels(val_images, val_labels) if val_images.exists() else {}
    test_stats = check_yolo_labels(test_images, test_labels) if test_images.exists() else {}

    total_images = train_stats.get("images", 0) + val_stats.get("images", 0) + test_stats.get("images", 0)
    ratio_train = train_stats.get("images", 0) / total_images if total_images else 0
    ratio_val = val_stats.get("images", 0) / total_images if total_images else 0
    ratio_test = test_stats.get("images", 0) / total_images if total_images else 0

    return {
        "data_yaml": str(data_yaml),
        "root": str(root),
        "splits": {
            "train_images": train_stats.get("images", 0),
            "val_images": val_stats.get("images", 0),
            "test_images": test_stats.get("images", 0),
            "total_images": total_images,
            "ratio_train": round(ratio_train, 4),
            "ratio_val": round(ratio_val, 4),
            "ratio_test": round(ratio_test, 4),
        },
        "label_consistency": {
            "train": train_stats,
            "val": val_stats,
            "test": test_stats,
        },
    }


def suggest_augmentation(chars_report: Dict) -> List[str]:
    imbalance = chars_report["class_balance"]["train"]["imbalance_ratio"]
    suggestions = []
    if imbalance >= 1.5:
        suggestions.append("Class imbalance cao: dùng WeightedRandomSampler hoặc class weights.")
        suggestions.append("Augment ký tự yếu: random rotate (-8..8), brightness/contrast, gaussian noise.")
        suggestions.append("Ưu tiên augment cho các class có count < 80% median.")
    else:
        suggestions.append("Class balance tương đối ổn, dùng augment nhẹ để tăng tổng quát hóa.")
    suggestions.append("Giữ tỷ lệ ký tự, tránh shear/perspective quá mạnh vì làm méo cấu trúc biển số.")
    return suggestions


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartPark dataset integrity check")
    parser.add_argument("--chars-dir", default="data/datasets/chars_36")
    parser.add_argument("--yolo-data", default="data/datasets/vietnam_license_plate/data.yaml")
    parser.add_argument("--out-json", default="reports/dataset_integrity_report.json")
    args = parser.parse_args()

    chars_report = check_chars36(Path(args.chars_dir))
    yolo_report = check_yolo_dataset(Path(args.yolo_data))

    report = {
        "chars_36": chars_report,
        "yolo_dataset": yolo_report,
        "augmentation_recommendations": suggest_augmentation(chars_report),
    }

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== DATASET INTEGRITY CHECK ===")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
