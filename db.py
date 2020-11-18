# from datetime import date
# import datetime
from datetime import datetime, timedelta
from peewee import *
import random

# this will create/refer-to spot.db file in cwd
db = SqliteDatabase('spot.db')


# model is a table
class Message(Model):
    created = DateTimeField(default=datetime.now)
    source = CharField()
    text = CharField()
    sent = DateTimeField()
    body = CharField()

    class Meta:
        database = db  # This model uses the "spot.db" database.


class Instance(Model):
    name = CharField()
    iid = CharField(default="")
    public_ip = CharField(default="")
    private_ip = CharField(default="")
    ns_record = CharField()
    test_url = CharField(default="")
    modified = DateField(default=datetime.now().date())
    state = CharField(default="")

    class Meta:
        database = db  # This model uses the "spot.db" database.


# create init db record for lms-chen
def inject_record():
    lms_chen = {
        "name": "lms-chen",
        "iid": "i-0763b2c8743f823ef",
        "public_ip": "1.1.1.1",
        "private_ip": "10.10.10.10",
        "ns_record": "lms-chen.lms.lumosglobal.com",
        "test_url": "https://lms-chen.lms.lumosglobal.com:1883/lms/v1/system/status",
        "state": "init"
    }
    instance = Instance.create(name=lms_chen["name"],
                               iid=lms_chen["iid"],
                               public_ip=lms_chen["public_ip"],
                               private_ip=lms_chen["private_ip"],
                               ns_record=lms_chen["ns_record"],
                               test_url=lms_chen["test_url"],
                               state=lms_chen["state"])
    instance.save()


def recreate_db():
    """Recreating db from scratch

        use this ONLY for recreate db from scratch.
        it will inject records from OLD__db-init file
    """

    print("will reinit db - FAKE")
    db.create_tables([Message, Instance])
    inject_record()


def init(recreate=False):
    db.connect()
    if recreate:
        recreate_db()


# init db if this script invoked manually
if __name__ == '__main__':
    """Initializing local Sqlite DB.
        This file SHOULD NOT run directly, only in case DB should be re-init.
       """
    print("initializing dataset")
    init(recreate=False)
