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
  - systemctl mask systemd-networkd-wait-online.service || true
  - systemctl stop systemd-networkd-wait-online.service || true
  - mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix || true

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

  - path: /etc/systemd/system/getty@tty1.service.d/override.conf
    permissions: '0644'
    content: |
      [Service]
      ExecStart=
      ExecStart=-/sbin/agetty --autologin kage --noclear %I $TERM
      Type=idle

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

  - path: /usr/local/bin/kage-desktop-launcher
    permissions: '0755'
    content: |
      #!/bin/bash
      export DISPLAY=:0
      export HOME=/home/kage
      export USER=kage
      export XDG_CURRENT_DESKTOP=XFCE
      export XDG_SESSION_TYPE=x11

      rm -f /tmp/.X0-lock /tmp/.X11-unix/X0 2>/dev/null || true
      mkdir -p /tmp/.X11-unix 2>/dev/null || true

      Xvfb :0 -screen 0 1280x800x24 -ac +extension GLX +render -noreset &
      sleep 1

      dbus-launch --exit-with-session startxfce4 &
      sleep 2

      exec x11vnc -display :0 -forever -shared -nopw -rfbport 5900 -wait 5 -defer 2

  - path: /etc/systemd/system/kage-desktop.service
    permissions: '0644'
    content: |
      [Unit]
      Description=Kage XFCE GUI Desktop & x11vnc Bridge
      After=network.target
      Wants=network.target

      [Service]
      Type=simple
      User=kage
      Group=kage
      WorkingDirectory=/home/kage
      ExecStart=/usr/local/bin/kage-desktop-launcher
      Restart=always
      RestartSec=2

      [Install]
      WantedBy=multi-user.target

  - path: /etc/systemd/system/kage-guest-agent.service
    permissions: '0644'
    content: |
      [Unit]
      Description=Kage In-Guest Agent Bridge Service
      After=kage-desktop.service

      [Service]
      Type=simple
      User=kage
      Environment=DISPLAY=:0
      Environment=HOME=/home/kage
      Environment=PYTHONPATH=/opt/kage-guest
      WorkingDirectory=/home/kage
      ExecStart=/usr/bin/python3 /opt/kage-guest/kage/guest/agent_service.py
      Restart=always
      RestartSec=2

      [Install]
      WantedBy=multi-user.target

runcmd:
  - mkdir -p /workspace /home/kage/workspace /home/kage/.ssh /tmp/.X11-unix
  - chown -R kage:kage /home/kage /opt/kage-guest /workspace
  - chmod 700 /home/kage/.ssh
  - chmod 1777 /tmp/.X11-unix
  - chmod 755 /usr/local/bin/kage-desktop-launcher
  - |
    # Mount virtio 9p workspace if available
    if ! grep -q "workspace /workspace" /etc/fstab; then
      echo "workspace /workspace 9p trans=virtio,version=9p2000.L,_netdev,rw,nofail 0 0" >> /etc/fstab
    fi
  - mount -a || true
  - systemctl daemon-reload
  - systemctl restart ssh || systemctl restart sshd || true
  - systemctl enable --now kage-desktop.service || true
  - systemctl enable --now kage-guest-agent.service || true
"""
