"""Agent orchestration routes for autonomous task execution on VM instances."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from kage.core.config import get_settings
from kage.core.instance import InstanceConfig

router = APIRouter(prefix="/instances/{name}/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    max_steps: int = 15
    temperature: float = 0.2


class AgentStepResponse(BaseModel):
    step: int
    thought: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None


class AgentRunResponse(BaseModel):
    success: bool
    final_answer: str
    steps: List[AgentStepResponse]
    total_steps: int


@router.post("/run", response_model=AgentRunResponse)
async def run_agent_task(name: str, req: AgentRunRequest):
    """Execute an autonomous AI agent task on the instance."""
    inst = InstanceConfig.load(name)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{name}' not found")

    settings = get_settings()
    model = req.model or settings.default_model

    from kage.agent.runner import AgentRunner

    runner = AgentRunner(
        instance_name=name,
        model=model,
        max_steps=req.max_steps,
        temperature=req.temperature,
    )

    result = await runner.run_async(req.prompt)
    return AgentRunResponse(
        success=result["success"],
        final_answer=result["final_answer"],
        steps=[AgentStepResponse(**s) for s in result["steps"]],
        total_steps=len(result["steps"]),
    )


@router.websocket("/ws")
async def agent_websocket_stream(websocket: WebSocket, name: str):
    """Real-time bidirectional WebSocket for interactive agent execution."""
    await websocket.accept()

    inst = InstanceConfig.load(name)
    if not inst:
        await websocket.send_json({"type": "error", "message": f"Instance '{name}' not found"})
        await websocket.close()
        return

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type", "prompt")

            if msg_type == "prompt":
                prompt = msg.get("prompt", "")
                model = msg.get("model") or get_settings().default_model
                max_steps = int(msg.get("max_steps", 15))

                from kage.agent.runner import AgentRunner

                runner = AgentRunner(
                    instance_name=name,
                    model=model,
                    max_steps=max_steps,
                )

                async def on_step(step_data: dict):
                    await websocket.send_json({"type": "step", "data": step_data})

                result = await runner.run_async(prompt, step_callback=on_step)
                await websocket.send_json({"type": "complete", "data": result})

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
