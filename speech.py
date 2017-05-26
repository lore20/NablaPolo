# -*- coding: utf-8 -*-

def getTranscription(source_uri):
    from google.cloud import speech
    client = speech.Client()
    sample = client.sample(source_uri=source_uri,
                           encoding=speech.Encoding.OGG_OPUS) #sample_rate_hertz=44100
    results = sample.recognize(language_code='en-GB', max_alternatives=2)
    msg = []
    for result in results:
        for alternative in result.alternatives:
            msg.append('transcript: {}, confidence: {}'.format(
                alternative.transcript, alternative.confidence))
    return '\n'.join(msg)