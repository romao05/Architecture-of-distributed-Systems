# Architecture-of-distributed-Systems
This repository contains the code used for the assignment from the course Architecture of Distributed Systems at TU/e


# Phase 1: Architectural Model

The main objective of this phase is to design the overall architecture of your distributed service. You
are asked to design a system where clients request the number of occurrences of a keyword in a text
document that is stored on the server.

1. Requirements & Stakeholders: Provide two functional and two non-functional requirements
of your system. Identify two stakeholders of the system and explain their roles in the system.

Functional Requirements:

Upon receiveing a file id and a word from a user, the system should provide the frequency of the received word in the file requested.

The server should cache the results in an in-memory database.

Non-Functional Requirements:

The client should receive the respons in less than 4 seconds.

The server should handle a load of __ thousand users.

Stakeholders and functions:

Site Reliability Engineers - Resource configuration for the application.

Developers - Group members.



3. Architectural Diagram & Description: Include a clear diagram that shows the architecture of
your system. Your service must follow a Client-Server architectural style. Your diagram should
illustrate the key components and the connectors between them. If needed, you may explain the
main functionality of the components and connectors concisely.

(Flow chart)

5. Architectural Style Trade-off Analysis: While your implementation must follow the Client-Server
model, briefly analyze the suitability of two other architectural styles, i.e., Peer-to-Peer, Layered,
and Publish-Subscribe, covered in the course. Discuss whether and how each could be used to
develop a similar service.

Publish-subscribe:

The publish-subscribe architecture is not compatible with these requirements. In this model, a server continuously performs a task and notifies subscribers of the internal changes they have requested. Here, the server's only purpose is to count words in static files in response to specific client requests, so there is no continuous activity: the server only acts when a request arrives.

Making publish-subscribe work would require one of two workarounds: a system that updates the files independently, or one that constantly iterates over every word in every file to keep the counts current. Even then, since the files are static, clients would periodically receive the same answers, which adds load without adding value.

Peer-2-peer:

Assuming the architecture has no file replicas, just like the Server-Client server described in Phase 1, a peer-to-peer (P2P) design with a super peer would also improve response time. The super peer acts as a request distributor: when a request arrives, it redirects it to the peer that holds the corresponding file, and that peer handles the request. While that peer is busy, the super peer keeps receiving new requests and distributing them among the other available peers. The system can therefore process multiple requests simultaneously, which is faster than the single-server, multiple-client implementation required by the assignment.

This design has drawbacks. Since there are no replicas, if the peer responsible for a file is unavailable or has crashed, the file cannot be found. The super peer is also a single point of failure and a potential bottleneck, because the speed of its request handling and distribution limits the throughput of the whole system, and if it crashes, the system stops working.

Regarding caching, the architecture would have caches at both levels. The super peer would keep a global cache, and each peer would keep a local cache of the most frequently requested files it is responsible for.



#for next meet. although usual text counter services are user based clients, there is a possibility that this might be a service for a company and they can be considered as a client. In which case, they will also be a stakeholder since it is their project requirement. additionally, it is not clear if the client provides the reference text which will then be stored in the server or the server already has the text stored and the client just provides the reference. the former makes sense.


