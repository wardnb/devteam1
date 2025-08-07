from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, List
import asyncio
import json
from datetime import datetime
from pathlib import Path

from orchestration.orchestrator import Orchestrator
from core.base_agent import Message

app = FastAPI(title="Autonomous Dev Team Dashboard")

# Global orchestrator instance
orchestrator: Orchestrator = None
active_connections: List[WebSocket] = []


@app.on_event("startup")
async def startup_event():
    global orchestrator
    orchestrator = Orchestrator()
    await orchestrator.start()
    

@app.on_event("shutdown")
async def shutdown_event():
    global orchestrator
    if orchestrator:
        await orchestrator.stop()
        

@app.get("/")
async def get_dashboard():
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>Autonomous Dev Team Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        h1 { 
            color: white; 
            text-align: center; 
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .dashboard { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; 
        }
        .card { 
            background: white; 
            border-radius: 10px; 
            padding: 20px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        .card:hover { transform: translateY(-5px); }
        .card h2 { 
            color: #667eea; 
            margin-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
        }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            padding: 8px 0;
            border-bottom: 1px solid #f5f5f5;
        }
        .metric:last-child { border-bottom: none; }
        .metric-value { 
            font-weight: bold; 
            color: #764ba2;
        }
        .agent-list { list-style: none; }
        .agent-item { 
            padding: 10px; 
            margin: 5px 0; 
            background: #f8f9fa; 
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status { 
            padding: 3px 8px; 
            border-radius: 3px; 
            font-size: 0.85em;
            font-weight: bold;
        }
        .status.idle { background: #d4edda; color: #155724; }
        .status.working { background: #fff3cd; color: #856404; }
        .status.error { background: #f8d7da; color: #721c24; }
        .status.offline { background: #e2e3e5; color: #383d41; }
        .controls { 
            background: white; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        input, button { 
            padding: 10px; 
            margin: 5px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        input { width: 60%; }
        button { 
            background: #667eea; 
            color: white; 
            border: none;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.3s;
        }
        button:hover { background: #764ba2; }
        .log-container {
            background: #1e1e1e;
            color: #00ff00;
            padding: 15px;
            border-radius: 5px;
            height: 200px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .log-entry { margin: 2px 0; }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .connecting { animation: pulse 2s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Autonomous Development Team</h1>
        
        <div class="controls">
            <h2>Project Control</h2>
            <input type="text" id="requirements" placeholder="Enter project requirements...">
            <button onclick="startProject()">Start Project</button>
            <button onclick="spawnAgent('developer')">+ Developer</button>
            <button onclick="spawnAgent('tester')">+ Tester</button>
            <button onclick="spawnAgent('ui_designer')">+ UI Designer</button>
        </div>
        
        <div class="dashboard">
            <div class="card">
                <h2>📊 Metrics</h2>
                <div id="metrics">
                    <div class="connecting">Connecting...</div>
                </div>
            </div>
            
            <div class="card">
                <h2>👥 Active Agents</h2>
                <ul id="agents" class="agent-list">
                    <div class="connecting">Loading agents...</div>
                </ul>
            </div>
            
            <div class="card">
                <h2>📋 Task Queue</h2>
                <div id="tasks">
                    <div class="connecting">Loading tasks...</div>
                </div>
            </div>
            
            <div class="card">
                <h2>📝 Activity Log</h2>
                <div class="log-container" id="log">
                    <div class="connecting">Waiting for activity...</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const ws = new WebSocket('ws://localhost:8000/ws');
        const log = document.getElementById('log');
        
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.type === 'metrics') {
                updateMetrics(data.data);
            } else if (data.type === 'agents') {
                updateAgents(data.data);
            } else if (data.type === 'log') {
                addLog(data.message);
            } else if (data.type === 'tasks') {
                updateTasks(data.data);
            }
        };
        
        function updateMetrics(metrics) {
            const container = document.getElementById('metrics');
            container.innerHTML = Object.entries(metrics).map(([key, value]) => 
                `<div class="metric">
                    <span>${key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                    <span class="metric-value">${value}</span>
                </div>`
            ).join('');
        }
        
        function updateAgents(agents) {
            const container = document.getElementById('agents');
            container.innerHTML = agents.map(agent => 
                `<li class="agent-item">
                    <span>${agent.id} - ${agent.role}</span>
                    <span class="status ${agent.state}">${agent.state}</span>
                </li>`
            ).join('');
        }
        
        function updateTasks(tasks) {
            const container = document.getElementById('tasks');
            container.innerHTML = tasks.map(task => 
                `<div class="metric">
                    <span>${task.title}</span>
                    <span class="metric-value">${task.status}</span>
                </div>`
            ).join('');
        }
        
        function addLog(message) {
            const timestamp = new Date().toLocaleTimeString();
            log.innerHTML = `<div class="log-entry">[${timestamp}] ${message}</div>` + log.innerHTML;
            if (log.children.length > 50) {
                log.removeChild(log.lastChild);
            }
        }
        
        function startProject() {
            const requirements = document.getElementById('requirements').value;
            if (requirements) {
                fetch('/api/start-project', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({requirements: requirements})
                });
                document.getElementById('requirements').value = '';
            }
        }
        
        function spawnAgent(type) {
            fetch('/api/spawn-agent', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({type: type})
            });
        }
        
        // Request initial data
        ws.onopen = function() {
            ws.send(JSON.stringify({action: 'get_status'}));
        };
        
        // Periodic updates
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({action: 'get_status'}));
            }
        }, 2000);
    </script>
</body>
</html>
    """)
    

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("action") == "get_status":
                # Send metrics
                metrics = orchestrator.get_metrics()
                await websocket.send_json({
                    "type": "metrics",
                    "data": metrics
                })
                
                # Send agent list
                agents = []
                for agent_id, agent in orchestrator.agents.items():
                    agents.append({
                        "id": agent_id,
                        "role": agent.role,
                        "state": agent.state.value
                    })
                await websocket.send_json({
                    "type": "agents",
                    "data": agents
                })
                
                # Send task list
                tasks = []
                for task in list(orchestrator.pending_tasks.values())[:10]:
                    tasks.append({
                        "title": task.title,
                        "status": task.status
                    })
                await websocket.send_json({
                    "type": "tasks",
                    "data": tasks
                })
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)
        

@app.post("/api/start-project")
async def start_project(request: Dict[str, Any]):
    requirements = request.get("requirements")
    if not requirements:
        raise HTTPException(status_code=400, detail="Requirements are required")
        
    await orchestrator.start_project(requirements)
    
    # Notify all websocket connections
    for connection in active_connections:
        await connection.send_json({
            "type": "log",
            "message": f"Started new project: {requirements[:50]}..."
        })
        
    return {"status": "success", "message": "Project started"}
    

@app.post("/api/spawn-agent")
async def spawn_agent(request: Dict[str, Any]):
    agent_type = request.get("type")
    
    agent_map = {
        "developer": "DeveloperAgent",
        "tester": "TesterAgent", 
        "ui_designer": "UIDesignerAgent",
        "project_manager": "ProjectManagerAgent"
    }
    
    if agent_type not in agent_map:
        raise HTTPException(status_code=400, detail="Invalid agent type")
        
    # Import and spawn the agent
    if agent_type == "developer":
        from agents.developer import DeveloperAgent
        agent = await orchestrator.spawn_agent(DeveloperAgent)
    elif agent_type == "tester":
        from agents.tester import TesterAgent
        agent = await orchestrator.spawn_agent(TesterAgent)
    elif agent_type == "ui_designer":
        from agents.ui_designer import UIDesignerAgent
        agent = await orchestrator.spawn_agent(UIDesignerAgent)
    elif agent_type == "project_manager":
        from agents.project_manager import ProjectManagerAgent
        agent = await orchestrator.spawn_agent(ProjectManagerAgent)
        
    # Notify all websocket connections
    for connection in active_connections:
        await connection.send_json({
            "type": "log",
            "message": f"Spawned new {agent_type}: {agent.agent_id}"
        })
        
    return {"status": "success", "agent_id": agent.agent_id}
    

@app.get("/api/metrics")
async def get_metrics():
    return orchestrator.get_metrics()
    

@app.get("/api/agents")
async def get_agents():
    agents = []
    for agent_id, agent in orchestrator.agents.items():
        agents.append({
            "id": agent_id,
            "name": agent.name,
            "role": agent.role,
            "state": agent.state.value,
            "capabilities": [c.value for c in agent.capabilities]
        })
    return agents