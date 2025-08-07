#!/usr/bin/env python3

import asyncio
import argparse
import os
import sys
from pathlib import Path
import structlog
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestration.orchestrator import Orchestrator
from agents.project_manager import ProjectManagerAgent
from agents.developer import DeveloperAgent
from agents.tester import TesterAgent
from agents.ui_designer import UIDesignerAgent
from communication.message_broker import MessageBroker


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


async def run_orchestrator(config_path: str = "./configs/config.yaml"):
    """Run the main orchestrator"""
    logger = structlog.get_logger()
    logger.info("Starting Orchestrator")
    
    orchestrator = Orchestrator(config_path)
    
    try:
        await orchestrator.start()
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(10)
            metrics = orchestrator.get_metrics()
            logger.info("Orchestrator metrics", **metrics)
            
    except KeyboardInterrupt:
        logger.info("Shutting down Orchestrator")
        await orchestrator.stop()
        

async def run_agent(agent_type: str, agent_id: Optional[str] = None):
    """Run a specific agent"""
    logger = structlog.get_logger()
    
    # Get configuration from environment variables
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    # Create message broker
    message_broker = MessageBroker(redis_host, redis_port)
    await message_broker.connect()
    
    # Create appropriate agent
    agent_classes = {
        "project_manager": ProjectManagerAgent,
        "developer": DeveloperAgent,
        "tester": TesterAgent,
        "ui_designer": UIDesignerAgent
    }
    
    agent_class = agent_classes.get(agent_type)
    if not agent_class:
        logger.error(f"Unknown agent type: {agent_type}")
        return
        
    agent = agent_class(agent_id=agent_id, ollama_host=ollama_host)
    
    # Register with message broker
    await message_broker.register_agent(agent.agent_id)
    
    # Setup message routing
    async def handle_message(msg_data):
        from core.base_agent import Message
        message = Message(**msg_data)
        await agent.receive_message(message)
        
    await message_broker.subscribe_agent(agent.agent_id, handle_message)
    
    # Override agent's broadcast method to use message broker
    original_broadcast = agent.broadcast_message
    async def new_broadcast(message):
        await message_broker.publish_message(message)
    agent.broadcast_message = new_broadcast
    
    try:
        # Start agent
        await agent.start()
        logger.info(f"Started {agent_type} agent: {agent.agent_id}")
        
        # Start message broker listener
        asyncio.create_task(message_broker.start_listening())
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(10)
            await agent.report_status()
            
    except KeyboardInterrupt:
        logger.info(f"Shutting down agent {agent.agent_id}")
        await agent.stop()
        await message_broker.unregister_agent(agent.agent_id)
        await message_broker.disconnect()
        

async def run_interactive_cli():
    """Run interactive CLI for managing the dev team"""
    logger = structlog.get_logger()
    logger.info("Starting Interactive CLI")
    
    orchestrator = Orchestrator()
    await orchestrator.start()
    
    print("\n" + "="*60)
    print("🤖 Autonomous Development Team - Interactive CLI")
    print("="*60)
    print("\nCommands:")
    print("  start <requirements> - Start a new project")
    print("  status              - Show team status")
    print("  metrics             - Show performance metrics")
    print("  agents              - List all agents")
    print("  spawn <type>        - Spawn a new agent")
    print("  help                - Show this help message")
    print("  quit                - Exit the program")
    print("="*60 + "\n")
    
    try:
        while True:
            command = input("devteam> ").strip()
            
            if not command:
                continue
                
            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "help":
                print("\nCommands:")
                print("  start <requirements> - Start a new project")
                print("  status              - Show team status")
                print("  metrics             - Show performance metrics")
                print("  agents              - List all agents")
                print("  spawn <type>        - Spawn a new agent")
                print("  help                - Show this help message")
                print("  quit                - Exit the program\n")
            elif cmd == "start":
                if len(parts) > 1:
                    requirements = parts[1]
                    print(f"Starting new project with requirements: {requirements}")
                    await orchestrator.start_project(requirements)
                else:
                    print("Usage: start <requirements>")
            elif cmd == "status":
                online_agents = await orchestrator.message_broker.get_online_agents()
                print(f"\nOnline Agents: {len(online_agents)}")
                for agent_id in online_agents:
                    if agent_id in orchestrator.agents:
                        agent = orchestrator.agents[agent_id]
                        print(f"  - {agent_id}: {agent.role} ({agent.state.value})")
            elif cmd == "metrics":
                metrics = orchestrator.get_metrics()
                print("\nSystem Metrics:")
                for key, value in metrics.items():
                    print(f"  {key}: {value}")
            elif cmd == "agents":
                print(f"\nTotal Agents: {len(orchestrator.agents)}")
                for agent_id, agent in orchestrator.agents.items():
                    print(f"  - {agent_id}: {agent.role} ({agent.state.value})")
                    print(f"    Capabilities: {[c.value for c in agent.capabilities]}")
            elif cmd == "spawn":
                if len(parts) > 1:
                    agent_type = parts[1].lower()
                    agent_map = {
                        "developer": DeveloperAgent,
                        "tester": TesterAgent,
                        "ui": UIDesignerAgent,
                        "pm": ProjectManagerAgent
                    }
                    if agent_type in agent_map:
                        new_agent = await orchestrator.spawn_agent(agent_map[agent_type])
                        print(f"Spawned new agent: {new_agent.agent_id}")
                    else:
                        print(f"Unknown agent type: {agent_type}")
                        print("Available types: developer, tester, ui, pm")
                else:
                    print("Usage: spawn <type>")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
                
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        await orchestrator.stop()
        

async def run_example_project():
    """Run an example project to demonstrate the system"""
    logger = structlog.get_logger()
    logger.info("Running example project")
    
    orchestrator = Orchestrator()
    await orchestrator.start()
    
    # Example project requirements
    project_requirements = """
    Create a simple Todo List web application with the following features:
    1. User can add new todo items
    2. User can mark items as complete
    3. User can delete items
    4. User can filter items by status (all, active, completed)
    5. Responsive design for mobile and desktop
    6. Data persistence using local storage
    7. Clean and intuitive user interface
    8. Comprehensive test coverage
    """
    
    logger.info("Starting Todo List project")
    await orchestrator.start_project(project_requirements)
    
    # Let the team work for a while
    for i in range(30):
        await asyncio.sleep(10)
        metrics = orchestrator.get_metrics()
        logger.info(f"Progress update {i+1}/30", **metrics)
        
        if metrics["completed_tasks"] >= 10:
            logger.info("Project milestone reached!")
            break
            
    # Show final results
    logger.info("Project completed!")
    metrics = orchestrator.get_metrics()
    logger.info("Final metrics", **metrics)
    
    await orchestrator.stop()
    

def main():
    parser = argparse.ArgumentParser(description="Autonomous Development Team")
    parser.add_argument("--mode", choices=["orchestrator", "agent", "interactive", "example"],
                      default="interactive",
                      help="Run mode: orchestrator, agent, interactive CLI, or example")
    parser.add_argument("--type", choices=["project_manager", "developer", "tester", "ui_designer"],
                      help="Agent type (required for agent mode)")
    parser.add_argument("--id", help="Agent ID (optional for agent mode)")
    parser.add_argument("--config", default="./configs/config.yaml",
                      help="Path to configuration file")
    
    args = parser.parse_args()
    
    if args.mode == "orchestrator":
        asyncio.run(run_orchestrator(args.config))
    elif args.mode == "agent":
        if not args.type:
            print("Error: --type is required for agent mode")
            sys.exit(1)
        asyncio.run(run_agent(args.type, args.id))
    elif args.mode == "interactive":
        asyncio.run(run_interactive_cli())
    elif args.mode == "example":
        asyncio.run(run_example_project())
        

if __name__ == "__main__":
    main()