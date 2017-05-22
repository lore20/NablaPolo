# coding=utf-8

import logging
import utility
import key
import geoUtils
import parseKml

# LUOGHI -> {name: {'loc': (<lat>,<lon>), 'fermate': [fermata1, fermata2, ...]}, 'polygon': <list polygon coords>}
# FERMATE -> {name: {'loc': (<lat>,<lon>), 'ref': refLuogo}}

LUOGHI, FERMATE = parseKml.parseMap()
GPS_FERMATE_LOC = [v['loc'] for v in FERMATE.values()]
FERMATE_NAMES = FERMATE.keys()
SORTED_LUOGHI = sorted(LUOGHI.keys())
SORTED_FERMATE_IN_LUOGO = lambda l: sorted([n for n, v in FERMATE.iteritems() if l in v['ref']])
SORTED_LUOGHI_WITH_FERMATA_IF_SINGLE = sorted(
    [l if len(v['fermate'])>1 else '{} ({})'.format(l, v['fermate'][0]) for l,v in LUOGHI.iteritems() ]
)


BASE_MAP_IMG_URL = "http://maps.googleapis.com/maps/api/staticmap?" + \
                   "&size=400x400" + "&maptype=roadmap" + \
                   "&key=" + key.GOOGLE_API_KEY

FULL_MAP_IMG_URL = BASE_MAP_IMG_URL + \
                   ''.join(["&markers=color:blue|{0},{1}".format(f[0],f[1]) for f in GPS_FERMATE_LOC])


def format_distance(dst):
    if (dst>=10):
        return str(round(dst, 0)) + " Km"
    if (dst>=1):
        return str(round(dst, 1)) + " Km"
    return str(int(dst*1000)) + " m"

def getFermateNearPosition(lat, lon, radius, max_threshold_ratio):
    import params
    result = {}
    centralPoint = (lat, lon)
    min_distance = None
    for f,v in FERMATE.iteritems():
        refPoint = v['loc']
        d = geoUtils.distance(refPoint, centralPoint)
        if d < radius:
            if min_distance is None or d < min_distance:
                min_distance = d
            result[f] = {
                'ref': v['ref'],
                'loc': refPoint,
                'dist': d
            }
    min_distance = max(min_distance, 1) # if it's less than 1 km use 1 km as a min distance
    result = {k:v for k,v in result.items() if v['dist'] <= max_threshold_ratio*min_distance}
    max_results = params.MAX_FERMATE_NEAR_LOCATION
    result_sorted = sorted(result.items(), key=lambda k: k[1]['dist'])[:max_results]
    result = dict(result_sorted)
    return result

def getFermateNearPositionImgUrl(lat, lon, radius = 10, max_threshold_ratio=2):
    fermate = getFermateNearPosition(lat, lon, radius, max_threshold_ratio)
    if fermate:
        fermate_name_sorted = sorted(fermate.items(), key=lambda k: k[1]['dist'])
        img_url = BASE_MAP_IMG_URL + \
                  "&markers=color:red|{},{}".format(lat, lon) + \
                  ''.join(["&markers=color:blue|label:{}|{},{}".format(num, v['loc'][0], v['loc'][1])
                           for num, v in enumerate(fermate.values(), 1)])
        text = 'Ho trovato *1 fermata* ' if len(fermate)==1 else 'Ho trovato *{} fermate* '.format(len(fermate))
        text += "in prossimità dalla posizione inserita:\n"
        text += '\n'.join('{}. {} - {} ({})'.format(num, v['ref'], f, format_distance(v['dist']))
                          for num, (f,v) in enumerate(fermate_name_sorted,1))
    else:
        img_url = None
        text = 'Nessuna fermata trovata nel raggio di {} km dalla posizione inserita.'.format(radius)
    return img_url, text


def getIntermediateLuoghiOrder(path):
    intermediates = []
    for lat, lon in path:
        for l, v in LUOGHI.items():
            if l in intermediates:
                continue
            polygon = v['polygon']
            if geoUtils.point_inside_polygon(lat, lon, polygon):
                intermediates.append(l)
                break
    return intermediates

def getIntermediateFermateOrder(path):
    import params
    intermediates = []
    for point in path:
        for f, v in FERMATE.items():
            if f in intermediates:
                continue
            loc = v['loc']
            dst = geoUtils.distance(point, loc)
            if dst < params.PATH_FERMATA_PROXIMITY_THRESHOLD:
                intermediates.append(f)
                break
    return intermediates


def test_intermediate_stops(start=None, end=None):
    from key import GOOGLE_API_KEY
    import polyline
    import requests
    import random

    if start is None:
        start = random.choice(FERMATE.keys())
    while end is None or end == start:
        end = random.choice(FERMATE.keys())

    print('{} --> {}'.format(start, end))

    origin_str = ','.join(str(x) for x in FERMATE[start]['loc'])
    destin_str = ','.join(str(x) for x in FERMATE[end]['loc'])
    api_url = 'https://maps.googleapis.com/maps/api/directions/json?' \
              'alternatives=true&units=metric&key={}'.format(GOOGLE_API_KEY) #avoid=tolls,highways
    api_url += '&origin={}&destination={}'.format(origin_str, destin_str)
    result = requests.get(api_url).json()
    routes = result['routes']
    print('Found {} routes.'.format(len(routes)))

    for n, r in enumerate(routes,1):
        poly_str = r['overview_polyline']['points']
        path = polyline.decode(poly_str)
        root_intermediates_luoghi = getIntermediateLuoghiOrder(path)
        root_intermediates_fermate = getIntermediateFermateOrder(path)
        print 'Percorso {} - Luoghi intermedi: {}'.format(n, ', '.join(root_intermediates_luoghi))
        print 'Percorso {} - Fermate intermedie: {}'.format(n, ', '.join(root_intermediates_fermate))


