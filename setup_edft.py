import py2exe
import sqlite3
import EliteDangerousFleetTracker
from EliteDangerousFleetTracker import EliteDangerousFleetTracker
from edft_shared_constants import LOCAL_DB_PATH
import logging
from logging import handlers
import threading
import time
import os
import webbrowser
from Account import TokenRequestType
from Account import Account
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
from enum import Enum
import secrets
import requests
import hashlib
import base64
import json
from edft_secrets import CLIENT_ID, FERNET_KEY
from cryptography.fernet import Fernet
from edft_shared_constants import API_QUERY_INTERVAL
import cffi

py2exe.freeze(
    options={
        "py2exe": {
            "packages": ["cryptography", "cffi"],
        }
    },
    windows=[{"script": "EDFT.py", "icon_resources": [(1, "edft.ico")]}],
)
