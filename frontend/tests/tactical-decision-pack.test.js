"use strict";

import assert from "node:assert/strict";
import test from "node:test";

await import("../tactical-board.js");

const board = globalThis.TACTICAL_BOARD;

test("creates a decision pack with recorded prediction output and provenance", () => {
    const pack = board.createDecisionPack({
        match: { home: "Home FC", away: "Away FC" },
        prediction: {
            status: "available",
            model_type: "dixon_coles",
            model_version: "dc-2.0",
            probabilities: { home_win: 0.51, draw: 0.24, away_win: 0.25 },
            expected_goals: { home: 1.62, away: 1.11 },
            score_matrix: [[0.12, 0.08], [0.11, 0.09]],
            coverage: { status: "ok", summary: "18 teams" },
        },
        provenance: {
            model_run_id: "prediction-run-22",
            input_hash: "abc123",
            lineage_status: "recorded",
        },
        limitations: ["Model context only."],
    });

    assert.equal(pack.schema, "scoutfootball.tactical-decision-pack");
    assert.equal(pack.prediction.status, "available");
    assert.equal(pack.prediction.probabilities.home_win, 0.51);
    assert.equal(pack.prediction.expected_goals.away, 1.11);
    assert.equal(pack.provenance.model_run_id, "prediction-run-22");
    assert.match(board.formatDecisionPackNotes(pack), /Home win: 51%/);
    assert.match(board.formatDecisionPackNotes(pack), /model run prediction-run-22/);
});

test("does not turn an unloaded prediction into fallback probabilities", () => {
    const pack = board.createDecisionPack({
        match: { home: "Home FC", away: "Away FC" },
        prediction: { status: "not_loaded", model_type: "poisson" },
    });

    assert.equal(pack.prediction.status, "not_loaded");
    assert.equal(pack.prediction.probabilities.home_win, null);
    assert.equal(pack.prediction.expected_goals.home, null);
    assert.equal(pack.prediction.score_matrix, null);
    assert.match(board.formatDecisionPackNotes(pack), /not loaded/i);
    assert.doesNotMatch(board.formatDecisionPackNotes(pack), /Home win:/);
});

test("round-trips constrained decision-pack metadata and drops untrusted fields", () => {
    const project = board.createProject("Decision pack import");
    project.metadata = {
        decision_pack: {
            schema: "wrong",
            version: "999",
            match: { home_team: "<img src=x>", away_team: "Away FC" },
            prediction: {
                status: "available",
                probabilities: { home_win: 4, draw: -1, away_win: 0.2 },
                expected_goals: { home: 99, away: -4 },
                score_matrix: Array.from({ length: 14 }, () => Array(14).fill(2)),
                coverage: { status: "ok", summary: "<script>ignored as data</script>" },
            },
            provenance: { input_hash: "hash-1", unsafe: "discard" },
            limitations: ["x".repeat(400)],
            unsafe: { nested: true },
        },
        unsafe: true,
    };

    const imported = board.importJSON(board.exportJSON(project));
    const pack = imported.metadata.decision_pack;

    assert.equal(pack.schema, "scoutfootball.tactical-decision-pack");
    assert.equal(pack.version, "1.0.0");
    assert.equal(pack.prediction.probabilities.home_win, 1);
    assert.equal(pack.prediction.probabilities.draw, 0);
    assert.equal(pack.prediction.expected_goals.home, 20);
    assert.equal(pack.prediction.score_matrix.length, 12);
    assert.equal(pack.prediction.score_matrix[0].length, 12);
    assert.equal(pack.provenance.unsafe, undefined);
    assert.equal(pack.limitations[0].length, 120);
    assert.equal(Object.hasOwn(imported.metadata, "unsafe"), false);
});
