# -*- coding: utf-8 -*-

from google.appengine.ext import ndb

from person import Person

def resetAll():
    for x in [Person]:
        more, cursor = True, None
        total = 0
        while more:
            records, cursor, more = Person.query().fetch_page(1000, keys_only=True, start_cursor=cursor)
            total += len(records)
            if records:
                create_futures = ndb.delete_multi_async(records)
                ndb.Future.wait_all(create_futures)

        print("Cleaned {} from {}".format(total, x.__name__))


# after updating online map (new places or change in names) we need to make sure that
# IMPORTANT: it assumes that in the update no previous fermate moved to a new zona
# - intermediate places of active ride_offers are regenerated
# - outdated percorsi preferiti (quartets) in person are removed
def updatePercorsi(dryRun=True):
    updatePeopleItinerary(dryRun)
    print('---------------')
    updateRideOfferItinerary(dryRun)


UPDATE_MSG = "🔔 Alcuni nomi nei percorsi sono stati modificati.\n" \
             "Ti consigliamo di ricontrollare i tuoi percosi andando su " \
             "⚙ IMPOSTAZIONI → 🛣 PERCORSI PREFERITI"

def updatePeopleItinerary(dryRun=True):
    from ride_offer import getRideQuartetToString
    from main import tell

    def isValidPercorso(startZona, startFermata, endZona, endFermata):
        from route import ZONE, FERMATE
        return startZona in ZONE and endZona in ZONE and \
               startFermata in FERMATE and endFermata in FERMATE

    more, cursor = True, None
    removed_percorsi = []
    changed_people = []
    while more:
        records, cursor, more = Person.query().fetch_page(1000, start_cursor=cursor)
        new_records = []
        for p in records:
            removeIndexes = []
            percosi = p.getPercorsi()
            for i,quartet in enumerate(percosi):
                if not isValidPercorso(*quartet):
                    removeIndexes.append(i)
                    if quartet not in removed_percorsi:
                        removed_percorsi.append(quartet)
            if removeIndexes:
                new_records.append(p)
                changed_people.append(p)
            if not dryRun and removeIndexes:
                p.removePercorsiMulti(removeIndexes)
                tell(p.chat_id, UPDATE_MSG)
        if not dryRun and new_records:
                create_futures = ndb.put_multi_async(new_records)
                ndb.Future.wait_all(create_futures)
    print('UpdatePeopleItinerary')
    print('Percorsi rimossi:\n{}'.format('\n'.join([getRideQuartetToString(*q) for q in removed_percorsi])))
    print('Da persone:\n{}'.format('\n'.join(p.getFirstNameLastNameUserName() for p in changed_people)))


def updateRideOfferItinerary(dryRun=True):
    import route
    import ride_offer

    percorsi_updated = []
    fermate_problems = []

    qry = ride_offer.getActiveRideOffersQry()
    records = qry.fetch()
    new_records = []
    for o in records:
        start_zona = o.getStartPlace()
        end_zona = o.getEndPlace()
        intermediates = route.get_intermediate_stops(start_zona, end_zona)
        #print o.getRideOfferPercorsoStr()
        if set(intermediates) != set(o.getIntermediatePlacesUtf()):
            o.intermediate_zone = intermediates
            new_records.append(o)
            percorsi_updated.append(o.key.id())
        if o.getStartFermata() not in route.FERMATE or o.getEndFermata() not in route.FERMATE:
            fermate_problems.append(o.key.id())
    if not dryRun and new_records:
        create_futures = ndb.put_multi_async(new_records)
        ndb.Future.wait_all(create_futures)

    print('UpdateRideOfferItinerary')
    print('Percorsi updated:\n{}'.format(', '.join(str(x) for x in percorsi_updated)))
    print('Fermate problems:\n{}'.format('\n'.join(str(x) for x in fermate_problems)))