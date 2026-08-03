"""select_sessions.py —— 一次性脚本：从 viking_all_session 挑 4 类 Agent session，
                       直接按 Agent × Batch 维度落地（无中间产物层）。

扫描流程：

  Pass 1（统计）
    扫描 /home/10358563/viking_all_session/<sid>/projects/<encoded_cwd>/*.jsonl，
    对每个 jsonl 看第一条 user 消息的 cwd basename，命中以下 4 个 Agent 时：
      - 需求分析Agent
      - 系统方案设计Agent
      - 子系统设计Agent
      - 组件设计Agent
    累计 (agent, sid, sub_dir) 的 jsonl 数。不拷任何文件。

  Pass 1.5（质量筛选）
    对每个 jsonl，检查源目录下是否存在同名 <sid>/ 子目录（即该主 session 是否
    召唤过 sub-agent）。如果不存在，丢弃该 jsonl —— 没召唤过 sub-agent 的 session
    没有分析价值。

  贪心装箱（first-fit-decreasing by jsonl count）
    对每个 Agent 独立装箱，按 jsonl 数降序排序 (sid, count)，
    把每个 sid 塞进"当前 jsonl 数最小且 + count 不超阈值"的 batch。
    超大 sid（count > batch_limit）单独成 batch。

  Pass 2（拷贝）
    按 (agent, sid) -> batch_id 映射表，把每个 jsonl **和它对应的 <sid>/ 子树**
    平铺拷到 <dst>/<Agent>/batch_NN/ 下：
      <dst>/<Agent>/batch_NN/<sid>.jsonl
      <dst>/<Agent>/batch_NN/<sid>/
    主 session 和它下属 sub-agent 目录永远在同一个 batch（最小不可拆单元）。
    不拷 .tmp/ 等中间产物。
    不同 workspace / encoded_cwd 下的同名 sid 会去重（同一个 sid 只拷一次）。

输出（最终结构，平铺无中间层）：
  /home/10358563/viking_all_session/SEE/
    ├── 需求分析Agent/
    │   ├── batch_00/
    │   │   ├── <sid_A>.jsonl                ← 主 session（仅保留有 sub-agent 调用的）
    │   │   ├── <sid_A>/                      ← 主 session 召唤的 sub-agent 会话数据
    │   │   ├── <sid_B>.jsonl
    │   │   └── <sid_B>/
    │   ├── batch_01/...
    │   └── ...
    ├── 系统方案设计Agent/
    │   └── ...
    ├── 子系统设计Agent/
    │   └── ...
    ├── 组件设计Agent/
    │   └── ...
    ├── select_sessions.batches.json    (装箱清单)
    ├── select_sessions.manifest.json   (扫描清单)
    └── select_sessions.log

设计要点：
  - 质量筛选：仅保留有 sub-agent 调用的主 session（<sid>.jsonl 必须有对应 <sid>/ 子目录）
  - 内容精简：每个 batch 平铺 <sid>.jsonl + <sid>/ 子树，不带 <encoded_cwd>/、不带 .tmp/ 等
  - 平铺：去掉了 <encoded_cwd>/ 中间层，所有 <sid>.jsonl 和 <sid>/ 直接落在 batch_NN/ 下
  - 同名 sid 去重：同一个 sid 在不同 workspace 下只保留首次出现的那个（避免冲突）
  - 最小不可拆单元 = <sid>.jsonl + <sid>/ 子树
  - 走标准 shutil.copytree，保留元数据
  - 重新跑安全：每个 batch 目录会先 rmtree 再重建
  - 中文按 utf-8 输出，stdout + 日志双写
  - 兼容 Python 3.6+（无 from __future__ / 无 PEP 604 类型注解）
"""
import argparse
import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

# 默认路径
DEFAULT_SRC = Path("/home/10358563/viking_all_session")
DEFAULT_DST = DEFAULT_SRC / "SEE"
TARGET_AGENTS = (
    "需求分析Agent",
    "系统方案设计Agent",
    "子系统设计Agent",
    "组件设计Agent",
)

# 默认 batch 上限（jsonl 数）
DEFAULT_MAX_SESSIONS_PER_BATCH = 30

# 拷贝时跳过的中间产物目录/文件
SKIP_NAMES = {".tmp"}


def extract_cwd_basename(jsonl_path):
    """读 jsonl 第一条 user 消息顶层 cwd 字段，返回 basename。无 user 消息或解析失败返 None。"""
    try:
        with jsonl_path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "user":
                    cwd = obj.get("cwd") or ""
                    if cwd:
                        return Path(cwd).name
                    return None
    except OSError:
        pass
    return None


def has_subagent_call(sub_dir, sid):
    """判断 <sid>.jsonl 对应的 <sid>/ 子目录是否存在（即主 session 是否召唤过 sub-agent）。"""
    return (sub_dir / sid).is_dir()


def pass1_scan(args, log):
    """Pass 1: 扫描源，按 (agent, sid) 聚合 jsonl。

    Pass 1.5: 质量筛选 —— 对每个 jsonl 检查同名 <sid>/ 子目录是否存在，
              不存在则丢弃（没召唤过 sub-agent 的 session 无分析价值）。
              同名 sid 在不同 <encoded_cwd>/ 下只保留首次出现的那个（去重）。

    返回:
      sid_sources: {(agent, sid): [(jsonl_path, subagent_dir_path), ...]}
      stats_count: {agent: total_jsonls}
      dropped_no_subagent: 丢弃数（无 sub-agent 调用）
      dropped_dup_sid: 同名 sid 重复丢弃数
    """
    sid_sources = defaultdict(list)  # (agent, sid) -> [(jsonl, sid_subdir), ...]
    seen_dirs = set()
    scanned_dirs = 0
    scanned_jsonl = 0
    stats_count = defaultdict(int)
    dropped_no_subagent = 0
    dropped_dup_sid = 0

    log("[pass1] src=" + str(args.src) + "  dry_run=" + str(args.dry_run))

    for sid_dir in sorted(args.src.iterdir()):
        if sid_dir.name == args.dst.name:
            continue  # 跳过输出目录本身
        if not sid_dir.is_dir():
            continue
        projects = sid_dir / "projects"
        if not projects.is_dir():
            continue
        for sub in sorted(projects.iterdir()):
            if not sub.is_dir():
                continue
            key = (sid_dir.name, sub.name)
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            scanned_dirs += 1

            jsonls = sorted(sub.glob("*.jsonl"))
            if not jsonls:
                continue
            sample = jsonls[0]
            scanned_jsonl += 1
            base = extract_cwd_basename(sample)

            if base not in TARGET_AGENTS:
                continue

            # Pass 1.5: 质量筛选 + 去重
            for jl in jsonls:
                sid_of_jsonl = jl.stem
                sid_subdir = sub / sid_of_jsonl
                if not sid_subdir.is_dir():
                    dropped_no_subagent += 1
                    continue

                # 同名 sid 去重：只保留首次出现的
                key2 = (base, sid_of_jsonl)
                if sid_sources.get(key2):
                    dropped_dup_sid += 1
                    continue

                sid_sources[key2].append((jl, sid_subdir))
                stats_count[base] += 1

    log("[pass1 done] scanned_dirs=" + str(scanned_dirs) +
        "  scanned_jsonl_for_cwd=" + str(scanned_jsonl) +
        "  kept_sids=" + str(len(sid_sources)) +
        "  dropped_no_subagent=" + str(dropped_no_subagent) +
        "  dropped_dup_sid=" + str(dropped_dup_sid))
    for a in TARGET_AGENTS:
        log("  " + a + ": " + str(stats_count[a]) + " jsonls in " +
            str(sum(1 for k in sid_sources if k[0] == a)) + " sids")

    return sid_sources, stats_count, scanned_dirs, scanned_jsonl, dropped_no_subagent, dropped_dup_sid


def greedy_pack(sid_subs_for_agent, batch_limit):
    """对单个 agent 做贪心装箱。

    sid_subs_for_agent: [(sid, total_jsonl_count), ...]
    返回: {sid: batch_id_str}, batch_plan: [{batch_id, count, sids}]
    """
    sorted_sids = sorted(sid_subs_for_agent, key=lambda x: -x[1])
    overflow = [(sid, c) for sid, c in sorted_sids if c > batch_limit]
    normal = [(sid, c) for sid, c in sorted_sids if c <= batch_limit]

    bins = []
    bin_idx = 0

    def new_bin():
        nonlocal bin_idx
        b = {"id": "batch_" + str(bin_idx).zfill(2), "count": 0, "sids": []}
        bins.append(b)
        bin_idx += 1
        return b

    # 超大 sid 单独成 batch
    for sid, c in overflow:
        b = new_bin()
        b["count"] = c
        b["sids"].append(sid)

    # 贪心：每个 sid 塞当前 count 最小且 + c 不超阈值的 bin
    for sid, c in normal:
        target = None
        for b in bins:
            if b["count"] + c <= batch_limit:
                if target is None or b["count"] < target["count"]:
                    target = b
        if target is None:
            target = new_bin()
        target["count"] += c
        target["sids"].append(sid)

    mapping = {}
    for b in bins:
        for sid in b["sids"]:
            mapping[sid] = b["id"]
    return mapping, bins


def copy_slim(src, dst, log):
    """精简拷贝：跳过 SKIP_NAMES 里的中间产物目录。

    src/dst 都是 Path。dst 不存在会被创建。
    """
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in SKIP_NAMES:
            continue
        target = dst / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, ignore=shutil.ignore_patterns(*SKIP_NAMES))
        else:
            shutil.copy2(entry, target)


def pass2_copy(args, log, sid_sources, batches_plan):
    """Pass 2: 按 (agent, sid) -> batch_id 映射表，平铺拷每个 <sid>.jsonl + 它对应的 <sid>/ 子树
    到 <dst>/<Agent>/batch_NN/<sid>.jsonl 和 <dst>/<Agent>/batch_NN/<sid>/

    不同 <encoded_cwd>/ 下的同名 sid 在 Pass 1.5 已去重，所以这里每个 sid 只拷一次。
    """
    log("[pass2] flatten copy to <dst>/<Agent>/batch_NN/<sid>.jsonl + <sid>/  (skip: " +
        ",".join(sorted(SKIP_NAMES)) + ")")

    # 准备 batch 目录
    if not args.dry_run:
        for agent, plan in batches_plan.items():
            agent_dir = args.dst / agent
            if agent_dir.exists():
                shutil.rmtree(agent_dir)
            agent_dir.mkdir(parents=True, exist_ok=True)
            for b in plan:
                (agent_dir / b["batch_id"]).mkdir(exist_ok=True)

    copied_files = 0
    copied_dirs = 0
    for (agent, sid), sources in sid_sources.items():
        batch_id = None
        for b in batches_plan.get(agent, []):
            if sid in b["sids"]:
                batch_id = b["batch_id"]
                break
        if batch_id is None:
            log("  [WARN] no batch assigned for " + agent + "/" + sid)
            continue

        # sources: [(jsonl_path, sid_subdir_path), ...]，Pass 1.5 已保证只一项
        for jsonl_path, sid_subdir_path in sources:
            if args.dry_run:
                log("  [DRY] " + agent + "/" + batch_id + "/" + sid +
                    ".jsonl  (from " + jsonl_path.parent.name + "/)")
                continue

            dst_batch_dir = args.dst / agent / batch_id
            # 拷贝主 session jsonl
            shutil.copy2(jsonl_path, dst_batch_dir / jsonl_path.name)
            copied_files += 1
            # 拷贝 <sid>/ 子树（跳过 SKIP_NAMES）
            shutil.copytree(
                sid_subdir_path, dst_batch_dir / sid,
                ignore=shutil.ignore_patterns(*SKIP_NAMES),
            )
            copied_dirs += 1

    log("[pass2 done] copied " + str(copied_files) + " jsonls + " +
        str(copied_dirs) + " sub-agent dirs")


def main():
    parser = argparse.ArgumentParser(
        description="一次性脚本：viking_all_session -> SEE/<Agent>/batch_NN/ (Agent × Batch 贪心装箱 + 质量筛选)",
    )
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC,
                        help="viking_all_session 根目录")
    parser.add_argument("--dst", type=Path, default=DEFAULT_DST,
                        help="输出目录")
    parser.add_argument("--dry-run", action="store_true",
                        help="只统计 + 装箱，不拷贝")
    parser.add_argument("--summary", action="store_true",
                        help="结束时按 agent 打印 jsonl 数 + batch 数 + 丢弃数")
    parser.add_argument("--max-sessions-per-batch", type=int,
                        default=DEFAULT_MAX_SESSIONS_PER_BATCH,
                        help="每个 batch 的 jsonl 数上限（默认 " +
                        str(DEFAULT_MAX_SESSIONS_PER_BATCH) + "）")
    args = parser.parse_args()

    if not args.src.is_dir():
        print("ERROR: src 目录不存在: " + str(args.src), file=sys.stderr)
        return 1

    args.dst.mkdir(parents=True, exist_ok=True)
    log_path = args.dst / "select_sessions.log"
    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log("[start] src=" + str(args.src) + "  dst=" + str(args.dst) +
        "  dry_run=" + str(args.dry_run) +
        "  max_per_batch=" + str(args.max_sessions_per_batch))

    t0 = time.time()

    # Pass 1 + 1.5
    sid_sources, stats_count, scanned_dirs, scanned_jsonl, dropped_no_sub, dropped_dup = \
        pass1_scan(args, log)

    # 贪心装箱：每个 (agent, sid) 算 1 个 jsonl（平铺后 sid 即最小单元）
    batch_limit = args.max_sessions_per_batch
    log("[pack] greedy first-fit-decreasing, limit=" + str(batch_limit))
    batches_plan = {}
    for agent in TARGET_AGENTS:
        sids = [sid for (a, sid) in sid_sources if a == agent]
        sid_count_pairs = [(sid, 1) for sid in sids]  # 平铺：每个 sid 算 1 个
        _, bins = greedy_pack(sid_count_pairs, batch_limit)
        batches_plan[agent] = [{
            "batch_id": b["id"],
            "sid_count": len(b["sids"]),
            "sids": b["sids"],
        } for b in bins]
        total_sids = sum(x["sid_count"] for x in batches_plan[agent])
        avg = round(total_sids / max(1, len(bins)), 1)
        log("  " + agent + ": " + str(len(bins)) + " batches, " +
            str(total_sids) + " sids, avg=" + str(avg))

    # Pass 2
    pass2_copy(args, log, sid_sources, batches_plan)

    # 写 manifest
    summary_by_agent = {a: stats_count[a] for a in TARGET_AGENTS}
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "src": str(args.src),
        "dst": str(args.dst),
        "target_agents": list(TARGET_AGENTS),
        "summary_by_agent": summary_by_agent,
        "total_kept_sids": len(sid_sources),
        "total_dropped_no_subagent": dropped_no_sub,
        "total_dropped_dup_sid": dropped_dup,
        "scanned_dirs": scanned_dirs,
        "scanned_jsonl_for_cwd": scanned_jsonl,
        "max_sessions_per_batch": batch_limit,
        "batches": batches_plan,
        "elapsed_sec": round(time.time() - t0, 2),
    }

    if not args.dry_run:
        manifest_path = args.dst / "select_sessions.manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log("[manifest] " + str(manifest_path))

        batches_path = args.dst / "select_sessions.batches.json"
        batches_path.write_text(
            json.dumps(batches_plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log("[batches ] " + str(batches_path))

        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        log("[log]      " + str(log_path))

    log("[done] elapsed=" + str(manifest["elapsed_sec"]) + "s")
    if args.summary:
        log("[summary]")
        log("  total_kept_sids: " + str(len(sid_sources)) +
            "  dropped_no_subagent: " + str(dropped_no_sub) +
            "  dropped_dup_sid: " + str(dropped_dup))
        for a in TARGET_AGENTS:
            plan = batches_plan.get(a, [])
            log("  " + a + ": " + str(summary_by_agent.get(a, 0)) +
                " jsonls / " + str(len(plan)) + " batches / " +
                str(sum(x["sid_count"] for x in plan)) + " sids")
    return 0


if __name__ == "__main__":
    sys.exit(main())