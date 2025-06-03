# 🌐 Interactive Nexus CLI Tool

A Natural Language Processing (NLP) based CLI assistant for Cisco Nexus switches. It converts human-friendly network queries into Nexus-specific CLI commands, executes them over SSH, and provides intelligent AI analysis of the output using multiple AI providers including OpenAI GPT, Anthropic Claude, and local Ollama models.

## 📦 Prerequisites

- Python 3.8+
- Cisco Nexus switch access via SSH
- At least one AI API key (OpenAI, Anthropic, or local Ollama)
- Switch inventory configured in `config/switches.yaml`

## 🤖 AI Model Support

The tool supports multiple AI providers for maximum flexibility:

- **Anthropic Claude**: Claude Sonnet 4, Claude Opus 4, Claude 3.5 Sonnet, Claude 3 Haiku
- **OpenAI GPT**: GPT-4o, GPT-4o-mini
- **Ollama**: Local models (llama3.3)

## 📁 Project Structure

```
nexus-monitor/
│
├── nexus_cli.py                # Main CLI tool
├── config/
│   └── switches.yaml           # Nexus switch inventory
├── .env                        # AI API keys
└── README.md                   # This file
```

## ⚙️ Environment Setup

### 1. Install Dependencies

```bash
pip install rich langchain-openai langchain-anthropic langchain-ollama paramiko pyyaml python-dotenv
```

### 2. Configure AI API Keys

Create a `.env` file in the project root with at least one API key:

```env
# Anthropic Claude (Recommended - Latest Claude 4 models)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI GPT
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Ollama (runs locally - no API key needed, just install Ollama)
# Download from: https://ollama.ai/
# Run: ollama pull llama3.3
```

### 3. Configure Switches

Create `config/switches.yaml`:

```yaml
switches:
  - hostname: DC1_LEAF_01
    ip: 192.168.1.10
    username: admin
    password: password123
  - hostname: DC1_SPINE_01
    ip: 192.168.1.11
    username: admin
    password: password123
  - hostname: CORE_SWITCH_01
    ip: 10.1.1.100
    username: netadmin
    password: securepass
```

## 🚀 Usage Modes

### 1. 📋 List Available AI Models

View all available AI models with their status and capabilities:

```bash
python nexus_cli.py --list-models
```

**Example Output:**
```
┌─────────────────────────────────┬───────────┬─────────────────────────────────────────────┬─────────────┐
│ Model Name                      │ Provider  │ Description                                 │ Status      │
├─────────────────────────────────┼───────────┼─────────────────────────────────────────────┼─────────────┤
│ claude-sonnet-4-20250514        │ Anthropic │ Claude Sonnet 4 - Latest and most capable  │ 🟢 Default  │
│ claude-opus-4-20250514          │ Anthropic │ Claude Opus 4 - Latest and most capable    │ ⚪ Available │
│ claude-3-5-sonnet-20241022      │ Anthropic │ Claude 3.5 Sonnet - Excellent reasoning    │ ⚪ Available │
│ gpt-4o-mini                     │ OpenAI    │ GPT-4o Mini - Fast and efficient          │ ⚪ Available │
│ gpt-4o                          │ OpenAI    │ GPT-4o - Most capable OpenAI model         │ ⚪ Available │
│ llama3.3                        │ Ollama    │ Llama 3.3 - Local model                   │ ⚪ Available │
└─────────────────────────────────┴───────────┴─────────────────────────────────────────────┴─────────────┘
```

### 2. 🧑‍💻 Interactive Mode (Default)

Launch the tool in full interactive CLI mode - this is the primary way to use the tool:

```bash
# Use default AI model (auto-selected: Claude Sonnet 4 > Claude 3.5 > GPT-4o-mini)
python nexus_cli.py

# Use specific AI model
python nexus_cli.py --model claude-sonnet-4-20250514
python nexus_cli.py --model gpt-4o-mini
python nexus_cli.py --model llama3.3
```

**What happens:**
- Shows available switches with connectivity status
- Displays current AI model being used
- Prompts you to select a switch
- Enters interactive shell where you can use natural language
- Provides AI-powered command suggestions
- Maintains session context and command history

**Interactive Commands:**
```
> show interface status
> check bgp neighbors
> show vlan configuration
> troubleshoot system health
> what interfaces are down
> get cpu and memory usage
> check for errors in logs
> show me routing table
```

**Built-in Interactive Commands:**
- `help` - Show detailed usage guide
- `models` - View/change AI models during session
- `switches` - View all configured switches with status
- `switch` - Change current switch
- `history` - View recent command history
- `suggestions` - Get AI-powered next command ideas
- `clear` - Clear the screen
- `exit` or `quit` - Exit the tool

---

### 3. ⚙️ Batch Mode (Single Command Execution)

Execute a single natural language command and exit. Perfect for scripting, automation, or one-off checks.

#### Basic Batch Syntax

```bash
python nexus_cli.py --batch "<natural language command>"
```

#### Batch Mode Arguments

| Argument | Description | Required | Example | Default |
|----------|-------------|----------|---------|---------|
| `--batch` | Natural language command to execute | Yes | `"check interface status"` | - |
| `--switch` | Target switch by hostname or IP | No | `DC1_SPINE_01` or `192.168.1.11` | First switch |
| `--model` | Specify AI model to use | No | `claude-sonnet-4-20250514` | Auto-selected |
| `--output` | Save results to file | No | `report.txt` | Console only |
| `--show-raw` | Automatically show raw command outputs | No | `true` or `false` | `false` |
| `--list-models` | List available AI models and exit | No | - | - |

#### 🆕 New `--show-raw` Flag

The `--show-raw` flag controls whether raw command outputs are automatically displayed in batch mode:

- **`--show-raw true`**: Fully automated execution with no interactive prompts
- **`--show-raw false`**: Interactive prompts for raw output display (default behavior)

**Examples:**
```bash
# Fully automated - no user interaction required
python nexus_cli.py --batch "check interface status" --show-raw true

# Interactive - will ask if you want to see raw outputs
python nexus_cli.py --batch "check interface status" --show-raw false

# Default behavior (same as --show-raw false)
python nexus_cli.py --batch "check interface status"
```

---

## 📋 Detailed Usage Examples

### AI Model Selection Examples

```bash
# List all available AI models
python nexus_cli.py --list-models

# Start interactive mode with Claude Sonnet 4
python nexus_cli.py --model claude-sonnet-4-20250514

# Start interactive mode with GPT-4o-mini
python nexus_cli.py --model gpt-4o-mini

# Start interactive mode with local Ollama model
python nexus_cli.py --model llama3.3

# Use specific model in batch mode
python nexus_cli.py --batch "check system health" --model claude-3-5-sonnet-20241022
```

### Interactive Mode Examples

```bash
# Launch interactive mode (auto-selects best available model)
python nexus_cli.py

# Then use natural language in the interactive shell:
DC1_LEAF_01> show me all interface status
DC1_LEAF_01> check bgp neighbors for any issues
DC1_LEAF_01> what's the system health
DC1_LEAF_01> troubleshoot vlan configuration
DC1_LEAF_01> find interfaces with errors
DC1_LEAF_01> show cpu and memory usage
DC1_LEAF_01> models                    # Change AI model during session
DC1_LEAF_01> suggestions               # Get AI suggestions
DC1_LEAF_01> history                   # View command history
DC1_LEAF_01> help                      # Show help
```

### Batch Mode Examples

#### Basic Single Commands

```bash
# Check interface status on default switch with default AI model
python nexus_cli.py --batch "show interface status"

# Check system health with specific AI model
python nexus_cli.py --batch "check system health" --model claude-sonnet-4-20250514

# Look for BGP issues using GPT-4o
python nexus_cli.py --batch "troubleshoot bgp neighbors" --model gpt-4o

# Check VLAN configuration using local Ollama model
python nexus_cli.py --batch "show vlan config" --model llama3.3
```

#### 🆕 Using the `--show-raw` Flag

```bash
# Fully automated execution - perfect for scripts and automation
python nexus_cli.py --batch "check interface status" --show-raw true
python nexus_cli.py --batch "system health check" --show-raw true --output health.txt
python nexus_cli.py --batch "show BGP neighbors" --switch DC1_SPINE_01 --show-raw true

# Interactive mode - will prompt for raw output display
python nexus_cli.py --batch "check interface status" --show-raw false
python nexus_cli.py --batch "system health check" --show-raw false --output health.txt

# Default behavior (interactive prompts)
python nexus_cli.py --batch "check interface status"
python nexus_cli.py --batch "system health check" --output health.txt
```

#### Targeting Specific Switches with Automation

```bash
# Target switch by hostname with automated raw output
python nexus_cli.py --batch "show bgp summary" --switch DC1_SPINE_01 --model claude-sonnet-4-20250514 --show-raw true

# Target switch by IP address with automated output and file save
python nexus_cli.py --batch "check interface errors" --switch 192.168.1.11 --model gpt-4o-mini --show-raw true --output errors.txt

# Check system resources with full automation
python nexus_cli.py --batch "get cpu and memory usage" --switch DC1_SPINE_01 --model claude-3-5-sonnet-20241022 --show-raw true
```

#### Saving Output to Files with Full Automation

```bash
# Save basic report with automated raw output display
python nexus_cli.py --batch "system health check" --model claude-sonnet-4-20250514 --show-raw true --output health_report.txt

# Save with timestamp and automated execution
python nexus_cli.py --batch "show interface counters errors" --model gpt-4o-mini --show-raw true --output daily_$(date +%Y%m%d).txt

# Comprehensive switch analysis with full automation
python nexus_cli.py --batch "complete system analysis" --model claude-opus-4-20250514 --show-raw true --output full_analysis.md

# BGP troubleshooting report with local model and automation
python nexus_cli.py --batch "troubleshoot all bgp issues" --switch DC1_LEAF_01 --model llama3.3 --show-raw true --output bgp_report.txt
```

### 🔄 Automation & Scripting Examples with `--show-raw`

#### Daily Health Check Script (Fully Automated)

```bash
#!/bin/bash
# daily_health_check.sh - No user interaction required

SWITCHES=("DC1_LEAF_01" "DC1_SPINE_01" "CORE_SWITCH_01")
DATE=$(date +%Y%m%d)
AI_MODEL="claude-sonnet-4-20250514"

for switch in "${SWITCHES[@]}"; do
    echo "Checking $switch with $AI_MODEL..."
    # Fully automated - no prompts
    python nexus_cli.py --batch "complete health check" \
        --switch "$switch" \
        --model "$AI_MODEL" \
        --show-raw true \
        --output "health_${switch}_${DATE}.txt"
done
```

#### Continuous Monitoring Script

```bash
#!/bin/bash
# continuous_monitor.sh - Perfect for cron jobs

# Monitor interface status every 15 minutes (fully automated)
python nexus_cli.py --batch "check for interface errors" \
    --switch DC1_LEAF_01 \
    --model gpt-4o-mini \
    --show-raw true \
    --output "/var/log/interface_errors_$(date +%Y%m%d_%H%M).txt"

# Monitor BGP status every hour (fully automated)
python nexus_cli.py --batch "monitor bgp neighbor status" \
    --switch DC1_SPINE_01 \
    --model claude-3-5-sonnet-20241022 \
    --show-raw true \
    --output "/var/log/bgp_status_$(date +%Y%m%d_%H%M).txt"
```

#### Multi-Switch Automation Script

```bash
#!/bin/bash
# multi_switch_automation.sh

SWITCHES=("DC1_SPINE_01" "DC1_SPINE_02" "DC1_LEAF_01" "DC1_LEAF_02" "DC1_LEAF_03")
DATE=$(date +%Y%m%d_%H%M%S)
AI_MODEL="gpt-4o-mini"  # Fast model for automation

echo "Running automated network health checks..."
for switch in "${SWITCHES[@]}"; do
    echo "Processing $switch..."

    # All commands run without any user interaction
    python nexus_cli.py --batch "check interface status" \
        --switch "$switch" --model "$AI_MODEL" --show-raw true \
        --output "reports/interface_${switch}_${DATE}.txt" &

    python nexus_cli.py --batch "system health check" \
        --switch "$switch" --model "$AI_MODEL" --show-raw true \
        --output "reports/health_${switch}_${DATE}.txt" &

    python nexus_cli.py --batch "show BGP neighbors" \
        --switch "$switch" --model "$AI_MODEL" --show-raw true \
        --output "reports/bgp_${switch}_${DATE}.txt" &
done

wait  # Wait for all background jobs to complete
echo "✅ All automated checks completed!"
```

#### Cron Job Examples with Full Automation

```bash
# Add to crontab for fully automated monitoring

# Daily comprehensive health check (no user interaction)
0 6 * * * /path/to/nexus_cli.py --batch "daily system health check" --model claude-sonnet-4-20250514 --show-raw true --output /var/log/nexus_health_$(date +\%Y\%m\%d).txt

# Frequent interface monitoring (fully automated)
0 */4 * * * /path/to/nexus_cli.py --batch "check for interface errors" --switch DC1_LEAF_01 --model gpt-4o-mini --show-raw true --output /var/log/interface_errors.txt

# BGP monitoring with detailed analysis (no prompts)
0 * * * * /path/to/nexus_cli.py --batch "monitor bgp neighbor status" --switch DC1_SPINE_01 --model claude-3-5-sonnet-20241022 --show-raw true --output /var/log/bgp_status.txt

# Cost-free monitoring with local model (fully automated)
0 */2 * * * /path/to/nexus_cli.py --batch "basic system check" --model llama3.3 --show-raw true --output /var/log/basic_health.txt
```

---

## 🧠 Natural Language Command Examples

The tool understands a wide variety of natural language inputs and leverages different AI models for optimal analysis:

### Network Status & Health
```bash
"show me system health"
"check overall switch status"
"what's wrong with this switch"
"get system performance metrics"
"show cpu and memory usage"
"check for any critical alerts"
```

### Interface Management
```bash
"show all interface status"
"which interfaces are down"
"check for interface errors"
"show interface utilization"
"get ethernet port status"
"find interfaces with high error rates"
```

### BGP & Routing
```bash
"check bgp neighbors"
"show bgp status"
"troubleshoot bgp issues"
"get routing table"
"check evpn neighbors"
"show bgp summary"
```

### VLAN & Layer 2
```bash
"show vlan configuration"
"check spanning tree status"
"get vlan interface mapping"
"show vpc status"
"troubleshoot layer 2 issues"
```

### Troubleshooting
```bash
"troubleshoot network connectivity"
"check for recent errors"
"analyze system logs"
"find performance bottlenecks"
"diagnose switch problems"
```

### Configuration Commands
```bash
"enable snmp community public"
"configure bgp as 65001"
"create vlan 100 named users"
"enable interface ethernet1/1"
"set interface description"
```

---

## 🤖 AI Model Comparison & Recommendations

### **Claude Sonnet 4** (Recommended for Production)
- **Best for**: Complex troubleshooting, detailed analysis, critical infrastructure
- **Strengths**: Latest AI technology, excellent reasoning, comprehensive insights
- **Use cases**: Production health checks, incident analysis, complex configurations
- **Automation**: Excellent with `--show-raw true` for detailed automated reports

### **Claude 3.5 Sonnet**
- **Best for**: Advanced analysis, technical deep-dives
- **Strengths**: Strong reasoning capabilities, detailed explanations
- **Use cases**: Network optimization, performance tuning, architecture analysis
- **Automation**: Great for scheduled analysis with `--show-raw true`

### **GPT-4o-mini**
- **Best for**: Quick checks, frequent monitoring, cost-effective automation
- **Strengths**: Fast responses, efficient, good for routine tasks
- **Use cases**: Regular health checks, interface monitoring, basic troubleshooting
- **Automation**: Perfect for high-frequency automated monitoring

### **GPT-4o**
- **Best for**: Comprehensive analysis, complex problem solving
- **Strengths**: Advanced reasoning, detailed insights
- **Use cases**: Complex troubleshooting, architectural decisions
- **Automation**: Excellent for detailed automated analysis

### **Ollama (llama3.3)**
- **Best for**: Cost-free operation, privacy-sensitive environments
- **Strengths**: No API costs, runs locally, data privacy
- **Use cases**: Development environments, continuous monitoring, sensitive networks
- **Automation**: Perfect for cost-free 24/7 automated monitoring

---

## 🔐 Safety Features

### Configuration Command Protection
- Automatically detects configuration commands
- Shows detailed warning before execution
- Requires explicit confirmation (or auto-confirms with `--show-raw true`)
- Lists all commands that will modify configuration

### Command Validation
- Converts IOS commands to proper Nexus syntax
- Validates command syntax before execution
- Suggests corrections for failed commands
- Blocks known problematic command patterns

### AI Model Safety
- All AI providers use secure API connections
- Local Ollama models ensure data privacy
- No sensitive switch data stored in AI model training
- Option to use local models for air-gapped environments

### Automation Safety
- `--show-raw true` enables safe automation by bypassing interactive prompts
- Configuration commands still show warnings before execution
- Failed commands suggest corrections automatically
- All operations are logged for audit trails

---

## 📊 Output Formats

### Interactive Mode Output
- Real-time command execution status
- Formatted command outputs with syntax highlighting
- Comprehensive AI analysis with model-specific insights
- Suggested next steps and related commands
- AI model attribution in analysis headers

### Batch Mode Output with `--show-raw true`
- Console output with execution summary
- Automatic display of raw command outputs
- No interactive prompts for fully automated operation
- Optional file output in Markdown format
- Detailed analysis and recommendations with AI model info

### Batch Mode Output with `--show-raw false`
- Console output with execution summary
- Interactive prompts for raw command output display
- User control over output verbosity
- Optional file output in Markdown format
- Detailed analysis and recommendations with AI model info

### Report Structure (when using --output)
```markdown
# Nexus CLI Analysis Report
**Generated:** 2025-05-30 22:12:41
**Switch:** DC1_SPINE_01 (192.168.1.11)
**User Request:** check system health
**AI Model:** Claude Sonnet 4 - Latest and most capable Claude model (Anthropic)

## Commands Executed
- show system resources
- show environment
- show logging last 50

## AI Analysis
✅ System is running normally with optimal performance...
[Detailed analysis powered by Claude Sonnet 4]

## Raw Command Outputs
### show system resources
```
Load Average: 1 minute: 0.50, 5 minutes: 0.45, 15 minutes: 0.40
Memory usage: 2048000 kB total, 1536000 kB used, 512000 kB free
```

---

## 🛠️ Troubleshooting

### Common Issues

**No AI Models Available**
```bash
# Error: No AI models available!
# Solution: Set at least one API key in .env file
echo "ANTHROPIC_API_KEY=your-key-here" >> .env
# or
echo "OPENAI_API_KEY=your-key-here" >> .env
# or install Ollama locally
```

**Model Not Found**
```bash
# Error: Model 'claude-sonnet-4-20250514' not available
# Solution: Check available models
python nexus_cli.py --list-models
```

**Switch Connection Failed**
```bash
# Error: SSH connection failed
# Check: IP address, credentials, SSH access
python nexus_cli.py  # Will show switch status in interactive mode
```

**Command Not Found**
```bash
# If you get syntax errors, the tool will suggest corrections
# It automatically converts IOS commands to Nexus syntax
```

**Automation Issues**
```bash
# For fully automated scripts, always use --show-raw true
python nexus_cli.py --batch "your command" --show-raw true

# For scripts that need user interaction, use --show-raw false or omit the flag
python nexus_cli.py --batch "your command" --show-raw false
```

### Getting Help

- Use `python nexus_cli.py --list-models` to see available AI models
- Use `help` command in interactive mode for detailed guidance
- Use `models` command in interactive mode to switch AI models
- Check switch connectivity with `switches` command
- View recent activity with `history` command
- Get AI suggestions with `suggestions` command
- Use `--show-raw true` for fully automated operation
- Use `--show-raw false` for interactive control

---

## 🔄 Integration Examples

### CI/CD Pipeline Integration with Full Automation

```yaml
# .github/workflows/network-health.yml
name: Network Health Check
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run automated health check with Claude Sonnet 4
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python nexus_cli.py --batch "comprehensive health analysis" --model claude-sonnet-4-20250514 --show-raw true --output health_report.md
      - name: Upload report
        uses: actions/upload-artifact@v2
        with:
          name: health-report
          path: health_report.md
```

### Monitoring Integration with Model Fallback and Full Automation

```bash
# Nagios/Zabbix integration with model fallback and automation
AI_MODELS=("claude-sonnet-4-20250514" "gpt-4o-mini" "llama3.3")

for model in "${AI_MODELS[@]}"; do
    if python nexus_cli.py --batch "check critical system status" --switch $1 --model "$model" --show-raw true --output /tmp/switch_status.txt 2>/dev/null; then
        break
    fi
done

if grep -q "CRITICAL\|ERROR\|DOWN" /tmp/switch_status.txt; then
    exit 2  # Critical status
else
    exit 0  # OK status
fi
```

### Multi-Model Analysis Pipeline with Automation

```bash
#!/bin/bash
# multi_model_analysis.sh - Compare insights from different AI models (fully automated)

SWITCH="DC1_LEAF_01"
QUERY="troubleshoot network performance issues"

echo "Running automated analysis with multiple AI models..."

# Fast analysis with GPT-4o-mini (fully automated)
python nexus_cli.py --batch "$QUERY" --switch "$SWITCH" --model gpt-4o-mini --show-raw true --output analysis_gpt4mini.txt

# Detailed analysis with Claude Sonnet 4 (fully automated)
python nexus_cli.py --batch "$QUERY" --switch "$SWITCH" --model claude-sonnet-4-20250514 --show-raw true --output analysis_claude4.txt

# Local analysis with Ollama (fully automated)
python nexus_cli.py --batch "$QUERY" --switch "$SWITCH" --model llama3.3 --show-raw true --output analysis_ollama.txt

echo "✅ Automated analysis complete. Compare outputs in analysis_*.txt files"
```

---

## 💡 Tips & Best Practices

### AI Model Selection Strategy

1. **Production Environments**: Use Claude Sonnet 4 for critical analysis
2. **Development/Testing**: Use GPT-4o-mini for fast iteration
3. **Cost Optimization**: Use Ollama for continuous monitoring
4. **Privacy/Security**: Use local Ollama models for sensitive environments
5. **Hybrid Approach**: Use different models for different types of analysis

### Automation Best Practices

1. **Always use `--show-raw true`** for scripts and automation
2. **Use `--show-raw false`** when you want interactive control
3. **Implement model fallback** strategies for reliability
4. **Save outputs to files** for audit trails and analysis
5. **Use appropriate models** based on frequency and criticality

### Performance Optimization

- Use `--list-models` to check model availability before scripting
- Cache model responses for repeated queries
- Use faster models (GPT-4o-mini) for frequent monitoring with `--show-raw true`
- Use advanced models (Claude Sonnet 4) for complex troubleshooting
- Implement parallel execution for multiple switches

### Cost Management

- Monitor API usage across different providers
- Use local Ollama models for development and testing
- Implement model fallback strategies
- Use appropriate models for task complexity
- Use `--show-raw true` to eliminate manual overhead in automation

### Security & Safety

- Always test configuration commands in lab environments first
- Use `--show-raw true` for predictable automation behavior
- Implement proper access controls for switch credentials
- Use local Ollama models for sensitive network environments
- Maintain audit logs of all executed commands

---

*Built with ❤️ for network engineers automating Cisco Nexus environments with the power of multiple AI providers and intelligent automation*
