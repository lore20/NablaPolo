# -*- coding: utf-8 -*-

from google.appengine.ext import ndb
from utility import convertToUtfIfNeeded

class RideOffer(ndb.Model): #ndb.Model
    driver_id = ndb.StringProperty()
    driver_name_lastname = ndb.StringProperty()
    driver_username = ndb.StringProperty()

    percorso = ndb.StringProperty()

    routes_info = ndb.PickleProperty()
    # list of route info:
    # for each route ->
    # {route_intermediates_fermate: <list>,
    # route_duration: <num> (seconds),
    # route_distance: <num> (meters)}

    fermate_intermedie = ndb.StringProperty(repeated=True) # set of fermate intermedie
    percorsi_passeggeri_compatibili = ndb.StringProperty(repeated=True) # set of percorsi compatibili

    registration_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    active = ndb.BooleanProperty() # remains active for non-programmati

    start_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    disactivation_datetime = ndb.DateTimeProperty()

    time_mode = ndb.StringProperty()  # BOTTONE_ADESSO, BOTTONE_OGGI, BOTTONE_PROX_GIORNI, BOTTONE_PROGRAMMATO

    # only for regular rides
    programmato = ndb.BooleanProperty(default=False)
    programmato_giorni = ndb.IntegerProperty(repeated=True) # Monday is 0 and Sunday is 6
    # also used for prox. ggiorni mode
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

    def getTimeMode(self):
        return convertToUtfIfNeeded(self.time_mode)

    def disactivate(self,  put=True):
        import date_time_util as dtu
        self.active = False
        self.disactivation_datetime = dtu.removeTimezone(dtu.nowCET())
        if put:
            self.put()

    def getAverageDistance(self):
        from utility import format_distance
        assert self.routes_info
        distances = [r_info['route_distance'] for r_info in self.routes_info]
        avg_km = sum(distances) / float(len(distances)) / 1000
        return format_distance(avg_km)

    def getAverageDuration(self):
        import date_time_util as dtu
        assert self.routes_info
        durations = [r_info['route_duration'] for r_info in self.routes_info]
        avg = sum(durations) / float(len(durations))
        return dtu.convertSecondsInHourMinString(avg)

    def getFermateIntermedieRoutes(self):
        assert self.routes_info
        return [r_info['route_intermediates_fermate'] for r_info in self.routes_info]

    def getDescription(self, driver_info=True):
        import route
        import params
        import date_time_util as dtu
        import person
        msg = []
        percorso = self.getPercorso()
        start_fermata, end_fermata = route.decodePercorso(percorso)

        msg.append('*Partenza*: {}'.format(start_fermata))
        msg.append('*Arrivo*: {}'.format(end_fermata))

        if self.programmato:
            giorni = [params.GIORNI_SETTIMANA_FULL[i] for i in self.programmato_giorni]
            giorni_str = ', '.join(giorni)
            msg.append('*Ora partenza*: {}'.format(self.getDepartingTime()))
            msg.append('*Tipologia*: {}'.format(self.getTimeMode()))
            msg.append('*Ogni*: {}'.format(giorni_str))
        else:
            msg.append('*Quando*: {}'.format(self.getTimeMode()))
            msg.append('*Ora partenza*: {}'.format(self.getDepartingTime()))
            date_str = dtu.formatDate(self.start_datetime)
            if date_str == dtu.formatDate(dtu.nowCET()):
                date_str += ' (OGGI)'
            elif date_str == dtu.formatDate(dtu.tomorrow()):
                date_str += ' (DOMANI)'
            elif self.programmato_giorni: # PROX_GIORNI
                giorno_index = self.programmato_giorni[0]
                date_str += ' ({})'.format(params.GIORNI_SETTIMANA[giorno_index])
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
            msg.append('*Distanza*: {}'.format(self.getAverageDistance()))
            msg.append('*Durata*: {}'.format(self.getAverageDuration()))
        return '\n'.join(msg)

    def populateRideWithDetails(self, put=True):
        import route
        import itertools
        self.routes_info = route.getRoutingDetails(self.getPercorso())
        # a list of route info: for each route -> {route_intermediates_fermate, route_duration, route_distance}
        fermate_intermedie_set = set()
        percorsi_compatibili_set = set()
        if self.routes_info:
            for r_info in self.routes_info:
                fermate = r_info['route_intermediates_fermate']
                fermate_intermedie_set.update(fermate)
                fermate_pairs = tuple(itertools.combinations(fermate, 2))
                for pair in fermate_pairs:
                    percorso = route.encodePercorso(*pair)
                    percorsi_compatibili_set.add(percorso)

        self.fermate_intermedie = list(fermate_intermedie_set)
        self.percorsi_passeggeri_compatibili = list(percorsi_compatibili_set)
        if put:
            self.put()

    def getRideInfoDetails(self):
        from utility import format_distance
        import date_time_util as dtu
        msg = []
        msg.append('{} tragitto/i trovati per viaggio\n*{}*:\n'.
                   format(len(self.routes_info), self.getPercorso()))
        for n, r_info in enumerate(self.routes_info, 1):
            msg.append('*{}.*'.format(n))
            distance = format_distance(float(r_info['route_distance']) / 1000)
            duration = dtu.convertSecondsInHourMinString(r_info['route_duration'])
            fermate_intermedie_str = ', '.join(r_info['route_intermediates_fermate'])
            msg.append('   ∙ Fermate intermedie: {}'.format(fermate_intermedie_str))
            msg.append('   ∙ Distanza: {}'.format(distance))
            msg.append('   ∙ Durata: {}'.format(duration))
        num_percorsi_compatibili = len(self.getPercorsiPasseggeriCompatibili())
        msg.append('\n{} percorso/i passeggeri compatibilie.'.format(num_percorsi_compatibili))
        #percorsi_compatibili_str = ', '.join(self.getPercorsiPasseggeriCompatibili())
        #msg.append('\n{} percorso/i passeggeri compatibilie: {}'.format(
        #    num_percorsi_compatibili, percorsi_compatibili_str))
        return '\n'.join(msg)



def addRideOffer(driver, start_datetime, percorso,
                 time_mode, programmato=False, giorni=()):
    import date_time_util as dtu
    o = RideOffer(
        driver_id = driver.getId(),
        driver_name_lastname = driver.getFirstNameLastName(),
        driver_username=driver.getUsername(),
        start_datetime=start_datetime,
        percorso=percorso,
        #percorsi_passeggeri_compatibili via setFermateIntermediePercorsiPasseggeriCompatibili
        #fermate_intermedie via setFermateIntermediePercorsiPasseggeriCompatibili
        registration_datetime = dtu.removeTimezone(dtu.nowCET()),
        active = True,
        time_mode = time_mode,
        programmato = programmato,
        programmato_giorni = giorni
    )
    #o.put() only after setFermateIntermediePercorsiPasseggeriCompatibili()
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
    more, cursor = True, None
    updated_records = []
    while more:
        records, cursor, more = RideOffer.query().fetch_page(1000, start_cursor=cursor)
        for ent in records:
            '''
            prop_to_delete = ['fermate_interemedie']
            for prop in prop_to_delete:
                if prop in ent._properties:
                    del ent._properties[prop]
            '''
            if ent.key.id() == 5767281011326976:
                ent.populateRideWithDetails(put=False)
                updated_records.append(ent)
    if updated_records:
        print 'Updating {} records'.format(len(updated_records))
        create_futures = ndb.put_multi_async(updated_records)
        ndb.Future.wait_all(create_futures)
