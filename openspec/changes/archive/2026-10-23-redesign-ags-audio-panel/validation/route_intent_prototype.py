#!/usr/bin/env python3
"""Executable, dependency-free sketch of audio-panel route-intent semantics.

This validates the product state transitions only. It does not claim that the
installed PipeWire/WirePlumber adapter has been proven to emit these events.
"""
from dataclasses import dataclass
from enum import Enum


class Kind(Enum):
    FOLLOW = "follow-preferred"
    EXPLICIT = "explicit"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Route:
    kind: Kind
    endpoint: str | None = None


@dataclass
class Session:
    preferred: str
    actual: dict[str, str]
    intent: dict[str, Route]

    @classmethod
    def hydrate(cls, preferred: str, actual: dict[str, str]) -> "Session":
        # Effective endpoint is not route intent. Existing streams hydrate as
        # unknown until metadata or an app-owned command establishes intent.
        intents = {stream: Route(Kind.UNKNOWN) for stream in actual}
        return cls(preferred, actual.copy(), intents)

    def observe_new_stream(self, stream: str) -> None:
        # Product default: new app streams follow the selected preference unless
        # a per-app explicit route is established.
        self.actual[stream] = self.preferred
        self.intent[stream] = Route(Kind.FOLLOW)

    def observe_new_explicit_stream(self, stream: str, endpoint: str) -> None:
        self.actual[stream] = endpoint
        self.intent[stream] = Route(Kind.EXPLICIT, endpoint)

    def choose_preferred(self, endpoint: str) -> None:
        self.preferred = endpoint
        for stream, route in self.intent.items():
            if route.kind is Kind.FOLLOW:
                self.actual[stream] = endpoint
            elif route.kind is Kind.EXPLICIT and self.actual[stream] != route.endpoint:
                # Reassert explicit intent if the platform follows its old
                # default and moves a target that happened to equal it.
                self.actual[stream] = route.endpoint  # adapter command effect

    def choose_app_endpoint(self, stream: str, endpoint: str) -> None:
        self.intent[stream] = Route(Kind.EXPLICIT, endpoint)
        self.actual[stream] = endpoint

    def choose_follow(self, stream: str) -> None:
        self.intent[stream] = Route(Kind.FOLLOW)
        self.actual[stream] = self.preferred

    def external_target(self, stream: str, endpoint: str) -> None:
        self.actual[stream] = endpoint
        self.intent[stream] = Route(Kind.EXPLICIT, endpoint)

    def relink(self, stream: str, endpoint: str) -> None:
        # A graph-node/link replacement under the same stable stream identity
        # updates actual endpoint without dropping the application-owned intent.
        self.actual[stream] = endpoint

    def after_owner_restart(self) -> None:
        # Without durable intent or a trustworthy event history, endpoint
        # equality cannot prove user intent. Keep effective route, mark unknown.
        self.intent = {stream: Route(Kind.UNKNOWN) for stream in self.actual}


def require(condition: bool, scenario: str) -> None:
    if not condition:
        raise AssertionError(scenario)
    print(f"PASS {scenario}")


def main() -> None:
    s = Session.hydrate("C", {"music": "C", "browser": "A"})
    require(all(route.kind is Kind.UNKNOWN for route in s.intent.values()), "startup hydration does not infer intent from endpoint equality")
    require(s.actual["music"] == "C", "unknown intent still reports the observed endpoint")

    s.observe_new_stream("new-default")
    require(s.intent["new-default"].kind is Kind.FOLLOW and s.actual["new-default"] == "C", "new app without override follows preferred")
    s.observe_new_explicit_stream("new-explicit", "C")
    require(s.intent["new-explicit"] == Route(Kind.EXPLICIT, "C"), "new explicit target equal to preferred remains explicit")

    s.choose_app_endpoint("music", "C")
    require(s.intent["music"] == Route(Kind.EXPLICIT, "C"), "explicit selection equal to preferred remains explicit")
    s.choose_preferred("B")
    require(s.actual["music"] == "C" and s.actual["browser"] == "A", "preferred change preserves both explicit routes")
    require(s.intent["new-default"].kind is Kind.FOLLOW and s.actual["new-default"] == "B", "preferred change moves confirmed following streams")
    require(s.intent["new-explicit"] == Route(Kind.EXPLICIT, "C") and s.actual["new-explicit"] == "C", "preferred change preserves explicit route equal to previous default")

    s.choose_follow("music")
    require(s.actual["music"] == "B" and s.intent["music"].kind is Kind.FOLLOW, "return to follow moves to current preferred")
    s.external_target("browser", "C")
    require(s.intent["browser"] == Route(Kind.EXPLICIT, "C"), "external route change becomes explicit")
    s.relink("browser", "C")
    require(s.intent["browser"] == Route(Kind.EXPLICIT, "C"), "relink preserves intent under stable stream identity")
    s.after_owner_restart()
    require(all(route.kind is Kind.UNKNOWN for route in s.intent.values()), "restart without recoverable intent reports unknown")


if __name__ == "__main__":
    main()
