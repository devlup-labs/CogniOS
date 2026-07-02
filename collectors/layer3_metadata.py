"""Layer 3 metadata telemetry collection."""
import sqlite3
from datetime import datetime
import psutil 
from CogniOS.utils.config import DB_PATH 
db_path = DB_PATH

class MetadataCollector:

    def __init__(self, db_path):

        self.conn = sqlite3.connect(db_path, check_same_thread = False)
        self.cursor = self.conn.cursor()

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_metadata(
            pid INTEGER,
            ppid INTEGER,
            process_name TEXT,
            create_time TEXT,
            exe_path TEXT,
            cmdline TEXT,
            username TEXT,
            nice_priority INTEGER,
            first_seen TEXT,
            PRIMARY KEY(pid, create_time)
        )
        """)

        self.conn.commit()
    def metadata_exists(self, pid, create_time):
        self.cursor.execute("SELECT 1 FROM process_metadata WHERE pid=? AND create_time=?", (pid, create_time)) 
        return self.cursor.fetchone() is not None

    def save_metadata(self, pid):

        try:
            p = psutil.Process(pid)

            create_time = datetime.fromtimestamp(
               p.create_time()
            ).isoformat()

            if self.metadata_exists(pid, create_time):
             return

            record = ( 

                p.pid,  #pid
                p.ppid(),  
                p.name(),

               create_time,
                p.exe(),   #to track the executable path 
                " ".join(p.cmdline()),  #to track the command line arguments
                p.username(),
                p.nice(),
                datetime.now().isoformat()  #to track when we first saw this process
            )

            self.cursor.execute("""
            INSERT INTO process_metadata
            VALUES(?,?,?,?,?,?,?,?,?)
            """, record)
            print(
    f"[LAYER3] Metadata stored for PID {pid}"
)

        except (
              psutil.NoSuchProcess,
    psutil.AccessDenied,
    psutil.ZombieProcess
         ) as e:
         print(f"[LAYER3 ERROR] {e}")
    
    def commit(self):
        self.conn.commit()

    def cleanup(self, days=7): #delete record older than 7 days

        self.cursor.execute("""
            DELETE FROM process_metadata
            WHERE julianday('now')-julianday(first_seen)> ?
            """,
            (days,)
        )

        self.conn.commit()

    def close(self):      #
            self.conn.close()



def process_top_processes(collector, top_cpu, top_mem):  

   
    top_pids = set()
    for proc in top_cpu:       #this will ensure that we only save metadata for unique PIDs, even if they appear in both top CPU and top memory lists
        top_pids.add(proc["pid"])
    for proc in top_mem:
        top_pids.add(proc["pid"])
    for pid in top_pids:
        collector.save_metadata(pid)

    collector.commit()
    collector.cleanup()
