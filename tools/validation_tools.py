import ast
import subprocess
from typing import Dict, Any, List, Optional

class ValidationTools:
    """Code validation and testing tools"""
    
    def validate_changes(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Validate changes made by the agent"""
        
        result = {
            "success": True,
            "errors": [],
            "warnings": []
        }
        
        # Validate Python files
        for file_path in changes.get("files_created", []):
            if file_path.endswith('.py'):
                validation = self.validate_python_file(file_path)
                if not validation.get("valid"):
                    result["errors"].extend(validation.get("errors", []))
                    result["warnings"].extend(validation.get("warnings", []))
        
        for file_path in changes.get("files_updated", []):
            if file_path.endswith('.py'):
                validation = self.validate_python_file(file_path)
                if not validation.get("valid"):
                    result["errors"].extend(validation.get("errors", []))
                    result["warnings"].extend(validation.get("warnings", []))
        
        if result["errors"]:
            result["success"] = False
        
        return result
    
    def validate_python_file(self, file_path: str) -> Dict[str, Any]:
        """Validate a Python file"""
        
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check syntax
            with open(file_path, 'r') as f:
                content = f.read()
            
            ast.parse(content)
            
            # Check for potential issues
            tree = ast.parse(content)
            
            # Check for unused imports
            imports = set()
            used_names = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
                elif isinstance(node, ast.Name):
                    if isinstance(node.ctx, ast.Load):
                        used_names.add(node.id)
            
            unused_imports = imports - used_names
            if unused_imports:
                result["warnings"].append(f"Unused imports: {', '.join(unused_imports)}")
            
            # Check for missing docstrings
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        result["warnings"].append(f"Missing docstring: {node.name}")
            
        except SyntaxError as e:
            result["valid"] = False
            result["errors"].append(f"Syntax error: {str(e)}")
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Error: {str(e)}")
        
        return result
    
    def run_tests(self, test_path: str = "tests/") -> Dict[str, Any]:
        """Run tests using pytest"""
        
        result = {
            "success": False,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": []
        }
        
        try:
            # Try to run pytest
            test_result = subprocess.run(
                ['pytest', test_path, '-v', '--tb=short'],
                capture_output=True,
                text=True
            )
            
            # Parse output (simplified)
            output = test_result.stdout
            
            if "passed" in output:
                result["success"] = True
            
            result["tests_run"] = output.count('PASSED') + output.count('FAILED')
            result["tests_passed"] = output.count('PASSED')
            result["tests_failed"] = output.count('FAILED')
            
            if test_result.stderr:
                result["errors"] = test_result.stderr.split('\n')
                
        except FileNotFoundError:
            result["errors"].append("pytest not installed. Run: pip install pytest")
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def lint_python(self, file_path: str) -> List[str]:
        """Run flake8 linter on Python file"""
        
        try:
            result = subprocess.run(
                ['flake8', file_path],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                return result.stdout.split('\n')
            return []
            
        except FileNotFoundError:
            return ["flake8 not installed. Run: pip install flake8"]
        except Exception as e:
            return [str(e)]