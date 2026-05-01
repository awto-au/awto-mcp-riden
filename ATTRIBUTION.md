# Attribution

This project builds on prior work from the open-source community.
Each upstream source is credited individually below.

---

## Baldanos/rd6006

**Repository:** https://github.com/Baldanos/rd6006  
**License:** Apache-2.0  
**Contributors:** Baldanos, scheric, MKesenheimer, AndKe, simeonmiteff, MPM1107, phsdv, seapython  

The original Python module for controlling Riden RD6006 power supplies over Modbus RTU.
It documents the complete Modbus register map for the RD60xx family (`registers.md`),
which remains the authoritative reference for register addresses used throughout this project.

> **Note:** ShayBox/Riden (below) is "based on" this work per their own README, and the
> register table in ShayBox's README links directly to `Baldanos/rd6006/registers.md`.
> The Apache-2.0 terms on the original register-map documentation and rd6006 driver code
> apply to those portions as inherited by ShayBox/Riden.

---

## ShayBox/Riden

**Repository:** https://github.com/ShayBox/Riden  
**License:** MIT  
**Contributors:** ShayBox, bluecube, zalexua, geeksville, wormyrocks  

A Python library extending Baldanos/rd6006 to support the full RD60xx/RK60xx product
family (RD6006, RD6006P, RD6012, RD6012P, RD6018, RD6024, RK6006). Provides the
`Riden` class (Modbus RTU via `modbus-tk`) and `Register` enum used directly by this
project's `riden_daemon.py`.

The `Bootloader` class in ShayBox/Riden is based on
[tjko/riden-flashtool](https://github.com/tjko/riden-flashtool) (AGPL-3.0).
**This project does not use the `Bootloader` class**, so the AGPL-3.0 terms do not
propagate here.

---

## awto-au/riden

**Repository:** https://github.com/awto-au/riden  
**License:** MIT (fork of ShayBox/Riden)  

Our traceability fork of ShayBox/Riden, held at a known-good commit, used as the
vendored upstream for this project. This fork was created solely to pin the dependency
to a revision under our control and does not introduce code changes.

---

## tjko/riden-flashtool *(indirect reference only)*

**Repository:** https://github.com/tjko/riden-flashtool  
**License:** AGPL-3.0  
**Author:** Timo Kokkonen (tjko), mdjurfeldt, cygeus, JorgHendriks  

Riden firmware flash tool, credited by ShayBox/Riden as the basis for their
`Bootloader` class. Included here for lineage completeness. **Not used by this project.**
AGPL-3.0 terms do not apply to this codebase.

---

## License compatibility summary

| Upstream | License | Used directly? | AGPL risk? |
|---|---|---|---|
| Baldanos/rd6006 | Apache-2.0 | Indirectly (via ShayBox) | No |
| ShayBox/Riden | MIT | Yes (via awto-au/riden fork) | No |
| awto-au/riden | MIT | Yes | No |
| tjko/riden-flashtool | AGPL-3.0 | No | No |

This project is released under the **MIT license**. See `LICENSE` for the full text.
