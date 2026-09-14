"""GUI automation and accessibility endpoints."""

from __future__ import annotations

from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from kage.core.instance import InstanceConfig

router = APIRouter(prefix="/instances/{name}/gui", tags=["gui"])


class ClickRequest(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    node_id: Optional[str] = None
    button: int = 1
    double: bool = False


class TypeRequest(BaseModel):
    text: Optional[str] = None
    keys: Optional[List[str]] = None
    delay_ms: int = 12


class DragRequest(BaseModel):
    start_x: int
    start_y: int
    end_x: int
    end_y: int


class ScrollRequest(BaseModel):
    direction: str = "down"
    clicks: int = 3


def _get_guest_base_url(name: str) -> str:
    inst = InstanceConfig.load(name)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")
    if not inst.ports:
        raise HTTPException(status_code=400, detail="Instance has no port mappings")
    return f"http://127.0.0.1:{inst.ports.guest_agent}"


@router.get("/tree")
async def get_accessibility_tree(name: str):
    """Retrieve structured AT-SPI2 accessibility tree from guest."""
    base_url = _get_guest_base_url(name)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{base_url}/gui/tree")
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Cannot reach in-guest agent. Ensure VM has booted and guest agent is active.",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/click")
async def click(name: str, req: ClickRequest):
    """Synthesize mouse click by coordinates (x, y) or resolve node_id center."""
    base_url = _get_guest_base_url(name)
    x = req.x
    y = req.y

    # If node_id was provided instead of coordinates, fetch tree and find center
    if (x is None or y is None) and req.node_id:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                tree_resp = await client.get(f"{base_url}/gui/tree")
                tree_data = tree_resp.json().get("tree", {})

                # Find node recursively
                def find_node(node: dict, target_id: str) -> Optional[dict]:
                    if node.get("node_id") == target_id:
                        return node
                    for ch in node.get("children", []):
                        found = find_node(ch, target_id)
                        if found:
                            return found
                    return None

                target_node = find_node(tree_data, req.node_id)
                if target_node and "center" in target_node:
                    x = target_node["center"]["x"]
                    y = target_node["center"]["y"]
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Node '{req.node_id}' not found in current accessibility tree",
                    )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed resolving node_id: {e}")

    if x is None or y is None:
        raise HTTPException(
            status_code=400,
            detail="Either (x, y) coordinates or valid node_id must be provided",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{base_url}/gui/click",
                json={"x": x, "y": y, "button": req.button, "double": req.double},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/type")
async def type_text(name: str, req: TypeRequest):
    """Synthesize keystrokes or text typing inside guest."""
    base_url = _get_guest_base_url(name)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{base_url}/gui/type",
                json={"text": req.text, "keys": req.keys, "delay_ms": req.delay_ms},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/drag")
async def drag(name: str, req: DragRequest):
    """Synthesize mouse drag operation."""
    base_url = _get_guest_base_url(name)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{base_url}/gui/drag",
                json={
                    "start_x": req.start_x,
                    "start_y": req.start_y,
                    "end_x": req.end_x,
                    "end_y": req.end_y,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/scroll")
async def scroll(name: str, req: ScrollRequest):
    """Synthesize mouse scroll wheel."""
    base_url = _get_guest_base_url(name)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{base_url}/gui/scroll",
                json={"direction": req.direction, "clicks": req.clicks},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/screenshot")
async def screenshot(name: str, format: str = Query("binary", enum=["binary", "base64"])):
    """Capture live screenshot of the guest desktop."""
    base_url = _get_guest_base_url(name)
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{base_url}/gui/screenshot?format={format}")
            resp.raise_for_status()
            if format == "base64":
                return resp.json()
            else:
                return Response(content=resp.content, media_type="image/png")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
