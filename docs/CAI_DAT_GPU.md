# Cài PyTorch để dùng GPU (RTX 3060) cho YOLOv8

Hiện tại máy bạn **có NVIDIA RTX 3060** (`nvidia-smi` OK) nhưng PyTorch đang là **bản CPU-only**: `2.9.1+cpu`, nên `torch.cuda.is_available()` = `False`.

## Nên chạy CPU hay GPU?

- **Nên chạy GPU**: nhanh hơn CPU rất nhiều (thường 5–10x+). Với dataset ~2.3k ảnh, 50 epoch trên RTX 3060 thường ~30–60 phút (tuỳ cấu hình), còn CPU có thể vài giờ.

## Cách chuyển sang GPU (Windows)

### 1) Dừng training CPU đang chạy (nếu đang chạy)

Trong PowerShell:

```powershell
Get-Process python
```

Nếu thấy process đang train, dừng (thay `<PID>` bằng ID):

```powershell
Stop-Process -Id <PID> -Force
```

### 2) Cài PyTorch có CUDA (khuyến nghị CUDA 12.1 wheels)

Chạy:

```powershell
py -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

> Nếu lệnh trên báo lỗi, cho mình output để mình chọn bản cu118/cu124 phù hợp.

### 3) Kiểm tra GPU đã nhận chưa

```powershell
py -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU')"
```

Kỳ vọng: `CUDA: True` và in ra tên GPU.

### 4) Train lại bằng GPU

Trong `train_yolo.py`, script đã tự chọn GPU nếu `torch.cuda.is_available()` là True. Chạy:

```powershell
py train_yolo.py
```

## Nếu vẫn muốn train CPU

Không cần cài CUDA. Giữ `batch=4` như hiện tại để tránh tràn RAM và cứ chạy `py train_yolo.py`.

