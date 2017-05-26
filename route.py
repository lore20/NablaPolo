# coding=utf-8

from key import GOOGLE_API_KEY

# ZONE -> {zona: {'loc': (<lat>,<lon>), 'stops': [stop1, stop2, ...]}, 'polygon': <list polygon coords>}
# FERMATE -> {zona_stop: {'zona': refZona, 'stop': <fermata_name>, 'loc': (<lat>,<lon>)}}

import parseKml

ZONE, FERMATE = parseKml.parseMap()
GPS_FERMATE_LOC = [v['loc'] for v in FERMATE.values()]

SORTED_ZONE = sorted(ZONE.keys())
SORTED_FERMATE_IN_ZONA = lambda l: sorted([x for x in ZONE[l]['stops']])
SORTED_ZONE_WITH_STOP_IF_SINGLE = sorted(
    [l if len(v['stops'])>1 else '{} ({})'.format(l, v['stops'][0]) for l,v in ZONE.iteritems() ]
)

PERCORSO_SEPARATOR = ' → '

def encodeFermataKey(zona, fermata):
    return '{} ({})'.format(zona, fermata)

def decodeFermataKey(fermata_key):
    assert fermata_key.count('(')==1
    zona, fermata = fermata_key[:-1].split(' (')
    assert zona in ZONE
    assert fermata in SORTED_FERMATE_IN_ZONA(zona)
    return zona, fermata

def encodeFermateKeysFromQuartet(start_zona, start_fermata, end_zona, end_fermata):
    start_fermata_key = encodeFermataKey(start_zona, start_fermata)
    end_fermata_key = encodeFermataKey(end_zona, end_fermata)
    return start_fermata_key, end_fermata_key

def encodePercorsoFromQuartet(start_zona, start_fermata, end_zona, end_fermata):
    start_fermata_key, end_fermata_key = encodeFermateKeysFromQuartet(
        start_zona, start_fermata, end_zona, end_fermata)
    return encodePercorso(start_fermata_key, end_fermata_key)

def decodePercorsoToQuartet(percorso_key):
    start_fermata_key, end_fermata_key = decodePercorso(percorso_key)
    start_zona, start_stop = decodeFermataKey(start_fermata_key)
    end_zone, end_stop = decodeFermataKey(end_fermata_key)
    return start_zona, start_stop, end_zone, end_stop

def encodePercorso(start_fermata_key, end_fermata_key):
    assert start_fermata_key in FERMATE
    assert end_fermata_key in FERMATE
    return '{}{}{}'.format(start_fermata_key, PERCORSO_SEPARATOR, end_fermata_key)

def decodePercorso(percorso_key):
    start_fermata_key, end_fermata_key = percorso_key.split(PERCORSO_SEPARATOR)
    return start_fermata_key, end_fermata_key

def getReversePath(start, start_fermata, end, end_fermata):
    return end, end_fermata, start, start_fermata

def format_distance(dst):
    if (dst>=10):
        return str(round(dst, 0)) + " Km"
    if (dst>=1):
        return str(round(dst, 1)) + " Km"
    return str(int(dst*1000)) + " m"

def getFermateNearPosition(lat, lon, radius, max_threshold_ratio):
    import geoUtils
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
                   "&key=" + GOOGLE_API_KEY

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

def getPercorsiPasseggeriCompatibili(percorso):
    import itertools
    start_fermata_key, end_fermata_key = decodePercorso(percorso)
    intermediates_fermate_routes = getIntermediateRouteFermate(start_fermata_key, end_fermata_key)
    percorsi_compatibili = set()
    fermate_interemedie_routes = []
    if intermediates_fermate_routes:
        for fermate_percorso in intermediates_fermate_routes:
            fermate_interemedie_routes.append(fermate_percorso)
            fermate_pairs = tuple(itertools.combinations(fermate_percorso, 2))
            for pair in fermate_pairs:
                percorso = encodePercorso(*pair)
                percorsi_compatibili.add(percorso)
    return tuple(percorsi_compatibili), tuple(fermate_interemedie_routes)

def getIntermediateFermateOrderFromPath(path):
    import geoUtils
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

def getIntermediateRouteFermate(start_fermata_key, end_fermata_key):
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
    intermediates_fermate_routes = []
    for r in routes:
        poly_str = r['overview_polyline']['points']
        path = polyline.decode(poly_str)
        fermate = getIntermediateFermateOrderFromPath(path)
        intermediates_fermate_routes.append(fermate)
    return intermediates_fermate_routes

def test_intermediate_stops(start=None, end=None):
    import random

    if start is None:
        start = random.choice(FERMATE.keys())
    while end is None or end == start:
        end = random.choice(FERMATE.keys())

    print('{} --> {}'.format(start, end))
    print('{} --> {}'.format(FERMATE[start]['loc'],FERMATE[end]['loc']))
    intermediates_fermate_routes = getIntermediateRouteFermate(start, end)

    print('Found {} routes.'.format(len(intermediates_fermate_routes)))

    for i, fermate_percorso in enumerate(intermediates_fermate_routes):
        print 'Percorso {} - Fermate intermedie: {}'.format(i+1, ', '.join(fermate_percorso))


