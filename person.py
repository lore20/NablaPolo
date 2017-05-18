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


class Person(geomodel.GeoModel, ndb.Model): #ndb.Expando
    chat_id = ndb.IntegerProperty()
    name = ndb.StringProperty()
    last_name = ndb.StringProperty()
    username = ndb.StringProperty()
    last_mod = ndb.DateTimeProperty(auto_now=True)
    state = ndb.IntegerProperty()
    enabled = ndb.BooleanProperty(default=True)
    notification_mode = ndb.StringProperty()

    percorsi_start_fermata = ndb.StringProperty(repeated=True)
    percorsi_start_place = ndb.StringProperty(repeated=True)
    percorsi_end_place = ndb.StringProperty(repeated=True)

    # location = ndb.GeoPtProperty() # inherited from geomodel.GeoModel
    latitude = ndb.ComputedProperty(lambda self: self.location.lat if self.location else None)
    longitude = ndb.ComputedProperty(lambda self: self.location.lon if self.location else None)

    new_tmp_variable = ndb.PickleProperty()

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

    def setTmpVariable(self, var_name, value, put=False):
        self.new_tmp_variable[var_name] = value
        if put:
            self.put()

    def getTmpVariable(self, var_name, initValue=None):
        if var_name in self.new_tmp_variable:
            return self.new_tmp_variable[var_name]
        self.new_tmp_variable[var_name] = initValue
        return initValue

    def getPercorsiNumber(self):
        return len(self.percorsi_start_place)

    def getPercorsiTriples(self):
        return zip(self.percorsi_start_place, self.percorsi_start_fermata, self.percorsi_end_place)

    def getPercorsiPairs(self):
        return zip(self.percorsi_start_place, self.percorsi_end_place)

    def getPercorsiList(self, start_fermata=True):
        if start_fermata:
            return [(start_place.encode('utf-8'), start_fermata.encode('utf-8'), end_place.encode('utf-8'))
                for start_place, start_fermata, end_place in self.getPercorsiTriples()]
        else:
            list_with_duplicates = [(start_place.encode('utf-8'), end_place.encode('utf-8'))
                                    for start_place, end_place in self.getPercorsiPairs()]
            return utility.removeDuplicatesFromList(list_with_duplicates)


    def getPercorsiStrList(self, start_fermata=True):
        if start_fermata:
            return ["{} ({}) → {}".format(
                start_place.encode('utf-8'), start_fermata.encode('utf-8'), end_place.encode('utf-8'))
                    for start_place, start_fermata, end_place in self.getPercorsiTriples()]
        else:
            list_with_duplicates = ["{} → {}".format(
                start_place.encode('utf-8'), end_place.encode('utf-8'))
                    for start_place, end_place in self.getPercorsiPairs()]
            return utility.removeDuplicatesFromList(list_with_duplicates)

    def getPercorsiFromCommand(self, command, fermata):
        logging.debug("In getItineraryFromCommand")
        logging.debug("input: {}".format(command))
        index = params.getIndexFromCommand(command, params.PERCORSO_COMMAND_PREFIX)
        logging.debug("index: {}".format(index))
        if index is None:
            return None
        index -= 1  # zero-based
        percorsi_tuples = self.getPercorsiList(start_fermata=fermata)
        if len(percorsi_tuples)<=index:
            return None
        return percorsi_tuples[index]

    def appendPercorsi(self, start_place, start_fermata, end_place):
        if self.percorsi_start_place is None:
            self.percorsi_start_place = []
            self.percorsi_start_fermata = []
            self.percorsi_end_place = []
        if (start_place, start_fermata, end_place) in self.getPercorsiTriples():
            return False
        self.percorsi_start_place.append(start_place)
        self.percorsi_start_fermata.append(start_fermata)
        self.percorsi_end_place.append(end_place)
        return True

    def removePercorsi(self, index):
        start = self.percorsi_start_place.pop(index).encode('utf-8')
        fermata = self.percorsi_start_fermata.pop(index).encode('utf-8')
        end = self.percorsi_end_place.pop(index).encode('utf-8')
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

    def getAndSaveRideOffersStartEndPlace(self, start_place, end_place):
        import ride_offer
        import pickle
        offers_per_day = ride_offer.getActiveRideOffersSortedPerDay(start_place, end_place)
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
        new_tmp_variable={}
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
                Person.notification_mode == params.NOTIFICATION_MODE_PERCORSI,
                Person.percorsi_start_place.IN(start_places),
                Person.percorsi_end_place == end_place
            ),
            ndb.AND(
                Person.notification_mode == params.NOTIFICATION_MODE_PERCORSI,
                Person.percorsi_start_place == start_place,
                Person.percorsi_end_place.IN(end_places),
            )
        )
    )
    return qry

def updatePeopleItinerary():
    import percorsi
    more, cursor = True, None
    while more:
        records, cursor, more = Person.query().fetch_page(1000, start_cursor=cursor)
        new_records = []
        for p in records:
            removeIndexes = []
            for i in range(len(p.percorsi_start_place)):
                start, start_fermata, end = p.percorsi_start_place[i].encode('utf-8'), \
                                            p.percorsi_start_fermata[i].encode('utf-8'), \
                                            p.percorsi_end_place[i].encode('utf-8')
                if not percorsi.isValidStartEnd(start, start_fermata, end):
                    removeIndexes.append(i)
                    logging.debug('Removing percorso {} ({}) - {} from user {}'.format(start, start_fermata, end, p.getFirstNameLastName()))
            if removeIndexes:
                p.percorsi_start_place = [x for i, x in enumerate(p.percorsi_start_place) if i not in removeIndexes]
                p.percorsi_start_fermata = [x for i, x in enumerate(p.percorsi_start_fermata) if i not in removeIndexes]
                p.percorsi_end_place = [x for i, x in enumerate(p.percorsi_end_place) if i not in removeIndexes]
                new_records.append(p)
        if new_records:
            create_futures = ndb.put_multi_async(new_records)
            ndb.Future.wait_all(create_futures)
    logging.debug('Updated people percorso')


# to remove property change temporary teh model to ndb.Expando
# see https://cloud.google.com/appengine/articles/update_schema#removing-deleted-properties-from-the-datastore

'''
def updatePeople():
    all_props = {'active', 'agree_on_terms', 'basic_route', 'basic_route', 'bus_stop_end', 'bus_stop_end', 'bus_stop_mid_back', 'bus_stop_mid_going', 'bus_stop_start', 'bus_stop_start', 'chat_id', 'enabled', 'language', 'last_city', 'last_city', 'last_mod', 'last_name', 'last_name', 'last_seen', 'last_seen', 'last_type', 'last_type', 'latitude', 'location', 'longitude', 'name', 'notification_enabled', 'notification_mode', 'notified', 'prev_state', 'prev_state', 'state', 'state', 'ticket_id', 'ticket_id', 'tmp', 'username', 'username', 'new_tmp_variable'}
    valid_props = {'chat_id', 'name', 'last_name', 'username', 'last_mod', 'state', 'enabled', 'notification_mode', 'percorsi_start_fermata', 'percorsi_start_place', 'percorsi_end_place', 'latitude', 'longitude', 'new_tmp_variable'}
    to_delete_props = {'tmp', 'basic_route', 'language', 'bus_stop_end', 'notified', 'bus_stop_mid_back', 'last_type', 'notification_enabled', 'agree_on_terms', 'prev_state', 'location', 'last_city', 'active', 'last_seen', 'bus_stop_mid_going', 'bus_stop_start', 'ticket_id'}

    more, cursor = True, None
    while more:
        records, cursor, more = Person.query().fetch_page(1000, start_cursor=cursor)
        for ent in records:
            #ent.notification_mode = params.NOTIFICATION_MODE_ALL
            del ent.tmp
            #for old_prop in to_delete_props:
                #try:
                #    delattr(ent, old_prop)
                #except:
                #    continue

            #del ent._properties['tmp_variables']
            #ent.new_tmp_variable = {}
            #delattr(ent, 'new_tmp_variable')
        if records:
            create_futures = ndb.put_multi_async(records)
            ndb.Future.wait_all(create_futures)
'''

def populatePeople():
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
                notification_mode=params.DEFAULT_NOTIFICATIONS_MODE,
                new_tmp_variable={}
            )
            new_utenti.append(p)
        if new_utenti:
            create_futures = ndb.put_multi_async(new_utenti)
            ndb.Future.wait_all(create_futures)
