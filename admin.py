# -*- coding: utf-8 -*-

from google.appengine.ext import ndb

from person import Person

def resetAll():
    for x in [Person]:
        create_futures = ndb.delete_multi_async(
            x.query().fetch(keys_only=True)
        )
        ndb.Future.wait_all(create_futures)
        print("Cleaned {}".format(x.__name__))
