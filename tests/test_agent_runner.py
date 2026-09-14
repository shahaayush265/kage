"""Tests for LiteLLM tool definitions and autonomous agent execution loop."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kage.agent.runner import AgentRunner
from kage.agent.tools import TOOL_DEFINITIONS
from kage.core.config import get_settings
from kage.core.instance import InstanceConfig, InstancePorts, InstanceStatus


def test_tool_definitions_validity():
    assert len(TOOL_DEFINITIONS) >= 5
    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "execute_shell" in names
    assert "get_accessibility_tree" in names
    assert "mouse_click" in names
    assert "type_text" in names
    assert "take_screenshot" in names
    assert "finish_task" in names


@pytest.mark.asyncio
async def test_agent_runner_loop_mocked(tmp_path):
    settings = get_settings()
    settings.kage_home = tmp_path / ".kage"
    settings.ensure_directories()

    ports = InstancePorts(
        ssh=2222,
        vnc=5900,
        novnc=6080,
        api=8000,
        guest_agent=9000,
        qmp=4444,
    )
    inst = InstanceConfig(
        name="test-agent-vm",
        status=InstanceStatus.RUNNING,
        ports=ports,
    )
    inst.save()

    runner = AgentRunner(instance_name="test-agent-vm", model="mock-model", max_steps=3)

    # Mock tool dispatch
    runner._dispatch_tool = AsyncMock(
        side_effect=[
            {"stdout": "test output", "stderr": "", "exit_code": 0},
            {"status": "finished", "answer": "Task completed successfully."},
        ]
    )

    # Mock LLM responses: 1st step calls execute_shell, 2nd step calls finish_task
    tool_call_1 = MagicMock()
    tool_call_1.id = "call_1"
    tool_call_1.function.name = "execute_shell"
    tool_call_1.function.arguments = '{"command": "echo test"}'
    tool_call_1.model_dump.return_value = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "execute_shell", "arguments": '{"command": "echo test"}'},
    }

    msg_1 = MagicMock()
    msg_1.content = "I will run echo test."
    msg_1.tool_calls = [tool_call_1]

    choice_1 = MagicMock()
    choice_1.message = msg_1

    resp_1 = MagicMock()
    resp_1.choices = [choice_1]

    tool_call_2 = MagicMock()
    tool_call_2.id = "call_2"
    tool_call_2.function.name = "finish_task"
    tool_call_2.function.arguments = '{"answer": "Done!"}'
    tool_call_2.model_dump.return_value = {
        "id": "call_2",
        "type": "function",
        "function": {"name": "finish_task", "arguments": '{"answer": "Done!"}'},
    }

    msg_2 = MagicMock()
    msg_2.content = "Finished task."
    msg_2.tool_calls = [tool_call_2]

    choice_2 = MagicMock()
    choice_2.message = msg_2

    resp_2 = MagicMock()
    resp_2.choices = [choice_2]

    runner.router.complete_async = AsyncMock(side_effect=[resp_1, resp_2])

    result = await runner.run_async("Please test the shell")

    assert result["success"] is True
    assert result["final_answer"] == "Done!"
    assert len(result["steps"]) == 2
    assert result["steps"][0]["tool_name"] == "execute_shell"
    assert result["steps"][1]["tool_name"] == "finish_task"
