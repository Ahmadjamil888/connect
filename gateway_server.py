#!/usr/bin/env python3

import argparse
import asyncio
from pathlib import Path

from gateway_runtime import AgentRuntime, GatewayServer, load_gateway_config


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--config", help="Path to openclaw-style config JSON")
    args = parser.parse_args()
    config = load_gateway_config(Path(args.config) if args.config else None)
    runtime = AgentRuntime(config)
    server = GatewayServer(runtime)
    print(f"Gateway listening on ws://{config.host}:{config.port}")
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
