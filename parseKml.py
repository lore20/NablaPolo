import requests
from collections import defaultdict
import xml.etree.ElementTree as ET
import percorsi

map_url = 'http://www.google.com/maps/d/u/0/kml?forcekml=1&mid=1cRlA85rd4ZxRDlSk8KTt5Wop5cM'

LUOGHI_LAYER_NAME = 'Luoghi'
FARMATE_LAYER_NAME = 'Fermate'

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

def mean(numbers):
    return float(sum(numbers)) / max(len(numbers), 1)

def getPolygonCentroid(poly):
    return mean([x[0] for x in poly]),mean([x[1] for x in poly])

def getLuogoConainingPoint(point, luoghi):
    from geoUtils import point_inside_polygon
    for n, v in luoghi.iteritems():
        polycoordinateList = v['polygon']
        if point_inside_polygon(point[0], point[1], polycoordinateList):
            return n
    return None

def getFermataUniqueKey(luogo, fermata):
    return '{} ({})'.format(luogo, fermata)

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
    luoghi = {}  # {name: {'loc': (<lat>,<lon>), 'fermate': [fermata1, fermata2, ...]}, 'polygon': <list polygon coords>}
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
            'polygon': coordinateList,
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
        luogo_name = getFermataUniqueKey(luogo, name)
        fermate[luogo_name] = {'name': name, 'loc': (lat, lon), 'ref': luogo}
        luoghi[luogo]['fermate'].append(name)


    return luoghi, fermate


def checkMap():
    luoghi, fermate = parseMap()
    checkLuoghi = all(len(v['fermate'])>0 for v in luoghi.values())
    checkFermate = all(fv['ref'] is not None for fv in fermate.values())
    print "Luoghi: {} check: {}".format(len(luoghi), checkLuoghi)
    print "Fermate: {} check: {}".format(len(fermate), checkFermate)
