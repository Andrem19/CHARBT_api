from __init__ import db
from datetime import datetime
import time
from models import Logs

def add_logs(ip_address, user_id, code, description):
    timestamp = int(time.time())
    log = Logs(user_id=user_id, action_code=code, description=description, timestamp=timestamp, ip_address=ip_address)
    db.session.add(log)
    db.session.commit()
