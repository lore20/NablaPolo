
from google.appengine.ext import ndb

class Person(ndb.Model):
    name = ndb.StringProperty()
    last_name = ndb.StringProperty(default='-')
    username = ndb.StringProperty(default='-')
    last_mod = ndb.DateTimeProperty(auto_now=True)
    last_seen = ndb.DateTimeProperty()
    chat_id = ndb.IntegerProperty()
    state = ndb.IntegerProperty()
    ticket_id = ndb.StringProperty()
    last_type = ndb.StringProperty(default='-1')
    location = ndb.StringProperty(default='-')
    language = ndb.StringProperty(default='IT')
    enabled = ndb.BooleanProperty(default=True)


def addPerson(chat_id, name):
    p = Person.get_or_insert(str(chat_id))
    p.name = name
    p.chat_id = chat_id
    #p.state = -1
    #p.location = '-'
    #p.language = 'IT'
    p.put()
    return p

def setType(p, type):
    p.last_type = type
    p.put()

def setState(p, state):
    p.state = state
    p.put()

def setLocation(p, loc):
    p.location = loc
    p.put()

def setStateLocation(p, state, loc):
    p.state = state
    p.location = loc
    p.put()