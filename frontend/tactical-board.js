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
    SCHEMA_VERSION: "1.2.0",
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
            coaching_points: {
                title: "4-3-3 Attacking",
                description: "Wide forwards provide natural width while the midfield triangle controls the central zones.",
                key_points: [
                    "Press high when the ball goes to opposition fullbacks",
                    "Wingers tuck in without the ball to form a 4-5-1 defensive block",
                    "Single pivot drops between CBs during build-up play",
                    "Fullbacks overlap when wingers cut inside to shoot"
                ]
            },
        },
        "4-2-3-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            DM: [{ x: 35, y: 35 }, { x: 35, y: 65 }],
            AM: [{ x: 55, y: 25 }, { x: 55, y: 50 }, { x: 55, y: 75 }],
            ST: [{ x: 75, y: 50 }],
            coaching_points: {
                title: "4-2-3-1 Balanced",
                description: "Double pivot provides defensive stability while the #10 links midfield to attack.",
                key_points: [
                    "Two holding midfielders screen the back four and win second balls",
                    "The #10 finds pockets between opposition midfield and defense",
                    "Wide AMs track back to form a 4-4-2 defensive shape",
                    "Lone striker presses the opposition center-backs to force long balls"
                ]
            },
        },
        "3-5-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 25 }, { x: 20, y: 50 }, { x: 20, y: 75 }],
            FB: [{ x: 35, y: 10 }, { x: 35, y: 90 }],
            CM: [{ x: 45, y: 30 }, { x: 45, y: 50 }, { x: 45, y: 70 }],
            ST: [{ x: 75, y: 35 }, { x: 75, y: 65 }],
            coaching_points: {
                title: "3-5-2 Midfield Control",
                description: "Three center-backs with wing-backs provide both defensive solidity and attacking width.",
                key_points: [
                    "Wing-backs must cover the entire flank -- fitness is critical",
                    "Three CBs allow one to step into midfield with the ball",
                    "Central midfield trio controls possession and tempo",
                    "Two strikers can split wide to create space for midfield runners"
                ]
            },
        },
        "4-4-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            CM: [{ x: 40, y: 25 }, { x: 40, y: 75 }],
            W:  [{ x: 40, y: 10 }, { x: 40, y: 90 }],
            ST: [{ x: 75, y: 35 }, { x: 75, y: 65 }],
            coaching_points: {
                title: "4-4-2 Classic",
                description: "Flat midfield four with a strike partnership. Simple structure, high work rate required.",
                key_points: [
                    "Midfield four must stay compact horizontally -- max 30m between wingers",
                    "One striker presses, the other drops to screen the opposition pivot",
                    "Wingers track back to form a flat defensive line of six",
                    "Direct play to the front two or through fullback overlaps"
                ]
            },
        },
        "5-3-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 18, y: 25 }, { x: 18, y: 50 }, { x: 18, y: 75 }],
            FB: [{ x: 30, y: 10 }, { x: 30, y: 90 }],
            CM: [{ x: 45, y: 25 }, { x: 45, y: 50 }, { x: 45, y: 75 }],
            ST: [{ x: 75, y: 35 }, { x: 75, y: 65 }],
            coaching_points: {
                title: "5-3-2 Defensive",
                description: "Five at the back with compact midfield. Absorb pressure and hit on the counter.",
                key_points: [
                    "Back five stays deep -- no more than 35m from own goal",
                    "Wing-backs provide the only width in transition moments",
                    "Midfield three win second balls and play quick forward passes",
                    "Two strikers stay high to stretch opposition and counter-attack"
                ]
            },
        },
        "3-4-3": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 25 }, { x: 20, y: 50 }, { x: 20, y: 75 }],
            CM: [{ x: 45, y: 15 }, { x: 45, y: 50 }, { x: 45, y: 85 }],
            W:  [{ x: 70, y: 15 }, { x: 70, y: 85 }],
            ST: [{ x: 80, y: 50 }],
            coaching_points: {
                title: "3-4-3 Attacking Width",
                description: "Three forwards with wide midfielders. High risk, high reward formation.",
                key_points: [
                    "High defensive line is mandatory to compress space",
                    "Wide midfielders must be two-way players -- attack and defend",
                    "Three CBs cover the width, with the central CB sweeping",
                    "Front three press aggressively to win the ball high up the pitch"
                ]
            },
        },
        "3-4-2-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 25 }, { x: 20, y: 50 }, { x: 20, y: 75 }],
            FB: [{ x: 35, y: 10 }, { x: 35, y: 90 }],
            CM: [{ x: 45, y: 35 }, { x: 45, y: 65 }],
            AM: [{ x: 60, y: 35 }, { x: 60, y: 65 }],
            ST: [{ x: 80, y: 50 }],
            coaching_points: {
                title: "3-4-2-1 Narrow Diamond",
                description: "Two attacking midfielders behind the striker create central overloads.",
                key_points: [
                    "Two #10s operate in half-spaces to overload the center",
                    "Wing-backs provide all width -- must be elite crossers",
                    "Central midfield pair wins the ball and feeds the #10s",
                    "Striker holds the ball up and brings others into play"
                ]
            },
        },
        "4-1-4-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            DM: [{ x: 35, y: 50 }],
            CM: [{ x: 50, y: 25 }, { x: 50, y: 75 }],
            W:  [{ x: 65, y: 15 }, { x: 65, y: 85 }],
            ST: [{ x: 80, y: 50 }],
            coaching_points: {
                title: "4-1-4-1 Pivot Shield",
                description: "Single defensive midfielder screens the back four while wide players provide attacking threat.",
                key_points: [
                    "The lone pivot must have excellent positional awareness",
                    "Two CMs push forward to support the attack in the final third",
                    "Wingers stay wide to stretch the opposition back line",
                    "Striker drops deep to link play when needed"
                ]
            },
        },
        "4-3-1-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            CM: [{ x: 40, y: 25 }, { x: 40, y: 50 }, { x: 40, y: 75 }],
            AM: [{ x: 60, y: 50 }],
            ST: [{ x: 80, y: 35 }, { x: 80, y: 65 }],
            coaching_points: {
                title: "4-3-1-2 Diamond",
                description: "Central diamond with two strikers. Dominates the middle but relies on fullbacks for width.",
                key_points: [
                    "Fullbacks provide all width -- must be attack-minded",
                    "The #10 at the tip of the diamond is the creative hub",
                    "Two strikers press the center-backs and create space for the #10",
                    "Three CMs behind the #10 control tempo and recycle possession"
                ]
            },
        },
        "4-2-2-2": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            DM: [{ x: 35, y: 35 }, { x: 35, y: 65 }],
            AM: [{ x: 55, y: 25 }, { x: 55, y: 75 }],
            ST: [{ x: 80, y: 35 }, { x: 80, y: 65 }],
            coaching_points: {
                title: "4-2-2-2 Box Midfield",
                description: "Compact box midfield with two strikers. Strong in transition and pressing.",
                key_points: [
                    "Double pivot wins second balls and feeds the attacking midfielders",
                    "Two AMs operate in half-spaces between opposition lines",
                    "Two strikers press high and stretch the back line vertically",
                    "Fullbacks overlap to provide crosses -- no natural wingers"
                ]
            },
        },
        "4-5-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 20, y: 30 }, { x: 20, y: 70 }],
            FB: [{ x: 20, y: 10 }, { x: 20, y: 90 }],
            CM: [{ x: 40, y: 15 }, { x: 40, y: 35 }, { x: 40, y: 50 }, { x: 40, y: 65 }, { x: 40, y: 85 }],
            ST: [{ x: 80, y: 50 }],
            coaching_points: {
                title: "4-5-1 Low Block",
                description: "Five across midfield with a deep defensive shape. Designed to absorb and counter.",
                key_points: [
                    "Five-man midfield creates a wall in front of the defense",
                    "Lone striker stays high to hold the ball and wait for support",
                    "Wide midfielders double up with fullbacks to defend the flanks",
                    "Quick vertical passes to the striker on turnovers"
                ]
            },
        },
        "5-4-1": {
            GK: [{ x: 5, y: 50 }],
            CB: [{ x: 18, y: 25 }, { x: 18, y: 50 }, { x: 18, y: 75 }],
            FB: [{ x: 30, y: 10 }, { x: 30, y: 90 }],
            CM: [{ x: 45, y: 25 }, { x: 45, y: 50 }, { x: 45, y: 75 }],
            ST: [{ x: 80, y: 50 }],
            coaching_points: {
                title: "5-4-1 Ultra Defensive",
                description: "Five defenders and a flat four midfield. Maximum protection with one outlet.",
                key_points: [
                    "Back five sits very deep -- minimal space behind the defense",
                    "Four midfielders narrow the central channel and force play wide",
                    "Lone striker presses the center-backs to delay build-up",
                    "Set pieces and long balls are the primary attacking outlets"
                ]
            },
        },
    },

    /* ── Training presets ──────────────────────────────────────────── */
    TRAINING_PRESETS: {
        "rondo": {
            label: "Rondo 4v2",
            coaching_points: {
                title: "Rondo 4v2",
                description: "Possession-based warm-up drill. Four attackers keep the ball while two defenders try to win it.",
                key_points: [
                    "One-touch or two-touch limit to increase difficulty",
                    "Attackers must create passing angles by moving off the ball",
                    "Defenders press as a pair -- communication is key",
                    "Switch defenders every 60 seconds to maintain intensity"
                ]
            },
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
            coaching_points: {
                title: "Pressing Drill",
                description: "Coordinated pressing exercise. Players learn to press in groups and cover passing lanes.",
                key_points: [
                    "First presser closes the ball carrier at speed",
                    "Second presser covers the nearest passing option",
                    "Remaining players squeeze space and cut passing lanes",
                    "Communication triggers: 'press', 'cover', 'squeeze'"
                ]
            },
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
            coaching_points: {
                title: "Counter Attack Drill",
                description: "Fast transition exercise. Players practice breaking quickly from defense to attack.",
                key_points: [
                    "First pass after winning the ball must be forward and vertical",
                    "Wide players sprint into channels to stretch the defense",
                    "Support runners arrive late to pick up second balls",
                    "Finish the attack within 8 seconds of winning possession"
                ]
            },
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
            coaching_points: {
                title: "Possession Grid",
                description: "Small-sided possession game. Numerical superiority for the attacking team.",
                key_points: [
                    "Keep the ball moving -- no player holds it for more than 3 touches",
                    "Create triangles around the ball at all times",
                    "Defenders win the ball and try to play through the gates",
                    "Rotate positions every 2 minutes to develop versatility"
                ]
            },
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

    /* ── Coaching Points helpers ────────────────────────────────────── */
    getFormationCoachingPoints(formationName) {
        const formation = this.FORMATIONS[formationName];
        return formation && formation.coaching_points ? formation.coaching_points : null;
    },

    getSetPieceCoachingPoints(type) {
        const preset = this.SET_PIECE_PRESETS[type];
        return preset && preset.coaching_points ? preset.coaching_points : null;
    },

    getTrainingCoachingPoints(type) {
        const preset = this.TRAINING_PRESETS[type];
        return preset && preset.coaching_points ? preset.coaching_points : null;
    },

    formatCoachingNotes(cp) {
        if (!cp) return "";
        let notes = cp.title || "";
        if (cp.description) notes += "\n" + cp.description;
        if (Array.isArray(cp.key_points) && cp.key_points.length > 0) {
            notes += "\n";
            for (const kp of cp.key_points) {
                notes += "\n- " + kp;
            }
        }
        return notes;
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

    /* ── Training equipment factories ─────────────────────────────── */
    createCone(x, y, color = "#ff9800") {
        return {
            id: this._uuid(),
            type: "cone",
            x, y,
            color: this._safeString(color, "#ff9800").slice(0, 32),
            radius: 1.5,
            locked: false,
            visible: true,
        };
    },

    createMarker(x, y, color = "#4caf50") {
        return {
            id: this._uuid(),
            type: "marker",
            x, y,
            color: this._safeString(color, "#4caf50").slice(0, 32),
            radius: 1.5,
            locked: false,
            visible: true,
        };
    },

    createPole(x, y, height = 6, color = "#ffeb3b") {
        return {
            id: this._uuid(),
            type: "pole",
            x, y,
            height: this._clampNumber(height, 2, 20, 6),
            color: this._safeString(color, "#ffeb3b").slice(0, 32),
            locked: false,
            visible: true,
        };
    },

    createLadder(x, y, width = 10, height = 8) {
        return {
            id: this._uuid(),
            type: "ladder",
            x, y,
            width: this._clampNumber(width, 2, 30, 10),
            height: this._clampNumber(height, 2, 20, 8),
            color: "#ffffff",
            locked: false,
            visible: true,
        };
    },

    createMiniGoal(x, y, width = 8, height = 5) {
        return {
            id: this._uuid(),
            type: "minigoal",
            x, y,
            width: this._clampNumber(width, 2, 30, 8),
            height: this._clampNumber(height, 2, 20, 5),
            color: "rgba(255,255,255,0.6)",
            locked: false,
            visible: true,
        };
    },

    /* ── Set-piece presets ────────────────────────────────────────── */
    SET_PIECE_PRESETS: {
        "corner-left": {
            label: "Corner (Left)",
            coaching_points: {
                title: "Corner Kick (Left Side)",
                description: "In-swinging delivery from the left. Attackers target near post and far post zones.",
                key_points: [
                    "Taker delivers an in-swinging ball to the near post area",
                    "First runner attacks the near post with a flick-on",
                    "Second runner arrives at the far post for the knockdown",
                    "Defenders mark man-to-man with one player on the post"
                ]
            },
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
            coaching_points: {
                title: "Corner Kick (Right Side)",
                description: "Out-swinging delivery from the right. Attackers aim for the six-yard box.",
                key_points: [
                    "Taker delivers an out-swinging ball towards the penalty spot",
                    "Runners time their movement to arrive as the ball crosses",
                    "One attacker screens the goalkeeper to block the view",
                    "Set a decoy run to pull defenders out of position"
                ]
            },
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
            coaching_points: {
                title: "Free Kick (Central)",
                description: "Direct shot or combination play from a central position 20-30m from goal.",
                key_points: [
                    "Wall must jump and turn -- goalkeeper covers the low shot",
                    "Taker can go over the wall or play a short combination",
                    "Runners make dummy runs to create confusion in the wall gap",
                    "If the ball is passed short, the receiver must shoot first time"
                ]
            },
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
            coaching_points: {
                title: "Free Kick (Wide Left)",
                description: "Crossing opportunity from the left channel. Attackers target specific zones in the box.",
                key_points: [
                    "Taker delivers to the back post where the tallest attacker runs",
                    "Near post runner makes a decoy run to pull the defense forward",
                    "Edge-of-box player picks up any clearance for a shot",
                    "Two players stay back to prevent a counter-attack"
                ]
            },
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
            coaching_points: {
                title: "Free Kick (Wide Right)",
                description: "Crossing opportunity from the right channel. Near post and far post runners required.",
                key_points: [
                    "In-swinging delivery from the right targets the six-yard box",
                    "One runner attacks the near post for a flick-on header",
                    "Second runner arrives at the back post for the finish",
                    "Set a block on the nearest defender to free up the runner"
                ]
            },
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
            coaching_points: {
                title: "Penalty Kick",
                description: "One-on-one from 12 yards. Technique and composure under pressure.",
                key_points: [
                    "Pick a side and commit -- do not change your mind mid-run",
                    "Place the ball low and to the corner for highest conversion",
                    "Goalkeeper research: know the taker's preferred side",
                    "Rebound runners position at the edge of the box"
                ]
            },
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
            coaching_points: {
                title: "Throw-in (Left Side)",
                description: "Long throw or short option from the left flank. Maintain possession or create a chance.",
                key_points: [
                    "Short throw to the nearest player maintains possession",
                    "Long throw into the box is a set-piece opportunity",
                    "Players must make space with a body feint before receiving",
                    "If under pressure, throw back to the goalkeeper to reset"
                ]
            },
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
            coaching_points: {
                title: "Throw-in (Right Side)",
                description: "Throw-in from the right flank. Focus on quick throw-ins to catch the opposition off guard.",
                key_points: [
                    "Quick throw-in before the defense sets up can create chances",
                    "Target the player making a run behind the fullback",
                    "If no forward option is available, recycle to the center-back",
                    "Second player peels away to offer a safe short option"
                ]
            },
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
            displayMode: "single",
            objects: [],
            layers: [{ id: "default", name: "Layer 1", visible: true, locked: false }],
            frames: [{ id: "frame-0", name: "Frame 1", objects: [], duration_ms: 3000 }],
            animationState: { playing: false, currentFrame: 0, loop: false },
            animationMode: "timing",
            stepDuration: 1000,
            version: this.SCHEMA_VERSION,
            created_at: now,
            updated_at: now,
            source_attribution: "ScoutFootball tactical board",
            metadata: {},
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
            appearance: {
                shape: "circle",  // "circle" | "square" | "triangle" | "diamond"
                size: 3,          // 1-5 scale (maps to radius)
                opacity: 1.0,     // 0.3-1.0
            },
            notes: "",
            pathPoints: [],      // [{x, y}] intermediate path points
            pathType: "linear",  // "linear" | "curved"
            easing: "linear",    // "linear" | "ease-in" | "ease-out" | "ease-in-out"
            delay_ms: 0,         // delay before object starts moving
            pause_ms: 0,         // pause at each path point
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
            visibleFrom: 0,
            visibleTo: Infinity,
            possession: null, // "home" | "away" | null
            pathPoints: [],
            pathType: "linear",
            easing: "linear",
            delay_ms: 0,
            pause_ms: 0,
        };
    },

    createMultipleBalls(count) {
        const balls = [];
        const c = Math.max(1, Math.min(20, Math.round(count || 1)));
        for (let i = 0; i < c; i++) {
            const bx = 10 + Math.random() * 80;
            const by = 10 + Math.random() * 80;
            balls.push(this.createBall(bx, by));
        }
        return balls;
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

    /* ── Event Marker types ─────────────────────────────────────────── */
    EVENT_MARKER_TYPES: ["press", "pass", "shot", "turnover", "overlap", "underlap", "third-man", "cover"],

    /* ── Phase types ────────────────────────────────────────────────── */
    PHASE_TYPES: ["buildup", "pressing", "defense", "counter", "set-piece"],

    PHASE_ICONS: {
        "buildup": "\u25CE",
        "pressing": "\u25CB",
        "defense": "\u25A3",
        "counter": "\u25B6",
        "set-piece": "\u25C7",
    },

    /* ── Event Marker factory ───────────────────────────────────────── */
    createEventMarker(x, y, markerType = "press", label = "") {
        const validType = this.EVENT_MARKER_TYPES.includes(markerType) ? markerType : "press";
        return {
            id: this._uuid(),
            type: "event-marker",
            x, y,
            markerType: validType,
            label: this._safeString(label).slice(0, 60),
            locked: false,
            visible: true,
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
        const type = ["player", "ball", "arrow", "zone", "text", "path", "rect", "ellipse", "bench", "cone", "marker", "pole", "ladder", "minigoal", "event-marker"].includes(object.type)
            ? object.type
            : "player";
        const safe = {
            id: this._safeId(object.id),
            type,
            locked: !!object.locked,
            visible: object.visible !== false,
            visibleFrom: Number.isFinite(object.visibleFrom) ? object.visibleFrom : 0,
            visibleTo: Number.isFinite(object.visibleTo) ? object.visibleTo : Infinity,
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
        if (type === "ball") {
            safe.possession = (object.possession === "home" || object.possession === "away") ? object.possession : null;
            safe.pathPoints = Array.isArray(object.pathPoints)
                ? object.pathPoints.slice(0, 50).map(p => ({
                    x: this._clampNumber(p.x, 0, 100, 50),
                    y: this._clampNumber(p.y, 0, 100, 50),
                }))
                : [];
            safe.pathType = ["linear", "curved"].includes(object.pathType) ? object.pathType : "linear";
            safe.easing = ["linear", "ease-in", "ease-out", "ease-in-out"].includes(object.easing) ? object.easing : "linear";
            safe.delay_ms = Math.round(this._clampNumber(object.delay_ms, 0, 10000, 0));
            safe.pause_ms = Math.round(this._clampNumber(object.pause_ms, 0, 10000, 0));
        }
        if (type === "player" || type === "bench") {
            safe.team = object.team === "away" ? "away" : "home";
            safe.label = this._safeString(object.label);
            safe.number = Math.round(this._clampNumber(object.number, 0, 99, 0));
            if (type === "player") {
                const validShapes = ["circle", "square", "triangle", "diamond"];
                const srcApp = object.appearance && typeof object.appearance === "object" ? object.appearance : {};
                safe.appearance = {
                    shape: validShapes.includes(srcApp.shape) ? srcApp.shape : "circle",
                    size: Math.round(this._clampNumber(srcApp.size, 1, 5, 3)),
                    opacity: this._clampNumber(srcApp.opacity, 0.3, 1.0, 1.0),
                };
                safe.notes = this._safeString(object.notes).slice(0, 500);
                // Sync radius with appearance.size so drawing stays consistent
                safe.radius = safe.appearance.size;
                // Path and timing fields
                safe.pathPoints = Array.isArray(object.pathPoints)
                    ? object.pathPoints.slice(0, 50).map(p => ({
                        x: this._clampNumber(p.x, 0, 100, 50),
                        y: this._clampNumber(p.y, 0, 100, 50),
                    }))
                    : [];
                safe.pathType = ["linear", "curved"].includes(object.pathType) ? object.pathType : "linear";
                safe.easing = ["linear", "ease-in", "ease-out", "ease-in-out"].includes(object.easing) ? object.easing : "linear";
                safe.delay_ms = Math.round(this._clampNumber(object.delay_ms, 0, 10000, 0));
                safe.pause_ms = Math.round(this._clampNumber(object.pause_ms, 0, 10000, 0));
            }
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
        if (type === "cone" || type === "marker") {
            safe.color = this._safeString(object.color, type === "cone" ? "#ff9800" : "#4caf50").slice(0, 32);
            safe.radius = this._clampNumber(object.radius, 0.5, 5, 1.5);
        }
        if (type === "pole") {
            safe.height = this._clampNumber(object.height, 2, 20, 6);
            safe.color = this._safeString(object.color, "#ffeb3b").slice(0, 32);
            safe.width = 0.3;
        }
        if (type === "ladder") {
            safe.width = this._clampNumber(object.width, 2, 30, 10);
            safe.height = this._clampNumber(object.height, 2, 20, 8);
            safe.color = this._safeString(object.color, "#ffffff").slice(0, 32);
        }
        if (type === "minigoal") {
            safe.width = this._clampNumber(object.width, 2, 30, 8);
            safe.height = this._clampNumber(object.height, 2, 20, 5);
            safe.color = this._safeString(object.color, "rgba(255,255,255,0.6)").slice(0, 48);
        }
        if (type === "event-marker") {
            safe.x = this._clampNumber(object.x, 0, 100, 50);
            safe.y = this._clampNumber(object.y, 0, 100, 50);
            safe.markerType = this.EVENT_MARKER_TYPES.includes(object.markerType) ? object.markerType : "press";
            safe.label = this._safeString(object.label).slice(0, 60);
        }
        return safe;
    },

    _sanitizeDecisionPack(pack) {
        if (!pack || typeof pack !== "object") return null;
        const prediction = pack.prediction && typeof pack.prediction === "object" ? pack.prediction : {};
        const provenance = pack.provenance && typeof pack.provenance === "object" ? pack.provenance : {};
        const match = pack.match && typeof pack.match === "object" ? pack.match : {};
        const status = ["available", "not_loaded"].includes(prediction.status)
            ? prediction.status
            : "not_loaded";
        const probability = (value) => {
            if (status !== "available") return null;
            const number = Number(value);
            return Number.isFinite(number) ? this._clampNumber(number, 0, 1, 0) : null;
        };
        const boundedMatrix = Array.isArray(prediction.score_matrix)
            ? prediction.score_matrix.slice(0, 12).map((row) => Array.isArray(row)
                ? row.slice(0, 12).map((value) => this._clampNumber(value, 0, 1, 0))
                : [])
            : null;
        const limitations = Array.isArray(pack.limitations)
            ? pack.limitations.slice(0, 6).map((item) => this._safeString(item).slice(0, 300)).filter(Boolean)
            : [];
        return {
            schema: "scoutfootball.tactical-decision-pack",
            version: "1.0.0",
            created_at: this._safeString(pack.created_at, new Date().toISOString()),
            match: {
                home_team: this._safeString(match.home_team).slice(0, 120),
                away_team: this._safeString(match.away_team).slice(0, 120),
            },
            prediction: {
                status,
                model_type: this._safeString(prediction.model_type).slice(0, 120),
                model_version: this._safeString(prediction.model_version).slice(0, 120),
                probabilities: {
                    home_win: probability(prediction.probabilities?.home_win),
                    draw: probability(prediction.probabilities?.draw),
                    away_win: probability(prediction.probabilities?.away_win),
                },
                expected_goals: {
                    home: status === "available" ? this._clampNumber(prediction.expected_goals?.home, 0, 20, 0) : null,
                    away: status === "available" ? this._clampNumber(prediction.expected_goals?.away, 0, 20, 0) : null,
                },
                score_matrix: status === "available" ? boundedMatrix : null,
                coverage: {
                    status: this._safeString(prediction.coverage?.status, "unknown").slice(0, 40),
                    summary: this._safeString(prediction.coverage?.summary).slice(0, 240),
                },
            },
            provenance: {
                model_run_id: this._safeString(provenance.model_run_id).slice(0, 160),
                input_hash: this._safeString(provenance.input_hash).slice(0, 160),
                feature_manifest_hash: this._safeString(provenance.feature_manifest_hash).slice(0, 160),
                lineage_status: this._safeString(provenance.lineage_status, "not_recorded").slice(0, 40),
                snapshot: this._safeString(provenance.snapshot, "local artifact snapshot").slice(0, 240),
            },
            limitations,
        };
    },

    createDecisionPack({ match = {}, prediction = {}, provenance = {}, limitations = [] } = {}) {
        return this._sanitizeDecisionPack({
            created_at: new Date().toISOString(),
            match: {
                home_team: match.home_team ?? match.home,
                away_team: match.away_team ?? match.away,
            },
            prediction,
            provenance,
            limitations,
        });
    },

    formatDecisionPackNotes(pack) {
        const safe = this._sanitizeDecisionPack(pack);
        if (!safe) return "";
        const prediction = safe.prediction;
        const lines = [
            `${safe.match.home_team || "Home"} vs ${safe.match.away_team || "Away"} Pre-Match Decision Pack`,
            `Model: ${prediction.model_type || "not recorded"}${prediction.model_version ? ` (${prediction.model_version})` : ""}`,
            `Coverage: ${prediction.coverage.summary || prediction.coverage.status || "unknown"}`,
        ];
        if (prediction.status === "available") {
            const probability = prediction.probabilities;
            lines.push(`Home win: ${Math.round((probability.home_win || 0) * 100)}% | Draw: ${Math.round((probability.draw || 0) * 100)}% | Away win: ${Math.round((probability.away_win || 0) * 100)}%`);
            lines.push(`Expected goals: ${(prediction.expected_goals.home || 0).toFixed(2)} / ${(prediction.expected_goals.away || 0).toFixed(2)}`);
        } else {
            lines.push("Prediction output was not loaded. No fallback probability or score estimate was recorded.");
        }
        lines.push(`Provenance: ${safe.provenance.model_run_id ? `model run ${safe.provenance.model_run_id}` : safe.provenance.snapshot}${safe.provenance.input_hash ? ` | input ${safe.provenance.input_hash}` : ""}`);
        if (safe.limitations.length) lines.push(`Limitations: ${safe.limitations.join(" ")}`);
        return lines.join("\n");
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
                eventMarkers: Array.isArray(frame?.eventMarkers)
                    ? frame.eventMarkers.slice(0, 50).map((m) => ({
                        type: ["press","pass","shot","turnover","overlap","underlap","third-man","cover"].includes(m?.type) ? m.type : "press",
                        x: this._clampNumber(m?.x, 0, 100, 50),
                        y: this._clampNumber(m?.y, 0, 100, 50),
                        label: this._safeString(m?.label).slice(0, 60),
                    }))
                    : [],
                phase: this.PHASE_TYPES.includes(frame?.phase) ? frame.phase : "",
                trigger: this._safeString(frame?.trigger).slice(0, 200),
                roles: this._safeString(frame?.roles).slice(0, 200),
            }))
            : [{ id: "frame-0", name: "Frame 1", objects: [], duration_ms: 3000, notes: "" }];
        return {
            board_id: this._safeId(project.board_id),
            title: this._safeString(project.title, "Untitled"),
            sport: "football",
            pitch_type: ["11v11", "7v7", "5v5", "half-field", "training", "blank"].includes(project.pitch_type) ? project.pitch_type : "11v11",
            displayMode: ["single", "both", "transition"].includes(project.displayMode) ? project.displayMode : "single",
            objects,
            layers: [{ id: "default", name: "Layer 1", visible: true, locked: false }],
            frames,
            animationMode: ["timing", "step"].includes(project.animationMode) ? project.animationMode : "timing",
            stepDuration: Math.round(this._clampNumber(project.stepDuration, 250, 10000, 1000)),
            version: this.SCHEMA_VERSION,
            created_at: this._safeString(project.created_at, now),
            updated_at: this._safeString(project.updated_at, now),
            source_attribution: this._safeString(
                project.source_attribution,
                "ScoutFootball tactical board",
            ),
            metadata: {
                decision_pack: this._sanitizeDecisionPack(project.metadata?.decision_pack),
            },
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
                            object_count: (safeProject.objects || []).length,
                            frame_count: (safeProject.frames || []).length,
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
            const msg = e instanceof SyntaxError
                ? "Corrupt file: invalid JSON. Please check the file is a valid tactical board export."
                : "Failed to import tactical board project: " + (e.message || e);
            console.warn(msg, e);
            return null;
        }
    },

    /* ── Migration history ───────────────────────────────────────────── */
    MIGRATION_HISTORY: [
        {
            version: "1.1.0",
            description: "Add animation path/timing fields to objects",
            migrate(project) {
                const addDefaults = (obj) => {
                    if (!obj || typeof obj !== "object") return;
                    if (obj.type === "player" || obj.type === "ball") {
                        if (!Array.isArray(obj.pathPoints)) obj.pathPoints = [];
                        if (typeof obj.pathType === "undefined") obj.pathType = "linear";
                        if (typeof obj.easing === "undefined") obj.easing = "linear";
                        if (typeof obj.delay_ms === "undefined") obj.delay_ms = 0;
                        if (typeof obj.pause_ms === "undefined") obj.pause_ms = 0;
                    }
                };
                if (Array.isArray(project.objects)) {
                    project.objects.forEach(addDefaults);
                }
                if (Array.isArray(project.frames)) {
                    for (const frame of project.frames) {
                        if (Array.isArray(frame.objects)) {
                            frame.objects.forEach(addDefaults);
                        }
                    }
                }
                if (typeof project.animationMode === "undefined") {
                    project.animationMode = "timing";
                }
                if (typeof project.stepDuration === "undefined") {
                    project.stepDuration = 1000;
                }
                return project;
            },
        },
        {
            version: "1.2.0",
            description: "Add constrained decision-pack metadata",
            migrate(project) {
                if (!project.metadata || typeof project.metadata !== "object") {
                    project.metadata = {};
                }
            },
        },
    ],

    /* ── Validate project ──────────────────────────────────────────── */
    validateProject(project) {
        const errors = [];
        if (!project || typeof project !== "object") {
            errors.push("Project is not a valid object");
            return { valid: false, errors };
        }
        if (!project.board_id || typeof project.board_id !== "string") {
            errors.push("Missing or invalid board_id");
        }
        if (!project.title || typeof project.title !== "string") {
            errors.push("Missing or invalid title");
        }
        if (!project.version || typeof project.version !== "string") {
            errors.push("Missing or invalid version");
        }
        if (!Array.isArray(project.objects)) {
            errors.push("Missing objects array");
        } else if (project.objects.length > this.MAX_OBJECTS) {
            errors.push("Too many objects: " + project.objects.length + " (max " + this.MAX_OBJECTS + ")");
        }
        if (!Array.isArray(project.frames)) {
            errors.push("Missing frames array");
        } else if (project.frames.length > this.MAX_FRAMES) {
            errors.push("Too many frames: " + project.frames.length + " (max " + this.MAX_FRAMES + ")");
        }
        if (!Array.isArray(project.layers)) {
            errors.push("Missing layers array");
        }
        if (!project.created_at || typeof project.created_at !== "string") {
            errors.push("Missing or invalid created_at");
        }
        if (!project.updated_at || typeof project.updated_at !== "string") {
            errors.push("Missing or invalid updated_at");
        }
        const validPitchTypes = ["11v11", "7v7", "5v5", "half-field", "training", "blank"];
        if (project.pitch_type && !validPitchTypes.includes(project.pitch_type)) {
            errors.push("Invalid pitch_type: " + project.pitch_type);
        }
        return { valid: errors.length === 0, errors };
    },

    /* ── Round-trip self-test ──────────────────────────────────────── */
    roundTripTest() {
        const checks = [];
        try {
            const proj = this.createProject("RT-Test");
            proj.objects.push(this.createPlayer(50, 50, "home", "GK", 1));
            proj.objects.push(this.createBall(50, 50));
            proj.objects.push(this.createArrow(10, 10, 90, 90, "solid"));
            this.addFrame(proj, "Frame 2", 2000);
            this.saveFrame(proj, 1);

            const json = this.exportJSON(proj);
            checks.push(["export returns string", typeof json === "string" && json.length > 0]);

            const imported = this.importJSON(json);
            checks.push(["import returns object", !!imported]);

            checks.push(["board_id matches", imported.board_id === proj.board_id]);
            checks.push(["title matches", imported.title === proj.title]);
            checks.push(["version matches", imported.version === proj.version]);
            checks.push(["object count matches", imported.objects.length === proj.objects.length]);
            checks.push(["frame count matches", imported.frames.length === proj.frames.length]);

            const pPlayer = imported.objects.find(function(o) { return o.type === "player"; });
            checks.push(["player has pathPoints", Array.isArray(pPlayer.pathPoints)]);
            checks.push(["player has easing", typeof pPlayer.easing === "string"]);

            const pBall = imported.objects.find(function(o) { return o.type === "ball"; });
            checks.push(["ball has delay_ms", typeof pBall.delay_ms === "number"]);
            checks.push(["animationMode preserved", imported.animationMode === proj.animationMode]);

            var validation = this.validateProject(imported);
            checks.push(["imported passes validation", validation.valid]);

            var corrupt = this.importJSON("{not valid json");
            checks.push(["corrupt JSON returns null", corrupt === null]);

            var noId = this.importJSON('{"title":"test"}');
            checks.push(["missing board_id returns null", noId === null]);
        } catch (e) {
            checks.push(["exception thrown", false]);
        }

        var failed = checks.filter(function(c) { return !c[1]; });
        if (failed.length > 0) {
            console.error("[roundTripTest] FAIL:", failed.map(function(c) { return c[0]; }).join(", "));
            return false;
        }
        console.log("[roundTripTest] PASS -- all " + checks.length + " checks passed");
        return true;
    },

    /* Compare semver strings: returns true if a < b */
    _versionBefore(a, b) {
        var pa = String(a).split(".").map(Number);
        var pb = String(b).split(".").map(Number);
        for (var i = 0; i < 3; i++) {
            if ((pa[i] || 0) < (pb[i] || 0)) return true;
            if ((pa[i] || 0) > (pb[i] || 0)) return false;
        }
        return false;
    },

    /* ── Animation / Keyframes ──────────────────────────────────────── */
    createFrame(name = "Frame", durationMs = 3000) {
        return {
            id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
            name,
            objects: [],       // snapshot of objects at this frame
            duration_ms: durationMs,
            notes: "",
            eventMarkers: [],
            phase: "",
            trigger: "",
            roles: "",
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

        // Apply migrations sequentially based on project.version
        var projectVersion = project.version || "1.0.0";
        for (var mi = 0; mi < this.MIGRATION_HISTORY.length; mi++) {
            var migration = this.MIGRATION_HISTORY[mi];
            if (this._versionBefore(projectVersion, migration.version)) {
                try {
                    migration.migrate(project);
                } catch (e) {
                    console.warn("Migration to " + migration.version + " failed:", e);
                }
            }
        }
        project.version = this.SCHEMA_VERSION;

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
                // Add missing fragment metadata to old frames
                if (frame && !Array.isArray(frame.eventMarkers)) {
                    frame.eventMarkers = [];
                }
                if (frame && typeof frame.phase === "undefined") {
                    frame.phase = "";
                }
                if (frame && typeof frame.trigger === "undefined") {
                    frame.trigger = "";
                }
                if (frame && typeof frame.roles === "undefined") {
                    frame.roles = "";
                }
            }
        }

        return project;
    },

    /* ── Animation Playback ─────────────────────────────────────────── */

    /* Easing functions: input t in [0,1], output eased t */
    _applyEasing(t, easing) {
        if (!easing || easing === "linear") return t;
        switch (easing) {
            case "ease-in":
                return t * t;
            case "ease-out":
                return t * (2 - t);
            case "ease-in-out":
                return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
            default:
                return t;
        }
    },

    /* Quadratic bezier evaluation: P(t) = (1-t)^2*P0 + 2*(1-t)*t*CP + t^2*P1 */
    _quadraticBezier(p0, cp, p1, t) {
        const mt = 1 - t;
        return {
            x: mt * mt * p0.x + 2 * mt * t * cp.x + t * t * p1.x,
            y: mt * mt * p0.y + 2 * mt * t * cp.y + t * t * p1.y,
        };
    },

    /* Calculate auto control point: perpendicular offset from midpoint */
    _autoControlPoint(p0, p1) {
        const mx = (p0.x + p1.x) / 2;
        const my = (p0.y + p1.y) / 2;
        const dx = p1.x - p0.x;
        const dy = p1.y - p0.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len < 0.001) return { x: mx, y: my };
        const offset = len * 0.3;
        // Perpendicular direction
        return {
            x: mx + (-dy / len) * offset,
            y: my + (dx / len) * offset,
        };
    },

    /* Interpolate along a path of points using bezier or linear segments */
    _interpolatePath(pathPoints, fromPos, toPos, t, pathType) {
        // Build full point sequence: from -> pathPoints -> to
        const allPoints = [
            { x: fromPos.x, y: fromPos.y },
            ...pathPoints.map(p => ({ x: p.x, y: p.y })),
            { x: toPos.x, y: toPos.y },
        ];

        if (allPoints.length < 2) return toPos;
        if (allPoints.length === 2) {
            // Simple linear
            return {
                x: allPoints[0].x + (allPoints[1].x - allPoints[0].x) * t,
                y: allPoints[0].y + (allPoints[1].y - allPoints[0].y) * t,
            };
        }

        if (pathType === "curved") {
            // Use piecewise quadratic bezier through all points
            // For N segments, distribute t across segments
            const segments = allPoints.length - 1;
            const segT = t * segments;
            const segIdx = Math.min(Math.floor(segT), segments - 1);
            const localT = segT - segIdx;

            const p0 = allPoints[segIdx];
            const p1 = allPoints[segIdx + 1];
            const cp = this._autoControlPoint(p0, p1);
            return this._quadraticBezier(p0, cp, p1, localT);
        }

        // Linear path through all points
        const segments = allPoints.length - 1;
        const segT = t * segments;
        const segIdx = Math.min(Math.floor(segT), segments - 1);
        const localT = segT - segIdx;

        const p0 = allPoints[segIdx];
        const p1 = allPoints[segIdx + 1];
        return {
            x: p0.x + (p1.x - p0.x) * localT,
            y: p0.y + (p1.y - p0.y) * localT,
        };
    },

    /* Calculate delay-adjusted t for an object within a frame duration */
    _delayAdjustedT(t, obj, frameDuration) {
        const delay = obj.delay_ms || 0;
        const pause = obj.pause_ms || 0;

        if (delay > 0 && frameDuration > 0) {
            const delayFraction = delay / frameDuration;
            if (t < delayFraction) return 0;
            t = (t - delayFraction) / (1 - delayFraction);
        }

        if (pause > 0 && frameDuration > 0) {
            const pauseFraction = pause / frameDuration;
            // Apply pause in the middle of the movement
            const pauseStart = 0.5 - pauseFraction / 2;
            const pauseEnd = 0.5 + pauseFraction / 2;
            if (t >= pauseStart && t <= pauseEnd) {
                return 0.5;
            } else if (t > pauseEnd) {
                t = 0.5 + (t - pauseEnd) / (1 - pauseEnd) * 0.5;
            } else {
                t = t / pauseStart * 0.5;
            }
        }

        return Math.max(0, Math.min(1, t));
    },

    interpolateObjects(fromObjs, toObjs, t, frameDuration) {
        if (!fromObjs || !toObjs) return toObjs || fromObjs || [];
        const result = [];
        for (const toObj of toObjs) {
            const fromObj = fromObjs.find((o) => o.id === toObj.id);
            if (!fromObj) {
                result.push({ ...toObj });
                continue;
            }
            const interp = { ...toObj };
            if (toObj.type === "player" || toObj.type === "ball" || toObj.type === "text" || toObj.type === "bench" || toObj.type === "cone" || toObj.type === "marker" || toObj.type === "pole") {
                // Apply delay/pause adjustment
                let localT = this._delayAdjustedT(t, toObj, frameDuration || 3000);
                // Apply easing
                localT = this._applyEasing(localT, toObj.easing);

                const pathPoints = toObj.pathPoints || fromObj.pathPoints || [];
                if (pathPoints.length > 0) {
                    // Path interpolation
                    const pos = this._interpolatePath(
                        pathPoints,
                        { x: fromObj.x, y: fromObj.y },
                        { x: toObj.x, y: toObj.y },
                        localT,
                        toObj.pathType || "linear"
                    );
                    interp.x = pos.x;
                    interp.y = pos.y;
                } else {
                    // Standard linear interpolation
                    interp.x = fromObj.x + (toObj.x - fromObj.x) * localT;
                    interp.y = fromObj.y + (toObj.y - fromObj.y) * localT;
                }
            }
            result.push(interp);
        }
        return result;
    },

    /* ── Team Templates ─────────────────────────────────────────────── */
    saveTeamTemplate(name, team = "home") {
        if (!name || typeof name !== "string") return false;
        const safeName = this._safeString(name).replace(/[^a-zA-Z0-9._\-\s]/g, "").slice(0, 60).trim();
        if (!safeName) return false;
        try {
            const players = [];
            /* We accept either a project object or rely on caller to pass objects */
            const src = (typeof team === "object" && Array.isArray(team.objects)) ? team.objects : [];
            for (const obj of src) {
                if (obj.type === "player" && obj.team === (typeof team === "string" ? team : "home")) {
                    players.push({ x: obj.x, y: obj.y, label: obj.label, number: obj.number, team: obj.team });
                }
            }
            const template = { name: safeName, team: typeof team === "string" ? team : "home", players, created: Date.now() };
            localStorage.setItem(`tactical-team-template-${safeName}`, JSON.stringify(template));
            return true;
        } catch { return false; }
    },

    loadTeamTemplate(name, team = "home") {
        if (!name) return [];
        const safeName = this._safeString(name).replace(/[^a-zA-Z0-9._\-\s]/g, "").slice(0, 60).trim();
        try {
            const data = localStorage.getItem(`tactical-team-template-${safeName}`);
            if (!data) return [];
            const template = JSON.parse(data);
            if (!Array.isArray(template.players)) return [];
            return template.players.map((p, i) => this.createPlayer(p.x, p.y, team, p.label || "", p.number || i + 1));
        } catch { return []; }
    },

    listTeamTemplates() {
        const templates = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith("tactical-team-template-")) {
                try {
                    const data = JSON.parse(localStorage.getItem(key));
                    templates.push({ name: data.name, team: data.team, playerCount: (data.players || []).length, created: data.created });
                } catch { /* skip */ }
            }
        }
        return templates.sort((a, b) => (b.created || 0) - (a.created || 0));
    },

    deleteTeamTemplate(name) {
        const safeName = this._safeString(name).replace(/[^a-zA-Z0-9._\-\s]/g, "").slice(0, 60).trim();
        try { localStorage.removeItem(`tactical-team-template-${safeName}`); return true; } catch { return false; }
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
    checks.push(["version set", migrated.version === "1.2.0"]);

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

    // 1.1.0 migration: pathPoints, pathType, easing, delay_ms, pause_ms added
    var mp = migrated.objects.find(function(o) { return o.type === "player"; });
    checks.push(["player has pathPoints after migration", Array.isArray(mp.pathPoints)]);
    checks.push(["player has pathType after migration", typeof mp.pathType === "string"]);
    checks.push(["player has easing after migration", typeof mp.easing === "string"]);
    checks.push(["player has delay_ms after migration", typeof mp.delay_ms === "number"]);
    checks.push(["player has pause_ms after migration", typeof mp.pause_ms === "number"]);
    checks.push(["project has animationMode", typeof migrated.animationMode === "string"]);
    checks.push(["project has stepDuration", typeof migrated.stepDuration === "number"]);

    // Validate migrated project
    var vr = TACTICAL_BOARD.validateProject(migrated);
    checks.push(["migrated project passes validation", vr.valid]);

    // Report results
    const failed = checks.filter(([, ok]) => !ok);
    if (failed.length > 0) {
        console.error("[migrateProject test] FAIL:", failed.map(([name]) => name).join(", "));
    } else {
        console.log("[migrateProject test] PASS — all " + checks.length + " checks passed");
    }
})();

// Expose the module for static-browser consumers and ESM-based contract tests.
globalThis.TACTICAL_BOARD = TACTICAL_BOARD;
