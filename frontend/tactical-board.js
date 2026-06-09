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
            style,  // "solid" | "dashed" | "curved"
            color: "#ffffff",
            width: 2,
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
    saveProject(project) {
        try {
            project.updated_at = new Date().toISOString();
            const key = `tactical-board-${project.board_id}`;
            localStorage.setItem(key, JSON.stringify(project));
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
            return data ? JSON.parse(data) : null;
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
                    if (data && data.board_id) {
                        projects.push({
                            board_id: data.board_id,
                            title: data.title,
                            updated_at: data.updated_at,
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
            const project = JSON.parse(jsonString);
            if (!project.board_id || !project.version) {
                throw new Error("Invalid project: missing board_id or version");
            }
            return project;
        } catch (e) {
            console.warn("Failed to import tactical board project:", e);
            return null;
        }
    },
};
