-- ============================================================
-- see_evidence
-- ------------------------------------------------------------
-- 阶段 2 调用 failure_analyzer detail 工具的原始结果。
-- 见用户决策 2026-07-25:
--   - detail 入参是 (session_id, uuid), 跨 run 结果稳定, 所以无 run_id
--   - 钩子时机: sub-agent 执行 detail 工具时即时入库
--   - 前端查证据链路: suggestion.evidence_uuids[] -> 本表
--
-- 存储策略: detail 整段 JSON, 因为 detail 内部 schema 复杂且仍在演化,
-- 不拆字段. 唯一键 (session_id, uuid) 保证入库幂等.
-- ============================================================

CREATE TABLE IF NOT EXISTS see_evidence (
    id              BIGINT       NOT NULL AUTO_INCREMENT,

    -- 业务键: 跨 run 唯一 (detail 工具入参就是这两个)
    session_id      VARCHAR(64)  NOT NULL,        -- 例: 5527b413-affc-443e-862f-15ff6bb3f7d1
    uuid            VARCHAR(128) NOT NULL,        -- sub-agent detail 工具返回的稳定 id

    -- detail 完整结果 (结构待定, 当前整段存)
    detail_json     JSON         NOT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_session_uuid (session_id, uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci COMMENT='detail 工具的原始结果，按 (session_id, uuid) 幂等';
