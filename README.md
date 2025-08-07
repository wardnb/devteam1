# Autonomous Development Team

A fully autonomous AI development team using local LLMs to collaborate on software projects without human intervention.

## Features

- **Autonomous Coordination**: Agents work together without human oversight
- **Specialized Roles**: Project Manager, Developers, Testers, UI Designers
- **Dynamic Team Scaling**: Automatically recruits additional agents as needed
- **Inter-Agent Communication**: Redis-based message broker for agent coordination
- **Task Management**: Automatic task breakdown, assignment, and tracking
- **Quality Assurance**: Built-in testing and code review processes
- **Containerized Deployment**: Docker support for easy scaling

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Orchestrator                        │
│  - Agent Management                                      │
│  - Task Distribution                                     │
│  - Performance Monitoring                                │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │    Message Broker       │
        │      (Redis)            │
        └────────────┬────────────┘
                     │
    ┌────────────────┼────────────────┬─────────────┬──────────────┐
    │                │                │             │              │
┌───▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐  ┌──▼──────┐  ┌────▼────┐
│  Project │  │ Developer  │  │ Developer  │  │ Tester  │  │   UI    │
│  Manager │  │  Agent 1   │  │  Agent 2   │  │  Agent  │  │Designer │
└──────────┘  └────────────┘  └────────────┘  └─────────┘  └─────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Ollama (for local LLM hosting)
- Redis (or use Docker)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd autonomous-dev-team
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install and configure Ollama:
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required models
ollama pull llama3.1:8b
ollama pull codellama:13b
```

### Running with Docker

1. Start all services:
```bash
cd docker
docker-compose up -d
```

2. View logs:
```bash
docker-compose logs -f
```

3. Stop services:
```bash
docker-compose down
```

### Running Locally

1. Start Redis:
```bash
redis-server
```

2. Start Ollama:
```bash
ollama serve
```

3. Run interactive CLI:
```bash
python main.py --mode interactive
```

## Usage

### Interactive CLI

The interactive CLI provides commands to manage your autonomous dev team:

```bash
python main.py --mode interactive
```

Commands:
- `start <requirements>` - Start a new project with given requirements
- `status` - Show current team status
- `metrics` - Display performance metrics
- `agents` - List all agents and their states
- `spawn <type>` - Manually spawn a new agent (developer/tester/ui/pm)
- `help` - Show help message
- `quit` - Exit the program

### Example Project

Run the built-in example Todo List project:

```bash
python main.py --mode example
```

### Starting a Custom Project

```python
# In interactive mode
devteam> start Create a REST API for a blog with user authentication, posts, comments, and categories. Include full CRUD operations and comprehensive testing.
```

## Agent Types

### Project Manager
- Breaks down requirements into tasks
- Assigns tasks to team members
- Tracks project progress
- Coordinates between agents
- Plans sprints

### Developer
- Implements features
- Writes code
- Performs code reviews
- Creates documentation
- Refactors code

### Tester/QA
- Creates test cases
- Executes tests
- Reports bugs
- Validates implementations
- Checks accessibility

### UI/UX Designer
- Creates mockups
- Designs components
- Ensures responsive design
- Validates accessibility
- Creates style guides

## Configuration

Edit `configs/config.yaml` to customize:

- LLM models and parameters
- Agent settings and capabilities
- Communication settings
- Orchestration parameters
- Recruitment policies

## Project Structure

```
autonomous-dev-team/
├── agents/              # Agent implementations
├── core/                # Core abstractions
├── communication/       # Message broker
├── orchestration/       # Orchestrator logic
├── configs/            # Configuration files
├── docker/             # Docker configurations
├── workspace/          # Agent working directory
├── logs/               # Application logs
└── examples/           # Example projects
```

## Development

### Adding New Agent Types

1. Create new agent class inheriting from `BaseAgent`
2. Implement required methods (`execute_task`, `handle_message`, etc.)
3. Register in orchestrator's agent map
4. Update configuration

### Extending Capabilities

1. Add new capability to `AgentCapability` enum
2. Update agents to support new capability
3. Modify task routing in orchestrator

## Monitoring

View real-time metrics:
- Tasks completed/failed
- Agent utilization
- Sprint velocity
- System performance

## Troubleshooting

### Agents not communicating
- Check Redis connection
- Verify network configuration
- Review agent logs

### LLM errors
- Ensure Ollama is running
- Verify models are downloaded
- Check memory availability

### Task failures
- Review agent logs
- Check task dependencies
- Verify agent capabilities match requirements

## License

MIT License

## Contributing

Contributions welcome! Please submit pull requests with:
- New agent types
- Improved coordination algorithms
- Additional LLM integrations
- Performance optimizations

## Roadmap

- [ ] Web UI for monitoring
- [ ] Support for more LLM providers
- [ ] Advanced planning algorithms
- [ ] Integration with Git/GitHub
- [ ] Deployment automation
- [ ] Performance analytics dashboard
- [ ] Multi-project support
- [ ] Agent learning and improvement