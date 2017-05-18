import requests
from collections import defaultdict
import xml.etree.ElementTree as ET
#from shapely.geometry import Point
#from shapely.geometry.polygon import Polygon

DEBUG = False

map_url = 'http://www.google.com/maps/d/u/0/kml?forcekml=1&mid=1cRlA85rd4ZxRDlSk8KTt5Wop5cM'

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

def getAreaNameOfPoint(point, areas):
    for name, polygon in areas.iteritems():
        #if polygon.contains(point):
        #    return name
        if point_inside_polygon(point[0], point[1], polygon):
            return name
    if DEBUG:
        print "Eror in finding area for point {}".format(list(point.coords)[0])
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
        name = fold.find(nameTag).text  # Fermate, Luoghi, Areas, Lines
        nameFolders[name] = fold

    # Luoghi
    luoghi = {}  # {name: (<lat>,<lon>)}
    #  using centroid of areas instead of placemarks
    '''
    luoghi_folder = nameFolders['Luoghi']
    placemarks = luoghi_folder.findall(placemarkTag)
    for p in placemarks:
        name = p.find(nameTag).text.strip() # luogo name (= area name)
        point = p.find(pointTag)
        coordinatesString = point.find(coordinatesTag).text.strip().split(',')
        lon, lat = [float(x) for x in coordinatesString[:2]]
    '''

    # Areas
    areas = {}  # {name: <polygon>}
    areas_folder = nameFolders['Areas']
    placemarks = areas_folder.findall(placemarkTag)
    for p in placemarks:
        name = p.find(nameTag).text.strip() # area name
        name = name.encode('utf-8')
        polygon = p.find(polygonTag)
        outerBoundaryIs = polygon.find(outerBoundaryIsTag)
        linearRing = outerBoundaryIs.find(linearRingTag)
        coordinatesStringList = [x.strip() for x in linearRing.find(coordinatesTag).text.strip().split('\n')]
        coordinateList = []
        for coordinatesString in coordinatesStringList:
            lon, lat = [float(x) for x in coordinatesString.split(',')[:2]]
            coordinateList.append((lat, lon))
        #polygon = Polygon(coordinateList)
        #areas[name] = polygon
        areas[name] = coordinateList
        #centroid_lat, centroid_lon = list(polygon.centroid.coords)[0]
        centroid_lat, centroid_lon = getPolygonCentroid(coordinateList)
        luoghi[name] = (centroid_lat, centroid_lon)

    # Fermate
    fermate = {} # {name: {'loc': (<lat>,<lon>), 'ref': refArea}}
    fermate_folder = nameFolders['Fermate']
    placemarks = fermate_folder.findall(placemarkTag)
    for p in placemarks:
        name = p.find(nameTag).text.strip() # fermata name
        name = name.encode('utf-8')
        point = p.find(pointTag)
        coordinatesString = point.find(coordinatesTag).text.strip().split(',')
        lon, lat = [float(x) for x in coordinatesString[:2]]
        #point = Point(lat, lon)
        areaName = getAreaNameOfPoint((lat,lon), areas)
        fermate[name] = {'loc': (lat, lon), 'ref': areaName}


    # Lines
    connections = defaultdict(set)  # { area1: set(area2, area3), area2: set(area1, area3), ... }
    lines_folder = nameFolders['Lines']
    placemarks = lines_folder.findall(placemarkTag)
    for p in placemarks:
        lineString = p.find(lineStringTag)
        coordinatesStringList = [x.strip() for x in lineString.find(coordinatesTag).text.strip().split('\n')]
        coordinateList = []
        for coordinatesString in coordinatesStringList:
            lon, lat = [float(x) for x in coordinatesString.split(',')[:2]]
            coordinateList.append((lat, lon))
        point1 = coordinateList[0] # Point(coordinateList[0])
        point2 = coordinateList[1] # Point(coordinateList[1])
        area1 = getAreaNameOfPoint(point1, areas)
        area2 = getAreaNameOfPoint(point2, areas)
        connections[area1].add(area2)
        connections[area2].add(area1)

    if DEBUG:
        checkLuoghi = set(luoghi.keys()) == set(connections.keys())
        checkFermate = all(fv['ref'] is not None for fv in fermate.values())
        checkConnections = all(len(s) > 0 for s in connections.values())
        print "Luoghi: {} check: {}".format(len(luoghi), checkLuoghi)
        print "Fermate: {} check: {}".format(len(fermate), checkFermate)
        print "Connections: {} check: {}".format(len(connections), checkConnections)

    return luoghi, fermate, connections