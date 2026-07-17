import psutil
import os
import sqlite3
import time
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DBPATH
from config import compilers  # yet not written in the config files- > will update soon
from config import browsers   # yet not written in the config files- > will update soon
from config import IDEs       # yet not written in the config files- > will update soon