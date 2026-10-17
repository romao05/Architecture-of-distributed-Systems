Markdown
## Getting Started & Usage

### 1. Run the Full Cluster
Build and deploy the Redis cache, 3 server replicas, and the load balancer:
```bash
docker compose up -d --build --wait
2. Test the Load Balancer
Send a batch of parallel requests through the load balancer:

Bash
docker compose run --rm --no-deps client wordcount-client --file shakespeare.txt --keyword "love,death,king,queen,night,day,war,peace,heart" --repeat 9 --parallel
3. Test Fault Tolerance (Phase 4)
Stream the load balancer logs in one terminal:

Bash
docker compose logs -f loadbalancer
Run a continuous stream of requests in a second terminal:

Bash
docker compose run --rm --no-deps client wordcount-client --file shakespeare.txt --keyword "love,death,king,queen,night,day,war,peace,heart" --repeat 1000
In a third terminal, forcefully kill one of the servers to observe instant re-routing:

Bash
docker kill wordcount-server2
Observe the 🔴 Health check... FAILED message in the load balancer logs and the ⚠️ Connection dropped recovery in the client output.

Bring the server back online to test automated recovery:

Bash
docker start wordcount-server2
Observe the 🟢 Health check... is back ONLINE log and the resumption of traffic distribution.

Fault Tolerance Evidence (Phase 4)
1. Client-Side Resilience (Handling Connection Drops & Recovery)
2. Load Balancer-Side Detection, Re-routing & Recovery
Makefile Quick Reference
If your environment supports make, you can use these shortcuts:

Bash
make up                 # Start redis, server1-3, and load balancer
make demo               # Run 9 parallel requests
make logs               # Follow load balancer and server logs
make lb-lrt             # Switch to least response time algorithm
make benchmark-phase3   # Run latency comparisons
Generating Report Figures & Tables
To run the automated benchmarking scripts and generate LaTeX tables and PDF figures for the final IEEE report:

Bash
.venv\Scripts\python scripts\benchmark.py
.venv\Scripts\python scripts\plot_phase3.py --report-dir ../ADS-Project
