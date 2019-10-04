import json
import jsonlogging
import logging


def lambda_handler(event, context):
    jsonlogging.configure_logging(context, tags={'argle': 'bargle'})
    logging.info("key 1 = " + event.get('key1'))
    return None
