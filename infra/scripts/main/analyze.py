#!/usr/bin/env python3
"""
失败模式分析脚本
按skill维度分析失败模式，提供具体证据
"""

import argparse
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

# 添加项目根目录到Python路径
# __file__ = infra/scripts/main/analyze.py
# 需要向上4级到项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def analyze_all_skills(output_dir: Path) -> dict:
    """按skill维度分析所有skill的失败模式"""
    skill_failures = defaultdict(lambda: {
        'total_sessions': 0,
        'total_calls': 0,
        'failed_calls': 0,
        'failure_patterns': defaultdict(lambda: {'count': 0, 'evidence': []}),
        'session_ids': set(),
    })
    
    for session_dir in output_dir.iterdir():
        if not session_dir.is_dir():
            continue
        
        skills_dir = session_dir / 'skills'
        if not skills_dir.exists():
            continue
        
        for skill_file in skills_dir.glob('*.json'):
            skill_name = skill_file.stem
            
            with open(skill_file, 'r', encoding='utf-8') as f:
                skill = json.load(f)
            
            skill_failures[skill_name]['total_sessions'] += 1
            skill_failures[skill_name]['session_ids'].add(session_dir.name)
            
            for tc in skill.get('tool_calls', []):
                skill_failures[skill_name]['total_calls'] += 1
                
                if not tc.get('success', True):
                    skill_failures[skill_name]['failed_calls'] += 1
                    
                    error = tc.get('error_output') or tc.get('error_message') or 'unknown'
                    pattern = f"{tc.get('tool_name', 'unknown')}:{error[:80]}"
                    
                    skill_failures[skill_name]['failure_patterns'][pattern]['count'] += 1
                    skill_failures[skill_name]['failure_patterns'][pattern]['evidence'].append({
                        'session_id': session_dir.name,
                        'uuid': tc.get('uuid'),
                        'tool_name': tc.get('tool_name'),
                        'input_summary': tc.get('input_summary'),
                        'error_output': tc.get('error_output'),
                        'reasoning': tc.get('reasoning'),
                    })
    
    # 转换为可序列化的格式
    result = {
        'total_skills': len(skill_failures),
        'skills': []
    }
    
    for skill_name, data in skill_failures.items():
        total_calls = data['total_calls']
        failed_calls = data['failed_calls']
        
        # 按count排序失败模式
        sorted_patterns = sorted(
            data['failure_patterns'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        skill_result = {
            'skill_name': skill_name,
            'total_sessions': data['total_sessions'],
            'total_calls': total_calls,
            'failed_calls': failed_calls,
            'failure_rate': failed_calls / total_calls if total_calls > 0 else 0,
            'failure_patterns': [
                {
                    'pattern': pattern,
                    'count': info['count'],
                    'evidence': info['evidence'][:5],  # 每个模式最多5个证据
                }
                for pattern, info in sorted_patterns[:10]  # 最多10个模式
            ]
        }
        result['skills'].append(skill_result)
    
    # 按失败率排序
    result['skills'].sort(key=lambda x: x['failure_rate'], reverse=True)
    
    return result


def analyze_single_skill(output_dir: Path, skill_name: str) -> dict:
    """分析指定skill的失败模式"""
    error_patterns = Counter()
    failure_details = []
    total_calls = 0
    failed_calls = 0
    total_sessions = 0
    
    for session_dir in output_dir.iterdir():
        if not session_dir.is_dir():
            continue
        
        skill_path = session_dir / f'skills/{skill_name}.json'
        if not skill_path.exists():
            continue
        
        total_sessions += 1
        
        with open(skill_path, 'r', encoding='utf-8') as f:
            skill = json.load(f)
        
        for tc in skill.get('tool_calls', []):
            total_calls += 1
            if not tc.get('success', True):
                failed_calls += 1
                error = tc.get('error_output') or tc.get('error_message') or 'unknown'
                pattern = f"{tc.get('tool_name', 'unknown')}:{error[:80]}"
                error_patterns[pattern] += 1
                
                failure_details.append({
                    'session_id': session_dir.name,
                    'uuid': tc.get('uuid'),
                    'tool_name': tc.get('tool_name'),
                    'input_summary': tc.get('input_summary'),
                    'error_output': tc.get('error_output'),
                    'reasoning': tc.get('reasoning'),
                })
    
    return {
        'skill_name': skill_name,
        'total_sessions': total_sessions,
        'total_calls': total_calls,
        'failed_calls': failed_calls,
        'failure_rate': failed_calls / total_calls if total_calls > 0 else 0,
        'failure_patterns': [
            {
                'pattern': pattern,
                'count': count,
                'evidence': [d for d in failure_details if f"{d['tool_name']}:{(d['error_output'] or 'unknown')[:80]}" == pattern][:5]
            }
            for pattern, count in error_patterns.most_common(10)
        ]
    }


def analyze_single_skill_with_suggestions(output_dir: Path, skill_name: str) -> dict:
    """分析指定skill的失败模式并生成进化建议"""
    result = analyze_single_skill(output_dir, skill_name)
    result['evolution_suggestions'] = generate_evolution_suggestions(result)
    return result


def generate_evolution_suggestions(skill_data: dict) -> list:
    """基于分析结果生成进化建议"""
    suggestions = []
    
    failure_rate = skill_data.get('failure_rate', 0)
    failure_patterns = skill_data.get('failure_patterns', [])
    
    # 如果失败率低于 10%，不建议进化
    if failure_rate < 0.1:
        return suggestions
    
    # 分析失败模式，生成建议
    for pattern_data in failure_patterns[:3]:  # 只处理前3个主要模式
        pattern = pattern_data.get('pattern', '')
        count = pattern_data.get('count', 0)
        evidence = pattern_data.get('evidence', [])
        
        # 根据失败模式判断进化类型
        if 'Exit code 127' in pattern or 'not found' in pattern.lower():
            suggestions.append({
                'type': 'fix',
                'direction': f'脚本或命令路径错误（出现{count}次），需要修正路径或添加路径检查',
                'failure_context': format_failure_context(evidence),
                'priority': 'high'
            })
        elif 'File does not exist' in pattern or 'No such file' in pattern:
            suggestions.append({
                'type': 'fix',
                'direction': f'文件不存在（出现{count}次），需要添加文件存在性检查',
                'failure_context': format_failure_context(evidence),
                'priority': 'high'
            })
        elif 'permission denied' in pattern.lower():
            suggestions.append({
                'type': 'fix',
                'direction': f'权限不足（出现{count}次），需要添加权限检查或使用正确的用户',
                'failure_context': format_failure_context(evidence),
                'priority': 'medium'
            })
        elif 'timeout' in pattern.lower():
            suggestions.append({
                'type': 'fix',
                'direction': f'超时（出现{count}次），需要增加超时时间或优化执行',
                'failure_context': format_failure_context(evidence),
                'priority': 'medium'
            })
        elif 'syntax error' in pattern.lower() or 'Traceback' in pattern:
            suggestions.append({
                'type': 'fix',
                'direction': f'语法或运行时错误（出现{count}次），需要修复脚本错误',
                'failure_context': format_failure_context(evidence),
                'priority': 'high'
            })
        else:
            # 对于其他错误，如果失败率很高，建议派生
            if failure_rate > 0.3 and count >= 3:
                suggestions.append({
                    'type': 'derived',
                    'direction': f'多次出现相同错误（{count}次），建议创建更健壮的版本',
                    'failure_context': format_failure_context(evidence),
                    'priority': 'medium'
                })
    
    # 如果没有明确的修复建议，但失败率较高，建议派生
    if not suggestions and failure_rate > 0.2:
        suggestions.append({
            'type': 'derived',
            'direction': f'整体失败率较高（{failure_rate:.1%}），建议创建增强版本',
            'failure_context': format_failure_context_summary(skill_data),
            'priority': 'low'
        })
    
    return suggestions


def format_failure_context(evidence: list) -> str:
    """格式化失败上下文"""
    lines = []
    for i, ev in enumerate(evidence[:3], 1):
        lines.append(f"### 失败案例 {i}")
        lines.append(f"- Session: {ev.get('session_id', 'N/A')}")
        lines.append(f"- 工具: {ev.get('tool_name', 'N/A')}")
        lines.append(f"- 输入: {ev.get('input_summary', 'N/A')[:100]}")
        lines.append(f"- 错误: {ev.get('error_output', 'N/A')[:100]}")
        if ev.get('reasoning'):
            lines.append(f"- 推理: {ev['reasoning'][:100]}")
        lines.append("")
    return '\n'.join(lines)


def format_failure_context_summary(skill_data: dict) -> str:
    """格式化失败上下文摘要"""
    lines = []
    lines.append(f"## 统计")
    lines.append(f"- 总调用: {skill_data.get('total_calls', 0)}")
    lines.append(f"- 失败调用: {skill_data.get('failed_calls', 0)}")
    lines.append(f"- 失败率: {skill_data.get('failure_rate', 0):.1%}")
    lines.append("")
    lines.append("## 主要失败模式")
    for i, pattern in enumerate(skill_data.get('failure_patterns', [])[:3], 1):
        lines.append(f"{i}. {pattern.get('pattern', 'N/A')} ({pattern.get('count', 0)}次)")
    return '\n'.join(lines)


def format_skill_report(skill_data: dict) -> str:
    """格式化单个skill的分析报告"""
    lines = []
    lines.append(f"# {skill_data['skill_name']} 失败模式分析")
    lines.append("")
    lines.append("## 统计")
    lines.append(f"- 分析session数：{skill_data['total_sessions']}")
    lines.append(f"- 总调用次数：{skill_data['total_calls']}")
    lines.append(f"- 失败调用次数：{skill_data['failed_calls']}")
    lines.append(f"- 失败率：{skill_data['failure_rate']:.2%}")
    lines.append("")
    
    lines.append("## TOP失败模式")
    for i, pattern_data in enumerate(skill_data['failure_patterns'], 1):
        lines.append(f"{i}. **{pattern_data['pattern']}** ({pattern_data['count']}次)")
        
        # 显示证据
        if pattern_data.get('evidence'):
            for evidence in pattern_data['evidence'][:2]:  # 最多显示2个证据
                lines.append(f"   - Session: {evidence['session_id']}")
                lines.append(f"     UUID: {evidence.get('uuid', 'N/A')}")
                lines.append(f"     Input: {evidence.get('input_summary', 'N/A')[:60]}")
                lines.append(f"     Error: {evidence.get('error_output', 'N/A')[:60]}")
    lines.append("")
    
    return "\n".join(lines)


def format_all_skills_report(result: dict) -> str:
    """格式化所有skill的分析报告"""
    lines = []
    lines.append("# Skill失败模式分析报告")
    lines.append("")
    lines.append(f"共分析 {result['total_skills']} 个skill")
    lines.append("")
    
    for skill_data in result['skills']:
        if skill_data['failed_calls'] > 0:
            lines.append(f"## {skill_data['skill_name']}")
            lines.append(f"- 失败率：{skill_data['failure_rate']:.2%}")
            lines.append(f"- 失败调用：{skill_data['failed_calls']}/{skill_data['total_calls']}")
            lines.append(f"- TOP失败模式：{skill_data['failure_patterns'][0]['pattern'] if skill_data['failure_patterns'] else 'N/A'}")
            lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='按skill维度分析失败模式')
    parser.add_argument('output_dir', type=Path, help='证据数据目录')
    parser.add_argument('skill_name', nargs='?', help='skill名称（可选，不指定则分析所有skill）')
    parser.add_argument('--output', '-o', type=Path, help='输出文件路径')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--suggestions', '-s', action='store_true', help='生成进化建议')
    
    args = parser.parse_args()
    
    if not args.output_dir.exists():
        print(f"错误：输出目录不存在: {args.output_dir}")
        sys.exit(1)
    
    # 分析失败模式
    if args.skill_name:
        # 分析单个skill
        if args.suggestions:
            result = analyze_single_skill_with_suggestions(args.output_dir, args.skill_name)
        else:
            result = analyze_single_skill(args.output_dir, args.skill_name)
        if args.json:
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            output = format_skill_report(result)
    else:
        # 分析所有skill
        result = analyze_all_skills(args.output_dir)
        if args.json:
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            output = format_all_skills_report(result)
    
    # 输出结果
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"报告已写入: {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
