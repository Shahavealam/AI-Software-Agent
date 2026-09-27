"""
Task Prompts for AI Software Engineer Agent

This module contains all task-specific prompts used by the agent
for various software engineering tasks.
"""

from typing import Dict, Any, List

# ============================================
# 1. CODE GENERATION PROMPTS
# ============================================

CODE_GENERATION_PROMPTS = {
    "python_api": {
        "system": """You are a senior Python developer specializing in API development.
Generate production-ready FastAPI/Flask/Django code with:
- Proper project structure
- Type hints and validation
- Error handling
- Documentation
- Security best practices
- Performance optimization
- Database integration
- Testing considerations""",
        "template": """
Create a {framework} API for {purpose}.

Requirements:
{requirements}

Project Context:
{context}

Features needed:
{features}

Generate complete code including:
1. Main application file
2. Models/Schemas
3. Routes/Endpoints
4. Database configuration
5. Authentication/Authorization
6. Error handlers
7. Middleware
8. Configuration files
9. Requirements.txt
10. README with setup instructions

Follow RESTful best practices and provide proper error responses.
        """
    },
    
    "python_cli": {
        "system": """You are a senior Python developer specializing in CLI applications.
Generate robust command-line tools with:
- argparse or click/typer for CLI
- Proper error handling
- Help documentation
- Configuration support
- Logging
- Progress indicators
- Cross-platform compatibility""",
        "template": """
Create a CLI tool for {purpose}.

Requirements:
{requirements}

Features:
{features}

Generate complete CLI application with:
1. Main entry point
2. Command parsing
3. Subcommands (if needed)
4. Configuration management
5. Logging setup
6. Error handling
7. Help messages
8. Setup.py or pyproject.toml
9. README with usage examples
        """
    },
    
    "python_library": {
        "system": """You are a senior Python library developer.
Create a well-structured Python library with:
- Clean API design
- Comprehensive documentation
- Type hints
- Unit tests
- CI/CD configuration
- Package distribution setup
- Examples and tutorials""",
        "template": """
Create a Python library for {purpose}.

Requirements:
{requirements}

Features:
{features}

Generate complete library structure:
1. Core module(s)
2. Public API
3. Private implementations
4. Exceptions
5. Configuration
6. Utils/helpers
7. Tests
8. Documentation
9. Setup files
10. Examples
11. README with quick start
        """
    },
    
    "javascript_react": {
        "system": """You are a senior React/JavaScript developer.
Create production-ready React components with:
- Functional components with hooks
- Props validation (PropTypes or TypeScript)
- State management
- Side effects handling
- Performance optimization
- Accessibility (a11y)
- Responsive design
- Component composition""",
        "template": """
Create a React component for {purpose}.

Requirements:
{requirements}

Design specification:
{design}

Generate complete React component with:
1. Component file
2. Styles (CSS/SCSS/Styled-components)
3. PropTypes or TypeScript interfaces
4. Hooks usage
5. Event handlers
6. API integration (if needed)
7. Loading states
8. Error states
9. Tests
10. Storybook stories (optional)
        """
    },
    
    "javascript_express": {
        "system": """You are a senior Node.js/Express developer.
Create robust Express.js APIs with:
- MVC architecture
- Middleware
- Error handling
- Authentication/Authorization
- Database integration
- Validation
- Logging
- Testing""",
        "template": """
Create an Express.js API for {purpose}.

Requirements:
{requirements}

Features:
{features}

Generate complete Express.js application:
1. Server setup
2. Routes
3. Controllers
4. Models
5. Middleware
6. Configuration
7. Database connection
8. Authentication
9. Validation
10. Tests
11. Environment configuration
12. README with setup
        """
    },
    
    "html_css": {
        "system": """You are a senior frontend developer.
Create responsive, accessible HTML/CSS with:
- Semantic HTML5
- CSS Grid/Flexbox
- Mobile-first responsive design
- Accessibility (WCAG)
- Cross-browser compatibility
- Performance optimization
- Clean styling""",
        "template": """
Create a {type} page for {purpose}.

Requirements:
{requirements}

Design mockup:
{design}

Generate complete HTML/CSS:
1. HTML structure
2. CSS styles
3. Responsive breakpoints
4. Interactive elements
5. Animations (if needed)
6. Accessibility features
7. Cross-browser support
        """
    }
}

# ============================================
# 2. CODE ANALYSIS PROMPTS
# ============================================

CODE_ANALYSIS_PROMPTS = {
    "review": {
        "system": """You are a senior code reviewer.
Analyze code for:
- Code quality and style
- Performance issues
- Security vulnerabilities
- Error handling
- Maintainability
- Documentation
- Testing coverage
- Best practices
- Architecture decisions

Provide specific, actionable feedback with examples.""",
        "template": """
Review the following code:

{code}

Review these aspects:
1. Code Quality: Is it clean and well-organized?
2. Performance: Any bottlenecks or optimizations needed?
3. Security: Any vulnerabilities?
4. Error Handling: Are errors properly handled?
5. Documentation: Is the code well-documented?
6. Testing: Are there adequate tests?
7. Architecture: Does it follow best practices?
8. Maintainability: Is it easy to maintain and extend?

Provide specific suggestions for improvement.
        """
    },
    
    "debug": {
        "system": """You are a senior software engineer specializing in debugging.
Analyze bugs and provide solutions:
- Identify root cause
- Analyze stack traces
- Check edge cases
- Review error patterns
- Suggest fixes
- Prevent recurrence
- Consider performance impact""",
        "template": """
Debug this issue:

Problem Description:
{problem}

Error Message:
{error}

Code Context:
{code}

Environment:
{environment}

Analyze and provide:
1. Root cause analysis
2. Steps to reproduce
3. Recommended fix
4. Alternative solutions
5. Prevention strategies
6. Testing approach for the fix
        """
    },
    
    "performance": {
        "system": """You are a performance optimization expert.
Analyze code performance and suggest improvements:
- Identify bottlenecks
- Memory usage analysis
- CPU usage analysis
- Database query optimization
- Caching strategies
- Code optimization
- Algorithm improvement
- Scalability concerns""",
        "template": """
Analyze performance of:

Code:
{code}

Context:
{context}

Metrics:
{metrics}

Provide performance analysis:
1. Current performance issues
2. Bottlenecks identified
3. Suggested optimizations
4. Expected improvement
5. Trade-offs considered
6. Implementation steps
7. Testing approach
        """
    },
    
    "security": {
        "system": """You are a security expert.
Analyze code for security vulnerabilities:
- Input validation
- Authentication/Authorization
- Data encryption
- SQL injection
- XSS prevention
- CSRF protection
- Secure headers
- Dependency vulnerabilities
- Secure coding practices""",
        "template": """
Perform security audit:

Code:
{code}

Context:
{context}

Identify:
1. Security vulnerabilities
2. Risk level (Critical/High/Medium/Low)
3. Exploitation vectors
4. Recommended fixes
5. Prevention strategies
6. Security best practices
7. Additional security measures
        """
    }
}

# ============================================
# 3. CODE REFACTORING PROMPTS
# ============================================

CODE_REFACTORING_PROMPTS = {
    "improve_quality": {
        "system": """You are a senior software architect specializing in code quality.
Refactor code to improve:
- Readability and maintainability
- Code organization
- Naming conventions
- DRY principles
- SOLID principles
- Design patterns
- Performance
- Testability""",
        "template": """
Refactor this code:

Current Code:
{code}

Goals:
{goals}

Constraints:
{constraints}

Provide refactored code with:
1. Improved structure
2. Better naming
3. Extracted functions/classes
4. Proper design patterns
5. Enhanced readability
6. Improved performance
7. Better error handling
8. Documentation
9. Explanation of changes
10. Benefits of refactoring
        """
    },
    
    "extract_module": {
        "system": """You are a senior software architect.
Extract code into reusable modules:
- Identify cohesive functionality
- Define clean interfaces
- Minimize coupling
- Maximize cohesion
- Provide proper abstractions
- Maintain backward compatibility""",
        "template": """
Extract module from:

Source File:
{source_code}

Functionality to extract:
{functionality}

Dependencies:
{dependencies}

Create a new module that:
1. Encapsulates the functionality
2. Exposes clean API
3. Handles dependencies
4. Is independently testable
5. Is well-documented
6. Maintains backward compatibility

Provide:
1. New module code
2. Updated source file
3. Usage examples
4. Documentation
5. Migration guide
        """
    },
    
    "clean_architecture": {
        "system": """You are a senior software architect specializing in Clean Architecture.
Restructure code following Clean Architecture principles:
- Separate concerns
- Dependency inversion
- Domain-driven design
- Use cases
- Repository pattern
- Services layer
- Controllers/Interface adapters
- Frameworks/External dependencies""",
        "template": """
Restructure to Clean Architecture:

Current Code:
{code}

Domain description:
{domain}

Features:
{features}

Provide Clean Architecture structure:
1. Domain layer (Entities, Value Objects)
2. Use Cases (Application layer)
3. Interface Adapters (Controllers, Presenters)
4. Infrastructure (Repositories, External services)
5. Frameworks (Web framework, Database)

For each layer provide:
- Code files
- Interfaces
- Implementations
- Tests
- Documentation
        """
    }
}

# ============================================
# 4. TESTING PROMPTS
# ============================================

TESTING_PROMPTS = {
    "unit_test": {
        "system": """You are a QA engineer specializing in unit testing.
Generate comprehensive unit tests:
- Test all public methods/functions
- Edge cases
- Error conditions
- Positive and negative scenarios
- Mocking external dependencies
- Test coverage targets
- Clear test descriptions""",
        "template": """
Generate unit tests for:

Source File:
{source_code}

Functions to test:
{functions}

Dependencies:
{dependencies}

Generate tests covering:
1. Happy path scenarios
2. Edge cases
3. Error handling
4. Boundary conditions
5. Integration with dependencies
6. Performance critical paths

Provide complete test file with:
- Proper imports
- Test class structure
- Test methods with assertions
- Mock objects
- Setup/Teardown
- Comments explaining tests
        """
    },
    
    "integration_test": {
        "system": """You are a QA engineer specializing in integration testing.
Generate integration tests:
- API testing
- Database integration
- Service integration
- End-to-end flows
- Authentication/Authorization
- Error scenarios
- Performance testing""",
        "template": """
Generate integration tests for:

System:
{system_description}

Components:
{components}

APIs/Endpoints:
{endpoints}

Database:
{database_schema}

Generate integration tests covering:
1. API endpoint testing
2. Database operations
3. Service interactions
4. Error scenarios
5. Authentication flows
6. Performance benchmarks

Provide complete test files with:
- Test setup
- Configuration
- Test cases
- Assertions
- Cleanup
- Reporting
        """
    },
    
    "e2e_test": {
        "system": """You are a QA engineer specializing in end-to-end testing.
Generate E2E tests:
- User journeys
- Critical paths
- Cross-browser testing
- Performance testing
- Accessibility testing
- Error scenarios
- Real user scenarios""",
        "template": """
Generate E2E tests for:

Application:
{application}

User Journeys:
{user_journeys}

Critical Features:
{critical_features}

Generate E2E tests covering:
1. User login/authentication
2. Main user journeys
3. Critical business flows
4. Error handling
5. Edge cases

Provide test files with:
- Test framework setup
- Page objects/selectors
- Test scenarios
- Assertions
- Reporting
        """
    }
}

# ============================================
# 5. DOCUMENTATION PROMPTS
# ============================================

DOCUMENTATION_PROMPTS = {
    "api_docs": {
        "system": """You are a technical writer specializing in API documentation.
Generate comprehensive API documentation:
- Overview
- Authentication
- Endpoints
- Request/Response examples
- Error codes
- Rate limiting
- Versioning
- SDKs/Code examples
- Interactive docs (OpenAPI)""",
        "template": """
Generate API documentation for:

API Name: {api_name}
Purpose: {purpose}
Endpoints:
{endpoints}

Generate complete documentation:
1. API Overview
2. Authentication/Authorization
3. Base URL and headers
4. Endpoint documentation for each:
   - Description
   - HTTP method
   - URL parameters
   - Request body
   - Response format
   - Error codes
   - Examples
5. Rate limiting
6. Versioning
7. Error handling
8. Code examples (Python, JavaScript, cURL)
9. OpenAPI/Swagger spec (optional)
        """
    },
    
    "technical_docs": {
        "system": """You are a senior technical writer.
Generate comprehensive technical documentation:
- Architecture overview
- System design
- Component descriptions
- Data flow
- Deployment
- Configuration
- Troubleshooting
- Performance tuning""",
        "template": """
Generate technical documentation for:

System: {system_name}
Purpose: {purpose}
Technology Stack:
{tech_stack}
Components:
{components}

Generate complete documentation:
1. System Overview
2. Architecture Diagram (text description)
3. Component Details
   - Purpose
   - Technology
   - Dependencies
   - Configuration
4. Data Flow
5. Deployment Guide
6. Configuration Guide
7. API Reference
8. Monitoring and Logging
9. Troubleshooting Guide
10. Performance Tuning
11. Security Considerations
12. Future Improvements
        """
    },
    
    "user_guide": {
        "system": """You are a technical writer specializing in user documentation.
Generate user-friendly guides:
- Getting started
- Tutorials
- How-to guides
- Reference
- FAQ
- Troubleshooting
- Best practices""",
        "template": """
Generate user guide for:

Product: {product_name}
Purpose: {purpose}
Target Audience: {audience}
Features:
{features}

Generate complete user guide:
1. Introduction
2. Getting Started
   - Installation/Setup
   - First steps
   - Quick start
3. Core Features
   - Step-by-step guides
   - Screenshot descriptions
   - Tips and tricks
4. Advanced Features
5. Customization
6. Troubleshooting
7. FAQ
8. Best Practices
9. Support
        """
    }
}

# ============================================
# 6. DEPLOYMENT PROMPTS
# ============================================

DEPLOYMENT_PROMPTS = {
    "docker": {
        "system": """You are a DevOps engineer specializing in containerization.
Create Docker configurations:
- Dockerfile
- Docker Compose
- Multi-stage builds
- Environment configuration
- Health checks
- Volume management
- Networking
- Security""",
        "template": """
Generate Docker configuration for:

Application: {application}
Technology Stack:
{tech_stack}
Services:
{services}

Generate:
1. Dockerfile(s)
   - Multi-stage builds
   - Layer optimization
   - Environment variables
   - Health checks
2. Docker Compose file
   - Services
   - Networks
   - Volumes
   - Environment variables
   - Dependencies
3. .dockerignore
4. Environment config (.env)
5. Deployment scripts
6. Documentation
        """
    },
    
    "kubernetes": {
        "system": """You are a DevOps engineer specializing in Kubernetes.
Create Kubernetes configurations:
- Deployments
- Services
- ConfigMaps
- Secrets
- Ingress
- Persistent Volumes
- StatefulSets
- HPA (Horizontal Pod Autoscaling)""",
        "template": """
Generate Kubernetes configuration for:

Application: {application}
Services:
{services}
Resource Requirements:
{resources}

Generate:
1. Deployment files
2. Service files
3. ConfigMaps
4. Secrets
5. Ingress rules
6. Persistent Volume Claims
7. StatefulSets (if needed)
8. HPA configuration
9. Service Mesh (optional)
10. Monitoring configurations
11. Documentation
        """
    },
    
    "ci_cd": {
        "system": """You are a DevOps engineer specializing in CI/CD.
Create CI/CD pipeline configurations:
- GitHub Actions
- GitLab CI
- Jenkins
- CircleCI
- Deployment stages
- Testing
- Building
- Deployment
- Monitoring""",
        "template": """
Generate CI/CD pipeline for:

Project: {project}
Technology Stack:
{tech_stack}
Deployment Target:
{deployment_target}

Generate pipeline configuration:
1. CI configuration
   - Linting
   - Testing
   - Building
   - Artifact creation
2. CD configuration
   - Staging deployment
   - Production deployment
   - Rollback strategy
3. Environment configuration
4. Security scanning
5. Performance testing
6. Documentation
        """
    }
}

# ============================================
# 7. PROBLEM SOLVING PROMPTS
# ============================================

PROBLEM_SOLVING_PROMPTS = {
    "system_design": {
        "system": """You are a senior system architect.
Design scalable, reliable systems:
- System architecture
- Database design
- Caching strategy
- Load balancing
- Microservices vs Monolith
- Security
- Monitoring
- Scalability
- Disaster recovery""",
        "template": """
Design a system for:

Problem: {problem}
Requirements:
{requirements}
Scale:
{scale_requirements}

Provide complete system design:
1. Architecture Overview
2. Technology Stack
3. Data Model
4. API Design
5. Service Components
6. Caching Strategy
7. Load Balancing
8. Database Design
9. Security Architecture
10. Monitoring Strategy
11. Deployment Strategy
12. Scalability Plan
13. Disaster Recovery
14. Cost Estimation
15. Implementation Phases
        """
    },
    
    "algorithm": {
        "system": """You are an algorithms expert.
Design efficient algorithms:
- Time complexity
- Space complexity
- Edge cases
- Optimization
- Implementation
- Testing
- Documentation""",
        "template": """
Design algorithm for:

Problem: {problem}
Input: {input}
Output: {output}
Constraints:
{constraints}

Provide:
1. Algorithm description
2. Approach/Strategy
3. Pseudocode
4. Implementation code
5. Complexity analysis
6. Edge cases
7. Optimization opportunities
8. Tests
9. Documentation
        """
    }
}

# ============================================
# 8. UTILITY FUNCTIONS
# ============================================

def get_task_prompt(task_type: str, task_name: str, context: Dict[str, Any]) -> tuple:
    """
    Get the appropriate prompt for a task
    
    Args:
        task_type: Type of task (code, analysis, refactor, test, documentation, deployment)
        task_name: Specific task name
        context: Context dictionary with variables
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    prompts_mapping = {
        "code": CODE_GENERATION_PROMPTS,
        "analysis": CODE_ANALYSIS_PROMPTS,
        "refactor": CODE_REFACTORING_PROMPTS,
        "test": TESTING_PROMPTS,
        "documentation": DOCUMENTATION_PROMPTS,
        "deployment": DEPLOYMENT_PROMPTS,
        "problem": PROBLEM_SOLVING_PROMPTS
    }
    
    if task_type not in prompts_mapping:
        raise ValueError(f"Invalid task type: {task_type}")
    
    if task_name not in prompts_mapping[task_type]:
        raise ValueError(f"Invalid task name: {task_name}")
    
    prompt_data = prompts_mapping[task_type][task_name]
    
    # Format the template with context
    try:
        user_prompt = prompt_data["template"].format(**context)
    except KeyError as e:
        # Add missing keys as empty strings
        for key in str(e).split():
            if key not in context:
                context[key] = "TBD"
        user_prompt = prompt_data["template"].format(**context)
    
    return prompt_data["system"], user_prompt

def get_code_generation_prompt(framework: str, purpose: str, requirements: List[str], 
                               features: List[str], context: Dict[str, Any] = None) -> tuple:
    """
    Get code generation prompt for specific framework
    
    Args:
        framework: Python, React, Express, etc.
        purpose: What the code should do
        requirements: List of requirements
        features: List of features
        context: Additional context
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if context is None:
        context = {}
    
    # Determine task based on framework
    if "python" in framework.lower():
        if "api" in purpose.lower():
            task_name = "python_api"
        elif "cli" in purpose.lower():
            task_name = "python_cli"
        else:
            task_name = "python_library"
    elif "react" in framework.lower():
        task_name = "javascript_react"
    elif "express" in framework.lower() or "node" in framework.lower():
        task_name = "javascript_express"
    else:
        task_name = "html_css"
    
    prompt_data = CODE_GENERATION_PROMPTS.get(task_name)
    
    if not prompt_data:
        raise ValueError(f"No prompt found for task: {task_name}")
    
    # Prepare context
    prompt_context = {
        "framework": framework,
        "purpose": purpose,
        "requirements": "\n".join(f"- {req}" for req in requirements),
        "features": "\n".join(f"- {feat}" for feat in features),
        **context
    }
    
    return prompt_data["system"], prompt_data["template"].format(**prompt_context)

def get_review_prompt(code: str, context: Dict[str, Any] = None) -> tuple:
    """
    Get code review prompt
    
    Args:
        code: Code to review
        context: Additional context
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if context is None:
        context = {}
    
    prompt_data = CODE_ANALYSIS_PROMPTS["review"]
    
    prompt_context = {
        "code": code,
        **context
    }
    
    return prompt_data["system"], prompt_data["template"].format(**prompt_context)

def get_test_prompt(source_code: str, functions: List[str], dependencies: List[str] = None) -> tuple:
    """
    Get test generation prompt
    
    Args:
        source_code: Source code to test
        functions: Functions to test
        dependencies: External dependencies
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if dependencies is None:
        dependencies = []
    
    prompt_data = TESTING_PROMPTS["unit_test"]
    
    prompt_context = {
        "source_code": source_code,
        "functions": "\n".join(f"- {func}" for func in functions),
        "dependencies": "\n".join(f"- {dep}" for dep in dependencies)
    }
    
    return prompt_data["system"], prompt_data["template"].format(**prompt_context)

def get_refactor_prompt(code: str, goals: List[str], constraints: List[str] = None) -> tuple:
    """
    Get code refactoring prompt
    
    Args:
        code: Code to refactor
        goals: Refactoring goals
        constraints: Refactoring constraints
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if constraints is None:
        constraints = []
    
    prompt_data = CODE_REFACTORING_PROMPTS["improve_quality"]
    
    prompt_context = {
        "code": code,
        "goals": "\n".join(f"- {goal}" for goal in goals),
        "constraints": "\n".join(f"- {constraint}" for constraint in constraints)
    }
    
    return prompt_data["system"], prompt_data["template"].format(**prompt_context)

def get_documentation_prompt(doc_type: str, **kwargs) -> tuple:
    """
    Get documentation generation prompt
    
    Args:
        doc_type: Type of documentation (api_docs, technical_docs, user_guide)
        **kwargs: Documentation-specific parameters
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    prompt_data = DOCUMENTATION_PROMPTS.get(doc_type)
    
    if not prompt_data:
        raise ValueError(f"Invalid documentation type: {doc_type}")
    
    return prompt_data["system"], prompt_data["template"].format(**kwargs)

def get_deployment_prompt(deployment_type: str, **kwargs) -> tuple:
    """
    Get deployment configuration prompt
    
    Args:
        deployment_type: docker, kubernetes, ci_cd
        **kwargs: Deployment-specific parameters
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    prompt_data = DEPLOYMENT_PROMPTS.get(deployment_type)
    
    if not prompt_data:
        raise ValueError(f"Invalid deployment type: {deployment_type}")
    
    return prompt_data["system"], prompt_data["template"].format(**kwargs)

# ============================================
# 9. TASK DISPATCHER
# ============================================

class TaskPromptDispatcher:
    """Dispatches appropriate prompts for different tasks"""
    
    @staticmethod
    def get_prompt(task: str, **kwargs) -> tuple:
        """
        Get prompt for a specific task
        
        Args:
            task: Task type (code_generation, review, test, refactor, documentation, deployment, system_design)
            **kwargs: Task-specific parameters
            
        Returns:
            tuple: (system_prompt, user_prompt)
        """
        task_mapping = {
            "code_generation": "get_code_generation_prompt",
            "review": "get_review_prompt",
            "test": "get_test_prompt",
            "refactor": "get_refactor_prompt",
            "documentation": "get_documentation_prompt",
            "deployment": "get_deployment_prompt",
            "system_design": "get_system_design_prompt"
        }
        
        if task not in task_mapping:
            raise ValueError(f"Invalid task: {task}")
        
        return globals()[task_mapping[task]](**kwargs)
    
    @staticmethod
    def get_system_design_prompt(problem: str, requirements: List[str], scale_requirements: str = None) -> tuple:
        """Get system design prompt"""
        prompt_data = PROBLEM_SOLVING_PROMPTS["system_design"]
        
        if scale_requirements is None:
            scale_requirements = "Not specified"
        
        prompt_context = {
            "problem": problem,
            "requirements": "\n".join(f"- {req}" for req in requirements),
            "scale_requirements": scale_requirements
        }
        
        return prompt_data["system"], prompt_data["template"].format(**prompt_context)