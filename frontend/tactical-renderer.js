/* Tactical Board Canvas Renderer — P1.5

   Renders the tactical board on an HTML5 Canvas.
   Handles:
   - Pitch drawing (grass, lines, circles)
   - Player/ball rendering
   - Arrow drawing (solid, dashed, curved)
   - Zone rendering
   - Text annotations
   - Drag & drop interaction
   - Arrow/zone drawing modes
   - Touch event support
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
    drawingMode: null,    // null | 'arrow' | 'zone'
    drawStart: null,      // {x, y} start point for drawing
    drawPreview: null,    // preview object during drawing

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
        this.onChange = null;
        this.drawingMode = null;
        this.drawStart = null;
        this.drawPreview = null;

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
                case "text":   this.drawText(obj); break;
            }
        }

        // Draw preview during drawing mode
        if (this.drawPreview) {
            this._drawPreviewObject(this.drawPreview);
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

        let endAngle;
        if (obj.style === "curved") {
            // Control point perpendicular to midpoint, offset by 30% of line length
            const mx = (start.x + end.x) / 2;
            const my = (start.y + end.y) / 2;
            const dx = end.x - start.x;
            const dy = end.y - start.y;
            const len = Math.sqrt(dx * dx + dy * dy);
            const offset = len * 0.3;
            // Perpendicular direction (rotate 90 degrees)
            const px = -dy / len * offset;
            const py = dx / len * offset;
            ctx.quadraticCurveTo(mx + px, my + py, end.x, end.y);
            // Tangent at t=1 of quadratic bezier: direction from control point to end
            endAngle = Math.atan2(end.y - (my + py), end.x - (mx + px));
        } else {
            ctx.lineTo(end.x, end.y);
            endAngle = Math.atan2(end.y - start.y, end.x - start.x);
        }
        ctx.stroke();

        // Arrowhead
        const headLen = 12;
        ctx.beginPath();
        ctx.moveTo(end.x, end.y);
        ctx.lineTo(end.x - headLen * Math.cos(endAngle - Math.PI / 6), end.y - headLen * Math.sin(endAngle - Math.PI / 6));
        ctx.moveTo(end.x, end.y);
        ctx.lineTo(end.x - headLen * Math.cos(endAngle + Math.PI / 6), end.y - headLen * Math.sin(endAngle + Math.PI / 6));
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

    drawText(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const fontSize = (obj.fontSize || 12) * this.scale;

        ctx.fillStyle = obj.color || "#ffffff";
        ctx.font = `${fontSize}px Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(obj.text || obj.label || "", pos.x, pos.y);
    },

    _drawPreviewObject(preview) {
        const ctx = this.ctx;
        ctx.setLineDash([6, 4]);
        ctx.strokeStyle = "rgba(255,255,255,0.7)";
        ctx.lineWidth = 2;

        if (preview.type === "arrow") {
            const start = this.toCanvas(preview.startX, preview.startY);
            const end = this.toCanvas(preview.endX, preview.endY);
            ctx.beginPath();
            ctx.moveTo(start.x, start.y);
            ctx.lineTo(end.x, end.y);
            ctx.stroke();
            // Arrowhead
            const angle = Math.atan2(end.y - start.y, end.x - start.x);
            const headLen = 10;
            ctx.beginPath();
            ctx.moveTo(end.x, end.y);
            ctx.lineTo(end.x - headLen * Math.cos(angle - Math.PI / 6), end.y - headLen * Math.sin(angle - Math.PI / 6));
            ctx.moveTo(end.x, end.y);
            ctx.lineTo(end.x - headLen * Math.cos(angle + Math.PI / 6), end.y - headLen * Math.sin(angle + Math.PI / 6));
            ctx.stroke();
        } else if (preview.type === "zone") {
            const tl = this.toCanvas(preview.x, preview.y);
            const w = preview.width * this.scale;
            const h = preview.height * this.scale;
            ctx.fillStyle = "rgba(255,255,255,0.1)";
            ctx.fillRect(tl.x, tl.y, w, h);
            ctx.strokeRect(tl.x, tl.y, w, h);
        }

        ctx.setLineDash([]);
    },

    drawSelection(obj) {
        const ctx = this.ctx;

        if (obj.type === "arrow") {
            // Highlight arrow midpoint
            const start = this.toCanvas(obj.startX, obj.startY);
            const end = this.toCanvas(obj.endX, obj.endY);
            const mx = (start.x + end.x) / 2;
            const my = (start.y + end.y) / 2;
            const r = 8;
            ctx.strokeStyle = "#ffd700";
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.arc(mx, my, r, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
        } else if (obj.type === "zone") {
            const tl = this.toCanvas(obj.x, obj.y);
            const w = obj.width * this.scale;
            const h = obj.height * this.scale;
            ctx.strokeStyle = "#ffd700";
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.strokeRect(tl.x - 3, tl.y - 3, w + 6, h + 6);
            ctx.setLineDash([]);
        } else {
            const pos = this.toCanvas(obj.x, obj.y);
            const r = (obj.radius || 3) * this.scale + 4;
            ctx.strokeStyle = "#ffd700";
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
        }
    },

    /* ── Event handling ──────────────────────────────────────────────── */
    bindEvents() {
        if (!this.canvas) return;

        this.canvas.addEventListener("mousedown", (e) => this.onMouseDown(e));
        this.canvas.addEventListener("mousemove", (e) => this.onMouseMove(e));
        this.canvas.addEventListener("mouseup", (e) => this.onMouseUp(e));
        this.canvas.addEventListener("mouseleave", (e) => this.onMouseUp(e));

        // Touch support
        this.canvas.addEventListener("touchstart", (e) => {
            e.preventDefault();
            if (e.touches.length > 0) {
                const touch = e.touches[0];
                this.onMouseDown({ clientX: touch.clientX, clientY: touch.clientY });
            }
        }, { passive: false });
        this.canvas.addEventListener("touchmove", (e) => {
            e.preventDefault();
            if (e.touches.length > 0) {
                const touch = e.touches[0];
                this.onMouseMove({ clientX: touch.clientX, clientY: touch.clientY });
            }
        }, { passive: false });
        this.canvas.addEventListener("touchend", (e) => {
            e.preventDefault();
            this.onMouseUp();
        }, { passive: false });
        this.canvas.addEventListener("touchcancel", (e) => {
            e.preventDefault();
            this.onMouseUp();
        }, { passive: false });

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

        // Drawing mode: start drawing arrow or zone
        if (this.drawingMode === "arrow" || this.drawingMode === "zone") {
            this.drawStart = { x, y };
            this.selectedObject = null;
            this.render();
            return;
        }

        // Text mode: prompt and place text
        if (this.drawingMode === "text") {
            const text = prompt("Enter annotation text:");
            if (text && text.trim()) {
                this.pushUndo();
                const textObj = TACTICAL_BOARD.createText(x, y, text.trim());
                this.project.objects.push(textObj);
                this.render();
            }
            return;
        }

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
            } else if (obj.type === "arrow") {
                // Hit test: distance from point to line segment < 3 units
                const dist = this._pointToSegmentDist(x, y, obj.startX, obj.startY, obj.endX, obj.endY);
                if (dist < 3) {
                    found = obj;
                    break;
                }
            } else if (obj.type === "zone") {
                // Hit test: point inside rectangle bounds
                if (x >= obj.x && x <= obj.x + obj.width &&
                    y >= obj.y && y <= obj.y + obj.height) {
                    found = obj;
                    break;
                }
            }
        }

        this.selectedObject = found;
        if (found) {
            this.isDragging = true;
            if (found.type === "arrow") {
                this.dragOffset = {
                    x: x - found.startX,
                    y: y - found.startY,
                };
            } else {
                this.dragOffset = { x: x - found.x, y: y - found.y };
            }
            this.pushUndo();
        }
        this.render();
    },

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const { x, y } = this.fromCanvas(cx, cy);

        // Drawing mode: update preview
        if (this.drawStart) {
            if (this.drawingMode === "arrow") {
                this.drawPreview = {
                    type: "arrow",
                    startX: this.drawStart.x,
                    startY: this.drawStart.y,
                    endX: x,
                    endY: y,
                };
            } else if (this.drawingMode === "zone") {
                const zx = Math.min(this.drawStart.x, x);
                const zy = Math.min(this.drawStart.y, y);
                const zw = Math.abs(x - this.drawStart.x);
                const zh = Math.abs(y - this.drawStart.y);
                this.drawPreview = {
                    type: "zone",
                    x: zx, y: zy,
                    width: zw, height: zh,
                };
            }
            this.render();
            return;
        }

        if (!this.isDragging || !this.selectedObject) return;

        if (this.selectedObject.type === "arrow") {
            // Move entire arrow
            const newStartX = Math.max(0, Math.min(100, x - this.dragOffset.x));
            const newStartY = Math.max(0, Math.min(100, y - this.dragOffset.y));
            const dx = newStartX - this.selectedObject.startX;
            const dy = newStartY - this.selectedObject.startY;
            this.selectedObject.startX = newStartX;
            this.selectedObject.startY = newStartY;
            this.selectedObject.endX = Math.max(0, Math.min(100, this.selectedObject.endX + dx));
            this.selectedObject.endY = Math.max(0, Math.min(100, this.selectedObject.endY + dy));
        } else {
            this.selectedObject.x = Math.max(0, Math.min(100, x - this.dragOffset.x));
            this.selectedObject.y = Math.max(0, Math.min(100, y - this.dragOffset.y));
        }
        this.render();
    },

    onMouseUp() {
        // Drawing mode: create the drawn object
        if (this.drawStart && this.drawPreview) {
            this.pushUndo();
            if (this.drawingMode === "arrow") {
                const arrow = TACTICAL_BOARD.createArrow(
                    this.drawPreview.startX, this.drawPreview.startY,
                    this.drawPreview.endX, this.drawPreview.endY,
                    "solid"
                );
                this.project.objects.push(arrow);
            } else if (this.drawingMode === "zone") {
                const zone = TACTICAL_BOARD.createZone(
                    this.drawPreview.x, this.drawPreview.y,
                    this.drawPreview.width, this.drawPreview.height
                );
                this.project.objects.push(zone);
            }
            this.drawStart = null;
            this.drawPreview = null;
            this.render();
        }
        this.isDragging = false;
        if (this.onChange) this.onChange();
    },

    /* ── Drawing mode ────────────────────────────────────────────────── */
    setDrawingMode(mode) {
        this.drawingMode = mode; // null | 'arrow' | 'zone' | 'text'
        this.drawStart = null;
        this.drawPreview = null;
        // Update cursor
        if (this.canvas) {
            if (mode === "text") this.canvas.style.cursor = "text";
            else if (mode === "arrow" || mode === "zone") this.canvas.style.cursor = "crosshair";
            else this.canvas.style.cursor = "default";
        }
        this.render();
    },

    /* ── Hit testing helpers ─────────────────────────────────────────── */
    _pointToSegmentDist(px, py, ax, ay, bx, by) {
        const dx = bx - ax;
        const dy = by - ay;
        const lenSq = dx * dx + dy * dy;
        if (lenSq === 0) return Math.sqrt((px - ax) * (px - ax) + (py - ay) * (py - ay));
        let t = ((px - ax) * dx + (py - ay) * dy) / lenSq;
        t = Math.max(0, Math.min(1, t));
        const projX = ax + t * dx;
        const projY = ay + t * dy;
        return Math.sqrt((px - projX) * (px - projX) + (py - projY) * (py - projY));
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
        if (this.onChange) this.onChange();
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
        loop: false,
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
            if (this.animationState.loop) {
                this.animationState.startTime = performance.now();
                this.animationState.animationId = requestAnimationFrame(() => this._animate());
            } else {
                this.animationState.isPlaying = false;
            }
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

    toggleLoop() {
        this.animationState.loop = !this.animationState.loop;
        return this.animationState.loop;
    },

    exportPNG(filename) {
        if (!this.canvas) return;
        // Temporarily remove selection highlight for clean export
        const savedSelection = this.selectedObject;
        this.selectedObject = null;
        this.render();
        const dataUrl = this.canvas.toDataURL("image/png");
        this.selectedObject = savedSelection;
        this.render();

        const link = document.createElement("a");
        link.download = filename || "tactical-board.png";
        link.href = dataUrl;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },

    /* ── WebM Animation Export ────────────────────────────────────────── */
    exportWebM(filename) {
        if (!this.canvas) return;

        // Feature detection
        if (typeof MediaRecorder === "undefined" || typeof this.canvas.captureStream !== "function") {
            alert("\u25C6 WebM export is not supported in this browser.\n\nMediaRecorder or canvas.captureStream() is unavailable.\nPlease use a Chromium-based browser (Chrome, Edge, Brave).");
            return;
        }

        if (!this.project || !this.project.frames || this.project.frames.length < 2) {
            alert("\u25C6 No animation frames to export.\n\nPlease add at least two keyframes before exporting.");
            return;
        }

        const mimeType = "video/webm";
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            alert("\u25C6 video/webm encoding is not supported in this browser.");
            return;
        }

        // Save loop state and force single-play for recording
        const savedLoop = this.animationState.loop;
        this.animationState.loop = false;

        // Set up MediaRecorder
        const stream = this.canvas.captureStream(30);
        const recorder = new MediaRecorder(stream, { mimeType });
        const chunks = [];

        recorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstop = () => {
            // Restore loop state
            this.animationState.loop = savedLoop;

            // Build blob and trigger download
            const blob = new Blob(chunks, { type: mimeType });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.download = filename || "tactical-animation.webm";
            link.href = url;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            setTimeout(() => URL.revokeObjectURL(url), 5000);
        };

        // Save the original _animate so we can restore after recording
        const self = this;
        const originalAnimate = this._animate.bind(this);

        // Override _animate to detect when animation finishes (non-loop)
        this._animate = function () {
            originalAnimate();
            // When the animation ends naturally (isPlaying becomes false),
            // stop the recorder. This fires only on the final frame transition.
            if (!self.animationState.isPlaying && recorder.state === "recording") {
                recorder.stop();
            }
        };

        // Start recording, then play
        recorder.start();
        this.play();

        // Restore original _animate after recording stops
        recorder.addEventListener("stop", () => {
            this._animate = originalAnimate;
        });
    },
};
