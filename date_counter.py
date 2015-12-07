
from google.appengine.ext import ndb

class DateCounter(ndb.Model):
    date = ndb.DateProperty(auto_now_add=True)
    people_counter = ndb.IntegerProperty()

def addPeopleCount():
    p = DateCounter.get_or_insert(str(datetime.now()))
    p.people_counter = Person.query().count()
    p.put()
    return p