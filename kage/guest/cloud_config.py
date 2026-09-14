"""Cloud-init user-data and bootstrap templates for zero-touch VM provisioning."""

from __future__ import annotations

import base64
from pathlib import Path

from kage.core.instance import InstanceConfig


class CloudConfigGenerator:
    """Generates user-data and meta-data for cloud-init NoCloud."""

    @classmethod
    def generate_meta_data(cls, instance_name: str) -> str:
        return f"""instance-id: kage-{instance_name}
local-hostname: {instance_name}
"""

    @classmethod
    def generate_user_data(cls, instance: InstanceConfig) -> str:
        # Read the guest agent python scripts to embed into the VM
        guest_dir = Path(__file__).parent
        atspi_py = (guest_dir / "atspi_tree.py").read_text(encoding="utf-8")
        input_py = (guest_dir / "input_synth.py").read_text(encoding="utf-8")
        screen_py = (guest_dir / "screen.py").read_text(encoding="utf-8")
        shell_py = (guest_dir / "shell_exec.py").read_text(encoding="utf-8")
        service_py = (guest_dir / "agent_service.py").read_text(encoding="utf-8")

        atspi_b64 = base64.b64encode(atspi_py.encode("utf-8")).decode("ascii")
        input_b64 = base64.b64encode(input_py.encode("utf-8")).decode("ascii")
        screen_b64 = base64.b64encode(screen_py.encode("utf-8")).decode("ascii")
        shell_b64 = base64.b64encode(shell_py.encode("utf-8")).decode("ascii")
        service_b64 = base64.b64encode(service_py.encode("utf-8")).decode("ascii")

        return f"""#cloud-config
hostname: {instance.name}
manage_etc_hosts: true

users:
  - name: kage
    gecos: Kage Agent User
    primary_group: kage
    groups: [sudo, adm, kvm]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: false
    passwd: "$6$rounds=4096$kagesalt$50w7hJ2uCvhjP0tWc0VqLzLp7Q1c1u9c.3c6eL9sC1jO6c0.mO3O7r5jA7oA8m4m2O.kagehashdummy"

ssh_pwauth: true
chpasswd:
  list: |
    kage:kage
    root:kage
  expire: false

write_files:
  - path: /opt/kage-guest/kage/__init__.py
    permissions: '0644'
    content: |
      __version__ = "0.1.0"

  - path: /opt/kage-guest/kage/guest/__init__.py
    permissions: '0644'
    content: |
      pass

  - path: /opt/kage-guest/kage/guest/atspi_tree.py
    encoding: b64
    permissions: '0644'
    content: {atspi_b64}

  - path: /opt/kage-guest/kage/guest/input_synth.py
    encoding: b64
    permissions: '0644'
    content: {input_b64}

  - path: /opt/kage-guest/kage/guest/screen.py
    encoding: b64
    permissions: '0644'
    content: {screen_b64}

  - path: /opt/kage-guest/kage/guest/shell_exec.py
    encoding: b64
    permissions: '0644'
    content: {shell_b64}

  - path: /opt/kage-guest/kage/guest/agent_service.py
    encoding: b64
    permissions: '0755'
    content: {service_b64}

  - path: /etc/systemd/system/kage-guest-agent.service
    permissions: '0644'
    content: |
      [Unit]
      Description=Kage In-Guest Agent Bridge Service
      After=network.target display-manager.service

      [Service]
      Type=simple
      User=kage
      Environment=DISPLAY=:0
      Environment=PYTHONPATH=/opt/kage-guest
      WorkingDirectory=/home/kage
      ExecStart=/usr/bin/python3 /opt/kage-guest/kage/guest/agent_service.py
      Restart=always
      RestartSec=2

      [Install]
      WantedBy=multi-user.target

  - path: /etc/systemd/system/x11vnc.service
    permissions: '0644'
    content: |
      [Unit]
      Description=x11vnc VNC Server for Display :0
      After=display-manager.service

      [Service]
      Type=simple
      User=kage
      Environment=DISPLAY=:0
      ExecStart=/usr/bin/x11vnc -display :0 -forever -shared -nopw -rfbport 5900
      Restart=always
      RestartSec=2

      [Install]
      WantedBy=multi-user.target

runcmd:
  - mkdir -p /workspace /home/kage/workspace
  - chown -R kage:kage /home/kage /opt/kage-guest /workspace
  - |
    # Mount virtio 9p workspace if available
    if ! grep -q "workspace /workspace" /etc/fstab; then
      echo "workspace /workspace 9p trans=virtio,version=9p2000.L,_netdev,rw,nofail 0 0" >> /etc/fstab
    fi
  - mount -a || true
  - systemctl daemon-reload
  - systemctl enable --now kage-guest-agent.service || true
  - systemctl enable --now x11vnc.service || true
"""
