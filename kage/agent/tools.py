"""LiteLLM / OpenAI compatible tool schemas for VM interaction."""

from typing import Any, Dict, List

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click a GUI button, icon, menu item, or element by its visible text label, role, or accessibility node_id (e.g. text='Terminal Emulator', text='Applications', text='Save').",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Visible text label or partial name of the GUI widget to click.",
                    },
                    "role": {
                        "type": "string",
                        "description": "Optional widget role filter (e.g. 'push button', 'menu', 'toggle button', 'window').",
                    },
                    "node_id": {
                        "type": "string",
                        "description": "Exact accessibility node ID (e.g. 'node_12' or 'win_4').",
                    },
                    "button": {
                        "type": "integer",
                        "description": "Mouse button: 1 for left click, 2 for middle, 3 for right click.",
                        "default": 1,
                    },
                    "double": {
                        "type": "boolean",
                        "description": "True for double-click.",
                        "default": False,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "Launch a desktop application inside the VM (e.g. 'terminal', 'browser', 'thunar', 'appfinder', 'editor', 'settings').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Application name or alias (e.g. 'terminal', 'thunar', 'xfce4-appfinder', 'firefox', 'mousepad').",
                    },
                },
                "required": ["app_name"],
            },
        },
    },
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
            "description": "Retrieve the AT-SPI2 accessibility tree hierarchy of all active GUI windows and clickable widgets with bounding boxes and center coordinates.",
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
            "description": "Click at specific (x, y) desktop coordinates on the screen.",
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
                "required": ["x", "y"],
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
            "description": "Press a key combination or special key (e.g. 'ctrl+c', 'Return', 'alt+F4', 'Escape', 'Super').",
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
