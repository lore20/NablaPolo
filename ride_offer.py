import person
from google.appengine.ext import ndb


class RideOffer(ndb.Model):
    driver_id = ndb.StringProperty()
    driver_name_lastname = ndb.StringProperty()
    driver_username = ndb.StringProperty()
    start_place = ndb.StringProperty()
    start_fermata = ndb.StringProperty()
    end_place = ndb.StringProperty()
    #end_fermata = ndb.StringProperty()
    intermediate_places = ndb.StringProperty(repeated=True)
    registration_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    active = ndb.BooleanProperty()

    start_datetime = ndb.DateTimeProperty()  # for programmati only time applies
    disactivation_datetime = ndb.DateTimeProperty()

    # only for regular rides
    programmato = ndb.BooleanProperty(default=False)
    programmato_giorni = ndb.IntegerProperty(repeated=True)
    #programmato_time = ndb.TimeProperty()

    def getDriverName(self):
        return self.driver_name_lastname.encode('utf-8')

    def getStartPlace(self):
        return self.start_place.encode('utf-8')

    def getStartFermata(self):
        return self.end_place.encode('utf-8')

    def getEndPlace(self):
        return self.start_place.encode('utf-8')

    def getDepartingTime(self):
        import date_time_util as dtu
        #return dtu.formatTime(self.programmato_time)
        return dtu.formatTime(self.start_datetime.time())

    def getDescription(self):
        import params
        import date_time_util as dtu
        msg = []
        msg.append('*Partenza*: {} ({})'.format(self.getStartPlace(), self.getStartFermata()))
        msg.append('*Arrivo*: {}'.format(self.end_place))
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
        msg.append('*Autista*: {} @{}'.format(self.getDriverName(), self.driver_username))
        return '\n'.join(msg)

    def disactivate(self,  put=True):
        import date_time_util as dtu
        self.active = False
        self.disactivation_datetime = dtu.removeTimezone(dtu.nowCET())
        if put:
            self.put()

def addRideOffer(driver, start_datetime, start_place, start_fermata, end_place,
                 programmato=False, programmato_giorni=()):
    import date_time_util as dtu
    import itinerary
    o = RideOffer(
        driver_id = str(driver.chat_id),
        driver_name_lastname = driver.getFirstNameLastName(),
        driver_username=driver.getUsername(),
        start_datetime=start_datetime,
        start_place=start_place,
        start_fermata=start_fermata,
        end_place=end_place,
        intermediate_places = itinerary.get_intermediate_stops(start_place, end_place),
        registration_datetime = dtu.removeTimezone(dtu.nowCET()),
        active = True,
        programmato = programmato,
        programmato_giorni = programmato_giorni,
        #programmato_time = start_datetime.time()
    )
    o.put()
    return o

def sortOffersPerDay(offers):
    import date_time_util as dtu
    result = [[],[],[],[],[],[],[]]
    today = dtu.getWeekday()
    now_dt = dtu.removeTimezone(dtu.nowCET())
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
    return result

def getActiveRideOffersDriver(chat_id):
    import date_time_util as dtu
    driver_id = str(chat_id)
    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            RideOffer.driver_id == driver_id,
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= dtu.nowUTC()

            )
        )
    ).order(RideOffer.start_datetime)
    return qry.fetch()


def getActiveRideOffersSortedPerDay(start_place, end_place):
    import date_time_util as dtu
    qry = RideOffer.query(
        ndb.AND(
            RideOffer.active == True,
            ndb.OR(
                ndb.AND(
                    RideOffer.start_place == start_place,
                    RideOffer.end_place == end_place
                ),
                ndb.AND(
                    RideOffer.start_place == start_place,
                    RideOffer.intermediate_places == end_place
                ),
                ndb.AND(
                    RideOffer.intermediate_places == start_place,
                    RideOffer.end_place == end_place
                )
            ),
            ndb.OR(
                RideOffer.programmato == True,
                RideOffer.start_datetime >= dtu.nowUTC()
            )
        )
    )
    offers = qry.fetch()
    return sortOffersPerDay(offers)