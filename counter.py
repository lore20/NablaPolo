
from google.appengine.ext import ndb

from person import Person
import bus_stops

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

class Counter(ndb.Model):
    name = ndb.StringProperty()
    counter = ndb.IntegerProperty()


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
    riders_current_counter = TN_PV_CURRENT_RIDES if driver.location == bus_stops.FERMATA_TRENTO else PV_TN_CURRENT_RIDES
    increaseCounter(riders_current_counter, 1)
    riders_tot_current_counter = TN_PV_TOTAL_RIDES if driver.location == bus_stops.FERMATA_TRENTO else PV_TN_TOTAL_RIDES
    increaseCounter(riders_tot_current_counter, 1)

def decreaseRides(driver):
    riders_current_counter = TN_PV_CURRENT_RIDES if driver.location == bus_stops.FERMATA_TRENTO else PV_TN_CURRENT_RIDES
    increaseCounter(riders_current_counter, -1)

def increasePassengerRide(passenger):
    passenger_tot_counter = TN_PV_TOTAL_PASSENGERS if passenger.location == bus_stops.FERMATA_TRENTO else PV_TN_TOTAL_PASSENGERS
    increaseCounter(passenger_tot_counter, 1)

def getDashboardData():
    p_wait_trento = Person.query().filter(Person.location == bus_stops.FERMATA_TRENTO, Person.state.IN([21, 22])).count()
    p_wait_povo = Person.query().filter(Person.location == bus_stops.FERMATA_POVO, Person.state.IN([21, 22])).count()

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