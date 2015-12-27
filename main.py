#import json
import json
import logging
import urllib
import urllib2
from time import sleep
import time_util
# import requests

import re
import key
import emoij
import counter
import person
from person import Person
import date_counter
import ride
from ride import Ride
import ride_request
from ride_request import RideRequest
import itinerary
import polls
from polls import PollAnswer
import token_factory

# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.api import channel
from google.appengine.api import taskqueue
from google.appengine.ext import deferred
from google.appengine.api import mail
from google.appengine.ext.db import datastore_errors


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

STATES = {
    -2:   'Initial without Start',
    -1:   'Initial with Start',
    0:    'Started',
    20:   'Passenger Asked For Location',
    21:   'Passenger with no driver matching journey',
    22:   'Passenger with driver(s) matching journey',
    23:   'Passenger who has confirmed a ride',
    30:   'Driver asked for location',
    31:   'Driver asked for time',
    32:   'Driver without borded passengers',
    325:  'Driver sending message',
    33:   'Driver with boarded passengers',
    80:   'Info',
    81:   'Info -> SEARCH BUS STOPS',
    82:   'Info -> SEND FEEDBACK',
    90:   'Settings',
    91:   'Settings -> Language',
    92:   'Settings -> Terms and Conditions',
    93:   'Settings -> Itinerary (Advanced)',
    931:  'Settings -> Itinerary (Advanced) -> Start Location',
    9311: 'Settings -> Itinerary (Advanced) -> Start Location -> Check',
    932:  'Settings -> Itinerary (Advanced) -> End Location',
    9321: 'Settings -> Itinerary (Advanced) -> End Location -> Check',
    933:  'Settings -> Itinerary (Advanced) -> Mid Points Going',
    9331: 'Settings -> Itinerary (Advanced) -> Mid Points Going -> Check',
    934:  'Settings -> Itinerary (Advanced) -> Mid Points Back',
    9341: 'Settings -> Itinerary (Advanced) -> Mid Points Back -> Check',
    935:  'Settings -> Itinerary (Base)',
    94:   'Settings -> Notification',
}

LANGUAGES = {'IT': 'it_IT',
             'EN': 'en',
             #'FR': 'fr_FR',
             #'DE': 'de',
             #'NL': 'nl',
             #'PL': 'pl',
             #'RU': 'ru'
             }

LANGUAGE_FLAGS = {
    "IT": emoij.FLAG_IT,
    "EN": emoij.FLAG_EN,
    #"RU", emoij.FLAG_RU,
    #"DE", emoij.FLAG_DE,
    #"FR", emoij.FLAG_FR,
    #"PL", emoij.FLAG_PL
}



MAX_WAITING_PASSENGER_MIN = 25
MAX_PICKUP_DRIVER_MIN = 15
MAX_COMPLETE_DRIVER_MIN = 20

# ================================
# ================================
# ================================

def getTodayTimeline():

    todayEvents = {itinerary.FERMATA_TRENTO: {}, itinerary.FERMATA_POVO: {}}

    today = time_util.get_today()
    #today = today - timedelta(days=1)

    for loc in [itinerary.FERMATA_TRENTO, itinerary.FERMATA_POVO]:

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




# ================================
# ================================
# ================================

def registerUser(p, name, last_name, username):
    #logging.debug('registering user')
    #logging.debug(p.name + _(' ') + cmd + _(' ') + str(p.enabled))
    #if (p.name.decode('utf-8') != name.decode('utf-8')):
    modified = False
    if p.name != name:
        p.name = name
        modified = True
    #if (p.last_name.decode('utf-8') != last_name.decode('utf-8')):
    if p.last_name != last_name:
        p.last_name = last_name
        modified = True
    if p.username != username:
        p.username = username
        modified = True
    if not p.enabled:
        p.enabled = True
        modified = True
    if modified:
        p.put()



def start(p):
    tell(p.chat_id, _("Hi") + _(' ') + p.name.encode('utf-8') + _('! ') + _("Are you a driver or a passenger?"),
    kb=[[emoij.CAR + _(' ') + _("Driver"), emoij.FOOTPRINTS + _(' ') + _("Passenger")],[emoij.NOENTRY + _(' ') + _("Abort")]])
    person.setNotified(p,False)
    person.setState(p,0)

def getUsers():
    query = Person.query() #.order(-Person.last_mod)
    if query.get() is None:
        return "No users found"
    text = ""
    for p in query.iter():
        text = text + p.name + " (" + str(p.state) + ") " + time_util.get_date_string(p.last_mod) + _("\n")
    return text

def restartAllUsers(msg):
    qry = Person.query()
    count = 0
    for p in qry:
        #if (p.state is None): # or p.state>-1
        if (p.enabled): # or p.state>-1
            if (time_util.ellapsed_min(p.last_mod)>60):
                count +=1
                if msg:
                    tell(p.chat_id, msg)
                restart(p)
                sleep(0.100) # no more than 10 messages per second
    logging.debug("Succeffully restarted users: " + str(count))
    return count

def restartLanguages():
    qry = Person.query(ndb.AND(Person.language != 'IT', Person.language != 'EN'))
    count = 0
    for p in qry:
        p.language = 'IT'
        p.put()
        if (p.enabled):
            count +=1
            tell(p.chat_id, 'Risettata lingua in italiano (solo italiano e inglese attualmente supportate).')
            restart(p)
            sleep(0.50) # no more than 10 messages per second
    logging.debug("Succeffully reset languages for users: " + str(count))
    return count

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

def broadcast(msg, language='ALL', curs=None, count = 0):
    users, next_curs, more = Person.query().fetch_page(50, start_cursor=curs) #.order(-Person.last_mod)
    try:
        for p in users:
            if (p.enabled):
                if language=='ALL' or p.language==language or (language=='EN' and p.language!='IT'):
                    setLanguage(p.language)
                    logging.debug("Sending message to chat id " + str(p.chat_id))
                    tell(p.chat_id, _("Listen listen...") + _(' ') + _(msg))
                    #tell(p.chat_id, msg)
                    count += 1
                    sleep(0.050) # no more than 20 messages per second
    except datastore_errors.Timeout:
        sleep(1)
        deferred.defer(broadcast, msg, language, curs, count)
        return
    if more:
        deferred.defer(broadcast, msg, language, next_curs, count, _queue='default')
    else:
        logging.debug('broadcasted to people ' + str(count))

def getInfoCount(lang='EN'):
    setLanguage(lang)
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

def getInfoDay(language=None):
    if language:
        setLanguage(language)
    today = time_util.get_today()
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
        msg += _("Let's make it happen! ") + emoij.SMILING_FACE
    return msg

def getInfoWeek():
    setLanguage('IT')
    lastweek = time_util.get_last_week()
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


def restart(p):
    agree = p.agree_on_terms
    itn = person.isItinerarySet(p)
    if not agree and not itn:
        tell(p.chat_id, _("In order to start, please go to SETTINGS to agree on terms and conditions and setup your default ITINERARY."),
             kb=[['HELP'], [_('SETTINGS'),_('INFO')]])
        person.setStateLocation(p, -2, '-')
    elif not agree:
        tell(p.chat_id, _("In order to start, please go to SETTINGS to agree on terms and conditions."),
             kb=[['HELP'], [_('SETTINGS'),_('INFO')]])
        person.setStateLocation(p, -2, '-')
    elif not itn:
        tell(p.chat_id, _("In order to start, please go to SETTINGS to setup your default ITINERARY. " +
                          "You only need to do this once but you can always change it later."),
             kb=[['HELP'], [_('SETTINGS'),_('INFO')],[_('INVITE A FRIEND')]])
        person.setStateLocation(p, -2, '-')
    else:
        textEnabled = _("(You have notifications ENABLED)") if p.notification_enabled else _("(You have notifications DISABLED)")
        tell(p.chat_id, _("Press START if you want to start a new journey! ") + textEnabled,
             kb=[['START','HELP'], [_('SETTINGS'),_('INFO')],[_('INVITE A FRIEND')]]    )
        person.setStateLocation(p, -1, '-')

def goToInfoPanel(p):
    tell(p.chat_id, _("This is the info panel."),
          kb=[[_('INFO USERS'),_('DAY SUMMARY')],[_('SEARCH BUS STOPS'),_('SEND FEEDBACK')],[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    person.setState(p, 80)

def goToSettings(p):
    keyboard = []
    text = _("This is the settings panel.")
    if not p.agree_on_terms:
        text += _('\n') + _("You have not agreed on Terms and Conditions, please press the button below.")
        keyboard.append([_('TERMS AND CONDITIONS')])
        keyboard.append([_('LANGUAGE')])
    else:
        keyboard.append([_('ITINERARY (basic)'), _('ITINERARY (advanced)')])
        keyboard.append([_('NOTIFICATIONS'), _('LANGUAGE')])

    keyboard.append([emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")])

    tell(p.chat_id, text, kb=keyboard)
    person.setState(p, 90)

def goToSettingNotification(p):
    keyboard = []
    if p.notification_enabled:
        tell(p.chat_id, _("You have the notifications ENABLED: "
                          "you will be informed when a driver going through your route inserts a new journey, "
                          "(even though you have no active requests) and we will send you weekly statistics."),
             kb=[[_('DISABLE NOTIFICATIONS')],[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    else:
        tell(p.chat_id, _("You have the notifications DISABLED: "
                          "you will NOT be informed when a driver going through your route inserts a new journey, "
                          "(unless you have an active request) and we will NOT send you weekly statistics."),
             kb=[[_('ENABLE NOTIFICATIONS')],[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    person.setState(p, 94)



def goToSettingItineraryBasic(p):
    commands = '\n\n'.join(itinerary.BASIC_ROUTES.keys())
    tell(p.chat_id, _("Click on one of the following routes: ") + _("\n\n") + commands,
         kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    person.setState(p, 935)

def goToSettingItineraryAdvanced(p):

    start = '?' if p.bus_stop_start is None else p.bus_stop_start
    end = '?' if p.bus_stop_end is None else p.bus_stop_end
    mid_going = [x.encode('UTF8') for x in p.bus_stop_mid_going]
    mid_back = [x.encode('UTF8') for x in p.bus_stop_mid_back]
    itn_txt = _("Itinerary: ") + _(start.encode('UTF8')) + _(' <-> ') + _(end.encode('UTF8')) + _('\n\n')

    firstRowButtons = [
        _("Change Start Location") if p.bus_stop_start else _("Set Start Location"),
        _("Change End Location") if p.bus_stop_end else _("Set End Location")
    ]

    keyboard = [firstRowButtons]
    if start!='?' and end!='?':
        keyboard.append([_("Change Mid Points Going"), _("Change Mid Points Back")],)
        itn_txt += _("Drivers can optionally add intermediate points where to pick up passengers:") + _("\n\n") +\
                   _("Mid Points Going: ") + str(mid_going) + _('\n') +\
                   _("Mid Points Back: ") + str(mid_back) + _('\n\n')
    keyboard.append([emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")])

    tell(p.chat_id, _("Your current itinerary settings:") + _("\n\n") + itn_txt, kb=keyboard)
    person.setState(p, 93)

def askToInsertLocation(p, text_prefix, new_state, PAPER_CLIP_INSTRUCTIONS):
    if (p.last_city is None):
        tell(p.chat_id, _("Please insert ") +  text_prefix + '. ' + PAPER_CLIP_INSTRUCTIONS,
             kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    else:
        tell(p.chat_id, _("Please insert ") +  text_prefix + '. ' + PAPER_CLIP_INSTRUCTIONS + ' ' +
               _("Alternatevely you can press on 'LIST BUS STOPS' and select one manually."),
             kb=[[_("List Bus Stops")],[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    person.setState(p,new_state)

def askGeoLocationOrListBusStops(p, intro_text, new_state):
    # p.last_city but exist
    tell(p.chat_id,
         intro_text + _("You can enter a location using GEOLOCATION or ask for a LIST of bus stops in your city"),
         kb = [[_('Geolocation'),_("List Bus Stops")],[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    person.setState(p,new_state)


def goToSettingMidPoints(p,state, PAPER_CLIP_INSTRUCTIONS):

    midpoints = p.bus_stop_mid_going if state==933 else p.bus_stop_mid_back
    midpoints = [x.encode('UTF8') for x in midpoints]

    text = _("Please select an intermediate point you can stop on the way FORWARD to pick-up other passangers ") \
        if state==933 else _("Please select an intermediate point you can stop on the way BACK to pick-up other passangers ")

    text += PAPER_CLIP_INSTRUCTIONS

    if p.last_city:
        text += _("(or alternatively by asking the list of the bus stops and selecting one manually).")
    text += "\n\n"

    keyboard = [[_("List Bus Stops")]] if p.last_city else []
    secondLineButtons = [_('Remove all')] if midpoints else []

    if (p.bus_stop_mid_going != list(reversed(p.bus_stop_mid_back))):
        if state==933:
            if p.bus_stop_mid_back:
                secondLineButtons.append(_('Same as other direction'))
        else:
            if p.bus_stop_mid_going:
                secondLineButtons.append(_('Same as other direction'))

    keyboard.append(secondLineButtons)
    keyboard.append([emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")])

    #logging.debug("goToSettingMidPoints:" + str(keyboard))
    tell(p.chat_id, text + _("Current midpoints:") + str(midpoints), kb=keyboard)
    person.setState(p,state)


def removeSpaces(str):
    #return re.sub(r'[^\w]','',str,re.UNICODE)
    str = re.sub(r"[\s'.]",'',str,re.UNICODE)
    str = str.replace('ò','o')
    return str

def replyListBusStops(p,new_state):
    bus_stops = itinerary.getOtherBusStops(p)
    bus_stops_formatted = ['/' + removeSpaces(x.encode('UTF8')) for x in bus_stops]
    bus_stops_str = '\n'.join(bus_stops_formatted)
    person.setTmp(p,bus_stops_formatted)
    person.appendTmp(p,bus_stops)
    tell(p.chat_id,
         _("Found the following bus stop(s) in your city:") + _("\n")
         + bus_stops_str + _("\n\n") + _("Press on one of them to set it."),
         kb = [[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
    person.setState(p,new_state)



# ================================
# ================================
# ================================

def assignNextTicketId(p, is_driver):
    ticketId = None
    bus_stop = person.getBusStop(p)
    ticketId = 'D_' if is_driver else 'P_'
    ticketId += bus_stop.short_name
    bus_stop_label = itinerary.getKeyFromBusStop(bus_stop)
    #logging.debug(bus_stop_label)
    number = counter.increaseQueueCounter(bus_stop_label, is_driver)
    ticketId += str(number)
    p.ticket_id = ticketId
    p.put()
    return ticketId

# ================================
# ================================
# ================================

MAX_MIN_IN_NON_START_STATE = 60 * 24 * 7

def restartOldUsers():
    past_date = time_util.now(-MAX_MIN_IN_NON_START_STATE)
    qry = Person.query(Person.state>=0)
    count = 0
    for p in qry:
        if (p.last_mod<past_date):
            tell(p.chat_id, _('Resetting interface to initial state'))
            restart(p)
            sleep(0.035)
            count += 1
    logging.debug('Restatered old users: ' + str(count))


def checkExpiredUsers():
    checkExpiredDrivers()
    checkExpiredPassengers()

def checkExpiredDrivers():
    qry = Person.query(Person.active==True, Person.state.IN([32,33]))
    oldDrivers = {
        32: [],
        33: []
    }
    for d in qry:
        if d.state==32: #picking up drivers
            if (time_util.ellapsed_min(d.last_seen) > MAX_PICKUP_DRIVER_MIN):
                oldDrivers[d.state].append(d)
        else:
            if (time_util.ellapsed_min(d.last_seen) > MAX_COMPLETE_DRIVER_MIN):
                oldDrivers[d.state].append(d)
    for d in oldDrivers[32]:
        setLanguage(d.language)
        tell(d.chat_id, _("The ride offer has been aborted: you were expected to give a ride some time ago!"))
        ride.abortRideOffer(d, True)
        removeDriver(d)
    for d in oldDrivers[33]:
        setLanguage(d.language)
        tell(d.chat_id, _("The ride has been completed automatically: you were supposed to arrive some time ago!"))
        ride.endRide(d,auto_end=True)
        removeDriver(d)

def checkExpiredPassengers():
    qry = Person.query(Person.active==True, Person.state.IN([21, 22]))
    oldPassengers = []
    for p in qry:
        if (time_util.ellapsed_min(p.last_seen) > MAX_WAITING_PASSENGER_MIN):
            oldPassengers.append(p)
    for p in oldPassengers:
        setLanguage(p.language)
        tell(p.chat_id, _("The ride request has been aborted: ") +
             _("after some time the requests automatically expire.") + _("\n") +
             _("We believe and hope you have already reached your destination, \
               otherwise feel free to start another request")
        )
        ride_request.abortRideRequest(p, auto_end=True)
        removePassenger(p)

# ================================
# ================================
# ================================

def putPassengerOnHold(passenger):
    tell(passenger.chat_id, _("Currently there are no drivers matching your journey.") + ' '
         + _("You will be notified as soon as one is available.") + ' '
         + _("If you find another solution, please abort your request."),
         kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
    person.setState(passenger, 21)


def getMatchingDrivers(passenger):
    match = []
    qry = Person.query(Person.active==True, Person.last_city==passenger.last_city, Person.state.IN([32,33]))#.order(-Person.last_mod)
    for d in qry:
        if itinerary.matchDriverAndPassenger(d, passenger):
            match.append(d)
    return match

def getMatchingPassengers(driver):
    match = []
    qry = Person.query(Person.active==True, Person.last_city==driver.last_city, Person.state.IN([21,22]))#.order(-Person.last_mod)
    for p in qry:
        if itinerary.matchDriverAndPassenger(driver, p):
            match.append(p)
    return match

def getMatchingPotentialPassengers(driver):
    match = []
    qry = Person.query(Person.active==False, Person.last_city==driver.last_city, Person.state==-1)#.order(-Person.last_mod)
    for p in qry:
        if itinerary.matchDriverAndPotentialPassenger(driver, p):
            match.append(p)
    return match

def hasMatchingDrivers(passenger):
    qry = Person.query(Person.active==True, Person.last_city==passenger.last_city, Person.state.IN([32,33]))
    for d in qry:
        if itinerary.matchDriverAndPassenger(d, passenger):
            return True
    return False

def hasMatchingPassengers(driver):
    qry = Person.query(Person.active==True, Person.last_city==driver.last_city, Person.state.IN([21,22]))
    for p in qry:
        if itinerary.matchDriverAndPassenger(driver, p):
            return True
    return False


def connect_with_matching_drivers(passenger):
    # a passenger is at a certain location and we want to check if there is a driver engaged matching the journey of the passenger
    matchDrivers = getMatchingDrivers(passenger)
    for d in matchDrivers:
       if not d.notified:
           setLanguage(d.language)
           tell(d.chat_id, _("There is a passenger matching your journey " + emoij.PEDESTRIAN),
                kb=[[_("List Passengers"), _("Send Message")],[emoij.NOENTRY + _(' ') + _("Abort")]])
           person.setNotified(d,True)

    setLanguage(passenger.language)
    person.setActive(passenger, True)

    if matchDrivers:
        tell(passenger.chat_id, _("There is a driver matching your journey."),
              kb=[[_('List Drivers'), _('Got the Ride!')],[emoij.NOENTRY + _(' ') + _("Abort")]])
        person.setState(passenger, 22)
    else:
        putPassengerOnHold(passenger)
        # state = 21


def connect_with_matchin_passengers(driver):

    matchPassengers = getMatchingPassengers(driver)

    for p in matchPassengers:
        if (p.state==21):
            person.setState(p, 22)
            setLanguage(p.language)
            tell(p.chat_id, _("The is a driver matching your journey! " + emoij.CAR),
                 kb=[[_("List Drivers"), _("Got the Ride!")],[emoij.NOENTRY + _(' ') + _("Abort")]])

    setLanguage(driver.language)

    if matchPassengers:
        tell(driver.chat_id, _("There is some passenger(s) matching your journey ") + emoij.PEDESTRIAN + '\n' +
              _("Have a nice trip!") + emoij.SMILING_FACE,
              kb=[[_("List Passengers"), _("Send Message")],[emoij.NOENTRY + _(' ') + _("Abort")]])
    else:
        tell(driver.chat_id, _("There is currently no passenger matching your journey.") + _(" ") +
             _("If a new passege request matches your journey we will notify you.") + _("\n") +
             _("Have a nice trip! ") + emoij.SMILING_FACE,
        kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])

def notify_potential_passengers(driver):
    matchPassengers = getMatchingPotentialPassengers(driver)
    if not matchPassengers:
        return
    count = 0
    for p in matchPassengers:
        if p.notification_enabled:
            count+=1
            setLanguage(p.language)
            text = _("Notification " + emoij.CAR + ": There is a driver matching your default route!") + '\n\n' +\
                   getDriverRideDetails(driver).encode('utf-8')
            tell(p.chat_id,text)
            #logging.debug(getDriverRideDetails(driver))
            sleep(0.035) # no more than 30 messages per second
    setLanguage(driver.language)
    logging.debug("Notified potential passengers: " + str(count))

def getDriverRideDetails(driver, id=True):
    text = driver.name.encode('utf-8') + _(" ride start: ") + \
           time_util.get_time_string(driver.last_seen) + \
           _(" itinerary: ") + person.getItinerary(driver,driver=True)
    if id:
        text += _(" (id: ") + driver.ticket_id + _(")")
    return text

def getPassengerRideDetails(passenger, id = True):
    text = passenger.name.encode('utf-8') +\
           _(" waiting since ") + time_util.get_time_string(passenger.last_seen) +\
           _(" itinerary: ") + person.getItinerary(passenger,driver=False)
    if id:
        text += _(" (id: ") + passenger.ticket_id + _(")")
    return text

def listDrivers(passenger):
    matchDrivers = getMatchingDrivers(passenger)
    if matchDrivers:
        text = ""
        for d in matchDrivers:
            if itinerary.matchDriverAndPassenger(d, passenger):
                text = text + getDriverRideDetails(d) + '\n'
        return text
    else:
        return _("No drivers found matching your journey")

def listPassengers(driver):
    matchPassengers = getMatchingPassengers(driver)
    if matchPassengers:
        text = ""
        for p in matchPassengers:
            if itinerary.matchDriverAndPassenger(driver, p):
                text = text + getPassengerRideDetails(p) + '\n'
        return text
    else:
       return _("No passengers found matching your journey")


def removePassenger(p, driver=None):
    person.setActive(p, False)
    matchDrivers = getMatchingDrivers(p)
    logging.debug('Found Drivers: ' + str(len(matchDrivers)))
    for d in matchDrivers:
        if d!=driver:
            dMatchPass = getMatchingPassengers(d)
            if len(dMatchPass)==1: #only this passenger
                setLanguage(d.language)
                tell(d.chat_id, _("Oops... there are no more passage requests matching your journey!"))
                person.setNotified(d, False)
    setLanguage(p.language)
    #updateDashboard()
    restart(p)

def removeDriver(d):
    person.setActive(d, False)
    matchPassengers = getMatchingPassengers(d)
    #logging.debug('Found Drivers: ' + str(len(matchPassengers)))
    for p in matchPassengers:
        pMatchDrivers = getMatchingDrivers(p)
        if len(pMatchDrivers)==1:  #only this driver
            setLanguage(p.language)
            tell(p.chat_id, _("Oops... the are no more drivers matching your journey!"))
            putPassengerOnHold(p)
    setLanguage(d.language)
    restart(d)

def askToSelectDriverByNameAndId(p):
    match = getMatchingDrivers(p)
    if match:
        buttons = []
        for d in match:
            buttons.append([d.name.encode('utf-8') + _(" (id: ") + d.ticket_id + _(")")])
        buttons.append([_("Someone else")])
        tell(p.chat_id, _("Great, which driver gave you a ride?"), kb=buttons)
        person.setState(p, 23)
    else: # no matching drivers
        tell(p.chat_id, _("Thanks, have a good ride!")) # cannot ask you which driver cause they are all gone
        removePassenger(p)

def getDriverSelectionId(passenger, ticket_id):
    id_str = ticket_id[ticket_id.index("(id:")+5:-1]
    qry = Person.query().filter(Person.last_city==passenger.last_city, Person.ticket_id==id_str)
    return qry.get()

def broadcast_driver_message(driver, msg):
    matchPassengers = getMatchingPassengers(driver)
    for p in matchPassengers:
        setLanguage(p.language)
        tell(p.chat_id, _("Message from " + driver.name) + _(': ') + msg)
        sleep(0.035) # no more than 30 messages per second
    setLanguage(driver.language)
    return len(matchPassengers)


# ================================
# ================================
# ================================


def setLanguage(langId):
    lang = LANGUAGES[langId] if langId is not None else LANGUAGES['IT']
    gettext.translation('PickMeUp', localedir='locale', languages=[lang]).install()

# ================================
# ================================
# ================================

def tell_katja(msg):
    tell(114258373, msg)

def tell_person(chat_id, msg):
    tell(chat_id, msg)
    p = ndb.Key(Person, str(chat_id)).get()
    if p and p.enabled:
        return True
    return False

def tell_katja_test():
    try:
        tell(114258373, 'test')
    except urllib2.HTTPError, err:
        if err.code == 403:
            e = Person.query(Person.chat_id==114258373).get()
            e.enabled = False
            e.put()

def tell_masters(msg):
    if key.TEST:
        return
    for id in key.MASTER_CHAT_ID:
        tell(id, msg)

def tell_fede(msg):
    for i in range(100):
        tell(key.FEDE_CHAT_ID, "prova " + str(i))
        sleep(0.1)

def sendLocation(chat_id, loc):
    try:
        resp = urllib2.urlopen(BASE_URL + 'sendLocation', urllib.urlencode({
            'chat_id': chat_id,
            'latitude': loc.lat,
            'longitude': loc.lon,
            #'reply_markup': json.dumps({
                #'one_time_keyboard': True,
                #'resize_keyboard': True,
                #'keyboard': kb,  # [['Test1','Test2'],['Test3','Test8']]
                #'reply_markup': json.dumps({'hide_keyboard': True})
            #}),
        })).read()
        logging.info('send location: ')
        logging.info(resp)
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = Person.query(Person.chat_id==chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.name.encode('utf-8') + _(' ') + str(chat_id))


def tell(chat_id, msg, kb=None, hideKb=True):
    #logging.debug('msg: ' + str(type(msg)))
    msg = msg if isinstance(msg, str) else msg.encode('utf-8')
    try:
        if kb:
            resp = urllib2.urlopen(BASE_URL + 'sendMessage', urllib.urlencode({
                'chat_id': chat_id,
                'text': msg, #msg.encode('utf-8'),
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
                    'text': msg, #msg.encode('utf-8'),
                    'disable_web_page_preview': 'true',
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
                    'disable_web_page_preview': 'true',
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


def updateDashboard():
    #logging.debug('updateDashboard')
    data = counter.getDashboardData()
    qry = token_factory.Token.query()
    removeKeys = []
    now = time_util.now()
    for t in qry:
        duration_sec = (now - t.start_daytime).seconds
        if (duration_sec>token_factory.TOKEN_DURATION_SEC):
            removeKeys.append(t.token_id)
        else:
            channel.send_message(t.token_id, json.dumps(data))
    for k in removeKeys:
        ndb.Key(token_factory.Token, k).delete()

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
        if key.TEST:
            return
        urlfetch.set_default_fetch_deadline(60)
        tell(key.TIRAMISU_CHAT_ID, getInfoCount())

class InfouserAllHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        broadcast(getInfoCount('IT'), language='IT')
        broadcast(getInfoCount('EN'), language='EN')

class DayPeopleCountHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        date_counter.addPeopleCount()

class InfodayTiramisuHandler(webapp2.RequestHandler):
    def get(self):
        if key.TEST:
            return
        urlfetch.set_default_fetch_deadline(60)
        tell(key.TIRAMISU_CHAT_ID, getInfoDay('IT'))

class InfodayAllHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        broadcast(getInfoWeek())

class ResetCountersHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        counter.resetCounter()

class NewVersionBroadcastHandler(webapp2.RequestHandler):

    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        return

"""
        text_it = "Da oggi @PickMeUp_bot ha una marcia in più!" + '\n' + \
                  "- Nuove tratte e nuove fermate completamente flessibili (welcome to Sanba, Mesiano & Pergine!)" + '\n' +\
                  "- Geolocalizzazione: trova automaticamente la fermata più vicina a te!" + '\n' +\
                  "- Col nuovo sistema di notifiche, ricevi le offerte di passaggi in tempo reale anche se non hai nessuna richiesta attiva." + '\n\n' + \
                  "Scopri tutte le novità e diffondi @PickMeUp_bot a tutti i tuoi amici!"

        text_en = "Today @PickMeUp_bot is much more powerful!" + '\n' + \
                  "- New routes and pickup locations (welcome to Sanba, Mesiano & Pergine!)" + '\n' +\
                  "- Geolocalization: automatically find pickup locations near you!" + '\n' +\
                  "- New notification system: get ride offers in real time even when you don't have active requests." + '\n\n' + \
                  "Find out what's new and tell about @PickMeUp_bot to all your friends!"

        broadcast(text_it, 'IT')
        broadcast(text_en, 'EN')
"""

class DashboardHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        data = counter.getDashboardData()
        token_id = token_factory.createToken()
        data['token'] = token_id
        data['today_events'] = json.dumps(getTodayTimeline())
        logging.debug('Requsts: ' + str(data['today_events']))
        template = DASHBOARD_DIR_ENV.get_template('PickMeUp.html')
        logging.debug("Requested Dashboard. Created new token.")
        self.response.write(template.render(data))

class GetTokenHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        token_id = token_factory.createToken()
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
        checkExpiredUsers()

class RestartOldUsersHandler(webapp2.RequestHandler):
    def get(self):
        restartOldUsers()

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
        #if "text" not in message:
        #    return;

        #text = message.get('text').encode('utf-8') if "text" in message else ""
        text = message.get('text') if "text" in message else ""


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
        text_location = message["location"] if "location" in message else None

        def reply(msg=None, kb=None, hideKb=True):
            tell(chat_id, msg, kb, hideKb)

        def replyLocation(location):
            sendLocation(chat_id, location)

        p = ndb.Key(Person, str(chat_id)).get()

        setLanguage(p.language if p is not None else None)

        INSTRUCTIONS =  (_("PickMeUp is a non-profit carpooling service (just like BlaBlaCar but for small journeys within a city).") + _("\n\n") +
                         _("You need to agree on terms and conditions in SETTINGS  and insert an ITINERARY to start a new journey.") + _("\n") +
                         _("Once all is set, you can press START to request or offer a ride.") + _("\n\n") +
                         _("Please visit our website at http://pickmeup.trentino.it " +
                           "read the pdf instructions at http://tiny.cc/pickmeup_info " +
                           "and if you want to promote this initiative do like us on FaceBook https://www.fb.com/321pickmeup ") + _("\n\n") +
                         _("If you want to join our discussions come to the tiramisu group at the following link: " +
                           "https://telegram.me/joinchat/B8zsMQBtAYuYtJMj7qPE7g") + _("\n\n") +
                         _("Any feedback or contribution is highly appreciated (go to INFO -> SEND FEEDBACK)! :D")) #.encode('utf-8')

        TERMS_AND_CONDITIONS = (_("PickMeUp is a dynamic carpooling system, like BlaBlaCar but within the city.") + _("\n") +
                                _("It is currently  under testing.") + _("\n\n") +
                                _("WARNINGS:") + _("\n") +
                                _("Drivers: please offer rides before starting the ride. " +
                                  "DO NOT use your phone while you drive.") + _("\n") +
                                _("Passengers: please ask for rides when you are at the bus stop. ") +
                                _("Be kind with the driver and the other passengers.") + _("\n\n") +
                                _("PickMeUp is a non-profit service and it is totally money-free between passengers and drivers.") + _("\n") +
                                _("The current version is under testing: ") +
                                _("no review system has been implemented yet and ride traceability is still limited. ") + _("\n\n") +
                                _("PickMeUp developers decline any responsibility for the use of the service.") + _("\n") +
                                _("If you want to use this service you have to agree on these terms by pressing the button below."))

        MESSAGE_FOR_FRIENDS = _("Hi, I've discovered @PickMeUp_bot a free capooling service via Telegram! ") +\
                              _("It's like BlaBlaCar, but for commuting within a city. ") + \
                              _("The system is currently under testing but the community is getting larger every day. ") + \
                              _("You can try it by clicking on @PickMeUp_bot and press START! ")

        PAPER_CLIP_INSTRUCTIONS = _("Please attach a location by 1) pressing the ") + emoij.PAPER_CLIP +\
                                  _(" icon below and 2) chosing a position in the map.")

        if p is None:
            # new user
            tell_masters("New user: " + name)
            p = person.addPerson(chat_id, name)
            #if text == '/help':
            #    reply(INSTRUCTIONS)
            if text in ['/start','START']:
                registerUser(p, name, last_name, username)
                restart(p)
                # state = 0
            else:
                reply(_("Hi") + ' ' + name + ", " + _("welcome!"))
                reply(INSTRUCTIONS)
        else:
            # known user
            if text == '/initbot' and chat_id in key.MASTER_CHAT_ID:
                itinerary.initBusStops()
                counter.resetCounter()
                itinerary.initBasicRoutes()
                reply('Succeffully initialized bot!')
            elif text=='/state':
                if p.state in STATES:
                    reply("You are in state " + str(p.state) + ": " + STATES[p.state]);
                else:
                    reply("You are in state " + str(p.state));
            elif p.state == -2:
                if text in ['/help','HELP']:
                    reply(INSTRUCTIONS)
                elif text == _('INFO'):
                    goToInfoPanel(p)
                    # state = 80
                elif text == _('SETTINGS'):
                    goToSettings(p)
                    # state = 90
                elif text == _('INVITE A FRIEND'):
                    reply(_('Forward the following message to your friends.'))
                    reply(MESSAGE_FOR_FRIENDS)
                else:
                    reply(_("Sorry, I don't understand you"))
                    restart(p)
            elif p.state == -1:
                # INITIAL STATE WITH START
                if text in ['/help','HELP']:
                    reply(INSTRUCTIONS)
                elif text in ['/start','START']:
                    #start(p, text, name, last_name, username)
                    registerUser(p, name, last_name, username)
                    start(p)
                    # state = 0
                elif text == _('INFO'):
                    goToInfoPanel(p)
                    # state = 80
                elif text == _('SETTINGS'):
                    goToSettings(p)
                    # state = 90
                elif text == _('INVITE A FRIEND'):
                    reply(_('Forward the following message to your friends.'))
                    reply(MESSAGE_FOR_FRIENDS)
                elif text == '/users':
                    reply(getUsers())
                elif text == '/alldrivers':
                    reply(person.listAllDrivers())
                elif text == '/allpassengers':
                    reply(person.listAllPassengers())
                elif chat_id in key.MASTER_CHAT_ID:
                    if text == '/resetusers':
                        logging.debug('reset user')
                        #c = person.resetNullStatesUsers()
                        #reply("Reset states of users: " + str(c))
                        deferred.defer(restartAllUsers,None) #'New interface :)')
                        #resetLastNames()
                        #resetEnabled()
                        #resetLanguages()
                        #resesetNames()
                    elif text=='/infocount':
                        reply(getInfoCount())
                    elif text=='/checkenabled':
                        checkEnabled()
                    elif text == '/resetcounters':
                        counter.resetCounter()
                    elif text == '/sendText':
                        id = -1
                        text = ""
                        if tell_person(id, text):
                            reply('Successfully sent text')
                        else:
                            reply('Problems in sending text')
                    elif text == '/resetBusStopsAndCounters':
                        itinerary.initBusStops()
                        counter.resetCounter()
                        reply('Succeffully reinitiated bus stops and counters')
                    elif text == '/resetBasicRoutes':
                        itinerary.initBasicRoutes()
                        reply('Succeffully reinitiated basic routes')
                    elif text == '/test':
                        #return
                        logging.debug('test')
                        #c = person.resetActive()
                        #reply("Successfully reset actives: " + str(c))
                        #deferred.defer(restartOldUsers)
                        #c = deferred.defer(restartLanguages)
                        #c = person.resetAllState(-2)
                        #reply("Successfully reset all states: " + str(c))
                        #c = person.resetTermsAndNotification()
                        #reply("Successfully reset users terms and notification: " + str(c))
                        #reply("/opzione1 bfdslkjfdsjaklfdj")
                        #reply("/opzione2 ju39jrkek")
                        #reply("/opzione3 349jfndkkj")
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
                        #msg = "test"
                        #deferred.defer(broadcast, msg)
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
                        return
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
            elif p.state == 0:
                # AFTER TYPING START
                if text.endswith(_("Passenger")):
                    person.setState(p, 20)
                    person.setType(p, text)
                    reply(_("Hi! I can try to help you to get a ride. Which bus stop are you at?"),
                          kb=[[p.bus_stop_start, p.bus_stop_end], [emoij.NOENTRY + _(' ') + _("Abort")]])
                elif text.endswith(_("Driver")):
                #elif text == emoij.CAR + _(' ') + _("Driver"):
                    person.setState(p, 30)
                    person.setType(p, text)
                    reply(_("Hi! Glad you can give a ride. Where can you start picking up passengers?"),
                          kb=[[p.bus_stop_start, p.bus_stop_end], [emoij.NOENTRY + _(' ') + _("Abort")]])
                elif text.endswith(_("Abort")):
                #elif text == emoij.NOENTRY + _(' ') + _("Abort"):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else: reply(_("Sorry, I don't understand you"))
            elif p.state == 20:
                # PASSANGERS, ASKED FOR LOCATION
                if text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    restart(p)
                    # state = -1
                elif text in [p.bus_stop_start, p.bus_stop_end]:
                    person.setLocation(p, text)
                    person.updateLastSeen(p)
                    ticket_id = assignNextTicketId(p, is_driver=False)
                    reply(_("Your passenger ID is: ") + ticket_id.encode('utf-8'))
                    connect_with_matching_drivers(p)
                    ride_request.recordRideRequest(p)
                    # updateDashboard()
                    # state = 21 or 22 depending if driver available
                else: reply(_("Sorry, I don't understand you") + _(' '))
                            #p.bus_stop_start + _(' ') + _("or") + _(' ') + p.bus_stop_end + '?')
            elif p.state == 21:
                # PASSENGERS IN A LOCATION WITH NO DRIVERS
                if text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    ride_request.abortRideRequest(p, auto_end=False)
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
                    ride_request.abortRideRequest(p, auto_end=False)
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
                    ride_request.confirmRideRequest(p, None)
                    removePassenger(p)
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    ride_request.abortRideRequest(p, auto_end=False)
                    removePassenger(p)
                    # state = -1
                else:
                    d = getDriverSelectionId(p, text)
                    if d is not None:
                        ride_request.confirmRideRequest(p, d)
                        reply(_("Great! Many thanks to") + _(' ') + d.name.encode('utf-8') + "!")
                        setLanguage(d.language)
                        ride.addPassengerInRide(d, p)
                        tell(d.chat_id, p.name.encode('utf-8') + _(' ') + _("confirmed you gave him/her a ride!"),
                             kb=[[_("List Passengers"), _("Reached Destination!")]]) #[emoij.NOENTRY + _(' ') + _("Abort")]
                        setLanguage(p.language)
                        if (d.state==32):
                            person.setState(d, 33)
                        removePassenger(p, driver=d)
                        # passenger state = -1
                    else:
                        reply(_("Name of driver not correct, try again."))
            elif p.state == 30:
                # DRIVERS, ASKED FOR LOCATION
                #logging.debug('input: ' + text + ' ' + str(type(text)))
                #logging.debug('start: ' + p.bus_stop_start + ' ' + str(type(p.bus_stop_start)))
                #logging.debug('destination: ' + p.bus_stop_end + ' ' + str(type(p.bus_stop_end)))
                if text.endswith(_("Abort")):
                    reply(_("Passage offer has been aborted."))
                    restart(p)
                    # state = -1
                elif text in [p.bus_stop_start, p.bus_stop_end]:
                    person.setLocation(p, text)
                    # CHECK AND NOTIFY PASSENGER WAIING IN THE SAME LOCATION
                    reply(_("In how many minutes will you be there?"),
                          kb=[['0','2','5','10'],['15','30','45','60'],[emoij.NOENTRY + _(' ') + _("Abort")]])
                    person.setState(p, 31)
                    # state = 31
                else:
                    reply(_("Sorry, I don't understand you"))
                    #reply("Eh? " + p.bus_stop_start + _("or") + p.bus_stop_end + "?")
            elif p.state == 31:
                # DRIVERS ASEKED FOR TIME
                if text in ['0','2','5','10','15','30','45','60']:
                    person.setLastSeen(p, time_util.now(addMinutes=int(text)))
                    ticket_id = assignNextTicketId(p, is_driver=True)
                    reply(_("Your driver ID is: ") + ticket_id.encode('utf-8') + '\n')
                    connect_with_matchin_passengers(p)
                    deferred.defer(notify_potential_passengers,p)
                    ride.recordRide(p, int(text))
                    person.setState(p, 32)
                    person.setActive(p, True)
                    # state = 32
                elif text.endswith(_("Abort")):
                    reply(_("Passage offer has been aborted."))
                    restart(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 32:
                # DRIVERS WHO HAS LEFT
                if text == _("List Passengers"):
                    reply(listPassengers(p))
                elif text == (_("Send Message")):
                    reply(_("Please type a short message which will be sent to all passengers matching your journey"),
                        kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                    person.setState(p, 325)
                elif text.endswith(_("Abort")):
                    reply(_("Passage offer has been aborted."))
                    ride.abortRideOffer(p, False)
                    removeDriver(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))# (" + text + ")")
            elif p.state == 325:
                if not text.endswith(_("Back")):
                    count = broadcast_driver_message(p, text)
                    reply(_("Sent message to ") + str(count) + _(" people"))
                if hasMatchingPassengers(p):
                    reply(_("There is some passenger(s) matching your journing ") + emoij.PEDESTRIAN,
                          kb=[[_("List Passengers"), _("Send Message")],[emoij.NOENTRY + _(' ') + _("Abort")]])
                else:
                    reply(_("Oops... there are no more passengers matching your journing!"),
                          kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
                    # all passangers have left while driver was typing
                person.setState(p, 32)
            elif p.state == 33:
                # DRIVER WHO HAS JUST BORDED AT LEAST A PASSANGER
                if text == _("List Passengers"):
                    reply(listPassengers(p))
                elif text == _("Reached Destination!"):
                    reply(_("Great, thanks!") + _(' ') + emoij.CLAPPING_HANDS)
                    ride.endRide(p,auto_end=False)
                    removeDriver(p)
                    # state -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 80:
                # INFO PANEL
                if text==_('INFO USERS'):
                    reply(getInfoCount())
                    # restart(p)
                    # state = -1
                elif text==_('DAY SUMMARY'):
                    reply(getInfoDay())
                    # restart(p)
                    # state = -1
                elif text==_('SEARCH BUS STOPS'):
                    reply(PAPER_CLIP_INSTRUCTIONS + ' ' +
                          _("I will give you a list of bus stops within a radius of 10 km from the given location."),
                          kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                    person.clearTmp(p)
                    person.setState(p, 81)
                elif text==_('SEND FEEDBACK'):
                    reply(_("Please send us any feedback, e.g., new bus stops, bugs, suggestions. "),
                          kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                    person.setState(p, 82)
                elif text.endswith(_("Back")):
                    restart(p)
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 81:
                if text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    bus_stops = itinerary.getClosestBusStops(loc_point, [], p, max_distance=10, trim=False)
                    #.replace(' ', '-')
                    if len(bus_stops)>0:
                        bus_stops_formatted = ['/' + removeSpaces(x.encode('UTF8')) for x in bus_stops]
                        bus_stops_str = ' - '.join(bus_stops_formatted)
                        person.setTmp(p,bus_stops_formatted)
                        person.appendTmp(p,bus_stops)
                        reply(_("Found the following bus stop(s) near the location: ") + bus_stops_str + "\n\n" +
                              _("By pressing on any of the names, the location will be presented to you."),
                              kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                        person.setState(p,81)
                    else:
                        reply(_("No bus stop found near location, try again. ") + PAPER_CLIP_INSTRUCTIONS)
                elif text.startswith('/') and text in p.tmp:
                    if (text in p.tmp):
                        i = p.tmp.index(text)
                        j = len(p.tmp)/2+i
                        bus_stop = p.tmp[j]
                        replyLocation(itinerary.getBusStopLocation(p.last_city, bus_stop))
                        #reply("Found: " + p.tmp[j])
                    else:
                        reply("Sorry, I don't understand you")
                    #logging.debug('getBusStopFromCommand')
                    #getBusStopFromCommand(text,p)
                elif text.endswith(_("Back")):
                    goToInfoPanel(p)
                    # state = 80
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 82:
                if text.endswith(_("Back")):
                    goToInfoPanel(p)
                    # state = 80
                else:
                    mail.send_mail(sender="Federico Sangati <federico.sangati@gmail.com>",
                                   to="PickMeUp <pickmeupbot@gmail.com>",
                                   subject="[Feedback] from user " + p.name + ' (' + str(p.chat_id) + ')',body=text)
                    reply(_("Thanks for your feedback!"))
                    goToInfoPanel(p)
            elif p.state == 90:
                #SETTINGS
                if text==_('TERMS AND CONDITIONS'):
                    reply(TERMS_AND_CONDITIONS, kb=[[_("I AGREE")],[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                    person.setState(p, 92)
                elif text==_('ITINERARY (advanced)'):
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                elif text==_('ITINERARY (basic)'):
                    goToSettingItineraryBasic(p)
                    # state = 935
                elif text==_('NOTIFICATIONS'):
                    goToSettingNotification(p)
                    # state = 94
                elif text==_('LANGUAGE'):
                    reply(_("Choose the language"),
                          kb=[[flag + _(' ') + name for (name,flag) in LANGUAGE_FLAGS.iteritems()],
                              [emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                    person.setState(p, 91)
                elif text.endswith(_("Back")):
                    restart(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 91:
                #LANGUAGE
                if len(text)>2 and text[-2:] in LANGUAGES.keys(): #['IT','EN','FR','DE','RU','NL','PL']:
                    l = text[-2:]
                    p.language = l
                    p.put()
                    gettext.translation('PickMeUp', localedir='locale', languages=[LANGUAGES[l]]).install()
                    restart(p)
                elif text.endswith(_("Back")):
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 92:
                #AGREE ON TERMS
                if text==_('I AGREE'):
                    person.setAgreeOnTerms(p)
                    reply("Thanks for agreeing on terms!")
                    goToSettings(p)
                    # state = 90
                elif text.endswith(_("Back")):
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 93:
                #ITINERARY ADVANCED
                if text in [_("Set Start Location"),_("Change Start Location")]:
                    askToInsertLocation(p, _('the START location'), 931, PAPER_CLIP_INSTRUCTIONS)
                    # state = 931
                elif text in [_("Set End Location"),_("Change End Location")]:
                    askToInsertLocation(p, _('the END location'), 932, PAPER_CLIP_INSTRUCTIONS)
                    # state = 932
                elif text==_("Change Mid Points Going"):
                    goToSettingMidPoints(p,933,PAPER_CLIP_INSTRUCTIONS)
                    # state = 933
                elif text==_("Change Mid Points Back"):
                    goToSettingMidPoints(p,934,PAPER_CLIP_INSTRUCTIONS)
                    # state = 934
                elif text.endswith(_("Back")):
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 931:
                #START LOCATION
                if text == _("List Bus Stops"):
                    replyListBusStops(p, 9311)
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    bus_stops = itinerary.getClosestBusStops(loc_point, [p.bus_stop_end], p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,9311)
                    else:
                        reply(_("No bus stop found near location, try again. ") + PAPER_CLIP_INSTRUCTIONS)
                elif text.endswith(_("Back")):
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9311:
                #CHECK START LOCATION
                #logging.debug("text: " + text)
                #logging.debug("tmp: " + str(p.tmp))
                if text.endswith(_("Back")):
                    askToInsertLocation(p, _('the START location'), 931, PAPER_CLIP_INSTRUCTIONS)
                    # state = 931
                elif text in p.tmp:
                    if text.startswith('/'):
                        if (text in p.tmp):
                            i = p.tmp.index(text)
                            j = len(p.tmp)/2+i
                            text = p.tmp[j]
                        else:
                            reply("Sorry, I don't understand you")
                            return
                    person.setBusStopStart(p,text)
                    reply(_("Thanks for setting the START location!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 932:
                #END LOCATION
                if text == _("List Bus Stops"):
                    replyListBusStops(p, 9321)
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    bus_stops = itinerary.getClosestBusStops(loc_point, [p.bus_stop_start], p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,9321)
                    else:
                        reply(_("No bus stop found near location, try again. ") + PAPER_CLIP_INSTRUCTIONS)
                elif text.endswith(_("Back")):
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9321:
                #CHECK END LOCATION
                if text.endswith(_("Back")):
                    askToInsertLocation(p, _('the END location'), 932, PAPER_CLIP_INSTRUCTIONS)
                    # state = 932
                elif text in p.tmp:
                    if text.startswith('/'):
                        if (text in p.tmp):
                            i = p.tmp.index(text)
                            j = len(p.tmp)/2+i
                            text = p.tmp[j]
                        else:
                            reply("Sorry, I don't understand you")
                            return
                    person.setBusStopEnd(p,text)
                    reply(_("Thanks for setting the END location!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 933:
                #MID POINT GOING
                if text == _("List Bus Stops"):
                    replyListBusStops(p, 9331)
                elif text == _("Remove all"):
                    person.emptyBusStopMidGoing(p)
                    reply(_("All mid points on the way FORWARD have been removed."))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                elif text == _('Same as other direction'):
                    p.bus_stop_mid_going = list(reversed(p.bus_stop_mid_back))
                    p.put()
                    reply(_("Successfully set mid points way FORWARD as in way BACK!"))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    bus_stops = itinerary.getClosestBusStops(loc_point, [p.bus_stop_start, p.bus_stop_end], p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,9331)
                    else:
                        reply(_("No bus stop found near location, try again. ") +
                              PAPER_CLIP_INSTRUCTIONS)
                elif text.endswith(_("Back")):
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9331:
                #CHECK MID POINT GOING
                if text.endswith(_("Back")):
                     goToSettingMidPoints(p,933,PAPER_CLIP_INSTRUCTIONS)
                    # state = 933
                elif text in p.tmp:
                    if text.startswith('/'):
                        if (text in p.tmp):
                            i = p.tmp.index(text)
                            j = len(p.tmp)/2+i
                            text = p.tmp[j]
                        else:
                            reply("Sorry, I don't understand you")
                            return
                    person.appendBusStopMidGoing(p,text)
                    reply(_("Thanks for adding a new mid point!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 934:
                #MID POINT BACK
                if text == _("List Bus Stops"):
                    replyListBusStops(p, 9341)
                elif text == _("Remove all"):
                    person.emptyBusStopMidBack(p)
                    reply(_("All mid points on the way BACK have been removed."))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                elif text == _('Same as other direction'):
                    p.bus_stop_mid_back = list(reversed(p.bus_stop_mid_going))
                    p.put()
                    reply(_("Successfully set mid points way BACK as in way FORWARD!"))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    bus_stops = itinerary.getClosestBusStops(loc_point, [p.bus_stop_start, p.bus_stop_end], p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,9341)
                    else:
                        reply(_("No bus stop found near location, try again. ") +
                              PAPER_CLIP_INSTRUCTIONS)
                elif text.endswith(_("Back")):
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9341:
                #CHECK MID POINT BACK
                if text.endswith(_("Back")):
                    goToSettingMidPoints(p,934,PAPER_CLIP_INSTRUCTIONS)
                    # state = 934
                elif text in p.tmp:
                    if text.startswith('/'):
                        if (text in p.tmp):
                            i = p.tmp.index(text)
                            j = len(p.tmp)/2+i
                            text = p.tmp[j]
                        else:
                            reply("Sorry, I don't understand you")
                            return
                    person.appendBusStopMidBack(p,text)
                    reply(_("Thanks for adding a new mid point!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 935:
                #ITINERARY BASIC
                if text in itinerary.BASIC_ROUTES.keys():
                    itinerary.setBasicRoute(p,text)
                    reply(_('Successfully set the route: ') + p.bus_stop_start + ' <-> ' + p.bus_stop_end)
                    restart(p)
                    # state = -1
                elif text.endswith(_("Back")):
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 94:
                #NOTIFICATIONS
                if text==_("ENABLE NOTIFICATIONS"):
                    person.setNotifications(p,True)
                    goToSettingNotification(p)
                    # state = 94
                elif text==_("DISABLE NOTIFICATIONS"):
                    person.setNotifications(p,False)
                    goToSettingNotification(p)
                    # state = 94
                elif text.endswith(_("Back")):
                    goToSettings(p)
                    # state = 90
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
    ('/restartOldUsers', RestartOldUsersHandler),
    ('/tiramisulottery', TiramisuHandler),
    ('/dayPeopleCount', DayPeopleCountHandler),
    ('/newVersionBroadcast', NewVersionBroadcastHandler),
], debug=True)
