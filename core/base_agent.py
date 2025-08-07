import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog
from pydantic import BaseModel, Field
from enum import Enum
import ollama
from tenacity import retry, stop_after_attempt, wait_exponential


class AgentState(Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    OFFLINE = "offline"


class AgentCapability(Enum):
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    UI_DESIGN = "ui_design"
    ARCHITECTURE = "architecture"
    PROJECT_MANAGEMENT = "project_management"
    DOCUMENTATION = "documentation"
    DEPLOYMENT = "deployment"


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    receiver_id: Optional[str] = None
    message_type: str
    content: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    requires_response: bool = False
    correlation_id: Optional[str] = None


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    assignee_id: Optional[str] = None
    status: str = "pending"
    priority: int = 1
    dependencies: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    def __init__(
        self, 
        agent_id: str,
        name: str,
        role: str,
        capabilities: List[AgentCapability],
        model_name: str = "llama3.1:8b",
        ollama_host: str = "http://localhost:11434"
    ):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.model_name = model_name
        self.ollama_host = ollama_host
        self.state = AgentState.IDLE
        self.current_task: Optional[Task] = None
        self.task_history: List[Task] = []
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.logger = structlog.get_logger().bind(agent_id=self.agent_id, role=self.role)
        self.ollama_client = ollama.Client(host=ollama_host)
        self.running = False
        self.context_memory: List[Dict[str, Any]] = []
        self.max_context_size = 10
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_llm_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
            )
            return response['message']['content']
        except Exception as e:
            self.logger.error(f"LLM generation failed: {e}")
            raise
            
    def add_to_context(self, item: Dict[str, Any]):
        self.context_memory.append(item)
        if len(self.context_memory) > self.max_context_size:
            self.context_memory.pop(0)
            
    def get_context_summary(self) -> str:
        if not self.context_memory:
            return "No previous context."
        context_items = []
        for item in self.context_memory[-5:]:
            context_items.append(f"- {item.get('type', 'unknown')}: {item.get('summary', 'N/A')}")
        return "\n".join(context_items)
        
    async def send_message(self, receiver_id: str, message_type: str, content: Dict[str, Any], requires_response: bool = False) -> Optional[Message]:
        message = Message(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
            requires_response=requires_response
        )
        await self.broadcast_message(message)
        if requires_response:
            return await self.wait_for_response(message.id)
        return None
        
    async def broadcast_message(self, message: Message):
        self.logger.info(f"Broadcasting message", message_type=message.message_type, receiver=message.receiver_id)
        
    async def wait_for_response(self, correlation_id: str, timeout: int = 30) -> Optional[Message]:
        try:
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < timeout:
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=1)
                    if message.correlation_id == correlation_id:
                        return message
                    else:
                        await self.message_queue.put(message)
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            self.logger.error(f"Error waiting for response: {e}")
        return None
        
    async def receive_message(self, message: Message):
        await self.message_queue.put(message)
        
    async def process_messages(self):
        while self.running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1)
                await self.handle_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
                
    @abstractmethod
    async def handle_message(self, message: Message):
        pass
        
    @abstractmethod
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        pass
        
    async def start_task(self, task: Task):
        self.current_task = task
        self.state = AgentState.WORKING
        self.logger.info(f"Starting task: {task.title}")
        
        try:
            self.add_to_context({
                "type": "task_start",
                "summary": f"Started task: {task.title}",
                "task_id": task.id
            })
            
            result = await self.execute_task(task)
            
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            task.result = result
            
            self.add_to_context({
                "type": "task_complete",
                "summary": f"Completed task: {task.title}",
                "task_id": task.id,
                "success": True
            })
            
            await self.send_message(
                receiver_id="orchestrator",
                message_type="task_completed",
                content={
                    "task_id": task.id,
                    "agent_id": self.agent_id,
                    "result": result
                }
            )
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            task.status = "failed"
            
            self.add_to_context({
                "type": "task_failed",
                "summary": f"Failed task: {task.title} - {str(e)}",
                "task_id": task.id,
                "error": str(e)
            })
            
            await self.send_message(
                receiver_id="orchestrator",
                message_type="task_failed",
                content={
                    "task_id": task.id,
                    "agent_id": self.agent_id,
                    "error": str(e)
                }
            )
            
        finally:
            self.task_history.append(task)
            self.current_task = None
            self.state = AgentState.IDLE
            
    async def request_assistance(self, capability_needed: AgentCapability, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = await self.send_message(
            receiver_id="orchestrator",
            message_type="assistance_request",
            content={
                "requesting_agent": self.agent_id,
                "capability_needed": capability_needed.value,
                "context": context
            },
            requires_response=True
        )
        
        if response and response.content.get("status") == "success":
            return response.content.get("result")
        return None
        
    async def report_status(self):
        await self.send_message(
            receiver_id="orchestrator",
            message_type="status_update",
            content={
                "agent_id": self.agent_id,
                "state": self.state.value,
                "current_task": self.current_task.id if self.current_task else None,
                "capabilities": [c.value for c in self.capabilities]
            }
        )
        
    async def start(self):
        self.running = True
        self.state = AgentState.IDLE
        self.logger.info(f"Agent {self.name} started")
        
        asyncio.create_task(self.process_messages())
        asyncio.create_task(self.heartbeat())
        
        await self.initialize()
        
    async def stop(self):
        self.running = False
        self.state = AgentState.OFFLINE
        self.logger.info(f"Agent {self.name} stopped")
        
    async def heartbeat(self):
        while self.running:
            await self.report_status()
            await asyncio.sleep(10)
            
    @abstractmethod
    async def initialize(self):
        pass
        
    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.agent_id} name={self.name} state={self.state.value}>"