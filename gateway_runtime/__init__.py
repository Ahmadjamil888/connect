"""Gateway runtime package.

Keep package import side effects minimal so submodules like `gateway_runtime.auth`
can be used independently from the legacy dashboard/runtime stack.
"""

from importlib import import_module

__all__ = [
    "GatewayConfig",
    "load_gateway_config",
    "DashboardServer",
    "AgentRuntime",
    "GatewayServer",
    "config",
    "auth",
    "dashboard",
    "runtime",
    "server",
]


def __getattr__(name):
    if name in {"GatewayConfig", "load_gateway_config"}:
        mod = import_module("gateway_runtime.config")
        return getattr(mod, name)
    if name == "DashboardServer":
        mod = import_module("gateway_runtime.dashboard")
        return getattr(mod, name)
    if name == "AgentRuntime":
        mod = import_module("gateway_runtime.runtime")
        return getattr(mod, name)
    if name == "GatewayServer":
        mod = import_module("gateway_runtime.server")
        return getattr(mod, name)
    raise AttributeError(name)
