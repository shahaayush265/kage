"""Shell execution endpoints bridging host to in-guest agent."""

from __future__ import annotations

from typing import Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kage.core.instance import InstanceConfig

router = APIRouter(prefix="/instances/{name}/shell", tags=["shell"])


class ShellExecRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: float = 60.0
    env: Optional[Dict[str, str]] = None


class ShellExecResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    timed_out: bool


@router.post("/exec", response_model=ShellExecResponse)
async def execute_shell_command(name: str, req: ShellExecRequest):
    """Execute a bash command inside the guest VM."""
    inst = InstanceConfig.load(name)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")

    if not inst.ports:
        raise HTTPException(status_code=400, detail="Instance has no port mappings")

    guest_url = f"http://127.0.0.1:{inst.ports.guest_agent}/shell/exec"

    async with httpx.AsyncClient(timeout=req.timeout + 5.0) as client:
        try:
            resp = await client.post(
                guest_url,
                json={
                    "command": req.command,
                    "cwd": req.cwd,
                    "timeout": req.timeout,
                    "env": req.env,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return ShellExecResponse(
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                exit_code=data.get("exit_code", 0),
                duration=data.get("duration", 0.0),
                timed_out=data.get("timed_out", False),
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Cannot connect to guest agent at {guest_url}. Is the VM running and booted?",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Guest execution failed: {e}")
