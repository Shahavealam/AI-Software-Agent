import ast
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

class CodeAnalyzer:
    """Analyzes Python code structure and dependencies"""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a single Python file"""
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return {"error": "File not found"}
        
        with open(full_path, 'r') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
            analysis = {
                "imports": [],
                "classes": [],
                "functions": [],
                "variables": [],
                "dependencies": [],
                "docstring": ast.get_docstring(tree) or ""
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    analysis["imports"].append(node.module or "")
                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    analysis["functions"].append(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            analysis["variables"].append(target.id)
            
            # Find dependencies
            for imp in analysis["imports"]:
                if not imp.startswith('.'):
                    analysis["dependencies"].append(imp)
            
            return analysis
            
        except SyntaxError as e:
            return {"error": f"Syntax error: {str(e)}"}
    
    def analyze_project(self) -> Dict[str, Any]:
        """Analyze entire project structure"""
        project_analysis = {
            "files": {},
            "total_files": 0,
            "python_files": 0,
            "dependencies": set(),
            "structure": {}
        }
        
        for root, dirs, files in os.walk(self.project_path):
            # Skip __pycache__ and .git
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            if '.git' in dirs:
                dirs.remove('.git')
            
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(self.project_path)
                    
                    project_analysis["python_files"] += 1
                    analysis = self.analyze_file(str(rel_path))
                    
                    if "error" not in analysis:
                        project_analysis["files"][str(rel_path)] = analysis
                        for dep in analysis.get("dependencies", []):
                            project_analysis["dependencies"].add(dep)
        
        project_analysis["total_files"] = len(project_analysis["files"])
        project_analysis["dependencies"] = list(project_analysis["dependencies"])
        
        return project_analysis
    
    def find_functions_by_name(self, name: str) -> List[str]:
        """Find all functions with a given name"""
        results = []
        project_analysis = self.analyze_project()
        
        for file_path, analysis in project_analysis["files"].items():
            if name in analysis.get("functions", []):
                results.append(file_path)
        
        return results
    
    def find_class_by_name(self, name: str) -> List[str]:
        """Find all classes with a given name"""
        results = []
        project_analysis = self.analyze_project()
        
        for file_path, analysis in project_analysis["files"].items():
            if name in analysis.get("classes", []):
                results.append(file_path)
        
        return results
    
    def get_file_dependencies(self, file_path: str) -> List[str]:
        """Get dependencies of a specific file"""
        analysis = self.analyze_file(file_path)
        return analysis.get("dependencies", [])
    
    def suggest_imports(self, file_path: str) -> List[str]:
        """Suggest missing imports based on code analysis"""
        full_path = self.project_path / file_path
        
        if not full_path.exists():
            return []
        
        with open(full_path, 'r') as f:
            content = f.read()
        
        # Look for undefined names that might need imports
        suggestions = []
        
        try:
            tree = ast.parse(content)
            local_names = set()
            
            # Collect defined names
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    local_names.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            local_names.add(target.id)
            
            # Find undefined names
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    if (isinstance(node.ctx, ast.Load) and 
                        node.id not in local_names and 
                        not node.id.startswith('_')):
                        # This might need an import
                        if node.id not in suggestions:
                            suggestions.append(node.id)
            
            return suggestions
            
        except SyntaxError:
            return []