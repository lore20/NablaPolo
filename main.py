# -*- coding: utf-8 -*-

from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.ext import deferred
from google.appengine.ext.db import datastore_errors

import json
import jsonUtil
import logging
from time import sleep
import requests
import utility
import geoUtils
import key
import person
from person import Person
import route
import date_time_util as dtu
import ride_offer
import params
import webapp2
import speech


########################
WORK_IN_PROGRESS = False
########################


# ================================
# ================================
# ================================

BASE_URL = 'https://api.telegram.org/bot' + key.TOKEN + '/'

STATES = {
    0: 'Initial state',
    1: 'Cerca/Richiesta/Offerta passaggio/Aggiungi Passaggio',
    11:   'Offri Passaggio',
    111:     'Passaggio a Breve (24 ore)',
    112:     'Passaggio Programmato (ripetuto)',
    13:   'Cerca Passaggio - Quando',
    14:   'Cerca Passaggio - Risultati',
    3: 'Impostazioni',
    31:   'Itinerari',
    311:     'Aggiungi Persorso Inverso',
    312:     'Rimuovi Persorso',
    32:   'Notifiche',
    33:   'Modifica Offerte',
    8:    'SpeechTest',
    9: 'Info',
    91:   'Info Fermate',
}

RESTART_STATE = 0

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

BOTTONE_SI = '✅ SI'
BOTTONE_NO = '❌ NO'
BOTTONE_INDIETRO = "🔙 INDIETRO"
BOTTONE_INIZIO = "🏠 TORNA ALL'INIZIO"
BOTTONE_INFO = "ℹ INFO"
BOTTONE_FERMATE = "🚏 FERMATE"
BOTTONE_MAPPA = "🗺 MAPPA COMPLETA"
BOTTENE_OFFRI_PASSAGGIO = "🚘 OFFRI"
BOTTENE_CERCA_PASSAGGIO = "👍 CERCA"
BOTTONE_IMPOSTAZIONI = "⚙ IMPOSTAZIONI"
BOTTONE_AGGIUNGI_PERCORSO = "➕ AGGIUNGI PERCORSO"
BOTTONE_RIMUOVI_PERCORSO = "➖ RIMUOVI PERCORSO"
BOTTONE_PERCORSI = "🛣 PERCORSI PREFERITI"
BOTTONE_NOTIFICHE = "🔔 NOTIFICHE PASSAGGI"
BOTTONE_ANNULLA = "❌ ANNULLA"
BOTTONE_ADESSO = "👇 ADESSO"
BOTTONE_A_BREVE = "⏰ A BREVE (24H)"
BOTTONE_PERIODICO = "📆 PERIODICO"
BOTTONE_CONFERMA = "👌 CONFERMA"
BOTTONE_ELIMINA_OFFERTE = "🗑🚘 ELIMINA MIE OFFERTE"
BOTTONE_ATTIVA_NOTIFICHE_TUTTE = "🔔🔔🔔 ATTIVA TUTTE"
BOTTONE_DISTATTIVA_NOTIFICHE = "🔕 DISATTIVA TUTTE"
BOTTONE_ATTIVA_NOTIFICHE_PERCORSI = "🔔🛣 MIEI PERCORSI"
BOTTONE_ELIMINA = "🗑 ELIMINA"
BOTTONE_REGOLAMENTO_ISTRUZIONI = "📜 REGOLAMENTO e ISTRUZIONI"
BOTTONE_STATS = "📊 STATISTICHE"
BOTTONE_CONTATTACI = "📩 CONTATTACI"

BOTTONE_LOCATION = {
    'text': "INVIA POSIZIONE",
    'request_location': True,
}


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

NOTIFICATION_WARNING_MSG = '🔔 Hai le notifiche attive per tutti i passaggi, ' \
              'per modificare le notifiche vai su {} → {}.'.format(BOTTONE_IMPOSTAZIONI, BOTTONE_NOTIFICHE)


def broadcast(sender, msg, qry = None, restart_user=False,
              blackList_sender=False, sendNotification=True,
              notificationWarning = False):

    if qry is None:
        qry = Person.query()
    qry = qry.order(Person._key) #_MultiQuery with cursors requires __key__ order

    more = True
    cursor = None
    total, enabledCount = 0, 0

    while more:
        users, cursor, more = qry.fetch_page(100, start_cursor=cursor)
        try:
            for p in users:
                #if p.chat_id not in key.TESTERS:
                #    continue
                if blackList_sender and p.chat_id == sender.chat_id:
                    continue
                total += 1
                p_msg = msg + '\n\n' + NOTIFICATION_WARNING_MSG \
                    if notificationWarning and p.notification_mode == params.NOTIFICATION_MODE_ALL \
                    else msg
                if tell(p.chat_id, p_msg, sleepDelay=True): #p.enabled
                    enabledCount += 1
                    if restart_user:
                        restart(p)

        except datastore_errors.Timeout:
            msg = '❗ datastore_errors.Timeout in broadcast :('
            tell_admin(msg)
            #deferredSafeHandleException(broadcast, sender, msg, qry, restart_user, curs, enabledCount, total, blackList_ids, sendNotification)
            return

    if sendNotification:
        disabled = total - enabledCount
        msg_debug = BROADCAST_COUNT_REPORT.format(total, enabledCount, disabled)
        tell(sender.chat_id, msg_debug)
    #return total, enabledCount, disabled



# ---------
# Restart All
# ---------

def restartAll(qry = None, curs=None):
    #return
    if qry is None:
        qry = Person.query()
    users, next_curs, more = qry.fetch_page(50, start_cursor=curs)
    try:
        for p in users:
            if p.enabled:
                restart(p)
            sleep(0.1)
    except datastore_errors.Timeout:
        sleep(1)
        deferredSafeHandleException(restartAll, qry, curs)
        return
    if more:
        deferredSafeHandleException(restartAll, qry, curs)

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
                #logging.info('Disabled user: ' + p.getFirstNameLastNameUserName())
            elif error_code == 400 and description == "INPUT_USER_DEACTIVATED":
                p = person.getPersonById(recipient_chat_id)
                p.setEnabled(False, put=True)
                debugMessage = '❗ Input user disactivated: ' + p.getFirstNameLastNameUserName()
                logging.debug(debugMessage)
                tell_admin(debugMessage)
            else:
                debugMessage = '❗ Raising unknown err ({}).' \
                               '\nStatus code: {}\nerror code: {}\ndescription: {}.'.format(
                    debugInfo, status_code, error_code, description)
                logging.error(debugMessage)
                # logging.debug('recipeint_chat_id: {}'.format(recipient_chat_id))
                logging.debug('Telling to {} who is in state {}'.format(p.chat_id, p.state))
                tell_admin(debugMessage)
    except:
        report_exception()


# ================================
# TELL FUNCTIONS
# ================================

def tellMaster(msg, markdown=False, one_time_keyboard=False):
    for id in key.ADMIN_CHAT_ID:
        tell(id, msg, markdown=markdown, one_time_keyboard=one_time_keyboard, sleepDelay=True)


def tellInputNonValidoUsareBottoni(chat_id, kb=None):
    msg = '⛔️ Input non riconosciuto, usa i bottoni qui sotto 🎛'
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
         sleepDelay=False, hide_keyboard=False, force_reply=False, disable_web_page_preview=True):
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
        'disable_web_page_preview': disable_web_page_preview,
        'parse_mode': 'Markdown' if markdown else '',
        'reply_markup': json.dumps(replyMarkup),
    }
    debugInfo = "tell function with msg={} and kb={}".format(msg, kb)
    success = sendRequest(key.TELEGRAM_API_URL + 'sendMessage', data, chat_id, debugInfo)
    if success:
        if sleepDelay:
            sleep(0.1)
        return True

def tell_admin(msg):
    for chat_id in key.ADMIN_CHAT_ID:
        tell(chat_id, msg, markdown=False)

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
        data = {
            'chat_id': chat_id,
            'latitude': latitude,
            'longitude': longitude,
        }
        resp = requests.post(key.TELEGRAM_API_URL + 'sendLocation', data)
        logging.info('send location: {}'.format(resp.text))
        if resp.status_code == 403:
            p = Person.query(Person.chat_id == chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.getFirstNameLastNameUserName())
    except:
        report_exception()

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
    except:
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
    except:
        report_exception()

def sendPhotoFromPngImage(chat_id, img_data, filename='image.png'):
    try:
        img = [('photo', (filename, img_data, 'image/png'))]
        data = {
            'chat_id': chat_id,
        }
        resp = requests.post(key.TELEGRAM_API_URL + 'sendPhoto', data=data, files=img)
        logging.info('Response: {}'.format(resp.text))
    except:
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
    except:
        report_exception()


# ================================
# SEND WAITING ACTION
# ================================

def sendWaitingAction(chat_id, action_tipo='typing', sleep_time=None):
    try:
        data = {
            'chat_id': chat_id,
            'action': action_tipo,
        }
        resp = requests.post(key.TELEGRAM_API_URL + 'sendChatAction', data)
        logging.info('send venue: {}'.format(resp.text))
        if resp.status_code==403:
            p = Person.query(Person.chat_id == chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.getFirstNameLastNameUserName())
        elif sleep_time:
            sleep(sleep_time)
    except:
        report_exception()


# ================================
# RESTART
# ================================
def restart(p, msg=None):
    if msg:
        tell(p.chat_id, msg)
    p.resetTmpVariable()
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
    if p.chat_id in key.ADMIN_CHAT_ID:
        if input.startswith('/broadcast ') and len(input) > 11:
            msg = '🔔 *Messaggio da PickMeUp* 🔔\n\n' + input[11:]
            logging.debug("Starting to broadcast " + msg)
            deferredSafeHandleException(broadcast, p, msg)
            return True
        elif input.startswith('/restartBroadcast ') and len(input) > 18:
            msg = '🔔 *Messaggio da PickMeUp* 🔔\n\n' + input[18:]
            logging.debug("Starting to broadcast " + msg)
            deferredSafeHandleException(broadcast, p, msg, restart_user=True)
            return True
        elif input == '/restartAll':
            deferredSafeHandleException(restartAll)
            return True
        elif input == '/testSpeech':
            redirectToState(p, 8)
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
        msg = '🏠 *Inizio*\n\n' \
              '• Premi su {} o {} per offrire/cercare passaggi\n' \
              '• Premi su {} per percorsi e notifiche\n' \
              '• Premi su {} per ottenere più info (mappa, contatti, ...)'.\
            format(BOTTENE_OFFRI_PASSAGGIO, BOTTENE_CERCA_PASSAGGIO, BOTTONE_IMPOSTAZIONI, BOTTONE_INFO)
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTENE_OFFRI_PASSAGGIO:
            if p.username is None or p.username == '-':
                msg = '⚠️ *Non hai uno username pubblico* impostato su Telegram. ' \
                      'Questo è necessario per far sì che i passeggeri ti possano contattare.\n\n' \
                      'Ti preghiamo di *scegliere uno username nelle impostazioni di Telegram* e riprovare.'
                tell(p.chat_id, msg, kb)
            else:
                redirectToState(p, 1, firstCall=True, passaggio_type='offerta')
        elif input == BOTTENE_CERCA_PASSAGGIO:
            redirectToState(p, 1, firstCall=True, passaggio_type='cerca')
        elif input == BOTTONE_IMPOSTAZIONI:
            redirectToState(p, 3)
        elif input == BOTTONE_INFO:
            redirectToState(p, 9)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 1: Imposta Percorso
# needs: input, firstCall, passaggio_type
# ================================
def goToState1(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
    if firstCall:
        passaggio_type = kwargs['passaggio_type']  # cerca, richiesta, offerta, aggiungi_preferiti
        PASSAGGIO_INFO = p.initTmpPassaggioInfo(passaggio_type)
    else:
        PASSAGGIO_INFO = p.getTmpPassaggioInfo()
        passaggio_type = PASSAGGIO_INFO['type']
    giveInstruction = input is None
    PASSAGGIO_PATH = PASSAGGIO_INFO['path']
    stage = len(PASSAGGIO_PATH)
    if giveInstruction:
        if stage == 0:
            msg = '📍 *Da dove parti?*'
            if passaggio_type in ['offerta','cerca']:
                percorsi = p.getPercorsi()
                if percorsi:
                    commands = ['🛣 {}: {}'.format(
                        params.getCommand(params.PERCORSO_COMMAND_PREFIX, n), i)
                        for n, i in enumerate(percorsi, 1)]
                    percorsiCmds = '\n\n'.join(commands)
                    msg = 'Seleziona uno dei *tuoi percorsi*:\n\n{}\n\n'.format(percorsiCmds)
                    msg += '📍 Oppure dimmi da *dove parti*.'
            kb = utility.makeListOfList(route.SORTED_ZONE_WITH_STOP_IF_SINGLE)
        elif stage == 1:
            logging.debug('Sorting fermate in {}'.format(PASSAGGIO_PATH[0]))
            fermate = route.SORTED_FERMATE_IN_ZONA(PASSAGGIO_PATH[0])
            kb = utility.makeListOfList(fermate)
            if len(fermate) == 1:
                p.setLastKeyboard(kb)
                repeatState(p, input=fermate[0])  # simulate user input
                return
            msg = '📍🚏 *Da quale fermata parti?*'
        elif stage == 2:
            msg = '🚩 *Dove vai?*'
            destinazioni = [
                l for l in route.SORTED_ZONE_WITH_STOP_IF_SINGLE \
                if not l.startswith(PASSAGGIO_PATH[0])
            ]
            kb = utility.makeListOfList(destinazioni)
        else: # stage == 3:
            fermate = route.SORTED_FERMATE_IN_ZONA(PASSAGGIO_PATH[2])
            kb = utility.makeListOfList(fermate)
            if len(fermate) == 1:
                p.setLastKeyboard(kb)
                repeatState(p, input=fermate[0])  # simulate user input
                return
            msg = '🚩🚏 *A quale fermata arrivi?*'
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if stage == 0 and input.startswith(params.PERCORSO_COMMAND_PREFIX):
            chosen_percorso = p.getPercorsoFromCommand(input)
            if chosen_percorso:
                percorsi_start_fermata_end = route.decodePercorsoToQuartet(chosen_percorso)
                PASSAGGIO_PATH.extend(percorsi_start_fermata_end)
                if passaggio_type == 'cerca':
                    showMatchedPercorsi(p, PASSAGGIO_INFO)
                else:  # passaggio_type in ['richiesta','offerta']:
                    redirectToState(p, 11)
            else:
                tellInputNonValido(p.chat_id, kb)
        else:
            voice = kwargs['voice'] if 'voice' in kwargs.keys() else None
            location = kwargs['location'] if 'location' in kwargs.keys() else None
            flat_kb = utility.flatten(kb)
            if input:
                input, perfectMatch = utility.matchInputToChoices(input, flat_kb)
                if not perfectMatch:
                    msg = 'Hai inserito: {}'.format(input)
                    tell(p.chat_id, msg)
            elif voice:
                file_id = voice['file_id']
                duration = int(voice['duration'])
                if duration > 5:
                    msg = "❗🙉 L'audio è troppo lungo, riprova!"
                    tell(p.chat_id, msg, kb)
                    return
                else:
                    transcription = speech.getTranscription(file_id, choices = flat_kb )
                    input, perfectMatch = utility.matchInputToChoices(transcription, flat_kb)
                    if input is None:
                        msg = "❗🙉 Ho capito: '{}' ma non è un posto che conosco, " \
                              "scegline uno nella lista qua sotto.".format(transcription)
                        tell(p.chat_id, msg, kb)
                        return
                    else:
                        msg = " 🎤 Hai scelto: {}".format(input)
                        tell(p.chat_id, msg)
            elif location and (stage==0 or stage==2):
                lat, lon = location['latitude'], location['longitude']
                p.setLocation(lat, lon)
                nearby_fermated_sorted_dict = route.getFermateNearPosition(lat, lon, radius=2)
                if nearby_fermated_sorted_dict is None:
                    msg = "❗📍 Non ho trovato fermate in prossimità della posizione inserita," \
                          "prova ad usare i pulsanti qua sotto.".format(input)
                    tell(p.chat_id, msg, kb)
                    return
                input = nearby_fermated_sorted_dict[0][0]
                msg = "📍 Hai scelto: {}".format(input)
                tell(p.chat_id, msg)
            if input:
                logging.debug('Received input: {}'.format(input))
                if input == BOTTONE_ANNULLA:
                    PASSAGGIO_INFO['abort'] = True
                    if passaggio_type == 'aggiungi_preferiti':
                        redirectToState(p, 31)
                    else:
                        restart(p)
                else:
                    if stage <= 3:
                        if '(' in input:  # Zona (fermata) case
                            zona, fermata = route.decodeFermataKey(input)
                            PASSAGGIO_PATH.append(zona)
                            PASSAGGIO_PATH.append(fermata)
                            # logging.debug('zona con fermata: {} ({})'.format(zona, fermata))
                        else:
                            PASSAGGIO_PATH.append(input)
                    if len(PASSAGGIO_PATH)==4: # cerca, richiesta, offerta, aggiungi_preferiti
                        if passaggio_type=='cerca':
                            showMatchedPercorsi(p, PASSAGGIO_INFO)
                        elif passaggio_type == 'aggiungi_preferiti':
                            aggiungiInPreferiti(p, PASSAGGIO_PATH)
                        else: #passaggio_type in ['richiesta','offerta']:
                            redirectToState(p, 11)
                    else:
                        repeatState(p)
            else:
                tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 11: Offri passaggio
# ================================
def goToState11(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    PASSAGGIO_PATH = PASSAGGIO_INFO['path']
    if giveInstruction:
        percorso_key = route.encodePercorsoFromQuartet(*PASSAGGIO_PATH)
        msg = "🛣 *Il tuo percorso*:\n{}\n\n".format(percorso_key)
        msg += "📆⌚ *Quando parti?*\n\n" \
               "Premi *{}* se parti ora, *{}* se parti nelle prossime 24 ore o *{}* " \
               "se vuoi programmare un viaggio regolare " \
               "(ad esempio ogni lunedì alle 8:00).".format(BOTTONE_ADESSO, BOTTONE_A_BREVE,
                                                            BOTTONE_PERIODICO)
        kb = [[BOTTONE_ADESSO], [BOTTONE_A_BREVE, BOTTONE_PERIODICO]]
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        PASSAGGIO_INFO['mode'] = input
        if input in utility.flatten(kb):
            if input == BOTTONE_ADESSO:
                dt = dtu.nowCET()
                sendWaitingAction(p.chat_id)
                finalizeOffer(p, PASSAGGIO_PATH, dt, time_mode=input)
                restart(p)
            elif input == BOTTONE_A_BREVE:
                redirectToState(p, 111)
            else:  # BOTTONE_PROGRAMMATO
                redirectToState(p, 112)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 111: Offri passaggio a breve (24 ore)
# ================================

def goToState111(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    PASSAGGIO_TIME = PASSAGGIO_INFO['time']
    giveInstruction = input is None
    stage = len(PASSAGGIO_TIME)
    if giveInstruction:
        current_hour = dtu.nowCET().hour
        if stage == 0:
            msg = '⌚ *A che ora parti?*'
            current_min = dtu.nowCET().minute
            if current_min > 52:
                current_hour += 1
            circular_range = range(current_hour, 24) + range(0, current_hour)
            hours = [str(x).zfill(2) for x in circular_range]
            kb = utility.distributeElementMaxSize(hours, 8)
        else:
            msg = '⌚ *A che minuto parti?*'
            startNowMinutes = current_hour == PASSAGGIO_TIME[0]
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
            PASSAGGIO_INFO['abort'] = True
            restart(p)
            return
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            PASSAGGIO_TIME.append(int(input))
            if stage == 0:
                repeatState(p)
            else:
                PASSAGGIO_PATH = PASSAGGIO_INFO['path']
                time_mode = PASSAGGIO_INFO['mode']
                dt = dtu.nowCET()
                dt = dt.replace(hour=PASSAGGIO_TIME[0], minute=PASSAGGIO_TIME[1])
                if dt.time() < dtu.nowCET().time():
                    dt = dtu.get_date_tomorrow(dt)
                sendWaitingAction(p.chat_id)
                finalizeOffer(p, PASSAGGIO_PATH, dt, time_mode=time_mode)
                restart(p)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 112: Offri passaggio periodico
# ================================

def goToState112(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    DAYS = PASSAGGIO_INFO['days']
    TIME_HH_MM = PASSAGGIO_INFO['time']
    STAGE = PASSAGGIO_INFO['stage']
    giveInstruction = input is None
    if giveInstruction:
        if STAGE == 0:
            if DAYS:
                msg = '*Puoi selezionare altri giorni o premere* {}'.format(BOTTONE_CONFERMA)
            else:
                msg = '*In che giorni effettui il viaggio?*'
            g = lambda x: '{}{}'.format(CHECK_ICON, x) if params.GIORNI_SETTIMANA.index(x) in DAYS else x
            GIORNI_CHECK = [g(x) for x in params.GIORNI_SETTIMANA]
            kb = [GIORNI_CHECK]
            if len(DAYS) > 0:
                kb.append([BOTTONE_CONFERMA])
        elif STAGE == 1:
            msg = '*A che ora parti?*'
            start_hour = 6
            circular_range = list(range(start_hour, 24)) + list(range(0, start_hour))
            hours = [str(x).zfill(2) for x in circular_range]
            kb = utility.distributeElementMaxSize(hours, 8)
        else:  # STAGE == 2
            msg = '*A che minuto parti?*'
            minutes = [str(x).zfill(2) for x in range(0, 60, 5)]
            kb = utility.distributeElementMaxSize(minutes, 6)
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_ANNULLA:
            PASSAGGIO_INFO['abort'] = True
            restart(p)
            return
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if STAGE == 0:  # DAYS
                if input == BOTTONE_CONFERMA:
                    PASSAGGIO_INFO['stage'] += 1
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
            elif STAGE == 1:  # hour
                PASSAGGIO_INFO['stage'] += 1
                TIME_HH_MM.append(int(input))
                repeatState(p)
            else:  # minute
                TIME_HH_MM.append(int(input))
                time_mode = PASSAGGIO_INFO['mode']
                PASSAGGIO_PATH = PASSAGGIO_INFO['path']
                dt = dtu.nowCET()
                dt = dt.replace(hour=TIME_HH_MM[0], minute=TIME_HH_MM[1])
                if dt.time() < dtu.nowCET().time():
                    dt = dtu.get_date_tomorrow(dt)
                sendWaitingAction(p.chat_id)
                finalizeOffer(p, PASSAGGIO_PATH, dt, time_mode = time_mode,
                              programmato=True, programmato_giorni=DAYS)
                restart(p)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# FOR OFFERS
def finalizeOffer(p, path, date_time, time_mode, programmato=False, programmato_giorni=()):
    date_time = dtu.removeTimezone(date_time)
    percorso = route.encodePercorsoFromQuartet(*path)
    o = ride_offer.addRideOffer(p, date_time, percorso, time_mode, programmato, programmato_giorni)
    ride_description_no_driver_info = o.getDescription(driver_info=False)
    msg = "Grazie per aver inserito l'offerta di passaggio\n{}".format(ride_description_no_driver_info)
    if p.isTester():
        msg += '\n\n👷 Sei un tester del sistema, info di debug in arrivo...'
    tell(p.chat_id, msg)
    deferredSafeHandleException(broadCastOffer, p, o)

def broadCastOffer(p, o):
    percorsi_passeggeri_compatibili, fermate_interemedie_routes = o.computePercorsiPasseggeriCompatibili()
    qry = person.getPeopleMatchingRideQry(percorsi_passeggeri_compatibili)
    if p.isTester():
        fermate_intermedie_str = [', '.join(x) for x in fermate_interemedie_routes]
        debug_msg = '👷 *Debug info:*\n'
        debug_msg += '{} tragitto/i trovati per viaggio\n*{}*:\n\n'.format(len(fermate_intermedie_str), o.getPercorso())
        debug_msg += '\n\n'.join(['*{}.* {}'.format(n, flist) for n, flist in enumerate(fermate_intermedie_str, 1)])
        debug_msg += '\n\n({} tragitti passeggeri compatibili)'.format(o.getNumberPercorsiPasseggeriCompatibili())
        tell(p.chat_id, debug_msg)
        logging.debug(debug_msg)
    msg_broadcast = '🚘 *Nuova offerta di passagio*:\n\n{}'.format(o.getDescription())
    broadcast(p, msg_broadcast, qry, blackList_sender=True,
              sendNotification=False, notificationWarning=True)


# FOR SEARCHES
def showMatchedPercorsi(p, PASSAGGIO_INFO):
    import pickle
    PASSAGGIO_PATH = PASSAGGIO_INFO['path']
    percorso = route.encodePercorsoFromQuartet(*PASSAGGIO_PATH)
    sendWaitingAction(p.chat_id)
    offers_per_day = ride_offer.getActiveRideOffersSortedPerDay(percorso)
    PASSAGGIO_INFO['search_results_per_day_pkl_dumps'] = pickle.dumps(offers_per_day)
    percorsi_num = sum([len(l) for l in offers_per_day])
    msg = "🛣 *Il tuo percorso*:\n{}\n\n".format(percorso)
    if percorsi_num == 1:
        # if only one skip choosing day
        chosen_day = [i for i,x in enumerate(offers_per_day) if len(x)==1][0]
        PASSAGGIO_INFO['search_chosen_day'] = chosen_day
        msg += "🚘 *{} passaggio trovato*".format(percorsi_num)
        tell(p.chat_id, msg)
        sendWaitingAction(p.chat_id, sleep_time=1)
        redirectToState(p, 14, firstCall=True)
    elif percorsi_num > 0:
        msg += "🚘 *{} passaggi trovati*".format(percorsi_num)
        tell(p.chat_id, msg)
        redirectToState(p, 13)
    else:
        msg += "🙊 *Nessun passaggio trovato*"
        tell(p.chat_id, msg)
        sendWaitingAction(p.chat_id, sleep_time=1)
        restart(p)

# ================================
# GO TO STATE 13: Cerca Passaggio - Quando
# ================================

def goToState13(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    giveInstruction = input is None
    if giveInstruction:
        msg = '📆 *Quando vuoi partire?*'
        offers_per_day = PASSAGGIO_INFO['search_results_per_day_pkl_dumps']
        today = dtu.getWeekday()
        giorni_sett_oggi_domani = params.GIORNI_SETTIMANA[today:] + params.GIORNI_SETTIMANA[:today]
        giorni_sett_oggi_domani[:2] = ['OGGI', 'DOMANI']
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
                chosen_day = (flat_kb.index(input) - 1 + today) % 7  # -1 because of BOTTONE_ANNULLA
                PASSAGGIO_INFO['search_chosen_day'] = chosen_day
                sendWaitingAction(p.chat_id, sleep_time=1)
                redirectToState(p, 14, firstCall=True)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 14: Cerca Passaggio - Risultati
# ================================

def goToState14(p, **kwargs):
    import pickle
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        PASSAGGIO_INFO = p.getTmpPassaggioInfo()
        chosen_day = PASSAGGIO_INFO['search_chosen_day']
        offers_per_day = pickle.loads(PASSAGGIO_INFO['search_results_per_day_pkl_dumps'])
        offers_chosen_day = offers_per_day[chosen_day]
        firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
        if firstCall:
            cursor = [0, len(offers_chosen_day)]
            p.setTmpVariable(person.VAR_CURSOR, cursor)
        else:
            cursor = p.getTmpVariable(person.VAR_CURSOR)
        #logging.debug('offers_chosen_day: {}'.format(offers_chosen_day))
        offer = offers_chosen_day[cursor[0]]
        msg = "🚘 Passaggio {}/{}\n\n{}".format(cursor[0]+1, cursor[1], offer.getDescription())
        single_offer = len(offers_chosen_day) == 1
        kb = [] if single_offer else [[BOTTONE_INDIETRO]]
        if len(offers_chosen_day)>1:
            kb.insert(0, [PREV_ICON, NEXT_ICON])
        kb.insert(0, [BOTTONE_INIZIO])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INIZIO:
                restart(p)
                return
            elif input==BOTTONE_INDIETRO:
                redirectToState(p, 13)
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
        msg = '⚙ *Le tue impostazioni*'
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
# GO TO STATE 31: Percorsi
# ================================

def goToState31(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    percorsi = p.getPercorsi()
    if giveInstruction:
        AGGIUNGI_RIMUOVI_BUTTONS = [BOTTONE_AGGIUNGI_PERCORSO]
        if percorsi:
            AGGIUNGI_RIMUOVI_BUTTONS.append(BOTTONE_RIMUOVI_PERCORSO)
        kb = [[BOTTONE_INIZIO], AGGIUNGI_RIMUOVI_BUTTONS, [BOTTONE_INDIETRO]]
        msg = '🛣 *I tuoi percorsi*\n\n'
        if percorsi:
            msg += '\n'.join(['∙ {}'.format(i) for i in percorsi])
        else:
            msg += '🤷‍♀️ Nessun percorso inserito.'
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INIZIO:
                restart(p)
            elif input == BOTTONE_INDIETRO:
                redirectToState(p, 3)
            elif input == BOTTONE_AGGIUNGI_PERCORSO:
                reached_max_percorsi = len(percorsi) >= params.MAX_PERCORSI
                if reached_max_percorsi:
                    msg = '🙀 Hai raggiunto il numero massimo di percorsi.'
                    tell(p.chat_id, msg, kb)
                    sendWaitingAction(p.chat_id, sleep_time=1)
                    redirectToState(p, 31)
                else:
                    redirectToState(p, 1, firstCall=True, passaggio_type='aggiungi_preferiti')
            else: # input == BOTTONE_RIMUOVI_PERCORSO
                redirectToState(p, 312)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)


# ================================
# Aggiungi in Preferiti - from 1
# ================================

def aggiungiInPreferiti(p, PASSAGGIO_PATH):
    percorso = route.encodePercorsoFromQuartet(*PASSAGGIO_PATH)
    if p.appendPercorsi(percorso):
        msg = '🛣 *Hai aggiunto il percorso*:\n{}'.format(percorso)
        tell(p.chat_id, msg)
        sendWaitingAction(p.chat_id, sleep_time=1)
        REVERSE_PATH = route.getReversePath(*PASSAGGIO_PATH)
        percorso = route.encodePercorsoFromQuartet(*REVERSE_PATH)
        if p.getPercorsiSize() < params.MAX_PERCORSI and not p.percorsoIsPresent(percorso):
            redirectToState(p, 311, reverse_path=REVERSE_PATH)
        else:
            redirectToState(p, 31)
    else:
        msg = '🤦‍♂️ *Percorso già inserito*:\n{}'.format(percorso)
        tell(p.chat_id, msg)
        sendWaitingAction(p.chat_id, sleep_time=1)
        redirectToState(p, 31)


# ================================
# GO TO STATE 311: Add Percorso Inverso
# ================================

def goToState311(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    if giveInstruction:
        REVERSE_PATH = kwargs['reverse_path']
        percorso = route.encodePercorsoFromQuartet(*REVERSE_PATH)
        PASSAGGIO_INFO['percorso'] = percorso
        msg = "↩️ *Vuoi anche inserire il passaggio inverso?*\n{}".format(percorso)
        kb = [[BOTTONE_SI, BOTTONE_NO]]
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_SI:
                percorso = PASSAGGIO_INFO['percorso']
                inserted = p.appendPercorsi(percorso)
                assert(inserted)
                msg = '🛣 *Hai aggiunto il percorso*:\n{}'.format(percorso)
                tell(p.chat_id, msg)
                sendWaitingAction(p.chat_id, sleep_time=1)
            redirectToState(p, 31)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 312: Rimuovi Percorsi
# ================================

def goToState312(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    percorsi = p.getPercorsi()
    if giveInstruction:
        msg = "*Premi il numero corrispondente al percorso che vuoi rimuovere.*\n\n"
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
                percorso = p.removePercorsi(n - 1)
                msg = '*Percorso cancellato*:\n{}'.format(percorso)
                tell(p.chat_id, msg)
                if p.getPercorsiSize()>0:
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
        #logging.debug("NOTIFICA_ATTIVA: {}".format(NOTIFICA_ATTIVA))
        active_index = NOTIFICHE_MODES.index(NOTIFICA_ATTIVA)
        NOTIFICHE_MODES.pop(active_index)
        NOTIFICHE_BUTTONS.pop(active_index)
        if NOTIFICA_ATTIVA == params.NOTIFICATION_MODE_NONE:
            msg = '🔕 Non hai *nessuna notifica attiva*.'
        elif NOTIFICA_ATTIVA == params.NOTIFICATION_MODE_PERCORSI:
            msg = '🔔🛣 Hai attivato le notifiche dei passaggio corrispondenti ai *tuoi percorsi*.'
        else: #BOTTONE_NOTIFICHE_TUTTE
            msg = '🔔🔔🔔 Hai attivato le notifiche per *tutti i passaggi*.'
        kb = utility.makeListOfList(NOTIFICHE_BUTTONS)
        kb.append([BOTTONE_INDIETRO])
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
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
            tell(p.chat_id, msg)
            sendWaitingAction(p, sleep_time=1)
            redirectToState(p, 3)
            return
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
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
# GO TO STATE 8: SpeechTest
# ================================

def goToState8(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    kb = [[BOTTONE_INIZIO]]
    if giveInstruction:
        msg = 'Prova a dire qualcosa...'
        tell(p.chat_id, msg, kb)
    else:
        voice = kwargs['voice'] if 'voice' in kwargs.keys() else None
        if input == BOTTONE_INIZIO:
            restart(p)
        elif voice:
            file_id = voice['file_id']
            duration = int(voice['duration'])
            if duration > 5:
                text = 'Sorry, your audio is too long.'
            else:
                text = speech.getTranscription(file_id, choices = ())
            tell(p.chat_id, text)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)


# ================================
# GO TO STATE 9: Info
# ================================

def goToState9(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    kb = [[BOTTONE_INIZIO], [BOTTONE_REGOLAMENTO_ISTRUZIONI], [BOTTONE_FERMATE], [BOTTONE_CONTATTACI, BOTTONE_STATS]]
    if giveInstruction:
        msg_lines = ['*Informazioni*']
        msg_lines.append('*PickMeUp* è un servizio di carpooling attualmente in sperimentazione nella provincia di Trento.')
        msg_lines.append('Clicca su {} o uno dei pulsanti qua sotto per avere maggiori informazioni.'.format(BOTTONE_REGOLAMENTO_ISTRUZIONI))
        msg = '\n\n'.join(msg_lines)
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_INIZIO:
            restart(p)
        elif input == BOTTONE_REGOLAMENTO_ISTRUZIONI:
            msg = 'https://docs.google.com/document/d/1hiP_rQKOiiPZwvqtZF3k0cGdqS1SZqs3VV7TIx9_s8o'
            tell(p.chat_id, msg, kb, markdown=False, disable_web_page_preview=False)
        elif input == BOTTONE_FERMATE:
            redirectToState(p, 91)
        elif input == BOTTONE_STATS:
            msg = utility.unindent(
                '''
                👤 Utenti: {}
                
                🚘 Passaggi attivi nei prossimi 7 giorni: {}
                📆🚘 Passaggi inseriti negli ultimi 7 giorni: {}                                
                '''
            ).format(
                person.getPeopleCount(),
                ride_offer.getActiveRideOffersCountInWeek(),
                ride_offer.getRideOfferInsertedLastDaysQry(7).count()
            )
            tell(p.chat_id, msg)
        elif input == BOTTONE_CONTATTACI:
            redirectToState(p, 92)
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
        msg = '∙ 📌 Mandami una *posizione GPS* (tramite la graffetta in basso), oppure\n' \
              '∙ ✏️🏷 scrivi un *indirizzo* (ad esempio "via rosmini trento"), oppure\n' \
              '∙ clicca su {}'.format(BOTTONE_MAPPA) #📎
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_INDIETRO:
            redirectToState(p, 9)
            return
        if input == BOTTONE_MAPPA:
            #sendPhotoViaUrlOrId(p.chat_id, percorsi.FULL_MAP_IMG_URL, kb)
            with open('data/pmu_map_low.png') as file_data:
                sendPhotoFromPngImage(p.chat_id, file_data, 'mappa.png')
            return
        if input:
            loc = geoUtils.getLocationFromAddress(input)
            if loc:
                p.setLocation(loc.latitude, loc.longitude, put=True)
                location = {
                    'latitude': loc.latitude,
                    'longitude': loc.longitude
                }
        if location:
            p.setLocation(location['latitude'], location['longitude'])
            img_url, text = route.getFermateNearPositionImgUrl(location['latitude'], location['longitude'])
            if img_url:
                sendPhotoViaUrlOrId(p.chat_id, img_url, kb)
            tell(p.chat_id, text)
        else:
            tellInputNonValidoUsareBottoni(p.chat_id, kb)

# ================================
# GO TO STATE 92: Contattaci
# ================================

def goToState92(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        kb = [[BOTTONE_INDIETRO]]
        msg = '📩 Non esitate a *contattarci*:\n\n' \
              '∙ 📝 Scrivi qua sotto qualsiasi feedback o consiglio\n' \
              '∙ 🗣 Entrare in chat con noi cliccando su @kercos\n' \
              '∙ 📬 Mandaci un email a pickmeupbot@gmail.com'
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input == BOTTONE_INDIETRO:
            redirectToState(p, 9)
            return
        else:
            msg = '📩📩📩\nMessaggio di feedback da {}:\n{}'.format(p.getFirstNameLastNameUserName(), input)
            tell_admin(msg)


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
        json_response = requests.get(key.TELEGRAM_API_URL + 'getMe').json()
        self.response.write(json.dumps(json_response))
        #self.response.write(json.dumps(json.load(urllib2.urlopen(key.TELEGRAM_API_URL + 'getMe'))))


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
            p = person.addPerson(chat_id, name, last_name, username)
            msg = " 😀 Ciao {},\nbenvenuto/a In PickMeUp!\n" \
                  "Se hai qualche domanda o suggerimento non esitare " \
                  "di contattarci cliccando su @kercos".format(p.getFirstName())
            reply(msg)
            restart(p)
            tellMaster("New user: " + name)
        else:
            # known user
            p.updateUserInfo(name, last_name, username)
            if text.startswith("/start"):
                msg = " 😀 Ciao {}!\nBentornato/a in PickMeUp!".format(name)
                reply(msg)
                restart(p)
            elif text == '/state':
                msg = "You are in state {}: {}".format(p.state, STATES.get(p.state, '(unknown)'))
                reply(msg)
            elif WORK_IN_PROGRESS and p.chat_id not in key.TESTERS:
                reply("🏗 Il sistema è in aggiornamento.")
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
    tell_admin(msg)
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
