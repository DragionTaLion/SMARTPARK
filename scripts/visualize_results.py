"""
Visualize SmartPark training outputs.

Produces:
1) Loss chart
2) Accuracy chart
3) Confusion matrix
4) Precision-Recall and F1 chart
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from ultralytics import YOLO
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
)
from sklearn.preprocessing import label_binarize


CHAR_LABELS = [str(i) for i in range(10)] + [chr(ord("A") + i) for i in range(26)]
plt.style.use("seaborn-v0_8-darkgrid")
sns.set_context("talk")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    return df


def first_existing(d: pd.DataFrame, names: List[str]) -> Optional[str]:
    for n in names:
        if n in d.columns:
            return n
    return None


def ensure_output_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def save_loss_chart(df: pd.DataFrame, out_dir: Path) -> None:
    epoch_col = first_existing(df, ["epoch"])
    train_loss_col = first_existing(df, ["train/loss", "train/box_loss"])
    val_loss_col = first_existing(df, ["val/loss", "val/box_loss"])
    if not epoch_col or not train_loss_col or not val_loss_col:
        return
    plt.figure(figsize=(12, 6))
    plt.plot(df[epoch_col], df[train_loss_col], label="Train Loss", linewidth=2)
    plt.plot(df[epoch_col], df[val_loss_col], label="Validation Loss", linewidth=2)
    plt.title("Loss Curve")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "loss_curve.png", dpi=220)
    plt.close()


def save_accuracy_chart(df: pd.DataFrame, out_dir: Path) -> None:
    epoch_col = first_existing(df, ["epoch"])
    # Classification
    top1_col = first_existing(df, ["metrics/accuracy_top1"])
    # Detection fallback: use mAP50 as "accuracy-like"
    map50_col = first_existing(df, ["metrics/mAP50(B)"])

    if not epoch_col:
        return

    plt.figure(figsize=(12, 6))
    if top1_col:
        plt.plot(df[epoch_col], df[top1_col] * 100, label="Val Accuracy Top-1 (%)", linewidth=2)
        plt.title("Accuracy Curve (Classification)")
        plt.ylabel("Accuracy (%)")
    elif map50_col:
        plt.plot(df[epoch_col], df[map50_col] * 100, label="mAP@0.5 (%)", linewidth=2)
        plt.title("Detection Quality Curve (mAP@0.5)")
        plt.ylabel("mAP@0.5 (%)")
    else:
        plt.close()
        return

    plt.xlabel("Epoch")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "accuracy_curve.png", dpi=220)
    plt.close()


def load_predictions_csv(pred_csv: Path) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], List[str]]:
    df = pd.read_csv(pred_csv)
    if "true_label" not in df.columns or "pred_label" not in df.columns:
        raise ValueError("predictions CSV phải có cột true_label, pred_label")
    y_true = df["true_label"].astype(str).to_numpy()
    y_pred = df["pred_label"].astype(str).to_numpy()

    score_cols = [c for c in df.columns if c.startswith("score_")]
    scores = None
    class_labels = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    if score_cols:
        class_labels = [c.replace("score_", "") for c in score_cols]
        scores = df[score_cols].to_numpy()
    return y_true, y_pred, scores, class_labels


def save_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    classes: List[str],
    out_dir: Path,
) -> Dict:
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    plt.figure(figsize=(16, 14))
    sns.heatmap(cm, cmap="Blues", xticklabels=classes, yticklabels=classes)
    plt.title("Confusion Matrix")
    plt.xlabel("Predicted Label")
    plt.ylabel("True Label")
    plt.tight_layout()
    plt.savefig(out_dir / "confusion_matrix_36x36.png", dpi=240)
    plt.close()

    # Top confusion pairs (excluding diagonal)
    worst = []
    for i, t in enumerate(classes):
        for j, p in enumerate(classes):
            if i != j and cm[i, j] > 0:
                worst.append((int(cm[i, j]), t, p))
    worst.sort(reverse=True)
    return {"top_confusions": [{"count": c, "true": t, "pred": p} for c, t, p in worst[:10]]}


def save_pr_and_f1_classification(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_scores: Optional[np.ndarray],
    classes: List[str],
    out_dir: Path,
) -> Dict:
    weighted_f1 = f1_score(y_true, y_pred, average="weighted")
    micro_f1 = f1_score(y_true, y_pred, average="micro")

    plt.figure(figsize=(12, 6))
    if y_scores is not None and len(classes) >= 2:
        y_true_bin = label_binarize(y_true, classes=classes)
        precision, recall, _ = precision_recall_curve(y_true_bin.ravel(), y_scores.ravel())
        plt.plot(recall, precision, linewidth=2, label="Micro-average PR")
    else:
        plt.plot([0, 1], [1, 0], "--", label="No confidence scores provided")
    plt.title(f"Precision-Recall Curve (Weighted F1={weighted_f1:.4f}, Micro F1={micro_f1:.4f})")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "precision_recall_f1.png", dpi=220)
    plt.close()

    return {"weighted_f1": float(weighted_f1), "micro_f1": float(micro_f1)}


def save_pr_and_f1_detection(df: pd.DataFrame, out_dir: Path) -> Dict:
    epoch_col = first_existing(df, ["epoch"])
    p_col = first_existing(df, ["metrics/precision(B)"])
    r_col = first_existing(df, ["metrics/recall(B)"])
    m50_col = first_existing(df, ["metrics/mAP50(B)"])
    m95_col = first_existing(df, ["metrics/mAP50-95(B)"])
    if not epoch_col or not p_col or not r_col:
        return {}

    precision = df[p_col].to_numpy()
    recall = df[r_col].to_numpy()
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)

    fig, ax = plt.subplots(1, 2, figsize=(16, 6))
    ax[0].plot(recall, precision, marker="o", linewidth=2)
    ax[0].set_title("Precision-Recall Trajectory by Epoch")
    ax[0].set_xlabel("Recall")
    ax[0].set_ylabel("Precision")

    ax[1].plot(df[epoch_col], f1, label="F1", linewidth=2)
    if m50_col:
        ax[1].plot(df[epoch_col], df[m50_col], label="mAP@0.5", linewidth=2)
    if m95_col:
        ax[1].plot(df[epoch_col], df[m95_col], label="mAP@0.5:0.95", linewidth=2)
    ax[1].set_title("F1 and mAP over Epochs")
    ax[1].set_xlabel("Epoch")
    ax[1].set_ylabel("Score")
    ax[1].legend()

    plt.tight_layout()
    plt.savefig(out_dir / "precision_recall_f1.png", dpi=220)
    plt.close()

    return {
        "best_f1": float(np.max(f1)),
        "best_precision": float(np.max(precision)),
        "best_recall": float(np.max(recall)),
        "best_map50": float(np.max(df[m50_col])) if m50_col else None,
        "best_map50_95": float(np.max(df[m95_col])) if m95_col else None,
    }


def infer_classification_predictions(
    model_path: Path, val_dir: Path, out_csv: Path
) -> Path:
    model = YOLO(str(model_path))
    class_names = [str(v) for _, v in sorted(model.names.items())]
    rows = []
    image_paths = [p for p in val_dir.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}]
    for img_path in image_paths:
        true_label = img_path.parent.name
        pred = model.predict(str(img_path), imgsz=32, verbose=False)[0]
        probs = pred.probs
        top_idx = int(probs.top1)
        pred_label = class_names[top_idx]
        row = {"image_path": str(img_path), "true_label": true_label, "pred_label": pred_label}
        prob_values = probs.data.detach().cpu().numpy()
        for i, c in enumerate(class_names):
            row[f"score_{c}"] = float(prob_values[i])
        rows.append(row)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    return out_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize SmartPark training results")
    parser.add_argument("--run-dir", required=True, help="Path containing results.csv")
    parser.add_argument("--task", choices=["classify", "detect", "auto"], default="auto")
    parser.add_argument("--predictions-csv", default=None, help="CSV with true_label,pred_label[,score_*]")
    parser.add_argument("--model-path", default=None, help="Classification model path to auto-build predictions CSV")
    parser.add_argument("--val-dir", default=None, help="Validation dir train/val/<class> for classification")
    parser.add_argument("--out-dir", default="reports/figures")
    parser.add_argument("--summary-json", default="reports/figures/metrics_summary.json")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir)
    ensure_output_dir(out_dir)

    results_csv = run_dir / "results.csv"
    if not results_csv.exists():
        raise FileNotFoundError(f"Không tìm thấy results.csv trong {run_dir}")

    df = pd.read_csv(results_csv)
    df = normalize_columns(df)

    task = args.task
    if task == "auto":
        if "metrics/accuracy_top1" in df.columns:
            task = "classify"
        elif "metrics/precision(B)" in df.columns:
            task = "detect"
        else:
            task = "classify"

    save_loss_chart(df, out_dir)
    save_accuracy_chart(df, out_dir)

    summary: Dict = {"task": task, "run_dir": str(run_dir), "figures_dir": str(out_dir)}

    if task == "classify":
        pred_csv = Path(args.predictions_csv) if args.predictions_csv else None
        if (pred_csv is None or not pred_csv.exists()) and args.model_path and args.val_dir:
            pred_csv = out_dir / "classification_predictions.csv"
            infer_classification_predictions(Path(args.model_path), Path(args.val_dir), pred_csv)
        if pred_csv and pred_csv.exists():
            y_true, y_pred, y_scores, classes = load_predictions_csv(pred_csv)
            summary.update(save_confusion_matrix(y_true, y_pred, classes, out_dir))
            summary.update(save_pr_and_f1_classification(y_true, y_pred, y_scores, classes, out_dir))
        else:
            # If predictions not available, create placeholder from existing metrics only.
            plt.figure(figsize=(12, 6))
            plt.text(
                0.02,
                0.6,
                "Confusion matrix cần file --predictions-csv\n"
                "định dạng: true_label,pred_label,score_<class>...",
                fontsize=13,
            )
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(out_dir / "confusion_matrix_36x36.png", dpi=220)
            plt.close()

            plt.figure(figsize=(12, 6))
            plt.text(
                0.02,
                0.6,
                "PR/F1 cho classification cần confidence score theo class\n"
                "(score_<class>) trong predictions CSV.",
                fontsize=13,
            )
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(out_dir / "precision_recall_f1.png", dpi=220)
            plt.close()
    else:
        summary.update(save_pr_and_f1_detection(df, out_dir))
        # Detect task does not generate 36x36 matrix by default.
        plt.figure(figsize=(12, 6))
        plt.text(
            0.02,
            0.6,
            "Confusion matrix 36x36 áp dụng cho bài toán classify ký tự.\n"
            "YOLO detect dùng PR/F1/mAP để đánh giá chính.",
            fontsize=13,
        )
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(out_dir / "confusion_matrix_36x36.png", dpi=220)
        plt.close()

    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved charts to: {out_dir}")
    print(f"Saved summary: {summary_path}")


if __name__ == "__main__":
    main()
