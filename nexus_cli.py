#!/usr/bin/env python3
"""
Interactive Nexus CLI Tool with Natural Language Processing
Supports both OpenAI and Anthropic Claude models
Accepts natural language commands and provides intelligent analysis
"""

import asyncio
import json
import re
import os
import sys
import socket
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
import urllib3
import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass
import paramiko
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.spinner import Spinner
import argparse
import time

from dotenv import load_dotenv
load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@dataclass
class NexusSwitch:
    hostname: str
    ip: str
    username: str
    password: str
    api_port: int = 443
    ssh_port: int = 22

class NexusClient:
    def __init__(self, switch: NexusSwitch):
        self.switch = switch
        self.ssh_client = None

    def connect_ssh(self):
        """Establish SSH connection"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                hostname=self.switch.ip,
                port=self.switch.ssh_port,
                username=self.switch.username,
                password=self.switch.password,
                timeout=10
            )
            return True
        except Exception as e:
            return False

    def execute_command(self, command: str) -> str:
        """Execute CLI command via SSH (supports config mode & disables pagination)"""
        if not self.ssh_client:
            if not self.connect_ssh():
                return f"SSH connection failed to {self.switch.ip}"

        try:
            shell = self.ssh_client.invoke_shell()
            shell.settimeout(10)
            buffer = ""

            # Clean login banner
            time.sleep(1)
            shell.recv(4096)

            # Disable pagination first
            shell.send("terminal length 0\n")
            time.sleep(0.5)
            shell.recv(4096)

            # Determine if this is a configuration command
            command_lower = command.lower().strip()
            is_show_command = command_lower.startswith('show ') or command_lower.startswith('display ')
            is_config_command = not is_show_command and any(keyword in command_lower for keyword in [
                'configure terminal', 'interface ethernet', 'interface vlan', 'router bgp',
                'vlan ', 'snmp-server', 'feature ', 'vpc ', 'no shutdown', 'shutdown',
                'description ', 'ip address', 'switchport', 'neighbor ', 'address-family'
            ])

            # Only enter config mode for actual configuration commands
            if is_config_command:
                shell.send("configure terminal\n")
                time.sleep(0.5)
                shell.recv(4096)

            # Send the command
            shell.send(command + "\n")
            time.sleep(2)

            # Read all output with improved handling
            timeout_count = 0
            max_timeouts = 10

            while timeout_count < max_timeouts:
                try:
                    chunk = shell.recv(4096).decode("utf-8", errors='ignore')
                    if chunk:
                        buffer += chunk
                        timeout_count = 0

                        # Check if we've reached a prompt
                        if re.search(r'[>#]\s*$', chunk.strip()):
                            break
                        elif "--More--" in chunk:
                            shell.send(" ")  # Spacebar to advance
                            time.sleep(0.2)
                    else:
                        timeout_count += 1
                        time.sleep(0.1)

                except socket.timeout:
                    timeout_count += 1
                    time.sleep(0.1)
                except Exception as e:
                    break

            # Exit config mode only if we entered it
            if is_config_command:
                shell.send("end\n")
                time.sleep(0.5)
                shell.recv(4096)

            shell.close()
            return buffer.strip()

        except Exception as e:
            return f"Command execution failed: {e}"

    def execute_command_block(self, commands: List[str]) -> str:
        """Execute a block of commands in a single SSH session maintaining context"""
        if not self.ssh_client:
            if not self.connect_ssh():
                return f"SSH connection failed to {self.switch.ip}"

        try:
            shell = self.ssh_client.invoke_shell()
            shell.settimeout(10)
            buffer = ""

            # Clean login banner
            time.sleep(1)
            shell.recv(4096)

            # Disable pagination
            shell.send("terminal length 0\n")
            time.sleep(0.5)
            shell.recv(4096)

            # Execute all commands in sequence
            for command in commands:
                shell.send(command + "\n")
                time.sleep(1)

                # Read output for this command
                try:
                    chunk = shell.recv(4096).decode("utf-8", errors='ignore')
                    buffer += f"\n--- Command: {command} ---\n"
                    buffer += chunk

                    # Handle --More-- prompts
                    while "--More--" in chunk:
                        shell.send(" ")
                        time.sleep(0.2)
                        chunk = shell.recv(4096).decode("utf-8", errors='ignore')
                        buffer += chunk

                except:
                    buffer += f"\n--- Command: {command} ---\n[Timeout or error reading output]\n"

            # Exit configuration mode
            shell.send("end\n")
            time.sleep(0.5)
            final_chunk = shell.recv(4096).decode("utf-8", errors='ignore')
            buffer += final_chunk

            shell.close()
            return buffer.strip()

        except Exception as e:
            return f"Command block execution failed: {e}"

    def close(self):
        """Close SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()

class AIModelManager:
    """Manages different AI models (OpenAI, Anthropic Claude, Ollama)"""

    def __init__(self):
        self.available_models = {}
        self.current_model = None
        self.setup_models()

    def setup_models(self):
        """Initialize available AI models"""

        # OpenAI GPT models
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.available_models["gpt-4o-mini"] = {
                "client": ChatOpenAI(
                    model="gpt-4o-mini",
                    api_key=openai_key,
                    temperature=0.8,
                    max_tokens=3000
                ),
                "provider": "OpenAI",
                "description": "GPT-4o Mini - Fast and efficient"
            }

            self.available_models["gpt-4o"] = {
                "client": ChatOpenAI(
                    model="gpt-4o",
                    api_key=openai_key,
                    temperature=0.8,
                    max_tokens=3000
                ),
                "provider": "OpenAI",
                "description": "GPT-4o - Most capable OpenAI model"
            }

        # Anthropic Claude models
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            # Claude 4 models (latest)
            self.available_models["claude-sonnet-4-20250514"] = {
                "client": ChatAnthropic(
                    model="claude-sonnet-4-20250514",
                    api_key=anthropic_key,
                    temperature=0.8,
                    max_tokens=3000
                ),
                "provider": "Anthropic",
                "description": "Claude Sonnet 4 - Latest and most capable Claude model"
            }

            self.available_models["claude-opus-4-20250514"] = {
                "client": ChatAnthropic(
                    model="claude-opus-4-20250514",
                    api_key=anthropic_key,
                    temperature=0.8,
                    max_tokens=3000
                ),
                "provider": "Anthropic",
                "description": "Claude Opus 4 - Latest and most capable Claude model"
            }

            # Claude 3.5 models
            self.available_models["claude-3-5-sonnet-20241022"] = {
                "client": ChatAnthropic(
                    model="claude-3-5-sonnet-20241022",
                    api_key=anthropic_key,
                    temperature=0.8,
                    max_tokens=3000
                ),
                "provider": "Anthropic",
                "description": "Claude 3.5 Sonnet - Excellent reasoning and analysis"
            }

            self.available_models["claude-3-haiku-20240307"] = {
                "client": ChatAnthropic(
                    model="claude-3-haiku-20240307",
                    api_key=anthropic_key,
                    temperature=0.8,
                    max_tokens=3000
                ),
                "provider": "Anthropic",
                "description": "Claude 3 Haiku - Fast and efficient"
            }

        # Ollama (local models)
        try:
            # Test if Ollama is available
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self.available_models["llama3.3"] = {
                    "client": ChatOllama(
                        base_url="http://localhost:11434",
                        model="llama3.3",
                        temperature=0.1,
                        num_predict=2048
                    ),
                    "provider": "Ollama",
                    "description": "Llama 3.3 - Local model"
                }
        except:
            pass  # Ollama not available

        # Set default model
        if self.available_models:
            # Prefer Claude Sonnet 4, then Claude 3.5 Sonnet, then GPT, then others
            claude_4_models = [model for model in self.available_models if "claude-sonnet-4" in model]
            claude_3_5_models = [model for model in self.available_models if "claude-3-5-sonnet" in model]
            gpt_4o_mini_models = [model for model in self.available_models if "gpt-4o-mini" in model]
            llama3_70b_models = [model for model in self.available_models if "llama3.3" in model]

            if claude_4_models:
                self.current_model = claude_4_models[0]
            elif claude_3_5_models:
                self.current_model = claude_3_5_models[0]
            elif gpt_4o_mini_models:
                self.current_model = gpt_4o_mini_models[0]
            elif llama3_70b_models:
                self.current_model = llama3_70b_models[0]
            else:
                self.current_model = list(self.available_models.keys())[0]

    def get_available_models(self) -> Dict:
        """Get list of available models"""
        return self.available_models

    def set_model(self, model_name: str) -> bool:
        """Set the current model"""
        if model_name in self.available_models:
            self.current_model = model_name
            return True
        return False

    def get_current_model(self):
        """Get the current model client"""
        if self.current_model and self.current_model in self.available_models:
            return self.available_models[self.current_model]["client"]
        return None

    def get_current_model_info(self) -> Dict:
        """Get current model information"""
        if self.current_model and self.current_model in self.available_models:
            return {
                "name": self.current_model,
                **self.available_models[self.current_model]
            }
        return None

    def display_available_models(self, console: Console):
        """Display available AI models in a formatted table"""
        if not self.available_models:
            console.print("[red]❌ No AI models available![/red]")
            console.print("[yellow]Please set one of the following API keys:[/yellow]")
            console.print("• OPENAI_API_KEY='your-openai-key'")
            console.print("• ANTHROPIC_API_KEY='your-anthropic-key'")
            console.print("• Or install Ollama with llama3.3 model")
            return

        table = Table(title="Available AI Models", title_style="bold green")
        table.add_column("Model Name", style="cyan", no_wrap=True)
        table.add_column("Provider", style="green")
        table.add_column("Description", style="blue")
        table.add_column("Status", style="yellow")

        for model_name, model_info in self.available_models.items():
            status = "🟢 Default" if model_name == self.current_model else "⚪ Available"
            table.add_row(
                model_name,
                model_info["provider"],
                model_info["description"],
                status
            )

        console.print(table)
        console.print(f"\n[dim]Current default model: {self.current_model}[/dim]")
        console.print(f"[dim]Use --model <model_name> to specify a different model[/dim]")

class NaturalLanguageNexusCLI:
    def __init__(self, initial_model: Optional[str] = None, show_raw: bool = False):
        self.console = Console()
        self.show_raw = show_raw  # Store the show_raw flag

        # Initialize AI Model Manager
        self.ai_manager = AIModelManager()

        if not self.ai_manager.get_available_models():
            self.console.print("[red]❌ No AI models available![/red]")
            self.console.print("[yellow]Please set one of the following API keys:[/yellow]")
            self.console.print("• OPENAI_API_KEY='your-openai-key'")
            self.console.print("• ANTHROPIC_API_KEY='your-anthropic-key'")
            self.console.print("• Or install Ollama with llama3.3 model")
            exit(1)

        # Set initial model if specified
        if initial_model:
            if not self.ai_manager.set_model(initial_model):
                self.console.print(f"[red]❌ Model '{initial_model}' not available[/red]")
                self.console.print("[yellow]Available models:[/yellow]")
                for model in self.ai_manager.get_available_models():
                    self.console.print(f"  • {model}")
                exit(1)

        # Show current model
        current_model_info = self.ai_manager.get_current_model_info()
        self.console.print(f"[green]🤖 Using AI Model: {current_model_info['description']} ({current_model_info['provider']})[/green]")

        # Load switch configurations
        self.switches = self.load_switches()
        self.current_switch = None

        # Command history and context
        self.command_history = []
        self.context = {
            "last_command": None,
            "last_output": None,
            "session_notes": []
        }

        # Only show the panel in interactive mode (not batch mode)
        if not self.show_raw:
            self.console.print(Panel.fit(
                "[bold green]🌐 Interactive Nexus CLI Tool[/bold green]\n"
                "[cyan]Natural Language Command Interface for Cisco Nexus Switches[/cyan]\n"
                f"[dim]AI Model: {current_model_info['name']} ({current_model_info['provider']})[/dim]",
                border_style="green"
            ))

    def show_available_models(self):
        """Display available AI models"""
        self.ai_manager.display_available_models(self.console)

    def select_model(self) -> bool:
        """Interactive model selection"""
        models = self.ai_manager.get_available_models()

        if not models:
            self.console.print("[red]No models available![/red]")
            return False

        self.show_available_models()

        model_choices = list(models.keys())
        choice = Prompt.ask(
            "Select an AI model",
            choices=model_choices,
            default=self.ai_manager.current_model
        )

        if self.ai_manager.set_model(choice):
            model_info = self.ai_manager.get_current_model_info()
            self.console.print(f"[green]✅ Switched to: {model_info['description']} ({model_info['provider']})[/green]")
            return True

        return False

    def load_switches(self) -> List[NexusSwitch]:
        """Load switch configurations"""
        try:
            with open("config/switches.yaml", 'r') as f:
                config = yaml.safe_load(f)

            switches = []
            for switch_config in config['switches']:
                switches.append(NexusSwitch(**switch_config))

            return switches
        except Exception as e:
            self.console.print(f"[red]Error loading switches: {e}[/red]")
            self.console.print("[yellow]Please ensure config/switches.yaml exists and is properly formatted[/yellow]")
            return []

    def show_available_switches(self):
        """Display available switches in a nice table"""
        table = Table(title="Available Nexus Switches")
        table.add_column("Index", style="cyan", no_wrap=True)
        table.add_column("Hostname", style="green")
        table.add_column("IP Address", style="blue")
        table.add_column("Status", style="yellow")

        for i, switch in enumerate(self.switches):
            # Quick connectivity test
            client = NexusClient(switch)
            status = "🟢 Online" if client.connect_ssh() else "🔴 Offline"
            client.close()

            table.add_row(
                str(i + 1),
                switch.hostname,
                switch.ip,
                status
            )

        self.console.print(table)

    def select_switch(self) -> Optional[NexusSwitch]:
        """Interactive switch selection"""
        self.show_available_switches()

        if not self.switches:
            self.console.print("[red]No switches configured![/red]")
            return None

        while True:
            try:
                choice = Prompt.ask(
                    "Select a switch",
                    choices=[str(i + 1) for i in range(len(self.switches))],
                    default="1"
                )

                selected_switch = self.switches[int(choice) - 1]
                self.console.print(f"[green]✅ Selected: {selected_switch.hostname} ({selected_switch.ip})[/green]")
                return selected_switch

            except (ValueError, IndexError):
                self.console.print("[red]Invalid selection. Please try again.[/red]")

    def validate_nexus_commands(self, commands: List[str]) -> List[str]:
        """Validate and correct common Nexus command syntax issues"""
        validated_commands = []

        # Common IOS to Nexus command translations with strict blocking
        ios_to_nexus = {
            "show bgp summary": "show bgp l2vpn evpn summary",
            "show bgp neighbors": "show bgp l2vpn evpn neighbors",
            "show ip bgp summary": "show bgp ipv4 unicast summary",
            "show ip bgp neighbors": "show bgp ipv4 unicast neighbors",
            "show processes cpu": "show system resources",
            "show processes": "show system resources",
            "show interface e1/": "show interface ethernet1/",
            "show int e1/": "show interface ethernet1/",
        }

        for command in commands:
            validated_command = command
            command_blocked = False

            # Strict blocking of IOS commands
            if command.lower().strip() in ["show bgp summary", "show bgp neighbors", "show ip bgp"]:
                if "show bgp neighbors" in command.lower():
                    validated_command = "show bgp l2vpn evpn neighbors"
                elif "show bgp summary" in command.lower():
                    validated_command = "show bgp l2vpn evpn summary"
                elif "show ip bgp" in command.lower():
                    validated_command = "show bgp ipv4 unicast summary"

                self.console.print(f"[red]🚫 Blocked IOS command: '{command}'[/red]")
                self.console.print(f"[green]✅ Using Nexus command: '{validated_command}'[/green]")
                command_blocked = True

            # Check for common IOS syntax and correct it
            if not command_blocked:
                for ios_cmd, nexus_cmd in ios_to_nexus.items():
                    if ios_cmd in command.lower():
                        validated_command = command.lower().replace(ios_cmd, nexus_cmd)
                        self.console.print(f"[yellow]🔧 Corrected: '{command}' → '{validated_command}'[/yellow]")
                        break

            # Check for other common issues
            if "show interface e1/" in validated_command:
                validated_command = validated_command.replace("show interface e1/", "show interface ethernet1/")
                self.console.print(f"[yellow]🔧 Corrected interface syntax: '{command}' → '{validated_command}'[/yellow]")

            validated_commands.append(validated_command)

        return validated_commands

    def translate_natural_language_to_commands(self, natural_input: str) -> List[str]:
        """Convert natural language to Nexus CLI commands using AI"""

        system_prompt = '''You are an expert Cisco Nexus network engineer. Convert natural language requests into appropriate Nexus CLI commands.

CRITICAL: Use ONLY NEXUS-SPECIFIC syntax. NEVER use IOS commands!
IMPORTANT: Return ONLY the CLI commands, one per line. Do NOT use markdown code blocks (```). Do NOT include explanatory text.

IMPORTANT: For VLAN-related queries about interface assignments, use these approaches:
- To find which VLAN an interface is assigned to: Use "show vlan brief" (shows all VLANs and their port assignments)
- To see interface configuration: Use "show running-config interface ethernetX/X"
- To see interface status: Use "show interface ethernetX/X"

• If configuration is needed, include commands such as:
  - configure terminal
  - snmp-server community public ro
  - feature <feature-name>
  - interface ethernetX/X
  - vlan <id>
  - router bgp <asn>
  - address-family l2vpn evpn
  - no shutdown

📌 Examples:
Input: "Which VLAN is interface e1/7 assigned to?"
Output:
show vlan brief

Input: "What VLAN is ethernet1/5 in?"
Output:
show vlan brief

Input: "Show me the VLAN assignment for interface e1/10"
Output:
show vlan brief

Input: "Configure SNMP v2 with community public"
Output:
configure terminal
snmp-server community public ro

Input: "Enable BGP on AS 65001"
Output:
configure terminal
feature bgp
router bgp 65001

Input: "Create VLAN 100 named USERS"
Output:
configure terminal
vlan 100
  name USERS

Input: "Configure interface e1/7 as access port and add it to vlan 100"
Output:
configure terminal
interface ethernet1/7
description "Access Port for VLAN 100"
switchport
switchport mode access
switchport access vlan 100
no shutdown

Input: "Enable interface Ethernet1/1"
Output:
configure terminal
interface ethernet1/1
no shutdown

Input: "Enable interface range Ethernet1/1-7"
Output:
configure terminal
interface ethernet1/1-7
no shutdown

Input: "Disable interface range Ethernet1/1-7"
Output:
configure terminal
interface ethernet1/1-7
shutdown

Input: "Default interface Ethernet1/1"
Output:
configure terminal
default interface ethernet1/1

FORBIDDEN IOS Commands (DO NOT USE):
- show bgp summary (IOS) ❌
- show bgp neighbors (IOS) ❌
- show ip bgp (IOS) ❌
- show processes (IOS) ❌
- show vlan interface (IOS style) ❌

REQUIRED NEXUS Commands:

BGP Commands:
- show bgp l2vpn evpn summary (for EVPN neighbors)
- show bgp l2vpn evpn neighbors (for EVPN neighbor details)
- show bgp ipv4 unicast summary (for IPv4 BGP)
- show bgp ipv4 unicast neighbors (for IPv4 BGP neighbors)
- show bgp ipv6 unicast summary (for IPv6 BGP)
- show bgp process (BGP process information)
- show bgp sessions (all BGP sessions)

Interface Commands:
- show running-config interface ethernet1/1
- show interface
- show interface brief
- show ip interface brief
- show interface ethernet1/1 (NOT e1/1)
- show interface status
- show interface status up
- show interface counters errors

System Commands:
- show system resources (NOT show processes)
- show environment
- show version
- show module

VLAN Commands:
- show vlan brief (shows all VLANs and their port assignments)
- show vlan id <vlan-id>
- show running-config vlan
- show running-config interface ethernet1/X (to see interface VLAN config)

NEVER generate these IOS commands:
- show bgp summary
- show bgp neighbors
- show ip bgp
- show processes cpu
- show vlan interface

REMEMBER: Return ONLY CLI commands, no markdown, no explanations, no code blocks.'''

        user_prompt = f"Convert this natural language request to Nexus CLI commands:\n\n{natural_input}"

        try:
            llm = self.ai_manager.get_current_model()
            if not llm:
                self.console.print("[red]No AI model available![/red]")
                return []

            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            commands_text = response.content.strip()

            # Check if AI is asking for clarification
            if commands_text.startswith("CLARIFY:"):
                self.console.print(f"[yellow]🤔 {commands_text[9:]}[/yellow]")
                return []

            # Parse commands (one per line)
            commands = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip() and not cmd.strip().startswith('```')]

            # Additional validation to catch any IOS commands that slipped through
            commands = self.strict_nexus_validation(commands)

            # Validate and correct Nexus syntax
            validated_commands = self.validate_nexus_commands(commands)

            return validated_commands

        except Exception as e:
            self.console.print(f"[red]Error translating command: {e}[/red]")
            return []

    def strict_nexus_validation(self, commands: List[str]) -> List[str]:
        """Strict validation to prevent any IOS commands"""
        validated_commands = []

        # Forbidden IOS patterns
        forbidden_patterns = [
            "show bgp summary",
            "show bgp neighbors",
            "show ip bgp",
            "show processes cpu",
            "show processes"
        ]

        # Required Nexus replacements
        nexus_replacements = {
            "show bgp summary": "show bgp l2vpn evpn summary",
            "show bgp neighbors": "show bgp l2vpn evpn neighbors",
            "show ip bgp summary": "show bgp ipv4 unicast summary",
            "show ip bgp neighbors": "show bgp ipv4 unicast neighbors",
            "show processes cpu": "show system resources",
            "show processes": "show system resources"
        }

        for command in commands:
            command_lower = command.lower().strip()

            # Check if this is a forbidden IOS command
            forbidden_found = False
            for forbidden in forbidden_patterns:
                if forbidden in command_lower:
                    if forbidden in nexus_replacements:
                        corrected = nexus_replacements[forbidden]
                        self.console.print(f"[red]🚫 Blocked IOS command: '{command}'[/red]")
                        self.console.print(f"[green]✅ Using Nexus equivalent: '{corrected}'[/green]")
                        validated_commands.append(corrected)
                        forbidden_found = True
                        break

            if not forbidden_found:
                validated_commands.append(command)

        return validated_commands

    def suggest_command_correction(self, failed_command: str, error_output: str) -> Optional[str]:
        """Suggest command corrections based on common Nexus syntax issues"""

        # Common corrections
        corrections = {
            "show bgp neighbors": "show bgp l2vpn evpn neighbors",
            "show bgp summary": "show bgp l2vpn evpn summary",
            "show ip bgp": "show bgp l2vpn evpn",
            "show processes cpu": "show system resources",
            "show processes": "show system resources"
        }

        # Direct lookup
        if failed_command in corrections:
            return corrections[failed_command]

        # Partial matching
        for wrong_cmd, correct_cmd in corrections.items():
            if wrong_cmd in failed_command:
                return failed_command.replace(wrong_cmd, correct_cmd)

        # BGP-related corrections
        if "bgp" in failed_command.lower():
            if "neighbor" in failed_command.lower():
                return "show bgp l2vpn evpn neighbors"
            elif "summary" in failed_command.lower():
                return "show bgp l2vpn evpn summary"
            else:
                return "show bgp l2vpn evpn summary"

        return None

    def group_interface_commands(self, commands: List[str]) -> Dict[str, List[str]]:
        """Group interface-related commands into blocks for proper execution"""
        interface_blocks = {}
        current_interface = None
        current_block = []
        individual_commands = []

        for command in commands:
            command_lower = command.lower().strip()

            # Handle show commands individually - they don't need grouping
            if command_lower.startswith('show ') or command_lower.startswith('display '):
                individual_commands.append(command)
                continue

            # Check if this is an interface configuration command
            if command_lower.startswith('interface '):
                # Save previous block if exists
                if current_interface and current_block:
                    interface_blocks[current_interface] = current_block.copy()

                # Start new interface block
                current_interface = command.split()[1] if len(command.split()) > 1 else "unknown"
                current_block = ['configure terminal', command]

            elif current_interface and any(keyword in command_lower for keyword in
                                         ['description', 'switchport', 'no shutdown', 'shutdown',
                                          'ip address', 'spanning-tree', 'mtu', 'speed', 'duplex']):
                # Add to current interface block
                current_block.append(command)

            elif command_lower == 'configure terminal':
                # Skip standalone configure terminal commands
                continue

            else:
                # Save current interface block if exists
                if current_interface and current_block:
                    interface_blocks[current_interface] = current_block.copy()
                    current_interface = None
                    current_block = []

                # Handle as individual command
                individual_commands.append(command)

        # Save final interface block if exists
        if current_interface and current_block:
            interface_blocks[current_interface] = current_block

        # Add individual commands as separate blocks
        for i, cmd in enumerate(individual_commands):
            interface_blocks[f"individual_{i}"] = [cmd]

        return interface_blocks

    def is_command_failure(self, output: str) -> bool:
        """Check if command output indicates a failure"""
        failure_indicators = [
            "Invalid command",
            "% Invalid",
            "Syntax error",
            "Command not found",
            "% Ambiguous command",
            "Permission denied",
            "Authentication failed"
        ]

        return any(indicator in output for indicator in failure_indicators)

    def execute_commands_on_switch(self, commands: List[str], switch: NexusSwitch) -> Dict:
        """Execute commands on the selected switch with proper context handling"""
        client = NexusClient(switch)

        if not client.connect_ssh():
            return {"error": f"Failed to connect to {switch.hostname}"}

        results = {}

        try:
            # Check if we have interface configuration commands that should be grouped
            interface_blocks = self.group_interface_commands(commands)

            if interface_blocks:
                # Execute interface configurations as blocks
                for block_name, block_commands in interface_blocks.items():
                    if block_name.startswith('individual_'):
                        # Execute individual commands normally
                        command = block_commands[0]
                        self.console.print(f"[cyan]Executing:[/cyan] [bold]{command}[/bold]")

                        with self.console.status(f"Running '{command}'...", spinner="dots"):
                            output = client.execute_command(command)

                            # Check for actual command failures (not just any error text)
                            if self.is_command_failure(output):
                                self.console.print(f"[red]❌ Command failed: {command}[/red]")

                                # Try to suggest a correction
                                suggested_command = self.suggest_command_correction(command, output)
                                if suggested_command:
                                    self.console.print(f"[yellow]💡 Suggested correction: {suggested_command}[/yellow]")

                                    # In batch mode with show_raw, don't ask for confirmation
                                    if self.show_raw:
                                        corrected_output = client.execute_command(suggested_command)
                                        results[suggested_command] = corrected_output
                                        self.console.print(f"[green]✅ Corrected command executed successfully[/green]")
                                        continue
                                    elif Confirm.ask("Try the suggested command?", default=True):
                                        corrected_output = client.execute_command(suggested_command)
                                        results[suggested_command] = corrected_output
                                        self.console.print(f"[green]✅ Corrected command executed successfully[/green]")
                                        continue
                            else:
                                self.console.print(f"[green]✅ Command executed successfully[/green]")

                            results[command] = output
                    else:
                        # Execute interface configuration as a block
                        self.console.print(f"[cyan]Executing interface block:[/cyan] [bold]{block_name}[/bold]")

                        with self.console.status(f"Configuring {block_name}...", spinner="dots"):
                            combined_output = client.execute_command_block(block_commands)

                        results[f"Interface Config: {block_name}"] = combined_output

                    # Store in context (use last command/output)
                    if block_name.startswith('individual_'):
                        self.context["last_command"] = block_commands[0]
                        self.context["last_output"] = results.get(block_commands[0], "")
                    else:
                        self.context["last_command"] = f"Interface Config: {block_name}"
                        self.context["last_output"] = results.get(f"Interface Config: {block_name}", "")

                    # Add to history
                    self.command_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "switch": switch.hostname,
                        "command": self.context["last_command"],
                        "output": self.context["last_output"][:500] + "..." if len(self.context["last_output"]) > 500 else self.context["last_output"]
                    })
            else:
                # Execute commands individually for non-interface configs
                for command in commands:
                    self.console.print(f"[cyan]Executing:[/cyan] [bold]{command}[/bold]")

                    with self.console.status(f"Running '{command}'...", spinner="dots"):
                        output = client.execute_command(command)

                        # Check for actual command failures (not just any error text)
                        if self.is_command_failure(output):
                            self.console.print(f"[red]❌ Command failed: {command}[/red]")

                            # Try to suggest a correction
                            suggested_command = self.suggest_command_correction(command, output)
                            if suggested_command:
                                self.console.print(f"[yellow]💡 Suggested correction: {suggested_command}[/yellow]")

                                # In batch mode with show_raw, don't ask for confirmation
                                if self.show_raw:
                                    corrected_output = client.execute_command(suggested_command)
                                    results[suggested_command] = corrected_output
                                    self.console.print(f"[green]✅ Corrected command executed successfully[/green]")
                                    continue
                                elif Confirm.ask("Try the suggested command?", default=True):
                                    corrected_output = client.execute_command(suggested_command)
                                    results[suggested_command] = corrected_output
                                    self.console.print(f"[green]✅ Corrected command executed successfully[/green]")
                                    continue
                        else:
                            self.console.print(f"[green]✅ Command executed successfully[/green]")

                        results[command] = output

                    # Store in context
                    self.context["last_command"] = command
                    self.context["last_output"] = output

                    # Add to history
                    self.command_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "switch": switch.hostname,
                        "command": command,
                        "output": output[:500] + "..." if len(output) > 500 else output
                    })

        finally:
            client.close()

        return results

    def analyze_command_output(self, natural_input: str, commands: List[str], results: Dict, switch: NexusSwitch) -> str:
        """Use AI to analyze command output and provide insights"""

        def parse_vlan_output(raw_output: str) -> List[Dict[str, str]]:
            """Parses the `show vlan` CLI output into a structured list"""
            vlan_data = []
            collecting = False

            for line in raw_output.splitlines():
                if re.match(r"^\s*----", line):
                    collecting = True
                    continue
                if not collecting or not line.strip():
                    continue

                # Match VLAN entry: ID, Name, Status, Ports (first line)
                match = re.match(r"^\s*(\d+)\s+(\S+)\s+(active|suspended|act/lshut|inactive)?\s*(.*)", line)
                if match:
                    vlan_id, name, status, ports = match.groups()
                    vlan_data.append({
                        "vlan_id": vlan_id,
                        "name": name,
                        "status": status,
                        "ports": ports.strip()
                    })
                elif vlan_data and line.strip().startswith("Eth"):
                    vlan_data[-1]["ports"] += ", " + line.strip()

            return vlan_data

        def find_interface_vlan(vlan_data: List[Dict], interface_name: str) -> Optional[Dict]:
            """Find which VLAN contains the specified interface"""
            # Normalize interface name (e1/7 -> ethernet1/7, Eth1/7 -> ethernet1/7)
            normalized_interface = interface_name.lower()
            if normalized_interface.startswith('e1/'):
                normalized_interface = normalized_interface.replace('e1/', 'ethernet1/')
            elif normalized_interface.startswith('eth1/'):
                normalized_interface = normalized_interface.replace('eth1/', 'ethernet1/')

            for vlan in vlan_data:
                ports = vlan.get('ports', '').lower()
                if normalized_interface in ports or interface_name.lower() in ports:
                    return vlan
            return None

        # Prepare outputs for analysis
        analysis_data = {}
        vlan_summary_lines = []
        interface_vlan_assignment = None

        for cmd, output in results.items():
            limited_output = output[:2000] + "..." if len(output) > 2000 else output
            analysis_data[cmd] = limited_output

            # Parse and extract VLAN summary if applicable
            if "show vlan" in cmd.lower():
                vlans = parse_vlan_output(output)
                vlan_summary_lines = [
                    f"VLAN {v['vlan_id']} ({v['name']}) - {v['status']} - Ports: {v['ports'] or 'None'}"
                    for v in vlans
                ]

                # If this is a query about interface VLAN assignment, find it specifically
                if any(keyword in natural_input.lower() for keyword in ['which vlan', 'what vlan', 'vlan assignment', 'assigned to']):
                    # Extract interface name from the query
                    interface_match = re.search(r'e\d+/\d+|ethernet\d+/\d+', natural_input.lower())
                    if interface_match:
                        interface_name = interface_match.group()
                        interface_vlan_assignment = find_interface_vlan(vlans, interface_name)

        vlan_summary_text = ""
        if vlan_summary_lines:
            vlan_summary_text = "Detected VLANs:\n" + "\n".join(vlan_summary_lines)

        # Create a specific analysis prompt based on the query type
        if interface_vlan_assignment:
            specific_finding = f"\nSPECIFIC FINDING: Interface {interface_match.group()} is assigned to VLAN {interface_vlan_assignment['vlan_id']} ({interface_vlan_assignment['name']}) - Status: {interface_vlan_assignment['status']}"
        elif any(keyword in natural_input.lower() for keyword in ['which vlan', 'what vlan', 'vlan assignment', 'assigned to']):
            interface_match = re.search(r'e\d+/\d+|ethernet\d+/\d+', natural_input.lower())
            if interface_match:
                specific_finding = f"\nSPECIFIC FINDING: Interface {interface_match.group()} was NOT found in any VLAN assignment. This interface may not be configured as an access port or may be a trunk port."
            else:
                specific_finding = ""
        else:
            specific_finding = ""

        analysis_prompt = f"""Analyze the output from these Nexus CLI commands and provide insights based on the user's request.

User Request: "{natural_input}"
Switch: {switch.hostname} ({switch.ip})
Commands Executed: {', '.join(commands)}

Command Outputs:
{json.dumps(analysis_data, indent=2)}

{vlan_summary_text}
{specific_finding}

Provide a comprehensive analysis including:
1. Direct answer to the user's question
2. Key findings and observations
3. Any issues or concerns identified
4. Recommended next steps or actions
5. Additional commands that might be helpful

Format the response clearly with emojis and sections for better readability.
Keep the analysis practical and actionable for network operations.
Focus on what matters most for network health and troubleshooting.

If there are any problems found, prioritize those in your analysis.
If everything looks good, highlight the positive status clearly.

IMPORTANT: If this was a query about VLAN assignment for a specific interface, make sure to directly answer which VLAN the interface is assigned to based on the show vlan brief output.
"""

        try:
            llm = self.ai_manager.get_current_model()
            if not llm:
                return "Analysis failed: No AI model available"

            response = llm.invoke([HumanMessage(content=analysis_prompt)])
            return response.content

        except Exception as e:
            return f"Analysis failed: {e}\n\nRaw command outputs:\n" + \
                   "\n".join([f"{cmd}:\n{output}\n" for cmd, output in results.items()])

    def display_results(self, natural_input: str, commands: List[str], results: Dict, analysis: str, switch: NexusSwitch):
        """Display results in a formatted way"""

        # Command execution summary
        self.console.print(Panel.fit(
            f"[bold green]✅ Executed {len(commands)} command(s) on {switch.hostname}[/bold green]",
            border_style="green"
        ))

        # Show raw command outputs based on show_raw flag or user preference
        if self.show_raw:
            # In batch mode with show_raw=true, automatically show raw outputs
            show_raw_outputs = True
        else:
            # In interactive mode or batch mode with show_raw=false, ask user
            show_raw_outputs = Confirm.ask("Show raw command outputs?", default=False)

        if show_raw_outputs:
            for command, output in results.items():
                self.console.print(f"\n[bold blue]Command:[/bold blue] {command}")

                # Syntax highlight if it looks like structured data
                if any(keyword in output.lower() for keyword in ['interface', 'bgp', 'route', 'neighbor']):
                    syntax = Syntax(output, "text", theme="monokai", line_numbers=False)
                    self.console.print(Panel(syntax, title="Output", border_style="blue"))
                else:
                    self.console.print(Panel(output, title="Output", border_style="blue"))

        # AI Analysis - Main focus
        current_model_info = self.ai_manager.get_current_model_info()
        self.console.print(Panel(
            analysis,
            title=f"🤖 AI Analysis ({current_model_info['provider']}) for: '{natural_input}'",
            border_style="cyan",
            expand=False
        ))

    def show_command_history(self):
        """Display recent command history"""
        if not self.command_history:
            self.console.print("[yellow]No command history available[/yellow]")
            return

        table = Table(title="Recent Command History")
        table.add_column("Time", style="cyan")
        table.add_column("Switch", style="green")
        table.add_column("Command", style="blue")
        table.add_column("Status", style="yellow")

        for entry in self.command_history[-10:]:  # Last 10 commands
            timestamp = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
            status = "✅ Success" if not entry["output"].startswith("Error") else "❌ Error"
            table.add_row(timestamp, entry["switch"], entry["command"], status)

        self.console.print(table)

    def get_suggested_commands(self, context: str = "") -> List[str]:
        """Get AI-suggested commands based on context"""
        suggestion_prompt = f"""Based on the current context of a Nexus switch troubleshooting session, suggest 5 useful natural language commands that a network engineer might want to run next.

Context: {context or "Starting troubleshooting session"}

Return suggestions as a simple list, one per line. Focus on common network troubleshooting tasks.

Examples:
- Check interface status
- Show BGP neighbors
- Get system health
- Look for errors in logs
- Check EVPN status"""

        try:
            llm = self.ai_manager.get_current_model()
            if not llm:
                return [
                    "Check interface status",
                    "Show system health",
                    "Get BGP status",
                    "Look for recent errors",
                    "Check EVPN neighbors"
                ]

            response = llm.invoke([HumanMessage(content=suggestion_prompt)])
            suggestions = [line.strip().lstrip('- ') for line in response.content.split('\n') if line.strip()]
            return suggestions[:5]
        except:
            return [
                "Check interface status",
                "Show system health",
                "Get BGP status",
                "Look for recent errors",
                "Check EVPN neighbors"
            ]

    def show_suggestions(self):
        """Show AI-generated command suggestions"""
        context = f"Last command: {self.context.get('last_command', 'None')}"
        suggestions = self.get_suggested_commands(context)

        self.console.print("\n[bold yellow]💡 Suggested commands:[/bold yellow]")
        for i, suggestion in enumerate(suggestions, 1):
            self.console.print(f"  [dim]{i}.[/dim] {suggestion}")
        print()

    def show_help(self):
        """Display help information"""
        current_model_info = self.ai_manager.get_current_model_info()

        help_text = f'''🌐 Interactive Nexus CLI Tool - Natural Language Interface

Current AI Model: {current_model_info['description']} ({current_model_info['provider']})

How to use:
• Type natural language commands like:
  - "check interface status"
  - "show me BGP neighbors"
  - "what's the CPU usage"
  - "troubleshoot EVPN"
  - "find interfaces that are down"
  - "check system health"
  - "show me routing table"
  - "what errors are in the logs"

Special commands:
• help - Show this help
• models - Show/change AI models
• switches - Show available switches
• history - Show command history
• switch - Change current switch
• suggestions - Get AI-suggested commands
• clear - Clear screen
• exit/quit - Exit the tool

Natural Language Examples:
• Troubleshooting:
  - "What's wrong with this switch?"
  - "Check for interface errors"
  - "Show me recent error logs"
  - "Troubleshoot BGP issues"

• Status Checks:
  - "Show system health"
  - "Check all interface status"
  - "Get BGP neighbor status"
  - "Show VPC configuration"

• Performance:
  - "What's the CPU and memory usage?"
  - "show interface"
  - "Check system resources"

• Configuration:
  - "Show running config for BGP"
  - "Display VLAN configuration"
  - "What's the current spanning tree status"

AI Models Supported:
• OpenAI GPT-4o and GPT-4o-mini
• Anthropic Claude Sonnet 4 (latest), Claude 3.5 Sonnet and Claude 3 Haiku
• Ollama local models (llama3.3)

Batch Mode:
• Run single commands: python nexus_cli.py --batch "check interface status"
• Specify switch: python nexus_cli.py --batch "show BGP" --switch DC1_SPINE_01
• Choose model: python nexus_cli.py --batch "system health" --model claude-sonnet-4-20250514
• Save output: python nexus_cli.py --batch "system health" --output report.txt
• Auto show raw output: python nexus_cli.py --batch "system health" --show-raw true
• List models: python nexus_cli.py --list-models

Environment Variables:
• OPENAI_API_KEY - For OpenAI models
• ANTHROPIC_API_KEY - For Claude models

Tips:
• The AI understands context - you can ask follow-up questions
• Commands are confirmed before execution for safety
• Use 'suggestions' to get ideas for what to check next
• All commands and outputs are logged for your session
• Switch between AI models using 'models' command
• Use --show-raw true in batch mode to automatically display raw outputs
        '''

        self.console.print(Panel(help_text, border_style="green"))

    def is_configuration_command(self, commands: List[str]) -> bool:
        """Check if any command is a configuration command"""
        for command in commands:
            command_lower = command.lower().strip()

            # Skip all show commands - they are read-only
            if command_lower.startswith('show '):
                continue

            # Skip display/monitoring commands
            if any(command_lower.startswith(prefix) for prefix in ['show', 'display', 'ping', 'traceroute', 'telnet', 'ssh']):
                continue

            # Check for actual configuration keywords
            config_keywords = [
                'configure terminal',
                'interface ethernet',  # More specific to avoid false positives
                'interface vlan',
                'interface loopback',
                'interface port-channel',
                'router bgp',
                'vlan ',
                'snmp-server',
                'feature ',
                'vpc ',
                'no shutdown',
                'shutdown',
                'description ',
                'ip address',
                'switchport',
                'neighbor ',
                'address-family',
                'route-map',
                'access-list',
                'ip route',
                'hostname',
                'username',
                'enable secret',
                'line vty',
                'copy running',
                'write memory',
                'default interface', # delete all the configuration under an interface
                'no ',  # Any 'no' command is typically configuration
            ]

            # Only flag as config if it matches keywords AND doesn't start with show
            if any(keyword in command_lower for keyword in config_keywords):
                return True

        return False

    def show_configuration_warning(self, commands: List[str]) -> bool:
        """Show warning for configuration commands and get confirmation"""
        # If show_raw is enabled (batch mode), automatically confirm configuration commands
        if self.show_raw:
            self.console.print("\n[bold yellow]⚠️  CONFIGURATION COMMANDS DETECTED - Auto-confirming in batch mode[/bold yellow]")
            for i, command in enumerate(commands, 1):
                if any(keyword in command.lower() for keyword in ['configure', 'interface', 'router', 'vlan', 'snmp-server']):
                    self.console.print(f"  [red]{i}. {command}[/red]")
                else:
                    self.console.print(f"  [dim]{i}. {command}[/dim]")
            return True

        self.console.print("\n[bold red]⚠️  CONFIGURATION COMMANDS DETECTED[/bold red]")
        self.console.print("[yellow]The following commands will modify the switch configuration:[/yellow]")

        for i, command in enumerate(commands, 1):
            if any(keyword in command.lower() for keyword in ['configure', 'interface', 'router', 'vlan', 'snmp-server']):
                self.console.print(f"  [red]{i}. {command}[/red]")
            else:
                self.console.print(f"  [dim]{i}. {command}[/dim]")

        self.console.print("\n[bold yellow]⚠️  This will change the switch configuration![/bold yellow]")
        self.console.print("[dim]• Changes will be saved to startup-config[/dim]")
        self.console.print("[dim]• Backup your configuration before proceeding[/dim]")
        self.console.print("[dim]• Test in a lab environment first[/dim]")

        return Confirm.ask("\n[bold red]Are you sure you want to proceed with configuration changes?[/bold red]", default=False)

    async def batch_mode(self, command: str, switch_name: Optional[str] = None, model_name: Optional[str] = None, output_file: Optional[str] = None):
        """Execute a single command in batch mode"""

        # Set model if specified
        if model_name:
            if not self.ai_manager.set_model(model_name):
                self.console.print(f"[red]❌ Model '{model_name}' not available[/red]")
                self.console.print("[yellow]Available models:[/yellow]")
                for model in self.ai_manager.get_available_models():
                    self.console.print(f"  • {model}")
                return

        # Select switch
        if switch_name:
            target_switch = None
            for switch in self.switches:
                if switch_name.lower() in [switch.hostname.lower(), switch.ip]:
                    target_switch = switch
                    break

            if not target_switch:
                self.console.print(f"[red]❌ Switch '{switch_name}' not found[/red]")
                return
        else:
            target_switch = self.switches[0] if self.switches else None

        if not target_switch:
            self.console.print("[red]❌ No switches available[/red]")
            return

        current_model_info = self.ai_manager.get_current_model_info()

        # Only show minimal output in batch mode
        if not self.show_raw:
            # Show the interactive panel in batch mode with show_raw=false
            self.console.print(Panel.fit(
                "[bold green]🌐 Interactive Nexus CLI Tool[/bold green]\n"
                "[cyan]Natural Language Command Interface for Cisco Nexus Switches[/cyan]\n"
                f"[dim]AI Model: {current_model_info['name']} ({current_model_info['provider']})[/dim]",
                border_style="green"
            ))

        self.console.print(f"[green]🎯 Executing on {target_switch.hostname}: '{command}'[/green]")
        self.console.print(f"[dim]Using: {current_model_info['description']} ({current_model_info['provider']})[/dim]")

        # Process command
        commands = self.translate_natural_language_to_commands(command)
        if not commands:
            return

        # Check if any commands are configuration commands
        if self.is_configuration_command(commands):
            if not self.show_configuration_warning(commands):
                self.console.print("[yellow]Configuration changes cancelled.[/yellow]")
                return

        results = self.execute_commands_on_switch(commands, target_switch)
        if "error" in results:
            self.console.print(f"[red]❌ {results['error']}[/red]")
            return

        analysis = self.analyze_command_output(command, commands, results, target_switch)

        # Display results
        self.display_results(command, commands, results, analysis, target_switch)

        # Save to file if requested
        if output_file:
            report = self.generate_report(command, commands, results, analysis, target_switch)
            with open(output_file, 'w') as f:
                f.write(report)
            self.console.print(f"[green]💾 Report saved to {output_file}[/green]")

    def generate_report(self, natural_input: str, commands: List[str], results: Dict, analysis: str, switch: NexusSwitch) -> str:
        """Generate a text report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_model_info = self.ai_manager.get_current_model_info()

        report = f"""# Nexus CLI Analysis Report
**Generated:** {timestamp}
**Switch:** {switch.hostname} ({switch.ip})
**User Request:** {natural_input}
**AI Model:** {current_model_info['description']} ({current_model_info['provider']})

## Commands Executed
{chr(10).join([f"- {cmd}" for cmd in commands])}

## AI Analysis
{analysis}

## Raw Command Outputs
"""

        for command, output in results.items():
            report += f"""
### {command}
```
{output}
```
"""

        report += """
---
*Generated by Interactive Nexus CLI Tool with Multi-AI Support*
"""

        return report

    async def interactive_loop(self):
        """Main interactive loop"""

        # Select initial switch
        self.current_switch = self.select_switch()
        if not self.current_switch:
            return

        current_model_info = self.ai_manager.get_current_model_info()
        self.console.print(f"\n[green]🚀 Ready! Connected to {self.current_switch.hostname}[/green]")
        self.console.print(f"[blue]🤖 AI Model: {current_model_info['description']} ({current_model_info['provider']})[/blue]")
        self.console.print("[dim]Type 'help' for usage information or start with natural language commands[/dim]")

        # Show initial suggestions
        self.show_suggestions()

        while True:
            try:
                # Get user input
                user_input = Prompt.ask(
                    f"[bold blue]{self.current_switch.hostname}>[/bold blue]",
                    default=""
                ).strip()

                if not user_input:
                    continue

                # Handle special commands
                if user_input.lower() in ['exit', 'quit', 'q']:
                    self.console.print("[green]👋 Goodbye![/green]")
                    break
                elif user_input.lower() == 'help':
                    self.show_help()
                    continue
                elif user_input.lower() in ['models', 'model']:
                    self.select_model()
                    continue
                elif user_input.lower() == 'switches':
                    self.show_available_switches()
                    continue
                elif user_input.lower() == 'switch':
                    new_switch = self.select_switch()
                    if new_switch:
                        self.current_switch = new_switch
                    continue
                elif user_input.lower() == 'history':
                    self.show_command_history()
                    continue
                elif user_input.lower() in ['suggestions', 'suggest', 'ideas']:
                    self.show_suggestions()
                    continue
                elif user_input.lower() == 'clear':
                    os.system('clear' if os.name == 'posix' else 'cls')
                    continue

                # Process natural language command
                current_model_info = self.ai_manager.get_current_model_info()
                self.console.print(f"[dim]🧠 Translating with {current_model_info['provider']}: '{user_input}'...[/dim]")

                # Translate to CLI commands
                commands = self.translate_natural_language_to_commands(user_input)

                if not commands:
                    continue

                self.console.print(f"[dim]📝 Generated commands: {', '.join(commands)}[/dim]")

                # Check if any commands are configuration commands
                if self.is_configuration_command(commands):
                    if not self.show_configuration_warning(commands):
                        self.console.print("[yellow]Configuration changes cancelled.[/yellow]")
                        continue

                # Confirm execution - skip in batch mode with show_raw
                if self.show_raw or Confirm.ask(f"Execute {len(commands)} command(s)?", default=True):
                    # Execute commands
                    results = self.execute_commands_on_switch(commands, self.current_switch)

                    if "error" in results:
                        self.console.print(f"[red]❌ {results['error']}[/red]")
                        continue

                    # Analyze results
                    self.console.print(f"[dim]🤖 Analyzing results with {current_model_info['provider']}...[/dim]")
                    analysis = self.analyze_command_output(user_input, commands, results, self.current_switch)

                    # Display results
                    self.display_results(user_input, commands, results, analysis, self.current_switch)

                    # Update context
                    self.context["session_notes"].append({
                        "request": user_input,
                        "commands": commands,
                        "key_findings": analysis[:200] + "..." if len(analysis) > 200 else analysis
                    })

                    # Show suggestions for next steps - skip in batch mode
                    if not self.show_raw and Confirm.ask("Show suggested next commands?", default=False):
                        self.show_suggestions()

                    print()  # Add spacing
                else:
                    continue

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'exit' to quit[/yellow]")
            except Exception as e:
                self.console.print(f"[red]❌ Error: {e}[/red]")

def list_available_models():
    """List all available AI models in a standalone function"""
    console = Console()

    # Create a temporary AI manager to check available models
    ai_manager = AIModelManager()

    if not ai_manager.get_available_models():
        console.print("[red]❌ No AI models available![/red]")
        console.print("[yellow]Please set one of the following API keys:[/yellow]")
        console.print("• OPENAI_API_KEY='your-openai-key'")
        console.print("• ANTHROPIC_API_KEY='your-anthropic-key'")
        console.print("• Or install Ollama with llama3.3 model")
        return

    # Display the models
    ai_manager.display_available_models(console)

    # Show usage examples
    console.print("\n[bold cyan]Usage Examples:[/bold cyan]")
    console.print("[dim]# Use a specific model in interactive mode[/dim]")
    console.print("python nexus_cli.py --model claude-sonnet-4-20250514")
    console.print("\n[dim]# Use a specific model in batch mode[/dim]")
    console.print('python nexus_cli.py --batch "check interface status" --model gpt-4o-mini')
    console.print("\n[dim]# Change model during interactive session[/dim]")
    console.print("Type 'models' at the prompt to switch models")

def install_requirements():
    """Install required packages if not present"""
    required_packages = [
        'rich',
        'langchain-openai',
        'langchain-anthropic',  # Added for Claude support
        'paramiko',
        'pyyaml',
        'python-dotenv',
        'langchain_ollama'
    ]

    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            os.system(f"pip install {package}")

def main():
    # Install requirements if needed
    try:
        from rich.console import Console
    except ImportError:
        install_requirements()
        from rich.console import Console

    parser = argparse.ArgumentParser(description="Interactive Nexus CLI Tool with Natural Language")
    parser.add_argument("--batch", help="Execute a single natural language command and exit")
    parser.add_argument("--switch", help="Specify switch by hostname or IP")
    parser.add_argument("--model", help="Specify AI model to use")
    parser.add_argument("--output", help="Save output to file")
    parser.add_argument("--list-models", action="store_true", help="List all available AI models and exit")
    parser.add_argument("--show-raw", help="Automatically show raw command outputs in batch mode (true/false)", default="false")

    args = parser.parse_args()

    # Convert show-raw argument to boolean
    show_raw = args.show_raw.lower() in ['true', '1', 'yes', 'on']

    # Handle --list-models flag
    if args.list_models:
        list_available_models()
        return

    # Initialize CLI with specified model and show_raw flag
    cli = NaturalLanguageNexusCLI(initial_model=args.model, show_raw=show_raw)

    if args.batch:
        # Batch mode - execute single command and exit
        asyncio.run(cli.batch_mode(args.batch, args.switch, args.model, args.output))
    else:
        # Interactive mode
        asyncio.run(cli.interactive_loop())


if __name__ == "__main__":
    main()
