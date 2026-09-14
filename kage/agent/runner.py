"""Autonomous ReAct agent execution loop for VM automation."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

import httpx

from kage.agent.prompts import SYSTEM_PROMPT
from kage.agent.router import LLMRouter
from kage.agent.tools import TOOL_DEFINITIONS
from kage.core.config import get_settings
from kage.core.instance import InstanceConfig

logger = logging.getLogger("kage.agent")


class AgentRunner:
    """Executes multi-step autonomous agent tasks against a Kage VM instance."""

    def __init__(
        self,
        instance_name: str,
        model: Optional[str] = None,
        max_steps: int = 15,
        temperature: float = 0.2,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        settings = get_settings()
        target_model = model or settings.default_model

        # Auto-resolve api_key and api_base from configured provider if not passed
        resolved_key = api_key
        resolved_base = api_base
        active_prov = settings.get_provider()
        if active_prov:
            if not resolved_key and active_prov.api_key:
                resolved_key = active_prov.api_key
            if not resolved_base and active_prov.api_base:
                resolved_base = active_prov.api_base

        self.instance_name = instance_name
        self.model = target_model
        self.max_steps = max_steps
        self.temperature = temperature
        self.router = LLMRouter(
            model=target_model,
            temperature=temperature,
            api_key=resolved_key,
            api_base=resolved_base,
        )

    def _get_guest_base_url(self) -> str:
        inst = InstanceConfig.load(self.instance_name)
        if not inst:
            raise RuntimeError(f"Instance '{self.instance_name}' not found")
        if not inst.ports:
            raise RuntimeError(f"Instance '{self.instance_name}' has no allocated ports")
        return f"http://127.0.0.1:{inst.ports.guest_agent}"

    async def _dispatch_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """Execute tool call on the guest VM via guest agent HTTP endpoint."""
        base_url = self._get_guest_base_url()

        async with httpx.AsyncClient(timeout=60.0) as client:
            if name == "execute_shell":
                cmd = args.get("command", "")
                cwd = args.get("cwd")
                resp = await client.post(
                    f"{base_url}/shell/exec", json={"command": cmd, "cwd": cwd}
                )
                return resp.json()

            elif name == "get_accessibility_tree":
                resp = await client.get(f"{base_url}/gui/tree")
                data = resp.json()
                return data.get("compact_text", data)

            elif name == "mouse_click":
                resp = await client.post(f"{base_url}/gui/click", json=args)
                return resp.json()

            elif name == "mouse_drag":
                resp = await client.post(f"{base_url}/gui/drag", json=args)
                return resp.json()

            elif name == "type_text":
                text = args.get("text", "")
                resp = await client.post(f"{base_url}/gui/type", json={"text": text})
                return resp.json()

            elif name == "key_combination":
                keys = args.get("keys", "")
                resp = await client.post(f"{base_url}/gui/type", json={"keys": [keys]})
                return resp.json()

            elif name == "take_screenshot":
                resp = await client.get(f"{base_url}/gui/screenshot?format=base64")
                return {"status": "success", "screenshot_captured": True}

            elif name == "finish_task":
                return {"status": "finished", "answer": args.get("answer", "")}

            else:
                return {"error": f"Unknown tool name '{name}'"}

    async def run_async(
        self,
        prompt: str,
        step_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        """Run the autonomous agent task loop."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        steps: List[Dict[str, Any]] = []
        final_answer = ""
        success = False

        for step_idx in range(1, self.max_steps + 1):
            try:
                response = await self.router.complete_async(
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                )
            except Exception as e:
                logger.error(f"LLM completion error at step {step_idx}: {e}")
                err_step = {
                    "step": step_idx,
                    "thought": f"Error calling model: {e}",
                    "tool_name": None,
                    "tool_args": None,
                    "tool_result": None,
                }
                steps.append(err_step)
                if step_callback:
                    await step_callback(err_step)
                final_answer = f"Agent failed due to LLM error: {e}"
                break

            choice = response.choices[0]
            msg = choice.message
            content = msg.content or ""
            tool_calls = getattr(msg, "tool_calls", None)

            # Append assistant message to history
            assistant_msg_dict: Dict[str, Any] = {"role": "assistant", "content": content}
            if tool_calls:
                assistant_msg_dict["tool_calls"] = [
                    tc.model_dump() if hasattr(tc, "model_dump") else dict(tc) for tc in tool_calls
                ]
            messages.append(assistant_msg_dict)

            if not tool_calls:
                # Agent responded with final text without tool call
                final_answer = content
                success = True
                step_record = {
                    "step": step_idx,
                    "thought": content,
                    "tool_name": None,
                    "tool_args": None,
                    "tool_result": None,
                }
                steps.append(step_record)
                if step_callback:
                    await step_callback(step_record)
                break

            # Execute tool calls
            for tool_call in tool_calls:
                t_name = tool_call.function.name
                t_args_str = tool_call.function.arguments
                try:
                    t_args = json.loads(t_args_str) if isinstance(t_args_str, str) else t_args_str
                except Exception:
                    t_args = {}

                # Execute tool
                try:
                    t_result = await self._dispatch_tool(t_name, t_args)
                except Exception as ex:
                    t_result = {"error": f"Tool execution failed: {ex}"}

                step_record = {
                    "step": step_idx,
                    "thought": content,
                    "tool_name": t_name,
                    "tool_args": t_args,
                    "tool_result": t_result,
                }
                steps.append(step_record)
                if step_callback:
                    await step_callback(step_record)

                # Append tool observation
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": t_name,
                        "content": json.dumps(t_result),
                    }
                )

                if t_name == "finish_task":
                    final_answer = t_args.get("answer", "")
                    success = True
                    break

            if success:
                break

        if not final_answer and steps:
            final_answer = steps[-1].get("thought") or "Task stopped at step limit."

        return {
            "success": success,
            "final_answer": final_answer,
            "steps": steps,
            "total_steps": len(steps),
        }
