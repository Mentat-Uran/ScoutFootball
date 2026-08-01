# Data Layout

本目录只提交结构，不提交抓取到的原始数据、模型产物或导出报告。

当前目录约定：

- `raw/`：各数据源原始快照与缓存。
- `silver/`：标准化后的维表、事实表和 bridge table。
- `gold/`：面向分析与应用的 marts、feature store。
- `models/`：训练集冻结版本、模型产物、OOF 预测。
- `reports/`：本地导出的 HTML/PDF 报告。
- `logs/`：采集日志、schema 校验日志、质量报告。

除 `.gitkeep` 外，其余运行期文件默认不进入版本控制。
