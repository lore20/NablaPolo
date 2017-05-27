# -*- coding: utf-8 -*-

import googleapiclient.discovery
from oauth2client.client import GoogleCredentials
credentials = GoogleCredentials.get_application_default()

import logging
import base64
from route import ZONE, FERMATE, STOPS

#PHRASES = ZONE.keys() + FERMATE.keys() + STOPS

def getTranscription(file_id, choices):
    import requests
    import key

    r = requests.get(key.TELEGRAM_API_URL + 'getFile', params={'file_id': file_id})
    rdict = r.json()
    #logging.debug('getFile response dict: {}'.format(rdict))
    file_path = rdict['result']['file_path']
    urlFile = key.TELEGRAM_BASE_URL_FILE + file_path
    #logging.debug('url: {}'.format(urlFile))
    fileContent = requests.get(urlFile).content
    speech_content = base64.b64encode(fileContent)
    #logging.debug('speech_content: {}'.format(speech_content))

    service = googleapiclient.discovery.build('speech', 'v1', credentials=credentials)
    service_request = service.speech().recognize(
        body={
            "config": {
                "encoding": 'OGG_OPUS',  # enum(AudioEncoding)
                "sampleRateHertz": 16000,
                "languageCode": 'it-IT',
                "maxAlternatives": 1,
                "speechContexts": {
                    "phrases": choices
                }
            },
            "audio": {
                "content": speech_content
            }
        })

    r_dict = service_request.execute()
    logging.debug('speech api response: {}'.format(r_dict))

    if 'results' in r_dict:
        return r_dict['results'][0]['alternatives'][0]['transcript']
    return None


'''
msg = []
results = r_dict['results']
for result in results:
    alternatives = result['alternatives']
    for alternative in alternatives:
        transcript = alternative['transcript'] if 'transcript' in alternative else None
        confidence = alternative['confidence'] if 'confidence' in alternative else None
        if confidence:
            msg.append('transcript: {}, confidence: {}'.format(transcript, confidence))
        else:
            msg.append('transcript: {}'.format(transcript))
return '\n'.join(msg)
'''
