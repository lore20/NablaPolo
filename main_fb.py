# -*- coding: utf-8 -*-

from google.appengine.api import urlfetch

import jsonUtil
import logging
import key
import webapp2

import requests
import json

json_headers = {'Content-type': 'application/json'}

def setFB_Menu():
    setMenu(['HELP','START'])

def setMenu(menu_items):
    response_data = {
        #"recipient": {"id": sender_id},
        "setting_type": "call_to_actions",
        "thread_state": "existing_thread",
        "call_to_actions": [
            {
                "type": "postback",
                "title": i,
                "payload": i
            }
            for i in menu_items
        ]
    }
    response_data_str = json.dumps(response_data)

    try:
        logging.info('sending menu with json: {}'.format(response_data))
        resp = requests.post(key.FACEBOOK_TRD_API_URL, data=response_data_str, headers=json_headers)
        logging.info('responding to request: {}'.format(resp.text))
        return resp.status_code == 200
    except:
        report_exception()

def sendMessage(sender_id, msg):
    response_data = {
        "recipient": {
            "id": sender_id
        },
        "message": {
            "text": msg,
        }
    }
    response_data_str = json.dumps(response_data)
    try:
        logging.info('responding to request with message: {}'.format(response_data))
        resp = requests.post(key.FACEBOOK_MSG_API_URL, data=response_data_str, headers=json_headers)
        logging.info('responding to request: {}'.format(resp.text))
        return resp.status_code == 200
    except:
        report_exception()

# max 11 reply_items
def sendMessageWithQuickReplies(sender_id, msg, reply_items):
    response_data = {
        "recipient": {
            "id": sender_id
        },
        "message": {
            "text": msg,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": i,
                    "payload": i
                }
                for i in reply_items
            ]
        }
    }
    response_data_str = json.dumps(response_data)
    try:
        logging.info('responding to request with message with quick replies: {}'.format(response_data))
        resp = requests.post(key.FACEBOOK_MSG_API_URL, data=response_data_str, headers=json_headers)
        logging.info('responding to request: {}'.format(resp.text))
        return resp.status_code == 200
    except:
        report_exception()

# max 3 button_items
def sendMessageWithButtons(sender_id, msg, button_items):
    response_data = {
        "recipient": {
            "id": sender_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": msg,
                    "buttons": [
                        {
                            "type": "postback",
                            "title": i,
                            "payload": i
                        }
                        for i in button_items
                    ]
                }
            }
        }
    }
    response_data_str = json.dumps(response_data)
    try:
        logging.info('responding to request with message with buttons: {}'.format(response_data))
        resp = requests.post(key.FACEBOOK_MSG_API_URL, data=response_data_str, headers=json_headers)
        logging.info('responding to request: {}'.format(resp.text))
        return resp.status_code == 200
    except:
        report_exception()

def sendPhotoUrl(sender_id, url):
    response_data = {
        "recipient": {
            "id": sender_id
        },
        "message": {
            "attachment": {
                "type": "file",
                "payload": {
                    "url": url
                }
            }
        }
    }
    response_data_str = json.dumps(response_data)
    try:
        logging.info('responding to request with image via url: {}'.format(response_data))
        resp = requests.post(key.FACEBOOK_MSG_API_URL, data=response_data_str, headers=json_headers)
        logging.info('responding to request: {}'.format(resp.text))
        return resp.status_code == 200
    except:
        report_exception()

def sendPhotoData(sender_id, file_data, filename):
    response_data = {
        "recipient": json.dumps(
            {
            "id": sender_id
            }
        ),
        "message": json.dumps(
            {
                "attachment": {
                    "type": "image",
                    "payload": {}
                }
            }
        )
    }

    files = {
        "filedata": (filename, file_data, 'image/png')
    }

    try:
        logging.info('sending photo data: {}'.format(response_data))
        resp = requests.post(key.FACEBOOK_MSG_API_URL, data=response_data, files=files)
        logging.info('responding to photo request: {}'.format(resp.text))
        return resp.status_code == 200
    except:
        report_exception()


def getUserInfo(user_id):
    url = 'https://graph.facebook.com/v2.6/{}?fields=first_name,last_name,profile_pic,locale,timezone,gender&access_token={}'.format(user_id, key.FACEBOOK_PAGE_ACCESS_TOKEN)
    logging.debug('Sending user info request: {}'.format(url))
    r = requests.get(url)
    json = r.json()
    first_name = json.get('first_name', None)
    last_name = json.get('last_name', None)
    logging.debug('Getting first name = {} and last name = {}'.format(first_name, last_name))
    return first_name, last_name

class WebhookHandler(webapp2.RequestHandler):

    # to confirm the webhook url
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        challange = self.request.get('hub.challenge')
        self.response.write(challange)

    # to handle user interaction
    def post(self):
        from main import dealWithUserInteraction
        urlfetch.set_default_fetch_deadline(60)
        body = jsonUtil.json_loads_byteified(self.request.body)
        logging.info('request body: {}'.format(body))
        messaging = body['entry'][0]['messaging'][0]
        chat_id = messaging['sender']['id']
        text = messaging.get('message', {}).get('text', '')
        if text=='':
            text = messaging.get('postback', {}).get('payload', '')
        #attachment = messaging.get('message', {}).get('attachments', [{}])[0]
        #voice_url = attachment.get('payload',{}).get('url',None) if attachment.get('type',None)=='audio' else None
        location = messaging.get('message', {}).get('attachments', [{}])[0].get('payload', {}).get('coordinates', None)
        # {"lat": 46.0, "long": 11.1}
        if location:
            location = {'latitude': location['lat'], 'longitude': location['long'] }

        # we need this as fb is send all sort of notification when user is active without sending any message
        if text=='' and location is None:
            return

        dealWithUserInteraction(chat_id, name=None, last_name=None, username=None,
                                application='messenger', text=text,
                                location=location, contact=None, photo=None, document=None, voice=None)



def report_exception():
    from main import tell_admin
    import traceback
    msg = "❗ Detected Exception: " + traceback.format_exc()
    tell_admin(msg)
    logging.error(msg)
