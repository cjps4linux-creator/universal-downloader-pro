"""Universal Downloader Pro  -  Windows Firewall egress lockdown."""

from __future__ import annotations

import subprocess


def allow_loopback() -> None:
    _run_netsh(["advfirewall", "firewall", "add", "rule", "name=UDP-Loopback", "dir=out", "action=allow", "protocol=any", "localip=127.0.0.1", "profile=private"])


def block_egress_except_tunnel(tunnel_port: int) -> None:
    _run_netsh(["advfirewall", "firewall", "add", "rule", "name=UDP-Block-Egress", "dir=out", "action=block", "remoteip=any", "localip!=127.0.0.1", "profile=private"])
    _run_netsh(["advfirewall", "firewall", "add", "rule", "name=UDP-Allow-Tunnel", "dir=out", "action=allow", "protocol=TCP,UDP", "localport=any", "remoteport=" + str(tunnel_port), "profile=private"])


def _run_netsh(args: list[str]) -> None:
    try:
        subprocess.run(["netsh"] + args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"netsh failed: {exc.stderr}") from exc
