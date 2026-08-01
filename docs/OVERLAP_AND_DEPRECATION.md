# 重叠与弃用清单

更新时间：2026-08-02。本文只做盘点和低风险决策建议；高风险删除/迁移需要维护者确认。

| 冲突/冗余 | 决策建议 | 本窗口动作 | 影响面与理由 |
|---|---|---|---|
| `frontend/app.js` 与 `desktop/app.js` 双前端真源 | 合并到单一生成源，短期保留 desktop 派生副本 | 保留，记录为未完成治理 | 两者近乎字节级相同，人工同步会让安全修复漂移。 |
| `Kylian_Mbappe-Lottin.json` 与 `Kylian_Mbappé.json` profile 变体 | 以 `Kylian_Mbappé.json` 为静态 profile 真源，旧 slug 仅作 deprecated alias | 主前端 `_staticUrlFor` 已归一到新 slug；旧文件暂不删除 | 变体名称不能继续产生两个静态详情入口；rating entity 是否合并仍由 canonical registry 决定。 |
| Streamlit、静态前端、FastAPI、Electron 四个产品面 | 保留 FastAPI + 主静态前端；Streamlit/Electron 逐步标注适配边界 | 保留，未删除 | 直接删除会扩大回归面；本地优先需要先明确主链路。 |
| Render/Vercel/Cloudflare 配置与 local-first 章程 | 弃用默认公共部署假设；配置保留为手动/历史发布路径 | 本地开发不触发云端 | 公共 URL、静态快照和本地事实源不能混称。 |
| `player_ratings.parquet`、`v2`、`v3`、`optimized` 与 `data/models/runs/` | `player_ratings_optimized.parquet` 暂作兼容 active artifact；run 目录作为可审阅候选证据 | 主评分链路仍 fail-closed；未删产物 | 评分文件的唯一事实源尚未通过模型准入，不能贸然删除旧文件。 |
| 新增球队积分 MLP 候选与现有优化器 | 两者并行作为候选实验；不自动替换 active rating | 已完成一次时间外 holdout；候选 run 保持 `not_activated` | MLP 优化的是球队赛季积分代理回归，不是独立球员能力；需独立标签、覆盖修复和相同切分比较后才可讨论晋级。 |
| `requirements.txt` 与 `pyproject.toml`/`uv.lock` | `pyproject.toml` + `uv.lock` 为声明真源；requirements 仅作为手工 Streamlit 派生清单 | 当前注释已无乱码；未删除 | 删除 requirements 可能破坏现有手工部署；后续应自动生成。 |
| `frontend/data/value_summary.json` synthetic 与 `/market-value/*` 真实本地 API | `/market-value/*` 为 market value 主链路；synthetic value summary 弃用为展示数据 | 已接入 market value；拒绝 synthetic fallback | 避免把匿名 Player A/B/C 说成真实身价。 |
| `predictions_default.json` 与 prediction API | 弃用默认预测文件 | 已移除前端默认预测 fallback | API 不可达时必须显示无数据，而不是 generic prediction。 |
| `.bak-20260605044151` 备份文件 | 删除 git 中的 6 个备份文件 | 已执行并核对 0 个残留 | 备份已被审计列为仓库体积污染；若仍需要应从 Git 历史恢复到 git 外部备份。 |
| 未合并 `codex/*` ×13、`solo/*` ×3、`local/*` ×2 分支 | 归档或删除 | 已按维护者明确指令删除 18 个本地分支；仅保留 `main` | 分支均无工作树；删除前核对了 tip、远端 `gone` 状态和 `main` 祖先关系；未执行远端删除或推送。 |
| `TASKS.md`、`CODEX_CONTINUOUS_STATE.md` 滚动大文档 | 归档历史，当前状态由生成器/短状态文件维护 | 本窗口只更新审计和新增清单 | 大文档会让旧结论伪装成当前实现。 |

## 当前单一真源决策

- 项目定位与本地优先边界：`docs/PROJECT_CHARTER.md`。
- 当前任务：`docs/TASKS.md` 顶部队列，但必须以代码、测试和运行态复核。
- 评级研究可发布性：`scoutfootball research-health` / `GET /health/research`。
- 真实市场身价：本地手工 Transfermarkt 快照经 `/market-value/*` API；不由 synthetic `value_summary.json` 提供。
- 依赖声明：`pyproject.toml`，`uv.lock` 为解析锁定结果。
