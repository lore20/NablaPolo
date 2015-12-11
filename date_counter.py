
from google.appengine.ext import ndb
import date_util
import person

class DateCounter(ndb.Model):
    date = ndb.DateProperty(auto_now_add=True)
    people_counter = ndb.IntegerProperty()

def addPeopleCount():
    p = DateCounter.get_or_insert(str(date_util.now()))
    p.people_counter = person.Person.query().count()
    p.put()
    return p