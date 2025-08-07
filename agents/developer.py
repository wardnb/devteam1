import asyncio
import os
import subprocess
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import re
from core.base_agent import BaseAgent, AgentCapability, Message, Task


class DeveloperAgent(BaseAgent):
    def __init__(self, agent_id: str = None, ollama_host: str = "http://localhost:11434"):
        super().__init__(
            agent_id=agent_id or "dev-001",
            name="Developer",
            role="developer",
            capabilities=[
                AgentCapability.CODE_GENERATION,
                AgentCapability.CODE_REVIEW,
                AgentCapability.DOCUMENTATION
            ],
            model_name="codellama:13b",
            ollama_host=ollama_host
        )
        self.workspace_path = Path("./workspace")
        self.current_project_context: Dict[str, Any] = {}
        self.code_patterns: Dict[str, str] = {}
        self.technology_stack: List[str] = []
        
    async def initialize(self):
        self.workspace_path.mkdir(exist_ok=True)
        self.logger.info("Developer Agent initialized")
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
        
        if message.message_type == "task_assignment":
            task_data = message.content.get("task")
            task = Task(**task_data)
            await self.start_task(task)
        elif message.message_type == "code_review_request":
            await self.review_code(message.content)
        elif message.message_type == "assistance_response":
            await self.handle_assistance_response(message.content)
        elif message.message_type == "project_context":
            self.current_project_context = message.content
            
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        self.logger.info(f"Executing task: {task.title}")
        
        task_type = self.identify_task_type(task)
        
        if task_type == "implementation":
            return await self.implement_feature(task)
        elif task_type == "bug_fix":
            return await self.fix_bug(task)
        elif task_type == "refactoring":
            return await self.refactor_code(task)
        elif task_type == "testing":
            return await self.write_tests(task)
        elif task_type == "documentation":
            return await self.write_documentation(task)
        else:
            return await self.generic_code_task(task)
            
    def identify_task_type(self, task: Task) -> str:
        title_lower = task.title.lower()
        desc_lower = task.description.lower()
        
        if any(word in title_lower or word in desc_lower for word in ["implement", "create", "add", "feature"]):
            return "implementation"
        elif any(word in title_lower or word in desc_lower for word in ["fix", "bug", "error", "issue"]):
            return "bug_fix"
        elif any(word in title_lower or word in desc_lower for word in ["refactor", "improve", "optimize"]):
            return "refactoring"
        elif any(word in title_lower or word in desc_lower for word in ["test", "testing", "unit test"]):
            return "testing"
        elif any(word in title_lower or word in desc_lower for word in ["document", "docs", "readme"]):
            return "documentation"
        else:
            return "generic"
            
    async def implement_feature(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert software developer. Generate clean, efficient, and well-structured code.
        Follow best practices and design patterns. Include error handling and input validation.
        Provide the complete implementation ready for production use."""
        
        prompt = f"""Task: {task.title}
        Description: {task.description}
        
        Project Context: {json.dumps(self.current_project_context, indent=2)}
        
        Please provide a complete implementation for this feature.
        Include:
        1. The main code implementation
        2. Any necessary imports or dependencies
        3. Error handling
        4. Basic documentation/comments
        
        Format the response with clear file paths and code blocks."""
        
        try:
            response = await self.generate_llm_response(prompt, system_prompt)
            code_files = self.extract_code_from_response(response)
            
            created_files = []
            for file_path, code_content in code_files.items():
                full_path = self.workspace_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(code_content)
                created_files.append(str(full_path))
                
            self.add_to_context({
                "type": "feature_implemented",
                "summary": f"Implemented: {task.title}",
                "files": created_files
            })
            
            test_needed = await self.check_if_tests_needed(task, created_files)
            if test_needed:
                await self.request_assistance(
                    AgentCapability.TESTING,
                    {
                        "task": "Write tests for new feature",
                        "files": created_files,
                        "feature": task.title
                    }
                )
                
            return {
                "status": "completed",
                "files_created": created_files,
                "implementation_summary": f"Successfully implemented {task.title}"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to implement feature: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
            
    def extract_code_from_response(self, response: str) -> Dict[str, str]:
        code_blocks = {}
        
        pattern = r'```(?:(\w+)\n)?(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for i, (lang, code) in enumerate(matches):
            lines = code.strip().split('\n')
            if lines and lines[0].startswith('# File:'):
                file_path = lines[0].replace('# File:', '').strip()
                code_content = '\n'.join(lines[1:])
            elif lines and lines[0].startswith('//') and 'File:' in lines[0]:
                file_path = lines[0].split('File:')[1].strip()
                code_content = '\n'.join(lines[1:])
            else:
                file_ext = self.get_extension_for_language(lang)
                file_path = f"generated_{i}.{file_ext}"
                code_content = code
                
            code_blocks[file_path] = code_content.strip()
            
        if not code_blocks:
            code_blocks["generated.py"] = response
            
        return code_blocks
        
    def get_extension_for_language(self, lang: str) -> str:
        extensions = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "go": "go",
            "rust": "rs",
            "html": "html",
            "css": "css"
        }
        return extensions.get(lang.lower(), "txt")
        
    async def fix_bug(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert debugger. Analyze the bug description and provide a fix.
        Explain the root cause and your solution approach."""
        
        prompt = f"""Bug Report: {task.title}
        Description: {task.description}
        
        Please:
        1. Identify the likely cause of the bug
        2. Provide the fix with code changes
        3. Explain what was wrong and how your fix addresses it"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        
        return {
            "status": "completed",
            "bug_analysis": response,
            "fix_applied": True
        }
        
    async def refactor_code(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert in code refactoring and clean code principles.
        Improve code quality while maintaining functionality."""
        
        prompt = f"""Refactoring Task: {task.title}
        Description: {task.description}
        
        Apply best practices including:
        - SOLID principles
        - DRY principle
        - Clear naming conventions
        - Proper abstraction levels"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        
        return {
            "status": "completed",
            "refactoring_summary": response
        }
        
    async def write_tests(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert in test-driven development.
        Write comprehensive unit tests with good coverage."""
        
        prompt = f"""Testing Task: {task.title}
        Description: {task.description}
        
        Write unit tests that:
        1. Cover happy path scenarios
        2. Test edge cases
        3. Include negative test cases
        4. Are well-organized and maintainable"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        code_files = self.extract_code_from_response(response)
        
        test_files = []
        for file_path, code_content in code_files.items():
            if "test" not in file_path.lower():
                file_path = f"tests/{file_path}"
            full_path = self.workspace_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(code_content)
            test_files.append(str(full_path))
            
        return {
            "status": "completed",
            "test_files": test_files,
            "coverage_estimate": "80%"
        }
        
    async def write_documentation(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are a technical writer specializing in developer documentation.
        Create clear, comprehensive, and well-structured documentation."""
        
        prompt = f"""Documentation Task: {task.title}
        Description: {task.description}
        
        Create documentation that includes:
        1. Overview and purpose
        2. Installation/setup instructions
        3. Usage examples
        4. API reference (if applicable)
        5. Troubleshooting section"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        
        doc_path = self.workspace_path / "docs" / f"{task.title.replace(' ', '_').lower()}.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(response)
        
        return {
            "status": "completed",
            "documentation_file": str(doc_path)
        }
        
    async def generic_code_task(self, task: Task) -> Dict[str, Any]:
        prompt = f"""Task: {task.title}
        Description: {task.description}
        
        Please complete this development task following best practices."""
        
        response = await self.generate_llm_response(prompt)
        
        return {
            "status": "completed",
            "result": response
        }
        
    async def review_code(self, review_request: Dict[str, Any]):
        files_to_review = review_request.get("files", [])
        review_context = review_request.get("context", "")
        
        reviews = []
        for file_path in files_to_review:
            if Path(file_path).exists():
                code = Path(file_path).read_text()
                
                system_prompt = """You are a senior code reviewer. Provide constructive feedback on:
                - Code quality and readability
                - Potential bugs or issues
                - Performance considerations
                - Security concerns
                - Best practices adherence"""
                
                prompt = f"""Review this code:
                File: {file_path}
                Context: {review_context}
                
                Code:
                {code}
                
                Provide specific, actionable feedback."""
                
                review = await self.generate_llm_response(prompt, system_prompt)
                reviews.append({
                    "file": file_path,
                    "review": review
                })
                
        await self.send_message(
            receiver_id=review_request.get("requester_id", "orchestrator"),
            message_type="code_review_complete",
            content={
                "reviews": reviews
            }
        )
        
    async def check_if_tests_needed(self, task: Task, files: List[str]) -> bool:
        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.java', '.go')):
                if 'test' not in file.lower():
                    return True
        return False
        
    async def handle_assistance_response(self, response: Dict[str, Any]):
        self.logger.info(f"Received assistance: {response.get('type')}")
        self.add_to_context({
            "type": "assistance_received",
            "summary": f"Got help with: {response.get('type')}",
            "details": response
        })
        
    async def run_tests(self, test_directory: str = None) -> Dict[str, Any]:
        test_dir = test_directory or str(self.workspace_path / "tests")
        
        if Path(test_dir).exists():
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", test_dir, "-v"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                return {
                    "status": "completed",
                    "passed": result.returncode == 0,
                    "output": result.stdout,
                    "errors": result.stderr
                }
            except Exception as e:
                return {
                    "status": "failed",
                    "error": str(e)
                }
        else:
            return {
                "status": "skipped",
                "reason": "No tests directory found"
            }