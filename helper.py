import logging
from logging import handlers
import os
import sqlite3
import sys
from urllib.parse import parse_qs
from edft_shared_constants import LOCAL_DB_PATH

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not os.path.isdir(LOCAL_DB_PATH):
    os.makedirs(LOCAL_DB_PATH)
if not os.path.isdir(LOCAL_DB_PATH + "\\logs"):
    os.makedirs(LOCAL_DB_PATH + "\\logs")

lh = logging.handlers.RotatingFileHandler(
    LOCAL_DB_PATH + "\\logs\\edft_helper.log", maxBytes=128 * 1024 * 1024, backupCount=5
)

lh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
lh.setFormatter(formatter)
logger.addHandler(lh)

try:
    redirect = parse_qs(sys.argv[1][17:])
    with sqlite3.connect(LOCAL_DB_PATH + "\\edft.db") as conn:
        cur = conn.cursor()
        res = cur.execute(
            "update accounts set code = ? where state = ?",
            (redirect["code"][0], redirect["state"][0]),
        )
        logger.info("Successfully processed code for state " + redirect["state"][0])
except:
    logger.exception("")
