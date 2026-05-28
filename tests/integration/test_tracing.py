#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests verifying charm traces reach an OpenTelemetry Collector."""

import time

import jubilant
import pytest
from conftest import (
    COS_CHANNEL,
    OTEL_COLLECTOR_APP_NAME,
)
from jubilant import Juju
from tenacity import retry, stop_after_attempt, wait_fixed

PARCA_AGENT = "parca-agent"
UBUNTU = "ubuntu-lite"
UBUNTU_APP = "ubuntu-noble"
NOBLE_BASE = "ubuntu@24.04"


def _trigger_update_status_event(juju: Juju, unit_name: str):
    """Fire an update-status hook on the given unit to force charm trace emission."""
    unit_slug = unit_name.replace("/", "-")
    juju.exec(
        f"JUJU_DISPATCH_PATH=hooks/update-status"
        f" /var/lib/juju/agents/unit-{unit_slug}/charm/dispatch",
        unit=unit_name,
    )


def _get_otelcol_metric(juju: Juju, metric_name: str, label_filter: str = "") -> float:
    """Return the numeric value of a Prometheus metric from the otelcol self-monitoring endpoint.

    Uses ``curl localhost:8888/metrics`` on the otelcol unit (port 8888 is the
    self-monitoring / Prometheus scrape endpoint exposed by the collector snap).

    Args:
        juju: Jubilant Juju instance.
        metric_name: Exact Prometheus metric name (without labels).
        label_filter: Optional substring that must appear in the matching line
                      (e.g. a label selector like ``receiver="otlp/..."``)

    Returns:
        The float value of the first matching line, or 0.0 if not found.
    """
    raw = juju.ssh(
        f"{OTEL_COLLECTOR_APP_NAME}/0",
        "curl -s localhost:8888/metrics",
    )
    for line in raw.splitlines():
        if line.startswith(metric_name) and not line.startswith("#"):
            if label_filter and label_filter not in line:
                continue
            # Prometheus exposition: "metric_name{labels} value [timestamp]"
            parts = line.rsplit(maxsplit=1)
            try:
                return float(parts[-1])
            except ValueError:
                continue
    return 0.0


@pytest.mark.setup
def test_deploy_parca_agent(juju: Juju, charm):
    """Deploy parca-agent and a principal ubuntu charm for it to attach to."""
    juju.deploy(charm, PARCA_AGENT, num_units=0)
    juju.deploy(
        UBUNTU,
        UBUNTU_APP,
        base=NOBLE_BASE,
        constraints={"virt-type": "virtual-machine"},
    )
    juju.integrate(UBUNTU_APP, PARCA_AGENT)
    juju.wait(
        lambda status: jubilant.all_active(status, UBUNTU_APP),
        timeout=15 * 60,
        error=lambda status: jubilant.any_error(status, UBUNTU_APP),
        delay=10,
        successes=3,
    )
    # parca-agent is blocked (no store configured) – that's expected and is fine for tracing
    juju.wait(
        lambda status: jubilant.all_blocked(status, PARCA_AGENT),
        timeout=10 * 60,
        delay=10,
        successes=3,
    )


@pytest.mark.setup
def test_deploy_otel_collector(juju: Juju):
    """Deploy the opentelemetry-collector charm."""
    # Set workload sampling rate to 100% so charm traces are not dropped.
    # TODO: remove workaround once https://github.com/canonical/opentelemetry-collector-operator/issues/85 is fixed
    config = {"tracing_sampling_rate_workload": 100}
    juju.deploy(OTEL_COLLECTOR_APP_NAME, channel=COS_CHANNEL, base=NOBLE_BASE, config=config)


@pytest.mark.setup
def test_integrate_cos_agent(juju: Juju):
    """Relate parca-agent to opentelemetry-collector via cos-agent."""
    juju.integrate(
        PARCA_AGENT + ":cos-agent",
        OTEL_COLLECTOR_APP_NAME + ":cos-agent",
    )
    juju.wait(
        lambda status: jubilant.all_blocked(status, OTEL_COLLECTOR_APP_NAME),
        timeout=10 * 60,
        delay=10,
        successes=3,
    )
    # parca-agent stays blocked (no store) but is otherwise healthy
    juju.wait(
        lambda status: jubilant.all_blocked(status, PARCA_AGENT),
        timeout=10 * 60,
        delay=10,
        successes=6,
    )


@retry(stop=stop_after_attempt(10), wait=wait_fixed(10))
def test_charm_traces_are_pushed(juju: Juju):
    """Verify parca-agent charm traces are received by the opentelemetry-collector.

    ops_tracing buffers spans on the first hook and flushes them on the next hook
    invocation, so we fire update-status twice with a short pause in between.
    Then we assert that the collector's self-monitoring metrics show at least one
    span accepted from the parca-agent OTLP receiver.
    """
    unit = f"{PARCA_AGENT}/0"
    # First invocation: generates and buffers the trace
    _trigger_update_status_event(juju, unit)
    time.sleep(3)
    # Second invocation: flushes buffered spans to otelcol via OTLP HTTP
    _trigger_update_status_event(juju, unit)

    accepted = _get_otelcol_metric(
        juju,
        "otelcol_receiver_accepted_spans__spans__total",
        label_filter="otlp/",
    )
    assert accepted > 0, (
        f"Expected otelcol_receiver_accepted_spans > 0 for OTLP receiver, got {accepted}. "
        "parca-agent may not be emitting charm traces."
    )


@pytest.mark.teardown
def test_remove_relations(juju: Juju):
    juju.cli("remove-relation", PARCA_AGENT, UBUNTU_APP)
    juju.cli("remove-relation", PARCA_AGENT + ":cos-agent", OTEL_COLLECTOR_APP_NAME + ":cos-agent")


@pytest.mark.teardown
def test_remove_applications(juju: Juju):
    juju.cli("remove-application", PARCA_AGENT)
    juju.cli("remove-application", UBUNTU_APP)
    juju.cli("remove-application", OTEL_COLLECTOR_APP_NAME)
