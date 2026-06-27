#!/usr/bin/env python3
"""
证据提取脚本
从session JSONL文件中提取结构化证据
"""

import argparse
import json
import sys
from pathlib import Path
from dataclasses import asdict

# 添加项目根目录到Python路径
# __file__ = infra/scripts/main/extract.py
# 需要向上4级到项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from infra.core.extractors import SessionExtractor
from infra.core.models.skill_pack import load_skill_pack


def main():
    parser = argparse.ArgumentParser(description='提取session证据')
    parser.add_argument('input', type=Path, help='输入JSONL文件或目录')
    parser.add_argument('--output', '-o', type=Path, default=Path('output'), help='输出目录')
    parser.add_argument('--skill-pack', '-s', type=str, default='requirement_analysis', help='技能包名称')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细日志')
    
    args = parser.parse_args()
    
    # 配置日志
    import logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # 加载技能包
    pack_path = Path(__file__).parent.parent.parent / 'packs' / args.skill_pack / 'pack.json'
    if pack_path.exists():
        skill_pack = load_skill_pack(str(pack_path))
        logger.info(f"加载技能包: {skill_pack.name}")
    else:
        logger.warning(f"技能包不存在: {pack_path}，使用默认配置")
        skill_pack = None
    
    # 创建提取器
    extractor = SessionExtractor(skill_pack=skill_pack)
    
    # 处理输入
    if args.input.is_file():
        logger.info(f"处理文件: {args.input}")
        evidence = extractor.extract_from_file(args.input)
        write_evidence(evidence, args.output, logger)
    elif args.input.is_dir():
        jsonl_files = list(args.input.rglob('*.jsonl'))
        jsonl_files = [f for f in jsonl_files if 'subagents' not in str(f)]
        logger.info(f"找到 {len(jsonl_files)} 个JSONL文件")
        
        for i, file_path in enumerate(jsonl_files, 1):
            try:
                logger.info(f"处理 [{i}/{len(jsonl_files)}]: {file_path.name}")
                evidence = extractor.extract_from_file(file_path)
                write_evidence(evidence, args.output, logger)
            except Exception as e:
                logger.error(f"处理失败 {file_path}: {e}")
    else:
        logger.error(f"输入路径不存在: {args.input}")
        sys.exit(1)
    
    logger.info("提取完成")


def write_evidence(evidence, output_dir, logger):
    """写入证据数据"""
    session_dir = output_dir / evidence.session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # 写入metadata
    metadata = {
        'session_id': evidence.session_id,
        'session_path': evidence.session_path,
        'user_command': evidence.context.user_command,
        'cwd': evidence.context.cwd,
        'version': evidence.context.version,
        'git_branch': evidence.context.git_branch,
        'start_time': evidence.context.start_time,
        'end_time': evidence.context.end_time,
        'requirement_id': evidence.context.requirement_id,
        'skill_pack': evidence.skill_pack,
    }
    with open(session_dir / 'metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # 写入skills
    skills_dir = session_dir / 'skills'
    skills_dir.mkdir(parents=True, exist_ok=True)
    for skill in evidence.skills:
        with open(skills_dir / f'{skill.skill_name}.json', 'w', encoding='utf-8') as f:
            json.dump(asdict(skill), f, indent=2, ensure_ascii=False)
    
    # 写入summary
    summary = {
        'session_id': evidence.session_id,
        'session_path': evidence.session_path,
        'session_outcome': evidence.session_outcome,
        'total_message_count': evidence.total_message_count,
        'total_skills': len(evidence.skills),
        'total_tool_calls': evidence.execution_summary.total_tool_calls,
        'successful_calls': evidence.execution_summary.successful_calls,
        'failed_calls': evidence.execution_summary.failed_calls,
        'success_rate': evidence.execution_summary.success_rate,
        'success_level': evidence.execution_summary.success_level,
        'total_duration_ms': evidence.execution_summary.total_duration_ms,
        'token_usage': {
            'input': evidence.execution_summary.token_usage.input,
            'output': evidence.execution_summary.token_usage.output,
        },
        'skills': [
            {
                'skill_name': s.skill_name,
                'stage': s.stage,
                'success_level': s.execution_summary.success_level,
                'failed_calls': s.execution_summary.failed_calls,
                'duration_ms': s.execution_summary.total_duration_ms,
            }
            for s in evidence.skills
        ],
    }
    with open(session_dir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"  写入: {session_dir}")


if __name__ == '__main__':
    main()
