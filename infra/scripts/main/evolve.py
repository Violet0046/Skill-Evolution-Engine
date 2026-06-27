#!/usr/bin/env python3
"""
Skill进化脚本
基于失败分析生成进化任务文件，供 subagent 执行
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infra.scripts.main.analyze import analyze_single_skill_with_suggestions


def read_original_skill(skills_dir: Path, skill_name: str) -> str:
    """读取原始SKILL定义"""
    skill_path = skills_dir / skill_name / 'SKILL.md'
    if not skill_path.exists():
        raise FileNotFoundError(f"SKILL不存在: {skill_path}")
    with open(skill_path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_evolution_task(analysis: dict, skill_content: str) -> dict:
    """生成进化任务，供 subagent 执行"""
    suggestions = analysis.get('evolution_suggestions', [])
    
    if not suggestions:
        return None
    
    # 选择优先级最高的建议
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    suggestions.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))
    
    best_suggestion = suggestions[0]
    evolution_type = best_suggestion.get('type', 'fix')
    
    # 根据进化类型选择提示词模板
    prompt_templates = {
        'fix': 'prompts/fix_evolution.md',
        'derived': 'prompts/derived_evolution.md',
        'captured': 'prompts/captured_evolution.md',
    }
    
    return {
        'task_type': 'evolution',
        'evolution_type': evolution_type,
        'skill_name': analysis.get('skill_name'),
        'skill_content': skill_content,
        'direction': best_suggestion.get('direction', ''),
        'failure_context': best_suggestion.get('failure_context', ''),
        'priority': best_suggestion.get('priority', 'medium'),
        'prompt_template': prompt_templates.get(evolution_type, 'prompts/fix_evolution.md'),
        'analysis_summary': {
            'total_sessions': analysis.get('total_sessions', 0),
            'total_calls': analysis.get('total_calls', 0),
            'failed_calls': analysis.get('failed_calls', 0),
            'failure_rate': analysis.get('failure_rate', 0),
        },
        'generated_at': datetime.now().isoformat(),
    }


def evolve_skill_from_analysis(skills_dir: Path, skill_name: str, analysis: dict, output_dir: Path = None) -> dict:
    """基于分析结果生成进化任务"""
    if analysis.get('total_calls', 0) == 0:
        return {
            'skill_name': skill_name,
            'status': 'skipped',
            'reason': '无调用数据',
        }
    
    if analysis.get('failed_calls', 0) == 0:
        return {
            'skill_name': skill_name,
            'status': 'skipped',
            'reason': '无失败案例',
        }
    
    # 读取原始SKILL
    try:
        skill_content = read_original_skill(skills_dir, skill_name)
    except FileNotFoundError as e:
        return {
            'skill_name': skill_name,
            'status': 'skipped',
            'reason': str(e),
        }
    
    # 生成进化任务
    task = generate_evolution_task(analysis, skill_content)
    
    if not task:
        return {
            'skill_name': skill_name,
            'status': 'skipped',
            'reason': '无进化建议',
        }
    
    # 保存任务文件
    if output_dir is None:
        output_dir = Path.cwd() / 'evolution_tasks'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    task_file = output_dir / f'{skill_name}.json'
    
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task, f, indent=2, ensure_ascii=False)
    
    return {
        'skill_name': skill_name,
        'status': 'task_generated',
        'evolution_type': task['evolution_type'],
        'priority': task['priority'],
        'task_file': str(task_file),
        'analysis_summary': task['analysis_summary'],
    }


def evolve_skill(skills_dir: Path, output_dir: Path, skill_name: str, task_output_dir: Path = None) -> dict:
    """进化指定skill（从output目录分析）"""
    # 分析失败模式并生成进化建议
    analysis = analyze_single_skill_with_suggestions(output_dir, skill_name)
    
    return evolve_skill_from_analysis(skills_dir, skill_name, analysis, task_output_dir)


def main():
    parser = argparse.ArgumentParser(description='生成SKILL进化任务')
    parser.add_argument('skill_name', nargs='?', help='skill名称')
    parser.add_argument('--all', '-a', action='store_true', help='处理所有skill')
    parser.add_argument('--skills-dir', '-s', type=Path, default=Path('skills'), help='skills目录')
    parser.add_argument('--output-dir', '-o', type=Path, default=Path('output'), help='证据数据目录')
    parser.add_argument('--task-dir', '-t', type=Path, help='进化任务输出目录')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    
    args = parser.parse_args()
    
    if not args.skills_dir.exists():
        print(f"错误：skills目录不存在: {args.skills_dir}")
        sys.exit(1)
    
    # 从output目录分析并生成进化任务
    if not args.output_dir.exists():
        print(f"错误：output目录不存在: {args.output_dir}")
        sys.exit(1)
    
    task_output_dir = args.task_dir or Path.cwd() / 'evolution_tasks'
    
    if args.all:
        # 处理所有skill
        results = []
        for skill_dir in args.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / 'SKILL.md').exists():
                try:
                    result = evolve_skill(args.skills_dir, args.output_dir, skill_dir.name, task_output_dir)
                    results.append(result)
                    if result['status'] == 'task_generated':
                        print(f"✓ {skill_dir.name}: {result['evolution_type']} 进化任务已生成")
                    else:
                        print(f"- {skill_dir.name}: {result['reason']}")
                except Exception as e:
                    print(f"✗ {skill_dir.name}: {e}")
        
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(f"\n共处理 {len(results)} 个skill")
    elif args.skill_name:
        # 处理指定skill
        try:
            result = evolve_skill(args.skills_dir, args.output_dir, args.skill_name, task_output_dir)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif result['status'] == 'task_generated':
                print(f"进化任务已生成: {result['skill_name']}")
                print(f"  进化类型: {result['evolution_type']}")
                print(f"  优先级: {result['priority']}")
                print(f"  任务文件: {result['task_file']}")
            else:
                print(f"跳过: {result['skill_name']} - {result['reason']}")
        except Exception as e:
            print(f"进化失败: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
