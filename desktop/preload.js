/* ScoutFootball Desktop — Preload Script */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("scoutDesktop", {
  version: process.env.npm_package_version || "1.0.0",
  platform: process.platform,
  isDesktop: true,

  // App info
  getAppVersion: () => ipcRenderer.invoke("get-app-version"),
  getPlatform: () => process.platform,

  // Update controls
  checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
  installUpdate: () => ipcRenderer.invoke("install-update"),

  // Window controls
  minimize: () => ipcRenderer.invoke("minimize-window"),
  maximize: () => ipcRenderer.invoke("maximize-window"),
  close: () => ipcRenderer.invoke("close-window"),

  // Logging
  log: (msg) => ipcRenderer.send("log", msg),
});
