"""Dynamic, conflict-free port allocator for VM instances."""

from __future__ import annotations

import socket
from typing import Optional, Set

from kage.core.instance import InstanceConfig, InstancePorts


class PortAllocator:
    """Manages dynamic port allocation ensuring no OS or instance collisions."""

    DEFAULT_RANGES = {
        "ssh": (2222, 2999),
        "vnc": (5900, 5999),
        "novnc": (6080, 6199),
        "api": (8000, 8199),
        "guest_agent": (9000, 9199),
        "qmp": (4444, 4599),
    }

    @staticmethod
    def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
        """Check if a TCP port is currently available for binding on host."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return True
            except (OSError, socket.error):
                return False

    @classmethod
    def get_used_ports_by_instances(cls, exclude_instance: Optional[str] = None) -> Set[int]:
        """Collect all ports currently allocated to registered instances."""
        used: Set[int] = set()
        instances = InstanceConfig.list_all()
        for inst in instances:
            if exclude_instance and inst.name == exclude_instance:
                continue
            if inst.ports:
                used.add(inst.ports.ssh)
                used.add(inst.ports.vnc)
                used.add(inst.ports.novnc)
                used.add(inst.ports.api)
                used.add(inst.ports.guest_agent)
                used.add(inst.ports.qmp)
        return used

    @classmethod
    def find_free_port(
        cls,
        start_port: int,
        end_port: int,
        used_ports: Set[int],
        host: str = "127.0.0.1",
    ) -> int:
        """Find the first free port in range that is neither used by instances nor bound by OS."""
        for port in range(start_port, end_port + 1):
            if port in used_ports:
                continue
            if cls.is_port_available(port, host):
                used_ports.add(port)
                return port
        raise RuntimeError(f"No free ports available in range {start_port}-{end_port}")

    @classmethod
    def allocate(
        cls,
        instance_name: str,
        host: str = "127.0.0.1",
        preferred_ports: Optional[InstancePorts] = None,
    ) -> InstancePorts:
        """Allocate a complete set of conflict-free ports for an instance."""
        used = cls.get_used_ports_by_instances(exclude_instance=instance_name)

        if preferred_ports:
            # Verify if preferred ports are available
            p = preferred_ports
            if (
                cls.is_port_available(p.ssh, host)
                and cls.is_port_available(p.vnc, host)
                and cls.is_port_available(p.novnc, host)
                and cls.is_port_available(p.api, host)
                and cls.is_port_available(p.guest_agent, host)
                and cls.is_port_available(p.qmp, host)
            ):
                return preferred_ports

        ssh_port = cls.find_free_port(
            cls.DEFAULT_RANGES["ssh"][0], cls.DEFAULT_RANGES["ssh"][1], used, host
        )
        vnc_port = cls.find_free_port(
            cls.DEFAULT_RANGES["vnc"][0], cls.DEFAULT_RANGES["vnc"][1], used, host
        )
        novnc_port = cls.find_free_port(
            cls.DEFAULT_RANGES["novnc"][0], cls.DEFAULT_RANGES["novnc"][1], used, host
        )
        api_port = cls.find_free_port(
            cls.DEFAULT_RANGES["api"][0], cls.DEFAULT_RANGES["api"][1], used, host
        )
        guest_agent_port = cls.find_free_port(
            cls.DEFAULT_RANGES["guest_agent"][0],
            cls.DEFAULT_RANGES["guest_agent"][1],
            used,
            host,
        )
        qmp_port = cls.find_free_port(
            cls.DEFAULT_RANGES["qmp"][0], cls.DEFAULT_RANGES["qmp"][1], used, host
        )

        return InstancePorts(
            ssh=ssh_port,
            vnc=vnc_port,
            novnc=novnc_port,
            api=api_port,
            guest_agent=guest_agent_port,
            qmp=qmp_port,
        )
