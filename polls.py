from google.appengine.ext import ndb
from datetime import datetime

class PollAnswer(ndb.Model):
    poll_title = ndb.StringProperty()
    user_id = ndb.IntegerProperty()
    user_name = ndb.StringProperty()
    user_lastname = ndb.StringProperty()
    submission_datetime = ndb.DateTimeProperty()
    answer = ndb.StringProperty()

def submittPollAnswer(id, name, lastname, title, answer):
    item = PollAnswer.get_or_insert(str(id))
    item.poll_title = title
    item.user_id = id
    item.user_name = name
    item.user_lastname = lastname
    item.submission_datetime = datetime.now()
    item.answer = answer
    item.put()
