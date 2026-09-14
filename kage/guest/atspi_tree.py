"""AT-SPI2 accessibility tree extractor, parser, and serializer for GUI automation."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Ensure system package path is included so pyatspi can be imported
if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.append("/usr/lib/python3/dist-packages")


@dataclass
class AccessibilityNode:
    """Represents a single GUI element in the accessibility hierarchy."""

    node_id: str
    name: str
    role: str
    states: List[str] = field(default_factory=list)
    bounds: Dict[str, int] = field(
        default_factory=lambda: {"x": 0, "y": 0, "width": 0, "height": 0}
    )
    description: str = ""
    value: str = ""
    children: List[AccessibilityNode] = field(default_factory=list)

    @property
    def center(self) -> Dict[str, int]:
        try:
            x = int(self.bounds.get("x", 0) or 0)
            y = int(self.bounds.get("y", 0) or 0)
            w = int(self.bounds.get("width", 0) or 0)
            h = int(self.bounds.get("height", 0) or 0)
            return {"x": x + w // 2, "y": y + h // 2}
        except Exception:
            return {"x": 0, "y": 0}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": str(self.node_id),
            "name": str(self.name),
            "role": str(self.role),
            "states": [str(s) for s in self.states if s is not None],
            "bounds": {
                "x": int(self.bounds.get("x", 0) or 0),
                "y": int(self.bounds.get("y", 0) or 0),
                "width": int(self.bounds.get("width", 0) or 0),
                "height": int(self.bounds.get("height", 0) or 0),
            },
            "center": self.center,
            "description": str(self.description),
            "value": str(self.value),
            "children": [c.to_dict() for c in self.children],
        }

    def to_compact_str(self, depth: int = 0) -> str:
        """Format as a compact indentation-based string with center coordinates for LLMs."""
        indent = "  " * depth
        try:
            x = int(self.bounds.get("x", 0) or 0)
            y = int(self.bounds.get("y", 0) or 0)
            w = int(self.bounds.get("width", 0) or 0)
            h = int(self.bounds.get("height", 0) or 0)
            cx, cy = x + w // 2, y + h // 2
            bounds_str = f"[{x},{y},{w}x{h}] center=({cx},{cy})"
        except Exception:
            bounds_str = "[0,0,0x0]"

        clean_name = self.name.replace("\n", " ").strip()
        name_str = f' "{clean_name}"' if clean_name else ""
        states_list = [
            str(s)
            for s in self.states
            if s is not None and s in ("focused", "editable", "checked", "active")
        ]
        state_str = f" ({','.join(states_list)})" if states_list else ""

        res = f"{indent}- [{self.node_id}] <{self.role}>{name_str} {bounds_str}{state_str}\n"
        for child in self.children:
            res += child.to_compact_str(depth + 1)
        return res


class AccessibilityTreeParser:
    """Extracts and parses accessibility hierarchy from AT-SPI2 or X11 fallback."""

    @classmethod
    def _prepare_env(cls, display: str = ":0") -> None:
        """Ensure DISPLAY and AT_SPI_BUS_ADDRESS are set."""
        if "DISPLAY" not in os.environ:
            os.environ["DISPLAY"] = display

        if "AT_SPI_BUS_ADDRESS" not in os.environ:
            # Auto-discover at-spi bus file
            cache_files = sorted(
                glob.glob(os.path.expanduser("~/.cache/at-spi/bus_*")),
                key=os.path.getmtime,
                reverse=True,
            )
            if cache_files:
                os.environ["AT_SPI_BUS_ADDRESS"] = f"unix:path={cache_files[0]}"

    @classmethod
    def get_tree(cls, display: str = ":0") -> AccessibilityNode:
        """Fetch the current accessibility tree."""
        cls._prepare_env(display)

        # 1. Try native pyatspi first
        try:
            tree = cls._get_tree_from_pyatspi()
            if tree and len(tree.children) > 0:
                return tree
        except Exception:
            pass

        # 2. Fallback to X11 window hierarchy
        return cls._get_tree_from_x11(display)

    @classmethod
    def _get_tree_from_pyatspi(cls) -> AccessibilityNode:
        """Traverse AT-SPI2 bus using pyatspi."""
        import pyatspi

        reg = pyatspi.Registry
        desktop = reg.getDesktop(0)

        counter = 0

        def parse_accessible(acc: Any, depth: int = 0) -> Optional[AccessibilityNode]:
            nonlocal counter
            if acc is None or depth > 8:
                return None

            try:
                name = str(acc.name or "").strip()
                role_name = str(acc.getRoleName() or "unknown").strip()

                states: List[str] = []
                try:
                    state_set = acc.getState()
                    for s in state_set.getStates():
                        if hasattr(s, "name") and s.name:
                            states.append(str(s.name).replace("STATE_", "").lower())
                        elif s is not None:
                            states.append(str(s).lower())
                except Exception:
                    pass

                # Bounding box
                bbox = {"x": 0, "y": 0, "width": 0, "height": 0}
                try:
                    component = acc.queryComponent()
                    rect = component.getExtents(pyatspi.DESKTOP_COORDS)
                    bbox = {
                        "x": int(rect.x),
                        "y": int(rect.y),
                        "width": int(rect.width),
                        "height": int(rect.height),
                    }
                except Exception:
                    pass

                # Filter out off-screen widgets with negative coordinates
                if (
                    bbox["x"] < -100
                    or bbox["y"] < -100
                    or bbox["width"] <= 0
                    or bbox["height"] <= 0
                ):
                    # Check if it has on-screen children
                    children: List[AccessibilityNode] = []
                    for i in range(acc.childCount):
                        child_node = parse_accessible(acc.getChildAtIndex(i), depth + 1)
                        if child_node:
                            children.append(child_node)
                    if not children:
                        return None
                    bbox = {"x": 0, "y": 0, "width": 0, "height": 0}
                else:
                    children: List[AccessibilityNode] = []
                    for i in range(acc.childCount):
                        child_node = parse_accessible(acc.getChildAtIndex(i), depth + 1)
                        if child_node:
                            children.append(child_node)

                val = ""
                try:
                    text_comp = acc.queryText()
                    val = str(text_comp.getText(0, text_comp.characterCount))
                except Exception:
                    pass

                # Prune empty non-informative nodes
                if (
                    not name
                    and not val
                    and not children
                    and bbox["width"] <= 2
                    and bbox["height"] <= 2
                ):
                    return None

                node_id = f"node_{counter}"
                counter += 1

                return AccessibilityNode(
                    node_id=node_id,
                    name=name,
                    role=role_name,
                    states=states,
                    bounds=bbox,
                    description=str(acc.description or ""),
                    value=val,
                    children=children,
                )
            except Exception:
                return None

        root_children: List[AccessibilityNode] = []
        for i in range(desktop.childCount):
            app_node = parse_accessible(desktop.getChildAtIndex(i), 1)
            if app_node:
                root_children.append(app_node)

        return AccessibilityNode(
            node_id="root",
            name="Desktop",
            role="desktop",
            bounds={"x": 0, "y": 0, "width": 1280, "height": 800},
            children=root_children,
        )

    @classmethod
    def _get_tree_from_x11(cls, display: str = ":0") -> AccessibilityNode:
        """Extract X11 window tree using xwininfo / wmctrl / xdotool as fallback."""
        env = os.environ.copy()
        env["DISPLAY"] = display

        root_node = AccessibilityNode(
            node_id="root",
            name="Desktop",
            role="desktop",
            bounds={"x": 0, "y": 0, "width": 1280, "height": 800},
        )

        counter = 0

        # Try wmctrl first
        if shutil.which("wmctrl"):
            try:
                res = subprocess.run(
                    ["wmctrl", "-l", "-G"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    for line in res.stdout.strip().splitlines():
                        parts = line.split(None, 7)
                        if len(parts) >= 8:
                            win_id, desk, x, y, w, h, host, title = parts
                            ix, iy, iw, ih = int(x), int(y), int(w), int(h)
                            if ix >= 0 and iy >= 0 and iw > 10 and ih > 10:
                                node = AccessibilityNode(
                                    node_id=f"win_{counter}",
                                    name=title,
                                    role="window",
                                    states=["visible"],
                                    bounds={
                                        "x": ix,
                                        "y": iy,
                                        "width": iw,
                                        "height": ih,
                                    },
                                )
                                counter += 1
                                root_node.children.append(node)
                    if root_node.children:
                        return root_node
            except Exception:
                pass

        return root_node
