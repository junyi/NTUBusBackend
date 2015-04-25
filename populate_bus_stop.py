from settings_local import APPLICATION_ID, REST_API_KEY, MASTER_KEY
import re, demjson, utm, urllib, urllib2
from lxml import html, etree
from urllib2 import urlopen
from HTMLParser import HTMLParser
from parse_rest.connection import register, ParseBatcher
from parse_rest.datatypes import Object, GeoPoint

class BusStop(Object):
	pass

class Route(Object):
	pass

class RouteBusStop(Object):
	pass

h = HTMLParser()
register(APPLICATION_ID, REST_API_KEY, master_key=MASTER_KEY)

def unescape(s):
	if s is not None:
		return h.unescape(s)
	else:
		return s

def get_bus_stop_and_route_data():
	response = urlopen("http://campusbus.ntu.edu.sg/ntubus/")
	raw_html = response.read()
	response.close()

	tree = html.fromstring(raw_html)

	script_nodes = tree.xpath("//script/node()")

	for node in script_nodes:
		if "var param" in node:
			node = node.replace("\n", "").replace("\t", "").replace("  ", " ")
			regex = "var param = (.*?);var"
			param = re.findall(regex, node, re.M)[0]
			return demjson.decode(param)

def get_bus_stops_for_route(routeid):
	data = urllib.urlencode({'routeid': routeid})
	url = "http://campusbus.ntu.edu.sg/ntubus/index.php/main/getCurrentBusStop/"
	req = urllib2.Request(url, data)
	response = urlopen(req)
	raw_html = response.read()
	response.close()

	tree = html.fromstring(raw_html)

	bus_stop_ids = tree.xpath("//bus_stop/@id")

	return bus_stop_ids

def create_bus_stop_object(bus_stop_dict):
	bus_stop = BusStop()
	bus_stop.ID = bus_stop_dict["id"]
	bus_stop.description = unescape(bus_stop_dict["description"])
	bus_stop.code = bus_stop_dict["code"]
	bus_stop.road_name = unescape(bus_stop_dict["road_name"])
	bus_stop.remark = unescape(bus_stop_dict["text_remark"])
	bus_stop.latlong = GeoPoint(float(bus_stop_dict["lat"]), float(bus_stop_dict["lon"]))

	return bus_stop

def create_route_object(route_dict):
	route = Route()
	route.ID = route_dict["id"]
	route.name = unescape(route_dict["name"])
	route.center = GeoPoint(route_dict["centerLonLat"][1], route_dict["centerLonLat"][0])
	zone = []
	for p in route_dict["zone"]:
		# Singapore's zone number and letter is 48N
		zone.append(GeoPoint(*utm.to_latlon(p[0], p[1], 48, 'N')))

	route.zone = zone

	return route

def create_route_bus_stop_object(route, bus_stop):
	rbs = RouteBusStop()
	rbs.bus_stop_parse_id = bus_stop
	rbs.route_parse_id = route
	rbs.bus_stop_id = bus_stop.ID
	rbs.route_id = route.ID

	return rbs

if __name__ == '__main__':

	batcher = ParseBatcher()

	data = get_bus_stop_and_route_data()

	bus_stops = data["bus_stops"]
	routes = data["routes"]

	bus_stops_to_save = []
	routes_to_save = []
	rbs_to_save = []

	for bus_stop in bus_stops:
		bus_stops_to_save.append(create_bus_stop_object(bus_stop))

	all_bus_stops = BusStop.Query.all()
	batcher.batch_delete(all_bus_stops)
	batcher.batch_save(bus_stops_to_save)

	for route in routes:
		routes_to_save.append(create_route_object(route))

	all_routes = Route.Query.all()
	batcher.batch_delete(all_routes)
	batcher.batch_save(routes_to_save)

	for route in routes_to_save:
		bus_stop_ids = get_bus_stops_for_route(int(route.ID))
		result = BusStop.Query.filter(ID__in=bus_stop_ids)
		for bus_stop in result:
			rbs_to_save.append(create_route_bus_stop_object(route, bus_stop))

	all_rbs = RouteBusStop.Query.all()
	batcher.batch_delete(all_rbs)
	batcher.batch_save(rbs_to_save)

	# Singapore's zone number and letter is 48N
	# print utm.to_latlon(352960.8633, 148815.78075, 48, 'N')



