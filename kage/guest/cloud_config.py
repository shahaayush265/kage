"""Cloud-init user-data and bootstrap templates for zero-touch VM provisioning."""

from __future__ import annotations

import base64
from pathlib import Path

from kage.core.config import get_or_create_ssh_key
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
        # Get or create dedicated host SSH key
        _, pub_key_str = get_or_create_ssh_key()
        ssh_keys_yaml = f"      - {pub_key_str}" if pub_key_str else ""

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

bootcmd:
  - systemctl mask systemd-networkd-wait-online.service systemd-networkd.service || true
  - systemctl stop systemd-networkd-wait-online.service || true

users:
  - name: kage
    gecos: Kage Agent User
    primary_group: kage
    groups: [sudo, adm, kvm]
    shell: /bin/bash
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    lock_passwd: false
    ssh_authorized_keys:
{ssh_keys_yaml}
  - name: root
    ssh_authorized_keys:
{ssh_keys_yaml}

ssh_pwauth: true
chpasswd:
  list: |
    kage:kage
    root:kage
  expire: false

write_files:
  - path: /etc/ssh/sshd_config.d/99-kage.conf
    permissions: '0644'
    content: |
      PasswordAuthentication yes
      PermitRootLogin yes
      UseDNS no
      GSSAPIAuthentication no

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
      After=network.target

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

runcmd:
  - mkdir -p /workspace /home/kage/workspace /home/kage/.ssh
  - chown -R kage:kage /home/kage /opt/kage-guest /workspace
  - chmod 700 /home/kage/.ssh
  - |
    # Mount virtio 9p workspace if available
    if ! grep -q "workspace /workspace" /etc/fstab; then
      echo "workspace /workspace 9p trans=virtio,version=9p2000.L,_netdev,rw,nofail 0 0" >> /etc/fstab
    fi
  - mount -a || true
  - systemctl daemon-reload
  - systemctl restart ssh || systemctl restart sshd || true
  - systemctl enable --now kage-guest-agent.service || true
"""
