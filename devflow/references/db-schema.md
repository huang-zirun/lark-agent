---
name: db-schema
title: 数据库 Schema 设计原则
description: 基于 SQL Style Guide 和 Flyway Best Practices 的数据库设计规范
tags: [database, schema, migration]
version: "1.0"
applicable_stages: [solution_design]
priority: 4
---

## 概述

数据库 Schema 是系统最难变更的部分之一，设计不当将长期影响性能与可维护性。本参考综合 SQL Style Guide、Flyway/Liquibase Migration Best Practices 及业界通用实践，定义 Schema 设计与迁移管理的标准规范。

## 命名规范

| 对象 | 规则 | 示例 |
|---|---|---|
| 表名 | snake_case 复数 | `user_accounts` |
| 列名 | snake_case | `created_at` |
| 主键 | `{table_singular}_id` | `user_account_id` |
| 外键 | `{referenced_singular}_id` | `order_id` |
| 索引 | `idx_{table}_{columns}` | `idx_orders_user_id_status` |
| 唯一约束 | `uk_{table}_{columns}` | `uk_users_email` |
| 检查约束 | `ck_{table}_{condition}` | `ck_orders_amount_positive` |

## 主键策略

- 优先使用 `BIGINT` 自增主键（性能最优，索引紧凑）
- 分布式场景使用 UUID v7（时间排序 + 唯一性）
- 禁止使用业务字段作为主键
- 主键列名统一为 `{表名单数}_id`

## 范式与反范式平衡

- 默认遵循第三范式（3NF），消除冗余与更新异常
- 读多写少的查询场景可适度反范式化（Denormalization），添加冗余字段减少 JOIN
- 反范式化必须通过注释说明原因，并在应用层保证一致性

## 索引设计

- WHERE、JOIN、ORDER BY 高频列建索引
- 联合索引遵循最左前缀原则，高选择性列在前
- 单表索引数建议 ≤ 5 个，避免写入性能退化
- 覆盖索引（Covering Index）优化高频查询
- 定期审查未使用索引并清理

## 数据类型选择

| 场景 | 推荐类型 | 避免 |
|---|---|---|
| 金额 | `DECIMAL(19,4)` | FLOAT/DOUBLE |
| 布尔 | `BOOLEAN` | TINYINT(1) |
| 时间戳 | `TIMESTAMP WITH TIME ZONE` | DATETIME |
| 短字符串 | `VARCHAR(n)` | CHAR(n) |
| 长文本 | `TEXT` | VARCHAR(65535) |
| JSON | `JSONB`（PostgreSQL） | TEXT 存储 JSON |

## 审计列与软删除

每张业务表必须包含审计列：

- `created_at TIMESTAMP NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMP NOT NULL DEFAULT NOW()`
- `created_by VARCHAR(64)`
- `updated_by VARCHAR(64)`

软删除使用 `deleted_at TIMESTAMP NULL`，查询默认过滤 `WHERE deleted_at IS NULL`。

## 迁移管理

- 使用 Flyway/Liquibase 管理迁移脚本
- 命名格式：`V{version}__{description}.sql`（如 `V001__create_user_accounts.sql`）
- 迁移脚本必须向前兼容（只增不删/改列）
- 破坏性变更分多步执行：先加新列 → 迁移数据 → 再删旧列
- 每次迁移必须有对应的 Rollback 方案

## Agent 使用指引

1. **DDL 生成**: 根据领域模型自动生成建表 DDL，包含审计列、索引建议与约束定义。
2. **命名一致性检查**: 扫描现有 Schema，检测不符合命名规范的表、列、索引并标注。
3. **索引建议**: 分析查询模式，建议缺失索引或冗余索引。
4. **迁移脚本生成**: 对比 Schema 变更，生成向前兼容的迁移脚本与 Rollback 方案。
