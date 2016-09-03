import numpy as np
import datetime
import geopy

stops = np.genfromtxt('ttdata/stops.txt', delimiter=',', dtype=None, names=True)
trips = np.genfromtxt('ttdata/merged.txt', delimiter=',', dtype=None, names=True)

def dow(date):
    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    day_number = date.weekday()
    return days[day_number]


def prettyprint(array):
    """Take a pandas dataframe in input and return a string containing one row per line"""

    temp = []
    for row in array:
        temp.append(', '.join(list(row)))
    response = '\n'.join(temp)
    if not temp:
        response = "No, mi spiace, ma non ci sono bus adesso..."
    return response


def find_nearest_vector(array, value):
  idx = np.array([np.linalg.norm(x-value) for x in array]).argmin()
  return idx


def getstop(location):
    """Take a location in input and return the name of the nearest
    bus stop the ids of one or two (one per direction, if available) stop_id
    """
    pt = location.latitude, location.longitude
    pt = np.asarray(pt)
#    pt = location
    points = np.asarray(zip(stops['stop_lat'],stops['stop_lon']))
    # find nearest stop given a tree and a point (pt)
    nn_idx = find_nearest_vector(points, pt)
    stop_name = stops['stop_name'][nn_idx]
    stop_id = stops['stop_id'][nn_idx]
    stop_code = stops['stop_code'][nn_idx]
    # check if there is the bus stop for opposite direction
    stop_id2 = None
    if stop_code[-1] == 'x':
        try:
            stop_code2 = stop_code[:-1] + 'z'
            stop_id2 = stops['stop_id'][np.where(stops['stop_code'] == stop_code2)[0][0]]
        except IndexError:
            return stop_name, stop_id
    elif stop_code[-1] == 'z':
        try:
            stop_code2 = stop_code[:-1] + 'x'
            stop_id2 = stops['stop_id'][np.where(stops['stop_code'] == stop_code2)[0][0]]
        except IndexError:
            return stop_name, stop_id
    return stop_name, stop_id, stop_id2


def gettrip(location):
    """Take in input a location and return a list containing info about the
    6 next buses (3 per direction). Info means: time,route short name and route headsign"""
    stop_id = getstop(location)[1]
    time = datetime.datetime.now()
    now = time.strftime('%H:%M:%S')

    nextbuses = trips[(trips['stop_id'] == stop_id) & (trips['arrival_time'] >= now) & (trips[dow(time)] != 0)][0:3]
    try:
        stop_id2 = getstop(location)[2]
        nextbuses2 = trips[(trips['stop_id'] == stop_id2) & (trips['arrival_time'] >= now) & (trips[dow(time)] != 0)][0:3]
        buses = np.concatenate((nextbuses, nextbuses2))
        response = prettyprint(buses[['arrival_time','route_short_name','trip_headsign']])
        return response
    except IndexError:
        response = prettyprint(nextbuses[['arrival_time','route_short_name','trip_headsign']])
        return response

def getBusTimes():
    point = geopy.point.Point(46.0678403, 11.1188594) #S.M.MAGGIORE
    return gettrip(point)