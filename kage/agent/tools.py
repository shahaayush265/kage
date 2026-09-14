"""LiteLLM / OpenAI compatible tool schemas for VM interaction."""

from typing import Any, Dict, List

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Execute a bash shell command inside the guest VM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to run.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory path inside VM (default: /home/kage).",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_accessibility_tree",
            "description": "Retrieve the AT-SPI2 accessibility tree hierarchy of active GUI windows and widgets.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "Click at specific (x, y) desktop coordinates or on an accessibility node_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "X coordinate on screen.",
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate on screen.",
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Target accessibility node ID (e.g. 'node_3' or 'btn_submit').",
                    },
                    "button": {
                        "type": "integer",
                        "description": "Mouse button: 1 for left click, 2 for middle, 3 for right click.",
                        "default": 1,
                    },
                    "double": {
                        "type": "boolean",
                        "description": "True to perform a double-click.",
                        "default": False,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_drag",
            "description": "Perform a mouse drag operation from starting coordinates to ending coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_x": {"type": "integer"},
                    "start_y": {"type": "integer"},
                    "end_x": {"type": "integer"},
                    "end_y": {"type": "integer"},
                },
                "required": ["start_x", "start_y", "end_x", "end_y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type a string of text into the currently focused GUI window or input field.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The exact text characters to type.",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "key_combination",
            "description": "Press a key combination or special key (e.g. 'ctrl+c', 'Return', 'alt+F4', 'Escape').",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Key combo string like 'ctrl+t', 'Return', 'Super', 'alt+Tab'.",
                    },
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Capture a live visual screenshot of the guest desktop for visual verification.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_task",
            "description": "Conclude task execution and provide the final answer or summary to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "Final response summary explaining what was accomplished.",
                    },
                },
                "required": ["answer"],
            },
        },
    },
]
