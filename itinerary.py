# coding=utf-8

from google.appengine.ext import ndb
import math
import operator
import logging
import person


#CITIES
CITY_TRENTO = 'Trento'
CITY_CALTANISSETTA = 'Caltanissetta'

CITIES = (CITY_TRENTO, CITY_CALTANISSETTA)

# http://overpass-turbo.eu/
# node["highway"="bus_stop"]({{bbox}});

#BUS STOPS TRENTO
TN_FS = ('Stazione FS', 46.0725463, 11.1199586, 'FS')
TN_Aquila = ("Venezia Port'Aquila", 46.0695135, 11.1278832, 'P_AQ')
TN_MesianoIng = ("MESIANO Fac. Ingegneria", 46.0671184, 11.1394574, 'MES_ING')
TN_Povo_Valoni = ("POVO Valoni", 46.0655767, 11.1462844, 'PV_VA')
TN_Povo_Sommarive = ("POVO Sommarive", 46.0654307, 11.1503973, 'PV_SO')
TN_Povo_PoloScientifico = ("POVO Polo Scientifico", 46.0671854, 11.1504241, 'PV_SC')
TN_Povo_Manci = ("POVO Piazza Manci", 46.0659831, 11.1545571, 'PV_M')
TN_Rosmini_SMM = ('Rosmini S.Maria Maggiore', 46.0678403, 11.1188594, 'RSM')
TN_Travai = ('Travai', 46.0645194, 11.1209105, 'Tra')
TN_Cavallegggeri = ("3 Nov. Ponte Cavalleggeri", 46.0592422, 11.126718, 'CAV')
TN_Questura = ("Verona Questura", 46.0457542, 11.1309265, 'QSTR')

#new entry
TN_Pergine_FS = ("Pergine FS", 46.0634661, 11.2315599, 'PER_FS')
TN_Mattarello_Catorni = ("Mattarello Catoni", 46.009173, 11.128193, 'MAT_CA')
TN_NORD_ZONA_COMMERCIALE = ("Trento Nord Zona Commerciale", 46.090066, 11.113395, 'NZC')

#RIVA - ARCO
TN_RIVA_INVIOLATA = ("Riva Inviolata", 45.889042, 10.843240, 'RDG_INV')
TN_ARCO_CASINO = ("Arco Casinò", 45.917813, 10.885141, 'ARC_CAS')
TN_ARCO_S_CAT_POLI = ("Arco S.Caterina Poli", 45.909959, 10.870948, 'ARC_CAS')

#RIVA - LEDRO
TN_RIVA_FLORIANI = ("Riva rotonda Floriani", 45.894707, 10.843048, 'RDG_RFL')
TN_LEDRO_BIACESA = ("Ledro Biacesa", 45.865099, 10.805401, "LDR_BIA")
TN_LEDRO_MOLINA = ("Ledro Molina", 45.871800, 10.772175, "LDR_MLN")
TN_LEDRO_MEZZOLAGO = ("Ledro Mezzolago", 45.881077, 10.750451, "LDR_ML")
TN_LEDRO_PIEVE = ("Pieve (consorzio turismo residence)", 45.889473, 10.729370, "LDR_PV")
TN_LEDRO_BEZZECCA = ("Bezzecca (albergo da Gino)", 45.895281, 10.715026, "LDR_BZC")
TN_LEDRO_TIARNO_SOTTO = ("Tiarno di sotto (benzinaio)", 45.892677, 10.685424, "LDR_TNA")
TN_LEDRO_TIARNO_SOPRA = ("Tiarno di sopra (Ribaga)", 45.888336, 10.671004, "LDR_TNB")

#RIVA - TENNO
TN_RIVA_MALOSSINI = ("Riva v. Oleandri (CS Malossini)", 45.897645, 10.844131, "RDG_CSM")
TN_TENNO_GAVAZZO = ("Gavazzo (bus stop)", 45.912496, 10.841007, "TEN_GAV")
TN_TENNO_COLOGNA = ("Cologna alta (chiesa parrocchiale)", 45.914870, 10.842381, "TEN_COL")
TN_TENNO_FARMACIA = ("Tenno farmacia", 45.918102, 10.832828, "TEN_FAR")
TN_TENNO_ZANOLLI = ("Ville del monte (Ex albergo Zanolli)", 45.930241, 10.822422, "TEN_ZAN")

#MORI - BESAGNO
#TN_MORI_BC = ("Mori Bar Centrale",  45.851634, 10.9788377, "MOR")
#TN_MORI_BESAGNO = ("Besagno", 45.8380353, 10.965215, "MOR_BS")

#for back compatibility (dashboard)
FERMATA_TRENTO = TN_Aquila[0]
FERMATA_POVO = TN_Povo_PoloScientifico[0]


#BUS STOPS CALTANISSETTA
CL_FS = ('Stazione FS', 37.4885123, 14.0577765, 'FS')
CL_Cefpas = ('Cefpas', 37.490577, 14.0290256, 'CEFPAS')

CITY_BUS_STOPS = {
    CITY_TRENTO: (
        TN_Povo_Valoni,
        TN_Povo_Sommarive,
        TN_Povo_PoloScientifico,
        TN_Povo_Manci,
        TN_FS,
        TN_Aquila,
        TN_MesianoIng,
        TN_Rosmini_SMM,
        TN_Travai,
        TN_Cavallegggeri,
        TN_Questura,
        TN_Pergine_FS,
        TN_Mattarello_Catorni,
        TN_NORD_ZONA_COMMERCIALE,
        TN_RIVA_INVIOLATA,
        TN_ARCO_CASINO,
        TN_ARCO_S_CAT_POLI,
        #
        TN_RIVA_FLORIANI,
        TN_LEDRO_BIACESA,
        TN_LEDRO_MOLINA,
        TN_LEDRO_MEZZOLAGO,
        TN_LEDRO_PIEVE,
        TN_LEDRO_BEZZECCA,
        TN_LEDRO_TIARNO_SOTTO,
        TN_LEDRO_TIARNO_SOPRA,
        #
        TN_RIVA_MALOSSINI,
        TN_TENNO_GAVAZZO,
        TN_TENNO_COLOGNA,
        TN_TENNO_FARMACIA,
        TN_TENNO_ZANOLLI,
        #
        #TN_MORI_BC,
        #TN_MORI_BESAGNO
    ),
    CITY_CALTANISSETTA: (
        CL_FS,
        CL_Cefpas
    )
}

BASIC_ROUTES = {
    "/Trento_Povo_Bus_5": (
        CITY_TRENTO, #city
        TN_Aquila[0], #start
        TN_Povo_PoloScientifico[0], #end
        [TN_MesianoIng[0]], #mid_going
        [TN_MesianoIng[0]], #mid_back
    ),
    "/Riva_Arco": (
        CITY_TRENTO, #city
        TN_RIVA_INVIOLATA[0], #start
        TN_ARCO_CASINO[0], #end
        [TN_ARCO_S_CAT_POLI[0]], #mid_going
        [TN_ARCO_S_CAT_POLI[0]], #mid_back
    ),
    "/Riva_Ledro": (
        CITY_TRENTO,  #city
        TN_RIVA_FLORIANI[0],  #start
        TN_LEDRO_TIARNO_SOPRA[0],  #end
        [TN_LEDRO_BIACESA[0], TN_LEDRO_MOLINA[0], TN_LEDRO_MEZZOLAGO[0], TN_LEDRO_PIEVE[0], TN_LEDRO_BEZZECCA[0], TN_LEDRO_TIARNO_SOTTO[0]],  #mid_going
        [TN_LEDRO_TIARNO_SOTTO[0], TN_LEDRO_BEZZECCA[0], TN_LEDRO_PIEVE[0], TN_LEDRO_MEZZOLAGO[0], TN_LEDRO_MOLINA[0], TN_LEDRO_BIACESA[0]], #mid_back
    ),
    "/Riva_Tenno": (
        CITY_TRENTO, #city
        TN_RIVA_MALOSSINI[0], #start
        TN_TENNO_ZANOLLI[0], #end
        [TN_TENNO_GAVAZZO[0],TN_TENNO_COLOGNA[0],TN_TENNO_FARMACIA[0]], #mid_going
        [TN_TENNO_FARMACIA[0],TN_TENNO_COLOGNA[0],TN_TENNO_GAVAZZO[0]], #mid_back
    ),
    #"/Mori_Besagno": (
    #    CITY_TRENTO, #city
    #    TN_MORI_BC[0], #start
    #    TN_MORI_BESAGNO[0], #end
    #    [], #mid_going
    #    [], #mid_back
    #)
}

MAX_CLUSTER_DISTANCE = 0.5 #km

class BusStop(ndb.Model):
    city = ndb.StringProperty()
    name = ndb.StringProperty()
    short_name = ndb.StringProperty()
    location = ndb.GeoPtProperty()
    cluster = ndb.StringProperty(repeated=True)

def getKeyFromBusStop(bus_stop):
    return bus_stop.city + " " + bus_stop.name

def getKey(cityName, bsName):
    return cityName + " " + bsName

def getBusStop(cityName, bsName):
    key = getKey(cityName, bsName)
    return ndb.Key(BusStop, key).get()

def initBusStops(delete=False):
    if delete:
        ndb.delete_multi(BusStop.query().fetch(keys_only=True))
    for city_key in CITY_BUS_STOPS:
        for bs_lat_lon in CITY_BUS_STOPS[city_key]:
            bs_name = bs_lat_lon[0]
            key = getKey(city_key,bs_name)
            bs = ndb.Key(BusStop, key).get()
            if (bs==None):
                bs = BusStop.get_or_insert(key)
                bs.populate(city=city_key,name=bs_lat_lon[0],location=ndb.GeoPt(bs_lat_lon[1], bs_lat_lon[2]), short_name=bs_lat_lon[3])
            bs.cluster = [bs_name]
            bs.put()
    for city_key in CITY_BUS_STOPS:
        city_busstops = CITY_BUS_STOPS[city_key]
        for stop_i in city_busstops:
            stop_i_name = stop_i[0]
            bs_i = getBusStop(city_key, stop_i_name)
            loc_i=ndb.GeoPt(stop_i[1], stop_i[2])
            for stop_j in city_busstops:
                stop_j_name = stop_j[0]
                if (stop_i_name==stop_j_name):
                    continue
                loc_j=ndb.GeoPt(stop_j[1], stop_j[2])
                dst = HaversineDistance(loc_i, loc_j)
                if (dst<=MAX_CLUSTER_DISTANCE):
                    bs_i.cluster.append(stop_j_name)
                    bs_i.put()

class BasicRoutes(ndb.Model):
    city = ndb.StringProperty()
    bus_stop_start = ndb.StringProperty()
    bus_stop_end = ndb.StringProperty()
    bus_stop_mid_going = ndb.StringProperty(repeated=True)
    bus_stop_mid_back = ndb.StringProperty(repeated=True)

def initBasicRoutes(delete=False):
    if delete:
        ndb.delete_multi(BasicRoutes.query().fetch(keys_only=True))
    for route_cmd in BASIC_ROUTES:
        route = BasicRoutes.get_or_insert(route_cmd)
        route_data = BASIC_ROUTES[route_cmd]
        logging.debug(str(route_data))
        route.populate(
            city=route_data[0],
            bus_stop_start=route_data[1],
            bus_stop_end=route_data[2],
            bus_stop_mid_going=route_data[3],
            bus_stop_mid_back=route_data[4]
        )
        route.put()

def getBasicRoutesCommands():
    cmd = []
    routes = BasicRoutes.query().fetch(keys_only=True)
    for r in routes:
        cmd.append(r.id())
    return cmd

def setBasicRoute(p, route_cmd):
    route = ndb.Key(BasicRoutes, route_cmd).get()
    p.populate(last_city = route.city,
        bus_stop_start = route.bus_stop_start,
        bus_stop_end = route.bus_stop_end,
        bus_stop_mid_going=route.bus_stop_mid_going,
        bus_stop_mid_back=route.bus_stop_mid_back
    )
    p.put()

def HaversineDistance(loc1, loc2):
    """Method to calculate Distance between two sets of Lat/Lon."""
    lat1 = loc1.lat
    lon1 = loc1.lon
    lat2 = loc2.lat
    lon2 = loc2.lon
    earth = 6371 #Earth's Radius in Kms.

    #Calculate Distance based in Haversine Formula
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = earth * c
    return d

MAX_DISTANCE = 1.0 #km

def getBusStopLocation(city, bs_name):
    bs = BusStop.query(BusStop.city==city, BusStop.name==bs_name).get()
    return bs.location

def matchDriverStartWithLocation(driver, bus_stop_name):
    bs_start_d = getBusStop(driver.last_city, driver.location)
    bs_start_p = getBusStop(driver.last_city, bus_stop_name)
    if (bs_start_d is None or bs_start_p is None):
        return False
    return matchClusterLocation(bs_start_d, bs_start_p)

def matchDriverEndWithLocation(driver, bus_stop_name):
    bs_end_d = getBusStop(driver.last_city, person.getDestination(driver))
    bs_end_p = getBusStop(driver.last_city, bus_stop_name)
    if (bs_end_d is None or bs_end_p is None):
        return False
    return matchClusterLocation(bs_end_d, bs_end_p)

def matchDriverMidPointsGoingWithLocation(driver, bus_stop_name):
    midPoints = person.getMidPoints(driver)
    if not midPoints:
        return False
    bs_start_p = getBusStop(driver.last_city, bus_stop_name)
    for md in midPoints:
        bs_start_d = getBusStop(driver.last_city, md)
        if bs_start_d is not None and bs_start_p is not None and matchClusterLocation(bs_start_d, bs_start_p):
            return True
    return False

def matchDriverMidPointsBackWithLocation(driver, bus_stop_name):
    midPoints = person.getMidPoints(driver)
    if not midPoints:
        return False
    bs_end_p = getBusStop(driver.last_city, bus_stop_name)
    for md in midPoints:
        bs_end_d = getBusStop(driver.last_city, md)
        if bs_end_d is not None and bs_end_p is not None and matchClusterLocation(bs_end_d, bs_end_p):
            return True
    return False


# match only if driver passes through their exact location
def matchDriverAndPassenger(driver, passenger):
    bus_stop_passenger = passenger.location
    return ( matchDriverStartWithLocation(driver, bus_stop_passenger) or
             matchDriverMidPointsGoingWithLocation(driver, bus_stop_passenger)) and\
           (matchDriverStartWithLocation(driver, bus_stop_passenger) or
            matchDriverMidPointsBackWithLocation(driver, bus_stop_passenger))

# passengers get notified even if driver doesn't pass through their exact location
def matchDriverAndPotentialPassenger(driver, passenger):
    bus_stop_passenger = [passenger.bus_stop_start, passenger.bus_stop_end]
    bus_stop_driver = [driver.bus_stop_start, driver.bus_stop_end]
    for i in [0,1]:
        if passenger.chat_id == 130870321:
            logging.debug(str(bus_stop_driver))
            logging.debug(str(bus_stop_passenger))
            logging.debug(str(matchDriverStartWithLocation(driver, bus_stop_passenger[i])) + ' ' +
                          str(matchDriverMidPointsGoingWithLocation(driver, bus_stop_passenger[i])) + ' ' +
                          str(matchDriverEndWithLocation(driver, bus_stop_passenger[1-i])) + ' ' +
                          str(matchDriverMidPointsBackWithLocation(driver, bus_stop_passenger[1-i]))
                          )
        if (matchDriverStartWithLocation(driver, bus_stop_passenger[i]) or
            matchDriverMidPointsGoingWithLocation(driver, bus_stop_passenger[i])) and \
            (matchDriverEndWithLocation(driver, bus_stop_passenger[1-i]) or
            matchDriverMidPointsBackWithLocation(driver, bus_stop_passenger[1-i])):
            return True
    return False


def matchClusterLocation(loc1, loc2):
    #return loc1.name == loc2.name or loc2.name in loc1.cluster
    return loc2.name in loc1.cluster


def getClosestBusStops(loc_point, exclude_points, person, max_distance=MAX_DISTANCE, trim=True):
    result = []
    first = True
    for bs in BusStop.query():
        if bs.name in exclude_points:
            continue
        dst = HaversineDistance(bs.location, loc_point)
        if (dst<=max_distance):
            result.append([bs.name, dst])
            if first:
                first = False
                person.last_city = bs.city
                person.put()
    result = sort_table(result, 1)
    #logging.debug(result)
    if trim:
        result = result[:2]
    return column(result,0)

def getOtherBusStops(person):
    result = []
    first = True
    for bs in BusStop.query(BusStop.city==person.last_city):
        if (bs.name not in [person.bus_stop_start,person.bus_stop_end] and
            bs.name not in person.bus_stop_mid_going and
            bs.name not in person.bus_stop_mid_back):
            result.append(bs.name)
    return result

def sort_table(table, col=0):
    return sorted(table, key=operator.itemgetter(col))

def column(matrix, i):
    return [row[i] for row in matrix]



