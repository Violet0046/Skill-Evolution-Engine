-- ============================================================
-- see_review_decision
-- ------------------------------------------------------------
-- 评审人对每条 change 的所有动作。事件溯源: 一行 = 一次动作。
--
-- 决策枚举:
--   approved  -> 直接替换原 skill (走落地回路修改 subjects/<project>/<target_file>)
--   modified  -> 先按 modified_content 人工修改后再替换
--   rejected  -> 拒绝这次进化
--
-- 设计要点:
--   - 同一 change 可被多人评审, 同时记录多行
--   - 同一评审人改主意也可记多行 (event-sourced)
--   - 最新的"有效"评审 = ORDER BY reviewed_at DESC
-- ============================================================

CREATE TABLE IF NOT EXISTS see_review_decision (
    id                  BIGINT       NOT NULL AUTO_INCREMENT,

    -- 关联到 004 (评审主体)
    evolution_change_id BIGINT       NOT NULL,           -- FK -> see_evolution_change.id

    -- 一次动作
    decision            ENUM('approved','modified','rejected') NOT NULL,
    comment             TEXT         NULL,               -- 评审人说明
    modified_content    LONGTEXT     NULL,               -- 仅 modified 时填

    -- 谁 + 何时 (你强调的: 多评审人同时记录)
    reviewer            VARCHAR(64)  NOT NULL,           -- 用户标识
    reviewed_at         DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    PRIMARY KEY (id),
    -- 这里不加 UNIQUE (reviewer, evolution_change_id): 允许同人改主意记多次
    KEY idx_change        (evolution_change_id, reviewed_at DESC),
    KEY idx_reviewer      (reviewer, reviewed_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci COMMENT='评审动作流水 (事件溯源)';
