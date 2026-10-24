<!-- ai-generated: 70% - opencode drafted the explanation from the two measurements I ran through Toxiproxy; I checked the numbers against the load output -->

# The gap between the client's p99 and the server's

The toxic is a downstream latency toxic of **100 ms with 10 ms of jitter, toxicity 1.0**, put in front of `svcdesk`
by Toxiproxy 2.12.0 (`docker compose --profile gap up -d toxiproxy`, proxy `svcdesk` on 8666 to `svcdesk:8080`). The
proxy sits between the load generator and the service, downstream of it, so it delays the answers on their way back
to the client and never touches the request the service measures.

Two different clocks see the same requests. The client, `oha` with `--latency-correction` at 40 requests per second
for 60 seconds, measures from the instant a request was scheduled until the answer arrived: its p99 was
**218.0 ms**. The server measures inside the process, from the first byte of the request handler to the last write of
the response: the p99 of `http_server_request_duration_seconds` over the same run was **114.2 ms**. The difference,
**103.8 ms**, is almost exactly the 100 ms the toxic was told to add, plus the toxiproxy hop and the jitter.

That is the whole point of the exercise: the service cannot see the gap. Its histogram is honest about what it did,
and its p99 (114 ms) still sits where it sat without the proxy; the users, however, waited 218 ms. A latency SLO
measured on the server's histogram would report 99 % of the requests at or below 125 ms and never notice that the
network in front of the service doubles every one of them. Client-side measurement is what sees the user's latency;
server-side measurement is what tells you whether the blame is yours or the path's. In this laboratory the
distinction has a second use: the checker's own q, measured at the client, is the number the bucket ladder has to
resolve, which is why a ladder designed around the server's own p50 would fail.
