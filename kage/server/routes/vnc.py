"""VNC connection and WebSocket streaming routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, WebSocket

from kage.core.instance import InstanceConfig
from kage.server.websockify_proxy import forward_vnc_websocket_to_tcp

logger = logging.getLogger("kage.vnc")
router = APIRouter(tags=["vnc"])


@router.get("/api/v1/instances/{name}/vnc/info")
async def get_vnc_info(name: str):
    """Retrieve VNC and noVNC port information for an instance."""
    inst = InstanceConfig.load(name)
    if not inst or not inst.ports:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")

    return {
        "name": name,
        "vnc_port": inst.ports.vnc,
        "novnc_port": inst.ports.novnc,
        "api_port": inst.ports.api,
        "websocket_url": f"/ws/vnc/{name}",
    }


@router.websocket("/ws/vnc/{name}")
async def vnc_websocket_endpoint(websocket: WebSocket, name: str):
    """Native WebSocket-to-TCP VNC stream proxy."""
    inst = InstanceConfig.load(name)
    if not inst or not inst.ports:
        await websocket.close(code=1008, reason=f"Instance '{name}' not found")
        return

    await forward_vnc_websocket_to_tcp(
        websocket=websocket,
        vnc_host="127.0.0.1",
        vnc_port=inst.ports.vnc,
    )
