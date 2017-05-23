# coding=utf-8

import logging
from google.appengine.ext import ndb
from geo import geomodel, geotypes

import utility
import params

# ------------------------
# TMP_VARIABLES NAMES
# ------------------------
VAR_LAST_KEYBOARD = 'last_keyboard'
VAR_PASSAGGIO_PATH = 'passaggio_path'  # [start zona, start fermata, dest zona, dest fermata]
VAR_PASSAGGIO_TIME = 'passaggio_time' # [hour, min]
VAR_PASSAGGIO_DAYS = 'passaggio_days' # [1,2]
VAR_RIDE_SEARCH_SORTED_PER_DAY = 'ride_search_sorted' # see ride_offer.getRideOffers
VAR_RIDE_SEARCH_DAY = 'ride_search_day'
VAR_MY_RIDES = 'my_rides'
VAR_CURSOR = 'cursor'
VAR_STAGE = 'stage' # stage within state


class Person(geomodel.GeoModel, ndb.Model): #ndb.Expando
    chat_id = ndb.IntegerProperty()
    name = ndb.StringProperty()
    last_name = ndb.StringProperty()
    username = ndb.StringProperty()
    last_mod = ndb.DateTimeProperty(auto_now=True)
    state = ndb.IntegerProperty()
    enabled = ndb.BooleanProperty(default=True)
    notification_mode = ndb.StringProperty()

    percorsi = ndb.StringProperty(repeated=True)
    percorsi_size = ndb.ComputedProperty(
        lambda self: len(self.percorsi) if self.percorsi else 0
    )

    # location = ndb.GeoPtProperty() # inherited from geomodel.GeoModel
    latitude = ndb.ComputedProperty(lambda self: self.location.lat if self.location else None)
    longitude = ndb.ComputedProperty(lambda self: self.location.lon if self.location else None)

    tmp_variables = ndb.PickleProperty()

    def resetPercorsi(self):
        self.percorsi = []

    def updateUserInfo(self, name, last_name, username):
        modified = False
        if self.getFirstName() != name:
            self.name = name
            modified = True
        if self.getLastName() != last_name:
            self.last_name = last_name
            modified = True
        if self.username != username:
            self.username = username
            modified = True
        if not self.enabled:
            self.enabled = True
            modified = True
        if modified:
            self.put()

    def isAdmin(self):
        import key
        return self.chat_id in key.ADMIN_CHAT_ID

    def isTester(self):
        import key
        return self.chat_id in key.TESTERS

    def getPropertyUtfMarkdown(self, property, escapeMarkdown=True):
        if property == None:
            return None
        result = property.encode('utf-8')
        if escapeMarkdown:
            result = utility.escapeMarkdown(result)
        return result

    def getFirstName(self, escapeMarkdown=True):
        return self.getPropertyUtfMarkdown(self.name, escapeMarkdown=escapeMarkdown)

    def getLastName(self, escapeMarkdown=True):
        return self.getPropertyUtfMarkdown(self.last_name, escapeMarkdown=escapeMarkdown)

    def getUsername(self, escapeMarkdown=True):
        return self.getPropertyUtfMarkdown(self.username, escapeMarkdown=escapeMarkdown)

    def getFirstNameLastName(self, escapeMarkdown=True):
        if self.last_name == None:
            return self.getFirstName(escapeMarkdown=escapeMarkdown)
        return self.getFirstName(escapeMarkdown=escapeMarkdown) + \
               ' ' + self.getLastName(escapeMarkdown=escapeMarkdown)

    def getNotificationMode(self, escapeMarkdown=True):
        return self.getPropertyUtfMarkdown(self.notification_mode, escapeMarkdown=escapeMarkdown)

    def getFirstNameLastNameUserName(self, escapeMarkdown=True):
        result = self.getFirstName(escapeMarkdown =escapeMarkdown)
        if self.last_name:
            result += ' ' + self.getLastName(escapeMarkdown = escapeMarkdown)
        if self.username:
            result += ' @' + self.getUsername(escapeMarkdown = escapeMarkdown)
        return result

    def setNotificationMode(self, mode, put=True):
        self.notification_mode = mode
        if put:
            self.put()

    def setEnabled(self, enabled, put=False):
        self.enabled = enabled
        if put:
            self.put()

    def setState(self, newstate, put=True):
        self.state = newstate
        if put:
            self.put()

    def setNotificheMode(self, mode):
        self.notification_mode = mode

    def setLastKeyboard(self, kb, put=True):
        self.setTmpVariable(VAR_LAST_KEYBOARD, value=kb, put=put)

    def getLastKeyboard(self):
        return self.getTmpVariable(VAR_LAST_KEYBOARD)

    def resetTmpVariable(self):
        self.tmp_variables = {}

    def setTmpVariable(self, var_name, value, put=False):
        self.tmp_variables[var_name] = value
        if put:
            self.put()

    def getTmpVariable(self, var_name, initValue=None):
        if var_name in self.tmp_variables:
            return self.tmp_variables[var_name]
        self.tmp_variables[var_name] = initValue
        return initValue

    def setLocation(self, lat, lon, put=False):
        self.location = ndb.GeoPt(lat, lon)
        self.update_location()
        if put:
            self.put()

    def getPercorsiNumber(self):
        return len(self.percorsi_start_zona)

    def getPercorsi(self):
        return tuple([p.encode('utf-8') for p in self.percorsi])

    def getPercorsiSize(self):
        return self.percorsi_size

    def getPercorsoFromCommand(self, command, fermate):
        logging.debug("In getItineraryFromCommand")
        logging.debug("input: {}".format(command))
        index = params.getIndexFromCommand(command, params.PERCORSO_COMMAND_PREFIX)
        logging.debug("index: {}".format(index))
        if index is None:
            return None
        index -= 1  # zero-based
        percorsi_tuples = self.getPercorsi()
        if len(percorsi_tuples)<=index:
            return None
        return percorsi_tuples[index]

    def percorsoIsPresent(self, percorso):
        return percorso in self.getPercorsi()

    def appendPercorsi(self, percorso, put=False):
        if self.percorsoIsPresent(percorso):
            return False
        self.percorsi.append(percorso)
        if put:
            self.put()
        return True

    def removePercorsi(self, index):
        removed_percorso = self.percorsi.pop(index).encode('utf-8')
        return removed_percorso

    def removePercorsiMulti(self, indexList):
        self.percorsi_start_zona = [x for i,x in enumerate(self.percorsi_start_zona) if i not in indexList]
        self.percorsi_start_fermata = [x for i,x in enumerate(self.percorsi_start_fermata) if i not in indexList]
        self.percorsi_end_zona = [x for i, x in enumerate(self.percorsi_end_zona) if i not in indexList]
        self.percorsi_end_fermata = [x for i, x in enumerate(self.percorsi_end_fermata) if i not in indexList]

    def saveMyRideOffers(self):
        import ride_offer
        import pickle
        offers = ride_offer.getActiveRideOffersDriver(self.chat_id)
        pkl_offers = pickle.dumps(offers)
        self.setTmpVariable(VAR_MY_RIDES, pkl_offers)
        return offers

    def deleteMyOfferAtCursor(self):
        import pickle
        pkl_offers = self.getTmpVariable(VAR_MY_RIDES)
        offers = pickle.loads(pkl_offers)
        cursor = self.getTmpVariable(VAR_CURSOR)
        o = offers.pop(cursor[0])
        o.disactivate()
        pkl_offers = pickle.dumps(offers)
        self.setTmpVariable(VAR_MY_RIDES, pkl_offers)
        cursor[1] -= 1

    def loadMyRideOffers(self):
        import pickle
        pkl_offers = self.getTmpVariable(VAR_MY_RIDES)
        offers = pickle.loads(pkl_offers)
        return offers

    def getAndSaveRideOffersStartEndPlace(self, start_zona, end_zona):
        import ride_offer
        import pickle
        offers_per_day = ride_offer.getActiveRideOffersSortedPerDay(start_zona, end_zona)
        pkl_offers = pickle.dumps(offers_per_day)
        self.setTmpVariable(VAR_RIDE_SEARCH_SORTED_PER_DAY, pkl_offers)
        return offers_per_day

    def loadRideOffersStartEndPlace(self):
        import pickle
        pkl_offers = self.getTmpVariable(VAR_RIDE_SEARCH_SORTED_PER_DAY)
        offers_per_day = pickle.loads(pkl_offers)
        return offers_per_day

    def totalRideOffersNumber(self):
        offers_per_day = self.loadRideOffersStartEndPlace()
        return sum([len(l) for l in offers_per_day])

    def saveRideOffersStartEndPlaceChosenDay(self, dayIndex):
        import pickle
        offers = self.loadRideOffersStartEndPlace()
        #logging.debug("In saveRideOffersChosenDay. dayIndex={} offers={}".format(dayIndex, offers))
        offers_chosen_day = offers[dayIndex]
        pkl_offers_chosen_day = pickle.dumps(offers_chosen_day)
        self.setTmpVariable(VAR_RIDE_SEARCH_DAY, pkl_offers_chosen_day)
        return offers_chosen_day

    def loadRideOffersStartEndDayChosenDay(self):
        import pickle
        pkl_offers = self.getTmpVariable(VAR_RIDE_SEARCH_DAY)
        offers = pickle.loads(pkl_offers)
        return offers

    def decreaseCursor(self):
        cursor = self.getTmpVariable(VAR_CURSOR)
        cursor[0] -= 1
        if cursor[0] == -1:
            cursor[0] = cursor[1] - 1

    def increaseCursor(self):
        cursor = self.getTmpVariable(VAR_CURSOR)
        cursor[0] += 1
        if cursor[0] == cursor[1]:
            cursor[0] = 0

def addPerson(chat_id, name, last_name, username):
    p = Person(
        id=str(chat_id),
        chat_id=chat_id,
        name=name,
        last_name=last_name,
        username=username,
        notification_mode = params.DEFAULT_NOTIFICATIONS_MODE,
        tmp_variables={}
    )
    p.resetPercorsi()
    p.put()
    return p


def deletePerson(chat_id):
    p = getPersonById(chat_id)
    p.key.delete()


def getPersonById(chat_id):
    return Person.get_by_id(str(chat_id))

def getPeopleCount():
    return Person.query().count()

def getPeopleMatchingRideQry(start_zona, intermediate_zone, end_zona):
    #logging.debug("In getPeopleMatchingRide")
    #logging.debug("start_zona: {}".format(start_zona))
    #logging.debug("intermediate_zone: {}".format(intermediate_zone))
    #logging.debug("end_zona: {}".format(end_zona))
    start_zonas = intermediate_zone + [start_zona]
    end_zone = intermediate_zone + [end_zona]
    qry = Person.query(
        ndb.OR(
            Person.notification_mode == params.NOTIFICATION_MODE_ALL,
            ndb.AND(
                Person.notification_mode == params.NOTIFICATION_MODE_PERCORSI,
                Person.percorsi_start_zona.IN(start_zonas),
                Person.percorsi_end_zona == end_zona
            ),
            ndb.AND(
                Person.notification_mode == params.NOTIFICATION_MODE_PERCORSI,
                Person.percorsi_start_zona == start_zona,
                Person.percorsi_end_zona.IN(end_zone),
            )
        )
    )
    return qry

# to remove property change temporary teh model to ndb.Expando
# see https://cloud.google.com/appengine/articles/update_schema#removing-deleted-properties-from-the-datastore

def updatePeople():
    more, cursor = True, None
    while more:
        records, cursor, more = Person.query().fetch_page(1000, start_cursor=cursor)
        for ent in records:
            to_delete = [
                'percorsi_start_zona', 'percorsi_end_zona',
                'percorsi_start_fermata', 'percorsi_end_fermata'
            ]
            for prop in to_delete:
                if prop in ent._properties:
                    del ent._properties[prop]
            ent.tmp_variables = {}
            ent.resetPercorsi()
        if records:
            create_futures = ndb.put_multi_async(records)
            ndb.Future.wait_all(create_futures)


def rePopulatePeopleFromBackup():
    from person_backup import Person_Backup
    more, cursor = True, None
    while more:
        records, cursor, more = Person_Backup.query().fetch_page(1000, start_cursor=cursor)
        new_utenti = []
        for ent in records:
            p = Person(
                id=str(ent.chat_id),
                chat_id=ent.chat_id,
                name=ent.name,
                last_name=ent.last_name,
                username=ent.username,
                percorsi=[],
                notification_mode=params.DEFAULT_NOTIFICATIONS_MODE,
                tmp_variables={}
            )
            new_utenti.append(p)
        if new_utenti:
            create_futures = ndb.put_multi_async(new_utenti)
            ndb.Future.wait_all(create_futures)
