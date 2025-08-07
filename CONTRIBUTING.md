# Contributing to Autonomous Development Team

Thank you for your interest in contributing to the Autonomous Development Team project! This document provides guidelines and information for contributors.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/devteam1.git`
3. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the setup script: `./setup.sh`

## Development Setup

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Ollama with required models
- Redis server

### Running Tests
```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=. tests/
```

### Code Style
- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to all public functions and classes
- Keep functions focused and modular

## Contributing Guidelines

### Reporting Issues
- Use the GitHub issue tracker
- Provide detailed reproduction steps
- Include system information and logs
- Use appropriate labels

### Submitting Pull Requests
1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation if needed
6. Commit with clear, descriptive messages
7. Push to your fork and submit a pull request

### Commit Messages
Follow the conventional commits format:
- `feat: add new agent type for deployment`
- `fix: resolve message routing issue`
- `docs: update README with new examples`
- `refactor: improve orchestrator performance`
- `test: add unit tests for developer agent`

## Architecture Guidelines

### Adding New Agent Types
1. Create a new file in `agents/` directory
2. Inherit from `BaseAgent`
3. Implement required abstract methods
4. Add appropriate capabilities
5. Register in orchestrator
6. Add configuration options
7. Write comprehensive tests

### Agent Design Principles
- Single responsibility principle
- Stateless where possible
- Async/await for I/O operations
- Proper error handling and logging
- Context awareness with memory management

### Communication Patterns
- Use message broker for all inter-agent communication
- Implement proper request-response patterns
- Handle message failures gracefully
- Avoid direct agent-to-agent communication

## Testing Guidelines

### Unit Tests
- Test individual agent methods
- Mock external dependencies
- Test error conditions
- Achieve >80% code coverage

### Integration Tests
- Test agent interactions
- Test message flow
- Test orchestrator behavior
- Use test containers for dependencies

### End-to-End Tests
- Test complete workflows
- Test with real LLM models
- Validate output quality
- Performance testing

## Documentation

### Code Documentation
- Add docstrings to all public APIs
- Include parameter and return type information
- Provide usage examples
- Document complex algorithms

### User Documentation
- Update README for new features
- Add configuration examples
- Include troubleshooting guides
- Provide migration guides for breaking changes

## Areas for Contribution

### High Priority
- GitHub integration for repository management
- Enhanced error handling and recovery
- Performance optimizations
- Additional LLM provider support

### Medium Priority
- Advanced planning algorithms
- Multi-project support
- Deployment automation
- Enhanced monitoring

### Good First Issues
- Documentation improvements
- Additional agent types
- Configuration enhancements
- Bug fixes and small features

## Community

### Communication Channels
- GitHub Discussions for general questions
- GitHub Issues for bugs and feature requests
- Pull Request reviews for code discussions

### Code of Conduct
- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Maintain professional communication

## Recognition

Contributors will be recognized in:
- README contributors section
- Release notes
- Project documentation

Thank you for contributing to making autonomous development teams a reality!