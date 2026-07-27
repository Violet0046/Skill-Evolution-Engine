-- ============================================================
-- see_evolution_change
-- ------------------------------------------------------------
-- 阶段 3 产物 .change 文件的入口记录。
-- 一行 = 一个 .change, 跟 (run_id, subject_target) 一一对应。
--
-- 字段 3 块:
--   (1) 业务键 (run_id, subject_target)
--   (2) 产物快照 original_content + new_content (评审前端做 diff)
--   (3) 推动它的 suggestions (evolver 实际发的那份)
--
-- 评审反馈字段 (approved/modified/rejected + comment) 放在
-- see_review_decision 表 (事件溯源, 另开).
-- ============================================================

CREATE TABLE IF NOT EXISTS see_evolution_change (
    id                      BIGINT       NOT NULL AUTO_INCREMENT,

    -- (1) 业务键
    run_id                  VARCHAR(64)  NOT NULL,
    subject_target          VARCHAR(700) NOT NULL,        -- '<subject_name>@<target_file>'

    -- (2) 产物快照 (评审前端做 diff)
    --    LONGTEXT 上限 4 GB, 单个 md 文件 (< 200 KB) 远低于此
    original_content        LONGTEXT     NOT NULL,        -- 原 subjects/<project>/<target_file>
    new_content             LONGTEXT     NULL,            -- evolver 写完后立刻填

    -- (3) 推动它的 suggestions (evolver 实际收到的那份)
    --     元素保留 id / priority / direction / rationale / evidence_uuids,
    --     前端点击 suggestion.id 直接反查 002 / 003
    suggestions_json        JSON         NOT NULL,

    -- (4) 预计算 diff (Python difflib 在阶段 3 末算一次存)
    --     { leftLines: [{lineNo, text, kind}], rightLines: [...], added, removed }
    --     前端拿到直接渲染, 不再前端算算法
    linediff_json           JSON         NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uk_run_subject_target (run_id, subject_target)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci COMMENT='阶段 3 产物 .change（评审系统的核心表）';
