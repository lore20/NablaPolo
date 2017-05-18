# coding=utf-8

import logging
from google.appengine.ext import ndb
from geo import geomodel, geotypes

import utility
import params

class Person_Backup(geomodel.GeoModel, ndb.Model): #ndb.Expando
    chat_id = ndb.IntegerProperty()
    name = ndb.StringProperty()
    last_name = ndb.StringProperty()
    username = ndb.StringProperty()
    last_mod = ndb.DateTimeProperty(auto_now=True)
    state = ndb.IntegerProperty()
    enabled = ndb.BooleanProperty(default=True)
    notification_mode = ndb.StringProperty(default=params.NOTIFICATION_MODE_ALL)

    percorsi_start_fermata = ndb.StringProperty(repeated=True)
    percorsi_start_place = ndb.StringProperty(repeated=True)
    percorsi_end_place = ndb.StringProperty(repeated=True)

    # location = ndb.GeoPtProperty() # inherited from geomodel.GeoModel
    latitude = ndb.ComputedProperty(lambda self: self.location.lat if self.location else None)
    longitude = ndb.ComputedProperty(lambda self: self.location.lon if self.location else None)

    new_tmp_variable = ndb.PickleProperty()


def populatePersonBackup():
    from person import Person
    more, cursor = True, None
    while more:
        records, cursor, more = Person.query().fetch_page(1000, start_cursor=cursor)
        new_utenti = []
        for ent in records:
            u = Person_Backup(
                id=str(ent.chat_id),
                chat_id=ent.chat_id,
                name=ent.name,
                last_name=ent.last_name,
                username=ent.username,
                notification_mode=params.DEFAULT_NOTIFICATIONS_MODE,
                new_tmp_variable={}
            )
            new_utenti.append(u)
        if new_utenti:
            create_futures = ndb.put_multi_async(new_utenti)
            ndb.Future.wait_all(create_futures)
