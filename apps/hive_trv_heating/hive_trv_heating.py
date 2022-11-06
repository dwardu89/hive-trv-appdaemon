import appdaemon.plugins.hass.hassapi as hass
import json
import datetime

#
# HiveHeating App
#
# Args:
#

# Will need to have something check periodically if heat is still required when nothing changes and renew the emergency_heating

APP_NAME = "Hive TRV Boost Mode"
APP_ICON = "🔥"

HVAC_ACTION_OFF = "off"
HVAC_ACTION_HEATING = "heating"

class HiveHeating(hass.Hass):

    def initialize(self):
        self.log("Initializing Hive Heating")
        # Trigger on change of target temperature
        self.log("Get Main Thermostat")
        self.log("Main Thermastat [{}]".format(self.args["main_thermostat"]))
        self.main_thermostat = self.args["main_thermostat"]
        self.log("Gather TRV list")
        for entity in self.args["trv_list"]:
            self.log("TRV [{}]".format(entity))
        self.trv_list = self.args["trv_list"]
        self.log("Is anyone home? [{}]".format(self.anyone_home()))
        self.log("Registering all TRVs with a HeatRequired callback".format(entity))
        self.listen_state(self.heating_required,
                          self.args["trv_list"], attribute="hvac_action")
        self.log("Using [{}] to track TRV Boost mode".format(
            self.args["trv_boost_mode"]))
        self.trv_boost_mode_entity = self.args["trv_boost_mode"]
        self.listen_state(self.boost_mode_disabled,
                          self.args["trv_boost_mode"])
        self.trv_boost_mode_temperature_entity = self.args["trv_boost_mode_temperature"]
        self.log("Target Mode Temperature Entity [{}]".format(
            self.trv_boost_mode_temperature_entity))
        self.log("Testing if entity is obtainable [{}]".format(
            self.get_state(self.trv_boost_mode_temperature_entity)), level="DEBUG")
        self.main_thermostat_zigbee_set_topic = self.args["main_thermostat_zigbee_set_topic"]

        self.SETPOINT_HOLD_DURATION = 30
        # Check if temperatures need to be run, this is used to check if appdaemon is restarted haphazardly
        self.run_minutely(self.temperature_check, datetime.time(0, 0, 0))

    def boost_mode_disabled(self, entity, attribute, old, new, kwargs):
        self.log("Boost Mode changed from [{}] => [{}]".format(old, new))

    def heating_required(self, entity, attribute, old, new, kwargs):
        target_temperature = self.get_state(entity, attribute="temperature")
        current_temperature = self.get_state(
            entity, attribute="current_temperature")

        trv_boost_mode_temperature = float(
            self.get_state(self.trv_boost_mode_temperature_entity))
        self.log("TRV Boost Mode Temperature [{}]".format(
            trv_boost_mode_temperature), level="DEBUG")

        self.log("TRV [{}]".format(entity), level="DEBUG")
        self.log("Attribute [{}] from {} => {}".format(
            attribute, old, new), level="DEBUG")
        self.log("Temperature Currently [{}], Required [{}]".format(
            current_temperature, target_temperature), level="DEBUG")

        # Check if the valve requires heat, if so enable boost mode for an hour
        require_boost_mode = self.is_boost_mode_still_required(entity, new == HVAC_ACTION_HEATING)
        if self.is_boost_mode_enabled() and require_boost_mode:
            self.log("Enabling Boost Mode")
            # Check if there's another TRV with a higher entity boost mode
            if target_temperature > trv_boost_mode_temperature:
                self.set_state(self.trv_boost_mode_temperature_entity,
                               state=target_temperature)
                trv_boost_mode_temperature = target_temperature
                # Also set the target temperature
                self.start_emergency_boost(trv_boost_mode_temperature)
        else:
            # disable boost mode, but check if the temperatures around the other valves are required
            # and check if those valves have boost mode enabled for them.
            # Eventually check if the valve is in the schedule
            self.set_state(self.trv_boost_mode_temperature_entity, state=5)
            self.log(
                "Disabling Boost Mode, Returning Main Thermostat to previous state")
            self.stop_emergency_boost()

    def is_boost_mode_still_required(self, entity, radiator_heating_required):
        if not radiator_heating_required:
            # If No heating is required for this trv, check if it is required for the other TRVs.
            for trv in self.trv_list:
                hvac_action = self.get_state(trv, attribute="hvac_action")
                if hvac_action == HVAC_ACTION_HEATING:
                    self.log("TRV [{}] still has hvac_action: {}".format(
                        trv, hvac_action))
                    return True
        else:
            self.log("TRV [{}] sent a hvac_action: {} status".format(
                entity, radiator_heating_required), level="DEBUG")
            return True
        self.log("No Heat is required any more", level="DEBUG")
        return False

    def get_max_radiator_temperature(self):
        max_temp = 5.0
        for trv in self.trv_list:
            trv_temp_required = float(
                self.get_state(trv, attribute="temperature"))
            if trv_temp_required > max_temp:
                max_temp = trv_temp_required
        return max_temp

    def temperature_check(self, kwargs):
        # Check if temperatures need to be run, this is used to check if appdaemon is restarted haphazardly
        self.log("Checking Temperature heat is required", level="DEBUG")

        # Check if the valve requires heat, if so enable boost mode for an hour
        require_boost_mode = self.is_boost_mode_still_required(
            entity=None, radiator_heating_required=False)
        main_thermostat_system_mode = self.get_state(
            self.main_thermostat, attribute="system_mode")
        self.log("Main Thermostat System Mode [{}]".format(
            main_thermostat_system_mode), level="DEBUG")
            
        if self.is_boost_mode_enabled() and require_boost_mode and not main_thermostat_system_mode == "emergency_heating":
            self.log("Enabling Boost Mode")
            # Get the highest temperature and start emergency boost
            self.start_emergency_boost(self.get_max_radiator_temperature())
        else:
            # disable boost mode, but check if the temperatures around the other valves are required
            # and check if those valves have boost mode enabled for them.
            # Eventually check if the valve is in the schedule
            # Only turn off if emergency heating is turned on. Otherwise there might be an external factor or heating.
            if main_thermostat_system_mode == "emergency_heating" and (not self.is_boost_mode_enabled() or not require_boost_mode):
                self.set_state(self.trv_boost_mode_temperature_entity, state=5)
                self.log(
                    "Still on emergency_heating. Disabling Boost Mode")
                self.stop_emergency_boost()

    def generate_mqtt_message(self, system_mode, temperature_setpoint_hold_duration, temperature_setpoint_hold=None, occupied_heating_setpoint=None):
        mqtt_message = dict()
        mqtt_message["system_mode"] = system_mode
        mqtt_message["temperature_setpoint_hold_duration"] = temperature_setpoint_hold_duration
        if temperature_setpoint_hold is not None:
            mqtt_message["temperature_setpoint_hold"] = temperature_setpoint_hold
        if occupied_heating_setpoint is not None:
            mqtt_message["occupied_heating_setpoint"] = occupied_heating_setpoint
        return json.dumps(mqtt_message)

    def call_mqtt_service(self, topic, payload):
        self.log("Publish message to topic [{}] with payload [{}]".format(
            topic, payload), level="DEBUG")
        self.call_service("mqtt/publish", topic=topic, payload=payload)

    def ensure_target_temperature_in_range(self, target_temperature):
        if target_temperature < 5:
            return 5
        elif target_temperature > 32:
            return 32
        return target_temperature

    def start_emergency_boost(self, target_temperature):
        target_temperature_ranged = self.ensure_target_temperature_in_range(
            target_temperature)
        mqtt_message = self.generate_mqtt_message(system_mode="emergency_heating",
                                                  temperature_setpoint_hold="1",
                                                  temperature_setpoint_hold_duration=self.SETPOINT_HOLD_DURATION,
                                                  occupied_heating_setpoint=str(target_temperature_ranged))

        self.log("Emergency Boost Mqtt message [{}]".format(
            mqtt_message), level="DEBUG")

        self.call_mqtt_service(
            topic=self.main_thermostat_zigbee_set_topic, payload=mqtt_message)

    def stop_emergency_boost(self):
        # target_temperature_ranged = self.ensure_target_temperature_in_range(
        #     target_temperature)
        mqtt_message = self.generate_mqtt_message(system_mode="emergency_heating",
                                                  temperature_setpoint_hold_duration=0)

        self.call_mqtt_service(
            topic=self.main_thermostat_zigbee_set_topic, payload=mqtt_message)

    def heating_mode_on(self, target_temperature):
        target_temperature = ensure_target_temperature_in_range(
            target_temperature)
        mqtt_message = self.generate_mqtt_message(system_mode="heat",
                                                  temperature_setpoint_hold="1",
                                                  occupied_heating_setpoint=target_temperature)

    def heating_mode_off(self, target_temperature):
        target_temperature = ensure_target_temperature_in_range(
            target_temperature)
        mqtt_message = self.generate_mqtt_message(system_mode="off",
                                                  temperature_setpoint_hold=0)

    def is_boost_mode_enabled(self):
        boost_mode_state = self.get_state(self.trv_boost_mode_entity)
        self.log("Boost Mode State [{}]".format(
            boost_mode_state), level="DEBUG")
        return boost_mode_state == "on"
