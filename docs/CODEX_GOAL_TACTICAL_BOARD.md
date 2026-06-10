# Codex Goal: Electronic Tactical Board Roadmap

## 目标

把 `frontend/` 里的电子战术板从“第一切片原型”升级为一个更接近现实教练白板、赛前演示板和轻量战术动画工具的本地优先模块。它仍然是 ScoutFootball 的产品可视化层，不进入模型训练，不引入重型视频处理，不把未接入后端的数据写成正式能力。

当前已有能力包括：0-100 归一化球场坐标、基础对象、主客队 player/ball/arrow/zone、阵型预设、拖拽、JSON 工程、本地保存、schema sanitizer、关键帧对象快照和线性插值。后续开发必须在这些基础上补齐交互、对象模型、动画、导出、球员数据联动和报告嵌入。

## 调研结论

类似电子战术板项目的高频能力可以归纳为六类：

1. 画布编辑：球场视图、球员/足球/箭头/区域/标签、拖拽、复制、删除、图层、缩放、撤销重做。
2. 球员身份：姓名、号码、位置、角色、队伍颜色、头像/圆点样式、球员信息卡、阵容导入。
3. 双队对抗：红蓝/主客两队同时显示，分别设置阵型、颜色、球衣号码、站位方向和控球状态。
4. 白板标注：像现实白板一样自由画线、箭头、圈选、擦除、荧光标记、虚线、曲线、区域和文字备注。
5. 动画演示：关键帧、路径、时间轴、球员/足球移动、路径尾迹、ghost silhouette、播放/暂停/逐帧和全屏演示。
6. 导出分享：PNG、PDF、WebM/MP4、JSON 工程、报告嵌入、训练卡、视频时间线或后续 telestration。

DrawTactics 强调路径动画、step-based/timing-based 两种动画模式、曲线路径、时间轴 scrubber、WebM 导出和裁切；TacticSlate 强调姓名/号码/角色/队色、箭头/曲线/虚线/高亮/连接器、逐帧动画、ghost silhouettes、IndexedDB 离线保存和 PNG/PDF/WebM 导出；JLA Tactics Board 强调球队数据库、预置球队/战术、自定义球员、动画、视频标注、MP4/PNG 导出和实时协作；Metrica Tactical Boards 强调球员 ID、区域、轨迹、球员移动动画、门后视角、导出到时间线并与视频标注工作流结合。

本项目近期应该吸收“本地可用、轻量、可截图、可导出、可嵌入报告”的部分；实时协作、商业球队数据库、重型视频 telestration、tracking 数据导入、3D/门后高级视角和云同步暂缓。

## 当前不足

### 对象模型不足

- `player` 当前只有 `team`、`label`、`number`、`color`、`radius` 等基础字段，缺少 `player_id`、`name`、`display_name`、`shirt_number`、`position`、`role`、`footedness`、`club`、`national_team`、`rating_snapshot`、`confidence_level`、`notes`、`injury_status`、`data_source`。
- `team` 当前只有 `home/away`，缺少 team profile：队名、短名、颜色、球衣样式、进攻方向、阵型、默认号码、默认角色、守门员颜色。
- `arrow` 只支持起点终点和 solid/dashed/curved，缺少 pass/run/press/cover/block/carry/shot 等 football-specific semantic type。
- `zone` 只有矩形，缺少 circle、free polygon、half-space、channel、pressing trap、defensive block、overload area 等战术区类型。
- 缺少 freehand stroke、eraser stroke、highlight stroke、text box、connector、measurement line、ghost player、cone/pole/mini-goal 等训练对象。

### 交互不足

- 还没有清晰的对象属性面板，无法直接修改号码、姓名、位置、颜色、角色、透明度、线宽、箭头样式。
- 鼠标悬浮球员时没有 player tooltip / info card。
- 双队管理不完整：不能同时从 UI 生成主队和客队阵型、单独选择两队颜色、镜像方向、首发号码和替补。
- 白板笔工具缺失：不能像现实白板一样按住鼠标/触控板自由画线。
- 缺少橡皮擦、框选、多选、吸附、对齐、复制粘贴、批量换色、批量锁定、对象搜索。
- 移动端/触屏交互未充分定义：pointer events、长按菜单、双指缩放、触控绘图防误触。

### 动画和演示不足

- 已有关键帧函数和线性插值基础，但缺少完整 Animate mode UI。
- 缺少时间轴、帧缩略图、帧备注、播放控制、循环、速度控制、逐帧播放。
- 缺少路径对象与关键帧联动：球员/足球应可沿 run/pass/carry path 移动，而不是只做对象快照跳变。
- 缺少 ghost silhouette / previous-frame shadow，用于解释球员从哪里移动到哪里。
- 缺少 coaching point 结构：phase、trigger、objective、player roles、risk、countermeasure。
- 缺少 presentation mode：隐藏编辑控件、全屏播放、只读分享、报告页嵌入预览。

### 导出和持久化不足

- JSON 导入导出已有基础，但版本迁移、只读打开旧工程、schema migration warning 还不完整。
- 还没有 PNG/PDF/WebM 导出。
- 没有导出布局模板，例如 16:9 演示图、A4 战术卡、手机竖屏短视频、报告内嵌图。
- localStorage 适合第一切片，但复杂工程和图片/动画导出后应评估 IndexedDB。
- 公开导出物还需要 source attribution，尤其是包含 StatsBomb Open Data、评分快照、比赛预测或球员画像时。

## 待实现功能清单

### P1.5-A：球员和球队对象增强

- [ ] 扩展 `player` schema：`player_id`、`name`、`display_name`、`shirt_number`、`position`、`role`、`team_id`、`rating_snapshot_id`、`confidence_level`、`notes`、`data_source`。
- [ ] 保留兼容字段 `label`、`number`，但内部统一映射到 `display_name` 和 `shirt_number`。
- [ ] 支持点击球员后在属性面板修改球衣号码、姓名、位置、角色、颜色、半径和备注。
- [ ] 支持直接双击球员快速改号码或名称。
- [ ] 支持球员号码显示开关：只显示号码、只显示姓名、号码+姓名、位置缩写、隐藏文字。
- [ ] 支持球员悬浮信息卡：姓名、号码、位置、角色、球队、评分、置信度、备注、数据来源。
- [ ] 悬浮卡必须使用安全渲染，不允许把导入 JSON 字符串直接进入 `innerHTML`。
- [ ] 新增 `teamProfile`：`team_id`、`name`、`short_name`、`primary_color`、`secondary_color`、`gk_color`、`formation`、`attacking_direction`、`kit_style`。
- [ ] 支持主队/客队分别设置颜色、阵型、方向和默认号码。
- [ ] 支持一键生成红蓝两队 11v11 对抗站位，不只生成单队。
- [ ] 支持主客队镜像：客队默认从右向左，主队默认从左向右。
- [ ] 支持替补/教练/中立标记，但默认不干扰 11v11 主画布。

### P1.5-B：白板式绘图工具

- [ ] 新增工具模式：select、pan、player、ball、arrow、zone、text、freehand、eraser、highlight。
- [ ] 实现 freehand stroke：鼠标/触控按下开始记录路径，移动时追加点，松开结束并写入 objects。
- [ ] freehand stroke 支持颜色、线宽、透明度、平滑度、虚线样式。
- [ ] 实现橡皮擦：可删除整条 stroke，也可按路径局部擦除；第一版允许整条删除即可。
- [ ] 支持普通箭头、虚线箭头、曲线箭头、无箭头线、双向箭头。
- [ ] 支持 football-specific arrow type：run、pass、carry、press、cover、block、shot、rotation。
- [ ] 支持圈选区域、矩形区域、圆形区域、多边形区域、半空间/边路通道模板。
- [ ] 支持文本标签和 coaching note 标签，文本可拖拽、缩放、换行。
- [ ] 支持图层顺序：球场背景 < 区域/高亮 < 路径/箭头 < 球员/足球 < 文字/悬浮标记。
- [ ] 支持快捷键：V 选择、P 球员、B 球、A 箭头、Z 区域、T 文字、F 白板笔、E 橡皮、Space 平移、Cmd/Ctrl+Z 撤销。

### P1.5-C：双队、阵型和比赛场景

- [ ] 阵型预设生成时允许选择 teamProfile，而不是只传 `home/away`。
- [ ] 补更多阵型：4-1-4-1、4-3-2-1、3-4-3、3-4-2-1、4-2-2-2、4-5-1、5-4-1。
- [ ] 补定位球模板：角球进攻、角球防守、任意球、点球、防守站位、开球、门球出球、高压逼抢、低位防守。
- [ ] 支持半场/全场/左半场/右半场/禁区局部视图。
- [ ] 预留门后视角，但近期先只做 schema 和 UI 占位，不做复杂 3D。
- [ ] 支持控球方标记、比赛阶段标记、phase 标签：build-up、pressing、transition、set-piece、counterattack、defensive block。
- [ ] 支持从比赛预测页创建赛前战术板：主队、客队、阵型、预测比分、模型版本、coverage 警示写入 metadata。

### P1.5-D：动画、时间轴和演示

- [ ] 完整实现 Animate mode UI：帧列表、增加帧、复制帧、删除帧、重命名帧、帧时长、帧备注。
- [ ] 支持播放/暂停/停止/上一帧/下一帧/循环/速度倍率。
- [ ] 支持 timeline scrubber，拖动时间轴时画布即时更新。
- [ ] 支持对象在帧之间线性插值，并保留当前已有 `interpolateObjects()` 的兼容性。
- [ ] 支持路径动画：球员和足球可绑定到 run/pass/carry path。
- [ ] 支持 easing：linear、ease-in、ease-out、ease-in-out。
- [ ] 支持 ghost silhouette：显示上一帧或起始位置的半透明影子。
- [ ] 支持 movement trail：显示球员或足球移动轨迹。
- [ ] 支持箭头/区域/文字按帧出现、淡入、淡出或隐藏。
- [ ] 支持 presentation mode：全屏、隐藏工具栏、只显示画布/备注/帧标题。
- [ ] 每个动画片段支持 metadata：`phase`、`trigger`、`coaching_point`、`risk`、`countermeasure`、`roles`、`duration_ms`。

### P1.5-E：导出和报告嵌入

- [ ] PNG 导出：当前画布、指定帧、透明背景、球场背景、16:9、1:1、9:16、A4 横版。
- [ ] PDF 导出：多帧战术卡，每帧包含图、标题、备注、对象图例、source attribution。
- [ ] WebM 导出：使用 `canvas.captureStream` + `MediaRecorder`，支持帧率、分辨率和裁切。
- [ ] WebM 不可用时必须显示清晰降级提示，不允许静默失败。
- [ ] MP4 导出仅作为后续可选本地后端能力，不在前端第一阶段强行实现。
- [ ] JSON 工程导出必须包含 schema version、对象、帧、teamProfiles、metadata、source attribution。
- [ ] JSON 导入必须做版本检查、字段迁移、对象数限制、文本长度限制、颜色值清洗、坐标 clamp。
- [ ] 旧版本工程不可完整迁移时，以只读方式打开并提示缺失字段。
- [ ] 报告页可嵌入 board snapshot、动画导出路径、战术备注、数据来源和生成时间。

### P1.5-F：数据分析联动

- [ ] 从球员画像页“发送到战术板”，自动带入姓名、号码、位置、评分、置信度和低置信度原因。
- [ ] 从 Squads/World Cup 页面生成国家队战术板，带入首发/替补但允许手动调整。
- [ ] 从 Compare 页面生成双方对抗战术板，自动创建红蓝两队。
- [ ] 从 Match Prediction 页面创建赛前方案，写入主客队、预测概率、比分矩阵、模型版本和 coverage。
- [ ] 从 Action Values 页面把 xT 热区作为只读背景层；必须标注 StatsBomb 样本限制，不写成全量战术建议。
- [ ] 从 watchlist/shortlist 读取球员备注，生成可审阅角色说明。
- [ ] 导出物若含模型输出，必须显示 model run id、输入 hash 或至少显示“local artifact snapshot”。

### P1.5-G：工程质量、安全和测试

- [ ] 为 tactical board schema 增加 fixture：legacy project、malicious strings、oversized project、invalid coordinates、unknown object types。
- [ ] 增加 sanitizer 单元测试：导入恶意 title/player name/team name/text label 不执行 HTML/JS。
- [ ] 增加 round-trip 测试：创建 -> 保存 -> 导出 JSON -> 导入 -> 对象/帧/teamProfiles/metadata 不丢失。
- [ ] 增加 renderer smoke test：空项目、双队项目、200 对象上限、60 帧上限、移动端尺寸不崩溃。
- [ ] 增加 `node --check frontend/tactical-board.js`、`node --check frontend/tactical-renderer.js`、`node --check frontend/app.js` 的验证说明。
- [ ] 大对象数量下保持交互可用：拖拽和绘图时避免每帧全量重排 DOM。
- [ ] 所有新增 UI 字符串继续保持项目现有 Liquid Glass 风格和几何图标风格，不引入杂乱 emoji。

## 推荐开发顺序

1. 先做对象 schema 和 UI 属性面板：号码、姓名、位置、队伍颜色、双队配置。
2. 再做悬浮信息卡和安全渲染，避免后续数据联动时返工。
3. 再做白板工具：freehand、eraser、highlight、text、football-specific arrows。
4. 再做双队阵型和定位球模板，保证可截图展示。
5. 再补 Animate mode：帧 UI、播放控制、ghost、trail。
6. 再做 PNG/PDF/WebM 导出。
7. 最后接球员画像、比赛预测、动作价值和报告页。

## Codex 执行要求

- 每次只实现一个稳定切片，不要一次性重写整个前端。
- 保持纯静态前端可运行：`python3 -m http.server 8600 --directory frontend`。
- 不新增云服务、不新增登录、不新增商业数据源。
- 不把 mock 数据称为真实数据。
- 不破坏现有 README/TASKS 描述的 pipeline、FastAPI 和 Streamlit 入口。
- 修改 schema 时必须保留旧工程兼容或给出只读降级。
- 新增外部数据字段时必须包含 source attribution。
- 完成后同步更新 `README.md`、`docs/TASKS.md` 和必要的前端注释。

## 验收命令

```bash
node --check frontend/app.js
node --check frontend/tactical-board.js
node --check frontend/tactical-renderer.js
python3 -m http.server 8600 --directory frontend
```

如改到 Python 后端或报告层，再执行：

```bash
uv run ruff check .
uv run pytest
PYTHONPATH=src uv run python -m scoutfootball validate
```
