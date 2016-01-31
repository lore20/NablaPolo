# -*- coding: utf-8 -*-

from google.appengine.ext import ndb

TURK_MODE = 'TurkOn'

class BooleanVariable(ndb.Model):
    value = ndb.BooleanProperty()

def setVarValue(key, value):
    entry = BooleanVariable.get_or_insert(key)
    entry.value = value
    entry.put()

def getVarValue(key):
    entry = ndb.Key(BooleanVariable, key).get()
    return entry.value

def turkMode():
    return getVarValue(TURK_MODE)

def enableTurkMode():
    setVarValue(TURK_MODE, True)

def disableTurkMode():
    setVarValue(TURK_MODE, False)