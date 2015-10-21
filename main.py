import json
import logging
import urllib
import urllib2
import datetime
from time import sleep
# import requests

import key
import emoij

# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
import webapp2

# import sys, gettext
# kwargs = {}
# if sys.version_info[0] < 3:
#     # In Python 2, ensure that the _() that gets installed into built-ins
#     # always returns unicodes.  This matches the default behavior under Python
#     # 3, although that keyword argument is not present in the Python 3 API.
#     kwargs['unicode'] = True
# gettext.install("PickMeUp", **kwargs)

import gettext

# ================================

class Counter(ndb.Model):
    name = ndb.StringProperty()
    counter = ndb.IntegerProperty()

# ================================

MAX_WAITING_TIMEOUT_MIN = 2

QUEUE_COUNTER_POVO = 'Queue_Counter_Povo'
QUEUE_COUNTER_TRENTO = 'Queue_Counter_Trento'
TN_PV_CURRENT_RIDES = 'tn_pv_current_rides'
TN_PV_TOTAL_RIDES = 'tn_pv_total_rides'
TN_PV_TOTAL_PASSENGERS = 'tn_pv_total_passengers'
PV_TN_CURRENT_RIDES = 'pv_tn_current_rides'
PV_TN_TOTAL_RIDES = 'pv_tn_total_rides'
PV_TN_TOTAL_PASSENGERS = 'pv_tn_total_passengers'

COUNTERS = [QUEUE_COUNTER_POVO, QUEUE_COUNTER_TRENTO,
            TN_PV_CURRENT_RIDES, TN_PV_TOTAL_RIDES, TN_PV_TOTAL_PASSENGERS,
            PV_TN_CURRENT_RIDES, PV_TN_TOTAL_RIDES, PV_TN_TOTAL_PASSENGERS]
FERMATA_TRENTO = 'Trento (bus stop A)'
FERMATA_POVO = 'Povo (bus stop B)'

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

def addRide(driver):
    riders_current_counter = TN_PV_CURRENT_RIDES if driver.location == FERMATA_TRENTO else PV_TN_CURRENT_RIDES
    increaseCounter(riders_current_counter, 1)
    riders_tot_current_counter = TN_PV_TOTAL_RIDES if driver.location == FERMATA_TRENTO else PV_TN_TOTAL_RIDES
    increaseCounter(riders_tot_current_counter, 1)

def removeRide(driver):
    riders_current_counter = TN_PV_CURRENT_RIDES if driver.location == FERMATA_TRENTO else PV_TN_CURRENT_RIDES
    increaseCounter(riders_current_counter, -1)

def addPassengerRide(passenger):
    passenger_tot_counter = TN_PV_TOTAL_PASSENGERS if passenger.location == FERMATA_TRENTO else PV_TN_TOTAL_PASSENGERS
    increaseCounter(passenger_tot_counter, 1)

# ================================

BASE_URL = 'https://api.telegram.org/bot' + key.TOKEN + '/'

STATES = {
    -1: 'Initial',
    0:   'Started',
    20:  'PassengerAskedForLoc',
    21:  'PassengerBored',
    22:  'PassengerEngaged',
    23:  'PassengerConfirmedRide',
    30:  'DriverAskedForLoc',
    305: 'DriverAskedForTime',
#    31:  'DriverOnHold',
    32:  'DriverEngaged',
    33:  'DriverTookSomeone',
    90:  'LanguageSettings'
}

LANGUAGES = {'IT': 'it_IT',
             'EN': 'en',
             'FR': 'fr_FR',
             'DE': 'de',
             'NL': 'nl',
             'PL': 'pl',
             'RU': 'ru'}

# ================================

class Person(ndb.Model):
    name = ndb.StringProperty()
    last_name = ndb.StringProperty(default='-')
    last_mod = ndb.DateTimeProperty(auto_now=True)
    last_seen = ndb.DateTimeProperty()
    chat_id = ndb.IntegerProperty()
    state = ndb.IntegerProperty()
    last_type = ndb.StringProperty(default='-1')
    location = ndb.StringProperty(default='-')
    language = ndb.StringProperty(default='IT')
    enabled = ndb.BooleanProperty(default=True)

# ================================


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

def start(p, cmd, name, last_name):
    logging.debug(p.name + _(' ') + cmd + _(' ') + str(p.enabled))
    if (p.name != name or p.last_name != last_name):
        p.name = name
        p.last_name = last_name
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

def get_date_string(date):
    newdate = date + datetime.timedelta(hours=2)
    time_day = str(newdate).split(" ")
    time = time_day[1].split(".")[0]
    day = time_day[0]
    return day + " " + time

def get_time_string(date):
    newdate = date + datetime.timedelta(hours=2)
    return str(newdate).split(" ")[1].split(".")[0]

def restartAllUsers():
    qry = Person.query()
    for p in qry:
        if (p.state>-1):
            tell(p.chat_id, _("Your ride has been aborted by the system manager"))
            restart(p)

def resestLanguages():
    qry = Person.query()
    for p in qry:
        p.language = 'IT'
        p.put()

def resestEnabled():
    qry = Person.query()
    for p in qry:
        p.enabled = True
        p.put()

def resestLastNames():
    qry = Person.query()
    for p in qry:
        p.last_name = '-'
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
        sleep(0.100) # no more than 10 messages per second

def broadcast(msg):
    qry = Person.query().order(-Person.last_mod)
    for p in qry:
        if (p.enabled):
            tell(p.chat_id, _("Listen listen...") + _(' ') + msg)
            sleep(0.100) # no more than 10 messages per second

def tellmyself(p, msg):
    tell(p.chat_id, "Listen listen... " + msg)


def restart(person):
    #tell(person.chat_id, "Press START if you want to restart.", kb=[['START', 'HELP'],['SETTINGS']])
    tell(person.chat_id, _("Press START if you want to restart"), kb=[['START'],['HELP','LANGUAGE']])
    setStateLocation(person, -1, '-')


#def putDriverOnHold(driver):
#    tell(driver.chat_id, "No passanger needs a ride for the moment. Waiting...", kb=[[emoij.NOENTRY + ' ' + _("Abort")]])
#    setState(driver, 31)

def putPassengerOnHold(passenger):
    passenger.last_seen = datetime.datetime.now()
    tell(passenger.chat_id, _("Waiting for a driver..."), kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
    setState(passenger, 21)

def check_available_drivers(passenger):
    # a passenger is at a certain location and we want to check if there is a driver bored or engaged
    #passenger.last_seen = datetime.datetime.now()
    qry = Person.query(Person.location == passenger.location, Person.state.IN([32,33])) #31
    counter = 0
    oldDrivers = {
        32: [],
        33: []
    }
    for d in qry:
        if (datetime.datetime.now() < d.last_seen + datetime.timedelta(minutes=MAX_WAITING_TIMEOUT_MIN)):
            counter = counter + 1
        else:
            oldDrivers[passenger.state].append(d)
        #    setState(p, 22)
        #tell(p.chat_id, "A driver coming: " + driver.name + " (" + get_time_string(driver.last_mod) + ")",
        #    kb=[['List Drivers', 'Got the Ride!'],[emoij.NOENTRY + _(' ') + _("Abort")]])
    #return qry.get() is not None
    for d in oldDrivers[32]:
        tell(d.chat_id, _("Ride aborted: you were expected to give a ride long time ago!"))
        removeDriver(d)
    for d in oldDrivers[33]:
        tell(d.chat_id, _("Ride complete automatically (you were supposed to arrive long time ago)!"))
        removeDriver(d)
        removeRide(d) # update counter current ride of -1
    return counter > 0

def engageDriver(d, min):
    d.last_seen = datetime.datetime.now() + datetime.timedelta(minutes=min)
    tell(d.chat_id, _("You can go pick up the passenger(s)!")  + _(' ') + emoij.SMILING_FACE,
          kb=[[_("List Passengers")],[emoij.NOENTRY + _(' ') + _("Abort")]])
    qry = Person.query(Person.location == d.location, Person.state.IN([21, 22]))
    for p in qry:
        if (p.state==21):
            setState(p, 22)
        tell(p.chat_id, _("A driver coming:") + _(' ') + d.name + _(' ') + _("expected at") + _(' ') + get_time_string(d.last_seen),
            kb=[[_("List Drivers"), _("Got the Ride!")],[emoij.NOENTRY + _(' ') + _("Abort")]])
    setState(d, 32)

def askDriverTime(d):
    tell(d.chat_id, _("There is someone waiting for you!") + emoij.PEDESTRIAN + _("\n") +
         _("In how many minutes will you be there?"), kb=[['1','5','10'],[emoij.NOENTRY + _(' ') + _("Abort")]])
    setState(d, 305)

def check_available_passenger(driver):
    # a driver is availbale for a location and we want to check if there are passengers bored or engaged
    #driver.last_seen = datetime.datetime.now()
    qry = Person.query(Person.location == driver.location, Person.state.IN([21, 22]))
    counter = 0
    oldPassengers = []
    for p in qry:
        if (datetime.datetime.now() < p.last_seen + datetime.timedelta(minutes=MAX_WAITING_TIMEOUT_MIN)):
            counter = counter + 1
        else:
            oldPassengers.append(p)
        #    setState(p, 22)
        #tell(p.chat_id, "A driver coming: " + driver.name + " (" + get_time_string(driver.last_mod) + ")",
        #    kb=[['List Drivers', 'Got the Ride!'],[emoij.NOENTRY + _(' ') + _("Abort")]])
    #return qry.get() is not None
    for p in oldPassengers:
        gettext.translation('PickMeUp', localedir='locale', languages=[p.language]).install()
        tell(p.chat_id, _("Ride aborted: you have waited for too long!"))
        removePassenger(p)
    return counter > 0

def listDrivers(passenger):
    qry = Person.query(Person.location == passenger.location, Person.state.IN([32,33])) #.order(-Person.last_mod)
    if qry.get() is None:
        return _("No drivers found in your location")
    else:
        text = ""
        for d in qry:
            text = text + d.name + _(' ') + _("expected at") + _(' ') + get_time_string(d.last_seen) + _("\n")
            #" (" + str(d.state) + ") " +
        return text

def listAllDrivers():
    qry = Person.query().filter(Person.state.IN([30, 305, 32, 33])) #31
    if qry.get() is None:
        return "No drivers found"
    else:
        #qry = qry.order(-Person.last_mod)
        text = ""
        for d in qry:
            text = text + d.name + _(' ') + d.location + _(" (") + str(d.state) + _(") ") + get_time_string(d.last_seen) + _("\n")
        return text


def listPassengers(driver):
    qry = Person.query(Person.location == driver.location, Person.state.IN([21, 22, 23])) #.order(-Person.last_mod)
    if qry.get() is None:
        return _("No passengers needing a ride found in your location")
    else:
        text = ""
        for p in qry:
            text = text + p.name + _(' ') + _("waiting since") + _(' ') + get_time_string(p.last_seen) + _("\n")
            #" (" + str(p.state) + ") "
        return text

def listAllPassengers():
    qry = Person.query().filter(Person.state.IN([21, 22, 23]))
    if qry.get() is None:
        return _("No passangers found")
    else:
        #qry = qry.order(-Person.last_mod)
        text = ""
        for p in qry:
            text = text + p.name + _(' ') + p.location + " (" + str(p.state) + ") " + get_time_string(p.last_seen) + _("\n")
        return text

def removePassenger(p, driver=None):
    loc = p.location
    restart(p)
    qry = Person.query().filter(Person.state.IN([21, 22]), Person.location==loc)
    if qry.get() is None:
        # there are no more passengers in that location
        qry = Person.query().filter(Person.state.IN([305,32]), Person.location==loc)
        for d in qry:
            if d!=driver:
                tell(d.chat_id, _("Oops... there are no more passengers waiting!"))
                #putDriverOnHold(d)
                restart(d)

def removeDriver(d):
    loc = d.location
    restart(d)
    qry = Person.query().filter(Person.state.IN([32,33]), Person.location==loc)
    if qry.get() is None:
        # there are no more drivers in that location
        qry = Person.query().filter(Person.state == 22, Person.location==loc)
        for p in qry:
            tell(p.chat_id, _("Oops... the driver(s) is no longer available!"))
            putPassengerOnHold(p)

def askToSelectDriverByName(p):
    qry = Person.query().filter(Person.state.IN([32,33]), Person.location==p.location)
    if qry.get() is None:
        tell(p.chat_id, _("Thanks, have a good ride!")) # cannot ask you which driver cause they are all gone
        removePassenger()
    else:
        buttons = []
        for d in qry:
            buttons.append([d.name])
        buttons.append([_("Someone else")])
        tell(p.chat_id, _("Great, which driver gave you a ride?"), kb=buttons)
        setState(p, 23)

def getDriverByLocAndName(loc, name_text):
    qry = Person.query().filter(Person.location==loc, Person.state.IN([32,33]), Person.name==name_text)
    return qry.get()

def tell_katja_test():
    try:
        tell(114258373, 'test')
    except urllib2.HTTPError, err:
        if err.code == 403:
            e = Person.query(Person.chat_id==114258373).get()
            e.enabled = False
            e.put()


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
            logging.info('Disabled user: ' + p.name + _(' ') + str(chat_id))


# ================================

class MeHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(BASE_URL + 'getMe'))))

class DashboardHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)

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
            "Passengers": {
                "Trento": p_wait_trento,
                "Povo": p_wait_povo
            },
            "Rides TN->PV": {
                "Current rides": r_cur_tn_pv,
#                "Current passengers": p_cur_tn_pv,
                "Total rides": r_tot_tn_pv,
                "Total passangers": p_tot_tn_pv
            },
            "Rides PV->TN": {
                "Current rides": r_cur_pv_tn,
 #               "Current passengers": p_cur_pv_tn,
                "Total rides": r_tot_pv_tn,
                "Total passangers": p_tot_pv_tn
            }
            # "Drivers": {
            #     "Trento": countDrivers(FERMATA_TRENTO),
            #     "Povo": countDrivers(FERMATA_POVO)
            # }
        }
        self.response.write(json.dumps(data))


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
        text = message.get('text').encode('utf-8')
        # fr = message.get('from')
        chat = message['chat']
        chat_id = chat['id']
        name = chat["first_name"].encode('utf-8')
        last_name = chat["last_name"].encode('utf-8') if "last_name" in chat else "-"
        #user_id = chat["id"]

        if not text:
            logging.info('no text')
            return

        def reply(msg=None, kb=None, hideKb=True):
            tell(chat_id, msg, kb, hideKb)

        p = ndb.Key(Person, str(chat_id)).get()

        #gettext.translation('PickMeUp', localedir='locale', languages=['en']).install()

        lang = LANGUAGES[p.language] if p is not None else LANGUAGES['IT']
        #lang = 'en'
        #logging.debug("Language: " + p.language)

        gettext.translation('PickMeUp', localedir='locale', languages=[lang]).install()

        instructions = (_("I\'m your Trento <-> Povo travelling assistant.") + _("\n\n") +
                        _("You can press START to get or offer a ride") + _("\n") +
                        _("You can press HELP to see this message again") + _("\n") +
                        _("You can press LANGUAGE to change the settings (language)") + _("\n\n") +
                        _("If you want to join the discussion about this initiative") + _(" ") +
                        _("come to the tiramisu group at the following link:") + _("\n") +
                        'https://telegram.me/joinchat/B8zsMQBtAYuYtJMj7qPE7g') #.encode('utf-8')

        if p is None:
            # new user
            tell(key.MASTER_CHAT_ID, msg = "New user: " + name)
            p = addPerson(chat_id, name)
            if text == '/help':
                reply(instructions)
            elif text in ['/start','START']:
                start(p, text, name, last_name)
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
                elif text in ['/start','START']:
                    start(p, text, name, last_name)
                    # state = 0
                elif text in ['LANGUAGE']:
                    reply(_("Choose the langauge"),
                          kb=[[emoij.FLAG_IT + _(' ') + "IT", emoij.FLAG_EN + _(' ') + "EN", emoij.FLAG_RU + _(' ') + "RU"],
                              [emoij.FLAG_DE + _(' ') + "DE", emoij.FLAG_FR + _(' ') + "FR", emoij.FLAG_PL + _(' ') + "PL"],
#                             [emoij.FLAG_NL + _(' ') + "NL"
                              [emoij.NOENTRY + _(' ') + _("Abort")]])
                    setState(p, 90)
                elif text == '/users':
                    reply(getUsers())
                elif text == '/alldrivers':
                    reply(listAllDrivers())
                elif text == '/allpassengers':
                    reply(listAllPassengers())
                elif chat_id==key.MASTER_CHAT_ID:
                    if text == '/resetusers':
                        #restartAllUsers()
                        resestLastNames()
                        #resestEnabled()
                        #resestLanguages()
                    elif text=='/checkenabled':
                        checkEnabled()
                    elif text == '/resetcounters':
                        resetCounter()
                    elif text == '/test':
                        tell_katja_test()
                    elif text.startswith('/broadcast ') and len(text)>11:
                        msg = text[11:].encode('utf-8')
                        broadcast(msg)
                    elif text.startswith('/self ') and len(text)>6:
                        msg = text[6:].encode('utf-8')
                        tellmyself(p,msg)
                    else:
                        reply('What command? I only understnad /help /start'
                              '/users /alldrivers /alldrivers '
                              '/checkenabled /resetusers /resetcounters '
                              '/self /broadcast')
                else:
                    reply(_("What command? I only understnad HELP or START."))
            #kb=[[emoij.CAR + _(' ') + _("Driver"), emoij.FOOTPRINTS + _(' ') + _("Passenger")],[emoij.NOENTRY + _(' ') + _("Abort")]])
            elif p.state == 0:
                # AFTER TYPING START
                #logging.debug(text, type(text))
                if text.endswith(_("Passenger")):
                #if text == emoij.FOOTPRINTS + _(' ') + _("Passenger"):
                    setState(p, 20)
                    setType(p, text)
                    reply(_("Hi! I can try to help you to get a ride. Where are you?"),
                          kb=[[FERMATA_TRENTO, FERMATA_POVO],[emoij.NOENTRY + _(' ') + _("Abort")]])
                elif text.endswith(_("Driver")):
                #elif text == emoij.CAR + _(' ') + _("Driver"):
                    setState(p, 30)
                    setType(p, text)
                    reply(_("Hi! Glad you can give a ride. Where are you?"),
                          kb=[[FERMATA_TRENTO, FERMATA_POVO],[emoij.NOENTRY + _(' ') + _("Abort")]])
                elif text.endswith(_("Abort")):
                #elif text == emoij.NOENTRY + _(' ') + _("Abort"):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else: reply(_("Eh? I don't understand you. Are you a Driver or a Passenger?"))
            elif p.state == 20:
                # PASSANGERS, ASKED FOR LOCATION
                if text in [FERMATA_POVO,FERMATA_TRENTO]:
                    setLocation(p, text)
                    if text == FERMATA_POVO:
                        reply(_("Your waiting position is:") + _(' ') + str(increaseQueueCounter(QUEUE_COUNTER_POVO)))
                    else:
                        reply(_("Your waiting position is:") + _(' ') + str(increaseQueueCounter(QUEUE_COUNTER_TRENTO)))
                    if check_available_drivers(p):
                        reply(_("There is a driver coming!"),
                              kb=[[_('List Drivers'), _('Got the Ride!')],[emoij.NOENTRY + _(' ') + _("Abort")]])
                        setState(p, 22)
                    else:
                        putPassengerOnHold(p)
                        # state = 21
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else: reply(_("Eh? I don't understand you.") + _(' ') + FERMATA_TRENTO + _(' ') + _("or") + _(' ') + FERMATA_POVO + '?')
            elif p.state == 21:
                # PASSENGERS IN A LOCATION WITH NO DRIVERS
                if text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    removePassenger(p)
                    #restart(p);
                    # state = -1
                else:
                    reply(_("Eh? If you want to Abort press the button!"), kb=[[emoij.NOENTRY + _(' ') + _("Abort")]])
            elif p.state == 22:
                # PASSENGERS NOTIFIED THERE IS A DRIVER
                if text == _("Got the Ride!"):
                    askToSelectDriverByName(p)
                elif text == _("List Drivers"):
                    reply(listDrivers(p))
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    removePassenger(p)
                    # state = -1
                else:
                    reply(_("Eh? I don't understand you. A driver is supposed to come, be patient!"))
            elif p.state == 23:
                # PASSENGERS WHO JUST CONFIRMED A RIDE
                if text == _('Other'):
                    reply(_("Thanks, have a good ride!"))
                    addPassengerRide(p) # increase counter tot passengers in ride of 1
                    addRide(p) # update counter tot and current ride of 1
                    removePassenger(p)
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    removePassenger(p)
                    # state = -1
                else:
                    d = getDriverByLocAndName(p.location, text)
                    if d is not None:
                        reply(_("Great! Many thanks to") + _(' ') + d.name + "!")
                        tell(d.chat_id, p.name + _(' ') + _("confirmed you gave him/her a ride!"),
                             kb=[[_("List Passengers"), _("Reached Destination!")]]) #[emoij.NOENTRY + _(' ') + _("Abort")]
                        if (d.state==32):
                            setState(d, 33)
                            addRide(d) # update counter tot and current ride of 1
                        addPassengerRide(p)
                        removePassenger(p, driver=d)
                        # passenger state = -1
                    else:
                        reply(_("Name of driver not correct, try again."))
            elif p.state == 30:
                # DRIVERS, ASKED FOR LOCATION
                if text in [FERMATA_POVO,FERMATA_TRENTO]:
                    setLocation(p, text)
                    # CHECK AND NOTIFY PASSENGER WAIING IN THE SAME LOCATION
                    if check_available_passenger(p):
                        askDriverTime(p)
                        # state = 305
                    else:
                        reply(_("Nobody needs a ride in your location.") + '\n' +
                              _("You can try in a bit or go to the bus stop and see if there is someone there") +
                              _(' ') + emoij.SMILING_FACE)
                        restart(p);
                        # state = -1
                        #putDriverOnHold(p);
                        # state = 31
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else: reply("Eh? " + FERMATA_TRENTO + _("or") + FERMATA_POVO + "?")
            elif p.state == 305:
                # DRIVERS ASEKED FOR TIME
                if text in ['1','5','10']:
                    engageDriver(p, int(text));
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else:
                    reply(_("Eh? I don't understand you."))# (" + text + ")")
            elif p.state == 31:
                # DRIVERS WAITING FOR NEW PASSENGERS
                if text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    restart(p);
                    # state = -1
                else:
                    reply(_("Eh? I don't understand you."))# (" + text + ")")
            elif p.state == 32:
                # DRIVERS NOTIFIED THERE ARE PASSENGERS WAITING
                if text == _("List Passengers"):
                    reply(listPassengers(p))
                elif text.endswith(_("Abort")):
                    reply(_("Passage aborted."))
                    removeDriver(p)
                    # state = -1
                else:
                    reply(_("Eh? I don't understand you."))# (" + text + ")")
            elif p.state == 33:
                # DRIVER WHO HAS JUST BORDED AT LEAST A PASSANGER
                if text == _("List Passengers"):
                    reply(listPassengers(p))
                elif text == _("Reached Destination!"):
                    reply(_("Great, thanks!") + _(' ') + emoij.CLAPPING_HANDS)
                    removeRide(p) # update counter current ride of -1
                    removeDriver(p)
                    # set state -1
                # elif text.endswith(_("Abort")):
                #     reply(_("Passage aborted."))
                #     removeRide(p) # update counter current ride of -1
                #     removeDriver(p)
                #     # state = -1
                else:
                    reply(_("Eh? I don't understand you."))# (" + text + ")")
            elif p.state == 90:
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
                    reply(_("Eh? I don't understand you."))# (" + text + ")")
            else:
                reply("Something is wrong with your state (" + str(p.state) + "). Contact the admin!")


app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    ('/dashboard', DashboardHandler),
    ('/updates', GetUpdatesHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/webhook', WebhookHandler),
], debug=True)
