from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from gateway_runtime.node_client import render_node_client_html
from gateway_runtime.runtime import AgentRuntime


def render_dashboard_html() -> str:
    return """<!doctype html>
<html class="dark" lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CONNECT Operator Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght@300;400;500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #131313;
      --surface: #181818;
      --surface-2: #1f1f1f;
      --surface-3: #272727;
      --surface-4: rgba(255, 255, 255, 0.035);
      --line: rgba(255, 255, 255, 0.075);
      --line-strong: rgba(39, 243, 169, 0.18);
      --text: #ebeee9;
      --muted: #94a196;
      --accent: #27f3a9;
      --accent-2: #ffb95e;
      --accent-soft: rgba(39, 243, 169, 0.12);
      --accent-soft-2: rgba(255, 185, 94, 0.12);
      --danger: #ff908e;
      --shadow: 0 30px 90px rgba(0, 0, 0, 0.34);
      --radius-xl: 28px;
      --radius-lg: 22px;
      --radius-md: 16px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      font-family: "Inter", system-ui, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 0% 0%, rgba(39,243,169,0.14), transparent 26%),
        radial-gradient(circle at 100% 0%, rgba(255,185,94,0.08), transparent 22%),
        linear-gradient(180deg, #0f0f0f 0%, #131313 48%, #111111 100%);
      overflow: hidden;
    }
    button, input, select, textarea, a {
      font: inherit;
      color: inherit;
    }
    button {
      border: 0;
      cursor: pointer;
      background: none;
    }
    a {
      text-decoration: none;
      color: inherit;
    }
    .material-symbols-outlined {
      font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 20;
      line-height: 1;
      font-size: 20px;
    }
    ::-webkit-scrollbar { width: 7px; height: 7px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,0.12);
      border-radius: 999px;
    }
    ::-webkit-scrollbar-thumb:hover { background: rgba(39,243,169,0.35); }
    .hidden { display: none !important; }
    .app-shell {
      height: 100dvh;
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
    }
    .sidebar {
      position: relative;
      z-index: 30;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 18px;
      padding: 18px;
      background: rgba(10, 10, 10, 0.88);
      backdrop-filter: blur(24px);
      border-right: 1px solid var(--line);
    }
    .brand-block,
    .status-panel,
    .nav-panel,
    .sidebar-panel,
    .hero-panel,
    .surface-card,
    .info-card,
    .row-card,
    .integration-card,
    .workflow-card,
    .doc-card,
    .composer,
    .chat-input-wrap,
    .stat-card {
      background: rgba(25, 25, 25, 0.82);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
    }
    .brand-block,
    .status-panel,
    .nav-panel,
    .sidebar-panel,
    .surface-card,
    .hero-panel {
      border-radius: var(--radius-xl);
    }
    .brand-block {
      padding: 18px;
      display: flex;
      gap: 14px;
      align-items: center;
      background:
        linear-gradient(180deg, rgba(39,243,169,0.1), rgba(39,243,169,0.03)),
        rgba(25,25,25,0.88);
      border-color: var(--line-strong);
    }
    .brand-mark {
      width: 48px;
      height: 48px;
      border-radius: 16px;
      display: grid;
      place-items: center;
      background: rgba(39,243,169,0.12);
      border: 1px solid rgba(39,243,169,0.22);
      color: var(--accent);
    }
    .brand-mark .material-symbols-outlined {
      font-variation-settings: "FILL" 1, "wght" 500, "GRAD" 0, "opsz" 20;
    }
    .brand-copy strong {
      display: block;
      font-family: "Space Grotesk", sans-serif;
      font-size: 22px;
      line-height: 1;
      letter-spacing: -0.04em;
      color: var(--accent);
    }
    .brand-copy span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }
    .sidebar-scroll {
      min-height: 0;
      overflow-y: auto;
      display: grid;
      gap: 18px;
      padding-right: 4px;
    }
    .status-panel,
    .sidebar-panel {
      padding: 16px;
    }
    .status-grid {
      display: grid;
      gap: 14px;
    }
    .status-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
    }
    .eyebrow,
    .subtle {
      font-family: "Space Grotesk", sans-serif;
      font-size: 11px;
      line-height: 1;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: var(--muted);
    }
    .status-value {
      margin-top: 5px;
      font-size: 14px;
      font-weight: 600;
      line-height: 1.35;
      word-break: break-word;
    }
    .pill,
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 7px 11px;
      background: var(--accent-soft);
      border: 1px solid var(--line-strong);
      color: var(--accent);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .nav-panel {
      padding: 12px;
      display: grid;
      gap: 8px;
    }
    .nav-btn {
      width: 100%;
      border-radius: 18px;
      padding: 13px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      border: 1px solid transparent;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
    }
    .nav-btn:hover {
      transform: translateX(2px);
      background: rgba(255,255,255,0.04);
      border-color: rgba(255,255,255,0.05);
    }
    .nav-btn.active {
      background: linear-gradient(180deg, rgba(39,243,169,0.13), rgba(39,243,169,0.05));
      border-color: var(--line-strong);
    }
    .nav-main {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .nav-icon {
      width: 38px;
      height: 38px;
      border-radius: 14px;
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      background: rgba(255,255,255,0.04);
      color: var(--accent);
    }
    .nav-copy {
      min-width: 0;
      text-align: left;
    }
    .nav-copy strong {
      display: block;
      font-family: "Space Grotesk", sans-serif;
      font-size: 15px;
      line-height: 1.1;
    }
    .nav-copy span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .nav-count {
      flex: 0 0 auto;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    .sidebar-panel h3,
    .hero-copy h2,
    .surface-head h2,
    .integration-card h3,
    .workflow-card h3,
    .doc-card h3,
    .panel-title {
      font-family: "Space Grotesk", sans-serif;
    }
    .sidebar-panel h3 {
      margin: 0 0 12px;
      font-size: 13px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .metric-stack {
      display: grid;
      gap: 10px;
    }
    .metric-card {
      border-radius: 18px;
      padding: 12px 14px;
      background: rgba(255,255,255,0.035);
      border: 1px solid rgba(255,255,255,0.05);
    }
    .metric-card strong {
      display: block;
      font-size: 24px;
      line-height: 1;
      margin-bottom: 5px;
    }
    .metric-card span {
      color: var(--muted);
      font-size: 12px;
    }
    .sidebar-footer {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 10px;
      padding-top: 14px;
      border-top: 1px solid rgba(255,255,255,0.05);
    }
    .footer-avatar {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--accent);
    }
    .footer-meta {
      min-width: 0;
    }
    .footer-meta strong {
      display: block;
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .footer-meta span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 11px;
    }
    .main-shell {
      min-width: 0;
      min-height: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(12, 12, 12, 0.74);
      backdrop-filter: blur(24px);
      position: relative;
      z-index: 20;
    }
    .topbar-left {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 16px;
      flex: 1;
    }
    .topbar-title {
      min-width: 0;
    }
    .topbar-title h1 {
      margin: 8px 0 0;
      font-family: "Space Grotesk", sans-serif;
      font-size: clamp(28px, 4vw, 40px);
      line-height: 0.96;
      letter-spacing: -0.05em;
      font-weight: 600;
    }
    .topbar-sub {
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
      max-width: 720px;
    }
    .topbar-actions {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .mobile-toggle,
    .ghost-btn,
    .link-btn,
    .primary-btn,
    .secondary-btn,
    .chip-btn,
    .top-action,
    .compact-btn {
      border-radius: 16px;
      padding: 11px 15px;
      border: 1px solid rgba(255,255,255,0.08);
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease, color 160ms ease;
    }
    .mobile-toggle:hover,
    .ghost-btn:hover,
    .link-btn:hover,
    .primary-btn:hover,
    .secondary-btn:hover,
    .chip-btn:hover,
    .top-action:hover,
    .compact-btn:hover {
      transform: translateY(-1px);
      border-color: rgba(39,243,169,0.18);
    }
    .mobile-toggle {
      display: none;
      width: 46px;
      height: 46px;
      padding: 0;
      place-items: center;
      background: rgba(255,255,255,0.03);
    }
    .badge-btn {
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--accent);
      background: var(--accent-soft);
      border: 1px solid var(--line-strong);
      font-weight: 700;
    }
    .ghost-btn,
    .link-btn,
    .secondary-btn,
    .chip-btn,
    .compact-btn,
    .top-action {
      background: rgba(255,255,255,0.03);
      color: var(--text);
    }
    .primary-btn {
      background: var(--accent);
      color: #063322;
      font-weight: 800;
      border-color: rgba(39,243,169,0.3);
    }
    .top-action {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
    }
    .search-shell {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-width: 220px;
      padding: 11px 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
    }
    .search-shell input {
      width: 100%;
      background: transparent;
      border: 0;
      outline: 0;
      color: var(--text);
      font-size: 13px;
    }
    .main-scroll {
      min-height: 0;
      overflow-y: auto;
      padding: 24px;
      display: grid;
      gap: 24px;
    }
    .hero-panel {
      position: relative;
      overflow: hidden;
      padding: 24px;
      background:
        radial-gradient(circle at 10% 0%, rgba(39,243,169,0.13), transparent 30%),
        radial-gradient(circle at 100% 20%, rgba(255,185,94,0.08), transparent 20%),
        rgba(25, 25, 25, 0.86);
    }
    .hero-grid {
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(280px, 420px);
      gap: 18px;
      align-items: start;
    }
    .hero-copy h2 {
      margin: 10px 0 0;
      font-size: clamp(34px, 5.2vw, 58px);
      line-height: 0.95;
      letter-spacing: -0.05em;
      font-weight: 600;
      max-width: 760px;
    }
    .hero-copy p {
      margin: 16px 0 0;
      color: #c1c9c1;
      font-size: 15px;
      line-height: 1.7;
      max-width: 780px;
    }
    .hero-actions {
      margin-top: 22px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .hero-side {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .stat-card {
      border-radius: 22px;
      padding: 16px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)),
        rgba(20,20,20,0.84);
    }
    .stat-card strong {
      display: block;
      margin-top: 10px;
      font-size: 26px;
      line-height: 1;
      font-family: "Space Grotesk", sans-serif;
    }
    .stat-card span {
      display: block;
      margin-top: 5px;
      font-size: 12px;
      color: var(--muted);
    }
    .stat-card .material-symbols-outlined {
      color: var(--accent);
      font-size: 22px;
    }
    .surface-card {
      padding: 22px;
      display: grid;
      gap: 20px;
    }
    .surface-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }
    .surface-head h2 {
      margin: 8px 0 0;
      font-size: 24px;
      line-height: 1;
      font-weight: 600;
      letter-spacing: -0.03em;
    }
    .view-section {
      display: grid;
      gap: 18px;
    }
    .view-grid {
      display: grid;
      gap: 18px;
    }
    .chat-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(300px, 420px);
      gap: 20px;
      min-height: 680px;
    }
    .chat-shell {
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 14px;
    }
    .chat-toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .select,
    .field {
      width: 100%;
      border-radius: 16px;
      padding: 12px 14px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      outline: 0;
    }
    .select {
      min-width: 220px;
      width: auto;
    }
    .chat-thread {
      min-height: 0;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 14px;
      padding-right: 6px;
    }
    .empty-state {
      border-radius: 24px;
      border: 1px dashed rgba(255,255,255,0.11);
      padding: 22px;
      color: var(--muted);
      background: rgba(255,255,255,0.02);
      line-height: 1.7;
    }
    .message {
      max-width: min(90%, 820px);
      border-radius: 22px;
      padding: 16px 18px;
      box-shadow: 0 14px 34px rgba(0,0,0,0.18);
      animation: riseIn 180ms ease;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.65;
      position: relative;
    }
    .message.user {
      align-self: flex-end;
      background: linear-gradient(180deg, rgba(39,243,169,0.16), rgba(39,243,169,0.08));
      border: 1px solid rgba(39,243,169,0.18);
    }
    .message.assistant {
      align-self: flex-start;
      background: rgba(255,255,255,0.045);
      border: 1px solid rgba(255,255,255,0.06);
    }
    .message.tool {
      align-self: flex-start;
      background: rgba(255,255,255,0.025);
      border: 1px dashed rgba(255,255,255,0.1);
      color: #d5d9d3;
    }
    .message-meta {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1;
      text-transform: uppercase;
      letter-spacing: 0.16em;
    }
    .typing {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.06);
      width: fit-content;
    }
    .typing span {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
      animation: pulse 1s infinite ease-in-out;
    }
    .typing span:nth-child(2) { animation-delay: 0.15s; }
    .typing span:nth-child(3) { animation-delay: 0.3s; }
    .composer {
      padding: 14px;
      border-radius: 24px;
      background: rgba(255,255,255,0.035);
    }
    .chat-input-wrap {
      border-radius: 18px;
      padding: 14px;
      background: rgba(0,0,0,0.16);
      border-color: rgba(255,255,255,0.05);
      box-shadow: none;
    }
    .composer textarea {
      width: 100%;
      min-height: 120px;
      resize: vertical;
      background: transparent;
      border: 0;
      outline: 0;
      color: var(--text);
      font-size: 15px;
      line-height: 1.6;
      padding: 0;
    }
    .composer-actions {
      margin-top: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .tiny {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }
    .right-stack,
    .card-list,
    .integration-grid,
    .workflow-grid,
    .docs-grid {
      display: grid;
      gap: 14px;
    }
    .info-card,
    .integration-card,
    .workflow-card,
    .doc-card,
    .row-card {
      border-radius: 22px;
      padding: 16px;
      min-width: 0;
      background: rgba(30,30,30,0.84);
    }
    .row-title,
    .panel-title {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 4px;
      word-break: break-word;
    }
    .row-meta,
    .row-extra {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
      word-break: break-word;
    }
    .row-extra { margin-top: 6px; }
    .json-box {
      margin: 0;
      max-height: 320px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 12px;
      line-height: 1.55;
      color: #d8ddd8;
      border-radius: 18px;
      padding: 14px;
      background: rgba(0,0,0,0.24);
      border: 1px solid rgba(255,255,255,0.06);
    }
    .integration-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .integration-top {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 10px;
    }
    .integration-card h3,
    .workflow-card h3,
    .doc-card h3 {
      margin: 0 0 8px;
      font-size: 18px;
      line-height: 1.1;
      letter-spacing: -0.02em;
    }
    .integration-card p,
    .workflow-card p,
    .doc-card p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.65;
    }
    .integration-form,
    .session-form {
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }
    .status-ok { color: var(--accent); }
    .status-bad { color: var(--danger); }
    .workflow-actions,
    .doc-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 16px;
    }
    .docs-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.54);
      opacity: 0;
      pointer-events: none;
      transition: opacity 180ms ease;
      z-index: 15;
    }
    body.sidebar-open .overlay {
      opacity: 1;
      pointer-events: auto;
    }
    @keyframes riseIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulse {
      0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
      40% { transform: scale(1); opacity: 1; }
    }
    @media (max-width: 1360px) {
      .chat-layout,
      .hero-grid {
        grid-template-columns: 1fr;
      }
      .integration-grid,
      .docs-grid {
        grid-template-columns: 1fr;
      }
      .hero-side {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }
    }
    @media (max-width: 1100px) {
      .app-shell {
        grid-template-columns: 1fr;
      }
      .sidebar {
        position: fixed;
        inset: 0 auto 0 0;
        width: min(86vw, 340px);
        transform: translateX(-105%);
        transition: transform 180ms ease;
      }
      body.sidebar-open .sidebar {
        transform: translateX(0);
      }
      .mobile-toggle {
        display: grid;
      }
      .search-shell {
        min-width: 0;
        width: min(300px, 100%);
      }
    }
    @media (max-width: 820px) {
      .topbar,
      .main-scroll,
      .hero-panel,
      .surface-card {
        padding-left: 18px;
        padding-right: 18px;
      }
      .topbar {
        flex-direction: column;
        align-items: stretch;
      }
      .topbar-actions {
        justify-content: flex-start;
      }
      .hero-side {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 620px) {
      .main-scroll {
        padding: 14px;
      }
      .topbar {
        padding: 14px;
      }
      .hero-panel,
      .surface-card {
        padding: 16px;
      }
      .hero-copy h2 {
        font-size: 34px;
      }
      .hero-actions,
      .composer-actions {
        flex-direction: column;
        align-items: stretch;
      }
      .chat-toolbar {
        flex-direction: column;
        align-items: stretch;
      }
      .select {
        width: 100%;
      }
      .hero-side {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="overlay" id="sidebarOverlay"></div>
  <div class="app-shell">
    <aside class="sidebar" id="sidebar">
      <div class="brand-block">
        <div class="brand-mark"><span class="material-symbols-outlined">terminal</span></div>
        <div class="brand-copy">
          <strong>Connect AI</strong>
          <span>v1 operator runtime</span>
        </div>
      </div>

      <div class="sidebar-scroll">
        <section class="status-panel">
          <div class="status-grid">
            <div class="status-row">
              <div>
                <div class="eyebrow">Mode</div>
                <div class="status-value" id="sidebarMode">local</div>
              </div>
              <span class="pill" id="sidebarLive">idle</span>
            </div>
            <div class="status-row">
              <div>
                <div class="eyebrow">Provider</div>
                <div class="status-value" id="sidebarProvider">-</div>
              </div>
              <div>
                <div class="eyebrow">Operator</div>
                <div class="status-value" id="sidebarUser">guest</div>
              </div>
            </div>
          </div>
        </section>

        <nav class="nav-panel">
          <button class="nav-btn active" data-view="chat">
            <div class="nav-main">
              <div class="nav-icon"><span class="material-symbols-outlined">dashboard</span></div>
              <div class="nav-copy"><strong>Dashboard</strong><span>Live CONNECT operator thread</span></div>
            </div>
            <div class="nav-count" id="navChatCount">0</div>
          </button>
          <button class="nav-btn" data-view="integrations">
            <div class="nav-main">
              <div class="nav-icon"><span class="material-symbols-outlined">hub</span></div>
              <div class="nav-copy"><strong>Integrations</strong><span>GitHub, Telegram, Slack, Discord, WhatsApp</span></div>
            </div>
            <div class="nav-count" id="navIntegrationCount">0</div>
          </button>
          <button class="nav-btn" data-view="sessions">
            <div class="nav-main">
              <div class="nav-icon"><span class="material-symbols-outlined">forum</span></div>
              <div class="nav-copy"><strong>Sessions</strong><span>Threads, agents, memory, activity</span></div>
            </div>
            <div class="nav-count" id="navSessionCount">0</div>
          </button>
          <button class="nav-btn" data-view="workflows">
            <div class="nav-main">
              <div class="nav-icon"><span class="material-symbols-outlined">account_tree</span></div>
              <div class="nav-copy"><strong>Workflows</strong><span>Automation and runnable routines</span></div>
            </div>
            <div class="nav-count" id="navWorkflowCount">0</div>
          </button>
          <button class="nav-btn" data-view="nodes">
            <div class="nav-main">
              <div class="nav-icon"><span class="material-symbols-outlined">devices</span></div>
              <div class="nav-copy"><strong>Nodes</strong><span>Devices, pairing, shared canvas state</span></div>
            </div>
            <div class="nav-count" id="navNodeCount">0</div>
          </button>
          <button class="nav-btn" data-view="docs">
            <div class="nav-main">
              <div class="nav-icon"><span class="material-symbols-outlined">description</span></div>
              <div class="nav-copy"><strong>Docs</strong><span>Operational guides and quick links</span></div>
            </div>
            <div class="nav-count">guide</div>
          </button>
        </nav>

        <section class="sidebar-panel">
          <h3>System</h3>
          <div class="metric-stack">
            <div class="metric-card"><strong id="metricTools">0</strong><span>tools available</span></div>
            <div class="metric-card"><strong id="metricServices">0</strong><span>live services</span></div>
            <div class="metric-card"><strong id="metricMemory">0</strong><span>memory entries</span></div>
          </div>
          <div class="sidebar-footer">
            <div class="footer-avatar"><span class="material-symbols-outlined">bolt</span></div>
            <div class="footer-meta">
              <strong id="footerIdentity">CONNECT operator</strong>
              <span id="footerUptime">Runtime control plane ready</span>
            </div>
          </div>
        </section>
      </div>
    </aside>

    <main class="main-shell">
      <header class="topbar">
        <div class="topbar-left">
          <button class="mobile-toggle" id="sidebarToggle" aria-label="Toggle sidebar">
            <span class="material-symbols-outlined">menu</span>
          </button>
          <div class="topbar-title">
            <div class="eyebrow">Connect control plane</div>
            <h1 id="pageTitle">Connect AI Dashboard</h1>
            <div class="topbar-sub" id="topbarSubtext">Production dashboard backed by live runtime state, sessions, tools, integrations, workflows, and memory.</div>
          </div>
        </div>
        <div class="topbar-actions">
          <div class="search-shell">
            <span class="material-symbols-outlined">search</span>
            <input id="topSearchInput" type="text" placeholder="Search sessions, docs, workflows" />
          </div>
          <button class="top-action" id="nodeClientButton"><span class="material-symbols-outlined">smartphone</span><span>Node client</span></button>
          <button class="badge-btn" id="plusBadge">runtime idle</button>
          <button class="ghost-btn" id="newSessionButton">New session</button>
          <button class="link-btn" id="refreshButton">Refresh</button>
        </div>
      </header>

      <div class="main-scroll">
        <section class="hero-panel">
          <div class="hero-grid">
            <div class="hero-copy">
              <div class="eyebrow">Live operator interface</div>
              <h2>Use CONNECT through a real command center, not a fake placeholder shell.</h2>
              <p>Everything here is wired to the same runtime used by your local shell: real sessions, memory, integrations, workflows, node pairing, and live backend execution. The layout follows your reference, but it stays practical for production use and smaller screens.</p>
              <div class="hero-actions">
                <button class="chip-btn" data-prompt="Inspect the current workspace and tell me what to work on next.">Inspect workspace</button>
                <button class="chip-btn" data-prompt="Summarize the current runtime health and any missing configuration.">Check runtime health</button>
                <button class="chip-btn" data-prompt="Help me configure integrations for production.">Configure integrations</button>
                <button class="chip-btn" data-view-jump="docs">Open docs</button>
              </div>
            </div>
            <div class="hero-side">
              <article class="stat-card">
                <span class="material-symbols-outlined">neurology</span>
                <strong id="heroProvider">-</strong>
                <span>active provider</span>
              </article>
              <article class="stat-card">
                <span class="material-symbols-outlined">forum</span>
                <strong id="heroSessions">0</strong>
                <span>live sessions</span>
              </article>
              <article class="stat-card">
                <span class="material-symbols-outlined">dns</span>
                <strong id="heroServices">0</strong>
                <span>running services</span>
              </article>
              <article class="stat-card">
                <span class="material-symbols-outlined">hub</span>
                <strong id="heroIntegrations">0</strong>
                <span>connected integrations</span>
              </article>
            </div>
          </div>
        </section>

        <section class="surface-card view-section" data-view-section="chat">
          <div class="surface-head">
            <div>
              <div class="subtle">Conversation surface</div>
              <h2>Chat with CONNECT AI</h2>
            </div>
            <span class="status-badge" id="chatBadge">idle</span>
          </div>
          <div class="chat-layout">
            <div class="chat-shell">
              <div class="chat-toolbar">
                <select id="sessionSelect" class="select"></select>
                <button class="secondary-btn" id="clearComposerButton">Clear draft</button>
              </div>
              <div id="chatThread" class="chat-thread">
                <div class="empty-state">No session history yet. Start with a real operator request and CONNECT will respond here using the same backend runtime used by the shell.</div>
              </div>
              <div class="composer">
                <div class="chat-input-wrap">
                  <textarea id="askInput" placeholder="Ask CONNECT to code, inspect, route, search, configure, automate, or message."></textarea>
                </div>
                <div class="composer-actions">
                  <div class="tiny">Responses are stored in the selected session and reflected into runtime memory and history.</div>
                  <div style="display:flex; gap:10px; flex-wrap:wrap;">
                    <button class="secondary-btn" id="refreshChatButton">Refresh thread</button>
                    <button class="primary-btn" id="askButton">Send to CONNECT</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="right-stack">
              <div class="info-card">
                <div class="subtle">Selected session</div>
                <div class="panel-title" id="selectedSessionTitle">No session</div>
                <div class="row-meta" id="selectedSessionMeta">Choose or create a session.</div>
              </div>
              <div class="info-card">
                <div class="subtle">Recent memory</div>
                <div id="memoryList" class="card-list"></div>
              </div>
              <div class="info-card">
                <div class="subtle">Gateway diagnostics</div>
                <pre class="json-box" id="statusOutput">Loading...</pre>
              </div>
            </div>
          </div>
        </section>

        <section class="surface-card view-section hidden" data-view-section="integrations">
          <div class="surface-head">
            <div>
              <div class="subtle">Connectors</div>
              <h2>Integrations and delivery paths</h2>
            </div>
            <span class="status-badge" id="integrationBadge">0 configured</span>
          </div>
          <div id="integrationList" class="integration-grid"></div>
        </section>

        <section class="surface-card view-section hidden" data-view-section="sessions">
          <div class="surface-head">
            <div>
              <div class="subtle">Threads and memory</div>
              <h2>Sessions, activity, and recent context</h2>
            </div>
            <span class="status-badge" id="sessionBadge">0 sessions</span>
          </div>
          <div class="view-grid">
            <div class="info-card">
              <div class="subtle">Create session</div>
              <div class="session-form">
                <input id="newSessionName" class="field" placeholder="Session name" />
                <select id="newSessionProfile" class="field">
                  <option value="coding">coding</option>
                  <option value="messaging">messaging</option>
                  <option value="minimal">minimal</option>
                </select>
                <button class="primary-btn" id="createSessionButton">Create session</button>
              </div>
            </div>
            <div id="sessionList" class="card-list"></div>
          </div>
        </section>

        <section class="surface-card view-section hidden" data-view-section="workflows">
          <div class="surface-head">
            <div>
              <div class="subtle">Automation</div>
              <h2>Workflows and runnable routines</h2>
            </div>
            <span class="status-badge" id="workflowBadge">0 workflows</span>
          </div>
          <div id="workflowList" class="workflow-grid"></div>
        </section>

        <section class="surface-card view-section hidden" data-view-section="nodes">
          <div class="surface-head">
            <div>
              <div class="subtle">Devices and canvas</div>
              <h2>Nodes, pairing, and shared surface state</h2>
            </div>
            <span class="status-badge" id="nodeBadge">0 nodes</span>
          </div>
          <div class="view-grid">
            <div class="info-card">
              <div class="subtle">Paired nodes</div>
              <div id="nodeList" class="card-list"></div>
            </div>
            <div class="info-card">
              <div class="subtle">Canvas snapshot</div>
              <div id="canvasList" class="card-list"></div>
              <div class="doc-actions">
                <button class="secondary-btn" id="nodeClientInlineButton">Open node client</button>
              </div>
            </div>
          </div>
        </section>

        <section class="surface-card view-section hidden" data-view-section="docs">
          <div class="surface-head">
            <div>
              <div class="subtle">Operational guides</div>
              <h2>Docs and quick links</h2>
            </div>
            <span class="status-badge">reference</span>
          </div>
          <div class="docs-grid">
            <article class="doc-card">
              <div class="subtle">Guide</div>
              <h3>Installation</h3>
              <p>Install from the repo clone or from the raw GitHub installer, then verify the launcher with <code>connect --doctor</code>.</p>
              <div class="doc-actions">
                <button class="secondary-btn" data-prompt="Show me the correct CONNECT installation steps for this machine.">Ask CONNECT</button>
              </div>
            </article>
            <article class="doc-card">
              <div class="subtle">Guide</div>
              <h3>Authentication</h3>
              <p>Use Clerk-backed sign-in when auth is enabled. The dashboard honors the same local operator session and deployment mode.</p>
              <div class="doc-actions">
                <button class="secondary-btn" data-prompt="Explain how CONNECT auth works in local and cloud mode.">Ask CONNECT</button>
              </div>
            </article>
            <article class="doc-card">
              <div class="subtle">Guide</div>
              <h3>Runtime and tools</h3>
              <p>Sessions, memory, workflows, messaging, nodes, and canvas all route through the gateway runtime you are operating here.</p>
              <div class="doc-actions">
                <button class="secondary-btn" data-prompt="Summarize the CONNECT runtime and tool system.">Ask CONNECT</button>
              </div>
            </article>
            <article class="doc-card">
              <div class="subtle">Guide</div>
              <h3>Integrations</h3>
              <p>Configure GitHub, Telegram, Slack, Discord, and WhatsApp here, then use those messaging targets directly from sessions and workflows.</p>
              <div class="doc-actions">
                <button class="secondary-btn" data-view-jump="integrations">Open integrations</button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>

  <script>
    const state = {
      activeView: "chat",
      sessions: [],
      tools: [],
      workflows: [],
      memory: [],
      nodes: [],
      canvas: { cards: [] },
      integrations: {},
      status: {},
      activeSessionId: "",
      loadingAsk: false,
      searchTerm: "",
    };

    async function loadJson(url, options) {
      const res = await fetch(url, options);
      return await res.json();
    }

    function escapeHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function formatTime(value) {
      if (!value) return "";
      try {
        return new Date(value).toLocaleString();
      } catch {
        return String(value);
      }
    }

    function activeSession() {
      return state.sessions.find((item) => item.id === state.activeSessionId) || null;
    }

    function rowHtml(title, meta, extra) {
      return `<div class="row-card"><div class="row-title">${escapeHtml(title)}</div><div class="row-meta">${escapeHtml(meta)}</div>${extra ? `<div class="row-extra">${escapeHtml(extra)}</div>` : ""}</div>`;
    }

    function toolMessageHtml(entry) {
      const role = entry.role || "assistant";
      const cls = role === "user" ? "user" : role === "tool" ? "tool" : "assistant";
      const label = role === "user" ? "operator" : role === "tool" ? "tool" : "connect";
      return `
        <article class="message ${cls}">
          <div class="message-meta">
            <span>${escapeHtml(label)}</span>
            <span>${escapeHtml(formatTime(entry.ts || ""))}</span>
          </div>
          <div>${escapeHtml(entry.content || "")}</div>
        </article>`;
    }

    function integrationCard(kind, title, description, connected, fields) {
      const formFields = fields.map(field => `<input class="field" data-kind="${kind}" data-field="${field.name}" placeholder="${escapeHtml(field.placeholder)}" type="${field.type || "text"}" />`).join("");
      return `
        <div class="integration-card">
          <div class="integration-top">
            <div>
              <div class="subtle">connector</div>
              <h3>${escapeHtml(title)}</h3>
              <p>${escapeHtml(description)}</p>
            </div>
            <div class="${connected ? "status-ok" : "status-bad"}">${connected ? "Connected" : "Not connected"}</div>
          </div>
          <div class="integration-form">
            ${formFields}
            <button class="primary-btn" data-save-kind="${kind}">Save ${escapeHtml(title)}</button>
          </div>
        </div>`;
    }

    function openNodeClient() {
      window.location.href = "/node-client";
    }

    function closeSidebar() {
      document.body.classList.remove("sidebar-open");
    }

    function toggleSidebar() {
      document.body.classList.toggle("sidebar-open");
    }

    function applySearchToView() {
      const raw = String(state.searchTerm || "").trim().toLowerCase();
      if (!raw) return;
      const sessionMatch = state.sessions.some(item => `${item.name} ${item.id} ${item.profile}`.toLowerCase().includes(raw));
      const workflowMatch = state.workflows.some(item => `${item.name || ""} ${item.description || ""}`.toLowerCase().includes(raw));
      const integrationMatch = ["github", "telegram", "slack", "discord", "whatsapp"].some(item => item.includes(raw));
      if (sessionMatch) {
        setView("sessions");
        return;
      }
      if (workflowMatch) {
        setView("workflows");
        return;
      }
      if (integrationMatch) {
        setView("integrations");
        return;
      }
      setView("docs");
    }

    function renderShellStatus() {
      const status = state.status || {};
      const currentUser = status.current_user || {};
      const services = Object.values(status.services || {}).filter(item => item && item.running);
      const connectedIntegrations = Object.values(state.integrations || {}).filter(item => item && item.connected).length;
      document.getElementById("sidebarMode").textContent = status.deployment_mode || "local";
      document.getElementById("sidebarLive").textContent = services.length ? `${services.length} live` : "idle";
      document.getElementById("sidebarProvider").textContent = status.provider || "none";
      document.getElementById("sidebarUser").textContent = currentUser.email || currentUser.user_id || "guest";
      document.getElementById("metricTools").textContent = String(status.tool_count || 0);
      document.getElementById("metricServices").textContent = String(services.length);
      document.getElementById("metricMemory").textContent = String(status.memory_entries || 0);
      document.getElementById("heroProvider").textContent = status.provider || "none";
      document.getElementById("heroSessions").textContent = String(state.sessions.length);
      document.getElementById("heroServices").textContent = String(services.length);
      document.getElementById("heroIntegrations").textContent = String(connectedIntegrations);
      document.getElementById("plusBadge").textContent = services.length ? `${services.length} live services` : "runtime idle";
      document.getElementById("topbarSubtext").textContent = currentUser.email
        ? `Signed in as ${currentUser.email}. Runtime-backed operator dashboard with sessions, tools, memory, integrations, workflows, and node state.`
        : "Runtime-backed operator dashboard with sessions, tools, memory, integrations, workflows, and node state.";
      document.getElementById("footerIdentity").textContent = currentUser.email || currentUser.user_id || "CONNECT operator";
      document.getElementById("footerUptime").textContent = status.provider_error ? `Provider issue: ${status.provider_error}` : `${services.length} live services · ${status.memory_entries || 0} memory entries`;
    }

    function renderSessions() {
      const raw = String(state.searchTerm || "").trim().toLowerCase();
      const rows = raw
        ? state.sessions.filter(s => `${s.name} ${s.id} ${s.profile} ${s.status}`.toLowerCase().includes(raw))
        : state.sessions;
      const target = document.getElementById("sessionList");
      document.getElementById("navSessionCount").textContent = String(state.sessions.length);
      document.getElementById("sessionBadge").textContent = `${state.sessions.length} sessions`;
      target.innerHTML = rows.length
        ? rows.map(s => `
            <button class="nav-btn ${s.id === state.activeSessionId ? "active" : ""}" data-session-pick="${escapeHtml(s.id)}">
              <div class="nav-main">
                <div class="nav-icon"><span class="material-symbols-outlined">chat_bubble</span></div>
                <div class="nav-copy">
                  <strong>${escapeHtml(s.name)}</strong>
                  <span>${escapeHtml(s.profile)} · ${escapeHtml(s.status)}</span>
                </div>
              </div>
              <div class="nav-count">${escapeHtml(s.id)}</div>
            </button>`).join("")
        : rowHtml("No sessions", raw ? "No sessions match the current search." : "Create one by asking CONNECT a question.");

      target.querySelectorAll("[data-session-pick]").forEach(button => {
        button.onclick = async () => {
          state.activeSessionId = button.getAttribute("data-session-pick") || "";
          syncSessionSelect();
          await loadChat();
          setView("chat");
        };
      });
    }

    function renderMemory(items) {
      const target = document.getElementById("memoryList");
      target.innerHTML = items.length
        ? items.slice().reverse().map(i => rowHtml(i.kind || "memory", i.content || "", formatTime(i.ts || ""))).join("")
        : rowHtml("No memory yet", "Recent context will appear here.");
    }

    function renderChat(items) {
      const target = document.getElementById("chatThread");
      document.getElementById("navChatCount").textContent = String(items.length);
      document.getElementById("chatBadge").textContent = state.loadingAsk ? "running" : `${items.length} msgs`;
      target.innerHTML = items.length
        ? items.map(toolMessageHtml).join("")
        : `<div class="empty-state">No chat yet. Start with a real operator request and CONNECT will answer here in the selected session.</div>`;
      target.scrollTop = target.scrollHeight;

      const current = activeSession();
      document.getElementById("selectedSessionTitle").textContent = current ? current.name : "No session selected";
      document.getElementById("selectedSessionMeta").textContent = current
        ? `${current.profile} · ${current.status} · updated ${formatTime(current.updated_at)}`
        : "Choose or create a session.";
    }

    function renderNodes(items) {
      const target = document.getElementById("nodeList");
      document.getElementById("nodeBadge").textContent = `${items.length} nodes`;
      document.getElementById("navNodeCount").textContent = String(items.length);
      target.innerHTML = items.length
        ? items.map(n => rowHtml(`${n.name} · ${n.node_id}`, `${n.platform} · last seen ${formatTime(n.last_seen)}`, Object.keys(n.location || {}).length ? JSON.stringify(n.location) : "")).join("")
        : rowHtml("No paired nodes", "Pair a node from the mobile client when ready.");
    }

    function renderCanvas(snapshot) {
      const cards = snapshot.cards || [];
      document.getElementById("canvasList").innerHTML = cards.length
        ? cards.slice().reverse().map(c => rowHtml(c.title || c.id, c.kind || "note", c.content || "")).join("")
        : rowHtml("Canvas empty", "Use canvas tools to publish cards.");
    }

    function renderWorkflows() {
      const raw = String(state.searchTerm || "").trim().toLowerCase();
      const rows = raw
        ? state.workflows.filter(item => `${item.name || ""} ${item.description || ""}`.toLowerCase().includes(raw))
        : state.workflows;
      const target = document.getElementById("workflowList");
      document.getElementById("navWorkflowCount").textContent = String(state.workflows.length);
      document.getElementById("workflowBadge").textContent = `${state.workflows.length} workflows`;
      if (!rows.length) {
        target.innerHTML = rowHtml("No workflows", raw ? "No workflows match the current search." : "Create workflow files in the workspace to make them runnable from here.");
        return;
      }
      target.innerHTML = rows.map(item => `
        <article class="workflow-card">
          <div class="subtle">workflow</div>
          <h3>${escapeHtml(item.name || "unnamed")}</h3>
          <p>${escapeHtml(item.description || "No description available.")}</p>
          <div class="workflow-actions">
            <button class="primary-btn" data-run-workflow="${escapeHtml(item.name || "")}">Run workflow</button>
          </div>
        </article>`).join("");

      target.querySelectorAll("[data-run-workflow]").forEach(button => {
        button.onclick = async () => {
          const name = button.getAttribute("data-run-workflow");
          if (!name) return;
          const original = button.textContent;
          button.textContent = "Running...";
          const result = await loadJson("/api/workflows/run", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({name, session_id: state.activeSessionId || ""})
          });
          button.textContent = result.ok ? "Ran workflow" : "Run failed";
          setTimeout(() => { button.textContent = original; }, 1200);
          await refresh();
        };
      });
    }

    function renderDocs() {
      document.querySelectorAll("[data-prompt]").forEach(button => {
        button.onclick = () => {
          const prompt = button.getAttribute("data-prompt") || "";
          document.getElementById("askInput").value = prompt;
          setView("chat");
          document.getElementById("askInput").focus();
        };
      });
      document.querySelectorAll("[data-view-jump]").forEach(button => {
        button.onclick = () => setView(button.getAttribute("data-view-jump") || "chat");
      });
    }

    function renderIntegrations(snapshot) {
      state.integrations = snapshot || {};
      const connectedCount = Object.values(snapshot || {}).filter(item => item && item.connected).length;
      document.getElementById("navIntegrationCount").textContent = String(connectedCount);
      document.getElementById("integrationBadge").textContent = `${connectedCount} configured`;
      document.getElementById("integrationList").innerHTML = [
        integrationCard("github", "GitHub", "Store a personal token for repository operations.", !!snapshot.github?.connected, [
          {name: "token", placeholder: "GitHub token", type: "password"}
        ]),
        integrationCard("telegram", "Telegram", "Bot token plus default chat id for send and receive.", !!snapshot.telegram?.connected, [
          {name: "bot_token", placeholder: "Telegram bot token", type: "password"},
          {name: "default_chat_id", placeholder: "Default chat id"}
        ]),
        integrationCard("slack_webhook", "Slack webhook", "Simple outbound Slack delivery by named webhook.", !!snapshot.slack_webhooks?.connected, [
          {name: "name", placeholder: "Webhook name"},
          {name: "webhook_url", placeholder: "Slack webhook URL", type: "password"}
        ]),
        integrationCard("slack_bot", "Slack bot", "Bidirectional bot mode with bot token and signing secret.", !!snapshot.slack_bot?.connected, [
          {name: "bot_token", placeholder: "Slack bot token", type: "password"},
          {name: "signing_secret", placeholder: "Slack signing secret", type: "password"}
        ]),
        integrationCard("discord", "Discord", "Send messages through named Discord webhooks.", !!snapshot.discord?.connected, [
          {name: "name", placeholder: "Webhook name"},
          {name: "webhook_url", placeholder: "Discord webhook URL", type: "password"}
        ]),
        integrationCard("whatsapp", "WhatsApp", "Twilio WhatsApp connector for inbound and outbound delivery.", !!snapshot.whatsapp?.connected, [
          {name: "account_sid", placeholder: "Twilio account SID"},
          {name: "auth_token", placeholder: "Twilio auth token", type: "password"},
          {name: "from_number", placeholder: "whatsapp:+1234567890"}
        ])
      ].join("");

      document.querySelectorAll("[data-save-kind]").forEach(button => {
        button.onclick = async () => {
          const kind = button.getAttribute("data-save-kind");
          const payload = {};
          document.querySelectorAll(`[data-kind="${kind}"]`).forEach(field => {
            payload[field.getAttribute("data-field")] = field.value;
          });
          const original = button.textContent;
          button.textContent = "Saving...";
          const result = await loadJson("/api/integrations", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({kind, payload})
          });
          button.textContent = result.ok ? "Saved" : "Save failed";
          setTimeout(() => { button.textContent = original; }, 1200);
          await refresh();
        };
      });
    }

    function syncSessionSelect() {
      const select = document.getElementById("sessionSelect");
      select.innerHTML = state.sessions.map(session => `<option value="${escapeHtml(session.id)}">${escapeHtml(session.name)} · ${escapeHtml(session.profile)}</option>`).join("");
      if (!state.activeSessionId && state.sessions[0]) {
        state.activeSessionId = state.sessions[0].id;
      }
      select.value = state.activeSessionId || "";
      select.onchange = async () => {
        state.activeSessionId = select.value;
        await loadChat();
      };
    }

    function setView(view) {
      state.activeView = view;
      document.querySelectorAll("[data-view-section]").forEach(section => {
        section.classList.toggle("hidden", section.getAttribute("data-view-section") !== view);
      });
      document.querySelectorAll("[data-view]").forEach(button => {
        button.classList.toggle("active", button.getAttribute("data-view") === view);
      });
      closeSidebar();
    }

    async function loadChat() {
      if (!state.activeSessionId) {
        renderChat([]);
        renderMemory([]);
        return;
      }
      const [historyRows, memoryRows] = await Promise.all([
        loadJson(`/api/session-history?session_id=${encodeURIComponent(state.activeSessionId)}&limit=40`),
        loadJson(`/api/memory?session_id=${encodeURIComponent(state.activeSessionId)}&limit=12`)
      ]);
      state.memory = memoryRows.items || [];
      renderChat(historyRows.items || []);
      renderMemory(state.memory);
      document.getElementById("statusOutput").textContent = JSON.stringify(state.status, null, 2);
    }

    async function createSession() {
      const name = document.getElementById("newSessionName").value.trim() || `session-${Date.now()}`;
      const profile = document.getElementById("newSessionProfile").value || "coding";
      const result = await loadJson("/api/sessions/new", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({name, profile})
      });
      if (result.ok && result.session_id) {
        state.activeSessionId = result.session_id;
        document.getElementById("newSessionName").value = "";
        await refresh();
        setView("chat");
      }
    }

    async function refresh() {
      const [status, toolRows, sessionRows, nodeRows, canvasSnapshot, integrationRows, workflowRows] = await Promise.all([
        loadJson("/api/status"),
        loadJson("/api/tools"),
        loadJson("/api/sessions"),
        loadJson("/api/nodes"),
        loadJson("/api/canvas"),
        loadJson("/api/integrations"),
        loadJson("/api/workflows")
      ]);
      state.status = status || {};
      state.tools = toolRows.items || [];
      state.sessions = sessionRows.items || [];
      state.nodes = nodeRows.items || [];
      state.canvas = canvasSnapshot || { cards: [] };
      state.workflows = workflowRows.items || [];
      if (!state.activeSessionId && state.sessions[0]) {
        state.activeSessionId = state.sessions[0].id;
      } else if (state.activeSessionId && !state.sessions.some(session => session.id === state.activeSessionId)) {
        state.activeSessionId = (state.sessions[0] || {}).id || "";
      }
      renderIntegrations(integrationRows);
      renderShellStatus();
      syncSessionSelect();
      renderSessions();
      renderNodes(state.nodes);
      renderCanvas(state.canvas);
      renderWorkflows();
      renderDocs();
      await loadChat();
    }

    async function ask() {
      if (state.loadingAsk) return;
      const input = document.getElementById("askInput");
      const content = input.value.trim();
      if (!content) return;
      state.loadingAsk = true;
      document.getElementById("chatBadge").textContent = "running";
      const thread = document.getElementById("chatThread");
      thread.insertAdjacentHTML("beforeend", `<div class="typing" id="typingBubble"><span></span><span></span><span></span></div>`);
      thread.scrollTop = thread.scrollHeight;
      const result = await loadJson("/api/ask", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({content, session_id: state.activeSessionId || ""})
      });
      const typing = document.getElementById("typingBubble");
      if (typing) typing.remove();
      input.value = "";
      state.loadingAsk = false;
      if (result.session_id) {
        state.activeSessionId = result.session_id;
      }
      await refresh();
    }

    document.getElementById("askButton").onclick = ask;
    document.getElementById("refreshButton").onclick = refresh;
    document.getElementById("refreshChatButton").onclick = loadChat;
    document.getElementById("clearComposerButton").onclick = () => { document.getElementById("askInput").value = ""; };
    document.getElementById("newSessionButton").onclick = createSession;
    document.getElementById("createSessionButton").onclick = createSession;
    document.getElementById("sidebarToggle").onclick = toggleSidebar;
    document.getElementById("sidebarOverlay").onclick = closeSidebar;
    document.getElementById("nodeClientButton").onclick = openNodeClient;
    document.getElementById("nodeClientInlineButton").onclick = openNodeClient;
    document.getElementById("askInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) ask();
    });
    document.getElementById("topSearchInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        state.searchTerm = event.target.value || "";
        applySearchToView();
        renderSessions();
        renderWorkflows();
      }
    });
    document.querySelectorAll("[data-view]").forEach(button => {
      button.onclick = () => setView(button.getAttribute("data-view") || "chat");
    });
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>"""


class DashboardServer:
    def __init__(self, runtime: AgentRuntime, host: str = "127.0.0.1", port: int = 18890):
        self.runtime = runtime
        self.host = host
        self.port = port

    def make_handler(self):
        runtime = self.runtime

        class Handler(BaseHTTPRequestHandler):
            def _auth_required(self) -> bool:
                return runtime.auth.requires_auth(runtime.config.deployment_mode)

            def _request_authenticated(self) -> bool:
                return runtime.auth.request_authenticated(self.headers)

            def _redirect(self, location: str):
                self.send_response(302)
                self.send_header("Location", location)
                self.end_headers()

            def _send_json(self, payload: Dict[str, Any], status: int = 200):
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_html(self, html: str):
                raw = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args):
                return

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/auth/login":
                    next_path = parse_qs(parsed.query).get("next", ["/"])[0]
                    self._send_html(runtime.auth.render_signin_html("/auth/clerk/callback", next_path))
                    return
                if parsed.path == "/":
                    if self._auth_required() and not self._request_authenticated():
                        self._redirect("/auth/login?next=/")
                        return
                    self._send_html(render_dashboard_html())
                    return
                if parsed.path == "/node-client":
                    if self._auth_required() and not self._request_authenticated():
                        self._redirect("/auth/login?next=/node-client")
                        return
                    self._send_html(render_node_client_html())
                    return
                if self._auth_required() and parsed.path.startswith("/api/") and parsed.path not in {"/api/node/manifest"} and not self._request_authenticated():
                    self._send_json({"ok": False, "error": "authentication required"}, status=401)
                    return
                if parsed.path == "/api/status":
                    self._send_json(runtime.gateway_status())
                    return
                if parsed.path == "/api/tools":
                    self._send_json({"items": runtime.catalog.list()})
                    return
                if parsed.path == "/api/sessions":
                    self._send_json({"items": runtime.sessions.list()})
                    return
                if parsed.path == "/api/session-history":
                    query = parse_qs(parsed.query)
                    session_id = query.get("session_id", [""])[0]
                    limit = int(query.get("limit", ["20"])[0])
                    self._send_json({"items": runtime.sessions.history(session_id, limit) if session_id else []})
                    return
                if parsed.path == "/api/memory":
                    query = parse_qs(parsed.query)
                    session_id = query.get("session_id", [""])[0]
                    limit = int(query.get("limit", ["10"])[0])
                    self._send_json({"items": runtime.memory.get_recent(session_id, limit)})
                    return
                if parsed.path == "/api/nodes":
                    self._send_json({"items": runtime.nodes.list_nodes()})
                    return
                if parsed.path == "/api/node/manifest":
                    self._send_json(runtime.node_manifest())
                    return
                if parsed.path == "/api/canvas":
                    self._send_json(runtime.canvas.snapshot())
                    return
                if parsed.path == "/api/workflows":
                    self._send_json({"items": runtime.workflows.list_workflows()})
                    return
                if parsed.path == "/api/integrations":
                    self._send_json(runtime.integration_snapshot())
                    return
                self._send_json({"error": "not found"}, status=404)

            def do_POST(self):
                if self.path not in {
                    "/api/ask",
                    "/api/sessions/new",
                    "/api/node/pair",
                    "/api/node/register",
                    "/api/node/screen",
                    "/api/node/camera",
                    "/api/node/location",
                    "/api/workflows/run",
                    "/api/webhooks/trigger",
                    "/api/slack/events",
                    "/api/whatsapp/inbound",
                    "/api/integrations",
                    "/auth/clerk/callback",
                }:
                    self._send_json({"error": "not found"}, status=404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw_body = self.rfile.read(length)
                    content_type = (self.headers.get("Content-Type", "") or "").lower()
                    if "application/json" in content_type:
                        payload = json.loads(raw_body.decode("utf-8") or "{}")
                    else:
                        payload = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(raw_body.decode("utf-8")).items()}
                    if self.path == "/auth/clerk/callback":
                        state = runtime.auth.complete_login(str(payload.get("token", "")), str(payload.get("email", "")))
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Set-Cookie", f"connect_session={state.local_session_id}; Path=/; HttpOnly; SameSite=Lax")
                        raw = json.dumps({"ok": True, "next_path": str(payload.get("next_path", "/"))}).encode("utf-8")
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                        return
                    if self._auth_required() and self.path not in {"/api/slack/events", "/api/whatsapp/inbound"} and not self._request_authenticated():
                        self._send_json({"ok": False, "error": "authentication required"}, status=401)
                        return
                    if self.path == "/api/ask":
                        session_id = payload.get("session_id") or runtime.ensure_default_session()
                        result = runtime.run_turn(session_id, str(payload.get("content", "")).strip())
                        self._send_json(result)
                        return
                    if self.path == "/api/sessions/new":
                        session = runtime.sessions.create(
                            name=str(payload.get("name", "default") or "default"),
                            profile=str(payload.get("profile", "coding") or "coding"),
                            target=str(payload.get("target", "") or ""),
                        )
                        self._send_json({"ok": True, "session_id": session.id, "name": session.name, "profile": session.profile})
                        return
                    if self.path == "/api/node/pair":
                        self._send_json(runtime.nodes.create_pairing(str(payload.get("label", "mobile"))))
                        return
                    if self.path == "/api/node/register":
                        self._send_json(runtime.nodes.register_node(payload["pair_code"], payload["pair_secret"], payload.get("node_name", "mobile"), payload.get("platform", "unknown")))
                        return
                    if self.path == "/api/node/screen":
                        runtime.nodes.update_screen(payload["node_id"], payload.get("screen", ""))
                        self._send_json({"ok": True})
                        return
                    if self.path == "/api/node/camera":
                        runtime.nodes.update_camera(payload["node_id"], payload.get("camera", ""))
                        self._send_json({"ok": True})
                        return
                    if self.path == "/api/node/location":
                        runtime.nodes.update_location(payload["node_id"], payload.get("location", {}))
                        self._send_json({"ok": True})
                        return
                    if self.path == "/api/workflows/run":
                        session_id = payload.get("session_id") or runtime.ensure_default_session()
                        self._send_json(runtime.workflows.run_named(payload["name"], payload.get("payload", {}), session_id=session_id))
                        return
                    if self.path == "/api/webhooks/trigger":
                        if runtime.config.webhook_bearer_token and not runtime.auth.validate_bearer(self.headers.get("Authorization", "")):
                            self._send_json({"ok": False, "error": "invalid webhook bearer token"}, status=401)
                            return
                        session_id = payload.get("session_id") or runtime.ensure_default_session()
                        self._send_json(runtime.workflows.trigger_webhook(payload["name"], payload.get("payload", {}), session_id=session_id))
                        return
                    if self.path == "/api/slack/events":
                        if runtime.slack_bot:
                            signature = self.headers.get("X-Slack-Signature", "")
                            timestamp = self.headers.get("X-Slack-Request-Timestamp", "")
                            if signature and timestamp and not runtime.slack_bot.verify_signature(timestamp, raw_body, signature):
                                self._send_json({"ok": False, "error": "invalid slack signature"}, status=401)
                                return
                        self._send_json(runtime.handle_slack_event(payload))
                        return
                    if self.path == "/api/whatsapp/inbound":
                        self._send_json(runtime.handle_whatsapp_inbound(payload))
                        return
                    if self.path == "/api/integrations":
                        self._send_json(runtime.save_integration(str(payload.get("kind", "")).strip(), payload.get("payload", {}) or {}))
                        return
                    self._send_json({"error": "not found"}, status=404)
                    return
                except Exception as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=500)

        return Handler

    def serve(self):
        httpd = ThreadingHTTPServer((self.host, self.port), self.make_handler())
        self.runtime.set_service_state("dashboard", True, self.host, self.port)
        print(f"Dashboard listening on http://{self.host}:{self.port}")
        try:
            httpd.serve_forever()
        finally:
            self.runtime.set_service_state("dashboard", False, self.host, self.port)
