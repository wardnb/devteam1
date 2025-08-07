import asyncio
import subprocess
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import re
from core.base_agent import BaseAgent, AgentCapability, Message, Task


class TesterAgent(BaseAgent):
    def __init__(self, agent_id: str = None, ollama_host: str = "http://localhost:11434"):
        super().__init__(
            agent_id=agent_id or "qa-001",
            name="Tester",
            role="tester",
            capabilities=[
                AgentCapability.TESTING,
                AgentCapability.DOCUMENTATION
            ],
            model_name="llama3.1:8b",
            ollama_host=ollama_host
        )
        self.test_results: List[Dict[str, Any]] = []
        self.test_coverage: Dict[str, float] = {}
        self.bug_reports: List[Dict[str, Any]] = []
        self.test_workspace = Path("./workspace/tests")
        
    async def initialize(self):
        self.test_workspace.mkdir(parents=True, exist_ok=True)
        self.logger.info("Tester Agent initialized")
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
        elif message.message_type == "test_request":
            await self.run_tests(message.content)
        elif message.message_type == "validation_request":
            await self.validate_implementation(message.content)
            
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        self.logger.info(f"Executing testing task: {task.title}")
        
        task_type = self.identify_test_type(task)
        
        if task_type == "unit_test":
            return await self.create_unit_tests(task)
        elif task_type == "integration_test":
            return await self.create_integration_tests(task)
        elif task_type == "ui_test":
            return await self.create_ui_tests(task)
        elif task_type == "validation":
            return await self.validate_functionality(task)
        elif task_type == "bug_report":
            return await self.report_bug(task)
        else:
            return await self.generic_test_task(task)
            
    def identify_test_type(self, task: Task) -> str:
        title_lower = task.title.lower()
        desc_lower = task.description.lower()
        
        if any(word in title_lower or word in desc_lower for word in ["unit test", "unit"]):
            return "unit_test"
        elif any(word in title_lower or word in desc_lower for word in ["integration", "e2e", "end-to-end"]):
            return "integration_test"
        elif any(word in title_lower or word in desc_lower for word in ["ui", "interface", "frontend"]):
            return "ui_test"
        elif any(word in title_lower or word in desc_lower for word in ["validate", "verify", "check"]):
            return "validation"
        elif any(word in title_lower or word in desc_lower for word in ["bug", "issue", "defect"]):
            return "bug_report"
        else:
            return "generic"
            
    async def create_unit_tests(self, task: Task) -> Dict[str, Any]:
        code_files = task.metadata.get("files", [])
        feature_description = task.description
        
        system_prompt = """You are an expert QA engineer specializing in unit testing.
        Create comprehensive unit tests that ensure code quality and correctness.
        Use appropriate testing frameworks and follow testing best practices."""
        
        prompt = f"""Create unit tests for the following feature:
        Feature: {task.title}
        Description: {feature_description}
        Files to test: {json.dumps(code_files, indent=2)}
        
        Generate tests that:
        1. Test all public functions/methods
        2. Cover edge cases and boundary conditions
        3. Test error handling
        4. Verify expected outputs
        5. Include setup and teardown when needed
        
        Use pytest framework for Python, Jest for JavaScript, or appropriate framework for the language."""
        
        try:
            response = await self.generate_llm_response(prompt, system_prompt)
            test_code = self.extract_test_code(response)
            
            test_files = []
            for test_name, test_content in test_code.items():
                test_path = self.test_workspace / test_name
                test_path.write_text(test_content)
                test_files.append(str(test_path))
                
            test_results = await self.run_test_suite(test_files)
            
            self.add_to_context({
                "type": "unit_tests_created",
                "summary": f"Created unit tests for {task.title}",
                "test_files": test_files,
                "results": test_results
            })
            
            return {
                "status": "completed",
                "test_files": test_files,
                "test_results": test_results,
                "coverage": self.estimate_coverage(test_code)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create unit tests: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
            
    async def create_integration_tests(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert in integration and end-to-end testing.
        Create tests that verify system components work together correctly."""
        
        prompt = f"""Create integration tests for:
        Feature: {task.title}
        Description: {task.description}
        
        Test scenarios should include:
        1. Component interaction testing
        2. Data flow validation
        3. API endpoint testing
        4. Database integration
        5. Error propagation handling"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        test_code = self.extract_test_code(response)
        
        integration_test_files = []
        for test_name, test_content in test_code.items():
            test_path = self.test_workspace / "integration" / test_name
            test_path.parent.mkdir(exist_ok=True)
            test_path.write_text(test_content)
            integration_test_files.append(str(test_path))
            
        return {
            "status": "completed",
            "integration_tests": integration_test_files,
            "scenarios_covered": len(test_code)
        }
        
    async def create_ui_tests(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert in UI/UX testing and automation.
        Create tests that validate user interface functionality and user experience."""
        
        prompt = f"""Create UI tests for:
        Feature: {task.title}
        Description: {task.description}
        
        Test cases should cover:
        1. User interaction flows
        2. Visual regression testing
        3. Responsive design validation
        4. Accessibility compliance
        5. Form validation and error states
        
        Use Selenium, Playwright, or Cypress for automation."""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        
        ui_test_spec = {
            "feature": task.title,
            "test_scenarios": self.parse_ui_test_scenarios(response),
            "accessibility_checks": ["WCAG 2.1 AA compliance", "Keyboard navigation", "Screen reader support"],
            "browser_compatibility": ["Chrome", "Firefox", "Safari", "Edge"]
        }
        
        spec_path = self.test_workspace / "ui" / f"{task.title.replace(' ', '_').lower()}_ui_tests.json"
        spec_path.parent.mkdir(exist_ok=True)
        spec_path.write_text(json.dumps(ui_test_spec, indent=2))
        
        await self.request_assistance(
            AgentCapability.UI_DESIGN,
            {
                "task": "Validate UI implementation",
                "test_spec": ui_test_spec
            }
        )
        
        return {
            "status": "completed",
            "ui_test_spec": str(spec_path),
            "scenarios": len(ui_test_spec["test_scenarios"])
        }
        
    async def validate_functionality(self, task: Task) -> Dict[str, Any]:
        validation_items = task.metadata.get("items_to_validate", [])
        
        validation_results = []
        for item in validation_items:
            result = await self.perform_validation(item)
            validation_results.append(result)
            
        passed = sum(1 for r in validation_results if r["passed"])
        failed = len(validation_results) - passed
        
        if failed > 0:
            for result in validation_results:
                if not result["passed"]:
                    await self.create_bug_report(result)
                    
        return {
            "status": "completed",
            "total_validations": len(validation_results),
            "passed": passed,
            "failed": failed,
            "details": validation_results
        }
        
    async def report_bug(self, task: Task) -> Dict[str, Any]:
        bug_details = {
            "id": f"BUG-{len(self.bug_reports) + 1:04d}",
            "title": task.title,
            "description": task.description,
            "severity": task.metadata.get("severity", "medium"),
            "steps_to_reproduce": task.metadata.get("steps", []),
            "expected_behavior": task.metadata.get("expected", ""),
            "actual_behavior": task.metadata.get("actual", ""),
            "environment": task.metadata.get("environment", {}),
            "reported_by": self.agent_id,
            "timestamp": task.created_at.isoformat()
        }
        
        self.bug_reports.append(bug_details)
        
        await self.send_message(
            receiver_id="developer",
            message_type="bug_report",
            content=bug_details
        )
        
        return {
            "status": "completed",
            "bug_id": bug_details["id"],
            "reported_to": "developer"
        }
        
    async def generic_test_task(self, task: Task) -> Dict[str, Any]:
        prompt = f"""Testing Task: {task.title}
        Description: {task.description}
        
        Please complete this testing task following QA best practices."""
        
        response = await self.generate_llm_response(prompt)
        
        return {
            "status": "completed",
            "result": response
        }
        
    def extract_test_code(self, response: str) -> Dict[str, str]:
        test_code = {}
        
        pattern = r'```(?:(\w+)\n)?(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for i, (lang, code) in enumerate(matches):
            if "test" in code.lower() or "describe" in code.lower() or "def test_" in code:
                test_name = f"test_{i}.py" if lang == "python" else f"test_{i}.js"
                test_code[test_name] = code.strip()
                
        if not test_code:
            test_code["test_generated.py"] = response
            
        return test_code
        
    async def run_test_suite(self, test_files: List[str]) -> Dict[str, Any]:
        results = {
            "total": len(test_files),
            "passed": 0,
            "failed": 0,
            "errors": [],
            "execution_time": 0
        }
        
        for test_file in test_files:
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", test_file, "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "file": test_file,
                        "error": result.stderr
                    })
                    
            except subprocess.TimeoutExpired:
                results["failed"] += 1
                results["errors"].append({
                    "file": test_file,
                    "error": "Test execution timeout"
                })
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "file": test_file,
                    "error": str(e)
                })
                
        self.test_results.append(results)
        return results
        
    def estimate_coverage(self, test_code: Dict[str, str]) -> float:
        total_lines = sum(len(code.split('\n')) for code in test_code.values())
        test_count = sum(code.count('def test_') + code.count('it(') + code.count('test(') 
                        for code in test_code.values())
        
        if test_count > 0:
            estimated_coverage = min(test_count * 15, 95)
        else:
            estimated_coverage = 0
            
        return estimated_coverage
        
    def parse_ui_test_scenarios(self, response: str) -> List[Dict[str, Any]]:
        scenarios = []
        
        lines = response.split('\n')
        current_scenario = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('Scenario:') or line.startswith('Test:'):
                if current_scenario:
                    scenarios.append(current_scenario)
                current_scenario = {
                    "name": line.replace('Scenario:', '').replace('Test:', '').strip(),
                    "steps": []
                }
            elif line.startswith('-') or line.startswith('*'):
                if current_scenario:
                    current_scenario["steps"].append(line[1:].strip())
                    
        if current_scenario:
            scenarios.append(current_scenario)
            
        return scenarios if scenarios else [
            {"name": "Basic UI Test", "steps": ["Navigate to page", "Verify elements", "Test interactions"]}
        ]
        
    async def perform_validation(self, item: Dict[str, Any]) -> Dict[str, Any]:
        validation_type = item.get("type", "functional")
        target = item.get("target", "")
        
        prompt = f"""Validate the following:
        Type: {validation_type}
        Target: {target}
        Criteria: {item.get('criteria', 'Standard validation')}
        
        Perform validation and report pass/fail with details."""
        
        response = await self.generate_llm_response(prompt)
        
        passed = "pass" in response.lower() or "success" in response.lower()
        
        return {
            "item": target,
            "type": validation_type,
            "passed": passed,
            "details": response
        }
        
    async def create_bug_report(self, validation_result: Dict[str, Any]):
        bug = {
            "id": f"BUG-{len(self.bug_reports) + 1:04d}",
            "title": f"Validation failed for {validation_result['item']}",
            "description": validation_result["details"],
            "severity": "medium",
            "type": validation_result["type"],
            "reported_by": self.agent_id
        }
        
        self.bug_reports.append(bug)
        
        await self.send_message(
            receiver_id="project_manager",
            message_type="bug_discovered",
            content=bug
        )
        
    async def validate_implementation(self, request: Dict[str, Any]):
        files = request.get("files", [])
        requirements = request.get("requirements", "")
        
        validation_report = {
            "files_checked": files,
            "requirements_met": [],
            "issues_found": [],
            "suggestions": []
        }
        
        for file_path in files:
            if Path(file_path).exists():
                issues = await self.analyze_code_quality(file_path)
                validation_report["issues_found"].extend(issues)
                
        if validation_report["issues_found"]:
            await self.send_message(
                receiver_id=request.get("requester_id", "orchestrator"),
                message_type="validation_complete",
                content=validation_report
            )
        else:
            validation_report["status"] = "passed"
            await self.send_message(
                receiver_id=request.get("requester_id", "orchestrator"),
                message_type="validation_complete",
                content=validation_report
            )
            
    async def analyze_code_quality(self, file_path: str) -> List[Dict[str, Any]]:
        issues = []
        
        try:
            result = subprocess.run(
                ["pylint", file_path, "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.stdout:
                pylint_issues = json.loads(result.stdout)
                for issue in pylint_issues:
                    if issue["type"] in ["error", "warning"]:
                        issues.append({
                            "file": file_path,
                            "line": issue.get("line", 0),
                            "type": issue["type"],
                            "message": issue["message"]
                        })
        except:
            pass
            
        return issues