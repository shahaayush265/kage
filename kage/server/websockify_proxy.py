"""Native asynchronous WebSocket-to-TCP bridge for noVNC desktop streaming."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("kage.vnc_proxy")


async def forward_vnc_websocket_to_tcp(
    websocket: WebSocket,
    vnc_host: str = "127.0.0.1",
    vnc_port: int = 5900,
) -> None:
    """Bridges a FastAPI WebSocket connection to a local QEMU VNC TCP port."""
    await websocket.accept(subprotocol="binary")

    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None

    try:
        reader, writer = await asyncio.open_connection(vnc_host, vnc_port)
    except Exception as e:
        logger.error(f"Failed to connect to VNC target {vnc_host}:{vnc_port}: {e}")
        await websocket.close(code=1011, reason=f"Cannot reach VNC server: {e}")
        return

    stop_event = asyncio.Event()

    async def ws_to_tcp():
        """Receive binary frames from browser WebSocket and write to VNC TCP socket."""
        try:
            while not stop_event.is_set():
                data = await websocket.receive_bytes()
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except WebSocketDisconnect:
            pass
        except Exception as err:
            logger.debug(f"WS -> TCP error: {err}")
        finally:
            stop_event.set()

    async def tcp_to_ws():
        """Receive bytes from VNC TCP socket and send binary frames to browser WebSocket."""
        try:
            while not stop_event.is_set():
                data = await reader.read(65536)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception as err:
            logger.debug(f"TCP -> WS error: {err}")
        finally:
            stop_event.set()

    try:
        await asyncio.gather(ws_to_tcp(), tcp_to_ws(), return_exceptions=True)
    finally:
        stop_event.set()
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
