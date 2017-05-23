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

SORTED_LUOGHI = sorted(LUOGHI.keys())
SORTED_FERMATE_IN_LUOGO = lambda l: sorted([x for x in LUOGHI[l]['fermate']])
SORTED_LUOGHI_WITH_FERMATA_IF_SINGLE = sorted(
    [l if len(v['fermate'])>1 else '{} ({})'.format(l, v['fermate'][0]) for l,v in LUOGHI.iteritems() ]
)

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
                'loc': refPoint,
                'dist': d
            }
    min_distance = max(min_distance, 1) # if it's less than 1 km use 1 km as a min distance
    result = {k:v for k,v in result.items() if v['dist'] <= max_threshold_ratio*min_distance}
    max_results = params.MAX_FERMATE_NEAR_LOCATION
    result_sorted = sorted(result.items(), key=lambda k: k[1]['dist'])[:max_results]
    result = dict(result_sorted)
    return result

BASE_MAP_IMG_URL = "http://maps.googleapis.com/maps/api/staticmap?" + \
                   "&size=400x400" + "&maptype=roadmap" + \
                   "&key=" + key.GOOGLE_API_KEY

def getFermateNearPositionImgUrl(lat, lon, radius = 10, max_threshold_ratio=2):
    fermate = getFermateNearPosition(lat, lon, radius, max_threshold_ratio)
    if fermate:
        fermate_name_sorted = sorted(fermate.items(), key=lambda k: k[1]['dist'])
        img_url = BASE_MAP_IMG_URL + \
                  "&markers=color:red|{},{}".format(lat, lon) + \
                  ''.join(["&markers=color:blue|label:{}|{},{}".format(num, v['loc'][0], v['loc'][1])
                           for num, (f,v) in enumerate(fermate_name_sorted, 1)])
        text = 'Ho trovato *1 fermata* ' if len(fermate)==1 else 'Ho trovato *{} fermate* '.format(len(fermate))
        text += "in prossimità dalla posizione inserita:\n"
        text += '\n'.join('{}. {}: {}'.format(num, f, format_distance(v['dist']))
                          for num, (f,v) in enumerate(fermate_name_sorted,1))
    else:
        img_url = None
        text = 'Nessuna fermata trovata nel raggio di {} km dalla posizione inserita.'.format(radius)
    return img_url, text


def getIntermediateLuoghiOrderFromPath(path):
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

def getIntermediateFermateOrderFromPath(path):
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

def getIntermediateLuoghi(start_place, start_fermata, end_place, end_fermata):
    import parseKml
    start_fermata_key = parseKml.getFermataUniqueKey(start_place, start_fermata)
    end_fermata_key = parseKml.getFermataUniqueKey(end_place, end_fermata)
    intermediates_luoghi_routes, intermediates_fermate_routes = \
        getIntermediateRoutePaths(start_fermata_key, end_fermata_key)
    intermediates_luoghi = set()
    for ifr in intermediates_luoghi_routes:
        intermediates_luoghi.update(ifr)
    return intermediates_luoghi

def getIntermediateRoutePaths(start_fermata_key, end_fermata_key):
    from key import GOOGLE_API_KEY
    import polyline
    import requests
    origin_str = ','.join(str(x) for x in FERMATE[start_fermata_key]['loc'])
    destin_str = ','.join(str(x) for x in FERMATE[end_fermata_key]['loc'])
    api_url = 'https://maps.googleapis.com/maps/api/directions/json?' \
              'alternatives=true&units=metric&key={}'.format(GOOGLE_API_KEY)  # avoid=tolls,highways
    api_url += '&origin={}&destination={}'.format(origin_str, destin_str)
    result = requests.get(api_url).json()
    routes = result['routes']
    intermediates_luoghi_routes = []
    intermediates_fermate_routes = []
    for r in routes:
        poly_str = r['overview_polyline']['points']
        path = polyline.decode(poly_str)
        fermate = getIntermediateFermateOrderFromPath(path)
        luoghi = []
        for f in fermate:
            l = FERMATE[f]['ref']
            if l not in luoghi:
                luoghi.append(l)
        intermediates_luoghi_routes.append(luoghi)
        intermediates_fermate_routes.append(fermate)
    return intermediates_luoghi_routes, intermediates_fermate_routes

def test_intermediate_stops(start=None, end=None):
    import random

    if start is None:
        start = random.choice(FERMATE.keys())
    while end is None or end == start:
        end = random.choice(FERMATE.keys())

    print('{} --> {}'.format(start, end))
    print('{} --> {}'.format(FERMATE[start]['loc'],FERMATE[end]['loc']))
    intermediates_luoghi_routes, intermediates_fermate_routes = getIntermediateRoutePaths(start, end)

    print('Found {} routes.'.format(len(intermediates_luoghi_routes)))

    for i in range(len(intermediates_luoghi_routes)):
        root_intermediates_luoghi = intermediates_luoghi_routes[i]
        root_intermediates_fermate = intermediates_fermate_routes[i]
        print 'Percorso {} - Luoghi intermedi: {}'.format(i+1, ', '.join(root_intermediates_luoghi))
        print 'Percorso {} - Fermate intermedie: {}'.format(i+1, ', '.join(root_intermediates_fermate))


