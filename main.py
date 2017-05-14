# -*- coding: utf-8 -*-

from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.ext import deferred
from google.appengine.ext.db import datastore_errors

import json
import jsonUtil
import logging
import urllib
import urllib2
from time import sleep
import requests
import emoji
import utility
import geoUtils
import key
import person
from person import Person
import percorsi
import date_time_util as dtu
import requests.packages.urllib3
import ride_offer
import params

import webapp2
# from flask import Flask, jsonify

import gettext

from jinja2 import Environment, FileSystemLoader

# ================================
# ================================
# ================================

BASE_URL = 'https://api.telegram.org/bot' + key.TOKEN + '/'

STATES = {
    0: 'Initial state',
    1: 'Offri Passaggio',
    11:   'Passaggio a Breve (24 ore)',
    12:   'Passaggio Programmato (ripetuto)',
    2: 'Cerca Passaggio - da/a',
    21:   'Cerca Passaggio - Quando',
    22:   'Cerca Passaggio - Risultati',
    3: 'Impostazioni',
    31:   'Itinerari',
    311:     'Aggiungi Itinerario',
    312:     'Rimuovi Itinerario',
    32:   'Notifiche',
    33:   'Modifica Offerte',
    9: 'Info',
    91:   'Info Fermate',
}

RESTART_STATE = 0

LANGUAGES = {'IT': 'it_IT',
             'EN': 'en',
             # 'FR': 'fr_FR',
             # 'DE': 'de',
             # 'NL': 'nl',
             # 'PL': 'pl',
             # 'RU': 'ru'
             }

LANGUAGE_FLAGS = {
    "IT": emoji.FLAG_IT,
    "EN": emoji.FLAG_EN,
    # "RU", emoji.FLAG_RU,
    # "DE", emoji.FLAG_DE,
    # "FR", emoji.FLAG_FR,
    # "PL", emoji.FLAG_PL
}

# ================================
# BUTTONS
# ================================

START_BUTTON = "🚩 START"
HELP_BUTTON = "🆘 HELP"

CHECK_ICON = '✅'
PREV_ICON = '⏪'
NEXT_ICON = '⏩'
BULLET_SYMBOL = '∙'
RIGHT_ARROW_SYMBOL = '→'

BOTTONE_INDIETRO = "🔙 INDIETRO"
BOTTONE_INFO = "ℹ INFO"
BOTTONE_FERMATE = "🚏 FERMATE"
BOTTONE_MAPPA = "🗺 MAPPA COMPLETA"
BOTTENE_OFFRI_PASSAGGIO = "🚘 OFFRI"
BOTTENE_CERCA_PASSAGGIO = "👍 CERCA"
BOTTONE_IMPOSTAZIONI = "⚙ IMPOSTAZIONI"
BOTTONE_AGGIUNGI_PERCORSO = "➕ AGGIUNGI PERCORSO"
BOTTONE_RIMUOVI_PERCORSO = "➖ RIMUOVI PERCORSO"
BOTTONE_PERCORSI = "🛣 PERCORSI"
BOTTONE_NOTIFICHE = "🔔 NOTIFICHE"
BOTTONE_ANNULLA = "❌ ANNULLA"
BOTTONE_ADESSO = "👇 ADESSO"
BOTTONE_A_BREVE = "⏰ A BREVE"
BOTTONE_PERIODICO = "📆 PERIODICO"
BOTTONE_CONFERMA = "👌 CONFERMA"
BOTTONE_ELIMINA_OFFERTE = "✖ 🚘ELIMINA MIE OFFERTE"
BOTTONE_ATTIVA_NOTIFICHE_TUTTE = "🔔🔔🔔 ATTIVA TUTTE"
BOTTONE_DISTATTIVA_NOTIFICHE = "🔕 DISATTIVA TUTTE"
BOTTONE_ATTIVA_NOTIFICHE_PERCORSI = "🔔🛣 ATTIVA NOTIFICHE MIEI PERCORSI"
BOTTONE_ELIMINA = "🗑 ELIMINA"

BOTTONE_LOCATION = {
    'text': "INVIA POSIZIONE",
    'request_location': True,
}

# ================================
# MESSAGES
# ================================

'''
INSTRUCTIONS = (
    _("PickMeUp is a non-profit carpooling service (just like BlaBlaCar but for small journeys within a city).") + "\n\n" +
    _("You need to agree on terms and conditions in SETTINGS  and insert an PERCORSY to start a new journey.") + "\n" +
    _("Once all is set, you can press START to request or offer a ride.") + "\n\n" +
    _("Please visit our website at http://pickmeup.trentino.it " +
      "read the pdf instructions at http://tiny.cc/pickmeup_info " +
      "and if you want to promote this initiative do like us on FaceBook https://www.fb.com/321pickmeup ") + "\n\n" +
    _("If you want to join our discussions come to the tiramisu group at the following link: " +
      "https://telegram.me/joinchat/B8zsMQBtAYuYtJMj7qPE7g") + "\n\n" +
    _("Any feedback or contribution is highly appreciated (go to INFO -> SEND FEEDBACK)! :D"))  # .encode('utf-8')

TERMS_AND_CONDITIONS = (_("PickMeUp is a dynamic carpooling system, like BlaBlaCar but within the city.") + "\n" +
                        _("It is currently  under testing.") + "\n\n" +
                        _("WARNINGS:") + "\n" +
                        _("Drivers: please offer rides before starting the ride. " +
                          "DO NOT use your phone while you drive.") + "\n" +
                        _("Passengers: please ask for rides when you are at the bus stop. ") +
                        _("Be kind with the driver and the other passengers.") + "\n\n" +
                        _(
                            "PickMeUp is a non-profit service and it is totally money-free between passengers and drivers.") + "\n" +
                        _("The current version is under testing: ") +
                        _(
                            "no review system has been implemented yet and ride traceability is still limited. ") + "\n\n" +
                        _("PickMeUp developers decline any responsibility for the use of the service.") + "\n" +
                        _(
                            "If you want to use this service you have to agree on these terms by pressing the button below."))

MESSAGE_FOR_FRIENDS = _("Hi, I've discovered @PickMeUp_bot a free capooling service via Telegram! ") + \
                      _("It's like BlaBlaCar, but for commuting within a city. ") + \
                      _("The system is currently under testing but the community is getting larger every day. ") + \
                      _("You can try it by clicking on @PickMeUp_bot and press START! ")

PAPER_CLIP_INSTRUCTIONS = _("Please attach a location by 1) pressing the ") + emoji.PAPER_CLIP + \
                          _(" icon below and 2) chosing a position in the map.")
'''


# ================================
# GENERAL FUNCTIONS
# ================================

# ---------
# BROADCAST
# ---------

BROADCAST_COUNT_REPORT = utility.unindent(
    """
    Messaggio inviato a {} persone
    Ricevuto da: {}
    Non rivevuto da : {} (hanno disattivato il bot)
    """
)

def broadcast(sender, msg, qry = None,
              restart_user=False, curs=None, enabledCount=0, total=0,
              blackList_ids=(), sendNotification=True):
    # return
    if qry is None:
        qry = Person.query()
    users, next_curs, more = qry.fetch_page(50, start_cursor=curs)
    try:
        for p in users:
            if p.chat_id in blackList_ids:
                continue
            total += 1
            if tell(p.chat_id, msg, sleepDelay=True): #p.enabled
                enabledCount += 1
                if restart_user:
                    restart(p)

    except datastore_errors.Timeout:
        sleep(1)
        deferredSafeHandleException(broadcast, sender, msg, qry, restart_user, curs, enabledCount, total, blackList_ids, sendNotification)
        return
    if more:
        deferredSafeHandleException(broadcast, sender, msg, qry, restart_user, next_curs, enabledCount, total, blackList_ids, sendNotification)
    elif sendNotification:
        disabled = total - enabledCount
        msg_debug = BROADCAST_COUNT_REPORT.format(total, enabledCount, disabled)
        tell(sender.chat_id, msg_debug)


# ---------
# INFO COUNT
# ---------

def getInfoCount():
    count = Person.query().count()
    msg = "Attualmente siamo in {} persone iscritte a BancaTempoBot! " \
          "Vogliamo crescere assieme! Invita altre persone ad aunirsi!".format(count)
    return msg


# ================================
# Telegram Send Request
# ================================
def sendRequest(url, data, recipient_chat_id, debugInfo):
    try:
        resp = requests.post(url, data)
        logging.info('Response: {}'.format(resp.text))
        respJson = json.loads(resp.text)
        success = respJson['ok']
        if success:
            return True
        else:
            status_code = resp.status_code
            error_code = respJson['error_code']
            description = respJson['description']
            p = person.getPersonById(recipient_chat_id)
            if error_code == 403:
                # Disabled user
                p.setEnabled(False, put=True)
                logging.info('Disabled user: ' + p.getUserInfoString())
            elif error_code == 400 and description == "INPUT_USER_DEACTIVATED":
                p = person.getPersonById(recipient_chat_id)
                p.setEnabled(False, put=True)
                debugMessage = '❗ Input user disactivated: ' + p.getUserInfoString()
                logging.debug(debugMessage)
                tell(key.FEDE_CHAT_ID, debugMessage, markdown=False)
            else:
                debugMessage = '❗ Raising unknown err ({}).' \
                               '\nStatus code: {}\nerror code: {}\ndescription: {}.'.format(
                    debugInfo, status_code, error_code, description)
                logging.error(debugMessage)
                # logging.debug('recipeint_chat_id: {}'.format(recipient_chat_id))
                logging.debug('Telling to {} who is in state {}'.format(p.chat_id, p.state))
                tell(key.FEDE_CHAT_ID, debugMessage, markdown=False)
    except:
        report_exception()


# ================================
# TELL FUNCTIONS
# ================================

def tellMaster(msg, markdown=False, one_time_keyboard=False):
    for id in key.MASTER_CHAT_ID:
        tell(id, msg, markdown=markdown, one_time_keyboard=one_time_keyboard, sleepDelay=True)


def tellInputNonValidoUsareBottoni(chat_id, kb=None):
    msg = '⛔️ È possibile inserire testo solo quando il programma lo richiede.\n\n' \
          'Proseguire utilizzando i bottoni qui sotto 🎛.'
    tell(chat_id, msg, kb)

def tellInputNonValido(chat_id, kb=None):
    msg = '⛔️ Input non riconosciuto.'
    tell(chat_id, msg, kb)

def tellInputNonValidoRepeatState(p):
    msg = "Input non valido, leggi bene le istruzioni."
    sendWaitingAction(p.chat_id, sleep_time=1.0)
    tell(p.chat_id, msg)
    repeatState(p)


def tell(chat_id, msg, kb=None, markdown=True, inline_keyboard=False, one_time_keyboard=False,
         sleepDelay=False, hide_keyboard=False, force_reply=False):
    # reply_markup: InlineKeyboardMarkup or ReplyKeyboardMarkup or ReplyKeyboardHide or ForceReply
    if inline_keyboard:
        replyMarkup = {  # InlineKeyboardMarkup
            'inline_keyboard': kb
        }
    elif kb:
        replyMarkup = {  # ReplyKeyboardMarkup
            'keyboard': kb,
            'resize_keyboard': True,
            'one_time_keyboard': one_time_keyboard,
        }
    elif hide_keyboard:
        replyMarkup = {  # ReplyKeyboardHide
            'hide_keyboard': hide_keyboard
        }
    elif force_reply:
        replyMarkup = {  # ForceReply
            'force_reply': force_reply
        }
    else:
        replyMarkup = {}

    data = {
        'chat_id': chat_id,
        'text': msg,
        'disable_web_page_preview': 'true',
        'parse_mode': 'Markdown' if markdown else '',
        'reply_markup': json.dumps(replyMarkup),
    }
    debugInfo = "tell function with msg={} and kb={}".format(msg, kb)
    success = sendRequest(key.TELEGRAM_API_URL + 'sendMessage', data, chat_id, debugInfo)
    if success:
        if sleepDelay:
            sleep(0.1)
        return True


def tell_person(chat_id, msg, markdown=False):
    tell(chat_id, msg, markdown=markdown)
    p = person.getPersonById(chat_id)
    if p and p.enabled:
        return True
    return False


def sendText(p, text, markdown=False, restartUser=False):
    split = text.split()
    if len(split) < 3:
        tell(p.chat_id, 'Commands should have at least 2 spaces')
        return
    if not split[1].isdigit():
        tell(p.chat_id, 'Second argument should be a valid chat_id')
        return
    id = int(split[1])
    text = ' '.join(split[2:])
    if tell_person(id, text, markdown=markdown):
        user = person.getPersonById(id)
        if restartUser:
            restart(user)
        tell(p.chat_id, 'Successfully sent text to ' + user.getFirstName())
    else:
        tell(p.chat_id, 'Problems in sending text')


# ================================
# SEND LOCATION
# ================================

def sendLocation(chat_id, latitude, longitude, kb=None):
    try:
        resp = urllib2.urlopen(key.TELEGRAM_API_URL + 'sendLocation', urllib.urlencode({
            'chat_id': chat_id,
            'latitude': latitude,
            'longitude': longitude,
        })).read()
        logging.info('send location: {}'.format(resp))
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = Person.query(Person.chat_id == chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.getUserInfoString())
        else:
            logging.info('Unknown exception: ' + str(err))


# ================================
# SEND VOICE
# ================================

def sendVoice(chat_id, file_id):
    try:
        data = {
            'chat_id': chat_id,
            'voice': file_id,
        }
        resp = requests.post(key.TELEGRAM_API_URL + 'sendVoice', data)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()


# ================================
# SEND PHOTO
# ================================

def sendPhotoViaUrlOrId(chat_id, url_id, kb=None):
    try:
        if kb:
            replyMarkup = {  # ReplyKeyboardMarkup
                'keyboard': kb,
                'resize_keyboard': True,
            }
        else:
            replyMarkup = {}
        data = {
            'chat_id': chat_id,
            'photo': url_id,
            'reply_markup': json.dumps(replyMarkup),
        }
        resp = requests.post(key.TELEGRAM_API_URL + 'sendPhoto', data)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()


# ================================
# SEND DOCUMENT
# ================================

def sendDocument(chat_id, file_id):
    try:
        data = {
            'chat_id': chat_id,
            'document': file_id,
        }
        resp = requests.post(key.TELEGRAM_API_URL + 'sendDocument', data)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()


# ================================
# SEND WAITING ACTION
# ================================

def sendWaitingAction(chat_id, action_tipo='typing', sleep_time=None):
    try:
        resp = urllib2.urlopen(key.TELEGRAM_API_URL + 'sendChatAction', urllib.urlencode({
            'chat_id': chat_id,
            'action': action_tipo,
        })).read()
        logging.info('send venue: {}'.format(resp))
        if sleep_time:
            sleep(sleep_time)
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = Person.query(Person.chat_id == chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.getUserInfoString())
        else:
            logging.info('Unknown exception: ' + str(err))


# ================================
# RESTART
# ================================
def restart(p, msg=None):
    if msg:
        tell(p.chat_id, msg)
    redirectToState(p, RESTART_STATE)


# ================================
# SWITCH TO STATE
# ================================
def redirectToState(p, new_state, **kwargs):
    if p.state != new_state:
        logging.debug("In redirectToState. current_state:{0}, new_state: {1}".format(str(p.state), str(new_state)))
        # p.firstCallCategoryPath()
        p.setState(new_state)
    repeatState(p, **kwargs)


# ================================
# REPEAT STATE
# ================================
def repeatState(p, put=False, **kwargs):
    methodName = "goToState" + str(p.state)
    method = possibles.get(methodName)
    if not method:
        tell(p.chat_id, "Si è verificato un problema (" + methodName +
             "). Segnalamelo mandando una messaggio a @kercos" + '\n' +
             "Ora verrai reindirizzato/a nella schermata iniziale.")
        restart(p)
    else:
        if put:
            p.put()
        method(p, **kwargs)

# ================================
# UNIVERSAL COMMANDS
# ================================

def dealWithUniversalCommands(p, input):
    if p.chat_id in key.MASTER_CHAT_ID:
        if input == '/aggiorna':
            import admin
            admin.updateItinerary()
            tell(p.chat_id, "Aggiornamento completato!")
            return True
    return False

## +++++ BEGIN OF STATES +++++ ###

# ================================
# GO TO STATE 0: Initial State
# ================================

def goToState0(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    kb = [
        [BOTTENE_OFFRI_PASSAGGIO, BOTTENE_CERCA_PASSAGGIO],
        [BOTTONE_IMPOSTAZIONI],
        [BOTTONE_INFO]
    ]
    if giveInstruction:
        msg = '*Schermata iniziale*'
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTENE_OFFRI_PASSAGGIO:
            if p.username is None or p.username == '-':
                msg = '⚠️ Non hai uno *username pubblico* impostato su Telegram. ' \
                      'Questo è necessario per far sì che i passeggeri ti possano contattare.\n\n' \
                      'Ti preghiamo di *scegliere uno username nelle impostazioni di Telegram* e riprovare.'
                tell(p.chat_id, msg, kb)
            else:
                redirectToState(p, 1, firstCall=True)
        elif input == BOTTENE_CERCA_PASSAGGIO:
            redirectToState(p, 2, firstCall=True)
        elif input == BOTTONE_IMPOSTAZIONI:
            redirectToState(p, 3)
        elif input == BOTTONE_INFO:
            redirectToState(p, 9)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 1: Offri Passaggio - Partenza - Destinazione
# ================================

def goToState1(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
    PASSAGGIO_PATH = [] if firstCall else p.getTmpVariable(person.VAR_PASSAGGIO_PATH)
    if firstCall:
        p.setTmpVariable(person.VAR_PASSAGGIO_PATH, PASSAGGIO_PATH)
    giveInstruction = input is None
    stage = len(PASSAGGIO_PATH)
    #logging.debug("State 1. PASSAGGIO_PATH: {}, STAGE: {}".format(PASSAGGIO_PATH, stage))
    if giveInstruction:
        if stage == 0:
            percorsiCmds = getItinerariCommands(p, start_fermata=True)
            if percorsiCmds:
                msg = 'Seleziona uno dei tuoi percorsi:\n\n{}\n\n'.format(percorsiCmds)
                msg += 'oppure dimmi da dove parti.'
            else:
                msg = '*Da dove parti?*'
            kb = utility.makeListOfList(percorsi.SORTED_LUOGHI)
        elif stage ==1:
            fermate = percorsi.SORTED_FERMATE_IN_LOCATION(PASSAGGIO_PATH[0])
            kb = utility.makeListOfList(fermate)
            if len(fermate)==1:
                p.setLastKeyboard(kb)
                repeatState(p, input=fermate[0])
                return
            msg = '*Da quale fermata?*'
        elif stage == 2:
            msg = '*Dove vai?*'
            destinazioni = list(percorsi.SORTED_LUOGHI)
            destinazioni.remove(PASSAGGIO_PATH[0])
            kb = utility.makeListOfList(destinazioni)
        else: #stage == 3
            #time_in_half_hour = dtu.formatTime(dtu.get_datetime_add_minutes(30, dt=dtu.nowCET()), '%H%M')
            msg = "*Quando parti?*\n\n" \
                  "Premi *{}* se parti ora, *{}* se parti nelle prossime 24 ore o *{}* " \
                  "se vuoi programmare un viaggio regolare " \
                  "(ad esempio ogni lunedì alle 8:00)".format(BOTTONE_ADESSO, BOTTONE_A_BREVE, BOTTONE_PERIODICO)
            kb = [[BOTTONE_ADESSO], [BOTTONE_A_BREVE, BOTTONE_PERIODICO]]
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if stage == 0 and input.startswith(params.PERCORSO_COMMAND_PREFIX):
            percorsi_start_fermata_end = p.getPercorsiFromCommand(input, fermata=True)
            if percorsi_start_fermata_end:
                PASSAGGIO_PATH.extend(percorsi_start_fermata_end)
                repeatState(p)
            else:
                tellInputNonValido(p.chat_id, kb)
        else:
            if input in utility.flatten(kb):
                if input == BOTTONE_ANNULLA:
                    restart(p)
                elif stage<=2:
                    PASSAGGIO_PATH.append(input)
                    repeatState(p)
                else:
                    if input==BOTTONE_ADESSO: # or dtu.getTime(input, format='%H%M'):
                        start_place = PASSAGGIO_PATH[0]
                        start_fermata = PASSAGGIO_PATH[1]
                        end_place = PASSAGGIO_PATH[2]
                        dt = dtu.nowCET() #if input==BOTTONE_ADESSO else dtu.getTime(input, format='%H%M')
                        finalizeOffer(p, start_place, start_fermata, end_place, dt)
                        sendWaitingAction(p.chat_id) #, sleep_time=1
                        restart(p)
                    elif input == BOTTONE_A_BREVE:
                        redirectToState(p, 11, firstCall=True)
                    else: # BOTTONE_PROGRAMMATO
                        redirectToState(p, 12, firstCall=True)
            else:
                tellInputNonValidoUsareBottoni(p.chat_id, kb)

def finalizeOffer(p, start_place, start_fermata, end_place, date_time, programmato=False, programmato_giorni=()):
    logging.debug("In finalizeOffer. DAYS: {}".format(programmato_giorni))
    #date_time = dtu.convertCETtoUTC(date_time)
    date_time = dtu.removeTimezone(date_time)
    time_str = dtu.formatTime(date_time, format='%H:%M')
    date_str = dtu.formatDate(date_time, format='%d.%m.%Y')
    o = ride_offer.addRideOffer(p, date_time, start_place, start_fermata, end_place,
                                programmato, programmato_giorni)
    qry = person.getPeopleMatchingRideQry(o.start_place, o.intermediate_places, o.end_place)
    msg = "Grazie per aver inserito l'offerta di passaggio\n" \
          "*{} ({}) ➡ {}* alle {}".format(start_place, start_fermata, end_place, time_str)
    if programmato:
        giorni = [params.GIORNI_SETTIMANA_FULL[x] for x in programmato_giorni]
        giorni_str = ', '.join(giorni)
        msg += ' ogni {}'.format(giorni_str)
    else:
        msg += ' del {}'.format(date_str)
    #msg += "\n\nOfferta inviata a {} persone".format(qry.count())
    tell(p.chat_id, msg)
    msg_broadcast = '🚘 *Nuova offerta di passagio*:\n\n{}'.format(o.getDescription())
    broadcast(p, msg_broadcast, qry, restart_user=False, curs=None, enabledCount=0, total=0,
              blackList_ids=[p.chat_id], sendNotification=False)

def getItinerariCommands(p, start_fermata):
    percorsi = p.getPercorsiStrList(start_fermata)
    commands = ['∙ {}: {}'.format(
        params.getCommand(params.PERCORSO_COMMAND_PREFIX, n), i)
                for n, i in enumerate(percorsi, 1)]
    return '\n'.join(commands)


# ================================
# GO TO STATE 11: Offri passaggio a breve (24 ore)
# ================================

def goToState11(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
    TIME_HH_MM = [] if firstCall else p.getTmpVariable(person.VAR_PASSAGGIO_TIME)
    if firstCall:
        p.setTmpVariable(person.VAR_PASSAGGIO_TIME, TIME_HH_MM)
    giveInstruction = input is None
    stage = len(TIME_HH_MM)
    if giveInstruction:
        current_hour = dtu.nowCET().hour
        if stage == 0:
            msg = '*A che ora parti?*'
            current_min = dtu.nowCET().minute
            if current_min > 52:
                current_hour += 1
            circular_range = range(current_hour, 24) + range(0, current_hour)
            hours = [str(x).zfill(2) for x in circular_range]
            kb = utility.distributeElementMaxSize(hours, 8)
        else:
            msg = '*A che minuto parti?*'
            startNowMinutes = current_hour == TIME_HH_MM[0]
            if startNowMinutes:
                current_min_approx = utility.roundup(dtu.nowCET().minute + 2, 5)
                circular_range = range(current_min_approx, 60, 5)
                minutes = [str(x).zfill(2) for x in circular_range]
            else:
                minutes = [str(x).zfill(2) for x in range(0, 60, 5)]
            kb = utility.distributeElementMaxSize(minutes, 6)
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_ANNULLA:
            restart(p)
            return
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            TIME_HH_MM.append(int(input))
            if stage == 0:
                repeatState(p)
            else:
                PASSAGGIO_PATH = p.getTmpVariable(person.VAR_PASSAGGIO_PATH)
                start_place = PASSAGGIO_PATH[0]
                start_fermata = PASSAGGIO_PATH[1]
                end_place = PASSAGGIO_PATH[2]
                dt = dtu.nowCET()
                dt = dt.replace(hour=TIME_HH_MM[0], minute=TIME_HH_MM[1])
                if dt.time() < dtu.nowCET().time():
                    dt = dtu.get_date_tomorrow(dt)
                finalizeOffer(p, start_place, start_fermata, end_place, dt)
                sendWaitingAction(p.chat_id, sleep_time=1)
                restart(p)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 12: Offri passaggio periodico
# ================================

def goToState12(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
    logging.debug("firstCall: {}".format(firstCall))
    TIME_HH_MM = [] if firstCall else p.getTmpVariable(person.VAR_PASSAGGIO_TIME)
    DAYS = [] if firstCall else p.getTmpVariable(person.VAR_PASSAGGIO_DAYS)
    STAGE = 0 if firstCall else p.getTmpVariable(person.VAR_STAGE)
    logging.debug("DAYS: {}".format(DAYS))
    if firstCall:
        p.setTmpVariable(person.VAR_PASSAGGIO_TIME, TIME_HH_MM)
        p.setTmpVariable(person.VAR_PASSAGGIO_DAYS, DAYS)
        p.setTmpVariable(person.VAR_STAGE, STAGE)
    giveInstruction = input is None
    logging.debug("Stage: {}".format(STAGE))
    if giveInstruction:
        if STAGE == 0:
            msg = '*In che giorni effettui il viaggio?*'
            logging.debug("msg: {}".format(msg))
            g = lambda x: '{}{}'.format(CHECK_ICON, x) if params.GIORNI_SETTIMANA.index(x) in DAYS else x
            GIORNI_CHECK = [g(x) for x in params.GIORNI_SETTIMANA]
            logging.debug("GIORNI_CHECK: {}".format(GIORNI_CHECK))
            kb = [GIORNI_CHECK]
            if len(DAYS) > 0:
                kb.append([BOTTONE_CONFERMA])
        elif STAGE == 1:
            msg = '*A che ora parti?*'
            start_hour = 6
            circular_range = range(start_hour, 24) + range(0, start_hour)
            hours = [str(x).zfill(2) for x in circular_range]
            kb = utility.distributeElementMaxSize(hours, 8)
        else: # STAGE == 2
            msg = '*A che minuto parti?*'
            minutes = [str(x).zfill(2) for x in range(0, 60, 5)]
            kb = utility.distributeElementMaxSize(minutes, 6)
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_ANNULLA:
            restart(p)
            return
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if STAGE == 0: # DAYS
                if input == BOTTONE_CONFERMA:
                    p.setTmpVariable(person.VAR_STAGE, STAGE + 1)
                    repeatState(p)
                else:
                    remove = CHECK_ICON in input
                    selected_giorno = input[-2:] if remove else input
                    selected_giorno_index = params.GIORNI_SETTIMANA.index(selected_giorno)
                    if remove:
                        DAYS.remove(selected_giorno_index)
                    else:
                        DAYS.append(selected_giorno_index)
                    repeatState(p)
            elif STAGE == 1: # hour
                p.setTmpVariable(person.VAR_STAGE, STAGE + 1)
                TIME_HH_MM.append(int(input))
                repeatState(p)
            else: # minute
                TIME_HH_MM.append(int(input))
                PASSAGGIO_PATH = p.getTmpVariable(person.VAR_PASSAGGIO_PATH)
                start_place = PASSAGGIO_PATH[0]
                start_fermata = PASSAGGIO_PATH[1]
                end_place = PASSAGGIO_PATH[2]
                dt = dtu.nowCET()
                dt = dt.replace(hour=TIME_HH_MM[0], minute=TIME_HH_MM[1])
                if dt.time() < dtu.nowCET().time():
                    dt = dtu.get_date_tomorrow(dt)
                finalizeOffer(p, start_place, start_fermata, end_place, dt, programmato=True, programmato_giorni=DAYS)
                sendWaitingAction(p.chat_id, sleep_time=1)
                restart(p)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 2: Cerca Passaggio - Partenza - Destinazione
# ================================

def goToState2(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
    PASSAGGIO_PATH = [] if firstCall else p.getTmpVariable(person.VAR_PASSAGGIO_PATH)
    logging.debug("PASSAGGIO_PATH: {}".format(PASSAGGIO_PATH))
    if firstCall:
        p.setTmpVariable(person.VAR_PASSAGGIO_PATH, PASSAGGIO_PATH)
    giveInstruction = input is None
    stage = len(PASSAGGIO_PATH)
    if giveInstruction:
        if stage == 0:
            percorsiCmds = getItinerariCommands(p, start_fermata=True)
            if percorsiCmds:
                msg = 'Seleziona uno dei *tuoi percorsi*:\n\n{}\n\n'.format(percorsiCmds)
                msg += 'oppure dimmi da *dove parti*.'
            else:
                msg = '*Da dove parti?*'
            kb = utility.makeListOfList(percorsi.SORTED_LUOGHI)
        else: # stage == 1:
            msg = '*Dove vai?*'
            destinazioni = list(percorsi.SORTED_LUOGHI)
            destinazioni.remove(PASSAGGIO_PATH[0])
            kb = utility.makeListOfList(destinazioni)
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if stage == 0 and input.startswith(params.PERCORSO_COMMAND_PREFIX):
            percorsi_start_end = p.getPercorsiFromCommand(input, fermata=False)
            if percorsi_start_end:
                PASSAGGIO_PATH.extend(percorsi_start_end)
                showItinerari(p, PASSAGGIO_PATH)
            else:
                tellInputNonValido(p.chat_id, kb)
        elif input in utility.flatten(kb):
                if input == BOTTONE_ANNULLA:
                    restart(p)
                    return
                PASSAGGIO_PATH.append(input)
                if stage == 0:
                    repeatState(p)
                else:
                    showItinerari(p, PASSAGGIO_PATH)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

def showItinerari(p, PASSAGGIO_PATH):
    start_place = PASSAGGIO_PATH[0]
    end_place = PASSAGGIO_PATH[1]
    sendWaitingAction(p.chat_id)
    offers = p.saveRideOffersStartEndPlace(start_place, end_place)
    percorsi_num = sum([len(l) for l in offers])
    msg = "Itinerari trovati: {}".format(percorsi_num)
    tell(p.chat_id, msg)
    if percorsi_num > 0:
        redirectToState(p, 21)
    else:
        sendWaitingAction(p.chat_id, sleep_time=1)
        restart(p)

# ================================
# GO TO STATE 21: Cerca Passaggio - Quando
# ================================

def goToState21(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        msg = '*Quando vuoi partire?*'
        offers_per_day = p.loadRideOffersStartEndPlace()
        today = dtu.getWeekday()
        giorni_sett_oggi_domani = params.GIORNI_SETTIMANA[today:] + params.GIORNI_SETTIMANA[:today]
        giorni_sett_oggi_domani[:2] = ['OGGI', 'DOMANI']
        logging.debug('giorni_sett_oggi_domani: {}'.format(giorni_sett_oggi_domani))
        offer_days_count = [len(x) for x in offers_per_day]
        offer_days_count_oggi_domani = offer_days_count[today:] + offer_days_count[:today]
        offer_giorni_sett_count_oggi_domani = ['{} ({})'.format(d, c) for d,c in zip(giorni_sett_oggi_domani, offer_days_count_oggi_domani)]
        kb = [[BOTTONE_ANNULLA], offer_giorni_sett_count_oggi_domani[:2], offer_giorni_sett_count_oggi_domani[2:]]
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_ANNULLA:
            restart(p)
            return
        kb = p.getLastKeyboard()
        flat_kb = utility.flatten(kb)
        if input in flat_kb:
            count = int(input[input.index('(')+1:input.index(')')])
            giorno = input[:input.index(' ')]
            giorno_full = giorno if len(giorno)>2 else params.GIORNI_SETTIMANA_FULL[params.GIORNI_SETTIMANA.index(giorno)]
            if count==0:
                msg = "Nessun passaggio per {}".format(giorno_full)
                tell(p.chat_id, msg, kb)
            else:
                today = dtu.getWeekday()
                giorno_index = (flat_kb.index(input) - 1 + today) % 7  # -1 because of BOTTONE_ANNULLA
                p.saveRideOffersStartEndPlaceChosenDay(giorno_index)
                #msg = "Debug - chosen day: {}".format(params.GIORNI_SETTIMANA[giorno_index])
                #tell(p.chat_id, msg)
                sendWaitingAction(p.chat_id, sleep_time=1)
                redirectToState(p, 22, firstCall=True)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 22: Cerca Passaggio - Risultati
# ================================

def goToState22(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
        offers_chosen_day = p.loadRideOffersStartEndDayChosenDay()
        cursor = [0, len(offers_chosen_day)] if firstCall else p.getTmpVariable(person.VAR_CURSOR)
        if firstCall:
            p.setTmpVariable(person.VAR_CURSOR, cursor)
        logging.debug('offers_chosen_day: {}'.format(offers_chosen_day))
        offer = offers_chosen_day[cursor[0]]
        msg = "Passaggio {}/{}\n\n{}".format(cursor[0]+1, cursor[1], offer.getDescription())
        kb = [[BOTTONE_INDIETRO]]
        if len(offers_chosen_day)>1:
            kb.insert(0, [PREV_ICON, NEXT_ICON])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input==BOTTONE_INDIETRO:
                redirectToState(p, 21)
            elif input==PREV_ICON:
                p.decreaseCursor()
                repeatState(p, put=True)
            else: #input==NEXT_ICON:
                p.increaseCursor()
                repeatState(p, put=True)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)


# ================================
# GO TO STATE 3: Impostazioni
# ================================

def goToState3(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        my_offers = p.saveMyRideOffers()
        if my_offers:
            kb = [[BOTTONE_ELIMINA_OFFERTE], [BOTTONE_PERCORSI, BOTTONE_NOTIFICHE], [BOTTONE_INDIETRO]]
        else:
            kb = [[BOTTONE_PERCORSI, BOTTONE_NOTIFICHE], [BOTTONE_INDIETRO]]
        msg = '*Schermata Impostazioni*'
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INDIETRO:
                restart(p)
            elif input == BOTTONE_PERCORSI:
                redirectToState(p, 31)
            elif input == BOTTONE_NOTIFICHE:
                redirectToState(p, 32)
            else: # input == BOTTONE_ELIMINA_OFFERTE:
                redirectToState(p, 33, firstCall=True)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 31: Itinerari
# ================================

def goToState31(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        percorsi = p.getPercorsiStrList()
        reached_max_percorsi = len(percorsi) > params.MAX_PERCORSI
        AGGIUNGI_RIMUOVI_BUTTONS = []
        if not reached_max_percorsi:
            AGGIUNGI_RIMUOVI_BUTTONS.append(BOTTONE_AGGIUNGI_PERCORSO)
        if percorsi:
            AGGIUNGI_RIMUOVI_BUTTONS.append(BOTTONE_RIMUOVI_PERCORSO)
        kb = [AGGIUNGI_RIMUOVI_BUTTONS, [BOTTONE_INDIETRO]]
        msg = '*Schermata Itinerari*\n\n'
        if percorsi:
            msg += '\n'.join(['∙ {}'.format(i) for i in percorsi])
            if reached_max_percorsi:
                msg += '\n\nHai raggiunto il numero massimo di percorsi.'
        else:
            msg += 'Nessun percorso inserito.'
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INDIETRO:
                redirectToState(p, 3)
            elif input == BOTTONE_AGGIUNGI_PERCORSO:
                redirectToState(p, 311, firstCall=True)
            else: # input == BOTTONE_RIMUOVI_PERCORSO
                redirectToState(p, 312)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 311: Aggiungi Itinerario
# ================================

def goToState311(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
    PASSAGGIO_PATH = [] if firstCall else p.getTmpVariable(person.VAR_PASSAGGIO_PATH)
    if firstCall:
        p.setTmpVariable(person.VAR_PASSAGGIO_PATH, PASSAGGIO_PATH)
    giveInstruction = input is None
    stage = len(PASSAGGIO_PATH)
    if giveInstruction:
        if stage == 0:
            # '*Offri Passaggio 1/4*\n\n' \
            msg = '*Da dove parti?*'
            kb = utility.makeListOfList(percorsi.SORTED_LUOGHI)
        elif stage ==1:
            # '*Offri Passaggio 2/4*\n\n' \
            fermate = percorsi.SORTED_FERMATE_IN_LOCATION(PASSAGGIO_PATH[0])
            kb = utility.makeListOfList(fermate)
            if len(fermate)==1:
                p.setLastKeyboard(kb)
                repeatState(p, input=fermate[0])
                return
            msg = '*Da quale fermata?*'
        else: # stage == 2:
            # '*Offri Passaggio 3/4*\n\n' \
            msg = '*Dove vai?*'
            destinazioni = list(percorsi.SORTED_LUOGHI)
            destinazioni.remove(PASSAGGIO_PATH[0])
            kb = utility.makeListOfList(destinazioni)
        kb.insert(0, [BOTTONE_INDIETRO])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_INDIETRO:
            redirectToState(p, 31)
            return
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            PASSAGGIO_PATH.append(input)
            if stage <= 1:
                repeatState(p)
            else: # stage==3
                p.appendPercorsi(PASSAGGIO_PATH[0], PASSAGGIO_PATH[1], PASSAGGIO_PATH[2])
                msg = '*Aggiunto percorso*:\n{} ({}) → {}'.format(
                    PASSAGGIO_PATH[0], PASSAGGIO_PATH[1], PASSAGGIO_PATH[2])
                tell(p.chat_id, msg)
                sendWaitingAction(p.chat_id, sleep_time=1)
                redirectToState(p, 31)

        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 312: Rimuovi Itinerari
# ================================

def goToState312(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    percorsi = p.getPercorsiStrList()
    if giveInstruction:
        msg = "*Premi il numero corrispondende al percorso che vuoi rimuovere.*\n\n"
        msg += '\n'.join(['{}. {}'.format(n,i) for n,i in enumerate(percorsi,1)])
        numberButtons = [str(n) for n in range(1,len(percorsi)+1)]
        kb = utility.distributeElementMaxSize(numberButtons)
        kb.insert(0, [BOTTONE_INDIETRO])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INDIETRO:
                redirectToState(p, 31)
            else:  # input == BOTTONE_RIMUOVI_PERCORSO
                n = int(input)
                PASSAGGIO_PATH = p.removePercorsi(n - 1)
                msg = '*Rimosso percorso*:\n{} ({}) → {}'.format(
                    PASSAGGIO_PATH[0], PASSAGGIO_PATH[1], PASSAGGIO_PATH[2])
                tell(p.chat_id, msg)
                if p.getPercorsiNumber()>0:
                    repeatState(p)
                else:
                    redirectToState(p, 31)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)


# ================================
# GO TO STATE 32: Notifiche
# ================================

def goToState32(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    NOTIFICHE_BUTTONS = [BOTTONE_ATTIVA_NOTIFICHE_TUTTE, BOTTONE_ATTIVA_NOTIFICHE_PERCORSI,
                         BOTTONE_DISTATTIVA_NOTIFICHE]
    if giveInstruction:
        NOTIFICHE_MODES = list(params.NOTIFICATIONS_MODES)
        NOTIFICA_ATTIVA = p.getNotificationMode()
        logging.debug("NOTIFICA_ATTIVA: {}".format(NOTIFICA_ATTIVA))
        active_index = NOTIFICHE_MODES.index(NOTIFICA_ATTIVA)
        NOTIFICHE_MODES.pop(active_index)
        NOTIFICHE_BUTTONS.pop(active_index)
        if NOTIFICA_ATTIVA == params.NOTIFICATION_MODE_NONE:
            msg = '🔕 Non hai nessuna notifica attiva.'
        elif NOTIFICA_ATTIVA == params.NOTIFICATION_MODE_PERCORSIES:
            msg = '🔔🛣 Hai attivato le notifiche dei passaggio corrispondenti ai tuoi itineri.'
        else: #BOTTONE_NOTIFICHE_TUTTE
            msg = '🔔🔔🔔 Hai attivato le notifiche per tutti i passaggi.'
        kb = utility.makeListOfList(NOTIFICHE_BUTTONS)
        kb.append([BOTTONE_INDIETRO])
        tell(p.chat_id, msg, kb)
        p.setLastKeyboard(kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INDIETRO:
                redirectToState(p, 3)
            else: #
                activated_index = NOTIFICHE_BUTTONS.index(input)
                activated_mode = params.NOTIFICATIONS_MODES[activated_index]
                p.setNotificationMode(activated_mode)
                repeatState(p)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 33: Elimina Offerte
# ================================

def goToState33(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        my_offers = p.loadMyRideOffers()
        if my_offers:
            firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
            if firstCall:
                cursor = [0, len(my_offers)]
                p.setTmpVariable(person.VAR_CURSOR, cursor)
            else:
                cursor = p.getTmpVariable(person.VAR_CURSOR)
            offer = my_offers[cursor[0]]
            msg = "Passaggio {}/{}\n\n{}".format(cursor[0] + 1, cursor[1], offer.getDescription())
            kb = [[BOTTONE_ELIMINA], [BOTTONE_INDIETRO]]
            if len(my_offers) > 1:
                kb.insert(0, [PREV_ICON, NEXT_ICON])
        else:
            msg = "Hai eliminato tutte le offerte"
            kb = [[BOTTONE_INDIETRO]]
        tell(p.chat_id, msg, kb)
        p.setLastKeyboard(kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INDIETRO:
                redirectToState(p, 3)
            elif input == PREV_ICON:
                p.decreaseCursor()
                repeatState(p, put=True)
            elif input==NEXT_ICON:
                p.increaseCursor()
                repeatState(p, put=True)
            else: # input==BOTTONE_ELIMINA:
                p.deleteMyOfferAtCursor()
                repeatState(p, put=True)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 9: Info
# ================================

def goToState9(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    kb = [[BOTTONE_FERMATE], [BOTTONE_INDIETRO]]
    if giveInstruction:
        msg = '*Schermata iniziale*\n\n' \
              'Clicca su {} per vedere le fermate PickMeUp.'.format(BOTTONE_FERMATE)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_FERMATE:
            redirectToState(p, 91)
        elif input == BOTTONE_INDIETRO:
            restart(p)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)


# ================================
# GO TO STATE 91: Info Fermate
# ================================

def goToState91(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    location = kwargs['location'] if 'location' in kwargs else None
    giveInstruction = input is None
    kb = [[BOTTONE_MAPPA], [BOTTONE_INDIETRO]] #[BOTTONE_LOCATION], # NOT WORKING FOR DESKTOP
    if giveInstruction:
        msg = 'Mandami una posizione tramite la graffetta 📎 in basso o scrivi il nome di un posto (ad esempio Trento).'
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_INDIETRO:
            redirectToState(p, 9)
            return
        if input == BOTTONE_MAPPA:
            sendPhotoViaUrlOrId(p.chat_id, percorsi.FULL_MAP_IMG_URL, kb)
            return
        if input:
            loc = geoUtils.getLocationFromAddress(input)
            if loc:
                location = {
                    'latitude': loc.latitude,
                    'longitude': loc.longitude
                }
        if location:
            img_url, text = percorsi.getFermateNearPositionImgUrl(location['latitude'], location['longitude'])
            if img_url:
                sendPhotoViaUrlOrId(p.chat_id, img_url, kb)
            tell(p.chat_id, text)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)


## +++++ END OF STATES +++++ ###

# ================================
# HANDLERS
# ================================

class SafeRequestHandler(webapp2.RequestHandler):
    def handle_exception(self, exception, debug_mode):
        report_exception()


class MeHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(key.TELEGRAM_API_URL + 'getMe'))))


class SetWebhookHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        allowed_updates = ["message", "inline_query", "chosen_inline_result", "callback_query"]
        data = {
            'url': key.TELEGRAM_WEBHOOK_URL,
            'allowed_updates': json.dumps(allowed_updates),
        }
        resp = requests.post(key.TELEGRAM_API_URL + 'setWebhook', data)
        logging.info('SetWebhook Response: {}'.format(resp.text))
        self.response.write(resp.text)


class GetWebhookInfo(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        resp = requests.post(key.TELEGRAM_API_URL + 'getWebhookInfo')
        logging.info('GetWebhookInfo Response: {}'.format(resp.text))
        self.response.write(resp.text)


class DeleteWebhook(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        resp = requests.post(key.TELEGRAM_API_URL + 'deleteWebhook')
        logging.info('DeleteWebhook Response: {}'.format(resp.text))
        self.response.write(resp.text)


# ================================
# WEBHOOK HANDLER
# ================================

def send_FB_menu(sender_id):
    #"recipient": {"id": sender_id},
    response_data = {
        "setting_type": "call_to_actions",
        "thread_state": "existing_thread",
        "call_to_actions": [
            {
                "type": "postback",
                "title": "Help",
                "payload": "DEVELOPER_DEFINED_PAYLOAD_FOR_HELP"
            },
            {
                "type": "postback",
                "title": "Start a New Order",
                "payload": "DEVELOPER_DEFINED_PAYLOAD_FOR_START_ORDER"
            },
            {
                "type": "web_url",
                "title": "View Website",
                "url": "http://petersapparel.parseapp.com/"
            }
        ]
    }

    logging.info('sending menu with json: {}'.format(response_data))
    resp = requests.post(key.FACEBOOK_TRD_API_URL, json=response_data)
    logging.info('responding to request: {}'.format(resp.text))

class FBHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        challange = self.request.get('hub.challenge')
        self.response.write(challange)

    def post(self):
        # urlfetch.set_default_fetch_deadline(60)
        body = jsonUtil.json_loads_byteified(self.request.body)
        logging.info('request body: {}'.format(body))
        data = body['entry'][0]['messaging'][0]
        sender = data['sender']['id']
        if 'message' not in data:
            return
        message = data['message']['text']
        logging.info('got message ({}) from {}'.format(message, sender))

        response_data = {
            "recipient": {"id": sender},
            "message": {
                "text": message,
                "quick_replies": [
                    {
                        "content_type": "text",
                        "title": "Red",
                        "payload": "DEVELOPER_DEFINED_PAYLOAD_FOR_PICKING_RED"
                    },
                    {
                        "content_type": "text",
                        "title": "Green",
                        "payload": "DEVELOPER_DEFINED_PAYLOAD_FOR_PICKING_GREEN"
                    },
                    {
                        "content_type": "text",
                        "title": "blue",
                        "payload": "DEVELOPER_DEFINED_PAYLOAD_FOR_PICKING_GREEN"
                    },
                ]
            }
        }

        '''
        response_data = {
            "recipient": {"id": sender},
            "message":{
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": "What do you want to do next?",
                        "buttons": [
                            {
                                "type": "web_url",
                                "url": "https://petersapparel.parseapp.com",
                                "title": "Show Website"
                            },
                            {
                                "type": "postback",
                                "title": "Start Chatting",
                                "payload": "USER_DEFINED_PAYLOAD"
                            }
                        ]
                    }
                }
            }
        }
        '''

        logging.info('responding to request with json: {}'.format(response_data))
        resp = requests.post(key.FACEBOOK_MSG_API_URL, json=response_data)
        logging.info('responding to request: {}'.format(resp.text))

        send_FB_menu(sender)


class TelegramWebhookHandler(SafeRequestHandler):
    def post(self):
        # urlfetch.set_default_fetch_deadline(60)
        body = jsonUtil.json_loads_byteified(self.request.body)
        logging.info('request body: {}'.format(body))
        # self.response.write(json.dumps(body))

        # update_id = body['update_id']
        if 'message' not in body:
            return
        message = body['message']
        if 'chat' not in message:
            return

        chat = message['chat']
        chat_id = chat['id']
        if 'first_name' not in chat:
            return
        text = message.get('text') if 'text' in message else ''
        name = chat['first_name']
        last_name = chat['last_name'] if 'last_name' in chat else None
        username = chat['username'] if 'username' in chat else None
        location = message['location'] if 'location' in message else None
        contact = message['contact'] if 'contact' in message else None
        photo = message.get('photo') if 'photo' in message else None
        document = message.get('document') if 'document' in message else None
        voice = message.get('voice') if 'voice' in message else None

        def reply(msg=None, kb=None, markdown=True, inline_keyboard=False):
            tell(chat_id, msg, kb=kb, markdown=markdown, inline_keyboard=inline_keyboard)

        p = ndb.Key(Person, str(chat_id)).get()

        # setLanguage(p.language if p is not None else None)

        if p is None:
            if text.startswith("/start"):
                p = person.addPerson(chat_id, name, last_name, username)
                msg = " 😀 Ciao {},\nbenvenuto/a In PickMeUp!\n".format(p.getFirstName())
                reply(msg)
                restart(p)
                tellMaster("New user: " + name)
            else:
                reply("Premi su /start se vuoi iniziare. "
                      "Se hai qualche domanda o suggerimento non esitare di contattarmi cliccando su @kercos")
        else:
            # known user
            p.updateUserInfo(name, last_name, username)
            if text.startswith("/start"):
                msg = " 😀 Ciao {}!\nBentornato in PickMeUp!".format(name)
                reply(msg)
                restart(p)
            elif text == '/state':
                msg = "You are in state {}: {}".format(p.state, STATES.get(p.state, '(unknown)'))
                reply(msg)
            else:
                if not dealWithUniversalCommands(p, input=text):
                    logging.debug("Sending {} to state {} with input {}".format(p.getFirstName(), p.state, text))
                    repeatState(p, input=text, location=location, contact=contact, photo=photo, document=document,
                                voice=voice)


def deferredSafeHandleException(obj, *args, **kwargs):
    # return
    try:
        deferred.defer(obj, *args, **kwargs)
    except:  # catch *all* exceptions
        report_exception()


def report_exception():
    import traceback
    msg = "❗ Detected Exception: " + traceback.format_exc()
    tell(key.FEDE_CHAT_ID, msg, markdown=False)
    logging.error(msg)


app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/get_webhook_info', GetWebhookInfo),
    ('/delete_webhook', DeleteWebhook),
    (key.FACEBOOK_WEBHOOK_PATH, FBHandler),
    (key.TELEGRAM_WEBHOOK_PATH, TelegramWebhookHandler),
], debug=True)

possibles = globals().copy()
possibles.update(locals())
