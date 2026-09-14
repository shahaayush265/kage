"""Shell execution endpoints bridging host to in-guest agent with SSH fallback."""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kage.core.config import get_or_create_ssh_key
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
    """Execute a bash command inside the guest VM (tries guest agent HTTP, falls back to SSH)."""
    inst = InstanceConfig.load(name)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")

    if not inst.ports:
        raise HTTPException(status_code=400, detail="Instance has no port mappings")

    guest_url = f"http://127.0.0.1:{inst.ports.guest_agent}/shell/exec"

    # 1. Try Guest Agent HTTP first with short timeout
    try:
        async with httpx.AsyncClient(timeout=min(req.timeout, 5.0)) as client:
            resp = await client.post(
                guest_url,
                json={
                    "command": req.command,
                    "cwd": req.cwd,
                    "timeout": req.timeout,
                    "env": req.env,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return ShellExecResponse(
                    stdout=data.get("stdout", ""),
                    stderr=data.get("stderr", ""),
                    exit_code=data.get("exit_code", 0),
                    duration=data.get("duration", 0.0),
                    timed_out=data.get("timed_out", False),
                )
    except Exception:
        # Fall back to direct SSH
        pass

    # 2. SSH Execution Fallback
    priv_key, _ = get_or_create_ssh_key()
    start_time = time.time()

    cmd_to_run = req.command
    if req.cwd:
        cmd_to_run = f"cd {req.cwd} && {cmd_to_run}"

    ssh_cmd = [
        "ssh",
        "-p",
        str(inst.ports.ssh),
        "-i",
        str(priv_key),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "ConnectTimeout=5",
        "kage@127.0.0.1",
        f"bash -c {cmd_to_run!r}",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ssh_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=req.timeout
            )
            duration = time.time() - start_time
            return ShellExecResponse(
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                exit_code=proc.returncode or 0,
                duration=round(duration, 3),
                timed_out=False,
            )
        except asyncio.TimeoutError:
            proc.kill()
            duration = time.time() - start_time
            return ShellExecResponse(
                stdout="",
                stderr=f"Command timed out after {req.timeout} seconds",
                exit_code=124,
                duration=round(duration, 3),
                timed_out=True,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SSH execution failed: {e}")
