import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

class GitTools:
    """Git operations for version control"""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        
    def is_git_repo(self) -> bool:
        """Check if project is a git repository"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def get_status(self) -> List[str]:
        """Get git status"""
        if not self.is_git_repo():
            return []
        
        try:
            result = subprocess.run(
                ['git', 'status', '--short'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return [line for line in result.stdout.split('\n') if line]
        except Exception as e:
            print(f"Error getting git status: {e}")
            return []
    
    def commit(self, message: str) -> bool:
        """Commit changes"""
        if not self.is_git_repo():
            return False
        
        try:
            # Add all changes
            subprocess.run(
                ['git', 'add', '.'],
                cwd=self.project_path,
                capture_output=True
            )
            
            # Commit
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            return result.returncode == 0
        except Exception as e:
            print(f"Error committing: {e}")
            return False
    
    def get_branch(self) -> Optional[str]:
        """Get current branch name"""
        if not self.is_git_repo():
            return None
        
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None
    
    def create_branch(self, branch_name: str) -> bool:
        """Create and switch to new branch"""
        if not self.is_git_repo():
            return False
        
        try:
            result = subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error creating branch: {e}")
            return False
    
    def get_diff(self) -> str:
        """Get diff of changes"""
        if not self.is_git_repo():
            return ""
        
        try:
            result = subprocess.run(
                ['git', 'diff'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            print(f"Error getting diff: {e}")
            return ""