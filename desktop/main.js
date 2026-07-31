/* ScoutFootball Desktop — Electron Main Process */

const { app, BrowserWindow, dialog, shell, Menu, Tray, nativeImage } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");

// ── Configuration ──────────────────────────────────────────────
const API_PORT = 8600;
const FRONTEND_PORT = 8601;
const APP_VERSION = app.getVersion();

let mainWindow = null;
let backendProcess = null;
let tray = null;
let isQuitting = false;

// ── Logging ────────────────────────────────────────────────────
const logDir = path.join(app.getPath("userData"), "logs");
fs.mkdirSync(logDir, { recursive: true });
const logFile = path.join(logDir, "scoutfootball.log");

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}\n`;
  fs.appendFileSync(logFile, line);
  console.log(line.trim());
}

// ── Path Resolution ────────────────────────────────────────────
function getBasePath() {
  if (app.isPackaged) {
    // In packaged app, resources are in extraResources
    return process.resourcesPath;
  }
  return path.join(__dirname);
}

function getFrontendDir() {
  // Frontend files are bundled in app.asar (via "files" in package.json)
  // __dirname resolves correctly inside asar
  const asarFrontend = path.join(__dirname, "frontend");
  if (fs.existsSync(asarFrontend)) {
    return asarFrontend;
  }
  // Fallback: check resources path
  const resFrontend = path.join(process.resourcesPath, "frontend");
  if (fs.existsSync(resFrontend)) {
    return resFrontend;
  }
  // Dev mode fallback
  return path.join(__dirname, "frontend");
}

function getBackendPath() {
  const isDev = !app.isPackaged;
  if (isDev) {
    return {
      command: "python3",
      args: ["-m", "scoutfootball", "serve", "--port", String(API_PORT)],
      cwd: path.join(__dirname, ".."),
      env: { ...process.env, PYTHONPATH: path.join(__dirname, "..", "src") },
    };
  }

  // Production: backend executable is in extraResources/backend/
  const platform = process.platform;
  const ext = platform === "win32" ? ".exe" : "";
  const backendExe = path.join(process.resourcesPath, "backend", `scoutfootball-server${ext}`);

  if (!fs.existsSync(backendExe)) {
    log(`Backend executable not found: ${backendExe}`);
    return null;
  }

  return {
    command: backendExe,
    args: ["--port", String(API_PORT)],
    cwd: process.resourcesPath,
    env: {
      ...process.env,
      SCOUTFOOTBALL_DATA_ROOT: path.join(process.resourcesPath, "data"),
    },
  };
}

// ── Backend Management ─────────────────────────────────────────
function startBackend() {
  const config = getBackendPath();
  if (!config) {
    log("Cannot start backend: no executable found");
    return false;
  }

  log(`Starting backend: ${config.command}`);
  log(`Backend cwd: ${config.cwd}`);
  log(`Backend data root: ${config.env.SCOUTFOOTBALL_DATA_ROOT || "default"}`);

  // Diagnostic: list resources directory contents when packaged
  if (app.isPackaged) {
    try {
      const resContents = fs.readdirSync(process.resourcesPath);
      log(`Resources dir contents: ${resContents.join(", ")}`);
      const backendDir = path.join(process.resourcesPath, "backend");
      if (fs.existsSync(backendDir)) {
        log(`Backend dir contents: ${fs.readdirSync(backendDir).join(", ")}`);
      }
      const dataDir = path.join(process.resourcesPath, "data");
      if (fs.existsSync(dataDir)) {
        const dataSubdirs = fs.readdirSync(dataDir);
        log(`Data dir contents: ${dataSubdirs.join(", ")}`);
      }
    } catch (e) {
      log(`Cannot list resources: ${e.message}`);
    }
  }

  try {
    backendProcess = spawn(config.command, config.args, {
      cwd: config.cwd,
      env: config.env,
      stdio: ["pipe", "pipe", "pipe"],
    });

    backendProcess.stdout.on("data", (data) => {
      log(`[backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr.on("data", (data) => {
      log(`[backend:err] ${data.toString().trim()}`);
    });

    backendProcess.on("close", (code) => {
      log(`Backend process exited with code ${code}`);
      backendProcess = null;
    });

    backendProcess.on("error", (err) => {
      log(`Backend process error: ${err.message}`);
      backendProcess = null;
    });

    return true;
  } catch (err) {
    log(`Failed to start backend: ${err.message}`);
    return false;
  }
}

function stopBackend() {
  if (backendProcess) {
    log("Stopping backend...");
    backendProcess.kill("SIGTERM");
    setTimeout(() => {
      if (backendProcess) {
        backendProcess.kill("SIGKILL");
      }
    }, 5000);
  }
}

// ── Health Check ───────────────────────────────────────────────
function checkApiHealth() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${API_PORT}/health`, { timeout: 2000 }, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(null);
        }
      });
    });
    req.on("error", () => resolve(null));
    req.on("timeout", () => {
      req.destroy();
      resolve(null);
    });
  });
}

async function waitForBackend(maxWaitMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const health = await checkApiHealth();
    if (health && health.status === "ok") {
      log("Backend is ready");
      return true;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  log("Backend did not become ready in time");
  return false;
}

// ── Frontend Server ────────────────────────────────────────────
let frontendServer = null;

function startFrontendServer() {
  const frontendDir = getFrontendDir();
  log(`Frontend directory: ${frontendDir}`);
  log(`Frontend exists: ${fs.existsSync(frontendDir)}`);

  if (!fs.existsSync(frontendDir)) {
    log(`Frontend directory not found: ${frontendDir}`);
    return false;
  }

  // List files in frontend dir for debugging
  try {
    const files = fs.readdirSync(frontendDir);
    log(`Frontend files: ${files.join(", ")}`);
  } catch (e) {
    log(`Cannot list frontend dir: ${e.message}`);
  }

  const handler = (req, res) => {
    let urlPath = req.url.split("?")[0];
    if (urlPath === "/") urlPath = "/index.html";

    const filePath = path.join(frontendDir, urlPath);
    const ext = path.extname(filePath);
    const mimeTypes = {
      ".html": "text/html",
      ".js": "application/javascript",
      ".css": "text/css",
      ".json": "application/json",
      ".png": "image/png",
      ".svg": "image/svg+xml",
      ".ico": "image/x-icon",
      ".parquet": "application/octet-stream",
    };

    fs.readFile(filePath, (err, data) => {
      if (err) {
        // Fallback to index.html for SPA routing
        fs.readFile(path.join(frontendDir, "index.html"), (err2, data2) => {
          if (err2) {
            res.writeHead(404);
            res.end("Not Found");
          } else {
            res.writeHead(200, { "Content-Type": "text/html" });
            res.end(data2);
          }
        });
      } else {
        res.writeHead(200, { "Content-Type": mimeTypes[ext] || "application/octet-stream" });
        res.end(data);
      }
    });
  };

  frontendServer = http.createServer(handler);
  frontendServer.listen(FRONTEND_PORT, "127.0.0.1", () => {
    log(`Frontend server listening on http://127.0.0.1:${FRONTEND_PORT}`);
  });

  return true;
}

function stopFrontendServer() {
  if (frontendServer) {
    frontendServer.close();
    frontendServer = null;
  }
}

// ── Window Management ──────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: `ScoutFootball v${APP_VERSION}`,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    backgroundColor: "#eef1f5",
    show: false,
  });

  const frontendUrl = `http://127.0.0.1:${FRONTEND_PORT}`;
  log(`Loading frontend: ${frontendUrl}`);
  mainWindow.loadURL(frontendUrl);

  mainWindow.once("ready-to-show", () => {
    log("Window ready-to-show");
    mainWindow.show();
  });

  // Debug: log web contents events
  mainWindow.webContents.on("did-fail-load", (event, errorCode, errorDesc) => {
    log(`Frontend load failed: ${errorCode} - ${errorDesc}`);
  });

  mainWindow.webContents.on("did-finish-load", () => {
    log("Frontend loaded successfully");
  });

  mainWindow.on("close", (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

// ── System Tray ────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, "build", "icon.png");
  let trayIcon;
  if (fs.existsSync(iconPath)) {
    trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } else {
    // Create a simple 16x16 icon
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);

  const contextMenu = Menu.buildFromTemplate([
    { label: `ScoutFootball v${APP_VERSION}`, enabled: false },
    { type: "separator" },
    {
      label: "Show Window",
      click: () => { if (mainWindow) mainWindow.show(); },
    },
    {
      label: "Check for Updates...",
      click: () => autoUpdater.checkForUpdates(),
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => { isQuitting = true; app.quit(); },
    },
  ]);

  tray.setToolTip(`ScoutFootball v${APP_VERSION}`);
  tray.setContextMenu(contextMenu);
  tray.on("click", () => { if (mainWindow) mainWindow.show(); });
}

// ── Auto Updater ───────────────────────────────────────────────
autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = true;

autoUpdater.on("checking-for-update", () => log("Checking for updates..."));

autoUpdater.on("update-available", async (info) => {
  log(`Update available: ${info.version}`);
  const result = await dialog.showMessageBox(mainWindow, {
    type: "info",
    buttons: ["Download", "Later"],
    title: "Update Available",
    message: `ScoutFootball v${info.version} is available.`,
    detail: `You are running v${APP_VERSION}.\n\nWould you like to download the update?`,
  });
  if (result.response === 0) autoUpdater.downloadUpdate();
});

autoUpdater.on("update-not-available", () => log("No update available"));

autoUpdater.on("download-progress", (progress) => {
  log(`Download progress: ${Math.round(progress.percent)}%`);
  if (mainWindow) mainWindow.setProgressBar(progress.percent / 100);
});

autoUpdater.on("update-downloaded", async () => {
  log("Update downloaded");
  if (mainWindow) mainWindow.setProgressBar(-1);
  const result = await dialog.showMessageBox(mainWindow, {
    type: "info",
    buttons: ["Restart Now", "Later"],
    title: "Update Ready",
    message: "Update has been downloaded.",
    detail: "ScoutFootball will restart to apply the update.",
  });
  if (result.response === 0) {
    isQuitting = true;
    autoUpdater.quitAndInstall();
  }
});

autoUpdater.on("error", (err) => log(`Auto-updater error: ${err.message}`));

// ── App Lifecycle ──────────────────────────────────────────────
app.on("ready", async () => {
  log(`ScoutFootball v${APP_VERSION} starting...`);
  log(`Platform: ${process.platform} ${process.arch}`);
  log(`App packaged: ${app.isPackaged}`);
  log(`__dirname: ${__dirname}`);
  log(`resourcesPath: ${process.resourcesPath}`);

  // Start backend (non-blocking: window opens immediately, backend readiness checked in background)
  const backendStarted = startBackend();
  if (backendStarted) {
    log("Waiting for backend to be ready...");
    waitForBackend().then((ready) => {
      if (ready) {
        log("Backend is ready - frontend will detect API online on next health check");
      } else {
        log("Backend did not become ready - frontend will use static fallback");
      }
    });
  }

  // Start frontend server
  const frontendStarted = startFrontendServer();
  if (!frontendStarted) {
    log("WARNING: Frontend server failed to start!");
  }

  // Create window and tray
  createWindow();
  createTray();

  // Check for updates after window is shown.
  // Skip in packaged builds without a publish server (local-only distribution);
  // autoUpdater reads app-update.yml which doesn't exist without a publish config.
  if (app.isPackaged) {
    log("Skipping auto-updater: local-only distribution (no publish server)");
  } else {
    setTimeout(() => {
      autoUpdater.checkForUpdates().catch(() => {});
    }, 5000);
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    isQuitting = true;
    app.quit();
  }
});

app.on("activate", () => {
    if (mainWindow) {
        mainWindow.show();
    } else {
        createWindow();
    }
});

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
  stopFrontendServer();
});

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
    }
  });
}
