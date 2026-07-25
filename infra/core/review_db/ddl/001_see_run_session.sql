-- ============================================================
-- see_run_session
-- ------------------------------------------------------------
-- 一次运行 (run_id) 处理的每个 session 的入口记录。
-- .index 是已经由阶段 1 处理过的结构化分类文件
-- （summary / by_agent_type / agent_cwd 等），
-- 直接照其结构入库：3 个高频字段结构化 + 1 个原始 JSON 兜底。
--
-- 业务唯一键 = (run_id, session_id)。session_id 本身是 UUID，已经
-- 等价于一个 hash，所以此处不再额外存 index_sha256。
-- "证据源指纹" 改为在下游 see_run_suggestion / see_evolution_change
-- 层用 evidence_uuids[] 集合的算法相似度在线计算。
-- ============================================================

CREATE TABLE IF NOT EXISTS see_run_session (
    id              BIGINT       NOT NULL AUTO_INCREMENT,

    -- 业务键
    run_id          VARCHAR(64)  NOT NULL,           -- 例: 2026-07-20-161903
    session_id      VARCHAR(64)  NOT NULL,           -- 例: 5527b413-affc-443e-862f-15ff6bb3f7d1

    -- .index 的高频查询字段（结构化）
    agent_cwd       JSON         NULL,               -- {"main": "/path", ...}
    by_agent_type   JSON         NULL,               -- {"general-purpose": {...}}
    summary         TEXT         NULL,               -- 摘要原文

    -- 兜底：原始 .index 内容（不建索引，参与查询仅用于回溯/重算）
    index_raw       JSON         NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_run_session (run_id, session_id),
    KEY idx_run_id       (run_id),
    KEY idx_session_id   (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci COMMENT='一次 run 处理的每个 session 入口记录（含 .index 内容）';
