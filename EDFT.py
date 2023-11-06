import sqlite3
from EliteDangerousFleetTracker import EliteDangerousFleetTracker
from edft_shared_constants import LOCAL_DB_PATH
import logging
from logging import handlers
import threading
import time
import os

if not os.path.isdir(LOCAL_DB_PATH):
    os.makedirs(LOCAL_DB_PATH)
if not os.path.isdir(LOCAL_DB_PATH + "\\logs"):
    os.makedirs(LOCAL_DB_PATH + "\\logs")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# lh = logging.StreamHandler()
lh = logging.handlers.RotatingFileHandler(
    LOCAL_DB_PATH + "\\logs\\edft.log", maxBytes=128 * 1024 * 1024, backupCount=5
)
lh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

lh.setFormatter(formatter)
logger.addHandler(lh)

API_REFRESH_INTERVAL = 60000


def capi_refresh_task(exitapp, instance) -> None:
    """
    Task that is executed by the thread dedicated to updating cAPI data. Broken into one-second chunks to hasten exit.
    :param exitapp: cheekily-mutable boolean flag that is set when GUI thread completes (user clicks quit button).
    :param instance: Reference to the instantiated EDFT main class to gain access to the accounts to update.
    """
    counter = 10000
    while exitapp[0] is False:
        if counter >= API_REFRESH_INTERVAL / 1000:
            for account in instance.account_table:
                if exitapp[0]:
                    break
                if not account.reauth_required:
                    account.update_from_capi()
            counter = 0
        counter += 1
        time.sleep(1)


with sqlite3.connect(LOCAL_DB_PATH + "\\edft.db") as conn:
    EDFT = EliteDangerousFleetTracker(conn, lh)
    logger.debug("starting up")
    cur = conn.cursor()
    res = cur.execute("SELECT name FROM sqlite_master WHERE name='accounts'")
    if res.fetchone() is None:  # i.e. first start, table doesn't exist.
        cur.execute(
            "CREATE TABLE accounts(name, state, code, challenge, verifier, access_token, refresh_token,"
            "reauth_required, reauth_prompted, cmdr_data, fc_data)"
        )
    EDFT.init_account_table()
    exitapp = [False]
    polling_thread = threading.Thread(target=capi_refresh_task, args=[exitapp, EDFT])
    polling_thread.start()
    EDFT.create_gui()
    exitapp[0] = True
    polling_thread.join()
