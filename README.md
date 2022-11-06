# Hive TRV Boost Mode

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

*[AppDaemon](https://github.com/home-assistant/appdaemon) app to mimick the behaviour of boost mode on your Hive Radiator Valves.*

In order to keep heating to a minimum, installing smart radiator valves is the first bit, however you can trigger heating for specific rooms depending on the temperatures set for your radiator valves. This will also stop heating once the target temperature is reached.

This assumes you are using Zigbee2MQTT to connect to your Hive Heating thermostat.

## Devices used

- [Hive Thermostat SLR1b](https://www.zigbee2mqtt.io/devices/SLR1b.html)
- [Hive UK7004240 Radiator Valve](https://www.zigbee2mqtt.io/devices/UK7004240.html)

## Installation

Use [HACS](https://github.com/custom-components/hacs) or [download](https://github.com/dwardu89/hive-trv-appdaemon/releases) the `heating` directory from inside the `apps` directory here to your local `apps` directory, then add the configuration to enable the `heating` module.

## App configuration

```yaml
heating:
  module: hive_trv_heating
  class: HiveHeating
  main_thermostat: climate.living_room_thermostat
  main_thermostat_zigbee_set_topic: "zigbee2mqtt/Living Room Thermostat/set"
  trv_list:
    - climate.office_radiator_valve
    - climate.main_bedroom_cove_radiator_valve
    - climate.main_bedroom_radiator_valve
    - climate.hallway_radiator_valve
    - climate.second_bedroom_radiator_valve
  log: heat_log
  frost_protection: True
  trv_boost_mode: input_boolean.trv_heating_boost_mode
  trv_boost_mode_temperature: input_number.trv_boost_mode_temperature

```

key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | | The module name of the app.
`class` | False | string | | The name of the Class.
`main_thermostat` | False | string | | The entity in home assistant referring to your main Hive thermostat.
`main_thermostat_zigbee_set_topic` | False | string | | The MQTT set topic referring to your main Hive thermostat.
`trv_list` | False | list(string) | | The list of TRV entities which you would like to have the app monitor for boost mode.
`log` | True | string | `heat_log` | The log in appdaemon to write the logs to. It's suggested you create a log specific to this to separate logging.
`frost_protection` | False | boolean | True | Enables frost protection, kicking off boost mode irreespective if boost mode is enabled. (TO BE IMPLEMENTED)
`trv_boost_mode` | False | string | | The input_boolean entity to control this app, enabling or disabling boost mode.
`trv_boost_mode_temperature` | False | string | | The input_number entity to determine what is the maximum boost mode value the `main_thermostat` should be set at.

## Appdaemon yaml 

In order to set the logs output, add this log entry to your `appdaemon.yaml` file. If you do not add it, it will default to the default log output.

```yaml
logs:
  heat_log:
    name: HeatLog
```

## Logic of Application

This app will use the `hvac_action` set in each Hive radiator valve, it probably can be used with other TRV's to interact with the Hive emergency boost feature. Once the radiator valve requires heat, it will set it's `hvac_action` attribute to `heating`. `heating` Triggers this appdaemon to push an emergency boost message to the main Hive thermostat. If the app is restarted or unexpectedly crashes, it will check if heating is required on a minute by minute basis just to ensure that no excess heating is done to save on costs.

You can set automations which will disable this app by setting the `trv_boost_mode` variable to False by changing the `input_boolean` provided.
