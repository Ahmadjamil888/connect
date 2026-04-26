# OpenClaw Parity Tracker

This repo is not at full OpenClaw parity yet.

This file tracks what is real, what is partial, and what is missing so progress can be measured honestly.

## Current Status

### Implemented
- Gateway-style runtime split
- WebSocket gateway server
- Local dashboard server
- Session store and session tools
- Memory store and memory tools
- Workspace bootstrap with `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `HEARTBEAT.md`
- Tool allow/deny and profile resolution
- Local cron persistence and scheduler loop
- Background orchestration queue
- Canvas persistence and snapshot/eval/present
- Node pairing contract over HTTP
- Browser-based node client prototype
- Telegram connector
- Discord webhook connector
- Slack webhook connector
- CLI onboarding for provider, launch mode, GitHub token, and messaging setup

### Partial
- Browser automation exists, but not as a full OpenClaw-style typed browser runtime with remote node targeting
- Canvas exists locally, but not as a full multi-device live collaborative canvas
- Node support exists as a local contract, but not as packaged iOS/Android apps
- Messaging exists for a few connectors, but not the broad multi-platform matrix
- Media tools exist in catalog shape, but are not wired to production backends
- Gateway control exists, but not full self-update/restart/deployment lifecycle management
- Memory exists, but not a full skill marketplace and long-term semantic memory stack

### Missing
- WhatsApp connector
- iMessage / BlueBubbles connector
- Slack bidirectional bot connector
- Signal connector
- Teams connector
- Matrix connector
- Discord inbound bot connector
- Google Chat connector
- IRC / LINE / WeChat / QQ / Feishu / Mattermost / Nextcloud Talk / Nostr / Twitch / Zalo connectors
- Real X/Twitter search integration
- Hosted node management
- Native mobile apps
- Full ClawHub-style skill registry and installation flow
- Lobster-style workflow engine
- Rich webhook trigger framework
- Production auth, multi-user access control, secrets management, and deployment packaging
- Sandboxed host/node execution model
- Update channels and release management

## Parity Areas

### 1. Gateway
- Status: partial
- Next work:
  - authenticated control plane
  - reconnect logic for external transports
  - deployment/service management

### 2. Agent Runtime
- Status: partial
- Next work:
  - stronger typed tool planner loop
  - per-agent model routing
  - cheaper subagent model delegation

### 3. Messaging
- Status: partial
- Implemented:
  - Telegram
  - Discord webhooks
  - Slack webhooks
- Next work:
  - WhatsApp
  - Slack bot mode
  - Discord inbound bot mode
  - Teams / Signal / Matrix

### 4. Nodes
- Status: partial
- Implemented:
  - pairing contract
  - state ingestion
  - browser prototype client
- Next work:
  - native Android client
  - native iOS client
  - camera/screen capture permissions
  - push notifications

### 5. Canvas
- Status: partial
- Implemented:
  - present
  - eval
  - snapshot
- Next work:
  - real-time interactive UI
  - remote node presentation
  - richer card/widget model

### 6. Media
- Status: missing
- Next work:
  - image analyze backend
  - image generation backend
  - TTS backend
  - music/video generation backends

### 7. Skills
- Status: missing
- Next work:
  - local skill manifest format
  - install/update/remove flow
  - registry index
  - trust/scanning policy

### 8. Workflows
- Status: missing
- Next work:
  - YAML workflow definitions
  - multi-step graph execution
  - per-step agent/tool policies
  - webhook and cron triggers

## Definition of "Full Parity"

This repo should only be described as full OpenClaw parity when:
- major messaging platforms are implemented end-to-end
- node apps exist beyond local HTTP prototypes
- canvas is interactive and multi-device
- media tools are backed by real providers
- skills and workflows are installable and runnable
- deployment and operations are production-grade
- tests cover all core runtime paths
