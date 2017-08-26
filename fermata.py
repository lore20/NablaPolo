# -*- coding: utf-8 -*-

from google.appengine.ext import ndb
import geoUtils
from geo import geomodel, geotypes

class Fermata(geomodel.GeoModel, ndb.Model):
    # format retourned by routing_util.encodeFermataKey
    # e.g., Ledro (Tiarno di sotto - benzinaio)
    #fermata_key = ndb.StringProperty() # id

    active = ndb.BooleanProperty()

    # location = ndb.GeoPtProperty() # inherited from geomodel.GeoModel
    #latitude = location.lat
    #longitude = location.lon

    def getFermataKey(self):
        return self.key.id()


def getClosestActiveFermata(lat, lon, radius):
    origin_point = (lat, lon)
    latMin, lonMin, latMax, lonMax = geoUtils.getBoxCoordinates(lat, lon, radius)
    box = geotypes.Box(latMax, lonMax, latMin, lonMin)  # north, east, south, west
    qry = Fermata.query(Fermata.active==True)
    fermate = Fermata.bounding_box_fetch(qry, box)
    if fermate:
        return min(
            fermate,
            key=lambda f: geoUtils.distance(origin_point, (f.location.lat, f.location.lon))
        )


