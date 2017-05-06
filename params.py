# -*- coding: utf-8 -*-

GIORNI_SETTIMANA = ['LU', 'MA', 'ME', 'GI', 'VE', 'SA', 'DO']
GIORNI_SETTIMANA_FULL = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']

MAX_ITINERARI = 8

NOTIFICATION_MODE_NONE = "NONE"
NOTIFICATION_MODE_ALL = "ALL"
NOTIFICATION_MODE_ITINERARIES = "ITINERARIES"
DEFAULT_NOTIFICATIONS_MODE = NOTIFICATION_MODE_ALL

NOTIFICATIONS_MODES = [NOTIFICATION_MODE_ALL, NOTIFICATION_MODE_ITINERARIES, NOTIFICATION_MODE_NONE]

ITINERARI_COMMAND_PREFIX = '/itinerario_'

def getCommand(prefix, suffix, escapeMarkdown=True):
    import utility
    result = "{}{}".format(prefix, suffix)
    if escapeMarkdown:
        return utility.escapeMarkdown(result)
    return result

def getIndexFromCommand(command, prefix):
    import utility
    index = command[len(prefix):]
    if utility.representsInt(index):
        return int(index)
    return None
