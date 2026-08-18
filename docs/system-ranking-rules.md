# 系统后端排序与 TOP6 评分规则

版本：v2.0  
面向对象：系统后端工程师  
适用范围：每日 18:30 采集大事件完成后的内容排序、首页 TOP6 生成  
相关文档：`system-engineer-requirements.md`、`crawler-api-contract.md`

## 1. 目标与边界

系统后端在每次采集大事件完成后，对该批次成功入库的 `items` 进行确定性评分，按分数生成当天首页 TOP6。

本规则必须满足：

- **不调用 LLM**：评分代码不得调用任何大模型接口。
- **不读取或理解摘要正文**：不得根据 `title`、`summary`、`content_excerpt` 的语义临时判断分数。
- **只使用结构化字段**：`event_type`、`category`、`source_name`、`published_at`、批次完成时间和适用的 GitHub metadata/metrics。
- **缺失非通用指标不扣分**：没有 Trending 排名、Star 增量、Fork 增量的内容，其“社区热度”应为 `null`（不适用），不能按 0 分参与扣减。
- **可回放、可解释**：每条内容必须保存总分、各维度得分、规则版本和入选原因。
- **历史固化**：日报生成后，当天 TOP6 及其分数快照不随未来规则修改而变化。

说明：爬虫端可借助 LLM 生成摘要、分类、事件类型等字段；系统端仅信任并使用这些已返回的结构化字段进行规则计算，不再调用 LLM。

## 2. 计算时机与候选范围

```text
18:30 采集大事件结束
  -> 保存所有成功/部分成功响应中的 items
  -> 仅取本次 crawl_batch 的可展示 items 作为候选
  -> 按本规则计算分数
  -> 排序、生成 TOP6、立即发布
  -> 固化 daily_report 与 daily_report_items
```

候选条件：

| 条件 | 要求 |
|---|---|
| 所属批次 | `crawl_batch_id` 为当前采集大事件。 |
| 处理状态 | `processing_status` 为可展示状态；失败或无原始链接的 item 不参加 TOP6。 |
| 内容窗口 | 由爬虫端保证为昨天 18:30 至今天 18:30 的新增内容；系统不再以摘要文本二次判断。 |
| 数量 | 0 条显示“今日暂无消息”；1-6 条均入选；超过 6 条按排序取前 6 条。 |

## 3. 总分公式

```text
基础分 = 事件重要性（0-40）+ 分类相关性（0-20）+ 时效性（0-15）+ 信源权威性（0-15）
最终分 = 基础分 + GitHub 社区热度加分（0-10，仅适用时参与）
```

基础分满分 90 分，所有内容均可计算。社区热度最多加 10 分，仅用于具备对应数据的 GitHub 内容，不适用时不加不减。

### 3.1 事件重要性：0-40 分

读取字段：`event_type`。

| `event_type` | 分数 | 说明 |
|---|---:|---|
| `security_issue` | 40 | 安全漏洞、安全公告、修复。 |
| `breaking_change` | 35 | 不兼容变更、弃用、迁移要求。 |
| `major_feature` | 30 | 重大能力或核心功能发布。 |
| `release` | 28 | 正式版本发布。 |
| `model_update` | 25 | 模型版本、能力或可用性更新。 |
| `product_update` | 20 | 产品或平台常规更新。 |
| `repo_metric_change` | 12 | 仓库指标变化信息。 |
| `community_activity` | 10 | Trending、社区活跃或生态动态。 |
| `research` / `tutorial` | 8 | 研究或教程。 |
| `opinion` / `other` / 空值 | 5 | 其他信息。 |

### 3.2 分类相关性：0-20 分

读取字段：`category`。

| `category` | 分数 |
|---|---:|
| `核心 Agent runtime 更新` | 20 |
| `金融 AI 产品与技术` | 17 |
| `GitHub 上升项目` | 15 |
| `大模型产品与平台` | 13 |
| `Agent 产品与应用` | 12 |
| `其他` / 空值 / 未识别值 | 6 |

### 3.3 时效性：0-15 分

读取字段：`published_at`，比较基准为当前 `crawl_batch.finished_at`；均使用 Asia/Shanghai 时区。缺失或无法解析发布时间时取 5 分，不得因数据源未提供精确发布时间而排除内容。

| 发布时间距批次完成时间 | 分数 |
|---|---:|
| 0-6 小时 | 15 |
| 大于 6 小时至 12 小时 | 12 |
| 大于 12 小时至 24 小时 | 9 |
| 大于 24 小时 | 6 |
| `published_at` 缺失或不可用 | 5 |

若 `published_at` 晚于 `finished_at`，按 0-6 小时处理，并记录数据异常日志（不阻断发布）。

### 3.4 信源权威性：0-15 分

读取字段：`source_name`。此分数由系统的固定配置表维护，不能由 LLM 决定。

| `source_name` | 分数 | 说明 |
|---|---:|---|
| `openai_codex_changelog` | 15 | 官方产品更新日志。 |
| `github_codex` / `github_pi_agent` / `github_hermes` / `github_opencode` | 14 | 项目官方 GitHub 仓库。 |
| `github_trending` | 8 | GitHub 趋势榜，适合发现项目，但不是项目官方公告。 |
| 未来新增的已认证官方信源 | 12-15 | 由系统配置明确设置。 |
| 未配置或未知信源 | 5 | 保底值，并记录配置告警。 |

### 3.5 GitHub 社区热度加分：0-10 分（可选）

仅当 item 属于 GitHub 相关内容，且当前批次中存在可用热度数据时计算。适用内容包括：

- `source_name = github_trending`，且 `metadata.trending_rank` 存在；
- GitHub 仓库内容，且可从当前与上一次指标快照得到 `stars` 或 `forks` 增量。

其他内容的 `community_heat_score` 写入 `null`，`community_heat_applicable = false`。

热度加分取以下**已获得项中的最高值**，不累加，避免同一项目因多个指标重复抬分：

| 可用条件 | 社区热度加分 |
|---|---:|
| Trending 排名 1-3 | 10 |
| Trending 排名 4-10 | 8 |
| Trending 排名大于 10 | 5 |
| 当前批次 Star 增量位于同批次 GitHub 仓库前 20% | 8 |
| 当前批次 Star 增量位于前 50% | 5 |
| 当前批次 Fork 增量位于前 20%，且无可用 Star 增量 | 4 |
| 有 GitHub 热度数据但不满足上述条件 | 2 |

实现约束：

- Star/Fork 增量 = 当前指标快照 - 同一 `source_name` 最近一次历史快照。
- 无历史快照、快照缺字段或增量小于等于 0 时，不计算对应增量排名。
- 热度比较只在当前 `crawl_batch` 内、具备同类指标的 GitHub 候选中进行；样本少于 3 条时不计算百分位，只可使用 Trending 排名或保底 2 分。
- `watchers`、`subscribers`、`open_issues` 第一阶段仅存储和可视化，不参与 TOP6 分数。

## 4. 排序、同分与首页多样性规则

排序键依次为：

```text
1. final_score 降序
2. event_impact_score 降序
3. published_at 降序（缺失值排后）
4. item.created_at 降序
5. item.id 升序（保证结果稳定）
```

首页多样性限制：

- 同一个 `source_name` 最多入选 2 条。
- 第一轮选择时，同一个 `category` 最多入选 2 条，避免单一类别占满首页。
- 如果第一轮不足 6 条，再按原排序补足剩余位置，此时只继续保留 `source_name` 最多 2 条限制。

此规则只改善首页展示结构，不代表去重或跨信源归并。

## 5. 入库字段与数据模型要求

在 `items` 表增加或确认以下字段：

| 字段 | 类型建议 | 必填 | 说明 |
|---|---|---:|---|
| `ranking_score` | numeric(5,2) | 是 | 最终分，范围 0-100。 |
| `ranking_version` | varchar(32) | 是 | 当前固定写入 `v2`。 |
| `event_impact_score` | smallint | 是 | 事件重要性得分，范围 5-40。 |
| `category_relevance_score` | smallint | 是 | 分类相关性得分，范围 6-20。 |
| `freshness_score` | smallint | 是 | 时效性得分，范围 5-15。 |
| `source_authority_score` | smallint | 是 | 信源权威性得分，范围 5-15。 |
| `community_heat_score` | smallint | 否 | 热度加分，`null` 表示不适用，范围 0-10。 |
| `community_heat_applicable` | boolean | 是 | 是否属于可计算社区热度的 GitHub 内容。 |
| `score_breakdown` | jsonb | 是 | 各维度、命中规则和输入字段快照，用于排查和展示。 |
| `selection_reason` | varchar(255) | 否 | 仅当进入 TOP6 时填写简短规则说明。 |

在 `daily_report_items` 中保存 `item_id`、`rank`、`ranking_score_snapshot`、`score_breakdown_snapshot`、`selection_reason_snapshot`，使历史日报保持不可变。

`score_breakdown` 示例：

```json
{
  "event_impact": 30,
  "category_relevance": 20,
  "freshness": 12,
  "source_authority": 14,
  "community_heat": null,
  "community_heat_applicable": false,
  "final_score": 76,
  "rules": {
    "event_type": "major_feature",
    "category": "核心 Agent runtime 更新",
    "source_name": "github_codex"
  }
}
```

## 6. 异常与降级

| 场景 | 系统行为 |
|---|---|
| `event_type` 或 `category` 不在枚举内 | 使用表中的保底分，并记录 warn 日志。 |
| `published_at` 缺失/解析失败 | 时效性取 5 分，仍可展示和参与排序。 |
| GitHub 热度字段不存在 | 写入 `community_heat_score = null`，不影响基础分。 |
| 当前批次无候选内容 | 不生成 TOP6 内容，首页显示“今日暂无消息”。 |
| 排序计算错误 | 记录 error 日志；该批次可按 `published_at` 降序降级生成首页列表，同时标记日报为 `degraded`。 |

## 7. 验收标准

| 验收项 | 标准 |
|---|---|
| 无 LLM 调用 | TOP6 计算过程不产生任何模型 API 请求。 |
| 不适用热度 | OpenAI Changelog 等非 GitHub 内容的 `community_heat_score` 为 `null`，不会被按 0 分扣减。 |
| 可解释 | 每个入库 item 可查询完整 `score_breakdown`。 |
| 可重现 | 同一批次、同一输入和同一规则版本，多次执行的排序一致。 |
| 多样性 | 单一 `source_name` 在首页 TOP6 中最多出现 2 条。 |
| 固化历史 | 修改未来规则不会改变已生成日报的排名及评分快照。 |
| 边界数量 | 0、1-6、超过 6 条候选内容均按规则正确生成首页。 |

## 8. 版本演进

第一阶段不做去重、跨信源归并，也不引入 LLM 评分。后续若调整权重或增加维度，必须新建规则版本（如 `v3`），禁止覆盖解释历史日报的旧版本快照。
