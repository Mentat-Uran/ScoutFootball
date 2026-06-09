/* Tactical Board Canvas Renderer — P1.5

   Renders the tactical board on an HTML5 Canvas.
   Handles:
   - Pitch drawing (grass, lines, circles)
   - Player/ball rendering
   - Arrow drawing
   - Zone rendering
   - Drag & drop interaction
   - Undo/redo stack
*/

const TacticalRenderer = {
    canvas: null,
    ctx: null,
    project: null,
    selectedObject: null,
    isDragging: false,
    dragOffset: { x: 0, y: 0 },
    undoStack: [],
    redoStack: [],
    scale: 1,
    offsetX: 0,
    offsetY: 0,

    /* ── Initialize ─────────────────────────────────────────────────── */
    init(canvasId, project) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error("Canvas not found:", canvasId);
            return;
        }
        this.ctx = this.canvas.getContext("2d");
        this.project = project;
        this.undoStack = [];
        this.redoStack = [];

        this.resize();
        this.bindEvents();
        this.render();
    },

    resize() {
        if (!this.canvas) return;
        const parent = this.canvas.parentElement;
        if (!parent) return;

        const rect = parent.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + "px";
        this.canvas.style.height = rect.height + "px";

        this.ctx.scale(dpr, dpr);
        this.scale = Math.min(rect.width / 110, rect.height / 78);
        this.offsetX = (rect.width - 110 * this.scale) / 2;
        this.offsetY = (rect.height - 78 * this.scale) / 2;

        this.render();
    },

    /* ── Coordinate conversion ──────────────────────────────────────── */
    toCanvas(x, y) {
        return {
            x: this.offsetX + (x + 5) * this.scale,
            y: this.offsetY + (y + 5) * this.scale,
        };
    },

    fromCanvas(cx, cy) {
        return {
            x: (cx - this.offsetX) / this.scale - 5,
            y: (cy - this.offsetY) / this.scale - 5,
        };
    },

    /* ── Render ─────────────────────────────────────────────────────── */
    render() {
        if (!this.ctx || !this.project) return;

        const ctx = this.ctx;
        const w = this.canvas.width / (window.devicePixelRatio || 1);
        const h = this.canvas.height / (window.devicePixelRatio || 1);

        // Clear
        ctx.clearRect(0, 0, w, h);

        // Draw pitch
        this.drawPitch();

        // Draw objects
        for (const obj of this.project.objects) {
            if (!obj.visible) continue;
            switch (obj.type) {
                case "player": this.drawPlayer(obj); break;
                case "ball":   this.drawBall(obj); break;
                case "arrow":  this.drawArrow(obj); break;
                case "zone":   this.drawZone(obj); break;
            }
        }

        // Draw selection highlight
        if (this.selectedObject) {
            this.drawSelection(this.selectedObject);
        }
    },

    drawPitch() {
        const ctx = this.ctx;
        const tl = this.toCanvas(0, 0);
        const br = this.toCanvas(100, 100);
        const pw = br.x - tl.x;
        const ph = br.y - tl.y;

        // Grass
        ctx.fillStyle = "#1a472a";
        ctx.fillRect(tl.x, tl.y, pw, ph);

        // Lines
        ctx.strokeStyle = "rgba(255,255,255,0.6)";
        ctx.lineWidth = 1.5;

        // Border
        ctx.strokeRect(tl.x, tl.y, pw, ph);

        // Center line
        const center = this.toCanvas(50, 50);
        ctx.beginPath();
        ctx.moveTo(center.x, tl.y);
        ctx.lineTo(center.x, br.y);
        ctx.stroke();

        // Center circle
        ctx.beginPath();
        ctx.arc(center.x, center.y, 10 * this.scale, 0, Math.PI * 2);
        ctx.stroke();

        // Center dot
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.beginPath();
        ctx.arc(center.x, center.y, 2, 0, Math.PI * 2);
        ctx.fill();

        // Penalty areas
        const paW = 16.5 / 105 * 100;
        const paH = 40.32 / 68 * 100;
        const paY = (100 - paH) / 2;

        // Left penalty area
        const lpa = this.toCanvas(0, paY);
        ctx.strokeRect(lpa.x, lpa.y, paW * this.scale, paH * this.scale);

        // Right penalty area
        const rpa = this.toCanvas(100 - paW, paY);
        ctx.strokeRect(rpa.x, rpa.y, paW * this.scale, paH * this.scale);

        // Goal areas
        const gaW = 5.5 / 105 * 100;
        const gaH = 18.32 / 68 * 100;
        const gaY = (100 - gaH) / 2;

        // Left goal area
        const lga = this.toCanvas(0, gaY);
        ctx.strokeRect(lga.x, lga.y, gaW * this.scale, gaH * this.scale);

        // Right goal area
        const rga = this.toCanvas(100 - gaW, gaY);
        ctx.strokeRect(rga.x, rga.y, gaW * this.scale, gaH * this.scale);

        // Goals
        const goalH = 7.32 / 68 * 100;
        const goalY = (100 - goalH) / 2;
        const goalW = 2;

        ctx.fillStyle = "rgba(255,255,255,0.3)";
        const lg = this.toCanvas(-goalW, goalY);
        ctx.fillRect(lg.x, lg.y, goalW * this.scale, goalH * this.scale);

        const rg = this.toCanvas(100, goalY);
        ctx.fillRect(rg.x, rg.y, goalW * this.scale, goalH * this.scale);
    },

    drawPlayer(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const r = obj.radius * this.scale;

        // Circle
        ctx.fillStyle = obj.color;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
        ctx.fill();

        // Border
        ctx.strokeStyle = "rgba(0,0,0,0.3)";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Label
        if (obj.label || obj.number) {
            ctx.fillStyle = "#fff";
            ctx.font = `bold ${Math.max(10, r * 0.8)}px Inter, sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(obj.number || obj.label, pos.x, pos.y);
        }
    },

    drawBall(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const r = obj.radius * this.scale;

        ctx.fillStyle = obj.color;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = "rgba(0,0,0,0.3)";
        ctx.lineWidth = 1;
        ctx.stroke();
    },

    drawArrow(obj) {
        const ctx = this.ctx;
        const start = this.toCanvas(obj.startX, obj.startY);
        const end = this.toCanvas(obj.endX, obj.endY);

        ctx.strokeStyle = obj.color;
        ctx.lineWidth = obj.width;
        ctx.setLineDash(obj.style === "dashed" ? [8, 4] : []);

        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();

        // Arrowhead
        const angle = Math.atan2(end.y - start.y, end.x - start.x);
        const headLen = 12;
        ctx.beginPath();
        ctx.moveTo(end.x, end.y);
        ctx.lineTo(end.x - headLen * Math.cos(angle - Math.PI / 6), end.y - headLen * Math.sin(angle - Math.PI / 6));
        ctx.moveTo(end.x, end.y);
        ctx.lineTo(end.x - headLen * Math.cos(angle + Math.PI / 6), end.y - headLen * Math.sin(angle + Math.PI / 6));
        ctx.stroke();

        ctx.setLineDash([]);
    },

    drawZone(obj) {
        const ctx = this.ctx;
        const tl = this.toCanvas(obj.x, obj.y);
        const w = obj.width * this.scale;
        const h = obj.height * this.scale;

        ctx.fillStyle = obj.color;
        ctx.fillRect(tl.x, tl.y, w, h);

        ctx.strokeStyle = obj.borderColor;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(tl.x, tl.y, w, h);

        if (obj.label) {
            ctx.fillStyle = "rgba(255,255,255,0.7)";
            ctx.font = `bold ${Math.max(10, 12 * this.scale / 3)}px Inter, sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(obj.label, tl.x + w / 2, tl.y + h / 2);
        }
    },

    drawSelection(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const r = (obj.radius || 3) * this.scale + 4;

        ctx.strokeStyle = "#ffd700";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
    },

    /* ── Event handling ──────────────────────────────────────────────── */
    bindEvents() {
        if (!this.canvas) return;

        this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
        this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
        this.canvas.addEventListener("mouseup", () => this.onMouseUp());
        this.canvas.addEventListener("mouseleave", () => this.onMouseUp());

        // Keyboard shortcuts
        document.addEventListener("keydown", (e) => {
            if (e.ctrlKey && e.key === "z") {
                e.preventDefault();
                this.undo();
            } else if (e.ctrlKey && e.key === "y") {
                e.preventDefault();
                this.redo();
            } else if (e.key === "Delete" && this.selectedObject) {
                this.deleteSelected();
            }
        });
    },

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const { x, y } = this.fromCanvas(cx, cy);

        // Find object under cursor
        let found = null;
        for (const obj of [...this.project.objects].reverse()) {
            if (!obj.visible || obj.locked) continue;
            if (obj.type === "player" || obj.type === "ball") {
                const dx = x - obj.x;
                const dy = y - obj.y;
                if (dx * dx + dy * dy < (obj.radius + 2) * (obj.radius + 2)) {
                    found = obj;
                    break;
                }
            }
        }

        this.selectedObject = found;
        if (found) {
            this.isDragging = true;
            this.dragOffset = { x: x - found.x, y: y - found.y };
            this.pushUndo();
        }
        this.render();
    },

    onMouseMove(e) {
        if (!this.isDragging || !this.selectedObject) return;

        const rect = this.canvas.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const { x, y } = this.fromCanvas(cx, cy);

        this.selectedObject.x = Math.max(0, Math.min(100, x - this.dragOffset.x));
        this.selectedObject.y = Math.max(0, Math.min(100, y - this.dragOffset.y));
        this.render();
    },

    onMouseUp() {
        this.isDragging = false;
    },

    /* ── Undo/Redo ──────────────────────────────────────────────────── */
    pushUndo() {
        this.undoStack.push(JSON.stringify(this.project.objects));
        this.redoStack = [];
        if (this.undoStack.length > 50) this.undoStack.shift();
    },

    undo() {
        if (this.undoStack.length === 0) return;
        this.redoStack.push(JSON.stringify(this.project.objects));
        this.project.objects = JSON.parse(this.undoStack.pop());
        this.selectedObject = null;
        this.render();
    },

    redo() {
        if (this.redoStack.length === 0) return;
        this.undoStack.push(JSON.stringify(this.project.objects));
        this.project.objects = JSON.parse(this.redoStack.pop());
        this.selectedObject = null;
        this.render();
    },

    deleteSelected() {
        if (!this.selectedObject) return;
        this.pushUndo();
        this.project.objects = this.project.objects.filter((o) => o.id !== this.selectedObject.id);
        this.selectedObject = null;
        this.render();
    },

    /* ── Public API ─────────────────────────────────────────────────── */
    loadFormation(formationName, team = "home") {
        this.pushUndo();
        const newObjects = TACTICAL_BOARD.generateFormation(formationName, team);
        // Remove existing players of this team
        this.project.objects = this.project.objects.filter((o) => !(o.type === "player" && o.team === team));
        this.project.objects.push(...newObjects);
        this.render();
    },

    clearBoard() {
        this.pushUndo();
        this.project.objects = [];
        this.selectedObject = null;
        this.render();
    },

    getProject() {
        this.project.updated_at = new Date().toISOString();
        return this.project;
    },

    /* ── Animation Playback ─────────────────────────────────────────── */
    animationState: {
        isPlaying: false,
        currentFrame: 0,
        animationId: null,
        startTime: 0,
    },

    play() {
        if (!this.project || !this.project.frames || this.project.frames.length < 2) return;
        this.animationState.isPlaying = true;
        this.animationState.currentFrame = 0;
        this.animationState.startTime = performance.now();
        this._animate();
    },

    stop() {
        this.animationState.isPlaying = false;
        if (this.animationState.animationId) {
            cancelAnimationFrame(this.animationState.animationId);
            this.animationState.animationId = null;
        }
        // Restore current frame
        if (this.project && this.project.frames) {
            TACTICAL_BOARD.loadFrame(this.project, this.animationState.currentFrame, this);
        }
    },

    _animate() {
        if (!this.animationState.isPlaying) return;

        const frames = this.project.frames;
        const elapsed = performance.now() - this.animationState.startTime;

        // Find current frame based on elapsed time
        let totalDuration = 0;
        let fromFrame = 0;
        let toFrame = 0;
        let frameElapsed = 0;

        for (let i = 0; i < frames.length; i++) {
            const dur = frames[i].duration_ms || 3000;
            if (elapsed < totalDuration + dur) {
                fromFrame = i;
                toFrame = (i + 1) % frames.length;
                frameElapsed = elapsed - totalDuration;
                break;
            }
            totalDuration += dur;
        }

        const fromDur = frames[fromFrame].duration_ms || 3000;
        const t = Math.min(1, frameElapsed / fromDur);

        // Interpolate
        const fromObjs = frames[fromFrame].objects || [];
        const toObjs = frames[toFrame].objects || [];
        this.project.objects = TACTICAL_BOARD.interpolateObjects(fromObjs, toObjs, t);
        this.render();

        // Check if animation is complete
        const totalAnimDuration = frames.reduce((sum, f) => sum + (f.duration_ms || 3000), 0);
        if (elapsed >= totalAnimDuration) {
            this.animationState.isPlaying = false;
            return;
        }

        this.animationState.animationId = requestAnimationFrame(() => this._animate());
    },

    goToFrame(index) {
        if (!this.project || !this.project.frames) return;
        if (index < 0 || index >= this.project.frames.length) return;
        this.animationState.currentFrame = index;
        TACTICAL_BOARD.loadFrame(this.project, index, this);
    },

    nextFrame() {
        if (!this.project || !this.project.frames) return;
        const next = (this.animationState.currentFrame + 1) % this.project.frames.length;
        this.goToFrame(next);
    },

    prevFrame() {
        if (!this.project || !this.project.frames) return;
        const prev = (this.animationState.currentFrame - 1 + this.project.frames.length) % this.project.frames.length;
        this.goToFrame(prev);
    },
};
