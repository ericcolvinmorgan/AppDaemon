import appdaemon.plugins.hass.hassapi as hass
import datetime

#
# Motion Control - Trigger actions based on motion sensors.
#
# Args:
# manual_toggle - Input control used to override automatic controls
# motion_sensors - The sensors that will be used to determine if entities should be automatically controlled
# controlled_entities - The entities that will be automatically updated at provided times 
#

class MotionControl(hass.Hass):
	def initialize(self):
		self.__manual_toggle = self.args["manual_toggle"]
		self.__motion_sensors = self.args["motion_sensors"]
		self.__entity_rulesets = self.args["entity_rulesets"]
		self.__current_entity_ruleset = {}

		# Register Manual Toggle Handlers
		self.handle_manual_toggle = self.listen_state(self.__on_manual_toggle, self.__manual_toggle['entity'])

		# Register Sensor Handlers
		for (sensor, sensor_details) in self.__motion_sensors.items():
			self.log("Registering Sensor: %s." % (sensor))
			self.handle_motion = self.listen_state(self.__on_motion_change, sensor, new = sensor_details['on_state'].casefold())
			self.handle_no_motion = self.listen_state(self.__on_motion_change, sensor, old = sensor_details['on_state'].casefold(), duration = sensor_details['duration'])
			sensor_details['on'] = (sensor_details['on_state'].casefold() == self.get_state(sensor))
			self.log("Current Sensor Values: %s" % (self.__motion_sensors[sensor]))

		# Register Ruleset Time Handlers
		for ruleset in self.__entity_rulesets:
			time = self.parse_time(ruleset["end"])
			run_time = datetime.time(time.hour, time.minute, time.second + 1)
			self.run_daily(self.__on_ruleset_change, run_time)
			
		self.update_entity_states()

	def update_entity_states(self):
		self.__update_current_entity_ruleset()
		self.__trigger_lights()

	def __update_current_entity_ruleset(self):
		# Determine if current ruleset is valid
		if(self.__time_in_range(self.__current_entity_ruleset) == False):
			# Update to latest ruleset 
			for ruleset in self.__entity_rulesets:
				if(self.__time_in_range(ruleset)):
					self.log("New ruleset applied.  Start: %s End: %s" % (ruleset['start'], ruleset['end']))
					self.__current_entity_ruleset = ruleset
					break

	def __time_in_range(self, ruleset):
		# Ensure ruleset has been loaded and that it doesn't cover a full (full days rulesets always valid)
		if (ruleset == {}): return False
		if (ruleset['start'] == ruleset['end']): return True
		self.log("Ruleset Valid: Start: %s End: %s Valid: %s" % (ruleset['start'], ruleset['end'], self.now_is_between(ruleset['start'], ruleset['end'])))
		return self.now_is_between(ruleset['start'], ruleset['end']) 

	def __on_ruleset_change(self, kwargs):
		self.update_entity_states()

	def __on_manual_toggle(self, entity, attribute, old, new, kwargs):
		self.log("Manual Toggle Triggers: entity:%s attribute:%s old:%s new:%s" % (entity, attribute, old, new))
		self.__trigger_lights()

	def __on_motion_change(self, entity, attribute, old, new, kwargs):
		self.log("Motion State Detected: entity:%s attribute:%s old:%s new:%s" % (entity, attribute, old, new))
		self.__update_sensor_status(entity, new.casefold())
		self.__trigger_lights()
	
	def __update_sensor_status(self, entity, value):
		self.__motion_sensors[entity]['on'] = (value == self.__motion_sensors[entity]['on_state'].casefold())

	def __trigger_lights(self):
		auto_toggle = (self.get_state(self.__manual_toggle['entity']).casefold() == self.__manual_toggle['automatic_state'].casefold()) 
		if(auto_toggle):
			if any(sensor['on'] == True for sensor in self.__motion_sensors.values()):
				self.log("Turning lights on")				
				self.__apply_entity_rules(self.__current_entity_ruleset, True)
			else:
				self.__apply_entity_rules(self.__current_entity_ruleset, False)

		else: self.log("Automatic control currently disabled.") 

	def __apply_entity_rules(self, entity_ruleset, on):
		for entity in entity_ruleset['entities']:
			self.log(entity)
			entity_on = on and entity['device_on'] 
			self.log(entity_on)
			if(entity_on):
				self.log("Attempting request for: %s" % (entity['entity']))
				if 'attributes' in entity: 
					self.turn_on(entity['entity'], **entity['attributes'])
				else:
					self.turn_on(entity['entity'])
			else:
				self.turn_off(entity['entity'])