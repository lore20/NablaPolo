from geopy.geocoders import Nominatim
from geopy.geocoders import GoogleV3
from geopy.distance import vincenty
from geopy.exc import GeocoderServiceError

import key
import logging
from geoLocation import GeoLocation


#https://raw.githubusercontent.com/dakk/Italia.json/master/italia_comuni.json

GEOLOCATOR_1 = Nominatim()
GEOLOCATOR_2 = GoogleV3(key.GOOGLE_API_KEY)

def getLocationFromAddress(locationName):
    try:
        for g in [GEOLOCATOR_1, GEOLOCATOR_2]:
            location = g.geocode(
                #locationName, timeout=10, exactly_one=True, language='it', region='it') #default one answer for Nominatim (not google)
                locationName, timeout=10, exactly_one=True, language='it')  # default one answer for Nominatim (not google)
            if location :
                return location
    except GeocoderServiceError:
        logging.error('GeocoderServiceError occurred')


def distance(point1, point2):
    #point1 = (41.49008, -71.312796)
    #point2 = (41.499498, -81.695391)
    return vincenty(point1, point2).kilometers


def getBoxCoordinates(lat, lon, radius):
    loc = GeoLocation.from_degrees(lat, lon)
    boxMinMaxCorners = loc.bounding_locations(radius)
    boxMinCorners = boxMinMaxCorners[0]
    boxMaxCorners = boxMinMaxCorners[1]
    latMin = boxMinCorners.deg_lat
    lonMin = boxMinCorners.deg_lon
    latMax = boxMaxCorners.deg_lat
    lonMax = boxMaxCorners.deg_lon
    return latMin, lonMin, latMax, lonMax

