from apscheduler.schedulers.background import BackgroundScheduler
from .jobs import scheduled_call_job

def start():
    scheduler = BackgroundScheduler()

    scheduler.add_job(scheduled_call_job, 'interval', minutes=1, max_instances=1, id='lead-batch-job')


    scheduler.start()


import logging
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)
