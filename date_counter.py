
from google.appengine.ext import ndb
import time_util
import person

class DateCounter(ndb.Model):
    date = ndb.DateProperty(auto_now_add=True)
    people_counter = ndb.IntegerProperty()

def addPeopleCount():
    p = DateCounter.get_or_insert(str(time_util.now()))
    p.people_counter = person.Person.query().count()
    p.put()
    return p