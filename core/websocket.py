import asyncio
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("core.websocket")

class WebSocketManager:
    """
    Quản lý tập trung các kết nối WebSocket và broadcast tin nhắn thread-safe.
    Dùng để tránh lỗi Circular Import giữa api_server và router.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.event_loop = None

    def set_loop(self, loop):
        """Lưu event loop của thread chính."""
        self.event_loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[WS] Client kết nối. Tổng: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"[WS] Client ngắt. Còn: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        """Broadcast data tới tất cả WebSocket clients (async)."""
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        
        for ws in dead:
            self.disconnect(ws)

    def broadcast_threadsafe(self, data: dict):
        """Thread-safe broadcast từ background threads (sync)."""
        if self.event_loop and self.event_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(data), self.event_loop)
        else:
            logger.warning("[WS] Event loop không khả dụng — bỏ qua broadcast")

# Instance duy nhất dùng toàn hệ thống
ws_manager = WebSocketManager()
