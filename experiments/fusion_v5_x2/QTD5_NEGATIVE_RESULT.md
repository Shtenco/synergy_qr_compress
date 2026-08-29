# QTD5 optimal-parser prototype — negative result

A bounded dynamic-programming COPY/LITERAL parser was prototyped locally against the same real Git README used by QTD4.1/AR2/AR3.

- QTD4.1 baseline: 571 B
- DP proposal best: 571 B
- exact round-trip: PASS

The proposal is therefore intentionally **not** promoted into production code yet. Current evidence says the remaining gain is in skeleton/literal probability modeling (AR2/AR3), not merely replacing QTD4.1 greedy matching with this approximate DP cost.
