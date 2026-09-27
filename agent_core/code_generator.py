import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

# Try to import langchain components with error handling
# (mirrors agent_orchestrator.py so missing deps don't crash the app)
try:
    from langchain_openai import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    HAS_LANGCHAIN = True
except ImportError as e:
    print(f"Warning: LangChain import error in code_generator: {e}")
    HAS_LANGCHAIN = False
    ChatOpenAI = None
    HumanMessage = None
    SystemMessage = None

from dotenv import load_dotenv

load_dotenv()

class CodeGenerator:
    """Generates and updates code based on requirements"""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.llm = None

        if not HAS_LANGCHAIN:
            print("Warning: LangChain not available in CodeGenerator. Using fallback mode.")
            return

        # Initialize with proper parameters for compatibility
        try:
            # Try the standard initialization
            self.llm = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                # temperature=0.3,
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )
        except Exception as e:
            # Fallback with minimal parameters
            print(f"Warning: Using fallback initialization: {e}")

            # self.llm = ChatOpenAI(
            #     model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            #     # temperature=0.3
            #     openai_api_key=os.getenv("OPENAI_API_KEY")
            # )
        
    def generate_new_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate content for a new file"""

        # Offline fallback: don't touch SystemMessage/HumanMessage if LLM is unavailable
        if not HAS_LANGCHAIN or self.llm is None:
            return f"""# Offline mode: LangChain/LLM not available.
# File: {file_path}
# Requirements: {plan.get('requirements', [])}
#
# Install dependencies (uv sync) and set OPENAI_API_KEY to enable generation.
pass
"""

        # Determine file type
        extension = file_path.split('.')[-1] if '.' in file_path else ''
        
        if extension == 'py':
            return self._generate_python_file(file_path, plan)
        elif extension == 'js':
            return self._generate_js_file(file_path, plan)
        elif extension in ['html', 'htm']:
            return self._generate_html_file(file_path, plan)
        elif extension == 'json':
            return self._generate_json_file(file_path, plan)
        elif extension == 'md':
            return self._generate_markdown_file(file_path, plan)
        elif extension == 'txt':
            return self._generate_text_file(file_path, plan)
        elif extension in ['yml', 'yaml']:
            return self._generate_yaml_file(file_path, plan)
        elif extension == 'css':
            return self._generate_css_file(file_path, plan)
        elif extension in ['jsx', 'tsx']:
            return self._generate_react_file(file_path, plan)
        elif extension == 'ts':
            return self._generate_typescript_file(file_path, plan)
        else:
            return self._generate_generic_file(file_path, plan)
    
    def _generate_python_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate Python file content"""
        
        messages = [
            SystemMessage(content="""You are a senior Python developer. Generate clean, well-documented Python code.
Include:
- Proper imports
- Class/function documentation with docstrings
- Type hints for all parameters and return values
- Error handling with try/except blocks
- Best practices and design patterns
- PEP 8 compliance
- __init__.py for packages"""),
            HumanMessage(content=f"""Generate Python code for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete file content only, no explanations outside the code.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""# Error generating Python file: {e}
# Please check your OpenAI API key and try again.

# File: {file_path}
# Requirements: {plan.get('requirements', [])}

pass"""
    
    def _generate_js_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate JavaScript file content"""
        
        messages = [
            SystemMessage(content="""You are a senior JavaScript developer. Generate clean, well-documented JavaScript code.
Include:
- Proper module imports (ES6 or CommonJS)
- Function documentation with JSDoc
- Error handling with try/catch
- Modern ES6+ syntax (const/let, arrow functions, destructuring)
- Best practices and design patterns
- Proper exports"""),
            HumanMessage(content=f"""Generate JavaScript code for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete file content only, no explanations outside the code.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""// Error generating JavaScript file: {e}
// Please check your OpenAI API key and try again.

// File: {file_path}
// Requirements: {plan.get('requirements', [])}

// TODO: Implement functionality
"""
    
    def _generate_typescript_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate TypeScript file content"""
        
        messages = [
            SystemMessage(content="""You are a senior TypeScript developer. Generate clean, well-documented TypeScript code.
Include:
- Proper imports
- Type definitions and interfaces
- Function documentation with JSDoc
- Error handling
- Modern TypeScript features
- Best practices"""),
            HumanMessage(content=f"""Generate TypeScript code for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete file content only, no explanations outside the code.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""// Error generating TypeScript file: {e}
// Please check your OpenAI API key and try again.

// File: {file_path}
// Requirements: {plan.get('requirements', [])}

// TODO: Implement functionality
"""
    
    def _generate_react_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate React component file content"""
        
        messages = [
            SystemMessage(content="""You are a senior React developer. Generate clean, well-documented React component code.
Include:
- Proper imports
- Component definition (functional or class)
- PropTypes or TypeScript types
- Hooks (useState, useEffect, etc.)
- Error boundaries
- Best practices"""),
            HumanMessage(content=f"""Generate React component for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete file content only, no explanations outside the code.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""// Error generating React component: {e}
// Please check your OpenAI API key and try again.

// File: {file_path}
// Requirements: {plan.get('requirements', [])}

// TODO: Implement component
"""
    
    def _generate_html_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate HTML file content"""
        
        messages = [
            SystemMessage(content="""You are a senior web developer. Generate clean, semantic HTML code.
Include:
- Proper HTML5 structure with DOCTYPE
- Accessibility features (ARIA labels, alt text)
- Responsive design meta tags
- CSS integration (inline, internal, or external)
- Best practices and semantic elements
- Proper head section with meta tags"""),
            HumanMessage(content=f"""Generate HTML code for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete file content only, no explanations outside the code.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""<!-- Error generating HTML file: {e} -->
<!-- Please check your OpenAI API key and try again. -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_path}</title>
</head>
<body>
    <h1>Coming Soon</h1>
    <p>File: {file_path}</p>
</body>
</html>
"""
    
    def _generate_css_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate CSS file content"""
        
        messages = [
            SystemMessage(content="""You are a senior CSS developer. Generate clean, well-organized CSS code.
Include:
- Proper selectors and specificity
- Responsive design with media queries
- CSS variables for theming
- Flexbox/Grid layouts
- Animations where appropriate
- Best practices and naming conventions"""),
            HumanMessage(content=f"""Generate CSS code for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete file content only, no explanations outside the code.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""/* Error generating CSS file: {e} */
/* Please check your OpenAI API key and try again. */

/* File: {file_path} */
/* Requirements: {plan.get('requirements', [])} */

/* TODO: Implement styles */
"""
    
    def _generate_json_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate JSON file content"""
        
        messages = [
            SystemMessage(content="""You are a data architect. Generate valid JSON with proper structure.
Include:
- Proper JSON syntax
- Meaningful key names
- Appropriate data types
- Nested objects where needed
- Arrays for collections"""),
            HumanMessage(content=f"""Generate JSON content for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide only valid JSON, no other text or explanations.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""{{}}
"""
    
    def _generate_yaml_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate YAML file content"""
        
        messages = [
            SystemMessage(content="""You are a DevOps engineer. Generate valid YAML with proper structure.
Include:
- Proper YAML syntax
- Meaningful key names
- Appropriate data types
- Nested structures where needed
- Lists and maps"""),
            HumanMessage(content=f"""Generate YAML content for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide only valid YAML, no other text or explanations.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""# Error generating YAML file: {e}
# Please check your OpenAI API key and try again.

# File: {file_path}
# Requirements: {plan.get('requirements', [])}

# TODO: Implement YAML configuration
"""
    
    def _generate_markdown_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate Markdown file content"""
        
        messages = [
            SystemMessage(content="""You are a technical writer. Generate clean, well-structured markdown.
Include:
- Proper headings hierarchy
- Lists and sublists
- Code blocks with language specification
- Tables where appropriate
- Links and references
- Images if applicable"""),
            HumanMessage(content=f"""Generate markdown content for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete markdown content.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""# Error generating Markdown file: {e}

# Please check your OpenAI API key and try again.

## File: {file_path}

## Requirements:
{plan.get('requirements', [])}
"""
    
    def _generate_text_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate plain text file content"""
        
        messages = [
            SystemMessage(content="You are a technical writer. Generate clear, well-structured text."),
            HumanMessage(content=f"""Generate text content for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}

Provide complete text content.""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""Error generating text file: {e}
Please check your OpenAI API key and try again.

File: {file_path}
Requirements: {plan.get('requirements', [])}
"""
    
    def _generate_generic_file(self, file_path: str, plan: Dict[str, Any]) -> str:
        """Generate generic file content"""
        
        messages = [
            SystemMessage(content="Generate appropriate content for the file type."),
            HumanMessage(content=f"""Generate content for: {file_path}

Requirements: {plan.get('requirements', [])}
Context: {plan}""")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"""# Error generating file: {e}
# File: {file_path}
# Requirements: {plan.get('requirements', [])}
"""
    
    def update_file(self, file_path: str, existing_content: str, plan: Dict[str, Any]) -> str:
        """Update an existing file with new content"""

        # Offline fallback
        if not HAS_LANGCHAIN or self.llm is None:
            return existing_content or f"# Offline mode: cannot update {file_path} without LLM.\n"

        # Determine file type
        extension = file_path.split('.')[-1] if '.' in file_path else ''
        
        # Ensure existing_content is properly formatted
        if not existing_content:
            existing_content = "# File is empty or not found"
        
        # Create the message content safely
        system_content = """You are a senior developer. Update the existing code while:
- Maintaining existing functionality
- Following the existing code style
- Adding new features as requested
- Preserving existing imports and structure
- Adding proper documentation for changes
- Not removing any existing functionality unless explicitly requested
- Fixing any bugs or issues found
- Ensuring code quality and best practices"""

        human_content = f"""Update this file: {file_path}

Existing content:
```{extension}
{existing_content}
```

Plan for updates: {plan.get('changes', [])}
Requirements: {plan.get('requirements', [])}
Context: {plan}"""