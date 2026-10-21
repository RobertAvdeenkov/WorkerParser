import json
import logging
from datetime import datetime

class JSONFormater(logging.Formatter):
    def format(self,record):
        json_data={
            'time':datetime.fromtimestamp(record.created).isoformat(),
            'level':record.levelname,
            'message':record.getMessage()
        }
        if record.exc_info: 
            json_data['exception']=self.formatException(record.exc_info)
        return json.dumps(json_data, ensure_ascii=True)

def setup_logger():
    logger= logging.getLogger('app')
    logger.setLevel(logging.INFO)

    handler= logging.StreamHandler()
    handler.setFormatter(JSONFormater())
    logger.addHandler(handler)

    return logger

logger=setup_logger()