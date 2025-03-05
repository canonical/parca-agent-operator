# Parca Agent Operator

Parca Agent is an always-on sampling profiler that uses eBPF to capture raw profiling data with
very low overhead. It observes user-space and kernel-space stacktraces 19 times per second and
builds pprof formatted profiles from the extracted data. Read more details in the design
documentation.

The collected data can be viewed locally via HTTP endpoints and then be configured to be sent to a
Parca server to be queried and analysed over time.

This operator is a subordinate, meaning it can be combined with any other operator to provide
profiling capability at the machine level.

## Example Usage

Below is an example of deploying PostgreSQL and using Parca Agent to profile each unit:

```shell
# Deploy PostgreSQL
juju deploy postgresql --constraints="virt-type=virtual-machine"

# Deploy the parca-agent subordinate
juju deploy parca-agent

# Integrate the agent with PostgreSQL
juju integrate postgresql parca-agent
```
