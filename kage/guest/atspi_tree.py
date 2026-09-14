"""AT-SPI2 accessibility tree extractor, parser, and serializer for GUI automation."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
        return {
            "x": self.bounds["x"] + self.bounds["width"] // 2,
            "y": self.bounds["y"] + self.bounds["height"] // 2,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "role": self.role,
            "states": self.states,
            "bounds": self.bounds,
            "center": self.center,
            "description": self.description,
            "value": self.value,
            "children": [c.to_dict() for c in self.children],
        }

    def to_compact_str(self, depth: int = 0) -> str:
        """Format as a compact indentation-based string for LLM context."""
        indent = "  " * depth
        b = self.bounds
        bounds_str = f"[{b['x']},{b['y']},{b['width']}x{b['height']}]"
        name_str = f' "{self.name}"' if self.name else ""
        state_str = f" ({','.join(self.states)})" if self.states else ""
        res = f"{indent}- [{self.node_id}] <{self.role}>{name_str} {bounds_str}{state_str}\n"
        for child in self.children:
            res += child.to_compact_str(depth + 1)
        return res


class AccessibilityTreeParser:
    """Extracts and parses accessibility hierarchy from AT-SPI2 or X11 fallback."""

    @classmethod
    def get_tree(cls, display: str = ":0") -> AccessibilityNode:
        """Fetch the current accessibility tree."""
        # Try native pyatspi if installed
        try:
            return cls._get_tree_from_pyatspi()
        except Exception:
            pass

        # Fallback to X11 window hierarchy via xdotool/xwininfo
        return cls._get_tree_from_x11(display)

    @classmethod
    def _get_tree_from_pyatspi(cls) -> AccessibilityNode:
        """Traverse AT-SPI2 bus using pyatspi."""
        import pyatspi

        reg = pyatspi.Registry
        desktop = reg.getDesktop(0)

        counter = 0

        def parse_accessible(acc: Any) -> Optional[AccessibilityNode]:
            nonlocal counter
            if acc is None:
                return None

            try:
                name = acc.name or ""
                role_name = acc.getRoleName() or "unknown"
                state_set = acc.getState()
                states = [
                    s.name.replace("STATE_", "").lower() for s in state_set.getStates() if s.name
                ]

                # Bounding box
                bbox = {"x": 0, "y": 0, "width": 0, "height": 0}
                try:
                    component = acc.queryComponent()
                    rect = component.getExtents(pyatspi.DESKTOP_COORDS)
                    bbox = {
                        "x": rect.x,
                        "y": rect.y,
                        "width": rect.width,
                        "height": rect.height,
                    }
                except Exception:
                    pass

                # Value
                val = ""
                try:
                    text_comp = acc.queryText()
                    val = text_comp.getText(0, text_comp.characterCount)
                except Exception:
                    pass

                node_id = f"node_{counter}"
                counter += 1

                children: List[AccessibilityNode] = []
                for i in range(acc.childCount):
                    child_node = parse_accessible(acc.getChildAtIndex(i))
                    if child_node:
                        children.append(child_node)

                return AccessibilityNode(
                    node_id=node_id,
                    name=name,
                    role=role_name,
                    states=states,
                    bounds=bbox,
                    description=acc.description or "",
                    value=val,
                    children=children,
                )
            except Exception:
                return None

        root = parse_accessible(desktop)
        if root:
            return root
        return AccessibilityNode(node_id="root", name="Desktop", role="desktop")

    @classmethod
    def _get_tree_from_x11(cls, display: str = ":0") -> AccessibilityNode:
        """Extract X11 window tree using xwininfo / xdotool as fallback."""
        env = os.environ.copy()
        env["DISPLAY"] = display

        root_node = AccessibilityNode(
            node_id="root",
            name="Desktop",
            role="desktop",
            bounds={"x": 0, "y": 0, "width": 1920, "height": 1080},
        )

        if not shutil.which("xdotool") and not shutil.which("wmctrl"):
            return root_node

        try:
            # Use wmctrl -l -G to list windows with geometry
            if shutil.which("wmctrl"):
                res = subprocess.run(
                    ["wmctrl", "-l", "-G"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    for idx, line in enumerate(res.stdout.strip().splitlines()):
                        parts = line.split(None, 7)
                        if len(parts) >= 8:
                            win_id, desk, x, y, w, h, host, title = parts
                            node = AccessibilityNode(
                                node_id=f"win_{idx}",
                                name=title,
                                role="window",
                                states=["visible"],
                                bounds={
                                    "x": int(x),
                                    "y": int(y),
                                    "width": int(w),
                                    "height": int(h),
                                },
                            )
                            root_node.children.append(node)
        except Exception:
            pass

        return root_node
