"""Instance lifecycle and status management API routes."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kage.core.instance import InstanceConfig, InstanceMetrics, InstanceStatus
from kage.core.process import ProcessManager
from kage.hypervisor.qemu import QEMURunner

router = APIRouter(prefix="/instances", tags=["instances"])


class InstanceResponse(BaseModel):
    name: str
    status: str
    cpus: int
    memory_mb: int
    disk_size_gb: int
    shared_dir: str | None
    ports: Dict[str, int] | None
    qemu_pid: int | None
    api_pid: int | None
    created_at: str
    updated_at: str
    metrics: InstanceMetrics


@router.get("", response_model=List[InstanceResponse])
async def list_instances():
    """List all registered instances with status and real-time metrics."""
    instances = InstanceConfig.list_all()
    results = []
    for inst in instances:
        # Check active status
        if inst.qemu_pid and not ProcessManager.is_alive(inst.qemu_pid):
            if inst.status == InstanceStatus.RUNNING:
                inst.status = InstanceStatus.STOPPED
                inst.save()

        metrics = ProcessManager.get_metrics(inst.qemu_pid)
        results.append(
            InstanceResponse(
                name=inst.name,
                status=inst.status.value,
                cpus=inst.cpus,
                memory_mb=inst.memory_mb,
                disk_size_gb=inst.disk_size_gb,
                shared_dir=inst.shared_dir,
                ports=inst.ports.to_dict() if inst.ports else None,
                qemu_pid=inst.qemu_pid,
                api_pid=inst.api_pid,
                created_at=inst.created_at,
                updated_at=inst.updated_at,
                metrics=metrics,
            )
        )
    return results


@router.get("/{name}", response_model=InstanceResponse)
async def get_instance(name: str):
    """Get detailed state and metrics of a single instance."""
    inst = InstanceConfig.load(name)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")

    metrics = ProcessManager.get_metrics(inst.qemu_pid)
    return InstanceResponse(
        name=inst.name,
        status=inst.status.value,
        cpus=inst.cpus,
        memory_mb=inst.memory_mb,
        disk_size_gb=inst.disk_size_gb,
        shared_dir=inst.shared_dir,
        ports=inst.ports.to_dict() if inst.ports else None,
        qemu_pid=inst.qemu_pid,
        api_pid=inst.api_pid,
        created_at=inst.created_at,
        updated_at=inst.updated_at,
        metrics=metrics,
    )


@router.post("/{name}/stop")
async def stop_instance(name: str):
    """Halt an active VM instance."""
    inst = InstanceConfig.load(name)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")

    success = QEMURunner.stop(inst)
    return {"name": name, "status": "Stopped", "success": success}
