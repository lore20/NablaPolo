import logging
from google.appengine.ext import ndb
import itinerary
import time_util

"""
class ActivePerson(ndb.Model):
    person = ndb.StructuredProperty(Person)
    state = ndb.IntegerProperty()
    last_city = ndb.StringProperty()
    last_seen = ndb.DateTimeProperty()

def addActivePerson(person):
    ap = ActivePerson.get_or_insert(str(person.chat_id))
    ap.person = person
    ap.state = person.state
    ap.last_city = person.last_city
    ap.last_seen = person.last_seen
    ap.put()

def updateStateActivePerson(person, state):
    ap = ActivePerson.get_or_insert(str(person.chat_id))
    ap.state = state
    ap.person.state = state
    ap.person.put()
    ap.put()

def updateLastSeenActivePerson(person, lastSeen):
    ap = ActivePerson.get_or_insert(str(person.chat_id))
    ap.lastSeen = lastSeen
    ap.person.lastSeen = lastSeen
    ap.person.put()
    ap.put()

def updateStateLastSeenActivePerson(person, state, lastSeen):
    ap = ActivePerson.get_or_insert(str(person.chat_id))
    ap.state = state
    ap.person.state = state
    ap.lastSeen = lastSeen
    ap.person.lastSeen = lastSeen
    ap.person.put()
    ap.put()

def removeActivePerson(person):
    ndb.Key(ActivePerson, str(person.chat_id)).delete()
"""

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
    agree_on_terms = ndb.BooleanProperty(default=False)
    notification_enabled = ndb.BooleanProperty(default=True)
    bus_stop_start = ndb.StringProperty()
    bus_stop_end = ndb.StringProperty()
    bus_stop_mid_going = ndb.StringProperty(repeated=True)
    bus_stop_mid_back = ndb.StringProperty(repeated=True)
    tmp = ndb.StringProperty(repeated=True)
    last_city = ndb.StringProperty()
    notified = ndb.BooleanProperty(default=False)
    prev_state = ndb.IntegerProperty()

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
    p.prev_state = p.state
    p.state = state
    p.put()

def setLastSeen(p, date):
    p.last_seen = date
    p.put()

def updateLastSeen(p):
    p.last_seen = time_util.now()
    p.put()

def setNotified(p, value):
    p.notified = value
    p.put()

def getDestination(p):
    if p.location==p.bus_stop_start:
        return p.bus_stop_end
    return p.bus_stop_start

def getMidPoints(p):
    if p.location==p.bus_stop_start:
        return p.bus_stop_mid_going
    return p.bus_stop_mid_back

def getItinerary(p, driver):
    start = p.location
    end = getDestination(p)
    midPoints = []
    if driver:
        midPoints = getMidPoints(p)
    txt = start + " -> "
    for mp in midPoints:
        txt += mp + " -> "
    txt += end
    return txt

def getLocationCluster(p):
    return itinerary.getBusStop(p.last_city, p.location).cluster

def getDestinationCluster(p):
    return itinerary.getBusStop(p.last_city, getDestination(p)).cluster

def getBusStop(p):
    return itinerary.getBusStop(p.last_city, p.location)

def setLocation(p, loc):
    p.location = loc
    p.put()

def setStateLocation(p, state, loc):
    p.state = state
    p.location = loc
    p.put()

def setNotifications(p,value):
    p.notification_enabled = value
    p.put()

def setAgreeOnTerms(p):
    p.agree_on_terms = True
    p.put()

def clearTmp(p):
    p.tmp = []
    p.put()


def setTmp(p, value):
    p.tmp = value
    p.put()

def appendTmp(p, value):
    # value mus be a list
    for x in value:
        p.tmp.append(x)
    p.put()


def isItinerarySet(p):
    return p.bus_stop_start!=None and p.bus_stop_end!=None

def setBusStopStart(p, bs):
    p.bus_stop_start = bs
    p.put()

def setBusStopEnd(p, bs):
    p.bus_stop_end = bs
    p.put()

def appendBusStopMidGoing(p, bs):
    #if p.bus_stop_intermediate_going is None:
    #    p.bus_stop_intermediate_going = []
    p.bus_stop_mid_going.append(bs)
    p.put()

def appendBusStopMidBack(p, bs):
    #if p.bus_stop_intermediate_back is None:
    #    p.bus_stop_intermediate_back = []
    p.bus_stop_mid_back.append(bs)
    p.put()

def emptyBusStopMidGoing(p):
    p.bus_stop_mid_going = []
    p.put()

def emptyBusStopMidBack(p):
    p.bus_stop_mid_back = []
    p.put()

def resetTermsAndNotification():
    qry = Person.query()
    count = 0
    for p in qry:
        p.agree_on_terms = False
        p.notification_enabled = True
        p.put()
        count+=1
    return count

def resetAllState(s):
    qry = Person.query()
    count = 0
    for p in qry:
        p.state = s
        p.put()
        count+=1
    logging.debug("Reset all states to " + str(s) + ": " + str(count))
    return count

def resetNullStatesUsers():
    qry = Person.query()
    count = 0
    for p in qry:
        if (p.state is None): # or p.state>-1
            setState(p,-1)
            count+=1
    return count

def resetLanguages():
    qry = Person.query()
    for p in qry:
        p.language = 'IT'
        p.put()

def resetEnabled():
    qry = Person.query()
    for p in qry:
        p.enabled = True
        p.put()

def isDriverOrPassenger(p):
    return p.state in [21, 22, 23, 30, 31, 32, 33]

def listAllDrivers():
    qry = Person.query().filter(Person.state.IN([30, 31, 32, 33]))
    if qry.get() is None:
        return "No drivers found"
    else:
        #qry = qry.order(-Person.last_mod)
        text = ""
        for d in qry:
            text = text + d.name.encode('utf-8') + _(' ') + d.location + _(" (") + str(d.state) + \
                   _(") ") + time_util.get_time_string(d.last_seen) + _("\n")
        return text


def listAllPassengers():
    qry = Person.query().filter(Person.state.IN([21, 22, 23]))
    if qry.get() is None:
        return _("No passangers found")
    else:
        #qry = qry.order(-Person.last_mod)
        text = ""
        for p in qry:
            text = text + p.name.encode('utf-8') + _(' ') + p.location + " (" + str(p.state) + ") " + time_util.get_time_string(p.last_seen) + _("\n")
        return text