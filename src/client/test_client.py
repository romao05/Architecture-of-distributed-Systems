import rpyc
import time

def test_server():
    print("[CLIENT] Connecting to server...")
    # Connect to the server container on port 18861
    conn = rpyc.connect("server", 18861)
    
    keyword = "the"
    filename = "Interstellar.txt"
    
    print(f"\n[CLIENT] Test 1: First request for '{keyword}' (Should be a CACHE MISS)")
    start_time = time.perf_counter()
    count1 = conn.root.count_keyword(filename, keyword)
    latency1 = (time.perf_counter() - start_time) * 1000
    print(f"Result: {count1} occurrences. Latency: {latency1:.2f} ms")
    
    print(f"\n[CLIENT] Test 2: Second request for '{keyword}' (Should be a CACHE HIT)")
    start_time = time.perf_counter()
    count2 = conn.root.count_keyword(filename, keyword)
    latency2 = (time.perf_counter() - start_time) * 1000
    print(f"Result: {count2} occurrences. Latency: {latency2:.2f} ms")

if __name__ == "__main__":
    # Give the server a few seconds to start up before connecting
    time.sleep(3) 
    test_server()