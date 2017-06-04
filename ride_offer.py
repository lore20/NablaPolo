# -*- coding: utf-8 -*-

from google.appengine.ext import ndb
from utility import convertToUtfIfNeeded

class RideOffer(ndb.Model): #ndb.Model
    driver_id = ndb.StringProperty()
    driver_name_lastname = ndb.StringProperty()
    driver_username = ndb.StringProperty()

    percorso = ndb.StringProperty()

    fermate_intermedie = ndb.StringProperty(repeated=True)
    percorsi_passeggeri_compatibili = ndb.StringProperty(repeated=True)

    registration_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    active = ndb.BooleanProperty() # remains active for non-programmati

    start_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    disactivation_datetime = ndb.DateTimeProperty()

    time_mode = ndb.StringProperty()  # BOTTONE_ADESSO, BOTTONE_A_BREVE, BOTTONE_PROGRAMMATO

    # only for regular rides
    programmato = ndb.BooleanProperty(default=False)
    programmato_giorni = ndb.IntegerProperty(repeated=True) # Monday is 0 and Sunday is 6
    # for time start_datetime is used

    def getDriverName(self):
        return convertToUtfIfNeeded(self.driver_name_lastname)

    def getPercorso(self):
        return convertToUtfIfNeeded(self.percorso)

    def getPercorsiPasseggeriCompatibili(self):
        return [convertToUtfIfNeeded(x) for x in self.percorsi_passeggeri_compatibili]

    def getNumberPercorsiPasseggeriCompatibili(self):
        return len(self.percorsi_passeggeri_compatibili)

    def getFermateIntermedie(self):
        return [convertToUtfIfNeeded(x) for x in self.fermate_intermedie]

    def getDepartingTime(self):
        import date_time_util as dtu
        #return dtu.formatTime(self.programmato_time)
        return dtu.formatTime(self.start_datetime.time())

    def getDescription(self, driver_info=True):
        import route
        import params
        import date_time_util as dtu
        import person
        msg = []
        percorso = self.getPercorso()
        start_zona, start_stop, end_zone, end_stop = route.decodePercorsoToQuartet(percorso)

        msg.append('*Partenza*: {} ({})'.format(start_zona, start_stop))
        msg.append('*Arrivo*: {} ({})'.format(end_zone, end_stop))

        msg.append('*Ora partenza*: {}'.format(self.getDepartingTime()))
        if self.programmato:
            giorni = [params.GIORNI_SETTIMANA_FULL[i] for i in self.programmato_giorni]
            giorni_str = ', '.join(giorni)
            msg.append('*Ogni*: {}'.format(giorni_str))
        else:
            date_str = dtu.formatDate(self.start_datetime)
            if date_str == dtu.formatDate(dtu.nowCET()):
                date_str += ' (OGGI)'
            elif date_str == dtu.formatDate(dtu.tomorrow()):
                date_str += ' (DOMANI)'
            msg.append('*Giorno partenza*: {}'.format(date_str))
        if driver_info:
            username = person.getPersonById(self.driver_id).getUsername()  # self.driver_username
            if username is None:
                from main import tell_admin
                tell_admin('❗ viaggio con driver_id {} non ha più username'.format(self.driver_id))
                username = '(username non più disponibile)'
            else:
                username = '@{}'.format(username)
            msg.append('*Autista*: {} {}'.format(self.getDriverName(), username))
        return '\n'.join(msg)

    def disactivate(self,  put=True):
        import date_time_util as dtu
        self.active = False
        self.disactivation_datetime = dtu.removeTimezone(dtu.nowCET())
        if put:
            self.put()

    def setFermateIntermediePercorsiPasseggeriCompatibili(self, put=True):
        import route
        import utility
        self.percorsi_passeggeri_compatibili, fermate_interemedie_routes = \
            route.getPercorsiPasseggeriCompatibili(self.getPercorso())
        self.fermate_interemedie = list(set(utility.flatten(fermate_interemedie_routes)))
        if put:
            self.put()
        return self.percorsi_passeggeri_compatibili, fermate_interemedie_routes


def addRideOffer(driver, start_datetime, percorso,
                 time_mode, programmato=False, programmato_giorni=()):
    import date_time_util as dtu
    o = RideOffer(
        driver_id = driver.getId(),
        driver_name_lastname = driver.getFirstNameLastName(),
        driver_username=driver.getUsername(),
        start_datetime=start_datetime,
        percorso=percorso,
        #percorsi_passeggeri_compatibili via computePercorsiPasseggeriCompatibili
        #fermate_intermedie via computePercorsiPasseggeriCompatibili
        registration_datetime = dtu.removeTimezone(dtu.nowCET()),
        active = True,
        time_mode = time_mode,
        programmato = programmato,
        programmato_giorni = programmato_giorni
    )
    #o.put() only after computePercorsiPasseggeriCompatibili()
    return o

def filterAndSortOffersPerDay(offers):
    import params
    import date_time_util as dtu
    from datetime import timedelta

    result = [[],[],[],[],[],[],[]]
    today = dtu.getWeekday()
    now_dt = dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)
    now_time = now_dt.time()
    for o in offers:
        if o.programmato:
            for g in o.programmato_giorni:
                # exclude those of today which have already happened
                if g != today or o.start_datetime.time() > now_time: #o.programmato_time > now_time:
                    result[g].append(o)
        elif o.start_datetime > now_dt:
            g = dtu.getWeekday(o.start_datetime)
            result[g].append(o)
    for results_days in result:
        results_days.sort(key=lambda x: x.getDepartingTime())
    return result

def getActiveRideOffersQry():
    import params
    import date_time_util as dtu
    from datetime import timedelta
    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= dtu.removeTimezone(dtu.nowCET()) - timedelta(
                    minutes=params.TIME_TOLERANCE_MIN)
            )
        )
    )
    return qry


def getActiveRideOffersCountInWeek():
    offers = getActiveRideOffersQry().fetch()
    offers_list_per_day = filterAndSortOffersPerDay(offers)
    count = sum([len(d) for d in offers_list_per_day])
    return count

def getRideOfferInsertedLastDaysQry(days):
    import date_time_util as dtu
    from datetime import timedelta
    return RideOffer.query(
        RideOffer.start_datetime >= dtu.removeTimezone(dtu.nowCET()) - timedelta(days=days)
    )


'''
def getActiveRideOffersProgrammatoQry():
    return RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            RideOffer.programmato == True,
        )
    )
'''


def getActiveRideOffersDriver(driver_id):
    import params
    import date_time_util as dtu
    from datetime import timedelta
    now_with_tolerance = dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)
    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            RideOffer.driver_id == driver_id,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= now_with_tolerance
            )
        )
    ).order(RideOffer.start_datetime)
    return qry.fetch()

def getActiveRideOffersSortedPerDay(percorso_passeggero):
    import params
    import date_time_util as dtu
    from datetime import timedelta

    nowWithTolerance = dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)

    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            RideOffer.percorsi_passeggeri_compatibili == percorso_passeggero,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= nowWithTolerance
            )
        )
    )
    offers = qry.fetch()
    return filterAndSortOffersPerDay(offers)

def getActiveRideOffers():
    import params
    import date_time_util as dtu
    from datetime import timedelta

    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= dtu.removeTimezone(dtu.nowCET()) - timedelta(minutes=params.TIME_TOLERANCE_MIN)
                # might be redundant as the filter is also applied afterwards
            )
        )
    )
    offers = qry.fetch()
    return offers

def updateRideOffers():
    from route import encodePercorsoFromQuartet
    from utility import convertToUtfIfNeeded
    more, cursor = True, None
    updated_records = []
    while more:
        records, cursor, more = RideOffer.query().fetch_page(1000, start_cursor=cursor)
        for ent in records:
            ent.percorso = encodePercorsoFromQuartet(
                convertToUtfIfNeeded(ent.start_place),
                convertToUtfIfNeeded(ent.start_fermata),
                convertToUtfIfNeeded(ent.end_place),
                convertToUtfIfNeeded(ent.end_fermata)
            )
            ent.driver_id = 'T_{}'.format(ent.driver_id)
            ent.setFermateIntermediePercorsiPasseggeriCompatibili(put=False)
            prop_to_delete = [
                'start_place', 'start_fermata',
                'end_place', 'end_fermata',
                'intermediate_places'
            ]
            for prop in prop_to_delete:
                if prop in ent._properties:
                    del ent._properties[prop]
        updated_records.extend(records)
    if updated_records:
        print 'Updating {} records'.format(len(updated_records))
        create_futures = ndb.put_multi_async(updated_records)
        ndb.Future.wait_all(create_futures)
