import logging
from logging import handlers
import os
import sqlite3
import sys
from urllib.parse import parse_qs
from edft_shared_constants import LOCAL_DB_PATH
import py2exe

py2exe.freeze(windows=["helper.py"])
