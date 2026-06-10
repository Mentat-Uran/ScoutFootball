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
    drawingMode: null,    // null | 'arrow' | 'zone' | 'text'
    drawStart: null,      // {x, y} start point for drawing
    drawPreview: null,    // preview object during drawing
    showGrid: false,
    snapToGrid: false,
    ghostOpacity: 0.2,
    showRatings: false,
    _penPoints: [],       // points collected during pen drawing
    _hoverCardEl: null,   // DOM element for player hover card
    _timelineEl: null,    // DOM element for timeline scrubber
    _overlapIndex: 0,     // index for cycling through overlapping objects
    _lastClickPos: null,  // last click position for overlap detection
    _presentationMode: false, // presentation mode flag

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
        this._keydownHandler = null;
        this._isRecording = false;
        this._penPoints = [];
        this._initHoverCard();
        this._initTimeline();

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

        // Draw grid overlay
        if (this.showGrid) this.drawGrid();

        // Draw ghost silhouettes (previous/next frame positions in animation mode)
        this._drawGhosts();

        // Draw objects
        for (const obj of this.project.objects) {
            if (!obj.visible) continue;
            switch (obj.type) {
                case "player": this.drawPlayer(obj); break;
                case "ball":   this.drawBall(obj); break;
                case "arrow":  this.drawArrow(obj); break;
                case "zone":   this.drawZone(obj); break;
                case "text":   this.drawText(obj); break;
                case "path":   this.drawPath(obj); break;
                case "rect":   this.drawRect(obj); break;
                case "ellipse": this.drawEllipse(obj); break;
                case "bench":  this.drawBench(obj); break;
                case "cone":   this.drawCone(obj); break;
                case "marker": this.drawMarker(obj); break;
                case "pole":   this.drawPole(obj); break;
                case "ladder": this.drawLadder(obj); break;
                case "minigoal": this.drawMiniGoal(obj); break;
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

        // Update timeline UI
        this.updateTimeline();
    },

    drawPitch() {
        const pt = (this.project && this.project.pitch_type) || "11v11";
        switch (pt) {
            case "half-field": this._drawHalfFieldPitch(); break;
            case "training":   this._drawTrainingPitch(); break;
            case "blank":      this._drawBlankCanvas(); break;
            case "7v7":        this._draw7v7Pitch(); break;
            case "5v5":        this._draw5v5Pitch(); break;
            default:           this._drawFullPitch(); break;
        }
    },

    _drawFullPitch() {
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

    _draw7v7Pitch() {
        const ctx = this.ctx;
        const tl = this.toCanvas(0, 0);
        const br = this.toCanvas(100, 100);
        const pw = br.x - tl.x;
        const ph = br.y - tl.y;

        ctx.fillStyle = "#1a472a";
        ctx.fillRect(tl.x, tl.y, pw, ph);

        ctx.strokeStyle = "rgba(255,255,255,0.6)";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(tl.x, tl.y, pw, ph);

        // Center line
        const center = this.toCanvas(50, 50);
        ctx.beginPath();
        ctx.moveTo(center.x, tl.y);
        ctx.lineTo(center.x, br.y);
        ctx.stroke();

        // Center circle (smaller)
        ctx.beginPath();
        ctx.arc(center.x, center.y, 8 * this.scale, 0, Math.PI * 2);
        ctx.stroke();

        // Center dot
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.beginPath();
        ctx.arc(center.x, center.y, 2, 0, Math.PI * 2);
        ctx.fill();

        // Penalty areas (proportional for 7v7)
        const paW = 13 / 105 * 100;
        const paH = 32 / 68 * 100;
        const paY = (100 - paH) / 2;

        const lpa = this.toCanvas(0, paY);
        ctx.strokeRect(lpa.x, lpa.y, paW * this.scale, paH * this.scale);

        const rpa = this.toCanvas(100 - paW, paY);
        ctx.strokeRect(rpa.x, rpa.y, paW * this.scale, paH * this.scale);

        // Goal areas
        const gaW = 4.5 / 105 * 100;
        const gaH = 16 / 68 * 100;
        const gaY = (100 - gaH) / 2;

        const lga = this.toCanvas(0, gaY);
        ctx.strokeRect(lga.x, lga.y, gaW * this.scale, gaH * this.scale);

        const rga = this.toCanvas(100 - gaW, gaY);
        ctx.strokeRect(rga.x, rga.y, gaW * this.scale, gaH * this.scale);

        // Goals (smaller for 7v7)
        const goalH = 5 / 68 * 100;
        const goalY = (100 - goalH) / 2;
        const goalW = 2;

        ctx.fillStyle = "rgba(255,255,255,0.3)";
        const lg = this.toCanvas(-goalW, goalY);
        ctx.fillRect(lg.x, lg.y, goalW * this.scale, goalH * this.scale);

        const rg = this.toCanvas(100, goalY);
        ctx.fillRect(rg.x, rg.y, goalW * this.scale, goalH * this.scale);
    },

    _draw5v5Pitch() {
        const ctx = this.ctx;
        const tl = this.toCanvas(0, 0);
        const br = this.toCanvas(100, 100);
        const pw = br.x - tl.x;
        const ph = br.y - tl.y;

        ctx.fillStyle = "#1a472a";
        ctx.fillRect(tl.x, tl.y, pw, ph);

        ctx.strokeStyle = "rgba(255,255,255,0.6)";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(tl.x, tl.y, pw, ph);

        // Center line
        const center = this.toCanvas(50, 50);
        ctx.beginPath();
        ctx.moveTo(center.x, tl.y);
        ctx.lineTo(center.x, br.y);
        ctx.stroke();

        // Center circle (smaller)
        ctx.beginPath();
        ctx.arc(center.x, center.y, 6 * this.scale, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.beginPath();
        ctx.arc(center.x, center.y, 2, 0, Math.PI * 2);
        ctx.fill();

        // Penalty areas
        const paW = 10 / 105 * 100;
        const paH = 28 / 68 * 100;
        const paY = (100 - paH) / 2;

        const lpa = this.toCanvas(0, paY);
        ctx.strokeRect(lpa.x, lpa.y, paW * this.scale, paH * this.scale);

        const rpa = this.toCanvas(100 - paW, paY);
        ctx.strokeRect(rpa.x, rpa.y, paW * this.scale, paH * this.scale);

        // Goals (small futsal goals)
        const goalH = 3 / 68 * 100;
        const goalY = (100 - goalH) / 2;
        const goalW = 2;

        ctx.fillStyle = "rgba(255,255,255,0.3)";
        const lg = this.toCanvas(-goalW, goalY);
        ctx.fillRect(lg.x, lg.y, goalW * this.scale, goalH * this.scale);

        const rg = this.toCanvas(100, goalY);
        ctx.fillRect(rg.x, rg.y, goalW * this.scale, goalH * this.scale);
    },

    _drawHalfFieldPitch() {
        const ctx = this.ctx;
        const tl = this.toCanvas(50, 0);
        const br = this.toCanvas(100, 100);
        const pw = br.x - tl.x;
        const ph = br.y - tl.y;

        // Grass
        ctx.fillStyle = "#1a472a";
        ctx.fillRect(tl.x, tl.y, pw, ph);

        ctx.strokeStyle = "rgba(255,255,255,0.6)";
        ctx.lineWidth = 1.5;

        // Border
        ctx.strokeRect(tl.x, tl.y, pw, ph);

        // Center line (at x=50)
        ctx.beginPath();
        ctx.moveTo(tl.x, tl.y);
        ctx.lineTo(tl.x, br.y);
        ctx.stroke();

        // Center arc (semicircle)
        const center = this.toCanvas(50, 50);
        ctx.beginPath();
        ctx.arc(center.x, center.y, 10 * this.scale, -Math.PI / 2, Math.PI / 2);
        ctx.stroke();

        // Center dot
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.beginPath();
        ctx.arc(center.x, center.y, 2, 0, Math.PI * 2);
        ctx.fill();

        // Penalty area (right side only)
        const paW = 16.5 / 105 * 100;
        const paH = 40.32 / 68 * 100;
        const paY = (100 - paH) / 2;

        const rpa = this.toCanvas(100 - paW, paY);
        ctx.strokeRect(rpa.x, rpa.y, paW * this.scale, paH * this.scale);

        // Penalty spot
        const pSpot = this.toCanvas(100 - 11 / 105 * 100, 50);
        ctx.beginPath();
        ctx.arc(pSpot.x, pSpot.y, 2, 0, Math.PI * 2);
        ctx.fill();

        // Penalty arc
        const paArcCenter = this.toCanvas(100 - 11 / 105 * 100, 50);
        ctx.beginPath();
        ctx.arc(paArcCenter.x, paArcCenter.y, 9.15 / 68 * 100 * this.scale, 0.7 * Math.PI, 1.3 * Math.PI);
        ctx.stroke();

        // Goal area (right side)
        const gaW = 5.5 / 105 * 100;
        const gaH = 18.32 / 68 * 100;
        const gaY = (100 - gaH) / 2;

        const rga = this.toCanvas(100 - gaW, gaY);
        ctx.strokeRect(rga.x, rga.y, gaW * this.scale, gaH * this.scale);

        // Goal (right side)
        const goalH = 7.32 / 68 * 100;
        const goalY = (100 - goalH) / 2;
        const goalW = 2;

        ctx.fillStyle = "rgba(255,255,255,0.3)";
        const rg = this.toCanvas(100, goalY);
        ctx.fillRect(rg.x, rg.y, goalW * this.scale, goalH * this.scale);
    },

    _drawTrainingPitch() {
        const ctx = this.ctx;
        const tl = this.toCanvas(0, 0);
        const br = this.toCanvas(100, 100);
        const pw = br.x - tl.x;
        const ph = br.y - tl.y;

        // Grass
        ctx.fillStyle = "#1a472a";
        ctx.fillRect(tl.x, tl.y, pw, ph);

        ctx.strokeStyle = "rgba(255,255,255,0.6)";
        ctx.lineWidth = 1.5;

        // Border only
        ctx.strokeRect(tl.x, tl.y, pw, ph);

        // Center line
        const center = this.toCanvas(50, 50);
        ctx.beginPath();
        ctx.moveTo(center.x, tl.y);
        ctx.lineTo(center.x, br.y);
        ctx.stroke();
    },

    _drawBlankCanvas() {
        // White background, no pitch markings
        const ctx = this.ctx;
        const w = this.canvas.width / (window.devicePixelRatio || 1);
        const h = this.canvas.height / (window.devicePixelRatio || 1);
        ctx.fillStyle = "#0e1525";
        ctx.fillRect(0, 0, w, h);
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

        // Rating badge
        if (this.showRatings && obj.rating != null) {
            const rating = Number(obj.rating);
            const badgeR = Math.max(7, r * 0.45);
            const bx = pos.x + r * 0.7;
            const by = pos.y - r * 0.7;
            const badgeColor = rating > 70 ? "#57d68d" : rating >= 50 ? "#f0c040" : "#ff6b6b";
            ctx.fillStyle = badgeColor;
            ctx.beginPath();
            ctx.arc(bx, by, badgeR, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = "rgba(0,0,0,0.4)";
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.fillStyle = "#000";
            ctx.font = `bold ${Math.max(7, badgeR * 0.9)}px Inter, sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(Math.round(rating), bx, by);
        }
    },

    drawBench(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const r = (obj.radius || 2) * this.scale;

        // Smaller circle with dashed border
        ctx.fillStyle = obj.color;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = "rgba(255,255,255,0.5)";
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        if (obj.label || obj.number) {
            ctx.fillStyle = "#fff";
            ctx.font = `bold ${Math.max(8, r * 0.7)}px Inter, sans-serif`;
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
        if (obj.startX === obj.endX && obj.startY === obj.endY) return;
        const ctx = this.ctx;
        const start = this.toCanvas(obj.startX, obj.startY);
        const end = this.toCanvas(obj.endX, obj.endY);

        ctx.strokeStyle = obj.color;
        ctx.lineWidth = obj.width || 2;

        // Set line dash pattern based on style
        switch (obj.style) {
            case "dashed":
                ctx.setLineDash([8, 4]);
                break;
            case "dotted":
                ctx.setLineDash([2, 4]);
                break;
            case "run":
                // Wavy dashed for runs
                ctx.setLineDash([6, 3, 2, 3]);
                break;
            case "pass":
                // Solid thin
                ctx.setLineDash([]);
                ctx.lineWidth = Math.max(1, (obj.width || 2) * 0.7);
                break;
            case "shot":
                // Thick solid
                ctx.setLineDash([]);
                ctx.lineWidth = (obj.width || 2) * 1.8;
                break;
            case "dribble":
                // Small dots
                ctx.setLineDash([1.5, 5]);
                break;
            default: // solid, curved
                ctx.setLineDash([]);
                break;
        }

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

    /* ── Grid ──────────────────────────────────────────────────────── */
    drawGrid() {
        const ctx = this.ctx;
        const tl = this.toCanvas(0, 0);
        const br = this.toCanvas(100, 100);
        ctx.strokeStyle = "rgba(255,255,255,0.1)";
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 4]);
        for (let i = 0; i <= 100; i += 10) {
            const p1 = this.toCanvas(i, 0);
            const p2 = this.toCanvas(i, 100);
            ctx.beginPath();
            ctx.moveTo(p1.x, tl.y);
            ctx.lineTo(p2.x, br.y);
            ctx.stroke();
            const p3 = this.toCanvas(0, i);
            const p4 = this.toCanvas(100, i);
            ctx.beginPath();
            ctx.moveTo(tl.x, p3.y);
            ctx.lineTo(br.x, p4.y);
            ctx.stroke();
        }
        ctx.setLineDash([]);
    },

    /* ── Path (free drawing) ───────────────────────────────────────── */
    drawPath(obj) {
        if (!obj.points || obj.points.length < 2) return;
        const ctx = this.ctx;
        ctx.strokeStyle = obj.color || "#ffffff";
        ctx.lineWidth = obj.width || 2;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.setLineDash([]);
        const start = this.toCanvas(obj.points[0].x, obj.points[0].y);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        for (let i = 1; i < obj.points.length; i++) {
            const p = this.toCanvas(obj.points[i].x, obj.points[i].y);
            ctx.lineTo(p.x, p.y);
        }
        ctx.stroke();
        ctx.lineCap = "butt";
        ctx.lineJoin = "miter";
    },

    /* ── Rectangle ─────────────────────────────────────────────────── */
    drawRect(obj) {
        const ctx = this.ctx;
        const tl = this.toCanvas(obj.x, obj.y);
        const w = obj.width * this.scale;
        const h = obj.height * this.scale;
        if (obj.fillColor) {
            ctx.fillStyle = obj.fillColor;
            ctx.fillRect(tl.x, tl.y, w, h);
        }
        if (obj.borderColor) {
            ctx.strokeStyle = obj.borderColor;
            ctx.lineWidth = 1.5;
            ctx.strokeRect(tl.x, tl.y, w, h);
        }
    },

    /* ── Ellipse ───────────────────────────────────────────────────── */
    drawEllipse(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const rx = obj.rx * this.scale;
        const ry = obj.ry * this.scale;
        ctx.beginPath();
        ctx.ellipse(pos.x, pos.y, rx, ry, 0, 0, Math.PI * 2);
        if (obj.fillColor) {
            ctx.fillStyle = obj.fillColor;
            ctx.fill();
        }
        if (obj.borderColor) {
            ctx.strokeStyle = obj.borderColor;
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }
    },

    /* ── Training Equipment Drawing ────────────────────────────────── */
    drawCone(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const r = (obj.radius || 1.5) * this.scale;
        // Triangle (cone shape)
        ctx.fillStyle = obj.color || "#ff9800";
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y - r);
        ctx.lineTo(pos.x - r * 0.87, pos.y + r * 0.5);
        ctx.lineTo(pos.x + r * 0.87, pos.y + r * 0.5);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.3)";
        ctx.lineWidth = 1;
        ctx.stroke();
    },

    drawMarker(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const r = (obj.radius || 1.5) * this.scale;
        // Diamond shape
        ctx.fillStyle = obj.color || "#4caf50";
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y - r);
        ctx.lineTo(pos.x + r, pos.y);
        ctx.lineTo(pos.x, pos.y + r);
        ctx.lineTo(pos.x - r, pos.y);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.3)";
        ctx.lineWidth = 1;
        ctx.stroke();
    },

    drawPole(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const h = (obj.height || 6) * this.scale;
        const w = 0.3 * this.scale;
        // Thin vertical line
        ctx.fillStyle = obj.color || "#ffeb3b";
        ctx.fillRect(pos.x - w / 2, pos.y - h / 2, w, h);
        // Small circle at top
        ctx.beginPath();
        ctx.arc(pos.x, pos.y - h / 2, w * 1.5, 0, Math.PI * 2);
        ctx.fill();
    },

    drawLadder(obj) {
        const ctx = this.ctx;
        const tl = this.toCanvas(obj.x, obj.y);
        const w = (obj.width || 10) * this.scale;
        const h = (obj.height || 8) * this.scale;
        ctx.strokeStyle = obj.color || "#ffffff";
        ctx.lineWidth = 1.5;
        // Outer frame
        ctx.strokeRect(tl.x, tl.y, w, h);
        // Horizontal rungs (4 divisions)
        const rungs = 4;
        for (let i = 1; i < rungs; i++) {
            const ry = tl.y + (h / rungs) * i;
            ctx.beginPath();
            ctx.moveTo(tl.x, ry);
            ctx.lineTo(tl.x + w, ry);
            ctx.stroke();
        }
    },

    drawMiniGoal(obj) {
        const ctx = this.ctx;
        const tl = this.toCanvas(obj.x, obj.y);
        const w = (obj.width || 8) * this.scale;
        const h = (obj.height || 5) * this.scale;
        // Goal frame (three sides, open bottom)
        ctx.strokeStyle = obj.color || "rgba(255,255,255,0.6)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(tl.x, tl.y + h);
        ctx.lineTo(tl.x, tl.y);
        ctx.lineTo(tl.x + w, tl.y);
        ctx.lineTo(tl.x + w, tl.y + h);
        ctx.stroke();
        // Net lines
        ctx.strokeStyle = "rgba(255,255,255,0.15)";
        ctx.lineWidth = 0.5;
        const netDiv = 4;
        for (let i = 1; i < netDiv; i++) {
            const nx = tl.x + (w / netDiv) * i;
            ctx.beginPath();
            ctx.moveTo(nx, tl.y);
            ctx.lineTo(nx, tl.y + h);
            ctx.stroke();
        }
        for (let i = 1; i < netDiv; i++) {
            const ny = tl.y + (h / netDiv) * i;
            ctx.beginPath();
            ctx.moveTo(tl.x, ny);
            ctx.lineTo(tl.x + w, ny);
            ctx.stroke();
        }
    },

    /* ── Ghost Silhouettes ─────────────────────────────────────────── */
    _drawGhosts() {
        if (!this.project || !this.project.frames || this.project.frames.length < 2) return;
        if (this.animationState.isPlaying) return;
        const frames = this.project.frames;
        const idx = this.animationState.currentFrame;
        const ctx = this.ctx;
        const opacity = this.ghostOpacity || 0.2;
        // Previous frame
        if (idx > 0 && frames[idx - 1] && frames[idx - 1].objects) {
            for (const obj of frames[idx - 1].objects) {
                if (obj.type === "player" && obj.visible) {
                    const pos = this.toCanvas(obj.x, obj.y);
                    const r = obj.radius * this.scale;
                    ctx.globalAlpha = opacity;
                    ctx.fillStyle = obj.color;
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.globalAlpha = 1;
                }
            }
        }
        // Next frame
        if (idx < frames.length - 1 && frames[idx + 1] && frames[idx + 1].objects) {
            for (const obj of frames[idx + 1].objects) {
                if (obj.type === "player" && obj.visible) {
                    const pos = this.toCanvas(obj.x, obj.y);
                    const r = obj.radius * this.scale;
                    ctx.globalAlpha = opacity * 0.6;
                    ctx.fillStyle = obj.color;
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.globalAlpha = 1;
                }
            }
        }
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
        } else if (preview.type === "rect") {
            const tl = this.toCanvas(preview.x, preview.y);
            const w = preview.width * this.scale;
            const h = preview.height * this.scale;
            ctx.fillStyle = "rgba(255,255,255,0.1)";
            ctx.fillRect(tl.x, tl.y, w, h);
            ctx.strokeRect(tl.x, tl.y, w, h);
        } else if (preview.type === "ellipse") {
            const pos = this.toCanvas(preview.x, preview.y);
            const rx = preview.rx * this.scale;
            const ry = preview.ry * this.scale;
            ctx.beginPath();
            ctx.ellipse(pos.x, pos.y, rx, ry, 0, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(255,255,255,0.1)";
            ctx.fill();
            ctx.stroke();
        }

        ctx.setLineDash([]);
    },

    drawSelection(obj) {
        const ctx = this.ctx;

        if (obj.type === "arrow" || obj.type === "path") {
            // Highlight arrow midpoint
            let start, end;
            if (obj.type === "path" && obj.points && obj.points.length >= 2) {
                start = this.toCanvas(obj.points[0].x, obj.points[0].y);
                end = this.toCanvas(obj.points[obj.points.length - 1].x, obj.points[obj.points.length - 1].y);
            } else {
                start = this.toCanvas(obj.startX, obj.startY);
                end = this.toCanvas(obj.endX, obj.endY);
            }
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
        } else if (obj.type === "zone" || obj.type === "rect") {
            const tl = this.toCanvas(obj.x, obj.y);
            const w = obj.width * this.scale;
            const h = obj.height * this.scale;
            ctx.strokeStyle = "#ffd700";
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.strokeRect(tl.x - 3, tl.y - 3, w + 6, h + 6);
            ctx.setLineDash([]);
        } else if (obj.type === "ellipse") {
            const pos = this.toCanvas(obj.x, obj.y);
            const rx = obj.rx * this.scale + 4;
            const ry = obj.ry * this.scale + 4;
            ctx.strokeStyle = "#ffd700";
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.ellipse(pos.x, pos.y, rx, ry, 0, 0, Math.PI * 2);
            ctx.stroke();
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
        this.canvas.addEventListener("dblclick", (e) => this.onDoubleClick(e));
        this.canvas.addEventListener("mouseleave", (e) => {
            this.onMouseUp(e);
            if (this._hoverCardEl) this._hoverCardEl.style.display = "none";
        });

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
        if (this._keydownHandler) {
            document.removeEventListener("keydown", this._keydownHandler);
        }
        this._keydownHandler = (e) => {
            if (e.ctrlKey && e.key === "z") {
                e.preventDefault();
                this.undo();
            } else if (e.ctrlKey && e.key === "y") {
                e.preventDefault();
                this.redo();
            } else if (e.key === "Delete" && this.selectedObject) {
                this.deleteSelected();
            } else if (e.ctrlKey && e.key === "d") {
                e.preventDefault();
                this.duplicateSelected();
            } else if (e.ctrlKey && e.key === "m") {
                e.preventDefault();
                this.mirrorSelected();
            }
        };
        document.addEventListener("keydown", this._keydownHandler);
    },

    onMouseDown(e) {
        if (!this.project) return;
        const rect = this.canvas.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        let { x, y } = this.fromCanvas(cx, cy);

        // Snap to grid
        if (this.snapToGrid) { x = Math.round(x / 5) * 5; y = Math.round(y / 5) * 5; }

        // Drawing mode: start drawing arrow or zone
        if (this.drawingMode === "arrow" || this.drawingMode === "zone" || this.drawingMode === "rect" || this.drawingMode === "ellipse") {
            this.drawStart = { x, y };
            this.selectedObject = null;
            this.render();
            return;
        }

        // Pen mode: start collecting points
        if (this.drawingMode === "pen") {
            this._penPoints = [{ x, y }];
            this.selectedObject = null;
            this.render();
            return;
        }

        // Eraser mode: remove object under cursor
        if (this.drawingMode === "eraser") {
            for (const obj of [...this.project.objects].reverse()) {
                if (!obj.visible || obj.locked) continue;
                if (obj.type === "player" || obj.type === "ball" || obj.type === "bench" || obj.type === "cone" || obj.type === "marker") {
                    const dx = x - obj.x, dy = y - obj.y;
                    if (dx * dx + dy * dy < (obj.radius + 2) * (obj.radius + 2)) {
                        this.pushUndo();
                        this.project.objects = this.project.objects.filter(o => o.id !== obj.id);
                        this.render();
                        if (this.onChange) this.onChange();
                        return;
                    }
                } else if (obj.type === "arrow" || obj.type === "path") {
                    const pts = obj.type === "path" ? obj.points : null;
                    if (pts) {
                        for (const p of pts) {
                            const dx = x - p.x, dy = y - p.y;
                            if (dx * dx + dy * dy < 25) {
                                this.pushUndo();
                                this.project.objects = this.project.objects.filter(o => o.id !== obj.id);
                                this.render();
                                if (this.onChange) this.onChange();
                                return;
                            }
                        }
                    }
                    const dist = this._pointToSegmentDist(x, y, obj.startX, obj.startY, obj.endX, obj.endY);
                    if (dist < 3) {
                        this.pushUndo();
                        this.project.objects = this.project.objects.filter(o => o.id !== obj.id);
                        this.render();
                        if (this.onChange) this.onChange();
                        return;
                    }
                } else if (obj.type === "zone" || obj.type === "rect" || obj.type === "ladder" || obj.type === "minigoal") {
                    if (x >= obj.x && x <= obj.x + obj.width && y >= obj.y && y <= obj.y + obj.height) {
                        this.pushUndo();
                        this.project.objects = this.project.objects.filter(o => o.id !== obj.id);
                        this.render();
                        if (this.onChange) this.onChange();
                        return;
                    }
                } else if (obj.type === "pole") {
                    const hw = 0.5, hh = (obj.height || 6) / 2;
                    if (x >= obj.x - hw && x <= obj.x + hw && y >= obj.y - hh && y <= obj.y + hh) {
                        this.pushUndo();
                        this.project.objects = this.project.objects.filter(o => o.id !== obj.id);
                        this.render();
                        if (this.onChange) this.onChange();
                        return;
                    }
                } else if (obj.type === "ellipse") {
                    const dx = (x - obj.x) / obj.rx, dy = (y - obj.y) / obj.ry;
                    if (dx * dx + dy * dy <= 1) {
                        this.pushUndo();
                        this.project.objects = this.project.objects.filter(o => o.id !== obj.id);
                        this.render();
                        if (this.onChange) this.onChange();
                        return;
                    }
                } else if (obj.type === "text") {
                    const pos = this.toCanvas(obj.x, obj.y);
                    const fontSize = (obj.fontSize || 12) * this.scale;
                    if (cx >= pos.x - fontSize * 3 && cx <= pos.x + fontSize * 3 && cy >= pos.y - fontSize && cy <= pos.y + fontSize) {
                        this.pushUndo();
                        this.project.objects = this.project.objects.filter(o => o.id !== obj.id);
                        this.render();
                        if (this.onChange) this.onChange();
                        return;
                    }
                }
            }
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

        // Find all objects under cursor (for overlap cycling)
        const hits = [];
        for (const obj of [...this.project.objects].reverse()) {
            if (!obj.visible || obj.locked) continue;
            if (obj.type === "player" || obj.type === "ball" || obj.type === "bench" || obj.type === "cone" || obj.type === "marker") {
                const dx = x - obj.x;
                const dy = y - obj.y;
                if (dx * dx + dy * dy < (obj.radius + 2) * (obj.radius + 2)) {
                    hits.push(obj);
                }
            } else if (obj.type === "arrow" || obj.type === "path") {
                if (obj.type === "path" && obj.points && obj.points.length >= 2) {
                    let hit = false;
                    for (let i = 0; i < obj.points.length - 1; i++) {
                        const dist = this._pointToSegmentDist(x, y, obj.points[i].x, obj.points[i].y, obj.points[i+1].x, obj.points[i+1].y);
                        if (dist < 3) { hit = true; break; }
                    }
                    if (hit) hits.push(obj);
                } else if (obj.type === "arrow") {
                    const dist = this._pointToSegmentDist(x, y, obj.startX, obj.startY, obj.endX, obj.endY);
                    if (dist < 3) hits.push(obj);
                }
            } else if (obj.type === "zone" || obj.type === "rect" || obj.type === "ladder" || obj.type === "minigoal") {
                if (x >= obj.x && x <= obj.x + obj.width && y >= obj.y && y <= obj.y + obj.height) {
                    hits.push(obj);
                }
            } else if (obj.type === "pole") {
                const hw = 0.5, hh = (obj.height || 6) / 2;
                if (x >= obj.x - hw && x <= obj.x + hw && y >= obj.y - hh && y <= obj.y + hh) {
                    hits.push(obj);
                }
            } else if (obj.type === "ellipse") {
                const dx = (x - obj.x) / obj.rx, dy = (y - obj.y) / obj.ry;
                if (dx * dx + dy * dy <= 1) hits.push(obj);
            }
        }

        // Overlap cycling: if clicking same position, cycle through hits
        let found = null;
        if (hits.length > 0) {
            const clickKey = Math.round(x * 10) + "," + Math.round(y * 10);
            if (this._lastClickPos === clickKey && hits.length > 1) {
                this._overlapIndex = (this._overlapIndex + 1) % hits.length;
            } else {
                this._overlapIndex = 0;
            }
            this._lastClickPos = clickKey;
            found = hits[this._overlapIndex];
        } else {
            this._lastClickPos = null;
            this._overlapIndex = 0;
        }

        this.selectedObject = found;
        if (found) {
            this.isDragging = true;
            // Track bench drag start for swap logic
            if (found.type === "bench") {
                this._benchDragStart = { x: found.x, y: found.y };
            } else {
                this._benchDragStart = null;
            }
            if (found.type === "arrow" || found.type === "path") {
                this.dragOffset = {
                    x: found.type === "path" && found.points && found.points.length > 0 ? x - found.points[0].x : x - (found.startX || 0),
                    y: found.type === "path" && found.points && found.points.length > 0 ? y - found.points[0].y : y - (found.startY || 0),
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
        let { x, y } = this.fromCanvas(cx, cy);

        // Snap to grid
        if (this.snapToGrid && (this.isDragging || this.drawStart || this._penPoints.length > 0)) {
            x = Math.round(x / 5) * 5;
            y = Math.round(y / 5) * 5;
        }

        // Pen mode: collect points
        if (this.drawingMode === "pen" && this._penPoints.length > 0) {
            this._penPoints.push({ x, y });
            this.render();
            // Draw the live pen stroke
            const ctx = this.ctx;
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 2;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            const s = this.toCanvas(this._penPoints[0].x, this._penPoints[0].y);
            ctx.beginPath();
            ctx.moveTo(s.x, s.y);
            for (let i = 1; i < this._penPoints.length; i++) {
                const p = this.toCanvas(this._penPoints[i].x, this._penPoints[i].y);
                ctx.lineTo(p.x, p.y);
            }
            ctx.stroke();
            ctx.lineCap = "butt";
            ctx.lineJoin = "miter";
            return;
        }

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
            } else if (this.drawingMode === "rect") {
                const rx = Math.min(this.drawStart.x, x);
                const ry = Math.min(this.drawStart.y, y);
                const rw = Math.abs(x - this.drawStart.x);
                const rh = Math.abs(y - this.drawStart.y);
                this.drawPreview = {
                    type: "rect",
                    x: rx, y: ry,
                    width: rw, height: rh,
                };
            } else if (this.drawingMode === "ellipse") {
                const ecx = (this.drawStart.x + x) / 2;
                const ecy = (this.drawStart.y + y) / 2;
                const erx = Math.abs(x - this.drawStart.x) / 2;
                const ery = Math.abs(y - this.drawStart.y) / 2;
                this.drawPreview = {
                    type: "ellipse",
                    x: ecx, y: ecy,
                    rx: erx, ry: ery,
                };
            }
            this.render();
            return;
        }

        // Hover card: show player info on hover
        this._updateHoverCard(cx, cy, x, y);

        if (!this.isDragging || !this.selectedObject) return;

        if (this.selectedObject.type === "path" && this.selectedObject.points) {
            // Move all path points
            const newX = Math.max(0, Math.min(100, x - this.dragOffset.x));
            const newY = Math.max(0, Math.min(100, y - this.dragOffset.y));
            const dx = newX - this.selectedObject.points[0].x;
            const dy = newY - this.selectedObject.points[0].y;
            for (const p of this.selectedObject.points) {
                p.x = Math.max(0, Math.min(100, p.x + dx));
                p.y = Math.max(0, Math.min(100, p.y + dy));
            }
        } else if (this.selectedObject.type === "arrow") {
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
        if (!this.project) return;

        // Pen mode: finalize path object
        if (this.drawingMode === "pen" && this._penPoints.length >= 2) {
            this.pushUndo();
            const pathObj = TACTICAL_BOARD.createPath(this._penPoints);
            this.project.objects.push(pathObj);
            this._penPoints = [];
            this.render();
            if (this.onChange) this.onChange();
            return;
        }
        this._penPoints = [];

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
            } else if (this.drawingMode === "rect") {
                const rect = TACTICAL_BOARD.createRect(
                    this.drawPreview.x, this.drawPreview.y,
                    this.drawPreview.width, this.drawPreview.height
                );
                this.project.objects.push(rect);
            } else if (this.drawingMode === "ellipse") {
                const ell = TACTICAL_BOARD.createEllipse(
                    this.drawPreview.x, this.drawPreview.y,
                    this.drawPreview.rx, this.drawPreview.ry
                );
                this.project.objects.push(ell);
            }
            this.drawStart = null;
            this.drawPreview = null;
            this.render();
        }

        // Bench-to-pitch swap: if a bench player was dragged onto the pitch area
        if (this.selectedObject && this.selectedObject.type === "bench") {
            const bx = this.selectedObject.x;
            const by = this.selectedObject.y;
            // Check if now on the pitch (0-100 range)
            if (bx >= 0 && bx <= 100 && by >= 0 && by <= 100) {
                const benchTeam = this.selectedObject.team;
                // Find nearest player of same team
                let nearest = null;
                let nearestDist = Infinity;
                for (const obj of this.project.objects) {
                    if (obj.type === "player" && obj.team === benchTeam) {
                        const dx = bx - obj.x;
                        const dy = by - obj.y;
                        const d = dx * dx + dy * dy;
                        if (d < nearestDist) {
                            nearestDist = d;
                            nearest = obj;
                        }
                    }
                }
                if (nearest && nearestDist < 400) {
                    // Swap: move the player to bench's original position, bench to player's position
                    this.pushUndo();
                    const origBenchX = this._benchDragStart ? this._benchDragStart.x : bx;
                    const origBenchY = this._benchDragStart ? this._benchDragStart.y : by;
                    const playerX = nearest.x;
                    const playerY = nearest.y;
                    nearest.x = origBenchX;
                    nearest.y = origBenchY;
                    nearest.type = "bench";
                    nearest.radius = 2;
                    this.selectedObject.x = playerX;
                    this.selectedObject.y = playerY;
                    this.selectedObject.type = "player";
                    this.selectedObject.radius = 3;
                }
            }
        }
        this._benchDragStart = null;

        this.isDragging = false;
        if (this.onChange) this.onChange();
    },

    /* ── Double-click: edit jersey number ──────────────────────────── */
    onDoubleClick(e) {
        if (!this.project || !this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        const cx = e.clientX - rect.left;
        const cy = e.clientY - rect.top;
        const { x, y } = this.fromCanvas(cx, cy);

        // Find player/bench object under cursor
        let found = null;
        for (const obj of [...this.project.objects].reverse()) {
            if (!obj.visible) continue;
            if (obj.type === "player" || obj.type === "bench") {
                const dx = x - obj.x;
                const dy = y - obj.y;
                if (dx * dx + dy * dy < (obj.radius + 2) * (obj.radius + 2)) {
                    found = obj;
                    break;
                }
            }
        }
        if (!found) return;

        // Create inline input
        this._removeJerseyInput();
        const input = document.createElement("input");
        input.type = "number";
        input.min = "0";
        input.max = "99";
        input.value = found.number || "";
        input.style.cssText = `position:fixed;left:${e.clientX - 16}px;top:${e.clientY - 16}px;` +
            "width:40px;height:28px;background:rgba(20,24,36,0.95);color:#fff;border:1px solid #7ca8ff;" +
            "border-radius:4px;text-align:center;font:14px/1 Inter,sans-serif;z-index:10000;outline:none;" +
            "box-shadow:0 2px 10px rgba(0,0,0,0.5)";
        input.dataset.playerId = found.id;

        const commit = () => {
            const val = parseInt(input.value, 10);
            if (!isNaN(val) && val >= 0 && val <= 99) {
                this.pushUndo();
                found.number = val;
                this.render();
                if (this.onChange) this.onChange();
            }
            this._removeJerseyInput();
        };

        input.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter") { ev.preventDefault(); commit(); }
            if (ev.key === "Escape") { this._removeJerseyInput(); }
        });
        input.addEventListener("blur", commit);

        document.body.appendChild(input);
        input.focus();
        input.select();
        this._jerseyInput = input;
    },

    _removeJerseyInput() {
        if (this._jerseyInput) {
            if (this._jerseyInput.parentNode) this._jerseyInput.parentNode.removeChild(this._jerseyInput);
            this._jerseyInput = null;
        }
    },

    /* ── Drawing mode ────────────────────────────────────────────────── */
    setDrawingMode(mode) {
        this.drawingMode = mode; // null | 'arrow' | 'zone' | 'text'
        this.drawStart = null;
        this.drawPreview = null;
        this._penPoints = [];
        // Update cursor
        if (this.canvas) {
            if (mode === "text") this.canvas.style.cursor = "text";
            else if (mode === "arrow" || mode === "zone" || mode === "rect" || mode === "ellipse") this.canvas.style.cursor = "crosshair";
            else if (mode === "pen") this.canvas.style.cursor = "crosshair";
            else if (mode === "eraser") this.canvas.style.cursor = "pointer";
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
    /* ── Duplicate / Mirror ──────────────────────────────────────────── */
    duplicateSelected() {
        if (!this.selectedObject) return;
        this.pushUndo();
        const copy = JSON.parse(JSON.stringify(this.selectedObject));
        // Generate new id
        copy.id = (typeof crypto !== "undefined" && crypto.randomUUID)
            ? crypto.randomUUID()
            : Date.now().toString(36) + Math.random().toString(36).slice(2);
        // Offset 5 units to the right
        if (copy.type === "arrow" || copy.type === "path") {
            if (copy.type === "path" && copy.points) {
                for (const p of copy.points) { p.x = Math.min(100, p.x + 5); }
            } else {
                copy.startX = Math.min(100, copy.startX + 5);
                copy.endX = Math.min(100, copy.endX + 5);
            }
        } else if (copy.type === "zone" || copy.type === "rect") {
            copy.x = Math.min(100, copy.x + 5);
        } else if (copy.type === "ellipse") {
            copy.x = Math.min(100, copy.x + 5);
        } else {
            copy.x = Math.min(100, copy.x + 5);
        }
        this.project.objects.push(copy);
        this.selectedObject = copy;
        this.render();
        if (this.onChange) this.onChange();
    },

    mirrorSelected() {
        if (!this.selectedObject) return;
        this.pushUndo();
        const obj = this.selectedObject;
        if (obj.type === "arrow") {
            obj.startX = 100 - obj.startX;
            obj.endX = 100 - obj.endX;
        } else if (obj.type === "path" && obj.points) {
            for (const p of obj.points) { p.x = 100 - p.x; }
        } else if (obj.type === "zone" || obj.type === "rect") {
            obj.x = 100 - obj.x - obj.width;
        } else if (obj.type === "ellipse") {
            obj.x = 100 - obj.x;
        } else {
            obj.x = 100 - obj.x;
        }
        this.render();
        if (this.onChange) this.onChange();
    },

    mirrorAllHome() {
        if (!this.project) return;
        this.pushUndo();
        for (const obj of this.project.objects) {
            if (obj.type === "player" && obj.team === "home") {
                obj.x = 100 - obj.x;
            }
        }
        this.render();
        if (this.onChange) this.onChange();
    },

    mirrorAllAway() {
        if (!this.project) return;
        this.pushUndo();
        for (const obj of this.project.objects) {
            if (obj.type === "player" && obj.team === "away") {
                obj.x = 100 - obj.x;
            }
        }
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
        if (!this.project || !this.project.frames) { this.animationState.isPlaying = false; return; }

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
        this.updateTimeline();
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

    /* ── Hover Card ──────────────────────────────────────────────────── */
    _initHoverCard() {
        if (this._hoverCardEl && this._hoverCardEl.parentNode) return;
        const el = document.createElement("div");
        el.style.cssText = "position:fixed;display:none;z-index:9999;pointer-events:none;" +
            "background:rgba(20,24,36,0.92);backdrop-filter:blur(12px);border:1px solid rgba(124,168,255,0.3);" +
            "border-radius:8px;padding:8px 12px;color:#e0e6f0;font:12px/1.4 Inter,sans-serif;" +
            "box-shadow:0 4px 20px rgba(0,0,0,0.4);min-width:120px;max-width:220px;";
        document.body.appendChild(el);
        this._hoverCardEl = el;
    },

    _updateHoverCard(cx, cy, nx, ny) {
        if (!this._hoverCardEl || !this.project) { return; }
        let hovered = null;
        for (const obj of [...this.project.objects].reverse()) {
            if (!obj.visible) continue;
            if (obj.type === "player" || obj.type === "bench") {
                const dx = nx - obj.x, dy = ny - obj.y;
                if (dx * dx + dy * dy < (obj.radius + 2) * (obj.radius + 2)) { hovered = obj; break; }
            }
        }
        if (hovered) {
            const team = hovered.team === "away" ? "\u5BA2\u573A" : "\u4E3B\u573A";
            const pos = hovered.type === "bench" ? " \u66FF\u8865" : "";
            const num = hovered.number ? `#${hovered.number}` : "";
            const label = hovered.label || "";
            this._hoverCardEl.innerHTML = `<div style="font-weight:600;margin-bottom:2px">\u25CB ${label} ${num}</div>` +
                `<div style="opacity:0.7;font-size:11px">\u7403\u961F: ${team}${pos}</div>` +
                `<div style="opacity:0.7;font-size:11px">\u4F4D\u7F6E: (${hovered.x.toFixed(0)}, ${hovered.y.toFixed(0)})</div>`;
            const rect = this.canvas.getBoundingClientRect();
            this._hoverCardEl.style.display = "block";
            this._hoverCardEl.style.left = (rect.left + cx + 16) + "px";
            this._hoverCardEl.style.top = (rect.top + cy - 10) + "px";
        } else {
            this._hoverCardEl.style.display = "none";
        }
    },

    /* ── Timeline UI ──────────────────────────────────────────────────── */
    _initTimeline() {
        if (!this.canvas || !this.canvas.parentElement) return;
        const parent = this.canvas.parentElement;
        if (this._timelineEl && this._timelineEl.parentNode) return;
        const el = document.createElement("div");
        el.style.cssText = "display:flex;align-items:center;gap:8px;padding:6px 10px;" +
            "background:rgba(20,24,36,0.85);backdrop-filter:blur(8px);border-top:1px solid rgba(255,255,255,0.08);" +
            "font:12px/1 Inter,sans-serif;color:#c0c8d8;user-select:none;";
        el.innerHTML =
            '<button data-act="prev" style="background:none;border:none;color:inherit;cursor:pointer;font-size:16px" title="\u4E0A\u4E00\u5E27">\u25C1</button>' +
            '<div style="flex:1;position:relative;height:20px;cursor:pointer" data-act="scrub">' +
            '<div style="position:absolute;top:8px;left:0;right:0;height:3px;background:rgba(255,255,255,0.12);border-radius:2px"></div>' +
            '<div data-el="progress" style="position:absolute;top:8px;left:0;height:3px;background:#7ca8ff;border-radius:2px;width:0%"></div>' +
            '<div data-el="markers" style="position:absolute;top:0;left:0;right:0;height:20px"></div>' +
            '<div data-el="indicator" style="position:absolute;top:3px;left:0;width:14px;height:14px;background:#7ca8ff;border-radius:50%;transform:translateX(-7px);box-shadow:0 0 6px rgba(124,168,255,0.6)"></div>' +
            '</div>' +
            '<button data-act="next" style="background:none;border:none;color:inherit;cursor:pointer;font-size:16px" title="\u4E0B\u4E00\u5E27">\u25B7</button>' +
            '<span data-el="label" style="min-width:48px;text-align:center;font-size:11px;color:#8892a4">1 / 1</span>';
        parent.appendChild(el);
        this._timelineEl = el;
        // Bind events
        el.querySelector('[data-act="prev"]').addEventListener("click", () => this.prevFrame());
        el.querySelector('[data-act="next"]').addEventListener("click", () => this.nextFrame());
        el.querySelector('[data-act="scrub"]').addEventListener("click", (ev) => {
            if (!this.project || !this.project.frames) return;
            const scrubEl = el.querySelector('[data-act="scrub"]');
            const r = scrubEl.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
            const idx = Math.min(this.project.frames.length - 1, Math.round(pct * (this.project.frames.length - 1)));
            this.goToFrame(idx);
            this.updateTimeline();
        });
    },

    updateTimeline() {
        if (!this._timelineEl || !this.project || !this.project.frames) return;
        const frames = this.project.frames;
        const idx = this.animationState.currentFrame;
        const pct = frames.length > 1 ? (idx / (frames.length - 1)) * 100 : 0;
        const progress = this._timelineEl.querySelector('[data-el="progress"]');
        const indicator = this._timelineEl.querySelector('[data-el="indicator"]');
        const label = this._timelineEl.querySelector('[data-el="label"]');
        const markers = this._timelineEl.querySelector('[data-el="markers"]');
        if (progress) progress.style.width = pct + "%";
        if (indicator) indicator.style.left = pct + "%";
        if (label) label.textContent = (idx + 1) + " / " + frames.length;
        // Render frame markers
        if (markers) {
            markers.innerHTML = "";
            for (let i = 0; i < frames.length; i++) {
                const m = document.createElement("div");
                const mp = frames.length > 1 ? (i / (frames.length - 1)) * 100 : 0;
                m.style.cssText = `position:absolute;top:2px;left:${mp}%;width:6px;height:6px;transform:translateX(-3px);` +
                    `background:${i === idx ? "#7ca8ff" : "rgba(255,255,255,0.25)"};border-radius:50%;cursor:pointer`;
                m.title = frames[i].name || ("Frame " + (i + 1));
                const fi = i;
                m.addEventListener("click", (ev) => { ev.stopPropagation(); this.goToFrame(fi); this.updateTimeline(); });
                markers.appendChild(m);
            }
        }
    },

    /* ── PDF Export ──────────────────────────────────────────────────── */
    exportPDF() {
        if (!this.canvas) return;
        const savedSelection = this.selectedObject;
        this.selectedObject = null;
        this.render();
        const dataUrl = this.canvas.toDataURL("image/png");
        this.selectedObject = savedSelection;
        this.render();
        const w = window.open("", "_blank");
        if (!w) { alert("\u25C6 \u8BF7\u5141\u8BB8\u5F39\u51FA\u7A97\u53E3\u4EE5\u5BFC\u51FAPDF"); return; }
        w.document.write(
            '<!DOCTYPE html><html><head><title>\u6218\u672F\u677F\u5BFC\u51FA</title>' +
            '<style>@media print{body{margin:0}img{max-width:100%;height:auto}}body{margin:20px;text-align:center}</style>' +
            '</head><body>' +
            '<h2 style="font-family:Inter,sans-serif;color:#333">\u6218\u672F\u677F \u2014 Tactical Board</h2>' +
            '<img src="' + dataUrl + '" style="max-width:100%;border:1px solid #ccc;border-radius:4px" />' +
            '<script>setTimeout(function(){window.print()},500)<\/script>' +
            '</body></html>'
        );
        w.document.close();
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
        if (this._isRecording) return;
        this._isRecording = true;
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
            this._isRecording = false;
        });
    },
};
