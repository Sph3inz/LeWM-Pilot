# SkyMind

AI-driven adaptive flight training on JSBSim (Windows).

## Setup

### Prerequisites

- Windows 10/11, Python 3.11+
- [Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) (for JSBSim)
- Node.js 18+ (dashboard)
- OpenRouter API key for LLM scenario generation

### Install

```powershell
cd C:\SkyMind
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-week1.txt
pip install git+https://github.com/sryu1/jsbgym.git
pip install -e packages/skymind-data -e packages/skymind-sim -e packages/skymind-core -e packages/skymind-llm
pip install -r requirements-ai-server.txt
pip install jsonschema

copy .env.example .env
# Edit .env — set OPENROUTER_API_KEY (never commit .env)
```

Optional — real LeWM planner (mock planner works without this):

```powershell
pip install -r requirements-lewm.txt
python scripts/collect_data.py
python scripts/finetune_lewm.py
# writes checkpoints/lewm_flight_v1.pt
```

## Demo

```powershell
.\scripts\preflight_demo.ps1

# Terminal 1
python scripts/run_demo.py
# or: python scripts/run_demo.py --mock-planner

# Terminal 2
cd apps/dashboard
npm install
npm run dev
# Open http://localhost:5173
```

## Layout

| Path | Role |
|------|------|
| `packages/skymind-sim` | jsbgym adapter, failures, keyboard pilot |
| `packages/skymind-data` | Session recorder, AutopilotCollector |
| `packages/skymind-core` | LeWM, Profiler, Orchestrator, Planner, AICoreService |
| `packages/skymind-llm` | OpenRouter scenario compiler |
| `apps/ai_server` | FastAPI + WebSocket @ 8765 |
| `apps/dashboard` | SvelteKit live adaptation UI |
| `configs/` | Sim, planner, scenario YAML/JSON |
| `schemas/` | Scenario + telemetry JSON schemas |
