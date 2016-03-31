import logging
from google.appengine.ext import ndb
import itinerary
import time_util

class Person(ndb.Model):
    name = ndb.StringProperty()
    active = ndb.BooleanProperty(default=False) # if active driver, passenger
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
    basic_route = ndb.StringProperty()

def addPerson(chat_id, name):
    p = Person.get_or_insert(str(chat_id))
    p.name = name
    p.chat_id = chat_id
    #p.state = -1
    #p.location = '-'
    #p.language = 'IT'
    p.put()
    return p

def updateUsername(p, username):
    if (p.username!=username):
        p.username = username
        p.put()

def getPerson(chat_id):
    return Person.query(Person.chat_id==chat_id).get()

def setActive(p, active):
    p.active = active
    p.put()

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

def setLastCity(p, last_city):
    p.last_city = last_city
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

def setBusStopStart(p, bs): #, swap_active=False
    swapped = False
    if bs == p.bus_stop_end:
        p.bus_stop_end = p.bus_stop_start
        tmp = p.bus_stop_mid_going
        p.bus_stop_mid_going = p.bus_stop_mid_back
        p.bus_stop_mid_back = tmp
        swapped = True
    p.bus_stop_start = bs
    #if swap_active:
    if bs in p.bus_stop_mid_going:
        index = p.bus_stop_mid_going.index(bs)
        p.bus_stop_mid_going = p.bus_stop_mid_going[index+1:]
        swapped = True
    if bs in p.bus_stop_mid_back:
        index = p.bus_stop_mid_back.index(bs)
        p.bus_stop_mid_back = p.bus_stop_mid_back[:index]
        swapped = True
    if not swapped:
        p.basic_route = None
    p.put()

def setBusStopEnd(p, bs): #, swap_active=False
    swapped = False
    if bs == p.bus_stop_start:
        p.bus_stop_start = p.bus_stop_end
        tmp = p.bus_stop_mid_going
        p.bus_stop_mid_going = p.bus_stop_mid_back
        p.bus_stop_mid_back = tmp
        swapped = True
    p.bus_stop_end = bs
    #if swap_active:
    if bs in p.bus_stop_mid_going:
        index = p.bus_stop_mid_going.index(bs)
        p.bus_stop_mid_going = p.bus_stop_mid_going[:index]
        swapped = True
    if bs in p.bus_stop_mid_back:
        index = p.bus_stop_mid_back.index(bs)
        p.bus_stop_mid_back = p.bus_stop_mid_back[index+1:]
        swapped = True
    if not swapped:
        p.basic_route = None
    p.put()

def appendBusStopMidGoing(p, bs):
    #if p.bus_stop_intermediate_going is None:
    #    p.bus_stop_intermediate_going = []
    p.bus_stop_mid_going.append(bs)
    p.basic_route = None
    p.put()

def appendBusStopMidBack(p, bs):
    #if p.bus_stop_intermediate_back is None:
    #    p.bus_stop_intermediate_back = []
    p.bus_stop_mid_back.append(bs)
    p.basic_route = None
    p.put()

def emptyBusStopMidGoing(p):
    p.bus_stop_mid_going = []
    p.basic_route = None
    p.put()

def emptyBusStopMidBack(p):
    p.bus_stop_mid_back = []
    p.basic_route = None
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

def resetBasicRoutes():
    qry = Person.query()
    count = 0
    for p in qry:
        p.basic_routes = None
        p.put()
        count+=1
    return count


def resetActive():
    qry = Person.query()
    count = 0
    for p in qry:
        p.active = False
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

"""
ACTIVE PERSON
"""
"""
class ActivePerson(ndb.Model):
    #person = ndb.StructuredProperty(Person)
    state = ndb.IntegerProperty()
    last_city = ndb.StringProperty()
    last_type = ndb.StringProperty()
    last_seen = ndb.DateTimeProperty()

def addActivePerson(p):
    #ap.key = ndb.Key(ActivePerson, str(person.chat_id))
    ap = ActivePerson(id=str(p.chat_id), state=p.state, last_city=p.last_city,
                      last_type=p.last_type, last_seen=p.last_seen)
    #person=p,
    ap.put()
    #return ap

def setStateActivePerson(person, state):
    ap = ndb.Key(ActivePerson, str(person.chat_id)).get()
    ap.state = state
    ap.put()
    person.state = state
    person.put()

def removeActivePerson(person):
    ndb.Key(ActivePerson, str(person.chat_id)).delete()

"""