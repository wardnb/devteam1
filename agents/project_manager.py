import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
from core.base_agent import BaseAgent, AgentCapability, Message, Task, AgentState


class ProjectManagerAgent(BaseAgent):
    def __init__(self, agent_id: str = None, ollama_host: str = "http://localhost:11434"):
        super().__init__(
            agent_id=agent_id or "pm-001",
            name="Project Manager",
            role="project_manager",
            capabilities=[
                AgentCapability.PROJECT_MANAGEMENT,
                AgentCapability.ARCHITECTURE
            ],
            model_name="llama3.1:8b",
            ollama_host=ollama_host
        )
        self.project_backlog: List[Task] = []
        self.sprint_tasks: List[Task] = []
        self.team_members: Dict[str, Dict[str, Any]] = {}
        self.project_context: Dict[str, Any] = {}
        
    async def initialize(self):
        self.logger.info("Project Manager Agent initialized")
        await self.send_message(
            receiver_id="orchestrator",
            message_type="agent_ready",
            content={
                "agent_id": self.agent_id,
                "capabilities": [c.value for c in self.capabilities]
            }
        )
        
    async def handle_message(self, message: Message):
        self.logger.info(f"Received message: {message.message_type}")
        
        if message.message_type == "new_project":
            await self.handle_new_project(message.content)
        elif message.message_type == "team_member_joined":
            await self.handle_team_member_joined(message.content)
        elif message.message_type == "task_status_update":
            await self.handle_task_status_update(message.content)
        elif message.message_type == "request_task_assignment":
            await self.handle_task_request(message.content)
        elif message.message_type == "progress_report_request":
            await self.generate_progress_report()
            
    async def handle_new_project(self, project_data: Dict[str, Any]):
        self.project_context = project_data
        requirements = project_data.get("requirements", "")
        
        system_prompt = """You are an experienced project manager for a software development team.
        Your task is to break down project requirements into specific, actionable tasks.
        Each task should be clear, measurable, and assignable to team members.
        Format your response as a JSON array of tasks with title, description, priority, and suggested_role fields."""
        
        prompt = f"""Project Requirements:
        {requirements}
        
        Current Team Capabilities:
        - Developers (code generation, code review)
        - Testers (testing, validation)
        - UI Designers (ui design, mockups)
        
        Please break down these requirements into specific development tasks.
        Consider dependencies and prioritize tasks appropriately."""
        
        try:
            response = await self.generate_llm_response(prompt, system_prompt)
            tasks_data = self.parse_llm_tasks(response)
            
            for task_data in tasks_data:
                task = Task(
                    title=task_data.get("title", "Untitled Task"),
                    description=task_data.get("description", ""),
                    priority=task_data.get("priority", 1),
                    metadata={
                        "suggested_role": task_data.get("suggested_role", "developer"),
                        "estimated_hours": task_data.get("estimated_hours", 4)
                    }
                )
                self.project_backlog.append(task)
                
            self.logger.info(f"Created {len(self.project_backlog)} tasks for the project")
            await self.plan_sprint()
            
        except Exception as e:
            self.logger.error(f"Failed to create project tasks: {e}")
            
    def parse_llm_tasks(self, response: str) -> List[Dict[str, Any]]:
        try:
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except:
            pass
            
        tasks = []
        lines = response.split('\n')
        current_task = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('Title:') or line.startswith('- Title:'):
                if current_task:
                    tasks.append(current_task)
                current_task = {"title": line.replace('Title:', '').replace('- Title:', '').strip()}
            elif line.startswith('Description:'):
                current_task["description"] = line.replace('Description:', '').strip()
            elif line.startswith('Priority:'):
                try:
                    current_task["priority"] = int(line.replace('Priority:', '').strip())
                except:
                    current_task["priority"] = 1
            elif line.startswith('Role:'):
                current_task["suggested_role"] = line.replace('Role:', '').strip()
                
        if current_task:
            tasks.append(current_task)
            
        return tasks if tasks else [
            {"title": "Setup project", "description": "Initialize project structure", "priority": 1, "suggested_role": "developer"}
        ]
        
    async def plan_sprint(self):
        available_capacity = len(self.team_members) * 40
        
        self.sprint_tasks = []
        total_hours = 0
        
        sorted_backlog = sorted(self.project_backlog, key=lambda x: x.priority, reverse=True)
        
        for task in sorted_backlog:
            if task.status == "pending":
                estimated_hours = task.metadata.get("estimated_hours", 4)
                if total_hours + estimated_hours <= available_capacity:
                    self.sprint_tasks.append(task)
                    total_hours += estimated_hours
                    
        self.logger.info(f"Planned sprint with {len(self.sprint_tasks)} tasks")
        await self.assign_tasks()
        
    async def assign_tasks(self):
        for task in self.sprint_tasks:
            if task.status == "pending" and not task.assignee_id:
                suggested_role = task.metadata.get("suggested_role", "developer")
                assignee = await self.find_available_team_member(suggested_role)
                
                if assignee:
                    task.assignee_id = assignee
                    task.status = "assigned"
                    
                    await self.send_message(
                        receiver_id=assignee,
                        message_type="task_assignment",
                        content={
                            "task": task.dict(),
                            "context": self.project_context
                        }
                    )
                    
                    self.logger.info(f"Assigned task '{task.title}' to {assignee}")
                    
    async def find_available_team_member(self, preferred_role: str) -> Optional[str]:
        for agent_id, info in self.team_members.items():
            if info.get("state") == "idle" and preferred_role in info.get("role", ""):
                return agent_id
                
        for agent_id, info in self.team_members.items():
            if info.get("state") == "idle":
                return agent_id
                
        return None
        
    async def handle_team_member_joined(self, member_data: Dict[str, Any]):
        agent_id = member_data.get("agent_id")
        self.team_members[agent_id] = {
            "role": member_data.get("role"),
            "capabilities": member_data.get("capabilities", []),
            "state": member_data.get("state", "idle")
        }
        self.logger.info(f"Team member joined: {agent_id}")
        
        if self.sprint_tasks:
            await self.assign_tasks()
            
    async def handle_task_status_update(self, update_data: Dict[str, Any]):
        task_id = update_data.get("task_id")
        new_status = update_data.get("status")
        
        for task in self.sprint_tasks:
            if task.id == task_id:
                task.status = new_status
                if new_status == "completed":
                    task.completed_at = datetime.utcnow()
                    self.add_to_context({
                        "type": "task_completed",
                        "summary": f"Task '{task.title}' completed by {task.assignee_id}",
                        "task_id": task_id
                    })
                break
                
        await self.check_sprint_progress()
        
    async def handle_task_request(self, request_data: Dict[str, Any]):
        requesting_agent = request_data.get("agent_id")
        
        for task in self.sprint_tasks:
            if task.status == "pending" and not task.assignee_id:
                task.assignee_id = requesting_agent
                task.status = "assigned"
                
                await self.send_message(
                    receiver_id=requesting_agent,
                    message_type="task_assignment",
                    content={
                        "task": task.dict(),
                        "context": self.project_context
                    }
                )
                return
                
        await self.send_message(
            receiver_id=requesting_agent,
            message_type="no_tasks_available",
            content={"message": "No tasks currently available"}
        )
        
    async def check_sprint_progress(self):
        completed = sum(1 for task in self.sprint_tasks if task.status == "completed")
        total = len(self.sprint_tasks)
        
        if completed == total and total > 0:
            self.logger.info("Sprint completed!")
            await self.generate_sprint_report()
            await self.plan_sprint()
            
    async def generate_progress_report(self):
        completed_tasks = [t for t in self.sprint_tasks if t.status == "completed"]
        in_progress_tasks = [t for t in self.sprint_tasks if t.status in ["assigned", "in_progress"]]
        pending_tasks = [t for t in self.sprint_tasks if t.status == "pending"]
        
        report = {
            "sprint_progress": {
                "completed": len(completed_tasks),
                "in_progress": len(in_progress_tasks),
                "pending": len(pending_tasks),
                "total": len(self.sprint_tasks)
            },
            "backlog_size": len(self.project_backlog),
            "team_status": self.team_members,
            "recent_completions": [
                {"title": t.title, "completed_at": t.completed_at.isoformat() if t.completed_at else None}
                for t in completed_tasks[-5:]
            ]
        }
        
        await self.send_message(
            receiver_id="orchestrator",
            message_type="progress_report",
            content=report
        )
        
        return report
        
    async def generate_sprint_report(self):
        prompt = f"""Generate a sprint retrospective summary based on the following completed tasks:
        {json.dumps([t.dict() for t in self.sprint_tasks if t.status == "completed"], default=str)}
        
        Include: accomplishments, challenges, and recommendations for the next sprint."""
        
        summary = await self.generate_llm_response(prompt)
        
        await self.send_message(
            receiver_id="orchestrator",
            message_type="sprint_completed",
            content={
                "summary": summary,
                "tasks_completed": len([t for t in self.sprint_tasks if t.status == "completed"]),
                "sprint_velocity": sum(t.metadata.get("estimated_hours", 0) for t in self.sprint_tasks if t.status == "completed")
            }
        )
        
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        if task.title == "Review Project Status":
            return await self.generate_progress_report()
        elif task.title == "Plan Sprint":
            await self.plan_sprint()
            return {"status": "Sprint planned", "tasks": len(self.sprint_tasks)}
        else:
            return {"status": "Task executed by Project Manager"}