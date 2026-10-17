Markdown
# Distributed Word Count Service: Scalability, Load Balancing & Fault Tolerance

This project implements a distributed Word Count Service built for the **Architecture of Distributed Systems** course at Eindhoven University of Technology (TU/e). The system processes real-time keyword occurrences across text files, utilizing an in-memory database (`Redis`) for high-performance caching and hot-keyword tracking.

---

## Project Overview & Course Phases

### Phase 1: Architectural Model
* **Architectural Style:** Client-Server architecture.
* **Core Requirements:** 
  * *Functional:* Provide exact word frequencies upon receiving a file ID and keyword; cache results in Redis.
  * *Non-Functional:* Client response time under 4 seconds; support concurrent user load.
* **Stakeholders:** Site Reliability Engineers (resource configuration) and Developers (implementation team).
* **Architectural Style Trade-offs:**
  * *Publish-Subscribe:* Incompatible with this system because the files are static and requests are sporadic; push-based notifications add unnecessary overhead without continuous state changes.
  * *Peer-to-Peer (P2P):* Could use a super-peer request distributor with distributed caches, but introduces single points of failure and file availability risks if replicas are missing.

### Phase 2: Core Service & Virtualization
* **Virtualization & Orchestration:** Docker containers managed via Docker Compose.
* **RPC Communication:** Implemented using Python's `rpyc` library.
* **Performance Evaluation:** Measured execution latency (average and 99th-percentile tail latency) across varying request rates.

### Phase 3: Scalability & Load Balancing
* **Replication:** Scaled from 1 server to 3 active replicas (`server1`, `server2`, `server3`).
* **Custom TCP Load Balancer:** Developed using Python's `asyncio` library to pipe raw byte-streams between clients and servers without RPC overhead.
* **Dynamic Algorithms:** 
  1. **Least Connections:** Routes traffic to the server with the fewest active connections.
  2. **Least Response Time (LRT):** Uses an Exponentially Weighted Moving Average (EWMA) of past latencies with an aging factor to optimize expected wait times.

### Phase 4: Fault Tolerance & Health Monitoring
* **Background Health Probing:** The load balancer runs an asynchronous health check loop that periodically probes each backend server via fast TCP handshakes.
* **Instant Failure Isolation:** When a server crashes or is killed, the load balancer instantly flags it offline and routes all incoming traffic to healthy replicas.
* **Automatic Recovery:** Once a failed server comes back online, the health monitor detects its recovery and seamlessly reintegrates it into the active routing pool.

---

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

## Fault Tolerance Evidence (Phase 4)

### 1. Client-Side Resilience (Handling Connection Drops & Recovery)
![Client Resilience - Part 1](https://raw.githubusercontent.com/satvik84/Architecture-of-distributed-Systems/phase-4-fault-tolerance/assets/fault-tolerance-client.png)
![Client Resilience - Part 2](https://raw.githubusercontent.com/satvik84/Architecture-of-distributed-Systems/phase-4-fault-tolerance/assets/fault-tolerance-client-2.png)

### 2. Load Balancer-Side Detection, Re-routing & Recovery
![Load Balancer - Part 1](https://raw.githubusercontent.com/satvik84/Architecture-of-distributed-Systems/phase-4-fault-tolerance/assets/fault-tolerance-lb.png)
![Load Balancer - Part 2](https://raw.githubusercontent.com/satvik84/Architecture-of-distributed-Systems/phase-4-fault-tolerance/assets/fault-tolerance-lb-2.png)

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
