可以融入，但要分层，不要全塞。ScoutFootball 最适合吸收的是“事件数据标准化 + 行为价值模型 + 评分验证 + 可视化组件”，而不是再堆更多爬虫。

最优先推荐这几类。

1. socceraction：最值得接入

这是最应该融入 ScoutFootball 的开源项目。它本身就是“足球动作价值评估工具包”，支持把 StatsBomb、Wyscout、Opta 等事件数据转成统一的 SPADL / atomic-SPADL 表示，并内置 xT、VAEP、Atomic-VAEP。它的定位和 ScoutFootball 的“球员评分系统”高度重合。 ￼

你现在的 ScoutFootball 评分主要还是赛季统计、FBref、Understat、Football-Data 这一类汇总数据。接入 socceraction 后，可以给球员评分增加“动作价值”维度：

player_rating =
  season_stats_score
+ possession_value_score
+ attacking_value
+ defensive_value
+ progression_value

最实际的开发方式不是直接重写评分系统，而是新增一个模块：

src/scoutfootball/action_value/
  spadl_adapter.py
  xt.py
  vaep.py
  aggregate.py

第一阶段只做 StatsBomb Open Data → SPADL → xT / VAEP → player_action_value.parquet。不要一开始就接 Opta、Wyscout，因为你没有商业数据源。

适合做进简历的表述：

引入 SPADL/VAEP 思路，将事件流数据转化为球员动作价值，补足传统进球、助攻、xG 指标对无球和推进贡献的低估。

2. VAEP 论文：作为球员评分模型的理论核心

《Actions Speak Louder Than Goals: Valuing Player Actions in Soccer》是 VAEP 的核心论文。它的核心问题是：传统指标过度关注射门、进球这些稀有事件，不能充分评价大量有上下文的普通动作；VAEP 用动作对比赛结果概率的影响来评估球员贡献。 ￼

这篇论文适合融入 ScoutFootball 的“评分解释系统”。比如球员详情页不要只显示：

进攻 86
防守 72
控球 80

而是显示：

进攻价值：来自射门、关键传球、进入危险区域动作
防守价值：来自抢断、拦截、降低对手得分概率的动作
推进价值：来自传球、带球、区域推进

这会让 ScoutFootball 从“统计打分器”升级成“可解释球探工具”。

3. xT / Expected Threat：比 VAEP 更容易先落地

xT 可以作为 VAEP 前的过渡版本。它的优势是实现简单，解释也直观：球员把球从低威胁区域移动到高威胁区域，就获得正价值。socceraction 已经内置 Expected Threat 模型。 ￼

建议你先做 xT，再做 VAEP。原因很现实：xT 对数据和模型要求低，容易在 Streamlit 里展示。

可以做三个功能：

球员 xT 排行榜
球队 xT 热区图
球员传球/带球推进价值图

这会显著提升项目观感。

4. StatsBomb Open Data：继续作为事件数据主源

你现在已经用了 StatsBomb Open Data，但后续可以用得更深。StatsBomb 的开源仓库提供 competitions、matches、events、lineups、three-sixty 等 JSON 数据，并明确用于公开研究和足球分析。 ￼

建议不要只用它做少量事件样本，而是把它作为 ScoutFootball 的“事件数据标准样板”。也就是说，所有 action-value、xT、VAEP、传球网络、shot map、pressure map 都先基于 StatsBomb Open Data 做出来。

可以新增：

src/scoutfootball/adapters/statsbomb_event.py
src/scoutfootball/features/action_features.py
src/scoutfootball/visualization/pitch.py

注意合规：如果你发布基于 StatsBomb 数据的研究或图表，需要标明数据源为 StatsBomb。StatsBomb README 里明确要求发布、分享或分发基于该数据的研究和分析时注明数据来源。 ￼

5. mplsoccer：最适合提升展示效果

这个库不要用来做模型，用来做图。mplsoccer 是基于 Matplotlib 的足球可视化库，可以画球场、雷达图、pizza chart、bumpy chart、热力图、箭头、散点、传球线，还能加载 StatsBomb open-data。 ￼

ScoutFootball 现在如果要提升“作品集观感”，mplsoccer 的性价比很高。建议做这些图：

球员雷达图
球员 pizza chart
shot map
pass map
xT heatmap
球队传球网络
赛季评分变化 bumpy chart

最适合放 README 的是：

Top 100 球员榜
球员详情页雷达图
比赛 shot map
球队 xT 热区图

这比继续加模型更容易让别人看懂项目价值。

6. kloppy：作为长期数据标准化层，短期不急

kloppy 的价值是把不同供应商的事件数据、追踪数据、坐标系统做统一。它支持事件和 tracking data，能处理不同 provider 的格式、坐标、方向，并导出 Pandas / Polars dataframe。 ￼

但你现在的数据源主要是公开数据，短期还不需要强行接 kloppy。它适合作为未来 v1.0 之后的架构升级：

provider raw data
→ kloppy normalized dataset
→ ScoutFootball internal schema
→ SPADL / action value / ratings

如果你后面想支持 Metrica、StatsBomb 360、SkillCorner、TRACAB 这类 tracking 或半 tracking 数据，kloppy 就有价值。现在先记着，不优先开发。

7. Dixon-Coles：用于升级你的比分预测模块

你现在的比分预测是 Independent Poisson baseline。下一步最自然的升级就是 Dixon-Coles。Dixon-Coles 解决的是独立 Poisson 在低比分，尤其 0-0、1-0、0-1、1-1 附近拟合不足的问题；后续研究也把 Dixon-Coles 解释为双 Poisson 的扩展，并讨论了对低比分概率的调整。 ￼

但是它只应该作为第二主线，不要超过球员评分。开发建议：

src/scoutfootball/models/
  poisson.py
  dixon_coles.py
  calibration.py
  backtest.py

你可以让比分预测模块形成三档模型：

baseline_0: league average
baseline_1: independent poisson
baseline_2: dixon-coles + time decay

然后在 EVALUATION.md 里比较 log loss、Brier score、RPS。这样比直接说“我做了预测模型”更可信。

8. xG 相关论文：不要重新造大模型，但要吸收方法

xG 本身不是统一标准，不同模型会因为数据源、特征和定义不同产生差异；常见做法是基于射门位置、角度、身体部位、助攻方式、上下文等特征训练概率模型。 ￼

你可以吸收两类论文：

一类是 Player / Position Adjusted xG。相关研究用 StatsBomb 事件数据和机器学习方法做 xG，并进一步按位置或球员调整 xG，用来回答“机会落到不同球员脚下是否应该给不同期望值”。 ￼

另一类是 xG 偏差和 finishing ability。2024 年有研究指出，用进球减 xG 评价终结能力会受样本量、高方差和模型偏差影响，不能粗暴解释为“射术强/弱”。 ￼

这对 ScoutFootball 很重要。你的评分模型里不要简单写：

finishing = goals - xG

更合理的是：

finishing_signal =
  shrinkage(goals - xG, shot_volume)

也就是射门样本少的球员不要给太高/太低的终结能力判断。

9. xG+ / possession-level shot probability：作为远期研究方向

2025 年的 xG+ 思路是：传统 xG 只评价“已经射门”的机会，而 xG+ 试图在控球过程中估计“接下来是否会产生射门，以及如果射门会有多高 xG”，从而缓解只看射门样本的限制。 ￼

这个方向很高级，但对 ScoutFootball 不是短期任务。它适合以后作为“进攻过程质量”模块：

possession_threat
shot_creation_probability
expected_possession_value

短期别做，容易开发失控。

10. floodlight：不适合短期，但可参考数据抽象

floodlight 是一个开源 Python 体育分析框架，目标是支持 tracking data、event data、game codes，并提供数据类、解析、预处理、通用数据模型和可视化。 ￼

它对你最有价值的不是直接接入，而是参考它的数据抽象方式。ScoutFootball 后面可以借鉴：

Game
Team
Player
Event
Frame
Segment

但现在不建议引入，除非你明确要处理 tracking data。

最建议的开发融合路线

不要同时接 10 个东西。按优先级来。

第一阶段：展示与评分增强。

接入 mplsoccer
做球员雷达图 / pizza chart / shot map / xT heatmap

收益最大，能马上提升项目展示效果。

第二阶段：事件价值模型。

接入 socceraction
StatsBomb → SPADL → xT
输出 player_action_value.parquet

这一步会让 ScoutFootball 从“赛季统计评分”升级为“动作价值评分”。

第三阶段：评分模型重构。

综合评分 =
  传统赛季统计
+ xG/xA
+ xT/VAEP
+ 出勤稳定性
+ 联赛强度
+ 年龄/趋势

第四阶段：模型评估文档。

EVALUATION.md
MODEL_CARD.md
baseline comparison
error analysis
position-wise metrics

第五阶段：比分预测升级。

Independent Poisson
→ Dixon-Coles
→ time decay
→ calibration