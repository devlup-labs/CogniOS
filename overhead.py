import os
import time
import threading
import psutil
from test import run_osd  # Replace with your project's entry point

class ResourceProfiler:
    def __init__(self, interval=0.1):
        self.interval = interval
        self.process = psutil.Process(os.getpid())
        self.stop_signal = threading.Event()
        
        # Data tracking arrays
        self.cpu_samples = []
        self.ram_samples = []
        
    def _sample_loop(self):
        """Background sampling loop for resource spikes."""
        # Initialize first CPU calculation benchmark
        self.process.cpu_percent(interval=None)
        
        while not self.stop_signal.is_set():
            try:
                # Capture physical memory allocated to RAM (RSS) in Megabytes
                mem_mb = self.process.memory_info().rss / (1024 ** 2)
                self.ram_samples.append(mem_mb)
                
                # Capture system-adjusted CPU utilization percentage
                cpu_p = self.process.cpu_percent(interval=None)
                self.cpu_samples.append(cpu_p)
                
                time.sleep(self.interval)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

    def run_profile(self, target_function, *args, **kwargs):
        # Establish baseline metrics
        initial_ram = self.process.memory_info().rss / (1024 ** 2)
    
        # Launch sampling worker thread
        sampler_thread = threading.Thread(target=self._sample_loop, daemon=True)
        sampler_thread.start()
    
        start_time = time.perf_counter()
        
        # Execute your application and safely intercept Ctrl+C closure
        try:
            target_function(*args, **kwargs)
        except KeyboardInterrupt:
            print("\n[!] Profiling stopped manually via Ctrl+C. Generating report...")
        finally:
            # Terminate sampling once execution completes or is interrupted
            end_time = time.perf_counter()
            self.stop_signal.set()
            sampler_thread.join()
                
        # Compile statistics
        duration = end_time - start_time
        peak_ram = max(self.ram_samples) if self.ram_samples else initial_ram
        ram_overhead = peak_ram - initial_ram
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0
        peak_cpu = max(self.cpu_samples) if self.cpu_samples else 0.0

        # Output Results
        print("=" * 45)
        print("           RESOURCE OVERHEAD REPORT          ")
        print("=" * 45)
        print(f"Total Execution Time : {duration:.4f} seconds")
        print("-" * 45)
        print(f"Baseline RAM Usage   : {initial_ram:.2f} MB")
        print(f"Peak RAM Usage       : {peak_ram:.2f} MB")
        print(f"Net RAM Overhead     : +{ram_overhead:.2f} MB (Delta)")
        print("-" * 45)
        print(f"Average CPU Load     : {avg_cpu:.1f}%")
        print(f"Peak CPU Spike       : {peak_cpu:.1f}%")
        print("=" * 45)

import cProfile
import pstats
import io

def calculate_overhead():
    pr = cProfile.Profile()
    pr.enable()
    
    # Execute the target project or function
    run_osd()
    
    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(20)  # Print top 20 functions by overhead
    print(s.getvalue())

if __name__ == '__main__':
    profiler = ResourceProfiler(interval=0.05)

    # FIX: Pass the function name directly without ()
    # profiler.run_profile(run_osd) 
    calculate_overhead()
