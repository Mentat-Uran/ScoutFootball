const i18n = {
    zh: {
        nav_overview: "总览",
        nav_players: "球员",
        nav_value: "身价",
        nav_matches: "预测",
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
        value_rank: "偏离榜",
        undervalued: "低估",
        overvalued: "高估",
        match_selector: "比赛选择",
        home_team: "主队",
        away_team: "客队",
        score_matrix: "比分矩阵",
        review_queue: "复核队列",
        watchlist: "Watchlist",
        snapshot: "快照",
        action_kicker: "StatsBomb 样本",
        action_title: "动作价值热区",
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
        wc_kicker: "2026 美加墨世界杯",
        wc_schedule_title: "小组赛赛程",
        wc_squads_title: "球队名单 & 评分",
        wc_compare_title: "球队实力对比",
        wc_prob_title: "小组出线概率",
        wc_teams: "球队",
        wc_groups: "小组",
        wc_group_matches: "小组赛",
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
        value_fairness: "身价公平性",
        oof_residual_label: "OOF 残差",
        league_bias_label: "联赛偏差",
        position_bias_label: "位置偏差",
        age_curve_label: "年龄曲线",
        transfermarkt_notice: "Transfermarkt 数据需手动导入，当前为估算值",
        value_no_fairness: "暂无身价公平性数据",
    },
    en: {
        nav_overview: "Overview",
        nav_players: "Players",
        nav_value: "Value",
        nav_matches: "Prediction",
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
        value_rank: "Deviation board",
        undervalued: "Undervalued",
        overvalued: "Overvalued",
        match_selector: "Match selector",
        home_team: "Home",
        away_team: "Away",
        score_matrix: "Score matrix",
        review_queue: "Review queue",
        watchlist: "Watchlist",
        snapshot: "Snapshot",
        action_kicker: "StatsBomb sample",
        action_title: "Action value heat zones",
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
        wc_kicker: "2026 FIFA World Cup",
        wc_schedule_title: "Group Stage Schedule",
        wc_squads_title: "Squad Ratings",
        wc_compare_title: "Team Comparison",
        wc_prob_title: "Advancement Probability",
        wc_teams: "Teams",
        wc_groups: "Groups",
        wc_group_matches: "Group Matches",
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
        value_fairness: "Value Fairness",
        oof_residual_label: "OOF Residual",
        league_bias_label: "League Bias",
        position_bias_label: "Position Bias",
        age_curve_label: "Age Curve",
        transfermarkt_notice: "Transfermarkt data requires manual import, estimates shown",
        value_no_fairness: "No value fairness data available",
    },
};

const API_BASE = window.__SCOUTFOOTBALL_API__ || "";

let players = [];
let reviews = [];
let matches = [];
let ratingsMeta = { model_meta: {}, league_metrics: [] };
let artifactSummary = { data_health: {}, artifacts: [] };
let predictionMeta = { status: "no_data" };
let valueSummaryMeta = { sample_count: 0, metrics: {} };
let modelRuns = { count: 0, runs: [] };
let watchlistData = [];
let shortlistData = [];
let actionValueSummary = { status: "no_data", players: [], metrics: {} };

async function fetchRatings(position, league) {
    const params = new URLSearchParams();
    if (position && position !== "ALL") params.set("position", position);
    if (league) params.set("league", league);
    params.set("limit", "20000");
    try {
        const resp = await fetch(`${API_BASE}/ratings?${params}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
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
        console.warn("Failed to fetch ratings, using demo data:", err);
        return getDemoPlayers();
    }
}

function getDemoPlayers() {
    /* Real data from optimized_params (2425 season, GPU run 2026-06-09) */
    const demoData = [
        { name: "James Maddison", position: "W", team: "Tottenham", league: "Premier League", season: "2425", rating: 94.2, minutes: 1809, matches: 31 },
        { name: "Anthony Elanga", position: "AM", team: "Nott'm Forest", league: "Premier League", season: "2425", rating: 93.2, minutes: 2501, matches: 38 },
        { name: "Trent Alexander-Arnold", position: "FB", team: "Liverpool", league: "Premier League", season: "2425", rating: 92.4, minutes: 2365, matches: 33 },
        { name: "Michael Olise", position: "W", team: "Bayern Munich", league: "Bundesliga", season: "2425", rating: 91.5, minutes: 2334, matches: 34 },
        { name: "Ousmane Dembélé", position: "ST", team: "Paris SG", league: "Ligue 1", season: "2425", rating: 91.1, minutes: 1730, matches: 29 },
        { name: "Bruno Fernandes", position: "CM", team: "Manchester Utd", league: "Premier League", season: "2425", rating: 91.1, minutes: 3018, matches: 36 },
        { name: "Bukayo Saka", position: "W", team: "Arsenal", league: "Premier League", season: "2425", rating: 90.1, minutes: 1729, matches: 25 },
        { name: "Matheus Cunha", position: "W", team: "Wolves", league: "Premier League", season: "2425", rating: 89.8, minutes: 2597, matches: 33 },
        { name: "Pedro Porro", position: "FB", team: "Tottenham", league: "Premier League", season: "2425", rating: 89.7, minutes: 2610, matches: 33 },
        { name: "Jacob Murphy", position: "W", team: "Newcastle", league: "Premier League", season: "2425", rating: 89.7, minutes: 2360, matches: 35 },
        { name: "Declan Rice", position: "CM", team: "Arsenal", league: "Premier League", season: "2425", rating: 89.5, minutes: 2825, matches: 35 },
        { name: "Jordan Pickford", position: "GK", team: "Everton", league: "Premier League", season: "2425", rating: 88.8, minutes: 3420, matches: 38 },
        { name: "Kevin De Bruyne", position: "AM", team: "Man City", league: "Premier League", season: "2425", rating: 88.0, minutes: 1702, matches: 28 },
        { name: "Enzo Fernández", position: "CM", team: "Chelsea", league: "Premier League", season: "2425", rating: 87.9, minutes: 2947, matches: 36 },
        { name: "Mark Flekken", position: "GK", team: "Brentford", league: "Premier League", season: "2425", rating: 87.4, minutes: 3275, matches: 37 },
        { name: "Omar Marmoush", position: "W", team: "Ein Frankfurt", league: "Bundesliga", season: "2425", rating: 87.3, minutes: 1448, matches: 17 },
        { name: "Antonee Robinson", position: "FB", team: "Fulham", league: "Premier League", season: "2425", rating: 87.1, minutes: 3167, matches: 36 },
        { name: "Andreas Pereira", position: "CM", team: "Fulham", league: "Premier League", season: "2425", rating: 86.8, minutes: 2013, matches: 33 },
        { name: "Marcus Tavernier", position: "CM", team: "Bournemouth", league: "Premier League", season: "2425", rating: 86.4, minutes: 1939, matches: 29 },
        { name: "Raphinha", position: "AM", team: "Barcelona", league: "La Liga", season: "2425", rating: 85.8, minutes: 2839, matches: 36 },
        { name: "Federico Dimarco", position: "FB", team: "Inter", league: "Serie A", season: "2425", rating: 85.8, minutes: 2177, matches: 33 },
        { name: "Nico Williams", position: "CM", team: "Ath Bilbao", league: "La Liga", season: "2425", rating: 85.8, minutes: 1996, matches: 29 },
        { name: "Rayan Cherki", position: "AM", team: "Lyon", league: "Ligue 1", season: "2425", rating: 85.6, minutes: 2041, matches: 30 },
        { name: "Bradley Barcola", position: "ST", team: "Paris SG", league: "Ligue 1", season: "2425", rating: 85.3, minutes: 2181, matches: 34 },
        { name: "Dwight McNeil", position: "W", team: "Everton", league: "Premier League", season: "2425", rating: 85.2, minutes: 1371, matches: 21 },
        { name: "Alexander Isak", position: "ST", team: "Newcastle", league: "Premier League", season: "2425", rating: 84.8, minutes: 2756, matches: 34 },
        { name: "Marc Guéhi", position: "CB", team: "Crystal Palace", league: "Premier League", season: "2425", rating: 84.8, minutes: 3059, matches: 34 },
        { name: "Aleix García", position: "CM", team: "Leverkusen", league: "Bundesliga", season: "2425", rating: 84.7, minutes: 1455, matches: 28 },
        { name: "Sergio Gómez", position: "FB", team: "Real Sociedad", league: "La Liga", season: "2425", rating: 84.7, minutes: 2738, matches: 37 },
        { name: "Jonathan Clauss", position: "FB", team: "Nice", league: "Ligue 1", season: "2425", rating: 84.6, minutes: 2303, matches: 28 },
    ];
    return demoData.map(p => ({
        name: p.name,
        position: p.position,
        team: p.team,
        league: p.league,
        season: p.season,
        key: `${p.name}|${p.season}|${p.team}`,
        rating: p.rating,
        confidence: "MEDIUM",
        minutes: p.minutes,
        matches: p.matches,
        low_appearance: p.minutes < 900,
        npg_p90: p.position === "ST" ? 0.65 : p.position === "W" ? 0.35 : 0.12,
        assists_p90: p.position === "AM" ? 0.38 : p.position === "W" ? 0.30 : 0.10,
        defense_composite: ["CB", "DM", "FB", "GK"].includes(p.position) ? 72 : 45,
        possession_composite: ["CM", "AM", "DM"].includes(p.position) ? 75 : 50,
        percentile: 50 + (p.rating - 80) * 3,
        value: 0,
        residual: 0,
        radar: [
            Math.min(99, Math.max(10, p.rating - 30 + Math.random() * 20)),
            Math.min(99, Math.max(10, p.rating - 25 + Math.random() * 20)),
            Math.min(99, Math.max(10, p.rating - 35 + Math.random() * 20)),
            Math.min(99, Math.max(10, p.rating - 30 + Math.random() * 20)),
            Math.min(99, Math.max(10, p.rating - 25 + Math.random() * 20)),
        ],
    }));
}

async function fetchRatingsMeta() {
    try {
        const resp = await fetch(`${API_BASE}/ratings/meta`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.warn("Failed to fetch ratings meta:", err);
        return { model_meta: {}, league_metrics: [] };
    }
}

async function fetchArtifacts() {
    try {
        const resp = await fetch(`${API_BASE}/artifacts`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.warn("Failed to fetch artifacts, using demo data:", err);
        return {
            player_match_rows: 8689,
            team_match_rows: 10660,
            rating_rows: 27254,
            event_samples: 8141,
            data_health: { oof_available: true, truth_labels_available: false },
        };
    }
}

async function fetchTeams() {
    try {
        const resp = await fetch(`${API_BASE}/teams`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        return data.teams || [];
    } catch (err) {
        console.warn("Failed to fetch teams, using demo data:", err);
        return [
            "Arsenal", "Liverpool", "Man City", "Chelsea", "Real Madrid", "Barcelona",
            "Bayern", "Leverkusen", "PSG", "Inter", "Napoli", "Milan",
            "Man United", "Tottenham", "Dortmund", "Atletico Madrid",
        ];
    }
}

async function fetchPrediction(homeTeam, awayTeam) {
    try {
        const resp = await fetch(`${API_BASE}/predictions/${encodeURIComponent(homeTeam)}/${encodeURIComponent(awayTeam)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.warn("Failed to fetch prediction:", err);
        return null;
    }
}

async function fetchPredictionMeta() {
    try {
        const resp = await fetch(`${API_BASE}/predictions/meta`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.warn("Failed to fetch prediction meta:", err);
        return { status: "no_data" };
    }
}

async function fetchModelRuns() {
    try {
        const resp = await fetch(`${API_BASE}/reports/model-runs`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.warn("Failed to fetch model runs:", err);
        return { count: 0, runs: [] };
    }
}

async function fetchActionValues() {
    try {
        const resp = await fetch(`${API_BASE}/action-values?limit=12`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.warn("Failed to fetch action values:", err);
        return { status: "no_data", players: [], metrics: {} };
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
        const resp = await fetch(`${API_BASE}/license`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
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
    home: "Arsenal",
    away: "Barcelona",
    charts: {},
    playerPage: 1,
    playerPageSize: 50,
    playerSortCol: "rating",
    playerSortAsc: false,
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
        button.classList.toggle("active", button.dataset.view === view);
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
}

async function renderPlayerProfile() {
    const player = players.find((item) => item.key === appState.selectedPlayerKey) || players[0];
    if (!player) return;
    document.getElementById("selected-player-name").textContent = player.name;

    // Fetch real profile data for radar
    let profile = null;
    try {
        const resp = await fetch(`${API_BASE}/players/${encodeURIComponent(player.name)}?season=${player.season}`);
        if (resp.ok) profile = await resp.json();
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
            const label = appState.lang === 'zh' ? '置信原因' : 'Confidence reason';
            return `<div><span>${escapeHtml(label)}</span><strong style="color:var(--text-muted);font-size:0.82rem">${escapeHtml(reason)}</strong></div>`;
        })()}
        ${/* Data sources */ (() => {
            const sources = profile ? (profile.data_sources || profile.sources || []) : [];
            if (!sources || sources.length === 0) return '';
            const label = appState.lang === 'zh' ? '数据来源' : 'Data sources';
            return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(sources.join(', '))}</strong></div>`;
        })()}
        ${/* Position percentile */ (() => {
            const pct = profile ? (profile.position_percentile ?? profile.percentile_rank ?? null) : null;
            if (pct == null) return '';
            const label = appState.lang === 'zh' ? '位置百分位' : 'Position percentile';
            return `<div><span>${escapeHtml(label)}</span><strong>\u25C6 ${escapeHtml(String(Math.round(pct)))}pct</strong></div>`;
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
        tacticalActionsEl.innerHTML = `<button class="text-button" id="btn-send-tactical" type="button" style="font-size:0.82rem;padding:0.3rem 0.6rem">\u25C6 ${zT ? '发送到战术板' : 'Send to tactical board'}</button>`;
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
    }
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
    if (!appState.charts[id]) appState.charts[id] = echarts.init(element);
    return appState.charts[id];
}

function chartTextColor() {
    return document.body.classList.contains("light-mode") ? "rgba(21,23,28,.65)" : "rgba(247,248,251,.68)";
}

function chartGridColor() {
    return document.body.classList.contains("light-mode") ? "rgba(21,23,28,.12)" : "rgba(247,248,251,.13)";
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

let valuePlayers = [];

// Mock value data for demo when API is unavailable
const MOCK_VALUE_DATA = (() => {
    const names = [
        "Mbapp\u00e9","Haaland","Vinicius Jr","Saka","Salah","Kane","Bellingham","Pedri","Rodri","Wirtz",
        "Musiala","Odegaard","Palmer","Foden","Rice","Gavi","Valverde","Bruno Fernandes","Lewandowski","De Bruyne",
        "Gundogan","Bernardo Silva","Griezmann","Lamine Yamal","Reus","Maddison","Xavi Simons","Leao","Osimhen","Isak",
        "Nkunku","Diaz","Barcola","Kvaratskhelia","Sane","Havertz","Martinelli","Gyokeres","Sesko","Dovbyk",
        "Thuram","Lookman","Lautaro Martinez","Lozano","Adeyemi","Mudryk","Nico Williams","Olmo","Zubimendi","Grimaldo",
        "Kulusevski","Mac Allister","Onana","Ruben Dias","Saliba","Van Dijk","Araujo","Marquinhos","Alisson","Courtois",
        "Raphinha","Mikel Merino","Zaire-Emery","Branco","Simakan","Bastoni","Achraf","Theo Hernandez","Robertson","Alexander-Arnold",
    ];
    const teams = [
        "Real Madrid","Man City","Real Madrid","Arsenal","Liverpool","Bayern","Real Madrid","Barcelona","Man City","Leverkusen",
        "Bayern","Arsenal","Chelsea","Man City","Arsenal","Barcelona","Real Madrid","Man United","Barcelona","Man City",
        "Barcelona","Man City","Atl\u00e9tico","Barcelona","Dortmund","Tottenham","RB Leipzig","Milan","Napoli","Newcastle",
        "Chelsea","Liverpool","PSG","Napoli","Bayern","Arsenal","Arsenal","Sporting","RB Leipzig","Roma",
        "Inter","Atalanta","Inter","PSV","Dortmund","Chelsea","Athletic","Barcelona","Real Sociedad","Leverkusen",
        "Tottenham","Liverpool","Man United","Man City","Arsenal","Liverpool","Barcelona","PSG","Liverpool","Real Madrid",
        "Barcelona","Real Sociedad","PSG","Leverkusen","RB Leipzig","Inter","PSG","Milan","Liverpool","Liverpool",
    ];
    const residuals = [
        0.82,0.65,0.71,0.45,0.38,0.22,0.55,0.30,0.12,0.48,
        0.42,0.18,0.62,0.08,-0.05,0.15,0.10,0.28,-0.35,-0.18,
        -0.22,-0.10,0.05,0.88,-0.42,0.32,0.35,0.25,0.15,0.40,
        0.20,-0.08,0.52,0.58,-0.15,-0.12,-0.25,0.72,0.30,0.18,
        0.10,0.45,-0.08,-0.30,-0.20,-0.55,0.38,0.12,0.05,-0.10,
        -0.15,-0.08,-0.22,-0.35,-0.18,-0.42,-0.25,-0.15,-0.50,-0.38,
        0.15,-0.05,0.22,-0.12,-0.18,-0.08,-0.10,-0.20,-0.45,-0.28,
    ];
    const actualValues = [
        180,170,150,120,90,110,120,100,90,130,
        120,100,90,100,80,80,90,80,50,60,
        30,60,40,100,25,55,60,70,75,65,
        55,65,50,70,45,55,50,65,40,35,
        45,35,50,20,30,28,45,40,30,25,
        35,50,40,55,60,45,50,45,50,40,
        45,30,45,30,22,40,50,45,30,55,
    ];
    return names.map((name, i) => {
        const actual = actualValues[i] * 1e6;
        const predicted = Math.round(actual * Math.exp(-residuals[i]));
        return {
            name, team: teams[i], season: "2526",
            actualValue: actual, predictedValue: predicted,
            residual: residuals[i],
            fairness: residuals[i] > 0.3 ? "cheap" : residuals[i] < -0.3 ? "expensive" : "fair",
        };
    });
})();

async function fetchValueReport() {
    try {
        const resp = await fetch(`${API_BASE}/value-summary`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        valueSummaryMeta = data;
        if (data.players && data.players.length > 0) {
            return data.players.map((p) => ({
                name: p.player || "",
                team: p.team || "",
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

function renderValue() {
    const isMock = valuePlayers.length === 0;
    const data = isMock ? MOCK_VALUE_DATA : valuePlayers;
    const sorted = [...data].sort((a, b) => (
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
                fhtml += `<div class="wc-metric"><span class="metric-value">${Number(val).toFixed(3)}</span><span>${escapeHtml(t('oof_residual_label'))}</span></div>`;
            }
            if (metrics.league_bias != null) {
                fhtml += `<div class="wc-metric"><span class="metric-value">${Number(metrics.league_bias).toFixed(3)}</span><span>${escapeHtml(t('league_bias_label'))}</span></div>`;
            }
            if (metrics.position_bias != null) {
                fhtml += `<div class="wc-metric"><span class="metric-value">${Number(metrics.position_bias).toFixed(3)}</span><span>${escapeHtml(t('position_bias_label'))}</span></div>`;
            }
            if (metrics.age_curve_coeff != null || metrics.age_curve != null) {
                const val = metrics.age_curve_coeff ?? metrics.age_curve;
                fhtml += `<div class="wc-metric"><span class="metric-value">${Number(val).toFixed(3)}</span><span>${escapeHtml(t('age_curve_label'))}</span></div>`;
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
}

let currentPrediction = null;

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
        };
    }
    return { home: appState.home, away: appState.away, hw: 0.34, draw: 0.28, aw: 0.38, xh: 1.32, xa: 1.42 };
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
async function renderMatches() {
    const myId = ++_matchRenderId;
    // Fetch prediction from API
    currentPrediction = await fetchPrediction(appState.home, appState.away);
    if (myId !== _matchRenderId) return; // stale
    const match = selectedMatch();
    const predictionCoverage = predictionMeta.status === "ok" && predictionMeta.num_teams
        ? `${predictionMeta.num_teams} teams`
        : "artifact pending";
    document.getElementById("match-title").textContent = `${match.home} vs ${match.away}`;
    const probabilityRows = [
        [t("home"), match.hw],
        [t("draw"), match.draw],
        [t("away"), match.aw],
    ];
    document.getElementById("match-probabilities").innerHTML = probabilityRows.map(([label, value]) => `
        <div class="probability-row">
            <span class="probability-label">${escapeHtml(label)}</span>
            <div class="probability-track"><div class="probability-fill" style="width:${sanitizeCssPercent(value * 100)}%"></div></div>
            <strong>${sanitizeCssPercent(value * 100)}%</strong>
        </div>
    `).join("");
    document.getElementById("match-detail").innerHTML = `
        <div><span>${escapeHtml(t("expected_goals"))}</span><strong>${match.xh.toFixed(2)} / ${match.xa.toFixed(2)}</strong></div>
        <div><span>${escapeHtml(t("coverage"))}</span><strong>${escapeHtml(predictionCoverage)}</strong></div>
        <div><span>model</span><strong>${escapeHtml(predictionMeta.model_type || "Poisson")}</strong></div>
        <div><span>train_rows</span><strong>${escapeHtml(predictionMeta.train_rows || "pending")}</strong></div>
    `;
    renderScoreMatrix(match);

    // Calibration section below score matrix
    const calibEl = document.getElementById('match-calibration');
    if (calibEl) {
        const rho = predictionMeta.dc_rho ?? predictionMeta.rho ?? null;
        const homeAdv = predictionMeta.home_advantage ?? predictionMeta.home_adv ?? null;
        const coverage = predictionMeta.coverage ?? predictionMeta.team_coverage ?? null;
        const brier = predictionMeta.brier_score ?? predictionMeta.brier ?? null;
        const rps = predictionMeta.rps ?? predictionMeta.ranked_probability_score ?? null;
        const modelVer = predictionMeta.model_version || predictionMeta.version || '';
        const modelType = predictionMeta.model_type || 'Poisson';
        const lowScore = predictionMeta.low_score_analysis || predictionMeta.low_score || {};
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
        const poissonPred = predictionMeta.poisson_prediction ?? predictionMeta.poisson_pred ?? null;
        const dcPred = predictionMeta.dixon_coles_prediction ?? predictionMeta.dc_pred ?? null;
        if (poissonPred && dcPred) {
            calibHtml += `<p style="margin:0.5rem 0 0.2rem;font-size:0.72rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em">${z ? '模型对比' : 'Model comparison'}</p>`;
            calibHtml += `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.2rem 0.6rem;font-size:0.75rem">`;
            calibHtml += `<div style="color:var(--text-muted)">${z ? '结果' : 'Outcome'}</div>`;
            calibHtml += `<div style="color:var(--text-muted)">Poisson</div>`;
            calibHtml += `<div style="color:var(--text-muted)">Dixon-Coles</div>`;
            const outcomes = ['home', 'draw', 'away'];
            const labels = [z ? '主胜' : 'Home', z ? '平局' : 'Draw', z ? '客胜' : 'Away'];
            for (let i = 0; i < outcomes.length; i++) {
                const pVal = poissonPred[outcomes[i]] ?? poissonPred[i] ?? null;
                const dcVal = dcPred[outcomes[i]] ?? dcPred[i] ?? null;
                calibHtml += `<div>${escapeHtml(labels[i])}</div>`;
                calibHtml += `<div>${pVal != null ? (Number(pVal) * 100).toFixed(1) + '%' : '–'}</div>`;
                calibHtml += `<div>${dcVal != null ? (Number(dcVal) * 100).toFixed(1) + '%' : '–'}</div>`;
            }
            calibHtml += `</div>`;
        }

        calibEl.innerHTML = calibHtml;
    }
}

function poisson(lambda, k) {
    let factorial = 1;
    for (let i = 2; i <= k; i += 1) factorial *= i;
    return Math.exp(-lambda) * (lambda ** k) / factorial;
}

function renderScoreMatrix(match) {
    const chart = getChart("score-chart");
    if (!chart) return;
    const data = [];
    for (let home = 0; home <= 5; home += 1) {
        for (let away = 0; away <= 5; away += 1) {
            data.push([away, home, +(poisson(match.xh, home) * poisson(match.xa, away)).toFixed(3)]);
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

let reviewQueue = [];

async function fetchReviewQueue() {
    try {
        const resp = await fetch(`${API_BASE}/review-queue?limit=50`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        return (data.players || []).map((p) => ({
            name: p.player || "",
            team: p.team || "",
            position: p.position_group || "",
            confidence: (p.confidence_level || "LOW").toUpperCase(),
            score: +(p.optimized_score || 0).toFixed(1),
            minutes: Math.round(p.minutes || 0),
        }));
    } catch (err) {
        console.warn("Failed to fetch review queue, using demo data:", err);
        return [
            { name: "Lamine Yamal", team: "Barcelona", position: "W", confidence: "LOW", score: 83.5, minutes: 2100 },
            { name: "Pau Cubarsí", team: "Barcelona", position: "CB", confidence: "LOW", score: 78.2, minutes: 1800 },
            { name: "Warren Zaïre-Emery", team: "PSG", position: "CM", confidence: "MEDIUM", score: 79.5, minutes: 2000 },
            { name: "Alejandro Garnacho", team: "Man United", position: "W", confidence: "LOW", score: 76.8, minutes: 1600 },
        ];
    }
}

async function fetchWatchlist() {
    try {
        const resp = await fetch(`${API_BASE}/watchlist?limit=12`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        return data.players || [];
    } catch (err) {
        console.warn("Failed to fetch watchlist:", err);
        return [];
    }
}

async function fetchShortlist() {
    try {
        const resp = await fetch(`${API_BASE}/shortlist?limit=12`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        return data.players || [];
    } catch (err) {
        console.warn("Failed to fetch shortlist:", err);
        return [];
    }
}

function renderScouting() {
    const queue = reviewQueue.length > 0 ? reviewQueue : [];
    const sortedQueue = sortReviewQueue(queue, scoutSortMode);

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

    // Review queue
    let reviewHtml = sortBarHtml;
    if (sortedQueue.length > 0) {
        for (const p of sortedQueue) {
            const pKey = p.player_name || p.name || "";
            const status = scoutQueueStatuses[pKey] || "pending";
            const statusClass = "status-" + status;
            const icon = STATUS_ICONS[status] || "\u25CB";
            const conf = (p.confidence_level || p.confidence || "LOW").toUpperCase();
            reviewHtml += `
                <div class="rank-item">
                    <div>
                        <strong>${escapeHtml(pKey)}</strong>
                        <span class="rank-meta">${escapeHtml(p.team)} \u00B7 ${escapeHtml(p.position_group || p.position || "")} \u00B7 ${escapeHtml(p.minutes)}min \u00B7 ${escapeHtml(p.reason_code || "")}</span>
                    </div>
                    <div style="display:flex;gap:6px;align-items:center">
                        <span class="status-pill status-clickable ${statusClass}" data-queue-status="${escapeAttr(pKey)}" title="${escapeHtml(t("status_" + status))}" style="cursor:pointer">${icon} ${escapeHtml(t("status_" + status))}</span>
                        <span class="status-pill ${confidenceClass(conf)}">${escapeHtml(conf)}</span>
                    </div>
                </div>`;
        }
    } else {
        reviewHtml += '<div style="color:var(--text-muted);text-align:center;padding:1rem">No low-confidence players in queue</div>';
    }
    document.getElementById("review-list").innerHTML = reviewHtml;

    // Watchlist with diff badge
    computeWatchlistDiff(watchlistData);
    const wlBadge = watchlistDiffCount > 0 ? `<span class="scout-badge">${watchlistDiffCount} ${t("scout_new_badge")}</span>` : "";
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

    document.getElementById("watchlist").innerHTML = watchlistData.length > 0 ? watchlistData.map((player) => {
        const pName = player.player_name || player.name || "";
        const conf = (player.confidence_level || player.confidence || "LOW").toUpperCase();
        return `
        <div class="watch-card">
            <div>
                <strong>${escapeHtml(pName)}</strong>
                <span class="rank-meta">${escapeHtml(player.team)} \u00B7 ${escapeHtml(player.position_group || player.position || "")} \u00B7 ${escapeHtml(player.reason_code || "")}</span>
            </div>
            <span class="status-pill ${confidenceClass(conf)}">${Number(player.optimized_score || player.rating || 0).toFixed(1)}</span>
        </div>`;
    }).join("") : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No players in watchlist</div>';

    // Save watchlist snapshot after rendering
    saveWatchlistSnapshot(watchlistData);

    // Shortlist with notes
    document.getElementById("shortlist-count").textContent = String(shortlistData.length);
    document.getElementById("shortlist").innerHTML = shortlistData.length > 0 ? shortlistData.map((player) => {
        const pName = player.player_name || player.name || "";
        const conf = (player.confidence_level || player.confidence || "HIGH").toUpperCase();
        const note = scoutShortlistNotes[pName] || "";
        return `
        <div class="watch-card">
            <div>
                <strong>${escapeHtml(pName)}</strong>
                <span class="rank-meta">${escapeHtml(player.team)} \u00B7 ${escapeHtml(player.position_group || player.position || "")} \u00B7 ${escapeHtml(player.reason_code || "")}</span>
            </div>
            <span class="status-pill ${confidenceClass(conf)}">${Number(player.optimized_score || player.rating || 0).toFixed(1)}</span>
            <div class="watch-card-extra">
                ${note ? `<div class="scout-note-display">\u25B8 ${escapeHtml(note)}</div>` : ""}
                <input class="scout-note-input" type="text" data-note-player="${escapeAttr(pName)}" value="${escapeAttr(note)}" placeholder="${escapeAttr(t("scout_note_placeholder"))}" />
            </div>
        </div>`;
    }).join("") : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No players in shortlist</div>';
}

function sortReviewQueue(queue, mode) {
    const arr = [...queue];
    if (mode === "priority") {
        const confOrder = { "LOW": 0, "MEDIUM": 1, "HIGH": 2 };
        arr.sort((a, b) => {
            const sa = scoutQueueStatuses[a.player_name || a.name] || "pending";
            const sb = scoutQueueStatuses[b.player_name || b.name] || "pending";
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
        arr.sort((a, b) => (b.minutes || 0) - (a.minutes || 0));
    }
    return arr;
}

function renderOverview() {
    const health = artifactSummary.data_health || {};
    const healthItems = document.querySelectorAll("#data-health-list .health-item");
    if (healthItems.length >= 3) {
        const oofBadge = healthItems[0].querySelector(".status-pill");
        oofBadge.className = `status-pill ${health.oof_available ? "status-high" : "status-low"}`;
        oofBadge.textContent = health.oof_available ? "HIGH" : "LOW";

        const proxyBadge = healthItems[1].querySelector(".status-pill");
        proxyBadge.className = `status-pill ${health.player_match_coverage ? "status-medium" : "status-low"}`;
        proxyBadge.textContent = health.player_match_coverage ? "MED" : "LOW";
        healthItems[1].querySelector("span[data-i18n='health_proxy']").textContent = health.player_match_coverage || t("health_proxy");

        const truthBadge = healthItems[2].querySelector(".status-pill");
        truthBadge.className = `status-pill ${health.truth_labels_available ? "status-high" : "status-low"}`;
        truthBadge.textContent = health.truth_labels_available ? "HIGH" : "LOW";
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
}

function _fmtMetric(value, decimals) {
    if (value == null) return "–";
    return Number(value).toFixed(decimals != null ? decimals : 3);
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
    document.getElementById("report-value-title").textContent = valueMetrics.estimator || "value_fairness_oof";
    document.getElementById("report-value-status").textContent = valueImprovement ? `+${Math.round(valueImprovement).toLocaleString()} MAE` : "ready";
    document.getElementById("report-value-status").className = `status-pill ${valueSummaryMeta.sample_count > 0 ? "status-high" : "status-low"}`;

    const predictionReady = predictionMeta.status === "ok";
    const predictionLabel = predictionReady
        ? `${predictionMeta.model_type || "independent_poisson"} · ${predictionMeta.num_teams || 0} teams`
        : "no artifact";
    document.getElementById("report-prediction-title").textContent = "poisson_baseline";
    document.getElementById("report-prediction-status").textContent = predictionLabel;
    document.getElementById("report-prediction-status").className = `status-pill ${predictionReady ? "status-medium" : "status-low"}`;

    document.getElementById("model-runs-count").textContent = String(modelRuns.count || 0);
    const runList = document.getElementById("model-runs-list");
    const runs = (modelRuns.runs || []).slice(0, 12);
    runList.innerHTML = runs.length > 0
        ? runs.map((run) => {
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

            // Header status
            const statusText = spearman != null ? "READY" : "N/A";
            const statusClass = spearman != null ? "status-high" : "status-low";

            // Details row
            const detailParts = [
                `<span style="color:var(--text-muted)">hash</span> ${escapeHtml(hash)}`,
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

            // Reproduce command for copy button
            const copyBtn = cmd
                ? `<button class="text-button" data-copy-cmd="${escapeAttr(cmd)}" style="font-size:0.72rem;padding:0.15rem 0.4rem;margin-left:0.3rem" title="${z ? '复制命令' : 'Copy command'}">\u25C6 ${z ? '复制' : 'Copy'}</button>`
                : '';

            const fullDetailSections = [depHtml, detailSections].filter(Boolean)
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
}

function renderActions() {
    const chart = getChart("action-chart");
    const players = actionValueSummary.players || [];
    const actionList = document.getElementById("action-list");
    const actionStatus = document.getElementById("action-status-pill");

    if (actionStatus) {
        actionStatus.textContent = actionValueSummary.status === "ok"
            ? `REAL ${players.length}`
            : "NO DATA";
        actionStatus.className = `status-pill ${actionValueSummary.status === "ok" ? "status-medium" : "status-low"}`;
    }

    actionList.innerHTML = players.length > 0
        ? players.map((player) => `
            <div class="rank-item">
                <div>
                    <strong>${escapeHtml(player.player_name || "")}</strong>
                    <span class="rank-meta">xT/90 ${Number(player.xT_per_90 || 0).toFixed(3)} · composite ${Number(player.composite_score || 0).toFixed(1)}</span>
                </div>
                <span class="status-pill status-medium">${Number(player.finishing_delta || 0).toFixed(2)}</span>
            </div>
        `).join("")
        : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No action value artifact</div>';

    // StatsBomb Open Data attribution
    const attrEl = document.getElementById('action-attribution');
    if (attrEl) {
        attrEl.innerHTML = `\u25C6 ${appState.lang === 'zh' ? '\u6570\u636E\u6765\u6E90' : 'Data source'}: StatsBomb Open Data | github.com/statsbomb/open-data`;
    }

    if (!chart) return;
    const chartPlayers = players.filter((player) => player.player_name && player.xT_per_90 != null);
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
            data: chartPlayers.map((player) => player.player_name),
            axisLabel: { color: chartTextColor(), rotate: 30 },
        },
        yAxis: {
            type: "value",
            name: "xT/90",
            nameTextStyle: { color: chartTextColor() },
            axisLabel: { color: chartTextColor() },
            splitLine: { lineStyle: { color: chartGridColor() } },
        },
        series: [{
            type: "bar",
            data: chartPlayers.map((player) => Number(player.xT_per_90 || 0)),
            itemStyle: { color: "rgba(87,214,141,.78)" },
            label: { show: false },
        }],
    }, true);
    chart.resize();
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

    const updatedPill = document.getElementById("license-updated");
    if (updatedPill) {
        updatedPill.textContent = licenseData.updated_at
            ? escapeHtml(String(licenseData.updated_at))
            : (appState.lang === "zh" ? "无时间戳" : "No timestamp");
    }

    const updatedText = document.getElementById("license-last-updated");
    if (updatedText) {
        updatedText.textContent = licenseData.updated_at
            ? (appState.lang === "zh" ? "最后更新: " : "Last updated: ") + escapeHtml(String(licenseData.updated_at))
            : "";
    }
}

async function renderActiveView() {
    if (appState.view === "overview") renderOverview();
    if (appState.view === "players") renderPlayers();
    if (appState.view === "value") renderValue();
    if (appState.view === "matches") await renderMatches();
    if (appState.view === "scouting") renderScouting();
    if (appState.view === "actions") renderActions();
    if (appState.view === "reports") renderReports();
    if (appState.view === "tactical") renderTactical();
    if (appState.view === "wc_schedule") renderWcSchedule();
    if (appState.view === "wc_squads") renderWcSquads();
    if (appState.view === "wc_compare") renderWcCompare();
    if (appState.view === "wc_probability") renderWcProbability();
    if (appState.view === "license") renderLicense();
    // Resize charts after layout paint to ensure correct dimensions
    requestAnimationFrame(() => {
        Object.values(appState.charts).forEach((chart) => {
            try { chart.resize(); } catch(e) { /* ignore disposed charts */ }
        });
    });
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
        document.body.classList.toggle("light-mode");
        document.getElementById("theme-toggle").textContent = document.body.classList.contains("light-mode") ? "☀" : "☾";
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
        await fetchWcSquad(e.target.value);
        renderWcCompare();
    });
    document.getElementById("wc-compare-b").addEventListener("change", async (e) => {
        appState.wcCompareB = e.target.value;
        await fetchWcSquad(e.target.value);
        renderWcCompare();
    });

    // Tactical board event handlers
    const tacticalLoadHome = document.getElementById("tactical-load-home");
    if (tacticalLoadHome) {
        tacticalLoadHome.addEventListener("click", () => {
            const formation = document.getElementById("tactical-formation").value;
            if (typeof TacticalRenderer !== "undefined") {
                TacticalRenderer.loadFormation(formation, "home");
                tacticalProject = TacticalRenderer.getProject();
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
                const json = TACTICAL_BOARD.exportJSON(tacticalProject);
                const blob = new Blob([json], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `tactical-board-${tacticalProject.board_id}.json`;
                a.click();
                URL.revokeObjectURL(url);
            }
        });
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

    // Reports: expand/collapse run details
    document.addEventListener("click", (e) => {
        const toggleBtn = e.target.closest("[data-toggle-run]");
        if (toggleBtn) {
            const runId = toggleBtn.dataset.toggleRun;
            const detailsEl = document.querySelector(`[data-run-details="${runId}"]`);
            if (detailsEl) {
                const isHidden = detailsEl.style.display === "none";
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
            renderScouting();
        }
    });

    // Scouting: note input change
    document.addEventListener("change", (e) => {
        if (e.target.matches(".scout-note-input")) {
            const pName = e.target.dataset.notePlayer;
            if (pName != null) {
                scoutShortlistNotes[pName] = e.target.value;
                saveScoutShortlistNotes();
            }
        }
    });

    // Scouting: note input live update on keyup
    document.addEventListener("keyup", (e) => {
        if (e.target.matches(".scout-note-input")) {
            const pName = e.target.dataset.notePlayer;
            if (pName != null) {
                scoutShortlistNotes[pName] = e.target.value;
                saveScoutShortlistNotes();
            }
        }
    });

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
    predictions: null,  // from /world-cup/predictions
    apiOnline: false,
};

/* ── Demo squad data (fallback when WC API is offline) ──────────────── */
const WC_DEMO_SQUADS = {
    "Argentina": [
        {name:"Lionel Messi",position:"AM",club:"Inter Miami",league:"MLS"},
        {name:"Julian Alvarez",position:"ST",club:"Atletico Madrid",league:"La Liga"},
        {name:"Lautaro Martinez",position:"ST",club:"Inter Milan",league:"Serie A"},
        {name:"Rodrigo De Paul",position:"CM",club:"Atletico Madrid",league:"La Liga"},
        {name:"Enzo Fernandez",position:"CM",club:"Chelsea",league:"Premier League"},
        {name:"Alexis Mac Allister",position:"CM",club:"Liverpool",league:"Premier League"},
        {name:"Emiliano Martinez",position:"GK",club:"Aston Villa",league:"Premier League"},
        {name:"Cristian Romero",position:"CB",club:"Tottenham",league:"Premier League"},
        {name:"Nahuel Molina",position:"FB",club:"Atletico Madrid",league:"La Liga"},
        {name:"Leandro Paredes",position:"DM",club:"Roma",league:"Serie A"},
        {name:"Paulo Dybala",position:"AM",club:"Roma",league:"Serie A"},
    ],
    "Brazil": [
        {name:"Vinicius Junior",position:"W",club:"Real Madrid",league:"La Liga"},
        {name:"Rodrygo",position:"W",club:"Real Madrid",league:"La Liga"},
        {name:"Raphinha",position:"W",club:"Barcelona",league:"La Liga"},
        {name:"Bruno Guimaraes",position:"CM",club:"Newcastle",league:"Premier League"},
        {name:"Marquinhos",position:"CB",club:"PSG",league:"Ligue 1"},
        {name:"Alisson",position:"GK",club:"Liverpool",league:"Premier League"},
        {name:"Gabriel Magalhaes",position:"CB",club:"Arsenal",league:"Premier League"},
        {name:"Endrick",position:"ST",club:"Real Madrid",league:"La Liga"},
        {name:"Casemiro",position:"DM",club:"Manchester United",league:"Premier League"},
    ],
    "France": [
        {name:"Kylian Mbappe",position:"W",club:"Real Madrid",league:"La Liga"},
        {name:"Ousmane Dembele",position:"W",club:"PSG",league:"Ligue 1"},
        {name:"Antoine Griezmann",position:"AM",club:"Atletico Madrid",league:"La Liga"},
        {name:"Aurelien Tchouameni",position:"DM",club:"Real Madrid",league:"La Liga"},
        {name:"Eduardo Camavinga",position:"CM",club:"Real Madrid",league:"La Liga"},
        {name:"William Saliba",position:"CB",club:"Arsenal",league:"Premier League"},
        {name:"Theo Hernandez",position:"FB",club:"AC Milan",league:"Serie A"},
        {name:"Mike Maignan",position:"GK",club:"AC Milan",league:"Serie A"},
        {name:"Jules Kounde",position:"CB",club:"Barcelona",league:"La Liga"},
    ],
    "England": [
        {name:"Jude Bellingham",position:"AM",club:"Real Madrid",league:"La Liga"},
        {name:"Bukayo Saka",position:"W",club:"Arsenal",league:"Premier League"},
        {name:"Phil Foden",position:"W",club:"Man City",league:"Premier League"},
        {name:"Declan Rice",position:"DM",club:"Arsenal",league:"Premier League"},
        {name:"Cole Palmer",position:"AM",club:"Chelsea",league:"Premier League"},
        {name:"Harry Kane",position:"ST",club:"Bayern Munich",league:"Bundesliga"},
        {name:"Trent Alexander-Arnold",position:"FB",club:"Liverpool",league:"Premier League"},
        {name:"Marc Guehi",position:"CB",club:"Crystal Palace",league:"Premier League"},
        {name:"Jordan Pickford",position:"GK",club:"Everton",league:"Premier League"},
    ],
    "Germany": [
        {name:"Florian Wirtz",position:"AM",club:"Leverkusen",league:"Bundesliga"},
        {name:"Jamal Musiala",position:"AM",club:"Bayern Munich",league:"Bundesliga"},
        {name:"Leroy Sane",position:"W",club:"Bayern Munich",league:"Bundesliga"},
        {name:"Joshua Kimmich",position:"DM",club:"Bayern Munich",league:"Bundesliga"},
        {name:"Antonio Rudiger",position:"CB",club:"Real Madrid",league:"La Liga"},
        {name:"Kai Havertz",position:"ST",club:"Arsenal",league:"Premier League"},
        {name:"Toni Kroos",position:"CM",club:"Real Madrid",league:"La Liga"},
    ],
    "Spain": [
        {name:"Lamine Yamal",position:"W",club:"Barcelona",league:"La Liga"},
        {name:"Pedri",position:"CM",club:"Barcelona",league:"La Liga"},
        {name:"Rodri",position:"DM",club:"Man City",league:"Premier League"},
        {name:"Gavi",position:"CM",club:"Barcelona",league:"La Liga"},
        {name:"Nico Williams",position:"W",club:"Athletic Bilbao",league:"La Liga"},
        {name:"Dani Olmo",position:"AM",club:"Barcelona",league:"La Liga"},
        {name:"Alvaro Morata",position:"ST",club:"AC Milan",league:"Serie A"},
    ],
    "Portugal": [
        {name:"Cristiano Ronaldo",position:"ST",club:"Al Nassr",league:"Saudi Pro League"},
        {name:"Bruno Fernandes",position:"AM",club:"Manchester United",league:"Premier League"},
        {name:"Bernardo Silva",position:"W",club:"Man City",league:"Premier League"},
        {name:"Rafael Leao",position:"W",club:"AC Milan",league:"Serie A"},
        {name:"Ruben Dias",position:"CB",club:"Man City",league:"Premier League"},
        {name:"Diogo Jota",position:"W",club:"Liverpool",league:"Premier League"},
        {name:"Vitinha",position:"CM",club:"PSG",league:"Ligue 1"},
    ],
    "Netherlands": [
        {name:"Xavi Simons",position:"AM",club:"RB Leipzig",league:"Bundesliga"},
        {name:"Virgil van Dijk",position:"CB",club:"Liverpool",league:"Premier League"},
        {name:"Frenkie de Jong",position:"CM",club:"Barcelona",league:"La Liga"},
        {name:"Cody Gakpo",position:"W",club:"Liverpool",league:"Premier League"},
        {name:"Matthijs de Ligt",position:"CB",club:"Bayern Munich",league:"Bundesliga"},
        {name:"Denzel Dumfries",position:"FB",club:"Inter Milan",league:"Serie A"},
    ],
    "Belgium": [
        {name:"Kevin De Bruyne",position:"AM",club:"Man City",league:"Premier League"},
        {name:"Romelu Lukaku",position:"ST",club:"Napoli",league:"Serie A"},
        {name:"Jeremy Doku",position:"W",club:"Man City",league:"Premier League"},
        {name:"Amadou Onana",position:"DM",club:"Aston Villa",league:"Premier League"},
    ],
    "Croatia": [
        {name:"Luka Modric",position:"CM",club:"Real Madrid",league:"La Liga"},
        {name:"Josko Gvardiol",position:"CB",club:"Man City",league:"Premier League"},
        {name:"Marcelo Brozovic",position:"DM",club:"Al Nassr",league:"Saudi Pro League"},
    ],
};

async function fetchWcGroups() {
    try {
        const resp = await fetch(`${API_BASE}/world-cup/groups`, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) throw new Error("API error");
        const data = await resp.json();
        wcApiData.groups = data;
        wcApiData.apiOnline = true;
        return data;
    } catch {
        wcApiData.apiOnline = false;
        return null;
    }
}

async function fetchWcSchedule(group, matchday) {
    try {
        let url = `${API_BASE}/world-cup/schedule`;
        const params = [];
        if (group) params.push(`group=${encodeURIComponent(group)}`);
        if (matchday) params.push(`matchday=${matchday}`);
        if (params.length) url += "?" + params.join("&");
        const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) throw new Error("API error");
        const data = await resp.json();
        wcApiData.schedule = data;
        return data;
    } catch {
        return null;
    }
}

async function fetchWcSquad(team) {
    if (wcApiData.squadCache[team]) return wcApiData.squadCache[team];
    try {
        const resp = await fetch(`${API_BASE}/world-cup/squads/${encodeURIComponent(team)}`, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) throw new Error("API error");
        const data = await resp.json();
        wcApiData.squadCache[team] = data;
        return data;
    } catch {
        return null;
    }
}

async function fetchWcPredictions() {
    try {
        const resp = await fetch(`${API_BASE}/world-cup/predictions`, { signal: AbortSignal.timeout(5000) });
        if (!resp.ok) throw new Error("API error");
        const data = await resp.json();
        wcApiData.predictions = data;
        return data;
    } catch {
        return null;
    }
}

function wcAllTeams() {
    return Object.values(WC_GROUPS).flat();
}

function wcTeamGroup(team) {
    for (const [letter, teams] of Object.entries(WC_GROUPS)) {
        if (teams.includes(team)) return letter;
    }
    return "?";
}

// Get enriched squad data (from API cache, or fallback to empty)
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
    // Fallback to demo data when API is offline
    const demo = WC_DEMO_SQUADS[team];
    if (demo) {
        return demo.map((p) => ({...p, hasRating: false, rating: 0, confidence: "NONE"}));
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
        // Fallback: generate locally (same logic as before)
        const groupStartOffsets = {A:0,B:0,C:0,D:0,E:1,F:1,G:1,H:1,I:2,J:2,K:2,L:2};
        const mdGaps = [0, 4, 8];
        const groupVenues = {
            A:["Estadio Azteca","Mexico City"],B:["BMO Field","Toronto"],
            C:["SoFi Stadium","Los Angeles"],D:["AT&T Stadium","Arlington"],
            E:["MetLife Stadium","New York"],F:["Lumen Field","Seattle"],
            G:["Mercedes-Benz Stadium","Atlanta"],H:["Hard Rock Stadium","Miami"],
            I:["Gillette Stadium","Boston"],J:["NRG Stadium","Houston"],
            K:["Levi's Stadium","San Francisco"],L:["Lincoln Financial Field","Philadelphia"],
        };
        for (const [letter, teams] of Object.entries(WC_GROUPS)) {
            const offset = groupStartOffsets[letter];
            const [venue, city] = groupVenues[letter];
            const [t1, t2, t3, t4] = teams;
            for (let md = 0; md < 3; md++) {
                const day = 11 + offset + mdGaps[md];
                const dateStr = `2026-06-${String(day).padStart(2, "0")}`;
                const pairings = md === 0 ? [[t1,t2],[t3,t4]] : md === 1 ? [[t1,t3],[t2,t4]] : [[t1,t4],[t2,t3]];
                pairings.forEach(([home, away], gi) => {
                    matches.push({date: dateStr, time_et: gi === 0 ? "19:30" : "22:00", group: letter, home, away, venue, city, matchday: md + 1});
                });
            }
        }
    }

    const filtered = matches.filter((m) => {
        if (groupFilter !== "ALL" && m.group !== groupFilter) return false;
        if (mdFilter !== "ALL" && String(m.matchday) !== mdFilter) return false;
        return true;
    });

    const tbody = document.getElementById("wc-schedule-table");
    tbody.innerHTML = filtered.map((m) => `<tr>
        <td>${escapeHtml(m.date)}</td><td>${escapeHtml(m.time_et || m.time)} ET</td><td>${escapeHtml(m.group)}</td>
        <td>${escapeHtml(m.home)}</td><td>${escapeHtml(m.away)}</td><td>${escapeHtml(m.venue)}, ${escapeHtml(m.city)}</td>
    </tr>`).join("");
}

function renderWcSquads() {
    const team = appState.wcSquadTeam;
    const rawSquad = wcGetSquad(team);
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

    const tbody = document.getElementById("wc-squad-table");
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
        // Fallback: compute locally
        const teams = wcAllTeams();
        const strengths = {};
        teams.forEach((t) => { strengths[t] = wcTeamStrength(t); });

        const container = document.getElementById("wc-prob-groups");
        container.innerHTML = Object.entries(WC_GROUPS).map(([letter, groupTeams]) => {
            const teamStrs = groupTeams.map((t) => ({team: t, strength: strengths[t]}));
            const total = teamStrs.reduce((s, x) => s + x.strength, 0);
            const rows = teamStrs.sort((a, b) => b.strength - a.strength).map((x) => {
                const p1 = x.strength / total;
                const pct = Math.round(p1 * 100);
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

    // Fetch API data in background, then re-render
    const [groupsData, scheduleData, predictionsData] = await Promise.all([
        fetchWcGroups(),
        fetchWcSchedule(),
        fetchWcPredictions(),
    ]);

    // Pre-fetch squads for the initially selected teams
    await Promise.all([
        fetchWcSquad("Argentina"),
        fetchWcSquad("France"),
    ]);

    // Re-render all WC views with API data
    renderWcSchedule();
    renderWcSquads();
    renderWcCompare();
    renderWcProbability();
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

function renderTactical() {
    if (!tacticalProject) {
        tacticalProject = TACTICAL_BOARD.createProject("ScoutFootball 战术板");
        // Load default formation
        tacticalProject.objects = TACTICAL_BOARD.generateFormation("4-3-3", "home");
    }

    if (typeof TacticalRenderer !== "undefined") {
        TacticalRenderer.init("tactical-canvas", tacticalProject);
        TacticalRenderer.onChange = tacticalAutoSave;
    }

    // Sync pitch type selector with current project
    const pitchTypeEl = document.getElementById("tactical-pitch-type");
    if (pitchTypeEl && tacticalProject.pitch_type) {
        pitchTypeEl.value = tacticalProject.pitch_type;
    }

    // Update project list
    renderTacticalProjectList();
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
    applyLocale();
    renderMatchSelectors();
    initWorldCup();
    bindEvents();
    setView("overview");

    // Load scouting localStorage state
    loadScoutQueueStatuses();
    loadScoutShortlistNotes();

    // Load real data from API in parallel
    const [ratingsData, meta, artifacts, teams, valueData, reviewData, predictionArtifact, runs, watchlistRows, shortlistRows, actionValues, licenseResp] = await Promise.all([
        fetchRatings(),
        fetchRatingsMeta(),
        fetchArtifacts(),
        fetchTeams(),
        fetchValueReport(),
        fetchReviewQueue(),
        fetchPredictionMeta(),
        fetchModelRuns(),
        fetchWatchlist(),
        fetchShortlist(),
        fetchActionValues(),
        fetchLicense(),
    ]);

    players = ratingsData;
    ratingsMeta = meta;
    artifactSummary = artifacts;
    valuePlayers = valueData;
    reviewQueue = reviewData;
    predictionMeta = predictionArtifact;
    modelRuns = runs;
    watchlistData = watchlistRows;
    shortlistData = shortlistRows;
    actionValueSummary = actionValues;
    licenseData = licenseResp;
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
        topOofPill.textContent = valueSummaryMeta.sample_count ? `OOF ${valueSummaryMeta.sample_count}` : "OOF none";
        topOofPill.className = `status-pill ${valueSummaryMeta.sample_count ? "status-high" : "status-low"}`;
    }

    renderActiveView();

    // Check API connection status
    const apiPill = document.getElementById("top-api-pill");
    if (apiPill) {
        try {
            const healthResp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
            if (healthResp.ok) {
                apiPill.textContent = "API OK";
                apiPill.className = "status-pill status-high";
            } else {
                apiPill.textContent = "API ERR";
                apiPill.className = "status-pill status-low";
            }
        } catch {
            apiPill.textContent = "OFFLINE";
            apiPill.className = "status-pill status-low";
        }
    }
});

const SCOUT_QUEUE_KEY = "scout-queue-statuses";
const SCOUT_NOTES_KEY = "scout-shortlist-notes";
const SCOUT_LASTVISIT_KEY = "scout-watchlist-lastvisit";
const SCOUT_SNAPSHOT_KEY = "scout-watchlist-snapshot";
const PLAYER_WATCHLIST_KEY = "sf-player-watchlist";
const PLAYER_SHORTLIST_KEY = "sf-player-shortlist";
const STATUS_CYCLE = ["pending", "reviewing", "approved", "rejected"];
const STATUS_ICONS = { pending: "\u25CB", reviewing: "\u25B2", approved: "\u2713", rejected: "\u2717" };

let scoutQueueStatuses = {};
let scoutShortlistNotes = {};
let scoutSortMode = "priority";
let watchlistDiffCount = 0;

/* ── Player Watchlist / Shortlist (localStorage) ─────────────────── */
function getPlayerWatchlist() {
    try { return JSON.parse(localStorage.getItem(PLAYER_WATCHLIST_KEY)) || []; } catch { return []; }
}
function savePlayerWatchlist(list) {
    try { localStorage.setItem(PLAYER_WATCHLIST_KEY, JSON.stringify(list)); } catch {}
}
function getPlayerShortlist() {
    try { return JSON.parse(localStorage.getItem(PLAYER_SHORTLIST_KEY)) || []; } catch { return []; }
}
function savePlayerShortlist(list) {
    try { localStorage.setItem(PLAYER_SHORTLIST_KEY, JSON.stringify(list)); } catch {}
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

function loadScoutQueueStatuses() {
    try { scoutQueueStatuses = JSON.parse(localStorage.getItem(SCOUT_QUEUE_KEY)) || {}; } catch { scoutQueueStatuses = {}; }
}

function saveScoutQueueStatuses() {
    try { localStorage.setItem(SCOUT_QUEUE_KEY, JSON.stringify(scoutQueueStatuses)); } catch {}
}

function loadScoutShortlistNotes() {
    try { scoutShortlistNotes = JSON.parse(localStorage.getItem(SCOUT_NOTES_KEY)) || {}; } catch { scoutShortlistNotes = {}; }
}

function saveScoutShortlistNotes() {
    try { localStorage.setItem(SCOUT_NOTES_KEY, JSON.stringify(scoutShortlistNotes)); } catch {}
}

function cycleQueueStatus(playerKey) {
    const current = scoutQueueStatuses[playerKey] || "pending";
    const idx = STATUS_CYCLE.indexOf(current);
    scoutQueueStatuses[playerKey] = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
    saveScoutQueueStatuses();
}

function computeWatchlistDiff(currentPlayers) {
    try {
        const lastVisit = parseInt(localStorage.getItem(SCOUT_LASTVISIT_KEY)) || 0;
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
    } catch {}
}
