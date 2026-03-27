import fnmatch
import logging
import os
import platform
import re
import socket
import subprocess
import time
from datetime import datetime

import psutil

from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class SystemStatus(BasePlugin):
    # Friendly names for non-Waveshare display drivers.
    # Waveshare EPD codes are parsed dynamically from the epd*in* pattern
    # (same rule used by display_manager.py) so no hardcoded list is needed.
    DISPLAY_NAME_MAP = {
        "inky": "Inky e-Paper",
        "mock": "Mock Display",
    }

    # Regex to extract size and variant from Waveshare EPD codes.
    # e.g. "epd7in3e" ? groups ("7", "3", "e"), "epd13in3k" ? ("13", "3", "k")
    _EPD_PATTERN = re.compile(
        r"^epd(\d+)in(\d+)([a-z]*)(?:_(v\d+|hd))?(?:([a-z]*)(?:_(v\d+|hd))?)?$",
        re.IGNORECASE,
    )

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
        show_disk = settings.get("showDisk", "true") == "true"
        show_disk_used_total = settings.get("showDiskUsedTotal", "false") == "true"
        show_ram_used_total = settings.get("showRamUsedTotal", "false") == "true"
        show_last_boot = settings.get("showLastBoot", "true") == "true"
        show_model = settings.get("showModel", "true") == "true"
        show_os = settings.get("showOS", "true") == "true"
        show_display = settings.get("showDisplay", "true") == "true"
        metrics = []

        if show_cpu:
            cpu_metric = {"label": "CPU", "value": self._get_cpu_usage(), "type": "progress"}
            cpu_freq = self._get_cpu_freq()
            if cpu_freq:
                cpu_metric["secondary_text"] = cpu_freq
            metrics.append(cpu_metric)

        if show_ram:
            vm = psutil.virtual_memory()
            ram_percent = vm.percent
            ram_metric = {"label": "RAM", "value": ram_percent, "type": "progress"}
            if show_ram_used_total:
                used = vm.used
                total = vm.total
                ram_metric["secondary_text"] = self._format_bytes(used) + " / " + self._format_bytes(total)
            metrics.append(ram_metric)

        if show_disk:
            try:
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                metric = {"label": "Disk", "value": disk_percent, "type": "progress"}
                if show_disk_used_total:
                    used = disk.used
                    total = disk.total
                    metric["secondary_text"] = self._format_bytes(used) + " / " + self._format_bytes(total)
                metrics.append(metric)
            except Exception:
                logger.exception("SystemStatus: failed to get disk usage")

        if show_temp:
            temp = self._get_temperature()
            if temp is not None:
                metrics.append({"label": "TEMP", "value": temp, "suffix": "°C", "type": "progress"})
            else:
                # Ensure the Temperature row is always present when enabled.
                # Show 'N/A' if temperature cannot be retrieved to avoid
                # visual jumps in the layout.
                metrics.append({"label": "TEMP", "value_text": "N/A", "type": "text"})

        if show_uptime:
            uptime_str = self._get_uptime()
            metrics.append({"label": "UPTIME", "value_text": uptime_str, "type": "text"})

        if show_last_boot:
            try:
                boot_ts = psutil.boot_time()
                boot_dt = datetime.fromtimestamp(boot_ts)
                boot_str = boot_dt.strftime("%b %d %H:%M")
                metrics.append({"label": "LAST BOOT", "value_text": boot_str, "type": "text"})
            except Exception:
                logger.exception("SystemStatus: failed to get boot time")

        if show_ip:
            ip = self._get_local_ip()
            if ip:
                metrics.append({"label": "Local IP", "value_text": ip, "type": "text"})
            else:
                logger.debug("SystemStatus: no valid local IP found; hiding IP metric")

        if show_model:
            model = self._get_model()
            if model:
                metrics.append({"label": "DEVICE", "value_text": model, "type": "text"})
            else:
                # Ensure the Device row is always present when enabled.
                # Show 'N/A' if model information cannot be retrieved.
                metrics.append({"label": "DEVICE", "value_text": "N/A", "type": "text"})

        if show_os:
            os_version = self._get_os_version()
            if os_version:
                metrics.append({"label": "OS", "value_text": os_version, "type": "text"})

        if show_display:
            display_value = self._get_display_value(device_config) or "N/A"
            metrics.append({"label": "Display", "value_text": display_value, "type": "text"})

        device_name = self._get_device_name()

        template_params = {
            "metrics": metrics,
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

    def _get_cpu_freq(self):
        """Get current CPU frequency as a human-readable string."""
        try:
            freq = psutil.cpu_freq()
            if freq and freq.current:
                mhz = freq.current
                if mhz >= 1000:
                    return f"{mhz / 1000:.1f} GHz"
                return f"{mhz:.0f} MHz"
        except Exception:
            pass
        return None

    def _get_cpu_usage(self):
        """Get total system CPU usage percentage.

        On WSL, psutil measures the Linux guest CPU, not the Windows host CPU
        shown by Task Manager. In that case, try reading the host CPU usage via
        PowerShell so the plugin matches what the user sees on Windows.
        """
        if self._is_wsl():
            windows_cpu = self._get_windows_host_cpu_usage()
            if windows_cpu is not None:
                return windows_cpu

        try:
            cpu = psutil.cpu_percent(interval=0.2)
        except Exception:
            cpu = 0.0

        try:
            cpu = float(cpu)
        except Exception:
            cpu = 0.0

        return max(0.0, min(100.0, cpu))

    def _is_wsl(self):
        """Return True when running inside Windows Subsystem for Linux."""
        try:
            if os.environ.get("WSL_INTEROP"):
                return True
            return "microsoft" in platform.release().lower()
        except Exception:
            return False

    def _get_windows_host_cpu_usage(self):
        """Read Windows host CPU usage from WSL to match Task Manager.

        Returns None if PowerShell/counters are unavailable.
        """
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter \"Name='_Total'\" | Select-Object -ExpandProperty PercentProcessorTime)",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode != 0:
                return None

            value = result.stdout.strip().replace(",", ".")
            cpu = float(value)
            return max(0.0, min(100.0, cpu))
        except Exception:
            logger.debug("SystemStatus: failed to read Windows host CPU usage", exc_info=True)
            return None

    def _format_bytes(self, num_bytes):
        """Format bytes into human-friendly string (GB or MB)."""
        try:
            gb = float(num_bytes) / (1024 ** 3)
            if gb >= 1:
                return f"{gb:.0f}GB"
            mb = float(num_bytes) / (1024 ** 2)
            return f"{mb:.0f}MB"
        except Exception:
            return "0B"

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

        Primary: use a UDP socket connect to an external address (no traffic
        is sent) to determine the outbound interface IP.

        Fallback: collect all IPv4 addresses from interfaces via
        `psutil.net_if_addrs()`, filter out loopback and link-local, then
        prioritize candidates using the following order:
          1) 192.168.x.x
          2) 10.x.x.x
          3) 172.x.x.x
          4) any other remaining IPv4

        Returns the best candidate or None if no valid address is found.
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

        def _is_loopback(a):
            return a.startswith("127.") if a else False

        def _is_link_local(a):
            return a.startswith("169.254.") if a else False

        def _priority(a):
            # Lower number => higher priority
            if a.startswith("192.168."):
                return 0
            if a.startswith("10."):
                return 1
            if a.startswith("172."):
                # Only treat 172.16.0.0 - 172.31.255.255 as private
                try:
                    parts = a.split('.')
                    if len(parts) >= 2:
                        second = int(parts[1])
                        if 16 <= second <= 31:
                            return 2
                except Exception:
                    pass
            return 3

        def _valid_ipv4(a):
            if not a:
                return False
            if _is_loopback(a) or _is_link_local(a):
                return False
            return True

        if _valid_ipv4(ip):
            return ip

        # Fallback: collect all valid IPv4 addresses
        candidates = []
        try:
            addrs = psutil.net_if_addrs()
            for iface, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        candidate = addr.address
                        if _valid_ipv4(candidate):
                            candidates.append(candidate)
        except Exception:
            candidates = []

        if not candidates:
            return None

        # Sort candidates by priority and return the best one
        candidates.sort(key=lambda a: _priority(a))
        return candidates[0]

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

    def _get_model(self):
        """Get device model with proper fallbacks.
        
        On Raspberry Pi: read /proc/device-tree/model
        On Linux (non-RPi): read DMI identifiers (product_name, sys_vendor)
        On Windows: use platform.uname().machine
        Returns None if no valid model found (never falls back to hostname).
        """
        # 1. Try Raspberry Pi model first
        model_path = "/proc/device-tree/model"
        if os.path.isfile(model_path):
            try:
                with open(model_path) as f:
                    model = f.read().strip().rstrip("\x00")
                if model:
                    return model
            except OSError:
                pass
        
        # 2. Linux non-RPi: try DMI identifiers
        dmi_product_name = "/sys/devices/virtual/dmi/id/product_name"
        dmi_sys_vendor = "/sys/devices/virtual/dmi/id/sys_vendor"
        
        vendor = None
        product = None
        
        if os.path.isfile(dmi_sys_vendor):
            try:
                with open(dmi_sys_vendor) as f:
                    vendor = f.read().strip()
                if not vendor:
                    vendor = None
            except OSError:
                pass
        
        if os.path.isfile(dmi_product_name):
            try:
                with open(dmi_product_name) as f:
                    product = f.read().strip()
                if not product:
                    product = None
            except OSError:
                pass
        
        # Combine vendor and product, or return whichever is available
        if vendor and product:
            return f"{vendor} {product}"
        if vendor:
            return vendor
        if product:
            return product
        
        # 3. Windows: use machine info
        try:
            if platform.system() == "Windows":
                uname = platform.uname()
                if uname.machine:
                    return uname.machine
        except Exception:
            pass
        
        # 4. No valid model found
        return None

    def _get_display_value(self, device_config):
        """Return a human-readable display description derived from the configuration.

        Uses the same epd*in* pattern as display_manager.py to identify Waveshare
        displays.  The size is parsed dynamically from the EPD code so that any
        current or future Waveshare model is resolved without a hardcoded map.
        """

        display_type = device_config.get_config("display_type", default=None)
        if not display_type:
            return None

        display_type_value = str(display_type).strip()
        if not display_type_value:
            return None

        normalized_type = display_type_value.lower()

        # Known non-Waveshare driver (e.g. inky, mock).
        friendly_name = self.DISPLAY_NAME_MAP.get(normalized_type)
        if friendly_name:
            return friendly_name

        # Mirror the Waveshare detection rule used by display_manager.py.
        # Only label as Waveshare when the type matches the epd*in* pattern.
        if fnmatch.fnmatch(normalized_type, "epd*in*"):
            parsed = self._parse_epd_code(normalized_type)
            if parsed:
                return f"{parsed} ({display_type_value})"
            return f"Waveshare e-Paper ({display_type_value})"

        # Completely unknown ? return the raw configured value without guessing a brand.
        return display_type_value

    @classmethod
    def _parse_epd_code(cls, code):
        """Parse a Waveshare EPD code into a friendly name.

        Examples:
            epd7in3e  ? Waveshare 7.3inch e-Paper
            epd5in83_v2 ? Waveshare 5.83inch e-Paper V2
            epd7in5b_hd ? Waveshare 7.5inch e-Paper HD
            epd13in3k ? Waveshare 13.3inch e-Paper
        """
        m = cls._EPD_PATTERN.match(code)
        if not m:
            return None

        inches = m.group(1)
        decimal = m.group(2)
        size = f"{inches}.{decimal}"

        # Collect version / variant suffixes (e.g. _v2, _hd, b, bc)
        suffixes = []
        for g in (m.group(4), m.group(5), m.group(6)):
            if g:
                suffixes.append(g.upper())

        suffix_str = f" {' '.join(suffixes)}" if suffixes else ""
        return f"Waveshare {size}inch e-Paper{suffix_str}"

    def _get_os_version(self):
        """Get OS version string.
        
        On Linux: read /etc/os-release (prefer PRETTY_NAME)
        On Windows: use platform.system() + platform.release()
        Returns None if not available.
        """
        # Try /etc/os-release (Linux, RPi)
        os_release_path = "/etc/os-release"
        if os.path.isfile(os_release_path):
            try:
                with open(os_release_path) as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.startswith("PRETTY_NAME="):
                            # Extract value, remove quotes
                            value = line.split("=", 1)[1].strip()
                            value = value.strip('"\'')
                            if value:
                                return value
                        elif line.startswith("NAME="):
                            # Fallback to NAME if PRETTY_NAME not found
                            value = line.split("=", 1)[1].strip()
                            value = value.strip('"\'')
                            if value:
                                name = value
                    # If we found a NAME but no PRETTY_NAME, return it
                    try:
                        return name
                    except NameError:
                        pass
            except OSError:
                pass
        
        # Windows fallback: system + release (e.g., "Windows 11")
        try:
            system = platform.system()
            if system == "Windows":
                release = platform.release()
                if release:
                    return f"{system} {release}"
                return system
        except Exception:
            pass
        
        return None
