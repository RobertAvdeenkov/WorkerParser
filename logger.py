import json
import logging

class JSONFormater(logging.Formatter):
    def format(self,record):
        return json.dumps({
            'time':self.formatTime(record),
            'level':record.levelname,
            'message':record.getMessage()
        })

logger= logging.getLogger('app')
handler= logging.StreamHandler()
handler.setFormatter(JSONFormater())
logger.addHandler(handler)
logger.setLevel(logging.INFO)