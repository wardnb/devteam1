import asyncio
import json
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import redis.asyncio as redis
from collections import defaultdict
import structlog
from core.base_agent import Message


class MessageBroker:
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_client: Optional[redis.Redis] = None
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.agent_channels: Dict[str, str] = {}
        self.logger = structlog.get_logger()
        self.running = False
        self.pubsub: Optional[redis.client.PubSub] = None
        
    async def connect(self):
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True
            )
            await self.redis_client.ping()
            self.pubsub = self.redis_client.pubsub()
            self.logger.info("Connected to Redis message broker")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            self.logger.info("Falling back to in-memory message broker")
            self.redis_client = None
            
    async def disconnect(self):
        if self.redis_client:
            if self.pubsub:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()
            await self.redis_client.close()
            
    async def register_agent(self, agent_id: str, channel: str = None):
        channel = channel or f"agent_{agent_id}"
        self.agent_channels[agent_id] = channel
        
        if self.redis_client:
            await self.redis_client.set(f"agent:{agent_id}:channel", channel)
            await self.redis_client.set(f"agent:{agent_id}:status", "online")
            await self.redis_client.set(f"agent:{agent_id}:last_seen", datetime.utcnow().isoformat())
            
        self.logger.info(f"Registered agent {agent_id} on channel {channel}")
        
    async def unregister_agent(self, agent_id: str):
        if agent_id in self.agent_channels:
            del self.agent_channels[agent_id]
            
        if self.redis_client:
            await self.redis_client.set(f"agent:{agent_id}:status", "offline")
            
        self.logger.info(f"Unregistered agent {agent_id}")
        
    async def publish_message(self, message: Message):
        serialized = json.dumps(message.dict(), default=str)
        
        if message.receiver_id:
            channel = self.agent_channels.get(message.receiver_id, f"agent_{message.receiver_id}")
            await self._publish_to_channel(channel, serialized)
        else:
            await self._publish_to_channel("broadcast", serialized)
            
        await self._store_message(message)
        
    async def _publish_to_channel(self, channel: str, message: str):
        if self.redis_client:
            await self.redis_client.publish(channel, message)
        else:
            for callback in self.subscribers.get(channel, []):
                await callback(json.loads(message))
                
    async def _store_message(self, message: Message):
        if self.redis_client:
            key = f"messages:{message.sender_id}:{message.receiver_id or 'broadcast'}"
            await self.redis_client.lpush(key, json.dumps(message.dict(), default=str))
            await self.redis_client.ltrim(key, 0, 99)
            
    async def subscribe_to_channel(self, channel: str, callback: Callable):
        if self.redis_client and self.pubsub:
            await self.pubsub.subscribe(channel)
            self.subscribers[channel].append(callback)
        else:
            self.subscribers[channel].append(callback)
            
    async def subscribe_agent(self, agent_id: str, callback: Callable):
        channel = self.agent_channels.get(agent_id, f"agent_{agent_id}")
        await self.subscribe_to_channel(channel, callback)
        await self.subscribe_to_channel("broadcast", callback)
        
    async def get_message_history(self, agent_id: str, limit: int = 10) -> List[Message]:
        if not self.redis_client:
            return []
            
        messages = []
        
        pattern = f"messages:*:{agent_id}"
        keys = []
        async for key in self.redis_client.scan_iter(match=pattern):
            keys.append(key)
            
        pattern = f"messages:{agent_id}:*"
        async for key in self.redis_client.scan_iter(match=pattern):
            keys.append(key)
            
        for key in keys[:limit]:
            raw_messages = await self.redis_client.lrange(key, 0, limit - 1)
            for raw_msg in raw_messages:
                try:
                    msg_data = json.loads(raw_msg)
                    messages.append(Message(**msg_data))
                except:
                    pass
                    
        return sorted(messages, key=lambda x: x.timestamp, reverse=True)[:limit]
        
    async def start_listening(self):
        if not self.redis_client or not self.pubsub:
            return
            
        self.running = True
        
        while self.running:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                if message and message['type'] == 'message':
                    channel = message['channel']
                    data = json.loads(message['data'])
                    
                    for callback in self.subscribers.get(channel, []):
                        asyncio.create_task(callback(data))
                        
            except Exception as e:
                self.logger.error(f"Error in message listener: {e}")
                await asyncio.sleep(1)
                
    async def stop_listening(self):
        self.running = False
        
    async def create_task_queue(self, queue_name: str):
        if self.redis_client:
            await self.redis_client.delete(f"queue:{queue_name}")
            
    async def add_task_to_queue(self, queue_name: str, task: Dict[str, Any]):
        if self.redis_client:
            await self.redis_client.rpush(f"queue:{queue_name}", json.dumps(task, default=str))
        else:
            if queue_name not in self.subscribers:
                self.subscribers[queue_name] = []
                
    async def get_task_from_queue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        if self.redis_client:
            task_data = await self.redis_client.lpop(f"queue:{queue_name}")
            if task_data:
                return json.loads(task_data)
        return None
        
    async def get_queue_length(self, queue_name: str) -> int:
        if self.redis_client:
            return await self.redis_client.llen(f"queue:{queue_name}")
        return 0
        
    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        event_message = Message(
            sender_id="system",
            receiver_id=None,
            message_type=f"event:{event_type}",
            content=data
        )
        await self.publish_message(event_message)
        
    async def get_online_agents(self) -> List[str]:
        online_agents = []
        
        if self.redis_client:
            pattern = "agent:*:status"
            async for key in self.redis_client.scan_iter(match=pattern):
                status = await self.redis_client.get(key)
                if status == "online":
                    agent_id = key.split(":")[1]
                    online_agents.append(agent_id)
        else:
            online_agents = list(self.agent_channels.keys())
            
        return online_agents
        
    async def send_direct_message(self, sender_id: str, receiver_id: str, content: Dict[str, Any]):
        message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="direct_message",
            content=content
        )
        await self.publish_message(message)
        
    async def request_response(self, sender_id: str, receiver_id: str, request: Dict[str, Any], timeout: int = 30) -> Optional[Dict[str, Any]]:
        correlation_id = str(uuid.uuid4())
        
        message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="request",
            content=request,
            requires_response=True,
            correlation_id=correlation_id
        )
        
        response_channel = f"response:{correlation_id}"
        response_received = asyncio.Event()
        response_data = {"data": None}
        
        async def response_handler(msg_data):
            response_data["data"] = msg_data
            response_received.set()
            
        await self.subscribe_to_channel(response_channel, response_handler)
        await self.publish_message(message)
        
        try:
            await asyncio.wait_for(response_received.wait(), timeout=timeout)
            return response_data["data"]
        except asyncio.TimeoutError:
            self.logger.warning(f"Request timeout for correlation_id: {correlation_id}")
            return None
        finally:
            if self.redis_client and self.pubsub:
                await self.pubsub.unsubscribe(response_channel)