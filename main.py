# -*- coding: utf-8 -*-

import main_fb
import main_telegram

import logging
from time import sleep
import utility
import geoUtils
import key
import person
from person import Person
import routing_util
import date_time_util as dtu
import ride_offer
import route
import params
import webapp2


########################
WORK_IN_PROGRESS = False
########################


# ================================
# ================================
# ================================

BASE_URL = 'https://api.telegram.org/bot' + key.TELEGRAM_TOKEN + '/'

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
    92:   'Contattaci',
}

RESTART_STATE = 0
SETTINGS_STATE = 3
HELP_STATE = 9

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
BOTTONE_OGGI = "⏰ OGGI"
BOTTONE_PROX_GIORNI = "📆 PROX. GIORNI"
BOTTONE_PERIODICO = "🔄📆 PERIODICO"
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
# TEMPLATE API CALLS
# ================================

def send_message(p, msg, kb=None, markdown=True, inline_keyboard=False, one_time_keyboard=False,
         sleepDelay=False, hide_keyboard=False, force_reply=False, disable_web_page_preview=True):
    if p.isTelegramUser():
        return main_telegram.send_message(p, msg, kb, markdown, inline_keyboard, one_time_keyboard,
                           sleepDelay, hide_keyboard, force_reply, disable_web_page_preview)
    else:
        if kb is None:
            kb = p.getLastKeyboard()
        if kb:
            kb_flat = utility.flatten(kb)[:11] # no more than 11
            return main_fb.sendMessageWithQuickReplies(p, msg, kb_flat)
        else:
            return main_fb.sendMessage(p, msg)
        #main_fb.sendMessageWithButtons(p, msg, kb_flat)

def send_photo_png_data(p, file_data, filename):
    if p.isTelegramUser():
        main_telegram.sendPhotoFromPngImage(p.chat_id, file_data, filename)
    else:
        main_fb.sendPhotoData(p, file_data, filename)
        # send message to show kb
        kb = p.getLastKeyboard()
        if kb:
            msg = 'Opzioni disponibili:'
            kb_flat = utility.flatten(kb)[:11] # no more than 11
            main_fb.sendMessageWithQuickReplies(p, msg, kb_flat)

def send_photo_url(p, url, kb=None):
    if p.isTelegramUser():
        main_telegram.sendPhotoViaUrlOrId(p.chat_id, url, kb)
    else:
        #main_fb.sendPhotoUrl(p.chat_id, url)
        import requests
        file_data = requests.get(url).content
        main_fb.sendPhotoData(p, file_data, 'file.png')
        # send message to show kb
        kb = p.getLastKeyboard()
        if kb:
            msg = 'Opzioni disponibili:'
            kb_flat = utility.flatten(kb)[:11]  # no more than 11
            main_fb.sendMessageWithQuickReplies(p, msg, kb_flat)

def sendWaitingAction(p, action_type='typing', sleep_time=None):
    if p.isTelegramUser():
        main_telegram.sendWaitingAction(p.chat_id, action_type, sleep_time)
    else:
        pass


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

    from google.appengine.ext.db import datastore_errors
    from google.appengine.api.urlfetch_errors import InternalTransientError

    if qry is None:
        qry = Person.query()
    qry = qry.order(Person._key) #_MultiQuery with cursors requires __key__ order

    more = True
    cursor = None
    total, enabledCount = 0, 0

    while more:
        users, cursor, more = qry.fetch_page(100, start_cursor=cursor)
        for p in users:
            try:
                #if p.getId() not in key.TESTERS:
                #    continue
                if not p.enabled:
                    continue
                if blackList_sender and sender and p.getId() == sender.getId():
                    continue
                total += 1
                p_msg = msg + '\n\n' + NOTIFICATION_WARNING_MSG \
                    if notificationWarning and p.notification_mode == params.NOTIFICATION_MODE_ALL \
                    else msg
                if send_message(p, p_msg, sleepDelay=True): #p.enabled
                    enabledCount += 1
                    if restart_user:
                        restart(p)
            except datastore_errors.Timeout:
                msg = '❗ datastore_errors. Timeout in broadcast :('
                tell_admin(msg)
                #deferredSafeHandleException(broadcast, sender, msg, qry, restart_user, curs, enabledCount, total, blackList_ids, sendNotification)
                return
            except InternalTransientError:
                msg = 'Internal Transient Error, waiting for 1 min.'
                tell_admin(msg)
                sleep(60)
                continue

    disabled = total - enabledCount
    msg_debug = BROADCAST_COUNT_REPORT.format(total, enabledCount, disabled)
    logging.debug(msg_debug)
    if sendNotification:
        send_message(sender, msg_debug)
    #return total, enabledCount, disabled



# ---------
# Restart All
# ---------

def restartAll(qry = None, curs=None):
    from google.appengine.ext.db import datastore_errors
    from main_exception import deferredSafeHandleException
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
# UTILIITY TELL FUNCTIONS
# ================================

def tellMaster(msg, markdown=False, one_time_keyboard=False):
    for id in key.ADMIN_IDS:
        p = person.getPersonById(id)
        main_telegram.send_message(
            p, msg, markdown=markdown,
            one_time_keyboard=one_time_keyboard,
            sleepDelay=True
        )

def tellInputNonValidoUsareBottoni(p, kb=None):
    msg = '⛔️ Input non riconosciuto, usa i bottoni qui sotto 🎛'
    send_message(p, msg, kb)

def tellInputNonValido(p, kb=None):
    msg = '⛔️ Input non riconosciuto.'
    send_message(p, msg, kb)

def tell_admin(msg):
    logging.debug(msg)
    for id in key.ADMIN_IDS:
        p = person.getPersonById(id)
        send_message(p, msg, markdown=False)

def send_message_to_person(id, msg, markdown=False):
    p = Person.get_by_id(id)
    send_message(p, msg, markdown=markdown)
    if p and p.enabled:
        return True
    return False

# ================================
# RESTART
# ================================
def restart(p, msg=None):
    if msg:
        send_message(p, msg)
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
        send_message(p, "Si è verificato un problema (" + methodName +
             "). Segnalamelo mandando una messaggio a @zolfariot" + '\n' +
             "Ora verrai reindirizzat+ nella schermata iniziale.")
        restart(p)
    else:
        if put:
            p.put()
        method(p, **kwargs)

# ================================
# UNIVERSAL COMMANDS
# ================================

def dealWithUniversalCommands(p, input):
    from main_exception import deferredSafeHandleException
    if p.isAdmin():
        if input.startswith('/testText '):
            text = input.split(' ', 1)[1]
            if text:
                msg = '🔔 *Messaggio da ∇Polo* 🔔\n\n' + text
                logging.debug("Test broadcast " + msg)
                send_message(p, msg)
                return True
        if input.startswith('/broadcast '):
            text = input.split(' ', 1)[1]
            if text:
                msg = '🔔 *Messaggio da ∇Polo* 🔔\n\n' + text
                logging.debug("Starting to broadcast " + msg)
                deferredSafeHandleException(broadcast, p, msg)
                return True
        elif input.startswith('/restartBroadcast '):
            text = input.split(' ', 1)[1]
            if text:
                msg = '🔔 *Messaggio da ∇Polo* 🔔\n\n' + text
                logging.debug("Starting to broadcast and restart" + msg)
                deferredSafeHandleException(broadcast, p, msg, restart_user=False)
                return True
        elif input.startswith('/textUser '):
            p_id, text = input.split(' ', 2)[1]
            if text:
                p = Person.get_by_id(p_id)
                if send_message(p, text, kb=p.getLastKeyboard()):
                    msg_admin = 'Message sent successfully to {}'.format(p.getFirstNameLastNameUserName())
                    tell_admin(msg_admin)
                else:
                    msg_admin = 'Problems sending message to {}'.format(p.getFirstNameLastNameUserName())
                    tell_admin(msg_admin)
                return True
        elif input.startswith('/restartUser '):
            p_id = input.split(' ')[1]
            p = Person.get_by_id(p_id)
            restart(p)
            msg_admin = 'User restarted: {}'.format(p.getFirstNameLastNameUserName())
            tell_admin(msg_admin)
            return True
        elif input == '/testlist':
            p_id = key.FEDE_FB_ID
            p = Person.get_by_id(p_id)
            main_fb.sendMessageWithList(p, 'Prova lista template', ['one','twp','three','four'])
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
        msg = ' 🏗 **Work In Progress** 🏗\n ' \
              ' *Servizio in fase sperimentale!*\n\n' \
              '🏠 *Inizio*\n\n' \
              '• Premi su {} o {} per offrire/cercare passaggi\n' \
              '• Premi su {} per percorsi e notifiche\n' \
              '• Premi su {} per ottenere più info (mappa, contatti, ...)'.\
            format(BOTTENE_OFFRI_PASSAGGIO, BOTTENE_CERCA_PASSAGGIO, BOTTONE_IMPOSTAZIONI, BOTTONE_INFO)
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        if input == BOTTENE_OFFRI_PASSAGGIO:
            if not p.isTelegramUser():
                msg = '⚠️ La possibilità di offrire passaggi è consentita solo a utenti registrati su Telegram. ' \
                      'Ti preghiamo di installare Telegram e aggiungere il bot ' \
                      '@PickMeUpBot (http://t.me/pickmeup_bot).\n\n'
                send_message(p, msg, kb)
            elif p.username is None or p.username == '-':
                msg = '⚠️ *Non hai uno username pubblico* impostato su Telegram. ' \
                      'Questo è necessario per far sì che i passeggeri ti possano contattare.\n\n' \
                      'Ti preghiamo di *scegliere uno username nelle impostazioni di Telegram* e riprovare.'
                send_message(p, msg, kb)
            else:
                redirectToState(p, 1, firstCall=True, passaggio_type='offerta')
        elif input == BOTTENE_CERCA_PASSAGGIO:
            redirectToState(p, 1, firstCall=True, passaggio_type='cerca')
        elif input == BOTTONE_IMPOSTAZIONI:
            redirectToState(p, 3)
        elif input == BOTTONE_INFO:
            redirectToState(p, 9)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

# ================================
# GO TO STATE 1: Imposta Percorso
# needs: input, firstCall, passaggio_type
# ================================
def goToState1(p, **kwargs):
    import speech
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
            msg = '📍 *Da dove parti?*\n' \
                  '   ∙ 🎛 usa i pulsanti sotto, oppure\n' \
                  '   ∙ 🗺📌 inviami una posizione GPS'
            if passaggio_type in ['offerta','cerca']:
                percorsi = p.getPercorsi()
                if percorsi:
                    commands = ['     🛣 {}: {}'.format(
                        params.getCommand(params.PERCORSO_COMMAND_PREFIX, n), i)
                        for n, i in enumerate(percorsi, 1)]
                    percorsiCmds = '\n\n'.join(commands)
                    msg += ' oppure\n' \
                           '   ∙ seleziona uno dei *tuoi percorsi*:\n\n{}\n\n'.format(percorsiCmds)
            kb = utility.makeListOfList(routing_util.SORTED_ZONE_WITH_STOP_IF_SINGLE)
        elif stage == 1:
            logging.debug('Sorting fermate in {}'.format(PASSAGGIO_PATH[0]))
            fermate = routing_util.SORTED_STOPS_IN_ZONA(PASSAGGIO_PATH[0])
            kb = utility.makeListOfList(fermate)
            if len(fermate) == 1:
                p.setLastKeyboard(kb)
                repeatState(p, input=fermate[0])  # simulate user input
                return
            msg = '📍🚏 *Da quale fermata parti?*'
        elif stage == 2:
            msg = '🚩 *Dove vai?*\n' \
                  '   ∙ 🎛 usa i pulsanti sotto, oppure\n' \
                  '   ∙ 🗺📌 inviami una posizione GPS'
            destinazioni = routing_util.SORTED_ZONE_WITH_STOP_IF_SINGLE
            fermata_start = routing_util.encodeFermataKey(PASSAGGIO_PATH[0], PASSAGGIO_PATH[1])
            if fermata_start in destinazioni:
                destinazioni.remove(fermata_start)
            #destinazioni = [
            #    l for l in route.SORTED_ZONE_WITH_STOP_IF_SINGLE \
            #    if not l.startswith(PASSAGGIO_PATH[0])
            #]
            kb = utility.makeListOfList(destinazioni)
        else: # stage == 3:
            fermate = routing_util.SORTED_STOPS_IN_ZONA(PASSAGGIO_PATH[2])
            if PASSAGGIO_PATH[0]==PASSAGGIO_PATH[2]: # same zona
                fermate.remove(PASSAGGIO_PATH[1]) # remove start_stop
            kb = utility.makeListOfList(fermate)
            #if len(fermate) == 1:
            #    p.setLastKeyboard(kb)
            #    repeatState(p, input=fermate[0])  # simulate user input
            #    return
            msg = '🚩🚏 *A quale fermata arrivi?*'
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if stage == 0 and input.startswith(params.PERCORSO_COMMAND_PREFIX):
            chosen_percorso = p.getPercorsoFromCommand(input)
            if chosen_percorso:
                percorsi_start_fermata_end = routing_util.decodePercorsoToQuartet(chosen_percorso)
                PASSAGGIO_PATH.extend(percorsi_start_fermata_end)
                if passaggio_type == 'cerca':
                    showMatchedPercorsi(p, PASSAGGIO_INFO)
                else:  # passaggio_type in ['richiesta','offerta']:
                    redirectToState(p, 11)
            else:
                tellInputNonValido(p, kb)
        else:
            voice = kwargs['voice'] if 'voice' in kwargs.keys() else None
            location = kwargs['location'] if 'location' in kwargs.keys() else None
            flat_kb = utility.flatten(kb)
            choices = list(flat_kb)
            if stage == 0 or stage == 2:
                choices.extend(routing_util.FERMATE.keys())
                choices = list(set(choices))
            if input:
                input, perfectMatch = utility.matchInputToChoices(input, choices)
                if input and not perfectMatch:
                    msg = 'Hai inserito: {}'.format(input)
                    send_message(p, msg)
            elif voice:
                file_id = voice['file_id']
                duration = int(voice['duration'])
                if duration > 5:
                    msg = "❗🙉 L'audio è troppo lungo, riprova!"
                    send_message(p, msg, kb)
                    return
                else:
                    transcription = speech.getTranscriptionTelegram(file_id, choices)
                    input, perfectMatch = utility.matchInputToChoices(transcription, choices)
                    if input is None:
                        if transcription:
                            msg = "❗🙉 Non ho capito, " \
                                  "scegli un posto dalla lista qua sotto.".format(transcription)
                        else:
                            msg = "❗🙉 Ho capito: '{}' ma non è un posto che conosco, " \
                                  "scegli un posto dalla lista qua sotto.".format(transcription)
                        send_message(p, msg, kb)
                        return
                    else:
                        msg = " 🎤 Hai scelto: {}".format(input)
                        send_message(p, msg)
            elif location and (stage==0 or stage==2):
                lat, lon = location['latitude'], location['longitude']
                p.setLocation(lat, lon)
                nearby_fermated_sorted_dict = routing_util.getFermateNearPosition(lat, lon, radius=4)
                if not nearby_fermated_sorted_dict:
                    msg = "❗ 🗺📌 Non ho trovato fermate in prossimità della posizione inserita," \
                          "prova ad usare i pulsanti qua sotto 🎛".format(input)
                    send_message(p, msg, kb)
                    return
                input = nearby_fermated_sorted_dict[0][0]
                msg = "🗺📌 Hai scelto: {}".format(input)
                send_message(p, msg)
                sendWaitingAction(p, sleep_time=1)
            if input:
                logging.debug('Received input: {}'.format(input))
                if input == BOTTONE_ANNULLA:
                    if passaggio_type == 'aggiungi_preferiti':
                        redirectToState(p, 31)
                    else:
                        restart(p)
                else:
                    if stage <= 3:
                        if '(' in input:  # Zona (fermata) case
                            if stage == 2:
                                fermata_key_partenza = routing_util.encodeFermataKey(*PASSAGGIO_PATH[:2])
                                if input == fermata_key_partenza:
                                    msg = "❗ Hai scelto lo stesso punto di partenza!".format(input)
                                    send_message(p, msg)
                                    repeatState(p)
                                    return
                            zona, stop = routing_util.decodeFermataKey(input)
                            if zona and stop:
                                PASSAGGIO_PATH.append(zona)
                                PASSAGGIO_PATH.append(stop)
                            else:
                                tellInputNonValidoUsareBottoni(p, kb)
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
                tellInputNonValidoUsareBottoni(p, kb)

# ================================
# GO TO STATE 11: Offri passaggio
# ================================
def goToState11(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    PASSAGGIO_PATH = PASSAGGIO_INFO['path']
    if giveInstruction:
        percorso_key = routing_util.encodePercorsoFromQuartet(*PASSAGGIO_PATH)
        msg = "🛣 *Il tuo percorso*:\n{}\n\n".format(percorso_key)
        msg += "📆⌚ *Quando parti?*\n\n" \
               "Premi *{}* se parti ora, " \
               "*{}* se parti oggi, " \
               "*{}* nei prossimi giorni o " \
               "*{}* se vuoi programmare un viaggio regolare " \
               "(ad esempio ogni lunedì alle 8:00).".format(BOTTONE_ADESSO, BOTTONE_OGGI,
                                                            BOTTONE_PROX_GIORNI, BOTTONE_PERIODICO)
        kb = [[BOTTONE_ANNULLA], [BOTTONE_ADESSO, BOTTONE_OGGI], [BOTTONE_PROX_GIORNI, BOTTONE_PERIODICO]]
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_ANNULLA:
                restart(p)
                return
            PASSAGGIO_INFO['mode'] = input
            if input == BOTTONE_ADESSO:
                dt = dtu.nowCET()
                sendWaitingAction(p)
                finalizeOffer(p, PASSAGGIO_PATH, dt, time_mode=input)
                restart(p)
            elif input == BOTTONE_OGGI:
                redirectToState(p, 111)
            elif input == BOTTONE_PROX_GIORNI:
                redirectToState(p, 112)
            else:
                assert input == BOTTONE_PERIODICO
                redirectToState(p, 113)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

# ================================
# GO TO STATE 111: Offri passaggio OGGI
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
            if current_min > params.MIN_TO_SWITCH_TO_NEXT_HOUR:
                current_hour += 1
            if current_hour==24:
                hour_range = [0] # if it's > 23.52 allow to choose tomorrow (but only 00 for hours)
            else:
                hour_range = range(current_hour, 24)
            hours = [str(x).zfill(2) for x in hour_range]
            kb = utility.distributeElementMaxSize(hours, 8)
        else:
            msg = '⌚ *A che minuto parti?*'
            startNowMinutes = current_hour == PASSAGGIO_TIME[0]
            if startNowMinutes:
                current_min_approx = utility.roundup(dtu.nowCET().minute + 2, 5)
                min_range = range(current_min_approx, 60, 5)
                minutes = [str(x).zfill(2) for x in min_range]
            else:
                minutes = [str(x).zfill(2) for x in range(0, 60, 5)]
            kb = utility.distributeElementMaxSize(minutes, 6)
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        if input == BOTTONE_ANNULLA:
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
                sendWaitingAction(p)
                finalizeOffer(p, PASSAGGIO_PATH, dt, time_mode=time_mode)
                restart(p)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

# ================================
# GO TO STATE 112: Offri passaggio nei prossimi giorni
# ================================

def goToState112(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    TIME_HH_MM = PASSAGGIO_INFO['time']
    STAGE = PASSAGGIO_INFO['stage']
    giveInstruction = input is None
    if giveInstruction:
        if STAGE == 0:
            msg = '*In che giorno effettui il viaggio?*'
            tomorrow = dtu.getWeekday()+1 % 7
            giorni_sett_da_domani = params.GIORNI_SETTIMANA[tomorrow:] + params.GIORNI_SETTIMANA[:tomorrow]
            giorni_sett_da_dopodomani = giorni_sett_da_domani[1:]
            kb = [['DOMANI'], giorni_sett_da_dopodomani]
        elif STAGE == 1:
            msg = '*A che ora parti?*'
            circular_range = list(range(params.DAY_START_HOUR, 24)) + list(range(0, params.DAY_START_HOUR))
            hours = [str(x).zfill(2) for x in circular_range]
            kb = utility.distributeElementMaxSize(hours, 8)
        else:  # STAGE == 2
            msg = '*A che minuto parti?*'
            minutes = [str(x).zfill(2) for x in range(0, 60, 5)]
            kb = utility.distributeElementMaxSize(minutes, 6)
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        if input == BOTTONE_ANNULLA:
            restart(p)
            return
        kb = p.getLastKeyboard()
        flat_kb = utility.flatten(kb)
        if input in flat_kb:
            if STAGE == 0:  # DAYS
                PASSAGGIO_INFO['stage'] += 1
                tomorrow = dtu.getWeekday() + 1 % 7
                chosen_day_index = (flat_kb.index(input) - 1 + tomorrow) % 7  # -1 because of BOTTONE_ANNULLA
                PASSAGGIO_INFO['days'] = [chosen_day_index]
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
                chosen_day_index = PASSAGGIO_INFO['days'][0]
                today_index = dtu.getWeekday()
                days_delta =  chosen_day_index - today_index if chosen_day_index>today_index else chosen_day_index + 7 - today_index
                dt = dtu.get_datetime_add_days(days_delta, dt)
                sendWaitingAction(p)
                finalizeOffer(p, PASSAGGIO_PATH, dt, time_mode=time_mode,
                              programmato=False, giorni=PASSAGGIO_INFO['days'])
                restart(p)
        else:
            tellInputNonValidoUsareBottoni(p, kb)


# ================================
# GO TO STATE 113: Offri passaggio periodico
# ================================

def goToState113(p, **kwargs):
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
            circular_range = list(range(params.DAY_START_HOUR, 24)) + list(range(0, params.DAY_START_HOUR))
            hours = [str(x).zfill(2) for x in circular_range]
            kb = utility.distributeElementMaxSize(hours, 8)
        else:  # STAGE == 2
            msg = '*A che minuto parti?*'
            minutes = [str(x).zfill(2) for x in range(0, 60, 5)]
            kb = utility.distributeElementMaxSize(minutes, 6)
        kb.insert(0, [BOTTONE_ANNULLA])
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        if input == BOTTONE_ANNULLA:
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
                sendWaitingAction(p)
                finalizeOffer(p, PASSAGGIO_PATH, dt, time_mode = time_mode,
                              programmato=True, giorni=DAYS)
                restart(p)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

# FOR OFFERS
def finalizeOffer(p, path, date_time, time_mode, programmato=False, giorni=()):
    from main_exception import deferredSafeHandleException
    date_time = dtu.removeTimezone(date_time)
    percorso = routing_util.encodePercorsoFromQuartet(*path)
    o = ride_offer.addRideOffer(p, date_time, percorso, time_mode, programmato, giorni)
    r = route.getRouteAddIfNotPresent(percorso)
    ride_description_no_driver_info = o.getDescription(driver_info=False)
    msg = "Grazie per aver inserito l'offerta di passaggio\n\n{}".format(ride_description_no_driver_info)
    if p.isTester():
        msg += '\n\n👷 Sei un tester del sistema, info di controllo in arrivo...'
    send_message(p, msg)
    deferredSafeHandleException(broadCastOffer, p, o, r)

def broadCastOffer(p, o, r):
    if not r.hasDetails():
        r.populateWithDetails() # may take few seconds (put=true)
    qry = person.getPeopleMatchingRideQry(r.percorsi_passeggeri_compatibili)
    if p.isTester():
        debug_msg = '👷 *Info di controllo:*\n{}'.format(r.getDetails())
        send_message(p, debug_msg)
        logging.debug(debug_msg)
    msg_broadcast = '🚘 *Nuova offerta di passaggio*:\n\n{}'.format(o.getDescription())
    blackList_sender = not p.isTester()
    broadcast(p, msg_broadcast, qry, restart_user=False, blackList_sender=blackList_sender,
              sendNotification=False, notificationWarning=True)


# FOR SEARCHES
def showMatchedPercorsi(p, PASSAGGIO_INFO):
    import pickle
    PASSAGGIO_PATH = PASSAGGIO_INFO['path']
    percorso = routing_util.encodePercorsoFromQuartet(*PASSAGGIO_PATH)
    sendWaitingAction(p)
    offers_per_day = ride_offer.getActiveRideOffersSortedPerDay(percorso)
    logging.debug('Offers per day: {}'.format(offers_per_day))
    PASSAGGIO_INFO['search_results_per_day_pkl_dumps'] = pickle.dumps(offers_per_day)
    percorsi_num = sum([len(l) for l in offers_per_day])
    msg = "🛣 *Il tuo percorso*:\n{}\n\n".format(percorso)
    if percorsi_num == 1:
        # if only one skip choosing day
        chosen_day_index = [i for i,x in enumerate(offers_per_day) if len(x)==1][0]
        PASSAGGIO_INFO['search_chosen_day'] = chosen_day_index
        msg += "🚘 *{} passaggio trovato nei prossimi 7 giorni*".format(percorsi_num)
        send_message(p, msg)
        sendWaitingAction(p, sleep_time=1)
        redirectToState(p, 14, firstCall=True)
    elif percorsi_num > 0:
        msg += "🚘 *{} passaggi trovati nei prossimi 7 giorni*".format(percorsi_num)
        send_message(p, msg)
        redirectToState(p, 13)
    else:
        msg += "🙊 *Nessun passaggio trovato*"
        send_message(p, msg)
        sendWaitingAction(p, sleep_time=1)
        restart(p)

# ================================
# GO TO STATE 13: Cerca Passaggio - Quando
# ================================

def goToState13(p, **kwargs):
    import pickle
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    PASSAGGIO_INFO = p.getTmpPassaggioInfo()
    giveInstruction = input is None
    if giveInstruction:
        msg = '📆 *Quando vuoi partire?*'
        offers_per_day = pickle.loads(PASSAGGIO_INFO['search_results_per_day_pkl_dumps'])
        today = dtu.getWeekday()
        giorni_sett_oggi_domani = params.GIORNI_SETTIMANA[today:] + params.GIORNI_SETTIMANA[:today]
        giorni_sett_oggi_domani[:2] = ['OGGI', 'DOMANI']
        offer_days_count = [len(x) for x in offers_per_day]
        offer_days_count_oggi_domani = offer_days_count[today:] + offer_days_count[:today]
        offer_giorni_sett_count_oggi_domani = ['{} ({})'.format(d, c) for d,c in zip(giorni_sett_oggi_domani, offer_days_count_oggi_domani)]
        kb = [[BOTTONE_ANNULLA], offer_giorni_sett_count_oggi_domani[:2], offer_giorni_sett_count_oggi_domani[2:]]
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
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
                send_message(p, msg, kb)
            else:
                today = dtu.getWeekday()
                chosen_day_index = (flat_kb.index(input) - 1 + today) % 7  # -1 because of BOTTONE_ANNULLA
                PASSAGGIO_INFO['search_chosen_day'] = chosen_day_index
                sendWaitingAction(p, sleep_time=1)
                redirectToState(p, 14, firstCall=True)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

# ================================
# GO TO STATE 14: Cerca Passaggio - Risultati
# ================================

def goToState14(p, **kwargs):
    import pickle
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        PASSAGGIO_INFO = p.getTmpPassaggioInfo()
        logging.debug('passaggio info: {}'.format(PASSAGGIO_INFO))
        chosen_day = PASSAGGIO_INFO['search_chosen_day']
        offers_per_day = pickle.loads(PASSAGGIO_INFO['search_results_per_day_pkl_dumps'])
        offers_chosen_day = offers_per_day[chosen_day]
        firstCall = kwargs['firstCall'] if 'firstCall' in kwargs.keys() else False
        if firstCall:
            cursor = [0, len(offers_chosen_day)]
            p.setTmpVariable(person.VAR_CURSOR, cursor)
        else:
            cursor = p.getTmpVariable(person.VAR_CURSOR)
        logging.debug('cursor: {}'.format(cursor))
        offer = offers_chosen_day[cursor[0]]
        msg = "🚘 Passaggio {}/{}\n\n{}".format(cursor[0]+1, cursor[1], offer.getDescription())
        #single_offer = len(offers_chosen_day) == 1
        kb = [[BOTTONE_INIZIO]]
        if len(offers_chosen_day)>1:
            kb.append([PREV_ICON, NEXT_ICON])
        kb.append([BOTTONE_INDIETRO])
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
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
            tellInputNonValidoUsareBottoni(p, kb)


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
        send_message(p, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INDIETRO:
                restart(p)
            elif input == BOTTONE_PERCORSI:
                redirectToState(p, 31)
            elif input == BOTTONE_NOTIFICHE:
                redirectToState(p, 32)
            else:
                assert input == BOTTONE_ELIMINA_OFFERTE
                redirectToState(p, 33, firstCall=True)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

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
        send_message(p, msg, kb)
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
                    send_message(p, msg, kb)
                    sendWaitingAction(p, sleep_time=1)
                    redirectToState(p, 31)
                else:
                    redirectToState(p, 1, firstCall=True, passaggio_type='aggiungi_preferiti')
            else:
                assert input == BOTTONE_RIMUOVI_PERCORSO
                redirectToState(p, 312)
        else:
            tellInputNonValidoUsareBottoni(p, kb)


# ================================
# Aggiungi in Preferiti - from 1
# ================================

def aggiungiInPreferiti(p, PASSAGGIO_PATH):
    percorso = routing_util.encodePercorsoFromQuartet(*PASSAGGIO_PATH)
    if p.appendPercorsi(percorso):
        msg = '🛣 *Hai aggiunto il percorso*:\n{}'.format(percorso)
        send_message(p, msg)
        sendWaitingAction(p, sleep_time=1)
        REVERSE_PATH = routing_util.getReversePath(*PASSAGGIO_PATH)
        percorso = routing_util.encodePercorsoFromQuartet(*REVERSE_PATH)
        if p.getPercorsiSize() < params.MAX_PERCORSI and not p.percorsoIsPresent(percorso):
            redirectToState(p, 311, reverse_path=REVERSE_PATH)
        else:
            redirectToState(p, 31)
    else:
        msg = '🤦‍♂️ *Percorso già inserito*:\n{}'.format(percorso)
        send_message(p, msg)
        sendWaitingAction(p, sleep_time=1)
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
        percorso = routing_util.encodePercorsoFromQuartet(*REVERSE_PATH)
        PASSAGGIO_INFO['percorso'] = percorso
        msg = "↩️ *Vuoi anche inserire il passaggio inverso?*\n{}".format(percorso)
        kb = [[BOTTONE_SI, BOTTONE_NO]]
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_SI:
                percorso = PASSAGGIO_INFO['percorso']
                inserted = p.appendPercorsi(percorso)
                assert(inserted)
                msg = '🛣 *Hai aggiunto il percorso*:\n{}'.format(percorso)
                send_message(p, msg)
                sendWaitingAction(p, sleep_time=1)
            redirectToState(p, 31)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

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
        send_message(p, msg, kb)
    else:
        kb = p.getLastKeyboard()
        if input in utility.flatten(kb):
            if input == BOTTONE_INDIETRO:
                redirectToState(p, 31)
            else:
                n = int(input)
                percorso = p.removePercorsi(n - 1)
                msg = '*Percorso cancellato*:\n{}'.format(percorso)
                send_message(p, msg)
                if p.getPercorsiSize()>0:
                    repeatState(p)
                else:
                    redirectToState(p, 31)
        else:
            tellInputNonValidoUsareBottoni(p, kb)


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
        send_message(p, msg, kb)
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
            tellInputNonValidoUsareBottoni(p, kb)

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
            logging.debug('State 33: attempting to access offer with cursor {}'.format(cursor))
            offer = my_offers[cursor[0]] # IndexError: list index out of range
            msg = "Passaggio {}/{}\n\n{}".format(cursor[0] + 1, cursor[1], offer.getDescription())
            kb = [[BOTTONE_ELIMINA], [BOTTONE_INDIETRO]]
            if len(my_offers) > 1:
                kb.insert(0, [PREV_ICON, NEXT_ICON])
        else:
            msg = "Hai eliminato tutte le offerte"
            send_message(p, msg)
            sendWaitingAction(p, sleep_time=1)
            redirectToState(p, 3)
            return
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
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
            else:
                assert input==BOTTONE_ELIMINA
                p.deleteMyOfferAtCursor()
                repeatState(p, put=True)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

# ================================
# GO TO STATE 8: SpeechTest
# ================================

def goToState8(p, **kwargs):
    import speech
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    kb = [[BOTTONE_INIZIO]]
    if giveInstruction:
        msg = 'Prova a dire qualcosa...'
        send_message(p, msg, kb)
    else:
        voice = kwargs['voice'] if 'voice' in kwargs.keys() else None
        if input == BOTTONE_INIZIO:
            restart(p)
        elif voice:
            # telegram
            file_id = voice['file_id']
            duration = int(voice['duration'])
            if duration > 5:
                text = 'Audio troppo lungo.'
            else:
                text = speech.getTranscriptionTelegram(file_id, choices = ())
            send_message(p, text)
        else:
            tellInputNonValidoUsareBottoni(p, kb)


# ================================
# GO TO STATE 9: Info
# ================================

def goToState9(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    kb = [[BOTTONE_INIZIO], [BOTTONE_REGOLAMENTO_ISTRUZIONI], [BOTTONE_FERMATE], [BOTTONE_CONTATTACI, BOTTONE_STATS]]
    if giveInstruction:
        msg_lines = ['*Informazioni*']
        msg_lines.append('*∇Polo* è un servizio di carpooling attualmente in sperimentazione, sviluppato a partire da PickMeUp.')
        msg_lines.append('Clicca su {} o uno dei pulsanti qua sotto per avere maggiori informazioni.'.format(BOTTONE_REGOLAMENTO_ISTRUZIONI))
        msg = '\n\n'.join(msg_lines)
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        if input == BOTTONE_INIZIO:
            restart(p)
        elif input == BOTTONE_REGOLAMENTO_ISTRUZIONI:
#            msg = 'https://docs.google.com/document/d/1hiP_rQKOiiPZwvqtZF3k0cGdqS1SZqs3VV7TIx9_s8o'
            msg = "Work In Progress!"
            send_message(p, msg, kb, markdown=False, disable_web_page_preview=False)
        elif input == BOTTONE_FERMATE:
            redirectToState(p, 91)
        elif input == BOTTONE_STATS:
            msg = utility.unindent(
                '''
                👤 Utenti: {}
                
                🚘 Passaggi disponibili nei prossimi 7 giorni: {}
                📆🚘 Offerte inserite negli ultimi 7 giorni: {}                                
                '''
            ).format(
                person.getPeopleCount(),
                ride_offer.getActiveRideOffersCountInWeek(),
                ride_offer.getRideOfferInsertedLastDaysQry(7).count()
            )
            send_message(p, msg)
        elif input == BOTTONE_CONTATTACI:
            redirectToState(p, 92)
        else:
            tellInputNonValidoUsareBottoni(p, kb)


# ================================
# GO TO STATE 91: Info Fermate
# ================================

def goToState91(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    location = kwargs['location'] if 'location' in kwargs else None
    giveInstruction = input is None
    kb = [[BOTTONE_MAPPA], [BOTTONE_INDIETRO]] #[BOTTONE_LOCATION], # NOT WORKING FOR DESKTOP
    if giveInstruction:
        msg = '∙ 🗺📌 Mandami una *posizione GPS* (tramite la graffetta in basso), oppure\n' \
              '∙ ✏️🏷 scrivi un *indirizzo* (ad esempio "via rosmini trento"), oppure\n' \
              '∙ clicca su {}'.format(BOTTONE_MAPPA) #📎
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        if input == BOTTONE_INDIETRO:
            redirectToState(p, 9)
            return
        if input == BOTTONE_MAPPA:
            with open('data/full_map.jpg') as file_data:
                send_photo_png_data(p, file_data, 'full_map')
            sendWaitingAction(p, sleep_time=1)
            repeatState(p)
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
            img_url, text = routing_util.getFermateNearPositionImgUrl(location['latitude'], location['longitude'])
            #logging.debug('img_url: {}'.format(img_url))
            if img_url:
                send_photo_url(p, img_url)
            send_message(p, text)
            sendWaitingAction(p, sleep_time=1)
            repeatState(p)
        else:
            tellInputNonValidoUsareBottoni(p, kb)

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
              '∙ 🗣 Entrare in chat con noi cliccando su @zolfariot\n' \
              '∙ 📬 Mandaci un email a collettivodiscienze@googlegroups.com'
        p.setLastKeyboard(kb)
        send_message(p, msg, kb)
    else:
        if input == BOTTONE_INDIETRO:
            redirectToState(p, 9)
        else:
            msg_admin = '📩📩📩\nMessaggio di feedback da {}:\n{}'.format(p.getFirstNameLastNameUserName(), input)
            tell_admin(msg_admin)
            msg = 'Grazie per il tuo messaggio, ti contatteremo il prima possibile.'
            send_message(p, msg)
            redirectToState(p, 9)


## +++++ END OF STATES +++++ ###

def dealWithUserInteraction(chat_id, name, last_name, username, application, text,
                            location, contact, photo, document, voice):

    p = person.getPersonByChatIdAndApplication(chat_id, application)
    name_safe = ' {}'.format(name) if name else ''

    if p is None:
        p = person.addPerson(chat_id, name, last_name, username, application)
        msg = " 😀 Ciao{},\nbenvenut+ In ∇Polo!\n" \
              "Se hai qualche domanda o suggerimento non esitare " \
              "a contattarci cliccando su @zolfariot".format(name_safe)
        send_message(p, msg)
        restart(p)
        tellMaster("New {} user: {}".format(application, p.getFirstNameLastNameUserName()))
    else:
        # known user
        modified, was_disabled = p.updateUserInfo(name, last_name, username)
        if WORK_IN_PROGRESS and p.getId() not in key.TESTER_IDS:
            send_message(p, "🏗 Il sistema è in aggiornamento, ti preghiamo di riprovare più tardi.")
        elif was_disabled or text in ['/start', 'start', 'START', 'INIZIO']:
            msg = " 😀 Ciao{}!\nBentornat+ in ∇Polo!".format(name_safe)
            send_message(p, msg)
            restart(p)
        elif text == '/state':
            msg = "You are in state {}: {}".format(p.state, STATES.get(p.state, '(unknown)'))
            send_message(p, msg)
        elif text in ['/settings', 'IMPOSTAZIONI']:
            redirectToState(p, SETTINGS_STATE)
        elif text in ['/help', 'HELP', 'AIUTO']:
            redirectToState(p, HELP_STATE)
        elif text in ['/stop', 'STOP']:
            p.setEnabled(False, put=True)
            msg = "🚫 Hai *disabilitato* ∇Polo.\n" \
                  "In qualsiasi momento puoi riattivarmi scrivendomi qualcosa."
            send_message(p, msg)
        else:
            if not dealWithUniversalCommands(p, input=text):
                logging.debug("Sending {} to state {} with input {}".format(p.getFirstName(), p.state, text))
                repeatState(p, input=text, location=location, contact=contact, photo=photo, document=document,
                            voice=voice)

app = webapp2.WSGIApplication([
    ('/telegram_me', main_telegram.MeHandler),
    ('/telegram_set_webhook', main_telegram.SetWebhookHandler),
    ('/telegram_get_webhook_info', main_telegram.GetWebhookInfo),
    ('/telegram_delete_webhook', main_telegram.DeleteWebhook),
#    (key.FACEBOOK_WEBHOOK_PATH, main_fb.WebhookHandler),
    (key.TELEGRAM_WEBHOOK_PATH, main_telegram.WebhookHandler),
], debug=True)

possibles = globals().copy()
possibles.update(locals())
