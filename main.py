# -*- coding: utf-8 -*-
from __future__ import division

# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.api import channel
from google.appengine.api import taskqueue
from google.appengine.ext import deferred
from google.appengine.api import mail
from google.appengine.ext.db import datastore_errors


from operator import itemgetter

import json
import logging
import urllib
import urllib2
from time import sleep
import time_util
# import requests
import googlemaps
import geopy

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
import boolVariable
#import bus
import bus_disp

from random import shuffle


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
    -2:    'Initial without Start',
    -1:    'Initial with Start',
    0:     'Started',
    20:    'Passenger Asked For Location',
    201:   'Passenger Asked For Changing Start Location',
    202:   'Passenger Asked For Changing Start Location',
    21:    'Passenger with no driver matching journey',
    22:    'Passenger with driver(s) matching journey',
    23:    'Passenger who has confirmed a ride',
    30:    'Driver asked for location',
    301:   'Driver Asked For Changing Start Location',
    302:   'Driver Asked For Changing Start Location',
    31:    'Driver asked for time',
    32:    'Driver without borded passengers',
    325:   'Driver sending message',
    33:    'Driver with boarded passengers',
    80:    'Info',
    81:    'Info -> SEARCH BUS STOPS',
    82:    'Info -> SEND FEEDBACK',
    90:    'Settings',
    91:    'Settings -> Language',
    92:    'Settings -> Terms and Conditions',
    93:    'Settings -> Itinerary',
    930:   'Settings -> Itinerary -> ChangeCity',
    931:   'Settings -> Itinerary (Simple)',
    935:   'Settings -> Itinerary (Advanced)',
    9351:  'Settings -> Itinerary (Advanced) -> Start Location',
    93511: 'Settings -> Itinerary (Advanced) -> Start Location -> Check',
    9352:  'Settings -> Itinerary (Advanced) -> End Location',
    93521: 'Settings -> Itinerary (Advanced) -> End Location -> Check',
    9353:  'Settings -> Itinerary (Advanced) -> Mid Points Going',
    93531: 'Settings -> Itinerary (Advanced) -> Mid Points Going -> Check',
    9354:  'Settings -> Itinerary (Advanced) -> Mid Points Back',
    93541: 'Settings -> Itinerary (Advanced) -> Mid Points Back -> Check',
    94:    'Settings -> Notification',
    -50:   'TurkMode On (MASTER)',
    -55:   'TurkMode On (USER)',

}

DRIVER_STATES = [30, 31, 32, 325, 33]
PASSENGER_STATES = [20,21,22,23]

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

###########
# BUTTONS
###########

START_BUTTON = "🚩 START"
HELP_BUTTON = "🆘 HELP"
ABORT_BUTTON_FUNC = lambda: "❌ " + _('Abort')
BACK_BUTTON_FUNC = lambda: "🔙 " + _('Back')
SETTINGS_BUTTON_FUNC = lambda: "⚙ " + _('SETTINGS')
INFO_BUTTON_FUNC = lambda: "ℹ " + _('INFO')
INVITE_FRIEND_BUTTON_FUNC = lambda: "🗣 " + _('INVITE A FRIEND')
ITINERARY_BUTTON_FUNC = lambda: "🛣 " + _('ITINERARY')
NOTIFICATIONS_BUTTON_FUNC = lambda: "🔔 " + _('NOTIFICATIONS')
LANGUAGE_BUTTON_FUNC = lambda: "🇮🇹🇬🇧🇩🇪 " + _('LANGUAGE')
ENABLE_NOTIFICATIONS_BUTTON_FUNC = lambda: "🔔 " + _('ENABLE NOTIFICATIONS')
DISABLE_NOTIFICATIONS_BUTTON_FUNC = lambda: "🔕 " + _('DISABLE NOTIFICATIONS')
CHANGE_START_BUTTON_FUNC = lambda: "🚩 " + _('Change Start')
CHANGE_END_BUTTON_FUNC = lambda: "🏁 " + _('Change End')
CHANGE_ITINERARY_BUTTON_FUNC = lambda: "🛣 " + _('Change ITINERARY')

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
    if p.getFirstName() != name:
        p.name = name
        modified = True
    #if (p.last_name.decode('utf-8') != last_name.decode('utf-8')):
    if p.getLastName() != last_name:
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
    if boolVariable.turkMode():
        tell(p.chat_id, _("Hi, you are now in an experimental mode in which you can type or record any ride offer or request. "
                          "The bot will analyze what you write or say and answer you as soon as possible. "
                          "Use the chat to input text or press the microphone to record any message. "),
             kb=[[ABORT_BUTTON_FUNC()]])
        person.setState(p,-55)
    else:
        tell(p.chat_id, _("Hi") + _(' ') + p.getFirstName() + _('! ') + _("Are you a driver or a passenger?"),
             kb=[[emoij.CAR + _(' ') + _('Driver'), emoij.FOOTPRINTS + _(' ') + _('Passenger')],[ABORT_BUTTON_FUNC()]])
        person.setNotified(p,False)
        person.setState(p,0)

def getUsers():
    query = Person.query() #.order(-Person.last_mod)
    if query.get() is None:
        return "No users found"
    text = ""
    for p in query.iter():
        text = text + p.getFirstName() + " (" + str(p.state) + ") " + time_util.get_date_string(p.last_mod) + "\n"
    return text

def restartUserInTurkMode():
    qry = Person.query(Person.state==-55)
    count = 0
    for p in qry:
        #if (p.state is None): # or p.state>-1
        if (p.enabled): # or p.state>-1
            msg = _("The system has been restored in non-experiemntal mode")
            tell(p.chat_id, msg)
            restartUser(p)
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
            restartUser(p)
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

def broadcast(msg, language='ALL', check_notification=False, curs=None, count = 0, markdown=False, restart=False):
    #return
    users, next_curs, more = Person.query().fetch_page(50, start_cursor=curs) #.order(-Person.last_mod)
    try:
        for p in users:
            if p.enabled and (not check_notification or p.notification_enabled):
                if language=='ALL' or p.language==language or (language=='EN' and p.language!='IT'):
                    setLanguage(p.language)
                    #logging.debug("Sending message to chat id " + str(p.chat_id))
                    tell(p.chat_id, _("Listen listen...") + _(' ') + _(msg), markdown=markdown)
                    #tell(p.chat_id, msg)
                    count += 1
                    if restart:
                        restartUser(p)
                    sleep(0.050) # no more than 20 messages per second
    except datastore_errors.Timeout:
        sleep(1)
        deferred.defer(broadcast, msg, language, check_notification, curs, count, markdown=markdown, restart=restart)
        return
    if more:
        deferred.defer(broadcast, msg, language, check_notification, next_curs, count, _queue='default', markdown=markdown, restart=restart)
    else:
        logging.debug('broadcasted to people ' + str(count))


def getInfoCount(lang='EN'):
    setLanguage(lang)
    c = Person.query().count()
    msg = _("We are now") + _(' ') + str(c) + _(' ') + _("people subscribed to PickMeUp!")
    return msg


def getInfoAllRequestsOffers():
    setLanguage('IT')
    qryRideRequestCount = RideRequest.query().count()
    qryRideCount = Ride.query().count()
    qryRideCompletedCount = Ride.query(Ride.passengers_names_str != None).count()
    msg = _("Since the beginning of time there were a total of ") + str(qryRideRequestCount) +\
          _(" ride requests and ") + str(qryRideCount) + _(" ride offers, of which ") +\
          str(qryRideCompletedCount) + _(" confirmed!") + "\n"
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
          str(qryRideCompletedCount) + _(" confirmed!") + "\n"
    if qryRideCompletedCount>0:
        msg += _("Many thanks to all of you! ") + emoij.CLAPPING_HANDS
    else:
        msg += _("Let's make it happen! ") + emoij.SMILING_FACE
    return msg

def getInfoWeek(language):
    setLanguage(language)
    lastweek = time_util.get_last_week()
    qryRideRequest = RideRequest.query(RideRequest.passenger_last_seen > lastweek)
    qryRide = Ride.query(Ride.start_daytime > lastweek)
    driverNameSet = set()
    for r in qryRide:
        driverNameSet.add(r.getDriverName())
    driversCount = qryRide.count()
    nameSetStr = ', '.join(driverNameSet)
    #qryRideCompleted = Ride.query(Ride.start_daytime > lastweek and Ride.end_daytime > lastweek)
    #qryRideCompletedCount = qryRideCompleted.count()
    c = Person.query().count()
    msg = _("We are now") + _(' ') + str(c) + _(' ') + _("people subscribed to PickMeUp!")
    msg += "\n"
    msg += _("This week there were a total of ") + str(qryRideRequest.count()) +\
          _(" ride requests and ") + str(driversCount) + _(" ride offers.") + "\n"
    if driversCount==0:
        msg += _("Many thanks to all of you! " ) + emoij.CLAPPING_HANDS
    elif driversCount==1:
        msg += _("Many thanks to our favorite driver: ") + nameSetStr + emoij.CLAPPING_HANDS
    else:
        msg += _("Many thanks to our special drivers: ") + nameSetStr + emoij.CLAPPING_HANDS * driversCount
    return msg

price_message = \
"""
Nelle ultime settimane ci sono state in totale {0} richieste di passaggio e {1} offerte di passaggio.
Un grazie enorme ai nostri  autisti: {2} {3}

🎁🎁🎁

🏅L’autista più virtuoso/a di questa settimana è stato/a *{4}*, che si è aggiudicato un lavaggio gratis presso *REPSOL* (viale Verona 196)! Tutti gli altri utenti (autisti o passeggeri) potranno usufruire di uno sconto di 3 € sul lavaggio esterno della macchina dicendo al gestore la parola segreta ‘SCONTO PICKMEUP’.

🏅Il secondo classificato è stato/a *{5}* che si è aggiudicato/a un aperitivo gratis presso il *Social Stone* (Via Gorizia 18).

In arrivo altri premi per tutti i nostri utenti: seguiteci su twitter e facebook per saperne di più!

Graze a *REPSOL* e al *Social Stone*!
"""

PREVIOUS_WINNERS = [162491524, 140299529, 126124516, 119936816, 78774534, 20651034]
#Roberto, Giacomo, Stefano, Gabriele, Matteo, Martina

def getWeekWinners():
    #startDate = time_util.get_last_week()
    startDate = time_util.get_date_CET_from_DDMMYY('060516')
    qryRideRequest = RideRequest.query(RideRequest.passenger_last_seen > startDate)
    qryRide = Ride.query(Ride.start_daytime > startDate)
    driverDict = {}
    for r in qryRide:
        id = r.driver_id
        if id in driverDict.keys():
            dicEntry = driverDict[id]
        else:
            driverDict[id] = dicEntry = {
                'name': r.getDriverName(),
                'rides': 0,
                'confirmed': 0,
            }
        dicEntry['rides'] += 1
        if r.end_daytime and r.end_daytime > startDate:
            dicEntry['confirmed'] += 1
    nameSetStr = ', '.join([dicEntry['name'] for dicEntry in driverDict.itervalues()])
    clapsHands = emoij.CLAPPING_HANDS * len(driverDict)

    confirmed_winners = keysWithSortedValInSubDict(driverDict, 'confirmed')
    ride_winners = keysWithSortedValInSubDict(driverDict, 'rides')

    logging.debug('ride winners: ' + str(ride_winners))
    logging.debug('confirmed winners: ' + str(confirmed_winners))

    winners_keys = keysWithSortedValInSubDict(driverDict, 'confirmed')
    for w in keysWithSortedValInSubDict(driverDict, 'rides'):
        if w not in winners_keys:
            winners_keys.append(w)

    logging.debug('all winners: ' + str(winners_keys))

    for w in PREVIOUS_WINNERS:
        if w in winners_keys:
            winners_keys.remove(w)

    logging.debug('all winners after removing previous winners: ' + str(winners_keys))

    if len(winners_keys) >= 2:
        first_place_id = winners_keys[0]
        first_place_name = driverDict[first_place_id]['name']
        second_place_id = winners_keys[1]
        second_place_name = driverDict[second_place_id]['name']

    debug = "----- info for masters -----\n"
    for k,v in driverDict.iteritems():
        debug += "Id " + str(k) + " Name:%(name)s Rides:%(rides)d Confermed:%(confirmed)d\n" %v
    if len(winners_keys) >= 2:
        debug += "Winner 1st position: " + str(first_place_id) + ' ' + first_place_name + "\n"
        debug += "Winner 2nd position: " + str(second_place_id) + ' ' + second_place_name + "\n"

    if len(winners_keys)<2:
        msg = "Questa settimana non abbiamo vincitori."
    else:
        msg = price_message.format(str(qryRideRequest.count()), str(qryRide.count()), nameSetStr,
                                   clapsHands, first_place_name, second_place_name)

    return msg, debug


def keysWithMaxValInSubDict(dict, label):
    k = dict.keys()
    v = [x[label] for x in dict.values()]
    return [k[i] for i, x in enumerate(v) if x == max(v)]

def keysWithSortedValInSubDict(dict, label):
    k = dict.keys()
    v = [x[label] for x in dict.values()]
    enumValues = [(i,j) for i,j in enumerate(v)]
    shuffle(enumValues)
    return [k[i] for i, x in sorted(enumValues, key=itemgetter(1), reverse=True) if x > 0]



def sendRecentDriversMessage(daysAgo, msg):
    drivers_id_set = set()
    someTimeAgo = time_util.get_date_days_ago(daysAgo)
    qry = Ride.query(Ride.start_daytime > someTimeAgo)
    for q in qry:
        drivers_id_set.add(q.driver_id)
    count = 0
    for driver_id in drivers_id_set:
        p = person.getPerson(driver_id)
        if p.enabled:
            count += 1
            #tell(p.chat_id, "Ciao " + p.name.encode("utf-8") + "! " + msg.encode("utf-8"))
            tell(p.chat_id, msg.encode("utf-8"))
            sleep(0.050) # no more than 20 messages per second
    logging.debug('Sente message to drivers ' + str(count))

def tellmyself(p, msg):
    tell(p.chat_id, "Listen listen... " + msg)


def restartUser(p):
    agree = p.agree_on_terms
    itn = person.isItinerarySet(p)
    if not agree and not itn:
        tell(p.chat_id, _("In order to start, please go to SETTINGS to agree on terms and conditions and setup your default ITINERARY."),
             kb=[[HELP_BUTTON], [SETTINGS_BUTTON_FUNC(),INFO_BUTTON_FUNC()]])
        person.setStateLocation(p, -2, '-')
    elif not agree:
        tell(p.chat_id, _("In order to start, please go to SETTINGS to agree on terms and conditions."),
             kb=[[HELP_BUTTON], [SETTINGS_BUTTON_FUNC(),INFO_BUTTON_FUNC()]])
        person.setStateLocation(p, -2, '-')
    elif not itn:
        tell(p.chat_id, _("In order to start, please go to SETTINGS to setup your default ITINERARY. " +
                          "You only need to do this once but you can always change it later."),
             kb=[[HELP_BUTTON], [SETTINGS_BUTTON_FUNC(),INFO_BUTTON_FUNC()],[INVITE_FRIEND_BUTTON_FUNC()]])
        person.setStateLocation(p, -2, '-')
    else:
        textEnabled = _("(You have notifications ENABLED)") if p.notification_enabled else _("(You have notifications DISABLED)")
        tell(p.chat_id, _("Press START if you want to start a new journey! ") + textEnabled,
             kb=[[START_BUTTON,HELP_BUTTON], [SETTINGS_BUTTON_FUNC(),INFO_BUTTON_FUNC()],[INVITE_FRIEND_BUTTON_FUNC()]]    )
        person.setStateLocation(p, -1, '-')


def goToState20(p):
    person.setState(p, 20)
    #logging.debug("In goToState20, p.basic_route: " + str(p.basic_route))
    secondRow = [CHANGE_START_BUTTON_FUNC(), CHANGE_ITINERARY_BUTTON_FUNC(), CHANGE_END_BUTTON_FUNC()] if p.basic_route else [CHANGE_ITINERARY_BUTTON_FUNC()]
    tell(p.chat_id, _("Hi! I can try to help you to get a ride. Which bus stop are you waiting at?"),
          kb=[
              [p.getBusStartStr(), p.getBusEndStr()],
              secondRow,
              [ABORT_BUTTON_FUNC()]])

def goToState30(p):
    person.setState(p, 30)
    secondRow = [CHANGE_START_BUTTON_FUNC(), CHANGE_ITINERARY_BUTTON_FUNC(), CHANGE_END_BUTTON_FUNC()] if p.basic_route else [CHANGE_ITINERARY_BUTTON_FUNC()]
    tell(p.chat_id, _("Hi! Glad you can give a ride. Where can you start picking up passengers?"),
         kb=[
              [p.getBusStartStr(), p.getBusEndStr()],
              secondRow,
              [ABORT_BUTTON_FUNC()]])

def goToInfoPanel(p):
    tell(p.chat_id, _("This is the info panel."),
          kb=[[_('INFO USERS'),_('DAY SUMMARY')],[_('SEARCH BUS STOPS'),_('SEND FEEDBACK')],[BACK_BUTTON_FUNC()]])
    person.setState(p, 80)

def goToSettings(p):
    keyboard = []
    text = _("This is the settings panel.")
    if not p.agree_on_terms:
        text += '\n' + _("You have not agreed on Terms and Conditions, please press the button below.")
        keyboard.append([_('TERMS AND CONDITIONS')])
        keyboard.append([LANGUAGE_BUTTON_FUNC()])
    else:
        #keyboard.append([_('ITINERARY (simple)'), _('ITINERARY (advanced)')])
        keyboard.append([ITINERARY_BUTTON_FUNC()])
        keyboard.append([NOTIFICATIONS_BUTTON_FUNC(), LANGUAGE_BUTTON_FUNC()])

    keyboard.append([BACK_BUTTON_FUNC()])

    tell(p.chat_id, text, kb=keyboard)
    person.setState(p, 90)

def goToSettingNotification(p):
    keyboard = []
    if p.notification_enabled:
        tell(p.chat_id, _("You have the notifications ENABLED: "
                          "you will be informed when a driver going through your route inserts a new journey, "
                          "(even though you have no active requests) and we will send you weekly statistics."),
             kb=[[DISABLE_NOTIFICATIONS_BUTTON_FUNC()],[BACK_BUTTON_FUNC()]])
    else:
        tell(p.chat_id, _("You have the notifications DISABLED: "
                          "you will NOT be informed when a driver going through your route inserts a new journey, "
                          "(unless you have an active request) and we will NOT send you weekly statistics."),
             kb=[[ENABLE_NOTIFICATIONS_BUTTON_FUNC()],[BACK_BUTTON_FUNC()]])
    person.setState(p, 94)

def goToChangeCity(p):
    text = _("Select the city where you are located")
    keyboard = [
            itinerary.CITIES,
            [BACK_BUTTON_FUNC()]
        ]
    tell(p.chat_id, text, kb=keyboard)
    person.setState(p, 930)

def goToSettingItinerary(p):
    if p.last_city is None:
        goToChangeCity(p)
    else:
        text = getItinerary(p)
        text += _("Click on 'ITINERARY (simple)' for predefined routes or 'ITINERARY (advanced)' "
                 "for manually setting departure, destinations and intermediate points.")
        keyboard = [
            [_('ITINERARY (simple)'), _('ITINERARY (advanced)')],
            [BACK_BUTTON_FUNC()]
        ]
        if key.TEST:
            keyboard.insert(1, [_('Change City')])
        tell(p.chat_id, text, kb=keyboard, markdown=True)
        person.setState(p, 93)

def goToSettingItinerarySimple(p):
    #commands = '\n\n'.join(itinerary.BASIC_ROUTES.keys())
    commandList = itinerary.getBasicRoutesCommands(p.last_city)
    commands = '\n\n'.join(commandList)
    tell(p.chat_id, _("Click on one of the following routes: ") + "\n\n" + commands,
         kb=[[BACK_BUTTON_FUNC()]])
    person.setState(p, 931)

def getItinerary(p):
    start = '?' if p.getBusStartStr() is None else p.getBusStartStr()
    end = '?' if p.getBusEndStr() is None else p.getBusEndStr()
    itn_txt = _("*Your current itinerary*: ") + start + _(' <-> ') + end + '\n\n'
    if start!='?' and end!='?':
        itn_txt += _("Drivers can optionally add intermediate points where to pick up passengers:") + "\n\n" +\
                   _("*Mid Points Going*: ") + p.getBusStopMidGoingStr() + '\n' +\
                   _("*Mid Points Back*: ") + p.getBusStopMidBackStr() + '\n\n'
    return itn_txt

def goToSettingItineraryAdvanced(p):
    itn_txt = getItinerary(p)
    firstRowButtons = [
        _('Change Start Location') if p.getBusStartStr() else _('Set Start Location'),
        _('Change End Location') if p.getBusEndStr() else _('Set End Location')
    ]
    keyboard = [firstRowButtons]
    if p.getBusStartStr() and p.getBusEndStr():
        keyboard.append([_('Change Mid Points Going'), _('Change Mid Points Back')],)
    keyboard.append([BACK_BUTTON_FUNC()])
    tell(p.chat_id, itn_txt, kb=keyboard, markdown=True)
    person.setState(p, 935)

def askToInsertLocation(p, text_prefix, new_state, PAPER_CLIP_INSTRUCTIONS):
    if (p.last_city is None):
        tell(p.chat_id, _("Please insert ") +  text_prefix + '. ' + PAPER_CLIP_INSTRUCTIONS,
             kb=[[BACK_BUTTON_FUNC()]])
    else:
        first_row_button = [_('List All Stops')]
        if p.basic_route:
            first_row_button.append(_('List Itinerary Stops'))
        tell(p.chat_id, _("Please insert ") +  text_prefix + '. ' + PAPER_CLIP_INSTRUCTIONS + ' ' +
               _("Alternatevely you can request to list the bus stops and select one manually."),
             kb=[first_row_button,[BACK_BUTTON_FUNC()]])
    person.setState(p,new_state)

def askGeoLocationOrListBusStops(p, intro_text, new_state):
    # p.last_city but exist
    tell(p.chat_id,
         intro_text + _("You can enter a location using GEOLOCATION or ask for a LIST of bus stops in your city"),
         kb = [[_('Geolocation'),_('List All Stops')],[BACK_BUTTON_FUNC()]])
    person.setState(p,new_state)


def goToSettingMidPoints(p,state, PAPER_CLIP_INSTRUCTIONS):

    midpoints = p.bus_stop_mid_going if state==9353 else p.bus_stop_mid_back
    midpoints = [x.encode('UTF8') for x in midpoints]

    text = _("Select an intermediate point you can stop on the way FORWARD to pick-up other passangers:") + '\n' \
        if state==9353 else _("Select an intermediate point you can stop on the way BACK to pick-up other passangers:") + '\n'

    text += PAPER_CLIP_INSTRUCTIONS

    if p.last_city:
        text += _(" Alternatively you can request to list the bus stops and select one manually.")
    text += "\n\n"

    keyboard = [[_('List All Stops')]] if p.last_city else []
    secondLineButtons = [_('Remove all')] if midpoints else []

    if (p.bus_stop_mid_going != list(reversed(p.bus_stop_mid_back))):
        if state==9353:
            if p.bus_stop_mid_back:
                secondLineButtons.append(_('Same as other direction'))
        else:
            if p.bus_stop_mid_going:
                secondLineButtons.append(_('Same as other direction'))

    keyboard.append(secondLineButtons)
    keyboard.append([BACK_BUTTON_FUNC()])

    #logging.debug("goToSettingMidPoints:" + str(keyboard))
    tell(p.chat_id, text + _("*Current midpoints*: ") + str(midpoints), kb=keyboard, markdown=True)
    person.setState(p,state)


def removeSpaces(str):
    #return re.sub(r'[^\w]','',str,re.UNICODE)
    str = re.sub(r"[\s'.]",'',str,re.UNICODE)
    str = str.replace('ò','o')
    str = str.replace('(','_')
    str = str.replace(')','')
    return str

def replyListAllBusStops(p,new_state):
    #bus_stops = itinerary.getOtherBusStops(p)
    bus_stops = itinerary.getAllBusStops(p)
    bus_stops_formatted = ['/' + removeSpaces(x.encode('UTF8')) for x in bus_stops]
    bus_stops_str = '\n'.join(bus_stops_formatted)
    person.setTmp(p,bus_stops_formatted)
    person.appendTmp(p,bus_stops)
    tell(p.chat_id,
         _("Found the following bus stop(s) in your city:") + "\n"
         + bus_stops_str + "\n\n" + _("Press on one of them to set it."),
         kb = [[BACK_BUTTON_FUNC()]])
    person.setState(p,new_state)

def replyListItineraryBusStops(p,new_state):
    bus_stops = itinerary.getItineraryBusStops(p)
    bus_stops_formatted = ['/' + removeSpaces(x.encode('UTF8')) for x in bus_stops]
    bus_stops_str = '\n'.join(bus_stops_formatted)
    person.setTmp(p,bus_stops_formatted)
    person.appendTmp(p,bus_stops)
    tell(p.chat_id,
         _("Found the following bus stop(s) in your current itinerary:") + "\n"
         + bus_stops_str + "\n\n" + _("Press on one of them to set it."),
         kb = [[BACK_BUTTON_FUNC()]])
    person.setState(p,new_state)


# ================================
# ================================
# ================================

def escape_markdown(text):
    for char in '*_`[':
        text = text.replace(char, '\\'+char)
    return text

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
    #return escape_markdown(ticketId)
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
            restartUser(p)
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
             _("after some time the requests automatically expire.") + "\n" +
             _("We believe and hope you have already reached your destination, \
               otherwise feel free to start another request")
        )
        ride_request.abortRideRequest(p, auto_end=True)
        removePassenger(p)

# ================================
# ================================
# ================================

def putPassengerOnHold(passenger):
    kb = [[ABORT_BUTTON_FUNC()]]
    if key.TEST and passenger.last_city == itinerary.CITY_TRENTO:
        kb.insert(0,[_('Show Bus Times')])
    tell(passenger.chat_id, _("Currently there are no drivers matching your journey.") + ' '
         + _("You will be notified as soon as one is available.") + ' '
         + _("If you find another solution, please abort your request."), kb)
    person.setState(passenger, 21)

def getActiveDrivers():
    match = []
    qry = Person.query(Person.active==True, Person.state.IN([32,33]))#.order(-Person.last_mod)
    for d in qry:
        match.append(d)
    return match

def getActivePassengers():
    match = []
    qry = Person.query(Person.active==True, Person.state.IN([21,22]))#.order(-Person.last_mod)
    for p in qry:
        match.append(p)
    return match


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
    qry = Person.query(Person.active==False, Person.last_city==driver.last_city)#.order(-Person.last_mod)
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
           tell(d.chat_id, _("There is a passenger matching your journey ") + emoij.PEDESTRIAN,
                kb=[[_('List Passengers'), _('Send Message')],[ABORT_BUTTON_FUNC()]])
           person.setNotified(d,True)

    setLanguage(passenger.language)
    person.setActive(passenger, True)

    if matchDrivers:
        tell(passenger.chat_id, _("There is a driver matching your journey."),
              kb=[[_('List Drivers'), _('Got the Ride!')],[ABORT_BUTTON_FUNC()]])
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
                 kb=[[_('List Drivers'), _('Got the Ride!')],[ABORT_BUTTON_FUNC()]])

    setLanguage(driver.language)

    if matchPassengers:
        tell(driver.chat_id, _("There is some passenger(s) matching your journey ") + emoij.PEDESTRIAN + '\n' +
              _("Have a nice trip!") + emoij.SMILING_FACE,
              kb=[[_('List Passengers'), _('Send Message')],[ABORT_BUTTON_FUNC()]])
    else:
        tell(driver.chat_id, _("There is currently no passenger matching your journey.") + _(" ") +
             _("If a new passege request matches your journey we will notify you.") + "\n" +
             _("Have a nice trip! ") + emoij.SMILING_FACE,
        kb=[[ABORT_BUTTON_FUNC()]])

def notify_potential_passengers(driver, time=None):
    matchPassengers = getMatchingPotentialPassengers(driver)
    if not matchPassengers:
        return
    count = 0
    for p in matchPassengers:
        if p.chat_id==driver.chat_id:
            continue
        if p.notification_enabled:
            count+=1
            setLanguage(p.language)
            if time:
                text = _("Scheduled Trip ") + emoij.CAR + _(": There is a driver matching your default route!") + \
                       '\n\n' + getDriverRideScheduleDetails(driver, time).encode('utf-8')
            else:
                text = _("Notification ") + emoij.CAR + _(": There is a driver matching your default route!") + \
                       '\n\n' + getDriverRideDetails(driver).encode('utf-8')
            tell(p.chat_id,text)
            #logging.debug(getDriverRideDetails(driver))
            sleep(0.035) # no more than 30 messages per second
    setLanguage(driver.language)

    tell(driver.chat_id,  _("We have informed ") + str(count) + _(" other people who travel on the same route."))
    logging.debug("Notified potential passengers: " + str(count))

def getDriverRideDetails(driver, id=True):
    text = driver.name.encode('utf-8') + _(" ride start: ") + \
           time_util.get_time_string(driver.last_seen) + \
           _(" itinerary: ") + person.getItinerary(driver,driver=True)
    if id:
        text += _(" (id: ") + driver.ticket_id + _(")")
    if (driver.username and driver.username!='-'):
        text +=  _(" username: @") + driver.username
    return text

def getDriverRideScheduleDetails(driver, time_text):
    text = driver.name.encode('utf-8') + _(" ride start: ") + \
           time_text + _(" itinerary: ") + person.getItinerary(driver,driver=True)
    if (driver.username and driver.username!='-'):
        text +=  _(" username: @") + driver.username
    return text


def getPassengerRideDetails(passenger, id = True):
    text = passenger.name.encode('utf-8') +\
           _(" waiting since ") + time_util.get_time_string(passenger.last_seen) +\
           _(" itinerary: ") + person.getItinerary(passenger,driver=False)
    if id:
        text += _(" (id: ") + passenger.ticket_id + _(")")
    if (passenger.username and passenger.username!='-'):
        text +=  _(" username: @") + passenger.username
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

def listActiveDrivers():
    matchDrivers = getActiveDrivers()
    if matchDrivers:
        text = ""
        for d in matchDrivers:
            text = text + getDriverRideDetails(d) + '\n'
        return text
    else:
        return _("No active drivers found")


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

def listActivePassengers():
    matchPassengers = getActivePassengers()
    if matchPassengers:
        text = ""
        for p in matchPassengers:
            text = text + getPassengerRideDetails(p) + '\n'
        return text
    else:
       return _("No active passengers found")


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
    restartUser(p)

def removeDriver(d):
    person.setActive(d, False)
    matchPassengers = getMatchingPassengers(d)
    #logging.debug('Found Drivers: ' + str(len(matchPassengers)))
    for p in matchPassengers:
        pMatchDrivers = getMatchingDrivers(p)
        if len(pMatchDrivers)==1:  #only this driver
            setLanguage(p.language)
            tell(p.chat_id, _("Oops... there are no more drivers matching your journey!"))
            putPassengerOnHold(p)
    setLanguage(d.language)
    restartUser(d)

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

def tell_person(chat_id, msg, markdown=False):
    tell(chat_id, msg, markdown=markdown)
    p = ndb.Key(Person, str(chat_id)).get()
    if p and p.enabled:
        return True
    return False


def sendText(p, text, markdown=False):
    split = text.split()
    if len(split)<3:
        tell(p.chat_id, 'Commands should have at least 2 spaces')
        return
    if not split[1].isdigit():
        tell(p.chat_id, 'Second argumnet should be a valid chat_id')
        return
    id = int(split[1])
    text = ' '.join(split[2:])
    if tell_person(id, text, markdown=markdown):
        user = person.getPerson(id)
        tell(p.chat_id, 'Successfully sent text to ' + user.getFirstName())
    else:
        tell(p.chat_id, 'Problems in sending text')

def restartSingleUser(p, text):
    split = text.split()
    if len(split)<2:
        tell(p.chat_id, 'Commands should have at least 1 space')
        return
    if not split[1].isdigit():
        tell(p.chat_id, 'Second argumnet should be a valid chat_id')
        return
    chat_id = split[1]
    text = ' '.join(split[2:])
    u = ndb.Key(Person, chat_id).get()
    if u:
        restartUser(u)
        tell(p.chat_id, 'Successfully restarted user: ' + u.name)
    else:
        tell(p.chat_id, 'Problems in sending text')

# ================================
# ================================
# ================================


def setLanguage(langId):
    lang = LANGUAGES[langId] if langId is not None else LANGUAGES['IT']
    gettext.translation('PickMeUp', localedir='locale', languages=[lang]).install()

# ================================
# ================================
# ================================

def tell_masters(msg, markdown=False, one_time_keyboard=False):
    if key.TEST:
        return
    for id in key.MASTER_CHAT_ID:
        tell(id, msg, markdown=markdown, one_time_keyboard = one_time_keyboard, sleepDelay=True)

def tell_fede(msg):
    for i in range(100):
        tell(key.FEDE_CHAT_ID, "prova " + str(i))
        sleep(0.1)

def sendVoice(chat_id, file_id):
    try:
        resp = urllib2.urlopen(BASE_URL + 'sendVoice', urllib.urlencode({
            'chat_id': str(chat_id),
            'voice': str(file_id), #.encode('utf-8'),
        })).read()
        logging.info('send voice: ')
        logging.info(resp)
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = Person.query(Person.chat_id==chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.getFirstName() + ' ' + str(chat_id))
        else:
            logging.info('Error occured: ' + str(err))


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
            logging.info('Disabled user: ' + p.getFirstName() + _(' ') + str(chat_id))


def tell(chat_id, msg, kb=None, markdown=False, inlineKeyboardMarkup=False,
         one_time_keyboard=True, sleepDelay=False):
    replyMarkup = {
        'resize_keyboard': True,
        'one_time_keyboard': one_time_keyboard
    }
    if kb:
        if inlineKeyboardMarkup:
            replyMarkup['inline_keyboard'] = kb
        else:
            replyMarkup['keyboard'] = kb
    try:
        resp = urllib2.urlopen(BASE_URL + 'sendMessage', urllib.urlencode({
            'chat_id': chat_id,
            'text': msg,  # .encode('utf-8'),
            'disable_web_page_preview': 'true',
            'parse_mode': 'Markdown' if markdown else '',
            # 'reply_to_message_id': str(message_id),
            'reply_markup': json.dumps(replyMarkup),
        })).read()
        logging.info('send response: ')
        logging.info(resp)
        resp_json = json.loads(resp)
        return resp_json['result']['message_id']
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = person.getPersonByChatId(chat_id)
            p.setEnabled(False, put=True)
            # logging.info('Disabled user: ' + p.name.encode('utf-8') + ' ' + str(chat_id))
        else:
            logging.debug('Raising unknown err in tell() with msg = ' + msg)
            raise err
    if sleepDelay:
        sleep(0.1)

'''
def tell(chat_id, msg, kb=None, hideKb=True, markdown=False):
    #logging.debug('msg: ' + str(type(msg)))
    msg = msg if isinstance(msg, str) else msg.encode('utf-8')
    try:
        if kb:
            resp = urllib2.urlopen(BASE_URL + 'sendMessage', urllib.urlencode({
                'chat_id': chat_id,
                'text': msg, #msg.encode('utf-8'),
                'disable_web_page_preview': 'true',
                'parse_mode': 'Markdown' if markdown else '',
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
                    'parse_mode': 'Markdown' if markdown else '',
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
                    'parse_mode': 'Markdown' if markdown else '',
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
            logging.info('Disabled user: ' + p.getName() + _(' ') + str(chat_id))
        else:
            logging.debug('Raising unknown err in tell() with msg = ' + msg)
            raise err
'''

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

"""
def getActiveDrivers(master_id):
    match = []
    qry = Person.query(Person.active == True, Person.state.IN(DRIVER_STATES))#.order(-Person.last_mod)
    for d in qry:
        if itinerary.matchDriverAndPassenger(d, passenger):
            match.append(d)
    return match

def getActivePassengers(master_id):
    match = []
    qry = Person.query(Person.active==True, Person.state.IN(PASSENGER_STATES))#.order(-Person.last_mod)
    for d in qry:
        if itinerary.matchDriverAndPassenger(d, passenger):
            match.append(d)
    return match
"""

# ================================
# ================================
# ================================

def testOrariBus(p):
    #TN_Rosmini_SMM = ('Rosmini S.Maria Maggiore', 46.0678403, 11.1188594, 'RSM')
    #location.latitude,location.longitude
    point = geopy.point.Point(46.0678403, 11.1188594)
    text = bus_disp.gettrip(point)
    tell(p.chat_id, text)

def tellBusTimes(p):
    bus_stop = person.getBusStop(p)
    bus_location = bus_stop.location
    point = geopy.point.Point(bus_location.lat, bus_location.lon)
    text = bus_disp.gettrip(point)
    tell(p.chat_id, text)

# ================================
# ================================
# ================================


gmaps = googlemaps.Client(key=key.GOOGLE_API_KEY)

def test_Google_Map_Api():
    # Geocoding an address
    #geocode_result = gmaps.geocode('1600 Amphitheatre Parkway, Mountain View, CA')
    #return geocode_result

    # Look up an address with reverse geocoding
    #reverse_geocode_result = gmaps.reverse_geocode((40.714224, -73.961452))

    # Request directions via public transit
    #now = datetime.now()
    #directions_result = gmaps.directions("Sydney Town Hall",
    #                                 "Parramatta, NSW",
    #                                 mode="transit",
    #                                 departure_time=now)


    """
    def distance_matrix(client, origins, destinations,
                    mode=None, language=None, avoid=None, units=None,
                    departure_time=None, arrival_time=None, transit_mode=None,
                    transit_routing_preference=None, traffic_model=None):
    """

    orig_coord = "45.29037,11.73045"
    dest_coord = "45.32724,11.79545"
    result = gmaps.distance_matrix(orig_coord, dest_coord, mode="driving", units='metric')
    if result[u'status']==[u'OK']:
        driving_dst = result[u'rows'][0][u'elements'][0][u'distance'][u'value'] #meters
        return driving_dst/1000
    else:
        return 0


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

'''
class InfouserTiramisuHandler(webapp2.RequestHandler):
    def get(self):
        if key.TEST:
            return
        urlfetch.set_default_fetch_deadline(60)
        tell(key.TIRAMISU_CHAT_ID, getInfoCount())
'''

'''
class InfouserAllHandler(webapp2.RequestHandler):
    def get(self):
        if key.TEST:
            return
        urlfetch.set_default_fetch_deadline(60)
        broadcast(getInfoCount('IT'), language='IT', check_notification=True)
        broadcast(getInfoCount('EN'), language='EN', check_notification=True)
'''

class InfoWeekAllHandler(webapp2.RequestHandler):
    def get(self):
        if key.TEST:
            return
        urlfetch.set_default_fetch_deadline(60)
        broadcast(getInfoWeek('IT'), language='IT', check_notification=True)
        broadcast(getInfoWeek('EN'), language='EN', check_notification=True)


class DayPeopleCountHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        date_counter.addPeopleCount()

'''
class InfodayTiramisuHandler(webapp2.RequestHandler):
    def get(self):
        if key.TEST:
            return
        urlfetch.set_default_fetch_deadline(60)
        tell(key.TIRAMISU_CHAT_ID, getInfoDay('IT'))
'''

'''
class InfoWeekPrices(webapp2.RequestHandler):
    def get(self):
        if key.TEST:
            return
        urlfetch.set_default_fetch_deadline(60)
        msg, debug = getWeekWinners()
        broadcast(msg, language='ALL', check_notification=True, markdown=True)
        tell_masters(debug)
'''

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
        #    return

        #text = message.get('text').encode('utf-8') if "text" in message else ""
        text = message.get('text').encode('utf-8') if "text" in message else ""


        # fr = message.get('from')
        if "chat" not in message:
            return
        chat = message['chat']
        chat_id = chat['id']
        if "first_name" not in chat:
            return
        name = chat["first_name"].encode('utf-8')
        last_name = chat["last_name"].encode('utf-8') if "last_name" in chat else "-"
        username = chat["username"].encode('utf-8') if "username" in chat else "-"
        text_location = message["location"] if "location" in message else None
        voice = message["voice"] if "voice" in message else None

        def reply(msg=None, kb=None, markdown=False, inlineKeyboardMarkup=False):
            tell(chat_id, msg, kb=kb, markdown=markdown, inlineKeyboardMarkup=inlineKeyboardMarkup)

        def replyLocation(location):
            sendLocation(chat_id, location)

        p = ndb.Key(Person, str(chat_id)).get()

        setLanguage(p.language if p is not None else None)

        INSTRUCTIONS =  (_("PickMeUp is a non-profit carpooling service (just like BlaBlaCar but for small journeys within a city).") + "\n\n" +
                         _("You need to agree on terms and conditions in SETTINGS  and insert an ITINERARY to start a new journey.") + "\n" +
                         _("Once all is set, you can press START to request or offer a ride.") + "\n\n" +
                         _("Please visit our website at http://pickmeup.trentino.it " +
                           "read the pdf instructions at http://tiny.cc/pickmeup_info " +
                           "and if you want to promote this initiative do like us on FaceBook https://www.fb.com/321pickmeup ") + "\n\n" +
                         _("If you want to join our discussions come to the tiramisu group at the following link: " +
                           "https://telegram.me/joinchat/B8zsMQBtAYuYtJMj7qPE7g") + "\n\n" +
                         _("Any feedback or contribution is highly appreciated (go to INFO -> SEND FEEDBACK)! :D")) #.encode('utf-8')

        TERMS_AND_CONDITIONS = (_("PickMeUp is a dynamic carpooling system, like BlaBlaCar but within the city.") + "\n" +
                                _("It is currently  under testing.") + "\n\n" +
                                _("WARNINGS:") + "\n" +
                                _("Drivers: please offer rides before starting the ride. " +
                                  "DO NOT use your phone while you drive.") + "\n" +
                                _("Passengers: please ask for rides when you are at the bus stop. ") +
                                _("Be kind with the driver and the other passengers.") + "\n\n" +
                                _("PickMeUp is a non-profit service and it is totally money-free between passengers and drivers.") + "\n" +
                                _("The current version is under testing: ") +
                                _("no review system has been implemented yet and ride traceability is still limited. ") + "\n\n" +
                                _("PickMeUp developers decline any responsibility for the use of the service.") + "\n" +
                                _("If you want to use this service you have to agree on these terms by pressing the button below."))

        MESSAGE_FOR_FRIENDS = _("Hi, I've discovered @PickMeUp_bot a free capooling service via Telegram! ") +\
                              _("It's like BlaBlaCar, but for commuting within a city. ") + \
                              _("The system is currently under testing but the community is getting larger every day. ") + \
                              _("You can try it by clicking on @PickMeUp_bot and press START! ")

        PAPER_CLIP_INSTRUCTIONS = _("Please attach a location by 1) pressing the ") + emoij.PAPER_CLIP +\
                                  _(" icon below and 2) chosing a position in the map.")

        if p is None:
            if text.startswith("/start"):
                p = person.addPerson(chat_id, name)
                registerUser(p, name, last_name, username)
                restartUser(p)
                # state = -2
                tell_masters("New user: " + name)
            else:
                reply("Premi su /start se vuoi iniziare. "
                      "Se hai qualche domanda o suggerimento non esitare di contattarmi cliccando su @kercos")
        else:
            # known user
            person.updateUsername(p, username)
            if text.startswith("/start"):
                reply(_("Hi") + ' ' + name + ", " + _("welcome back!"))
                registerUser(p, name, last_name, username)
                restartUser(p)
                # state = -2
            elif text=='/state':
                if p.state in STATES:
                    reply("You are in state " + str(p.state) + ": " + STATES[p.state])
                else:
                    reply("You are in state " + str(p.state))
            elif p.state == -2:
                if text in ['/help', HELP_BUTTON]:
                    reply(INSTRUCTIONS)
                elif text == INFO_BUTTON_FUNC():
                    goToInfoPanel(p)
                    # state = 80
                elif text == SETTINGS_BUTTON_FUNC():
                    goToSettings(p)
                    # state = 90
                elif text == INVITE_FRIEND_BUTTON_FUNC():
                    reply(_('Forward the following message to your friends.'))
                    reply(MESSAGE_FOR_FRIENDS)
                else:
                    reply(_("Sorry, I don't understand you"))
                    restartUser(p)
            elif p.state == -1:
                # INITIAL STATE WITH START
                if text in ['/help', HELP_BUTTON]:
                    reply(INSTRUCTIONS)
                elif text in [START_BUTTON]:
                    #registerUser(p, name, last_name, username)
                    start(p)
                    # state = 0 or state=-55 in turk mode active
                elif text == INFO_BUTTON_FUNC():
                    goToInfoPanel(p)
                    # state = 80
                elif text == SETTINGS_BUTTON_FUNC():
                    goToSettings(p)
                    # state = 90
                elif text == INVITE_FRIEND_BUTTON_FUNC():
                    reply(_('Forward the following message to your friends.'))
                    reply(MESSAGE_FOR_FRIENDS)
                elif text == '/users':
                    reply(getUsers())
                elif text == '/alldrivers':
                    reply(person.listAllDrivers())
                elif text == '/allpassengers':
                    reply(person.listAllPassengers())
                elif chat_id in key.MASTER_CHAT_ID:
                    if text == '/turkOn' and chat_id==key.TURK_ID:
                        boolVariable.enableTurkMode()
                        reply('Turk Mode Activated, to disable type /turkOff\n'
                              'Other commands are /activeDrivers /activePassengers /sendText [user_id] [msg]', kb=[])
                        person.setState(p, -50)
                    elif text == '/initbot':
                        itinerary.initBusStops(delete=True)
                        counter.resetCounter(delete=True)
                        itinerary.initBasicRoutes(delete=True)
                        boolVariable.disableTurkMode()
                        reply('Succeffully initialized bot!')
                    elif text.startswith('/restart '):
                        # restart single user
                        restartSingleUser(p, text)
                    elif text=='/infocount':
                        reply(getInfoCount())
                    elif text=='/checkenabled':
                        checkEnabled()
                    elif text == '/resetcounters':
                        counter.resetCounter()
                    elif text.startswith('/sendText'):
                        sendText(p, text, markdown=True)
                    elif text == '/resetBusStopsAndCounters':
                        itinerary.initBusStops()
                        counter.resetCounter()
                        reply('Succeffully reinitiated bus stops and counters')
                    elif text == '/resetBasicRoutes':
                        itinerary.initBasicRoutes()
                        reply('Succeffully reinitiated basic routes')
                    elif text == '/test':
                        return
                        #km = test_Google_Map_Api()
                        #reply('test ok: ' + str(km))
                    elif text == '/testBus':
                        testOrariBus(p)
                    elif text == '/testDate':
                        nowTxt = time_util.get_date_string(time_util.now())
                        reply("Now: " + nowTxt)
                    elif text.startswith('/tellRecentDrivers '):
                        msg = text[19:]
                        deferred.defer(sendRecentDriversMessage, 100, msg)
                    elif text == '/getAllInfo':
                        reply(getInfoAllRequestsOffers())
                    elif text.startswith('/broadcastRestart ') and len(text) > 18:
                        msg = text[18:]  # .encode('utf-8')
                        deferred.defer(broadcast, msg, check_notification=True, restart=True)
                    elif text.startswith('/broadcast ') and len(text)>11:
                        msg = text[11:] #.encode('utf-8')
                        deferred.defer(broadcast, msg, check_notification=True)
                    elif text.startswith('/broadcast_it ') and len(text)>14:
                        msg = text[14:] #.encode('utf-8')
                        deferred.defer(broadcast, msg, 'IT', check_notification=True)
                    elif text.startswith('/broadcast_en ') and len(text)>14:
                        msg = text[14:] #.encode('utf-8')
                        deferred.defer(broadcast, msg, 'EN', check_notification=True)
                    elif text.startswith('/self ') and len(text)>6:
                        msg = text[6:] #.encode('utf-8')
                        tellmyself(p,msg)
                    elif text=='/getInfoWeek':
                        tellmyself(p, getInfoWeek('EN'))
                    elif text=='/getWeekWinners':
                        msg, debug = getWeekWinners()
                        tell(p.chat_id, msg + "\n" + debug, markdown=True)
                    else:
                        reply('Sorry, I only understand /help /start '
                              '/users and other secret commands...')
                    #setLanguage(d.language)
                else:
                    reply(_("Sorry, I don't understand you"))
                    restartUser(p)
            elif p.state == 0:
                # AFTER TYPING START
                if text.endswith(_("Passenger")):
                    person.setType(p, text)
                    goToState20(p)
                elif text.endswith(_("Driver")):
                #elif text == emoij.CAR + _(' ') + _("Driver"):
                    person.setType(p, text)
                    goToState30(p)
                elif text == ABORT_BUTTON_FUNC():
                #elif text == emoij.NOENTRY + _(' ') + _("Abort"):
                    reply(_("Passage aborted."))
                    restartUser(p)
                    # state = -1
                else: reply(_("Sorry, I don't understand you"))
            #else:
            #    tell(p, "Sorry system under maintanance, we will be back soon.")
            #    restartUser(p)
            #    return
            elif p.state == 20:
                # PASSANGERS, ASKED FOR LOCATION
                if text == CHANGE_ITINERARY_BUTTON_FUNC():
                    goToSettingItinerary(p)
                    # state = 93
                elif text == CHANGE_START_BUTTON_FUNC():
                    replyListItineraryBusStops(p, 201)
                elif text == CHANGE_END_BUTTON_FUNC():
                    replyListItineraryBusStops(p, 202)
                elif text in [p.getBusStartStr(), p.getBusEndStr()]:
                    person.setLocation(p, text)
                    person.updateLastSeen(p)
                    ticket_id = assignNextTicketId(p, is_driver=False)
                    reply(_("Your passenger ID is: ") + ticket_id.encode('utf-8'))
                    connect_with_matching_drivers(p)
                    ride_request.recordRideRequest(p)
                    # updateDashboard()
                    # state = 21 or 22 depending if driver available
                elif text == ABORT_BUTTON_FUNC():
                    reply(_("Passage aborted."))
                    restartUser(p)
                    # state = -1
                else: reply(_("Sorry, I don't understand you") + _(' '))
                            #p.getBusStart() + _(' ') + _("or") + _(' ') + p.getBusEnd() + '?')
            elif p.state == 201:
                # PASSANGERS, ASKED FOR CHANGING START LOCATION
                if text == BACK_BUTTON_FUNC():
                    goToState20(p)
                    # state = 9351
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    itinerary.setBasicRoute(p, p.basic_route)
                    person.setBusStopStart(p,text) #,swap_active=True
                    reply(_("Successfully changed the START location!"))
                    goToState20(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 202:
                # PASSANGERS, ASKED FOR CHANGING END LOCATION
                if text == BACK_BUTTON_FUNC():
                    goToState20(p)
                    # state = 9351
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    person.setBusStopEnd(p,text) #,swap_active=True
                    reply(_("Successfully changed the END location!"))
                    goToState20(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 21:
                # PASSENGERS IN A LOCATION WITH NO DRIVERS
                if text == ABORT_BUTTON_FUNC():
                    reply(_("Passage aborted."))
                    ride_request.abortRideRequest(p, auto_end=False)
                    removePassenger(p)
                    # state = -1
                elif text==(_('Show Bus Times')) and p.last_city == itinerary.CITY_TRENTO:
                    tellBusTimes(p)
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 22:
                # PASSENGERS NOTIFIED THERE IS A DRIVER
                if text == _('Got the Ride!'):
                    askToSelectDriverByNameAndId(p)
                    #state = 23
                elif text == _('List Drivers'):
                    reply(listDrivers(p))
                elif text == ABORT_BUTTON_FUNC():
                    reply(_("Passage aborted."))
                    ride_request.abortRideRequest(p, auto_end=False)
                    removePassenger(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 23:
                # PASSENGERS WHO JUST CONFIRMED A RIDE
                if text == _('Someone else'):
                    reply(_("Thanks, have a good ride!"))
                    #recordRide('Other',-1, p.last_seen,p.location)
                    #addPassengerInRide(None, p)
                    ride_request.confirmRideRequest(p, None)
                    removePassenger(p)
                elif text == ABORT_BUTTON_FUNC():
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
                        tell(d.chat_id, p.getFirstName() + _(' ') + _("confirmed you gave him/her a ride!"),
                             kb=[[_('List Passengers'), _('Reached Destination!')]]) #[ABORT_BUTTON_FUNC()]
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
                #logging.debug('start: ' + p.getBusStart() + ' ' + str(type(p.getBusStart())))
                #logging.debug('destination: ' + p.getBusEnd() + ' ' + str(type(p.getBusEnd())))
                if text == CHANGE_ITINERARY_BUTTON_FUNC():
                    goToSettingItinerary(p)
                    # state = 93
                elif text == CHANGE_START_BUTTON_FUNC():
                    replyListItineraryBusStops(p, 301)
                elif text == CHANGE_END_BUTTON_FUNC():
                    replyListItineraryBusStops(p, 302)
                elif text in [p.getBusStartStr(), p.getBusEndStr()]:
                    person.setLocation(p, text)
                    # CHECK AND NOTIFY PASSENGER WAIING IN THE SAME LOCATION
                    reply(_("In how many minutes will you be there?"),
                          kb=[['0','5','10','15'],[_('Schedule Trip')],[ABORT_BUTTON_FUNC()]])
                    person.setState(p, 31)
                    # state = 31
                elif text == ABORT_BUTTON_FUNC():
                    reply(_("Passage offer has been aborted."))
                    restartUser(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
                    #reply("Eh? " + p.getBusStart() + _("or") + p.getBusEnd() + "?")
            elif p.state == 301:
                # PASSANGERS, ASKED FOR CHANGING START LOCATION
                if text == BACK_BUTTON_FUNC():
                    goToState30(p)
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    person.setBusStopStart(p,text) #,swap_active=True
                    reply(_("Successfully changed the START location!"))
                    goToState30(p)
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 302:
                # PASSANGERS, ASKED FOR CHANGING END LOCATION
                if text == BACK_BUTTON_FUNC():
                    goToState30(p)
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    person.setBusStopEnd(p,text) #,swap_active=True
                    reply(_("Successfully changed the END location!"))
                    goToState30(p)
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 31:
                # DRIVERS ASEKED FOR TIME
                if text in ['0','5','10','15']:
                    person.setLastSeen(p, time_util.now(addMinutes=int(text)))
                    ticket_id = assignNextTicketId(p, is_driver=True)
                    reply(_("Your driver ID is: ") + ticket_id.encode('utf-8') + '\n')
                    connect_with_matchin_passengers(p)
                    deferred.defer(notify_potential_passengers,p)
                    ride.recordRide(p, int(text))
                    person.setState(p, 32)
                    person.setActive(p, True)
                    # state = 32
                elif text==_('Schedule Trip'):
                    if (p.username and p.username!='-'):
                        reply(_("You can now schedule a trip in the next 24h. "
                                "Please enter a time in the format HH:MM."),
                              kb=[[ABORT_BUTTON_FUNC()]])
                        person.setState(p, 315)
                    else:
                        reply(_("You need a public username to schedule a trip, "
                                "please add it in your Telegram settings and press on 'Schedule Trip'."),
                                kb=[[_('Schedule Trip')],[ABORT_BUTTON_FUNC()]])
                elif text == ABORT_BUTTON_FUNC():
                    reply(_("Passage offer has been aborted."))
                    restartUser(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 315:
                # Choose time
                if (len(text)==5 and time_util.isTimeFormat(text)):
                    deferred.defer(notify_potential_passengers,p, time=text)
                    reply(_("Thanks for scheduling the trip! "))
                    restartUser(p)
                elif text == ABORT_BUTTON_FUNC():
                    reply(_("Passage offer has been aborted."))
                    restartUser(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you. Please enter a time in the format HH:MM."))
            elif p.state == 32:
                # DRIVERS WHO HAS LEFT
                if text == _('List Passengers'):
                    reply(listPassengers(p))
                elif text == (_('Send Message')):
                    reply(_("Please type a short message which will be sent to all passengers matching your journey"),
                        kb=[[emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                    person.setState(p, 325)
                elif text == ABORT_BUTTON_FUNC():
                    reply(_("Passage offer has been aborted."))
                    ride.abortRideOffer(p, False)
                    removeDriver(p)
                    # state = -1
                else:
                    reply(_("Sorry, I don't understand you"))# (" + text + ")")
            elif p.state == 325:
                if not text == BACK_BUTTON_FUNC():
                    count = broadcast_driver_message(p, text)
                    reply(_("Sent message to ") + str(count) + _(" people"))
                if hasMatchingPassengers(p):
                    reply(_("There is some passenger(s) matching your journing ") + emoij.PEDESTRIAN,
                          kb=[[_('List Passengers'), _('Send Message')],[ABORT_BUTTON_FUNC()]])
                else:
                    reply(_("Oops... there are no more passengers matching your journing!"),
                          kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
                    # all passangers have left while driver was typing
                person.setState(p, 32)
            elif p.state == 33:
                # DRIVER WHO HAS JUST BORDED AT LEAST A PASSANGER
                if text == _('List Passengers'):
                    reply(listPassengers(p))
                elif text == _('Reached Destination!'):
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
                    # restartUser(p)
                    # state = -1
                elif text==_('DAY SUMMARY'):
                    reply(getInfoDay())
                    # restartUser(p)
                    # state = -1
                elif text==_('SEARCH BUS STOPS'):
                    reply(PAPER_CLIP_INSTRUCTIONS + ' ' +
                          _("I will give you a list of bus stops within a radius of 10 km from the given location."),
                          kb=[[BACK_BUTTON_FUNC()]])
                    person.clearTmp(p)
                    person.setState(p, 81)
                elif text==_('SEND FEEDBACK'):
                    reply(_("Please send us any feedback, e.g., new bus stops, bugs, suggestions. "),
                          kb=[[BACK_BUTTON_FUNC()]])
                    person.setState(p, 82)
                elif text == BACK_BUTTON_FUNC():
                    restartUser(p)
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
                              kb=[[BACK_BUTTON_FUNC()]])
                        person.setState(p,81)
                    else:
                        reply(_("No bus stop found near location, try again. ") + PAPER_CLIP_INSTRUCTIONS)
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    bus_stop = p.tmp[j]
                    replyLocation(itinerary.getBusStopLocation(p.last_city, bus_stop))
                    #reply("Found: " + p.tmp[j])
                    #logging.debug('getBusStopFromCommand')
                    #getBusStopFromCommand(text,p)
                elif text == BACK_BUTTON_FUNC():
                    goToInfoPanel(p)
                    # state = 80
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 82:
                if text == BACK_BUTTON_FUNC():
                    goToInfoPanel(p)
                    # state = 80
                else:
                    mail.send_mail(sender="Federico Sangati <federico.sangati@gmail.com>",
                                   to="PickMeUp <pickmeupbot@gmail.com>",
                                   subject="[Feedback] from user " + p.getFirstName() + ' (' + str(p.chat_id) + ')', body=text)
                    reply(_("Thanks for your feedback!"))
                    goToInfoPanel(p)
            elif p.state == 90:
                #SETTINGS
                if text==_('TERMS AND CONDITIONS'):
                    reply(TERMS_AND_CONDITIONS, kb=[[_('I AGREE')],[BACK_BUTTON_FUNC()]])
                    person.setState(p, 92)
                elif text==ITINERARY_BUTTON_FUNC():
                    goToSettingItinerary(p)
                    # state = 93
                elif text==NOTIFICATIONS_BUTTON_FUNC():
                    goToSettingNotification(p)
                    # state = 94
                elif text==LANGUAGE_BUTTON_FUNC():
                    reply(_('Choose the language'),
                          kb=[[flag + _(' ') + name for (name,flag) in LANGUAGE_FLAGS.iteritems()],
                              [BACK_BUTTON_FUNC()]])
                    person.setState(p, 91)
                elif text == BACK_BUTTON_FUNC():
                    restartUser(p)
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
                    restartUser(p)
                elif text == BACK_BUTTON_FUNC():
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 92:
                #AGREE ON TERMS
                if text==_('I AGREE'):
                    person.setAgreeOnTerms(p)
                    reply(_("Thanks for agreeing on terms!"))
                    goToSettings(p)
                    # state = 90
                elif text == BACK_BUTTON_FUNC():
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state ==93:
                #ITINERARY
                if text==_('Change City'):
                    goToChangeCity(p)
                    #state = 930
                elif text==_('ITINERARY (simple)'):
                    goToSettingItinerarySimple(p)
                    # state = 931
                elif text==_('ITINERARY (advanced)'):
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                elif text == BACK_BUTTON_FUNC():
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state ==930:
                #ITINERARY CHANGE CITY
                if text in itinerary.CITIES:
                    person.setLastCity(p, text)
                    #logging.debug(p.last_city)
                    reply(_("Successfully set city to: ") + p.last_city.encode('utf-8'))
                    goToSettingItinerary(p)
                    # state = 931
                elif text == BACK_BUTTON_FUNC():
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 931:
                #ITINERARY SIMPLE
                if text.startswith('/'):
                    commandList = itinerary.getBasicRoutesCommands(p.last_city)
                    commands = '\n\n'.join(commandList)
                    if text in commands:
                        itinerary.setBasicRoute(p,text)
                        reply(_('Successfully set the route: ') + p.getBusStartStr() + ' <-> ' + p.getBusEndStr())
                        restartUser(p)
                        # state = -1
                    else:
                        reply(_("Sorry, I don't understand you"))
                elif text == BACK_BUTTON_FUNC():
                    goToSettingItinerary(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 935:
                #ITINERARY ADVANCED
                # from 93,
                if text in [_('Set Start Location'),_('Change Start Location')]:
                    askToInsertLocation(p, _('the START location'), 9351, PAPER_CLIP_INSTRUCTIONS)
                    # state = 9351
                elif text in [_('Set End Location'),_('Change End Location')]:
                    askToInsertLocation(p, _('the END location'), 9352, PAPER_CLIP_INSTRUCTIONS)
                    # state = 9352
                elif text==_('Change Mid Points Going'):
                    goToSettingMidPoints(p,9353,PAPER_CLIP_INSTRUCTIONS)
                    # state = 9353
                elif text==_('Change Mid Points Back'):
                    goToSettingMidPoints(p,9354,PAPER_CLIP_INSTRUCTIONS)
                    # state = 9354
                elif text == BACK_BUTTON_FUNC():
                    goToSettingItinerary(p)
                    # state = 93
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9351:
                #ITINERARY ADVANCED START LOCATION
                if text == _('List All Stops'):
                    replyListAllBusStops(p, 93511)
                elif text == _('List Itinerary Stops'):
                    replyListItineraryBusStops(p, 93511)
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    exluded_points = [] #[p.getBusEnd()]
                    bus_stops = itinerary.getClosestBusStops(loc_point, exluded_points, p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [emoij.LEFTWARDS_BLACK_ARROW + _(' ') + _("Back")]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,93511)
                    else:
                        reply(_("No bus stop found near location, try again. ") + PAPER_CLIP_INSTRUCTIONS)
                elif text == BACK_BUTTON_FUNC():
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 93511:
                #ITINERARY ADVANCED CHECK START LOCATION
                #logging.debug("text: " + text)
                #logging.debug("tmp: " + str(p.tmp))
                if text == BACK_BUTTON_FUNC():
                    askToInsertLocation(p, _('the START location'), 9351, PAPER_CLIP_INSTRUCTIONS)
                    # state = 9351
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    person.setBusStopStart(p,text) #,swap_active=True
                    reply(_("Thanks for setting the START location!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9352:
                #ITINERARY ADVANCED END LOCATION
                if text == _('List All Stops'):
                    replyListAllBusStops(p, 93521)
                elif text == _('List Itinerary Stops'):
                    replyListItineraryBusStops(p, 93521)
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    exluded_points = [] #[p.getBusStart()]
                    bus_stops = itinerary.getClosestBusStops(loc_point, exluded_points, p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [BACK_BUTTON_FUNC()]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,93521)
                    else:
                        reply(_("No bus stop found near location, try again. ") + PAPER_CLIP_INSTRUCTIONS)
                elif text == BACK_BUTTON_FUNC():
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 93521:
                #ITINERARY ADVANCED CHECK END LOCATION
                if text == BACK_BUTTON_FUNC():
                    askToInsertLocation(p, _('the END location'), 9352, PAPER_CLIP_INSTRUCTIONS)
                    # state = 9352
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    person.setBusStopEnd(p,text) #,swap_active=True
                    reply(_("Thanks for setting the END location!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9353:
                #ITINERARY ADVANCED MID POINT GOING
                if text == _('List All Stops'):
                    replyListAllBusStops(p, 93531)
                elif text == _('Remove all'):
                    person.emptyBusStopMidGoing(p)
                    reply(_("All mid points on the way FORWARD have been removed."))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                elif text == _('Same as other direction'):
                    p.bus_stop_mid_going = list(reversed(p.bus_stop_mid_back))
                    p.put()
                    reply(_("Successfully set mid points way FORWARD as in way BACK!"))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    exluded_points = [] #[p.getBusStart(), p.getBusEnd()]
                    bus_stops = itinerary.getClosestBusStops(loc_point, exluded_points, p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [BACK_BUTTON_FUNC()]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,93531)
                    else:
                        reply(_("No bus stop found near location, try again. ") +
                              PAPER_CLIP_INSTRUCTIONS)
                elif text == BACK_BUTTON_FUNC():
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 93531:
                #ITINERARY ADVANCED CHECK MID POINT GOING
                if text == BACK_BUTTON_FUNC():
                     goToSettingMidPoints(p,9353,PAPER_CLIP_INSTRUCTIONS)
                    # state = 9353
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    person.appendBusStopMidGoing(p,text)
                    reply(_("Thanks for adding a new mid point!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 9354:
                #ITINERARY ADVANCED MID POINT BACK
                if text == _('List All Stops'):
                    replyListAllBusStops(p, 93541)
                elif text == _('Remove all'):
                    person.emptyBusStopMidBack(p)
                    reply(_("All mid points on the way BACK have been removed."))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                elif text == _('Same as other direction'):
                    p.bus_stop_mid_back = list(reversed(p.bus_stop_mid_going))
                    p.put()
                    reply(_("Successfully set mid points way BACK as in way FORWARD!"))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                elif text_location!=None:
                    loc_point = ndb.GeoPt(text_location['latitude'], text_location['longitude'])
                    exluded_points = [] #[p.getBusStart(), p.getBusEnd()]
                    bus_stops = itinerary.getClosestBusStops(loc_point, exluded_points, p)
                    if len(bus_stops)>0:
                        reply(_("Found the following bus stop(s) near the location, please make one selection."),
                              kb=[bus_stops, [BACK_BUTTON_FUNC()]])
                        person.setTmp(p,bus_stops)
                        person.setState(p,93541)
                    else:
                        reply(_("No bus stop found near location, try again. ") +
                              PAPER_CLIP_INSTRUCTIONS)
                elif text == BACK_BUTTON_FUNC():
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 93541:
                #ITINERARY ADVANCED CHECK MID POINT BACK
                if text == BACK_BUTTON_FUNC():
                    goToSettingMidPoints(p,9354,PAPER_CLIP_INSTRUCTIONS)
                    # state = 9354
                elif text in p.tmp:
                    i = p.tmp.index(text)
                    j = len(p.tmp)//2+i
                    text = p.tmp[j]
                    person.appendBusStopMidBack(p,text)
                    reply(_("Thanks for adding a new mid point!"))
                    replyLocation(itinerary.getBusStopLocation(p.last_city, text))
                    goToSettingItineraryAdvanced(p)
                    # state = 935
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == 94:
                #NOTIFICATIONS
                if text == ENABLE_NOTIFICATIONS_BUTTON_FUNC():
                    person.setNotifications(p,True)
                    goToSettingNotification(p)
                    # state = 94
                elif text== DISABLE_NOTIFICATIONS_BUTTON_FUNC():
                    person.setNotifications(p,False)
                    goToSettingNotification(p)
                    # state = 94
                elif text == BACK_BUTTON_FUNC():
                    goToSettings(p)
                    # state = 90
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == -50:
                # TURK MODE MASTER
                if text == '/turkOff':
                    boolVariable.disableTurkMode()
                    reply("Turk mode disabled")
                    restartUser(p)
                    deferred.defer(restartUserInTurkMode)
                elif text == '/activeDrivers':
                    reply(listActiveDrivers())
                elif text == '/activePassengers':
                    reply(listActivePassengers())
                elif text.startswith('/sendText'):
                    sendText(p, text, markdown=True)
                else:
                    reply(_("Sorry, I don't understand you"))
            elif p.state == -55:
                # turk mode user
                if voice!=None:
                    file_id = voice['file_id']
                    tell(key.TURK_ID, p.getFirstName() + '(' + str(p.chat_id) + ") sent you this recording:")
                    sendVoice(key.TURK_ID, file_id)
                    reply(_("Successfully sent message to the bot, you will receive an answer shortly."))
                elif text==ABORT_BUTTON_FUNC():
                    reply(_("Passage offer has been aborted."))
                    restartUser(p)
                elif text:
                    tell(key.TURK_ID, p.getFirstName()
                         + ' (' + str(p.chat_id) + ") sent you this message: "
                         + text)
                    reply(_("Successfully sent message to the bot, you will receive an answer shortly."))
                # TURK MODE USER
                else:
                    reply(_("Sorry, I don't understand you"))
            else:
                reply(_("Something is wrong with your state (") + str(p.state).encode('utf-8') +
                      _(").") + _("I'm going to bring you back to the initial screen. ") +
                      _("If the problem presists, please write a message to @kercos"))
                restartUser(p)

    def handle_exception(self, exception, debug_mode):
        logging.exception(exception)
        tell(key.FEDE_CHAT_ID, "❗ Detected Exception: " + str(exception))

app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    ('/dashboard', DashboardHandler),
#    ('/_ah/channel/connected/', DashboardConnectedHandler),
#    ('/_ah/channel/disconnected/', DashboardDisconnectedHandler),
    ('/notify_token', GetTokenHandler),
    ('/updates', GetUpdatesHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/webhook', WebhookHandler),
    #('/infousers_tiramisu', InfouserTiramisuHandler),
    #('/infouser_weekly_all', InfouserAllHandler),
    # ('/infoday_tiramisu', InfodayTiramisuHandler),
    ('/infoweek_all', InfoWeekAllHandler),
    #('/infoweek_all', InfoWeekPrices),
    ('/resetcounters', ResetCountersHandler),
    ('/checkExpiredUsers', CheckExpiredUsersHandler),
    ('/restartOldUsers', RestartOldUsersHandler),
    ('/tiramisulottery', TiramisuHandler),
    ('/dayPeopleCount', DayPeopleCountHandler),
    ('/newVersionBroadcast', NewVersionBroadcastHandler),
], debug=True)
