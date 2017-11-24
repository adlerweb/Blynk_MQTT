#!/usr/bin/python2
'''
 Blynk.cc to MQTT broker bridge
 
 Example:
   ./blynk-mqtt.py -t YourAppToken --dump

 Arguments:
   -h, --help
	  Show this help
   -s, --server
	  Blynk server, defaults to cloud.blynk.cc
   -p, --port
	  Blynk server port, defaults to 8442
   -t, --token
	  Your Blynk access token
   --mqtt-server
	  MQTT server name or IP
   --mqtt-port
	  MQTT server port
   --topic
	  MQTT topic to subscript and write to
   -v, --dump
	  write all messages to console
   --sndbuf
   --rcvbuf
   --nodelay

 Author:   Volodymyr Shymanskyy, Aliaksei
 License:  The MIT license
'''
import select, socket, struct
import os, sys, time, getopt
import paho.mqtt.client as mqtt
from threading import Thread

# Configuration options

# Parse command line options
try:
	opts, args = getopt.getopt(sys.argv[1:],
		"hvs:p:t:",
		["help", "server=", "port=", "token=", "sndbuf=", "rcvbuf=", "nodelay=", "dump", "mqtt-server=", "mqtt-port=", "topic="])
except getopt.GetoptError:
	print >>sys.stderr, __doc__
	sys.exit(2)

# Default options
SERVER = "cloud.blynk.cc"
PORT = 8442
NODELAY = 1	 # TCP_NODELAY
SNDBUF = 0	  # No SNDBUF override
RCVBUF = 0	  # No RCVBUF override
TOKEN = "YourAppToken"
DUMP = 0

MQTT_SERVER = "test.mosquitto.org"
MQTT_PORT = 1883
# MQTT_LOGIN = ""
# MQTT_PASSWORD = ""
MQTT_CLIENT = "blynk.cc"
TOPIC = "/blynk"

# topics to virtual pins translate table
translate_topic = (
	('sensors/bmpt', 0),
	('sensors/bmpp', 1),
	('sensors/dhtt1', 2),
	('sensors/dhth1', 3),
	('sensors/freemem', 4),
	('sensors/uptime', 5),
)

# other blynk nodes inside the project
bridges = [
	"AnotherAppToken"
]

# last pin state storage
pin_storage = {}

for o, v in opts:
	if o in ("-h", "--help"):
		print __doc__
		sys.exit()
	elif o in ("-s", "--server"):
		SERVER = v
	elif o in ("-p", "--port"):
		PORT = int(v)
	elif o in ("-t", "--token"):
		TOKEN = v
	elif o in ("--sndbuf",):
		SNDBUF = int(v)
	elif o in ("--rcvbuf",):
		RCVBUF = int(v)
	elif o in ("--nodelay",):
		NODELAY = int(v)
	elif o in ("-v", "--dump",):
		DUMP = 1
	elif o in ("--mqtt-server",):
		MQTT_SERVER = v
	elif o in ("--mqtt-port",):
		MQTT_PORT = v
	elif o in ("--topic",):
		TOPIC = v


# Blynk protocol helpers

hdr = struct.Struct("!BHH")

class MsgType:
	RSP	= 0
	LOGIN  = 2
	PING   = 6
	BRIDGE = 15
	HW	 = 20

class MsgStatus:
	OK	 = 200

def hw(*args):
	# Convert params to string and join using \0
	data = "\0".join(map(str, args))
	dump("< " + " ".join(map(str, args)))
	# Prepend HW command header
	return hdr.pack(MsgType.HW, genMsgId(), len(data)) + data

def handle_hw(data, mqtt):
	params = data.split("\0")
	cmd = params.pop(0)
	if cmd == 'info':
		pass

	### VIRTUAL pin operations
	if cmd == 'vw':		   # This should call user handler
		pin = int(params.pop(0))
		val = params.pop(0)
		log("Virtual write pin %d, value %s" % (pin, val))
		mqtt.publish(u"%s/vw/%d" % (TOPIC, pin), val)
		
	elif cmd == 'vr':		   # This should call user handler
		pin = int(params.pop(0))
		log("Virtual read pin %d" % pin)
		mqtt.publish(u"%s/vr/%d" % (TOPIC, pin))
		try:
			conn.sendall(hw("vw", pin, pin_storage[pin]))
		except:
			pass
		
	else:
		log("Unknown HW cmd: %s" % cmd)

static_msg_id = 1
def genMsgId():
	global static_msg_id
	static_msg_id += 1
	return static_msg_id

# Other utilities

start_time = time.time()
def log(msg):
	print "[{:7.3f}] {:}".format(float(time.time() - start_time), msg)

def dump(msg):
	if DUMP:
		log(msg)

def receive(sock, length):
	d = []
	l = 0
	while l < length:
		r = ''
		try:
			r = sock.recv(length-l)
		except socket.timeout:
			continue
		if not r:
			return ''
		d.append(r)
		l += len(r)
	return ''.join(d)

# Threads

def readthread(conn, mqtt):
	while (True):
		data = receive(conn, hdr.size)
		if not data:
			break
		msg_type, msg_id, msg_len = hdr.unpack(data)
		dump("Got {0}, {1}, {2}".format(msg_type, msg_id, msg_len))
		if msg_type == MsgType.RSP:
			pass
		elif msg_type == MsgType.PING:
			log("Got ping")
			# Send Pong
			conn.sendall(hdr.pack(MsgType.RSP, msg_id, MsgStatus.OK))
		elif msg_type == MsgType.HW or msg_type == MsgType.BRIDGE:
			data = receive(conn, msg_len)
			# Print HW message
			dump("> " + " ".join(data.split("\0")))
			handle_hw(data, mqtt)
		else:
			log("Unknown msg type")
			break


def writethread(conn, mqtt):
	while (True):
		time.sleep(10)
		log("Sending heartbeat...")
		conn.sendall(hdr.pack(MsgType.PING, genMsgId(), 0))

def on_mqtt_message(client, userdata, msg):
	log("Topic %s, Message %s" % (msg.topic, str(msg.payload)))
	
	topic = msg.topic
	l = len(TOPIC)

	if topic[0:l] == TOPIC:
		path = topic[l:].split('/')
		if path[1] == "vw":
			pin = int(path[2])
			pin_storage[pin] = str(msg.payload)
			conn.sendall(hw("vw", pin, str(msg.payload)))
	
	for old, pin in translate_topic:
		old_topic = u"%s/%s" % (TOPIC, old)
		if old_topic == msg.topic:
			pin_storage[pin] = str(msg.payload)
			log(u"Write topic %s to vw/%s, val %s" % (old_topic, pin, str(msg.payload)))
			conn.sendall(hw("vw", pin, str(msg.payload)))
	
	for idx, br in enumerate(bridges):
		old_topic = u"%s/%s" % (TOPIC, br)
		path = topic[l:].split('/')
		if topic[0:l] == TOPIC and (path[1] == br or path[1] == idx) and path[2] == "vw":
			log(u"Bridge topic %s to node %s pin %s val %s" % (old_topic, br, path[3], str(msg.payload)))
			
			data = [str(idx+1), "vw", path[3], msg.payload]
			msg = "\0".join(map(str, data))
	        dump("< HWSYNC " + " ".join(map(str, data)))
	        conn.sendall(hdr.pack(MsgType.BRIDGE, genMsgId(), len(msg)))
	        conn.sendall(msg)
	        data = receive(conn, hdr.size)
	        if not data:
		        log("bridge timeout")
		        return

	        msg_type, msg_id, status = hdr.unpack(data)
	        dump("Got {0}, {1}, {2}".format(msg_type, msg_id, status))

	        if status != MsgStatus.OK:
		        log("bridge %d failed: %d" % (idx+1, status))
		        return

# Main code
log('Connecting to MQTT broker %s:%d' % (MQTT_SERVER, MQTT_PORT))
try:
	mqtt = mqtt.Client(MQTT_CLIENT)
	mqtt.connect(MQTT_SERVER, MQTT_PORT, 60)
	mqtt.on_message = on_mqtt_message
except:
	log("Can't connect")
	sys.exit(1)

log('Subscribed to MQTT-Topic %s/#' % TOPIC)
mqtt.subscribe("%s/#" % TOPIC)

log('Connecting to %s:%d' % (SERVER, PORT))
try:
	conn = socket.create_connection((SERVER, PORT), 3)
except:
	log("Can't connect")
	sys.exit(1)

if NODELAY != 0:
	conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
if SNDBUF != 0:
	sndbuf = conn.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
	log('Default SNDBUF %s changed to %s' % (sndbuf, SNDBUF))
	conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SNDBUF)
if RCVBUF != 0:
	rcvbuf = conn.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
	log('Default RCVBUF %s changed to %s' % (rcvbuf, RCVBUF))
	conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RCVBUF)
	
# Authenticate
conn.sendall(hdr.pack(MsgType.LOGIN, genMsgId(), len(TOKEN)))
conn.sendall(TOKEN)
data = receive(conn, hdr.size)
if not data:
	log("Auth timeout")
	sys.exit(1)

msg_type, msg_id, status = hdr.unpack(data)
dump("Got {0}, {1}, {2}".format(msg_type, msg_id, status))

if status != MsgStatus.OK:
	log("Auth failed: %d" % status)
	sys.exit(1)
	
# Bind bridges
for idx, br in enumerate(bridges):
	data = [str(idx+1), "i", br]
	msg = "\0".join(map(str, data))
	dump("< BRIDGE " + " ".join(map(str, data)))
	conn.sendall(hdr.pack(MsgType.BRIDGE, genMsgId(), len(msg)))
	conn.sendall(msg)
	data = receive(conn, hdr.size)
	if not data:
		log("bridge timeout")
		sys.exit(1)

	msg_type, msg_id, status = hdr.unpack(data)
	dump("Got {0}, {1}, {2}".format(msg_type, msg_id, status))

	if status != MsgStatus.OK:
		log("bridge %d failed: %d" % (idx+1, status))
		sys.exit(1)

wt = Thread(target=readthread,  args=(conn, mqtt))
rt = Thread(target=writethread, args=(conn, mqtt))

wt.start()
rt.start()

mqtt.loop_forever()

wt.join()
rt.join()


conn.close()
