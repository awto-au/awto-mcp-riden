"""
awto-riden RidenWorker — thread-safe wrapper for Riden RD60xx PSU control.

Used by both the CLI (ttu_cli.py) and MCP server (mcp_server.py).
Each caller opens the serial port independently; Modbus serializes at protocol level.

Transport: USB serial (/dev/ttyUSB0), Bluetooth serial (/dev/rfcomm0), or native BLE.
Driver: ShayBox/Riden library (Modbus RTU via pymodbus).
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import threading
import time
from typing import Any

import colorlog
import psutil
from riden import Riden

from protocol import DEFAULT_ADDRESS, DEFAULT_BAUD, DEFAULT_PORT

log = logging.getLogger("riden.daemon")

_start_time   = time.monotonic()
_FREE_THREADED = sys.version_info >= (3, 13) and not sys._is_gil_enabled()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    root  = logging.getLogger()
    root.setLevel(level)

    # syslog — plain text, no ANSI (journald / /var/log/syslog)
    try:
        syslog = logging.handlers.SysLogHandler(
            address="/dev/log",
            facility=logging.handlers.SysLogHandler.LOG_DAEMON,
        )
        syslog.ident = "awto-riden-daemon: "
        syslog.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(syslog)
    except OSError:
        pass  # /dev/log absent (container, minimal install) — stderr only

    # stderr — colored, Go-style ISO timestamp
    _LOG_COLORS = {
        "DEBUG":    "cyan",
        "INFO":     "green",
        "WARNING":  "yellow",
        "ERROR":    "red",
        "CRITICAL": "bold_red",
    }
    handler = colorlog.StreamHandler(sys.stderr)
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s %(levelname)-8s%(reset)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        log_colors=_LOG_COLORS,
    ))
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# RidenWorker — thread-safe PSU wrapper
# ---------------------------------------------------------------------------

class RidenWorker:
    """Thread-safe wrapper around the ShayBox/Riden driver.

    All Modbus I/O is serialised through _lock. The log loop runs in a
    daemon thread and also acquires _lock for each poll.
    """

    def __init__(self, port: str, baud: int, address: int) -> None:
        self._port    = port
        self._baud    = baud
        self._address = address
        self._psu: Riden | None = None
        self._lock    = threading.Lock()

        self._log_path:   str | None         = None
        self._log_file                       = None
        self._log_lock    = threading.Lock()
        self._log_thread: threading.Thread | None = None
        self._log_stop    = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        with self._lock:
            self._psu = Riden(
                port=self._port,
                baudrate=self._baud,
                address=self._address,
            )
            # Try to read PSU state with a timeout to avoid hanging
            try:
                # Set serial timeout for reads
                if hasattr(self._psu, 'serial') and self._psu.serial:
                    self._psu.serial.timeout = 2.0
                self._psu.update()
                log.info(
                    "connected to PSU on %s (baud=%d addr=%d) id=%s",
                    self._port, self._baud, self._address,
                    getattr(self._psu, "id", "?"),
                )
            except Exception as e:
                log.warning(
                    "PSU not responding yet (%s); will retry on first command",
                    e,
                )
                # State will be read lazily on first query

    def close(self) -> None:
        self._stop_log()
        with self._lock:
            if self._psu is not None:
                # pymodbus client lives at _psu._client
                try:
                    client = getattr(self._psu, "_client", None)
                    if client is not None:
                        client.close()
                except Exception:
                    pass
                self._psu = None
        log.info("PSU disconnected")

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _assert_connected(self) -> Riden:
        if self._psu is None:
            raise IOError("PSU not connected")
        return self._psu

    @staticmethod
    def _protection_str(psu: Riden) -> str:
        # Register 16: 0=none, 1=OVP, 2=OCP
        val = getattr(psu, "protect", 0) or 0
        return {1: "OVP", 2: "OCP"}.get(int(val), "none")

    def _read_status(self, psu: Riden) -> dict[str, Any]:
        psu.update()
        return {
            "v_set":   round(float(psu.v_set),  3),
            "i_set":   round(float(psu.i_set),  4),
            "v_out":   round(float(psu.v_out),  3),
            "i_out":   round(float(psu.i_out),  4),
            "p_out":   round(float(psu.p_out),  3),
            "v_in":    round(float(psu.v_in),   2),
            "output":  bool(psu.enable),
            "cv_cc":   "CC" if getattr(psu, "cv_cc", 0) else "CV",
            "protect": self._protection_str(psu),
            "temp_c":  getattr(psu, "int_c", None),
        }

    # ------------------------------------------------------------------
    # Commands — all acquire _lock
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._read_status(self._assert_connected())

    def set_voltage(self, volts: float) -> dict[str, Any]:
        with self._lock:
            psu = self._assert_connected()
            psu.set_v_set(volts)
            return self._read_status(psu)

    def set_current(self, amps: float) -> dict[str, Any]:
        with self._lock:
            psu = self._assert_connected()
            psu.set_i_set(amps)
            return self._read_status(psu)

    def set_output(self, on: bool) -> dict[str, Any]:
        with self._lock:
            psu = self._assert_connected()
            psu.enable = on
            return self._read_status(psu)

    def set_ovp(self, volts: float) -> dict[str, Any]:
        """Set over-voltage protection via M0 OVP register (register 82)."""
        with self._lock:
            psu = self._assert_connected()
            if hasattr(psu, "set_ovp"):
                psu.set_ovp(volts)
            else:
                # Direct Modbus write — scale matches v_set (×100 for RD60xx)
                scale = _infer_v_scale(psu)
                psu._client.write_register(82, int(volts * scale), unit=self._address)
            return self._read_status(psu)

    def set_ocp(self, amps: float) -> dict[str, Any]:
        """Set over-current protection via M0 OCP register (register 83)."""
        with self._lock:
            psu = self._assert_connected()
            if hasattr(psu, "set_ocp"):
                psu.set_ocp(amps)
            else:
                # Direct Modbus write — scale matches i_set (×1000 for RD60xx)
                scale = _infer_i_scale(psu)
                psu._client.write_register(83, int(amps * scale), unit=self._address)
            return self._read_status(psu)

    def power_cycle(self, seconds: float) -> dict[str, Any]:
        with self._lock:
            psu = self._assert_connected()
            psu.enable = False
        time.sleep(max(0.1, seconds))
        with self._lock:
            psu = self._assert_connected()
            psu.enable = True
            return self._read_status(psu)

    # ------------------------------------------------------------------
    # Status logging
    # ------------------------------------------------------------------

    def log_start(self, path: str, interval_ms: int) -> None:
        self._stop_log()
        self._log_stop.clear()
        self._log_path = path
        with self._log_lock:
            self._log_file = open(path, "a")
        self._log_thread = threading.Thread(
            target=self._log_loop,
            args=(interval_ms,),
            daemon=True,
            name="riden-log",
        )
        self._log_thread.start()
        log.info("logging started → %s every %d ms", path, interval_ms)

    def _log_loop(self, interval_ms: int) -> None:
        while not self._log_stop.wait(interval_ms / 1000.0):
            try:
                st = self.status()
                line = json.dumps({"ts": time.time(), **st}) + "\n"
                with self._log_lock:
                    if self._log_file:
                        self._log_file.write(line)
                        self._log_file.flush()
            except Exception as exc:
                log.warning("log loop error: %s", exc)

    def log_stop(self) -> None:
        self._stop_log()
        log.info("logging stopped")

    def _stop_log(self) -> None:
        self._log_stop.set()
        if self._log_thread and self._log_thread.is_alive():
            self._log_thread.join(timeout=3.0)
        with self._log_lock:
            if self._log_file:
                try:
                    self._log_file.close()
                except Exception:
                    pass
                self._log_file = None
        self._log_path = None

    # ------------------------------------------------------------------
    # Process health
    # ------------------------------------------------------------------

    def info(self) -> dict[str, Any]:
        proc = psutil.Process()
        with proc.oneshot():
            return {
                "pid":          proc.pid,
                "rss_mb":       round(proc.memory_info().rss / 1024 / 1024, 1),
                "cpu_pct":      proc.cpu_percent(interval=None),
                "threads":      proc.num_threads(),
                "open_fds":     proc.num_fds(),
                "uptime_s":     round(time.monotonic() - _start_time, 1),
                "port":         self._port,
                "baud":         self._baud,
                "address":      self._address,
                "connected":    self._psu is not None,
                "logging":      self._log_path,
                "free_threaded": _FREE_THREADED,
                "python":       sys.version.split()[0],
            }

