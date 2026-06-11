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

// ── Backend Management ─────────────────────────────────────────
function getBackendPath() {
  // In production, the backend executable is in the resources folder
  const isDev = !app.isPackaged;
  if (isDev) {
    // Development: use the Python script directly
    return {
      command: "python3",
      args: ["-m", "scoutfootball", "serve"],
      cwd: path.join(__dirname, ".."),
      env: { ...process.env, PYTHONPATH: path.join(__dirname, "..", "src") },
    };
  }

  // Production: use the bundled executable
  const platform = process.platform;
  const ext = platform === "win32" ? ".exe" : "";
  const backendExe = path.join(process.resourcesPath, "backend", `scoutfootball-server${ext}`);

  if (!fs.existsSync(backendExe)) {
    log(`Backend executable not found: ${backendExe}`);
    return null;
  }

  return {
    command: backendExe,
    args: [],
    cwd: path.join(process.resourcesPath),
    env: {
      ...process.env,
      SCOUTFOOTBALL_DATA_ROOT: path.join(process.resourcesPath, "data"),
    },
  };
}

function startBackend() {
  const config = getBackendPath();
  if (!config) {
    log("Cannot start backend: no executable found");
    return false;
  }

  log(`Starting backend: ${config.command} ${config.args.join(" ")}`);

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
    // Force kill after 5 seconds
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

async function waitForBackend(maxWaitMs = 15000) {
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
  const frontendDir = app.isPackaged
    ? path.join(process.resourcesPath, "frontend")
    : path.join(__dirname, "frontend");

  if (!fs.existsSync(frontendDir)) {
    log(`Frontend directory not found: ${frontendDir}`);
    return false;
  }

  const handler = (req, res) => {
    let filePath = path.join(frontendDir, req.url === "/" ? "index.html" : req.url);
    // Remove query strings
    filePath = filePath.split("?")[0];

    const ext = path.extname(filePath);
    const mimeTypes = {
      ".html": "text/html",
      ".js": "application/javascript",
      ".css": "text/css",
      ".json": "application/json",
      ".png": "image/png",
      ".svg": "image/svg+xml",
      ".ico": "image/x-icon",
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
    icon: path.join(__dirname, "build", "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    backgroundColor: "#0a0a0f",
    show: false, // Show after ready
  });

  // Load the frontend
  mainWindow.loadURL(`http://127.0.0.1:${FRONTEND_PORT}`);

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
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

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

// ── System Tray ────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, "build", "icon.png");
  if (fs.existsSync(iconPath)) {
    tray = new Tray(nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 }));
  } else {
    tray = new Tray(nativeImage.createEmpty());
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: `ScoutFootball v${APP_VERSION}`,
      enabled: false,
    },
    { type: "separator" },
    {
      label: "Show Window",
      click: () => {
        if (mainWindow) mainWindow.show();
      },
    },
    {
      label: "Check for Updates...",
      click: () => autoUpdater.checkForUpdates(),
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setToolTip(`ScoutFootball v${APP_VERSION}`);
  tray.setContextMenu(contextMenu);
  tray.on("click", () => {
    if (mainWindow) mainWindow.show();
  });
}

// ── Auto Updater ───────────────────────────────────────────────
autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = true;

autoUpdater.on("checking-for-update", () => {
  log("Checking for updates...");
});

autoUpdater.on("update-available", async (info) => {
  log(`Update available: ${info.version}`);
  const result = await dialog.showMessageBox(mainWindow, {
    type: "info",
    buttons: ["Download", "Later"],
    title: "Update Available",
    message: `ScoutFootball v${info.version} is available.`,
    detail: `You are running v${APP_VERSION}.\n\nWould you like to download the update?`,
  });
  if (result.response === 0) {
    autoUpdater.downloadUpdate();
  }
});

autoUpdater.on("update-not-available", () => {
  log("No update available");
});

autoUpdater.on("download-progress", (progress) => {
  log(`Download progress: ${Math.round(progress.percent)}%`);
  if (mainWindow) {
    mainWindow.setProgressBar(progress.percent / 100);
  }
});

autoUpdater.on("update-downloaded", async () => {
  log("Update downloaded");
  if (mainWindow) {
    mainWindow.setProgressBar(-1); // Remove progress bar
  }
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

autoUpdater.on("error", (err) => {
  log(`Auto-updater error: ${err.message}`);
});

// ── App Lifecycle ──────────────────────────────────────────────
app.on("ready", async () => {
  log(`ScoutFootball v${APP_VERSION} starting...`);
  log(`Platform: ${process.platform} ${process.arch}`);
  log(`App packaged: ${app.isPackaged}`);

  // Start backend
  const backendStarted = startBackend();
  if (backendStarted) {
    log("Waiting for backend to be ready...");
    await waitForBackend();
  }

  // Start frontend server
  startFrontendServer();

  // Create window and tray
  createWindow();
  createTray();

  // Check for updates after window is shown
  setTimeout(() => {
    autoUpdater.checkForUpdates();
  }, 3000);
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
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
  stopFrontendServer();
});

// Prevent multiple instances
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
