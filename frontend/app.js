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
    },
};

const API_BASE = window.__SCOUTFOOTBALL_API__ || "";

let players = [];
let reviews = [];
let matches = [];

async function fetchRatings(position, league) {
    const params = new URLSearchParams();
    if (position && position !== "ALL") params.set("position", position);
    if (league) params.set("league", league);
    params.set("limit", "20000");
    try {
        const resp = await fetch(`${API_BASE}/ratings?${params}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        return (data.players || []).map((p) => ({
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
            percentile: 50,
            value: 0,
            residual: 0,
            radar: [50, 50, 50, 50, 50],
        }));
    } catch (err) {
        console.warn("Failed to fetch ratings:", err);
        return [];
    }
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
        console.warn("Failed to fetch artifacts:", err);
        return { player_match_rows: 0, team_match_rows: 0, rating_rows: 0, event_samples: 0, data_health: {} };
    }
}

async function fetchTeams() {
    try {
        const resp = await fetch(`${API_BASE}/teams`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        return data.teams || [];
    } catch (err) {
        console.warn("Failed to fetch teams:", err);
        return [];
    }
}

async function fetchPrediction(homeTeam, awayTeam) {
    try {
        const resp = await fetch(`${API_BASE}/prediction/${encodeURIComponent(homeTeam)}/${encodeURIComponent(awayTeam)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.warn("Failed to fetch prediction:", err);
        return null;
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
    valueMode: "under",
    home: "Arsenal",
    away: "Barcelona",
    charts: {},
};

function t(key) {
    return i18n[appState.lang][key] || key;
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
        const matchesQuery = !query || [player.name, player.team, player.position].join(" ").toLowerCase().includes(query);
        return matchesPosition && matchesSeason && matchesQuery;
    });
}

function renderPlayers() {
    const rows = filteredPlayers().sort((a, b) => b.rating - a.rating);
    const tbody = document.getElementById("player-table");
    if (players.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">Loading...</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map((player, index) => {
        const lowAppBadge = player.low_appearance
            ? `<span class="status-pill low-appearance" title="${appState.lang === 'zh' ? '出场不足20场，评分已扣减' : 'Under 20 matches, score penalized'}">${appState.lang === 'zh' ? '低出场' : 'LOW APP'}</span>`
            : '';
        return `
        <tr class="${player.key === appState.selectedPlayerKey ? "selected" : ""}${player.low_appearance ? " low-appearance-row" : ""}" data-player="${player.key}" style="cursor:pointer">
            <td>${index + 1}</td>
            <td>${player.name}${lowAppBadge}</td>
            <td>${player.position}</td>
            <td>${player.team}</td>
            <td>${player.season}</td>
            <td>${player.rating.toFixed(1)}</td>
            <td><span class="status-pill ${confidenceClass(player.confidence)}">${player.confidence}</span></td>
        </tr>`;
    }).join("");

    tbody.querySelectorAll("tr[data-player]").forEach((row) => {
        row.addEventListener("click", () => {
            appState.selectedPlayerKey = row.dataset.player;
            renderPlayers();
            renderPlayerProfile();
        });
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
    const badge = document.getElementById("player-confidence");
    badge.textContent = player.confidence;
    badge.className = `status-pill ${confidenceClass(player.confidence)}`;

    // Fetch real profile data for radar
    let profile = null;
    try {
        const resp = await fetch(`${API_BASE}/player/${encodeURIComponent(player.name)}/profile?season=${player.season}`);
        if (resp.ok) profile = await resp.json();
    } catch (err) { /* fallback to list data */ }

    const detailMinutes = profile ? profile.minutes : player.minutes;
    const detailScore = profile ? profile.optimized_score : player.rating;
    const detailPosition = profile ? profile.position_group : player.position;
    const detailMatches = profile ? profile.matches : player.matches;
    const detailLowApp = profile ? profile.low_appearance : player.low_appearance;
    const lowAppWarning = detailLowApp
        ? `<div class="low-appearance-warning">${appState.lang === "zh" ? "⚠ 出场不足20场，评分已扣减最多30%" : "⚠ Under 20 matches, score penalized up to 30%"}</div>`
        : "";
    document.getElementById("player-detail").innerHTML = `
        <div><span>${t("th_team")}</span><strong>${player.team}</strong></div>
        <div><span>${t("minutes")}</span><strong>${detailMinutes}</strong></div>
        <div><span>${appState.lang === "zh" ? "出场" : "Matches"}</span><strong>${detailMatches}</strong></div>
        <div><span>${t("th_pos")}</span><strong>${detailPosition}</strong></div>
        <div><span>${t("th_rating")}</span><strong>${detailScore}</strong></div>
        ${lowAppWarning}
    `;

    // Use real radar data from profile API, or fallback to defaults
    const radar = (profile && profile.radar) ? profile.radar : player.radar;
    renderRadar({ ...player, radar });
}

function getChart(id) {
    if (!window.echarts) {
        const element = document.getElementById(id);
        if (element && !element.textContent) element.textContent = "Chart runtime unavailable.";
        return null;
    }
    const element = document.getElementById(id);
    if (!element) return null;
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
    const data = valuePlayers.length > 0 ? valuePlayers : MOCK_VALUE_DATA;
    const sorted = [...data].sort((a, b) => (
        appState.valueMode === "under" ? b.residual - a.residual : a.residual - b.residual
    ));
    document.getElementById("value-list").innerHTML = sorted.slice(0, 50).map((player) => {
        const valM = (player.actualValue / 1e6).toFixed(1);
        return `
        <div class="rank-item">
            <div>
                <strong>${player.name}</strong>
                <span class="rank-meta">${player.team} · €${valM}M</span>
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
    const scatterData = data.map((player) => ({
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
                return `<strong>${d.name}</strong><br/>${d.team}<br/>${isZh ? "实际" : "Actual"}: €${d.value[0]}M<br/>${isZh ? "预测" : "Predicted"}: €${d.value[1]}M<br/>${isZh ? "残差" : "Residual"}: ${d.residual > 0 ? "+" : ""}${d.residual.toFixed(2)}`;
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
    home.innerHTML = teams.map((team) => `<option value="${team}">${team}</option>`).join("");
    away.innerHTML = teams.map((team) => `<option value="${team}">${team}</option>`).join("");
    home.value = appState.home;
    away.value = appState.away;
}

async function renderMatches() {
    // Fetch prediction from API
    currentPrediction = await fetchPrediction(appState.home, appState.away);
    const match = selectedMatch();
    document.getElementById("match-title").textContent = `${match.home} vs ${match.away}`;
    const probabilityRows = [
        [t("home"), match.hw],
        [t("draw"), match.draw],
        [t("away"), match.aw],
    ];
    document.getElementById("match-probabilities").innerHTML = probabilityRows.map(([label, value]) => `
        <div class="probability-row">
            <span class="probability-label">${label}</span>
            <div class="probability-track"><div class="probability-fill" style="width:${Math.round(value * 100)}%"></div></div>
            <strong>${Math.round(value * 100)}%</strong>
        </div>
    `).join("");
    document.getElementById("match-detail").innerHTML = `
        <div><span>${t("expected_goals")}</span><strong>${match.xh.toFixed(2)} / ${match.xa.toFixed(2)}</strong></div>
        <div><span>${t("coverage")}</span><strong>0.92</strong></div>
        <div><span>model</span><strong>Poisson</strong></div>
        <div><span>calibration</span><strong>pending</strong></div>
    `;
    renderScoreMatrix(match);
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
        console.warn("Failed to fetch review queue:", err);
        return [];
    }
}

function renderScouting() {
    const queue = reviewQueue.length > 0 ? reviewQueue : [];
    document.getElementById("review-list").innerHTML = queue.length > 0
        ? queue.map((p) => `
            <div class="rank-item">
                <div>
                    <strong>${p.name}</strong>
                    <span class="rank-meta">${p.team} · ${p.position} · ${p.minutes}min</span>
                </div>
                <span class="status-pill ${confidenceClass(p.confidence)}">${p.confidence}</span>
            </div>
        `).join("")
        : '<div style="color:var(--text-muted);text-align:center;padding:1rem">No low-confidence players in queue</div>';
    document.getElementById("watchlist").innerHTML = players.slice(0, 4).map((player) => `
        <div class="watch-card">
            <div>
                <strong>${player.name}</strong>
                <span class="rank-meta">${player.team} · ${player.position}</span>
            </div>
            <span class="status-pill ${confidenceClass(player.confidence)}">${player.rating.toFixed(1)}</span>
        </div>
    `).join("");
}

function renderActions() {
    const chart = getChart("action-chart");
    if (!chart) return;
    const zones = [];
    for (let x = 0; x < 8; x += 1) {
        for (let y = 0; y < 5; y += 1) {
            const centerBias = Math.max(0, 1 - Math.abs(y - 2) * 0.23);
            const finalThird = x > 4 ? 0.55 : 0.2;
            zones.push([x, y, +(centerBias * (0.3 + finalThird + x * 0.055)).toFixed(2)]);
        }
    }
    chart.setOption({
        title: {
            text: appState.lang === "zh" ? "样例数据 · 非真实 xT/VAEP 产物" : "Sample data · Not real xT/VAEP output",
            left: "center", top: 0,
            textStyle: { color: "rgba(255,180,60,.85)", fontSize: 12, fontWeight: 400 },
        },
        grid: { left: 36, right: 20, top: 30, bottom: 28 },
        xAxis: { type: "category", data: ["1", "2", "3", "4", "5", "6", "7", "8"], axisLabel: { color: chartTextColor() } },
        yAxis: { type: "category", data: ["L", "HL", "C", "HR", "R"], axisLabel: { color: chartTextColor() } },
        visualMap: {
            min: 0,
            max: 1.3,
            show: false,
            inRange: { color: ["rgba(255,255,255,.04)", "rgba(87,214,141,.78)"] },
        },
        series: [{ type: "heatmap", data: zones, label: { show: false } }],
    });
    chart.resize();
}

async function renderActiveView() {
    if (appState.view === "players") renderPlayers();
    if (appState.view === "value") renderValue();
    if (appState.view === "matches") await renderMatches();
    if (appState.view === "scouting") renderScouting();
    if (appState.view === "actions") renderActions();
    Object.values(appState.charts).forEach((chart) => chart.resize());
}

function exportPlayers() {
    const header = ["rank", "player", "position", "team", "rating", "confidence"];
    const rows = filteredPlayers().map((player, index) => [
        index + 1,
        player.name,
        player.position,
        player.team,
        player.rating,
        player.confidence,
    ]);
    const csv = [header, ...rows].map((row) => row.join(",")).join("\n");
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
        renderPlayers();
    });
    document.getElementById("global-search").addEventListener("input", () => {
        if (appState.view !== "players") setView("players");
        else renderPlayers();
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
            appState.away = getTeams().find((team) => team !== appState.home) || appState.away;
            document.getElementById("away-team").value = appState.away;
        }
        renderMatches();
    });
    document.getElementById("away-team").addEventListener("change", (event) => {
        appState.away = event.target.value;
        if (appState.home === appState.away) {
            appState.home = getTeams().find((team) => team !== appState.away) || appState.home;
            document.getElementById("home-team").value = appState.home;
        }
        renderMatches();
    });
    document.getElementById("export-players").addEventListener("click", exportPlayers);
    window.addEventListener("resize", () => {
        Object.values(appState.charts).forEach((chart) => chart.resize());
    });
}

document.addEventListener("DOMContentLoaded", async () => {
    applyLocale();
    renderMatchSelectors();
    bindEvents();
    setView("overview");

    // Load real data from API in parallel
    const [ratingsData, meta, artifacts, teams, valueData, reviewData] = await Promise.all([
        fetchRatings(),
        fetchRatingsMeta(),
        fetchArtifacts(),
        fetchTeams(),
        fetchValueReport(),
        fetchReviewQueue(),
    ]);

    players = ratingsData;
    valuePlayers = valueData;
    reviewQueue = reviewData;
    if (players.length > 0) {
        appState.selectedPlayerKey = players[0].key;
    }

    // Populate season filter dropdown
    const seasons = [...new Set(players.map((p) => p.season).filter(Boolean))].sort();
    const seasonSelect = document.getElementById("season-filter");
    seasonSelect.innerHTML = '<option value="ALL">ALL</option>' + seasons.map((s) => `<option value="${s}">${s}</option>`).join("");
    seasonSelect.value = appState.season;

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
        healthItems[1].querySelector(".status-pill").className = "status-pill status-low";
        healthItems[2].querySelector(".status-pill").className = `status-pill ${health.truth_labels_available ? "status-high" : "status-low"}`;
        healthItems[2].querySelector(".status-pill").textContent = health.truth_labels_available ? "HIGH" : "LOW";
    }

    renderActiveView();
});
