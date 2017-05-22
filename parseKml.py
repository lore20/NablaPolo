import requests
from collections import defaultdict
import xml.etree.ElementTree as ET

map_url = 'http://www.google.com/maps/d/u/0/kml?forcekml=1&mid=1cRlA85rd4ZxRDlSk8KTt5Wop5cM'

LUOGHI_LAYER_NAME = 'Luoghi'
FARMATE_LAYER_NAME = 'Fermate'
CONNESSIONI_LAYER_NAME = 'Connessioni'

tagPrefix = '{http://www.opengis.net/kml/2.2}'
docTag = tagPrefix + 'Document'
folderTag = tagPrefix + 'Folder'
nameTag = tagPrefix + 'name'
placemarkTag = tagPrefix + 'Placemark'
pointTag = tagPrefix + 'Point'
coordinatesTag = tagPrefix + 'coordinates'
polygonTag = tagPrefix + 'Polygon'
outerBoundaryIsTag = tagPrefix + 'outerBoundaryIs'
linearRingTag = tagPrefix + 'LinearRing'
lineStringTag = tagPrefix + 'LineString'

def point_inside_polygon(x,y,poly):
    n = len(poly)
    inside =False
    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xinters = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x,p1y = p2x,p2y
    return inside

def mean(numbers):
    return float(sum(numbers)) / max(len(numbers), 1)

def getPolygonCentroid(poly):
    return mean([x[0] for x in poly]),mean([x[1] for x in poly])

def getLuogoConainingPoint(point, luoghi):
    for n, v in luoghi.iteritems():
        polycoordinateList = v['poly']
        if point_inside_polygon(point[0], point[1], polycoordinateList):
            return n
    return None

def parseMap():
    r = requests.get(map_url)
    kml_xml = r.content
    root = ET.fromstring(kml_xml)
    #root = ET.parse('data/PickMeUp.kml') #getroot()
    document = root.find(docTag)
    folders = document.findall(folderTag)
    nameFolders = {}
    for fold in folders:
        name = fold.find(nameTag).text  # Fermate, LuoghiFlags, Luoghi, Lines
        nameFolders[name] = fold

    # LUOGHI
    # IMPORTANT - LUOGHI CANNOT SHARE THE SAME PREFIX
    luoghi = {}  # {name: {'loc': (<lat>,<lon>), 'fermate': [fermata1, fermata2, ...]}}
    luoghi_folder = nameFolders[LUOGHI_LAYER_NAME]
    placemarks = luoghi_folder.findall(placemarkTag)
    for p in placemarks:
        name = p.find(nameTag).text.strip() # luogo name
        name = name.encode('utf-8')
        polygon = p.find(polygonTag)
        outerBoundaryIs = polygon.find(outerBoundaryIsTag)
        linearRing = outerBoundaryIs.find(linearRingTag)
        coordinatesStringList = [x.strip() for x in linearRing.find(coordinatesTag).text.strip().split('\n')]
        coordinateList = []
        for coordinatesString in coordinatesStringList:
            lon, lat = [float(x) for x in coordinatesString.split(',')[:2]]
            coordinateList.append((lat, lon))
        centroid_lat, centroid_lon = getPolygonCentroid(coordinateList)
        luoghi[name] = {
            'loc': (centroid_lat, centroid_lon), # centroid
            'poly': coordinateList,
            'fermate': []
        }

    # FERMATE
    fermate = {} # {luogo_name: {'name': <fermata_name>, 'loc': (<lat>,<lon>), 'ref': refLuogo}}
    fermate_folder = nameFolders[FARMATE_LAYER_NAME]
    placemarks = fermate_folder.findall(placemarkTag)
    for p in placemarks:
        name = p.find(nameTag).text.strip() # fermata name
        name = name.encode('utf-8')
        point = p.find(pointTag)
        coordinatesString = point.find(coordinatesTag).text.strip().split(',')
        lon, lat = [float(x) for x in coordinatesString[:2]]
        #point = Point(lat, lon)
        luogo = getLuogoConainingPoint((lat, lon), luoghi)
        luogo_name = '{} ({})'.format(luogo, name)
        fermate[luogo_name] = {'name': name, 'loc': (lat, lon), 'ref': luogo}
        luoghi[luogo]['fermate'].append(name)


    # Lines
    connections = defaultdict(set)  # { luogo1: set(luogo2, luogo3), luogo2: set(luogo1, luogo3), ... }
    connessioni_folder = nameFolders[CONNESSIONI_LAYER_NAME]
    placemarks = connessioni_folder.findall(placemarkTag)
    for p in placemarks:
        lineString = p.find(lineStringTag)
        coordinatesStringList = [x.strip() for x in lineString.find(coordinatesTag).text.strip().split('\n')]
        coordinateList = []
        for coordinatesString in coordinatesStringList:
            lon, lat = [float(x) for x in coordinatesString.split(',')[:2]]
            coordinateList.append((lat, lon))
        point1 = coordinateList[0] # Point(coordinateList[0])
        point2 = coordinateList[1] # Point(coordinateList[1])
        luogo1 = getLuogoConainingPoint(point1, luoghi)
        luogo2 = getLuogoConainingPoint(point2, luoghi)
        connections[luogo1].add(luogo2)
        connections[luogo2].add(luogo1)

    return luoghi, fermate, connections


def checkMap():
    luoghi, fermate, connections = parseMap()
    checkLuoghi = set(luoghi.keys()) == set(connections.keys())
    checkFermate = all(fv['ref'] is not None for fv in fermate.values())
    checkConnections = all(len(s) > 0 for s in connections.values())
    print "Luoghi: {} check: {}".format(len(luoghi), checkLuoghi)
    print "Fermate: {} check: {}".format(len(fermate), checkFermate)
    print "Connections: {} check: {}".format(len(connections), checkConnections)