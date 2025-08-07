import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
from core.base_agent import BaseAgent, AgentCapability, Message, Task


class UIDesignerAgent(BaseAgent):
    def __init__(self, agent_id: str = None, ollama_host: str = "http://localhost:11434"):
        super().__init__(
            agent_id=agent_id or "ui-001", 
            name="UI Designer",
            role="ui_designer",
            capabilities=[
                AgentCapability.UI_DESIGN,
                AgentCapability.DOCUMENTATION
            ],
            model_name="llama3.1:8b",
            ollama_host=ollama_host
        )
        self.design_workspace = Path("./workspace/designs")
        self.design_system: Dict[str, Any] = {}
        self.component_library: List[Dict[str, Any]] = []
        self.accessibility_standards = ["WCAG 2.1 AA"]
        
    async def initialize(self):
        self.design_workspace.mkdir(parents=True, exist_ok=True)
        await self.load_design_system()
        self.logger.info("UI Designer Agent initialized")
        await self.send_message(
            receiver_id="orchestrator",
            message_type="agent_ready",
            content={
                "agent_id": self.agent_id,
                "capabilities": [c.value for c in self.capabilities]
            }
        )
        
    async def load_design_system(self):
        self.design_system = {
            "colors": {
                "primary": "#007bff",
                "secondary": "#6c757d",
                "success": "#28a745",
                "danger": "#dc3545",
                "warning": "#ffc107",
                "info": "#17a2b8",
                "light": "#f8f9fa",
                "dark": "#343a40"
            },
            "typography": {
                "font_family": "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
                "sizes": {
                    "h1": "2.5rem",
                    "h2": "2rem",
                    "h3": "1.75rem",
                    "h4": "1.5rem",
                    "h5": "1.25rem",
                    "h6": "1rem",
                    "body": "1rem",
                    "small": "0.875rem"
                }
            },
            "spacing": {
                "xs": "0.25rem",
                "sm": "0.5rem",
                "md": "1rem",
                "lg": "1.5rem",
                "xl": "3rem"
            },
            "breakpoints": {
                "mobile": "576px",
                "tablet": "768px",
                "desktop": "992px",
                "large": "1200px"
            }
        }
        
    async def handle_message(self, message: Message):
        self.logger.info(f"Received message: {message.message_type}")
        
        if message.message_type == "task_assignment":
            task_data = message.content.get("task")
            task = Task(**task_data)
            await self.start_task(task)
        elif message.message_type == "design_review_request":
            await self.review_design(message.content)
        elif message.message_type == "component_request":
            await self.create_component(message.content)
            
    async def execute_task(self, task: Task) -> Dict[str, Any]:
        self.logger.info(f"Executing UI design task: {task.title}")
        
        task_type = self.identify_design_task(task)
        
        if task_type == "mockup":
            return await self.create_mockup(task)
        elif task_type == "component":
            return await self.design_component(task)
        elif task_type == "style_guide":
            return await self.create_style_guide(task)
        elif task_type == "prototype":
            return await self.create_prototype(task)
        elif task_type == "accessibility":
            return await self.accessibility_audit(task)
        else:
            return await self.generic_design_task(task)
            
    def identify_design_task(self, task: Task) -> str:
        title_lower = task.title.lower()
        desc_lower = task.description.lower()
        
        if any(word in title_lower or word in desc_lower for word in ["mockup", "wireframe", "sketch"]):
            return "mockup"
        elif any(word in title_lower or word in desc_lower for word in ["component", "widget", "element"]):
            return "component"
        elif any(word in title_lower or word in desc_lower for word in ["style", "guide", "design system"]):
            return "style_guide"
        elif any(word in title_lower or word in desc_lower for word in ["prototype", "interactive"]):
            return "prototype"
        elif any(word in title_lower or word in desc_lower for word in ["accessibility", "a11y", "wcag"]):
            return "accessibility"
        else:
            return "generic"
            
    async def create_mockup(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert UI/UX designer. Create detailed mockups and wireframes.
        Focus on user experience, visual hierarchy, and modern design principles."""
        
        prompt = f"""Create a mockup for:
        Feature: {task.title}
        Description: {task.description}
        
        Design Requirements:
        1. User-friendly interface
        2. Responsive design (mobile, tablet, desktop)
        3. Clear visual hierarchy
        4. Consistent with design system
        5. Accessibility compliant
        
        Provide:
        - HTML structure
        - CSS styling
        - Component breakdown
        - User flow description"""
        
        try:
            response = await self.generate_llm_response(prompt, system_prompt)
            
            mockup_data = self.parse_design_response(response)
            
            html_content = mockup_data.get("html", "")
            css_content = mockup_data.get("css", "")
            
            mockup_name = task.title.replace(" ", "_").lower()
            html_path = self.design_workspace / f"{mockup_name}.html"
            css_path = self.design_workspace / f"{mockup_name}.css"
            
            if html_content:
                full_html = self.create_full_html_mockup(html_content, css_content, task.title)
                html_path.write_text(full_html)
                
            if css_content:
                css_path.write_text(css_content)
                
            mockup_spec = {
                "name": task.title,
                "files": {
                    "html": str(html_path),
                    "css": str(css_path)
                },
                "components": mockup_data.get("components", []),
                "user_flow": mockup_data.get("user_flow", ""),
                "responsive_breakpoints": self.design_system["breakpoints"]
            }
            
            spec_path = self.design_workspace / f"{mockup_name}_spec.json"
            spec_path.write_text(json.dumps(mockup_spec, indent=2))
            
            self.add_to_context({
                "type": "mockup_created",
                "summary": f"Created mockup for {task.title}",
                "files": [str(html_path), str(css_path), str(spec_path)]
            })
            
            return {
                "status": "completed",
                "mockup_files": mockup_spec["files"],
                "specification": str(spec_path)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create mockup: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
            
    async def design_component(self, task: Task) -> Dict[str, Any]:
        component_name = task.metadata.get("component_name", task.title)
        
        system_prompt = """You are an expert in component-based UI design.
        Create reusable, accessible, and well-documented UI components."""
        
        prompt = f"""Design a UI component:
        Name: {component_name}
        Purpose: {task.description}
        
        Requirements:
        1. Reusable and configurable
        2. Accessible (WCAG 2.1 AA)
        3. Responsive design
        4. Clear API/props
        5. Multiple states (default, hover, active, disabled)
        
        Provide:
        - HTML structure
        - CSS styling
        - JavaScript functionality (if needed)
        - Usage documentation"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        
        component_code = self.parse_design_response(response)
        
        component = {
            "name": component_name,
            "description": task.description,
            "html": component_code.get("html", ""),
            "css": component_code.get("css", ""),
            "javascript": component_code.get("javascript", ""),
            "props": component_code.get("props", {}),
            "states": ["default", "hover", "active", "disabled", "loading"],
            "accessibility_features": [
                "Keyboard navigation",
                "ARIA labels",
                "Focus indicators",
                "Screen reader support"
            ]
        }
        
        self.component_library.append(component)
        
        component_path = self.design_workspace / "components" / f"{component_name.lower().replace(' ', '_')}.json"
        component_path.parent.mkdir(exist_ok=True)
        component_path.write_text(json.dumps(component, indent=2))
        
        return {
            "status": "completed",
            "component": component,
            "saved_to": str(component_path)
        }
        
    async def create_style_guide(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert in design systems and style guides.
        Create comprehensive documentation for UI consistency."""
        
        prompt = f"""Create a style guide for:
        Project: {task.title}
        Requirements: {task.description}
        
        Include:
        1. Color palette
        2. Typography rules
        3. Spacing system
        4. Component patterns
        5. Interaction states
        6. Accessibility guidelines"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        
        style_guide = {
            "project": task.title,
            "version": "1.0.0",
            "design_system": self.design_system,
            "components": self.component_library,
            "guidelines": self.parse_guidelines(response),
            "accessibility": {
                "standards": self.accessibility_standards,
                "requirements": [
                    "Minimum contrast ratio 4.5:1",
                    "Keyboard navigable",
                    "Screen reader compatible",
                    "Focus indicators",
                    "Alternative text for images"
                ]
            }
        }
        
        guide_path = self.design_workspace / "style_guide.json"
        guide_path.write_text(json.dumps(style_guide, indent=2))
        
        css_variables = self.generate_css_variables(self.design_system)
        css_path = self.design_workspace / "design_tokens.css"
        css_path.write_text(css_variables)
        
        return {
            "status": "completed",
            "style_guide": str(guide_path),
            "design_tokens": str(css_path)
        }
        
    async def create_prototype(self, task: Task) -> Dict[str, Any]:
        system_prompt = """You are an expert in interactive prototyping.
        Create functional prototypes that demonstrate user interactions."""
        
        prompt = f"""Create an interactive prototype for:
        Feature: {task.title}
        Description: {task.description}
        
        Include:
        1. Interactive elements
        2. State transitions
        3. Animations/transitions
        4. Form validations
        5. Error states
        6. Success feedback"""
        
        response = await self.generate_llm_response(prompt, system_prompt)
        
        prototype_code = self.parse_design_response(response)
        
        prototype_name = task.title.replace(" ", "_").lower()
        prototype_path = self.design_workspace / "prototypes" / prototype_name
        prototype_path.mkdir(parents=True, exist_ok=True)
        
        html_content = self.create_interactive_prototype(
            prototype_code.get("html", ""),
            prototype_code.get("css", ""),
            prototype_code.get("javascript", ""),
            task.title
        )
        
        (prototype_path / "index.html").write_text(html_content)
        
        return {
            "status": "completed",
            "prototype_path": str(prototype_path / "index.html"),
            "interactions": prototype_code.get("interactions", [])
        }
        
    async def accessibility_audit(self, task: Task) -> Dict[str, Any]:
        files_to_audit = task.metadata.get("files", [])
        
        audit_results = {
            "standard": "WCAG 2.1 AA",
            "files_audited": files_to_audit,
            "issues": [],
            "warnings": [],
            "passes": [],
            "score": 0
        }
        
        for file_path in files_to_audit:
            if Path(file_path).exists():
                issues = await self.check_accessibility(file_path)
                audit_results["issues"].extend(issues)
                
        total_checks = 10
        passed_checks = total_checks - len(audit_results["issues"])
        audit_results["score"] = (passed_checks / total_checks) * 100
        
        audit_path = self.design_workspace / "accessibility_audit.json"
        audit_path.write_text(json.dumps(audit_results, indent=2))
        
        if audit_results["issues"]:
            await self.send_message(
                receiver_id="developer",
                message_type="accessibility_issues",
                content=audit_results
            )
            
        return {
            "status": "completed",
            "audit_report": str(audit_path),
            "score": audit_results["score"],
            "issues_found": len(audit_results["issues"])
        }
        
    async def generic_design_task(self, task: Task) -> Dict[str, Any]:
        prompt = f"""UI/UX Design Task: {task.title}
        Description: {task.description}
        
        Please complete this design task following best practices."""
        
        response = await self.generate_llm_response(prompt)
        
        return {
            "status": "completed",
            "result": response
        }
        
    def parse_design_response(self, response: str) -> Dict[str, Any]:
        result = {
            "html": "",
            "css": "",
            "javascript": "",
            "components": [],
            "user_flow": "",
            "interactions": []
        }
        
        import re
        
        html_match = re.search(r'```html\n(.*?)```', response, re.DOTALL)
        if html_match:
            result["html"] = html_match.group(1).strip()
            
        css_match = re.search(r'```css\n(.*?)```', response, re.DOTALL)
        if css_match:
            result["css"] = css_match.group(1).strip()
            
        js_match = re.search(r'```(?:javascript|js)\n(.*?)```', response, re.DOTALL)
        if js_match:
            result["javascript"] = js_match.group(1).strip()
            
        lines = response.split('\n')
        for line in lines:
            if 'component' in line.lower():
                result["components"].append(line.strip())
            if 'flow' in line.lower() or 'step' in line.lower():
                result["user_flow"] += line + "\n"
                
        return result
        
    def create_full_html_mockup(self, html_content: str, css_content: str, title: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Mockup</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: {self.design_system['typography']['font_family']};
            line-height: 1.6;
            color: {self.design_system['colors']['dark']};
        }}
        
        {css_content}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
        
    def create_interactive_prototype(self, html: str, css: str, js: str, title: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Interactive Prototype</title>
    <style>
        {css}
    </style>
</head>
<body>
    {html}
    <script>
        {js}
    </script>
</body>
</html>"""
        
    def generate_css_variables(self, design_system: Dict[str, Any]) -> str:
        css_vars = ":root {\n"
        
        for color_name, color_value in design_system["colors"].items():
            css_vars += f"    --color-{color_name}: {color_value};\n"
            
        for size_name, size_value in design_system["typography"]["sizes"].items():
            css_vars += f"    --font-size-{size_name}: {size_value};\n"
            
        for space_name, space_value in design_system["spacing"].items():
            css_vars += f"    --spacing-{space_name}: {space_value};\n"
            
        css_vars += "}\n"
        return css_vars
        
    def parse_guidelines(self, response: str) -> List[str]:
        guidelines = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and (line[0].isupper() or line.startswith('-') or line.startswith('*')):
                guidelines.append(line.replace('-', '').replace('*', '').strip())
                
        return guidelines if guidelines else ["Follow design system", "Maintain consistency", "Prioritize usability"]
        
    async def check_accessibility(self, file_path: str) -> List[Dict[str, Any]]:
        issues = []
        
        content = Path(file_path).read_text()
        
        if '<img' in content and 'alt=' not in content:
            issues.append({
                "type": "error",
                "rule": "Images must have alt text",
                "file": file_path
            })
            
        if 'color:' in content and not self.check_color_contrast(content):
            issues.append({
                "type": "warning",
                "rule": "Ensure sufficient color contrast",
                "file": file_path
            })
            
        if '<button' in content or '<a' in content:
            if ':focus' not in content:
                issues.append({
                    "type": "warning",
                    "rule": "Interactive elements should have focus states",
                    "file": file_path
                })
                
        return issues
        
    def check_color_contrast(self, content: str) -> bool:
        return True
        
    async def review_design(self, review_request: Dict[str, Any]):
        design_files = review_request.get("files", [])
        
        review_results = {
            "reviewer": self.agent_id,
            "files_reviewed": design_files,
            "feedback": [],
            "approval_status": "pending"
        }
        
        for file_path in design_files:
            if Path(file_path).exists():
                feedback = await self.generate_design_feedback(file_path)
                review_results["feedback"].append({
                    "file": file_path,
                    "comments": feedback
                })
                
        review_results["approval_status"] = "approved" if not any("issue" in str(f).lower() for f in review_results["feedback"]) else "needs_revision"
        
        await self.send_message(
            receiver_id=review_request.get("requester_id", "orchestrator"),
            message_type="design_review_complete",
            content=review_results
        )
        
    async def generate_design_feedback(self, file_path: str) -> str:
        content = Path(file_path).read_text()
        
        prompt = f"""Review this UI design/code:
        File: {file_path}
        
        Check for:
        1. Design consistency
        2. User experience
        3. Accessibility
        4. Responsive design
        5. Performance considerations
        
        Content preview:
        {content[:500]}...
        
        Provide constructive feedback."""
        
        return await self.generate_llm_response(prompt)
        
    async def create_component(self, request: Dict[str, Any]):
        component_spec = request.get("specification", {})
        
        task = Task(
            title=f"Create {component_spec.get('name', 'Component')}",
            description=component_spec.get('description', ''),
            metadata={"component_name": component_spec.get('name')}
        )
        
        result = await self.design_component(task)
        
        await self.send_message(
            receiver_id=request.get("requester_id", "orchestrator"),
            message_type="component_created",
            content=result
        )