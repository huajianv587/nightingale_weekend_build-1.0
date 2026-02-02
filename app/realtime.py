
from typing import Dict, Set
from fastapi import WebSocket
import asyncio

class ConnectionManager:
    def __init__(self):
        self.thread: Dict[int, Set[WebSocket]] = {}
        self.clinic: Dict[int, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect_thread(self, thread_id: int, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.thread.setdefault(thread_id, set()).add(ws)

    async def connect_clinic(self, clinic_id: int, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.clinic.setdefault(clinic_id, set()).add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            for m in (self.thread, self.clinic):
                for k in list(m.keys()):
                    if ws in m[k]:
                        m[k].remove(ws)
                        if not m[k]:
                            del m[k]

    async def broadcast_thread(self, thread_id: int, payload: dict):
        for ws in list(self.thread.get(thread_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    async def broadcast_clinic(self, clinic_id: int, payload: dict):
        for ws in list(self.clinic.get(clinic_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                pass

manager = ConnectionManager()
