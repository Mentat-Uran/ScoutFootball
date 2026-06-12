// Runtime config:
// - Vercel demo defaults to static JSON + hosted backend.
// - Local/LAN deployments default to same-origin backend mode.
(function configureScoutFootballRuntime() {
    const host = window.location.hostname || "";
    const isVercelDemo =
        host === "scoutfootball.vercel.app"
        || host === "scoutfootball-for-world-cup.vercel.app"
        || host.endsWith(".vercel.app");

    if (typeof window.__SCOUTFOOTBALL_STATIC__ !== "boolean") {
        window.__SCOUTFOOTBALL_STATIC__ = isVercelDemo;
    }

    if (!window.__SCOUTFOOTBALL_API__) {
        window.__SCOUTFOOTBALL_API__ = isVercelDemo
            ? "https://scoutfootball-for-world-cup.onrender.com"
            : window.location.origin;
    }
}());
