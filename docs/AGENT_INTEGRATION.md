# Kage Agent Integration Guide

Learn how to connect custom AI frameworks (LangChain, AutoGen, CrewAI, LlamaIndex, or custom Python agents) directly to Kage VM instances.

---

## 1. Python SDK / HTTP Client Example

```python
import httpx


class KageVM:
    def __init__(self, instance_name: str, api_base: str = "http://127.0.0.1:8000"):
        self.instance_name = instance_name
        self.api_base = f"{api_base}/api/v1/instances/{instance_name}"
        self.client = httpx.Client(timeout=30.0)

    def exec(self, command: str, cwd: str = "/home/kage") -> str:
        resp = self.client.post(
            f"{self.api_base}/shell/exec", json={"command": command, "cwd": cwd}
        )
        resp.raise_for_status()
        return resp.json()["stdout"]

    def get_ui_tree(self) -> dict:
        resp = self.client.get(f"{self.api_base}/gui/tree")
        resp.raise_for_status()
        return resp.json()

    def click(self, x: int, y: int):
        resp = self.client.post(f"{self.api_base}/gui/click", json={"x": x, "y": y})
        resp.raise_for_status()
        return resp.json()

    def screenshot(self) -> bytes:
        resp = self.client.get(f"{self.api_base}/gui/screenshot?format=binary")
        resp.raise_for_status()
        return resp.content


# Usage
vm = KageVM("alpha")
output = vm.exec("ls -la /workspace")
print(output)
```

---

## 2. OpenAI / LiteLLM Function Calling Definition

```python
import litellm

tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Execute bash command in VM",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    }
]

response = litellm.completion(
    model="claude-3-7-sonnet-20250219",
    messages=[{"role": "user", "content": "Check python version"}],
    tools=tools,
)
```

---

## 3. LangChain Tool Integration

```python
from langchain.tools import tool


@tool
def kage_shell_executor(command: str) -> str:
    """Executes a bash command inside the Kage Linux VM."""
    import httpx

    resp = httpx.post(
        "http://127.0.0.1:8000/api/v1/instances/alpha/shell/exec", json={"command": command}
    )
    return resp.json().get("stdout", "")
```
