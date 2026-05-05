"""
SmartPark retraining orchestrator.

Features:
- Tuned settings for RTX 3060
- Epoch callback every 10 epochs to render charts
- Final visualization + executive summary markdown
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict

import pandas as pd
import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
VIS_SCRIPT = ROOT / "scripts" / "visualize_results.py"


def run_visualization(run_dir: Path, task: str, out_dir: Path) -> None:
    cmd = [
        sys.executable,
        str(VIS_SCRIPT),
        "--run-dir",
        str(run_dir),
        "--task",
        task,
        "--out-dir",
        str(out_dir),
        "--summary-json",
        str(out_dir / "metrics_summary.json"),
    ]
    subprocess.run(cmd, check=False)


def build_executive_summary(run_dir: Path, out_md: Path, task: str) -> None:
    results_csv = run_dir / "results.csv"
    if not results_csv.exists():
        return
    df = pd.read_csv(results_csv)
    df.columns = [c.strip() for c in df.columns]

    lines = ["# SmartPark Executive Summary", ""]
    lines.append(f"- Run dir: `{run_dir}`")
    lines.append(f"- Task: `{task}`")
    lines.append("")

    if task == "classify" and "train/loss" in df.columns and "val/loss" in df.columns:
        train_start, train_end = float(df["train/loss"].iloc[0]), float(df["train/loss"].iloc[-1])
        val_start, val_end = float(df["val/loss"].iloc[0]), float(df["val/loss"].iloc[-1])
        overfit_flag = val_end > float(df["val/loss"].min()) * 1.15
        lines.append("## 1) Đánh giá hội tụ Loss")
        lines.append(f"- Train loss: `{train_start:.4f} -> {train_end:.4f}`")
        lines.append(f"- Val loss: `{val_start:.4f} -> {val_end:.4f}`")
        lines.append(f"- Nhận định overfitting: `{'Có dấu hiệu' if overfit_flag else 'Chưa rõ ràng'}`")
        lines.append("")
    elif task == "detect":
        p = "metrics/precision(B)"
        r = "metrics/recall(B)"
        m50 = "metrics/mAP50(B)"
        m95 = "metrics/mAP50-95(B)"
        if p in df.columns and r in df.columns:
            f1 = 2 * df[p] * df[r] / (df[p] + df[r] + 1e-12)
            lines.append("## 1) Đánh giá hội tụ Loss và Detection Metrics")
            lines.append(f"- Best Precision: `{df[p].max():.4f}`")
            lines.append(f"- Best Recall: `{df[r].max():.4f}`")
            if m50 in df.columns:
                lines.append(f"- Best mAP@0.5: `{df[m50].max():.4f}`")
            if m95 in df.columns:
                lines.append(f"- Best mAP@0.5:0.95: `{df[m95].max():.4f}`")
            lines.append(f"- Best F1: `{f1.max():.4f}`")
            lines.append("")

    summary_json = ROOT / "reports" / "figures" / "metrics_summary.json"
    lines.append("## 2) Top ký tự yếu nhất (từ confusion matrix)")
    if summary_json.exists():
        data = json.loads(summary_json.read_text(encoding="utf-8"))
        top_conf = data.get("top_confusions", [])[:3]
        if top_conf:
            for item in top_conf:
                lines.append(f"- `{item['true']} -> {item['pred']}`: `{item['count']}` mẫu nhầm")
        else:
            lines.append("- Chưa có dữ liệu `top_confusions` (cần predictions CSV cho classify).")
    else:
        lines.append("- Chưa có metrics summary.")
    lines.append("")

    lines.append("## 3) Kết luận triển khai")
    if task == "detect" and "metrics/mAP50(B)" in df.columns:
        ready = df["metrics/mAP50(B)"].max() >= 0.95 and df.get("metrics/mAP50-95(B)", pd.Series([0])).max() >= 0.70
        lines.append(
            f"- Model v4.0: `{'Có thể pilot thực tế' if ready else 'Chưa đủ chuẩn production, cần cải thiện thêm'}`"
        )
    else:
        lines.append("- Quyết định production cần thêm confusion matrix + test thực địa ban ngày/ban đêm.")

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


def train_classification(args: argparse.Namespace) -> Path:
    device = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(args.model)

    vis_out = ROOT / "reports" / "figures"
    vis_out.mkdir(parents=True, exist_ok=True)

    def on_fit_epoch_end(trainer):
        epoch = trainer.epoch + 1
        if epoch % 10 == 0:
            run_visualization(Path(trainer.save_dir), "classify", vis_out)

    model.add_callback("on_fit_epoch_end", on_fit_epoch_end)

    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        device=device,
        project=args.project,
        name=args.name,
        batch=args.batch if device == 0 else max(8, args.batch // 2),
        lr0=args.lr0,
        patience=args.patience,
        save=True,
        save_period=10,
        plots=True,
        exist_ok=True,
        workers=0,
    )
    run_dir = Path("runs/classify") / args.project / args.name
    run_visualization(run_dir, "classify", vis_out)
    build_executive_summary(run_dir, ROOT / "reports" / "executive_summary.md", "classify")
    return run_dir


def train_detection(args: argparse.Namespace) -> Path:
    device = 0 if torch.cuda.is_available() else "cpu"
    model = YOLO(args.model)

    vis_out = ROOT / "reports" / "figures"
    vis_out.mkdir(parents=True, exist_ok=True)

    def on_fit_epoch_end(trainer):
        epoch = trainer.epoch + 1
        if epoch % 10 == 0:
            run_visualization(Path(trainer.save_dir), "detect", vis_out)

    model.add_callback("on_fit_epoch_end", on_fit_epoch_end)

    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        device=device,
        project=args.project,
        name=args.name,
        batch=args.batch if device == 0 else max(4, args.batch // 2),
        lr0=args.lr0,
        patience=args.patience,
        save=True,
        save_period=10,
        plots=True,
        exist_ok=True,
        workers=4 if device == 0 else 0,
    )
    run_dir = Path("runs/detect") / args.project / args.name
    run_visualization(run_dir, "detect", vis_out)
    build_executive_summary(run_dir, ROOT / "reports" / "executive_summary.md", "detect")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrain SmartPark models with visualization hooks")
    parser.add_argument("--task", choices=["classify", "detect"], required=True)
    parser.add_argument("--model", default="yolov8n-cls.pt")
    parser.add_argument("--data", required=True)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=32)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--lr0", type=float, default=0.003)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--project", default="smartpark_v4")
    parser.add_argument("--name", default="baseline")
    args = parser.parse_args()

    if args.task == "classify":
        run_dir = train_classification(args)
    else:
        if args.model == "yolov8n-cls.pt":
            args.model = "yolov8n.pt"
        if args.imgsz == 32:
            args.imgsz = 640
        if args.batch == 64:
            args.batch = 16
        run_dir = train_detection(args)

    print(f"Training completed. Run directory: {run_dir}")
    print("Figures saved in reports/figures")
    print("Executive summary saved in reports/executive_summary.md")


if __name__ == "__main__":
    main()
