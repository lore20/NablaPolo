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
VAR_PASSAGGIO_PATH = 'passaggio_path'  # [start luogo, start fermata, dest luogo, dest fermata]
VAR_PASSAGGIO_TIME = 'passaggio_time' # [hour, min]
VAR_PASSAGGIO_DAYS = 'passaggio_days' # [1,2]
VAR_RIDE_SEARCH_SORTED_PER_DAY = 'ride_search_sorted' # see ride_offer.getRideOffers
VAR_RIDE_SEARCH_DAY = 'ride_search_day'
VAR_MY_RIDES = 'my_rides'
VAR_CURSOR = 'cursor'
VAR_STAGE = 'stage' # stage within state


class Person(geomodel.GeoModel, ndb.Model):
    chat_id = ndb.IntegerProperty()
    name = ndb.StringProperty()
    last_name = ndb.StringProperty()
    username = ndb.StringProperty()
    last_mod = ndb.DateTimeProperty(auto_now=True)
    state = ndb.IntegerProperty()
    language = ndb.StringProperty(default='IT')
    enabled = ndb.BooleanProperty(default=True)
    agree_on_terms = ndb.BooleanProperty(default=False)
    notification_mode = ndb.StringProperty(default=params.NOTIFICATION_MODE_ALL)

    itinerari_start_fermata = ndb.StringProperty(repeated=True)
    itinerari_start_place = ndb.StringProperty(repeated=True)
    itinerari_end_place = ndb.StringProperty(repeated=True)

    # location = ndb.GeoPtProperty() # inherited from geomodel.GeoModel
    latitude = ndb.ComputedProperty(lambda self: self.location.lat if self.location else None)
    longitude = ndb.ComputedProperty(lambda self: self.location.lon if self.location else None)

    tmp_variables = ndb.PickleProperty()

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

    def setTmpVariable(self, var_name, value, put=False):
        self.tmp_variables[var_name] = value
        if put:
            self.put()

    def getTmpVariable(self, var_name, initValue=None):
        if var_name in self.tmp_variables:
            return self.tmp_variables[var_name]
        self.tmp_variables[var_name] = initValue
        return initValue

    def getItineraryNumber(self):
        return len(self.itinerari_start_place)

    def getItineraryStrList(self, start_fermata=True):
        if start_fermata:
            return ["{} ({}) → {}".format(
                start_place.encode('utf-8'), start_fermata.encode('utf-8'), end_place.encode('utf-8'))
                    for start_place, start_fermata, end_place in
                    zip(self.itinerari_start_place, self.itinerari_start_fermata, self.itinerari_end_place)]
        else:
            return ["{} → {}".format(
                start_place.encode('utf-8'), end_place.encode('utf-8'))
                    for start_place, end_place in
                    zip(self.itinerari_start_place, self.itinerari_end_place)]

    def getItineraryFromCommand(self, command, fermata):
        logging.debug("In getItineraryFromCommand")
        logging.debug("input: {}".format(command))
        index = params.getIndexFromCommand(command, params.ITINERARI_COMMAND_PREFIX)
        logging.debug("index: {}".format(index))
        if index is None:
            return None
        index -= 1  # zero-based
        if len(self.itinerari_start_place)<=index:
            return None
        start, start_fermata, end = self.itinerari_start_place[index].encode('utf-8'), \
                                    self.itinerari_start_fermata[index].encode('utf-8'), \
                                    self.itinerari_end_place[index].encode('utf-8')
        if fermata:
            return start, start_fermata, end
        else:
            return start, end

    def appendItinerary(self, start_place, start_fermata, end_place):
        if self.itinerari_start_place is None:
            self.itinerari_start_place = []
            self.itinerari_start_fermata = []
            self.itinerari_end_place = []
        self.itinerari_start_place.append(start_place)
        self.itinerari_start_fermata.append(start_fermata)
        self.itinerari_end_place.append(end_place)

    def removeItinerario(self, index):
        start = self.itinerari_start_place.pop(index).encode('utf-8')
        fermata = self.itinerari_start_fermata.pop(index).encode('utf-8')
        end = self.itinerari_end_place.pop(index).encode('utf-8')
        return start, fermata, end

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

    def saveRideOffersStartEndPlace(self, start_place, end_place):
        import ride_offer
        import pickle
        offers = ride_offer.getActiveRideOffersSortedPerDay(start_place, end_place)
        pkl_offers = pickle.dumps(offers)
        self.setTmpVariable(VAR_RIDE_SEARCH_SORTED_PER_DAY, pkl_offers)
        return offers

    def loadRideOffersStartEndPlace(self):
        import pickle
        pkl_offers = self.getTmpVariable(VAR_RIDE_SEARCH_SORTED_PER_DAY)
        offers = pickle.loads(pkl_offers)
        return offers

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
    p.put()
    return p


def deletePerson(chat_id):
    p = getPersonById(chat_id)
    p.key.delete()


def getPersonById(chat_id):
    return Person.get_by_id(str(chat_id))

def getPeopleMatchingRideQry(start_place, intermediate_places, end_place):
    #logging.debug("In getPeopleMatchingRide")
    #logging.debug("start_place: {}".format(start_place))
    #logging.debug("intermediate_places: {}".format(intermediate_places))
    #logging.debug("end_place: {}".format(end_place))
    start_places = intermediate_places + [start_place]
    end_places = intermediate_places + [end_place]
    qry = Person.query(
        ndb.OR(
            Person.notification_mode == params.NOTIFICATION_MODE_ALL,
            ndb.AND(
                Person.notification_mode == params.NOTIFICATION_MODE_ITINERARIES,
                Person.itinerari_start_place.IN(start_places),
                Person.itinerari_end_place == end_place
            ),
            ndb.AND(
                Person.notification_mode == params.NOTIFICATION_MODE_ITINERARIES,
                Person.itinerari_start_place == start_place,
                Person.itinerari_end_place.IN(end_places),
            )
        )
    )
    return qry.order(Person._key)

def updatePeople():
    all_people = Person.query().fetch()
    for p in all_people:
        p.tmp_variables = {}
    create_futures = ndb.put_multi_async(all_people)
    ndb.Future.wait_all(create_futures)
