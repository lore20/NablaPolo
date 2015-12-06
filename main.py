#import json
import json
import logging
import urllib
import urllib2
import datetime
from datetime import datetime
from datetime import timedelta
from time import sleep
import date_util
# import requests

import key
import emoij

# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.api import channel
from google.appengine.api import taskqueue
from google.appengine.ext import deferred

#from google.appengine.ext import vendor
#vendor.add('lib')

import webapp2
#from flask import Flask, jsonify

import gettext

from jinja2 import Environment, FileSystemLoader

# ================================
# ================================
# ================================

BASE_URL = 'https://api.telegram.org/bot' + key.TOKEN + '/'

DASHBOARD_DIR_ENV = Environment(loader=FileSystemLoader('dashboard'), autoescape = True)
tell_completed = False

STATES = {
    -1: 'Initial',
    0:   'Started',
    20:  'PassengerAskedForLoc',
    21:  'PassengerBored',
    22:  'PassengerEngaged',
    23:  'PassengerConfirmedRide',
    30:  'DriverAskedForLoc',
    31:  'DriverAskedForTime',
    32:  'DriverWhoHasLeft',
    315: 'DriverSendingMessage',
    33:  'DriverTookSomeone',
    90:  'Settings',
    91:  'Language'
}

LANGUAGES = {'IT': 'it_IT',
             'EN': 'en',
             'FR': 'fr_FR',
             'DE': 'de',
             'NL': 'nl',
             'PL': 'pl',
             'RU': 'ru'}

# ================================
# ================================
# ================================

class Counter(ndb.Model):
    name = ndb.StringProperty()
    counter = ndb.IntegerProperty()


FERMATA_TRENTO = 'Trento Porta Aquila'
FERMATA_POVO = 'Povo Sommarive/Valoni/Mesiano' #'Povo Sommarive'


MAX_WAITING_PASSENGER_MIN = 25
MAX_PICKUP_DRIVER_MIN = 10
MAX_COMPLETE_DRIVER_MIN = 15

QUEUE_PASSENGERS_COUNTER_POVO = 'Queue_Passengers_Counter_Povo'
QUEUE_PASSENGERS_COUNTER_TRENTO = 'Queue_Passengers_Counter_Trento'
QUEUE_DRIVERS_COUNTER_POVO = 'Queue_Drivers_Counter_Povo'
QUEUE_DRIVERS_COUNTER_TRENTO = 'Queue_Drivers_Counter_Trento'
TN_PV_CURRENT_RIDES = 'tn_pv_current_rides'
TN_PV_TOTAL_RIDES = 'tn_pv_total_rides'
TN_PV_TOTAL_PASSENGERS = 'tn_pv_total_passengers'
PV_TN_CURRENT_RIDES = 'pv_tn_current_rides'
PV_TN_TOTAL_RIDES = 'pv_tn_total_rides'
PV_TN_TOTAL_PASSENGERS = 'pv_tn_total_passengers'

COUNTERS = [QUEUE_PASSENGERS_COUNTER_POVO, QUEUE_PASSENGERS_COUNTER_TRENTO,
            QUEUE_DRIVERS_COUNTER_POVO, QUEUE_DRIVERS_COUNTER_TRENTO,
            TN_PV_CURRENT_RIDES, TN_PV_TOTAL_RIDES, TN_PV_TOTAL_PASSENGERS,
            PV_TN_CURRENT_RIDES, PV_TN_TOTAL_RIDES, PV_TN_TOTAL_PASSENGERS]

def resetCounter():
    for name in COUNTERS:
        c = Counter.get_or_insert(str(name))
        c.name = name
        c.counter = 0
        c.put()

def increaseQueueCounter(n):
    entry = Counter.query(Counter.name == n).get()
    c = entry.counter
    c = (c+1)%100
    if (c==0):
        c=1
    entry.counter = c
    entry.put()
    return c

def increaseCounter(c, i):
    entry = Counter.query(Counter.name == c).get()
    c = entry.counter
    c = (c+i)
    entry.counter = c
    entry.put()
    return c

def increaseRides(driver):
    riders_current_counter = TN_PV_CURRENT_RIDES if driver.location == FERMATA_TRENTO else PV_TN_CURRENT_RIDES
    increaseCounter(riders_current_counter, 1)
    riders_tot_current_counter = TN_PV_TOTAL_RIDES if driver.location == FERMATA_TRENTO else PV_TN_TOTAL_RIDES
    increaseCounter(riders_tot_current_counter, 1)

def decreaseRides(driver):
    riders_current_counter = TN_PV_CURRENT_RIDES if driver.location == FERMATA_TRENTO else PV_TN_CURRENT_RIDES
    increaseCounter(riders_current_counter, -1)

def increasePassengerRide(passenger):
    passenger_tot_counter = TN_PV_TOTAL_PASSENGERS if passenger.location == FERMATA_TRENTO else PV_TN_TOTAL_PASSENGERS
    increaseCounter(passenger_tot_counter, 1)

def getTodayTimeline():

    todayEvents = {FERMATA_TRENTO: {}, FERMATA_POVO: {}}

    today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
    #today = today - timedelta(days=1)

    for loc in [FERMATA_TRENTO,FERMATA_POVO]:

        requests = []
        qryRideRequests = RideRequest.query(RideRequest.passenger_last_seen > today)
        for r in qryRideRequests:
            #RideRequest.passenger_location==loc
            #logging.debug(r.passenger_location + " " + str(r.passenger_location==loc))
            if (r.passenger_location==loc):
                start = r.passenger_last_seen
                end = r.abort_time
                if (end is not None):
                    requests.append([start.isoformat(), end.isoformat()])

        todayEvents[loc][loc + ' Ride Requests'] = requests

        offers = []
        qryRideOffers = Ride.query(Ride.start_daytime > today)
        for r in qryRideOffers:
            if (r.start_location==loc):
                start = r.start_daytime
                end = r.abort_daytime if r.abort_daytime is not None else r.end_daytime
                if (end is not None):
                    offers.append([start.isoformat(), end.isoformat()])

        #requests = date_util.removeOverlapping(requests)
        #offers = date_util.removeOverlapping(offers)

        todayEvents[loc][loc + ' Ride Offers'] = offers

    return todayEvents

def getDashboardData():
    p_wait_trento = Person.query().filter(Person.location == FERMATA_TRENTO, Person.state.IN([21, 22])).count()
    p_wait_povo = Person.query().filter(Person.location == FERMATA_POVO, Person.state.IN([21, 22])).count()

    r_cur_tn_pv = Counter.query(Counter.name == 'tn_pv_current_rides').get().counter
    #p_cur_tn_pv = 0
    r_tot_tn_pv = Counter.query(Counter.name == 'tn_pv_total_rides').get().counter
    p_tot_tn_pv = Counter.query(Counter.name == 'tn_pv_total_passengers').get().counter

    r_cur_pv_tn = Counter.query(Counter.name == 'pv_tn_current_rides').get().counter
    #p_cur_pv_tn = 0
    r_tot_pv_tn = Counter.query(Counter.name == 'pv_tn_total_rides').get().counter
    p_tot_pv_tn = Counter.query(Counter.name == 'pv_tn_total_passengers').get().counter

    data = {
        "passenger": {
            "trento": str(p_wait_trento),
            "povo": str(p_wait_povo)
        },
        "ridesPovoToTrento": {
            "currentRides": str(r_cur_tn_pv),
    #                "Current passengers": p_cur_tn_pv,
            "totalRides": str(r_tot_tn_pv),
            "totalPassengers": str(p_tot_tn_pv)
        },
        "ridesTrentoToPovo": {
            "currentRides": str(r_cur_pv_tn),
    #               "Current passengers": p_cur_pv_tn,
            "totalRides": str(r_tot_pv_tn),
            "totalPassengers": str(p_tot_pv_tn)
        }
        # "Drivers": {
        #     "Trento": countDrivers(FERMATA_TRENTO),
        #     "Povo": countDrivers(FERMATA_POVO)
        # }
    }
    return data

# ================================
# ================================
# ================================


class DateCounter(ndb.Model):
    date = ndb.DateProperty(auto_now_add=True)
    people_counter = ndb.IntegerProperty()

def addPeopleCount():
    p = DateCounter.get_or_insert(str(datetime.now()))
    p.people_counter = Person.query().count()
    p.put()
    return p


# ================================
# ================================
# ================================


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

def start(p, cmd, name, last_name, username):
    #logging.debug(p.name + _(' ') + cmd + _(' ') + str(p.enabled))
    #if (p.name.decode('utf-8') != name.decode('utf-8')):
    if (p.name != name):
        p.name = name
        p.put()
    #if (p.last_name.decode('utf-8') != last_name.decode('utf-8')):
    if (p.last_name != last_name):
        p.last_name = last_name
        p.put()
    if (p.username != username):
        p.username = username
        p.put()
    if not p.enabled:
        if cmd=='/start':
            p.enabled = True
            p.put()
        else: # START when diasbled
            return
    tell(p.chat_id, _("Hi") + _(' ') + p.name.encode('utf-8') + _('! ') + _("Are you a driver or a passenger?"),
    kb=[[emoij.CAR + _(' ') + _("Driver"), emoij.FOOTPRINTS + _(' ') + _("Passenger")],[emoij.NOENTRY + _(' ') + _("Abort")]])
    setState(p,0)

def getUsers():
    query = Person.query().order(-Person.last_mod)
    if query.get() is None:
        return "No users found"
    text = ""
    for p in query.iter():
        text = text + p.name + " (" + str(p.state) + ") " + get_date_string(p.last_mod) + _("\n")
    return text

def get_date_CET(date):
    if date is None: return None
    newdate = date + timedelta(hours=1)
    return newdate

def get_date_string(date):
    newdate = get_date_CET(date)
    time_day = str(newdate).split(" ")
    time = time_day[1].split(".")[0]
    day = time_day[0]
    return day + " " + time

def get_time_string(date):
    newdate = date + timedelta(hours=1)
    return str(newdate).split(" ")[1].split(".")[0]

def restartAllUsers(msg):
    qry = Person.query()
    for p in qry:
        #if (p.state is None): # or p.state>-1
        if (p.enabled): # or p.state>-1
            tell(p.chat_id, msg)
            restart(p)
            sleep(0.100) # no more than 10 messages per second

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

def resetLastNames():
    qry = Person.query()
    for p in qry:
        p.last_name = '-'
        p.put()

def resesetNames():
    qry = Person.query()
    for p in qry:
        p.name = p.name.encode('utf-8')
        p.put()

def checkEnabled():
    qry = Person.query(Person.enabled==True)
    for p in qry:
        try:
            tell(p.chat_id, "test")
        except urllib2.HTTPError, err:
            if err.code == 403:
                p.enabled = False
                p.put()
        sleep(0.035) # no more than 30 messages per second


def broadcast_driver_message(driver, msg):
    qry = Person.query(Person.location == driver.location, Person.state.IN([21, 22]))
    for p in qry:
        setLanguage(p.language)
        tell(p.chat_id, _("Message from " + driver.name) + _(': ') + msg)
        sleep(0.035) # no more than 30 messages per second
    setLanguage(driver.language)
    return qry.count()

def broadcast(msg, language='ALL'):
    qry = Person.query().order(-Person.last_mod)
    count = 0
    for p in qry:
        if (p.enabled):
            if language=='ALL' or p.language==language or (language=='EN' and p.language!='IT'):
                count += 1
                setLanguage(p.language)
                tell(p.chat_id, _("Listen listen...") + _(' ') + _(msg))
                sleep(0.100) # no more than 10 messages per second
    logging.debug('broadcasted to people ' + str(count))

def getInfoCount():
    setLanguage('IT')
    c = Person.query().count()
    msg = _("We are now") + _(' ') + str(c) + _(' ') + _("people subscribed to PickMeUp!") + _(' ') +\
          _("We want to get bigger and bigger!") + _(' ') + _("Invite more people to join us!")
    return msg

def getInfoAllRequestsOffers():
    setLanguage('IT')
    qryRideRequestCount = RideRequest.query().count()
    qryRideCount = Ride.query().count()
    qryRideCompletedCount = Ride.query(Ride.passengers_names_str != None).count()
    msg = _("Since the beginiing of time there were a total of ") + str(qryRideRequestCount) +\
          _(" ride requests and ") + str(qryRideCount) + _(" ride offers, of which ") +\
          str(qryRideCompletedCount) + _(" successfully completed!") + _("\n")
    return msg

def getInfoDay():
    setLanguage('IT')
    today = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
    qryRideRequest = RideRequest.query(RideRequest.passenger_last_seen > today)
    qryRide = Ride.query(Ride.start_daytime > today)
    qryRideCompleted = Ride.query(Ride.start_daytime > today and Ride.end_daytime > today)
    qryRideCompletedCount = qryRideCompleted.count()
    msg = _("Today there were a total of ") + str(qryRideRequest.count()) +\
          _(" ride requests and ") + str(qryRide.count()) + _(" ride offers, of which ") +\
          str(qryRideCompletedCount) + _(" successfully completed!") + _("\n")
    if qryRideCompletedCount>0:
        msg += _("Many thanks to all of you! " + emoij.CLAPPING_HANDS)
    else:
        msg += _("Let's make it happen! " + emoij.SMILING_FACE)
    return msg

def getInfoWeek():
    setLanguage('IT')
    lastweek = datetime.now() - timedelta(days=7)
    qryRideRequest = RideRequest.query(RideRequest.passenger_last_seen > lastweek)
    qryRide = Ride.query(Ride.start_daytime > lastweek)
    qryRideCompleted = Ride.query(Ride.start_daytime > lastweek and Ride.end_daytime > lastweek)
    qryRideCompletedCount = qryRideCompleted.count()
    msg = _("This week there were a total of ") + str(qryRideRequest.count()) +\
          _(" ride requests and ") + str(qryRide.count()) + _(" ride offers, of which ") +\
          str(qryRideCompletedCount) + _(" successfully completed!") + _("\n")
    msg += _("Many thanks to all of you! " + emoij.CLAPPING_HANDS)
    return msg


def tellmyself(p, msg):
    tell(p.chat_id, "Listen listen... " + msg)


def restart(person):
    tell(person.chat_id, _("Press START if you want to restart"), kb=[['START','HELP'], [_('SETTINGS'),_('DISCLAIMER')]]    )
    setStateLocation(person, -1, '-')


def putPassengerOnHold(passenger):
    tell(passenger.chat_id, _("Waiting for a driver..."), kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
    setState(passenger, 21)

def updateLastSeen(p):
    p.last_seen = datetime.now()
    p.put()

def assignNextTicketId(p):
    ticketId = None
    if (p.state>29 and p.state<40):
        #driver
        if p.location == FERMATA_POVO:
            ticketId = _('DP') + str(increaseQueueCounter(QUEUE_DRIVERS_COUNTER_POVO))
        else:
            ticketId = _('DT') + str(increaseQueueCounter(QUEUE_DRIVERS_COUNTER_TRENTO))
    else:
        #passenger
        if p.location == FERMATA_POVO:
            ticketId = _('PP') + str(increaseQueueCounter(QUEUE_PASSENGERS_COUNTER_POVO))
        else:
            ticketId = _('PT') + str(increaseQueueCounter(QUEUE_PASSENGERS_COUNTER_TRENTO))
    p.ticket_id = ticketId
    p.put()
    return ticketId

def checkExpiredUsers():
    checkExpiredDrivers()
    checkExpiredPassengers()

def checkExpiredDrivers():
    for location in [FERMATA_TRENTO,FERMATA_POVO]:
        qry = Person.query(Person.location == location, Person.state.IN([32,33]))
        oldDrivers = {
            32: [],
            33: []
        }
        for d in qry:
            if d.state==32: #picking up drivers
                if (datetime.now() >= d.last_seen + timedelta(minutes=MAX_PICKUP_DRIVER_MIN)):
                    oldDrivers[d.state].append(d)
            else:
                if (datetime.now() >= d.last_seen + timedelta(minutes=MAX_COMPLETE_DRIVER_MIN)):
                    oldDrivers[d.state].append(d)
        for d in oldDrivers[32]:
            setLanguage(d.language)
            tell(d.chat_id, _("The ride offer has been aborted: you were expected to give a ride some time ago!"))
            abortRideOffer(d, True)
            removeDriver(d)
        for d in oldDrivers[33]:
            setLanguage(d.language)
            tell(d.chat_id, _("The ride has been completed automatically: you were supposed to arrive some time ago!"))
            endRide(d,auto_end=True)
            removeDriver(d)
            decreaseRides(d) # update counter current ride of -1

def checkExpiredPassengers():
    for location in [FERMATA_TRENTO,FERMATA_POVO]:
        qry = Person.query(Person.location == location, Person.state.IN([21, 22]))
        oldPassengers = []
        for p in qry:
            if (datetime.now() >= p.last_seen + timedelta(minutes=MAX_WAITING_PASSENGER_MIN)):
                oldPassengers.append(p)
        for p in oldPassengers:
            setLanguage(p.language)
            tell(p.chat_id, _("The ride request has been aborted: ") +
                 _("after some time the requests automatically expire.") + _("\n") +
                 _("We believe and hope you have already reached your destination, \
                   otherwise feel free to start another request")
            )
            abortRideRequest(p, auto_end=True)
            removePassenger(p)


def check_available_drivers(passenger):
    # a passenger is at a certain location and we want to check if there is a driver engaged
    qry = Person.query(Person.location == passenger.location, Person.state.IN([32,33]))
    if (Person.query(Person.location == passenger.location, Person.state.IN([21,22])).count()==0):
        for d in qry:
            if (d.state==32):
                setLanguage(d.language)
                tell(d.chat_id, _("There is now a passenger waiting at the stop " + emoij.PEDESTRIAN),
                    kb=[[_("List Passengers"), _("Send Message")],[emoij.NOENTRY + _(' ') + _("Abort")]])
    setLanguage(passenger.language)

    if (qry.count() > 0):
        tell(passenger.chat_id, _("There is a driver coming!"),
              kb=[[_('List Drivers'), _('Got the Ride!')],[emoij.NOENTRY + _(' ') + _("Abort")]])
        setState(passenger, 22)
    else:
        putPassengerOnHold(passenger)
        # state = 22


def engageDriver(d, min):
    d.last_seen = datetime.now() + timedelta(minutes=min)
    qry = Person.query(Person.location == d.location, Person.state.IN([21, 22]))
    for p in qry:
        if (p.state==21):
            setState(p, 22)
        setLanguage(p.language)
        tell(p.chat_id, _("A driver is coming: ") + d.name.encode('utf-8') +
             _(" expected at ") + get_time_string(d.last_seen).encode('utf-8') +
             _(" (id: ") + d.ticket_id.encode('utf-8') + _(")"),
             kb=[[_("List Drivers"), _("Got the Ride!")],[emoij.NOENTRY + _(' ') + _("Abort")]])
    setLanguage(d.language)
    setState(d, 32)

def check_available_passenger(driver):
    # a driver is availbale for a location and we want to check if there are passengers bored or engaged
    #driver.last_seen = datetime.now()
    qry = Person.query(Person.location == driver.location, Person.state.IN([21, 22]))
    counter = qry.count()
    return counter > 0

def listDrivers(passenger):
    qry = Person.query(Person.location == passenger.location, Person.state.IN([32,33])) #.order(-Person.last_mod)
    if qry.get() is None:
        return _("No drivers found in your location")
    else:
        text = ""
        for d in qry:
            text = text + d.name.encode('utf-8') + _(" expected at ") + get_time_string(d.last_seen) +\
                   _(" (id: ") + d.ticket_id + _(")") + _("\n")
        return text

def listPassengers(driver):
    qry = Person.query(Person.location == driver.location, Person.state.IN([21, 22, 23])) #.order(-Person.last_mod)
    if qry.get() is None:
        return _("No passengers needing a ride found in your location")
    else:
        text = ""
        for p in qry:
            text = text + p.name.encode('utf-8') + _(" waiting since ") + get_time_string(p.last_seen) +\
                   _(" (id: ") + p.ticket_id + _(")") + _("\n")
        return text


def listAllDrivers():
    qry = Person.query().filter(Person.state.IN([30, 31, 32, 33]))
    if qry.get() is None:
        return "No drivers found"
    else:
        #qry = qry.order(-Person.last_mod)
        text = ""
        for d in qry:
            text = text + d.name.encode('utf-8') + _(' ') + d.location + _(" (") + str(d.state) + \
                   _(") ") + get_time_string(d.last_seen) + _("\n")
        return text


def listAllPassengers():
    qry = Person.query().filter(Person.state.IN([21, 22, 23]))
    if qry.get() is None:
        return _("No passangers found")
    else:
        #qry = qry.order(-Person.last_mod)
        text = ""
        for p in qry:
            text = text + p.name.encode('utf-8') + _(' ') + p.location + " (" + str(p.state) + ") " + get_time_string(p.last_seen) + _("\n")
        return text

def removePassenger(p, driver=None):
    loc = p.location
    restart(p)
    qry = Person.query().filter(Person.state.IN([21, 22]), Person.location==loc)
    if qry.get() is None:
        # there are no more passengers in that location
        qry = Person.query().filter(Person.state.IN([32]), Person.location==loc)
        for d in qry:
            if d!=driver:
                setLanguage(d.language)
                tell(d.chat_id, _("Oops... there are no more passengers waiting!"))
                #putDriverOnHold(d)
                #restart(d)
        setLanguage(p.language)
    updateDashboard()

def removeDriver(d):
    loc = d.location
    restart(d)
    qry = Person.query().filter(Person.state.IN([32,33]), Person.location==loc)
    if qry.get() is None:
        # there are no more drivers in that location
        qry = Person.query().filter(Person.state == 22, Person.location==loc)
        for p in qry:
            setLanguage(p.language)
            tell(p.chat_id, _("Oops... the driver(s) is no longer available!"))
            putPassengerOnHold(p)
        setLanguage(d.language)

def askToSelectDriverByNameAndId(p):
    qry = Person.query().filter(Person.state.IN([32,33]), Person.location==p.location)
    if qry.get() is None:
        tell(p.chat_id, _("Thanks, have a good ride!")) # cannot ask you which driver cause they are all gone
        removePassenger()
    else:
        buttons = []
        for d in qry:
            buttons.append([d.name.encode('utf-8') + _(" (id: ") + d.ticket_id + _(")")])
        buttons.append([_("Someone else")])
        tell(p.chat_id, _("Great, which driver gave you a ride?"), kb=buttons)
        setState(p, 23)

def getDriverByLocAndNameAndId(loc, name_text):
    id_str = name_text[name_text.index("(id:")+5:-1]
    qry = Person.query().filter(Person.location==loc, Person.ticket_id==id_str)
    return qry.get()

def tell_katja(msg):
    tell(114258373, msg)


def setLanguage(langId):
    lang = LANGUAGES[langId] if langId is not None else LANGUAGES['IT']
    gettext.translation('PickMeUp', localedir='locale', languages=[lang]).install()

def tell_katja_test():
    try:
        tell(114258373, 'test')
    except urllib2.HTTPError, err:
        if err.code == 403:
            e = Person.query(Person.chat_id==114258373).get()
            e.enabled = False
            e.put()

def tell_masters(msg):
    for id in key.MASTER_CHAT_ID:
        tell(id, msg)

def tell_fede(msg):
    for i in range(100):
        tell(key.FEDE_CHAT_ID, "prova " + str(i))
        sleep(0.1)


def tell(chat_id, msg, kb=None, hideKb=True):
    try:
        if kb:
            resp = urllib2.urlopen(BASE_URL + 'sendMessage', urllib.urlencode({
                'chat_id': chat_id,
                'text': msg, #.encode('utf-8'),
                'disable_web_page_preview': 'true',
                #'reply_to_message_id': str(message_id),
                'reply_markup': json.dumps({
                    #'one_time_keyboard': True,
                    'resize_keyboard': True,
                    'keyboard': kb,  # [['Test1','Test2'],['Test3','Test8']]
                    'reply_markup': json.dumps({'hide_keyboard': True})
                }),
            })).read()
        else:
            if hideKb:
                resp = urllib2.urlopen(BASE_URL + 'sendMessage', urllib.urlencode({
                    'chat_id': str(chat_id),
                    'text': msg, #.encode('utf-8'),
                    #'disable_web_page_preview': 'true',
                    #'reply_to_message_id': str(message_id),
                    'reply_markup': json.dumps({
                        #'one_time_keyboard': True,
                        'resize_keyboard': True,
                        #'keyboard': kb,  # [['Test1','Test2'],['Test3','Test8']]
                        'reply_markup': json.dumps({'hide_keyboard': True})
                }),
                })).read()
            else:
                resp = urllib2.urlopen(BASE_URL + 'sendMessage', urllib.urlencode({
                    'chat_id': str(chat_id),
                    'text': msg, #.encode('utf-8'),
                    #'disable_web_page_preview': 'true',
                    #'reply_to_message_id': str(message_id),
                    'reply_markup': json.dumps({
                        #'one_time_keyboard': True,
                        'resize_keyboard': True,
                        #'keyboard': kb,  # [['Test1','Test2'],['Test3','Test8']]
                        'reply_markup': json.dumps({'hide_keyboard': False})
                }),
                })).read()
        logging.info('send response: ')
        logging.info(resp)
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = Person.query(Person.chat_id==chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.name.encode('utf-8') + _(' ') + str(chat_id))

# ================================
# ================================
# ================================

class Ride(ndb.Model):
    driver_name = ndb.StringProperty()
    driver_id = ndb.IntegerProperty()
    driver_ticket_id = ndb.StringProperty()
    start_daytime = ndb.DateTimeProperty()
    abort_daytime = ndb.DateTimeProperty()
    auto_abort = ndb.BooleanProperty()
    minutes_to_pickup = ndb.IntegerProperty()
    start_location = ndb.StringProperty()
    passengers_ids = ndb.JsonProperty()
    passengers_names = ndb.JsonProperty()
    passengers_names_str = ndb.StringProperty()
    end_daytime = ndb.DateTimeProperty()
    auto_end = ndb.BooleanProperty()

def getRideKey(driver):
    key = str(driver.chat_id) + '_' + str(driver.last_seen)
    return key

def recordRide(driver, minutes_to_pickup):
    key = getRideKey(driver)
    r = Ride.get_or_insert(key)
    r.driver_name = driver.name
    r.driver_id = driver.chat_id
    r.driver_ticket_id = driver.ticket_id
    r.start_daytime = datetime.now()
    r.minutes_to_pickup = minutes_to_pickup
    r.start_location = driver.location
    r.passengers_ids = [] #ids
    r.passengers_names = [] #names
    k = r.put()
    #logging.debug('New ride. Key:' + str(k))
    return r

def abortRideOffer(driver, auto_end):
#    logging.debug('aborted requested by ' + passenger.name)
    key = getRideKey(driver)
    r = Ride.get_or_insert(key)
    r.abort_daytime = datetime.now()
    r.auto_abort = auto_end
    r.put()

def addPassengerInRide(driver, passenger):
    key = getRideKey(driver)
    ride = ndb.Key(Ride, key).get()
    ride.passengers_ids.append(passenger.chat_id)
    ride.passengers_names.append(passenger.name)
    ride.put()

def endRide(driver, auto_end):
    key = getRideKey(driver)
    ride = ndb.Key(Ride, key).get()
    ride.end_daytime = datetime.now()
    ride.auto_end = auto_end
    ride.passengers_names_str = str(ride.passengers_names)
    ride.put()
    if tell_completed:
        duration_sec = (ride.end_daytime - ride.start_daytime).seconds
        duration_min_str  = str(duration_sec/60) + ":" + str(duration_sec%60)
        tell(key.TIRAMISU_CHAT_ID, "Passenger completed! Driver: " + driver.name +
                     ". Passengers: " + ride.passengers_names_str + ". Duration (min): " + duration_min_str)


# ================================
# ================================
# ================================

class RideRequest(ndb.Model):
    passenger_name = ndb.StringProperty()
    passenger_id = ndb.IntegerProperty()
    passenger_last_seen = ndb.DateTimeProperty()
    passenger_location = ndb.StringProperty()
    passenger_ticket_id = ndb.StringProperty()
    driver_name = ndb.StringProperty()
    driver_id = ndb.IntegerProperty()
    abort_time = ndb.DateTimeProperty()
    auto_aborted = ndb.BooleanProperty()

def getRideRequestKey(passenger):
    key = str(passenger.chat_id) + '_' + str(passenger.last_seen)
    return key

def recordRideRequest(passenger):
    key = getRideRequestKey(passenger)
    request = RideRequest.get_or_insert(key)
    request.passenger_name = passenger.name
    request.passenger_id = passenger.chat_id
    request.passenger_last_seen = passenger.last_seen
    request.passenger_location = passenger.location
    request.passenger_ticket_id = passenger.ticket_id
    k = request.put()
    #logging.debug('New ride. Key:' + str(k))
    return request

def confirmRideRequest(passenger, driver):
    key = getRideRequestKey(passenger)
    request = RideRequest.get_or_insert(key)
    request.driver_name = driver.name if driver is not None else 'Other'
    request.driver_id = driver.chat_id if driver is not None else -1
    request.put()

def abortRideRequest(passenger, auto_end):
#    logging.debug('aborted requested by ' + passenger.name)
    key = getRideRequestKey(passenger)
    request = RideRequest.get_or_insert(key)
    request.abort_time = datetime.now()
    request.auto_aborted = auto_end
    request.put()

# ================================
# ================================
# ================================

class PollAnswer(ndb.Model):
    poll_title = ndb.StringProperty()
    user_id = ndb.IntegerProperty()
    user_name = ndb.StringProperty()
    user_lastname = ndb.StringProperty()
    submission_datetime = ndb.DateTimeProperty()
    answer = ndb.StringProperty()

def submittPollAnswer(id, name, lastname, title, answer):
    item = PollAnswer.get_or_insert(str(id))
    item.poll_title = title
    item.user_id = id
    item.user_name = name
    item.user_lastname = lastname
    item.submission_datetime = datetime.now()
    item.answer = answer
    item.put()


# ================================
# ================================
# ================================

TOKEN_DURATION_MIN = 100
TOKEN_DURATION_SEC = TOKEN_DURATION_MIN*60

class Token(ndb.Model):
    token_id = ndb.StringProperty()
    start_daytime = ndb.DateTimeProperty()

def createToken():
    now = datetime.now()
    token_id = channel.create_channel(str(now), duration_minutes=TOKEN_DURATION_MIN)
    token = Token.get_or_insert(token_id)
    token.start_daytime = now
    token.token_id = token_id
    token.put()
    return token_id

def updateDashboard():
    #logging.debug('updateDashboard')
    data = getDashboardData()
    qry = Token.query()
    removeKeys = []
    now = datetime.now()
    for t in qry:
        duration_sec = (now - t.start_daytime).seconds
        if (duration_sec>TOKEN_DURATION_SEC):
            removeKeys.append(t.token_id)
        else:
            channel.send_message(t.token_id, json.dumps(data))
    for k in removeKeys:
        ndb.Key(Token, k).delete()

# ================================
# ================================
# ================================

class MeHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(BASE_URL + 'getMe'))))

class TiramisuHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        #tell(key.MASTER_CHAT_ID, msg = "Lottery test")

class InfouserTiramisuHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        tell(key.TIRAMISU_CHAT_ID, getInfoCount())

class InfouserAllHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        broadcast(getInfoCount())

class DayPeopleCountHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        addPeopleCount()

class InfodayTiramisuHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        tell(key.TIRAMISU_CHAT_ID, getInfoDay())

class InfodayAllHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        broadcast(getInfoWeek())

class ResetCountersHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        resetCounter()

class DashboardHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        data = getDashboardData()
        token_id = createToken()
        data['token'] = token_id
        data['today_events'] = json.dumps(getTodayTimeline())
        logging.debug('Requsts: ' + str(data['today_events']))
        template = DASHBOARD_DIR_ENV.get_template('PickMeUp.html')
        logging.debug("Requested Dashboard. Created new token.")
        self.response.write(template.render(data))

class GetTokenHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        token_id = createToken()
        logging.debug("Token handler. Created a new token.")
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps({'token': token_id}))

class DashboardConnectedHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        client_id = self.request.get('from')
        logging.debug("Channel connection request from client id: " + client_id)

class DashboardDisconnectedHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        client_id = self.request.get('from')
        logging.debug("Channel disconnection request from client id: " + client_id)

class CheckExpiredUsersHandler(webapp2.RequestHandler):
    def get(self):
        checkExpiredUsers();

class GetUpdatesHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(BASE_URL + 'getUpdates'))))


class SetWebhookHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        url = self.request.get('url')
        if url:
            self.response.write(
                json.dumps(json.load(urllib2.urlopen(BASE_URL + 'setWebhook', urllib.urlencode({'url': url})))))

# ================================
# ================================
# ================================


class WebhookHandler(webapp2.RequestHandler):

    def post(self):
        urlfetch.set_default_fetch_deadline(60)
        body = json.loads(self.request.body)
        logging.info('request body:')
        logging.info(body)
        self.response.write(json.dumps(body))

        # update_id = body['update_id']
        message = body['message']
        message_id = message.get('message_id')
        # date = message.get('date')
        if "text" not in message:
            return;
        text = message.get('text').encode('utf-8')
        # fr = message.get('from')
        if "chat" not in message:
            return;
        chat = message['chat']
        chat_id = chat['id']
        if "first_name" not in chat:
            return;
        name = chat["first_name"].encode('utf-8')
        last_name = chat["last_name"].encode('utf-8') if "last_name" in chat else "-"
        username = chat["username"] if "username" in chat else "-"

        def reply(msg=None, kb=None, hideKb=True):
            tell(chat_id, msg, kb, hideKb)

        p = ndb.Key(Person, str(chat_id)).get()

        setLanguage(p.language if p is not None else None)

        instructions =  (_("I\'m your Trento <-> Povo travelling assistant.") + _("\n\n") +
                        _("You can press START to get or offer a ride") + _("\n") +
                        _("You can press HELP to see this message again") + _("\n") +
                        _("You can press SETTING to change the settings (e.g., language)") + _("\n\n") +
                        _("You can visit our website at http://pickmeup.trentino.it\
                        or read the pdf instructions at http://tiny.cc/pickmeup_info") + _("\n\n") +
                        _("If you want to join the discussion about this initiative \
                        come to the tiramisu group at the following link: \
                        https://telegram.me/joinchat/B8zsMQBtAYuYtJMj7qPE7g")) #.encode('utf-8')

        disclaimer =   (_("PickMeUp is a dynamic carpooling system, like BlaBlaCar but within the city.") + _("\n") +
                        _("It is currently  under testing on the Trento-Povo route.") + _("\n\n") +
                        _("WARNINGS:") + _("\n") +
                        _("Drivers: please offer rides before starting the ride. "
                          "DO NOT use your phone while you drive.") + _("\n") +
                        _("Passengers: please ask for rides when you are at the bus stop. ") +
                        _("Be kind with the driver and the other passengers.") + _("\n\n") +
                        _("PickMeUp is a non-profit service and it is totally money-free between passengers and drivers.") + _("\n") +
                        _("The current version is under testing: ") +
                        _("no review system has been implemented yet and ride traceability is still limited. ") + _("\n\n") +
                        _("PickMeUp developers decline any responsibility for the use of the service."))

        if p is None:
            # new user
            tell_masters("New user: " + name)
            p = addPerson(chat_id, name)
            if text == '/help':
                reply(instructions)
            elif text in ['/start','START']:
                start(p, text, name, last_name, username)
                # state = 0
            else:
                reply(_("Hi") + _(' ') + name + ", " + _("welcome!"))
                reply(instructions)
        else:
            # known user
            if text=='/state':
              reply("You are in state " + str(p.state) + ": " + STATES[p.state]);
            elif p.state == -1:
                # INITIAL STATE
                if text in ['/help','HELP']:
                    reply(instructions)
                elif text == _('DISCLAIMER'):
                    reply(disclaimer)
                elif text in ['/start','START']:
                    start(p, text, name, last_name, username)
                    # state = 0
                elif text == _('SETTINGS'):
                    reply(_("Settings options"),
                          kb=[[_('LANGUAGE')], [_('INFO USERS'),_('DAY SUMMARY')],[emoij.NOENTRY + _(' ') + _("Abort")]])
                    setState(p, 90)
                elif text == '/users':
                    reply(getUsers())
                elif text == '/alldrivers':
                    reply(listAllDrivers())
                elif text == '/allpassengers':
                    reply(listAllPassengers())
                elif chat_id in key.MASTER_CHAT_ID:
                    if text == '/resetusers':
                        logging.debug('reset user')
                        c = resetNullStatesUsers()
                        reply("Reset states of users: " + str(c))
                        #restartAllUsers('Less spam, new interface :)')
                        #resetLastNames()
                        #resetEnabled()
                        #resetLanguages()
                        #resesetNames()
                    elif text=='/infocount':
                        reply(getInfoCount())
                    elif text=='/checkenabled':
                        checkEnabled()
                    elif text == '/resetcounters':
                        resetCounter()
                    elif text == '/test':
                        logging.debug('test')
                        reply("/opzione1 bfdslkjfdsjaklfdj")
                        reply("/opzione2 ju39jrkek")
                        reply("/opzione3 349jfndkkj")
                        #tell_katja_test()
                        #updateDashboard()
                        #reply('test')
                        #reply(getInfoDay())
                        #tell_masters('test')
                        #reply(getInfoWeek())
                        #testQueue()
                        #msg = "Prova di broadcasting.\n" + \
                        #      "Se lo ricevi una sola volta vuol dire che da ora in poi funziona :D (se no cerchiamo di risolverlo)\n\n" + \
                        #      "Broadcasting test.\n" + \
                        #      "If you receive it only once it means that now it works correctly :D (if not we will try to fix it)"
                        #msg = "Last  broadcast test for today :P"
                        #broadcastQueue(msg)
                        #deferred.defer(tell_fede, "Hello, world!")
                    elif text == '/getAllInfo':
                        reply(getInfoAllRequestsOffers())
                    elif text.startswith('/broadcast ') and len(text)>11:
                        msg = text[11:] #.encode('utf-8')
                        deferred.defer(broadcast, msg)
                    elif text.startswith('/broadcast_it ') and len(text)>14:
                        msg = text[14:] #.encode('utf-8')
                        deferred.defer(broadcast, msg, 'IT')
                    elif text.startswith('/broadcast_en ') and len(text)>14:
                        msg = text[14:] #.encode('utf-8')
                        deferred.defer(broadcast, msg, 'EN')
                    elif text.startswith('/self ') and len(text)>6:
                        msg = text[6:] #.encode('utf-8')
                        tellmyself(p,msg)
                    else:
                        reply('Sorry, I only understand /help /start '
                              '/users and other secret commands...')
                    #setLanguage(d.language)
                else:
                    reply(_("Sorry, I don't understand you"))
                    restart(p)
            #kb=[[emoij.CAR + _(' ') + _("Driver"), emoij.FOOTPRINTS + _(' ') + _("Passenger")],[emoij.NOENTRY + _(' ') + _("Abort")]])
            elif p.state == 0:
                # AFTER TYPING START
                #logging.debug(text, type(text))
                if text.endswith(_("Passenger")):
                #if text == emoij.FOOTPRINTS + _(' ') + _("Passenger"):
                    setState(p, 20)
                    setType(p, text)
                    reply(_("Hi! I can try to help you to get a ride. Which bus stop are you at?"),
                          kb=[[FERMATA_TRENTO, FERMATA_POVO],[emoij.NOENTRY + _(' ') + _("Abort")]])
                elif text.endswith(_("Driver")):
                #elif text == emoij.CAR + _(' ') + _("Driver"):
                    setState(p, 30)
                    setType(p, text)
                    reply(_("Hi! Glad you can give a ride. Where can you pick up passengers?"),
                          kb=[[FERMATA_TRENTO, FERMATA_POVO],[emoij.NOENTRY + _(' ') + _("Abort")]])
                elif text.endswith(_("Abort")):
                #elif text == emoij.NOENTRY + _(' ') + _("Abort"):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else: reply(_("Sorry, I don't understand you"))
            elif p.state == 20:
                # PASSANGERS, ASKED FOR LOCATION
                if text in [FERMATA_POVO,FERMATA_TRENTO]:
                    setLocation(p, text)
                    updateLastSeen(p)
                    check_available_drivers(p)
                    assignNextTicketId(p)
                    reply(_("Your passenger ID is: ") + p.ticket_id.encode('utf-8'))
                    recordRideRequest(p)
                    updateDashboard()
                    # state = 21 or 22 depending if driver available
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else: reply(_("Sorry, I don't understand you") + _(' ') +
                            FERMATA_TRENTO + _(' ') + _("or") + _(' ') + FERMATA_POVO + '?')
            elif p.state == 21:
                # PASSENGERS IN A LOCATION WITH NO DRIVERS
                if text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    abortRideRequest(p, auto_end=False)
                    removePassenger(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 22:
                # PASSENGERS NOTIFIED THERE IS A DRIVER
                if text == _("Got the Ride!"):
                    askToSelectDriverByNameAndId(p)
                    #state = 23
                elif text == _("List Drivers"):
                    reply(listDrivers(p))
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    abortRideRequest(p, auto_end=False)
                    removePassenger(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 23:
                # PASSENGERS WHO JUST CONFIRMED A RIDE
                if text == _("Someone else"):
                    reply(_("Thanks, have a good ride!"))
                    #recordRide('Other',-1, p.last_seen,p.location)
                    #addPassengerInRide(None, p)
                    increasePassengerRide(p) # increase counter tot passengers in ride of 1
                    increaseRides(p) # update counter tot and current ride of 1
                    confirmRideRequest(p, None)
                    removePassenger(p)
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    abortRideRequest(p, auto_end=False)
                    removePassenger(p)
                    # state = -1
                else:
                    d = getDriverByLocAndNameAndId(p.location, text)
                    if d is not None:
                        confirmRideRequest(p, d)
                        reply(_("Great! Many thanks to") + _(' ') + d.name.encode('utf-8') + "!")
                        setLanguage(d.language)
                        addPassengerInRide(d, p)
                        tell(d.chat_id, p.name.encode('utf-8') + _(' ') + _("confirmed you gave him/her a ride!"),
                             kb=[[_("List Passengers"), _("Reached Destination!")]]) #[emoij.NOENTRY + _(' ') + _("Abort")]
                        setLanguage(p.language)
                        if (d.state==32):
                            setState(d, 33)
                            increaseRides(d) # update counter tot and current ride of 1
                        increasePassengerRide(p)
                        removePassenger(p, driver=d)
                        # passenger state = -1
                    else:
                        reply(_("Name of driver not correct, try again."))
            elif p.state == 30:
                # DRIVERS, ASKED FOR LOCATION
                if text in [FERMATA_POVO,FERMATA_TRENTO]:
                    setLocation(p, text)
                    # CHECK AND NOTIFY PASSENGER WAIING IN THE SAME LOCATION
                    reply(_("In how many minutes will you be there?"),
                          kb=[['0','2','5'],['10','15','20'],[emoij.NOENTRY + _(' ') + _("Abort")]])
                    setState(p, 31)
                    # state = 31
                elif text.endswith(_("Abort")):
                    reply(_("Passage offer has been aborted."))
                    restart(p);
                    # state = -1
                else: reply("Eh? " + FERMATA_TRENTO + _("or") + FERMATA_POVO + "?")
            elif p.state == 31:
                # DRIVERS ASEKED FOR TIME
                if text in ['0','2','5','10','15','20']:
                    if check_available_passenger(p):
                        reply(_("There is someone waiting for you ") + emoij.PEDESTRIAN + '\n' +
                              _("Have a nice trip!") + emoij.SMILING_FACE,
                              kb=[[_("List Passengers"), _("Send Message")],[emoij.NOENTRY + _(' ') + _("Abort")]])
                    else:
                        reply(_("There is currently nobody there but if somebody arrives \
                        we will notify you and will let them know you are coming.") + _("\n") +
                        _("Have a nice trip! ") + emoij.SMILING_FACE,
                        kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
                    setState(p, 32)
                    # state = 31
                    assignNextTicketId(p)
                    reply(_("Your driver ID is: ") + p.ticket_id.encode('utf-8'))
                    engageDriver(p, int(text))
                    recordRide(p, int(text))
                elif text.endswith(_("Abort")):
                    reply(_("Passage offer has been aborted."))
                    restart(p);
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 32:
                # DRIVERS WHO HAS LEFT
                if text == _("List Passengers"):
                    reply(listPassengers(p))
                elif text == (_("Send Message")):
                    reply(_("Please type a short message which will be sent to all passenger waiting at your location"),
                        kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                    setState(p, 325)
                elif text.endswith(_("Abort")):
                    reply(_("Passage offer has been aborted."))
                    abortRideOffer(p, False)
                    removeDriver(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))# (" + text + ")")
            elif p.state == 325:
                if not text.endswith(_("Back")):
                    count = broadcast_driver_message(p, text)
                    reply(_("Sent message to ") + str(count) + _(" people"))
                if check_available_passenger(p):
                    reply(_("There is someone waiting for you ") + emoij.PEDESTRIAN,
                          kb=[[_("List Passengers"), _("Send Message")],[emoij.NOENTRY + _(' ') + _("Abort")]])
                else:
                    reply(_("Oops... there are no more passengers waiting!"),
                          kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
                    # all passangers have left while driver was typing
                setState(p, 32)
            elif p.state == 33:
                # DRIVER WHO HAS JUST BORDED AT LEAST A PASSANGER
                if text == _("List Passengers"):
                    reply(listPassengers(p))
                elif text == _("Reached Destination!"):
                    reply(_("Great, thanks!") + _(' ') + emoij.CLAPPING_HANDS)
                    decreaseRides(p) # update counter current ride of -1
                    endRide(p,auto_end=False)
                    removeDriver(p)
                    # state -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 90:
                if text.endswith(_("Abort")):
                    restart(p)
                    # state = -1
                elif text==_('LANGUAGE'):
                    reply(_("Choose the language"),
                          kb=[[emoij.FLAG_IT + _(' ') + "IT", emoij.FLAG_EN + _(' ') + "EN", emoij.FLAG_RU + _(' ') + "RU"],
                              [emoij.FLAG_DE + _(' ') + "DE", emoij.FLAG_FR + _(' ') + "FR", emoij.FLAG_PL + _(' ') + "PL"],
#                             [emoij.FLAG_NL + _(' ') + "NL"
                              [emoij.NOENTRY + _(' ') + _("Abort")]])
                    setState(p, 91)
                elif text==_('INFO USERS'):
                    reply(getInfoCount())
                    restart(p)
                    # state = -1
                elif text==_('DAY SUMMARY'):
                    reply(getInfoDay())
                    restart(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 91:
                if text.endswith(_("Abort")):
                    restart(p)
                    # state = -1
                elif len(text)>2 and text[-2:] in ['IT','EN','FR','DE','RU','NL','PL']:
                    l = text[-2:]
                    p.language = l
                    p.put()
                    gettext.translation('PickMeUp', localedir='locale', languages=[LANGUAGES[l]]).install()
                    restart(p)
                else:
                    reply(_("Sorry, I don't understand you"))
            else:
                reply(_("Something is wrong with your state (") + str(p.state).encode('utf-8') +
                      _("). Please contact the admin at pickmeupbot@gmail.com"))

app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    ('/dashboard', DashboardHandler),
#    ('/_ah/channel/connected/', DashboardConnectedHandler),
#    ('/_ah/channel/disconnected/', DashboardDisconnectedHandler),
    ('/notify_token', GetTokenHandler),
    ('/updates', GetUpdatesHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/webhook', WebhookHandler),
    ('/infousers_tiramisu', InfouserTiramisuHandler),
    ('/infouser_weekly_all', InfouserAllHandler),
    ('/infoday_tiramisu', InfodayTiramisuHandler),
    ('/infoweek_all', InfodayAllHandler),
    ('/resetcounters', ResetCountersHandler),
    ('/checkExpiredUsers', CheckExpiredUsersHandler),
    ('/tiramisulottery', TiramisuHandler),
    ('/dayPeopleCount', DayPeopleCountHandler),
], debug=True)
