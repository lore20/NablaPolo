import numpy as np
#import scipy.spatial as spatial
import kdtree
import pandas as pd
import time
import datetime
import geopy

#from http://www.ttesercizio.it/TTEOpenData/
# google_transit_extraurbano.zip (csv)

stops = pd.read_csv("ttdata/stops.txt")
stop_times = pd.read_csv("ttdata/stop_times.txt")
routes = pd.read_csv("ttdata/routes.txt")
trips = pd.read_csv("ttdata/trips.txt")
calendar = pd.read_csv("ttdata/calendar.txt",names=['service_id','monday','tuesday','wednesday','thursday','friday','saturday','sunday','start_date','end_date'],header=0)

points = stops[['stop_lat','stop_lon']].values
print(points)
tree = kdtree.create(points)
#nn = points[spatial.KDTree(points).query(pt)[1]] #find nearest stop given a tree and a point (pt)

def dow(date):
    days=["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    dayNumber=date.weekday()
    return days[dayNumber]

def prettyprint(df):
    """Take a pandas dataframe in input and return a string containing one row per line"""
    
    temp = []
    for i,row in df.iterrows():
        temp.append(str(row.values))
    response = '\n'.join(temp)
    if not temp:
        response = "No, mi spiace, ma non ci sono bus adesso..."
    return response

def getstop(location):
    """Take a location in input and return the name of the nearest
    bus stop the ids of one or two (one per direction, if available) stop_id
    """
    pt = location.latitude,location.longitude
    pt = np.asarray(pt)
    #points = stops[['stop_lat','stop_lon']].values
    #nn = points[spatial.KDTree(points).query(pt)[1]] #find nearest stop given a tree and a point (pt)
    nn = tree.search_nn(pt)
    stop_name = stops['stop_name'][(stops['stop_lat'] ==nn[0]) & (stops['stop_lon'] ==nn[1])].iloc[0]
    stop_id = stops['stop_id'][stops['stop_name'] == stop_name].iloc[0]
    stop_code = stops['stop_code'][stops['stop_id'] == stop_id].iloc[0]
    stop_id2 = None #check if there is the bus stop for opposite direction
    if stop_code[-1] == 'x':
        try:
            stop_code2 = stop_code
            temp = list(stop_code2)
            temp[-1] = 'z'
            stop_code2 = ''.join(temp)
            stop_id2 = stops['stop_id'][stops['stop_code'] == stop_code2].iloc[0]
        except (KeyError,IndexError):
            return stop_name,stop_id
    elif stop_code[-1] == 'z':
        try:
            stop_code2 = stop_code
            temp = list(stop_code2)
            temp[-1] = 'x'
            stop_code2 = ''.join(temp)
            stop_id2 = stops['stop_id'][stops['stop_code'] == stop_code2].iloc[0]
        except (KeyError,IndexError):
            return stop_name,stop_id
    return stop_name,stop_id,stop_id2

def gettrip(location):
    """Take in input a location and return a list containing info about the 
    6 next buses (3 per direction). Info means: time,route short name and route headsign"""
    stop_id = getstop(location)[1]
    time = datetime.datetime.now()
    now = time.strftime('%H:%M:%S') 
    a = pd.merge(stop_times,trips,on=['trip_id']) #merge the dfs in order to simplify extraction process
    b = pd.merge(a,calendar,on=['service_id'])
    c = pd.merge(b,routes,on=['route_id'])
    c = c.sort_values('arrival_time')
    nextbuses = c[(c['stop_id'] == stop_id) & (c['arrival_time'] >= now) & (c[dow(time)] != 0)].iloc[0:3]
    try:
        getstop(location)[2]
        stop_id2 = getstop(location)[2]
        nextbuses2 = c[(c['stop_id'] == stop_id2) & (c['arrival_time'] >= now) & (c[dow(time)] != 0)].iloc[0:3]
        dfs = [nextbuses,nextbuses2]
        response = prettyprint(pd.concat(dfs)[['arrival_time','route_short_name','trip_headsign']])
        return response
    except IndexError:
        response = prettyprint(nextbuses[['arrival_time','route_short_name','trip_headsign']])
        return response

 
point = geopy.point.Point(46.0678403, 11.1188594) #S.M.MAGGIORE
print(gettrip(point))