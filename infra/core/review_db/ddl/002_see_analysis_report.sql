-- ============================================================
-- see_analysis_report
-- ------------------------------------------------------------
-- 阶段 2 产物 .analysis_report.json 的"按 (subject_name, target_file) 预聚合"
-- 但是同一 session 内的预聚合。
--
-- 业务键: (run_id, session_id, subject_target) 一行
--   - subject_target = subject_name + "@" + target_file  (拼成一个字段)
--   - 因为这俩在业务上总是成对使用, 合并便于索引和去重
--
-- 设计要点:
--   - 每行存的是同一 (run_id, session_id, subject, target) 下的多条 suggestion
--     (组成一个数组, 每元素含 description / rationale / evidence_uuids 等)
--   - evidence_uuids 不能在这里拍平——因为同一 subject_target 可能涉及多个
--     建议, 每条建议引用不同的证据, 拍平会污染真实证据圈
--   - 跨 session 的聚合留给 see_evolution_change (同一个 (run_id, subject_target)
--     会在不同 session 各有一行 analysis_report, 但 change 是一个)
--
-- 这一表对应阶段 3 的 evolve 需要的"按 session 划分的种子食材"
-- 而 discover 阶段需要的是"跨 session 的聚合"——那是 003 的事
-- ============================================================

CREATE TABLE IF NOT EXISTS see_analysis_report (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,

    -- 业务键
    run_id              VARCHAR(64)  NOT NULL,
    session_id          VARCHAR(64)  NOT NULL,
    subject_target      VARCHAR(600) NOT NULL,    -- '<subject_name>@<target_file>' (utf8mb4 下与 64+64 复合唯一键总长不超 3072 字节)

    -- 预聚合的 suggestions (同一 subject_target 下可能有 N 条)
    -- 元素结构: {
    --   "priority": "high|medium|low",
    --   "category": "...",
    --   "description": "...",
    --   "rationale": "...",
    --   "suggested_text": "...",
    --   "evidence_uuids": ["uuid-1", "uuid-2", ...]   ← 每条建议独立保留, 不拍平
    -- }
    suggestions_json    JSON         NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_run_session_target (run_id, session_id, subject_target),
    KEY idx_run_subject_target (run_id, subject_target),
    KEY idx_session_id         (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci COMMENT='阶段 2 产物, 按 (run_id, session_id, subject_target) 预聚合';
