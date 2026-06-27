"""Session evidence extractor."""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime

from infra.core.models.evidence import (
    SkillEvidence, ToolCall,
    TokenUsage, ExecutionSummary, SessionContext, SessionEvidence
)
from infra.core.models.skill_pack import SkillPackConfig
from infra.core.config import ExtractorConfig, DEFAULT_CONFIG


def safe_get_nested(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO format timestamp string."""
    if not timestamp_str:
        return None
    try:
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(timestamp_str)
        except (ValueError, AttributeError):
            clean_str = re.sub(r'[+-]\d{2}:\d{2}$', '', timestamp_str)
            return datetime.strptime(clean_str, '%Y-%m-%dT%H:%M:%S.%f')
    except (ValueError, TypeError):
        return None


def calculate_duration_ms(start: datetime, end: datetime) -> int:
    """Calculate duration in milliseconds."""
    delta = end - start
    return int(delta.total_seconds() * 1000)


def truncate_string(s: Optional[str], max_length: int = 500) -> Optional[str]:
    """Truncate string to maximum length."""
    if s is None:
        return None
    if len(s) <= max_length:
        return s
    return s[:max_length - 3] + "..."


def extract_requirement_id(user_command: str) -> Optional[str]:
    """Extract requirement ID from user command (e.g., RAN-XXXXXXX)."""
    if not user_command:
        return None
    match = re.search(r'RAN-\d+', user_command)
    return match.group(0) if match else None


class SessionExtractor:
    """Extract evidence from session JSONL files."""
    
    def __init__(self, skill_pack: Optional[SkillPackConfig] = None,
                 config: Optional[ExtractorConfig] = None):
        self.skill_pack = skill_pack
        self.config = config or DEFAULT_CONFIG
        self.max_input_summary = self.config.max_input_summary
        self.max_error_output = self.config.max_error_output
    
    def extract_from_file(self, file_path: Path) -> SessionEvidence:
        """Extract evidence from a JSONL file."""
        messages = self._load_messages(file_path)
        if not messages:
            return SessionEvidence(
                session_id=file_path.stem,
                session_path=str(file_path)
            )
        
        session_id = self._get_session_id(messages, file_path)
        context = self._extract_context(messages)
        
        # Extract skill evidence
        skill_evidences = self._extract_skill_evidences(messages, session_id, context, file_path)
        
        # Handle sessions without Skill tool_use calls
        if not skill_evidences:
            skill_evidences = self._handle_no_skill_session(messages, session_id, context, file_path)
        
        # Calculate overall summary
        total_tool_calls = sum(s.execution_summary.total_tool_calls for s in skill_evidences)
        successful_calls = sum(s.execution_summary.successful_calls for s in skill_evidences)
        failed_calls = sum(s.execution_summary.failed_calls for s in skill_evidences)
        total_duration = sum(s.execution_summary.total_duration_ms for s in skill_evidences)
        total_input_tokens = sum(s.execution_summary.token_usage.input for s in skill_evidences)
        total_output_tokens = sum(s.execution_summary.token_usage.output for s in skill_evidences)
        
        # Determine session outcome
        session_outcome = self._determine_session_outcome(messages, skill_evidences)
        
        # Extract end time
        end_time = self._extract_end_time(messages)
        context.end_time = end_time
        
        return SessionEvidence(
            session_id=session_id,
            session_path=str(file_path),
            context=context,
            skills=skill_evidences,
            execution_summary=ExecutionSummary(
                total_tool_calls=total_tool_calls,
                successful_calls=successful_calls,
                failed_calls=failed_calls,
                total_duration_ms=total_duration,
                token_usage=TokenUsage(input=total_input_tokens, output=total_output_tokens)
            ),
            skill_pack=self.skill_pack.name if self.skill_pack else "unknown",
            session_outcome=session_outcome,
            total_message_count=len(messages)
        )
    
    def _load_messages(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load messages from JSONL file."""
        messages = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            messages.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except FileNotFoundError:
            return []
        return messages
    
    def _get_session_id(self, messages: List[Dict[str, Any]], file_path: Path) -> str:
        """Get session ID from messages or filename."""
        for msg in messages:
            sid = msg.get('sessionId')
            if sid:
                return sid
        return file_path.stem
    
    def _extract_context(self, messages: List[Dict[str, Any]]) -> SessionContext:
        """Extract session context."""
        context = SessionContext()
        
        for msg in messages:
            if 'cwd' in msg and not context.cwd:
                context.cwd = msg['cwd']
            if 'version' in msg and not context.version:
                context.version = msg['version']
            if 'gitBranch' in msg and not context.git_branch:
                context.git_branch = msg['gitBranch']
            if 'timestamp' in msg and not context.start_time:
                context.start_time = msg['timestamp']
        
        # Extract user command
        # 跳过系统消息，找到真正的用户命令
        skip_patterns = [
            '<local-command-caveat>',
            '<local-command-stdout>',
            'Launching skill:',
            'Base directory for this skill:',
            '[Request interrupted',
        ]
        
        # 先收集所有可能的用户命令
        possible_commands = []
        
        for msg in messages:
            if msg.get('type') == 'user':
                content = safe_get_nested(msg, 'message', 'content')
                if isinstance(content, str):
                    # 检查是否是系统消息
                    should_skip = any(pattern in content for pattern in skip_patterns)
                    if not should_skip:
                        # 检查是否是command格式
                        if '<command-name>' in content:
                            # 提取command-name和command-args
                            import re
                            name_match = re.search(r'<command-name>(.*?)</command-name>', content)
                            args_match = re.search(r'<command-args>(.*?)</command-args>', content)
                            if name_match:
                                command = name_match.group(1)
                                if args_match:
                                    command += ' ' + args_match.group(1)
                                possible_commands.append(command[:200])
                        else:
                            # 提取第一行作为用户命令
                            first_line = content.split('\n')[0][:200]
                            if first_line and not first_line.startswith('<'):
                                possible_commands.append(first_line)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')
                            # 检查是否是系统消息
                            should_skip = any(pattern in text for pattern in skip_patterns)
                            if not should_skip:
                                # 检查是否是command格式
                                if '<command-name>' in text:
                                    import re
                                    name_match = re.search(r'<command-name>(.*?)</command-name>', text)
                                    args_match = re.search(r'<command-args>(.*?)</command-args>', text)
                                    if name_match:
                                        command = name_match.group(1)
                                        if args_match:
                                            command += ' ' + args_match.group(1)
                                        possible_commands.append(command[:200])
                                else:
                                    first_line = text.split('\n')[0][:200]
                                    if first_line and not first_line.startswith('<'):
                                        possible_commands.append(first_line)
        
        # 过滤掉系统命令（如/model），保留真正的用户命令
        system_commands = ['/model']
        for cmd in possible_commands:
            is_system = any(cmd.startswith(sys_cmd) for sys_cmd in system_commands)
            if not is_system:
                context.user_command = cmd
                break
        
        # 如果没有找到真正的用户命令，使用第一个
        if not context.user_command and possible_commands:
            context.user_command = possible_commands[0]
        
        return context
    
    def _extract_skill_evidences(self, messages: List[Dict[str, Any]], 
                                  session_id: str, context: SessionContext,
                                  file_path: Path) -> List[SkillEvidence]:
        """Extract skill evidences using stack-based approach."""
        skill_stack = []
        current_skill_key = None
        assigned_skill: Dict[int, Optional[str]] = {}
        
        for i, msg in enumerate(messages):
            msg_type = msg.get('type')
            
            # Check for Skill tool call (push to stack)
            if msg_type == 'assistant':
                content = safe_get_nested(msg, 'message', 'content', default=[])
                if isinstance(content, list):
                    for item in content:
                        if (isinstance(item, dict) and 
                            item.get('type') == 'tool_use' and 
                            item.get('name') == 'Skill'):
                            skill_name = item.get('input', {}).get('skill', '')
                            if skill_name:
                                skill_stack.append(skill_name)
                                current_skill_key = skill_name
                
                # Check for end_turn (pop from stack)
                stop_reason = safe_get_nested(msg, 'message', 'stop_reason')
                if stop_reason == 'end_turn' and skill_stack:
                    skill_stack.pop()
                    current_skill_key = skill_stack[-1] if skill_stack else None
            
            # Assign message to current skill
            if current_skill_key:
                assigned_skill[i] = current_skill_key
        
        # Group messages by skill
        skill_groups: Dict[str, List[Dict[str, Any]]] = {}
        for i, msg in enumerate(messages):
            skill = assigned_skill.get(i)
            if skill:
                if skill not in skill_groups:
                    skill_groups[skill] = []
                skill_groups[skill].append(msg)
        
        # Build evidence for each skill
        evidences = []
        for skill_name, skill_messages in skill_groups.items():
            evidence = self._build_skill_evidence(
                skill_name, session_id, context, skill_messages, file_path
            )
            evidences.append(evidence)
        
        return evidences
    
    def _build_skill_evidence(self, skill_name: str, session_id: str,
                               context: SessionContext, messages: List[Dict[str, Any]],
                               file_path: Path) -> SkillEvidence:
        """Build SkillEvidence from grouped messages."""
        tool_calls = []
        total_input_tokens = 0
        total_output_tokens = 0
        start_time = None
        end_time = None
        pending_reasoning = None  # Store reasoning until next tool call
        
        for msg in messages:
            timestamp = msg.get('timestamp')
            if timestamp:
                if not start_time:
                    start_time = timestamp
                end_time = timestamp
            
            # Extract token usage
            if msg.get('type') == 'assistant':
                usage = safe_get_nested(msg, 'message', 'usage')
                if usage:
                    total_input_tokens += usage.get('input_tokens', 0)
                    total_output_tokens += usage.get('output_tokens', 0)
                
                # Extract reasoning (before tool calls)
                reasoning = self._extract_reasoning(msg)
                if reasoning:
                    pending_reasoning = reasoning
                
                # Extract tool calls
                content = safe_get_nested(msg, 'message', 'content', default=[])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            tc = self._extract_tool_call(item, messages, msg)
                            if tc:
                                # Add pending reasoning to this tool call
                                if pending_reasoning:
                                    tc.reasoning = pending_reasoning
                                    pending_reasoning = None
                                tool_calls.append(tc)
        
        # Calculate duration
        duration_ms = None
        if start_time and end_time:
            ts_start = parse_timestamp(start_time)
            ts_end = parse_timestamp(end_time)
            if ts_start and ts_end:
                duration_ms = calculate_duration_ms(ts_start, ts_end)
        
        successful = sum(1 for tc in tool_calls if tc.success)
        failed = sum(1 for tc in tool_calls if not tc.success)
        
        # Determine stage
        stage = self._determine_stage(skill_name)
        
        # Extract file I/O and retry chains
        files_read, files_written = self._extract_file_io(tool_calls)
        retry_chains = self._extract_retry_chains(tool_calls)
        
        # Try to load skill definition
        skill_definition = self._load_skill_definition(skill_name)
        
        return SkillEvidence(
            skill_name=skill_name,
            session_id=session_id,
            context=context,
            execution_summary=ExecutionSummary(
                total_tool_calls=len(tool_calls),
                successful_calls=successful,
                failed_calls=failed,
                total_duration_ms=duration_ms or 0,
                token_usage=TokenUsage(input=total_input_tokens, output=total_output_tokens)
            ),
            tool_calls=tool_calls,
            stage=stage,
            skill_definition=skill_definition,
            files_read=files_read,
            files_written=files_written,
            retry_chains=retry_chains,
        )
    
    def _extract_tool_call(self, tool_item: Dict[str, Any],
                            all_messages: List[Dict[str, Any]],
                            assistant_msg: Dict[str, Any]) -> Optional[ToolCall]:
        """Extract tool call information."""
        tool_use_id = tool_item.get('id', '')
        tool_name = tool_item.get('name', 'unknown')
        input_params = tool_item.get('input', {})
        
        input_summary = self._create_input_summary(tool_name, input_params)
        
        # Find corresponding result
        success = True
        error_message = None
        error_output = None
        output_summary = None
        duration_ms = None
        uuid = assistant_msg.get('uuid')
        timestamp = assistant_msg.get('timestamp')
        agent_id = None
        agent_type = None
        
        ts_start = parse_timestamp(assistant_msg.get('timestamp'))
        
        for msg in all_messages:
            if msg.get('type') == 'user':
                content = safe_get_nested(msg, 'message', 'content', default=[])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            if item.get('tool_use_id') == tool_use_id:
                                success = not item.get('is_error', False)
                                if not success:
                                    # error_output 从 content 获取（主要来源）
                                    result_content = item.get('content', '')
                                    if isinstance(result_content, str):
                                        error_output = truncate_string(result_content, 5000)
                                        # error_message 从 error_output 提取第一行
                                        if error_output:
                                            first_line = error_output.split('\n')[0]
                                            error_message = truncate_string(first_line, 200)
                                else:
                                    # Extract output summary for successful calls
                                    output_summary = self._extract_output_summary(item)
                
                tool_result = msg.get('toolUseResult')
                if tool_result and isinstance(tool_result, dict):
                    if msg.get('sourceToolAssistantUUID') == assistant_msg.get('uuid'):
                        if tool_result.get('is_error'):
                            success = False
                            # stderr 只用于hook调试日志，不作为错误信息来源
                            # 如果 error_output 还未从 content 获取，尝试从 toolUseResult 获取
                            if not error_output:
                                stderr = tool_result.get('stderr', '')
                                stdout = tool_result.get('stdout', '')
                                error_output = truncate_string(stderr or stdout, 5000)
                                if error_output:
                                    first_line = error_output.split('\n')[0]
                                    error_message = truncate_string(first_line, 200)
                        else:
                            # Extract output summary from toolUseResult if not already extracted
                            if not output_summary:
                                output_summary = self._extract_output_summary(tool_result)
                        
                        # 提取 subagent 信息（当工具是 Agent/Task 时）
                        if tool_name in ('Agent', 'Task'):
                            agent_id = tool_result.get('agentId')
                            agent_type = tool_result.get('agentType') or input_params.get('subagent_type', '')
                        
                        ts_end = parse_timestamp(msg.get('timestamp'))
                        if ts_start and ts_end:
                            duration_ms = calculate_duration_ms(ts_start, ts_end)
        
        return ToolCall(
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            success=success,
            duration_ms=duration_ms,
            input_summary=input_summary,
            output_summary=output_summary,
            error_message=error_message,
            error_output=error_output,
            uuid=uuid,
            timestamp=timestamp,
            agent_id=agent_id,
            agent_type=agent_type,
        )
    
    def _determine_stage(self, skill_name: str) -> Optional[str]:
        """Determine which stage a skill belongs to."""
        if not self.skill_pack:
            return None
        
        for stage in self.skill_pack.stages:
            if skill_name in stage.skills:
                return stage.name
        return None
    
    def _create_input_summary(self, tool_name: str, input_params: Dict[str, Any]) -> str:
        """Create human-readable input summary."""
        if tool_name == 'Bash':
            return truncate_string(input_params.get('command', ''), self.max_input_summary)
        elif tool_name in ['Read', 'Write', 'Edit']:
            return f"file_path: {input_params.get('file_path', '')}"
        elif tool_name in ['Glob', 'Grep']:
            return f"pattern: {input_params.get('pattern', '')}"
        elif tool_name == 'Skill':
            skill = input_params.get('skill', '')
            args = input_params.get('args', '')
            return f"skill: {skill}, args: {truncate_string(args, self.max_input_summary - len(skill) - 10)}"
        elif tool_name in ['Agent', 'Task']:
            desc = input_params.get('description', '')
            return f"description: {truncate_string(desc, self.max_input_summary)}"
        else:
            return truncate_string(json.dumps(input_params, ensure_ascii=False), self.max_input_summary)
    
    def _extract_output_summary(self, tool_result: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract output summary from tool result."""
        if not tool_result or not self.config.extract_output_summary:
            return None
        
        content = tool_result.get('content', '')
        if isinstance(content, list):
            # Extract text from content blocks
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    elif 'content' in item:
                        text_parts.append(str(item['content']))
            content = ' '.join(text_parts)
        elif isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        
        return truncate_string(content, self.config.max_output_summary)
    
    def _extract_reasoning(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract LLM reasoning from assistant message."""
        if not self.config.extract_reasoning:
            return None
        
        content = safe_get_nested(message, 'message', 'content', default=[])
        if not isinstance(content, list):
            return None
        
        # Extract text blocks before tool_use
        text_blocks = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text' and item.get('text'):
                    text_blocks.append(item['text'])
                # Stop at first tool_use
                elif item.get('type') == 'tool_use':
                    break
        
        if not text_blocks:
            return None
        
        reasoning = ' '.join(text_blocks)
        return truncate_string(reasoning, self.config.max_reasoning)
    
    def _extract_file_io(self, tool_calls: List[ToolCall]) -> Tuple[List[str], List[str]]:
        """Extract file I/O from tool calls."""
        if not self.config.extract_file_io:
            return [], []
        
        files_read = set()
        files_written = set()
        
        for call in tool_calls:
            if call.tool_name == 'Read':
                # Extract file path from input_summary
                if call.input_summary.startswith('file_path: '):
                    files_read.add(call.input_summary[11:])
            elif call.tool_name in ('Write', 'Edit'):
                if call.input_summary.startswith('file_path: '):
                    files_written.add(call.input_summary[11:])
            elif call.tool_name == 'Bash':
                # Try to extract file paths from bash commands
                # This is a simple heuristic
                pass
        
        return list(files_read), list(files_written)
    
    def _extract_retry_chains(self, tool_calls: List[ToolCall]) -> List[List[ToolCall]]:
        """Extract retry chains from tool calls."""
        if not self.config.extract_retry_chains:
            return []
        
        chains = []
        current_chain = []
        
        for call in tool_calls:
            if call.success:
                if current_chain:
                    chains.append(current_chain)
                    current_chain = []
            else:
                current_chain.append(call)
        
        # Don't forget the last chain
        if current_chain:
            chains.append(current_chain)
        
        # Only return chains with multiple failures (actual retries)
        return [chain for chain in chains if len(chain) > 1]
    
    def _determine_stage(self, skill_name: str) -> Optional[str]:
        """Determine which stage a skill belongs to."""
        if not self.skill_pack:
            return None
        
        for stage in self.skill_pack.stages:
            if skill_name in stage.skills or skill_name in stage.agents:
                return stage.name
        
        # Return "unknown" instead of None for better data quality
        return "unknown"
    
    def _handle_no_skill_session(self, messages: List[Dict[str, Any]], 
                                  session_id: str, context: SessionContext,
                                  file_path: Path) -> List[SkillEvidence]:
        """Handle sessions without Skill tool_use calls."""
        # Create an implicit skill from the user command
        skill_name = context.user_command[:20] + "..." if len(context.user_command) > 20 else context.user_command
        if not skill_name:
            skill_name = "implicit_session"
        
        # Build tool calls from all assistant messages
        tool_calls = []
        total_input_tokens = 0
        total_output_tokens = 0
        start_time = None
        end_time = None
        
        for msg in messages:
            timestamp = msg.get('timestamp')
            if timestamp:
                if not start_time:
                    start_time = timestamp
                end_time = timestamp
            
            # Extract token usage
            if msg.get('type') == 'assistant':
                usage = safe_get_nested(msg, 'message', 'usage')
                if usage:
                    total_input_tokens += usage.get('input_tokens', 0)
                    total_output_tokens += usage.get('output_tokens', 0)
                
                # Extract tool calls
                content = safe_get_nested(msg, 'message', 'content', default=[])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_use':
                            tc = self._extract_tool_call(item, messages, msg)
                            if tc:
                                tool_calls.append(tc)
        
        # Calculate duration
        duration_ms = None
        if start_time and end_time:
            ts_start = parse_timestamp(start_time)
            ts_end = parse_timestamp(end_time)
            if ts_start and ts_end:
                duration_ms = calculate_duration_ms(ts_start, ts_end)
        
        successful = sum(1 for tc in tool_calls if tc.success)
        failed = sum(1 for tc in tool_calls if not tc.success)
        
        # Extract file I/O and retry chains
        files_read, files_written = self._extract_file_io(tool_calls)
        retry_chains = self._extract_retry_chains(tool_calls)
        
        # Try to load skill definition
        skill_definition = self._load_skill_definition(skill_name)
        
        return [SkillEvidence(
            skill_name=skill_name,
            session_id=session_id,
            context=context,
            execution_summary=ExecutionSummary(
                total_tool_calls=len(tool_calls),
                successful_calls=successful,
                failed_calls=failed,
                total_duration_ms=duration_ms or 0,
                token_usage=TokenUsage(input=total_input_tokens, output=total_output_tokens)
            ),
            tool_calls=tool_calls,
            stage="implicit",
            skill_definition=skill_definition,
            files_read=files_read,
            files_written=files_written,
            retry_chains=retry_chains,
        )]
    
    def _determine_session_outcome(self, messages: List[Dict[str, Any]], 
                                    skill_evidences: List[SkillEvidence]) -> str:
        """Determine session outcome."""
        # Check for interruption
        for msg in messages:
            content = safe_get_nested(msg, 'message', 'content')
            if isinstance(content, str) and '[Request interrupted' in content:
                return 'interrupted'
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        if '[Request interrupted' in item.get('text', ''):
                            return 'interrupted'
        
        # Check success rate
        if not skill_evidences:
            return 'empty'
        
        total_failed = sum(s.execution_summary.failed_calls for s in skill_evidences)
        total_calls = sum(s.execution_summary.total_tool_calls for s in skill_evidences)
        
        if total_calls == 0:
            return 'empty'
        
        success_rate = (total_calls - total_failed) / total_calls
        if success_rate >= 0.9:
            return 'success'
        elif success_rate >= 0.5:
            return 'partial'
        else:
            return 'failure'
    
    def _extract_end_time(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract end time from messages."""
        for msg in reversed(messages):
            timestamp = msg.get('timestamp')
            if timestamp:
                return timestamp
        return None
    
    def _load_skill_definition(self, skill_name: str) -> Optional[str]:
        """Load skill definition from .claude/skills directory."""
        if not self.config.extract_skill_definition:
            return None
        
        # Try to find skill definition in common locations
        possible_paths = [
            Path.cwd() / '.claude' / 'skills' / skill_name / 'SKILL.md',
            Path.cwd() / 'skills' / skill_name / 'SKILL.md',
            Path.cwd() / 'packs' / self.skill_pack.name / 'skills' / skill_name / 'SKILL.md' if self.skill_pack else None,
        ]
        
        for path in possible_paths:
            if path and path.exists():
                try:
                    content = path.read_text(encoding='utf-8')
                    return truncate_string(content, self.config.max_skill_definition)
                except Exception:
                    pass
        
        return None
