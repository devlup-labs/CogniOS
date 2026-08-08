import os
import sys
import sqlite3
import pandas as pd
from collections import deque
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH
from config import SLIDING_WIND_N
#commenting some part of the sliding window file
#other modules will suffer because as buffer implementation will cause other modules to work on the stale 
# class SlidingWindowBuffer:
#     def __init__(self, maxlen: int = SLIDING_WIND_N):
#        # it initialises the deque with a maxlen=SLIDING_WIND_N
#         self.buffer = deque(maxlen=maxlen)

#     def add(self, snapshot: dict) -> None:
#         # this checks the deque  if full then drops the oldest adds newest
#         self.buffer.append(snapshot)

#     def is_ready(self) -> bool:
#         # keeps check if maxlen is achieved or not
#         return len(self.buffer) == self.buffer.maxlen

#     def get_window(self) -> list[dict]:
#         # Returns a copy of the current buffer as a standard Python list.
#         return list(self.buffer)
def get_window_from_db(db_path=DB_PATH, limit=SLIDING_WIND_N):
    try:
        with sqlite3.connect(db_path,timeout=10.0) as conn:
            # it will fetch last nth rows n=limit from the db
            query = f"select * from layer1_sys order by timestamp desc limit {limit}"
            df = pd.read_sql(query, conn)
            if df.empty:
                return None
            
            # Reverses the dataframe so the oldest data is first, newest is last
            df = df[::-1].reset_index(drop=True)
            return df
    except Exception as e:
        print(f"Window Extraction Error: {e}")
        return None
