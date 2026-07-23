
Principles:

- Progressive application (detail? think of a better label to lkabel this). for each method, we shoudl have different levels of detail / involvement that you can go to with it. so that we can get someo f the benefits of more detailed testing systems without having to go to all the hassle upfront. like progressive disclosure but for conformance detail / testing infra complexity.

FUTURE IDEAS:

e2e harness engineer:
- reference file for setting up docker-compose based e2e harnesses
- useful when you need to simulate interactions between distributed systems in full
- features setting up a SUT container built from local source code with other containers running dependant services
- answers: how to minimise flakiness? how to make failures obvious and clear? how to extract maximum utility from the harness?
- idea: wrap it with a python cli. this way we can either: write scripted tests in bash, or do adhoc probing via cli
- how to make the cli stable / useful? Fully self documenting. Each command contains its own check / act / validate loop. (Check pre-requisites. Do action. Validate response. Fail fast with clear logs.)
- stability: when using supporting services, we need to know those services are running properly before relying on them for tests. perhaps an assertion that scans the logs looking for a regex value? or a file that is written / deleted when ready? etc.
- efficiency: how to use docker to build cached builds so that rerunning tests is fast / no cold start
- how to combine together all logs in a useful way? could we add things like: intercept and log all docker compose traffic. (tcpdump for tcp, mitmproxy for http)
- can the cli do linting on docker compose file? maybe if we tag resources in docker compose to indicate what is SUT, what is support, etc.
- could the harness act as a layer to be built on for model based testing? or conformance testing against a simpler model? (tracing, event log, etc)
