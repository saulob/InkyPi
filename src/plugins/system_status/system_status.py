import logging
import os
import platform
import socket
import subprocess
import time

import psutil

from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class SystemStatus(BasePlugin):

    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        show_cpu = settings.get("showCpu", "true") == "true"
        show_ram = settings.get("showRam", "true") == "true"
        show_temp = settings.get("showTemp", "true") == "true"
        show_uptime = settings.get("showUptime", "true") == "true"
        show_ip = settings.get("showIp", "false") == "true"
        style = settings.get("style", "dots")

        metrics = []

        if show_cpu:
            cpu = psutil.cpu_percent(interval=1)
            metrics.append({"label": "CPU", "value": cpu, "type": "progress"})

        if show_ram:
            ram = psutil.virtual_memory().percent
            metrics.append({"label": "RAM", "value": ram, "type": "progress"})

        if show_temp:
            temp = self._get_temperature()
            if temp is not None:
                metrics.append({"label": "TEMP", "value": temp, "suffix": "°C", "type": "progress"})

        if show_uptime:
            uptime_str = self._get_uptime()
            metrics.append({"label": "UPTIME", "value_text": uptime_str, "type": "text"})

        if show_ip:
            ip = self._get_local_ip()
            if ip:
                metrics.append({"label": "Local IP", "value_text": ip, "type": "text"})
            else:
                logger.debug("SystemStatus: no valid local IP found; hiding IP metric")

        device_name = self._get_device_name()

        template_params = {
            "metrics": metrics,
            "style": style,
            "device_name": device_name,
            "plugin_settings": settings,
        }

        return self.render_image(
            dimensions, "system_status.html", "system_status.css", template_params
        )

    def _get_temperature(self):
        """Get CPU temperature with multi-platform fallback."""
        # 1. Try psutil sensors
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name in ("cpu_thermal", "cpu-thermal", "coretemp", "k10temp", "acpitz"):
                    if name in temps and temps[name]:
                        return round(temps[name][0].current)
                # Fallback: use first available sensor
                first_key = next(iter(temps))
                if temps[first_key]:
                    return round(temps[first_key][0].current)
        except (AttributeError, OSError):
            pass

        # 2. Raspberry Pi: vcgencmd
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Output: temp=42.0'C
                temp_str = result.stdout.strip()
                temp_val = float(temp_str.split("=")[1].split("'")[0])
                return round(temp_val)
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass

        # 3. Linux thermal zone
        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.isfile(thermal_path):
            try:
                with open(thermal_path) as f:
                    raw = f.read().strip()
                return round(int(raw) / 1000)
            except (ValueError, OSError):
                pass

        return None

    def _get_uptime(self):
        """Get system uptime as readable text."""
        boot = psutil.boot_time()
        elapsed = time.time() - boot
        days = int(elapsed // 86400)
        hours = int((elapsed % 86400) // 3600)
        minutes = int((elapsed % 3600) // 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes or not parts:
            parts.append(f"{minutes}m")
        return " ".join(parts)

    def _get_local_ip(self):
        """Get the primary local IPv4 address for the device.

        Uses a UDP socket connect to a well-known external address to determine
        the outbound interface IP (no packets are sent). Falls back to
        inspecting network interfaces via psutil. Returns None when no valid
        non-loopback IPv4 address is available.
        """
        # Preferred method: UDP socket to external host (doesn't send traffic)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            finally:
                s.close()
        except OSError:
            ip = None

        def _valid_ipv4(a):
            if not a:
                return False
            if a.startswith("127."):
                return False
            if a.startswith("169.254."):
                return False
            return True

        if _valid_ipv4(ip):
            return ip

        # Fallback: inspect interfaces and pick the first valid IPv4 address
        try:
            addrs = psutil.net_if_addrs()
            for iface, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        candidate = addr.address
                        if _valid_ipv4(candidate):
                            return candidate
        except Exception:
            pass

        return None

    def _get_device_name(self):
        """Detect device model or fallback to hostname."""
        # Try Raspberry Pi model
        model_path = "/proc/device-tree/model"
        if os.path.isfile(model_path):
            try:
                with open(model_path) as f:
                    model = f.read().strip().rstrip("\x00")
                if model:
                    return model
            except OSError:
                pass

        return platform.node() or "System"
