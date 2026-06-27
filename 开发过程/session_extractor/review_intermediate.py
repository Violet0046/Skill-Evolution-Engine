"""
演示 simplify + detector 两阶段产物的脚本。
- 阶段 0: 原始 entries（classifier + sort_by_timestamp 之后）
- 阶段 1: simplify 之后（detector 还没跑）
- 阶段 2: 完整 v4 collector 输出
"""

import sys
import json
import os
import tempfile

sys.path.insert(0, ".")

from src.pipeline import run as pipeline_run, _classify_entries
from src.util.session_io import load_session_entries
from src.util.timestamp import sort_by_timestamp
from src.util.session_io import extract_session_header, insert_cwd_changes
from src.simplify import simplify_entries

SESSION = "1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl"
CONFIG = "src/simplify/entry_fields_config.json"
SPECS = "specs/"


def show_entry(label, e, max_text_len=60):
    """格式化单条 entry 输出。"""
    cls = e.get("entry_class", "?")
    uuid_short = (e.get("uuid") or "?")[:8]
    # 提取 message.content 的关键信息
    msg = e.get("message", {})
    info = ""
    if cls == "ai_text":
        text = msg.get("content", [{}])[0].get("text", "") if msg.get("content") else ""
        text_short = (text[:max_text_len] + "...") if len(text) > max_text_len else text
        info = f"text='{text_short}'"
    elif cls == "ai_tool_call":
        items = msg.get("content", [])
        if items:
            name = items[0].get("name", "")
            info = f"name={name}"
    elif cls == "tool_result":
        content = msg.get("content", [{}])[0].get("content", "") if msg.get("content") else ""
        info = f"content='{content[:30]}...'" if len(content) > 30 else f"content='{content}'"
    elif cls == "user_input":
        content = msg.get("content", "")
        if isinstance(content, str):
            info = f"text='{content[:40]}'"
    elif cls == "attachment.hook_success":
        att = e.get("attachment", {})
        info = f"hook={att.get('hookName','')} exit={att.get('exitCode','')}"
    cwd_field = e.get("cwd")
    cwd_str = f" cwd={cwd_field[:30]}" if cwd_field else ""
    prev_str = f" prev_cwd={e['prev_cwd'][:30]}" if "prev_cwd" in e else ""
    return f"  [{label:12s}] uuid={uuid_short} cls={cls:25s} {info}{cwd_str}{prev_str}"


def show_phase(label, entries, max_show=8):
    """展示一组 entry 的关键信息。"""
    print(f"\n{'='*80}\n{label}（{len(entries)} 条 entry）\n{'='*80}")
    for e in entries[:max_show]:
        print(show_entry("", e))
    if len(entries) > max_show:
        print(f"  ... ({len(entries) - max_show} more)")


def main():
    # 强制 stdout 用 UTF-8（避免 Windows GBK 乱码）
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory() as d:
        # === 阶段 0: load + classify + sort（不做 simplify）===
        print("\n\n" + "="*80)
        print("阶段 0: load + classify + sort（无 simplify）")
        print("="*80)
        entries, _ = load_session_entries(SESSION)
        _classify_entries(entries)                # pipeline 用的 in-place 版本
        entries = sort_by_timestamp(entries)
        entries, cwd_changes = insert_cwd_changes(entries)
        print(f"原始 entry 数: {len(entries)}")
        print(f"cwd_changes 计数: {cwd_changes}")

        # 字段统计
        all_keys = set()
        for e in entries:
            all_keys.update(e.keys())
        print(f"原始 entry 字段 union: {sorted(all_keys)}")
        show_phase("阶段 0 — classify+sort 后", entries, max_show=6)

        # === 阶段 1: simplify 之后（detector 还没跑）===
        print("\n\n" + "="*80)
        print("阶段 1: simplify 之后（detector 还没跑）")
        print("="*80)
        simplified = simplify_entries(entries, CONFIG)
        print(f"simplified entry 数: {len(simplified)}（整类型 DROP {len(entries) - len(simplified)} 条）")

        all_keys_s = set()
        for e in simplified:
            all_keys_s.update(e.keys())
        print(f"simplified entry 字段 union: {sorted(all_keys_s)}")

        # 比较 字段集
        dropped_keys = all_keys - all_keys_s
        added_keys = all_keys_s - all_keys
        if dropped_keys:
            print(f"被 drop 的字段: {sorted(dropped_keys)}")
        if added_keys:
            print(f"新增字段: {sorted(added_keys)}")

        show_phase("阶段 1 — simplify 后", simplified, max_show=6)

        # === 阶段 2: 完整 collector（simplify + detector + bundle）===
        print("\n\n" + "="*80)
        print("阶段 2: 完整 v4 collector（simplify + detector + bundle）")
        print("="*80)

        # 阶段 2.5: 先单独展示每个 detector 的原始输出（直接调 detector.run()）
        print("\n--- 阶段 2.5: 5 个 detector 各自 run() 的输出 ---")

        from src.detectors import get_all, run_all
        from src.models import DetectorContext, ClassifiedEntry
        from src.spec_loader import load_spec as load_spec_func
        from src.pipeline import _build_ctx_spec

        classified_for_det = [ClassifiedEntry(raw=e, entry_class=e.get("entry_class", ""))
                               for e in simplified]

        spec = load_spec_func(SPECS)
        ctx = DetectorContext(spec=_build_ctx_spec(spec), env={}, cwd_realpath_cache={})

        all_results = run_all(classified_for_det, ctx, enabled=None)
        for det_name, events in all_results.items():
            print(f"\n  [{det_name}] 输出 {len(events)} 条事件:")
            for ev in events[:3]:
                # 截短每个 event 的展示
                ev_short = str(ev)[:200] + "..." if len(str(ev)) > 200 else str(ev)
                print(f"    {ev_short}")
            if len(events) > 3:
                print(f"    ... ({len(events) - 3} more)")

        # 然后跑完整 collector（写到 out.jsonl）
        out_path = os.path.join(d, "out.jsonl")
        bundle = pipeline_run(
            input_path=SESSION,
            output_path=out_path,
            config_path=CONFIG,
            spec_dir=SPECS,
            quiet=True,
        )

        # 读 header（第 1 行）
        with open(out_path, "r", encoding="utf-8") as f:
            header = json.loads(f.readline())
            trace_lines = f.readlines()

        print(f"\n--- Bundle Header（schema_version={header['schema_version']}）---")
        print(f"session 字段: {len(header['session'])} 个")
        for k, v in header["session"].items():
            v_short = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
            print(f"  {k:18s} = {v_short}")

        print(f"\nstate_machine:")
        print(f"  phases: {header['state_machine']['phases']}")
        print(f"  transitions: {len(header['state_machine']['transitions'])} 条")
        for t in header['state_machine']['transitions'][:3]:
            print(f"    {t.get('phase')} via {t.get('role')} at {t.get('at')}")

        print(f"\nconstraint_events: {len(header['constraint_events'])} 条")
        for e in header['constraint_events'][:3]:
            print(f"  kind={e.get('kind'):20s} phase={e.get('phase'):8s} exit={e.get('exit_code')}")

        print(f"\nuser_feedback: {len(header['user_feedback'])} 条")
        for f in header['user_feedback'][:3]:
            text = f.get('text', '')[:50] + "..." if len(f.get('text', '')) > 50 else f.get('text', '')
            print(f"  text='{text}'")

        print(f"\nexecution_pattern:")
        print(f"  step_counts: {header['execution_pattern']['step_counts']}")
        print(f"  tool_distribution: {header['execution_pattern']['tool_distribution']}")
        print(f"  phase_durations: {list(header['execution_pattern']['phase_durations'].keys())}")

        print(f"\ndetector_meta:")
        print(f"  enabled: {header['detector_meta']['enabled']}")
        print(f"  spec_loaded: {header['detector_meta']['spec_loaded']}")
        print(f"  truncate_enabled: {header['detector_meta']['truncate_enabled']}")
        print(f"  warnings: {header['detector_meta']['warnings']}")

        print(f"\n--- Trace NDJSON（{len(trace_lines)} 条）---")
        for i, line in enumerate(trace_lines[:5]):
            e = json.loads(line)
            print(show_entry(f"trace[{i}]", e))
        print(f"  ... ({len(trace_lines) - 5} more)" if len(trace_lines) > 5 else "")


if __name__ == "__main__":
    main()
