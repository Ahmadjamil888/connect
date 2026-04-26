# AI ASSISTANT - Capability-Layered AI Operator

Ek advanced AI platform jo planning, coding, automation, aur project execution ko controlled tools ke through run karta hai.

This repo is strongest when treated as:
- a `core brain` with planning, memory, and reflection
- a `tool system` for filesystem, terminal, browser, code, and web actions
- an `execution engine` with retries, run state, and world-state tracking
- a `safety layer` with policy scopes, confirmations, and audit logs

## 🚀 Quick Start (3 Minutes)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Choose a Provider
- `Anthropic`: `ANTHROPIC_API_KEY`
- `Groq`: `GROQ_API_KEY`
- `OpenAI`: `OPENAI_API_KEY`
- `OpenRouter`: `OPENROUTER_API_KEY`
- `Gemini`: `GOOGLE_GEMINI_API_KEY`
- `Hugging Face`: `HUGGINGFACE_API_KEY`
- `Ollama`: no key, but `ollama serve` must be running locally

### Step 3: Set Provider Config

**Method A: Edit .env file (Recommended - persists)**
```bash
# Open .env file and add either:
AI_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here

# or:
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**Method B: Environment variable (temporary)**
```bash
# Windows
set AI_PROVIDER=groq
set GROQ_API_KEY=gsk_your_key_here

# Linux/Mac
export AI_PROVIDER=groq
export GROQ_API_KEY=gsk_your_key_here
```

### Step 4: Run
```bash
python ai_assistant.py
# or run one goal directly
python ai_assistant.py "build a next js website"
# or inspect provider/launcher state
python ai_assistant.py --doctor
```

### Global `connect` Command
```bash
install_connect_command.bat
```
This installs `connect` into `%USERPROFILE%\connect-bin` and lets you launch the CLI from any directory while keeping your current working directory intact.

---

## Architecture

### 1. Core Brain
- Multi-step planning before execution
- Reflection and retry loop after tool results
- Short-term and long-term memory
- Tool selection based on task and policy

### 2. Tool System
- Filesystem tools for reading, writing, searching, and project setup
- Terminal tools for command execution
- Browser tools for navigation, snapshots, and automation
- Code tools for Python execution, workflow generation, and helper synthesis

### 3. Execution + Safety
- Policy scopes for `filesystem`, `terminal`, `browser`, `network`, `os_control`, `auth`, and more
- Confirmation prompts for dangerous actions
- Audit log and persistent world-state tracking
- Autonomous runs with resume support

### 4. Coding Agent Direction
- Repo inspection and environment observation
- Write, run, debug, patch, rerun loop
- Workflow generation and reusable helper synthesis
- Explicit path toward stronger git/testing/deployment automation
- Richer terminal presentation for plans, patches, shell output, and observations

See [ARCHITECTURE.md](/C:/Users/Admin/Desktop/ai%20assistant%20for%20pc/ARCHITECTURE.md) for the target system design.

## ✨ Features

### 1. Intelligent Chatting
- Natural conversations in English, Urdu, Hindi
- Remembers user preferences
- Multi-turn context awareness

### 2. Controlled Computer Operations
- File management through explicit tools
- System commands through `run_shell_command`
- Browser/UI actions through automation tools
- Sensitive OS actions blocked by policy unless enabled

### 3. Web Automation
- Open websites in browser
- Fill forms automatically
- Click elements
- Navigate pages

### 4. Website Creation
- Full websites (HTML, CSS, JavaScript)
- Multi-page sites
- Responsive design
- Deploy to Netlify/Vercel

### 5. Account Setup Assistance
- Step-by-step guidance for Gmail, GitHub, etc.
- OTP handling (user enters manually)
- Login assistance with permission

### 6. Startup Creation Wizard ⭐
**Idea se Launch tak - 7 Steps:**
1. Idea Validation
2. Business Plan
3. Website Building
4. Content Generation
5. Marketing Strategy
6. Deployment
7. Analytics Setup

### 7. Weekly Analytics
- Task completion stats
- Success rate
- Projects overview
- Conversation history

### 8. Continuous Management
- Website health monitoring
- Auto-update checks
- Project status tracking

---

## 💬 Examples

### Create Website
```
[AI Assistant]> Create a website for my restaurant "Taste of India"

[*] Executing: create_website
    Result: Created website with 4 files (home, about, menu, contact)
```

### Startup Creation (Urdu/Hindi)
```
[AI Assistant]> Mujhe startup banana hai - online coaching platform

[*] Starting Startup Creation Wizard...
✓ Validating business idea
✓ Creating business plan
✓ Building website
✓ Generating content
✓ Creating marketing strategy
✓ Setting up deployment
✓ Configuring analytics
```

### Account Setup Help
```
[AI Assistant]> Help me create a Gmail account

Account setup guide for Gmail:
1. Go to gmail.com
2. Click 'Create account'
3. Enter your name
4. Choose username
...
```

### Weekly Report
```
[AI Assistant]> /report

# Weekly Report
- Conversations: 15
- Tasks: 42 (38 completed, 4 failed)
- Success Rate: 90.5%
- Projects: 3 (2 active)
```

### Save Preferences
```
[AI Assistant]> Mera naam Ahmad hai, yaad rakhna
[*] Saved: name

[AI Assistant]> Mera naam kya hai?
Ahmad
```

---

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/chat` | Conversation mode |
| `/agent [goal]` | Run the autonomous planner/executor loop |
| `/agent-runs` | List recent autonomous runs |
| `/agent-resume [run_id]` | Resume a paused or failed run |
| `/policy` | Show current policy scopes |
| `/policy-set [scope] [on\|off]` | Toggle a policy scope |
| `/audit [N]` | Show recent audit entries |
| `/startup [idea]` | Create startup from idea |
| `/report` | Weekly analytics report |
| `/projects` | List all projects |
| `/stats` | Task statistics |
| `/profile` | User profile |
| `/doctor` | Provider and launcher diagnostics |
| `/clear` | Clear conversation |
| `/exit` | Exit |

---

## 🛠️ Available Tools (40+)

### File Operations
- `read_file`, `write_file`, `create_directory`, `list_directory`
- `file_operations` - Copy, move, delete, rename files
- `search_files` - Search entire system for files

### System & PC Access ⭐ NEW
- `manage_processes` - List, start, kill processes
- `control_media` - Volume control, media playback
- `take_screenshot` - Capture screenshots
- `registry_operations`, `schedule_task`, `install_package`

These capabilities should stay behind policy gates and confirmation prompts.

### Network
- `network_operations` - Ping, get IP, port scan, netstat
- `web_scrape` - Scrape website content
- `download_file` - Download files from URLs

### Windows Integration
- `registry_operations` - Read/write Windows registry
- `schedule_task` - Windows Task Scheduler integration
- `send_notification` - Desktop notifications

### Development
- `execute_python` - Run Python code dynamically
- `install_package` - Install pip, npm, choco, winget packages

### Web Development
- `create_website`, `generate_content`, `deploy_website`

### Browser Automation
- `open_browser`, `fill_form_field`, `click_element`

### Account Setup
- `guide_account_setup`, `request_otp`

### Business
- `validate_business_idea`, `create_business_plan`, `create_marketing_strategy`

### Analytics
- `generate_weekly_report`, `get_task_statistics`

### Project Management
- `create_project`, `update_project_status`, `monitor_project_health`, `check_website_status`

### User Data
- `save_user_preference`, `get_user_preference`

### Clipboard
- `copy_to_clipboard`, `get_clipboard`

---

## 🔒 Security Features

- **Encrypted Credentials**: Passwords stored encrypted locally
- **Permission Gates**: Asks before sensitive actions
- **OTP Safety**: User manually enters OTP (never auto-submitted)
- **Local Storage**: All data stored on your computer
- **No Cloud Sync**: Your data stays private

---

## 📁 Data Storage

Data is stored in `~/.ai_assistant/`:
```
~/.ai_assistant/
├── user_data.json       # Profile & preferences
├── history.json         # Conversation history
├── projects.json        # Projects
├── analytics.json       # Analytics data
└── credentials.enc.json # Encrypted credentials
```

---

## 🌐 Languages

```
English: "Create a website for my business"
Urdu:    "Mere business ke liye website banao"
Hindi:   "Mujhe startup banana hai"
```

---

## ⚙️ Configuration

### Environment Variables
```bash
GROQ_API_KEY=gsk_...        # Your Groq API key
AI_ASSISTANT_DEBUG=true     # Enable debug mode
```

### AI Models
- **Primary**: Groq API (Llama 3.3 70B) - Free, 500+ requests/day
- **Fallback**: Ollama (llama3.2) - Local, unlimited

---

## 🆚 Comparison

| Feature | AI Assistant | Others |
|---------|-------------|--------|
| Setup Time | 3 min | 30+ min |
| Cost | 100% Free | Paid |
| Languages | En/Ur/Hi | English only |
| Startup Wizard | ✅ 7-step | ❌ |
| Analytics | ✅ Weekly | ❌ |
| Data Storage | ✅ Local | Cloud only |
| Account Help | ✅ | ❌ |

---

## 🐛 Troubleshooting

### "GROQ_API_KEY not set"
```bash
# Get free key: https://console.groq.com/keys
set GROQ_API_KEY=your_key
```

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Ollama not running"
```bash
# Install: https://ollama.ai
ollama pull llama3.2
```

---

## 📚 Documentation

- `ADVANCED_PLATFORM_GUIDE.md` - Detailed guide with examples
- `COMPLETE_SUMMARY.md` - Full feature overview

---

## 🎯 Use Cases

### 1. Entrepreneur
```
"I want to start an online tutoring business"
→ Creates business plan, website, marketing strategy
→ Deploys and sets up analytics
```

### 2. Developer
```
"Create a React portfolio and deploy it"
→ Builds multi-page site
→ Deploys to Netlify
```

### 3. Student
```
"Help me setup Gmail and GitHub accounts"
→ Step-by-step guidance
→ OTP handling
```

### 4. Business Owner
```
"Weekly report dikhao"
→ Shows tasks, projects, success rate
```

### 5. System Admin ⭐ NEW
```
"Show me all processes using more than 5% CPU"
→ Lists high-CPU processes

"Kill all Chrome processes"
→ Terminates Chrome instances

"Search for all Python files on my system"
→ Finds all .py files
```

### 6. Network Analysis ⭐ NEW
```
"Ping google.com and show results"
→ Runs ping test

"Scan ports on 192.168.1.1"
→ Shows open ports on router

"Show my IP address"
→ Displays local IP
```

### 7. File Management ⭐ NEW
```
"Copy all documents from Downloads to Desktop"
→ Bulk file operations

"Delete all .tmp files in C:\temp"
→ Cleanup operations
```

### 8. Automation ⭐ NEW
```
"Create a scheduled task to run backup every day at 5pm"
→ Windows Task Scheduler integration

"Take a screenshot every hour"
→ Automated screen capture
```

---

## 📝 License

MIT License - Free for personal and commercial use

---

## 🙏 Credits

Built with:
- Python 3.x
- Groq API (Llama 3.3 70B)
- Ollama (local fallback)
- Open source libraries

---

**"Apna AI assistant se sab kuch karein - chatting se le kar startup banane tak!"**

Happy Automating! 🚀
