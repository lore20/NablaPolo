# coding=utf-8

import geoUtils

from geo import geomodel, geotypes
from google.appengine.ext import ndb

from itinerary import BASE_MAP_IMG_URL, FERMATE_DICT

class Fermata(geomodel.GeoModel, ndb.Model):
    # name = id
    # location = ndb.GeoPtProperty() # inherited from geomodel.GeoModel
    latitude = ndb.ComputedProperty(lambda self: self.location.lat if self.location else None)
    longitude = ndb.ComputedProperty(lambda self: self.location.lon if self.location else None)

def getFermateNearPositionImgUrl(lat, lon, radius=1):
    latMin, lonMin, latMax, lonMax = geoUtils.getBoxCoordinates(lat, lon, radius)
    box = geotypes.Box(latMax, lonMax, latMin, lonMin)  # north, east, south, west
    qry = Fermata.query()
    fermate = Fermata.bounding_box_fetch(qry, box)
    if fermate:
        img_url = BASE_MAP_IMG_URL + \
                  "&markers=color:red|{0},{1}".format(lat, lon) + \
                  ''.join(["&markers=color:blue|{0},{1}".format(f.location.lat, f.location.lon) for f in fermate])
        text = "{} fermate trovate nel raggio di {} km dalla posizione inserita:\n".format(len(fermate),radius)
        text += '\n'.join('- {}'.format(f.key.id()) for f in fermate)
    else:
        img_url = None
        text = 'Nessuna fermata trovata nel raggio di {} km dalla posizione inserita.'.format(radius)
    return img_url, text

def populateFermate():
    entries = []
    for name,loc in FERMATE_DICT.iteritems():
        f = Fermata(id=name, location = ndb.GeoPt(loc[0], loc[1]))
        f.update_location()
        entries.append(f)
    create_futures = ndb.put_multi_async(entries)
    ndb.Future.wait_all(create_futures)

def deleteAllFermate():
    delete_futures = ndb.delete_multi_async(
        Fermata.query().fetch(keys_only=True)
    )
    ndb.Future.wait_all(delete_futures)
