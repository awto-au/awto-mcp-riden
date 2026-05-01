# riden_transport.py — transport abstraction for Riden RD60xx / RK60xx PSUs.
#
# Provides a hardware-independent Modbus RTU interface so riden_daemon.py
# does not depend on the ShayBox/Riden upstream library at runtime.
#
# Implemented:
#   SerialTransport  — USB serial / BT serial via modbus-tk + pyserial
#
# Stubs (not yet implemented):
#   TcpTransport     — Modbus TCP or pyserial socket:// URL (WiFi bridge)
#   BleTransport     — Bleak BLE (RK6006-BT native BLE)
#
# Register-level protocol derived from:
#   Baldanos/rd6006 (Apache-2.0)  https://github.com/Baldanos/rd6006
#   ShayBox/Riden   (MIT)         https://github.com/awto-au/riden
# See ATTRIBUTION.md for full lineage.

from __future__ import annotations

from abc import ABC, abstractmethod

from modbus_tk.defines import (
    READ_HOLDING_REGISTERS,
    WRITE_MULTIPLE_REGISTERS,
    WRITE_SINGLE_REGISTER,
)
from modbus_tk.exceptions import ModbusInvalidResponseError
from modbus_tk.modbus_rtu import RtuMaster
from serial import Serial


# ---------------------------------------------------------------------------
# Model detection helpers
# (extracted from ShayBox/Riden Riden.__init__ — MIT licence)
# ---------------------------------------------------------------------------

def _model_info(device_id: int) -> dict:
    """Return model type string and v/i/p multipliers for a given device ID."""
    if device_id >= 60241:
        return dict(type="RD6024", v_multi=100, i_multi=100, p_multi=100)
    if 60180 <= device_id <= 60189:
        return dict(type="RD6018", v_multi=100, i_multi=100, p_multi=100)
    if 60120 <= device_id <= 60124:
        return dict(type="RD6012", v_multi=100, i_multi=100, p_multi=100)
    if 60125 <= device_id <= 60129:
        # i_multi is dynamic (depends on I_RANGE register) — caller must check
        return dict(type="RD6012P", v_multi=1000, i_multi=1000, p_multi=1000)
    if 60060 <= device_id <= 60064:
        return dict(type="RD6006", v_multi=100, i_multi=1000, p_multi=100)
    if device_id == 60065:
        return dict(type="RD6006P", v_multi=1000, i_multi=10000, p_multi=1000)
    if device_id == 60066:
        return dict(type="RK6006", v_multi=100, i_multi=1000, p_multi=100)
    return dict(type="unknown", v_multi=100, i_multi=1000, p_multi=100)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class RidenTransport(ABC):
    """Minimal Modbus RTU interface over any physical link."""

    @abstractmethod
    def open(self) -> None:
        """Open the transport (connect serial port, TCP socket, BLE, …)."""

    @abstractmethod
    def close(self) -> None:
        """Release the transport."""

    @property
    @abstractmethod
    def address(self) -> int:
        """Modbus slave address."""

    @abstractmethod
    def read(self, register: int, count: int = 1) -> tuple[int, ...]:
        """Read *count* holding registers starting at *register*.

        Returns a tuple of raw integer register values (always a tuple,
        even for count=1, for consistency).
        """

    @abstractmethod
    def write(self, register: int, value: int) -> None:
        """Write a single holding register."""

    @abstractmethod
    def write_multiple(self, register: int, values: tuple | list) -> None:
        """Write a contiguous block of holding registers."""


# ---------------------------------------------------------------------------
# Serial transport (USB serial / Bluetooth RFCOMM)
# ---------------------------------------------------------------------------

class SerialTransport(RidenTransport):
    """Modbus RTU over a serial port (USB or BT RFCOMM).

    Replaces the unbounded-retry read/write methods from ShayBox/Riden with
    bounded retries (default 3). Raises TimeoutError after exhausting retries
    instead of recursing forever on flaky links.

    Args:
        port:     Serial device path, e.g. '/dev/ttyUSB0' or '/dev/rfcomm0'.
        baud:     Baud rate (default 115200).
        address:  Modbus slave address (default 1).
        retries:  Number of attempts before raising TimeoutError (default 3).
        timeout:  Serial read timeout in seconds (default 0.5).
    """

    def __init__(
        self,
        port: str,
        baud: int = 115200,
        address: int = 1,
        retries: int = 3,
        timeout: float = 0.5,
    ) -> None:
        self._port    = port
        self._baud    = baud
        self._address = address
        self._retries = retries
        self._timeout = timeout
        self._serial: Serial | None = None
        self._master: RtuMaster | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        self._serial = Serial(self._port, self._baud, timeout=self._timeout)
        self._master = RtuMaster(self._serial)
        self._master.set_timeout(self._timeout)

    def close(self) -> None:
        if self._master is not None:
            try:
                self._master.close()
            except Exception:
                pass
            self._master = None
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    @property
    def address(self) -> int:
        return self._address

    @property
    def port(self) -> str:
        return self._port

    @property
    def baud(self) -> int:
        return self._baud

    # ------------------------------------------------------------------
    # Modbus operations — bounded retries
    # ------------------------------------------------------------------

    def _execute(self, fn, description: str):
        last_exc: Exception | None = None
        for _ in range(self._retries):
            try:
                return fn()
            except ModbusInvalidResponseError as exc:
                last_exc = exc
        raise TimeoutError(f"modbus {description} failed after {self._retries} retries") from last_exc

    def read(self, register: int, count: int = 1) -> tuple[int, ...]:
        if self._master is None:
            raise IOError("transport not open")
        result = self._execute(
            lambda: self._master.execute(
                self._address, READ_HOLDING_REGISTERS, register, count
            ),
            f"read reg={register} count={count}",
        )
        return result  # modbus_tk already returns a tuple

    def write(self, register: int, value: int) -> None:
        if self._master is None:
            raise IOError("transport not open")
        self._execute(
            lambda: self._master.execute(
                self._address, WRITE_SINGLE_REGISTER, register, 1, value
            ),
            f"write reg={register} value={value}",
        )

    def write_multiple(self, register: int, values: tuple | list) -> None:
        if self._master is None:
            raise IOError("transport not open")
        self._execute(
            lambda: self._master.execute(
                self._address, WRITE_MULTIPLE_REGISTERS, register, 1, values
            ),
            f"write_multiple reg={register} count={len(values)}",
        )


# ---------------------------------------------------------------------------
# TCP stub  (WiFi bridge / Modbus TCP gateway)
# ---------------------------------------------------------------------------

class TcpTransport(RidenTransport):
    """Modbus RTU tunnelled over TCP (e.g. serial-to-WiFi bridge).

    Not yet implemented — raises NotImplementedError on open().
    Placeholder for future pyserial socket:// URL support.
    """

    def __init__(self, host: str, port: int = 8080, address: int = 1) -> None:
        self._host    = host
        self._port    = port
        self._address = address

    def open(self) -> None:
        raise NotImplementedError("TcpTransport is not yet implemented")

    def close(self) -> None:
        pass

    @property
    def address(self) -> int:
        return self._address

    def read(self, register: int, count: int = 1) -> tuple[int, ...]:
        raise NotImplementedError("TcpTransport is not yet implemented")

    def write(self, register: int, value: int) -> None:
        raise NotImplementedError("TcpTransport is not yet implemented")

    def write_multiple(self, register: int, values: tuple | list) -> None:
        raise NotImplementedError("TcpTransport is not yet implemented")


# ---------------------------------------------------------------------------
# BLE stub  (RK6006-BT native BLE via bleak)
# ---------------------------------------------------------------------------

class BleTransport(RidenTransport):
    """Native BLE transport for RK6006-BT via bleak.

    Not yet implemented — raises NotImplementedError on open().
    See BLE_ROADMAP.md for the planned implementation.
    """

    def __init__(self, mac: str, address: int = 1) -> None:
        self._mac     = mac
        self._address = address

    def open(self) -> None:
        raise NotImplementedError("BleTransport is not yet implemented")

    def close(self) -> None:
        pass

    @property
    def address(self) -> int:
        return self._address

    def read(self, register: int, count: int = 1) -> tuple[int, ...]:
        raise NotImplementedError("BleTransport is not yet implemented")

    def write(self, register: int, value: int) -> None:
        raise NotImplementedError("BleTransport is not yet implemented")

    def write_multiple(self, register: int, values: tuple | list) -> None:
        raise NotImplementedError("BleTransport is not yet implemented")
