import person
from google.appengine.ext import ndb
from datetime import datetime

class Ride(ndb.Model):
    driver_name = ndb.StringProperty()
    driver_id = ndb.IntegerProperty()
    driver_ticket_id = ndb.StringProperty()
    start_daytime = ndb.DateTimeProperty()
    abort_daytime = ndb.DateTimeProperty()
    auto_abort = ndb.BooleanProperty()
    minutes_to_pickup = ndb.IntegerProperty()
    start_location = ndb.StringProperty()
    end_location = ndb.StringProperty()
    passengers_ids = ndb.JsonProperty()
    passengers_names = ndb.JsonProperty()
    passengers_names_str = ndb.StringProperty()
    end_daytime = ndb.DateTimeProperty()
    auto_end = ndb.BooleanProperty()

    def getDriverName(self):
        return self.driver_name.encode('utf-8')

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
    r.end_location = driver.getDestination()
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
    """
    if tell_completed:
        duration_sec = (ride.end_daytime - ride.start_daytime).seconds
        duration_min_str  = str(duration_sec/60) + ":" + str(duration_sec%60)
        tell(key.TIRAMISU_CHAT_ID, "Passenger completed! Driver: " + driver.name +
                     ". Passengers: " + ride.passengers_names_str + ". Duration (min): " + duration_min_str)
    """
