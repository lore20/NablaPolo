
from google.appengine.ext import ndb
from datetime import datetime
from google.appengine.api import channel

TOKEN_DURATION_MIN = 100
TOKEN_DURATION_SEC = TOKEN_DURATION_MIN*60

class Token(ndb.Model):
    token_id = ndb.StringProperty()
    start_daytime = ndb.DateTimeProperty()

def createToken():
    now = datetime.now()
    token_id = channel.create_channel(str(now), duration_minutes=TOKEN_DURATION_MIN)
    token = Token.get_or_insert(token_id)
    token.start_daytime = now
    token.token_id = token_id
    token.put()
    return token_id