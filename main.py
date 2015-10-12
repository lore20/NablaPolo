import json
import logging
import urllib
import urllib2
import datetime
# import requests

import key
import emoij

# for sending images
#from PIL import Image
#import multipart


# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
import webapp2

# import MySQLdb
# see https://cloud.google.com/appengine/docs/python/cloud-sql/#Python_Connect_to_your_database

# TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

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
};

# ================================

class Person(ndb.Model):
    name = ndb.StringProperty()
    last_mod = ndb.DateTimeProperty(auto_now=True)
    last_seen = ndb.DateTimeProperty()
    chat_id = ndb.IntegerProperty()
    state = ndb.IntegerProperty()
    last_type = ndb.StringProperty()
    location = ndb.StringProperty()

# ================================


def addPerson(chat_id, name):
    p = Person.get_or_insert(str(chat_id))
    p.name = name
    p.chat_id = chat_id
    p.state = -1
    p.location = '-'
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

def start(p):
    tell(p.chat_id, "Hi " + p.name + "! Are you a driver or a passenger?",
    kb=[[emoij.CAR + ' Driver', emoij.FOOTPRINTS + ' Passenger'],[emoij.NOENTRY + ' Abort']])
    setState(p,0)

def getUsers():
    query = Person.query().order(-Person.last_mod)
    if query.get() is None:
        return "No users found"
    text = ""
    for p in query.iter():
        text = text + p.name + " (" + str(p.state) + ") " + get_date_string(p.last_mod) + "\n"
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
            tell(p.chat_id, "Your ride has been aborted by the system manager")
        restart(p)

def broadcast(msg):
    qry = Person.query()
    for p in qry:
        tell(p.chat_id, "Listen listen... " + msg, hideKb=False)


def restart(person):
    tell(person.chat_id, "Press START if you want to restart.", kb=[['START']])
    setStateLocation(person, -1, '-')


#def putDriverOnHold(driver):
#    tell(driver.chat_id, "No passanger needs a ride for the moment. Waiting...", kb=[[emoij.NOENTRY + ' Abort']])
#    setState(driver, 31)

def putPassengerOnHold(passenger):
    passenger.last_seen = datetime.datetime.now()
    tell(passenger.chat_id, "Waiting for a driver!", kb=[[emoij.NOENTRY + ' Abort']])
    setState(passenger, 21)

def check_available_drivers(passenger):
    # a passenger is at a certain location and we want to check if there is a driver bored or engaged
    #passenger.last_seen = datetime.datetime.now()
    qry = Person.query(Person.location == passenger.location, Person.state.IN([32,33])) #31
    #for d in qry:
    #    if (d.state==31):
    #        engageDriver(d)
    return qry.get() is not None

def engageDriver(d, min):
    d.last_seen = datetime.datetime.now() + datetime.timedelta(minutes=min)
    tell(d.chat_id, "You can go pick up the passenger(s)!",
          kb=[['List Passengers'],[emoij.NOENTRY + ' Abort']])
    qry = Person.query(Person.location == d.location, Person.state.IN([21, 22]))
    for p in qry:
        if (p.state==21):
            setState(p, 22)
        tell(p.chat_id, "A driver coming: " + d.name + " expected at " + get_time_string(d.last_seen),
            kb=[['List Drivers', 'Got the Ride!'],[emoij.NOENTRY + ' Abort']])
    setState(d, 32)

def askDriverTime(d):
    tell(d.chat_id, "There is someone waiting for you! In how many minutes will you be there?",
          kb=[['1','5','10'],[emoij.NOENTRY + ' Abort']])
    setState(d, 305)

def check_available_passenger(driver):
    # a driver is availbale for a location and we want to check if there are passengers bored or engaged
    #driver.last_seen = datetime.datetime.now()
    qry = Person.query(Person.location == driver.location, Person.state.IN([21, 22]))
    #for p in qry:
    #    if (p.state==21):
    #        setState(p, 22)
    #    tell(p.chat_id, "A driver coming: " + driver.name + " (" + get_time_string(driver.last_mod) + ")",
    #        kb=[['List Drivers', 'Got the Ride!'],[emoij.NOENTRY + ' Abort']])
    return qry.get() is not None

def listDrivers(passenger):
    qry = Person.query(Person.location == passenger.location, Person.state.IN([32,33])) #.order(-Person.last_mod)
    if qry.get() is None:
        return "No drivers found in your location"
    else:
        text = ""
        for d in qry:
            text = text + d.name + ' expected at: ' + get_time_string(d.last_seen) + "\n"
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
            text = text + d.name + " " + d.location + " (" + str(d.state) + ") " + get_time_string(d.last_seen) + "\n"
        return text


def listPassengers(driver):
    qry = Person.query(Person.location == driver.location, Person.state.IN([21, 22, 23])) #.order(-Person.last_mod)
    if qry.get() is None:
        return "No passengers needing a ride found in your location"
    else:
        text = ""
        for p in qry:
            text = text + p.name + ' waiting since ' + get_time_string(p.last_seen) + "\n"
            #" (" + str(p.state) + ") "
        return text

def listAllPassengers():
    qry = Person.query().filter(Person.state.IN([21, 22, 23]))
    if qry.get() is None:
        return "No passangers found"
    else:
        #qry = qry.order(-Person.last_mod)
        text = ""
        for p in qry:
            text = text + p.name + " " + p.location + " (" + str(p.state) + ") " + get_time_string(p.last_seen) + "\n"
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
                tell(d.chat_id, "Oops... all gone!")
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
            tell(p.chat_id, "Oops... all gone!")
            putPassengerOnHold(p)

def askToSelectDriverByName(p):
    qry = Person.query().filter(Person.state.IN([32,33]), Person.location==p.location)
    if qry.get() is None:
        tell(p.chat_id, "Thanks you, have a good ride! (cannot ask you which driver cause they are all gone)")
        removePassenger()
    else:
        buttons = []
        for d in qry:
            buttons.append([d.name])
        buttons.append(['Other'])
        tell(p.chat_id, "Great, which driver gave you a ride?", kb=buttons)
        setState(p, 23)

def getDriverByLocAndName(loc, name_text):
    qry = Person.query().filter(Person.location==loc, Person.state.IN([32,33]), Person.name==name_text)
    return qry.get()

def tell(chat_id, msg, kb=None, hideKb=True):
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

# ================================

class MeHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(BASE_URL + 'getMe'))))


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
        text = message.get('text')
        # fr = message.get('from')
        chat = message['chat']
        chat_id = chat['id']
        first_name = chat["first_name"]
        #user_id = chat["id"]
        name = str(first_name)

        if not text:
            logging.info('no text')
            return

        def reply(msg=None, kb=None, hideKb=True):
            tell(chat_id, msg, kb, hideKb)

        instructions = ('I\'m your Trento <-> Povo travelling assistant.\n' \
                        'You can write /start to get or offer a ride\n' \
                        'You can write /help to see this message again'.encode('utf-8'))


        p = ndb.Key(Person, str(chat_id)).get()
        if p is None:
            # new user
            tell(key.MASTER_CHAT_ID, msg = "New user: " + name)
            p = addPerson(chat_id, name)
            if text == '/help':
                reply(instructions)
            elif text in ['/start','START']:
                start(p)
                # state = 0
            else:
                reply("Hi " + name + ", welcome!")
                reply(instructions)
        else:
            # known user
            if text=='/state':
              reply("You are in state " + str(p.state) + ": " + STATES[p.state]);
            elif p.state == -1:
                # INITIAL STATE
                if text == '/help':
                    reply(instructions)
                elif text in ['/start','START']:
                    start(p)
                    # state = 0
                elif text == '/users':
                    reply(getUsers())
                elif text == '/alldrivers':
                    reply(listAllDrivers())
                elif text == '/allpassengers':
                    reply(listAllPassengers())
                elif chat_id==key.MASTER_CHAT_ID:
                    if text == '/resetall':
                        restartAllUsers()
                    elif text.startswith('/broadcast ') and len(text)>11:
                        msg = text[11:]
                        broadcast(msg)
                    else:
                        reply('What command? I only understnad /help /start '
                              '/users /alldrivers /alldrivers /resetall /broadcast.')
                else:
                    reply('What command? I only understnad /help or /start.')
            elif p.state == 0:
                # AFTER TYPING START
                if text.endswith('Passenger'):
                    setState(p, 20)
                    setType(p, text)
                    reply("Hi! I can try to help you to get a ride. Where are you?", 
                          kb=[['Trento Porta Aquila', 'Povo Sommarive'],[emoij.NOENTRY + ' Abort']])
                elif text.endswith('Driver'):
                    setState(p, 30)
                    setType(p, text)
                    reply("Hi! Glad you can give a ride. Where are you?", 
                          kb=[['Trento Porta Aquila', 'Povo Sommarive'],[emoij.NOENTRY + ' Abort']])
                elif text.endswith('Abort'):
                    reply("Passage aborted.")
                    restart(p);
                    # state = -1
                else: reply("Eh? I don't understand you. Are you a Driver or a Passenger?")
            elif p.state == 20:
                # PASSANGERS, ASKED FOR LOCATION
                if text in ['Povo Sommarive','Trento Porta Aquila']:
                    setLocation(p, text)
                    if check_available_drivers(p):
                        reply("There is a driver coming!", 
                              kb=[['List Drivers', 'Got the Ride!'],[emoij.NOENTRY + ' Abort']])
                        setState(p, 22)
                    else:
                        putPassengerOnHold(p)
                        # state = 21
                elif text.endswith('Abort'):
                    reply("Passage aborted.")
                    restart(p);
                    # state = -1
                else: reply("Eh? I don't understand you. Trento or Povo?")
            elif p.state == 21:
                # PASSENGERS IN A LOCATION WITH NO DRIVERS
                if text.endswith('Abort'):
                    reply("Passage aborted.")
                    removePassenger(p)
                    #restart(p);
                    # state = -1
                else:
                    reply("Eh? If you want to Abort press the button!", kb=[[emoij.NOENTRY + ' Abort']])
            elif p.state == 22:
                # PASSENGERS NOTIFIED THERE IS A DRIVER
                if text == 'Got the Ride!':
                    askToSelectDriverByName(p)
                elif text == 'List Drivers':
                    reply(listDrivers(p))
                elif text.endswith('Abort'):
                    reply("Passage aborted.")
                    removePassenger(p)
                    # state = -1
                else:
                    reply("Eh? I don't understand you. A driver is supposed to come, be patient!")
            elif p.state == 23:
                # PASSENGERS WHO JUST CONFIRMED A RIDE
                if text == 'Other':
                    reply("Thanks, have a good ride!")
                    removePassenger(p)
                elif text.endswith('Abort'):
                    reply("Passage aborted.")
                    removePassenger(p)
                    # state = -1
                else:
                    d = getDriverByLocAndName(p.location, text)
                    if d is not None:
                        reply("Great! Many thanks to " + d.name + "! ")
                        tell(d.chat_id, p.name + " confirmed you gave him/her a ride!",
                             kb=[['List Passengers', 'Reached Destination!'],[emoij.NOENTRY + ' Abort']])
                        if (d.state==32):
                            setState(d, 33)
                        removePassenger(p, driver=d)
                        # passenger state = -1
                    else:
                        reply("Name of driver not correct, try again.")
            elif p.state == 30:
                # DRIVERS, ASKED FOR LOCATION
                if text in ['Povo Sommarive','Trento Porta Aquila']:
                    setLocation(p, text)
                    # CHECK AND NOTIFY PASSENGER WAIING IN THE SAME LOCATION
                    if check_available_passenger(p):
                        askDriverTime(p)
                        # state = 305
                    else:
                        reply("Nobody needs a ride in your location. Thanks anyway! You can also try in a bit :)")
                        restart(p);
                        # state = -1
                        #putDriverOnHold(p);
                        # state = 31
                elif text.endswith('Abort'):
                    reply("Passage aborted.")
                    restart(p);
                    # state = -1
                else: reply("Eh? Trento or Povo?")
            elif p.state == 305:
                # DRIVERS ASEKED FOR TIME
                if text in ['1','5','10']:
                    engageDriver(p, int(text));
                elif text.endswith('Abort'):
                    reply("Passage aborted.")
                    restart(p);
                    # state = -1
                else:
                    reply("Eh? I don't understand you.")
            elif p.state == 31:
                # DRIVERS WAITING FOR NEW PASSENGERS
                if text.endswith('Abort'):
                    reply("Passage aborted.")
                    restart(p);
                    # state = -1
                else:
                    reply("Eh? I don't understand you.")
            elif p.state == 32:
                # DRIVERS NOTIFIED THERE ARE PASSENGERS WAITING
                if text == 'List Passengers':
                    reply(listPassengers(p))
                elif text.endswith('Abort'):
                    reply("Passage aborted..")
                    removeDriver(p)
                    # state = -1
                else:
                    reply("Eh? I don't understand you. (" + text + ")")
            elif p.state == 33:
                # DRIVER WHO HAS JUST BORDED AT LEAST A PASSANGER
                if text == 'List Passengers':
                    reply(listPassengers(p))
                elif text == 'Reached Destination!':
                    reply("Great, thanks! " + emoij.CLAPPING_HANDS)
                    removeDriver(p)
                    # set state -1
                elif text.endswith('Abort'):
                    reply("Passage aborted..")
                    removeDriver(p)
                    # state = -1
                else:
                    reply("Eh? I don't understand you. (" + text + ")")
            else:
                reply("Something is wrong with your state (" + str(p.state) + "). Contact the admin!")


app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    ('/updates', GetUpdatesHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/webhook', WebhookHandler),
], debug=True)
