import rpyc
import time
import threading
import numpy as np
import matplotlib.pyplot as plt
import concurrent.futures

# The assignment requires at least 5 rates, starting >=10, with intervals >=10. 
# This tests 6 rates up to 200 req/s.
REQUEST_RATES = [50, 80, 110, 140, 170, 200] 

# 15 seconds per rate guarantees enough time to gather thousands of data points
DURATION_PER_RATE = 15  

# The specific workloads requested to be executed sequentially
WORKLOADS = [
    ("Interstellar.txt", "the"),
    ("Kung_fu_panda.txt", "and"),
    ("Sherlock_holmes.txt", "is")
]

# Use thread-local storage to reuse TCP connections. 
# Opening 200 new sockets per second would exhaust Docker's network ports and crash the test.
thread_local = threading.local()

def get_connection():
    """Maintains a persistent RPyC connection per thread."""
    if not hasattr(thread_local, "conn") or thread_local.conn.closed:
        thread_local.conn = rpyc.connect("server", 18861)
    return thread_local.conn

def send_request(filename, keyword):
    """Measures the exact execution latency of the request round-trip[cite: 4]."""
    try:
        conn = get_connection()
        start = time.perf_counter()
        conn.root.count_keyword(filename, keyword)
        latency = (time.perf_counter() - start) * 1000
        return latency
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def test_rate(rate, filename, keyword):
    """Fires requests at a specific rate for a set duration."""
    print(f"  -> Testing {rate} req/sec...")
    latencies = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=rate) as executor:
        for _ in range(DURATION_PER_RATE):
            loop_start = time.perf_counter()
            
            # Dispatch 'rate' number of requests simultaneously
            futures = [executor.submit(send_request, filename, keyword) for _ in range(rate)]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result is not None:
                    latencies.append(result)
            
            # Sleep for whatever fraction of the second is left to maintain the exact request rate
            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0, 1.0 - elapsed)
            time.sleep(sleep_time)

    avg_latency = np.mean(latencies)
    p99_latency = np.percentile(latencies, 99)
    print(f"     Result: Avg = {avg_latency:.2f} ms | P99 = {p99_latency:.2f} ms")
    return avg_latency, p99_latency

def run_benchmarks():
    for filename, keyword in WORKLOADS:
        print(f"\n==================================================")
        print(f"STARTING WORKLOAD: File='{filename}', Keyword='{keyword}'")
        print(f"==================================================")
        
        avg_results, p99_results = [], []
        
        for rate in REQUEST_RATES:
            avg, p99 = test_rate(rate, filename, keyword)
            avg_results.append(avg)
            p99_results.append(p99)
            
        # Clean up the filename for saving the images (e.g., remove .txt)
        file_prefix = filename.replace('.txt', '')
            
        # Figure 1: Average Execution Latency[cite: 4]
        plt.figure(figsize=(8, 5))
        plt.plot(REQUEST_RATES, avg_results, marker='o', color='b', linewidth=2)
        plt.title(f'Average Execution Latency vs Request Rate\n({filename} / "{keyword}")')
        plt.xlabel('Request Rate (req/s)')
        plt.ylabel('Latency (ms)')
        plt.grid(True, linestyle='--', alpha=0.7)
        avg_img_name = f'avg_latency_{file_prefix}.png'
        plt.savefig(avg_img_name) 
        plt.close()
        
        # Figure 2: 99th-Percentile (Tail) Latency[cite: 4]
        plt.figure(figsize=(8, 5))
        plt.plot(REQUEST_RATES, p99_results, marker='s', color='r', linewidth=2)
        plt.title(f'99th-Percentile (Tail) Latency vs Request Rate\n({filename} / "{keyword}")')
        plt.xlabel('Request Rate (req/s)')
        plt.ylabel('Latency (ms)')
        plt.grid(True, linestyle='--', alpha=0.7)
        p99_img_name = f'p99_latency_{file_prefix}.png'
        plt.savefig(p99_img_name)
        plt.close()
        
        print(f"SAVED: {avg_img_name} and {p99_img_name}")

if __name__ == "__main__":
    print("[BENCHMARK] Warming up. Giving server 3 seconds to boot...")
    time.sleep(3)
    run_benchmarks()
    print("\n[BENCHMARK] All workloads completed successfully.")