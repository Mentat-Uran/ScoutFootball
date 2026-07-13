import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const frontend = join(root, "frontend");
const output = join(root, "dist");
const publicDir = join(output, "public");

await rm(output, { recursive: true, force: true });
await mkdir(publicDir, { recursive: true });
await cp(frontend, publicDir, {
  recursive: true,
  filter: (source) => !source.includes("local-data"),
});

const indexPath = join(publicDir, "index.html");
const index = await readFile(indexPath, "utf8");
const injectedConfig = '<script src="sites-runtime-config.js"></script>\n    <script src="config.js"></script>';
if (!index.includes('<script src="config.js"></script>')) {
  throw new Error("Expected config.js script tag was not found in frontend/index.html");
}
await writeFile(
  indexPath,
  index.replace('<script src="config.js"></script>', injectedConfig),
);

await writeFile(
  join(publicDir, "sites-runtime-config.js"),
  "window.__SCOUTFOOTBALL_STATIC__ = true;\nwindow.__SCOUTFOOTBALL_API__ = \"https://scoutfootball-for-world-cup.onrender.com\";\n",
);

const workerPath = join(output, "server", "index.js");
await mkdir(dirname(workerPath), { recursive: true });
await writeFile(
  workerPath,
  `export default {
  async fetch(request, env) {
    const asset = await env.ASSETS.fetch(request);
    if (asset.status !== 404) return asset;

    const acceptsHtml = (request.headers.get("accept") || "").includes("text/html");
    if (!acceptsHtml) return asset;
    return env.ASSETS.fetch(new Request(new URL("/", request.url), request));
  },
};
`,
);
