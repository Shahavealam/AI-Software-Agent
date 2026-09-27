import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

# Try to import langchain components with error handling
try:
    from langchain_openai import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    HAS_LANGCHAIN = True
except ImportError as e:
    print(f"Warning: LangChain import error: {e}")
    HAS_LANGCHAIN = False

from dotenv import load_dotenv

# Import agent components
from agent_core.code_analyzer import CodeAnalyzer
from agent_core.code_generator import CodeGenerator
from agent_core.file_manager import FileManager
from tools.git_tools import GitTools
from tools.validation_tools import ValidationTools

load_dotenv()


class SoftwareAgent:
    """Main orchestrator for software engineering tasks"""
    
    def __init__(self, project_path: Union[str, Path] = "."):
        self.project_path = Path(project_path)
        self.analyzer = CodeAnalyzer(self.project_path)
        self.generator = CodeGenerator(self.project_path)
        self.file_manager = FileManager(self.project_path)
        self.git = GitTools(self.project_path)
        self.validator = ValidationTools()
        
        # Initialize LLM with compatibility fixes
        self.llm = None
        self._initialize_llm()
        
        # System prompt for the agent
        self.system_prompt = """You are an AI Software Engineer Agent. Your task is to:
1. Understand the user's software engineering requirements
2. Analyze existing code structure
3. Generate new code or modifications
4. Ensure code quality and best practices
5. Provide clear explanations of changes

Always consider:
- Code maintainability
- Performance implications
- Security best practices
- Error handling
- Documentation
- Testing requirements

Break down complex tasks into manageable steps and explain your reasoning.
"""
    
    def _initialize_llm(self):
        """Initialize the LLM with compatibility fixes"""
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not HAS_LANGCHAIN:
            print("Warning: LangChain not available. Using fallback mode.")
            self.llm = None
            return
        
        try:
            # Try different initialization methods
            if api_key:
                try:
                    # Method 1: Standard initialization with API key
                    self.llm = ChatOpenAI(
                        model=model_name,
                        # temperature=0.3,
                        openai_api_key=api_key
                    )
                    print(f"✅ LLM initialized with model: {model_name}")
                    return
                except Exception as e:
                    print(f"Method 1 failed: {e}")
            
            try:
                # Method 2: Without explicit API key (uses env var)
                self.llm = ChatOpenAI(
                    model=model_name,
                    temperature=0.3
                )
                print(f"✅ LLM initialized with model: {model_name}")
                return
            except Exception as e:
                print(f"Method 2 failed: {e}")
            
            try:
                # Method 3: With minimal parameters
                self.llm = ChatOpenAI(
                    model_name=model_name,
                    temperature=0.3
                )
                print(f"✅ LLM initialized with model: {model_name}")
                return
            except Exception as e:
                print(f"Method 3 failed: {e}")
            
            # If all methods fail, try with older API
            try:
                import openai
                self.llm = ChatOpenAI(
                    model=model_name,
                    temperature=0.3,
                    openai_api_key=api_key or os.getenv("OPENAI_API_KEY")
                )
                print(f"✅ LLM initialized with model: {model_name}")
                return
            except Exception as e:
                print(f"Method 4 failed: {e}")
            
            # Final fallback: set to None
            print("⚠️ Could not initialize LLM. Running in offline mode.")
            self.llm = None
            
        except Exception as e:
            print(f"❌ Error initializing LLM: {e}")
            self.llm = None
    
    def _call_llm(self, messages: List) -> Any:
        """Safely call the LLM with error handling"""
        if self.llm is None:
            # Return a mock response when LLM is not available
            class MockResponse:
                def __init__(self):
                    self.content = "I'm currently in offline mode. Please check your OpenAI API key and try again."
            
            # Extract the last user message for context
            for msg in reversed(messages):
                if hasattr(msg, 'content') and msg.content:
                    return MockResponse()
            
            return MockResponse()
        
        try:
            return self.llm.invoke(messages)
        except Exception as e:
            print(f"Error calling LLM: {e}")
            class ErrorResponse:
                def __init__(self):
                    self.content = f"Error: {str(e)}. Please check your configuration."
            return ErrorResponse()
    
    def process_request(self, user_input: str) -> Dict[str, Any]:
        """Process user request and execute necessary actions"""
        
        # Step 1: Understand the request
        analysis = self._analyze_request(user_input)
        
        if analysis.get("requires_clarification"):
            return {
                "status": "clarification_needed",
                "message": analysis.get("message", "I need more information to proceed."),
                "suggestions": analysis.get("suggestions", [])
            }
        
        # Step 2: Generate execution plan
        plan = self._generate_plan(analysis)
        
        # Step 3: Execute plan
        result = self._execute_plan(plan)
        
        # Step 4: Validate changes
        if self.validator:
            validation = self.validator.validate_changes(result)
            
            if not validation.get("success"):
                result["warnings"] = validation.get("warnings", [])
                result["errors"] = validation.get("errors", [])
        
        return result
    
    def _analyze_request(self, user_input: str) -> Dict[str, Any]:
        """Analyze user request and extract requirements"""
        
        if self.llm is None:
            # Simple analysis without LLM
            return {
                "type": "unknown",
                "requirements": [user_input],
                "complexity": "medium",
                "requires_clarification": False
            }
        
        # Use LLM to analyze request
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
Analyze this software engineering request and extract requirements:

Request: {user_input}

Provide response in JSON format with:
{{
    "type": "create|update|fix|refactor|document|test",
    "target_files": ["file1.py", "file2.py"],
    "requirements": ["req1", "req2"],
    "technologies": ["python", "fastapi"],
    "complexity": "low|medium|high",
    "requires_clarification": true/false,
    "clarification_questions": ["q1", "q2"] if applicable
}}
""")
        ]
        
        try:
            response = self._call_llm(messages)
            
            # Try to parse JSON from response
            content = response.content
            # Extract JSON from markdown code blocks if present
            import re
            json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            analysis = json.loads(content)
            return analysis
        except json.JSONDecodeError:
            # Fallback: Parse manually
            return {
                "type": "unknown",
                "requirements": [user_input],
                "complexity": "medium",
                "requires_clarification": False
            }
        except Exception as e:
            print(f"Error analyzing request: {e}")
            return {
                "type": "unknown",
                "requirements": [user_input],
                "complexity": "medium",
                "requires_clarification": False
            }
    
    def _generate_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate execution plan based on analysis"""
        
        # Get existing files in project
        existing_files = self.file_manager.list_files() if self.file_manager else []
        
        # Determine target files
        target_files = analysis.get("target_files", [])
        
        if not target_files:
            # If no specific files, let LLM decide or use defaults
            if self.llm is not None:
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=f"""
Given the analysis and existing files, determine which files need to be created or modified.

Analysis: {json.dumps(analysis, indent=2)}
Existing files: {existing_files}

Provide a plan in JSON format:
{{
    "files_to_create": ["new_file1.py", "new_file2.py"],
    "files_to_update": ["existing_file1.py"],
    "dependencies": ["package1", "package2"],
    "steps": [
        "Step 1 description",
        "Step 2 description"
    ]
}}
""")
                ]
                
                try:
                    response = self._call_llm(messages)
                    content = response.content
                    # Extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1)
                    plan = json.loads(content)
                    return plan
                except:
                    pass
            
            # Default plan
            plan = {
                "files_to_create": [],
                "files_to_update": [],
                "steps": [analysis.get("requirements", [""])[0]]
            }
        else:
            plan = {
                "files_to_create": [f for f in target_files if f not in existing_files],
                "files_to_update": [f for f in target_files if f in existing_files],
                "steps": [f"Process {f}" for f in target_files]
            }
        
        return plan
    
    def _execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the generated plan"""
        
        result = {
            "status": "success",
            "files_created": [],
            "files_updated": [],
            "summary": "",
            "suggestions": []
        }
        
        # Create new files
        for file_path in plan.get("files_to_create", []):
            success = self._create_file(file_path, plan)
            if success:
                result["files_created"].append(file_path)
        
        # Update existing files
        for file_path in plan.get("files_to_update", []):
            success = self._update_file(file_path, plan)
            if success:
                result["files_updated"].append(file_path)
        
        # Generate summary
        if result["files_created"] or result["files_updated"]:
            result["summary"] = self._generate_summary(result)
            result["suggestions"] = self._generate_suggestions(result)
        else:
            result["summary"] = "No files were created or updated. Please provide more specific requirements."
            result["suggestions"] = [
                "Specify which files to create or modify",
                "Provide more detailed requirements",
                "Check if the project structure is correct"
            ]
        
        return result
    
    def _create_file(self, file_path: str, plan: Dict[str, Any]) -> bool:
        """Create a new file with appropriate content"""
        try:
            # Generate content for the new file
            content = self.generator.generate_new_file(file_path, plan)
            
            # Create the file
            self.file_manager.create_file(file_path, content)
            print(f"✅ Created file: {file_path}")
            return True
        except Exception as e:
            print(f"Error creating {file_path}: {e}")
            return False
    
    def _update_file(self, file_path: str, plan: Dict[str, Any]) -> bool:
        """Update an existing file"""
        try:
            # Read existing content
            existing_content = self.file_manager.read_file(file_path)
            
            if existing_content is None:
                print(f"⚠️ File {file_path} not found, creating instead")
                return self._create_file(file_path, plan)
            
            # Generate updated content
            updated_content = self.generator.update_file(
                file_path, 
                existing_content, 
                plan
            )
            
            # Update the file
            self.file_manager.update_file(file_path, updated_content)
            print(f"🔄 Updated file: {file_path}")
            return True
        except Exception as e:
            print(f"Error updating {file_path}: {e}")
            return False
    
    def _generate_summary(self, result: Dict[str, Any]) -> str:
        """Generate a summary of changes"""
        if self.llm is None:
            files_created = result.get('files_created', [])
            files_updated = result.get('files_updated', [])
            
            summary = "Changes made:\n"
            if files_created:
                summary += f"- Created: {', '.join(files_created)}\n"
            if files_updated:
                summary += f"- Updated: {', '.join(files_updated)}\n"
            return summary
        
        messages = [
            SystemMessage(content="You are a technical writer. Summarize the changes made."),
            HumanMessage(content=f"""
Given the changes made, provide a clear summary:

Files created: {result.get('files_created', [])}
Files updated: {result.get('files_updated', [])}

Provide a concise summary of what was accomplished.
""")
        ]
        
        try:
            response = self._call_llm(messages)
            return response.content
        except:
            return f"Created {len(result.get('files_created', []))} files and updated {len(result.get('files_updated', []))} files."
    
    def _generate_suggestions(self, result: Dict[str, Any]) -> List[str]:
        """Generate suggestions for next steps"""
        suggestions = [
            "Consider adding unit tests for the new functionality",
            "Review the code for potential optimizations",
            "Update documentation to reflect changes"
        ]
        
        if self.llm is None:
            return suggestions
        
        try:
            messages = [
                SystemMessage(content="You are a senior software engineer. Provide actionable suggestions."),
                HumanMessage(content=f"""
Based on these changes:
Files created: {result.get('files_created', [])}
Files updated: {result.get('files_updated', [])}

Provide 3-4 specific, actionable suggestions for next steps.
""")
            ]
            
            response = self._call_llm(messages)
            # Parse response into list of suggestions
            lines = response.content.split('\n')
            for line in lines:
                if line.strip() and not line.strip().startswith('#'):
                    clean_line = line.strip().replace('-', '').replace('•', '').strip()
                    if clean_line and len(clean_line) > 5:
                        suggestions.append(clean_line)
        except:
            pass
        
        return suggestions[:5]
    
    def show_status(self):
        """Show project status"""
        if self.file_manager:
            files = self.file_manager.list_files()
            print(f"\n{Fore.CYAN}📁 Project Status:{Fore.RESET}" if 'Fore' in dir() else "\nProject Status:")
            print(f"  Total files: {len(files)}")
            print(f"  Python files: {len([f for f in files if f.endswith('.py')])}")
            
            # Show LLM status
            print(f"  LLM Status: {'✅ Connected' if self.llm else '⚠️ Offline Mode'}")
            
            # Show git status if available
            if self.git:
                git_status = self.git.get_status()
                if git_status:
                    print(f"\n{Fore.YELLOW}🔀 Git Status:{Fore.RESET}" if 'Fore' in dir() else "\nGit Status:")
                    for line in git_status[:5]:
                        print(f"  {line}")
        else:
            print("File manager not available")
    
    def view_file(self, filename: str):
        """View file content"""
        if self.file_manager:
            content = self.file_manager.read_file(filename)
            if content:
                print(f"\n{Fore.CYAN}📄 File: {filename}{Fore.RESET}" if 'Fore' in dir() else f"\nFile: {filename}")
                print("─" * 60)
                print(content)
                print("─" * 60)
            else:
                print(f"{Fore.RED}File not found: {filename}{Fore.RESET}" if 'Fore' in dir() else f"File not found: {filename}")
        else:
            print("File manager not available")
    
    def list_files(self):
        """List all files in project"""
        if self.file_manager:
            files = self.file_manager.list_files()
            print(f"\n{Fore.CYAN}📁 Files in project:{Fore.RESET}" if 'Fore' in dir() else "\nFiles in project:")
            for file in sorted(files)[:20]:  # Limit to 20 files
                print(f"  📄 {file}")
            if len(files) > 20:
                print(f"  ... and {len(files) - 20} more files")
        else:
            print("File manager not available")