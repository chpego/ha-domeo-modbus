# S&P DOMEO EVO for Home Assistant

<img src="https://raw.githubusercontent.com/chpego/ha-domeo-modbus/main/custom_components/domeo_modbus/brand/icon.png" alt="" width="96" align="right">

- Read and control an **S&P DOMEO EVO** heat recovery ventilation unit (225, 315, 450; FL, RD, DHU, Sérénité) from Home Assistant, over its Modbus RTU port.
- Fully local: through an RS485 to Modbus TCP gateway or a USB RS485 adapter. No cloud, no account.
- Set up from the UI, in English or French.

[![Release][release-shield]][release]
[![Downloads][downloads-shield]][release]
[![License][license-shield]](LICENSE)
[![Tests][tests-shield]][tests]
[![Hassfest][hassfest-shield]][hassfest]
[![Repository validation][validation-shield]][validation]

[Version française](README_fr.md)

> [!NOTE]
> This integration is in **beta**. The register map follows the official S&P table, and the first real units are being tested on the [HACF forum](https://forum.hacf.fr/t/vmc-s-p-domeo-evo-225-fl-via-modbus-tcp-rtu/69801). See [Known limitations](#known-limitations).

## Contents

- [Features](#features)
- [Supported units](#supported-units)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Setup](#setup)
- [Data updates](#data-updates)
- [Entities](#entities)
- [What the integration writes](#what-the-integration-writes)
- [Automation example](#automation-example)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Related projects](#related-projects)
- [Disclaimer and license](#disclaimer-and-license)

## Features

- **Local.** Nothing leaves your network.
- **Set up from the UI.** Pick the link (network gateway or serial port), the model and the variant.
- **Airflows within the unit's limits.** Low, high and freecooling airflows are bounded by the range of your model.
- **AIRSENS probes found automatically.** One sensor per connected humidity, CO₂ or VOC probe.
- **Tells you about jumper JP1.** A diagnostic entity and a repair warn you when the unit ignores Modbus commands.
- **Safe for the link.** It never writes the unit's own address, speed or parity.
- **Diagnostics.** One-click download with the raw register map, the gateway address redacted.
- **Translated.** English and French.

## Supported units

| Unit | Status | Evidence |
| --- | --- | --- |
| **DOMEO EVO 225 RD** | Readings and commands confirmed | Two real 225 RD units ([#6](https://github.com/chpego/ha-domeo-modbus/issues/6), [#12](https://github.com/chpego/ha-domeo-modbus/issues/12)): readings, holiday mode, start boost. Filter reset is being confirmed. |
| DOMEO EVO 225 FL | Expected to work | Same unit with a wired control panel, not yet tested |
| DOMEO EVO 315, 450 | Expected to work | Same register table; airflow ranges per model from the S&P table |
| DHU, Sérénité variants | Expected to work | Humidity regulation and AIRSENS probes follow the S&P table, tested on a simulator |
| Domeo 210 FL and DHU (previous range) | Being tested | Built on the two S&P tables of 2017 (FL, and DHU for France) and a Domeo 210 YAML in use since 2021; not yet tested by an owner ([#15](https://github.com/chpego/ha-domeo-modbus/issues/15)). Choose **Domeo 210** in the model list, then FL or DHU. |

**Domeo 210, still unconfirmed on a real unit:** the order of input registers 22 and 23 (exhaust, then outdoor temperature) and holiday mode and the automatic bypass turning on with 1. Both 2017 tables say so; an older table of 2014 says the opposite. The DHU also gets its humidity regulation settings; it reports no humidity reading over Modbus. The 210 does not report jumper JP1, so a refused command is the only sign that JP1 is open. In the Europe version (three speeds and standby) there is no boost button, and the holiday switch is a standby switch.

**Not supported:** the rest of the previous Domeo range (the previous Domeo DHU or Hygro, Flexeo, Ideo, and the Atacama sold by Leroy Merlin). It uses other register tables, where the same addresses mean other settings, so the integration refuses these units when you add them as a DOMEO EVO ([#7](https://github.com/chpego/ha-domeo-modbus/issues/7)). "DHU" here means the DOMEO EVO DHU. The Atacama is said to have the same board as the Domeo 210 (HACF topic 3947): adding it as a Domeo 210 may work, but nobody has tried yet.

**Why `domeo_modbus`?** The technical name (domain `domeo_modbus`, repository `ha-domeo-modbus`) is not tied to the EVO range, so the previous Domeo range goes into this same integration, with its own register table ([#15](https://github.com/chpego/ha-domeo-modbus/issues/15), testers welcome). The integration is still shown as **S&P DOMEO EVO**.

Have one of these units? A test report with your diagnostics file is very welcome: [open an issue](https://github.com/chpego/ha-domeo-modbus/issues).

## Prerequisites

- Home Assistant **2026.10.2** or newer.
- Jumper **JP1** closed on the unit's board. With JP1 open, the unit answers readings but refuses every command. Once JP1 is closed, the unit takes orders over Modbus. According to S&P, a wired control panel then stops working; a radio control panel (RD) keeps working, as a tester's unit showed ([#12](https://github.com/chpego/ha-domeo-modbus/issues/12)). Cut the power before you open the unit.
- A link to the unit's RS485 terminals (A, B, GND):
  - a **gateway** (Waveshare RS485 TO ETH, Elfin EW11…) in **Modbus TCP to RTU** mode, or
  - a **USB RS485 adapter** on the Home Assistant host.
- Line settings: **19200 baud, 8 data bits, even parity, 1 stop bit**. These are the factory settings. 9600 baud or 2 stop bits, sometimes suggested elsewhere, do not work.

## Installation

### Marketplace

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=chpego&repository=ha-domeo-modbus)

Or add it by hand: **Settings → Marketplace → ⋮ → Custom repositories**, add `https://github.com/chpego/ha-domeo-modbus` with the type **Integration**, then download **S&P DOMEO EVO**.

### Pre-release versions

Betas are published as GitHub pre-releases. To get them, open this repository in the Marketplace and turn on its **Pre-release** switch.

### Coming from 0.2.0-beta.1

Since 0.2.0-beta.2 the integration is called `domeo_modbus` instead of `domeo_evo`, and the repository `ha-domeo-modbus` instead of `ha-domeo-evo` ([#10](https://github.com/chpego/ha-domeo-modbus/issues/10)). Home Assistant cannot carry the old entry over, so:

1. In **Settings → Devices & services**, delete the **S&P DOMEO EVO** entry.
2. In the **Marketplace**, remove the integration, then download it again from this repository.
3. Restart Home Assistant and add the unit again ([Setup](#setup)).

The entity IDs come from the unit's name, so they are the same as before and your automations keep working.

### Manually

Copy `custom_components/domeo_modbus` into your `config/custom_components/` folder and restart Home Assistant.

## Setup

[![Open your Home Assistant instance and start setting up S&P DOMEO EVO.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=domeo_modbus)

Or go to **Settings → Devices & services → Add integration → S&P DOMEO EVO**, then:

1. Choose **Network** (gateway) or **Serial port** (USB adapter).
2. Enter the gateway address and port (usually 502), or the serial port.
3. Leave the unit ID at **1** unless you changed it.
4. Pick the **model** from the rating plate (225, 315 or 450) and the **variant**. The unit does not report either, and they set the airflow ranges and the humidity settings.

To change the gateway address or the link later, use **Reconfigure** on the integration. The unit reports no serial number, so adding it again would create a second device.

## Data updates

- **Readings** (airflow, temperatures, operating mode, alarms, switches, probes): every 30 seconds.
- **Settings** (airflows, thresholds, intervals): every 5 minutes, and right after you change one.
- **Partial failures:** each part of the unit is read separately. If one part does not answer, only its entities go unavailable.
- **Silent gateway:** after three readings in a row time out, the link is reopened. Some gateways keep the connection open while the unit behind them is silent.

Home Assistant shares one connection per gateway and sends one request at a time. If another program (a YAML `modbus:` configuration, Node-RED…) talks to the same gateway, turn it off or enable the gateway's **multi-host** mode.

## Entities

| Kind | Entities |
| --- | --- |
| Sensors | Airflow, operating mode, the five air temperatures, preheater, control panel, 0-10 V input; integrated humidity (DHU, Sérénité); one sensor per AIRSENS probe (humidity, CO₂ or VOC) |
| Binary sensors | Filter replacement, defrost, motor faults, temperature probe faults, CLP contact, **Modbus control (JP1)** |
| Switches | Holiday mode, manual bypass, automatic bypass, defrost allowed |
| Buttons | Start boost, reset filter alarm |
| Selects | Automatic mode (proportional or agile), CLP contact type |
| Numbers | Low, high and freecooling airflow (limited to the model's range), bypass thresholds, manual bypass duration, filter interval, airflow correction and offset; humidity and air-quality regulation (DHU, Sérénité) |

Some diagnostic and configuration entities are disabled by default. Enable them from the device page.

A button shows **Unknown** until you press it for the first time. That is how Home Assistant shows buttons, not an error.

## What the integration writes

Nothing, until you use a command. It never writes holding registers 40001 to 40003 (the unit's address, speed and parity): a wrong value there cuts the link at the next power cycle. It does not offer the AIRSENS ID reset (coil 9), which forgets the paired probes. It only reads the addresses the S&P table documents.

## Automation example

Start a boost when the bathroom gets humid. The unit ends the boost on its own after 30 minutes; it cannot be stopped earlier over Modbus. Replace the entity IDs with your own.

```yaml
alias: "Ventilation: boost when the bathroom is humid"
triggers:
  - trigger: numeric_state
    entity_id: sensor.bathroom_humidity
    above: 70
actions:
  - action: button.press
    target:
      entity_id: button.domeo_evo_225_fl_start_boost
mode: single
```

> [!WARNING]
> Do not copy older YAML examples that call `modbus.write_register` with `address: 2`: that register is the unit's **parity**, and writing it cuts the link at the next power cycle.

## Known limitations

- **Holiday mode.** The S&P table says coil 4 is *0 = on*, but reports from two real units point the other way, so the integration reads and writes it as *1 = on* ([#6](https://github.com/chpego/ha-domeo-modbus/issues/6)). If the switch shows the opposite of what your unit does, please say so in an issue.
- **No stop boost.** The table says writing 0 stops a boost, but a real unit ignores it (FC06 and FC16 alike), and S&P support confirmed a boost cannot be stopped over Modbus. It ends on its own after 30 minutes, so the integration has no stop button.
- **No boost in holiday mode.** A real unit does not start a boost while holiday mode is on. The start boost button then fails with a message asking you to turn holiday mode off first.
- **Filter reset.** Being confirmed on real units. The integration writes coil 8, as the table says.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| A repair says *jumper JP1 is open*, or commands fail with *exception 0x01* | JP1 is open. Cut the power, close JP1, power on. The **Modbus control (JP1)** entity turns on. |
| Setup says *the unit does not answer* | Wrong line settings or wiring. Check 19200 baud, 8E1, A/B not swapped, and the gateway in Modbus TCP to RTU mode. |
| The unit stopped answering after a power cut | Its parity may have been changed by a wrong YAML write to holding register 40003 (address 2). Try odd parity on the gateway, then write `2` back to that register. |
| Humidity stuck at 54 % | No humidity sensor is fitted (FL and RD units). This is what the unit reports. |
| Pre-exchanger temperature unknown | No probe is fitted there; the unit flags it as a fault. |

### Debug logs

On the integration's card: **⋮ → Enable debug logging**, reproduce the problem, then **⋮ → Disable debug logging** to download the log.

### Diagnostics

On the integration's card: **⋮ → Download diagnostics**. Attach the file to an [issue](https://github.com/chpego/ha-domeo-modbus/issues). The gateway address is redacted.

## Contributing

Bug reports and test reports from real units are welcome, in English or French.

The test suite enforces 100 % line coverage and runs on every pull request:

```sh
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest --cov
```

The register map lives in the `domeo-evo-modbus` library, built on [`modbus-connection`](https://home-assistant-libs.github.io/modbus-connection/). This repository ships its own copy in `custom_components/domeo_modbus/domeo_evo_modbus/`; `scripts/vendor_domeo_evo_modbus.sh` updates it. Releases follow [RELEASING.md](RELEASING.md).

## Related projects

- [xtozez/homeassistant-domeo-evo-225fl-modbus](https://github.com/xtozez/homeassistant-domeo-evo-225fl-modbus): the YAML configuration that started it all, with the official S&P register table (PDF).
- [HACF forum thread](https://forum.hacf.fr/t/vmc-s-p-domeo-evo-225-fl-via-modbus-tcp-rtu/69801): wiring, gateways and real-unit findings (in French).
- [timlaing/modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway): a generic Modbus integration that ships a DOMEO EVO device file. Run one or the other on the same gateway, or enable multi-host.

## Disclaimer and license

Not affiliated with or endorsed by S&P (Soler & Palau) or Unelvent. Use at your own risk: commands change how your ventilation runs.

[MIT](LICENSE)

[release-shield]: https://img.shields.io/github/v/release/chpego/ha-domeo-modbus.svg?include_prereleases
[release]: https://github.com/chpego/ha-domeo-modbus/releases
[downloads-shield]: https://img.shields.io/github/downloads/chpego/ha-domeo-modbus/total.svg
[license-shield]: https://img.shields.io/github/license/chpego/ha-domeo-modbus.svg
[tests-shield]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/tests.yml/badge.svg
[tests]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/tests.yml
[hassfest-shield]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hassfest.yml/badge.svg
[hassfest]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hassfest.yml
[validation-shield]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hacs.yml/badge.svg
[validation]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hacs.yml
