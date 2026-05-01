# Design Notes — awto-mcp-riden

> Original design discussion (v0 spec). Preserved for reference.

---

## Question

> Do I use stock firmware or enhanced by ?? soft. Can I use BT serial?

## Answer (summary)

Yes. For MCP, use **stock firmware first** and talk to the RD60xx over **Modbus RTU serial**. The RD6006/RD60xx family is already controllable over serial Modbus, and Python libraries exist for USB serial control.

## Transport choice

```
Best:       USB serial
Good:       WiFi module with bridge/MQTT
Possible:   Bluetooth serial
Avoid:      flashing PSU firmware unless you need features
```

- **USB serial** is the cleanest. The official manual describes USB PC control via serial port, baud rate and slave address; community Python code uses Modbus over serial.
- **Bluetooth serial** should work if the BT module exposes a normal serial port (e.g. `/dev/rfcomm0` on Linux). Treat it exactly like USB serial, but expect more latency and occasional disconnects. Good enough for set/read/power-cycle, not ideal for tight logging.
- **WiFi stock firmware** is awkward but usable. The Riden WiFi board behaves like a UART bridge, not normal Modbus TCP; one project bridges it to MQTT without modifying PSU or WiFi firmware.

## Enhanced firmware options

- **UniSoft firmware:** Alternative firmware for RD6006/RD6012/RD6018 style units. Useful, but check exact model support carefully.
- **Riden-dongle firmware:** Flashes the WiFi module, not the PSU. Adds Modbus TCP, SCPI and web UI. More lab-automation friendly. Not compatible with the original mobile app.

## Roadmap

1. Start with **stock firmware + USB serial**. ✅ Done
2. **BT serial** for wireless bench use. ⏳ Planned
3. **WiFi dongle** with `riden-dongle` for SCPI / Modbus TCP. 🔮 Future
