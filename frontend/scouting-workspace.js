(function initScoutingWorkspace(root) {
    "use strict";

    const SCHEMA = "scoutfootball.scouting-workspace";
    const VERSION = "1.0.0";
    const MAX_BYTES = 1_000_000;
    const MAX_ENTRIES = 1_000;
    const MAX_PLAYERS = 500;
    const MAX_KEY_LENGTH = 180;
    const MAX_NOTE_LENGTH = 2_000;
    const VALID_STATUSES = new Set(["pending", "reviewing", "approved", "rejected"]);
    const FORBIDDEN_KEYS = new Set(["__proto__", "prototype", "constructor"]);

    function isRecord(value) {
        return value !== null && typeof value === "object" && !Array.isArray(value);
    }

    function cleanString(value, maxLength) {
        return String(value == null ? "" : value).trim().slice(0, maxLength);
    }

    function cleanTimestamp(value, fallback) {
        const candidate = cleanString(value, 64);
        const parsed = Date.parse(candidate);
        return Number.isFinite(parsed) ? new Date(parsed).toISOString() : fallback;
    }

    function cleanKey(value) {
        const key = cleanString(value, MAX_KEY_LENGTH);
        if (!key || FORBIDDEN_KEYS.has(key)) return "";
        return key;
    }

    function cleanStatusMap(value) {
        const output = Object.create(null);
        if (!isRecord(value)) return output;
        for (const [rawKey, rawStatus] of Object.entries(value).slice(0, MAX_ENTRIES)) {
            const key = cleanKey(rawKey);
            const status = cleanString(rawStatus, 32).toLowerCase();
            if (key && VALID_STATUSES.has(status)) output[key] = status;
        }
        return output;
    }

    function cleanNoteMap(value) {
        const output = Object.create(null);
        if (!isRecord(value)) return output;
        for (const [rawKey, rawNote] of Object.entries(value).slice(0, MAX_ENTRIES)) {
            const key = cleanKey(rawKey);
            const note = cleanString(rawNote, MAX_NOTE_LENGTH);
            if (key && note) output[key] = note;
        }
        return output;
    }

    function cleanPlayerList(value) {
        if (!Array.isArray(value)) return [];
        const output = [];
        const seen = new Set();
        for (const row of value.slice(0, MAX_PLAYERS)) {
            if (!isRecord(row)) continue;
            const name = cleanString(row.player_name || row.name, MAX_KEY_LENGTH);
            const playerId = cleanString(row.player_id, 96);
            const key = cleanKey(row.key || playerId || name);
            const dedupeKey = key.toLowerCase();
            if (!key || seen.has(dedupeKey)) continue;
            seen.add(dedupeKey);
            const ratingValue = Number(row.optimized_score ?? row.rating);
            output.push({
                key,
                player_id: playerId,
                name,
                team: cleanString(row.team, MAX_KEY_LENGTH),
                position: cleanString(row.position_group || row.position, 32),
                rating: Number.isFinite(ratingValue) ? Math.max(0, Math.min(100, ratingValue)) : 0,
            });
        }
        return output;
    }

    function cleanStringList(value, maxItems, maxLength) {
        if (!Array.isArray(value)) return [];
        const output = [];
        const seen = new Set();
        for (const item of value.slice(0, maxItems)) {
            const cleaned = cleanString(item, maxLength);
            if (!cleaned || seen.has(cleaned)) continue;
            seen.add(cleaned);
            output.push(cleaned);
        }
        return output;
    }

    function createWorkspace(state) {
        const source = isRecord(state) ? state : {};
        const now = cleanTimestamp(source.exported_at, new Date().toISOString());
        const createdAt = cleanTimestamp(source.created_at, now);
        return {
            schema: SCHEMA,
            version: VERSION,
            exported_at: now,
            audit: {
                created_at: createdAt,
                updated_at: now,
                device_scope: "browser-local",
                source: "manual-export",
                app_version: cleanString(source.app_version, 32),
            },
            source: {
                rating_snapshot_ids: cleanStringList(source.rating_snapshot_ids, MAX_ENTRIES, 180),
                attribution: "ScoutFootball local scouting decisions; server queues remain read-only",
            },
            review: {
                statuses: cleanStatusMap(source.review_statuses),
                shortlist_notes: cleanNoteMap(source.shortlist_notes),
                watchlist_notes: cleanNoteMap(source.watchlist_notes),
            },
            selections: {
                watchlist: cleanPlayerList(source.watchlist),
                shortlist: cleanPlayerList(source.shortlist),
            },
            watchlist_snapshot: {
                player_keys: cleanStringList(source.snapshot_player_keys, MAX_PLAYERS, MAX_KEY_LENGTH),
                saved_at: cleanTimestamp(source.snapshot_saved_at, null),
            },
        };
    }

    function normalizeWorkspace(input) {
        if (!isRecord(input)) throw new Error("workspace_not_object");
        if (input.schema !== SCHEMA) throw new Error("workspace_schema_invalid");
        const version = cleanString(input.version, 32);
        if (!/^1\./.test(version)) throw new Error("workspace_version_unsupported");

        const audit = isRecord(input.audit) ? input.audit : {};
        const source = isRecord(input.source) ? input.source : {};
        const review = isRecord(input.review) ? input.review : {};
        const selections = isRecord(input.selections) ? input.selections : {};
        const snapshot = isRecord(input.watchlist_snapshot) ? input.watchlist_snapshot : {};
        return createWorkspace({
            exported_at: input.exported_at,
            created_at: audit.created_at,
            app_version: audit.app_version,
            rating_snapshot_ids: source.rating_snapshot_ids,
            review_statuses: review.statuses,
            shortlist_notes: review.shortlist_notes,
            watchlist_notes: review.watchlist_notes,
            watchlist: selections.watchlist,
            shortlist: selections.shortlist,
            snapshot_player_keys: snapshot.player_keys,
            snapshot_saved_at: snapshot.saved_at,
        });
    }

    function parseWorkspace(raw) {
        const text = typeof raw === "string" ? raw : JSON.stringify(raw);
        if (text.length > MAX_BYTES) throw new Error("workspace_too_large");
        let parsed;
        try {
            parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
        } catch {
            throw new Error("workspace_json_invalid");
        }
        return normalizeWorkspace(parsed);
    }

    function toLocalState(workspace) {
        const normalized = normalizeWorkspace(workspace);
        return {
            created_at: normalized.audit.created_at,
            review_statuses: normalized.review.statuses,
            shortlist_notes: normalized.review.shortlist_notes,
            watchlist_notes: normalized.review.watchlist_notes,
            watchlist: normalized.selections.watchlist,
            shortlist: normalized.selections.shortlist,
            snapshot_player_keys: normalized.watchlist_snapshot.player_keys,
            snapshot_saved_at: normalized.watchlist_snapshot.saved_at,
        };
    }

    function serializeWorkspace(workspace) {
        return JSON.stringify(normalizeWorkspace(workspace), null, 2);
    }

    root.SCOUTING_WORKSPACE = Object.freeze({
        SCHEMA,
        VERSION,
        MAX_BYTES,
        createWorkspace,
        normalizeWorkspace,
        parseWorkspace,
        serializeWorkspace,
        toLocalState,
    });
})(globalThis);
