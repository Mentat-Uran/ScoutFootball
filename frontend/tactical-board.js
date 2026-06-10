/* Tactical Board Module — P1.5 First Slice

   Canvas-based tactical board with:
   - Normalized pitch coordinates (0-100)
   - Basic objects: players, ball, arrows
   - Formation presets
   - Drag & drop
   - Local JSON project schema
   - Undo/redo
*/

const TACTICAL_BOARD = {
    /* ── Schema version ────────────────────────────────────────────── */
    SCHEMA_VERSION: "1.0.0",
    MAX_OBJECTS: 200,
    MAX_FRAMES: 60,
    MAX_TEXT_LENGTH: 120,
    MAX_IMPORT_BYTES: 1_000_000,

    /* ── Pitch config ──────────────────────────────────────────────── */
    PITCH: {
        width: 105,   // meters (FIFA standard)
        height: 68,
        padding: 5,   // canvas padding in normalized units
    },

    /* ── Formation presets ─────────────────────────────────────────── */
    FORMATIONS: {
        "4-3-3": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            CM: [{ x: 40, y: 25 }, { x: 40, y: 50 }, { x: 40, y: 75 }],
            W:  [{ x: 70, y: 15 }, { x: 70, y: 85 }],
            ST: [{ x: 80, y: 50 }],
        },
        "4-2-3-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            DM: [{ x: 35, y: 35 }, { x: 35, y: 65 }],
            AM: [{ x: 55, y: 25 }, { x: 55, y: 50 }, { x: 55, y: 75 }],
            ST: [{ x: 75, y: 50 }],
        },
        "3-5-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 25 }, { x: 20, y: 50 }, { x: 20, y: 75 }],
            FB: [{ x: 35, y: 10 }, { x: 35, y: 90 }],
            CM: [{ x: 45, y: 30 }, { x: 45, y: 50 }, { x: 45, y: 70 }],
            ST: [{ x: 75, y: 35 }, { x: 75, y: 65 }],
        },
        "4-4-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            CM: [{ x: 40, y: 25 }, { x: 40, y: 75 }],
            W:  [{ x: 40, y: 10 }, { x: 40, y: 90 }],
            ST: [{ x: 75, y: 35 }, { x: 75, y: 65 }],
        },
        "5-3-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 18, y: 25 }, { x: 18, y: 50 }, { x: 18, y: 75 }],
            FB: [{ x: 30, y: 10 }, { x: 30, y: 90 }],
            CM: [{ x: 45, y: 25 }, { x: 45, y: 50 }, { x: 45, y: 75 }],
            ST: [{ x: 75, y: 35 }, { x: 75, y: 65 }],
        },
        "3-4-3": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 25 }, { x: 20, y: 50 }, { x: 20, y: 75 }],
            CM: [{ x: 45, y: 15 }, { x: 45, y: 50 }, { x: 45, y: 85 }],
            W:  [{ x: 70, y: 15 }, { x: 70, y: 85 }],
            ST: [{ x: 80, y: 50 }],
        },
        "3-4-2-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 25 }, { x: 20, y: 50 }, { x: 20, y: 75 }],
            FB: [{ x: 35, y: 10 }, { x: 35, y: 90 }],
            CM: [{ x: 45, y: 35 }, { x: 45, y: 65 }],
            AM: [{ x: 60, y: 35 }, { x: 60, y: 65 }],
            ST: [{ x: 80, y: 50 }],
        },
        "4-1-4-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            DM: [{ x: 35, y: 50 }],
            CM: [{ x: 50, y: 25 }, { x: 50, y: 75 }],
            W:  [{ x: 65, y: 15 }, { x: 65, y: 85 }],
            ST: [{ x: 80, y: 50 }],
        },
        "4-3-1-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            CM: [{ x: 40, y: 25 }, { x: 40, y: 50 }, { x: 40, y: 75 }],
            AM: [{ x: 60, y: 50 }],
            ST: [{ x: 80, y: 35 }, { x: 80, y: 65 }],
        },
        "4-2-2-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            DM: [{ x: 35, y: 35 }, { x: 35, y: 65 }],
            AM: [{ x: 55, y: 25 }, { x: 55, y: 75 }],
            ST: [{ x: 80, y: 35 }, { x: 80, y: 65 }],
        },
        "4-5-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            CM: [{ x: 40, y: 15 }, { x: 40, y: 35 }, { x: 40, y: 50 }, { x: 40, y: 65 }, { x: 40, y: 85 }],
            ST: [{ x: 80, y: 50 }],
        },
        "5-4-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 18, y: 25 }, { x: 18, y: 50 }, { x: 18, y: 75 }],
            FB: [{ x: 30, y: 10 }, { x: 30, y: 90 }],
            CM: [{ x: 45, y: 25 }, { x: 45, y: 50 }, { x: 45, y: 75 }],
            ST: [{ x: 80, y: 50 }],
        },
    },

    /* ── Training presets ──────────────────────────────────────────── */
    TRAINING_PRESETS: {
        "rondo": {
            label: "Rondo 4v2",
            area: { x: 40, y: 40, w: 20, h: 20 },
            attackers: [
                { x: 40, y: 40 }, { x: 60, y: 40 },
                { x: 40, y: 60 }, { x: 60, y: 60 },
            ],
            defenders: [
                { x: 48, y: 48 }, { x: 52, y: 52 },
            ],
            arrows: [
                { x1: 42, y1: 42, x2: 58, y2: 42, style: "pass" },
                { x1: 58, y1: 42, x2: 58, y2: 58, style: "pass" },
                { x1: 58, y1: 58, x2: 42, y2: 58, style: "pass" },
                { x1: 42, y1: 58, x2: 42, y2: 42, style: "pass" },
            ],
        },
        "pressing-drill": {
            label: "Pressing Drill",
            attackers: [
                { x: 70, y: 25 }, { x: 70, y: 50 }, { x: 70, y: 75 },
            ],
            midfielders: [
                { x: 50, y: 20 }, { x: 50, y: 40 }, { x: 50, y: 60 }, { x: 50, y: 80 },
            ],
            defenders: [
                { x: 30, y: 25 }, { x: 30, y: 50 }, { x: 30, y: 75 },
            ],
            arrows: [
                { x1: 70, y1: 50, x2: 55, y2: 50, style: "run" },
                { x1: 50, y1: 40, x2: 55, y2: 45, style: "run" },
                { x1: 50, y1: 60, x2: 55, y2: 55, style: "run" },
            ],
        },
        "counter-attack": {
            label: "Counter Attack",
            defenders: [
                { x: 15, y: 25 }, { x: 15, y: 50 }, { x: 15, y: 75 },
                { x: 25, y: 15 }, { x: 25, y: 85 },
            ],
            midfielders: [
                { x: 35, y: 35 }, { x: 35, y: 65 },
            ],
            attackers: [
                { x: 55, y: 30 }, { x: 55, y: 70 },
                { x: 70, y: 50 },
            ],
            arrows: [
                { x1: 35, y1: 50, x2: 55, y2: 50, style: "pass" },
                { x1: 55, y1: 50, x2: 75, y2: 50, style: "run" },
                { x1: 55, y1: 30, x2: 75, y2: 40, style: "run" },
                { x1: 55, y1: 70, x2: 75, y2: 60, style: "run" },
            ],
        },
        "possession": {
            label: "Possession Grid",
            area: { x: 30, y: 25, w: 40, h: 50 },
            teamA: [
                { x: 35, y: 30 }, { x: 45, y: 35 }, { x: 55, y: 30 },
                { x: 35, y: 50 }, { x: 55, y: 50 },
                { x: 45, y: 60 },
            ],
            teamB: [
                { x: 40, y: 40 }, { x: 50, y: 45 },
            ],
            circles: [
                { x: 45, y: 45, r: 5 },
            ],
        },
    },

    generateTraining(type, team = "home") {
        const preset = this.TRAINING_PRESETS[type];
        if (!preset) return [];

        const objects = [];

        // Area zone
        if (preset.area) {
            objects.push(this.createZone(
                preset.area.x, preset.area.y, preset.area.w, preset.area.h,
                preset.label || type
            ));
        }

        // Players
        const playerGroups = ["attackers", "defenders", "midfielders", "teamA", "teamB"];
        const oppTeam = team === "home" ? "away" : "home";
        let num = 1;
        for (const group of playerGroups) {
            const players = preset[group];
            if (!players) continue;
            const isTeamA = (group === "attackers" || group === "midfielders" || group === "teamA");
            const t = isTeamA ? team : oppTeam;
            for (const pos of players) {
                objects.push(this.createPlayer(pos.x, pos.y, t, "", num++));
            }
        }

        // Arrows
        if (preset.arrows) {
            for (const a of preset.arrows) {
                objects.push(this.createArrow(a.x1, a.y1, a.x2, a.y2, a.style || "solid"));
            }
        }

        // Circles (e.g. possession grid)
        if (preset.circles) {
            for (const c of preset.circles) {
                objects.push(this.createEllipse(
                    c.x, c.y, c.r, c.r,
                    "rgba(255,255,255,0.08)", "rgba(255,255,255,0.4)"
                ));
            }
        }

        // Ball at center
        objects.push(this.createBall(50, 50));

        return objects;
    },

    /* ── Bench player factory ─────────────────────────────────────── */
    createBenchPlayer(x, y, team = "home", label = "", number = 0) {
        return {
            id: this._uuid(),
            type: "bench",
            x, y,
            team,
            label: this._safeString(label),
            number: Math.round(this._clampNumber(number, 0, 99, 0)),
            color: team === "home" ? "#7ca8ff" : "#ff6b7b",
            radius: 2,
            locked: false,
            visible: true,
        };
    },

    /* ── Set-piece presets ────────────────────────────────────────── */
    SET_PIECE_PRESETS: {
        "corner-left": {
            label: "Corner (Left)",
            taker: { x: 0, y: 0 },
            attackers: [
                { x: 88, y: 35 }, { x: 90, y: 50 }, { x: 88, y: 65 },
                { x: 82, y: 40 }, { x: 82, y: 60 },
            ],
            defenders: [
                { x: 92, y: 38 }, { x: 92, y: 50 }, { x: 92, y: 62 },
                { x: 85, y: 45 }, { x: 85, y: 55 },
            ],
        },
        "corner-right": {
            label: "Corner (Right)",
            taker: { x: 0, y: 100 },
            attackers: [
                { x: 88, y: 35 }, { x: 90, y: 50 }, { x: 88, y: 65 },
                { x: 82, y: 40 }, { x: 82, y: 60 },
            ],
            defenders: [
                { x: 92, y: 38 }, { x: 92, y: 50 }, { x: 92, y: 62 },
                { x: 85, y: 45 }, { x: 85, y: 55 },
            ],
        },
        "freekick-central": {
            label: "Free Kick (Central)",
            taker: { x: 72, y: 50 },
            attackers: [
                { x: 85, y: 42 }, { x: 85, y: 50 }, { x: 85, y: 58 },
            ],
            defenders: [
                { x: 78, y: 38 }, { x: 78, y: 44 }, { x: 78, y: 50 },
                { x: 78, y: 56 }, { x: 78, y: 62 },
            ],
            wall: [
                { x: 76, y: 44 }, { x: 76, y: 50 }, { x: 76, y: 56 },
            ],
        },
        "freekick-wide-left": {
            label: "Free Kick (Wide Left)",
            taker: { x: 70, y: 10 },
            attackers: [
                { x: 88, y: 40 }, { x: 90, y: 50 }, { x: 88, y: 60 },
                { x: 82, y: 45 }, { x: 82, y: 55 },
            ],
            defenders: [
                { x: 92, y: 40 }, { x: 92, y: 50 }, { x: 92, y: 60 },
                { x: 86, y: 45 }, { x: 86, y: 55 },
            ],
        },
        "freekick-wide-right": {
            label: "Free Kick (Wide Right)",
            taker: { x: 70, y: 90 },
            attackers: [
                { x: 88, y: 40 }, { x: 90, y: 50 }, { x: 88, y: 60 },
                { x: 82, y: 45 }, { x: 82, y: 55 },
            ],
            defenders: [
                { x: 92, y: 40 }, { x: 92, y: 50 }, { x: 92, y: 60 },
                { x: 86, y: 45 }, { x: 86, y: 55 },
            ],
        },
        "penalty": {
            label: "Penalty",
            taker: { x: 78, y: 50 },
            attackers: [
                { x: 72, y: 35 }, { x: 72, y: 50 }, { x: 72, y: 65 },
            ],
            defenders: [
                { x: 95, y: 42 }, { x: 95, y: 50 }, { x: 95, y: 58 },
                { x: 88, y: 45 }, { x: 88, y: 55 },
            ],
        },
        "throwin-left": {
            label: "Throw-in (Left)",
            taker: { x: 50, y: 0 },
            attackers: [
                { x: 55, y: 20 }, { x: 60, y: 35 }, { x: 50, y: 45 },
                { x: 65, y: 50 },
            ],
            defenders: [
                { x: 55, y: 25 }, { x: 58, y: 40 }, { x: 52, y: 50 },
            ],
        },
        "throwin-right": {
            label: "Throw-in (Right)",
            taker: { x: 50, y: 100 },
            attackers: [
                { x: 55, y: 80 }, { x: 60, y: 65 }, { x: 50, y: 55 },
                { x: 65, y: 50 },
            ],
            defenders: [
                { x: 55, y: 75 }, { x: 58, y: 60 }, { x: 52, y: 50 },
            ],
        },
    },

    generateSetPiece(type, team = "home") {
        const preset = this.SET_PIECE_PRESETS[type];
        if (!preset) return [];

        const objects = [];
        const mirror = team === "away";
        const mx = (x) => mirror ? 100 - x : x;
        const my = (y) => mirror ? 100 - y : y;

        // Taker
        if (preset.taker) {
            objects.push(this.createPlayer(mx(preset.taker.x), my(preset.taker.y), team, "FB", 1));
        }

        // Attackers
        let num = 2;
        for (const pos of (preset.attackers || [])) {
            objects.push(this.createPlayer(mx(pos.x), my(pos.y), team, "ST", num++));
        }

        // Wall (if exists, rendered as dashed zone)
        if (preset.wall && preset.wall.length > 0) {
            const xs = preset.wall.map((p) => p.x);
            const ys = preset.wall.map((p) => p.y);
            const zx = mirror ? 100 - Math.max(...xs) : Math.min(...xs);
            const zy = Math.min(...ys);
            const zw = Math.abs(xs[xs.length - 1] - xs[0]) || 3;
            const zh = Math.abs(ys[ys.length - 1] - ys[0]) || 10;
            objects.push(this.createZone(zx, zy, zw, zh, "Wall"));
        }

        // Ball at taker position or near set piece
        const ballX = preset.taker ? mx(preset.taker.x) : 78;
        const ballY = preset.taker ? my(preset.taker.y) : 50;
        objects.push(this.createBall(ballX, ballY));

        return objects;
    },

    /* ── Default project template ──────────────────────────────────── */
    createProject(title = "Untitled") {
        const now = new Date().toISOString();
        return {
            board_id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36),
            title,
            sport: "football",
            pitch_type: "11v11",
            objects: [],
            layers: [{ id: "default", name: "Layer 1", visible: true, locked: false }],
            frames: [{ id: "frame-0", name: "Frame 1", objects: [], duration_ms: 3000 }],
            animationState: { playing: false, currentFrame: 0, loop: false },
            version: this.SCHEMA_VERSION,
            created_at: now,
            updated_at: now,
            source_attribution: "ScoutFootball tactical board",
        };
    },

    /* ── Object factories ──────────────────────────────────────────── */
    createPlayer(x, y, team = "home", label = "", number = 0) {
        return {
            id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
            type: "player",
            x, y,
            team,   // "home" | "away"
            label,
            number,
            color: team === "home" ? "#7ca8ff" : "#ff6b7b",
            radius: 3,
            locked: false,
            visible: true,
        };
    },

    createBall(x, y) {
        return {
            id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
            type: "ball",
            x, y,
            color: "#ffffff",
            radius: 1.5,
            locked: false,
            visible: true,
        };
    },

    createArrow(startX, startY, endX, endY, style = "solid") {
        return {
            id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
            type: "arrow",
            startX, startY, endX, endY,
            style,  // "solid" | "dashed" | "curved" | "dotted" | "run" | "pass" | "shot" | "dribble"
            color: "#ffffff",
            width: 2,
            locked: false,
            visible: true,
        };
    },

    createPath(points, color = "#ffffff", width = 2) {
        return {
            id: this._uuid(),
            type: "path",
            points: Array.isArray(points) ? points.map(p => ({
                x: this._clampNumber(p.x, 0, 100, 50),
                y: this._clampNumber(p.y, 0, 100, 50),
            })) : [],
            color: this._safeString(color, "#ffffff").slice(0, 32),
            width: this._clampNumber(width, 0.5, 10, 2),
            locked: false,
            visible: true,
        };
    },

    createRect(x, y, width, height, fillColor = "rgba(255,255,255,0.15)", borderColor = "rgba(255,255,255,0.4)") {
        return {
            id: this._uuid(),
            type: "rect",
            x, y, width, height,
            fillColor: this._safeString(fillColor, "rgba(255,255,255,0.15)").slice(0, 48),
            borderColor: this._safeString(borderColor, "rgba(255,255,255,0.4)").slice(0, 48),
            locked: false,
            visible: true,
        };
    },

    createEllipse(x, y, rx, ry, fillColor = "rgba(255,255,255,0.15)", borderColor = "rgba(255,255,255,0.4)") {
        return {
            id: this._uuid(),
            type: "ellipse",
            x, y, rx, ry,
            fillColor: this._safeString(fillColor, "rgba(255,255,255,0.15)").slice(0, 48),
            borderColor: this._safeString(borderColor, "rgba(255,255,255,0.4)").slice(0, 48),
            locked: false,
            visible: true,
        };
    },

    createZone(x, y, width, height, label = "") {
        return {
            id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
            type: "zone",
            x, y, width, height,
            label,
            color: "rgba(255,255,255,0.15)",
            borderColor: "rgba(255,255,255,0.4)",
            locked: false,
            visible: true,
        };
    },

    createText(x, y, text, options = {}) {
        return {
            id: this._uuid(),
            type: "text",
            x, y,
            text: this._safeString(text).slice(0, this.MAX_TEXT_LENGTH),
            fontSize: this._clampNumber(options.fontSize, 8, 36, 14),
            color: this._safeString(options.color, "#ffffff").slice(0, 32),
            locked: false,
            visible: true,
        };
    },

    createLayer(name) {
        return {
            id: this._uuid(),
            name: this._safeString(name, "Untitled Layer"),
            visible: true,
            locked: false,
        };
    },

    /* ── Formation generator ────────────────────────────────────────── */
    generateFormation(formationName, team = "home", offsetX = 0) {
        const formation = this.FORMATIONS[formationName];
        if (!formation) return [];

        const objects = [];
        const positions = [
            { role: "GK", items: formation.GK || [] },
            { role: "CB", items: formation.CB || [] },
            { role: "FB", items: formation.FB || [] },
            { role: "DM", items: formation.DM || [] },
            { role: "CM", items: formation.CM || [] },
            { role: "AM", items: formation.AM || [] },
            { role: "W",  items: formation.W || [] },
            { role: "ST", items: formation.ST || [] },
        ];

        let number = 1;
        for (const { role, items } of positions) {
            for (const pos of items) {
                const x = team === "away" ? 100 - pos.x + offsetX : pos.x + offsetX;
                const y = pos.y;
                const player = this.createPlayer(x, y, team, role, number);
                objects.push(player);
                number++;
            }
        }

        // Add ball at center
        if (team === "home") {
            objects.push(this.createBall(50, 50));
        }

        return objects;
    },

    /* ── Local storage ──────────────────────────────────────────────── */
    _safeString(value, fallback = "") {
        const text = String(value ?? fallback).slice(0, this.MAX_TEXT_LENGTH);
        return text.replace(/[\u0000-\u001F\u007F]/g, "");
    },

    _uuid() {
        return crypto.randomUUID
            ? crypto.randomUUID()
            : Date.now().toString(36) + Math.random().toString(36).slice(2);
    },

    _safeId(value, fallback = "") {
        const text = this._safeString(value, fallback || Date.now().toString(36));
        return text.replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 80) || Date.now().toString(36);
    },

    _clampNumber(value, min, max, fallback = 0) {
        const n = Number(value);
        if (!Number.isFinite(n)) return fallback;
        return Math.max(min, Math.min(max, n));
    },

    _sanitizeObject(object) {
        if (!object || typeof object !== "object") return null;
        const type = ["player", "ball", "arrow", "zone", "text", "path", "rect", "ellipse", "bench"].includes(object.type)
            ? object.type
            : "player";
        const safe = {
            id: this._safeId(object.id),
            type,
            locked: !!object.locked,
            visible: object.visible !== false,
        };
        if (type === "arrow") {
            safe.startX = this._clampNumber(object.startX, 0, 100, 50);
            safe.startY = this._clampNumber(object.startY, 0, 100, 50);
            safe.endX = this._clampNumber(object.endX, 0, 100, 55);
            safe.endY = this._clampNumber(object.endY, 0, 100, 55);
            safe.style = ["solid", "dashed", "curved", "dotted", "run", "pass", "shot", "dribble"].includes(object.style) ? object.style : "solid";
            safe.color = this._safeString(object.color, "#ffffff").slice(0, 32);
            safe.width = this._clampNumber(object.width, 0.5, 8, 2);
            return safe;
        }
        if (type === "path") {
            safe.points = Array.isArray(object.points)
                ? object.points.slice(0, 1000).map(p => ({
                    x: this._clampNumber(p.x, 0, 100, 50),
                    y: this._clampNumber(p.y, 0, 100, 50),
                }))
                : [];
            safe.color = this._safeString(object.color, "#ffffff").slice(0, 32);
            safe.width = this._clampNumber(object.width, 0.5, 10, 2);
            return safe;
        }
        if (type === "rect") {
            safe.x = this._clampNumber(object.x, 0, 100, 50);
            safe.y = this._clampNumber(object.y, 0, 100, 50);
            safe.width = this._clampNumber(object.width, 1, 100, 20);
            safe.height = this._clampNumber(object.height, 1, 100, 20);
            safe.fillColor = this._safeString(object.fillColor, "rgba(255,255,255,0.15)").slice(0, 48);
            safe.borderColor = this._safeString(object.borderColor, "rgba(255,255,255,0.4)").slice(0, 48);
            return safe;
        }
        if (type === "ellipse") {
            safe.x = this._clampNumber(object.x, 0, 100, 50);
            safe.y = this._clampNumber(object.y, 0, 100, 50);
            safe.rx = this._clampNumber(object.rx, 1, 50, 10);
            safe.ry = this._clampNumber(object.ry, 1, 50, 10);
            safe.fillColor = this._safeString(object.fillColor, "rgba(255,255,255,0.15)").slice(0, 48);
            safe.borderColor = this._safeString(object.borderColor, "rgba(255,255,255,0.4)").slice(0, 48);
            return safe;
        }
        safe.x = this._clampNumber(object.x, 0, 100, 50);
        safe.y = this._clampNumber(object.y, 0, 100, 50);
        safe.color = this._safeString(object.color, type === "player" ? "#7ca8ff" : "#ffffff").slice(0, 32);
        safe.radius = this._clampNumber(object.radius, 0.5, 8, type === "ball" ? 1.5 : 3);
        if (type === "player" || type === "bench") {
            safe.team = object.team === "away" ? "away" : "home";
            safe.label = this._safeString(object.label);
            safe.number = Math.round(this._clampNumber(object.number, 0, 99, 0));
        }
        if (type === "zone") {
            safe.width = this._clampNumber(object.width, 1, 100, 20);
            safe.height = this._clampNumber(object.height, 1, 100, 20);
            safe.label = this._safeString(object.label);
            safe.borderColor = this._safeString(object.borderColor, "rgba(255,255,255,0.4)").slice(0, 48);
        }
        if (type === "text") {
            safe.text = this._safeString(object.text).slice(0, this.MAX_TEXT_LENGTH);
            safe.fontSize = this._clampNumber(object.fontSize, 8, 36, 14);
        }
        return safe;
    },

    sanitizeProject(project) {
        if (!project || typeof project !== "object") return null;
        const now = new Date().toISOString();
        const objects = Array.isArray(project.objects)
            ? project.objects.slice(0, this.MAX_OBJECTS).map((item) => this._sanitizeObject(item)).filter(Boolean)
            : [];
        const frames = Array.isArray(project.frames) && project.frames.length > 0
            ? project.frames.slice(0, this.MAX_FRAMES).map((frame, i) => ({
                id: this._safeId(frame?.id, `frame-${i}`),
                name: this._safeString(frame?.name, `Frame ${i + 1}`),
                duration_ms: Math.round(this._clampNumber(frame?.duration_ms, 250, 60000, 3000)),
                notes: this._safeString(frame?.notes),
                objects: Array.isArray(frame?.objects)
                    ? frame.objects.slice(0, this.MAX_OBJECTS).map((item) => this._sanitizeObject(item)).filter(Boolean)
                    : [],
            }))
            : [{ id: "frame-0", name: "Frame 1", objects: [], duration_ms: 3000, notes: "" }];
        return {
            board_id: this._safeId(project.board_id),
            title: this._safeString(project.title, "Untitled"),
            sport: "football",
            pitch_type: ["11v11", "7v7", "5v5", "half-field", "training", "blank"].includes(project.pitch_type) ? project.pitch_type : "11v11",
            objects,
            layers: [{ id: "default", name: "Layer 1", visible: true, locked: false }],
            frames,
            version: this.SCHEMA_VERSION,
            created_at: this._safeString(project.created_at, now),
            updated_at: this._safeString(project.updated_at, now),
            source_attribution: this._safeString(
                project.source_attribution,
                "ScoutFootball tactical board",
            ),
        };
    },

    saveProject(project) {
        try {
            const safeProject = this.sanitizeProject(project);
            if (!safeProject) throw new Error("Invalid project");
            safeProject.updated_at = new Date().toISOString();
            const key = `tactical-board-${safeProject.board_id}`;
            localStorage.setItem(key, JSON.stringify(safeProject));
            return true;
        } catch (e) {
            console.warn("Failed to save tactical board project:", e);
            return false;
        }
    },

    loadProject(boardId) {
        try {
            const key = `tactical-board-${boardId}`;
            const data = localStorage.getItem(key);
            if (!data) return null;
            const project = this.sanitizeProject(JSON.parse(data));
            return project ? this.migrateProject(project) : null;
        } catch (e) {
            console.warn("Failed to load tactical board project:", e);
            return null;
        }
    },

    listProjects() {
        const projects = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith("tactical-board-")) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    const safeProject = this.sanitizeProject(data);
                    if (safeProject && safeProject.board_id) {
                        projects.push({
                            board_id: safeProject.board_id,
                            title: safeProject.title,
                            updated_at: safeProject.updated_at,
                        });
                    }
                } catch { /* skip corrupt entries */ }
            }
        }
        return projects.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
    },

    deleteProject(boardId) {
        try {
            localStorage.removeItem(`tactical-board-${boardId}`);
            return true;
        } catch {
            return false;
        }
    },

    exportJSON(project) {
        return JSON.stringify(project, null, 2);
    },

    importJSON(jsonString) {
        try {
            if (String(jsonString ?? "").length > this.MAX_IMPORT_BYTES) {
                throw new Error("Project file too large");
            }
            const project = JSON.parse(jsonString);
            if (!project.board_id) {
                throw new Error("Invalid project: missing board_id");
            }
            const safe = this.sanitizeProject(project);
            return safe ? this.migrateProject(safe) : null;
        } catch (e) {
            console.warn("Failed to import tactical board project:", e);
            return null;
        }
    },

    /* ── Animation / Keyframes ──────────────────────────────────────── */
    createFrame(name = "Frame", durationMs = 3000) {
        return {
            id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
            name,
            objects: [],       // snapshot of objects at this frame
            duration_ms: durationMs,
            notes: "",
        };
    },

    saveFrame(project, frameIndex) {
        if (!project || !project.frames) return;
        const frame = project.frames[frameIndex];
        if (frame) {
            frame.objects = JSON.parse(JSON.stringify(project.objects));
        }
    },

    loadFrame(project, frameIndex, renderer) {
        if (!project || !project.frames) return;
        const frame = project.frames[frameIndex];
        if (frame && frame.objects) {
            project.objects = JSON.parse(JSON.stringify(frame.objects));
            if (renderer) renderer.render();
        }
    },

    addFrame(project, name, durationMs = 3000) {
        if (!project.frames) project.frames = [];
        const frame = this.createFrame(name || `Frame ${project.frames.length + 1}`, durationMs);
        frame.objects = JSON.parse(JSON.stringify(project.objects));
        project.frames.push(frame);
        return frame;
    },

    removeFrame(project, frameIndex) {
        if (!project.frames || project.frames.length <= 1) return;
        if (frameIndex < 0 || frameIndex >= project.frames.length) return;
        project.frames.splice(frameIndex, 1);
    },

    renameProject(project, newTitle) {
        if (!project || typeof project !== "object") return;
        const sanitized = this._safeString(newTitle, "Untitled").trim() || "Untitled";
        project.title = sanitized;
        project.updated_at = new Date().toISOString();
    },

    toggleLoop(project) {
        if (!project) return false;
        if (!project.animationState) {
            project.animationState = { playing: false, currentFrame: 0, loop: false };
        }
        project.animationState.loop = !project.animationState.loop;
        return project.animationState.loop;
    },

    /* ── Version migration ─────────────────────────────────────────── */
    migrateProject(project) {
        if (!project || typeof project !== "object") return null;

        // Set version if missing
        if (!project.version) {
            project.version = this.SCHEMA_VERSION;
        }

        // Add missing layers
        if (!Array.isArray(project.layers) || project.layers.length === 0) {
            project.layers = [{ id: "default", name: "Layer 1", visible: true, locked: false }];
        }

        // Add missing frames
        if (!Array.isArray(project.frames) || project.frames.length === 0) {
            project.frames = [{ id: "frame-0", name: "Frame 1", objects: [], duration_ms: 3000 }];
        }

        // Add missing animationState
        if (!project.animationState || typeof project.animationState !== "object") {
            project.animationState = { playing: false, currentFrame: 0, loop: false };
        }

        // Fix objects missing visible/locked defaults
        if (Array.isArray(project.objects)) {
            for (const obj of project.objects) {
                if (obj && typeof obj === "object") {
                    if (obj.visible === undefined) obj.visible = true;
                    if (obj.locked === undefined) obj.locked = false;
                }
            }
        }

        // Sanitize all objects through _sanitizeObject
        if (Array.isArray(project.objects)) {
            project.objects = project.objects
                .map((obj) => this._sanitizeObject(obj))
                .filter(Boolean);
        }

        // Sanitize frame objects too
        if (Array.isArray(project.frames)) {
            for (const frame of project.frames) {
                if (frame && Array.isArray(frame.objects)) {
                    frame.objects = frame.objects
                        .map((obj) => this._sanitizeObject(obj))
                        .filter(Boolean);
                }
            }
        }

        return project;
    },

    /* ── Animation Playback ─────────────────────────────────────────── */
    interpolateObjects(fromObjs, toObjs, t) {
        if (!fromObjs || !toObjs) return toObjs || fromObjs || [];
        // Linear interpolation between two object sets
        const result = [];
        for (const toObj of toObjs) {
            const fromObj = fromObjs.find((o) => o.id === toObj.id);
            if (!fromObj) {
                result.push({ ...toObj });
                continue;
            }
            const interp = { ...toObj };
            if (toObj.type === "player" || toObj.type === "ball" || toObj.type === "text" || toObj.type === "bench") {
                interp.x = fromObj.x + (toObj.x - fromObj.x) * t;
                interp.y = fromObj.y + (toObj.y - fromObj.y) * t;
            }
            result.push(interp);
        }
        return result;
    },
};

/* ── migrateProject self-test ─────────────────────────────────────────── */
(function testMigrateProject() {
    // Simulate an old project missing version, layers, frames, animationState,
    // and objects without visible/locked fields.
    const oldProject = {
        board_id: "test-old-001",
        title: "Old Project",
        sport: "football",
        objects: [
            { id: "p1", type: "player", x: 50, y: 50, team: "home", color: "#7ca8ff", radius: 3, label: "", number: 1 },
            { id: "b1", type: "ball", x: 50, y: 50, color: "#ffffff", radius: 1.5 },
            { id: "a1", type: "arrow", startX: 10, startY: 10, endX: 90, endY: 90, style: "solid", color: "#ffffff", width: 2 },
        ],
        created_at: "2024-01-01T00:00:00.000Z",
        updated_at: "2024-01-01T00:00:00.000Z",
    };

    const migrated = TACTICAL_BOARD.migrateProject(oldProject);

    const checks = [];

    // Version should be set
    checks.push(["version set", migrated.version === "1.0.0"]);

    // Layers should be added
    checks.push(["layers added", Array.isArray(migrated.layers) && migrated.layers.length >= 1]);
    checks.push(["layer has id", migrated.layers[0].id === "default"]);

    // Frames should be added
    checks.push(["frames added", Array.isArray(migrated.frames) && migrated.frames.length >= 1]);
    checks.push(["frame has id", migrated.frames[0].id === "frame-0"]);

    // animationState should be added
    checks.push(["animationState added", !!migrated.animationState]);
    checks.push(["animationState.playing", migrated.animationState.playing === false]);
    checks.push(["animationState.currentFrame", migrated.animationState.currentFrame === 0]);
    checks.push(["animationState.loop", migrated.animationState.loop === false]);

    // Objects should be sanitized (visible/locked defaults applied, then sanitized)
    checks.push(["objects preserved", migrated.objects.length === 3]);

    const player = migrated.objects.find((o) => o.type === "player");
    checks.push(["player visible", player.visible === true]);
    checks.push(["player locked", player.locked === false]);

    const ball = migrated.objects.find((o) => o.type === "ball");
    checks.push(["ball visible", ball.visible === true]);
    checks.push(["ball locked", ball.locked === false]);

    const arrow = migrated.objects.find((o) => o.type === "arrow");
    checks.push(["arrow visible", arrow.visible === true]);
    checks.push(["arrow locked", arrow.locked === false]);

    // Null input should return null
    checks.push(["null returns null", TACTICAL_BOARD.migrateProject(null) === null]);

    // Report results
    const failed = checks.filter(([, ok]) => !ok);
    if (failed.length > 0) {
        console.error("[migrateProject test] FAIL:", failed.map(([name]) => name).join(", "));
    } else {
        console.log("[migrateProject test] PASS — all " + checks.length + " checks passed");
    }
})();
