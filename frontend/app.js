const APP_VERSION = "1.0.3";
const i18n = {
    zh: {
        nav_overview: "总览",
        nav_players: "球员",
        nav_compare: "对比",
        nav_value: "身价",
        nav_matches: "预测",
        nav_teams: "球队",
        nav_scouting: "球探",
        nav_actions: "动作价值",
        nav_reports: "报告",
        status_label: "本地产物",
        app_title: "ScoutFootball 分析终端",
        search_placeholder: "搜索球员、球队、报告",
        overview_kicker: "只读研究工作台",
        overview_title: "覆盖、模型、球探决策",
        metric_player_match: "球员比赛行",
        metric_team_match: "球队比赛行",
        metric_ratings: "评分行",
        metric_events: "事件样本",
        data_health: "数据健康",
        health_oof: "身价 OOF 可用",
        health_proxy: "球员 match-level 覆盖不足",
        health_trends: "趋势指标契约待统一",
        health_truth: "真实标签仍为空表",
        card_players: "球员画像",
        card_players_body: "排名、位置内 percentile、雷达、置信度和详情卡。",
        card_value: "身价偏离",
        card_value_body: "OOF 残差、偏差榜、年龄和联赛分层。",
        card_match: "比赛预测",
        card_match_body: "胜平负、比分矩阵、模型覆盖和校准入口。",
        players_kicker: "位置内画像",
        player_pool: "球员池",
        export: "导出",
        th_rank: "排名",
        th_player: "球员",
        th_pos: "位置",
        th_team: "球队",
        th_rating: "评分",
        th_conf: "置信度",
        th_season: "赛季",
        value_kicker: "OOF residual",
        value_title: "实际身价 vs 预测身价",
        compare_kicker: "球员对比",
        compare_title: "双球员雷达叠加与指标差异",
        compare_note: "选择两名球员进行位置百分位、雷达维度和关键统计的并排对比。",
        compare_select: "选择球员",
        compare_player_a: "球员 A",
        compare_player_b: "球员 B",
        compare_button: "对比",
        compare_radar_title: "雷达图对比",
        compare_stats_title: "关键指标",
        compare_pct_title: "位置百分位对比",
        compare_col_metric: "指标",
        compare_col_dimension: "维度",
        value_rank: "偏离榜",
        undervalued: "低估",
        overvalued: "高估",
        match_selector: "比赛选择",
        model_label: "模型",
        home_team: "主队",
        away_team: "客队",
        score_matrix: "比分矩阵",
        review_queue: "复核队列",
        watchlist: "Watchlist",
        snapshot: "快照",
        scouting_kicker: "本地优先决策台",
        scouting_title: "复核、观察与候选闭环",
        scouting_boundary: "服务端队列只读；决策默认保存在当前浏览器，可显式启用本地 API 持久化。",
        teams_kicker: "球队实力分析",
        teams_title: "球队评分聚合与位置组实力",
        teams_note: "基于球员评分的分钟加权聚合，展示球队整体实力、位置组分布和核心球员。",
        teams_metric_count: "球队数",
        teams_metric_avg: "平均评分",
        teams_metric_top: "最高评分",
        teams_table_title: "球队排名",
        teams_col_team: "球队",
        teams_col_league: "联赛",
        teams_col_rating: "评分",
        teams_col_squad: "阵容",
        teams_detail_title: "球队详情",
        teams_detail_placeholder: "选择一支球队查看详情",
        teams_chart_title: "位置组实力对比",
        teams_compare_title: "球队对比",
        teams_compare_a: "球队 A",
        teams_compare_b: "球队 B",
        teams_compare_button: "对比",
        teams_compare_radar: "位置组雷达",
        teams_compare_pos: "位置组对比",
        teams_compare_col_group: "组",
        scouting_metric_review: "待复核",
        scouting_metric_short: "候选",
        scouting_search: "搜索球员、球队或原因",
        scouting_status_all: "全部状态",
        scouting_local_state: "本地状态",
        scout_workspace_export: "导出工作区",
        scout_workspace_import: "导入工作区",
        scout_workspace_server_save: "保存到本地 API",
        scout_workspace_server_load: "从本地 API 加载",
        scout_workspace_preview_kicker: "安全导入",
        scout_workspace_preview_title: "球探工作区预览",
        scout_workspace_merge: "安全合并",
        scout_workspace_replace: "替换本地",
        action_kicker: "StatsBomb 样本",
        action_title: "动作价值研究台",
        action_boundary: "仅表示当前 StatsBomb Open Data 覆盖样本；默认过滤低于 450 分钟的极小样本。",
        action_search: "搜索球员或赛事",
        action_all_competitions: "全部赛事",
        action_ranking: "动作价值排名",
        action_pipeline: "动作价值后端",
        backend_contracts: "后端契约",
        minutes: "分钟",
        percentile: "百分位",
        value: "身价",
        residual: "残差",
        home: "主胜",
        draw: "平局",
        away: "客胜",
        expected_goals: "期望进球",
        coverage: "覆盖",
        nav_wc_schedule: "赛程",
        nav_wc_squads: "名单",
        nav_wc_compare: "对比",
        nav_wc_probability: "出线",
        nav_wc_knockout: "淘汰赛",
        nav_wc_tournament: "锦标赛",
        wc_kicker: "2026 美加墨世界杯",
        wc_schedule_title: "小组赛赛程",
        wc_squads_title: "球队名单 & 评分",
        wc_compare_title: "球队实力对比",
        wc_prob_title: "小组出线概率",
        wc_knockout_title: "淘汰赛对阵表",
        wc_tournament_title: "锦标赛模拟器",
        wc_tournament_desc: "录入比赛结果，查看出线情景",
        wc_tournament_win: "夺冠概率 (Top 16)",
        wc_win_prob: "夺冠概率",
        wc_team_outlook: "球队前景",
        wc_view_outlook: "查看前景",
        wc_outlook_group_finish: "小组名次概率",
        wc_outlook_group_rank: "小组排名",
        wc_outlook_knockout_path: "淘汰赛投影路径",
        wc_outlook_championship: "夺冠概率",
        wc_outlook_strength: "阵容强度分解",
        wc_outlook_coverage: "名单覆盖率",
        wc_outlook_shrunk_avg: "收缩后平均评分",
        wc_outlook_core_avg: "核心球员平均评分",
        wc_outlook_disclaimer: "说明",
        wc_outlook_loading: "加载中...",
        wc_outlook_select_team: "选择球队",
        wc_outlook_no_data: "暂无该球队的前景数据",
        wc_outlook_r32: "32强",
        wc_outlook_r16: "16强",
        wc_outlook_qf: "四分之一决赛",
        wc_outlook_sf: "半决赛",
        wc_outlook_final: "决赛",
        wc_outlook_projected_opponent: "投影对手",
        wc_outlook_advance_prob: "晋级概率",
        wc_outlook_no_opponent: "未投影",
        wc_teams: "球队",
        wc_groups: "小组",
        wc_group_matches: "小组赛",
        wc_briefing: "赛前简报",
        wc_export_json: "导出简报 JSON",
        wc_export_csv: "导出简报 CSV",
        wc_fixtures: "赛程表",
        wc_date: "日期",
        wc_time: "时间",
        wc_group_col: "小组",
        wc_home: "主队",
        wc_away_col: "客队",
        wc_venue: "场馆",
        wc_squad_list: "球员名单",
        wc_club: "俱乐部",
        wc_league: "联赛",
        wc_rating_dist: "评分分布",
        wc_compare_summary: "总览对比",
        wc_strength_rank: "48 队实力排名",
        wc_strength: "实力评分",
        wc_entertainment: "娱乐性估算",
        wc_squad_size: "名单",
        wc_rated: "有评分",
        wc_big5: "五大联赛",
        wc_avg_rating: "均分",
        wc_no_data: "无数据",
        wc_low_coverage: "评分覆盖率低于50%，结论置信度较低",
        sort_priority: "优先级",
        sort_date: "日期",
        sort_name: "姓名",
        status_pending: "待处理",
        status_reviewing: "审核中",
        status_approved: "已通过",
        status_rejected: "已拒绝",
        scout_new_badge: "新",
        scout_note_placeholder: "添加备注...",
        nav_license: "数据源",
        nav_data: "数据",
        data_kicker: "数据状态",
        data_title: "数据源与覆盖",
        data_sources_table: "数据源列表",
        data_th_name: "名称",
        data_th_rows: "行数",
        data_th_updated: "最后更新",
        data_th_type: "类型",
        data_type_real: "真实",
        data_type_proxy: "代理",
        data_type_synthetic: "合成",
        data_coverage_league: "联赛覆盖",
        data_missing_warnings: "缺失数据警告",
        data_no_missing: "无缺失数据",
        data_source_real: "真实数据",
        data_source_proxy: "代理数据",
        data_source_synthetic: "合成数据",
        confidence_gate: "置信门槛",
        confidence_gate_desc: "覆盖率 > 0.90 = 高置信度",
        coverage_league: "联赛覆盖",
        rated_teams: "有评分球队",
        total_teams: "总球队",
        export_csv: "导出 CSV",
        license_kicker: "数据源许可",
        license_title: "Data Source Manifest",
        license_sources_label: "数据源",
        license_table_title: "数据源列表",
        license_th_source: "数据源",
        license_th_license: "许可证",
        license_th_attribution: "署名要求",
        license_th_url: "URL",
        license_attribution_notice: "StatsBomb 署名声明",
        model_version: "模型版本",
        model_comparison: "模型对比",
        coverage_warning: "▲ 覆盖率低于90%",
        log_loss: "对数损失",
        send_to_tactical: "发送到战术板",
        expand_details: "展开详情",
        collapse_details: "收起详情",
        copy_command: "复制命令",
        train_seasons: "训练赛季",
        test_seasons: "测试赛季",
        dependency_versions: "依赖版本",
        toggle_ratings: "切换评分",
        th_actions: "操作",
        action_watchlist: "观察",
        action_shortlist: "候选",
        action_tactical: "战术",
        action_compare: "对比",
        compare_title: "球员对比",
        compare_select_hint: "选择两名球员进行对比",
        compare_clear: "清除",
        compare_dimension: "维度",
        compare_percentile: "百分位",
        compare_no_same_pos: "两名球员位置不同，百分位基于各自位置池计算",
        value_fairness: "身价公平性",
        oof_residual_label: "OOF 残差",
        league_bias_label: "联赛偏差",
        position_bias_label: "位置偏差",
        age_curve_label: "年龄曲线",
        transfermarkt_notice: "Transfermarkt 数据需手动导入，当前为估算值",
        value_no_fairness: "暂无身价公平性数据",
        price_band_label: "价格区间",
        price_all: "全部",
        price_low: "低 (<20M)",
        price_medium: "中 (20-80M)",
        price_high: "高 (>80M)",
        age_curve_title: "年龄曲线",
        same_cohort_title: "同位置同年龄对比",
        watchlist_notes_label: "观察备注",
        generate_tactical_role: "生成战术角色",
        tactical_role_label: "战术角色分析",
        nav_calibration: "校准",
        nav_help: "帮助",
        nav_backtest: "回测",
        calibration_kicker: "模型校准",
        calibration_title: "预测 vs 实际",
        calibration_plot: "校准图",
        calibration_brier: "Brier 分解",
        calibration_low_score: "低分桶分析",
        calibration_league: "联赛校准",
        backtest_kicker: "模型回测对比",
        backtest_title: "Poisson vs Dixon-Coles 回测",
        backtest_metric_desc: "Log Loss / Brier / RPS",
        backtest_metric_comparison: "指标对比",
        backtest_metric: "指标",
        backtest_dc_decay: "DC (衰减)",
        backtest_winner: "胜出",
        backtest_folds: "分折明细",
        backtest_calibration: "Isotonic 校准效果",
        backtest_fold: "折",
        backtest_test_matches: "测试比赛",
        backtest_not_available: "暂无回测数据",
        backtest_instructions: "运行 `PYTHONPATH=src uv run python -m scoutfootball backtest` 生成回测产物。",
        backtest_brier_before: "校准前 Brier",
        backtest_brier_after: "校准后 Brier",
        backtest_rps_before: "校准前 RPS",
        backtest_rps_after: "校准后 RPS",
        backtest_n_matches: "比赛数",
        backtest_no_calibration: "暂无 isotonic 校准报告",
        backtest_fold_chart: "分折指标趋势",
        backtest_tuning: "Decay 参数调优",
        backtest_tuning_desc: "Dixon-Coles 时间衰减网格搜索",
        backtest_drift: "校准漂移监控",
        backtest_drift_desc: "按时间窗口追踪 RPS/Brier/LogLoss 漂移",
        backtest_ensemble_weights: "集成权重优化",
        backtest_ensemble_weights_desc: "基于回测 RPS 网格搜索的最优权重",
        backtest_calibration_comparison: "校准对比分析",
        backtest_calibration_comparison_desc: "原始 vs Isotonic 重校准 按比分线对比",
        ensemble_weights_not_available: "尚未优化权重",
        ensemble_weights_instructions: "运行 `scoutfootball optimize-ensemble` 计算并缓存最优集成权重",
        ensemble_weights_default: "默认等权重",
        ensemble_weights_optimized: "已优化",
        ensemble_achieved_rps: "达成 RPS",
        ensemble_n_matches: "比赛数",
        ensemble_saved_at: "保存时间",
        calibration_comparison_not_available: "暂无校准对比数据",
        calibration_comparison_instructions: "运行 `scoutfootball tune-predictions --run-backtest` 生成回测产物",
        calibration_comparison_overall: "总体指标",
        calibration_comparison_by_score: "按比分线分解",
        calibration_comparison_by_league: "按联赛分解",
        calibration_comparison_league: "联赛",
        calibration_comparison_score_line: "比分",
        calibration_comparison_raw: "原始",
        calibration_comparison_recalibrated: "重校准",
        calibration_comparison_improvement: "改善%",
        calibration_comparison_n_matches: "场次",
        prediction_attribution_title: "预测因子归因",
        prediction_attribution_desc: "基于排列中性化的 Dixon-Coles 因子贡献分解",
        prediction_attribution_baseline: "基线胜率",
        prediction_attribution_factor: "因子",
        prediction_attribution_delta: "Δ 主胜概率",
        prediction_attribution_neutralized: "中性化后胜率",
        prediction_attribution_loading: "计算因子归因中…",
        prediction_attribution_fetch: "分析因子",
        prediction_attribution_not_available: "暂无归因数据",
        prediction_attribution_instructions: "需要足够的 team_match 数据以拟合 Dixon-Coles 模型",
        prediction_attribution_ci_fetch: "置信区间",
        prediction_attribution_ci_loading: "Bootstrap 置信区间计算中…",
        prediction_attribution_ci_not_available: "暂无置信区间数据",
        prediction_attribution_delta_ci: "Δ 90% CI",
        prediction_attribution_delta_mean: "Δ 均值",
        prediction_diagnostics_title: "预测诊断",
        prediction_diagnostics_desc: "校准、漂移与因子归因综合视图",
        prediction_diagnostics_fetch: "诊断",
        prediction_diagnostics_loading: "加载诊断数据中…",
        prediction_diagnostics_calibration: "校准",
        prediction_diagnostics_drift: "漂移",
        prediction_diagnostics_attribution: "因子归因",
        prediction_diagnostics_ci_cache: "CI 缓存",
        prediction_diagnostics_stable: "稳定",
        prediction_diagnostics_drift_detected: "检测到漂移",
        ensemble_attribution_title: "集成归因",
        ensemble_attribution_desc: "多模型因子贡献与加权融合",
        ensemble_attribution_fetch: "集成分析",
        ensemble_attribution_loading: "计算集成归因中…",
        ensemble_attribution_not_available: "暂无集成归因数据",
        ensemble_attribution_weights: "权重",
        ensemble_attribution_weights_source: "权重来源",
        ensemble_attribution_blended: "融合",
        ensemble_attribution_per_model: "逐模型",
        ensemble_attribution_drift_timeline: "漂移时间线",
        ensemble_attribution_drift_timeline_loading: "加载漂移时间线…",
        ensemble_attribution_drift_timeline_not_available: "暂无漂移时间线数据",
        value_bet_title: "价值投注分析",
        value_bet_desc: "模型概率 vs 市场赔率 EV/Kelly 计算",
        value_bet_fetch: "分析",
        value_bet_home_odds: "主胜赔率",
        value_bet_draw_odds: "平局赔率",
        value_bet_away_odds: "客胜赔率",
        value_bet_loading: "计算中…",
        value_bet_error: "分析失败",
        value_bet_outcome: "结果",
        value_bet_model_prob: "模型概率",
        value_bet_odds: "赔率",
        value_bet_implied: "隐含概率",
        value_bet_ev: "期望值(EV)",
        value_bet_edge: "Edge",
        value_bet_kelly: "Kelly 份额",
        value_bet_recommendation: "推荐",
        value_bet_best_bet: "最佳投注",
        value_bet_no_value: "无价值投注",
        value_bet_overround: "抽水率",
        value_bet_disclaimer: "分析使用模型概率,非实时市场数据。仅供研究用途。",
        backtest_reliability: "可靠性图",
        backtest_reliability_desc: "预测概率 vs 观测频率校准曲线",
        backtest_reliability_fetch: "加载",
        backtest_reliability_loading: "加载可靠性图…",
        backtest_reliability_not_available: "暂无可靠性图数据",
        backtest_reliability_ece: "ECE (期望校准误差)",
        backtest_reliability_rms: "RMS 校准误差",
        backtest_reliability_predicted: "预测概率",
        backtest_reliability_observed: "观测频率",
        backtest_reliability_samples: "样本数",
        model_comparison_title: "模型对比仪表板",
        model_comparison_desc: "Poisson / DC / DC-Decay 在对齐预测集上的统一指标对比",
        model_comparison_fetch: "加载",
        model_comparison_loading: "加载模型对比数据...",
        model_comparison_error: "加载模型对比失败",
        model_comparison_not_available: "暂无回测数据，请先运行 scoutfootball backtest",
        model_comparison_n_aligned: "对齐比赛数",
        model_comparison_n_models: "模型数",
        model_comparison_metric: "指标",
        model_comparison_winner: "获胜模型",
        model_comparison_accuracy: "准确率",
        model_comparison_avg_confidence: "平均置信度",
        model_comparison_cal_gap: "校准差距",
        scoreline_cal_title: "比分线校准矩阵",
        scoreline_cal_desc: "按实际比分分桶对比预测概率 vs 实际结果率",
        scoreline_cal_fetch: "加载",
        scoreline_cal_loading: "加载比分线校准...",
        scoreline_cal_error: "加载比分线校准失败",
        scoreline_cal_not_available: "暂无回测数据",
        scoreline_cal_scoreline: "比分",
        scoreline_cal_n_matches: "比赛数",
        scoreline_cal_outcome: "主导结果",
        scoreline_cal_avg_probs: "平均预测概率",
        scoreline_cal_actual_rates: "实际结果率",
        scoreline_cal_outcome_summary: "按结果汇总",
        confidence_dist_title: "置信度分布校准",
        confidence_dist_desc: "按预测置信度分桶对比准确率，检验过度自信/欠自信",
        confidence_dist_fetch: "加载",
        confidence_dist_loading: "加载置信度分布...",
        confidence_dist_error: "加载置信度分布失败",
        confidence_dist_not_available: "暂无回测数据",
        confidence_dist_bucket: "置信度区间",
        confidence_dist_n_pred: "预测数",
        confidence_dist_accuracy: "准确率",
        confidence_dist_avg_conf: "平均置信度",
        confidence_dist_cal_gap: "校准差距",
        confidence_dist_overall_acc: "总体准确率",
        confidence_dist_overall_conf: "总体置信度",
        error_analysis_title: "预测误差分析",
        error_analysis_desc: "按置信度分桶找出最差预测，定位模型系统性错误",
        error_analysis_fetch: "加载",
        error_analysis_loading: "加载误差分析...",
        error_analysis_error: "加载误差分析失败",
        error_analysis_not_available: "暂无回测数据",
        error_analysis_bucket: "置信度区间",
        error_analysis_n_pred: "预测数",
        error_analysis_avg_conf: "平均置信度",
        error_analysis_accuracy: "准确率",
        error_analysis_avg_brier: "平均 Brier",
        error_analysis_avg_log_loss: "平均 LogLoss",
        error_analysis_worst_matches: "最差预测",
        error_analysis_overall_worst: "全局最差预测",
        error_analysis_match_id: "比赛ID",
        error_analysis_score: "比分",
        error_analysis_actual: "实际结果",
        error_analysis_predicted: "预测结果",
        error_analysis_confidence: "置信度",
        error_analysis_brier: "Brier",
        error_analysis_log_loss: "LogLoss",
        error_analysis_correct: "正确",
        error_analysis_overall_acc: "总体准确率",
        error_analysis_overall_brier: "总体 Brier",
        error_analysis_overall_log_loss: "总体 LogLoss",
        outcome_dist_title: "结果分布偏差",
        outcome_dist_desc: "对比模型预测结果分布与实际结果分布",
        outcome_dist_fetch: "加载",
        outcome_dist_loading: "加载结果分布...",
        outcome_dist_error: "加载结果分布失败",
        outcome_dist_not_available: "暂无回测数据",
        outcome_dist_outcome: "结果",
        outcome_dist_pred_count: "预测数",
        outcome_dist_pred_share: "预测占比",
        outcome_dist_actual_count: "实际数",
        outcome_dist_actual_share: "实际占比",
        outcome_dist_gap: "分布差距",
        outcome_dist_dominant_bias: "主导偏差",
        outcome_dist_disclaimer: "说明",
        h2h_bias_title: "H2H 历史偏差修正",
        h2h_bias_desc: "基于历史交锋结果调整基线预测概率",
        h2h_bias_fetch: "修正",
        h2h_bias_loading: "计算 H2H 偏差修正...",
        h2h_bias_error: "加载 H2H 偏差修正失败",
        h2h_bias_not_available: "暂无基线预测或 H2H 数据",
        h2h_bias_baseline: "基线概率",
        h2h_bias_corrected: "修正后概率",
        h2h_bias_adjustments: "调整量",
        h2h_bias_h2h_rates: "H2H 历史结果率",
        h2h_bias_n_meetings: "交锋场次",
        h2h_bias_applied: "已应用修正",
        h2h_bias_not_applied: "未应用修正（样本不足）",
        h2h_bias_disclaimer: "免责声明",
        h2h_bias_home_win: "主胜",
        h2h_bias_draw: "平",
        h2h_bias_away_win: "客胜",
        temporal_val_title: "时序验证回测",
        temporal_val_desc: "按时间窗口追踪模型指标趋势",
        temporal_val_fetch: "加载",
        temporal_val_loading: "计算时序验证...",
        temporal_val_error: "加载时序验证失败",
        temporal_val_not_available: "暂无回测数据",
        temporal_val_n_windows: "时间窗口数",
        temporal_val_n_matches: "总比赛数",
        temporal_val_trend: "趋势",
        temporal_val_window: "时间窗口",
        prob_heatmap_title: "概率热力图",
        prob_heatmap_desc: "主胜 vs 客胜概率空间内的密度与准确率",
        prob_heatmap_fetch: "加载",
        prob_heatmap_loading: "计算概率热力图...",
        prob_heatmap_error: "加载概率热力图失败",
        prob_heatmap_not_available: "暂无回测数据",
        prob_heatmap_n_predictions: "预测总数",
        prob_heatmap_grid: "网格",
        prob_heatmap_coverage: "覆盖率",
        prob_heatmap_home_bin: "主胜区间",
        prob_heatmap_away_bin: "客胜区间",
        prob_heatmap_density: "密度",
        prob_heatmap_accuracy: "准确率",
        prob_heatmap_confidence: "置信度",
        staleness_title: "模型新鲜度",
        staleness_desc: "回测数据覆盖窗口与模型新鲜度指示",
        staleness_fetch: "加载",
        staleness_loading: "计算模型新鲜度...",
        staleness_error: "加载模型新鲜度失败",
        staleness_not_available: "暂无回测数据",
        staleness_level: "新鲜度等级",
        staleness_days: "距今天数",
        staleness_backtest_start: "回测起始",
        staleness_backtest_end: "回测结束",
        staleness_n_matches: "回测比赛数",
        staleness_model_type: "模型类型",
        ci_plot_title: "置信区间图",
        ci_plot_desc: "CI 宽度 vs 置信度散点,判断高置信预测是否伴随更窄区间",
        ci_plot_fetch: "加载",
        ci_plot_loading: "计算置信区间散点...",
        ci_plot_error: "加载置信区间图失败",
        ci_plot_not_available: "暂无 CI 列数据(需启用 bootstrap CI 生成)",
        ci_plot_n_points: "散点数",
        ci_plot_avg_conf: "平均置信度",
        ci_plot_avg_width: "平均 CI 宽度",
        ci_plot_corr: "相关系数",
        ci_plot_match: "比赛",
        ci_plot_conf: "置信度",
        ci_plot_lower: "CI 下界",
        ci_plot_upper: "CI 上界",
        ci_plot_width: "CI 宽度",
        ci_plot_correct: "正确",
        ci_plot_no_points: "无散点数据",
        ci_plot_truncated: "已截取前 50 行(共 {n} 行)",
        fold_comparison_title: "折叠对比",
        fold_comparison_desc: "交叉验证折间指标稳定性分析(stable/moderate/unstable)",
        fold_comparison_fetch: "加载",
        fold_comparison_loading: "计算折间指标...",
        fold_comparison_error: "加载折叠对比失败",
        fold_comparison_not_available: "暂无 fold 列数据(需启用交叉验证折分配)",
        fold_comparison_stability: "稳定性",
        fold_comparison_n_folds: "折数",
        fold_comparison_n_matches: "总样本数",
        fold_comparison_acc_std: "准确率标准差",
        fold_comparison_fold: "折",
        fold_comparison_n: "样本数",
        fold_comparison_accuracy: "准确率",
        fold_comparison_brier: "Brier",
        fold_comparison_rps: "RPS",
        fold_comparison_log_loss: "LogLoss",
        fold_comparison_avg_conf: "平均置信度",
        fold_comparison_no_folds: "无折数据",
        league_error_title: "联赛误差分析",
        league_error_desc: "按联赛分组的误差与最差预测,识别模型在不同赛事的表现差异",
        league_error_fetch: "加载",
        league_error_loading: "计算联赛误差...",
        league_error_error: "加载联赛误差分析失败",
        league_error_not_available: "暂无 league 列数据(需启用联赛元数据)",
        league_error_n_leagues: "联赛数",
        league_error_n_matches: "总样本数",
        league_error_accuracy: "总体准确率",
        league_error_brier: "总体 Brier",
        league_error_avg_conf: "平均置信度",
        league_error_match_id: "比赛 ID",
        league_error_pred: "预测结果",
        league_error_actual: "实际结果",
        league_error_conf: "置信度",
        league_error_no_leagues: "无联赛数据",
        feature_importance_title: "特征重要性排名",
        feature_importance_desc: "按 Brier 分离度排名的输入特征,识别对预测误差影响最大的因子",
        feature_importance_fetch: "加载",
        feature_importance_loading: "计算特征重要性...",
        feature_importance_error: "加载特征重要性失败",
        feature_importance_not_available: "暂无可分析的特征列(需在回测中保存输入特征)",
        feature_importance_n_features: "特征数",
        feature_importance_n_matches: "总样本数",
        feature_importance_overall_brier: "总体 Brier",
        feature_importance_top: "最高重要性",
        feature_importance_feature: "特征",
        feature_importance_importance: "重要性",
        feature_importance_mean: "均值",
        feature_importance_std: "标准差",
        feature_importance_n: "样本数",
        feature_importance_truncated: "仅显示前 20 个特征(共 {n} 个)",
        feature_importance_no_features: "无特征数据",
        ci_coverage_title: "置信区间覆盖率",
        ci_coverage_desc: "验证 bootstrap CI 是否达到标称覆盖率,判断区间是否过窄或过宽",
        ci_coverage_fetch: "加载",
        ci_coverage_loading: "计算覆盖率...",
        ci_coverage_error: "加载覆盖率分析失败",
        ci_coverage_not_available: "暂无 CI 列数据(需启用 bootstrap CI 生成)",
        ci_coverage_assessment: "覆盖评估",
        ci_coverage_overall: "总体覆盖率",
        ci_coverage_avg_width: "平均 CI 宽度",
        ci_coverage_nominal: "标称水平",
        ci_coverage_n_matches: "样本数",
        ci_coverage_bucket: "分桶",
        ci_coverage_conf_range: "置信度范围",
        ci_coverage_n: "样本数",
        ci_coverage_empirical: "经验覆盖率",
        ci_coverage_no_buckets: "无分桶数据",
        drift_heatmap_title: "校准漂移热力图",
        drift_heatmap_desc: "时间窗口 × 置信度分桶的 Brier/RPS 网格,定位漂移发生的置信区间",
        drift_heatmap_fetch: "加载",
        drift_heatmap_loading: "计算漂移热力图...",
        drift_heatmap_error: "加载漂移热力图失败",
        drift_heatmap_not_available: "暂无 match_date 列数据(需启用比赛日期元数据)",
        drift_heatmap_drift: "漂移检测",
        drift_heatmap_drift_yes: "检测到漂移",
        drift_heatmap_drift_no: "无漂移",
        drift_heatmap_n_windows: "时间窗口数",
        drift_heatmap_n_buckets: "置信分桶数",
        drift_heatmap_n_matches: "总样本数",
        drift_heatmap_window: "时间窗口",
        drift_heatmap_conf_bucket: "置信分桶",
        drift_heatmap_n: "样本数",
        drift_heatmap_accuracy: "准确率",
        drift_heatmap_brier: "Brier",
        drift_heatmap_rps: "RPS",
        drift_heatmap_log_loss: "LogLoss",
        drift_heatmap_no_cells: "无热力图单元格数据",
        momentum_kicker: "比赛动量预测",
        momentum_title: "实时胜率时间线",
        momentum_home_goals: "主队进球",
        momentum_away_goals: "客队进球",
        momentum_minute: "当前分钟",
        momentum_update: "更新",
        backtest_best_decay: "最优 Decay",
        backtest_selection_metric: "选择指标",
        backtest_half_life: "半衰期(天)",
        backtest_tuning_not_available: "暂无调优数据",
        backtest_tuning_instructions: "运行 `PYTHONPATH=src uv run python -m scoutfootball tune-predictions` 生成调优结果。",
        data_attribution: "数据归属与合规",
        run_comparison: "模型运行对比",
        run_compare_btn: "对比",
        xT_label: "xT 每90分钟",
        xT_percentile: "xT 百分位",
        xT_contribution: "xT 贡献",
        xT_not_available: "xT 数据不可用",
        confidence_reason_label: "置信原因",
        rating_snapshot: "评分快照",
        error_clustering_title: "预测误差聚类",
        error_clustering_desc: "对最差预测按特征签名 k-means 聚类,发现误差模式",
        error_clustering_fetch: "加载",
        error_clustering_loading: "计算误差聚类中…",
        error_clustering_not_available: "暂无回测数据",
        error_clustering_error: "加载误差聚类失败",
        error_clustering_n_clusters: "簇数",
        error_clustering_n_worst: "最差样本",
        error_clustering_n_features: "特征数",
        error_clustering_avg_brier: "平均 Brier",
        error_clustering_cluster: "簇",
        error_clustering_matches: "场",
        error_clustering_brier: "Brier",
        error_clustering_accuracy: "准确率",
        error_clustering_conf: "平均置信度",
        error_clustering_actual: "实际主导",
        error_clustering_predicted: "预测主导",
        error_clustering_feature: "特征",
        error_clustering_centroid: "质心 z",
        error_clustering_no_clusters: "无聚类结果",
        data_drift_title: "数据漂移检测",
        data_drift_desc: "训练/holdout 窗口特征分布 KS 检验,标记 p<0.05 的漂移特征",
        data_drift_fetch: "加载",
        data_drift_loading: "计算数据漂移中…",
        data_drift_not_available: "暂无回测数据(需 match_date 列)",
        data_drift_error: "加载数据漂移失败",
        data_drift_ratio: "漂移比例",
        data_drift_drifted: "漂移特征",
        data_drift_n_train: "训练样本",
        data_drift_n_holdout: "Holdout 样本",
        data_drift_split_date: "分割点",
        data_drift_feature: "特征",
        data_drift_ks: "KS 统计量",
        data_drift_p_value: "p 值",
        data_drift_status: "状态",
        data_drift_train_mean: "训练均值",
        data_drift_holdout_mean: "Holdout 均值",
        data_drift_drifted_yes: "漂移",
        data_drift_drifted_no: "稳定",
        data_drift_no_features: "无特征漂移数据",
        ci_width_title: "置信区间宽度分析",
        ci_width_desc: "按置信度分桶跟踪平均 CI 宽度,标记过宽/过窄的置信区间",
        ci_width_fetch: "加载",
        ci_width_loading: "计算 CI 宽度分析中…",
        ci_width_not_available: "暂无 CI 列数据(需启用 bootstrap CI 生成)",
        ci_width_error: "加载 CI 宽度分析失败",
        ci_width_assessment: "评估",
        ci_width_avg: "平均 CI 宽度",
        ci_width_avg_conf: "平均置信度",
        ci_width_corr: "宽度-置信度相关",
        ci_width_bucket: "置信度桶",
        ci_width_n: "场次",
        ci_width_avg_width: "平均宽度",
        ci_width_avg_lower: "平均下界",
        ci_width_avg_upper: "平均上界",
        ci_width_std: "宽度标准差",
        ci_width_relative: "相对宽度",
        ci_width_no_buckets: "无桶数据",
        stress_test_title: "回测场景压力测试",
        stress_test_desc: "模拟分布偏移并测量模型退化,量化鲁棒性",
        stress_test_fetch: "加载",
        stress_test_loading: "计算压力测试中…",
        stress_test_not_available: "暂无回测数据",
        stress_test_error: "加载压力测试失败",
        stress_test_shift_type: "偏移类型",
        stress_test_shift_ratio: "偏移比例",
        stress_test_n_shifted: "扰动场次",
        stress_test_degradation: "退化评分",
        stress_test_assessment: "评估",
        stress_test_baseline: "基线指标",
        stress_test_stressed: "压力指标",
        stress_test_acc_delta: "准确率变化",
        stress_test_brier_delta: "Brier 变化",
        stress_test_rps_delta: "RPS 变化",
        stress_test_conf_delta: "置信度变化",
        stress_test_n_matches: "场次",
        stress_test_accuracy: "准确率",
        stress_test_brier: "Brier",
        stress_test_rps: "RPS",
        stress_test_log_loss: "LogLoss",
        stress_test_conf: "平均置信度",
        team_drift_title: "按球队校准漂移",
        team_drift_desc: "追踪单支球队预测质量随时间的演化",
        team_drift_fetch: "加载",
        team_drift_loading: "计算球队漂移中…",
        stress_test_team_input: "球队名称",
        stress_test_team_input_ph: "输入球队名",
        team_drift_not_available: "暂无回测数据或球队不存在",
        team_drift_error: "加载球队漂移失败",
        team_drift_team: "球队",
        team_drift_n_matches: "总场次",
        team_drift_n_windows: "窗口数",
        team_drift_drift_detected: "漂移检测",
        team_drift_drift_yes: "检测到漂移",
        team_drift_drift_no: "稳定",
        team_drift_latest_brier: "最新 Brier",
        team_drift_hist_brier: "历史平均 Brier",
        team_drift_rel_change: "相对变化",
        team_drift_trend: "趋势",
        team_drift_window: "时间窗口",
        team_drift_n: "场次",
        team_drift_acc: "准确率",
        team_drift_brier: "Brier",
        team_drift_conf: "平均置信度",
        team_drift_no_points: "无窗口数据(样本不足)",
        uncertainty_title: "预测不确定性量化",
        uncertainty_desc: "每场比赛的熵、置信度边际、概率离散度",
        uncertainty_fetch: "加载",
        uncertainty_loading: "计算不确定性中…",
        uncertainty_not_available: "暂无回测数据",
        uncertainty_error: "加载不确定性分析失败",
        uncertainty_avg_entropy: "平均熵",
        uncertainty_avg_margin: "平均边际",
        uncertainty_avg_dispersion: "平均离散度",
        uncertainty_high_count: "高不确定性场次",
        uncertainty_high_acc: "高不确定性准确率",
        uncertainty_low_acc: "低不确定性准确率",
        uncertainty_entropy_corr: "熵-准确率相关",
        uncertainty_match: "比赛",
        uncertainty_conf: "置信度",
        uncertainty_entropy: "熵",
        uncertainty_margin: "边际",
        uncertainty_dispersion: "离散度",
        uncertainty_predicted: "预测",
        uncertainty_actual: "实际",
        uncertainty_correct: "正确",
        uncertainty_label: "标签",
        uncertainty_no_points: "无不确定点数据",
        profit_loss_title: "回测盈亏模拟",
        profit_loss_desc: "Flat-stake 和 Kelly 投注策略的累计盈亏",
        profit_loss_fetch: "加载",
        profit_loss_loading: "计算盈亏中…",
        profit_loss_not_available: "暂无回测数据",
        profit_loss_error: "加载盈亏模拟失败",
        profit_loss_n_matches: "比赛数",
        profit_loss_win_rate: "胜率",
        profit_loss_flat_roi: "Flat ROI",
        profit_loss_kelly_roi: "Kelly ROI",
        profit_loss_flat_profit: "Flat 总盈亏",
        profit_loss_kelly_profit: "Kelly 总盈亏",
        profit_loss_max_dd: "最大回撤",
        profit_loss_avg_conf: "平均置信度",
        profit_loss_assessment: "评估",
        profit_loss_match: "场次",
        profit_loss_predicted: "预测",
        profit_loss_actual: "实际",
        profit_loss_correct: "正确",
        profit_loss_prob: "概率",
        profit_loss_odds: "隐含赔率",
        profit_loss_flat_stake: "Flat 盈亏",
        profit_loss_cum_flat: "Flat 累计",
        profit_loss_kelly_stake: "Kelly 盈亏",
        profit_loss_cum_kelly: "Kelly 累计",
        profit_loss_no_points: "无盈亏数据",
        trajectory_title: "累计性能轨迹",
        trajectory_desc: "累计 accuracy/Brier/profit 趋势与变点检测",
        trajectory_fetch: "加载",
        trajectory_loading: "计算轨迹中…",
        trajectory_not_available: "暂无回测数据",
        trajectory_error: "加载轨迹失败",
        trajectory_n_matches: "比赛数",
        trajectory_final_acc: "最终准确率",
        trajectory_final_brier: "最终 Brier",
        trajectory_final_profit: "最终盈亏",
        trajectory_trend: "趋势",
        trajectory_best_win: "最佳窗口准确率",
        trajectory_worst_win: "最差窗口准确率",
        trajectory_change_points: "变点数",
        trajectory_index: "序号",
        trajectory_cum_acc: "累计准确率",
        trajectory_cum_brier: "累计 Brier",
        trajectory_cum_profit: "累计盈亏",
        trajectory_roll_acc: "滚动准确率",
        trajectory_roll_brier: "滚动 Brier",
        trajectory_date: "日期",
        trajectory_no_points: "无轨迹数据",
        difficulty_title: "比赛难度分层",
        difficulty_desc: "按预测难度分层评估模型表现",
        difficulty_fetch: "加载",
        difficulty_loading: "计算分层中…",
        difficulty_not_available: "暂无回测数据",
        difficulty_error: "加载分层失败",
        difficulty_n_matches: "比赛数",
        difficulty_overall_acc: "总体准确率",
        difficulty_overall_brier: "总体 Brier",
        difficulty_best_tier: "最佳层",
        difficulty_worst_tier: "最差层",
        difficulty_tier: "分层",
        difficulty_acc: "准确率",
        difficulty_brier: "Brier",
        difficulty_rps: "RPS",
        difficulty_log_loss: "LogLoss",
        difficulty_conf: "平均置信度",
        difficulty_cal_gap: "校准差距",
        difficulty_assessment: "评估",
        difficulty_no_tiers: "无分层数据",
    },
    en: {
        nav_overview: "Overview",
        nav_players: "Players",
        nav_compare: "Compare",
        nav_value: "Value",
        nav_matches: "Prediction",
        nav_teams: "Teams",
        nav_scouting: "Scouting",
        nav_actions: "Action Value",
        nav_reports: "Reports",
        status_label: "Local artifacts",
        app_title: "ScoutFootball Analyst Console",
        search_placeholder: "Search players, teams, reports",
        overview_kicker: "Read-only research desk",
        overview_title: "Coverage, models, scouting decisions",
        metric_player_match: "player match rows",
        metric_team_match: "team match rows",
        metric_ratings: "rating rows",
        metric_events: "event samples",
        data_health: "Data health",
        health_oof: "value OOF ready",
        health_proxy: "player match-level coverage is thin",
        health_trends: "trend metric contract pending",
        health_truth: "truth labels are still empty",
        card_players: "Player profile",
        card_players_body: "Rankings, percentiles, radar, confidence, detail cards.",
        card_value: "Value deviation",
        card_value_body: "OOF residuals, deviation boards, age and league slices.",
        card_match: "Match prediction",
        card_match_body: "1X2, score matrix, model coverage, calibration entry.",
        players_kicker: "Position profile",
        player_pool: "Player pool",
        export: "Export",
        th_rank: "Rank",
        th_player: "Player",
        th_pos: "Pos",
        th_team: "Team",
        th_rating: "Rating",
        th_conf: "Confidence",
        th_season: "Season",
        value_kicker: "OOF residual",
        value_title: "Actual value vs predicted value",
        compare_kicker: "Player Comparison",
        compare_title: "Dual radar overlay and metric diff",
        compare_note: "Select two players for side-by-side position percentile, radar dimension and key stat comparison.",
        compare_select: "Select Players",
        compare_player_a: "Player A",
        compare_player_b: "Player B",
        compare_button: "Compare",
        compare_radar_title: "Radar Comparison",
        compare_stats_title: "Key Metrics",
        compare_pct_title: "Position Percentile Comparison",
        compare_col_metric: "Metric",
        compare_col_dimension: "Dimension",
        value_rank: "Deviation board",
        undervalued: "Undervalued",
        overvalued: "Overvalued",
        match_selector: "Match selector",
        model_label: "Model",
        home_team: "Home",
        away_team: "Away",
        score_matrix: "Score matrix",
        review_queue: "Review queue",
        watchlist: "Watchlist",
        snapshot: "Snapshot",
        scouting_kicker: "Local-first decision desk",
        scouting_title: "Review, monitor, decide",
        scouting_boundary: "Server queues are read-only. Decisions stay in this browser unless local API persistence is explicitly enabled.",
        teams_kicker: "Team Strength Analysis",
        teams_title: "Aggregated Ratings & Position Group Strength",
        teams_note: "Minutes-weighted aggregation of player ratings, showing overall team strength, position group distribution and key players.",
        teams_metric_count: "Teams",
        teams_metric_avg: "Avg Rating",
        teams_metric_top: "Top Rating",
        teams_table_title: "Team Rankings",
        teams_col_team: "Team",
        teams_col_league: "League",
        teams_col_rating: "Rating",
        teams_col_squad: "Squad",
        teams_detail_title: "Team Detail",
        teams_detail_placeholder: "Select a team to view details",
        teams_chart_title: "Position Group Strength Comparison",
        teams_compare_title: "Team Comparison",
        teams_compare_a: "Team A",
        teams_compare_b: "Team B",
        teams_compare_button: "Compare",
        teams_compare_radar: "Position Group Radar",
        teams_compare_pos: "Position Group Comparison",
        teams_compare_col_group: "Group",
        scouting_metric_review: "To review",
        scouting_metric_short: "Shortlist",
        scouting_search: "Search player, team, or reason",
        scouting_status_all: "All statuses",
        scouting_local_state: "Local state",
        scout_workspace_export: "Export workspace",
        scout_workspace_import: "Import workspace",
        scout_workspace_server_save: "Save to local API",
        scout_workspace_server_load: "Load from local API",
        scout_workspace_preview_kicker: "Safe import",
        scout_workspace_preview_title: "Scouting workspace preview",
        scout_workspace_merge: "Safe merge",
        scout_workspace_replace: "Replace local",
        action_kicker: "StatsBomb sample",
        action_title: "Action-value research desk",
        action_boundary: "Current StatsBomb Open Data coverage only; samples below 450 estimated minutes are filtered by default.",
        action_search: "Search player or competition",
        action_all_competitions: "All competitions",
        action_ranking: "Action-value ranking",
        action_pipeline: "Action-value backend",
        backend_contracts: "Backend contracts",
        minutes: "Minutes",
        percentile: "Percentile",
        value: "Value",
        residual: "Residual",
        home: "Home",
        draw: "Draw",
        away: "Away",
        expected_goals: "Expected goals",
        coverage: "Coverage",
        nav_wc_schedule: "Schedule",
        nav_wc_squads: "Squads",
        nav_wc_compare: "Compare",
        nav_wc_probability: "Odds",
        nav_wc_knockout: "Knockout",
        nav_wc_tournament: "Tournament",
        wc_kicker: "2026 FIFA World Cup",
        wc_schedule_title: "Group Stage Schedule",
        wc_squads_title: "Squad Ratings",
        wc_compare_title: "Team Comparison",
        wc_prob_title: "Advancement Probability",
        wc_knockout_title: "Knockout Bracket",
        wc_tournament_title: "Tournament Simulator",
        wc_tournament_desc: "Record match results and explore qualification scenarios",
        wc_tournament_win: "Tournament Win Probability (Top 16)",
        wc_win_prob: "Win Prob.",
        wc_team_outlook: "Team Outlook",
        wc_view_outlook: "View Outlook",
        wc_outlook_group_finish: "Group Finish Probability",
        wc_outlook_group_rank: "Group Rank",
        wc_outlook_knockout_path: "Projected Knockout Path",
        wc_outlook_championship: "Championship Probability",
        wc_outlook_strength: "Squad Strength Breakdown",
        wc_outlook_coverage: "Squad Coverage",
        wc_outlook_shrunk_avg: "Shrunk Avg Rating",
        wc_outlook_core_avg: "Core Players Avg Rating",
        wc_outlook_disclaimer: "Note",
        wc_outlook_loading: "Loading...",
        wc_outlook_select_team: "Select Team",
        wc_outlook_no_data: "No outlook data available for this team",
        wc_outlook_r32: "Round of 32",
        wc_outlook_r16: "Round of 16",
        wc_outlook_qf: "Quarter-Finals",
        wc_outlook_sf: "Semi-Finals",
        wc_outlook_final: "Final",
        wc_outlook_projected_opponent: "Projected Opponent",
        wc_outlook_advance_prob: "Advance Probability",
        wc_outlook_no_opponent: "Not projected",
        wc_teams: "Teams",
        wc_groups: "Groups",
        wc_group_matches: "Group Matches",
        wc_briefing: "Pre-match briefing",
        wc_export_json: "Export briefing JSON",
        wc_export_csv: "Export briefing CSV",
        wc_fixtures: "Fixtures",
        wc_date: "Date",
        wc_time: "Time",
        wc_group_col: "Group",
        wc_home: "Home",
        wc_away_col: "Away",
        wc_venue: "Venue",
        wc_squad_list: "Squad List",
        wc_club: "Club",
        wc_league: "League",
        wc_rating_dist: "Rating Distribution",
        wc_compare_summary: "Summary",
        wc_strength_rank: "48-Team Strength Ranking",
        wc_strength: "Strength",
        wc_entertainment: "Entertainment estimate",
        wc_squad_size: "Squad",
        wc_rated: "Rated",
        wc_big5: "Big 5",
        wc_avg_rating: "Avg",
        wc_no_data: "No data",
        wc_low_coverage: "Rating coverage below 50%, low confidence",
        sort_priority: "Priority",
        sort_date: "Date",
        sort_name: "Name",
        status_pending: "Pending",
        status_reviewing: "Reviewing",
        status_approved: "Approved",
        status_rejected: "Rejected",
        scout_new_badge: "new",
        scout_note_placeholder: "Add note...",
        nav_license: "Sources",
        nav_data: "Data",
        data_kicker: "Data Status",
        data_title: "Data Sources & Coverage",
        data_sources_table: "Data Sources",
        data_th_name: "Name",
        data_th_rows: "Rows",
        data_th_updated: "Last Updated",
        data_th_type: "Type",
        data_type_real: "Real",
        data_type_proxy: "Proxy",
        data_type_synthetic: "Synthetic",
        data_coverage_league: "League Coverage",
        data_missing_warnings: "Missing Data Warnings",
        data_no_missing: "No missing data",
        data_source_real: "Real data",
        data_source_proxy: "Proxy data",
        data_source_synthetic: "Synthetic data",
        confidence_gate: "Confidence Gate",
        confidence_gate_desc: "Coverage > 0.90 = high confidence",
        coverage_league: "League Coverage",
        rated_teams: "Rated Teams",
        total_teams: "Total Teams",
        export_csv: "Export CSV",
        license_kicker: "Data Source Licenses",
        license_title: "Data Source Manifest",
        license_sources_label: "Sources",
        license_table_title: "Data Source List",
        license_th_source: "Source",
        license_th_license: "License",
        license_th_attribution: "Attribution",
        license_th_url: "URL",
        license_attribution_notice: "StatsBomb Attribution Notice",
        model_version: "Model version",
        model_comparison: "Model comparison",
        coverage_warning: "▲ coverage below 90%",
        log_loss: "Log loss",
        send_to_tactical: "Send to tactical board",
        expand_details: "Expand details",
        collapse_details: "Collapse details",
        copy_command: "Copy command",
        train_seasons: "Train seasons",
        test_seasons: "Test seasons",
        dependency_versions: "Dependency versions",
        toggle_ratings: "Toggle ratings",
        th_actions: "Actions",
        action_watchlist: "Watch",
        action_shortlist: "Short",
        action_tactical: "Tactical",
        action_compare: "Compare",
        compare_title: "Player Comparison",
        compare_select_hint: "Select two players to compare",
        compare_clear: "Clear",
        compare_dimension: "Dimension",
        compare_percentile: "Percentile",
        compare_no_same_pos: "Players have different positions; percentiles are position-relative",
        value_fairness: "Value Fairness",
        oof_residual_label: "OOF Residual",
        league_bias_label: "League Bias",
        position_bias_label: "Position Bias",
        age_curve_label: "Age Curve",
        transfermarkt_notice: "Transfermarkt data requires manual import, estimates shown",
        value_no_fairness: "No value fairness data available",
        price_band_label: "Price Band",
        price_all: "All",
        price_low: "Low (<20M)",
        price_medium: "Mid (20-80M)",
        price_high: "High (>80M)",
        age_curve_title: "Age Curve",
        same_cohort_title: "Same-Position Same-Age Comparison",
        watchlist_notes_label: "Watchlist Notes",
        generate_tactical_role: "Generate Tactical Role",
        tactical_role_label: "Tactical Role Analysis",
        nav_calibration: "Calibration",
        nav_help: "Help",
        nav_backtest: "Backtest",
        calibration_kicker: "Model calibration",
        calibration_title: "Predicted vs Actual",
        calibration_plot: "Calibration plot",
        calibration_brier: "Brier decomposition",
        calibration_low_score: "Low-score bucket analysis",
        calibration_league: "Per-league calibration",
        backtest_kicker: "Model Backtest Comparison",
        backtest_title: "Poisson vs Dixon-Coles Backtest",
        backtest_metric_desc: "Log Loss / Brier / RPS",
        backtest_metric_comparison: "Metric Comparison",
        backtest_metric: "Metric",
        backtest_dc_decay: "DC (decay)",
        backtest_winner: "Winner",
        backtest_folds: "Per-Fold Breakdown",
        backtest_calibration: "Isotonic Calibration Effect",
        backtest_fold: "Fold",
        backtest_test_matches: "Test Matches",
        backtest_not_available: "No backtest data available",
        backtest_instructions: "Run `PYTHONPATH=src uv run python -m scoutfootball backtest` to generate backtest artifacts.",
        backtest_brier_before: "Brier Before",
        backtest_brier_after: "Brier After",
        backtest_rps_before: "RPS Before",
        backtest_rps_after: "RPS After",
        backtest_n_matches: "Matches",
        backtest_no_calibration: "No isotonic calibration report available",
        backtest_fold_chart: "Per-Fold Metric Trends",
        backtest_tuning: "Decay Parameter Tuning",
        backtest_tuning_desc: "Dixon-Coles time-decay grid search",
        backtest_drift: "Calibration Drift Monitoring",
        backtest_drift_desc: "Track RPS/Brier/LogLoss drift across time windows",
        backtest_ensemble_weights: "Ensemble Weight Optimization",
        backtest_ensemble_weights_desc: "Optimal weights from backtest RPS grid search",
        backtest_calibration_comparison: "Calibration Comparison",
        backtest_calibration_comparison_desc: "Raw vs Isotonic recalibration per score line",
        ensemble_weights_not_available: "Weights not yet optimized",
        ensemble_weights_instructions: "Run `scoutfootball optimize-ensemble` to compute and cache optimal weights",
        ensemble_weights_default: "Default equal weights",
        ensemble_weights_optimized: "Optimized",
        ensemble_achieved_rps: "Achieved RPS",
        ensemble_n_matches: "Matches",
        ensemble_saved_at: "Saved at",
        calibration_comparison_not_available: "No calibration comparison data available",
        calibration_comparison_instructions: "Run `scoutfootball tune-predictions --run-backtest` to generate backtest artifacts",
        calibration_comparison_overall: "Overall Metrics",
        calibration_comparison_by_score: "Per Score Line",
        calibration_comparison_by_league: "Per League",
        calibration_comparison_league: "League",
        calibration_comparison_score_line: "Score",
        calibration_comparison_raw: "Raw",
        calibration_comparison_recalibrated: "Recalibrated",
        calibration_comparison_improvement: "Improvement%",
        calibration_comparison_n_matches: "Matches",
        prediction_attribution_title: "Prediction Factor Attribution",
        prediction_attribution_desc: "Permutation-neutralized Dixon-Coles factor contribution breakdown",
        prediction_attribution_baseline: "Baseline win prob",
        prediction_attribution_factor: "Factor",
        prediction_attribution_delta: "Δ Home win prob",
        prediction_attribution_neutralized: "Neutralized win prob",
        prediction_attribution_loading: "Computing factor attribution…",
        prediction_attribution_fetch: "Analyze Factors",
        prediction_attribution_not_available: "No attribution data available",
        prediction_attribution_instructions: "Requires sufficient team_match data to fit Dixon-Coles model",
        prediction_attribution_ci_fetch: "Confidence Interval",
        prediction_attribution_ci_loading: "Bootstrap CI computing…",
        prediction_attribution_ci_not_available: "No CI data available",
        prediction_attribution_delta_ci: "Δ 90% CI",
        prediction_attribution_delta_mean: "Δ Mean",
        prediction_diagnostics_title: "Prediction Diagnostics",
        prediction_diagnostics_desc: "Combined view of calibration, drift, and attribution",
        prediction_diagnostics_fetch: "Diagnostics",
        prediction_diagnostics_loading: "Loading diagnostics…",
        prediction_diagnostics_calibration: "Calibration",
        prediction_diagnostics_drift: "Drift",
        prediction_diagnostics_attribution: "Attribution",
        prediction_diagnostics_ci_cache: "CI Cache",
        prediction_diagnostics_stable: "Stable",
        prediction_diagnostics_drift_detected: "Drift detected",
        ensemble_attribution_title: "Ensemble Attribution",
        ensemble_attribution_desc: "Multi-model factor contributions and weighted blend",
        ensemble_attribution_fetch: "Ensemble Analysis",
        ensemble_attribution_loading: "Computing ensemble attribution…",
        ensemble_attribution_not_available: "No ensemble attribution data available",
        ensemble_attribution_weights: "Weights",
        ensemble_attribution_weights_source: "Weights source",
        ensemble_attribution_blended: "Blended",
        ensemble_attribution_per_model: "Per model",
        ensemble_attribution_drift_timeline: "Drift Timeline",
        ensemble_attribution_drift_timeline_loading: "Loading drift timeline…",
        ensemble_attribution_drift_timeline_not_available: "No drift timeline data available",
        value_bet_title: "Value Bet Analysis",
        value_bet_desc: "Model probability vs market odds EV/Kelly calculation",
        value_bet_fetch: "Analyze",
        value_bet_home_odds: "Home Win Odds",
        value_bet_draw_odds: "Draw Odds",
        value_bet_away_odds: "Away Win Odds",
        value_bet_loading: "Calculating…",
        value_bet_error: "Analysis failed",
        value_bet_outcome: "Outcome",
        value_bet_model_prob: "Model Prob",
        value_bet_odds: "Odds",
        value_bet_implied: "Implied Prob",
        value_bet_ev: "Expected Value",
        value_bet_edge: "Edge",
        value_bet_kelly: "Kelly Fraction",
        value_bet_recommendation: "Recommendation",
        value_bet_best_bet: "Best Bet",
        value_bet_no_value: "No value bet found",
        value_bet_overround: "Overround",
        value_bet_disclaimer: "Analysis uses model probabilities, not live market data. For research purposes only.",
        backtest_reliability: "Reliability Diagram",
        backtest_reliability_desc: "Predicted probability vs observed frequency calibration curve",
        backtest_reliability_fetch: "Load",
        backtest_reliability_loading: "Loading reliability diagram…",
        backtest_reliability_not_available: "No reliability diagram data available",
        backtest_reliability_ece: "ECE (Expected Calibration Error)",
        backtest_reliability_rms: "RMS Calibration Error",
        backtest_reliability_predicted: "Predicted Probability",
        backtest_reliability_observed: "Observed Frequency",
        backtest_reliability_samples: "Samples",
        model_comparison_title: "Model Comparison Dashboard",
        model_comparison_desc: "Poisson / DC / DC-Decay unified metrics on aligned prediction set",
        model_comparison_fetch: "Load",
        model_comparison_loading: "Loading model comparison...",
        model_comparison_error: "Failed to load model comparison",
        model_comparison_not_available: "No backtest data. Run scoutfootball backtest first.",
        model_comparison_n_aligned: "Aligned Matches",
        model_comparison_n_models: "Models",
        model_comparison_metric: "Metric",
        model_comparison_winner: "Winner",
        model_comparison_accuracy: "Accuracy",
        model_comparison_avg_confidence: "Avg Confidence",
        model_comparison_cal_gap: "Calibration Gap",
        scoreline_cal_title: "Score-line Calibration Matrix",
        scoreline_cal_desc: "Predicted vs actual outcome rates by score-line bucket",
        scoreline_cal_fetch: "Load",
        scoreline_cal_loading: "Loading score-line calibration...",
        scoreline_cal_error: "Failed to load score-line calibration",
        scoreline_cal_not_available: "No backtest data available",
        scoreline_cal_scoreline: "Score-line",
        scoreline_cal_n_matches: "Matches",
        scoreline_cal_outcome: "Dominant Outcome",
        scoreline_cal_avg_probs: "Avg Predicted Probs",
        scoreline_cal_actual_rates: "Actual Outcome Rates",
        scoreline_cal_outcome_summary: "Outcome Summary",
        confidence_dist_title: "Confidence Distribution Calibration",
        confidence_dist_desc: "Accuracy per confidence bucket — detects over/under-confidence",
        confidence_dist_fetch: "Load",
        confidence_dist_loading: "Loading confidence distribution...",
        confidence_dist_error: "Failed to load confidence distribution",
        confidence_dist_not_available: "No backtest data available",
        confidence_dist_bucket: "Confidence Bucket",
        confidence_dist_n_pred: "Predictions",
        confidence_dist_accuracy: "Accuracy",
        confidence_dist_avg_conf: "Avg Confidence",
        confidence_dist_cal_gap: "Calibration Gap",
        confidence_dist_overall_acc: "Overall Accuracy",
        confidence_dist_overall_conf: "Overall Confidence",
        error_analysis_title: "Prediction Error Analysis",
        error_analysis_desc: "Bucket by confidence to find worst predictions and systematic errors",
        error_analysis_fetch: "Load",
        error_analysis_loading: "Loading error analysis...",
        error_analysis_error: "Failed to load error analysis",
        error_analysis_not_available: "No backtest data available",
        error_analysis_bucket: "Confidence Bucket",
        error_analysis_n_pred: "Predictions",
        error_analysis_avg_conf: "Avg Confidence",
        error_analysis_accuracy: "Accuracy",
        error_analysis_avg_brier: "Avg Brier",
        error_analysis_avg_log_loss: "Avg LogLoss",
        error_analysis_worst_matches: "Worst Matches",
        error_analysis_overall_worst: "Overall Worst Matches",
        error_analysis_match_id: "Match ID",
        error_analysis_score: "Score",
        error_analysis_actual: "Actual",
        error_analysis_predicted: "Predicted",
        error_analysis_confidence: "Confidence",
        error_analysis_brier: "Brier",
        error_analysis_log_loss: "LogLoss",
        error_analysis_correct: "Correct",
        error_analysis_overall_acc: "Overall Accuracy",
        error_analysis_overall_brier: "Overall Brier",
        error_analysis_overall_log_loss: "Overall LogLoss",
        outcome_dist_title: "Outcome Distribution Bias",
        outcome_dist_desc: "Compare predicted vs actual 1x2 outcome distribution",
        outcome_dist_fetch: "Load",
        outcome_dist_loading: "Loading outcome distribution...",
        outcome_dist_error: "Failed to load outcome distribution",
        outcome_dist_not_available: "No backtest data available",
        outcome_dist_outcome: "Outcome",
        outcome_dist_pred_count: "Predicted Count",
        outcome_dist_pred_share: "Predicted Share",
        outcome_dist_actual_count: "Actual Count",
        outcome_dist_actual_share: "Actual Share",
        outcome_dist_gap: "Distribution Gap",
        outcome_dist_dominant_bias: "Dominant Bias",
        outcome_dist_disclaimer: "Disclaimer",
        h2h_bias_title: "H2H Historical Bias Correction",
        h2h_bias_desc: "Adjust baseline predictions using historical head-to-head results",
        h2h_bias_fetch: "Correct",
        h2h_bias_loading: "Computing H2H bias correction...",
        h2h_bias_error: "Failed to load H2H bias correction",
        h2h_bias_not_available: "No baseline prediction or H2H data available",
        h2h_bias_baseline: "Baseline Probabilities",
        h2h_bias_corrected: "Corrected Probabilities",
        h2h_bias_adjustments: "Adjustments",
        h2h_bias_h2h_rates: "H2H Historical Rates",
        h2h_bias_n_meetings: "Meetings",
        h2h_bias_applied: "Correction Applied",
        h2h_bias_not_applied: "No Correction (insufficient sample)",
        h2h_bias_disclaimer: "Disclaimer",
        h2h_bias_home_win: "Home Win",
        h2h_bias_draw: "Draw",
        h2h_bias_away_win: "Away Win",
        temporal_val_title: "Temporal Validation",
        temporal_val_desc: "Track model metric trends across time windows",
        temporal_val_fetch: "Load",
        temporal_val_loading: "Computing temporal validation...",
        temporal_val_error: "Failed to load temporal validation",
        temporal_val_not_available: "No backtest data available",
        temporal_val_n_windows: "N Windows",
        temporal_val_n_matches: "Total Matches",
        temporal_val_trend: "Trend",
        temporal_val_window: "Window",
        prob_heatmap_title: "Probability Heatmap",
        prob_heatmap_desc: "Density and accuracy across home_win vs away_win probability space",
        prob_heatmap_fetch: "Load",
        prob_heatmap_loading: "Computing probability heatmap...",
        prob_heatmap_error: "Failed to load probability heatmap",
        prob_heatmap_not_available: "No backtest data available",
        prob_heatmap_n_predictions: "N Predictions",
        prob_heatmap_grid: "Grid",
        prob_heatmap_coverage: "Coverage",
        prob_heatmap_home_bin: "Home Bin",
        prob_heatmap_away_bin: "Away Bin",
        prob_heatmap_density: "Density",
        prob_heatmap_accuracy: "Accuracy",
        prob_heatmap_confidence: "Confidence",
        staleness_title: "Model Staleness",
        staleness_desc: "Backtest data coverage window and model freshness indicator",
        staleness_fetch: "Load",
        staleness_loading: "Computing model staleness...",
        staleness_error: "Failed to load model staleness",
        staleness_not_available: "No backtest data available",
        staleness_level: "Staleness Level",
        staleness_days: "Days Since",
        staleness_backtest_start: "Backtest Start",
        staleness_backtest_end: "Backtest End",
        staleness_n_matches: "Backtest Matches",
        staleness_model_type: "Model Type",
        ci_plot_title: "Confidence Interval Plot",
        ci_plot_desc: "CI width vs confidence scatter; checks if high-confidence predictions have narrower CIs",
        ci_plot_fetch: "Load",
        ci_plot_loading: "Computing CI scatter...",
        ci_plot_error: "Failed to load CI plot",
        ci_plot_not_available: "No CI column data (bootstrap CI generation required)",
        ci_plot_n_points: "Points",
        ci_plot_avg_conf: "Avg Confidence",
        ci_plot_avg_width: "Avg CI Width",
        ci_plot_corr: "Correlation",
        ci_plot_match: "Match",
        ci_plot_conf: "Confidence",
        ci_plot_lower: "CI Lower",
        ci_plot_upper: "CI Upper",
        ci_plot_width: "CI Width",
        ci_plot_correct: "Correct",
        ci_plot_no_points: "No scatter points",
        ci_plot_truncated: "Showing first 50 of {n} rows",
        fold_comparison_title: "Fold Comparison",
        fold_comparison_desc: "Cross-validation fold metrics stability (stable/moderate/unstable)",
        fold_comparison_fetch: "Load",
        fold_comparison_loading: "Computing fold metrics...",
        fold_comparison_error: "Failed to load fold comparison",
        fold_comparison_not_available: "No fold column data (cross-validation fold assignment required)",
        fold_comparison_stability: "Stability",
        fold_comparison_n_folds: "Folds",
        fold_comparison_n_matches: "Total Matches",
        fold_comparison_acc_std: "Accuracy Std",
        fold_comparison_fold: "Fold",
        fold_comparison_n: "N",
        fold_comparison_accuracy: "Accuracy",
        fold_comparison_brier: "Brier",
        fold_comparison_rps: "RPS",
        fold_comparison_log_loss: "LogLoss",
        fold_comparison_avg_conf: "Avg Confidence",
        fold_comparison_no_folds: "No fold data",
        league_error_title: "League Error Analysis",
        league_error_desc: "Per-league error and worst predictions; identifies model performance variance across competitions",
        league_error_fetch: "Load",
        league_error_loading: "Computing league errors...",
        league_error_error: "Failed to load league error analysis",
        league_error_not_available: "No league column data (league metadata required)",
        league_error_n_leagues: "Leagues",
        league_error_n_matches: "Total Matches",
        league_error_accuracy: "Overall Accuracy",
        league_error_brier: "Overall Brier",
        league_error_avg_conf: "Avg Confidence",
        league_error_match_id: "Match ID",
        league_error_pred: "Predicted",
        league_error_actual: "Actual",
        league_error_conf: "Confidence",
        league_error_no_leagues: "No league data",
        feature_importance_title: "Feature Importance Ranking",
        feature_importance_desc: "Input features ranked by Brier separation; identifies factors most associated with prediction error",
        feature_importance_fetch: "Load",
        feature_importance_loading: "Computing feature importance...",
        feature_importance_error: "Failed to load feature importance",
        feature_importance_not_available: "No analyzable feature columns (input features must be saved during backtest)",
        feature_importance_n_features: "Features",
        feature_importance_n_matches: "Total Matches",
        feature_importance_overall_brier: "Overall Brier",
        feature_importance_top: "Top Importance",
        feature_importance_feature: "Feature",
        feature_importance_importance: "Importance",
        feature_importance_mean: "Mean",
        feature_importance_std: "Std",
        feature_importance_n: "Matches",
        feature_importance_truncated: "Showing top 20 features (of {n})",
        feature_importance_no_features: "No feature data",
        ci_coverage_title: "Confidence Band Coverage",
        ci_coverage_desc: "Validates whether bootstrap CIs achieve nominal coverage; detects under/overcoverage",
        ci_coverage_fetch: "Load",
        ci_coverage_loading: "Computing coverage...",
        ci_coverage_error: "Failed to load coverage analysis",
        ci_coverage_not_available: "No CI column data (bootstrap CI generation required)",
        ci_coverage_assessment: "Assessment",
        ci_coverage_overall: "Overall Coverage",
        ci_coverage_avg_width: "Avg CI Width",
        ci_coverage_nominal: "Nominal Level",
        ci_coverage_n_matches: "Matches",
        ci_coverage_bucket: "Bucket",
        ci_coverage_conf_range: "Confidence Range",
        ci_coverage_n: "Matches",
        ci_coverage_empirical: "Empirical Coverage",
        ci_coverage_no_buckets: "No bucket data",
        drift_heatmap_title: "Calibration Drift Heatmap",
        drift_heatmap_desc: "Time window × confidence bucket grid of Brier/RPS; pinpoints which confidence range drifts",
        drift_heatmap_fetch: "Load",
        drift_heatmap_loading: "Computing drift heatmap...",
        drift_heatmap_error: "Failed to load drift heatmap",
        drift_heatmap_not_available: "No match_date column data (match date metadata required)",
        drift_heatmap_drift: "Drift Detection",
        drift_heatmap_drift_yes: "Drift Detected",
        drift_heatmap_drift_no: "No Drift",
        drift_heatmap_n_windows: "Time Windows",
        drift_heatmap_n_buckets: "Confidence Buckets",
        drift_heatmap_n_matches: "Total Matches",
        drift_heatmap_window: "Time Window",
        drift_heatmap_conf_bucket: "Conf Bucket",
        drift_heatmap_n: "Matches",
        drift_heatmap_accuracy: "Accuracy",
        drift_heatmap_brier: "Brier",
        drift_heatmap_rps: "RPS",
        drift_heatmap_log_loss: "LogLoss",
        drift_heatmap_no_cells: "No heatmap cell data",
        momentum_kicker: "Match Momentum Prediction",
        momentum_title: "Live Win Probability Timeline",
        momentum_home_goals: "Home Goals",
        momentum_away_goals: "Away Goals",
        momentum_minute: "Current Minute",
        momentum_update: "Update",
        backtest_best_decay: "Best Decay",
        backtest_selection_metric: "Selection Metric",
        backtest_half_life: "Half-Life (days)",
        backtest_tuning_not_available: "No tuning data available",
        backtest_tuning_instructions: "Run `PYTHONPATH=src uv run python -m scoutfootball tune-predictions` to generate tuning results.",
        data_attribution: "Data Attribution & Compliance",
        run_comparison: "Model Run Comparison",
        run_compare_btn: "Compare",
        xT_label: "xT per 90",
        xT_percentile: "xT percentile",
        xT_contribution: "xT contribution",
        xT_not_available: "xT data not available",
        confidence_reason_label: "Confidence reason",
        rating_snapshot: "Rating snapshot",
        error_clustering_title: "Prediction Error Clustering",
        error_clustering_desc: "k-means clustering on worst predictions by feature signatures to surface error patterns",
        error_clustering_fetch: "Load",
        error_clustering_loading: "Computing error clustering...",
        error_clustering_not_available: "No backtest data available",
        error_clustering_error: "Failed to load error clustering",
        error_clustering_n_clusters: "Clusters",
        error_clustering_n_worst: "Worst samples",
        error_clustering_n_features: "Features",
        error_clustering_avg_brier: "Avg Brier",
        error_clustering_cluster: "Cluster",
        error_clustering_matches: "matches",
        error_clustering_brier: "Brier",
        error_clustering_accuracy: "Accuracy",
        error_clustering_conf: "Avg confidence",
        error_clustering_actual: "Dominant actual",
        error_clustering_predicted: "Dominant predicted",
        error_clustering_feature: "Feature",
        error_clustering_centroid: "Centroid z",
        error_clustering_no_clusters: "No clusters",
        data_drift_title: "Data Drift Detection",
        data_drift_desc: "KS test on feature distributions between train/holdout windows, flag drift when p<0.05",
        data_drift_fetch: "Load",
        data_drift_loading: "Computing data drift...",
        data_drift_not_available: "No backtest data available (requires match_date column)",
        data_drift_error: "Failed to load data drift",
        data_drift_ratio: "Drift ratio",
        data_drift_drifted: "Drifted features",
        data_drift_n_train: "Train samples",
        data_drift_n_holdout: "Holdout samples",
        data_drift_split_date: "Split point",
        data_drift_feature: "Feature",
        data_drift_ks: "KS statistic",
        data_drift_p_value: "p-value",
        data_drift_status: "Status",
        data_drift_train_mean: "Train mean",
        data_drift_holdout_mean: "Holdout mean",
        data_drift_drifted_yes: "Drifted",
        data_drift_drifted_no: "Stable",
        data_drift_no_features: "No feature drift data",
        ci_width_title: "Confidence Interval Width Analysis",
        ci_width_desc: "Bucketed avg CI width by confidence, flag too wide/narrow intervals",
        ci_width_fetch: "Load",
        ci_width_loading: "Computing CI width analysis...",
        ci_width_not_available: "No CI columns available (requires bootstrap CI generation)",
        ci_width_error: "Failed to load CI width analysis",
        ci_width_assessment: "Assessment",
        ci_width_avg: "Avg CI width",
        ci_width_avg_conf: "Avg confidence",
        ci_width_corr: "Width-conf correlation",
        ci_width_bucket: "Confidence bucket",
        ci_width_n: "Matches",
        ci_width_avg_width: "Avg width",
        ci_width_avg_lower: "Avg lower",
        ci_width_avg_upper: "Avg upper",
        ci_width_std: "Width std",
        ci_width_relative: "Relative width",
        ci_width_no_buckets: "No bucket data",
        stress_test_title: "Backtest Scenario Stress Test",
        stress_test_desc: "Simulate distribution shifts and measure model degradation",
        stress_test_fetch: "Load",
        stress_test_loading: "Computing stress test...",
        stress_test_not_available: "No backtest data available",
        stress_test_error: "Failed to load stress test",
        stress_test_shift_type: "Shift type",
        stress_test_shift_ratio: "Shift ratio",
        stress_test_n_shifted: "Shifted matches",
        stress_test_degradation: "Degradation score",
        stress_test_assessment: "Assessment",
        stress_test_baseline: "Baseline metrics",
        stress_test_stressed: "Stressed metrics",
        stress_test_acc_delta: "Accuracy delta",
        stress_test_brier_delta: "Brier delta",
        stress_test_rps_delta: "RPS delta",
        stress_test_conf_delta: "Confidence delta",
        stress_test_n_matches: "Matches",
        stress_test_accuracy: "Accuracy",
        stress_test_brier: "Brier",
        stress_test_rps: "RPS",
        stress_test_log_loss: "LogLoss",
        stress_test_conf: "Avg confidence",
        team_drift_title: "Per-Team Calibration Drift",
        team_drift_desc: "Track how a single team's prediction quality evolves over time",
        team_drift_fetch: "Load",
        team_drift_loading: "Computing team drift...",
        stress_test_team_input: "Team name",
        stress_test_team_input_ph: "Enter team name",
        team_drift_not_available: "No backtest data or team not found",
        team_drift_error: "Failed to load team drift",
        team_drift_team: "Team",
        team_drift_n_matches: "Total matches",
        team_drift_n_windows: "Windows",
        team_drift_drift_detected: "Drift detected",
        team_drift_drift_yes: "Drift detected",
        team_drift_drift_no: "Stable",
        team_drift_latest_brier: "Latest Brier",
        team_drift_hist_brier: "Historical avg Brier",
        team_drift_rel_change: "Relative change",
        team_drift_trend: "Trend",
        team_drift_window: "Time window",
        team_drift_n: "Matches",
        team_drift_acc: "Accuracy",
        team_drift_brier: "Brier",
        team_drift_conf: "Avg confidence",
        team_drift_no_points: "No window data (insufficient samples)",
        uncertainty_title: "Prediction Uncertainty Quantification",
        uncertainty_desc: "Per-match entropy, confidence margin, and probability dispersion",
        uncertainty_fetch: "Load",
        uncertainty_loading: "Computing uncertainty...",
        uncertainty_not_available: "No backtest data available",
        uncertainty_error: "Failed to load uncertainty analysis",
        uncertainty_avg_entropy: "Avg entropy",
        uncertainty_avg_margin: "Avg margin",
        uncertainty_avg_dispersion: "Avg dispersion",
        uncertainty_high_count: "High-uncertainty matches",
        uncertainty_high_acc: "High-uncertainty accuracy",
        uncertainty_low_acc: "Low-uncertainty accuracy",
        uncertainty_entropy_corr: "Entropy-accuracy corr",
        uncertainty_match: "Match",
        uncertainty_conf: "Confidence",
        uncertainty_entropy: "Entropy",
        uncertainty_margin: "Margin",
        uncertainty_dispersion: "Dispersion",
        uncertainty_predicted: "Predicted",
        uncertainty_actual: "Actual",
        uncertainty_correct: "Correct",
        uncertainty_label: "Label",
        uncertainty_no_points: "No uncertainty points",
        profit_loss_title: "Backtest Profit/Loss Simulation",
        profit_loss_desc: "Flat-stake and Kelly betting strategy cumulative P/L",
        profit_loss_fetch: "Load",
        profit_loss_loading: "Computing profit/loss...",
        profit_loss_not_available: "No backtest data available",
        profit_loss_error: "Failed to load P/L simulation",
        profit_loss_n_matches: "Matches",
        profit_loss_win_rate: "Win rate",
        profit_loss_flat_roi: "Flat ROI",
        profit_loss_kelly_roi: "Kelly ROI",
        profit_loss_flat_profit: "Flat total P/L",
        profit_loss_kelly_profit: "Kelly total P/L",
        profit_loss_max_dd: "Max drawdown",
        profit_loss_avg_conf: "Avg confidence",
        profit_loss_assessment: "Assessment",
        profit_loss_match: "Match",
        profit_loss_predicted: "Predicted",
        profit_loss_actual: "Actual",
        profit_loss_correct: "Correct",
        profit_loss_prob: "Probability",
        profit_loss_odds: "Implied odds",
        profit_loss_flat_stake: "Flat P/L",
        profit_loss_cum_flat: "Flat cumul",
        profit_loss_kelly_stake: "Kelly P/L",
        profit_loss_cum_kelly: "Kelly cumul",
        profit_loss_no_points: "No P/L data",
        trajectory_title: "Cumulative Performance Trajectory",
        trajectory_desc: "Cumulative accuracy/Brier/profit trends and change-point detection",
        trajectory_fetch: "Load",
        trajectory_loading: "Computing trajectory...",
        trajectory_not_available: "No backtest data available",
        trajectory_error: "Failed to load trajectory",
        trajectory_n_matches: "Matches",
        trajectory_final_acc: "Final accuracy",
        trajectory_final_brier: "Final Brier",
        trajectory_final_profit: "Final profit",
        trajectory_trend: "Trend",
        trajectory_best_win: "Best window accuracy",
        trajectory_worst_win: "Worst window accuracy",
        trajectory_change_points: "Change points",
        trajectory_index: "Index",
        trajectory_cum_acc: "Cumulative accuracy",
        trajectory_cum_brier: "Cumulative Brier",
        trajectory_cum_profit: "Cumulative profit",
        trajectory_roll_acc: "Rolling accuracy",
        trajectory_roll_brier: "Rolling Brier",
        trajectory_date: "Date",
        trajectory_no_points: "No trajectory data",
        difficulty_title: "Match Difficulty Stratification",
        difficulty_desc: "Per-difficulty-tier model performance evaluation",
        difficulty_fetch: "Load",
        difficulty_loading: "Computing stratification...",
        difficulty_not_available: "No backtest data available",
        difficulty_error: "Failed to load stratification",
        difficulty_n_matches: "Matches",
        difficulty_overall_acc: "Overall accuracy",
        difficulty_overall_brier: "Overall Brier",
        difficulty_best_tier: "Best tier",
        difficulty_worst_tier: "Worst tier",
        difficulty_tier: "Tier",
        difficulty_acc: "Accuracy",
        difficulty_brier: "Brier",
        difficulty_rps: "RPS",
        difficulty_log_loss: "LogLoss",
        difficulty_conf: "Avg confidence",
        difficulty_cal_gap: "Calibration gap",
        difficulty_assessment: "Assessment",
        difficulty_no_tiers: "No tier data",
    },
};

// ─ API configuration ─────────────────────────────────────────────────────
// Strategy: API-first with static fallback.
// - Always try the live API first.
// - If the API is unreachable (network error, timeout, 5xx), fall back to
//   the local static JSON files in /data/.
// - apiOnline tracks whether the backend is reachable so the UI can show
//   a status indicator.
const HOSTNAME = window.location.hostname || "";
const IS_VERCEL_DEMO =
    HOSTNAME === "scoutfootball.vercel.app"
    || HOSTNAME === "scoutfootball-for-world-cup.vercel.app"
    || HOSTNAME.endsWith(".vercel.app");
const API_BASE = window.__SCOUTFOOTBALL_API__
    || (IS_VERCEL_DEMO
        ? "https://scoutfootball-for-world-cup.onrender.com"
        : window.location.origin);
let apiOnline = null; // null=unknown, true=online, false=offline
let usingStaticData = false; // true when static fallback was used

// Team name → filename slug (must match scripts/export_static_frontend_data.py)
function _teamSlug(name) {
    return String(name || "").replace(/\s+/g, "_").replace(/\//g, "_");
}

// Map an API path to a local static JSON file URL.
// Returns null if no static equivalent exists.
function _staticUrlFor(apiPath) {
    // Strip query string — compare endpoints use ?a=..&b=.. but the static
    // file is a pairs list that must be searched client-side.
    const pathOnly = (apiPath || "").split("?")[0];
    const m = pathOnly.replace(/^\/+/, "/");
    const map = {
        "/health": "/data/health.json",
        "/artifacts": "/data/artifacts.json",
        "/teams": "/data/teams.json",
        "/teams/strength": "/data/team_strength.json",
        "/teams/compare": "/data/team_compare_pairs.json",
        "/ratings": "/data/ratings.json",
        "/ratings/meta": "/data/ratings_meta.json",
        "/ratings/snapshots": "/data/ratings.json",
        "/predictions/meta": "/data/predictions_meta.json",
        "/predictions/calibration": "/data/predictions_calibration.json",
        "/value-summary": "/data/value_summary.json",
        "/action-values": "/data/action_values.json",
        "/action-values/evidence": "/data/action_value_evidence.json",
        "/action-values/matches": "/data/action_value_matches.json",
        "/review-queue": "/data/review_queue.json",
        "/watchlist": "/data/watchlist.json",
        "/shortlist": "/data/shortlist.json",
        "/model-runs": "/data/model_runs.json",
        "/reports/model-runs": "/data/model_runs.json",
        "/license": "/data/artifacts.json",
        "/players": "/data/players_list.json",
        "/players/compare": "/data/player_compare_pairs.json",
        "/worldcup/teams": "/data/worldcup/teams.json",
        "/world-cup/groups": "/data/worldcup/groups.json",
        "/world-cup/schedule": "/data/worldcup/schedule.json",
        "/world-cup/predictions": "/data/worldcup/predictions.json",
        "/world-cup/knockout": "/data/worldcup/knockout.json",
        "/world-cup/match-predictions": "/data/worldcup/match_predictions.json",
        "/world-cup/match-briefings": "/data/worldcup/match_briefings.json",
        "/world-cup/group-predictions": "/data/worldcup/group_predictions.json",
        "/world-cup/predictions-index": "/data/worldcup/predictions_index.json",
    };
    if (map[m]) return map[m];
    // Squad: /world-cup/squads/<Team Name> → /data/worldcup/squads/<Team_Slug>.json
    const squad = m.match(/^\/world-cup\/squads\/(.+)$/);
    if (squad) return `/data/worldcup/squads/${encodeURIComponent(_teamSlug(decodeURIComponent(squad[1])))}.json`;
    // Player profile: use pre-exported file if available.
    const player = m.match(/^\/players?\/(.+)$/);
    if (player) return `/data/player_profiles/${encodeURIComponent(_teamSlug(decodeURIComponent(player[1])))}.json`;
    const actionEvidence = m.match(/^\/action-values\/evidence\/(.+)$/);
    if (actionEvidence) return "/data/action_value_evidence.json";
    // H2H: /predictions/<home>/<away>/h2h → pairs file (searched client-side by key)
    const h2h = m.match(/^\/predictions\/(.+)\/(.+)\/h2h$/);
    if (h2h) return "/data/h2h_pairs.json";
    // Match predictions: /predictions/<home>/<away> → generic static prediction
    const pred = m.match(/^\/predictions\/.+\/.+$/);
    if (pred) return "/data/predictions_default.json";
    return null;
}

// Fetch JSON with configurable strategy.
// On Vercel demo: static-first (instant load), then optionally refresh from API.
// On local/LAN: API-first with static fallback.
async function fetchJson(apiPath, opts) {
    const params = (opts && opts.params) || "";
    const fetchOpts = opts && opts.fetchOpts ? opts.fetchOpts : undefined;

    // Desktop app: static-first (instant load from bundled data), then refresh from API
    if (IS_VERCEL_DEMO || window.__SCOUTFOOTBALL_DESKTOP__) {
        return _fetchJsonStaticFirst(apiPath, params, fetchOpts);
    }
    return _fetchJsonApiFirst(apiPath, params, fetchOpts);
}

async function _fetchJsonStaticFirst(apiPath, params, fetchOpts) {
    const staticUrl = _staticUrlFor(apiPath);
    if (staticUrl !== null) {
        try {
            const resp = await fetch(staticUrl, fetchOpts);
            if (resp.ok) {
                const data = await resp.json();
                // Don't force apiOnline=false; let health check poll determine status
                _tryRefreshFromApi(apiPath, params, fetchOpts);
                return data;
            }
        } catch (_) { /* static failed, try API below */ }
    }
    return _fetchJsonApiFirst(apiPath, params, fetchOpts);
}

function _tryRefreshFromApi(apiPath, params, fetchOpts) {
    try {
        let url = API_BASE + apiPath;
        if (params && String(params).length > 0) url += `?${params}`;
        fetch(url, { ...fetchOpts, signal: AbortSignal.timeout(8000) })
            .then((resp) => { if (resp.ok) apiOnline = true; })
            .catch(() => {});
    } catch (_) {}
}

async function _fetchJsonApiFirst(apiPath, params, fetchOpts) {
    const apiTimeout = (fetchOpts && fetchOpts.signal) ? undefined : AbortSignal.timeout(5000);

    try {
        let url = API_BASE + apiPath;
        if (params && String(params).length > 0) url += `?${params}`;
        const resp = await fetch(url, { ...fetchOpts, signal: apiTimeout });
        if (resp.ok) {
            apiOnline = true;
            return resp.json();
        }
        // A plain static server returns 404 for API routes. When a tracked
        // static snapshot exists, continue to that fallback instead of
        // treating the 404 as a terminal API error.
        if (resp.status >= 400 && resp.status < 500 && _staticUrlFor(apiPath) === null) {
            throw new Error(`HTTP ${resp.status}`);
        }
    } catch (err) {
        if (err.message && /^HTTP [4]\d\d$/.test(err.message)) throw err;
    }

    const staticUrl = _staticUrlFor(apiPath);
    if (staticUrl !== null) {
        try {
            const resp = await fetch(staticUrl, fetchOpts);
            if (resp.ok) {
                apiOnline = false;
                usingStaticData = true;
                return resp.json();
            }
        } catch (_) {}
    }

    apiOnline = false;
    usingStaticData = false;
    throw new Error("api_and_static_unavailable");
}

let players = [];
let reviews = [];
let matches = [];
let ratingsMeta = { model_meta: {}, league_metrics: [] };
let artifactSummary = { data_health: {}, artifacts: [] };
let predictionMeta = { status: "no_data" };
let predictionCalibration = {};
let valueSummaryMeta = { sample_count: 0, metrics: {} };
let modelRuns = { count: 0, runs: [] };
let watchlistData = [];
let shortlistData = [];
let actionValueSummary = { status: "no_data", players: [], metrics: {} };
let scoutingWorkspaceCapabilities = {
    enabled: false,
    configured: false,
    local_only: true,
};
let scoutingWorkspaceServerId = null;
let scoutingWorkspaceServerRevision = null;
let actionValueEvidenceIndex = {
    status: "no_data",
    coverage: {},
    player_index: [],
    available_player_ids: [],
};
let actionValueMatchSummary = { status: "no_data", rows: [], manifest: {} };
let teamStrengthData = { count: 0, teams: [] };
let dataLoadErrors = new Set(); // tracks which data sources failed to load

async function fetchRatings(position, league) {
    const params = new URLSearchParams();
    if (position && position !== "ALL") params.set("position", position);
    if (league) params.set("league", league);
    params.set("limit", "3000");
    try {
        const data = await fetchJson("/ratings", { params });
        const rawPlayers = (data.players || []).map((p) => ({
            name: p.player || "",
            position: p.position_group || "",
            team: p.team || "",
            league: p.league || "",
            season: p.season || "",
            key: `${p.player || ""}|${p.season || ""}|${p.team || ""}`,
            rating: +(p.optimized_score || 0).toFixed(1),
            confidence: (p.confidence_level || "LOW").toUpperCase(),
            minutes: Math.round(p.minutes || 0),
            matches: Math.round(p.matches || 0),
            low_appearance: !!p.low_appearance,
            npg_p90: +(p.npg_p90 || 0).toFixed(3),
            assists_p90: +(p.assists_p90 || 0).toFixed(3),
            defense_composite: p.defense_composite,
            possession_composite: p.possession_composite,
            value: 0,
            residual: 0,
        }));

        // Compute position-relative percentiles client-side for radar
        const byPosition = {};
        for (const p of rawPlayers) {
            if (!byPosition[p.position]) byPosition[p.position] = [];
            byPosition[p.position].push(p);
        }
        function pctRank(value, arr, key) {
            const vals = arr.map((p) => p[key]).filter((v) => v != null && !isNaN(v)).sort((a, b) => a - b);
            if (vals.length === 0) return 50;
            const idx = vals.filter((v) => v < value).length;
            return Math.round(idx / vals.length * 100);
        }
        for (const p of rawPlayers) {
            const pool = byPosition[p.position] || [];
            const attack = (p.npg_p90 || 0) + (p.assists_p90 || 0);
            const attackPool = pool.map((x) => (x.npg_p90 || 0) + (x.assists_p90 || 0));
            const attackPct = attackPool.length > 0 ? Math.round(attackPool.filter((v) => v < attack).length / attackPool.length * 100) : 50;
            p.percentile = pctRank(p.rating, pool, "rating");
            p.radar = [
                attackPct,
                p.possession_composite != null ? pctRank(p.possession_composite, pool, "possession_composite") : 50,
                p.defense_composite != null ? pctRank(p.defense_composite, pool, "defense_composite") : 50,
                Math.min(100, Math.round((p.minutes || 0) / 2700 * 100)),
                p.percentile,
            ];
        }
        return rawPlayers;
    } catch (err) {
        console.warn("Failed to fetch ratings:", err);
        dataLoadErrors.add("ratings");
        return getDemoPlayers();
    }
}

function getDemoPlayers() {
    /* Fallback: no demo data — API must be online for player ratings */
    return [];
}

async function fetchRatingsMeta() {
    try {
        const data = await fetchJson("/ratings/meta");
        return data;
    } catch (err) {
        console.warn("Failed to fetch ratings meta:", err);
        return { model_meta: {}, league_metrics: [] };
    }
}

async function fetchArtifacts() {
    try {
        return await fetchJson("/artifacts");
    } catch (err) {
        console.warn("Failed to fetch artifacts:", err);
        return {};
    }
}

async function fetchTeams() {
    try {
        const data = await fetchJson("/teams");
        return data.teams || [];
    } catch (err) {
        console.warn("Failed to fetch teams:", err);
        return [];
    }
}

async function fetchTeamStrength(league) {
    const params = new URLSearchParams();
    if (league) params.set("league", league);
    params.set("limit", "200");
    try {
        const data = await fetchJson("/teams/strength", { params });
        return data;
    } catch (err) {
        console.warn("Failed to fetch team strength:", err);
        return { count: 0, teams: [] };
    }
}

async function fetchPrediction(homeTeam, awayTeam, model) {
    try {
        const modelParam = model || appState.predictionModel || "poisson";
        const data = await fetchJson(`/predictions/${encodeURIComponent(homeTeam)}/${encodeURIComponent(awayTeam)}?model=${encodeURIComponent(modelParam)}`);
        if (data) {
            data.home_team = data.home_team || homeTeam;
            data.away_team = data.away_team || awayTeam;
        }
        return data;
    } catch {
        return null;
    }
}

async function fetchPredictionMeta() {
    try {
        return await fetchJson("/predictions/meta");
    } catch (err) {
        console.warn("Failed to fetch prediction meta:", err);
        return { status: "no_data" };
    }
}

async function fetchModelRuns() {
    try {
        return await fetchJson("/reports/model-runs");
    } catch (err) {
        console.warn("Failed to fetch model runs:", err);
        return { count: 0, runs: [] };
    }
}

const modelRunDetailCache = {};

async function fetchModelRunDetail(runId) {
    if (modelRunDetailCache[runId]) return modelRunDetailCache[runId];
    try {
        const data = await fetchJson(`/reports/model-runs/${encodeURIComponent(runId)}`);
        modelRunDetailCache[runId] = data;
        return data;
    } catch (err) {
        console.warn("Failed to fetch model run detail:", err);
        return null;
    }
}

async function fetchActionValues() {
    try {
        return await fetchJson("/action-values");
    } catch (err) {
        console.warn("Failed to fetch action values:", err);
        dataLoadErrors.add("action-values");
        return { status: "no_data", players: [], metrics: {} };
    }
}

async function fetchPlayerMatchActionValues() {
    try {
        return await fetchJson("/action-values/matches");
    } catch (err) {
        console.warn("Failed to fetch player-match action values:", err);
        return { status: "no_data", rows: [], manifest: {} };
    }
}

let licenseData = { license_attribution: {}, data_source_label: "", updated_at: null };

const LICENSE_SOURCES = [
    { key: "statsbomb", name: "StatsBomb Open Data", license: "MIT / CC-BY-SA 4.0", attribution: "\u25C6 Required on public charts", url: "https://github.com/statsbomb/open-data" },
    { key: "football_data", name: "Football-Data.co.uk", license: "Free (non-commercial)", attribution: "Attribution appreciated", url: "https://www.football-data.co.uk" },
    { key: "fbref", name: "FBref", license: "Restricted (personal research)", attribution: "No redistribution", url: "https://fbref.com" },
    { key: "understat", name: "Understat", license: "Public", attribution: "Attribution appreciated", url: "https://understat.com" },
    { key: "club_elo", name: "Club Elo", license: "Public", attribution: "Attribution appreciated", url: "https://clubelo.com" },
    { key: "transfermarkt", name: "Transfermarkt", license: "Manual import only", attribution: "No automated scraping", url: "https://www.transfermarkt.com" },
];

async function fetchLicense() {
    try {
        return await fetchJson("/license");
    } catch (err) {
        console.warn("Failed to fetch license info:", err);
        return { license_attribution: {}, data_source_label: "", updated_at: null };
    }
}

let teamList = [];

function getTeams() {
    return teamList.length > 0 ? teamList : Array.from(new Set(matches.flatMap((match) => [match.home, match.away]))).sort();
}

const appState = {
    lang: "zh",
    view: "overview",
    selectedPlayerKey: "",
    position: "ALL",
    season: "ALL",
    league: "ALL",
    valueMode: "under",
    valuePriceBand: "all",
    home: "Arsenal",
    away: "Barcelona",
    predictionModel: "dixon_coles",
    charts: {},
    playerPage: 1,
    playerPageSize: 50,
    playerSortCol: "rating",
    playerSortAsc: false,
    compareKeys: [],
    scoutingQuery: "",
    scoutingStatus: "ALL",
    actionMode: "xt",
    actionQuery: "",
    actionCompetition: "ALL",
    actionTeam: "ALL",
    actionSeason: "ALL",
    actionMinMinutes: 450,
};

function t(key) {
    return i18n[appState.lang][key] || key;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;",
    }[char]));
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#96;");
}

function sanitizeCssPercent(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, Math.round(n)));
}

function csvCell(value) {
    const raw = String(value ?? "");
    const safe = /^[=+\-@\t\r]/.test(raw) ? `'${raw}` : raw;
    return `"${safe.replace(/"/g, '""')}"`;
}

function safeNum(value, decimals) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "–";
    return n.toFixed(decimals != null ? decimals : 1);
}

// SearchTypeahead: lightweight typeahead component for player/team search.
// Takes an input element (or ID), a type ("players", "teams", or "all"),
// and an optional onSelect callback. Silently degrades on API failure.
function SearchTypeahead(inputEl, type, onSelect) {
    const input = typeof inputEl === "string" ? document.getElementById(inputEl) : inputEl;
    if (!input) return null;
    if (input.dataset.typeaheadBound) return null;
    input.dataset.typeaheadBound = "1";

    type = type || "all";
    const wrapper = input.parentElement;
    if (wrapper && getComputedStyle(wrapper).position === "static") {
        wrapper.style.position = "relative";
    }

    let debounceTimer = null;
    let dropdown = null;
    let items = [];
    let activeIndex = -1;
    let suppressInput = false;

    function closeDropdown() {
        if (dropdown) {
            dropdown.remove();
            dropdown = null;
        }
        activeIndex = -1;
        items = [];
    }

    function buildItems(data) {
        const all = [];
        if (type === "players" || type === "all") {
            (data.players || []).forEach(p => {
                all.push({
                    label: p.player_name || "",
                    sub: [p.team, p.position].filter(Boolean).join(" · "),
                    value: p.player_name || "",
                    rating: p.rating,
                });
            });
        }
        if (type === "teams" || type === "all") {
            (data.teams || []).forEach(t => {
                all.push({
                    label: t.team_name || "",
                    sub: t.league || "",
                    value: t.team_name || "",
                });
            });
        }
        return all;
    }

    function renderDropdown(data) {
        closeDropdown();
        items = buildItems(data || {});

        dropdown = document.createElement("div");
        dropdown.className = "typeahead-dropdown";

        if (items.length === 0) {
            const emptyText = (typeof appState !== "undefined" && appState.lang === "en") ? "No matches found" : "无匹配结果";
            dropdown.innerHTML = `<div class="typeahead-empty">${escapeHtml(emptyText)}</div>`;
        } else {
            dropdown.innerHTML = items.map((item, i) => {
                const sub = item.sub ? `<span class="typeahead-sub">${escapeHtml(item.sub)}</span>` : "";
                const rating = item.rating != null ? `<span class="typeahead-rating">${escapeHtml(String(item.rating))}</span>` : "";
                return `<div class="typeahead-item" data-index="${escapeAttr(String(i))}">` +
                    `<span class="typeahead-label">${escapeHtml(item.label)}</span>` +
                    sub + rating +
                    `</div>`;
            }).join("");
        }

        if (wrapper) wrapper.appendChild(dropdown);

        dropdown.querySelectorAll(".typeahead-item").forEach(el => {
            el.addEventListener("mousedown", (e) => {
                e.preventDefault();
                const idx = parseInt(el.dataset.index, 10);
                selectItem(idx);
            });
        });
    }

    function selectItem(idx) {
        if (idx < 0 || idx >= items.length) return;
        const item = items[idx];
        suppressInput = true;
        input.value = item.value;
        closeDropdown();
        if (typeof onSelect === "function") onSelect(item.value, item);
    }

    function setActiveIndex(idx) {
        activeIndex = idx;
        if (!dropdown) return;
        const els = dropdown.querySelectorAll(".typeahead-item");
        els.forEach((el, i) => {
            el.classList.toggle("active", i === idx);
        });
        if (idx >= 0 && els[idx]) {
            els[idx].scrollIntoView({ block: "nearest" });
        }
    }

    async function fetchSuggestions(query) {
        try {
            const data = await fetchJson("/search?q=" + encodeURIComponent(query) + "&type=" + type + "&limit=10");
            if (input.value.trim() !== query) return;
            renderDropdown(data);
        } catch (_) {
            /* silently degrade */
        }
    }

    input.addEventListener("input", () => {
        if (suppressInput) {
            suppressInput = false;
            return;
        }
        const query = input.value.trim();
        if (query.length < 2) {
            closeDropdown();
            return;
        }
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => fetchSuggestions(query), 300);
    });

    input.addEventListener("keydown", (e) => {
        if (!dropdown || items.length === 0) {
            if (e.key === "Escape") closeDropdown();
            return;
        }
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIndex(activeIndex < items.length - 1 ? activeIndex + 1 : 0);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIndex(activeIndex > 0 ? activeIndex - 1 : items.length - 1);
        } else if (e.key === "Enter") {
            if (activeIndex >= 0) {
                e.preventDefault();
                e.stopImmediatePropagation();
                selectItem(activeIndex);
            }
        } else if (e.key === "Escape") {
            e.preventDefault();
            closeDropdown();
        }
    });

    input.addEventListener("blur", () => {
        setTimeout(closeDropdown, 150);
    });

    return { close: closeDropdown };
}

async function fetchPredictionCalibration() {
    try {
        return await fetchJson("/predictions/calibration");
    } catch (err) {
        console.warn("Failed to fetch prediction calibration:", err);
        return {};
    }
}

function formatTimestamp(value) {
    if (value == null || value === "") return "";
    const numeric = Number(value);
    const date = Number.isFinite(numeric)
        ? new Date(numeric < 1e12 ? numeric * 1000 : numeric)
        : new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString(appState.lang === "zh" ? "zh-CN" : "en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function confidenceClass(confidence) {
    if (confidence === "HIGH") return "status-high";
    if (confidence === "MEDIUM") return "status-medium";
    return "status-low";
}

function applyLocale() {
    document.documentElement.lang = appState.lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach((element) => {
        element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        element.placeholder = t(element.dataset.i18nPlaceholder);
    });
    document.getElementById("lang-toggle").textContent = appState.lang === "zh" ? "EN" : "中";
}

async function setView(view) {
    appState.view = view;
    document.querySelectorAll(".view").forEach((element) => {
        element.classList.toggle("active", element.id === `view-${view}`);
    });
    document.querySelectorAll(".nav-action[data-view]").forEach((button) => {
        const isActive = button.dataset.view === view;
        button.classList.toggle("active", isActive);
        if (isActive) {
            button.setAttribute("aria-current", "page");
        } else {
            button.removeAttribute("aria-current");
        }
    });
    requestAnimationFrame(renderActiveView);
}

function filteredPlayers() {
    const query = document.getElementById("global-search").value.trim().toLowerCase();
    return players.filter((player) => {
        const matchesPosition = appState.position === "ALL" || player.position === appState.position;
        const matchesSeason = appState.season === "ALL" || player.season === appState.season;
        const matchesLeague = appState.league === "ALL" || player.league === appState.league;
        const matchesQuery = !query || [player.name, player.team, player.position].join(" ").toLowerCase().includes(query);
        return matchesPosition && matchesSeason && matchesLeague && matchesQuery;
    });
}

function renderPlayers() {
    const sorted = filteredPlayers().sort((a, b) => {
        const col = appState.playerSortCol;
        const dir = appState.playerSortAsc ? 1 : -1;
        if (col === "rating") return dir * (a.rating - b.rating);
        const va = String(a[col] || "").toLowerCase();
        const vb = String(b[col] || "").toLowerCase();
        return dir * va.localeCompare(vb);
    });
    const total = sorted.length;
    const pageSize = appState.playerPageSize;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    appState.playerPage = Math.min(appState.playerPage, totalPages);
    const start = (appState.playerPage - 1) * pageSize;
    const rows = sorted.slice(start, start + pageSize);
    const tbody = document.getElementById("player-table");
    if (players.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--text-muted)">Loading...</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map((player, i) => {
        const index = start + i;
        const lowAppBadge = player.low_appearance
            ? `<span class="status-pill low-appearance" title="${appState.lang === 'zh' ? '出场不足20场，评分已扣减' : 'Under 20 matches, score penalized'}">${appState.lang === 'zh' ? '低出场' : 'LOW APP'}</span>`
            : '';
        return `
        <tr class="${player.key === appState.selectedPlayerKey ? "selected" : ""}${player.low_appearance ? " low-appearance-row" : ""}" data-player-key="${escapeAttr(player.key)}" style="cursor:pointer">
            <td>${index + 1}</td>
            <td>${escapeHtml(player.name)}${lowAppBadge}</td>
            <td>${escapeHtml(player.position)}</td>
            <td>${escapeHtml(player.team)}</td>
            <td>${escapeHtml(player.season)}</td>
            <td>${player.rating.toFixed(1)}</td>
            <td><span class="status-pill ${confidenceClass(player.confidence)}">${escapeHtml(player.confidence)}</span></td>
            <td class="actions-cell">
                <button class="action-btn${isInPlayerWatchlist(player.key) ? ' active' : ''}" data-action-watch="${escapeAttr(player.key)}" title="${escapeHtml(t('action_watchlist'))}" type="button">\u25A1</button>
                <button class="action-btn${isInPlayerShortlist(player.key) ? ' active' : ''}" data-action-short="${escapeAttr(player.key)}" title="${escapeHtml(t('action_shortlist'))}" type="button">\u25B3</button>
                <button class="action-btn${appState.compareKeys.includes(player.key) ? ' active' : ''}" data-action-compare="${escapeAttr(player.key)}" title="${escapeHtml(t('action_compare'))}" type="button">\u27F7</button>
                <button class="action-btn" data-action-tactical="${escapeAttr(player.key)}" title="${escapeHtml(t('action_tactical'))}" type="button">\u25CE</button>
            </td>
        </tr>`;
    }).join("");

    tbody.querySelectorAll("tr[data-player-key]").forEach((row) => {
        row.addEventListener("click", () => {
            appState.selectedPlayerKey = row.dataset.playerKey;
            renderPlayers();
            renderPlayerProfile();
        });
    });

    // Action button handlers
    tbody.querySelectorAll("[data-action-watch]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const playerKey = btn.dataset.actionWatch;
            const player = players.find((p) => p.key === playerKey);
            if (player) togglePlayerWatchlist(player);
            renderPlayers();
        });
    });
    tbody.querySelectorAll("[data-action-short]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const playerKey = btn.dataset.actionShort;
            const player = players.find((p) => p.key === playerKey);
            if (player) togglePlayerShortlist(player);
            renderPlayers();
        });
    });
    tbody.querySelectorAll("[data-action-tactical]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const playerKey = btn.dataset.actionTactical;
            const player = players.find((p) => p.key === playerKey);
            if (player) sendToTacticalBoard(player);
        });
    });
    tbody.querySelectorAll("[data-action-compare]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const playerKey = btn.dataset.actionCompare;
            const idx = appState.compareKeys.indexOf(playerKey);
            if (idx >= 0) {
                appState.compareKeys.splice(idx, 1);
            } else {
                if (appState.compareKeys.length >= 2) appState.compareKeys.shift();
                appState.compareKeys.push(playerKey);
            }
            renderPlayers();
            renderComparePanel();
        });
    });

    // Pagination controls
    const pageInfo = document.getElementById("player-page-info");
    const pageNum = document.getElementById("player-page-num");
    if (pageInfo) pageInfo.textContent = `${total} ${appState.lang === 'zh' ? '名球员' : 'players'}`;
    if (pageNum) pageNum.textContent = `${appState.playerPage}/${totalPages}`;
    const prevBtn = document.getElementById("player-prev-page");
    const nextBtn = document.getElementById("player-next-page");
    if (prevBtn) prevBtn.disabled = appState.playerPage <= 1;
    if (nextBtn) nextBtn.disabled = appState.playerPage >= totalPages;

    // Update sort indicators on headers
    document.querySelectorAll("th[data-sort]").forEach((th) => {
        const isActive = th.dataset.sort === appState.playerSortCol;
        const arrow = isActive ? (appState.playerSortAsc ? " ▲" : " ▼") : "";
        const baseText = th.getAttribute("data-i18n") ? t(th.getAttribute("data-i18n")) : th.textContent.replace(/[▲▼]/g, "").trim();
        th.textContent = baseText + arrow;
    });

    if (!rows.some((player) => player.key === appState.selectedPlayerKey) && rows[0]) {
        appState.selectedPlayerKey = rows[0].key;
    }
    renderPlayerProfile();
    renderComparePanel();
}

async function renderPlayerProfile() {
    const player = players.find((item) => item.key === appState.selectedPlayerKey) || players[0];
    if (!player) return;
    document.getElementById("selected-player-name").textContent = player.name;

    // Fetch real profile data for radar
    let profile = null;
    try {
        profile = await fetchJson(`/players/${encodeURIComponent(player.name)}?season=${player.season}`);
    } catch (err) { /* fallback to list data */ }

    const detailMinutes = profile ? profile.minutes : player.minutes;
    const detailScore = profile ? profile.optimized_score : player.rating;
    const detailPosition = profile ? profile.position_group : player.position;
    const detailMatches = profile ? profile.matches : player.matches;
    const detailLowApp = profile ? profile.low_appearance : player.low_appearance;
    const detailConfidence = profile ? profile.confidence_level : player.confidence;
    const detailLeague = profile ? profile.league : player.league;
    const lowAppWarning = detailLowApp
        ? `<div class="low-appearance-warning">${appState.lang === "zh" ? "▲ 出场不足20场，评分已扣减最多30%" : "▲ Under 20 matches, score penalized up to 30%"}</div>`
        : "";
    document.getElementById("player-detail").innerHTML = `
        <div><span>${escapeHtml(t("th_team"))}</span><strong>${escapeHtml(player.team)}</strong></div>
        <div><span>${escapeHtml(t("minutes"))}</span><strong>${escapeHtml(detailMinutes)}</strong></div>
        <div><span>${appState.lang === "zh" ? "出场" : "Matches"}</span><strong>${escapeHtml(detailMatches)}</strong></div>
        <div><span>${escapeHtml(t("th_pos"))}</span><strong>${escapeHtml(detailPosition)}</strong></div>
        <div><span>${escapeHtml(t("th_rating"))}</span><strong>${escapeHtml(detailScore)}</strong></div>
        <div><span>${appState.lang === "zh" ? "联赛" : "League"}</span><strong>${escapeHtml(detailLeague || "–")}</strong></div>
        ${/* Season trend */ (() => {
            const trend = profile ? (profile.season_trend || profile.rating_trend || null) : null;
            if (!trend) return '';
            const trendDir = typeof trend === 'string' ? trend : (trend > 0 ? 'up' : trend < 0 ? 'down' : 'stable');
            const trendSym = trendDir === 'up' ? '\u25B2' : trendDir === 'down' ? '\u25BC' : '\u25CB';
            const trendColor = trendDir === 'up' ? '#57d68d' : trendDir === 'down' ? '#ff6b6b' : 'var(--text-muted)';
            const trendLabel = appState.lang === 'zh' ? '赛季趋势' : 'Season trend';
            return `<div><span>${escapeHtml(trendLabel)}</span><strong style="color:${trendColor}">${trendSym} ${escapeHtml(trendDir)}</strong></div>`;
        })()}
        ${/* Confidence reason */ (() => {
            const reason = profile ? (profile.confidence_reason || profile.confidence_detail || '') : '';
            if (!reason) return '';
            const label = t('confidence_reason_label');
            return `<div><span>${escapeHtml(label)}</span><strong style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(reason)}</strong></div>`;
        })()}
        ${/* xT summary */ (() => {
            const xt = profile ? profile.xt_summary : null;
            if (!xt || !xt.available) {
                const label = t('xT_not_available');
                return `<div><span>${escapeHtml(t('xT_label'))}</span><strong style="color:var(--text-muted);font-size:0.82rem">N/A - ${escapeHtml(label)}</strong></div>`;
            }
            const parts = [];
            if (xt.xT_per_90 != null) parts.push(`${escapeHtml(t('xT_label'))}: ${escapeHtml(String(xt.xT_per_90))}`);
            if (xt.xT_percentile != null) parts.push(`${escapeHtml(t('xT_percentile'))}: ${escapeHtml(String(xt.xT_percentile))}pct`);
            if (xt.xT_contribution != null) parts.push(`${escapeHtml(t('xT_contribution'))}: ${escapeHtml(String(xt.xT_contribution))}`);
            if (parts.length === 0) return '';
            const note = xt.coverage_note ? ` (${escapeHtml(xt.coverage_note)})` : '';
            return `<div><span>${escapeHtml(t('xT_label'))}</span><strong style="font-size:0.82rem">${parts.join(' | ')}${note}</strong></div>`;
        })()}
        ${/* Per-90 metrics */ (() => {
            if (!profile) return '';
            const z = appState.lang === 'zh';
            const metrics = [
                { key: 'npg_p90', label: z ? '非点球进球/90' : 'Non-pen goals/90' },
                { key: 'assists_p90', label: z ? '助攻/90' : 'Assists/90' },
                { key: 'defense_composite', label: z ? '防守综合' : 'Defense composite' },
                { key: 'possession_composite', label: z ? '控球综合' : 'Possession composite' },
            ];
            const cells = metrics.map(m => {
                const v = profile[m.key];
                if (v === undefined || v === null) return '';
                const display = typeof v === 'number' ? v.toFixed(3) : escapeHtml(String(v));
                return `<div><span>${escapeHtml(m.label)}</span><strong style="font-size:1rem">${display}</strong></div>`;
            }).join('');
            if (!cells) return '';
            return `<div style="grid-column:1/-1"><span style="display:block;font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem">${z ? '每90分钟指标' : 'Per-90 Metrics'}</span><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">${cells}</div></div>`;
        })()}
        ${/* Position percentiles (all dimensions) */ (() => {
            const pcts = profile ? (profile.position_percentiles || null) : null;
            if (!pcts || typeof pcts !== 'object') return '';
            const z = appState.lang === 'zh';
            const entries = Object.entries(pcts)
                .filter(([k, v]) => v && typeof v === 'object' && v.percentile !== undefined && v.percentile !== null);
            if (entries.length === 0) return '';
            const cells = entries.map(([key, info]) => {
                const label = info.label || key;
                const pct = Math.round(info.percentile);
                const color = pct >= 80 ? '#57d68d' : pct >= 60 ? '#4f9cff' : pct >= 40 ? '#f5a623' : '#ff6b6b';
                const isOverall = key === 'overall_score';
                const highlight = isOverall ? 'border:1px solid var(--accent, #4f9cff);background:rgba(79,156,255,0.08)' : 'background:rgba(255,255,255,0.03)';
                return `<div style="text-align:center;padding:6px 4px;${highlight};border-radius:6px">
                    <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px">${escapeHtml(label)}</div>
                    <div style="font-size:1.1rem;font-weight:700;color:${color}">${pct}<span style="font-size:0.65rem;color:var(--text-muted)">pct</span></div>
                </div>`;
            }).join('');
            const header = z ? '位置各维度百分位' : 'Position Dimension Percentiles';
            return `<div style="grid-column:1/-1"><span style="display:block;font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem">${escapeHtml(header)}</span><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:6px">${cells}</div></div>`;
        })()}
        ${/* Position explanation (contribution breakdown) */ (() => {
            const pe = profile ? (profile.position_explanation || null) : null;
            if (!pe || typeof pe !== 'object') return '';
            const z = appState.lang === 'zh';
            const dimLabels = {
                attack: z ? '进攻' : 'Attack',
                defense: z ? '防守' : 'Defense',
                possession: z ? '控球' : 'Possession',
                availability: z ? '出勤' : 'Availability',
                quality: z ? '质量' : 'Quality',
                xT: 'xT',
            };
            const rows = Object.entries(pe)
                .filter(([k, v]) => v && typeof v === 'object')
                .map(([key, info]) => {
                    const label = dimLabels[key] || key;
                    const pct = info.percentile_rank;
                    const contrib = info.contribution;
                    const conf = info.confidence || '';
                    const pctStr = (pct !== undefined && pct !== null) ? Math.round(pct) + '%' : '—';
                    const contribStr = (contrib !== undefined && contrib !== null) ? Math.round(contrib * 10) / 10 + '' : '—';
                    const confColor = conf === 'HIGH' ? '#57d68d' : conf === 'MEDIUM' ? '#f5a623' : '#ff6b6b';
                    return `<tr>
                        <td style="padding:3px 6px;font-size:0.78rem">${escapeHtml(label)}</td>
                        <td style="padding:3px 6px;font-size:0.78rem;text-align:right">${pctStr}</td>
                        <td style="padding:3px 6px;font-size:0.78rem;text-align:right">${contribStr}</td>
                        <td style="padding:3px 6px;font-size:0.72rem;text-align:right;color:${confColor}">${escapeHtml(conf)}</td>
                    </tr>`;
                }).join('');
            if (!rows) return '';
            const header = z ? '评分维度拆解' : 'Rating Dimension Breakdown';
            return `<div style="grid-column:1/-1">
                <span style="display:block;font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem">${escapeHtml(header)}</span>
                <table style="width:100%;border-collapse:collapse;font-size:0.78rem">
                    <thead><tr style="border-bottom:1px solid var(--border,rgba(255,255,255,0.08))">
                        <th style="padding:3px 6px;text-align:left;font-weight:500;color:var(--text-muted)">${z ? '维度' : 'Dimension'}</th>
                        <th style="padding:3px 6px;text-align:right;font-weight:500;color:var(--text-muted)">${z ? '百分位' : 'Percentile'}</th>
                        <th style="padding:3px 6px;text-align:right;font-weight:500;color:var(--text-muted)">${z ? '贡献' : 'Contrib'}</th>
                        <th style="padding:3px 6px;text-align:right;font-weight:500;color:var(--text-muted)">${z ? '置信度' : 'Conf'}</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
        })()}
        ${/* 3-season trend */ (() => {
            const trend = profile ? (profile.trend_3seasons || null) : null;
            if (!trend || !trend.seasons || trend.seasons.length === 0) return '';
            const z = appState.lang === 'zh';
            const seasons = trend.seasons;
            const delta = trend.delta;
            const cells = seasons.map(s => {
                return `<div style="text-align:center;padding:6px 4px;background:rgba(255,255,255,0.03);border-radius:6px">
                    <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px">${escapeHtml(String(s.season))}</div>
                    <div style="font-size:1rem;font-weight:600">${escapeHtml(String(s.optimized_score))}</div>
                    <div style="font-size:0.65rem;color:var(--text-muted)">${escapeHtml(String(s.minutes))}min</div>
                </div>`;
            }).join('');
            let deltaHtml = '';
            if (delta) {
                const sc = delta.score_change;
                const scColor = sc > 0 ? '#57d68d' : sc < 0 ? '#ff6b6b' : 'var(--text-muted)';
                const scSym = sc > 0 ? '\u25B2' : sc < 0 ? '\u25BC' : '\u25CB';
                deltaHtml = `<div style="margin-top:6px;font-size:0.75rem;color:var(--text-muted)">
                    ${escapeHtml(delta.season_from)} \u2192 ${escapeHtml(delta.season_to)}:
                    <span style="color:${scColor}">${scSym} ${Math.abs(sc).toFixed(1)}</span>
                    <span style="margin-left:6px">G ${escapeHtml(String(delta.goals_change >= 0 ? '+' : ''))}${delta.goals_change.toFixed(3)}</span>
                    <span style="margin-left:6px">A ${escapeHtml(String(delta.assists_change >= 0 ? '+' : ''))}${delta.assists_change.toFixed(3)}</span>
                </div>`;
            }
            const header = z ? '近3赛季趋势' : '3-Season Trend';
            return `<div style="grid-column:1/-1">
                <span style="display:block;font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem">${escapeHtml(header)}</span>
                <div style="display:grid;grid-template-columns:repeat(${seasons.length},1fr);gap:6px">${cells}</div>
                ${deltaHtml}
            </div>`;
        })()}
        ${/* Season history table */ (() => {
            const seasons = profile ? (profile.seasons || []) : [];
            if (seasons.length === 0) return '';
            const z = appState.lang === 'zh';
            const rows = seasons.map(s => {
                return `<tr style="border-bottom:1px solid var(--border,rgba(255,255,255,0.05))">
                    <td style="padding:3px 6px;font-size:0.75rem">${escapeHtml(String(s.season || ''))}</td>
                    <td style="padding:3px 6px;font-size:0.75rem">${escapeHtml(String(s.team || ''))}</td>
                    <td style="padding:3px 6px;font-size:0.75rem">${escapeHtml(String(s.league || ''))}</td>
                    <td style="padding:3px 6px;font-size:0.75rem">${escapeHtml(String(s.position_group || ''))}</td>
                    <td style="padding:3px 6px;font-size:0.75rem;text-align:right">${escapeHtml(String(s.minutes || ''))}</td>
                    <td style="padding:3px 6px;font-size:0.75rem;text-align:right;font-weight:600">${escapeHtml(String(s.optimized_score || ''))}</td>
                </tr>`;
            }).join('');
            const header = z ? '赛季历史' : 'Season History';
            return `<div style="grid-column:1/-1">
                <span style="display:block;font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem">${escapeHtml(header)}</span>
                <div style="overflow-x:auto">
                <table style="width:100%;border-collapse:collapse;font-size:0.75rem">
                    <thead><tr style="border-bottom:1px solid var(--border,rgba(255,255,255,0.08))">
                        <th style="padding:3px 6px;text-align:left;font-weight:500;color:var(--text-muted)">${z ? '赛季' : 'Season'}</th>
                        <th style="padding:3px 6px;text-align:left;font-weight:500;color:var(--text-muted)">${z ? '球队' : 'Team'}</th>
                        <th style="padding:3px 6px;text-align:left;font-weight:500;color:var(--text-muted)">${z ? '联赛' : 'League'}</th>
                        <th style="padding:3px 6px;text-align:left;font-weight:500;color:var(--text-muted)">${z ? '位置' : 'Pos'}</th>
                        <th style="padding:3px 6px;text-align:right;font-weight:500;color:var(--text-muted)">${z ? '分钟' : 'Min'}</th>
                        <th style="padding:3px 6px;text-align:right;font-weight:500;color:var(--text-muted)">${z ? '评分' : 'Score'}</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
                </div>
            </div>`;
        })()}
        ${/* Data sources */ (() => {
            const sources = profile ? (profile.data_sources || profile.sources || []) : [];
            if (!sources || sources.length === 0) return '';
            const label = appState.lang === 'zh' ? '数据来源' : 'Data sources';
            return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(sources.join(', '))}</strong></div>`;
        })()}
        ${/* Low confidence reasons */ (() => {
            const reasons = profile ? (profile.low_confidence_reasons || []) : [];
            if (!reasons || reasons.length === 0) return '';
            const z = appState.lang === 'zh';
            const header = z ? '低置信度原因' : 'Low Confidence Reasons';
            const items = reasons.map(r => `<li style="font-size:0.75rem;color:#f5a623;margin:2px 0">${escapeHtml(String(r))}</li>`).join('');
            return `<div style="grid-column:1/-1">
                <span style="display:block;font-size:0.75rem;color:var(--text-muted);margin-bottom:0.2rem">${escapeHtml(header)}</span>
                <ul style="margin:0;padding-left:1.2rem;list-style:none">${items}</ul>
            </div>`;
        })()}
        ${/* Missing fields */ (() => {
            const missing = [];
            if (profile && profile.has_defense === false) missing.push('defense');
            if (profile && profile.has_possession === false) missing.push('possession');
            if (profile && profile.has_shooting === false) missing.push('shooting');
            if (profile && profile.has_passing === false) missing.push('passing');
            if (profile && profile.has_gk === false) missing.push('gk');
            if (missing.length === 0) return '';
            const label = appState.lang === 'zh' ? '缺失字段' : 'Missing fields';
            return `<div><span>${escapeHtml(label)}</span><strong style="color:#ff6b6b">\u25CB ${escapeHtml(missing.join(', '))}</strong></div>`;
        })()}
        ${/* Watchlist/Shortlist notes */ (() => {
            const wlNote = watchlistNotes[player.name] || "";
            const slNote = scoutShortlistNotes[player.name] || "";
            if (!wlNote && !slNote) return "";
            const label = appState.lang === "zh" ? "球探备注" : "Scout notes";
            let noteHtml = "";
            if (wlNote) noteHtml += (appState.lang === "zh" ? "观察: " : "Watch: ") + escapeHtml(wlNote);
            if (slNote) noteHtml += (noteHtml ? " | " : "") + (appState.lang === "zh" ? "候选: " : "Short: ") + escapeHtml(slNote);
            return `<div><span>${escapeHtml(label)}</span><strong style="font-size:0.82rem;color:var(--text-muted)">${noteHtml}</strong></div>`;
        })()}
        ${/* Similar players panel container */ (() => {
            const label = appState.lang === 'zh' ? '相似球员' : 'Similar Players';
            return `<div style="grid-column:1/-1;margin-top:0.5rem" id="similar-players-panel">
                <span style="display:block;font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem">${escapeHtml(label)}</span>
                <div id="similar-players-controls" style="display:flex;flex-wrap:wrap;gap:0.4rem;align-items:center;margin-bottom:0.4rem;font-size:0.72rem"></div>
                <div id="similar-players-list" style="font-size:0.78rem;color:var(--text-muted)">—</div>
            </div>`;
        })()}
    `;
    // Always remove existing warning before conditionally inserting new one
    const existing = document.getElementById("player-detail").nextElementSibling;
    if (existing && existing.classList && existing.classList.contains("low-appearance-warning")) {
        existing.remove();
    }
    if (lowAppWarning) {
        document.getElementById("player-detail").insertAdjacentHTML("afterend", lowAppWarning);
    }

    // Use real radar data from profile API, or fallback to defaults
    const radar = (profile && profile.radar) ? profile.radar : player.radar;
    renderRadar({ ...player, radar });

    // Update confidence badge with profile data if available
    const confidence = profile ? (profile.confidence_level || player.confidence) : player.confidence;
    const badge = document.getElementById("player-confidence");
    if (badge) {
        badge.textContent = confidence;
        badge.className = `status-pill ${confidenceClass(confidence)}`;
    }

    // Send to tactical board button
    const tacticalActionsEl = document.getElementById("player-tactical-actions");
    if (tacticalActionsEl) {
        const zT = appState.lang === 'zh';
        tacticalActionsEl.innerHTML = `<button class="text-button" id="btn-send-tactical" type="button" style="font-size:0.82rem;padding:0.3rem 0.6rem">\u25C6 ${zT ? '发送到战术板' : 'Send to tactical board'}</button> <button class="text-button" id="btn-export-csv" type="button" style="font-size:0.82rem;padding:0.3rem 0.6rem">${zT ? '导出报告 CSV' : 'Export report CSV'}</button> <button class="text-button" id="btn-export-json" type="button" style="font-size:0.82rem;padding:0.3rem 0.6rem">${zT ? '导出 JSON' : 'Export JSON'}</button>`;
        const sendBtn = document.getElementById("btn-send-tactical");
        if (sendBtn) {
            sendBtn.addEventListener("click", () => {
                // Create or get tactical project
                if (!tacticalProject) {
                    tacticalProject = TACTICAL_BOARD.createProject("ScoutFootball \u6218\u672f\u677f");
                }
                // Add player to tactical board
                const playerObj = {
                    type: "player",
                    x: 50,
                    y: 50,
                    radius: 3,
                    color: "#4a90d9",
                    label: escapeHtml(player.name),
                    number: String(Math.round(detailScore || player.rating || 0)),
                    rating: detailScore || player.rating || null,
                    team: player.team || "",
                    position: detailPosition || player.position || "",
                };
                tacticalProject.objects = tacticalProject.objects || [];
                tacticalProject.objects.push(playerObj);
                // Switch to tactical view
                setView("tactical");
            });
        }
        const csvBtn = document.getElementById("btn-export-csv");
        if (csvBtn) {
            csvBtn.addEventListener("click", () => {
                exportPlayerScoutingReportCSV(player, profile, {
                    score: detailScore, position: detailPosition, minutes: detailMinutes,
                    matches: detailMatches, confidence: detailConfidence, league: detailLeague,
                });
            });
        }
        const jsonBtn = document.getElementById("btn-export-json");
        if (jsonBtn) {
            jsonBtn.addEventListener("click", () => {
                exportPlayerScoutingReportJSON(player, profile, {
                    score: detailScore, position: detailPosition, minutes: detailMinutes,
                    matches: detailMatches, confidence: detailConfidence, league: detailLeague,
                });
            });
        }
    }

    // Async fetch similar players
    _fetchAndRenderSimilarPlayers(player.name, profile);
}

function _radarLabels() {
    return ["Attack", "Possession", "Defense", "Reliability", "Impact"];
}

async function _fetchAndRenderSimilarPlayers(playerName, profile) {
    const container = document.getElementById("similar-players-list");
    const controlsEl = document.getElementById("similar-players-controls");
    if (!container) return;
    const z = appState.lang === 'zh';

    // Per-player similarity filter state (persists across refetches within
    // the same player profile view).
    if (!appState.similarFilters) {
        appState.similarFilters = {
            same_position_only: true,
            league: '',
            min_minutes: '',
        };
    }

    function _buildQueryString() {
        const f = appState.similarFilters;
        const params = [`limit=8`];
        if (profile && profile.season) params.push(`season=${encodeURIComponent(profile.season)}`);
        if (!f.same_position_only) params.push(`same_position_only=false`);
        if (f.league) params.push(`league=${encodeURIComponent(f.league)}`);
        if (f.min_minutes) {
            const mm = parseFloat(f.min_minutes);
            if (!isNaN(mm) && mm > 0) params.push(`min_minutes=${mm}`);
        }
        return params.join('&');
    }

    function _renderControls() {
        if (!controlsEl) return;
        const f = appState.similarFilters;
        const posLabel = z ? '同位置' : 'Same pos';
        const leagueLabel = z ? '联赛' : 'League';
        const minMinLabel = z ? '最少分钟' : 'Min min';
        const refreshLabel = z ? '刷新' : 'Apply';
        const tPos = (profile && profile.position_group) || '';
        const posHint = tPos ? ` (${tPos})` : '';
        controlsEl.innerHTML = `
            <label style="display:inline-flex;align-items:center;gap:0.2rem;cursor:pointer">
                <input type="checkbox" id="sim-same-pos" ${f.same_position_only ? 'checked' : ''} style="margin:0">
                <span>${escapeHtml(posLabel)}${escapeHtml(posHint)}</span>
            </label>
            <label style="display:inline-flex;align-items:center;gap:0.2rem">
                <span>${escapeHtml(leagueLabel)}</span>
                <input type="text" id="sim-league" value="${escapeAttr(f.league || '')}" placeholder="${z ? '如 La Liga' : 'e.g. La Liga'}" style="width:90px;font-size:0.72rem;padding:0.15rem 0.3rem">
            </label>
            <label style="display:inline-flex;align-items:center;gap:0.2rem">
                <span>${escapeHtml(minMinLabel)}</span>
                <input type="number" id="sim-min-min" value="${escapeAttr(f.min_minutes || '')}" placeholder="0" min="0" step="100" style="width:60px;font-size:0.72rem;padding:0.15rem 0.3rem">
            </label>
            <button class="text-button" id="sim-apply" type="button" style="font-size:0.7rem;padding:0.15rem 0.5rem">${escapeHtml(refreshLabel)}</button>
        `;
        const applyBtn = document.getElementById('sim-apply');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                const samePos = document.getElementById('sim-same-pos');
                const league = document.getElementById('sim-league');
                const minMin = document.getElementById('sim-min-min');
                appState.similarFilters.same_position_only = samePos ? samePos.checked : true;
                appState.similarFilters.league = league ? league.value.trim() : '';
                appState.similarFilters.min_minutes = minMin ? minMin.value.trim() : '';
                _fetchAndRenderSimilarPlayers(playerName, profile);
            });
        }
    }

    _renderControls();

    try {
        const data = await fetchJson(`/players/${encodeURIComponent(playerName)}/similar?${_buildQueryString()}`);
        if (data.error || !data.similar || data.similar.length === 0) {
            const errMsg = data.error === 'pool_too_small'
                ? (z ? '候选池过小' : 'Candidate pool too small')
                : data.error === 'zero_vector'
                    ? (z ? '目标特征向量为零' : 'Target feature vector is zero')
                    : (z ? '无相似球员数据' : 'No similar players found');
            container.textContent = errMsg;
            return;
        }
        const target = data.target || {};
        let html = '<div style="display:flex;flex-wrap:wrap;gap:0.4rem">';
        for (const p of data.similar) {
            const simColor = p.similarity >= 80 ? 'var(--accent)' : p.similarity >= 60 ? '#5b9fd6' : 'var(--text-muted)';
            const strengths = (p.shared_strengths || []).length > 0
                ? `<span style="font-size:0.65rem;color:var(--accent)">+${escapeHtml(p.shared_strengths.join('/'))}</span>` : '';
            const weaknesses = (p.shared_weaknesses || []).length > 0
                ? `<span style="font-size:0.65rem;color:#ff6b6b">-${escapeHtml(p.shared_weaknesses.join('/'))}</span>` : '';
            const posBadge = p.position_group && p.position_group !== (target.position_group || '')
                ? `<span style="font-size:0.6rem;background:rgba(91,159,214,0.2);padding:0.05rem 0.3rem;border-radius:4px;margin-left:0.2rem">${escapeHtml(p.position_group)}</span>` : '';
            html += `<div class="similar-player-card" data-player="${escapeAttr(p.name)}" style="cursor:pointer;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:0.4rem 0.5rem;min-width:120px;background:rgba(255,255,255,0.03)">
                <div style="font-weight:600;font-size:0.8rem">${escapeHtml(p.name)}${posBadge}</div>
                <div style="font-size:0.68rem;color:var(--text-muted)">${escapeHtml(p.team || '')} · ${escapeHtml(p.league || '')}</div>
                <div style="font-size:0.75rem;color:${simColor};font-weight:600">${p.similarity.toFixed(0)}% ${z ? '相似' : 'sim.'}</div>
                <div style="font-size:0.68rem;color:var(--text-muted)">${z ? '评分' : 'Rating'} ${p.optimized_score != null ? p.optimized_score.toFixed(1) : '—'}</div>
                ${strengths}${weaknesses}
            </div>`;
        }
        html += '</div>';

        // Feature weights disclosure (collapsed by default).
        if (data.feature_weights) {
            const weightsLabel = z ? '位置权重' : 'Position weights';
            const weightsEntries = Object.entries(data.feature_weights)
                .map(([k, v]) => `<span style="display:inline-block;margin-right:0.4rem;font-size:0.65rem"><strong>${escapeHtml(k)}</strong>: ${v.toFixed(2)}</span>`)
                .join('');
            html += `<details style="margin-top:0.4rem"><summary style="font-size:0.7rem;color:var(--text-muted);cursor:pointer">${escapeHtml(weightsLabel)}</summary><div style="margin-top:0.2rem">${weightsEntries}</div></details>`;
        }

        const csvLabel = z ? '导出 CSV' : 'Export CSV';
        html += `<button class="text-button" id="btn-export-similar-csv" type="button" style="font-size:0.72rem;padding:0.2rem 0.5rem;margin-top:0.4rem">${csvLabel}</button>`;
        container.innerHTML = html;

        // Click to view player
        container.querySelectorAll('.similar-player-card').forEach(card => {
            card.addEventListener('click', () => {
                const name = card.getAttribute('data-player');
                if (!name) return;
                const match = players.find(p => p.name === name || p.key === name);
                if (match) {
                    appState.selectedPlayerKey = match.key;
                    renderPlayerProfile();
                } else {
                    // If not in current list, try searching via compare input
                    const compareA = document.getElementById('compare-input-a');
                    if (compareA) compareA.value = name;
                }
            });
        });

        // CSV export
        const csvBtn = document.getElementById('btn-export-similar-csv');
        if (csvBtn) {
            csvBtn.addEventListener('click', () => {
                const headers = ['name', 'team', 'league', 'season', 'position_group', 'optimized_score', 'similarity', 'shared_strengths', 'shared_weaknesses', 'minutes'];
                const rows = [headers.join(',')];
                for (const p of data.similar) {
                    rows.push(headers.map(h => {
                        let val = p[h];
                        if (Array.isArray(val)) val = val.join(';');
                        return csvCell(String(val != null ? val : ''));
                    }).join(','));
                }
                const targetName = target.name || playerName;
                const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `similar_${targetName.replace(/\s+/g, '_')}.csv`;
                a.click();
                URL.revokeObjectURL(a.href);
            });
        }
    } catch (err) {
        container.textContent = z ? '加载失败' : 'Load failed';
    }
}

function _buildScoutingReport(player, profile, detail) {
    const radar = (profile && profile.radar) ? profile.radar : (player.radar || []);
    const radarLabels = _radarLabels();
    const radarEntries = radarLabels.map((label, i) => ({
        label,
        value: radar[i] != null ? Math.round(radar[i]) : null,
    }));

    const percentiles = [];
    if (profile && profile.position_percentiles && typeof profile.position_percentiles === "object") {
        for (const [key, val] of Object.entries(profile.position_percentiles)) {
            if (val && val.percentile != null) {
                percentiles.push({ dimension: key, label: val.label || key, percentile: Math.round(val.percentile) });
            }
        }
    }

    const xtSummary = (profile && profile.xt_summary) ? profile.xt_summary : {};
    const trend = (profile && profile.trend_3seasons) ? profile.trend_3seasons : {};
    const trendSeasons = Array.isArray(trend.seasons) ? trend.seasons : [];
    const trendDelta = trend.delta || {};
    const lowConfReasons = Array.isArray(profile && profile.low_confidence_reasons) ? profile.low_confidence_reasons : [];
    const seasonsHistory = Array.isArray(profile && profile.seasons) ? profile.seasons : [];
    const shortlistDossier = getShortlistDossier({
        player_id: player.player_id || profile && profile.player_id,
        key: player.key,
        name: player.name,
    });

    return {
        player: player.name || "",
        team: player.team || "",
        position: detail.position || player.position || "",
        rating: detail.score != null ? Math.round(detail.score * 10) / 10 : (player.rating || ""),
        confidence: detail.confidence || (profile ? profile.confidence_level : "") || "",
        season: player.season || (profile ? profile.season : "") || "",
        minutes: detail.minutes ?? (profile ? profile.minutes : "") ?? "",
        matches: detail.matches ?? (profile ? profile.matches : "") ?? "",
        league: detail.league || (profile ? profile.league : "") || "",
        npg_p90: profile ? profile.npg_p90 : null,
        assists_p90: profile ? profile.assists_p90 : null,
        defense_composite: profile ? profile.defense_composite : null,
        possession_composite: profile ? profile.possession_composite : null,
        radar: radarEntries,
        position_percentiles: percentiles,
        xt_summary: {
            available: xtSummary.available || false,
            xT_per_90: xtSummary.xT_per_90 ?? null,
            xT_total: xtSummary.xT_total ?? null,
            xT_percentile: xtSummary.xT_percentile ?? null,
            coverage_note: xtSummary.coverage_note || "",
        },
        trend_3seasons: trendSeasons.map(s => ({
            season: s.season || "",
            team: s.team || "",
            score: s.optimized_score ?? null,
            minutes: s.minutes ?? null,
        })),
        trend_delta: {
            season_from: trendDelta.season_from || "",
            season_to: trendDelta.season_to || "",
            score_change: trendDelta.score_change ?? null,
            goals_change: trendDelta.goals_change ?? null,
            assists_change: trendDelta.assists_change ?? null,
            minutes_change: trendDelta.minutes_change ?? null,
        },
        low_confidence_reasons: lowConfReasons,
        seasons_history: seasonsHistory.map(s => ({
            season: s.season || "",
            team: s.team || "",
            league: s.league || "",
            position_group: s.position_group || "",
            score: s.optimized_score ?? null,
            minutes: s.minutes ?? null,
        })),
        watchlist_note: watchlistNotes[player.name] || "",
        shortlist_note: shortlistDossier.rationale,
        shortlist_dossier: shortlistDossier,
        exported_at: new Date().toISOString(),
        app_version: APP_VERSION,
    };
}

function exportPlayerScoutingReportCSV(player, profile, detail) {
    const report = _buildScoutingReport(player, profile, detail);
    const lines = [];
    const safeName = (player.name || "player").replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]/g, "_");

    // Section 1: Profile
    lines.push(["# Scouting Report"]);
    lines.push(["field", "value"]);
    lines.push(["player", report.player]);
    lines.push(["team", report.team]);
    lines.push(["position", report.position]);
    lines.push(["rating", report.rating]);
    lines.push(["confidence", report.confidence]);
    lines.push(["season", report.season]);
    lines.push(["minutes", report.minutes]);
    lines.push(["matches", report.matches]);
    lines.push(["league", report.league]);
    lines.push(["npg_p90", report.npg_p90 ?? ""]);
    lines.push(["assists_p90", report.assists_p90 ?? ""]);
    lines.push(["defense_composite", report.defense_composite ?? ""]);
    lines.push(["possession_composite", report.possession_composite ?? ""]);
    lines.push([]);

    // Section 2: Radar
    lines.push(["# Radar (0-100 percentile)"]);
    lines.push(["dimension", "value"]);
    for (const r of report.radar) {
        lines.push([r.label, r.value ?? ""]);
    }
    lines.push([]);

    // Section 3: Position percentiles
    if (report.position_percentiles.length > 0) {
        lines.push(["# Position Percentiles"]);
        lines.push(["dimension_key", "label", "percentile"]);
        for (const p of report.position_percentiles) {
            lines.push([p.dimension, p.label, p.percentile]);
        }
        lines.push([]);
    }

    // Section 4: xT summary
    if (report.xt_summary.available || report.xt_summary.xT_per_90 != null) {
        lines.push(["# xT Summary"]);
        lines.push(["field", "value"]);
        lines.push(["available", report.xt_summary.available]);
        lines.push(["xT_per_90", report.xt_summary.xT_per_90 ?? ""]);
        lines.push(["xT_total", report.xt_summary.xT_total ?? ""]);
        lines.push(["xT_percentile", report.xt_summary.xT_percentile ?? ""]);
        if (report.xt_summary.coverage_note) lines.push(["coverage_note", report.xt_summary.coverage_note]);
        lines.push([]);
    }

    // Section 5: 3-season trend
    if (report.trend_3seasons.length > 0) {
        lines.push(["# 3-Season Trend"]);
        lines.push(["season", "team", "score", "minutes"]);
        for (const s of report.trend_3seasons) {
            lines.push([s.season, s.team, s.score ?? "", s.minutes ?? ""]);
        }
        const d = report.trend_delta;
        if (d.season_from) {
            lines.push(["delta_from", d.season_from, "", ""]);
            lines.push(["delta_to", d.season_to, "", ""]);
            lines.push(["score_change", d.score_change ?? "", "", ""]);
            lines.push(["goals_change", d.goals_change ?? "", "", ""]);
            lines.push(["assists_change", d.assists_change ?? "", "", ""]);
            lines.push(["minutes_change", d.minutes_change ?? "", "", ""]);
        }
        lines.push([]);
    }

    // Section 6: Low confidence reasons
    if (report.low_confidence_reasons.length > 0) {
        lines.push(["# Low Confidence Reasons"]);
        lines.push(["reason"]);
        for (const r of report.low_confidence_reasons) {
            lines.push([r]);
        }
        lines.push([]);
    }

    // Section 7: Browser-local scouting decision context
    if (report.watchlist_note || report.shortlist_note || report.shortlist_dossier.target_role) {
        lines.push(["# Browser-local Scouting Decision"]);
        lines.push(["field", "value"]);
        if (report.watchlist_note) lines.push(["watchlist", report.watchlist_note]);
        lines.push(["priority", report.shortlist_dossier.priority]);
        lines.push(["recommendation", report.shortlist_dossier.recommendation]);
        if (report.shortlist_dossier.target_role) lines.push(["target_role", report.shortlist_dossier.target_role]);
        if (report.shortlist_note) lines.push(["rationale_and_risks", report.shortlist_note]);
        lines.push([]);
    }

    // Section 8: Season history
    if (report.seasons_history.length > 0) {
        lines.push(["# Season History"]);
        lines.push(["season", "team", "league", "position_group", "score", "minutes"]);
        for (const s of report.seasons_history) {
            lines.push([s.season, s.team, s.league, s.position_group, s.score ?? "", s.minutes ?? ""]);
        }
        lines.push([]);
    }

    lines.push(["# Exported", report.exported_at, "ScoutFootball v" + report.app_version]);

    const csv = lines.map(r => r.map(csvCell).join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeName}_scouting_report.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

function exportPlayerScoutingReportJSON(player, profile, detail) {
    const report = _buildScoutingReport(player, profile, detail);
    const json = JSON.stringify(report, null, 2);
    const blob = new Blob([json], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(player.name || "player").replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]/g, "_")}_scouting_report.json`;
    link.click();
    URL.revokeObjectURL(url);
}

function exportPlayerProfileCSV(player, profile, detailScore, detailPosition, detailMinutes, detailMatches, detailConfidence, detailLeague) {
    // Legacy entry point: delegates to the new report exporter.
    exportPlayerScoutingReportCSV(player, profile, {
        score: detailScore, position: detailPosition, minutes: detailMinutes,
        matches: detailMatches, confidence: detailConfidence, league: detailLeague,
    });
}

function getChart(id) {
    if (!window.echarts) {
        const element = document.getElementById(id);
        if (element && !element.textContent) element.textContent = "Chart runtime unavailable.";
        return null;
    }
    const element = document.getElementById(id);
    if (!element) return null;
    // Don't init on hidden containers - will have zero dimensions
    if (element.offsetParent === null) return null;
    const existing = appState.charts[id];
    if (existing) {
        try {
            if (existing.isDisposed && existing.isDisposed()) {
                delete appState.charts[id];
            } else if (existing.getDom && existing.getDom() !== element) {
                existing.dispose();
                delete appState.charts[id];
            }
        } catch {
            delete appState.charts[id];
        }
    }
    if (!appState.charts[id]) {
        const adopted = echarts.getInstanceByDom(element);
        appState.charts[id] = adopted || echarts.init(element);
    }
    return appState.charts[id];
}

function chartTextColor() {
    return document.body.classList.contains("dark-mode") ? "rgba(247,248,251,.68)" : "rgba(21,23,28,.65)";
}

function chartGridColor() {
    return document.body.classList.contains("dark-mode") ? "rgba(247,248,251,.13)" : "rgba(21,23,28,.12)";
}

function renderRadar(player) {
    const chart = getChart("radar-chart");
    if (!chart) return;
    chart.setOption({
        radar: {
            indicator: [
                { name: appState.lang === "zh" ? "进攻" : "Attack", max: 100 },
                { name: appState.lang === "zh" ? "控球" : "Possession", max: 100 },
                { name: appState.lang === "zh" ? "防守" : "Defense", max: 100 },
                { name: appState.lang === "zh" ? "可靠性" : "Reliability", max: 100 },
                { name: appState.lang === "zh" ? "影响力" : "Impact", max: 100 },
            ],
            shape: "circle",
            axisName: { color: chartTextColor(), fontWeight: 700 },
            splitLine: { lineStyle: { color: chartGridColor() } },
            axisLine: { lineStyle: { color: chartGridColor() } },
            splitArea: { show: false },
        },
        series: [{
            type: "radar",
            data: [{
                value: player.radar,
                name: player.name,
                areaStyle: { color: "rgba(255,255,255,.08)" },
                lineStyle: { color: chartTextColor(), width: 2 },
                itemStyle: { color: chartTextColor() },
            }],
        }],
    });
    requestAnimationFrame(() => {
        chart.resize();
        // Second resize after paint to catch any late layout shifts
        requestAnimationFrame(() => chart.resize());
    });
}

function renderComparePanel() {
    const panel = document.getElementById("compare-panel");
    if (!panel) return;
    const z = appState.lang === "zh";

    if (appState.compareKeys.length < 2) {
        panel.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:1.5rem 0;font-size:0.85rem">${escapeHtml(t("compare_select_hint"))}</div>`;
        return;
    }

    const p1 = players.find((p) => p.key === appState.compareKeys[0]);
    const p2 = players.find((p) => p.key === appState.compareKeys[1]);
    if (!p1 || !p2) {
        panel.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:1.5rem 0;font-size:0.85rem">${escapeHtml(t("compare_select_hint"))}</div>`;
        return;
    }

    const radarLabels = [
        z ? "进攻" : "Attack",
        z ? "控球" : "Possession",
        z ? "防守" : "Defense",
        z ? "可靠性" : "Reliability",
        z ? "影响力" : "Impact",
    ];

    // Info cards
    let html = `<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.8rem;gap:0.5rem">`;
    html += `<div style="flex:1;text-align:center;padding:0.4rem 0.6rem;border-radius:8px;background:rgba(74,144,217,.12)">`;
    html += `<div style="font-weight:700;font-size:0.95rem">${escapeHtml(p1.name)}</div>`;
    html += `<div style="font-size:0.78rem;color:var(--text-muted)">${escapeHtml(p1.team)} · ${escapeHtml(p1.position)}</div>`;
    html += `<div style="font-size:1.1rem;font-weight:700;margin-top:0.2rem">${p1.rating.toFixed(1)}</div>`;
    html += `</div>`;
    html += `<div style="flex:0 0 auto;align-self:center;font-size:0.8rem;color:var(--text-muted);font-weight:700">VS</div>`;
    html += `<div style="flex:1;text-align:center;padding:0.4rem 0.6rem;border-radius:8px;background:rgba(255,159,67,.12)">`;
    html += `<div style="font-weight:700;font-size:0.95rem">${escapeHtml(p2.name)}</div>`;
    html += `<div style="font-size:0.78rem;color:var(--text-muted)">${escapeHtml(p2.team)} · ${escapeHtml(p2.position)}</div>`;
    html += `<div style="font-size:1.1rem;font-weight:700;margin-top:0.2rem">${p2.rating.toFixed(1)}</div>`;
    html += `</div>`;
    html += `</div>`;

    // Position mismatch warning
    if (p1.position !== p2.position) {
        html += `<div style="font-size:0.72rem;color:#ff9f43;margin-bottom:0.5rem;text-align:center">${escapeHtml(t("compare_no_same_pos"))}</div>`;
    }

    // Radar chart container
    html += `<div id="compare-radar-chart" class="chart-box" style="height:260px"></div>`;

    // Percentile comparison table
    html += `<div style="margin-top:0.6rem;overflow-x:auto"><table style="width:100%;font-size:0.78rem;border-collapse:collapse">`;
    html += `<thead><tr style="border-bottom:1px solid var(--glass-border)">`;
    html += `<th style="text-align:left;padding:0.3rem 0.4rem;color:var(--text-muted)">${escapeHtml(t("compare_dimension"))}</th>`;
    html += `<th style="text-align:center;padding:0.3rem 0.4rem">${escapeHtml(p1.name)}</th>`;
    html += `<th style="text-align:center;padding:0.3rem 0.4rem">${escapeHtml(p2.name)}</th>`;
    html += `<th style="text-align:center;padding:0.3rem 0.4rem">${z ? "差值" : "Diff"}</th>`;
    html += `</tr></thead><tbody>`;

    const r1 = p1.radar || [50, 50, 50, 50, 50];
    const r2 = p2.radar || [50, 50, 50, 50, 50];
    for (let i = 0; i < radarLabels.length; i++) {
        const v1 = r1[i] ?? 0;
        const v2 = r2[i] ?? 0;
        const diff = v1 - v2;
        const diffColor = diff > 0 ? "#57d68d" : diff < 0 ? "#ff6b6b" : "var(--text-muted)";
        html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05)">`;
        html += `<td style="padding:0.3rem 0.4rem">${escapeHtml(radarLabels[i])}</td>`;
        html += `<td style="text-align:center;padding:0.3rem 0.4rem">${Math.round(v1)}pct</td>`;
        html += `<td style="text-align:center;padding:0.3rem 0.4rem">${Math.round(v2)}pct</td>`;
        html += `<td style="text-align:center;padding:0.3rem 0.4rem;color:${diffColor}">${diff > 0 ? "+" : ""}${Math.round(diff)}</td>`;
        html += `</tr>`;
    }

    // Extra metrics rows
    const extraMetrics = [
        { label: z ? "非点球进球/90" : "NPG p90", k: "npg_p90" },
        { label: z ? "助攻/90" : "Assists p90", k: "assists_p90" },
        { label: z ? "分钟" : "Minutes", k: "minutes" },
        { label: z ? "出场" : "Matches", k: "matches" },
    ];
    for (const m of extraMetrics) {
        const v1 = p1[m.k] ?? 0;
        const v2 = p2[m.k] ?? 0;
        const diff = v1 - v2;
        const diffColor = diff > 0 ? "#57d68d" : diff < 0 ? "#ff6b6b" : "var(--text-muted)";
        html += `<tr style="border-bottom:1px solid rgba(255,255,255,.05)">`;
        html += `<td style="padding:0.3rem 0.4rem">${escapeHtml(m.label)}</td>`;
        html += `<td style="text-align:center;padding:0.3rem 0.4rem">${typeof v1 === "number" ? (m.k === "npg_p90" || m.k === "assists_p90" ? v1.toFixed(3) : v1) : escapeHtml(String(v1))}</td>`;
        html += `<td style="text-align:center;padding:0.3rem 0.4rem">${typeof v2 === "number" ? (m.k === "npg_p90" || m.k === "assists_p90" ? v2.toFixed(3) : v2) : escapeHtml(String(v2))}</td>`;
        html += `<td style="text-align:center;padding:0.3rem 0.4rem;color:${diffColor}">${diff > 0 ? "+" : ""}${(m.k === "npg_p90" || m.k === "assists_p90") ? diff.toFixed(3) : Math.round(diff)}</td>`;
        html += `</tr>`;
    }

    html += `</tbody></table></div>`;

    // Clear button
    html += `<div style="text-align:center;margin-top:0.6rem"><button class="text-button" id="btn-clear-compare" type="button" style="font-size:0.78rem;padding:0.25rem 0.6rem">${escapeHtml(t("compare_clear"))}</button></div>`;

    panel.innerHTML = html;

    // Render comparison radar
    requestAnimationFrame(() => {
        const chartEl = document.getElementById("compare-radar-chart");
        if (chartEl && window.echarts) {
            const chart = echarts.init(chartEl);
            appState.charts["compare-radar-chart"] = chart;
            chart.setOption({
                radar: {
                    indicator: radarLabels.map((name) => ({ name, max: 100 })),
                    shape: "circle",
                    axisName: { color: chartTextColor(), fontWeight: 700, fontSize: 11 },
                    splitLine: { lineStyle: { color: chartGridColor() } },
                    axisLine: { lineStyle: { color: chartGridColor() } },
                    splitArea: { show: false },
                },
                series: [{
                    type: "radar",
                    data: [
                        {
                            value: r1,
                            name: p1.name,
                            areaStyle: { color: "rgba(74,144,217,.18)" },
                            lineStyle: { color: "#4a90d9", width: 2 },
                            itemStyle: { color: "#4a90d9" },
                        },
                        {
                            value: r2,
                            name: p2.name,
                            areaStyle: { color: "rgba(255,159,67,.18)" },
                            lineStyle: { color: "#ff9f43", width: 2 },
                            itemStyle: { color: "#ff9f43" },
                        },
                    ],
                }],
            });
            requestAnimationFrame(() => chart.resize());
        }

        // Clear button handler
        const clearBtn = document.getElementById("btn-clear-compare");
        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                appState.compareKeys = [];
                renderPlayers();
                renderComparePanel();
            });
        }
    });
}

let valuePlayers = [];
let valueStratification = {};

// No mock value data — API must be online for value report

async function fetchValueReport() {
    try {
        const data = await fetchJson("/value-summary");
        valueSummaryMeta = data;
        // Prefer dedicated stratification fields, fall back to nested
        // structure from newer API payloads.
        if (data && typeof data === "object") {
            valueStratification = data.stratification || {};
        }
        if (data.players && data.players.length > 0) {
            return data.players.map((p) => ({
                name: p.player || "",
                team: p.team || "",
                season: p.season || "",
                league: p.league || "",
                positionGroup: p.position_group || "",
                age: p.age ?? null,
                ageBand: p.age_band || "",
                priceBand: p.price_band || "",
                actualValue: p.actual_value || 0,
                predictedValue: p.predicted_value || 0,
                residual: p.residual_log || 0,
                fairness: p.fairness_label || "",
            }));
        }
        return [];
    } catch (err) {
        console.warn("Failed to fetch value report:", err);
        return [];
    }
}

async function fetchPlayerComparison(a, b) {
    try {
        const data = await fetchJson(`/players/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
        // Static fallback returns a pairs list; find the matching pair client-side.
        if (data && Array.isArray(data.pairs)) {
            const aLower = a.toLowerCase();
            const bLower = b.toLowerCase();
            const pair = data.pairs.find(p => {
                const na = (p.player_a && p.player_a.name || "").toLowerCase();
                const nb = (p.player_b && p.player_b.name || "").toLowerCase();
                return (na === aLower && nb === bLower) || (na === bLower && nb === aLower);
            });
            if (pair) return pair;
            return { error: "对比数据离线不可用" };
        }
        return data;
    } catch (err) {
        console.warn("Failed to fetch comparison:", err);
        return { error: "Failed to load comparison" };
    }
}

async function fetchHeadToHead(home, away) {
    try {
        const data = await fetchJson(`/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/h2h`);
        // Static fallback returns a pairs object keyed by "Home_Away"; try both orderings.
        if (data && !data.head_to_head && typeof data === "object" && !Array.isArray(data)) {
            const pairs = data.pairs && typeof data.pairs === "object" ? data.pairs : data;
            const aliases = data.team_aliases && typeof data.team_aliases === "object"
                ? data.team_aliases
                : {};
            const slug = (s) => {
                const raw = _teamSlug(s);
                return aliases[raw.toLowerCase()] || raw;
            };
            const key1 = `${slug(home)}_${slug(away)}`;
            const key2 = `${slug(away)}_${slug(home)}`;
            if (pairs[key1]) return pairs[key1];
            if (pairs[key2]) return pairs[key2];
            return { error: "H2H data not available offline for this pair" };
        }
        return data;
    } catch (err) {
        console.warn("Failed to fetch head-to-head:", err);
        return { error: "Failed to load head-to-head" };
    }
}

function _h2hResultBadge(match, queriedHomeTeam) {
    const perspectiveResult = String(match.queried_home_result || "").toUpperCase();
    if (["W", "D", "L"].includes(perspectiveResult)) return perspectiveResult;
    const ftr = String(match.result || "").toUpperCase();
    if (ftr === "D") return "D";
    const matchHome = String(match.home_team || "").trim().toLowerCase();
    const queriedHome = String(queriedHomeTeam || "").trim().toLowerCase();
    const matchHomeIsQueriedHome = matchHome === queriedHome;
    if (matchHomeIsQueriedHome) {
        return ftr === "H" ? "W" : "L";
    }
    return ftr === "A" ? "W" : "L";
}

function _h2hBadgeClass(result) {
    const r = String(result || "").toUpperCase();
    if (r === "W") return "h2h-badge-w";
    if (r === "D") return "h2h-badge-d";
    return "h2h-badge-l";
}

function _renderFormColumn(teamName, formSummary, formList) {
    const wins = Number(formSummary.wins) || 0;
    const draws = Number(formSummary.draws) || 0;
    const losses = Number(formSummary.losses) || 0;
    const gf = Number(formSummary.goals_for) || 0;
    const ga = Number(formSummary.goals_against) || 0;
    const streak = Array.isArray(formSummary.streak) ? formSummary.streak : [];

    let html = `<div class="h2h-form-card">`;
    html += `<div class="h2h-form-team">${teamName}</div>`;
    html += `<div class="h2h-form-summary">`;
    html += `${wins}胜 ${draws}平 ${losses}负, 进${gf}球 失${ga}球`;
    html += `</div>`;

    if (streak.length > 0) {
        html += `<div class="h2h-form-streak" aria-label="近五场战绩">`;
        for (const r of streak) {
            html += `<span class="${_h2hBadgeClass(r)}" style="font-size:0.68rem">${escapeHtml(String(r).toUpperCase())}</span>`;
        }
        html += `</div>`;
    }

    const recent = formList.slice(0, 5);
    if (recent.length > 0) {
        html += `<div class="h2h-form-list">`;
        for (const m of recent) {
            const date = escapeHtml(String(m.date || "–"));
            const opp = escapeHtml(String(m.opponent || "–"));
            const venue = escapeHtml(String(m.venue || ""));
            const gf2 = m.goals_for != null ? m.goals_for : "–";
            const ga2 = m.goals_against != null ? m.goals_against : "–";
            const badge = String(m.result || "").toUpperCase();
            html += `<div class="h2h-form-row">`;
            html += `<span class="h2h-form-opponent">${date}${venue ? ` <span class="h2h-venue">[${venue}]</span>` : ""} vs ${opp}</span>`;
            html += `<span class="h2h-form-score"><strong>${escapeHtml(String(gf2))}-${escapeHtml(String(ga2))}</strong> <span class="${_h2hBadgeClass(badge)}">${escapeHtml(badge || "–")}</span></span>`;
            html += `</div>`;
        }
        html += `</div>`;
    }

    html += `</div>`;
    return html;
}

function _trendLabel(label) {
    const labels = {
        improving: "上升",
        declining: "下滑",
        stable: "平稳",
        insufficient: "样本不足",
        no_data: "无数据",
    };
    return labels[label] || label;
}

function _trendLabelClass(label) {
    if (label === "improving") return "trend-up";
    if (label === "declining") return "trend-down";
    return "trend-flat";
}

function _renderFormTrendCard(teamName, trend) {
    if (!trend || !trend.matches) {
        return `<div class="h2h-form-card"><div class="h2h-form-team">${teamName}</div><p class="h2h-message h2h-message-inline">无近期趋势数据</p></div>`;
    }
    const rating = Number(trend.form_rating) || 0;
    const momentum = Number(trend.momentum) || 0;
    const ppg = Number(trend.ppg) || 0;
    const gfPg = Number(trend.gf_per_game) || 0;
    const gaPg = Number(trend.ga_per_game) || 0;
    const cleanSheets = Number(trend.clean_sheets) || 0;
    const failedToScore = Number(trend.failed_to_score) || 0;
    const label = trend.trend_label || "no_data";
    const pointsTrend = Array.isArray(trend.points_trend) ? trend.points_trend : [];

    let html = `<div class="h2h-form-card">`;
    html += `<div class="h2h-form-team">${teamName}</div>`;

    // Form rating bar (0-100)
    const ratingColor = rating >= 60 ? "var(--accent,#5fd4a8)" : rating >= 35 ? "var(--warn,#f0c869)" : "var(--danger,#f0877a)";
    html += `<div class="trend-rating">`;
    html += `<div class="trend-rating-bar" role="img" aria-label="状态评分 ${rating.toFixed(0)}">`;
    html += `<span style="width:${Math.max(2, Math.min(100, rating))}%;background:${ratingColor}"></span>`;
    html += `</div>`;
    html += `<span class="trend-rating-value">${rating.toFixed(0)}</span>`;
    html += `</div>`;

    // Trend label badge
    html += `<div class="trend-label-row"><span class="trend-badge ${_trendLabelClass(label)}">${_trendLabel(label)}</span>`;
    html += `<span class="trend-momentum">势头 ${momentum >= 0 ? "+" : ""}${momentum.toFixed(2)}</span></div>`;

    // Key metrics
    html += `<div class="trend-metrics">`;
    html += `<span>场均 ${ppg.toFixed(2)} 分</span>`;
    html += `<span>进 ${gfPg.toFixed(2)} / 失 ${gaPg.toFixed(2)}</span>`;
    html += `<span>零封 ${cleanSheets} · 未进球 ${failedToScore}</span>`;
    html += `</div>`;

    // Sparkline (cumulative points, oldest -> newest)
    if (pointsTrend.length >= 2) {
        const max = pointsTrend[pointsTrend.length - 1] || 1;
        const w = 100, h = 24;
        const step = w / (pointsTrend.length - 1);
        let path = `M0,${h}`;
        for (let i = 0; i < pointsTrend.length; i++) {
            const x = i * step;
            const y = h - (pointsTrend[i] / max) * h;
            path += ` L${x.toFixed(1)},${y.toFixed(1)}`;
        }
        html += `<svg class="trend-sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="积分趋势">`;
        html += `<path d="${path}" fill="none" stroke="${ratingColor}" stroke-width="1.5"/>`;
        html += `</svg>`;
    }

    html += `</div>`;
    return html;
}

async function fetchMomentum(home, away, homeGoals, awayGoals, minute) {
    try {
        const hg = homeGoals || 0;
        const ag = awayGoals || 0;
        const m = minute || 0;
        return await fetchJson(
            `/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/momentum`
            + `?home_goals=${hg}&away_goals=${ag}&minute=${m}`,
            { fetchOpts: { signal: AbortSignal.timeout(60000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch momentum:", err);
        return null;
    }
}

async function renderMomentum(home, away) {
    const statusPill = document.getElementById("momentum-status");
    const summaryEl = document.getElementById("momentum-summary");
    const chartEl = document.getElementById("momentum-chart");
    if (!statusPill || !summaryEl || !chartEl) return;

    const hgInput = document.getElementById("momentum-home-goals");
    const agInput = document.getElementById("momentum-away-goals");
    const minInput = document.getElementById("momentum-minute");
    const hg = parseInt(hgInput?.value || "0", 10) || 0;
    const ag = parseInt(agInput?.value || "0", 10) || 0;
    const minute = parseInt(minInput?.value || "0", 10) || 0;
    const z = appState.lang === "zh";

    statusPill.textContent = z ? "加载中" : "loading";
    statusPill.className = "status-pill status-medium";

    const data = await fetchMomentum(home, away, hg, ag, minute);
    capturePredictionEvidence("momentum", home, away, compactMomentumEvidence(data));
    if (!data || data.error) {
        statusPill.textContent = z ? "错误" : "error";
        statusPill.className = "status-pill status-low";
        summaryEl.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${z ? "动量预测不可用" : "Momentum unavailable"}</p>`;
        return;
    }

    const timeline = data.timeline || [];
    if (timeline.length === 0) {
        statusPill.textContent = z ? "无数据" : "no data";
        statusPill.className = "status-pill status-low";
        summaryEl.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${z ? "无时间线数据" : "No timeline data"}</p>`;
        return;
    }

    statusPill.textContent = z ? "可用" : "OK";
    statusPill.className = "status-pill status-high";

    // Current probabilities (first timeline point = current minute)
    const current = timeline[0];
    summaryEl.innerHTML = `
        <div class="detail-grid" style="margin-bottom:0.5rem">
            <div><span>${escapeHtml(z ? "当前比分" : "Score")}</span><strong>${escapeHtml(String(data.current_home_goals))} - ${escapeHtml(String(data.current_away_goals))}</strong></div>
            <div><span>${escapeHtml(z ? "分钟" : "Minute")}</span><strong>${escapeHtml(String(data.current_minute))}'</strong></div>
            <div><span>${escapeHtml(z ? "主胜" : "Home")}</span><strong style="color:var(--accent)">${(current.home_win * 100).toFixed(1)}%</strong></div>
            <div><span>${escapeHtml(z ? "平" : "Draw")}</span><strong>${(current.draw * 100).toFixed(1)}%</strong></div>
            <div><span>${escapeHtml(z ? "客胜" : "Away")}</span><strong style="color:var(--warn, #f59e0b)">${(current.away_win * 100).toFixed(1)}%</strong></div>
        </div>`;

    // ECharts timeline chart
    const chart = getChart("momentum-chart");
    if (!chart) return;

    const minutes = timeline.map((p) => p.minute + "'");
    const homeWinData = timeline.map((p) => +(p.home_win * 100).toFixed(2));
    const drawData = timeline.map((p) => +(p.draw * 100).toFixed(2));
    const awayWinData = timeline.map((p) => +(p.away_win * 100).toFixed(2));

    chart.setOption({
        tooltip: { trigger: "axis" },
        legend: {
            data: [z ? "主胜" : "Home Win", z ? "平局" : "Draw", z ? "客胜" : "Away Win"],
            top: 0,
            textStyle: { fontSize: 10 },
        },
        grid: { left: 48, right: 24, top: 36, bottom: 38 },
        xAxis: {
            type: "category",
            data: minutes,
            name: z ? "分钟" : "Minute",
            nameTextStyle: { fontSize: 10 },
            axisLabel: { fontSize: 9 },
        },
        yAxis: {
            type: "value",
            min: 0,
            max: 100,
            axisLabel: { fontSize: 9, formatter: "{value}%" },
        },
        series: [
            {
                name: z ? "主胜" : "Home Win",
                type: "line",
                data: homeWinData,
                smooth: true,
                symbol: "circle",
                symbolSize: 4,
                lineStyle: { width: 2 },
                itemStyle: { color: "#64b5f6" },
                areaStyle: { opacity: 0.1 },
            },
            {
                name: z ? "平局" : "Draw",
                type: "line",
                data: drawData,
                smooth: true,
                symbol: "circle",
                symbolSize: 4,
                lineStyle: { width: 2 },
                itemStyle: { color: "#9e9e9e" },
            },
            {
                name: z ? "客胜" : "Away Win",
                type: "line",
                data: awayWinData,
                smooth: true,
                symbol: "circle",
                symbolSize: 4,
                lineStyle: { width: 2 },
                itemStyle: { color: "#ff9800" },
                areaStyle: { opacity: 0.1 },
            },
        ],
    });
}

async function fetchAndRenderPredictionAttribution(home, away) {
    const panel = document.getElementById("match-attribution-panel");
    const body = document.getElementById("match-attribution-body");
    const btn = document.getElementById("btn-prediction-attribution");
    if (!panel || !body) return;
    const z = appState.lang === "zh";

    panel.style.display = "block";
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_loading"))}</p>`;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/attribution`,
            { fetchOpts: { signal: AbortSignal.timeout(60000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch prediction attribution:", err);
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    if (!data || data.status === "error" || data.status === "not_available") {
        const msg = data && data.status === "error"
            ? `Error: ${escapeHtml(data.message || "unknown")}`
            : escapeHtml(t("prediction_attribution_not_available"));
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${msg}</p>`
            + `<p style="font-size:0.72rem;margin-top:0.4rem;font-family:monospace;color:var(--text-muted)">${escapeHtml((data && data.instructions) || t("prediction_attribution_instructions"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const baselineHome = Number(data.baseline_home_win ?? 0);
    const baselineDraw = Number(data.baseline_draw ?? 0);
    const baselineAway = Number(data.baseline_away_win ?? 0);
    const factors = Array.isArray(data.factors) ? data.factors : [];

    const deltaColor = (d) => {
        if (d == null || Number.isNaN(d)) return "var(--text-muted)";
        return d > 0 ? "var(--accent, #64b5f6)" : "var(--warn, #f59e0b)";
    };
    const fmtPct = (v) => v != null && !Number.isNaN(Number(v)) ? `${(Number(v) * 100).toFixed(2)}%` : "—";
    const fmtDeltaPct = (d) => d != null && !Number.isNaN(Number(d))
        ? `${Number(d) >= 0 ? "+" : ""}${(Number(d) * 100).toFixed(2)}pp`
        : "—";

    const baselineHtml = `
        <div class="detail-grid" style="margin-bottom:0.5rem">
            <div><span>${escapeHtml(t("prediction_attribution_baseline"))}</span><strong style="color:var(--accent)">${fmtPct(baselineHome)}</strong></div>
            <div><span>${z ? "平" : "Draw"}</span><strong>${fmtPct(baselineDraw)}</strong></div>
            <div><span>${z ? "客胜" : "Away"}</span><strong>${fmtPct(baselineAway)}</strong></div>
        </div>`;

    let factorsHtml = "";
    if (factors.length > 0) {
        const rows = factors.map((f, idx) => {
            const delta = Number(f.delta);
            const neutralized = Number(f.neutralized_home_win);
            const label = f.label || f.factor || "—";
            return `<tr>
                <td><strong>${escapeHtml(f.factor || "—")}</strong><div style="font-size:0.68rem;color:var(--text-muted)">${escapeHtml(label)}</div></td>
                <td>${fmtPct(neutralized)}</td>
                <td style="color:${deltaColor(delta)}">${fmtDeltaPct(delta)}</td>
                <td>${idx + 1}</td>
            </tr>`;
        }).join("");
        factorsHtml = `
            <h4 style="margin:0.5rem 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("prediction_attribution_factor"))}</h4>
            <table class="data-table" style="width:100%;font-size:0.76rem">
                <thead>
                    <tr>
                        <th>${escapeHtml(t("prediction_attribution_factor"))}</th>
                        <th>${escapeHtml(t("prediction_attribution_neutralized"))}</th>
                        <th>${escapeHtml(t("prediction_attribution_delta"))}</th>
                        <th>#</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    const methodNote = `<div style="font-size:0.68rem;color:var(--text-muted);margin-top:0.4rem">method: ${escapeHtml(data.method || "permutation-neutralize")} · model: ${escapeHtml(data.model_type || "dixon_coles")} · n_factors: ${escapeHtml(String(data.n_factors ?? factors.length))}</div>`;

    body.innerHTML = `${baselineHtml}${factorsHtml}${methodNote}`;
    if (btn) btn.disabled = false;
}

async function fetchAndRenderPredictionAttributionCI(home, away) {
    const body = document.getElementById("match-attribution-body");
    const btn = document.getElementById("btn-prediction-attribution-ci");
    if (!body) return;
    const z = appState.lang === "zh";

    const placeholder = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_ci_loading"))}</p>`;
    const prev = body.innerHTML;
    body.innerHTML = placeholder;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/attribution/ci`,
            { fetchOpts: { signal: AbortSignal.timeout(120000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch attribution CI:", err);
        body.innerHTML = prev + `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_ci_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    if (!data || data.status === "error" || data.status === "not_available") {
        const msg = data && data.status === "error"
            ? `Error: ${escapeHtml(data.message || "unknown")}`
            : escapeHtml(t("prediction_attribution_ci_not_available"));
        body.innerHTML = prev + `<p style="color:var(--text-muted);font-size:0.82rem">${msg}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const cis = Array.isArray(data.factor_cis) ? data.factor_cis : [];
    const fmtPct = (v) => v != null && !Number.isNaN(Number(v))
        ? `${(Number(v) * 100).toFixed(2)}pp`
        : "—";
    const fmtCI = (lo, hi) => {
        const loStr = lo == null || Number.isNaN(Number(lo)) ? "—" : `${(Number(lo) * 100).toFixed(2)}pp`;
        const hiStr = hi == null || Number.isNaN(Number(hi)) ? "—" : `${(Number(hi) * 100).toFixed(2)}pp`;
        return `[${loStr}, ${hiStr}]`;
    };

    let ciHtml = "";
    if (cis.length > 0) {
        const rows = cis.map((c) => {
            const lo = Number(c.delta_low);
            const hi = Number(c.delta_high);
            const mean = Number(c.delta_mean);
            const crossesZero = (!Number.isNaN(lo) && !Number.isNaN(hi) && lo <= 0 && hi >= 0);
            const ciColor = crossesZero ? "var(--text-muted)" : "var(--accent, #64b5f6)";
            return `<tr>
                <td><strong>${escapeHtml(c.factor || "—")}</strong></td>
                <td style="color:${ciColor}">${fmtCI(lo, hi)}</td>
                <td>${fmtPct(mean)}</td>
            </tr>`;
        }).join("");
        ciHtml = `
            <h4 style="margin:0.6rem 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("prediction_attribution_delta_ci"))}</h4>
            <table class="data-table" style="width:100%;font-size:0.76rem">
                <thead>
                    <tr>
                        <th>${escapeHtml(t("prediction_attribution_factor"))}</th>
                        <th>${escapeHtml(t("prediction_attribution_delta_ci"))}</th>
                        <th>${escapeHtml(t("prediction_attribution_delta_mean"))}</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;
    } else {
        ciHtml = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_ci_not_available"))}</p>`;
    }

    const nBoot = Number(data.n_bootstrap ?? 0);
    const failed = Number(data.failed_iterations ?? 0);
    const note = `<div style="font-size:0.68rem;color:var(--text-muted);margin-top:0.4rem">bootstrap: n=${escapeHtml(String(nBoot))} · failed=${escapeHtml(String(failed))} · confidence=${escapeHtml(String(data.confidence_level ?? 0.9))}</div>`;

    body.innerHTML = prev + ciHtml + note;
    if (btn) btn.disabled = false;
}

async function fetchAndRenderDiagnostics(home, away) {
    const panel = document.getElementById("match-diagnostics-panel");
    const body = document.getElementById("match-diagnostics-body");
    const btn = document.getElementById("btn-prediction-diagnostics");
    if (!panel || !body) return;
    const z = appState.lang === "zh";

    panel.style.display = "block";
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_diagnostics_loading"))}</p>`;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/diagnostics`,
            { fetchOpts: { signal: AbortSignal.timeout(90000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch diagnostics:", err);
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(z ? "诊断数据不可用" : "Diagnostics unavailable")}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    if (!data || data.status === "error" || data.status === "not_available") {
        const msg = data && data.status === "error"
            ? `Error: ${escapeHtml(data.message || "unknown")}`
            : escapeHtml(z ? "诊断数据不可用" : "Diagnostics unavailable");
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${msg}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const fmtPct = (v) => v != null && !Number.isNaN(Number(v)) ? `${(Number(v) * 100).toFixed(2)}%` : "—";

    // Calibration section
    const cal = data.calibration || {};
    const calHtml = `
        <div style="margin-bottom:0.6rem">
            <h4 style="margin:0 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("prediction_diagnostics_calibration"))}</h4>
            <div class="detail-grid" style="font-size:0.76rem">
                <div><span>${z ? "原始 RPS" : "Raw RPS"}</span><strong>${escapeHtml(String(cal.rps_raw ?? "—"))}</strong></div>
                <div><span>${z ? "重校准 RPS" : "Recal RPS"}</span><strong>${escapeHtml(String(cal.rps_recalibrated ?? "—"))}</strong></div>
                <div><span>${z ? "场次" : "Matches"}</span><strong>${escapeHtml(String(cal.n_matches ?? "—"))}</strong></div>
            </div>
        </div>`;

    // Drift section
    const drift = data.drift || {};
    const driftStatus = drift.drift_detected === true
        ? `<span class="status-pill status-low">${escapeHtml(t("prediction_diagnostics_drift_detected"))}</span>`
        : `<span class="status-pill status-high">${escapeHtml(t("prediction_diagnostics_stable"))}</span>`;
    const driftHtml = `
        <div style="margin-bottom:0.6rem">
            <h4 style="margin:0 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("prediction_diagnostics_drift"))}</h4>
            <div style="font-size:0.76rem">${driftStatus}
                <span style="margin-left:0.5rem;color:var(--text-muted)">${z ? "窗口" : "window"}: ${escapeHtml(String(drift.latest_window ?? "—"))} · ${z ? "指标" : "metric"}: ${escapeHtml(String(drift.drift_metric ?? "—"))}</span>
            </div>
        </div>`;

    // Attribution section
    const attr = data.attribution || {};
    const factors = Array.isArray(attr.top_factors) ? attr.top_factors : [];
    let attrHtml = `
        <div style="margin-bottom:0.6rem">
            <h4 style="margin:0 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("prediction_diagnostics_attribution"))}</h4>`;
    if (factors.length > 0) {
        const rows = factors.map((f) => {
            const delta = Number(f.delta);
            const dStr = !Number.isNaN(delta) ? `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(2)}pp` : "—";
            const color = delta > 0 ? "var(--accent, #64b5f6)" : (delta < 0 ? "var(--warn, #f59e0b)" : "var(--text-muted)");
            return `<tr><td><strong>${escapeHtml(f.factor || "—")}</strong></td><td style="color:${color}">${dStr}</td></tr>`;
        }).join("");
        attrHtml += `<table class="data-table" style="width:100%;font-size:0.76rem"><tbody>${rows}</tbody></table>`;
    } else {
        attrHtml += `<p style="color:var(--text-muted);font-size:0.76rem">${escapeHtml(z ? "暂无归因数据" : "No attribution data")}</p>`;
    }
    attrHtml += `</div>`;

    // CI cache section
    const ciCache = data.ci_cache || {};
    const ciStatus = ciCache.available === true
        ? `<span class="status-pill status-high">${z ? "已缓存" : "cached"}</span>`
        : `<span class="status-pill status-medium">${z ? "未缓存" : "not cached"}</span>`;
    const ciCacheHtml = `
        <div>
            <h4 style="margin:0 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("prediction_diagnostics_ci_cache"))}</h4>
            <div style="font-size:0.76rem">${ciStatus}
                <span style="margin-left:0.5rem;color:var(--text-muted)">${z ? "年龄(秒)" : "age(s)"}: ${escapeHtml(String(ciCache.age_seconds ?? "—"))}</span>
            </div>
        </div>`;

    body.innerHTML = `${calHtml}${driftHtml}${attrHtml}${ciCacheHtml}`;
    if (btn) btn.disabled = false;
}

async function fetchAndRenderEnsembleAttribution(home, away) {
    const panel = document.getElementById("match-ensemble-attribution-panel");
    const body = document.getElementById("match-ensemble-attribution-body");
    const btn = document.getElementById("btn-ensemble-attribution");
    if (!panel || !body) return;
    const z = appState.lang === "zh";

    panel.style.display = "block";
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("ensemble_attribution_loading"))}</p>`;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/ensemble-attribution`,
            { fetchOpts: { signal: AbortSignal.timeout(90000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch ensemble attribution:", err);
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("ensemble_attribution_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    if (!data || data.status === "error" || data.status === "not_available") {
        const msg = data && data.status === "error"
            ? `Error: ${escapeHtml(data.message || "unknown")}`
            : escapeHtml(t("ensemble_attribution_not_available"));
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${msg}</p>`
            + `<p style="font-size:0.72rem;margin-top:0.4rem;font-family:monospace;color:var(--text-muted)">${escapeHtml((data && data.instructions) || "")}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const fmtPct = (v) => v != null && !Number.isNaN(Number(v)) ? `${(Number(v) * 100).toFixed(2)}%` : "—";
    const fmtDeltaPct = (d) => d != null && !Number.isNaN(Number(d))
        ? `${Number(d) >= 0 ? "+" : ""}${(Number(d) * 100).toFixed(2)}pp`
        : "—";
    const deltaColor = (d) => {
        if (d == null || Number.isNaN(d)) return "var(--text-muted)";
        return d > 0 ? "var(--accent, #64b5f6)" : "var(--warn, #f59e0b)";
    };

    // Weights header
    const weights = data.weights || {};
    const weightsSource = data.weights_source || "equal";
    const weightsLabel = weightsSource === "optimized"
        ? (z ? "优化" : "optimized")
        : (z ? "等权" : "equal");
    const weightsStr = Object.entries(weights)
        .map(([k, v]) => `${escapeHtml(k)}: ${(Number(v) * 100).toFixed(1)}%`)
        .join(" · ");
    const weightsHtml = `
        <div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:0.5rem">
            <strong>${escapeHtml(t("ensemble_attribution_weights_source"))}:</strong> ${escapeHtml(weightsLabel)}
            <span style="margin-left:0.5rem">| ${escapeHtml(t("ensemble_attribution_weights"))}: ${weightsStr}</span>
        </div>`;

    // Helper to render a factor table from an attribution object
    const renderFactorTable = (attr, headerLabel) => {
        const factors = Array.isArray(attr.factors) ? attr.factors : [];
        if (factors.length === 0) {
            return `<p style="color:var(--text-muted);font-size:0.76rem">${escapeHtml(z ? "暂无因子" : "No factors")}</p>`;
        }
        const rows = factors.map((f) => {
            const delta = Number(f.delta);
            const neutralized = Number(f.neutralized_home_win);
            return `<tr>
                <td><strong>${escapeHtml(f.factor || "—")}</strong></td>
                <td>${fmtPct(neutralized)}</td>
                <td style="color:${deltaColor(delta)}">${fmtDeltaPct(delta)}</td>
            </tr>`;
        }).join("");
        return `
            <h4 style="margin:0.4rem 0 0.2rem;font-size:0.74rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(headerLabel)}</h4>
            <table class="data-table" style="width:100%;font-size:0.74rem">
                <thead><tr>
                    <th>${escapeHtml(t("prediction_attribution_factor"))}</th>
                    <th>${escapeHtml(t("prediction_attribution_neutralized"))}</th>
                    <th>${escapeHtml(t("prediction_attribution_delta"))}</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
    };

    // Blended section
    const blended = data.blended || {};
    const blendedBaseline = `
        <div class="detail-grid" style="margin-bottom:0.3rem;font-size:0.74rem">
            <div><span>${escapeHtml(t("prediction_attribution_baseline"))}</span><strong style="color:var(--accent)">${fmtPct(blended.baseline_home_win)}</strong></div>
            <div><span>${z ? "平" : "Draw"}</span><strong>${fmtPct(blended.baseline_draw)}</strong></div>
            <div><span>${z ? "客胜" : "Away"}</span><strong>${fmtPct(blended.baseline_away_win)}</strong></div>
        </div>`;
    const blendedHtml = `
        <div style="margin-bottom:0.6rem">
            <h4 style="margin:0 0 0.2rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("ensemble_attribution_blended"))}</h4>
            ${blendedBaseline}
            ${renderFactorTable(blended, t("ensemble_attribution_blended"))}
        </div>`;

    // Per-model section
    const perModel = data.per_model || {};
    const perModelNames = Object.keys(perModel);
    let perModelHtml = "";
    if (perModelNames.length > 0) {
        const tables = perModelNames.map((name) => {
            const w = weights[name];
            const wStr = w != null ? ` (${(Number(w) * 100).toFixed(0)}%)` : "";
            return renderFactorTable(perModel[name], `${escapeHtml(name)}${wStr}`);
        }).join("");
        perModelHtml = `
            <div>
                <h4 style="margin:0.4rem 0 0.2rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("ensemble_attribution_per_model"))}</h4>
                ${tables}
            </div>`;
    }

    body.innerHTML = `${weightsHtml}${blendedHtml}${perModelHtml}`;
    if (btn) btn.disabled = false;
}

async function fetchAndRenderEnsembleAttributionCI(home, away) {
    const body = document.getElementById("match-ensemble-attribution-body");
    const btn = document.getElementById("btn-ensemble-attribution-ci");
    if (!body) return;
    const z = appState.lang === "zh";

    const placeholder = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_ci_loading"))}</p>`;
    const prev = body.innerHTML;
    body.innerHTML = placeholder;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/ensemble-attribution/ci`,
            { fetchOpts: { signal: AbortSignal.timeout(120000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch ensemble attribution CI:", err);
        body.innerHTML = prev + `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_ci_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    if (!data || data.status === "error" || data.status === "not_available") {
        const msg = data && data.status === "error"
            ? `Error: ${escapeHtml(data.message || "unknown")}`
            : escapeHtml(t("prediction_attribution_ci_not_available"));
        body.innerHTML = prev + `<p style="color:var(--text-muted);font-size:0.82rem">${msg}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const cis = Array.isArray(data.factor_cis) ? data.factor_cis : [];
    const fmtPct = (v) => v != null && !Number.isNaN(Number(v))
        ? `${(Number(v) * 100).toFixed(2)}pp`
        : "—";
    const fmtCI = (lo, hi) => {
        const loStr = lo == null || Number.isNaN(Number(lo)) ? "—" : `${(Number(lo) * 100).toFixed(2)}pp`;
        const hiStr = hi == null || Number.isNaN(Number(hi)) ? "—" : `${(Number(hi) * 100).toFixed(2)}pp`;
        return `[${loStr}, ${hiStr}]`;
    };

    let ciHtml = "";
    if (cis.length > 0) {
        const rows = cis.map((c) => {
            const lo = Number(c.delta_low);
            const hi = Number(c.delta_high);
            const mean = Number(c.delta_mean);
            const crossesZero = (!Number.isNaN(lo) && !Number.isNaN(hi) && lo <= 0 && hi >= 0);
            const ciColor = crossesZero ? "var(--text-muted)" : "var(--accent, #64b5f6)";
            return `<tr>
                <td><strong>${escapeHtml(c.factor || "—")}</strong></td>
                <td style="color:${ciColor}">${fmtCI(lo, hi)}</td>
                <td>${fmtPct(mean)}</td>
            </tr>`;
        }).join("");
        ciHtml = `
            <h4 style="margin:0.6rem 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("prediction_attribution_delta_ci"))} (${z ? "融合" : "blended"})</h4>
            <table class="data-table" style="width:100%;font-size:0.76rem">
                <thead>
                    <tr>
                        <th>${escapeHtml(t("prediction_attribution_factor"))}</th>
                        <th>${escapeHtml(t("prediction_attribution_delta_ci"))}</th>
                        <th>${escapeHtml(t("prediction_attribution_delta_mean"))}</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;
    } else {
        ciHtml = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("prediction_attribution_ci_not_available"))}</p>`;
    }

    const nBoot = Number(data.n_bootstrap ?? 0);
    const failed = Number(data.failed_iterations ?? 0);
    const ws = data.weights_source || "equal";
    const wsLabel = ws === "optimized" ? (z ? "优化" : "optimized") : (z ? "等权" : "equal");
    const note = `<div style="font-size:0.68rem;color:var(--text-muted);margin-top:0.4rem">bootstrap: n=${escapeHtml(String(nBoot))} · failed=${escapeHtml(String(failed))} · confidence=${escapeHtml(String(data.confidence_level ?? 0.9))} · weights=${escapeHtml(wsLabel)}</div>`;

    body.innerHTML = prev + ciHtml + note;
    if (btn) btn.disabled = false;
}

async function fetchAndRenderDriftTimeline() {
    const body = document.getElementById("match-diagnostics-body");
    const btn = document.getElementById("btn-drift-timeline");
    if (!body) return;
    const z = appState.lang === "zh";

    const prev = body.innerHTML;
    body.innerHTML += `<div id="drift-timeline-loading" style="margin-top:0.5rem"><p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("ensemble_attribution_drift_timeline_loading"))}</p></div>`;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/drift/timeline`,
            { fetchOpts: { signal: AbortSignal.timeout(60000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch drift timeline:", err);
        const loading = document.getElementById("drift-timeline-loading");
        if (loading) loading.remove();
        body.innerHTML = prev + `<p style="color:var(--text-muted);font-size:0.82rem;margin-top:0.5rem">${escapeHtml(t("ensemble_attribution_drift_timeline_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const loading = document.getElementById("drift-timeline-loading");
    if (loading) loading.remove();

    if (!data || data.status === "error" || data.status === "not_available" || data.status === "no_data") {
        const msg = data && data.status === "error"
            ? `Error: ${escapeHtml(data.message || "unknown")}`
            : escapeHtml(t("ensemble_attribution_drift_timeline_not_available"));
        body.innerHTML = prev + `<p style="color:var(--text-muted);font-size:0.82rem;margin-top:0.5rem">${msg}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const points = Array.isArray(data.points) ? data.points : [];
    if (points.length < 2) {
        body.innerHTML = prev + `<p style="color:var(--text-muted);font-size:0.82rem;margin-top:0.5rem">${escapeHtml(t("ensemble_attribution_drift_timeline_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    // Build chart container
    const chartId = "drift-timeline-chart";
    const driftDetected = data.drift_detected === true;
    const statusPill = driftDetected
        ? `<span class="status-pill status-low">${escapeHtml(t("prediction_diagnostics_drift_detected"))}</span>`
        : `<span class="status-pill status-high">${escapeHtml(t("prediction_diagnostics_stable"))}</span>`;
    const metricName = data.metric || "rps_1x2";
    const threshold = Number(data.threshold ?? 0.05);

    body.innerHTML = prev + `
        <div style="margin-top:0.6rem">
            <h4 style="margin:0 0 0.3rem;font-size:0.78rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("ensemble_attribution_drift_timeline"))}</h4>
            <div style="font-size:0.72rem;margin-bottom:0.4rem">${statusPill}
                <span style="margin-left:0.5rem;color:var(--text-muted)">${z ? "指标" : "metric"}: ${escapeHtml(metricName)} · ${z ? "阈值" : "threshold"}: ${(threshold * 100).toFixed(0)}% · ${z ? "窗口" : "windows"}: ${escapeHtml(String(data.n_points ?? points.length))}</span>
            </div>
            <div id="${chartId}" style="width:100%;height:240px"></div>
        </div>`;

    // Render ECharts line chart
    const chart = getChart(chartId);
    if (!chart) {
        if (btn) btn.disabled = false;
        return;
    }

    const dates = points.map((p) => p.date || p.end_date || "");
    const rpsSeries = points.map((p) => Number(p.rps_1x2));
    const brierSeries = points.map((p) => Number(p.brier_1x2));
    const logLossSeries = points.map((p) => Number(p.log_loss_exact));

    // Compute threshold reference line as avg * (1 + threshold)
    const validRps = rpsSeries.filter((v) => !Number.isNaN(v));
    const avgRps = validRps.length > 0
        ? validRps.reduce((a, b) => a + b, 0) / validRps.length
        : 0;
    const thresholdLine = dates.map(() => avgRps * (1 + threshold));

    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    const textColor = isDark ? "#e0e0e0" : "#333";
    const gridColor = isDark ? "#333" : "#ddd";

    chart.setOption({
        tooltip: { trigger: "axis" },
        legend: { data: ["RPS", "Brier", "LogLoss"], textStyle: { color: textColor, fontSize: 10 } },
        grid: { left: "8%", right: "5%", bottom: "15%", top: "15%" },
        xAxis: {
            type: "category",
            data: dates,
            axisLabel: { color: textColor, fontSize: 9, rotate: 30 },
            axisLine: { lineStyle: { color: gridColor } },
        },
        yAxis: {
            type: "value",
            axisLabel: { color: textColor, fontSize: 9 },
            axisLine: { lineStyle: { color: gridColor } },
            splitLine: { lineStyle: { color: gridColor } },
        },
        series: [
            {
                name: "RPS",
                type: "line",
                data: rpsSeries,
                smooth: true,
                symbol: "circle",
                symbolSize: 5,
                lineStyle: { width: 2 },
                itemStyle: { color: "#64b5f6" },
            },
            {
                name: "Brier",
                type: "line",
                data: brierSeries,
                smooth: true,
                symbol: "circle",
                symbolSize: 4,
                lineStyle: { width: 1.5, type: "dashed" },
                itemStyle: { color: "#f59e0b" },
            },
            {
                name: "LogLoss",
                type: "line",
                data: logLossSeries,
                smooth: true,
                symbol: "circle",
                symbolSize: 4,
                lineStyle: { width: 1.5, type: "dotted" },
                itemStyle: { color: "#10b981" },
            },
            {
                name: "Threshold",
                type: "line",
                data: thresholdLine,
                symbol: "none",
                lineStyle: { width: 1, type: "dashed", color: "#ef4444" },
                itemStyle: { color: "#ef4444" },
            },
        ],
    });

    if (btn) btn.disabled = false;
}

async function fetchAndRenderValueBet(home, away) {
    const resultDiv = document.getElementById("match-value-bet-result");
    const btn = document.getElementById("btn-value-bet");
    if (!resultDiv) return;
    const z = appState.lang === "zh";

    const homeOdds = parseFloat(document.getElementById("value-bet-home-odds")?.value || "2.0");
    const drawOdds = parseFloat(document.getElementById("value-bet-draw-odds")?.value || "3.5");
    const awayOdds = parseFloat(document.getElementById("value-bet-away-odds")?.value || "3.0");

    if (!homeOdds || !drawOdds || !awayOdds || homeOdds < 1 || drawOdds < 1 || awayOdds < 1) {
        resultDiv.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("value_bet_error"))}</p>`;
        return;
    }

    resultDiv.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("value_bet_loading"))}</p>`;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/value?home_odds=${homeOdds}&draw_odds=${drawOdds}&away_odds=${awayOdds}`,
            { fetchOpts: { signal: AbortSignal.timeout(30000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch value bet:", err);
        resultDiv.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("value_bet_error"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    if (!data || data.status === "error") {
        resultDiv.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("value_bet_error"))}: ${escapeHtml(data?.message || "unknown")}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const outcomes = Array.isArray(data.outcomes) ? data.outcomes : [];
    const outcomeLabels = {
        home_win: z ? "主胜" : "Home Win",
        draw: z ? "平局" : "Draw",
        away_win: z ? "客胜" : "Away Win",
    };

    const rows = outcomes.map((o) => {
        const isValue = o.recommendation === "value_bet";
        const evPct = (o.expected_value * 100).toFixed(1);
        const edgePct = (o.edge * 100).toFixed(1);
        const kellyPct = (o.kelly_fraction * 100).toFixed(1);
        const recColor = isValue ? "var(--status-high, #10b981)" : "var(--text-muted)";
        const recText = isValue ? (z ? "有价值" : "Value") : (z ? "无价值" : "No Value");
        return `<tr style="border-bottom:1px solid var(--border)">
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem">${escapeHtml(outcomeLabels[o.outcome] || o.outcome)}</td>
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem;text-align:right">${(o.model_probability * 100).toFixed(1)}%</td>
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem;text-align:right">${o.decimal_odds.toFixed(2)}</td>
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem;text-align:right">${(o.implied_probability * 100).toFixed(1)}%</td>
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem;text-align:right;color:${o.expected_value >= 0 ? "var(--status-high, #10b981)" : "var(--status-low, #ef4444)"}">${evPct >= 0 ? "+" : ""}${evPct}%</td>
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem;text-align:right;color:${o.edge >= 0 ? "var(--status-high, #10b981)" : "var(--status-low, #ef4444)"}">${edgePct >= 0 ? "+" : ""}${edgePct}%</td>
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem;text-align:right">${kellyPct}%</td>
            <td style="padding:0.3rem 0.4rem;font-size:0.78rem;color:${recColor};font-weight:600">${recText}</td>
        </tr>`;
    }).join("");

    const bestBetHtml = data.best_bet
        ? `<div style="margin-top:0.5rem;padding:0.4rem 0.6rem;background:var(--bg-elevated,rgba(0,0,0,0.05));border-radius:6px;border-left:3px solid var(--status-high, #10b981)">
            <span style="font-size:0.75rem;font-weight:600">${escapeHtml(t("value_bet_best_bet"))}: ${escapeHtml(outcomeLabels[data.best_bet.outcome] || data.best_bet.outcome)}</span>
            <span style="font-size:0.72rem;color:var(--text-muted);margin-left:0.5rem">EV: ${(data.best_bet.expected_value * 100).toFixed(1)}% · Kelly: ${(data.best_bet.kelly_fraction * 100).toFixed(1)}%</span>
          </div>`
        : `<div style="margin-top:0.5rem;padding:0.4rem 0.6rem;background:var(--bg-elevated,rgba(0,0,0,0.05));border-radius:6px">
            <span style="font-size:0.75rem;color:var(--text-muted)">${escapeHtml(t("value_bet_no_value"))}</span>
          </div>`;

    const overroundPct = ((data.overround || 0) * 100).toFixed(1);
    resultDiv.innerHTML = `
        <table style="width:100%;border-collapse:collapse;margin-top:0.3rem">
            <thead>
                <tr style="border-bottom:2px solid var(--border)">
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:left;color:var(--text-muted)">${escapeHtml(t("value_bet_outcome"))}</th>
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:right;color:var(--text-muted)">${escapeHtml(t("value_bet_model_prob"))}</th>
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:right;color:var(--text-muted)">${escapeHtml(t("value_bet_odds"))}</th>
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:right;color:var(--text-muted)">${escapeHtml(t("value_bet_implied"))}</th>
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:right;color:var(--text-muted)">${escapeHtml(t("value_bet_ev"))}</th>
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:right;color:var(--text-muted)">${escapeHtml(t("value_bet_edge"))}</th>
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:right;color:var(--text-muted)">${escapeHtml(t("value_bet_kelly"))}</th>
                    <th style="padding:0.3rem 0.4rem;font-size:0.7rem;text-align:center;color:var(--text-muted)">${escapeHtml(t("value_bet_recommendation"))}</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
        ${bestBetHtml}
        <div style="margin-top:0.3rem;font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("value_bet_overround"))}: ${overroundPct}%</div>
        <div style="margin-top:0.2rem;font-size:0.65rem;color:var(--text-muted);font-style:italic">${escapeHtml(t("value_bet_disclaimer"))}</div>
    `;

    if (btn) btn.disabled = false;
}

async function fetchAndRenderReliabilityDiagram() {
    const body = document.getElementById("backtest-reliability-body");
    const btn = document.getElementById("btn-reliability-diagram");
    if (!body) return;
    const z = appState.lang === "zh";

    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("backtest_reliability_loading"))}</p>`;
    if (btn) btn.disabled = true;

    let data;
    try {
        data = await fetchJson(
            `/predictions/calibration/reliability?n_bins=10`,
            { fetchOpts: { signal: AbortSignal.timeout(30000) } },
        );
    } catch (err) {
        console.warn("Failed to fetch reliability diagram:", err);
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("backtest_reliability_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    if (!data || data.status === "error" || data.status === "not_available" || data.status === "no_data") {
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(t("backtest_reliability_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }

    const perOutcome = data.per_outcome || {};
    const overall = data.overall || {};
    const ece = (overall.ece || 0).toFixed(4);
    const rms = (overall.rms_calibration_error || 0).toFixed(4);
    const nPred = data.n_predictions || 0;

    const chartId = "reliability-chart";
    body.innerHTML = `
        <div style="font-size:0.75rem;margin-bottom:0.4rem;color:var(--text-muted)">
            ${escapeHtml(t("backtest_reliability_ece"))}: <strong>${ece}</strong> ·
            ${escapeHtml(t("backtest_reliability_rms"))}: <strong>${rms}</strong> ·
            ${z ? "预测数" : "Predictions"}: <strong>${nPred}</strong>
        </div>
        <div id="${chartId}" style="width:100%;height:300px"></div>`;

    const chart = getChart(chartId);
    if (!chart) {
        if (btn) btn.disabled = false;
        return;
    }

    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    const textColor = isDark ? "#e0e0e0" : "#333";
    const gridColor = isDark ? "#333" : "#ddd";

    // Perfect calibration line (0-1 diagonal)
    const diagonal = [[0, 0], [1, 1]];

    // Build per-outcome series
    const outcomeColors = { home_win: "#64b5f6", draw: "#f59e0b", away_win: "#10b981" };
    const outcomeLabels = {
        home_win: z ? "主胜" : "Home Win",
        draw: z ? "平局" : "Draw",
        away_win: z ? "客胜" : "Away Win",
    };

    const series = [
        {
            name: z ? "完美校准" : "Perfect",
            type: "line",
            data: diagonal,
            symbol: "none",
            lineStyle: { width: 1, type: "dashed", color: "#999" },
            itemStyle: { color: "#999" },
        },
    ];

    for (const [outcome, bins] of Object.entries(perOutcome)) {
        if (!Array.isArray(bins) || bins.length === 0) continue;
        const pts = bins.map((b) => [b.mean_predicted, b.observed_frequency]);
        series.push({
            name: outcomeLabels[outcome] || outcome,
            type: "scatter",
            data: pts,
            symbolSize: (bins.length > 0 ? 8 : 5),
            itemStyle: { color: outcomeColors[outcome] || "#888" },
        });
        // Also add a connecting line
        const sorted = pts.slice().sort((a, b) => a[0] - b[0]);
        series.push({
            name: outcomeLabels[outcome] || outcome,
            type: "line",
            data: sorted,
            symbol: "none",
            lineStyle: { width: 1, color: outcomeColors[outcome] || "#888", opacity: 0.5 },
            itemStyle: { color: outcomeColors[outcome] || "#888" },
        });
    }

    chart.setOption({
        tooltip: {
            trigger: "item",
            formatter: (p) => {
                const x = (p.data[0] * 100).toFixed(1);
                const y = (p.data[1] * 100).toFixed(1);
                return `${p.seriesName}<br/>${escapeHtml(t("backtest_reliability_predicted"))}: ${x}%<br/>${escapeHtml(t("backtest_reliability_observed"))}: ${y}%`;
            },
        },
        legend: { textStyle: { color: textColor, fontSize: 10 } },
        grid: { left: "10%", right: "5%", bottom: "15%", top: "15%" },
        xAxis: {
            type: "value",
            min: 0,
            max: 1,
            name: escapeHtml(t("backtest_reliability_predicted")),
            nameTextStyle: { color: textColor, fontSize: 10 },
            axisLabel: { color: textColor, fontSize: 9, formatter: (v) => `${(v * 100).toFixed(0)}%` },
            axisLine: { lineStyle: { color: gridColor } },
            splitLine: { lineStyle: { color: gridColor } },
        },
        yAxis: {
            type: "value",
            min: 0,
            max: 1,
            name: escapeHtml(t("backtest_reliability_observed")),
            nameTextStyle: { color: textColor, fontSize: 10 },
            axisLabel: { color: textColor, fontSize: 9, formatter: (v) => `${(v * 100).toFixed(0)}%` },
            axisLine: { lineStyle: { color: gridColor } },
            splitLine: { lineStyle: { color: gridColor } },
        },
        series,
    });

    if (btn) btn.disabled = false;
}

async function fetchAndRenderModelComparison() {
    const body = document.getElementById("backtest-model-comparison-body");
    const btn = document.getElementById("btn-model-comparison");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("model_comparison_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/models/comparison");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("model_comparison_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("model_comparison_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const models = Array.isArray(data.models) ? data.models : [];
        const winners = data.metric_winners || {};
        const metricRows = [
            { key: "log_loss", label: "Log Loss", higher: false },
            { key: "brier", label: "Brier", higher: false },
            { key: "rps", label: "RPS", higher: false },
            { key: "accuracy", label: escapeHtml(t("model_comparison_accuracy")), higher: true },
            { key: "avg_confidence", label: escapeHtml(t("model_comparison_avg_confidence")), higher: true },
            { key: "calibration_gap", label: escapeHtml(t("model_comparison_cal_gap")), higher: false },
        ];
        const fmt = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? v.toFixed(4) : String(v));
        let html = `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.2rem;font-weight:600">${data.n_aligned ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("model_comparison_n_aligned"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.2rem;font-weight:600">${data.n_models ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("model_comparison_n_models"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.2rem;font-weight:600">${models.length}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">Models Listed</div>
            </div>
        </div>`;
        // Per-model metrics table
        html += `<table class="data-table" style="width:100%;font-size:0.78rem;border-collapse:collapse">
            <thead><tr style="text-align:left;border-bottom:1px solid var(--border-color)">
                <th style="padding:0.3rem">Model</th>
                <th style="padding:0.3rem">N</th>
                <th style="padding:0.3rem">Log Loss</th>
                <th style="padding:0.3rem">Brier</th>
                <th style="padding:0.3rem">RPS</th>
                <th style="padding:0.3rem">Acc</th>
                <th style="padding:0.3rem">Conf</th>
                <th style="padding:0.3rem">Cal Gap</th>
            </tr></thead><tbody>`;
        for (const m of models) {
            html += `<tr style="border-bottom:1px solid var(--border-color)">
                <td style="padding:0.3rem;font-weight:600">${escapeHtml(m.label || m.model)}</td>
                <td style="padding:0.3rem">${m.n_predictions ?? 0}</td>
                <td style="padding:0.3rem">${fmt(m.log_loss)}</td>
                <td style="padding:0.3rem">${fmt(m.brier)}</td>
                <td style="padding:0.3rem">${fmt(m.rps)}</td>
                <td style="padding:0.3rem">${fmt(m.accuracy)}</td>
                <td style="padding:0.3rem">${fmt(m.avg_confidence)}</td>
                <td style="padding:0.3rem">${fmt(m.calibration_gap)}</td>
            </tr>`;
        }
        html += `</tbody></table>`;
        // Metric winners
        const winnerEntries = Object.entries(winners);
        if (winnerEntries.length > 0) {
            html += `<h4 style="margin:0.8rem 0 0.4rem;font-size:0.85rem">${escapeHtml(t("model_comparison_winner"))}</h4><ul style="list-style:none;padding:0;font-size:0.78rem">`;
            for (const [metric, winner] of winnerEntries) {
                const row = metricRows.find(r => r.key === metric);
                const label = row ? row.label : metric;
                const winnerModel = models.find(m => m.model === winner);
                const winnerLabel = winnerModel ? (winnerModel.label || winnerModel.model) : winner;
                html += `<li style="padding:0.2rem 0;border-bottom:1px solid var(--border-color)">
                    <span style="font-weight:600">${label}</span>: 
                    <span style="color:var(--accent-primary)">${escapeHtml(winnerLabel)}</span>
                </li>`;
            }
            html += `</ul>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("model_comparison_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderScorelineCalibration() {
    const body = document.getElementById("backtest-scoreline-calibration-body");
    const btn = document.getElementById("btn-scoreline-calibration");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("scoreline_cal_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/scoreline?max_scoreline=5&min_samples=3");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("scoreline_cal_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("scoreline_cal_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const entries = Array.isArray(data.entries) ? data.entries : [];
        const fmt = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? (v * 100).toFixed(1) + "%" : String(v));
        let html = `<div style="margin-bottom:0.5rem;font-size:0.8rem;color:var(--text-muted)">
            ${data.n_matches ?? 0} matches · ${data.n_scorelines ?? 0} score-lines
        </div>`;
        html += `<div style="overflow-x:auto"><table class="data-table" style="width:100%;font-size:0.75rem;border-collapse:collapse">
            <thead><tr style="text-align:left;border-bottom:1px solid var(--border-color)">
                <th style="padding:0.3rem">${escapeHtml(t("scoreline_cal_scoreline"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("scoreline_cal_outcome"))}</th>
                <th style="padding:0.3rem">N</th>
                <th style="padding:0.3rem">Pred HW</th>
                <th style="padding:0.3rem">Pred D</th>
                <th style="padding:0.3rem">Pred AW</th>
                <th style="padding:0.3rem">Act HW</th>
                <th style="padding:0.3rem">Act D</th>
                <th style="padding:0.3rem">Act AW</th>
            </tr></thead><tbody>`;
        for (const e of entries) {
            const outcomeColor = e.outcome === "home_win" ? "var(--accent-primary)" : (e.outcome === "draw" ? "var(--text-muted)" : "var(--accent-secondary)");
            html += `<tr style="border-bottom:1px solid var(--border-color)">
                <td style="padding:0.3rem;font-weight:600;font-family:monospace">${escapeHtml(e.scoreline)}</td>
                <td style="padding:0.3rem;color:${outcomeColor}">${escapeHtml(e.outcome)}</td>
                <td style="padding:0.3rem">${e.n_matches}</td>
                <td style="padding:0.3rem">${fmt(e.avg_home_win_prob)}</td>
                <td style="padding:0.3rem">${fmt(e.avg_draw_prob)}</td>
                <td style="padding:0.3rem">${fmt(e.avg_away_win_prob)}</td>
                <td style="padding:0.3rem;font-weight:600">${fmt(e.actual_home_win_rate)}</td>
                <td style="padding:0.3rem;font-weight:600">${fmt(e.actual_draw_rate)}</td>
                <td style="padding:0.3rem;font-weight:600">${fmt(e.actual_away_win_rate)}</td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
        // Outcome summary
        const summary = Array.isArray(data.outcome_summary) ? data.outcome_summary : [];
        if (summary.length > 0) {
            html += `<h4 style="margin:0.8rem 0 0.4rem;font-size:0.85rem">${escapeHtml(t("scoreline_cal_outcome_summary"))}</h4><ul style="list-style:none;padding:0;font-size:0.78rem">`;
            for (const s of summary) {
                const dist = s.scoreline_distribution || {};
                const distStr = Object.entries(dist).slice(0, 3).map(([k, v]) => `${escapeHtml(k)}: ${v}`).join(", ");
                html += `<li style="padding:0.2rem 0;border-bottom:1px solid var(--border-color)">
                    <span style="font-weight:600">${escapeHtml(s.outcome)}</span> — 
                    ${s.n_matches} matches, avg pred ${fmt(s.avg_predicted_prob)}
                    ${distStr ? ` · top: ${distStr}` : ""}
                </li>`;
            }
            html += `</ul>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("scoreline_cal_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderConfidenceDistribution() {
    const body = document.getElementById("backtest-confidence-distribution-body");
    const btn = document.getElementById("btn-confidence-distribution");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("confidence_dist_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/confidence-distribution?n_bins=10&min_samples_per_bucket=5");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("confidence_dist_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("confidence_dist_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const buckets = Array.isArray(data.buckets) ? data.buckets : [];
        const fmt = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? (v * 100).toFixed(1) + "%" : String(v));
        let html = `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_predictions ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">Predictions</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${fmt(data.overall_accuracy)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("confidence_dist_overall_acc"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${fmt(data.overall_confidence)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("confidence_dist_overall_conf"))}</div>
            </div>
        </div>`;
        html += `<table class="data-table" style="width:100%;font-size:0.78rem;border-collapse:collapse">
            <thead><tr style="text-align:left;border-bottom:1px solid var(--border-color)">
                <th style="padding:0.3rem">${escapeHtml(t("confidence_dist_bucket"))}</th>
                <th style="padding:0.3rem">N</th>
                <th style="padding:0.3rem">${escapeHtml(t("confidence_dist_accuracy"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("confidence_dist_avg_conf"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("confidence_dist_cal_gap"))}</th>
            </tr></thead><tbody>`;
        for (const b of buckets) {
            const gapColor = Math.abs(b.calibration_gap) < 0.05 ? "var(--status-high)" : (Math.abs(b.calibration_gap) < 0.15 ? "var(--status-medium)" : "var(--status-low)");
            html += `<tr style="border-bottom:1px solid var(--border-color)">
                <td style="padding:0.3rem;font-family:monospace">${escapeHtml(b.bucket_label)}</td>
                <td style="padding:0.3rem">${b.n_predictions}</td>
                <td style="padding:0.3rem;font-weight:600">${fmt(b.accuracy)}</td>
                <td style="padding:0.3rem">${fmt(b.avg_confidence)}</td>
                <td style="padding:0.3rem;color:${gapColor}">${fmt(b.calibration_gap)}</td>
            </tr>`;
        }
        html += `</tbody></table>`;
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("confidence_dist_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderErrorAnalysis() {
    const body = document.getElementById("backtest-error-analysis-body");
    const btn = document.getElementById("btn-error-analysis");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("error_analysis_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/error-analysis?n_bins=5&min_samples_per_bucket=5&top_n=5");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("error_analysis_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("error_analysis_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const fmt = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? v.toFixed(4) : String(v));
        const fmtPct = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? (v * 100).toFixed(1) + "%" : String(v));
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_predictions ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">N</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${fmtPct(data.overall_accuracy)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("error_analysis_overall_acc"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${fmt(data.overall_avg_brier)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("error_analysis_overall_brier"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${fmt(data.overall_avg_log_loss)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("error_analysis_overall_log_loss"))}</div>
            </div>
        </div>`;
        const buckets = Array.isArray(data.buckets) ? data.buckets : [];
        for (const b of buckets) {
            html += `<h4 style="margin:0.8rem 0 0.4rem;font-size:0.85rem">${escapeHtml(b.bucket_label)} · ${b.n_predictions} predictions · acc ${fmtPct(b.accuracy)} · brier ${fmt(b.avg_brier)}</h4>`;
            const worst = Array.isArray(b.worst_matches) ? b.worst_matches : [];
            if (worst.length === 0) continue;
            html += `<table class="data-table" style="width:100%;font-size:0.75rem;border-collapse:collapse;margin-bottom:0.5rem">
                <thead><tr style="text-align:left;border-bottom:1px solid var(--border-color)">
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_match_id"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_score"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_actual"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_predicted"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_confidence"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_brier"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_log_loss"))}</th>
                </tr></thead><tbody>`;
            for (const m of worst) {
                const correctColor = m.correct ? "var(--status-high)" : "var(--status-low)";
                const scoreStr = (m.home_goals !== null && m.away_goals !== null) ? `${m.home_goals}-${m.away_goals}` : "–";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem;font-family:monospace">${escapeHtml(String(m.match_id ?? "–"))}</td>
                    <td style="padding:0.25rem;font-family:monospace">${escapeHtml(scoreStr)}</td>
                    <td style="padding:0.25rem">${escapeHtml(m.actual_outcome)}</td>
                    <td style="padding:0.25rem;color:${correctColor}">${escapeHtml(m.predicted_outcome)}</td>
                    <td style="padding:0.25rem">${fmtPct(m.confidence)}</td>
                    <td style="padding:0.25rem;font-weight:600">${fmt(m.brier)}</td>
                    <td style="padding:0.25rem">${fmt(m.log_loss)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        }
        // Overall worst matches
        const overallWorst = Array.isArray(data.worst_matches_overall) ? data.worst_matches_overall : [];
        if (overallWorst.length > 0) {
            html += `<h4 style="margin:1rem 0 0.4rem;font-size:0.85rem">${escapeHtml(t("error_analysis_overall_worst"))}</h4>`;
            html += `<table class="data-table" style="width:100%;font-size:0.75rem;border-collapse:collapse">
                <thead><tr style="text-align:left;border-bottom:1px solid var(--border-color)">
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_match_id"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_score"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_actual"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_predicted"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_confidence"))}</th>
                    <th style="padding:0.25rem">${escapeHtml(t("error_analysis_brier"))}</th>
                </tr></thead><tbody>`;
            for (const m of overallWorst) {
                const correctColor = m.correct ? "var(--status-high)" : "var(--status-low)";
                const scoreStr = (m.home_goals !== null && m.away_goals !== null) ? `${m.home_goals}-${m.away_goals}` : "–";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem;font-family:monospace">${escapeHtml(String(m.match_id ?? "–"))}</td>
                    <td style="padding:0.25rem;font-family:monospace">${escapeHtml(scoreStr)}</td>
                    <td style="padding:0.25rem">${escapeHtml(m.actual_outcome)}</td>
                    <td style="padding:0.25rem;color:${correctColor}">${escapeHtml(m.predicted_outcome)}</td>
                    <td style="padding:0.25rem">${fmtPct(m.confidence)}</td>
                    <td style="padding:0.25rem;font-weight:600">${fmt(m.brier)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("error_analysis_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderOutcomeDistribution() {
    const body = document.getElementById("backtest-outcome-distribution-body");
    const btn = document.getElementById("btn-outcome-distribution");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("outcome_dist_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/outcome-distribution");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("outcome_dist_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("outcome_dist_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const fmtPct = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? (v * 100).toFixed(1) + "%" : String(v));
        const entries = Array.isArray(data.entries) ? data.entries : [];
        const biasColor = (data.dominant_bias && data.dominant_bias !== "none") ? "var(--status-medium)" : "var(--status-high)";
        let html = `<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_predictions ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">N</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${biasColor}">${escapeHtml(data.dominant_bias || "none")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("outcome_dist_dominant_bias"))}</div>
            </div>
        </div>`;
        html += `<table class="data-table" style="width:100%;font-size:0.78rem;border-collapse:collapse">
            <thead><tr style="text-align:left;border-bottom:1px solid var(--border-color)">
                <th style="padding:0.3rem">${escapeHtml(t("outcome_dist_outcome"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("outcome_dist_pred_count"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("outcome_dist_pred_share"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("outcome_dist_actual_count"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("outcome_dist_actual_share"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("outcome_dist_gap"))}</th>
            </tr></thead><tbody>`;
        for (const e of entries) {
            const gapColor = Math.abs(e.distribution_gap) < 0.03 ? "var(--status-high)" : (Math.abs(e.distribution_gap) < 0.10 ? "var(--status-medium)" : "var(--status-low)");
            html += `<tr style="border-bottom:1px solid var(--border-color)">
                <td style="padding:0.3rem;font-weight:600">${escapeHtml(e.outcome)}</td>
                <td style="padding:0.3rem">${e.predicted_count}</td>
                <td style="padding:0.3rem">${fmtPct(e.predicted_share)}</td>
                <td style="padding:0.3rem">${e.actual_count}</td>
                <td style="padding:0.3rem">${fmtPct(e.actual_share)}</td>
                <td style="padding:0.3rem;color:${gapColor};font-weight:600">${fmtPct(e.distribution_gap)}</td>
            </tr>`;
        }
        html += `</tbody></table>`;
        if (data.disclaimer) {
            html += `<p style="margin-top:0.6rem;font-size:0.72rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("outcome_dist_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderH2HBiasCorrection() {
    const body = document.getElementById("match-h2h-bias-body");
    const btn = document.getElementById("btn-h2h-bias");
    if (!body) return;
    const home = appState.selectedHome || "";
    const away = appState.selectedAway || "";
    if (!home || !away) {
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("h2h_bias_not_available"))}</p>`;
        return;
    }
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("h2h_bias_loading"))}</p>`;
    try {
        const data = await apiFetch(`/predictions/${encodeURIComponent(home)}/${encodeURIComponent(away)}/h2h-bias-correction`);
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("h2h_bias_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("h2h_bias_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const fmtPct = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? (v * 100).toFixed(1) + "%" : String(v));
        const applied = data.correction_applied === true;
        const appliedColor = applied ? "var(--status-medium)" : "var(--text-muted)";
        const appliedText = applied ? t("h2h_bias_applied") : t("h2h_bias_not_applied");
        const base = data.baseline_probabilities || {};
        const corr = data.corrected_probabilities || {};
        const adj = data.adjustments || {};
        const rates = data.h2h_rates || {};
        let html = `<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_meetings ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("h2h_bias_n_meetings"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${appliedColor}">${escapeHtml(appliedText)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("h2h_bias_applied"))}</div>
            </div>
        </div>`;
        html += `<table class="data-table" style="width:100%;font-size:0.78rem;border-collapse:collapse">
            <thead><tr style="text-align:left;border-bottom:1px solid var(--border-color)">
                <th style="padding:0.3rem">${escapeHtml(t("h2h_bias_home_win"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("h2h_bias_draw"))}</th>
                <th style="padding:0.3rem">${escapeHtml(t("h2h_bias_away_win"))}</th>
            </tr></thead><tbody>`;
        html += `<tr style="border-bottom:1px solid var(--border-color)">
            <td style="padding:0.3rem">${fmtPct(base.home_win)}</td>
            <td style="padding:0.3rem">${fmtPct(base.draw)}</td>
            <td style="padding:0.3rem">${fmtPct(base.away_win)}</td>
        </tr>`;
        html += `<tr style="border-bottom:1px solid var(--border-color);font-weight:600">
            <td style="padding:0.3rem">${fmtPct(corr.home_win)}</td>
            <td style="padding:0.3rem">${fmtPct(corr.draw)}</td>
            <td style="padding:0.3rem">${fmtPct(corr.away_win)}</td>
        </tr>`;
        const adjColor = (v) => Math.abs(v) < 0.005 ? "var(--text-muted)" : (v > 0 ? "var(--status-medium)" : "var(--status-low)");
        html += `<tr style="border-bottom:1px solid var(--border-color);font-size:0.72rem">
            <td style="padding:0.3rem;color:${adjColor(adj.home_win || 0)}">${fmtPct(adj.home_win)}</td>
            <td style="padding:0.3rem;color:${adjColor(adj.draw || 0)}">${fmtPct(adj.draw)}</td>
            <td style="padding:0.3rem;color:${adjColor(adj.away_win || 0)}">${fmtPct(adj.away_win)}</td>
        </tr>`;
        html += `<tr style="font-size:0.72rem;color:var(--text-muted)">
            <td style="padding:0.3rem">${fmtPct(rates.home_win)}</td>
            <td style="padding:0.3rem">${fmtPct(rates.draw)}</td>
            <td style="padding:0.3rem">${fmtPct(rates.away_win)}</td>
        </tr>`;
        html += `</tbody></table>`;
        html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)"><strong>${escapeHtml(t("h2h_bias_baseline"))}:</strong> ${escapeHtml(t("h2h_bias_h2h_rates"))} → ${escapeHtml(t("h2h_bias_corrected"))}</p>`;
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("h2h_bias_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderTemporalValidation() {
    const body = document.getElementById("backtest-temporal-validation-body");
    const btn = document.getElementById("btn-temporal-validation");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("temporal_val_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/temporal-validation");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("temporal_val_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("temporal_val_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const windows = data.windows || [];
        const fmtPct = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? (v * 100).toFixed(1) + "%" : String(v));
        const fmtNum = (v, d) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? v.toFixed(d) : String(v));
        const trendColor = data.trend === "improving" ? "var(--status-medium)" : (data.trend === "degrading" ? "var(--status-low)" : "var(--text-muted)");
        let html = `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_windows ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("temporal_val_n_windows"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_total_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("temporal_val_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${trendColor}">${escapeHtml(data.trend || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("temporal_val_trend"))}</div>
            </div>
        </div>`;
        if (windows.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.75rem;border-collapse:collapse">
                <thead><tr style="text-align:right;border-bottom:1px solid var(--border-color)">
                    <th style="padding:0.3rem;text-align:left">${escapeHtml(t("temporal_val_window"))}</th>
                    <th style="padding:0.3rem">N</th>
                    <th style="padding:0.3rem">Acc</th>
                    <th style="padding:0.3rem">Brier</th>
                    <th style="padding:0.3rem">RPS</th>
                    <th style="padding:0.3rem">LL</th>
                    <th style="padding:0.3rem">Conf</th>
                </tr></thead><tbody>`;
            for (const w of windows) {
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem;text-align:left">${escapeHtml(w.window_label || "")}</td>
                    <td style="padding:0.3rem">${w.n_matches ?? 0}</td>
                    <td style="padding:0.3rem">${fmtPct(w.accuracy)}</td>
                    <td style="padding:0.3rem">${fmtNum(w.brier, 4)}</td>
                    <td style="padding:0.3rem">${fmtNum(w.rps, 4)}</td>
                    <td style="padding:0.3rem">${fmtNum(w.log_loss, 4)}</td>
                    <td style="padding:0.3rem">${fmtPct(w.avg_confidence)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("temporal_val_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderProbabilityHeatmap() {
    const body = document.getElementById("backtest-probability-heatmap-body");
    const btn = document.getElementById("btn-probability-heatmap");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("prob_heatmap_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/probability-heatmap");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("prob_heatmap_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("prob_heatmap_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const cells = data.cells || [];
        const fmtPct = (v) => (v === null || v === undefined) ? "–" : (typeof v === "number" ? (v * 100).toFixed(1) + "%" : String(v));
        let html = `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_predictions ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("prob_heatmap_n_predictions"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_bins ?? 0}×${data.n_bins ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("prob_heatmap_grid"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${fmtPct(data.total_density)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("prob_heatmap_coverage"))}</div>
            </div>
        </div>`;
        if (cells.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.75rem;border-collapse:collapse">
                <thead><tr style="text-align:right;border-bottom:1px solid var(--border-color)">
                    <th style="padding:0.3rem;text-align:left">${escapeHtml(t("prob_heatmap_home_bin"))}</th>
                    <th style="padding:0.3rem;text-align:left">${escapeHtml(t("prob_heatmap_away_bin"))}</th>
                    <th style="padding:0.3rem">N</th>
                    <th style="padding:0.3rem">${escapeHtml(t("prob_heatmap_density"))}</th>
                    <th style="padding:0.3rem">${escapeHtml(t("prob_heatmap_accuracy"))}</th>
                    <th style="padding:0.3rem">${escapeHtml(t("prob_heatmap_confidence"))}</th>
                </tr></thead><tbody>`;
            for (const c of cells) {
                const accColor = c.accuracy >= 0.5 ? "var(--status-medium)" : "var(--status-low)";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem;text-align:left">${escapeHtml(c.home_bin || "")}</td>
                    <td style="padding:0.3rem;text-align:left">${escapeHtml(c.away_bin || "")}</td>
                    <td style="padding:0.3rem">${c.count ?? 0}</td>
                    <td style="padding:0.3rem">${fmtPct(c.density)}</td>
                    <td style="padding:0.3rem;color:${accColor}">${fmtPct(c.accuracy)}</td>
                    <td style="padding:0.3rem">${fmtPct(c.avg_confidence)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("prob_heatmap_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderPredictionStaleness() {
    const body = document.getElementById("backtest-prediction-staleness-body");
    const btn = document.getElementById("btn-prediction-staleness");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("staleness_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/staleness");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("staleness_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("staleness_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const levelColor = data.staleness_level === "fresh" ? "var(--status-medium)" : (data.staleness_level === "stale" ? "var(--status-low)" : "var(--status-high)");
        let html = `<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${levelColor}">${escapeHtml(data.staleness_level || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("staleness_level"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.days_since_backtest_end ?? "–"}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("staleness_days"))}</div>
            </div>
        </div>`;
        html += `<table class="data-table" style="width:100%;font-size:0.75rem;border-collapse:collapse">
            <tbody>
                <tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem;color:var(--text-muted)">${escapeHtml(t("staleness_backtest_start"))}</td>
                    <td style="padding:0.3rem;text-align:right">${escapeHtml(data.backtest_start || "–")}</td>
                </tr>
                <tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem;color:var(--text-muted)">${escapeHtml(t("staleness_backtest_end"))}</td>
                    <td style="padding:0.3rem;text-align:right">${escapeHtml(data.backtest_end || "–")}</td>
                </tr>
                <tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem;color:var(--text-muted)">${escapeHtml(t("staleness_n_matches"))}</td>
                    <td style="padding:0.3rem;text-align:right">${data.n_backtest_matches ?? 0}</td>
                </tr>
                <tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem;color:var(--text-muted)">${escapeHtml(t("staleness_model_type"))}</td>
                    <td style="padding:0.3rem;text-align:right">${escapeHtml(data.model_type || "–")}</td>
                </tr>
            </tbody>
        </table>`;
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("staleness_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderConfidenceIntervalPlot() {
    const body = document.getElementById("backtest-ci-plot-body");
    const btn = document.getElementById("btn-ci-plot");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_plot_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/ci-plot?max_points=300");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_plot_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("ci_plot_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const corrText = (data.correlation === null || data.correlation === undefined)
            ? "–"
            : Number(data.correlation).toFixed(3);
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_predictions ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_plot_n_points"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.avg_confidence || 0).toFixed(3)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_plot_avg_conf"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.avg_ci_width || 0).toFixed(3)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_plot_avg_width"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${corrText}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_plot_corr"))}</div>
            </div>
        </div>`;
        const points = Array.isArray(data.points) ? data.points : [];
        if (points.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.72rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.3rem">${escapeHtml(t("ci_plot_match"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("ci_plot_conf"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("ci_plot_lower"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("ci_plot_upper"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("ci_plot_width"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("ci_plot_correct"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            for (const p of points.slice(0, 50)) {
                const correctBadge = p.correct === null || p.correct === undefined
                    ? "–"
                    : (p.correct
                        ? `<span style="color:var(--status-medium)">✓</span>`
                        : `<span style="color:var(--status-low)">✗</span>`);
                const homeLabel = p.home_team || "–";
                const awayLabel = p.away_team || "–";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem">${escapeHtml(String(homeLabel))} vs ${escapeHtml(String(awayLabel))}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(p.confidence || 0).toFixed(3)}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(p.ci_lower || 0).toFixed(3)}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(p.ci_upper || 0).toFixed(3)}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(p.ci_width || 0).toFixed(3)}</td>
                    <td style="padding:0.3rem;text-align:right">${correctBadge}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
            if (points.length > 50) {
                html += `<p style="margin-top:0.3rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(t("ci_plot_truncated")).replace("{n}", String(points.length))}</p>`;
            }
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_plot_no_points"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("ci_plot_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderFoldComparison() {
    const body = document.getElementById("backtest-fold-comparison-body");
    const btn = document.getElementById("btn-fold-comparison");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("fold_comparison_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/fold-comparison");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("fold_comparison_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("fold_comparison_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const stabilityColor = data.stability === "stable"
            ? "var(--status-medium)"
            : (data.stability === "unstable" ? "var(--status-low)" : "var(--status-high)");
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.95rem;font-weight:600;color:${stabilityColor}">${escapeHtml(data.stability || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("fold_comparison_stability"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_folds ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("fold_comparison_n_folds"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_total_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("fold_comparison_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.accuracy_std || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("fold_comparison_acc_std"))}</div>
            </div>
        </div>`;
        const folds = Array.isArray(data.folds) ? data.folds : [];
        if (folds.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.75rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.3rem">${escapeHtml(t("fold_comparison_fold"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("fold_comparison_n"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("fold_comparison_accuracy"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("fold_comparison_brier"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("fold_comparison_rps"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("fold_comparison_log_loss"))}</th>
                        <th style="padding:0.3rem;text-align:right">${escapeHtml(t("fold_comparison_avg_conf"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            for (const f of folds) {
                const ll = (f.log_loss === null || f.log_loss === undefined) ? "–" : Number(f.log_loss).toFixed(4);
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.3rem">${f.fold ?? "–"}</td>
                    <td style="padding:0.3rem;text-align:right">${f.n_matches ?? 0}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(f.accuracy || 0).toFixed(4)}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(f.brier || 0).toFixed(4)}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(f.rps || 0).toFixed(4)}</td>
                    <td style="padding:0.3rem;text-align:right">${ll}</td>
                    <td style="padding:0.3rem;text-align:right">${Number(f.avg_confidence || 0).toFixed(4)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("fold_comparison_no_folds"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("fold_comparison_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderLeagueErrorAnalysis() {
    const body = document.getElementById("backtest-league-error-body");
    const btn = document.getElementById("btn-league-error");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("league_error_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/league-errors");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("league_error_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("league_error_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_leagues ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("league_error_n_leagues"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_total_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("league_error_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_accuracy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("league_error_accuracy"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_brier || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("league_error_brier"))}</div>
            </div>
        </div>`;
        const leagues = Array.isArray(data.leagues) ? data.leagues : [];
        if (leagues.length > 0) {
            for (const lg of leagues) {
                const ll = (lg.log_loss === null || lg.log_loss === undefined) ? "–" : Number(lg.log_loss).toFixed(4);
                html += `<details style="margin-bottom:0.6rem;border:1px solid var(--border-color);border-radius:6px;padding:0.4rem 0.6rem">
                    <summary style="cursor:pointer;font-size:0.85rem;font-weight:600">
                        ${escapeHtml(lg.league || "–")} — acc ${Number(lg.accuracy || 0).toFixed(4)} / brier ${Number(lg.brier || 0).toFixed(4)} / n ${lg.n_matches ?? 0}
                    </summary>
                    <div style="margin-top:0.4rem;font-size:0.72rem;color:var(--text-muted)">
                        RPS: ${Number(lg.rps || 0).toFixed(4)} | LogLoss: ${ll} | ${escapeHtml(t("league_error_avg_conf"))}: ${Number(lg.avg_confidence || 0).toFixed(4)}
                    </div>`;
                const worst = Array.isArray(lg.worst_matches) ? lg.worst_matches : [];
                if (worst.length > 0) {
                    html += `<table class="data-table" style="width:100%;font-size:0.7rem;border-collapse:collapse;margin-top:0.3rem">
                        <thead>
                            <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                                <th style="padding:0.25rem">${escapeHtml(t("league_error_match_id"))}</th>
                                <th style="padding:0.25rem;text-align:right">${escapeHtml(t("league_error_pred"))}</th>
                                <th style="padding:0.25rem;text-align:right">${escapeHtml(t("league_error_actual"))}</th>
                                <th style="padding:0.25rem;text-align:right">${escapeHtml(t("league_error_conf"))}</th>
                                <th style="padding:0.25rem;text-align:right">${escapeHtml(t("league_error_brier"))}</th>
                            </tr>
                        </thead>
                        <tbody>`;
                    for (const m of worst) {
                        html += `<tr style="border-bottom:1px solid var(--border-color)">
                            <td style="padding:0.25rem">${escapeHtml(String(m.match_id ?? "–"))}</td>
                            <td style="padding:0.25rem;text-align:right">${escapeHtml(m.predicted_outcome || "–")}</td>
                            <td style="padding:0.25rem;text-align:right">${escapeHtml(m.actual_outcome || "–")}</td>
                            <td style="padding:0.25rem;text-align:right">${Number(m.confidence || 0).toFixed(3)}</td>
                            <td style="padding:0.25rem;text-align:right">${Number(m.brier || 0).toFixed(4)}</td>
                        </tr>`;
                    }
                    html += `</tbody></table>`;
                }
                html += `</details>`;
            }
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("league_error_no_leagues"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("league_error_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderFeatureImportance() {
    const body = document.getElementById("backtest-feature-importance-body");
    const btn = document.getElementById("btn-feature-importance");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("feature_importance_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/feature-importance");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("feature_importance_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("feature_importance_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_features ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("feature_importance_n_features"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_total_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("feature_importance_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_brier || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("feature_importance_overall_brier"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.features && data.features.length > 0 ? Number(data.features[0].importance || 0).toFixed(6) : "–"}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("feature_importance_top"))}</div>
            </div>
        </div>`;
        const features = Array.isArray(data.features) ? data.features : [];
        if (features.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.72rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">#</th>
                        <th style="padding:0.25rem">${escapeHtml(t("feature_importance_feature"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("feature_importance_importance"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("feature_importance_mean"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("feature_importance_std"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("feature_importance_n"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            features.slice(0, 20).forEach((fe, idx) => {
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem">${idx + 1}</td>
                    <td style="padding:0.25rem">${escapeHtml(fe.feature || "–")}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(fe.importance || 0).toFixed(6)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(fe.mean_value || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(fe.std_value || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${fe.n_matches ?? 0}</td>
                </tr>`;
            });
            html += `</tbody></table>`;
            if (features.length > 20) {
                html += `<p style="margin-top:0.3rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(t("feature_importance_truncated").replace("{n}", String(features.length)))}</p>`;
            }
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("feature_importance_no_features"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("feature_importance_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderCICoverage() {
    const body = document.getElementById("backtest-ci-coverage-body");
    const btn = document.getElementById("btn-ci-coverage");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_coverage_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/ci-coverage");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_coverage_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("ci_coverage_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const assessmentColors = {
            well_calibrated: "var(--status-high, #4ade80)",
            undercoverage: "var(--status-low, #f87171)",
            overcoverage: "var(--status-medium, #fbbf24)",
            insufficient_data: "var(--text-muted)",
        };
        const assessmentColor = assessmentColors[data.coverage_assessment] || "var(--text-muted)";
        const nominalText = (data.nominal_level === null || data.nominal_level === undefined) ? "–" : Number(data.nominal_level).toFixed(2);
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600;color:${assessmentColor}">${escapeHtml(data.coverage_assessment || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_coverage_assessment"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_coverage || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_coverage_overall"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.avg_ci_width || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_coverage_avg_width"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${nominalText}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_coverage_nominal"))}</div>
            </div>
        </div>`;
        html += `<div style="font-size:0.72rem;color:var(--text-muted);margin-bottom:0.4rem">${escapeHtml(t("ci_coverage_n_matches"))}: ${data.n_matches ?? 0}</div>`;
        const buckets = Array.isArray(data.buckets) ? data.buckets : [];
        if (buckets.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.72rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("ci_coverage_bucket"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_coverage_conf_range"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_coverage_n"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_coverage_empirical"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_coverage_avg_width"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            for (const b of buckets) {
                const confRange = `[${Number(b.confidence_lower || 0).toFixed(3)}, ${Number(b.confidence_upper || 0).toFixed(3)}]`;
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem">${escapeHtml(b.bucket_label || "–")}</td>
                    <td style="padding:0.25rem;text-align:right">${confRange}</td>
                    <td style="padding:0.25rem;text-align:right">${b.n_matches ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(b.empirical_coverage || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(b.avg_ci_width || 0).toFixed(4)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_coverage_no_buckets"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("ci_coverage_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderDriftHeatmap() {
    const body = document.getElementById("backtest-drift-heatmap-body");
    const btn = document.getElementById("btn-drift-heatmap");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("drift_heatmap_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/drift-heatmap");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("drift_heatmap_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("drift_heatmap_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const driftColor = data.drift_detected ? "var(--status-low, #f87171)" : "var(--status-high, #4ade80)";
        const driftText = data.drift_detected ? t("drift_heatmap_drift_yes") : t("drift_heatmap_drift_no");
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600;color:${driftColor}">${escapeHtml(driftText)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("drift_heatmap_drift"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_windows ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("drift_heatmap_n_windows"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_confidence_buckets ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("drift_heatmap_n_buckets"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_total_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("drift_heatmap_n_matches"))}</div>
            </div>
        </div>`;
        const cells = Array.isArray(data.cells) ? data.cells : [];
        if (cells.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.7rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("drift_heatmap_window"))}</th>
                        <th style="padding:0.25rem">${escapeHtml(t("drift_heatmap_conf_bucket"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("drift_heatmap_n"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("drift_heatmap_accuracy"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("drift_heatmap_brier"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("drift_heatmap_rps"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("drift_heatmap_log_loss"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            for (const c of cells) {
                const ll = (c.log_loss === null || c.log_loss === undefined) ? "–" : Number(c.log_loss).toFixed(4);
                const brierColor = `hsl(${Math.max(0, 120 - Number(c.brier || 0) * 500)}, 70%, 45%)`;
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem;font-size:0.66rem">${escapeHtml(c.window_start || "–")} → ${escapeHtml(c.window_end || "–")}</td>
                    <td style="padding:0.25rem">${escapeHtml(c.confidence_bucket || "–")} <span style="font-size:0.62rem;color:var(--text-muted)">[${Number(c.confidence_lower || 0).toFixed(3)},${Number(c.confidence_upper || 0).toFixed(3)}]</span></td>
                    <td style="padding:0.25rem;text-align:right">${c.n_matches ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(c.accuracy || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${brierColor};font-weight:600">${Number(c.brier || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(c.rps || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${ll}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("drift_heatmap_no_cells"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("drift_heatmap_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderErrorClustering() {
    const body = document.getElementById("backtest-error-clustering-body");
    const btn = document.getElementById("btn-error-clustering");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("error_clustering_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/error-clustering");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("error_clustering_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("error_clustering_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_clusters ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("error_clustering_n_clusters"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_worst_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("error_clustering_n_worst"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_features_used ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("error_clustering_n_features"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_avg_brier || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("error_clustering_avg_brier"))}</div>
            </div>
        </div>`;
        const clusters = Array.isArray(data.clusters) ? data.clusters : [];
        if (clusters.length > 0) {
            for (const c of clusters) {
                const brierColor = `hsl(${Math.max(0, 120 - Number(c.avg_brier || 0) * 500)}, 70%, 45%)`;
                html += `<details style="margin-bottom:0.5rem;border:1px solid var(--border-color);border-radius:6px;padding:0.4rem">
                    <summary style="cursor:pointer;font-size:0.8rem;font-weight:600">
                        ${escapeHtml(t("error_clustering_cluster"))} #${c.cluster_id} · ${c.n_matches} ${escapeHtml(t("error_clustering_matches"))} · ${escapeHtml(t("error_clustering_brier"))}: <span style="color:${brierColor}">${Number(c.avg_brier || 0).toFixed(4)}</span>
                    </summary>
                    <div style="margin-top:0.4rem;font-size:0.72rem">
                        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.3rem;margin-bottom:0.4rem">
                            <div><span style="color:var(--text-muted)">${escapeHtml(t("error_clustering_accuracy"))}:</span> ${Number(c.accuracy || 0).toFixed(4)}</div>
                            <div><span style="color:var(--text-muted)">${escapeHtml(t("error_clustering_conf"))}:</span> ${Number(c.avg_confidence || 0).toFixed(4)}</div>
                            <div><span style="color:var(--text-muted)">${escapeHtml(t("error_clustering_actual"))}:</span> ${escapeHtml(c.dominant_actual_outcome || "–")}</div>
                            <div><span style="color:var(--text-muted)">${escapeHtml(t("error_clustering_predicted"))}:</span> ${escapeHtml(c.dominant_predicted_outcome || "–")}</div>
                        </div>
                        <table class="data-table" style="width:100%;font-size:0.68rem;border-collapse:collapse">
                            <thead><tr style="border-bottom:1px solid var(--border-color);text-align:left">
                                <th style="padding:0.2rem">${escapeHtml(t("error_clustering_feature"))}</th>
                                <th style="padding:0.2rem;text-align:right">${escapeHtml(t("error_clustering_centroid"))}</th>
                                <th style="padding:0.2rem;text-align:right">|z|</th>
                            </tr></thead>
                            <tbody>`;
                const feats = Array.isArray(c.top_centroid_features) ? c.top_centroid_features : [];
                for (const f of feats) {
                    const valColor = f.centroid_value >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)";
                    html += `<tr style="border-bottom:1px solid var(--border-color)">
                        <td style="padding:0.2rem">${escapeHtml(f.feature || "–")}</td>
                        <td style="padding:0.2rem;text-align:right;color:${valColor}">${Number(f.centroid_value || 0).toFixed(4)}</td>
                        <td style="padding:0.2rem;text-align:right">${Number(f.abs_centroid || 0).toFixed(4)}</td>
                    </tr>`;
                }
                html += `</tbody></table></div></details>`;
            }
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("error_clustering_no_clusters"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("error_clustering_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderDataDrift() {
    const body = document.getElementById("backtest-data-drift-body");
    const btn = document.getElementById("btn-data-drift");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("data_drift_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/data-drift");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("data_drift_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("data_drift_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const driftRatio = Number(data.drift_ratio || 0);
        const driftColor = driftRatio > 0.3 ? "var(--status-low, #f87171)" : (driftRatio > 0.1 ? "var(--status-medium, #fbbf24)" : "var(--status-high, #4ade80)");
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600;color:${driftColor}">${(driftRatio * 100).toFixed(1)}%</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("data_drift_ratio"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_drifted ?? 0}/${data.n_features ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("data_drift_drifted"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_train ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("data_drift_n_train"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_holdout ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("data_drift_n_holdout"))}</div>
            </div>
        </div>`;
        if (data.split_date) {
            html += `<p style="font-size:0.72rem;color:var(--text-muted);margin-bottom:0.4rem">${escapeHtml(t("data_drift_split_date"))}: ${escapeHtml(data.split_date)} · p&lt;${escapeHtml(String(data.p_value_threshold ?? 0.05))}</p>`;
        }
        const features = Array.isArray(data.features) ? data.features : [];
        if (features.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.7rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("data_drift_feature"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("data_drift_ks"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("data_drift_p_value"))}</th>
                        <th style="padding:0.25rem;text-align:center">${escapeHtml(t("data_drift_status"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("data_drift_train_mean"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("data_drift_holdout_mean"))}</th>
                        <th style="padding:0.25rem;text-align:right">Δ</th>
                    </tr>
                </thead>
                <tbody>`;
            for (const f of features) {
                const statusColor = f.drifted ? "var(--status-low, #f87171)" : "var(--status-high, #4ade80)";
                const statusText = f.drifted ? t("data_drift_drifted_yes") : t("data_drift_drifted_no");
                const deltaColor = (f.mean_delta || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem">${escapeHtml(f.feature || "–")}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(f.ks_statistic || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(f.p_value || 0).toFixed(6)}</td>
                    <td style="padding:0.25rem;text-align:center;color:${statusColor};font-weight:600">${escapeHtml(statusText)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(f.train_mean || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(f.holdout_mean || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${deltaColor}">${Number(f.mean_delta || 0).toFixed(4)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("data_drift_no_features"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("data_drift_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderCIWidth() {
    const body = document.getElementById("backtest-ci-width-body");
    const btn = document.getElementById("btn-ci-width");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_width_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/ci-width");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_width_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("ci_width_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const assessmentColors = {
            "expected_narrowing": "var(--status-high, #4ade80)",
            "weak_correlation": "var(--status-medium, #fbbf24)",
            "anomalous_widening": "var(--status-low, #f87171)",
            "insufficient_data": "var(--text-muted)",
        };
        const assessmentColor = assessmentColors[data.assessment] || "var(--text-muted)";
        const corr = data.width_confidence_correlation;
        const corrColor = corr !== null && corr !== undefined ? (corr < -0.3 ? "var(--status-high, #4ade80)" : (corr > 0.3 ? "var(--status-low, #f87171)" : "var(--status-medium, #fbbf24)")) : "var(--text-muted)";
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${assessmentColor}">${escapeHtml(data.assessment || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_width_assessment"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_avg_ci_width || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_width_avg"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_avg_confidence || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_width_avg_conf"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600;color:${corrColor}">${corr !== null && corr !== undefined ? Number(corr).toFixed(4) : "–"}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("ci_width_corr"))}</div>
            </div>
        </div>`;
        const buckets = Array.isArray(data.buckets) ? data.buckets : [];
        if (buckets.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.7rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("ci_width_bucket"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_width_n"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_width_avg_width"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_width_avg_lower"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_width_avg_upper"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_width_std"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("ci_width_relative"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            for (const b of buckets) {
                const widthColor = `hsl(${Math.max(0, 120 - Number(b.relative_width || 0) * 200)}, 70%, 45%)`;
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem">${escapeHtml(b.bucket_label || "–")} <span style="font-size:0.62rem;color:var(--text-muted)">[${Number(b.confidence_lower || 0).toFixed(3)},${Number(b.confidence_upper || 0).toFixed(3)}]</span></td>
                    <td style="padding:0.25rem;text-align:right">${b.n_matches ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right;font-weight:600">${Number(b.avg_ci_width || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(b.avg_ci_lower || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(b.avg_ci_upper || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(b.width_std || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${widthColor}">${Number(b.relative_width || 0).toFixed(4)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("ci_width_no_buckets"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("ci_width_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderStressTest() {
    const body = document.getElementById("backtest-stress-test-body");
    const btn = document.getElementById("btn-stress-test");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("stress_test_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/stress-test");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("stress_test_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("stress_test_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const assessmentColors = {
            "severe": "var(--status-low, #f87171)",
            "moderate": "var(--status-medium, #fbbf24)",
            "mild": "var(--status-high, #4ade80)",
            "negligible": "var(--status-high, #4ade80)",
        };
        const assessmentColor = assessmentColors[data.assessment] || "var(--text-muted)";
        const degColor = data.degradation_score >= 0.5 ? "var(--status-low, #f87171)" : (data.degradation_score >= 0.2 ? "var(--status-medium, #fbbf24)" : "var(--status-high, #4ade80)");
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${assessmentColor}">${escapeHtml(data.assessment || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("stress_test_assessment"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600;color:${degColor}">${Number(data.degradation_score || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("stress_test_degradation"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${escapeHtml(data.shift_type || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("stress_test_shift_type"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_shifted ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("stress_test_n_shifted"))}</div>
            </div>
        </div>`;
        const baseline = data.baseline || {};
        const stressed = data.stressed || {};
        const fmt = (v) => v !== null && v !== undefined ? Number(v).toFixed(4) : "–";
        const deltaColor = (d) => d > 0 ? "var(--status-low, #f87171)" : (d < 0 ? "var(--status-high, #4ade80)" : "var(--text-muted)");
        html += `<table class="data-table" style="width:100%;font-size:0.72rem;border-collapse:collapse;margin-bottom:0.4rem">
            <thead>
                <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                    <th style="padding:0.25rem">${escapeHtml(t("stress_test_n_matches"))}</th>
                    <th style="padding:0.25rem;text-align:right">${escapeHtml(t("stress_test_accuracy"))}</th>
                    <th style="padding:0.25rem;text-align:right">${escapeHtml(t("stress_test_brier"))}</th>
                    <th style="padding:0.25rem;text-align:right">${escapeHtml(t("stress_test_rps"))}</th>
                    <th style="padding:0.25rem;text-align:right">${escapeHtml(t("stress_test_log_loss"))}</th>
                    <th style="padding:0.25rem;text-align:right">${escapeHtml(t("stress_test_conf"))}</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem;font-weight:600">${escapeHtml(t("stress_test_baseline"))}</td>
                    <td style="padding:0.25rem;text-align:right">${baseline.n_matches ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(baseline.accuracy)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(baseline.brier)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(baseline.rps)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(baseline.log_loss)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(baseline.avg_confidence)}</td>
                </tr>
                <tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem;font-weight:600">${escapeHtml(t("stress_test_stressed"))}</td>
                    <td style="padding:0.25rem;text-align:right">${stressed.n_matches ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(stressed.accuracy)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(stressed.brier)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(stressed.rps)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(stressed.log_loss)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(stressed.avg_confidence)}</td>
                </tr>
                <tr style="border-bottom:1px solid var(--border-color);font-weight:600">
                    <td style="padding:0.25rem">Δ</td>
                    <td style="padding:0.25rem;text-align:right;color:${deltaColor(data.accuracy_delta)}">${fmt(data.accuracy_delta)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${deltaColor(data.brier_delta)}">${fmt(data.brier_delta)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${deltaColor(data.rps_delta)}">${fmt(data.rps_delta)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(data.log_loss_delta)}</td>
                    <td style="padding:0.25rem;text-align:right">${fmt(data.confidence_delta)}</td>
                </tr>
            </tbody>
        </table>`;
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("stress_test_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderTeamDrift() {
    const body = document.getElementById("backtest-team-drift-body");
    const btn = document.getElementById("btn-team-drift");
    if (!body) return;
    if (btn) btn.disabled = true;
    let teamName = "";
    const input = document.getElementById("team-drift-input");
    if (input) teamName = (input.value || "").trim();
    if (!teamName) {
        body.innerHTML = `<div style="margin-bottom:0.4rem">
            <label style="font-size:0.78rem;color:var(--text-muted)">${escapeHtml(t("stress_test_team_input"))}</label>
            <input id="team-drift-input" type="text" placeholder="${escapeHtml(t("stress_test_team_input_ph"))}" style="margin-left:0.4rem;padding:0.2rem 0.4rem;font-size:0.78rem;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-base);color:var(--text-primary)" />
        </div>
        <p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("team_drift_not_available"))}</p>`;
        if (btn) btn.disabled = false;
        return;
    }
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("team_drift_loading"))}</p>`;
    try {
        const params = new URLSearchParams({ team_name: teamName });
        const data = await apiFetch(`/predictions/calibration/team-drift?${params.toString()}`);
        const inputHtml = `<div style="margin-bottom:0.4rem">
            <label style="font-size:0.78rem;color:var(--text-muted)">${escapeHtml(t("stress_test_team_input"))}</label>
            <input id="team-drift-input" type="text" value="${escapeHtml(teamName)}" placeholder="${escapeHtml(t("stress_test_team_input_ph"))}" style="margin-left:0.4rem;padding:0.2rem 0.4rem;font-size:0.78rem;border:1px solid var(--border-color);border-radius:4px;background:var(--bg-base);color:var(--text-primary)" />
        </div>`;
        if (!data || data.status === "not_available") {
            body.innerHTML = inputHtml + `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("team_drift_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = inputHtml + `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("team_drift_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const driftColor = data.drift_detected ? "var(--status-low, #f87171)" : "var(--status-high, #4ade80)";
        const trendColors = {
            "improving": "var(--status-high, #4ade80)",
            "degrading": "var(--status-low, #f87171)",
            "stable": "var(--status-medium, #fbbf24)",
            "insufficient_data": "var(--text-muted)",
        };
        const trendColor = trendColors[data.trend] || "var(--text-muted)";
        let html = inputHtml + `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${driftColor}">${data.drift_detected ? escapeHtml(t("team_drift_drift_yes")) : escapeHtml(t("team_drift_drift_no"))}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("team_drift_drift_detected"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_total_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("team_drift_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_windows ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("team_drift_n_windows"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600;color:${trendColor}">${escapeHtml(data.trend || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("team_drift_trend"))}</div>
            </div>
        </div>`;
        html += `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${Number(data.latest_brier || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("team_drift_latest_brier"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${Number(data.historical_avg_brier || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("team_drift_hist_brier"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${driftColor}">${Number(data.relative_change || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("team_drift_rel_change"))}</div>
            </div>
        </div>`;
        const points = Array.isArray(data.points) ? data.points : [];
        if (points.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.7rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("team_drift_window"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("team_drift_n"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("team_drift_acc"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("team_drift_brier"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("team_drift_conf"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            for (const p of points) {
                const brierColor = `hsl(${Math.max(0, 120 - Number(p.brier || 0) * 200)}, 70%, 45%)`;
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem;font-size:0.65rem">${escapeHtml(p.window_label || "–")}</td>
                    <td style="padding:0.25rem;text-align:right">${p.n_matches ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.accuracy || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;font-weight:600;color:${brierColor}">${Number(p.brier || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.avg_confidence || 0).toFixed(4)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("team_drift_no_points"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("team_drift_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderUncertainty() {
    const body = document.getElementById("backtest-uncertainty-body");
    const btn = document.getElementById("btn-uncertainty");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("uncertainty_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/uncertainty");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("uncertainty_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("uncertainty_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const corr = data.entropy_accuracy_correlation;
        const corrColor = corr !== null && corr !== undefined ? (corr < -0.3 ? "var(--status-high, #4ade80)" : (corr > 0.3 ? "var(--status-low, #f87171)" : "var(--status-medium, #fbbf24)")) : "var(--text-muted)";
        const highAccColor = data.high_uncertainty_accuracy < 0.5 ? "var(--status-low, #f87171)" : "var(--status-high, #4ade80)";
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.avg_entropy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("uncertainty_avg_entropy"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.avg_margin || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("uncertainty_avg_margin"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.avg_dispersion || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("uncertainty_avg_dispersion"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.high_uncertainty_count ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("uncertainty_high_count"))}</div>
            </div>
        </div>`;
        html += `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${highAccColor}">${Number(data.high_uncertainty_accuracy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("uncertainty_high_acc"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${Number(data.low_uncertainty_accuracy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("uncertainty_low_acc"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${corrColor}">${corr !== null && corr !== undefined ? Number(corr).toFixed(4) : "–"}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("uncertainty_entropy_corr"))}</div>
            </div>
        </div>`;
        const points = Array.isArray(data.points) ? data.points : [];
        if (points.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.68rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("uncertainty_match"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("uncertainty_conf"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("uncertainty_entropy"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("uncertainty_margin"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("uncertainty_dispersion"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("uncertainty_predicted"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("uncertainty_label"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("uncertainty_correct"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            const shown = points.slice(0, 50);
            for (const p of shown) {
                const labelColors = {
                    "high": "var(--status-low, #f87171)",
                    "medium": "var(--status-medium, #fbbf24)",
                    "low": "var(--status-high, #4ade80)",
                };
                const labelColor = labelColors[p.uncertainty_label] || "var(--text-muted)";
                const matchLabel = p.home_team && p.away_team ? `${escapeHtml(p.home_team)} vs ${escapeHtml(p.away_team)}` : (p.match_id ? escapeHtml(p.match_id) : "–");
                const correctMark = p.correct === true ? "✓" : (p.correct === false ? "✗" : "–");
                const correctColor = p.correct === true ? "var(--status-high, #4ade80)" : (p.correct === false ? "var(--status-low, #f87171)" : "var(--text-muted)");
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem">${matchLabel}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.confidence || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.entropy || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.margin || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.dispersion || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${escapeHtml(p.predicted_outcome || "–")}</td>
                    <td style="padding:0.25rem;text-align:right;color:${labelColor}">${escapeHtml(p.uncertainty_label || "–")}</td>
                    <td style="padding:0.25rem;text-align:right;color:${correctColor}">${correctMark}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
            if (points.length > 50) {
                html += `<p style="margin-top:0.3rem;font-size:0.68rem;color:var(--text-muted)">Showing 50 of ${points.length} points</p>`;
            }
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("uncertainty_no_points"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("uncertainty_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderProfitLoss() {
    const body = document.getElementById("backtest-profit-loss-body");
    const btn = document.getElementById("btn-profit-loss");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("profit_loss_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/profit-loss");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("profit_loss_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("profit_loss_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const assessmentColors = {
            "profitable": "var(--status-high, #4ade80)",
            "breakeven": "var(--status-medium, #fbbf24)",
            "unprofitable": "var(--status-low, #f87171)",
        };
        const assColor = assessmentColors[data.assessment] || "var(--text-muted)";
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.win_rate || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_win_rate"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${Number(data.flat_roi || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)"}">${Number(data.flat_roi || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_flat_roi"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${assColor}">${escapeHtml(data.assessment || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_assessment"))}</div>
            </div>
        </div>`;
        html += `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${Number(data.total_flat_profit || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)"}">${Number(data.total_flat_profit || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_flat_profit"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${Number(data.max_flat_drawdown || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_max_dd"))} (Flat)</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${Number(data.total_kelly_profit || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)"}">${Number(data.total_kelly_profit || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_kelly_profit"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${Number(data.kelly_roi || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)"}">${Number(data.kelly_roi || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("profit_loss_kelly_roi"))}</div>
            </div>
        </div>`;
        const points = Array.isArray(data.points) ? data.points : [];
        if (points.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.68rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("profit_loss_match"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_predicted"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_actual"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_correct"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_prob"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_odds"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_flat_stake"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_cum_flat"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_kelly_stake"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("profit_loss_cum_kelly"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            const shown = points.slice(0, 50);
            for (const p of shown) {
                const correctMark = p.correct ? "✓" : "✗";
                const correctColor = p.correct ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)";
                const flatColor = Number(p.flat_profit || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)";
                const kellyColor = Number(p.kelly_profit || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem">${p.match_index ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${escapeHtml(p.predicted_outcome || "–")}</td>
                    <td style="padding:0.25rem;text-align:right">${escapeHtml(p.actual_outcome || "–")}</td>
                    <td style="padding:0.25rem;text-align:right;color:${correctColor}">${correctMark}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.model_probability || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.implied_odds || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${flatColor}">${Number(p.flat_profit || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.cumulative_flat_profit || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${kellyColor}">${Number(p.kelly_profit || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.cumulative_kelly_profit || 0).toFixed(4)}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
            if (points.length > 50) {
                html += `<p style="margin-top:0.3rem;font-size:0.68rem;color:var(--text-muted)">Showing 50 of ${points.length} points</p>`;
            }
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("profit_loss_no_points"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("profit_loss_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderTrajectory() {
    const body = document.getElementById("backtest-trajectory-body");
    const btn = document.getElementById("btn-trajectory");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("trajectory_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/trajectory");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("trajectory_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("trajectory_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        const trendColors = {
            "improving": "var(--status-high, #4ade80)",
            "degrading": "var(--status-low, #f87171)",
            "stable": "var(--status-medium, #fbbf24)",
            "insufficient_data": "var(--text-muted)",
        };
        const trendColor = trendColors[data.trend] || "var(--text-muted)";
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.final_accuracy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_final_acc"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${Number(data.final_brier || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_final_brier"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:0.9rem;font-weight:600;color:${trendColor}">${escapeHtml(data.trend || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_trend"))}</div>
            </div>
        </div>`;
        html += `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600;color:${Number(data.final_profit || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)"}">${Number(data.final_profit || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_final_profit"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${Number(data.best_window_accuracy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_best_win"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${Number(data.worst_window_accuracy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_worst_win"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${data.n_change_points ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("trajectory_change_points"))}</div>
            </div>
        </div>`;
        const points = Array.isArray(data.points) ? data.points : [];
        if (points.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.68rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("trajectory_index"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("trajectory_cum_acc"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("trajectory_cum_brier"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("trajectory_cum_profit"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("trajectory_roll_acc"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("trajectory_roll_brier"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("trajectory_date"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            const shown = points.slice(0, 50);
            for (const p of shown) {
                const profitColor = Number(p.cumulative_profit || 0) >= 0 ? "var(--status-high, #4ade80)" : "var(--status-low, #f87171)";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem">${p.match_index ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.cumulative_accuracy || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(p.cumulative_brier || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${profitColor}">${Number(p.cumulative_profit || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${p.rolling_accuracy != null ? Number(p.rolling_accuracy).toFixed(4) : "–"}</td>
                    <td style="padding:0.25rem;text-align:right">${p.rolling_brier != null ? Number(p.rolling_brier).toFixed(4) : "–"}</td>
                    <td style="padding:0.25rem;text-align:right;font-size:0.65rem">${escapeHtml(p.match_date || "–")}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
            if (points.length > 50) {
                html += `<p style="margin-top:0.3rem;font-size:0.68rem;color:var(--text-muted)">Showing 50 of ${points.length} points</p>`;
            }
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("trajectory_no_points"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("trajectory_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function fetchAndRenderDifficulty() {
    const body = document.getElementById("backtest-difficulty-body");
    const btn = document.getElementById("btn-difficulty");
    if (!body) return;
    if (btn) btn.disabled = true;
    body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("difficulty_loading"))}</p>`;
    try {
        const data = await apiFetch("/predictions/calibration/difficulty");
        if (!data || data.status === "not_available") {
            body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("difficulty_not_available"))}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        if (data.status === "error") {
            body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("difficulty_error"))}: ${escapeHtml(data.message || "")}</p>`;
            if (btn) btn.disabled = false;
            return;
        }
        let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin-bottom:0.8rem">
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${data.n_matches ?? 0}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("difficulty_n_matches"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.1rem;font-weight:600">${Number(data.overall_accuracy || 0).toFixed(4)}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("difficulty_overall_acc"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${escapeHtml(data.best_tier || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("difficulty_best_tier"))}</div>
            </div>
            <div style="text-align:center;padding:0.4rem;background:var(--bg-elevated);border-radius:6px">
                <div style="font-size:1.0rem;font-weight:600">${escapeHtml(data.worst_tier || "–")}</div>
                <div style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(t("difficulty_worst_tier"))}</div>
            </div>
        </div>`;
        const tiers = Array.isArray(data.tiers) ? data.tiers : [];
        if (tiers.length > 0) {
            html += `<table class="data-table" style="width:100%;font-size:0.7rem;border-collapse:collapse">
                <thead>
                    <tr style="border-bottom:1px solid var(--border-color);text-align:left">
                        <th style="padding:0.25rem">${escapeHtml(t("difficulty_tier"))}</th>
                        <th style="padding:0.25rem;text-align:right">N</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("difficulty_acc"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("difficulty_brier"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("difficulty_rps"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("difficulty_log_loss"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("difficulty_conf"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("difficulty_cal_gap"))}</th>
                        <th style="padding:0.25rem;text-align:right">${escapeHtml(t("difficulty_assessment"))}</th>
                    </tr>
                </thead>
                <tbody>`;
            const assessmentColors = {
                "strong": "var(--status-high, #4ade80)",
                "average": "var(--status-medium, #fbbf24)",
                "weak": "var(--status-low, #f87171)",
                "no_data": "var(--text-muted)",
            };
            for (const tr of tiers) {
                const brierColor = `hsl(${Math.max(0, 120 - Number(tr.brier || 0) * 200)}, 70%, 45%)`;
                const assColor = assessmentColors[tr.assessment] || "var(--text-muted)";
                html += `<tr style="border-bottom:1px solid var(--border-color)">
                    <td style="padding:0.25rem;font-size:0.65rem">${escapeHtml(tr.tier || "–")}</td>
                    <td style="padding:0.25rem;text-align:right">${tr.n_matches ?? 0}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(tr.accuracy || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;font-weight:600;color:${brierColor}">${Number(tr.brier || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(tr.rps || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${tr.log_loss != null ? Number(tr.log_loss).toFixed(4) : "–"}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(tr.avg_confidence || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right">${Number(tr.calibration_gap || 0).toFixed(4)}</td>
                    <td style="padding:0.25rem;text-align:right;color:${assColor}">${escapeHtml(tr.assessment || "–")}</td>
                </tr>`;
            }
            html += `</tbody></table>`;
        } else {
            html += `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("difficulty_no_tiers"))}</p>`;
        }
        if (data.disclaimer) {
            html += `<p style="margin-top:0.4rem;font-size:0.68rem;color:var(--text-muted)">${escapeHtml(data.disclaimer)}</p>`;
        }
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--text-low);font-size:0.85rem">${escapeHtml(t("difficulty_error"))}: ${escapeHtml(String(e))}</p>`;
    }
    if (btn) btn.disabled = false;
}

async function renderHeadToHead(home, away) {
    const container = document.getElementById("match-h2h-content");
    const statusPill = document.getElementById("h2h-status");
    if (!container) return;

    container.setAttribute("aria-busy", "true");
    container.innerHTML = `<p class="h2h-message">加载中...</p>`;
    if (statusPill) { statusPill.textContent = "loading"; statusPill.className = "status-pill status-medium"; }

    const data = await fetchHeadToHead(home, away);
    capturePredictionEvidence("head_to_head", home, away, compactHeadToHeadEvidence(data));

    if (!data || data.error) {
        container.innerHTML = `<p class="h2h-message">交锋记录加载失败</p>`;
        container.setAttribute("aria-busy", "false");
        if (statusPill) { statusPill.textContent = "–"; }
        return;
    }

    const h2h = Array.isArray(data.head_to_head) ? data.head_to_head : [];
    const summary = data.summary || {};
    const totalMeetings = Number(summary.total_meetings) || 0;
    const homeForm = Array.isArray(data.home_form) ? data.home_form : [];
    const awayForm = Array.isArray(data.away_form) ? data.away_form : [];

    if (h2h.length === 0 && homeForm.length === 0 && awayForm.length === 0) {
        container.innerHTML = `<p class="h2h-message">暂无交锋或近期比赛数据</p>`;
        container.setAttribute("aria-busy", "false");
        if (statusPill) { statusPill.textContent = "0"; }
        return;
    }

    const homeName = escapeHtml(data.home_team || home);
    const awayName = escapeHtml(data.away_team || away);
    const homeWins = Number(summary.home_wins) || 0;
    const draws = Number(summary.draws) || 0;
    const awayWins = Number(summary.away_wins) || 0;
    const total = homeWins + draws + awayWins;

    let html = "";

    // 1. H2H Summary bar (CSS flexbox proportional bars)
    if (total > 0) {
        html += `<div class="h2h-summary">`;
        html += `<div class="h2h-eyebrow">交锋总览 · ${total} 场</div>`;
        html += `<div class="h2h-ratio" role="img" aria-label="${homeName} ${homeWins} 胜，平局 ${draws} 场，${awayName} ${awayWins} 胜">`;
        if (homeWins > 0) html += `<div class="h2h-segment h2h-segment-home" style="flex:${homeWins}">${homeName} ${homeWins}</div>`;
        if (draws > 0) html += `<div class="h2h-segment h2h-segment-draw" style="flex:${draws}">平 ${draws}</div>`;
        if (awayWins > 0) html += `<div class="h2h-segment h2h-segment-away" style="flex:${awayWins}">${awayWins} ${awayName}</div>`;
        html += `</div>`;

        const homeAvg = Number(summary.home_goals_avg) || 0;
        const awayAvg = Number(summary.away_goals_avg) || 0;
        html += `<div class="h2h-meta">场均进球: ${homeName} ${homeAvg.toFixed(2)} · ${awayName} ${awayAvg.toFixed(2)}</div>`;
        if (summary.last_meeting_date) html += `<div class="h2h-meta">上次交锋: ${escapeHtml(String(summary.last_meeting_date))}</div>`;
        html += `</div>`;
    } else {
        html += `<p class="h2h-message h2h-message-inline">暂无直接交锋记录，仍可参考近期状态</p>`;
    }

    // 2. H2H Recent Matches list
    const recentH2h = h2h.slice(0, 10);
    if (recentH2h.length > 0) {
        html += `<div class="h2h-history">`;
        html += `<div class="h2h-eyebrow">近期交锋</div>`;
        html += `<div class="table-scroll h2h-table-scroll">`;
        html += `<table class="h2h-table">`;
        html += `<caption class="sr-only">${homeName} 与 ${awayName} 的近期交锋</caption>`;
        html += `<thead><tr><th style="text-align:left">日期</th><th style="text-align:left">赛事</th><th style="text-align:left">比分</th><th>结果</th></tr></thead><tbody>`;
        for (const m of recentH2h) {
            const date = escapeHtml(String(m.date || "–"));
            const league = escapeHtml(String(m.league || "–"));
            const season = escapeHtml(String(m.season || ""));
            const mHome = escapeHtml(String(m.home_team || "–"));
            const mAway = escapeHtml(String(m.away_team || "–"));
            const hg = m.home_goals != null ? escapeHtml(String(m.home_goals)) : "–";
            const ag = m.away_goals != null ? escapeHtml(String(m.away_goals)) : "–";
            const badge = _h2hResultBadge(m, data.home_team || home);
            const leagueLabel = season ? `${league} ${season}` : league;
            html += `<tr>`;
            html += `<td class="h2h-muted h2h-nowrap">${date}</td>`;
            html += `<td class="h2h-muted">${leagueLabel}</td>`;
            html += `<td><strong>${mHome} ${hg} - ${ag} ${mAway}</strong></td>`;
            html += `<td class="h2h-result-cell"><span class="${_h2hBadgeClass(badge)}" aria-label="查询主队结果 ${escapeHtml(badge)}">${escapeHtml(badge)}</span></td>`;
            html += `</tr>`;
        }
        html += `</tbody></table></div></div>`;
    }

    // 3. Form comparison (two columns side by side)
    const homeFormSummary = data.home_form_summary || {};
    const awayFormSummary = data.away_form_summary || {};

    html += `<div class="h2h-form-grid">`;
    html += _renderFormColumn(homeName, homeFormSummary, homeForm);
    html += _renderFormColumn(awayName, awayFormSummary, awayForm);
    html += `</div>`;

    // 4. Form trend comparison (momentum, rating, goals trend)
    const homeTrend = data.home_form_trend || null;
    const awayTrend = data.away_form_trend || null;
    if (homeTrend || awayTrend) {
        html += `<div class="h2h-eyebrow">近期趋势</div>`;
        html += `<div class="h2h-form-grid">`;
        html += _renderFormTrendCard(homeName, homeTrend);
        html += _renderFormTrendCard(awayName, awayTrend);
        html += `</div>`;
    }

    // 5. Data coverage note
    const coverage = data.data_coverage || {};
    const seasons = Array.isArray(coverage.seasons_covered) ? coverage.seasons_covered : [];
    const source = escapeHtml(String(coverage.source || "Football-Data"));
    html += `<div class="h2h-coverage">`;
    html += `数据来源: ${source}, 覆盖 ${seasons.length} 赛季`;
    html += `</div>`;

    container.innerHTML = html;
    container.setAttribute("aria-busy", "false");
    if (statusPill) {
        statusPill.textContent = String(totalMeetings);
        statusPill.className = `status-pill ${totalMeetings > 0 ? "status-high" : "status-medium"}`;
    }
}

async function fetchActionValueEvidenceIndex() {
    try {
        const data = await fetchJson("/action-values/evidence");
        if (data && data.players && !Array.isArray(data.available_player_ids)) {
            const playerIndex = Array.isArray(data.player_index) ? data.player_index : [];
            return {
                status: data.status || "ok",
                schema_version: data.schema_version,
                coverage: data.coverage || {},
                player_index: playerIndex,
                available_player_ids: Object.keys(data.players),
            };
        }
        return data || { status: "no_data", coverage: {}, available_player_ids: [] };
    } catch (err) {
        console.warn("Failed to fetch action-value evidence index:", err);
        return { status: "no_data", coverage: {}, player_index: [], available_player_ids: [] };
    }
}

async function fetchActionValueEvidence(playerId) {
    try {
        const data = await fetchJson(`/action-values/evidence/${encodeURIComponent(playerId)}`);
        if (data && data.players && typeof data.players === "object") {
            return data.players[String(playerId)] || {
                status: "not_found",
                player_id: String(playerId),
                matches: [],
                coverage: data.coverage || {},
            };
        }
        return data;
    } catch (err) {
        console.warn("Failed to fetch player action-value evidence:", err);
        return { status: "error", player_id: String(playerId), matches: [], coverage: {} };
    }
}

async function fetchActionValuePlayerContext(playerId) {
    try {
        return await fetchJson(`/action-values/players/${encodeURIComponent(playerId)}/context`);
    } catch (err) {
        const explorer = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER : null;
        if (explorer) {
            return explorer.playerContextFromRows(
                playerId,
                actionValueSummary.xt_players || actionValueSummary.players || [],
                actionValueSummary.vaep_players || [],
                actionValueMatchSummary.rows || [],
            );
        }
        return { status: "not_available", models: {}, match_sample: { rows: [] } };
    }
}

async function fetchActionValueRatingLinks(playerId) {
    try {
        return await fetchJson(`/action-values/players/${encodeURIComponent(playerId)}/rating-links`);
    } catch (err) {
        console.warn("Failed to fetch action-value rating links:", err);
        return { status: "rating_artifact_unavailable", rating_candidates: [] };
    }
}

async function renderCompare() {
    const btn = document.getElementById("compare-btn");
    const inputA = document.getElementById("compare-input-a");
    const inputB = document.getElementById("compare-input-b");

    // Wire typeahead first so its keydown handler runs before the Enter handler below
    SearchTypeahead("compare-input-a", "players");
    SearchTypeahead("compare-input-b", "players");

    if (btn && !btn.dataset.bound) {
        btn.dataset.bound = "1";
        btn.addEventListener("click", async () => {
            const a = inputA.value.trim();
            const b = inputB.value.trim();
            if (!a || !b) return;
            btn.disabled = true;
            btn.textContent = "...";
            try {
                await _renderCompareResult(a, b);
            } finally {
                btn.disabled = false;
                btn.textContent = t("compare_button");
            }
        });
        // Allow Enter key
        const handler = (e) => { if (e.key === "Enter") btn.click(); };
        if (inputA) inputA.addEventListener("keydown", handler);
        if (inputB) inputB.addEventListener("keydown", handler);
    }

    // Wire the CSV export button
    const exportBtn = document.getElementById("btn-compare-export-csv");
    if (exportBtn && !exportBtn.dataset.bound) {
        exportBtn.dataset.bound = "1";
        exportBtn.addEventListener("click", exportPlayerComparisonCSV);
    }
    const exportJsonBtn = document.getElementById("btn-compare-export-json");
    if (exportJsonBtn && !exportJsonBtn.dataset.bound) {
        exportJsonBtn.dataset.bound = "1";
        exportJsonBtn.addEventListener("click", exportPlayerComparisonJSON);
    }
}

function _safeCompareFilename(data) {
    const left = (data?.player_a?.name || "player_a").replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]/g, "_");
    const right = (data?.player_b?.name || "player_b").replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]/g, "_");
    return `compare_${left}_vs_${right}`;
}

function exportPlayerComparisonJSON() {
    const comparison = appState.lastCompareData;
    if (!comparison || comparison.error) return;
    const payload = {
        schema: "scoutfootball.player-comparison-export",
        version: "1.0.0",
        exported_at: new Date().toISOString(),
        storage_scope: "browser-local-download",
        comparison,
        limitations: [
            "Position percentiles are relative to each player's loaded position pool.",
            "This export is not a transfer recommendation or a server-side audit record.",
        ],
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${_safeCompareFilename(comparison)}.json`;
    link.click();
    URL.revokeObjectURL(url);
}

function exportPlayerComparisonCSV() {
    const data = appState.lastCompareData;
    if (!data || data.error) return;
    const nameA = data.player_a ? data.player_a.name : "A";
    const nameB = data.player_b ? data.player_b.name : "B";
    const lines = [];

    // Section 1: Player profiles
    lines.push(["# Player Comparison"]);
    lines.push(["field", "player_a", "player_b"]);
    const pa = data.player_a || {};
    const pb = data.player_b || {};
    for (const key of ["name", "team", "position_group", "position", "season", "league", "rating", "minutes"]) {
        lines.push([key, pa[key] ?? "", pb[key] ?? ""]);
    }
    lines.push([]);

    // Section 2: Radar values
    lines.push(["# Radar (0-100 percentile)"]);
    lines.push(["dimension", nameA, nameB]);
    const labels = data.radar_labels || [];
    const radarA = data.radar_a || [];
    const radarB = data.radar_b || [];
    for (let i = 0; i < labels.length; i++) {
        lines.push([labels[i], radarA[i] ?? "", radarB[i] ?? ""]);
    }
    lines.push([]);

    // Section 3: Stats comparison
    lines.push(["# Stats Comparison"]);
    lines.push(["metric", nameA, nameB, "diff"]);
    for (const s of (data.stats_comparison || [])) {
        lines.push([s.metric, s.player_a ?? "", s.player_b ?? "", s.diff ?? ""]);
    }
    lines.push([]);

    // Section 4: Position percentile comparison
    lines.push(["# Position Percentile Comparison"]);
    lines.push(["dimension", nameA, nameB, "diff"]);
    for (const p of (data.position_percentile_comparison || [])) {
        lines.push([p.dimension, p.player_a ?? "", p.player_b ?? "", p.diff ?? ""]);
    }
    lines.push([]);

    lines.push(["# Exported", new Date().toISOString(), "ScoutFootball v" + APP_VERSION]);

    const csv = lines.map(r => r.map(csvCell).join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${_safeCompareFilename(data)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

async function _renderCompareResult(a, b) {
    const data = await fetchPlayerComparison(a, b);
    appState.lastCompareData = data;
    const shortlistActions = document.getElementById("compare-shortlist-actions");
    if (shortlistActions) {
        const players = [data.player_a, data.player_b].filter(Boolean);
        shortlistActions.style.display = players.length ? "flex" : "none";
        shortlistActions.innerHTML = `${players.map((player, index) => `<button class="text-button compare-add-shortlist" data-compare-shortlist-index="${index}" type="button">${escapeHtml(appState.lang === "zh" ? `加入短名单：${player.name || "球员"}` : `Add to shortlist: ${player.name || "Player"}`)}</button>`).join("")}<span class="toolbar-status">${escapeHtml(appState.lang === "zh" ? "仅保存到当前浏览器" : "Saved in this browser only")}</span>`;
        shortlistActions.querySelectorAll(".compare-add-shortlist").forEach((button) => {
            button.addEventListener("click", () => {
                const player = players[Number(button.dataset.compareShortlistIndex)];
                if (!player) return;
                const key = String(player.player_id || player.key || player.name || "");
                if (!key) return;
                const list = getPlayerShortlist();
                if (!list.some((entry) => entry.key === key)) {
                    list.push({ key, name: player.name || "", team: player.team || "", position: player.position_group || player.position || "", rating: player.rating ?? "" });
                    savePlayerShortlist(list);
                }
                button.disabled = true;
                button.textContent = appState.lang === "zh" ? "已加入短名单" : "Added to shortlist";
            });
        });
    }
    const wrap = document.getElementById("compare-result-wrap");
    const pctPanel = document.getElementById("compare-pct-panel");

    if (data.error) {
        if (wrap) wrap.style.display = "none";
        if (pctPanel) pctPanel.style.display = "none";
        alert(data.error);
        return;
    }

    if (wrap) wrap.style.display = "flex";

    // Update column headers with player names
    const colA = document.getElementById("compare-col-a");
    const colB = document.getElementById("compare-col-b");
    const pctColA = document.getElementById("compare-pct-col-a");
    const pctColB = document.getElementById("compare-pct-col-b");
    const nameA = data.player_a ? data.player_a.name : a;
    const nameB = data.player_b ? data.player_b.name : b;
    if (colA) colA.textContent = nameA;
    if (colB) colB.textContent = nameB;
    if (pctColA) pctColA.textContent = nameA;
    if (pctColB) pctColB.textContent = nameB;

    // Position pill
    const posPill = document.getElementById("compare-position-pill");
    if (posPill) {
        const posA = data.player_a ? data.player_a.position_group : "";
        const posB = data.player_b ? data.player_b.position_group : "";
        posPill.textContent = posA === posB ? posA : `${posA} vs ${posB}`;
    }

    // Render stats table
    const statsBody = document.getElementById("compare-stats-body");
    if (statsBody) {
        statsBody.innerHTML = (data.stats_comparison || []).map(s => {
            const valA = s.player_a !== null && s.player_a !== undefined ? s.player_a : "—";
            const valB = s.player_b !== null && s.player_b !== undefined ? s.player_b : "—";
            const diff = s.diff !== null && s.diff !== undefined ? (s.diff > 0 ? `+${s.diff}` : s.diff) : "—";
            const cls = s.diff > 0 ? "status-high" : s.diff < 0 ? "status-low" : "";
            return `<tr>
                <td>${escapeHtml(s.metric)}</td>
                <td>${escapeHtml(String(valA))}</td>
                <td>${escapeHtml(String(valB))}</td>
                <td><span class="status-pill ${cls}">${diff}</span></td>
            </tr>`;
        }).join("");
    }

    // Render percentile table
    const pctBody = document.getElementById("compare-pct-body");
    if (pctBody) {
        const pcts = data.position_percentile_comparison || [];
        if (pcts.length > 0) {
            if (pctPanel) pctPanel.style.display = "block";
            // Fix column headers
            if (pctColA) pctColA.textContent = nameA;
            if (pctColB) pctColB.textContent = nameB;
            pctBody.innerHTML = pcts.map(p => {
                const valA = p.player_a !== null && p.player_a !== undefined ? p.player_a : "—";
                const valB = p.player_b !== null && p.player_b !== undefined ? p.player_b : "—";
                const diff = p.diff !== null && p.diff !== undefined ? (p.diff > 0 ? `+${p.diff}` : p.diff) : "—";
                const cls = p.diff > 0 ? "status-high" : p.diff < 0 ? "status-low" : "";
                return `<tr>
                    <td>${escapeHtml(p.dimension)}</td>
                    <td>${escapeHtml(String(valA))}</td>
                    <td>${escapeHtml(String(valB))}</td>
                    <td><span class="status-pill ${cls}">${diff}</span></td>
                </tr>`;
            }).join("");
        } else {
            if (pctPanel) pctPanel.style.display = "none";
        }
    }

    // Render radar chart
    const chartEl = document.getElementById("compare-radar-chart");
    if (chartEl && typeof echarts !== "undefined") {
        if (appState.charts.compare) appState.charts.compare.dispose();
        const chart = echarts.init(chartEl);
        appState.charts.compare = chart;

        chart.setOption({
            tooltip: { trigger: "item" },
            legend: { data: [nameA, nameB], bottom: 0 },
            radar: {
                indicator: (data.radar_labels || []).map(l => ({ name: l, max: 100 })),
                shape: "polygon",
            },
            series: [{
                type: "radar",
                data: [
                    {
                        value: data.radar_a || [],
                        name: nameA,
                        areaStyle: { opacity: 0.2 },
                        lineStyle: { width: 2 },
                    },
                    {
                        value: data.radar_b || [],
                        name: nameB,
                        areaStyle: { opacity: 0.2 },
                        lineStyle: { width: 2 },
                    },
                ],
            }],
        });
    }
}

function renderValue() {
    const isMock = valuePlayers.length === 0;
    const data = valuePlayers;
    // Apply price band filter
    const band = appState.valuePriceBand || "all";
    let filtered = data;
    if (band === "low") filtered = data.filter((p) => p.actualValue < 20e6);
    else if (band === "medium") filtered = data.filter((p) => p.actualValue >= 20e6 && p.actualValue <= 80e6);
    else if (band === "high") filtered = data.filter((p) => p.actualValue > 80e6);
    const sorted = [...filtered].sort((a, b) => (
        appState.valueMode === "under" ? b.residual - a.residual : a.residual - b.residual
    ));

    // Show demo data indicator when using mock data
    const valueTitle = document.getElementById("value-panel-title");
    if (valueTitle) {
        let indicator = valueTitle.querySelector(".data-source-indicator");
        if (!indicator) {
            indicator = document.createElement("span");
            indicator.className = "status-pill data-source-indicator";
            valueTitle.appendChild(indicator);
        }
        if (isMock) {
            indicator.textContent = appState.lang === "zh" ? "DEMO" : "DEMO";
            indicator.className = "status-pill status-low data-source-indicator";
        } else {
            indicator.textContent = "";
            indicator.className = "status-pill data-source-indicator";
        }
    }

    // Value fairness metrics from API
    const valueListEl = document.getElementById("value-list");
    const fairnessEl = document.getElementById("value-fairness");
    const metrics = valueSummaryMeta.metrics || {};
    const sampleCount = valueSummaryMeta.sample_count || 0;

    if (fairnessEl) {
        let fhtml = '';
        if (sampleCount > 0 && Object.keys(metrics).length > 0) {
            // Show real fairness data from API
            const z = appState.lang === 'zh';
            fhtml += '<div class="wc-metric-row" style="display:flex;flex-wrap:wrap;gap:0.8rem;padding:0.5rem 0">';
            if (metrics.oof_residual != null || metrics.mae != null) {
                const val = metrics.oof_residual ?? metrics.mae;
                fhtml += `<div class="wc-metric"><span class="metric-value">${safeNum(val, 3)}</span><span>${escapeHtml(t('oof_residual_label'))}</span></div>`;
            }
            if (metrics.league_bias != null) {
                fhtml += `<div class="wc-metric"><span class="metric-value">${safeNum(metrics.league_bias, 3)}</span><span>${escapeHtml(t('league_bias_label'))}</span></div>`;
            }
            if (metrics.position_bias != null) {
                fhtml += `<div class="wc-metric"><span class="metric-value">${safeNum(metrics.position_bias, 3)}</span><span>${escapeHtml(t('position_bias_label'))}</span></div>`;
            }
            if (metrics.age_curve_coeff != null || metrics.age_curve != null) {
                const val = metrics.age_curve_coeff ?? metrics.age_curve;
                fhtml += `<div class="wc-metric"><span class="metric-value">${safeNum(val, 3)}</span><span>${escapeHtml(t('age_curve_label'))}</span></div>`;
            }
            if (sampleCount) {
                fhtml += `<div class="wc-metric"><span class="metric-value">${sampleCount}</span><span>samples</span></div>`;
            }
            fhtml += '</div>';
            // Additional metrics in grid
            const skipKeys = new Set(['oof_residual','mae','league_bias','position_bias','age_curve_coeff','age_curve']);
            const extraMetrics = Object.entries(metrics).filter(([k]) => !skipKeys.has(k) && metrics[k] != null);
            if (extraMetrics.length > 0) {
                fhtml += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(7rem,1fr));gap:0.2rem 0.6rem;font-size:0.78rem;padding:0.3rem 0">';
                for (const [k, v] of extraMetrics) {
                    const display = typeof v === 'number' ? v.toFixed(4) : String(v);
                    fhtml += `<div><span style="color:var(--text-muted)">${escapeHtml(k)}</span><br><strong>${escapeHtml(display)}</strong></div>`;
                }
                fhtml += '</div>';
            }
        } else {
            // No real data: show Transfermarkt notice
            const z = appState.lang === 'zh';
            fhtml += `<div style="font-size:0.82rem;color:var(--text-muted);padding:0.5rem 0">\u25B2 ${escapeHtml(t('transfermarkt_notice'))}</div>`;
            fhtml += `<div style="font-size:0.78rem;color:var(--text-muted);padding:0.2rem 0">${escapeHtml(t('value_no_fairness'))}</div>`;
        }
        fairnessEl.innerHTML = fhtml;
    }

    // Stratification chips (position / league / age band / price band)
    const stratEl = document.getElementById("value-stratification");
    if (stratEl) {
        const sections = [
            { key: "by_position", labelZh: "位置", labelEn: "Position" },
            { key: "by_league", labelZh: "联赛", labelEn: "League" },
            { key: "by_age_band", labelZh: "年龄段", labelEn: "Age band" },
            { key: "by_price_band", labelZh: "身价段", labelEn: "Price band" },
        ];
        const isZh = appState.lang === "zh";
        const html = [];
        for (const section of sections) {
            const rows = valueStratification[section.key];
            if (!Array.isArray(rows) || rows.length === 0) continue;
            const title = isZh ? section.labelZh : section.labelEn;
            html.push(`<div class="strat-block">
                <h4 style="margin:.2rem 0 .4rem; font-weight:600; font-size:.85rem; color:var(--text-muted)">
                    ${escapeHtml(title)}
                </h4>
                <div style="display:flex; flex-wrap:wrap; gap:.35rem;">
                ${rows.slice(0, 8).map((r) => {
                    const residual = Number(r.mean_residual_log);
                    const cls = residual >= 0 ? "status-high" : "status-medium";
                    const sign = residual > 0 ? "+" : "";
                    return `<span class="status-pill ${cls}" title="${escapeHtml(r.group)}: ${sign}${residual.toFixed(2)} (n=${r.count})">
                        ${escapeHtml(r.group)} <small style="opacity:.7">${sign}${residual.toFixed(2)} · ${r.count}</small>
                    </span>`;
                }).join("")}
                </div>
            </div>`);
        }
        // Fairness distribution
        const fairnessDist = valueStratification.fairness_distribution;
        if (fairnessDist && typeof fairnessDist === "object" && Object.keys(fairnessDist).length > 0) {
            const title = isZh ? "高估 / 低估分布" : "Fairness distribution";
            const items = Object.entries(fairnessDist).slice(0, 10).sort((a, b) => b[1] - a[1]);
            html.push(`<div class="strat-block">
                <h4 style="margin:.2rem 0 .4rem; font-weight:600; font-size:.85rem; color:var(--text-muted)">${escapeHtml(title)}</h4>
                <div style="display:flex; flex-wrap:wrap; gap:.35rem;">
                ${items.map(([k, v]) => `<span class="status-pill status-medium">${escapeHtml(k)} <small style="opacity:.7">${v}</small></span>`).join("")}
                </div>
            </div>`);
        }
        if (html.length > 0) {
            stratEl.innerHTML = `<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(14rem, 1fr)); gap:.6rem; padding:.4rem 0;">${html.join("")}</div>`;
        } else {
            stratEl.innerHTML = "";
        }
    }

    valueListEl.innerHTML = sorted.slice(0, 50).map((player) => {
        const valM = (player.actualValue / 1e6).toFixed(1);
        return `
        <div class="rank-item">
            <div>
                <strong>${escapeHtml(player.name)}</strong>
                <span class="rank-meta">${escapeHtml(player.team)} · €${valM}M</span>
            </div>
            <span class="status-pill ${player.residual >= 0 ? "status-high" : "status-medium"}">${player.residual > 0 ? "+" : ""}${player.residual.toFixed(2)}</span>
        </div>
    `}).join("");

    const chart = getChart("value-chart");
    if (!chart) return;
    const isZh = appState.lang === "zh";

    // Force resize before setOption to avoid stale container dimensions
    chart.resize();

    // Build scatter data with player key for click-through
    const scatterData = data.filter(p => p.actualValue > 100000 && p.predictedValue > 100000).map((player) => ({
        value: [
            +(player.actualValue / 1e6).toFixed(1),
            +(player.predictedValue / 1e6).toFixed(1),
        ],
        name: player.name,
        key: player.name + "|" + (player.season || ""),
        team: player.team || "",
        residual: player.residual,
    }));

    chart.setOption({
        animation: false,
        tooltip: {
            trigger: "item",
            formatter(params) {
                if (params.componentType !== "series" || params.seriesIndex !== 0) return "";
                const d = params.data;
                return `<strong>${escapeHtml(d.name)}</strong><br/>${escapeHtml(d.team)}<br/>${isZh ? "实际" : "Actual"}: €${d.value[0]}M<br/>${isZh ? "预测" : "Predicted"}: €${d.value[1]}M<br/>${isZh ? "残差" : "Residual"}: ${d.residual > 0 ? "+" : ""}${d.residual.toFixed(2)}`;
            },
        },
        grid: { left: 54, right: 20, top: 24, bottom: 48 },
        xAxis: {
            type: "log",
            name: isZh ? "实际身价 €M" : "Actual €M",
            nameTextStyle: { color: chartTextColor() },
            axisLabel: { color: chartTextColor(), formatter: (v) => v >= 1 ? v.toFixed(0) : v.toFixed(1) },
            splitLine: { lineStyle: { color: chartGridColor() } },
            min: 0.1,
        },
        yAxis: {
            type: "log",
            name: isZh ? "预测身价 €M" : "Predicted €M",
            nameTextStyle: { color: chartTextColor() },
            axisLabel: { color: chartTextColor(), formatter: (v) => v >= 1 ? v.toFixed(0) : v.toFixed(1) },
            splitLine: { lineStyle: { color: chartGridColor() } },
            min: 0.1,
        },
        series: [{
            type: "scatter",
            symbolSize: 10,
            data: scatterData,
            itemStyle: {
                color(params) {
                    const r = params.data.residual;
                    if (r > 0.5) return "#34d399";
                    if (r > 0.15) return "#6ee7b7";
                    if (r < -0.5) return "#f87171";
                    if (r < -0.15) return "#fca5a5";
                    return "rgba(216,221,231,.86)";
                },
            },
            emphasis: { itemStyle: { shadowBlur: 12, shadowColor: "rgba(0,0,0,.4)" }, symbolSize: 14 },
            label: { show: false },
        }, {
            type: "line",
            data: [[0.1, 0.1], [200, 200]],
            symbol: "none",
            lineStyle: { color: chartGridColor(), type: "dashed" },
        }],
    }, true);

    // Click scatter point -> navigate to player
    chart.off("click");
    chart.on("click", (params) => {
        if (params.componentType !== "series" || params.seriesIndex !== 0) return;
        const d = params.data;
        const match = players.find((p) => p.key === d.key || p.name === d.name);
        if (match) {
            appState.selectedPlayerKey = match.key;
            setView("players");
        } else {
            // Player not in ratings list — search and switch view
            document.getElementById("global-search").value = d.name;
            if (appState.view !== "players") setView("players");
            else renderPlayers();
        }
    });

    chart.resize();

    // ── Age Curve Scatter: x=age, y=rating, color=position ──
    renderAgeCurveScatter(filtered);

    // ── Same-position same-age comparison table ──
    renderSameCohortComparison(filtered);
}

// ── Age Curve Scatter Chart ──────────────────────────────────────
const POS_COLORS = {
    GK: "#f59e0b", CB: "#3b82f6", FB: "#06b6d4", DM: "#8b5cf6",
    CM: "#6366f1", AM: "#ec4899", W: "#10b981", ST: "#ef4444",
};

function renderAgeCurveScatter(data) {
    const chart = getChart("age-curve-chart");
    if (!chart) return;
    const isZh = appState.lang === "zh";
    chart.resize();
    // Group by position for color coding
    const positions = [...new Set(data.map((p) => p.position || p.position_group || ""))].filter(Boolean);
    const series = positions.map((pos) => ({
        name: pos,
        type: "scatter",
        data: data.filter((p) => (p.position || p.position_group || "") === pos).map((p) => ({
            value: [p.age || 25, (p.rating || p.optimized_score || 0)],
            name: p.name || p.player_name || "",
            team: p.team || "",
        })),
        symbolSize: 8,
        itemStyle: { color: POS_COLORS[pos] || "rgba(160,170,200,.7)" },
        emphasis: { itemStyle: { shadowBlur: 8 } },
    }));
    // If API data lacks age field, generate synthetic ages for visualization
    const hasAge = data.some((p) => p.age != null);
    if (!hasAge) {
        // Generate synthetic age data when API doesn't provide age
        for (const s of series) {
            s.data = s.data.map((d) => ({ ...d, value: [20 + Math.random() * 15, d.value[1]] }));
        }
    }
    chart.setOption({
        animation: false,
        title: { text: isZh ? "年龄曲线" : "Age Curve", left: "center", top: 0, textStyle: { color: chartTextColor(), fontSize: 12 } },
        tooltip: {
            trigger: "item",
            formatter(params) {
                const d = params.data;
                return `<strong>${escapeHtml(d.name)}</strong><br/>${escapeHtml(d.team)}<br/>${isZh ? "年龄" : "Age"}: ${d.value[0]}<br/>${isZh ? "评分" : "Rating"}: ${d.value[1].toFixed(1)}`;
            },
        },
        legend: { bottom: 0, textStyle: { color: chartTextColor(), fontSize: 10 }, data: positions },
        grid: { left: 48, right: 20, top: 36, bottom: 48 },
        xAxis: { type: "value", name: isZh ? "年龄" : "Age", nameTextStyle: { color: chartTextColor() }, axisLabel: { color: chartTextColor() }, splitLine: { lineStyle: { color: chartGridColor() } }, min: 17, max: 40 },
        yAxis: { type: "value", name: isZh ? "评分" : "Rating", nameTextStyle: { color: chartTextColor() }, axisLabel: { color: chartTextColor() }, splitLine: { lineStyle: { color: chartGridColor() } }, min: 60, max: 100 },
        series,
    }, true);
    chart.resize();
}

function renderSameCohortComparison(data) {
    const el = document.getElementById("value-same-cohort");
    if (!el) return;
    const z = appState.lang === "zh";
    // Find a selected player from value list or use first entry
    const selected = data[0];
    if (!selected) { el.innerHTML = ""; return; }
    const sPos = selected.position || selected.position_group || "";
    const sAge = selected.age || 25;
    // Find same-position same-age (within 2 years) players
    const cohort = data.filter((p) => {
        const pos = p.position || p.position_group || "";
        const age = p.age || 25;
        return pos === sPos && Math.abs(age - sAge) <= 2;
    }).sort((a, b) => (b.rating || b.optimized_score || 0) - (a.rating || a.optimized_score || 0)).slice(0, 10);
    if (cohort.length <= 1) { el.innerHTML = ""; return; }
    let html = `<p style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin:0.3rem 0">${escapeHtml(t("same_cohort_title"))} (${escapeHtml(sPos)}, ${sAge}+/-2)</p>`;
    html += '<div style="font-size:0.75rem;line-height:1.6">';
    for (const p of cohort) {
        const name = p.name || p.player_name || "";
        const score = Number(p.rating || p.optimized_score || 0).toFixed(1);
        html += `<div style="display:flex;justify-content:space-between;gap:0.4rem"><span>${escapeHtml(name)}</span><span style="color:var(--text-muted)">${escapeHtml(String(score))}</span></div>`;
    }
    html += '</div>';
    el.innerHTML = html;
}

let currentPrediction = null;
let currentPredictionEvidence = {
    fixture_key: null,
    head_to_head: { status: "not_loaded" },
    momentum: { status: "not_loaded" },
};

function predictionFixtureKey(home, away) {
    return `${String(home || "").trim().toLowerCase()}::${String(away || "").trim().toLowerCase()}`;
}

function resetCurrentPredictionEvidence(home, away) {
    currentPredictionEvidence = {
        fixture_key: predictionFixtureKey(home, away),
        head_to_head: { status: "loading" },
        momentum: { status: "loading" },
    };
}

function capturePredictionEvidence(kind, home, away, evidence) {
    if (currentPredictionEvidence.fixture_key !== predictionFixtureKey(home, away)) return;
    currentPredictionEvidence[kind] = evidence;
}

function compactHeadToHeadEvidence(data) {
    if (!data || data.error) return { status: "unavailable" };
    const summary = data.summary || {};
    const coverage = data.data_coverage || {};
    return {
        status: "available",
        summary: {
            total_meetings: Number(summary.total_meetings) || 0,
            home_wins: Number(summary.home_wins) || 0,
            draws: Number(summary.draws) || 0,
            away_wins: Number(summary.away_wins) || 0,
            home_goals_avg: Number(summary.home_goals_avg) || 0,
            away_goals_avg: Number(summary.away_goals_avg) || 0,
            last_meeting_date: summary.last_meeting_date || null,
        },
        recent_form: {
            home: data.home_form_summary || {},
            away: data.away_form_summary || {},
            home_trend: data.home_form_trend || null,
            away_trend: data.away_form_trend || null,
        },
        data_coverage: {
            source: coverage.source || null,
            seasons_covered: Array.isArray(coverage.seasons_covered) ? coverage.seasons_covered : [],
            total_matches_scanned: Number(coverage.total_matches_scanned) || 0,
        },
    };
}

function compactMomentumEvidence(data) {
    if (!data || data.error || !Array.isArray(data.timeline) || data.timeline.length === 0) return { status: "unavailable" };
    const point = data.timeline[0] || {};
    return {
        status: "available",
        current_scoreline: {
            home_goals: Number(data.current_home_goals) || 0,
            away_goals: Number(data.current_away_goals) || 0,
            minute: Number(data.current_minute) || 0,
        },
        remaining_outcome_probabilities: {
            home_win: point.home_win ?? null,
            draw: point.draw ?? null,
            away_win: point.away_win ?? null,
        },
    };
}

function currentPredictionEvidenceFor(match) {
    if (currentPredictionEvidence.fixture_key !== predictionFixtureKey(match.home, match.away)) {
        return {
            fixture_key: predictionFixtureKey(match.home, match.away),
            head_to_head: { status: "not_loaded" },
            momentum: { status: "not_loaded" },
        };
    }
    return currentPredictionEvidence;
}

function selectedPredictionCalibration() {
    const direct = (currentPrediction && currentPrediction.calibration) || {};
    const detail = predictionCalibration.dixon_coles?.status === "ok"
        ? predictionCalibration.dixon_coles
        : (predictionCalibration.poisson || {});
    const merged = {
        brier: direct.brier ?? detail.brier_1x2,
        rps: direct.rps ?? detail.rps_1x2,
        log_loss: direct.log_loss ?? detail.log_loss_exact,
    };
    return Object.values(merged).some((value) => value != null) ? merged : null;
}

function selectedMatch() {
    if (currentPrediction && !currentPrediction.error) {
        return {
            home: currentPrediction.home_team || appState.home,
            away: currentPrediction.away_team || appState.away,
            hw: currentPrediction.home_win || 0.34,
            draw: currentPrediction.draw || 0.28,
            aw: currentPrediction.away_win || 0.38,
            xh: currentPrediction.home_lambda || 1.32,
            xa: currentPrediction.away_lambda || 1.42,
            score_matrix: currentPrediction.score_matrix || null,
            calibration: selectedPredictionCalibration(),
            model_version: currentPrediction.model_version || "",
            model_type: currentPrediction.model_type || "poisson",
            confidence_intervals: currentPrediction.confidence_intervals || null,
            form_config: currentPrediction.form_config || null,
            weights: currentPrediction.weights || null,
            model_predictions: currentPrediction.model_predictions || null,
        };
    }
    return { home: appState.home, away: appState.away, hw: 0.34, draw: 0.28, aw: 0.38, xh: 1.32, xa: 1.42, score_matrix: null, calibration: null, model_version: "", model_type: "poisson", confidence_intervals: null, form_config: null, weights: null, model_predictions: null };
}

function renderMatchSelectors() {
    const teams = getTeams();
    const home = document.getElementById("home-team");
    const away = document.getElementById("away-team");
    home.innerHTML = teams.map((team) => `<option value="${escapeAttr(team)}">${escapeHtml(team)}</option>`).join("");
    away.innerHTML = teams.map((team) => `<option value="${escapeAttr(team)}">${escapeHtml(team)}</option>`).join("");
    home.value = appState.home;
    away.value = appState.away;
}

let _matchRenderId = 0;
function buildCurrentPredictionExport() {
    const match = selectedMatch();
    const evidence = currentPredictionEvidenceFor(match);
    return {
        schema: "scoutfootball.match-prediction-export",
        version: "1.1.0",
        exported_at: new Date().toISOString(),
        storage_scope: "browser-local-download",
        fixture: { home_team: match.home, away_team: match.away },
        prediction: { home_win: match.hw, draw: match.draw, away_win: match.aw, home_expected_goals: match.xh, away_expected_goals: match.xa, model_type: match.model_type, model_version: match.model_version, confidence_intervals: match.confidence_intervals || null },
        coverage: predictionMeta,
        contextual_evidence: {
            non_additive_to_prediction: true,
            head_to_head: evidence.head_to_head,
            momentum: evidence.momentum,
        },
        limitations: ["Prediction is model context, not a guarantee, betting instruction, or live match intelligence.", "Coverage and calibration fields reflect the loaded local/API snapshot.", "Head-to-head, recent form, and momentum are separately loaded context; they do not alter or add to the exported pre-match probabilities.", "An unavailable context section means the report makes no inference from missing data."],
    };
}
function _downloadPredictionExport(content, filename, type) {
    const blob = new Blob([content], { type }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}
function exportCurrentPredictionJSON() {
    const payload = buildCurrentPredictionExport();
    _downloadPredictionExport(JSON.stringify(payload, null, 2), "scoutfootball-match-prediction.json", "application/json;charset=utf-8");
}
function exportCurrentPredictionCSV() {
    const payload = buildCurrentPredictionExport(); const p = payload.prediction;
    const h2h = payload.contextual_evidence.head_to_head || {};
    const h2hSummary = h2h.summary || {};
    const homeTrend = h2h.recent_form?.home_trend || {};
    const awayTrend = h2h.recent_form?.away_trend || {};
    const momentum = payload.contextual_evidence.momentum || {};
    const scoreline = momentum.current_scoreline || {};
    const remaining = momentum.remaining_outcome_probabilities || {};
    const lines = [["# ScoutFootball Match Prediction"], ["home_team", payload.fixture.home_team], ["away_team", payload.fixture.away_team], ["model_type", p.model_type || ""], ["model_version", p.model_version || ""], ["home_win", p.home_win ?? ""], ["draw", p.draw ?? ""], ["away_win", p.away_win ?? ""], ["home_expected_goals", p.home_expected_goals ?? ""], ["away_expected_goals", p.away_expected_goals ?? ""], ["storage_scope", payload.storage_scope], [], ["# Contextual evidence (separate; non-additive to prediction)"], ["head_to_head_status", h2h.status || "not_loaded"], ["h2h_total_meetings", h2hSummary.total_meetings ?? ""], ["h2h_home_wins", h2hSummary.home_wins ?? ""], ["h2h_draws", h2hSummary.draws ?? ""], ["h2h_away_wins", h2hSummary.away_wins ?? ""], ["home_form_trend", homeTrend.trend_label || ""], ["away_form_trend", awayTrend.trend_label || ""], ["momentum_status", momentum.status || "not_loaded"], ["momentum_minute", scoreline.minute ?? ""], ["momentum_home_goals", scoreline.home_goals ?? ""], ["momentum_away_goals", scoreline.away_goals ?? ""], ["remaining_home_win", remaining.home_win ?? ""], ["remaining_draw", remaining.draw ?? ""], ["remaining_away_win", remaining.away_win ?? ""], [], ["# Limitations"], ...payload.limitations.map((x) => [x])];
    _downloadPredictionExport(`\uFEFF${lines.map((row) => row.map(csvCell).join(",")).join("\n")}`, "scoutfootball-match-prediction.csv", "text/csv;charset=utf-8");
}
async function renderMatches() {
    const myId = ++_matchRenderId;
    resetCurrentPredictionEvidence(appState.home, appState.away);
    // Fetch prediction from API
    currentPrediction = await fetchPrediction(appState.home, appState.away);
    if (myId !== _matchRenderId) return; // stale
    const match = selectedMatch();
    const predictionCoverage = predictionMeta.status === "ok" && predictionMeta.num_teams
        ? `${predictionMeta.num_teams} teams`
        : "artifact pending";
    document.getElementById("match-title").textContent = `${match.home} vs ${match.away}`;
    const ci = match.confidence_intervals;
    const ciLabels = ci ? {
        home: ci.home_win ? `[${(ci.home_win[0] * 100).toFixed(1)}%, ${(ci.home_win[1] * 100).toFixed(1)}%]` : "",
        draw: ci.draw ? `[${(ci.draw[0] * 100).toFixed(1)}%, ${(ci.draw[1] * 100).toFixed(1)}%]` : "",
        away: ci.away_win ? `[${(ci.away_win[0] * 100).toFixed(1)}%, ${(ci.away_win[1] * 100).toFixed(1)}%]` : "",
    } : null;
    const probabilityRows = [
        [t("home"), match.hw, ciLabels ? ciLabels.home : ""],
        [t("draw"), match.draw, ciLabels ? ciLabels.draw : ""],
        [t("away"), match.aw, ciLabels ? ciLabels.away : ""],
    ];
    document.getElementById("match-probabilities").innerHTML = probabilityRows.map(([label, value, ciText]) => `
        <div class="probability-row">
            <span class="probability-label">${escapeHtml(label)}</span>
            <div class="probability-track"><div class="probability-fill" style="width:${sanitizeCssPercent(value * 100)}%"></div></div>
            <strong>${sanitizeCssPercent(value * 100)}%</strong>
            ${ciText ? `<span style="font-size:0.65rem;color:var(--text-muted);min-width:90px;text-align:right">${escapeHtml(ciText)}</span>` : ""}
        </div>
    `).join("");
    document.getElementById("match-detail").innerHTML = `
        <div><span>${escapeHtml(t("expected_goals"))}</span><strong>${match.xh.toFixed(2)} / ${match.xa.toFixed(2)}</strong></div>
        <div><span>${escapeHtml(t("coverage"))}</span><strong>${escapeHtml(predictionCoverage)}</strong></div>
        <div><span>model</span><strong>${escapeHtml(match.model_type || predictionMeta.model_type || "Poisson")}</strong></div>
        <div><span>train_rows</span><strong>${escapeHtml(predictionMeta.train_rows || "pending")}</strong></div>
    `;
    renderScoreMatrix(match);
    renderOutcomeBar(match);

    // Calibration section below score matrix
    const calibEl = document.getElementById('match-calibration');
    if (calibEl) {
        const dcModel = predictionMeta.dixon_coles || {};
        const poissonModel = predictionMeta.poisson || {};
        const rho = dcModel.rho ?? null;
        const homeAdv = dcModel.home_advantage ?? null;
        const coverage = predictionMeta.coverage ?? poissonModel.coverage ?? null;
        const brier = poissonModel.brier_score ?? dcModel.brier_score ?? null;
        const rps = poissonModel.rps ?? dcModel.rps ?? null;
        const modelVer = poissonModel.model_version || dcModel.model_version || '';
        const modelType = predictionMeta.model_type || poissonModel.model_type || 'Poisson';
        const lowScore = poissonModel.low_score_analysis || dcModel.low_score_analysis || {};
        const z = appState.lang === 'zh';

        let calibHtml = '';

        // Model info
        calibHtml += `<div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.4rem">`;
        calibHtml += `\u25C6 ${z ? '模型' : 'Model'}: ${escapeHtml(modelType)}`;
        if (modelVer) calibHtml += ` v${escapeHtml(modelVer)}`;
        calibHtml += `</div>`;

        // Dixon-Coles rho
        if (rho != null) {
            calibHtml += `<div style="font-size:0.75rem;margin-bottom:0.2rem">`;
            calibHtml += `<span style="color:var(--text-muted)">Dixon-Coles \u03C1:</span> <strong>${escapeHtml(String(Number(rho).toFixed(4)))}</strong>`;
            calibHtml += `</div>`;
        }

        // Home advantage
        if (homeAdv != null) {
            calibHtml += `<div style="font-size:0.75rem;margin-bottom:0.2rem">`;
            calibHtml += `<span style="color:var(--text-muted)">${z ? '主场优势' : 'Home advantage'}:</span> <strong>${escapeHtml(String(Number(homeAdv).toFixed(4)))}</strong>`;
            calibHtml += `</div>`;
        }

        // Coverage gate warning
        if (coverage != null && Number(coverage) < 0.90) {
            calibHtml += `<div style="font-size:0.78rem;color:#ff6b6b;margin:0.3rem 0;padding:0.25rem 0.4rem;background:rgba(255,107,107,.1);border-radius:4px">`;
            calibHtml += `\u25B2 ${z ? '覆盖率低于90%，预测可能不可靠' : 'Coverage below 90% \u2014 predictions may be unreliable'} (${(Number(coverage) * 100).toFixed(1)}%)`;
            calibHtml += `</div>`;
        }

        // Low-score analysis
        const lowScoreKeys = ['0-0', '1-0', '0-1', '1-1'];
        const hasLowScore = lowScoreKeys.some((k) => lowScore[k] != null || lowScore[k.replace('-', '_')] != null);
        if (hasLowScore) {
            calibHtml += `<p style="margin:0.5rem 0 0.2rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? '低比分分析' : 'Low-score analysis'}</p>`;
            calibHtml += `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.2rem 0.6rem;font-size:0.75rem">`;
            calibHtml += `<div style="color:var(--text-muted)">${z ? '比分' : 'Score'}</div><div style="color:var(--text-muted)">${z ? '实际' : 'Actual'}</div><div style="color:var(--text-muted)">${z ? '预测' : 'Predicted'}</div>`;
            for (const key of lowScoreKeys) {
                const entry = lowScore[key] || lowScore[key.replace('-', '_')] || {};
                const actual = entry.actual ?? entry.act ?? '–';
                const predicted = entry.predicted ?? entry.pred ?? '–';
                calibHtml += `<div>${escapeHtml(key)}</div>`;
                calibHtml += `<div>${typeof actual === 'number' ? (actual * 100).toFixed(1) + '%' : escapeHtml(String(actual))}</div>`;
                calibHtml += `<div>${typeof predicted === 'number' ? (predicted * 100).toFixed(1) + '%' : escapeHtml(String(predicted))}</div>`;
            }
            calibHtml += `</div>`;
        }

        // Brier / RPS
        if (brier != null || rps != null) {
            calibHtml += `<div style="margin-top:0.4rem;font-size:0.75rem">`;
            if (brier != null) {
                calibHtml += `<span style="color:var(--text-muted)">Brier:</span> <strong>${escapeHtml(String(Number(brier).toFixed(4)))}</strong> `;
            }
            if (rps != null) {
                calibHtml += `<span style="color:var(--text-muted)">RPS:</span> <strong>${escapeHtml(String(Number(rps).toFixed(4)))}</strong>`;
            }
            calibHtml += `</div>`;
        }

        // Log-loss
        const logLoss = predictionMeta.log_loss ?? predictionMeta.logloss ?? null;
        if (logLoss != null) {
            calibHtml += `<div style="margin-top:0.3rem;font-size:0.75rem">`;
            calibHtml += `<span style="color:var(--text-muted)">${z ? '对数损失' : 'Log loss'}:</span> <strong>${escapeHtml(String(Number(logLoss).toFixed(4)))}</strong>`;
            calibHtml += `</div>`;
        }

        // Model comparison section (Poisson vs Dixon-Coles side by side)
        const modelCmp = match.model_comparison ?? null;
        const poissonPred = modelCmp?.poisson ?? null;
        const dcPred = modelCmp?.dixon_coles ?? null;
        if (poissonPred && dcPred) {
            calibHtml += `<p style="margin:0.5rem 0 0.2rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? '模型对比' : 'Model comparison'}</p>`;
            calibHtml += `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.2rem 0.6rem;font-size:0.75rem">`;
            calibHtml += `<div style="color:var(--text-muted)">${z ? '结果' : 'Outcome'}</div>`;
            calibHtml += `<div style="color:var(--text-muted)">Poisson</div>`;
            calibHtml += `<div style="color:var(--text-muted)">Dixon-Coles</div>`;
            const outcomes = ['home', 'draw', 'away'];
            const labels = [z ? '主胜' : 'Home', z ? '平局' : 'Draw', z ? '客胜' : 'Away'];
            for (let i = 0; i < outcomes.length; i++) {
                const pVal = poissonPred[outcomes[i]] ?? null;
                const dcVal = dcPred[outcomes[i]] ?? null;
                calibHtml += `<div>${escapeHtml(labels[i])}</div>`;
                calibHtml += `<div>${pVal != null ? (Number(pVal) * 100).toFixed(1) + '%' : '–'}</div>`;
                calibHtml += `<div>${dcVal != null ? (Number(dcVal) * 100).toFixed(1) + '%' : '–'}</div>`;
            }
            calibHtml += `</div>`;
        }

        // API-level calibration from /predictions/{home}/{away}
        if (match.calibration) {
            const apiCal = match.calibration;
            calibHtml += `<p style="margin:0.5rem 0 0.2rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? '预测校准指标' : 'Prediction calibration'}</p>`;
            calibHtml += `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.2rem 0.6rem;font-size:0.75rem">`;
            calibHtml += `<div style="color:var(--text-muted)">${z ? '指标' : 'Metric'}</div>`;
            calibHtml += `<div style="color:var(--text-muted)">${z ? '值' : 'Value'}</div>`;
            calibHtml += `<div style="color:var(--text-muted)">${z ? '说明' : 'Note'}</div>`;
            const calibMetrics = [
                { key: "brier", label: "Brier", note: z ? "越低越好" : "Lower is better" },
                { key: "rps", label: "RPS", note: z ? "越低越好" : "Lower is better" },
                { key: "log_loss", label: z ? "对数损失" : "Log loss", note: z ? "越低越好" : "Lower is better" },
            ];
            for (const m of calibMetrics) {
                const val = apiCal[m.key];
                calibHtml += `<div>${escapeHtml(m.label)}</div>`;
                calibHtml += `<div>${val != null ? escapeHtml(String(Number(val).toFixed(4))) : '–'}</div>`;
                calibHtml += `<div style="color:var(--text-muted)">${escapeHtml(m.note)}</div>`;
            }
            calibHtml += `</div>`;
        }

        // Model version from API
        if (match.model_version) {
            calibHtml += `<div style="margin-top:0.3rem;font-size:0.72rem;color:var(--text-muted)">`;
            calibHtml += `${z ? '模型版本' : 'Model version'}: <strong>${escapeHtml(match.model_version)}</strong>`;
            calibHtml += `</div>`;
        }

        // Bootstrap confidence intervals
        if (match.confidence_intervals) {
            const ciData = match.confidence_intervals;
            const ciLevel = ciData.confidence_level ? `${(ciData.confidence_level * 100).toFixed(0)}%` : '90%';
            const ciN = ciData.n_bootstrap || '?';
            const ciFailed = ciData.failed_iterations || 0;
            calibHtml += `<div style="margin-top:0.6rem;padding:0.4rem 0.5rem;background:rgba(100,180,255,0.06);border-radius:6px">`;
            calibHtml += `<p style="margin:0 0 0.3rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">`;
            calibHtml += `${z ? '置信区间' : 'Confidence Intervals'} (${escapeHtml(ciLevel)}, n=${escapeHtml(String(ciN))})`;
            if (ciFailed > 0) calibHtml += ` <span style="opacity:0.6">(${ciFailed} ${z ? '失败' : 'failed'})</span>`;
            calibHtml += `</p>`;
            const ciRows = [
                [z ? '主胜' : 'Home Win', ciData.home_win],
                [z ? '平局' : 'Draw', ciData.draw],
                [z ? '客胜' : 'Away Win', ciData.away_win],
                [z ? '主队λ' : 'Home λ', ciData.home_lambda],
                [z ? '客队λ' : 'Away λ', ciData.away_lambda],
            ];
            calibHtml += `<div style="display:grid;grid-template-columns:1fr auto;gap:0.15rem 0.5rem;font-size:0.72rem">`;
            for (const [label, range] of ciRows) {
                if (range && Array.isArray(range)) {
                    const fmt = (v) => Number(v).toFixed(3);
                    calibHtml += `<div style="color:var(--text-muted)">${escapeHtml(label)}</div>`;
                    calibHtml += `<div><strong>[${fmt(range[0])}, ${fmt(range[1])}]</strong></div>`;
                }
            }
            calibHtml += `</div>`;
            calibHtml += `</div>`;
        }

        // Form-weighted model config
        if (match.form_config) {
            const fc = match.form_config;
            calibHtml += `<div style="margin-top:0.3rem;font-size:0.72rem;color:var(--text-muted)">`;
            calibHtml += `${z ? '状态权重' : 'Form weighting'}: `;
            calibHtml += `${z ? '回看' : 'lookback'}=<strong>${escapeHtml(String(fc.lookback))}</strong>, `;
            calibHtml += `${z ? '因子' : 'factor'}=<strong>${escapeHtml(String(fc.form_factor))}</strong>`;
            if (fc.decay != null) calibHtml += `, decay=<strong>${escapeHtml(String(fc.decay))}</strong>`;
            calibHtml += `</div>`;
        }

        // Ensemble model breakdown
        if (match.model_type === "ensemble" && match.weights && match.model_predictions) {
            const weights = match.weights;
            const mp = match.model_predictions;
            calibHtml += `<div style="margin-top:0.6rem;padding:0.4rem 0.5rem;background:rgba(100,180,255,0.06);border-radius:6px">`;
            calibHtml += `<p style="margin:0 0 0.3rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">`;
            calibHtml += `${z ? '集成模型分解' : 'Ensemble Breakdown'}</p>`;
            const modelNames = Object.keys(weights);
            if (modelNames.length > 0) {
                calibHtml += `<table class="data-table" style="width:100%;font-size:0.7rem">`;
                calibHtml += `<thead><tr><th>${z ? '模型' : 'Model'}</th><th>${z ? '权重' : 'Weight'}</th><th>${z ? '主胜' : 'Home'}</th><th>${z ? '平' : 'Draw'}</th><th>${z ? '客胜' : 'Away'}</th><th>${z ? '主λ' : 'Hλ'}</th><th>${z ? '客λ' : 'Aλ'}</th></tr></thead><tbody>`;
                for (const name of modelNames) {
                    const w = weights[name];
                    const p = mp[name] || {};
                    calibHtml += `<tr><td>${escapeHtml(name)}</td>`;
                    calibHtml += `<td><strong>${(Number(w) * 100).toFixed(1)}%</strong></td>`;
                    calibHtml += `<td>${fmtMetric(p.home_win)}</td>`;
                    calibHtml += `<td>${fmtMetric(p.draw)}</td>`;
                    calibHtml += `<td>${fmtMetric(p.away_win)}</td>`;
                    calibHtml += `<td>${fmtMetric(p.home_lambda)}</td>`;
                    calibHtml += `<td>${fmtMetric(p.away_lambda)}</td></tr>`;
                }
                calibHtml += `</tbody></table>`;
            }
            calibHtml += `</div>`;
        }

        calibEl.innerHTML = calibHtml;
    }

    // Head-to-head section (loads independently — failures don't affect prediction display)
    renderHeadToHead(appState.home, appState.away).catch((e) => console.warn("H2H render failed:", e));
    renderMomentum(appState.home, appState.away).catch((e) => console.warn("Momentum render failed:", e));

    // Show attribution panel (on-demand via button) and reset its body for the new match
    const attributionPanel = document.getElementById("match-attribution-panel");
    const attributionBody = document.getElementById("match-attribution-body");
    if (attributionPanel && attributionBody) {
        attributionPanel.style.display = "block";
        attributionBody.innerHTML = `<p style="color:var(--text-muted);font-size:0.78rem">${escapeHtml(t("prediction_attribution_instructions"))}</p>`;
    }

    // Reset diagnostics panel for the new match (hidden until user clicks the button)
    const diagnosticsPanel = document.getElementById("match-diagnostics-panel");
    const diagnosticsBody = document.getElementById("match-diagnostics-body");
    if (diagnosticsPanel && diagnosticsBody) {
        diagnosticsPanel.style.display = "none";
        diagnosticsBody.innerHTML = "";
    }

    // Reset ensemble attribution panel for the new match (hidden until user clicks the button)
    const ensAttrPanel = document.getElementById("match-ensemble-attribution-panel");
    const ensAttrBody = document.getElementById("match-ensemble-attribution-body");
    if (ensAttrPanel && ensAttrBody) {
        ensAttrPanel.style.display = "none";
        ensAttrBody.innerHTML = "";
    }

    // Show value bet panel for the new match (odds inputs visible, result cleared)
    const valueBetPanel = document.getElementById("match-value-bet-panel");
    const valueBetResult = document.getElementById("match-value-bet-result");
    if (valueBetPanel) {
        valueBetPanel.style.display = "block";
    }
    if (valueBetResult) {
        valueBetResult.innerHTML = "";
    }

    // Show H2H bias correction panel (on-demand via button) and reset its body
    const h2hBiasPanel = document.getElementById("match-h2h-bias-panel");
    const h2hBiasBody = document.getElementById("match-h2h-bias-body");
    if (h2hBiasPanel) {
        h2hBiasPanel.style.display = "block";
    }
    if (h2hBiasBody) {
        h2hBiasBody.innerHTML = "";
    }
}

function poisson(lambda, k) {
    let factorial = 1;
    for (let i = 2; i <= k; i += 1) factorial *= i;
    return Math.exp(-lambda) * (lambda ** k) / factorial;
}

function renderScoreMatrixInto(chartId, match) {
    const chart = getChart(chartId);
    if (!chart) return;
    const data = [];

    // Use API score_matrix if available, otherwise compute client-side
    if (match.score_matrix && Array.isArray(match.score_matrix)) {
        for (let home = 0; home <= 5; home += 1) {
            for (let away = 0; away <= 5; away += 1) {
                const val = (match.score_matrix[home] && match.score_matrix[home][away] != null)
                    ? match.score_matrix[home][away]
                    : +(poisson(match.xh, home) * poisson(match.xa, away)).toFixed(3);
                data.push([away, home, +val.toFixed(4)]);
            }
        }
    } else {
        for (let home = 0; home <= 5; home += 1) {
            for (let away = 0; away <= 5; away += 1) {
                data.push([away, home, +(poisson(match.xh, home) * poisson(match.xa, away)).toFixed(3)]);
            }
        }
    }
    chart.setOption({
        tooltip: { position: "top" },
        grid: { left: 48, right: 24, top: 26, bottom: 38 },
        xAxis: {
            type: "category",
            data: ["0", "1", "2", "3", "4", "5"],
            name: match.away,
            nameTextStyle: { color: chartTextColor() },
            axisLabel: { color: chartTextColor() },
        },
        yAxis: {
            type: "category",
            data: ["0", "1", "2", "3", "4", "5"],
            name: match.home,
            nameTextStyle: { color: chartTextColor() },
            axisLabel: { color: chartTextColor() },
        },
        visualMap: {
            min: 0,
            max: 0.18,
            show: false,
            inRange: { color: ["rgba(255,255,255,.05)", "rgba(124,168,255,.82)"] },
        },
        series: [{
            type: "heatmap",
            data,
            label: { show: true, color: chartTextColor(), formatter: ({ value }) => value[2].toFixed(2) },
        }],
    });
    chart.resize();
}

function renderScoreMatrix(match) {
    renderScoreMatrixInto("score-chart", match);
}

function renderOutcomeBarInto(chartId, match) {
    const chart = getChart(chartId);
    if (!chart) return;
    const z = appState.lang === "zh";
    const labels = [z ? "主胜" : "Home", z ? "平局" : "Draw", z ? "客胜" : "Away"];
    const values = [match.hw, match.draw, match.aw];
    const colors = ["#4a90d9", "#8e8e93", "#ff9f43"];
    chart.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: 60, right: 20, top: 20, bottom: 36 },
        xAxis: {
            type: "category",
            data: labels,
            axisLabel: { color: chartTextColor(), fontSize: 12 },
        },
        yAxis: {
            type: "value",
            max: 1,
            axisLabel: { color: chartTextColor(), formatter: (v) => (v * 100).toFixed(0) + "%" },
            splitLine: { lineStyle: { color: chartGridColor() } },
        },
        series: [{
            type: "bar",
            data: values.map((v, i) => ({
                value: v,
                itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] },
            })),
            barWidth: "40%",
            label: {
                show: true,
                position: "top",
                color: chartTextColor(),
                formatter: ({ value }) => (value * 100).toFixed(1) + "%",
            },
        }],
    });
    requestAnimationFrame(() => {
        chart.resize();
        requestAnimationFrame(() => chart.resize());
    });
}

function renderOutcomeBar(match) {
    renderOutcomeBarInto("outcome-bar-chart", match);
}

let reviewQueue = [];

async function fetchReviewQueue() {
    try {
        const data = await fetchJson("/review-queue");
        return (data.players || []).map((p) => ({
            player_id: p.player_id || "",
            name: p.player_name || p.player || "",
            player_name: p.player_name || p.player || "",
            team: p.team || "",
            league: p.league || "",
            season: p.season || "",
            position: p.position_group || "",
            position_group: p.position_group || "",
            confidence: (p.confidence_level || "LOW").toUpperCase(),
            confidence_level: (p.confidence_level || "LOW").toUpperCase(),
            score: +(p.optimized_score || 0).toFixed(1),
            optimized_score: +(p.optimized_score || 0).toFixed(1),
            minutes: Math.round(p.minutes || 0),
            reason_code: p.reason_code || "",
            review_status: p.review_status || "pending",
            reviewer_note: p.reviewer_note || "",
            as_of_date: p.as_of_date || "",
            rating_snapshot_id: p.rating_snapshot_id || "",
        }));
    } catch (err) {
        console.warn("Failed to fetch review queue:", err);
        dataLoadErrors.add("review-queue");
        return [];
    }
}

async function fetchWatchlist() {
    try {
        const data = await fetchJson("/watchlist");
        return data.players || [];
    } catch (err) {
        console.warn("Failed to fetch watchlist:", err);
        dataLoadErrors.add("watchlist");
        return [];
    }
}

async function fetchShortlist() {
    try {
        const data = await fetchJson("/shortlist");
        return data.players || [];
    } catch (err) {
        console.warn("Failed to fetch shortlist:", err);
        dataLoadErrors.add("shortlist");
        return [];
    }
}

async function fetchScoutingWorkspaceCapabilities() {
    try {
        const data = await fetchJson("/scouting-workspaces/capabilities");
        return data && typeof data === "object"
            ? data
            : { enabled: false, configured: false, local_only: true };
    } catch (err) {
        console.warn("Scouting workspace persistence is unavailable:", err);
        return { enabled: false, configured: false, local_only: true };
    }
}

function renderScouting() {
    const queue = reviewQueue.length > 0 ? reviewQueue : [];
    const filteredQueue = filterReviewQueue(queue);
    const sortedQueue = sortReviewQueue(filteredQueue, scoutSortMode);
    const combinedWatchlist = mergeScoutingRows(watchlistData, getPlayerWatchlist());
    const combinedShortlist = mergeScoutingRows(shortlistData, getPlayerShortlist());

    const reviewCount = queue.filter((player) => {
        const status = getQueueStatus(player);
        return status === "pending" || status === "reviewing";
    }).length;
    const reviewCountEl = document.getElementById("scout-review-count");
    const watchCountEl = document.getElementById("scout-watch-count");
    const shortCountEl = document.getElementById("scout-short-count");
    if (reviewCountEl) reviewCountEl.textContent = String(reviewCount);
    if (watchCountEl) watchCountEl.textContent = String(combinedWatchlist.length);
    if (shortCountEl) shortCountEl.textContent = String(combinedShortlist.length);

    // Sort bar
    const sortModes = [
        { key: "priority", label: t("sort_priority"), symbol: "\u25C6" },
        { key: "date", label: t("sort_date"), symbol: "\u25BC" },
        { key: "name", label: t("sort_name"), symbol: "\u25CE" },
    ];
    let sortBarHtml = '<div class="scout-sort-bar">';
    for (const m of sortModes) {
        const active = scoutSortMode === m.key ? " active" : "";
        sortBarHtml += `<button class="scout-sort-btn${active}" data-scout-sort="${m.key}" type="button">${m.symbol} ${escapeHtml(m.label)}</button>`;
    }
    sortBarHtml += "</div>";

    // Review queue (paginated)
    const totalPages = Math.max(1, Math.ceil(sortedQueue.length / SCOUT_PAGE_SIZE));
    if (scoutCurrentPage > totalPages) scoutCurrentPage = totalPages;
    const pageStart = (scoutCurrentPage - 1) * SCOUT_PAGE_SIZE;
    const pageEnd = Math.min(pageStart + SCOUT_PAGE_SIZE, sortedQueue.length);
    const pageItems = sortedQueue.slice(pageStart, pageEnd);

    let reviewHtml = sortBarHtml;
    if (sortedQueue.length > 0) {
        for (const p of pageItems) {
            const pKey = p.player_name || p.name || "";
            const statusKey = queueStatusKey(p);
            const status = getQueueStatus(p);
            const statusClass = "status-" + status;
            const icon = STATUS_ICONS[status] || "\u25CB";
            const conf = (p.confidence_level || p.confidence || "LOW").toUpperCase();
            const meta = [p.team, p.position_group || p.position, `${p.minutes || 0}min`, p.reason_code, p.as_of_date]
                .filter(Boolean).join(" \u00B7 ");
            reviewHtml += `
                <div class="rank-item" data-review-state="${escapeAttr(status)}">
                    <div>
                        <strong>${escapeHtml(pKey)}</strong>
                        <span class="rank-meta">${escapeHtml(meta)}</span>
                    </div>
                    <div style="display:flex;gap:6px;align-items:center">
                        <button class="status-pill status-clickable ${statusClass}" data-queue-status="${escapeAttr(statusKey)}" title="${escapeHtml(t("status_" + status))}" type="button">${icon} ${escapeHtml(t("status_" + status))}</button>
                        <span class="status-pill ${confidenceClass(conf)}">${safeNum(p.optimized_score || p.score || 0)} · ${escapeHtml(conf)}</span>
                    </div>
                </div>`;
        }
        // Pagination controls
        if (totalPages > 1) {
            reviewHtml += `<div class="scout-pagination">
                <span class="rank-meta">${pageStart + 1}-${pageEnd} / ${sortedQueue.length}</span>
                <div class="scout-page-btns">
                    <button class="text-button" id="scout-prev-page" type="button" ${scoutCurrentPage <= 1 ? 'disabled style="opacity:0.4"' : ''}>&#9664;</button>
                    <span class="rank-meta">${scoutCurrentPage} / ${totalPages}</span>
                    <button class="text-button" id="scout-next-page" type="button" ${scoutCurrentPage >= totalPages ? 'disabled style="opacity:0.4"' : ''}>&#9654;</button>
                </div>
            </div>`;
        }
    } else {
        const loadFailed = dataLoadErrors.has("review-queue");
        const emptyMsg = loadFailed
            ? (appState.lang === "zh" ? "数据加载失败（API 和静态缓存均不可用）" : "Data load failed (both API and static cache unavailable)")
            : (appState.lang === "zh" ? "当前筛选没有复核对象" : "No review items match the current filters");
        reviewHtml += `<div style="color:var(--text-muted);text-align:center;padding:1rem">${escapeHtml(emptyMsg)}</div>`;
    }
    document.getElementById("review-list").innerHTML = reviewHtml;

    // Watchlist with diff badge
    computeWatchlistDiff(combinedWatchlist);
    const wlHeader = document.querySelector("#view-scouting .panel-head h3[data-i18n='watchlist']");
    if (wlHeader) {
        const existingBadge = wlHeader.querySelector(".scout-badge");
        if (existingBadge) existingBadge.remove();
        if (watchlistDiffCount > 0) {
            const badge = document.createElement("span");
            badge.className = "scout-badge";
            badge.textContent = `${watchlistDiffCount} ${t("scout_new_badge")}`;
            wlHeader.appendChild(badge);
        }
    }

    document.getElementById("watchlist").innerHTML = combinedWatchlist.length > 0 ? combinedWatchlist.map((player) => {
        const pName = player.player_name || player.name || "";
        const conf = (player.confidence_level || player.confidence || "LOW").toUpperCase();
        const wlNote = watchlistNotes[pName] || "";
        return `
        <div class="watch-card">
            <div>
                <strong>${escapeHtml(pName)}</strong>
                <span class="rank-meta">${escapeHtml(player.team)} \u00B7 ${escapeHtml(player.position_group || player.position || "")} \u00B7 ${escapeHtml(player.reason_code || "")}</span>
            </div>
            <span class="status-pill ${confidenceClass(conf)}">${safeNum(player.optimized_score || player.rating || 0)}</span>
            <div class="watch-card-extra">
                ${wlNote ? `<div class="scout-note-display">\u25B8 ${escapeHtml(wlNote)}</div>` : ""}
                <textarea class="scout-note-textarea" data-wl-note-player="${escapeAttr(pName)}" rows="2" placeholder="${escapeAttr(t("scout_note_placeholder"))}">${escapeHtml(wlNote)}</textarea>
            </div>
        </div>`;
    }).join("") : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No players in watchlist</div>';

    // Shortlist dossiers: local-only decision context with a stable player key.
    document.getElementById("shortlist-count").textContent = String(combinedShortlist.length);
    document.getElementById("shortlist").innerHTML = combinedShortlist.length > 0 ? combinedShortlist.map((player) => {
        const pName = player.player_name || player.name || "";
        const conf = (player.confidence_level || player.confidence || "HIGH").toUpperCase();
        const dossierKey = scoutingPlayerKey(player);
        const dossier = getShortlistDossier(player);
        const note = dossier.rationale;
        const zh = appState.lang === "zh";
        return `
        <div class="watch-card">
            <div>
                <strong>${escapeHtml(pName)}</strong>
                <span class="rank-meta">${escapeHtml(player.team)} \u00B7 ${escapeHtml(player.position_group || player.position || "")} \u00B7 ${escapeHtml(player.reason_code || "")}</span>
            </div>
            <span class="status-pill ${confidenceClass(conf)}">${safeNum(player.optimized_score || player.rating || 0)}</span>
            <div class="watch-card-extra">
                <div class="scout-dossier-grid" data-shortlist-dossier="${escapeAttr(dossierKey)}">
                    <label><span>${escapeHtml(zh ? "优先级" : "Priority")}</span>
                        <select class="glass-control scout-dossier-input" data-dossier-player="${escapeAttr(dossierKey)}" data-dossier-legacy-name="${escapeAttr(pName)}" data-dossier-field="priority">
                            <option value="urgent"${dossier.priority === "urgent" ? " selected" : ""}>${escapeHtml(zh ? "紧急" : "Urgent")}</option>
                            <option value="standard"${dossier.priority === "standard" ? " selected" : ""}>${escapeHtml(zh ? "标准" : "Standard")}</option>
                            <option value="monitor"${dossier.priority === "monitor" ? " selected" : ""}>${escapeHtml(zh ? "持续观察" : "Monitor")}</option>
                        </select>
                    </label>
                    <label><span>${escapeHtml(zh ? "建议" : "Recommendation")}</span>
                        <select class="glass-control scout-dossier-input" data-dossier-player="${escapeAttr(dossierKey)}" data-dossier-legacy-name="${escapeAttr(pName)}" data-dossier-field="recommendation">
                            <option value="target"${dossier.recommendation === "target" ? " selected" : ""}>${escapeHtml(zh ? "重点引进" : "Target")}</option>
                            <option value="monitor"${dossier.recommendation === "monitor" ? " selected" : ""}>${escapeHtml(zh ? "继续观察" : "Monitor")}</option>
                            <option value="decline"${dossier.recommendation === "decline" ? " selected" : ""}>${escapeHtml(zh ? "暂不推进" : "Decline")}</option>
                        </select>
                    </label>
                    <label class="scout-dossier-wide"><span>${escapeHtml(zh ? "目标角色" : "Target role")}</span>
                        <input class="glass-control scout-dossier-input" data-dossier-player="${escapeAttr(dossierKey)}" data-dossier-legacy-name="${escapeAttr(pName)}" data-dossier-field="target_role" maxlength="120" value="${escapeAttr(dossier.target_role)}" placeholder="${escapeAttr(zh ? "例如：高压体系的右侧中卫" : "e.g. right-sided centre-back in a high press")}">
                    </label>
                    <label class="scout-dossier-wide"><span>${escapeHtml(zh ? "理由与风险" : "Rationale and risks")}</span>
                        <textarea class="scout-note-textarea scout-dossier-input" data-dossier-player="${escapeAttr(dossierKey)}" data-dossier-legacy-name="${escapeAttr(pName)}" data-dossier-field="rationale" maxlength="2000" rows="3" placeholder="${escapeAttr(t("scout_note_placeholder"))}">${escapeHtml(note)}</textarea>
                    </label>
                </div>
                <button class="text-button scout-tactical-role-btn" data-tactical-role="${escapeAttr(pName)}" type="button" style="font-size:0.72rem;padding:0.2rem 0.4rem;margin-top:0.2rem">\u25C6 ${escapeHtml(t("generate_tactical_role"))}</button>
            </div>
        </div>`;
    }).join("") : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No players in shortlist</div>';

    updateSnapshotStatus();
    renderScoutingWorkspaceStatus();
}

function queueStatusKey(player) {
    return String(player.player_id || player.player_name || player.name || "");
}

function scoutingPlayerKey(player) {
    return String(player && (player.player_id || player.key || player.player_name || player.name) || "").trim();
}

function getShortlistDossier(player) {
    const key = scoutingPlayerKey(player);
    const name = String(player && (player.player_name || player.name) || "");
    const stored = scoutShortlistDossiers[key];
    return {
        priority: stored && ["urgent", "standard", "monitor"].includes(stored.priority)
            ? stored.priority
            : "standard",
        recommendation: stored && ["target", "monitor", "decline"].includes(stored.recommendation)
            ? stored.recommendation
            : "monitor",
        target_role: String(stored && stored.target_role || "").slice(0, 120),
        // Existing browser-local notes remain visible and become the dossier rationale on edit.
        rationale: String(stored && stored.rationale || scoutShortlistNotes[name] || "").slice(0, 2000),
    };
}

function updateShortlistDossier(playerKey, legacyName, field, value) {
    if (!playerKey || !["priority", "recommendation", "target_role", "rationale"].includes(field)) return;
    const current = getShortlistDossier({ key: playerKey, name: legacyName });
    const limit = field === "target_role" ? 120 : field === "rationale" ? 2000 : 24;
    current[field] = String(value || "").trim().slice(0, limit);
    if (field === "priority" && !["urgent", "standard", "monitor"].includes(current[field])) {
        current[field] = "standard";
    }
    if (field === "recommendation" && !["target", "monitor", "decline"].includes(current[field])) {
        current[field] = "monitor";
    }
    scoutShortlistDossiers[playerKey] = current;
    if (field === "rationale" && legacyName) scoutShortlistNotes[legacyName] = current.rationale;
    saveScoutShortlistDossiers();
}

function getQueueStatus(player) {
    const stableKey = queueStatusKey(player);
    const nameKey = String(player.player_name || player.name || "");
    const localStatus = scoutQueueStatuses[stableKey] || scoutQueueStatuses[nameKey];
    if (STATUS_CYCLE.includes(localStatus)) return localStatus;
    const apiStatus = String(player.review_status || "pending").toLowerCase();
    return STATUS_CYCLE.includes(apiStatus) ? apiStatus : "pending";
}

function filterReviewQueue(queue) {
    const query = appState.scoutingQuery.trim().toLowerCase();
    return queue.filter((player) => {
        const statusMatch = appState.scoutingStatus === "ALL" || getQueueStatus(player) === appState.scoutingStatus;
        const haystack = [player.player_name, player.name, player.team, player.league, player.position_group, player.reason_code]
            .join(" ").toLowerCase();
        return statusMatch && (!query || haystack.includes(query));
    });
}

function mergeScoutingRows(serverRows, localRows) {
    const merged = [];
    const seen = new Set();
    for (const row of [...(serverRows || []), ...(localRows || [])]) {
        const name = row.player_name || row.name || "";
        const key = String(row.player_id || row.key || name).toLowerCase();
        if (!key || seen.has(key)) continue;
        seen.add(key);
        merged.push({
            ...row,
            player_name: name,
            position_group: row.position_group || row.position || "",
            optimized_score: Number(row.optimized_score || row.rating || 0),
            confidence_level: (row.confidence_level || row.confidence || "MEDIUM").toUpperCase(),
            reason_code: row.reason_code || (row.key ? "manual_selection" : ""),
        });
    }
    return merged;
}

function sortReviewQueue(queue, mode) {
    const arr = [...queue];
    if (mode === "priority") {
        const confOrder = { "LOW": 0, "MEDIUM": 1, "HIGH": 2 };
        arr.sort((a, b) => {
            const sa = getQueueStatus(a);
            const sb = getQueueStatus(b);
            const siA = STATUS_CYCLE.indexOf(sa);
            const siB = STATUS_CYCLE.indexOf(sb);
            if (siA !== siB) return siA - siB;
            const ca = confOrder[(a.confidence_level || a.confidence || "LOW").toUpperCase()] ?? 1;
            const cb = confOrder[(b.confidence_level || b.confidence || "LOW").toUpperCase()] ?? 1;
            return ca - cb;
        });
    } else if (mode === "name") {
        arr.sort((a, b) => (a.player_name || a.name || "").localeCompare(b.player_name || b.name || ""));
    } else if (mode === "date") {
        arr.sort((a, b) => String(b.as_of_date || "").localeCompare(String(a.as_of_date || "")) || (b.minutes || 0) - (a.minutes || 0));
    }
    return arr;
}

function computeLeagueCoverage() {
    const byLeagueSeason = {};
    for (const p of players) {
        const league = p.league || "";
        const season = p.season || "";
        if (!league) continue;
        const key = `${league}|${season}`;
        if (!byLeagueSeason[key]) byLeagueSeason[key] = { league, season, teams: new Set(), ratedTeams: new Set() };
        byLeagueSeason[key].teams.add(p.team);
        if (p.rating > 0 && p.team) byLeagueSeason[key].ratedTeams.add(p.team);
    }
    // Group by league (aggregate seasons)
    const byLeague = {};
    for (const entry of Object.values(byLeagueSeason)) {
        if (!byLeague[entry.league]) byLeague[entry.league] = { total: 0, rated: 0 };
        byLeague[entry.league].total += entry.teams.size;
        byLeague[entry.league].rated += entry.ratedTeams.size;
    }
    return Object.entries(byLeague).map(([league, data]) => ({
        league,
        rated: data.rated,
        total: data.total,
        coverage: data.total > 0 ? data.rated / data.total : 0,
    })).sort((a, b) => a.league.localeCompare(b.league));
}

function renderOverview() {
    const health = artifactSummary.data_health || {};
    const healthItems = document.querySelectorAll("#data-health-list .health-item");
    if (healthItems.length >= 3) {
        const oofBadge = healthItems[0].querySelector(".status-pill");
        oofBadge.className = `status-pill ${health.oof_available ? "status-high" : "status-low"}`;
        oofBadge.textContent = health.oof_available ? "HIGH" : "LOW";
        const oofText = healthItems[0].querySelector("span[data-i18n='health_oof']");
        if (oofText) {
            oofText.textContent = health.oof_available
                ? (appState.lang === "zh" ? "身价 OOF 可用" : "Value OOF available")
                : (appState.lang === "zh" ? "身价 OOF 未生成" : "Value OOF not generated");
        }

        const proxyBadge = healthItems[1].querySelector(".status-pill");
        proxyBadge.className = `status-pill ${health.player_match_coverage ? "status-medium" : "status-low"}`;
        proxyBadge.textContent = health.player_match_coverage ? "MED" : "LOW";
        healthItems[1].querySelector("span[data-i18n='health_proxy']").textContent = health.player_match_coverage || t("health_proxy");

        const truthBadge = healthItems[2].querySelector(".status-pill");
        truthBadge.className = `status-pill ${health.truth_labels_available ? "status-high" : "status-low"}`;
        truthBadge.textContent = health.truth_labels_available ? "HIGH" : "LOW";
        const truthText = healthItems[2].querySelector("span[data-i18n='health_truth']");
        if (truthText) {
            truthText.textContent = health.truth_labels_available
                ? (appState.lang === "zh" ? "真实标签可用" : "Truth labels available")
                : (appState.lang === "zh" ? "真实标签未生成" : "Truth labels not generated");
        }
    }

    const overallBadge = document.querySelector("#view-overview .compact-panel .panel-head .status-pill");
    if (overallBadge) {
        const overallHigh = health.oof_available && health.truth_labels_available;
        overallBadge.className = `status-pill ${overallHigh ? "status-high" : "status-medium"}`;
        overallBadge.textContent = overallHigh ? "HIGH" : "MED";
    }

    // Confidence gate
    const gatePill = document.getElementById("confidence-gate-pill");
    if (gatePill && health.confidence_gate) {
        gatePill.textContent = "< 0.90 → LOW";
        gatePill.title = health.confidence_gate;
    }

    // License attribution from API
    const licenses = artifactSummary.license_attribution;
    if (licenses) {
        const licenseList = document.getElementById("license-list");
        if (licenseList) {
            const entries = Object.entries(licenses);
            licenseList.innerHTML = entries.map(([key, desc]) =>
                `<li class="health-item"><span class="dot status-high"></span><span title="${escapeAttr(desc)}">${escapeHtml(key)}</span></li>`
            ).join("");
        }
    }

    // ── Confidence Gate Section ──
    const gateSection = document.getElementById("confidence-gate-section");
    if (gateSection) {
        const pmCoverage = health.player_match_coverage || "";
        const hasMatch = pmCoverage.includes("real");
        const hasProxy = pmCoverage.includes("proxy");
        const dsLabel = artifactSummary.data_source_label || "";

        // Data source labels
        const sourceLabels = [
            { label: hasMatch ? t("data_type_real") : t("data_type_proxy"), cls: hasMatch ? "status-high" : "status-medium" },
            { label: dsLabel || "local parquet", cls: "status-medium" },
        ];

        // License attribution summary
        const licEntries = licenses ? Object.entries(licenses) : [];

        // Coverage by league
        const leagueCoverage = computeLeagueCoverage();

        let html = '<div class="panel-head"><h3>' + escapeHtml(t("confidence_gate")) + '</h3>';
        html += '<span class="status-pill status-medium">' + escapeHtml(t("confidence_gate_desc")) + '</span></div>';

        // Data source labels row
        html += '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.6rem">';
        sourceLabels.forEach(s => {
            html += `<span class="status-pill ${s.cls}">${escapeHtml(s.label)}</span>`;
        });
        html += '</div>';

        // License attribution summary
        if (licEntries.length > 0) {
            html += '<p style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin:0.3rem 0">' + escapeHtml(t("license_sources_label")) + '</p>';
            html += '<div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin-bottom:0.6rem">';
            licEntries.forEach(([key]) => {
                html += `<span class="status-pill status-medium">${escapeHtml(key)}</span>`;
            });
            html += '</div>';
        }

        // Coverage by league
        if (leagueCoverage.length > 0) {
            html += '<p style="font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin:0.3rem 0">' + escapeHtml(t("coverage_league")) + '</p>';
            html += '<div style="display:grid;grid-template-columns:1fr auto auto auto;gap:0.2rem 0.6rem;font-size:0.78rem">';
            leagueCoverage.forEach(lc => {
                const pctColor = lc.coverage > 0.90 ? "status-high" : (lc.coverage >= 0.70 ? "status-medium" : "status-low");
                const pctLabel = lc.coverage > 0.90 ? "HIGH" : (lc.coverage >= 0.70 ? "MED" : "LOW");
                html += `<span>${escapeHtml(lc.league)}</span>`;
                html += `<span>${escapeHtml(String(lc.rated))}/${escapeHtml(String(lc.total))}</span>`;
                html += `<span class="status-pill ${pctColor}">${Math.round(lc.coverage * 100)}%</span>`;
                html += `<span class="status-pill ${pctColor}">${pctLabel}</span>`;
            });
            html += '</div>';
        }

        // Link to license page
        html += '<div style="margin-top:0.5rem"><a href="#" onclick="setView(\'license\');return false" style="color:var(--accent);font-size:0.78rem">' + escapeHtml(appState.lang === "zh" ? "查看完整数据源详情" : "View full data source details") + '</a></div>';

        gateSection.innerHTML = html;
    }
}

function _fmtMetric(value, decimals) {
    if (value == null) return "–";
    return safeNum(value, decimals != null ? decimals : 3);
}

function _metricColor(metricKey, value) {
    if (value == null) return "var(--text-muted)";
    const v = Number(value);
    if (metricKey === "spearman" || metricKey === "pearson") {
        if (v >= 0.7) return "var(--accent, #4caf50)";
        if (v >= 0.5) return "var(--text, #ccc)";
        return "var(--warn, #ff9800)";
    }
    return "var(--text, #ccc)";
}

function _renderMetricCell(label, value, decimals, metricKey) {
    const formatted = _fmtMetric(value, decimals);
    const color = _metricColor(metricKey, value);
    return `<div><span style="color:var(--text-muted)">${escapeHtml(label)}</span><br><strong style="color:${color}">${escapeHtml(formatted)}</strong></div>`;
}

function _renderMetricsBlock(title, m, decimals) {
    if (!m || Object.keys(m).length === 0) return "";
    const d = decimals != null ? decimals : 3;
    const cells = [
        _renderMetricCell("Spearman", m.spearman, d, "spearman"),
        _renderMetricCell("Pearson", m.pearson, d, "pearson"),
        _renderMetricCell("Rank loss", m.rank_loss, d),
        _renderMetricCell("Cal MAE", m.calibration_mae, 1),
        _renderMetricCell("Pts MAE", m.points_mae, 1),
        _renderMetricCell("Pts RMSE", m.points_rmse, 1),
    ];
    if (m.n_players != null) cells.push(_renderMetricCell("Players", m.n_players, 0));
    if (m.n_team_seasons != null) cells.push(_renderMetricCell("Team-seas", m.n_team_seasons, 0));
    return `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(title)}</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(6rem,1fr));gap:0.25rem 0.6rem;font-size:0.78rem">${cells.join("")}</div>`;
}

function _renderParamsGrid(args) {
    if (!args || Object.keys(args).length === 0) return "";
    const knownEntries = [
        ["pop_size", "pop"],
        ["n_steps", "steps"],
        ["lr", "lr"],
        ["patience", "patience"],
        ["warmup_steps", "warmup"],
        ["grad_clip", "grad clip"],
        ["min_lr_ratio", "min lr"],
        ["spearman_weight", "sp wt"],
        ["ndcg_weight", "ndcg wt"],
        ["position_consistency_weight", "pos wt"],
        ["points_regression_weight", "pts wt"],
        ["distribution_weight", "dist wt"],
        ["quantile_weight", "quant wt"],
        ["range_penalty_weight", "range wt"],
        ["tail_calibration_weight", "tail wt"],
        ["league_bias_weight", "league wt"],
        ["extreme_penalty_weight", "extreme wt"],
        ["prior_weight", "prior wt"],
        ["dc_likelihood_weight", "dc wt"],
        ["dc_rho", "dc rho"],
        ["league_calibration_prior_n", "cal prior"],
        ["league_calibration_cap", "cal cap"],
    ];
    const knownKeys = new Set(knownEntries.map(([k]) => k));
    // Known params first
    const cells = knownEntries
        .filter(([key]) => args[key] != null)
        .map(([key, label]) => {
            const v = args[key];
            const formatted = typeof v === "boolean" ? (v ? "on" : "off") : String(v);
            return `<div><span style="color:var(--text-muted)">${escapeHtml(label)}</span><br><span>${escapeHtml(formatted)}</span></div>`;
        });
    // Remaining params not in known list (full parameter dump)
    const extraCells = Object.entries(args)
        .filter(([key]) => !knownKeys.has(key) && args[key] != null)
        .map(([key, v]) => {
            const formatted = typeof v === "boolean" ? (v ? "on" : "off") : String(v);
            return `<div><span style="color:var(--text-muted)">${escapeHtml(key)}</span><br><span>${escapeHtml(formatted)}</span></div>`;
        });
    const allCells = [...cells, ...extraCells];
    if (allCells.length === 0) return "";
    return `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">Parameters (${allCells.length})</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(5.5rem,1fr));gap:0.2rem 0.5rem;font-size:0.75rem">${allCells.join("")}</div>`;
}

function _renderPositionMetrics(posMetrics) {
    if (!posMetrics || Object.keys(posMetrics).length === 0) return "";
    const rows = Object.entries(posMetrics).map(([pos, m]) => {
        return `<tr>
            <td style="padding:0.15rem 0.4rem;font-weight:600">${escapeHtml(pos)}</td>
            <td style="padding:0.15rem 0.4rem">${_fmtMetric(m.spearman)}</td>
            <td style="padding:0.15rem 0.4rem">${_fmtMetric(m.pearson)}</td>
            <td style="padding:0.15rem 0.4rem">${m.n_players != null ? Math.round(m.n_players) : "–"}</td>
        </tr>`;
    });
    return `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">Position-wise</p>
    <table style="font-size:0.75rem;width:100%;border-collapse:collapse">
        <thead><tr style="color:var(--text-muted)">
            <th style="text-align:left;padding:0.15rem 0.4rem">Pos</th>
            <th style="text-align:left;padding:0.15rem 0.4rem">Spearman</th>
            <th style="text-align:left;padding:0.15rem 0.4rem">Pearson</th>
            <th style="text-align:left;padding:0.15rem 0.4rem">N</th>
        </tr></thead>
        <tbody>${rows.join("")}</tbody>
    </table>`;
}

function _renderErrorCases(errorCases) {
    if (!errorCases) return "";
    const parts = [];
    const over = errorCases.over_estimated || [];
    const under = errorCases.under_estimated || [];
    if (over.length > 0) {
        const items = over.slice(0, 5).map((e) => {
            const team = e.team || e.team_name || "?";
            const residual = e.residual != null ? Number(e.residual).toFixed(1) : "";
            return `${escapeHtml(team)}${residual ? " (+" + residual + ")" : ""}`;
        }).join(", ");
        parts.push(`<div><span style="color:var(--text-muted)">Over-estimated:</span> ${items}</div>`);
    }
    if (under.length > 0) {
        const items = under.slice(0, 5).map((e) => {
            const team = e.team || e.team_name || "?";
            const residual = e.residual != null ? Number(e.residual).toFixed(1) : "";
            return `${escapeHtml(team)}${residual ? " (" + residual + ")" : ""}`;
        }).join(", ");
        parts.push(`<div><span style="color:var(--text-muted)">Under-estimated:</span> ${items}</div>`);
    }
    if (parts.length === 0) return "";
    return `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">Error cases</p>
    <div style="font-size:0.75rem;line-height:1.5">${parts.join("")}</div>`;
}

function _renderRunDetailExtra(detail) {
    if (!detail) return "";
    const z = appState.lang === "zh";
    const sections = [];

    // Feature importance from parquet (only available via detail endpoint)
    const fi = detail.feature_importance;
    if (Array.isArray(fi) && fi.length > 0) {
        const rows = fi.slice(0, 10).map((e, i) => {
            const name = e.name || e.feature || `f${i}`;
            const val = e.importance ?? e.value ?? 0;
            const pct = typeof val === "number" && val <= 1 && val >= 0
                ? (val * 100).toFixed(2) + "%"
                : Number(val).toFixed(4);
            return `<div>\u25C6 ${escapeHtml(String(name))} <span style="color:var(--text-muted)">${escapeHtml(pct)}</span></div>`;
        }).join("");
        sections.push(`<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? "特征重要性（完整）" : "Feature Importance (full)"}</p>
        <div style="font-size:0.75rem;line-height:1.6">${rows}</div>`);
    }

    // Params summary with min/max (only available via detail endpoint)
    const ps = detail.params_summary;
    if (ps && typeof ps === "object") {
        const shape = Array.isArray(ps.shape) ? ps.shape.join("×") : String(ps.shape || "—");
        const cells = [
            `<span style="color:var(--text-muted)">shape</span> ${escapeHtml(shape)}`,
            `<span style="color:var(--text-muted)">mean</span> ${ps.mean != null ? Number(ps.mean).toFixed(6) : "—"}`,
            `<span style="color:var(--text-muted)">std</span> ${ps.std != null ? Number(ps.std).toFixed(6) : "—"}`,
            `<span style="color:var(--text-muted)">min</span> ${ps.min != null ? Number(ps.min).toFixed(6) : "—"}`,
            `<span style="color:var(--text-muted)">max</span> ${ps.max != null ? Number(ps.max).toFixed(6) : "—"}`,
        ];
        sections.push(`<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? "参数统计" : "Params Summary"}</p>
        <div style="font-size:0.75rem;line-height:1.6">${cells.join(" · ")}</div>`);
    }

    // Data attribution (only available via detail endpoint)
    const da = detail.data_attribution;
    if (da && typeof da === "object") {
        const parts = [];
        if (da.primary_source) {
            parts.push(`<div><span style="color:var(--text-muted)">${z ? "主要数据源" : "Primary source"}:</span> ${escapeHtml(da.primary_source)}</div>`);
        }
        if (da.license_note) {
            parts.push(`<div style="margin-top:0.2rem;font-size:0.72rem;line-height:1.5">${escapeHtml(da.license_note)}</div>`);
        }
        if (da.statsbomb_attribution_required) {
            parts.push(`<div style="margin-top:0.3rem;padding:0.3rem 0.4rem;background:var(--bg-alt,#1a1a2e);border-radius:4px;font-size:0.72rem;line-height:1.5"><strong>StatsBomb:</strong> ${escapeHtml(da.statsbomb_attribution_required)}</div>`);
        }
        if (parts.length > 0) {
            sections.push(`<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? "数据归属" : "Data Attribution"}</p>
            <div style="font-size:0.75rem;line-height:1.5">${parts.join("")}</div>`);
        }
    }

    if (sections.length === 0) return "";
    return sections.join("<hr style=\"border:none;border-top:1px solid var(--border,#333);margin:0.35rem 0\">");
}

function _populateRunComparisonSelects() {
    const selA = document.getElementById("compare-run-a");
    const selB = document.getElementById("compare-run-b");
    if (!selA || !selB) return;
    const runs = (modelRuns.runs || []).slice(0, 20);
    const z = appState.lang === "zh";
    const prevA = selA.value;
    const prevB = selB.value;

    const options = runs.map((r) => {
        const id = r.run_id || "";
        const sp = r.holdout_summary?.optimized_test?.spearman ?? r.spearman;
        const label = sp != null ? `${id} (sp ${Number(sp).toFixed(3)})` : id;
        return `<option value="${escapeAttr(id)}">${escapeHtml(label)}</option>`;
    }).join("");

    selA.innerHTML = `<option value="">${z ? "— 选择 —" : "— Select —"}</option>` + options;
    selB.innerHTML = `<option value="">${z ? "— 选择 —" : "— Select —"}</option>` + options;
    if (prevA) selA.value = prevA;
    if (prevB) selB.value = prevB;

    const btn = document.getElementById("compare-runs-btn");
    if (btn && !btn.dataset.bound) {
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {
            const a = selA.value;
            const b = selB.value;
            if (!a || !b || a === b) return;
            renderRunComparison(a, b);
        });
    }
}

async function renderRunComparison(runIdA, runIdB) {
    const body = document.getElementById("run-comparison-body");
    const statusEl = document.getElementById("run-comparison-status");
    if (!body) return;
    const z = appState.lang === "zh";
    body.innerHTML = `<p style="color:var(--text-muted)">${z ? "加载中..." : "Loading..."}</p>`;

    const [detailA, detailB] = await Promise.all([
        fetchModelRunDetail(runIdA),
        fetchModelRunDetail(runIdB),
    ]);

    if (!detailA || !detailB) {
        body.innerHTML = `<p style="color:var(--text-muted)">${z ? "无法加载运行详情" : "Failed to load run details"}</p>`;
        if (statusEl) { statusEl.textContent = z ? "加载失败" : "failed"; statusEl.className = "status-pill status-low"; }
        return;
    }

    const hsA = detailA.holdout_summary || {};
    const hsB = detailB.holdout_summary || {};
    const metricKeys = ["spearman", "pearson", "rank_loss", "calibration_mae", "points_mae", "points_rmse", "points_bias", "points_spread_ratio", "raw_spread_ratio", "team_coverage"];
    const splitKeys = ["optimized_test", "baseline_test", "optimized_train", "baseline_train"];
    const splitLabels = z
        ? { optimized_test: "优化(测试)", baseline_test: "基线(测试)", optimized_train: "优化(训练)", baseline_train: "基线(训练)" }
        : { optimized_test: "Opt (test)", baseline_test: "Base (test)", optimized_train: "Opt (train)", baseline_train: "Base (train)" };

    function fmtVal(v) {
        if (v === undefined || v === null) return "—";
        if (typeof v === "number") return v.toFixed(4);
        return String(v);
    }

    let tableHtml = `<div class="table-scroll"><table style="width:100%;font-size:0.75rem"><thead><tr>
        <th style="text-align:left">${z ? "指标" : "Metric"}</th>
        <th>${escapeHtml(runIdA)}</th>
        <th>${escapeHtml(runIdB)}</th>
        <th>${z ? "差异" : "Delta"}</th>
    </tr></thead><tbody>`;

    splitKeys.forEach((sk) => {
        const splitA = hsA[sk] || {};
        const splitB = hsB[sk] || {};
        if (Object.keys(splitA).length === 0 && Object.keys(splitB).length === 0) return;
        tableHtml += `<tr><td colspan="4" style="font-weight:700;padding-top:0.4rem;color:var(--text-secondary,#ccc)">${escapeHtml(splitLabels[sk] || sk)}</td></tr>`;
        metricKeys.forEach((mk) => {
            const va = splitA[mk];
            const vb = splitB[mk];
            if (va === undefined && vb === undefined) return;
            let delta = "";
            let deltaClass = "";
            if (typeof va === "number" && typeof vb === "number") {
                const d = vb - va;
                delta = (d >= 0 ? "+" : "") + d.toFixed(4);
                // For error metrics (rank_loss, calibration_mae, points_*), lower is better
                const lowerIsBetter = mk !== "spearman" && mk !== "pearson" && mk !== "team_coverage";
                if (lowerIsBetter) {
                    deltaClass = d < 0 ? "status-high" : (d > 0 ? "status-low" : "status-medium");
                } else {
                    deltaClass = d > 0 ? "status-high" : (d < 0 ? "status-low" : "status-medium");
                }
            }
            tableHtml += `<tr>
                <td style="padding-left:0.8rem">${escapeHtml(mk)}</td>
                <td style="text-align:center">${fmtVal(va)}</td>
                <td style="text-align:center">${fmtVal(vb)}</td>
                <td style="text-align:center">${delta ? `<span class="status-pill ${deltaClass}" style="font-size:0.62rem">${escapeHtml(delta)}</span>` : "—"}</td>
            </tr>`;
        });
    });
    tableHtml += `</tbody></table></div>`;

    // Overfit gap comparison
    const ogA = hsA.overfit_rank_loss_gap;
    const ogB = hsB.overfit_rank_loss_gap;
    let ogHtml = "";
    if (ogA != null && ogB != null) {
        const z2 = z;
        ogHtml = `<div style="margin-top:0.5rem;font-size:0.75rem">
            <span style="color:var(--text-muted)">${z2 ? "过拟合差距" : "Overfit gap"}: </span>
            <strong>${escapeHtml(runIdA)}</strong> ${Number(ogA).toFixed(4)} →
            <strong>${escapeHtml(runIdB)}</strong> ${Number(ogB).toFixed(4)}
            ${(ogB - ogA) < 0 ? `<span class="status-pill status-high" style="font-size:0.62rem">${z2 ? "改善" : "improved"}</span>` : ""}
        </div>`;
    }

    body.innerHTML = tableHtml + ogHtml;
    if (statusEl) {
        statusEl.textContent = `${runIdA} vs ${runIdB}`;
        statusEl.className = "status-pill status-high";
    }
}

function _renderDataAttributionPanel() {
    const panel = document.getElementById("data-attribution-content");
    if (!panel) return;
    const z = appState.lang === "zh";
    const la = licenseData.license_attribution || {};
    const dsLabel = licenseData.data_source_label || "—";
    const updatedAt = licenseData.updated_at;

    let html = "";

    // Primary source summary
    html += `<div style="margin-bottom:0.5rem">
        <span style="color:var(--text-muted)">${z ? "数据源标签" : "Data source label"}: </span>
        <strong>${escapeHtml(dsLabel)}</strong>
        ${updatedAt ? `<span style="color:var(--text-muted);font-size:0.72rem;margin-left:0.5rem">${z ? "更新于" : "updated"} ${new Date(updatedAt * 1000).toLocaleDateString()}</span>` : ""}
    </div>`;

    // license_attribution is a simple key→string dict from /license endpoint
    const sourceKeys = Object.keys(la).filter((k) =>
        k !== "statsbomb_attribution_required" && k !== "license_note" && k !== "sources",
    );
    if (sourceKeys.length > 0) {
        html += `<p style="margin:0.5rem 0 0.25rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? "数据源归属" : "Source Attribution"}</p>`;
        html += `<div style="font-size:0.75rem;line-height:1.6">`;
        sourceKeys.forEach((key) => {
            const note = la[key];
            if (!note) return;
            // Find matching LICENSE_SOURCES entry for URL
            const meta = LICENSE_SOURCES.find((s) => s.key === key);
            const name = meta ? meta.name : key;
            const url = meta ? meta.url : "";
            html += `<div style="display:flex;align-items:baseline;gap:0.4rem;margin-bottom:0.2rem;flex-wrap:wrap">
                <strong>${escapeHtml(name)}</strong>
                <span style="font-size:0.72rem;color:var(--text-muted)">${escapeHtml(note)}</span>
                ${url ? `<a href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer" style="font-size:0.72rem;color:var(--accent,#4f9cff)">${z ? "链接" : "link"}</a>` : ""}
            </div>`;
        });
        html += `</div>`;
    }

    // StatsBomb special callout
    const statsbombAttr = la.statsbomb_attribution_required;
    if (statsbombAttr) {
        html += `<div style="margin:0.4rem 0;padding:0.4rem 0.5rem;background:var(--bg-alt,#1a1a2e);border-radius:4px;font-size:0.75rem;line-height:1.5">
            <strong>StatsBomb Open Data:</strong> ${escapeHtml(statsbombAttr)}
        </div>`;
    }

    if (html === "") {
        html = `<p style="color:var(--text-muted)">${z ? "暂无归属信息" : "No attribution data available"}</p>`;
    }

    panel.innerHTML = html;
}

function _posGroupRating(team, group) {
    const pg = (team.position_groups || {})[group];
    return pg ? pg.rating : null;
}

function _posGroupCount(team, group) {
    const pg = (team.position_groups || {})[group];
    return pg ? pg.player_count : 0;
}

function _ratingCell(rating) {
    if (rating === null || rating === undefined || isNaN(rating)) {
        return '<span style="color:var(--text-muted)">—</span>';
    }
    const cls = rating >= 60 ? "status-high" : rating >= 45 ? "status-medium" : "status-low";
    return `<span class="status-pill ${cls}">${rating.toFixed(1)}</span>`;
}

async function renderTeams() {
    const tbody = document.getElementById("teams-table-body");
    if (!tbody) return;

    // Fetch data if not loaded
    if (teamStrengthData.count === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted)">Loading...</td></tr>';
        try {
            teamStrengthData = await fetchTeamStrength();
        } catch {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted)">Failed to load</td></tr>';
            return;
        }
    }

    const teams = teamStrengthData.teams || [];
    if (teams.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted)">No data</td></tr>';
        return;
    }

    // Update summary metrics
    const countEl = document.getElementById("teams-count");
    const avgEl = document.getElementById("teams-avg-rating");
    const topEl = document.getElementById("teams-top-rating");
    if (countEl) countEl.textContent = teams.length;
    const ratings = teams.map(t => t.overall_rating || 0);
    const avg = ratings.length > 0 ? ratings.reduce((a, b) => a + b, 0) / ratings.length : 0;
    const top = ratings.length > 0 ? Math.max(...ratings) : 0;
    if (avgEl) avgEl.textContent = avg.toFixed(1);
    if (topEl) topEl.textContent = top.toFixed(1);

    // Populate league filter
    const leagueFilter = document.getElementById("teams-league-filter");
    if (leagueFilter && leagueFilter.options.length <= 1) {
        const leagues = [...new Set(teams.map(t => t.league).filter(Boolean))].sort();
        leagues.forEach(lg => {
            const opt = document.createElement("option");
            opt.value = lg;
            opt.textContent = lg;
            leagueFilter.appendChild(opt);
        });
    }

    // Filter by league
    const selectedLeague = leagueFilter ? leagueFilter.value : "";
    const filtered = selectedLeague ? teams.filter(t => t.league === selectedLeague) : teams;

    // Render table
    tbody.innerHTML = filtered.map((team, i) => {
        return `
        <tr style="cursor:pointer" data-team="${escapeAttr(team.team)}">
            <td>${i + 1}</td>
            <td>${escapeHtml(team.team)}</td>
            <td>${escapeHtml(team.league || "—")}</td>
            <td><strong>${(team.overall_rating || 0).toFixed(1)}</strong></td>
            <td>${team.squad_size || 0}</td>
            <td>${_ratingCell(_posGroupRating(team, "GK"))}</td>
            <td>${_ratingCell(_posGroupRating(team, "DEF"))}</td>
            <td>${_ratingCell(_posGroupRating(team, "MID"))}</td>
            <td>${_ratingCell(_posGroupRating(team, "ATT"))}</td>
        </tr>`;
    }).join("");

    // Row click handler
    tbody.querySelectorAll("tr[data-team]").forEach(row => {
        row.addEventListener("click", () => {
            const teamName = row.dataset.team;
            const team = filtered.find(t => t.team === teamName);
            if (team) renderTeamDetail(team);
        });
    });

    // League filter handler
    if (leagueFilter) {
        leagueFilter.onchange = () => renderTeams();
    }

    // Render chart
    renderTeamsChart(filtered);
    initTeamCompareControls();
}

function renderTeamDetail(team) {
    const content = document.getElementById("teams-detail-content");
    const pill = document.getElementById("teams-detail-pill");
    if (!content) return;

    const posGroups = ["GK", "DEF", "MID", "ATT"];
    const posBreakdown = posGroups.map(g => {
        const pg = (team.position_groups || {})[g];
        if (!pg) return "";
        return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:0.3rem 0;border-bottom:1px solid var(--border)">
            <span style="font-weight:600">${g}</span>
            <span>${_ratingCell(pg.rating)} <span style="color:var(--text-muted);font-size:0.8rem">(${pg.player_count} players)</span></span>
        </div>`;
    }).join("");

    const topPlayers = (team.top_players || []).map(p => {
        return `
        <tr>
            <td>${escapeHtml(p.name)}</td>
            <td>${escapeHtml(p.position || "—")}</td>
            <td>${(p.rating || 0).toFixed(1)}</td>
            <td>${p.minutes || 0}</td>
            <td><span class="status-pill ${(p.confidence || "LOW").toUpperCase() === "HIGH" ? "status-high" : (p.confidence || "LOW").toUpperCase() === "MEDIUM" ? "status-medium" : "status-low"}">${escapeHtml(p.confidence || "LOW")}</span></td>
        </tr>`;
    }).join("");

    content.innerHTML = `
        <h4 style="margin:0 0 0.5rem">${escapeHtml(team.team)}</h4>
        <p style="color:var(--text-muted);margin:0 0 0.5rem">${escapeHtml(team.league || "—")} · ${escapeHtml(team.season || "—")}</p>
        <div style="margin:0.5rem 0">
            <strong>${(team.overall_rating || 0).toFixed(1)}</strong> overall · ${team.squad_size || 0} players · ${team.total_minutes || 0} total minutes
        </div>
        <div style="margin:0.8rem 0">${posBreakdown}</div>
        ${topPlayers ? `
        <p style="margin:0.8rem 0 0.3rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">Top Players</p>
        <table class="data-table" style="font-size:0.8rem">
            <thead><tr><th>Name</th><th>Pos</th><th>Rating</th><th>Min</th><th>Conf</th></tr></thead>
            <tbody>${topPlayers}</tbody>
        </table>` : ""}`;
    if (pill) pill.textContent = (team.overall_rating || 0).toFixed(1);
}

function renderTeamsChart(teams) {
    const chartEl = document.getElementById("teams-chart");
    if (!chartEl || typeof echarts === "undefined") return;

    // Show top 15 teams
    const top = teams.slice(0, 15);
    const chart = echarts.init(chartEl);
    if (appState.charts.teams) appState.charts.teams.dispose();
    appState.charts.teams = chart;

    const teamNames = top.map(t => t.team);
    const series = ["GK", "DEF", "MID", "ATT"].map(group => ({
        name: group,
        type: "bar",
        stack: "total",
        data: top.map(t => {
            const pg = (t.position_groups || {})[group];
            return pg ? pg.rating : 0;
        }),
    }));

    chart.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        legend: { data: ["GK", "DEF", "MID", "ATT"], bottom: 0 },
        grid: { left: "3%", right: "4%", bottom: "15%", containLabel: true },
        xAxis: { type: "category", data: teamNames, axisLabel: { rotate: 45, fontSize: 10 } },
        yAxis: { type: "value", name: "Rating" },
        series: series,
    });
}

async function fetchTeamComparison(a, b) {
    try {
        const data = await fetchJson(`/teams/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
        // Static fallback returns a pairs list; find the matching pair client-side.
        if (data && Array.isArray(data.pairs)) {
            const aLower = a.toLowerCase();
            const bLower = b.toLowerCase();
            const pair = data.pairs.find(p => {
                const na = (p.team_a && p.team_a.name || "").toLowerCase();
                const nb = (p.team_b && p.team_b.name || "").toLowerCase();
                return (na === aLower && nb === bLower) || (na === bLower && nb === aLower);
            });
            if (pair) return pair;
            return { error: "对比数据离线不可用" };
        }
        return data;
    } catch (err) {
        console.warn("Failed to fetch team comparison:", err);
        return { error: "Failed to load comparison" };
    }
}

function initTeamCompareControls() {
    const btn = document.getElementById("team-compare-btn");
    const inputA = document.getElementById("team-compare-input-a");
    const inputB = document.getElementById("team-compare-input-b");

    // Wire typeahead first so its keydown handler runs before the Enter handler below
    SearchTypeahead("team-compare-input-a", "teams");
    SearchTypeahead("team-compare-input-b", "teams");

    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = "1";

    const doCompare = async () => {
        const a = inputA.value.trim();
        const b = inputB.value.trim();
        if (!a || !b) return;
        btn.disabled = true;
        btn.textContent = "...";
        try {
            await _renderTeamCompareResult(a, b);
        } finally {
            btn.disabled = false;
            btn.textContent = t("teams_compare_button");
        }
    };

    btn.addEventListener("click", doCompare);
    const handler = (e) => { if (e.key === "Enter") doCompare(); };
    if (inputA) inputA.addEventListener("keydown", handler);
    if (inputB) inputB.addEventListener("keydown", handler);
}

async function _renderTeamCompareResult(a, b) {
    const data = await fetchTeamComparison(a, b);
    const wrap = document.getElementById("team-compare-result");

    if (data.error) {
        if (wrap) wrap.style.display = "none";
        alert(data.error);
        return;
    }

    if (wrap) wrap.style.display = "block";

    const nameA = data.team_a ? data.team_a.name : a;
    const nameB = data.team_b ? data.team_b.name : b;

    // Column headers
    const colA = document.getElementById("team-compare-col-a");
    const colB = document.getElementById("team-compare-col-b");
    if (colA) colA.textContent = nameA;
    if (colB) colB.textContent = nameB;

    // Pill
    const pill = document.getElementById("team-compare-pill");
    if (pill) {
        const diff = data.overall_diff || 0;
        pill.textContent = diff > 0 ? `${nameA} +${diff.toFixed(1)}` : diff < 0 ? `${nameB} +${(-diff).toFixed(1)}` : "Tie";
    }

    // Position group table
    const body = document.getElementById("team-compare-pos-body");
    if (body) {
        body.innerHTML = (data.position_group_comparison || []).map(p => {
            const valA = p.rating_a !== null && p.rating_a !== undefined ? p.rating_a.toFixed(1) : "—";
            const valB = p.rating_b !== null && p.rating_b !== undefined ? p.rating_b.toFixed(1) : "—";
            const diff = p.diff !== null && p.diff !== undefined ? (p.diff > 0 ? `+${p.diff.toFixed(1)}` : p.diff.toFixed(1)) : "—";
            const cls = p.diff > 0 ? "status-high" : p.diff < 0 ? "status-low" : "";
            return `<tr>
                <td>${escapeHtml(p.group)}</td>
                <td>${valA}</td>
                <td>${valB}</td>
                <td><span class="status-pill ${cls}">${diff}</span></td>
            </tr>`;
        }).join("");
    }

    // Radar chart
    const chartEl = document.getElementById("team-compare-radar-chart");
    if (chartEl && typeof echarts !== "undefined") {
        if (appState.charts.teamCompare) appState.charts.teamCompare.dispose();
        const chart = echarts.init(chartEl);
        appState.charts.teamCompare = chart;

        const radarA = data.radar_a || [];
        const radarB = data.radar_b || [];
        const labels = data.radar_labels || [];
        const z = appState.lang === "zh";

        chart.setOption({
            tooltip: { trigger: "item" },
            legend: { data: [nameA, nameB], bottom: 0 },
            radar: {
                indicator: labels.map(l => ({ name: l, max: 100 })),
                shape: "polygon",
                splitArea: { areaStyle: { color: ["rgba(100,180,255,0.02)", "rgba(100,180,255,0.05)"] } },
            },
            series: [{
                type: "radar",
                data: [
                    {
                        value: radarA,
                        name: nameA,
                        areaStyle: { opacity: 0.15, color: "#4a90d9" },
                        lineStyle: { width: 2, color: "#4a90d9" },
                        itemStyle: { color: "#4a90d9" },
                    },
                    {
                        value: radarB,
                        name: nameB,
                        areaStyle: { opacity: 0.15, color: "#ff9f43" },
                        lineStyle: { width: 2, color: "#ff9f43" },
                        itemStyle: { color: "#ff9f43" },
                    },
                ],
            }],
        });

        // Dimension difference table
        const diffEl = document.getElementById("team-compare-diff-table");
        if (diffEl) {
            const rows = labels.map((label, i) => {
                const valA = radarA[i] != null ? radarA[i] : null;
                const valB = radarB[i] != null ? radarB[i] : null;
                const diff = (valA != null && valB != null) ? valA - valB : null;
                const diffText = diff != null ? (diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)) : "—";
                const cls = diff > 0 ? "status-high" : diff < 0 ? "status-low" : "";
                const winner = diff > 0 ? nameA : diff < 0 ? nameB : z ? "持平" : "Tie";
                return `<tr>
                    <td style="font-weight:600">${escapeHtml(label)}</td>
                    <td>${valA != null ? valA.toFixed(1) : "—"}</td>
                    <td>${valB != null ? valB.toFixed(1) : "—"}</td>
                    <td><span class="status-pill ${cls}">${diffText}</span></td>
                    <td style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(winner)}</td>
                </tr>`;
            }).join("");
            diffEl.innerHTML = `
                <table style="width:100%;font-size:0.75rem;border-collapse:collapse">
                    <thead>
                        <tr style="color:var(--text-muted);text-align:left">
                            <th style="padding:0.2rem">${z ? "维度" : "Dimension"}</th>
                            <th style="padding:0.2rem">${escapeHtml(nameA)}</th>
                            <th style="padding:0.2rem">${escapeHtml(nameB)}</th>
                            <th style="padding:0.2rem">Δ</th>
                            <th style="padding:0.2rem">${z ? "优势" : "Edge"}</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>`;
        }
    }
}

function renderReports() {
    const latestRun = (modelRuns.runs || [])[0] || {};
    const latestMetrics = latestRun.metrics || {};
    const holdoutSummary = latestRun.holdout_summary || {};
    const optTest = holdoutSummary.optimized_test || {};
    const runSpearman = optTest.spearman ?? latestMetrics.spearman ?? latestRun.spearman;
    const runStatus = runSpearman != null ? `Spearman ${Number(runSpearman).toFixed(3)}` : "no metrics";
    document.getElementById("report-run-title").textContent = latestRun.run_id || "rating_optimizer_gpu";
    document.getElementById("report-run-status").textContent = runStatus;
    document.getElementById("report-run-status").className = `status-pill ${runSpearman != null ? "status-high" : "status-low"}`;

    const valueMetrics = valueSummaryMeta.metrics || {};
    const valueImprovement = valueMetrics.mae_improvement_vs_baseline;
    const valueIsDemo = valueSummaryMeta.status === "demo";
    document.getElementById("report-value-title").textContent = valueMetrics.estimator || "value_fairness_oof";
    document.getElementById("report-value-status").textContent = valueIsDemo
        ? "DEMO"
        : (valueImprovement ? `+${Math.round(valueImprovement).toLocaleString()} MAE` : "ready");
    document.getElementById("report-value-status").className = `status-pill ${valueIsDemo ? "status-medium" : (valueSummaryMeta.sample_count > 0 ? "status-high" : "status-low")}`;

    const predictionReady = predictionMeta.status === "ok";
    const dcReady = (predictionMeta.dixon_coles || {}).status === "ok";
    const predictionLabel = predictionReady
        ? `${predictionMeta.model_type || "independent_poisson"} · ${predictionMeta.num_teams || 0} teams`
        : "no artifact";
    const dcLabel = dcReady
        ? `DC: rho=${((predictionMeta.dixon_coles || {}).rho || 0).toFixed(3)}`
        : "";
    document.getElementById("report-prediction-title").textContent = predictionReady
        ? (dcReady ? "Poisson + Dixon-Coles" : "Poisson baseline")
        : "prediction";
    document.getElementById("report-prediction-status").textContent = dcReady
        ? `${predictionLabel} | ${dcLabel}`
        : predictionLabel;
    document.getElementById("report-prediction-status").className = `status-pill ${predictionReady ? "status-medium" : "status-low"}`;

    document.getElementById("model-runs-count").textContent = String(modelRuns.count || 0);
    const runList = document.getElementById("model-runs-list");
    const runs = (modelRuns.runs || []).slice(0, 12);
    runList.innerHTML = runs.length > 0
        ? runs.map((run) => {
            const z = appState.lang === "zh";
            const metrics = run.metrics || {};
            const args = run.args || {};
            const hs = run.holdout_summary || {};
            const optTest = hs.optimized_test || {};
            const baseTest = hs.baseline_test || {};
            const optTrain = hs.optimized_train || {};
            const baseTrain = hs.baseline_train || {};
            // Top-level flat aliases from enrichment
            const spearman = optTest.spearman ?? metrics.spearman ?? run.spearman;
            const pearson = optTest.pearson ?? metrics.pearson ?? run.pearson;
            const hash = run.input_hash || "n/a";
            const seed = args.seed ?? run.seed ?? "–";
            const nPlayers = optTest.n_players ?? metrics.n_players ?? run.n_players ?? "–";
            const nTeamSeasons = optTest.n_team_seasons ?? metrics.n_team_seasons ?? run.n_team_seasons ?? "–";
            const coverage = optTest.team_coverage ?? metrics.team_coverage ?? run.team_coverage;
            const dataSource = run.data_source || "";
            const overfitGap = hs.overfit_rank_loss_gap;
            const lineage = run.lineage || {};
            const snapshotHash = lineage.dataset_snapshot?.input_hash || hash;
            const manifestHash = lineage.feature_manifest?.hash || null;
            const lineageStatus = lineage.status || "not_recorded";

            // Header status
            const statusText = spearman != null ? "READY" : "N/A";
            const statusClass = spearman != null ? "status-high" : "status-low";

            // Details row
            const detailParts = [
                `<span style="color:var(--text-muted)">hash</span> ${escapeHtml(hash)}`,
                `<span style="color:var(--text-muted)">snapshot</span> ${escapeHtml(snapshotHash || "n/a")}`,
                `<span style="color:var(--text-muted)">seed</span> ${escapeHtml(String(seed))}`,
                `<span style="color:var(--text-muted)">players</span> ${escapeHtml(String(nPlayers))}`,
                `<span style="color:var(--text-muted)">team-seas</span> ${escapeHtml(String(nTeamSeasons))}`,
            ];
            if (coverage != null) {
                detailParts.push(`<span style="color:var(--text-muted)">coverage</span> ${(coverage * 100).toFixed(1)}%`);
            }
            if (overfitGap != null) {
                detailParts.push(`<span style="color:var(--text-muted)">overfit gap</span> ${Number(overfitGap).toFixed(3)}`);
            }
            if (dataSource) {
                detailParts.push(`<span style="color:var(--text-muted)">source</span> ${escapeHtml(dataSource)}`);
            }

            // Metrics blocks
            const optTestHtml = _renderMetricsBlock("Optimized (test)", optTest);
            const baseTestHtml = _renderMetricsBlock("Baseline (test)", baseTest);
            const optTrainHtml = _renderMetricsBlock("Optimized (train)", optTrain);
            const baseTrainHtml = _renderMetricsBlock("Baseline (train)", baseTrain);

            // Parameters grid
            const paramsHtml = _renderParamsGrid(args);

            // Position-wise metrics
            const posMetrics = run.position_metrics || run.position_metrics_by_group || {};
            const posHtml = _renderPositionMetrics(posMetrics);

            // Error cases
            const errorHtml = _renderErrorCases(run.error_cases);

            // Reproduce command
            const cmd = run.reproduce_command || "";
            const cmdHtml = cmd
                ? `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">Reproduce</p>
                   <pre style="margin:0;padding:0.35rem 0.5rem;background:var(--bg-alt,#1a1a2e);border-radius:4px;font-size:0.72rem;overflow-x:auto;white-space:pre-wrap;word-break:break-all;font-family:monospace;color:var(--text,#ccc)">${escapeHtml(cmd)}</pre>`
                : "";

            // Assemble detail block (everything below the header)
            // Season split (train/test)
            const trainSeasons = run.train_seasons || args.train_seasons || run.season_split?.train || null;
            const testSeasons = run.test_seasons || args.test_seasons || run.season_split?.test || null;
            let seasonSplitHtml = '';
            if (trainSeasons || testSeasons) {
                const z2 = appState.lang === 'zh';
                seasonSplitHtml = `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z2 ? '训练/测试赛季' : 'Train/Test seasons'}</p>`;
                seasonSplitHtml += `<div style="font-size:0.75rem;line-height:1.5">`;
                if (trainSeasons) {
                    const label = Array.isArray(trainSeasons) ? trainSeasons.join(', ') : String(trainSeasons);
                    seasonSplitHtml += `<div><span style="color:var(--text-muted)">${z2 ? '训练' : 'Train'}:</span> ${escapeHtml(label)}</div>`;
                }
                if (testSeasons) {
                    const label = Array.isArray(testSeasons) ? testSeasons.join(', ') : String(testSeasons);
                    seasonSplitHtml += `<div><span style="color:var(--text-muted)">${z2 ? '测试' : 'Test'}:</span> ${escapeHtml(label)}</div>`;
                }
                seasonSplitHtml += `</div>`;
            }

            // Feature importance top 5
            const featImp = run.feature_importance || run.feature_importances || args.feature_importance || null;
            let featImpHtml = '';
            if (featImp && typeof featImp === 'object') {
                const entries = Array.isArray(featImp)
                    ? featImp.slice(0, 5)
                    : Object.entries(featImp)
                        .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
                        .slice(0, 5)
                        .map(([k, v]) => ({ name: k, importance: v }));
                if (entries.length > 0) {
                    const z3 = appState.lang === 'zh';
                    featImpHtml = `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z3 ? '特征重要性 Top 5' : 'Feature importance Top 5'}</p>`;
                    featImpHtml += `<div style="font-size:0.75rem;line-height:1.6">`;
                    entries.forEach((e, i) => {
                        const name = typeof e === 'object' ? (e.name || e.feature || Object.keys(e)[0] || `f${i}`) : String(e);
                        const val = typeof e === 'object' ? (e.importance ?? e.value ?? Object.values(e)[0] ?? 0) : 0;
                        const pct = typeof val === 'number' && val <= 1 && val >= 0 ? (val * 100).toFixed(1) + '%' : Number(val).toFixed(3);
                        featImpHtml += `<div>\u25C6 ${escapeHtml(String(name))} <span style="color:var(--text-muted)">${escapeHtml(pct)}</span></div>`;
                    });
                    featImpHtml += `</div>`;
                }
            }

            const detailSections = [optTestHtml, baseTestHtml, optTrainHtml, baseTrainHtml, seasonSplitHtml, paramsHtml, featImpHtml, posHtml, errorHtml, cmdHtml]
                .filter(Boolean)
                .join("<hr style=\"border:none;border-top:1px solid var(--border,#333);margin:0.35rem 0\">");

            // Dependency versions
            const depVersions = run.dependency_versions || run.dependencies || args.dependency_versions || null;
            let depHtml = '';
            if (depVersions && typeof depVersions === 'object') {
                const z4 = appState.lang === 'zh';
                depHtml = `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z4 ? '依赖版本' : 'Dependency versions'}</p>`;
                depHtml += `<div style="font-size:0.75rem;line-height:1.5">`;
                for (const [k, v] of Object.entries(depVersions)) {
                    depHtml += `<div><span style="color:var(--text-muted)">${escapeHtml(k)}:</span> ${escapeHtml(String(v))}</div>`;
                }
                depHtml += `</div>`;
            }

            let lineageHtml = '';
            if (lineage && typeof lineage === 'object') {
                const z5 = appState.lang === 'zh';
                const stateLabel = lineageStatus === 'recorded'
                    ? (z5 ? '已记录' : 'Recorded')
                    : (z5 ? '未完整记录' : 'Not fully recorded');
                const manifestVersion = lineage.feature_manifest?.schema_version || '—';
                const manifestGenerated = lineage.feature_manifest?.generated_at || '—';
                lineageHtml = `<p style="margin:0.4rem 0 0.15rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z5 ? '数据血缘' : 'Data lineage'}</p>
                    <div style="font-size:0.75rem;line-height:1.5">
                        <div><span style="color:var(--text-muted)">${z5 ? '状态' : 'Status'}:</span> ${escapeHtml(stateLabel)}</div>
                        <div><span style="color:var(--text-muted)">${z5 ? '数据快照' : 'Dataset snapshot'}:</span> ${escapeHtml(String(snapshotHash || '—'))}</div>
                        <div><span style="color:var(--text-muted)">${z5 ? '特征清单' : 'Feature manifest'}:</span> ${escapeHtml(String(manifestHash || '—'))} · v${escapeHtml(String(manifestVersion))}</div>
                        <div><span style="color:var(--text-muted)">${z5 ? '生成时间' : 'Generated'}:</span> ${escapeHtml(String(manifestGenerated))}</div>
                    </div>`;
            }

            // Reproduce command for copy button
            const copyBtn = cmd
                ? `<button class="text-button" data-copy-cmd="${escapeAttr(cmd)}" style="font-size:0.72rem;padding:0.15rem 0.4rem;margin-left:0.3rem" title="${z ? '复制命令' : 'Copy command'}">\u25C6 ${z ? '复制' : 'Copy'}</button>`
                : '';

            const fullDetailSections = [lineageHtml, depHtml, detailSections].filter(Boolean)
                .join("<hr style=\"border:none;border-top:1px solid var(--border,#333);margin:0.35rem 0\">");

            const runIdx = run.run_id || `run_${Math.random().toString(36).slice(2, 8)}`;

            return `
            <div style="padding:0.6rem 0.8rem;border-bottom:1px solid var(--border,#333)">
                <div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap">
                    <strong style="font-size:0.85rem">${escapeHtml(run.run_id || "run")}</strong>
                    <span class="status-pill ${statusClass}">${statusText}</span>
                    ${spearman != null ? `<span style="font-size:0.78rem;color:var(--text-muted)">sp ${Number(spearman).toFixed(3)} / pr ${_fmtMetric(pearson)}</span>` : ""}
                    ${copyBtn}
                    ${fullDetailSections ? `<button class="text-button" data-toggle-run="${escapeAttr(runIdx)}" style="font-size:0.72rem;padding:0.15rem 0.4rem;margin-left:auto">\u25B6 ${z ? '展开详情' : 'Expand'}</button>` : ""}
                </div>
                <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.2rem;line-height:1.6">${detailParts.join(" · ")}</div>
                ${fullDetailSections ? `<div class="run-details-collapsed" data-run-details="${escapeAttr(runIdx)}" style="display:none;margin-top:0.35rem">${fullDetailSections}</div>` : ""}
            </div>`;
        }).join("")
        : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No model runs found</div>';

    // Data attribution panel
    _renderDataAttributionPanel();

    // Run comparison: populate selects
    _populateRunComparisonSelects();

    // Board Snapshots section
    var snapshotsList = document.getElementById("board-snapshots-list");
    var snapshotsCount = document.getElementById("board-snapshots-count");
    if (snapshotsList && typeof TACTICAL_BOARD !== "undefined") {
        var projects = TACTICAL_BOARD.listProjects();
        if (snapshotsCount) snapshotsCount.textContent = String(projects.length);
        snapshotsList.innerHTML = projects.length > 0
            ? projects.map(function(p) {
                var date = p.updated_at ? new Date(p.updated_at).toLocaleDateString() : "";
                var notes = "";
                try {
                    var full = TACTICAL_BOARD.loadProject(p.board_id);
                    if (full) {
                        var cp = full.coaching_points || (full.frames && full.frames[0] && full.frames[0].notes);
                        if (typeof cp === "string") notes = cp.slice(0, 80);
                        else if (cp && cp.title) notes = cp.title + (cp.description ? ": " + cp.description.slice(0, 50) : "");
                    }
                } catch (ex) { /* ignore */ }
                return '<div class="rank-item" data-load-board="' + escapeAttr(p.board_id) + '" style="cursor:pointer">' +
                    '<div>' +
                        '<strong style="font-size:0.85rem">' + escapeHtml(p.title || "Untitled") + '</strong>' +
                        '<span class="rank-meta">' + (p.object_count || 0) + ' objects, ' + (p.frame_count || 0) + ' frames' + (date ? ' \u00b7 ' + date : '') + '</span>' +
                        (notes ? '<span class="rank-meta" style="display:block;font-style:italic;opacity:0.7">' + escapeHtml(notes) + '</span>' : '') +
                    '</div>' +
                    '<span class="status-pill status-medium">Board</span>' +
                '</div>';
            }).join("")
            : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No board snapshots saved</div>';

        // Click handler: switch to tactical view and load project
        snapshotsList.querySelectorAll("[data-load-board]").forEach(function(el) {
            el.addEventListener("click", function() {
                var boardId = this.getAttribute("data-load-board");
                if (boardId && typeof switchView === "function") {
                    switchView("tactical");
                    var proj = TACTICAL_BOARD.loadProject(boardId);
                    if (proj && typeof TacticalRenderer !== "undefined") {
                        TacticalRenderer.project = proj;
                        TacticalRenderer.render();
                    }
                }
            });
        });
    }
}

function renderActions() {
    const chart = getChart("action-chart");
    const mode = appState.actionMode;
    const sourceRows = mode === "vaep"
        ? (actionValueSummary.vaep_players || [])
        : (actionValueSummary.xt_players || actionValueSummary.players || []);
    const metricKey = mode === "vaep" ? "vaep_per_90" : "xt_per_90";
    const legacyMetricKey = mode === "xt" ? "xT_per_90" : metricKey;
    const explorer = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER : null;
    populateActionFilters(sourceRows);
    const players = (explorer ? explorer.filterRows(sourceRows, {
        query: appState.actionQuery,
        competition: appState.actionCompetition,
        team: appState.actionTeam,
        season: appState.actionSeason,
        minimumMinutes: appState.actionMinMinutes,
    }) : sourceRows).sort((a, b) => Number(b[metricKey] ?? b[legacyMetricKey] ?? 0) - Number(a[metricKey] ?? a[legacyMetricKey] ?? 0));
    const actionList = document.getElementById("action-list");
    const actionStatus = document.getElementById("action-status-pill");
    const metrics = actionValueSummary.metrics || {};

    document.querySelectorAll("[data-action-mode]").forEach((button) => {
        const active = button.dataset.actionMode === mode;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    const chartTitle = document.getElementById("action-chart-title");
    const listTitle = document.getElementById("action-list-title");
    if (chartTitle) chartTitle.textContent = mode === "vaep" ? "VAEP / 90" : "xT / 90";
    if (listTitle) listTitle.textContent = mode === "vaep"
        ? (appState.lang === "zh" ? "VAEP 排名" : "VAEP ranking")
        : (appState.lang === "zh" ? "xT 排名" : "xT ranking");

    if (actionStatus) {
        actionStatus.textContent = actionValueSummary.status === "ok"
            ? `${mode.toUpperCase()} ${players.length}`
            : "NO DATA";
        actionStatus.className = `status-pill ${actionValueSummary.status === "ok" ? "status-medium" : "status-low"}`;
    }

    const metricsEl = document.getElementById("action-metrics");
    const identity = explorer
        ? explorer.identitySummary(actionValueSummary.identity_coverage, sourceRows)
        : { total: sourceRows.length, mapped: 0, unmapped: sourceRows.length, rate: 0 };
    if (metricsEl) {
        const rowCount = mode === "vaep"
            ? (metrics.vaep_rows ?? sourceRows.length)
            : (metrics.xt_rows ?? sourceRows.length);
        const coverage = mode === "vaep"
            ? `${(identity.rate * 100).toFixed(1)}%`
            : Number(metrics.players_with_xt ?? metrics.xt_rows ?? sourceRows.length).toLocaleString();
        const mean = mode === "vaep" ? metrics.mean_vaep_per_90 : metrics.mean_xt_per_90;
        metricsEl.innerHTML = `
            <div><span class="metric-value">${Number(rowCount || 0).toLocaleString()}</span><span>${escapeHtml(mode === "vaep" ? (appState.lang === "zh" ? "球员-球队生涯行" : "player-team career rows") : (appState.lang === "zh" ? "球员-球队-赛季行" : "player-team-season rows"))}</span></div>
            <div><span class="metric-value">${coverage}</span><span>${escapeHtml(mode === "vaep" ? (appState.lang === "zh" ? "身份完整映射" : "identity mapped") : "xT values")}</span></div>
            <div><span class="metric-value">${mean == null ? "–" : safeNum(mean, 3)}</span><span>${escapeHtml(appState.lang === "zh" ? "样本均值 / 90" : "sample mean / 90")}</span></div>`;
    }

    const identityNote = document.getElementById("action-identity-note");
    if (identityNote) {
        identityNote.hidden = mode !== "vaep";
        if (mode === "vaep") {
            const seasonNote = actionValueSummary.identity_coverage?.season_context_semantics
                || "Season labels are context only; VAEP is aggregated across each player-team career row.";
            identityNote.innerHTML = `<strong>${identity.mapped.toLocaleString()} / ${identity.total.toLocaleString()}</strong> ${escapeHtml(appState.lang === "zh" ? "行已补齐球员、球队和赛季上下文" : "rows have player, team, and season context")} · ${escapeHtml(appState.lang === "zh" ? "未映射" : "unmapped")} ${identity.unmapped.toLocaleString()}<span>${escapeHtml(seasonNote)}</span>`;
        }
    }

    const evidenceNote = document.getElementById("action-evidence-note");
    const evidenceIds = new Set(explorer
        ? explorer.evidencePlayerIds(actionValueEvidenceIndex)
        : (actionValueEvidenceIndex.available_player_ids || []).map(String));
    if (evidenceNote) {
        const evidenceCoverage = actionValueEvidenceIndex.coverage || {};
        const available = actionValueEvidenceIndex.status === "ok";
        evidenceNote.innerHTML = available
            ? `<strong>${Number(evidenceCoverage.match_count || 0).toLocaleString()}</strong> ${escapeHtml(appState.lang === "zh" ? "场可复现比赛证据" : "reproducible evidence matches")} · <strong>${evidenceIds.size.toLocaleString()}</strong> ${escapeHtml(appState.lang === "zh" ? "名球员可下钻" : "players available for drill-down")}<span>${escapeHtml(appState.lang === "zh" ? "仅限仓库内 StatsBomb 样例，点击带“比赛证据”标记的球员查看。" : "Tracked StatsBomb sample only. Open a player marked Match evidence.")}</span>`
            : `<strong>0</strong> ${escapeHtml(appState.lang === "zh" ? "场比赛证据可用" : "evidence matches available")}<span>${escapeHtml(appState.lang === "zh" ? "聚合排名仍可使用；比赛级样例未加载。" : "Aggregate rankings remain available; match sample is not loaded.")}</span>`;
    }

    actionList.innerHTML = players.length > 0
        ? players.map((player, index) => {
            const hasEvidence = evidenceIds.has(String(player.player_id || ""));
            return `
            <button class="rank-item action-rank-item" type="button" data-action-index="${index}" aria-label="${escapeAttr(`${actionPlayerLabel(player, mode)} details`)}">
                <div>
                    <strong>${escapeHtml(actionPlayerLabel(player, mode))}</strong>
                    <span class="rank-meta">${escapeHtml(actionPlayerMeta(player, mode))}</span>
                    ${hasEvidence ? `<span class="action-evidence-badge">${escapeHtml(appState.lang === "zh" ? "比赛证据" : "Match evidence")}</span>` : ""}
                    ${Number(player.estimated_minutes || player.minutes || 0) < 900 ? `<div class="sample-warning">${escapeHtml(appState.lang === "zh" ? "小样本，仅供研究" : "Small sample; research use only")}</div>` : ""}
                </div>
                <span class="status-pill status-medium">${safeNum(player[metricKey] ?? player[legacyMetricKey] ?? 0, 3)}</span>
            </button>
        `;
        }).join("")
        : (() => {
            const loadFailed = dataLoadErrors.has("action-values");
            const msg = loadFailed
                ? (appState.lang === "zh" ? "数据加载失败（API 和静态缓存均不可用）" : "Data load failed (both API and static cache unavailable)")
                : (appState.lang === "zh" ? "当前筛选没有动作价值样本" : "No action-value samples match the current filters");
            return `<div style="color:var(--text-muted);text-align:center;padding:1rem">${escapeHtml(msg)}</div>`;
        })();
    actionList.querySelectorAll("[data-action-index]").forEach((button) => {
        button.addEventListener("click", () => {
            const player = players[Number(button.dataset.actionIndex)];
            if (player) showActionValueDetail(player, mode);
        });
    });

    // StatsBomb Open Data attribution
    const attrEl = document.getElementById('action-attribution');
    if (attrEl) {
        const apiAttr = actionValueSummary.attribution_required
            || (appState.lang === 'zh' ? '公开展示时必须注明数据来源' : 'Data source must be attributed in any public display');
        attrEl.innerHTML = `\u25C6 ${appState.lang === 'zh' ? '\u6570\u636E\u6765\u6E90' : 'Data source'}: StatsBomb Open Data | github.com/statsbomb/open-data<br><small>${escapeHtml(apiAttr)}</small>`;
    }

    if (!chart) return;
    const chartPlayers = players.filter((player) => (player.player_name || player.player_id) && (player[metricKey] ?? player[legacyMetricKey]) != null).slice(0, 20);
    if (chartPlayers.length === 0) {
        chart.clear();
        return;
    }
    chart.setOption({
        title: {
            text: appState.lang === "zh" ? "真实 StatsBomb 样本 · 非全量联赛能力" : "Real StatsBomb sample · Not full-league coverage",
            left: "center", top: 0,
            textStyle: { color: "rgba(255,180,60,.85)", fontSize: 12, fontWeight: 400 },
        },
        grid: { left: 56, right: 20, top: 34, bottom: 60 },
        xAxis: {
            type: "category",
            data: chartPlayers.map((player) => actionPlayerLabel(player, mode)),
            axisLabel: { color: chartTextColor(), rotate: 30 },
        },
        yAxis: {
            type: "value",
            name: mode === "vaep" ? "VAEP/90" : "xT/90",
            nameTextStyle: { color: chartTextColor() },
            axisLabel: { color: chartTextColor() },
            splitLine: { lineStyle: { color: chartGridColor() } },
        },
        series: [{
            type: "bar",
            data: chartPlayers.map((player) => Number(player[metricKey] ?? player[legacyMetricKey] ?? 0)),
            itemStyle: { color: mode === "vaep" ? "rgba(124,168,255,.82)" : "rgba(87,214,141,.78)" },
            label: { show: false },
        }],
    }, true);
    chart.resize();

    // Wire up "Show on Tactical Board" button for xT heatmap
    const btnXTHeatmap = document.getElementById("btn-xt-heatmap-tactical");
    const heatmapStatus = document.getElementById("xt-heatmap-status");
    if (btnXTHeatmap) {
        btnXTHeatmap.disabled = mode !== "xt" || sourceRows.length === 0;
        btnXTHeatmap.onclick = function() {
            if (!actionValueSummary || actionValueSummary.status === "no_data") {
                if (heatmapStatus) heatmapStatus.textContent = appState.lang === "zh" ? "\u65e0\u6570\u636e" : "No data available";
                return;
            }
            // Generate xT heatmap grid from action value data (12x8 standard grid)
            var xtGrid = generateXTHeatmapGrid(actionValueSummary);
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.setXTHeatmapData(xtGrid);
                TacticalRenderer._showXTHeatmap = true;
                var toggleBtn = document.getElementById("tactical-toggle-heatmap");
                if (toggleBtn) toggleBtn.classList.add("active");
                // Update source_attribution to include StatsBomb when xT data is loaded
                if (tacticalProject && !String(tacticalProject.source_attribution || "").includes("StatsBomb")) {
                    tacticalProject.source_attribution = "ScoutFootball tactical board + StatsBomb Open Data (xT)";
                }
                // Navigate to tactical view
                setView("tactical");
                if (heatmapStatus) heatmapStatus.textContent = appState.lang === "zh" ? "\u5df2\u52a0\u8f7d" : "Loaded on tactical board";
            }
        };
    }
}

function setActionFilterOptions(selectId, values, previous, allLabel) {
    const select = document.getElementById(selectId);
    if (!select) return "ALL";
    const next = values.includes(previous) ? previous : "ALL";
    select.innerHTML = `<option value="ALL">${escapeHtml(allLabel)}</option>`
        + values.map((value) => `<option value="${escapeAttr(value)}">${escapeHtml(value)}</option>`).join("");
    select.value = next;
    return next;
}

function populateActionFilters(rows) {
    const options = typeof ACTION_VALUE_EXPLORER !== "undefined"
        ? ACTION_VALUE_EXPLORER.filterOptions(rows)
        : { competitions: [], teams: [], seasons: [] };
    appState.actionCompetition = setActionFilterOptions(
        "action-competition-filter",
        options.competitions,
        appState.actionCompetition,
        t("action_all_competitions"),
    );
    appState.actionTeam = setActionFilterOptions(
        "action-team-filter",
        options.teams,
        appState.actionTeam,
        appState.lang === "zh" ? "全部球队" : "All teams",
    );
    appState.actionSeason = setActionFilterOptions(
        "action-season-filter",
        options.seasons,
        appState.actionSeason,
        appState.lang === "zh" ? "全部赛季" : "All seasons",
    );
}

function actionPlayerLabel(player, mode) {
    if (player.player_name) return player.player_name;
    return mode === "vaep" ? `Player ID ${player.player_id || "–"}` : String(player.player_id || "–");
}

function actionPlayerMeta(player, mode) {
    const parts = [];
    const team = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER.rowTeam(player) : "";
    const seasons = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER.rowSeasons(player) : [];
    const competitions = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER.rowCompetitions(player) : [];
    if (team) parts.push(team);
    if (competitions.length) parts.push(competitions.join(" / "));
    if (seasons.length) parts.push(seasons.length > 2 ? `${seasons[0]}–${seasons[seasons.length - 1]} (${seasons.length})` : seasons.join(" / "));
    if (player.estimated_minutes != null) parts.push(`${Math.round(Number(player.estimated_minutes || 0))}min`);
    if (player.n_matches != null) parts.push(`${Number(player.n_matches).toFixed(Number(player.n_matches) % 1 ? 1 : 0)} matches`);
    if (mode === "xt" && player.xt_total != null) parts.push(`xT ${Number(player.xt_total).toFixed(2)}`);
    if (mode === "vaep" && player.vaep_total != null) parts.push(`VAEP ${Number(player.vaep_total).toFixed(2)}`);
    return parts.join(" \u00B7 ");
}

function showActionValueDetail(player, mode) {
    const dialog = document.getElementById("action-detail-dialog");
    const title = document.getElementById("action-detail-title");
    const kicker = document.getElementById("action-detail-kicker");
    const content = document.getElementById("action-detail-content");
    if (!dialog || !title || !content) return;

    const explorer = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER : null;
    const team = explorer ? explorer.rowTeam(player) : String(player.team_name || player.team_id || "–");
    const seasons = explorer ? explorer.rowSeasons(player) : [player.season].filter(Boolean);
    const competitions = explorer ? explorer.rowCompetitions(player) : [player.competition].filter(Boolean);
    const metric = mode === "vaep" ? player.vaep_per_90 : (player.xt_per_90 ?? player.xT_per_90);
    const total = mode === "vaep" ? player.vaep_total : player.xt_total;
    const identityStatus = player.identity_status || (player.player_name ? "mapped" : "unmapped");
    const facts = [
        [appState.lang === "zh" ? "球队" : "Team", team || "–"],
        [appState.lang === "zh" ? "赛季上下文" : "Season context", seasons.join(" · ") || "–"],
        [appState.lang === "zh" ? "赛事" : "Competition", competitions.join(" · ") || "–"],
        [appState.lang === "zh" ? "估算分钟" : "Estimated minutes", Math.round(Number(player.estimated_minutes || 0)).toLocaleString()],
        [appState.lang === "zh" ? "比赛" : "Matches", Number(player.n_matches || 0).toLocaleString()],
        [appState.lang === "zh" ? "动作" : "Actions", Number(player.n_actions || 0).toLocaleString()],
    ];
    if (kicker) kicker.textContent = mode === "vaep" ? "VAEP · player-team career" : "xT · player-team-season";
    title.textContent = actionPlayerLabel(player, mode);
    content.innerHTML = `
        <div class="action-detail-score">
            <div><span>${escapeHtml(`${mode === "vaep" ? "VAEP" : "xT"} / 90`)}</span><strong>${metric == null ? "–" : safeNum(metric, 3)}</strong></div>
            <div><span>${escapeHtml(appState.lang === "zh" ? "累计价值" : "Total value")}</span><strong>${total == null ? "–" : safeNum(total, 2)}</strong></div>
            <div><span>${escapeHtml(appState.lang === "zh" ? "身份状态" : "Identity")}</span><strong>${escapeHtml(identityStatus)}</strong></div>
        </div>
        <dl class="action-detail-facts">${facts.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
        <div class="action-detail-boundary">${escapeHtml(mode === "vaep"
            ? (appState.lang === "zh" ? "VAEP 按球员—球队生涯聚合；赛季仅用于说明底层覆盖范围，不能解释为单赛季 VAEP。" : "VAEP is aggregated by player-team career. Seasons describe source coverage and are not season-level VAEP values.")
            : (appState.lang === "zh" ? "xT 行对应一个球员—球队—赛季样本。" : "Each xT row represents a player-team-season sample."))}</div>
        <section class="action-evidence-section" aria-labelledby="action-context-title">
            <div class="action-evidence-head">
                <div><p class="eyebrow">Model context</p><h4 id="action-context-title">${escapeHtml(appState.lang === "zh" ? "跨模型研究档案" : "Cross-model research dossier")}</h4></div>
                <span class="status-pill status-medium" id="action-context-status">loading</span>
            </div>
            <div id="action-context-content" data-player-id="${escapeAttr(String(player.player_id || ""))}" aria-live="polite"><p class="action-evidence-message">${escapeHtml(appState.lang === "zh" ? "正在加载独立模型上下文..." : "Loading separate model contexts...")}</p></div>
        </section>
        <section class="action-evidence-section" aria-labelledby="action-rating-links-title">
            <div class="action-evidence-head">
                <div><p class="eyebrow">Rating reference</p><h4 id="action-rating-links-title">${escapeHtml(appState.lang === "zh" ? "评分记录候选" : "Rating-record candidates")}</h4></div>
                <span class="status-pill status-medium" id="action-rating-links-status">loading</span>
            </div>
            <div id="action-rating-links-content" data-player-id="${escapeAttr(String(player.player_id || ""))}" aria-live="polite"><p class="action-evidence-message">${escapeHtml(appState.lang === "zh" ? "正在核对姓名、球队和赛季..." : "Checking name, team, and season...")}</p></div>
        </section>
        <section class="action-evidence-section" aria-labelledby="action-evidence-title">
            <div class="action-evidence-head">
                <div><p class="eyebrow">StatsBomb sample evidence</p><h4 id="action-evidence-title">${escapeHtml(appState.lang === "zh" ? "比赛级 xT 证据" : "Match-level xT evidence")}</h4></div>
                <span class="status-pill status-medium" id="action-evidence-status">loading</span>
            </div>
            <div id="action-evidence-content" data-player-id="${escapeAttr(String(player.player_id || ""))}" aria-live="polite"><p class="action-evidence-message">${escapeHtml(appState.lang === "zh" ? "正在加载比赛证据..." : "Loading match evidence...")}</p></div>
        </section>`;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    void renderActionValuePlayerContext(player);
    void renderActionValueRatingLinks(player);
    void renderActionValueEvidence(player);
}

function actionContextRows(title, rows, metricKey, contextKey) {
    const items = Array.isArray(rows) ? rows : [];
    if (!items.length) return `<section class="action-evidence-breakdown"><h5>${escapeHtml(title)}</h5><p class="action-evidence-message">–</p></section>`;
    return `<section class="action-evidence-breakdown"><h5>${escapeHtml(title)}</h5>${items.map((row) => {
        const team = row.team_name || (row.team_id ? `Team ID ${row.team_id}` : "–");
        const context = row[contextKey] || row.season || "–";
        return `<div class="action-evidence-breakdown-row"><span>${escapeHtml(team)} <small>${escapeHtml(String(context))}</small></span><strong>${safeNum(row[metricKey] || 0, 3)} / 90</strong></div>`;
    }).join("")}</section>`;
}

async function downloadActionValueContext(data, player = {}) {
    const shortlistContext = getShortlistDossier(player);
    const ratingLinks = await fetchActionValueRatingLinks(String(player.player_id || data.player_id || ""));
    const payload = {
        schema: "scoutfootball.action-value-research-dossier-export",
        version: "1.1.0",
        exported_at: new Date().toISOString(),
        storage_scope: "browser-local-download",
        action_value_context: data,
        scouting_context: {
            scope: "browser-local-shortlist-dossier",
            player_key: scoutingPlayerKey(player),
            in_shortlist: isInPlayerShortlist(scoutingPlayerKey(player)),
            dossier: shortlistContext,
            non_additive_to_action_values: true,
        },
        rating_reference: {
            scope: "strict-name-team-season-candidates",
            status: ratingLinks?.status || "rating_artifact_unavailable",
            candidates: Array.isArray(ratingLinks?.rating_candidates) ? ratingLinks.rating_candidates : [],
            non_additive_to_action_values: true,
            requires_human_identity_verification: true,
        },
        limitations: [
            "xT, VAEP, and match-sample values retain their own granularities and are not additive.",
            "Scouting context is browser-local decision context, not a model feature or server-side recommendation.",
            "Rating references are strict identity candidates, not confirmed links or a merged scoring signal.",
        ],
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `action-value-context-${String(data.player_id || "player")}.json`;
    link.click();
    URL.revokeObjectURL(url);
}

async function renderActionValuePlayerContext(player) {
    const target = document.getElementById("action-context-content");
    const status = document.getElementById("action-context-status");
    const playerId = String(player.player_id || "");
    if (!target || !playerId) return;
    const data = await fetchActionValuePlayerContext(playerId);
    if (target.dataset.playerId !== playerId) return;
    const xtRows = data?.models?.xt?.rows || [];
    const vaepRows = data?.models?.vaep?.rows || [];
    const matchRows = data?.match_sample?.rows || [];
    if (data?.status !== "ok") {
        target.innerHTML = `<div class="action-detail-boundary">${escapeHtml(appState.lang === "zh" ? "未找到该球员的跨模型上下文；当前排名仍保持原始模型粒度。" : "No cross-model context was found; rankings retain their original model granularity.")}</div>`;
        if (status) { status.textContent = "N/A"; status.className = "status-pill status-low"; }
        return;
    }
    const reason = data.comparability?.reason || "These values are not additive or directly comparable.";
    target.innerHTML = `
        <div class="action-detail-boundary"><strong>${escapeHtml(appState.lang === "zh" ? "不可合并比较" : "Non-additive comparison")}</strong> · ${escapeHtml(reason)}</div>
        <div class="action-evidence-breakdown-grid">
            ${actionContextRows("xT · player-team-season", xtRows, "xt_per_90", "season")}
            ${actionContextRows("VAEP · player-team-career", vaepRows, "vaep_per_90", "season_context")}
        </div>
        <div class="action-evidence-scope"><strong>${matchRows.length}</strong> ${escapeHtml(appState.lang === "zh" ? "场版本化比赛样例" : "versioned match samples")}<span>${escapeHtml(appState.lang === "zh" ? "比赛级 xT 使用独立样例网格，不能与上方聚合数值相加。" : "Match-level xT uses a separate sample grid and is not additive with aggregate values.")}</span></div>
        <button class="text-button" id="action-context-export" type="button">${escapeHtml(appState.lang === "zh" ? "导出研究档案 JSON" : "Export research dossier JSON")}</button>`;
    target.querySelector("#action-context-export")?.addEventListener("click", () => downloadActionValueContext(data, player));
    if (status) { status.textContent = "READY"; status.className = "status-pill status-high"; }
}

function openActionValueRatingCandidate(candidate) {
    const linked = players.find((row) => row.name === candidate.player
        && row.team === candidate.team && row.season === candidate.season);
    if (!linked) return;
    appState.selectedPlayerKey = linked.key;
    void setView("players");
}

async function renderActionValueRatingLinks(player) {
    const target = document.getElementById("action-rating-links-content");
    const status = document.getElementById("action-rating-links-status");
    const playerId = String(player.player_id || "");
    if (!target || !playerId) return;
    const data = await fetchActionValueRatingLinks(playerId);
    if (target.dataset.playerId !== playerId) return;
    const candidates = Array.isArray(data?.rating_candidates) ? data.rating_candidates : [];
    const boundary = appState.lang === "zh"
        ? "候选仅由规范化姓名、球队和赛季一致产生；StatsBomb 与评分产物没有共享的稳定球员 ID，必须人工核验。"
        : "Candidates require normalized name, team, and season agreement. StatsBomb and rating artifacts have no shared stable player ID, so human verification remains required.";
    if (data?.status !== "candidate_available" || candidates.length === 0) {
        target.innerHTML = `<div class="action-detail-boundary">${escapeHtml(boundary)}<br>${escapeHtml(appState.lang === "zh" ? "当前没有严格评分候选；不会按姓名单独推断关联。" : "No strict rating candidate is available; name-only links are not inferred.")}</div>`;
        if (status) { status.textContent = "NO LINK"; status.className = "status-pill status-low"; }
        return;
    }
    const rows = candidates.map((candidate, index) => {
        const loaded = players.some((row) => row.name === candidate.player
            && row.team === candidate.team && row.season === candidate.season);
        return `<div class="action-evidence-breakdown-row"><span>${escapeHtml(candidate.player)} <small>${escapeHtml(`${candidate.team} · ${candidate.season} · ${candidate.league || ""}`)}</small></span><strong>${escapeHtml(String(Number(candidate.optimized_score || 0).toFixed(1)))}</strong>${loaded ? `<button class="text-button" type="button" data-action-rating-candidate="${index}">${escapeHtml(appState.lang === "zh" ? "打开评分画像" : "Open rating profile")}</button>` : ""}</div>`;
    }).join("");
    target.innerHTML = `<div class="action-detail-boundary">${escapeHtml(boundary)}</div><div class="action-evidence-breakdown"><h5>${escapeHtml(appState.lang === "zh" ? "严格候选（非确认身份）" : "Strict candidates (not confirmed identities)")}</h5>${rows}</div>`;
    target.querySelectorAll("[data-action-rating-candidate]").forEach((button) => {
        button.addEventListener("click", () => openActionValueRatingCandidate(candidates[Number(button.dataset.actionRatingCandidate)]));
    });
    if (status) { status.textContent = "CANDIDATE"; status.className = "status-pill status-medium"; }
}

function actionEvidenceBreakdown(title, rows) {
    const items = Array.isArray(rows) ? rows : [];
    return `<section class="action-evidence-breakdown"><h5>${escapeHtml(title)}</h5>${items.length
        ? items.map((row) => {
            const label = String(row.key || "unknown").replaceAll("_", " ");
            const value = Number(row.xt_total || 0);
            return `<div class="action-evidence-breakdown-row"><span>${escapeHtml(label)} <small>${Number(row.n_actions || 0).toLocaleString()}</small></span><strong class="${value >= 0 ? "positive" : "negative"}">${value >= 0 ? "+" : ""}${safeNum(value, 3)}</strong></div>`;
        }).join("")
        : `<p class="action-evidence-message">–</p>`}</section>`;
}

function renderPlayerMatchValueRows(playerId) {
    const explorer = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER : null;
    const rows = explorer
        ? explorer.playerMatchRows(actionValueMatchSummary.rows, playerId)
        : (actionValueMatchSummary.rows || []).filter(
            (row) => String(row.player_id || "") === String(playerId)
        );
    const manifest = actionValueMatchSummary.manifest || {};
    if (actionValueMatchSummary.status !== "ok") {
        return `<div class="action-detail-boundary">${escapeHtml(
            "The versioned player-match xT artifact is not loaded; match evidence remains available."
        )}</div>`;
    }
    if (!rows.length) return "";
    const scope = manifest.coverage_scope || "sample";
    return `<section class="action-evidence-versioned" aria-label="Versioned player match xT">
        <div class="action-evidence-head"><div><p class="eyebrow">Versioned player-match xT</p><h5>Match context and value rows</h5></div><span class="status-pill status-medium">${escapeHtml(scope.toUpperCase())}</span></div>
        <p class="action-evidence-message">Current three-match StatsBomb sample only; not full competition coverage and not additive with differently scoped xT grids.</p>
        <div class="action-evidence-match-grid">${rows.map((row) => {
            const score = row.home_score == null || row.away_score == null
                ? ""
                : ` ${row.home_score}-${row.away_score}`;
            const fixture = `${row.home_team_name || "Home"} v ${row.away_team_name || "Away"}${score}`;
            return `<article class="action-evidence-match-card"><div><strong>${escapeHtml(row.match_date || `Match ${row.match_id || ""}`)}</strong><span>${escapeHtml(fixture)}</span></div><div class="action-evidence-match-score"><span>xT / 90</span><strong>${safeNum(row.xt_per_90 || 0, 3)}</strong></div><dl><div><dt>xT</dt><dd>${safeNum(row.xt_total || 0, 3)}</dd></div><div><dt>actions</dt><dd>${Number(row.n_actions || 0)}</dd></div><div><dt>minutes</dt><dd>${Math.round(Number(row.estimated_minutes || 0))}</dd></div></dl></article>`;
        }).join("")}</div></section>`;
}

async function renderActionValueEvidence(player) {
    const target = document.getElementById("action-evidence-content");
    const status = document.getElementById("action-evidence-status");
    const playerId = String(player.player_id || "");
    if (!target || !playerId) {
        if (target) target.innerHTML = `<p class="action-evidence-message">${escapeHtml(appState.lang === "zh" ? "缺少球员 ID，无法匹配比赛证据。" : "Player ID is missing; evidence cannot be matched.")}</p>`;
        if (status) status.textContent = "N/A";
        return;
    }

    const data = await fetchActionValueEvidence(playerId);
    if (target.dataset.playerId !== playerId) return;
    const coverage = data && data.coverage ? data.coverage : {};
    if (!data || data.status !== "ok") {
        target.innerHTML = `<div class="action-detail-boundary">${escapeHtml(appState.lang === "zh" ? `当前仓库仅有 ${Number(coverage.match_count || 0)} 场比赛级样例，该球员不在样例中；上方聚合值仍来自更广的 StatsBomb 产物。` : `The repository contains ${Number(coverage.match_count || 0)} match-level samples and this player is not present. The aggregate value above comes from the broader StatsBomb artifact.`)}</div>`;
        if (status) {
            status.textContent = "NO MATCH";
            status.className = "status-pill status-low";
        }
        return;
    }

    const matches = Array.isArray(data.matches) ? data.matches : [];
    const explorer = typeof ACTION_VALUE_EXPLORER !== "undefined" ? ACTION_VALUE_EXPLORER : null;
    const actionTypes = explorer ? explorer.coreActionTypes(data) : (data.action_types || []);
    const matchCards = matches.map((match) => `
        <article class="action-evidence-match-card">
            <div><strong>${escapeHtml(match.match_label || `Match ${match.match_id}`)}</strong><span>${escapeHtml(match.team_name || "–")} · ID ${escapeHtml(String(match.match_id || "–"))}</span></div>
            <div class="action-evidence-match-score"><span>xT</span><strong>${safeNum(match.xt_total || 0, 3)}</strong></div>
            <dl><div><dt>pass</dt><dd>${Number(match.n_pass || 0)} / ${safeNum(match.xt_pass || 0, 3)}</dd></div><div><dt>carry</dt><dd>${Number(match.n_carry || 0)} / ${safeNum(match.xt_carry || 0, 3)}</dd></div><div><dt>shot</dt><dd>${Number(match.n_shot || 0)} / ${safeNum(match.xt_shot || 0, 3)}</dd></div></dl>
        </article>`).join("");
    const topActions = (Array.isArray(data.top_actions) ? data.top_actions : []).slice(0, 8);
    const topActionsHtml = topActions.length
        ? `<div class="table-scroll action-evidence-table-scroll"><table class="action-evidence-table"><thead><tr><th>${escapeHtml(appState.lang === "zh" ? "时间" : "Time")}</th><th>${escapeHtml(appState.lang === "zh" ? "动作" : "Action")}</th><th>xT</th><th>${escapeHtml(appState.lang === "zh" ? "坐标" : "Coordinates")}</th></tr></thead><tbody>${topActions.map((action) => `<tr><td>${Number(action.minute || 0)}:${String(Number(action.second || 0)).padStart(2, "0")}</td><td>${escapeHtml(action.action_type || "–")}<span class="rank-meta">${escapeHtml(action.match_label || action.match_id || "")}</span></td><td><strong>${Number(action.xt_delta || 0) >= 0 ? "+" : ""}${safeNum(action.xt_delta || 0, 4)}</strong></td><td>${safeNum(action.start_x || 0, 0)},${safeNum(action.start_y || 0, 0)} → ${safeNum(action.end_x || 0, 0)},${safeNum(action.end_y || 0, 0)}</td></tr>`).join("")}</tbody></table></div>`
        : `<p class="action-evidence-message">${escapeHtml(appState.lang === "zh" ? "没有可展示的动作。" : "No actions available.")}</p>`;

    target.innerHTML = `
        <div class="action-evidence-scope"><strong>${matches.length}</strong> ${escapeHtml(appState.lang === "zh" ? "场比赛" : "matches")} · <strong>${Number(data.n_actions || 0).toLocaleString()}</strong> ${escapeHtml(appState.lang === "zh" ? "个动作" : "actions")} · xT ${safeNum(data.xt_total || 0, 3)}<span>${escapeHtml(coverage.scope_note || "StatsBomb Open Data sample only")}</span></div>
        ${renderPlayerMatchValueRows(playerId)}
        <div class="action-evidence-match-grid">${matchCards}</div>
        <div class="action-evidence-breakdown-grid">
            ${actionEvidenceBreakdown(appState.lang === "zh" ? "动作类型" : "Action types", actionTypes)}
            ${actionEvidenceBreakdown(appState.lang === "zh" ? "终点区域" : "Destination zones", data.zones)}
            ${actionEvidenceBreakdown(appState.lang === "zh" ? "时间段" : "Time buckets", data.time_buckets)}
        </div>
        <div class="action-evidence-top"><h5>${escapeHtml(appState.lang === "zh" ? "高价值动作" : "Highest-value actions")}</h5>${topActionsHtml}</div>`;
    if (status) {
        status.textContent = `${matches.length} MATCH`;
        status.className = "status-pill status-high";
    }
}

function generateXTHeatmapGrid(summary) {
    // Standard StatsBomb xT grid: 12 columns (length) x 8 rows (width)
    var defaultXT = [
        [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00],
        [0.00, 0.00, 0.00, 0.00, 0.01, 0.01, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06],
        [0.00, 0.00, 0.00, 0.01, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.14, 0.18],
        [0.00, 0.00, 0.01, 0.01, 0.02, 0.04, 0.06, 0.09, 0.14, 0.20, 0.28, 0.35],
        [0.00, 0.00, 0.01, 0.01, 0.02, 0.04, 0.06, 0.09, 0.14, 0.20, 0.28, 0.35],
        [0.00, 0.00, 0.00, 0.01, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.14, 0.18],
        [0.00, 0.00, 0.00, 0.00, 0.01, 0.01, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06],
        [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00],
    ];
    if (summary && summary.metrics && summary.metrics.mean_xt_per_90) {
        var meanXT = summary.metrics.mean_xt_per_90;
        var scaleFactor = meanXT / 0.06;
        for (var r = 0; r < defaultXT.length; r++) {
            for (var c = 0; c < defaultXT[r].length; c++) {
                defaultXT[r][c] = defaultXT[r][c] * scaleFactor;
            }
        }
    }
    return defaultXT;
}

function refreshAllChartColors() {
    // Re-render all active charts with updated theme colors
    Object.keys(appState.charts).forEach((id) => {
        const element = document.getElementById(id);
        if (!element || element.offsetParent === null) return; // Skip hidden charts
        const chart = appState.charts[id];
        if (!chart) return;
        
        // Re-render based on chart type
        switch(id) {
            case "radar-chart": {
                const player = players.find((item) => item.key === appState.selectedPlayerKey) || players[0];
                if (player) renderRadar(player);
                break;
            }
            case "value-chart":
                renderValue();
                break;
            case "score-chart":
                renderScoreMatrix(selectedMatch());
                break;
            case "outcome-bar-chart":
                renderOutcomeBar(selectedMatch());
                break;
            case "compare-radar-chart":
                renderComparePanel();
                break;
            case "action-chart":
                renderActions();
                break;
        }
    });
}

function renderLicense() {
    const tbody = document.getElementById("license-table-body");
    if (!tbody) return;

    const attribution = licenseData.license_attribution || {};
    const rows = LICENSE_SOURCES.map((src) => {
        const desc = attribution[src.key] || "";
        return `<tr>
            <td>${escapeHtml(src.name)}</td>
            <td>${escapeHtml(src.license)}</td>
            <td>${escapeHtml(desc || src.attribution)}</td>
            <td><a href="${escapeAttr(src.url)}" target="_blank" rel="noopener" style="color:var(--accent)">${escapeHtml(src.url)}</a></td>
        </tr>`;
    }).join("");
    tbody.innerHTML = rows || '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">' + (appState.lang === "zh" ? "无数据" : "No data") + "</td></tr>";

    const timestamp = formatTimestamp(licenseData.updated_at);
    const updatedPill = document.getElementById("license-updated");
    if (updatedPill) {
        updatedPill.textContent = timestamp
            ? timestamp
            : (appState.lang === "zh" ? "无时间戳" : "No timestamp");
    }

    const updatedText = document.getElementById("license-last-updated");
    if (updatedText) {
        updatedText.textContent = timestamp
            ? (appState.lang === "zh" ? "最后更新: " : "Last updated: ") + timestamp
            : "";
    }
}

// ── Data Status Page ──────────────────────────────────────────────

function _classifyArtifact(name) {
    if (/statsbomb|events_all/.test(name)) return "real";
    if (/truth_labels|oof/.test(name)) return "real";
    if (/player_match|season_proxy/.test(name)) return "proxy";
    if (/team_match/.test(name)) return "real";
    if (/ratings/.test(name)) return "real";
    return "synthetic";
}

function renderData() {
    const artifacts = artifactSummary.artifacts || [];
    const health = artifactSummary.data_health || {};
    const licenses = artifactSummary.license_attribution || {};

    // Data sources table
    const sourcesTbody = document.getElementById("data-sources-table");
    if (sourcesTbody) {
        let totalRows = 0;
        let sourceCount = 0;
        const rows = artifacts.map(a => {
            const rows = a.rows || 0;
            totalRows += rows;
            if (rows > 0) sourceCount++;
            const srcType = _classifyArtifact(a.label || a.name || "");
            const typeLabel = srcType === "real" ? t("data_type_real") : (srcType === "proxy" ? t("data_type_proxy") : t("data_type_synthetic"));
            const typeCls = srcType === "real" ? "status-high" : (srcType === "proxy" ? "status-medium" : "status-low");
            const modified = a.updated_at ? new Date(a.updated_at * 1000).toISOString().slice(0, 10) : "–";
            return `<tr>
                <td>${escapeHtml(a.label || a.name || "–")}</td>
                <td>${rows.toLocaleString()}</td>
                <td>${escapeHtml(modified)}</td>
                <td><span class="status-pill ${typeCls}">${escapeHtml(typeLabel)}</span></td>
            </tr>`;
        }).join("");
        sourcesTbody.innerHTML = rows || '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">' + (appState.lang === "zh" ? "无数据" : "No data") + "</td></tr>";

        // Update summary metrics
        const totalEl = document.getElementById("data-total-rows");
        if (totalEl) totalEl.textContent = totalRows.toLocaleString();
        const countEl = document.getElementById("data-source-count");
        if (countEl) countEl.textContent = String(sourceCount);
    }

    // Coverage by league-season
    const coverageTbody = document.getElementById("data-coverage-table");
    if (coverageTbody) {
        const byLeagueSeason = {};
        for (const p of players) {
            const league = p.league || "";
            const season = p.season || "";
            if (!league) continue;
            const key = `${league}|${season}`;
            if (!byLeagueSeason[key]) byLeagueSeason[key] = { league, season, teams: new Set(), rated: 0, total: 0 };
            byLeagueSeason[key].teams.add(p.team);
            byLeagueSeason[key].total++;
            if (p.rating > 0) byLeagueSeason[key].rated++;
        }
        // Compute per-unique-team coverage
        const byLeagueSeasonAgg = {};
        for (const p of players) {
            const league = p.league || "";
            const season = p.season || "";
            if (!league) continue;
            const key = `${league}|${season}`;
            if (!byLeagueSeasonAgg[key]) byLeagueSeasonAgg[key] = { league, season, teams: new Set(), ratedTeams: new Set() };
            byLeagueSeasonAgg[key].teams.add(p.team);
            if (p.rating > 0) byLeagueSeasonAgg[key].ratedTeams.add(p.team);
        }
        const coverageRows = Object.values(byLeagueSeasonAgg).sort((a, b) => {
            if (a.league !== b.league) return a.league.localeCompare(b.league);
            return a.season.localeCompare(b.season);
        }).map(entry => {
            const total = entry.teams.size;
            const rated = entry.ratedTeams.size;
            const pct = total > 0 ? rated / total : 0;
            const pctColor = pct > 0.90 ? "status-high" : (pct >= 0.70 ? "status-medium" : "status-low");
            const pctLabel = pct > 0.90 ? "HIGH" : (pct >= 0.70 ? "MED" : "LOW");
            return `<tr>
                <td>${escapeHtml(entry.league)}</td>
                <td>${escapeHtml(entry.season)}</td>
                <td>${rated}</td>
                <td>${total}</td>
                <td><span class="status-pill ${pctColor}">${Math.round(pct * 100)}% ${pctLabel}</span></td>
            </tr>`;
        }).join("");
        coverageTbody.innerHTML = coverageRows || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">' + (appState.lang === "zh" ? "无数据" : "No data") + "</td></tr>";
    }

    // Missing data warnings
    const warningsEl = document.getElementById("data-missing-warnings");
    if (warningsEl) {
        const warnings = [];
        if (!health.oof_available) warnings.push(appState.lang === "zh" ? "OOF 预测数据缺失" : "OOF prediction data missing");
        if (!health.truth_labels_available) warnings.push(appState.lang === "zh" ? "真实标签数据缺失" : "Truth labels data missing");
        if (!health.player_match_coverage) warnings.push(appState.lang === "zh" ? "球员比赛级覆盖不足" : "Player match-level coverage is thin");

        // Check for leagues with low coverage
        const leagueCov = computeLeagueCoverage();
        for (const lc of leagueCov) {
            if (lc.coverage < 0.70) {
                warnings.push((appState.lang === "zh" ? "联赛 " : "League ") + escapeHtml(lc.league) + (appState.lang === "zh" ? " 覆盖率过低: " : " coverage too low: ") + Math.round(lc.coverage * 100) + "%");
            }
        }

        if (warnings.length === 0) {
            warningsEl.innerHTML = '<li class="health-item"><span class="dot status-high"></span><span>' + escapeHtml(t("data_no_missing")) + '</span></li>';
        } else {
            warningsEl.innerHTML = warnings.map(w =>
                `<li class="health-item"><span class="dot status-low"></span><span>${w}</span></li>`
            ).join("");
        }
    }
}

async function renderActiveView() {
    if (appState.view === "overview") renderOverview();
    if (appState.view === "players") await renderPlayers();
    if (appState.view === "compare") await renderCompare();
    if (appState.view === "value") renderValue();
    if (appState.view === "matches") await renderMatches();
    if (appState.view === "teams") await renderTeams();
    if (appState.view === "scouting") renderScouting();
    if (appState.view === "actions") renderActions();
    if (appState.view === "reports") renderReports();
    if (appState.view === "tactical") renderTactical();
    if (appState.view === "wc_schedule") renderWcSchedule();
    if (appState.view === "wc_squads") renderWcSquads();
    if (appState.view === "wc_compare") renderWcCompare();
    if (appState.view === "wc_probability") renderWcProbability();
    if (appState.view === "wc_knockout") renderWcKnockout();
    if (appState.view === "wc_tournament") {
        // Lazy-load tournament data on first view, then render
        if (!wcApiData.tournament) {
            loadAndRenderWcTournament();
        } else {
            renderWcTournament();
        }
    }
    if (appState.view === "license") renderLicense();
    if (appState.view === "data") renderData();
    if (appState.view === "calibration") renderCalibration();
    if (appState.view === "backtest") renderBacktest();
    // Resize charts after layout paint to ensure correct dimensions
    requestAnimationFrame(() => {
        Object.values(appState.charts).forEach((chart) => {
            try { chart.resize(); } catch(e) { /* ignore disposed charts */ }
        });
    });
}

async function renderCalibration() {
    const statusPill = document.getElementById("calibration-status");
    try {
        const data = Object.keys(predictionCalibration).length > 0
            ? predictionCalibration
            : await fetchPredictionCalibration();
        predictionCalibration = data;

        // Status
        const dcStatus = data.dixon_coles ? data.dixon_coles.status : "not_available";
        if (statusPill) {
            statusPill.textContent = dcStatus === "ok" ? "DC: OK" : dcStatus;
            statusPill.className = `status-pill ${dcStatus === "ok" ? "status-high" : "status-medium"}`;
        }

        // Metrics summary
        const metricsEl = document.getElementById("calibration-metrics");
        if (metricsEl) {
            const dc = data.dixon_coles || {};
            const poisson = data.poisson || {};
            const zT = appState.lang === "zh";
            let html = '<div class="detail-grid">';
            if (dc.status === "ok") {
                html += `<div><span>${zT ? "DC 对数损失" : "DC Log Loss"}</span><strong>${escapeHtml(String(dc.log_loss_exact))}</strong></div>`;
                html += `<div><span>${zT ? "DC Brier" : "DC Brier 1x2"}</span><strong>${escapeHtml(String(dc.brier_1x2))}</strong></div>`;
                html += `<div><span>${zT ? "DC RPS" : "DC RPS"}</span><strong>${escapeHtml(String(dc.rps_1x2))}</strong></div>`;
                html += `<div><span>${zT ? "DC 场次" : "DC matches"}</span><strong>${escapeHtml(String(dc.n_matches))}</strong></div>`;
            }
            if (poisson.status === "ok") {
                html += `<div><span>${zT ? "Poisson 对数损失" : "Poisson Log Loss"}</span><strong>${escapeHtml(String(poisson.log_loss_exact || "–"))}</strong></div>`;
                html += `<div><span>${zT ? "Poisson Brier" : "Poisson Brier"}</span><strong>${escapeHtml(String(poisson.brier_1x2 || "–"))}</strong></div>`;
            }
            html += '</div>';
            metricsEl.innerHTML = html;
        }

        // Calibration plot (predicted vs actual home-win)
        const calPlot = data.calibration_plot || [];
        const chartEl = document.getElementById("calibration-plot-chart");
        if (chartEl && calPlot.length > 0 && typeof echarts !== "undefined") {
            const chart = getChart("calibration-plot-chart");
            chart.setOption({
                tooltip: { trigger: "axis" },
                xAxis: { type: "value", name: "Predicted", min: 0, max: 1 },
                yAxis: { type: "value", name: "Actual", min: 0, max: 1 },
                series: [
                    { type: "line", data: [[0, 0], [1, 1]], lineStyle: { type: "dashed", color: "#888" }, symbol: "none", silent: true },
                    {
                        type: "scatter",
                        data: calPlot.map(p => [p.mean_predicted, p.mean_actual]),
                        symbolSize: calPlot.map(p => Math.max(8, Math.sqrt(p.n_matches) * 3)),
                        itemStyle: { color: "#4a90d9" },
                        label: { show: false },
                    },
                ],
                grid: { left: 50, right: 20, top: 30, bottom: 40 },
            });
        }

        // Low score breakdown
        const lowScoreEl = document.getElementById("calibration-low-score");
        if (lowScoreEl) {
            const buckets = data.low_score_breakdown || [];
            if (buckets.length === 0) {
                lowScoreEl.innerHTML = `<div style="padding:0.5rem;color:var(--text-muted)">${escapeHtml(appState.lang === "zh" ? "无数据" : "No data")}</div>`;
            } else {
                lowScoreEl.innerHTML = buckets.map(b =>
                    `<div class="rank-item" style="display:flex;justify-content:space-between;padding:4px 8px;font-size:0.82rem">
                        <span>${escapeHtml(b.score_bucket)}</span>
                        <span>${escapeHtml(String(b.n_matches))} ${escapeHtml(appState.lang === "zh" ? "场" : "matches")}</span>
                        <span>${escapeHtml(appState.lang === "zh" ? "实际" : "Actual")}: ${escapeHtml(String(b.actual_pct))}%</span>
                        <span>${escapeHtml(appState.lang === "zh" ? "预测" : "Pred")}: ${escapeHtml(String(b.mean_predicted_pct))}%</span>
                        <span style="color:${b.calibration_error > 5 ? '#ff6b6b' : '#57d68d'}">${escapeHtml(String(b.calibration_error))}% err</span>
                    </div>`
                ).join("");
            }
        }

        // Per-league calibration
        const leagueEl = document.getElementById("calibration-league");
        if (leagueEl) {
            const leagues = data.league_coverage || [];
            if (leagues.length === 0) {
                leagueEl.innerHTML = `<div style="padding:0.5rem;color:var(--text-muted)">${escapeHtml(appState.lang === "zh" ? "无数据" : "No data")}</div>`;
            } else {
                leagueEl.innerHTML = leagues.map(l =>
                    `<div class="rank-item" style="display:flex;justify-content:space-between;padding:4px 8px;font-size:0.82rem">
                        <span>${escapeHtml(l.league)}</span>
                        <span>${escapeHtml(String(l.n_matches))} ${escapeHtml(appState.lang === "zh" ? "场" : "matches")}</span>
                        <span>${escapeHtml(appState.lang === "zh" ? "对数损失" : "LogLoss")}: ${escapeHtml(String(l.mean_log_loss))}</span>
                        <span>Brier: ${escapeHtml(String(l.mean_brier))}</span>
                    </div>`
                ).join("");
            }
        }

        // Brier decomposition
        const brierEl = document.getElementById("calibration-brier");
        if (brierEl && data.dixon_coles && data.dixon_coles.status === "ok") {
            const dc = data.dixon_coles;
            brierEl.innerHTML = `<p style="font-size:0.72rem;color:var(--text-muted);margin:0.3rem 0">
                Brier 1x2: ${escapeHtml(String(dc.brier_1x2))} | RPS: ${escapeHtml(String(dc.rps_1x2))} | n=${escapeHtml(String(dc.n_matches))}
            </p>`;
        }
    } catch (err) {
        if (statusPill) {
            statusPill.textContent = "error";
            statusPill.className = "status-pill status-low";
        }
        console.warn("Failed to fetch calibration:", err);
    }
}

// ── Backtest Comparison ─────────────────────────────────────────────────

let backtestComparisonData = null;
let decayTuningData = null;
let calibrationDriftData = null;
let ensembleWeightsData = null;
let calibrationComparisonData = null;

async function fetchBacktestComparison() {
    try {
        return await fetchJson("/predictions/backtest", {
            fetchOpts: { signal: AbortSignal.timeout(60000) },
        });
    } catch (err) {
        console.warn("Failed to fetch backtest comparison:", err);
        return null;
    }
}

async function fetchDecayTuning() {
    try {
        return await fetchJson("/predictions/tuning", {
            fetchOpts: { signal: AbortSignal.timeout(60000) },
        });
    } catch (err) {
        console.warn("Failed to fetch decay tuning:", err);
        return null;
    }
}

async function fetchCalibrationDrift() {
    try {
        return await fetchJson("/predictions/drift", {
            fetchOpts: { signal: AbortSignal.timeout(60000) },
        });
    } catch (err) {
        console.warn("Failed to fetch calibration drift:", err);
        return null;
    }
}

async function fetchEnsembleWeights() {
    try {
        return await fetchJson("/predictions/ensemble/weights", {
            fetchOpts: { signal: AbortSignal.timeout(30000) },
        });
    } catch (err) {
        console.warn("Failed to fetch ensemble weights:", err);
        return null;
    }
}

async function fetchCalibrationComparison() {
    try {
        return await fetchJson("/predictions/calibration/comparison", {
            fetchOpts: { signal: AbortSignal.timeout(60000) },
        });
    } catch (err) {
        console.warn("Failed to fetch calibration comparison:", err);
        return null;
    }
}

function fmtMetric(v) {
    if (v === null || v === undefined || v === "") return "—";
    const n = Number(v);
    return Number.isFinite(n) ? n.toFixed(4) : String(v);
}

async function renderBacktest() {
    const z = appState.lang === "zh";
    const statusPill = document.getElementById("backtest-status");
    try {
        const data = backtestComparisonData || await fetchBacktestComparison();
        backtestComparisonData = data;

        if (!data) {
            if (statusPill) {
                statusPill.textContent = z ? "错误" : "error";
                statusPill.className = "status-pill status-low";
            }
            return;
        }

        if (data.status === "not_available") {
            if (statusPill) {
                statusPill.textContent = z ? "无数据" : "NO DATA";
                statusPill.className = "status-pill status-low";
            }
            const instrEl = document.getElementById("backtest-instructions");
            if (instrEl) {
                instrEl.style.display = "block";
                instrEl.innerHTML = `<article class="liquid-panel compact" style="padding:1rem;color:var(--text-muted)">
                    <p>${escapeHtml(t("backtest_not_available"))}</p>
                    <p style="font-size:0.8rem;margin-top:0.5rem;font-family:monospace">${escapeHtml(data.instructions || t("backtest_instructions"))}</p>
                </article>`;
            }
            // Hide data panels
            ["backtest-comparison-panel", "backtest-folds-panel", "backtest-calibration-panel"].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.style.display = "none";
            });
            return;
        }

        if (statusPill) {
            statusPill.textContent = z ? "可用" : "OK";
            statusPill.className = "status-pill status-high";
        }
        const instrEl = document.getElementById("backtest-instructions");
        if (instrEl) instrEl.style.display = "none";

        // Metric comparison table
        const metricTableBody = document.querySelector("#backtest-metric-table tbody");
        if (metricTableBody) {
            const mc = data.metric_comparison || [];
            metricTableBody.innerHTML = mc.map((row) => {
                const winner = row.winner;
                const cells = [
                    `<td>${escapeHtml(row.metric)}</td>`,
                    `<td>${fmtMetric(row.independent_poisson)}</td>`,
                    `<td>${fmtMetric(row.dixon_coles)}</td>`,
                    `<td>${fmtMetric(row.dixon_coles_decay)}</td>`,
                    `<td><span class="status-pill status-high" style="font-size:0.65rem">${escapeHtml(winner || "—")}</span></td>`,
                ];
                return `<tr>${cells.join("")}</tr>`;
            }).join("");
        }

        // Folds table
        const foldsHead = document.querySelector("#backtest-folds-table thead");
        const foldsBody = document.querySelector("#backtest-folds-table tbody");
        const folds = data.folds || [];
        const models = data.models || [];
        if (foldsHead && foldsBody) {
            // Build header dynamically based on available models
            let head = `<tr><th>${escapeHtml(t("backtest_fold"))}</th>`;
            for (const m of models) {
                head += `<th>${escapeHtml(m.model)}<br><span style="font-size:0.65rem;color:var(--text-muted)">${escapeHtml(t("backtest_test_matches"))}</span></th>`;
                head += `<th>${escapeHtml(m.model)}<br><span style="font-size:0.65rem;color:var(--text-muted)">Log Loss</span></th>`;
                head += `<th>${escapeHtml(m.model)}<br><span style="font-size:0.65rem;color:var(--text-muted)">Brier</span></th>`;
                head += `<th>${escapeHtml(m.model)}<br><span style="font-size:0.65rem;color:var(--text-muted)">RPS</span></th>`;
            }
            head += "</tr>";
            foldsHead.innerHTML = head;
            foldsBody.innerHTML = folds.map((f) => {
                let row = `<tr><td>${escapeHtml(String(f.fold))}</td>`;
                for (const m of models) {
                    const prefix = m.model;
                    row += `<td>${escapeHtml(String(f[`${prefix}_test_matches`] ?? "—"))}</td>`;
                    row += `<td>${fmtMetric(f[`${prefix}_log_loss`])}</td>`;
                    row += `<td>${fmtMetric(f[`${prefix}_brier`])}</td>`;
                    row += `<td>${fmtMetric(f[`${prefix}_rps`])}</td>`;
                }
                row += "</tr>";
                return row;
            }).join("");
        }

        // Calibration panel
        const calBody = document.getElementById("backtest-calibration-body");
        if (calBody) {
            const cal = data.calibration || {};
            if (cal.status === "ok") {
                calBody.innerHTML = `<div class="detail-grid">
                    <div><span>${escapeHtml(t("backtest_brier_before"))}</span><strong>${fmtMetric(cal.brier_before)}</strong></div>
                    <div><span>${escapeHtml(t("backtest_brier_after"))}</span><strong>${fmtMetric(cal.brier_after)}</strong></div>
                    <div><span>${escapeHtml(t("backtest_rps_before"))}</span><strong>${fmtMetric(cal.rps_before)}</strong></div>
                    <div><span>${escapeHtml(t("backtest_rps_after"))}</span><strong>${fmtMetric(cal.rps_after)}</strong></div>
                    <div><span>${escapeHtml(t("backtest_n_matches"))}</span><strong>${escapeHtml(String(cal.n_matches ?? "—"))}</strong></div>
                </div>`;
            } else {
                calBody.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("backtest_no_calibration"))}</p>`;
            }
        }

        // Per-fold chart (ECharts)
        _renderBacktestFoldChart(data, models, folds);

        // Decay tuning panel
        try {
            const tuning = decayTuningData || await fetchDecayTuning();
            decayTuningData = tuning;
            _renderDecayTuning(tuning);
        } catch (e) {
            console.warn("Failed to render decay tuning:", e);
        }

        // Calibration drift panel
        try {
            const drift = calibrationDriftData || await fetchCalibrationDrift();
            calibrationDriftData = drift;
            _renderCalibrationDrift(drift);
        } catch (e) {
            console.warn("Failed to render calibration drift:", e);
        }

        // Ensemble weights panel
        try {
            const weights = ensembleWeightsData || await fetchEnsembleWeights();
            ensembleWeightsData = weights;
            _renderEnsembleWeights(weights);
        } catch (e) {
            console.warn("Failed to render ensemble weights:", e);
        }

        // Calibration comparison panel
        try {
            const comp = calibrationComparisonData || await fetchCalibrationComparison();
            calibrationComparisonData = comp;
            _renderCalibrationComparison(comp);
        } catch (e) {
            console.warn("Failed to render calibration comparison:", e);
        }

        // Reliability diagram panel (shown, but data loaded on button click)
        const reliabilityPanel = document.getElementById("backtest-reliability-panel");
        if (reliabilityPanel) {
            reliabilityPanel.style.display = "block";
        }
        // Model comparison / scoreline calibration / confidence distribution panels
        const modelCmpPanel = document.getElementById("backtest-model-comparison-panel");
        if (modelCmpPanel) modelCmpPanel.style.display = "block";
        const scorelinePanel = document.getElementById("backtest-scoreline-calibration-panel");
        if (scorelinePanel) scorelinePanel.style.display = "block";
        const confDistPanel = document.getElementById("backtest-confidence-distribution-panel");
        if (confDistPanel) confDistPanel.style.display = "block";
        const errorAnalysisPanel = document.getElementById("backtest-error-analysis-panel");
        if (errorAnalysisPanel) errorAnalysisPanel.style.display = "block";
        const outcomeDistPanel = document.getElementById("backtest-outcome-distribution-panel");
        if (outcomeDistPanel) outcomeDistPanel.style.display = "block";
        const temporalValPanel = document.getElementById("backtest-temporal-validation-panel");
        if (temporalValPanel) temporalValPanel.style.display = "block";
        const heatmapPanel = document.getElementById("backtest-probability-heatmap-panel");
        if (heatmapPanel) heatmapPanel.style.display = "block";
        const stalenessPanel = document.getElementById("backtest-prediction-staleness-panel");
        if (stalenessPanel) stalenessPanel.style.display = "block";
        const ciPlotPanel = document.getElementById("backtest-ci-plot-panel");
        if (ciPlotPanel) ciPlotPanel.style.display = "block";
        const foldCmpPanel = document.getElementById("backtest-fold-comparison-panel");
        if (foldCmpPanel) foldCmpPanel.style.display = "block";
        const leagueErrPanel = document.getElementById("backtest-league-error-panel");
        if (leagueErrPanel) leagueErrPanel.style.display = "block";
        const featureImpPanel = document.getElementById("backtest-feature-importance-panel");
        if (featureImpPanel) featureImpPanel.style.display = "block";
        const ciCovPanel = document.getElementById("backtest-ci-coverage-panel");
        if (ciCovPanel) ciCovPanel.style.display = "block";
        const driftHmPanel = document.getElementById("backtest-drift-heatmap-panel");
        if (driftHmPanel) driftHmPanel.style.display = "block";
        const errClusterPanel = document.getElementById("backtest-error-clustering-panel");
        if (errClusterPanel) errClusterPanel.style.display = "block";
        const dataDriftPanel = document.getElementById("backtest-data-drift-panel");
        if (dataDriftPanel) dataDriftPanel.style.display = "block";
        const ciWidthPanel = document.getElementById("backtest-ci-width-panel");
        if (ciWidthPanel) ciWidthPanel.style.display = "block";
        const stressTestPanel = document.getElementById("backtest-stress-test-panel");
        if (stressTestPanel) stressTestPanel.style.display = "block";
        const teamDriftPanel = document.getElementById("backtest-team-drift-panel");
        if (teamDriftPanel) teamDriftPanel.style.display = "block";
        const uncertaintyPanel = document.getElementById("backtest-uncertainty-panel");
        if (uncertaintyPanel) uncertaintyPanel.style.display = "block";
        const profitLossPanel = document.getElementById("backtest-profit-loss-panel");
        if (profitLossPanel) profitLossPanel.style.display = "block";
        const trajectoryPanel = document.getElementById("backtest-trajectory-panel");
        if (trajectoryPanel) trajectoryPanel.style.display = "block";
        const difficultyPanel = document.getElementById("backtest-difficulty-panel");
        if (difficultyPanel) difficultyPanel.style.display = "block";
    } catch (err) {
        if (statusPill) {
            statusPill.textContent = z ? "错误" : "error";
            statusPill.className = "status-pill status-low";
        }
        console.warn("Failed to render backtest:", err);
    }
}

function _renderDecayTuning(data) {
    const panel = document.getElementById("backtest-tuning-panel");
    if (!panel) return;
    const body = document.getElementById("backtest-tuning-body");
    if (!body) return;

    if (!data || data.status === "not_available") {
        panel.style.display = "block";
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(t("backtest_tuning_not_available"))}</p>
            <p style="font-size:0.75rem;margin-top:0.5rem;font-family:monospace;color:var(--text-muted)">${escapeHtml((data && data.instructions) || t("backtest_tuning_instructions"))}</p>`;
        return;
    }

    if (data.status === "error") {
        panel.style.display = "block";
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">Error: ${escapeHtml(data.error || "unknown")}</p>`;
        return;
    }

    panel.style.display = "block";
    const candidates = data.candidates || [];
    const bestDecay = data.best_decay;
    const selMetric = data.selection_metric || "rps_1x2";

    // Highlight best decay in the table
    const rows = candidates.map((c) => {
        const isBest = c.decay === bestDecay;
        const hl = c.half_life_days === Infinity || c.half_life_days === "inf"
            ? "∞"
            : fmtMetric(c.half_life_days);
        const cls = isBest ? ' style="background:var(--accent-alpha, rgba(100,180,255,0.12))"' : "";
        const badge = isBest
            ? ` <span class="status-pill status-high" style="font-size:0.6rem">BEST</span>`
            : "";
        return `<tr${cls}>
            <td>${escapeHtml(String(c.decay))}${badge}</td>
            <td>${escapeHtml(String(hl))}</td>
            <td>${fmtMetric(c.log_loss_exact)}</td>
            <td>${fmtMetric(c.brier_1x2)}</td>
            <td>${fmtMetric(c.rps_1x2)}</td>
        </tr>`;
    }).join("");

    body.innerHTML = `
        <div class="detail-grid" style="margin-bottom:1rem">
            <div><span>${escapeHtml(t("backtest_best_decay"))}</span><strong style="font-size:1.1rem;color:var(--accent)">${escapeHtml(String(bestDecay ?? "—"))}</strong></div>
            <div><span>${escapeHtml(t("backtest_selection_metric"))}</span><strong>${escapeHtml(String(selMetric))}</strong></div>
            <div><span>${escapeHtml(t("backtest_n_matches"))}</span><strong>${escapeHtml(String(data.n_matches ?? "—"))}</strong></div>
        </div>
        <table class="data-table" style="width:100%;font-size:0.8rem">
            <thead>
                <tr>
                    <th>Decay</th>
                    <th>${escapeHtml(t("backtest_half_life"))}</th>
                    <th>Log Loss</th>
                    <th>Brier</th>
                    <th>RPS</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;
}

function _renderCalibrationDrift(data) {
    const panel = document.getElementById("backtest-drift-panel");
    if (!panel) return;
    const body = document.getElementById("backtest-drift-body");
    if (!body) return;
    const statusPill = document.getElementById("drift-status-pill");
    const z = appState.lang === "zh";

    if (!data) {
        panel.style.display = "none";
        return;
    }

    if (data.status === "not_available" || data.status === "no_data" || data.status === "no_date_column") {
        panel.style.display = "block";
        if (statusPill) {
            statusPill.textContent = z ? "无数据" : "NO DATA";
            statusPill.className = "status-pill status-low";
        }
        const msg = data.status === "not_available"
            ? (z ? "未生成回测产物，请先运行 tune-predictions --run-backtest。" : "Run 'scoutfootball tune-predictions --run-backtest' to generate backtest artifacts.")
            : (z ? "回测产物缺少必要字段。" : "Backtest artifact missing required fields.");
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${escapeHtml(msg)}</p>`;
        if (data.instructions) {
            body.innerHTML += `<p style="font-size:0.75rem;margin-top:0.5rem;font-family:monospace;color:var(--text-muted)">${escapeHtml(data.instructions)}</p>`;
        }
        return;
    }

    if (data.status === "error") {
        panel.style.display = "block";
        if (statusPill) {
            statusPill.textContent = z ? "错误" : "error";
            statusPill.className = "status-pill status-low";
        }
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">Error: ${escapeHtml(data.message || "unknown")}</p>`;
        return;
    }

    panel.style.display = "block";
    const driftDetected = !!data.drift_detected;
    const driftMetric = data.drift_metric || "rps_1x2";
    const driftThreshold = data.drift_threshold;
    const nWindows = data.n_windows || 0;
    const overall = data.overall_metrics || {};
    const windows = data.windows || [];
    const latest = data.latest_window;

    if (statusPill) {
        if (driftDetected) {
            statusPill.textContent = z ? "漂移" : "DRIFT";
            statusPill.className = "status-pill status-low";
        } else {
            statusPill.textContent = z ? "稳定" : "STABLE";
            statusPill.className = "status-pill status-high";
        }
    }

    const windowRows = windows.map((w) => {
        const isLatest = latest && w.start_date === latest.start_date && w.end_date === latest.end_date;
        const cls = isLatest ? ' style="background:var(--accent-alpha, rgba(100,180,255,0.12))"' : "";
        const badge = isLatest
            ? ` <span class="status-pill status-medium" style="font-size:0.6rem">${z ? "最新" : "LATEST"}</span>`
            : "";
        return `<tr${cls}>
            <td>${escapeHtml(String(w.start_date || "—"))}${badge}</td>
            <td>${escapeHtml(String(w.end_date || "—"))}</td>
            <td>${escapeHtml(String(w.n_matches ?? "—"))}</td>
            <td>${fmtMetric(w.rps_1x2)}</td>
            <td>${fmtMetric(w.brier_1x2)}</td>
            <td>${fmtMetric(w.log_loss_exact)}</td>
        </tr>`;
    }).join("");

    // Compute relative change of latest window vs historical average for display
    let latestRelChange = null;
    if (latest && windows.length >= 2) {
        const historical = windows.slice(0, -1);
        const avgMetric = historical.reduce((s, w) => s + (Number(w[driftMetric]) || 0), 0) / historical.length;
        const latestMetric = Number(latest[driftMetric]) || 0;
        if (avgMetric > 0) {
            latestRelChange = (latestMetric - avgMetric) / avgMetric;
        }
    }
    const latestBlock = latest ? `
        <div class="detail-grid" style="margin-top:0.8rem">
            <div><span>${escapeHtml(z ? "最新窗口 RPS" : "Latest RPS")}</span><strong>${fmtMetric(latest.rps_1x2)}</strong></div>
            <div><span>${escapeHtml(z ? "相对变化" : "Relative change")}</span><strong style="color:${driftDetected ? "var(--warn, #f59e0b)" : "var(--accent)"}">${latestRelChange !== null ? `${(latestRelChange >= 0 ? "+" : "")}${(latestRelChange * 100).toFixed(2)}%` : "—"}</strong></div>
            <div><span>${escapeHtml(z ? "阈值" : "Threshold")}</span><strong>${(Number(driftThreshold) * 100).toFixed(1)}%</strong></div>
        </div>` : "";

    body.innerHTML = `
        <div class="detail-grid" style="margin-bottom:0.8rem">
            <div><span>${escapeHtml(z ? "漂移检测" : "Drift detected")}</span><strong style="color:${driftDetected ? "var(--warn, #f59e0b)" : "var(--accent)"}">${driftDetected ? (z ? "是" : "YES") : (z ? "否" : "NO")}</strong></div>
            <div><span>${escapeHtml(z ? "监控指标" : "Drift metric")}</span><strong>${escapeHtml(String(driftMetric))}</strong></div>
            <div><span>${escapeHtml(z ? "窗口数" : "Windows")}</span><strong>${escapeHtml(String(nWindows))}</strong></div>
            <div><span>${escapeHtml(z ? "整体 RPS" : "Overall RPS")}</span><strong>${fmtMetric(overall.rps_1x2)}</strong></div>
            <div><span>${escapeHtml(z ? "整体 Brier" : "Overall Brier")}</span><strong>${fmtMetric(overall.brier_1x2)}</strong></div>
            <div><span>${escapeHtml(z ? "整体 LogLoss" : "Overall LogLoss")}</span><strong>${fmtMetric(overall.log_loss_exact)}</strong></div>
        </div>
        <table class="data-table" style="width:100%;font-size:0.8rem">
            <thead>
                <tr>
                    <th>${escapeHtml(z ? "窗口起" : "Start")}</th>
                    <th>${escapeHtml(z ? "窗口止" : "End")}</th>
                    <th>${escapeHtml(z ? "场次数" : "Matches")}</th>
                    <th>RPS</th>
                    <th>Brier</th>
                    <th>Log Loss</th>
                </tr>
            </thead>
            <tbody>${windowRows}</tbody>
        </table>${latestBlock}`;
}

function _renderEnsembleWeights(data) {
    const panel = document.getElementById("backtest-ensemble-weights-panel");
    if (!panel) return;
    const body = document.getElementById("backtest-ensemble-weights-body");
    if (!body) return;
    const statusPill = document.getElementById("ensemble-weights-status-pill");
    const z = appState.lang === "zh";

    if (!data) {
        panel.style.display = "none";
        return;
    }

    panel.style.display = "block";

    if (data.status === "not_available") {
        if (statusPill) {
            statusPill.textContent = z ? "等权重" : "EQUAL";
            statusPill.className = "status-pill status-medium";
        }
        const defaultW = data.default_weights || {};
        const defaultRows = Object.entries(defaultW).map(([k, v]) =>
            `<div><span>${escapeHtml(k)}</span><strong>${(Number(v) * 100).toFixed(1)}%</strong></div>`
        ).join("");
        body.innerHTML = `
            <p style="color:var(--text-muted);font-size:0.85rem;margin:0 0 0.5rem">${escapeHtml(t("ensemble_weights_not_available"))}</p>
            <p style="font-size:0.75rem;margin:0 0 0.8rem;font-family:monospace;color:var(--text-muted)">${escapeHtml(data.instructions || t("ensemble_weights_instructions"))}</p>
            <div class="detail-grid">${defaultRows}</div>`;
        return;
    }

    if (data.status === "error") {
        if (statusPill) {
            statusPill.textContent = z ? "错误" : "error";
            statusPill.className = "status-pill status-low";
        }
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">Error: ${escapeHtml(data.message || "unknown")}</p>`;
        return;
    }

    if (statusPill) {
        statusPill.textContent = z ? "已优化" : "OPTIMIZED";
        statusPill.className = "status-pill status-high";
    }

    const weights = data.weights || {};
    const weightBars = Object.entries(weights).map(([k, v]) => {
        const pct = (Number(v) * 100).toFixed(1);
        return `<div style="margin-bottom:0.4rem">
            <div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:0.2rem">
                <span>${escapeHtml(k)}</span><strong>${pct}%</strong>
            </div>
            <div style="height:6px;background:var(--bg-elevated, rgba(255,255,255,0.08));border-radius:3px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:var(--accent, #64b5f6);border-radius:3px"></div>
            </div>
        </div>`;
    }).join("");

    const meta = `
        <div class="detail-grid" style="margin-top:0.8rem">
            ${data.rps != null ? `<div><span>${escapeHtml(t("ensemble_achieved_rps"))}</span><strong>${fmtMetric(data.rps)}</strong></div>` : ""}
            ${data.n_matches != null ? `<div><span>${escapeHtml(t("ensemble_n_matches"))}</span><strong>${escapeHtml(String(data.n_matches))}</strong></div>` : ""}
            ${data.saved_at ? `<div><span>${escapeHtml(t("ensemble_saved_at"))}</span><strong style="font-size:0.75rem">${escapeHtml(String(data.saved_at).slice(0, 19).replace("T", " "))}</strong></div>` : ""}
        </div>`;

    body.innerHTML = `${weightBars}${meta}`;
}

function _renderCalibrationComparison(data) {
    const panel = document.getElementById("backtest-calibration-comparison-panel");
    if (!panel) return;
    const body = document.getElementById("backtest-calibration-comparison-body");
    if (!body) return;
    const z = appState.lang === "zh";

    if (!data) {
        panel.style.display = "none";
        return;
    }

    panel.style.display = "block";

    if (data.status === "not_available" || data.status === "error") {
        const msg = data.status === "error"
            ? `Error: ${escapeHtml(data.message || "unknown")}`
            : escapeHtml(t("calibration_comparison_not_available"));
        body.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem">${msg}</p>
            <p style="font-size:0.75rem;margin-top:0.5rem;font-family:monospace;color:var(--text-muted)">${escapeHtml(data.instructions || t("calibration_comparison_instructions"))}</p>`;
        return;
    }

    const overall = data.overall || {};
    const improvement = data.improvement || {};
    const byScoreLine = data.by_score_line || [];
    const calMetrics = data.calibrator_metrics || {};

    // Overall metrics card
    const brierImp = improvement.brier_improvement_pct;
    const rpsImp = improvement.rps_improvement_pct;
    const impColor = (v) => v != null && v < 0 ? "var(--accent, #64b5f6)" : "var(--warn, #f59e0b)";

    const overallHtml = `
        <h4 style="margin:0 0 0.5rem;font-size:0.85rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("calibration_comparison_overall"))}</h4>
        <div class="detail-grid">
            <div><span>Brier ${escapeHtml(t("calibration_comparison_raw"))}</span><strong>${fmtMetric(overall.brier_raw)}</strong></div>
            <div><span>Brier ${escapeHtml(t("calibration_comparison_recalibrated"))}</span><strong>${fmtMetric(overall.brier_recalibrated)}</strong></div>
            <div><span>Brier ${escapeHtml(t("calibration_comparison_improvement"))}</span><strong style="color:${impColor(brierImp)}">${brierImp != null ? `${brierImp >= 0 ? "+" : ""}${brierImp.toFixed(2)}%` : "—"}</strong></div>
            <div><span>RPS ${escapeHtml(t("calibration_comparison_raw"))}</span><strong>${fmtMetric(overall.rps_raw)}</strong></div>
            <div><span>RPS ${escapeHtml(t("calibration_comparison_recalibrated"))}</span><strong>${fmtMetric(overall.rps_recalibrated)}</strong></div>
            <div><span>RPS ${escapeHtml(t("calibration_comparison_improvement"))}</span><strong style="color:${impColor(rpsImp)}">${rpsImp != null ? `${rpsImp >= 0 ? "+" : ""}${rpsImp.toFixed(2)}%` : "—"}</strong></div>
        </div>
        <div style="font-size:0.72rem;color:var(--text-muted);margin-top:0.4rem">
            ${escapeHtml(t("calibration_comparison_n_matches"))}: ${escapeHtml(String(data.n_matches ?? calMetrics.n_samples ?? "—"))}
        </div>`;

    // Per-score-line table
    let scoreLineHtml = "";
    if (byScoreLine.length > 0) {
        const rows = byScoreLine.map((s) => {
            const bImp = s.brier_improvement_pct;
            const rImp = s.rps_improvement_pct;
            return `<tr>
                <td><strong>${escapeHtml(s.score_line)}</strong></td>
                <td>${escapeHtml(String(s.n_matches))}</td>
                <td>${fmtMetric(s.brier_raw)}</td>
                <td>${fmtMetric(s.brier_recalibrated)}</td>
                <td style="color:${impColor(bImp)}">${bImp != null ? `${bImp >= 0 ? "+" : ""}${bImp.toFixed(2)}%` : "—"}</td>
                <td>${fmtMetric(s.rps_raw)}</td>
                <td>${fmtMetric(s.rps_recalibrated)}</td>
                <td style="color:${impColor(rImp)}">${rImp != null ? `${rImp >= 0 ? "+" : ""}${rImp.toFixed(2)}%` : "—"}</td>
            </tr>`;
        }).join("");
        scoreLineHtml = `
            <h4 style="margin:1rem 0 0.5rem;font-size:0.85rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("calibration_comparison_by_score"))}</h4>
            <table class="data-table" style="width:100%;font-size:0.78rem">
                <thead>
                    <tr>
                        <th>${escapeHtml(t("calibration_comparison_score_line"))}</th>
                        <th>N</th>
                        <th>Brier ${escapeHtml(t("calibration_comparison_raw"))}</th>
                        <th>Brier ${escapeHtml(t("calibration_comparison_recalibrated"))}</th>
                        <th>Δ%</th>
                        <th>RPS ${escapeHtml(t("calibration_comparison_raw"))}</th>
                        <th>RPS ${escapeHtml(t("calibration_comparison_recalibrated"))}</th>
                        <th>Δ%</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    // Per-league breakdown table
    const byLeague = Array.isArray(data.by_league) ? data.by_league : [];
    let leagueHtml = "";
    if (byLeague.length > 0) {
        const lgRows = byLeague.map((l) => {
            const bImp = l.brier_improvement_pct;
            const rImp = l.rps_improvement_pct;
            return `<tr>
                <td><strong>${escapeHtml(String(l.league))}</strong></td>
                <td>${escapeHtml(String(l.n_matches))}</td>
                <td>${fmtMetric(l.brier_raw)}</td>
                <td>${fmtMetric(l.brier_recalibrated)}</td>
                <td style="color:${impColor(bImp)}">${bImp != null ? `${bImp >= 0 ? "+" : ""}${bImp.toFixed(2)}%` : "—"}</td>
                <td>${fmtMetric(l.rps_raw)}</td>
                <td>${fmtMetric(l.rps_recalibrated)}</td>
                <td style="color:${impColor(rImp)}">${rImp != null ? `${rImp >= 0 ? "+" : ""}${rImp.toFixed(2)}%` : "—"}</td>
            </tr>`;
        }).join("");
        leagueHtml = `
            <h4 style="margin:1rem 0 0.5rem;font-size:0.85rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${escapeHtml(t("calibration_comparison_by_league"))}</h4>
            <table class="data-table" style="width:100%;font-size:0.78rem">
                <thead>
                    <tr>
                        <th>${escapeHtml(t("calibration_comparison_league"))}</th>
                        <th>N</th>
                        <th>Brier ${escapeHtml(t("calibration_comparison_raw"))}</th>
                        <th>Brier ${escapeHtml(t("calibration_comparison_recalibrated"))}</th>
                        <th>Δ%</th>
                        <th>RPS ${escapeHtml(t("calibration_comparison_raw"))}</th>
                        <th>RPS ${escapeHtml(t("calibration_comparison_recalibrated"))}</th>
                        <th>Δ%</th>
                    </tr>
                </thead>
                <tbody>${lgRows}</tbody>
            </table>`;
    }

    body.innerHTML = `${overallHtml}${scoreLineHtml}${leagueHtml}`;
}

function _renderBacktestFoldChart(data, models, folds) {
    const container = document.getElementById("backtest-fold-chart");
    if (!container) return;
    const panel = document.getElementById("backtest-fold-chart-panel");
    if (!folds || folds.length === 0 || !models || models.length === 0) {
        if (panel) panel.style.display = "none";
        return;
    }
    if (panel) panel.style.display = "";
    const chart = getChart("backtest-fold-chart");
    if (!chart) return;
    const z = appState.lang === "zh";

    const metricKeys = ["log_loss", "brier", "rps"];
    const metricLabels = z
        ? { log_loss: "Log Loss", brier: "Brier", rps: "RPS" }
        : { log_loss: "Log Loss", brier: "Brier", rps: "RPS" };
    const modelColors = ["#4f9cff", "#6bcf7f", "#f5a623"];

    const foldLabels = folds.map((f) => String(f.fold));

    const series = [];
    models.forEach((m, mi) => {
        metricKeys.forEach((mk) => {
            const seriesData = folds.map((f) => {
                const v = f[`${m.model}_${mk}`];
                return v != null ? Number(v) : null;
            });
            series.push({
                name: `${m.model} ${metricLabels[mk]}`,
                type: "line",
                data: seriesData,
                smooth: true,
                symbol: "circle",
                symbolSize: 6,
                lineStyle: { width: 2 },
                itemStyle: { color: modelColors[mi % modelColors.length] },
                emphasis: { focus: "series" },
            });
        });
    });

    chart.setOption({
        tooltip: {
            trigger: "axis",
            axisPointer: { type: "cross" },
        },
        legend: {
            top: 5,
            textStyle: { fontSize: 10, color: "#aaa" },
            type: "scroll",
        },
        grid: {
            left: "8%",
            right: "5%",
            bottom: "8%",
            top: "18%",
        },
        xAxis: {
            type: "category",
            data: foldLabels,
            name: z ? "折" : "Fold",
            nameTextStyle: { color: "#888", fontSize: 10 },
            axisLabel: { color: "#aaa", fontSize: 10 },
        },
        yAxis: {
            type: "value",
            name: z ? "指标值（越低越好）" : "Metric (lower=better)",
            nameTextStyle: { color: "#888", fontSize: 10 },
            axisLabel: { color: "#aaa", fontSize: 10 },
            splitLine: { lineStyle: { color: "rgba(128,128,128,0.15)" } },
        },
        series,
    }, true);
}

function exportPlayers() {
    const header = ["rank", "player", "position", "team", "league", "season", "rating", "confidence", "minutes", "goals", "assists"];
    const rows = filteredPlayers().map((player, index) => [
        index + 1,
        player.name,
        player.position,
        player.team,
        player.league || "",
        player.season,
        player.rating,
        player.confidence,
        player.minutes || "",
        player.goals || "",
        player.assists || "",
    ]);
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "scoutfootball-player-pool.csv";
    link.click();
    URL.revokeObjectURL(url);
}

function bindEvents() {
    document.querySelectorAll(".nav-action[data-view]").forEach((button) => {
        button.addEventListener("click", () => setView(button.dataset.view));
    });
    document.querySelectorAll("[data-jump]").forEach((card) => {
        card.addEventListener("click", () => setView(card.dataset.jump));
    });
    document.getElementById("theme-toggle").addEventListener("click", () => {
        const toggle = document.getElementById("theme-toggle");
        document.body.classList.toggle("dark-mode");
        const darkMode = document.body.classList.contains("dark-mode");
        toggle.textContent = darkMode ? "☾" : "☀";
        toggle.setAttribute("aria-pressed", darkMode ? "true" : "false");
        toggle.setAttribute("aria-label", darkMode ? "切换为浅色主题" : "切换为深色主题");
        localStorage.setItem("sf-theme", darkMode ? "dark" : "light");
        refreshAllChartColors();
        renderActiveView();
    });
    document.getElementById("lang-toggle").addEventListener("click", () => {
        appState.lang = appState.lang === "zh" ? "en" : "zh";
        applyLocale();
        renderActiveView();
    });
    document.getElementById("position-filter").addEventListener("change", (event) => {
        appState.position = event.target.value;
        renderPlayers();
    });
    document.getElementById("season-filter").addEventListener("change", (event) => {
        appState.season = event.target.value;
        appState.playerPage = 1;
        renderPlayers();
    });
    document.getElementById("league-filter").addEventListener("change", (event) => {
        appState.league = event.target.value;
        appState.playerPage = 1;
        renderPlayers();
    });
    // Pagination
    document.getElementById("player-prev-page")?.addEventListener("click", () => {
        if (appState.playerPage > 1) { appState.playerPage--; renderPlayers(); }
    });
    document.getElementById("player-next-page")?.addEventListener("click", () => {
        appState.playerPage++;
        renderPlayers();
    });
    // Column sorting
    document.querySelectorAll("th[data-sort]").forEach((th) => {
        th.addEventListener("click", () => {
            const col = th.dataset.sort;
            if (appState.playerSortCol === col) {
                appState.playerSortAsc = !appState.playerSortAsc;
            } else {
                appState.playerSortCol = col;
                appState.playerSortAsc = col === "name" || col === "position" || col === "team";
            }
            appState.playerPage = 1;
            renderPlayers();
        });
    });
    let searchTimer = null;
    document.getElementById("global-search").addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            appState.playerPage = 1;
            if (appState.view !== "players") setView("players");
            else renderPlayers();
        }, 300);
    });
    // Wire typeahead suggestions on the global player search
    SearchTypeahead("global-search", "players", () => {
        document.getElementById("global-search").dispatchEvent(new Event("input", { bubbles: true }));
    });
    document.querySelectorAll("[data-value-mode]").forEach((button) => {
        button.addEventListener("click", () => {
            appState.valueMode = button.dataset.valueMode;
            document.querySelectorAll("[data-value-mode]").forEach((item) => item.classList.toggle("active", item === button));
            renderValue();
        });
    });
    document.getElementById("home-team").addEventListener("change", (event) => {
        appState.home = event.target.value;
        if (appState.home === appState.away) {
            const nextAway = getTeams().find((team) => team !== appState.home);
            if (nextAway) appState.away = nextAway;
            document.getElementById("away-team").value = appState.away;
        }
        renderMatches();
    });
    document.getElementById("away-team").addEventListener("change", (event) => {
        appState.away = event.target.value;
        if (appState.home === appState.away) {
            const nextHome = getTeams().find((team) => team !== appState.away);
            if (nextHome) appState.home = nextHome;
            document.getElementById("home-team").value = appState.home;
        }
        renderMatches();
    });
    const modelSelect = document.getElementById("prediction-model");
    if (modelSelect) {
        modelSelect.addEventListener("change", (event) => {
            appState.predictionModel = event.target.value;
            renderMatches();
        });
        modelSelect.value = appState.predictionModel;
    }
    document.getElementById("export-players").addEventListener("click", exportPlayers);
    // World Cup events
    document.getElementById("wc-group-filter").addEventListener("change", () => renderWcSchedule());
    document.getElementById("wc-matchday-filter").addEventListener("change", () => renderWcSchedule());
    document.getElementById("wc-squad-team").addEventListener("change", async (e) => {
        appState.wcSquadTeam = e.target.value;
        await fetchWcSquad(e.target.value);
        renderWcSquads();
    });
    document.getElementById("wc-compare-a").addEventListener("change", async (e) => {
        appState.wcCompareA = e.target.value;
        if (appState.wcCompareA === appState.wcCompareB) {
            const nextB = wcAllTeams().find((team) => team !== appState.wcCompareA);
            if (nextB) {
                appState.wcCompareB = nextB;
                document.getElementById("wc-compare-b").value = nextB;
            }
        }
        await Promise.all([
            fetchWcSquad(e.target.value),
            fetchWcMatchPrediction(e.target.value, appState.wcCompareB),
            fetchWcSquadBalanceComparison(e.target.value, appState.wcCompareB),
        ]);
        renderWcCompare();
    });
    document.getElementById("wc-compare-b").addEventListener("change", async (e) => {
        appState.wcCompareB = e.target.value;
        if (appState.wcCompareA === appState.wcCompareB) {
            const nextA = wcAllTeams().find((team) => team !== appState.wcCompareB);
            if (nextA) {
                appState.wcCompareA = nextA;
                document.getElementById("wc-compare-a").value = nextA;
            }
        }
        await Promise.all([
            fetchWcSquad(e.target.value),
            fetchWcMatchPrediction(appState.wcCompareA, e.target.value),
            fetchWcSquadBalanceComparison(appState.wcCompareA, e.target.value),
        ]);
        renderWcCompare();
    });

    // Pre-match plan button: create tactical project from match prediction
    const prematchBtn = document.getElementById("btn-prematch-plan");
    if (prematchBtn) {
        prematchBtn.addEventListener("click", () => {
            createPrematchPlan();
        });
    }
    const predictionJsonBtn = document.getElementById("btn-prediction-export-json");
    if (predictionJsonBtn) predictionJsonBtn.addEventListener("click", exportCurrentPredictionJSON);
    const predictionCsvBtn = document.getElementById("btn-prediction-export-csv");
    if (predictionCsvBtn) predictionCsvBtn.addEventListener("click", exportCurrentPredictionCSV);

    // Momentum update button: re-fetch momentum with current scoreline/minute
    const momentumBtn = document.getElementById("btn-momentum-update");
    if (momentumBtn) {
        momentumBtn.addEventListener("click", () => {
            renderMomentum(appState.home, appState.away).catch((e) => console.warn("Momentum update failed:", e));
        });
    }

    // Prediction attribution button: fetch permutation-based factor attribution
    const attributionBtn = document.getElementById("btn-prediction-attribution");
    if (attributionBtn) {
        attributionBtn.addEventListener("click", () => {
            fetchAndRenderPredictionAttribution(appState.home, appState.away).catch(
                (e) => console.warn("Prediction attribution failed:", e)
            );
        });
    }

    // Prediction attribution CI button: bootstrap confidence intervals on factor deltas
    const attributionCIBtn = document.getElementById("btn-prediction-attribution-ci");
    if (attributionCIBtn) {
        attributionCIBtn.addEventListener("click", () => {
            fetchAndRenderPredictionAttributionCI(appState.home, appState.away).catch(
                (e) => console.warn("Prediction attribution CI failed:", e)
            );
        });
    }

    // Prediction diagnostics button: combined calibration/drift/attribution view
    const diagnosticsBtn = document.getElementById("btn-prediction-diagnostics");
    if (diagnosticsBtn) {
        diagnosticsBtn.addEventListener("click", () => {
            fetchAndRenderDiagnostics(appState.home, appState.away).catch(
                (e) => console.warn("Prediction diagnostics failed:", e)
            );
        });
    }

    // Drift timeline button: ECharts line chart of per-window calibration metrics
    const driftTimelineBtn = document.getElementById("btn-drift-timeline");
    if (driftTimelineBtn) {
        driftTimelineBtn.addEventListener("click", () => {
            fetchAndRenderDriftTimeline().catch(
                (e) => console.warn("Drift timeline failed:", e)
            );
        });
    }

    // Ensemble attribution button: per-model + blended factor contributions
    const ensembleAttrBtn = document.getElementById("btn-ensemble-attribution");
    if (ensembleAttrBtn) {
        ensembleAttrBtn.addEventListener("click", () => {
            fetchAndRenderEnsembleAttribution(appState.home, appState.away).catch(
                (e) => console.warn("Ensemble attribution failed:", e)
            );
        });
    }

    // Ensemble attribution CI button: bootstrap CIs on blended factor deltas
    const ensembleAttrCIBtn = document.getElementById("btn-ensemble-attribution-ci");
    if (ensembleAttrCIBtn) {
        ensembleAttrCIBtn.addEventListener("click", () => {
            fetchAndRenderEnsembleAttributionCI(appState.home, appState.away).catch(
                (e) => console.warn("Ensemble attribution CI failed:", e)
            );
        });
    }

    // Value bet analysis button: EV/Kelly/edge calculation vs market odds
    const valueBetBtn = document.getElementById("btn-value-bet");
    if (valueBetBtn) {
        valueBetBtn.addEventListener("click", () => {
            fetchAndRenderValueBet(appState.home, appState.away).catch(
                (e) => console.warn("Value bet analysis failed:", e)
            );
        });
    }

    // Reliability diagram button: calibration scatter plot
    const reliabilityBtn = document.getElementById("btn-reliability-diagram");
    if (reliabilityBtn) {
        reliabilityBtn.addEventListener("click", () => {
            fetchAndRenderReliabilityDiagram().catch(
                (e) => console.warn("Reliability diagram failed:", e)
            );
        });
    }

    // Model comparison button: unified metrics dashboard
    const modelCmpBtn = document.getElementById("btn-model-comparison");
    if (modelCmpBtn) {
        modelCmpBtn.addEventListener("click", () => {
            fetchAndRenderModelComparison().catch(
                (e) => console.warn("Model comparison failed:", e)
            );
        });
    }

    // Score-line calibration button: predicted vs actual by score-line
    const scorelineBtn = document.getElementById("btn-scoreline-calibration");
    if (scorelineBtn) {
        scorelineBtn.addEventListener("click", () => {
            fetchAndRenderScorelineCalibration().catch(
                (e) => console.warn("Score-line calibration failed:", e)
            );
        });
    }

    // Confidence distribution button: accuracy per confidence bucket
    const confDistBtn = document.getElementById("btn-confidence-distribution");
    if (confDistBtn) {
        confDistBtn.addEventListener("click", () => {
            fetchAndRenderConfidenceDistribution().catch(
                (e) => console.warn("Confidence distribution failed:", e)
            );
        });
    }

    // Error analysis button: worst matches per confidence bucket
    const errorAnalysisBtn = document.getElementById("btn-error-analysis");
    if (errorAnalysisBtn) {
        errorAnalysisBtn.addEventListener("click", () => {
            fetchAndRenderErrorAnalysis().catch(
                (e) => console.warn("Error analysis failed:", e)
            );
        });
    }

    // Outcome distribution button: predicted vs actual 1x2 distribution
    const outcomeDistBtn = document.getElementById("btn-outcome-distribution");
    if (outcomeDistBtn) {
        outcomeDistBtn.addEventListener("click", () => {
            fetchAndRenderOutcomeDistribution().catch(
                (e) => console.warn("Outcome distribution failed:", e)
            );
        });
    }

    // H2H bias correction button: adjust baseline with historical H2H rates
    const h2hBiasBtn = document.getElementById("btn-h2h-bias");
    if (h2hBiasBtn) {
        h2hBiasBtn.addEventListener("click", () => {
            fetchAndRenderH2HBiasCorrection().catch(
                (e) => console.warn("H2H bias correction failed:", e)
            );
        });
    }

    // Temporal validation button: per-window metric trends
    const temporalValBtn = document.getElementById("btn-temporal-validation");
    if (temporalValBtn) {
        temporalValBtn.addEventListener("click", () => {
            fetchAndRenderTemporalValidation().catch(
                (e) => console.warn("Temporal validation failed:", e)
            );
        });
    }

    // Probability heatmap button: 2D density grid
    const heatmapBtn = document.getElementById("btn-probability-heatmap");
    if (heatmapBtn) {
        heatmapBtn.addEventListener("click", () => {
            fetchAndRenderProbabilityHeatmap().catch(
                (e) => console.warn("Probability heatmap failed:", e)
            );
        });
    }

    // Prediction staleness button: model freshness indicator
    const stalenessBtn = document.getElementById("btn-prediction-staleness");
    if (stalenessBtn) {
        stalenessBtn.addEventListener("click", () => {
            fetchAndRenderPredictionStaleness().catch(
                (e) => console.warn("Prediction staleness failed:", e)
            );
        });
    }

    // CI plot button: confidence vs CI width scatter
    const ciPlotBtn = document.getElementById("btn-ci-plot");
    if (ciPlotBtn) {
        ciPlotBtn.addEventListener("click", () => {
            fetchAndRenderConfidenceIntervalPlot().catch(
                (e) => console.warn("CI plot failed:", e)
            );
        });
    }

    // Fold comparison button: per-fold metrics + stability
    const foldCmpBtn = document.getElementById("btn-fold-comparison");
    if (foldCmpBtn) {
        foldCmpBtn.addEventListener("click", () => {
            fetchAndRenderFoldComparison().catch(
                (e) => console.warn("Fold comparison failed:", e)
            );
        });
    }

    // League error analysis button: per-league error + worst predictions
    const leagueErrBtn = document.getElementById("btn-league-error");
    if (leagueErrBtn) {
        leagueErrBtn.addEventListener("click", () => {
            fetchAndRenderLeagueErrorAnalysis().catch(
                (e) => console.warn("League error analysis failed:", e)
            );
        });
    }

    // Feature importance button: bin-wise Brier separation ranking
    const featureImpBtn = document.getElementById("btn-feature-importance");
    if (featureImpBtn) {
        featureImpBtn.addEventListener("click", () => {
            fetchAndRenderFeatureImportance().catch(
                (e) => console.warn("Feature importance failed:", e)
            );
        });
    }

    // CI coverage button: bootstrap CI coverage validation
    const ciCovBtn = document.getElementById("btn-ci-coverage");
    if (ciCovBtn) {
        ciCovBtn.addEventListener("click", () => {
            fetchAndRenderCICoverage().catch(
                (e) => console.warn("CI coverage failed:", e)
            );
        });
    }

    // Drift heatmap button: window × confidence bucket grid
    const driftHmBtn = document.getElementById("btn-drift-heatmap");
    if (driftHmBtn) {
        driftHmBtn.addEventListener("click", () => {
            fetchAndRenderDriftHeatmap().catch(
                (e) => console.warn("Drift heatmap failed:", e)
            );
        });
    }

    // Error clustering button: k-means on worst predictions
    const errClusterBtn = document.getElementById("btn-error-clustering");
    if (errClusterBtn) {
        errClusterBtn.addEventListener("click", () => {
            fetchAndRenderErrorClustering().catch(
                (e) => console.warn("Error clustering failed:", e)
            );
        });
    }

    // Data drift button: KS test between train/holdout
    const dataDriftBtn = document.getElementById("btn-data-drift");
    if (dataDriftBtn) {
        dataDriftBtn.addEventListener("click", () => {
            fetchAndRenderDataDrift().catch(
                (e) => console.warn("Data drift failed:", e)
            );
        });
    }

    // CI width button: per-confidence-bucket CI width
    const ciWidthBtn = document.getElementById("btn-ci-width");
    if (ciWidthBtn) {
        ciWidthBtn.addEventListener("click", () => {
            fetchAndRenderCIWidth().catch(
                (e) => console.warn("CI width failed:", e)
            );
        });
    }

    // Stress test button: distribution shift simulation
    const stressTestBtn = document.getElementById("btn-stress-test");
    if (stressTestBtn) {
        stressTestBtn.addEventListener("click", () => {
            fetchAndRenderStressTest().catch(
                (e) => console.warn("Stress test failed:", e)
            );
        });
    }

    // Team drift button: per-team calibration drift
    const teamDriftBtn = document.getElementById("btn-team-drift");
    if (teamDriftBtn) {
        teamDriftBtn.addEventListener("click", () => {
            fetchAndRenderTeamDrift().catch(
                (e) => console.warn("Team drift failed:", e)
            );
        });
    }

    // Uncertainty button: per-match uncertainty quantification
    const uncertaintyBtn = document.getElementById("btn-uncertainty");
    if (uncertaintyBtn) {
        uncertaintyBtn.addEventListener("click", () => {
            fetchAndRenderUncertainty().catch(
                (e) => console.warn("Uncertainty failed:", e)
            );
        });
    }

    // Profit/Loss button: flat-stake and Kelly betting simulation
    const profitLossBtn = document.getElementById("btn-profit-loss");
    if (profitLossBtn) {
        profitLossBtn.addEventListener("click", () => {
            fetchAndRenderProfitLoss().catch(
                (e) => console.warn("Profit/Loss failed:", e)
            );
        });
    }

    // Trajectory button: cumulative performance trajectory
    const trajectoryBtn = document.getElementById("btn-trajectory");
    if (trajectoryBtn) {
        trajectoryBtn.addEventListener("click", () => {
            fetchAndRenderTrajectory().catch(
                (e) => console.warn("Trajectory failed:", e)
            );
        });
    }

    // Difficulty button: match difficulty stratification
    const difficultyBtn = document.getElementById("btn-difficulty");
    if (difficultyBtn) {
        difficultyBtn.addEventListener("click", () => {
            fetchAndRenderDifficulty().catch(
                (e) => console.warn("Difficulty failed:", e)
            );
        });
    }

    // WC team template button: create tactical project from WC squad
    const wcTeamTemplateBtn = document.getElementById("btn-wc-team-template");
    if (wcTeamTemplateBtn) {
        wcTeamTemplateBtn.addEventListener("click", () => {
            createWcTeamTemplate();
        });
    }

    // Tactical board event handlers
    const tacticalLoadHome = document.getElementById("tactical-load-home");
    if (tacticalLoadHome) {
        tacticalLoadHome.addEventListener("click", () => {
            const formation = document.getElementById("tactical-formation").value;
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.loadFormation(formation, "home");
                tacticalProject = TacticalRenderer.getProject();
                // Load coaching points into frame notes
                if (typeof TACTICAL_BOARD !== "undefined") {
                    const cp = TACTICAL_BOARD.getFormationCoachingPoints(formation);
                    if (cp) {
                        const notes = TACTICAL_BOARD.formatCoachingNotes(cp);
                        TacticalRenderer.setCurrentFrameNotes(notes);
                        updateCoachingNotesPanel();
                    }
                }
            }
        });
    }
    const tacticalLoadAway = document.getElementById("tactical-load-away");
    if (tacticalLoadAway) {
        tacticalLoadAway.addEventListener("click", () => {
            const formation = document.getElementById("tactical-formation").value;
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.loadFormation(formation, "away");
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }
    const tacticalClear = document.getElementById("tactical-clear");
    if (tacticalClear) {
        tacticalClear.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.clearBoard();
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }
    const tacticalLoadSetPiece = document.getElementById("tactical-load-setpiece");
    if (tacticalLoadSetPiece) {
        tacticalLoadSetPiece.addEventListener("click", () => {
            const type = document.getElementById("tactical-setpiece").value;
            if (!type) return;
            if (typeof TacticalRenderer !== "undefined" && typeof TACTICAL_BOARD !== "undefined") {
                const objects = TACTICAL_BOARD.generateSetPiece(type, "home");
                if (objects.length > 0) {
                    TacticalRenderer.clearBoard();
                    const project = TacticalRenderer.getProject();
                    project.objects = objects;
                    TacticalRenderer.render();
                    tacticalProject = project;
                    // Load coaching points into frame notes
                    const cp = TACTICAL_BOARD.getSetPieceCoachingPoints(type);
                    if (cp) {
                        const notes = TACTICAL_BOARD.formatCoachingNotes(cp);
                        TacticalRenderer.setCurrentFrameNotes(notes);
                        updateCoachingNotesPanel();
                    }
                }
            }
        });
    }
    const tacticalLoadTraining = document.getElementById("tactical-load-training");
    if (tacticalLoadTraining) {
        tacticalLoadTraining.addEventListener("click", () => {
            const type = document.getElementById("tactical-training").value;
            if (!type) return;
            if (typeof TacticalRenderer !== "undefined" && typeof TACTICAL_BOARD !== "undefined") {
                const objects = TACTICAL_BOARD.generateTraining(type, "home");
                if (objects.length > 0) {
                    TacticalRenderer.clearBoard();
                    const project = TacticalRenderer.getProject();
                    project.objects = objects;
                    TacticalRenderer.render();
                    tacticalProject = project;
                    // Load coaching points into frame notes
                    const cp = TACTICAL_BOARD.getTrainingCoachingPoints(type);
                    if (cp) {
                        const notes = TACTICAL_BOARD.formatCoachingNotes(cp);
                        TacticalRenderer.setCurrentFrameNotes(notes);
                        updateCoachingNotesPanel();
                    }
                }
            }
        });
    }
    const tacticalSave = document.getElementById("tactical-save");
    if (tacticalSave) {
        tacticalSave.addEventListener("click", () => {
            if (tacticalProject) {
                TACTICAL_BOARD.saveProject(tacticalProject);
                renderTacticalProjectList();
            }
        });
    }
    const tacticalExport = document.getElementById("tactical-export");
    if (tacticalExport) {
        tacticalExport.addEventListener("click", () => {
            if (tacticalProject) {
                // Show export preview with attribution
                const previewEl = document.getElementById("tactical-export-preview");
                const attrEl = document.getElementById("tactical-export-attribution");
                if (previewEl && attrEl) {
                    const attribution = [
                        "Title: " + (tacticalProject.title || "Untitled"),
                        "Source: " + (tacticalProject.source_attribution || "ScoutFootball tactical board"),
                        "Version: " + (tacticalProject.version || TACTICAL_BOARD.SCHEMA_VERSION),
                        "Objects: " + (tacticalProject.objects || []).length,
                        "Frames: " + (tacticalProject.frames || []).length,
                        "Created: " + (tacticalProject.created_at || "unknown"),
                        "Updated: " + (tacticalProject.updated_at || "unknown"),
                        ...(tacticalProject.metadata?.decision_pack ? [
                            "",
                            "Decision pack: " + (tacticalProject.metadata.decision_pack.prediction?.status === "available" ? "prediction recorded" : "prediction not loaded"),
                            "Model: " + (tacticalProject.metadata.decision_pack.prediction?.model_type || "not recorded"),
                            "Model run: " + (tacticalProject.metadata.decision_pack.provenance?.model_run_id || "not recorded; local artifact snapshot"),
                            "Input hash: " + (tacticalProject.metadata.decision_pack.provenance?.input_hash || "not recorded"),
                            ...(tacticalProject.metadata.decision_pack.provenance?.briefing_schema ? [
                                "Briefing contract: " + tacticalProject.metadata.decision_pack.provenance.briefing_schema
                                    + (tacticalProject.metadata.decision_pack.provenance.briefing_version ? " v" + tacticalProject.metadata.decision_pack.provenance.briefing_version : ""),
                                "Briefing source: " + (tacticalProject.metadata.decision_pack.provenance.briefing_source || "not recorded"),
                            ] : []),
                        ] : []),
                        "",
                        "No data leaves the browser. All projects are stored locally.",
                    ].join("\n");
                    attrEl.textContent = attribution;
                    previewEl.style.display = "flex";
                } else {
                    // Fallback: direct export
                    doTacticalExport(tacticalProject);
                }
            }
        });
    }
    // Export preview confirm/cancel handlers
    const exportConfirm = document.getElementById("tactical-export-confirm");
    const exportCancel = document.getElementById("tactical-export-cancel");
    const exportPreview = document.getElementById("tactical-export-preview");
    if (exportConfirm) {
        exportConfirm.addEventListener("click", () => {
            if (exportPreview) exportPreview.style.display = "none";
            if (tacticalProject) doTacticalExport(tacticalProject);
        });
    }
    if (exportCancel) {
        exportCancel.addEventListener("click", () => {
            if (exportPreview) exportPreview.style.display = "none";
        });
    }
    function doTacticalExport(project) {
        const json = TACTICAL_BOARD.exportJSON(project);
        const blob = new Blob([json], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `tactical-board-${project.board_id}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
    const tacticalImport = document.getElementById("tactical-import");
    if (tacticalImport) {
        tacticalImport.addEventListener("click", () => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".json";
            input.addEventListener("change", (e) => {
                const file = e.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = (ev) => {
                    const project = TACTICAL_BOARD.importJSON(ev.target.result);
                    if (project) {
                        tacticalProject = project;
                        renderTactical();
                    } else {
                        alert("Failed to import project. The file may be corrupt or not a valid tactical board export.");
                    }
                };
                reader.readAsText(file);
            });
            input.click();
        });
    }
    const tacticalExportPng = document.getElementById("tactical-export-png");
    if (tacticalExportPng) {
        tacticalExportPng.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                const title = tacticalProject?.title || "tactical-board";
                const cropSelect = document.getElementById("tactical-crop-mode");
                const transparentCb = document.getElementById("tactical-transparent-bg");
                const crop = cropSelect ? cropSelect.value : "full";
                const transparent = transparentCb ? transparentCb.checked : false;
                TacticalRenderer.exportPNG(`${title}.png`, { crop, transparent });
            }
        });
    }
    const tacticalExportWebm = document.getElementById("tactical-export-webm");
    if (tacticalExportWebm) {
        tacticalExportWebm.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                const title = tacticalProject?.title || "tactical-animation";
                TacticalRenderer.exportWebM(`${title}.webm`);
            }
        });
    }
    const tacticalExportGif = document.getElementById("tactical-export-gif");
    if (tacticalExportGif) {
        tacticalExportGif.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                const title = tacticalProject?.title || "tactical-animation";
                TacticalRenderer.exportGIF(`${title}.gif`);
            }
        });
    }
    // MP4 export via backend ffmpeg conversion
    const tacticalExportMp4 = document.getElementById("tactical-export-mp4");
    if (tacticalExportMp4) {
        // Check if ffmpeg is available on the backend
        fetchJson("/tactical-board/capabilities").then(caps => {
            if (caps.ffmpeg_available) {
                tacticalExportMp4.style.opacity = "1";
                tacticalExportMp4.title = "ffmpeg detected: " + (caps.ffmpeg_path || "");
            } else {
                tacticalExportMp4.title = "ffmpeg not found on server — MP4 export unavailable";
            }
        }).catch(() => { /* API offline, keep button dimmed */ });

        tacticalExportMp4.addEventListener("click", async () => {
            if (typeof TacticalRenderer === "undefined") return;
            const zT = appState.lang === "zh";
            try {
                // First export as WebM blob
                tacticalExportMp4.disabled = true;
                tacticalExportMp4.textContent = zT ? "◆ 导出中..." : "◆ Exporting...";

                const stream = TacticalRenderer.canvas.captureStream(30);
                const mimeType = "video/webm;codecs=vp9";
                const recorder = new MediaRecorder(stream, { mimeType });
                const chunks = [];
                recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

                // Play animation and record
                const wasPlaying = TacticalRenderer.animationState.playing;
                if (!wasPlaying) TacticalRenderer.toggleAnimation();
                recorder.start();

                await new Promise(resolve => setTimeout(resolve, 3000)); // Record 3s

                recorder.stop();
                if (wasPlaying) TacticalRenderer.toggleAnimation();

                await new Promise(resolve => { recorder.onstop = resolve; });
                const webmBlob = new Blob(chunks, { type: "video/webm" });

                // Send to backend for MP4 conversion
                const resp = await fetch(`${API_BASE}/tactical-board/export/mp4`, {
                    method: "POST",
                    headers: { "Content-Type": "video/webm" },
                    body: webmBlob,
                });
                const result = await resp.json();

                if (result.status === "ok") {
                    alert(zT
                        ? `◆ MP4 导出成功！\n保存到: ${result.path}\n大小: ${(result.size_bytes / 1024).toFixed(1)} KB`
                        : `◆ MP4 exported!\nSaved to: ${result.path}\nSize: ${(result.size_bytes / 1024).toFixed(1)} KB`
                    );
                } else {
                    alert(zT
                        ? `◆ MP4 导出失败: ${result.error}`
                        : `◆ MP4 export failed: ${result.error}`
                    );
                }
            } catch (err) {
                alert(zT
                    ? `◆ MP4 导出失败: ${err.message}`
                    : `◆ MP4 export failed: ${err.message}`
                );
            } finally {
                tacticalExportMp4.disabled = false;
                tacticalExportMp4.textContent = "◆ 导出 MP4";
            }
        });
    }

    // Animation controls
    const tacticalAddFrame = document.getElementById("tactical-add-frame");
    if (tacticalAddFrame) {
        tacticalAddFrame.addEventListener("click", () => {
            if (tacticalProject && typeof TacticalRenderer !== "undefined") {
                TACTICAL_BOARD.saveFrame(tacticalProject, TacticalRenderer.animationState.currentFrame);
                TACTICAL_BOARD.addFrame(tacticalProject);
                renderTacticalFrameList();
            }
        });
    }
    const tacticalSaveFrame = document.getElementById("tactical-save-frame");
    if (tacticalSaveFrame) {
        tacticalSaveFrame.addEventListener("click", () => {
            if (tacticalProject && typeof TacticalRenderer !== "undefined") {
                TACTICAL_BOARD.saveFrame(tacticalProject, TacticalRenderer.animationState.currentFrame);
                renderTacticalFrameList();
            }
        });
    }
    const tacticalPlay = document.getElementById("tactical-play");
    if (tacticalPlay) {
        tacticalPlay.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.play();
            }
        });
    }
    const tacticalStop = document.getElementById("tactical-stop");
    if (tacticalStop) {
        tacticalStop.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.stop();
            }
        });
    }
    const tacticalPrevFrame = document.getElementById("tactical-prev-frame");
    if (tacticalPrevFrame) {
        tacticalPrevFrame.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.prevFrame();
                tacticalProject = TacticalRenderer.getProject();
                renderTacticalFrameList();
            }
        });
    }
    const tacticalNextFrame = document.getElementById("tactical-next-frame");
    if (tacticalNextFrame) {
        tacticalNextFrame.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.nextFrame();
                tacticalProject = TacticalRenderer.getProject();
                renderTacticalFrameList();
            }
        });
    }

    // Drawing tool buttons
    const toolButtons = ["tactical-tool-select", "tactical-tool-arrow", "tactical-tool-zone", "tactical-tool-text"];
    function setActiveTool(activeId) {
        toolButtons.forEach((id) => {
            const btn = document.getElementById(id);
            if (btn) btn.classList.toggle("active", id === activeId);
        });
    }
    // Pitch type selector
    const tacticalPitchType = document.getElementById("tactical-pitch-type");
    if (tacticalPitchType) {
        tacticalPitchType.addEventListener("change", (e) => {
            if (tacticalProject && typeof TacticalRenderer !== "undefined") {
                tacticalProject.pitch_type = e.target.value;
                TacticalRenderer.render();
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }

    // Display mode selector
    const tacticalDisplayMode = document.getElementById("tactical-display-mode");
    if (tacticalDisplayMode) {
        tacticalDisplayMode.addEventListener("change", (e) => {
            if (tacticalProject && typeof TacticalRenderer !== "undefined") {
                tacticalProject.displayMode = e.target.value;
                TacticalRenderer.render();
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }

    // Duplicate / Mirror buttons
    const tacticalDuplicate = document.getElementById("tactical-duplicate");
    if (tacticalDuplicate) {
        tacticalDuplicate.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.duplicateSelected();
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }
    const tacticalMirror = document.getElementById("tactical-mirror");
    if (tacticalMirror) {
        tacticalMirror.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.mirrorSelected();
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }
    const tacticalMirrorHome = document.getElementById("tactical-mirror-home");
    if (tacticalMirrorHome) {
        tacticalMirrorHome.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.mirrorAllHome();
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }
    const tacticalMirrorAway = document.getElementById("tactical-mirror-away");
    if (tacticalMirrorAway) {
        tacticalMirrorAway.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.mirrorAllAway();
                tacticalProject = TacticalRenderer.getProject();
            }
        });
    }

    const tacticalToolSelect = document.getElementById("tactical-tool-select");
    if (tacticalToolSelect) {
        tacticalToolSelect.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.setDrawingMode(null);
            }
            setActiveTool("tactical-tool-select");
        });
    }

    const tacticalToolArrow = document.getElementById("tactical-tool-arrow");
    if (tacticalToolArrow) {
        tacticalToolArrow.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.setDrawingMode("arrow");
            }
            setActiveTool("tactical-tool-arrow");
        });
    }

    const tacticalToolZone = document.getElementById("tactical-tool-zone");
    if (tacticalToolZone) {
        tacticalToolZone.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.setDrawingMode("zone");
            }
            setActiveTool("tactical-tool-zone");
        });
    }

    const tacticalToolText = document.getElementById("tactical-tool-text");
    if (tacticalToolText) {
        tacticalToolText.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.setDrawingMode("text");
            }
            setActiveTool("tactical-tool-text");
        });
    }

    // Loop toggle
    const tacticalLoop = document.getElementById("tactical-loop");
    if (tacticalLoop) {
        tacticalLoop.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.toggleLoop();
                tacticalLoop.classList.toggle("active", TacticalRenderer.animationState.loop);
            }
        });
    }

    // Tactical: toggle player ratings
    const tacticalToggleRatings = document.getElementById("tactical-toggle-ratings");
    if (tacticalToggleRatings) {
        tacticalToggleRatings.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.showRatings = !TacticalRenderer.showRatings;
                tacticalToggleRatings.classList.toggle("active", TacticalRenderer.showRatings);
                TacticalRenderer.render();
            }
        });
    }

    // Equipment placement handler
    const tacticalPlaceEquipment = document.getElementById("tactical-place-equipment");
    if (tacticalPlaceEquipment) {
        tacticalPlaceEquipment.addEventListener("click", () => {
            const equipmentType = document.getElementById("tactical-equipment").value;
            if (!equipmentType) return;
            if (typeof TacticalRenderer !== "undefined" && typeof TACTICAL_BOARD !== "undefined") {
                const project = TacticalRenderer.getProject();
                let obj = null;
                switch (equipmentType) {
                    case "cone": obj = TACTICAL_BOARD.createCone(50, 50); break;
                    case "marker": obj = TACTICAL_BOARD.createMarker(50, 50); break;
                    case "pole": obj = TACTICAL_BOARD.createPole(50, 50); break;
                    case "ladder": obj = TACTICAL_BOARD.createLadder(50, 50); break;
                    case "minigoal": obj = TACTICAL_BOARD.createMiniGoal(50, 50); break;
                }
                if (obj) {
                    project.objects.push(obj);
                    TacticalRenderer.selectedObject = obj;
                    TacticalRenderer.render();
                    tacticalProject = project;
                }
            }
        });
    }

    // Eraser tool button
    const tacticalEraser = document.getElementById("tactical-eraser");
    if (tacticalEraser) {
        tacticalEraser.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                const isEraser = TacticalRenderer.drawingMode === "eraser";
                TacticalRenderer.setDrawingMode(isEraser ? null : "eraser");
                tacticalEraser.classList.toggle("active", !isEraser);
                setActiveTool(isEraser ? "tactical-tool-select" : null);
            }
        });
    }

    // Presentation mode button
    const tacticalPresentation = document.getElementById("tactical-presentation");
    if (tacticalPresentation) {
        tacticalPresentation.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.togglePresentation();
            }
        });
    }

    // Animation trails toggle
    const tacticalToggleTrails = document.getElementById("tactical-toggle-trails");
    if (tacticalToggleTrails) {
        tacticalToggleTrails.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.showTrails = !TacticalRenderer.showTrails;
                tacticalToggleTrails.classList.toggle("active", TacticalRenderer.showTrails);
                if (!TacticalRenderer.showTrails) {
                    TacticalRenderer._trailPositions.clear();
                }
                TacticalRenderer.render();
            }
        });
    }

    // Simplify button: remove hidden objects and empty frames
    const tacticalSimplify = document.getElementById("tactical-simplify");
    if (tacticalSimplify) {
        tacticalSimplify.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.simplifyProject();
                tacticalProject = TacticalRenderer.getProject();
                tacticalAutoSave();
            }
        });
    }

    // xT Heatmap toggle
    const tacticalToggleHeatmap = document.getElementById("tactical-toggle-heatmap");
    if (tacticalToggleHeatmap) {
        tacticalToggleHeatmap.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                var isOn = TacticalRenderer.toggleXTHeatmap();
                tacticalToggleHeatmap.classList.toggle("active", isOn);
            }
        });
    }

    // Debug mode toggle (FPS counter)
    const tacticalToggleDebug = document.getElementById("tactical-toggle-debug");
    if (tacticalToggleDebug) {
        tacticalToggleDebug.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer._debugMode = !TacticalRenderer._debugMode;
                tacticalToggleDebug.classList.toggle("active", TacticalRenderer._debugMode);
                TacticalRenderer.render();
            }
        });
    }

    // Coaching notes textarea: sync notes to current frame
    const coachingNotesEl = document.getElementById("tactical-coaching-notes");
    if (coachingNotesEl) {
        coachingNotesEl.addEventListener("input", () => {
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.setCurrentFrameNotes(coachingNotesEl.value);
                tacticalProject = TacticalRenderer.getProject();
                tacticalAutoSave();
            }
        });
    }

    // Animation mode toggle
    const tacticalAnimMode = document.getElementById("tactical-animation-mode");
    const stepDurationLabel = document.getElementById("tactical-step-duration-label");
    if (tacticalAnimMode) {
        tacticalAnimMode.addEventListener("change", (e) => {
            if (tacticalProject) {
                tacticalProject.animationMode = e.target.value;
                if (stepDurationLabel) {
                    stepDurationLabel.style.display = e.target.value === "step" ? "flex" : "none";
                }
                tacticalAutoSave();
            }
        });
    }

    // Step duration slider
    const tacticalStepDuration = document.getElementById("tactical-step-duration");
    const stepDurationValue = document.getElementById("tactical-step-duration-value");
    if (tacticalStepDuration) {
        tacticalStepDuration.addEventListener("input", (e) => {
            const val = parseInt(e.target.value, 10);
            if (stepDurationValue) stepDurationValue.textContent = val + "ms";
            if (tacticalProject) {
                tacticalProject.stepDuration = val;
                tacticalAutoSave();
            }
        });
    }

    // Path editing: add path point mode
    const tacticalAddPathPoint = document.getElementById("tactical-add-path-point");
    if (tacticalAddPathPoint) {
        tacticalAddPathPoint.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                const sel = TacticalRenderer.selectedObject;
                if (sel && (sel.type === "player" || sel.type === "ball")) {
                    const isActive = TacticalRenderer._pathEditMode && TacticalRenderer._pathEditObjectId === sel.id;
                    TacticalRenderer.setPathEditMode(!isActive, isActive ? null : sel.id);
                    tacticalAddPathPoint.classList.toggle("active", !isActive);
                    tacticalAddPathPoint.textContent = isActive ? "+ 路径点" : "完成路径";
                }
            }
        });
    }

    // Path editing: clear path points
    const tacticalClearPathPoints = document.getElementById("tactical-clear-path-points");
    if (tacticalClearPathPoints) {
        tacticalClearPathPoints.addEventListener("click", () => {
            if (typeof TacticalRenderer !== "undefined") {
                const sel = TacticalRenderer.selectedObject;
                if (sel) {
                    TacticalRenderer.clearPathPoints(sel.id);
                    tacticalProject = TacticalRenderer.getProject();
                    renderTacticalFrameList();
                }
            }
        });
    }

    // Path type selector
    const tacticalPathType = document.getElementById("tactical-path-type");
    if (tacticalPathType) {
        tacticalPathType.addEventListener("change", (e) => {
            if (typeof TacticalRenderer !== "undefined") {
                const sel = TacticalRenderer.selectedObject;
                if (sel) {
                    TacticalRenderer.setObjectPathType(sel.id, e.target.value);
                    tacticalProject = TacticalRenderer.getProject();
                }
            }
        });
    }

    // Easing selector
    const tacticalEasing = document.getElementById("tactical-easing");
    if (tacticalEasing) {
        tacticalEasing.addEventListener("change", (e) => {
            if (typeof TacticalRenderer !== "undefined") {
                const sel = TacticalRenderer.selectedObject;
                if (sel) {
                    TacticalRenderer.setObjectEasing(sel.id, e.target.value);
                    tacticalProject = TacticalRenderer.getProject();
                }
            }
        });
    }

    // Delay input
    const tacticalObjDelay = document.getElementById("tactical-obj-delay");
    if (tacticalObjDelay) {
        tacticalObjDelay.addEventListener("change", (e) => {
            if (typeof TacticalRenderer !== "undefined") {
                const sel = TacticalRenderer.selectedObject;
                if (sel) {
                    TacticalRenderer.setObjectDelay(sel.id, parseInt(e.target.value, 10) || 0);
                    tacticalProject = TacticalRenderer.getProject();
                    renderTacticalFrameList();
                }
            }
        });
    }

    // Pause input
    const tacticalObjPause = document.getElementById("tactical-obj-pause");
    if (tacticalObjPause) {
        tacticalObjPause.addEventListener("change", (e) => {
            if (typeof TacticalRenderer !== "undefined") {
                const sel = TacticalRenderer.selectedObject;
                if (sel) {
                    TacticalRenderer.setObjectPause(sel.id, parseInt(e.target.value, 10) || 0);
                    tacticalProject = TacticalRenderer.getProject();
                    renderTacticalFrameList();
                }
            }
        });
    }

    // Reports: expand/collapse run details
    document.addEventListener("click", async (e) => {
        const toggleBtn = e.target.closest("[data-toggle-run]");
        if (toggleBtn) {
            const runId = toggleBtn.dataset.toggleRun;
            const detailsEl = document.querySelector(`[data-run-details="${runId}"]`);
            if (detailsEl) {
                const isHidden = detailsEl.style.display === "none";
                if (isHidden && !detailsEl.dataset.detailLoaded) {
                    // First expand: load detail endpoint for feature_importance, params_summary, data_attribution
                    const z = appState.lang === "zh";
                    const loadingHint = document.createElement("div");
                    loadingHint.style.cssText = "font-size:0.75rem;color:var(--text-muted);padding:0.3rem 0";
                    loadingHint.textContent = z ? "加载详情..." : "Loading details...";
                    detailsEl.appendChild(loadingHint);
                    detailsEl.style.display = "block";
                    toggleBtn.textContent = z ? "\u25BC 收起详情" : "\u25BC Collapse";

                    const detail = await fetchModelRunDetail(runId);
                    loadingHint.remove();
                    if (detail) {
                        const extraHtml = _renderRunDetailExtra(detail);
                        if (extraHtml) {
                            const wrapper = document.createElement("div");
                            wrapper.innerHTML = extraHtml;
                            detailsEl.appendChild(wrapper.firstElementChild || wrapper);
                        }
                        detailsEl.dataset.detailLoaded = "1";
                    }
                    // Keep expanded after loading
                    return;
                }
                detailsEl.style.display = isHidden ? "block" : "none";
                toggleBtn.textContent = isHidden
                    ? (appState.lang === "zh" ? "\u25BC \u6536\u8d77\u8be6\u60c5" : "\u25BC Collapse")
                    : (appState.lang === "zh" ? "\u25B6 \u5c55\u5f00\u8be6\u60c5" : "\u25B6 Expand");
            }
        }
    });

    // Reports: copy run command
    document.addEventListener("click", (e) => {
        const copyBtn = e.target.closest("[data-copy-cmd]");
        if (copyBtn) {
            const cmd = copyBtn.dataset.copyCmd;
            if (cmd && navigator.clipboard) {
                navigator.clipboard.writeText(cmd).then(() => {
                    const orig = copyBtn.textContent;
                    copyBtn.textContent = "\u2713 Copied";
                    setTimeout(() => { copyBtn.textContent = orig; }, 1500);
                }).catch(() => {});
            }
        }
    });

    // Scouting: status badge click to cycle
    document.addEventListener("click", (e) => {
        const statusEl = e.target.closest("[data-queue-status]");
        if (statusEl) {
            const pKey = statusEl.dataset.queueStatus;
            cycleQueueStatus(pKey);
            renderScouting();
        }
    });

    // Scouting: sort toggle
    document.addEventListener("click", (e) => {
        const sortBtn = e.target.closest("[data-scout-sort]");
        if (sortBtn) {
            scoutSortMode = sortBtn.dataset.scoutSort;
            scoutCurrentPage = 1;
            renderScouting();
        }
        // Scouting pagination
        if (e.target.id === "scout-prev-page" && scoutCurrentPage > 1) {
            scoutCurrentPage--;
            renderScouting();
        }
        if (e.target.id === "scout-next-page") {
            scoutCurrentPage++;
            renderScouting();
        }
    });

    const scoutSearch = document.getElementById("scout-search");
    if (scoutSearch) {
        scoutSearch.addEventListener("input", (e) => {
            appState.scoutingQuery = e.target.value;
            scoutCurrentPage = 1;
            renderScouting();
        });
    }
    const scoutStatusFilter = document.getElementById("scout-status-filter");
    if (scoutStatusFilter) {
        scoutStatusFilter.addEventListener("change", (e) => {
            appState.scoutingStatus = e.target.value;
            scoutCurrentPage = 1;
            renderScouting();
        });
    }
    const scoutSnapshotButton = document.getElementById("scout-save-snapshot");
    if (scoutSnapshotButton) {
        scoutSnapshotButton.addEventListener("click", () => {
            saveWatchlistSnapshot(mergeScoutingRows(watchlistData, getPlayerWatchlist()));
            computeWatchlistDiff(mergeScoutingRows(watchlistData, getPlayerWatchlist()));
            renderScouting();
        });
    }
    const scoutExportButton = document.getElementById("scout-export-csv");
    if (scoutExportButton) scoutExportButton.addEventListener("click", exportReviewQueueCSV);
    const scoutDecisionPackJsonButton = document.getElementById("scout-export-decision-pack-json");
    if (scoutDecisionPackJsonButton) {
        scoutDecisionPackJsonButton.addEventListener("click", exportShortlistDecisionPackJSON);
    }
    const scoutDecisionPackCsvButton = document.getElementById("scout-export-decision-pack-csv");
    if (scoutDecisionPackCsvButton) {
        scoutDecisionPackCsvButton.addEventListener("click", exportShortlistDecisionPackCSV);
    }
    const scoutShortlistTacticalButton = document.getElementById("scout-shortlist-to-tactical");
    if (scoutShortlistTacticalButton) {
        scoutShortlistTacticalButton.addEventListener("click", sendShortlistToTacticalBoard);
    }

    const scoutWorkspaceExportButton = document.getElementById("scout-export-workspace");
    if (scoutWorkspaceExportButton) {
        scoutWorkspaceExportButton.addEventListener("click", exportScoutingWorkspace);
    }
    const scoutWorkspaceImportButton = document.getElementById("scout-import-workspace");
    const scoutWorkspaceFile = document.getElementById("scout-workspace-file");
    if (scoutWorkspaceImportButton && scoutWorkspaceFile) {
        scoutWorkspaceImportButton.addEventListener("click", () => scoutWorkspaceFile.click());
        scoutWorkspaceFile.addEventListener("change", async () => {
            const [file] = scoutWorkspaceFile.files || [];
            scoutWorkspaceFile.value = "";
            if (file) await previewScoutingWorkspaceImport(file);
        });
    }
    const scoutServerSaveButton = document.getElementById("scout-server-save");
    if (scoutServerSaveButton) {
        scoutServerSaveButton.addEventListener("click", saveScoutingWorkspaceToServer);
    }
    const scoutServerLoadButton = document.getElementById("scout-server-load");
    if (scoutServerLoadButton) {
        scoutServerLoadButton.addEventListener("click", loadLatestScoutingWorkspaceFromServer);
    }
    const scoutWorkspaceDialog = document.getElementById("scout-workspace-dialog");
    const scoutWorkspaceCancel = document.getElementById("scout-workspace-cancel");
    const scoutWorkspaceMerge = document.getElementById("scout-workspace-merge");
    const scoutWorkspaceReplace = document.getElementById("scout-workspace-replace");
    if (scoutWorkspaceCancel && scoutWorkspaceDialog) {
        scoutWorkspaceCancel.addEventListener("click", () => {
            pendingScoutingWorkspaceImport = null;
            scoutWorkspaceDialog.close();
        });
        scoutWorkspaceDialog.addEventListener("close", () => {
            pendingScoutingWorkspaceImport = null;
        });
    }
    if (scoutWorkspaceMerge) {
        scoutWorkspaceMerge.addEventListener("click", () => applyScoutingWorkspaceImport("merge"));
    }
    if (scoutWorkspaceReplace) {
        scoutWorkspaceReplace.addEventListener("click", () => applyScoutingWorkspaceImport("replace"));
    }

    // Scouting: note input change
    document.addEventListener("change", (e) => {
        if (e.target.matches(".scout-dossier-input") && e.target.dataset.dossierPlayer) {
            updateShortlistDossier(
                e.target.dataset.dossierPlayer,
                e.target.dataset.dossierLegacyName,
                e.target.dataset.dossierField,
                e.target.value,
            );
        }
        if (e.target.matches(".scout-note-textarea") && e.target.dataset.notePlayer) {
            const pName = e.target.dataset.notePlayer;
            if (pName != null) {
                scoutShortlistNotes[pName] = e.target.value;
                saveScoutShortlistNotes();
            }
        }
        // Watchlist notes textarea
        if (e.target.matches(".scout-note-textarea") && e.target.dataset.wlNotePlayer) {
            const pName = e.target.dataset.wlNotePlayer;
            if (pName != null) {
                watchlistNotes[pName] = e.target.value;
                saveWatchlistNotes();
            }
        }
    });
    // Scouting: note and dossier text update while typing.
    document.addEventListener("input", (e) => {
        if (e.target.matches(".scout-dossier-input") && e.target.dataset.dossierPlayer) {
            updateShortlistDossier(
                e.target.dataset.dossierPlayer,
                e.target.dataset.dossierLegacyName,
                e.target.dataset.dossierField,
                e.target.value,
            );
        }
        if (e.target.matches(".scout-note-textarea") && e.target.dataset.notePlayer) {
            const pName = e.target.dataset.notePlayer;
            if (pName != null) {
                scoutShortlistNotes[pName] = e.target.value;
                saveScoutShortlistNotes();
            }
        }
        // Watchlist notes textarea live update
        if (e.target.matches(".scout-note-textarea") && e.target.dataset.wlNotePlayer) {
            const pName = e.target.dataset.wlNotePlayer;
            if (pName != null) {
                watchlistNotes[pName] = e.target.value;
                saveWatchlistNotes();
            }
        }
    });

    // Scouting: tactical role button click
    document.addEventListener("click", (e) => {
        const roleBtn = e.target.closest("[data-tactical-role]");
        if (roleBtn) {
            const pName = roleBtn.dataset.tacticalRole;
            const player = mergeScoutingRows(shortlistData, getPlayerShortlist())
                .find((p) => (p.player_name || p.name || "") === pName);
            if (player) {
                const role = generateTacticalRole(player);
                const roleEl = document.getElementById("player-tactical-role");
                if (roleEl) {
                    roleEl.innerHTML = `<div style="font-size:0.78rem;padding:0.3rem 0"><strong>${escapeHtml(t("tactical_role_label"))}:</strong> ${escapeHtml(role)}</div>`;
                }
            }
        }
    });

    // Value page: price band filter
    const priceBandSelect = document.getElementById("value-price-band");
    if (priceBandSelect) {
        priceBandSelect.addEventListener("change", (e) => {
            appState.valuePriceBand = e.target.value;
            renderValue();
        });
    }

    document.querySelectorAll("[data-action-mode]").forEach((button) => {
        button.addEventListener("click", () => {
            appState.actionMode = button.dataset.actionMode;
            renderActions();
        });
    });
    const actionSearch = document.getElementById("action-search");
    if (actionSearch) {
        actionSearch.addEventListener("input", (e) => {
            appState.actionQuery = e.target.value;
            renderActions();
        });
    }
    const actionCompetitionFilter = document.getElementById("action-competition-filter");
    if (actionCompetitionFilter) {
        actionCompetitionFilter.addEventListener("change", (e) => {
            appState.actionCompetition = e.target.value;
            renderActions();
        });
    }
    const actionTeamFilter = document.getElementById("action-team-filter");
    if (actionTeamFilter) {
        actionTeamFilter.addEventListener("change", (e) => {
            appState.actionTeam = e.target.value;
            renderActions();
        });
    }
    const actionSeasonFilter = document.getElementById("action-season-filter");
    if (actionSeasonFilter) {
        actionSeasonFilter.addEventListener("change", (e) => {
            appState.actionSeason = e.target.value;
            renderActions();
        });
    }
    const actionMinutesFilter = document.getElementById("action-minutes-filter");
    if (actionMinutesFilter) {
        actionMinutesFilter.addEventListener("change", (e) => {
            appState.actionMinMinutes = Number(e.target.value || 0);
            renderActions();
        });
    }
    const actionDetailDialog = document.getElementById("action-detail-dialog");
    const actionDetailClose = document.getElementById("action-detail-close");
    if (actionDetailClose && actionDetailDialog) {
        actionDetailClose.addEventListener("click", () => actionDetailDialog.close());
        actionDetailDialog.addEventListener("click", (event) => {
            if (event.target === actionDetailDialog) actionDetailDialog.close();
        });
    }
    window.addEventListener("resize", () => {
        Object.values(appState.charts).forEach((chart) => {
            try { chart.resize(); } catch { /* ignore disposed chart */ }
        });
    });
}

// ── World Cup Data ───────────────────────────────────────────────────────

// Static group structure (official FIFA draw — not from API)
const WC_GROUPS = {
    A: ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    B: ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    C: ["Brazil", "Morocco", "Haiti", "Scotland"],
    D: ["United States", "Paraguay", "Australia", "Turkey"],
    E: ["Germany", "Curacao", "Ivory Coast", "Ecuador"],
    F: ["Netherlands", "Japan", "Sweden", "Tunisia"],
    G: ["Belgium", "Egypt", "Iran", "New Zealand"],
    H: ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    I: ["France", "Senegal", "Iraq", "Norway"],
    J: ["Argentina", "Algeria", "Austria", "Jordan"],
    K: ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    L: ["England", "Croatia", "Ghana", "Panama"],
};

const WC_HOSTS = ["United States", "Canada", "Mexico"];
const WC_BIG5 = new Set(["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]);

// API-driven World Cup data cache
let wcApiData = {
    groups: null,       // from /world-cup/groups
    schedule: null,     // from /world-cup/schedule
    squadCache: {},     // team -> from /world-cup/squads/{team}
    squadBalanceComparisonCache: {}, // ordered team pair -> role-depth comparison
    predictions: null,  // from /world-cup/predictions
    knockout: null,     // from /world-cup/knockout
    matchPredictionCache: {}, // home|away -> single-match prediction
    matchBriefingCache: {}, // home|away -> source-bounded pre-match briefing
    outlookCache: {},   // team -> from /world-cup/outlook/{team}
    teams: null,        // from /worldcup/teams
    apiOnline: false,
    squadLoading: new Set(),
    outlookLoading: new Set(),
    tournament: null,       // from /world-cup/tournament/summary
    tournamentMatches: null, // from /world-cup/tournament/matches
    tournamentScenarios: null, // team -> scenarios
    tournamentSelectedGroup: "A",
    tournamentLoading: false,
    knockoutBracket: null,  // from /world-cup/tournament/knockout
    knockoutProbabilities: null,  // from /world-cup/tournament/knockout/probabilities
    knockoutReviews: {},  // match ID → local pre-recording result review
    knockoutScenarios: {},  // team → scenario data from /world-cup/tournament/knockout/scenarios/{team}
    groupStageSimulation: null,  // from /world-cup/tournament/group-simulation
    tournamentExport: null,  // from /world-cup/tournament/export
};

/* ── No demo squad data — API must be online for WC squads ─────────── */
const WC_DEMO_SQUADS = {};

async function fetchWcTeams() {
    try {
        const data = await fetchJson("/worldcup/teams", { fetchOpts: { signal: AbortSignal.timeout(60000) } });
        wcApiData.teams = data;
        wcApiData.apiOnline = true;
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcTeams failed:", e.message);
        return null;
    }
}

async function fetchWcGroups() {
    try {
        const data = await fetchJson("/world-cup/groups", { fetchOpts: { signal: AbortSignal.timeout(60000) } });
        wcApiData.groups = data;
        wcApiData.apiOnline = true;
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcGroups failed:", e.message);
        return null;
    }
}

async function fetchWcSchedule(group, matchday) {
    try {
        const data = await fetchJson("/world-cup/schedule", { fetchOpts: { signal: AbortSignal.timeout(60000) } });
        wcApiData.schedule = data;
        wcApiData.apiOnline = true;
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcSchedule failed:", e.message);
        return null;
    }
}

async function fetchWcSquad(team) {
    if (wcApiData.squadCache[team]) return wcApiData.squadCache[team];
    wcApiData.squadLoading.add(team);
    try {
        const data = await fetchJson(`/world-cup/squads/${encodeURIComponent(team)}`, { fetchOpts: { signal: AbortSignal.timeout(60000) } });
        wcApiData.squadCache[team] = data;
        wcApiData.apiOnline = true;
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcSquad failed:", e.message);
        return null;
    } finally {
        wcApiData.squadLoading.delete(team);
        if (appState.view === "wc_squads" && appState.wcSquadTeam === team) {
            renderWcSquads();
        }
    }
}

async function fetchWcSquadBalanceComparison(teamA, teamB) {
    if (!teamA || !teamB) return null;
    const cacheKey = `${teamA}|${teamB}`;
    if (wcApiData.squadBalanceComparisonCache[cacheKey]) {
        return wcApiData.squadBalanceComparisonCache[cacheKey];
    }
    try {
        const data = await fetchJson(
            `/world-cup/squad-balance-comparison/${encodeURIComponent(teamA)}/${encodeURIComponent(teamB)}`,
            { fetchOpts: { signal: AbortSignal.timeout(60000) } },
        );
        if (data?.status === "ok") {
            wcApiData.squadBalanceComparisonCache[cacheKey] = data;
            wcApiData.apiOnline = true;
        }
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcSquadBalanceComparison failed:", e.message);
        return null;
    }
}

async function fetchWcPredictions() {
    try {
        const data = await fetchJson("/world-cup/predictions", { fetchOpts: { signal: AbortSignal.timeout(60000) } });
        wcApiData.predictions = data;
        wcApiData.apiOnline = true;
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcPredictions failed:", e.message);
        return null;
    }
}

async function fetchWcKnockout() {
    try {
        const data = await fetchJson("/world-cup/knockout", { fetchOpts: { signal: AbortSignal.timeout(90000) } });
        if (data && data.status === "ok") {
            wcApiData.knockout = data;
        }
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcKnockout failed:", e.message);
        return null;
    }
}

// ── World Cup Team Outlook ──────────────────────────────────────────────

async function fetchWcTeamOutlook(team) {
    if (!team) return null;
    if (wcApiData.outlookCache[team]) return wcApiData.outlookCache[team];
    wcApiData.outlookLoading.add(team);
    try {
        const data = await fetchJson(`/world-cup/outlook/${encodeURIComponent(team)}`, {
            fetchOpts: { signal: AbortSignal.timeout(60000) },
        });
        if (data && data.status === "ok") {
            wcApiData.outlookCache[team] = data;
        }
        wcApiData.apiOnline = true;
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcTeamOutlook failed:", e.message);
        return null;
    } finally {
        wcApiData.outlookLoading.delete(team);
    }
}

function renderWcOutlook(outlook) {
    const z = appState.lang === "zh";
    const panel = document.getElementById("wc-outlook-panel");
    if (!panel) return;
    if (!outlook || outlook.status !== "ok") {
        panel.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:1rem">${z ? "暂无该球队的前景数据" : "No outlook data available for this team"}</p>`;
        return;
    }
    const data = outlook.outlook || outlook;

    function probBar(label, value, color) {
        const pct = Math.max(0, Math.min(100, (value || 0) * 100));
        const barColor = color || "var(--accent, #4f9cff)";
        return `<div class="prob-row" style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.4rem">
            <span style="min-width:60px;font-size:0.8rem;color:var(--text-muted)">${escapeHtml(label)}</span>
            <div class="probability-track" style="flex:1">
                <div class="probability-fill" style="width:${sanitizeCssPercent(pct)}%;background:${barColor}"></div>
            </div>
            <strong style="min-width:50px;text-align:right;font-size:0.85rem">${pct.toFixed(1)}%</strong>
        </div>`;
    }

    const gf = data.group_finish || {};
    const finishBars = ["p1st", "p2nd", "p3rd", "p4th", "p_advance"]
        .map((key, i) => {
            const label = z ? ["第1", "第2", "第3", "第4", "出线"][i] : ["1st", "2nd", "3rd", "4th", "Advance"][i];
            const colors = ["#4f9cff", "#6bcf7f", "#f5a623", "#e0556a", "#9b6cf5"];
            if (gf[key] === undefined || gf[key] === null) return "";
            return probBar(label, gf[key], colors[i]);
        })
        .join("");

    const groupRank = data.group_rank;
    const groupTeams = (data.group_teams || []).map((t, i) => {
        const rank = i + 1;
        const name = typeof t === "string" ? t : (t.team || t.name || "");
        const isCurrent = name === data.team;
        return `<span class="status-pill ${isCurrent ? "status-high" : "status-low"}" style="font-size:0.7rem;margin:0.1rem">${rank}. ${escapeHtml(name)}</span>`;
    }).join("");

    const kp = data.knockout_path || [];
    const roundLabels = z
        ? { round_of_32: "32强", round_of_16: "16强", quarter_finals: "四分之一决赛", semi_finals: "半决赛", final: "决赛" }
        : { round_of_32: "Round of 32", round_of_16: "Round of 16", quarter_finals: "Quarter-Final", semi_finals: "Semi-Final", final: "Final" };
    const pathHtml = kp.map((step) => {
        const opp = step.opponent;
        const advP = step.win_probability;
        const advPct = (advP === undefined || advP === null) ? null : Math.round(advP * 100);
        const oppName = opp ? escapeHtml(opp) : (z ? "未投影" : "Not projected");
        const advBadge = (advPct === null)
            ? ""
            : `<span class="status-pill ${advPct >= 50 ? "status-high" : "status-medium"}" style="font-size:0.65rem">${advPct}%</span>`;
        return `<div class="ko-path-step" style="display:flex;justify-content:space-between;align-items:center;padding:0.4rem 0;border-bottom:1px solid var(--border, rgba(255,255,255,0.08))">
            <span style="font-size:0.8rem;color:var(--text-muted)">${escapeHtml(roundLabels[step.round] || step.round)}</span>
            <span style="font-size:0.85rem;font-weight:600">${oppName}</span>
            ${advBadge}
        </div>`;
    }).join("");

    const champProb = data.championship_probability;
    const champPct = (champProb === undefined || champProb === null) ? null : (champProb * 100);

    const sb = data.strength_breakdown || {};
    const coverage = sb.coverage;
    const coveragePct = (coverage === undefined || coverage === null) ? null : Math.round(coverage * 100);
    const shrunkAvg = sb.shrunk_avg_rating;
    const coreAvg = sb.core_avg_rating;

    function _sbRow(label, value, fmt) {
        if (value === undefined || value === null) return "";
        const display = fmt ? fmt(value) : escapeHtml(String(value));
        return `<div><span style="color:var(--text-muted)">${escapeHtml(label)}: </span><strong>${display}</strong></div>`;
    }
    const rated = sb.rated_players;
    const total = sb.total_players;
    const ratedStr = (rated !== undefined && rated !== null && total !== undefined && total !== null)
        ? `${rated}/${total}` : null;
    const scorePct = (v) => (v === undefined || v === null) ? null : `${Math.round((v || 0) * 100)}%`;
    const balance = data.squad_balance || {};
    const roleLabels = z
        ? { GK: "门将", CB: "中卫", FB: "边后卫", DM: "后腰", CM: "中场", AM: "前腰", W: "边锋", ST: "中锋" }
        : { GK: "GK", CB: "CB", FB: "FB", DM: "DM", CM: "CM", AM: "AM", W: "W", ST: "ST" };
    const roleBalance = Object.entries(balance.roles || {}).map(([role, details]) => {
        const count = Number(details.count || 0);
        const target = Number(details.planning_target || 0);
        const state = String(details.depth_status || "unknown");
        const color = state === "deep" ? "status-high" : state === "adequate" ? "status-medium" : "status-low";
        return `<span class="status-pill ${color}" style="font-size:0.68rem;margin:0.12rem">${escapeHtml(roleLabels[role] || role)} ${count}/${target}</span>`;
    }).join("");
    const planningFlags = (balance.planning_flags || []).map((flag) =>
        `${roleLabels[flag.role] || flag.role} ${flag.count}/${flag.target}`
    );
    const balanceNote = balance.disclaimer
        ? `<p style="font-size:0.68rem;color:var(--text-muted);line-height:1.4;margin:0.45rem 0 0">${escapeHtml(balance.disclaimer)}</p>`
        : "";

    const disclaimer = data.disclaimer ? `<p style="font-size:0.72rem;color:var(--text-muted);margin-top:0.8rem;line-height:1.5">${escapeHtml(data.disclaimer)}</p>` : "";

    panel.innerHTML = `<div class="wc-outlook-content" style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
        <div>
            <h4 style="font-size:0.85rem;margin-bottom:0.5rem;color:var(--text-secondary, #ccc)">${z ? "小组名次概率" : "Group Finish Probability"}</h4>
            ${finishBars || `<p style="color:var(--text-muted);font-size:0.8rem">—</p>`}
            <div style="margin-top:0.6rem">
                <span style="font-size:0.75rem;color:var(--text-muted)">${z ? "小组排名" : "Group Rank"}: </span>
                <strong>${groupRank !== undefined && groupRank !== null ? `#${groupRank}` : "—"}</strong>
            </div>
            <div style="margin-top:0.4rem">${groupTeams}</div>
        </div>
        <div>
            <h4 style="font-size:0.85rem;margin-bottom:0.5rem;color:var(--text-secondary, #ccc)">${z ? "夺冠概率" : "Championship Probability"}</h4>
            ${champPct === null
                ? `<p style="color:var(--text-muted);font-size:0.8rem">—</p>`
                : `<div style="display:flex;align-items:baseline;gap:0.3rem">
                    <span style="font-size:1.8rem;font-weight:700;color:var(--accent, #4f9cff)">${champPct.toFixed(2)}%</span>
                </div>`
            }
            <h4 style="font-size:0.85rem;margin:0.8rem 0 0.5rem;color:var(--text-secondary, #ccc)">${z ? "阵容强度分解" : "Squad Strength Breakdown"}</h4>
            <div style="font-size:0.8rem;line-height:1.8">
                <div><span style="color:var(--text-muted)">${z ? "名单覆盖率" : "Squad Coverage"}: </span><strong>${coveragePct === null ? "—" : coveragePct + "%"}</strong></div>
                ${ratedStr ? _sbRow(z ? "已评分球员" : "Rated Players", ratedStr) : ""}
                ${_sbRow(z ? "收缩后平均评分" : "Shrunk Avg Rating", shrunkAvg, (v) => Number(v).toFixed(3))}
                ${_sbRow(z ? "核心球员平均评分" : "Core Avg Rating", coreAvg, (v) => Number(v).toFixed(3))}
                ${_sbRow(z ? "轮换球员平均评分" : "Depth Avg Rating", sb.depth_avg_rating, (v) => Number(v).toFixed(3))}
                ${_sbRow(z ? "替补球员平均评分" : "Reserve Avg Rating", sb.reserve_avg_rating, (v) => Number(v).toFixed(3))}
                ${_sbRow(z ? "阵容质量评分" : "Squad Quality Rating", sb.squad_quality_rating, (v) => Number(v).toFixed(3))}
                ${_sbRow(z ? "观察平均评分" : "Observed Avg Rating", sb.observed_avg_rating, (v) => Number(v).toFixed(3))}
                ${_sbRow(z ? "代理平均评分" : "Proxy Avg Rating", sb.proxy_avg_rating, (v) => Number(v).toFixed(3))}
            </div>
            <h4 style="font-size:0.8rem;margin:0.8rem 0 0.4rem;color:var(--text-secondary, #ccc)">${z ? "强度分量" : "Strength Components"}</h4>
            <div style="font-size:0.8rem;line-height:1.8">
                ${_sbRow(z ? "评分分量" : "Rating Score", scorePct(sb.rating_score))}
                ${_sbRow(z ? "Opta 分量" : "Opta Score", scorePct(sb.opta_score))}
                ${_sbRow(z ? "联赛分量" : "League Score", scorePct(sb.league_score))}
                ${_sbRow(z ? "覆盖分量" : "Coverage Score", scorePct(sb.coverage_score))}
                ${_sbRow(z ? "五大联赛分量" : "Big5 Score", scorePct(sb.big5_score))}
                ${_sbRow(z ? "五大联赛占比" : "Big5 Ratio", scorePct(sb.big5_ratio))}
            </div>
        </div>
    </div>
    <div style="margin-top:1rem">
        <h4 style="font-size:0.85rem;margin-bottom:0.5rem;color:var(--text-secondary, #ccc)">${z ? "阵容位置深度" : "Squad Role Depth"}</h4>
        <div>${roleBalance || `<span style="color:var(--text-muted);font-size:0.8rem">—</span>`}</div>
        ${planningFlags.length ? `<p style="font-size:0.72rem;color:var(--warn, #f5a623);margin:0.45rem 0 0">${escapeHtml(z ? "规划关注：" : "Planning flags: ")}${escapeHtml(planningFlags.join(" · "))}</p>` : ""}
        ${balanceNote}
    </div>
    <div style="margin-top:1rem">
        <h4 style="font-size:0.85rem;margin-bottom:0.5rem;color:var(--text-secondary, #ccc)">${z ? "淘汰赛投影路径" : "Projected Knockout Path"}</h4>
        ${pathHtml || `<p style="color:var(--text-muted);font-size:0.8rem">${z ? "未投影" : "Not projected"}</p>`}
    </div>
    ${disclaimer}`;
}

async function loadAndRenderWcOutlook(team) {
    const panel = document.getElementById("wc-outlook-panel");
    const z = appState.lang === "zh";
    if (panel && wcApiData.outlookLoading.has(team)) {
        panel.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:1rem">${z ? "加载中..." : "Loading..."}</p>`;
    }
    const data = await fetchWcTeamOutlook(team);
    renderWcOutlook(data);
}

// ── Tournament Simulator ────────────────────────────────────────────────

async function fetchWcTournamentSummary() {
    try {
        const data = await fetchJson("/world-cup/tournament/summary", {
            fetchOpts: { signal: AbortSignal.timeout(15000) },
        });
        if (data && data.status === "ok") {
            wcApiData.tournament = data;
            wcApiData.apiOnline = true;
        }
        return data;
    } catch (e) {
        console.warn("[WC Tournament] fetchWcTournamentSummary failed:", e.message);
        return null;
    }
}

async function fetchWcTournamentMatches(group) {
    const params = group ? `group=${encodeURIComponent(group)}` : "";
    try {
        const data = await fetchJson("/world-cup/tournament/matches", { params });
        if (data && data.status === "ok") {
            wcApiData.tournamentMatches = data;
            wcApiData.apiOnline = true;
        }
        return data;
    } catch (e) {
        console.warn("[WC Tournament] fetchWcTournamentMatches failed:", e.message);
        return null;
    }
}

async function fetchWcTournamentScenarios(team) {
    if (!team) return null;
    try {
        const data = await fetchJson(
            `/world-cup/tournament/scenarios/${encodeURIComponent(team)}`,
            { params: "max_scenarios=15" },
        );
        if (data && data.status === "ok") {
            if (!wcApiData.tournamentScenarios) wcApiData.tournamentScenarios = {};
            wcApiData.tournamentScenarios[team] = data;
            wcApiData.apiOnline = true;
        }
        return data;
    } catch (e) {
        console.warn("[WC Tournament] fetchWcTournamentScenarios failed:", e.message);
        return null;
    }
}

async function postTournamentResult(matchId, homeGoals, awayGoals) {
    const z = appState.lang === "zh";
    try {
        const params = `match_id=${encodeURIComponent(matchId)}&home_goals=${homeGoals}&away_goals=${awayGoals}`;
        const resp = await fetch(
            `${API_BASE}/world-cup/tournament/result?${params}`,
            { method: "POST", signal: AbortSignal.timeout(15000) },
        );
        const data = await resp.json();
        if (data && data.status === "ok") {
            wcApiData.apiOnline = true;
            return data;
        }
        alert((z ? "录入失败: " : "Apply failed: ") + (data?.message || "unknown"));
        return null;
    } catch (e) {
        alert((z ? "录入失败: " : "Apply failed: ") + e.message);
        return null;
    }
}

async function deleteTournamentResult(matchId) {
    const z = appState.lang === "zh";
    try {
        const params = `match_id=${encodeURIComponent(matchId)}`;
        const resp = await fetch(
            `${API_BASE}/world-cup/tournament/result?${params}`,
            { method: "DELETE", signal: AbortSignal.timeout(15000) },
        );
        const data = await resp.json();
        if (data && data.status === "ok") {
            wcApiData.apiOnline = true;
            return data;
        }
        alert((z ? "清除失败: " : "Clear failed: ") + (data?.message || "unknown"));
        return null;
    } catch (e) {
        alert((z ? "清除失败: " : "Clear failed: ") + e.message);
        return null;
    }
}

async function resetTournament() {
    const z = appState.lang === "zh";
    if (!confirm(z ? "重置所有比赛结果？" : "Reset all match results?")) return;
    try {
        const resp = await fetch(`${API_BASE}/world-cup/tournament/reset`, {
            method: "POST",
            signal: AbortSignal.timeout(15000),
        });
        const data = await resp.json();
        if (data && data.status === "ok") {
            wcApiData.tournament = data.summary;
            wcApiData.tournamentScenarios = {};
            wcApiData.apiOnline = true;
            return data;
        }
        return null;
    } catch (e) {
        alert((z ? "重置失败: " : "Reset failed: ") + e.message);
        return null;
    }
}

async function loadAndRenderWcTournament() {
    const z = appState.lang === "zh";
    const statusEl = document.getElementById("wc-tournament-status");
    if (statusEl) {
        statusEl.textContent = z ? "加载中..." : "Loading...";
        statusEl.className = "status-pill status-medium";
    }
    wcApiData.tournamentLoading = true;
    await Promise.all([
        fetchWcTournamentSummary(),
        fetchWcTournamentMatches(wcApiData.tournamentSelectedGroup),
    ]);
    wcApiData.tournamentLoading = false;
    renderWcTournament();
}

function renderWcTournament() {
    const z = appState.lang === "zh";
    const root = document.getElementById("wc-tournament-root");
    if (!root) return;

    const data = wcApiData.tournament;
    const matchesData = wcApiData.tournamentMatches;

    // Status pill
    const statusEl = document.getElementById("wc-tournament-status");
    if (statusEl) {
        if (!data) {
            statusEl.textContent = "API OFFLINE";
            statusEl.className = "status-pill status-low";
        } else if (wcApiData.apiOnline) {
            statusEl.textContent = "LIVE";
            statusEl.className = "status-pill status-high";
        } else {
            statusEl.textContent = "STATIC";
            statusEl.className = "status-pill status-medium";
        }
        statusEl.style.fontSize = "0.65rem";
    }

    if (!data) {
        root.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:2rem">${z ? "锦标赛数据加载中..." : "Loading tournament data..."}</p>`;
        return;
    }

    const completed = data.completed_matches || 0;
    const total = data.total_matches || 72;
    const pct = total ? Math.round((completed / total) * 100) : 0;
    const groupsComplete = data.groups_complete || 0;

    // Group selector
    const groupLetters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"];
    const selectedGroup = wcApiData.tournamentSelectedGroup || "A";
    const groupOptions = groupLetters.map(
        (g) => `<option value="${g}"${g === selectedGroup ? " selected" : ""}>${z ? `小组 ${g}` : `Group ${g}`}</option>`,
    ).join("");

    // Standings for selected group
    const groupStandings = (data.standings && data.standings[selectedGroup]) || [];

    // Best thirds (list of dicts)
    const bestThirds = data.best_thirds || [];

    // Advancing (winners/runners_up are lists of dicts with 'team' key)
    const adv = data.advancing || { winners: [], runners_up: [], best_thirds: [], all_advancing: [], provisional: true };
    const winnerTeams = (adv.winners || []).map((w) => w.team || w);
    const runnerUpTeams = (adv.runners_up || []).map((r) => r.team || r);
    const bestThirdTeams = (bestThirds || []).slice(0, 8);

    // Matches list
    const matches = (matchesData && matchesData.matches) || [];

    root.innerHTML = `
        <article class="liquid-panel compact" style="margin-bottom:1rem">
            <div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center">
                <div>
                    <span class="metric-value">${completed}/${total}</span>
                    <span>${z ? "比赛已录入" : "matches recorded"}</span>
                </div>
                <div>
                    <span class="metric-value">${pct}%</span>
                    <span>${z ? "完成度" : "complete"}</span>
                </div>
                <div>
                    <span class="metric-value">${groupsComplete}/12</span>
                    <span>${z ? "小组完赛" : "groups done"}</span>
                </div>
                <div>
                    <span class="metric-value">${adv.all_advancing ? adv.all_advancing.length : 0}</span>
                    <span>${z ? "已出线" : "advancing"}</span>
                </div>
                <button class="text-button" id="wc-tournament-refresh" type="button">↻ ${z ? "刷新" : "Refresh"}</button>
                <button class="text-button" id="wc-tournament-reset" type="button" style="color:var(--status-low)">${z ? "重置全部" : "Reset All"}</button>
            </div>
        </article>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem" class="wc-tournament-grid">
            <article class="liquid-panel compact">
                <div class="panel-head">
                    <h3>${z ? "小组积分榜" : "Group Standings"}</h3>
                    <select id="wc-tournament-group-select" class="filter-select" style="min-width:80px">${groupOptions}</select>
                </div>
                <div class="table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>${z ? "球队" : "Team"}</th>
                                <th>P</th>
                                <th>W</th>
                                <th>D</th>
                                <th>L</th>
                                <th>GF</th>
                                <th>GA</th>
                                <th>GD</th>
                                <th>Pts</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${groupStandings.map((s, i) => {
                                const pos = i + 1;
                                const cls = pos === 1 ? "status-high" : pos === 2 ? "status-medium" : (pos === 3 ? "status-low" : "");
                                return `<tr>
                                    <td><span class="status-pill ${cls}" style="font-size:0.6rem">${pos}</span></td>
                                    <td>${escapeHtml(s.team)}</td>
                                    <td>${s.played}</td>
                                    <td>${s.won}</td>
                                    <td>${s.drawn}</td>
                                    <td>${s.lost}</td>
                                    <td>${s.goals_for}</td>
                                    <td>${s.goals_against}</td>
                                    <td>${s.goal_difference >= 0 ? "+" : ""}${s.goal_difference}</td>
                                    <td><strong>${s.points}</strong></td>
                                </tr>`;
                            }).join("")}
                        </tbody>
                    </table>
                </div>
                <p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.5rem">
                    ${z ? "前 2 名直接出线，第 3 名参与最佳小组第三评比" : "Top 2 advance; 3rd enters best-thirds ranking"}
                </p>
            </article>

            <article class="liquid-panel compact">
                <div class="panel-head">
                    <h3>${z ? "比赛录入" : "Match Entry"}</h3>
                </div>
                <div class="table-scroll" style="max-height:400px;overflow-y:auto">
                    <table>
                        <thead>
                            <tr>
                                <th>${z ? "比赛日" : "MD"}</th>
                                <th>${z ? "主队" : "Home"}</th>
                                <th>${z ? "比分" : "Score"}</th>
                                <th>${z ? "客队" : "Away"}</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            ${matches.map((m) => {
                                if (m.completed) {
                                    return `<tr>
                                        <td>${m.matchday}</td>
                                        <td>${escapeHtml(m.home)}</td>
                                        <td><strong>${m.result.home_goals}-${m.result.away_goals}</strong></td>
                                        <td>${escapeHtml(m.away)}</td>
                                        <td><button class="text-button wc-tournament-clear" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.7rem;padding:0.2rem 0.5rem">${z ? "清除" : "Clear"}</button></td>
                                    </tr>`;
                                }
                                return `<tr>
                                    <td>${m.matchday}</td>
                                    <td>${escapeHtml(m.home)}</td>
                                    <td>
                                        <input type="number" min="0" max="30" class="wc-tournament-input" data-match-id="${escapeAttr(m.match_id)}" data-side="home" style="width:2.5rem" placeholder="-">
                                        <span style="margin:0 0.2rem">:</span>
                                        <input type="number" min="0" max="30" class="wc-tournament-input" data-match-id="${escapeAttr(m.match_id)}" data-side="away" style="width:2.5rem" placeholder="-">
                                    </td>
                                    <td>${escapeHtml(m.away)}</td>
                                    <td><button class="text-button wc-tournament-apply" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.7rem;padding:0.2rem 0.5rem">${z ? "录入" : "Apply"}</button></td>
                                </tr>`;
                            }).join("")}
                        </tbody>
                    </table>
                </div>
            </article>
        </div>

        <article class="liquid-panel compact" style="margin-bottom:1rem">
            <div class="panel-head">
                <h3>${z ? "出线球队" : "Advancing Teams"}</h3>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem" class="wc-advancing-grid">
                <div>
                    <h4 style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.4rem">${z ? "小组第一" : "Group Winners"}</h4>
                    <div>${winnerTeams.length ? winnerTeams.map((t) => `<span class="status-pill status-high" style="font-size:0.7rem;margin:0.1rem">${escapeHtml(t)}</span>`).join("") : `<span style="color:var(--text-muted);font-size:0.8rem">${z ? "待定" : "TBD"}</span>`}</div>
                </div>
                <div>
                    <h4 style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.4rem">${z ? "小组第二" : "Runners-Up"}</h4>
                    <div>${runnerUpTeams.length ? runnerUpTeams.map((t) => `<span class="status-pill status-medium" style="font-size:0.7rem;margin:0.1rem">${escapeHtml(t)}</span>`).join("") : `<span style="color:var(--text-muted);font-size:0.8rem">${z ? "待定" : "TBD"}</span>`}</div>
                </div>
                <div>
                    <h4 style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.4rem">${z ? "最佳小组第三" : "Best Thirds"}</h4>
                    <div>${bestThirdTeams.length ? bestThirdTeams.map((t) => `<span class="status-pill status-low" style="font-size:0.7rem;margin:0.1rem">${escapeHtml(t.team)}${t.provisional ? "*" : ""}</span>`).join("") : `<span style="color:var(--text-muted);font-size:0.8rem">${z ? "待定" : "TBD"}</span>`}</div>
                    ${adv.provisional ? `<p style="font-size:0.7rem;color:var(--text-muted);margin-top:0.3rem">${z ? "(暂定，小组赛未完赛)" : "(provisional)"}</p>` : ""}
                </div>
            </div>
        </article>

        <article class="liquid-panel compact">
            <div class="panel-head">
                <h3>${z ? "小组赛模拟" : "Group Stage Simulation"}</h3>
                <div style="display:flex;gap:0.5rem;align-items:center">
                    <select id="wc-tournament-sim-mode" class="filter-select" style="min-width:100px">
                        <option value="random">${z ? "随机" : "Random"}</option>
                        <option value="strength">${z ? "实力加权" : "Strength"}</option>
                    </select>
                    <button class="text-button" id="wc-tournament-sim-btn" type="button">${z ? "模拟" : "Simulate"}</button>
                </div>
            </div>
            <div id="wc-tournament-sim-panel">
                <p style="color:var(--text-muted);text-align:center;padding:1rem;font-size:0.85rem">
                    ${z ? "点击「模拟」批量模拟剩余小组赛" : "Click \"Simulate\" to bulk-simulate remaining group matches"}
                </p>
            </div>
        </article>

        <article class="liquid-panel compact">
            <div class="panel-head">
                <h3>${z ? "出线情景分析" : "Qualification Scenarios"}</h3>
                <div style="display:flex;gap:0.5rem;align-items:center">
                    <select id="wc-tournament-scenario-team" class="filter-select" style="min-width:200px">
                        ${groupStandings.map((s) => `<option value="${escapeAttr(s.team)}">${escapeHtml(s.team)}</option>`).join("")}
                    </select>
                    <button class="text-button" id="wc-tournament-scenario-btn" type="button">${z ? "计算" : "Compute"}</button>
                </div>
            </div>
            <div id="wc-tournament-scenarios-panel">
                <p style="color:var(--text-muted);text-align:center;padding:1rem;font-size:0.85rem">
                    ${z ? "选择一支球队查看出线情景" : "Select a team to view qualification scenarios"}
                </p>
            </div>
        </article>

        <article class="liquid-panel compact">
            <div class="panel-head">
                <h3>${z ? "小组赛模拟器" : "Group Stage Simulator"}</h3>
                <div style="display:flex;gap:0.5rem;align-items:center">
                    <select id="wc-grpsim-mode" class="filter-select" style="min-width:100px">
                        <option value="random">${z ? "随机" : "Random"}</option>
                        <option value="strength">${z ? "实力加权" : "Strength"}</option>
                    </select>
                    <select id="wc-grpsim-iter" class="filter-select" style="min-width:80px">
                        <option value="500">500</option>
                        <option value="1000" selected>1000</option>
                        <option value="3000">3000</option>
                    </select>
                    <button class="text-button" id="wc-grpsim-btn" type="button">${z ? "模拟" : "Simulate"}</button>
                </div>
            </div>
            <div id="wc-grpsim-panel">
                <p style="color:var(--text-muted);text-align:center;padding:1rem;font-size:0.85rem">
                    ${z ? "点击「模拟」批量模拟剩余小组赛，查看出线概率" : "Click \"Simulate\" to run remaining group matches and see advancement odds"}
                </p>
            </div>
        </article>

        <article class="liquid-panel compact" style="margin-top:1rem">
            <div class="panel-head">
                <h3>${z ? "淘汰赛对阵图" : "Knockout Bracket"}</h3>
                <div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap">
                    <button class="text-button" id="wc-ko-generate" type="button" style="font-size:0.75rem">${z ? "生成对阵" : "Generate Bracket"}</button>
                    <button class="text-button" id="wc-ko-refresh" type="button" style="font-size:0.75rem">↻</button>
                    <select id="wc-ko-scenario-team" class="filter-select" style="min-width:160px;font-size:0.7rem" data-placeholder="${z ? "夺冠情景" : "Championship Scenarios"}">
                        <option value="">${z ? "— 夺冠情景 —" : "— Scenarios —"}</option>
                    </select>
                    <button class="text-button" id="wc-ko-scenario-btn" type="button" style="font-size:0.75rem">${z ? "分析" : "Analyze"}</button>
                    <button class="text-button" id="wc-ko-share" type="button" style="font-size:0.75rem">${z ? "分享" : "Share"}</button>
                    <button class="text-button" id="wc-ko-import" type="button" style="font-size:0.75rem">${z ? "导入" : "Import"}</button>
                    <button class="text-button" id="wc-ko-print" type="button" style="font-size:0.75rem">🖨</button>
                </div>
            </div>
            <div id="wc-ko-bracket-panel">
                <p style="color:var(--text-muted);text-align:center;padding:1rem;font-size:0.85rem">
                    ${z ? "点击「生成对阵」从小组赛成绩创建淘汰赛对阵图" : "Click \"Generate Bracket\" to create the knockout bracket from group results"}
                </p>
            </div>
        </article>
    `;

    // Bind event listeners
    const groupSelect = document.getElementById("wc-tournament-group-select");
    if (groupSelect && !groupSelect.dataset.bound) {
        groupSelect.dataset.bound = "1";
        groupSelect.addEventListener("change", async (e) => {
            wcApiData.tournamentSelectedGroup = e.target.value;
            await fetchWcTournamentMatches(e.target.value);
            await fetchWcTournamentSummary();
            renderWcTournament();
        });
    }

    const refreshBtn = document.getElementById("wc-tournament-refresh");
    if (refreshBtn && !refreshBtn.dataset.bound) {
        refreshBtn.dataset.bound = "1";
        refreshBtn.addEventListener("click", () => loadAndRenderWcTournament());
    }

    const resetBtn = document.getElementById("wc-tournament-reset");
    if (resetBtn && !resetBtn.dataset.bound) {
        resetBtn.dataset.bound = "1";
        resetBtn.addEventListener("click", async () => {
            await resetTournament();
            await fetchWcTournamentMatches(wcApiData.tournamentSelectedGroup);
            renderWcTournament();
        });
    }

    // Apply result buttons
    root.querySelectorAll(".wc-tournament-apply").forEach((btn) => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = "1";
        btn.addEventListener("click", async (e) => {
            const matchId = e.target.dataset.matchId;
            const homeInput = root.querySelector(`input[data-match-id="${CSS.escape(matchId)}"][data-side="home"]`);
            const awayInput = root.querySelector(`input[data-match-id="${CSS.escape(matchId)}"][data-side="away"]`);
            const hg = homeInput ? parseInt(homeInput.value, 10) : NaN;
            const ag = awayInput ? parseInt(awayInput.value, 10) : NaN;
            if (isNaN(hg) || isNaN(ag) || hg < 0 || ag < 0 || hg > 30 || ag > 30) {
                alert(z ? "请输入 0-30 的有效比分" : "Enter valid scores (0-30)");
                return;
            }
            const result = await postTournamentResult(matchId, hg, ag);
            if (result && result.status === "ok") {
                // Refresh summary and matches, then re-render
                await Promise.all([
                    fetchWcTournamentSummary(),
                    fetchWcTournamentMatches(wcApiData.tournamentSelectedGroup),
                ]);
                renderWcTournament();
            }
        });
    });

    // Clear result buttons
    root.querySelectorAll(".wc-tournament-clear").forEach((btn) => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = "1";
        btn.addEventListener("click", async (e) => {
            const matchId = e.target.dataset.matchId;
            const result = await deleteTournamentResult(matchId);
            if (result && result.status === "ok") {
                await Promise.all([
                    fetchWcTournamentSummary(),
                    fetchWcTournamentMatches(wcApiData.tournamentSelectedGroup),
                ]);
                renderWcTournament();
            }
        });
    });

    // Scenario compute button
    const scenBtn = document.getElementById("wc-tournament-scenario-btn");
    if (scenBtn && !scenBtn.dataset.bound) {
        scenBtn.dataset.bound = "1";
        scenBtn.addEventListener("click", async () => {
            const team = document.getElementById("wc-tournament-scenario-team").value;
            await fetchWcTournamentScenarios(team);
            renderWcTournamentScenarios(team);
        });
    }

    // Knockout bracket buttons
    const koGenBtn = document.getElementById("wc-ko-generate");
    if (koGenBtn && !koGenBtn.dataset.bound) {
        koGenBtn.dataset.bound = "1";
        koGenBtn.addEventListener("click", async () => {
            koGenBtn.disabled = true;
            koGenBtn.textContent = z ? "生成中..." : "Generating...";
            await generateKnockoutBracket();
            koGenBtn.disabled = false;
            koGenBtn.textContent = z ? "生成对阵" : "Generate Bracket";
        });
    }

    const koRefreshBtn = document.getElementById("wc-ko-refresh");
    if (koRefreshBtn && !koRefreshBtn.dataset.bound) {
        koRefreshBtn.dataset.bound = "1";
        koRefreshBtn.addEventListener("click", async () => {
            await fetchWcKnockoutBracket();
            renderWcKnockoutBracket();
        });
    }

    // Group stage simulator button
    const grpSimBtn = document.getElementById("wc-grpsim-btn");
    if (grpSimBtn && !grpSimBtn.dataset.bound) {
        grpSimBtn.dataset.bound = "1";
        grpSimBtn.addEventListener("click", async () => {
            const mode = document.getElementById("wc-grpsim-mode").value;
            const iter = parseInt(document.getElementById("wc-grpsim-iter").value, 10) || 1000;
            grpSimBtn.disabled = true;
            grpSimBtn.textContent = z ? "模拟中..." : "Simulating...";
            await fetchWcGroupStageSimulation(mode, iter);
            renderWcGroupStageSimulation();
            grpSimBtn.disabled = false;
            grpSimBtn.textContent = z ? "模拟" : "Simulate";
        });
    }

    // Knockout scenarios analyze button
    const koScenBtn = document.getElementById("wc-ko-scenario-btn");
    if (koScenBtn && !koScenBtn.dataset.bound) {
        koScenBtn.dataset.bound = "1";
        koScenBtn.addEventListener("click", async () => {
            const team = document.getElementById("wc-ko-scenario-team").value;
            if (!team) return;
            koScenBtn.disabled = true;
            koScenBtn.textContent = z ? "分析中..." : "Analyzing...";
            await fetchWcKnockoutScenarios(team);
            renderWcKnockoutScenarios(team);
            koScenBtn.disabled = false;
            koScenBtn.textContent = z ? "分析" : "Analyze";
        });
    }

    // Populate knockout scenario team dropdown from bracket R32 teams
    const koScenTeam = document.getElementById("wc-ko-scenario-team");
    if (koScenTeam && wcApiData.knockoutBracket && wcApiData.knockoutBracket.rounds) {
        const r32Teams = [];
        const r32 = wcApiData.knockoutBracket.rounds.r32;
        if (r32 && r32.matches) {
            for (const m of r32.matches) {
                if (m.home) r32Teams.push(m.home);
                if (m.away) r32Teams.push(m.away);
            }
        }
        const currentVal = koScenTeam.value;
        koScenTeam.innerHTML = `<option value="">${z ? "— 夺冠情景 —" : "— Scenarios —"}</option>` +
            r32Teams.map((t) => `<option value="${escapeAttr(t)}">${escapeHtml(t)}</option>`).join("");
        if (currentVal) koScenTeam.value = currentVal;
    }

    // Share button — export tournament state as base64url-encoded string
    const koShareBtn = document.getElementById("wc-ko-share");
    if (koShareBtn && !koShareBtn.dataset.bound) {
        koShareBtn.dataset.bound = "1";
        koShareBtn.addEventListener("click", async () => {
            koShareBtn.disabled = true;
            koShareBtn.textContent = z ? "导出中..." : "Exporting...";
            await fetchWcTournamentExport();
            renderWcShareDialog();
            koShareBtn.disabled = false;
            koShareBtn.textContent = z ? "分享" : "Share";
        });
    }

    // Import button — show import dialog for encoded state string
    const koImportBtn = document.getElementById("wc-ko-import");
    if (koImportBtn && !koImportBtn.dataset.bound) {
        koImportBtn.dataset.bound = "1";
        koImportBtn.addEventListener("click", () => {
            renderWcImportDialog();
        });
    }

    // Print button — trigger print/PDF export of bracket
    const koPrintBtn = document.getElementById("wc-ko-print");
    if (koPrintBtn && !koPrintBtn.dataset.bound) {
        koPrintBtn.dataset.bound = "1";
        koPrintBtn.addEventListener("click", () => {
            window.print();
        });
    }

    // Auto-render knockout bracket if data is available
    if (wcApiData.knockoutBracket) {
        renderWcKnockoutBracket();
    } else {
        // Try fetching silently
        fetchWcKnockoutBracket().then(() => renderWcKnockoutBracket());
    }
}

function renderWcTournamentScenarios(team) {
    const z = appState.lang === "zh";
    const panel = document.getElementById("wc-tournament-scenarios-panel");
    if (!panel) return;

    const data = wcApiData.tournamentScenarios && wcApiData.tournamentScenarios[team];
    if (!data || data.status !== "ok") {
        panel.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:1rem;font-size:0.85rem">${z ? "无情景数据" : "No scenario data"}</p>`;
        return;
    }

    const prob = data.advance_probability || 0;
    const probPct = (prob * 100).toFixed(1);
    const probCls = prob >= 0.7 ? "status-high" : (prob >= 0.3 ? "status-medium" : "status-low");

    const scenarios = data.scenarios || [];
    const remaining = data.remaining_matches || [];

    panel.innerHTML = `
        <div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center;margin-bottom:0.8rem">
            <div>
                <span class="status-pill ${probCls}" style="font-size:0.8rem">
                    ${z ? "出线概率" : "Advance prob"}: ${probPct}%
                </span>
            </div>
            <div style="color:var(--text-muted);font-size:0.85rem">
                ${z ? "剩余比赛" : "Remaining"}: ${remaining.length}  ·  ${z ? "情景数" : "Scenarios"}: ${scenarios.length}
            </div>
        </div>
        <p style="font-size:0.85rem;margin-bottom:0.8rem">${escapeHtml(data.summary || "")}</p>
        ${scenarios.length === 0 ? "" : `
            <div class="table-scroll" style="max-height:300px;overflow-y:auto">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>${z ? "路径" : "Path"}</th>
                            <th>${z ? "结果" : "Result"}</th>
                            <th>${z ? "描述" : "Description"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${scenarios.map((sc, i) => {
                            const tagCls = sc.advances ? "status-high" : "status-low";
                            const tag = sc.advances ? (z ? "出线" : "ADV") : (z ? "出局" : "OUT");
                            const pathLabel = {
                                winner: z ? "小组第一" : "Winner",
                                "runner-up": z ? "小组第二" : "Runner-up",
                                "best-third": z ? "最佳第三" : "Best 3rd",
                                eliminated: z ? "淘汰" : "Eliminated",
                            }[sc.advance_path] || sc.advance_path;
                            return `<tr>
                                <td>${i + 1}</td>
                                <td><span class="status-pill ${tagCls}" style="font-size:0.65rem">${pathLabel}</span></td>
                                <td>${tag}</td>
                                <td style="font-size:0.75rem">${escapeHtml(sc.description || "")}</td>
                            </tr>`;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        `}
    `;
}

async function fetchWcKnockoutBracket() {
    try {
        const data = await fetchJson("/world-cup/tournament/knockout");
        if (data && data.status === "ok") {
            wcApiData.knockoutBracket = data;
        }
    } catch (e) {
        // Silent fail — bracket may not be generated yet
    }
}

async function generateKnockoutBracket() {
    try {
        const data = await fetchJson("/world-cup/tournament/knockout/generate", {
            method: "POST",
        });
        if (data && data.status === "ok") {
            wcApiData.knockoutProbabilities = null;  // invalidate cache
            await fetchWcKnockoutBracket();
            renderWcKnockoutBracket();
        } else if (data && data.message) {
            alert(data.message);
        }
    } catch (e) {
        alert((appState.lang === "zh" ? "生成失败: " : "Generate failed: ") + e.message);
    }
}

async function applyKnockoutResult(matchId, homeGoals, awayGoals, penaltiesWinner) {
    let url = `/world-cup/tournament/knockout/result?match_id=${encodeURIComponent(matchId)}&home_goals=${homeGoals}&away_goals=${awayGoals}`;
    if (penaltiesWinner) url += `&penalties_winner=${encodeURIComponent(penaltiesWinner)}`;
    try {
        const data = await fetchJson(url, { method: "POST" });
        if (data && data.status === "ok") {
            wcApiData.knockoutProbabilities = null;  // invalidate cache
            delete wcApiData.knockoutReviews[matchId];
            await fetchWcKnockoutBracket();
            renderWcKnockoutBracket();
        } else if (data && data.message) {
            alert(data.message);
        }
    } catch (e) {
        alert((appState.lang === "zh" ? "录入失败: " : "Apply failed: ") + e.message);
    }
}

async function clearKnockoutResult(matchId) {
    const url = `/world-cup/tournament/knockout/result?match_id=${encodeURIComponent(matchId)}`;
    try {
        const data = await fetchJson(url, { method: "DELETE" });
        if (data && data.status === "ok") {
            wcApiData.knockoutProbabilities = null;  // invalidate cache
            delete wcApiData.knockoutReviews[matchId];
            await fetchWcKnockoutBracket();
            renderWcKnockoutBracket();
        }
    } catch (e) {
        // Silent fail
    }
}

async function fetchWcKnockoutReview(matchId) {
    try {
        const review = await fetchJson(`/world-cup/tournament/knockout/${encodeURIComponent(matchId)}/review`);
        if (review) {
            wcApiData.knockoutReviews[matchId] = review;
            renderWcKnockoutBracket();
        }
        return review;
    } catch (err) {
        console.warn("[WC] knockout result review failed:", err);
        return null;
    }
}

function downloadWcKnockoutReview(review) {
    if (!review) return;
    const matchId = String(review.match_id || "knockout-match").replace(/[^a-z0-9_-]+/gi, "-");
    const payload = {
        ...review,
        exported_at: new Date().toISOString(),
        export_scope: "browser download; the recorded tournament result remains local to this ScoutFootball instance",
    };
    _downloadLocalBriefing(
        JSON.stringify(payload, null, 2),
        `scoutfootball-${matchId}-local-result-review.json`,
        "application/json;charset=utf-8",
    );
}

async function fetchWcKnockoutProbabilities() {
    try {
        const data = await fetchJson("/world-cup/tournament/knockout/probabilities");
        if (data && data.status === "ok") {
            wcApiData.knockoutProbabilities = data;
        } else {
            wcApiData.knockoutProbabilities = null;
        }
    } catch (e) {
        wcApiData.knockoutProbabilities = null;
    }
}

async function fetchWcKnockoutScenarios(team) {
    try {
        const data = await fetchJson(`/world-cup/tournament/knockout/scenarios/${encodeURIComponent(team)}?num_simulations=5000`);
        if (data) {
            wcApiData.knockoutScenarios[team] = data;
        }
    } catch (e) {
        wcApiData.knockoutScenarios[team] = { status: "error", message: String(e) };
    }
}

async function fetchWcGroupStageSimulation(mode, iterations) {
    try {
        const data = await fetchJson(`/world-cup/tournament/group-simulation?mode=${mode}&num_simulations=${iterations}`);
        if (data && data.status === "ok") {
            wcApiData.groupStageSimulation = data;
        } else {
            wcApiData.groupStageSimulation = null;
        }
    } catch (e) {
        wcApiData.groupStageSimulation = null;
    }
}

function renderWcKnockoutScenarios(team) {
    const z = appState.lang === "zh";
    const data = wcApiData.knockoutScenarios[team];
    if (!data || data.status !== "ok") {
        alert(data && data.message ? data.message : (z ? "无法获取情景数据" : "Failed to load scenario data"));
        return;
    }

    // Render scenario panel as an overlay inserted before the bracket panel
    const bracketPanel = document.getElementById("wc-ko-bracket-panel");
    if (!bracketPanel) return;

    let scenPanel = document.getElementById("wc-ko-scenarios-display");
    if (!scenPanel) {
        scenPanel = document.createElement("div");
        scenPanel.id = "wc-ko-scenarios-display";
        bracketPanel.parentElement.insertBefore(scenPanel, bracketPanel);
    }

    const basePct = (data.current_championship_probability * 100).toFixed(2);
    const nm = data.next_match;
    const scenarios = data.scenarios || [];

    let html = `<div style="padding:0.8rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:6px;background:var(--panel-bg,rgba(255,255,255,0.03));margin-bottom:1rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem">
            <h4 style="font-size:0.9rem">${escapeHtml(team)} ${z ? "夺冠情景分析" : "Championship Scenarios"}</h4>
            <button class="text-button" onclick="document.getElementById('wc-ko-scenarios-display').remove()" style="font-size:0.7rem;padding:0.2rem 0.5rem">✕</button>
        </div>
        <div style="font-size:0.8rem;margin-bottom:0.6rem">
            <span style="color:var(--text-muted)">${z ? "当前夺冠概率" : "Current Championship Prob"}:</span>
            <span style="font-weight:bold;margin-left:0.5rem;color:var(--accent-color,#4a9eff)">${basePct}%</span>
        </div>`;

    if (nm) {
        const winPct = nm.win_probability !== null ? (nm.win_probability * 100).toFixed(1) + "%" : "—";
        html += `<div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.4rem">
            ${z ? "下一场" : "Next match"}: ${escapeHtml(nm.round).toUpperCase()} ${nm.match_id || ""}
            ${nm.opponent ? ` — ${z ? "对手" : "vs"} <span style="color:var(--text)">${escapeHtml(nm.opponent)}</span>` : ` (${z ? "对手待定" : "TBD"})`}
            ${nm.win_probability !== null ? ` (${z ? "胜率" : "Win"} ${winPct})` : ""}
        </div>`;
    }

    if (scenarios.length > 0) {
        const roundLabels = z ? {
            r32: "32强", r16: "16强", qf: "四分之一", sf: "半决赛", final: "决赛",
        } : {
            r32: "R32", r16: "R16", qf: "QF", sf: "SF", final: "Final",
        };
        html += `<table style="width:100%;font-size:0.75rem;border-collapse:collapse">
            <thead><tr style="border-bottom:1px solid var(--border-color,rgba(255,255,255,0.1))">
                <th style="text-align:left;padding:0.3rem">${z ? "轮次" : "Round"}</th>
                <th style="text-align:left;padding:0.3rem">${z ? "对手" : "Opponent"}</th>
                <th style="text-align:right;padding:0.3rem">${z ? "胜率" : "Win Prob"}</th>
                <th style="text-align:right;padding:0.3rem">${z ? "夺冠(若胜)" : "Champ If Win"}</th>
            </tr></thead><tbody>`;
        for (const s of scenarios) {
            const label = roundLabels[s.round] || s.round;
            const opp = s.opponent ? escapeHtml(s.opponent) : `<span style="color:var(--text-muted)">TBD</span>`;
            const wp = s.match_win_probability !== null && s.match_win_probability !== undefined
                ? (s.match_win_probability * 100).toFixed(1) + "%" : "—";
            const champIfWin = s.championship_if_win !== undefined
                ? (s.championship_if_win * 100).toFixed(2) + "%" : "—";
            const champIfReach = s.championship_if_reach !== undefined
                ? (s.championship_if_reach * 100).toFixed(2) + "%" : null;
            html += `<tr style="border-bottom:1px solid var(--border-color,rgba(255,255,255,0.05))">
                <td style="padding:0.3rem">${label}</td>
                <td style="padding:0.3rem">${opp}</td>
                <td style="text-align:right;padding:0.3rem">${wp}</td>
                <td style="text-align:right;padding:0.3rem;color:var(--accent-color,#4a9eff)">${champIfWin}</td>
            </tr>`;
            if (champIfReach) {
                html += `<tr style="font-size:0.65rem;color:var(--text-muted)">
                    <td colspan="4" style="padding:0.1rem 0.3rem 0.3rem">${z ? "若到达此轮，夺冠概率" : "If reach this round"}: ${champIfReach}</td>
                </tr>`;
            }
        }
        html += `</tbody></table>`;
    }

    if (data.disclaimer) {
        html += `<p style="font-size:0.65rem;color:var(--text-muted);margin-top:0.5rem">${escapeHtml(data.disclaimer)}</p>`;
    }
    html += `</div>`;

    scenPanel.innerHTML = html;
}

async function fetchWcTournamentExport() {
    try {
        const data = await fetchJson(`/world-cup/tournament/export`);
        if (data && data.status === "ok") {
            wcApiData.tournamentExport = data;
        } else {
            wcApiData.tournamentExport = null;
        }
    } catch (e) {
        wcApiData.tournamentExport = null;
    }
}

async function fetchWcTournamentImport(encoded) {
    try {
        const resp = await fetch(`${API_BASE}/world-cup/tournament/import`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ encoded }),
        });
        const data = await resp.json();
        return data;
    } catch (e) {
        return { status: "error", code: "request_failed", message: String(e) };
    }
}

function renderWcShareDialog() {
    const z = appState.lang === "zh";
    const data = wcApiData.tournamentExport;
    if (!data || data.status !== "ok") {
        alert(z ? "导出失败，请检查 API 是否在线" : "Export failed. Check if API is online.");
        return;
    }

    const bracketPanel = document.getElementById("wc-ko-bracket-panel");
    if (!bracketPanel) return;

    let dlg = document.getElementById("wc-ko-share-dialog");
    if (!dlg) {
        dlg = document.createElement("div");
        dlg.id = "wc-ko-share-dialog";
        bracketPanel.parentElement.insertBefore(dlg, bracketPanel);
    }

    const encoded = data.encoded || "";
    const sizeKb = ((data.state_size || 0) / 1024).toFixed(1);
    const fullJson = JSON.stringify({
        format: data.format,
        schema_version: data.schema_version,
        encoded,
        exported_at: data.exported_at,
    }, null, 2);

    dlg.innerHTML = `<div style="padding:0.8rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:6px;background:var(--panel-bg,rgba(255,255,255,0.03));margin-bottom:1rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem">
            <h4 style="font-size:0.9rem">${z ? "分享锦标赛状态" : "Share Tournament State"}</h4>
            <button class="text-button" onclick="document.getElementById('wc-ko-share-dialog').remove()" style="font-size:0.7rem;padding:0.2rem 0.5rem">✕</button>
        </div>
        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.4rem">
            ${z ? "格式" : "Format"}: ${escapeHtml(data.format || "")} · ${z ? "大小" : "Size"}: ${sizeKb} KB · ${z ? "导出时间" : "Exported"}: ${escapeHtml(data.exported_at || "")}
        </div>
        <p style="font-size:0.75rem;margin-bottom:0.4rem">${z ? "复制下方编码字符串，在其他设备粘贴到「导入」对话框即可恢复锦标赛状态。" : "Copy the encoded string below and paste it into the Import dialog on another device to restore the tournament state."}</p>
        <textarea id="wc-ko-share-code" readonly style="width:100%;height:80px;font-size:0.65rem;font-family:monospace;padding:0.4rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:4px;background:var(--bg-color,rgba(0,0,0,0.3));color:var(--text);resize:vertical" onclick="this.select()">${escapeHtml(encoded)}</textarea>
        <div style="display:flex;gap:0.5rem;margin-top:0.5rem">
            <button class="text-button" id="wc-ko-share-copy" type="button" style="font-size:0.75rem">${z ? "复制编码" : "Copy Code"}</button>
            <button class="text-button" id="wc-ko-share-download" type="button" style="font-size:0.75rem">${z ? "下载 JSON" : "Download JSON"}</button>
        </div>
    </div>`;

    const copyBtn = dlg.querySelector("#wc-ko-share-copy");
    if (copyBtn) {
        copyBtn.addEventListener("click", () => {
            const ta = dlg.querySelector("#wc-ko-share-code");
            if (ta) {
                ta.select();
                try {
                    document.execCommand("copy");
                    copyBtn.textContent = z ? "已复制!" : "Copied!";
                    setTimeout(() => { copyBtn.textContent = z ? "复制编码" : "Copy Code"; }, 1500);
                } catch (e) {
                    alert(z ? "复制失败，请手动选择复制" : "Copy failed. Please select and copy manually.");
                }
            }
        });
    }

    const dlBtn = dlg.querySelector("#wc-ko-share-download");
    if (dlBtn) {
        dlBtn.addEventListener("click", () => {
            const blob = new Blob([fullJson], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `wc_tournament_state_${(data.exported_at || "export").replace(/[:.]/g, "-")}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }
}

function renderWcImportDialog() {
    const z = appState.lang === "zh";
    const bracketPanel = document.getElementById("wc-ko-bracket-panel");
    if (!bracketPanel) return;

    let dlg = document.getElementById("wc-ko-import-dialog");
    if (!dlg) {
        dlg = document.createElement("div");
        dlg.id = "wc-ko-import-dialog";
        bracketPanel.parentElement.insertBefore(dlg, bracketPanel);
    }

    dlg.innerHTML = `<div style="padding:0.8rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:6px;background:var(--panel-bg,rgba(255,255,255,0.03));margin-bottom:1rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem">
            <h4 style="font-size:0.9rem">${z ? "导入锦标赛状态" : "Import Tournament State"}</h4>
            <button class="text-button" onclick="document.getElementById('wc-ko-import-dialog').remove()" style="font-size:0.7rem;padding:0.2rem 0.5rem">✕</button>
        </div>
        <p style="font-size:0.75rem;margin-bottom:0.4rem">${z ? "粘贴分享编码字符串到下方文本框，点击导入将覆盖当前锦标赛状态。" : "Paste the shared encoded string into the box below. Importing will overwrite the current tournament state."}</p>
        <textarea id="wc-ko-import-code" placeholder="${z ? "粘贴编码..." : "Paste encoded string..."}" style="width:100%;height:80px;font-size:0.65rem;font-family:monospace;padding:0.4rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:4px;background:var(--bg-color,rgba(0,0,0,0.3));color:var(--text);resize:vertical"></textarea>
        <div id="wc-ko-import-msg" style="font-size:0.7rem;margin-top:0.4rem;min-height:1rem"></div>
        <div style="display:flex;gap:0.5rem;margin-top:0.5rem">
            <button class="text-button" id="wc-ko-import-confirm" type="button" style="font-size:0.75rem">${z ? "导入" : "Import"}</button>
            <button class="text-button" id="wc-ko-import-file" type="button" style="font-size:0.75rem">${z ? "从文件加载" : "Load File"}</button>
        </div>
        <input type="file" id="wc-ko-import-file-input" accept=".json,.txt" style="display:none">
    </div>`;

    const confirmBtn = dlg.querySelector("#wc-ko-import-confirm");
    const msgEl = dlg.querySelector("#wc-ko-import-msg");
    if (confirmBtn) {
        confirmBtn.addEventListener("click", async () => {
            const ta = dlg.querySelector("#wc-ko-import-code");
            const encoded = ta ? ta.value.trim() : "";
            if (!encoded) {
                msgEl.textContent = z ? "请输入编码字符串" : "Please enter the encoded string";
                msgEl.style.color = "var(--status-low-color,#f44336)";
                return;
            }
            confirmBtn.disabled = true;
            confirmBtn.textContent = z ? "导入中..." : "Importing...";
            msgEl.textContent = "";
            const result = await fetchWcTournamentImport(encoded);
            confirmBtn.disabled = false;
            confirmBtn.textContent = z ? "导入" : "Import";
            if (result && result.status === "ok") {
                msgEl.textContent = z ? "导入成功！正在刷新..." : "Import successful! Refreshing...";
                msgEl.style.color = "var(--status-high-color,#4caf50)";
                setTimeout(async () => {
                    wcApiData.knockoutBracket = null;
                    wcApiData.knockoutProbabilities = null;
                    wcApiData.knockoutScenarios = {};
                    wcApiData.tournamentExport = null;
                    await fetchWcTournamentSummary();
                    await fetchWcTournamentMatches(wcApiData.tournamentSelectedGroup || "A");
                    await fetchWcKnockoutBracket();
                    renderWcTournament();
                    dlg.remove();
                }, 1200);
            } else {
                const code = (result && result.code) || "unknown";
                const knownCodes = {
                    decode_failed: z ? "解码失败：编码格式无效" : "Decode failed: invalid encoding",
                    invalid_state: z ? "状态数据无效：schema 不兼容" : "Invalid state: incompatible schema",
                    request_failed: z ? "请求失败：API 不可用" : "Request failed: API unavailable",
                };
                msgEl.textContent = knownCodes[code] || (z ? "导入失败" : "Import failed") + ` (${code})`;
                msgEl.style.color = "var(--status-low-color,#f44336)";
            }
        });
    }

    const fileBtn = dlg.querySelector("#wc-ko-import-file");
    const fileInput = dlg.querySelector("#wc-ko-import-file-input");
    if (fileBtn && fileInput) {
        fileBtn.addEventListener("click", () => fileInput.click());
        fileInput.addEventListener("change", (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (ev) => {
                try {
                    const text = String(ev.target.result || "");
                    let encoded = text;
                    try {
                        const parsed = JSON.parse(text);
                        if (parsed && parsed.encoded) encoded = parsed.encoded;
                    } catch (_) { /* not JSON, use raw text */ }
                    const ta = dlg.querySelector("#wc-ko-import-code");
                    if (ta) ta.value = encoded;
                } catch (err) {
                    msgEl.textContent = z ? "文件读取失败" : "File read failed";
                    msgEl.style.color = "var(--status-low-color,#f44336)";
                }
            };
            reader.readAsText(file);
        });
    }
}

function renderWcGroupStageSimulation() {
    const z = appState.lang === "zh";
    const panel = document.getElementById("wc-grpsim-panel");
    if (!panel) return;

    const data = wcApiData.groupStageSimulation;
    if (!data) {
        panel.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:1rem;font-size:0.85rem">${z ? "模拟失败" : "Simulation failed"}</p>`;
        return;
    }

    const adv = data.advancement_probability || [];
    const winners = data.most_likely_group_winners || [];
    const top20 = adv.slice(0, 20);

    let html = `<div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.5rem">
        ${z ? "模式" : "Mode"}: ${data.mode} | ${z ? "模拟次数" : "Simulations"}: ${data.num_simulations} | ${z ? "剩余比赛" : "Remaining"}: ${data.remaining_matches}
    </div>`;

    // Most likely group winners
    if (winners.length > 0) {
        html += `<h4 style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem;text-transform:uppercase">${z ? "最可能小组第一" : "Most Likely Group Winners"}</h4>
        <div style="display:flex;flex-wrap:wrap;gap:0.3rem;margin-bottom:0.8rem">`;
        for (const w of winners) {
            const pct = (w.probability * 100).toFixed(0);
            html += `<span class="status-pill status-high" style="font-size:0.7rem">${escapeHtml(w.group)}: ${escapeHtml(w.team)} (${pct}%)</span>`;
        }
        html += `</div>`;
    }

    // Top 20 advancement probabilities
    if (top20.length > 0) {
        html += `<h4 style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.3rem;text-transform:uppercase">${z ? "出线概率 Top 20" : "Advancement Probability Top 20"}</h4>
        <div style="display:flex;flex-direction:column;gap:0.2rem">`;
        for (const t of top20) {
            const advPct = (t.advance_prob * 100).toFixed(1);
            const winPct = (t.win_group_prob * 100).toFixed(1);
            const barWidth = Math.max(1, t.advance_prob * 100);
            const barColor = t.advance_prob >= 0.8 ? "var(--status-high-color,#4caf50)" :
                             t.advance_prob >= 0.4 ? "var(--status-medium-color,#ff9800)" :
                             "var(--status-low-color,#f44336)";
            html += `<div style="display:flex;align-items:center;gap:0.5rem;font-size:0.7rem">
                <span style="min-width:30px;color:var(--text-muted)">${escapeHtml(t.group)}</span>
                <span style="min-width:100px">${escapeHtml(t.team)}</span>
                <div style="flex:1;background:var(--border-color,rgba(255,255,255,0.1));border-radius:3px;height:6px;overflow:hidden"><div style="width:${barWidth}%;height:100%;background:${barColor}"></div></div>
                <span style="min-width:45px;text-align:right">${advPct}%</span>
                <span style="min-width:60px;text-align:right;color:var(--text-muted)">${z ? "小组第一" : "Win"} ${winPct}%</span>
            </div>`;
        }
        html += `</div>`;
    }

    if (data.disclaimer) {
        html += `<p style="font-size:0.65rem;color:var(--text-muted);margin-top:0.5rem">${escapeHtml(data.disclaimer)}</p>`;
    }

    panel.innerHTML = html;
}

function renderWcKnockoutBracket() {
    const z = appState.lang === "zh";
    const panel = document.getElementById("wc-ko-bracket-panel");
    if (!panel) return;

    const data = wcApiData.knockoutBracket;
    if (!data || !data.generated) {
        panel.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:1rem;font-size:0.85rem">
            ${z ? "尚未生成对阵图。点击上方「生成对阵」按钮。" : "No bracket generated yet. Click \"Generate Bracket\" above."}
        </p>`;
        return;
    }

    const rounds = data.rounds || {};
    const roundOrder = ["r32", "r16", "qf", "sf", "final"];
    const roundLabels = z ? {
        r32: "32 强", r16: "16 强", qf: "四分之一决赛", sf: "半决赛", final: "决赛",
    } : {
        r32: "Round of 32", r16: "Round of 16", qf: "Quarter-Finals", sf: "Semi-Finals", final: "Final",
    };

    const champ = data.champion;
    const prov = data.provisional;

    // Build a lookup of probabilities by match_id
    const probsData = wcApiData.knockoutProbabilities;
    const probsMap = {};
    if (probsData && probsData.match_probabilities) {
        for (const p of probsData.match_probabilities) {
            if (p.match_id) probsMap[p.match_id] = p;
        }
    }

    let html = "";

    if (champ) {
        html += `<div style="text-align:center;padding:0.8rem;margin-bottom:1rem;background:var(--panel-bg,rgba(255,255,255,0.05));border-radius:8px">
            <span style="font-size:1.2rem">🏆</span>
            <span style="font-size:1.1rem;font-weight:bold;margin-left:0.5rem">${escapeHtml(champ)}</span>
            <span style="color:var(--text-muted);margin-left:0.5rem">${z ? "冠军" : "Champion"}</span>
        </div>`;
    }

    if (prov && !champ) {
        html += `<p style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.5rem">${z ? "(暂定——小组赛未完赛)" : "(Provisional — group stage incomplete)"}</p>`;
    }

    // Tournament win odds table
    if (probsData && probsData.tournament_win_probability && probsData.tournament_win_probability.length > 0) {
        const odds = probsData.tournament_win_probability.slice(0, 8);
        html += `<div style="margin-bottom:1rem;padding:0.6rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:6px;background:var(--panel-bg,rgba(255,255,255,0.03))">
            <h4 style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.4rem;text-transform:uppercase;letter-spacing:0.05em">${z ? "夺冠概率" : "Tournament Win Odds"} <span style="font-weight:normal;text-transform:none">(${z ? "蒙特卡洛 " + probsData.num_simulations + " 次模拟" : "MC " + probsData.num_simulations + " sims"})</span></h4>
            <div style="display:flex;flex-wrap:wrap;gap:0.4rem">`;
        for (const t of odds) {
            const pct = (t.win_probability * 100).toFixed(1);
            const barWidth = Math.max(2, t.win_probability * 100);
            html += `<div style="min-width:110px;flex:1">
                <div style="font-size:0.7rem;margin-bottom:0.1rem">${escapeHtml(t.team)}</div>
                <div style="background:var(--border-color,rgba(255,255,255,0.1));border-radius:3px;height:4px;overflow:hidden"><div style="width:${barWidth}%;height:100%;background:var(--accent-color,#4a9eff)"></div></div>
                <div style="font-size:0.65rem;color:var(--text-muted)">${pct}%</div>
            </div>`;
        }
        html += `</div></div>`;
    }

    // Render bracket as horizontal scroll with columns per round
    html += `<div style="overflow-x:auto;padding-bottom:0.5rem"><div style="display:flex;gap:1rem;min-width:max-content">`;

    for (const code of roundOrder) {
        const rd = rounds[code];
        if (!rd || !rd.matches || rd.matches.length === 0) continue;
        html += `<div style="min-width:240px">
            <h4 style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;text-transform:uppercase;letter-spacing:0.05em">${roundLabels[code] || code}</h4>
            <div style="display:flex;flex-direction:column;gap:0.4rem">`;
        for (const m of rd.matches) {
            html += renderKnockoutMatchCard(m, z, probsMap[m.match_id]);
        }
        html += `</div></div>`;
    }

    html += `</div></div>`;

    if (probsData && probsData.disclaimer) {
        html += `<p style="font-size:0.65rem;color:var(--text-muted);margin-top:0.5rem">${escapeHtml(probsData.disclaimer)}</p>`;
    }

    panel.innerHTML = html;

    // Bind event listeners
    panel.querySelectorAll(".wc-ko-apply").forEach((btn) => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = "1";
        btn.addEventListener("click", async (e) => {
            const matchId = e.target.dataset.matchId;
            const card = panel.querySelector(`[data-ko-card="${CSS.escape(matchId)}"]`);
            const hgInput = card && card.querySelector(".wc-ko-hg");
            const agInput = card && card.querySelector(".wc-ko-ag");
            const penSelect = card && card.querySelector(".wc-ko-pen");
            const hg = hgInput ? parseInt(hgInput.value, 10) : NaN;
            const ag = agInput ? parseInt(agInput.value, 10) : NaN;
            if (isNaN(hg) || isNaN(ag) || hg < 0 || ag < 0 || hg > 30 || ag > 30) {
                alert(z ? "请输入 0-30 的有效比分" : "Enter valid scores (0-30)");
                return;
            }
            const pen = (hg === ag && penSelect) ? penSelect.value : null;
            await applyKnockoutResult(matchId, hg, ag, pen);
        });
    });

    panel.querySelectorAll(".wc-ko-clear").forEach((btn) => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = "1";
        btn.addEventListener("click", async (e) => {
            const matchId = e.target.dataset.matchId;
            await clearKnockoutResult(matchId);
        });
    });

    panel.querySelectorAll(".wc-ko-brief").forEach((btn) => {
        btn.addEventListener("click", () => {
            void openKnockoutMatchBriefing(btn.dataset.matchId);
        });
    });

    panel.querySelectorAll(".wc-ko-review").forEach((btn) => {
        btn.addEventListener("click", () => {
            void fetchWcKnockoutReview(btn.dataset.matchId);
        });
    });

    panel.querySelectorAll(".wc-ko-review-export").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const matchId = btn.dataset.matchId;
            const review = wcApiData.knockoutReviews[matchId] || await fetchWcKnockoutReview(matchId);
            if (review) downloadWcKnockoutReview(review);
        });
    });

    // Auto-fetch probabilities if not yet loaded
    if (!wcApiData.knockoutProbabilities) {
        fetchWcKnockoutProbabilities().then(() => {
            if (wcApiData.knockoutProbabilities) renderWcKnockoutBracket();
        });
    }
}

function renderKnockoutMatchCard(m, z, prob) {
    const home = m.home || "TBD";
    const away = m.away || "TBD";
    const hasResult = m.winner != null;
    const hg = m.home_goals;
    const ag = m.away_goals;
    const isReady = m.home != null && m.away != null;
    const decidedByPen = m.decided_by === "penalties";
    const review = wcApiData.knockoutReviews[m.match_id];
    let reviewHtml = "";
    if (review?.status === "ok") {
        const snapshot = review.prediction_snapshot || {};
        const prediction = snapshot.prediction || {};
        const comparison = review.comparison || {};
        const resultText = comparison.directional_result === "matched_direction"
            ? (z ? "方向一致" : "direction matched")
            : comparison.directional_result === "recorded_upset"
                ? (z ? "本地录入结果偏离模型方向" : "recorded upset")
                : (z ? "没有方向性判断" : "no directional call");
        reviewHtml = `<div style="margin-top:0.35rem;padding:0.3rem;background:var(--bg-elevated);border-radius:4px;font-size:0.62rem;color:var(--text-muted)">
            <div>${z ? "赛前本地快照" : "Pre-recording snapshot"}: ${(Number(prediction.home_win_probability || 0) * 100).toFixed(0)}% / ${(Number(prediction.away_win_probability || 0) * 100).toFixed(0)}%</div>
            <div>${escapeHtml(resultText)} · ${z ? "胜方当时概率" : "winner probability"} ${(Number(comparison.recorded_winner_probability || 0) * 100).toFixed(0)}%</div>
            <div style="margin-top:0.15rem">${z ? "仅与本地录入结果对照，不构成模型评估。" : "Local result comparison only; not a model evaluation."}</div>
        </div>`;
    } else if (review?.status === "snapshot_not_recorded") {
        reviewHtml = `<div style="margin-top:0.35rem;font-size:0.62rem;color:var(--text-muted)">${z ? "此旧本地赛果没有赛前快照；不会反推模型判断。" : "This older local result has no pre-recording snapshot; no model call is inferred."}</div>`;
    }

    // Probability bar HTML (for ready-for-input matches)
    const probBar = (prob && prob.home_win_probability != null && prob.away_win_probability != null)
        ? `<div style="display:flex;align-items:center;gap:0.2rem;margin-top:0.2rem;font-size:0.6rem;color:var(--text-muted)">
              <span style="font-weight:bold;color:var(--text-secondary)">${(prob.home_win_probability * 100).toFixed(0)}%</span>
              <div style="flex:1;height:3px;border-radius:2px;overflow:hidden;display:flex">
                  <div style="width:${prob.home_win_probability * 100}%;background:var(--accent-color,#4a9eff)"></div>
                  <div style="width:${prob.away_win_probability * 100}%;background:var(--border-color,rgba(255,255,255,0.2))"></div>
              </div>
              <span style="font-weight:bold;color:var(--text-secondary)">${(prob.away_win_probability * 100).toFixed(0)}%</span>
          </div>`
        : "";

    if (hasResult) {
        return `<div data-ko-card="${escapeAttr(m.match_id)}" style="padding:0.5rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:6px;font-size:0.8rem;background:var(--panel-bg,rgba(255,255,255,0.03))">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:${m.winner === m.home ? 'bold' : 'normal'}">${escapeHtml(home)}</span>
                <span style="font-weight:bold;margin:0 0.3rem">${hg}-${ag}${decidedByPen ? " (pen)" : ""}</span>
                <span style="font-weight:${m.winner === m.away ? 'bold' : 'normal'}">${escapeHtml(away)}</span>
            </div>
            <div style="display:flex;gap:0.3rem;flex-wrap:wrap;margin-top:0.2rem"><button class="text-button wc-ko-brief" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.65rem;padding:0.1rem 0.3rem">${z ? "简报" : "Brief"}</button><button class="text-button wc-ko-review" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.65rem;padding:0.1rem 0.3rem">${z ? "本地复盘" : "Review"}</button><button class="text-button wc-ko-review-export" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.65rem;padding:0.1rem 0.3rem">${z ? "导出复盘" : "Export review"}</button><button class="text-button wc-ko-clear" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.65rem;padding:0.1rem 0.3rem;color:var(--status-low)">${z ? "清除" : "Clear"}</button></div>
            ${reviewHtml}
        </div>`;
    }

    if (!isReady) {
        return `<div data-ko-card="${escapeAttr(m.match_id)}" style="padding:0.5rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:6px;font-size:0.8rem;opacity:0.6;background:var(--panel-bg,rgba(255,255,255,0.03))">
            <div style="display:flex;justify-content:space-between">
                <span>${escapeHtml(home)}</span>
                <span style="color:var(--text-muted)">vs</span>
                <span>${escapeHtml(away)}</span>
            </div>
        </div>`;
    }

    // Ready for input
    return `<div data-ko-card="${escapeAttr(m.match_id)}" style="padding:0.5rem;border:1px solid var(--border-color,rgba(255,255,255,0.1));border-radius:6px;font-size:0.8rem;background:var(--panel-bg,rgba(255,255,255,0.03))">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem">
            <span>${escapeHtml(home)}</span>
            <span style="color:var(--text-muted);font-size:0.7rem">vs</span>
            <span>${escapeHtml(away)}</span>
        </div>
        <div style="display:flex;gap:0.3rem;align-items:center">
            <input type="number" min="0" max="30" class="wc-ko-hg" style="width:2rem;font-size:0.75rem;text-align:center" placeholder="-">
            <span>:</span>
            <input type="number" min="0" max="30" class="wc-ko-ag" style="width:2rem;font-size:0.75rem;text-align:center" placeholder="-">
            <button class="text-button wc-ko-apply" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.65rem;padding:0.1rem 0.4rem">${z ? "录入" : "Apply"}</button>
        </div>
        ${probBar}
        <button class="text-button wc-ko-brief" data-match-id="${escapeAttr(m.match_id)}" type="button" style="font-size:0.65rem;padding:0.1rem 0.3rem;margin-top:0.3rem">${z ? "加载赛前简报" : "Load briefing"}</button>
    </div>`;
}

async function openKnockoutMatchBriefing(matchId) {
    const z = appState.lang === "zh";
    try {
        const briefing = await fetchJson(`/world-cup/tournament/knockout/${encodeURIComponent(matchId)}/briefing`);
        if (briefing?.status !== "ok") {
            alert(briefing?.status === "not_ready"
                ? (z ? "该淘汰赛席位尚未确定，不会推断对手或生成简报。" : "This knockout slot is unresolved; no opponent or briefing is inferred.")
                : (z ? "本地淘汰赛简报不可用。" : "The local knockout briefing is unavailable."));
            return;
        }
        const fixture = briefing.fixture || {};
        const home = fixture.home_team;
        const away = fixture.away_team;
        if (!home || !away) return;
        const cacheKey = `${home}|${away}`;
        wcApiData.matchBriefingCache[cacheKey] = briefing;
        appState.wcCompareA = home;
        appState.wcCompareB = away;
        await Promise.all([
            fetchWcSquad(home), fetchWcSquad(away), fetchWcMatchPrediction(home, away),
            fetchWcSquadBalanceComparison(home, away),
        ]);
        await setView("wc_compare");
    } catch (err) {
        console.warn("[WC] knockout briefing failed:", err);
        alert(z ? "加载本地淘汰赛简报失败。" : "Failed to load the local knockout briefing.");
    }
}

async function fetchWcMatchPrediction(teamA, teamB) {
    const cacheKey = `${teamA}|${teamB}`;
    if (wcApiData.matchPredictionCache[cacheKey]) return wcApiData.matchPredictionCache[cacheKey];

    // If API is offline, look up from pre-computed match_predictions.json
    if (apiOnline === false) {
        try {
            if (!wcApiData._matchPredictionsAll) {
                const mpData = await fetchJson("/world-cup/match-predictions");
                wcApiData._matchPredictionsAll = mpData && mpData.matches ? mpData.matches : [];
            }
            const found = wcApiData._matchPredictionsAll.find(
                (m) => (m.home === teamA && m.away === teamB) || (m.home === teamB && m.away === teamA)
            );
            if (found) {
                // Convert to the same format as the dynamic API response
                const result = {
                    home_team: found.home,
                    away_team: found.away,
                    home_win: found.home_win_p,
                    draw: found.draw_p,
                    away_win: found.away_win_p,
                    home_lambda: found.exp_home_goals,
                    away_lambda: found.exp_away_goals,
                    model_type: "poisson_strength_ratio",
                    model_version: "wc-static-1.0",
                    score_matrix: null,
                };
                wcApiData.matchPredictionCache[cacheKey] = result;
                return result;
            }
        } catch (e) {
            console.warn("[WC] static match prediction lookup failed:", e.message);
        }
        return null;
    }

    try {
        const data = await fetchJson(`/world-cup/predictions/${encodeURIComponent(teamA)}/${encodeURIComponent(teamB)}`, {
            fetchOpts: { signal: AbortSignal.timeout(60000) },
        });
        wcApiData.matchPredictionCache[cacheKey] = data;
        wcApiData.apiOnline = true;
        return data;
    } catch (e) {
        console.warn("[WC] fetchWcMatchPrediction failed:", e.message);
        return null;
    }
}

async function fetchWcMatchBriefing(teamA, teamB) {
    const cacheKey = `${teamA}|${teamB}`;
    if (wcApiData.matchBriefingCache[cacheKey]) return wcApiData.matchBriefingCache[cacheKey];

    if (apiOnline !== false) {
        try {
            const briefing = await fetchJson(`/world-cup/match-briefings/${encodeURIComponent(teamA)}/${encodeURIComponent(teamB)}`);
            if (briefing?.status === "ok") {
                wcApiData.matchBriefingCache[cacheKey] = briefing;
                wcApiData.apiOnline = true;
                return briefing;
            }
        } catch (e) {
            console.warn("[WC] fetchWcMatchBriefing failed:", e.message);
        }
    }

    try {
        if (!wcApiData._matchBriefingsAll) {
            const data = await fetchJson("/world-cup/match-briefings");
            wcApiData._matchBriefingsAll = data?.briefings || [];
        }
        const briefing = wcApiData._matchBriefingsAll.find((item) =>
            item?.fixture?.home_team === teamA && item?.fixture?.away_team === teamB,
        ) || wcApiData._matchBriefingsAll.find((item) =>
            item?.fixture?.home_team === teamB && item?.fixture?.away_team === teamA,
        );
        if (briefing?.status === "ok") {
            wcApiData.matchBriefingCache[cacheKey] = briefing;
            return briefing;
        }
    } catch (e) {
        console.warn("[WC] static match briefing lookup failed:", e.message);
    }
    return null;
}

function _safeBriefingFilename(briefing) {
    const fixture = briefing?.fixture || {};
    const raw = `${fixture.home_team || "home"}_vs_${fixture.away_team || "away"}`;
    return raw.replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]/g, "_");
}

function _safeWcComparisonFilename(comparison) {
    const teams = comparison?.teams || {};
    const teamA = teams.team_a?.team || "team_a";
    const teamB = teams.team_b?.team || "team_b";
    return `${teamA}_vs_${teamB}`.replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]/g, "_");
}

function _downloadLocalBriefing(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

function exportWcBriefingJSON(briefing) {
    if (briefing?.status !== "ok") return;
    const payload = {
        schema: "scoutfootball.world-cup-match-briefing-export",
        version: "1.0.0",
        exported_at: new Date().toISOString(),
        storage_scope: "browser-local-download",
        briefing,
    };
    _downloadLocalBriefing(
        JSON.stringify(payload, null, 2),
        `${_safeBriefingFilename(briefing)}_world_cup_briefing.json`,
        "application/json;charset=utf-8",
    );
}

function exportWcSquadBalanceComparisonJSON(comparison) {
    if (comparison?.status !== "ok") return;
    const payload = {
        schema: "scoutfootball.world-cup-squad-balance-comparison-export",
        version: "1.0.0",
        exported_at: new Date().toISOString(),
        storage_scope: "browser-local-download",
        comparison,
    };
    _downloadLocalBriefing(
        JSON.stringify(payload, null, 2),
        `${_safeWcComparisonFilename(comparison)}_squad_role_comparison.json`,
        "application/json;charset=utf-8",
    );
}

function exportWcSquadBalanceComparisonCSV(comparison) {
    if (comparison?.status !== "ok") return;
    const teams = comparison.teams || {};
    const teamA = teams.team_a?.team || "team_a";
    const teamB = teams.team_b?.team || "team_b";
    const lines = [
        ["# World Cup Expected-Callup Role Comparison"],
        ["team_a", teamA],
        ["team_b", teamB],
        ["storage_scope", "browser-local-download"],
        [],
        ["role", `${teamA}_count`, `${teamA}_target`, `${teamA}_rated_players`, `${teamA}_rating_coverage`, `${teamB}_count`, `${teamB}_target`, `${teamB}_rated_players`, `${teamB}_rating_coverage`, "count_difference", "rated_player_difference", "rating_coverage_difference"],
    ];
    for (const row of comparison.roles || []) {
        const teamARole = row.team_a || {};
        const teamBRole = row.team_b || {};
        lines.push([
            row.role || "",
            teamARole.count ?? "",
            teamARole.planning_target ?? "",
            teamARole.rated_players ?? "",
            teamARole.rating_coverage ?? "",
            teamBRole.count ?? "",
            teamBRole.planning_target ?? "",
            teamBRole.rated_players ?? "",
            teamBRole.rating_coverage ?? "",
            row.count_difference ?? "",
            row.rated_player_difference ?? "",
            row.rating_coverage_difference ?? "",
        ]);
    }
    lines.push([], ["# Limitation"], [comparison.disclaimer || ""]);
    lines.push([], ["# Exported", new Date().toISOString(), `ScoutFootball v${APP_VERSION}`]);
    _downloadLocalBriefing(
        `\uFEFF${lines.map((row) => row.map(csvCell).join(",")).join("\n")}`,
        `${_safeWcComparisonFilename(comparison)}_squad_role_comparison.csv`,
        "text/csv;charset=utf-8",
    );
}

function exportWcBriefingCSV(briefing) {
    if (briefing?.status !== "ok") return;
    const fixture = briefing.fixture || {};
    const prediction = briefing.prediction || {};
    const teams = briefing.teams || {};
    const lines = [
        ["# World Cup Match Briefing"],
        ["field", "value"],
        ["home_team", fixture.home_team || ""],
        ["away_team", fixture.away_team || ""],
        ["model_type", prediction.model_type || ""],
        ["model_version", prediction.model_version || ""],
        ["home_win", prediction.home_win ?? ""],
        ["draw", prediction.draw ?? ""],
        ["away_win", prediction.away_win ?? ""],
        ["home_expected_goals", prediction.home_lambda ?? ""],
        ["away_expected_goals", prediction.away_lambda ?? ""],
        ["source_attribution", briefing.source_attribution || ""],
        ["storage_scope", "browser-local-download"],
        [],
        ["# Team Coverage"],
        ["team", "rating_coverage", "rated_players", "total_players", "core_avg_rating", "depth_avg_rating"],
    ];
    for (const team of [teams.home, teams.away]) {
        if (!team) continue;
        const squad = team.squad || {};
        lines.push([
            team.team || "",
            squad.rating_coverage ?? "",
            squad.rated_players ?? "",
            squad.total_players ?? "",
            squad.core_avg_rating ?? "",
            squad.depth_avg_rating ?? "",
        ]);
    }
    lines.push([], ["# Top Rated Players"], ["team", "player", "position", "club", "rating", "confidence"]);
    for (const team of [teams.home, teams.away]) {
        for (const player of team?.squad?.top_rated_players || []) {
            lines.push([team.team || "", player.name || "", player.position || "", player.club || "", player.rating ?? "", player.rating_confidence || ""]);
        }
    }
    lines.push([], ["# Squad Role Depth"], ["team", "role", "count", "planning_target", "depth_status", "rating_coverage"]);
    for (const team of [teams.home, teams.away]) {
        for (const [role, details] of Object.entries(team?.squad?.balance?.roles || {})) {
            lines.push([
                team.team || "",
                role,
                details.count ?? "",
                details.planning_target ?? "",
                details.depth_status ?? "",
                details.rating_coverage ?? "",
            ]);
        }
    }
    lines.push([], ["# Limitations"], ["limitation"]);
    for (const limitation of briefing.limitations || []) lines.push([limitation]);
    lines.push([], ["# Exported", new Date().toISOString(), `ScoutFootball v${APP_VERSION}`]);
    const csv = lines.map((row) => row.map(csvCell).join(",")).join("\n");
    _downloadLocalBriefing(
        `\uFEFF${csv}`,
        `${_safeBriefingFilename(briefing)}_world_cup_briefing.csv`,
        "text/csv;charset=utf-8",
    );
}

function wcAllTeams() {
    if (wcApiData.teams && wcApiData.teams.teams) {
        return wcApiData.teams.teams.map((t) => t.team);
    }
    return Object.values(WC_GROUPS).flat();
}

function wcTeamGroup(team) {
    if (wcApiData.teams && wcApiData.teams.teams) {
        const entry = wcApiData.teams.teams.find((t) => t.team === team);
        if (entry) return entry.group;
    }
    for (const [letter, teams] of Object.entries(WC_GROUPS)) {
        if (teams.includes(team)) return letter;
    }
    return "?";
}

// Get enriched squad data (from API cache, or return empty)
function wcGetSquad(team) {
    const cached = wcApiData.squadCache[team];
    if (cached && cached.players) {
        return cached.players.map((p) => ({
            name: p.name,
            position: p.position,
            club: p.club,
            league: p.club_league,
            hasRating: p.has_rating,
            rating: p.rating,
            confidence: p.rating_confidence ? p.rating_confidence.toUpperCase() : "NONE",
        }));
    }
    return [];
}

/* Match squad player names against the global ratings (players) array */
function matchSquadWithRatings(squad) {
    if (!players || players.length === 0) return squad;
    const ratingMap = {};
    for (const p of players) {
        const key = (p.name || "").toLowerCase();
        if (key) ratingMap[key] = p;
    }
    return squad.map((sp) => {
        if (sp.hasRating) return sp;
        const key = (sp.name || "").toLowerCase();
        const match = ratingMap[key];
        if (match) {
            return {
                ...sp,
                hasRating: true,
                rating: match.rating,
                confidence: match.confidence || "LOW",
                position: sp.position || match.position,
            };
        }
        return sp;
    });
}

// Compute team strength from API data or fallback
function wcTeamStrength(team) {
    // Try from teams API data
    if (wcApiData.teams && wcApiData.teams.teams) {
        const entry = wcApiData.teams.teams.find((t) => t.team === team);
        if (entry) return entry.strength;
    }
    // Try from predictions API data
    if (wcApiData.predictions && wcApiData.predictions.ranking) {
        const entry = wcApiData.predictions.ranking.find((r) => r.team === team);
        if (entry) return entry.strength;
    }
    // Try from groups API data
    if (wcApiData.groups && wcApiData.groups.groups) {
        for (const g of wcApiData.groups.groups) {
            const t = g.teams.find((t) => t.team === team);
            if (t) return t.strength;
        }
    }
    // Fallback: compute from squad
    const squad = wcGetSquad(team);
    const rated = squad.filter((p) => p.hasRating);
    if (rated.length > 0) {
        const avg = rated.reduce((s, p) => s + p.rating, 0) / rated.length;
        const ratingScore = Math.min(Math.max((avg - 30) / 70, 0), 1);
        const big5Count = squad.filter((p) => WC_BIG5.has(p.league)).length;
        const big5Score = Math.min(big5Count / 10, 1);
        return 0.7 * ratingScore + 0.3 * big5Score;
    }
    return 0.2;
}

// ── World Cup Renderers ──────────────────────────────────────────────────

async function openWcFixtureBriefing(home, away) {
    if (!home || !away) return;
    appState.wcCompareA = home;
    appState.wcCompareB = away;
    const selA = document.getElementById("wc-compare-a");
    const selB = document.getElementById("wc-compare-b");
    if (selA) selA.value = home;
    if (selB) selB.value = away;
    await Promise.all([
        fetchWcSquad(home),
        fetchWcSquad(away),
        fetchWcMatchPrediction(home, away),
        fetchWcMatchBriefing(home, away),
    ]);
    await setView("wc_compare");
}

function renderWcSchedule() {
    const groupFilter = document.getElementById("wc-group-filter").value;
    const mdFilter = document.getElementById("wc-matchday-filter").value;

    // Groups overview — use API data if available
    const overview = document.getElementById("wc-groups-overview");
    if (wcApiData.groups && wcApiData.groups.groups) {
        overview.innerHTML = wcApiData.groups.groups.map((g) => {
            const hostTag = (tm) => tm.is_host ? " ★" : "";
            return `<article class="liquid-panel compact-panel">
                <h3>${escapeHtml(g.group)}</h3>
                <ul class="wc-group-list">${g.teams.map((tm, i) => `<li>${i + 1}. ${escapeHtml(tm.team)}${hostTag(tm)}${tm.avg_rating ? ` <span style="color:var(--text-muted);font-size:0.8em">(${tm.avg_rating})</span>` : ""}</li>`).join("")}</ul>
            </article>`;
        }).join("");
    } else {
        overview.innerHTML = Object.entries(WC_GROUPS).map(([letter, teams]) => {
            const hostTag = (tm) => WC_HOSTS.includes(tm) ? " ★" : "";
            return `<article class="liquid-panel compact-panel">
                <h3>${escapeHtml(letter)}</h3>
                <ul class="wc-group-list">${teams.map((tm, i) => `<li>${i + 1}. ${escapeHtml(tm)}${hostTag(tm)}</li>`).join("")}</ul>
            </article>`;
        }).join("");
    }

    // Show DEMO badge if API offline
    const scheduleTitle = document.getElementById("wc-schedule-title");
    if (scheduleTitle) {
        let indicator = scheduleTitle.querySelector(".data-source-indicator");
        if (!indicator) {
            indicator = document.createElement("span");
            indicator.className = "status-pill data-source-indicator";
            scheduleTitle.appendChild(indicator);
        }
        if (!wcApiData.apiOnline) {
            indicator.textContent = "DEMO";
            indicator.className = "status-pill status-low data-source-indicator";
        } else {
            indicator.textContent = "";
            indicator.className = "status-pill data-source-indicator";
        }
    }

    // Use API schedule if available, otherwise generate locally
    let matches = [];
    if (wcApiData.schedule && wcApiData.schedule.matches) {
        matches = wcApiData.schedule.matches;
    } else {
        // Fallback: official 2026 World Cup schedule (all times ET)
        const schedule = [
            // Group A
            {date:"2026-06-11",time_et:"15:00",group:"A",home:"Mexico",away:"South Africa",venue:"Estadio Azteca",city:"Mexico City",matchday:1},
            {date:"2026-06-11",time_et:"22:00",group:"A",home:"South Korea",away:"Czech Republic",venue:"Estadio Akron",city:"Guadalajara",matchday:1},
            {date:"2026-06-18",time_et:"12:00",group:"A",home:"South Africa",away:"Czech Republic",venue:"Mercedes-Benz Stadium",city:"Atlanta",matchday:2},
            {date:"2026-06-18",time_et:"21:00",group:"A",home:"Mexico",away:"South Korea",venue:"Estadio Akron",city:"Guadalajara",matchday:2},
            {date:"2026-06-24",time_et:"21:00",group:"A",home:"Mexico",away:"Czech Republic",venue:"Estadio Azteca",city:"Mexico City",matchday:3},
            {date:"2026-06-24",time_et:"21:00",group:"A",home:"South Africa",away:"South Korea",venue:"Estadio BBVA",city:"Monterrey",matchday:3},
            // Group B
            {date:"2026-06-12",time_et:"15:00",group:"B",home:"Canada",away:"Bosnia and Herzegovina",venue:"BMO Field",city:"Toronto",matchday:1},
            {date:"2026-06-13",time_et:"15:00",group:"B",home:"Qatar",away:"Switzerland",venue:"Levi's Stadium",city:"San Francisco Bay Area",matchday:1},
            {date:"2026-06-18",time_et:"15:00",group:"B",home:"Bosnia and Herzegovina",away:"Switzerland",venue:"SoFi Stadium",city:"Los Angeles",matchday:2},
            {date:"2026-06-18",time_et:"18:00",group:"B",home:"Canada",away:"Qatar",venue:"BC Place",city:"Vancouver",matchday:2},
            {date:"2026-06-24",time_et:"15:00",group:"B",home:"Bosnia and Herzegovina",away:"Qatar",venue:"Lumen Field",city:"Seattle",matchday:3},
            {date:"2026-06-24",time_et:"15:00",group:"B",home:"Canada",away:"Switzerland",venue:"BC Place",city:"Vancouver",matchday:3},
            // Group C
            {date:"2026-06-13",time_et:"18:00",group:"C",home:"Brazil",away:"Morocco",venue:"MetLife Stadium",city:"New York/New Jersey",matchday:1},
            {date:"2026-06-13",time_et:"21:00",group:"C",home:"Haiti",away:"Scotland",venue:"Gillette Stadium",city:"Boston",matchday:1},
            {date:"2026-06-19",time_et:"18:00",group:"C",home:"Morocco",away:"Scotland",venue:"Gillette Stadium",city:"Boston",matchday:2},
            {date:"2026-06-19",time_et:"21:00",group:"C",home:"Haiti",away:"Brazil",venue:"Lincoln Financial Field",city:"Philadelphia",matchday:2},
            {date:"2026-06-24",time_et:"18:00",group:"C",home:"Morocco",away:"Haiti",venue:"Mercedes-Benz Stadium",city:"Atlanta",matchday:3},
            {date:"2026-06-24",time_et:"18:00",group:"C",home:"Brazil",away:"Scotland",venue:"Hard Rock Stadium",city:"Miami",matchday:3},
            // Group D
            {date:"2026-06-12",time_et:"21:00",group:"D",home:"United States",away:"Paraguay",venue:"SoFi Stadium",city:"Los Angeles",matchday:1},
            {date:"2026-06-13",time_et:"00:00",group:"D",home:"Australia",away:"Turkey",venue:"BC Place",city:"Vancouver",matchday:1},
            {date:"2026-06-19",time_et:"00:00",group:"D",home:"Paraguay",away:"Turkey",venue:"Levi's Stadium",city:"San Francisco Bay Area",matchday:2},
            {date:"2026-06-19",time_et:"15:00",group:"D",home:"United States",away:"Australia",venue:"Lumen Field",city:"Seattle",matchday:2},
            {date:"2026-06-25",time_et:"22:00",group:"D",home:"United States",away:"Turkey",venue:"SoFi Stadium",city:"Los Angeles",matchday:3},
            {date:"2026-06-25",time_et:"22:00",group:"D",home:"Paraguay",away:"Australia",venue:"Levi's Stadium",city:"San Francisco Bay Area",matchday:3},
            // Group E
            {date:"2026-06-14",time_et:"13:00",group:"E",home:"Germany",away:"Curacao",venue:"NRG Stadium",city:"Houston",matchday:1},
            {date:"2026-06-14",time_et:"19:00",group:"E",home:"Ivory Coast",away:"Ecuador",venue:"Lincoln Financial Field",city:"Philadelphia",matchday:1},
            {date:"2026-06-20",time_et:"16:00",group:"E",home:"Germany",away:"Ivory Coast",venue:"BMO Field",city:"Toronto",matchday:2},
            {date:"2026-06-20",time_et:"20:00",group:"E",home:"Curacao",away:"Ecuador",venue:"Arrowhead Stadium",city:"Kansas City",matchday:2},
            {date:"2026-06-25",time_et:"16:00",group:"E",home:"Germany",away:"Ecuador",venue:"MetLife Stadium",city:"New York/New Jersey",matchday:3},
            {date:"2026-06-25",time_et:"16:00",group:"E",home:"Curacao",away:"Ivory Coast",venue:"Lincoln Financial Field",city:"Philadelphia",matchday:3},
            // Group F
            {date:"2026-06-14",time_et:"16:00",group:"F",home:"Netherlands",away:"Japan",venue:"AT&T Stadium",city:"Dallas",matchday:1},
            {date:"2026-06-14",time_et:"19:00",group:"F",home:"Sweden",away:"Tunisia",venue:"Estadio BBVA",city:"Monterrey",matchday:1},
            {date:"2026-06-20",time_et:"13:00",group:"F",home:"Netherlands",away:"Sweden",venue:"NRG Stadium",city:"Houston",matchday:2},
            {date:"2026-06-20",time_et:"00:00",group:"F",home:"Japan",away:"Tunisia",venue:"Estadio BBVA",city:"Monterrey",matchday:2},
            {date:"2026-06-25",time_et:"19:00",group:"F",home:"Netherlands",away:"Tunisia",venue:"Arrowhead Stadium",city:"Kansas City",matchday:3},
            {date:"2026-06-25",time_et:"19:00",group:"F",home:"Japan",away:"Sweden",venue:"AT&T Stadium",city:"Dallas",matchday:3},
            // Group G
            {date:"2026-06-15",time_et:"15:00",group:"G",home:"Belgium",away:"Egypt",venue:"Lumen Field",city:"Seattle",matchday:1},
            {date:"2026-06-15",time_et:"21:00",group:"G",home:"Iran",away:"New Zealand",venue:"SoFi Stadium",city:"Los Angeles",matchday:1},
            {date:"2026-06-21",time_et:"15:00",group:"G",home:"Belgium",away:"Iran",venue:"SoFi Stadium",city:"Los Angeles",matchday:2},
            {date:"2026-06-21",time_et:"21:00",group:"G",home:"Egypt",away:"New Zealand",venue:"BC Place",city:"Vancouver",matchday:2},
            {date:"2026-06-26",time_et:"23:00",group:"G",home:"Belgium",away:"New Zealand",venue:"BC Place",city:"Vancouver",matchday:3},
            {date:"2026-06-26",time_et:"23:00",group:"G",home:"Egypt",away:"Iran",venue:"Lumen Field",city:"Seattle",matchday:3},
            // Group H
            {date:"2026-06-15",time_et:"12:00",group:"H",home:"Spain",away:"Cape Verde",venue:"Mercedes-Benz Stadium",city:"Atlanta",matchday:1},
            {date:"2026-06-15",time_et:"18:00",group:"H",home:"Saudi Arabia",away:"Uruguay",venue:"Hard Rock Stadium",city:"Miami",matchday:1},
            {date:"2026-06-21",time_et:"12:00",group:"H",home:"Spain",away:"Saudi Arabia",venue:"Mercedes-Benz Stadium",city:"Atlanta",matchday:2},
            {date:"2026-06-21",time_et:"18:00",group:"H",home:"Cape Verde",away:"Uruguay",venue:"Hard Rock Stadium",city:"Miami",matchday:2},
            {date:"2026-06-26",time_et:"20:00",group:"H",home:"Spain",away:"Uruguay",venue:"Estadio Akron",city:"Guadalajara",matchday:3},
            {date:"2026-06-26",time_et:"20:00",group:"H",home:"Cape Verde",away:"Saudi Arabia",venue:"NRG Stadium",city:"Houston",matchday:3},
            // Group I
            {date:"2026-06-16",time_et:"15:00",group:"I",home:"France",away:"Senegal",venue:"MetLife Stadium",city:"New York/New Jersey",matchday:1},
            {date:"2026-06-16",time_et:"18:00",group:"I",home:"Iraq",away:"Norway",venue:"Gillette Stadium",city:"Boston",matchday:1},
            {date:"2026-06-22",time_et:"17:00",group:"I",home:"France",away:"Iraq",venue:"Lincoln Financial Field",city:"Philadelphia",matchday:2},
            {date:"2026-06-22",time_et:"20:00",group:"I",home:"Senegal",away:"Norway",venue:"MetLife Stadium",city:"New York/New Jersey",matchday:2},
            {date:"2026-06-26",time_et:"15:00",group:"I",home:"France",away:"Norway",venue:"Gillette Stadium",city:"Boston",matchday:3},
            {date:"2026-06-26",time_et:"15:00",group:"I",home:"Iraq",away:"Senegal",venue:"BMO Field",city:"Toronto",matchday:3},
            // Group J
            {date:"2026-06-16",time_et:"21:00",group:"J",home:"Argentina",away:"Algeria",venue:"Arrowhead Stadium",city:"Kansas City",matchday:1},
            {date:"2026-06-16",time_et:"00:00",group:"J",home:"Austria",away:"Jordan",venue:"Levi's Stadium",city:"San Francisco Bay Area",matchday:1},
            {date:"2026-06-22",time_et:"13:00",group:"J",home:"Argentina",away:"Austria",venue:"AT&T Stadium",city:"Dallas",matchday:2},
            {date:"2026-06-22",time_et:"23:00",group:"J",home:"Algeria",away:"Jordan",venue:"Levi's Stadium",city:"San Francisco Bay Area",matchday:2},
            {date:"2026-06-27",time_et:"22:00",group:"J",home:"Argentina",away:"Jordan",venue:"AT&T Stadium",city:"Dallas",matchday:3},
            {date:"2026-06-27",time_et:"22:00",group:"J",home:"Algeria",away:"Austria",venue:"Arrowhead Stadium",city:"Kansas City",matchday:3},
            // Group K
            {date:"2026-06-17",time_et:"13:00",group:"K",home:"Portugal",away:"DR Congo",venue:"NRG Stadium",city:"Houston",matchday:1},
            {date:"2026-06-17",time_et:"22:00",group:"K",home:"Uzbekistan",away:"Colombia",venue:"Estadio Azteca",city:"Mexico City",matchday:1},
            {date:"2026-06-23",time_et:"13:00",group:"K",home:"Portugal",away:"Uzbekistan",venue:"NRG Stadium",city:"Houston",matchday:2},
            {date:"2026-06-23",time_et:"22:00",group:"K",home:"DR Congo",away:"Colombia",venue:"Estadio Akron",city:"Guadalajara",matchday:2},
            {date:"2026-06-27",time_et:"19:30",group:"K",home:"Portugal",away:"Colombia",venue:"Hard Rock Stadium",city:"Miami",matchday:3},
            {date:"2026-06-27",time_et:"19:30",group:"K",home:"DR Congo",away:"Uzbekistan",venue:"Mercedes-Benz Stadium",city:"Atlanta",matchday:3},
            // Group L
            {date:"2026-06-17",time_et:"16:00",group:"L",home:"England",away:"Croatia",venue:"AT&T Stadium",city:"Dallas",matchday:1},
            {date:"2026-06-17",time_et:"19:00",group:"L",home:"Ghana",away:"Panama",venue:"BMO Field",city:"Toronto",matchday:1},
            {date:"2026-06-23",time_et:"16:00",group:"L",home:"England",away:"Ghana",venue:"Gillette Stadium",city:"Boston",matchday:2},
            {date:"2026-06-23",time_et:"19:00",group:"L",home:"Croatia",away:"Panama",venue:"BMO Field",city:"Toronto",matchday:2},
            {date:"2026-06-27",time_et:"17:00",group:"L",home:"England",away:"Panama",venue:"MetLife Stadium",city:"New York/New Jersey",matchday:3},
            {date:"2026-06-27",time_et:"17:00",group:"L",home:"Croatia",away:"Ghana",venue:"Lincoln Financial Field",city:"Philadelphia",matchday:3},
        ];
        matches = schedule;
    }

    const filtered = matches.filter((m) => {
        if (groupFilter !== "ALL" && m.group !== groupFilter) return false;
        if (mdFilter !== "ALL" && String(m.matchday) !== mdFilter) return false;
        return true;
    });

    const tbody = document.getElementById("wc-schedule-table");
    tbody.innerHTML = filtered.map((m, index) => `<tr data-wc-home="${escapeAttr(m.home)}" data-wc-away="${escapeAttr(m.away)}" data-row-index="${index}" style="cursor:pointer">
        <td>${escapeHtml(m.date)}</td><td>${escapeHtml(m.time_et || m.time)} ET</td><td>${escapeHtml(m.group)}</td>
        <td>${escapeHtml(m.home)}</td><td>${escapeHtml(m.away)}</td><td>${escapeHtml(m.venue)}, ${escapeHtml(m.city)}</td>
        <td><button class="text-button wc-schedule-briefing" type="button" data-wc-home="${escapeAttr(m.home)}" data-wc-away="${escapeAttr(m.away)}" style="font-size:0.72rem;padding:0.2rem 0.45rem">${escapeHtml(t("wc_briefing"))}</button></td>
    </tr>`).join("");

    tbody.querySelectorAll("tr[data-wc-home][data-wc-away]").forEach((row) => {
        row.addEventListener("click", async () => {
            const home = row.dataset.wcHome;
            const away = row.dataset.wcAway;
            await openWcFixtureBriefing(home, away);
        });
    });
    tbody.querySelectorAll(".wc-schedule-briefing").forEach((button) => {
        button.addEventListener("click", async (event) => {
            event.stopPropagation();
            button.disabled = true;
            await openWcFixtureBriefing(button.dataset.wcHome, button.dataset.wcAway);
        });
    });
}

function renderWcSquads() {
    const team = appState.wcSquadTeam;
    const rawSquad = wcGetSquad(team);
    const tbody = document.getElementById("wc-squad-table");
    const summary = document.getElementById("wc-squad-summary");
    if (rawSquad.length === 0) {
        const loading = wcApiData.squadLoading.has(team);
        const message = loading
            ? (appState.lang === "zh" ? "正在加载球队名单..." : "Loading squad...")
            : (appState.lang === "zh" ? "球队名单暂不可用" : "Squad unavailable");
        if (summary) {
            summary.innerHTML = `<div class="wc-metric"><span class="metric-value">${loading ? "…" : "—"}</span><span>${escapeHtml(message)}</span></div>`;
        }
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">${escapeHtml(message)}</td></tr>`;
        }
        const chart = getChart("wc-squad-chart");
        if (chart) chart.clear();
        return;
    }
    // Enrich squad with real ratings from /ratings API data
    const squad = matchSquadWithRatings(rawSquad);
    const rated = squad.filter((p) => p.hasRating);
    const big5 = squad.filter((p) => WC_BIG5.has(p.league));
    const avgRating = rated.length > 0 ? (rated.reduce((s, p) => s + p.rating, 0) / rated.length).toFixed(2) : "\u2014";
    const group = wcTeamGroup(team);

    // Show DEMO badge if API offline
    const squadTitle = document.getElementById("wc-squad-title");
    if (squadTitle) {
        let indicator = squadTitle.querySelector(".data-source-indicator");
        if (!indicator) {
            indicator = document.createElement("span");
            indicator.className = "status-pill data-source-indicator";
            squadTitle.appendChild(indicator);
        }
        if (!wcApiData.apiOnline) {
            indicator.textContent = "DEMO";
            indicator.className = "status-pill status-low data-source-indicator";
        } else {
            indicator.textContent = "";
            indicator.className = "status-pill data-source-indicator";
        }
    }

    // Coverage summary: X/Y players have ratings
    const coverageLabel = appState.lang === "zh"
        ? `${rated.length}/${squad.length} \u7403\u5458\u6709\u8bc4\u5206`
        : `${rated.length}/${squad.length} players rated`;

    document.getElementById("wc-squad-summary").innerHTML = `
        <div class="wc-metric"><span class="metric-value">${squad.length}</span><span>${escapeHtml(t("wc_squad_size"))}</span></div>
        <div class="wc-metric"><span class="metric-value">${rated.length}</span><span>${escapeHtml(t("wc_rated"))}</span></div>
        <div class="wc-metric"><span class="metric-value">${big5.length}</span><span>${escapeHtml(t("wc_big5"))}</span></div>
        <div class="wc-metric"><span class="metric-value">${escapeHtml(avgRating)}</span><span>${escapeHtml(t("wc_avg_rating"))}</span></div>
        <div class="wc-metric"><span class="metric-value">${escapeHtml(group)}</span><span>${escapeHtml(t("wc_group_col"))}</span></div>
        <div class="wc-metric"><span class="metric-value">${escapeHtml(coverageLabel)}</span><span>\u25CE ${escapeHtml(t("coverage"))}</span></div>
    `;

    tbody.innerHTML = squad.map((p) => {
        const confClass = p.hasRating
            ? (p.confidence === "HIGH" ? "status-high" : "status-medium")
            : "status-low";
        const confText = p.hasRating ? p.confidence : (appState.lang === "zh" ? "\u65E0\u6570\u636E" : "N/A");
        const ratingText = p.hasRating ? p.rating.toFixed(2) : "\u2014";
        const posText = p.position || "\u2014";
        return `<tr>
            <td>${escapeHtml(p.name)}</td><td>${escapeHtml(posText)}</td><td>${escapeHtml(p.club)}</td><td>${escapeHtml(p.league)}</td>
            <td>${escapeHtml(ratingText)}</td>
            <td><span class="status-pill ${confClass}">${escapeHtml(confText)}</span></td>
        </tr>`;
    }).join("");

    // Rating distribution chart
    const chart = getChart("wc-squad-chart");
    if (!chart) return;
    const chartData = [...rated].sort((a, b) => b.rating - a.rating);
    chart.setOption({
        animation: false,
        grid: {left: 80, right: 20, top: 20, bottom: 40},
        xAxis: {type: "value", axisLabel: {color: chartTextColor()}, splitLine: {lineStyle: {color: chartGridColor()}}},
        yAxis: {type: "category", data: chartData.map((p) => p.name), axisLabel: {color: chartTextColor(), fontSize: 11}},
        series: [{type: "bar", data: chartData.map((p) => p.rating), itemStyle: {color: "#7ca8ff"}}],
    }, true);
    chart.resize();

    if (squad.length > 0 && rated.length / squad.length < 0.5) {
        document.getElementById("wc-squad-summary").innerHTML += `<div class="wc-warning">\u25B2 ${escapeHtml(t("wc_low_coverage"))}</div>`;
    }
}

function renderWcCompare() {
    const teamA = appState.wcCompareA;
    const teamB = appState.wcCompareB;
    const squadA = wcGetSquad(teamA);
    const squadB = wcGetSquad(teamB);
    const ratedA = squadA.filter((p) => p.hasRating);
    const ratedB = squadB.filter((p) => p.hasRating);

    document.getElementById("wc-compare-a-name").textContent = teamA;
    document.getElementById("wc-compare-b-name").textContent = teamB;
    document.getElementById("wc-compare-role-a-name").textContent = teamA;
    document.getElementById("wc-compare-role-b-name").textContent = teamB;

    const avgA = ratedA.length > 0 ? (ratedA.reduce((s, p) => s + p.rating, 0) / ratedA.length).toFixed(2) : "—";
    const avgB = ratedB.length > 0 ? (ratedB.reduce((s, p) => s + p.rating, 0) / ratedB.length).toFixed(2) : "—";
    const big5A = squadA.filter((p) => WC_BIG5.has(p.league)).length;
    const big5B = squadB.filter((p) => WC_BIG5.has(p.league)).length;

    document.getElementById("wc-compare-table").innerHTML = [
        [t("wc_squad_size"), squadA.length, squadB.length],
        [t("wc_rated"), ratedA.length, ratedB.length],
        [t("wc_big5"), big5A, big5B],
        [t("wc_avg_rating"), avgA, avgB],
    ].map(([label, a, b]) => `<tr><td>${escapeHtml(label)}</td><td>${escapeHtml(a)}</td><td>${escapeHtml(b)}</td></tr>`).join("");

    const comparison = wcApiData.squadBalanceComparisonCache[`${teamA}|${teamB}`];
    const roleDepth = document.getElementById("wc-compare-role-depth");
    const roleDepthNote = document.getElementById("wc-compare-role-depth-note");
    const exportJson = document.getElementById("wc-export-role-comparison-json");
    const exportCsv = document.getElementById("wc-export-role-comparison-csv");
    if (comparison?.status === "ok") {
        roleDepth.innerHTML = (comparison.roles || []).map((row) => {
            const a = row.team_a || {};
            const b = row.team_b || {};
            const countDelta = Number(row.count_difference || 0);
            const coverageDelta = Number(row.rating_coverage_difference || 0);
            const formatSide = (details) => `${Number(details.count || 0)}/${Number(details.planning_target || 0)} · ${Math.round(Number(details.rating_coverage || 0) * 100)}%`;
            return `<tr><td>${escapeHtml(row.role || "—")}</td><td>${escapeHtml(formatSide(a))}</td><td>${escapeHtml(formatSide(b))}</td><td>${escapeHtml(countDelta > 0 ? `+${countDelta}` : String(countDelta))}</td><td>${escapeHtml(`${coverageDelta > 0 ? "+" : ""}${Math.round(coverageDelta * 100)}pp`)}</td></tr>`;
        }).join("") || `<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">—</td></tr>`;
        roleDepthNote.textContent = comparison.disclaimer || "";
    } else {
        roleDepth.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">${escapeHtml(appState.lang === "zh" ? "位置深度比较暂不可用" : "Role-depth comparison unavailable")}</td></tr>`;
        roleDepthNote.textContent = "";
    }
    if (exportJson) {
        exportJson.disabled = comparison?.status !== "ok";
        exportJson.onclick = () => exportWcSquadBalanceComparisonJSON(comparison);
    }
    if (exportCsv) {
        exportCsv.disabled = comparison?.status !== "ok";
        exportCsv.onclick = () => exportWcSquadBalanceComparisonCSV(comparison);
    }

    // Chart
    const chart = getChart("wc-compare-chart");
    if (chart) {
        const allRated = [
            ...ratedA.map((p) => ({...p, team: teamA})),
            ...ratedB.map((p) => ({...p, team: teamB})),
        ].sort((a, b) => b.rating - a.rating);
        chart.setOption({
            animation: false,
            grid: {left: 80, right: 20, top: 20, bottom: 40},
            xAxis: {type: "value", axisLabel: {color: chartTextColor()}, splitLine: {lineStyle: {color: chartGridColor()}}},
            yAxis: {type: "category", data: allRated.map((p) => p.name), axisLabel: {color: chartTextColor(), fontSize: 11}},
            series: [{type: "bar", data: allRated.map((p) => ({value: p.rating, itemStyle: {color: p.team === teamA ? "#7ca8ff" : "#57d68d"}}))}],
        }, true);
        chart.resize();
    }

    // Top 5
    const renderTop = (rated, el) => {
        el.innerHTML = rated.sort((a, b) => b.rating - a.rating).slice(0, 5).map((p) =>
            `<div class="rank-item"><div><strong>${escapeHtml(p.name)}</strong><span class="rank-meta">${escapeHtml(p.position)} · ${escapeHtml(p.club)}</span></div><span class="status-pill status-high">${p.rating.toFixed(2)}</span></div>`
        ).join("") || `<div style="color:var(--text-muted);text-align:center;padding:1rem">${t("wc_no_data")}</div>`;
    };
    document.getElementById("wc-compare-a-top-title").textContent = `${teamA} Top 5`;
    document.getElementById("wc-compare-b-top-title").textContent = `${teamB} Top 5`;
    renderTop([...ratedA], document.getElementById("wc-compare-a-top"));
    renderTop([...ratedB], document.getElementById("wc-compare-b-top"));

    renderWcMatchPredictionPanel(teamA, teamB);
}

function renderWcMatchPredictionPanel(teamA, teamB) {
    const panel = document.getElementById("wc-match-prediction-panel");
    if (!panel) return;

    const cacheKey = `${teamA}|${teamB}`;
    const prediction = wcApiData.matchPredictionCache[cacheKey];
    const briefing = wcApiData.matchBriefingCache[cacheKey];
    if (!prediction || prediction.error) {
        panel.innerHTML = `<div style="color:var(--text-muted);padding:0.8rem 0">${escapeHtml(t("wc_no_data"))}</div>`;
        return;
    }

    const match = {
        home: prediction.home_team || teamA,
        away: prediction.away_team || teamB,
        hw: prediction.home_win || 0,
        draw: prediction.draw || 0,
        aw: prediction.away_win || 0,
        xh: prediction.home_lambda || 0,
        xa: prediction.away_lambda || 0,
        score_matrix: prediction.score_matrix || null,
        model_type: prediction.model_type || "world_cup_strength_poisson",
        model_version: prediction.model_version || "wc-1.0",
    };

    const z = appState.lang === "zh";
    const briefingBody = briefing?.status === "ok"
        ? (() => {
            const home = briefing.teams?.home || {};
            const away = briefing.teams?.away || {};
            const coverage = (team) => `${Math.round(Number(team.squad?.rating_coverage || 0) * 100)}%`;
            const topPlayers = (team) => (team.squad?.top_rated_players || []).slice(0, 3)
                .map((player) => `${player.name} (${Number(player.rating).toFixed(1)})`).join(" · ") || (z ? "无评分球员" : "No rated players");
            return `
                <div class="wc-summary-row" style="margin:0.35rem 0 0.65rem">
                    <div><span>${z ? "主队评分覆盖" : "Home rating coverage"}</span><strong>${coverage(home)}</strong></div>
                    <div><span>${z ? "客队评分覆盖" : "Away rating coverage"}</span><strong>${coverage(away)}</strong></div>
                </div>
                <p style="font-size:0.78rem;line-height:1.55;margin:0.3rem 0"><strong>${escapeHtml(home.team || teamA)}</strong>: ${escapeHtml(topPlayers(home))}</p>
                <p style="font-size:0.78rem;line-height:1.55;margin:0.3rem 0"><strong>${escapeHtml(away.team || teamB)}</strong>: ${escapeHtml(topPlayers(away))}</p>
                <p style="font-size:0.75rem;color:var(--text-muted);line-height:1.5;margin:0.55rem 0">${escapeHtml((briefing.limitations || []).join(" "))}</p>
                <div class="filter-row" style="margin-top:0.65rem">
                    <button class="text-button wc-create-briefing-plan" type="button" style="font-size:0.8rem;padding:0.35rem 0.65rem">${z ? "创建本地战术方案" : "Create local tactical plan"}</button>
                    <button class="text-button wc-export-briefing-json" type="button" style="font-size:0.8rem;padding:0.35rem 0.65rem">${escapeHtml(t("wc_export_json"))}</button>
                    <button class="text-button wc-export-briefing-csv" type="button" style="font-size:0.8rem;padding:0.35rem 0.65rem">${escapeHtml(t("wc_export_csv"))}</button>
                </div>
            `;
        })()
        : `<button class="text-button wc-load-briefing" type="button" style="font-size:0.8rem;padding:0.35rem 0.65rem">${z ? "加载赛前简报" : "Load pre-match briefing"}</button>
           <p style="font-size:0.75rem;color:var(--text-muted);margin:0.5rem 0 0">${z ? "简报仅使用本地阵容评分和简化强度模型；离线快照不存在时会明确显示不可用。" : "Briefings use local roster ratings and a simplified strength model; unavailable offline snapshots stay unavailable."}</p>`;
    panel.innerHTML = `
        <div class="layout-2">
            <article class="liquid-panel table-panel">
                <div class="panel-head">
                    <h3>${escapeHtml(match.home)} vs ${escapeHtml(match.away)}</h3>
                    <span class="status-pill status-medium">${escapeHtml(match.model_type)}</span>
                </div>
                <div id="wc-match-probabilities"></div>
                <div class="wc-summary-row" id="wc-match-detail" style="margin-top:0.8rem"></div>
                <div id="wc-outcome-bar-chart" class="chart-box" style="height:220px;margin-top:0.8rem"></div>
            </article>
            <article class="liquid-panel chart-panel">
                <div class="panel-head">
                    <h3>${z ? "比分矩阵" : "Score Matrix"}</h3>
                </div>
                <div id="wc-score-chart" class="chart-box" style="height:340px"></div>
            </article>
        </div>
        <article class="liquid-panel compact-panel" style="margin-top:1rem">
            <div class="panel-head"><h3>${z ? "赛前比赛简报" : "Pre-match briefing"}</h3><span class="status-pill status-medium">local artifact</span></div>
            ${briefingBody}
        </article>
    `;

    document.getElementById("wc-match-probabilities").innerHTML = [
        [z ? "主胜" : "Home", match.hw],
        [z ? "平局" : "Draw", match.draw],
        [z ? "客胜" : "Away", match.aw],
    ].map(([label, value]) => `
        <div class="probability-row">
            <span class="probability-label">${escapeHtml(label)}</span>
            <div class="probability-track"><div class="probability-fill" style="width:${sanitizeCssPercent(value * 100)}%"></div></div>
            <strong>${sanitizeCssPercent(value * 100)}%</strong>
        </div>
    `).join("");

    document.getElementById("wc-match-detail").innerHTML = `
        <div><span>${escapeHtml(t("expected_goals"))}</span><strong>${match.xh.toFixed(2)} / ${match.xa.toFixed(2)}</strong></div>
        <div><span>${z ? "强度" : "Strength"}</span><strong>${Number(prediction.home_strength || 0).toFixed(3)} / ${Number(prediction.away_strength || 0).toFixed(3)}</strong></div>
        <div><span>model</span><strong>${escapeHtml(match.model_version)}</strong></div>
        <div><span>${z ? "主场修正" : "Host bonus"}</span><strong>${Number(prediction.host_bonus || 0).toFixed(2)}</strong></div>
    `;

    renderScoreMatrixInto("wc-score-chart", match);
    renderOutcomeBarInto("wc-outcome-bar-chart", match);

    const loadBriefing = panel.querySelector(".wc-load-briefing");
    if (loadBriefing) {
        loadBriefing.addEventListener("click", async () => {
            loadBriefing.disabled = true;
            await fetchWcMatchBriefing(teamA, teamB);
            renderWcMatchPredictionPanel(teamA, teamB);
        });
    }
    const createPlan = panel.querySelector(".wc-create-briefing-plan");
    if (createPlan && briefing?.status === "ok") {
        createPlan.addEventListener("click", () => createWcBriefingTacticalPlan(briefing));
    }
    const exportJson = panel.querySelector(".wc-export-briefing-json");
    if (exportJson && briefing?.status === "ok") {
        exportJson.addEventListener("click", () => exportWcBriefingJSON(briefing));
    }
    const exportCsv = panel.querySelector(".wc-export-briefing-csv");
    if (exportCsv && briefing?.status === "ok") {
        exportCsv.addEventListener("click", () => exportWcBriefingCSV(briefing));
    }
}

function renderWcProbability() {
    // Use API predictions if available
    if (wcApiData.predictions && wcApiData.predictions.groups) {
        // Group probability cards from API
        const container = document.getElementById("wc-prob-groups");
        container.innerHTML = wcApiData.predictions.groups.map((g) => {
            const rows = g.teams.map((x) => {
                const pct = Math.round(x.p_advance * 100);
                return `<div class="wc-prob-row"><span>${escapeHtml(x.team)}</span><div class="probability-track"><div class="probability-fill" style="width:${sanitizeCssPercent(pct)}%"></div></div><strong>${pct}%</strong></div>`;
            }).join("");
            return `<article class="liquid-panel compact-panel"><h3>${escapeHtml(g.group)}</h3>${rows}</article>`;
        }).join("");

        // 48-team ranking from API
        const ranking = wcApiData.predictions.ranking || [];
        document.getElementById("wc-prob-table").innerHTML = ranking.map((x) => `<tr>
            <td>${x.rank}</td><td>${escapeHtml(x.team)}</td><td>${escapeHtml(x.group || "?")}</td><td>${x.strength.toFixed(3)}</td>
        </tr>`).join("");
    } else {
        // Fallback: compute locally with proper ranking probability model
        const _AMP = 2.5; // exponent to widen gap between strong/weak teams
        const teams = wcAllTeams();
        const strengths = {};
        teams.forEach((t) => { strengths[t] = wcTeamStrength(t); });

        const container = document.getElementById("wc-prob-groups");
        container.innerHTML = Object.entries(WC_GROUPS).map(([letter, groupTeams]) => {
            const teamStrs = groupTeams.map((t) => ({team: t, raw: strengths[t], strength: Math.pow(strengths[t], _AMP)}));
            const total = teamStrs.reduce((s, x) => s + x.strength, 0);
            const rows = teamStrs.sort((a, b) => b.raw - a.raw).map((x) => {
                const p1 = x.strength / total;
                let p2 = 0;
                for (const other of teamStrs) {
                    if (other.team === x.team) continue;
                    const p1Other = other.strength / total;
                    const remaining = total - other.strength;
                    p2 += p1Other * (remaining > 0 ? x.strength / remaining : 0);
                }
                // p3rd: sum over each pair (j, k) being 1st and 2nd, prob i is best of remaining
                let p3 = 0;
                for (const j of teamStrs) {
                    if (j.team === x.team) continue;
                    const p1J = j.strength / total;
                    const remJ = total - j.strength;
                    for (const k of teamStrs) {
                        if (k.team === x.team || k.team === j.team) continue;
                        const p2Jk = p1J * (remJ > 0 ? k.strength / remJ : 0);
                        const remJk = total - j.strength - k.strength;
                        p3 += p2Jk * (remJk > 0 ? x.strength / remJk : 0);
                    }
                }
                const pAdvance = Math.min(p1 + p2 + p3 * (8 / 12), 1.0);
                const pct = Math.round(pAdvance * 100);
                return `<div class="wc-prob-row"><span>${escapeHtml(x.team)}</span><div class="probability-track"><div class="probability-fill" style="width:${sanitizeCssPercent(pct)}%"></div></div><strong>${pct}%</strong></div>`;
            }).join("");
            return `<article class="liquid-panel compact-panel"><h3>${escapeHtml(letter)}</h3>${rows}</article>`;
        }).join("");

        const ranked = teams.map((t) => ({team: t, strength: strengths[t], group: wcTeamGroup(t)}))
            .sort((a, b) => b.strength - a.strength);
        document.getElementById("wc-prob-table").innerHTML = ranked.map((x, i) => `<tr>
            <td>${i + 1}</td><td>${escapeHtml(x.team)}</td><td>${escapeHtml(x.group)}</td><td>${x.strength.toFixed(3)}</td>
        </tr>`).join("");
    }
}

function renderWcKnockout() {
    const z = appState.lang === "zh";
    const bracketEl = document.getElementById("wc-knockout-bracket");
    const tableEl = document.getElementById("wc-knockout-table");
    const statusEl = document.querySelector(".wc-knockout-status");

    if (!wcApiData.knockout || wcApiData.knockout.status !== "ok") {
        if (bracketEl) bracketEl.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:2rem">${z ? "淘汰赛数据加载中..." : "Loading knockout data..."}</p>`;
        if (tableEl) tableEl.innerHTML = "";
        if (statusEl) {
            statusEl.textContent = "API OFFLINE";
            statusEl.className = "status-pill status-low wc-knockout-status";
            statusEl.style.fontSize = "0.65rem";
        }
        return;
    }

    const data = wcApiData.knockout;
    if (statusEl) {
        if (wcApiData.apiOnline) {
            statusEl.textContent = "LIVE DATA";
            statusEl.className = "status-pill status-high wc-knockout-status";
        } else {
            statusEl.textContent = "STATIC";
            statusEl.className = "status-pill status-medium wc-knockout-status";
        }
        statusEl.style.fontSize = "0.65rem";
    }

    const roundLabels = z
        ? { r32: "32 强", r16: "16 强", qf: "四分之一决赛", sf: "半决赛", final: "决赛" }
        : { r32: "Round of 32", r16: "Round of 16", qf: "Quarter-Finals", sf: "Semi-Finals", final: "Final" };

    function matchupHtml(m) {
        if (!m) return "";
        const ht = escapeHtml(m.home_team || "?");
        const at = escapeHtml(m.away_team || "?");
        const hp = Math.round((m.home_win_probability || 0) * 100);
        const ap = Math.round((m.away_win_probability || 0) * 100);
        const homeWin = hp >= ap;
        return `<div class="ko-matchup">
            <div class="ko-team${homeWin ? " ko-winner" : ""}">
                <span class="ko-name">${ht}</span>
                <span class="ko-prob">${hp}%</span>
            </div>
            <div class="ko-team${!homeWin ? " ko-winner" : ""}">
                <span class="ko-name">${at}</span>
                <span class="ko-prob">${ap}%</span>
            </div>
        </div>`;
    }

    function roundColumn(label, matchups) {
        if (!matchups || matchups.length === 0) return "";
        const matches = matchups.map((m) => matchupHtml(m)).join("");
        return `<div class="ko-round">
            <h4 class="ko-round-title">${escapeHtml(label)}</h4>
            ${matches}
        </div>`;
    }

    const html = `<div class="ko-bracket">
        ${roundColumn(roundLabels.r32, data.round_of_32)}
        ${roundColumn(roundLabels.r16, data.round_of_16)}
        ${roundColumn(roundLabels.qf, data.quarter_finals)}
        ${roundColumn(roundLabels.sf, data.semi_finals)}
        ${roundColumn(roundLabels.final, data.final)}
    </div>`;

    if (bracketEl) bracketEl.innerHTML = html;

    // Tournament win probability table
    if (tableEl) {
        const winProb = data.tournament_win_probability || [];
        tableEl.innerHTML = winProb.map((x, i) => {
            const pct = (x.win_probability || 0) * 100;
            return `<tr>
                <td>${i + 1}</td>
                <td>${escapeHtml(x.team)}</td>
                <td>${escapeHtml(x.group || "?")}</td>
                <td>${(x.strength || 0).toFixed(3)}</td>
                <td><div class="probability-track"><div class="probability-fill" style="width:${sanitizeCssPercent(pct)}%"></div></div><strong>${pct.toFixed(1)}%</strong></td>
            </tr>`;
        }).join("");
    }
}

// ── Init World Cup ───────────────────────────────────────────────────────

async function initWorldCup() {
    const teams = wcAllTeams();
    // Populate group filter
    const groupFilter = document.getElementById("wc-group-filter");
    groupFilter.innerHTML = '<option value="ALL">ALL</option>' +
        Object.keys(WC_GROUPS).map((g) => `<option value="${escapeAttr(g)}">${escapeHtml(g)}</option>`).join("");
    // Populate squad team selector
    const squadSelect = document.getElementById("wc-squad-team");
    squadSelect.innerHTML = teams.map((tm) => `<option value="${escapeAttr(tm)}">${escapeHtml(tm)}</option>`).join("");
    squadSelect.value = "Argentina";
    appState.wcSquadTeam = "Argentina";
    // Populate compare selectors
    const selA = document.getElementById("wc-compare-a");
    const selB = document.getElementById("wc-compare-b");
    selA.innerHTML = teams.map((tm) => `<option value="${escapeAttr(tm)}">${escapeHtml(tm)}</option>`).join("");
    selB.innerHTML = teams.map((tm) => `<option value="${escapeAttr(tm)}">${escapeHtml(tm)}</option>`).join("");
    selA.value = "Argentina";
    selB.value = "France";
    appState.wcCompareA = "Argentina";
    appState.wcCompareB = "France";
    // Populate outlook team selector
    const outlookSelect = document.getElementById("wc-outlook-team");
    if (outlookSelect) {
        outlookSelect.innerHTML = teams.map((tm) => `<option value="${escapeAttr(tm)}">${escapeHtml(tm)}</option>`).join("");
        outlookSelect.value = "Argentina";
        const outlookBtn = document.getElementById("wc-outlook-btn");
        if (outlookBtn && !outlookBtn.dataset.bound) {
            outlookBtn.dataset.bound = "1";
            outlookBtn.addEventListener("click", () => {
                const tm = document.getElementById("wc-outlook-team").value;
                if (tm) loadAndRenderWcOutlook(tm);
            });
        }
        if (outlookSelect && !outlookSelect.dataset.bound) {
            outlookSelect.dataset.bound = "1";
            outlookSelect.addEventListener("change", () => {
                const tm = outlookSelect.value;
                if (tm) loadAndRenderWcOutlook(tm);
            });
        }
    }

    // Fetch API data in background, then re-render
    const [groupsData, scheduleData, predictionsData, teamsData, knockoutData] = await Promise.all([
        fetchWcGroups(),
        fetchWcSchedule(),
        fetchWcPredictions(),
        fetchWcTeams(),
        fetchWcKnockout(),
    ]);

    // Pre-fetch squads for the initially selected teams
    await Promise.all([
        fetchWcSquad("Argentina"),
        fetchWcSquad("France"),
        fetchWcSquadBalanceComparison("Argentina", "France"),
        fetchWcMatchPrediction("Argentina", "France"),
        fetchWcTeamOutlook("Argentina"),
    ]);

    // Re-render all WC views with API data
    renderWcSchedule();
    renderWcSquads();
    renderWcCompare();
    renderWcProbability();
    renderWcKnockout();
    // Render initial team outlook for the default selection
    renderWcOutlook(wcApiData.outlookCache["Argentina"]);

    // Update WC data status pills based on API availability
    document.querySelectorAll(".wc-data-status").forEach((el) => {
        if (wcApiData.apiOnline) {
            el.textContent = "LIVE DATA";
            el.className = "status-pill status-high wc-data-status";
            el.style.fontSize = "0.65rem";
        } else if (usingStaticData) {
            el.textContent = "STATIC";
            el.className = "status-pill status-medium wc-data-status";
            el.style.fontSize = "0.65rem";
        } else {
            el.textContent = "API OFFLINE";
            el.className = "status-pill status-low wc-data-status";
            el.style.fontSize = "0.65rem";
        }
    });
}

/* ── Tactical Board ─────────────────────────────────────────────────── */

let tacticalProject = null;
let _tacticalAutoSaveTimer = null;
function tacticalAutoSave() {
    clearTimeout(_tacticalAutoSaveTimer);
    _tacticalAutoSaveTimer = setTimeout(() => {
        if (tacticalProject && typeof TACTICAL_BOARD !== "undefined") {
            TACTICAL_BOARD.saveProject(tacticalProject);
        }
    }, 2000);
}

function syncObjectPropertyUI(obj) {
    const pathTypeEl = document.getElementById("tactical-path-type");
    const easingEl = document.getElementById("tactical-easing");
    const delayEl = document.getElementById("tactical-obj-delay");
    const pauseEl = document.getElementById("tactical-obj-pause");
    const addPathBtn = document.getElementById("tactical-add-path-point");

    if (obj && (obj.type === "player" || obj.type === "ball")) {
        if (pathTypeEl) pathTypeEl.value = obj.pathType || "linear";
        if (easingEl) easingEl.value = obj.easing || "linear";
        if (delayEl) delayEl.value = obj.delay_ms || 0;
        if (pauseEl) pauseEl.value = obj.pause_ms || 0;
        if (addPathBtn) {
            addPathBtn.textContent = "+ 路径点";
            addPathBtn.classList.remove("active");
        }
        // Exit path edit mode on new selection
        if (typeof TacticalRenderer !== "undefined") {
            TacticalRenderer.setPathEditMode(false, null);
        }
    } else {
        if (pathTypeEl) pathTypeEl.value = "linear";
        if (easingEl) easingEl.value = "linear";
        if (delayEl) delayEl.value = 0;
        if (pauseEl) pauseEl.value = 0;
    }
}

function renderTactical() {
    if (!tacticalProject) {
        tacticalProject = TACTICAL_BOARD.createProject("ScoutFootball 战术板");
        // Load default formation
        tacticalProject.objects = TACTICAL_BOARD.generateFormation("4-3-3", "home");
    }

    if (typeof TacticalRenderer !== "undefined") {
        TacticalRenderer.init("tactical-canvas", tacticalProject);
        TacticalRenderer.onChange = tacticalAutoSave;
        TacticalRenderer.onSelectionChange = (obj) => syncObjectPropertyUI(obj);
    }

    // Sync pitch type selector with current project
    const pitchTypeEl = document.getElementById("tactical-pitch-type");
    if (pitchTypeEl && tacticalProject.pitch_type) {
        pitchTypeEl.value = tacticalProject.pitch_type;
    }

    // Sync display mode selector
    const displayModeEl = document.getElementById("tactical-display-mode");
    if (displayModeEl) {
        displayModeEl.value = tacticalProject.displayMode || "single";
    }

    // Sync animation mode selector
    const animModeEl = document.getElementById("tactical-animation-mode");
    if (animModeEl) {
        animModeEl.value = tacticalProject.animationMode || "timing";
        const stepLabel = document.getElementById("tactical-step-duration-label");
        if (stepLabel) {
            stepLabel.style.display = (tacticalProject.animationMode === "step") ? "flex" : "none";
        }
    }
    const stepDurEl = document.getElementById("tactical-step-duration");
    if (stepDurEl) {
        stepDurEl.value = tacticalProject.stepDuration || 1000;
        const stepVal = document.getElementById("tactical-step-duration-value");
        if (stepVal) stepVal.textContent = (tacticalProject.stepDuration || 1000) + "ms";
    }

    // Update project list
    renderTacticalProjectList();

    // Update coaching notes panel for current frame
    updateCoachingNotesPanel();
    renderTacticalDecisionPack();
}

function updateCoachingNotesPanel() {
    const notesEl = document.getElementById("tactical-coaching-notes");
    if (!notesEl) return;
    if (typeof TacticalRenderer !== "undefined") {
        notesEl.value = TacticalRenderer.getCurrentFrameNotes();
    }
}

function buildPrematchDecisionPack(match) {
    const response = currentPrediction && !currentPrediction.error ? currentPrediction : null;
    const artifact = predictionMeta && typeof predictionMeta === "object" ? predictionMeta : {};
    const isAvailable = Boolean(response);
    const coverageCount = artifact.status === "ok" && Number.isFinite(Number(artifact.num_teams))
        ? Number(artifact.num_teams)
        : null;
    const coverageSummary = coverageCount
        ? `${coverageCount} teams`
        : (artifact.status === "ok" ? "artifact loaded; team count not recorded" : "artifact pending");
    const inputHash = response?.input_hash
        || artifact.input_hash
        || artifact.dixon_coles?.input_hash
        || artifact.poisson?.input_hash
        || "";
    const modelRunId = response?.model_run_id || artifact.model_run_id || "";
    const evidence = currentPredictionEvidenceFor(match);
    return TACTICAL_BOARD.createDecisionPack({
        match: { home: match.home, away: match.away },
        prediction: {
            status: isAvailable ? "available" : "not_loaded",
            model_type: response?.model_type || artifact.model_type || "",
            model_version: response?.model_version || artifact.model_version || "",
            probabilities: isAvailable ? {
                home_win: response.home_win,
                draw: response.draw,
                away_win: response.away_win,
            } : {},
            expected_goals: isAvailable ? {
                home: response.home_lambda,
                away: response.away_lambda,
            } : {},
            score_matrix: isAvailable ? response.score_matrix : null,
            coverage: {
                status: artifact.status || "unknown",
                summary: coverageSummary,
            },
        },
        provenance: {
            model_run_id: modelRunId,
            input_hash: inputHash,
            lineage_status: modelRunId ? "recorded" : (artifact.status === "ok" ? "artifact_snapshot" : "not_recorded"),
            snapshot: modelRunId ? "local model run record" : "local prediction artifact snapshot",
        },
        contextual_evidence: {
            non_additive_to_prediction: true,
            head_to_head: evidence.head_to_head,
            momentum: evidence.momentum,
        },
        limitations: [
            "Pre-match probabilities are model context, not a tactical recommendation.",
            "This decision pack and JSON export are browser-local; they are not synchronized to a server.",
            "Head-to-head, recent form, and momentum are separate context only; they do not change probabilities or prescribe tactics.",
            ...(isAvailable ? [] : ["Prediction output was unavailable when this plan was created; no fallback estimate is included."]),
        ],
    });
}

function renderTacticalDecisionPack() {
    const el = document.getElementById("tactical-decision-pack");
    const pack = tacticalProject?.metadata?.decision_pack;
    if (!el) return;
    if (!pack) {
        el.hidden = true;
        el.textContent = "";
        return;
    }
    const prediction = pack.prediction || {};
    const provenance = pack.provenance || {};
    const status = prediction.status === "available" ? "Prediction recorded" : "Prediction not loaded";
    const model = prediction.model_type || "model not recorded";
    const version = prediction.model_version ? ` (${prediction.model_version})` : "";
    const coverage = prediction.coverage?.summary || prediction.coverage?.status || "coverage unknown";
    const provenanceLabel = provenance.model_run_id
        ? `model run ${provenance.model_run_id}`
        : (provenance.snapshot || "local artifact snapshot");
    const context = pack.contextual_evidence || {};
    const h2h = context.head_to_head || {};
    const momentum = context.momentum || {};
    const h2hSummary = h2h.summary || {};
    const form = h2h.recent_form || {};
    const h2hLabel = h2h.status === "available"
        ? `${h2hSummary.total_meetings ?? 0} meetings; form ${form.home_trend || "not recorded"} / ${form.away_trend || "not recorded"}`
        : (h2h.status || "not loaded");
    const scoreline = momentum.current_scoreline || {};
    const momentumLabel = momentum.status === "available"
        ? `${scoreline.home_goals ?? "?"}-${scoreline.away_goals ?? "?"} at ${scoreline.minute ?? "?"}'`
        : (momentum.status || "not loaded");
    el.textContent = `${status} · ${model}${version}\nCoverage: ${coverage}\nProvenance: ${provenanceLabel}${provenance.input_hash ? ` · input ${provenance.input_hash}` : ""}\nSeparate context (non-additive): H2H ${h2hLabel}; momentum ${momentumLabel}.\nLocal-only: this decision pack remains in this browser and exported JSON.`;
    el.hidden = false;
}

function createPrematchPlan() {
    if (typeof TACTICAL_BOARD === "undefined") return;
    const match = selectedMatch();
    if (!match) return;

    // Create new tactical project
    const project = TACTICAL_BOARD.createProject(match.home + " vs " + match.away + " pre-match");
    project.pitch_type = "11v11";

    // Load home team formation (default 4-3-3)
    const homeObjs = TACTICAL_BOARD.generateFormation("4-3-3", "home");
    // Load away team formation (mirrored)
    const awayObjs = TACTICAL_BOARD.generateFormation("4-3-3", "away");
    project.objects = [...homeObjs, ...awayObjs];

    const decisionPack = buildPrematchDecisionPack(match);
    project.metadata = { decision_pack: decisionPack };
    project.source_attribution = "ScoutFootball tactical board + local prediction artifact snapshot";
    let notes = TACTICAL_BOARD.formatDecisionPackNotes(decisionPack);
    notes += "\n- Edit formations to plan your tactical approach";

    if (project.frames && project.frames[0]) {
        project.frames[0].notes = notes;
    }

    // Coaching points for the default formation
    const cp = TACTICAL_BOARD.getFormationCoachingPoints("4-3-3");
    if (cp) {
        const cpNotes = TACTICAL_BOARD.formatCoachingNotes(cp);
        if (project.frames && project.frames[0]) {
            project.frames[0].notes = notes + "\n\n--- Coaching Points ---\n" + cpNotes;
        }
    }

    // Save and switch to tactical view
    TACTICAL_BOARD.saveProject(project);
    tacticalProject = project;
    setView("tactical");
}

function createWcBriefingTacticalPlan(briefing) {
    if (typeof TACTICAL_BOARD === "undefined" || briefing?.status !== "ok") return;
    const fixture = briefing.fixture || {};
    const prediction = briefing.prediction || {};
    const home = briefing.teams?.home || {};
    const away = briefing.teams?.away || {};
    const inputSnapshot = briefing.input_snapshot || {};
    const hasPrediction = Number.isFinite(Number(prediction.home_win))
        && Number.isFinite(Number(prediction.draw))
        && Number.isFinite(Number(prediction.away_win));
    const coverage = (team) => `${team.team || "team"}: ${Math.round(Number(team.squad?.rating_coverage || 0) * 100)}% rating coverage`;
    const decisionPack = TACTICAL_BOARD.createDecisionPack({
        match: { home: fixture.home_team, away: fixture.away_team },
        prediction: {
            status: hasPrediction ? "available" : "not_loaded",
            model_type: prediction.model_type || "",
            model_version: prediction.model_version || "",
            probabilities: hasPrediction ? {
                home_win: prediction.home_win,
                draw: prediction.draw,
                away_win: prediction.away_win,
            } : {},
            expected_goals: hasPrediction ? {
                home: prediction.home_lambda,
                away: prediction.away_lambda,
            } : {},
            score_matrix: hasPrediction ? prediction.score_matrix : null,
            coverage: {
                status: "source_bounded",
                summary: `${coverage(home)}; ${coverage(away)}`,
            },
        },
        provenance: {
            model_run_id: inputSnapshot.rating_model_run_id || "",
            input_hash: inputSnapshot.rating_input_hash || "",
            feature_manifest_hash: inputSnapshot.feature_manifest_hash || "",
            lineage_status: "source_bounded_artifact",
            snapshot: "local World Cup match briefing artifact",
            briefing_schema: briefing.schema || "",
            briefing_version: briefing.version || "",
            briefing_source: briefing.source_attribution || "",
        },
        limitations: briefing.limitations || [
            "World Cup briefing limits were not available; treat this as local model context only.",
        ],
    });
    const project = TACTICAL_BOARD.createProject(`${fixture.home_team || "Home"} vs ${fixture.away_team || "Away"} World Cup pre-match`);
    project.pitch_type = "11v11";
    project.objects = [
        ...TACTICAL_BOARD.generateFormation("4-3-3", "home"),
        ...TACTICAL_BOARD.generateFormation("4-3-3", "away"),
    ];
    project.metadata = { decision_pack: decisionPack };
    project.source_attribution = "ScoutFootball tactical board + local World Cup match briefing artifact";
    if (project.frames?.[0]) {
        const topNames = (team) => (team.squad?.top_rated_players || []).slice(0, 3)
            .map((player) => `${player.name} (${Number(player.rating).toFixed(1)})`).join(", ") || "not recorded";
        project.frames[0].notes = `${TACTICAL_BOARD.formatDecisionPackNotes(decisionPack)}\n\nSquad context (local artifact, not a confirmed lineup):\n${home.team || fixture.home_team}: ${topNames(home)}\n${away.team || fixture.away_team}: ${topNames(away)}`;
    }
    TACTICAL_BOARD.saveProject(project);
    tacticalProject = project;
    setView("tactical");
}

function createWcTeamTemplate() {
    if (typeof TACTICAL_BOARD === "undefined") return;
    const team = appState.wcSquadTeam;
    if (!team) return;

    const rawSquad = wcGetSquad(team);
    const squad = matchSquadWithRatings(rawSquad);

    // Create project
    const project = TACTICAL_BOARD.createProject(team + " World Cup template");
    project.pitch_type = "11v11";

    // Default formation: 4-3-3
    const formationName = "4-3-3";
    const formation = TACTICAL_BOARD.FORMATIONS[formationName];
    if (!formation) return;

    // Build position list from formation
    const positionRoles = [
        { role: "GK", items: formation.GK || [] },
        { role: "CB", items: formation.CB || [] },
        { role: "FB", items: formation.FB || [] },
        { role: "DM", items: formation.DM || [] },
        { role: "CM", items: formation.CM || [] },
        { role: "AM", items: formation.AM || [] },
        { role: "W",  items: formation.W || [] },
        { role: "ST", items: formation.ST || [] },
    ];

    // Assign players from squad to positions
    const objects = [];
    let squadIdx = 0;
    let num = 1;
    for (const { role, items } of positionRoles) {
        for (const pos of items) {
            const player = squadIdx < squad.length ? squad[squadIdx] : null;
            const label = player ? player.name : "";
            objects.push(TACTICAL_BOARD.createPlayer(pos.x, pos.y, "home", label, num));
            squadIdx++;
            num++;
        }
    }

    // Add ball at center
    objects.push(TACTICAL_BOARD.createBall(50, 50));
    project.objects = objects;

    // Add coaching notes with squad info
    const rated = squad.filter(p => p.hasRating);
    const avgRating = rated.length > 0
        ? (rated.reduce((s, p) => s + p.rating, 0) / rated.length).toFixed(2)
        : "N/A";

    let notes = team + " World Cup Template\n";
    notes += "Formation: " + formationName + " | Squad: " + squad.length + " players\n";
    notes += "Rated: " + rated.length + " | Avg rating: " + avgRating + "\n";
    notes += "\n- Players assigned to formation positions from squad list";
    notes += "\n- Edit player names and positions as needed";
    notes += "\n- Add additional frames for set-piece plans";

    if (project.frames && project.frames[0]) {
        project.frames[0].notes = notes;
    }

    // Add formation coaching points
    const cp = TACTICAL_BOARD.getFormationCoachingPoints(formationName);
    if (cp && project.frames && project.frames[0]) {
        project.frames[0].notes += "\n\n--- Coaching Points ---\n" + TACTICAL_BOARD.formatCoachingNotes(cp);
    }

    TACTICAL_BOARD.saveProject(project);
    tacticalProject = project;
    setView("tactical");
}

function renderTacticalProjectList() {
    const list = document.getElementById("tactical-project-list");
    if (!list) return;

    const projects = TACTICAL_BOARD.listProjects();
    list.innerHTML = projects.length > 0
        ? projects.map((p) => `
            <div class="rank-item" style="cursor:pointer;display:flex;align-items:center;justify-content:space-between" data-board-id="${escapeAttr(p.board_id)}">
                <div>
                    <span class="tactical-project-title" data-board-id="${escapeAttr(p.board_id)}">${escapeHtml(p.title || "Untitled")}</span>
                    <span class="rank-meta">${escapeHtml(p.updated_at ? new Date(p.updated_at).toLocaleDateString() : "")}</span>
                </div>
                <button class="text-button" data-delete-board="${escapeAttr(p.board_id)}" title="Delete project" style="color:var(--danger,#e74c3c);font-size:0.85rem;padding:0.2rem 0.4rem">✕</button>
            </div>
        `).join("")
        : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No saved projects</div>';

    // Click to load
    list.querySelectorAll("[data-board-id]").forEach((el) => {
        if (!el.classList.contains("tactical-project-title")) {
            el.addEventListener("click", () => {
                const loaded = TACTICAL_BOARD.loadProject(el.dataset.boardId);
                if (loaded) {
                    tacticalProject = loaded;
                    renderTactical();
                }
            });
        }
    });

    // Double-click to rename project title
    list.querySelectorAll(".tactical-project-title").forEach((titleSpan) => {
        titleSpan.addEventListener("dblclick", (e) => {
            e.stopPropagation();
            const boardId = titleSpan.dataset.boardId;
            const currentTitle = titleSpan.textContent;
            const input = document.createElement("input");
            input.type = "text";
            input.value = currentTitle;
            input.style.cssText = "font-size:inherit;font-weight:bold;width:100%;padding:0 0.15rem;border:1px solid var(--accent,#7ca8ff);border-radius:3px;background:var(--bg,#1a1a2e);color:var(--text,#e0e0e0)";
            titleSpan.replaceWith(input);
            input.focus();
            input.select();

            function commitRename() {
                const newTitle = input.value.trim() || currentTitle;
                const loaded = TACTICAL_BOARD.loadProject(boardId);
                if (loaded) {
                    TACTICAL_BOARD.renameProject(loaded, newTitle);
                    TACTICAL_BOARD.saveProject(loaded);
                    if (tacticalProject && tacticalProject.board_id === boardId) {
                        tacticalProject.title = loaded.title;
                        tacticalProject.updated_at = loaded.updated_at;
                    }
                }
                renderTacticalProjectList();
            }

            function cancelRename() {
                renderTacticalProjectList();
            }

            input.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter") { ev.preventDefault(); commitRename(); }
                if (ev.key === "Escape") { ev.preventDefault(); cancelRename(); }
            });
            input.addEventListener("blur", commitRename);
        });
    });

    // Delete buttons
    list.querySelectorAll("[data-delete-board]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            TACTICAL_BOARD.deleteProject(btn.dataset.deleteBoard);
            renderTacticalProjectList();
        });
    });
}

function renderTacticalFrameList() {
    const list = document.getElementById("tactical-frame-list");
    if (!list || !tacticalProject || !tacticalProject.frames) return;

    const currentFrame = (typeof TacticalRenderer !== "undefined")
        ? TacticalRenderer.animationState.currentFrame
        : 0;

    const frameCount = tacticalProject.frames.length;

    list.innerHTML = tacticalProject.frames.map((frame, i) => `
        <div class="rank-item" style="cursor:pointer;display:flex;align-items:center;justify-content:space-between;${i === currentFrame ? 'background:var(--glass-bg-hover)' : ''}" data-frame-index="${i}">
            <div>
                <strong>${escapeHtml(frame.name || `Frame ${i + 1}`)}</strong>
                <span class="rank-meta">${escapeHtml(frame.duration_ms || 3000)}ms · ${escapeHtml((frame.objects || []).length)} objects</span>
            </div>
            <div style="display:flex;align-items:center;gap:0.2rem">
                <button class="text-button" data-frame-up="${i}" title="Move frame earlier" style="font-size:0.85rem;padding:0.2rem 0.4rem;${i === 0 ? 'opacity:0.3;pointer-events:none' : ''}">\u25C0</button>
                <button class="text-button" data-frame-down="${i}" title="Move frame later" style="font-size:0.85rem;padding:0.2rem 0.4rem;${i === frameCount - 1 ? 'opacity:0.3;pointer-events:none' : ''}">\u25B6</button>
                <button class="text-button" data-delete-frame="${i}" title="Delete frame" style="color:var(--danger,#e74c3c);font-size:0.85rem;padding:0.2rem 0.4rem">\u2715</button>
            </div>
        </div>
    `).join("");

    list.querySelectorAll("[data-frame-index]").forEach((el) => {
        el.addEventListener("click", () => {
            const idx = parseInt(el.dataset.frameIndex, 10);
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.goToFrame(idx);
                tacticalProject = TacticalRenderer.getProject();
                renderTacticalFrameList();
                updateCoachingNotesPanel();
            }
        });
    });

    // Frame up (move earlier)
    list.querySelectorAll("[data-frame-up]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const idx = parseInt(btn.dataset.frameUp, 10);
            if (idx <= 0 || !tacticalProject || !tacticalProject.frames) return;
            const tmp = tacticalProject.frames[idx - 1];
            tacticalProject.frames[idx - 1] = tacticalProject.frames[idx];
            tacticalProject.frames[idx] = tmp;
            TACTICAL_BOARD.saveProject(tacticalProject);
            renderTacticalFrameList();
        });
    });

    // Frame down (move later)
    list.querySelectorAll("[data-frame-down]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const idx = parseInt(btn.dataset.frameDown, 10);
            if (!tacticalProject || !tacticalProject.frames || idx >= tacticalProject.frames.length - 1) return;
            const tmp = tacticalProject.frames[idx + 1];
            tacticalProject.frames[idx + 1] = tacticalProject.frames[idx];
            tacticalProject.frames[idx] = tmp;
            TACTICAL_BOARD.saveProject(tacticalProject);
            renderTacticalFrameList();
        });
    });

    // Delete frame buttons
    list.querySelectorAll("[data-delete-frame]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const idx = parseInt(btn.dataset.deleteFrame, 10);
            if (tacticalProject && typeof TacticalRenderer !== "undefined") {
                TACTICAL_BOARD.removeFrame(tacticalProject, idx);
                tacticalProject = TacticalRenderer.getProject();
                renderTacticalFrameList();
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    // Restore theme preference
    const savedTheme = localStorage.getItem("sf-theme");
    if (savedTheme === "dark" || (!savedTheme && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
        document.body.classList.add("dark-mode");
        document.getElementById("theme-toggle").textContent = "☾";
    }
    const themeToggle = document.getElementById("theme-toggle");
    const startsDark = document.body.classList.contains("dark-mode");
    themeToggle.setAttribute("aria-pressed", startsDark ? "true" : "false");
    themeToggle.setAttribute("aria-label", startsDark ? "切换为浅色主题" : "切换为深色主题");
    applyLocale();
    renderMatchSelectors();
    // Start WC init early — it runs in parallel with other API calls
    const wcInitPromise = initWorldCup();
    bindEvents();
    setView("overview");

    // Load scouting localStorage state
    if (typeof SCOUTING_WORKSPACE !== "undefined") ensureScoutingWorkspaceMeta();
    loadScoutQueueStatuses();
    loadScoutShortlistNotes();
    loadScoutShortlistDossiers();
    loadWatchlistNotes();

    // Load real data from API in parallel
    const [ratingsData, meta, artifacts, teams, valueData, reviewData, predictionArtifact, predictionCalibrationData, runs, watchlistRows, shortlistRows, actionValues, actionEvidenceIndex, actionValueMatches, workspaceCapabilities, licenseResp] = await Promise.all([
        fetchRatings(),
        fetchRatingsMeta(),
        fetchArtifacts(),
        fetchTeams(),
        fetchValueReport(),
        fetchReviewQueue(),
        fetchPredictionMeta(),
        fetchPredictionCalibration(),
        fetchModelRuns(),
        fetchWatchlist(),
        fetchShortlist(),
        fetchActionValues(),
        fetchActionValueEvidenceIndex(),
        fetchPlayerMatchActionValues(),
        fetchScoutingWorkspaceCapabilities(),
        fetchLicense(),
    ]);

    players = ratingsData;
    ratingsMeta = meta;
    artifactSummary = artifacts;
    valuePlayers = valueData;
    reviewQueue = reviewData;
    predictionMeta = predictionArtifact;
    predictionCalibration = predictionCalibrationData;
    modelRuns = runs;
    watchlistData = watchlistRows;
    shortlistData = shortlistRows;
    actionValueSummary = actionValues;
    actionValueEvidenceIndex = actionEvidenceIndex;
    actionValueMatchSummary = actionValueMatches;
    scoutingWorkspaceCapabilities = workspaceCapabilities;
    licenseData = licenseResp;
    applyScoutingWorkspaceCapabilities();
    if (players.length > 0) {
        appState.selectedPlayerKey = players[0].key;
    }

    // Populate season filter dropdown
    const seasons = [...new Set(players.map((p) => p.season).filter(Boolean))].sort();
    const seasonSelect = document.getElementById("season-filter");
    seasonSelect.innerHTML = '<option value="ALL">ALL</option>' + seasons.map((s) => `<option value="${escapeAttr(s)}">${escapeHtml(s)}</option>`).join("");
    seasonSelect.value = appState.season;

    // Populate league filter dropdown
    const leagues = [...new Set(players.map((p) => p.league).filter(Boolean))].sort();
    const leagueSelect = document.getElementById("league-filter");
    leagueSelect.innerHTML = '<option value="ALL">ALL</option>' + leagues.map((l) => `<option value="${escapeAttr(l)}">${escapeHtml(l)}</option>`).join("");
    leagueSelect.value = appState.league;

    // Update team list for match prediction
    teamList = teams;
    if (teamList.length > 0) {
        appState.home = teamList[0];
        appState.away = teamList.length > 1 ? teamList[1] : teamList[0];
    }
    renderMatchSelectors();

    // Update overview metrics from artifacts API
    const metricValues = document.querySelectorAll(".coverage-strip .metric-value");
    if (metricValues[0]) metricValues[0].textContent = (artifacts.player_match_rows || 0).toLocaleString();
    if (metricValues[1]) metricValues[1].textContent = (artifacts.team_match_rows || 0).toLocaleString();
    if (metricValues[2]) metricValues[2].textContent = (artifacts.rating_rows || 0).toLocaleString();
    if (metricValues[3]) metricValues[3].textContent = (artifacts.event_samples || 0).toLocaleString();

    // Update data health
    const health = artifacts.data_health || {};
    const healthItems = document.querySelectorAll("#data-health-list .health-item");
    if (healthItems.length >= 3) {
        healthItems[0].querySelector(".status-pill").className = `status-pill ${health.oof_available ? "status-high" : "status-low"}`;
        healthItems[0].querySelector(".status-pill").textContent = health.oof_available ? "HIGH" : "LOW";
        healthItems[1].querySelector(".status-pill").className = `status-pill ${health.player_match_coverage ? "status-medium" : "status-low"}`;
        healthItems[1].querySelector(".status-pill").textContent = health.player_match_coverage ? "MED" : "LOW";
        healthItems[2].querySelector(".status-pill").className = `status-pill ${health.truth_labels_available ? "status-high" : "status-low"}`;
        healthItems[2].querySelector(".status-pill").textContent = health.truth_labels_available ? "HIGH" : "LOW";
    }

    const topCoveragePill = document.getElementById("top-coverage-pill");
    if (topCoveragePill) {
        topCoveragePill.textContent = health.player_match_coverage || artifacts.data_source_label || "local parquet";
        topCoveragePill.className = `status-pill ${health.player_match_coverage ? "status-medium" : "status-low"}`;
    }
    const topOofPill = document.getElementById("top-oof-pill");
    if (topOofPill) {
        const valueIsDemo = valueSummaryMeta.status === "demo";
        topOofPill.textContent = valueIsDemo
            ? `DEMO ${valueSummaryMeta.sample_count || 0}`
            : (valueSummaryMeta.sample_count ? `OOF ${valueSummaryMeta.sample_count}` : "OOF none");
        topOofPill.className = `status-pill ${valueIsDemo ? "status-medium" : (valueSummaryMeta.sample_count ? "status-high" : "status-low")}`;
    }

    renderActiveView();

    // Check API connection status (initial + periodic polling)
    const apiPill = document.getElementById("top-api-pill");
    function syncApiOfflineBanner() {
        const existingBanner = document.getElementById("global-demo-banner");
        if (apiOnline !== false || window.__SCOUTFOOTBALL_DESKTOP__) {
            if (existingBanner) existingBanner.remove();
            return;
        }

        if (existingBanner) return;
        const demoBanner = document.createElement("div");
        demoBanner.id = "global-demo-banner";
        demoBanner.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:9999;padding:0.3rem 1rem;background:rgba(255,107,107,0.15);color:#ff6b6b;font-size:0.72rem;text-align:center;border-bottom:1px solid rgba(255,107,107,0.3)";
        const z = appState.lang === "zh";
        demoBanner.textContent = z
            ? "◆ API 离线 — 使用静态缓存数据。启动后端获取实时数据：PYTHONPATH=src uv run python -m scoutfootball serve"
            : "◆ API Offline — Using cached static data. Start backend for live data: PYTHONPATH=src uv run python -m scoutfootball serve";
        document.body.prepend(demoBanner);
    }

    function checkApiStatus() {
        if (!apiPill) return;
        fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) })
            .then((resp) => {
                if (resp.ok) {
                    apiPill.textContent = "API OK";
                    apiPill.className = "status-pill status-high";
                    apiOnline = true;
                    usingStaticData = false;
                } else {
                    apiPill.textContent = "API ERR";
                    apiPill.className = "status-pill status-low";
                    apiOnline = false;
                }
                syncApiOfflineBanner();
            })
            .catch(() => {
                apiPill.textContent = usingStaticData ? "STATIC" : "OFFLINE";
                apiPill.className = "status-pill status-medium";
                apiOnline = false;
                syncApiOfflineBanner();
            });
    }
    checkApiStatus();
    // Poll every 10s so backend coming online is detected automatically
    setInterval(checkApiStatus, 10000);

    // Initialize World Cup — already started in parallel above, just await completion
    await wcInitPromise;
});

const SCOUT_QUEUE_KEY = "scout-queue-statuses";
const SCOUT_NOTES_KEY = "scout-shortlist-notes";
const SCOUT_DOSSIERS_KEY = "sf-shortlist-dossiers";
const SCOUT_LASTVISIT_KEY = "scout-watchlist-lastvisit";
const SCOUT_SNAPSHOT_KEY = "scout-watchlist-snapshot";
const SCOUT_WORKSPACE_META_KEY = "sf-scouting-workspace-meta";
const WATCHLIST_NOTES_KEY = "sf-watchlist-notes";
const PLAYER_WATCHLIST_KEY = "sf-player-watchlist";
const PLAYER_SHORTLIST_KEY = "sf-player-shortlist";
const STATUS_CYCLE = ["pending", "reviewing", "approved", "rejected"];
const STATUS_ICONS = { pending: "\u25CB", reviewing: "\u25B2", approved: "\u2713", rejected: "\u2717" };

let scoutQueueStatuses = {};
let scoutShortlistNotes = {};
let scoutShortlistDossiers = {};
let watchlistNotes = {};
let scoutSortMode = "priority";
let watchlistDiffCount = 0;
const SCOUT_PAGE_SIZE = 50;
let scoutCurrentPage = 1;
let pendingScoutingWorkspaceImport = null;
let lastScoutingTouchAt = 0;

function newScoutingWorkspaceId() {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
        return globalThis.crypto.randomUUID();
    }
    return `workspace-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function ensureScoutingWorkspaceMeta() {
    const now = new Date().toISOString();
    let stored = {};
    try {
        stored = JSON.parse(localStorage.getItem(SCOUT_WORKSPACE_META_KEY)) || {};
    } catch {
        stored = {};
    }
    const workspace = SCOUTING_WORKSPACE.createWorkspace({
        workspace_id: stored.workspace_id || newScoutingWorkspaceId(),
        created_at: stored.created_at || now,
        updated_at: stored.updated_at || now,
        exported_at: now,
        revision: stored.revision || 1,
        last_action: stored.last_action || "local-edit",
        imported_from: stored.imported_from || "",
        app_version: APP_VERSION,
    });
    const meta = workspace.audit;
    try {
        localStorage.setItem(SCOUT_WORKSPACE_META_KEY, JSON.stringify(meta));
    } catch {}
    return meta;
}

function touchScoutingWorkspace(lastAction = "local-edit") {
    const current = ensureScoutingWorkspaceMeta();
    const now = new Date().toISOString();
    const nowMs = Date.now();
    const coalescedEdit =
        lastAction === "local-edit"
        && lastScoutingTouchAt > 0
        && nowMs - lastScoutingTouchAt < 750;
    lastScoutingTouchAt = nowMs;
    const next = SCOUTING_WORKSPACE.createWorkspace({
        workspace_id: current.workspace_id,
        created_at: current.created_at,
        updated_at: now,
        exported_at: now,
        revision: Math.min(
            current.revision + (coalescedEdit ? 0 : 1),
            Number.MAX_SAFE_INTEGER,
        ),
        last_action: lastAction,
        imported_from: current.imported_from,
        app_version: APP_VERSION,
    }).audit;
    try {
        localStorage.setItem(SCOUT_WORKSPACE_META_KEY, JSON.stringify(next));
    } catch {}
    renderScoutingWorkspaceStatus();
    return next;
}

function currentSnapshotState() {
    let playerKeys = [];
    let savedAt = null;
    try {
        playerKeys = JSON.parse(localStorage.getItem(SCOUT_SNAPSHOT_KEY)) || [];
        const timestamp = Number(localStorage.getItem(SCOUT_LASTVISIT_KEY) || 0);
        savedAt = timestamp > 0 ? new Date(timestamp).toISOString() : null;
    } catch {
        playerKeys = [];
    }
    return { playerKeys, savedAt };
}

function buildCurrentScoutingWorkspace() {
    const meta = ensureScoutingWorkspaceMeta();
    const snapshot = currentSnapshotState();
    const ratingSnapshotIds = reviewQueue
        .map((player) => player.rating_snapshot_id)
        .filter(Boolean);
    return SCOUTING_WORKSPACE.createWorkspace({
        workspace_id: meta.workspace_id,
        created_at: meta.created_at,
        updated_at: meta.updated_at,
        exported_at: new Date().toISOString(),
        revision: meta.revision,
        last_action: meta.last_action,
        imported_from: meta.imported_from,
        app_version: APP_VERSION,
        rating_snapshot_ids: ratingSnapshotIds,
        review_statuses: scoutQueueStatuses,
        shortlist_notes: scoutShortlistNotes,
        watchlist_notes: watchlistNotes,
        shortlist_dossiers: scoutShortlistDossiers,
        watchlist: getPlayerWatchlist(),
        shortlist: getPlayerShortlist(),
        snapshot_player_keys: snapshot.playerKeys,
        snapshot_saved_at: snapshot.savedAt,
    });
}

function renderScoutingWorkspaceStatus() {
    const status = document.getElementById("scout-workspace-status");
    if (!status || typeof SCOUTING_WORKSPACE === "undefined") return;
    const workspace = buildCurrentScoutingWorkspace();
    const summary = SCOUTING_WORKSPACE.summarizeWorkspace(workspace);
    const locale = appState.lang === "zh" ? "zh-CN" : "en-US";
    const updated = new Date(summary.updated_at).toLocaleString(locale);
    const serverScope = scoutingWorkspaceCapabilities.enabled
        ? (
            scoutingWorkspaceServerRevision == null
            || scoutingWorkspaceServerId !== workspace.audit.workspace_id
            ? (appState.lang === "zh" ? "本地 API 可用" : "local API ready")
            : `${appState.lang === "zh" ? "本地 API" : "local API"} rev ${scoutingWorkspaceServerRevision}`
        )
        : (appState.lang === "zh" ? "仅当前浏览器" : "this browser only");
    const label = document.createElement("strong");
    label.textContent = `Workspace v${SCOUTING_WORKSPACE.VERSION}`;
    status.replaceChildren(
        label,
        document.createTextNode(
            ` · rev ${summary.revision} · ${summary.decision_count} ${appState.lang === "zh" ? "项决策" : "decisions"} · ${updated} · ${serverScope}`,
        ),
    );
}

function applyScoutingWorkspaceCapabilities() {
    const enabled = Boolean(scoutingWorkspaceCapabilities.enabled);
    for (const id of ["scout-server-save", "scout-server-load"]) {
        const button = document.getElementById(id);
        if (button) button.hidden = !enabled;
    }
    renderScoutingWorkspaceStatus();
}

async function scoutingWorkspaceBackendRequest(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        signal: AbortSignal.timeout(8_000),
    });
    let data = {};
    try {
        data = await response.json();
    } catch {
        data = {};
    }
    if (!response.ok) {
        const detail = data && typeof data.detail === "object" ? data.detail : {};
        const error = new Error(detail.code || `workspace_http_${response.status}`);
        error.status = response.status;
        error.currentRevision = detail.current_revision;
        throw error;
    }
    return data;
}

function workspaceForServerSave() {
    const current = buildCurrentScoutingWorkspace();
    const state = SCOUTING_WORKSPACE.toLocalState(current);
    const now = new Date().toISOString();
    return SCOUTING_WORKSPACE.createWorkspace({
        workspace_id: current.audit.workspace_id,
        created_at: current.audit.created_at,
        updated_at: now,
        exported_at: now,
        revision: current.audit.revision + 1,
        last_action: "server-save",
        imported_from: current.audit.imported_from,
        app_version: APP_VERSION,
        rating_snapshot_ids: current.source.rating_snapshot_ids,
        review_statuses: state.review_statuses,
        shortlist_notes: state.shortlist_notes,
        watchlist_notes: state.watchlist_notes,
        shortlist_dossiers: state.shortlist_dossiers,
        watchlist: state.watchlist,
        shortlist: state.shortlist,
        snapshot_player_keys: state.snapshot_player_keys,
        snapshot_saved_at: state.snapshot_saved_at,
    });
}

async function saveScoutingWorkspaceToServer() {
    try {
        const workspace = workspaceForServerSave();
        const headers = { "Content-Type": "application/json" };
        if (
            scoutingWorkspaceServerRevision != null
            && scoutingWorkspaceServerId === workspace.audit.workspace_id
        ) {
            headers["If-Match"] = `"${scoutingWorkspaceServerRevision}"`;
        }
        const result = await scoutingWorkspaceBackendRequest(
            `/scouting-workspaces/${encodeURIComponent(workspace.audit.workspace_id)}`,
            {
                method: "PUT",
                headers,
                body: SCOUTING_WORKSPACE.serializeWorkspace(workspace),
            },
        );
        persistScoutingWorkspace(workspace);
        scoutingWorkspaceServerId = workspace.audit.workspace_id;
        scoutingWorkspaceServerRevision = Number(result.server_revision);
        renderScouting();
        setScoutingWorkspaceMessage(
            appState.lang === "zh"
                ? `已保存到本地 API · rev ${scoutingWorkspaceServerRevision}`
                : `Saved to local API · rev ${scoutingWorkspaceServerRevision}`,
        );
    } catch (error) {
        if (error.status === 409 || error.status === 428) {
            try {
                const workspaceId = buildCurrentScoutingWorkspace().audit.workspace_id;
                const remote = await scoutingWorkspaceBackendRequest(
                    `/scouting-workspaces/${encodeURIComponent(workspaceId)}`,
                );
                showScoutingWorkspacePreview(
                    SCOUTING_WORKSPACE.normalizeWorkspace(remote.workspace),
                    appState.lang === "zh" ? "本地 API 冲突版本" : "Conflicting local API version",
                    remote,
                );
                setScoutingWorkspaceMessage(
                    appState.lang === "zh"
                        ? "检测到服务器版本冲突；请预览合并后再次保存"
                        : "Server revision conflict; preview and merge before saving again",
                    true,
                );
                return;
            } catch (loadError) {
                setScoutingWorkspaceMessage(workspaceErrorMessage(loadError), true);
                return;
            }
        }
        setScoutingWorkspaceMessage(workspaceErrorMessage(error), true);
    }
}

async function loadLatestScoutingWorkspaceFromServer() {
    try {
        const record = await scoutingWorkspaceBackendRequest("/scouting-workspaces/latest");
        showScoutingWorkspacePreview(
            SCOUTING_WORKSPACE.normalizeWorkspace(record.workspace),
            appState.lang === "zh" ? "本地 API 最新版本" : "Latest local API workspace",
            record,
        );
    } catch (error) {
        setScoutingWorkspaceMessage(workspaceErrorMessage(error), true);
    }
}

function setScoutingWorkspaceMessage(message, isError = false) {
    const status = document.getElementById("scout-snapshot-status");
    if (!status) return;
    status.textContent = message;
    status.style.color = isError ? "var(--bad)" : "var(--good)";
    setTimeout(() => {
        status.style.color = "";
        updateSnapshotStatus();
    }, 3500);
}

function workspaceErrorMessage(error) {
    const code = String(error && error.message ? error.message : error);
    const zh = appState.lang === "zh";
    const messages = {
        workspace_too_large: zh ? "工作区文件超过 1 MB 限制" : "Workspace exceeds the 1 MB limit",
        workspace_json_invalid: zh ? "工作区不是有效 JSON" : "Workspace is not valid JSON",
        workspace_not_object: zh ? "工作区根节点必须是对象" : "Workspace root must be an object",
        workspace_schema_invalid: zh ? "工作区 schema 不匹配" : "Workspace schema does not match",
        workspace_version_unsupported: zh ? "不支持该工作区版本" : "Workspace version is unsupported",
        workspace_not_found: zh ? "本地 API 中还没有工作区" : "No workspace is stored in the local API",
        workspace_persistence_disabled: zh ? "本地 API 持久化未启用" : "Local API persistence is disabled",
        workspace_remote_access_denied: zh ? "本地 API 拒绝远程工作区访问" : "Local API denied remote workspace access",
        workspace_revision_conflict: zh ? "服务器版本冲突" : "Server revision conflict",
        workspace_precondition_required: zh ? "保存前必须加载服务器版本" : "Load the server revision before saving",
    };
    return messages[code] || (zh ? `导入失败：${code}` : `Import failed: ${code}`);
}

function exportScoutingWorkspace() {
    if (typeof SCOUTING_WORKSPACE === "undefined") {
        setScoutingWorkspaceMessage(
            appState.lang === "zh" ? "工作区模块未加载" : "Workspace module is unavailable",
            true,
        );
        return;
    }
    touchScoutingWorkspace("manual-export");
    const workspace = buildCurrentScoutingWorkspace();
    const blob = new Blob([SCOUTING_WORKSPACE.serializeWorkspace(workspace)], {
        type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    link.href = url;
    link.download = `scoutfootball-scouting-workspace-${stamp}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
    setScoutingWorkspaceMessage(
        appState.lang === "zh" ? "工作区已导出" : "Workspace exported",
    );
}

function workspaceSummaryCard(title, summary) {
    const locale = appState.lang === "zh" ? "zh-CN" : "en-US";
    const updated = new Date(summary.updated_at).toLocaleString(locale);
    return `<div class="workspace-preview-card">
        <div><strong>${escapeHtml(title)}</strong><div class="rank-meta">rev ${summary.revision} · ${escapeHtml(updated)}</div></div>
        <div class="workspace-preview-metrics">
            <span><b>${summary.status_count}</b>${escapeHtml(appState.lang === "zh" ? "状态" : "statuses")}</span>
            <span><b>${summary.note_count}</b>${escapeHtml(appState.lang === "zh" ? "备注" : "notes")}</span>
            <span><b>${summary.dossier_count || 0}</b>${escapeHtml(appState.lang === "zh" ? "档案" : "dossiers")}</span>
            <span><b>${summary.watchlist_count + summary.shortlist_count}</b>${escapeHtml(appState.lang === "zh" ? "选择" : "selections")}</span>
        </div>
    </div>`;
}

function showScoutingWorkspacePreview(incoming, label, serverRecord = null) {
    const local = buildCurrentScoutingWorkspace();
    const analysis = SCOUTING_WORKSPACE.analyzeConflict(local, incoming);
    pendingScoutingWorkspaceImport = { incoming, local, analysis, serverRecord };
    const preview = document.getElementById("scout-workspace-preview");
    const dialog = document.getElementById("scout-workspace-dialog");
    if (!preview || !dialog) throw new Error("workspace_dialog_unavailable");
    const conflictText = analysis.total_conflicts > 0
        ? (appState.lang === "zh"
            ? `检测到 ${analysis.status_conflicts} 个状态冲突、${analysis.note_conflicts} 个备注冲突和 ${analysis.dossier_conflicts || 0} 个档案冲突。安全合并会保留两边条目，并以更新时间较新的工作区解决同键冲突。`
            : `Found ${analysis.status_conflicts} status conflicts, ${analysis.note_conflicts} note conflicts, and ${analysis.dossier_conflicts || 0} dossier conflicts. Safe merge keeps entries from both sides and uses the newer workspace for same-key conflicts.`)
        : (appState.lang === "zh"
            ? "未检测到同键冲突。仍会先预览，不会自动覆盖当前浏览器状态。"
            : "No same-key conflicts detected. The import is still previewed and never overwrites browser state automatically.");
    const serverText = serverRecord
        ? ` · ${appState.lang === "zh" ? "服务器" : "server"} rev ${Number(serverRecord.server_revision)}`
        : "";
    preview.innerHTML = `<div class="workspace-preview-grid">
        ${workspaceSummaryCard(appState.lang === "zh" ? "当前浏览器" : "Current browser", analysis.local)}
        ${workspaceSummaryCard(`${label}${serverText}`, analysis.incoming)}
    </div><p class="workspace-conflict-note">${escapeHtml(conflictText)}</p>`;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
}

async function previewScoutingWorkspaceImport(file) {
    try {
        if (file.size > SCOUTING_WORKSPACE.MAX_BYTES) throw new Error("workspace_too_large");
        const incoming = SCOUTING_WORKSPACE.parseWorkspace(await file.text());
        showScoutingWorkspacePreview(
            incoming,
            file.name || (appState.lang === "zh" ? "导入文件" : "Import file"),
        );
    } catch (error) {
        pendingScoutingWorkspaceImport = null;
        setScoutingWorkspaceMessage(workspaceErrorMessage(error), true);
    }
}

function replaceWorkspaceAudit(incoming) {
    const state = SCOUTING_WORKSPACE.toLocalState(incoming);
    const now = new Date().toISOString();
    return SCOUTING_WORKSPACE.createWorkspace({
        workspace_id: state.audit.workspace_id,
        created_at: state.audit.created_at,
        updated_at: now,
        exported_at: now,
        revision: state.audit.revision + 1,
        last_action: "import-replace",
        imported_from: state.audit.workspace_id,
        app_version: APP_VERSION,
        rating_snapshot_ids: incoming.source.rating_snapshot_ids,
        review_statuses: state.review_statuses,
        shortlist_notes: state.shortlist_notes,
        watchlist_notes: state.watchlist_notes,
        shortlist_dossiers: state.shortlist_dossiers,
        watchlist: state.watchlist,
        shortlist: state.shortlist,
        snapshot_player_keys: state.snapshot_player_keys,
        snapshot_saved_at: state.snapshot_saved_at,
    });
}

function persistScoutingWorkspace(workspace) {
    const state = SCOUTING_WORKSPACE.toLocalState(workspace);
    const keys = [
        SCOUT_QUEUE_KEY,
        SCOUT_NOTES_KEY,
        SCOUT_DOSSIERS_KEY,
        WATCHLIST_NOTES_KEY,
        PLAYER_WATCHLIST_KEY,
        PLAYER_SHORTLIST_KEY,
        SCOUT_SNAPSHOT_KEY,
        SCOUT_LASTVISIT_KEY,
        SCOUT_WORKSPACE_META_KEY,
    ];
    const backup = new Map(keys.map((key) => [key, localStorage.getItem(key)]));
    try {
        localStorage.setItem(SCOUT_QUEUE_KEY, JSON.stringify(state.review_statuses));
        localStorage.setItem(SCOUT_NOTES_KEY, JSON.stringify(state.shortlist_notes));
        localStorage.setItem(SCOUT_DOSSIERS_KEY, JSON.stringify(state.shortlist_dossiers));
        localStorage.setItem(WATCHLIST_NOTES_KEY, JSON.stringify(state.watchlist_notes));
        localStorage.setItem(PLAYER_WATCHLIST_KEY, JSON.stringify(state.watchlist));
        localStorage.setItem(PLAYER_SHORTLIST_KEY, JSON.stringify(state.shortlist));
        localStorage.setItem(SCOUT_SNAPSHOT_KEY, JSON.stringify(state.snapshot_player_keys));
        const savedAt = Date.parse(state.snapshot_saved_at);
        if (Number.isFinite(savedAt)) localStorage.setItem(SCOUT_LASTVISIT_KEY, String(savedAt));
        else localStorage.removeItem(SCOUT_LASTVISIT_KEY);
        localStorage.setItem(SCOUT_WORKSPACE_META_KEY, JSON.stringify(state.audit));
    } catch (error) {
        for (const [key, value] of backup) {
            if (value === null) localStorage.removeItem(key);
            else localStorage.setItem(key, value);
        }
        throw error;
    }
    loadScoutQueueStatuses();
    loadScoutShortlistNotes();
    loadScoutShortlistDossiers();
    loadWatchlistNotes();
    lastScoutingTouchAt = 0;
}

function applyScoutingWorkspaceImport(mode) {
    if (!pendingScoutingWorkspaceImport) return;
    const { local, incoming, serverRecord } = pendingScoutingWorkspaceImport;
    try {
        const result = mode === "replace"
            ? replaceWorkspaceAudit(incoming)
            : SCOUTING_WORKSPACE.mergeWorkspaces(
                local,
                incoming,
                serverRecord ? { workspaceId: incoming.audit.workspace_id } : undefined,
            );
        persistScoutingWorkspace(result);
        if (serverRecord) {
            scoutingWorkspaceServerId = incoming.audit.workspace_id;
            scoutingWorkspaceServerRevision = Number(serverRecord.server_revision);
        }
        pendingScoutingWorkspaceImport = null;
        const dialog = document.getElementById("scout-workspace-dialog");
        if (dialog) dialog.close();
        scoutCurrentPage = 1;
        renderScouting();
        setScoutingWorkspaceMessage(
            appState.lang === "zh"
                ? (serverRecord
                    ? "本地 API 工作区已载入；后续保存将检查服务器版本"
                    : (mode === "replace" ? "已替换本地工作区" : "工作区已安全合并"))
                : (serverRecord
                    ? "Local API workspace loaded; the next save will check its server revision"
                    : (mode === "replace" ? "Local workspace replaced" : "Workspace safely merged")),
        );
    } catch (error) {
        setScoutingWorkspaceMessage(workspaceErrorMessage(error), true);
    }
}

/* ── Player Watchlist / Shortlist (localStorage) ─────────────────── */
function getPlayerWatchlist() {
    try { return JSON.parse(localStorage.getItem(PLAYER_WATCHLIST_KEY)) || []; } catch { return []; }
}
function savePlayerWatchlist(list) {
    try {
        localStorage.setItem(PLAYER_WATCHLIST_KEY, JSON.stringify(list));
        touchScoutingWorkspace();
    } catch {}
}
function getPlayerShortlist() {
    try { return JSON.parse(localStorage.getItem(PLAYER_SHORTLIST_KEY)) || []; } catch { return []; }
}
function savePlayerShortlist(list) {
    try {
        localStorage.setItem(PLAYER_SHORTLIST_KEY, JSON.stringify(list));
        touchScoutingWorkspace();
    } catch {}
}
function isInPlayerWatchlist(playerKey) {
    return getPlayerWatchlist().some((p) => p.key === playerKey);
}
function isInPlayerShortlist(playerKey) {
    return getPlayerShortlist().some((p) => p.key === playerKey);
}
function togglePlayerWatchlist(player) {
    const list = getPlayerWatchlist();
    const idx = list.findIndex((p) => p.key === player.key);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push({ key: player.key, name: player.name, team: player.team, position: player.position, rating: player.rating });
    }
    savePlayerWatchlist(list);
    return idx < 0; // true if added
}
function togglePlayerShortlist(player) {
    const list = getPlayerShortlist();
    const idx = list.findIndex((p) => p.key === player.key);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push({ key: player.key, name: player.name, team: player.team, position: player.position, rating: player.rating });
    }
    savePlayerShortlist(list);
    return idx < 0;
}
function sendToTacticalBoard(player) {
    if (!tacticalProject) {
        tacticalProject = typeof TACTICAL_BOARD !== "undefined"
            ? TACTICAL_BOARD.createProject("ScoutFootball \u6218\u672f\u677f")
            : { title: "ScoutFootball \u6218\u672f\u677f", objects: [] };
    }
    // Add player marker to tactical project
    const marker = {
        type: "player_marker",
        id: "pm_" + Date.now(),
        label: player.name,
        position: player.position,
        rating: player.rating,
        team: player.team,
        x: 50 + Math.random() * 30 - 15,
        y: 50 + Math.random() * 30 - 15,
    };
    if (!tacticalProject.objects) tacticalProject.objects = [];
    tacticalProject.objects.push(marker);
    if (typeof TACTICAL_BOARD !== "undefined" && TACTICAL_BOARD.saveProject) {
        TACTICAL_BOARD.saveProject(tacticalProject);
    }
    setView("tactical");
}

function sendShortlistToTacticalBoard() {
    const players = mergeScoutingRows(shortlistData, getPlayerShortlist());
    if (!players.length) return;
    tacticalProject = typeof TACTICAL_BOARD !== "undefined"
        ? TACTICAL_BOARD.createProject("ScoutFootball shortlist tactical review")
        : { title: "ScoutFootball shortlist tactical review", objects: [] };
    tacticalProject.objects = players.map((player, index) => {
        const dossier = getShortlistDossier(player);
        return {
            type: "player_marker",
            id: `shortlist_${Date.now()}_${index}`,
            label: player.player_name || player.name || "Player",
            position: player.position_group || player.position || "",
            rating: player.optimized_score ?? player.rating ?? null,
            team: player.team || "",
            x: 20 + (index % 4) * 20,
            y: 28 + Math.floor(index / 4) * 18,
            shortlist_context: {
                priority: dossier.priority,
                recommendation: dossier.recommendation,
                target_role: dossier.target_role,
                rationale: dossier.rationale,
                scope: "browser-local-shortlist",
            },
        };
    });
    tacticalProject.source_attribution = "ScoutFootball browser-local shortlist tactical review";
    tacticalProject.notes = "Shortlist and dossier context are browser-local only; not a confirmed lineup or transfer recommendation.";
    if (typeof TACTICAL_BOARD !== "undefined" && TACTICAL_BOARD.saveProject) {
        TACTICAL_BOARD.saveProject(tacticalProject);
    }
    setView("tactical");
}

function loadScoutQueueStatuses() {
    try { scoutQueueStatuses = JSON.parse(localStorage.getItem(SCOUT_QUEUE_KEY)) || {}; } catch { scoutQueueStatuses = {}; }
}

function saveScoutQueueStatuses() {
    try {
        localStorage.setItem(SCOUT_QUEUE_KEY, JSON.stringify(scoutQueueStatuses));
        touchScoutingWorkspace();
    } catch {}
}

function loadScoutShortlistNotes() {
    try { scoutShortlistNotes = JSON.parse(localStorage.getItem(SCOUT_NOTES_KEY)) || {}; } catch { scoutShortlistNotes = {}; }
}

function saveScoutShortlistNotes() {
    try {
        localStorage.setItem(SCOUT_NOTES_KEY, JSON.stringify(scoutShortlistNotes));
        touchScoutingWorkspace();
    } catch {}
}

function loadScoutShortlistDossiers() {
    try { scoutShortlistDossiers = JSON.parse(localStorage.getItem(SCOUT_DOSSIERS_KEY)) || {}; } catch { scoutShortlistDossiers = {}; }
}

function saveScoutShortlistDossiers() {
    try {
        localStorage.setItem(SCOUT_DOSSIERS_KEY, JSON.stringify(scoutShortlistDossiers));
        localStorage.setItem(SCOUT_NOTES_KEY, JSON.stringify(scoutShortlistNotes));
        touchScoutingWorkspace();
    } catch {}
}

function loadWatchlistNotes() {
    try { watchlistNotes = JSON.parse(localStorage.getItem(WATCHLIST_NOTES_KEY)) || {}; } catch { watchlistNotes = {}; }
}

function saveWatchlistNotes() {
    try {
        localStorage.setItem(WATCHLIST_NOTES_KEY, JSON.stringify(watchlistNotes));
        touchScoutingWorkspace();
    } catch {}
}

function generateTacticalRole(player) {
    const pos = (player.position_group || player.position || "").toUpperCase();
    const score = Number(player.optimized_score || player.rating || 0);
    const minutes = Math.round(player.minutes || 0);
    const z = appState.lang === "zh";
    const roleMap = {
        GK: { zh: "门将 - 最后防线组织者", en: "Goalkeeper - Last line organizer" },
        CB: { zh: "中后卫 - 防线核心，负责拦截和出球", en: "Centre-Back - Defensive anchor, ball-playing defender" },
        FB: { zh: "边后卫 - 攻守转换枢纽，提供宽度", en: "Full-Back - Transition hub, provides width" },
        DM: { zh: "防守型中场 - 屏障型后腰，扫荡和分球", en: "Defensive Midfielder - Shield pivot, screen and distribute" },
        CM: { zh: "中场 - 节拍器型中场，串联攻守", en: "Central Midfielder - Tempo-setter, links attack and defense" },
        AM: { zh: "前腰 - 创造型10号位，关键传球和远射", en: "Attacking Midfielder - Creative No.10, key passes and long shots" },
        W: { zh: "边锋 - 突破型翼锋，内切或下底传中", en: "Winger - Dribbling flanker, cuts inside or delivers crosses" },
        ST: { zh: "前锋 - 终结者型中锋，禁区嗅觉", en: "Striker - Finisher centre-forward, box presence" },
    };
    const role = roleMap[pos] || { zh: "多功能球员", en: "Versatile player" };
    let tier = "";
    if (score >= 90) tier = z ? "世界级" : "World-class";
    else if (score >= 85) tier = z ? "精英级" : "Elite";
    else if (score >= 78) tier = z ? "可靠级" : "Reliable";
    else tier = z ? "发展中" : "Developing";
    const workload = minutes >= 2700 ? (z ? "主力" : "Starter") : (z ? "轮换" : "Rotation");
    return (z ? role.zh : role.en) + " | " + tier + " | " + workload;
}

function cycleQueueStatus(playerKey) {
    const player = reviewQueue.find((row) => queueStatusKey(row) === playerKey);
    const current = scoutQueueStatuses[playerKey] || (player ? getQueueStatus(player) : "pending");
    const idx = STATUS_CYCLE.indexOf(current);
    scoutQueueStatuses[playerKey] = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
    saveScoutQueueStatuses();
}

function computeWatchlistDiff(currentPlayers) {
    try {
        const snapshot = JSON.parse(localStorage.getItem(SCOUT_SNAPSHOT_KEY)) || [];
        const currentKeys = new Set(currentPlayers.map(p => p.player_name || p.name));
        const snapshotKeys = new Set(snapshot);
        let added = 0;
        for (const k of currentKeys) { if (!snapshotKeys.has(k)) added++; }
        watchlistDiffCount = added;
    } catch {
        watchlistDiffCount = 0;
    }
}

function saveWatchlistSnapshot(currentPlayers) {
    try {
        const keys = currentPlayers.map(p => p.player_name || p.name);
        localStorage.setItem(SCOUT_SNAPSHOT_KEY, JSON.stringify(keys));
        localStorage.setItem(SCOUT_LASTVISIT_KEY, String(Date.now()));
        touchScoutingWorkspace();
    } catch {}
}

function updateSnapshotStatus() {
    const status = document.getElementById("scout-snapshot-status");
    if (!status) return;
    try {
        const timestamp = Number(localStorage.getItem(SCOUT_LASTVISIT_KEY) || 0);
        if (!timestamp) {
            status.textContent = appState.lang === "zh" ? "尚未保存基线快照" : "No baseline snapshot saved";
            return;
        }
        const stamp = new Date(timestamp).toLocaleString(appState.lang === "zh" ? "zh-CN" : "en-US");
        status.textContent = watchlistDiffCount > 0
            ? `${watchlistDiffCount} ${appState.lang === "zh" ? "名新增 · 基线" : "new · baseline"} ${stamp}`
            : `${appState.lang === "zh" ? "无新增 · 基线" : "No additions · baseline"} ${stamp}`;
    } catch {
        status.textContent = "";
    }
}

function exportReviewQueueCSV() {
    const rows = sortReviewQueue(filterReviewQueue(reviewQueue), scoutSortMode);
    const header = ["player_id", "player_name", "team", "league", "season", "position_group", "optimized_score", "minutes", "confidence_level", "reason_code", "review_status", "reviewer_note", "as_of_date"];
    const data = rows.map((player) => [
        player.player_id || "",
        player.player_name || player.name || "",
        player.team || "",
        player.league || "",
        player.season || "",
        player.position_group || player.position || "",
        player.optimized_score || player.score || 0,
        player.minutes || 0,
        player.confidence_level || player.confidence || "",
        player.reason_code || "",
        getQueueStatus(player),
        player.reviewer_note || "",
        player.as_of_date || "",
    ]);
    const csv = [header, ...data].map((row) => row.map(csvCell).join(",")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "scoutfootball-review-queue.csv";
    link.click();
    URL.revokeObjectURL(url);
}

function buildShortlistDecisionPack() {
    const priorityOrder = { urgent: 0, standard: 1, monitor: 2 };
    const players = mergeScoutingRows(shortlistData, getPlayerShortlist())
        .map((player) => {
            const dossier = getShortlistDossier(player);
            return {
                player_id: player.player_id || player.key || "",
                player: player.player_name || player.name || "",
                team: player.team || "",
                position: player.position_group || player.position || "",
                rating: player.optimized_score ?? player.rating ?? null,
                confidence: player.confidence_level || player.confidence || "",
                reason_code: player.reason_code || "",
                priority: dossier.priority,
                recommendation: dossier.recommendation,
                target_role: dossier.target_role,
                rationale_and_risks: dossier.rationale,
            };
        })
        .sort((left, right) => (
            (priorityOrder[left.priority] ?? 9) - (priorityOrder[right.priority] ?? 9)
            || Number(right.rating || 0) - Number(left.rating || 0)
            || left.player.localeCompare(right.player)
        ));
    return {
        schema: "scoutfootball.shortlist-decision-pack",
        version: "1.0.0",
        status: players.length ? "ok" : "empty",
        exported_at: new Date().toISOString(),
        storage_scope: "browser-local-download",
        player_count: players.length,
        players,
        limitations: [
            "Shortlist selection and dossiers are browser-local decision context.",
            "This export is not a server-side audit record, transfer instruction, or cross-device sync artifact.",
            "Ratings and confidence reflect the loaded local or API data snapshot and may have incomplete coverage.",
        ],
    };
}

function _downloadShortlistDecisionPack(content, filename, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

function exportShortlistDecisionPackJSON() {
    const pack = buildShortlistDecisionPack();
    _downloadShortlistDecisionPack(
        JSON.stringify(pack, null, 2),
        "scoutfootball-shortlist-decision-pack.json",
        "application/json;charset=utf-8",
    );
}

function exportShortlistDecisionPackCSV() {
    const pack = buildShortlistDecisionPack();
    const lines = [
        ["# ScoutFootball Shortlist Decision Pack"],
        ["storage_scope", pack.storage_scope],
        ["player_count", pack.player_count],
        [],
        ["player_id", "player", "team", "position", "rating", "confidence", "reason_code", "priority", "recommendation", "target_role", "rationale_and_risks"],
        ...pack.players.map((player) => [
            player.player_id, player.player, player.team, player.position,
            player.rating ?? "", player.confidence, player.reason_code,
            player.priority, player.recommendation, player.target_role,
            player.rationale_and_risks,
        ]),
        [],
        ["# Limitations"],
        ...pack.limitations.map((limitation) => [limitation]),
        [],
        ["# Exported", pack.exported_at, `ScoutFootball v${APP_VERSION}`],
    ];
    _downloadShortlistDecisionPack(
        `\uFEFF${lines.map((row) => row.map(csvCell).join(",")).join("\n")}`,
        "scoutfootball-shortlist-decision-pack.csv",
        "text/csv;charset=utf-8",
    );
}
