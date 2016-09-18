import person
from google.appengine.ext import ndb
from datetime import datetime

class RideRequest(ndb.Model):
    passenger_name = ndb.StringProperty()
    passenger_id = ndb.IntegerProperty()
    passenger_last_seen = ndb.DateTimeProperty()
    passenger_location = ndb.StringProperty()
    passenger_destination = ndb.StringProperty()
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
    request.passenger_destination = passenger.getDestination()
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