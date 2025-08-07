import asyncio
import uuid
from typing import Any, Dict, List, Optional, Type
from datetime import datetime
import yaml
import structlog
from pathlib import Path
from collections import defaultdict

from core.base_agent import BaseAgent, Task, Message, AgentCapability, AgentState
from communication.message_broker import MessageBroker
from agents.project_manager import ProjectManagerAgent
from agents.developer import DeveloperAgent  
from agents.tester import TesterAgent
from agents.ui_designer import UIDesignerAgent


class Orchestrator:
    def __init__(self, config_path: str = "./configs/config.yaml"):
        self.config = self.load_config(config_path)
        self.agents: Dict[str, BaseAgent] = {}
        self.message_broker = MessageBroker(
            redis_host=self.config["communication"]["redis"]["host"],
            redis_port=self.config["communication"]["redis"]["port"],
            redis_db=self.config["communication"]["redis"]["db"]
        )
        self.logger = structlog.get_logger()
        self.running = False
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.pending_tasks: Dict[str, Task] = {}
        self.completed_tasks: List[Task] = []
        self.agent_pool: Dict[str, List[str]] = defaultdict(list)
        self.metrics: Dict[str, Any] = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "agents_spawned": 0,
            "total_runtime": 0
        }
        
    def load_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
            
    async def initialize(self):
        await self.message_broker.connect()
        await self.spawn_initial_agents()
        await self.setup_message_routing()
        self.logger.info("Orchestrator initialized")
        
    async def spawn_initial_agents(self):
        agent_configs = self.config.get("agents", {})
        
        if agent_configs.get("project_manager", {}).get("enabled", True):
            await self.spawn_agent(ProjectManagerAgent, "pm-001")
            
        if agent_configs.get("developer", {}).get("enabled", True):
            max_devs = agent_configs["developer"].get("max_instances", 3)
            for i in range(min(1, max_devs)):
                await self.spawn_agent(DeveloperAgent, f"dev-{i+1:03d}")
                
        if agent_configs.get("tester", {}).get("enabled", True):
            await self.spawn_agent(TesterAgent, "qa-001")
            
        if agent_configs.get("ui_designer", {}).get("enabled", True):
            await self.spawn_agent(UIDesignerAgent, "ui-001")
            
    async def spawn_agent(self, agent_class: Type[BaseAgent], agent_id: str = None) -> BaseAgent:
        if not agent_id:
            agent_id = f"{agent_class.__name__.lower()}_{uuid.uuid4().hex[:8]}"
            
        agent = agent_class(
            agent_id=agent_id,
            ollama_host=self.config["llm"]["base_url"]
        )
        
        self.agents[agent_id] = agent
        
        for capability in agent.capabilities:
            self.agent_pool[capability.value].append(agent_id)
            
        await self.message_broker.register_agent(agent_id)
        
        await self.message_broker.subscribe_agent(
            agent_id,
            lambda msg: asyncio.create_task(self.route_message_to_agent(agent_id, msg))
        )
        
        asyncio.create_task(agent.start())
        
        self.metrics["agents_spawned"] += 1
        self.logger.info(f"Spawned agent: {agent_id} ({agent_class.__name__})")
        
        return agent
        
    async def setup_message_routing(self):
        await self.message_broker.subscribe_to_channel(
            "orchestrator",
            self.handle_orchestrator_message
        )
        
        await self.message_broker.subscribe_to_channel(
            "broadcast",
            self.handle_broadcast_message
        )
        
    async def route_message_to_agent(self, agent_id: str, message_data: Dict[str, Any]):
        if agent_id in self.agents:
            message = Message(**message_data)
            await self.agents[agent_id].receive_message(message)
            
    async def handle_orchestrator_message(self, message_data: Dict[str, Any]):
        message = Message(**message_data)
        
        if message.message_type == "agent_ready":
            await self.handle_agent_ready(message.content)
        elif message.message_type == "task_completed":
            await self.handle_task_completed(message.content)
        elif message.message_type == "task_failed":
            await self.handle_task_failed(message.content)
        elif message.message_type == "assistance_request":
            await self.handle_assistance_request(message)
        elif message.message_type == "status_update":
            await self.handle_status_update(message.content)
        elif message.message_type == "progress_report":
            await self.handle_progress_report(message.content)
        elif message.message_type == "sprint_completed":
            await self.handle_sprint_completed(message.content)
            
    async def handle_broadcast_message(self, message_data: Dict[str, Any]):
        message = Message(**message_data)
        
        for agent_id, agent in self.agents.items():
            if agent_id != message.sender_id:
                await agent.receive_message(message)
                
    async def handle_agent_ready(self, content: Dict[str, Any]):
        agent_id = content.get("agent_id")
        capabilities = content.get("capabilities", [])
        
        self.logger.info(f"Agent {agent_id} is ready with capabilities: {capabilities}")
        
        if "project_manager" in agent_id:
            await self.send_team_roster_to_pm(agent_id)
            
    async def send_team_roster_to_pm(self, pm_id: str):
        team_roster = []
        
        for agent_id, agent in self.agents.items():
            if agent_id != pm_id:
                team_roster.append({
                    "agent_id": agent_id,
                    "role": agent.role,
                    "capabilities": [c.value for c in agent.capabilities],
                    "state": agent.state.value
                })
                
        for member in team_roster:
            await self.message_broker.publish_message(
                Message(
                    sender_id="orchestrator",
                    receiver_id=pm_id,
                    message_type="team_member_joined",
                    content=member
                )
            )
            
    async def handle_task_completed(self, content: Dict[str, Any]):
        task_id = content.get("task_id")
        agent_id = content.get("agent_id")
        result = content.get("result")
        
        self.logger.info(f"Task {task_id} completed by {agent_id}")
        
        if task_id in self.pending_tasks:
            task = self.pending_tasks[task_id]
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.result = result
            
            self.completed_tasks.append(task)
            del self.pending_tasks[task_id]
            
            self.metrics["tasks_completed"] += 1
            
        await self.check_for_dependent_tasks(task_id)
        
    async def handle_task_failed(self, content: Dict[str, Any]):
        task_id = content.get("task_id")
        agent_id = content.get("agent_id")
        error = content.get("error")
        
        self.logger.error(f"Task {task_id} failed by {agent_id}: {error}")
        
        if task_id in self.pending_tasks:
            task = self.pending_tasks[task_id]
            task.status = "failed"
            
            self.metrics["tasks_failed"] += 1
            
            await self.attempt_task_recovery(task, error)
            
    async def attempt_task_recovery(self, task: Task, error: str):
        if "retry" not in task.metadata:
            task.metadata["retry"] = 0
            
        if task.metadata["retry"] < 3:
            task.metadata["retry"] += 1
            task.status = "pending"
            
            self.logger.info(f"Retrying task {task.id} (attempt {task.metadata['retry']})")
            
            await asyncio.sleep(5 * task.metadata["retry"])
            
            await self.assign_task_to_agent(task)
        else:
            self.logger.error(f"Task {task.id} failed after 3 retries")
            await self.escalate_failed_task(task, error)
            
    async def escalate_failed_task(self, task: Task, error: str):
        pm_agents = [aid for aid, agent in self.agents.items() if "project_manager" in agent.role]
        
        if pm_agents:
            await self.message_broker.publish_message(
                Message(
                    sender_id="orchestrator",
                    receiver_id=pm_agents[0],
                    message_type="task_escalation",
                    content={
                        "task": task.dict(),
                        "error": error,
                        "severity": "high"
                    }
                )
            )
            
    async def handle_assistance_request(self, message: Message):
        content = message.content
        requesting_agent = content.get("requesting_agent")
        capability_needed = content.get("capability_needed")
        context = content.get("context")
        
        helper_agent = await self.find_agent_with_capability(capability_needed, exclude=requesting_agent)
        
        if helper_agent:
            assistance_task = Task(
                title=f"Assist {requesting_agent}",
                description=f"Provide {capability_needed} assistance",
                metadata={"context": context, "requester": requesting_agent}
            )
            
            await self.agents[helper_agent].start_task(assistance_task)
            
            if message.requires_response:
                response = Message(
                    sender_id="orchestrator",
                    receiver_id=message.sender_id,
                    message_type="assistance_response",
                    content={
                        "status": "success",
                        "helper_agent": helper_agent,
                        "task_id": assistance_task.id
                    },
                    correlation_id=message.correlation_id
                )
                await self.message_broker.publish_message(response)
        else:
            if self.config["recruitment"]["auto_recruit"]:
                await self.recruit_agent_for_capability(capability_needed)
                
    async def find_agent_with_capability(self, capability: str, exclude: str = None) -> Optional[str]:
        capable_agents = self.agent_pool.get(capability, [])
        
        for agent_id in capable_agents:
            if agent_id != exclude and self.agents[agent_id].state == AgentState.IDLE:
                return agent_id
                
        return None
        
    async def handle_status_update(self, content: Dict[str, Any]):
        agent_id = content.get("agent_id")
        state = content.get("state")
        
        if agent_id in self.agents:
            self.agents[agent_id].state = AgentState(state)
            
    async def handle_progress_report(self, content: Dict[str, Any]):
        self.logger.info(f"Progress Report: {content}")
        
    async def handle_sprint_completed(self, content: Dict[str, Any]):
        self.logger.info(f"Sprint Completed: {content}")
        await self.analyze_sprint_performance(content)
        
    async def analyze_sprint_performance(self, sprint_data: Dict[str, Any]):
        velocity = sprint_data.get("sprint_velocity", 0)
        tasks_completed = sprint_data.get("tasks_completed", 0)
        
        if velocity < 20:
            self.logger.warning("Low sprint velocity detected")
            if self.config["recruitment"]["auto_recruit"]:
                await self.recruit_additional_developers()
                
    async def check_for_dependent_tasks(self, completed_task_id: str):
        for task in list(self.pending_tasks.values()):
            if completed_task_id in task.dependencies:
                task.dependencies.remove(completed_task_id)
                if not task.dependencies and task.status == "blocked":
                    task.status = "pending"
                    await self.assign_task_to_agent(task)
                    
    async def assign_task_to_agent(self, task: Task):
        suggested_role = task.metadata.get("suggested_role", "developer")
        
        agent_id = await self.find_agent_with_capability(
            self.role_to_capability(suggested_role)
        )
        
        if agent_id:
            task.assignee_id = agent_id
            task.status = "assigned"
            self.pending_tasks[task.id] = task
            
            await self.message_broker.publish_message(
                Message(
                    sender_id="orchestrator",
                    receiver_id=agent_id,
                    message_type="task_assignment",
                    content={"task": task.dict()}
                )
            )
        else:
            await self.task_queue.put(task)
            
    def role_to_capability(self, role: str) -> str:
        role_capability_map = {
            "developer": AgentCapability.CODE_GENERATION.value,
            "tester": AgentCapability.TESTING.value,
            "ui_designer": AgentCapability.UI_DESIGN.value,
            "project_manager": AgentCapability.PROJECT_MANAGEMENT.value,
            "architect": AgentCapability.ARCHITECTURE.value
        }
        return role_capability_map.get(role, AgentCapability.CODE_GENERATION.value)
        
    async def recruit_agent_for_capability(self, capability: str):
        self.logger.info(f"Recruiting agent for capability: {capability}")
        
        agent_class_map = {
            AgentCapability.CODE_GENERATION.value: DeveloperAgent,
            AgentCapability.TESTING.value: TesterAgent,
            AgentCapability.UI_DESIGN.value: UIDesignerAgent,
            AgentCapability.PROJECT_MANAGEMENT.value: ProjectManagerAgent
        }
        
        agent_class = agent_class_map.get(capability, DeveloperAgent)
        new_agent = await self.spawn_agent(agent_class)
        
        await self.notify_pm_of_new_agent(new_agent)
        
    async def recruit_additional_developers(self):
        current_devs = len([a for a in self.agents.values() if "developer" in a.role])
        max_devs = self.config["agents"]["developer"].get("max_instances", 3)
        
        if current_devs < max_devs:
            await self.spawn_agent(DeveloperAgent)
            
    async def notify_pm_of_new_agent(self, agent: BaseAgent):
        pm_agents = [aid for aid, a in self.agents.items() if "project_manager" in a.role]
        
        if pm_agents:
            await self.message_broker.publish_message(
                Message(
                    sender_id="orchestrator",
                    receiver_id=pm_agents[0],
                    message_type="team_member_joined",
                    content={
                        "agent_id": agent.agent_id,
                        "role": agent.role,
                        "capabilities": [c.value for c in agent.capabilities],
                        "state": agent.state.value
                    }
                )
            )
            
    async def start_project(self, project_requirements: str):
        self.logger.info("Starting new project")
        
        pm_agents = [aid for aid, agent in self.agents.items() if "project_manager" in agent.role]
        
        if not pm_agents:
            pm = await self.spawn_agent(ProjectManagerAgent, "pm-001")
            pm_agents = [pm.agent_id]
            
        await self.message_broker.publish_message(
            Message(
                sender_id="orchestrator",
                receiver_id=pm_agents[0],
                message_type="new_project",
                content={
                    "requirements": project_requirements,
                    "project_id": str(uuid.uuid4()),
                    "created_at": datetime.utcnow().isoformat()
                }
            )
        )
        
    async def process_task_queue(self):
        while self.running:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1)
                await self.assign_task_to_agent(task)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing task queue: {e}")
                
    async def monitor_agent_health(self):
        while self.running:
            await asyncio.sleep(30)
            
            online_agents = await self.message_broker.get_online_agents()
            
            for agent_id, agent in self.agents.items():
                if agent_id not in online_agents and agent.state != AgentState.OFFLINE:
                    self.logger.warning(f"Agent {agent_id} appears to be offline")
                    agent.state = AgentState.OFFLINE
                    
            for agent_id in list(self.agents.keys()):
                if self.agents[agent_id].state == AgentState.ERROR:
                    await self.restart_agent(agent_id)
                    
    async def restart_agent(self, agent_id: str):
        self.logger.info(f"Restarting agent {agent_id}")
        
        agent = self.agents[agent_id]
        agent_class = type(agent)
        
        await agent.stop()
        del self.agents[agent_id]
        
        await self.spawn_agent(agent_class, agent_id)
        
    async def start(self):
        self.running = True
        await self.initialize()
        
        asyncio.create_task(self.message_broker.start_listening())
        asyncio.create_task(self.process_task_queue())
        asyncio.create_task(self.monitor_agent_health())
        
        self.logger.info("Orchestrator started")
        
    async def stop(self):
        self.running = False
        
        for agent in self.agents.values():
            await agent.stop()
            
        await self.message_broker.stop_listening()
        await self.message_broker.disconnect()
        
        self.logger.info("Orchestrator stopped")
        
    def get_metrics(self) -> Dict[str, Any]:
        return {
            **self.metrics,
            "active_agents": len([a for a in self.agents.values() if a.state != AgentState.OFFLINE]),
            "total_agents": len(self.agents),
            "pending_tasks": len(self.pending_tasks),
            "completed_tasks": len(self.completed_tasks),
            "task_queue_size": self.task_queue.qsize()
        }