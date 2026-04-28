from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from gateway_runtime.node_client import render_node_client_html
from gateway_runtime.runtime import AgentRuntime


def render_dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Connect AI</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
--bg:#0a0b0f;
--bg2:#111318;
--bg3:#181b22;
--bg4:#1e2229;
--border:#ffffff12;
--border2:#ffffff20;
--text:#e8eaf0;
--text2:#8b90a0;
--text3:#555b6a;
--accent:#27f3a9;
--accent2:#14c98a;
--accent3:#7ff7cb;
--green:#10d9a0;
--amber:#f59e0b;
--red:#ef4444;
--blue:#3b82f6;
--pink:#ec4899;
--font-head:'Syne',sans-serif;
--font-body:'DM Sans',sans-serif;
--font-mono:'DM Mono',monospace;
--sidebar:240px;
--rad:10px;
--rad2:14px;
}
body{background:var(--bg);color:var(--text);font-family:var(--font-body);font-size:14px;display:flex;height:100vh;overflow:hidden}
button,input,select,textarea{font:inherit}
button{cursor:pointer}
.sidebar{width:var(--sidebar);min-width:var(--sidebar);background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:10;transition:transform .25s ease}
.sidebar-logo{padding:20px 18px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--border)}
.logo-mark{width:32px;height:32px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:#fff;font-family:var(--font-head);font-size:13px;font-weight:800}
.logo-text{font-family:var(--font-head);font-size:17px;font-weight:700;color:var(--text);letter-spacing:-0.3px}
.logo-badge{font-size:9px;background:#ffffff15;color:var(--text2);padding:2px 6px;border-radius:20px;font-family:var(--font-mono);border:1px solid var(--border2)}
.sidebar-section{padding:10px 10px 4px;font-size:10px;font-weight:600;letter-spacing:1.2px;color:var(--text3);text-transform:uppercase;font-family:var(--font-head)}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:var(--rad);margin:1px 8px;cursor:pointer;color:var(--text2);font-size:13.5px;font-weight:400;transition:all .15s;position:relative}
.nav-item:hover{background:var(--bg3);color:var(--text)}
.nav-item.active{background:linear-gradient(90deg,#6c63ff18,#6c63ff08);color:var(--text);border-left:2px solid var(--accent)}
.nav-item.active .nav-icon{color:var(--accent)}
.nav-icon{width:16px;height:16px;flex-shrink:0;opacity:.8;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-family:var(--font-mono)}
.nav-badge{margin-left:auto;background:var(--accent);color:white;font-size:10px;padding:1px 6px;border-radius:20px;font-family:var(--font-mono)}
.nav-badge.green{background:var(--green);color:#000}
.nav-badge.amber{background:var(--amber);color:#000}
.sidebar-divider{height:1px;background:var(--border);margin:8px 12px}
.sidebar-bottom{margin-top:auto;border-top:1px solid var(--border);padding:10px}
.user-card{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:var(--rad);cursor:pointer;transition:background .15s}
.user-card:hover{background:var(--bg3)}
.avatar{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--pink));display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:white;flex-shrink:0}
.user-info{flex:1;min-width:0}
.user-name{font-size:13px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.user-plan{font-size:11px;color:var(--text3)}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;background:var(--bg)}
.topbar{height:52px;border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 20px;gap:12px;background:var(--bg);flex-shrink:0}
.topbar-title{font-family:var(--font-head);font-size:16px;font-weight:600;color:var(--text)}
.topbar-sub{font-size:13px;color:var(--text3);margin-left:2px}
.topbar-spacer{flex:1}
.tb-btn{display:flex;align-items:center;gap:7px;padding:6px 12px;border-radius:var(--rad);border:1px solid var(--border2);background:transparent;color:var(--text2);font-size:13px;font-family:var(--font-body);cursor:pointer;transition:all .15s}
.tb-btn:hover{border-color:var(--border2);background:var(--bg3);color:var(--text)}
.tb-btn.primary{background:var(--accent);border-color:var(--accent);color:white;font-weight:500}
.tb-btn.primary:hover{background:var(--accent2)}
.status-dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 6px #10d9a060}
.content{flex:1;overflow-y:auto;overflow-x:hidden}
.content::-webkit-scrollbar{width:4px}
.content::-webkit-scrollbar-track{background:transparent}
.content::-webkit-scrollbar-thumb{background:var(--border2);border-radius:10px}
.view{display:none;padding:24px;height:100%}
.view.active{display:flex;flex-direction:column}
.chat-view{padding:0 !important;flex-direction:row !important}
.chat-container{flex:1;display:flex;flex-direction:column;height:100%}
.chat-header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;flex-shrink:0}
.chat-model-pill{display:flex;align-items:center;gap:7px;padding:5px 12px;background:var(--bg3);border:1px solid var(--border2);border-radius:20px;cursor:pointer;transition:all .15s;font-size:12.5px;color:var(--text)}
.chat-model-pill:hover{border-color:var(--accent)}
.model-dot{width:7px;height:7px;border-radius:50%;background:var(--green)}
.chat-messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:18px}
.chat-messages::-webkit-scrollbar{width:4px}
.chat-messages::-webkit-scrollbar-thumb{background:var(--border);border-radius:10px}
.msg{display:flex;gap:12px;animation:fadeup .25s ease}
@keyframes fadeup{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg-avatar{width:30px;height:30px;border-radius:8px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700}
.msg-avatar.user{background:linear-gradient(135deg,var(--accent),var(--pink));color:white}
.msg-avatar.ai{background:linear-gradient(135deg,var(--green),var(--blue));color:#000}
.msg-body{flex:1;min-width:0}
.msg-meta{display:flex;align-items:center;gap:8px;margin-bottom:5px;flex-wrap:wrap}
.msg-name{font-size:12.5px;font-weight:600;color:var(--text)}
.msg-time{font-size:11px;color:var(--text3)}
.msg-content{font-size:14px;line-height:1.65;color:var(--text2);word-break:break-word}
.msg-content code{font-family:var(--font-mono);background:var(--bg3);padding:1px 6px;border-radius:5px;font-size:12.5px;color:var(--accent3);border:1px solid var(--border)}
.msg-content pre{background:var(--bg3);border:1px solid var(--border);border-radius:var(--rad);padding:14px;margin:10px 0;font-family:var(--font-mono);font-size:12.5px;overflow-x:auto;color:var(--text);white-space:pre-wrap}
.msg-actions{display:flex;gap:6px;margin-top:7px;opacity:0;transition:opacity .15s}
.msg:hover .msg-actions{opacity:1}
.msg-action-btn{padding:3px 8px;border:1px solid var(--border);border-radius:6px;background:transparent;color:var(--text3);font-size:11px;cursor:pointer;transition:all .15s;font-family:var(--font-body)}
.msg-action-btn:hover{border-color:var(--accent);color:var(--accent)}
.typing-indicator{display:flex;gap:4px;align-items:center;padding:4px 0}
.typing-dot{width:5px;height:5px;border-radius:50%;background:var(--text3);animation:bounce .8s infinite}
.typing-dot:nth-child(2){animation-delay:.15s}
.typing-dot:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
.chat-input-wrap{padding:16px 20px;border-top:1px solid var(--border);flex-shrink:0;background:var(--bg)}
.chat-input-box{background:var(--bg3);border:1px solid var(--border2);border-radius:var(--rad2);padding:12px 14px;display:flex;align-items:flex-end;gap:10px;transition:border-color .15s}
.chat-input-box:focus-within{border-color:var(--accent)}
#chat-input{flex:1;background:transparent;border:none;outline:none;color:var(--text);font-family:var(--font-body);font-size:14px;resize:none;max-height:140px;min-height:22px;line-height:1.5}
#chat-input::placeholder{color:var(--text3)}
.send-btn{width:34px;height:34px;background:var(--accent);border:none;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s;color:#fff}
.send-btn:hover{background:var(--accent2);transform:scale(1.04)}
.send-btn:disabled{opacity:.4;cursor:not-allowed}
.chat-tools{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.chat-tool-btn{display:flex;align-items:center;gap:5px;padding:4px 10px;border:1px solid var(--border);border-radius:6px;background:transparent;color:var(--text3);font-size:12px;cursor:pointer;transition:all .15s;font-family:var(--font-body)}
.chat-tool-btn:hover{border-color:var(--border2);color:var(--text);background:var(--bg4)}
.chat-history-panel{width:220px;border-right:1px solid var(--border);display:flex;flex-direction:column;background:var(--bg2);flex-shrink:0}
.chat-hist-header{padding:14px 14px 10px;font-family:var(--font-head);font-size:13px;font-weight:600;color:var(--text);display:flex;align-items:center;justify-content:space-between}
.new-chat-btn{width:24px;height:24px;background:var(--accent);border:none;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s;color:#fff;font-size:14px}
.new-chat-btn:hover{background:var(--accent2)}
.hist-search{margin:0 10px 10px;position:relative}
.hist-search input{width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:7px;padding:7px 10px 7px 30px;color:var(--text);font-family:var(--font-body);font-size:12.5px;outline:none}
.hist-search input::placeholder{color:var(--text3)}
.hist-search input:focus{border-color:var(--accent)}
.hist-search-icon{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--text3);width:13px;height:13px;font-size:12px}
.hist-list{flex:1;overflow-y:auto;padding:0 8px}
.hist-list::-webkit-scrollbar{width:3px}
.hist-list::-webkit-scrollbar-thumb{background:var(--border)}
.hist-group-label{font-size:10px;letter-spacing:.8px;text-transform:uppercase;color:var(--text3);padding:8px 6px 4px;font-weight:600;font-family:var(--font-head)}
.hist-item{padding:8px 8px;border-radius:8px;cursor:pointer;transition:background .15s;margin-bottom:1px}
.hist-item:hover{background:var(--bg3)}
.hist-item.active{background:#6c63ff18}
.hist-item-title{font-size:12.5px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:400}
.hist-item-meta{font-size:11px;color:var(--text3);margin-top:2px}
.page-header{margin-bottom:22px}
.page-title{font-family:var(--font-head);font-size:22px;font-weight:700;color:var(--text);letter-spacing:-0.5px}
.page-sub{font-size:14px;color:var(--text2);margin-top:4px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rad2);padding:18px;transition:border-color .15s}
.card:hover{border-color:var(--border2)}
.card-sm{padding:14px}
.card-title{font-family:var(--font-head);font-size:14px;font-weight:600;color:var(--text);margin-bottom:4px}
.card-sub{font-size:12.5px;color:var(--text3)}
.stat-num{font-family:var(--font-head);font-size:28px;font-weight:700;color:var(--text);letter-spacing:-1px;margin:8px 0 4px}
.stat-trend{font-size:12px;display:flex;align-items:center;gap:4px}
.trend-up{color:var(--green)}
.trend-down{color:var(--red)}
.badge{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:500}
.badge-green{background:#10d9a018;color:var(--green);border:1px solid #10d9a030}
.badge-amber{background:#f59e0b18;color:var(--amber);border:1px solid #f59e0b30}
.badge-red{background:#ef444418;color:var(--red);border:1px solid #ef444430}
.badge-blue{background:#3b82f618;color:var(--blue);border:1px solid #3b82f630}
.badge-purple{background:#6c63ff18;color:var(--accent3);border:1px solid #6c63ff30}
.badge-dot{width:5px;height:5px;border-radius:50%;background:currentColor}
.model-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rad2);padding:16px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.model-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--accent),var(--accent2));opacity:0;transition:opacity .2s}
.model-card:hover{border-color:var(--accent);transform:translateY(-1px)}
.model-card:hover::before{opacity:1}
.model-card.active{border-color:var(--accent)}
.model-card.active::before{opacity:1}
.model-logo{width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:13px;margin-bottom:10px;background:#ffffff0e;color:var(--accent3);font-family:var(--font-mono)}
.model-name{font-family:var(--font-head);font-size:14px;font-weight:600;color:var(--text);margin-bottom:3px}
.model-desc{font-size:12px;color:var(--text3);line-height:1.5;margin-bottom:10px}
.model-tags{display:flex;flex-wrap:wrap;gap:5px}
.toggle{width:36px;height:20px;background:var(--bg4);border-radius:10px;cursor:pointer;position:relative;transition:background .2s;border:1px solid var(--border);flex-shrink:0}
.toggle.on{background:var(--accent);border-color:var(--accent)}
.toggle::after{content:'';width:14px;height:14px;background:white;border-radius:50%;position:absolute;top:2px;left:2px;transition:left .2s;box-shadow:0 1px 4px rgba(0,0,0,.4)}
.toggle.on::after{left:18px}
.int-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rad2);padding:14px;display:flex;align-items:center;gap:12px;transition:border-color .15s}
.int-card:hover{border-color:var(--border2)}
.int-icon{width:38px;height:38px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;background:var(--bg3);font-family:var(--font-mono);color:var(--accent3)}
.int-info{flex:1;min-width:0}
.int-name{font-size:13.5px;font-weight:500;color:var(--text)}
.int-desc{font-size:12px;color:var(--text3);margin-top:1px}
.int-actions{display:flex;align-items:center;gap:8px;flex-shrink:0}
.wf-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rad2);padding:16px;transition:all .15s;cursor:pointer}
.wf-card:hover{border-color:var(--border2);background:var(--bg3)}
.wf-header{display:flex;align-items:flex-start;gap:10px;margin-bottom:10px}
.wf-icon{width:36px;height:36px;border-radius:8px;background:var(--bg4);display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;color:var(--accent3);font-family:var(--font-mono)}
.wf-title{font-family:var(--font-head);font-size:13.5px;font-weight:600;color:var(--text)}
.wf-sub{font-size:12px;color:var(--text3);margin-top:2px}
.wf-steps{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:10px}
.wf-step{font-size:11px;background:var(--bg3);color:var(--text2);padding:3px 8px;border-radius:5px;border:1px solid var(--border);font-family:var(--font-mono)}
.wf-arrow{color:var(--text3);font-size:10px}
.local-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--rad2);padding:16px;transition:all .15s}
.local-card:hover{border-color:var(--border2)}
.local-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.local-icon{width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;background:var(--bg3);flex-shrink:0;color:var(--accent3);font-family:var(--font-mono)}
.local-title{font-family:var(--font-head);font-size:14px;font-weight:600;color:var(--text)}
.local-val{font-size:12px;color:var(--text3);margin-top:2px;font-family:var(--font-mono)}
.progress-bar{height:5px;background:var(--bg4);border-radius:10px;overflow:hidden;margin-top:8px}
.progress-fill{height:100%;border-radius:10px;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .6s ease}
.data-table{width:100%;border-collapse:collapse}
.data-table th{text-align:left;padding:10px 14px;font-size:11.5px;font-weight:600;color:var(--text3);letter-spacing:.5px;text-transform:uppercase;border-bottom:1px solid var(--border);font-family:var(--font-head)}
.data-table td{padding:11px 14px;font-size:13px;color:var(--text2);border-bottom:1px solid var(--border)}
.data-table tr:last-child td{border-bottom:none}
.data-table tr:hover td{background:var(--bg3)}
.field{margin-bottom:14px}
.field label{display:block;font-size:12.5px;font-weight:500;color:var(--text2);margin-bottom:6px;font-family:var(--font-head)}
.input{width:100%;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;padding:8px 12px;color:var(--text);font-family:var(--font-body);font-size:13.5px;outline:none;transition:border-color .15s}
.input:focus{border-color:var(--accent)}
.input::placeholder{color:var(--text3)}
select.input{cursor:pointer}
.textarea{resize:vertical;min-height:80px;line-height:1.5}
.loader{display:inline-block;width:14px;height:14px;border:2px solid var(--border2);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px;text-align:center;gap:12px}
.empty-title{font-family:var(--font-head);font-size:16px;font-weight:600;color:var(--text2)}
.empty-sub{font-size:13px;color:var(--text3);max-width:280px;line-height:1.6}
.tabs{display:flex;gap:2px;background:var(--bg3);border-radius:9px;padding:3px;margin-bottom:18px;width:fit-content;flex-wrap:wrap}
.tab{padding:6px 14px;border-radius:7px;cursor:pointer;font-size:13px;color:var(--text3);transition:all .15s;font-weight:400}
.tab.active{background:var(--bg2);color:var(--text);border:1px solid var(--border)}
.sec-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;gap:10px}
.sec-title{font-family:var(--font-head);font-size:15px;font-weight:600;color:var(--text)}
.notif{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:var(--rad);border:1px solid var(--border);background:var(--bg2);margin-bottom:8px}
.notif-icon{width:28px;height:28px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:11px;flex-shrink:0;font-family:var(--font-mono)}
.modal-overlay{display:none;position:fixed;inset:0;background:#00000080;z-index:100;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--bg2);border:1px solid var(--border2);border-radius:16px;padding:24px;width:460px;max-width:90vw;animation:fadeup .2s ease}
.modal-title{font-family:var(--font-head);font-size:17px;font-weight:700;color:var(--text);margin-bottom:4px}
.modal-sub{font-size:13px;color:var(--text3);margin-bottom:18px}
.modal-footer{display:flex;gap:8px;justify-content:flex-end;margin-top:18px;border-top:1px solid var(--border);padding-top:16px}
.btn{padding:8px 16px;border-radius:8px;font-size:13.5px;font-family:var(--font-body);cursor:pointer;border:1px solid var(--border2);transition:all .15s;font-weight:500}
.btn-ghost{background:transparent;color:var(--text2)}
.btn-ghost:hover{background:var(--bg3);color:var(--text)}
.btn-primary{background:var(--accent);border-color:var(--accent);color:white}
.btn-primary:hover{background:var(--accent2)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.pulse{animation:pulse 2s infinite}
.cmd-hint{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text3)}
.kbd{background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:2px 5px;font-family:var(--font-mono);font-size:10px;color:var(--text2)}
.overlay{display:none}
@media (max-width:1200px){.grid-4,.grid-3{grid-template-columns:1fr 1fr}.grid-2{grid-template-columns:1fr}}
@media (max-width:980px){
  body{position:relative}
  .overlay{display:block;position:fixed;inset:0;background:#00000088;opacity:0;pointer-events:none;transition:opacity .2s;z-index:9}
  body.sidebar-open .overlay{opacity:1;pointer-events:auto}
  .sidebar{position:fixed;left:0;top:0;bottom:0;transform:translateX(-100%)}
  body.sidebar-open .sidebar{transform:translateX(0)}
  .chat-view{flex-direction:column !important}
  .chat-history-panel{width:100%;max-height:220px;border-right:none;border-bottom:1px solid var(--border)}
}
@media (max-width:720px){
  .topbar{padding:0 12px;gap:8px;flex-wrap:wrap;height:auto;min-height:52px}
  .view{padding:14px}
  .grid-4,.grid-3,.grid-2{grid-template-columns:1fr}
  .cmd-hint{display:none}
}
</style>
</head>
<body>
<div class="overlay" id="sidebar-overlay"></div>
<aside class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="logo-mark">CN</div>
    <span class="logo-text">Connect AI</span>
    <span class="logo-badge">v2.0</span>
  </div>
  <div style="flex:1;overflow-y:auto;padding:8px 0">
    <div class="sidebar-section">Main</div>
    <div class="nav-item active" data-view="dashboard"><span class="nav-icon">DB</span>Dashboard</div>
    <div class="nav-item" data-view="chat"><span class="nav-icon">CH</span>Chat<span class="nav-badge" id="chat-nav-count">0</span></div>
    <div class="sidebar-section">Configure</div>
    <div class="nav-item" data-view="models"><span class="nav-icon">ML</span>Models<span class="nav-badge green" id="model-nav-count">0</span></div>
    <div class="nav-item" data-view="integrations"><span class="nav-icon">IN</span>Integrations<span class="nav-badge amber" id="integration-nav-count">0</span></div>
    <div class="nav-item" data-view="workflows"><span class="nav-icon">WF</span>Workflows</div>
    <div class="nav-item" data-view="locals"><span class="nav-icon">LC</span>Locals</div>
    <div class="sidebar-divider"></div>
    <div class="sidebar-section">System</div>
    <div class="nav-item" data-view="settings"><span class="nav-icon">ST</span>Settings</div>
    <div class="nav-item" data-view="analytics"><span class="nav-icon">AN</span>Analytics</div>
  </div>
  <div class="sidebar-bottom">
    <div class="user-card">
      <div class="avatar" id="operator-avatar">A</div>
      <div class="user-info">
        <div class="user-name" id="operator-name">Admin User</div>
        <div class="user-plan" id="operator-plan">Runtime active</div>
      </div>
      <span style="font-size:12px;color:var(--text3);flex-shrink:0">></span>
    </div>
  </div>
</aside>

<main class="main">
  <div id="view-dashboard" class="view active">
    <div class="topbar">
      <button class="tb-btn" id="sidebar-toggle">Menu</button>
      <span class="topbar-title">Connect AI</span>
      <span class="topbar-sub">Overview</span>
      <div class="topbar-spacer"></div>
      <div class="cmd-hint"><span class="kbd">Ctrl</span><span class="kbd">K</span><span style="margin-left:2px">Command</span></div>
      <button class="tb-btn" id="goto-chat-btn">New Chat</button>
      <button class="tb-btn primary" id="goto-models-btn">Models</button>
    </div>
    <div class="content">
      <div style="padding:24px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:22px;gap:12px;flex-wrap:wrap">
          <div>
            <div style="font-family:var(--font-head);font-size:22px;font-weight:700;color:var(--text);letter-spacing:-0.5px" id="welcome-title">CONNECT is ready</div>
            <div style="font-size:14px;color:var(--text3);margin-top:3px" id="welcome-sub">Your runtime is live and ready for operator input.</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;background:var(--bg3);padding:8px 14px;border-radius:var(--rad);border:1px solid var(--border)">
            <div class="status-dot" id="system-status-dot"></div>
            <span style="font-size:13px;color:var(--text2)" id="system-status-text">Loading runtime</span>
          </div>
        </div>
        <div class="grid-4" style="margin-bottom:20px">
          <div class="card card-sm"><div class="card-sub">Sessions</div><div class="stat-num" id="dash-stat-sessions">0</div><div class="stat-trend trend-up" id="dash-stat-sessions-sub">Real session threads</div></div>
          <div class="card card-sm"><div class="card-sub">Memory Entries</div><div class="stat-num" id="dash-stat-memory">0</div><div class="stat-trend trend-up" id="dash-stat-memory-sub">Runtime memory records</div></div>
          <div class="card card-sm"><div class="card-sub">Live Services</div><div class="stat-num" id="dash-stat-services">0</div><div class="stat-trend trend-up" id="dash-stat-services-sub">Gateway and dashboard state</div></div>
          <div class="card card-sm"><div class="card-sub">Active Workflows</div><div class="stat-num" id="dash-stat-workflows">0</div><div class="stat-trend" style="color:var(--text3)" id="dash-stat-workflows-sub">Runnable workflow files</div></div>
        </div>
        <div class="grid-2" style="margin-bottom:20px">
          <div class="card">
            <div class="sec-header">
              <div class="sec-title">Active Models</div>
              <button class="tb-btn" style="padding:4px 10px;font-size:12px" data-open-view="models">View all</button>
            </div>
            <table class="data-table">
              <thead><tr><th>Model</th><th>Status</th><th>Provider</th></tr></thead>
              <tbody id="dashboard-model-table"></tbody>
            </table>
          </div>
          <div class="card">
            <div class="sec-header">
              <div class="sec-title">Recent Activity</div>
              <span class="badge badge-purple">Live</span>
            </div>
            <div id="dashboard-activity-list"></div>
          </div>
        </div>
        <div class="grid-2">
          <div class="card">
            <div class="sec-header">
              <div class="sec-title">Provider Readiness</div>
              <span style="font-size:12px;color:var(--text3)">Current runtime</span>
            </div>
            <div id="provider-bars"></div>
          </div>
          <div class="card">
            <div class="sec-header">
              <div class="sec-title">Running Workflows</div>
              <button class="tb-btn" style="padding:4px 10px;font-size:12px" data-open-view="workflows">Manage</button>
            </div>
            <div id="dashboard-workflow-list"></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div id="view-chat" class="view chat-view" style="display:none">
    <div class="chat-history-panel">
      <div class="chat-hist-header">
        Conversations
        <button class="new-chat-btn" id="new-chat-btn" title="New chat">+</button>
      </div>
      <div class="hist-search">
        <span class="hist-search-icon">?</span>
        <input type="text" placeholder="Search chats..." id="chat-search-input">
      </div>
      <div class="hist-list" id="chat-history-list"></div>
    </div>
    <div class="chat-container">
      <div class="chat-header">
        <div class="chat-model-pill" data-open-view="models">
          <div class="model-dot"></div>
          <span id="active-model-display">loading</span>
          <span style="color:var(--text3)">v</span>
        </div>
        <div class="topbar-spacer"></div>
        <div style="display:flex;align-items:center;gap:4px;font-size:12px;color:var(--text3)">
          <span>Mode:</span>
          <span style="font-family:var(--font-mono);font-size:12px;color:var(--text2)" id="chat-session-status">idle</span>
        </div>
        <button class="tb-btn" style="padding:5px 10px;font-size:12px" id="refresh-chat-btn">Refresh</button>
      </div>
      <div class="chat-messages" id="chat-messages"></div>
      <div class="chat-input-wrap">
        <div class="chat-tools">
          <button class="chat-tool-btn" data-open-view="integrations">Integrations</button>
          <button class="chat-tool-btn" data-open-view="workflows">Workflows</button>
          <button class="chat-tool-btn" data-open-view="models">Models</button>
          <button class="chat-tool-btn" id="node-client-btn">Node client</button>
        </div>
        <div class="chat-input-box">
          <textarea id="chat-input" placeholder="Message CONNECT... (Shift+Enter for newline)" rows="1"></textarea>
          <button class="send-btn" id="send-btn">></button>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:7px;gap:10px;flex-wrap:wrap">
          <span style="font-size:11px;color:var(--text3)"><span id="chat-model-foot">runtime</span>  <span id="token-count" style="color:var(--text2)">~0 tokens</span></span>
          <div class="cmd-hint"><span class="kbd">Enter</span><span>to send</span><span class="kbd" style="margin-left:6px">Shift+Enter</span><span>newline</span></div>
        </div>
      </div>
    </div>
  </div>

  <div id="view-models" class="view" style="display:none">
    <div class="topbar">
      <button class="tb-btn" id="sidebar-toggle-models">Menu</button>
      <span class="topbar-title">Connect AI</span>
      <div class="topbar-spacer"></div>
      <button class="tb-btn primary" id="open-model-modal-btn">+ Add Model</button>
    </div>
    <div class="content">
      <div style="padding:24px">
        <div style="margin-bottom:18px">
          <div class="tabs">
            <div class="tab active">All Models</div>
            <div class="tab">Cloud</div>
            <div class="tab">Local</div>
          </div>
        </div>
        <div class="grid-3" id="model-card-grid"></div>
      </div>
    </div>
  </div>

  <div id="view-integrations" class="view" style="display:none">
    <div class="topbar">
      <button class="tb-btn" id="sidebar-toggle-integrations">Menu</button>
      <span class="topbar-title">Connect AI</span>
      <div class="topbar-spacer"></div>
      <button class="tb-btn primary" data-open-view="settings">Configure</button>
    </div>
    <div class="content">
      <div style="padding:24px">
        <div class="page-header">
          <div class="page-sub">Connect runtime messaging, repository, and delivery services to CONNECT.</div>
        </div>
        <div class="sec-header"><div class="sec-title">Connected</div></div>
        <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:24px" id="integration-connected-list"></div>
        <div class="sec-header"><div class="sec-title">Available Integrations</div></div>
        <div class="grid-2" id="integration-available-list"></div>
      </div>
    </div>
  </div>

  <div id="view-workflows" class="view" style="display:none">
    <div class="topbar">
      <button class="tb-btn" id="sidebar-toggle-workflows">Menu</button>
      <span class="topbar-title">Connect AI</span>
      <div class="topbar-spacer"></div>
      <button class="tb-btn" id="refresh-workflows-btn">Refresh</button>
    </div>
    <div class="content">
      <div style="padding:24px">
        <div class="grid-2" id="workflow-grid"></div>
      </div>
    </div>
  </div>

  <div id="view-locals" class="view" style="display:none">
    <div class="topbar">
      <button class="tb-btn" id="sidebar-toggle-locals">Menu</button>
      <span class="topbar-title">Connect AI</span>
      <div class="topbar-spacer"></div>
      <button class="tb-btn" id="open-node-client-btn">Node client</button>
    </div>
    <div class="content">
      <div style="padding:24px">
        <div class="page-sub" style="margin-bottom:20px;color:var(--text3)">Local runtime visibility comes from the current CONNECT provider state, node pairing, and workspace services.</div>
        <div class="grid-4" style="margin-bottom:22px">
          <div class="card card-sm"><div class="card-sub">Selected Provider</div><div class="stat-num" style="font-size:20px" id="local-selected-provider">-</div><div class="progress-bar"><div class="progress-fill" id="local-provider-fill" style="width:0%"></div></div></div>
          <div class="card card-sm"><div class="card-sub">Node Count</div><div class="stat-num" style="font-size:20px" id="local-node-count">0</div><div class="progress-bar"><div class="progress-fill" style="width:40%;background:linear-gradient(90deg,var(--green),#10d9a080)"></div></div></div>
          <div class="card card-sm"><div class="card-sub">Canvas Cards</div><div class="stat-num" style="font-size:20px" id="local-canvas-count">0</div><div class="progress-bar"><div class="progress-fill" style="width:50%;background:linear-gradient(90deg,var(--amber),#f59e0b80)"></div></div></div>
          <div class="card card-sm"><div class="card-sub">Gateway Status</div><div style="margin:10px 0 4px;display:flex;align-items:center;gap:8px"><div class="status-dot"></div><span style="font-family:var(--font-head);font-size:16px;font-weight:700;color:var(--text)" id="local-gateway-status">Running</span></div><div style="font-size:12px;color:var(--text3)" id="local-gateway-meta">dashboard and gateway state</div></div>
        </div>
        <div class="sec-header"><div class="sec-title">Installed / Available Local Providers</div></div>
        <div style="display:flex;flex-direction:column;gap:10px" id="local-provider-list"></div>
      </div>
    </div>
  </div>

  <div id="view-settings" class="view" style="display:none">
    <div class="topbar"><button class="tb-btn" id="sidebar-toggle-settings">Menu</button><span class="topbar-title">Connect AI</span><div class="topbar-spacer"></div></div>
    <div class="content">
      <div style="padding:24px;max-width:620px">
        <div style="margin-bottom:24px">
          <div class="sec-title" style="margin-bottom:14px">Provider</div>
          <div class="field"><label>Default Provider</label><select class="input" id="settings-provider-select"></select></div>
          <div class="field"><label>Model Name</label><input class="input" id="settings-model-input" placeholder="e.g. gpt-4.1-mini"></div>
          <div class="field"><label>API Key</label><input class="input" id="settings-key-input" type="password" placeholder="Enter API key only when you need to save or rotate it"></div>
        </div>
        <div style="margin-bottom:24px">
          <div class="sec-title" style="margin-bottom:14px">Preferences</div>
          <div style="display:flex;flex-direction:column;gap:12px">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:var(--rad)"><div><div style="font-size:13.5px;color:var(--text)">Stream responses</div><div style="font-size:12px;color:var(--text3)">Current runtime supports token streaming in shell and can be extended in GUI.</div></div><div class="toggle on" id="pref-stream-toggle"></div></div>
            <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:var(--rad)"><div><div style="font-size:13.5px;color:var(--text)">Save conversation history</div><div style="font-size:12px;color:var(--text3)">Session history is stored in the runtime session manager.</div></div><div class="toggle on" id="pref-history-toggle"></div></div>
          </div>
        </div>
        <div style="margin-top:20px"><button class="btn btn-primary" id="save-settings-btn">Save Provider Settings</button></div>
      </div>
    </div>
  </div>

  <div id="view-analytics" class="view" style="display:none">
    <div class="topbar"><button class="tb-btn" id="sidebar-toggle-analytics">Menu</button><span class="topbar-title">Connect AI</span><div class="topbar-spacer"></div><button class="tb-btn" id="refresh-analytics-btn">Refresh</button></div>
    <div class="content">
      <div style="padding:24px">
        <div class="grid-4" style="margin-bottom:20px">
          <div class="card card-sm"><div class="card-sub">Tools</div><div class="stat-num" id="analytics-tools">0</div><div class="stat-trend trend-up">Available to runtime</div></div>
          <div class="card card-sm"><div class="card-sub">Implemented</div><div class="stat-num" id="analytics-implemented">0</div><div class="stat-trend trend-down">Backed by real actions</div></div>
          <div class="card card-sm"><div class="card-sub">Stubbed</div><div class="stat-num" id="analytics-stubbed">0</div><div class="stat-trend trend-up">Need external wiring</div></div>
          <div class="card card-sm"><div class="card-sub">Cron Jobs</div><div class="stat-num" id="analytics-cron">0</div><div class="stat-trend trend-up">Scheduled items</div></div>
        </div>
        <div class="card" style="margin-bottom:16px">
          <div class="sec-header"><div class="sec-title">Provider Status</div></div>
          <table class="data-table">
            <thead><tr><th>Provider</th><th>Configured</th><th>Ready</th><th>Model</th><th>Selected</th></tr></thead>
            <tbody id="analytics-provider-table"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</main>

<div class="modal-overlay" id="add-model-modal">
  <div class="modal">
    <div class="modal-title">Save Provider / Model</div>
    <div class="modal-sub">Store a provider selection and optional API key in the project env used by CONNECT.</div>
    <div class="field"><label>Provider</label><select class="input" id="modal-provider-select"></select></div>
    <div class="field"><label>Model ID</label><input class="input" id="modal-model-input" placeholder="e.g. gpt-4.1-mini"></div>
    <div class="field"><label>API Key</label><input class="input" id="modal-key-input" type="password" placeholder="Leave blank to keep the current key"></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" id="close-model-modal-btn">Cancel</button>
      <button class="btn btn-primary" id="save-model-modal-btn">Save</button>
    </div>
  </div>
</div>

<script>
const views = ['dashboard','chat','models','integrations','workflows','locals','settings','analytics'];
const state = {
  status: {},
  providers: [],
  sessions: [],
  integrations: {},
  workflows: [],
  nodes: [],
  canvas: {cards: []},
  activeView: 'dashboard',
  activeSessionId: '',
  sessionMessages: [],
  chatSearch: '',
  loadingChat: false
};

function byId(id){ return document.getElementById(id); }
function escapeHtml(value){
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function formatTime(value){
  if(!value) return '';
  try { return new Date(value).toLocaleString(); } catch { return String(value); }
}
function formatCodeBlocks(text){
  const raw = escapeHtml(text || '');
  return raw
    .replace(/```([\\s\\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\\n/g, '<br>');
}
async function loadJson(url, options){
  const res = await fetch(url, options);
  return await res.json();
}
function toggleSidebar(forceOpen){
  const open = typeof forceOpen === 'boolean' ? forceOpen : !document.body.classList.contains('sidebar-open');
  document.body.classList.toggle('sidebar-open', open);
}
function switchView(v){
  state.activeView = v;
  views.forEach(id => {
    const el = byId('view-' + id);
    if(!el) return;
    const active = id === v;
    el.style.display = active ? 'flex' : 'none';
    el.classList.toggle('active', active);
  });
  document.querySelectorAll('.nav-item[data-view]').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-view') === v);
  });
  toggleSidebar(false);
}
function activeSession(){
  return state.sessions.find(item => item.id === state.activeSessionId) || null;
}
function statusBadge(ready, configured){
  if(ready === 'yes') return '<span class="badge badge-green"><span class="badge-dot"></span>Active</span>';
  if(configured === 'yes') return '<span class="badge badge-amber"><span class="badge-dot"></span>Standby</span>';
  return '<span class="badge badge-red"><span class="badge-dot"></span>Missing</span>';
}
function serviceCount(){
  return Object.values(state.status.services || {}).filter(item => item && item.running).length;
}
function connectedIntegrationCount(){
  return Object.values(state.integrations || {}).filter(item => item && item.connected).length;
}
function totalMessageCount(){
  return state.sessions.reduce((sum, item) => sum + Number(item.message_count || 0), 0);
}

function renderDashboard(){
  const currentUser = state.status.current_user || {};
  const provider = state.status.provider || 'none';
  const currentModel = state.status.provider_model || state.providers.find(item => item.selected === 'yes')?.model || provider;
  byId('welcome-title').textContent = currentUser.email ? `Welcome back, ${currentUser.email}` : 'CONNECT is ready';
  byId('welcome-sub').textContent = `Provider ${provider} is ${state.status.provider_error ? 'reporting an issue' : 'available'} and the runtime is serving real sessions, workflows, and integrations.`;
  byId('system-status-text').textContent = serviceCount() ? `${serviceCount()} services live` : 'runtime idle';
  byId('dash-stat-sessions').textContent = String(state.sessions.length);
  byId('dash-stat-memory').textContent = String(state.status.memory_entries || 0);
  byId('dash-stat-services').textContent = String(serviceCount());
  byId('dash-stat-workflows').textContent = String(state.workflows.length);

  const selectedRows = state.providers.filter(item => item.ready === 'yes' || item.selected === 'yes').slice(0, 4);
  const modelTable = byId('dashboard-model-table');
  modelTable.innerHTML = selectedRows.length ? selectedRows.map(item => `
    <tr>
      <td><span style="font-family:var(--font-mono);font-size:12.5px">${escapeHtml(item.model || item.name)}</span></td>
      <td>${statusBadge(item.ready, item.configured)}</td>
      <td style="font-family:var(--font-mono);font-size:12.5px">${escapeHtml(item.name)}</td>
    </tr>`).join('') : '<tr><td colspan="3">No providers configured.</td></tr>';

  const activity = [];
  if(state.sessions[0]) activity.push({kind:'session', title:`Session updated: ${state.sessions[0].name}`, meta:`${state.sessions[0].status}  ${formatTime(state.sessions[0].updated_at)}`});
  if(state.workflows[0]) activity.push({kind:'workflow', title:`Workflow available: ${state.workflows[0].name}`, meta:`${state.workflows[0].step_count || 0} steps`});
  if(connectedIntegrationCount()) activity.push({kind:'integration', title:`${connectedIntegrationCount()} integrations connected`, meta:'Messaging and repository connectors live'});
  if(state.status.provider_error) activity.push({kind:'provider', title:`Provider issue`, meta:state.status.provider_error});
  const activityList = byId('dashboard-activity-list');
  activityList.innerHTML = activity.length ? activity.map(item => `
    <div class="notif">
      <div class="notif-icon" style="background:${item.kind === 'provider' ? '#ef444418' : item.kind === 'integration' ? '#6c63ff18' : '#10d9a018'}">${escapeHtml(item.kind.slice(0,2).toUpperCase())}</div>
      <div><div style="font-size:13px;color:var(--text);font-weight:500">${escapeHtml(item.title)}</div><div style="font-size:12px;color:var(--text3);margin-top:2px">${escapeHtml(item.meta)}</div></div>
    </div>`).join('') : '<div class="empty-state"><div class="empty-title">No recent activity</div><div class="empty-sub">Runtime activity will appear here once sessions, workflows, or integrations change.</div></div>';

  const providerBars = byId('provider-bars');
  providerBars.innerHTML = state.providers.map((item, index) => `
    <div style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;gap:10px;margin-bottom:4px">
        <span style="font-size:12px;color:var(--text2)">${escapeHtml(item.name)}</span>
        <span style="font-size:12px;color:var(--text3)">${escapeHtml(item.model || '')}</span>
      </div>
      <div class="progress-bar"><div class="progress-fill" style="width:${item.ready === 'yes' ? '100' : item.configured === 'yes' ? '60' : '18'}%"></div></div>
    </div>`).join('');

  const workflowRows = byId('dashboard-workflow-list');
  workflowRows.innerHTML = state.workflows.length ? state.workflows.slice(0, 3).map(item => `
    <div style="display:flex;align-items:center;gap:10px;padding:8px 10px;background:var(--bg3);border-radius:var(--rad);border:1px solid var(--border)">
      <span style="font-size:14px;font-family:var(--font-mono);color:var(--accent3)">WF</span>
      <div style="flex:1"><div style="font-size:13px;font-weight:500;color:var(--text)">${escapeHtml(item.name)}</div><div style="font-size:11px;color:var(--text3)">${escapeHtml((item.step_count || 0) + ' steps')}  ${escapeHtml(item.trigger ? 'webhook: ' + item.trigger : 'manual run')}</div></div>
      <span class="badge badge-green pulse"><span class="badge-dot"></span>Ready</span>
    </div>`).join('') : '<div class="empty-state"><div class="empty-title">No workflows found</div><div class="empty-sub">Add YAML workflow files to the workspace and they will appear here.</div></div>';

  byId('operator-name').textContent = currentUser.email || currentUser.user_id || 'Local Operator';
  byId('operator-avatar').textContent = (currentUser.email || 'A').slice(0,1).toUpperCase();
  byId('operator-plan').textContent = currentModel || provider;
}

function renderChatHistory(){
  const search = state.chatSearch.trim().toLowerCase();
  const rows = search ? state.sessions.filter(item => `${item.name} ${item.id} ${item.profile}`.toLowerCase().includes(search)) : state.sessions;
  byId('chat-nav-count').textContent = String(state.sessions.length);
  const grouped = {'Today':[], 'Earlier':[]};
  rows.forEach(item => {
    const updated = item.updated_at ? new Date(item.updated_at) : null;
    const now = new Date();
    const sameDay = updated && updated.toDateString() === now.toDateString();
    (sameDay ? grouped['Today'] : grouped['Earlier']).push(item);
  });
  const container = byId('chat-history-list');
  let html = '';
  Object.entries(grouped).forEach(([label, items]) => {
    if(!items.length) return;
    html += `<div class="hist-group-label">${escapeHtml(label)}</div>`;
    html += items.map(item => `
      <div class="hist-item ${item.id === state.activeSessionId ? 'active' : ''}" data-session-id="${escapeHtml(item.id)}">
        <div class="hist-item-title">${escapeHtml(item.name)}</div>
        <div class="hist-item-meta">${escapeHtml(item.profile)}  ${escapeHtml(formatTime(item.updated_at))}</div>
      </div>`).join('');
  });
  container.innerHTML = html || '<div class="empty-state"><div class="empty-title">No chats</div><div class="empty-sub">Create a session to start chatting with CONNECT.</div></div>';
  container.querySelectorAll('[data-session-id]').forEach(el => {
    el.onclick = async () => {
      state.activeSessionId = el.getAttribute('data-session-id') || '';
      await refreshSessionHistory();
    };
  });
}

function renderSessionMessages(){
  const wrap = byId('chat-messages');
  const current = activeSession();
  byId('chat-session-status').textContent = current ? current.status : 'idle';
  byId('active-model-display').textContent = state.status.provider_model || state.status.provider || 'runtime';
  byId('chat-model-foot').textContent = state.status.provider_model || state.status.provider || 'runtime';
  if(!state.sessionMessages.length){
    wrap.innerHTML = '<div class="empty-state"><div class="empty-title">No conversation yet</div><div class="empty-sub">Start with a real operator request. Responses come from the live runtime and are stored in the selected session.</div></div>';
    return;
  }
  wrap.innerHTML = state.sessionMessages.map(item => {
    const isUser = item.role === 'user';
    const label = isUser ? 'You' : item.role === 'tool' ? 'Tool' : 'CONNECT';
    return `<div class="msg">
      <div class="msg-avatar ${isUser ? 'user' : 'ai'}">${isUser ? 'A' : 'AI'}</div>
      <div class="msg-body">
        <div class="msg-meta"><span class="msg-name">${escapeHtml(label)}</span><span class="msg-time">${escapeHtml(formatTime(item.ts || ''))}</span></div>
        <div class="msg-content">${formatCodeBlocks(item.content || '')}</div>
        <div class="msg-actions"><button class="msg-action-btn" data-copy="${escapeHtml(item.content || '')}">Copy</button></div>
      </div>
    </div>`;
  }).join('');
  wrap.querySelectorAll('[data-copy]').forEach(btn => {
    btn.onclick = async () => {
      try { await navigator.clipboard.writeText(btn.getAttribute('data-copy') || ''); } catch {}
    };
  });
  wrap.scrollTop = wrap.scrollHeight;
}

function renderModels(){
  byId('model-nav-count').textContent = String(state.providers.length);
  const grid = byId('model-card-grid');
  grid.innerHTML = state.providers.map(item => `
    <div class="model-card ${item.selected === 'yes' ? 'active' : ''}" data-provider-card="${escapeHtml(item.name)}">
      <div class="model-logo">${escapeHtml(item.name.slice(0,2).toUpperCase())}</div>
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;flex-wrap:wrap">
        <div class="model-name">${escapeHtml(item.name)}</div>
        ${item.selected === 'yes' ? '<span class="badge badge-purple" style="font-size:10px;padding:1px 6px">Default</span>' : ''}
      </div>
      <div class="model-desc">${escapeHtml(item.note || 'provider')}</div>
      <div class="model-tags">
        ${statusBadge(item.ready, item.configured)}
        <span class="badge badge-blue">${escapeHtml(item.ready === 'yes' && item.name === 'ollama' ? 'Local' : 'Cloud')}</span>
        <span class="badge badge-purple">${escapeHtml(item.model || '')}</span>
      </div>
      <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center;gap:8px">
        <span style="font-size:12px;color:var(--text3);font-family:var(--font-mono)">${escapeHtml(item.selected === 'yes' ? 'selected' : item.configured === 'yes' ? 'configured' : 'not set')}</span>
        <button class="btn btn-ghost" style="padding:4px 10px;font-size:12px" data-pick-provider="${escapeHtml(item.name)}">Configure</button>
      </div>
    </div>`).join('');
  grid.querySelectorAll('[data-pick-provider]').forEach(btn => {
    btn.onclick = () => openProviderModal(btn.getAttribute('data-pick-provider') || '');
  });
  renderProviderSelects();
}

function renderIntegrations(){
  const defs = [
    ['github', 'GitHub', 'Repository token for code and repo operations.', 'GH'],
    ['telegram', 'Telegram', 'Bot token and default chat id.', 'TG'],
    ['slack_webhooks', 'Slack Webhooks', 'Named outbound webhook delivery.', 'SW'],
    ['slack_bot', 'Slack Bot', 'Bidirectional Slack bot runtime.', 'SB'],
    ['discord', 'Discord', 'Named Discord webhooks.', 'DC'],
    ['whatsapp', 'WhatsApp', 'Twilio WhatsApp connector.', 'WA']
  ];
  byId('integration-nav-count').textContent = String(connectedIntegrationCount());
  const connected = [];
  const available = [];
  defs.forEach(([key, name, desc, icon]) => {
    const row = state.integrations[key] || {};
    const markup = `<div class="int-card">
      <div class="int-icon">${icon}</div>
      <div class="int-info"><div class="int-name">${escapeHtml(name)}</div><div class="int-desc">${escapeHtml(desc)}</div></div>
      <div class="int-actions">${row.connected ? '<span class="badge badge-green"><span class="badge-dot"></span>Connected</span>' : `<button class="btn btn-ghost" style="padding:5px 12px;font-size:12.5px" data-open-view="settings">Configure</button>`}</div>
    </div>`;
    (row.connected ? connected : available).push(markup);
  });
  byId('integration-connected-list').innerHTML = connected.join('') || '<div class="empty-state"><div class="empty-title">No integrations connected</div><div class="empty-sub">Configure messaging or repository connectors in settings and they will show here.</div></div>';
  byId('integration-available-list').innerHTML = available.join('');
}

function renderWorkflows(){
  const grid = byId('workflow-grid');
  grid.innerHTML = state.workflows.length ? state.workflows.map(item => `
    <div class="wf-card">
      <div class="wf-header">
        <div class="wf-icon">WF</div>
        <div><div class="wf-title">${escapeHtml(item.name)}</div><div class="wf-sub">${escapeHtml(item.path || '')}</div></div>
        <div style="margin-left:auto"><span class="badge badge-green pulse"><span class="badge-dot"></span>Ready</span></div>
      </div>
      <div class="wf-steps"><span class="wf-step">${escapeHtml(String(item.step_count || 0))} steps</span>${item.trigger ? '<span class="wf-arrow">></span><span class="wf-step">webhook</span>' : ''}</div>
      <div style="margin-top:12px;display:flex;align-items:center;justify-content:space-between;gap:8px">
        <span style="font-size:12px;color:var(--text3)">${escapeHtml(item.trigger ? 'Trigger: ' + item.trigger : 'Manual runtime workflow')}</span>
        <div style="display:flex;gap:6px"><button class="btn btn-ghost" style="padding:4px 10px;font-size:12px" data-run-workflow="${escapeHtml(item.name)}">Run</button></div>
      </div>
    </div>`).join('') : '<div class="empty-state"><div class="empty-title">No workflows</div><div class="empty-sub">Drop YAML workflows into the runtime workspace to make them runnable here.</div></div>';
  grid.querySelectorAll('[data-run-workflow]').forEach(btn => {
    btn.onclick = async () => {
      const name = btn.getAttribute('data-run-workflow');
      if(!name) return;
      const result = await loadJson('/api/workflows/run', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name, session_id: state.activeSessionId || ''})
      });
      btn.textContent = result.ok ? 'Ran' : 'Failed';
      setTimeout(() => { btn.textContent = 'Run'; }, 1200);
    };
  });
}

function renderLocals(){
  byId('local-selected-provider').textContent = state.status.provider || 'none';
  byId('local-provider-fill').style.width = state.status.provider === 'ollama' ? '100%' : state.providers.some(item => item.name === 'ollama' && item.ready === 'yes') ? '80%' : '30%';
  byId('local-node-count').textContent = String(state.nodes.length);
  byId('local-canvas-count').textContent = String((state.canvas.cards || []).length);
  byId('local-gateway-status').textContent = serviceCount() ? 'Running' : 'Idle';
  byId('local-gateway-meta').textContent = `${serviceCount()} services  ${state.status.workspace_root || ''}`;
  const list = byId('local-provider-list');
  const rows = state.providers.filter(item => item.name === 'ollama' || item.ready === 'yes');
  list.innerHTML = rows.length ? rows.map(item => `
    <div class="local-card">
      <div class="local-header">
        <div class="local-icon">${escapeHtml(item.name.slice(0,2).toUpperCase())}</div>
        <div style="flex:1"><div class="local-title">${escapeHtml(item.name)}</div><div class="local-val">${escapeHtml(item.model || '')}  ${escapeHtml(item.note || '')}</div></div>
        ${item.name === state.status.provider ? '<span class="badge badge-blue">Active</span>' : item.ready === 'yes' ? '<span class="badge badge-green pulse">Ready</span>' : '<span class="badge badge-amber">Standby</span>'}
        <div class="toggle ${item.name === state.status.provider ? 'on' : ''}"></div>
      </div>
      <div style="display:flex;gap:14px;font-size:12px;color:var(--text3);flex-wrap:wrap"><span>Configured: ${escapeHtml(item.configured)}</span><span>Ready: ${escapeHtml(item.ready)}</span><span>Model: ${escapeHtml(item.model || '')}</span></div>
    </div>`).join('') : '<div class="empty-state"><div class="empty-title">No local provider</div><div class="empty-sub">Start Ollama locally or configure a provider to see runtime-local availability here.</div></div>';
}

function renderSettings(){
  renderProviderSelects();
  byId('settings-provider-select').value = state.status.provider || state.providers[0]?.name || '';
  byId('settings-model-input').value = state.status.provider_model || '';
}

function renderProviderSelects(){
  const options = state.providers.map(item => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}</option>`).join('');
  byId('settings-provider-select').innerHTML = options;
  byId('modal-provider-select').innerHTML = options;
}

function renderAnalytics(){
  byId('analytics-tools').textContent = String(state.status.tool_count || 0);
  byId('analytics-implemented').textContent = String(state.status.implemented_tool_count || 0);
  byId('analytics-stubbed').textContent = String(state.status.stubbed_tool_count || 0);
  byId('analytics-cron').textContent = String(state.status.cron_count || 0);
  byId('analytics-provider-table').innerHTML = state.providers.map(item => `
    <tr>
      <td><span style="font-family:var(--font-mono);font-size:12.5px">${escapeHtml(item.name)}</span></td>
      <td>${item.configured === 'yes' ? '<span class="badge badge-green">yes</span>' : '<span class="badge badge-red">no</span>'}</td>
      <td>${item.ready === 'yes' ? '<span class="badge badge-green">yes</span>' : '<span class="badge badge-amber">no</span>'}</td>
      <td>${escapeHtml(item.model || '')}</td>
      <td>${item.selected === 'yes' ? '<span class="badge badge-purple">selected</span>' : ''}</td>
    </tr>`).join('');
}

async function refreshSessionHistory(){
  if(!state.activeSessionId){
    state.sessionMessages = [];
    renderSessionMessages();
    renderChatHistory();
    return;
  }
  const history = await loadJson(`/api/session-history?session_id=${encodeURIComponent(state.activeSessionId)}&limit=60`);
  state.sessionMessages = history.items || [];
  renderChatHistory();
  renderSessionMessages();
}

async function sendMessage(){
  const input = byId('chat-input');
  const text = input.value.trim();
  if(!text || state.loadingChat) return;
  state.loadingChat = true;
  byId('send-btn').disabled = true;
  input.value = '';
  input.style.height = 'auto';
  const wrap = byId('chat-messages');
  wrap.insertAdjacentHTML('beforeend', `<div class="msg" id="typing-msg"><div class="msg-avatar ai">AI</div><div class="msg-body"><div class="msg-meta"><span class="msg-name">CONNECT</span><span class="msg-time">typing...</span></div><div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div></div>`);
  wrap.scrollTop = wrap.scrollHeight;
  try{
    const result = await loadJson('/api/ask', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content:text, session_id: state.activeSessionId || ''})
    });
    if(result.session_id) state.activeSessionId = result.session_id;
    await refreshAll();
    switchView('chat');
  }catch(error){
    const typing = byId('typing-msg');
    if(typing) typing.remove();
  }
  state.loadingChat = false;
  byId('send-btn').disabled = false;
}

function autoResize(el){
  el.style.height='auto';
  el.style.height=Math.min(el.scrollHeight,140)+'px';
  byId('token-count').textContent='~'+Math.max(0, Math.floor((el.value || '').length/4))+' tokens';
}

async function newChat(){
  const name = `session-${Date.now()}`;
  const result = await loadJson('/api/sessions/new', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name, profile:'coding'})
  });
  if(result.ok && result.session_id){
    state.activeSessionId = result.session_id;
    await refreshAll();
    switchView('chat');
  }
}

function openProviderModal(providerName){
  byId('modal-provider-select').value = providerName || state.status.provider || state.providers[0]?.name || '';
  const provider = state.providers.find(item => item.name === byId('modal-provider-select').value);
  byId('modal-model-input').value = provider?.model || '';
  byId('modal-key-input').value = '';
  byId('add-model-modal').classList.add('open');
}

async function saveProviderSettings(fromModal){
  const provider = byId(fromModal ? 'modal-provider-select' : 'settings-provider-select').value;
  const model = byId(fromModal ? 'modal-model-input' : 'settings-model-input').value.trim();
  const apiKey = byId(fromModal ? 'modal-key-input' : 'settings-key-input').value.trim();
  const result = await loadJson('/api/providers/select', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({provider, model, api_key: apiKey})
  });
  if(result.ok){
    if(fromModal) byId('add-model-modal').classList.remove('open');
    byId('settings-key-input').value = '';
    await refreshAll();
  }
}

async function refreshAll(){
  const [status, providers, sessions, integrations, workflows, nodes, canvas] = await Promise.all([
    loadJson('/api/status'),
    loadJson('/api/providers'),
    loadJson('/api/sessions'),
    loadJson('/api/integrations'),
    loadJson('/api/workflows'),
    loadJson('/api/nodes'),
    loadJson('/api/canvas')
  ]);
  state.status = status || {};
  state.providers = providers.items || [];
  state.sessions = sessions.items || [];
  state.integrations = integrations || {};
  state.workflows = workflows.items || [];
  state.nodes = nodes.items || [];
  state.canvas = canvas || {cards: []};
  if(!state.activeSessionId && state.sessions[0]) state.activeSessionId = state.sessions[0].id;
  renderDashboard();
  renderModels();
  renderIntegrations();
  renderWorkflows();
  renderLocals();
  renderSettings();
  renderAnalytics();
  await refreshSessionHistory();
}

document.querySelectorAll('.nav-item[data-view]').forEach(el => {
  el.onclick = () => switchView(el.getAttribute('data-view'));
});
document.querySelectorAll('[data-open-view]').forEach(el => {
  el.onclick = () => switchView(el.getAttribute('data-open-view'));
});
['sidebar-toggle','sidebar-toggle-models','sidebar-toggle-integrations','sidebar-toggle-workflows','sidebar-toggle-locals','sidebar-toggle-settings','sidebar-toggle-analytics'].forEach(id => {
  const el = byId(id);
  if(el) el.onclick = () => toggleSidebar();
});
byId('sidebar-overlay').onclick = () => toggleSidebar(false);
byId('goto-chat-btn').onclick = () => switchView('chat');
byId('goto-models-btn').onclick = () => switchView('models');
byId('new-chat-btn').onclick = newChat;
byId('refresh-chat-btn').onclick = refreshSessionHistory;
byId('open-node-client-btn').onclick = () => { window.location.href = '/node-client'; };
byId('node-client-btn').onclick = () => { window.location.href = '/node-client'; };
byId('refresh-workflows-btn').onclick = refreshAll;
byId('refresh-analytics-btn').onclick = refreshAll;
byId('open-model-modal-btn').onclick = () => openProviderModal(state.status.provider || state.providers[0]?.name || '');
byId('close-model-modal-btn').onclick = () => byId('add-model-modal').classList.remove('open');
byId('save-model-modal-btn').onclick = () => saveProviderSettings(true);
byId('save-settings-btn').onclick = () => saveProviderSettings(false);
byId('chat-input').addEventListener('keydown', event => {
  if(event.key === 'Enter' && !event.shiftKey){
    event.preventDefault();
    sendMessage();
  }
});
byId('chat-input').addEventListener('input', event => autoResize(event.target));
byId('send-btn').onclick = sendMessage;
byId('chat-search-input').addEventListener('input', event => {
  state.chatSearch = event.target.value || '';
  renderChatHistory();
});
document.querySelectorAll('.toggle').forEach(el => {
  el.onclick = () => el.classList.toggle('on');
});
byId('add-model-modal').addEventListener('click', function(event){ if(event.target === this) this.classList.remove('open'); });

refreshAll();
setInterval(refreshAll, 7000);
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
                    payload = runtime.gateway_status()
                    payload["provider_model"] = getattr(runtime.ai, "model_name", "")
                    self._send_json(payload)
                    return
                if parsed.path == "/api/tools":
                    self._send_json({"items": runtime.catalog.list()})
                    return
                if parsed.path == "/api/providers":
                    self._send_json(runtime.provider_snapshot())
                    return
                if parsed.path == "/api/sessions":
                    items = runtime.sessions.list()
                    for row in items:
                        row["message_count"] = str(len(runtime.sessions.history(row["id"], 9999)))
                    self._send_json({"items": items})
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
                    "/api/providers/select",
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
                    if self.path == "/api/providers/select":
                        self._send_json(runtime.save_provider_config(str(payload.get("provider", "")), str(payload.get("api_key", "")), str(payload.get("model", ""))))
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
