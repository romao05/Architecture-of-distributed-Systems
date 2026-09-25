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






