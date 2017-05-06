# coding=utf-8

import logging
import utility
import jsonUtil
import key
import geoUtils

FERMATE_ITINERARY = jsonUtil.json_load_byteified(open("data/fermate_itinerary.json"))
FERMATE_DICT = FERMATE_ITINERARY['Fermate']
ITINERARI = FERMATE_ITINERARY['Itinerari']
LUOGHI = FERMATE_ITINERARY['Luoghi']
GPS_LOCATIONS = [v['loc'] for v in FERMATE_DICT.values()]
FERMATE_NAMES = FERMATE_DICT.keys()
SORTED_LUOGHI = sorted(list(set(utility.flatten([v['ref'] for v in FERMATE_DICT.values()]))))
SORTED_FERMATE_IN_LOCATION = lambda l: sorted([n for n,v in FERMATE_DICT.iteritems() if l in v['ref']])

BASE_MAP_IMG_URL = "http://maps.googleapis.com/maps/api/staticmap?" + \
                   "&size=400x400" + "&maptype=roadmap" + \
                   "&key=" + key.GOOGLE_API_KEY

FULL_MAP_IMG_URL = BASE_MAP_IMG_URL + \
                   ''.join(["&markers=color:blue|{0},{1}".format(f[0],f[1]) for f in GPS_LOCATIONS])


def getDistanceBetweenLuoghi(A, B):
    import geoUtils
    locA = LUOGHI[A]['loc']
    locB = LUOGHI[B]['loc']
    return geoUtils.distance(locA, locB)


def get_shortest_paths(start, end, dst=0, old_path=None, tolerance=5):
    #print '--------------------'
    #print 'start: {}, end={}, old_path={}'.format(start, end, old_path)
    if old_path is None:
        old_path = []
    else:
        dst += getDistanceBetweenLuoghi(old_path[-1], start)
    #print 'dst = {}'.format(dst)
    path = old_path + [start]
    if start == end:
        return [path], [dst]
    if not ITINERARI.has_key(start):
        return None, None
    shortest_paths = []
    shortest_dsts = []
    for node in ITINERARI[start]:
        if node not in path:
            #print 'node: {}, end={}, path={}'.format(node, end, path)
            new_paths, new_dsts = get_shortest_paths(node, end, dst, path)
            if new_dsts:
                if len(shortest_dsts)==0  or new_dsts[0] <= shortest_dsts[0]+tolerance:
                    shortest_paths.extend(new_paths)
                    shortest_dsts.extend(new_dsts)
    return shortest_paths, shortest_dsts

def get_intermediate_stops(start, end):
    shortest_paths, shortest_dsts = get_shortest_paths(start, end)
    intermedie = set()
    if shortest_paths:
        for sp in shortest_paths:
            intermedie.update(sp)
        #logging.debug("intermediate before removing start and end: {}".format(intermedie))
        intermedie.remove(start)
        intermedie.remove(end)
    return list(intermedie)
