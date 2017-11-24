# Blynk.cc to MQTT broker bridge

[Blynk.cc](http://blynk.cc/) is a simple DIY-IoT platform with [Android application](https://play.google.com/store/apps/details?id=cc.blynk). It uses a central cloud based or selfhosted server as well as its own protocol to communicate to hardware nodes.

This is a simple bridge between the Blynk infrastructure and MQTT. It is written in python2 and requires the paho-mqtt python module. Only virtual pins can be used.

## Requirements

- Python 2
- [paho-mqqt](https://pypi.python.org/pypi/paho-mqtt)

## Configuration

You have to supply at least your Blynk application token, MQTT server and a topic to use. You can either enter them directly in the source code or pass them using the arguments described below.

### Configuration using source
-----

```
TOKEN = "YourAppToken"
MQTT_SERVER = "test.mosquitto.org"
MQTT_PORT = 1883
TOPIC = "/blynk"
```
The bridge subscribes to all /blynk/# topics in this case.

#### MQTT translations
You can use the translation table to add additional aliases:
```
translate_topic = (
	('sensors/bmpt', 0),
	('sensors/bmpp', 1),
)
```

#### Blynk bridging

Using this feature you can control other Blynk-Nodes using MQTT. This requires you to add the other Blynk-nodes access keys into the configuration. Please note the bridging is designed to work directly between the devices so you do not get instant feedback inside the app. Also you'll only be able to send commands to other devices, not receive any messages or values without modifying the existing nodes.

```
bridges = [
	"AnotherAppToken"
]
```

When configured values published to /blynk/AnotherAppToken/vw/1 will be relayed to the other devices virtual pin 1.

### Configuration using arguments

 - --mqtt-server test.mosquitto.org
 - --mqtt-port 1883
 - -t YourAppToken
 - --topic "/ESP009xxxxx"

## Starting the bridge

Start using ```python2 blynk-mqtt.py```

You can now assign this script like any other hardware inside the Blynk-App and as such control or read your MQQT-Devices.

# Internals

## MQTT Topics

Virtual pin 0 write request will be published as /ESP009xxxxx/vw/0.
Virtual pin 0 read request will be published as /ESP009xxxxx/vr/0, also an answer containing the latest pin value will be sent to Blynk server

This example will send values from topic /ESP009xxxxx/sensors/bmpt to virtual pin 0.


# Copyright

This work based on blynk-library/tests/pseudo-library.py from the Blynk.cc project.
Written by Volodymyr Shymanskyy, Aliaksei
Contributors: adlerweb

Licensed under MIT License
