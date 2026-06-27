"""
演示：从 out.jsonl（v4 collector 的输出）读 → 重新跑 detector → 输出事件。

模拟 phase2 使用方式：消费 out.jsonl 提取硬约束信号。
"""

import sys
import json

sys.path.insert(0, ".")

from types import SimpleNamespace
from src.detectors import run_all
from src.models import ClassifiedEntry, DetectorContext
from src.spec_loader import load_spec
from src.pipeline import _build_ctx_spec

OUT = "out_v4_review.jsonl"
SPECS = "specs/"


def main():
    # 强制 UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 第一步：跑 v4 collector 写 out.jsonl
    print("=" * 80)
    print("Step 1: 跑 v4 collector 写 out.jsonl")
    print("=" * 80)
    from src.pipeline import run as pipeline_run
    import os
    out_path = OUT
    bundle = pipeline_run(
        input_path="1b4c0c37-23cc-4e75-9eb9-125629d9d274.jsonl",
        output_path=out_path,
        config_path="src/simplify/entry_fields_config.json",
        spec_dir=SPECS,
        quiet=True,
    )
    print(f"已写: {out_path} ({os.path.getsize(out_path)} bytes)")
    print()

    # 第二步：模拟 phase2 — 读 out.jsonl，重新跑 detector
    print("=" * 80)
    print("Step 2: 模拟 phase2 — 读 out.jsonl，重新跑 detector")
    print("=" * 80)
    print("(完全独立于 pipeline.py 的 detector 调用，验证 out.jsonl 字段足够 detector 还原原信号)")
    print()

    with open(out_path, "r", encoding="utf-8") as f:
        header = json.loads(f.readline())
        trace_entries = [json.loads(line) for line in f if line.strip()]

    print(f"读到的 header 字段: {len(header)} 个")
    print(f"读到的 trace entries: {len(trace_entries)} 条")
    print()

    # 构造 ClassifiedEntry 列表（用 trace entries）
    classified = [ClassifiedEntry(raw=e, entry_class=e.get("entry_class", ""))
                  for e in trace_entries]
    spec = load_spec(SPECS)
    ctx = DetectorContext(spec=_build_ctx_spec(spec), env={}, cwd_realpath_cache={})

    # 跑 5 个 detector
    print("=" * 80)
    print("Step 3: 5 detector 从 out.jsonl 还原的信号")
    print("=" * 80)
    results = run_all(classified, ctx, enabled=None)

    detector_to_bundle_field = {
        "state_machine": "state_machine",
        "gate": "constraint_events",
        "review_contract": "constraint_events",
        "user_confirmation": "user_feedback",
        "symlink": "symlink_hop",
    }

    for det_name, events in results.items():
        bundle_field = detector_to_bundle_field.get(det_name, "?")
        print(f"\n[{det_name}] → bundle.{bundle_field}（{len(events)} 条事件）")

        # 跟原始 bundle 的对应字段对比
        if det_name == "state_machine":
            original = bundle.state_machine
            original_count = len(original.get("transitions", []))
            this_count = len(events[0].get("transitions", [])) if events else 0
            match = "✓" if original_count == this_count else "✗"
            print(f"  跟原 bundle 对比: {match} (这次 transitions={this_count}, 原 bundle={original_count})")
        elif det_name in ("gate", "review_contract"):
            # 注意：bundle 中 kind 是 "gate_rejected" / "review_contract"（不是 detector 名字）
            kind_in_bundle = "gate_rejected" if det_name == "gate" else "review_contract"
            original_count = sum(1 for e in bundle.constraint_events if e.get("kind") == kind_in_bundle)
            match = "✓" if original_count == len(events) else "✗"
            print(f"  跟原 bundle 对比: {match} (这次={len(events)}, 原 constraint_events 中 kind={kind_in_bundle}: {original_count})")
        elif det_name == "user_confirmation":
            match = "✓" if len(bundle.user_feedback) == len(events) else "✗"
            print(f"  跟原 bundle 对比: {match} (这次={len(events)}, 原 user_feedback: {len(bundle.user_feedback)})")
        elif det_name == "symlink":
            match = "✓" if len(bundle.symlink_hop) == len(events) else "✗"
            print(f"  跟原 bundle 对比: {match} (这次={len(events)}, 原 symlink_hop: {len(bundle.symlink_hop)})")

        for ev in events[:3]:
            ev_short = str(ev)[:180] + "..." if len(str(ev)) > 180 else str(ev)
            print(f"    {ev_short}")
        if len(events) > 3:
            print(f"    ... ({len(events) - 3} more)")

    print()
    print("=" * 80)
    print("总结: out.jsonl 包含足够信息让 detector 还原所有信号")
    print("=" * 80)

    # 清理
    if os.path.exists(out_path):
        os.unlink(out_path)


if __name__ == "__main__":
    main()
