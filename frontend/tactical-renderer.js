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
    _presentationNotesEl: null, // overlay for frame notes in presentation mode
    showTrails: false,           // show animation trails
    _trailPositions: new Map(),  // objectId -> [{x,y}...] trail positions during animation
    _ballDragTrail: [],          // last N positions during ball drag
    _pathEditMode: false,        // path point editing mode
    _pathEditObjectId: null,     // object id being path-edited
    _perfMonitor: {               // performance monitor state
        renderTime: 0,
        fps: 0,
        frameCount: 0,
        lastSecond: 0,
        _frameTimes: [],
    },
    _debugMode: false,             // show FPS counter
    _xtHeatmapData: null,          // xT heatmap data for overlay
    _showXTHeatmap: false,         // toggle xT heatmap visibility
    _showExportAttribution: false, // draw attribution on canvas during export

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

        // Make canvas focusable for keyboard navigation
        if (!this.canvas.hasAttribute("tabindex")) {
            this.canvas.setAttribute("tabindex", "0");
        }
    },

    /* ── Accessibility: announce object to screen readers ─────────── */
    _announceObject(obj, action) {
        if (!obj) return;
        var label = obj.type || "object";
        if (obj.type === "player") {
            label = "Player" + (obj.label ? " " + obj.label : "") + (obj.number ? " #" + obj.number : "") + " (" + (obj.team || "home") + ")";
        } else if (obj.type === "ball") {
            label = "Ball";
        } else if (obj.type === "arrow") {
            label = "Arrow (" + (obj.style || "solid") + ")";
        } else if (obj.type === "zone") {
            label = "Zone" + (obj.label ? ": " + obj.label : "");
        } else if (obj.type === "text") {
            label = "Text: " + (obj.text || "").slice(0, 40);
        }
        var msg = label + (action ? " " + action : "");
        // Use aria-live region if available
        var live = document.getElementById("tactical-a11y-live");
        if (live) {
            live.textContent = msg;
        }
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
        const perfStart = performance.now();
        const ctx = this.ctx;
        const w = this.canvas.width / (window.devicePixelRatio || 1);
        const h = this.canvas.height / (window.devicePixelRatio || 1);

        // Clear
        ctx.clearRect(0, 0, w, h);

        // Draw pitch
        this.drawPitch();

        // Draw xT heatmap overlay (semi-transparent, on top of pitch)
        if (this._showXTHeatmap && this._xtHeatmapData) {
            this._drawXTHeatmap();
        }

        // Draw grid overlay
        if (this.showGrid) this.drawGrid();

        // Draw ghost silhouettes (previous/next frame positions in animation mode)
        this._drawGhosts();

        // Draw animation trails (behind objects)
        if (this.showTrails && this.animationState.isPlaying) {
            this._drawTrails();
        }

        // Draw ball drag trail (when dragging a ball)
        if (this._ballDragTrail.length > 0) {
            this._drawBallDragTrail();
        }

        // Draw objects (with frame visibility check)
        const currentFrame = this.animationState.currentFrame || 0;
        const dMode = (this.project && this.project.displayMode) || "single";
        for (const obj of this.project.objects) {
            if (!obj.visible) continue;
            // Frame visibility: object only renders when currentFrame is within [visibleFrom, visibleTo]
            const vf = Number.isFinite(obj.visibleFrom) ? obj.visibleFrom : 0;
            const vt = Number.isFinite(obj.visibleTo) ? obj.visibleTo : Infinity;
            if (currentFrame < vf || currentFrame > vt) continue;

            // Both-teams display mode: reposition players based on team
            const savedX = obj.x;
            const savedY = obj.y;
            if (dMode !== "single" && obj.type === "player") {
                if (dMode === "both") {
                    // Home team on left half (0-48), away team on right half (52-100)
                    obj.x = obj.team === "home" ? obj.x * 0.48 : 52 + obj.x * 0.48;
                } else if (dMode === "transition") {
                    // Both teams shown, mirrored for away
                    obj.x = obj.team === "home" ? obj.x * 0.85 + 5 : obj.x * 0.85 + 10;
                    if (obj.team === "away") obj.y = 100 - obj.y;
                }
            }

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
                case "event-marker": this.drawEventMarker(obj); break;
            }

            // Restore original coordinates
            obj.x = savedX;
            obj.y = savedY;
        }

        // Draw transition mode attack direction arrows
        if (dMode === "transition") {
            this._drawTransitionArrows();
        }

        // Draw path indicators for objects with pathPoints
        this._drawObjectPaths();

        // Draw preview during drawing mode
        if (this.drawPreview) {
            this._drawPreviewObject(this.drawPreview);
        }

        // Draw selection highlight
        if (this.selectedObject) {
            this.drawSelection(this.selectedObject);
        }

        // Draw team color legend (accessibility: text labels alongside color indicators)
        this._drawTeamLegend();

        // Draw performance warnings (object/frame count)
        this._drawPerformanceWarnings();

        // Draw export attribution when recording or capturing frames
        if (this._showExportAttribution) {
            this._drawExportAttribution();
        }

        // Draw FPS counter in debug mode
        if (this._debugMode) {
            this._drawFPSCounter(perfStart);
        }
        // Track render time
        this._perfMonitor.renderTime = performance.now() - perfStart;

        // Update timeline UI
        this.updateTimeline();
    },

    /* ── Team color legend ──────────────────────────────────────────── */
    _drawTeamLegend() {
        if (!this.project) return;
        var ctx = this.ctx;
        var hasHome = this.project.objects.some(function(o) { return o.type === "player" && o.team === "home"; });
        var hasAway = this.project.objects.some(function(o) { return o.type === "player" && o.team === "away"; });
        if (!hasHome && !hasAway) return;

        var w = this.canvas.width / (window.devicePixelRatio || 1);
        var x = w - 90;
        var y = 10;
        var lineH = 16;

        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(x - 4, y - 2, 86, (hasHome && hasAway ? 2 : 1) * lineH + 8);

        ctx.font = "bold 11px Inter, sans-serif";
        ctx.textBaseline = "middle";

        if (hasHome) {
            ctx.fillStyle = "#7ca8ff";
            ctx.beginPath();
            ctx.arc(x + 6, y + lineH / 2 + 2, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = "#fff";
            ctx.textAlign = "left";
            ctx.fillText("Home", x + 16, y + lineH / 2 + 2);
            y += lineH;
        }
        if (hasAway) {
            ctx.fillStyle = "#ff6b7b";
            ctx.beginPath();
            ctx.arc(x + 6, y + lineH / 2 + 2, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = "#fff";
            ctx.textAlign = "left";
            ctx.fillText("Away", x + 16, y + lineH / 2 + 2);
        }
    },

    /* ── Performance boundary warnings ──────────────────────────────── */
    _checkPerformance() {
        if (!this.project) return { objectCount: 0, frameCount: 0, warnings: [] };
        const objectCount = (this.project.objects || []).length;
        const frameCount = (this.project.frames || []).length;
        const warnings = [];
        if (objectCount > 200) {
            warnings.push("Too many objects (" + objectCount + "). Consider splitting the project.");
        }
        if (frameCount > 60) {
            warnings.push("Too many frames (" + frameCount + "). Consider splitting the animation.");
        }
        return { objectCount, frameCount, warnings };
    },

    _drawPerformanceWarnings() {
        var check = this._checkPerformance();
        if (check.warnings.length === 0) return;
        var ctx = this.ctx;
        var w = this.canvas.width / (window.devicePixelRatio || 1);
        var y = 40;
        ctx.save();
        ctx.font = "bold 12px Inter, sans-serif";
        ctx.textBaseline = "top";
        for (var i = 0; i < check.warnings.length; i++) {
            var msg = check.warnings[i];
            var tw = ctx.measureText(msg).width + 16;
            ctx.fillStyle = "rgba(255,80,80,0.85)";
            ctx.fillRect((w - tw) / 2, y, tw, 22);
            ctx.fillStyle = "#ffffff";
            ctx.textAlign = "center";
            ctx.fillText(msg, w / 2, y + 5);
            y += 28;
        }
        ctx.restore();
    },

    /* ── Export attribution (drawn on canvas before PNG/WebM/GIF capture) */
    _drawExportAttribution() {
        if (!this.project) return;
        var ctx = this.ctx;
        var w = this.canvas.width / (window.devicePixelRatio || 1);
        var h = this.canvas.height / (window.devicePixelRatio || 1);
        var attribution = this.project.source_attribution || "ScoutFootball tactical board";
        ctx.save();
        ctx.font = "10px Inter, sans-serif";
        ctx.fillStyle = "rgba(255,255,255,0.55)";
        ctx.textAlign = "right";
        ctx.textBaseline = "bottom";
        ctx.fillText(attribution + " \u2014 " + new Date().toISOString().slice(0, 10), w - 10, h - 6);
        ctx.restore();
    },

    /* ── FPS counter (debug mode) ───────────────────────────────────── */
    _drawFPSCounter(perfStart) {
        var now = performance.now();
        var pm = this._perfMonitor;
        pm._frameTimes.push(now);
        // Keep only last 2 seconds of frame times
        while (pm._frameTimes.length > 0 && pm._frameTimes[0] < now - 2000) {
            pm._frameTimes.shift();
        }
        pm.fps = pm._frameTimes.length > 1
            ? Math.round((pm._frameTimes.length - 1) / ((now - pm._frameTimes[0]) / 1000))
            : 0;
        var ctx = this.ctx;
        ctx.save();
        ctx.font = "bold 11px monospace";
        ctx.textBaseline = "top";
        ctx.textAlign = "left";
        var txt = "FPS: " + pm.fps + "  Render: " + pm.renderTime.toFixed(1) + "ms";
        ctx.fillStyle = "rgba(0,0,0,0.7)";
        ctx.fillRect(8, 8, ctx.measureText(txt).width + 12, 18);
        ctx.fillStyle = "#00ff88";
        ctx.fillText(txt, 14, 11);
        ctx.restore();
    },

    /* ── Simplify project ───────────────────────────────────────────── */
    simplifyProject() {
        if (!this.project) return;
        // Remove hidden objects
        this.project.objects = (this.project.objects || []).filter(function(o) { return o.visible !== false; });
        // Remove empty frames (frames with no objects and no event markers)
        if (Array.isArray(this.project.frames)) {
            this.project.frames = this.project.frames.filter(function(f) {
                return (f.objects && f.objects.length > 0) || (f.eventMarkers && f.eventMarkers.length > 0);
            });
            // Ensure at least one frame remains
            if (this.project.frames.length === 0) {
                this.project.frames = [{ id: "frame-0", name: "Frame 1", objects: [], duration_ms: 3000, notes: "" }];
            }
        }
        this.render();
    },

    /* ── xT Heatmap overlay ─────────────────────────────────────────── */
    setXTHeatmapData(data) {
        this._xtHeatmapData = data;
        this.render();
    },

    toggleXTHeatmap() {
        this._showXTHeatmap = !this._showXTHeatmap;
        this.render();
        return this._showXTHeatmap;
    },

    _drawXTHeatmap() {
        if (!this._xtHeatmapData || !this.ctx) return;
        var ctx = this.ctx;
        var data = this._xtHeatmapData;
        // data is a 2D array: data[row][col] = xT value (12 cols x 8 rows typical)
        var rows = data.length;
        if (rows === 0) return;
        var cols = data[0].length;
        if (cols === 0) return;

        // Find min/max for color scale
        var minVal = Infinity, maxVal = -Infinity;
        for (var r = 0; r < rows; r++) {
            for (var c = 0; c < cols; c++) {
                var v = data[r][c];
                if (v < minVal) minVal = v;
                if (v > maxVal) maxVal = v;
            }
        }
        var range = maxVal - minVal || 1;

        // Map grid cells to pitch coordinates (0-100)
        var cellW = 100 / cols;
        var cellH = 100 / rows;
        ctx.save();
        ctx.globalAlpha = 0.45;
        for (var r = 0; r < rows; r++) {
            for (var c = 0; c < cols; c++) {
                var v = data[r][c];
                var t = (v - minVal) / range; // 0..1
                // Blue (low) to Red (high) color scale
                var red = Math.round(t * 255);
                var blue = Math.round((1 - t) * 255);
                var green = Math.round(80 * (1 - Math.abs(t - 0.5) * 2));
                ctx.fillStyle = "rgb(" + red + "," + green + "," + blue + ")";
                var tl = this.toCanvas(c * cellW, r * cellH);
                var br = this.toCanvas((c + 1) * cellW, (r + 1) * cellH);
                ctx.fillRect(tl.x, tl.y, br.x - tl.x, br.y - tl.y);
            }
        }
        ctx.restore();
        // Draw color scale legend
        this._drawHeatmapColorScale(minVal, maxVal);
        // StatsBomb attribution
        var w = this.canvas.width / (window.devicePixelRatio || 1);
        ctx.save();
        ctx.font = "10px Inter, sans-serif";
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.textAlign = "right";
        ctx.textBaseline = "bottom";
        ctx.fillText("Data: StatsBomb Open Data", w - 10, this.canvas.height / (window.devicePixelRatio || 1) - 8);
        ctx.restore();
    },

    _drawHeatmapColorScale(minVal, maxVal) {
        var ctx = this.ctx;
        var w = this.canvas.width / (window.devicePixelRatio || 1);
        var barX = w - 30;
        var barY = 60;
        var barW = 14;
        var barH = 100;
        ctx.save();
        ctx.globalAlpha = 0.85;
        for (var i = 0; i < barH; i++) {
            var t = i / barH;
            var red = Math.round(t * 255);
            var blue = Math.round((1 - t) * 255);
            var green = Math.round(80 * (1 - Math.abs(t - 0.5) * 2));
            ctx.fillStyle = "rgb(" + red + "," + green + "," + blue + ")";
            ctx.fillRect(barX, barY + i, barW, 1);
        }
        ctx.globalAlpha = 1;
        ctx.font = "9px monospace";
        ctx.fillStyle = "#fff";
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        ctx.fillText(maxVal.toFixed(2), barX + barW + 3, barY);
        ctx.fillText(minVal.toFixed(2), barX + barW + 3, barY + barH - 10);
        ctx.fillText("xT", barX + barW + 3, barY + barH / 2 - 4);
        ctx.restore();
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

        // Shape rendering based on appearance
        ctx.fillStyle = obj.color;
        ctx.globalAlpha = (obj.appearance && typeof obj.appearance.opacity === "number") ? obj.appearance.opacity : 1.0;

        const shape = (obj.appearance && obj.appearance.shape) || "circle";
        switch (shape) {
            case "square": {
                const s = r * 1.6;
                ctx.fillRect(pos.x - s / 2, pos.y - s / 2, s, s);
                break;
            }
            case "triangle": {
                const s = r * 1.8;
                ctx.beginPath();
                ctx.moveTo(pos.x, pos.y - s);
                ctx.lineTo(pos.x - s * 0.87, pos.y + s * 0.5);
                ctx.lineTo(pos.x + s * 0.87, pos.y + s * 0.5);
                ctx.closePath();
                ctx.fill();
                break;
            }
            case "diamond": {
                const s = r * 1.6;
                ctx.beginPath();
                ctx.moveTo(pos.x, pos.y - s);
                ctx.lineTo(pos.x + s, pos.y);
                ctx.lineTo(pos.x, pos.y + s);
                ctx.lineTo(pos.x - s, pos.y);
                ctx.closePath();
                ctx.fill();
                break;
            }
            default: { // circle
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
                ctx.fill();
                break;
            }
        }
        ctx.globalAlpha = 1.0;

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

        // Accessibility: show team text label alongside color when focus ring active
        if (this._focusRingActive && this.selectedObject && this.selectedObject.id === obj.id) {
            ctx.fillStyle = "#fff";
            ctx.font = `bold ${Math.max(9, r * 0.55)}px Inter, sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            var teamLabel = (obj.team === "away") ? "AWAY" : "HOME";
            ctx.fillText(teamLabel, pos.x, pos.y + r + 3);
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

        // Possession indicator: small colored dot next to ball
        if (obj.possession === "home" || obj.possession === "away") {
            const dotR = r * 0.4;
            const dotOffset = r + dotR + 2;
            const dotColor = obj.possession === "home" ? "#7ca8ff" : "#ff6b7b";
            ctx.fillStyle = dotColor;
            ctx.beginPath();
            ctx.arc(pos.x + dotOffset, pos.y - dotOffset, dotR, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = "rgba(0,0,0,0.4)";
            ctx.lineWidth = 1;
            ctx.stroke();
        }
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

    /* ── Transition Mode Arrows ────────────────────────────────────── */
    _drawTransitionArrows() {
        const ctx = this.ctx;
        // Draw attack direction arrows for each team
        // Home team: arrow from left to center
        const homeStart = this.toCanvas(8, 50);
        const homeEnd = this.toCanvas(42, 50);
        ctx.strokeStyle = "rgba(124,168,255,0.5)";
        ctx.lineWidth = 2.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(homeStart.x, homeStart.y);
        ctx.lineTo(homeEnd.x, homeEnd.y);
        ctx.stroke();
        // Arrowhead
        const hAngle = Math.atan2(homeEnd.y - homeStart.y, homeEnd.x - homeStart.x);
        ctx.beginPath();
        ctx.moveTo(homeEnd.x, homeEnd.y);
        ctx.lineTo(homeEnd.x - 10 * Math.cos(hAngle - Math.PI / 6), homeEnd.y - 10 * Math.sin(hAngle - Math.PI / 6));
        ctx.moveTo(homeEnd.x, homeEnd.y);
        ctx.lineTo(homeEnd.x - 10 * Math.cos(hAngle + Math.PI / 6), homeEnd.y - 10 * Math.sin(hAngle + Math.PI / 6));
        ctx.stroke();

        // Away team: arrow from right to center
        const awayStart = this.toCanvas(92, 50);
        const awayEnd = this.toCanvas(58, 50);
        ctx.strokeStyle = "rgba(255,107,123,0.5)";
        ctx.lineWidth = 2.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(awayStart.x, awayStart.y);
        ctx.lineTo(awayEnd.x, awayEnd.y);
        ctx.stroke();
        const aAngle = Math.atan2(awayEnd.y - awayStart.y, awayEnd.x - awayStart.x);
        ctx.beginPath();
        ctx.moveTo(awayEnd.x, awayEnd.y);
        ctx.lineTo(awayEnd.x - 10 * Math.cos(aAngle - Math.PI / 6), awayEnd.y - 10 * Math.sin(aAngle - Math.PI / 6));
        ctx.moveTo(awayEnd.x, awayEnd.y);
        ctx.lineTo(awayEnd.x - 10 * Math.cos(aAngle + Math.PI / 6), awayEnd.y - 10 * Math.sin(aAngle + Math.PI / 6));
        ctx.stroke();
        ctx.setLineDash([]);
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

    /* ── Animation Trails ──────────────────────────────────────────── */
    _drawTrails() {
        if (!this._trailPositions || this._trailPositions.size === 0) return;
        const ctx = this.ctx;
        const maxTrail = 10;
        for (const [objId, positions] of this._trailPositions) {
            if (!positions || positions.length < 2) continue;
            // Find the object to get its color
            const obj = this.project.objects.find((o) => o.id === objId);
            if (!obj) continue;
            const baseColor = obj.color || "#ffffff";
            const isBall = obj.type === "ball";
            const r = (isBall ? obj.radius * 0.6 : obj.radius * 0.5) * this.scale;

            for (let i = 0; i < positions.length; i++) {
                const pct = (i + 1) / (maxTrail + 1); // 0..1 opacity
                const alpha = pct * 0.5; // fading from 0.05 to 0.5
                const pos = this.toCanvas(positions[i].x, positions[i].y);
                ctx.globalAlpha = alpha;
                ctx.fillStyle = baseColor;
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, r * pct, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.globalAlpha = 1;
        }
    },

    _drawBallDragTrail() {
        if (!this._ballDragTrail || this._ballDragTrail.length < 2) return;
        const ctx = this.ctx;
        const maxLen = 3;
        const trail = this._ballDragTrail.slice(-maxLen);
        for (let i = 0; i < trail.length; i++) {
            const pct = (i + 1) / (maxLen + 1);
            const alpha = pct * 0.35;
            const pos = this.toCanvas(trail[i].x, trail[i].y);
            ctx.globalAlpha = alpha;
            ctx.fillStyle = "#ffffff";
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 2 * this.scale * pct, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.globalAlpha = 1;
    },

    _collectTrailPositions() {
        if (!this.showTrails || !this.project || !this.project.objects) return;
        const maxTrail = 10;
        for (const obj of this.project.objects) {
            if (obj.type !== "player" && obj.type !== "ball") continue;
            if (!this._trailPositions.has(obj.id)) {
                this._trailPositions.set(obj.id, []);
            }
            const arr = this._trailPositions.get(obj.id);
            arr.push({ x: obj.x, y: obj.y });
            if (arr.length > maxTrail) arr.shift();
        }
    },

    /* ── Object Path Visualization ──────────────────────────────────── */
    _drawObjectPaths() {
        if (!this.project || !this.project.objects) return;
        const ctx = this.ctx;
        const frames = this.project.frames;
        if (!frames || frames.length < 2) return;
        const curIdx = this.animationState.currentFrame || 0;
        const nextIdx = (curIdx + 1) % frames.length;
        const curFrame = frames[curIdx];
        const nextFrame = frames[nextIdx];
        if (!curFrame || !nextFrame) return;

        for (const toObj of (nextFrame.objects || [])) {
            if (!toObj.pathPoints || toObj.pathPoints.length === 0) continue;
            const fromObj = (curFrame.objects || []).find(o => o.id === toObj.id);
            if (!fromObj) continue;

            // Build full path: from -> pathPoints -> to
            const allPoints = [
                { x: fromObj.x, y: fromObj.y },
                ...toObj.pathPoints.map(p => ({ x: p.x, y: p.y })),
                { x: toObj.x, y: toObj.y },
            ];
            if (allPoints.length < 2) continue;

            // Draw the path
            ctx.save();
            ctx.strokeStyle = "rgba(255,255,100,0.35)";
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            const sp = this.toCanvas(allPoints[0].x, allPoints[0].y);
            ctx.moveTo(sp.x, sp.y);

            if (toObj.pathType === "curved" && allPoints.length > 2) {
                // Draw piecewise bezier
                for (let i = 0; i < allPoints.length - 1; i++) {
                    const p0 = allPoints[i];
                    const p1 = allPoints[i + 1];
                    const cp = TACTICAL_BOARD._autoControlPoint(p0, p1);
                    const cpC = this.toCanvas(cp.x, cp.y);
                    const p1C = this.toCanvas(p1.x, p1.y);
                    ctx.quadraticCurveTo(cpC.x, cpC.y, p1C.x, p1C.y);
                }
            } else {
                // Draw linear segments
                for (let i = 1; i < allPoints.length; i++) {
                    const p = this.toCanvas(allPoints[i].x, allPoints[i].y);
                    ctx.lineTo(p.x, p.y);
                }
            }
            ctx.stroke();
            ctx.setLineDash([]);

            // Draw path point markers
            for (let i = 1; i < allPoints.length - 1; i++) {
                const pp = this.toCanvas(allPoints[i].x, allPoints[i].y);
                ctx.beginPath();
                ctx.arc(pp.x, pp.y, 3, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(255,255,100,0.6)";
                ctx.fill();
                ctx.strokeStyle = "rgba(255,255,100,0.8)";
                ctx.lineWidth = 1;
                ctx.stroke();
            }

            ctx.restore();
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

        // Focus ring: thicker, more visible outline for keyboard navigation
        var isFocus = !!this._focusRingActive;
        var ringColor = isFocus ? "#00bcd4" : "#ffd700";
        var ringWidth = isFocus ? 3 : 2;

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
            ctx.strokeStyle = ringColor;
            ctx.lineWidth = ringWidth;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.arc(mx, my, r, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
        } else if (obj.type === "zone" || obj.type === "rect") {
            const tl = this.toCanvas(obj.x, obj.y);
            const w = obj.width * this.scale;
            const h = obj.height * this.scale;
            ctx.strokeStyle = ringColor;
            ctx.lineWidth = ringWidth;
            ctx.setLineDash([4, 4]);
            ctx.strokeRect(tl.x - 3, tl.y - 3, w + 6, h + 6);
            ctx.setLineDash([]);
        } else if (obj.type === "ellipse") {
            const pos = this.toCanvas(obj.x, obj.y);
            const rx = obj.rx * this.scale + 4;
            const ry = obj.ry * this.scale + 4;
            ctx.strokeStyle = ringColor;
            ctx.lineWidth = ringWidth;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.ellipse(pos.x, pos.y, rx, ry, 0, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
        } else {
            const pos = this.toCanvas(obj.x, obj.y);
            const r = (obj.radius || 3) * this.scale + 4;
            ctx.strokeStyle = ringColor;
            ctx.lineWidth = ringWidth;
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
            } else if (e.key === "Tab" && this.project && this.canvas && document.activeElement === this.canvas) {
                // Tab cycles through objects on the canvas
                e.preventDefault();
                var objs = (this.project.objects || []).filter(function(o) { return o.visible !== false; });
                if (objs.length === 0) return;
                var idx = -1;
                if (this.selectedObject) {
                    idx = objs.findIndex(function(o) { return o.id === this.selectedObject.id; }.bind(this));
                }
                var next = e.shiftKey
                    ? (idx <= 0 ? objs.length - 1 : idx - 1)
                    : (idx + 1) % objs.length;
                this.selectedObject = objs[next];
                this._focusRingActive = true;
                this.render();
                this._announceObject(this.selectedObject);
            } else if (e.key === "Enter" && this._focusRingActive && this.selectedObject) {
                // Enter confirms selection of the focused object
                e.preventDefault();
                this._announceObject(this.selectedObject, "selected");
            } else if (e.key === "Escape" && this._focusRingActive) {
                this._focusRingActive = false;
                this.selectedObject = null;
                this.render();
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

        // Event marker mode: place marker at click position
        if (this.drawingMode === "event-marker") {
            this.pushUndo();
            const markerType = this._eventMarkerType || "press";
            const marker = TACTICAL_BOARD.createEventMarker(x, y, markerType);
            this.project.objects.push(marker);
            this.selectedObject = marker;
            this.render();
            if (this.onChange) this.onChange();
            return;
        }

        // Path edit mode: add path point to selected object
        if (this._pathEditMode && this._pathEditObjectId) {
            const targetObj = this.project.objects.find(o => o.id === this._pathEditObjectId);
            if (targetObj && (targetObj.type === "player" || targetObj.type === "ball")) {
                if (!targetObj.pathPoints) targetObj.pathPoints = [];
                targetObj.pathPoints.push({ x, y });
                this.render();
                if (this.onChange) this.onChange();
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
        // Notify selection change for UI sync
        if (this.onSelectionChange) this.onSelectionChange(found);
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

        // Track ball drag trail
        if (this.selectedObject.type === "ball") {
            this._ballDragTrail.push({ x: this.selectedObject.x, y: this.selectedObject.y });
            if (this._ballDragTrail.length > 3) this._ballDragTrail.shift();
        }

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
        this._ballDragTrail = [];
        if (this.onChange) this.onChange();
    },

    /* ── Double-click: edit jersey number ──────────────────────────── */
    /* ── Double-click: open player detail panel ────────────────────── */
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
        if (!found) {
            this._closePlayerDetailPanel();
            return;
        }
        this._showPlayerDetailPanel(found, cx, cy, e.clientX, e.clientY);
    },

    /* ── Player Detail Panel ───────────────────────────────────────── */
    _initPlayerDetailPanel() {
        if (this._playerDetailPanelEl) return;
        const el = document.createElement("div");
        el.id = "player-detail-panel";
        el.style.cssText = "position:fixed;display:none;z-index:10001;" +
            "background:rgba(16,20,32,0.96);backdrop-filter:blur(16px);border:1px solid rgba(124,168,255,0.35);" +
            "border-radius:10px;padding:14px 16px;color:#e0e6f0;font:13px/1.4 Inter,sans-serif;" +
            "box-shadow:0 8px 32px rgba(0,0,0,0.6);width:280px;";
        document.body.appendChild(el);
        this._playerDetailPanelEl = el;
        this._playerDetailPanelTarget = null;

        // Close on click elsewhere
        this._panelOutsideClickHandler = (ev) => {
            if (this._playerDetailPanelEl && this._playerDetailPanelEl.style.display !== "none") {
                if (!this._playerDetailPanelEl.contains(ev.target) && this.canvas && !this.canvas.contains(ev.target)) {
                    this._closePlayerDetailPanel();
                }
            }
        };
        document.addEventListener("mousedown", this._panelOutsideClickHandler);

        // Close on Escape
        this._panelEscapeHandler = (ev) => {
            if (ev.key === "Escape") this._closePlayerDetailPanel();
        };
        document.addEventListener("keydown", this._panelEscapeHandler);
    },

    _showPlayerDetailPanel(obj, canvasX, canvasY, clientX, clientY) {
        this._initPlayerDetailPanel();
        this._playerDetailPanelTarget = obj;
        const el = this._playerDetailPanelEl;

        const name = obj.label || "";
        const num = obj.number || 0;
        const role = obj.label || "CB";
        const team = obj.team || "home";
        const notes = obj.notes || "";
        const shape = (obj.appearance && obj.appearance.shape) || "circle";
        const size = (obj.appearance && obj.appearance.size) || 3;
        const opacity = (obj.appearance && typeof obj.appearance.opacity === "number") ? obj.appearance.opacity : 1.0;

        el.innerHTML = `
            <div style="font-weight:700;font-size:14px;margin-bottom:10px;color:#7ca8ff">Player Detail</div>
            <div style="margin-bottom:6px">
                <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Name</label>
                <input type="text" id="_pd_name" value="${this._escAttr(name)}" style="width:100%;padding:4px 6px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:#e0e6f0;font:13px/1 Inter,sans-serif;outline:none">
            </div>
            <div style="display:flex;gap:8px;margin-bottom:6px">
                <div style="flex:1">
                    <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Number</label>
                    <input type="number" id="_pd_number" min="0" max="99" value="${num}" style="width:100%;padding:4px 6px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:#e0e6f0;font:13px/1 Inter,sans-serif;outline:none">
                </div>
                <div style="flex:1">
                    <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Position</label>
                    <select id="_pd_position" style="width:100%;padding:4px 6px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:#e0e6f0;font:13px/1 Inter,sans-serif;outline:none">
                        ${["GK","CB","FB","DM","CM","AM","W","ST"].map(p => `<option value="${p}" ${role===p?"selected":""}>${p}</option>`).join("")}
                    </select>
                </div>
            </div>
            <div style="margin-bottom:6px">
                <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Team</label>
                <select id="_pd_team" style="width:100%;padding:4px 6px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:#e0e6f0;font:13px/1 Inter,sans-serif;outline:none">
                    <option value="home" ${team==="home"?"selected":""}>Home</option>
                    <option value="away" ${team==="away"?"selected":""}>Away</option>
                </select>
            </div>
            <div style="display:flex;gap:8px;margin-bottom:6px">
                <div style="flex:1">
                    <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Shape</label>
                    <select id="_pd_shape" style="width:100%;padding:4px 6px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:#e0e6f0;font:13px/1 Inter,sans-serif;outline:none">
                        ${["circle","square","triangle","diamond"].map(s => `<option value="${s}" ${shape===s?"selected":""}>${s}</option>`).join("")}
                    </select>
                </div>
                <div style="flex:1">
                    <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Size (${size})</label>
                    <input type="range" id="_pd_size" min="1" max="5" step="1" value="${size}" style="width:100%;accent-color:#7ca8ff">
                </div>
            </div>
            <div style="margin-bottom:6px">
                <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Opacity (${opacity.toFixed(1)})</label>
                <input type="range" id="_pd_opacity" min="0.3" max="1.0" step="0.1" value="${opacity}" style="width:100%;accent-color:#7ca8ff">
            </div>
            <div style="margin-bottom:10px">
                <label style="display:block;font-size:11px;color:#8892a4;margin-bottom:2px">Notes</label>
                <textarea id="_pd_notes" rows="3" style="width:100%;padding:4px 6px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:#e0e6f0;font:12px/1.3 Inter,sans-serif;outline:none;resize:vertical">${this._escHtml(notes)}</textarea>
            </div>
            <div style="display:flex;gap:8px;justify-content:flex-end">
                <button id="_pd_cancel" style="padding:5px 14px;border:1px solid rgba(255,255,255,0.2);border-radius:5px;background:transparent;color:#c0c8d8;cursor:pointer;font:12px/1 Inter,sans-serif">Cancel</button>
                <button id="_pd_save" style="padding:5px 14px;border:none;border-radius:5px;background:#7ca8ff;color:#0a0e1a;cursor:pointer;font:12px/1 Inter,sans-serif;font-weight:600">Save</button>
            </div>
        `;

        // Position the panel
        const panelW = 280;
        const panelH = 420;
        let left = clientX + 16;
        let top = clientY - 20;
        if (left + panelW > window.innerWidth - 10) left = clientX - panelW - 16;
        if (top + panelH > window.innerHeight - 10) top = window.innerHeight - panelH - 10;
        if (top < 10) top = 10;
        el.style.left = left + "px";
        el.style.top = top + "px";
        el.style.display = "block";

        // Update labels on range inputs
        const sizeInput = el.querySelector("#_pd_size");
        const opacityInput = el.querySelector("#_pd_opacity");
        if (sizeInput) {
            sizeInput.addEventListener("input", () => {
                const lbl = sizeInput.previousElementSibling;
                if (lbl) lbl.textContent = `Size (${sizeInput.value})`;
            });
        }
        if (opacityInput) {
            opacityInput.addEventListener("input", () => {
                const lbl = opacityInput.previousElementSibling;
                if (lbl) lbl.textContent = `Opacity (${parseFloat(opacityInput.value).toFixed(1)})`;
            });
        }

        // Save handler
        el.querySelector("#_pd_save").addEventListener("click", () => {
            const target = this._playerDetailPanelTarget;
            if (!target) return;
            this.pushUndo();
            const newName = el.querySelector("#_pd_name").value.trim();
            const newNum = parseInt(el.querySelector("#_pd_number").value, 10);
            const newPosition = el.querySelector("#_pd_position").value;
            const newTeam = el.querySelector("#_pd_team").value;
            const newShape = el.querySelector("#_pd_shape").value;
            const newSize = parseInt(el.querySelector("#_pd_size").value, 10);
            const newOpacity = parseFloat(el.querySelector("#_pd_opacity").value);
            const newNotes = el.querySelector("#_pd_notes").value;

            target.label = newName;
            if (!isNaN(newNum) && newNum >= 0 && newNum <= 99) target.number = newNum;
            // Update label to position role if name is empty
            if (!target.label) target.label = newPosition;
            target.team = newTeam;
            if (target.team === "away") target.color = "#ff6b7b";
            else target.color = "#7ca8ff";
            if (!target.appearance) target.appearance = {};
            target.appearance.shape = ["circle","square","triangle","diamond"].includes(newShape) ? newShape : "circle";
            target.appearance.size = Math.max(1, Math.min(5, newSize || 3));
            target.appearance.opacity = Math.max(0.3, Math.min(1.0, isNaN(newOpacity) ? 1.0 : newOpacity));
            target.radius = target.appearance.size;
            target.notes = String(newNotes || "").slice(0, 500);
            this._closePlayerDetailPanel();
            this.render();
            if (this.onChange) this.onChange();
        });

        // Cancel handler
        el.querySelector("#_pd_cancel").addEventListener("click", () => {
            this._closePlayerDetailPanel();
        });
    },

    _closePlayerDetailPanel() {
        if (this._playerDetailPanelEl) {
            this._playerDetailPanelEl.style.display = "none";
        }
        this._playerDetailPanelTarget = null;
    },

    _escAttr(s) {
        return String(s || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    },

    _escHtml(s) {
        return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    },

    /* ── Drawing mode ────────────────────────────────────────────────── */
    setDrawingMode(mode) {
        this.drawingMode = mode; // null | 'arrow' | 'zone' | 'text' | 'event-marker'
        this.drawStart = null;
        this.drawPreview = null;
        this._penPoints = [];
        // Update cursor
        if (this.canvas) {
            if (mode === "text") this.canvas.style.cursor = "text";
            else if (mode === "arrow" || mode === "zone" || mode === "rect" || mode === "ellipse") this.canvas.style.cursor = "crosshair";
            else if (mode === "pen") this.canvas.style.cursor = "crosshair";
            else if (mode === "eraser") this.canvas.style.cursor = "pointer";
            else if (mode === "event-marker") this.canvas.style.cursor = "crosshair";
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
        this._pathEditMode = false;
        this._pathEditObjectId = null;
        this.render();
    },

    /* Path editing methods */
    setPathEditMode(enabled, objectId) {
        this._pathEditMode = !!enabled;
        this._pathEditObjectId = enabled ? objectId : null;
    },

    clearPathPoints(objectId) {
        if (!this.project) return;
        const obj = this.project.objects.find(o => o.id === objectId);
        if (obj && obj.pathPoints) {
            obj.pathPoints = [];
            this.render();
            if (this.onChange) this.onChange();
        }
    },

    setObjectPathType(objectId, pathType) {
        if (!this.project) return;
        const obj = this.project.objects.find(o => o.id === objectId);
        if (obj) {
            obj.pathType = pathType;
            this.render();
            if (this.onChange) this.onChange();
        }
    },

    setObjectEasing(objectId, easing) {
        if (!this.project) return;
        const obj = this.project.objects.find(o => o.id === objectId);
        if (obj) {
            obj.easing = easing;
            if (this.onChange) this.onChange();
        }
    },

    setObjectDelay(objectId, delayMs) {
        if (!this.project) return;
        const obj = this.project.objects.find(o => o.id === objectId);
        if (obj) {
            obj.delay_ms = Math.max(0, Math.round(delayMs || 0));
            if (this.onChange) this.onChange();
        }
    },

    setObjectPause(objectId, pauseMs) {
        if (!this.project) return;
        const obj = this.project.objects.find(o => o.id === objectId);
        if (obj) {
            obj.pause_ms = Math.max(0, Math.round(pauseMs || 0));
            if (this.onChange) this.onChange();
        }
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
        // Clear trail positions
        this._trailPositions.clear();
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
        const animMode = (this.project && this.project.animationMode) || "timing";
        const stepDur = (this.project && this.project.stepDuration) || 1000;

        // Find current frame based on elapsed time
        let totalDuration = 0;
        let fromFrame = 0;
        let toFrame = 0;
        let frameElapsed = 0;

        for (let i = 0; i < frames.length; i++) {
            const dur = (animMode === "step") ? stepDur : (frames[i].duration_ms || 3000);
            if (elapsed < totalDuration + dur) {
                fromFrame = i;
                toFrame = (i + 1) % frames.length;
                frameElapsed = elapsed - totalDuration;
                break;
            }
            totalDuration += dur;
        }

        const fromDur = (animMode === "step") ? stepDur : (frames[fromFrame].duration_ms || 3000);
        const t = Math.min(1, frameElapsed / fromDur);

        // Interpolate (pass frameDuration for delay/pause calculations)
        const fromObjs = frames[fromFrame].objects || [];
        const toObjs = frames[toFrame].objects || [];
        this.project.objects = TACTICAL_BOARD.interpolateObjects(fromObjs, toObjs, t, fromDur);
        // Collect trail positions for animation trails
        this._collectTrailPositions();
        this.render();

        // Update presentation notes overlay
        if (this._presentationMode) {
            this.animationState.currentFrame = fromFrame;
            this._updatePresentationNotes();
        }

        // Check if animation is complete
        let totalAnimDuration;
        if (animMode === "step") {
            totalAnimDuration = frames.length * stepDur;
        } else {
            totalAnimDuration = frames.reduce((sum, f) => sum + (f.duration_ms || 3000), 0);
        }
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
        const animMode = (this.project && this.project.animationMode) || "timing";
        const modeLabel = animMode === "step" ? " [step]" : "";
        if (label) label.textContent = (idx + 1) + " / " + frames.length + modeLabel;
        // Render frame markers with delay/pause indicators
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

                // Show delay/pause indicators for objects in this frame
                const frameObjs = frames[i].objects || [];
                let hasDelay = false, hasPause = false;
                for (const obj of frameObjs) {
                    if (obj.delay_ms > 0) hasDelay = true;
                    if (obj.pause_ms > 0) hasPause = true;
                }
                if (hasDelay || hasPause) {
                    const ind = document.createElement("div");
                    ind.style.cssText = `position:absolute;top:12px;left:${mp}%;transform:translateX(-3px);font-size:8px;line-height:1;color:rgba(255,200,100,0.7)`;
                    ind.textContent = (hasDelay ? "d" : "") + (hasPause ? "p" : "");
                    ind.title = (hasDelay ? "Has delay " : "") + (hasPause ? "Has pause" : "");
                    markers.appendChild(ind);
                }
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
        const attribution = this.project.source_attribution || "ScoutFootball tactical board";
        const w = window.open("", "_blank");
        if (!w) { alert("\u25C6 \u8BF7\u5141\u8BB8\u5F39\u51FA\u7A97\u53E3\u4EE5\u5BFC\u51FAPDF"); return; }
        w.document.write(
            '<!DOCTYPE html><html><head><title>\u6218\u672F\u677F\u5BFC\u51FA</title>' +
            '<style>@media print{body{margin:0}img{max-width:100%;height:auto}}body{margin:20px;text-align:center}</style>' +
            '</head><body>' +
            '<h2 style="font-family:Inter,sans-serif;color:#333">\u6218\u672F\u677F \u2014 Tactical Board</h2>' +
            '<img src="' + dataUrl + '" style="max-width:100%;border:1px solid #ccc;border-radius:4px" />' +
            '<div style="margin-top:8px;font-size:11px;color:#999;font-family:Inter,sans-serif">' + this._escapeNotesHtml(attribution) + ' \u2014 ' + new Date().toISOString().slice(0, 10) + '</div>' +
            '<script>setTimeout(function(){window.print()},500)<\/script>' +
            '</body></html>'
        );
        w.document.close();
    },

    exportPNG(filename, options) {
        if (!this.canvas) return;
        const opts = options || {};
        const crop = opts.crop || "full";
        const transparent = !!opts.transparent;

        // Temporarily remove selection highlight for clean export
        const savedSelection = this.selectedObject;
        this.selectedObject = null;

        let dataUrl;

        if (crop === "full" && !transparent) {
            // Simple case: render as-is
            this._showExportAttribution = true;
            this.render();
            this._showExportAttribution = false;
            dataUrl = this.canvas.toDataURL("image/png");
        } else {
            // Determine crop region in normalized coordinates (0-100 pitch space)
            let cropX1 = 0, cropY1 = 0, cropX2 = 100, cropY2 = 100;
            if (crop === "half-left") {
                cropX1 = -5; cropX2 = 50;
            } else if (crop === "half-right") {
                cropX1 = 50; cropX2 = 105;
            } else if (crop === "center-16:9") {
                // Center crop to 16:9 aspect ratio
                const pitchW = 110; // total canvas units (100 + 5 padding each side)
                const pitchH = 78;
                const targetRatio = 16 / 9;
                const currentRatio = pitchW / pitchH;
                if (currentRatio > targetRatio) {
                    // Too wide, crop width
                    const newW = pitchH * targetRatio;
                    const pad = (pitchW - newW) / 2;
                    cropX1 = pad - 5;
                    cropX2 = 105 - (pad - 5);
                } else {
                    // Too tall, crop height
                    const newH = pitchW / targetRatio;
                    const pad = (pitchH - newH) / 2;
                    cropY1 = pad - 5;
                    cropY2 = 105 - (pad - 5);
                }
            } else if (crop === "square-1:1") {
                // Square crop centered
                const pitchW = 110;
                const pitchH = 78;
                if (pitchW > pitchH) {
                    const pad = (pitchW - pitchH) / 2;
                    cropX1 = pad - 5;
                    cropX2 = 105 - (pad - 5);
                } else {
                    const pad = (pitchH - pitchW) / 2;
                    cropY1 = pad - 5;
                    cropY2 = 105 - (pad - 5);
                }
            }

            // Convert crop region to canvas pixels
            const tl = this.toCanvas(cropX1, cropY1);
            const br = this.toCanvas(cropX2, cropY2);
            const cropW = Math.round(br.x - tl.x);
            const cropH = Math.round(br.y - tl.y);
            const dpr = window.devicePixelRatio || 1;

            // Render (with or without background)
            if (transparent) {
                // Clear canvas fully (no pitch drawing)
                const w = this.canvas.width / dpr;
                const h = this.canvas.height / dpr;
                this.ctx.clearRect(0, 0, w, h);
                // Draw objects only (no pitch, no grid)
                for (const obj of this.project.objects) {
                    if (!obj.visible) continue;
                    const cf = this.animationState.currentFrame || 0;
                    const vf = Number.isFinite(obj.visibleFrom) ? obj.visibleFrom : 0;
                    const vt = Number.isFinite(obj.visibleTo) ? obj.visibleTo : Infinity;
                    if (cf < vf || cf > vt) continue;
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
                        case "event-marker": this.drawEventMarker(obj); break;
                    }
                }
            } else {
                this._showExportAttribution = true;
                this.render();
                this._showExportAttribution = false;
            }

            // Create offscreen canvas for cropping
            const offscreen = document.createElement("canvas");
            offscreen.width = cropW * dpr;
            offscreen.height = cropH * dpr;
            const offCtx = offscreen.getContext("2d");
            offCtx.drawImage(
                this.canvas,
                tl.x * dpr, tl.y * dpr, cropW * dpr, cropH * dpr,
                0, 0, cropW * dpr, cropH * dpr
            );
            dataUrl = offscreen.toDataURL("image/png");
        }

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
        this._showExportAttribution = true;
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
            this._showExportAttribution = false;
        });
    },

    /* ── GIF Animation Export ──────────────────────────────────────────── */
    exportGIF(filename) {
        if (!this.canvas) return;

        if (typeof GIF === "undefined") {
            alert("\u25C6 GIF export is not available.\n\nThe gif.js library is not loaded.\nPlease check your network connection or use WebM export instead.");
            return;
        }

        if (!this.project || !this.project.frames || this.project.frames.length < 2) {
            alert("\u25C6 No animation frames to export.\n\nPlease add at least two keyframes before exporting.");
            return;
        }

        const self = this;
        const frames = this.project.frames;
        const fps = 10;
        const delay = Math.round(1000 / fps);

        // Save current state
        const savedFrame = this.animationState.currentFrame;
        const savedPlaying = this.animationState.isPlaying;
        if (savedPlaying) this.stop();

        try {
            this._showExportAttribution = true;
            const gif = new GIF({
                workers: 2,
                quality: 10,
                width: this.canvas.width,
                height: this.canvas.height,
                workerScript: "https://cdn.jsdelivr.net/npm/gif.js@0.2.0/dist/gif.worker.js",
            });

            // Capture each frame
            for (let i = 0; i < frames.length; i++) {
                this.animationState.currentFrame = i;
                this._loadFrameForCapture(i);
                this.render();
                const frameDelay = frames[i].duration_ms || 3000;
                const frameCount = Math.max(1, Math.round(frameDelay / delay));
                for (let j = 0; j < frameCount; j++) {
                    gif.addFrame(this.canvas, { copy: true, delay: delay });
                }
            }

            gif.on("finished", function (blob) {
                // Restore state
                self._showExportAttribution = false;
                self.animationState.currentFrame = savedFrame;
                self._loadFrameForCapture(savedFrame);
                self.render();

                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.download = filename || "tactical-animation.gif";
                link.href = url;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                setTimeout(function () { URL.revokeObjectURL(url); }, 5000);
            });

            gif.on("progress", function (p) {
                // Could update a progress indicator; no-op for now
            });

            gif.render();
        } catch (e) {
            // Restore state on error
            this._showExportAttribution = false;
            this.animationState.currentFrame = savedFrame;
            this._loadFrameForCapture(savedFrame);
            this.render();
            alert("\u25C6 GIF export failed: " + e.message + "\n\nPlease try WebM export instead.");
        }
    },

    _loadFrameForCapture(frameIndex) {
        /* Load frame objects for rendering without triggering animation logic. */
        if (!this.project || !this.project.frames) return;
        const frame = this.project.frames[frameIndex];
        if (!frame || !frame.objects) return;
        // Apply frame objects directly to the renderer state
        this.currentObjects = JSON.parse(JSON.stringify(frame.objects));
    },

    /* ── Presentation Mode ───────────────────────────────────────────── */
    togglePresentation() {
        if (this._presentationMode) {
            this.exitPresentation();
        } else {
            this.enterPresentation();
        }
    },

    enterPresentation() {
        this._presentationMode = true;
        const container = document.getElementById("tactical-canvas-container");
        // Hide editing UI
        const view = document.getElementById("view-tactical");
        if (view) {
            const panels = view.querySelectorAll(".table-panel, .filter-row");
            panels.forEach((el) => { el.style.display = "none"; });
            // Hide the left side panel entirely
            const sidePanel = view.querySelector(".table-panel");
            if (sidePanel) sidePanel.style.display = "none";
        }
        // Make canvas container full width
        if (container) {
            container.style.width = "100%";
            container.style.height = "100dvh";
            container.style.minHeight = "100dvh";
        }
        // Hide the layout-2 second column
        if (view) {
            const layout2 = view.querySelector(".layout-2");
            if (layout2) {
                layout2.style.display = "block";
                layout2.style.gridTemplateColumns = "1fr";
            }
        }
        // Request fullscreen on the container
        if (container && container.requestFullscreen) {
            container.requestFullscreen().catch(() => {});
        }
        // Create notes overlay
        this._createPresentationNotes();
        // Update notes for current frame
        this._updatePresentationNotes();
        // Auto-play if frames exist
        if (this.project && this.project.frames && this.project.frames.length >= 2) {
            this.animationState.loop = true;
            this.play();
        }
        // Bind ESC handler
        this._presentationEscHandler = (e) => {
            if (e.key === "Escape") {
                this.exitPresentation();
            }
        };
        document.addEventListener("keydown", this._presentationEscHandler);
        this.resize();
    },

    exitPresentation() {
        this._presentationMode = false;
        // Stop animation
        this.stop();
        // Restore editing UI
        const view = document.getElementById("view-tactical");
        if (view) {
            const panels = view.querySelectorAll(".table-panel, .filter-row");
            panels.forEach((el) => { el.style.display = ""; });
            const layout2 = view.querySelector(".layout-2");
            if (layout2) {
                layout2.style.display = "";
                layout2.style.gridTemplateColumns = "";
            }
        }
        const container = document.getElementById("tactical-canvas-container");
        if (container) {
            container.style.width = "";
            container.style.height = "";
            container.style.minHeight = "";
        }
        // Remove notes overlay
        this._removePresentationNotes();
        // Unbind ESC handler
        if (this._presentationEscHandler) {
            document.removeEventListener("keydown", this._presentationEscHandler);
            this._presentationEscHandler = null;
        }
        // Exit fullscreen
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
        }
        this.resize();
    },

    _createPresentationNotes() {
        if (this._presentationNotesEl) return;
        const container = document.getElementById("tactical-canvas-container");
        if (!container) return;
        const el = document.createElement("div");
        el.id = "presentation-notes-overlay";
        el.style.cssText = "position:absolute;bottom:0;left:0;right:0;padding:16px 24px;" +
            "background:rgba(0,0,0,0.75);backdrop-filter:blur(8px);color:#e0e6f0;" +
            "font:16px/1.5 Inter,sans-serif;text-align:center;z-index:10;" +
            "pointer-events:none;min-height:24px;transition:opacity 0.3s";
        container.style.position = "relative";
        container.appendChild(el);
        this._presentationNotesEl = el;
    },

    _removePresentationNotes() {
        if (this._presentationNotesEl && this._presentationNotesEl.parentNode) {
            this._presentationNotesEl.parentNode.removeChild(this._presentationNotesEl);
        }
        this._presentationNotesEl = null;
    },

    _updatePresentationNotes() {
        if (!this._presentationNotesEl || !this.project || !this.project.frames) return;
        const idx = this.animationState.currentFrame;
        const frame = this.project.frames[idx];
        const notes = frame ? (frame.notes || "") : "";
        // Build HTML: coaching points get styled differently from plain notes
        if (notes) {
            const lines = notes.split("\n").filter(l => l.trim());
            let html = "";
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (line.startsWith("- ")) {
                    // Key point item
                    html += '<div style="text-align:left;max-width:700px;margin:0 auto;padding:1px 0;font-size:14px;color:#c0c8d8">\u25CB ' + this._escapeNotesHtml(line.slice(2)) + '</div>';
                } else if (i === 0) {
                    // Title line
                    html += '<div style="font-size:18px;font-weight:700;margin-bottom:4px;color:#fff">' + this._escapeNotesHtml(line) + '</div>';
                } else {
                    html += '<div style="font-size:14px;color:#b0b8c8;margin:2px 0">' + this._escapeNotesHtml(line) + '</div>';
                }
            }
            this._presentationNotesEl.innerHTML = html;
            this._presentationNotesEl.style.opacity = "1";
        } else {
            this._presentationNotesEl.textContent = "";
            this._presentationNotesEl.style.opacity = "0";
        }
    },

    _escapeNotesHtml(text) {
        return String(text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    },

    /* ── Coaching Notes per frame ────────────────────────────────────── */
    setCurrentFrameNotes(text) {
        if (!this.project || !this.project.frames) return;
        const idx = this.animationState.currentFrame;
        const frame = this.project.frames[idx];
        if (frame) {
            frame.notes = String(text || "");
        }
    },

    getCurrentFrameNotes() {
        if (!this.project || !this.project.frames) return "";
        const idx = this.animationState.currentFrame;
        const frame = this.project.frames[idx];
        return frame ? (frame.notes || "") : "";
    },

    /* ── Event Marker Drawing ────────────────────────────────────────── */
    drawEventMarker(obj) {
        const ctx = this.ctx;
        const pos = this.toCanvas(obj.x, obj.y);
        const r = 3 * this.scale;
        const markerType = obj.markerType || "press";

        // Background circle
        ctx.fillStyle = "rgba(255,200,0,0.85)";
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.5)";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Icon text inside
        ctx.fillStyle = "#000";
        ctx.font = `bold ${Math.max(8, r * 1.1)}px Inter, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const icons = {
            "press": "P",
            "pass": "\u2192",
            "shot": "\u2299",
            "turnover": "X",
            "overlap": "O",
            "underlap": "U",
            "third-man": "3",
            "cover": "\u25A3",
        };
        ctx.fillText(icons[markerType] || "P", pos.x, pos.y);

        // Label below
        if (obj.label) {
            ctx.fillStyle = "#fff";
            ctx.font = `${Math.max(8, 9 * this.scale / 3)}px Inter, sans-serif`;
            ctx.textAlign = "center";
            ctx.fillText(obj.label, pos.x, pos.y + r + 8);
        }
    },

    /* ── Print Mode Export ───────────────────────────────────────────── */
    exportPrint() {
        if (!this.project) return;
        const frames = this.project.frames || [];
        const title = this.project.title || "Tactical Board";
        const attribution = this.project.source_attribution || "ScoutFootball tactical board";

        // Collect unique players across all frames
        const playerMap = new Map();
        for (const frame of frames) {
            for (const obj of (frame.objects || [])) {
                if (obj.type === "player" && obj.label) {
                    const key = obj.label + "|" + obj.number + "|" + obj.team;
                    if (!playerMap.has(key)) {
                        playerMap.set(key, {
                            name: obj.label,
                            number: obj.number || "",
                            team: obj.team || "home",
                        });
                    }
                }
            }
        }
        const players = Array.from(playerMap.values());

        // Phase icons
        const phaseIcons = {
            "buildup": "\u25CE",
            "pressing": "\u25CB",
            "defense": "\u25A3",
            "counter": "\u25B6",
            "set-piece": "\u25C7",
        };

        // Build frame pages
        const savedFrame = this.animationState.currentFrame;
        const savedSelection = this.selectedObject;
        this.selectedObject = null;
        let framePages = "";
        for (let i = 0; i < frames.length; i++) {
            // Render frame
            this.animationState.currentFrame = i;
            if (frames[i].objects && frames[i].objects.length > 0) {
                this.project.objects = JSON.parse(JSON.stringify(frames[i].objects));
            }
            this.render();
            const dataUrl = this.canvas.toDataURL("image/png");

            const notes = frames[i].notes || "";
            const phase = frames[i].phase || "";
            const phaseLabel = phase ? (phaseIcons[phase] || "") + " " + phase : "";
            const trigger = frames[i].trigger || "";
            const roles = frames[i].roles || "";
            const duration = frames[i].duration_ms || 3000;

            let metaHtml = "";
            if (phaseLabel) metaHtml += '<div style="font-size:13px;color:#555;margin:4px 0"><strong>' + this._escapeNotesHtml(phaseLabel) + '</strong></div>';
            if (trigger) metaHtml += '<div style="font-size:12px;color:#666;margin:2px 0">Trigger: ' + this._escapeNotesHtml(trigger) + '</div>';
            if (roles) metaHtml += '<div style="font-size:12px;color:#666;margin:2px 0">Roles: ' + this._escapeNotesHtml(roles) + '</div>';

            let notesHtml = "";
            if (notes) {
                const lines = notes.split("\n").filter(l => l.trim());
                notesHtml = '<div style="margin:8px 0;padding:8px 12px;background:#f9f9f9;border-radius:4px;font-size:13px;line-height:1.6">';
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith("- ")) {
                        notesHtml += '<div style="padding:1px 0;color:#333">\u25CB ' + this._escapeNotesHtml(trimmed.slice(2)) + '</div>';
                    } else {
                        notesHtml += '<div style="padding:1px 0;color:#222;font-weight:600">' + this._escapeNotesHtml(trimmed) + '</div>';
                    }
                }
                notesHtml += '</div>';
            }

            framePages += '<div class="print-frame" style="page-break-inside:avoid;margin:20px 0">';
            framePages += '<h3 style="margin:0 0 4px;font-size:16px;color:#222">' + this._escapeNotesHtml(frames[i].name || ("Frame " + (i + 1))) + ' <span style="font-size:12px;color:#888">(' + duration + 'ms)</span></h3>';
            framePages += metaHtml;
            framePages += '<img src="' + dataUrl + '" style="max-width:100%;border:1px solid #ddd;border-radius:4px" />';
            framePages += notesHtml;
            framePages += '</div>';
        }

        // Restore state
        this.animationState.currentFrame = savedFrame;
        this.selectedObject = savedSelection;
        if (frames[savedFrame] && frames[savedFrame].objects) {
            this.project.objects = JSON.parse(JSON.stringify(frames[savedFrame].objects));
        }
        this.render();

        // Legend HTML
        let legendHtml = "";
        if (players.length > 0) {
            legendHtml = '<div style="margin:16px 0"><h3 style="font-size:15px;color:#222;border-bottom:1px solid #ddd;padding-bottom:4px">Player Legend</h3>';
            legendHtml += '<table style="font-size:13px;width:100%;border-collapse:collapse">';
            legendHtml += '<tr style="background:#f0f0f0"><th style="text-align:left;padding:4px 8px">Name</th><th style="text-align:left;padding:4px 8px">Number</th><th style="text-align:left;padding:4px 8px">Team</th></tr>';
            for (const p of players) {
                const teamLabel = p.team === "away" ? "Away" : "Home";
                legendHtml += '<tr><td style="padding:4px 8px;border-bottom:1px solid #eee">' + this._escapeNotesHtml(p.name) + '</td>';
                legendHtml += '<td style="padding:4px 8px;border-bottom:1px solid #eee">' + (p.number || "-") + '</td>';
                legendHtml += '<td style="padding:4px 8px;border-bottom:1px solid #eee">' + teamLabel + '</td></tr>';
            }
            legendHtml += '</table></div>';
        }

        // Open print window
        const w = window.open("", "_blank");
        if (!w) {
            alert("\u25C6 Please allow pop-ups to use print mode");
            return;
        }
        w.document.write(
            '<!DOCTYPE html><html><head><title>' + this._escapeNotesHtml(title) + '</title>' +
            '<style>' +
            '@media print { body { margin: 0; } .print-frame { page-break-inside: avoid; } }' +
            'body { margin: 20px; font-family: Inter, Arial, sans-serif; color: #222; background: #fff; }' +
            'h1 { font-size: 22px; margin: 0 0 4px; }' +
            '.subtitle { font-size: 13px; color: #888; margin-bottom: 16px; }' +
            '</style></head><body>' +
            '<h1>' + this._escapeNotesHtml(title) + '</h1>' +
            '<div class="subtitle">' + this._escapeNotesHtml(attribution) + '</div>' +
            framePages +
            legendHtml +
            '<div style="margin-top:24px;padding-top:8px;border-top:1px solid #ddd;font-size:11px;color:#999">' +
            'Generated by ' + this._escapeNotesHtml(attribution) + ' \u2014 ' + new Date().toISOString().slice(0, 10) +
            '</div>' +
            '<script>setTimeout(function(){window.print()},600)<\/script>' +
            '</body></html>'
        );
        w.document.close();
    },
};
