# -*- coding: utf-8 -*-

from google.appengine.ext import ndb

from person import Person

def resetAll():
    for x in [Person]:
        more, cursor = True, None
        total = 0
        while more:
            records, cursor, more = Person.query().fetch_page(1000, keys_only=True, start_cursor=cursor)
            total += len(records)
            if records:
                create_futures = ndb.delete_multi_async(records)
                ndb.Future.wait_all(create_futures)

        print("Cleaned {} from {}".format(total, x.__name__))

def updateItinerary():
    import percorsi
    import person
    percorsi.updateMap()
    person.updatePeopleItinerary()