# coding=utf-8

import logging
import utility
import key
import geoUtils
import parseKml

# LUOGHI -> {name: {'loc': (<lat>,<lon>), 'poly': <list coordinate>, 'fermate': <list fermate names>}}
# FERMATE -> {name: (<lat>,<lon>)}
# CONNECTIONS -> { luogo1: set(luogo2, luogo3), luogo2: set(luogo1, luogo3), ... }

LUOGHI, FERMATE, CONNECTIONS = parseKml.parseMap()
GPS_LOCATIONS = [v['loc'] for v in FERMATE.values()]
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
                   ''.join(["&markers=color:blue|{0},{1}".format(f[0],f[1]) for f in GPS_LOCATIONS])


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

def getDistanceBetweenLuoghi(A, B):
    import geoUtils
    locA = LUOGHI[A]['loc']
    locB = LUOGHI[B]['loc']
    return geoUtils.distance(locA, locB)

def getPathDistance(path):
    return sum([getDistanceBetweenLuoghi(path[i], path[i+1]) for i in range(len(path)-1)])

'''
def get_shortest_paths(start, end, dst=0, path_so_far=None, tolerance=5):
    #print '--------------------'
    #print 'start: {}, end={}, old_path={}'.format(start, end, old_path)
    if path_so_far is None:
        path_so_far = []
    else:
        dst += getDistanceBetweenLuoghi(path_so_far[-1], start)
    #print 'dst = {}'.format(dst)
    path = path_so_far + [start]
    if start == end:
        return [path], [dst]
    if not CONNECTIONS.has_key(start):
        return None, None
    shortest_paths = []
    shortest_dsts = []
    for node in CONNECTIONS[start]:
        if node not in path:
            #print 'node: {}, end={}, path={}'.format(node, end, path)
            new_paths, new_dsts = get_shortest_paths(node, end, dst, path)
            if new_dsts:
                if len(shortest_dsts)==0  or new_dsts[0] <= min(shortest_dsts)+tolerance:
                    shortest_paths.extend(new_paths)
                    shortest_dsts.extend(new_dsts)
    return shortest_paths, shortest_dsts
'''


def find_all_paths(start, end, path=None):
    path = path + [start] if path else [start]
    if start == end:
        return [path]
    paths = []
    for node in CONNECTIONS[start]:
        if node not in path:
            extended_paths = find_all_paths(node, end, path)
            for p in extended_paths:
                paths.append(p)
    return paths

def get_shortest_paths_distance(start, end, tolerance=5):
    all_paths = find_all_paths(start, end)
    all_dsts = [getPathDistance(p) for p in all_paths]
    min_dst_plus_tolerance = min(all_dsts) + tolerance
    return ([ (p,d) for p,d in zip(all_paths, all_dsts) if d <= min_dst_plus_tolerance])


def get_intermediate_stops(start, end):
    shortes_paths = [pd[0] for pd in get_shortest_paths_distance(start, end)]
    intermediate_stops = set()
    for p in shortes_paths:
        intermediate_stops.update(p)
    intermediate_stops.remove(start)
    intermediate_stops.remove(end)
    return intermediate_stops

def test_intermediate_stops(start=None, end=None):
    import random
    LUOGHI_NAMES = LUOGHI.keys()
    if start is None:
        start = random.choice(LUOGHI_NAMES)
    while end is None or end == start:
        end = random.choice(LUOGHI_NAMES)
    shortest_paths_dsts = get_shortest_paths_distance(start, end)
    print '\n'.join(['{}: {}'.format(x, y) for x,y in shortest_paths_dsts])
    stops = get_intermediate_stops(start, end)
    stops_str = "PASSA DA: {}".format(', '.join(stops)) if stops else 'DIRETTO'
    print '{} -> {}\n{}'.format(start, end, stops_str)