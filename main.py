import os
import sys
import json
import time
from typing import Dict, Any, List
from agent_core.agent_orchestrator import SoftwareAgent
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Load environment variables
load_dotenv()

class SoftwareAgentCLI:
    """Command-line interface for the software engineer agent"""
    
    def __init__(self):
        self.agent = SoftwareAgent()
        self.current_project = None
        self.session_history = []
        
    def display_welcome(self):
        """Display welcome banner"""
        print(f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════════╗
║  {Style.BRIGHT}🤖 AI Software Engineer Agent{Fore.RESET}{Fore.CYAN}                            ║
║  {Fore.LIGHTBLACK_EX}Your intelligent coding assistant for software development{Fore.RESET}{Fore.CYAN}    ║
╚══════════════════════════════════════════════════════════════════╝{Fore.RESET}
        
{Fore.GREEN}📌 Commands:
  • Describe what you want to build or fix
  • "list files" - Show all project files
  • "view <filename>" - View file content
  • "status" - Show current project status
  • "commit" - Commit changes
  • "help" - Show this menu
  • "exit" - Quit the agent{Fore.RESET}
        """)
    
    def process_user_request(self, user_input: str) -> Dict[str, Any]:
        """Process user request through the agent"""
        print(f"\n{Fore.YELLOW}🤔 Agent is analyzing your request...{Fore.RESET}")
        
        # Simulate thinking
        time.sleep(0.5)
        
        # Process through agent
        result = self.agent.process_request(user_input)
        
        return result
    
    def display_result(self, result: Dict[str, Any]):
        """Display the agent's response and actions"""
        if result.get("status") == "success":
            print(f"\n{Fore.GREEN}✅ Success!{Fore.RESET}")
            
            # Display what was created/updated
            if result.get("files_created"):
                print(f"\n{Fore.CYAN}📁 Files Created:{Fore.RESET}")
                for file in result["files_created"]:
                    print(f"  ✅ {file}")
            
            if result.get("files_updated"):
                print(f"\n{Fore.YELLOW}📝 Files Updated:{Fore.RESET}")
                for file in result["files_updated"]:
                    print(f"  🔄 {file}")
            
            if result.get("summary"):
                print(f"\n{Fore.WHITE}📋 Summary:{Fore.RESET}")
                print(f"  {result['summary']}")
            
            if result.get("suggestions"):
                print(f"\n{Fore.MAGENTA}💡 Suggestions:{Fore.RESET}")
                for suggestion in result["suggestions"]:
                    print(f"  • {suggestion}")
                    
        else:
            print(f"\n{Fore.RED}❌ Error: {result.get('message', 'Unknown error')}{Fore.RESET}")
            if result.get("suggestions"):
                print(f"\n{Fore.YELLOW}💡 Suggestions:{Fore.RESET}")
                for suggestion in result["suggestions"]:
                    print(f"  • {suggestion}")
    
    def run(self):
        """Main CLI loop"""
        self.display_welcome()
        
        while True:
            try:
                # Get user input
                user_input = input(f"\n{Fore.GREEN}👤 You:{Fore.RESET} ")
                
                # Check for special commands
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print(f"\n{Fore.MAGENTA}👋 Thank you for using AI Software Engineer Agent!{Fore.RESET}\n")
                    break
                
                elif user_input.lower() == 'help':
                    self.display_welcome()
                    continue
                
                elif user_input.lower() == 'status':
                    self.agent.show_status()
                    continue
                
                elif user_input.lower().startswith('view '):
                    filename = user_input[5:].strip()
                    self.agent.view_file(filename)
                    continue
                
                elif user_input.lower() == 'list files':
                    self.agent.list_files()
                    continue
                
                # Process through agent
                result = self.process_user_request(user_input)
                self.display_result(result)
                
                # Save to history
                self.session_history.append({
                    "user_input": user_input,
                    "result": result
                })
                
            except KeyboardInterrupt:
                print(f"\n\n{Fore.YELLOW}👋 Goodbye!{Fore.RESET}")
                break
            except Exception as e:
                print(f"\n{Fore.RED}⚠️ Error: {str(e)}{Fore.RESET}")

if __name__ == "__main__":
    cli = SoftwareAgentCLI()
    cli.run()