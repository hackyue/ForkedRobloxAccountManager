import './style.css';
import { apiService, Account, Game, SavedUser, Settings, RobloxVersion, InstallerVersionEntry, WeaoExploitItem, BrowserExtension, UpdateCheckResult, UpdateDownloadStatus, ChromiumStatus } from './api';
import { invoke } from '@tauri-apps/api/tauri';
import { appWindow } from '@tauri-apps/api/window';
import { open as openDialog, save as saveDialog } from '@tauri-apps/api/dialog';
import { writeTextFile, writeBinaryFile } from '@tauri-apps/api/fs';
import { open as openExternal } from '@tauri-apps/api/shell';
import { THEMES, Theme, applyTheme, getTheme, getAllThemes, initThemeFromStorage, getCurrentThemeId, getCurrentTheme, saveCustomTheme, deleteCustomTheme, importThemeJson, getCustomThemes, getBackgroundSettings, saveBackgroundSettings, applyBackground, BACKGROUND_PRESETS, CustomBackgroundSettings } from './themes';
import { updateAppThemeIcons, getThemeIconUrl } from './colorWashIcon';

async function pickNativeFolder(title?: string): Promise<string | null> {
  try {
    const selected = await openDialog({
      directory: true,
      multiple: false,
      title: title || 'Select Folder'
    });
    if (typeof selected === 'string' && selected) return selected;
  } catch (_) { }
  return null;
}

async function pickNativeFile(title?: string, filters?: Array<{ name: string; extensions: string[] }>): Promise<string | null> {
  try {
    const selected = await openDialog({
      directory: false,
      multiple: false,
      title: title || 'Select File',
      filters: filters || [{ name: 'Extension Packages', extensions: ['crx', 'xpi'] }, { name: 'All Files', extensions: ['*'] }]
    });
    if (typeof selected === 'string' && selected) return selected;
  } catch (_) { }
  return null;
}

async function saveTextFileNative(options: {
  title: string;
  defaultPath: string;
  filters: Array<{ name: string; extensions: string[] }>;
  content: string;
  successMessage?: string;
}): Promise<boolean> {
  try {
    const filePath = await saveDialog({
      title: options.title,
      defaultPath: options.defaultPath,
      filters: options.filters
    });
    if (!filePath) return false;
    await writeTextFile(filePath, options.content);
    if (options.successMessage) {
      toast(options.successMessage, 'success');
    }
    return true;
  } catch (err) {
    console.error('Failed to save file:', err);
    toast('Failed to save file', 'error');
    return false;
  }
}

// Global window drag handler for frameless window titlebars (including setup wizard)
document.addEventListener('mousedown', (e) => {
  if (e.button !== 0) return;
  const target = e.target as HTMLElement | null;
  if (!target) return;
  if (target.closest('.titlebar-btn') || target.closest('button') || target.closest('input') || target.closest('select') || target.closest('a')) {
    return;
  }
  if (target.hasAttribute('data-tauri-drag-region') || target.closest('[data-tauri-drag-region]') || target.closest('.titlebar-drag') || target.closest('.titlebar')) {
    appWindow.startDragging().catch(() => { });
  }
});

// Suppress default Microsoft Edge / WebView2 browser context menu across the entire app
window.addEventListener('contextmenu', (e) => {
  e.preventDefault();
});

// Suppress WebView2 / Microsoft Edge browser default shortcuts and dialogs
window.addEventListener('keydown', (e) => {
  const key = e.key ? e.key.toLowerCase() : '';
  if (
    (e.ctrlKey && !e.altKey && (key === 'j' || key === 'p' || key === 'u' || key === 'f')) ||
    e.key === 'F7' ||
    e.key === 'F3' ||
    (e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight'))
  ) {
    e.preventDefault();
  }
});

// Intercept any web link clicks to open in user's default browser instead of WebView2 window
document.addEventListener('click', (e) => {
  const anchor = (e.target as HTMLElement)?.closest('a');
  if (anchor && anchor.href && (anchor.href.startsWith('http://') || anchor.href.startsWith('https://'))) {
    e.preventDefault();
    openExternal(anchor.href).catch(() => { });
  }
});

window.addEventListener('dragover', (e) => {
  e.preventDefault();
});

window.addEventListener('drop', (e) => {
  e.preventDefault();
});

// Initialize theme from storage right away
initThemeFromStorage();

// Setup screen state
let showSetup = false;
let setupStep = 0;
let isSetupRerun = false;
let setupData: any = {
  importMode: 'fresh',
  importPath: '',
  importPassword: '',
  importPreview: null,
  importStatus: '',
  importedSummary: null,
  encryptionEnabled: true,
  encryptionMethod: 'password',
  encryptionPassword: '',
  confirmPassword: '',
  preferredBrowser: 'auto',
  credentialImportInstances: 1,
  multiInstance: false,
  multiLaunchDelay: 1000,
  autoKillRobloxOnExit: false,
  autoMemoryTrimEnabled: false,
  autoCloseCrashHandlers: false,
  headlessMode: false,
  autoValidateOnLaunch: true,
  selectedTheme: 'default-dark',
  accentColor: '',
  autoArrangeScope: 'both',
  autoArrangeDimensionMode: 'auto',
  autoArrangeTargetWidth: 800,
  autoArrangeTargetHeight: 600,
  keepClientsArranged: false
};

// Types
interface State {
  accounts: Account[];
  games: Game[];
  robloxVersions: RobloxVersion[];
  selectedVersion: string;
  selectedId: number | null;
  selectedIds: Set<number>;
  editingId: number | null;
  revealed: Record<number, { password?: boolean; cookie?: boolean }>;
  search: string;
  groupFilter: string;
  statusFilter: 'all' | 'valid' | 'expired' | 'banned';
  activeGame: string | null;
  activeSavedUser: string | null;
  savedUsers: SavedUser[];
  placeMode: 'place' | 'user';
  serverMode: 'vip' | 'jobid' | 'subplace';
  targetGameName?: string;
  targetGameIcon?: string;
  targetGameLoading?: boolean;
  targetUserJoinable?: boolean;
  targetUserPresence?: number;
  targetUserLocation?: string;
  previousView?: string;
  view: 'accounts' | 'settings' | 'instances' | 'vip' | 'console' | 'webhooks' | 'extensions' | 'bloxgen' | 'fastflags' | 'clientsettings' | 'about';
  settingsTab: 'general' | 'roblox' | 'launching' | 'automation' | 'appearance' | 'notifications' | 'privacy' | 'security' | 'data' | 'keybinds' | 'custom-theme';
  settingsSearch: string;
  isLocked: boolean;
  settings: Settings;
}

interface StatusMeta {
  label: string;
  dot: string;
  bucket: 'valid' | 'expired' | 'banned';
}

const state: State = {
  accounts: [],
  games: [],
  robloxVersions: [],
  selectedVersion: 'auto',
  selectedId: null,
  selectedIds: new Set<number>(),
  editingId: null,
  revealed: {},
  search: "",
  groupFilter: "All Groups",
  statusFilter: "all",
  activeGame: null,
  activeSavedUser: null,
  savedUsers: [],
  placeMode: "place",
  serverMode: "vip",
  view: "accounts",
  settingsTab: "general",
  settingsSearch: "",
  isLocked: false,
  settings: {
    firstLaunch: true,
    multiSelect: true,
    activeIndicator: true,
    disableSuccessPopups: false,
    confirmBeforeLaunch: true,
    compactRows: false,
    showTableAvatars: true,
    showSavedGamesBar: true,
    autoSaveLaunchDetails: true,
    showDetailPanel: true,
    layoutPreset: 'standard',
    toastPosition: 'bottom-right',
    toastDuration: 3500,
    enableSoundEffects: false,
    showLaunchNotifications: true,
    showErrorNotifications: true,
    accentIndex: 0,
    selectedTheme: 'default-dark',
    accentColor: '',
    robloxPath: "",
    launchClient: "standard",
    autoUpdateCheck: true,
    autoCheckRobloxUpdates: true,
    encryptionEnabled: false,
    encryptionMethod: "none",
    preferredBrowser: "auto" as const,
    multiInstance: false,
    autoValidateOnLaunch: true,
    autoSortAccounts: 'none',
    multiLaunchDelay: 1000,
    confirmBulkDelete: true,
    autoKillRobloxOnExit: false,
    autoCloseCrashHandlers: false,
    minimizeToTray: false,
    startAtStartup: false,
    streamerMode: false,
    streamerHideUsernames: true,
    streamerHideAvatars: true,
    streamerHideSensitiveInfo: true,
    streamerHideGroupsAndNotes: false,
    streamerBlurLevel: 'medium',
    streamerRevealOnHover: false,
    autoArrangeScope: 'both',
    autoArrangeDimensionMode: 'auto',
    autoArrangeTargetWidth: 800,
    autoArrangeTargetHeight: 600,
    keepClientsArranged: false,
    preferredRegion: '',
    serverPerAccount: false,
    enableTopmost: false,
    autoRelaunchEnabled: false,
    autoRelaunchIntervalMinutes: 60,
    autoRelaunchGroup: '',
    swapPreserveSettings: true,
    swapPreserveFastflags: false,
    swapPreserveAppSettings: true,
    swapDeleteStudio: false,
    swapPurgeAuth: true,
    swapCreateRestorePoint: false,
    swapSpoofMac: true,
    swapSpoofHwid: true,
    swapSpoofVolume: false,
    swapOuiMirror: true,
    swapDhcpRefresh: true,
    swapCleanBeforeRun: false,
    swapAutoReinstallRoblox: false
  }
};

function showAppLoader(): void {
  let loader = document.getElementById('app-loader');
  if (!loader) {
    loader = document.createElement('div');
    loader.id = 'app-loader';
    loader.innerHTML = `
      <div class="loader-content">
        <div class="loader-logo-wrap">
          <div class="loader-glow-ring"></div>
          <img src="${getThemeIconUrl(getCurrentThemeId() || 'default-dark')}" alt="Forked Roblox Manager Logo" class="loader-app-logo" />
        </div>
        <div class="loader-progress-box">
          <div id="loader-error-container" style="display: none;"></div>
          <div class="loader-progress-track">
            <div class="loader-progress-bar" id="loader-bar"></div>
          </div>
          <div class="loader-status-text" id="loader-status">Initializing engine...</div>
        </div>
      </div>
      <div class="loader-footer">Roblox Account Manager</div>
    `;
    document.body.appendChild(loader);
    updateAppLoaderProgress(15, 'Initializing application engine...');
    const currentTheme = getCurrentTheme();
    updateAppThemeIcons(currentTheme.id, currentTheme.colors.primary).catch(() => { });
  }
}

let globalChromiumStatus: ChromiumStatus | null = null;

function updateAppLoaderProgress(percent: number, statusMsg?: string): void {
  const bar = document.getElementById('loader-bar');
  const status = document.getElementById('loader-status');
  if (bar) {
    bar.classList.remove('error');
    bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
  }
  if (status && statusMsg) {
    status.classList.remove('error');
    status.textContent = statusMsg;
  }
}

function showTracebackModal(errorData?: {
  title?: string;
  exception_name?: string;
  exception_message?: string;
  traceback?: string;
  github_issue_url?: string;
}): void {
  const existing = document.getElementById('traceback-modal-overlay');
  if (existing && existing.parentNode) {
    existing.parentNode.removeChild(existing);
  }

  const overlay = el('div', { id: 'traceback-modal-overlay', class: 'modal-overlay traceback-modal-overlay' }, []);
  const card = el('div', { class: 'modal-card traceback-modal-card' }, []);

  const closeModal = () => {
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
  };

  const closeBtnHeader = el('button', { class: 'modal-close-btn', type: 'button' }, [document.createTextNode('×')]);
  closeBtnHeader.addEventListener('click', closeModal);

  const header = el('div', { class: 'modal-header' }, [
    el('h3', { class: 'modal-title' }, [document.createTextNode(errorData?.title || 'Bug / Traceback Detector')]),
    closeBtnHeader
  ]);

  const body = el('div', { class: 'modal-body traceback-modal-body' }, []);

  const badge = el('div', { class: 'traceback-badge' }, [
    document.createTextNode(errorData?.exception_name || 'Unhandled Exception')
  ]);

  const msgBox = el('div', { class: 'traceback-message' }, [
    document.createTextNode(errorData?.exception_message || 'An error occurred during application execution.')
  ]);

  const tbCode = el('pre', { class: 'traceback-code-block' }, [
    document.createTextNode((errorData?.traceback || 'No traceback detail available.').trim())
  ]);

  body.appendChild(badge);
  body.appendChild(msgBox);
  body.appendChild(tbCode);

  const issueUrl = errorData?.github_issue_url || 'https://github.com/hackyue/ForkedRobloxAccountManager/issues/new';

  const issueBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [document.createTextNode('Create GitHub Issue')]);
  issueBtn.addEventListener('click', () => {
    openExternal(issueUrl).catch(() => { });
  });

  const copyBtn = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Copy Traceback')]);
  copyBtn.addEventListener('click', () => {
    const textToCopy = `${errorData?.exception_name || 'Exception'}: ${errorData?.exception_message || ''}\n\n${errorData?.traceback || ''}`;
    navigator.clipboard.writeText(textToCopy).then(() => {
      toast('Traceback copied to clipboard', 'success');
    }).catch(() => {
      toast('Failed to copy traceback', 'error');
    });
  });

  const closeBtnFooter = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Close')]);
  closeBtnFooter.addEventListener('click', closeModal);

  const footer = el('div', { class: 'modal-footer traceback-modal-footer' }, [
    issueBtn,
    copyBtn,
    closeBtnFooter
  ]);

  overlay.addEventListener('click', (evt) => {
    if (evt.target === overlay) {
      closeModal();
    }
  });

  card.appendChild(header);
  card.appendChild(body);
  card.appendChild(footer);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
}

function showLoaderError(reason: string): void {
  const bar = document.getElementById('loader-bar');
  const status = document.getElementById('loader-status');
  const errorContainer = document.getElementById('loader-error-container');

  if (bar) {
    bar.style.width = '100%';
    bar.classList.add('error');
  }
  if (status) {
    status.classList.remove('error');
    status.textContent = '';
  }
  if (errorContainer) {
    errorContainer.style.display = 'flex';
    errorContainer.className = 'loader-error-box';
    errorContainer.innerHTML = `
      <div class="loader-error-text">Failed to Launch: ${escapeHtml(reason)}</div>
      <div class="loader-actions">
        <button id="loader-retry-btn" class="loader-btn loader-btn-primary">Retry Connection</button>
        <button id="loader-traceback-btn" class="loader-btn loader-btn-secondary">View Full Error</button>
        <button id="loader-continue-btn" class="loader-btn loader-btn-secondary">Continue Anyway</button>
      </div>
    `;
    const retryBtn = document.getElementById('loader-retry-btn');
    const tracebackBtn = document.getElementById('loader-traceback-btn');
    const continueBtn = document.getElementById('loader-continue-btn');

    if (retryBtn) {
      retryBtn.onclick = async () => {
        if (bar) {
          bar.classList.remove('error');
        }
        if (status) {
          status.classList.remove('error');
        }
        errorContainer.style.display = 'none';
        updateAppLoaderProgress(15, 'Relaunching backend...');
        addLog('Attempting to relaunch backend process...', 'info');
        try {
          const relaunchRes = await apiService.relaunchBackend();
          if (relaunchRes && !relaunchRes.started) {
            addLog('Failed to relaunch backend: ' + relaunchRes.reason, 'error');
            showLoaderError(relaunchRes.reason);
            return;
          }
        } catch (e: any) {
          addLog('Backend relaunch error: ' + (e?.message || String(e)), 'warning');
        }
        loadFromBackend(5, 600);
      };
    }
    if (tracebackBtn) {
      tracebackBtn.onclick = async () => {
        try {
          const lastErr = await apiService.getLastError();
          if (lastErr && lastErr.has_error) {
            showTracebackModal({
              title: lastErr.title || 'Backend Error Traceback',
              exception_name: lastErr.exception_name || 'Exception',
              exception_message: lastErr.exception_message || reason,
              traceback: lastErr.traceback || reason,
              github_issue_url: lastErr.github_issue_url
            });
            return;
          }
        } catch (_) { }
        showTracebackModal({
          title: 'Error Traceback',
          exception_name: 'Launch Error',
          exception_message: reason,
          traceback: `Error: ${reason}`
        });
      };
    }
    if (continueBtn) {
      continueBtn.onclick = async () => {
        renderAll();
        await hideAppLoader();
      };
    }
  }
}

async function hideAppLoader(): Promise<void> {
  const loader = document.getElementById('app-loader');
  if (loader) {
    updateAppLoaderProgress(100, 'Ready!');
    await new Promise(r => setTimeout(r, 200));

    loader.classList.add('fade-out');
    setTimeout(() => {
      if (loader.parentNode) {
        loader.parentNode.removeChild(loader);
      }
    }, 400);
  }
}

async function loadFromBackend(retries = 5, delay = 600): Promise<void> {
  showAppLoader();
  updateAppLoaderProgress(20, 'Connecting to Python backend...');

  try {
    const backendStatus = await invoke<any>('get_backend_status');
    if (backendStatus && !backendStatus.started) {
      addLog('Backend failed to start: ' + backendStatus.reason, 'error');
      showLoaderError(backendStatus.reason);
      return;
    }
  } catch (_) { }

  let lastErrorMsg = '';

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      addLog(`Connecting to backend server (attempt ${attempt}/${retries})...`, 'info');

      const authStatus = await apiService.getAuthStatus();
      if (authStatus && authStatus.locked) {
        state.isLocked = true;
        await hideAppLoader();
        renderUnlockScreen();
        return;
      }
      state.isLocked = false;
      removeUnlockScreen();

      updateAppLoaderProgress(50, 'Loading accounts & saved games...');

      const [accounts, games, settings, versionsRes, savedUsers, chromiumRes] = await Promise.all([
        apiService.getAccounts(),
        apiService.getGames(),
        apiService.getSettings(),
        apiService.getRobloxVersions().catch(() => ({ success: false, versions: [] })),
        apiService.getSavedUsers().catch(() => []),
        apiService.getChromiumStatus().catch(() => null)
      ]);

      if (chromiumRes && chromiumRes.success && chromiumRes.status) {
        globalChromiumStatus = chromiumRes.status;
      }

      state.accounts = Array.isArray(accounts) ? accounts : [];
      state.games = Array.isArray(games) ? games : [];
      state.savedUsers = Array.isArray(savedUsers) ? savedUsers : [];
      if (settings) {
        state.settings = { ...state.settings, ...settings };
        if (settings.lastPlaceMode && (settings.lastPlaceMode === 'place' || settings.lastPlaceMode === 'user')) {
          state.placeMode = settings.lastPlaceMode;
        } else {
          state.placeMode = 'place';
        }
        if (settings.lastServerMode) {
          state.serverMode = settings.lastServerMode;
        }
      }
      if (versionsRes && versionsRes.success && Array.isArray(versionsRes.versions)) {
        state.robloxVersions = versionsRes.versions;
      }

      updateAppLoaderProgress(80, 'Applying theme & workspace settings...');

      if (state.settings.selectedTheme) {
        applyTheme(state.settings.selectedTheme, state.settings.accentColor);
      }

      if (!state.settings.preferredBrowser) {
        state.settings.preferredBrowser = 'auto';
      }
      if (state.settings.enableTopmost) {
        appWindow.setAlwaysOnTop(true).catch(() => { });
      }

      state.view = state.settings.defaultStartupView || 'accounts';

      if (state.settings.firstLaunch === true) {
        await hideAppLoader();
        isSetupRerun = false;
        showSetup = true;
        renderSetup();
        return;
      }

      if (state.accounts.length > 0 && (!state.selectedId || !getAccount(state.selectedId))) {
        state.selectedId = state.accounts[0].id;
        state.selectedIds = new Set([state.selectedId]);
      }

      renderAll();

      const placeInputEl = document.getElementById('place-input') as HTMLInputElement | null;
      const serverInputEl = document.getElementById('server-input') as HTMLInputElement | null;
      if (placeInputEl) {
        const initialVal = state.placeMode === 'user' ? (state.settings.lastUserId || '') : (state.settings.lastPlaceId || '');
        if (initialVal) {
          placeInputEl.value = initialVal;
          updateTargetGameFromPlaceInput(initialVal);
        }
      }
      if (serverInputEl) {
        if (!state.settings.lastServerMode && state.settings.lastServerId) {
          state.serverMode = detectServerMode(state.settings.lastServerId);
        }
        const initialServerVal = state.serverMode === 'jobid'
          ? (state.settings.lastJobId || '')
          : state.serverMode === 'subplace'
            ? (state.settings.lastSubplaceId || '')
            : (state.settings.lastVipServerId || state.settings.lastServerId || '');
        if (initialServerVal) {
          serverInputEl.value = initialServerVal;
        }
      }
      renderLaunchBar();

      await hideAppLoader();

      if (state.settings.autoUpdateCheck !== false) {
        setTimeout(() => {
          checkAppUpdateOnStartup();
        }, 2000);
      }

      if (state.settings.autoValidateOnLaunch !== false && state.accounts.length > 0) {
        try {
          const authStatus = await apiService.getAuthStatus();
          if (authStatus && !authStatus.locked) {
            handleValidateSelectedAccountsSilently();
          }
        } catch (_e) {
        }
      }
      return;
    } catch (error: any) {
      lastErrorMsg = error?.message || String(error) || 'Failed to connect to backend server at http://127.0.0.1:5050';
      const isDecryptionError = lastErrorMsg.toLowerCase().includes('decrypt');
      if (attempt < retries && !isDecryptionError) {
        updateAppLoaderProgress(20, `Connecting to Python backend (attempt ${attempt}/${retries})...`);
        await new Promise(r => setTimeout(r, delay));
      } else {
        addLog('Failed to load data from backend: ' + lastErrorMsg, 'error');
        showLoaderError(lastErrorMsg);
        return;
      }
    }
  }
}

// Utility functions
function statusMeta(s: string): StatusMeta {
  const norm = String(s || '').toLowerCase();
  switch (norm) {
    case "valid":
    case "online":
    case "ingame":
    case "offline":
    case "active":
    case "ok":
      return { label: "Valid", dot: "valid", bucket: "valid" };
    case "expired":
    case "invalid":
    case "error":
      return { label: "Expired", dot: "expired", bucket: "expired" };
    case "banned":
      return { label: "Banned", dot: "banned", bucket: "banned" };
    default:
      return { label: "Expired", dot: "expired", bucket: "expired" };
  }
}

function getAccount(id: number): Account | null {
  for (const account of state.accounts) {
    if (account.id === id) return account;
  }
  return null;
}

function detectServerMode(serverId: string, fallbackMode: 'vip' | 'jobid' | 'subplace' = 'vip'): 'vip' | 'jobid' | 'subplace' {
  const trimmed = (serverId || '').trim();
  if (!trimmed) return fallbackMode;
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(trimmed)) {
    return 'jobid';
  }
  return fallbackMode;
}

function extractPrivateServerCode(input: string): { code: string; placeId?: string; isUrl: boolean } {
  const trimmed = (input || '').trim();
  if (!trimmed) return { code: '', isUrl: false };

  let extractedPlaceId: string | undefined = undefined;
  const placeMatch = trimmed.match(/(?:games|placeId=|\/)(\d{4,15})/i);
  if (placeMatch) {
    extractedPlaceId = placeMatch[1];
  }

  const vipMatch = trimmed.match(/(?:privateServerLinkCode|linkCode|privateServerId|vipServerId)=([a-zA-Z0-9_-]+)/i);
  if (vipMatch) {
    return { code: vipMatch[1], placeId: extractedPlaceId, isUrl: true };
  }

  const isFullUrl = trimmed.includes('://') || trimmed.toLowerCase().includes('roblox.com');
  return { code: trimmed, placeId: extractedPlaceId, isUrl: isFullUrl };
}

async function resolveAndNormalizePrivateServer(
  input: string,
  cookie?: string
): Promise<{ code: string; placeId?: string; original: string; changed: boolean }> {
  const trimmed = (input || '').trim();
  if (!trimmed) return { code: '', original: '', changed: false };

  const extracted = extractPrivateServerCode(trimmed);
  if (extracted.code && extracted.code !== trimmed) {
    return {
      code: extracted.code,
      placeId: extracted.placeId,
      original: trimmed,
      changed: true
    };
  }

  const isShareLink = /roblox\.com\/(?:share|share-links)|roblox:\/\/navigation\/share_links|share\?code=/i.test(trimmed);
  if (isShareLink) {
    try {
      if (!cookie && state.accounts.length > 0) {
        const acc = (state.selectedId ? getAccount(state.selectedId) : null) || state.accounts.find(a => a.cookie);
        if (acc) cookie = acc.cookie;
      }
      const res = await apiService.resolvePrivateServer(trimmed, cookie);
      if (res && !res.error) {
        const resolvedCode = (res.link_code || res.resolved || res.access_code || '').trim();
        if (resolvedCode && resolvedCode !== trimmed) {
          return {
            code: resolvedCode,
            placeId: res.place_id || extracted.placeId,
            original: trimmed,
            changed: true
          };
        }
      }
    } catch (_) { }
  }

  return {
    code: extracted.code,
    placeId: extracted.placeId,
    original: trimmed,
    changed: extracted.code !== trimmed
  };
}

async function refreshAccountList(selectAccountId?: number): Promise<void> {
  try {
    const freshAccounts = await apiService.getAccounts();
    state.accounts = Array.isArray(freshAccounts) ? freshAccounts : [];
    if (selectAccountId && getAccount(selectAccountId)) {
      state.selectedId = selectAccountId;
      state.selectedIds = new Set([selectAccountId]);
    } else if (state.selectedId && !getAccount(state.selectedId)) {
      state.selectedId = state.accounts.length ? state.accounts[0].id : null;
      state.selectedIds = state.selectedId ? new Set([state.selectedId]) : new Set();
    } else if (!state.selectedId && state.accounts.length > 0) {
      state.selectedId = state.accounts[0].id;
      state.selectedIds = new Set([state.accounts[0].id]);
    }
    renderAll();
  } catch (err) {
    console.error('Failed to refresh accounts list:', err);
  }
}

let importBannerHideTimeoutId: number | null = null;

function showImportBanner(message: string = 'Importing accounts...'): void {
  if (importBannerHideTimeoutId !== null) {
    clearTimeout(importBannerHideTimeoutId);
    importBannerHideTimeoutId = null;
  }

  const pos = state.settings.toastPosition || 'bottom-right';
  const toastWrap = document.getElementById('toast-wrap');
  if (toastWrap) {
    toastWrap.className = `pos-${pos}`;
  }

  let banner = document.getElementById('import-progress-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'import-progress-banner';
    banner.className = `import-progress-banner pos-${pos}`;
    banner.innerHTML = `
      <div class="import-spinner"></div>
      <div class="import-text" id="import-progress-text">${message}</div>
    `;
    if (toastWrap) {
      toastWrap.appendChild(banner);
    } else {
      document.body.appendChild(banner);
    }
    void banner.offsetWidth;
  } else {
    banner.className = `import-progress-banner pos-${pos}`;
    const textEl = document.getElementById('import-progress-text');
    if (textEl) textEl.textContent = message;
    if (toastWrap && banner.parentElement !== toastWrap) {
      toastWrap.appendChild(banner);
    }
  }

  banner.classList.add('show');
}

function hideImportBanner(): void {
  if (importBannerHideTimeoutId !== null) {
    clearTimeout(importBannerHideTimeoutId);
    importBannerHideTimeoutId = null;
  }

  const banner = document.getElementById('import-progress-banner');
  if (banner) {
    banner.classList.remove('show');
    importBannerHideTimeoutId = window.setTimeout(() => {
      const elToHide = document.getElementById('import-progress-banner');
      if (elToHide && !elToHide.classList.contains('show')) {
        elToHide.remove();
      }
      importBannerHideTimeoutId = null;
    }, 300);
  }
}

let _sharedAudioCtx: AudioContext | null = null;

function playNotificationChime(type: 'success' | 'error' | 'info' = 'success'): void {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) return;
    if (!_sharedAudioCtx || _sharedAudioCtx.state === 'closed') {
      _sharedAudioCtx = new AudioCtx();
    }
    const ctx = _sharedAudioCtx;
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => { });
    }
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    if (type === 'success') {
      osc.frequency.setValueAtTime(587.33, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12);
    } else if (type === 'error') {
      osc.frequency.setValueAtTime(349.23, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.15);
    } else {
      osc.frequency.setValueAtTime(523.25, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.1);
    }
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.22);
    osc.onended = () => {
      osc.disconnect();
      gain.disconnect();
    };
  } catch (e) { }
}

function toast(msg: string, type: 'success' | 'error' | 'info' = 'success', forceShow: boolean = false): void {
  if (!forceShow) {
    if (type === 'success' && state.settings.disableSuccessPopups) return;
    if (type === 'error' && state.settings.showErrorNotifications === false) return;
    if (type === 'info' && state.settings.showLaunchNotifications === false) return;
  }

  const wrap = document.getElementById('toast-wrap');
  if (!wrap) return;

  const pos = state.settings.toastPosition || 'bottom-right';
  wrap.className = `pos-${pos}`;

  const el = document.createElement('div');
  el.className = 'toast' + (type === 'error' ? ' toast-error' : type === 'info' ? ' toast-info' : '');
  el.textContent = msg;
  wrap.appendChild(el);

  if (state.settings.enableSoundEffects) {
    playNotificationChime(type);
  }

  const duration = state.settings.toastDuration || 3500;

  setTimeout(() => {
    el.style.transition = 'opacity .25s, transform .25s';
    el.style.opacity = '0';
    el.style.transform = 'translateY(-6px)';
    setTimeout(() => el.remove(), 250);
  }, duration);

  addLog(msg, type === 'error' ? 'error' : type === 'info' ? 'info' : 'success');
}

function el(tag: string, attrs: Record<string, any> | null, children: (HTMLElement | SVGElement | Text)[]): HTMLElement {
  const svgTags = ['svg', 'path', 'polyline', 'polygon', 'rect', 'circle', 'line', 'g', 'use', 'defs', 'clippath'];
  const e = svgTags.includes(tag.toLowerCase())
    ? (document.createElementNS('http://www.w3.org/2000/svg', tag) as unknown as HTMLElement)
    : document.createElement(tag);
  if (attrs) {
    for (const k in attrs) {
      if (k === 'class') e.className = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else if (k.startsWith('on') && typeof attrs[k] === 'function') {
        e.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      }
      else if (typeof attrs[k] === 'function') {
        (e as any)[k] = attrs[k];
      }
      else if (k === 'selected' || k === 'checked' || k === 'disabled' || k === 'readonly') {
        (e as any)[k] = Boolean(attrs[k]);
      }
      else e.setAttribute(k, attrs[k]);
    }
  }
  (children || []).forEach(c => { if (c) e.appendChild(c); });
  return e;
}

function initials(name: string): string {
  if (!name) return "?";
  return name.slice(0, 2).toUpperCase();
}

function copyToClipboard(text: string): void {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch(() => { });
  }
}

function filteredAccounts(): Account[] {
  const list = (state.accounts || []).filter(a => {
    if (!a) return false;
    const q = (state.search || '').toLowerCase();
    const matchesSearch = !q ||
      (a.username || '').toLowerCase().includes(q) ||
      (a.display_name || '').toLowerCase().includes(q) ||
      (a.group || '').toLowerCase().includes(q) ||
      (a.note || '').toLowerCase().includes(q);

    const matchesGroup = !state.groupFilter || state.groupFilter === "All Groups" || (a.group || '') === state.groupFilter;

    let matchesStatus = true;
    if (state.statusFilter && state.statusFilter !== 'all') {
      const bucket = statusMeta(a.status).bucket;
      matchesStatus = bucket === state.statusFilter;
    }

    return matchesSearch && matchesGroup && matchesStatus;
  });

  const sortMode = state.settings.autoSortAccounts || 'none';
  if (sortMode === 'status') {
    const order: Record<string, number> = { valid: 1, expired: 2, error: 2, invalid: 2, banned: 3 };
    list.sort((a, b) => (order[statusMeta(a.status).bucket] || 2) - (order[statusMeta(b.status).bucket] || 2));
  } else if (sortMode === 'username') {
    list.sort((a, b) => (a.username || '').localeCompare(b.username || ''));
  }

  return list;
}

function getSelectedAccounts(): Account[] {
  if (state.selectedIds.size > 0) {
    const list: Account[] = [];
    state.selectedIds.forEach(id => {
      const a = getAccount(id);
      if (a) list.push(a);
    });
    if (list.length > 0) return list;
  }
  if (state.selectedId != null) {
    const a = getAccount(state.selectedId);
    if (a) return [a];
  }
  return [];
}

function showConfirmModal(
  title: string,
  message: string,
  confirmBtnText: string = 'Confirm Launch',
  isDanger: boolean = false
): Promise<boolean> {
  return new Promise((resolve) => {
    let overlay = document.getElementById('confirm-modal-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'confirm-modal-overlay';
      overlay.className = 'overlay';
      overlay.innerHTML = `
        <div class="modal" style="max-width: 380px;">
          <h3 id="confirm-modal-title">Confirm Action</h3>
          <p class="hint" id="confirm-modal-msg" style="margin: 14px 0 20px; font-size: 13px; color: var(--fg); line-height: 1.5;"></p>
          <div class="modal-actions" style="display:flex; gap:10px; justify-content:flex-end;">
            <button class="btn btn-secondary" id="confirm-modal-cancel">Cancel</button>
            <button class="btn btn-primary" id="confirm-modal-ok">Confirm</button>
          </div>
        </div>
      `;
      document.body.appendChild(overlay);
    }

    const titleEl = document.getElementById('confirm-modal-title');
    const msgEl = document.getElementById('confirm-modal-msg');
    const okBtn = document.getElementById('confirm-modal-ok') as HTMLButtonElement | null;
    const cancelBtn = document.getElementById('confirm-modal-cancel') as HTMLButtonElement | null;

    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = message;
    if (okBtn) {
      okBtn.textContent = confirmBtnText;
      okBtn.className = isDanger ? 'btn btn-danger' : 'btn btn-primary';
    }

    const cleanup = (result: boolean) => {
      if (overlay) overlay.classList.remove('show');
      if (okBtn) okBtn.onclick = null;
      if (cancelBtn) cancelBtn.onclick = null;
      resolve(result);
    };

    if (okBtn) okBtn.onclick = () => cleanup(true);
    if (cancelBtn) cancelBtn.onclick = () => cleanup(false);

    overlay.classList.add('show');
  });
}

async function handleLaunchAccount(id: number): Promise<void> {
  state.selectedId = id;
  state.selectedIds = new Set([id]);
  renderAll();
  await handleLaunchSelectedAccounts();
}

async function handleLaunchSelectedAccounts(): Promise<void> {
  const accountsToLaunch = getSelectedAccounts();
  if (!accountsToLaunch.length) {
    toast('Please select an account first', 'error');
    return;
  }

  const placeInput = document.getElementById('place-input') as HTMLInputElement | null;
  const serverInput = document.getElementById('server-input') as HTMLInputElement | null;
  const place = placeInput?.value.trim() || '';
  const server = serverInput?.value.trim() || '';

  if (state.settings.confirmBeforeLaunch) {
    const target = place ? `place "${place}"` : 'Roblox Client';
    const msg = accountsToLaunch.length === 1
      ? `Are you sure you want to launch ${target} as @${accountsToLaunch[0].username}?`
      : `Are you sure you want to launch ${target} on ${accountsToLaunch.length} selected accounts simultaneously?`;
    const confirmed = await showConfirmModal('Confirm Roblox Launch', msg, 'Launch Roblox');
    if (!confirmed) return;
  }

  if (accountsToLaunch.length > 1 && !state.settings.multiInstance) {
    addLog('Enabling multi-instance mode for simultaneous launch...', 'info');
    await updateSetting('multiInstance', true);
  }

  const btnLaunch = document.getElementById('btn-launch') as HTMLButtonElement | null;
  if (btnLaunch) btnLaunch.disabled = true;

  let successCount = 0;
  let lastError = '';
  for (let i = 0; i < accountsToLaunch.length; i++) {
    const a = accountsToLaunch[i];
    const prefix = accountsToLaunch.length > 1 ? `[${i + 1}/${accountsToLaunch.length}] ` : '';
    addLog(`${prefix}Launching Roblox for @${a.username}...`, 'info');
    toast(`${prefix}Launching Roblox for @${a.username}...`, 'info');

    try {
      const placeIdToLaunch = (state.serverMode === 'subplace' && server.trim()) ? server.trim() : place;
      const serverIdToLaunch = (state.placeMode === 'user' || state.serverMode === 'subplace') ? '' : server;
      const res = await apiService.launchAccount({
        username: a.username,
        placeId: placeIdToLaunch,
        serverId: serverIdToLaunch,
        serverMode: state.serverMode,
        version: state.selectedVersion === 'auto' ? undefined : state.selectedVersion,
        launchMode: state.placeMode === 'user' ? 'join_user' : 'place'
      });

      if (res.success) {
        successCount++;
        addLog(`${prefix}Roblox launched for @${a.username}`, 'success');

        if (successCount === 1 && state.settings.autoSaveLaunchDetails !== false && place) {
          if (state.placeMode === 'user') {
            const rawUser = place.replace(/^@/, '').trim();
            const exists = (state.savedUsers || []).some(u => u.username.toLowerCase() === rawUser.toLowerCase() || u.user_id === rawUser);
            if (!exists) {
              const displayName = state.targetGameName ? state.targetGameName.replace(/^Join @/, '').replace(/^Join User:\s*/, '') : rawUser;
              apiService.createSavedUser({
                username: rawUser,
                display_name: displayName || rawUser,
                icon_url: state.targetGameIcon
              }).then(saved => {
                state.savedUsers.push(saved);
                renderGames();
              }).catch(() => { });
            }
          } else {
            const placeIdMatch = place.match(/(?:games|placeId=|\/)?(\d{4,15})/);
            const resolvedPlaceId = placeIdMatch ? placeIdMatch[1] : (place.match(/^\d+$/) ? place : '');
            if (resolvedPlaceId) {
              const exists = (state.games || []).some(g => g.placeId === resolvedPlaceId);
              if (!exists) {
                const gameName = state.targetGameName || `Game ${resolvedPlaceId}`;
                apiService.createGame({
                  name: gameName,
                  placeId: resolvedPlaceId,
                  serverId: server || undefined,
                  serverMode: server ? state.serverMode : undefined,
                  placeMode: state.placeMode,
                  icon_url: state.targetGameIcon
                }).then(savedGame => {
                  state.games.push(savedGame);
                  renderGames();
                }).catch(() => { });
              }
            }
          }
        }
      } else {
        const err = res.error || "Roblox isn't installed";
        lastError = err;
        addLog(`${prefix}Failed to launch @${a.username}: ${err}`, 'error');
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      lastError = errMsg;
      addLog(`${prefix}Launch error for @${a.username}: ${errMsg}`, 'error');
    }

    if (i < accountsToLaunch.length - 1) {
      await new Promise(r => setTimeout(r, state.settings.multiLaunchDelay || 1000));
    }
  }

  if (btnLaunch) btnLaunch.disabled = false;

  if (successCount === accountsToLaunch.length) {
    toast(`Successfully launched ${successCount} account${successCount > 1 ? 's' : ''}!`, 'success');
  } else if (successCount > 0) {
    toast(`Launched ${successCount}/${accountsToLaunch.length} accounts (${lastError || 'some failed'})`, 'info');
  } else {
    if (accountsToLaunch.length === 1) {
      toast(`Failed to launch @${accountsToLaunch[0].username}: ${lastError || "Roblox isn't installed"}`, 'error');
    } else {
      toast(`Failed to launch accounts: ${lastError || "Roblox isn't installed"}`, 'error');
    }
  }
}

async function handleLaunchBrowser(id: number): Promise<void> {
  state.selectedId = id;
  state.selectedIds = new Set([id]);
  renderAll();
  await handleLaunchSelectedBrowsers();
}

async function handleLaunchSelectedBrowsers(): Promise<void> {
  const accountsToLaunch = getSelectedAccounts();
  if (!accountsToLaunch.length) {
    toast('Please select an account first', 'error');
    return;
  }

  const browser = state.settings.preferredBrowser || 'auto';

  if (state.settings.confirmBeforeLaunch && accountsToLaunch.length > 1) {
    const confirmed = await showConfirmModal('Confirm Browser Launch', `Open browser for ${accountsToLaunch.length} selected accounts?`, 'Open Browser');
    if (!confirmed) return;
  }

  const btnLaunchBrowser = document.getElementById('btn-launch-browser') as HTMLButtonElement | null;
  if (btnLaunchBrowser) btnLaunchBrowser.disabled = true;

  let successCount = 0;
  let lastError = '';
  for (let i = 0; i < accountsToLaunch.length; i++) {
    const a = accountsToLaunch[i];
    const prefix = accountsToLaunch.length > 1 ? `[${i + 1}/${accountsToLaunch.length}] ` : '';
    addLog(`${prefix}Opening browser for @${a.username} (${browser})...`, 'info');

    try {
      const res = await apiService.launchHome({
        username: a.username,
        preferredBrowser: browser
      });

      if (res.success) {
        successCount++;
        addLog(`${prefix}Browser opened for @${a.username}`, 'success');
      } else {
        const err = res.error || 'Failed to open browser';
        lastError = err;
        addLog(`${prefix}Failed to open browser for @${a.username}: ${err}`, 'error');
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      lastError = errMsg;
      addLog(`${prefix}Browser launch error for @${a.username}: ${errMsg}`, 'error');
    }

    if (i < accountsToLaunch.length - 1) {
      await new Promise(r => setTimeout(r, state.settings.multiLaunchDelay || 1000));
    }
  }

  if (btnLaunchBrowser) btnLaunchBrowser.disabled = false;

  if (successCount === accountsToLaunch.length) {
    toast(`Opened browser for ${successCount} account${successCount > 1 ? 's' : ''}!`, 'success');
  } else if (successCount > 0) {
    toast(`Opened browser for ${successCount}/${accountsToLaunch.length} accounts (${lastError || 'some failed'})`, 'info');
  } else {
    toast(lastError ? `Failed to open browser: ${lastError}` : 'Failed to open browser', 'error');
  }
}

async function saveEdit(id: number): Promise<void> {
  const a = getAccount(id);
  if (!a) return;

  const nameEl = document.getElementById('edit-username') as HTMLInputElement | null;
  const statusEl = document.getElementById('edit-status') as HTMLSelectElement | null;
  const groupEl = document.getElementById('edit-group') as HTMLInputElement | null;
  const noteEl = document.getElementById('edit-note') as HTMLTextAreaElement | null;

  const updateData: Partial<Account> = {};
  if (nameEl) updateData.username = nameEl.value.trim() || a.username;
  if (statusEl) updateData.status = statusEl.value as Account['status'];
  if (groupEl) updateData.group = groupEl.value.trim();
  if (noteEl) updateData.note = noteEl.value;

  try {
    await apiService.updateAccount(id, updateData);
    Object.assign(a, updateData);
    state.editingId = null;
    toast('Account updated');
    renderAll();
  } catch (error) {
    addLog('Failed to update account: ' + error, 'error');
    toast('Failed to update account', 'error');
  }
}

async function deleteAccount(id: number): Promise<void> {
  const a = getAccount(id);
  if (!a) return;
  const confirmed = await showConfirmModal('Confirm Remove Account', `Remove "${a.username}" from the account list?`, 'Delete Account', true);
  if (!confirmed) return;

  try {
    await apiService.deleteAccount(id);

    state.accounts = state.accounts.filter(x => x.id !== id);
    state.selectedIds.delete(id);
    if (state.selectedId === id) {
      state.selectedId = state.accounts.length ? state.accounts[0].id : null;
    }
    if (state.selectedId != null) {
      state.selectedIds = new Set([state.selectedId]);
    }
    toast('Account removed');
    renderAll();
  } catch (error) {
    addLog('Failed to delete account: ' + error, 'error');
    toast('Failed to delete account', 'error');
  }
}

async function bulkDeleteSelected(): Promise<void> {
  const ids = Array.from(state.selectedIds);
  const count = ids.length;
  if (!count) return;
  if (state.settings.confirmBulkDelete !== false) {
    const confirmed = await showConfirmModal('Confirm Bulk Delete', `Remove ${count} selected accounts from the list?`, `Delete ${count} Accounts`, true);
    if (!confirmed) return;
  }

  try {
    await apiService.bulkDeleteAccounts(ids);

    state.accounts = state.accounts.filter(x => !ids.includes(x.id));
    state.selectedIds = new Set();
    state.selectedId = state.accounts.length ? state.accounts[0].id : null;
    if (state.selectedId != null) {
      state.selectedIds = new Set([state.selectedId]);
    }
    toast(`${count} accounts removed`);
    renderAll();
  } catch (error) {
    addLog('Failed to delete accounts: ' + error, 'error');
    toast('Failed to delete accounts', 'error');
  }
}

async function exportAccounts(): Promise<void> {
  try {
    let filePath: string | null = null;
    try {
      filePath = await saveDialog({
        title: 'Save Accounts Backup',
        defaultPath: 'accounts.json',
        filters: [{ name: 'JSON Files', extensions: ['json'] }]
      });
    } catch (dialogErr) {
      console.warn('Native save dialog error:', dialogErr);
    }

    if (!filePath) {
      return;
    }

    const data = await apiService.exportData(true);
    let written = false;

    try {
      await writeTextFile(filePath, JSON.stringify(data, null, 2));
      written = true;
    } catch (fsErr) {
      console.warn('writeTextFile failed, falling back to backend export:', fsErr);
      try {
        const res = await apiService.exportData(true, filePath);
        if (res && (res.success || res.path)) {
          written = true;
        }
      } catch (beErr) {
        console.error('Backend export save failed:', beErr);
      }
    }

    if (written) {
      toast('Accounts exported successfully', 'success');
    } else {
      toast('Failed to write backup file to selected path', 'error');
    }
  } catch (error) {
    addLog('Failed to export accounts: ' + error, 'error');
    toast('Failed to export accounts', 'error');
  }
}

async function importAccounts(file: File): Promise<void> {
  if (!file) return;
  showImportBanner(`Importing accounts from ${file.name}...`);
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const parsed = JSON.parse(reader.result as string) as any;
      let payload: any = {};
      if (Array.isArray(parsed)) {
        payload = { accounts: parsed };
      } else if (parsed && typeof parsed === 'object') {
        payload = parsed;
      } else {
        throw new Error('invalid format');
      }

      try {
        const result = await apiService.importData(payload);
        hideImportBanner();
        toast(result.message || 'Accounts imported successfully', 'success');
        await refreshAccountList();
      } catch (error) {
        hideImportBanner();
        addLog('Failed to import accounts: ' + error, 'error');
        toast('Import failed: backend error', 'error');
      }
    } catch (err) {
      hideImportBanner();
      toast('Import failed: invalid JSON file', 'error');
    }
  };
  reader.readAsText(file);
}

function showSetGroupModal(accounts: Account[]): void {
  if (!accounts || accounts.length === 0) return;
  const app = document.getElementById('app') || document.body;

  const existingGroups: string[] = [];
  state.accounts.forEach(acc => {
    const g = (acc.group || '').trim();
    if (g && g !== 'All Groups' && !existingGroups.includes(g)) {
      existingGroups.push(g);
    }
  });
  existingGroups.sort((a, b) => a.localeCompare(b));

  const isMulti = accounts.length > 1;
  const initialGroup = isMulti
    ? (accounts.every(a => (a.group || '') === (accounts[0].group || '')) ? (accounts[0].group || '') : '')
    : (accounts[0].group || '');

  const title = isMulti
    ? `Set Group (${accounts.length} Accounts)`
    : `Set Group (@${accounts[0].username})`;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'set-group-modal-overlay';

  const chipsHtml = existingGroups.length > 0
    ? `<div style="display: flex; flex-direction: column; gap: 6px; padding-top: 10px; border-top: 1px solid var(--border-soft);">
        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted);">Existing Groups (click to apply)</div>
        <div style="display: flex; flex-wrap: wrap; gap: 6px; max-height: 90px; overflow-y: auto;" id="set-group-chips">
          ${existingGroups.map(g => `<button type="button" class="set-group-chip" data-group="${escapeHtml(g)}" style="border-radius: 14px; font-size: 11px; font-weight: 500; padding: 3px 10px; background: rgba(255,255,255,0.06); border: 1px solid var(--border); color: var(--fg); cursor: pointer; transition: all 0.15s ease;">${escapeHtml(g)}</button>`).join('')}
        </div>
      </div>`
    : '';

  overlay.innerHTML = `
    <div class="modal" style="max-width: 440px; width: calc(100% - 32px); animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);">
      <div class="modal-header" style="padding: 14px 18px; display: flex; align-items: center; justify-content: space-between;">
        <h3 style="margin: 0; font-size: 13.5px; font-weight: 600; display: flex; align-items: center; gap: 8px; color: var(--fg);">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16" style="color: var(--primary);"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          <span>${title}</span>
        </h3>
        <button class="modal-close" id="set-group-modal-close" style="width: 26px; height: 26px; font-size: 14px; border: none; background: transparent; cursor: pointer; color: var(--muted); border-radius: 4px; display: flex; align-items: center; justify-content: center;">✕</button>
      </div>
      <div class="modal-body" style="padding: 18px; display: flex; flex-direction: column; gap: 14px;">
        <div class="field" style="display: flex; flex-direction: column; gap: 6px;">
          <label for="set-group-input" style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted);">Group Name</label>
          <input type="text" id="set-group-input" class="input" style="width: 100%; box-sizing: border-box; padding: 9px 12px; border-radius: 6px; border: 1px solid var(--border); background: rgba(255,255,255,0.04); color: var(--fg); font-size: 13px; outline: none;" placeholder="e.g. Main Accounts, Trading Alts..." value="${escapeHtml(initialGroup)}" autocomplete="off" />
          <span style="font-size: 11px; color: var(--muted); line-height: 1.4; margin-top: 2px;">Leave blank or click Clear to remove accounts from any group.</span>
        </div>
        ${chipsHtml}
      </div>
      <div class="modal-footer" style="display: flex; justify-content: space-between; align-items: center; padding: 12px 18px; border-top: 1px solid var(--border-soft); background: rgba(0, 0, 0, 0.2);">
        <button class="btn btn-secondary" id="set-group-clear-btn" type="button" style="white-space: nowrap; font-size: 12px; padding: 6px 14px; color: var(--red); border-color: rgba(239, 68, 68, 0.25);">Clear Group</button>
        <div style="display: flex; gap: 8px; align-items: center;">
          <button class="btn btn-secondary" id="set-group-cancel-btn" type="button" style="white-space: nowrap; font-size: 12px; padding: 6px 14px;">Cancel</button>
          <button class="btn btn-primary" id="set-group-save-btn" type="button" style="white-space: nowrap; font-size: 12px; padding: 6px 14px;">Save Group</button>
        </div>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  const input = overlay.querySelector('#set-group-input') as HTMLInputElement | null;
  const closeBtn = overlay.querySelector('#set-group-modal-close');
  const cancelBtn = overlay.querySelector('#set-group-cancel-btn');
  const clearBtn = overlay.querySelector('#set-group-clear-btn');
  const saveBtn = overlay.querySelector('#set-group-save-btn') as HTMLButtonElement | null;

  if (input) {
    input.focus();
    input.select();
  }

  const closeModal = () => {
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  overlay.querySelectorAll('.set-group-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const g = chip.getAttribute('data-group');
      if (input && g) {
        input.value = g;
        input.focus();
      }
    });
  });

  const applyGroup = async (groupValue: string) => {
    const trimmed = groupValue.trim();
    if (saveBtn) saveBtn.disabled = true;

    try {
      for (const a of accounts) {
        a.group = trimmed;
        await apiService.updateAccount(a.id, { group: trimmed }).catch(err => {
          addLog(`Failed to update group for @${a.username}: ${err}`, 'error');
        });
      }

      if (trimmed) {
        toast(`Group set to "${trimmed}" for ${accounts.length} account${accounts.length > 1 ? 's' : ''}`, 'success');
      } else {
        toast(`Group cleared for ${accounts.length} account${accounts.length > 1 ? 's' : ''}`, 'info');
      }

      renderAll();
      closeModal();
    } catch (err) {
      toast('Failed to update group', 'error');
      if (saveBtn) saveBtn.disabled = false;
    }
  };

  saveBtn?.addEventListener('click', () => {
    applyGroup(input ? input.value : '');
  });

  clearBtn?.addEventListener('click', () => {
    applyGroup('');
  });

  input?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      applyGroup(input.value);
    } else if (e.key === 'Escape') {
      closeModal();
    }
  });
}

async function clearAllAccounts(): Promise<void> {
  showClearAccountsModal();
}

function showClearAccountsModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3>Clear All Accounts</h3>
        <button class="modal-close" id="modal-close">×</button>
      </div>
      <div class="modal-body">
        <p>Are you sure you want to remove all accounts from the list? This action cannot be undone.</p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
        <button class="btn btn-danger" id="modal-confirm">Clear All</button>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  const closeBtn = overlay.querySelector('.modal-close');
  const cancelBtn = overlay.querySelector('#modal-cancel');
  const confirmBtn = overlay.querySelector('#modal-confirm') as HTMLButtonElement | null;

  const closeModal = () => {
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  confirmBtn?.addEventListener('click', async () => {
    try {
      await apiService.clearAccounts();
      state.accounts = [];
      state.selectedIds = new Set();
      state.selectedId = null;
      toast('All accounts cleared');
      renderAll();
      closeModal();
    } catch (error) {
      addLog('Failed to clear accounts: ' + error, 'error');
      toast('Failed to clear accounts', 'error');
    }
  });
}

async function deleteAllData(): Promise<void> {
  showDeleteConfirmModal();
}

function showDeleteConfirmModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  // Create modal overlay
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal delete-confirm-modal">
      <div class="modal-header">
        <h3>Delete All Data</h3>
        <button class="modal-close" id="modal-close">×</button>
      </div>
      <div class="modal-body">
        <p class="warning-text">This will permanently delete ALL your data including:</p>
        <ul class="data-list">
          <li>All accounts</li>
          <li>All saved games</li>
          <li>All settings and preferences</li>
          <li>Encryption configuration</li>
        </ul>
        <p class="warning-text">This action cannot be undone!</p>
        
        <div class="confirmation-step" id="step-1">
          <label>Type "DELETE" to confirm:</label>
          <input type="text" id="delete-confirmation" placeholder="DELETE" autocomplete="off">
        </div>
        
        <div class="confirmation-step" id="step-2" style="display: none;">
          <p class="final-warning">Are you absolutely sure you want to proceed?</p>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
        <button class="btn btn-danger" id="modal-confirm" disabled="true">Confirm</button>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  // Event listeners
  const closeBtn = overlay.querySelector('.modal-close');
  const cancelBtn = overlay.querySelector('#modal-cancel');
  const confirmBtn = overlay.querySelector('#modal-confirm') as HTMLButtonElement | null;
  const confirmationInput = overlay.querySelector('#delete-confirmation') as HTMLInputElement | null;

  const closeModal = () => {
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  confirmationInput?.addEventListener('input', (e) => {
    const value = (e.target as HTMLInputElement).value;
    if (confirmBtn) {
      (confirmBtn as HTMLButtonElement).disabled = value !== 'DELETE';
    }
  });

  confirmBtn?.addEventListener('click', () => {
    const step1 = overlay.querySelector('#step-1') as HTMLElement | null;
    const step2 = overlay.querySelector('#step-2') as HTMLElement | null;

    if (step1 && step1.style.display !== 'none') {
      // Move to step 2
      step1.style.display = 'none';
      step2!.style.display = 'block';
      if (confirmBtn) {
        (confirmBtn as HTMLButtonElement).textContent = 'Delete All Data';
        (confirmBtn as HTMLButtonElement).disabled = false;
      }
    } else {
      // Execute deletion
      executeDeleteAllData();
      closeModal();
    }
  });

  // Focus on input
  setTimeout(() => confirmationInput?.focus(), 100);
}

async function executeDeleteAllData(): Promise<void> {
  try {
    const response = await apiService.clearAllData();
    state.accounts = [];
    state.games = [];
    state.selectedIds = new Set();
    state.selectedId = null;

    // Update settings from backend response
    if (response && (response as any).settings) {
      state.settings = (response as any).settings;
    } else {
      state.settings = {
        firstLaunch: true,
        multiSelect: true,
        activeIndicator: true,
        disableSuccessPopups: false,
        confirmBeforeLaunch: true,
        compactRows: false,
        accentIndex: 0,
        robloxPath: "",
        launchClient: "standard",
        autoUpdateCheck: true,
        autoCheckRobloxUpdates: true,
        encryptionEnabled: false,
        encryptionMethod: "none",
        preferredBrowser: "auto",
        multiInstance: false
      };
    }

    toast('All data deleted. Setup will run on next launch.', 'success');

    // Reload to trigger setup
    setTimeout(() => {
      location.reload();
    }, 1500);
  } catch (error) {
    addLog('Failed to delete all data: ' + error, 'error');
    toast('Failed to delete all data', 'error');
  }
}

async function uninstallApplication(): Promise<void> {
  showUninstallConfirmModal();
}

function showUninstallConfirmModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal delete-confirm-modal">
      <div class="modal-header">
        <h3>Uninstall Application</h3>
        <button class="modal-close" id="modal-close">×</button>
      </div>
      <div class="modal-body">
        <p class="warning-text">This will completely uninstall Forked Account Manager from your system and remove all data.</p>
        <ul class="data-list">
          <li>Application installation and executables</li>
          <li>All account data, saved games, and settings</li>
          <li>AppData configuration & cache files</li>
        </ul>
        <p class="warning-text">The application will automatically exit while the uninstaller completes. This cannot be undone!</p>
        
        <div class="confirmation-step" id="step-1">
          <label>Type "UNINSTALL" to confirm:</label>
          <input type="text" id="uninstall-confirmation" placeholder="UNINSTALL" autocomplete="off">
        </div>
        
        <div class="confirmation-step" id="step-2" style="display: none;">
          <p class="final-warning">Are you absolutely sure you want to permanently delete everything and exit?</p>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
        <button class="btn btn-danger" id="modal-confirm" disabled="true">Confirm Uninstall</button>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  const closeBtn = document.getElementById('modal-close');
  const cancelBtn = document.getElementById('modal-cancel');
  const confirmBtn = document.getElementById('modal-confirm') as HTMLButtonElement;
  const confirmationInput = document.getElementById('uninstall-confirmation');

  const closeModal = () => {
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  confirmationInput?.addEventListener('input', (e) => {
    const value = (e.target as HTMLInputElement).value;
    if (confirmBtn) {
      confirmBtn.disabled = value !== 'UNINSTALL';
    }
  });

  confirmBtn?.addEventListener('click', async () => {
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');

    if (step1 && step1.style.display !== 'none') {
      step1.style.display = 'none';
      step2!.style.display = 'block';
      if (confirmBtn) {
        confirmBtn.textContent = 'Permanently Uninstall';
        confirmBtn.disabled = false;
      }
    } else {
      closeModal();
      await executeUninstall();
    }
  });

  setTimeout(() => confirmationInput?.focus(), 100);
}

async function executeUninstall(): Promise<void> {
  try {
    toast('Initiating application uninstallation...', 'info');
    await apiService.uninstall();
    toast('Uninstaller launched. Exiting FRAM...', 'success');
    setTimeout(async () => {
      try {
        await invoke('close_window');
      } catch (err) {
        window.close();
      }
    }, 500);
  } catch (error) {
    addLog('Uninstall failed: ' + error, 'error');
    toast('Uninstall failed', 'error');
  }
}

const SETTINGS_SUBSETTING_PARENT_KEYS: (keyof Settings)[] = [
  'headlessMode',
  'keepClientsArranged',
  'autoArrangeDimensionMode',
  'antiAfkEnabled',
  'autoRejoinEnabled',
  'autoRelaunchEnabled',
  'autoMemoryTrimEnabled',
  'streamerMode',
  'encryptionEnabled',
  'encryptionMethod',
  'multiSelect'
];

async function updateSetting<K extends keyof Settings>(key: K, value: Settings[K]): Promise<void> {
  state.settings[key] = value;
  addLog('Setting updated: ' + String(key) + ' = ' + String(value), 'info');

  applyAllSettingsLayout();

  try {
    if (key === 'multiInstance') {
      await apiService.toggleMultiInstance(Boolean(value)).catch(err => {
        addLog('Failed to toggle multi-instance state: ' + err, 'error');
      });
    }
    if (key === 'headlessMode') {
      await apiService.toggleHeadlessMode(Boolean(value)).catch(err => {
        addLog('Failed to toggle headless mode state: ' + err, 'error');
      });
    }
    if (key === 'keepClientsArranged') {
      await apiService.toggleAutoArrange(Boolean(value)).catch(err => {
        addLog('Failed to toggle auto-arrange state: ' + err, 'error');
      });
    }
    if (key === 'enableTopmost') {
      appWindow.setAlwaysOnTop(Boolean(value)).catch(() => { });
    }
    if (key === 'autoCloseCrashHandlers' && value) {
      apiService.killAllCrashHandlers().catch(() => { });
    }
    if (key === 'autoRelaunchEnabled' || key === 'autoRelaunchIntervalMinutes' || key === 'autoRelaunchGroup') {
      const payload: any = {};
      if (key === 'autoRelaunchEnabled') payload.autoRelaunchEnabled = Boolean(value);
      if (key === 'autoRelaunchIntervalMinutes') payload.autoRelaunchIntervalMinutes = Number(value);
      if (key === 'autoRelaunchGroup') payload.autoRelaunchGroup = String(value);
      apiService.updateAutoRelaunchSettings(payload).catch(() => { });
    }

    const updated = await apiService.updateSettings({ [key]: value });
    if (updated) {
      state.settings = { ...state.settings, ...updated };
      applyAllSettingsLayout();
    }

    addLog('Setting saved to backend: ' + String(key) + ' = ' + String(value), 'success');
  } catch (error) {
    addLog('Failed to update settings: ' + error, 'error');
    toast('Failed to save settings', 'error');
  }

  if (state.view !== 'settings') {
    renderAll();
  } else {
    const structuralKeys: (keyof Settings)[] = [
      'selectedTheme',
      'accentColor',
      'layoutPreset',
      'showDetailPanel',
      'showSavedGamesBar'
    ];
    if (structuralKeys.includes(key)) {
      renderAll();
    } else if (SETTINGS_SUBSETTING_PARENT_KEYS.includes(key)) {
      renderSettingsView();
    }
  }
}

// Rendering functions
function renderStats(): void {
  const total = state.accounts.length;
  let valid = 0, expired = 0, banned = 0;

  state.accounts.forEach(a => {
    const b = statusMeta(a.status).bucket;
    if (b === "valid") valid++;
    else if (b === "expired") expired++;
    else if (b === "banned") banned++;
  });

  const statTotal = document.getElementById('stat-total');
  const statValid = document.getElementById('stat-valid');
  const statExpired = document.getElementById('stat-expired');
  const statBanned = document.getElementById('stat-banned');

  if (statTotal) statTotal.textContent = total.toString();
  if (statValid) statValid.textContent = valid.toString();
  if (statExpired) statExpired.textContent = expired.toString();
  if (statBanned) statBanned.textContent = banned.toString();

  const pillAccounts = document.querySelector('.pill.accounts') as HTMLElement;
  const pillValid = document.querySelector('.pill.valid') as HTMLElement;
  const pillExpired = document.querySelector('.pill.expired') as HTMLElement;
  const pillBanned = document.querySelector('.pill.banned') as HTMLElement;

  if (pillAccounts) {
    pillAccounts.classList.toggle('active-filter', state.statusFilter === 'all');
    pillAccounts.onclick = () => { state.statusFilter = 'all'; renderAll(); };
  }
  if (pillValid) {
    pillValid.classList.toggle('active-filter', state.statusFilter === 'valid');
    pillValid.onclick = () => { state.statusFilter = state.statusFilter === 'valid' ? 'all' : 'valid'; renderAll(); };
  }
  if (pillExpired) {
    pillExpired.classList.toggle('active-filter', state.statusFilter === 'expired');
    pillExpired.onclick = () => { state.statusFilter = state.statusFilter === 'expired' ? 'all' : 'expired'; renderAll(); };
  }
  if (pillBanned) {
    pillBanned.classList.toggle('active-filter', state.statusFilter === 'banned');
    pillBanned.onclick = () => { state.statusFilter = state.statusFilter === 'banned' ? 'all' : 'banned'; renderAll(); };
  }
}

function renderGroupFilter(): void {
  const groups: string[] = ["All Groups"];
  state.accounts.forEach(a => {
    if (a.group && groups.indexOf(a.group) === -1) {
      groups.push(a.group);
    }
  });

  const sel = document.getElementById('group-filter') as HTMLSelectElement;
  if (!sel) return;

  sel.innerHTML = "";
  groups.forEach(g => {
    const o = el('option', { value: g }, []) as HTMLOptionElement;
    o.textContent = g;
    if (g === state.groupFilter) {
      o.selected = true;
    }
    sel.appendChild(o);
  });
}

let draggedAccountId: number | null = null;

async function reorderAccount(sourceId: number, targetId: number, isBefore: boolean): Promise<void> {
  const accounts = [...state.accounts];
  const sourceIndex = accounts.findIndex(x => x.id === sourceId);
  const targetIndex = accounts.findIndex(x => x.id === targetId);
  if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) return;

  const [moved] = accounts.splice(sourceIndex, 1);
  const newTargetIndex = accounts.findIndex(x => x.id === targetId);
  const insertIndex = isBefore ? newTargetIndex : newTargetIndex + 1;
  accounts.splice(insertIndex, 0, moved);

  state.accounts = accounts;
  state.selectedId = sourceId;
  state.selectedIds = new Set([sourceId]);

  if (state.settings.autoSortAccounts !== 'none') {
    state.settings.autoSortAccounts = 'none';
    updateSetting('autoSortAccounts', 'none').catch(() => { });
    toast('Account list sorting set to None for custom order', 'info');
  }

  renderAll();

  try {
    const ids = state.accounts.map(x => x.id);
    await apiService.reorderAccounts({ ids });
  } catch (err) {
    addLog('Failed to persist account order: ' + err, 'warning');
  }
}

async function moveAccountPosition(id: number, direction: 'up' | 'down'): Promise<void> {
  const visible = filteredAccounts();
  const visibleIdx = visible.findIndex(x => x.id === id);
  if (visibleIdx === -1) return;

  if (direction === 'up') {
    if (visibleIdx === 0) return;
    const target = visible[visibleIdx - 1];
    return reorderAccount(id, target.id, true);
  } else if (direction === 'down') {
    if (visibleIdx === visible.length - 1) return;
    const target = visible[visibleIdx + 1];
    return reorderAccount(id, target.id, false);
  }
}

function updateTableSelectionVisuals(): void {
  const tbody = document.getElementById('table-body');
  if (tbody) {
    const rows = tbody.querySelectorAll<HTMLTableRowElement>('tr[data-id]');
    rows.forEach(row => {
      const rawId = row.getAttribute('data-id');
      const id = rawId ? parseInt(rawId, 10) : null;
      if (id !== null && state.selectedIds.has(id)) {
        row.classList.add('selected');
      } else {
        row.classList.remove('selected');
      }
    });
  }
  renderDetail();
  renderLaunchBar();
  renderStats();
}

function renderTable(): void {
  const tbody = document.getElementById('table-body');
  if (!tbody) return;

  tbody.innerHTML = "";
  const list = filteredAccounts();

  const emptyState = document.getElementById('empty-state');
  const accountsTable = document.getElementById('accounts-table');

  if (emptyState) {
    if (list.length === 0) {
      emptyState.style.display = 'flex';
      if (accountsTable) accountsTable.style.display = 'none';
      emptyState.innerHTML = `
        <div class="empty-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="16" x2="22" y1="11" y2="11"/></svg>
        </div>
        <div class="empty-state-title">${state.accounts.length === 0 ? 'No Accounts Added' : 'No Matching Accounts'}</div>
        <div class="empty-state-desc">${state.accounts.length === 0 ? 'Add your Roblox accounts with Quick Sign-In or Browser Login.' : 'Try changing your search query or group filter.'}</div>
        ${state.accounts.length === 0 ? `<button class="btn btn-primary" id="empty-add-btn" style="margin-top:16px;padding:8px 18px;height:auto;font-size:12.5px;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="margin-right:6px;"><path d="M5 12h14"/><path d="M12 5v14"/></svg>Add Account</button>` : ''}
      `;
      const addBtn = document.getElementById('empty-add-btn');
      if (addBtn) {
        addBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          showAddAccountOptions(addBtn);
        });
      }
    } else {
      emptyState.style.display = 'none';
      if (accountsTable) accountsTable.style.display = '';
    }
  }

  if (accountsTable) {
    accountsTable.classList.toggle('compact', state.settings.compactRows);
  }

  list.forEach((a, idx) => {
    const meta = statusMeta(a.status);
    const tr = el('tr', {
      class: state.selectedIds.has(a.id) ? 'selected' : '',
      'data-id': a.id.toString(),
      draggable: 'true'
    }, []);

    tr.appendChild(el('td', { class: 'muted mono' }, [document.createTextNode((idx + 1).toString())]));

    const userTd = el('td', {}, []);
    const userWrap = el('div', { class: 'row-user-wrap' }, []);

    if (state.settings.showTableAvatars !== false) {
      if (state.settings.downloadAvatarIcons !== false && a.avatar_url) {
        const img = el('img', { class: 'row-avatar', src: a.avatar_url, alt: a.username }, []) as HTMLImageElement;
        img.onerror = () => {
          const fallback = el('div', { class: 'row-avatar-fallback' }, [document.createTextNode(initials(a.username))]);
          img.replaceWith(fallback);
        };
        userWrap.appendChild(img);
      } else {
        const fallback = el('div', { class: 'row-avatar-fallback' }, [document.createTextNode(initials(a.username))]);
        userWrap.appendChild(fallback);
      }
    }

    const namesWrap = el('div', { class: 'row-user-names' }, []);
    const nameRow = el('div', { style: 'display:flex; align-items:center; gap:6px;' }, []);
    const uSpan = el('span', { class: 'row-username' }, [document.createTextNode(a.username || '(unnamed)')]);
    nameRow.appendChild(uSpan);
    if (a.auto_rejoin_enabled) {
      const arBadge = el('span', {
        class: 'auto-rejoin-badge',
        title: `Auto-Rejoin enabled for @${a.username}`,
        style: 'font-size:9.5px; padding:1px 5px; border-radius:4px; background:rgba(16,185,129,0.08); color:var(--emerald); border:1px solid rgba(16,185,129,0.15); font-weight:600; box-shadow:none; text-shadow:none;'
      }, [document.createTextNode('Rejoin')]);
      nameRow.appendChild(arBadge);
    }
    if (a.anti_afk_enabled) {
      const afkBadge = el('span', {
        class: 'anti-afk-badge',
        title: `Anti-AFK enabled for @${a.username}`,
        style: 'font-size:9.5px; padding:1px 5px; border-radius:4px; background:rgba(99,102,241,0.08); color:var(--accent); border:1px solid rgba(99,102,241,0.15); font-weight:600; box-shadow:none; text-shadow:none;'
      }, [document.createTextNode('Anti-AFK')]);
      nameRow.appendChild(afkBadge);
    }
    namesWrap.appendChild(nameRow);
    if (a.display_name && a.display_name !== a.username) {
      const dSpan = el('span', { class: 'row-display-name' }, [document.createTextNode(a.display_name)]);
      namesWrap.appendChild(dSpan);
    }
    userWrap.appendChild(namesWrap);
    userTd.appendChild(userWrap);
    tr.appendChild(userTd);

    const statusTd = el('td', {}, []);
    const span = el('span', {}, []);
    if (state.settings.activeIndicator) {
      span.appendChild(el('span', { class: 'dot ' + meta.dot }, []));
    }
    const lbl = document.createElement('span');
    lbl.className = 'muted';
    lbl.textContent = meta.label;
    span.appendChild(lbl);
    statusTd.appendChild(span);
    tr.appendChild(statusTd);

    const groupTd = el('td', { class: 'muted' }, []);
    if (a.group) {
      const groupSpan = el('span', { class: 'row-group' }, [document.createTextNode(a.group)]);
      groupTd.appendChild(groupSpan);
    } else {
      groupTd.textContent = '—';
    }
    tr.appendChild(groupTd);

    const noteTd = el('td', { class: 'muted truncate row-note' }, []) as HTMLElement;
    noteTd.textContent = a.note || '';
    noteTd.title = a.note || '';
    tr.appendChild(noteTd);

    const menuTd = el('td', {}, []);
    const actionsWrap = el('div', { class: 'row-actions' }, []);

    const quickLaunchBtn = el('button', {
      class: 'row-quick-launch',
      title: `Launch as @${a.username}`,
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><polygon points="5 3 19 12 5 21 5 3"/></svg>'
    }, []);
    quickLaunchBtn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      handleLaunchAccount(a.id);
    });
    actionsWrap.appendChild(quickLaunchBtn);

    const menuBtn = el('button', {
      class: 'row-menu-btn',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>'
    }, []);
    menuBtn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      openRowMenu(a.id, menuBtn);
    });
    actionsWrap.appendChild(menuBtn);
    menuTd.appendChild(actionsWrap);
    tr.appendChild(menuTd);

    tr.addEventListener('contextmenu', (ev) => {
      ev.preventDefault();
      if (!state.selectedIds.has(a.id)) {
        if (state.selectedId !== a.id) {
          state.revealed = {};
        }
        state.selectedIds = new Set([a.id]);
        state.selectedId = a.id;
        updateTableSelectionVisuals();
      }
      openRowMenu(a.id, ev);
    });

    tr.addEventListener('click', (ev) => {
      if (state.selectedId !== a.id) {
        state.revealed = {};
      }
      if (state.settings.multiSelect && matchesMultiSelectClick(ev)) {
        if (state.selectedIds.has(a.id)) {
          state.selectedIds.delete(a.id);
        } else {
          state.selectedIds.add(a.id);
        }
        state.selectedId = state.selectedIds.size ? a.id : null;
      } else if (state.settings.multiSelect && ev.shiftKey && state.selectedId != null) {
        const lastIdx = list.findIndex(x => x.id === state.selectedId);
        const currentIdx = idx;
        if (lastIdx !== -1) {
          const start = Math.min(lastIdx, currentIdx);
          const end = Math.max(lastIdx, currentIdx);
          for (let i = start; i <= end; i++) {
            state.selectedIds.add(list[i].id);
          }
        } else {
          state.selectedIds.add(a.id);
        }
      } else {
        state.selectedIds = new Set([a.id]);
        state.selectedId = a.id;
      }
      state.editingId = null;
      updateTableSelectionVisuals();
    });

    tr.addEventListener('dblclick', () => {
      handleLaunchAccount(a.id);
    });

    tr.addEventListener('dragstart', (ev) => {
      const target = ev.target as HTMLElement;
      if (target.closest('button, input, select, a, .row-actions')) {
        ev.preventDefault();
        return;
      }
      draggedAccountId = a.id;
      if (ev.dataTransfer) {
        ev.dataTransfer.setData('text/plain', a.id.toString());
        ev.dataTransfer.effectAllowed = 'move';
      }
      tr.classList.add('row-dragging');
    });

    tr.addEventListener('dragend', () => {
      draggedAccountId = null;
      document.querySelectorAll('.row-dragging, .drop-target-before, .drop-target-after').forEach(el => {
        el.classList.remove('row-dragging', 'drop-target-before', 'drop-target-after');
      });
    });

    tbody.appendChild(tr);
  });

  if (accountsTable) {
    accountsTable.ondragover = (ev: DragEvent) => {
      ev.preventDefault();
      if (ev.dataTransfer) {
        ev.dataTransfer.dropEffect = 'move';
      }
    };
  }

  tbody.ondragover = (ev: DragEvent) => {
    ev.preventDefault();
    if (ev.dataTransfer) {
      ev.dataTransfer.dropEffect = 'move';
    }
    if (draggedAccountId == null) return;

    const targetTr = (ev.target as HTMLElement).closest('tr');
    tbody.querySelectorAll('tr').forEach(r => {
      if (r !== targetTr) {
        r.classList.remove('drop-target-before', 'drop-target-after');
      }
    });

    if (!targetTr) return;
    const targetId = Number(targetTr.getAttribute('data-id'));
    if (!targetId || targetId === draggedAccountId) return;

    const rect = targetTr.getBoundingClientRect();
    const mid = rect.top + rect.height / 2;
    if (ev.clientY < mid) {
      targetTr.classList.add('drop-target-before');
      targetTr.classList.remove('drop-target-after');
    } else {
      targetTr.classList.add('drop-target-after');
      targetTr.classList.remove('drop-target-before');
    }
  };

  tbody.ondragleave = (ev: DragEvent) => {
    if (ev.relatedTarget && tbody.contains(ev.relatedTarget as Node)) return;
    tbody.querySelectorAll('tr').forEach(r => {
      r.classList.remove('drop-target-before', 'drop-target-after');
    });
  };

  tbody.ondrop = (ev: DragEvent) => {
    ev.preventDefault();
    const targetTr = (ev.target as HTMLElement).closest('tr');
    tbody.querySelectorAll('tr').forEach(r => {
      r.classList.remove('drop-target-before', 'drop-target-after', 'row-dragging');
    });

    if (!targetTr || draggedAccountId == null) return;
    const targetId = Number(targetTr.getAttribute('data-id'));
    if (!targetId || targetId === draggedAccountId) return;

    const rect = targetTr.getBoundingClientRect();
    const isBefore = ev.clientY < (rect.top + rect.height / 2);
    const sourceId = draggedAccountId;
    draggedAccountId = null;
    reorderAccount(sourceId, targetId, isBefore);
  };
}

function renderDetail(): void {
  const panel = document.getElementById('detail-panel');
  if (!panel) return;

  if (state.settings.showDetailPanel === false) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = '';

  panel.innerHTML = "";

  if (state.selectedIds.size > 1) {
    const selectedAccounts = getSelectedAccounts();
    const count = selectedAccounts.length;

    const wrap = el('div', {
      style: 'padding:14px;display:flex;flex-direction:column;gap:12px;overflow-y:auto;height:100%;box-sizing:border-box;'
    }, []);

    const header = el('div', {
      style: 'display:flex;align-items:center;justify-content:space-between;padding-bottom:8px;border-bottom:1px solid var(--border-soft);'
    }, [
      el('div', { style: 'font-size:13px;font-weight:700;color:var(--fg);' }, [document.createTextNode(`${count} Accounts Selected`)]),
      el('span', { style: 'font-size:10px;padding:2px 6px;border-radius:4px;background:var(--primary-dim);color:var(--primary);font-weight:600;' }, [document.createTextNode('Multi-Select')])
    ]);
    wrap.appendChild(header);

    const launchRow = el('div', { style: 'display:flex;gap:6px;' }, []);
    const multiLaunchBtn = el('button', {
      class: 'btn btn-primary',
      style: 'flex:1;',
      html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="5 3 19 12 5 21 5 3"/></svg> Launch (${count})`
    }, []);
    multiLaunchBtn.addEventListener('click', handleLaunchSelectedAccounts);

    const multiBrowserBtn = el('button', {
      class: 'btn btn-secondary',
      title: `Open ${count} accounts in browser`,
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
    }, []);
    multiBrowserBtn.addEventListener('click', handleLaunchSelectedBrowsers);

    launchRow.appendChild(multiLaunchBtn);
    launchRow.appendChild(multiBrowserBtn);
    wrap.appendChild(launchRow);

    const multiGroupBtn = el('button', {
      class: 'btn btn-secondary',
      style: 'width:100%;justify-content:flex-start;gap:8px;',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> Set Group'
    }, []);
    multiGroupBtn.addEventListener('click', () => {
      showSetGroupModal(selectedAccounts);
    });
    wrap.appendChild(multiGroupBtn);

    const copySection = el('div', { style: 'display:flex;flex-direction:column;gap:6px;' }, []);
    copySection.appendChild(el('div', { class: 'field-label' }, [document.createTextNode('Batch Copy Options')]));

    const copyUsernamesBtn = el('button', {
      class: 'btn btn-secondary',
      style: 'justify-content:flex-start;',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg> Copy Usernames'
    }, []);
    copyUsernamesBtn.addEventListener('click', () => {
      const text = selectedAccounts.map(acc => acc.username || '').join('\n');
      copyToClipboard(text);
      toast(`Copied ${count} usernames to clipboard`, 'success');
    });

    const copyPasswordsBtn = el('button', {
      class: 'btn btn-secondary',
      style: 'justify-content:flex-start;',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Copy Passwords'
    }, []);
    copyPasswordsBtn.addEventListener('click', () => {
      const text = selectedAccounts.map(acc => acc.password || '').join('\n');
      copyToClipboard(text);
      toast(`Copied ${count} passwords to clipboard`, 'success');
    });

    const copyCookiesBtn = el('button', {
      class: 'btn btn-secondary',
      style: 'justify-content:flex-start;',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0-2 19.8"/></svg> Copy Cookies (.ROBLOSECURITY)'
    }, []);
    copyCookiesBtn.addEventListener('click', () => {
      const text = selectedAccounts.map(acc => acc.cookie || '').join('\n');
      copyToClipboard(text);
      toast(`Copied ${count} cookies to clipboard`, 'success');
    });

    const copyUserPassBtn = el('button', {
      class: 'btn btn-secondary',
      style: 'justify-content:flex-start;',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Copy user:pass Combo'
    }, []);
    copyUserPassBtn.addEventListener('click', () => {
      const text = selectedAccounts.map(acc => `${acc.username || ''}:${acc.password || ''}`).join('\n');
      copyToClipboard(text);
      toast(`Copied ${count} user:pass combos to clipboard`, 'success');
    });

    const copyUserPassCookieBtn = el('button', {
      class: 'btn btn-secondary',
      style: 'justify-content:flex-start;',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg> Copy user:pass:cookie Combo'
    }, []);
    copyUserPassCookieBtn.addEventListener('click', () => {
      const text = selectedAccounts.map(acc => `${acc.username || ''}:${acc.password || ''}:${acc.cookie || ''}`).join('\n');
      copyToClipboard(text);
      toast(`Copied ${count} user:pass:cookie combos to clipboard`, 'success');
    });

    copySection.appendChild(copyUsernamesBtn);
    copySection.appendChild(copyPasswordsBtn);
    copySection.appendChild(copyCookiesBtn);
    copySection.appendChild(copyUserPassBtn);
    copySection.appendChild(copyUserPassCookieBtn);
    wrap.appendChild(copySection);

    const manageSection = el('div', { style: 'display:flex;flex-direction:column;gap:6px;margin-top:auto;' }, []);
    const delAllBtn = el('button', { class: 'btn btn-danger' }, [document.createTextNode(`Delete Selected (${count})`)]);
    delAllBtn.addEventListener('click', bulkDeleteSelected);

    const clearBtn = el('button', { class: 'btn btn-secondary' }, [document.createTextNode('Clear Selection')]);
    clearBtn.addEventListener('click', () => {
      state.selectedIds = new Set();
      state.selectedId = null;
      renderAll();
    });

    manageSection.appendChild(delAllBtn);
    manageSection.appendChild(clearBtn);
    wrap.appendChild(manageSection);

    panel.appendChild(wrap);
    return;
  }

  const a = state.selectedId ? getAccount(state.selectedId) : null;
  if (!a) {
    panel.appendChild(el('div', { class: 'detail-empty' }, [document.createTextNode('Select an account to view details.')]));
    return;
  }

  const isEditing = state.editingId === a.id;
  const rev = state.revealed[a.id] || {};

  const header = el('div', { class: 'detail-header' }, []);
  const avatarRow = el('div', { class: 'detail-avatar-row' }, []);

  if (state.settings.downloadAvatarIcons !== false && a.avatar_url) {
    const avatarImg = el('img', {
      src: a.avatar_url,
      alt: a.username,
      style: 'width:36px;height:36px;border-radius:8px;border:1px solid var(--border);object-fit:cover;'
    }, []) as HTMLImageElement;
    avatarImg.onerror = () => {
      const fallback = el('div', { class: 'avatar' }, [document.createTextNode(initials(a.username))]);
      avatarImg.replaceWith(fallback);
    };
    avatarRow.appendChild(avatarImg);
  } else {
    avatarRow.appendChild(el('div', { class: 'avatar' }, [document.createTextNode(initials(a.username))]));
  }

  const nameWrap = el('div', { class: 'detail-name' }, []);
  if (isEditing) {
    const nameInput = el('input', { type: 'text', value: a.username, id: 'edit-username' }, []) as HTMLInputElement;
    nameWrap.appendChild(nameInput);
  } else {
    const nameRow = el('div', { style: 'display:flex;align-items:center;gap:6px;' }, [
      el('span', { class: 'dot ' + statusMeta(a.status).dot, title: `Status: ${statusMeta(a.status).label}` }, []),
      el('span', { style: 'font-weight:600;font-size:13px;color:var(--fg);' }, [document.createTextNode(a.display_name || a.username || '(unnamed)')])
    ]);
    nameWrap.appendChild(nameRow);
    if (a.display_name && a.display_name !== a.username) {
      nameWrap.appendChild(el('div', { style: 'font-size:11px;color:var(--muted);' }, [document.createTextNode('@' + a.username)]));
    }
    if (a.user_id) {
      nameWrap.appendChild(el('div', { style: 'font-size:10px;color:var(--muted);font-family:IBM Plex Mono, monospace;' }, [document.createTextNode('ID: ' + a.user_id)]));
    }
  }
  avatarRow.appendChild(nameWrap);
  header.appendChild(avatarRow);

  const actions = el('div', { class: 'detail-actions', style: 'display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;' }, []);
  if (isEditing) {
    const saveBtn = el('button', { class: 'btn btn-primary btn-block' }, [document.createTextNode('Save')]);
    saveBtn.addEventListener('click', () => saveEdit(a.id));

    const cancelBtn = el('button', { class: 'btn btn-secondary' }, [document.createTextNode('Cancel')]);
    cancelBtn.addEventListener('click', () => { state.editingId = null; renderAll(); });

    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);
  } else {
    const launchBtn = el('button', {
      class: 'btn btn-primary',
      style: 'flex:1;',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="5 3 19 12 5 21 5 3"/></svg> Launch'
    }, []);
    launchBtn.addEventListener('click', () => handleLaunchAccount(a.id));

    const browserBtn = el('button', {
      class: 'btn btn-secondary',
      title: 'Open in Browser',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
    }, []);
    browserBtn.addEventListener('click', () => handleLaunchBrowser(a.id));

    const editBtn = el('button', {
      class: 'btn btn-secondary',
      title: 'Edit account details',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/></svg>'
    }, []);
    editBtn.addEventListener('click', () => { state.editingId = a.id; renderAll(); });

    const delBtn = el('button', {
      class: 'btn btn-danger',
      title: 'Delete account',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>'
    }, []);
    delBtn.addEventListener('click', () => deleteAccount(a.id));

    actions.appendChild(launchBtn);
    actions.appendChild(browserBtn);
    actions.appendChild(editBtn);
    actions.appendChild(delBtn);
  }
  header.appendChild(actions);
  panel.appendChild(header);

  const body = el('div', { class: 'detail-body' }, []);

  if (isEditing) {
    const statusBlock = el('div', {}, []);
    statusBlock.appendChild(el('div', { class: 'field-label' }, [document.createTextNode('Status')]));
    const statusSel = el('select', { class: 'detail-select', id: 'edit-status' }, []) as HTMLSelectElement;
    (["valid", "expired", "banned"] as const).forEach(s => {
      const o = el('option', { value: s }, []) as HTMLOptionElement;
      o.textContent = statusMeta(s).label;
      if (s === a.status) o.selected = true;
      statusSel.appendChild(o);
    });
    statusBlock.appendChild(statusSel);
    body.appendChild(statusBlock);
  }

  const groupBlock = el('div', { class: 'detail-field-group' }, []);
  const groupLabelRow = el('div', { style: 'display:flex;align-items:center;justify-content:space-between;' }, [
    el('div', { class: 'field-label' }, [document.createTextNode('Group')])
  ]);
  if (!isEditing) {
    const editGroupBtn = el('button', {
      class: 'icon-btn',
      title: 'Edit Group',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/></svg>'
    }, []);
    editGroupBtn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      showSetGroupModal([a]);
    });
    groupLabelRow.appendChild(editGroupBtn);
  }
  groupBlock.appendChild(groupLabelRow);

  if (isEditing) {
    const groupInput = el('input', { class: 'detail-input', type: 'text', id: 'edit-group', list: 'edit-group-datalist' }, []) as HTMLInputElement;
    groupInput.value = a.group || '';
    groupBlock.appendChild(groupInput);

    const datalist = el('datalist', { id: 'edit-group-datalist' }, []) as HTMLDataListElement;
    const existingGroups: string[] = [];
    state.accounts.forEach(acc => {
      const g = (acc.group || '').trim();
      if (g && g !== 'All Groups' && !existingGroups.includes(g)) {
        existingGroups.push(g);
      }
    });
    existingGroups.sort((x, y) => x.localeCompare(y));
    existingGroups.forEach(g => {
      datalist.appendChild(el('option', { value: g }, []));
    });
    groupBlock.appendChild(datalist);
  } else {
    const groupValRow = el('div', {
      class: `field-value ${a.group ? 'row-group ' : ''}detail-group-clickable`,
      style: 'cursor:pointer;',
      title: 'Click to edit group'
    }, [
      el('span', {}, [document.createTextNode(a.group || '—')])
    ]);
    groupValRow.addEventListener('click', () => {
      showSetGroupModal([a]);
    });
    groupBlock.appendChild(groupValRow);
  }

  const isStreamer = Boolean(state.settings.streamerMode);
  const hideSensitive = isStreamer && Boolean(state.settings.streamerHideSensitiveInfo);

  const pwBlock = el('div', { class: 'detail-field-pw' }, []);
  pwBlock.appendChild(el('div', { class: 'field-label' }, [document.createTextNode('Password')]));
  const pwRow = el('div', { class: 'secret-row' }, []);
  const pwSpan = el('span', {}, []);
  pwSpan.textContent = a.password ? ((rev.password && !hideSensitive) ? a.password : '••••••••') : '—';
  pwRow.appendChild(pwSpan);
  if (a.password) {
    const pwToggle = el('button', {
      class: 'icon-btn',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>'
    }, []);
    pwToggle.addEventListener('click', () => {
      if (hideSensitive) {
        toast('Disable Streamer Mode sensitive protection to reveal passwords', 'info');
        return;
      }
      state.revealed[a.id] = state.revealed[a.id] || {};
      state.revealed[a.id].password = !state.revealed[a.id].password;
      renderAll();
    });
    pwRow.appendChild(pwToggle);
  }
  pwBlock.appendChild(pwRow);
  body.appendChild(pwBlock);

  const ckBlock = el('div', { class: 'detail-field-cookie' }, []);
  ckBlock.appendChild(el('div', { class: 'field-label' }, [document.createTextNode('Cookie')]));
  const ckRow = el('div', { class: 'secret-row' }, []);
  const ckSpan = el('span', {}, []);
  ckSpan.textContent = a.cookie ? ((rev.cookie && !hideSensitive) ? a.cookie : '••••••••••••') : '—';
  ckRow.appendChild(ckSpan);
  if (a.cookie) {
    const ckToggle = el('button', {
      class: 'icon-btn',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>'
    }, []);
    ckToggle.addEventListener('click', () => {
      if (hideSensitive) {
        toast('Disable Streamer Mode sensitive protection to reveal cookies', 'info');
        return;
      }
      state.revealed[a.id] = state.revealed[a.id] || {};
      state.revealed[a.id].cookie = !state.revealed[a.id].cookie;
      renderAll();
    });

    const ckCopy = el('button', {
      class: 'icon-btn',
      html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>'
    }, []);
    ckCopy.addEventListener('click', () => {
      copyToClipboard(a.cookie);
      toast('Cookie copied to clipboard');
    });
    ckRow.appendChild(ckToggle);
    ckRow.appendChild(ckCopy);
  }
  ckBlock.appendChild(ckRow);
  body.appendChild(ckBlock);

  const noteBlock = el('div', { class: 'detail-field-note' }, []);
  noteBlock.appendChild(el('div', { class: 'field-label' }, [document.createTextNode('Note')]));
  if (isEditing) {
    const noteArea = el('textarea', { class: 'note-edit', id: 'edit-note' }, []) as HTMLTextAreaElement;
    noteArea.value = a.note || '';
    noteBlock.appendChild(noteArea);
  } else {
    const noteVal = el('div', { class: 'field-value row-note detail-note' }, []);
    noteVal.style.whiteSpace = 'pre-wrap';
    noteVal.textContent = a.note || '—';
    noteBlock.appendChild(noteVal);
  }
  body.appendChild(noteBlock);

  const autoRejoinBlock = el('div', { class: 'auto-rejoin-block detail-field-rejoin' }, []);
  autoRejoinBlock.appendChild(el('div', { class: 'field-label' }, [document.createTextNode('Auto-Rejoin')]));
  const isAutoRejoinOn = Boolean(a.auto_rejoin_enabled);
  const autoRejoinBtn = el('button', {
    class: 'btn btn-sm auto-rejoin-btn ' + (isAutoRejoinOn ? 'btn-primary' : 'btn-secondary'),
    html: (isAutoRejoinOn ? 'Active' : 'Disabled')
  }, []);
  if (isAutoRejoinOn) {
    autoRejoinBtn.style.background = 'var(--emerald)';
    autoRejoinBtn.style.borderColor = 'var(--emerald)';
    autoRejoinBtn.style.color = '#ffffff';
  }
  autoRejoinBtn.addEventListener('click', async () => {
    const newState = !a.auto_rejoin_enabled;
    a.auto_rejoin_enabled = newState;
    await apiService.updateAccount(a.id, { auto_rejoin_enabled: newState });
    toast(`${newState ? 'Enabled' : 'Disabled'} Auto-Rejoin for @${a.username}`, 'info');
    renderAll();
  });
  autoRejoinBlock.appendChild(autoRejoinBtn);
  body.appendChild(autoRejoinBlock);

  const antiAfkBlock = el('div', { class: 'anti-afk-block detail-field-afk' }, []);
  antiAfkBlock.appendChild(el('div', { class: 'field-label' }, [document.createTextNode('Anti-AFK')]));
  const isAntiAfkOn = Boolean(a.anti_afk_enabled);
  const antiAfkBtn = el('button', {
    class: 'btn btn-sm anti-afk-btn ' + (isAntiAfkOn ? 'btn-primary' : 'btn-secondary'),
    html: (isAntiAfkOn ? 'Active' : 'Disabled')
  }, []);
  if (isAntiAfkOn) {
    antiAfkBtn.style.background = 'var(--emerald)';
    antiAfkBtn.style.borderColor = 'var(--emerald)';
    antiAfkBtn.style.color = '#ffffff';
  }
  antiAfkBtn.addEventListener('click', async () => {
    const newState = !a.anti_afk_enabled;
    a.anti_afk_enabled = newState;
    await apiService.updateAccount(a.id, { anti_afk_enabled: newState });
    toast(`${newState ? 'Enabled' : 'Disabled'} Anti-AFK for @${a.username}`, 'info');
    renderAll();
  });
  antiAfkBlock.appendChild(antiAfkBtn);
  body.appendChild(antiAfkBlock);

  panel.appendChild(body);
}

async function showSubplacesModal(initialPlaceId: string = '', parentGameName?: string): Promise<void> {
  const pInput = document.getElementById('place-input') as HTMLInputElement | null;
  const rawId = (initialPlaceId || pInput?.value || '').trim();
  const idMatch = rawId.match(/(?:games|placeId=|\/)?(\d{4,15})/);
  const targetId = idMatch ? idMatch[1] : (rawId.match(/^\d+$/) ? rawId : '');

  if (!targetId) {
    toast('Please enter a Place ID first to view its subplaces', 'info');
    return;
  }

  const overlay = el('div', { class: 'modal-overlay' }, []);
  const modal = el('div', {
    class: 'modal',
    style: 'max-width: 520px; width: 92%; max-height: 80vh; display:flex; flex-direction:column;'
  }, [
    el('div', { class: 'modal-header' }, [
      el('h3', { class: 'modal-title' }, [
        document.createTextNode(`Universe Subplaces (${parentGameName || `Place ${targetId}`})`)
      ]),
      el('button', { class: 'modal-close', html: '&times;' }, [])
    ]),
    el('div', {
      class: 'modal-body',
      style: 'overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:10px; padding:16px;'
    }, [
      el('div', {
        id: 'subplaces-loading',
        style: 'color:var(--text-muted); font-size:13px; text-align:center; padding:24px;'
      }, [
        document.createTextNode(`Loading universe subplaces for Place ${targetId}...`)
      ])
    ])
  ]);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  const closeBtn = modal.querySelector('.modal-close') as HTMLElement;
  const closeModal = () => overlay.remove();
  closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  const body = modal.querySelector('.modal-body') as HTMLElement;

  try {
    const res = await apiService.getSubplaces(targetId);
    body.innerHTML = '';
    if (res && res.success && Array.isArray(res.subplaces) && res.subplaces.length > 0) {
      const intro = el('div', { style: 'font-size:12px; color:var(--text-muted); margin-bottom:4px;' }, [
        document.createTextNode(`Found ${res.subplaces.length} subplace(s) in this universe. Click to set as subplace.`)
      ]);
      body.appendChild(intro);

      const list = el('div', { style: 'display:flex; flex-direction:column; gap:8px;' }, []);
      res.subplaces.forEach(sub => {
        const item = el('div', {
          class: 'card',
          style: 'padding:10px 14px; display:flex; align-items:center; justify-content:space-between; gap:12px; background:var(--bg-2); border:1px solid var(--border); border-radius:6px; cursor:pointer; transition:border-color 0.15s ease;'
        }, [
          el('div', { style: 'display:flex; flex-direction:column; gap:2px; overflow:hidden;' }, [
            el('div', { style: 'font-weight:600; font-size:13px; color:var(--fg); word-break:break-all;' }, [document.createTextNode(sub.name || `Place ${sub.id}`)]),
            el('div', { style: 'font-size:11px; color:var(--text-muted); font-family:monospace;' }, [document.createTextNode(`ID: ${sub.id}`)])
          ])
        ]);

        const actionBtns = el('div', { style: 'display:flex; gap:6px; flex-shrink:0;' }, []);

        const applySubplace = () => {
          state.serverMode = 'subplace';
          const serverInput = document.getElementById('server-input') as HTMLInputElement | null;
          if (serverInput) {
            serverInput.value = String(sub.id);
            state.settings.lastSubplaceId = String(sub.id);
            saveLaunchBarState();
            renderLaunchBar();
          }
          toast(`Subplace ID set to ${sub.id}`);
          closeModal();
        };

        const setSubplaceBtn = el('button', { class: 'btn btn-primary btn-sm', style: 'font-size:11.5px; padding:4px 10px;' }, [
          document.createTextNode('Set Subplace')
        ]);
        setSubplaceBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          applySubplace();
        });
        actionBtns.appendChild(setSubplaceBtn);

        item.addEventListener('click', (e) => {
          const target = e.target as HTMLElement;
          if (target.tagName === 'BUTTON' || target.closest('button')) return;
          applySubplace();
        });

        const saveSubBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'font-size:11.5px; padding:4px 10px;' }, [
          document.createTextNode('+ Save')
        ]);
        saveSubBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          try {
            saveSubBtn.setAttribute('disabled', 'true');
            const newGame = await apiService.createGame({
              name: sub.name || `Place ${sub.id}`,
              placeId: String(sub.id)
            });
            state.games.push(newGame);
            toast(`Saved game "${sub.name || sub.id}"`);
            renderGames();
          } catch (err) {
            toast('Failed to save subplace: ' + err, 'error');
          } finally {
            saveSubBtn.removeAttribute('disabled');
          }
        });
        actionBtns.appendChild(saveSubBtn);

        item.appendChild(actionBtns);
        list.appendChild(item);
      });
      body.appendChild(list);
    } else {
      body.appendChild(el('div', { style: 'color:var(--text-muted); font-size:13px; text-align:center; padding:24px;' }, [
        document.createTextNode(res?.error || 'No subplaces found for this universe, or place is not part of a multi-place universe.')
      ]));
    }
  } catch (err: any) {
    body.innerHTML = '';
    body.appendChild(el('div', { style: 'color:var(--red); font-size:13px; padding:16px; text-align:center;' }, [
      document.createTextNode(`Failed to fetch subplaces: ${err?.message || err}`)
    ]));
  }
}

function showAddGameModal(): void {
  const appContainer = document.getElementById('app');
  if (!appContainer) return;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <h3>Save Game</h3>
        <button class="modal-close" id="add-game-close">×</button>
      </div>
      <div class="modal-body">
        <div class="field" style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-size: 12px; font-weight: 500;">Place ID or Game Link <span style="color: red;">*</span></label>
          <input type="text" id="add-game-place-id" placeholder="e.g. 142823291 or https://roblox.com/games/..." style="width: 100%;" />
        </div>
        <div class="field" style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-size: 12px; font-weight: 500;">Private Server ID / Link (Optional)</label>
          <input type="text" id="add-game-server-id" placeholder="e.g. VIP server link or code" style="width: 100%;" />
        </div>
        <div class="field" style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-size: 12px; font-weight: 500;">Game Name</label>
          <input type="text" id="add-game-name" placeholder="Auto-fetching game name..." style="width: 100%;" />
        </div>
        <div id="add-game-preview-box" style="display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 6px; font-size: 12px;">
          <div id="add-game-icon-preview" style="width: 32px; height: 32px; border-radius: 4px; background: var(--bg-2); display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="6 3 20 12 6 21 6 3"/></svg>
          </div>
          <div style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            <span id="add-game-status-text" style="color: var(--muted); font-size: 11px;">Enter a Place ID to fetch details</span>
          </div>
        </div>
      </div>
      <div class="modal-footer" style="display:flex; justify-content:space-between; align-items:center; width:100%;">
        <button class="btn btn-secondary" id="add-game-explore-subplaces" type="button" style="font-size:12px;">Explore Subplaces</button>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-secondary" id="add-game-cancel">Cancel</button>
          <button class="btn btn-primary" id="add-game-save">Save Game</button>
        </div>
      </div>
    </div>
  `;

  appContainer.appendChild(overlay);

  const placeInput = document.getElementById('add-game-place-id') as HTMLInputElement;
  const serverInput = document.getElementById('add-game-server-id') as HTMLInputElement;
  const nameInput = document.getElementById('add-game-name') as HTMLInputElement;
  const closeBtn = document.getElementById('add-game-close');
  const cancelBtn = document.getElementById('add-game-cancel');
  const saveBtn = document.getElementById('add-game-save') as HTMLButtonElement;
  const iconPreview = document.getElementById('add-game-icon-preview');
  const statusText = document.getElementById('add-game-status-text');

  let fetchedIconUrl = '';
  let isUserModifiedName = false;
  let fetchTimer: ReturnType<typeof setTimeout> | null = null;

  nameInput.addEventListener('input', () => {
    if (nameInput.value.trim().length > 0) {
      isUserModifiedName = true;
    }
  });

  const extractPlaceAndServer = (val: string) => {
    let raw = val.trim();
    if (!raw) return { placeId: '', serverId: '' };

    const extracted = extractPrivateServerCode(raw);
    const placeMatch = raw.match(/(?:games|placeId=|\/)?(\d{4,15})/);
    const extractedPlaceId = extracted.placeId || (placeMatch ? placeMatch[1] : (raw.match(/^\d+$/) ? raw : ''));
    const extractedServerId = extracted.code !== raw ? extracted.code : '';

    return { placeId: extractedPlaceId, serverId: extractedServerId };
  };

  const handlePlaceInputChange = async () => {
    const val = placeInput.value.trim();
    const parsed = extractPlaceAndServer(val);

    if (parsed.serverId && !serverInput.value.trim()) {
      serverInput.value = parsed.serverId;
    }

    if (/roblox\.com\/(?:share|share-links)|roblox:\/\/navigation\/share_links|share\?code=/i.test(val)) {
      try {
        const resolved = await resolveAndNormalizePrivateServer(val);
        if (resolved.placeId && (!parsed.placeId || parsed.placeId !== resolved.placeId)) {
          placeInput.value = resolved.placeId;
        }
        if (resolved.code && !serverInput.value.trim()) {
          serverInput.value = resolved.code;
        }
      } catch (_) { }
    }

    const targetPlaceId = placeInput.value.trim().match(/(?:games|placeId=|\/)?(\d{4,15})/)?.[1] || parsed.placeId;

    if (!targetPlaceId) {
      if (statusText) statusText.textContent = 'Enter a Place ID to fetch details';
      if (iconPreview) {
        iconPreview.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
      }
      return;
    }

    if (statusText) statusText.textContent = `Fetching info for Place ${targetPlaceId}...`;

    if (fetchTimer) clearTimeout(fetchTimer);
    fetchTimer = setTimeout(async () => {
      try {
        const info = await apiService.getGameInfo(targetPlaceId);
        if (info && info.name && !info.error) {
          if (!isUserModifiedName || !nameInput.value.trim()) {
            nameInput.value = info.name;
          }
          fetchedIconUrl = info.icon_url || '';
          if (statusText) statusText.textContent = `Found: ${info.name}`;
          if (iconPreview) {
            if (info.icon_url) {
              iconPreview.innerHTML = `<img src="${info.icon_url}" style="width:100%;height:100%;object-fit:cover;" />`;
            } else {
              iconPreview.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
            }
          }
        } else {
          if (!isUserModifiedName || !nameInput.value.trim()) {
            nameInput.value = `Place ${targetPlaceId}`;
          }
          if (statusText) statusText.textContent = `Place ${targetPlaceId}`;
        }
      } catch (err) {
        if (!isUserModifiedName || !nameInput.value.trim()) {
          nameInput.value = `Place ${targetPlaceId}`;
        }
        if (statusText) statusText.textContent = `Place ${targetPlaceId}`;
      }
    }, 250);
  };

  placeInput.addEventListener('input', handlePlaceInputChange);

  serverInput.addEventListener('input', () => {
    const rawVal = serverInput.value.trim();
    const direct = extractPrivateServerCode(rawVal);
    if (direct.code && direct.code !== rawVal) {
      serverInput.value = direct.code;
      if (direct.placeId && !placeInput.value.trim()) {
        placeInput.value = direct.placeId;
        handlePlaceInputChange();
      }
    }
  });

  serverInput.addEventListener('blur', async () => {
    const rawVal = serverInput.value.trim();
    if (rawVal) {
      const normalized = await resolveAndNormalizePrivateServer(rawVal);
      if (normalized.code && normalized.code !== rawVal) {
        serverInput.value = normalized.code;
      }
      if (normalized.placeId && !placeInput.value.trim()) {
        placeInput.value = normalized.placeId;
        handlePlaceInputChange();
      }
    }
  });

  const closeModal = () => {
    if (fetchTimer) clearTimeout(fetchTimer);
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);
  const exploreSubplacesBtn = document.getElementById('add-game-explore-subplaces');
  exploreSubplacesBtn?.addEventListener('click', () => {
    const rawPlaceVal = placeInput.value.trim();
    const parsed = extractPlaceAndServer(rawPlaceVal);
    const placeId = parsed.placeId || rawPlaceVal;
    if (!placeId) {
      toast('Please enter a Place ID first to explore subplaces', 'info');
      placeInput.focus();
      return;
    }
    showSubplacesModal(placeId, nameInput.value.trim());
  });
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  saveBtn.addEventListener('click', async () => {
    const rawPlaceVal = placeInput.value.trim();
    const parsed = extractPlaceAndServer(rawPlaceVal);
    const placeId = parsed.placeId || rawPlaceVal;
    let rawServerVal = serverInput.value.trim() || parsed.serverId;
    if (rawServerVal) {
      const normalizedServer = await resolveAndNormalizePrivateServer(rawServerVal);
      rawServerVal = normalizedServer.code || rawServerVal;
    }
    const serverId = rawServerVal;
    const name = nameInput.value.trim() || (placeId ? `Place ${placeId}` : 'Roblox Game');

    if (!placeId) {
      toast('Please enter a valid Place ID', 'error');
      placeInput.focus();
      return;
    }

    try {
      const determinedServerMode = serverId ? detectServerMode(serverId, state.serverMode) : undefined;
      const newGame = await apiService.createGame({
        name,
        placeId,
        serverId: serverId || undefined,
        serverMode: determinedServerMode,
        placeMode: state.placeMode,
        icon_url: fetchedIconUrl || undefined
      });
      state.games.push(newGame);
      toast(`Saved game "${name}"`);
      renderGames();
      closeModal();
    } catch (err) {
      addLog('Failed to save game: ' + err, 'error');
      toast('Failed to save game', 'error');
    }
  });

  placeInput.focus();
}

function renderGames(): void {
  const row = document.getElementById('games-row');
  if (!row) return;

  if (state.settings.showSavedGamesBar === false) {
    row.style.display = 'none';
    return;
  }
  row.style.display = '';

  if (state.placeMode === 'user') {
    renderSavedUsersBar(row);
    return;
  }

  row.innerHTML = "";
  const label = el('span', {
    class: 'games-label',
    html: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1"><path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/></svg>'
  }, []);
  label.appendChild(document.createTextNode(' Saved Games'));
  row.appendChild(label);

  state.games.forEach(g => {
    const chip = el('div', {
      class: 'game-chip' + (state.activeGame === g.id ? ' active' : '')
    }, []);

    if (g.icon_url) {
      const img = el('img', {
        src: g.icon_url,
        class: 'game-chip-icon',
        alt: g.name
      }, []);
      chip.appendChild(img);
    } else {
      const svgIcon = el('span', {
        class: 'game-chip-icon-fallback',
        html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="6 3 20 12 6 21 6 3"/></svg>'
      }, []);
      chip.appendChild(svgIcon);
    }

    const nameSpan = el('span', { class: 'gname' }, [document.createTextNode(g.name)]);
    chip.appendChild(nameSpan);

    const placeIdSpan = el('span', { class: 'gid' }, [document.createTextNode(g.placeId)]);
    chip.appendChild(placeIdSpan);

    if (g.serverId) {
      const vipBadge = el('span', {
        class: 'game-chip-vip',
        title: `Private Server ID: ${g.serverId}`
      }, [document.createTextNode('VIP')]);
      chip.appendChild(vipBadge);
    }

    chip.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      showSubplacesModal(g.placeId, g.name);
    });

    const deleteBtn = el('button', {
      class: 'game-chip-delete',
      title: 'Delete saved game',
      html: '×'
    }, []);

    deleteBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await apiService.deleteGame(g.id);
        state.games = state.games.filter(item => item.id !== g.id);
        if (state.activeGame === g.id) {
          state.activeGame = null;
        }
        toast(`Deleted saved game "${g.name}"`);
        renderGames();
      } catch (err) {
        toast('Failed to delete game', 'error');
      }
    });
    chip.appendChild(deleteBtn);

    chip.addEventListener('click', () => {
      state.activeGame = g.id;
      state.activeSavedUser = null;
      state.placeMode = g.placeMode || 'place';
      const serverVal = (g.serverId || '').trim();
      if (serverVal) {
        state.serverMode = g.serverMode || detectServerMode(serverVal);
        if (state.serverMode === 'jobid') {
          state.settings.lastJobId = serverVal;
        } else if (state.serverMode === 'subplace') {
          state.settings.lastSubplaceId = serverVal;
        } else {
          state.settings.lastVipServerId = serverVal;
        }
      }
      const placeInput = document.getElementById('place-input') as HTMLInputElement | null;
      const serverInput = document.getElementById('server-input') as HTMLInputElement | null;
      if (placeInput) {
        placeInput.value = g.placeId;
        updateTargetGameFromPlaceInput(g.placeId);
      }
      if (serverInput) {
        serverInput.value = serverVal;
      }
      renderLaunchBar();
      saveLaunchBarState();
      renderGames();
    });

    row.appendChild(chip);
  });

  const addChip = el('button', {
    class: 'game-chip-add',
    html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="M12 5v14"/></svg>'
  }, []);
  addChip.appendChild(document.createTextNode(' Add'));
  addChip.addEventListener('click', () => {
    showAddGameModal();
  });
  row.appendChild(addChip);
}

function renderSavedUsersBar(row: HTMLElement): void {
  row.innerHTML = "";
  const label = el('span', {
    class: 'games-label',
    html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
  }, []);
  label.appendChild(document.createTextNode(' Saved Users'));
  row.appendChild(label);

  (state.savedUsers || []).forEach(u => {
    const chip = el('div', {
      class: 'game-chip' + (state.activeSavedUser === u.id ? ' active' : '')
    }, []);

    if (u.icon_url) {
      const img = el('img', {
        src: u.icon_url,
        class: 'game-chip-icon',
        alt: u.username
      }, []);
      chip.appendChild(img);
    } else {
      const svgIcon = el('span', {
        class: 'game-chip-icon-fallback',
        html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
      }, []);
      chip.appendChild(svgIcon);
    }

    const nameSpan = el('span', { class: 'gname' }, [document.createTextNode(u.display_name || u.username)]);
    chip.appendChild(nameSpan);

    const userHandleSpan = el('span', { class: 'gid' }, [document.createTextNode(`@${u.username}`)]);
    chip.appendChild(userHandleSpan);

    const deleteBtn = el('button', {
      class: 'game-chip-delete',
      title: 'Delete saved user target',
      html: '×'
    }, []);

    deleteBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await apiService.deleteSavedUser(u.id);
        state.savedUsers = state.savedUsers.filter(item => item.id !== u.id);
        if (state.activeSavedUser === u.id) {
          state.activeSavedUser = null;
        }
        toast(`Deleted saved user "@${u.username}"`);
        renderGames();
      } catch (err) {
        toast('Failed to delete saved user', 'error');
      }
    });
    chip.appendChild(deleteBtn);

    chip.addEventListener('click', () => {
      state.activeSavedUser = u.id;
      state.activeGame = null;
      state.placeMode = 'user';
      const placeInput = document.getElementById('place-input') as HTMLInputElement | null;
      if (placeInput) {
        placeInput.value = u.username;
        updateTargetGameFromPlaceInput(u.username);
      }
      renderLaunchBar();
      saveLaunchBarState();
      renderGames();
    });

    row.appendChild(chip);
  });

  const addChip = el('button', {
    class: 'game-chip-add',
    html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="M12 5v14"/></svg>'
  }, []);
  addChip.appendChild(document.createTextNode(' Add'));
  addChip.addEventListener('click', () => {
    showAddSavedUserModal();
  });
  row.appendChild(addChip);
}

function showAddSavedUserModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const overlay = el('div', { class: 'modal-overlay' }, []);
  const modal = el('div', { class: 'modal', style: 'max-width:440px;' }, []);

  const header = el('div', { class: 'modal-header' }, [
    el('h3', {}, [document.createTextNode('Save User Target')]),
    el('button', { class: 'modal-close', id: 'add-user-modal-close' }, [document.createTextNode('×')])
  ]);

  const body = el('div', { class: 'modal-body' }, []);

  const formGroup = el('div', { class: 'form-group' }, [
    el('label', {}, [document.createTextNode('Roblox Username or User ID')]),
    el('input', {
      type: 'text',
      id: 'add-user-input',
      class: 'setup-input',
      placeholder: 'e.g. Builderman or 156',
      autocomplete: 'off'
    }, [])
  ]);

  const previewBox = el('div', {
    id: 'add-user-preview',
    style: 'display:none; margin-top:12px; padding:10px 14px; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; align-items:center; gap:12px;'
  }, []);

  body.appendChild(formGroup);
  body.appendChild(previewBox);

  const footer = el('div', { class: 'modal-footer' }, [
    el('button', { class: 'btn btn-secondary', id: 'add-user-cancel' }, [document.createTextNode('Cancel')]),
    el('button', { class: 'btn btn-primary', id: 'add-user-save' }, [document.createTextNode('Save User')])
  ]);

  modal.appendChild(header);
  modal.appendChild(body);
  modal.appendChild(footer);
  overlay.appendChild(modal);
  app.appendChild(overlay);

  const userInput = document.getElementById('add-user-input') as HTMLInputElement;
  const saveBtn = document.getElementById('add-user-save') as HTMLButtonElement;
  const closeBtn = document.getElementById('add-user-modal-close');
  const cancelBtn = document.getElementById('add-user-cancel');

  const closeModal = () => overlay.remove();
  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  let fetchedInfo: { username: string; displayName?: string; userId?: string; avatar_url?: string } | null = null;
  let lookupDebounce: any = null;

  userInput.addEventListener('input', () => {
    clearTimeout(lookupDebounce);
    const val = userInput.value.trim().replace(/^@/, '');
    if (!val) {
      previewBox.style.display = 'none';
      fetchedInfo = null;
      return;
    }
    lookupDebounce = setTimeout(async () => {
      try {
        const info = await apiService.getUserInfo(val);
        if (info && info.username && !info.error) {
          fetchedInfo = {
            username: info.username,
            displayName: info.display_name || info.username,
            userId: info.user_id ? String(info.user_id) : undefined,
            avatar_url: info.avatar_url || (info.user_id ? `https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds=${info.user_id}&size=150x150&format=Png&isCircular=true` : undefined)
          };
          previewBox.style.display = 'flex';
          previewBox.innerHTML = `
            <img src="${escapeHtml(fetchedInfo.avatar_url || '')}" style="width:36px;height:36px;border-radius:50%;background:var(--border);" onerror="this.style.display='none'" />
            <div>
              <div style="font-weight:600;font-size:13px;color:var(--fg);">${escapeHtml(fetchedInfo.displayName || '')}</div>
              <div style="font-size:11px;color:var(--muted);">@${escapeHtml(fetchedInfo.username)} ${fetchedInfo.userId ? `(ID: ${escapeHtml(fetchedInfo.userId)})` : ''}</div>
            </div>
          `;
        } else {
          previewBox.style.display = 'none';
          fetchedInfo = null;
        }
      } catch (_) {
        previewBox.style.display = 'none';
        fetchedInfo = null;
      }
    }, 400);
  });

  saveBtn.addEventListener('click', async () => {
    const rawVal = userInput.value.trim().replace(/^@/, '');
    if (!rawVal) {
      toast('Please enter a username or User ID', 'info');
      return;
    }

    try {
      saveBtn.disabled = true;
      const targetUser = fetchedInfo || { username: rawVal };
      const created = await apiService.createSavedUser(targetUser);
      state.savedUsers.push(created);
      toast(`Saved user target "@${created.username}"`, 'success');
      renderGames();
      closeModal();
    } catch (err) {
      toast('Failed to save user target', 'error');
    } finally {
      saveBtn.disabled = false;
    }
  });

  setTimeout(() => userInput.focus(), 100);
}

let placeFetchTimeout: ReturnType<typeof setTimeout> | null = null;
let _targetGameGeneration = 0;
async function updateTargetGameFromPlaceInput(value: string): Promise<void> {
  const myGen = ++_targetGameGeneration;
  const trimmed = value.trim();

  if (!trimmed) {
    state.targetGameName = undefined;
    state.targetGameIcon = undefined;
    state.targetGameLoading = false;
    state.targetUserJoinable = undefined;
    state.targetUserPresence = undefined;
    state.targetUserLocation = undefined;
    renderLaunchBar();
    return;
  }

  if (state.placeMode === 'user') {
    state.targetGameLoading = true;
    renderLaunchBar();
    try {
      const cleanUser = trimmed.replace(/^@/, '');
      const res = await apiService.getUserInfo(cleanUser);
      if (myGen !== _targetGameGeneration) return;
      if (res && res.username && !res.error) {
        state.targetGameName = `@${res.username}`;
        state.targetGameIcon = res.avatar_url || (res.user_id ? `https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds=${res.user_id}&size=150x150&format=Png&isCircular=true` : undefined);
        state.targetUserJoinable = res.joinable;
        state.targetUserPresence = res.presence_type;
        state.targetUserLocation = res.location;
      } else {
        state.targetGameName = trimmed.startsWith('@') ? trimmed : `@${trimmed}`;
        state.targetGameIcon = undefined;
        state.targetUserJoinable = undefined;
        state.targetUserPresence = undefined;
        state.targetUserLocation = undefined;
      }
    } catch (_) {
      if (myGen !== _targetGameGeneration) return;
      state.targetGameName = trimmed.startsWith('@') ? trimmed : `@${trimmed}`;
      state.targetGameIcon = undefined;
      state.targetUserJoinable = undefined;
      state.targetUserPresence = undefined;
      state.targetUserLocation = undefined;
    } finally {
      if (myGen === _targetGameGeneration) {
        state.targetGameLoading = false;
        renderLaunchBar();
      }
    }
    return;
  }

  const match = trimmed.match(/(?:games|placeId=|\/)?(\d{4,15})/);
  const placeId = match ? match[1] : (trimmed.match(/^\d+$/) ? trimmed : '');

  if (!placeId) {
    state.targetGameName = undefined;
    state.targetGameIcon = undefined;
    state.targetGameLoading = false;
    renderLaunchBar();
    return;
  }

  state.targetGameLoading = true;
  renderLaunchBar();

  try {
    const res = await apiService.getGameInfo(placeId);
    if (myGen !== _targetGameGeneration) return;
    if (res && res.name && !res.error) {
      state.targetGameName = res.name;
      state.targetGameIcon = res.icon_url || '';
      addLog(`Target game: ${res.name}`, 'info');
    } else {
      state.targetGameName = `Place ${placeId}`;
      state.targetGameIcon = undefined;
    }
  } catch (_) {
    if (myGen !== _targetGameGeneration) return;
    state.targetGameName = `Place ${placeId}`;
    state.targetGameIcon = undefined;
  } finally {
    if (myGen === _targetGameGeneration) {
      state.targetGameLoading = false;
      renderLaunchBar();
    }
  }
}

function saveLaunchBarState(): void {
  const placeInput = document.getElementById('place-input') as HTMLInputElement | null;
  const serverInput = document.getElementById('server-input') as HTMLInputElement | null;

  const currentPlaceVal = placeInput ? placeInput.value : '';
  const currentServerVal = serverInput ? serverInput.value : '';
  const lastPlaceMode = state.placeMode;
  const lastServerMode = state.serverMode;

  if (state.placeMode === 'user') {
    state.settings.lastUserId = currentPlaceVal;
  } else {
    state.settings.lastPlaceId = currentPlaceVal;
  }

  if (state.serverMode === 'jobid') {
    state.settings.lastJobId = currentServerVal;
  } else if (state.serverMode === 'subplace') {
    state.settings.lastSubplaceId = currentServerVal;
  } else {
    state.settings.lastVipServerId = currentServerVal;
  }
  state.settings.lastServerId = currentServerVal;
  state.settings.lastPlaceMode = lastPlaceMode;
  state.settings.lastServerMode = lastServerMode;

  apiService.updateSettings({
    lastPlaceId: state.settings.lastPlaceId,
    lastUserId: state.settings.lastUserId,
    lastServerId: currentServerVal,
    lastVipServerId: state.settings.lastVipServerId,
    lastJobId: state.settings.lastJobId,
    lastSubplaceId: state.settings.lastSubplaceId,
    lastPlaceMode,
    lastServerMode
  }).catch(() => { });
}

function switchPlaceMode(targetMode: 'place' | 'user'): void {
  if (state.placeMode === targetMode) return;

  const placeInput = document.getElementById('place-input') as HTMLInputElement | null;
  if (placeInput) {
    if (state.placeMode === 'user') {
      state.settings.lastUserId = placeInput.value;
    } else {
      state.settings.lastPlaceId = placeInput.value;
    }
  }

  state.placeMode = targetMode;
  if (targetMode === 'place') {
    state.activeSavedUser = null;
  } else {
    state.activeGame = null;
  }

  const restoredVal = targetMode === 'user' ? (state.settings.lastUserId || '') : (state.settings.lastPlaceId || '');
  if (placeInput) {
    placeInput.value = restoredVal;
  }

  renderLaunchBar();
  renderGames();
  updateTargetGameFromPlaceInput(restoredVal);
  saveLaunchBarState();
  toast(targetMode === 'place' ? 'Switched to Place ID mode' : 'Switched to Join User mode', 'info');
}

function switchServerMode(targetMode: 'vip' | 'jobid' | 'subplace'): void {
  if (state.serverMode === targetMode) return;

  const serverInput = document.getElementById('server-input') as HTMLInputElement | null;
  if (serverInput) {
    if (state.serverMode === 'jobid') {
      state.settings.lastJobId = serverInput.value;
    } else if (state.serverMode === 'subplace') {
      state.settings.lastSubplaceId = serverInput.value;
    } else {
      state.settings.lastVipServerId = serverInput.value;
    }
  }

  state.serverMode = targetMode;

  const restoredVal = targetMode === 'jobid'
    ? (state.settings.lastJobId || '')
    : targetMode === 'subplace'
      ? (state.settings.lastSubplaceId || '')
      : (state.settings.lastVipServerId || (targetMode === 'vip' && !state.settings.lastVipServerId && !state.settings.lastJobId && !state.settings.lastSubplaceId ? state.settings.lastServerId || '' : ''));

  if (serverInput) {
    serverInput.value = restoredVal;
  }

  renderLaunchBar();
  saveLaunchBarState();
  const modeName = targetMode === 'jobid' ? 'Join Job ID' : targetMode === 'subplace' ? 'Subplace' : 'Private Server';
  toast(`Switched to ${modeName} mode`, 'info');
}

function renderLaunchBar(): void {
  const selectedAccounts = getSelectedAccounts();
  const count = selectedAccounts.length;
  const a = count > 0 ? selectedAccounts[0] : null;

  // Target Account
  const avatarWrap = document.getElementById('launch-target-avatar-wrap');
  if (avatarWrap) {
    avatarWrap.innerHTML = '';
    if (count === 0) {
      const fb = el('div', { class: 'launch-target-avatar-fallback' }, [document.createTextNode('?')]);
      avatarWrap.appendChild(fb);
    } else if (count === 1 && a) {
      if (state.settings.downloadAvatarIcons !== false && a.avatar_url) {
        const img = el('img', { class: 'launch-target-avatar', src: a.avatar_url, alt: a.username }, []) as HTMLImageElement;
        img.onerror = () => {
          const fb = el('div', { class: 'launch-target-avatar-fallback' }, [document.createTextNode(initials(a.username))]);
          img.replaceWith(fb);
        };
        avatarWrap.appendChild(img);
      } else {
        const fb = el('div', { class: 'launch-target-avatar-fallback' }, [document.createTextNode(initials(a.username))]);
        avatarWrap.appendChild(fb);
      }
    } else {
      const fb = el('div', { class: 'launch-target-avatar-fallback launch-target-multi-badge' }, [document.createTextNode(count.toString())]);
      fb.title = `${count} accounts selected`;
      avatarWrap.appendChild(fb);
    }
  }

  const launchTarget = document.getElementById('launch-target');
  const targetLabel = launchTarget?.querySelector('.launch-target-label');
  if (targetLabel) {
    targetLabel.textContent = count > 1 ? `Target Accounts (${count})` : 'Target Account';
  }

  const launchUsername = document.getElementById('launch-username');
  if (launchUsername) {
    if (count === 0) {
      launchUsername.textContent = 'None selected';
      launchUsername.title = '';
    } else if (count === 1 && a) {
      const label = a.display_name ? `${a.display_name} (@${a.username})` : `@${a.username}`;
      launchUsername.textContent = label;
      launchUsername.title = label;
    } else {
      const names = selectedAccounts.map(x => '@' + x.username).join(', ');
      launchUsername.textContent = names;
      launchUsername.title = names;
    }
  }

  // Target Game / Target User
  const gameAvatarWrap = document.getElementById('launch-game-avatar-wrap');
  const gameNameEl = document.getElementById('launch-game-name');
  const placeInput = document.getElementById('place-input') as HTMLInputElement | null;
  const currentPlaceVal = placeInput?.value.trim() || '';

  if (gameAvatarWrap) {
    gameAvatarWrap.innerHTML = '';
    gameAvatarWrap.style.position = 'relative';

    if (state.placeMode === 'user') {
      if (state.targetGameIcon) {
        const img = el('img', {
          class: 'launch-target-avatar',
          src: state.targetGameIcon,
          alt: state.targetGameName || 'User',
          style: 'border-radius: 50%; object-fit: cover;'
        }, []) as HTMLImageElement;
        img.onerror = () => {
          const fb = el('div', { class: 'launch-target-avatar-fallback', style: 'border-radius: 50%;' }, []);
          fb.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
          img.replaceWith(fb);
        };
        gameAvatarWrap.appendChild(img);
      } else {
        const fb = el('div', { class: 'launch-target-avatar-fallback', style: 'border-radius: 50%;' }, []);
        fb.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
        gameAvatarWrap.appendChild(fb);
      }

      if (currentPlaceVal && !state.targetGameLoading && state.targetUserJoinable !== undefined) {
        const dot = document.createElement('span');
        dot.className = 'launch-user-presence-dot';
        dot.style.cssText = 'position:absolute; bottom:-1px; right:-1px; width:10px; height:10px; border-radius:50%; border:2px solid var(--bg-1, #1e293b); box-sizing:border-box;';
        if (state.targetUserJoinable) {
          dot.style.background = '#22c55e';
          dot.title = 'Joinable';
        } else if (state.targetUserPresence === 1) {
          dot.style.background = '#3b82f6';
          dot.title = 'Online';
        } else if (state.targetUserPresence === 2) {
          dot.style.background = '#f59e0b';
          dot.title = 'Joins Off';
        } else if (state.targetUserPresence === 3) {
          dot.style.background = '#f97316';
          dot.title = 'In Studio';
        } else {
          dot.style.background = '#64748b';
          dot.title = 'Not Joinable';
        }
        gameAvatarWrap.appendChild(dot);
      }
    } else {
      if (state.targetGameIcon) {
        const img = el('img', { class: 'launch-target-avatar', src: state.targetGameIcon, alt: state.targetGameName || 'Game' }, []);
        gameAvatarWrap.appendChild(img);
      } else {
        const fb = el('div', { class: 'launch-target-avatar-fallback launch-target-game-fallback' }, []);
        fb.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
        gameAvatarWrap.appendChild(fb);
      }
    }
  }

  let userStatusEl = document.getElementById('launch-user-status-badge');

  if (state.placeMode === 'user') {
    if (gameNameEl) {
      if (state.targetGameLoading) {
        gameNameEl.textContent = 'Searching...';
        gameNameEl.title = 'Searching user...';
      } else if (state.targetGameName) {
        gameNameEl.textContent = state.targetGameName;
        gameNameEl.title = state.targetGameName;
      } else if (currentPlaceVal) {
        gameNameEl.textContent = currentPlaceVal.startsWith('@') ? currentPlaceVal : `@${currentPlaceVal}`;
        gameNameEl.title = currentPlaceVal;
      } else {
        gameNameEl.textContent = 'No user';
        gameNameEl.title = 'Enter a username or user ID to join';
      }
    }

    if (!userStatusEl && gameNameEl && gameNameEl.parentElement) {
      userStatusEl = document.createElement('span');
      userStatusEl.id = 'launch-user-status-badge';
      gameNameEl.parentElement.appendChild(userStatusEl);
    }

    if (userStatusEl) {
      if (!currentPlaceVal) {
        userStatusEl.style.display = 'none';
      } else if (state.targetGameLoading) {
        userStatusEl.style.display = 'inline-flex';
        userStatusEl.innerHTML = '<span style="font-size:10px; color:var(--muted); font-weight:500;">Checking join status...</span>';
      } else if (state.targetUserJoinable !== undefined) {
        userStatusEl.style.display = 'inline-flex';
        if (state.targetUserJoinable) {
          const locText = state.targetUserLocation ? ` • ${state.targetUserLocation}` : '';
          userStatusEl.innerHTML = `<span style="display:inline-flex; align-items:center; gap:4px; font-size:10.5px; font-weight:600; color:#22c55e;" title="User is currently joinable in game${locText}"><span style="width:6px; height:6px; border-radius:50%; background:#22c55e; display:inline-block; flex-shrink:0;"></span>Joinable${locText ? ` (${state.targetUserLocation})` : ''}</span>`;
        } else {
          let label = 'Not Joinable';
          let color = '#94a3b8';
          if (state.targetUserPresence === 1) {
            label = 'Online';
            color = '#3b82f6';
          } else if (state.targetUserPresence === 2) {
            label = 'Joins Off';
            color = '#f59e0b';
          } else if (state.targetUserPresence === 3) {
            label = 'In Studio';
            color = '#f97316';
          } else {
            label = 'Offline';
            color = '#94a3b8';
          }
          userStatusEl.innerHTML = `<span style="display:inline-flex; align-items:center; gap:4px; font-size:10.5px; font-weight:600; color:${color};" title="${label}"><span style="width:6px; height:6px; border-radius:50%; background:${color}; display:inline-block; flex-shrink:0;"></span>${label}</span>`;
        }
      } else {
        userStatusEl.style.display = 'none';
      }
    }
  } else {
    if (userStatusEl) {
      userStatusEl.style.display = 'none';
    }
    if (gameNameEl) {
      if (state.targetGameLoading) {
        gameNameEl.textContent = 'Searching...';
        gameNameEl.title = 'Searching game info...';
      } else if (state.targetGameName) {
        gameNameEl.textContent = state.targetGameName;
        gameNameEl.title = state.targetGameName;
      } else if (currentPlaceVal) {
        gameNameEl.textContent = `Place ${currentPlaceVal}`;
        gameNameEl.title = `Place ${currentPlaceVal}`;
      } else {
        gameNameEl.textContent = 'Roblox Client';
        gameNameEl.title = 'Roblox Client (Home)';
      }
    }
  }

  const verSelect = document.getElementById('version-select') as HTMLSelectElement;
  if (verSelect) {
    const currentVal = state.selectedVersion || 'auto';
    verSelect.innerHTML = '<option value="auto">Latest Version</option>';
    (state.robloxVersions || []).forEach(v => {
      const opt = el('option', { value: v.path }, []) as HTMLOptionElement;
      opt.textContent = `${v.source ? `[${v.source}] ` : ''}${v.version}`;
      verSelect.appendChild(opt);
    });
    verSelect.value = currentVal;
  }

  const btnLaunch = document.getElementById('btn-launch') as HTMLButtonElement;
  const btnLaunchBrowser = document.getElementById('btn-launch-browser') as HTMLButtonElement;

  if (placeInput && btnLaunch) {
    btnLaunch.disabled = count === 0;
    if (btnLaunchBrowser) {
      btnLaunchBrowser.disabled = count === 0;
      btnLaunchBrowser.title = count > 1 ? `Open ${count} accounts in browser` : 'Open account in browser';
    }
    btnLaunch.innerHTML = `
      <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>
      ${count > 1 ? `Launch (${count})` : 'Launch'}
    `;
    const placeLabel = document.querySelector('.launch-field-place .launch-field-label');
    const targetGameLabel = document.querySelector('#launch-target-game .launch-target-label');
    const placeMenu = document.getElementById('place-mode-dropdown');
    const placeFieldWrapper = placeInput.closest('.launch-field-place') as HTMLElement | null;
    if (state.placeMode === 'place') {
      placeInput.placeholder = 'Place ID...';
      placeInput.title = 'Place ID mode';
      if (placeLabel) placeLabel.textContent = 'Place ID / Game Target';
      if (targetGameLabel) targetGameLabel.textContent = 'Target Game';
      if (placeFieldWrapper) placeFieldWrapper.classList.remove('mode-user');
    } else if (state.placeMode === 'user') {
      placeInput.placeholder = 'Username or User ID...';
      placeInput.title = 'Join User mode';
      if (placeLabel) placeLabel.textContent = 'Join Target User';
      if (targetGameLabel) targetGameLabel.textContent = 'Target User';
      if (placeFieldWrapper) placeFieldWrapper.classList.add('mode-user');
    }
    if (placeMenu) {
      placeMenu.querySelectorAll('.launch-mode-option').forEach(opt => {
        opt.classList.toggle('active', opt.getAttribute('data-mode') === state.placeMode);
      });
    }

    const serverInput = document.getElementById('server-input') as HTMLInputElement | null;
    const serverFieldWrapper = serverInput?.closest('.launch-field-server') as HTMLElement | null;
    const serverInputWrap = serverInput?.closest('.launch-input-wrap') as HTMLElement | null;
    const serverLabel = document.querySelector('.launch-field-server .launch-field-label');
    const serverMenu = document.getElementById('server-mode-dropdown');
    const serverSubplacesBtn = document.getElementById('server-subplaces-btn') as HTMLElement | null;
    if (serverFieldWrapper) {
      if (state.placeMode === 'user') {
        serverFieldWrapper.style.display = 'none';
      } else {
        serverFieldWrapper.style.display = '';
      }
    }
    if (serverSubplacesBtn && serverInputWrap) {
      if (state.serverMode === 'subplace' && state.placeMode !== 'user') {
        serverSubplacesBtn.style.display = 'flex';
        serverInputWrap.classList.add('has-subplaces-btn');
      } else {
        serverSubplacesBtn.style.display = 'none';
        serverInputWrap.classList.remove('has-subplaces-btn');
      }
    }
    if (serverInput) {
      if (state.serverMode === 'jobid') {
        serverInput.placeholder = 'Job ID...';
        serverInput.title = 'Job ID mode';
        if (serverLabel) serverLabel.textContent = 'Job ID';
      } else if (state.serverMode === 'subplace') {
        serverInput.placeholder = 'Subplace ID...';
        serverInput.title = 'Subplace ID mode';
        if (serverLabel) serverLabel.textContent = 'Subplace ID';
      } else {
        serverInput.placeholder = 'Private Server Link...';
        serverInput.title = 'Private Server Link mode';
        if (serverLabel) serverLabel.textContent = 'Private Server Link';
      }
    }
    if (serverMenu) {
      serverMenu.querySelectorAll('.launch-mode-option').forEach(opt => {
        opt.classList.toggle('active', opt.getAttribute('data-mode') === state.serverMode);
      });
    }
  }
}

async function refreshRobloxVersions(): Promise<void> {
  try {
    const versionsRes = await apiService.getRobloxVersions();
    if (versionsRes && versionsRes.success && Array.isArray(versionsRes.versions)) {
      state.robloxVersions = versionsRes.versions;
      renderLaunchBar();
    }
  } catch (err) {
    console.error('Failed to refresh Roblox versions:', err);
  }
}

// Settings rendering
interface SettingsTab {
  id: 'general' | 'roblox' | 'launching' | 'automation' | 'appearance' | 'notifications' | 'privacy' | 'security' | 'data' | 'keybinds' | 'custom-theme';
  label: string;
  icon: string;
  dividerBefore?: boolean;
}

const SETTINGS_TABS: SettingsTab[] = [
  {
    id: 'general',
    label: 'General',
    icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
  },
  {
    id: 'roblox',
    label: 'Roblox',
    icon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.926 23.998L0 18.892L5.075.002L24 5.108ZM15.348 10.09l-5.282-1.453l-1.414 5.273l5.282 1.453z"/></svg>',
    dividerBefore: true
  },
  {
    id: 'launching',
    label: 'Launching',
    icon: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>'
  },
  {
    id: 'automation',
    label: 'Automation',
    icon: '<rect width="18" height="12" x="3" y="6" rx="2"/><path d="M9 18v2"/><path d="M15 18v2"/><path d="M12 2v4"/><circle cx="8" cy="12" r="1"/><circle cx="16" cy="12" r="1"/>'
  },
  {
    id: 'appearance',
    label: 'Appearance',
    icon: '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
    dividerBefore: true
  },
  {
    id: 'notifications',
    label: 'Notifications',
    icon: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>'
  },
  {
    id: 'privacy',
    label: 'Privacy',
    icon: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    dividerBefore: true
  },
  {
    id: 'security',
    label: 'Security',
    icon: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
  },
  {
    id: 'data',
    label: 'Data',
    icon: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>'
  },
  {
    id: 'keybinds',
    label: 'Keybinds',
    icon: '<rect width="20" height="14" x="2" y="5" rx="2"/><line x1="6" x2="6.01" y1="9" y2="9"/><line x1="10" x2="10.01" y1="9" y2="9"/><line x1="14" x2="14.01" y1="9" y2="9"/><line x1="18" x2="18.01" y1="9" y2="9"/><line x1="6" x2="6.01" y1="13" y2="13"/><line x1="18" x2="18.01" y1="13" y2="13"/><line x1="10" x2="14" y1="13" y2="13"/>',
    dividerBefore: true
  }
];

interface SettingItemDefinition {
  id: string;
  tab: 'general' | 'roblox' | 'launching' | 'automation' | 'appearance' | 'notifications' | 'privacy' | 'security' | 'data' | 'keybinds' | 'custom-theme';
  label: string;
  desc: string;
  dependsOn?: { key: keyof Settings; value?: any };
  isVisible?: (settings: Settings) => boolean;
}

const ALL_SETTINGS_ITEMS: SettingItemDefinition[] = [
  // 1. General
  { id: 'setting-enable-topmost', tab: 'general', label: 'Always on Top', desc: 'Keep FRAM above other desktop windows' },
  { id: 'setting-start-at-startup', tab: 'general', label: 'Start FRAM on Windows Startup', desc: 'Automatically launch FRAM when Windows starts' },
  { id: 'setting-minimize-tray', tab: 'general', label: 'Minimize to System Tray', desc: 'Keep FRAM running in the system tray when minimized or closed' },
  { id: 'setting-default-startup-view', tab: 'general', label: 'Default Startup Landing View', desc: 'Choose which main tab opens when FRAM launches' },
  { id: 'setting-auto-validate-cookies', tab: 'general', label: 'Validate Cookies on Startup', desc: 'Validate stored account sessions when FRAM launches' },
  { id: 'setting-multi-select', tab: 'general', get label() { return state.settings.multiSelect ? `Multi Select (${getMultiSelectBindText()})` : 'Multi Select'; }, desc: 'Enable selecting multiple accounts for bulk actions' },
  { id: 'setting-account-sorting', tab: 'general', label: 'Account List Default Sorting', desc: 'Sort accounts automatically by status or username' },
  { id: 'setting-auto-update-checks', tab: 'general', label: 'Automatic Update Checks', desc: 'Check for new FRAM versions on launch' },
  { id: 'setting-rerun-setup', tab: 'general', label: 'Rerun Setup Wizard', desc: 'Reopen the initial setup and onboarding wizard' },

  // 2. Roblox
  { id: 'setting-roblox-path', tab: 'roblox', label: 'Roblox Installation Path', desc: 'Custom path to Roblox player executable (leave blank for auto-detect)' },
  { id: 'setting-roblox-global-client', tab: 'roblox', label: 'Roblox Client Settings', desc: 'Configure Graphics Quality, Frame rate cap, Volume, Controls, Camera, and Accessibility' },
  { id: 'setting-roblox-fastflags', tab: 'roblox', label: 'Roblox FastFlags Editor', desc: 'Manage custom Roblox FastFlags and fine-tune performance' },
  { id: 'setting-icon-cache', tab: 'roblox', label: 'Roblox Icon & Thumbnail Cache', desc: 'Inspect disk usage and clear downloaded game and avatar thumbnail images' },
  { id: 'setting-roblox-updates', tab: 'roblox', label: 'Auto-check for Roblox Updates', desc: 'Check whether a newer Roblox client version is available' },
  { id: 'setting-disable-executor-presets', tab: 'roblox', label: 'Disable Executor Presets', desc: 'Hide executor presets in the Roblox Installer modal' },

  // 3. Launching
  { id: 'setting-multi-instance', tab: 'launching', label: 'Multi-Instance Roblox', desc: 'Allow multiple Roblox accounts to run simultaneously without instance mutex conflicts' },
  { id: 'setting-multi-launch-delay', tab: 'launching', label: 'Multi-Account Launch Stagger Delay', desc: 'Time gap in milliseconds between launching consecutive accounts' },
  { id: 'setting-confirm-before-launch', tab: 'launching', label: 'Confirm Before Account Launch', desc: 'Show a confirmation dialog before launching accounts' },
  { id: 'setting-auto-close-crash-handlers', tab: 'launching', label: 'Auto Close RobloxCrashHandlers', desc: 'Automatically detect and terminate unresponsive RobloxCrashHandler processes' },
  { id: 'setting-auto-save-launch-details', tab: 'launching', label: 'Save Launch Details', desc: 'Automatically save game place IDs and user targets to the Saved Games bar' },
  { id: 'setting-preferred-region', tab: 'launching', label: 'Preferred Server Region', desc: 'Automatically select a preferred geographic region when joining public servers' },
  { id: 'setting-server-per-account', tab: 'launching', label: 'Server For Each Account', desc: 'Assign a different public server to each account during batch launching' },
  { id: 'setting-auto-kill-roblox', tab: 'launching', label: 'Auto-Close Roblox Clients on FRAM Exit', desc: 'Automatically terminate Roblox clients when FRAM closes' },
  { id: 'setting-headless-mode', tab: 'launching', label: 'Headless Client Launch', desc: 'Launch Roblox instances hidden in the background' },
  { id: 'setting-headless-idle-priority', tab: 'launching', label: 'Idle CPU Priority', desc: 'Lower background Roblox client CPU priority to Idle', dependsOn: { key: 'headlessMode', value: true } },
  { id: 'setting-headless-trim-memory', tab: 'launching', label: 'Headless Auto Memory Trim', desc: 'Automatically optimize memory usage for background instances', dependsOn: { key: 'headlessMode', value: true } },
  { id: 'setting-headless-actions', tab: 'launching', label: 'Headless Actions', desc: 'Quick actions to hide or restore all running Roblox clients', dependsOn: { key: 'headlessMode', value: true } },

  // 4. Automation
  { id: 'setting-keep-clients-arranged', tab: 'automation', label: 'Auto Arrange Roblox', desc: 'Automatically arrange and maintain Roblox client window positions' },
  { id: 'setting-auto-arrange-scope', tab: 'automation', label: 'Auto-Arrange Monitor Scope', desc: 'Distribute client windows across all monitors, primary monitor, or secondary monitor', dependsOn: { key: 'keepClientsArranged', value: true } },
  { id: 'setting-auto-arrange-dimension-mode', tab: 'automation', label: 'Auto-Arrange Tile Sizing Mode', desc: 'Adaptive grid fit or fixed target resolution', dependsOn: { key: 'keepClientsArranged', value: true } },
  { id: 'setting-auto-arrange-target-size', tab: 'automation', label: 'Target Client Resolution', desc: 'Target client width and height in pixels when Fixed Target Resolution is selected', dependsOn: { key: 'keepClientsArranged', value: true } },
  { id: 'setting-auto-arrange-target-width', tab: 'automation', label: 'Target Client Width', desc: 'Width used when Fixed Target Resolution is selected', dependsOn: { key: 'keepClientsArranged', value: true } },
  { id: 'setting-auto-arrange-target-height', tab: 'automation', label: 'Target Client Height', desc: 'Height used when Fixed Target Resolution is selected', dependsOn: { key: 'keepClientsArranged', value: true } },
  { id: 'setting-anti-afk', tab: 'automation', label: 'Enable Anti-AFK', desc: 'Prevent Roblox from disconnecting due to inactivity' },
  { id: 'setting-anti-afk-interval', tab: 'automation', label: 'Anti-AFK Interval', desc: 'Time in minutes between simulated input pulses (1-19 min)', dependsOn: { key: 'antiAfkEnabled', value: true } },
  { id: 'setting-anti-afk-key', tab: 'automation', label: 'Simulated Input Key', desc: 'Simulated input event sent in the background without stealing focus', dependsOn: { key: 'antiAfkEnabled', value: true } },
  { id: 'setting-anti-afk-status', tab: 'automation', label: 'Live Status', desc: 'Real-time countdown and pulse activity indicator for Anti-AFK', dependsOn: { key: 'antiAfkEnabled', value: true } },
  { id: 'setting-auto-rejoin', tab: 'automation', label: 'Enable Auto-Rejoin', desc: 'Automatically reconnect when Roblox crashes or disconnects' },
  { id: 'setting-auto-rejoin-delay', tab: 'automation', label: 'Auto-Rejoin Delay', desc: 'Delay in seconds before attempting to reconnect', dependsOn: { key: 'autoRejoinEnabled', value: true } },
  { id: 'setting-auto-rejoin-max-attempts', tab: 'automation', label: 'Maximum Attempts', desc: 'Maximum number of retries (0 = unlimited)', dependsOn: { key: 'autoRejoinEnabled', value: true } },
  { id: 'setting-auto-rejoin-behavior', tab: 'automation', label: 'Rejoin Launch Behavior', desc: 'Choose whether to reconnect to the exact VIP server or the place', dependsOn: { key: 'autoRejoinEnabled', value: true } },
  { id: 'setting-auto-relaunch', tab: 'automation', label: 'Enable Periodic Group Auto-Relaunch', desc: 'Automatically restart accounts belonging to a selected group' },
  { id: 'setting-auto-relaunch-group', tab: 'automation', label: 'Target Account Group', desc: 'Select which account group is affected', dependsOn: { key: 'autoRelaunchEnabled', value: true } },
  { id: 'setting-auto-relaunch-interval', tab: 'automation', label: 'Relaunch Interval', desc: 'How frequently the group should be relaunched in minutes', dependsOn: { key: 'autoRelaunchEnabled', value: true } },
  { id: 'setting-auto-relaunch-status', tab: 'automation', label: 'Live Schedule Status', desc: 'Real-time schedule timer and status for group auto-relaunch', dependsOn: { key: 'autoRelaunchEnabled', value: true } },
  { id: 'setting-auto-relaunch-trigger', tab: 'automation', label: 'Relaunch Group Now', desc: 'Manually trigger the automation to close and relaunch the group now', dependsOn: { key: 'autoRelaunchEnabled', value: true } },
  { id: 'setting-auto-memory-trim', tab: 'automation', label: 'Auto Memory Trim', desc: 'Periodically optimize active Roblox client memory usage' },
  { id: 'setting-auto-memory-trim-interval', tab: 'automation', label: 'Memory Trim Interval', desc: 'How frequently memory trimming occurs', dependsOn: { key: 'autoMemoryTrimEnabled', value: true } },
  { id: 'setting-preferred-browser', tab: 'automation', label: 'Preferred Automation Browser', desc: 'Default web browser used for account login & automation' },

  // 5. Appearance
  { id: 'setting-selected-theme', tab: 'appearance', label: 'Color Theme', desc: 'Choose your visual color theme or open Custom Theme Studio' },
  { id: 'setting-custom-accent', tab: 'appearance', label: 'Custom Accent Color', desc: 'Custom accent color picker for UI elements' },
  { id: 'setting-custom-background', tab: 'appearance', label: 'Custom Background Wallpaper', desc: 'Choose a background wallpaper preset or upload a custom image' },
  { id: 'setting-layout-preset', tab: 'appearance', label: 'UI Layout Format Preset', desc: 'Switch positions of Account Details panel and Launch & Saved Games bar' },
  { id: 'setting-show-detail-panel', tab: 'appearance', label: 'Show Account Inspector Panel', desc: 'Display detail panel for selected account on the right' },
  { id: 'setting-show-saved-games', tab: 'appearance', label: 'Show Saved Games Bar', desc: 'Display saved games quick-launch row at the top' },
  { id: 'setting-compact-rows', tab: 'appearance', label: 'Compact Table Rows', desc: 'Reduce account row padding density' },
  { id: 'setting-show-table-avatars', tab: 'appearance', label: 'Show Avatars in Table', desc: 'Show account avatar profile pictures in list' },
  { id: 'setting-download-avatar-icons', tab: 'appearance', label: 'Download Avatar Profile Icons', desc: 'Fetch real Roblox avatar icons instead of stylized initials' },
  { id: 'setting-active-indicator', tab: 'appearance', label: 'Show Account Status Dot', desc: 'Display an account status indicator dot in accounts table' },

  // 6. Notifications
  { id: 'setting-toast-pos', tab: 'notifications', label: 'Toast Screen Position', desc: 'Where notification popups appear on screen' },
  { id: 'setting-toast-dur', tab: 'notifications', label: 'Notification Display Time', desc: 'How long notifications remain visible' },
  { id: 'setting-launch-alerts', tab: 'notifications', label: 'Show Launch Alerts', desc: 'Show notifications when accounts are launched or browser sessions are opened' },
  { id: 'setting-error-alerts', tab: 'notifications', label: 'Show Error & Warning Alerts', desc: 'Display toast notifications on errors and warnings' },
  { id: 'setting-success-popups', tab: 'notifications', label: 'Show Success Popups', desc: 'Show success notifications when operations complete' },
  { id: 'setting-chime-effects', tab: 'notifications', label: 'Audio Chime Effects', desc: 'Play a sound when notifications appear' },
  { id: 'setting-preview-notif', tab: 'notifications', label: 'Preview Notification', desc: 'Test notification appearance, position, duration, and sound' },

  // 7. Privacy
  { id: 'setting-streamer-mode', tab: 'privacy', label: 'Streamer Mode', desc: 'Enable privacy masking throughout FRAM to prevent accidental data leaks' },
  { id: 'setting-streamer-hide-usernames', tab: 'privacy', label: 'Mask Usernames & Display Names', desc: 'Hide account usernames and display names across the interface', dependsOn: { key: 'streamerMode', value: true } },
  { id: 'setting-streamer-hide-avatars', tab: 'privacy', label: 'Blur Account Avatars', desc: 'Blur account profile pictures', dependsOn: { key: 'streamerMode', value: true } },
  { id: 'setting-streamer-hide-sensitive', tab: 'privacy', label: 'Mask Passwords, Cookies & VIP Links', desc: 'Hide sensitive account credentials, tokens, and VIP server links', dependsOn: { key: 'streamerMode', value: true } },
  { id: 'setting-streamer-hide-groups', tab: 'privacy', label: 'Hide Group Tags & Notes', desc: 'Hide account group information and notes', dependsOn: { key: 'streamerMode', value: true } },
  { id: 'setting-streamer-blur-level', tab: 'privacy', label: 'Streamer Blur Intensity', desc: 'Choose visual blur level for masked elements', dependsOn: { key: 'streamerMode', value: true } },
  { id: 'setting-streamer-reveal-hover', tab: 'privacy', label: 'Uncensor on Hover', desc: 'Temporarily uncensor masked elements when hovering your mouse over them', dependsOn: { key: 'streamerMode', value: true } },

  // 8. Security
  { id: 'setting-encryption-status', tab: 'security', label: 'Encryption Status', desc: 'Show whether account data is protected with master password and AES cipher' },
  { id: 'setting-switch-encryption', tab: 'security', label: 'Switch Encryption Method', desc: 'Change how accounts and credentials are secured, or update your master password' },
  { id: 'setting-lock-session', tab: 'security', label: 'Lock Session', desc: 'Immediately lock FRAM and require the master password to continue', isVisible: (s) => Boolean(s.encryptionEnabled && s.encryptionMethod === 'password') },

  // 9. Data
  { id: 'setting-backup-accounts', tab: 'data', label: 'Backup & Import', desc: 'Export accounts as encrypted or plain JSON, or import accounts' },
  { id: 'setting-confirm-bulk-delete', tab: 'data', label: 'Confirm Before Bulk Deletion', desc: 'Require confirmation before deleting multiple selected accounts' },
  { id: 'setting-clear-accounts', tab: 'data', label: 'Clear All Accounts', desc: 'Remove all accounts from the database' },
  { id: 'setting-delete-all-data', tab: 'data', label: 'Delete All Data', desc: 'Permanently remove accounts, games, and custom settings' },
  { id: 'setting-uninstall-app', tab: 'data', label: 'Uninstall Application', desc: 'Completely uninstall FRAM and clean up application data' },

  // 10. Keybinds
  { id: 'setting-keyboard-shortcuts', tab: 'keybinds', label: 'Keyboard Shortcuts', desc: 'Configure custom in-app hotkeys and keybind combinations for navigation, account actions, and Roblox tools' },
  { id: 'setting-keybinds-actions', tab: 'keybinds', label: 'Account Action Keybinds', desc: 'Hotkeys for launching, selecting, and managing accounts' },
  { id: 'setting-keybinds-nav', tab: 'keybinds', label: 'Navigation Hotkeys', desc: 'Hotkeys for switching between app views' },
  { id: 'setting-keybinds-tools', tab: 'keybinds', label: 'Roblox Tool Hotkeys', desc: 'Hotkeys for auto-arranging, memory trimming, and killing clients' }
];

interface KeybindDefinition {
  id: string;
  label: string;
  desc: string;
  category: 'actions' | 'navigation' | 'tools';
  defaultKeys: string[];
}

const KEYBIND_DEFINITIONS: KeybindDefinition[] = [
  // Account Actions
  { id: 'launch_selected', label: 'Launch Selected Account(s)', desc: 'Launch Roblox for selected account or all checked accounts', category: 'actions', defaultKeys: ['Enter'] },
  { id: 'multi_select', label: 'Multi-Select Accounts', desc: 'Key combination pressed while clicking an account row to toggle its selection', category: 'actions', defaultKeys: ['Ctrl+Click'] },
  { id: 'select_all', label: 'Select All Accounts', desc: 'Select all visible accounts in the active group filter', category: 'actions', defaultKeys: ['Ctrl+A'] },
  { id: 'deselect_all', label: 'Deselect All Accounts', desc: 'Clear active account selection', category: 'actions', defaultKeys: ['Ctrl+D'] },
  { id: 'search', label: 'Search Accounts & Settings', desc: 'Quickly focus the search bar from anywhere', category: 'actions', defaultKeys: ['Ctrl+F'] },
  { id: 'refresh', label: 'Refresh Accounts & Statuses', desc: 'Reload account status and Roblox sessions', category: 'actions', defaultKeys: ['F5', 'Ctrl+R'] },
  { id: 'add_account', label: 'Quick Add Account', desc: 'Open the Add Account options menu', category: 'actions', defaultKeys: ['Ctrl+N'] },
  { id: 'delete_selected', label: 'Delete Selected Account(s)', desc: 'Remove selected accounts from your library', category: 'actions', defaultKeys: ['Delete', 'Backspace'] },
  { id: 'close_or_clear', label: 'Close Modal / Clear Selection', desc: 'Close open dialogs or clear active selections', category: 'actions', defaultKeys: ['Esc'] },

  // Navigation
  { id: 'nav_accounts', label: 'Switch to Accounts', desc: 'Open Accounts list view', category: 'navigation', defaultKeys: ['Ctrl+1'] },
  { id: 'nav_instances', label: 'Switch to Instance Manager', desc: 'Open Instance Manager view', category: 'navigation', defaultKeys: ['Ctrl+2'] },
  { id: 'nav_vip', label: 'Switch to VIP Servers', desc: 'Open VIP Server Manager view', category: 'navigation', defaultKeys: ['Ctrl+3'] },
  { id: 'nav_console', label: 'Switch to Console Logs', desc: 'Open Application Console view', category: 'navigation', defaultKeys: ['Ctrl+4'] },
  { id: 'nav_webhooks', label: 'Switch to Discord Webhooks', desc: 'Open Webhook Manager view', category: 'navigation', defaultKeys: ['Ctrl+5'] },
  { id: 'nav_extensions', label: 'Switch to Extensions', desc: 'Open Extensions Manager view', category: 'navigation', defaultKeys: ['Ctrl+6'] },
  { id: 'nav_bloxgen', label: 'Switch to BloxGen Generator', desc: 'Open BloxGen Generator view', category: 'navigation', defaultKeys: ['Ctrl+7'] },
  { id: 'nav_fastflags', label: 'Switch to FastFlags Editor', desc: 'Open Roblox FastFlags Editor view', category: 'navigation', defaultKeys: ['Ctrl+9'] },
  { id: 'nav_about', label: 'Switch to About', desc: 'Open About & Build Information view', category: 'navigation', defaultKeys: ['Ctrl+0'] },
  { id: 'nav_settings', label: 'Switch to Settings', desc: 'Open Application Settings view', category: 'navigation', defaultKeys: ['Ctrl+8', 'Ctrl+,'] },

  // Roblox Tools
  { id: 'tool_auto_arrange', label: 'Auto-Arrange Clients', desc: 'Instantly tile and position active Roblox client windows', category: 'tools', defaultKeys: ['Ctrl+Shift+A'] },
  { id: 'tool_kill_roblox', label: 'Kill All Roblox Clients', desc: 'Instantly force close all active Roblox client processes', category: 'tools', defaultKeys: ['Ctrl+Shift+K'] },
  { id: 'tool_trim_memory', label: 'Trim Client Memory', desc: 'Instantly optimize RAM usage for running Roblox clients', category: 'tools', defaultKeys: ['Ctrl+Shift+M'] },
  { id: 'shortcuts_help', label: 'Keyboard Shortcuts Help', desc: 'Open the keyboard shortcuts reference dialog', category: 'tools', defaultKeys: ['Ctrl+/'] },
];

function getKeybinds(id: string): string[] {
  const custom = state.settings.customKeybinds?.[id];
  if (custom) {
    return Array.isArray(custom) ? custom : [custom];
  }
  const def = KEYBIND_DEFINITIONS.find(k => k.id === id);
  return def ? [...def.defaultKeys] : [];
}

function getMultiSelectBindText(): string {
  const keys = getKeybinds('multi_select');
  if (!keys || keys.length === 0) return 'Ctrl + Click';
  return keys.map(k => {
    return k.split('+').map(part => part.trim()).join(' + ');
  }).join(' / ');
}

function matchesMultiSelectClick(ev: MouseEvent): boolean {
  const keys = getKeybinds('multi_select');
  if (!keys || keys.length === 0) {
    return Boolean(ev.ctrlKey || ev.metaKey);
  }
  return keys.some(k => {
    const parts = k.split('+').map(p => p.trim().toLowerCase());
    const needsCtrl = parts.includes('ctrl') || parts.includes('cmd') || parts.includes('control');
    const needsAlt = parts.includes('alt');
    const needsShift = parts.includes('shift');

    if (!needsCtrl && !needsAlt && !needsShift) {
      return Boolean(ev.ctrlKey || ev.metaKey);
    }
    if (needsCtrl && !(ev.ctrlKey || ev.metaKey)) return false;
    if (needsAlt && !ev.altKey) return false;
    if (needsShift && !ev.shiftKey) return false;
    return true;
  });
}

function isCustomKeybind(id: string): boolean {
  return Boolean(state.settings.customKeybinds && state.settings.customKeybinds[id]);
}

function eventToShortcut(e: KeyboardEvent): string | null {
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push('Ctrl');
  if (e.altKey) parts.push('Alt');
  if (e.shiftKey) parts.push('Shift');

  let key = e.key;
  if (key === 'Control' || key === 'Shift' || key === 'Alt' || key === 'Meta') {
    return null;
  }

  if (key === ' ') key = 'Space';
  else if (key === 'Escape') key = 'Esc';
  else if (key === 'ArrowUp') key = 'Up';
  else if (key === 'ArrowDown') key = 'Down';
  else if (key === 'ArrowLeft') key = 'Left';
  else if (key === 'ArrowRight') key = 'Right';
  else if (key.length === 1) key = key.toUpperCase();

  parts.push(key);
  return parts.join('+');
}

function matchesShortcut(e: KeyboardEvent, shortcut: string): boolean {
  if (!shortcut) return false;
  const parts = shortcut.split('+').map(p => p.trim());
  const needsCtrl = parts.includes('Ctrl') || parts.includes('Cmd');
  const needsAlt = parts.includes('Alt');
  const needsShift = parts.includes('Shift');

  const hasCtrl = Boolean(e.ctrlKey || e.metaKey);
  const hasAlt = Boolean(e.altKey);
  const hasShift = Boolean(e.shiftKey);

  if (hasCtrl !== needsCtrl) return false;
  if (hasAlt !== needsAlt) return false;
  if (hasShift !== needsShift) return false;

  const mainKey = parts.filter(p => !['Ctrl', 'Alt', 'Shift', 'Cmd', 'Meta'].includes(p))[0];
  if (!mainKey) return false;

  let eventKey = e.key;
  if (eventKey === ' ') eventKey = 'Space';
  else if (eventKey === 'Escape') eventKey = 'Esc';
  else if (eventKey === 'ArrowUp') eventKey = 'Up';
  else if (eventKey === 'ArrowDown') eventKey = 'Down';
  else if (eventKey === 'ArrowLeft') eventKey = 'Left';
  else if (eventKey === 'ArrowRight') eventKey = 'Right';

  if (eventKey.toLowerCase() === mainKey.toLowerCase()) return true;
  if (e.code && e.code.toLowerCase() === mainKey.toLowerCase()) return true;
  if (mainKey.toLowerCase() === 'esc' && (eventKey.toLowerCase() === 'escape' || eventKey.toLowerCase() === 'esc')) return true;
  return false;
}

function matchesAction(e: KeyboardEvent, id: string): boolean {
  const keys = getKeybinds(id);
  return keys.some(k => matchesShortcut(e, k));
}

let activeRecordingKeybindId: string | null = null;
let activeRecordingKeybindCleanup: (() => void) | null = null;

function stopRecordingKeybind(): void {
  if (activeRecordingKeybindCleanup) {
    activeRecordingKeybindCleanup();
    activeRecordingKeybindCleanup = null;
  }
  activeRecordingKeybindId = null;
}

function startRecordingKeybind(actionId: string, onDone: () => void): void {
  stopRecordingKeybind();
  activeRecordingKeybindId = actionId;

  const targetAction = KEYBIND_DEFINITIONS.find(k => k.id === actionId);
  const label = targetAction ? targetAction.label : actionId;

  const applyNewShortcut = (shortcut: string) => {
    const conflictingAction = KEYBIND_DEFINITIONS.find(k => {
      if (k.id === actionId) return false;
      const currentKeys = getKeybinds(k.id);
      return currentKeys.some(ck => ck.toLowerCase() === shortcut.toLowerCase());
    });

    if (!state.settings.customKeybinds) {
      state.settings.customKeybinds = {};
    }

    state.settings.customKeybinds[actionId] = shortcut;

    if (conflictingAction) {
      delete state.settings.customKeybinds[conflictingAction.id];
      toast(`Bound "${label}" to ${shortcut} (Reassigned from "${conflictingAction.label}")`, 'info');
    } else {
      toast(`Bound "${label}" to ${shortcut}`, 'success');
    }

    updateSetting('customKeybinds', state.settings.customKeybinds).catch(() => { });
    stopRecordingKeybind();
    onDone();
  };

  const handleKeydown = (e: KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.key === 'Escape') {
      stopRecordingKeybind();
      toast(`Rebinding "${label}" cancelled`, 'info');
      onDone();
      return;
    }

    const shortcut = eventToShortcut(e);
    if (!shortcut) {
      return;
    }

    applyNewShortcut(shortcut);
  };

  const handleMousedown = (e: MouseEvent) => {
    const parts: string[] = [];
    if (e.ctrlKey || e.metaKey) parts.push('Ctrl');
    if (e.altKey) parts.push('Alt');
    if (e.shiftKey) parts.push('Shift');

    if (parts.length > 0 || actionId === 'multi_select') {
      e.preventDefault();
      e.stopPropagation();
      parts.push('Click');
      const shortcut = parts.join('+');
      applyNewShortcut(shortcut);
    }
  };

  window.addEventListener('keydown', handleKeydown, { capture: true });
  window.addEventListener('mousedown', handleMousedown, { capture: true });
  activeRecordingKeybindCleanup = () => {
    window.removeEventListener('keydown', handleKeydown, { capture: true });
    window.removeEventListener('mousedown', handleMousedown, { capture: true });
  };
}

function isSettingVisible(item: SettingItemDefinition): boolean {
  if (item.isVisible) {
    return item.isVisible(state.settings);
  }
  if (item.dependsOn) {
    const parentVal = state.settings[item.dependsOn.key];
    if (item.dependsOn.value !== undefined) {
      return parentVal === item.dependsOn.value;
    }
    return Boolean(parentVal);
  }
  return true;
}

function getVisibleSettingsItems(): SettingItemDefinition[] {
  return ALL_SETTINGS_ITEMS.filter(isSettingVisible);
}

function jumpToSetting(tabId: 'general' | 'roblox' | 'launching' | 'automation' | 'appearance' | 'notifications' | 'privacy' | 'security' | 'data' | 'keybinds' | 'custom-theme', settingTitle: string): void {
  const matchItem = ALL_SETTINGS_ITEMS.find(item =>
    item.label.toLowerCase().trim() === settingTitle.toLowerCase().trim() ||
    item.label.toLowerCase().includes(settingTitle.toLowerCase())
  );

  if (matchItem && matchItem.dependsOn) {
    const depKey = matchItem.dependsOn.key;
    const requiredVal = matchItem.dependsOn.value !== undefined ? matchItem.dependsOn.value : true;
    if ((state.settings as any)[depKey] !== requiredVal) {
      (state.settings as any)[depKey] = requiredVal;
      updateSetting(depKey as any, requiredVal);
    }
  }

  state.settingsTab = tabId;
  renderSettingsView();

  setTimeout(() => {
    const inner = document.getElementById('settings-content-inner');
    if (!inner) return;

    let rows = Array.from(inner.querySelectorAll('.setting-row, .theme-card'));
    let target = rows.find(r => {
      const label = r.querySelector('.setting-label, .theme-card-title')?.textContent || '';
      return label.toLowerCase().trim() === settingTitle.toLowerCase().trim() ||
        label.toLowerCase().includes(settingTitle.toLowerCase());
    });

    if (!target) {
      target = rows.find(r => (r.textContent || '').toLowerCase().includes(settingTitle.toLowerCase()));
    }

    if (!target) {
      const sections = Array.from(inner.querySelectorAll('.settings-section'));
      target = sections.find(s => (s.textContent || '').toLowerCase().includes(settingTitle.toLowerCase()));
    }

    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.classList.remove('setting-row-highlight');
      void (target as HTMLElement).offsetWidth;
      target.classList.add('setting-row-highlight');
      setTimeout(() => {
        target.classList.remove('setting-row-highlight');
      }, 2600);
    }
  }, 60);
}

function settingsToggleRow(label: string, desc: string, key: keyof Settings): HTMLElement {
  const row = el('div', { class: 'setting-row' }, []);
  const textWrap = el('div', {}, []);
  const labelEl = el('div', { class: 'setting-label' }, [document.createTextNode(label)]);
  textWrap.appendChild(labelEl);
  if (desc) {
    textWrap.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode(desc)]));
  }
  row.appendChild(textWrap);

  const sw = el('button', {
    class: 'switch' + (state.settings[key] ? ' on' : ''),
    type: 'button'
  }, [el('span', { class: 'knob' }, [])]) as HTMLButtonElement;
  sw.addEventListener('click', () => {
    const nextVal = !state.settings[key];
    sw.className = 'switch' + (nextVal ? ' on' : '');
    if (key === 'multiSelect') {
      labelEl.textContent = nextVal ? `Multi Select (${getMultiSelectBindText()})` : 'Multi Select';
    }
    updateSetting(key, nextVal);
  });
  row.appendChild(sw);

  return row;
}

let robloxHubAvailableVersionsCache: InstallerVersionEntry[] = [];
let robloxHubPollingTimer: any = null;

function getBootstrapperIconUrl(sourceName: string): string {
  const s = (sourceName || '').trim().toLowerCase();
  if (s === 'bloxstrap') return '/BootstrapperIcon/Bloxstrap.png';
  if (s === 'fishstrap') return '/BootstrapperIcon/Fishstrap.png';
  if (s === 'voidstrap') return '/BootstrapperIcon/Voidstrap.png';
  if (s === 'froststrap') return '/BootstrapperIcon/froststrap.png';
  if (s === 'exploitstrap') return '/BootstrapperIcon/ExploitStrap.png';
  return '/BootstrapperIcon/Roblox.png';
}

function renderRobloxHubSection(container: HTMLElement): void {
  const hubContainer = el('div', { class: 'roblox-hub-container' }, []);

  const downloadSec = el('div', { class: 'roblox-hub-section' }, []);
  const downloadHeader = el('div', { class: 'roblox-hub-header' }, [
    el('div', { class: 'roblox-hub-title' }, [document.createTextNode('DOWNLOAD')])
  ]);
  downloadSec.appendChild(downloadHeader);

  const downloadCard = el('div', { class: 'roblox-download-card' }, []);

  const cardLeft = el('div', { class: 'roblox-card-left' }, []);
  const iconBox = el('div', { class: 'roblox-card-icon-box' }, []);
  const iconImg = el('img', {
    src: getBootstrapperIconUrl('Roblox'),
    alt: 'Roblox',
    class: 'roblox-card-icon-img'
  }, []) as HTMLImageElement;
  iconBox.appendChild(iconImg);
  cardLeft.appendChild(iconBox);

  const cardDetails = el('div', { class: 'roblox-card-details' }, []);
  const cardTitle = el('div', { class: 'roblox-card-title' }, [document.createTextNode('Roblox')]);
  const cardSubtitle = el('div', { class: 'roblox-card-subtitle' }, [document.createTextNode('Roblox Corporation')]);

  const versionRow = el('div', { class: 'roblox-card-version-row' }, []);
  const clientSelect = el('select', { class: 'roblox-client-pill-select', id: 'roblox-hub-client-select' }, []) as HTMLSelectElement;
  const versionSelect = el('select', { class: 'roblox-version-pill-select', id: 'roblox-hub-version-select' }, []) as HTMLSelectElement;

  versionRow.appendChild(clientSelect);
  versionRow.appendChild(versionSelect);

  cardDetails.appendChild(cardTitle);
  cardDetails.appendChild(cardSubtitle);
  cardDetails.appendChild(versionRow);
  cardLeft.appendChild(cardDetails);
  downloadCard.appendChild(cardLeft);

  const actionBtnContainer = el('div', { style: 'display:flex; flex-direction:column; align-items:flex-end; gap:6px;' }, []);
  const actionBtn = el('button', { type: 'button' }, []) as HTMLButtonElement;
  actionBtnContainer.appendChild(actionBtn);
  downloadCard.appendChild(actionBtnContainer);

  const progressTrack = el('div', { class: 'roblox-download-progress-bar', style: 'display:none;' }, []);
  const progressFill = el('div', { class: 'roblox-download-progress-fill' }, []);
  progressTrack.appendChild(progressFill);
  const statusLabel = el('div', { class: 'installer-status-text', style: 'display:none; margin-top:4px;' }, []);

  downloadSec.appendChild(downloadCard);
  downloadSec.appendChild(progressTrack);
  downloadSec.appendChild(statusLabel);
  hubContainer.appendChild(downloadSec);

  const installedSec = el('div', { class: 'roblox-hub-section' }, []);
  const installedHeader = el('div', { class: 'roblox-hub-header' }, []);
  const installedTitle = el('div', { class: 'roblox-hub-title' }, [document.createTextNode('INSTALLED VERSIONS')]);
  const refreshBtn = el('button', { class: 'roblox-refresh-btn', type: 'button', title: 'Refresh installed versions' }, []) as HTMLButtonElement;
  refreshBtn.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>';
  installedHeader.appendChild(installedTitle);
  installedHeader.appendChild(refreshBtn);
  installedSec.appendChild(installedHeader);

  const installedListContainer = el('div', { id: 'roblox-installed-versions-list' }, []);
  installedSec.appendChild(installedListContainer);
  hubContainer.appendChild(installedSec);

  container.appendChild(hubContainer);

  const KNOWN_BOOTSTRAPPERS = [
    { id: 'roblox', name: 'Roblox', subtitle: 'Roblox Corporation' },
    { id: 'bloxstrap', name: 'Bloxstrap', subtitle: 'Bloxstrap Client' },
    { id: 'fishstrap', name: 'Fishstrap', subtitle: 'Fishstrap Client' },
    { id: 'voidstrap', name: 'Voidstrap', subtitle: 'Voidstrap Client' },
    { id: 'froststrap', name: 'FrostStrap', subtitle: 'FrostStrap Client' },
    { id: 'exploitstrap', name: 'ExploitStrap', subtitle: 'ExploitStrap Client' }
  ];

  let currentHubClients: { id: string; name: string; subtitle: string }[] = [{ id: 'roblox', name: 'Roblox', subtitle: 'Roblox Corporation' }];

  const getSelectedClientInfo = () => {
    const cid = clientSelect.value || (currentHubClients[0]?.id ?? 'roblox');
    return currentHubClients.find(b => b.id === cid)
      || KNOWN_BOOTSTRAPPERS.find(b => b.id === cid)
      || { id: cid, name: cid, subtitle: `${cid} Client` };
  };

  const updateActionButtonState = () => {
    const cinfo = getSelectedClientInfo();

    iconImg.src = getBootstrapperIconUrl(cinfo.name);
    iconImg.onerror = () => { iconImg.src = '/BootstrapperIcon/Roblox.png'; };
    iconImg.alt = cinfo.name;
    cardTitle.textContent = cinfo.name;
    cardSubtitle.textContent = cinfo.subtitle;

    actionBtn.className = 'roblox-action-download-btn';
    actionBtn.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download';
    actionBtn.title = `Download and install Roblox into ${cinfo.name}`;
  };

  clientSelect.addEventListener('change', () => {
    updateActionButtonState();
  });

  const populateClients = async () => {
    const currentVal = clientSelect.value;
    try {
      const res = await apiService.getInstallerClients();
      const serverClients = res.clients || [];
      const clientsList: { id: string; name: string; subtitle: string }[] = [];

      if (serverClients.length > 0) {
        serverClients.forEach(sc => {
          const known = KNOWN_BOOTSTRAPPERS.find(b => b.id === sc.id || b.name.toLowerCase() === sc.name.toLowerCase());
          if (known) {
            clientsList.push({ id: sc.id, name: known.name, subtitle: known.subtitle });
          } else {
            clientsList.push({ id: sc.id, name: sc.name, subtitle: `${sc.name} Client` });
          }
        });
      } else {
        clientsList.push({ id: 'roblox', name: 'Roblox', subtitle: 'Roblox Corporation' });
      }

      currentHubClients = clientsList;
      clientSelect.innerHTML = '';
      clientsList.forEach(clientItem => {
        const opt = el('option', { value: clientItem.id }, []) as HTMLOptionElement;
        opt.textContent = clientItem.name;
        if (clientItem.id === (currentVal || clientsList[0].id)) opt.selected = true;
        clientSelect.appendChild(opt);
      });
    } catch (_) {
      currentHubClients = [{ id: 'roblox', name: 'Roblox', subtitle: 'Roblox Corporation' }];
      clientSelect.innerHTML = '';
      currentHubClients.forEach(b => {
        const opt = el('option', { value: b.id }, []) as HTMLOptionElement;
        opt.textContent = b.name;
        if (b.id === (currentVal || 'roblox')) opt.selected = true;
        clientSelect.appendChild(opt);
      });
    }
    updateActionButtonState();
  };

  const startDownloadFlow = async () => {
    const cinfo = getSelectedClientInfo();
    let targetVersion = versionSelect.value;
    let targetEntry = robloxHubAvailableVersionsCache.find(v => v.version === targetVersion);
    if (!targetEntry) {
      targetEntry = robloxHubAvailableVersionsCache[0] || {
        version: targetVersion || 'version-latest',
        status: 'LIVE',
        download_channel: 'LIVE'
      };
    }

    actionBtn.disabled = true;
    progressTrack.style.display = 'block';
    statusLabel.style.display = 'block';
    progressFill.style.width = '5%';
    statusLabel.textContent = `Preparing download for ${cinfo.name}...`;

    try {
      let startRes = await apiService.startInstallerDownload(targetEntry, cinfo.id, false);
      if (!startRes.success && startRes.already_exists) {
        const overwrite = await showConfirmModal(
          'Version Already Exists',
          `Roblox version ${targetEntry.version} is already installed in ${startRes.client_name || cinfo.name}. Do you want to overwrite it?`,
          'Overwrite & Reinstall',
          true
        );
        if (overwrite) {
          startRes = await apiService.startInstallerDownload(targetEntry, cinfo.id, true);
        } else {
          actionBtn.disabled = false;
          progressTrack.style.display = 'none';
          statusLabel.style.display = 'none';
          return;
        }
      }

      if (!startRes.success) {
        toast('Installer failed: ' + (startRes.error || 'Could not start'), 'error');
        statusLabel.textContent = 'Error: ' + (startRes.error || 'Failed');
        actionBtn.disabled = false;
        return;
      }

      if (robloxHubPollingTimer) clearInterval(robloxHubPollingTimer);
      robloxHubPollingTimer = setInterval(async () => {
        try {
          const statusRes = await apiService.getInstallerStatus();
          if (statusRes && statusRes.success && statusRes.status) {
            const st = statusRes.status;
            const pct = Math.max(0, Math.min(100, st.progress || 0));
            progressFill.style.width = `${pct}%`;
            statusLabel.textContent = st.status || `Installing... ${pct}%`;

            if (st.success === true) {
              clearInterval(robloxHubPollingTimer);
              robloxHubPollingTimer = null;
              toast(`Successfully installed ${st.version || targetEntry.version} to ${cinfo.name}!`, 'success');
              setTimeout(async () => {
                progressTrack.style.display = 'none';
                statusLabel.style.display = 'none';
                actionBtn.disabled = false;
                await refreshInstalledList();
                updateActionButtonState();
              }, 1200);
            } else if (st.success === false) {
              clearInterval(robloxHubPollingTimer);
              robloxHubPollingTimer = null;
              actionBtn.disabled = false;
              toast('Installation failed: ' + (st.error || 'Unknown error'), 'error');
              statusLabel.textContent = 'Installation failed: ' + (st.error || 'Unknown error');
            }
          }
        } catch (_) { }
      }, 500);

    } catch (err: any) {
      actionBtn.disabled = false;
      progressTrack.style.display = 'none';
      statusLabel.style.display = 'none';
      toast('Failed to start installation: ' + err.message, 'error');
    }
  };

  actionBtn.addEventListener('click', () => {
    startDownloadFlow();
  });

  const populateAvailableVersions = async (forceRefresh = false) => {
    try {
      if (forceRefresh) {
        robloxHubAvailableVersionsCache = [];
      }
      let versions = robloxHubAvailableVersionsCache;
      if (!versions || versions.length === 0) {
        const res = await apiService.getInstallerAvailableVersions();
        if (res && res.success && res.versions) {
          versions = res.versions;
          robloxHubAvailableVersionsCache = versions;
        }
      }

      const currentVal = versionSelect.value;
      versionSelect.innerHTML = '';
      if (versions && versions.length > 0) {
        versions.forEach((v, idx) => {
          const opt = el('option', { value: v.version }, []) as HTMLOptionElement;
          opt.textContent = v.version;
          if (v.version === currentVal || (!currentVal && idx === 0)) opt.selected = true;
          versionSelect.appendChild(opt);
        });
      } else {
        const fallbackVer = (state.robloxVersions && state.robloxVersions[0]?.version) || 'version-latest';
        const opt = el('option', { value: fallbackVer }, []) as HTMLOptionElement;
        opt.textContent = fallbackVer;
        versionSelect.appendChild(opt);
      }
    } catch (_) {
      versionSelect.innerHTML = '<option value="version-latest">version-latest</option>';
    }
  };

  const renderInstalledList = () => {
    installedListContainer.innerHTML = '';
    const versions = state.robloxVersions || [];

    if (versions.length === 0) {
      const emptyCard = el('div', { class: 'roblox-installed-empty' }, [
        document.createTextNode('No installed Roblox versions detected. Click "Download" above to install Roblox.')
      ]);
      installedListContainer.appendChild(emptyCard);
      return;
    }

    const combinedCard = el('div', { class: 'roblox-installed-combined-card' }, []);

    versions.forEach(v => {
      const row = el('div', { class: 'roblox-installed-row' }, []);

      const left = el('div', { class: 'roblox-installed-left' }, []);
      const ic = el('div', { class: 'roblox-installed-icon-box' }, []);
      const rowIconImg = el('img', {
        src: getBootstrapperIconUrl(v.source),
        alt: v.source || 'Roblox',
        class: 'roblox-installed-icon-img'
      }, []) as HTMLImageElement;
      rowIconImg.onerror = () => { rowIconImg.src = '/BootstrapperIcon/Roblox.png'; };
      ic.appendChild(rowIconImg);
      left.appendChild(ic);

      const details = el('div', { class: 'roblox-installed-details' }, []);
      const titleEl = el('div', { class: 'roblox-installed-title' }, [
        document.createTextNode(v.source || 'Roblox')
      ]);
      const verRow = el('div', { class: 'roblox-installed-version' }, [
        document.createTextNode(v.version)
      ]);
      details.appendChild(titleEl);
      details.appendChild(verRow);
      left.appendChild(details);
      row.appendChild(left);

      const actions = el('div', { class: 'roblox-installed-actions' }, []);
      const uninstallBtn = el('button', { class: 'roblox-row-uninstall-btn', type: 'button', title: 'Uninstall this version' }, []) as HTMLButtonElement;
      uninstallBtn.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg> Uninstall';
      uninstallBtn.addEventListener('click', async () => {
        const confirmed = await showConfirmModal(
          'Uninstall Roblox Version',
          `Are you sure you want to uninstall version "${v.version}" from ${v.source}?\nThis will remove the version files from your disk.`,
          'Uninstall',
          true
        );
        if (!confirmed) return;

        uninstallBtn.disabled = true;
        uninstallBtn.textContent = 'Uninstalling...';
        toast(`Uninstalling ${v.version}...`, 'info');

        try {
          const res = await apiService.uninstallRobloxVersion(v.path, v.version);
          if (res && res.success) {
            toast(`Successfully uninstalled ${v.version} from ${v.source}`, 'success');
          } else {
            toast('Uninstall failed: ' + (res?.error || 'Unknown error'), 'error');
          }
        } catch (err: any) {
          toast('Error uninstalling version: ' + (err.message || err), 'error');
        } finally {
          await refreshInstalledList();
          updateActionButtonState();
        }
      });

      actions.appendChild(uninstallBtn);
      row.appendChild(actions);

      combinedCard.appendChild(row);
    });

    installedListContainer.appendChild(combinedCard);
  };

  const refreshInstalledList = async (showFeedback = true) => {
    refreshBtn.disabled = true;
    refreshBtn.classList.add('spinning');
    try {
      const [res] = await Promise.all([
        apiService.getRobloxVersions(),
        populateClients(),
        populateAvailableVersions(showFeedback),
        new Promise(r => setTimeout(r, 450))
      ]);
      if (res && res.success && Array.isArray(res.versions)) {
        state.robloxVersions = res.versions;
        if (showFeedback) {
          toast(`Installed versions refreshed (${res.versions.length} found)`, 'success');
        }
      } else if (showFeedback) {
        toast('Failed to refresh versions: ' + (res?.error || 'Unknown error'), 'error');
      }
      renderInstalledList();
      renderLaunchBar();
      updateActionButtonState();
    } catch (err: any) {
      if (showFeedback) {
        toast('Failed to refresh versions: ' + (err?.message || err), 'error');
      }
    } finally {
      refreshBtn.classList.remove('spinning');
      refreshBtn.disabled = false;
    }
  };

  refreshBtn.addEventListener('click', () => {
    refreshInstalledList(true);
  });

  populateClients();
  populateAvailableVersions();
  renderInstalledList();
  refreshInstalledList(false);
}

function addSwapLog(level: 'info' | 'success' | 'warn' | 'error', msg: string): void {
  const mapType: 'info' | 'success' | 'warning' | 'error' = level === 'warn' ? 'warning' : level;
  addLog(`[Spoofer] ${msg}`, mapType, 'spoofer');
}

let lastRblxSwapStatus: any = null;
let lastRblxSwapAdapters: any[] = [];
let isSpooferRunning: boolean = false;
let isCleanerRunning: boolean = false;
let lastCleanerStatus: any = null;
let globalCleanProgressTimer: any = null;
let globalCleanHideTimeout: any = null;

let lastAntiAfkStatus: any = null;
let lastAutoRelaunchStatus: any = null;

let isRobloxInstallerRunning: boolean = false;
let lastRobloxInstallerStatus: any = null;
let globalRobloxInstallerPollTimer: any = null;

let globalChromiumPollTimer: any = null;

function showRblxSwapRestoreModal(backupInfo: any, onRestored: () => void): void {
  const overlay = el('div', { class: 'rblxswap-modal-overlay' }, []);
  const card = el('div', { class: 'rblxswap-modal-card' }, []);

  const title = el('div', { class: 'rblxswap-modal-title' }, [document.createTextNode('Restore Original Identifiers')]);
  const desc = el('div', { class: 'rblxswap-modal-desc' }, [
    document.createTextNode(`Revert hardware spoofing using the snapshot backup created ${backupInfo?.saved_at ? new Date(backupInfo.saved_at).toLocaleString() : 'previously'}. Select the identifiers you wish to restore.`)
  ]);

  const checksWrap = el('div', { style: 'display:flex; flex-direction:column; gap:8px;' }, []);

  const chkMac = el('input', { type: 'checkbox', checked: 'true' }, []) as HTMLInputElement;
  const rowMac = el('label', { class: 'rblxswap-checkbox-row' }, [
    chkMac,
    el('div', { class: 'rblxswap-checkbox-label' }, [
      el('span', {}, [document.createTextNode('Network Adapter MAC Address(es)')]),
      el('span', { class: 'rblxswap-checkbox-sub' }, [document.createTextNode('Restores factory physical addresses and cycles network adapters')])
    ])
  ]);

  const chkHwid = el('input', { type: 'checkbox', checked: 'true' }, []) as HTMLInputElement;
  const rowHwid = el('label', { class: 'rblxswap-checkbox-row' }, [
    chkHwid,
    el('div', { class: 'rblxswap-checkbox-label' }, [
      el('span', {}, [document.createTextNode('Windows Hardware IDs (MachineGuid / HwProfileGuid / MachineId)')]),
      el('span', { class: 'rblxswap-checkbox-sub' }, [document.createTextNode('Restores genuine Windows registry cryptographic GUIDs')])
    ])
  ]);

  const chkVol = el('input', { type: 'checkbox', checked: backupInfo?.has?.volume ? 'true' : 'false' }, []) as HTMLInputElement;
  const rowVol = el('label', { class: 'rblxswap-checkbox-row' }, [
    chkVol,
    el('div', { class: 'rblxswap-checkbox-label' }, [
      el('span', {}, [document.createTextNode('Disk Volume Serial Number (VSN)')]),
      el('span', { class: 'rblxswap-checkbox-sub', style: 'color:#f59e0b;' }, [document.createTextNode('Rewrites original boot sector bytes. Requires system reboot to complete.')])
    ])
  ]);

  checksWrap.appendChild(rowMac);
  checksWrap.appendChild(rowHwid);
  checksWrap.appendChild(rowVol);

  const btnsWrap = el('div', { style: 'display:flex; justify-content:flex-end; gap:8px; margin-top:8px;' }, []);
  const btnCancel = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Cancel')]);
  const btnSubmit = el('button', { class: 'btn btn-primary', type: 'button' }, [document.createTextNode('Restore Selected')]);

  btnCancel.addEventListener('click', () => {
    document.body.removeChild(overlay);
  });

  btnSubmit.addEventListener('click', async () => {
    btnSubmit.setAttribute('disabled', 'true');
    btnSubmit.textContent = 'Restoring...';
    try {
      if (lastRblxSwapStatus && !lastRblxSwapStatus.elevated) {
        addSwapLog('info', 'Requesting administrator elevation via Windows UAC...');
        toast('Please approve the Windows UAC prompt to continue', 'info');
      }
      addSwapLog('info', 'Starting restore of original identifiers...');
      const res = await apiService.restoreRblxIdentifiers({
        guids: chkHwid.checked,
        mac: chkMac.checked,
        volume: chkVol.checked
      });
      if (res && res.ok) {
        addSwapLog('success', 'Original identifiers restored successfully.');
        toast('Identifiers restored from backup');
        if (chkVol.checked) {
          toast('System reboot required to re-mount restored disk volume serial', 'info');
        }
      } else {
        const err = (res && res.errors && res.errors.join(', ')) || res?.reason || 'Restore failed';
        addSwapLog('error', `Restore encountered issues: ${err}`);
        toast(`Restore completed with warnings: ${err}`, 'error');
      }
      onRestored();
      document.body.removeChild(overlay);
    } catch (err: any) {
      addSwapLog('error', `Restore request failed: ${err.message || err}`);
      toast(`Restore failed: ${err.message || err}`, 'error');
      btnSubmit.removeAttribute('disabled');
      btnSubmit.textContent = 'Restore Selected';
    }
  });

  btnsWrap.appendChild(btnCancel);
  btnsWrap.appendChild(btnSubmit);

  card.appendChild(title);
  card.appendChild(desc);
  card.appendChild(checksWrap);
  card.appendChild(btnsWrap);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
}

function showRblxSwapConfirmModal(params: {
  doMac: boolean;
  doHwid: boolean;
  doVolume: boolean;
  doRestorePoint: boolean;
  doClean: boolean;
  adapterLabel: string;
  ouiMirror: boolean;
  dhcpRefresh: boolean;
  anticheats: any[];
  onConfirm: () => void;
}): void {
  const overlay = el('div', { class: 'rblxswap-modal-overlay' }, []);
  const card = el('div', { class: 'rblxswap-modal-card rblxswap-confirm-card' }, []);

  const title = el('div', { class: 'rblxswap-modal-title' }, [document.createTextNode('Confirm Hardware & Network Spoof')]);
  const desc = el('div', { class: 'rblxswap-modal-desc' }, [
    document.createTextNode('Review the actions that will be performed. A safety snapshot of your original identifiers is automatically captured before modification.')
  ]);

  card.appendChild(title);
  card.appendChild(desc);

  if (params.anticheats && params.anticheats.length > 0) {
    const acNames = params.anticheats.map((a: any) => a.name).join(', ');
    const acNotice = el('div', { class: 'rblxswap-confirm-notice warn' }, [
      document.createTextNode(`Warning: Active anti-cheat(s) detected (${acNames}). Spoofing hardware while these kernel drivers run may trigger integrity flags in those games.`)
    ]);
    card.appendChild(acNotice);
  }

  const isHardwareEncrypted = Boolean(state.settings.encryptionEnabled && state.settings.encryptionMethod === 'hardware');
  if (params.doHwid && isHardwareEncrypted) {
    const hwNotice = el('div', { class: 'rblxswap-confirm-notice info' }, [
      document.createTextNode('Hardware Encryption Protected: Account encryption keys are securely anchored to your physical hardware profile. Spoofing registry HWIDs will not lock you out of your accounts.')
    ]);
    card.appendChild(hwNotice);
  }

  const list = el('div', { class: 'rblxswap-confirm-list' }, []);

  const makeConfirmRow = (label: string, detail: string, badgeText: string, badgeType: 'spoof' | 'reboot' | 'unchanged') => {
    const row = el('div', { class: 'rblxswap-confirm-row' }, []);
    const main = el('div', { class: 'rblxswap-confirm-main' }, [
      el('div', { class: 'rblxswap-confirm-label' }, [document.createTextNode(label)]),
      el('div', { class: 'rblxswap-confirm-detail' }, [document.createTextNode(detail)])
    ]);
    const badge = el('span', { class: `rblxswap-confirm-badge ${badgeType}` }, [document.createTextNode(badgeText)]);
    row.appendChild(main);
    row.appendChild(badge);
    return row;
  };

  list.appendChild(makeConfirmRow(
    'Network Adapter MAC Address',
    params.doMac
      ? `Target: ${params.adapterLabel} • OUI Mirror: ${params.ouiMirror ? 'Enabled' : 'Disabled'} • DHCP Renew: ${params.dhcpRefresh ? 'Enabled' : 'Disabled'}`
      : 'Network adapter physical addresses will remain unchanged.',
    params.doMac ? 'Will Spoof' : 'Unchanged',
    params.doMac ? 'spoof' : 'unchanged'
  ));

  list.appendChild(makeConfirmRow(
    'Windows Hardware IDs (HWID)',
    params.doHwid
      ? (isHardwareEncrypted
        ? 'Rotates MachineGuid, HwProfileGuid, and SQM MachineId in Windows Registry (hardware encryption key anchored & protected).'
        : 'Rotates MachineGuid, HwProfileGuid, and SQM MachineId in Windows Registry.')
      : 'Registry hardware GUIDs will remain unchanged.',
    params.doHwid ? 'Will Spoof' : 'Unchanged',
    params.doHwid ? 'spoof' : 'unchanged'
  ));

  list.appendChild(makeConfirmRow(
    'Disk Volume Serial Number (VSN)',
    params.doVolume
      ? 'Patches drive boot sector volume serial. Takes effect on next system reboot.'
      : 'Drive boot sector volume serial will remain unchanged.',
    params.doVolume ? 'Reboot Required' : 'Unchanged',
    params.doVolume ? 'reboot' : 'unchanged'
  ));

  list.appendChild(makeConfirmRow(
    'Windows System Restore Point',
    params.doRestorePoint
      ? 'Creates a system restore checkpoint before applying registry modifications.'
      : 'No system restore checkpoint will be created.',
    params.doRestorePoint ? 'Will Create' : 'Disabled',
    params.doRestorePoint ? 'spoof' : 'unchanged'
  ));

  list.appendChild(makeConfirmRow(
    'Roblox Smart Trace Cleaner',
    params.doClean
      ? `Will terminate running Roblox clients and purge residue. Global Client Settings: ${state.settings.swapPreserveSettings !== false ? 'Preserved' : 'Wiped'}.`
      : 'Smart cleaner will not run automatically.',
    params.doClean ? 'Auto-Clean' : 'Off',
    params.doClean ? 'spoof' : 'unchanged'
  ));

  card.appendChild(list);

  const hasAnyAction = params.doMac || params.doHwid || params.doVolume || params.doClean;
  if (!hasAnyAction) {
    const emptyNotice = el('div', { class: 'rblxswap-confirm-notice warn' }, [
      document.createTextNode('No spoofer or cleaner actions are enabled. Please toggle at least one option before proceeding.')
    ]);
    card.appendChild(emptyNotice);
  }

  const btnsWrap = el('div', { style: 'display:flex; justify-content:flex-end; gap:8px; margin-top:4px;' }, []);
  const btnCancel = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Cancel')]);
  const btnConfirm = el('button', { class: 'btn btn-primary', type: 'button' }, [document.createTextNode('Confirm & Spoof')]);

  if (!hasAnyAction) {
    btnConfirm.setAttribute('disabled', 'true');
  }

  btnCancel.addEventListener('click', () => {
    if (overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
  });

  btnConfirm.addEventListener('click', () => {
    if (overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
    }
    params.onConfirm();
  });

  btnsWrap.appendChild(btnCancel);
  btnsWrap.appendChild(btnConfirm);
  card.appendChild(btnsWrap);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
}

let isSpooferExtraOpen: boolean = false;
let isCleanerExtraOpen: boolean = false;

function renderRobloxSwapSection(container: HTMLElement): void {
  const SWAP_ICONS = {
    hash: '<span style="font-weight:700;font-size:16px;font-family:monospace;line-height:1;">#</span>',
    bolt: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
    trash: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>',
    disk: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect><rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>',
    globe: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>',
    refresh: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>',
    shield: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>',
    network: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"></rect><rect x="2" y="16" width="6" height="6" rx="1"></rect><rect x="9" y="2" width="6" height="6" rx="1"></rect><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"></path><path d="M12 12V8"></path></svg>',
    rocket: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>',
    key: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>',
    sliders: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg>',
    flag: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path><line x1="4" y1="22" x2="4" y2="15"></line></svg>',
    folder: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
    download: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>'
  };

  const makeIconSettingRow = (iconHtml: string, label: string, desc: string, controlEl: HTMLElement): HTMLElement => {
    const row = el('div', { class: 'setting-row' }, []);
    const main = el('div', { class: 'setting-row-main' }, []);
    const iconWrap = el('div', { class: 'setting-row-icon' }, []);
    iconWrap.innerHTML = iconHtml;
    main.appendChild(iconWrap);

    const textWrap = el('div', { class: 'setting-row-text' }, []);
    textWrap.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode(label)]));
    if (desc) {
      textWrap.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode(desc)]));
    }
    main.appendChild(textWrap);
    row.appendChild(main);
    row.appendChild(controlEl);
    return row;
  };

  const makeIconToggleRow = (iconHtml: string, label: string, desc: string, key: keyof Settings): HTMLElement => {
    const sw = el('button', {
      class: 'switch' + (state.settings[key] ? ' on' : ''),
      type: 'button'
    }, [el('span', { class: 'knob' }, [])]) as HTMLButtonElement;
    sw.addEventListener('click', () => {
      const nextVal = !state.settings[key];
      sw.className = 'switch' + (nextVal ? ' on' : '');
      updateSetting(key, nextVal);
    });
    return makeIconSettingRow(iconHtml, label, desc, sw);
  };

  let cachedAdapters: any[] = lastRblxSwapAdapters || [];
  let cachedStatus: any = lastRblxSwapStatus || null;

  const anticheatAlert = el('div', { class: 'rblxswap-ac-box', id: 'rblxswap-ac-box', style: 'display:none; margin-bottom:12px;' }, []);

  const statusBar = el('div', { class: 'rblxswap-status-bar', style: 'margin-bottom:12px;' }, []);
  const pillsWrap = el('div', { class: 'rblxswap-pills' }, []);
  const elevationPill = el('span', {
    class: 'rblxswap-status-pill' + (lastRblxSwapStatus ? (lastRblxSwapStatus.elevated ? ' elevated' : ' not-elevated') : ''),
    id: 'rblxswap-elevation-pill'
  }, [
    document.createTextNode(lastRblxSwapStatus ? (lastRblxSwapStatus.elevated ? 'Administrator Rights Active' : 'Standard User (UAC On-Demand)') : 'Checking Admin Rights...')
  ]);
  const backupPill = el('span', {
    class: 'rblxswap-status-pill' + (lastRblxSwapStatus?.backup?.exists ? ' backed-up' : ''),
    id: 'rblxswap-backup-pill'
  }, [
    document.createTextNode(lastRblxSwapStatus ? (lastRblxSwapStatus.backup?.exists ? `Backup Snapshot Active (${lastRblxSwapStatus.backup.saved_at ? new Date(lastRblxSwapStatus.backup.saved_at).toLocaleDateString() : 'Saved'})` : 'No Backup Snapshot') : 'Checking Backup...')
  ]);
  pillsWrap.appendChild(elevationPill);
  pillsWrap.appendChild(backupPill);
  statusBar.appendChild(pillsWrap);

  const statusActions = el('div', { style: 'display:flex; align-items:center; gap:8px;' }, []);
  const btnRefreshStatus = el('button', { class: 'btn btn-secondary btn-sm', type: 'button', style: 'font-size:11px;' }, [document.createTextNode('Refresh Status')]);
  const btnRevert = el('button', { class: 'btn btn-secondary btn-sm', type: 'button', style: 'font-size:11px; color:#f87171;' }, [document.createTextNode('Revert Spoof & Restore')]);
  statusActions.appendChild(btnRefreshStatus);
  statusActions.appendChild(btnRevert);
  statusBar.appendChild(statusActions);

  const spooferSec = el('div', { class: 'settings-section', id: 'setting-spoofer-section' }, []);
  spooferSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Spoofer')]));
  spooferSec.appendChild(anticheatAlert);

  const spooferCard = el('div', { class: 'settings-card' }, []);

  const spoofBtnGroup = el('div', { class: 'btn-group-split' }, []);
  const btnRunSpoof = el('button', { class: 'btn btn-primary btn-sm btn-main', type: 'button' }, [document.createTextNode(isSpooferRunning ? 'Spoofing...' : 'Spoof Now')]);
  if (isSpooferRunning) btnRunSpoof.setAttribute('disabled', 'true');
  const btnToggleSpooferExtra = el('button', {
    class: 'btn btn-primary btn-sm btn-dropdown',
    type: 'button',
    title: isSpooferExtraOpen ? 'Hide extra settings' : 'Show extra settings'
  }, []) as HTMLButtonElement;
  btnToggleSpooferExtra.innerHTML = `<svg class="swap-dropdown-arrow${isSpooferExtraOpen ? ' open' : ''}" id="spoofer-arrow" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
  spoofBtnGroup.appendChild(btnRunSpoof);
  spoofBtnGroup.appendChild(btnToggleSpooferExtra);

  spooferCard.appendChild(makeIconSettingRow(
    SWAP_ICONS.rocket,
    'Execute Spoofer',
    'Apply hardware identifier rotation and network MAC randomization',
    spoofBtnGroup
  ));

  const spooferExtraWrap = el('div', { class: 'settings-collapsible-wrap settings-nested-card' + (isSpooferExtraOpen ? ' open' : ''), id: 'spoofer-extra-wrap' }, []);
  spooferExtraWrap.appendChild(el('div', { class: 'settings-sub-header' }, [
    document.createTextNode('Spoofer Options')
  ]));

  spooferExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.hash,
    'Spoof MAC address',
    'Randomize the network adapter identifier',
    'swapSpoofMac'
  ));

  spooferExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.bolt,
    'Spoof hardware identifiers',
    'Rotate MachineGuid, HwProfileGuid, and MachineId',
    'swapSpoofHwid'
  ));

  const adapterSelect = el('select', { style: 'font-size:11.5px; max-width:240px;' }, []) as HTMLSelectElement;
  const btnCycleAdapter = el('button', { class: 'btn btn-secondary btn-sm', type: 'button' }, [document.createTextNode('Cycle')]);
  const btnResetMac = el('button', { class: 'btn btn-secondary btn-sm', type: 'button', style: 'color:var(--yellow, #fbbf24);' }, [document.createTextNode('Reset Factory')]);
  const adapterControlRow = el('div', { class: 'btn-row' }, [adapterSelect, btnCycleAdapter, btnResetMac]);

  spooferExtraWrap.appendChild(makeIconSettingRow(
    SWAP_ICONS.network,
    'Target network adapter',
    'Select specific physical adapter or spoof all active network cards',
    adapterControlRow
  ));

  spooferExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.globe,
    'OUI mirror mode',
    'Retain vendor prefix matching real hardware network card',
    'swapOuiMirror'
  ));

  spooferExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.refresh,
    'DHCP refresh',
    'Release and renew router IP address lease after spoofing',
    'swapDhcpRefresh'
  ));

  spooferExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.disk,
    'Disk volume serial (VSN)',
    'Patch boot sector volume serial number (takes effect on reboot)',
    'swapSpoofVolume'
  ));

  spooferExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.shield,
    'System restore checkpoint',
    'Create a Windows System Restore point before spoofing',
    'swapCreateRestorePoint'
  ));

  const statusRow = el('div', { class: 'setting-row' }, []);
  const statusLeft = el('div', { class: 'setting-row-main' }, []);
  const statusIcon = el('div', { class: 'setting-row-icon' }, []);
  statusIcon.innerHTML = SWAP_ICONS.shield;
  statusLeft.appendChild(statusIcon);
  const statusText = el('div', { class: 'setting-row-text' }, [
    el('div', { class: 'setting-label' }, [document.createTextNode('Elevation & Snapshot Status')]),
    el('div', { class: 'setting-desc' }, [
      el('div', { style: 'display:flex; align-items:center; gap:8px; margin-top:4px; flex-wrap:wrap;' }, [
        elevationPill,
        backupPill
      ])
    ])
  ]);
  statusLeft.appendChild(statusText);
  statusRow.appendChild(statusLeft);
  statusRow.appendChild(statusActions);
  spooferExtraWrap.appendChild(statusRow);

  spooferCard.appendChild(spooferExtraWrap);

  const cleanerRightControl = el('div', { style: 'display:flex; align-items:center; gap:10px;' }, []);
  const cleanerBtnGroup = el('div', { class: 'btn-group-split' }, []);
  const btnCleanNow = el('button', { class: 'btn btn-secondary btn-sm btn-main', type: 'button' }, [document.createTextNode(isCleanerRunning ? 'Cleaning...' : 'Clean Now')]);
  if (isCleanerRunning) btnCleanNow.setAttribute('disabled', 'true');
  const btnToggleCleanerExtra = el('button', {
    class: 'btn btn-secondary btn-sm btn-dropdown',
    type: 'button',
    title: isCleanerExtraOpen ? 'Hide cleaner settings' : 'Show cleaner settings'
  }, []) as HTMLButtonElement;
  btnToggleCleanerExtra.innerHTML = `<svg class="swap-dropdown-arrow${isCleanerExtraOpen ? ' open' : ''}" id="cleaner-arrow" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
  cleanerBtnGroup.appendChild(btnCleanNow);
  cleanerBtnGroup.appendChild(btnToggleCleanerExtra);

  const swCleanBeforeRun = el('button', {
    class: 'switch' + (state.settings.swapCleanBeforeRun ? ' on' : ''),
    type: 'button',
    title: 'Run smart cleaner automatically before spoofing'
  }, [el('span', { class: 'knob' }, [])]) as HTMLButtonElement;
  swCleanBeforeRun.addEventListener('click', () => {
    const nextVal = !state.settings.swapCleanBeforeRun;
    updateSetting('swapCleanBeforeRun', nextVal);
    swCleanBeforeRun.className = 'switch' + (nextVal ? ' on' : '');
  });

  cleanerRightControl.appendChild(cleanerBtnGroup);
  cleanerRightControl.appendChild(swCleanBeforeRun);

  spooferCard.appendChild(makeIconSettingRow(
    SWAP_ICONS.trash,
    'Run smart cleaner',
    'Clear Roblox residue from disk before the run',
    cleanerRightControl
  ));

  const isCleaningActive = isCleanerRunning || Boolean(lastCleanerStatus?.active);
  const cleanerProgressWrap = el('div', {
    class: 'cleaner-progress-container',
    id: 'cleaner-progress-wrap',
    style: isCleaningActive ? 'display:block;' : 'display:none;'
  }, []);
  const cleanerProgressHeader = el('div', { class: 'cleaner-progress-header' }, []);
  const cleanerProgressStatus = el('div', { class: 'cleaner-progress-status' }, []);
  const cleanerSpinner = el('span', { class: 'cleaner-spinner', id: 'cleaner-spinner', style: isCleaningActive ? 'display:inline-block;' : 'display:none;' }, []);
  const cleanerStatusLabel = el('span', { class: 'cleaner-progress-status-label', id: 'cleaner-status-label' }, [
    document.createTextNode(lastCleanerStatus?.step || 'Scanning and safeguarding settings...')
  ]);
  cleanerProgressStatus.appendChild(cleanerSpinner);
  cleanerProgressStatus.appendChild(cleanerStatusLabel);

  const cleanerPercentLabel = el('div', {
    class: 'cleaner-progress-percent',
    id: 'cleaner-percent-label',
    style: isCleaningActive ? 'color:var(--primary, #60a5fa);' : ''
  }, [
    document.createTextNode(lastCleanerStatus ? `${lastCleanerStatus.progress || 0}%` : '0%')
  ]);
  cleanerProgressHeader.appendChild(cleanerProgressStatus);
  cleanerProgressHeader.appendChild(cleanerPercentLabel);

  const cleanerProgressTrack = el('div', { class: 'cleaner-progress-track' }, []);
  const cleanerProgressFill = el('div', {
    class: 'cleaner-progress-fill' + (lastCleanerStatus?.progress === 100 ? ' success' : ''),
    id: 'cleaner-progress-fill',
    style: `width:${lastCleanerStatus?.progress || (isCleaningActive ? 5 : 0)}%;`
  }, []);
  cleanerProgressTrack.appendChild(cleanerProgressFill);

  cleanerProgressWrap.appendChild(cleanerProgressHeader);
  cleanerProgressWrap.appendChild(cleanerProgressTrack);
  spooferCard.appendChild(cleanerProgressWrap);

  const cleanerExtraWrap = el('div', { class: 'settings-collapsible-wrap settings-nested-card' + (isCleanerExtraOpen ? ' open' : ''), id: 'cleaner-extra-wrap' }, []);
  cleanerExtraWrap.appendChild(el('div', { class: 'settings-sub-header' }, [
    document.createTextNode('Smart Cleaner Options')
  ]));

  cleanerExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.key,
    'Purge auth tokens & LocalStorage',
    'Erase cached Roblox client cookies and session keys',
    'swapPurgeAuth'
  ));

  cleanerExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.sliders,
    'Global Client Settings',
    'Keep GlobalBasicSettings_13.xml preferences intact during cleanup',
    'swapPreserveSettings'
  ));

  cleanerExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.flag,
    'Preserve FastFlags (FFlags)',
    'Keep custom ClientAppSettings.json intact',
    'swapPreserveFastflags'
  ));

  cleanerExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.sliders,
    'Preserve App Settings',
    'Keep appStorage.json preferences (Themes, Startup, Tray) intact during cleanup',
    'swapPreserveAppSettings'
  ));

  cleanerExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.folder,
    'Clean Roblox Studio folders',
    'Delete Roblox Studio version folders during wipe',
    'swapDeleteStudio'
  ));

  cleanerExtraWrap.appendChild(makeIconToggleRow(
    SWAP_ICONS.download,
    'Automatically reinstall Roblox',
    'Download and install a fresh Roblox client after cleanup finishes',
    'swapAutoReinstallRoblox'
  ));

  spooferCard.appendChild(cleanerExtraWrap);

  spooferSec.appendChild(spooferCard);
  container.appendChild(spooferSec);

  btnToggleSpooferExtra.addEventListener('click', (e) => {
    e.stopPropagation();
    isSpooferExtraOpen = !isSpooferExtraOpen;
    const isOpen = spooferExtraWrap.classList.toggle('open', isSpooferExtraOpen);
    const arrow = document.getElementById('spoofer-arrow');
    if (arrow) arrow.classList.toggle('open', isOpen);
    btnToggleSpooferExtra.title = isOpen ? 'Hide extra settings' : 'Show extra settings';
  });

  btnToggleCleanerExtra.addEventListener('click', (e) => {
    e.stopPropagation();
    isCleanerExtraOpen = !isCleanerExtraOpen;
    const isOpen = cleanerExtraWrap.classList.toggle('open', isCleanerExtraOpen);
    const arrow = document.getElementById('cleaner-arrow');
    if (arrow) arrow.classList.toggle('open', isOpen);
    btnToggleCleanerExtra.title = isOpen ? 'Hide cleaner settings' : 'Show cleaner settings';
  });

  const populateAdapterSelect = (adapters: any[]) => {
    adapterSelect.innerHTML = '';
    const optAll = el('option', { value: '' }, [document.createTextNode('All Physical Adapters (Default)')]);
    adapterSelect.appendChild(optAll);
    adapters.forEach(a => {
      const label = `${a.name} (${a.description}) - ${a.mac}${a.spoofed ? ' [SPOOFED]' : ''}`;
      const opt = el('option', { value: a.description }, [document.createTextNode(label)]) as HTMLOptionElement;
      adapterSelect.appendChild(opt);
    });
  };

  const refreshAdapters = async () => {
    try {
      const res = await apiService.getRblxSwapAdapters();
      if (res && res.success && res.adapters) {
        cachedAdapters = res.adapters;
        lastRblxSwapAdapters = res.adapters;
        populateAdapterSelect(res.adapters);
      }
    } catch (_) { }
  };

  const refreshAllStatus = async () => {
    try {
      const res = await apiService.getRblxSwapStatus();
      if (res && res.success) {
        cachedStatus = res;
        lastRblxSwapStatus = res;

        if (res.elevated) {
          elevationPill.className = 'rblxswap-status-pill elevated';
          elevationPill.textContent = 'Administrator Rights Active';
        } else {
          elevationPill.className = 'rblxswap-status-pill not-elevated';
          elevationPill.textContent = 'Standard User (UAC On-Demand)';
        }

        if (res.backup && res.backup.exists) {
          backupPill.className = 'rblxswap-status-pill backed-up';
          backupPill.textContent = `Backup Snapshot Active (${res.backup.saved_at ? new Date(res.backup.saved_at).toLocaleDateString() : 'Saved'})`;
          btnRevert.style.display = 'inline-block';
        } else {
          backupPill.className = 'rblxswap-status-pill';
          backupPill.textContent = 'No Backup Snapshot';
          btnRevert.style.display = 'none';
        }

        if (res.anticheats && res.anticheats.length > 0) {
          anticheatAlert.style.display = 'block';
          anticheatAlert.innerHTML = '';
          const acHead = el('div', { class: 'rblxswap-ac-header' }, [
            el('div', { class: 'rblxswap-ac-title' }, [
              el('svg', { viewBox: '0 0 24 24', width: '16', height: '16', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
                el('path', { d: 'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z' }, []),
                el('line', { x1: '12', y1: '9', x2: '12', y2: '13' }, []),
                el('line', { x1: '12', y1: '17', x2: '12.01', y2: '17' }, [])
              ]),
              document.createTextNode(`Active Anti-Cheat Detected (${res.anticheats.map((a: any) => a.name).join(', ')})`)
            ])
          ]);
          anticheatAlert.appendChild(acHead);

          const acDesc = el('div', { style: 'font-size:11.5px; color:var(--muted); line-height:1.4;' }, [
            document.createTextNode('Kernel anti-cheats track hardware identifiers continuously. To avoid false flags or hardware mismatch bans in other games, disable them before spoofing:')
          ]);
          anticheatAlert.appendChild(acDesc);

          res.anticheats.forEach((ac: any) => {
            const ul = el('ul', { class: 'rblxswap-ac-steps' }, []);
            (ac.steps || []).forEach((st: string) => {
              ul.appendChild(el('li', {}, [document.createTextNode(st)]));
            });
            anticheatAlert.appendChild(ul);
          });
        } else {
          anticheatAlert.style.display = 'none';
        }
      }
    } catch (_) { }
    await refreshAdapters();
  };

  btnRefreshStatus.addEventListener('click', async () => {
    btnRefreshStatus.setAttribute('disabled', 'true');
    await refreshAllStatus();
    btnRefreshStatus.removeAttribute('disabled');
    toast('RblxSwap status and network adapters refreshed');
  });

  btnRevert.addEventListener('click', () => {
    if (cachedStatus && cachedStatus.backup) {
      showRblxSwapRestoreModal(cachedStatus.backup, () => {
        refreshAllStatus();
      });
    } else {
      toast('No backup snapshot exists to restore from', 'info');
    }
  });

  const executeSmartCleanWithProgress = async (showToastOnFinish: boolean = true): Promise<boolean> => {
    if (globalCleanHideTimeout) {
      clearTimeout(globalCleanHideTimeout);
      globalCleanHideTimeout = null;
    }
    if (globalCleanProgressTimer) {
      clearInterval(globalCleanProgressTimer);
      globalCleanProgressTimer = null;
    }

    isCleanerRunning = true;
    lastCleanerStatus = { active: true, progress: 5, step: 'Scanning and safeguarding settings...' };

    const updateCleanDom = (pct: number, stepText: string, isError: boolean = false, isSuccess: boolean = false) => {
      const wrap = document.getElementById('cleaner-progress-wrap');
      const fill = document.getElementById('cleaner-progress-fill');
      const spinner = document.getElementById('cleaner-spinner');
      const pctLabel = document.getElementById('cleaner-percent-label');
      const statusLabel = document.getElementById('cleaner-status-label');

      if (wrap) wrap.style.display = 'block';
      if (fill) {
        fill.style.width = `${pct}%`;
        fill.className = 'cleaner-progress-fill' + (isError ? ' error' : isSuccess ? ' success' : '');
      }
      if (spinner) spinner.style.display = (isError || isSuccess) ? 'none' : 'inline-block';
      if (pctLabel) {
        pctLabel.textContent = isError ? 'Failed' : `${pct}%`;
        pctLabel.style.color = isError ? '#f87171' : isSuccess ? '#4ade80' : 'var(--primary, #60a5fa)';
      }
      if (statusLabel && stepText) statusLabel.textContent = stepText;
    };

    updateCleanDom(5, 'Scanning and safeguarding settings...');
    btnCleanNow.setAttribute('disabled', 'true');
    btnCleanNow.textContent = 'Cleaning...';

    globalCleanProgressTimer = setInterval(async () => {
      try {
        const res = await apiService.getRblxSwapCleanStatus();
        if (res && res.success && res.status) {
          const st = res.status;
          const pct = Math.max(0, Math.min(100, st.progress || 0));
          lastCleanerStatus = { active: st.active !== false, progress: pct, step: st.step || '' };
          updateCleanDom(pct, st.step || '');
        }
      } catch (_) { }
    }, 120);

    try {
      addSwapLog('info', 'Executing Roblox trace clean...');
      const res = await apiService.cleanRblxTraces({
        preserve_settings: state.settings.swapPreserveSettings !== false,
        preserve_fastflags: Boolean(state.settings.swapPreserveFastflags),
        preserve_app_settings: state.settings.swapPreserveAppSettings !== false,
        delete_studio: Boolean(state.settings.swapDeleteStudio),
        purge_auth: state.settings.swapPurgeAuth !== false
      });

      if (globalCleanProgressTimer) {
        clearInterval(globalCleanProgressTimer);
        globalCleanProgressTimer = null;
      }

      if (res && res.success) {
        (res.logs || []).forEach(l => addSwapLog(l.level, l.msg));

        if (state.settings.swapAutoReinstallRoblox) {
          lastCleanerStatus = { active: true, progress: 15, step: 'Fetching latest Roblox release for reinstallation...' };
          updateCleanDom(15, 'Fetching latest Roblox release for reinstallation...');
          addSwapLog('info', 'Starting automatic Roblox client reinstallation...');

          try {
            const vRes = await apiService.getInstallerAvailableVersions();
            const targetVersion = (vRes && vRes.success && vRes.versions && vRes.versions.length > 0) ? vRes.versions[0] : null;

            if (targetVersion) {
              lastCleanerStatus = { active: true, progress: 25, step: `Downloading ${targetVersion.version}...` };
              updateCleanDom(25, `Downloading ${targetVersion.version}...`);

              const startRes = await apiService.startInstallerDownload(targetVersion, 'roblox', true);
              if (startRes && startRes.success) {
                await new Promise<void>((resolve) => {
                  const installTimer = setInterval(async () => {
                    try {
                      const iStatus = await apiService.getInstallerStatus();
                      if (iStatus && iStatus.success && iStatus.status) {
                        const st = iStatus.status;
                        const pct = Math.max(25, Math.min(100, st.progress || 25));
                        lastCleanerStatus = { active: true, progress: pct, step: st.status || '' };
                        updateCleanDom(pct, st.status || '');
                        if (st.success === true) {
                          clearInterval(installTimer);
                          addSwapLog('success', `Roblox ${targetVersion.version} reinstalled successfully.`);
                          resolve();
                        } else if (st.success === false) {
                          clearInterval(installTimer);
                          addSwapLog('warn', `Roblox reinstallation failed: ${st.error || 'Unknown error'}`);
                          resolve();
                        }
                      }
                    } catch (_) { }
                  }, 400);
                });
              } else {
                addSwapLog('warn', `Failed starting Roblox installer: ${startRes?.error || 'Unknown error'}`);
              }
            } else {
              addSwapLog('warn', 'Could not locate remote Roblox version for reinstallation.');
            }
          } catch (iErr: any) {
            addSwapLog('warn', `Automatic reinstallation error: ${iErr.message || iErr}`);
          }
        }

        const finishStep = state.settings.swapAutoReinstallRoblox
          ? 'Cleanup and Roblox reinstallation completed!'
          : 'Roblox traces cleaned successfully!';
        lastCleanerStatus = { active: false, progress: 100, step: finishStep };
        updateCleanDom(100, finishStep, false, true);
        if (showToastOnFinish) {
          toast(state.settings.swapAutoReinstallRoblox ? 'Roblox traces cleaned & reinstalled' : 'Roblox traces cleaned successfully');
        }
        globalCleanHideTimeout = setTimeout(() => {
          const wrap = document.getElementById('cleaner-progress-wrap');
          if (wrap) wrap.style.display = 'none';
          lastCleanerStatus = null;
        }, 2500);
        return true;
      } else {
        const errStep = `Clean failed: ${res?.error || 'Unknown error'}`;
        lastCleanerStatus = { active: false, progress: 0, step: errStep };
        updateCleanDom(0, errStep, true);
        addSwapLog('error', `Trace clean failed: ${res?.error || 'Unknown error'}`);
        if (showToastOnFinish) {
          toast(`Trace clean failed: ${res?.error || 'Error'}`, 'error');
        }
        globalCleanHideTimeout = setTimeout(() => {
          const wrap = document.getElementById('cleaner-progress-wrap');
          if (wrap) wrap.style.display = 'none';
          lastCleanerStatus = null;
        }, 3500);
        return false;
      }
    } catch (err: any) {
      if (globalCleanProgressTimer) {
        clearInterval(globalCleanProgressTimer);
        globalCleanProgressTimer = null;
      }
      const errStep = `Clean failed: ${err.message || err}`;
      lastCleanerStatus = { active: false, progress: 0, step: errStep };
      updateCleanDom(0, errStep, true);
      addSwapLog('error', `Clean error: ${err.message || err}`);
      if (showToastOnFinish) {
        toast(`Clean failed: ${err.message || err}`, 'error');
      }
      globalCleanHideTimeout = setTimeout(() => {
        const wrap = document.getElementById('cleaner-progress-wrap');
        if (wrap) wrap.style.display = 'none';
        lastCleanerStatus = null;
      }, 3500);
      return false;
    } finally {
      isCleanerRunning = false;
      btnCleanNow.removeAttribute('disabled');
      btnCleanNow.textContent = 'Clean Now';
    }
  };

  btnCleanNow.addEventListener('click', async () => {
    await executeSmartCleanWithProgress(true);
  });

  btnCycleAdapter.addEventListener('click', async () => {
    const selectedDesc = adapterSelect.value;
    const target = cachedAdapters.find(a => a.description === selectedDesc) || cachedAdapters[0];
    if (!target || !target.name) {
      toast('No network adapter available to cycle', 'info');
      return;
    }
    btnCycleAdapter.setAttribute('disabled', 'true');
    try {
      if (cachedStatus && !cachedStatus.elevated) {
        addSwapLog('info', 'Requesting administrator elevation via Windows UAC...');
      }
      addSwapLog('info', `Cycling adapter ${target.name}...`);
      const res = await apiService.restartRblxAdapter(target.name);
      if (res && res.success) {
        addSwapLog('success', `Adapter ${target.name} restarted.`);
        toast(`Adapter ${target.name} restarted`);
      } else {
        addSwapLog('warn', `Failed restarting adapter: ${res?.error || 'Error'}`);
        toast('Failed restarting adapter', 'error');
      }
    } catch (err: any) {
      addSwapLog('error', `Restart error: ${err.message || err}`);
    } finally {
      btnCycleAdapter.removeAttribute('disabled');
    }
  });

  btnResetMac.addEventListener('click', async () => {
    const selectedDesc = adapterSelect.value;
    const target = cachedAdapters.find(a => a.description === selectedDesc) || cachedAdapters[0];
    if (!target) {
      toast('No network adapter available to reset', 'info');
      return;
    }
    btnResetMac.setAttribute('disabled', 'true');
    try {
      if (cachedStatus && !cachedStatus.elevated) {
        addSwapLog('info', 'Requesting administrator elevation via Windows UAC...');
      }
      addSwapLog('info', `Resetting MAC address for ${target.name}...`);
      const res = await apiService.resetRblxMac({
        adapter_desc: target.description,
        adapter_name: target.name,
        restart: true
      });
      if (res && res.success) {
        addSwapLog('success', `Reset ${target.name} to factory hardware address.`);
        toast(`Reset ${target.name} to factory MAC`);
        await refreshAdapters();
      } else {
        addSwapLog('error', `Reset MAC failed: ${res?.error || 'Error'}`);
      }
    } catch (err: any) {
      addSwapLog('error', `Reset error: ${err.message || err}`);
    } finally {
      btnResetMac.removeAttribute('disabled');
    }
  });

  btnRunSpoof.addEventListener('click', () => {
    const doMac = state.settings.swapSpoofMac !== false;
    const doHwid = state.settings.swapSpoofHwid !== false;
    const doVolume = Boolean(state.settings.swapSpoofVolume);
    const doClean = Boolean(state.settings.swapCleanBeforeRun);
    const doRestorePoint = Boolean(state.settings.swapCreateRestorePoint);

    if (!doMac && !doHwid && !doVolume && !doClean) {
      toast('Select at least one spoofer or cleaner option to execute', 'info');
      return;
    }

    const selectedDesc = adapterSelect.value;
    const isAll = !selectedDesc;
    const found = cachedAdapters.find(a => a.description === selectedDesc);
    const adapterLabel = selectedDesc
      ? (found?.name ? `${found.name} (${found.description})` : selectedDesc)
      : 'All Physical Adapters (Default)';

    showRblxSwapConfirmModal({
      doMac,
      doHwid,
      doVolume,
      doRestorePoint,
      doClean,
      adapterLabel,
      ouiMirror: state.settings.swapOuiMirror !== false,
      dhcpRefresh: state.settings.swapDhcpRefresh !== false,
      anticheats: cachedStatus?.anticheats || [],
      onConfirm: async () => {
        isSpooferRunning = true;
        btnRunSpoof.setAttribute('disabled', 'true');
        btnRunSpoof.textContent = 'Spoofing...';

        try {
          if (doClean) {
            addSwapLog('info', 'Executing smart trace cleaner before spoof run...');
            await executeSmartCleanWithProgress(false);
          }

          if (doRestorePoint || doHwid || doVolume || doMac) {
            if (cachedStatus && !cachedStatus.elevated) {
              addSwapLog('info', 'Requesting administrator elevation via Windows UAC...');
              toast('Please approve the Windows UAC prompt to continue', 'info');
            }
            addSwapLog('info', 'Executing hardware & network spoofing sequence...');
            const sRes = await apiService.spoofRblxAll({
              create_restore_point: doRestorePoint,
              restore_point_desc: 'FRAM RblxSwap Pre-Spoof',
              guids: doHwid,
              volume: doVolume,
              mac: doMac,
              all_adapters: isAll,
              adapter_desc: found?.description,
              adapter_name: found?.name,
              mirror_oui: state.settings.swapOuiMirror !== false,
              restart: true
            });

            if (sRes && sRes.success) {
              if (doRestorePoint && sRes.restore_point) {
                if (sRes.restore_point.ok) {
                  addSwapLog('success', 'System Restore point created.');
                } else {
                  addSwapLog('warn', `System Restore point skipped: ${sRes.restore_point.message || 'Error'}`);
                }
              }

              if (sRes.hwid && sRes.hwid.length > 0) {
                sRes.hwid.forEach((r: any) => {
                  if (r.ok) {
                    addSwapLog('success', `Spoofed ${r.name}: ${r.value}${r.reboot ? ' (Applies on reboot)' : ''}`);
                  } else {
                    addSwapLog('error', `Failed ${r.name}: ${r.error || 'Denied'}`);
                  }
                });
              }

              if (sRes.mac && sRes.mac.length > 0) {
                sRes.mac.forEach((r: any) => {
                  addSwapLog(r.ok ? 'success' : 'error', `${r.name || r.desc}: new MAC ${r.mac} ${r.ok ? 'applied' : 'failed'}`);
                });
              } else if (sRes.single_mac) {
                addSwapLog('success', `Applied new MAC: ${sRes.single_mac}`);
              }

              if (doMac && state.settings.swapDhcpRefresh !== false) {
                addSwapLog('info', 'Refreshing DHCP IP lease...');
                await apiService.dhcpRblxRefresh();
                addSwapLog('success', 'DHCP refresh finished.');
              }

              addSwapLog('success', 'Hardware & MAC spoofing complete.');
              toast('Hardware & MAC spoofing complete');
              if (doVolume) {
                toast('Disk Volume Serial will take effect on next system reboot', 'info');
              }
            } else {
              const err = sRes?.error || 'Spoofing failed';
              addSwapLog('error', `Spoofing encountered an error: ${err}`);
              toast(`Spoofing failed: ${err}`, 'error');
            }
          }

          await refreshAllStatus();
        } catch (err: any) {
          addSwapLog('error', `Spoof exception: ${err.message || err}`);
          toast(`Spoofing error: ${err.message || err}`, 'error');
        } finally {
          isSpooferRunning = false;
          btnRunSpoof.removeAttribute('disabled');
          btnRunSpoof.textContent = 'Spoof Now';
        }
      }
    });
  });

  if (!lastRblxSwapStatus) {
    setTimeout(refreshAllStatus, 60);
  } else if (lastRblxSwapAdapters.length > 0) {
    populateAdapterSelect(lastRblxSwapAdapters);
  }
}

function openSwitchEncryptionModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const existing = document.getElementById('switch-encryption-modal-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'switch-encryption-modal-overlay';

  const modal = document.createElement('div');
  modal.className = 'modal switch-encryption-modal';

  const currentMethod: 'password' | 'hardware' | 'none' = state.settings.encryptionEnabled
    ? (state.settings.encryptionMethod || 'password')
    : 'none';
  let targetMethod: 'password' | 'hardware' | 'none' = currentMethod;

  modal.innerHTML = `
    <div class="modal-header">
      <h3 style="margin:0; font-size:13px; font-weight:600; color:var(--fg);">
        Switch Encryption Method
      </h3>
      <button class="modal-close" id="switch-enc-close" type="button">✕</button>
    </div>
    <div class="modal-body" style="padding: 16px 20px; max-height: 75vh; overflow-y: auto;">
      <p style="font-size:12px; color:var(--muted); margin:0 0 14px 0; line-height:1.45;">
        Choose how your Roblox accounts, session cookies, and stored credentials are protected on this device.
      </p>

      <div class="switch-enc-section-label">Select Encryption Method</div>
      <div class="switch-enc-list" id="switch-enc-cards">
        <div class="switch-enc-card ${targetMethod === 'password' ? 'selected' : ''}" data-method="password" id="card-enc-password">
          <div class="switch-enc-radio"></div>
          <div class="switch-enc-info">
            <div class="switch-enc-header">
              <span class="switch-enc-title">Master Password</span>
              ${currentMethod === 'password' ? '<span class="security-card-badge badge-active">Active</span>' : '<span class="security-card-badge badge-rec">Recommended</span>'}
            </div>
            <div class="switch-enc-desc">AES-256 GCM encryption.</div>
          </div>
        </div>

        <div class="switch-enc-card ${targetMethod === 'hardware' ? 'selected' : ''}" data-method="hardware" id="card-enc-hardware">
          <div class="switch-enc-radio"></div>
          <div class="switch-enc-info">
            <div class="switch-enc-header">
              <span class="switch-enc-title">Hardware Profile</span>
              ${currentMethod === 'hardware' ? '<span class="security-card-badge badge-active">Active</span>' : ''}
            </div>
            <div class="switch-enc-desc">Machine-bound key (UUID & CPU).</div>
          </div>
        </div>

        <div class="switch-enc-card ${targetMethod === 'none' ? 'selected' : ''}" data-method="none" id="card-enc-none">
          <div class="switch-enc-radio"></div>
          <div class="switch-enc-info">
            <div class="switch-enc-header">
              <span class="switch-enc-title">No Encryption</span>
              ${currentMethod === 'none' ? '<span class="security-card-badge badge-active">Active</span>' : ''}
            </div>
            <div class="switch-enc-desc">Plain text JSON storage.</div>
          </div>
        </div>
      </div>

      <div class="switch-enc-section-label" style="margin-top:14px;">Configuration & Details</div>
      <div id="switch-enc-dynamic-form"></div>
      <div id="switch-enc-error-box" class="security-error-alert" style="display:none;"></div>
    </div>
    <div class="modal-footer" style="padding:12px 20px; display:flex; justify-content:flex-end; gap:8px;">
      <button class="btn btn-secondary" id="switch-enc-cancel" type="button">Cancel</button>
      <button class="btn btn-primary" id="switch-enc-confirm" type="button">Confirm</button>
    </div>
  `;

  overlay.appendChild(modal);
  app.appendChild(overlay);

  const closeModal = () => overlay.remove();
  document.getElementById('switch-enc-close')?.addEventListener('click', closeModal);
  document.getElementById('switch-enc-cancel')?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  const formArea = document.getElementById('switch-enc-dynamic-form');
  const confirmBtn = document.getElementById('switch-enc-confirm') as HTMLButtonElement | null;
  const errorBox = document.getElementById('switch-enc-error-box');

  let savedCurrentPassword = '';
  let savedNewPassword = '';
  let savedConfPassword = '';

  const showError = (msg: string) => {
    if (!errorBox) return;
    errorBox.textContent = msg;
    errorBox.style.display = 'flex';
  };
  const hideError = () => {
    if (!errorBox) return;
    errorBox.textContent = '';
    errorBox.style.display = 'none';
  };

  const calculatePasswordStrength = (pwd: string): { percent: number; label: string; color: string } => {
    if (!pwd) return { percent: 0, label: '', color: 'var(--border)' };
    let score = 0;
    if (pwd.length >= 8) score += 25;
    if (pwd.length >= 12) score += 15;
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score += 20;
    if (/\d/.test(pwd)) score += 20;
    if (/[^a-zA-Z0-9]/.test(pwd)) score += 20;
    score = Math.min(100, score);
    if (score < 40) return { percent: score, label: 'Weak', color: '#f87171' };
    if (score < 70) return { percent: score, label: 'Fair', color: '#fbbf24' };
    if (score < 90) return { percent: score, label: 'Good', color: '#60a5fa' };
    return { percent: score, label: 'Strong', color: '#4ade80' };
  };

  const attachEyeToggle = (inputId: string, btnId: string): void => {
    const inp = document.getElementById(inputId) as HTMLInputElement | null;
    const btn = document.getElementById(btnId) as HTMLButtonElement | null;
    if (!inp || !btn) return;
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const isPass = inp.type === 'password';
      inp.type = isPass ? 'text' : 'password';
      btn.innerHTML = isPass
        ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
        : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
    });
  };

  const renderDynamicForm = () => {
    if (!formArea) return;

    const oldCurr = document.getElementById('switch-curr-pwd') as HTMLInputElement | null;
    if (oldCurr) savedCurrentPassword = oldCurr.value;
    const oldNew = document.getElementById('switch-new-pwd') as HTMLInputElement | null;
    if (oldNew) savedNewPassword = oldNew.value;
    const oldConf = document.getElementById('switch-conf-pwd') as HTMLInputElement | null;
    if (oldConf) savedConfPassword = oldConf.value;

    hideError();

    let html = '';

    if (targetMethod === 'password') {
      const isUpdatingPassword = (currentMethod === 'password');
      html += `
        <div class="switch-enc-form-box">
          <div style="font-size:12px; font-weight:600; color:var(--fg);">
            ${isUpdatingPassword ? 'Change Master Password' : 'Create Master Password'}
          </div>

          ${currentMethod === 'password' ? `
            <div class="switch-enc-field">
              <label>Current Master Password <span style="color:var(--red);">*</span></label>
              <div class="switch-enc-input-wrap">
                <input type="password" id="switch-curr-pwd" placeholder="Enter current password to authorize" autocomplete="current-password" />
                <button type="button" class="switch-enc-eye" id="switch-curr-pwd-eye" title="Toggle password visibility">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>
            </div>
          ` : ''}

          <div class="switch-enc-field">
            <label>${isUpdatingPassword ? 'New Master Password' : 'Master Password'} <span style="color:var(--red);">*</span></label>
            <div class="switch-enc-input-wrap">
              <input type="password" id="switch-new-pwd" placeholder="New master password (min 8 chars)" autocomplete="new-password" />
              <button type="button" class="switch-enc-eye" id="switch-new-pwd-eye" title="Toggle password visibility">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
            <div class="password-strength-wrap" id="switch-strength-wrap">
              <div class="password-meter-track">
                <div class="password-meter-bar" id="switch-meter-bar"></div>
              </div>
              <div class="password-meter-text">
                <span>Strength: <strong id="switch-meter-label">-</strong></span>
                <span id="switch-match-badge" style="font-size:11px;"></span>
              </div>
            </div>
          </div>

          <div class="switch-enc-field">
            <label>Confirm ${isUpdatingPassword ? 'New ' : ''}Password <span style="color:var(--red);">*</span></label>
            <div class="switch-enc-input-wrap">
              <input type="password" id="switch-conf-pwd" placeholder="Re-enter password to confirm" autocomplete="new-password" />
              <button type="button" class="switch-enc-eye" id="switch-conf-pwd-eye" title="Toggle password visibility">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>

          <div class="security-notice-box caution">
            <div>
              If you lose this password, your encrypted account credentials cannot be recovered.
            </div>
          </div>
        </div>
      `;
    } else if (targetMethod === 'hardware') {
      html += `
        <div class="switch-enc-form-box">
          <div style="font-size:12px; font-weight:600; color:var(--fg);">
            ${currentMethod === 'password' ? 'Authorization Required' : 'Hardware Profile Details'}
          </div>

          ${currentMethod === 'password' ? `
            <div class="switch-enc-field">
              <label>Current Master Password <span style="color:var(--red);">*</span></label>
              <div class="switch-enc-input-wrap">
                <input type="password" id="switch-curr-pwd" placeholder="Enter current password to authorize switch" autocomplete="current-password" />
                <button type="button" class="switch-enc-eye" id="switch-curr-pwd-eye" title="Toggle password visibility">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>
            </div>
          ` : ''}

          <div class="security-notice-box info">
            <div>
              Accounts are bound to this machine. No password prompt is needed on this PC.
            </div>
          </div>
        </div>
      `;
    } else if (targetMethod === 'none') {
      html += `
        <div class="switch-enc-form-box">
          <div style="font-size:12px; font-weight:600; color:var(--fg);">
            ${currentMethod === 'password' ? 'Authorization & Confirmation' : 'Security Confirmation'}
          </div>

          ${currentMethod === 'password' ? `
            <div class="switch-enc-field">
              <label>Current Master Password <span style="color:var(--red);">*</span></label>
              <div class="switch-enc-input-wrap">
                <input type="password" id="switch-curr-pwd" placeholder="Enter current password to authorize decryption" autocomplete="current-password" />
                <button type="button" class="switch-enc-eye" id="switch-curr-pwd-eye" title="Toggle password visibility">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>
            </div>
          ` : ''}

          <div class="security-notice-box warning">
            <div>
              Accounts and session cookies will be stored unencrypted in plain text JSON on disk.
            </div>
          </div>
        </div>
      `;
    }

    formArea.innerHTML = html;

    if (currentMethod === 'password') {
      const currInp = document.getElementById('switch-curr-pwd') as HTMLInputElement | null;
      if (currInp && savedCurrentPassword) {
        currInp.value = savedCurrentPassword;
      }
      attachEyeToggle('switch-curr-pwd', 'switch-curr-pwd-eye');
    }

    if (targetMethod === 'password') {
      const newInp = document.getElementById('switch-new-pwd') as HTMLInputElement | null;
      const confInp = document.getElementById('switch-conf-pwd') as HTMLInputElement | null;
      if (newInp && savedNewPassword) newInp.value = savedNewPassword;
      if (confInp && savedConfPassword) confInp.value = savedConfPassword;

      attachEyeToggle('switch-new-pwd', 'switch-new-pwd-eye');
      attachEyeToggle('switch-conf-pwd', 'switch-conf-pwd-eye');

      const meterBar = document.getElementById('switch-meter-bar');
      const meterLabel = document.getElementById('switch-meter-label');
      const matchBadge = document.getElementById('switch-match-badge');

      const updateStrengthAndMatch = () => {
        const val = newInp?.value || '';
        const confVal = confInp?.value || '';

        const st = calculatePasswordStrength(val);
        if (meterBar) {
          meterBar.style.width = `${st.percent}%`;
          meterBar.style.backgroundColor = st.color;
        }
        if (meterLabel) {
          meterLabel.textContent = st.label || '-';
          meterLabel.style.color = st.color;
        }

        if (matchBadge) {
          if (!confVal) {
            matchBadge.textContent = '';
          } else if (val === confVal) {
            matchBadge.textContent = '✓ Passwords match';
            matchBadge.style.color = '#4ade80';
          } else {
            matchBadge.textContent = '✕ Passwords do not match';
            matchBadge.style.color = '#f87171';
          }
        }
      };

      newInp?.addEventListener('input', updateStrengthAndMatch);
      confInp?.addEventListener('input', updateStrengthAndMatch);
      updateStrengthAndMatch();
    }

    updateConfirmButton();
  };

  const updateConfirmButton = () => {
    if (!confirmBtn) return;
    if (targetMethod === currentMethod) {
      if (targetMethod === 'password') {
        confirmBtn.textContent = 'Update Master Password';
        confirmBtn.className = 'btn btn-primary';
        confirmBtn.disabled = false;
      } else if (targetMethod === 'hardware') {
        confirmBtn.textContent = 'Currently Active';
        confirmBtn.className = 'btn btn-secondary';
        confirmBtn.disabled = true;
      } else {
        confirmBtn.textContent = 'Currently Active';
        confirmBtn.className = 'btn btn-secondary';
        confirmBtn.disabled = true;
      }
    } else {
      if (targetMethod === 'password') {
        confirmBtn.textContent = 'Switch to Master Password';
        confirmBtn.className = 'btn btn-primary';
        confirmBtn.disabled = false;
      } else if (targetMethod === 'hardware') {
        confirmBtn.textContent = 'Switch to Hardware Profile';
        confirmBtn.className = 'btn btn-primary';
        confirmBtn.disabled = false;
      } else {
        confirmBtn.textContent = 'Disable Encryption';
        confirmBtn.className = 'btn btn-danger';
        confirmBtn.disabled = false;
      }
    }
  };

  const cards = document.querySelectorAll('#switch-enc-cards .switch-enc-card');
  cards.forEach(card => {
    card.addEventListener('click', () => {
      const method = card.getAttribute('data-method') as 'password' | 'hardware' | 'none';
      if (!method) return;
      targetMethod = method;
      cards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      renderDynamicForm();
    });
  });

  confirmBtn?.addEventListener('click', async () => {
    hideError();

    let currPwdVal = '';
    if (currentMethod === 'password') {
      const currInput = document.getElementById('switch-curr-pwd') as HTMLInputElement | null;
      currPwdVal = (currInput?.value || '').trim();
      if (!currPwdVal) {
        showError('Please enter your current master password to authorize this change.');
        currInput?.focus();
        return;
      }
    }

    let newPwdVal = '';
    if (targetMethod === 'password') {
      const newInp = document.getElementById('switch-new-pwd') as HTMLInputElement | null;
      const confInp = document.getElementById('switch-conf-pwd') as HTMLInputElement | null;
      newPwdVal = (newInp?.value || '').trim();
      const confVal = (confInp?.value || '').trim();

      if (newPwdVal.length < 8) {
        showError('New master password must be at least 8 characters long.');
        newInp?.focus();
        return;
      }
      if (newPwdVal !== confVal) {
        showError('Passwords do not match. Please verify your new password.');
        confInp?.focus();
        return;
      }
    }

    if (targetMethod === currentMethod && targetMethod !== 'password') {
      closeModal();
      return;
    }

    const origText = confirmBtn.textContent || '';
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Migrating encryption...';

    try {
      const res = await apiService.switchEncryption({
        method: targetMethod,
        current_password: currPwdVal,
        new_password: newPwdVal,
      });

      if (!res || !res.success) {
        showError(res?.error || 'Failed to switch encryption method.');
        confirmBtn.disabled = false;
        confirmBtn.textContent = origText;
        return;
      }

      state.settings.encryptionEnabled = res.encryptionEnabled;
      state.settings.encryptionMethod = res.encryptionMethod as any;
      if (res.settings) {
        state.settings = { ...state.settings, ...res.settings };
      }

      const methodNames: Record<string, string> = {
        password: 'Master Password',
        hardware: 'Hardware Profile',
        none: 'No Encryption',
      };
      const chosenLabel = methodNames[targetMethod] || targetMethod;
      toast(`Encryption method switched to ${chosenLabel} successfully!`, 'success');

      closeModal();
      renderSettingsView();
    } catch (err: any) {
      showError(err.message || 'An unexpected error occurred while switching encryption.');
      confirmBtn.disabled = false;
      confirmBtn.textContent = origText;
    }
  });

  renderDynamicForm();
}

function renderSettingsView(): void {
  const query = (state.settingsSearch || '').trim().toLowerCase();

  // tabs
  const tabsWrap = document.getElementById('settings-tabs');
  if (tabsWrap) {
    tabsWrap.innerHTML = "";
    SETTINGS_TABS.forEach(t => {
      if (t.dividerBefore) {
        const div = el('div', { class: 'settings-nav-divider' }, []);
        tabsWrap.appendChild(div);
      }
      const tabGroup = el('div', { class: 'settings-tab-group' }, []);
      const isActive = state.settingsTab === t.id || (state.settingsTab === 'custom-theme' && t.id === 'appearance');
      const btn = el('button', {
        class: 'settings-tab-btn' + (isActive ? ' active' : ''),
      }, [
        el('span', { class: 'tab-btn-icon', html: t.icon.startsWith('<svg') ? t.icon : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + t.icon + '</svg>' }, []),
        el('span', { class: 'tab-btn-label' }, [document.createTextNode(t.label)])
      ]);

      const matchesForTab = query
        ? getVisibleSettingsItems().filter(item => item.tab === t.id && (item.label.toLowerCase().includes(query) || item.desc.toLowerCase().includes(query)))
        : [];

      if (query && matchesForTab.length > 0) {
        const badge = el('span', { class: 'tab-match-badge' }, [document.createTextNode(matchesForTab.length.toString())]);
        btn.appendChild(badge);
      }

      btn.addEventListener('click', () => {
        state.settingsTab = t.id as any;
        renderSettingsView();
      });
      tabGroup.appendChild(btn);

      if (query && matchesForTab.length > 0) {
        const subItemsWrap = el('div', { class: 'settings-tab-subitems' }, []);
        matchesForTab.forEach(match => {
          const itemBtn = el('button', {
            class: 'settings-subitem-btn',
            title: match.desc
          }, [
            el('svg', {
              viewBox: '0 0 24 24',
              fill: 'none',
              stroke: 'currentColor',
              'stroke-width': '2',
              'stroke-linecap': 'round',
              'stroke-linejoin': 'round'
            }, [
              el('polyline', { points: '9 18 15 12 9 6' }, [])
            ]),
            el('span', { class: 'subitem-title' }, [document.createTextNode(match.label)])
          ]);

          itemBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            jumpToSetting(match.tab, match.label);
          });
          subItemsWrap.appendChild(itemBtn);
        });
        tabGroup.appendChild(subItemsWrap);
      }

      tabsWrap.appendChild(tabGroup);
    });
  }

  // content
  const inner = document.getElementById('settings-content-inner');
  if (!inner) return;

  const settingsScrollParent = document.querySelector('.settings-content') || inner.parentElement;
  const savedScrollTop = settingsScrollParent ? settingsScrollParent.scrollTop : 0;

  inner.innerHTML = "";

  if (state.settingsTab === 'general') {
    inner.appendChild(el('h2', {}, [document.createTextNode('General')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Settings that control the behavior and configuration of the FRAM application itself.')]));

    const appSec = el('div', { class: 'settings-section' }, []);
    appSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Application')]));
    const appCard = el('div', { class: 'settings-card' }, []);
    appCard.appendChild(settingsToggleRow('Always on Top', 'Keep FRAM above other desktop windows', 'enableTopmost'));
    appCard.appendChild(settingsToggleRow('Start FRAM on Windows Startup', 'Automatically launch FRAM when Windows starts', 'startAtStartup'));
    appCard.appendChild(settingsToggleRow('Minimize to System Tray', 'Keep FRAM running in the system tray when minimized or closed', 'minimizeToTray'));
    appSec.appendChild(appCard);
    inner.appendChild(appSec);

    const startupSec = el('div', { class: 'settings-section' }, []);
    startupSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Startup')]));
    const startupCard = el('div', { class: 'settings-card' }, []);

    const startupViewRow = el('div', { class: 'setting-row' }, []);
    const startupViewText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Default Startup Landing View')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Choose which main tab opens when FRAM launches')])
    ]);
    startupViewRow.appendChild(startupViewText);
    const startupViewSel = el('select', { style: 'min-width:180px;' }, []) as HTMLSelectElement;
    [
      { value: 'accounts', label: 'Accounts' },
      { value: 'instances', label: 'Instances' },
      { value: 'vip', label: 'VIP Servers' },
      { value: 'settings', label: 'Settings' }
    ].forEach(opt => {
      const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
      o.textContent = opt.label;
      if (opt.value === (state.settings.defaultStartupView || 'accounts')) o.selected = true;
      startupViewSel.appendChild(o);
    });
    startupViewSel.addEventListener('change', (e) => updateSetting('defaultStartupView', (e.target as HTMLSelectElement).value as any));
    startupViewRow.appendChild(startupViewSel);
    startupCard.appendChild(startupViewRow);

    const validateRow = settingsToggleRow('Validate Cookies on Startup', 'Validate stored account sessions when FRAM launches', 'autoValidateOnLaunch');
    validateRow.style.borderBottom = 'none';
    startupCard.appendChild(validateRow);

    startupSec.appendChild(startupCard);
    inner.appendChild(startupSec);

    const accountsViewSec = el('div', { class: 'settings-section' }, []);
    accountsViewSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Accounts View')]));
    const accountsViewCard = el('div', { class: 'settings-card' }, []);

    accountsViewCard.appendChild(settingsToggleRow(state.settings.multiSelect ? `Multi Select (${getMultiSelectBindText()})` : 'Multi Select', 'Enable selecting multiple accounts for bulk actions', 'multiSelect'));

    const sortRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const sortText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Account List Default Sorting')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Sort accounts automatically by creation order, status, or username')])
    ]);
    sortRow.appendChild(sortText);
    const sortSel = el('select', {}, []) as HTMLSelectElement;
    [
      { value: 'none', label: 'Creation Order' },
      { value: 'status', label: 'Status' },
      { value: 'username', label: 'Username A–Z' }
    ].forEach(opt => {
      const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
      o.textContent = opt.label;
      if (opt.value === (state.settings.autoSortAccounts || 'none')) o.selected = true;
      sortSel.appendChild(o);
    });
    sortSel.addEventListener('change', (e) => updateSetting('autoSortAccounts', (e.target as HTMLSelectElement).value as any));
    sortRow.appendChild(sortSel);
    accountsViewCard.appendChild(sortRow);

    accountsViewSec.appendChild(accountsViewCard);
    inner.appendChild(accountsViewSec);

    const updateSec = el('div', { class: 'settings-section' }, []);
    updateSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Updates')]));
    const updateCard = el('div', { class: 'settings-card' }, []);

    updateCard.appendChild(settingsToggleRow('Automatic Update Checks', 'Check for new FRAM versions on launch', 'autoUpdateCheck'));

    const checkUpdateRow = el('div', { class: 'setting-row' }, [
      el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Check for Updates Now')]),
        el('div', { class: 'setting-desc', id: 'updater-check-status-desc' }, [
          document.createTextNode('Check GitHub releases for the latest version of FRAM')
        ])
      ]),
      el('button', {
        class: 'btn btn-secondary btn-sm',
        id: 'btn-check-updates-now',
        type: 'button',
        style: 'font-size:11.5px; padding:5px 12px;',
        onclick: async () => {
          const btn = document.getElementById('btn-check-updates-now') as HTMLButtonElement | null;
          const statusDesc = document.getElementById('updater-check-status-desc');
          if (btn) {
            btn.disabled = true;
            btn.textContent = 'Checking...';
          }
          if (statusDesc) {
            statusDesc.textContent = 'Querying GitHub releases...';
          }
          try {
            const res = await apiService.checkForUpdates(true);
            if (res.update_available) {
              if (statusDesc) statusDesc.textContent = `New version available: v${res.latest_version}`;
              showUpdateModal(res);
            } else {
              if (statusDesc) statusDesc.textContent = `You are running the latest version (v${res.current_version}).`;
              toast('FRAM is up to date', 'info');
            }
          } catch (err: any) {
            if (statusDesc) statusDesc.textContent = 'Failed to check for updates.';
            toast('Failed to check for updates: ' + (err?.message || err), 'error');
          } finally {
            if (btn) {
              btn.disabled = false;
              btn.textContent = 'Check for Updates Now';
            }
          }
        }
      }, [document.createTextNode('Check for Updates Now')])
    ]);
    updateCard.appendChild(checkUpdateRow);

    const onboardingRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const onboardingText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Rerun Setup Wizard')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Reopen the initial setup/onboarding wizard')])
    ]);
    onboardingRow.appendChild(onboardingText);

    const rerunBtn = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Rerun Setup Wizard')]);
    rerunBtn.addEventListener('click', () => {
      isSetupRerun = true;
      setupStep = 0;
      setupData = {
        importMode: 'fresh',
        importPath: '',
        importPreview: null,
        importStatus: '',
        importedSummary: null,
        preferredBrowser: state.settings.preferredBrowser || 'auto',
        multiInstance: state.settings.multiInstance || false,
        multiLaunchDelay: state.settings.multiLaunchDelay || 1000,
        autoKillRobloxOnExit: state.settings.autoKillRobloxOnExit || false,
        autoMemoryTrimEnabled: state.settings.autoMemoryTrimEnabled || false,
        autoCloseCrashHandlers: state.settings.autoCloseCrashHandlers || false,
        headlessMode: state.settings.headlessMode || false,
        autoValidateOnLaunch: state.settings.autoValidateOnLaunch !== false,
        selectedTheme: state.settings.selectedTheme || 'default-dark',
        accentColor: state.settings.accentColor || '',
        encryptionEnabled: Boolean(state.settings.encryptionEnabled),
        encryptionMethod: state.settings.encryptionEnabled ? (state.settings.encryptionMethod || 'password') : 'none',
        encryptionPassword: '',
        confirmPassword: ''
      };
      showSetup = true;
      renderSetup();
    });
    onboardingRow.appendChild(rerunBtn);
    updateCard.appendChild(onboardingRow);

    updateSec.appendChild(updateCard);
    inner.appendChild(updateSec);
  }

  if (state.settingsTab === 'roblox') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Roblox')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Configure Roblox installation paths, client settings, FastFlags, and thumbnail caching.')]));

    renderRobloxHubSection(inner);
    renderRobloxSwapSection(inner);

    const installSec = el('div', { class: 'settings-section' }, []);
    installSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Installation')]));
    const installCard = el('div', { class: 'settings-card' }, []);

    const pathRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const pathText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Roblox Installation Path')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Path to RobloxPlayerBeta.exe (leave blank to automatically detect installation)')])
    ]);
    pathRow.appendChild(pathText);
    const pathInput = el('input', {
      type: 'text',
      placeholder: 'C:\\Users\\...\\RobloxPlayerBeta.exe',
      style: 'min-width:240px;'
    }, []) as HTMLInputElement;
    pathInput.value = state.settings.robloxPath || '';
    pathInput.addEventListener('change', (e) => updateSetting('robloxPath', (e.target as HTMLInputElement).value));
    pathRow.appendChild(pathInput);
    installCard.appendChild(pathRow);
    installSec.appendChild(installCard);
    inner.appendChild(installSec);

    const clientSettingsSec = el('div', { class: 'settings-section' }, []);
    clientSettingsSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Roblox Client Settings')]));
    const clientSettingsCard = el('div', { class: 'settings-card' }, []);

    const openGlobalRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    openGlobalRow.dataset.settingId = 'setting-roblox-global-client';
    const openGlobalText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Roblox Client Settings')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Configure Graphics Quality, Frame Rate / FPS Cap, Volume, Controls, Camera, and Accessibility.')])
    ]);
    openGlobalRow.appendChild(openGlobalText);
    const openGlobalBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [
      document.createTextNode('Open Settings')
    ]);
    openGlobalBtn.addEventListener('click', () => {
      state.revealed = {};
      state.previousView = state.view;
      state.view = 'clientsettings';
      renderAll();
    });
    openGlobalRow.appendChild(openGlobalBtn);
    clientSettingsCard.appendChild(openGlobalRow);
    clientSettingsSec.appendChild(clientSettingsCard);
    inner.appendChild(clientSettingsSec);

    const fastflagsSec = el('div', { class: 'settings-section' }, []);
    fastflagsSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Roblox FastFlags')]));
    const fastflagsCard = el('div', { class: 'settings-card' }, []);

    const fastflagsRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    fastflagsRow.dataset.settingId = 'setting-roblox-fastflags';
    const fastflagsText = el('div', {}, [
      el('div', { class: 'setting-label' }, [
        document.createTextNode('Roblox FastFlags Editor')
      ]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Add, edit, or remove custom FastFlags to fine-tune graphics and engine performance.')])
    ]);
    fastflagsRow.appendChild(fastflagsText);
    const fastflagsBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [
      document.createTextNode('Open Editor')
    ]);
    fastflagsBtn.addEventListener('click', () => {
      state.revealed = {};
      state.previousView = state.view;
      state.view = 'fastflags';
      renderAll();
    });
    fastflagsRow.appendChild(fastflagsBtn);
    fastflagsCard.appendChild(fastflagsRow);
    fastflagsSec.appendChild(fastflagsCard);
    inner.appendChild(fastflagsSec);

    const cacheSec = el('div', { class: 'settings-section' }, []);
    cacheSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Cache')]));
    const cacheCard = el('div', { class: 'settings-card' }, []);

    const iconCacheRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const iconCacheText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Roblox Icon & Thumbnail Cache')]),
      el('div', { class: 'setting-desc', id: 'icon-cache-stats-desc' }, [document.createTextNode('Calculating cached icon disk usage...')])
    ]);
    iconCacheRow.appendChild(iconCacheText);

    const iconCacheBtns = el('div', { class: 'btn-row' }, []);
    const refreshStatsBtn = el('button', { class: 'btn btn-secondary', title: 'Refresh icon cache statistics' }, [document.createTextNode('Refresh')]);
    const clearCacheBtn = el('button', { class: 'btn btn-secondary', style: 'color: var(--yellow);' }, [document.createTextNode('Clear Icon Cache')]) as HTMLButtonElement;

    const updateCacheDisplay = async () => {
      try {
        const res = await apiService.getIconCacheStats();
        const descEl = document.getElementById('icon-cache-stats-desc');
        if (res && res.success && res.stats && descEl) {
          const s = res.stats as any;
          const mb = s.disk_size_mb !== undefined ? `${s.disk_size_mb} MB` : '0 MB';
          const files = s.saved_image_files || 0;
          const avatars = s.avatar_icons || 0;
          const places = s.place_icons || 0;
          descEl.textContent = `Using ${mb} across ${files} downloaded files (${avatars} avatar headshots, ${places} place icons).`;
        }
      } catch (_) {
        const descEl = document.getElementById('icon-cache-stats-desc');
        if (descEl) descEl.textContent = 'Unable to query icon cache stats.';
      }
    };

    refreshStatsBtn.addEventListener('click', () => {
      updateCacheDisplay();
      toast('Icon cache statistics refreshed');
    });

    clearCacheBtn.addEventListener('click', async () => {
      const confirmed = await showConfirmModal('Clear Icon Cache', 'Are you sure you want to clear the icon and thumbnail cache? Thumbnails will be re-downloaded on demand.', 'Clear Cache');
      if (!confirmed) {
        return;
      }
      try {
        clearCacheBtn.disabled = true;
        const res = await apiService.clearIconCache();
        if (res && res.success) {
          toast('Icon cache cleared');
          await updateCacheDisplay();
        } else {
          toast('Failed to clear icon cache', 'error');
        }
      } catch (err: any) {
        toast('Error clearing icon cache: ' + err, 'error');
      } finally {
        clearCacheBtn.disabled = false;
      }
    });

    iconCacheBtns.appendChild(refreshStatsBtn);
    iconCacheBtns.appendChild(clearCacheBtn);
    iconCacheRow.appendChild(iconCacheBtns);
    cacheCard.appendChild(iconCacheRow);
    setTimeout(updateCacheDisplay, 50);

    cacheSec.appendChild(cacheCard);
    inner.appendChild(cacheSec);

    const robloxUpdatesSec = el('div', { class: 'settings-section' }, []);
    robloxUpdatesSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Roblox Updates & Installer')]));
    const robloxUpdatesCard = el('div', { class: 'settings-card' }, []);
    const autoCheckRow = settingsToggleRow('Auto-check for Roblox Updates', 'Check whether a newer Roblox client version is available on launch', 'autoCheckRobloxUpdates');
    const disablePresetsRow = settingsToggleRow('Disable Executor Presets', 'Hide executor presets and live status icons in the Roblox Installer modal', 'disableExecutorPresets');
    disablePresetsRow.style.borderBottom = 'none';
    robloxUpdatesCard.appendChild(autoCheckRow);
    robloxUpdatesCard.appendChild(disablePresetsRow);
    robloxUpdatesSec.appendChild(robloxUpdatesCard);
    inner.appendChild(robloxUpdatesSec);
  }

  if (state.settingsTab === 'launching') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Launching')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Settings that determine how FRAM starts and manages Roblox instances during launch.')]));

    const multiSec = el('div', { class: 'settings-section' }, []);
    multiSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Multiple Instances')]));
    const multiCard = el('div', { class: 'settings-card' }, []);

    multiCard.appendChild(settingsToggleRow('Multi-Instance Roblox', 'Allow multiple Roblox accounts to run simultaneously without instance mutex conflicts', 'multiInstance'));

    const delayRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const delayText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Multi-Account Launch Stagger Delay')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Delay between launching consecutive accounts in milliseconds (1000 ms = 1 sec)')])
    ]);
    delayRow.appendChild(delayText);
    const delayInput = el('input', {
      type: 'number',
      min: '0',
      max: '60000',
      step: '100',
      value: String(state.settings.multiLaunchDelay || 1000),
      style: 'width:100px; text-align:right;'
    }, []) as HTMLInputElement;
    delayInput.addEventListener('change', (e) => {
      const val = Math.max(0, Number((e.target as HTMLInputElement).value) || 1000);
      updateSetting('multiLaunchDelay', val);
    });
    delayRow.appendChild(delayInput);
    multiCard.appendChild(delayRow);
    multiSec.appendChild(multiCard);
    inner.appendChild(multiSec);

    const launchSetupSec = el('div', { class: 'settings-section' }, []);
    launchSetupSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Launch Setup')]));
    const launchSetupCard = el('div', { class: 'settings-card' }, []);
    launchSetupCard.appendChild(settingsToggleRow('Confirm Before Account Launch', 'Show a confirmation dialog before launching accounts', 'confirmBeforeLaunch'));
    launchSetupCard.appendChild(settingsToggleRow('Auto Close RobloxCrashHandlers', 'Automatically detect and terminate unresponsive RobloxCrashHandler processes', 'autoCloseCrashHandlers'));
    const saveDetailsRow = settingsToggleRow('Save Launch Details', 'Automatically save game place IDs and user targets to the Saved Games bar when launching', 'autoSaveLaunchDetails');
    saveDetailsRow.style.borderBottom = 'none';
    launchSetupCard.appendChild(saveDetailsRow);
    launchSetupSec.appendChild(launchSetupCard);
    inner.appendChild(launchSetupSec);

    const serverSec = el('div', { class: 'settings-section' }, []);
    serverSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Server Selection')]));
    const serverCard = el('div', { class: 'settings-card' }, []);

    const regionRow = el('div', { class: 'setting-row' }, []);
    const regionText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Preferred Server Region')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Automatically select a preferred geographic region when joining public servers')])
    ]);
    regionRow.appendChild(regionText);
    const regionSel = el('select', { style: 'min-width:180px;' }, []) as HTMLSelectElement;
    const regionOptions = [
      { value: '', label: 'Any (Default)' },
      { value: 'united states', label: 'United States' },
      { value: 'us east', label: 'US East' },
      { value: 'us central', label: 'US Central' },
      { value: 'us west', label: 'US West' },
      { value: 'canada', label: 'Canada' },
      { value: 'brazil', label: 'Brazil' },
      { value: 'europe', label: 'Europe' },
      { value: 'united kingdom', label: 'United Kingdom' },
      { value: 'germany', label: 'Germany' },
      { value: 'france', label: 'France' },
      { value: 'netherlands', label: 'Netherlands' },
      { value: 'singapore', label: 'Singapore' },
      { value: 'japan', label: 'Japan' },
      { value: 'hong kong', label: 'Hong Kong' },
      { value: 'south korea', label: 'South Korea' },
      { value: 'india', label: 'India' },
      { value: 'australia', label: 'Australia' }
    ];
    regionOptions.forEach(choice => {
      const o = el('option', { value: choice.value }, []) as HTMLOptionElement;
      o.textContent = choice.label;
      if (choice.value === (state.settings.preferredRegion || '')) o.selected = true;
      regionSel.appendChild(o);
    });
    regionSel.addEventListener('change', (e) => updateSetting('preferredRegion', (e.target as HTMLSelectElement).value));
    regionRow.appendChild(regionSel);
    serverCard.appendChild(regionRow);

    const serverPerAccountRow = settingsToggleRow('Server For Each Account', 'Assign a different public server to each account during batch launching', 'serverPerAccount');
    serverPerAccountRow.style.borderBottom = 'none';
    serverCard.appendChild(serverPerAccountRow);

    serverSec.appendChild(serverCard);
    inner.appendChild(serverSec);

    const cleanupSec = el('div', { class: 'settings-section' }, []);
    cleanupSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Launch Cleanup')]));
    const cleanupCard = el('div', { class: 'settings-card' }, []);
    const killRow = settingsToggleRow('Auto-Close Roblox Clients on FRAM Exit', 'Automatically terminate Roblox clients when FRAM closes', 'autoKillRobloxOnExit');
    killRow.style.borderBottom = 'none';
    cleanupCard.appendChild(killRow);
    cleanupSec.appendChild(cleanupCard);
    inner.appendChild(cleanupSec);

    const headlessSec = el('div', { class: 'settings-section' }, []);
    headlessSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Headless Mode')]));
    const headlessCard = el('div', { class: 'settings-card' }, []);

    const enableHeadlessRow = settingsToggleRow('Headless Client Launch', 'Launch Roblox instances hidden in the background to save GPU and CPU resources', 'headlessMode');
    if (!state.settings.headlessMode) {
      enableHeadlessRow.style.borderBottom = 'none';
    }
    headlessCard.appendChild(enableHeadlessRow);

    if (state.settings.headlessMode) {
      headlessCard.appendChild(settingsToggleRow('Idle CPU Priority', 'Lower background Roblox client CPU priority to Idle', 'headlessIdlePriority'));
      headlessCard.appendChild(settingsToggleRow('Headless Auto Memory Trim', 'Automatically optimize memory usage for background instances', 'headlessTrimMemory'));

      const headlessActionsRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
      const headlessActionsText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Headless Actions')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Hide or restore running Roblox client windows immediately')])
      ]);
      const headlessActionsBtnWrap = el('div', { style: 'display:flex; gap:8px; align-items:center;' }, []);

      const btnApplyHeadless = el('button', { class: 'btn btn-secondary btn-sm', style: 'font-size:11.5px; padding:5px 10px;' }, [document.createTextNode('Hide All Clients')]);
      btnApplyHeadless.addEventListener('click', async () => {
        try {
          btnApplyHeadless.setAttribute('disabled', 'true');
          const res = await apiService.applyHeadlessNow();
          if (res.success) {
            toast('Headless mode applied: clients hidden');
          } else {
            toast(res.error || 'Failed to apply headless mode', 'error');
          }
        } catch (err: any) {
          toast(`Error: ${err.message || err}`, 'error');
        } finally {
          btnApplyHeadless.removeAttribute('disabled');
        }
      });

      const btnRestoreHeadless = el('button', { class: 'btn btn-secondary btn-sm', style: 'font-size:11.5px; padding:5px 10px;' }, [document.createTextNode('Restore All Clients')]);
      btnRestoreHeadless.addEventListener('click', async () => {
        try {
          btnRestoreHeadless.setAttribute('disabled', 'true');
          const res = await apiService.restoreHeadlessWindows();
          if (res.success) {
            toast('Roblox client windows restored');
          } else {
            toast(res.error || 'Failed to restore Roblox windows', 'error');
          }
        } catch (err: any) {
          toast(`Error: ${err.message || err}`, 'error');
        } finally {
          btnRestoreHeadless.removeAttribute('disabled');
        }
      });

      headlessActionsBtnWrap.appendChild(btnApplyHeadless);
      headlessActionsBtnWrap.appendChild(btnRestoreHeadless);
      headlessActionsRow.appendChild(headlessActionsText);
      headlessActionsRow.appendChild(headlessActionsBtnWrap);
      headlessCard.appendChild(headlessActionsRow);
    }

    headlessSec.appendChild(headlessCard);
    inner.appendChild(headlessSec);
  }

  if (state.settingsTab === 'automation') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Automation')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Configure automated Roblox window arrangement, Anti-AFK, auto-rejoin, scheduled relaunches, and memory optimization.')]));

    const arrangeSec = el('div', { class: 'settings-section' }, []);
    arrangeSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Roblox Window Automation')]));
    const arrangeCard = el('div', { class: 'settings-card' }, []);

    const keepArrangedRow = settingsToggleRow('Auto Arrange Roblox', 'Automatically arrange and maintain Roblox client positions', 'keepClientsArranged');
    if (!state.settings.keepClientsArranged) {
      keepArrangedRow.style.borderBottom = 'none';
    }
    arrangeCard.appendChild(keepArrangedRow);

    if (state.settings.keepClientsArranged) {
      const scopeRow = el('div', { class: 'setting-row' }, []);
      const scopeText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Auto-Arrange Monitor Scope')]),
        el('div', { class: 'setting-desc', id: 'auto-arrange-monitor-desc' }, [document.createTextNode('All Monitors, Primary Monitor, or Secondary Monitor')])
      ]);
      scopeRow.appendChild(scopeText);
      const scopeSel = el('select', { style: 'min-width:210px;' }, []) as HTMLSelectElement;

      const populateMonitors = async () => {
        const currentScope = String(state.settings.autoArrangeScope || 'both');
        scopeSel.innerHTML = '';
        const baseOpts: Array<{ value: string; label: string }> = [
          { value: 'both', label: 'All Monitors' },
          { value: 'primary', label: 'Primary Monitor' },
          { value: 'secondary', label: 'Secondary Monitor' }
        ];
        try {
          const monRes = await apiService.getAutoArrangeMonitors();
          if (monRes && monRes.success && Array.isArray(monRes.monitors) && monRes.monitors.length > 0) {
            const descEl = document.getElementById('auto-arrange-monitor-desc');
            if (descEl) {
              descEl.textContent = `Detected ${monRes.monitors.length} display monitor(s). Select target monitor or span all screens.`;
            }
            baseOpts.length = 0;
            baseOpts.push({ value: 'both', label: `All Monitors (${monRes.monitors.length} Displays)` });
            monRes.monitors.forEach(m => {
              const role = m.is_primary ? 'Primary' : `Display ${m.id}`;
              baseOpts.push({
                value: `monitor_${m.id}`,
                label: `Monitor ${m.id}: ${m.width}×${m.height} (${role})`
              });
            });
          }
        } catch (_) { }

        baseOpts.forEach(opt => {
          const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
          o.textContent = opt.label;
          if (opt.value === currentScope) o.selected = true;
          scopeSel.appendChild(o);
        });
        if (!scopeSel.value && baseOpts.length > 0) {
          scopeSel.value = baseOpts[0].value;
        }
      };
      populateMonitors();

      scopeSel.addEventListener('change', (e) => updateSetting('autoArrangeScope', (e.target as HTMLSelectElement).value as any));
      scopeRow.appendChild(scopeSel);
      arrangeCard.appendChild(scopeRow);

      const dimModeRow = el('div', { class: 'setting-row' }, []);
      const dimModeText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Auto-Arrange Tile Sizing Mode')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Adaptive screen grid fitting or fixed target resolution')])
      ]);
      dimModeRow.appendChild(dimModeText);
      const dimModeSel = el('select', { style: 'min-width:180px;' }, []) as HTMLSelectElement;
      [
        { value: 'auto', label: 'Adaptive Grid' },
        { value: 'target_size', label: 'Fixed Target Resolution' }
      ].forEach(opt => {
        const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
        o.textContent = opt.label;
        if (opt.value === (state.settings.autoArrangeDimensionMode || 'auto')) o.selected = true;
        dimModeSel.appendChild(o);
      });
      dimModeSel.addEventListener('change', (e) => {
        const val = (e.target as HTMLSelectElement).value as any;
        updateSetting('autoArrangeDimensionMode', val);
        renderSettingsView();
      });
      if (state.settings.autoArrangeDimensionMode !== 'target_size') {
        dimModeRow.style.borderBottom = 'none';
      }
      dimModeRow.appendChild(dimModeSel);
      arrangeCard.appendChild(dimModeRow);

      if (state.settings.autoArrangeDimensionMode === 'target_size') {
        const dimInputsRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
        const dimInputsText = el('div', {}, [
          el('div', { class: 'setting-label' }, [document.createTextNode('Target Client Resolution')]),
          el('div', { class: 'setting-desc' }, [document.createTextNode('Target client width and height in pixels used when Fixed Target Resolution is selected')])
        ]);
        dimInputsRow.appendChild(dimInputsText);
        const inputsWrap = el('div', { style: 'display:flex; align-items:center; gap:8px;' }, []);

        const widthInput = el('input', {
          type: 'number',
          min: '50',
          max: '7680',
          step: '10',
          value: String(state.settings.autoArrangeTargetWidth || 800),
          style: 'width:80px; text-align:right;',
          title: 'Target Client Width'
        }, []) as HTMLInputElement;
        widthInput.addEventListener('change', (e) => updateSetting('autoArrangeTargetWidth', Number((e.target as HTMLInputElement).value) || 800));

        const xSpan = el('span', { style: 'color:var(--text-muted); font-weight:600;' }, [document.createTextNode('×')]);

        const heightInput = el('input', {
          type: 'number',
          min: '50',
          max: '4320',
          step: '10',
          value: String(state.settings.autoArrangeTargetHeight || 600),
          style: 'width:80px; text-align:right;',
          title: 'Target Client Height'
        }, []) as HTMLInputElement;
        heightInput.addEventListener('change', (e) => updateSetting('autoArrangeTargetHeight', Number((e.target as HTMLInputElement).value) || 600));

        inputsWrap.appendChild(widthInput);
        inputsWrap.appendChild(xSpan);
        inputsWrap.appendChild(heightInput);
        dimInputsRow.appendChild(inputsWrap);
        arrangeCard.appendChild(dimInputsRow);
      }
    }

    arrangeSec.appendChild(arrangeCard);
    inner.appendChild(arrangeSec);

    const antiAfkSec = el('div', { class: 'settings-section' }, []);
    antiAfkSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Anti-AFK')]));
    const antiAfkCard = el('div', { class: 'settings-card' }, []);

    const enableAntiAfkRow = settingsToggleRow('Enable Anti-AFK', 'Prevent Roblox from disconnecting due to inactivity', 'antiAfkEnabled');
    if (!state.settings.antiAfkEnabled) {
      enableAntiAfkRow.style.borderBottom = 'none';
    }
    antiAfkCard.appendChild(enableAntiAfkRow);

    if (state.settings.antiAfkEnabled) {
      const intervalRow = el('div', { class: 'setting-row' }, []);
      const intervalText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Anti-AFK Interval')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Time in minutes between simulated input pulses (1-19 min)')])
      ]);
      intervalRow.appendChild(intervalText);
      const intervalInput = el('input', { type: 'number', min: '1', max: '19', value: String(state.settings.antiAfkIntervalMinutes || 10), style: 'width:80px; text-align:right;' }, []) as HTMLInputElement;
      intervalInput.addEventListener('change', async (e) => {
        const val = Math.max(1, Math.min(19, Number((e.target as HTMLInputElement).value) || 10));
        await updateSetting('antiAfkIntervalMinutes', val);
        await apiService.updateAntiAfkSettings({ antiAfkIntervalMinutes: val });
      });
      intervalRow.appendChild(intervalInput);
      antiAfkCard.appendChild(intervalRow);

      const keyRow = el('div', { class: 'setting-row' }, []);
      const keyText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Simulated Input Key')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Simulated input event sent in the background without stealing focus')])
      ]);
      keyRow.appendChild(keyText);
      const keySel = el('select', { style: 'min-width:180px;' }, []) as HTMLSelectElement;
      [
        { value: 'M1', label: 'Left Click / M1' },
        { value: 'M2', label: 'Right Click / M2' },
        { value: 'M3', label: 'Middle Click / M3' },
        { value: 'Space', label: 'Spacebar' },
        { value: 'W', label: 'W' },
        { value: 'A', label: 'A' },
        { value: 'S', label: 'S' },
        { value: 'D', label: 'D' },
        { value: 'Arrow Keys', label: 'Arrow Keys' },
        { value: 'F15', label: 'F15' }
      ].forEach(opt => {
        const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
        o.textContent = opt.label;
        if (opt.value === (state.settings.antiAfkKeyName || 'M1')) o.selected = true;
        keySel.appendChild(o);
      });
      keySel.addEventListener('change', async (e) => {
        const val = (e.target as HTMLSelectElement).value;
        await updateSetting('antiAfkKeyName', val);
        await apiService.updateAntiAfkSettings({ antiAfkKeyName: val });
      });
      keyRow.appendChild(keySel);
      antiAfkCard.appendChild(keyRow);

      const durationRow = el('div', { class: 'setting-row' }, []);
      const durationText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Input Hold Duration')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Duration in seconds the simulated key or mouse click is held (0.1 - 5.0s)')])
      ]);
      durationRow.appendChild(durationText);
      const durationInput = el('input', { type: 'number', min: '0.1', max: '5.0', step: '0.1', value: String(state.settings.antiAfkDuration ?? 1.0), style: 'width:80px; text-align:right;' }, []) as HTMLInputElement;
      durationInput.addEventListener('change', async (e) => {
        const val = Math.max(0.05, Math.min(10.0, Number((e.target as HTMLInputElement).value) || 1.0));
        await updateSetting('antiAfkDuration', val);
        await apiService.updateAntiAfkSettings({ antiAfkDuration: val });
      });
      durationRow.appendChild(durationInput);
      antiAfkCard.appendChild(durationRow);

      const overlayRow = el('div', { class: 'setting-row' }, []);
      const overlayTextWrap = el('div', {}, []);
      overlayTextWrap.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode('Show Timer on Roblox Window')]));
      overlayTextWrap.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode('Display a live countdown overlay on the top-right of each Roblox client')]));
      overlayRow.appendChild(overlayTextWrap);
      const overlaySw = el('button', {
        class: 'switch' + (state.settings.antiAfkShowNextLabel ? ' on' : ''),
        type: 'button'
      }, [el('span', { class: 'knob' }, [])]) as HTMLButtonElement;
      overlaySw.addEventListener('click', async () => {
        const nextVal = !state.settings.antiAfkShowNextLabel;
        overlaySw.className = 'switch' + (nextVal ? ' on' : '');
        await updateSetting('antiAfkShowNextLabel', nextVal);
        await apiService.updateAntiAfkSettings({ antiAfkShowNextLabel: nextVal });
      });
      overlayRow.appendChild(overlaySw);
      antiAfkCard.appendChild(overlayRow);

      let initialAntiAfkText = 'Checking...';
      let initialAntiAfkColor = 'var(--fg)';
      let initialAntiAfkDesc = 'Connecting to Anti-AFK engine...';

      if (lastAntiAfkStatus && lastAntiAfkStatus.success) {
        const count = lastAntiAfkStatus.roblox_instance_count || 0;
        const remaining = Number(lastAntiAfkStatus.seconds_until_next_run || 0);
        const m = Math.floor(remaining / 60);
        const sec = remaining % 60;
        const timeStr = `${m}m ${sec}s`;
        if (lastAntiAfkStatus.in_progress) {
          initialAntiAfkText = 'Sending pulse...';
          initialAntiAfkColor = 'var(--yellow)';
        } else if (lastAntiAfkStatus.enabled) {
          initialAntiAfkText = `Next pulse in ${timeStr}`;
          initialAntiAfkColor = 'var(--emerald)';
        } else {
          initialAntiAfkText = 'Disabled';
          initialAntiAfkColor = 'var(--text-muted)';
        }
        const initDur = lastAntiAfkStatus.duration_seconds || 1;
        initialAntiAfkDesc = `Targeting ${count} running Roblox client window(s). Key: ${lastAntiAfkStatus.key_name || 'M1'} (${initDur}s hold). Interval: ${lastAntiAfkStatus.interval_minutes} min.`;
      }

      const statusRow = el('div', { class: 'setting-row' }, []);
      const statusText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Live Status')]),
        el('div', { class: 'setting-desc', id: 'anti-afk-live-desc' }, [document.createTextNode(initialAntiAfkDesc)])
      ]);
      statusRow.appendChild(statusText);

      const statusBadge = el('span', {
        id: 'anti-afk-live-badge',
        class: 'badge',
        style: `font-size:11.5px; font-weight:600; padding:4px 10px; background:var(--bg-3); color:${initialAntiAfkColor};`
      }, [document.createTextNode(initialAntiAfkText)]);
      statusRow.appendChild(statusBadge);
      antiAfkCard.appendChild(statusRow);

      const updateAntiAfkLiveStatus = async () => {
        try {
          const s = await apiService.getAntiAfkStatus();
          if (s && s.success) {
            lastAntiAfkStatus = s;
            const descEl = document.getElementById('anti-afk-live-desc');
            const badgeEl = document.getElementById('anti-afk-live-badge');
            if (!descEl || !badgeEl) return;
            const count = s.roblox_instance_count || 0;
            const remaining = Number(s.seconds_until_next_run || 0);
            const m = Math.floor(remaining / 60);
            const sec = remaining % 60;
            const timeStr = `${m}m ${sec}s`;
            if (s.in_progress) {
              badgeEl.textContent = 'Sending pulse...';
              badgeEl.style.color = 'var(--yellow)';
            } else if (s.enabled) {
              badgeEl.textContent = `Next pulse in ${timeStr}`;
              badgeEl.style.color = 'var(--emerald)';
            } else {
              badgeEl.textContent = 'Disabled';
              badgeEl.style.color = 'var(--text-muted)';
            }
            const dur = s.duration_seconds || 1;
            descEl.textContent = `Targeting ${count} running Roblox client window(s). Key: ${s.key_name || 'M1'} (${dur}s hold). Interval: ${s.interval_minutes} min.`;
          }
        } catch (_) { }
      };

      const afkTimer = setInterval(() => {
        if (!document.getElementById('anti-afk-live-badge')) {
          clearInterval(afkTimer);
          return;
        }
        updateAntiAfkLiveStatus();
      }, 1000);
      updateAntiAfkLiveStatus();

      const triggerRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
      const triggerText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Manual Test Pulse')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Immediately trigger the configured input across all applicable Roblox windows')])
      ]);
      triggerRow.appendChild(triggerText);

      const btnTrigger = el('button', { class: 'btn btn-secondary btn-sm', type: 'button', style: 'font-size:11.5px; padding:5px 12px;' }, [document.createTextNode('Manual Test Pulse')]);
      btnTrigger.addEventListener('click', async () => {
        try {
          btnTrigger.setAttribute('disabled', 'true');
          const res = await apiService.triggerAntiAfk();
          if (res.success) {
            toast('Anti-AFK test pulse sent');
          } else {
            toast(res.error || 'Anti-AFK pulse failed', 'error');
          }
        } catch (err: any) {
          toast(`Error: ${err.message || err}`, 'error');
        } finally {
          btnTrigger.removeAttribute('disabled');
        }
      });
      triggerRow.appendChild(btnTrigger);
      antiAfkCard.appendChild(triggerRow);
    }

    antiAfkSec.appendChild(antiAfkCard);
    inner.appendChild(antiAfkSec);

    const rejoinSec = el('div', { class: 'settings-section' }, []);
    rejoinSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Auto-Rejoin')]));
    const rejoinCard = el('div', { class: 'settings-card' }, []);

    const enableRejoinRow = settingsToggleRow('Enable Auto-Rejoin', 'Automatically reconnect when Roblox crashes or disconnects', 'autoRejoinEnabled');
    if (!state.settings.autoRejoinEnabled) {
      enableRejoinRow.style.borderBottom = 'none';
    }
    rejoinCard.appendChild(enableRejoinRow);

    if (state.settings.autoRejoinEnabled) {
      const delayRow = el('div', { class: 'setting-row' }, []);
      const delayText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Auto-Rejoin Delay')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Delay in seconds before attempting to reconnect')])
      ]);
      delayRow.appendChild(delayText);
      const delayInput = el('input', { type: 'number', min: '0', max: '300', value: String(state.settings.autoRejoinDelaySeconds || 5), style: 'width:80px; text-align:right;' }, []) as HTMLInputElement;
      delayInput.addEventListener('change', (e) => updateSetting('autoRejoinDelaySeconds', Number((e.target as HTMLInputElement).value) as any));
      delayRow.appendChild(delayInput);
      rejoinCard.appendChild(delayRow);

      const maxAttemptsRow = el('div', { class: 'setting-row' }, []);
      const maxAttemptsText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Maximum Attempts')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Maximum number of retries (0 = unlimited)')])
      ]);
      maxAttemptsRow.appendChild(maxAttemptsText);
      const maxAttemptsInput = el('input', { type: 'number', min: '0', max: '100', value: String(state.settings.autoRejoinMaxAttempts || 0), style: 'width:80px; text-align:right;' }, []) as HTMLInputElement;
      maxAttemptsInput.addEventListener('change', (e) => updateSetting('autoRejoinMaxAttempts', Number((e.target as HTMLInputElement).value) as any));
      maxAttemptsRow.appendChild(maxAttemptsInput);
      rejoinCard.appendChild(maxAttemptsRow);

      const behaviorRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
      const behaviorText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Rejoin Launch Behavior')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Choose whether to reconnect to the exact VIP server or the place')])
      ]);
      behaviorRow.appendChild(behaviorText);
      const behaviorSel = el('select', { style: 'min-width:180px;' }, []) as HTMLSelectElement;
      [
        { value: 'rejoin_same_server', label: 'Rejoin Same VIP Server' },
        { value: 'rejoin_same_game', label: 'Rejoin Game Place' }
      ].forEach(opt => {
        const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
        o.textContent = opt.label;
        if (opt.value === (state.settings.autoRejoinLaunchBehavior || 'rejoin_same_server')) o.selected = true;
        behaviorSel.appendChild(o);
      });
      behaviorSel.addEventListener('change', (e) => updateSetting('autoRejoinLaunchBehavior', (e.target as HTMLSelectElement).value as any));
      behaviorRow.appendChild(behaviorSel);
      rejoinCard.appendChild(behaviorRow);
    }

    rejoinSec.appendChild(rejoinCard);
    inner.appendChild(rejoinSec);

    const relaunchSec = el('div', { class: 'settings-section' }, []);
    relaunchSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Auto-Relaunch')]));
    const relaunchCard = el('div', { class: 'settings-card' }, []);

    const relaunchToggleRow = settingsToggleRow(
      'Enable Periodic Group Auto-Relaunch',
      'Automatically restart accounts belonging to a selected group',
      'autoRelaunchEnabled'
    );
    if (!state.settings.autoRelaunchEnabled) {
      relaunchToggleRow.style.borderBottom = 'none';
    }
    relaunchCard.appendChild(relaunchToggleRow);

    if (state.settings.autoRelaunchEnabled) {
      const groupRow = el('div', { class: 'setting-row' }, []);
      const groupText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Target Account Group')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Select which account group is affected')])
      ]);
      groupRow.appendChild(groupText);

      const groupSel = el('select', { style: 'min-width:180px;' }, []) as HTMLSelectElement;
      const groups = Array.from(new Set(state.accounts.map(a => (a.group || '').trim()).filter(Boolean))).sort();
      const defaultGroupOpt = el('option', { value: '' }, [document.createTextNode('-- Select Group --')]);
      groupSel.appendChild(defaultGroupOpt);
      groups.forEach(grp => {
        const o = el('option', { value: grp }, [document.createTextNode(grp)]) as HTMLOptionElement;
        if (grp === (state.settings.autoRelaunchGroup || '')) o.selected = true;
        groupSel.appendChild(o);
      });
      groupSel.addEventListener('change', async (e) => {
        const val = (e.target as HTMLSelectElement).value;
        await updateSetting('autoRelaunchGroup', val);
        await apiService.updateAutoRelaunchSettings({ autoRelaunchGroup: val });
      });
      groupRow.appendChild(groupSel);
      relaunchCard.appendChild(groupRow);

      const intervalRow = el('div', { class: 'setting-row' }, []);
      const intervalText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Relaunch Interval')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('How frequently the group should be relaunched in minutes')])
      ]);
      intervalRow.appendChild(intervalText);

      const intervalInput = el('input', {
        type: 'number',
        min: '1',
        max: '1440',
        value: String(state.settings.autoRelaunchIntervalMinutes || 60),
        style: 'width:80px; text-align:right;',
        title: 'Interval in minutes'
      }, []) as HTMLInputElement;
      intervalInput.addEventListener('change', async (e) => {
        const val = Math.max(1, parseInt((e.target as HTMLInputElement).value) || 60);
        await updateSetting('autoRelaunchIntervalMinutes', val);
        await apiService.updateAutoRelaunchSettings({ autoRelaunchIntervalMinutes: val });
      });
      intervalRow.appendChild(intervalInput);
      relaunchCard.appendChild(intervalRow);

      let initialRelaunchText = 'Checking...';
      let initialRelaunchColor = 'var(--fg)';
      let initialRelaunchDesc = 'Fetching status...';

      if (lastAutoRelaunchStatus && lastAutoRelaunchStatus.success) {
        const count = lastAutoRelaunchStatus.accounts_in_group || 0;
        const remaining = Number(lastAutoRelaunchStatus.seconds_until_next_run || 0);
        const m = Math.floor(remaining / 60);
        const sec = remaining % 60;
        const timeStr = `${m}m ${sec}s`;
        if (lastAutoRelaunchStatus.in_progress) {
          initialRelaunchText = 'Relaunching group...';
          initialRelaunchColor = 'var(--yellow)';
        } else if (lastAutoRelaunchStatus.enabled && lastAutoRelaunchStatus.group) {
          initialRelaunchText = `Next cycle in ${timeStr}`;
          initialRelaunchColor = 'var(--emerald)';
        } else {
          initialRelaunchText = lastAutoRelaunchStatus.group ? 'Idle' : 'No group selected';
          initialRelaunchColor = 'var(--text-muted)';
        }
        initialRelaunchDesc = `Group '${lastAutoRelaunchStatus.group || 'None'}' (${count} account(s)). Interval: ${lastAutoRelaunchStatus.interval_minutes} min. ${lastAutoRelaunchStatus.last_summary ? `Last: ${lastAutoRelaunchStatus.last_summary}` : ''}`;
      }

      const statusRow = el('div', { class: 'setting-row' }, []);
      const statusText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Live Schedule Status')]),
        el('div', { class: 'setting-desc', id: 'auto-relaunch-status-desc' }, [document.createTextNode(initialRelaunchDesc)])
      ]);
      statusRow.appendChild(statusText);

      const statusBadge = el('span', {
        id: 'auto-relaunch-status-badge',
        class: 'badge',
        style: `font-size:11.5px; font-weight:600; padding:4px 10px; background:var(--bg-3); color:${initialRelaunchColor};`
      }, [document.createTextNode(initialRelaunchText)]);
      statusRow.appendChild(statusBadge);
      relaunchCard.appendChild(statusRow);

      const updateRelaunchStatus = async () => {
        try {
          const s = await apiService.getAutoRelaunchStatus();
          if (s && s.success) {
            lastAutoRelaunchStatus = s;
            const descEl = document.getElementById('auto-relaunch-status-desc');
            const badgeEl = document.getElementById('auto-relaunch-status-badge');
            if (!descEl || !badgeEl) return;
            const count = s.accounts_in_group || 0;
            const remaining = Number(s.seconds_until_next_run || 0);
            const m = Math.floor(remaining / 60);
            const sec = remaining % 60;
            const timeStr = `${m}m ${sec}s`;
            if (s.in_progress) {
              badgeEl.textContent = 'Relaunching group...';
              badgeEl.style.color = 'var(--yellow)';
            } else if (s.enabled && s.group) {
              badgeEl.textContent = `Next cycle in ${timeStr}`;
              badgeEl.style.color = 'var(--emerald)';
            } else {
              badgeEl.textContent = s.group ? 'Idle' : 'No group selected';
              badgeEl.style.color = 'var(--text-muted)';
            }
            descEl.textContent = `Group '${s.group || 'None'}' (${count} account(s)). Interval: ${s.interval_minutes} min. ${s.last_summary ? `Last: ${s.last_summary}` : ''}`;
          }
        } catch (_) { }
      };

      const relaunchTimer = setInterval(() => {
        if (!document.getElementById('auto-relaunch-status-badge')) {
          clearInterval(relaunchTimer);
          return;
        }
        updateRelaunchStatus();
      }, 1000);
      updateRelaunchStatus();

      const triggerRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
      const triggerText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Relaunch Group Now')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Manually trigger the automation to close and relaunch the group now')])
      ]);
      triggerRow.appendChild(triggerText);

      const btnTrigger = el('button', { class: 'btn btn-secondary btn-sm', type: 'button', style: 'font-size:11.5px; padding:5px 12px;' }, [document.createTextNode('Relaunch Group Now')]);
      btnTrigger.addEventListener('click', async () => {
        try {
          btnTrigger.setAttribute('disabled', 'true');
          const res = await apiService.triggerAutoRelaunch();
          if (res.success) {
            toast('Group relaunch started');
            updateRelaunchStatus();
          } else {
            toast(res.error || 'Failed to trigger group relaunch', 'error');
          }
        } catch (err: any) {
          toast(`Error: ${err.message || err}`, 'error');
        } finally {
          btnTrigger.removeAttribute('disabled');
        }
      });
      triggerRow.appendChild(btnTrigger);
      relaunchCard.appendChild(triggerRow);
    }

    relaunchSec.appendChild(relaunchCard);
    inner.appendChild(relaunchSec);

    const memSec = el('div', { class: 'settings-section' }, []);
    memSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Memory Optimization')]));
    const memCard = el('div', { class: 'settings-card' }, []);

    const autoTrimRow = settingsToggleRow('Auto Memory Trim', 'Periodically optimize active Roblox client memory usage', 'autoMemoryTrimEnabled');
    if (!state.settings.autoMemoryTrimEnabled) {
      autoTrimRow.style.borderBottom = 'none';
    }
    memCard.appendChild(autoTrimRow);

    if (state.settings.autoMemoryTrimEnabled) {
      const trimIntervalRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
      const trimIntervalText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Memory Trim Interval')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('How frequently memory trimming occurs')])
      ]);
      trimIntervalRow.appendChild(trimIntervalText);
      const trimIntervalSel = el('select', { style: 'min-width:140px;' }, []) as HTMLSelectElement;
      [
        { value: '1', label: 'Every 1 Minute' },
        { value: '5', label: 'Every 5 Minutes (Default)' },
        { value: '10', label: 'Every 10 Minutes' },
        { value: '15', label: 'Every 15 Minutes' },
        { value: '30', label: 'Every 30 Minutes' }
      ].forEach(opt => {
        const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
        o.textContent = opt.label;
        if (Number(opt.value) === (state.settings.autoMemoryTrimIntervalMinutes || 5)) o.selected = true;
        trimIntervalSel.appendChild(o);
      });
      trimIntervalSel.addEventListener('change', (e) => updateSetting('autoMemoryTrimIntervalMinutes', Number((e.target as HTMLSelectElement).value) as any));
      trimIntervalRow.appendChild(trimIntervalSel);
      memCard.appendChild(trimIntervalRow);
    }

    memSec.appendChild(memCard);
    inner.appendChild(memSec);

    const browserSec = el('div', { class: 'settings-section' }, []);
    browserSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Browser')]));
    const browserCard = el('div', { class: 'settings-card' }, []);

    const browserRow = el('div', { class: 'setting-row' }, []);
    const browserText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Preferred Automation Browser')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Select preferred web browser for account operations')])
    ]);
    browserRow.appendChild(browserText);
    const browserSel = el('select', { style: 'min-width:140px;' }, []) as HTMLSelectElement;
    [
      { value: 'auto', label: 'Auto' },
      { value: 'chrome', label: 'Chrome' },
      { value: 'edge', label: 'Edge' },
      { value: 'firefox', label: 'Firefox' },
      { value: 'waterfox', label: 'Waterfox' },
      { value: 'chromium', label: 'Chromium' }
    ].forEach(item => {
      const o = el('option', { value: item.value }, []) as HTMLOptionElement;
      o.textContent = item.label;
      if (item.value === state.settings.preferredBrowser) o.selected = true;
      browserSel.appendChild(o);
    });
    browserSel.addEventListener('change', (e) => updateSetting('preferredBrowser', (e.target as HTMLSelectElement).value as any));
    browserRow.appendChild(browserSel);
    browserCard.appendChild(browserRow);

    const credInstancesRow = el('div', { class: 'setting-row' }, []);
    const credInstancesText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('User:Pass Import Instances')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Number of concurrent browser instances (1-5) initialized when importing User:Pass credentials.')])
    ]);
    credInstancesRow.appendChild(credInstancesText);
    const credInstancesInput = el('input', {
      type: 'number',
      min: '1',
      max: '5',
      value: String(state.settings.credentialImportInstances || 1),
      class: 'setting-input',
      style: 'width:80px; text-align:center;'
    }, []) as HTMLInputElement;
    credInstancesInput.addEventListener('change', (e) => {
      const v = Math.min(5, Math.max(1, parseInt((e.target as HTMLInputElement).value) || 1));
      (e.target as HTMLInputElement).value = String(v);
      updateSetting('credentialImportInstances', v);
    });
    credInstancesRow.appendChild(credInstancesInput);
    browserCard.appendChild(credInstancesRow);

    const chromiumRow = el('div', { class: 'setting-row', style: 'border-bottom:none; flex-direction:column; align-items:stretch; gap:10px;' }, []);
    const chromiumTop = el('div', { style: 'display:flex; justify-content:space-between; align-items:center; width:100%; gap:12px;' }, []);

    const isInstalled = Boolean(globalChromiumStatus?.installed);
    const isDownloading = Boolean(globalChromiumStatus?.downloading);
    const versionStr = globalChromiumStatus?.version || '';

    const initialBadgeText = isInstalled
      ? (versionStr ? `Installed (v${versionStr})` : 'Installed')
      : (isDownloading ? 'Downloading...' : 'Not Installed');
    const initialBadgeBg = isInstalled
      ? 'rgba(52, 211, 153, 0.2)'
      : (isDownloading ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255, 255, 255, 0.08)');
    const initialBadgeColor = isInstalled
      ? 'var(--emerald, #34d399)'
      : (isDownloading ? 'var(--accent, #3b82f6)' : 'var(--muted, #94a3b8)');
    const initialDescText = isInstalled
      ? (versionStr
        ? `Portable Chromium v${versionStr} and matching ChromeDriver are installed and ready.`
        : 'Portable Chromium and ChromeDriver are installed and ready.')
      : (isDownloading
        ? (globalChromiumStatus?.status_text || 'Downloading Chromium and ChromeDriver...')
        : (globalChromiumStatus?.error
          ? `Installation status: ${globalChromiumStatus.error}`
          : 'Download portable Chrome for Testing and ChromeDriver for isolated browser automation'));
    const initialBtnText = isInstalled
      ? 'Reinstall Chromium'
      : (isDownloading ? `${globalChromiumStatus?.progress || 0}%` : 'Download Chromium');
    const initialBtnClass = isInstalled
      ? 'btn btn-secondary btn-sm'
      : (isDownloading ? 'btn btn-secondary btn-sm' : 'btn btn-primary btn-sm');
    const initialUninstallDisplay = isInstalled ? 'inline-flex' : 'none';

    const chromiumInfo = el('div', {}, [
      el('div', { style: 'display:flex; align-items:center; gap:8px;' }, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Download Chromium')]),
        el('span', { id: 'chromium-status-badge', class: 'badge', style: `font-size:10.5px; padding:2px 8px; border-radius:10px; font-weight:600; background:${initialBadgeBg}; color:${initialBadgeColor};` }, [document.createTextNode(initialBadgeText)])
      ]),
      el('div', { class: 'setting-desc', id: 'chromium-status-desc' }, [
        document.createTextNode(initialDescText)
      ])
    ]);
    chromiumTop.appendChild(chromiumInfo);

    const chromiumActionGroup = el('div', { style: 'display:flex; align-items:center; gap:8px; flex-shrink:0;' }, []);

    const btnDownloadChromium = el('button', {
      class: initialBtnClass,
      id: 'btn-download-chromium',
      type: 'button',
      style: 'font-size:11.5px; padding:6px 14px; white-space:nowrap; display:inline-flex; align-items:center; gap:6px;'
    }, [
      el('span', { id: 'btn-download-chromium-text' }, [document.createTextNode(initialBtnText)])
    ]) as HTMLButtonElement;
    if (isDownloading) btnDownloadChromium.disabled = true;
    chromiumActionGroup.appendChild(btnDownloadChromium);

    const btnUninstallChromium = el('button', {
      class: 'btn btn-secondary btn-sm',
      id: 'btn-uninstall-chromium',
      type: 'button',
      style: `font-size:11.5px; padding:6px 12px; white-space:nowrap; display:${initialUninstallDisplay}; align-items:center; gap:6px; color:var(--rose, #f43f5e);`
    }, [
      el('span', { id: 'btn-uninstall-chromium-text' }, [document.createTextNode('Uninstall')])
    ]) as HTMLButtonElement;
    chromiumActionGroup.appendChild(btnUninstallChromium);

    chromiumTop.appendChild(chromiumActionGroup);
    chromiumRow.appendChild(chromiumTop);

    const chromiumProgressContainer = el('div', {
      id: 'chromium-progress-container',
      style: 'display:none; width:100%; margin-top:2px;'
    }, [
      el('div', {
        style: 'height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden; width:100%; position:relative;'
      }, [
        el('div', {
          id: 'chromium-progress-bar',
          style: 'height:100%; width:0%; background:var(--accent); border-radius:3px; transition:width 0.25s ease;'
        }, [])
      ])
    ]);
    chromiumRow.appendChild(chromiumProgressContainer);

    const updateChromiumUI = (status: ChromiumStatus) => {
      globalChromiumStatus = status;
      const badge = document.getElementById('chromium-status-badge');
      const desc = document.getElementById('chromium-status-desc');
      const btn = document.getElementById('btn-download-chromium') as HTMLButtonElement | null;
      const btnText = document.getElementById('btn-download-chromium-text');
      const btnUninstall = document.getElementById('btn-uninstall-chromium') as HTMLButtonElement | null;
      const progressContainer = document.getElementById('chromium-progress-container');
      const progressBar = document.getElementById('chromium-progress-bar');

      if (!badge || !desc || !btn || !btnText) return;

      if (status.downloading) {
        badge.textContent = 'Downloading...';
        badge.style.background = 'rgba(59, 130, 246, 0.2)';
        badge.style.color = 'var(--accent, #3b82f6)';
        desc.textContent = status.status_text || 'Downloading Chromium and ChromeDriver...';
        btn.disabled = true;
        btn.className = 'btn btn-secondary btn-sm';
        btnText.textContent = `${status.progress}%`;
        if (btnUninstall) btnUninstall.style.display = 'none';
        if (progressContainer) progressContainer.style.display = 'block';
        if (progressBar) progressBar.style.width = `${Math.max(status.progress, 5)}%`;
      } else {
        if (progressContainer) progressContainer.style.display = 'none';
        btn.disabled = false;
        if (status.installed) {
          badge.textContent = status.version ? `Installed (v${status.version})` : 'Installed';
          badge.style.background = 'rgba(52, 211, 153, 0.2)';
          badge.style.color = 'var(--emerald, #34d399)';
          desc.textContent = status.version
            ? `Portable Chromium v${status.version} and matching ChromeDriver are installed and ready.`
            : 'Portable Chromium and ChromeDriver are installed and ready.';
          btnText.textContent = 'Reinstall Chromium';
          btn.className = 'btn btn-secondary btn-sm';
          if (btnUninstall) {
            btnUninstall.style.display = 'inline-flex';
            btnUninstall.disabled = false;
          }
        } else {
          badge.textContent = 'Not Installed';
          badge.style.background = 'rgba(255, 255, 255, 0.08)';
          badge.style.color = 'var(--muted, #94a3b8)';
          desc.textContent = status.error
            ? `Installation status: ${status.error}`
            : 'Download portable Chrome for Testing and ChromeDriver for isolated browser automation.';
          btnText.textContent = 'Download Chromium';
          btn.className = 'btn btn-primary btn-sm';
          if (btnUninstall) btnUninstall.style.display = 'none';
        }
      }
    };

    const pollChromiumStatus = async () => {
      try {
        const res = await apiService.getChromiumStatus();
        if (res && res.success && res.status) {
          updateChromiumUI(res.status);
          if (res.status.downloading) {
            if (!globalChromiumPollTimer) {
              globalChromiumPollTimer = setInterval(pollChromiumStatus, 500);
            }
          } else {
            if (globalChromiumPollTimer) {
              clearInterval(globalChromiumPollTimer);
              globalChromiumPollTimer = null;
            }
          }
        } else {
          if (globalChromiumPollTimer) {
            clearInterval(globalChromiumPollTimer);
            globalChromiumPollTimer = null;
          }
        }
      } catch (err: any) {
        if (globalChromiumPollTimer) {
          clearInterval(globalChromiumPollTimer);
          globalChromiumPollTimer = null;
        }
      }
    };

    btnDownloadChromium.addEventListener('click', async () => {
      try {
        btnDownloadChromium.disabled = true;
        const res = await apiService.startChromiumDownload();
        if (res.success) {
          toast('Chromium download started', 'info');
          if (globalChromiumPollTimer) clearInterval(globalChromiumPollTimer);
          globalChromiumPollTimer = setInterval(pollChromiumStatus, 500);
          pollChromiumStatus();
        } else {
          toast(res.error || 'Failed to start Chromium download', 'error');
          btnDownloadChromium.disabled = false;
        }
      } catch (err: any) {
        toast(`Error: ${err?.message || err}`, 'error');
        btnDownloadChromium.disabled = false;
      }
    });

    btnUninstallChromium.addEventListener('click', async () => {
      try {
        const confirmed = await showConfirmModal(
          'Uninstall Chromium',
          'Are you sure you want to uninstall and remove portable Chromium and ChromeDriver?',
          'Uninstall',
          true
        );
        if (!confirmed) return;

        btnUninstallChromium.disabled = true;
        btnDownloadChromium.disabled = true;
        const res = await apiService.uninstallChromium();
        if (res && res.success) {
          toast('Chromium uninstalled successfully', 'success');
          if (state.settings.preferredBrowser === 'chromium') {
            updateSetting('preferredBrowser', 'auto');
            browserSel.value = 'auto';
          }
          await pollChromiumStatus();
        } else {
          toast(res?.error || 'Failed to uninstall Chromium', 'error');
          btnUninstallChromium.disabled = false;
          btnDownloadChromium.disabled = false;
        }
      } catch (err: any) {
        toast(`Error: ${err?.message || err}`, 'error');
        btnUninstallChromium.disabled = false;
        btnDownloadChromium.disabled = false;
      }
    });

    pollChromiumStatus();

    browserCard.appendChild(chromiumRow);
    browserSec.appendChild(browserCard);
    inner.appendChild(browserSec);
  }

  if (state.settingsTab === 'appearance') {
    renderThemesTab(inner);

    const layoutSec = el('div', { class: 'settings-section' }, []);
    layoutSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Workspace Layout')]));
    const layoutCard = el('div', { class: 'settings-card' }, []);

    const layoutPresetRow = el('div', { class: 'setting-row' }, []);
    const layoutPresetText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('UI Layout Format Preset')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Switch positions of Account Details panel and Launch & Saved Games bar')])
    ]);
    layoutPresetRow.appendChild(layoutPresetText);
    const layoutPresetSel = el('select', {}, []) as HTMLSelectElement;
    [
      { value: 'standard', label: 'Standard Layout' },
      { value: 'swapped', label: 'Legacy Layout' }
    ].forEach(opt => {
      const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
      o.textContent = opt.label;
      if (opt.value === (state.settings.layoutPreset || 'standard')) o.selected = true;
      layoutPresetSel.appendChild(o);
    });
    layoutPresetSel.addEventListener('change', (e) => updateSetting('layoutPreset', (e.target as HTMLSelectElement).value as any));
    layoutPresetRow.appendChild(layoutPresetSel);
    layoutCard.appendChild(layoutPresetRow);

    layoutCard.appendChild(settingsToggleRow('Show Account Inspector Panel', 'Display detail panel for selected account on the right', 'showDetailPanel'));
    const savedGamesRow = settingsToggleRow('Show Saved Games Bar', 'Display saved games quick-launch row at the top', 'showSavedGamesBar');
    savedGamesRow.style.borderBottom = 'none';
    layoutCard.appendChild(savedGamesRow);

    layoutSec.appendChild(layoutCard);
    inner.appendChild(layoutSec);

    const tableSec = el('div', { class: 'settings-section' }, []);
    tableSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Accounts Table')]));
    const tableCard = el('div', { class: 'settings-card' }, []);

    tableCard.appendChild(settingsToggleRow('Compact Table Rows', 'Reduce account row padding', 'compactRows'));
    tableCard.appendChild(settingsToggleRow('Show Avatars in Table', 'Show account avatar images in table rows', 'showTableAvatars'));
    tableCard.appendChild(settingsToggleRow('Download Avatar Profile Icons', 'Fetch real Roblox avatar icons instead of stylized initials', 'downloadAvatarIcons'));
    const statusDotRow = settingsToggleRow('Show Account Status Dot', 'Display an account status indicator dot in accounts table', 'activeIndicator');
    statusDotRow.style.borderBottom = 'none';
    tableCard.appendChild(statusDotRow);
    tableSec.appendChild(tableCard);
    inner.appendChild(tableSec);
  }

  if (state.settingsTab === 'notifications') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Notifications')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Configure toast notification position, duration, alert categories, and sound effects.')]));

    const toastsSec = el('div', { class: 'settings-section' }, []);
    toastsSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Toasts')]));
    const toastsCard = el('div', { class: 'settings-card' }, []);

    const posRow = el('div', { class: 'setting-row' }, []);
    const posText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Toast Screen Position')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Screen location where notification popups appear')])
    ]);
    posRow.appendChild(posText);
    const posSel = el('select', {}, []) as HTMLSelectElement;
    [
      { value: 'bottom-right', label: 'Bottom-Right' },
      { value: 'top-right', label: 'Top-Right' },
      { value: 'bottom-left', label: 'Bottom-Left' },
      { value: 'top-left', label: 'Top-Left' },
      { value: 'top-center', label: 'Top-Center' }
    ].forEach(opt => {
      const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
      o.textContent = opt.label;
      if (opt.value === (state.settings.toastPosition || 'bottom-right')) o.selected = true;
      posSel.appendChild(o);
    });
    posSel.addEventListener('change', (e) => updateSetting('toastPosition', (e.target as HTMLSelectElement).value as any));
    posRow.appendChild(posSel);
    toastsCard.appendChild(posRow);

    const durRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const durText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Notification Display Time')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('How long notifications remain visible')])
    ]);
    durRow.appendChild(durText);
    const durSel = el('select', {}, []) as HTMLSelectElement;
    [
      { value: '2000', label: 'Quick (2 seconds)' },
      { value: '3500', label: 'Standard (3.5 seconds)' },
      { value: '5000', label: 'Long (5 seconds)' },
      { value: '8000', label: 'Persistent (8 seconds)' }
    ].forEach(opt => {
      const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
      o.textContent = opt.label;
      if (Number(opt.value) === (state.settings.toastDuration || 3500)) o.selected = true;
      durSel.appendChild(o);
    });
    durSel.addEventListener('change', (e) => updateSetting('toastDuration', Number((e.target as HTMLSelectElement).value) as any));
    durRow.appendChild(durSel);
    toastsCard.appendChild(durRow);

    toastsSec.appendChild(toastsCard);
    inner.appendChild(toastsSec);

    const typesSec = el('div', { class: 'settings-section' }, []);
    typesSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Notification Types')]));
    const typesCard = el('div', { class: 'settings-card' }, []);

    typesCard.appendChild(settingsToggleRow('Show Launch Alerts', 'Show notifications when accounts are launched or browser sessions are opened', 'showLaunchNotifications'));
    typesCard.appendChild(settingsToggleRow('Show Error & Warning Alerts', 'Show errors and warnings', 'showErrorNotifications'));

    const successRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const successText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Show Success Popups')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Show success notifications when operations complete')])
    ]);
    successRow.appendChild(successText);
    const successSw = el('button', {
      class: 'switch' + (!state.settings.disableSuccessPopups ? ' on' : ''),
      type: 'button'
    }, [el('span', { class: 'knob' }, [])]) as HTMLButtonElement;
    successSw.addEventListener('click', () => updateSetting('disableSuccessPopups', state.settings.disableSuccessPopups ? false : true));
    successRow.appendChild(successSw);
    typesCard.appendChild(successRow);

    typesSec.appendChild(typesCard);
    inner.appendChild(typesSec);

    const soundSec = el('div', { class: 'settings-section' }, []);
    soundSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Sound')]));
    const soundCard = el('div', { class: 'settings-card' }, []);
    const soundRow = settingsToggleRow('Audio Chime Effects', 'Play a sound when notifications appear', 'enableSoundEffects');
    soundRow.style.borderBottom = 'none';
    soundCard.appendChild(soundRow);
    soundSec.appendChild(soundCard);
    inner.appendChild(soundSec);

    const previewSec = el('div', { class: 'settings-section' }, []);
    previewSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Preview')]));
    const previewCard = el('div', { class: 'settings-card' }, []);

    const previewRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const previewText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Preview Notification')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Test notification appearance, position, duration, and sound')])
    ]);
    previewRow.appendChild(previewText);

    const previewBtn = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Preview Notification')]);
    previewBtn.addEventListener('click', () => {
      toast('Notification settings test successful!', 'success', true);
    });
    previewRow.appendChild(previewBtn);
    previewCard.appendChild(previewRow);
    previewSec.appendChild(previewCard);
    inner.appendChild(previewSec);
  }

  if (state.settingsTab === 'privacy') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Privacy')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Settings designed to prevent sensitive information from being visible during streaming, recording, screen sharing, or demonstrations.')]));

    const streamerSec = el('div', { class: 'settings-section' }, []);
    streamerSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Streamer Mode')]));
    const streamerCard = el('div', { class: 'settings-card' }, []);

    const streamerToggleRow = settingsToggleRow('Streamer Mode', 'Enable privacy masking throughout FRAM', 'streamerMode');
    if (!state.settings.streamerMode) {
      streamerToggleRow.style.borderBottom = 'none';
    }
    streamerCard.appendChild(streamerToggleRow);
    streamerSec.appendChild(streamerCard);
    inner.appendChild(streamerSec);

    if (state.settings.streamerMode) {
      const maskSec = el('div', { class: 'settings-section' }, []);
      maskSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Information Masking')]));
      const maskCard = el('div', { class: 'settings-card' }, []);

      maskCard.appendChild(settingsToggleRow('Mask Usernames & Display Names', 'Hide account usernames and display names', 'streamerHideUsernames'));
      maskCard.appendChild(settingsToggleRow('Blur Account Avatars', 'Blur profile pictures', 'streamerHideAvatars'));
      maskCard.appendChild(settingsToggleRow('Mask Passwords, Cookies & VIP Links', 'Hide sensitive account information and VIP server links/codes', 'streamerHideSensitiveInfo'));
      const groupsRow = settingsToggleRow('Hide Group Tags & Notes', 'Hide account group information and notes', 'streamerHideGroupsAndNotes');
      groupsRow.style.borderBottom = 'none';
      maskCard.appendChild(groupsRow);

      maskSec.appendChild(maskCard);
      inner.appendChild(maskSec);

      const styleSec = el('div', { class: 'settings-section' }, []);
      styleSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Masking Style')]));
      const styleCard = el('div', { class: 'settings-card' }, []);

      const blurRow = el('div', { class: 'setting-row' }, []);
      const blurText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Streamer Blur Intensity')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Choose visual blur level for masked elements')])
      ]);
      blurRow.appendChild(blurText);

      const blurSelect = el('select', { class: 'header-tool-select', style: 'min-width:160px;' }, []) as HTMLSelectElement;
      [
        { value: 'light', label: 'Light Blur' },
        { value: 'medium', label: 'Medium Blur' },
        { value: 'heavy', label: 'Heavy Blur' }
      ].forEach(opt => {
        const o = el('option', { value: opt.value }, []) as HTMLOptionElement;
        o.textContent = opt.label;
        const currentVal = ((state.settings.streamerBlurLevel as string) === 'mask' ? 'medium' : state.settings.streamerBlurLevel) || 'medium';
        if (opt.value === currentVal) {
          o.selected = true;
        }
        blurSelect.appendChild(o);
      });

      blurSelect.addEventListener('change', (e) => {
        const val = (e.target as HTMLSelectElement).value as any;
        updateSetting('streamerBlurLevel', val);
      });
      blurRow.appendChild(blurSelect);
      styleCard.appendChild(blurRow);

      const hoverRow = settingsToggleRow('Uncensor on Hover', 'Temporarily uncensor masked elements when hovering over them', 'streamerRevealOnHover');
      hoverRow.style.borderBottom = 'none';
      styleCard.appendChild(hoverRow);

      styleSec.appendChild(styleCard);
      inner.appendChild(styleSec);
    }
  }

  if (state.settingsTab === 'security') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Security')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Settings responsible for protecting FRAM stored account information and sessions.')]));

    const encSec = el('div', { class: 'settings-section' }, []);
    encSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Encryption')]));
    const encCard = el('div', { class: 'settings-card' }, []);

    const encRow = el('div', { class: 'setting-row' }, []);
    const encText = el('div', {}, []);
    encText.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode('Encryption Status')]));
    encText.appendChild(el('div', { class: 'setting-desc' }, [
      document.createTextNode(state.settings.encryptionEnabled
        ? 'Account database is encrypted and protected'
        : 'Account data stored in plain text')
    ]));
    encRow.appendChild(encText);

    const encBadge = state.settings.encryptionEnabled
      ? el('span', { class: 'badge badge-success' }, [document.createTextNode('Active')])
      : el('span', { style: 'color: var(--yellow); font-size: 11.5px; font-weight: 700;' }, [document.createTextNode('Unencrypted')]);
    encRow.appendChild(encBadge);
    encCard.appendChild(encRow);

    const methodRow = el('div', { class: 'setting-row' }, []);
    methodRow.dataset.settingId = 'setting-encryption-method';
    const methodText = el('div', {}, []);
    methodText.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode('Encryption Method')]));
    const currentMethod = state.settings.encryptionEnabled ? (state.settings.encryptionMethod || 'none') : 'none';
    const cipherLabel = state.settings.encryptionEnabled
      ? (currentMethod === 'hardware' ? 'Hardware profile bound to this machine' : 'AES-256 GCM master password protection')
      : 'No encryption configured (plain text JSON)';
    methodText.appendChild(el('div', { class: 'setting-desc' }, [
      document.createTextNode(cipherLabel)
    ]));
    methodRow.appendChild(methodText);

    const methodDisplay = !state.settings.encryptionEnabled
      ? 'None'
      : (currentMethod === 'hardware' ? 'Hardware' : 'Password');
    const methodBadge = el('span', {
      class: 'badge',
      style: 'font-size:11.5px; font-weight:600; padding:4px 10px; background:var(--bg-3); color:var(--fg); text-transform: capitalize;'
    }, [document.createTextNode(methodDisplay)]);
    methodRow.appendChild(methodBadge);
    encCard.appendChild(methodRow);

    const switchRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    switchRow.dataset.settingId = 'setting-switch-encryption';
    const switchText = el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Switch Encryption Method')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Change how accounts and credentials are secured, or update your master password')])
    ]);
    switchRow.appendChild(switchText);

    const switchBtnText = state.settings.encryptionEnabled && currentMethod === 'password'
      ? 'Switch Method / Change Password'
      : 'Switch Method';
    const switchBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [
      document.createTextNode(switchBtnText)
    ]) as HTMLButtonElement;
    switchBtn.addEventListener('click', () => {
      openSwitchEncryptionModal();
    });
    switchRow.appendChild(switchBtn);
    encCard.appendChild(switchRow);

    encSec.appendChild(encCard);
    inner.appendChild(encSec);

    if (state.settings.encryptionEnabled && state.settings.encryptionMethod === 'password') {
      const sessionSec = el('div', { class: 'settings-section' }, []);
      sessionSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Session Security')]));
      const sessionCard = el('div', { class: 'settings-card' }, []);

      const lockRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
      const lockText = el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Lock Session')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Immediately lock FRAM and require the master password to continue')])
      ]);
      lockRow.appendChild(lockText);

      const lockBtn = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Lock Session')]) as HTMLButtonElement;
      lockBtn.addEventListener('click', async () => {
        await apiService.lockApp();
        state.isLocked = true;
        toast('Application locked', 'info');
        renderUnlockScreen();
      });
      lockRow.appendChild(lockBtn);
      sessionCard.appendChild(lockRow);

      sessionSec.appendChild(sessionCard);
      inner.appendChild(sessionSec);
    }
  }

  if (state.settingsTab === 'data') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Data')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Settings for backups, importing/exporting, deletion, and application data management.')]));

    const backupSec = el('div', { class: 'settings-section' }, []);
    backupSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Backup & Import')]));
    const backupCard = el('div', { class: 'settings-card' }, []);

    const backupRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    backupRow.dataset.settingId = 'setting-backup-accounts';
    const backupText = el('div', {}, []);
    backupText.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode('Backup & Import')]));
    backupText.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode('Export accounts as encrypted or plain JSON, or import previously exported accounts')]));
    backupRow.appendChild(backupText);

    const backupBtns = el('div', { class: 'btn-row' }, []);
    const exportBtn = el('button', { class: 'btn btn-secondary' }, [document.createTextNode('Backup')]);
    exportBtn.addEventListener('click', exportAccounts);

    const importBtn = el('button', { class: 'btn btn-secondary' }, [document.createTextNode('Import')]);
    const importInput = el('input', {
      type: 'file',
      accept: '.json',
      style: 'display:none;'
    }, []) as HTMLInputElement;
    importInput.addEventListener('change', (e) => {
      importAccounts((e.target as HTMLInputElement).files![0]);
      (e.target as HTMLInputElement).value = '';
    });
    importBtn.addEventListener('click', () => importInput.click());

    backupBtns.appendChild(exportBtn);
    backupBtns.appendChild(importBtn);
    backupBtns.appendChild(importInput);
    backupRow.appendChild(backupBtns);
    backupCard.appendChild(backupRow);

    backupSec.appendChild(backupCard);
    inner.appendChild(backupSec);

    const delSec = el('div', { class: 'settings-section' }, []);
    delSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Deletion')]));
    const delCard = el('div', { class: 'settings-card' }, []);
    const bulkDelRow = settingsToggleRow('Confirm Before Bulk Deletion', 'Require confirmation before deleting multiple accounts', 'confirmBulkDelete');
    bulkDelRow.style.borderBottom = 'none';
    delCard.appendChild(bulkDelRow);
    delSec.appendChild(delCard);
    inner.appendChild(delSec);

    const dangerSec = el('div', { class: 'settings-section' }, []);
    dangerSec.appendChild(el('div', { class: 'settings-section-title', style: 'color: var(--red);' }, [document.createTextNode('Danger Zone')]));
    const dangerCard = el('div', { class: 'settings-card danger' }, []);

    const clearRow = el('div', { class: 'setting-row' }, []);
    const clearText = el('div', {}, []);
    clearText.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode('Clear All Accounts')]));
    clearText.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode('Remove all accounts from the database')]));
    clearRow.appendChild(clearText);

    const clearBtn = el('button', { class: 'btn btn-danger' }, [document.createTextNode('Clear All Accounts')]);
    clearBtn.addEventListener('click', clearAllAccounts);
    clearRow.appendChild(clearBtn);
    dangerCard.appendChild(clearRow);

    const deleteDataRow = el('div', { class: 'setting-row' }, []);
    const deleteDataText = el('div', {}, []);
    deleteDataText.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode('Delete All Data')]));
    deleteDataText.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode('Permanently remove accounts, games, and custom settings')]));
    deleteDataRow.appendChild(deleteDataText);

    const deleteDataBtn = el('button', { class: 'btn btn-danger' }, [document.createTextNode('Delete All Data')]);
    deleteDataBtn.addEventListener('click', deleteAllData);
    deleteDataRow.appendChild(deleteDataBtn);
    dangerCard.appendChild(deleteDataRow);

    const uninstallRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
    const uninstallText = el('div', {}, []);
    uninstallText.appendChild(el('div', { class: 'setting-label' }, [document.createTextNode('Uninstall Application')]));
    uninstallText.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode('Completely uninstall FRAM and clean up application data')]));
    uninstallRow.appendChild(uninstallText);

    const uninstallBtn = el('button', { class: 'btn btn-danger' }, [document.createTextNode('Uninstall Application')]);
    uninstallBtn.addEventListener('click', uninstallApplication);
    uninstallRow.appendChild(uninstallBtn);
    dangerCard.appendChild(uninstallRow);

    dangerSec.appendChild(dangerCard);
    inner.appendChild(dangerSec);
  }

  if (state.settingsTab === 'keybinds') {
    inner.appendChild(el('h2', {}, [document.createTextNode('Keybinds')]));
    inner.appendChild(el('p', {}, [document.createTextNode('Configure custom in-app keyboard shortcuts. Click any key combination to rebind it, or reset individual keys or all keys back to defaults.')]));

    const topToolbar = el('div', { class: 'keybind-top-toolbar' }, []);
    const hasAnyCustom = Boolean(state.settings.customKeybinds && Object.keys(state.settings.customKeybinds).length > 0);
    if (hasAnyCustom) {
      const resetAllBtn = el('button', {
        class: 'btn btn-sm btn-secondary',
        style: 'display:inline-flex; align-items:center; gap:6px;',
        html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg> Reset All to Defaults'
      }, []);
      resetAllBtn.onclick = () => {
        stopRecordingKeybind();
        state.settings.customKeybinds = {};
        updateSetting('customKeybinds', {}).catch(() => { });
        toast('All keybinds reset to defaults', 'success');
        renderSettingsView();
      };
      topToolbar.appendChild(resetAllBtn);
    }
    inner.appendChild(topToolbar);

    const renderKeybindRow = (def: KeybindDefinition, isLast: boolean) => {
      const row = el('div', { class: 'setting-row', id: `keybind-row-${def.id}` }, []);
      if (isLast) {
        row.style.borderBottom = 'none';
      }

      const text = el('div', {}, []);
      const labelWrap = el('div', { class: 'setting-label', style: 'display:flex; align-items:center; gap:8px;' }, [
        document.createTextNode(def.label)
      ]);
      if (isCustomKeybind(def.id)) {
        const badge = el('span', {
          style: 'font-size:10px; font-weight:600; padding:1px 6px; border-radius:4px; background:var(--primary-dim); color:var(--primary); text-transform:uppercase; letter-spacing:0.5px;'
        }, [document.createTextNode('Custom')]);
        labelWrap.appendChild(badge);
      }
      text.appendChild(labelWrap);
      text.appendChild(el('div', { class: 'setting-desc' }, [document.createTextNode(def.desc)]));
      row.appendChild(text);

      const actionsWrap = el('div', { class: 'keybind-actions-wrap' }, []);
      const isRecording = activeRecordingKeybindId === def.id;

      const recordBtn = el('button', {
        class: `keybind-record-btn${isRecording ? ' recording' : ''}`,
        type: 'button',
        title: isRecording ? 'Press desired key combination (Escape to cancel)' : 'Click to rebind'
      }, []);

      if (isRecording) {
        const dot = el('span', { class: 'keybind-recording-dot' }, []);
        recordBtn.appendChild(dot);
        recordBtn.appendChild(document.createTextNode('Press keys... (Esc to cancel)'));
      } else {
        const keys = getKeybinds(def.id);
        keys.forEach((k, idx) => {
          if (idx > 0) {
            const sep = el('span', { style: 'font-size:11px; color:var(--text-muted); margin:0 3px;' }, [document.createTextNode('or')]);
            recordBtn.appendChild(sep);
          }
          const subKeys = k.split('+');
          const kbdWrap = el('span', { style: 'display:inline-flex; align-items:center; gap:3px;' }, []);
          subKeys.forEach((subK, subIdx) => {
            if (subIdx > 0) {
              const plus = el('span', { style: 'font-size:10px; color:var(--text-muted);' }, [document.createTextNode('+')]);
              kbdWrap.appendChild(plus);
            }
            kbdWrap.appendChild(el('kbd', {}, [document.createTextNode(subK)]));
          });
          recordBtn.appendChild(kbdWrap);
        });
      }

      recordBtn.onclick = (e) => {
        e.stopPropagation();
        if (isRecording) {
          stopRecordingKeybind();
          renderSettingsView();
        } else {
          startRecordingKeybind(def.id, () => {
            renderSettingsView();
          });
          renderSettingsView();
        }
      };
      actionsWrap.appendChild(recordBtn);

      if (isCustomKeybind(def.id)) {
        const resetBtn = el('button', {
          class: 'keybind-reset-btn',
          type: 'button',
          title: 'Reset this shortcut to default',
          html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>'
        }, []);
        resetBtn.onclick = (e) => {
          e.stopPropagation();
          if (state.settings.customKeybinds) {
            delete state.settings.customKeybinds[def.id];
          }
          updateSetting('customKeybinds', state.settings.customKeybinds).catch(() => { });
          toast(`Reset "${def.label}" to default`, 'info');
          renderSettingsView();
        };
        actionsWrap.appendChild(resetBtn);
      }

      row.appendChild(actionsWrap);
      return row;
    };

    const categories: { key: 'actions' | 'navigation' | 'tools'; title: string }[] = [
      { key: 'actions', title: 'Account Actions' },
      { key: 'navigation', title: 'Navigation' },
      { key: 'tools', title: 'Roblox Tools' }
    ];

    categories.forEach(cat => {
      const items = KEYBIND_DEFINITIONS.filter(k => {
        if (k.id === 'multi_select' && !state.settings.multiSelect) return false;
        return k.category === cat.key;
      });
      if (items.length === 0) return;

      const sec = el('div', { class: 'settings-section' }, []);
      sec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode(cat.title)]));
      const card = el('div', { class: 'settings-card' }, []);

      items.forEach((item, idx) => {
        card.appendChild(renderKeybindRow(item, idx === items.length - 1));
      });

      sec.appendChild(card);
      inner.appendChild(sec);
    });
  }

  if (state.settingsTab === 'custom-theme') {
    renderCustomThemeStudio(inner);
  }

  const searchInput = document.getElementById('settings-search-input') as HTMLInputElement | null;
  if (searchInput) {
    searchInput.value = state.settingsSearch || '';
    searchInput.oninput = (e) => {
      state.settingsSearch = (e.target as HTMLInputElement).value;
      renderSettingsView();
    };
  }

  if (query) {
    let matchCount = 0;
    const sections = inner.querySelectorAll('.settings-section');
    sections.forEach(sec => {
      let secHasMatches = false;
      const rows = sec.querySelectorAll('.setting-row');
      rows.forEach(r => {
        const text = r.textContent?.toLowerCase() || '';
        if (text.includes(query)) {
          (r as HTMLElement).style.display = '';
          secHasMatches = true;
          matchCount++;
        } else {
          (r as HTMLElement).style.display = 'none';
        }
      });

      const secTitle = sec.querySelector('.settings-section-title')?.textContent?.toLowerCase() || '';
      if (secTitle.includes(query)) {
        rows.forEach(r => {
          (r as HTMLElement).style.display = '';
        });
        secHasMatches = true;
        matchCount++;
      }

      (sec as HTMLElement).style.display = secHasMatches ? '' : 'none';
    });

    const banner = el('div', { class: 'settings-search-banner' }, [
      el('span', {}, [document.createTextNode(`Showing settings matching "${state.settingsSearch}" (${matchCount} found)`)]),
      el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:3px 8px;font-size:11px;' }, [document.createTextNode('Clear Search')])
    ]);
    banner.querySelector('button')?.addEventListener('click', () => {
      state.settingsSearch = '';
      if (searchInput) searchInput.value = '';
      renderSettingsView();
    });
    inner.insertBefore(banner, inner.firstChild);

    if (matchCount === 0) {
      const altTabMatches: { tabId: string; label: string; count: number }[] = [];
      const categoryMatches: Record<string, string[]> = {
        general: ['always on top', 'start fram on windows startup', 'minimize to system tray', 'default startup landing view', 'validate cookies on startup', 'multi select', 'account list default sorting', 'automatic update checks', 'check for updates now', 'rerun setup wizard'],
        roblox: ['roblox installation path', 'roblox client settings', 'preserve global client settings', 'preserve in-game settings', 'roblox fastflags', 'roblox fastflags editor', 'roblox icon & thumbnail cache', 'auto-check for roblox updates', 'rblxswap', 'clean traces', 'alt swap', 'spoof mac', 'hwid', 'mac address', 'disk volume serial', 'anticheat', 'restore identifiers', 'spoof hardware'],
        launching: ['multi-instance roblox', 'multi-account launch stagger delay', 'confirm before account launch', 'preferred server region', 'server for each account', 'save launch details', 'auto-close roblox clients on fram exit', 'headless client launch', 'idle cpu priority', 'headless auto memory trim', 'headless actions'],
        automation: ['keep roblox clients arranged', 'auto-arrange monitor scope', 'auto-arrange tile sizing mode', 'target client width', 'target client height', 'anti-afk', 'anti-afk interval', 'simulated input key', 'manual test pulse', 'auto-rejoin', 'auto-relaunch', 'relaunch group now', 'auto memory trim', 'preferred automation browser'],
        appearance: ['color theme', 'custom theme studio', 'custom accent color', 'custom background wallpaper', 'wallpaper blur', 'wallpaper opacity', 'wallpaper dim', 'ui layout format preset', 'show account inspector panel', 'show saved games bar', 'compact table rows', 'show avatars in table', 'download avatar profile icons', 'show account status dot'],
        notifications: ['toast screen position', 'notification display time', 'show launch alerts', 'show error & warning alerts', 'show success popups', 'audio chime effects', 'preview notification'],
        privacy: ['streamer mode', 'mask usernames & display names', 'blur account avatars', 'mask passwords & cookies', 'hide group tags & notes', 'streamer masking style'],
        security: ['encryption status', 'encryption method', 'switch encryption', 'change encryption method', ...(state.settings.encryptionEnabled && state.settings.encryptionMethod === 'password' ? ['lock session'] : [])],
        data: ['backup', 'import', 'backup & import', 'backup accounts', 'restore accounts', 'import accounts', 'confirm before bulk deletion', 'clear all accounts', 'delete all data', 'uninstall application'],
        keybinds: ['account actions', 'keyboard shortcuts', 'navigation hotkeys', 'roblox tools', 'auto-arrange clients', 'kill all roblox clients', 'trim client memory']
      };

      SETTINGS_TABS.forEach(t => {
        if (t.id !== state.settingsTab) {
          const keywords = categoryMatches[t.id] || [];
          const count = keywords.filter(k => k.includes(query)).length;
          if (count > 0) {
            altTabMatches.push({ tabId: t.id, label: t.label, count });
          }
        }
      });

      const noResults = el('div', { class: 'empty-state', style: 'padding:30px 20px;' }, [
        el('div', { class: 'empty-state-title' }, [document.createTextNode('No Settings Found in This Tab')]),
        el('div', { class: 'empty-state-desc' }, [document.createTextNode(`No settings match "${state.settingsSearch}" in current view.`)])
      ]);

      if (altTabMatches.length > 0) {
        const suggWrap = el('div', { style: 'margin-top:14px;display:flex;gap:8px;justify-content:center;' }, []);
        altTabMatches.forEach(atm => {
          const btn = el('button', { class: 'btn btn-primary', style: 'font-size:11px;' }, [
            document.createTextNode(`Switch to ${atm.label} (${atm.count} match${atm.count > 1 ? 'es' : ''})`)
          ]);
          btn.addEventListener('click', () => {
            state.settingsTab = atm.tabId as any;
            renderSettingsView();
          });
          suggWrap.appendChild(btn);
        });
        noResults.appendChild(suggWrap);
      }
      inner.appendChild(noResults);
    }
  }

  if (settingsScrollParent) {
    settingsScrollParent.scrollTop = savedScrollTop;
  }
}

function createThemePreviewBox(theme: Theme): HTMLElement {
  const box = el('div', { class: 'theme-preview-box', style: `background: ${theme.colors.bg};` }, []);

  const header = el('div', { class: 'theme-preview-header', style: `background: ${theme.colors.bg2}; border-bottom: 1px solid ${theme.colors.borderSoft};` }, [
    el('div', { class: 'theme-preview-dot', style: `background: ${theme.colors.border};` }, []),
    el('div', { class: 'theme-preview-dot', style: `background: ${theme.colors.border};` }, [])
  ]);
  box.appendChild(header);

  const body = el('div', { class: 'theme-preview-body' }, []);
  const side = el('div', { class: 'theme-preview-side', style: `background: ${theme.colors.card}; border-right: 1px solid ${theme.colors.borderSoft};` }, [
    el('div', { class: 'theme-preview-item', style: `background: ${theme.colors.primary};` }, []),
    el('div', { class: 'theme-preview-item', style: `background: ${theme.colors.border};` }, []),
    el('div', { class: 'theme-preview-item', style: `background: ${theme.colors.border};` }, [])
  ]);
  body.appendChild(side);

  const content = el('div', { class: 'theme-preview-content', style: `background: ${theme.colors.bg};` }, [
    el('div', { class: 'theme-preview-row active', style: `background: ${theme.colors.primaryDim}; border-left: 2px solid ${theme.colors.primary};` }, []),
    el('div', { class: 'theme-preview-row', style: `background: ${theme.colors.cardAlt};` }, []),
    el('div', { class: 'theme-preview-row', style: `background: ${theme.colors.cardAlt}; opacity: 0.6;` }, [])
  ]);
  body.appendChild(content);
  box.appendChild(body);

  return box;
}

function compressImage(file: File, maxWidth = 1920, maxHeight = 1080, quality = 0.85): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        let w = img.width;
        let h = img.height;
        if (w > maxWidth || h > maxHeight) {
          const ratio = Math.min(maxWidth / w, maxHeight / h);
          w = Math.round(w * ratio);
          h = Math.round(h * ratio);
        }
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          resolve(reader.result as string);
          return;
        }
        ctx.drawImage(img, 0, 0, w, h);
        const dataUrl = canvas.toDataURL('image/jpeg', quality);
        resolve(dataUrl);
      };
      img.onerror = () => resolve(reader.result as string);
      img.src = reader.result as string;
    };
    reader.onerror = () => resolve('');
    reader.readAsDataURL(file);
  });
}

let themeEditingTarget: Theme | null = null;
let customBgSourceMode: 'preset' | 'file' | 'url' = 'preset';

function createThemeLiveMockup(theme: Theme): HTMLElement {
  const c = theme.colors;
  const wrap = el('div', {
    style: `border: 1px solid ${c.border}; border-radius: 10px; overflow: hidden; background: ${c.bg}; box-shadow: 0 8px 30px rgba(0,0,0,0.35); font-size: 11px; display: flex; flex-direction: column;`
  }, []);

  const titlebar = el('div', {
    style: `display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: ${c.bg2}; border-bottom: 1px solid ${c.border};`
  }, [
    el('div', { style: 'display: flex; align-items: center; gap: 8px;' }, [
      el('div', { style: `width: 9px; height: 9px; border-radius: 50%; background: ${c.primary};` }, []),
      el('span', { style: `font-size: 11px; font-weight: 700; color: ${c.fg};` }, [document.createTextNode(theme.name || 'Theme Preview')])
    ]),
    el('div', { style: 'display: flex; gap: 5px;' }, [
      el('div', { style: `width: 8px; height: 8px; border-radius: 50%; background: ${c.muted}; opacity: 0.35;` }, []),
      el('div', { style: `width: 8px; height: 8px; border-radius: 50%; background: ${c.muted}; opacity: 0.35;` }, [])
    ])
  ]);
  wrap.appendChild(titlebar);

  const body = el('div', { style: 'display: flex; min-height: 240px;' }, []);

  const sidebar = el('div', {
    style: `width: 88px; background: ${c.bg2}; border-right: 1px solid ${c.border}; padding: 10px 8px; display: flex; flex-direction: column; gap: 6px;`
  }, [
    el('div', {
      style: `padding: 6px 8px; border-radius: 5px; background: ${c.primaryDim || (c.primary + '28')}; color: ${c.primary}; font-weight: 700; font-size: 10.5px;`
    }, [document.createTextNode('Accounts')]),
    el('div', {
      style: `padding: 6px 8px; border-radius: 5px; color: ${c.muted}; font-size: 10.5px;`
    }, [document.createTextNode('Appearance')]),
    el('div', {
      style: `padding: 6px 8px; border-radius: 5px; color: ${c.muted}; font-size: 10.5px;`
    }, [document.createTextNode('Settings')])
  ]);
  body.appendChild(sidebar);

  const main = el('div', {
    style: `flex: 1; padding: 14px; display: flex; flex-direction: column; gap: 10px; background: ${c.bg};`
  }, [
    el('div', { style: 'display: flex; align-items: center; justify-content: space-between;' }, [
      el('span', { style: `font-size: 12px; font-weight: 700; color: ${c.fg};` }, [document.createTextNode('Account Manager')]),
      el('span', {
        style: `font-size: 10px; padding: 4px 10px; border-radius: 5px; background: ${c.primary}; color: #08101f; font-weight: 700; box-shadow: 0 1px 6px rgba(0,0,0,0.2);`
      }, [document.createTextNode('+ Add Account')])
    ]),
    el('div', {
      style: `background: ${c.card}; border: 1px solid ${c.border}; border-radius: 7px; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between;`
    }, [
      el('div', { style: 'display: flex; align-items: center; gap: 9px;' }, [
        el('div', {
          style: `width: 22px; height: 22px; border-radius: 50%; background: ${c.primary}; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 9.5px; font-weight: 700;`
        }, [document.createTextNode('M')]),
        el('div', {}, [
          el('div', { style: `font-size: 11px; font-weight: 600; color: ${c.fg}; line-height: 1.1;` }, [document.createTextNode('MainAccount')]),
          el('div', { style: `font-size: 9px; color: ${c.muted}; margin-top: 2px;` }, [document.createTextNode('@roblox_main')])
        ])
      ]),
      el('span', {
        style: `font-size: 9px; padding: 2px 7px; border-radius: 4px; background: ${c.accent}24; color: ${c.accent}; font-weight: 700;`
      }, [document.createTextNode('Ready')])
    ]),
    el('div', {
      style: `background: ${c.cardAlt || c.hoverBg || c.card}; border: 1px solid ${c.primary}; border-radius: 7px; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between;`
    }, [
      el('div', { style: 'display: flex; align-items: center; gap: 9px;' }, [
        el('div', {
          style: `width: 22px; height: 22px; border-radius: 50%; background: ${c.border}; display: flex; align-items: center; justify-content: center; color: ${c.fg}; font-size: 9.5px; font-weight: 700;`
        }, [document.createTextNode('A')]),
        el('div', {}, [
          el('div', { style: `font-size: 11px; font-weight: 600; color: ${c.fg}; line-height: 1.1;` }, [document.createTextNode('AltAccount')]),
          el('div', { style: `font-size: 9px; color: ${c.muted}; margin-top: 2px;` }, [document.createTextNode('Selected row state')])
        ])
      ]),
      el('span', {
        style: `font-size: 9px; padding: 2px 7px; border-radius: 4px; background: ${c.primaryDim || (c.primary + '28')}; color: ${c.primary}; font-weight: 700;`
      }, [document.createTextNode('Active')])
    ])
  ]);
  body.appendChild(main);
  wrap.appendChild(body);

  return wrap;
}

function renderCustomThemeStudio(inner: HTMLElement): void {
  const isEditing = Boolean(themeEditingTarget);
  const baseTheme = themeEditingTarget || getCurrentTheme();

  const draftTheme: Theme = {
    id: isEditing ? themeEditingTarget!.id : ('custom-' + Date.now().toString(36)),
    name: isEditing ? themeEditingTarget!.name : 'My Custom Theme',
    category: 'Custom',
    description: isEditing ? themeEditingTarget!.description : 'Custom theme',
    author: 'User',
    isCustom: true,
    colors: { ...baseTheme.colors },
    accentSwatches: [...baseTheme.accentSwatches]
  };

  const header = el('div', { class: 'theme-studio-header' }, [
    el('div', {}, [
      el('button', { class: 'theme-studio-back-btn', type: 'button' }, [
        el('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', width: '13', height: '13' }, [
          el('polyline', { points: '15 18 9 12 15 6' }, [])
        ]),
        document.createTextNode('Back to Appearance')
      ]),
      el('h2', { style: 'margin: 10px 0 3px 0;' }, [
        document.createTextNode(isEditing ? `Edit: ${draftTheme.name}` : 'Theme Creator')
      ])
    ]),
    el('div', { style: 'display:flex;align-items:center;gap:8px;' }, [
      (() => {
        const cancelBtn = el('button', { class: 'btn btn-secondary', type: 'button' }, [document.createTextNode('Cancel')]);
        cancelBtn.addEventListener('click', () => {
          themeEditingTarget = null;
          state.settingsTab = 'appearance';
          renderSettingsView();
        });
        return cancelBtn;
      })(),
      (() => {
        const saveBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [
          document.createTextNode('Save Theme')
        ]);
        saveBtn.addEventListener('click', () => {
          const nameInput = document.getElementById('studio-theme-name') as HTMLInputElement | null;
          draftTheme.name = nameInput?.value.trim() || 'My Custom Theme';
          draftTheme.isCustom = true;
          draftTheme.accentSwatches = [draftTheme.colors.primary, draftTheme.colors.accent, '#4f8ef7', '#34d399', '#f472b6', '#f59e0b'];

          saveCustomTheme(draftTheme);
          state.settings.selectedTheme = draftTheme.id;
          state.settings.accentColor = draftTheme.colors.primary;
          updateSetting('selectedTheme', draftTheme.id);
          updateSetting('accentColor', draftTheme.colors.primary);
          try {
            updateSetting('customThemes' as any, getCustomThemes() as any);
          } catch (e) {
          }

          applyTheme(draftTheme.id, draftTheme.colors.primary);
          toast(`Theme "${draftTheme.name}" saved!`, 'success');

          themeEditingTarget = null;
          state.settingsTab = 'appearance';
          renderSettingsView();
        });
        return saveBtn;
      })()
    ])
  ]);

  (header.querySelector('.theme-studio-back-btn') as HTMLElement)?.addEventListener('click', () => {
    themeEditingTarget = null;
    state.settingsTab = 'appearance';
    renderSettingsView();
  });

  inner.appendChild(header);

  const topCard = el('div', { class: 'studio-top-bar' }, [
    el('div', { class: 'studio-input-group' }, [
      el('label', { class: 'studio-input-label' }, [document.createTextNode('Theme Name')]),
      (() => {
        const inp = el('input', {
          type: 'text',
          id: 'studio-theme-name',
          value: draftTheme.name,
          placeholder: 'Enter theme name...'
        }, []) as HTMLInputElement;
        inp.addEventListener('input', () => {
          draftTheme.name = inp.value.trim() || 'My Theme';
          refreshMockup();
        });
        return inp;
      })()
    ]),
    el('div', { class: 'studio-input-group' }, [
      el('label', { class: 'studio-input-label' }, [document.createTextNode('Start from Existing Theme')]),
      (() => {
        const baseSel = el('select', { style: 'width:100%;' }, []) as HTMLSelectElement;
        const defaultOpt = el('option', { value: '' }, [document.createTextNode('Load colors from theme...')]);
        baseSel.appendChild(defaultOpt);
        getAllThemes().forEach(t => {
          const opt = el('option', { value: t.id }, [document.createTextNode(t.name)]);
          baseSel.appendChild(opt);
        });
        baseSel.addEventListener('change', () => {
          const chosen = getTheme(baseSel.value);
          if (chosen) {
            draftTheme.colors = { ...chosen.colors };
            updateStudioTokens();
          }
        });
        return baseSel;
      })()
    ])
  ]);
  inner.appendChild(topCard);

  const studioGrid = el('div', { class: 'theme-studio-grid' }, []);

  const leftCol = el('div', { style: 'display:flex;flex-direction:column;gap:14px;' }, []);

  const tokensCard = el('div', { class: 'settings-card', style: 'padding:16px;' }, [
    el('div', { style: 'font-size:13px;font-weight:700;margin-bottom:12px;' }, [document.createTextNode('Colors')])
  ]);

  const editableTokens: Array<{ key: keyof typeof draftTheme.colors; title: string; desc: string }> = [
    { key: 'bg', title: 'Main Background', desc: 'App window & main backdrop' },
    { key: 'card', title: 'Cards & Panels', desc: 'Card and container background' },
    { key: 'bg2', title: 'Sidebar & Surface', desc: 'Sidebar navigation and inputs' },
    { key: 'primary', title: 'Primary Accent', desc: 'Buttons, active indicators, and links' },
    { key: 'accent', title: 'Secondary Accent', desc: 'Status pills and secondary highlights' },
    { key: 'fg', title: 'Text Color', desc: 'Headings and primary text' },
    { key: 'muted', title: 'Muted Text', desc: 'Subtitles and secondary labels' },
    { key: 'border', title: 'Borders', desc: 'Card borders, outlines, and dividers' },
    { key: 'cardAlt', title: 'Hover & Selected', desc: 'Selected cards and hover row state' }
  ];

  const pickersWrap = el('div', { class: 'studio-colors-list' }, []);
  tokensCard.appendChild(pickersWrap);
  leftCol.appendChild(tokensCard);
  studioGrid.appendChild(leftCol);

  const rightCol = el('div', { class: 'theme-studio-preview-card' }, []);
  const previewCard = el('div', { class: 'settings-card', style: 'padding:16px;display:flex;flex-direction:column;gap:12px;' }, [
    el('div', { style: 'display:flex;align-items:center;justify-content:space-between;' }, [
      el('span', { style: 'font-size:13px;font-weight:700;' }, [document.createTextNode('Live Preview')])
    ])
  ]);

  const mockupContainer = el('div', { id: 'studio-live-mockup' }, []);
  mockupContainer.appendChild(createThemeLiveMockup(draftTheme));
  previewCard.appendChild(mockupContainer);

  rightCol.appendChild(previewCard);

  if (isEditing) {
    const dangerCard = el('div', { class: 'settings-card danger', style: 'padding:14px;display:flex;align-items:center;justify-content:space-between;' }, [
      el('div', {}, [
        el('div', { style: 'font-size:12px;font-weight:700;color:var(--danger);' }, [document.createTextNode('Delete Theme')]),
        el('div', { style: 'font-size:11px;color:var(--muted);' }, [document.createTextNode('Delete this custom theme permanently')])
      ]),
      (() => {
        const delBtn = el('button', { class: 'btn btn-danger', type: 'button' }, [document.createTextNode('Delete Theme')]);
        let confirmPending = false;
        delBtn.addEventListener('click', () => {
          if (!confirmPending) {
            confirmPending = true;
            delBtn.textContent = 'Click to Confirm';
            setTimeout(() => {
              confirmPending = false;
              delBtn.textContent = 'Delete Theme';
            }, 3000);
            return;
          }
          if (state.settings.selectedTheme === draftTheme.id) {
            state.settings.selectedTheme = 'default-dark';
            applyTheme('default-dark', state.settings.accentColor);
            updateSetting('selectedTheme', 'default-dark');
          }
          deleteCustomTheme(draftTheme.id);
          try {
            updateSetting('customThemes' as any, getCustomThemes() as any);
          } catch (e) {
          }
          themeEditingTarget = null;
          state.settingsTab = 'appearance';
          renderSettingsView();
        });
        return delBtn;
      })()
    ]);
    rightCol.appendChild(dangerCard);
  }

  studioGrid.appendChild(rightCol);
  inner.appendChild(studioGrid);

  const updateStudioTokens = () => {
    pickersWrap.innerHTML = '';
    editableTokens.forEach(token => {
      const row = el('div', { class: 'studio-color-row' }, []);
      const val = draftTheme.colors[token.key];

      const meta = el('div', { class: 'studio-color-meta' }, [
        el('span', { class: 'studio-color-title' }, [document.createTextNode(token.title)]),
        el('span', { class: 'studio-color-desc' }, [document.createTextNode(token.desc)])
      ]);
      row.appendChild(meta);

      const controls = el('div', { class: 'studio-color-controls' }, []);

      const swatch = el('label', {
        class: 'studio-color-swatch',
        style: `background: ${val};`
      }, []);
      const colorInp = el('input', {
        type: 'color',
        id: `studio-color-${token.key}`,
        value: val
      }, []) as HTMLInputElement;
      swatch.appendChild(colorInp);
      controls.appendChild(swatch);

      const hexInp = el('input', {
        type: 'text',
        class: 'studio-hex-field',
        id: `studio-hex-${token.key}`,
        value: val,
        spellcheck: false
      }, []) as HTMLInputElement;
      controls.appendChild(hexInp);

      row.appendChild(controls);
      pickersWrap.appendChild(row);

      colorInp.addEventListener('input', () => {
        swatch.style.background = colorInp.value;
        hexInp.value = colorInp.value;
        draftTheme.colors[token.key] = colorInp.value;
        refreshMockup();
      });

      hexInp.addEventListener('input', () => {
        let textVal = hexInp.value.trim();
        if (!textVal.startsWith('#') && /^[0-9a-fA-F]{6}$/.test(textVal)) {
          textVal = '#' + textVal;
          hexInp.value = textVal;
        }
        if (/^#[0-9a-fA-F]{6}$/.test(textVal)) {
          swatch.style.background = textVal;
          colorInp.value = textVal;
          draftTheme.colors[token.key] = textVal;
          refreshMockup();
        }
      });
    });

    refreshMockup();
  };

  const refreshMockup = () => {
    draftTheme.colors.primaryDim = draftTheme.colors.primary + '28';
    draftTheme.colors.borderSoft = draftTheme.colors.border;
    draftTheme.colors.fg2 = draftTheme.colors.fg;
    draftTheme.colors.fg3 = draftTheme.colors.muted;
    draftTheme.colors.hoverBg = draftTheme.colors.cardAlt;
    draftTheme.colors.listBg = draftTheme.colors.bg;
    draftTheme.colors.accentAlt = draftTheme.colors.accent;
    draftTheme.colors.listSelect = draftTheme.colors.primary + '33';

    mockupContainer.innerHTML = '';
    mockupContainer.appendChild(createThemeLiveMockup(draftTheme));
  };

  updateStudioTokens();
}

function showThemeImportModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';

  const modal = document.createElement('div');
  modal.className = 'modal theme-share-dialog';

  modal.innerHTML = `
    <div class="modal-header">
      <h3>Import Custom Theme</h3>
      <button class="modal-close" id="theme-io-close">✕</button>
    </div>
    <div class="modal-body">
      <div class="theme-share-tabs">
        <button type="button" class="theme-share-tab-btn active" id="tab-btn-file">File Upload</button>
        <button type="button" class="theme-share-tab-btn" id="tab-btn-paste">Paste JSON</button>
      </div>

      <div id="import-panel-file">
        <div class="theme-dropzone" id="theme-drop-area">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32" style="margin-bottom:8px;color:var(--primary);"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          <div style="font-size:13px;font-weight:600;margin-bottom:4px;">Drag and drop theme JSON file here</div>
          <div style="font-size:11px;color:var(--muted);margin-bottom:10px;">or click to browse your files</div>
          <button type="button" class="btn btn-secondary" id="browse-theme-file-btn">Select .json File</button>
          <input type="file" id="theme-file-input" accept=".json,application/json" style="display:none;" />
        </div>
      </div>

      <div id="import-panel-paste" style="display:none;">
        <p style="font-size:12px;color:var(--muted);margin-bottom:8px;">
          Paste valid theme JSON text directly below:
        </p>
        <textarea class="theme-json-textarea" id="theme-import-code" placeholder="{\n  &quot;name&quot;: &quot;Awesome Theme&quot;,\n  &quot;colors&quot;: { ... }\n}"></textarea>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" id="theme-io-cancel">Cancel</button>
      <button class="btn btn-primary" id="theme-io-import-btn">Import & Apply</button>
    </div>
  `;

  overlay.appendChild(modal);
  app.appendChild(overlay);

  const closeModal = () => overlay.remove();
  document.getElementById('theme-io-close')?.addEventListener('click', closeModal);
  document.getElementById('theme-io-cancel')?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });

  const tabFile = document.getElementById('tab-btn-file');
  const tabPaste = document.getElementById('tab-btn-paste');
  const panelFile = document.getElementById('import-panel-file');
  const panelPaste = document.getElementById('import-panel-paste');

  tabFile?.addEventListener('click', () => {
    tabFile.classList.add('active');
    tabPaste?.classList.remove('active');
    if (panelFile) panelFile.style.display = 'block';
    if (panelPaste) panelPaste.style.display = 'none';
  });

  tabPaste?.addEventListener('click', () => {
    tabPaste.classList.add('active');
    tabFile?.classList.remove('active');
    if (panelPaste) panelPaste.style.display = 'block';
    if (panelFile) panelFile.style.display = 'none';
  });

  const fileInp = document.getElementById('theme-file-input') as HTMLInputElement | null;
  const browseBtn = document.getElementById('browse-theme-file-btn');
  const dropArea = document.getElementById('theme-drop-area');

  browseBtn?.addEventListener('click', () => fileInp?.click());
  dropArea?.addEventListener('click', (e) => {
    if (e.target !== browseBtn) fileInp?.click();
  });

  dropArea?.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropArea.classList.add('dragover');
  });

  dropArea?.addEventListener('dragleave', () => {
    dropArea.classList.remove('dragover');
  });

  const processFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const content = reader.result as string;
        const imported = importThemeJson(content);
        const importedAccent = imported.accentSwatches?.[0] || imported.colors.primary;
        state.settings.selectedTheme = imported.id;
        state.settings.accentColor = importedAccent;
        applyTheme(imported.id, importedAccent);
        apiService.updateSettings({ selectedTheme: imported.id, accentColor: importedAccent }).catch(() => { });
        try {
          updateSetting('customThemes' as any, getCustomThemes() as any);
        } catch (e) {
        }
        toast(`Theme "${imported.name}" imported successfully!`, 'success');
        closeModal();
        renderSettingsView();
      } catch (err: any) {
        toast('Failed to import theme: ' + (err.message || 'Invalid format'), 'error');
      }
    };
    reader.readAsText(file);
  };

  dropArea?.addEventListener('drop', (e) => {
    e.preventDefault();
    dropArea.classList.remove('dragover');
    if (e.dataTransfer?.files?.[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  });

  fileInp?.addEventListener('change', () => {
    if (fileInp.files?.[0]) {
      processFile(fileInp.files[0]);
    }
  });

  document.getElementById('theme-io-import-btn')?.addEventListener('click', () => {
    const codeInp = document.getElementById('theme-import-code') as HTMLTextAreaElement | null;
    const text = codeInp?.value.trim();
    if (!text) {
      toast('Please paste theme JSON or upload a file', 'info');
      return;
    }
    try {
      const imported = importThemeJson(text);
      const importedAccent = imported.accentSwatches?.[0] || imported.colors.primary;
      state.settings.selectedTheme = imported.id;
      state.settings.accentColor = importedAccent;
      applyTheme(imported.id, importedAccent);
      apiService.updateSettings({ selectedTheme: imported.id, accentColor: importedAccent }).catch(() => { });
      try {
        updateSetting('customThemes' as any, getCustomThemes() as any);
      } catch (e) {
      }
      toast(`Theme "${imported.name}" imported successfully!`, 'success');
      closeModal();
      renderSettingsView();
    } catch (err: any) {
      toast('Theme import error: ' + (err.message || 'Invalid format'), 'error');
    }
  });
}

function renderThemesTab(inner: HTMLElement): void {
  inner.appendChild(el('h2', {}, [document.createTextNode('Appearance')]));
  inner.appendChild(el('p', {}, [document.createTextNode('Customize colors, themes, wallpaper, and transparency.')]));

  const currentId = state.settings.selectedTheme || getCurrentThemeId() || 'default-dark';
  const currentTheme = getTheme(currentId) || THEMES['default-dark'];

  const activeSec = el('div', { class: 'settings-section' }, []);
  const activeCard = el('div', { class: 'settings-card', style: 'padding: 12px 16px; margin-bottom: 12px;' }, [
    el('div', { style: 'display: flex; align-items: center; justify-content: space-between;' }, [
      el('div', {}, [
        el('div', { style: 'display: flex; align-items: center; gap: 8px;' }, [
          el('span', { style: 'font-size: 14px; font-weight: 700; color: var(--fg);' }, [document.createTextNode(currentTheme.name)])
        ]),
        el('div', { style: 'font-size: 11px; color: var(--muted); margin-top: 3px;' }, [
          document.createTextNode(currentTheme.description + (currentTheme.author ? ` • By ${currentTheme.author}` : ''))
        ])
      ]),
      el('div', { style: 'display: flex; align-items: center; gap: 10px;' }, [
        currentTheme.isCustom ? (() => {
          const editBtn = el('button', { class: 'theme-mini-btn', type: 'button' }, [document.createTextNode('Edit in Studio')]);
          editBtn.addEventListener('click', () => {
            themeEditingTarget = currentTheme;
            state.settingsTab = 'custom-theme';
            renderSettingsView();
          });
          return editBtn;
        })() : document.createTextNode(''),
        el('div', { class: 'theme-palette-dots' }, [
          el('span', { class: 'theme-color-dot', style: `background: ${currentTheme.colors.bg};` }, []),
          el('span', { class: 'theme-color-dot', style: `background: ${currentTheme.colors.card};` }, []),
          el('span', { class: 'theme-color-dot', style: `background: ${currentTheme.colors.primary};` }, [])
        ])
      ])
    ])
  ]);
  activeSec.appendChild(activeCard);
  inner.appendChild(activeSec);

  const accentSec = el('div', { class: 'settings-section' }, []);
  accentSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Accent Color')]));
  const accentCard = el('div', { class: 'settings-card' }, []);
  const accentRow = el('div', { class: 'setting-row', style: 'border-bottom:none;' }, []);
  const accentText = el('div', {}, [
    el('div', { class: 'setting-label' }, [document.createTextNode('Accent Color')]),
    el('div', { class: 'setting-desc' }, [document.createTextNode('Color used for buttons, links, and highlights')])
  ]);
  accentRow.appendChild(accentText);

  const swWrap = el('div', { class: 'accent-swatches-group' }, []);
  const themePresets = [currentTheme.colors.primary, '#4f8ef7', '#34d399', '#f472b6', '#f59e0b', '#a78bfa', '#00f0ff'];
  themePresets.forEach(color => {
    const active = state.settings.accentColor ? state.settings.accentColor.toLowerCase() === color.toLowerCase() : color === currentTheme.colors.primary;
    const dot = el('div', {
      class: 'accent-circle' + (active ? ' active' : ''),
      style: `background: ${color};`
    }, []);
    dot.addEventListener('click', () => {
      state.settings.accentColor = color;
      applyTheme(currentId, color);
      updateSetting('accentColor', color);
    });
    swWrap.appendChild(dot);
  });

  const currentAccent = state.settings.accentColor;
  const isCustomActive = Boolean(currentAccent && !themePresets.some(c => c.toLowerCase() === currentAccent.toLowerCase()));
  const customWrap = el('div', { class: 'custom-color-wrap' }, []);
  const customCircle = el('div', {
    class: 'custom-color-circle' + (isCustomActive ? ' active' : ''),
    title: 'Custom accent color'
  }, []);
  if (isCustomActive && currentAccent) {
    customCircle.style.setProperty('--custom-accent-color', currentAccent);
  }
  const colorInput = el('input', {
    type: 'color',
    class: 'custom-color-input',
    value: state.settings.accentColor || currentTheme.colors.primary
  }, []) as HTMLInputElement;
  colorInput.addEventListener('input', (e) => {
    const val = (e.target as HTMLInputElement).value;
    state.settings.accentColor = val;
    applyTheme(currentId, val);
    swWrap.querySelectorAll('.accent-circle').forEach(c => c.classList.remove('active'));
    customCircle.classList.add('active');
    customCircle.style.setProperty('--custom-accent-color', val);
  });
  colorInput.addEventListener('change', (e) => {
    const val = (e.target as HTMLInputElement).value;
    updateSetting('accentColor', val);
  });
  customWrap.appendChild(customCircle);
  customWrap.appendChild(colorInput);
  swWrap.appendChild(customWrap);

  accentRow.appendChild(swWrap);
  accentCard.appendChild(accentRow);
  accentSec.appendChild(accentCard);
  inner.appendChild(accentSec);

  const builtInSec = el('div', { class: 'settings-section' }, []);
  const builtInThemesList = Object.values(THEMES);

  const builtInHeader = el('div', { class: 'theme-gallery-toolbar' }, [
    el('div', { class: 'settings-section-title', style: 'margin:0;' }, [
      document.createTextNode('Built-in Themes')
    ])
  ]);
  builtInSec.appendChild(builtInHeader);

  const builtInGrid = el('div', { class: 'theme-grid' }, []);
  builtInThemesList.forEach(theme => {
    const isSelected = theme.id === currentId;
    const card = el('div', {
      class: 'theme-card' + (isSelected ? ' selected' : '')
    }, []);

    card.appendChild(createThemePreviewBox(theme));

    const header = el('div', { class: 'theme-card-header' }, [
      el('span', { class: 'theme-card-title' }, [document.createTextNode(theme.name)])
    ]);
    card.appendChild(header);

    card.appendChild(el('div', { class: 'theme-card-desc' }, [document.createTextNode(theme.description)]));

    const dots = el('div', { class: 'theme-palette-dots' }, [
      el('span', { class: 'theme-color-dot', style: `background: ${theme.colors.bg};` }, []),
      el('span', { class: 'theme-color-dot', style: `background: ${theme.colors.card};` }, []),
      el('span', { class: 'theme-color-dot', style: `background: ${theme.colors.primary};` }, [])
    ]);
    card.appendChild(dots);

    if (isSelected) {
      card.appendChild(el('div', { class: 'theme-active-badge' }, [
        el('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '3', width: '11', height: '11' }, [
          el('polyline', { points: '20 6 9 17 4 12' }, [])
        ])
      ]));
    }

    card.addEventListener('click', () => {
      const defaultAccent = theme.accentSwatches?.[0] || theme.colors.primary;
      state.settings.selectedTheme = theme.id;
      state.settings.accentColor = defaultAccent;
      applyTheme(theme.id, defaultAccent);
      apiService.updateSettings({ selectedTheme: theme.id, accentColor: defaultAccent }).catch(() => { });
      toast(`Theme set to ${theme.name}`, 'success');
      renderSettingsView();
    });

    builtInGrid.appendChild(card);
  });
  builtInSec.appendChild(builtInGrid);
  inner.appendChild(builtInSec);

  const customThemesList = getCustomThemes();
  const customThemesSec = el('div', { class: 'settings-section' }, []);

  const customHeader = el('div', { class: 'theme-gallery-toolbar' }, [
    el('div', { class: 'settings-section-title', style: 'margin:0;' }, [document.createTextNode('Custom Themes')])
  ]);
  customThemesSec.appendChild(customHeader);

  if (customThemesList.length === 0) {
    const emptyCard = el('div', { class: 'theme-empty-card' }, [
      el('div', { style: 'font-size:13px;font-weight:600;color:var(--fg);' }, [document.createTextNode('No custom themes')]),
      el('div', { style: 'font-size:11px;color:var(--muted);max-width:380px;' }, [
        document.createTextNode('Create your own theme or import one from a file.')
      ]),
      el('div', { style: 'display:flex;gap:8px;margin-top:6px;' }, [
        (() => {
          const openBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [
            document.createTextNode('Open Theme Creator')
          ]);
          openBtn.addEventListener('click', () => {
            themeEditingTarget = null;
            state.settingsTab = 'custom-theme';
            renderSettingsView();
          });
          return openBtn;
        })(),
        (() => {
          const importBtn = el('button', { class: 'btn btn-secondary', type: 'button' }, [
            document.createTextNode('Import Theme')
          ]);
          importBtn.addEventListener('click', () => showThemeImportModal());
          return importBtn;
        })()
      ])
    ]);
    customThemesSec.appendChild(emptyCard);
  } else {
    const customGrid = el('div', { class: 'theme-grid' }, []);
    customThemesList.forEach(theme => {
      const isSelected = theme.id === currentId;
      const card = el('div', {
        class: 'theme-card' + (isSelected ? ' selected' : '')
      }, []);

      card.appendChild(createThemePreviewBox(theme));

      const ch = el('div', { class: 'theme-card-header' }, [
        el('span', { class: 'theme-card-title' }, [document.createTextNode(theme.name)])
      ]);
      card.appendChild(ch);

      if (theme.author) {
        card.appendChild(el('div', { class: 'theme-card-author' }, [document.createTextNode(`By ${theme.author}`)]));
      }

      card.appendChild(el('div', { class: 'theme-card-desc' }, [document.createTextNode(theme.description)]));

      const dots = el('div', { class: 'theme-palette-dots' }, [
        el('span', { class: 'theme-color-dot', style: `background: ${theme.colors.bg};` }, []),
        el('span', { class: 'theme-color-dot', style: `background: ${theme.colors.card};` }, []),
        el('span', { class: 'theme-color-dot', style: `background: ${theme.colors.primary};` }, [])
      ]);
      card.appendChild(dots);

      if (isSelected) {
        card.appendChild(el('div', { class: 'theme-active-badge' }, [
          el('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '3', width: '11', height: '11' }, [
            el('polyline', { points: '20 6 9 17 4 12' }, [])
          ])
        ]));
      }

      const actionsRow = el('div', { class: 'theme-card-actions' }, []);
      const editBtn = el('button', { class: 'theme-mini-btn', type: 'button' }, [document.createTextNode('Edit in Studio')]);
      editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        themeEditingTarget = theme;
        state.settingsTab = 'custom-theme';
        renderSettingsView();
      });
      actionsRow.appendChild(editBtn);

      const delBtn = el('button', { class: 'theme-mini-btn danger', type: 'button' }, [document.createTextNode('Delete')]);
      let confirmDel = false;
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!confirmDel) {
          confirmDel = true;
          delBtn.textContent = 'Confirm?';
          setTimeout(() => {
            confirmDel = false;
            delBtn.textContent = 'Delete';
          }, 3000);
          return;
        }
        if (state.settings.selectedTheme === theme.id) {
          const fallbackTheme = getTheme('default-dark');
          const fallbackAccent = fallbackTheme.accentSwatches?.[0] || fallbackTheme.colors.primary;
          state.settings.selectedTheme = 'default-dark';
          state.settings.accentColor = fallbackAccent;
          applyTheme('default-dark', fallbackAccent);
          apiService.updateSettings({ selectedTheme: 'default-dark', accentColor: fallbackAccent }).catch(() => { });
        }
        deleteCustomTheme(theme.id);
        try {
          updateSetting('customThemes' as any, getCustomThemes() as any);
        } catch (e) {
        }
        renderSettingsView();
      });
      actionsRow.appendChild(delBtn);
      card.appendChild(actionsRow);

      card.addEventListener('click', () => {
        const defaultAccent = theme.accentSwatches?.[0] || theme.colors.primary;
        state.settings.selectedTheme = theme.id;
        state.settings.accentColor = defaultAccent;
        applyTheme(theme.id, defaultAccent);
        apiService.updateSettings({ selectedTheme: theme.id, accentColor: defaultAccent }).catch(() => { });
        toast(`Theme set to ${theme.name}`, 'success');
        renderSettingsView();
      });

      customGrid.appendChild(card);
    });

    const addCard = el('div', {
      class: 'theme-card',
      style: 'border: 1px dashed var(--border); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; min-height: 140px; cursor: pointer; background: var(--bg-2);'
    }, [
      el('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', width: '22', height: '22', style: 'color:var(--primary);' }, [
        el('path', { d: 'M12 5v14M5 12h14' }, [])
      ]),
      el('span', { style: 'font-size:12px;font-weight:600;color:var(--fg);' }, [document.createTextNode('Open Theme Creator')]),
      (() => {
        const importSubBtn = el('button', { class: 'theme-mini-btn', type: 'button', style: 'margin-top:4px;' }, [
          document.createTextNode('Import Theme')
        ]);
        importSubBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          showThemeImportModal();
        });
        return importSubBtn;
      })()
    ]);
    addCard.addEventListener('click', () => {
      themeEditingTarget = null;
      state.settingsTab = 'custom-theme';
      renderSettingsView();
    });
    customGrid.appendChild(addCard);

    customThemesSec.appendChild(customGrid);
  }
  inner.appendChild(customThemesSec);

  const wallpaperSec = el('div', { class: 'settings-section' }, []);
  wallpaperSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Wallpaper')]));

  const wallpaperCard = el('div', { class: 'settings-card', style: 'padding:18px;display:flex;flex-direction:column;gap:16px;' }, []);
  const bgSettings = getBackgroundSettings();

  const isBgActive = bgSettings.enabled && (
    (bgSettings.type === 'preset' && bgSettings.presetId) ||
    (bgSettings.type === 'custom' && bgSettings.customImage) ||
    (bgSettings.type === 'url' && bgSettings.customImage)
  );

  if (isBgActive) {
    const stage = el('div', { class: 'wallpaper-stage' }, []);

    let activeBgStyle = '';
    if (bgSettings.type === 'preset') {
      const p = BACKGROUND_PRESETS.find(x => x.id === bgSettings.presetId) || BACKGROUND_PRESETS[0];
      activeBgStyle = p.previewGradient;
    } else if (bgSettings.customImage) {
      activeBgStyle = `url("${bgSettings.customImage}")`;
    }

    const stageSize = (bgSettings.fit === 'repeat' || bgSettings.fit === 'center') ? 'auto' : (bgSettings.fit || 'cover');
    const stagePos = bgSettings.fit === 'repeat' ? 'top left' : 'center';
    const stageRepeat = bgSettings.fit === 'repeat' ? 'repeat' : 'no-repeat';

    const stageBg = el('div', {
      class: 'wallpaper-stage-bg',
      style: `background:${activeBgStyle};background-size:${stageSize};background-position:${stagePos};background-repeat:${stageRepeat};opacity:${(bgSettings.opacity ?? 100) / 100};filter:${bgSettings.blur > 0 ? `blur(${bgSettings.blur}px)` : 'none'};`
    }, []);
    stage.appendChild(stageBg);

    const stageTop = el('div', { class: 'wallpaper-stage-content' }, [
      el('span', {
        style: 'font-size:11px;font-weight:600;background:rgba(0,0,0,0.65);padding:3px 10px;border-radius:5px;color:#fff;backdrop-filter:blur(6px);display:flex;align-items:center;gap:6px;'
      }, [
        el('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '3', width: '11', height: '11' }, [
          el('polyline', { points: '20 6 9 17 4 12' }, [])
        ]),
        document.createTextNode('Active Wallpaper')
      ]),
      (() => {
        const removeBtn = el('button', { class: 'theme-mini-btn danger', type: 'button', style: 'backdrop-filter:blur(6px);' }, [
          document.createTextNode('Remove Wallpaper')
        ]);
        removeBtn.addEventListener('click', () => {
          bgSettings.enabled = false;
          bgSettings.type = 'none';
          bgSettings.customImage = '';
          saveBackgroundSettings(bgSettings);
          toast('Background removed', 'info');
          renderSettingsView();
        });
        return removeBtn;
      })()
    ]);
    stage.appendChild(stageTop);

    const stageBottom = el('div', { style: 'position:relative;z-index:1;font-size:11px;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,0.9);background:rgba(0,0,0,0.5);padding:4px 10px;border-radius:5px;width:fit-content;' }, [
      document.createTextNode(bgSettings.type === 'preset' ? `Preset: ${BACKGROUND_PRESETS.find(x => x.id === bgSettings.presetId)?.name || 'Pattern'}` : 'Custom Image')
    ]);
    stage.appendChild(stageBottom);

    wallpaperCard.appendChild(stage);
  }

  const sourceSelectRow = el('div', { style: 'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;' }, [
    el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Wallpaper Source')]),
      el('div', { class: 'setting-desc' }, [document.createTextNode('Pick a preset pattern, upload an image file, or enter an image link.')])
    ]),
    (() => {
      const sourceTabs = el('div', { class: 'theme-source-tabs' }, []);
      const modes: Array<{ id: 'preset' | 'file' | 'url'; label: string }> = [
        { id: 'preset', label: 'Presets' },
        { id: 'file', label: 'Upload Image' },
        { id: 'url', label: 'Image URL' }
      ];

      modes.forEach(m => {
        const btn = el('button', {
          type: 'button',
          class: 'theme-source-tab-btn' + (customBgSourceMode === m.id ? ' active' : '')
        }, [document.createTextNode(m.label)]);
        btn.addEventListener('click', () => {
          customBgSourceMode = m.id;
          renderSettingsView();
        });
        sourceTabs.appendChild(btn);
      });
      return sourceTabs;
    })()
  ]);
  wallpaperCard.appendChild(sourceSelectRow);

  if (customBgSourceMode === 'preset') {
    const presetsBox = el('div', { style: 'display:flex;flex-direction:column;gap:10px;' }, []);
    const presetGrid = el('div', { class: 'bg-presets-grid' }, []);
    BACKGROUND_PRESETS.forEach(preset => {
      const isSelected = bgSettings.enabled && bgSettings.type === 'preset' && bgSettings.presetId === preset.id;
      const card = el('div', {
        class: 'bg-preset-card' + (isSelected ? ' active' : ''),
        style: `background: ${preset.previewGradient};`
      }, [
        el('span', { class: 'bg-preset-title' }, [document.createTextNode(preset.name)])
      ]);

      card.addEventListener('click', () => {
        bgSettings.enabled = true;
        bgSettings.type = 'preset';
        bgSettings.presetId = preset.id;
        if (bgSettings.glassmorphism === 'none') {
          bgSettings.glassmorphism = 'medium';
        }
        saveBackgroundSettings(bgSettings);
        renderSettingsView();
      });

      presetGrid.appendChild(card);
    });
    presetsBox.appendChild(presetGrid);
    wallpaperCard.appendChild(presetsBox);
  }

  if (customBgSourceMode === 'file') {
    const fileArea = el('div', { style: 'display:flex;flex-direction:column;gap:12px;background:var(--bg-2);padding:16px;border-radius:8px;border:1px solid var(--border-soft);' }, []);
    const fileHeader = el('div', {}, [
      el('div', { style: 'font-size:12px;font-weight:600;' }, [document.createTextNode('Upload Image')]),
      el('div', { style: 'font-size:11px;color:var(--muted);margin-top:2px;' }, [document.createTextNode('Supports PNG, JPG, or WebP.')])
    ]);
    fileArea.appendChild(fileHeader);

    const fileInp = el('input', { type: 'file', accept: 'image/*', style: 'display:none;' }, []) as HTMLInputElement;
    fileInp.addEventListener('change', async () => {
      if (fileInp.files?.[0]) {
        const file = fileInp.files[0];
        toast('Loading image...', 'info');
        const dataUrl = await compressImage(file);
        if (dataUrl) {
          bgSettings.enabled = true;
          bgSettings.type = 'custom';
          bgSettings.customImage = dataUrl;
          if (bgSettings.glassmorphism === 'none') {
            bgSettings.glassmorphism = 'medium';
          }
          saveBackgroundSettings(bgSettings);
          toast('Wallpaper applied!', 'success');
          renderSettingsView();
        } else {
          toast('Failed to load image', 'error');
        }
      }
    });

    const fileActionsRow = el('div', { style: 'display:flex;align-items:center;gap:12px;flex-wrap:wrap;' }, []);
    const pickBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [
      document.createTextNode('Choose Image...')
    ]);
    pickBtn.addEventListener('click', () => fileInp.click());
    fileActionsRow.appendChild(pickBtn);
    fileActionsRow.appendChild(fileInp);

    if (bgSettings.enabled && bgSettings.type === 'custom' && bgSettings.customImage) {
      const activeTag = el('span', { style: 'font-size:11px;color:var(--primary);font-weight:600;' }, [
        document.createTextNode('Image loaded')
      ]);
      fileActionsRow.appendChild(activeTag);
    }

    fileArea.appendChild(fileActionsRow);
    wallpaperCard.appendChild(fileArea);
  }

  if (customBgSourceMode === 'url') {
    const urlArea = el('div', { style: 'display:flex;flex-direction:column;gap:12px;background:var(--bg-2);padding:16px;border-radius:8px;border:1px solid var(--border-soft);' }, []);
    const urlHeader = el('div', {}, [
      el('div', { style: 'font-size:12px;font-weight:600;' }, [document.createTextNode('Image URL')]),
      el('div', { style: 'font-size:11px;color:var(--muted);margin-top:2px;' }, [document.createTextNode('Paste a direct link to an image.')])
    ]);
    urlArea.appendChild(urlHeader);

    const urlRow = el('div', { style: 'display:flex;align-items:center;gap:8px;' }, []);
    const urlInput = el('input', {
      type: 'text',
      placeholder: 'https://example.com/image.png',
      value: (bgSettings.customImage?.startsWith('http') ? bgSettings.customImage : ''),
      style: 'flex:1;'
    }, []) as HTMLInputElement;

    const applyUrlBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [document.createTextNode('Apply')]);
    applyUrlBtn.addEventListener('click', () => {
      const val = urlInput.value.trim();
      if (val) {
        bgSettings.enabled = true;
        bgSettings.type = 'url';
        bgSettings.customImage = val;
        if (bgSettings.glassmorphism === 'none') {
          bgSettings.glassmorphism = 'medium';
        }
        saveBackgroundSettings(bgSettings);
        toast('Wallpaper applied!', 'success');
        renderSettingsView();
      }
    });
    urlRow.appendChild(urlInput);
    urlRow.appendChild(applyUrlBtn);
    urlArea.appendChild(urlRow);
    wallpaperCard.appendChild(urlArea);
  }

  if (bgSettings.enabled) {
    const tuningGrid = el('div', { class: 'wallpaper-tuning-grid' }, []);

    const dimmerCard = el('div', { class: 'wallpaper-control-card' }, [
      el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Brightness')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Dims the wallpaper so text is easier to read')])
      ]),
      el('div', { class: 'bg-slider-row' }, [
        el('div', { class: 'bg-slider-input-wrap' }, [
          (() => {
            const slider = el('input', {
              type: 'range',
              min: '10',
              max: '100',
              step: '5',
              value: String(bgSettings.opacity ?? 100)
            }, []) as HTMLInputElement;
            const valLabel = el('span', { class: 'bg-slider-val' }, [document.createTextNode(`${bgSettings.opacity ?? 100}%`)]);
            slider.addEventListener('input', () => {
              const v = Number(slider.value);
              valLabel.textContent = `${v}%`;
              bgSettings.opacity = v;
              applyBackground(bgSettings);
            });
            slider.addEventListener('change', () => {
              saveBackgroundSettings(bgSettings);
            });
            const wrap = el('div', { style: 'display:flex;align-items:center;gap:10px;flex:1;' }, [slider, valLabel]);
            return wrap;
          })()
        ])
      ])
    ]);
    tuningGrid.appendChild(dimmerCard);

    const blurCard = el('div', { class: 'wallpaper-control-card' }, [
      el('div', {}, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Blur')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('Blurs the wallpaper behind windows')])
      ]),
      el('div', { class: 'bg-slider-row' }, [
        el('div', { class: 'bg-slider-input-wrap' }, [
          (() => {
            const slider = el('input', {
              type: 'range',
              min: '0',
              max: '25',
              step: '1',
              value: String(bgSettings.blur ?? 0)
            }, []) as HTMLInputElement;
            const valLabel = el('span', { class: 'bg-slider-val' }, [document.createTextNode(`${bgSettings.blur ?? 0}px`)]);
            slider.addEventListener('input', () => {
              const v = Number(slider.value);
              valLabel.textContent = `${v}px`;
              bgSettings.blur = v;
              applyBackground(bgSettings);
            });
            slider.addEventListener('change', () => {
              saveBackgroundSettings(bgSettings);
            });
            const wrap = el('div', { style: 'display:flex;align-items:center;gap:10px;flex:1;' }, [slider, valLabel]);
            return wrap;
          })()
        ])
      ])
    ]);
    tuningGrid.appendChild(blurCard);

    const fitCard = el('div', {
      class: 'wallpaper-control-card',
      style: 'grid-column: 1 / -1; display:flex; flex-direction:column; align-items:center; text-align:center; gap:10px;'
    }, [
      el('div', { style: 'text-align:center;' }, [
        el('div', { class: 'setting-label' }, [document.createTextNode('Fit Mode')]),
        el('div', { class: 'setting-desc' }, [document.createTextNode('How the image fits your screen')])
      ]),
      (() => {
        const fitWrap = el('div', { class: 'theme-source-tabs', style: 'justify-content:center;' }, []);
        const fitModes: Array<{ id: CustomBackgroundSettings['fit']; label: string }> = [
          { id: 'cover', label: 'Fill Screen' },
          { id: 'contain', label: 'Fit Inside' },
          { id: 'repeat', label: 'Tile' },
          { id: 'center', label: 'Center' }
        ];
        fitModes.forEach(m => {
          const btn = el('button', {
            type: 'button',
            class: 'theme-source-tab-btn' + (bgSettings.fit === m.id ? ' active' : ''),
            style: 'text-align:center; justify-content:center;'
          }, [document.createTextNode(m.label)]);
          btn.addEventListener('click', () => {
            bgSettings.fit = m.id;
            saveBackgroundSettings(bgSettings);
            renderSettingsView();
          });
          fitWrap.appendChild(btn);
        });
        return fitWrap;
      })()
    ]);
    tuningGrid.appendChild(fitCard);

    wallpaperCard.appendChild(tuningGrid);
  }

  wallpaperSec.appendChild(wallpaperCard);
  inner.appendChild(wallpaperSec);

  const glassSec = el('div', { class: 'settings-section' }, []);
  glassSec.appendChild(el('div', { class: 'settings-section-title' }, [document.createTextNode('Window Transparency')]));

  const glassCard = el('div', { class: 'settings-card', style: 'padding:18px;display:flex;flex-direction:column;gap:16px;' }, [
    el('div', {}, [
      el('div', { class: 'setting-label' }, [document.createTextNode('Transparency Level')]),
      el('div', { class: 'setting-desc' }, [
        document.createTextNode('Makes cards and menus see-through so your wallpaper shows behind them.')
      ])
    ])
  ]);

  const glassLevels: Array<{
    id: CustomBackgroundSettings['glassmorphism'];
    title: string;
    desc: string;
  }> = [
      {
        id: 'none',
        title: 'Off',
        desc: 'Solid background. No transparency.'
      },
      {
        id: 'subtle',
        title: 'Low',
        desc: 'Slight transparency.'
      },
      {
        id: 'medium',
        title: 'Medium',
        desc: 'Balanced blur and transparency.'
      },
      {
        id: 'high',
        title: 'High',
        desc: 'Very transparent.'
      }
    ];

  const levelsGrid = el('div', { class: 'glass-levels-grid' }, []);
  glassLevels.forEach(lvl => {
    const isLvlActive = bgSettings.glassmorphism === lvl.id;
    const card = el('div', {
      class: 'glass-level-card' + (isLvlActive ? ' active' : '')
    }, [
      el('div', { class: 'glass-level-title' }, [
        document.createTextNode(lvl.title)
      ]),
      el('div', { class: 'glass-level-desc' }, [document.createTextNode(lvl.desc)])
    ]);

    card.addEventListener('click', () => {
      bgSettings.glassmorphism = lvl.id;
      saveBackgroundSettings(bgSettings);
      renderSettingsView();
    });

    levelsGrid.appendChild(card);
  });
  glassCard.appendChild(levelsGrid);

  const glassDemoStage = el('div', { class: 'glass-demo-stage' }, []);

  let demoBg = '';
  if (bgSettings.enabled && bgSettings.type === 'preset') {
    const p = BACKGROUND_PRESETS.find(x => x.id === bgSettings.presetId) || BACKGROUND_PRESETS[0];
    demoBg = p.previewGradient;
  } else if (bgSettings.enabled && bgSettings.customImage) {
    demoBg = `url("${bgSettings.customImage}") center/cover`;
  } else {
    demoBg = `radial-gradient(ellipse at top left, ${currentTheme.colors.primary}44 0%, transparent 60%), radial-gradient(ellipse at bottom right, ${currentTheme.colors.accent}33 0%, transparent 60%), ${currentTheme.colors.bg}`;
  }

  const demoStageBg = el('div', {
    style: `position:absolute;inset:0;background:${demoBg};filter:${bgSettings.blur > 0 ? `blur(${bgSettings.blur}px)` : 'none'};z-index:0;`
  }, []);
  glassDemoStage.appendChild(demoStageBg);

  const glassStyleMap: Record<CustomBackgroundSettings['glassmorphism'], { bg: string; blur: string; border: string }> = {
    none: { bg: 'var(--card)', blur: 'none', border: 'var(--border)' },
    subtle: { bg: 'rgba(25, 30, 42, 0.75)', blur: 'blur(8px)', border: 'rgba(255, 255, 255, 0.12)' },
    medium: { bg: 'rgba(20, 26, 38, 0.55)', blur: 'blur(16px)', border: 'rgba(255, 255, 255, 0.18)' },
    high: { bg: 'rgba(15, 20, 32, 0.38)', blur: 'blur(24px)', border: 'rgba(255, 255, 255, 0.25)' }
  };

  const activeGlass = glassStyleMap[bgSettings.glassmorphism || 'medium'];

  const demoBox = el('div', {
    class: 'glass-demo-box',
    style: `position:relative;z-index:1;background:${activeGlass.bg};backdrop-filter:${activeGlass.blur};border:1px solid ${activeGlass.border};`
  }, [
    el('div', { style: 'display:flex;align-items:center;justify-content:space-between;' }, [
      el('span', { style: 'font-size:12px;font-weight:700;color:var(--fg);' }, [document.createTextNode('Preview')])
    ]),
    el('div', { style: 'font-size:11px;color:var(--fg2);line-height:1.4;' }, [
      document.createTextNode('This shows how cards and menus will look over your background.')
    ])
  ]);
  glassDemoStage.appendChild(demoBox);
  glassCard.appendChild(glassDemoStage);

  glassSec.appendChild(glassCard);
  inner.appendChild(glassSec);
}

// Setup screen rendering
function renderSetup(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const isRerunWizard = Boolean(isSetupRerun || state.settings.firstLaunch === false);
  if (isRerunWizard) {
    setupData.encryptionEnabled = Boolean(state.settings.encryptionEnabled);
    setupData.encryptionMethod = state.settings.encryptionEnabled ? (state.settings.encryptionMethod || 'password') : 'none';
  } else {
    if (setupData.encryptionEnabled === undefined) {
      setupData.encryptionEnabled = true;
      setupData.encryptionMethod = 'password';
    }
  }

  if (setupData.preferredBrowser === 'chromium') {
    setupData.preferredBrowser = 'auto';
  }

  let setupWrapper = document.getElementById('setup-wrapper');
  if (!setupWrapper) {
    app.innerHTML = `
      <div class="setup-wrapper" id="setup-wrapper">
        <div class="titlebar" data-tauri-drag-region>
          <div class="titlebar-drag" data-tauri-drag-region>
            <div class="setup-brand" data-tauri-drag-region>
              <img src="${getThemeIconUrl(setupData.selectedTheme || 'default-dark')}" alt="FRAM" class="logo-icon" style="width:20px;height:20px;object-fit:contain;border-radius:4px;" data-tauri-drag-region />
              <span data-tauri-drag-region>Roblox Account Manager</span>
            </div>
          </div>
          <div class="titlebar-controls">
            <button id="setup-minimize" class="titlebar-btn" title="Minimize">–</button>
            <button id="setup-close" class="titlebar-btn close" title="Close">✕</button>
          </div>
        </div>

        <div class="setup-main-viewport">
          <div class="setup-card">
            <!-- Stepper Header -->
            <div class="setup-stepper" id="setup-stepper">
              <div class="setup-step-pill active" id="stepper-step-0" data-step="0">
                <span class="step-dot"></span>
                <span>1. Welcome</span>
              </div>
              <div class="setup-step-pill" id="stepper-step-1" data-step="1">
                <span class="step-dot"></span>
                <span>2. Appearance</span>
              </div>
              <div class="setup-step-pill" id="stepper-step-2" data-step="2">
                <span class="step-dot"></span>
                <span>3. Browser</span>
              </div>
              <div class="setup-step-pill" id="stepper-step-3" data-step="3">
                <span class="step-dot"></span>
                <span>4. Roblox</span>
              </div>
              <div class="setup-step-pill" id="stepper-step-4" data-step="4">
                <span class="step-dot"></span>
                <span>5. Security</span>
              </div>
            </div>

            <!-- Sliding Viewport -->
            <div class="setup-carousel-container">
              <div class="setup-track" id="setup-track">
                <!-- Slide 0: Welcome & Past Version Import -->
                <div class="setup-slide" id="setup-slide-0">
                  <div class="setup-slide-header">
                    <h2>Welcome to Roblox Account Manager</h2>
                    <p>Start with a fresh setup or import your accounts and settings from an existing FRAMdata / AccountManagerData folder.</p>
                  </div>

                  <div class="setup-import-choice-grid">
                    <div class="setup-import-card ${setupData.importMode === 'fresh' ? 'selected' : ''}" data-import-mode="fresh">
                      <div class="setup-import-card-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-wrench preview-icon"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z"/></svg>
                      </div>
                      <div class="setup-import-card-body">
                        <div class="setup-import-card-title">Clean Setup</div>
                        <div class="setup-import-card-desc">Start fresh with default configuration and no accounts.</div>
                      </div>
                    </div>

                    <div class="setup-import-card ${setupData.importMode === 'import' ? 'selected' : ''}" data-import-mode="import">
                      <div class="setup-import-card-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-folder-input preview-icon"><path d="M2 9V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-1"/><path d="M2 13h10"/><path d="m9 16 3-3-3-3"/></svg>
                      </div>
                      <div class="setup-import-card-body">
                        <div class="setup-import-card-title">Import Past Version Data</div>
                        <div class="setup-import-card-desc">Bring over accounts and settings from a past FRAMdata folder.</div>
                      </div>
                    </div>
                  </div>

                  <div class="setup-import-box" id="setup-import-box" style="display: ${setupData.importMode === 'import' ? 'flex' : 'none'};">
                    <label class="setup-import-label">FRAMdata / AccountManagerData Folder Location</label>
                    <div class="setup-import-input-row">
                      <input type="text" id="setup-import-path-input" class="setup-input" placeholder="Select or paste folder path..." value="${setupData.importPath || ''}" />
                      <button type="button" class="btn btn-secondary" id="setup-browse-folder-btn">Browse...</button>
                      <button type="button" class="btn btn-primary" id="setup-verify-path-btn">Verify Path</button>
                    </div>

                    <div class="setup-import-input-row" id="setup-import-pwd-row" style="display:none; margin-top:6px;">
                      <input type="password" id="setup-import-pwd-input" class="setup-input" placeholder="Enter master password for encrypted account file..." value="${setupData.importPassword || ''}" />
                      <button type="button" class="btn btn-secondary" id="setup-import-pwd-apply-btn">Decrypt</button>
                    </div>

                    <div class="setup-import-status-box" id="setup-import-status-box" style="display:none;"></div>
                  </div>
                </div>

                <!-- Slide 1: Appearance & Personalization -->
                <div class="setup-slide" id="setup-slide-1">
                  <div class="setup-slide-header">
                    <h2>Appearance & Personalization</h2>
                    <p>Select your interface theme and custom accent color highlight.</p>
                  </div>

                  <div class="setup-theme-grid" id="setup-theme-grid"></div>

                  <div class="setup-accent-row">
                    <div style="font-size:11.5px; font-weight:600; color:var(--fg);">Accent Color</div>
                    <div class="accent-swatches-group" id="setup-accent-swatches"></div>
                  </div>
                </div>

                <!-- Slide 2: Automation Browser Selection -->
                <div class="setup-slide" id="setup-slide-2">
                  <div class="setup-slide-header">
                    <h2>Automation Browser Selection</h2>
                    <p>Select your default browser for automated logins and session management.</p>
                  </div>

                  <div class="setup-options-section">
                    <div class="setup-browser-grid" id="setup-browser-grid">
                      <div class="setup-browser-card ${setupData.preferredBrowser === 'auto' ? 'selected' : ''}" data-browser="auto">
                        <div class="setup-browser-icon">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                        </div>
                        <div class="setup-browser-info">
                          <div class="setup-browser-name">Auto-detect <span style="font-size:9px;padding:1px 4px;border-radius:3px;background:rgba(52,211,153,0.18);color:var(--emerald);">Best</span></div>
                          <div class="setup-browser-sub">System browser</div>
                        </div>
                      </div>

                      <div class="setup-browser-card ${setupData.preferredBrowser === 'chrome' ? 'selected' : ''}" data-browser="chrome">
                        <div class="setup-browser-icon">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="21.17" y1="8" x2="12" y2="8"/><line x1="3.95" y1="6.06" x2="8.54" y2="14"/><line x1="10.88" y1="21.94" x2="15.46" y2="14"/></svg>
                        </div>
                        <div class="setup-browser-info">
                          <div class="setup-browser-name">Google Chrome</div>
                          <div class="setup-browser-sub">Standard browser</div>
                        </div>
                      </div>

                      <div class="setup-browser-card ${setupData.preferredBrowser === 'edge' ? 'selected' : ''}" data-browser="edge">
                        <div class="setup-browser-icon">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 10 10 0 0 0 9.54-13H12"/></svg>
                        </div>
                        <div class="setup-browser-info">
                          <div class="setup-browser-name">Microsoft Edge</div>
                          <div class="setup-browser-sub">Built into Windows</div>
                        </div>
                      </div>

                      <div class="setup-browser-card ${setupData.preferredBrowser === 'firefox' ? 'selected' : ''}" data-browser="firefox">
                        <div class="setup-browser-icon">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a8 8 0 0 0-8 8c0 4.41 3.59 8 8 8a8 8 0 0 0 8-8c0-.62-.07-1.22-.21-1.8A7.94 7.94 0 0 1 12 14a5 5 0 0 1-5-5c0-2.3 1.55-4.24 3.68-4.82A7.95 7.95 0 0 0 12 2z"/></svg>
                        </div>
                        <div class="setup-browser-info">
                          <div class="setup-browser-name">Mozilla Firefox</div>
                          <div class="setup-browser-sub">Gecko engine</div>
                        </div>
                      </div>

                      <div class="setup-browser-card ${setupData.preferredBrowser === 'waterfox' ? 'selected' : ''}" data-browser="waterfox">
                        <div class="setup-browser-icon">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6c-3.31 0-6 2.69-6 6 0 2.22 1.21 4.15 3 5.19V17a3 3 0 0 0 6 0v-.81c1.79-1.04 3-2.97 3-5.19 0-3.31-2.69-6-6-6z"/></svg>
                        </div>
                        <div class="setup-browser-info">
                          <div class="setup-browser-name">Waterfox</div>
                          <div class="setup-browser-sub">Privacy browser</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Slide 3: Roblox Client Multi-Instance & Optimization -->
                <div class="setup-slide" id="setup-slide-3">
                  <div class="setup-slide-header">
                    <h2>Roblox Execution Engine</h2>
                    <p>Configure client multi-instance settings and launch automation behavior.</p>
                  </div>

                  <div class="setup-client-config-grid">
                    <div class="setup-config-card">
                      <div class="setup-config-info">
                        <div class="setup-config-title">Multi Instance</div>
                        <div class="setup-config-desc">Play on multiple Roblox accounts simultaneously without client conflicts.</div>
                      </div>
                      <button type="button" class="switch ${setupData.multiInstance ? 'on' : ''}" id="setup-sw-multi"><span class="knob"></span></button>
                    </div>

                    <div class="setup-config-card">
                      <div class="setup-config-info">
                        <div class="setup-config-title">Memory Trimmer</div>
                        <div class="setup-config-desc">Periodically optimize RAM usage across background Roblox instances.</div>
                      </div>
                      <button type="button" class="switch ${setupData.autoMemoryTrimEnabled ? 'on' : ''}" id="setup-sw-trim"><span class="knob"></span></button>
                    </div>

                    <div class="setup-config-card">
                      <div class="setup-config-info">
                        <div class="setup-config-title">CrashHandler Closer</div>
                        <div class="setup-config-desc">Automatically detect and terminate unresponsive RobloxCrashHandler processes.</div>
                      </div>
                      <button type="button" class="switch ${setupData.autoCloseCrashHandlers ? 'on' : ''}" id="setup-sw-crash-handler"><span class="knob"></span></button>
                    </div>

                    <div class="setup-config-card">
                      <div class="setup-config-info">
                        <div class="setup-config-title">Headless Mode</div>
                        <div class="setup-config-desc">Launch Roblox instances hidden in the background to save GPU and CPU resources.</div>
                      </div>
                      <button type="button" class="switch ${setupData.headlessMode ? 'on' : ''}" id="setup-sw-headless"><span class="knob"></span></button>
                    </div>
                  </div>
                </div>

                <!-- Slide 4: Vault Security & Encryption -->
                <div class="setup-slide" id="setup-slide-4">
                  <div class="setup-slide-header">
                    <h2>Vault Security & Encryption</h2>
                    <p>Choose how your cookies and account credentials are secured on this device.</p>
                  </div>

                  <div class="setup-security-grid" id="setup-security-grid" style="${isRerunWizard ? 'opacity:0.45; pointer-events:none; filter:grayscale(0.6); cursor:not-allowed;' : ''}">
                    <div class="setup-security-card ${setupData.encryptionMethod === 'password' ? 'selected' : ''}" data-method="password">
                      <div class="setup-security-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><circle cx="12" cy="16" r="1"/></svg>
                      </div>
                      <div style="flex:1;">
                        <div class="setup-security-title">Master Password ${isRerunWizard && setupData.encryptionMethod === 'password' ? '<span class="badge-recommended" style="background:rgba(79,142,247,0.18);color:var(--primary);">Active</span>' : '<span class="badge-recommended">Recommended</span>'}</div>
                        <div class="setup-security-desc">AES-256 GCM encryption unlocked with your master password on startup.</div>
                      </div>
                    </div>

                    <div class="setup-security-card ${setupData.encryptionMethod === 'hardware' ? 'selected' : ''}" data-method="hardware">
                      <div class="setup-security-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                      </div>
                      <div style="flex:1;">
                        <div class="setup-security-title">Hardware / DPAPI (Windows) ${isRerunWizard && setupData.encryptionMethod === 'hardware' ? '<span class="badge-recommended" style="background:rgba(79,142,247,0.18);color:var(--primary);">Active</span>' : ''}</div>
                        <div class="setup-security-desc">Tied to your Windows user credentials automatically. Seamless boot access.</div>
                      </div>
                    </div>

                    <div class="setup-security-card ${setupData.encryptionMethod === 'none' ? 'selected' : ''}" data-method="none">
                      <div class="setup-security-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                      </div>
                      <div style="flex:1;">
                        <div class="setup-security-title">No Encryption</div>
                        <div class="setup-security-desc">Plain JSON storage. Fastest access for secure personal machines.</div>
                      </div>
                    </div>
                  </div>

                  ${isRerunWizard ? `
                    <div style="margin-top:12px; padding:10px 14px; border-radius:8px; background:var(--card-alt); border:1px solid var(--border); font-size:11.5px; color:var(--muted); line-height:1.45; display:flex; align-items:center; gap:8px;">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15" style="color:var(--primary);flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                      <span>An encryption method is already configured on this device. To change or switch encryption, use <b>Settings &gt; Security</b>.</span>
                    </div>
                  ` : `
                    <div class="setup-pwd-wrap" id="setup-password-box" style="display: ${setupData.encryptionMethod === 'password' ? 'flex' : 'none'};">
                      <div style="display:flex; gap:8px;">
                        <input type="password" id="setup-password-input" class="setup-input" placeholder="Create Master Password (min 8 chars)" value="${setupData.encryptionPassword || ''}" autocomplete="new-password" />
                        <input type="password" id="setup-confirm-input" class="setup-input" placeholder="Confirm Password" value="${setupData.confirmPassword || ''}" autocomplete="new-password" />
                      </div>
                      <div id="pwd-match-badge" style="font-size:11px; color:var(--muted); min-height:16px;"></div>
                    </div>
                  `}
                </div>
              </div>
            </div>

            <!-- Stepper Footer -->
            <div class="setup-footer">
              <button type="button" class="btn-setup btn-setup-secondary" id="setup-btn-back" style="display:none;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="m15 18-6-6 6-6"/></svg>
                Back
              </button>
              <div class="setup-dots" id="setup-dots">
                <span class="setup-dot active" data-step="0"></span>
                <span class="setup-dot" data-step="1"></span>
                <span class="setup-dot" data-step="2"></span>
                <span class="setup-dot" data-step="3"></span>
                <span class="setup-dot" data-step="4"></span>
              </div>
              <button type="button" class="btn-setup btn-setup-primary" id="setup-btn-next">
                Continue
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="m9 18 6-6-6-6"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    bindSetupGlobalListeners();
    updateAppThemeIcons(setupData.selectedTheme || 'default-dark', setupData.accentColor).catch(() => { });
  }

  updateSetupView();
}

function triggerFramDataPreview(path: string): void {
  const statusBox = document.getElementById('setup-import-status-box');
  const pwdRow = document.getElementById('setup-import-pwd-row');
  if (!statusBox) return;

  const trimmed = (path || '').trim();
  if (!trimmed) {
    statusBox.style.display = 'none';
    if (pwdRow) pwdRow.style.display = 'none';
    setupData.importPreview = null;
    adjustSetupContainerHeight();
    return;
  }

  statusBox.style.display = 'block';
  statusBox.className = 'setup-import-status-box loading';
  statusBox.textContent = 'Scanning location for FRAMdata...';

  apiService.previewFRAMData(trimmed, setupData.importPassword || '').then(res => {
    if (res && res.valid) {
      setupData.importPreview = res;
      setupData.importPath = trimmed;

      if (res.is_encrypted && res.requires_password) {
        if (pwdRow) pwdRow.style.display = 'flex';
        statusBox.className = 'setup-import-status-box warning';
        statusBox.innerHTML = `🔒 <b>Account file is encrypted.</b> Enter the master password used when saving the accounts and click Decrypt.`;
      } else {
        if (pwdRow && !res.requires_password) pwdRow.style.display = 'none';
        statusBox.className = 'setup-import-status-box success';
        const parts = [];
        if (res.accounts_count) parts.push(`${res.accounts_count} accounts`);
        if (res.is_encrypted) parts.push(`decrypted`);
        if (res.games_count) parts.push(`${res.games_count} saved games`);
        if (res.users_count) parts.push(`${res.users_count} followed users`);
        if (res.has_settings) parts.push('preferences');
        if (res.has_webhooks) parts.push('webhook config');
        if (res.has_themes) parts.push('custom themes');
        const details = parts.length > 0 ? parts.join(', ') : 'valid data folder';
        statusBox.innerHTML = `✓ <b>Valid FRAMdata folder found!</b> Detected ${details}.`;
      }
    } else {
      if (pwdRow) pwdRow.style.display = 'none';
      setupData.importPreview = null;
      statusBox.className = 'setup-import-status-box error';
      statusBox.innerHTML = `✗ <b>Invalid location:</b> ${res?.error || 'No saved accounts or settings found.'}`;
    }
    adjustSetupContainerHeight();
  }).catch(err => {
    if (pwdRow) pwdRow.style.display = 'none';
    setupData.importPreview = null;
    statusBox.className = 'setup-import-status-box error';
    statusBox.innerHTML = `✗ <b>Error scanning path:</b> ${err?.message || err}`;
    adjustSetupContainerHeight();
  });
}

function bindSetupGlobalListeners(): void {
  const minBtn = document.getElementById('setup-minimize');
  const closeBtn = document.getElementById('setup-close');
  const backBtn = document.getElementById('setup-btn-back');
  const nextBtn = document.getElementById('setup-btn-next');
  const pwdInput = document.getElementById('setup-password-input') as HTMLInputElement | null;
  const confirmInput = document.getElementById('setup-confirm-input') as HTMLInputElement | null;

  if (minBtn) {
    minBtn.addEventListener('click', async () => {
      try {
        await invoke('minimize_window');
      } catch (error) {
        addLog('Failed to minimize window: ' + error, 'error');
      }
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', async () => {
      try {
        await invoke('close_window');
      } catch (error) {
        addLog('Failed to close window: ' + error, 'error');
      }
    });
  }

  if (backBtn) backBtn.addEventListener('click', handleSetupBack);
  if (nextBtn) nextBtn.addEventListener('click', handleSetupNext);

  // Import Mode Cards
  const importCards = document.querySelectorAll('.setup-import-choice-grid .setup-import-card');
  const importBox = document.getElementById('setup-import-box');
  importCards.forEach(card => {
    card.addEventListener('click', () => {
      const mode = (card as HTMLElement).dataset.importMode || 'fresh';
      setupData.importMode = mode;
      importCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      if (importBox) {
        importBox.style.display = mode === 'import' ? 'flex' : 'none';
        adjustSetupContainerHeight();
      }
    });
  });

  const pathInput = document.getElementById('setup-import-path-input') as HTMLInputElement | null;
  const browseBtn = document.getElementById('setup-browse-folder-btn');
  const verifyBtn = document.getElementById('setup-verify-path-btn');

  if (pathInput) {
    pathInput.addEventListener('input', () => {
      setupData.importPath = pathInput.value;
    });
    pathInput.addEventListener('change', () => {
      triggerFramDataPreview(pathInput.value);
    });
  }

  if (browseBtn) {
    browseBtn.addEventListener('click', async () => {
      let selectedPath = await pickNativeFolder('Select FRAMdata or AccountManagerData Folder');

      if (!selectedPath) {
        try {
          const res = await apiService.selectFolderDialog();
          if (res && res.success && res.path) {
            selectedPath = res.path;
          }
        } catch (e) {
          addLog('Backend folder picker failed: ' + e, 'error');
        }
      }

      if (selectedPath) {
        if (pathInput) pathInput.value = selectedPath;
        setupData.importPath = selectedPath;
        triggerFramDataPreview(selectedPath);
      }
    });
  }

  if (verifyBtn) {
    verifyBtn.addEventListener('click', () => {
      const val = pathInput ? pathInput.value : setupData.importPath;
      triggerFramDataPreview(val);
    });
  }

  const impPwdInput = document.getElementById('setup-import-pwd-input') as HTMLInputElement | null;
  const impPwdApplyBtn = document.getElementById('setup-import-pwd-apply-btn');

  if (impPwdInput) {
    impPwdInput.addEventListener('input', () => {
      setupData.importPassword = impPwdInput.value;
    });
    impPwdInput.addEventListener('change', () => {
      const val = pathInput ? pathInput.value : setupData.importPath;
      triggerFramDataPreview(val);
    });
  }

  if (impPwdApplyBtn) {
    impPwdApplyBtn.addEventListener('click', () => {
      const val = pathInput ? pathInput.value : setupData.importPath;
      triggerFramDataPreview(val);
    });
  }

  // Browser Cards
  const browserCards = document.querySelectorAll('#setup-browser-grid .setup-browser-card');
  browserCards.forEach(card => {
    card.addEventListener('click', () => {
      const b = (card as HTMLElement).dataset.browser || 'auto';
      setupData.preferredBrowser = b;
      browserCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
    });
  });

  // Client toggles
  const swMulti = document.getElementById('setup-sw-multi');
  if (swMulti) {
    swMulti.addEventListener('click', () => {
      setupData.multiInstance = !setupData.multiInstance;
      swMulti.className = `switch${setupData.multiInstance ? ' on' : ''}`;
    });
  }

  const delaySlider = document.getElementById('setup-delay-slider') as HTMLInputElement | null;
  const delayLabel = document.getElementById('setup-delay-val-label');
  if (delaySlider) {
    delaySlider.addEventListener('input', () => {
      const val = Number(delaySlider.value);
      setupData.multiLaunchDelay = val;
      if (delayLabel) delayLabel.textContent = `${(val / 1000).toFixed(1)}s`;
    });
  }

  const swTrim = document.getElementById('setup-sw-trim');
  if (swTrim) {
    swTrim.addEventListener('click', () => {
      setupData.autoMemoryTrimEnabled = !setupData.autoMemoryTrimEnabled;
      swTrim.className = `switch${setupData.autoMemoryTrimEnabled ? ' on' : ''}`;
    });
  }

  const swCrash = document.getElementById('setup-sw-crash-handler');
  if (swCrash) {
    swCrash.addEventListener('click', () => {
      setupData.autoCloseCrashHandlers = !setupData.autoCloseCrashHandlers;
      swCrash.className = `switch${setupData.autoCloseCrashHandlers ? ' on' : ''}`;
    });
  }

  const swHeadless = document.getElementById('setup-sw-headless');
  if (swHeadless) {
    swHeadless.addEventListener('click', () => {
      setupData.headlessMode = !setupData.headlessMode;
      swHeadless.className = `switch${setupData.headlessMode ? ' on' : ''}`;
    });
  }

  // Security Cards
  const secCards = document.querySelectorAll('#setup-security-grid .setup-security-card');
  secCards.forEach(card => {
    card.addEventListener('click', () => {
      const isRerun = Boolean(isSetupRerun || state.settings.firstLaunch === false);
      if (isRerun) return;
      const method = (card as HTMLElement).dataset.method || 'none';
      setupData.encryptionEnabled = method !== 'none';
      setupData.encryptionMethod = method;
      secCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');

      const pwdBox = document.getElementById('setup-password-box');
      if (pwdBox) {
        pwdBox.style.display = method === 'password' ? 'flex' : 'none';
        adjustSetupContainerHeight();
      }
    });
  });

  const updateMatch = () => {
    const pwd = (pwdInput?.value || '').trim();
    const conf = (confirmInput?.value || '').trim();
    const badge = document.getElementById('pwd-match-badge');
    if (!badge) return;
    if (!pwd && !conf) {
      badge.textContent = '';
      return;
    }
    if (pwd.length < 8) {
      badge.textContent = 'Password must be at least 8 characters';
      badge.style.color = 'var(--amber)';
    } else if (conf && pwd !== conf) {
      badge.textContent = '✗ Passwords do not match';
      badge.style.color = 'var(--red)';
    } else if (conf && pwd === conf) {
      badge.textContent = '✓ Passwords match';
      badge.style.color = 'var(--emerald)';
    } else {
      badge.textContent = 'Enter confirmation password';
      badge.style.color = 'var(--muted)';
    }
  };

  if (pwdInput) {
    pwdInput.addEventListener('input', () => {
      setupData.encryptionPassword = pwdInput.value;
      updateMatch();
    });
    pwdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleSetupNext();
    });
  }

  if (confirmInput) {
    confirmInput.addEventListener('input', () => {
      setupData.confirmPassword = confirmInput.value;
      updateMatch();
    });
    confirmInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleSetupNext();
    });
  }

  for (let i = 0; i < 5; i++) {
    const stepItem = document.getElementById(`stepper-step-${i}`);
    if (stepItem) {
      stepItem.addEventListener('click', () => {
        if (i <= setupStep || i === 0) {
          setupStep = i;
          updateSetupView();
        }
      });
    }
  }
}

function updateSetupView(): void {
  const track = document.getElementById('setup-track');
  if (track) {
    track.style.transform = `translateX(-${setupStep * 20}%)`;
  }

  for (let i = 0; i < 5; i++) {
    const pill = document.getElementById(`stepper-step-${i}`);
    if (pill) {
      pill.classList.toggle('active', i === setupStep);
      pill.classList.toggle('completed', i < setupStep);
    }
  }

  const dots = document.querySelectorAll('#setup-dots .setup-dot');
  dots.forEach((d, idx) => {
    d.classList.toggle('active', idx === setupStep);
  });

  const backBtn = document.getElementById('setup-btn-back');
  const nextBtn = document.getElementById('setup-btn-next');

  if (backBtn) {
    backBtn.style.display = setupStep > 0 ? 'inline-flex' : 'none';
  }

  if (nextBtn) {
    nextBtn.removeAttribute('disabled');
    (nextBtn as HTMLButtonElement).disabled = false;
    nextBtn.style.opacity = '1';
    nextBtn.style.pointerEvents = 'auto';
    nextBtn.style.cursor = 'pointer';
    if (setupStep === 4) {
      nextBtn.className = 'btn-setup btn-setup-finish';
      nextBtn.innerHTML = `Complete Setup <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><polygon points="5 3 19 12 5 21 5 3"/></svg>`;
    } else {
      nextBtn.className = 'btn-setup btn-setup-primary';
      nextBtn.innerHTML = `Continue <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="m9 18 6-6-6-6"/></svg>`;
    }
  }

  if (setupStep === 1) {
    renderSetupThemeSlide();
  }

  adjustSetupContainerHeight();
}

function adjustSetupContainerHeight(): void {
  const container = document.querySelector('.setup-carousel-container') as HTMLElement | null;
  const currentSlide = document.getElementById(`setup-slide-${setupStep}`);
  if (container && currentSlide) {
    setTimeout(() => {
      const h = currentSlide.offsetHeight || currentSlide.scrollHeight;
      if (h > 0) {
        container.style.height = `${h}px`;
      }
    }, 40);
  }
}



function renderSetupThemeSlide(): void {
  const gridWrap = document.getElementById('setup-theme-grid');
  const swatchWrap = document.getElementById('setup-accent-swatches');
  if (!gridWrap || !swatchWrap) return;

  const activeThemeId = setupData.selectedTheme || 'default-dark';
  const activeTheme = getTheme(activeThemeId) || THEMES['default-dark'];
  const curatedThemeIds = ['default-dark', 'synapse-neon', 'midnight-matrix', 'crimson-abyss', 'stardust-os', 'aurora-fade'];

  const refreshUI = () => {
    const curThemeId = setupData.selectedTheme || 'default-dark';
    const curTheme = getTheme(curThemeId) || THEMES['default-dark'];
    const curAccent = setupData.accentColor || curTheme.colors.primary;

    gridWrap.querySelectorAll<HTMLElement>('.setup-theme-card').forEach(card => {
      const tid = card.dataset.themeId;
      card.classList.toggle('selected', tid === curThemeId);
    });

    const swatches = swatchWrap.querySelectorAll<HTMLElement>('.accent-circle');
    const firstSwatch = swatches[0];
    if (firstSwatch) {
      firstSwatch.style.background = curTheme.colors.primary;
      firstSwatch.dataset.color = curTheme.colors.primary;
    }

    const presets = [curTheme.colors.primary, '#4f8ef7', '#34d399', '#f472b6', '#f59e0b', '#a78bfa', '#00f0ff'];
    swatches.forEach((sw, idx) => {
      const c = idx === 0 ? curTheme.colors.primary : presets[idx];
      const active = curAccent ? curAccent.toLowerCase() === c.toLowerCase() : c === curTheme.colors.primary;
      sw.classList.toggle('active', active);
    });

    const isCustomActive = Boolean(curAccent && !presets.some(c => c.toLowerCase() === curAccent.toLowerCase()));
    const customCircle = swatchWrap.querySelector<HTMLElement>('.custom-color-circle');
    if (customCircle) {
      customCircle.classList.toggle('active', isCustomActive);
      if (isCustomActive && curAccent) {
        customCircle.style.setProperty('--custom-accent-color', curAccent);
      }
    }
    const colorInput = swatchWrap.querySelector<HTMLInputElement>('.custom-color-input');
    if (colorInput) {
      colorInput.value = curAccent || curTheme.colors.primary;
    }
  };

  if (gridWrap.children.length === 0) {
    curatedThemeIds.forEach(tid => {
      const t = getTheme(tid) || THEMES[tid];
      if (!t) return;
      const isSelected = t.id === activeThemeId;

      const card = el('div', { class: 'setup-theme-card' + (isSelected ? ' selected' : ''), 'data-theme-id': t.id }, []);

      const preview = el('div', {
        class: 'setup-theme-preview',
        style: `background: ${t.colors.bg}; border: 1px solid ${t.colors.borderSoft};`
      }, [
        el('div', { class: 'setup-theme-dot', style: `background: ${t.colors.card};` }, []),
        el('div', { class: 'setup-theme-dot', style: `background: ${t.colors.primary};` }, []),
        el('div', { class: 'setup-theme-dot', style: `background: ${t.colors.border};` }, [])
      ]);
      card.appendChild(preview);

      const name = el('div', { class: 'setup-theme-name' }, [document.createTextNode(t.name)]);
      card.appendChild(name);

      card.addEventListener('click', () => {
        setupData.selectedTheme = t.id;
        const defaultAccent = t.accentSwatches?.[0] || t.colors.primary;
        setupData.accentColor = defaultAccent;
        applyTheme(t.id, defaultAccent);
        updateAppThemeIcons(t.id, defaultAccent).catch(() => { });
        refreshUI();
      });

      gridWrap.appendChild(card);
    });

    swatchWrap.innerHTML = '';
    const presets = [activeTheme.colors.primary, '#4f8ef7', '#34d399', '#f472b6', '#f59e0b', '#a78bfa', '#00f0ff'];
    presets.forEach((color) => {
      const active = setupData.accentColor ? setupData.accentColor.toLowerCase() === color.toLowerCase() : color === activeTheme.colors.primary;
      const dot = el('div', {
        class: 'accent-circle' + (active ? ' active' : ''),
        style: `background: ${color};`,
        'data-color': color
      }, []);
      dot.addEventListener('click', () => {
        const targetColor = (dot as HTMLElement).dataset.color || color;
        setupData.accentColor = targetColor;
        applyTheme(setupData.selectedTheme || 'default-dark', targetColor);
        refreshUI();
      });
      swatchWrap.appendChild(dot);
    });

    const setupAccent = setupData.accentColor;
    const isCustomActive = Boolean(setupAccent && !presets.some(c => c.toLowerCase() === setupAccent.toLowerCase()));
    const customWrap = el('div', { class: 'custom-color-wrap' }, []);
    const customCircle = el('div', {
      class: 'custom-color-circle' + (isCustomActive ? ' active' : ''),
      title: 'Custom accent color'
    }, []);
    if (isCustomActive && setupAccent) {
      customCircle.style.setProperty('--custom-accent-color', setupAccent);
    }
    const colorInput = el('input', {
      type: 'color',
      class: 'custom-color-input',
      value: setupData.accentColor || activeTheme.colors.primary
    }, []) as HTMLInputElement;
    colorInput.addEventListener('input', (e) => {
      const val = (e.target as HTMLInputElement).value;
      setupData.accentColor = val;
      applyTheme(setupData.selectedTheme || 'default-dark', val);
      refreshUI();
    });
    customWrap.appendChild(customCircle);
    customWrap.appendChild(colorInput);
    swatchWrap.appendChild(customWrap);
  } else {
    refreshUI();
  }
}

function handleSetupNext(): void {
  if (setupStep === 0) {
    if (setupData.importMode === 'import' && setupData.importPath && !setupData.importPreview?.valid) {
      toast('Please verify your import folder path before continuing', 'error');
      return;
    }
    setupStep = 1;
    updateSetupView();
  } else if (setupStep === 1) {
    setupStep = 2;
    updateSetupView();
  } else if (setupStep === 2) {
    setupStep = 3;
    updateSetupView();
  } else if (setupStep === 3) {
    setupStep = 4;
    updateSetupView();
  } else if (setupStep === 4) {
    const isRerun = Boolean(isSetupRerun || state.settings.firstLaunch === false);
    if (!isRerun && setupData.encryptionEnabled && setupData.encryptionMethod === 'password') {
      const pwd = (setupData.encryptionPassword || '').trim();
      const conf = (setupData.confirmPassword || '').trim();
      if (!pwd || pwd.length < 8) {
        toast('Password must be at least 8 characters', 'error');
        return;
      }
      if (pwd !== conf) {
        toast('Passwords do not match', 'error');
        return;
      }
    }
    completeSetup();
  }
}

function handleSetupBack(): void {
  if (setupStep > 0) {
    setupStep--;
    updateSetupView();
  }
}

async function completeSetup(): Promise<void> {
  addLog('Starting setup completion...', 'info');

  try {
    if (setupData.importMode === 'import' && setupData.importPath) {
      addLog('Importing FRAMdata from ' + setupData.importPath, 'info');
      toast('Importing past version data...', 'info');
      const impRes = await apiService.importFRAMData(setupData.importPath, setupData.importPassword || '');
      if (impRes && impRes.success) {
        const parts = [];
        if (impRes.accounts_imported) parts.push(`${impRes.accounts_imported} accounts`);
        if (impRes.games_imported) parts.push(`${impRes.games_imported} games`);
        if (impRes.users_imported) parts.push(`${impRes.users_imported} followed users`);
        const summary = parts.length > 0 ? parts.join(', ') : 'past version data';
        toast(`Imported ${summary}!`, 'success');
        setupData.importedSummary = impRes;
      } else {
        toast(`Import warning: ${impRes?.error || 'Could not import all items'}`, 'error');
      }
    }

    const isRerun = Boolean(isSetupRerun || state.settings.firstLaunch === false);
    const requestBody = {
      encryptionEnabled: isRerun ? Boolean(state.settings.encryptionEnabled) : (setupData.encryptionEnabled || false),
      encryptionMethod: isRerun ? (state.settings.encryptionMethod || 'none') : (setupData.encryptionMethod || 'none'),
      encryptionPassword: isRerun ? '' : (setupData.encryptionPassword || ''),
      preferredBrowser: setupData.preferredBrowser || 'auto',
      selectedTheme: setupData.selectedTheme || 'default-dark',
      accentColor: setupData.accentColor || '',
      multiInstance: Boolean(setupData.multiInstance),
      multiLaunchDelay: Number(setupData.multiLaunchDelay || 1000),
      autoKillRobloxOnExit: Boolean(setupData.autoKillRobloxOnExit),
      autoMemoryTrimEnabled: Boolean(setupData.autoMemoryTrimEnabled),
      autoCloseCrashHandlers: Boolean(setupData.autoCloseCrashHandlers),
      headlessMode: Boolean(setupData.headlessMode),
      autoValidateOnLaunch: Boolean(setupData.autoValidateOnLaunch)
    };

    addLog('Sending setup payload to backend', 'info');

    const result = await apiService.completeSetup(requestBody);

    if (result && (result.success !== false)) {
      addLog('Setup completed successfully', 'success');

      if (setupData.headlessMode) {
        apiService.toggleHeadlessMode(true).catch(() => { });
      }
      if (setupData.autoCloseCrashHandlers) {
        apiService.killAllCrashHandlers().catch(() => { });
      }

      const wrapper = document.getElementById('setup-wrapper');
      if (wrapper) {
        wrapper.classList.add('fade-out');
      }

      setTimeout(async () => {
        isSetupRerun = false;
        showSetup = false;
        if (result.settings) {
          state.settings = { ...state.settings, ...result.settings };
        }
        initApp();
        applyTheme(state.settings.selectedTheme || 'default-dark', state.settings.accentColor);
        updateAppThemeIcons(state.settings.selectedTheme || 'default-dark', state.settings.accentColor).catch(() => { });
        toast('Setup completed! Welcome to Forked Roblox Account Manager.', 'success');
        await loadFromBackend();
        renderAll();
      }, 350);
    } else {
      const errorMsg = result?.error || 'Setup failed';
      addLog('Setup failed: ' + errorMsg, 'error');
      toast(errorMsg, 'error');
    }
  } catch (error: any) {
    console.error('Setup failed:', error);
    const errorMsg = error?.message || 'Failed to complete setup';
    addLog('Setup error: ' + errorMsg, 'error');
    toast(errorMsg, 'error');
  }
}

function applyStreamerModeStyles(): void {
  const isStreamer = Boolean(state.settings.streamerMode);
  document.body.classList.toggle('streamer-mode-active', isStreamer);
  const blurLevel = ((state.settings.streamerBlurLevel as string) === 'mask' ? 'medium' : state.settings.streamerBlurLevel) || 'medium';
  document.body.setAttribute('data-streamer-blur', blurLevel);

  document.body.classList.toggle('streamer-hide-usernames', isStreamer && Boolean(state.settings.streamerHideUsernames));
  document.body.classList.toggle('streamer-hide-avatars', isStreamer && Boolean(state.settings.streamerHideAvatars));
  document.body.classList.toggle('streamer-hide-sensitive', isStreamer && Boolean(state.settings.streamerHideSensitiveInfo));
  document.body.classList.toggle('streamer-hide-groups', isStreamer && Boolean(state.settings.streamerHideGroupsAndNotes));
  document.body.classList.toggle('streamer-reveal-hover', isStreamer && Boolean(state.settings.streamerRevealOnHover));

  const pillStreamer = document.getElementById('pill-streamer-mode');
  if (pillStreamer) {
    pillStreamer.classList.toggle('active', isStreamer);
  }
}

function applyAllSettingsLayout(): void {
  if (state.settings.selectedTheme) {
    applyTheme(state.settings.selectedTheme, state.settings.accentColor);
  }

  applyStreamerModeStyles();

  const accountsView = document.getElementById('accounts-view');
  if (accountsView) {
    const content = accountsView.querySelector('.content') as HTMLElement | null;
    const panel = document.getElementById('detail-panel');
    const bottomBar = accountsView.querySelector('.bottombar') as HTMLElement | null;

    if (content && panel && bottomBar) {
      const isSwapped = state.settings.layoutPreset === 'swapped';
      if (isSwapped) {
        if (bottomBar.parentElement !== content) {
          content.appendChild(bottomBar);
        }
        if (panel.parentElement !== accountsView) {
          accountsView.appendChild(panel);
        }
        bottomBar.classList.add('pos-side');
        panel.classList.add('pos-bottom');
      } else {
        if (panel.parentElement !== content) {
          content.appendChild(panel);
        }
        if (bottomBar.parentElement !== accountsView) {
          accountsView.appendChild(bottomBar);
        }
        bottomBar.classList.remove('pos-side');
        panel.classList.remove('pos-bottom');
      }
    }
  }

  const panel = document.getElementById('detail-panel');
  if (panel) {
    panel.style.display = state.settings.showDetailPanel === false ? 'none' : '';
  }

  const gamesRow = document.getElementById('games-row');
  if (gamesRow) {
    gamesRow.style.display = state.settings.showSavedGamesBar === false ? 'none' : '';
  }

  const accountsTable = document.getElementById('accounts-table');
  if (accountsTable) {
    accountsTable.classList.toggle('compact', Boolean(state.settings.compactRows));
  }

  const toastWrap = document.getElementById('toast-wrap');
  if (toastWrap) {
    const pos = state.settings.toastPosition || 'bottom-right';
    toastWrap.className = `pos-${pos}`;
  }

  const importBanner = document.getElementById('import-progress-banner');
  if (importBanner) {
    const pos = state.settings.toastPosition || 'bottom-right';
    const isShowing = importBanner.classList.contains('show');
    importBanner.className = `import-progress-banner pos-${pos}${isShowing ? ' show' : ''}`;
  }
}

let lastRenderedView: string = 'accounts';
let instancesAutoRefreshTimer: any = null;
let consoleLogsAutoRefreshTimer: any = null;

function renderAll(): void {
  if (showSetup) {
    renderSetup();
    return;
  }

  if (state.view !== lastRenderedView) {
    state.revealed = {};
    lastRenderedView = state.view;
  }

  applyAllSettingsLayout();

  const accountsView = document.getElementById('accounts-view');
  const settingsView = document.getElementById('settings-view');
  const instancesView = document.getElementById('instances-view');
  const vipView = document.getElementById('vip-view');
  const consoleView = document.getElementById('console-view');
  const webhooksView = document.getElementById('webhooks-view');
  const extensionsView = document.getElementById('extensions-view');
  const bloxgenView = document.getElementById('bloxgen-view');
  const fastflagsView = document.getElementById('fastflags-view');
  const clientsettingsView = document.getElementById('clientsettings-view');
  const aboutView = document.getElementById('about-view');

  const btnAccounts = document.getElementById('btn-accounts');
  const btnSettings = document.getElementById('btn-settings');
  const btnInstances = document.getElementById('btn-instances');
  const btnVip = document.getElementById('btn-vip');
  const btnConsole = document.getElementById('btn-console');
  const btnWebhooks = document.getElementById('btn-webhooks');
  const btnExtensions = document.getElementById('btn-extensions');
  const btnBloxgen = document.getElementById('btn-bloxgen');
  const btnFastflags = document.getElementById('btn-fastflags');
  const btnClientSettings = document.getElementById('btn-client-settings');
  const btnAbout = document.getElementById('btn-about');

  if (btnAccounts) {
    btnAccounts.classList.toggle('active', state.view === 'accounts');
  }

  if (accountsView) {
    accountsView.classList.toggle('show', state.view === 'accounts');
  }
  if (settingsView) {
    settingsView.classList.toggle('show', state.view === 'settings');
  }
  if (instancesView) {
    instancesView.classList.toggle('show', state.view === 'instances');
  }
  if (vipView) {
    vipView.classList.toggle('show', state.view === 'vip');
  }
  if (consoleView) {
    consoleView.classList.toggle('show', state.view === 'console');
  }
  if (webhooksView) {
    webhooksView.classList.toggle('show', state.view === 'webhooks');
  }
  if (extensionsView) {
    extensionsView.classList.toggle('show', state.view === 'extensions');
  }
  if (bloxgenView) {
    bloxgenView.classList.toggle('show', state.view === 'bloxgen');
  }
  if (fastflagsView) {
    fastflagsView.classList.toggle('show', state.view === 'fastflags');
  }
  if (clientsettingsView) {
    clientsettingsView.classList.toggle('show', state.view === 'clientsettings');
  }
  if (aboutView) {
    aboutView.classList.toggle('show', state.view === 'about');
  }

  if (btnFastflags) {
    btnFastflags.classList.toggle('active', state.view === 'fastflags');
  }
  if (btnClientSettings) {
    btnClientSettings.classList.toggle('active', state.view === 'clientsettings');
  }
  if (btnAbout) {
    btnAbout.classList.toggle('active', state.view === 'about');
  }

  if (btnSettings) {
    btnSettings.classList.toggle('active', state.view === 'settings');
  }
  if (btnInstances) {
    btnInstances.classList.toggle('active', state.view === 'instances');
  }
  if (btnVip) {
    btnVip.classList.toggle('active', state.view === 'vip');
  }
  if (btnConsole) {
    btnConsole.classList.toggle('active', state.view === 'console');
  }
  if (btnWebhooks) {
    btnWebhooks.classList.toggle('active', state.view === 'webhooks');
  }
  const isChromeDefault = state.settings.preferredBrowser === 'chrome';
  if (btnExtensions) {
    btnExtensions.classList.toggle('active', state.view === 'extensions');
    (btnExtensions as HTMLButtonElement).disabled = isChromeDefault;
    btnExtensions.style.opacity = isChromeDefault ? '0.4' : '1';
    btnExtensions.style.pointerEvents = isChromeDefault ? 'none' : 'auto';
    btnExtensions.title = isChromeDefault ? 'Extension Manager (Disabled when Chrome is default browser)' : 'Extension Manager';
    btnExtensions.classList.toggle('disabled', isChromeDefault);
  }
  if (isChromeDefault && state.view === 'extensions') {
    state.view = 'accounts';
  }
  if (btnBloxgen) {
    btnBloxgen.classList.toggle('active', state.view === 'bloxgen');
  }

  if (state.view !== 'instances' && instancesAutoRefreshTimer) {
    clearInterval(instancesAutoRefreshTimer);
    instancesAutoRefreshTimer = null;
  }
  if (state.view !== 'console' && consoleLogsAutoRefreshTimer) {
    clearInterval(consoleLogsAutoRefreshTimer);
    consoleLogsAutoRefreshTimer = null;
  }

  if (state.view === 'accounts') {
    renderStats();
    renderGroupFilter();
    renderTable();
    renderDetail();
    renderGames();
    renderLaunchBar();
    return;
  }

  if (state.view === 'webhooks') {
    fetchWebhookConfig();
    return;
  }

  if (state.view === 'extensions') {
    renderExtensionsView();
    return;
  }

  if (state.view === 'bloxgen') {
    renderBloxgenView();
    return;
  }

  if (state.view === 'console') {
    fetchBackendLogs().then(() => renderConsoleView());
    if (!consoleLogsAutoRefreshTimer) {
      consoleLogsAutoRefreshTimer = setInterval(() => {
        if (document.hidden) return;
        if (state.view === 'console') {
          fetchBackendLogs().then(() => renderConsoleView());
        }
      }, 3000);
    }
    return;
  }

  if (state.view === 'fastflags') {
    renderFastFlagsView();
    return;
  }

  if (state.view === 'clientsettings') {
    renderClientSettingsView();
    return;
  }

  if (state.view === 'about') {
    renderAboutView();
    return;
  }

  if (state.view === 'settings') {
    renderSettingsView();
    return;
  }

  if (state.view === 'vip') {
    renderVipView();
    return;
  }

  if (state.view === 'instances') {
    renderInstancesView();
    if (!instancesAutoRefreshTimer) {
      instancesAutoRefreshTimer = setInterval(() => {
        if (document.hidden) return;
        const checkbox = document.getElementById('instances-auto-refresh') as HTMLInputElement;
        if (state.view === 'instances' && (!checkbox || checkbox.checked)) {
          renderInstancesView();
        }
      }, 3500);
    }
    return;
  }
}

function getFilteredVipAccounts(): Account[] {
  const groupSelect = document.getElementById('vip-group-filter') as HTMLSelectElement | null;
  const searchInput = document.getElementById('vip-search-input') as HTMLInputElement | null;
  const query = (searchInput?.value || '').trim().toLowerCase();
  const activeGroup = groupSelect?.value || 'All';

  return (state.accounts || []).filter(a => {
    if (!a) return false;
    const matchesSearch = !query ||
      (a.username || '').toLowerCase().includes(query) ||
      (a.display_name || '').toLowerCase().includes(query) ||
      (a.group || '').toLowerCase().includes(query) ||
      (a.vip_server || '').toLowerCase().includes(query);
    const matchesGroup = activeGroup === 'All' || (a.group || '') === activeGroup;
    return matchesSearch && matchesGroup;
  });
}

let vipSelectedIds: Set<number> = new Set();
let lastVipGroupsKey: string = '';
const vipGameCache = new Map<string, { name: string; icon_url?: string }>();

function getAccountVipPlaceId(a: Account): string | undefined {
  if (a.vip_place_id) return a.vip_place_id;
  if (a.vip_server) {
    const extracted = extractPrivateServerCode(a.vip_server);
    if (extracted.placeId) return extracted.placeId;
  }
  return undefined;
}

async function resolveGameForVip(placeId: string): Promise<{ name: string; icon_url?: string } | null> {
  const pid = (placeId || '').trim();
  if (!pid) return null;
  if (vipGameCache.has(pid)) {
    return vipGameCache.get(pid)!;
  }
  const saved = (state.games || []).find(g => String(g.placeId) === pid);
  if (saved && saved.name) {
    const res = { name: saved.name, icon_url: saved.icon_url };
    vipGameCache.set(pid, res);
    return res;
  }
  try {
    const info = await apiService.getGameInfo(pid);
    if (info && !info.error) {
      const res = { name: info.name || `Place ${pid}`, icon_url: info.icon_url };
      vipGameCache.set(pid, res);
      return res;
    }
  } catch (_) { }
  return null;
}

function showSetVipGameModal(targetAccount?: Account): void {
  let overlay = document.getElementById('vip-set-game-modal-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'vip-set-game-modal-overlay';
    overlay.className = 'overlay';
    overlay.innerHTML = `
      <div class="modal" style="max-width: 440px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <h3 style="margin:0; font-size:16px; font-weight:600;">Set Target Game for VIP</h3>
          <button class="btn btn-icon" id="vip-modal-close" style="width:28px; height:28px;">&times;</button>
        </div>
        <p style="font-size:12px; color:var(--text-muted); margin-bottom:14px; line-height:1.4;">
          Assign the Place ID associated with your VIP server(s).
        </p>
        <div style="display:flex; flex-direction:column; gap:12px;">
          <div>
            <label style="font-size:11.5px; font-weight:600; color:var(--text-muted); display:block; margin-bottom:4px;">Choose from Saved Games</label>
            <select id="vip-modal-game-select" style="width:100%; height:34px; background:var(--bg); border:1px solid var(--border); border-radius:6px; color:var(--fg); padding:0 8px; font-size:12px; outline:none;">
              <option value="">-- Choose a saved game --</option>
            </select>
          </div>
          <div>
            <label style="font-size:11.5px; font-weight:600; color:var(--text-muted); display:block; margin-bottom:4px;">Or Enter Place ID Manually</label>
            <input type="text" id="vip-modal-place-input" placeholder="e.g. 189707" style="width:100%; height:34px; background:var(--bg); border:1px solid var(--border); border-radius:6px; color:var(--fg); padding:0 10px; font-size:12px; outline:none;" />
          </div>
          <div id="vip-modal-preview" style="display:none; align-items:center; gap:10px; padding:10px; background:var(--bg); border:1px solid var(--border); border-radius:6px;">
            <div id="vip-modal-preview-thumb" style="width:40px; height:40px; border-radius:4px; overflow:hidden; background:var(--card-bg); flex-shrink:0; display:flex; align-items:center; justify-content:center;"></div>
            <div style="flex:1; min-width:0;">
              <div id="vip-modal-preview-name" style="font-size:12.5px; font-weight:600; color:var(--text-bright); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"></div>
              <div id="vip-modal-preview-id" style="font-size:11px; color:var(--text-muted);"></div>
            </div>
          </div>
        </div>
        <div style="display:flex; gap:8px; justify-content:flex-end; margin-top:20px;">
          <button class="btn btn-secondary" id="vip-modal-cancel">Cancel</button>
          <button class="btn btn-primary" id="vip-modal-apply" style="background:#10b981; border-color:#059669; color:#fff;">Apply Game</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
  }

  const closeBtn = document.getElementById('vip-modal-close');
  const cancelBtn = document.getElementById('vip-modal-cancel');
  const applyBtn = document.getElementById('vip-modal-apply');
  const selectEl = document.getElementById('vip-modal-game-select') as HTMLSelectElement | null;
  const placeInput = document.getElementById('vip-modal-place-input') as HTMLInputElement | null;
  const previewDiv = document.getElementById('vip-modal-preview');
  const previewThumb = document.getElementById('vip-modal-preview-thumb');
  const previewName = document.getElementById('vip-modal-preview-name');
  const previewId = document.getElementById('vip-modal-preview-id');

  const close = () => {
    overlay?.classList.remove('show');
  };

  if (closeBtn) closeBtn.onclick = close;
  if (cancelBtn) cancelBtn.onclick = close;

  if (selectEl) {
    selectEl.innerHTML = '<option value="">-- Choose a saved game --</option>' +
      (state.games || []).map(g => `<option value="${g.placeId}">${g.name} (${g.placeId})</option>`).join('');
    selectEl.value = '';
  }

  const currentPlaceId = targetAccount ? getAccountVipPlaceId(targetAccount) : (
    vipSelectedIds.size > 0 ? (getAccountVipPlaceId(state.accounts.find(a => vipSelectedIds.has(a.id))!) || '') : ''
  );

  if (placeInput) {
    placeInput.value = currentPlaceId || '';
  }

  const updatePreview = async (pid: string) => {
    const trimmed = (pid || '').trim();
    if (!trimmed || !previewDiv || !previewName || !previewId || !previewThumb) {
      if (previewDiv) previewDiv.style.display = 'none';
      return;
    }
    previewDiv.style.display = 'flex';
    previewId.textContent = `Place ID: ${trimmed}`;
    previewName.textContent = 'Loading game information...';
    previewThumb.innerHTML = '<div style="width:14px; height:14px; border:2px solid var(--accent); border-top-color:transparent; border-radius:50%; animation:spin 0.8s linear infinite;"></div>';

    const info = await resolveGameForVip(trimmed);
    if (info) {
      previewName.textContent = info.name;
      if (info.icon_url) {
        previewThumb.innerHTML = `<img src="${info.icon_url}" style="width:100%; height:100%; object-fit:cover;" alt="" />`;
      } else {
        previewThumb.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><rect width="20" height="14" x="2" y="3" rx="2"/></svg>';
      }
    } else {
      previewName.textContent = `Place ${trimmed}`;
      previewThumb.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><rect width="20" height="14" x="2" y="3" rx="2"/></svg>';
    }
  };

  if (selectEl && placeInput) {
    selectEl.onchange = () => {
      if (selectEl.value) {
        placeInput.value = selectEl.value;
        updatePreview(selectEl.value);
      }
    };
    placeInput.oninput = () => {
      if (selectEl) selectEl.value = '';
      updatePreview(placeInput.value);
    };
  }

  if (currentPlaceId) {
    updatePreview(currentPlaceId);
  } else if (previewDiv) {
    previewDiv.style.display = 'none';
  }

  if (applyBtn) {
    applyBtn.onclick = async () => {
      const chosenPlaceId = (placeInput?.value || '').trim();
      const info = chosenPlaceId ? await resolveGameForVip(chosenPlaceId) : null;
      const gameName = info?.name || (chosenPlaceId ? `Place ${chosenPlaceId}` : '');

      let targetAccounts: Account[] = [];
      if (targetAccount) {
        targetAccounts = [targetAccount];
      } else if (vipSelectedIds.size > 0) {
        targetAccounts = state.accounts.filter(a => vipSelectedIds.has(a.id));
      } else {
        targetAccounts = state.accounts.filter(a => Boolean(a.vip_server));
        if (targetAccounts.length === 0) {
          targetAccounts = state.accounts;
        }
      }

      if (targetAccounts.length === 0) {
        toast('No accounts found to assign game to', 'error');
        close();
        return;
      }

      const mapping: Record<string, any> = {};
      targetAccounts.forEach(a => {
        a.vip_place_id = chosenPlaceId;
        a.vip_game_name = gameName;
        mapping[a.username] = {
          vip_server: a.vip_server || '',
          vip_place_id: chosenPlaceId,
          vip_game_name: gameName
        };
      });

      try {
        await apiService.bulkUpdateVip(mapping);
        toast(`Assigned game "${gameName || chosenPlaceId || 'None'}" to ${targetAccounts.length} account(s)!`, 'success');
        renderVipView();
      } catch (err) {
        toast('Failed to save game to accounts: ' + err, 'error');
      }
      close();
    };
  }

  overlay.classList.add('show');
}

function renderVipView(): void {
  const tableBody = document.getElementById('vip-table-body');
  const groupSelect = document.getElementById('vip-group-filter') as HTMLSelectElement | null;
  const selectAllCb = document.getElementById('vip-select-all') as HTMLInputElement | null;
  const selectionLabel = document.getElementById('vip-selection-label');

  if (!tableBody) return;

  if (groupSelect) {
    const currentVal = groupSelect.value || 'All';
    const groups: string[] = ['All'];
    (state.accounts || []).forEach(a => {
      if (a.group && groups.indexOf(a.group) === -1) {
        groups.push(a.group);
      }
    });
    const groupsKey = groups.join('|');
    if (groupsKey !== lastVipGroupsKey) {
      lastVipGroupsKey = groupsKey;
      groupSelect.innerHTML = groups.map(g => `<option value="${g}">${g === 'All' ? 'All Groups' : g}</option>`).join('');
      groupSelect.value = groups.includes(currentVal) ? currentVal : 'All';
    }
  }

  const list = getFilteredVipAccounts();

  // Update launch VIP bottom control button
  const btnVipLaunch = document.getElementById('btn-vip-launch') as HTMLButtonElement | null;
  if (btnVipLaunch) {
    const hasSelection = vipSelectedIds.size > 0;
    btnVipLaunch.disabled = !hasSelection;
    btnVipLaunch.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" style="width:12px;height:12px;margin-right:4px;"><polygon points="6 3 20 12 6 21 6 3"/></svg> Launch VIP${hasSelection ? ` (${vipSelectedIds.size})` : ''}`;
  }

  if (selectionLabel) {
    selectionLabel.textContent = `Selected: (${vipSelectedIds.size})`;
  }

  if (selectAllCb) {
    selectAllCb.checked = list.length > 0 && list.every(a => vipSelectedIds.has(a.id));
  }

  if (list.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align:center; padding:40px; color:var(--text-muted);">
          No accounts found matching your filters.
        </td>
      </tr>
    `;
    return;
  }

  tableBody.innerHTML = '';
  list.forEach(a => {
    const isSelected = vipSelectedIds.has(a.id);
    const tr = document.createElement('tr');
    if (isSelected) tr.classList.add('selected');

    tr.addEventListener('click', (e) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'BUTTON' || target.closest('button') || target.closest('input')) {
        return;
      }
      if (vipSelectedIds.has(a.id)) {
        vipSelectedIds.delete(a.id);
      } else {
        vipSelectedIds.add(a.id);
      }
      renderVipView();
    });

    const cbTd = document.createElement('td');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = isSelected;
    cb.addEventListener('click', (e) => e.stopPropagation());
    cb.addEventListener('change', (e) => {
      e.stopPropagation();
      if (cb.checked) {
        vipSelectedIds.add(a.id);
      } else {
        vipSelectedIds.delete(a.id);
      }
      renderVipView();
    });
    cbTd.appendChild(cb);
    tr.appendChild(cbTd);

    const userTd = document.createElement('td');
    const userWrap = document.createElement('div');
    userWrap.className = 'row-user-wrap';

    if (state.settings.downloadAvatarIcons !== false && a.avatar_url) {
      const img = document.createElement('img');
      img.src = a.avatar_url;
      img.className = 'row-avatar';
      img.alt = a.username || '';
      img.onerror = () => {
        const fallback = document.createElement('div');
        fallback.className = 'row-avatar-fallback';
        fallback.textContent = initials(a.username);
        img.replaceWith(fallback);
      };
      userWrap.appendChild(img);
    } else {
      const fallback = document.createElement('div');
      fallback.className = 'row-avatar-fallback';
      fallback.textContent = initials(a.username);
      userWrap.appendChild(fallback);
    }

    const userNames = document.createElement('div');
    userNames.className = 'row-user-names';

    const uSpan = document.createElement('span');
    uSpan.className = 'row-username';
    uSpan.textContent = a.display_name || a.username;

    const dSpan = document.createElement('span');
    dSpan.className = 'row-display-name';
    dSpan.textContent = `@${a.username}`;

    userNames.appendChild(uSpan);
    userNames.appendChild(dSpan);
    userWrap.appendChild(userNames);

    userTd.appendChild(userWrap);
    tr.appendChild(userTd);

    const groupTd = document.createElement('td');
    groupTd.className = 'muted vip-group-cell';
    if (a.group) {
      const groupSpan = document.createElement('span');
      groupSpan.className = 'row-group';
      groupSpan.textContent = a.group;
      groupTd.appendChild(groupSpan);
    } else {
      groupTd.textContent = '—';
    }
    tr.appendChild(groupTd);

    // Game cell
    const gameTd = document.createElement('td');
    gameTd.className = 'vip-game-cell';
    const accPlaceId = getAccountVipPlaceId(a);

    const gameWrap = document.createElement('div');
    gameWrap.className = 'vip-game-cell-wrap';
    gameWrap.title = 'Click to assign or change game';

    const gameThumb = document.createElement('div');
    gameThumb.className = 'vip-game-cell-thumb';

    const gameInfoDiv = document.createElement('div');
    gameInfoDiv.className = 'vip-game-cell-info';

    const gameNameSpan = document.createElement('div');
    gameNameSpan.className = 'vip-game-cell-name';

    const gamePidSpan = document.createElement('div');
    gamePidSpan.className = 'vip-game-cell-pid';

    if (accPlaceId) {
      gamePidSpan.textContent = `ID: ${accPlaceId}`;
      const cached = vipGameCache.get(accPlaceId) || (state.games || []).find(g => String(g.placeId) === accPlaceId);
      if (cached) {
        gameNameSpan.textContent = cached.name || a.vip_game_name || `Place ${accPlaceId}`;
        if (cached.icon_url) {
          gameThumb.innerHTML = `<img src="${cached.icon_url}" alt="" />`;
        } else {
          gameThumb.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><rect width="20" height="14" x="2" y="3" rx="2"/></svg>`;
        }
      } else {
        gameNameSpan.textContent = a.vip_game_name || `Place ${accPlaceId}`;
        gameThumb.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><rect width="20" height="14" x="2" y="3" rx="2"/></svg>`;
        resolveGameForVip(accPlaceId).then(info => {
          if (info) {
            gameNameSpan.textContent = info.name;
            if (info.icon_url) {
              gameThumb.innerHTML = `<img src="${info.icon_url}" alt="" />`;
            }
          }
        }).catch(() => { });
      }
    } else {
      gameNameSpan.textContent = 'None Assigned';
      gameNameSpan.style.color = 'var(--text-muted)';
      gamePidSpan.textContent = 'No Place ID';
      gameThumb.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13" style="opacity:0.35;"><rect width="20" height="14" x="2" y="3" rx="2"/></svg>`;
    }

    gameWrap.addEventListener('click', (e) => {
      e.stopPropagation();
      showSetVipGameModal(a);
    });

    gameWrap.appendChild(gameThumb);
    gameInfoDiv.appendChild(gameNameSpan);
    gameInfoDiv.appendChild(gamePidSpan);
    gameWrap.appendChild(gameInfoDiv);
    gameTd.appendChild(gameWrap);
    tr.appendChild(gameTd);

    const vipTd = document.createElement('td');
    vipTd.className = 'vip-server-cell';
    const vipInput = document.createElement('input');
    vipInput.type = 'text';
    vipInput.className = 'vip-inline-input';
    vipInput.placeholder = 'Enter private server link or code...';
    vipInput.value = a.vip_server || '';
    vipInput.style.cssText = 'width:100%; height:28px; box-sizing:border-box; background:var(--bg); border:1px solid var(--border); border-radius:4px; color:var(--fg); padding:0 8px; font-size:11.5px; outline:none; display:block;';

    const unblurIfHoverAllowed = () => {
      if (document.body.classList.contains('streamer-reveal-hover')) {
        vipInput.style.filter = 'none';
      }
    };
    const restoreBlur = () => {
      if (document.activeElement !== vipInput) {
        vipInput.style.filter = '';
      }
    };

    vipInput.addEventListener('mouseenter', unblurIfHoverAllowed);
    vipInput.addEventListener('mouseleave', restoreBlur);
    vipInput.addEventListener('focus', () => { vipInput.style.filter = 'none'; });
    vipInput.addEventListener('blur', restoreBlur);

    vipTd.addEventListener('mouseenter', unblurIfHoverAllowed);
    vipTd.addEventListener('mouseleave', restoreBlur);

    vipInput.addEventListener('click', (e) => e.stopPropagation());
    vipInput.addEventListener('keydown', (e) => {
      e.stopPropagation();
      if (e.key === 'Enter') {
        vipInput.blur();
      }
    });

    let saveTimeout: any = null;
    const applyVipInputValue = async (rawVal: string) => {
      const trimmed = rawVal.trim();
      if (!trimmed) {
        if (a.vip_server !== '' || a.vip_place_id) {
          a.vip_server = '';
          a.vip_place_id = '';
          a.vip_game_name = '';
          apiService.updateAccount(a.id, { vip_server: '', vip_place_id: '', vip_game_name: '' }).catch(() => { });
          renderVipView();
        }
        return;
      }
      const normalized = await resolveAndNormalizePrivateServer(trimmed, a.cookie);
      const finalVal = normalized.code || trimmed;
      const extractedPlaceId = normalized.placeId || extractPrivateServerCode(trimmed).placeId;
      if (finalVal !== vipInput.value) {
        vipInput.value = finalVal;
      }
      let needsUpdate = false;
      const updates: Partial<Account> = {};
      if (a.vip_server !== finalVal) {
        a.vip_server = finalVal;
        updates.vip_server = finalVal;
        needsUpdate = true;
      }
      if (extractedPlaceId && a.vip_place_id !== extractedPlaceId) {
        a.vip_place_id = extractedPlaceId;
        updates.vip_place_id = extractedPlaceId;
        needsUpdate = true;
        resolveGameForVip(extractedPlaceId).then(info => {
          if (info && info.name) {
            a.vip_game_name = info.name;
            apiService.updateAccount(a.id, { vip_game_name: info.name }).catch(() => { });
          }
        });
      }
      if (needsUpdate) {
        apiService.updateAccount(a.id, updates).catch(() => { });
        renderVipView();
        if (normalized.changed) {
          toast(`Converted private server link into code for @${a.username}`, 'success');
        }
      }
    };

    vipInput.addEventListener('input', (e) => {
      e.stopPropagation();
      const val = vipInput.value.trim();
      const direct = extractPrivateServerCode(val);
      if (direct.code && direct.code !== val) {
        vipInput.value = direct.code;
        a.vip_server = direct.code;
        if (direct.placeId) a.vip_place_id = direct.placeId;
        apiService.updateAccount(a.id, { vip_server: direct.code, ...(direct.placeId ? { vip_place_id: direct.placeId } : {}) }).catch(() => { });
        toast(`Converted private server link into code for @${a.username}`, 'success');
        renderVipView();
        return;
      }
      a.vip_server = val;
      if (saveTimeout) clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
        applyVipInputValue(vipInput.value);
      }, 500);
    });

    vipInput.addEventListener('blur', (e) => {
      e.stopPropagation();
      applyVipInputValue(vipInput.value);
    });
    vipTd.appendChild(vipInput);
    tr.appendChild(vipTd);

    const statusTd = document.createElement('td');
    const meta = statusMeta(a.status);
    statusTd.innerHTML = `<span class="status-badge ${meta.bucket}"><span class="dot ${meta.dot}"></span>${meta.label}</span>`;
    tr.appendChild(statusTd);

    const actionTd = document.createElement('td');
    const actionWrap = document.createElement('div');
    actionWrap.style.cssText = 'display:flex; gap:4px; align-items:center;';

    const launchBtn = document.createElement('button');
    launchBtn.className = 'btn btn-secondary btn-sm';
    launchBtn.title = 'Launch VIP Server';
    const hasVip = Boolean(a.vip_server);
    if (hasVip) {
      launchBtn.style.cssText = 'padding:3px 8px; font-size:11px; color:#10b981; border-color:rgba(16,185,129,0.35); font-weight:600; cursor:pointer;';
      launchBtn.disabled = false;
    } else {
      launchBtn.style.cssText = 'padding:3px 8px; font-size:11px; color:var(--text-muted); border-color:var(--border); opacity:0.4; cursor:not-allowed;';
      launchBtn.disabled = true;
    }
    launchBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" width="11" height="11"><polygon points="6 3 20 12 6 21 6 3"/></svg> Launch';
    launchBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!a.vip_server) {
        toast(`Account @${a.username} has no VIP server link assigned`, 'error');
        return;
      }
      const normalized = await resolveAndNormalizePrivateServer(a.vip_server || '', a.cookie);
      const serverCodeToUse = normalized.code || a.vip_server || '';
      const placeIdFromUrl = a.vip_place_id || normalized.placeId || extractPrivateServerCode(a.vip_server || '').placeId;
      const fallbackPlaceId = (document.getElementById('place-input') as HTMLInputElement)?.value.trim() || undefined;
      const placeIdToUse = placeIdFromUrl || fallbackPlaceId;

      toast(`Launching VIP server for @${a.username}...`, 'info');
      apiService.launchAccount({
        username: a.username,
        placeId: placeIdToUse,
        serverId: serverCodeToUse,
        serverMode: 'vip'
      }).then(res => {
        if (res.success) toast(`Launched VIP server for @${a.username}`, 'success');
        else toast(`Failed to launch VIP: ${res.error || "Roblox isn't installed"}`, 'error');
      }).catch(err => toast(`Error launching VIP: ${err}`, 'error'));
    });

    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn btn-secondary btn-sm';
    copyBtn.title = 'Copy VIP Server Link';
    copyBtn.style.cssText = 'padding:3px 6px; font-size:11px;';
    copyBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="11" height="11"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>';
    copyBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (a.vip_server) {
        copyToClipboard(a.vip_server);
        toast(`Copied VIP link for @${a.username}`);
      } else {
        toast(`No VIP server link set for @${a.username}`, 'info');
      }
    });

    const clearBtn = document.createElement('button');
    clearBtn.className = 'btn btn-secondary btn-sm';
    clearBtn.title = 'Clear VIP Server';
    clearBtn.style.cssText = 'padding:3px 6px; font-size:11px; color:var(--red);';
    clearBtn.innerHTML = '×';
    clearBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      a.vip_server = '';
      a.vip_place_id = '';
      a.vip_game_name = '';
      vipInput.value = '';
      apiService.updateAccount(a.id, { vip_server: '', vip_place_id: '', vip_game_name: '' }).then(() => {
        toast(`Cleared VIP server for @${a.username}`);
        renderVipView();
      });
    });

    actionWrap.appendChild(launchBtn);
    actionWrap.appendChild(copyBtn);
    actionWrap.appendChild(clearBtn);
    actionTd.appendChild(actionWrap);
    tr.appendChild(actionTd);

    tableBody.appendChild(tr);
  });
}

function importVipCsv(): void {
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = '.csv,.txt';
  fileInput.addEventListener('change', (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
      const text = String(evt.target?.result || '');
      if (!text.trim()) return;

      const lines = text.split('\n');
      const mapping: Record<string, string> = {};
      let count = 0;

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const parts = trimmed.split(/[,;\t]+/);
        if (parts.length >= 2) {
          const username = parts[0].replace(/^["']|["']$/g, '').trim();
          const vip = parts[1].replace(/^["']|["']$/g, '').trim();
          if (username && vip && username.toLowerCase() !== 'username') {
            mapping[username] = vip;
            count++;
          }
        }
      }

      if (count > 0) {
        try {
          const res = await apiService.bulkUpdateVip(mapping);
          state.accounts.forEach(a => {
            if (mapping[a.username]) {
              a.vip_server = mapping[a.username];
            }
          });
          toast(`Imported VIP server links for ${res.changed || count} account(s)!`, 'success');
          renderVipView();
        } catch (err) {
          toast('Failed to import VIP CSV: ' + err, 'error');
        }
      } else {
        toast('No valid username,vip_link rows found in CSV', 'error');
      }
    };
    reader.readAsText(file);
  });
  fileInput.click();
}

async function exportVipCsv(): Promise<void> {
  const rows = ['Username,Group,VIP Server Link'];
  (state.accounts || []).forEach(a => {
    const uname = `"${(a.username || '').replace(/"/g, '""')}"`;
    const grp = `"${(a.group || '').replace(/"/g, '""')}"`;
    const vip = `"${(a.vip_server || '').replace(/"/g, '""')}"`;
    rows.push(`${uname},${grp},${vip}`);
  });

  const csvContent = rows.join('\n');
  await saveTextFileNative({
    title: 'Export VIP Server Mappings',
    defaultPath: 'VIP_Server_Mappings.csv',
    filters: [{ name: 'CSV Files', extensions: ['csv'] }, { name: 'All Files', extensions: ['*'] }],
    content: csvContent,
    successMessage: 'Exported VIP server mappings to CSV'
  });
}


let lastInstancesDataJson: string = '';

async function renderInstancesView(forceRedraw: boolean = false): Promise<void> {
  const container = document.getElementById('instances-content-body');
  const statCount = document.getElementById('instances-stat-count');
  const statCrash = document.getElementById('instances-stat-crash-handlers') || document.getElementById('instances-stat-trim') || document.getElementById('instances-stat-mutex');
  const statCrashIcon = document.getElementById('instances-stat-crash-icon');
  const statCpu = document.getElementById('instances-stat-cpu');
  const statMem = document.getElementById('instances-stat-memory');
  const statusLabel = document.getElementById('multi-inst-status-label');
  const toggleBtn = document.getElementById('btn-toggle-multi-instance');

  try {
    const data = await apiService.getRunningInstances();
    const currentJson = JSON.stringify(data);
    if (!forceRedraw && lastInstancesDataJson === currentJson && container && container.children.length > 0) {
      return;
    }
    lastInstancesDataJson = currentJson;

    const gameInstances = data.instances || [];
    const crashHandlers = data.crashHandlers || [];

    if (statCount) statCount.textContent = `${gameInstances.length}`;

    let totalMem = 0;
    let totalCpu = data.totalCpuPercent ?? 0;
    if (Array.isArray(gameInstances)) {
      totalMem += gameInstances.reduce((acc, inst) => acc + (inst.memory_mb || 0), 0);
      if (totalCpu === 0) {
        totalCpu += gameInstances.reduce((acc, inst) => acc + (inst.cpu_percent || 0), 0);
      }
    }
    if (Array.isArray(crashHandlers)) {
      totalMem += crashHandlers.reduce((acc, inst) => acc + (inst.memory_mb || 0), 0);
      if (data.totalCpuPercent === undefined) {
        totalCpu += crashHandlers.reduce((acc, inst) => acc + (inst.cpu_percent || 0), 0);
      }
    }

    if (statCrash) {
      const count = crashHandlers.length;
      if (count > 0) {
        statCrash.textContent = `${count} Running`;
        statCrash.style.color = 'var(--red)';
        if (statCrashIcon) {
          statCrashIcon.style.background = 'rgba(239,68,68,0.15)';
          statCrashIcon.style.color = '#ef4444';
        }
      } else {
        statCrash.textContent = '0 Running';
        statCrash.style.color = 'var(--green)';
        if (statCrashIcon) {
          statCrashIcon.style.background = 'rgba(16,185,129,0.15)';
          statCrashIcon.style.color = '#10b981';
        }
      }
    }

    if (statCpu) {
      statCpu.textContent = `${totalCpu.toFixed(1)}%`;
      statCpu.style.color = totalCpu > 50 ? 'var(--red)' : totalCpu > 20 ? 'var(--yellow)' : 'var(--text-bright)';
    }

    if (statMem) {
      statMem.textContent = `${totalMem.toFixed(1)} MB`;
    }

    if (statusLabel) {
      statusLabel.textContent = data.multiInstanceEnabled ? 'ENABLED' : 'DISABLED';
    }
    if (toggleBtn) {
      toggleBtn.classList.toggle('active', data.multiInstanceEnabled);
    }

    if (container) {
      let mainContentHtml = '';

      if (gameInstances.length === 0 && crashHandlers.length === 0) {
        mainContentHtml = `
          <div class="empty-state" style="padding: 40px; text-align: center;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:48px;height:48px;opacity:0.4;margin-bottom:12px;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            <div style="font-size:16px; font-weight:600; margin-bottom:4px;">No Running Roblox Instances</div>
            <div style="font-size:13px; color:var(--text-muted);">Launch an account to monitor running Roblox processes here.</div>
          </div>
        `;
      } else {
        if (gameInstances.length === 0) {
          mainContentHtml += `
            <div class="empty-state" style="padding: 30px; text-align: center; margin-bottom: 16px;">
              <div style="font-size:14px; font-weight:600; margin-bottom:2px;">No Active Roblox Game Clients</div>
              <div style="font-size:12px; color:var(--text-muted);">No RobloxPlayerBeta.exe processes are currently active.</div>
            </div>
          `;
        } else {
          let rowsHtml = gameInstances.map(inst => {
            let accountHtml = `<span style="font-size:12px; color:var(--text-muted); font-style:italic;">Unassigned / External</span>`;
            if (inst.username) {
              const avatarSrc = inst.avatar_url || '/icon.ico';
              accountHtml = `
                <div style="display:inline-flex; align-items:center; justify-content:center; gap:8px;">
                  <img src="${avatarSrc}" class="instance-account-avatar" style="width:26px; height:26px; border-radius:50%; object-fit:cover; border:1px solid var(--border);" onerror="this.src='/icon.ico'" />
                  <div class="instance-account-name" style="display:flex; flex-direction:column; align-items:flex-start; line-height:1.2;">
                    <span style="font-weight:600; color:var(--text-bright); font-size:12.5px;">${inst.display_name || inst.username}</span>
                    <span style="font-size:10.5px; color:var(--text-muted);">@${inst.username}</span>
                  </div>
                </div>
              `;
            }

            let placeHtml = `<span style="font-size:12px; color:var(--text-muted); font-style:italic;">None</span>`;
            if (inst.place_id) {
              const matchedGame = (state.games || []).find(g => String(g.placeId) === String(inst.place_id));
              if (matchedGame && matchedGame.name) {
                placeHtml = `
                  <div style="display:inline-flex; flex-direction:column; align-items:center; justify-content:center; line-height:1.2;">
                    <span style="font-weight:600; color:var(--text-bright); font-size:12px; max-width:145px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${matchedGame.name}">${matchedGame.name}</span>
                    <code class="pid-badge" style="background:rgba(99,102,241,0.12); color:#6366f1; border-color:rgba(99,102,241,0.25); font-size:10.5px; padding:1px 5px; margin-top:2px;" title="Place ID: ${inst.place_id}">${inst.place_id}</code>
                  </div>
                `;
              } else {
                placeHtml = `
                  <code class="pid-badge" style="background:rgba(99,102,241,0.12); color:#6366f1; border-color:rgba(99,102,241,0.25); font-size:11px; padding:2px 6px;" title="Place ID: ${inst.place_id}">${inst.place_id}</code>
                `;
              }
            }

            return `
              <tr>
                <td style="text-align:center;"><code class="pid-badge">${inst.pid}</code></td>
                <td style="text-align:center;">${accountHtml}</td>
                <td style="text-align:center;">${placeHtml}</td>
                <td style="text-align:center; font-weight:600; color:var(--text-bright);">${inst.name}</td>
                <td style="text-align:center;"><span class="status-badge valid"><span class="dot"></span>${inst.status}</span></td>
                <td style="text-align:center;"><span style="font-weight:600; color:${(inst.cpu_percent || 0) > 25 ? 'var(--red)' : (inst.cpu_percent || 0) > 12 ? 'var(--yellow)' : 'var(--text-bright)'};">${(inst.cpu_percent ?? 0).toFixed(1)}%</span></td>
                <td style="text-align:center;">${inst.memory_mb.toFixed(1)} MB</td>
                <td style="text-align:center; white-space:nowrap;">
                  <div style="display:inline-flex; align-items:center; justify-content:center; gap:6px;">
                    <button class="btn btn-secondary btn-sm btn-relaunch-pid" data-pid="${inst.pid}" data-username="${inst.username || ''}" data-placeid="${inst.place_id || ''}" style="color:var(--primary); padding:4px 9px; font-size:11.5px; display:inline-flex; align-items:center; gap:4px; border-color:rgba(99,102,241,0.35);" title="Relaunch this specific instance">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/></svg>
                      Relaunch
                    </button>
                    <button class="btn btn-secondary btn-sm btn-kill-pid" data-pid="${inst.pid}" style="color:var(--red); padding:4px 9px; font-size:11.5px; display:inline-flex; align-items:center; gap:4px; border-color:rgba(239,68,68,0.3);" title="Terminate this process PID">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
                      Kill
                    </button>
                  </div>
                </td>
              </tr>
            `;
          }).join('');

          mainContentHtml += `
            <table class="instances-table">
              <thead>
                <tr>
                  <th style="width:80px; text-align:center;">PID</th>
                  <th style="width:180px; text-align:center;">Account Tied</th>
                  <th style="width:150px; text-align:center;">Place ID Tied</th>
                  <th style="text-align:center;">Process Name</th>
                  <th style="width:100px; text-align:center;">Status</th>
                  <th style="width:90px; text-align:center;">CPU</th>
                  <th style="width:100px; text-align:center;">Memory</th>
                  <th style="width:170px; text-align:center;">Action</th>
                </tr>
              </thead>
              <tbody>
                ${rowsHtml}
              </tbody>
            </table>
          `;
        }

        if (crashHandlers.length > 0) {
          let crashRowsHtml = crashHandlers.map(inst => `
            <tr>
              <td style="text-align:center;"><code class="pid-badge" style="background:rgba(239,68,68,0.12); color:var(--red); border-color:rgba(239,68,68,0.25);">${inst.pid}</code></td>
              <td style="text-align:center; font-weight:600; color:var(--text-bright);">${inst.name}</td>
              <td style="text-align:center;">${(inst.cpu_percent ?? 0).toFixed(1)}%</td>
              <td style="text-align:center;">${inst.memory_mb.toFixed(1)} MB</td>
              <td style="text-align:center;">
                <button class="btn btn-secondary btn-sm btn-kill-pid" data-pid="${inst.pid}" style="color:var(--red); padding:4px 10px; font-size:12px; border-color:rgba(239,68,68,0.3); display:inline-flex; align-items:center; justify-content:center;">
                  Kill PID
                </button>
              </td>
            </tr>
          `).join('');

          mainContentHtml += `
            <div style="margin-top:20px; border:1px solid rgba(239,68,68,0.25); background:rgba(239,68,68,0.03); border-radius:10px; padding:14px; overflow:hidden;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span style="display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px; border-radius:50%; background:rgba(239,68,68,0.15); color:var(--red);">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                  </span>
                  <div>
                    <span style="font-weight:700; font-size:13px; color:var(--text-bright);">Crash Handler Processes</span>
                  </div>
                </div>
                <button class="btn btn-danger btn-sm btn-purge-crash-handlers" style="font-size:11.5px; padding:4px 10px; display:flex; align-items:center; gap:6px;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  Kill All Crash Handlers
                </button>
              </div>
              <table class="instances-table">
                <thead>
                  <tr>
                    <th style="width:100px; text-align:center;">PID</th>
                    <th style="text-align:center;">Process Name</th>
                    <th style="width:100px; text-align:center;">CPU</th>
                    <th style="width:110px; text-align:center;">Memory</th>
                    <th style="width:120px; text-align:center;">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${crashRowsHtml}
                </tbody>
              </table>
            </div>
          `;
        }
      }

      container.innerHTML = mainContentHtml;

      container.querySelectorAll('.btn-relaunch-pid').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const target = e.currentTarget as HTMLElement;
          const pidAttr = target.getAttribute('data-pid');
          const username = target.getAttribute('data-username') || '';
          const placeId = target.getAttribute('data-placeid') || '';
          const pid = pidAttr ? parseInt(pidAttr, 10) : undefined;

          if (!username) {
            toast('Cannot relaunch unassigned external instance (no linked account)', 'error');
            return;
          }

          try {
            target.style.pointerEvents = 'none';
            target.style.opacity = '0.6';
            toast(`Relaunching Roblox instance for @${username}...`, 'info');
            const res = await apiService.relaunchInstance({ pid, username, placeId });
            if (res.success) {
              toast(res.message || `Relaunched instance for @${username}`, 'success');
              addLog(`Relaunched Roblox instance for @${username} (PID: ${pid || 'N/A'}, Place ID: ${placeId || 'None'})`, 'info');
              setTimeout(() => {
                renderInstancesView();
              }, 1500);
            } else {
              toast(res.error || 'Failed to relaunch instance', 'error');
            }
          } catch (err: any) {
            toast(`Relaunch error: ${err.message || err}`, 'error');
          } finally {
            target.style.pointerEvents = '';
            target.style.opacity = '';
          }
        });
      });

      container.querySelectorAll('.btn-purge-crash-handlers').forEach(btn => {
        btn.addEventListener('click', async () => {
          try {
            const res = await apiService.killAllCrashHandlers();
            if (res.success) {
              toast(`Terminated ${res.killed || 0} crash handler process(es)`, 'success');
              renderInstancesView();
            } else {
              toast(res.error || 'Failed to kill crash handlers', 'error');
            }
          } catch (err: any) {
            toast(`Error: ${err.message || err}`, 'error');
          }
        });
      });

      container.querySelectorAll('.btn-kill-pid').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const pidAttr = (e.currentTarget as HTMLElement).getAttribute('data-pid');
          if (!pidAttr) return;
          const pid = parseInt(pidAttr, 10);
          try {
            const res = await apiService.killInstanceProcess(pid);
            if (res.success) {
              toast(`Terminated process PID ${pid}`, 'success');
              renderInstancesView();
            } else {
              toast(res.error || 'Failed to kill process', 'error');
            }
          } catch (err: any) {
            toast(`Error: ${err.message || err}`, 'error');
          }
        });
      });
    }
  } catch (error: any) {
    console.error('Failed to fetch running instances:', error);
    if (container) {
      container.innerHTML = `<div class="empty-state" style="color:var(--red);">Error loading running instances: ${error.message || error}</div>`;
    }
  }
}

// Row menu handling
let currentMenuAccountId: number | null = null;

// Fullscreen Console Logic
let logBuffer: { message: string; type: 'info' | 'error' | 'success' | 'warning' | 'api' | 'get' | 'fetch' | 'options'; category?: string; timestamp: Date }[] = [];
let consoleFilterLevel: string = 'all';
let consoleSearchQuery: string = '';
let consoleAutoScroll: boolean = true;
let backendLogCache: { timestamp: string; time?: number; message: string; level: string; category?: string; source?: string }[] = [];

function addLog(message: string, type: 'info' | 'error' | 'success' | 'warning' | 'api' | 'get' | 'fetch' | 'options' = 'info', category: string = 'app'): void {
  const timestamp = new Date();
  logBuffer.push({ message, type, category, timestamp });

  if (logBuffer.length > 1000) {
    logBuffer = logBuffer.slice(-1000);
  }

  if (state.view === 'console') {
    renderConsoleView();
  }
}

async function fetchBackendLogs(): Promise<void> {
  try {
    const res = await apiService.getSystemLogs();
    if (res && res.success && Array.isArray(res.logs)) {
      backendLogCache = res.logs;
    }
  } catch (err) {
    // Silent catch
  }
}

function renderConsoleView(): void {
  const container = document.getElementById('console-view-body');
  if (!container) return;

  const combined: { timestamp: string; message: string; level: string; category?: string; source?: string; timeMs: number; seq: number }[] = [];
  let seq = 0;

  logBuffer.forEach(l => {
    combined.push({
      timestamp: l.timestamp.toLocaleTimeString(),
      message: l.message,
      level: l.type,
      category: l.category || 'app',
      source: 'app',
      timeMs: l.timestamp.getTime(),
      seq: seq++
    });
  });

  backendLogCache.forEach(bl => {
    let timeMs = typeof bl.time === 'number' && bl.time > 0 ? bl.time : 0;
    let displayTimestamp = bl.timestamp;
    if (timeMs > 0) {
      displayTimestamp = new Date(timeMs).toLocaleTimeString();
    } else if (bl.timestamp) {
      const match = bl.timestamp.match(/^(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d+))?$/);
      if (match) {
        const d = new Date();
        d.setHours(parseInt(match[1], 10), parseInt(match[2], 10), parseInt(match[3], 10), match[4] ? parseInt(match[4].slice(0, 3).padEnd(3, '0'), 10) : 0);
        timeMs = d.getTime();
        displayTimestamp = d.toLocaleTimeString();
      }
    }

    combined.push({
      timestamp: displayTimestamp || bl.timestamp,
      message: bl.message,
      level: bl.level || 'info',
      category: bl.category || 'system',
      source: 'backend',
      timeMs: timeMs || Date.now(),
      seq: seq++
    });
  });

  combined.sort((a, b) => {
    if (a.timeMs !== b.timeMs) {
      return a.timeMs - b.timeMs;
    }
    return a.seq - b.seq;
  });

  const filtered = combined.filter(entry => {
    const cat = (entry.category || '').toLowerCase();
    const lvl = (entry.level || '').toLowerCase();
    const src = (entry.source || '').toLowerCase();
    const msg = entry.message.toLowerCase();

    if (consoleFilterLevel === 'backend') {
      if (src !== 'backend') return false;
    } else if (consoleFilterLevel === 'api') {
      if (cat !== 'api' && cat !== 'get' && cat !== 'fetch' && cat !== 'options' && lvl !== 'api' && lvl !== 'get' && lvl !== 'fetch' && lvl !== 'options' && !msg.startsWith('get ') && !msg.startsWith('post ') && !msg.startsWith('options ') && !msg.startsWith('put ') && !msg.startsWith('delete ')) return false;
    } else if (consoleFilterLevel !== 'all') {
      if (lvl !== consoleFilterLevel.toLowerCase()) return false;
    }

    if (consoleSearchQuery) {
      const q = consoleSearchQuery.toLowerCase();
      const matchMsg = msg.includes(q);
      const matchLevel = lvl.includes(q);
      const matchCat = cat.includes(q);
      const matchSrc = src.includes(q);
      if (!matchMsg && !matchLevel && !matchCat && !matchSrc) return false;
    }

    return true;
  });

  container.innerHTML = '';

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="console-empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
        <div>No log entries match the current filter.</div>
      </div>
    `;
  } else {
    filtered.forEach((log, index) => {
      const row = document.createElement('div');
      const cat = (log.category || '').toLowerCase();
      const lvl = (log.level || '').toLowerCase();

      let displayBadge = 'INFO';
      let badgeClass = `badge-${lvl}`;

      if (cat === 'api' || cat === 'get' || cat === 'fetch' || cat === 'options' || lvl === 'api' || lvl === 'get' || lvl === 'fetch' || lvl === 'options') {
        displayBadge = 'API';
        badgeClass = 'badge-api';
      } else {
        displayBadge = log.level.toUpperCase();
      }

      row.className = `console-log-row log-${lvl} ${log.source === 'backend' ? 'log-source-backend' : ''}`;

      const numSpan = document.createElement('span');
      numSpan.className = 'console-log-num';
      numSpan.textContent = (index + 1).toString();

      const timeSpan = document.createElement('span');
      timeSpan.className = 'console-log-time';
      timeSpan.textContent = `[${log.timestamp}]`;

      const badgeSpan = document.createElement('span');
      badgeSpan.className = `console-log-badge ${badgeClass}`;
      badgeSpan.textContent = displayBadge;

      const srcSpan = document.createElement('span');
      srcSpan.className = `console-log-src src-${log.source}`;
      srcSpan.textContent = log.source === 'backend' ? 'BACKEND' : 'APP';

      const textSpan = document.createElement('span');
      textSpan.className = 'console-log-text';
      textSpan.textContent = log.message;

      row.appendChild(numSpan);
      row.appendChild(timeSpan);
      row.appendChild(badgeSpan);
      row.appendChild(srcSpan);
      row.appendChild(textSpan);
      container.appendChild(row);
    });
  }

  const countEl = document.getElementById('console-log-count');
  if (countEl) {
    countEl.textContent = `${filtered.length} entries shown (${combined.length} total)`;
  }

  if (consoleAutoScroll) {
    container.scrollTop = container.scrollHeight;
  }
}

let clientSettingsState: {
  exists: boolean;
  file_path: string;
  is_roblox_running: boolean;
  settings: Record<string, any>;
  specs: Record<string, any[]>;
  error?: string;
} | null = null;
let clientSettingsActiveTab = 'Graphics';
let clientSettingsSearchQuery = '';

const CLIENT_SETTINGS_DESCRIPTIONS: Record<string, string> = {
  GraphicsQualityLevel: 'Manual graphics rendering quality slider from 1 (lowest) to 21 (ultra).',
  GraphicsOptimizationMode: 'Preset graphics optimization profile (Auto, Performance, Quality).',
  MaxQualityEnabled: 'Force Roblox to render at maximum fidelity regardless of automatic throttling.',
  VignetteEnabled: 'Enable or disable the subtle dark vignette shading along screen edges.',
  FramerateCap: 'Target framerate / FPS cap. Set to 0 for uncapped or specify target (e.g. 60, 120, 144, 240).',
  Fullscreen: 'Launch Roblox client directly in borderless fullscreen mode.',
  StartMaximized: 'Start Roblox client window maximized by default upon launch.',
  MasterVolume: 'Primary master game volume and sound output level.',
  PartyVoiceVolume: 'Party and spatial voice chat volume level.',
  ComputerMovementMode: 'Keyboard and mouse character movement input mode.',
  ControlMode: 'Mouse cursor lock behavior and movement control scheme.',
  MouseSensitivity: 'General mouse cursor and look sensitivity multiplier.',
  MouseSensitivityFirstPersonX: 'Horizontal look sensitivity in first-person camera mode.',
  MouseSensitivityFirstPersonY: 'Vertical look sensitivity in first-person camera mode.',
  MouseSensitivityThirdPersonX: 'Horizontal look sensitivity in third-person camera mode.',
  MouseSensitivityThirdPersonY: 'Vertical look sensitivity in third-person camera mode.',
  GamepadCameraSensitivity: 'Look sensitivity when playing with an external gamepad or controller.',
  HapticStrength: 'Controller rumble vibration and haptic feedback intensity.',
  CameraMode: 'Default character camera tracking behavior (Classic or Follow).',
  CameraYInverted: 'Invert vertical Y-axis movement when rotating the camera.',
  ComputerCameraMovementMode: 'Camera rotation and orbital panning navigation scheme.',
  ReducedMotion: 'Reduces rapid screen shaking, swaying, and high-intensity motion effects.',
  ReadAloud: 'Text-to-speech accessibility narration for in-game dialog and menus.',
  AllTutorialsDisabled: 'Skip all initial onboarding and intro tutorial dialogs.',
  PreferredTextSize: 'System font and UI text size scale.',
  PreferredTransparency: 'Transparency reduction for background UI panels.',
  PlayerNamesEnabled: 'Display player usernames above character avatars in-game.',
  PerformanceStatsVisible: 'Display live ping, FPS, memory usage, and network diagnostics on-screen.',
  ChatVisible: 'Show or hide the in-game text chat window.',
  ChatTranslationEnabled: 'Enable automatic real-time translation of foreign language chat messages.',
  ChatTranslationToggleEnabled: 'Allow toggling chat translation directly from the in-game chat bar.',
  ChatTranslationLocale: 'Preferred target language locale code for incoming chat messages (e.g. en_us).',
  PlayerListVisible: 'Show or hide the player list leaderboard in the top-right corner.',
  BadgeVisible: 'Display notifications when achievement badges are unlocked.',
  PlayerHeight: 'Custom avatar height scale offset.',
  AppMode: 'Select an app mode. Your other devices will not be affected.',
  AppTheme: 'Explore themes to customize your experience in the Roblox client.',
  LaunchAtStartup: 'Launch Roblox automatically when I start my computer.',
  MinimizeToTray: 'Closing the window sends Roblox to the system tray instead of fully exiting.'
};

const CLIENT_SETTINGS_TAB_ICONS: Record<string, string> = {
  Graphics: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
  Audio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>',
  Controls: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M12 12h.01M16 10h.01M16 14h.01M6 10v4M4 12h4"/></svg>',
  Camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>',
  Accessibility: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>',
  Chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  Display: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
  'Device Preferences': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>'
};

function showRobloxGlobalSettingsModal(): void {
  state.revealed = {};
  state.previousView = state.view;
  state.view = 'clientsettings';
  renderAll();
}
(window as any).showRobloxGlobalSettingsModal = showRobloxGlobalSettingsModal;

async function renderClientSettingsView(): Promise<void> {
  const tabsContainer = document.getElementById('clientsettings-tabs');
  const contentArea = document.getElementById('clientsettings-content-inner');
  const backBtn = document.getElementById('btn-clientsettings-back');
  const searchInput = document.getElementById('clientsettings-search-input') as HTMLInputElement | null;

  if (backBtn) {
    backBtn.onclick = () => {
      state.view = (state.previousView as any) || 'settings';
      renderAll();
    };
  }

  if (searchInput && !searchInput.dataset.initialized) {
    searchInput.dataset.initialized = 'true';
    searchInput.value = clientSettingsSearchQuery;
    searchInput.addEventListener('input', () => {
      clientSettingsSearchQuery = searchInput.value.trim().toLowerCase();
      renderClientSettingsTabs(tabsContainer);
      renderClientSettingsContent(contentArea);
    });
  }

  if (!clientSettingsState) {
    if (contentArea) {
      contentArea.innerHTML = `
        <div style="padding:40px 0; text-align:center; color:var(--muted); font-size:13px;">
          <div class="cleaner-spinner" style="width:20px; height:20px; margin:0 auto 12px auto; display:block;"></div>
          Loading Roblox Client Settings...
        </div>
      `;
    }
    try {
      const res = await apiService.getRobloxGlobalSettings();
      clientSettingsState = res;
    } catch (err: any) {
      if (contentArea) {
        contentArea.innerHTML = `<div style="color:var(--red); padding:20px;">Failed to load Roblox global settings: ${err.message || err}</div>`;
      }
      return;
    }
  }

  renderClientSettingsTabs(tabsContainer);
  renderClientSettingsContent(contentArea);
}

let clientSettingsAutoSaveTimeout: any = null;
function queueClientSettingsAutoSave(): void {
  if (clientSettingsAutoSaveTimeout) {
    clearTimeout(clientSettingsAutoSaveTimeout);
  }
  clientSettingsAutoSaveTimeout = setTimeout(async () => {
    if (!clientSettingsState) return;
    try {
      await apiService.updateRobloxGlobalSettings(clientSettingsState.settings);
    } catch (e) {
      console.error('Roblox client settings auto-save failed:', e);
    }
  }, 400);
}

function renderClientSettingsTabs(container: HTMLElement | null): void {
  if (!container || !clientSettingsState) return;
  const data = clientSettingsState;
  const categories = Object.keys(data.specs || {});
  const query = clientSettingsSearchQuery;

  let html = '';
  categories.forEach(cat => {
    const specs = data.specs[cat] || [];
    let matchCount = specs.length;
    if (query) {
      matchCount = specs.filter(s => {
        const label = (s.label || s.key || '').toLowerCase();
        const desc = (CLIENT_SETTINGS_DESCRIPTIONS[s.key] || '').toLowerCase();
        return label.includes(query) || desc.includes(query) || cat.toLowerCase().includes(query);
      }).length;
    }

    const isActive = cat === clientSettingsActiveTab;
    const iconSvg = CLIENT_SETTINGS_TAB_ICONS[cat] || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>';

    html += `
      <button class="settings-tab-btn ${isActive ? 'active' : ''}" data-tab="${cat}" type="button" style="${query && matchCount === 0 ? 'opacity:0.4;' : ''}">
        ${iconSvg}
        <span>${cat}</span>
      </button>
    `;
  });

  container.innerHTML = html;

  const buttons = container.querySelectorAll('.settings-tab-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = (btn as HTMLElement).dataset.tab;
      if (tab) {
        clientSettingsActiveTab = tab;
        renderClientSettingsTabs(container);
        const contentArea = document.getElementById('clientsettings-content-inner');
        renderClientSettingsContent(contentArea);
      }
    });
  });
}

function renderClientSettingsContent(contentArea: HTMLElement | null): void {
  if (!contentArea || !clientSettingsState) return;
  const data = clientSettingsState;

  if (!data.exists) {
    contentArea.innerHTML = `
      <div style="padding:30px; text-align:center;">
        <div style="font-size:16px; font-weight:600; color:var(--text-bright); margin-bottom:8px;">GlobalBasicSettings_13.xml Not Found</div>
        <div style="color:var(--muted); font-size:13px; max-width:480px; margin:0 auto 20px auto;">
          Roblox client settings file was not detected at <code style="color:var(--accent);">${data.file_path || '%LOCALAPPDATA%\\Roblox'}</code>.
          Please ensure Roblox is installed and has been launched at least once.
        </div>
        <button class="btn btn-primary" id="btn-clientsettings-retry-load">Retry Detection</button>
      </div>
    `;
    const retryBtn = contentArea.querySelector('#btn-clientsettings-retry-load');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        clientSettingsState = null;
        renderClientSettingsView();
      });
    }
    return;
  }

  const query = clientSettingsSearchQuery;
  const specs = data.specs || {};
  let visibleSpecs: Array<{ spec: any; category: string }> = [];

  if (query) {
    Object.keys(specs).forEach(cat => {
      (specs[cat] || []).forEach((s: any) => {
        const label = (s.label || s.key || '').toLowerCase();
        const desc = (CLIENT_SETTINGS_DESCRIPTIONS[s.key] || '').toLowerCase();
        if (label.includes(query) || desc.includes(query) || cat.toLowerCase().includes(query)) {
          visibleSpecs.push({ spec: s, category: cat });
        }
      });
    });
  } else {
    const currentCategorySpecs = specs[clientSettingsActiveTab] || [];
    visibleSpecs = currentCategorySpecs.map((s: any) => ({ spec: s, category: clientSettingsActiveTab }));
  }

  const runningBannerHtml = data.is_roblox_running ? `
    <div style="margin-bottom:16px; font-size:12px; border:1px solid rgba(245,158,11,0.3); background:rgba(245,158,11,0.1); color:#f59e0b; padding:10px 14px; border-radius:8px; display:flex; align-items:center; gap:8px;">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;flex-shrink:0;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      <span>Roblox client is currently running. Setting changes may be overwritten until Roblox is closed.</span>
    </div>
  ` : '';

  const headerTitle = query ? `Search Results (${visibleSpecs.length})` : `${clientSettingsActiveTab} Settings`;
  const headerSubtitle = query
    ? `Showing all Roblox client settings matching "${query}".`
    : 'Configure roblox client settings';

  contentArea.innerHTML = `
    ${runningBannerHtml}

    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px; gap:16px; flex-wrap:wrap;">
      <div>
        <h2 style="margin:0;">${headerTitle}</h2>
        <p style="margin:4px 0 0 0; color:var(--muted); font-size:12.5px;">${headerSubtitle}</p>
        <div style="font-size:11px; color:var(--fg-3); margin-top:4px; font-family:monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:600px;">
          ${data.file_path || ''}
        </div>
      </div>

      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        ${!query ? `<button class="btn btn-secondary" id="btn-clientsettings-reset-cat" title="Reset all settings in this category to default">Reset Category</button>` : ''}
        <button class="btn btn-secondary" id="btn-clientsettings-reload" title="Reload settings from file">Reload</button>
      </div>
    </div>

    <div class="settings-card" id="clientsettings-card-wrap">
      ${visibleSpecs.length === 0 ? `
        <div style="padding:32px; text-align:center; color:var(--muted); font-size:13px;">
          No settings found matching "${query}".
        </div>
      ` : ''}
    </div>
  `;

  const cardWrap = contentArea.querySelector('#clientsettings-card-wrap');
  if (!cardWrap) return;

  visibleSpecs.forEach(({ spec }) => {
    const key = spec.key;
    const currentSettings = data.settings || {};
    const val = currentSettings[key] !== undefined ? currentSettings[key] : spec.default;
    const desc = CLIENT_SETTINGS_DESCRIPTIONS[key] || '';

    const row = document.createElement('div');
    row.className = 'setting-row';
    row.dataset.key = key;

    const infoWrap = document.createElement('div');
    infoWrap.className = 'setting-info';
    infoWrap.style.flex = '1';
    infoWrap.style.minWidth = '0';

    const labelRow = document.createElement('div');
    labelRow.style.display = 'flex';
    labelRow.style.alignItems = 'center';
    labelRow.style.gap = '8px';

    const label = document.createElement('span');
    label.className = 'setting-label';
    label.textContent = spec.label || key;
    labelRow.appendChild(label);

    infoWrap.appendChild(labelRow);

    if (desc) {
      const descEl = document.createElement('div');
      descEl.className = 'setting-desc';
      descEl.textContent = desc;
      infoWrap.appendChild(descEl);
    }

    row.appendChild(infoWrap);

    const controlWrap = document.createElement('div');
    controlWrap.style.display = 'flex';
    controlWrap.style.alignItems = 'center';
    controlWrap.style.gap = '10px';
    controlWrap.style.flexShrink = '0';

    const resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'btn btn-secondary btn-icon';
    resetBtn.style.padding = '4px';
    resetBtn.style.height = '26px';
    resetBtn.style.width = '26px';
    resetBtn.style.color = 'var(--muted)';
    resetBtn.title = `Reset to default (${spec.default})`;
    resetBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>';

    if (spec.control === 'bool') {
      const sw = document.createElement('button');
      sw.type = 'button';
      sw.className = `switch ${val ? 'on' : ''}`;
      sw.innerHTML = '<span class="knob"></span>';

      sw.addEventListener('click', () => {
        const nextVal = !data.settings[key];
        data.settings[key] = nextVal;
        sw.classList.toggle('on', nextVal);
        queueClientSettingsAutoSave();
      });

      resetBtn.addEventListener('click', () => {
        data.settings[key] = spec.default;
        sw.classList.toggle('on', !!spec.default);
        queueClientSettingsAutoSave();
      });

      controlWrap.appendChild(sw);
      controlWrap.appendChild(resetBtn);
    } else if (spec.control === 'combo') {
      const sel = document.createElement('select');
      sel.style.minWidth = '150px';
      (spec.options || []).forEach((opt: [string, any]) => {
        const optEl = document.createElement('option');
        optEl.value = String(opt[1]);
        optEl.textContent = opt[0];
        if (String(val) === String(opt[1])) optEl.selected = true;
        sel.appendChild(optEl);
      });

      sel.addEventListener('change', () => {
        const parsed = Number(sel.value);
        data.settings[key] = !isNaN(parsed) && typeof spec.default === 'number' ? parsed : sel.value;
        queueClientSettingsAutoSave();
      });

      resetBtn.addEventListener('click', () => {
        data.settings[key] = spec.default;
        sel.value = String(spec.default);
        queueClientSettingsAutoSave();
      });

      controlWrap.appendChild(sel);
      controlWrap.appendChild(resetBtn);
    } else if (spec.control === 'scale') {
      const isPercent = spec.display === 'percent';
      const isInt = spec.display === 'int';
      const step = isInt ? '1' : '0.05';
      const min = spec.minimum !== undefined ? String(spec.minimum) : '0';
      const max = spec.maximum !== undefined ? String(spec.maximum) : '1';

      const slider = document.createElement('input');
      slider.type = 'range';
      slider.min = min;
      slider.max = max;
      slider.step = step;
      slider.value = String(val);
      slider.style.width = '140px';

      const formatVal = (num: number) => isPercent ? `${Math.round(num * 100)}%` : isInt ? `${Math.round(num)}` : num.toFixed(2);

      const valLabel = document.createElement('span');
      valLabel.style.fontSize = '12px';
      valLabel.style.fontWeight = '600';
      valLabel.style.minWidth = '46px';
      valLabel.style.textAlign = 'right';
      valLabel.style.fontVariantNumeric = 'tabular-nums';
      valLabel.textContent = formatVal(Number(val));

      slider.addEventListener('input', () => {
        const num = Number(slider.value);
        data.settings[key] = num;
        valLabel.textContent = formatVal(num);
        queueClientSettingsAutoSave();
      });

      resetBtn.addEventListener('click', () => {
        data.settings[key] = spec.default;
        slider.value = String(spec.default);
        valLabel.textContent = formatVal(Number(spec.default));
        queueClientSettingsAutoSave();
      });

      controlWrap.appendChild(slider);
      controlWrap.appendChild(valLabel);
      controlWrap.appendChild(resetBtn);
    } else if (spec.control === 'spinbox') {
      const numInput = document.createElement('input');
      numInput.type = 'number';
      numInput.min = String(spec.minimum ?? 0);
      numInput.max = String(spec.maximum ?? 999);
      numInput.value = String(val);
      numInput.style.width = '80px';
      numInput.style.textAlign = 'right';

      numInput.addEventListener('change', () => {
        data.settings[key] = Number(numInput.value);
        queueClientSettingsAutoSave();
      });

      resetBtn.addEventListener('click', () => {
        data.settings[key] = spec.default;
        numInput.value = String(spec.default);
        queueClientSettingsAutoSave();
      });

      controlWrap.appendChild(numInput);
      controlWrap.appendChild(resetBtn);
    } else {
      const textInput = document.createElement('input');
      textInput.type = 'text';
      textInput.value = String(val || '');
      textInput.style.width = '140px';

      textInput.addEventListener('change', () => {
        data.settings[key] = textInput.value;
        queueClientSettingsAutoSave();
      });

      resetBtn.addEventListener('click', () => {
        data.settings[key] = spec.default;
        textInput.value = String(spec.default || '');
        queueClientSettingsAutoSave();
      });

      controlWrap.appendChild(textInput);
      controlWrap.appendChild(resetBtn);
    }

    row.appendChild(controlWrap);
    cardWrap.appendChild(row);
  });

  const resetCatBtn = contentArea.querySelector('#btn-clientsettings-reset-cat');
  if (resetCatBtn) {
    resetCatBtn.addEventListener('click', async () => {
      const confirmed = await showConfirmModal(
        'Reset Category Settings',
        `Are you sure you want to reset all settings in ${clientSettingsActiveTab} to default values?`,
        'Reset'
      );
      if (!confirmed) return;
      const catSpecs = data.specs[clientSettingsActiveTab] || [];
      catSpecs.forEach((s: any) => {
        data.settings[s.key] = s.default;
      });
      renderClientSettingsContent(contentArea);
      queueClientSettingsAutoSave();
      toast(`${clientSettingsActiveTab} settings reset to defaults.`);
    });
  }

  const reloadBtn = contentArea.querySelector('#btn-clientsettings-reload');
  if (reloadBtn) {
    reloadBtn.addEventListener('click', async () => {
      clientSettingsState = null;
      await renderClientSettingsView();
      toast('Roblox client settings reloaded from disk.');
    });
  }
}

let fastFlagsActiveTab: 'active' | 'presets' | 'add' | 'json' | 'maintenance' = 'active';
let fastFlagsSearchQuery = '';
let fastFlagsTypeFilter: 'all' | 'bool' | 'number' | 'string' = 'all';
let fastFlagsState: {
  success: boolean;
  exists: boolean;
  file_path: string;
  flags: Record<string, string>;
  error?: string;
} | null = null;
let fastFlagsIsDirty = false;

interface FastFlagSimpleOption {
  label: string;
  value: string;
}

interface FastFlagSliderConfig {
  title: string;
  minLabel: string;
  maxLabel: string;
  min: number;
  max: number;
  step?: number;
  formatValue?: (val: string | number) => string;
  getSliderValue: (flags: Record<string, string>) => string | number;
  applySlider: (flags: Record<string, string>, value: string) => void;
}

interface FastFlagPreset {
  id: string;
  name: string;
  category: 'Performance' | 'Graphics' | 'Multi-Instance' | 'Display & Engine';
  description: string;
  hasHelpIcon?: boolean;
  helpText?: string;
  type: 'toggle' | 'select';
  options?: FastFlagSimpleOption[];
  sliderConfig?: FastFlagSliderConfig;
  getValueBadge?: (flags: Record<string, string>) => string | null;
  getIsActive?: (flags: Record<string, string>) => boolean;
  getSelectedValue?: (flags: Record<string, string>) => string;
  applyToggle?: (flags: Record<string, string>, active: boolean) => void;
  applySelect?: (flags: Record<string, string>, value: string) => void;
}

const FASTFLAGS_PRESETS: FastFlagPreset[] = [
  {
    id: 'msaa_quality',
    name: 'Anti-Aliasing Quality (MSAA)',
    category: 'Graphics',
    description: 'Higher MSAA levels reduce jagged edges but may impact performance.',
    type: 'toggle',
    sliderConfig: {
      title: 'Drag to adjust MSAA anti-aliasing sample level.',
      minLabel: '1x (Basic)',
      maxLabel: '8x (Ultra Smooth)',
      min: 1,
      max: 4,
      step: 1,
      formatValue: (val) => {
        const map: Record<string, string> = { '1': '1x MSAA', '2': '2x MSAA', '3': '4x MSAA', '4': '8x Ultra MSAA' };
        return map[String(val)] || '4x MSAA';
      },
      getSliderValue: (flags) => {
        const v = flags['FIntDebugForceMSAASamples'];
        if (v === '8') return 4;
        if (v === '4') return 3;
        if (v === '2') return 2;
        if (v === '1') return 1;
        return 3;
      },
      applySlider: (flags, val) => {
        const map: Record<string, string> = { '1': '1', '2': '2', '3': '4', '4': '8' };
        flags['FIntDebugForceMSAASamples'] = map[String(val)] || '4';
      }
    },
    getValueBadge: (flags) => {
      const v = flags['FIntDebugForceMSAASamples'];
      if (!v || v === '0') return null;
      return `${v}x MSAA`;
    },
    getIsActive: (flags) => {
      const v = flags['FIntDebugForceMSAASamples'];
      return !!v && v !== '0';
    },
    applyToggle: (flags, active) => {
      if (active) {
        flags['FIntDebugForceMSAASamples'] = '4';
      } else {
        delete flags['FIntDebugForceMSAASamples'];
      }
    }
  },
  {
    id: 'fov_target',
    name: 'Camera Field of View (FOV)',
    category: 'Graphics',
    description: 'Customizes the camera perspective angle for wider peripheral vision (default is 70°).',
    type: 'toggle',
    sliderConfig: {
      title: 'Drag to adjust custom camera field of view angle.',
      minLabel: '60° (Narrow)',
      maxLabel: '120° (Ultra Wide)',
      min: 60,
      max: 120,
      step: 1,
      formatValue: (val) => `${val}° FOV`,
      getSliderValue: (flags) => {
        const v = flags['DFIntFieldOfView'] || flags['FIntCameraFOV'] || flags['DFIntCameraMinFov'];
        return v ? parseInt(v, 10) || 90 : 90;
      },
      applySlider: (flags, val) => {
        flags['DFIntFieldOfView'] = String(val);
        flags['FIntCameraFOV'] = String(val);
        flags['DFIntCameraMinFov'] = String(val);
        flags['DFIntCameraMaxFov'] = String(val);
      }
    },
    getValueBadge: (flags) => {
      const v = flags['DFIntFieldOfView'] || flags['FIntCameraFOV'] || flags['DFIntCameraMinFov'];
      if (!v || v === '70') return null;
      return `${v}° FOV`;
    },
    getIsActive: (flags) => {
      const v = flags['DFIntFieldOfView'] || flags['FIntCameraFOV'] || flags['DFIntCameraMinFov'];
      return !!v && v !== '70';
    },
    applyToggle: (flags, active) => {
      if (active) {
        flags['DFIntFieldOfView'] = '90';
        flags['FIntCameraFOV'] = '90';
        flags['DFIntCameraMinFov'] = '90';
        flags['DFIntCameraMaxFov'] = '90';
      } else {
        delete flags['DFIntFieldOfView'];
        delete flags['FIntCameraFOV'];
        delete flags['DFIntCameraMinFov'];
        delete flags['DFIntCameraMaxFov'];
      }
    }
  },
  {
    id: 'mesh_details',
    name: 'Mesh Details (LOD)',
    category: 'Graphics',
    description: 'Control mesh geometry detail distance to optimize performance or visual quality.',
    type: 'toggle',
    sliderConfig: {
      title: 'Drag to adjust mesh detail level for performance or fidelity.',
      minLabel: 'Performance',
      maxLabel: 'Quality',
      min: 1,
      max: 4,
      step: 1,
      formatValue: (val) => {
        const v = String(val);
        if (v === '4') return 'Ultra Detail';
        if (v === '3') return 'High Detail';
        if (v === '2') return 'Balanced Detail';
        return 'Fast / Low Detail';
      },
      getSliderValue: (flags) => {
        const val = flags['DFIntCSGLevelOfDetailSwitchingDistance'];
        if (val === '0') return 4;
        if (val === '500') return 3;
        if (val === '150') return 2;
        if (val === '50') return 1;
        return 4;
      },
      applySlider: (flags, val) => {
        if (val === '4') {
          flags['DFIntCSGLevelOfDetailSwitchingDistance'] = '0';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL12'] = '0';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL23'] = '0';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL34'] = '0';
        } else if (val === '3') {
          flags['DFIntCSGLevelOfDetailSwitchingDistance'] = '500';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL12'] = '1000';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL23'] = '2000';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL34'] = '4000';
        } else if (val === '2') {
          flags['DFIntCSGLevelOfDetailSwitchingDistance'] = '150';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL12'] = '300';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL23'] = '600';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL34'] = '1200';
        } else {
          flags['DFIntCSGLevelOfDetailSwitchingDistance'] = '50';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL12'] = '100';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL23'] = '200';
          flags['DFIntCSGLevelOfDetailSwitchingDistanceL34'] = '400';
        }
      }
    },
    getValueBadge: (flags) => {
      const val = flags['DFIntCSGLevelOfDetailSwitchingDistance'];
      if (val === undefined) return null;
      if (val === '0') return 'Ultra Mesh';
      if (val === '500') return 'High Mesh';
      if (val === '150') return 'Balanced Mesh';
      return 'Fast Mesh';
    },
    getIsActive: (flags) => flags['DFIntCSGLevelOfDetailSwitchingDistance'] !== undefined,
    applyToggle: (flags, active) => {
      if (active) {
        flags['DFIntCSGLevelOfDetailSwitchingDistance'] = '0';
        flags['DFIntCSGLevelOfDetailSwitchingDistanceL12'] = '0';
        flags['DFIntCSGLevelOfDetailSwitchingDistanceL23'] = '0';
        flags['DFIntCSGLevelOfDetailSwitchingDistanceL34'] = '0';
      } else {
        delete flags['DFIntCSGLevelOfDetailSwitchingDistance'];
        delete flags['DFIntCSGLevelOfDetailSwitchingDistanceL12'];
        delete flags['DFIntCSGLevelOfDetailSwitchingDistanceL23'];
        delete flags['DFIntCSGLevelOfDetailSwitchingDistanceL34'];
      }
    }
  },
  {
    id: 'override_graphics_level',
    name: 'Override Graphics Quality Level',
    category: 'Graphics',
    description: 'Locks graphics quality to a selected level. Roblox in-game slider will only affect render distance.',
    hasHelpIcon: true,
    helpText: 'Locks the graphics quality to a selected amount. Note: With this setting enabled, the graphics slider in the Roblox menu will only affect the render distance in a game.',
    type: 'toggle',
    sliderConfig: {
      title: 'Drag to adjust locked graphics rendering quality level.',
      minLabel: 'Level 1 (Lowest)',
      maxLabel: 'Level 21 (Ultra HD)',
      min: 1,
      max: 21,
      step: 1,
      formatValue: (val) => val === '21' ? 'Level 21 (Ultra HD)' : `Level ${val}`,
      getSliderValue: (flags) => {
        const val = flags['FIntRomarkStartWithGraphicQualityLevel'];
        return val ? parseInt(val, 10) || 21 : 21;
      },
      applySlider: (flags, val) => {
        if (val === '21') {
          flags['FIntRomarkStartWithGraphicQualityLevel'] = '21';
          flags['FFlagFixGraphicsQuality'] = 'True';
          flags['FFlagCommitToGraphicsQualityFix'] = 'True';
          flags['DFIntMaximumFreeMemoryAtStartupHeader'] = '2147483647';
        } else {
          flags['FIntRomarkStartWithGraphicQualityLevel'] = String(val);
          delete flags['FFlagFixGraphicsQuality'];
          delete flags['FFlagCommitToGraphicsQualityFix'];
          delete flags['DFIntMaximumFreeMemoryAtStartupHeader'];
        }
      }
    },
    getValueBadge: (flags) => {
      const val = flags['FIntRomarkStartWithGraphicQualityLevel'];
      if (!val) return null;
      return val === '21' ? 'Level 21 Ultra' : `Level ${val}`;
    },
    getIsActive: (flags) => {
      const val = flags['FIntRomarkStartWithGraphicQualityLevel'];
      return !!val && val !== 'disabled';
    },
    applyToggle: (flags, active) => {
      if (active) {
        flags['FIntRomarkStartWithGraphicQualityLevel'] = '21';
        flags['FFlagFixGraphicsQuality'] = 'True';
        flags['FFlagCommitToGraphicsQualityFix'] = 'True';
        flags['DFIntMaximumFreeMemoryAtStartupHeader'] = '2147483647';
      } else {
        delete flags['FIntRomarkStartWithGraphicQualityLevel'];
        delete flags['FFlagFixGraphicsQuality'];
        delete flags['FFlagCommitToGraphicsQualityFix'];
        delete flags['DFIntMaximumFreeMemoryAtStartupHeader'];
      }
    }
  },
  {
    id: 'fps_target',
    name: 'Framerate Limit (Target FPS)',
    category: 'Performance',
    description: 'Sets target scheduler framerate cap to unlock high refresh rates or limit background FPS.',
    type: 'toggle',
    sliderConfig: {
      title: 'Drag to set custom target scheduler framerate cap.',
      minLabel: '30 FPS',
      maxLabel: '360 FPS / Unlimited',
      min: 30,
      max: 360,
      step: 10,
      formatValue: (val) => parseInt(String(val), 10) >= 360 ? 'Unlimited (9999 FPS)' : `${val} FPS`,
      getSliderValue: (flags) => {
        const val = flags['DFIntTaskSchedulerTargetFps'];
        if (!val || val === '9999') return 360;
        const n = parseInt(val, 10);
        return isNaN(n) ? 144 : Math.min(360, Math.max(30, n));
      },
      applySlider: (flags, val) => {
        if (parseInt(val, 10) >= 360) {
          flags['DFIntTaskSchedulerTargetFps'] = '9999';
        } else {
          flags['DFIntTaskSchedulerTargetFps'] = String(val);
        }
      }
    },
    getValueBadge: (flags) => {
      const val = flags['DFIntTaskSchedulerTargetFps'];
      if (!val) return null;
      return val === '9999' ? 'Unlimited FPS' : `${val} FPS`;
    },
    getIsActive: (flags) => {
      const val = flags['DFIntTaskSchedulerTargetFps'];
      return !!val && val !== 'default' && val !== '60';
    },
    applyToggle: (flags, active) => {
      if (active) {
        flags['DFIntTaskSchedulerTargetFps'] = '144';
      } else {
        delete flags['DFIntTaskSchedulerTargetFps'];
      }
    }
  },
  {
    id: 'background_throttle',
    name: 'Background Window Throttling',
    category: 'Multi-Instance',
    description: 'Minimizes CPU & GPU load when Roblox client windows are minimized or in the background.',
    hasHelpIcon: true,
    helpText: 'Minimizes CPU and memory consumption when Roblox windows are running unfocused in the background.',
    type: 'toggle',
    sliderConfig: {
      title: 'Drag to set background FPS cap when client windows are minimized.',
      minLabel: '1 FPS (Max Power Savings)',
      maxLabel: '30 FPS (Balanced)',
      min: 1,
      max: 30,
      step: 1,
      formatValue: (val) => `${val} FPS background`,
      getSliderValue: (flags) => {
        const val = flags['DFIntTargetFpsMinimized'];
        return val ? parseInt(val, 10) || 1 : 1;
      },
      applySlider: (flags, val) => {
        flags['DFIntMinimizeMemory'] = '1';
        flags['DFIntMaxFrameBufferSize'] = '1';
        flags['DFIntTargetFpsMinimized'] = String(val);
      }
    },
    getValueBadge: (flags) => {
      if (flags['DFIntMinimizeMemory'] !== '1') return null;
      const fps = flags['DFIntTargetFpsMinimized'] || '1';
      return `${fps} FPS Throttled`;
    },
    getIsActive: (flags) => flags['DFIntMinimizeMemory'] === '1',
    applyToggle: (flags, active) => {
      if (active) {
        flags['DFIntMinimizeMemory'] = '1';
        flags['DFIntMaxFrameBufferSize'] = '1';
        flags['DFIntTargetFpsMinimized'] = '1';
      } else {
        delete flags['DFIntMinimizeMemory'];
        delete flags['DFIntMaxFrameBufferSize'];
        delete flags['DFIntTargetFpsMinimized'];
      }
    }
  },
  {
    id: 'pause_voxelizer',
    name: 'Pause Voxelizer',
    category: 'Graphics',
    description: 'Disables baked shadows to improve performance, but may cause lighting issues in some games.',
    type: 'toggle',
    getIsActive: (flags) => String(flags['DFFlagDebugPauseVoxelizer'] || '').toLowerCase() === 'true',
    applyToggle: (flags, active) => {
      if (active) {
        flags['DFFlagDebugPauseVoxelizer'] = 'True';
      } else {
        delete flags['DFFlagDebugPauseVoxelizer'];
      }
    }
  },
  {
    id: 'gray_sky',
    name: 'Gray Sky',
    category: 'Graphics',
    description: "Changes the game's sky to a solid gray color. Note: This will not work in games that have a custom skybox added by the developer.",
    type: 'toggle',
    getIsActive: (flags) => String(flags['FFlagDebugSkyGray'] || '').toLowerCase() === 'true',
    applyToggle: (flags, active) => {
      if (active) {
        flags['FFlagDebugSkyGray'] = 'True';
      } else {
        delete flags['FFlagDebugSkyGray'];
      }
    }
  },
  {
    id: 'disable_grass',
    name: 'Disable Grass',
    category: 'Graphics',
    description: "Removes Roblox's default grass textures. Note: This setting does not affect custom grass textures used by individual games.",
    type: 'toggle',
    getIsActive: (flags) => flags['FIntFRMMinGrassDistance'] === '0' || flags['FIntFRMMaxGrassDistance'] === '0',
    applyToggle: (flags, active) => {
      if (active) {
        flags['FIntFRMMinGrassDistance'] = '0';
        flags['FIntFRMMaxGrassDistance'] = '0';
      } else {
        delete flags['FIntFRMMinGrassDistance'];
        delete flags['FIntFRMMaxGrassDistance'];
      }
    }
  },
  {
    id: 'preserve_display_scaling',
    name: 'Preserve Rendering Quality With Display Scaling',
    category: 'Display & Engine',
    description: 'Roblox reduces your rendering quality depending on how your display is scaled in Windows.',
    hasHelpIcon: true,
    helpText: 'Roblox reduces your rendering quality depending on how your display is scaled in Windows.',
    type: 'toggle',
    getIsActive: (flags) => String(flags['DFFlagDisableDPIScale'] || '').toLowerCase() === 'true' || String(flags['FFlagDebugEnableDpiScale'] || '').toLowerCase() === 'false',
    applyToggle: (flags, active) => {
      if (active) {
        flags['DFFlagDisableDPIScale'] = 'True';
        flags['FFlagDebugEnableDpiScale'] = 'False';
      } else {
        delete flags['DFFlagDisableDPIScale'];
        delete flags['FFlagDebugEnableDpiScale'];
      }
    }
  },
  {
    id: 'rendering_mode',
    name: 'Rendering Mode',
    category: 'Display & Engine',
    description: 'Configure the rendering API used for Roblox. Note: Press Alt + Enter to enter exclusive fullscreen when using Direct3D as the rendering API.',
    hasHelpIcon: true,
    helpText: 'Configure the rendering API used for Roblox. Note: Press Alt + Enter to enter exclusive fullscreen when using Direct3D as the rendering API.',
    type: 'select',
    options: [
      { label: 'Direct3D11 (Default)', value: 'd3d11' },
      { label: 'Direct3D10', value: 'd3d10' },
      { label: 'Vulkan', value: 'vulkan' },
      { label: 'OpenGL', value: 'opengl' }
    ],
    getValueBadge: (flags) => {
      if (String(flags['FFlagDebugGraphicsPreferVulkan'] || '').toLowerCase() === 'true') return 'Vulkan';
      if (String(flags['FFlagDebugGraphicsPreferOpenGL'] || '').toLowerCase() === 'true') return 'OpenGL';
      if (String(flags['FFlagDebugGraphicsPreferD3D10'] || '').toLowerCase() === 'true') return 'D3D10';
      return null;
    },
    getSelectedValue: (flags) => {
      if (String(flags['FFlagDebugGraphicsPreferVulkan'] || '').toLowerCase() === 'true') return 'vulkan';
      if (String(flags['FFlagDebugGraphicsPreferOpenGL'] || '').toLowerCase() === 'true') return 'opengl';
      if (String(flags['FFlagDebugGraphicsPreferD3D10'] || '').toLowerCase() === 'true') return 'd3d10';
      return 'd3d11';
    },
    applySelect: (flags, val) => {
      delete flags['FFlagDebugGraphicsPreferD3D11'];
      delete flags['FFlagDebugGraphicsDisableDirect3D11'];
      delete flags['FFlagDebugGraphicsPreferD3D10'];
      delete flags['FFlagDebugGraphicsPreferVulkan'];
      delete flags['FFlagDebugGraphicsPreferOpenGL'];
      if (val === 'd3d11') {
        flags['FFlagDebugGraphicsPreferD3D11'] = 'True';
        flags['FFlagDebugGraphicsDisableDirect3D11'] = 'False';
      } else if (val === 'd3d10') {
        flags['FFlagDebugGraphicsPreferD3D10'] = 'True';
      } else if (val === 'vulkan') {
        flags['FFlagDebugGraphicsPreferVulkan'] = 'True';
        flags['FFlagDebugGraphicsDisableDirect3D11'] = 'True';
      } else if (val === 'opengl') {
        flags['FFlagDebugGraphicsPreferOpenGL'] = 'True';
        flags['FFlagDebugGraphicsDisableDirect3D11'] = 'True';
      }
    }
  },
  {
    id: 'lighting_technology',
    name: 'Lighting Engine Technology',
    category: 'Graphics',
    description: 'Forces lighting rendering model (Phase 3 Future Is Bright, Phase 2 ShadowMap, or Voxel).',
    type: 'select',
    options: [
      { label: 'Default (Engine Choice)', value: 'default' },
      { label: 'Future Is Bright (Phase 3)', value: 'fib3' },
      { label: 'ShadowMap (Phase 2)', value: 'shadowmap' },
      { label: 'Voxel (Phase 1)', value: 'voxel' }
    ],
    getValueBadge: (flags) => {
      if (String(flags['FFlagDebugForceFutureIsBrightPhase3'] || '').toLowerCase() === 'true') return 'Future (Phase 3)';
      if (String(flags['FFlagDebugForceFutureIsBrightPhase2'] || '').toLowerCase() === 'true') return 'ShadowMap (Phase 2)';
      if (String(flags['FFlagDebugForceVoxel'] || '').toLowerCase() === 'true') return 'Voxel (Phase 1)';
      return null;
    },
    getSelectedValue: (flags) => {
      if (String(flags['FFlagDebugForceFutureIsBrightPhase3'] || '').toLowerCase() === 'true') return 'fib3';
      if (String(flags['FFlagDebugForceFutureIsBrightPhase2'] || '').toLowerCase() === 'true') return 'shadowmap';
      if (String(flags['FFlagDebugForceVoxel'] || '').toLowerCase() === 'true') return 'voxel';
      return 'default';
    },
    applySelect: (flags, val) => {
      delete flags['FFlagDebugForceFutureIsBrightPhase3'];
      delete flags['FFlagDebugForceFutureIsBrightPhase2'];
      delete flags['FFlagDebugForceVoxel'];
      if (val === 'fib3') {
        flags['FFlagDebugForceFutureIsBrightPhase3'] = 'True';
      } else if (val === 'shadowmap') {
        flags['FFlagDebugForceFutureIsBrightPhase2'] = 'True';
      } else if (val === 'voxel') {
        flags['FFlagDebugForceVoxel'] = 'True';
      }
    }
  },
  {
    id: 'disable_post_fx',
    name: 'Disable Post-Processing (Clear Visuals)',
    category: 'Graphics',
    description: 'Removes motion blur, bloom, depth of field, and color correction for maximum visibility.',
    type: 'toggle',
    getIsActive: (flags) => String(flags['FFlagDisablePostFx'] || '').toLowerCase() === 'true',
    applyToggle: (flags, active) => {
      if (active) {
        flags['FFlagDisablePostFx'] = 'True';
        flags['FFlagDebugDisablePostFx'] = 'True';
      } else {
        delete flags['FFlagDisablePostFx'];
        delete flags['FFlagDebugDisablePostFx'];
      }
    }
  },
  {
    id: 'disable_shadows',
    name: 'Disable Shadows',
    category: 'Performance',
    description: 'Disables shadow maps and complex lighting effects to increase FPS on low-end systems.',
    type: 'toggle',
    getIsActive: (flags) => String(flags['FFlagDebugDisableShadowMapping'] || '').toLowerCase() === 'true',
    applyToggle: (flags, active) => {
      if (active) {
        flags['FFlagDebugDisableShadowMapping'] = 'True';
      } else {
        delete flags['FFlagDebugDisableShadowMapping'];
      }
    }
  },
  {
    id: 'disable_chrome_ui',
    name: 'Disable 2024 Chrome UI',
    category: 'Display & Engine',
    description: 'Disables modern topbar Chrome navigation interface and restores classic Roblox layout.',
    type: 'toggle',
    getIsActive: (flags) => String(flags['FFlagEnableInGameMenuChrome'] || '').toLowerCase() === 'false',
    applyToggle: (flags, active) => {
      if (active) {
        flags['FFlagEnableInGameMenuChrome'] = 'False';
        flags['FFlagEnableInGameMenuChromeABTest2'] = 'False';
      } else {
        delete flags['FFlagEnableInGameMenuChrome'];
        delete flags['FFlagEnableInGameMenuChromeABTest2'];
      }
    }
  },
  {
    id: 'disable_telemetry',
    name: 'Disable Telemetry & Crash Analytics',
    category: 'Performance',
    description: 'Disables background crash analytics and diagnostic telemetry reporting threads.',
    type: 'toggle',
    getIsActive: (flags) => String(flags['FFlagDebugDisableTelemetry'] || '').toLowerCase() === 'true',
    applyToggle: (flags, active) => {
      if (active) {
        flags['FFlagDebugDisableTelemetry'] = 'True';
        flags['FFlagDebugDisableAnalytics'] = 'True';
      } else {
        delete flags['FFlagDebugDisableTelemetry'];
        delete flags['FFlagDebugDisableAnalytics'];
      }
    }
  }
];

function detectFastFlagType(name: string, value: string): 'bool' | 'number' | 'string' {
  const v = (value || '').trim().toLowerCase();
  if (v === 'true' || v === 'false') return 'bool';
  if (/^(df|f)int/i.test(name) || /^(df|f)float/i.test(name)) return 'number';
  if (/^(df|f)flag/i.test(name) || /^dflag/i.test(name)) return 'bool';
  if (/^(df|f)string/i.test(name)) return 'string';
  if (/^-?\d+(\.\d+)?$/.test(v)) return 'number';
  return 'string';
}

async function fetchFastFlagsData(force = false): Promise<void> {
  if (fastFlagsState && !force) return;
  try {
    const data = await apiService.getRobloxFastFlags();
    fastFlagsState = data;
    fastFlagsIsDirty = false;
  } catch (err: any) {
    fastFlagsState = {
      success: false,
      exists: false,
      file_path: '',
      flags: {},
      error: err.message || String(err)
    };
  }
}

let fastFlagsAutoSaveTimeout: any = null;
function queueFastFlagsAutoSave(): void {
  if (fastFlagsAutoSaveTimeout) {
    clearTimeout(fastFlagsAutoSaveTimeout);
  }
  fastFlagsAutoSaveTimeout = setTimeout(async () => {
    if (!fastFlagsState || !fastFlagsIsDirty) return;
    try {
      await apiService.updateRobloxFastFlags(fastFlagsState.flags);
      fastFlagsIsDirty = false;
    } catch (e) {
      console.error('FastFlags auto-save failed:', e);
    }
  }, 400);
}

async function renderFastFlagsView(): Promise<void> {
  const tabsContainer = document.getElementById('fastflags-tabs');
  const contentArea = document.getElementById('fastflags-content-inner');
  const backBtn = document.getElementById('btn-fastflags-back');

  if (backBtn) {
    backBtn.onclick = () => {
      state.view = (state.previousView as any) || 'settings';
      renderAll();
    };
  }

  if (!fastFlagsState) {
    if (contentArea) {
      contentArea.innerHTML = `
        <div style="padding:40px 0; text-align:center; color:var(--muted); font-size:13px;">
          <div class="cleaner-spinner" style="width:20px; height:20px; margin:0 auto 12px auto; display:block;"></div>
          Loading Roblox FastFlags configuration...
        </div>
      `;
    }
    await fetchFastFlagsData();
  }

  const data = fastFlagsState;
  if (!data || !tabsContainer || !contentArea) return;

  tabsContainer.innerHTML = `
    <button class="settings-tab-btn ${fastFlagsActiveTab === 'active' ? 'active' : ''}" data-tab="active" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
      <span>Active Flags</span>
    </button>

    <button class="settings-tab-btn ${fastFlagsActiveTab === 'presets' ? 'active' : ''}" data-tab="presets" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
      <span>Presets</span>
    </button>

    <button class="settings-tab-btn ${fastFlagsActiveTab === 'add' ? 'active' : ''}" data-tab="add" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
      <span>Add FastFlag</span>
    </button>

    <button class="settings-tab-btn ${fastFlagsActiveTab === 'json' ? 'active' : ''}" data-tab="json" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
      <span>Raw JSON Editor</span>
    </button>

    <div class="settings-nav-divider"></div>

    <button class="settings-tab-btn ${fastFlagsActiveTab === 'maintenance' ? 'active' : ''}" data-tab="maintenance" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/></svg>
      <span>Storage</span>
    </button>
  `;

  const tabButtons = tabsContainer.querySelectorAll('.settings-tab-btn');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = (btn as HTMLElement).dataset.tab as any;
      if (tab) {
        fastFlagsActiveTab = tab;
        renderFastFlagsView();
      }
    });
  });

  if (fastFlagsActiveTab === 'active') {
    renderFastFlagsActiveTab(contentArea);
  } else if (fastFlagsActiveTab === 'presets') {
    renderFastFlagsPresetsTab(contentArea);
  } else if (fastFlagsActiveTab === 'add') {
    renderFastFlagsAddTab(contentArea);
  } else if (fastFlagsActiveTab === 'json') {
    renderFastFlagsJsonTab(contentArea);
  } else if (fastFlagsActiveTab === 'maintenance') {
    renderFastFlagsMaintenanceTab(contentArea);
  }
}

function renderFastFlagsActiveTab(contentArea: HTMLElement): void {
  if (!fastFlagsState) return;
  const data = fastFlagsState;

  const allKeys = Object.keys(data.flags || {}).sort();
  const boolCount = allKeys.filter(k => detectFastFlagType(k, String(data.flags[k])) === 'bool').length;
  const numCount = allKeys.filter(k => detectFastFlagType(k, String(data.flags[k])) === 'number').length;
  const strCount = allKeys.filter(k => detectFastFlagType(k, String(data.flags[k])) === 'string').length;

  contentArea.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px; gap:16px; flex-wrap:wrap;">
      <div>
        <h2>Roblox FastFlags Editor</h2>
        <p style="margin:0;">Configure custom engine variables and graphics tuning stored in ClientAppSettings.json.</p>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <button class="btn btn-secondary btn-sm" id="btn-fastflags-reload" title="Reload FastFlags from disk">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;margin-right:4px;"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          Reload
        </button>
        <button class="btn btn-secondary btn-sm" id="btn-fastflags-import-json">Import JSON</button>
        <button class="btn btn-secondary btn-sm" id="btn-fastflags-export-json">Export JSON</button>
      </div>
    </div>

    <div style="display:flex; gap:10px; align-items:center; margin-bottom:16px; flex-wrap:wrap;">
      <div class="search-wrap" style="flex:1; min-width:220px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        <input type="search" id="fastflags-search-input" placeholder="Search flags by name or value..." value="${fastFlagsSearchQuery}" autocomplete="off" />
      </div>

      <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
        <button class="pill ${fastFlagsTypeFilter === 'all' ? 'active' : ''}" data-type="all">All (${allKeys.length})</button>
        <button class="pill ${fastFlagsTypeFilter === 'bool' ? 'active' : ''}" data-type="bool">Boolean (${boolCount})</button>
        <button class="pill ${fastFlagsTypeFilter === 'number' ? 'active' : ''}" data-type="number">Numeric (${numCount})</button>
        <button class="pill ${fastFlagsTypeFilter === 'string' ? 'active' : ''}" data-type="string">String (${strCount})</button>
      </div>

      <button class="btn btn-primary btn-sm" id="btn-fastflags-add-quick">+ Add Flag</button>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">Active Flags List</div>
      <div class="settings-card" id="fastflags-table-rows"></div>
    </div>
  `;

  const reloadBtn = document.getElementById('btn-fastflags-reload');
  reloadBtn?.addEventListener('click', async () => {
    toast('Reloading FastFlags from disk...', 'info');
    await fetchFastFlagsData(true);
    renderFastFlagsView();
  });

  const searchInput = document.getElementById('fastflags-search-input') as HTMLInputElement | null;
  searchInput?.addEventListener('input', () => {
    fastFlagsSearchQuery = searchInput.value;
    renderFlagRows();
  });

  const filterPills = contentArea.querySelectorAll('.pill');
  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      const type = (pill as HTMLElement).dataset.type as any;
      if (type) {
        fastFlagsTypeFilter = type;
        renderFastFlagsActiveTab(contentArea);
      }
    });
  });

  const addQuickBtn = document.getElementById('btn-fastflags-add-quick');
  addQuickBtn?.addEventListener('click', () => {
    fastFlagsActiveTab = 'add';
    renderFastFlagsView();
  });

  const importJsonBtn = document.getElementById('btn-fastflags-import-json');
  importJsonBtn?.addEventListener('click', () => {
    fastFlagsActiveTab = 'json';
    renderFastFlagsView();
  });

  const exportJsonBtn = document.getElementById('btn-fastflags-export-json');
  exportJsonBtn?.addEventListener('click', async () => {
    const jsonStr = JSON.stringify(data.flags || {}, null, 2);
    await saveTextFileNative({
      title: 'Export ClientAppSettings.json',
      defaultPath: 'ClientAppSettings.json',
      filters: [{ name: 'JSON Files', extensions: ['json'] }, { name: 'All Files', extensions: ['*'] }],
      content: jsonStr,
      successMessage: 'Exported ClientAppSettings.json'
    });
  });

  const renderFlagRows = () => {
    const listContainer = document.getElementById('fastflags-table-rows');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    const currentFiltered = allKeys.filter(key => {
      const val = String(data.flags[key] || '');
      const matchesSearch = !fastFlagsSearchQuery ||
        key.toLowerCase().includes(fastFlagsSearchQuery.toLowerCase()) ||
        val.toLowerCase().includes(fastFlagsSearchQuery.toLowerCase());
      if (!matchesSearch) return false;
      if (fastFlagsTypeFilter === 'all') return true;
      return detectFastFlagType(key, val) === fastFlagsTypeFilter;
    });

    if (currentFiltered.length === 0) {
      listContainer.innerHTML = `
        <div style="padding:48px 20px; text-align:center; color:var(--muted); font-size:13px;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:36px;height:36px;margin:0 auto 12px auto;display:block;opacity:0.6;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <b style="color:var(--fg); font-size:14px; display:block; margin-bottom:4px;">No FastFlags Found</b>
          <span>${fastFlagsSearchQuery ? 'No flags match your current search query.' : 'No active FastFlags configured. Add flags or apply presets to get started!'}</span>
          <div style="margin-top:16px; display:flex; gap:10px; justify-content:center;">
            <button class="btn btn-secondary btn-sm" id="btn-empty-presets">Browse Presets</button>
            <button class="btn btn-primary btn-sm" id="btn-empty-add">+ Add FastFlag</button>
          </div>
        </div>
      `;
      document.getElementById('btn-empty-presets')?.addEventListener('click', () => {
        fastFlagsActiveTab = 'presets';
        renderFastFlagsView();
      });
      document.getElementById('btn-empty-add')?.addEventListener('click', () => {
        fastFlagsActiveTab = 'add';
        renderFastFlagsView();
      });
      return;
    }

    const INITIAL_LIMIT = 100;
    let currentLimit = INITIAL_LIMIT;

    const renderSlice = () => {
      listContainer.innerHTML = '';
      const slice = currentFiltered.slice(0, currentLimit);

      slice.forEach(key => {
        const val = String(data.flags[key] || '');
        const type = detectFastFlagType(key, val);
        const isTrue = val.toLowerCase() === 'true';

        const row = document.createElement('div');
        row.className = 'setting-row';

        let valControlHtml = '';
        if (type === 'bool') {
          valControlHtml = `
            <button class="switch ${isTrue ? 'on' : ''}" type="button" data-key="${key}" title="Toggle True / False">
              <span class="knob"></span>
            </button>
            <span style="font-size:12px; font-weight:600; font-family:'IBM Plex Mono', monospace; color:${isTrue ? 'var(--emerald)' : 'var(--muted)'}; min-width:42px;">${isTrue ? 'True' : 'False'}</span>
          `;
        } else if (type === 'number') {
          valControlHtml = `
            <input type="number" class="fastflags-val-input" data-key="${key}" value="${val}" style="text-align:right; width:140px;" />
          `;
        } else {
          valControlHtml = `
            <input type="text" class="fastflags-val-input" data-key="${key}" value="${val}" style="width:180px;" />
          `;
        }

        row.innerHTML = `
          <div class="setting-info" style="display:flex; align-items:center; gap:10px; flex:1; min-width:0;">
            <span class="flag-name-mono fastflags-name-text" title="Click to copy name" style="cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${key}</span>
            <span class="fastflags-type-badge ${type}">${type}</span>
          </div>
          <div class="setting-control" style="display:flex; align-items:center; gap:10px; flex-shrink:0;">
            ${valControlHtml}
            <button class="btn btn-secondary btn-sm btn-copy-name" title="Copy flag name" type="button" style="padding:4px 8px;">Copy</button>
            <button class="btn btn-secondary btn-sm btn-del-flag" title="Delete FastFlag" type="button" style="color:var(--red); padding:4px 8px;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        `;

        const nameEl = row.querySelector('.fastflags-name-text');
        nameEl?.addEventListener('click', () => {
          navigator.clipboard.writeText(key);
          toast(`Copied ${key}`, 'info');
        });

        const copyNameBtn = row.querySelector('.btn-copy-name');
        copyNameBtn?.addEventListener('click', () => {
          navigator.clipboard.writeText(key);
          toast(`Copied ${key}`, 'info');
        });

        const delBtn = row.querySelector('.btn-del-flag');
        delBtn?.addEventListener('click', () => {
          delete data.flags[key];
          fastFlagsIsDirty = true;
          queueFastFlagsAutoSave();
          toast(`Removed ${key}`, 'info');
          renderFastFlagsView();
        });

        if (type === 'bool') {
          const sw = row.querySelector('.switch');
          sw?.addEventListener('click', () => {
            const current = (data.flags[key] || '').toLowerCase() === 'true';
            data.flags[key] = current ? 'False' : 'True';
            fastFlagsIsDirty = true;
            queueFastFlagsAutoSave();
            renderFlagRows();
          });
        } else {
          const valInput = row.querySelector('.fastflags-val-input') as HTMLInputElement | null;
          valInput?.addEventListener('input', () => {
            if (valInput) {
              data.flags[key] = valInput.value;
              fastFlagsIsDirty = true;
              queueFastFlagsAutoSave();
            }
          });
        }

        listContainer.appendChild(row);
      });

      if (currentFiltered.length > currentLimit) {
        const moreBtn = document.createElement('button');
        moreBtn.className = 'btn btn-secondary';
        moreBtn.type = 'button';
        moreBtn.style.cssText = 'width: 100%; margin: 12px 0; padding: 10px; font-size:12px;';
        moreBtn.textContent = `Show more matching flags (${currentFiltered.length - currentLimit} remaining)...`;
        moreBtn.addEventListener('click', () => {
          currentLimit += 100;
          renderSlice();
        });
        listContainer.appendChild(moreBtn);
      }
    };

    renderSlice();
  };

  renderFlagRows();
}

let fastFlagsPresetsCategoryFilter: string = 'all';
let fastFlagsPresetsSearchQuery: string = '';

function renderFastFlagsPresetsTab(contentArea: HTMLElement): void {
  if (!fastFlagsState) return;
  const data = fastFlagsState;

  const categories = ['all', 'Graphics', 'Performance', 'Display & Engine', 'Multi-Instance'];

  contentArea.innerHTML = `
    <div class="fastflags-presets-container">
      <div class="fastflags-presets-header">
        <h1 class="fastflags-presets-title">Presets</h1>
        <div style="display:flex; gap:8px; align-items:center;">
          <button class="btn btn-secondary btn-sm" id="btn-presets-clear-all" style="color:var(--red);">Reset All Presets</button>
        </div>
      </div>

      <div class="fastflags-preset-filter-bar" style="margin-bottom:14px;">
        <div class="search-wrap" style="flex:1; min-width:200px;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <input type="search" id="presets-search-input" placeholder="Search presets..." value="${fastFlagsPresetsSearchQuery}" autocomplete="off" />
        </div>
        <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
          ${categories.map(cat => `
            <button class="pill ${fastFlagsPresetsCategoryFilter === cat ? 'active' : ''}" data-cat="${cat}">${cat === 'all' ? `All (${FASTFLAGS_PRESETS.length})` : cat}</button>
          `).join('')}
        </div>
      </div>

      <div class="fastflags-presets-list" id="fastflags-presets-list"></div>
    </div>
  `;

  const searchInput = document.getElementById('presets-search-input') as HTMLInputElement | null;
  searchInput?.addEventListener('input', () => {
    fastFlagsPresetsSearchQuery = searchInput.value;
    renderPresetsList();
  });

  const categoryPills = contentArea.querySelectorAll('.fastflags-preset-filter-bar .pill');
  categoryPills.forEach(pill => {
    pill.addEventListener('click', () => {
      const cat = (pill as HTMLElement).dataset.cat || 'all';
      fastFlagsPresetsCategoryFilter = cat;
      categoryPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      renderPresetsList();
    });
  });

  document.getElementById('btn-presets-clear-all')?.addEventListener('click', async () => {
    data.flags = {};
    fastFlagsIsDirty = false;
    await apiService.updateRobloxFastFlags({});
    toast('Reset all presets to default', 'info');
    renderFastFlagsPresetsTab(contentArea);
  });

  const renderPresetsList = () => {
    const list = document.getElementById('fastflags-presets-list');
    if (!list) return;
    list.innerHTML = '';

    const filtered = FASTFLAGS_PRESETS.filter(p => {
      if (fastFlagsPresetsCategoryFilter !== 'all' && p.category !== fastFlagsPresetsCategoryFilter) {
        return false;
      }
      if (fastFlagsPresetsSearchQuery) {
        const q = fastFlagsPresetsSearchQuery.toLowerCase();
        return p.name.toLowerCase().includes(q) || p.description.toLowerCase().includes(q);
      }
      return true;
    });

    if (filtered.length === 0) {
      list.innerHTML = `
        <div style="padding:40px 20px; text-align:center; color:var(--muted); font-size:13px; background:var(--card); border:1px solid var(--border); border-radius:8px;">
          <b style="color:var(--fg); font-size:14px; display:block; margin-bottom:4px;">No Presets Found</b>
          <span>No presets matched your current filter criteria.</span>
        </div>
      `;
      return;
    }

    filtered.forEach(preset => {
      const row = document.createElement('div');
      row.className = 'fastflags-preset-row';

      const main = document.createElement('div');
      main.className = 'fastflags-preset-main';

      const info = document.createElement('div');
      info.className = 'fastflags-preset-info';

      const label = document.createElement('div');
      label.className = 'fastflags-preset-label';

      const badgeText = preset.getValueBadge ? preset.getValueBadge(data.flags) : null;
      label.innerHTML = `
        <span>${preset.name}</span>
        ${badgeText ? `<span class="fastflags-preset-val-badge">${badgeText}</span>` : ''}
      `;

      const desc = document.createElement('p');
      desc.className = 'fastflags-preset-subtext';
      desc.textContent = preset.description;

      info.appendChild(label);
      info.appendChild(desc);
      main.appendChild(info);

      const control = document.createElement('div');
      control.className = 'fastflags-preset-control';

      let selectEl: HTMLSelectElement | null = null;
      let switchEl: HTMLButtonElement | null = null;
      let rangeInput: HTMLInputElement | null = null;
      let sliderSection: HTMLElement | null = null;
      let sliderTitleEl: HTMLElement | null = null;

      const updateBadge = () => {
        const liveBadge = label.querySelector('.fastflags-preset-val-badge');
        const newBadgeVal = preset.getValueBadge ? preset.getValueBadge(data.flags) : null;
        if (newBadgeVal) {
          if (liveBadge) {
            liveBadge.textContent = newBadgeVal;
          } else {
            const b = document.createElement('span');
            b.className = 'fastflags-preset-val-badge';
            b.textContent = newBadgeVal;
            label.insertBefore(b, label.children[1] || null);
          }
        } else if (liveBadge) {
          liveBadge.remove();
        }
      };

      const updateSliderTitle = () => {
        if (sliderTitleEl && preset.sliderConfig && rangeInput) {
          const curVal = rangeInput.value;
          const fVal = preset.sliderConfig.formatValue ? preset.sliderConfig.formatValue(curVal) : curVal;
          sliderTitleEl.textContent = `${preset.sliderConfig.title} (${fVal})`;
        }
      };

      const syncSelectFromFlags = () => {
        if (!selectEl || !preset.getSelectedValue) return;
        const currentVal = preset.getSelectedValue(data.flags);
        const optExists = Array.from(selectEl.options).some(o => o.value === currentVal);
        if (!optExists && currentVal && currentVal !== 'default' && currentVal !== 'disabled') {
          let customOpt = selectEl.querySelector('option[data-custom="true"]') as HTMLOptionElement | null;
          if (!customOpt) {
            customOpt = document.createElement('option');
            customOpt.setAttribute('data-custom', 'true');
            selectEl.appendChild(customOpt);
          }
          const labelText = preset.sliderConfig?.formatValue ? preset.sliderConfig.formatValue(currentVal) : currentVal;
          customOpt.value = currentVal;
          customOpt.textContent = labelText;
          selectEl.value = currentVal;
        } else {
          const customOpt = selectEl.querySelector('option[data-custom="true"]');
          if (customOpt && optExists) {
            customOpt.remove();
          }
          selectEl.value = currentVal;
        }
      };

      const syncSliderFromFlags = () => {
        if (!rangeInput || !preset.sliderConfig) return;
        const nextVal = preset.sliderConfig.getSliderValue(data.flags);
        rangeInput.value = String(nextVal);
        updateSliderTitle();
      };

      if (preset.sliderConfig) {
        sliderSection = document.createElement('div');
        sliderSection.className = 'fastflags-preset-slider-section';

        sliderTitleEl = document.createElement('div');
        sliderTitleEl.className = 'fastflags-preset-slider-title';

        const currentSliderVal = preset.sliderConfig.getSliderValue(data.flags);
        const formattedVal = preset.sliderConfig.formatValue ? preset.sliderConfig.formatValue(currentSliderVal) : String(currentSliderVal);
        sliderTitleEl.textContent = `${preset.sliderConfig.title} (${formattedVal})`;
        sliderSection.appendChild(sliderTitleEl);

        const sliderRow = document.createElement('div');
        sliderRow.className = 'fastflags-preset-slider-row';

        const minLabel = document.createElement('span');
        minLabel.className = 'fastflags-preset-slider-label';
        minLabel.textContent = preset.sliderConfig.minLabel;

        const maxLabel = document.createElement('span');
        maxLabel.className = 'fastflags-preset-slider-label';
        maxLabel.textContent = preset.sliderConfig.maxLabel;

        rangeInput = document.createElement('input');
        rangeInput.type = 'range';
        rangeInput.className = 'fastflags-preset-range';
        rangeInput.min = String(preset.sliderConfig.min);
        rangeInput.max = String(preset.sliderConfig.max);
        rangeInput.step = String(preset.sliderConfig.step || 1);
        rangeInput.value = String(currentSliderVal);

        rangeInput.addEventListener('input', () => {
          if (preset.sliderConfig && rangeInput) {
            preset.sliderConfig.applySlider(data.flags, rangeInput.value);
            updateSliderTitle();
          }
          syncSelectFromFlags();
          updateBadge();
          fastFlagsIsDirty = true;
          queueFastFlagsAutoSave();
        });

        sliderRow.appendChild(minLabel);
        sliderRow.appendChild(rangeInput);
        sliderRow.appendChild(maxLabel);
        sliderSection.appendChild(sliderRow);
      }

      if (preset.type === 'toggle') {
        const isActive = preset.getIsActive ? preset.getIsActive(data.flags) : false;
        switchEl = document.createElement('button');
        switchEl.className = `switch ${isActive ? 'on' : ''}`;
        switchEl.type = 'button';
        switchEl.setAttribute('aria-label', preset.name);
        switchEl.innerHTML = '<span class="knob"></span>';

        if (sliderSection) {
          sliderSection.style.display = isActive ? 'flex' : 'none';
        }

        switchEl.addEventListener('click', () => {
          const currentlyActive = switchEl?.classList.contains('on') ?? false;
          const nextActive = !currentlyActive;
          if (nextActive) {
            switchEl?.classList.add('on');
          } else {
            switchEl?.classList.remove('on');
          }
          if (sliderSection) {
            sliderSection.style.display = nextActive ? 'flex' : 'none';
          }
          if (preset.applyToggle) {
            preset.applyToggle(data.flags, nextActive);
          }
          syncSliderFromFlags();
          updateBadge();
          fastFlagsIsDirty = true;
          queueFastFlagsAutoSave();
        });

        control.appendChild(switchEl);
      } else if (preset.type === 'select') {
        const currentVal = preset.getSelectedValue ? preset.getSelectedValue(data.flags) : (preset.options?.[0]?.value || '');
        const sel = document.createElement('select');
        selectEl = sel;
        sel.className = 'fastflags-preset-select';
        sel.setAttribute('aria-label', preset.name);

        (preset.options || []).forEach(opt => {
          const optEl = document.createElement('option');
          optEl.value = opt.value;
          optEl.textContent = opt.label;
          if (opt.value === currentVal) {
            optEl.selected = true;
          }
          sel.appendChild(optEl);
        });

        syncSelectFromFlags();

        sel.addEventListener('change', () => {
          if (preset.applySelect) {
            preset.applySelect(data.flags, sel.value);
          }
          syncSliderFromFlags();
          updateBadge();
          fastFlagsIsDirty = true;
          queueFastFlagsAutoSave();
        });

        control.appendChild(sel);
      }

      main.appendChild(control);
      row.appendChild(main);
      if (sliderSection) {
        row.appendChild(sliderSection);
      }
      list.appendChild(row);
    });
  };

  renderPresetsList();
}

function renderFastFlagsAddTab(contentArea: HTMLElement): void {
  if (!fastFlagsState) return;
  const data = fastFlagsState;

  contentArea.innerHTML = `
    <div style="margin-bottom:20px;">
      <h2>Add Custom FastFlag</h2>
      <p style="margin:0;">Create a new variable entry for Roblox ClientAppSettings.json with automatic type detection and format verification.</p>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">Flag Parameters</div>
      <div class="settings-card">
        <div class="setting-row" style="flex-direction:column; align-items:flex-start; gap:8px;">
          <div class="setting-info">
            <div class="setting-label">Flag Name</div>
            <div class="setting-desc">Enter exact FastFlag variable name (e.g. DFIntTaskSchedulerTargetFps, FFlagDisablePostFx)</div>
          </div>
          <input type="text" id="add-flag-name" placeholder="e.g. DFIntTaskSchedulerTargetFps" style="width:100%; max-width:100%; height:34px; font-family:'IBM Plex Mono', monospace; font-size:13px;" />
          <div id="add-flag-validation" style="font-size:11.5px; font-weight:600; min-height:18px;"></div>
        </div>

        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-label">Value Type</div>
            <div class="setting-desc">Data format expected by the Roblox client engine</div>
          </div>
          <select id="add-flag-type" style="min-width:160px; height:32px;">
            <option value="bool">Boolean (True/False)</option>
            <option value="number">Number (Int/Float)</option>
            <option value="string">String (Text)</option>
          </select>
        </div>

        <div class="setting-row" style="border-bottom:none;">
          <div class="setting-info">
            <div class="setting-label">Flag Value</div>
            <div class="setting-desc">Value assigned to this variable</div>
          </div>
          <div id="add-flag-val-wrap" style="display:flex; align-items:center; gap:10px;"></div>
        </div>
      </div>
    </div>

    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
      <div style="font-size:12px; color:var(--muted);">
        Popular quick picks:
        <a href="javascript:void(0)" class="quick-flag-link" data-name="DFIntTaskSchedulerTargetFps" data-type="number" data-val="9999" style="color:var(--accent); text-decoration:underline; margin-left:6px;">TargetFps</a>,
        <a href="javascript:void(0)" class="quick-flag-link" data-name="FFlagDisablePostFx" data-type="bool" data-val="True" style="color:var(--accent); text-decoration:underline; margin-left:4px;">DisablePostFx</a>,
        <a href="javascript:void(0)" class="quick-flag-link" data-name="FFlagDebugDisableShadowMapping" data-type="bool" data-val="True" style="color:var(--accent); text-decoration:underline; margin-left:4px;">DisableShadows</a>
      </div>
      <button class="btn btn-primary" id="btn-add-flag-submit" disabled style="padding:8px 24px;" type="button">Add FastFlag</button>
    </div>
  `;

  const nameInput = document.getElementById('add-flag-name') as HTMLInputElement | null;
  const typeSelect = document.getElementById('add-flag-type') as HTMLSelectElement | null;
  const valWrap = document.getElementById('add-flag-val-wrap');
  const validationEl = document.getElementById('add-flag-validation');
  const submitBtn = document.getElementById('btn-add-flag-submit') as HTMLButtonElement | null;

  let currentBool = true;

  const renderValInput = () => {
    if (!valWrap || !typeSelect) return;
    valWrap.innerHTML = '';
    const type = typeSelect.value;
    if (type === 'bool') {
      const sw = document.createElement('button');
      sw.className = `switch ${currentBool ? 'on' : ''}`;
      sw.type = 'button';
      sw.innerHTML = '<span class="knob"></span>';
      sw.addEventListener('click', () => {
        currentBool = !currentBool;
        sw.className = `switch ${currentBool ? 'on' : ''}`;
        const lbl = valWrap.querySelector('.bool-lbl');
        if (lbl) lbl.textContent = currentBool ? 'True' : 'False';
      });
      const lbl = document.createElement('span');
      lbl.className = 'bool-lbl';
      lbl.style.cssText = 'font-size:12px; font-weight:600; font-family:monospace; color:var(--emerald);';
      lbl.textContent = currentBool ? 'True' : 'False';
      valWrap.appendChild(sw);
      valWrap.appendChild(lbl);
    } else if (type === 'number') {
      const num = document.createElement('input');
      num.type = 'number';
      num.id = 'add-flag-num-input';
      num.value = '0';
      num.style.cssText = 'width:160px; height:32px; font-family:monospace; text-align:right;';
      valWrap.appendChild(num);
    } else {
      const txt = document.createElement('input');
      txt.type = 'text';
      txt.id = 'add-flag-txt-input';
      txt.placeholder = 'Value string';
      txt.style.cssText = 'width:200px; height:32px; font-family:monospace;';
      valWrap.appendChild(txt);
    }
  };

  typeSelect?.addEventListener('change', renderValInput);
  renderValInput();

  const validate = async () => {
    if (!nameInput || !validationEl || !submitBtn) return;
    const name = nameInput.value.trim();
    if (!name) {
      validationEl.textContent = '';
      submitBtn.disabled = true;
      return;
    }

    if (/^(df|f)int/i.test(name) || /^(df|f)float/i.test(name)) {
      if (typeSelect && typeSelect.value !== 'number') {
        typeSelect.value = 'number';
        renderValInput();
      }
    } else if (/^(df|f)flag/i.test(name) || /^dflag/i.test(name)) {
      if (typeSelect && typeSelect.value !== 'bool') {
        typeSelect.value = 'bool';
        renderValInput();
      }
    } else if (/^(df|f)string/i.test(name)) {
      if (typeSelect && typeSelect.value !== 'string') {
        typeSelect.value = 'string';
        renderValInput();
      }
    }

    const res = await apiService.validateRobloxFastFlag(name);
    if (res.valid) {
      validationEl.textContent = '✓ ' + (res.message || 'Valid FastFlag name format');
      validationEl.style.color = 'var(--emerald)';
      submitBtn.disabled = false;
    } else {
      validationEl.textContent = '✗ ' + (res.message || 'Invalid flag name format');
      validationEl.style.color = 'var(--red)';
      submitBtn.disabled = true;
    }
  };

  nameInput?.addEventListener('input', validate);

  const doSubmit = () => {
    if (!nameInput || !typeSelect) return;
    const name = nameInput.value.trim();
    if (!name) return;
    const type = typeSelect.value;
    let valStr = '';

    if (type === 'bool') {
      valStr = currentBool ? 'True' : 'False';
    } else if (type === 'number') {
      const num = document.getElementById('add-flag-num-input') as HTMLInputElement | null;
      valStr = num?.value || '0';
    } else {
      const txt = document.getElementById('add-flag-txt-input') as HTMLInputElement | null;
      valStr = txt?.value || '';
    }

    data.flags[name] = valStr;
    fastFlagsIsDirty = true;
    toast(`Added flag ${name} = ${valStr}`, 'success');
    fastFlagsActiveTab = 'active';
    renderFastFlagsView();
  };

  submitBtn?.addEventListener('click', doSubmit);
  nameInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && submitBtn && !submitBtn.disabled) {
      doSubmit();
    }
  });

  const quickLinks = contentArea.querySelectorAll('.quick-flag-link');
  quickLinks.forEach(link => {
    link.addEventListener('click', () => {
      const name = (link as HTMLElement).dataset.name || '';
      const type = (link as HTMLElement).dataset.type || 'bool';
      const val = (link as HTMLElement).dataset.val || '';
      if (nameInput) nameInput.value = name;
      if (typeSelect) typeSelect.value = type;
      renderValInput();
      if (type === 'bool') currentBool = val === 'True';
      if (type === 'number') {
        const num = document.getElementById('add-flag-num-input') as HTMLInputElement | null;
        if (num) num.value = val;
      }
      validate();
    });
  });
}

function renderFastFlagsJsonTab(contentArea: HTMLElement): void {
  if (!fastFlagsState) return;
  const data = fastFlagsState;

  const initialJson = JSON.stringify(data.flags || {}, null, 2);

  contentArea.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; gap:16px; flex-wrap:wrap;">
      <div>
        <h2>Raw ClientAppSettings.json Editor</h2>
        <p style="margin:0;">Directly view and edit the raw JSON variables payload. Compatible with Bloxstrap and GitHub presets.</p>
      </div>
      <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <button class="btn btn-secondary btn-sm" id="btn-json-prettify" type="button">Format JSON</button>
        <button class="btn btn-secondary btn-sm" id="btn-json-minify" type="button">Minify</button>
        <button class="btn btn-secondary btn-sm" id="btn-json-copy" type="button">Copy JSON</button>
        <button class="btn btn-primary btn-sm" id="btn-json-apply" type="button">Apply JSON</button>
      </div>
    </div>

    <div id="json-error-banner" style="display:none; padding:8px 12px; margin-bottom:12px; background:rgba(240,87,92,0.15); border:1px solid var(--red); border-radius:6px; color:var(--red); font-size:12px;"></div>

    <textarea class="fastflags-json-textarea" id="fastflags-raw-textarea" spellcheck="false">${initialJson}</textarea>
  `;

  const textarea = document.getElementById('fastflags-raw-textarea') as HTMLTextAreaElement | null;
  const errorBanner = document.getElementById('json-error-banner');

  const setError = (msg: string) => {
    if (!errorBanner) return;
    if (msg) {
      errorBanner.textContent = 'JSON Syntax Error: ' + msg;
      errorBanner.style.display = 'block';
    } else {
      errorBanner.style.display = 'none';
    }
  };

  document.getElementById('btn-json-prettify')?.addEventListener('click', () => {
    if (!textarea) return;
    try {
      const parsed = JSON.parse(textarea.value);
      textarea.value = JSON.stringify(parsed, null, 2);
      setError('');
    } catch (e: any) {
      setError(e.message || String(e));
    }
  });

  document.getElementById('btn-json-minify')?.addEventListener('click', () => {
    if (!textarea) return;
    try {
      const parsed = JSON.parse(textarea.value);
      textarea.value = JSON.stringify(parsed);
      setError('');
    } catch (e: any) {
      setError(e.message || String(e));
    }
  });

  document.getElementById('btn-json-copy')?.addEventListener('click', () => {
    if (!textarea) return;
    navigator.clipboard.writeText(textarea.value);
    toast('JSON copied to clipboard!', 'success');
  });

  document.getElementById('btn-json-apply')?.addEventListener('click', () => {
    if (!textarea) return;
    try {
      const parsed = JSON.parse(textarea.value);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error('FastFlags payload must be a JSON object of key-value pairs.');
      }
      const newFlags: Record<string, string> = {};
      Object.entries(parsed).forEach(([k, v]) => {
        newFlags[k] = typeof v === 'boolean' ? (v ? 'True' : 'False') : String(v);
      });
      data.flags = newFlags;
      fastFlagsIsDirty = true;
      setError('');
      toast(`Applied ${Object.keys(newFlags).length} flags to active configuration!`, 'success');
      fastFlagsActiveTab = 'active';
      renderFastFlagsView();
    } catch (e: any) {
      setError(e.message || String(e));
      toast('Failed to parse JSON: check syntax error banner', 'error');
    }
  });
}

function renderFastFlagsMaintenanceTab(contentArea: HTMLElement): void {
  if (!fastFlagsState) return;
  const data = fastFlagsState;

  contentArea.innerHTML = `
    <div style="margin-bottom:20px;">
      <h2>Maintenance & Diagnostics</h2>
      <p style="margin:0;">Manage FastFlags configuration backups, local target storage paths, and reset utilities.</p>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">Target Storage Location</div>
      <div class="settings-card">
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-label">Config Target Path</div>
            <div class="setting-desc" style="word-break:break-all;">${data.file_path || 'Path unavailable'}</div>
          </div>
          <button class="btn btn-secondary btn-sm" id="btn-maint-copy-path" type="button" style="flex-shrink:0;">Copy Path</button>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <div class="settings-section-title">Database & Backup Operations</div>
      <div class="settings-card">
        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-label">Create Backup</div>
            <div class="setting-desc">Create a .backup snapshot of your active ClientAppSettings.json configuration</div>
          </div>
          <button class="btn btn-secondary btn-sm" id="btn-maint-backup" type="button">Create Backup</button>
        </div>

        <div class="setting-row">
          <div class="setting-info">
            <div class="setting-label">Restore from Backup</div>
            <div class="setting-desc">Restores your previous FastFlags configuration from the latest .backup snapshot</div>
          </div>
          <button class="btn btn-secondary btn-sm" id="btn-maint-restore" type="button">Restore</button>
        </div>

        <div class="setting-row" style="border-bottom:none;">
          <div class="setting-info">
            <div class="setting-label">Reset to Default</div>
            <div class="setting-desc">Deletes ClientAppSettings.json file and clears all active FastFlags</div>
          </div>
          <button class="btn btn-secondary btn-sm" id="btn-maint-reset" type="button" style="color:var(--red); border-color:rgba(240,87,92,0.3);">Reset to Default</button>
        </div>
      </div>
    </div>
  `;

  document.getElementById('btn-maint-copy-path')?.addEventListener('click', () => {
    if (data.file_path) {
      navigator.clipboard.writeText(data.file_path);
      toast('FastFlags target path copied to clipboard!', 'success');
    }
  });

  document.getElementById('btn-maint-backup')?.addEventListener('click', async () => {
    toast('Creating FastFlags backup...', 'info');
    const res = await apiService.backupRobloxFastFlags();
    if (res.success) {
      toast('Backup created successfully!', 'success');
    } else {
      toast(`Backup failed: ${res.error}`, 'error');
    }
  });

  document.getElementById('btn-maint-restore')?.addEventListener('click', async () => {
    toast('Restoring FastFlags from backup...', 'info');
    const res = await apiService.restoreRobloxFastFlags();
    if (res.success) {
      toast('Backup restored successfully!', 'success');
      await fetchFastFlagsData(true);
      renderFastFlagsView();
    } else {
      toast(`Restore failed: ${res.error}`, 'error');
    }
  });

  document.getElementById('btn-maint-reset')?.addEventListener('click', async () => {
    const confirmed = await showConfirmModal('Reset FastFlags', 'Are you sure you want to reset all FastFlags? This will remove ClientAppSettings.json.', 'Reset All', true);
    if (confirmed) {
      toast('Resetting FastFlags...', 'info');
      const res = await apiService.resetRobloxFastFlags();
      if (res.success) {
        toast('FastFlags reset to default!', 'success');
        await fetchFastFlagsData(true);
        renderFastFlagsView();
      } else {
        toast(`Reset failed: ${res.error}`, 'error');
      }
    }
  });
}

let currentAboutTab: 'overview' | 'whatsnew' = 'overview';
let cachedGithubReleases: any[] | null = null;
let isFetchingGithubReleases = false;
let githubReleasesError: string | null = null;

function formatReleaseMarkdown(raw: string): string {
  if (!raw || !raw.trim()) {
    return '<p style="color:var(--muted); font-style:italic; margin:0;">No release notes provided for this build.</p>';
  }

  let text = raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  text = text.replace(/^### (.*$)/gim, '<h4 style="font-size:13px; font-weight:700; color:var(--text-bright); margin:12px 0 6px 0;">$1</h4>');
  text = text.replace(/^## (.*$)/gim, '<h3 style="font-size:14px; font-weight:700; color:var(--text-bright); margin:14px 0 6px 0;">$1</h3>');
  text = text.replace(/^# (.*$)/gim, '<h2 style="font-size:15px; font-weight:700; color:var(--text-bright); margin:16px 0 8px 0;">$1</h2>');

  text = text.replace(/\*\*\*(.*?)\*\*\*/gim, '<b><i>$1</i></b>');
  text = text.replace(/\*\*(.*?)\*\*/gim, '<b>$1</b>');
  text = text.replace(/\*(.*?)\*/gim, '<i>$1</i>');

  text = text.replace(/```([\s\S]*?)```/gim, '<pre style="background:var(--bg-2); border:1px solid var(--border); border-radius:6px; padding:8px 12px; font-size:11.5px; overflow-x:auto; margin:8px 0; font-family:var(--font-mono); color:var(--fg);">$1</pre>');
  text = text.replace(/`([^`]+)`/gim, '<code style="background:var(--bg-2); border:1px solid var(--border); border-radius:4px; padding:1px 5px; font-size:11.5px; font-family:var(--font-mono); color:var(--primary);">$1</code>');

  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/gim, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:var(--primary); text-decoration:underline;">$1</a>');

  text = text.replace(/^[\*\-\+] (.*$)/gim, '<li style="margin-left:18px; margin-bottom:3px; list-style-type:disc;">$1</li>');

  text = text.replace(/\n\n+/g, '<div style="height:8px;"></div>');
  text = text.replace(/\n/g, '<br/>');

  return text;
}

const FALLBACK_APP_RELEASES = [
  {
    name: 'Version 3.0.0 — Major Architecture & UI Overhaul',
    tag_name: 'v3.0.0',
    published_at: '2026-09-20T12:00:00Z',
    html_url: 'https://github.com/hackyue/ForkedRobloxAccountManager/releases',
    body: `### 🚀 Highlights & Major Features
- **All-New Tauri Desktop Architecture**: Ultra-lightweight, high-performance desktop client with native system tray integration.
- **Enhanced Account Management**: Seamless cookie, user:pass, browser, and Quick Sign-In login flows.
- **Multi-Instance & Mutex Engine**: Unlimited concurrent Roblox instances with crash recovery and auto memory trimmer.
- **Roblox Swap & Trace Cleaner**: Network adapter MAC address spoofing, hardware ID cleaner, and cached trace purger.
- **Auto Rejoin & Anti-AFK**: Background heartbeats with configurable keypresses and smart reconnection routines.
- **FastFlags & Bootstrappers Manager**: Advanced FastFlag presets, lighting tweaks, and integrated bootstrapper configurations.
- **12 Custom Theme Palettes**: Vibrant UI themes with custom color wash icons and full layout customization.`
  }
];

async function loadGithubReleases(force = false): Promise<void> {
  if (isFetchingGithubReleases) return;
  if (cachedGithubReleases && !force) return;

  isFetchingGithubReleases = true;
  githubReleasesError = null;

  if (currentAboutTab === 'whatsnew') {
    renderAboutView();
  }

  try {
    try {
      const backendRes = await apiService.getGithubReleases(force);
      if (backendRes && backendRes.success && Array.isArray(backendRes.releases) && backendRes.releases.length > 0) {
        cachedGithubReleases = backendRes.releases;
        return;
      }
    } catch (_e) {
    }

    try {
      const res = await fetch('https://api.github.com/repos/hackyue/ForkedRobloxAccountManager/releases', {
        headers: {
          'Accept': 'application/vnd.github.v3+json'
        }
      });

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          cachedGithubReleases = data;
          return;
        }
      }
    } catch (err: any) {
    }

    if (!cachedGithubReleases || cachedGithubReleases.length === 0) {
      cachedGithubReleases = FALLBACK_APP_RELEASES;
    }
  } finally {
    isFetchingGithubReleases = false;
    if (currentAboutTab === 'whatsnew') {
      renderAboutView();
    }
  }
}

function renderAboutView(): void {
  const container = document.getElementById('about-content-body');
  if (!container) return;

  const tabBtnOverview = document.getElementById('btn-about-tab-overview');
  const tabBtnWhatsnew = document.getElementById('btn-about-tab-whatsnew');
  const backBtn = document.getElementById('btn-about-back');

  if (backBtn && !backBtn.dataset.initialized) {
    backBtn.dataset.initialized = 'true';
    backBtn.addEventListener('click', () => {
      state.revealed = {};
      state.view = (state.previousView as any) || 'accounts';
      renderAll();
    });
  }

  if (tabBtnOverview) {
    tabBtnOverview.className = 'btn btn-sm ' + (currentAboutTab === 'overview' ? 'btn-primary' : 'btn-secondary');
    if (!tabBtnOverview.dataset.initialized) {
      tabBtnOverview.dataset.initialized = 'true';
      tabBtnOverview.addEventListener('click', () => {
        currentAboutTab = 'overview';
        renderAboutView();
      });
    }
  }

  if (tabBtnWhatsnew) {
    tabBtnWhatsnew.className = 'btn btn-sm ' + (currentAboutTab === 'whatsnew' ? 'btn-primary' : 'btn-secondary');
    if (!tabBtnWhatsnew.dataset.initialized) {
      tabBtnWhatsnew.dataset.initialized = 'true';
      tabBtnWhatsnew.addEventListener('click', () => {
        currentAboutTab = 'whatsnew';
        renderAboutView();
        if (!cachedGithubReleases && !isFetchingGithubReleases) {
          loadGithubReleases();
        }
      });
    }
  }

  container.innerHTML = '';

  if (currentAboutTab === 'overview') {
    container.innerHTML = `
      <div class="about-links-chips">
        <a href="https://framrbx.netlify.app/home" target="_blank" rel="noopener noreferrer" class="about-link-chip" title="Official Website">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          <span>Website</span>
        </a>
        <a href="https://framrbx.netlify.app/wiki" target="_blank" rel="noopener noreferrer" class="about-link-chip" title="Documentation & Wiki">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
          <span>Documentation</span>
        </a>
        <a href="https://github.com/hackyue/ForkedRobloxAccountManager" target="_blank" rel="noopener noreferrer" class="about-link-chip github" title="GitHub Repository">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
          <span>GitHub</span>
        </a>
        <a href="https://discord.gg/SpMTxg8YjJ" target="_blank" rel="noopener noreferrer" class="about-link-chip discord" title="Discord Community">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.093.252-.19.37-.287a.075.075 0 0 1 .078-.01c3.927 1.793 8.18 1.793 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.077.077 0 0 1-.006.128c-.598.35-1.22.648-1.873.892-.043.016-.062.066-.041.107.356.698.767 1.363 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
          <span>Discord Server</span>
        </a>
        <a href="https://www.youtube.com/@hackyue" target="_blank" rel="noopener noreferrer" class="about-link-chip youtube" title="YouTube Channel">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.56 49.56 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/><polygon points="10 15 15 12 10 9 10 15"/></svg>
          <span>YouTube</span>
        </a>
        <a href="https://github.com/hackyue/ForkedRobloxAccountManager/issues/new" target="_blank" rel="noopener noreferrer" class="about-link-chip" title="Report an Issue or Suggestion">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span>Report Issue</span>
        </a>
      </div>

      <div class="about-specs-grid">
        <div class="about-spec-card" id="btn-about-card-release" style="cursor:pointer;" title="View Release Changelogs">
          <div class="about-spec-info">
            <span class="about-spec-val">Version 3.0.0</span>
            <span style="font-size:12px; color:var(--muted); margin-top:2px;">Click to view What's New changelogs &rarr;</span>
          </div>
        </div>
      </div>

      <div style="display:flex; flex-direction:column; gap:18px;">
        <div>
          <h3 style="font-size:15px; font-weight:700; color:var(--text-bright); margin:0;">Credits & Attributions</h3>
          <p style="font-size:12.5px; color:var(--muted); margin:4px 0 0 0;">Forked Roblox Account Manager has used or based features off of these repositories/apis:</p>
        </div>

        <div>
          <h4 style="font-size:12px; font-weight:700; color:var(--text-bright); text-transform:uppercase; letter-spacing:0.5px; margin:0 0 10px 0; opacity:0.85;">Repositories & Codebases</h4>
          <div class="about-credits-grid">
            <div class="about-credit-card">
              <div class="about-credit-header">
                <h4 class="about-credit-name">Roblox Account Manager</h4>
                <span class="about-credit-author">by ic3w0lf22</span>
              </div>
              <p class="about-credit-desc">Used for account manager mechanics, Multi-Roblox mutex handling, server join protocol integration, and account encryption concepts.</p>
              <a href="https://github.com/ic3w0lf22/roblox-account-manager/releases" target="_blank" rel="noopener noreferrer" class="about-credit-link">
                <span>View Releases</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>

            <div class="about-credit-card">
              <div class="about-credit-header">
                <h4 class="about-credit-name">RobloxAccountManager</h4>
                <span class="about-credit-author">by evanovar</span>
              </div>
              <p class="about-credit-desc">This application was forked from this repository, which provided the foundational UI layout, account list workflows, and core manager structure.</p>
              <a href="https://github.com/evanovar/RobloxAccountManager" target="_blank" rel="noopener noreferrer" class="about-credit-link">
                <span>View Repository</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>

            <div class="about-credit-card">
              <div class="about-credit-header">
                <h4 class="about-credit-name">Bloxstrap</h4>
                <span class="about-credit-author">by bloxstraplabs</span>
              </div>
              <p class="about-credit-desc">Used for FastFlag configuration systems, bootstrapper launcher arguments, client UX concepts, and Discord Rich Presence mechanics.</p>
              <a href="https://github.com/bloxstraplabs/bloxstrap" target="_blank" rel="noopener noreferrer" class="about-credit-link">
                <span>View Repository</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>

            <div class="about-credit-card">
              <div class="about-credit-header">
                <h4 class="about-credit-name">Froststrap</h4>
                <span class="about-credit-author">by Froststrap Team</span>
              </div>
              <p class="about-credit-desc">Used for FastFlag presets, rendering engine tweaks, bootstrapper customization options, and client tuning parameters.</p>
              <a href="https://github.com/Froststrap/Froststrap" target="_blank" rel="noopener noreferrer" class="about-credit-link">
                <span>View Repository</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>

            <div class="about-credit-card">
              <div class="about-credit-header">
                <h4 class="about-credit-name">RBLXSwap</h4>
                <span class="about-credit-author">by focat69</span>
              </div>
              <p class="about-credit-desc">Used for Roblox Swap feature implementation, high-speed account/group sniper logic, and token validation routines.</p>
              <a href="https://github.com/focat69/rblxswap/releases/tag/v0.2.0" target="_blank" rel="noopener noreferrer" class="about-credit-link">
                <span>View Release v0.2.0</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>
          </div>
        </div>

        <div>
          <h4 style="font-size:12px; font-weight:700; color:var(--text-bright); text-transform:uppercase; letter-spacing:0.5px; margin:0 0 10px 0; opacity:0.85;">APIs & Web Services</h4>
          <div class="about-credits-grid">
            <div class="about-credit-card">
              <div class="about-credit-header">
                <h4 class="about-credit-name">WhatExpsAre.Online</h4>
                <span class="about-credit-author">by WhatExpsAre.Online API</span>
              </div>
              <p class="about-credit-desc">Used for live exploit/executor status data, client update tracking, and Roblox version monitoring endpoints.</p>
              <a href="https://whatexpsare.online/" target="_blank" rel="noopener noreferrer" class="about-credit-link">
                <span>View API Service</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>

            <div class="about-credit-card">
              <div class="about-credit-header">
                <h4 class="about-credit-name">Bloxgen</h4>
                <span class="about-credit-author">by Bloxgen API</span>
              </div>
              <p class="about-credit-desc">Used for generating Roblox accounts via their automated account generation API.</p>
              <a href="https://bloxgen.net/" target="_blank" rel="noopener noreferrer" class="about-credit-link">
                <span>View Website</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>
          </div>
        </div>
      </div>
    `;

    document.getElementById('btn-about-card-release')?.addEventListener('click', () => {
      currentAboutTab = 'whatsnew';
      renderAboutView();
      if (!cachedGithubReleases && !isFetchingGithubReleases) {
        loadGithubReleases();
      }
    });
  } else if (currentAboutTab === 'whatsnew') {
    if (isFetchingGithubReleases && !cachedGithubReleases) {
      container.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:60px 20px; gap:14px; text-align:center;">
          <div class="spinner" style="width:32px; height:32px; border-width:3px;"></div>
          <div style="font-size:14px; font-weight:600; color:var(--fg);">Fetching release notes from GitHub...</div>
          <div style="font-size:12px; color:var(--muted);">Querying https://api.github.com/repos/hackyue/ForkedRobloxAccountManager/releases</div>
        </div>
      `;
    } else if (githubReleasesError && (!cachedGithubReleases || cachedGithubReleases.length === 0)) {
      container.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:50px 20px; gap:12px; text-align:center; background:var(--card); border:1px solid var(--border); border-radius:12px;">
          <div style="width:44px; height:44px; border-radius:50%; background:rgba(240,87,92,0.15); color:var(--red); display:flex; align-items:center; justify-content:center;">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <div style="font-size:15px; font-weight:700; color:var(--fg);">Unable to Load GitHub Releases</div>
          <p style="font-size:12.5px; color:var(--muted); max-width:480px; margin:0;">${githubReleasesError}</p>
          <div style="display:flex; gap:10px; margin-top:8px;">
            <button class="btn btn-primary btn-sm" id="btn-about-retry-releases">Retry</button>
            <a href="https://github.com/hackyue/ForkedRobloxAccountManager/releases" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">View on GitHub</a>
          </div>
        </div>
      `;
      document.getElementById('btn-about-retry-releases')?.addEventListener('click', () => {
        loadGithubReleases(true);
      });
    } else if (cachedGithubReleases && cachedGithubReleases.length > 0) {
      let releasesHtml = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <div>
            <h3 style="font-size:15px; font-weight:700; color:var(--text-bright); margin:0;">Release History & Changelogs</h3>
            <p style="font-size:12px; color:var(--muted); margin:2px 0 0 0;">Fetched directly from GitHub Releases</p>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-secondary btn-sm" id="btn-about-refresh-releases" title="Check for newer release notes" style="display:inline-flex; align-items:center; gap:6px;">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              <span>Refresh</span>
            </button>
            <a href="https://github.com/hackyue/ForkedRobloxAccountManager/releases" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center; gap:6px;">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              <span>All Releases</span>
            </a>
          </div>
        </div>
        <div class="about-releases-list">
      `;

function isPackageSupportedRelease(tagOrName: string): boolean {
  if (!tagOrName) return false;
  const clean = tagOrName.replace(/^v/i, '').split('-')[0].trim();
  const parts = clean.split('.').map(p => {
    const num = parseInt(p, 10);
    return isNaN(num) ? 0 : num;
  });
  while (parts.length < 3) parts.push(0);
  const cutoff = [2, 5, 4];
  for (let i = 0; i < 3; i++) {
    const n = parts[i] || 0;
    const c = cutoff[i] || 0;
    if (n > c) return true;
    if (n < c) return false;
  }
  return true;
}

      cachedGithubReleases.forEach((rel: any, index: number) => {
        const title = rel.name || rel.tag_name || 'Release';
        const tag = rel.tag_name || '';
        const isLatest = index === 0 && !rel.prerelease;
        const isPre = rel.prerelease;
        const dateStr = rel.published_at ? new Date(rel.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
        const formattedBody = formatReleaseMarkdown(rel.body);

        const isSupported = isPackageSupportedRelease(rel.tag_name || rel.name || '');
        const assets = Array.isArray(rel.assets) ? rel.assets : [];
        const installerAssets = isSupported ? assets.filter((a: any) => {
          const n = (a.name || '').toLowerCase();
          return n.endsWith('.exe') || n.endsWith('.msi');
        }) : [];

        releasesHtml += `
          <div class="about-release-card">
            <div class="about-release-header">
              <div class="about-release-title-row">
                <h4 class="about-release-title">${title}</h4>
                ${tag ? `<span class="badge" style="font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px; background:var(--bg-2); border:1px solid var(--border); color:var(--fg);">${tag}</span>` : ''}
                ${isLatest ? `<span class="about-release-tag latest">LATEST RELEASE</span>` : ''}
                ${isPre ? `<span class="about-release-tag" style="background:rgba(245,158,11,0.15); color:#f59e0b; border-color:rgba(245,158,11,0.3);">PRE-RELEASE</span>` : ''}
              </div>
              ${dateStr ? `<span class="about-release-date">${dateStr}</span>` : ''}
            </div>
            <div class="about-release-body">
              ${formattedBody}
            </div>
            <div class="about-release-footer">
              ${isSupported && installerAssets.length > 0 ? `
                <div class="about-release-installers">
                  ${installerAssets.map((asset: any) => {
                    const isMsi = (asset.name || '').toLowerCase().endsWith('.msi');
                    const sizeMb = asset.size ? (asset.size / (1024 * 1024)).toFixed(1) + ' MB' : '';
                    const btnClass = isMsi ? 'btn btn-secondary btn-sm about-release-pkg-btn' : 'btn btn-primary btn-sm about-release-pkg-btn';
                    const label = isMsi ? `Update with .msi ${sizeMb ? `(${sizeMb})` : ''}` : `Update with .exe ${sizeMb ? `(${sizeMb})` : ''}`;
                    return `
                      <button type="button" class="${btnClass} btn-release-install-pkg" data-rel-idx="${index}" data-asset-name="${asset.name}" data-download-url="${asset.browser_download_url}" data-asset-size="${asset.size || 0}" title="Download and install ${asset.name}">
                        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        <span>${label}</span>
                      </button>
                    `;
                  }).join('')}
                </div>
              ` : ''}

              <div style="display:flex; align-items:center; gap:10px; margin-left:auto;">
                <a href="${rel.html_url || 'https://github.com/hackyue/ForkedRobloxAccountManager/releases'}" target="_blank" rel="noopener noreferrer" class="about-link-chip github" style="padding:6px 12px; font-size:12px;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
                  <span>View Release</span>
                </a>
              </div>
            </div>
          </div>
        `;
      });

      releasesHtml += `</div>`;
      container.innerHTML = releasesHtml;

      container.querySelectorAll('.btn-release-install-pkg').forEach(btn => {
        btn.addEventListener('click', () => {
          const relIdx = parseInt(btn.getAttribute('data-rel-idx') || '0', 10);
          const rel = cachedGithubReleases?.[relIdx];
          if (!rel) return;
          const assetName = btn.getAttribute('data-asset-name') || 'FRAM_Installer.exe';
          const downloadUrl = btn.getAttribute('data-download-url') || '';
          const assetSize = parseInt(btn.getAttribute('data-asset-size') || '0', 10);
          const targetVersion = (rel.tag_name || '').replace(/^v/i, '') || '3.0.0';

          const updatePayload: UpdateCheckResult = {
            success: true,
            update_available: true,
            current_version: '3.0.0',
            latest_version: targetVersion,
            latest_tag: rel.tag_name || `v${targetVersion}`,
            release_title: `${rel.name || rel.tag_name || 'Release'} — ${assetName}`,
            release_notes: rel.body || '',
            published_at: rel.published_at || '',
            html_url: rel.html_url || downloadUrl,
            asset_name: assetName,
            asset_size: assetSize,
            download_url: downloadUrl,
            sha256: ''
          };
          showUpdateModal(updatePayload);
        });
      });

      document.getElementById('btn-about-refresh-releases')?.addEventListener('click', () => {
        loadGithubReleases(true);
      });
    } else {
      container.innerHTML = `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 20px; gap:10px; text-align:center;">
          <p style="font-size:13.5px; color:var(--muted);">No releases found on GitHub repository.</p>
          <a href="https://github.com/hackyue/ForkedRobloxAccountManager/releases" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm">Open GitHub Releases</a>
        </div>
      `;
    }
  }
}

interface ExecutorPresetItem {
  id: string;
  name: string;
  aliases: string[];
  icon: string;
}

const EXECUTOR_PRESETS: ExecutorPresetItem[] = [
  { id: 'solara', name: 'Solara', aliases: ['solara', 'salara'], icon: '/ExecutorIcons/Salara.ico' },
  { id: 'wave', name: 'Wave', aliases: ['wave'], icon: '/ExecutorIcons/Wave.png' },
  { id: 'xeno', name: 'Xeno', aliases: ['xeno'], icon: '/ExecutorIcons/xeno.png' },
  { id: 'synz', name: 'Synapse Z', aliases: ['synapse z', 'synz', 'synapse'], icon: '/ExecutorIcons/synz.webp' },
  { id: 'potassium', name: 'Potassium', aliases: ['potassium'], icon: '/ExecutorIcons/Potassium.ico' },
  { id: 'velocity', name: 'Velocity', aliases: ['velocity'], icon: '/ExecutorIcons/Velocity.ico' },
  { id: 'volt', name: 'Volt', aliases: ['volt'], icon: '/ExecutorIcons/Volt.svg' },
  { id: 'sirhurt', name: 'SirHurt', aliases: ['sirhurt', 'sir hurt'], icon: '/ExecutorIcons/SirHurt.png' },
  { id: 'madium', name: 'Madium', aliases: ['madium'], icon: '/ExecutorIcons/Madium.png' },
  { id: 'real', name: 'Real', aliases: ['real'], icon: '/ExecutorIcons/Real.png' }
];

function showRobloxInstallerModal(): void {
  let existing = document.getElementById('installer-modal-overlay');
  if (existing) existing.remove();

  const disablePresets = Boolean(state.settings.disableExecutorPresets);

  const overlay = document.createElement('div');
  overlay.id = 'installer-modal-overlay';
  overlay.className = 'modal-overlay show';

  overlay.innerHTML = `
    <div class="modal installer-modal">
      <div class="modal-header">
        <h3>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:middle;margin-right:6px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Roblox Installer
        </h3>
        <button class="modal-close" id="installer-modal-close">×</button>
      </div>
      <div class="modal-body">
        <p class="hint">Install a specific version of Roblox into any supported bootstrapper client on your system.</p>
        
        ${!disablePresets ? `
        <div class="installer-executors-section">
          <div class="installer-executors-header">
            <span class="installer-executors-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              Select Executor Preset
            </span>
          </div>
          <div class="installer-executors-grid" id="installer-executors-grid">
            ${EXECUTOR_PRESETS.map(p => `
              <button type="button" class="installer-executor-btn" data-executor-id="${p.id}" title="Select ${p.name} preset">
                <img src="${p.icon}" alt="${p.name}" class="installer-executor-icon" />
                <span class="installer-executor-name">${p.name}</span>
                <span class="installer-executor-dot" id="exec-dot-${p.id}"></span>
              </button>
            `).join('')}
          </div>
          <div class="installer-executor-preview" id="installer-executor-preview" style="display:none;">
            <div class="installer-executor-preview-info">
              <div class="installer-executor-preview-title" id="installer-preview-title">
                <span id="installer-preview-name">Selected Executor</span>
                <span class="installer-status-pill updated" id="installer-preview-status">UPDATED</span>
              </div>
              <div class="installer-executor-preview-sub" id="installer-preview-sub"></div>
            </div>
            <button type="button" class="installer-executor-clear-btn" id="installer-executor-clear-btn" title="Clear executor selection">✕ Clear</button>
          </div>
        </div>
        ` : ''}

        <div class="installer-field">
          <label for="installer-version-select">Select Version Target</label>
          <select id="installer-version-select">
            <option value="">Fetching available versions...</option>
          </select>
        </div>

        <div class="installer-field">
          <label for="installer-client-select">Select Target Client</label>
          <select id="installer-client-select">
            <option value="">Fetching installed clients...</option>
          </select>
        </div>

        <div class="installer-progress-container" id="installer-progress-container" style="display:none;">
          <div class="installer-progress-track">
            <div class="installer-progress-fill" id="installer-progress-fill"></div>
          </div>
          <div class="installer-status-text" id="installer-status-text">Ready</div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="installer-modal-cancel">Cancel</button>
        <button class="btn btn-primary" id="installer-start-btn" disabled>Install Version</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  const closeBtn = document.getElementById('installer-modal-close') as HTMLButtonElement | null;
  const cancelBtn = document.getElementById('installer-modal-cancel') as HTMLButtonElement | null;
  const startBtn = document.getElementById('installer-start-btn') as HTMLButtonElement;
  const versionSelect = document.getElementById('installer-version-select') as HTMLSelectElement;
  const clientSelect = document.getElementById('installer-client-select') as HTMLSelectElement;
  const progressContainer = document.getElementById('installer-progress-container') as HTMLElement;
  const progressFill = document.getElementById('installer-progress-fill') as HTMLElement;
  const statusText = document.getElementById('installer-status-text') as HTMLElement;

  const executorsGrid = document.getElementById('installer-executors-grid') as HTMLElement;
  const executorPreview = document.getElementById('installer-executor-preview') as HTMLElement;
  const previewName = document.getElementById('installer-preview-name') as HTMLElement;
  const previewStatus = document.getElementById('installer-preview-status') as HTMLElement;
  const previewSub = document.getElementById('installer-preview-sub') as HTMLElement;
  const clearExecutorBtn = document.getElementById('installer-executor-clear-btn') as HTMLButtonElement;

  let pollInterval: any = null;
  let versionsList: InstallerVersionEntry[] = [];
  let weaoExploitsList: WeaoExploitItem[] = [];
  let selectedExecutorPreset: ExecutorPresetItem | null = null;

  const setControlsDisabled = (disabled: boolean) => {
    startBtn.disabled = disabled;
    if (cancelBtn) cancelBtn.disabled = disabled;
    if (closeBtn) closeBtn.disabled = disabled;
    versionSelect.disabled = disabled;
    clientSelect.disabled = disabled;
    if (executorsGrid) {
      executorsGrid.querySelectorAll<HTMLButtonElement>('.installer-executor-btn').forEach(btn => {
        btn.disabled = disabled;
      });
    }
  };

  const closeModal = () => {
    if (pollInterval) clearInterval(pollInterval);
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay && !startBtn.disabled) closeModal();
  });

  const findExploitForPreset = (preset: ExecutorPresetItem): WeaoExploitItem | undefined => {
    return weaoExploitsList.find(e => {
      const titleLower = (e.title || '').trim().toLowerCase();
      if (titleLower === preset.name.toLowerCase()) return true;
      return preset.aliases.some(a => a.toLowerCase() === titleLower || titleLower.includes(a.toLowerCase()));
    });
  };

  const updateExecutorDots = () => {
    EXECUTOR_PRESETS.forEach(p => {
      const dot = document.getElementById(`exec-dot-${p.id}`);
      if (!dot) return;
      const exploit = findExploitForPreset(p);
      if (exploit) {
        if (exploit.updateStatus) {
          dot.className = 'installer-executor-dot';
          dot.title = `${p.name}: Updated for ${exploit.rbxversion || 'current'}`;
        } else {
          dot.className = 'installer-executor-dot outdated';
          dot.title = `${p.name}: Outdated`;
        }
      } else {
        dot.className = 'installer-executor-dot outdated';
        dot.title = `${p.name}: Status unavailable`;
      }
    });
  };

  const selectExecutor = (preset: ExecutorPresetItem) => {
    selectedExecutorPreset = preset;
    const allBtns = executorsGrid.querySelectorAll('.installer-executor-btn');
    allBtns.forEach(b => {
      if (b.getAttribute('data-executor-id') === preset.id) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });

    const exploit = findExploitForPreset(preset);
    if (!exploit) {
      previewName.textContent = preset.name;
      previewStatus.textContent = 'NO DATA';
      previewStatus.className = 'installer-status-pill outdated';
      previewSub.textContent = 'No active exploit status found from WEAO API';
      executorPreview.style.display = 'flex';
      return;
    }

    const isUpdated = Boolean(exploit.updateStatus);
    previewName.textContent = exploit.title || preset.name;
    previewStatus.textContent = isUpdated ? 'UPDATED' : 'OUTDATED';
    previewStatus.className = `installer-status-pill ${isUpdated ? 'updated' : 'outdated'}`;

    const rbxVersion = (exploit.rbxversion || '').trim();
    const metaParts: string[] = [];
    if (exploit.uncPercentage != null) {
      metaParts.push(`UNC: ${exploit.uncPercentage}%`);
    }
    if (exploit.updatedDate) {
      metaParts.push(exploit.updatedDate);
    }
    previewSub.textContent = metaParts.length > 0
      ? metaParts.join(' • ')
      : (isUpdated ? 'Ready to install' : 'Outdated version');
    executorPreview.style.display = 'flex';

    if (rbxVersion) {
      let foundIndex = versionsList.findIndex(v => v.version.toLowerCase() === rbxVersion.toLowerCase());
      if (foundIndex === -1) {
        const newEntry: InstallerVersionEntry = {
          version: rbxVersion,
          status: isUpdated ? 'LIVE' : 'PAST',
          source: 'WEAO',
          label: `[${exploit.title}] ${rbxVersion}`
        };
        versionsList.unshift(newEntry);
        foundIndex = 0;

        versionSelect.innerHTML = versionsList.map((v, idx) =>
          `<option value="${idx}">${v.label || ('[' + (v.status || 'PAST') + '] ' + v.version)}</option>`
        ).join('');
      }
      versionSelect.value = String(foundIndex);
      if (clientSelect.value) {
        startBtn.disabled = false;
      }
    }
  };

  const clearExecutorSelection = () => {
    selectedExecutorPreset = null;
    executorsGrid.querySelectorAll('.installer-executor-btn').forEach(b => b.classList.remove('active'));
    executorPreview.style.display = 'none';
  };

  clearExecutorBtn?.addEventListener('click', clearExecutorSelection);

  executorsGrid?.querySelectorAll<HTMLButtonElement>('.installer-executor-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const eid = btn.getAttribute('data-executor-id');
      const preset = EXECUTOR_PRESETS.find(p => p.id === eid);
      if (preset) {
        selectExecutor(preset);
      }
    });
  });

  async function loadData() {
    try {
      const [verRes, clientRes, weaoRes] = await Promise.all([
        apiService.getInstallerAvailableVersions(),
        apiService.getInstallerClients(),
        disablePresets
          ? Promise.resolve({ success: false, exploits: [] })
          : apiService.getWeaoExploits().catch(() => ({ success: false, exploits: [] }))
      ]);

      if (!disablePresets && weaoRes.success && Array.isArray(weaoRes.exploits) && weaoRes.exploits.length > 0) {
        weaoExploitsList = weaoRes.exploits;
        updateExecutorDots();
      }

      if (verRes.success && verRes.versions.length > 0) {
        versionsList = verRes.versions;
        versionSelect.innerHTML = verRes.versions.map((v, idx) =>
          `<option value="${idx}">${v.label || ('[' + (v.status || 'PAST') + '] ' + v.version)}</option>`
        ).join('');
      } else {
        versionSelect.innerHTML = '<option value="">No versions found</option>';
      }

      if (clientRes.success && clientRes.clients.length > 0) {
        clientSelect.innerHTML = clientRes.clients.map(c =>
          `<option value="${c.id}">${c.name} (${c.versions_path})</option>`
        ).join('');
      } else {
        clientSelect.innerHTML = '<option value="">No installed clients found</option>';
      }

      if (versionsList.length > 0 && clientRes.clients && clientRes.clients.length > 0) {
        startBtn.disabled = false;
      }
    } catch (err: any) {
      statusText.textContent = 'Failed to load installer info: ' + err.message;
      progressContainer.style.display = 'block';
    }
  }

  loadData();

  const pollStatus = () => {
    if (globalRobloxInstallerPollTimer) {
      clearInterval(globalRobloxInstallerPollTimer);
    }
    globalRobloxInstallerPollTimer = setInterval(async () => {
      try {
        const res = await apiService.getInstallerStatus();
        if (res.success && res.status) {
          const st = res.status;
          lastRobloxInstallerStatus = st;
          progressFill.style.width = (st.progress || 0) + '%';
          statusText.textContent = st.status || 'Processing...';

          if (st.success === true) {
            isRobloxInstallerRunning = false;
            clearInterval(globalRobloxInstallerPollTimer);
            globalRobloxInstallerPollTimer = null;
            setControlsDisabled(false);
            statusText.textContent = st.status || 'Successfully installed!';
            toast(st.status || 'Installation completed!', 'info');
            refreshRobloxVersions();
          } else if (st.success === false) {
            isRobloxInstallerRunning = false;
            clearInterval(globalRobloxInstallerPollTimer);
            globalRobloxInstallerPollTimer = null;
            setControlsDisabled(false);
            statusText.textContent = 'Error: ' + (st.error || 'Failed to install');
            toast('Installation failed: ' + (st.error || 'Unknown error'), 'error');
          }
        }
      } catch (err) {
        console.error('Error polling installer status:', err);
      }
    }, 500);
  };

  if (isRobloxInstallerRunning) {
    setControlsDisabled(true);
    progressContainer.style.display = 'block';
    if (lastRobloxInstallerStatus) {
      progressFill.style.width = (lastRobloxInstallerStatus.progress || 0) + '%';
      statusText.textContent = lastRobloxInstallerStatus.status || 'Installing...';
    }
    pollStatus();
  }

  startBtn.addEventListener('click', async () => {
    const vIndex = parseInt(versionSelect.value, 10);
    const clientId = clientSelect.value;
    if (isNaN(vIndex) || !versionsList[vIndex] || !clientId) return;

    const selectedVersion = versionsList[vIndex];
    isRobloxInstallerRunning = true;
    lastRobloxInstallerStatus = { progress: 0, status: 'Starting installer...' };
    setControlsDisabled(true);
    progressContainer.style.display = 'block';
    progressFill.style.width = '0%';
    statusText.textContent = selectedExecutorPreset
      ? `Starting installer for ${selectedExecutorPreset.name} (${selectedVersion.version})...`
      : 'Starting installer...';

    try {
      let res = await apiService.startInstallerDownload(selectedVersion, clientId, false);

      if (res.already_exists) {
        const confirmOverwrite = await showConfirmModal(
          'Version Already Exists',
          `The version folder for ${selectedVersion.version} already exists in ${res.client_name || clientId}. Do you want to overwrite it with a fresh install?`,
          'Overwrite',
          true
        );
        if (confirmOverwrite) {
          res = await apiService.startInstallerDownload(selectedVersion, clientId, true);
        } else {
          isRobloxInstallerRunning = false;
          setControlsDisabled(false);
          progressContainer.style.display = 'none';
          return;
        }
      }

      if (res.success) {
        pollStatus();
      } else {
        isRobloxInstallerRunning = false;
        statusText.textContent = 'Error: ' + (res.error || 'Failed to start installer');
        setControlsDisabled(false);
      }
    } catch (err: any) {
      isRobloxInstallerRunning = false;
      statusText.textContent = 'Error starting installation: ' + err.message;
      setControlsDisabled(false);
    }
  });
}

function showUpdateModal(initialCheck?: UpdateCheckResult): void {
  let existing = document.getElementById('updater-modal-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'updater-modal-overlay';
  overlay.className = 'modal-overlay show';

  overlay.innerHTML = `
    <div class="modal updater-modal">
      <div class="modal-header">
        <h3>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:middle;margin-right:6px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          Software Update
        </h3>
        <button class="modal-close" id="updater-modal-close">×</button>
      </div>
      <div class="modal-body">
        <div class="updater-version-info">
          <div class="updater-badges">
            <span class="updater-badge current" id="updater-curr-badge">Current: v3.0.0</span>
            <span class="updater-arrow">→</span>
            <span class="updater-badge latest" id="updater-latest-badge">Checking...</span>
          </div>
          <h4 class="updater-release-title" id="updater-release-title">Checking for updates...</h4>
          <div class="updater-release-meta" id="updater-release-meta"></div>
        </div>

        <div class="updater-notes-label">What's New</div>
        <div class="updater-notes-box" id="updater-notes-box">Checking latest release notes...</div>

        <div class="updater-progress-container" id="updater-progress-container" style="display:none;">
          <div class="updater-progress-track">
            <div class="updater-progress-fill" id="updater-progress-fill"></div>
          </div>
          <div class="updater-status-text" id="updater-status-text">Ready</div>
        </div>
      </div>
      <div class="modal-footer">
        <a href="https://github.com/hackyue/ForkedRobloxAccountManager/releases" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" id="updater-view-release-btn" style="margin-right:auto;">View on GitHub</a>
        <button class="btn btn-secondary" id="updater-modal-cancel">Close</button>
        <button class="btn btn-primary" id="updater-action-btn" disabled>Download & Install</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  const closeBtn = document.getElementById('updater-modal-close') as HTMLButtonElement | null;
  const cancelBtn = document.getElementById('updater-modal-cancel') as HTMLButtonElement | null;
  const actionBtn = document.getElementById('updater-action-btn') as HTMLButtonElement;
  const viewReleaseBtn = document.getElementById('updater-view-release-btn') as HTMLAnchorElement | null;
  const currBadge = document.getElementById('updater-curr-badge') as HTMLElement;
  const latestBadge = document.getElementById('updater-latest-badge') as HTMLElement;
  const releaseTitle = document.getElementById('updater-release-title') as HTMLElement;
  const releaseMeta = document.getElementById('updater-release-meta') as HTMLElement;
  const notesBox = document.getElementById('updater-notes-box') as HTMLElement;
  const progressContainer = document.getElementById('updater-progress-container') as HTMLElement;
  const progressFill = document.getElementById('updater-progress-fill') as HTMLElement;
  const statusText = document.getElementById('updater-status-text') as HTMLElement;

  let pollInterval: any = null;
  let downloadCompleted = false;
  let currentModalCheck: UpdateCheckResult | null = initialCheck || null;

  const closeModal = () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    overlay.remove();
  };

  if (closeBtn) closeBtn.onclick = closeModal;
  if (cancelBtn) cancelBtn.onclick = closeModal;

  const renderCheckData = (data: UpdateCheckResult) => {
    currentModalCheck = data;
    currBadge.textContent = `Current: v${data.current_version}`;

    if (data.html_url && viewReleaseBtn) {
      viewReleaseBtn.href = data.html_url;
    }

    if (data.update_available) {
      latestBadge.textContent = `Latest: v${data.latest_version}`;
      latestBadge.className = 'updater-badge latest';
      releaseTitle.textContent = data.release_title || `FRAM v${data.latest_version}`;

      const metaParts: string[] = [];
      if (data.published_at) {
        try {
          const d = new Date(data.published_at);
          metaParts.push(`Released: ${d.toLocaleDateString()}`);
        } catch (_) { }
      }
      if (data.asset_name) {
        metaParts.push(data.asset_name);
      }
      if (data.asset_size && data.asset_size > 0) {
        metaParts.push(`${(data.asset_size / (1024 * 1024)).toFixed(1)} MB`);
      }
      releaseMeta.textContent = metaParts.join(' • ');

      notesBox.textContent = data.release_notes ? data.release_notes.trim() : 'No release notes provided.';
      actionBtn.disabled = false;
      actionBtn.textContent = 'Download & Install';
      if (cancelBtn) cancelBtn.textContent = 'Later';
    } else {
      latestBadge.textContent = `Up to Date`;
      latestBadge.className = 'updater-badge current';
      releaseTitle.textContent = `You're on the latest version`;
      releaseMeta.textContent = `FRAM v${data.current_version} is the newest release.`;
      notesBox.textContent = data.release_notes || 'No new updates available at this time.';
      actionBtn.disabled = true;
      actionBtn.textContent = 'Up to Date';
      if (cancelBtn) cancelBtn.textContent = 'Close';
    }
  };

  if (initialCheck) {
    renderCheckData(initialCheck);
  } else {
    apiService.checkForUpdates(true).then((data) => {
      renderCheckData(data);
    }).catch((err) => {
      releaseTitle.textContent = 'Unable to check for updates';
      notesBox.textContent = `Error: ${err?.message || err}`;
      if (cancelBtn) cancelBtn.textContent = 'Close';
    });
  }

  actionBtn.onclick = async () => {
    if (downloadCompleted) {
      actionBtn.disabled = true;
      actionBtn.textContent = 'Applying update...';
      statusText.textContent = 'Launching updater...';
      try {
        const res = await apiService.applyUpdate();
        if (res.success) {
          statusText.textContent = 'Updater launched. Exiting application...';
          toast('Updater launched');
          setTimeout(() => {
            appWindow.close().catch(() => { });
          }, 1500);
        } else {
          statusText.textContent = 'Failed to apply: ' + (res.error || 'Unknown error');
          actionBtn.disabled = false;
          actionBtn.textContent = 'Retry Install';
        }
      } catch (err: any) {
        statusText.textContent = 'Error: ' + (err?.message || err);
        actionBtn.disabled = false;
        actionBtn.textContent = 'Retry Install';
      }
      return;
    }

    actionBtn.disabled = true;
    actionBtn.textContent = 'Starting download...';
    if (cancelBtn) cancelBtn.disabled = true;
    progressContainer.style.display = 'flex';
    progressFill.style.width = '0%';
    statusText.textContent = 'Connecting...';

    try {
      const startRes = await apiService.startUpdateDownload(currentModalCheck?.download_url ? {
        download_url: currentModalCheck.download_url,
        asset_name: currentModalCheck.asset_name,
        sha256: currentModalCheck.sha256,
        total_bytes: currentModalCheck.asset_size
      } : undefined);
      if (!startRes.success) {
        statusText.textContent = 'Failed: ' + (startRes.error || 'Could not start download');
        actionBtn.disabled = false;
        actionBtn.textContent = 'Retry Download';
        if (cancelBtn) cancelBtn.disabled = false;
        return;
      }

      actionBtn.textContent = 'Downloading...';

      pollInterval = setInterval(async () => {
        try {
          const res = await apiService.getUpdateStatus();
          if (res && res.success && res.status) {
            const st: UpdateDownloadStatus = res.status;
            progressFill.style.width = `${st.progress || 0}%`;
            statusText.textContent = st.status || 'Downloading...';

            if (st.success === true) {
              clearInterval(pollInterval);
              pollInterval = null;
              downloadCompleted = true;
              progressFill.style.width = '100%';
              statusText.textContent = 'Download completed! Click "Install & Restart" to apply.';
              actionBtn.disabled = false;
              actionBtn.textContent = 'Install & Restart';
              if (cancelBtn) cancelBtn.disabled = false;
            } else if (st.success === false || st.error) {
              clearInterval(pollInterval);
              pollInterval = null;
              statusText.textContent = 'Download failed: ' + (st.error || 'Unknown error');
              actionBtn.disabled = false;
              actionBtn.textContent = 'Retry Download';
              if (cancelBtn) cancelBtn.disabled = false;
            }
          }
        } catch (pollErr: any) {
          console.error('Error polling update download status:', pollErr);
        }
      }, 300);

    } catch (err: any) {
      statusText.textContent = 'Error: ' + (err?.message || err);
      actionBtn.disabled = false;
      actionBtn.textContent = 'Retry Download';
      if (cancelBtn) cancelBtn.disabled = false;
    }
  };
}

function showUpdateNotificationToast(update: UpdateCheckResult): void {
  const existing = document.querySelector('.update-launch-toast');
  if (existing) existing.remove();

  const toastEl = document.createElement('div');
  toastEl.className = 'update-launch-toast';
  toastEl.innerHTML = `
    <div class="update-toast-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
    </div>
    <div class="update-toast-body">
      <div class="update-toast-title">FRAM Update Available</div>
      <div class="update-toast-desc">v${update.latest_version} is available. Click to view release notes and install.</div>
    </div>
    <button class="update-toast-btn" id="btn-toast-update-view">Update</button>
    <button class="update-toast-close" id="btn-toast-update-close">×</button>
  `;
  document.body.appendChild(toastEl);

  const viewBtn = toastEl.querySelector('#btn-toast-update-view');
  const closeBtn = toastEl.querySelector('#btn-toast-update-close');

  if (viewBtn) {
    viewBtn.addEventListener('click', () => {
      toastEl.remove();
      showUpdateModal(update);
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      toastEl.remove();
    });
  }

  setTimeout(() => {
    if (toastEl.parentElement) {
      toastEl.classList.add('fade-out');
      setTimeout(() => toastEl.remove(), 400);
    }
  }, 14000);
}

async function checkAppUpdateOnStartup(): Promise<void> {
  try {
    const res = await apiService.checkForUpdates(false);
    if (res && res.update_available) {
      showUpdateNotificationToast(res);
    }
  } catch (_e) {
    /* Silent check on startup */
  }
}

function showAddAccountOptions(anchorEl?: HTMLElement | null): void {
  const btnTarget = anchorEl || document.getElementById('btn-add-account') || document.getElementById('btn-accounts');
  if (!btnTarget) return;

  // Remove existing menu if present
  const existingMenu = document.getElementById('add-account-menu');
  if (existingMenu) {
    existingMenu.remove();
    return;
  }

  const menu = document.createElement('div');
  menu.id = 'add-account-menu';
  menu.className = 'dropdown-menu';
  menu.innerHTML = `
    <div class="add-account-dropdown-header">
      <div class="dropdown-header-title">Add Roblox Account</div>
    </div>
    <div class="menu-item" data-method="browser">
      <div class="menu-item-icon-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/><line x1="21.17" y1="8" x2="12" y2="8"/><line x1="3.95" y1="6.06" x2="8.54" y2="14"/><line x1="10.88" y1="21.94" x2="15.46" y2="14"/></svg>
      </div>
      <div class="menu-item-text">
        <div class="menu-item-title">Browser Login</div>
      </div>
      <svg class="menu-item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
    </div>
    <div class="menu-item" data-method="cookie">
      <div class="menu-item-icon-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><circle cx="12" cy="16" r="1"/></svg>
      </div>
      <div class="menu-item-text">
        <div class="menu-item-title">Cookie Import</div>
      </div>
      <svg class="menu-item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
    </div>
    <div class="menu-item" data-method="credentials">
      <div class="menu-item-icon-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </div>
      <div class="menu-item-text">
        <div class="menu-item-title">User:Pass Import</div>
      </div>
      <svg class="menu-item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
    </div>
    <div class="menu-item" data-method="quick-signin">
      <div class="menu-item-icon-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
      </div>
      <div class="menu-item-text">
        <div class="menu-item-title">Quick Sign-In Code</div>
      </div>
      <svg class="menu-item-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
    </div>
  `;

  document.body.appendChild(menu);

  // Position menu relative to target button using exact DOM dimensions
  const rect = btnTarget.getBoundingClientRect();
  const menuWidth = menu.offsetWidth;
  const menuHeight = menu.offsetHeight;

  let top = rect.bottom + 6;
  if (top + menuHeight > window.innerHeight) {
    top = Math.max(10, rect.top - menuHeight - 6);
  }

  // Center horizontally relative to target button
  let left = rect.left + (rect.width / 2) - (menuWidth / 2);
  left = Math.min(Math.max(10, left), Math.max(10, window.innerWidth - menuWidth - 10));

  menu.style.top = top + 'px';
  menu.style.left = left + 'px';

  const menuItems = menu.querySelectorAll('.menu-item');

  menuItems.forEach(item => {
    item.addEventListener('click', () => {
      const method = item.getAttribute('data-method');
      menu.remove();
      if (method) {
        handleAccountAddition(method);
      }
    });
  });

  // Close menu when clicking outside
  const closeMenu = (e: MouseEvent) => {
    if (!menu.contains(e.target as Node) && !btnTarget.contains(e.target as Node)) {
      menu.remove();
      document.removeEventListener('click', closeMenu);
    }
  };

  setTimeout(() => {
    document.addEventListener('click', closeMenu);
  }, 0);
}

async function handleAccountAddition(method: string): Promise<void> {
  switch (method) {
    case 'browser':
      showBrowserLoginModal();
      break;
    case 'cookie':
      showCookieImportModal();
      break;
    case 'credentials':
      showCredentialsImportModal();
      break;
    case 'quick-signin':
      showQuickSignInModal();
      break;
  }
}

function showBrowserLoginModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal account-modal">
      <div class="modal-header">
        <h3>Browser Login</h3>
        <button class="modal-close" id="modal-close">×</button>
      </div>
      <div class="modal-body">
        <div class="field">
          <label>Instances</label>
          <input type="number" id="browser-amount" value="1" min="1" max="10" autocomplete="off">
        </div>
        <div class="field">
          <label>Website URL</label>
          <input type="text" id="browser-website" value="https://www.roblox.com/login" autocomplete="off">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
        <button class="btn btn-primary" id="modal-confirm">Start</button>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  const closeBtn = document.getElementById('modal-close');
  const cancelBtn = document.getElementById('modal-cancel');
  const confirmBtn = document.getElementById('modal-confirm');

  const closeModal = () => {
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  confirmBtn?.addEventListener('click', async () => {
    const amount = parseInt((document.getElementById('browser-amount') as HTMLInputElement).value) || 1;
    const website = (document.getElementById('browser-website') as HTMLInputElement).value;
    const browser = state.settings.preferredBrowser || 'auto';

    addLog('Using browser setting: ' + browser + ' (from settings: ' + state.settings.preferredBrowser + ')', 'info');

    try {
      showImportBanner(`${amount} Browser${amount === 1 ? '' : 's'} running`);
      await apiService.addAccountBrowser(amount, website, browser);
      closeModal();

      let pollCount = 0;
      let wasUserClosed = false;
      const initialAccountsCount = (state.accounts || []).length;

      const pollTimer = setInterval(async () => {
        pollCount++;
        await refreshAccountList();
        const currentCount = (state.accounts || []).length;
        const newlyAdded = Math.max(0, currentCount - initialAccountsCount);

        let isRunning = true;
        let bStatus: any = null;
        try {
          bStatus = await apiService.getBrowserStatus();
          isRunning = Boolean(bStatus.is_running);
          if (bStatus.user_closed || bStatus.last_close_reason === 'user_closed') {
            wasUserClosed = true;
          }
        } catch (_) { }

        if (newlyAdded > 0 && newlyAdded < amount) {
          showImportBanner(`Browser automation (${newlyAdded}/${amount} account${amount > 1 ? 's' : ''} logged in)...`);
        } else if (newlyAdded === 0) {
          const runningCount = (bStatus && typeof bStatus.active_instances === 'number' && bStatus.active_instances > 0) ? bStatus.active_instances : amount;
          showImportBanner(`${runningCount} Browser${runningCount === 1 ? '' : 's'} running`);
        }

        if (newlyAdded >= amount || !isRunning || pollCount >= 180) {
          clearInterval(pollTimer);
          hideImportBanner();
          if (newlyAdded > 0) {
            toast(`Browser login complete: ${newlyAdded} account(s) added!`, 'success');
            await refreshAccountList();
          } else if (wasUserClosed) {
            toast('User closed browser.', 'info');
            addLog('Browser login ended: user closed browser.', 'info');
          } else if (!isRunning) {
            toast('Browser automation ended.', 'info');
          }
        }
      }, 1000);
    } catch (error) {
      hideImportBanner();
      addLog('Browser login failed: ' + error, 'error');
      toast('Failed to start browser login', 'error');
    }
  });
}

interface ParsedCookieLine {
  username?: string;
  password?: string;
  cookie: string;
  group?: string;
  note?: string;
}

function parseSingleCookieLine(line: string): ParsedCookieLine | null {
  let trimmed = String(line || '').trim();
  if (!trimmed) return null;

  if (trimmed.toLowerCase().startsWith('.roblosecurity=')) {
    trimmed = trimmed.substring(15).trim();
  } else if (trimmed.toLowerCase().startsWith('cookie:')) {
    trimmed = trimmed.substring(7).trim();
  }

  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    trimmed = trimmed.substring(1, trimmed.length - 1).trim();
  }

  if (!trimmed) return null;

  const warnIdx = trimmed.indexOf('_|WARNING:');
  if (warnIdx !== -1) {
    const before = trimmed.substring(0, warnIdx).trim();
    const after = trimmed.substring(warnIdx).trim();

    let cookie = after;
    let remainder = '';

    const match = after.match(/^(_\|WARNING:[^\s,;"'\t]+)(.*)$/);
    if (match) {
      cookie = match[1];
      remainder = match[2].trim();
    }

    let username = '';
    let password = '';
    let group = '';
    let note = '';

    if (before) {
      const cleanBefore = before.replace(/[:,\t|]+$/, '');
      const parts = cleanBefore.split(/[:,\t|]+/);
      if (parts.length === 1) {
        username = parts[0].trim();
      } else if (parts.length >= 2) {
        username = parts[0].trim();
        password = parts.slice(1).join('').trim();
      }
    }

    if (remainder) {
      const cleanRemainder = remainder.replace(/^[:,\t|]+/, '');
      const parts = cleanRemainder.split(/[:,\t|]+/);
      if (parts.length === 1) {
        group = parts[0].trim();
      } else if (parts.length >= 2) {
        group = parts[0].trim();
        note = parts.slice(1).join(' ').trim();
      }
    }

    return { cookie, username, password, group, note };
  }

  const sep = trimmed.includes('\t') ? '\t' : (trimmed.includes(',') && !trimmed.startsWith('_')) ? ',' : (trimmed.includes(';') && !trimmed.startsWith('_')) ? ';' : null;
  if (sep) {
    const parts = trimmed.split(sep).map(p => p.trim().replace(/^["']|["']$/g, ''));
    let cookieIdx = -1;
    let maxLen = 0;
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      if (p.startsWith('_') && p.length > 50) {
        cookieIdx = i;
        break;
      }
      if (p.length > maxLen && p.length > 50) {
        maxLen = p.length;
        cookieIdx = i;
      }
    }

    if (cookieIdx !== -1) {
      const cookie = parts[cookieIdx];
      const before = parts.slice(0, cookieIdx);
      const after = parts.slice(cookieIdx + 1);

      let username = '';
      let password = '';
      let group = '';
      let note = '';

      if (before.length === 1) {
        username = before[0];
      } else if (before.length >= 2) {
        username = before[0];
        password = before[1];
      }

      if (after.length === 1) {
        group = after[0];
      } else if (after.length >= 2) {
        group = after[0];
        note = after.slice(1).join(' ');
      }

      return { cookie, username, password, group, note };
    }
  }

  return { cookie: trimmed };
}

function parseMultiLineCookieInput(input: string): ParsedCookieLine[] {
  let raw = String(input || '').trim();
  if (!raw) return [];

  if (raw.startsWith('[') && raw.endsWith(']')) {
    try {
      const jsonArr = JSON.parse(raw);
      if (Array.isArray(jsonArr)) {
        const results: ParsedCookieLine[] = [];
        for (const item of jsonArr) {
          if (typeof item === 'string' && item.trim()) {
            const parsed = parseSingleCookieLine(item);
            if (parsed && parsed.cookie) results.push(parsed);
          } else if (item && typeof item === 'object') {
            const cookie = item.cookie || item.token || item.roblosecurity || item['.ROBLOSECURITY'] || '';
            if (cookie) {
              results.push({
                cookie: String(cookie).trim(),
                username: item.username || item.user || item.displayName || '',
                password: item.password || item.pass || '',
                group: item.group || '',
                note: item.note || ''
              });
            }
          }
        }
        if (results.length > 0) return results;
      }
    } catch (_) { }
  }

  raw = raw.replace(/([^\n\r])(\.ROBLOSECURITY=|_\|WARNING:-DO-NOT-SHARE-THIS)/gi, '$1\n$2');

  const rawLines = raw.split(/[\r\n]+/);
  const results: ParsedCookieLine[] = [];

  for (const rLine of rawLines) {
    const trimmed = rLine.trim();
    if (!trimmed) continue;

    if (trimmed.includes(';') && (trimmed.includes('_|') || trimmed.includes('.ROBLOSECURITY='))) {
      trimmed.split(';').forEach(sub => {
        const parsed = parseSingleCookieLine(sub);
        if (parsed && parsed.cookie) results.push(parsed);
      });
    } else {
      const parsed = parseSingleCookieLine(trimmed);
      if (parsed && parsed.cookie) results.push(parsed);
    }
  }

  return results;
}

interface CookieImportActiveState {
  isRunning: boolean;
  rawInput: string;
  defaultGroup: string;
  defaultNote: string;
  parsedCount: number;
  statusHtml: string;
  statusType?: 'running' | 'success' | 'error';
}

const activeCookieImportState: CookieImportActiveState = {
  isRunning: false,
  rawInput: '',
  defaultGroup: '',
  defaultNote: '',
  parsedCount: 0,
  statusHtml: '',
  statusType: undefined
};

let activeCookieImportModalElements: {
  overlay: HTMLElement;
  confirmBtn: HTMLButtonElement;
  statusEl: HTMLElement | null;
  inputEl: HTMLTextAreaElement;
  updateCount: () => void;
} | null = null;

function showCookieImportModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal account-modal" style="max-width: 560px; width: 92%;">
      <div class="modal-header">
        <h3>Cookie Import</h3>
        <button class="modal-close" id="modal-close">×</button>
      </div>
      <div class="modal-body" style="display:flex; flex-direction:column; gap:14px; padding:16px 20px;">
        <div class="field" style="margin-bottom:0;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <label style="margin-bottom:0; font-weight:600;">Cookies / Combos (One per line)</label>
            <span id="cookie-detect-count" style="font-size:11px; color:var(--muted); font-weight:600;">0 cookies detected</span>
          </div>
          <textarea id="cookie-multiline-input" rows="7" style="font-family: 'IBM Plex Mono', monospace; font-size:11.5px; line-height:1.45; resize:vertical; width:100%; box-sizing:border-box; background:var(--bg-2); border:1px solid var(--border); border-radius:8px; padding:10px 12px; color:var(--fg);" placeholder="Paste .ROBLOSECURITY cookies or combos here:&#10;• Raw cookie: _|WARNING:-DO-NOT-SHARE-THIS...&#10;• User:Cookie: username:_|WARNING:-DO-NOT-SHARE-THIS...&#10;• User:Pass:Cookie: username:password:_|WARNING:-DO-NOT-SHARE-THIS..."></textarea>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
          <div class="field" style="margin-bottom:0;">
            <label style="font-weight:600;">Default Group (optional)</label>
            <input type="text" id="cookie-default-group" placeholder="e.g. Alts, Mains" autocomplete="off" style="background:var(--bg-2); border:1px solid var(--border); border-radius:8px; padding:8px 12px; color:var(--fg); width:100%; box-sizing:border-box;">
          </div>
          <div class="field" style="margin-bottom:0;">
            <label style="font-weight:600;">Default Note (optional)</label>
            <input type="text" id="cookie-default-note" placeholder="Optional note for all" autocomplete="off" style="background:var(--bg-2); border:1px solid var(--border); border-radius:8px; padding:8px 12px; color:var(--fg); width:100%; box-sizing:border-box;">
          </div>
        </div>

        <div id="cookie-import-status" style="display:none; padding:10px 14px; border-radius:8px; font-size:12px; font-weight:500;"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
        <button class="btn btn-primary" id="modal-confirm">Import Accounts</button>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  const closeBtn = document.getElementById('modal-close');
  const cancelBtn = document.getElementById('modal-cancel');
  const confirmBtn = document.getElementById('modal-confirm') as HTMLButtonElement;
  const inputEl = document.getElementById('cookie-multiline-input') as HTMLTextAreaElement;
  const countEl = document.getElementById('cookie-detect-count');
  const statusEl = document.getElementById('cookie-import-status');
  const groupEl = document.getElementById('cookie-default-group') as HTMLInputElement;
  const noteEl = document.getElementById('cookie-default-note') as HTMLInputElement;

  if (activeCookieImportState.rawInput && inputEl) {
    inputEl.value = activeCookieImportState.rawInput;
  }
  if (activeCookieImportState.defaultGroup && groupEl) {
    groupEl.value = activeCookieImportState.defaultGroup;
  }
  if (activeCookieImportState.defaultNote && noteEl) {
    noteEl.value = activeCookieImportState.defaultNote;
  }

  const closeModal = () => {
    if (activeCookieImportModalElements?.overlay === overlay) {
      activeCookieImportModalElements = null;
    }
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  const renderStatus = () => {
    if (!statusEl) return;
    if (activeCookieImportState.statusHtml) {
      statusEl.style.display = 'flex';
      statusEl.style.alignItems = 'center';
      statusEl.style.gap = '8px';
      if (activeCookieImportState.statusType === 'success') {
        statusEl.style.background = 'rgba(16, 185, 129, 0.12)';
        statusEl.style.border = '1px solid rgba(16, 185, 129, 0.3)';
        statusEl.style.color = 'var(--emerald)';
      } else if (activeCookieImportState.statusType === 'error') {
        statusEl.style.background = 'rgba(239, 68, 68, 0.12)';
        statusEl.style.border = '1px solid rgba(239, 68, 68, 0.3)';
        statusEl.style.color = 'var(--rose)';
      } else {
        statusEl.style.background = 'rgba(99, 102, 241, 0.12)';
        statusEl.style.border = '1px solid rgba(99, 102, 241, 0.3)';
        statusEl.style.color = 'var(--fg)';
      }
      statusEl.innerHTML = activeCookieImportState.statusHtml;
    } else {
      statusEl.style.display = 'none';
      statusEl.innerHTML = '';
    }
  };

  const updateCount = () => {
    const parsed = parseMultiLineCookieInput(inputEl.value);
    const count = parsed.length;
    if (countEl) {
      countEl.textContent = count === 1 ? '1 cookie detected' : `${count} cookies detected`;
      countEl.style.color = count > 0 ? 'var(--emerald)' : 'var(--muted)';
    }
    if (confirmBtn) {
      if (activeCookieImportState.isRunning) {
        confirmBtn.disabled = true;
        const runningCount = activeCookieImportState.parsedCount || count;
        confirmBtn.innerHTML = `<span class="loading-spinner-inline"></span> Validating & Importing ${runningCount} Account${runningCount > 1 ? 's' : ''}...`;
      } else {
        confirmBtn.disabled = false;
        confirmBtn.textContent = count > 1 ? `Import ${count} Accounts` : count === 1 ? 'Import 1 Account' : 'Import Accounts';
      }
    }
  };

  activeCookieImportModalElements = {
    overlay,
    confirmBtn,
    statusEl,
    inputEl,
    updateCount
  };

  inputEl.addEventListener('input', () => {
    activeCookieImportState.rawInput = inputEl.value;
    if (!activeCookieImportState.isRunning && activeCookieImportState.statusHtml) {
      activeCookieImportState.statusHtml = '';
      activeCookieImportState.statusType = undefined;
      renderStatus();
    }
    updateCount();
  });

  groupEl?.addEventListener('input', () => {
    activeCookieImportState.defaultGroup = groupEl.value;
  });

  noteEl?.addEventListener('input', () => {
    activeCookieImportState.defaultNote = noteEl.value;
  });

  renderStatus();
  updateCount();
  setTimeout(() => inputEl.focus(), 100);

  confirmBtn?.addEventListener('click', async () => {
    if (activeCookieImportState.isRunning) return;

    const rawVal = inputEl.value;
    const parsed = parseMultiLineCookieInput(rawVal);

    if (parsed.length === 0) {
      toast('No valid cookies found in input. Please paste at least one .ROBLOSECURITY cookie.', 'error');
      return;
    }

    const defaultGroup = groupEl?.value.trim() || '';
    const defaultNote = noteEl?.value.trim() || '';

    activeCookieImportState.isRunning = true;
    activeCookieImportState.rawInput = rawVal;
    activeCookieImportState.defaultGroup = defaultGroup;
    activeCookieImportState.defaultNote = defaultNote;
    activeCookieImportState.parsedCount = parsed.length;
    activeCookieImportState.statusType = 'running';
    activeCookieImportState.statusHtml = `<span class="loading-spinner-inline"></span> <span>Validating ${parsed.length} account cookie(s) with Roblox API... Please wait.</span>`;

    renderStatus();
    updateCount();
    showImportBanner(`Validating and importing ${parsed.length} account${parsed.length > 1 ? 's' : ''}...`);

    try {
      const res = await apiService.bulkImportCookies(parsed, defaultGroup, defaultNote);
      hideImportBanner();
      activeCookieImportState.isRunning = false;
      activeCookieImportState.rawInput = '';
      activeCookieImportState.parsedCount = 0;

      if (res.success) {
        activeCookieImportState.statusType = 'success';
        activeCookieImportState.statusHtml = `<span>Successfully imported ${res.imported_count} account(s)!${res.failed_count > 0 ? ` (${res.failed_count} invalid or failed)` : ''}</span>`;
        toast(`Successfully imported ${res.imported_count} account(s)!`, 'success');
        if (res.failed_count > 0) {
          toast(`${res.failed_count} cookie(s) were invalid or failed validation.`, 'info');
        }
        await refreshAccountList();
      } else {
        const errMsg = res.errors?.join(', ') || 'Unknown error';
        activeCookieImportState.statusType = 'error';
        activeCookieImportState.statusHtml = `<span>Bulk import failed: ${errMsg}</span>`;
        toast(`Bulk import failed: ${errMsg}`, 'error');
      }
    } catch (error) {
      hideImportBanner();
      activeCookieImportState.isRunning = false;
      activeCookieImportState.rawInput = '';
      activeCookieImportState.parsedCount = 0;
      activeCookieImportState.statusType = 'error';
      activeCookieImportState.statusHtml = `<span>Failed to import accounts: ${String(error)}</span>`;
      addLog('Cookie import failed: ' + error, 'error');
      toast('Failed to import accounts: ' + error, 'error');
    }

    if (activeCookieImportModalElements && document.body.contains(activeCookieImportModalElements.overlay)) {
      const currentModalInputEl = activeCookieImportModalElements.inputEl;
      if (currentModalInputEl) {
        currentModalInputEl.value = '';
      }
      const currentModalStatusEl = activeCookieImportModalElements.statusEl;
      if (currentModalStatusEl) {
        currentModalStatusEl.style.display = 'flex';
        currentModalStatusEl.style.alignItems = 'center';
        currentModalStatusEl.style.gap = '8px';
        if (activeCookieImportState.statusType === 'success') {
          currentModalStatusEl.style.background = 'rgba(16, 185, 129, 0.12)';
          currentModalStatusEl.style.border = '1px solid rgba(16, 185, 129, 0.3)';
          currentModalStatusEl.style.color = 'var(--emerald)';
        } else if (activeCookieImportState.statusType === 'error') {
          currentModalStatusEl.style.background = 'rgba(239, 68, 68, 0.12)';
          currentModalStatusEl.style.border = '1px solid rgba(239, 68, 68, 0.3)';
          currentModalStatusEl.style.color = 'var(--rose)';
        }
        currentModalStatusEl.innerHTML = activeCookieImportState.statusHtml;
      }
      activeCookieImportModalElements.updateCount();
    }
  });
}

function showCredentialsImportModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal account-modal">
      <div class="modal-header">
        <h3>User:Pass Import</h3>
        <button class="modal-close" id="modal-close">×</button>
      </div>
      <div class="modal-body">
        <div class="field">
          <label>Credentials (username:password per line)</label>
          <textarea id="cred-input" rows="4" placeholder="user1:password1&#10;user2:password2&#10;user3:password3" autocomplete="off"></textarea>
        </div>
        <div class="field" style="margin-bottom:0;">
          <label>Instances (Concurrent Browsers, 1-5)</label>
          <input type="number" id="cred-instances" value="${Math.min(5, Math.max(1, state.settings.credentialImportInstances || 1))}" min="1" max="5" autocomplete="off">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="modal-cancel">Cancel</button>
        <button class="btn btn-primary" id="modal-confirm">Import</button>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  const closeBtn = document.getElementById('modal-close');
  const cancelBtn = document.getElementById('modal-cancel');
  const confirmBtn = document.getElementById('modal-confirm') as HTMLButtonElement;

  const closeModal = () => {
    overlay.remove();
  };

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });

  confirmBtn?.addEventListener('click', async () => {
    const input = (document.getElementById('cred-input') as HTMLTextAreaElement).value;
    const browser = state.settings.preferredBrowser || 'auto';
    const instancesVal = parseInt((document.getElementById('cred-instances') as HTMLInputElement)?.value) || 1;
    const maxConcurrent = Math.min(5, Math.max(1, instancesVal));
    state.settings.credentialImportInstances = maxConcurrent;

    addLog('Using browser setting for credentials: ' + browser + ' with ' + maxConcurrent + ' instance(s) (from settings: ' + state.settings.preferredBrowser + ')', 'info');

    if (!input.trim()) {
      toast('Please enter at least one credential', 'error');
      return;
    }

    const lines = input.trim().split(/[\r\n]+/);
    const credentials: [string, string][] = [];

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      const parts = trimmed.split(/[:,\t\s]+/);
      if (parts.length >= 2) {
        const username = parts[0];
        const password = parts.slice(1).join('');
        if (username && password) {
          credentials.push([username, password]);
        }
      }
    }

    if (credentials.length === 0) {
      toast('No valid credentials found. Please use format: username:password', 'error');
      return;
    }

    confirmBtn.disabled = true;
    confirmBtn.innerHTML = `<span class="loading-spinner-inline"></span> Starting Login (${credentials.length})...`;
    showImportBanner(`Logging in ${credentials.length} account${credentials.length > 1 ? 's' : ''} via ${maxConcurrent} browser${maxConcurrent > 1 ? 's' : ''}...`);

    try {
      await apiService.addAccountCredentials(credentials, browser, maxConcurrent);
      closeModal();

      let pollCount = 0;
      let wasUserClosed = false;
      const initialAccountsCount = (state.accounts || []).length;

      const pollTimer = setInterval(async () => {
        pollCount++;
        await refreshAccountList();
        const currentCount = (state.accounts || []).length;
        const newlyAdded = Math.max(0, currentCount - initialAccountsCount);

        let isRunning = true;
        try {
          const bStatus = await apiService.getBrowserStatus();
          isRunning = Boolean(bStatus.is_running);
          if (bStatus.user_closed || bStatus.last_close_reason === 'user_closed') {
            wasUserClosed = true;
          }
        } catch (_) { }

        if (newlyAdded > 0 && newlyAdded < credentials.length) {
          showImportBanner(`Importing credentials (${newlyAdded}/${credentials.length} account${credentials.length > 1 ? 's' : ''} imported)...`);
        } else if (newlyAdded === 0) {
          showImportBanner(`Logging in ${credentials.length} account${credentials.length > 1 ? 's' : ''} via browser automation...`);
        }

        if (newlyAdded >= credentials.length || !isRunning || pollCount >= 180) {
          clearInterval(pollTimer);
          hideImportBanner();
          if (newlyAdded > 0) {
            toast(`Credential import complete: ${newlyAdded} account(s) added!`, 'success');
            await refreshAccountList();
          } else if (wasUserClosed) {
            toast('User closed browser.', 'info');
            addLog('Credential login ended: user closed browser.', 'info');
          } else if (!isRunning && pollCount > 1) {
            toast('Credential login process ended.', 'info');
          }
          confirmBtn.disabled = false;
          confirmBtn.textContent = 'Import';
        }
      }, 1000);
    } catch (error) {
      hideImportBanner();
      addLog('Credential import failed: ' + error, 'error');
      toast('Failed to start credential login', 'error');
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Import';
    }
  });
}

function showQuickSignInModal(): void {
  const app = document.getElementById('app');
  if (!app) return;

  const selectedBrowser = state.settings.preferredBrowser || 'auto';

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal account-modal" style="max-width: 480px; width: 100%; padding: 18px 20px;">
      <div class="modal-body" style="padding: 0; margin: 0;">
        <div class="qsi-container" id="qsi-dynamic-content">
          <div class="qsi-status-badge">
            <div class="qsi-status-info">
              <div class="qsi-pulse-dot"></div>
              <span>Starting Quick Sign-In...</span>
            </div>
            <button class="qsi-close-btn" id="qsi-status-close" title="Close">×</button>
          </div>

          <div class="qsi-code-card">
            <div class="qsi-loading-radar"></div>
            <p style="margin: 0; font-size: 13px; color: var(--fg-2);">Generating one-time sign-in code...</p>
          </div>

          <div class="qsi-instructions-card">
            <ol>
              <li>Open <strong>Roblox</strong> on your phone or logged-in browser.</li>
              <li>Go to <strong>Settings (⚙️) → Quick Log In</strong>.</li>
              <li>Enter the 6-character code and tap <strong>Confirm</strong>.</li>
            </ol>
          </div>

          <div class="qsi-timer-row">
            <span>Session validity:</span>
            <span class="qsi-timer-badge" id="qsi-timer-badge">⏱️ 5:00</span>
          </div>
        </div>
      </div>

      <div class="modal-footer" id="qsi-modal-footer" style="padding: 12px 0 0 0; margin-top: 14px; border-top: 1px solid var(--border);">
        <button class="btn btn-secondary" id="qsi-btn-cancel">Cancel</button>
      </div>
    </div>
  `;

  app.appendChild(overlay);

  const cancelBtn = document.getElementById('qsi-btn-cancel');
  const dynamicContent = document.getElementById('qsi-dynamic-content');
  const modalFooter = document.getElementById('qsi-modal-footer');

  let pollingInterval: number | null = null;
  let countdownInterval: number | null = null;
  let sessionId: string | null = null;
  let remainingSeconds = 300;
  let isClosed = false;

  const cleanup = () => {
    isClosed = true;
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
    if (countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }
    if (sessionId) {
      apiService.cancelQuickSignIn(sessionId).catch(() => { });
    }
    overlay.remove();
  };

  document.getElementById('qsi-status-close')?.addEventListener('click', cleanup);
  cancelBtn?.addEventListener('click', cleanup);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) cleanup();
  });

  let currentRenderedCode = '';
  let currentRenderedQr = '';

  const renderActiveView = (statusText: string, code: string = '', qrUrl: string = '') => {
    if (!dynamicContent || isClosed) return;

    if (currentRenderedCode === code && currentRenderedQr === qrUrl && dynamicContent.querySelector('.qsi-status-info span')) {
      const statusSpan = dynamicContent.querySelector('.qsi-status-info span');
      if (statusSpan && statusSpan.textContent !== statusText) {
        statusSpan.textContent = statusText;
      }
      return;
    }

    currentRenderedCode = code;
    currentRenderedQr = qrUrl;

    let codeMarkup = '';
    if (code) {
      const charTiles = code.split('').map(c => `<div class="qsi-tile">${c}</div>`).join('');
      codeMarkup = `
        <div class="qsi-code-card">
          <div class="qsi-code-tiles">${charTiles}</div>
          <div class="qsi-code-actions">
            <button class="qsi-btn-copy" id="qsi-copy-code-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy Code
            </button>
            <button class="qsi-btn-open" id="qsi-open-roblox-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
              Open Quick Login
            </button>
          </div>
          ${qrUrl ? `<div class="qsi-qr-wrapper"><img src="${qrUrl}" alt="Roblox Quick Sign-In QR" /></div>` : ''}
        </div>
      `;
    } else {
      codeMarkup = `
        <div class="qsi-code-card">
          <div class="qsi-loading-radar"></div>
          <p style="margin: 0; font-size: 13px; color: var(--fg-2);">Generating one-time sign-in code...</p>
        </div>
      `;
    }

    dynamicContent.innerHTML = `
      <div class="qsi-status-badge">
        <div class="qsi-status-info">
          <div class="qsi-pulse-dot"></div>
          <span>${statusText}</span>
        </div>
        <button class="qsi-close-btn" id="qsi-status-close" title="Close">×</button>
      </div>

      ${codeMarkup}

      <div class="qsi-instructions-card">
        <ol>
          <li>Open <strong>Roblox</strong> on your phone or logged-in browser.</li>
          <li>Go to <strong>Settings (⚙️) → Quick Log In</strong>.</li>
          <li>Enter the code <strong>${code || '...'}</strong> and tap <strong>Confirm</strong>.</li>
        </ol>
      </div>

      <div class="qsi-timer-row">
        <span>Session validity:</span>
        <span class="qsi-timer-badge" id="qsi-timer-badge">
          ⏱️ ${Math.floor(remainingSeconds / 60)}:${(remainingSeconds % 60).toString().padStart(2, '0')}
        </span>
      </div>
    `;

    document.getElementById('qsi-status-close')?.addEventListener('click', cleanup);

    const copyBtn = document.getElementById('qsi-copy-code-btn');
    copyBtn?.addEventListener('click', () => {
      if (!code) return;
      navigator.clipboard.writeText(code).then(() => {
        copyBtn.classList.add('copied');
        copyBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          Copied!
        `;
        setTimeout(() => {
          if (!isClosed && copyBtn) {
            copyBtn.classList.remove('copied');
            copyBtn.innerHTML = `
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy Code
            `;
          }
        }, 2000);
      });
    });

    const openRobloxBtn = document.getElementById('qsi-open-roblox-btn');
    openRobloxBtn?.addEventListener('click', () => {
      openExternal('https://www.roblox.com/my/account#!/security').catch(() => { });
    });
  };

  const renderSuccessView = (username: string, displayName?: string, avatarUrl?: string) => {
    if (!dynamicContent || isClosed) return;

    if (modalFooter) {
      modalFooter.innerHTML = `<button class="btn btn-primary" id="qsi-done-btn">Done</button>`;
      document.getElementById('qsi-done-btn')?.addEventListener('click', cleanup);
    }

    const defaultAvatarSvg = `
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
        <circle cx="12" cy="7" r="4"></circle>
      </svg>
    `;

    dynamicContent.innerHTML = `
      <div class="qsi-success-card">
        <div class="qsi-avatar-glow">
          ${avatarUrl ? `<img src="${avatarUrl}" alt="${username}" />` : defaultAvatarSvg}
        </div>
        <div>
          <h4 class="qsi-success-name">${displayName || username}</h4>
          <p class="qsi-success-user">@${username}</p>
        </div>
        <div class="qsi-status-badge" style="border-color: #10b981; background: rgba(16, 185, 129, 0.1); color: #10b981;">
          <div class="qsi-status-info">
            <div class="qsi-pulse-dot success"></div>
            <span>Account connected successfully!</span>
          </div>
          <button class="qsi-close-btn" id="qsi-status-close" title="Close">×</button>
        </div>
      </div>
    `;

    document.getElementById('qsi-status-close')?.addEventListener('click', cleanup);

    setTimeout(async () => {
      await refreshAccountList();
    }, 400);

    setTimeout(() => {
      if (!isClosed) cleanup();
    }, 2500);
  };

  const renderErrorView = (errorMsg: string) => {
    if (!dynamicContent || isClosed) return;
    if (modalFooter) {
      modalFooter.innerHTML = `
        <button class="btn btn-secondary" id="qsi-err-close">Close</button>
        <button class="btn btn-primary" id="qsi-err-retry">Try Again</button>
      `;
      document.getElementById('qsi-err-close')?.addEventListener('click', cleanup);
      document.getElementById('qsi-err-retry')?.addEventListener('click', () => {
        cleanup();
        showQuickSignInModal();
      });
    }

    dynamicContent.innerHTML = `
      <div class="qsi-status-badge" style="border-color: #ef4444; background: rgba(239, 68, 68, 0.1); color: #ef4444;">
        <div class="qsi-status-info">
          <div class="qsi-pulse-dot error"></div>
          <span>${errorMsg}</span>
        </div>
        <button class="qsi-close-btn" id="qsi-status-close" title="Close">×</button>
      </div>
      <div class="qsi-instructions-card" style="margin-top: 12px;">
        <p style="margin: 0; font-size: 12px; color: var(--fg-2); line-height: 1.5;">
          Make sure you approve the code in your Roblox app before the 5-minute window expires.
        </p>
      </div>
    `;

    document.getElementById('qsi-status-close')?.addEventListener('click', cleanup);
  };

  const pollStatus = async () => {
    if (!sessionId || isClosed) return;

    try {
      const data = await apiService.getQuickSignInStatus(sessionId);
      if (isClosed) return;

      const statusMsg = data.status_message || data.status || 'Processing...';

      if (data.status === 'code_ready' || data.code) {
        renderActiveView(statusMsg, data.code, data.qr_image_url);
      } else if (data.status === 'starting') {
        renderActiveView(statusMsg);
      }

      if (data.result || data.status === 'completed' || data.status === 'error' || data.status === 'cancelled') {
        if (pollingInterval) {
          clearInterval(pollingInterval);
          pollingInterval = null;
        }

        if (data.result?.success || data.status === 'completed') {
          const res = data.result || { username: 'Account', success: true };
          addLog(`Quick Sign-In successfully authenticated: ${res.username}`, 'success');
          toast(`Account connected: ${res.username}`, 'success');
          renderSuccessView(res.username, res.display_name, res.avatar_url);
        } else if (data.status === 'cancelled') {
          addLog('Quick Sign-In session cancelled.', 'info');
          renderErrorView('Quick Sign-In was cancelled.');
        } else {
          const errMsg = data.result?.error || data.error || 'Quick Sign-In timed out or failed';
          addLog(`Quick Sign-In failed: ${errMsg}`, 'error');
          toast(`Quick Sign-In failed: ${errMsg}`, 'error');
          renderErrorView(errMsg);
        }
      }
    } catch (err) {
      if (!isClosed) {
        console.error('Failed to poll Quick Sign-In status:', err);
      }
    }
  };

  const startProcess = async () => {
    addLog(`Starting Quick Sign-In session with preferred browser: ${selectedBrowser}`, 'info');

    try {
      const response = await apiService.startQuickSignIn(selectedBrowser);
      if (response.success && response.session_id) {
        sessionId = response.session_id;
        addLog(`Quick Sign-In session started (ID: ${sessionId})`, 'info');

        pollingInterval = window.setInterval(pollStatus, 500);

        countdownInterval = window.setInterval(() => {
          if (remainingSeconds > 0) {
            remainingSeconds--;
            const timerBadge = document.getElementById('qsi-timer-badge');
            if (timerBadge) {
              timerBadge.textContent = `⏱️ ${Math.floor(remainingSeconds / 60)}:${(remainingSeconds % 60).toString().padStart(2, '0')}`;
            }
          }
        }, 1000);
      } else {
        const err = response.error || 'Failed to start session';
        addLog(`Failed to start Quick Sign-In: ${err}`, 'error');
        toast(`Failed to start Quick Sign-In: ${err}`, 'error');
        renderErrorView(err);
      }
    } catch (err) {
      console.error('Failed to start Quick Sign-In:', err);
      addLog(`Failed to start Quick Sign-In: ${err}`, 'error');
      toast('Failed to start Quick Sign-In', 'error');
      renderErrorView(String(err));
    }
  };

  startProcess();
}

async function handleValidateAccount(a: Account): Promise<void> {
  try {
    toast(`Validating cookie for @${a.username || 'account'}...`, 'info');
    const res = await apiService.validateAccount(a.id);
    const idx = state.accounts.findIndex(acc => acc.id === a.id);
    if (idx !== -1) {
      state.accounts[idx] = res.account;
    }
    if (res.status === 'valid') {
      toast(`Cookie is VALID for @${res.account.username}`, 'success');
    } else if (res.status === 'banned') {
      toast(`Account @${res.account.username} is BANNED`, 'error');
    } else {
      toast(`Cookie is EXPIRED for @${res.account.username || a.username}`, 'error');
    }
    renderAll();
  } catch (error) {
    addLog(`Validation failed for @${a.username}: ${error}`, 'error');
    toast(`Failed to validate cookie for @${a.username}`, 'error');
  }
}

async function handleValidateSelectedAccounts(): Promise<void> {
  const selected = getSelectedAccounts();
  if (selected.length === 0) return;
  toast(`Validating cookies for ${selected.length} account(s)...`, 'info');
  let validCount = 0;
  let expiredCount = 0;
  let bannedCount = 0;
  for (const a of selected) {
    try {
      const res = await apiService.validateAccount(a.id);
      const idx = state.accounts.findIndex(acc => acc.id === a.id);
      if (idx !== -1) {
        state.accounts[idx] = res.account;
      }
      if (res.status === 'valid') validCount++;
      else if (res.status === 'banned') bannedCount++;
      else expiredCount++;
    } catch (error) {
      expiredCount++;
    }
  }
  toast(`Validated ${selected.length} account(s): ${validCount} valid, ${expiredCount} expired, ${bannedCount} banned`, 'success');
  renderAll();
}

async function handleValidateSelectedAccountsSilently(): Promise<void> {
  const accountsToValidate = state.accounts || [];
  if (accountsToValidate.length === 0) return;
  for (const a of accountsToValidate) {
    try {
      const res = await apiService.validateAccount(a.id);
      const idx = state.accounts.findIndex(acc => acc.id === a.id);
      if (idx !== -1) {
        state.accounts[idx] = res.account;
      }
    } catch (error) { }
  }
  renderAll();
}

function openRowMenu(id: number, anchor: HTMLElement | MouseEvent): void {
  currentMenuAccountId = id;
  const pop = document.getElementById('row-popover');
  if (!pop) return;

  const selectedAccounts = getSelectedAccounts();
  const isMulti = selectedAccounts.length > 1;
  const count = selectedAccounts.length;

  if (isMulti) {
    pop.innerHTML = `
      <button data-action="launch-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>Launch All (${count})</button>
      <button data-action="browser-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>Open in browser (${count})</button>
      <button data-action="validate-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>Validate Accounts (${count})</button>
      <button data-action="set-group-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>Set Group (${count})</button>
      <button data-action="enable-auto-rejoin-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>Enable Auto-Rejoin (${count})</button>
      <button data-action="disable-auto-rejoin-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>Disable Auto-Rejoin (${count})</button>
      <button data-action="enable-anti-afk-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/></svg>Enable Anti-AFK (${count})</button>
      <button data-action="disable-anti-afk-multi"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/></svg>Disable Anti-AFK (${count})</button>
      <hr>
      <button data-action="copy-usernames"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>Copy usernames (${count})</button>
      <button data-action="copy-passwords"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Copy passwords (${count})</button>
      <button data-action="copy-cookies"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0-2 19.8"/></svg>Copy cookies (${count})</button>
      <button data-action="copy-userpass"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>Copy user:pass combo (${count})</button>
      <button data-action="copy-userpasscookie"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>Copy user:pass:cookie combo (${count})</button>
      <hr>
      <button data-action="delete-multi" style="color:var(--red);"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>Delete selected (${count})</button>
    `;
  } else {
    const targetAcc = getAccount(id);
    pop.innerHTML = `
      <button data-action="launch"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>Launch Roblox</button>
      <button data-action="browser"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>Open in browser</button>
      <button data-action="view"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>View details</button>
      <button data-action="validate"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>Validate Account</button>
      <button data-action="set-group"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>Set Group</button>
      <button data-action="toggle-auto-rejoin"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>${targetAcc?.auto_rejoin_enabled ? 'Disable' : 'Enable'} Auto-Rejoin</button>
      <button data-action="toggle-anti-afk"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/></svg>${targetAcc?.anti_afk_enabled ? 'Disable' : 'Enable'} Anti-AFK</button>
      <hr>
      <button data-action="copy"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>Copy username</button>
      <button data-action="copy-password"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Copy password</button>
      <button data-action="cookie"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0-2 19.8"/></svg>Copy cookie</button>
      <button data-action="copy-userpass"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>Copy user:pass combo</button>
      <button data-action="copy-userpasscookie"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>Copy user:pass:cookie combo</button>
      <hr>
      <button data-action="delete" style="color:var(--red);"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>Delete</button>
    `;
  }

  if (anchor instanceof MouseEvent) {
    pop.style.top = (anchor.clientY + 4 + window.scrollY) + 'px';
    pop.style.left = (anchor.clientX - 140 + window.scrollX) + 'px';
  } else {
    const rect = anchor.getBoundingClientRect();
    pop.style.top = (rect.bottom + 4 + window.scrollY) + 'px';
    pop.style.left = (rect.left - 130 + window.scrollX) + 'px';
  }
  pop.classList.add('show');
}

function isEditingInput(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

function showShortcutsModal(): void {
  const existing = document.getElementById('shortcuts-modal-overlay');
  if (existing) {
    existing.remove();
    return;
  }

  const formatActionKeys = (actionId: string, fallbackStatic?: string): string => {
    const keys = getKeybinds(actionId);
    if (keys.length === 0) {
      return fallbackStatic || `<span style="color:var(--text-muted);">None</span>`;
    }
    return keys.map(k => {
      const parts = k.split('+');
      return parts.map(p => `<kbd>${p}</kbd>`).join(' + ');
    }).join(' <span style="font-size:11px; color:var(--text-muted); margin:0 3px;">or</span> ');
  };

  const overlay = el('div', { id: 'shortcuts-modal-overlay', class: 'overlay show' }, []);
  overlay.innerHTML = `
    <div class="shortcuts-modal">
      <div class="shortcuts-header">
        <h3>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="6" y1="9" x2="6.01" y2="9"/><line x1="10" y1="9" x2="10.01" y2="9"/><line x1="14" y1="9" x2="14.01" y2="9"/><line x1="18" y1="9" x2="18.01" y2="9"/><line x1="6" y1="13" x2="6.01" y2="13"/><line x1="18" y1="13" x2="18.01" y2="13"/><line x1="9" y1="13" x2="15" y2="13"/></svg>
          Keyboard Shortcuts
        </h3>
        <button class="win-btn close" id="shortcuts-modal-close" style="width:26px;height:26px;font-size:12px;" title="Close">✕</button>
      </div>
      <div class="shortcuts-body">
        <div class="shortcuts-group">
          <div class="shortcuts-category-title">App Navigation</div>
          <div class="shortcuts-list">
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to Accounts List</span>
              <div class="shortcut-keys">${formatActionKeys('nav_accounts')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to Instance Manager</span>
              <div class="shortcut-keys">${formatActionKeys('nav_instances')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to VIP Servers</span>
              <div class="shortcut-keys">${formatActionKeys('nav_vip')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to Console Logs</span>
              <div class="shortcut-keys">${formatActionKeys('nav_console')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to Webhook Manager</span>
              <div class="shortcut-keys">${formatActionKeys('nav_webhooks')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to Extensions</span>
              <div class="shortcut-keys">${formatActionKeys('nav_extensions')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to Generator</span>
              <div class="shortcut-keys">${formatActionKeys('nav_bloxgen')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Switch to FastFlags</span>
              <div class="shortcut-keys">${formatActionKeys('nav_fastflags')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Open Settings</span>
              <div class="shortcut-keys">${formatActionKeys('nav_settings')}</div>
            </div>
          </div>
        </div>

        <div class="shortcuts-group">
          <div class="shortcuts-category-title">Account List</div>
          <div class="shortcuts-list">
            ${state.settings.multiSelect ? `
            <div class="shortcut-item">
              <span class="shortcut-label">Multi-select account</span>
              <div class="shortcut-keys">${formatActionKeys('multi_select')}</div>
            </div>` : ''}
            <div class="shortcut-item">
              <span class="shortcut-label">Select all accounts</span>
              <div class="shortcut-keys">${formatActionKeys('select_all')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Deselect all accounts</span>
              <div class="shortcut-keys">${formatActionKeys('deselect_all')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Navigate accounts</span>
              <div class="shortcut-keys"><kbd>↑</kbd> <kbd>↓</kbd></div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Expand selection (range)</span>
              <div class="shortcut-keys"><kbd>Shift</kbd> + <kbd>↑</kbd> <kbd>↓</kbd></div>
            </div>
            ${state.settings.multiSelect ? `
            <div class="shortcut-item">
              <span class="shortcut-label">Toggle account in multi-select</span>
              <div class="shortcut-keys"><kbd>Space</kbd></div>
            </div>` : ''}
            <div class="shortcut-item">
              <span class="shortcut-label">Launch selected account(s)</span>
              <div class="shortcut-keys">${formatActionKeys('launch_selected')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Reorder account up / down</span>
              <div class="shortcut-keys"><kbd>Alt</kbd> + <kbd>↑</kbd> <kbd>↓</kbd></div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Delete selected account(s)</span>
              <div class="shortcut-keys">${formatActionKeys('delete_selected')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Add new account</span>
              <div class="shortcut-keys">${formatActionKeys('add_account')}</div>
            </div>
          </div>
        </div>

        <div class="shortcuts-group">
          <div class="shortcuts-category-title">Roblox Tools</div>
          <div class="shortcuts-list">
            <div class="shortcut-item">
              <span class="shortcut-label">Auto-arrange Roblox windows</span>
              <div class="shortcut-keys">${formatActionKeys('tool_auto_arrange')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Force quit Roblox clients (Kill)</span>
              <div class="shortcut-keys">${formatActionKeys('tool_kill_roblox')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Trim Roblox RAM</span>
              <div class="shortcut-keys">${formatActionKeys('tool_trim_memory')}</div>
            </div>
          </div>
        </div>

        <div class="shortcuts-group">
          <div class="shortcuts-category-title">General & Utilities</div>
          <div class="shortcuts-list">
            <div class="shortcut-item">
              <span class="shortcut-label">Search</span>
              <div class="shortcut-keys">${formatActionKeys('search')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Refresh current view</span>
              <div class="shortcut-keys">${formatActionKeys('refresh')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Back / Clear search / Close modal</span>
              <div class="shortcut-keys">${formatActionKeys('close_or_clear')}</div>
            </div>
            <div class="shortcut-item">
              <span class="shortcut-label">Show keyboard shortcuts</span>
              <div class="shortcut-keys">${formatActionKeys('shortcuts_help')}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  const closeBtn = document.getElementById('shortcuts-modal-close');
  const closeModal = () => overlay.remove();

  closeBtn?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal();
  });
}

let shortcutsInitialized = false;
function setupKeyboardShortcuts(): void {
  if (shortcutsInitialized) return;
  shortcutsInitialized = true;

  window.addEventListener('keydown', (e: KeyboardEvent) => {
    if (activeRecordingKeybindId) {
      return;
    }

    // 1. Escape / Close or Clear action (prioritize active modals/menus/focus/subviews)
    if (e.key === 'Escape' || matchesAction(e, 'close_or_clear')) {
      const shortcutsOverlay = document.getElementById('shortcuts-modal-overlay');
      if (shortcutsOverlay) {
        e.preventDefault();
        shortcutsOverlay.remove();
        return;
      }

      const addAccountMenu = document.getElementById('add-account-menu');
      if (addAccountMenu) {
        e.preventDefault();
        addAccountMenu.remove();
        return;
      }

      const rowPopover = document.getElementById('row-popover');
      if (rowPopover?.classList.contains('show')) {
        e.preventDefault();
        rowPopover.classList.remove('show');
        return;
      }

      const confirmOverlay = document.getElementById('confirm-modal-overlay');
      if (confirmOverlay?.classList.contains('show')) {
        e.preventDefault();
        const cancelBtn = document.getElementById('confirm-modal-cancel') as HTMLButtonElement | null;
        if (cancelBtn) {
          cancelBtn.click();
        } else {
          confirmOverlay.classList.remove('show');
        }
        return;
      }

      const anyOverlay = Array.from(document.querySelectorAll<HTMLElement>('.overlay')).find(o =>
        o.id !== 'unlock-overlay' && (o.classList.contains('show') || window.getComputedStyle(o).display === 'flex')
      );
      if (anyOverlay) {
        e.preventDefault();
        const closeBtn = anyOverlay.querySelector<HTMLElement>('#modal-close, #modal-cancel, .close-btn, .win-btn.close');
        if (closeBtn) {
          closeBtn.click();
        } else {
          anyOverlay.remove();
        }
        return;
      }

      const searchInput = document.getElementById('search-input') as HTMLInputElement | null;
      if (document.activeElement === searchInput) {
        e.preventDefault();
        if (searchInput && searchInput.value) {
          searchInput.value = '';
          state.search = '';
          renderAll();
        }
        searchInput?.blur();
        return;
      }

      const settingsSearchInput = document.getElementById('settings-search-input') as HTMLInputElement | null;
      if (document.activeElement === settingsSearchInput) {
        e.preventDefault();
        if (settingsSearchInput && settingsSearchInput.value) {
          settingsSearchInput.value = '';
          state.settingsSearch = '';
          renderSettingsView();
        }
        settingsSearchInput?.blur();
        return;
      }

      if (isEditingInput(document.activeElement)) {
        (document.activeElement as HTMLElement).blur();
        return;
      }

      if (state.settingsTab === 'custom-theme') {
        e.preventDefault();
        themeEditingTarget = null;
        state.settingsTab = 'appearance';
        renderSettingsView();
        return;
      }

      if (state.view === 'accounts' && (state.selectedIds.size > 0 || state.selectedId != null)) {
        e.preventDefault();
        state.selectedIds = new Set();
        state.selectedId = null;
        renderAll();
        return;
      }

      if (state.view !== 'accounts') {
        e.preventDefault();
        state.revealed = {};
        state.view = 'accounts';
        renderAll();
        return;
      }

      return;
    }

    // Shielding for setup wizard or app lock
    if (state.isLocked || showSetup) return;

    // 2. Global shortcuts that work anywhere in the application
    // Shortcuts Help
    if (matchesAction(e, 'shortcuts_help') || (!isEditingInput(e.target) && e.key === '?')) {
      e.preventDefault();
      showShortcutsModal();
      return;
    }

    // View Navigation
    if (matchesAction(e, 'nav_accounts')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'accounts';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_instances')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'instances';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_vip')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'vip';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_console')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'console';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_webhooks')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'webhooks';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_extensions')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'extensions';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_bloxgen')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'bloxgen';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_fastflags')) {
      e.preventDefault();
      state.revealed = {};
      state.previousView = state.view;
      state.view = 'fastflags';
      renderAll();
      return;
    }
    if (matchesAction(e, 'nav_settings')) {
      e.preventDefault();
      state.revealed = {};
      state.view = 'settings';
      renderAll();
      return;
    }

    // Quick Tool Actions
    if (matchesAction(e, 'tool_auto_arrange')) {
      e.preventDefault();
      const arrangeBtn = document.getElementById('btn-auto-arrange-header') as HTMLButtonElement | null;
      arrangeBtn?.click();
      return;
    }
    if (matchesAction(e, 'tool_kill_roblox')) {
      e.preventDefault();
      const killBtn = document.getElementById('btn-kill-roblox') as HTMLButtonElement | null;
      killBtn?.click();
      return;
    }
    if (matchesAction(e, 'tool_trim_memory')) {
      e.preventDefault();
      const trimBtn = document.getElementById('btn-trim-memory-header') as HTMLButtonElement | null;
      trimBtn?.click();
      return;
    }

    // Context-Aware Search
    if (matchesAction(e, 'search')) {
      e.preventDefault();
      if (state.view === 'settings') {
        const settingsSearch = document.getElementById('settings-search-input') as HTMLInputElement | null;
        if (settingsSearch) {
          settingsSearch.focus();
          settingsSearch.select();
        }
        return;
      }
      if (state.view !== 'accounts') {
        state.revealed = {};
        state.view = 'accounts';
        renderAll();
      }
      const searchInput = document.getElementById('search-input') as HTMLInputElement | null;
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
      return;
    }

    // Context-Aware Refresh
    if (matchesAction(e, 'refresh')) {
      e.preventDefault();
      if (state.view === 'accounts') {
        const btnRefresh = document.getElementById('btn-refresh') as HTMLButtonElement | null;
        btnRefresh?.click();
      } else if (state.view === 'instances') {
        const btnRefreshInstances = document.getElementById('btn-refresh-instances') as HTMLButtonElement | null;
        btnRefreshInstances?.click();
      } else if (state.view === 'settings') {
        renderSettingsView();
      } else if (state.view === 'vip') {
        renderVipView();
      } else if (state.view === 'console') {
        renderConsoleView();
      } else {
        renderAll();
      }
      return;
    }

    // If typing in input / textarea / editable, do not hijack editing keys
    if (isEditingInput(e.target)) {
      return;
    }

    // Context-Aware Add
    if (matchesAction(e, 'add_account')) {
      if (state.view === 'accounts') {
        e.preventDefault();
        const btnAdd = document.getElementById('btn-add-account');
        showAddAccountOptions(btnAdd);
        return;
      }
      if (state.view === 'vip') {
        e.preventDefault();
        const vipInp = document.getElementById('vip-input-url') as HTMLInputElement | null;
        vipInp?.focus();
        return;
      }
      return;
    }

    // 3. Below shortcuts ONLY apply when actively viewing the Accounts List
    if (state.view !== 'accounts') return;

    // Toggle Multi Select
    if (matchesAction(e, 'toggle_multi_select')) {
      e.preventDefault();
      const nextVal = !state.settings.multiSelect;
      state.settings.multiSelect = nextVal;
      updateSetting('multiSelect', nextVal).catch(() => { });
      if (!nextVal && state.selectedIds.size > 1) {
        if (state.selectedId != null) {
          state.selectedIds = new Set([state.selectedId]);
        } else if (state.selectedIds.size > 0) {
          state.selectedId = Array.from(state.selectedIds)[0];
          state.selectedIds = new Set([state.selectedId]);
        }
      }
      renderAll();
      toast(nextVal ? 'Multi Select enabled' : 'Multi Select disabled', 'info');
      return;
    }

    // Select All Accounts in list
    if (matchesAction(e, 'select_all')) {
      e.preventDefault();
      const list = filteredAccounts();
      if (list.length === 0) return;

      state.selectedIds = new Set(list.map(a => a.id));
      if (state.selectedId == null || !state.selectedIds.has(state.selectedId)) {
        state.selectedId = list[0].id;
      }
      if (!state.settings.multiSelect) {
        state.settings.multiSelect = true;
        updateSetting('multiSelect', true).catch(() => { });
      }
      state.editingId = null;
      renderAll();
      toast(`Selected ${list.length} accounts`, 'info');
      return;
    }

    // Deselect All Accounts
    if (matchesAction(e, 'deselect_all')) {
      e.preventDefault();
      if (state.selectedIds.size > 0 || state.selectedId != null) {
        state.selectedIds = new Set();
        state.selectedId = null;
        renderAll();
      }
      return;
    }

    // Arrow navigation (ArrowDown / ArrowUp)
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const list = filteredAccounts();
      if (list.length === 0) return;

      e.preventDefault();
      const currentIdx = state.selectedId != null ? list.findIndex(a => a.id === state.selectedId) : -1;
      let nextIdx = currentIdx;

      if (e.key === 'ArrowDown') {
        nextIdx = currentIdx === -1 ? 0 : Math.min(currentIdx + 1, list.length - 1);
      } else {
        nextIdx = currentIdx === -1 ? 0 : Math.max(currentIdx - 1, 0);
      }

      const nextAccount = list[nextIdx];
      if (!nextAccount) return;

      if (e.shiftKey) {
        state.settings.multiSelect = true;
        state.selectedIds.add(nextAccount.id);
        state.selectedId = nextAccount.id;
      } else {
        state.selectedIds = new Set([nextAccount.id]);
        state.selectedId = nextAccount.id;
      }

      state.editingId = null;
      renderAll();

      const targetRow = document.querySelector(`tr[data-id="${nextAccount.id}"]`);
      targetRow?.scrollIntoView({ block: 'nearest' });
      return;
    }

    // Space (Toggle selection of currently highlighted account)
    if (e.key === ' ' || e.code === 'Space') {
      if (state.selectedId != null) {
        e.preventDefault();
        if (state.selectedIds.has(state.selectedId)) {
          state.selectedIds.delete(state.selectedId);
          if (state.selectedIds.size > 0) {
            state.selectedId = Array.from(state.selectedIds)[0];
          }
        } else {
          state.selectedIds.add(state.selectedId);
        }
        renderAll();
      }
      return;
    }

    // Launch selected accounts
    if (matchesAction(e, 'launch_selected')) {
      const accounts = getSelectedAccounts();
      if (accounts.length > 0) {
        e.preventDefault();
        handleLaunchSelectedAccounts();
      }
      return;
    }

    // Alt + Up / Alt + Down (Move account up / down in list)
    if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      if (state.selectedId == null) return;
      e.preventDefault();
      moveAccountPosition(state.selectedId, e.key === 'ArrowUp' ? 'up' : 'down');
      return;
    }

    // Delete / Backspace (Remove selected accounts)
    if (matchesAction(e, 'delete_selected')) {
      e.preventDefault();
      if (state.selectedIds.size > 1) {
        bulkDeleteSelected();
      } else if (state.selectedIds.size === 1 || state.selectedId != null) {
        const targetId = state.selectedId ?? Array.from(state.selectedIds)[0];
        if (targetId != null) {
          deleteAccount(targetId);
        }
      }
    }
  });
}

// Initialize the app
function initApp(): void {
  // Create the app structure
  const app = document.getElementById('app');
  if (!app) return;

  app.innerHTML = `
    <div class="titlebar" data-tauri-drag-region>
      <div class="logo">
        <img src="${getThemeIconUrl(state.settings.selectedTheme || 'default-dark')}" alt="FRAM" class="logo-icon" />
        <span class="title">Roblox Account Manager</span>
      </div>
      <div class="spacer"></div>
      <button class="win-btn" id="btn-min" title="Minimize">–</button>
      <button class="win-btn close" id="btn-close" title="Close">✕</button>
    </div>

    <div class="body">
      <!-- rail -->
      <div class="rail">
        <button class="rail-btn" id="btn-accounts" title="Accounts List">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </button>
        <button class="rail-btn" id="btn-instances" title="Instance Manager">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        </button>
        <button class="rail-btn" id="btn-vip" title="VIP Servers">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/></svg>
        </button>
        <button class="rail-btn" id="btn-console" title="Console">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
        </button>
        <button class="rail-btn" id="btn-roblox-installer" title="Roblox Installer">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </button>
        <button class="rail-btn" id="btn-webhooks" title="Webhook Manager">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        </button>
        <button class="rail-btn" id="btn-extensions" title="Extension Manager">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-blocks"><path d="M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2"/><rect x="14" y="2" width="8" height="8" rx="1"/></svg>
        </button>
        <button class="rail-btn" id="btn-bloxgen" title="BloxGen Account Manager">
          <svg viewBox="0 0 24 24" fill="none" stroke="#d41313ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-user-star" style="color:#8b0000;"><path d="M16.051 12.616a1 1 0 0 1 1.909.024l.737 1.452a1 1 0 0 0 .737.535l1.634.256a1 1 0 0 1 .588 1.806l-1.172 1.168a1 1 0 0 0-.282.866l.259 1.613a1 1 0 0 1-1.541 1.134l-1.465-.75a1 1 0 0 0-.912 0l-1.465.75a1 1 0 0 1-1.539-1.133l.258-1.613a1 1 0 0 0-.282-.866l-1.156-1.153a1 1 0 0 1 .572-1.822l1.633-.256a1 1 0 0 0 .737-.535z"/><path d="M8 15H7a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/></svg>
        </button>
        <div class="rail-spacer"></div>
        <a href="https://github.com/hackyue/ForkedRobloxAccountManager" target="_blank" rel="noopener noreferrer" class="rail-btn rail-social-btn github" title="GitHub Repository">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
        </a>
        <a href="https://www.youtube.com/@hackyue" target="_blank" rel="noopener noreferrer" class="rail-btn rail-social-btn youtube" title="YouTube Channel">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.56 49.56 0 0 1-16.2 0A2 2 0 0 1 2.5 17"/><polygon points="10 15 15 12 10 9 10 15"/></svg>
        </a>
        <a href="https://discord.gg/SpMTxg8YjJ" target="_blank" rel="noopener noreferrer" class="rail-btn rail-social-btn discord" title="Discord Community">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.093.252-.19.37-.287a.075.075 0 0 1 .078-.01c3.927 1.793 8.18 1.793 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.077.077 0 0 1-.006.128c-.598.35-1.22.648-1.873.892-.043.016-.062.066-.041.107.356.698.767 1.363 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
        </a>
        <button class="rail-btn" id="btn-about" title="About">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        </button>
        <button class="rail-btn" id="btn-settings" title="Settings">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
      </div>

      <!-- main col -->
      <div class="main-col">
        <div class="view show" id="accounts-view">
          <div class="headerbar">
            <div class="pill accounts">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>
              <b id="stat-total">0</b> accounts
            </div>
            <div class="pill valid"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg><b id="stat-valid">0</b> valid</div>
            <div class="pill expired"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m14.5 9.5-5 5"/><path d="m9.5 9.5 5 5"/></svg><b id="stat-expired">0</b> expired</div>
            <div class="pill banned"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/></svg><b id="stat-banned">0</b> banned</div>
            <div class="header-spacer"></div>
            <div class="header-tools">
              <button class="header-tool-btn header-tool-btn-wide" id="btn-add-account" title="Add New Roblox Account">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="13" height="13"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
                <span>Add Account</span>
              </button>
              <button class="header-tool-btn" id="btn-trim-memory-header" title="Trim Roblox Memory (Reclaim RAM)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>
              </button>
              <button class="header-tool-btn" id="btn-auto-arrange-header" title="Auto-Arrange Roblox Client Windows">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>
              </button>
              <button class="header-tool-btn header-tool-kill" id="btn-kill-roblox" title="Force Quit Roblox (Kill Processes)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
              </button>
              <button class="header-tool-btn" id="btn-refresh" title="Refresh Statuses">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/></svg>
              </button>
              <select id="group-filter" class="header-tool-select"></select>
              <div class="search-wrap header-tool-search">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                <input type="search" id="search-input" placeholder="Search..." autocomplete="off">
              </div>
            </div>
          </div>

          <div class="content">
            <div class="table-wrap">
              <table id="accounts-table">
                <thead>
                  <tr>
                    <th style="width:32px;">#</th>
                    <th>Username</th>
                    <th style="width:100px;">Status</th>
                    <th>Group</th>
                    <th>Note</th>
                    <th style="width:36px;"></th>
                  </tr>
                </thead>
                <tbody id="table-body"></tbody>
              </table>
              <div id="empty-state" class="empty-state" style="display:none;">No accounts match your filters.</div>
            </div>

            <div class="detail-panel" id="detail-panel"></div>
          </div>

          <div class="bottombar">
            <div class="games-row" id="games-row"></div>
            <div class="launch-row">
              <div class="launch-targets-wrap">
                <div class="launch-target" id="launch-target">
                  <div class="launch-target-avatar-wrap" id="launch-target-avatar-wrap"></div>
                  <div class="launch-target-info">
                    <span class="launch-target-label">Target Account</span>
                    <b class="launch-target-name" id="launch-username">None selected</b>
                  </div>
                </div>
                <div class="launch-target launch-target-game" id="launch-target-game">
                  <div class="launch-target-avatar-wrap" id="launch-game-avatar-wrap"></div>
                  <div class="launch-target-info">
                    <span class="launch-target-label">Target Game</span>
                    <b class="launch-target-name" id="launch-game-name">Roblox Client</b>
                  </div>
                </div>
              </div>
              <div class="launch-controls">
                <div class="launch-field launch-field-place">
                  <label class="launch-field-label">Place ID / Game Target</label>
                  <div class="launch-input-wrap">
                    <input type="text" id="place-input" placeholder="Place ID..." autocomplete="off">
                    <button type="button" class="launch-mode-btn" id="place-mode-btn" title="Select target mode (Place ID, Join User)">
                      <svg class="launch-mode-arrow" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div class="launch-mode-dropdown" id="place-mode-dropdown" style="display: none;">
                      <div class="launch-mode-option active" data-mode="place">
                        <div class="launch-mode-option-info">
                          <span class="launch-mode-option-title">Place ID</span>
                          <span class="launch-mode-option-desc">Specific place or experience ID</span>
                        </div>
                        <svg class="launch-mode-check" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      </div>
                      <div class="launch-mode-option" data-mode="user">
                        <div class="launch-mode-option-info">
                          <span class="launch-mode-option-title">Join User</span>
                          <span class="launch-mode-option-desc">Follow username or user ID in-game</span>
                        </div>
                        <svg class="launch-mode-check" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="launch-field launch-field-server">
                  <label class="launch-field-label">Job ID / Server Link</label>
                  <div class="launch-input-wrap">
                    <input type="text" id="server-input" placeholder="Private Server ID / Link..." autocomplete="off">
                    <button type="button" class="launch-mode-btn launch-subplaces-btn" id="server-subplaces-btn" title="View Universe Subplaces" style="display: none;">
                      <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                    </button>
                    <button type="button" class="launch-mode-btn" id="server-mode-btn" title="Select server mode (Private Server, Job ID, Subplace)">
                      <svg class="launch-mode-arrow" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                    </button>
                    <div class="launch-mode-dropdown" id="server-mode-dropdown" style="display: none;">
                      <div class="launch-mode-option active" data-mode="vip">
                        <div class="launch-mode-option-info">
                          <span class="launch-mode-option-title">Private Server</span>
                          <span class="launch-mode-option-desc">VIP link, share link, or server code</span>
                        </div>
                        <svg class="launch-mode-check" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      </div>
                      <div class="launch-mode-option" data-mode="jobid">
                        <div class="launch-mode-option-info">
                          <span class="launch-mode-option-title">Job ID</span>
                          <span class="launch-mode-option-desc">Roblox server instance GUID / Job ID</span>
                        </div>
                        <svg class="launch-mode-check" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      </div>
                      <div class="launch-mode-option" data-mode="subplace">
                        <div class="launch-mode-option-info">
                          <span class="launch-mode-option-title">Subplace</span>
                          <span class="launch-mode-option-desc">Universe subplace ID</span>
                        </div>
                        <svg class="launch-mode-check" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="launch-field launch-field-version">
                  <label class="launch-field-label">Roblox Client Version</label>
                  <select id="version-select" class="version-select">
                    <option value="auto">Latest Version</option>
                  </select>
                </div>
              </div>
              <div class="launch-actions">
                <button class="btn btn-primary launch-btn" id="btn-launch" disabled>
                  <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>
                  Launch
                </button>
                <button class="launch-browser-btn" id="btn-launch-browser" title="Open account in browser" disabled>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- settings view -->
        <div class="view" id="settings-view">
          <div class="settings-nav">
            <div class="settings-nav-header">
              <span class="settings-nav-title">Settings</span>
              <button class="settings-nav-back-btn" id="btn-settings-back" title="Back to Accounts" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                <span>Back</span>
              </button>
            </div>
            <div class="settings-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              <input type="search" id="settings-search-input" placeholder="Search..." autocomplete="off">
            </div>
            <div class="settings-tabs" id="settings-tabs"></div>
          </div>
          <div class="settings-content">
            <div class="settings-content-inner" id="settings-content-inner"></div>
          </div>
        </div>

        <!-- instances view -->
        <div class="view" id="instances-view">
          <div class="instances-headerbar">
            <div class="instances-title-wrap">
              <h2 style="font-size:18px; font-weight:700; color:var(--text-bright); margin:0;">Instance Manager</h2>
              <span style="font-size:12px; color:var(--text-muted);">Manage active Roblox client processes & multi-instance mutex configuration</span>
            </div>
            <div class="instances-header-actions" style="display:flex; gap:10px; align-items:center;">
              <button class="btn btn-secondary" id="btn-toggle-multi-instance" style="display:flex; align-items:center; gap:6px; font-size:12px;">
                Multi-Instance: <b id="multi-inst-status-label">ENABLED</b>
              </button>
              <button class="btn btn-secondary" id="btn-trim-memory-instances" style="display:flex; align-items:center; gap:6px; font-size:12px;" title="Trim RAM working set of all running Roblox client instances">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>
                Trim Memory
              </button>
              <button class="btn btn-secondary" id="btn-arrange-instances" style="display:flex; align-items:center; gap:6px; font-size:12px;" title="Auto-arrange active Roblox client windows across your monitors">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;"><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>
                Arrange Clients
              </button>
              <button class="btn btn-secondary" id="btn-refresh-instances" style="display:flex; align-items:center; gap:6px; font-size:12px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/></svg>
                Refresh
              </button>
              <button class="btn btn-danger" id="btn-kill-all-instances" style="display:flex; align-items:center; gap:6px; font-size:12px; background:var(--red); color:#fff; border:none; padding:6px 12px; border-radius:6px; cursor:pointer;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>
                Kill All Roblox
              </button>
            </div>
          </div>
          <div class="instances-content" style="padding:20px; overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:20px;">
            <div class="instances-stats-grid">
              <div class="instance-stat-card">
                <div class="stat-icon" style="background:rgba(99,102,241,0.15); color:#6366f1;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                </div>
                <div class="stat-info">
                  <span class="stat-label">Active Game Clients</span>
                  <b class="stat-value" id="instances-stat-count">0</b>
                </div>
              </div>
              <div class="instance-stat-card">
                <div class="stat-icon" style="background:rgba(16,185,129,0.15); color:#10b981;" id="instances-stat-crash-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                </div>
                <div class="stat-info">
                  <span class="stat-label">Crash Handlers Running</span>
                  <b class="stat-value" id="instances-stat-crash-handlers">0 Running</b>
                </div>
              </div>
              <div class="instance-stat-card">
                <div class="stat-icon" style="background:rgba(6,182,212,0.15); color:#06b6d4;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>
                </div>
                <div class="stat-info">
                  <span class="stat-label">CPU Usage</span>
                  <b class="stat-value" id="instances-stat-cpu">0.0%</b>
                </div>
              </div>
              <div class="instance-stat-card">
                <div class="stat-icon" style="background:rgba(16,185,129,0.15); color:#10b981;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                </div>
                <div class="stat-info">
                  <span class="stat-label">RAM Usage</span>
                  <b class="stat-value" id="instances-stat-memory">0.0 MB</b>
                </div>
              </div>
            </div>

            <div class="instances-section">
              <div class="instances-section-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <h3 style="font-size:15px; font-weight:600; margin:0; color:var(--text-bright);">Running Process Instances</h3>
                <label style="font-size:12px; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; gap:6px;">
                  <input type="checkbox" id="instances-auto-refresh" checked> Auto-refresh (3s)
                </label>
              </div>
              <div class="instances-table-wrap" id="instances-content-body">
                <!-- Dynamically rendered -->
              </div>
            </div>
          </div>
        </div>

        <!-- vip view -->
        <div class="view" id="vip-view">
          <div class="instances-headerbar">
            <div class="instances-title-wrap">
              <h2 style="font-size:18px; font-weight:700; color:var(--text-bright); margin:0;">VIP Server Manager</h2>
              <span style="font-size:12px; color:var(--text-muted);">Assign, import, export, and launch private servers per account</span>
            </div>
            <div class="instances-header-actions" style="display:flex; gap:10px; align-items:center;">
              <select id="vip-group-filter" class="header-tool-select" style="font-size:12px; height:32px; padding:0 8px;">
                <option value="All">All Groups</option>
              </select>
              <div class="search-wrap header-tool-search" style="height:32px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                <input type="search" id="vip-search-input" placeholder="Search VIPs..." autocomplete="off">
              </div>
              <button class="btn btn-secondary" id="btn-vip-import-csv" style="display:flex; align-items:center; gap:6px; font-size:12px; height:32px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Import CSV
              </button>
              <button class="btn btn-secondary" id="btn-vip-export-csv" style="display:flex; align-items:center; gap:6px; font-size:12px; height:32px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                Export CSV
              </button>
            </div>
          </div>
          <div class="vip-content-wrap">
            <div class="instances-table-wrap" id="vip-table-wrap">
              <table class="instances-table" id="vip-table">
                <thead>
                  <tr>
                    <th style="width:40px;"><input type="checkbox" id="vip-select-all" /></th>
                    <th style="width:190px;">Account</th>
                    <th style="width:110px;">Group</th>
                    <th style="width:190px;">Game</th>
                    <th>VIP Server Link / Code</th>
                    <th style="width:100px;">Status</th>
                    <th style="width:140px;">Actions</th>
                  </tr>
                </thead>
                <tbody id="vip-table-body">
                  <!-- Dynamically rendered -->
                </tbody>
              </table>
            </div>
            <!-- VIP Bottom Control Bar -->
            <div class="vip-control-bar">
              <span id="vip-selection-label" style="font-size:12px; font-weight:600; color:var(--text-bright); min-width:140px;">Selected: (0)</span>
              <input type="text" id="vip-batch-input" placeholder="Paste private server link or VIP code for selected accounts..." style="flex:1; height:34px; background:var(--bg); border:1px solid var(--border); border-radius:6px; color:var(--fg); padding:0 12px; font-size:12px; outline:none;" />
              <button class="btn btn-primary" id="btn-vip-apply" style="height:34px; font-size:12px; padding:0 14px;">Apply to Selected</button>
              <button class="btn btn-secondary" id="btn-vip-clear" style="height:34px; font-size:12px; padding:0 14px;">Clear Selected</button>
              <button class="btn btn-secondary" id="btn-vip-set-game" style="height:34px; font-size:12px; padding:0 12px;" title="Set Target Game for selected accounts">Set Game</button>
              <button class="btn btn-primary" id="btn-vip-launch" style="height:34px; font-size:12px; padding:0 14px;">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width:12px;height:12px;margin-right:4px;"><polygon points="6 3 20 12 6 21 6 3"/></svg>
                Launch VIP
              </button>
            </div>
          </div>
        </div>

        <!-- console view -->
        <div class="view" id="console-view">
          <div class="console-view-headerbar">
            <div class="console-view-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;color:var(--accent);"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
              <h2>Application Console</h2>
            </div>
            <div class="console-filter-tabs" id="console-filter-tabs">
              <button class="console-filter-btn active" data-filter="all">ALL</button>
              <button class="console-filter-btn" data-filter="info">INFO</button>
              <button class="console-filter-btn" data-filter="success">SUCCESS</button>
              <button class="console-filter-btn" data-filter="warning">WARN</button>
              <button class="console-filter-btn" data-filter="error">ERROR</button>
              <button class="console-filter-btn" data-filter="api">API</button>
              <button class="console-filter-btn" data-filter="backend">BACKEND</button>
            </div>
            <div class="search-wrap console-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              <input type="search" id="console-search-input" placeholder="Filter console logs..." autocomplete="off">
            </div>
            <div class="console-header-actions">
              <button class="btn btn-secondary btn-sm" id="btn-console-copy" title="Copy all logs to clipboard">Copy Logs</button>
              <button class="btn btn-secondary btn-sm" id="btn-console-export" title="Export logs as file">Export .txt</button>
              <button class="btn btn-danger btn-sm" id="btn-console-clear" title="Clear all logs">Clear</button>
            </div>
          </div>
          <div class="console-view-body" id="console-view-body"></div>
          <div class="console-view-footer">
            <span id="console-log-count">0 entries</span>
            <label class="console-autoscroll-toggle">
              <input type="checkbox" id="console-autoscroll-check" checked> Auto-Scroll
            </label>
          </div>
        </div>

        <!-- webhooks view -->
        <div class="view" id="webhooks-view">
          <div class="webhooks-headerbar" style="padding:16px 20px; border-bottom:1px solid var(--border-soft); display:flex; justify-content:space-between; align-items:center; background:var(--card);">
            <div class="webhooks-title-wrap">
              <h2 style="font-size:18px; font-weight:700; color:var(--text-bright); margin:0;">Discord Webhook Manager</h2>
              <span style="font-size:12px; color:var(--text-muted);">Real-time notifications, instance logs, monitor screenshots, and automated status reports</span>
            </div>
            <div class="webhooks-header-actions" style="display:flex; gap:10px; align-items:center;">
              <button class="btn btn-secondary btn-sm" id="btn-webhook-test">Test Embed</button>
              <button class="btn btn-secondary btn-sm" id="btn-webhook-test-screenshot">Test Screenshot</button>
              <button class="btn btn-primary btn-sm" id="btn-webhook-save">Save Settings</button>
            </div>
          </div>

          <div class="webhooks-content" style="padding:20px; overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:20px;">
            <div class="webhooks-grid" style="display:grid; grid-template-columns: repeat(2, 1fr); gap:20px;">
              
              <!-- Webhook Connection Card -->
              <div class="card" style="padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px;">
                <div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--border-soft); padding-bottom:12px;">
                  <h3 style="font-size:15px; font-weight:600; margin:0; color:var(--text-bright);">Webhook Connection</h3>
                  <label class="toggle-switch" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                    <input type="checkbox" id="webhook-enable-toggle">
                    <span style="font-size:13px; font-weight:600; color:var(--muted);" id="webhook-status-label">Disabled</span>
                  </label>
                </div>

                <div class="form-group" style="display:flex; flex-direction:column; gap:6px;">
                  <label style="font-size:12px; font-weight:600; color:var(--muted);">Discord Webhook URL</label>
                  <div style="display:flex; gap:8px;">
                    <input type="password" id="webhook-url-input" class="form-control" placeholder="https://discord.com/api/webhooks/..." style="flex:1; background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;">
                    <button class="btn btn-secondary" id="btn-toggle-webhook-visibility" title="Show/Hide URL" style="padding:8px 12px;">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    </button>
                  </div>
                </div>

                <div class="form-group" style="display:flex; flex-direction:column; gap:6px;">
                  <label style="font-size:12px; font-weight:600; color:var(--muted);">Ping User ID (Optional)</label>
                  <input type="text" id="webhook-ping-user-input" class="form-control" placeholder="e.g. 123456789012345678" style="background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px; width:100%;">
                  <span style="font-size:11px; color:var(--muted);">Mention specific Discord user ID when alerts trigger</span>
                </div>
              </div>

              <!-- Event Notification Triggers Card -->
              <div class="card" style="padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px;">
                <div style="border-bottom:1px solid var(--border-soft); padding-bottom:12px;">
                  <h3 style="font-size:15px; font-weight:600; margin:0; color:var(--text-bright);">Event Notification Triggers</h3>
                </div>

                <div style="display:flex; flex-direction:column; gap:12px;">
                  <label style="display:flex; align-items:center; justify-content:space-between; cursor:pointer;">
                    <div>
                      <b style="font-size:13px; display:block; color:var(--text-bright);">Account Launch Alerts</b>
                      <span style="font-size:11px; color:var(--muted);">Send notifications when accounts launch Roblox instances</span>
                    </div>
                    <input type="checkbox" id="webhook-trigger-launches" checked>
                  </label>

                  <label style="display:flex; align-items:center; justify-content:space-between; cursor:pointer;">
                    <div>
                      <b style="font-size:13px; display:block; color:var(--text-bright);">Auto-Rejoin Event Alerts</b>
                      <span style="font-size:11px; color:var(--muted);">Notify when auto-rejoin monitor triggers reconnects</span>
                    </div>
                    <input type="checkbox" id="webhook-trigger-rejoins" checked>
                  </label>

                  <label style="display:flex; align-items:center; justify-content:space-between; cursor:pointer;">
                    <div>
                      <b style="font-size:13px; display:block; color:var(--text-bright);">Console Error Logs</b>
                      <span style="font-size:11px; color:var(--muted);">Mirror critical application errors to Discord</span>
                    </div>
                    <input type="checkbox" id="webhook-trigger-logs" checked>
                  </label>

                  <label style="display:flex; align-items:center; justify-content:space-between; cursor:pointer;">
                    <div>
                      <b style="font-size:13px; display:block; color:var(--text-bright);">Redact Sensitive Data</b>
                      <span style="font-size:11px; color:var(--muted);">Automatically strip cookies & tokens from webhooks</span>
                    </div>
                    <input type="checkbox" id="webhook-redact-sensitive" checked>
                  </label>
                </div>
              </div>

              <!-- Monitor Screenshots Card -->
              <div class="card" style="padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px;">
                <div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--border-soft); padding-bottom:12px;">
                  <h3 style="font-size:15px; font-weight:600; margin:0; color:var(--text-bright);">Monitor Screenshots</h3>
                  <label class="toggle-switch" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                    <input type="checkbox" id="webhook-screenshot-enable-toggle">
                    <span style="font-size:13px; font-weight:600; color:var(--muted);" id="webhook-screenshot-status-label">Disabled</span>
                  </label>
                </div>

                <div style="display:flex; flex-direction:column; gap:12px;">
                  <div class="form-group" style="display:flex; flex-direction:column; gap:6px;">
                    <label style="font-size:12px; font-weight:600; color:var(--muted);">Automated Screenshot Interval</label>
                    <div style="display:flex; align-items:center; gap:8px;">
                      <input type="number" id="webhook-screenshot-interval" class="form-control" min="1" max="1440" placeholder="15" style="width:100px; background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;">
                      <span style="font-size:12px; color:var(--muted);">minutes (default: 15)</span>
                    </div>
                  </div>

                  <label style="display:flex; align-items:center; justify-content:space-between; cursor:pointer;">
                    <div>
                      <b style="font-size:13px; display:block; color:var(--text-bright);">Capture All Monitors</b>
                      <span style="font-size:11px; color:var(--muted);">Capture multi-monitor setup instead of primary display</span>
                    </div>
                    <input type="checkbox" id="webhook-screenshot-all-monitors">
                  </label>

                  <div style="padding-top:4px;">
                    <button class="btn btn-secondary btn-sm" id="btn-send-instant-screenshot">Capture & Send Screenshot Now</button>
                  </div>
                </div>
              </div>

              <!-- Roblox Instance Summary Reports Card -->
              <div class="card" style="padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px;">
                <div style="display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--border-soft); padding-bottom:12px;">
                  <h3 style="font-size:15px; font-weight:600; margin:0; color:var(--text-bright);">Roblox Instance Reports</h3>
                  <label class="toggle-switch" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                    <input type="checkbox" id="webhook-instance-summary-toggle">
                    <span style="font-size:13px; font-weight:600; color:var(--muted);" id="webhook-instance-status-label">Disabled</span>
                  </label>
                </div>

                <div style="display:flex; flex-direction:column; gap:12px;">
                  <div class="form-group" style="display:flex; flex-direction:column; gap:6px;">
                    <label style="font-size:12px; font-weight:600; color:var(--muted);">Report Interval</label>
                    <div style="display:flex; align-items:center; gap:8px;">
                      <input type="number" id="webhook-instance-summary-interval" class="form-control" min="1" max="1440" placeholder="15" style="width:100px; background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;">
                      <span style="font-size:12px; color:var(--muted);">minutes (default: 15)</span>
                    </div>
                  </div>

                  <div style="padding-top:4px;">
                    <button class="btn btn-secondary btn-sm" id="btn-send-instant-instances">Send Instance Status Report Now</button>
                  </div>
                </div>
              </div>

            </div>

            <!-- Recent Webhook Event History Card -->
            <div class="card" style="padding:20px; display:flex; flex-direction:column; gap:12px; background:var(--card); border:1px solid var(--border); border-radius:8px;">
              <h3 style="font-size:15px; font-weight:600; margin:0; color:var(--text-bright);">Recent Webhook Event Activity</h3>
              <div id="webhook-history-container" style="max-height:220px; overflow-y:auto; font-family:monospace; font-size:12px; background:var(--bg-2); border-radius:6px; padding:10px 14px; border:1px solid var(--border);">
                <span style="color:var(--muted);">No webhook events recorded yet.</span>
              </div>
            </div>

          </div>
        </div>

        <!-- extensions view -->
        <div class="view" id="extensions-view">
          <div class="extensions-headerbar" style="padding:16px 20px; border-bottom:1px solid var(--border-soft); display:flex; justify-content:space-between; align-items:center; background:var(--card);">
            <div class="extensions-title-wrap">
              <h2 style="font-size:18px; font-weight:700; color:var(--text-bright); margin:0;">Extension Manager</h2>
              <span style="font-size:12px; color:var(--text-muted);">Manage browser extensions for supported browsers</span>
            </div>
            <div class="extensions-header-actions" style="display:flex; gap:10px; align-items:center;">
              <button class="btn btn-secondary btn-sm" id="btn-extensions-refresh">Refresh</button>
              <button class="btn btn-primary btn-sm" id="btn-extensions-install">+ Install Extension</button>
            </div>
          </div>

          <div class="extensions-content" style="padding:20px; overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:20px;">
            <div id="extensions-grid" style="display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:16px;">
              <div style="color:var(--muted); font-size:13px;">Loading extensions...</div>
            </div>
          </div>
        </div>

        <!-- bloxgen view -->
        <div class="view" id="bloxgen-view">
          <div class="bloxgen-headerbar" style="padding:14px 20px; border-bottom:1px solid var(--border-soft); display:flex; justify-content:space-between; align-items:center; background:var(--card); flex-wrap:wrap; gap:12px;">
            <div class="bloxgen-title-wrap" style="display:flex; flex-direction:column; gap:2px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <h2 style="font-size:18px; font-weight:700; color:var(--text-bright); margin:0;">BloxGen Account Manager</h2>
                <span class="bloxgen-badge">API</span>
              </div>
              <span style="font-size:12px; color:var(--text-muted);">Account generation, cookie validation, stock health, and social growth</span>
            </div>
            <div class="bloxgen-header-actions" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
              <div style="display:flex; align-items:center; gap:6px; background:var(--bg-2); border:1px solid var(--border); padding:4px 8px; border-radius:6px;">
                <span style="font-size:11px; font-weight:600; color:var(--muted);">API Key:</span>
                <input type="password" id="bloxgen-key-input-header" class="form-control" placeholder="BLOX-XXXXXXXXXXXXXXXX" style="width:200px; background:transparent; border:none; color:var(--fg); font-size:12px; font-family:monospace; padding:2px 4px;" />
                <button class="btn btn-secondary btn-sm" id="btn-bloxgen-toggle-key-header" style="padding:2px 8px; font-size:11px;" title="Toggle Show/Hide Key">Show</button>
                <button class="btn btn-primary btn-sm" id="btn-bloxgen-save-key-header" style="padding:2px 10px; font-size:11px;">Save</button>
              </div>
              <button class="btn btn-secondary btn-sm" id="btn-bloxgen-refresh" title="Refresh BloxGen Data">Refresh Data</button>
            </div>
          </div>

          <div class="bloxgen-content" style="padding:20px; overflow-y:auto; flex:1; display:flex; flex-direction:column; gap:20px;">
            <div style="display:flex; gap:10px; border-bottom:1px solid var(--border-soft); padding-bottom:12px;">
              <button class="btn btn-primary btn-sm" id="tab-bloxgen-overview">Dashboard & Stock</button>
              <button class="btn btn-secondary btn-sm" id="tab-bloxgen-generator">Account Generator</button>
              <button class="btn btn-secondary btn-sm" id="tab-bloxgen-checker">Cookie Checker</button>
              <button class="btn btn-secondary btn-sm" id="tab-bloxgen-botting">Social Growth</button>
            </div>

            <div id="bloxgen-tab-container" style="display:flex; flex-direction:column; gap:20px;"></div>
          </div>
        </div>

        <!-- FastFlags Editor View -->
        <div class="view" id="fastflags-view">
          <div class="settings-nav">
            <div class="settings-nav-header">
              <span class="settings-nav-title">FastFlags</span>
              <button class="settings-nav-back-btn" id="btn-fastflags-back" title="Back" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                <span>Back</span>
              </button>
            </div>
            <div class="settings-tabs" id="fastflags-tabs"></div>
          </div>
          <div class="settings-content">
            <div class="settings-content-inner" id="fastflags-content-inner"></div>
          </div>
        </div>

        <!-- Roblox Client Settings View -->
        <div class="view" id="clientsettings-view">
          <div class="settings-nav">
            <div class="settings-nav-header">
              <span class="settings-nav-title">Client Settings</span>
              <button class="settings-nav-back-btn" id="btn-clientsettings-back" title="Back" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                <span>Back</span>
              </button>
            </div>
            <div class="settings-search-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              <input type="search" id="clientsettings-search-input" placeholder="Search settings..." autocomplete="off">
            </div>
            <div class="settings-tabs" id="clientsettings-tabs"></div>
          </div>
          <div class="settings-content">
            <div class="settings-content-inner" id="clientsettings-content-inner"></div>
          </div>
        </div>

        <!-- About View -->
        <div class="view" id="about-view">
          <div class="about-headerbar">
            <div class="about-title-wrap">
              <div style="display:flex; align-items:center; gap:8px;">
                <h2 style="font-size:17px; font-weight:700; color:var(--text-bright); margin:0;">About Forked Roblox Account Manager</h2>
                <span class="badge" style="font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px; background:var(--primary-dim); color:var(--primary); border:1px solid var(--primary);">v3.0.0</span>
              </div>
              <span style="font-size:12px; color:var(--text-muted);">Account Manager, Instance Manager, VIP Server Manager · Developed by <b style="color:var(--fg);">hackyue</b></span>
            </div>
            <div class="about-header-actions" style="display:flex; gap:8px; align-items:center;">
              <button class="btn btn-secondary btn-sm" id="btn-about-tab-overview">Overview</button>
              <button class="btn btn-secondary btn-sm" id="btn-about-tab-whatsnew">What's New</button>
              <button class="btn btn-secondary btn-sm" id="btn-about-back" title="Back to Accounts" style="margin-left:6px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:12px; height:12px; margin-right:4px;"><polyline points="15 18 9 12 15 6"/></svg>
                Back
              </button>
            </div>
          </div>
          <div class="about-view-body" id="about-content-body"></div>
        </div>
      </div>
      </div>
    </div>
  </div>

  <!-- Install extension modal -->
  <div class="overlay" id="install-extension-overlay">
    <div class="modal" style="width:480px; max-width:90vw;">
      <h3>Install Browser Extension</h3>
      <p class="hint">Install an extension from Chrome Web Store, Firefox Add-ons, or a local package/folder.</p>
      
      <div class="field" style="margin-bottom:12px;">
        <label>Extension Source</label>
        <select id="ext-install-source" class="form-control" style="width:100%; background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;">
          <option value="web_store">Chrome Web Store (Extension ID or URL)</option>
          <option value="firefox">Firefox Add-ons (Slug, GUID, or URL)</option>
          <option value="unpacked">Unpacked Folder (Folder Path)</option>
          <option value="crx">Chrome Extension Package (*.crx)</option>
          <option value="xpi">Firefox Add-on Package (*.xpi)</option>
        </select>
      </div>

      <div class="field" id="ext-install-input-wrap">
        <label id="ext-install-label">Extension ID or Store URL</label>
        <div style="display:flex; gap:8px;">
          <input type="text" id="ext-install-target" placeholder="e.g. cjpalhdlnbpafiamejdnhcphjbkeiagm" autocomplete="off" style="flex:1;">
          <button class="btn btn-secondary" id="ext-install-browse-btn" style="display:none; white-space:nowrap; padding:0 12px; height:36px; line-height:36px;">Browse...</button>
        </div>
        <p id="ext-install-hint" class="hint" style="margin-top:4px; font-size:11px;">Paste a 32-character Chrome Web Store ID or store URL</p>
      </div>

      <div class="modal-actions" style="margin-top:20px;">
        <button class="btn btn-secondary" id="ext-install-cancel">Cancel</button>
        <button class="btn btn-primary" id="ext-install-confirm">Install Extension</button>
      </div>
    </div>
  </div>

  <!-- Add account modal -->
  <div class="overlay" id="add-overlay">
    <div class="modal">
      <h3>Add account</h3>
      <p class="hint">Add an account to the list.</p>
      <div class="field"><label>Display name</label><input type="text" id="new-username" placeholder="e.g. NewPlayer42" autocomplete="off"></div>
      <div class="field"><label>Group</label><input type="text" id="new-group" placeholder="e.g. My Friends Group" autocomplete="off"></div>
      <div class="field"><label>Note</label><textarea id="new-note" rows="2" placeholder="Optional note"></textarea></div>
      <div class="modal-actions">
        <button class="btn btn-secondary" id="add-cancel">Cancel</button>
        <button class="btn btn-primary" id="add-confirm">Add account</button>
      </div>
    </div>
  </div>

  <!-- Row menu popover -->
  <div class="popover" id="row-popover">
    <button data-action="launch"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>Launch Roblox</button>
    <button data-action="browser"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>Open in browser</button>
    <button data-action="view"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>View details</button>
    <button data-action="validate"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>Validate Account</button>
    <button data-action="set-group"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>Set Group</button>
    <button data-action="copy"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>Copy username</button>
    <button data-action="cookie"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Copy cookie</button>
    <hr>
    <button data-action="delete" style="color:var(--red);"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>Delete</button>
  </div>

  <div id="toast-wrap"></div>
  `;

  // Event listeners
  document.addEventListener('click', (e) => {
    const pop = document.getElementById('row-popover');
    if (pop && !pop.contains(e.target as Node)) {
      pop.classList.remove('show');
    }
  });

  const rowPopover = document.getElementById('row-popover');
  if (rowPopover) {
    rowPopover.addEventListener('click', (e) => {
      const btn = (e.target as HTMLElement).closest('button');
      if (!btn) return;
      const action = btn.getAttribute('data-action');
      const selectedAccounts = getSelectedAccounts();
      const a = currentMenuAccountId ? getAccount(currentMenuAccountId) : (selectedAccounts[0] || null);

      if (action === 'launch' && a) { handleLaunchAccount(a.id); }
      if (action === 'browser' && a) { handleLaunchBrowser(a.id); }
      if (action === 'launch-multi') { handleLaunchSelectedAccounts(); }
      if (action === 'browser-multi') { handleLaunchSelectedBrowsers(); }
      if (action === 'view' && a) { state.selectedId = a.id; state.selectedIds = new Set([a.id]); renderAll(); }
      if (action === 'validate' && a) { handleValidateAccount(a); }
      if (action === 'validate-multi') { handleValidateSelectedAccounts(); }
      if (action === 'set-group' && a) { showSetGroupModal([a]); }
      if (action === 'set-group-multi') {
        const accounts = selectedAccounts.length > 0 ? selectedAccounts : (a ? [a] : []);
        if (accounts.length > 0) {
          showSetGroupModal(accounts);
        }
      }
      if (action === 'copy' && a) { copyToClipboard(a.username || ''); toast('Username copied'); }
      if (action === 'copy-password' && a) { copyToClipboard(a.password || ''); toast('Password copied'); }
      if (action === 'cookie' && a) { copyToClipboard(a.cookie || ''); toast('Cookie copied'); }
      if (action === 'copy-userpass') {
        const accounts = selectedAccounts.length > 1 ? selectedAccounts : (a ? [a] : []);
        const text = accounts.map(acc => `${acc.username || ''}:${acc.password || ''}`).join('\n');
        copyToClipboard(text);
        toast(`Copied ${accounts.length > 1 ? accounts.length + ' ' : ''}user:pass combo`);
      }
      if (action === 'copy-userpasscookie') {
        const accounts = selectedAccounts.length > 1 ? selectedAccounts : (a ? [a] : []);
        const text = accounts.map(acc => `${acc.username || ''}:${acc.password || ''}:${acc.cookie || ''}`).join('\n');
        copyToClipboard(text);
        toast(`Copied ${accounts.length > 1 ? accounts.length + ' ' : ''}user:pass:cookie combo`);
      }
      if (action === 'copy-usernames') {
        const text = selectedAccounts.map(acc => acc.username || '').join('\n');
        copyToClipboard(text);
        toast(`Copied ${selectedAccounts.length} usernames`);
      }
      if (action === 'copy-passwords') {
        const text = selectedAccounts.map(acc => acc.password || '').join('\n');
        copyToClipboard(text);
        toast(`Copied ${selectedAccounts.length} passwords`);
      }
      if (action === 'copy-cookies') {
        const text = selectedAccounts.map(acc => acc.cookie || '').join('\n');
        copyToClipboard(text);
        toast(`Copied ${selectedAccounts.length} cookies`);
      }
      if (action === 'toggle-auto-rejoin' && a) {
        const newState = !a.auto_rejoin_enabled;
        a.auto_rejoin_enabled = newState;
        apiService.updateAccount(a.id, { auto_rejoin_enabled: newState }).then(() => {
          toast(`${newState ? 'Enabled' : 'Disabled'} Auto-Rejoin for @${a.username}`, 'info');
          renderAll();
        });
      }
      if (action === 'toggle-anti-afk' && a) {
        const newState = !a.anti_afk_enabled;
        a.anti_afk_enabled = newState;
        apiService.updateAccount(a.id, { anti_afk_enabled: newState }).then(() => {
          toast(`${newState ? 'Enabled' : 'Disabled'} Anti-AFK for @${a.username}`, 'info');
          renderAll();
        });
      }
      if (action === 'enable-auto-rejoin-multi') {
        const accounts = selectedAccounts.length > 0 ? selectedAccounts : (a ? [a] : []);
        accounts.forEach(acc => {
          acc.auto_rejoin_enabled = true;
          apiService.updateAccount(acc.id, { auto_rejoin_enabled: true }).catch(() => { });
        });
        toast(`Enabled Auto-Rejoin for ${accounts.length} account(s)`, 'info');
        renderAll();
      }
      if (action === 'disable-auto-rejoin-multi') {
        const accounts = selectedAccounts.length > 0 ? selectedAccounts : (a ? [a] : []);
        accounts.forEach(acc => {
          acc.auto_rejoin_enabled = false;
          apiService.updateAccount(acc.id, { auto_rejoin_enabled: false }).catch(() => { });
        });
        toast(`Disabled Auto-Rejoin for ${accounts.length} account(s)`, 'info');
        renderAll();
      }
      if (action === 'enable-anti-afk-multi') {
        const accounts = selectedAccounts.length > 0 ? selectedAccounts : (a ? [a] : []);
        accounts.forEach(acc => {
          acc.anti_afk_enabled = true;
          apiService.updateAccount(acc.id, { anti_afk_enabled: true }).catch(() => { });
        });
        toast(`Enabled Anti-AFK for ${accounts.length} account(s)`, 'info');
        renderAll();
      }
      if (action === 'disable-anti-afk-multi') {
        const accounts = selectedAccounts.length > 0 ? selectedAccounts : (a ? [a] : []);
        accounts.forEach(acc => {
          acc.anti_afk_enabled = false;
          apiService.updateAccount(acc.id, { anti_afk_enabled: false }).catch(() => { });
        });
        toast(`Disabled Anti-AFK for ${accounts.length} account(s)`, 'info');
        renderAll();
      }
      if (action === 'delete' && a) { deleteAccount(a.id); }
      if (action === 'delete-multi') { bulkDeleteSelected(); }
      rowPopover.classList.remove('show');
    });
  }

  let searchDebounceTimer: any = null;
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.search = (e.target as HTMLInputElement).value;
      if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
      searchDebounceTimer = setTimeout(() => {
        renderTable();
      }, 50);
    });
  }

  const groupFilter = document.getElementById('group-filter');
  if (groupFilter) {
    groupFilter.addEventListener('change', (e) => {
      state.groupFilter = (e.target as HTMLSelectElement).value;
      renderTable();
    });
  }

  const btnAccounts = document.getElementById('btn-accounts');
  if (btnAccounts) {
    btnAccounts.addEventListener('click', () => {
      state.revealed = {};
      state.view = 'accounts';
      renderAll();
    });
  }

  const btnAddAccount = document.getElementById('btn-add-account');
  if (btnAddAccount) {
    btnAddAccount.addEventListener('click', () => {
      showAddAccountOptions(btnAddAccount);
    });
  }

  const addCancel = document.getElementById('add-cancel');
  if (addCancel) {
    addCancel.addEventListener('click', () => {
      const addOverlay = document.getElementById('add-overlay');
      if (addOverlay) addOverlay.classList.remove('show');
    });
  }

  const addOverlay = document.getElementById('add-overlay');
  if (addOverlay) {
    addOverlay.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).id === 'add-overlay') {
        addOverlay.classList.remove('show');
      }
    });
  }

  const addConfirm = document.getElementById('add-confirm');
  if (addConfirm) {
    addConfirm.addEventListener('click', async () => {
      const newUsername = document.getElementById('new-username') as HTMLInputElement;
      const newGroup = document.getElementById('new-group') as HTMLInputElement;
      const newNote = document.getElementById('new-note') as HTMLTextAreaElement;

      const name = newUsername?.value.trim();
      if (!name) { toast('Enter a display name first', 'error'); return; }

      const newAcc: Partial<Account> = {
        username: name,
        status: 'valid',
        group: newGroup?.value.trim() || '',
        note: newNote?.value.trim() || '',
        password: '',
        cookie: ''
      };

      try {
        const createdAccount = await apiService.createAccount(newAcc);
        const overlay = document.getElementById('add-overlay');
        if (overlay) overlay.classList.remove('show');
        if (newUsername) newUsername.value = '';
        if (newGroup) newGroup.value = '';
        if (newNote) newNote.value = '';
        toast('Account added');
        await refreshAccountList(createdAccount?.id);
      } catch (error) {
        addLog('Failed to create account: ' + error, 'error');
        toast('Failed to create account', 'error');
      }
    });
  }

  const pillStreamer = document.getElementById('pill-streamer-mode');
  if (pillStreamer) {
    pillStreamer.addEventListener('click', () => {
      const newMode = !state.settings.streamerMode;
      updateSetting('streamerMode', newMode);
      toast(`Streamer Mode ${newMode ? 'ENABLED' : 'DISABLED'}`, 'info');
    });
  }

  const handleTrimMemoryAction = async (btn?: HTMLElement | null) => {
    if (btn) {
      btn.style.pointerEvents = 'none';
      btn.style.opacity = '0.6';
    }
    try {
      toast('Trimming Roblox memory...', 'info');
      const res = await apiService.trimRobloxMemory();
      if (res.success) {
        const count = res.trimmedCount ?? res.trimmed ?? 0;
        const saved = res.savedMb ?? 0;
        if (count > 0) {
          toast(`Trimmed ${count} instance(s), reclaimed ${saved} MB RAM`, 'success');
          addLog(`Trimmed Roblox memory: ${saved} MB reclaimed across ${count} instance(s)`, 'info');
        } else {
          toast('No active Roblox instances to trim', 'info');
        }
        if (state.view === 'instances') {
          renderInstancesView();
        }
      } else {
        toast(res.error || 'Failed to trim memory', 'error');
      }
    } catch (err: any) {
      toast(`RAM trim error: ${err.message || err}`, 'error');
    } finally {
      if (btn) {
        btn.style.pointerEvents = '';
        btn.style.opacity = '';
      }
    }
  };

  const pillTrimRam = document.getElementById('pill-trim-ram');
  if (pillTrimRam) {
    pillTrimRam.addEventListener('click', () => handleTrimMemoryAction(pillTrimRam));
  }

  const btnTrimMemoryHeader = document.getElementById('btn-trim-memory-header');
  if (btnTrimMemoryHeader) {
    btnTrimMemoryHeader.addEventListener('click', () => handleTrimMemoryAction(btnTrimMemoryHeader));
  }

  const btnAutoArrangeHeader = document.getElementById('btn-auto-arrange-header');
  if (btnAutoArrangeHeader) {
    btnAutoArrangeHeader.addEventListener('click', async () => {
      try {
        toast('Arranging Roblox client windows...', 'info');
        const res = await apiService.autoArrangeClients();
        if (res.success) {
          toast(res.message || `Auto-arranged ${res.count} client(s)!`, 'success');
        } else {
          toast(res.message || res.error || 'No active Roblox clients detected', 'info');
        }
      } catch (err: any) {
        toast(err.message || 'Failed to auto-arrange clients', 'error');
      }
    });
  }

  const btnKillRoblox = document.getElementById('btn-kill-roblox');
  if (btnKillRoblox) {
    btnKillRoblox.addEventListener('click', async () => {
      try {
        toast('Force quitting Roblox clients...', 'info');
        const res = await apiService.killRobloxProcess();
        if (res.success) {
          toast('Force quit all Roblox client processes', 'success');
          addLog('Force terminated Roblox client processes', 'info');
        } else {
          toast(res.error || 'Failed to force quit Roblox', 'error');
        }
      } catch (err) {
        addLog('Error force quitting Roblox: ' + err, 'error');
        toast('Failed to force quit Roblox', 'error');
      }
    });
  }

  const btnRefresh = document.getElementById('btn-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', async function () {
      const btn = this as HTMLButtonElement;
      btn.style.transition = 'transform .5s ease';
      btn.style.transform = 'rotate(360deg)';
      setTimeout(() => { btn.style.transform = ''; }, 500);

      try {
        toast('Refreshing account statuses...', 'info');
        const res = await apiService.validateAllAccounts();
        state.accounts = res.accounts;
        toast(`Refreshed: ${res.summary.valid} valid, ${res.summary.expired} expired, ${res.summary.banned} banned`, 'success');
        renderAll();
      } catch (error) {
        addLog('Refresh status check failed, reloading accounts: ' + error, 'warning');
        await loadFromBackend();
        toast('Account list refreshed');
      }
    });
  }

  const btnVip = document.getElementById('btn-vip');
  if (btnVip) {
    btnVip.addEventListener('click', () => {
      state.revealed = {};
      state.view = state.view === 'vip' ? 'accounts' : 'vip';
      renderAll();
    });
  }

  const vipSelectAll = document.getElementById('vip-select-all') as HTMLInputElement | null;
  if (vipSelectAll) {
    vipSelectAll.addEventListener('change', () => {
      const isChecked = vipSelectAll.checked;
      const visibleList = getFilteredVipAccounts();
      if (isChecked) {
        visibleList.forEach(a => vipSelectedIds.add(a.id));
      } else {
        visibleList.forEach(a => vipSelectedIds.delete(a.id));
      }
      renderVipView();
    });
  }

  let vipSearchDebounceTimer: any = null;
  const vipSearchInput = document.getElementById('vip-search-input');
  if (vipSearchInput) {
    vipSearchInput.addEventListener('input', () => {
      if (vipSearchDebounceTimer) clearTimeout(vipSearchDebounceTimer);
      vipSearchDebounceTimer = setTimeout(() => {
        renderVipView();
      }, 50);
    });
  }

  const vipGroupFilter = document.getElementById('vip-group-filter');
  if (vipGroupFilter) {
    vipGroupFilter.addEventListener('change', () => {
      renderVipView();
    });
  }

  const btnVipImportCsv = document.getElementById('btn-vip-import-csv');
  if (btnVipImportCsv) {
    btnVipImportCsv.addEventListener('click', () => {
      importVipCsv();
    });
  }

  const btnVipExportCsv = document.getElementById('btn-vip-export-csv');
  if (btnVipExportCsv) {
    btnVipExportCsv.addEventListener('click', () => {
      exportVipCsv();
    });
  }

  const btnVipSetGame = document.getElementById('btn-vip-set-game');
  if (btnVipSetGame) {
    btnVipSetGame.addEventListener('click', () => {
      showSetVipGameModal();
    });
  }

  const vipBatchInput = document.getElementById('vip-batch-input') as HTMLInputElement | null;
  if (vipBatchInput) {
    vipBatchInput.addEventListener('mouseenter', () => {
      if (document.body.classList.contains('streamer-reveal-hover')) {
        vipBatchInput.style.filter = 'none';
      }
    });
    vipBatchInput.addEventListener('mouseleave', () => {
      if (document.activeElement !== vipBatchInput) {
        vipBatchInput.style.filter = '';
      }
    });
    vipBatchInput.addEventListener('focus', () => {
      vipBatchInput.style.filter = 'none';
    });
    vipBatchInput.addEventListener('blur', () => {
      vipBatchInput.style.filter = '';
    });
  }

  const btnVipApply = document.getElementById('btn-vip-apply');
  if (btnVipApply) {
    btnVipApply.addEventListener('click', async () => {
      const rawVal = (document.getElementById('vip-batch-input') as HTMLInputElement)?.value.trim() || '';
      if (vipSelectedIds.size === 0) {
        toast('Select at least one account first', 'error');
        return;
      }
      let finalVal = rawVal;
      let extractedPlaceId: string | undefined;
      if (rawVal) {
        const normalized = await resolveAndNormalizePrivateServer(rawVal);
        finalVal = normalized.code || rawVal;
        extractedPlaceId = normalized.placeId || extractPrivateServerCode(rawVal).placeId;
        const batchInput = document.getElementById('vip-batch-input') as HTMLInputElement | null;
        if (batchInput && finalVal !== rawVal) {
          batchInput.value = finalVal;
        }
      }
      const mapping: Record<string, any> = {};
      state.accounts.forEach(a => {
        if (vipSelectedIds.has(a.id)) {
          a.vip_server = finalVal;
          if (extractedPlaceId) {
            a.vip_place_id = extractedPlaceId;
          }
          mapping[a.username] = {
            vip_server: finalVal,
            vip_place_id: a.vip_place_id || '',
            vip_game_name: a.vip_game_name || ''
          };
        }
      });
      try {
        await apiService.bulkUpdateVip(mapping);
        toast(`Updated VIP server for ${vipSelectedIds.size} account(s)!`, 'success');
        renderVipView();
      } catch (err) {
        toast('Failed to apply VIP server link: ' + err, 'error');
      }
    });
  }

  const btnVipClear = document.getElementById('btn-vip-clear');
  if (btnVipClear) {
    btnVipClear.addEventListener('click', async () => {
      if (vipSelectedIds.size === 0) {
        toast('Select at least one account first', 'error');
        return;
      }
      const mapping: Record<string, any> = {};
      state.accounts.forEach(a => {
        if (vipSelectedIds.has(a.id)) {
          mapping[a.username] = {
            vip_server: '',
            vip_place_id: '',
            vip_game_name: ''
          };
          a.vip_server = '';
          a.vip_place_id = '';
          a.vip_game_name = '';
        }
      });
      try {
        await apiService.bulkUpdateVip(mapping);
        toast(`Cleared VIP server for ${vipSelectedIds.size} account(s)`, 'info');
        renderVipView();
      } catch (err) {
        toast('Failed to clear VIP server link: ' + err, 'error');
      }
    });
  }

  const btnVipLaunch = document.getElementById('btn-vip-launch');
  if (btnVipLaunch) {
    btnVipLaunch.addEventListener('click', async () => {
      if (vipSelectedIds.size === 0) {
        toast('Select at least one account first', 'error');
        return;
      }
      const accountsToLaunch = state.accounts.filter(a => vipSelectedIds.has(a.id));
      const withVip = accountsToLaunch.filter(a => Boolean(a.vip_server));
      if (withVip.length === 0) {
        toast('None of the selected accounts have VIP server links set', 'error');
        return;
      }

      if (state.settings.confirmBeforeLaunch) {
        const confirmed = await showConfirmModal('Confirm VIP Server Launch', `Are you sure you want to launch VIP server for ${withVip.length} selected account(s)?`, 'Launch VIP');
        if (!confirmed) return;
      }

      toast(`Launching VIP server for ${withVip.length} account(s)...`, 'info');
      for (let i = 0; i < withVip.length; i++) {
        const a = withVip[i];
        try {
          const normalized = await resolveAndNormalizePrivateServer(a.vip_server || '', a.cookie);
          const serverCodeToUse = normalized.code || a.vip_server || '';
          const placeIdFromUrl = a.vip_place_id || normalized.placeId || extractPrivateServerCode(a.vip_server || '').placeId;
          const fallbackPlaceId = (document.getElementById('place-input') as HTMLInputElement)?.value.trim() || undefined;
          const placeIdToUse = placeIdFromUrl || fallbackPlaceId;

          const res = await apiService.launchAccount({
            username: a.username,
            placeId: placeIdToUse,
            serverId: serverCodeToUse,
            serverMode: 'vip'
          });
          if (res.success) {
            toast(`Launched @${a.username}`, 'success');
          } else {
            toast(`Failed to launch @${a.username}: ${res.error || "Roblox isn't installed"}`, 'error');
          }
        } catch (err) {
          toast(`Failed to launch @${a.username}: ${err}`, 'error');
        }
        if (i < withVip.length - 1) {
          await new Promise(r => setTimeout(r, state.settings.multiLaunchDelay || 1000));
        }
      }
    });
  }

  const btnSettings = document.getElementById('btn-settings');
  if (btnSettings) {
    btnSettings.addEventListener('click', () => {
      state.revealed = {};
      state.view = state.view === 'settings' ? 'accounts' : 'settings';
      renderAll();
    });
  }

  const btnSettingsBack = document.getElementById('btn-settings-back');
  if (btnSettingsBack) {
    btnSettingsBack.addEventListener('click', () => {
      state.revealed = {};
      state.view = 'accounts';
      renderAll();
    });
  }

  const btnConsole = document.getElementById('btn-console');
  if (btnConsole) {
    btnConsole.addEventListener('click', () => {
      state.revealed = {};
      state.view = state.view === 'console' ? 'accounts' : 'console';
      renderAll();
    });
  }

  const btnFastflags = document.getElementById('btn-fastflags');
  if (btnFastflags) {
    btnFastflags.addEventListener('click', () => {
      state.revealed = {};
      state.previousView = state.view;
      state.view = state.view === 'fastflags' ? 'accounts' : 'fastflags';
      renderAll();
    });
  }

  const btnClientSettings = document.getElementById('btn-client-settings');
  if (btnClientSettings) {
    btnClientSettings.addEventListener('click', () => {
      state.revealed = {};
      state.previousView = state.view;
      state.view = state.view === 'clientsettings' ? 'accounts' : 'clientsettings';
      renderAll();
    });
  }

  const btnAbout = document.getElementById('btn-about');
  if (btnAbout) {
    btnAbout.addEventListener('click', () => {
      state.revealed = {};
      state.previousView = state.view;
      state.view = state.view === 'about' ? 'accounts' : 'about';
      renderAll();
    });
  }

  const btnWebhooks = document.getElementById('btn-webhooks');
  if (btnWebhooks) {
    btnWebhooks.addEventListener('click', () => {
      state.revealed = {};
      state.view = state.view === 'webhooks' ? 'accounts' : 'webhooks';
      renderAll();
    });
  }

  const btnExtensions = document.getElementById('btn-extensions');
  if (btnExtensions) {
    btnExtensions.addEventListener('click', () => {
      if (state.settings.preferredBrowser === 'chrome') {
        toast('Extension manager is disabled when Chrome is selected as default browser', 'error');
        return;
      }
      state.revealed = {};
      state.view = state.view === 'extensions' ? 'accounts' : 'extensions';
      renderAll();
    });
  }

  const btnBloxgen = document.getElementById('btn-bloxgen');
  if (btnBloxgen) {
    btnBloxgen.addEventListener('click', () => {
      state.revealed = {};
      state.view = state.view === 'bloxgen' ? 'accounts' : 'bloxgen';
      renderAll();
    });
  }

  const btnExtensionsInstall = document.getElementById('btn-extensions-install');
  if (btnExtensionsInstall) {
    btnExtensionsInstall.addEventListener('click', () => openInstallExtensionModal());
  }

  const btnExtensionsRefresh = document.getElementById('btn-extensions-refresh');
  if (btnExtensionsRefresh) {
    btnExtensionsRefresh.addEventListener('click', () => {
      toast('Refreshing extensions list...', 'info');
      renderExtensionsView();
    });
  }

  const extSourceSelect = document.getElementById('ext-install-source');
  if (extSourceSelect) {
    extSourceSelect.addEventListener('change', () => updateInstallModalSourceUI());
  }

  const extBrowseBtn = document.getElementById('ext-install-browse-btn');
  if (extBrowseBtn) {
    extBrowseBtn.addEventListener('click', async () => {
      const srcSelect = document.getElementById('ext-install-source') as HTMLSelectElement | null;
      const targetInput = document.getElementById('ext-install-target') as HTMLInputElement | null;
      if (!srcSelect || !targetInput) return;
      const src = srcSelect.value;
      if (src === 'unpacked') {
        const folder = await pickNativeFolder('Select Unpacked Extension Folder');
        if (folder) {
          targetInput.value = folder;
        } else {
          const res = await apiService.browseExtensionFolder();
          if (res && res.success && res.path) targetInput.value = res.path;
        }
      } else if (src === 'crx' || src === 'xpi') {
        const filters = src === 'crx'
          ? [{ name: 'Chrome Extension (*.crx)', extensions: ['crx'] }]
          : [{ name: 'Firefox Add-on (*.xpi)', extensions: ['xpi'] }];
        const file = await pickNativeFile('Select Extension Package', filters);
        if (file) {
          targetInput.value = file;
        } else {
          const res = await apiService.browseExtensionFile(src);
          if (res && res.success && res.path) targetInput.value = res.path;
        }
      }
    });
  }

  const extInstallCancel = document.getElementById('ext-install-cancel');
  if (extInstallCancel) {
    extInstallCancel.addEventListener('click', () => {
      document.getElementById('install-extension-overlay')?.classList.remove('show');
    });
  }

  const extInstallConfirm = document.getElementById('ext-install-confirm');
  if (extInstallConfirm) {
    extInstallConfirm.addEventListener('click', async () => {
      const srcSelect = document.getElementById('ext-install-source') as HTMLSelectElement | null;
      const targetInput = document.getElementById('ext-install-target') as HTMLInputElement | null;
      if (!srcSelect || !targetInput) return;
      const source = srcSelect.value;
      const val = targetInput.value.trim();
      if (!val) {
        toast('Please enter a target path, ID, or URL', 'error');
        return;
      }
      extInstallConfirm.setAttribute('disabled', 'true');
      extInstallConfirm.textContent = 'Installing...';
      try {
        const res = await apiService.addExtension(source, val);
        if (res.success && res.extension) {
          toast(`Successfully installed "${res.extension.name}"!`, 'success');
          document.getElementById('install-extension-overlay')?.classList.remove('show');
          targetInput.value = '';
          renderExtensionsView();
        } else {
          toast(res.error || 'Failed to install extension', 'error');
        }
      } catch (err: any) {
        toast(err.message || 'Failed to install extension', 'error');
      } finally {
        extInstallConfirm.removeAttribute('disabled');
        extInstallConfirm.textContent = 'Install Extension';
      }
    });
  }

  const btnWebhookSave = document.getElementById('btn-webhook-save');
  if (btnWebhookSave) {
    btnWebhookSave.addEventListener('click', () => saveWebhookConfig());
  }

  const btnWebhookTest = document.getElementById('btn-webhook-test');
  if (btnWebhookTest) {
    btnWebhookTest.addEventListener('click', () => testWebhook());
  }

  const btnWebhookTestScreenshot = document.getElementById('btn-webhook-test-screenshot');
  if (btnWebhookTestScreenshot) {
    btnWebhookTestScreenshot.addEventListener('click', () => testWebhookScreenshot());
  }

  const btnSendInstantScreenshot = document.getElementById('btn-send-instant-screenshot');
  if (btnSendInstantScreenshot) {
    btnSendInstantScreenshot.addEventListener('click', () => testWebhookScreenshot());
  }

  const btnSendInstantInstances = document.getElementById('btn-send-instant-instances');
  if (btnSendInstantInstances) {
    btnSendInstantInstances.addEventListener('click', () => testWebhookInstances());
  }

  const webhookScreenshotToggle = document.getElementById('webhook-screenshot-enable-toggle') as HTMLInputElement | null;
  const webhookScreenshotStatusLabel = document.getElementById('webhook-screenshot-status-label');
  if (webhookScreenshotToggle && webhookScreenshotStatusLabel) {
    webhookScreenshotToggle.addEventListener('change', () => {
      webhookScreenshotStatusLabel.textContent = webhookScreenshotToggle.checked ? 'Enabled' : 'Disabled';
      webhookScreenshotStatusLabel.style.color = webhookScreenshotToggle.checked ? 'var(--green)' : 'var(--muted)';
    });
  }

  const webhookEnableToggle = document.getElementById('webhook-enable-toggle') as HTMLInputElement | null;
  const webhookStatusLabel = document.getElementById('webhook-status-label');
  if (webhookEnableToggle && webhookStatusLabel) {
    webhookEnableToggle.addEventListener('change', () => {
      webhookStatusLabel.textContent = webhookEnableToggle.checked ? 'Enabled' : 'Disabled';
      webhookStatusLabel.style.color = webhookEnableToggle.checked ? 'var(--green)' : 'var(--muted)';
    });
  }

  const webhookInstanceToggle = document.getElementById('webhook-instance-summary-toggle') as HTMLInputElement | null;
  const webhookInstanceStatusLabel = document.getElementById('webhook-instance-status-label');
  if (webhookInstanceToggle && webhookInstanceStatusLabel) {
    webhookInstanceToggle.addEventListener('change', () => {
      webhookInstanceStatusLabel.textContent = webhookInstanceToggle.checked ? 'Enabled' : 'Disabled';
      webhookInstanceStatusLabel.style.color = webhookInstanceToggle.checked ? 'var(--green)' : 'var(--muted)';
    });
  }

  const btnToggleWebhookVis = document.getElementById('btn-toggle-webhook-visibility');
  const webhookUrlInput = document.getElementById('webhook-url-input') as HTMLInputElement | null;
  if (btnToggleWebhookVis && webhookUrlInput) {
    btnToggleWebhookVis.addEventListener('click', () => {
      webhookUrlInput.type = webhookUrlInput.type === 'password' ? 'text' : 'password';
    });
  }

  // Console View Filter Tabs & Actions
  const filterTabs = document.getElementById('console-filter-tabs');
  if (filterTabs) {
    filterTabs.querySelectorAll('.console-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        filterTabs.querySelectorAll('.console-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        consoleFilterLevel = btn.getAttribute('data-filter') || 'all';
        renderConsoleView();
      });
    });
  }

  let consoleSearchDebounceTimer: any = null;
  const consoleSearch = document.getElementById('console-search-input') as HTMLInputElement | null;
  if (consoleSearch) {
    consoleSearch.addEventListener('input', () => {
      consoleSearchQuery = consoleSearch.value.trim();
      if (consoleSearchDebounceTimer) clearTimeout(consoleSearchDebounceTimer);
      consoleSearchDebounceTimer = setTimeout(() => {
        renderConsoleView();
      }, 50);
    });
  }

  const btnCopyLogs = document.getElementById('btn-console-copy');
  if (btnCopyLogs) {
    btnCopyLogs.addEventListener('click', () => {
      const rows = document.querySelectorAll('#console-view-body .console-log-row');
      const text = Array.from(rows).map(r => r.textContent || '').join('\n');
      copyToClipboard(text);
      toast('Console logs copied to clipboard!', 'success');
    });
  }

  const btnExportLogs = document.getElementById('btn-console-export');
  if (btnExportLogs) {
    btnExportLogs.addEventListener('click', async () => {
      const rows = document.querySelectorAll('#console-view-body .console-log-row');
      const text = Array.from(rows).map(r => r.textContent || '').join('\n');
      const defaultName = `fram-console-logs-${new Date().toISOString().slice(0, 10)}.log`;
      await saveTextFileNative({
        title: 'Export Console Logs',
        defaultPath: defaultName,
        filters: [{ name: 'Log Files', extensions: ['log', 'txt'] }, { name: 'All Files', extensions: ['*'] }],
        content: text,
        successMessage: 'Exported console log file'
      });
    });
  }

  const btnClearLogs = document.getElementById('btn-console-clear');
  if (btnClearLogs) {
    btnClearLogs.addEventListener('click', () => {
      logBuffer = [];
      backendLogCache = [];
      renderConsoleView();
      toast('Console logs cleared', 'info');
    });
  }

  const autoScrollCheck = document.getElementById('console-autoscroll-check') as HTMLInputElement | null;
  if (autoScrollCheck) {
    autoScrollCheck.addEventListener('change', () => {
      consoleAutoScroll = autoScrollCheck.checked;
    });
  }

  const btnInstaller = document.getElementById('btn-roblox-installer');
  if (btnInstaller) {
    btnInstaller.addEventListener('click', () => {
      showRobloxInstallerModal();
    });
  }

  const btnInstances = document.getElementById('btn-instances');
  if (btnInstances) {
    btnInstances.addEventListener('click', () => {
      state.revealed = {};
      state.view = state.view === 'instances' ? 'accounts' : 'instances';
      renderAll();
    });
  }

  const btnToggleMultiInst = document.getElementById('btn-toggle-multi-instance');
  if (btnToggleMultiInst) {
    btnToggleMultiInst.addEventListener('click', async () => {
      try {
        const res = await apiService.toggleMultiInstance();
        if (res.success) {
          state.settings.multiInstance = res.enabled;
          toast(`Multi-instance ${res.enabled ? 'enabled' : 'disabled'}`, 'info');
          renderInstancesView();
        }
      } catch (err: any) {
        toast(`Failed to toggle multi-instance: ${err.message || err}`, 'error');
      }
    });
  }

  const btnTrimMemoryInstances = document.getElementById('btn-trim-memory-instances');
  if (btnTrimMemoryInstances) {
    btnTrimMemoryInstances.addEventListener('click', () => handleTrimMemoryAction(btnTrimMemoryInstances));
  }

  const btnArrangeInstances = document.getElementById('btn-arrange-instances');
  if (btnArrangeInstances) {
    btnArrangeInstances.addEventListener('click', async () => {
      try {
        toast('Arranging Roblox client windows...', 'info');
        const res = await apiService.autoArrangeClients();
        if (res.success) {
          toast(res.message || `Auto-arranged ${res.count} client(s)!`, 'success');
        } else {
          toast(res.message || res.error || 'No active Roblox clients detected', 'info');
        }
      } catch (err: any) {
        toast(err.message || 'Failed to arrange clients', 'error');
      }
    });
  }

  const btnRefreshInstances = document.getElementById('btn-refresh-instances');
  if (btnRefreshInstances) {
    btnRefreshInstances.addEventListener('click', () => {
      renderInstancesView();
      toast('Instances refreshed', 'info');
    });
  }

  const btnKillAllInstances = document.getElementById('btn-kill-all-instances');
  if (btnKillAllInstances) {
    btnKillAllInstances.addEventListener('click', async () => {
      try {
        const res = await apiService.killRobloxProcess();
        if (res.success) {
          toast(`Terminated all Roblox processes (${res.killed || 0} killed)`, 'success');
          renderInstancesView();
        } else {
          toast('Failed to kill Roblox processes', 'error');
        }
      } catch (err: any) {
        toast(`Error: ${err.message || err}`, 'error');
      }
    });
  }

  const placeInput = document.getElementById('place-input') as HTMLInputElement | null;
  if (placeInput) {
    const handlePlaceInputCheck = async (val: string) => {
      const trimmed = val.trim();
      if (!trimmed || state.placeMode === 'user') return;
      const direct = extractPrivateServerCode(trimmed);
      if (direct.code && direct.code !== trimmed) {
        if (direct.placeId) {
          placeInput.value = direct.placeId;
        }
        if (serverInput) {
          serverInput.value = direct.code;
        }
        state.serverMode = 'vip';
        renderLaunchBar();
        updateTargetGameFromPlaceInput(placeInput.value);
        saveLaunchBarState();
        toast('Detected VIP server link: set Place ID and Private Server Code', 'info');
        return;
      }
      if (/roblox\.com\/(?:share|share-links)|roblox:\/\/navigation\/share_links|share\?code=/i.test(trimmed)) {
        try {
          const a = state.selectedId ? getAccount(state.selectedId) : null;
          const cookie = a ? a.cookie : '';
          const resolved = await resolveAndNormalizePrivateServer(trimmed, cookie);
          if (resolved.placeId) {
            placeInput.value = resolved.placeId;
          }
          if (serverInput && resolved.code) {
            serverInput.value = resolved.code;
          }
          state.serverMode = 'vip';
          renderLaunchBar();
          updateTargetGameFromPlaceInput(placeInput.value);
          saveLaunchBarState();
          toast('Resolved private server share link: set Place ID and Code', 'success');
        } catch (_) { }
      }
    };

    placeInput.addEventListener('input', (e) => {
      const val = (e.target as HTMLInputElement).value;
      const direct = extractPrivateServerCode(val.trim());
      if (direct.code && direct.code !== val.trim() && state.placeMode !== 'user') {
        if (direct.placeId) placeInput.value = direct.placeId;
        if (serverInput) serverInput.value = direct.code;
        state.serverMode = 'vip';
      }
      renderLaunchBar();
      if (placeFetchTimeout) clearTimeout(placeFetchTimeout);
      placeFetchTimeout = setTimeout(() => {
        updateTargetGameFromPlaceInput(placeInput.value);
        handlePlaceInputCheck(placeInput.value);
      }, 350);
    });
    placeInput.addEventListener('change', () => {
      handlePlaceInputCheck(placeInput.value);
      saveLaunchBarState();
    });
    placeInput.addEventListener('blur', (e) => {
      const val = (e.target as HTMLInputElement).value;
      updateTargetGameFromPlaceInput(val);
      handlePlaceInputCheck(val);
      saveLaunchBarState();
    });
    placeInput.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      switchPlaceMode(state.placeMode === 'place' ? 'user' : 'place');
    });
  }

  const placeModeBtn = document.getElementById('place-mode-btn') as HTMLButtonElement | null;
  const placeModeDropdown = document.getElementById('place-mode-dropdown') as HTMLElement | null;
  const serverModeBtn = document.getElementById('server-mode-btn') as HTMLButtonElement | null;
  const serverModeDropdown = document.getElementById('server-mode-dropdown') as HTMLElement | null;

  if (placeModeBtn && placeModeDropdown) {
    placeModeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = placeModeDropdown.style.display !== 'none';
      placeModeDropdown.style.display = isOpen ? 'none' : 'flex';
      placeModeBtn.classList.toggle('open', !isOpen);
      if (serverModeDropdown && serverModeBtn) {
        serverModeDropdown.style.display = 'none';
        serverModeBtn.classList.remove('open');
      }
    });

    placeModeDropdown.querySelectorAll('.launch-mode-option').forEach(opt => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        const mode = opt.getAttribute('data-mode') as 'place' | 'user';
        if (mode) {
          switchPlaceMode(mode);
        }
        placeModeDropdown.style.display = 'none';
        placeModeBtn.classList.remove('open');
      });
    });
  }

  const serverInput = document.getElementById('server-input') as HTMLInputElement | null;
  if (serverInput) {
    const handleServerInputNormalization = async (rawVal: string) => {
      if (!rawVal || state.serverMode !== 'vip') return;
      const direct = extractPrivateServerCode(rawVal);
      if (direct.code && direct.code !== rawVal) {
        serverInput.value = direct.code;
        if (direct.placeId && placeInput && !placeInput.value.trim()) {
          placeInput.value = direct.placeId;
          updateTargetGameFromPlaceInput(direct.placeId);
        }
        saveLaunchBarState();
        toast('Converted private server link into code', 'success');
        return;
      }

      if (/roblox\.com\/(?:share|share-links)|roblox:\/\/navigation\/share_links|share\?code=/i.test(rawVal)) {
        try {
          const a = state.selectedId ? getAccount(state.selectedId) : null;
          const cookie = a ? a.cookie : '';
          const resolved = await resolveAndNormalizePrivateServer(rawVal, cookie);
          if (resolved.code && resolved.code !== rawVal) {
            serverInput.value = resolved.code;
            addLog(`Private server resolved to code: ${resolved.code}`, 'success');
            toast(`Private server share link converted to code`, 'success');
          }
          if (resolved.placeId && placeInput && !placeInput.value.trim()) {
            placeInput.value = resolved.placeId;
            updateTargetGameFromPlaceInput(resolved.placeId);
          }
          saveLaunchBarState();
        } catch (error) {
          addLog('Failed to resolve private server link: ' + error, 'error');
        }
      }
    };

    let serverInputTimeout: any = null;
    serverInput.addEventListener('input', (e) => {
      const val = (e.target as HTMLInputElement).value;
      if (state.serverMode === 'vip') {
        const direct = extractPrivateServerCode(val.trim());
        if (direct.code && direct.code !== val.trim()) {
          serverInput.value = direct.code;
          if (direct.placeId && placeInput && !placeInput.value.trim()) {
            placeInput.value = direct.placeId;
            updateTargetGameFromPlaceInput(direct.placeId);
          }
        }
        if (serverInputTimeout) clearTimeout(serverInputTimeout);
        serverInputTimeout = setTimeout(() => {
          handleServerInputNormalization(serverInput.value.trim());
        }, 400);
      }
      renderLaunchBar();
    });

    serverInput.addEventListener('blur', async (e) => {
      const value = (e.target as HTMLInputElement).value.trim();
      await handleServerInputNormalization(value);
      saveLaunchBarState();
    });
    serverInput.addEventListener('change', () => {
      saveLaunchBarState();
    });
    serverInput.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const nextMode = state.serverMode === 'vip' ? 'jobid' : state.serverMode === 'jobid' ? 'subplace' : 'vip';
      switchServerMode(nextMode);
    });
  }

  const serverSubplacesBtn = document.getElementById('server-subplaces-btn') as HTMLButtonElement | null;
  if (serverSubplacesBtn) {
    serverSubplacesBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const placeVal = (document.getElementById('place-input') as HTMLInputElement | null)?.value.trim() || '';
      const placeMatch = placeVal.match(/(?:games|placeId=|\/)?(\d{4,15})/);
      const placeId = placeMatch ? placeMatch[1] : (placeVal.match(/^\d+$/) ? placeVal : '');

      const serverVal = (document.getElementById('server-input') as HTMLInputElement | null)?.value.trim() || '';
      const fallbackPlaceId = serverVal.match(/^\d{4,15}$/) ? serverVal : '';

      const targetId = placeId || fallbackPlaceId;
      showSubplacesModal(targetId, state.targetGameName);
    });
  }

  if (serverModeBtn && serverModeDropdown) {
    serverModeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = serverModeDropdown.style.display !== 'none';
      serverModeDropdown.style.display = isOpen ? 'none' : 'flex';
      serverModeBtn.classList.toggle('open', !isOpen);
      if (placeModeDropdown && placeModeBtn) {
        placeModeDropdown.style.display = 'none';
        placeModeBtn.classList.remove('open');
      }
    });

    serverModeDropdown.querySelectorAll('.launch-mode-option').forEach(opt => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        const mode = opt.getAttribute('data-mode') as 'vip' | 'jobid' | 'subplace';
        if (mode) {
          switchServerMode(mode);
        }
        serverModeDropdown.style.display = 'none';
        serverModeBtn.classList.remove('open');
      });
    });
  }

  document.addEventListener('click', (e) => {
    const target = e.target as HTMLElement;
    if (placeModeDropdown && !placeModeDropdown.contains(target) && !placeModeBtn?.contains(target)) {
      placeModeDropdown.style.display = 'none';
      placeModeBtn?.classList.remove('open');
    }
    if (serverModeDropdown && !serverModeDropdown.contains(target) && !serverModeBtn?.contains(target)) {
      serverModeDropdown.style.display = 'none';
      serverModeBtn?.classList.remove('open');
    }
  });

  const versionSelect = document.getElementById('version-select') as HTMLSelectElement;
  if (versionSelect) {
    versionSelect.addEventListener('change', () => {
      state.selectedVersion = versionSelect.value;
      addLog('Selected Roblox version: ' + state.selectedVersion, 'info');
    });
  }

  const btnLaunch = document.getElementById('btn-launch');
  if (btnLaunch) {
    btnLaunch.addEventListener('click', () => {
      const selected = getSelectedAccounts();
      if (selected.length > 0) {
        handleLaunchSelectedAccounts();
      } else {
        toast('Please select an account first', 'error');
      }
    });
  }

  const btnLaunchBrowser = document.getElementById('btn-launch-browser');
  if (btnLaunchBrowser) {
    btnLaunchBrowser.addEventListener('click', () => {
      const selected = getSelectedAccounts();
      if (selected.length > 0) {
        handleLaunchSelectedBrowsers();
      } else {
        toast('Please select an account first', 'error');
      }
    });
  }

  const btnMin = document.getElementById('btn-min');
  if (btnMin) {
    btnMin.addEventListener('click', async () => {
      try {
        if (state.settings.minimizeToTray) {
          await invoke('hide_window');
          toast('FRAM minimized to hidden icons / system tray', 'info');
        } else {
          await invoke('minimize_window');
        }
      } catch (error) {
        addLog('Failed to minimize window: ' + error, 'error');
      }
    });
  }

  const btnClose = document.getElementById('btn-close');
  if (btnClose) {
    btnClose.addEventListener('click', async () => {
      saveLaunchBarState();
      try {
        if (state.settings.minimizeToTray) {
          await invoke('hide_window');
          toast('FRAM minimized to hidden icons / system tray', 'info');
        } else {
          if (state.settings.autoKillRobloxOnExit) {
            await apiService.killRobloxProcess().catch(() => { });
          }
          await invoke('close_window');
        }
      } catch (error) {
        addLog('Failed to close window: ' + error, 'error');
      }
    });
  }

  window.addEventListener('beforeunload', () => {
    saveLaunchBarState();
    if (state.settings.autoKillRobloxOnExit) {
      apiService.killRobloxProcess().catch(() => { });
    }
  });

  setupKeyboardShortcuts();

  renderAll();
}

function removeUnlockScreen(): void {
  const existing = document.getElementById('unlock-overlay');
  if (existing) {
    existing.remove();
  }
}

function renderUnlockScreen(): void {
  removeUnlockScreen();

  const overlay = el('div', { id: 'unlock-overlay', class: 'unlock-overlay' }, []);
  const card = el('div', { class: 'unlock-card' }, []);

  const iconWrap = el('div', {
    class: 'unlock-icon-wrap',
    html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path><circle cx="12" cy="16" r="1"></circle></svg>`
  }, []);

  const title = el('div', { class: 'unlock-title' }, [document.createTextNode('Master Password Required')]);
  const desc = el('div', { class: 'unlock-desc' }, [
    document.createTextNode('Please enter your master password to unlock your accounts.')
  ]);

  const form = el('form', { class: 'unlock-form' }, []);
  const inputWrap = el('div', { class: 'unlock-input-wrap' }, []);

  const pwdInput = el('input', {
    type: 'password',
    id: 'unlock-password-input',
    placeholder: 'Enter master password...',
    autocomplete: 'current-password',
    required: 'true'
  }, []) as HTMLInputElement;

  let showPwd = false;
  const eyeBtn = el('button', {
    type: 'button',
    class: 'unlock-eye-btn',
    title: 'Show/Hide Password',
    html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`
  }, []);
  eyeBtn.addEventListener('click', () => {
    showPwd = !showPwd;
    pwdInput.type = showPwd ? 'text' : 'password';
  });

  inputWrap.appendChild(pwdInput);
  inputWrap.appendChild(eyeBtn);

  const errorDiv = el('div', { class: 'unlock-error', id: 'unlock-error-msg' }, []);

  const submitBtn = el('button', {
    type: 'submit',
    class: 'btn btn-primary unlock-btn'
  }, [document.createTextNode('Unlock Application')]) as HTMLButtonElement;

  form.appendChild(inputWrap);
  form.appendChild(errorDiv);
  form.appendChild(submitBtn);

  const doUnlock = async () => {
    const val = pwdInput.value.trim();
    if (!val) {
      errorDiv.textContent = 'Please enter your master password.';
      pwdInput.focus();
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Unlocking...';
    errorDiv.textContent = '';

    try {
      const res = await apiService.unlockApp(val);
      if (res && res.success) {
        state.isLocked = false;
        removeUnlockScreen();
        toast('App unlocked successfully', 'success');
        await loadFromBackend();
        renderAll();
      } else {
        errorDiv.textContent = res?.error || 'Invalid master password. Please try again.';
        pwdInput.focus();
        pwdInput.select();
      }
    } catch (err: any) {
      errorDiv.textContent = err?.message || 'Invalid master password. Please try again.';
      pwdInput.focus();
      pwdInput.select();
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Unlock Application';
    }
  };

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    doUnlock();
  });

  submitBtn.addEventListener('click', (e) => {
    e.preventDefault();
    doUnlock();
  });

  pwdInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      doUnlock();
    }
  });

  card.appendChild(iconWrap);
  card.appendChild(title);
  card.appendChild(desc);
  card.appendChild(form);
  overlay.appendChild(card);

  document.body.appendChild(overlay);
  setTimeout(() => pwdInput.focus(), 100);
}

async function fetchWebhookConfig() {
  try {
    const data = await apiService.getWebhookConfig();
    if (data.success && data.config) {
      const cfg = data.config;
      const urlInput = document.getElementById('webhook-url-input') as HTMLInputElement | null;
      const enableToggle = document.getElementById('webhook-enable-toggle') as HTMLInputElement | null;
      const pingInput = document.getElementById('webhook-ping-user-input') as HTMLInputElement | null;
      const launchesToggle = document.getElementById('webhook-trigger-launches') as HTMLInputElement | null;
      const rejoinsToggle = document.getElementById('webhook-trigger-rejoins') as HTMLInputElement | null;
      const logsToggle = document.getElementById('webhook-trigger-logs') as HTMLInputElement | null;
      const redactToggle = document.getElementById('webhook-redact-sensitive') as HTMLInputElement | null;
      const screenshotEnableToggle = document.getElementById('webhook-screenshot-enable-toggle') as HTMLInputElement | null;
      const screenshotIntervalInput = document.getElementById('webhook-screenshot-interval') as HTMLInputElement | null;
      const screenshotAllMonitorsToggle = document.getElementById('webhook-screenshot-all-monitors') as HTMLInputElement | null;
      const screenshotStatusLabel = document.getElementById('webhook-screenshot-status-label');
      const instanceSummaryToggle = document.getElementById('webhook-instance-summary-toggle') as HTMLInputElement | null;
      const instanceSummaryIntervalInput = document.getElementById('webhook-instance-summary-interval') as HTMLInputElement | null;
      const instanceStatusLabel = document.getElementById('webhook-instance-status-label');
      const statusLabel = document.getElementById('webhook-status-label');

      if (urlInput) urlInput.value = cfg.webhook_url || '';
      if (enableToggle) enableToggle.checked = Boolean(cfg.enabled);
      if (pingInput) pingInput.value = cfg.ping_user_id || '';
      if (launchesToggle) launchesToggle.checked = cfg.send_launches !== false;
      if (rejoinsToggle) rejoinsToggle.checked = cfg.send_rejoins !== false;
      if (logsToggle) logsToggle.checked = cfg.send_logs !== false;
      if (redactToggle) redactToggle.checked = cfg.redact_sensitive !== false;
      if (screenshotEnableToggle) screenshotEnableToggle.checked = Boolean(cfg.screenshot_enabled);
      if (screenshotIntervalInput) screenshotIntervalInput.value = String(cfg.screenshot_interval_minutes || 15);
      if (screenshotAllMonitorsToggle) screenshotAllMonitorsToggle.checked = Boolean(cfg.screenshot_all_monitors);
      if (screenshotStatusLabel) {
        screenshotStatusLabel.textContent = cfg.screenshot_enabled ? 'Enabled' : 'Disabled';
        screenshotStatusLabel.style.color = cfg.screenshot_enabled ? 'var(--green)' : 'var(--muted)';
      }
      if (instanceSummaryToggle) instanceSummaryToggle.checked = Boolean(cfg.instance_summary_enabled);
      if (instanceSummaryIntervalInput) instanceSummaryIntervalInput.value = String(cfg.instance_summary_interval_minutes || 15);
      if (instanceStatusLabel) {
        instanceStatusLabel.textContent = cfg.instance_summary_enabled ? 'Enabled' : 'Disabled';
        instanceStatusLabel.style.color = cfg.instance_summary_enabled ? 'var(--green)' : 'var(--muted)';
      }
      if (statusLabel) {
        statusLabel.textContent = cfg.enabled ? 'Enabled' : 'Disabled';
        statusLabel.style.color = cfg.enabled ? 'var(--green)' : 'var(--muted)';
      }

      if (data.history && Array.isArray(data.history)) {
        renderWebhookHistory(data.history);
      }
    }
  } catch (err) {
    console.error('Failed to fetch webhook config:', err);
  }
}

function renderWebhookHistory(history: any[]) {
  const container = document.getElementById('webhook-history-container');
  if (!container) return;
  if (!history || history.length === 0) {
    container.innerHTML = `<span style="color:var(--muted);">No webhook events recorded yet.</span>`;
    return;
  }
  container.innerHTML = history.map(item => {
    const isOk = item.status === 'Success';
    const badgeColor = isOk ? 'var(--green)' : 'var(--red)';
    return `<div style="display:flex; justify-content:space-between; align-items:center; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.05);">
      <div>
        <span style="color:var(--muted); margin-right:8px;">[${item.timestamp}]</span>
        <b style="color:var(--text-bright);">${item.event}</b>
      </div>
      <span style="color:${badgeColor}; font-weight:600;">${item.status}</span>
    </div>`;
  }).join('');
}

async function saveWebhookConfig() {
  const urlInput = document.getElementById('webhook-url-input') as HTMLInputElement | null;
  const enableToggle = document.getElementById('webhook-enable-toggle') as HTMLInputElement | null;
  const pingInput = document.getElementById('webhook-ping-user-input') as HTMLInputElement | null;
  const launchesToggle = document.getElementById('webhook-trigger-launches') as HTMLInputElement | null;
  const rejoinsToggle = document.getElementById('webhook-trigger-rejoins') as HTMLInputElement | null;
  const logsToggle = document.getElementById('webhook-trigger-logs') as HTMLInputElement | null;
  const redactToggle = document.getElementById('webhook-redact-sensitive') as HTMLInputElement | null;
  const screenshotEnableToggle = document.getElementById('webhook-screenshot-enable-toggle') as HTMLInputElement | null;
  const screenshotIntervalInput = document.getElementById('webhook-screenshot-interval') as HTMLInputElement | null;
  const screenshotAllMonitorsToggle = document.getElementById('webhook-screenshot-all-monitors') as HTMLInputElement | null;
  const instanceSummaryToggle = document.getElementById('webhook-instance-summary-toggle') as HTMLInputElement | null;
  const instanceSummaryIntervalInput = document.getElementById('webhook-instance-summary-interval') as HTMLInputElement | null;

  const payload = {
    webhook_url: urlInput?.value.trim() || '',
    enabled: enableToggle?.checked || false,
    ping_user_id: pingInput?.value.trim() || '',
    send_launches: launchesToggle?.checked || false,
    send_rejoins: rejoinsToggle?.checked || false,
    send_logs: logsToggle?.checked || false,
    redact_sensitive: redactToggle?.checked || false,
    screenshot_enabled: screenshotEnableToggle?.checked || false,
    screenshot_interval_minutes: parseInt(screenshotIntervalInput?.value || '15', 10) || 15,
    screenshot_all_monitors: screenshotAllMonitorsToggle?.checked || false,
    instance_summary_enabled: instanceSummaryToggle?.checked || false,
    instance_summary_interval_minutes: parseInt(instanceSummaryIntervalInput?.value || '15', 10) || 15
  };

  try {
    const data = await apiService.saveWebhookConfig(payload);
    if (data.success) {
      toast('Webhook settings saved successfully!', 'success');
      fetchWebhookConfig();
    } else {
      toast(data.error || 'Failed to save webhook settings', 'error');
    }
  } catch (err) {
    toast('Failed to save webhook settings', 'error');
  }
}

async function testWebhook() {
  const urlInput = document.getElementById('webhook-url-input') as HTMLInputElement | null;
  const url = urlInput?.value.trim();
  if (!url) {
    toast('Please enter a Discord Webhook URL first.', 'info');
    return;
  }
  toast('Sending test webhook to Discord...', 'info');
  try {
    const data = await apiService.testWebhook(url);
    if (data.success) {
      toast('Test webhook delivered successfully!', 'success');
      fetchWebhookConfig();
    } else {
      toast(data.error || 'Test webhook failed.', 'error');
    }
  } catch (err) {
    toast('Failed to send test webhook.', 'error');
  }
}

async function testWebhookScreenshot() {
  const urlInput = document.getElementById('webhook-url-input') as HTMLInputElement | null;
  const allMonitorsToggle = document.getElementById('webhook-screenshot-all-monitors') as HTMLInputElement | null;
  const url = urlInput?.value.trim();
  if (!url) {
    toast('Please enter a Discord Webhook URL first.', 'info');
    return;
  }
  const allMonitors = allMonitorsToggle ? allMonitorsToggle.checked : false;
  toast(`Capturing and sending screenshot (${allMonitors ? 'All Monitors' : 'Primary Monitor'})...`, 'info');
  try {
    const data = await apiService.testWebhookScreenshot(url, allMonitors);
    if (data.success) {
      toast('Monitor screenshot delivered successfully to Discord!', 'success');
      fetchWebhookConfig();
    } else {
      toast(data.error || 'Screenshot delivery failed.', 'error');
    }
  } catch (err) {
    toast('Failed to send monitor screenshot.', 'error');
  }
}

async function testWebhookInstances() {
  const urlInput = document.getElementById('webhook-url-input') as HTMLInputElement | null;
  const url = urlInput?.value.trim();
  if (!url) {
    toast('Please enter a Discord Webhook URL first.', 'info');
    return;
  }
  toast('Sending Roblox instance status report to Discord...', 'info');
  try {
    const data = await apiService.testWebhookInstances(url);
    if (data.success) {
      toast('Instance status report delivered successfully to Discord!', 'success');
      fetchWebhookConfig();
    } else {
      toast(data.error || 'Instance report delivery failed.', 'error');
    }
  } catch (err) {
    toast('Failed to send instance status report.', 'error');
  }
}

function escapeHtml(str: string): string {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

let cachedExtensions: BrowserExtension[] = [];

async function renderExtensionsView() {
  const container = document.getElementById('extensions-grid');
  if (!container) return;

  try {
    const res = await apiService.getExtensions();
    if (!res.success || !res.extensions) {
      container.innerHTML = `<div style="grid-column:1/-1; padding:24px; text-align:center; color:var(--red); background:var(--card); border:1px solid var(--border); border-radius:8px;">Failed to load extensions: ${escapeHtml(res.error || 'Unknown error')}</div>`;
      return;
    }

    cachedExtensions = res.extensions;
    if (cachedExtensions.length === 0) {
      container.innerHTML = `
        <div style="grid-column:1/-1; padding:32px 20px; text-align:center; background:var(--card); border:1px solid var(--border); border-radius:8px; display:flex; flex-direction:column; align-items:center; gap:12px;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40" style="color:var(--muted);" class="lucide lucide-blocks"><path d="M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2"/><rect x="14" y="2" width="8" height="8" rx="1"/></svg>
          <div style="font-size:15px; font-weight:600; color:var(--text-bright);">No Browser Extensions Installed</div>
          <div style="font-size:13px; color:var(--muted); max-width:440px;">Installed extensions will automatically load into browser automation and web sign-in windows.</div>
          <button class="btn btn-primary btn-sm" id="btn-extensions-empty-install" style="margin-top:6px;">+ Install Extension</button>
        </div>
      `;
      const emptyBtn = document.getElementById('btn-extensions-empty-install');
      if (emptyBtn) {
        emptyBtn.addEventListener('click', () => openInstallExtensionModal());
      }
      return;
    }

    container.innerHTML = cachedExtensions.map(ext => `
      <div class="ext-card" style="background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; display:flex; flex-direction:column; gap:12px; position:relative;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
          <div style="flex:1; overflow:hidden;">
            <div style="font-size:14px; font-weight:600; color:var(--text-bright); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(ext.name)}">${escapeHtml(ext.name)}</div>
            <div style="display:flex; align-items:center; gap:6px; margin-top:4px; flex-wrap:wrap;">
              <span class="ext-badge ${escapeHtml(ext.source)}" style="font-size:10px; font-weight:600; padding:2px 7px; border-radius:4px; text-transform:uppercase; background:var(--primary-dim); color:var(--primary); border:1px solid rgba(79, 142, 247, 0.3);">${escapeHtml(ext.display_source || ext.source)}</span>
              ${ext.manifest_version ? `<span style="font-size:10px; padding:2px 6px; border-radius:4px; background:var(--bg-2); color:var(--muted); border:1px solid var(--border);">MV${ext.manifest_version}</span>` : ''}
            </div>
          </div>
          <label class="toggle-switch" style="cursor:pointer;" title="${ext.enabled ? 'Enabled' : 'Disabled'}">
            <input type="checkbox" class="ext-toggle-check" data-key="${escapeHtml(ext.key)}" ${ext.enabled ? 'checked' : ''}>
          </label>
        </div>

        <div style="font-size:11px; color:var(--muted); display:flex; flex-direction:column; gap:4px; background:var(--bg-2); padding:8px 10px; border-radius:6px; border:1px solid var(--border-soft); word-break:break-all;">
          ${ext.extension_id ? `<div><strong style="color:var(--fg-2);">ID:</strong> ${escapeHtml(ext.extension_id)}</div>` : ''}
          <div><strong style="color:var(--fg-2);">Key:</strong> ${escapeHtml(ext.key)}</div>
          ${ext.installed_at ? `<div><strong style="color:var(--fg-2);">Installed:</strong> ${escapeHtml(ext.installed_at)}</div>` : ''}
        </div>

        <div style="display:flex; justify-content:flex-end; align-items:center; margin-top:auto; padding-top:6px; border-top:1px solid var(--border-soft);">
          <button class="btn btn-secondary btn-sm ext-delete-btn" data-key="${escapeHtml(ext.key)}" data-name="${escapeHtml(ext.name)}" style="color:var(--red); border-color:rgba(240, 87, 92, 0.3); padding:4px 10px; font-size:11.5px; display:inline-flex; align-items:center; gap:4px;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            Uninstall
          </button>
        </div>
      </div>
    `).join('');

    container.querySelectorAll('.ext-toggle-check').forEach(chk => {
      chk.addEventListener('change', async (e) => {
        const input = e.target as HTMLInputElement;
        const key = input.getAttribute('data-key') || '';
        try {
          const res = await apiService.toggleExtension(key, input.checked);
          if (res.success) {
            toast(`Extension ${input.checked ? 'enabled' : 'disabled'}`, 'info');
          } else {
            input.checked = !input.checked;
            toast(res.error || 'Failed to toggle extension', 'error');
          }
        } catch (err: any) {
          input.checked = !input.checked;
          toast(err.message || 'Failed to toggle extension', 'error');
        }
      });
    });

    container.querySelectorAll('.ext-delete-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const key = btn.getAttribute('data-key') || '';
        const name = btn.getAttribute('data-name') || 'this extension';
        try {
          const res = await apiService.deleteExtension(key);
          if (res.success) {
            toast(`Extension "${name}" uninstalled`, 'success');
            renderExtensionsView();
          } else {
            toast(res.error || 'Failed to uninstall extension', 'error');
          }
        } catch (err: any) {
          toast(err.message || 'Failed to uninstall extension', 'error');
        }
      });
    });

  } catch (err: any) {
    container.innerHTML = `<div style="grid-column:1/-1; padding:24px; text-align:center; color:var(--red);">Error loading extensions: ${escapeHtml(err.message || err)}</div>`;
  }
}

function openInstallExtensionModal() {
  const modal = document.getElementById('install-extension-overlay');
  if (modal) {
    modal.classList.add('show');
    updateInstallModalSourceUI();
  }
}

function updateInstallModalSourceUI() {
  const sourceSelect = document.getElementById('ext-install-source') as HTMLSelectElement | null;
  const label = document.getElementById('ext-install-label');
  const targetInput = document.getElementById('ext-install-target') as HTMLInputElement | null;
  const hint = document.getElementById('ext-install-hint');
  const browseBtn = document.getElementById('ext-install-browse-btn');

  if (!sourceSelect || !label || !targetInput || !hint || !browseBtn) return;

  const source = sourceSelect.value;
  if (source === 'web_store') {
    label.textContent = 'Chrome Web Store ID or URL';
    targetInput.placeholder = 'e.g. cjpalhdlnbpafiamejdnhcphjbkeiagm';
    hint.textContent = 'Paste a 32-character Chrome Web Store extension ID or store URL';
    browseBtn.style.display = 'none';
  } else if (source === 'firefox') {
    label.textContent = 'Firefox Add-on Slug, GUID, or URL';
    targetInput.placeholder = 'e.g. ublock-origin';
    hint.textContent = 'Enter Firefox Add-on slug (e.g. ublock-origin), GUID, or store URL';
    browseBtn.style.display = 'none';
  } else if (source === 'unpacked') {
    label.textContent = 'Unpacked Extension Folder Path';
    targetInput.placeholder = 'C:\\path\\to\\unpacked-extension';
    hint.textContent = 'Path to directory containing manifest.json';
    browseBtn.style.display = 'inline-block';
  } else if (source === 'crx') {
    label.textContent = 'Chrome CRX File Path';
    targetInput.placeholder = 'C:\\path\\to\\extension.crx';
    hint.textContent = 'Path to local .crx package file';
    browseBtn.style.display = 'inline-block';
  } else if (source === 'xpi') {
    label.textContent = 'Firefox XPI File Path';
    targetInput.placeholder = 'C:\\path\\to\\extension.xpi';
    hint.textContent = 'Path to local .xpi package file';
    browseBtn.style.display = 'inline-block';
  }
}

let bloxgenActiveTab: 'overview' | 'generator' | 'checker' | 'botting' = 'overview';
let bloxgenKeyInputVisible = false;
let bloxgenSelectedType = 'alt';
let bloxgenSelectedTarget = '';
let bloxgenLastGeneratedAccount: any = null;
let bloxgenHistory: any[] = [];
let bloxgenOverviewData: {
  balance?: any;
  stock?: any;
  prices?: any;
  dailyLimit?: any;
  loadedKey?: string;
} = {};

function loadBloxgenStoredData(): void {
  try {
    const rawHist = localStorage.getItem('fram_bloxgen_history');
    if (rawHist) {
      const parsed = JSON.parse(rawHist);
      bloxgenHistory = Array.isArray(parsed) ? parsed : [];
    }
  } catch (e) {
    bloxgenHistory = [];
  }
  try {
    const rawLast = localStorage.getItem('fram_bloxgen_last_account');
    if (rawLast) {
      bloxgenLastGeneratedAccount = JSON.parse(rawLast);
    }
  } catch (e) {
    bloxgenLastGeneratedAccount = null;
  }
}

function saveBloxgenStoredData(): void {
  try {
    localStorage.setItem('fram_bloxgen_history', JSON.stringify(bloxgenHistory.slice(0, 100)));
    if (bloxgenLastGeneratedAccount) {
      localStorage.setItem('fram_bloxgen_last_account', JSON.stringify(bloxgenLastGeneratedAccount));
    } else {
      localStorage.removeItem('fram_bloxgen_last_account');
    }
  } catch (e) {
    console.error('Failed to save BloxGen history to localStorage', e);
  }
}

loadBloxgenStoredData();

async function fetchBloxgenOverviewData(apiKey: string) {
  if (!apiKey) return;
  try {
    const [balRes, stockRes, pricesRes, limitRes] = await Promise.all([
      apiService.getBloxgenBalance(apiKey).catch(() => null),
      apiService.getBloxgenStock(apiKey).catch(() => null),
      apiService.getBloxgenPrices(apiKey).catch(() => null),
      apiService.getBloxgenDailyLimit(apiKey).catch(() => null)
    ]);
    bloxgenOverviewData = {
      balance: balRes,
      stock: stockRes,
      prices: pricesRes,
      dailyLimit: limitRes,
      loadedKey: apiKey
    };
  } catch (err) {
    console.error('Failed to fetch BloxGen overview data', err);
  }
}

function openBloxgenFlexCardModal(acc: any): void {
  const existing = document.getElementById('bloxgen-flex-modal');
  if (existing) existing.remove();

  const backdrop = el('div', { id: 'bloxgen-flex-modal', class: 'bloxgen-flex-modal-backdrop' }, []);
  const modal = el('div', { class: 'bloxgen-flex-modal-card' }, [
    el('div', { style: 'display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-soft); padding-bottom:10px;' }, [
      el('h3', { style: 'margin:0; font-size:16px; font-weight:700; color:var(--text-bright); display:flex; align-items:center; gap:8px;' }, [
        document.createTextNode('🏆 BloxGen Account Card')
      ]),
      (() => {
        const closeBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px;' }, [document.createTextNode('✕')]);
        closeBtn.onclick = () => backdrop.remove();
        return closeBtn;
      })()
    ])
  ]);

  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 680;
  canvas.className = 'bloxgen-flex-canvas-preview';
  modal.appendChild(canvas);

  const drawCard = (avatarImg?: HTMLImageElement) => {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const bgGradient = ctx.createLinearGradient(0, 0, 1200, 680);
    bgGradient.addColorStop(0, '#090d16');
    bgGradient.addColorStop(0.5, '#0f172a');
    bgGradient.addColorStop(1, '#1e1b4b');
    ctx.fillStyle = bgGradient;
    ctx.fillRect(0, 0, 1200, 680);

    const radGrad = ctx.createRadialGradient(240, 240, 10, 240, 240, 400);
    radGrad.addColorStop(0, 'rgba(225, 32, 40, 0.25)');
    radGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = radGrad;
    ctx.fillRect(0, 0, 1200, 680);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 4;
    ctx.strokeRect(16, 16, 1168, 648);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.beginPath();
    ctx.roundRect(40, 40, 1120, 600, 20);
    ctx.fill();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#e12028';
    ctx.font = '900 24px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText('BLOXGEN', 70, 95);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.font = '600 16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText('ACCOUNT PASSPORT', 200, 94);

    const typeText = (acc.type || 'ALT').toUpperCase();
    ctx.fillStyle = '#e12028';
    ctx.beginPath();
    ctx.roundRect(960, 68, 160, 40, 8);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 15px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(typeText, 1040, 93);
    ctx.textAlign = 'left';

    ctx.save();
    ctx.beginPath();
    ctx.roundRect(70, 150, 220, 220, 24);
    ctx.clip();
    if (avatarImg && avatarImg.complete && avatarImg.naturalWidth > 0) {
      ctx.drawImage(avatarImg, 70, 150, 220, 220);
    } else {
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(70, 150, 220, 220);
      ctx.fillStyle = '#94a3b8';
      ctx.font = 'bold 72px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText((acc.username || 'U')[0].toUpperCase(), 180, 285);
      ctx.textAlign = 'left';
    }
    ctx.restore();

    ctx.strokeStyle = 'rgba(225, 32, 40, 0.6)';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.roundRect(70, 150, 220, 220, 24);
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 42px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(acc.username || 'Roblox User', 330, 210);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.font = '500 20px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(`Roblox ID: ${acc.id || 'N/A'}`, 330, 255);

    let badgeX = 330;
    const drawPill = (text: string, bgColor: string, textColor: string) => {
      ctx.font = 'bold 16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      const w = ctx.measureText(text).width + 30;
      ctx.fillStyle = bgColor;
      ctx.beginPath();
      ctx.roundRect(badgeX, 290, w, 36, 18);
      ctx.fill();
      ctx.fillStyle = textColor;
      ctx.fillText(text, badgeX + 15, 314);
      badgeX += w + 14;
    };

    if (acc.region) {
      drawPill(`📍 ${acc.region}`, 'rgba(59, 130, 246, 0.2)', '#60a5fa');
    }
    if (acc.age_verified || acc.type === '18+ age verified') {
      drawPill('🔞 18+ Age Verified', 'rgba(244, 63, 94, 0.2)', '#fb7185');
    }
    if (acc.email_verified) {
      drawPill('✉️ Email Verified', 'rgba(56, 189, 248, 0.2)', '#38bdf8');
    }
    if (acc.estimated_age_group || acc.estimated_age) {
      drawPill(`Age: ${acc.estimated_age_group || acc.estimated_age}`, 'rgba(255, 255, 255, 0.1)', '#e2e8f0');
    }

    const statBoxY = 410;
    const stats = [
      { label: 'STATUS', value: 'Active & Verified', color: '#4ade80' },
      { label: 'REGION LOCK', value: acc.region || 'Global / Any', color: '#ffffff' },
      { label: 'ROBUX / RAP', value: (acc.robux || acc.rap) ? `R$ ${acc.robux || 0} / ${acc.rap || 0}` : 'Standard Stock', color: (acc.robux || acc.rap) ? '#facc15' : '#94a3b8' },
      { label: 'GENERATED', value: acc.timestamp ? acc.timestamp.split(',')[0] : 'Today', color: '#94a3b8' }
    ];

    stats.forEach((stat, idx) => {
      const sx = 70 + idx * 265;
      ctx.fillStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.beginPath();
      ctx.roundRect(sx, statBoxY, 245, 100, 12);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.font = '700 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      ctx.fillText(stat.label, sx + 20, statBoxY + 34);

      ctx.fillStyle = stat.color;
      ctx.font = 'bold 18px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      ctx.fillText(stat.value, sx + 20, statBoxY + 70);
    });

    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.font = '500 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText('Powered by BloxGen API • Forked Roblox Account Manager', 70, 595);
  };

  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.onload = () => drawCard(img);
  img.onerror = () => drawCard();
  const avatarSrc = acc.fullAvatarUrl || acc.avatarUrl;
  if (avatarSrc) {
    img.src = avatarSrc;
  } else {
    drawCard();
  }

  const actionsRow = el('div', { style: 'display:flex; justify-content:flex-end; gap:10px; margin-top:8px;' }, [
    (() => {
      const copyBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:6px 14px;' }, [document.createTextNode('📋 Copy Image')]);
      copyBtn.onclick = () => {
        canvas.toBlob(blob => {
          if (blob && navigator.clipboard && (window as any).ClipboardItem) {
            navigator.clipboard.write([new (window as any).ClipboardItem({ 'image/png': blob })])
              .then(() => toast('Card image copied to clipboard!', 'success'))
              .catch(() => toast('Failed to copy card image', 'error'));
          } else {
            toast('Clipboard item copy not supported in this environment', 'error');
          }
        });
      };
      return copyBtn;
    })(),
    (() => {
      const downloadBtn = el('button', { class: 'btn btn-primary btn-sm', style: 'padding:6px 14px;' }, [document.createTextNode('💾 Download PNG')]);
      downloadBtn.onclick = async () => {
        try {
          const defaultName = `bloxgen-${acc.username || 'account'}-card.png`;
          const filePath = await saveDialog({
            title: 'Save BloxGen Card',
            defaultPath: defaultName,
            filters: [{ name: 'PNG Images', extensions: ['png'] }]
          });
          if (!filePath) return;
          const dataUrl = canvas.toDataURL('image/png');
          const base64Data = dataUrl.replace(/^data:image\/png;base64,/, '');
          const binaryString = atob(base64Data);
          const len = binaryString.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          await writeBinaryFile(filePath, bytes);
          toast('Card image saved successfully!', 'success');
        } catch (err) {
          console.error('Failed to save card image:', err);
          toast('Failed to save card image', 'error');
        }
      };
      return downloadBtn;
    })()
  ]);

  modal.appendChild(actionsRow);
  backdrop.appendChild(modal);
  backdrop.addEventListener('click', (e) => {
    if (e.target === backdrop) backdrop.remove();
  });
  document.body.appendChild(backdrop);
}

async function renderBloxgenView() {
  const container = document.getElementById('bloxgen-view');
  if (!container) return;

  const currentKey = state.settings.bloxgenApiKey || '';
  if (currentKey && bloxgenOverviewData.loadedKey !== currentKey) {
    await fetchBloxgenOverviewData(currentKey);
  }

  const keyInput = document.getElementById('bloxgen-key-input-header') as HTMLInputElement | null;
  const toggleKeyBtn = document.getElementById('btn-bloxgen-toggle-key-header');
  const saveKeyBtn = document.getElementById('btn-bloxgen-save-key-header');
  const refreshBtn = document.getElementById('btn-bloxgen-refresh');

  const titleWrap = container.querySelector('.bloxgen-title-wrap');
  if (titleWrap) {
    const existingRole = titleWrap.querySelector('.bloxgen-role-badge');
    if (existingRole) existingRole.remove();
    const userRole = bloxgenOverviewData.balance?.data?.role;
    if (userRole) {
      const rBadge = el('span', { class: `bloxgen-role-badge ${String(userRole).toLowerCase()}` }, [
        document.createTextNode(String(userRole).toUpperCase())
      ]);
      const titleRow = titleWrap.querySelector('div') || titleWrap;
      titleRow.appendChild(rBadge);
    }
  }

  if (keyInput) {
    keyInput.value = currentKey;
    keyInput.type = bloxgenKeyInputVisible ? 'text' : 'password';
  }

  if (toggleKeyBtn && !toggleKeyBtn.hasAttribute('data-bound')) {
    toggleKeyBtn.setAttribute('data-bound', 'true');
    toggleKeyBtn.addEventListener('click', () => {
      bloxgenKeyInputVisible = !bloxgenKeyInputVisible;
      if (keyInput) {
        keyInput.type = bloxgenKeyInputVisible ? 'text' : 'password';
      }
      toggleKeyBtn.textContent = bloxgenKeyInputVisible ? 'Hide' : 'Show';
    });
  }

  if (saveKeyBtn && !saveKeyBtn.hasAttribute('data-bound')) {
    saveKeyBtn.setAttribute('data-bound', 'true');
    saveKeyBtn.addEventListener('click', async () => {
      const val = keyInput ? keyInput.value.trim() : '';
      state.settings.bloxgenApiKey = val;
      await apiService.updateSettings({ bloxgenApiKey: val });
      toast('BloxGen API Key saved!', 'success');
      await fetchBloxgenOverviewData(val);
      renderBloxgenView();
    });
  }

  if (refreshBtn && !refreshBtn.hasAttribute('data-bound')) {
    refreshBtn.setAttribute('data-bound', 'true');
    refreshBtn.addEventListener('click', async () => {
      const k = state.settings.bloxgenApiKey || '';
      if (k) {
        toast('Refreshing BloxGen data...', 'info');
        await fetchBloxgenOverviewData(k);
        renderBloxgenView();
      } else {
        toast('Please enter and save your BloxGen API key first', 'error');
      }
    });
  }

  const tabBtns: Array<{ id: 'overview' | 'generator' | 'checker' | 'botting'; el: HTMLElement | null }> = [
    { id: 'overview', el: document.getElementById('tab-bloxgen-overview') },
    { id: 'generator', el: document.getElementById('tab-bloxgen-generator') },
    { id: 'checker', el: document.getElementById('tab-bloxgen-checker') },
    { id: 'botting', el: document.getElementById('tab-bloxgen-botting') }
  ];

  tabBtns.forEach(tab => {
    if (tab.el) {
      tab.el.className = `btn ${bloxgenActiveTab === tab.id ? 'btn-primary' : 'btn-secondary'} btn-sm`;
      if (!tab.el.hasAttribute('data-bound')) {
        tab.el.setAttribute('data-bound', 'true');
        tab.el.addEventListener('click', () => {
          bloxgenActiveTab = tab.id;
          renderBloxgenView();
        });
      }
    }
  });

  const tabContainer = document.getElementById('bloxgen-tab-container');
  if (!tabContainer) return;
  tabContainer.innerHTML = '';

  if (!currentKey) {
    const warningCard = el('div', { class: 'card', style: 'padding:24px; text-align:center; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
      el('h4', { style: 'color:#f87171; margin-top:0; font-size:16px;' }, [document.createTextNode('BloxGen API Key Required')]),
      el('p', { style: 'color:var(--text-muted); font-size:13px; margin-bottom:12px;' }, [
        document.createTextNode('Please enter your BloxGen API key in the top headerbar above and click "Save" to start generating accounts, checking cookies, and viewing stock.')
      ]),
      el('a', { href: 'https://bloxgen.net/dashboard/overview', target: '_blank', class: 'btn btn-secondary btn-sm', style: 'width:fit-content; margin:0 auto;' }, [
        document.createTextNode('Get API Key from BloxGen Dashboard ↗')
      ])
    ]);
    tabContainer.appendChild(warningCard);
    return;
  }

  if (bloxgenActiveTab === 'overview') {
    renderBloxgenOverviewTab(tabContainer);
  } else if (bloxgenActiveTab === 'generator') {
    renderBloxgenGeneratorTab(tabContainer);
  } else if (bloxgenActiveTab === 'checker') {
    renderBloxgenCheckerTab(tabContainer);
  } else if (bloxgenActiveTab === 'botting') {
    renderBloxgenBottingTab(tabContainer);
  }
}

function renderBloxgenOverviewTab(parent: HTMLElement) {
  const grid = el('div', { style: 'display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:16px;' }, []);

  const balCard = el('div', { class: 'card', style: 'padding:16px; display:flex; flex-direction:column; gap:12px; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
    el('div', { style: 'display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-soft); padding-bottom:8px;' }, [
      el('h3', { style: 'font-size:14px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('Account Balance')]),
      (() => {
        const r = bloxgenOverviewData.balance?.data?.role;
        return r
          ? el('span', { class: `bloxgen-role-badge ${String(r).toLowerCase()}` }, [document.createTextNode(String(r).toUpperCase())])
          : el('span', { style: 'font-size:11px; color:var(--muted);' }, [document.createTextNode('USD')]);
      })()
    ])
  ]);
  const balVal = bloxgenOverviewData.balance?.data?.balance;
  const balDisplay = balVal !== undefined ? `$${Number(balVal).toFixed(4)}` : (bloxgenOverviewData.balance?.message || 'Unavailable');
  balCard.appendChild(el('div', { style: 'font-size:26px; font-weight:700; color:#4ade80;' }, [document.createTextNode(balDisplay)]));
  grid.appendChild(balCard);

  const pricesCard = el('div', { class: 'card', style: 'padding:16px; display:flex; flex-direction:column; gap:12px; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
    el('div', { style: 'border-bottom:1px solid var(--border-soft); padding-bottom:8px;' }, [
      el('h3', { style: 'font-size:14px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('Account Pricing')])
    ])
  ]);
  const pricesList = el('div', { style: 'display:flex; flex-direction:column; gap:6px;' }, []);
  const pricesObj = bloxgenOverviewData.prices?.data || {};
  if (Object.keys(pricesObj).length > 0) {
    Object.entries(pricesObj).forEach(([type, cost]) => {
      const item = el('div', { class: 'bloxgen-stock-item' }, [
        el('span', { style: 'font-weight:500; color:var(--fg);' }, [document.createTextNode(type)]),
        el('span', { style: 'color:#4ade80; font-weight:600;' }, [document.createTextNode(`$${cost}`)])
      ]);
      pricesList.appendChild(item);
    });
  } else {
    pricesList.appendChild(el('div', { style: 'color:var(--muted); font-size:12px;' }, [document.createTextNode('No pricing details.')]));
  }
  pricesCard.appendChild(pricesList);
  grid.appendChild(pricesCard);

  const limitCard = el('div', { class: 'card', style: 'padding:16px; display:flex; flex-direction:column; gap:12px; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
    el('div', { style: 'border-bottom:1px solid var(--border-soft); padding-bottom:8px;' }, [
      el('h3', { style: 'font-size:14px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('Daily Limits')])
    ])
  ]);
  const limitList = el('div', { style: 'display:flex; flex-direction:column; gap:6px;' }, []);
  const limitData = bloxgenOverviewData.dailyLimit?.data;
  if (limitData) {
    if (Array.isArray(limitData.accountTypes) && limitData.accountTypes.length > 0) {
      limitData.accountTypes.forEach((info: any) => {
        const item = el('div', { class: 'bloxgen-stock-item' }, [
          el('span', { style: 'color:var(--fg); font-weight:500;' }, [document.createTextNode(info.accountType)]),
          el('span', { style: 'font-size:11px; color:var(--text-muted);' }, [
            document.createTextNode(`Used: ${info.generationsToday ?? 0} / Limit: ${info.dailyLimit === -1 ? '∞' : (info.dailyLimit ?? '∞')}`)
          ])
        ]);
        limitList.appendChild(item);
      });
    } else if (limitData.accountTypeLimits && typeof limitData.accountTypeLimits === 'object') {
      Object.entries(limitData.accountTypeLimits).forEach(([type, cap]: [string, any]) => {
        const item = el('div', { class: 'bloxgen-stock-item' }, [
          el('span', { style: 'color:var(--fg);' }, [document.createTextNode(type)]),
          el('span', { style: 'font-size:11px; color:var(--text-muted);' }, [
            document.createTextNode(`Daily Cap: ${cap === -1 ? '∞' : cap}`)
          ])
        ]);
        limitList.appendChild(item);
      });
    } else if (limitData.dailyLimit !== undefined) {
      limitList.appendChild(el('div', { class: 'bloxgen-stock-item' }, [
        el('span', { style: 'color:var(--fg);' }, [document.createTextNode('General Limit')]),
        el('span', { style: 'color:var(--text-muted);' }, [document.createTextNode(`${limitData.generationsToday || 0} / ${limitData.dailyLimit === -1 ? '∞' : limitData.dailyLimit}`)])
      ]));
    }
  } else {
    limitList.appendChild(el('div', { style: 'color:var(--muted); font-size:12px;' }, [document.createTextNode('Limits unavailable.')]));
  }
  limitCard.appendChild(limitList);
  grid.appendChild(limitCard);

  parent.appendChild(grid);

  const stockCard = el('div', { class: 'card', style: 'padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
    el('div', { style: 'border-bottom:1px solid var(--border-soft); padding-bottom:12px;' }, [
      el('h3', { style: 'font-size:15px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('Stock Availability & In-Stock Regions')])
    ])
  ]);
  const stockList = el('div', { style: 'display:flex; flex-direction:column; gap:8px;' }, []);
  const stockObj = bloxgenOverviewData.stock?.data || {};
  if (Object.keys(stockObj).length > 0) {
    Object.entries(stockObj).forEach(([type, info]: [string, any]) => {
      const isAvail = info.available === true;
      let regionsSummary = 'Global / Standard';
      if (Array.isArray(info.regions) && info.regions.length > 0) {
        regionsSummary = info.regions.join(', ');
      }
      if (info.continents && typeof info.continents === 'object') {
        const cNames = Object.keys(info.continents);
        if (cNames.length > 0) {
          regionsSummary += ` • Continents: ${cNames.join(', ')}`;
        }
      }
      const item = el('div', { class: 'bloxgen-stock-item' }, [
        el('div', { style: 'display:flex; align-items:center; gap:8px;' }, [
          el('span', { class: `bloxgen-tag ${isAvail ? 'in-stock' : 'out-stock'}` }, [
            document.createTextNode(isAvail ? 'IN STOCK' : 'OUT OF STOCK')
          ]),
          el('b', { style: 'color:var(--text-bright);' }, [document.createTextNode(type)])
        ]),
        el('span', { style: 'color:var(--muted); font-size:12px;' }, [document.createTextNode(regionsSummary)])
      ]);
      stockList.appendChild(item);
    });
  } else {
    stockList.appendChild(el('div', { style: 'color:var(--muted); font-size:12px;' }, [document.createTextNode('Stock details unavailable.')]));
  }
  stockCard.appendChild(stockList);
  parent.appendChild(stockCard);
}

function renderBloxgenGeneratorTab(parent: HTMLElement) {
  const layout = el('div', { style: 'display:grid; grid-template-columns:330px 1fr; gap:20px;' }, []);

  const formCard = el('div', { class: 'card', style: 'padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
    el('div', { style: 'border-bottom:1px solid var(--border-soft); padding-bottom:12px;' }, [
      el('h3', { style: 'font-size:15px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('Generator Setup')])
    ])
  ]);

  const typeGroup = el('div', { class: 'form-group', style: 'display:flex; flex-direction:column; gap:6px;' }, [
    el('label', { style: 'font-size:12px; font-weight:600; color:var(--muted);' }, [document.createTextNode('Account Type')]),
    (() => {
      const select = el('select', { id: 'bloxgen-gen-type', class: 'form-control', style: 'background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;' }, []) as HTMLSelectElement;
      const options = ['alt', '+30 days old', '+1 year old', '5+ years old', 'dump', '18+ age verified'];
      options.forEach(opt => {
        const o = el('option', { value: opt }, [document.createTextNode(opt)]) as HTMLOptionElement;
        if (opt === bloxgenSelectedType) o.selected = true;
        select.appendChild(o);
      });
      select.addEventListener('change', (e) => {
        bloxgenSelectedType = (e.target as HTMLSelectElement).value;
        updateTargetDropdownOptions();
      });
      return select;
    })()
  ]);
  formCard.appendChild(typeGroup);

  const targetSelect = el('select', { id: 'bloxgen-gen-target', class: 'form-control', style: 'background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;' }, []) as HTMLSelectElement;

  const updateTargetDropdownOptions = () => {
    targetSelect.innerHTML = '';
    const defOpt = el('option', { value: '' }, [document.createTextNode('Any Region / Continent (Default)')]) as HTMLOptionElement;
    if (bloxgenSelectedTarget === '') defOpt.selected = true;
    targetSelect.appendChild(defOpt);

    const stockInfo = bloxgenOverviewData.stock?.data?.[bloxgenSelectedType] || {};
    const inStockRegions: string[] = Array.isArray(stockInfo.regions) ? stockInfo.regions : [];
    const inStockContinents: Record<string, string[]> = stockInfo.continents || {};

    const contGroup = document.createElement('optgroup');
    contGroup.label = 'Continents (Ultra Plan)';
    const continents = [
      { slug: 'europe', label: '🇪🇺 Europe (Whole Continent)' },
      { slug: 'north-america', label: '🇺🇸 North America (Whole Continent)' },
      { slug: 'asia', label: '🌏 Asia (Whole Continent)' },
      { slug: 'south-america', label: '🌎 South America (Whole Continent)' },
      { slug: 'africa', label: '🌍 Africa (Whole Continent)' },
      { slug: 'oceania', label: '🇦🇺 Oceania (Whole Continent)' },
      { slug: 'antarctica', label: '❄️ Antarctica' }
    ];

    continents.forEach(c => {
      const val = `continent:${c.slug}`;
      const isStocked = !!inStockContinents[c.slug];
      const opt = el('option', { value: val }, [
        document.createTextNode(`${c.label}${isStocked ? ' ✓ in stock' : ''}`)
      ]) as HTMLOptionElement;
      if (val === bloxgenSelectedTarget) opt.selected = true;
      contGroup.appendChild(opt);
    });
    targetSelect.appendChild(contGroup);

    const countryGroup = document.createElement('optgroup');
    countryGroup.label = 'Specific Countries (Ultra Plan)';
    const defaultCountries = [
      { code: 'US', name: 'United States' },
      { code: 'GB', name: 'United Kingdom' },
      { code: 'DE', name: 'Germany' },
      { code: 'CA', name: 'Canada' },
      { code: 'FR', name: 'France' },
      { code: 'AU', name: 'Australia' },
      { code: 'BR', name: 'Brazil' },
      { code: 'JP', name: 'Japan' },
      { code: 'NL', name: 'Netherlands' }
    ];

    const allCountryCodes = new Set(defaultCountries.map(c => c.code));
    inStockRegions.forEach(r => allCountryCodes.add(r));

    Array.from(allCountryCodes).forEach(code => {
      const known = defaultCountries.find(c => c.code === code);
      const name = known ? known.name : code;
      const isStocked = inStockRegions.includes(code);
      const val = `region:${code}`;
      const opt = el('option', { value: val }, [
        document.createTextNode(`${name} (${code})${isStocked ? ' ✓ in stock' : ''}`)
      ]) as HTMLOptionElement;
      if (val === bloxgenSelectedTarget) opt.selected = true;
      countryGroup.appendChild(opt);
    });
    targetSelect.appendChild(countryGroup);
  };

  targetSelect.addEventListener('change', (e) => {
    bloxgenSelectedTarget = (e.target as HTMLSelectElement).value;
  });
  updateTargetDropdownOptions();

  const regionGroup = el('div', { class: 'form-group', style: 'display:flex; flex-direction:column; gap:6px;' }, [
    el('label', { style: 'font-size:12px; font-weight:600; color:var(--muted);' }, [document.createTextNode('Region / Continent Target (Ultra)')]),
    targetSelect
  ]);
  formCard.appendChild(regionGroup);

  const targetGroupGroup = el('div', { class: 'form-group', style: 'display:flex; flex-direction:column; gap:6px;' }, [
    el('label', { style: 'font-size:12px; font-weight:600; color:var(--muted);' }, [document.createTextNode('FRAM Account Group')]),
    (() => {
      const input = el('input', {
        id: 'bloxgen-gen-group',
        class: 'form-control',
        value: state.settings.bloxgenDefaultGroup || 'BloxGen',
        placeholder: 'e.g. BloxGen, Alts, Farming',
        style: 'background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;'
      }, []) as HTMLInputElement;
      input.addEventListener('change', (e) => {
        const val = (e.target as HTMLInputElement).value.trim();
        state.settings.bloxgenDefaultGroup = val;
        updateSetting('bloxgenDefaultGroup', val).catch(() => { });
      });
      return input;
    })()
  ]);
  formCard.appendChild(targetGroupGroup);

  const autoAddCheck = el('label', { style: 'display:flex; align-items:center; gap:8px; cursor:pointer; font-size:12px; color:var(--fg);' }, [
    (() => {
      const chk = el('input', { type: 'checkbox', id: 'bloxgen-gen-autoadd' }, []) as HTMLInputElement;
      chk.checked = state.settings.bloxgenAutoAddAccounts !== false;
      chk.addEventListener('change', (e) => {
        const val = (e.target as HTMLInputElement).checked;
        state.settings.bloxgenAutoAddAccounts = val;
        updateSetting('bloxgenAutoAddAccounts', val).catch(() => { });
      });
      return chk;
    })(),
    document.createTextNode('Auto-add generated account to FRAM list')
  ]);
  formCard.appendChild(autoAddCheck);

  const genBtn = el('button', { class: 'btn btn-primary', type: 'button', style: 'margin-top:6px;' }, [
    document.createTextNode('Generate Account Now')
  ]) as HTMLButtonElement;

  genBtn.addEventListener('click', async () => {
    const apiKey = state.settings.bloxgenApiKey || '';
    if (!apiKey) {
      toast('API Key is required to generate accounts', 'error');
      return;
    }
    const typeSelect = document.getElementById('bloxgen-gen-type') as HTMLSelectElement | null;
    const groupInput = document.getElementById('bloxgen-gen-group') as HTMLInputElement | null;
    const autoAddInput = document.getElementById('bloxgen-gen-autoadd') as HTMLInputElement | null;

    const accType = typeSelect?.value || bloxgenSelectedType || 'alt';
    const group = (groupInput?.value || state.settings.bloxgenDefaultGroup || 'BloxGen').trim();
    const shouldAutoAdd = autoAddInput ? autoAddInput.checked : (state.settings.bloxgenAutoAddAccounts !== false);

    let regionParam: string | undefined = undefined;
    let continentParam: string | undefined = undefined;
    if (bloxgenSelectedTarget.startsWith('continent:')) {
      continentParam = bloxgenSelectedTarget.replace('continent:', '');
    } else if (bloxgenSelectedTarget.startsWith('region:')) {
      regionParam = bloxgenSelectedTarget.replace('region:', '');
    } else if (bloxgenSelectedTarget) {
      regionParam = bloxgenSelectedTarget;
    }

    genBtn.disabled = true;
    genBtn.textContent = 'Generating account...';
    try {
      const res = await apiService.generateBloxgenAccount(apiKey, accType, regionParam, continentParam);
      if (res && res.success && (res.data || res.account || res.username)) {
        const raw = res.data || res.account || res;
        const username = raw.username || raw.name || raw.user || '';
        const password = raw.password || raw.pass || '';
        const cookie = raw.cookie || raw.roblosecurity || raw['.ROBLOSECURITY'] || raw.roblosecurity_cookie || '';
        const itemType = raw.type || accType || 'alt';
        const itemRegion = raw.region || regionParam || (continentParam ? continentParam.toUpperCase() : 'Global');
        const cost = raw.cost !== undefined ? raw.cost : 0;
        const id = raw.id || raw.userId || raw.user_id || '';
        const avatarUrl = raw.avatarUrl || raw.avatar_url || '';
        const fullAvatarUrl = raw.fullAvatarUrl || raw.full_avatar_url || avatarUrl;
        const emailVerified = raw.email_verified === true;
        const ageVerified = raw.age_verified === true || itemType === '18+ age verified';
        const estimatedAge = raw.estimated_age;
        const estimatedAgeGroup = raw.estimated_age_group;
        const robux = raw.robux;
        const rap = raw.rap;
        const summary = raw.summary;

        let addedToFram = false;
        if (shouldAutoAdd && (username || cookie)) {
          try {
            const created = await apiService.createAccount({
              username: username || 'BloxGen_Account',
              password: password,
              cookie: cookie,
              group: group,
              note: `BloxGen (${itemType}) - ${itemRegion}`
            });
            addedToFram = true;
            toast(`Auto-added ${username || 'account'} under '${group}'`, 'success');
            await refreshAccountList(created?.id);
          } catch (e) {
            console.error('Failed to auto-add account to FRAM', e);
            toast('Failed to auto-add account to FRAM database', 'error');
          }
        }

        const generatedItem = {
          username,
          password,
          cookie,
          id,
          type: itemType,
          region: itemRegion,
          cost,
          avatarUrl,
          fullAvatarUrl,
          email_verified: emailVerified,
          age_verified: ageVerified,
          estimated_age: estimatedAge,
          estimated_age_group: estimatedAgeGroup,
          robux,
          rap,
          summary,
          addedToFram,
          timestamp: new Date().toLocaleString()
        };

        bloxgenLastGeneratedAccount = generatedItem;
        bloxgenHistory.unshift(generatedItem);
        saveBloxgenStoredData();

        toast(`Account generated: ${username || 'Success'}`, 'success');
        await fetchBloxgenOverviewData(apiKey);
        renderBloxgenView();
      } else {
        const msg = res?.message || res?.error || 'Failed to generate account';
        toast(`Generation error: ${msg}`, 'error');
      }
    } catch (err: any) {
      toast(`Generation failed: ${err?.message || err}`, 'error');
    } finally {
      genBtn.disabled = false;
      genBtn.textContent = 'Generate Account Now';
    }
  });

  formCard.appendChild(genBtn);
  layout.appendChild(formCard);

  const rightCol = el('div', { style: 'display:flex; flex-direction:column; gap:20px;' }, []);

  if (bloxgenLastGeneratedAccount) {
    const acc = bloxgenLastGeneratedAccount;
    const resCard = el('div', { class: 'card', style: 'padding:20px; display:flex; flex-direction:column; gap:14px; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
      el('div', { style: 'display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-soft); padding-bottom:10px;' }, [
        el('h4', { style: 'margin:0; color:#4ade80; font-size:15px; font-weight:700;' }, [document.createTextNode('Newly Generated Account')]),
        el('div', { style: 'display:flex; align-items:center; gap:6px;' }, [
          (() => {
            const flexBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px; font-size:11px;' }, [document.createTextNode('🏆 Flex Card')]);
            flexBtn.onclick = () => openBloxgenFlexCardModal(acc);
            return flexBtn;
          })(),
          acc.addedToFram
            ? el('span', { class: 'bloxgen-tag in-stock', style: 'font-size:11px;' }, [document.createTextNode('In FRAM List')])
            : (() => {
              const addBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px; font-size:11px;' }, [document.createTextNode('+ Add to FRAM')]) as HTMLButtonElement;
              addBtn.onclick = async () => {
                addBtn.disabled = true;
                try {
                  const grp = state.settings.bloxgenDefaultGroup || 'BloxGen';
                  const created = await apiService.createAccount({
                    username: acc.username || 'BloxGen_Account',
                    password: acc.password || '',
                    cookie: acc.cookie || '',
                    group: grp,
                    note: `BloxGen (${acc.type}) - ${acc.region || 'Global'}`
                  });
                  acc.addedToFram = true;
                  saveBloxgenStoredData();
                  toast(`Added ${acc.username} to FRAM under '${grp}'`, 'success');
                  await refreshAccountList(created?.id);
                  renderBloxgenView();
                } catch (err) {
                  toast('Failed to add account to FRAM', 'error');
                  addBtn.disabled = false;
                }
              };
              return addBtn;
            })(),
          el('span', { class: 'bloxgen-tag in-stock' }, [document.createTextNode(acc.type || 'Account')])
        ])
      ])
    ]);

    const gridRow = el('div', { style: 'display:flex; gap:16px; align-items:flex-start;' }, []);
    const imgUrl = acc.avatarUrl || acc.fullAvatarUrl || '/app-logo.png';
    const avatar = el('img', { src: imgUrl, style: 'width:64px; height:64px; border-radius:8px; background:var(--bg-2); border:1px solid var(--border); object-fit:cover;', alt: 'Avatar' }, []);
    gridRow.appendChild(avatar);

    const detailsCol = el('div', { style: 'display:flex; flex-direction:column; gap:6px; flex:1;' }, [
      el('div', { style: 'font-weight:700; font-size:16px; color:var(--text-bright);' }, [document.createTextNode(acc.username)]),
      el('div', { style: 'font-size:12px; color:var(--text-muted);' }, [
        document.createTextNode(`ID: ${acc.id || 'N/A'} | Region: ${acc.region || 'Any'} | Cost: $${acc.cost || 0} | ${acc.timestamp || ''}`)
      ]),
      (() => {
        const badgesWrap = el('div', { style: 'display:flex; gap:6px; flex-wrap:wrap; margin-top:2px;' }, []);
        if (acc.age_verified || acc.type === '18+ age verified') {
          badgesWrap.appendChild(el('span', { class: 'bloxgen-tag age18' }, [document.createTextNode('🔞 18+ Age Verified')]));
        }
        if (acc.email_verified) {
          badgesWrap.appendChild(el('span', { class: 'bloxgen-tag verified' }, [document.createTextNode('✉️ Email Verified')]));
        }
        if (acc.estimated_age_group || acc.estimated_age) {
          badgesWrap.appendChild(el('span', { class: 'bloxgen-tag', style: 'background:var(--bg-3); color:var(--fg);' }, [
            document.createTextNode(`Est. Age: ${acc.estimated_age_group || acc.estimated_age}`)
          ]));
        }
        if (acc.robux !== undefined || acc.rap !== undefined) {
          badgesWrap.appendChild(el('span', { class: 'bloxgen-tag robux' }, [
            document.createTextNode(`🪙 R$ ${acc.robux ?? 0} | RAP: ${acc.rap ?? 0}`)
          ]));
        }
        return badgesWrap;
      })()
    ]);
    gridRow.appendChild(detailsCol);
    resCard.appendChild(gridRow);

    if (acc.summary) {
      const summaryBox = el('div', { style: 'font-size:12px; color:var(--text-muted); background:var(--bg-3); padding:6px 10px; border-radius:6px; border-left:3px solid var(--primary);' }, [
        document.createTextNode(`"${acc.summary}"`)
      ]);
      resCard.appendChild(summaryBox);
    }

    const credRowUser = el('div', { class: 'bloxgen-credential-row' }, [
      el('span', {}, [document.createTextNode(`Username: ${acc.username}`)]),
      (() => {
        const b = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px; font-size:11px;' }, [document.createTextNode('Copy Username')]);
        b.addEventListener('click', () => { navigator.clipboard.writeText(acc.username); toast('Username copied', 'info'); });
        return b;
      })()
    ]);
    resCard.appendChild(credRowUser);

    if (acc.password) {
      const credRowPass = el('div', { class: 'bloxgen-credential-row' }, [
        el('span', {}, [document.createTextNode(`Password: ${acc.password}`)]),
        (() => {
          const b = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px; font-size:11px;' }, [document.createTextNode('Copy Password')]);
          b.addEventListener('click', () => { navigator.clipboard.writeText(acc.password); toast('Password copied', 'info'); });
          return b;
        })()
      ]);
      resCard.appendChild(credRowPass);
    }

    if (acc.cookie) {
      const credRowCookie = el('div', { class: 'bloxgen-credential-row' }, [
        el('span', { style: 'overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:320px;' }, [document.createTextNode(`Cookie: ${acc.cookie}`)]),
        (() => {
          const b = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px; font-size:11px;' }, [document.createTextNode('Copy Cookie')]);
          b.addEventListener('click', () => { navigator.clipboard.writeText(acc.cookie); toast('Cookie copied', 'info'); });
          return b;
        })()
      ]);
      resCard.appendChild(credRowCookie);
    }

    rightCol.appendChild(resCard);
  }

  const histCard = el('div', { class: 'card', style: 'padding:20px; display:flex; flex-direction:column; gap:12px; background:var(--card); border:1px solid var(--border); border-radius:8px;' }, [
    el('div', { style: 'display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border-soft); padding-bottom:10px;' }, [
      el('h3', { style: 'font-size:15px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode(`Recent Generations (${bloxgenHistory.length})`)]),
      bloxgenHistory.length > 0
        ? (() => {
          const clrBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px; font-size:11px;' }, [document.createTextNode('Clear History')]);
          clrBtn.onclick = () => {
            bloxgenHistory = [];
            bloxgenLastGeneratedAccount = null;
            saveBloxgenStoredData();
            renderBloxgenView();
            toast('Recent generations history cleared', 'info');
          };
          return clrBtn;
        })()
        : el('span', {}, [])
    ])
  ]);

  if (bloxgenHistory.length > 0) {
    const list = el('div', { style: 'display:flex; flex-direction:column; gap:10px; max-height:480px; overflow-y:auto; padding-right:4px;' }, []);
    bloxgenHistory.forEach((item) => {
      const row = el('div', {
        class: 'bloxgen-stock-item',
        style: 'flex-direction:column; align-items:stretch; gap:8px; padding:10px 12px;'
      }, []);

      const topRow = el('div', { style: 'display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;' }, [
        el('div', { style: 'display:flex; align-items:center; gap:6px; flex-wrap:wrap;' }, [
          el('b', { style: 'color:var(--text-bright); font-size:13px;' }, [document.createTextNode(item.username || 'Unknown')]),
          el('span', { class: 'bloxgen-tag in-stock', style: 'font-size:10px;' }, [document.createTextNode(item.type || 'alt')]),
          item.region ? el('span', { class: 'bloxgen-tag', style: 'font-size:10px; background:var(--bg-3); color:var(--fg);' }, [document.createTextNode(item.region)]) : el('span', {}, []),
          (item.age_verified || item.type === '18+ age verified') ? el('span', { class: 'bloxgen-tag age18', style: 'font-size:10px;' }, [document.createTextNode('🔞 18+ Age')]) : el('span', {}, []),
          item.email_verified ? el('span', { class: 'bloxgen-tag verified', style: 'font-size:10px;' }, [document.createTextNode('✉️ Verified')]) : el('span', {}, []),
          (item.robux || item.rap) ? el('span', { class: 'bloxgen-tag robux', style: 'font-size:10px;' }, [document.createTextNode(`R$ ${item.robux ?? 0}`)]) : el('span', {}, []),
          item.addedToFram
            ? el('span', { class: 'bloxgen-tag in-stock', style: 'font-size:10px;' }, [document.createTextNode('In FRAM')])
            : (() => {
              const addBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:1px 6px; font-size:10px;' }, [document.createTextNode('+ Add to FRAM')]) as HTMLButtonElement;
              addBtn.onclick = async (e) => {
                e.stopPropagation();
                addBtn.disabled = true;
                try {
                  const grp = state.settings.bloxgenDefaultGroup || 'BloxGen';
                  const created = await apiService.createAccount({
                    username: item.username || 'BloxGen_Account',
                    password: item.password || '',
                    cookie: item.cookie || '',
                    group: grp,
                    note: `BloxGen (${item.type}) - ${item.region || 'Global'}`
                  });
                  item.addedToFram = true;
                  saveBloxgenStoredData();
                  toast(`Added ${item.username} to FRAM under '${grp}'`, 'success');
                  await refreshAccountList(created?.id);
                  renderBloxgenView();
                } catch (err) {
                  toast('Failed to add account to FRAM', 'error');
                  addBtn.disabled = false;
                }
              };
              return addBtn;
            })()
        ]),
        el('div', { style: 'display:flex; align-items:center; gap:8px;' }, [
          (() => {
            const fBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:1px 6px; font-size:10px;' }, [document.createTextNode('🏆 Flex')]);
            fBtn.onclick = (e) => { e.stopPropagation(); openBloxgenFlexCardModal(item); };
            return fBtn;
          })(),
          el('span', { style: 'color:var(--muted); font-size:11px;' }, [document.createTextNode(item.timestamp || '')])
        ])
      ]);
      row.appendChild(topRow);

      const actRow = el('div', { style: 'display:flex; gap:6px; align-items:center; flex-wrap:wrap;' }, []);
      if (item.username) {
        const uBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 6px; font-size:10px;' }, [document.createTextNode('Copy User')]);
        uBtn.onclick = () => { navigator.clipboard.writeText(item.username); toast('Username copied', 'info'); };
        actRow.appendChild(uBtn);
      }
      if (item.password) {
        const pBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 6px; font-size:10px;' }, [document.createTextNode('Copy Pass')]);
        pBtn.onclick = () => { navigator.clipboard.writeText(item.password); toast('Password copied', 'info'); };
        actRow.appendChild(pBtn);
      }
      if (item.cookie) {
        const cBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 6px; font-size:10px;' }, [document.createTextNode('Copy Cookie')]);
        cBtn.onclick = () => { navigator.clipboard.writeText(item.cookie); toast('Cookie copied', 'info'); };
        actRow.appendChild(cBtn);
      }
      if (actRow.childNodes.length > 0) {
        row.appendChild(actRow);
      }

      list.appendChild(row);
    });
    histCard.appendChild(list);
  } else {
    histCard.appendChild(el('div', { style: 'color:var(--muted); font-size:12px;' }, [document.createTextNode('No generated accounts saved yet.')]));
  }
  rightCol.appendChild(histCard);

  layout.appendChild(rightCol);
  parent.appendChild(layout);
}

function renderBloxgenCheckerTab(parent: HTMLElement) {
  const card = el('div', { class: 'card', style: 'padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px; max-width:680px;' }, [
    el('div', { style: 'border-bottom:1px solid var(--border-soft); padding-bottom:12px; display:flex; justify-content:space-between; align-items:center;' }, [
      el('h3', { style: 'font-size:15px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('BloxGen Cookie Validator')]),
      el('span', { class: 'bloxgen-tag verified' }, [document.createTextNode('Decrypted Snapshot & FRAM Sync')])
    ])
  ]);

  const cookieInputGroup = el('div', { class: 'form-group', style: 'display:flex; flex-direction:column; gap:6px;' }, [
    el('label', { style: 'font-size:12px; font-weight:600; color:var(--muted);' }, [document.createTextNode('.ROBLOSECURITY Cookie')]),
    el('textarea', { id: 'bloxgen-check-cookie-input', class: 'form-control', rows: '3', placeholder: '_|WARNING:-DO-NOT-SHARE-THIS.--...', style: 'background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px; font-family:monospace;' }, [])
  ]);
  card.appendChild(cookieInputGroup);

  const checkBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [document.createTextNode('Validate Cookie Now')]) as HTMLButtonElement;
  const resultWrap = el('div', { id: 'bloxgen-checker-result-wrap', style: 'margin-top:10px;' }, []);

  checkBtn.addEventListener('click', async () => {
    const apiKey = state.settings.bloxgenApiKey || '';
    const cookieInput = document.getElementById('bloxgen-check-cookie-input') as HTMLTextAreaElement | null;
    const cookie = cookieInput?.value.trim() || '';
    if (!cookie) {
      toast('Please enter a cookie to check', 'error');
      return;
    }
    checkBtn.disabled = true;
    checkBtn.textContent = 'Checking cookie...';
    try {
      const res = await apiService.checkBloxgenSingleCookie(apiKey, cookie);
      resultWrap.innerHTML = '';
      if (res && res.success && res.data) {
        const d = res.data;
        const sr = d.singleResult || {};
        const isValid = sr.status === 'valid' || d.status === 'completed' || d.results?.valid === 1;

        if (isValid) {
          const username = sr.username || d.username || 'Roblox User';
          const userId = sr.user_id || d.id || d.user_id || 'N/A';
          const displayName = sr.display_name || sr.displayName || '';
          const joinDate = sr.join_date || (sr.year ? `Year ${sr.year}` : '');

          const resBox = el('div', { class: 'bloxgen-credential-row', style: 'flex-direction:column; align-items:flex-start; gap:8px; padding:14px;' }, [
            el('div', { style: 'display:flex; justify-content:space-between; width:100%; align-items:center;' }, [
              el('div', { style: 'color:#4ade80; font-weight:700; font-size:14px;' }, [document.createTextNode('✓ VALID COOKIE')]),
              (() => {
                const addFramBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:3px 10px; font-size:11px;' }, [document.createTextNode('+ Add to FRAM')]) as HTMLButtonElement;
                addFramBtn.onclick = async () => {
                  addFramBtn.disabled = true;
                  try {
                    const grp = state.settings.bloxgenDefaultGroup || 'BloxGen';
                    const created = await apiService.createAccount({
                      username: username,
                      password: '',
                      cookie: cookie,
                      group: grp,
                      note: `Validated Cookie (ID: ${userId})`
                    });
                    toast(`Added ${username} to FRAM list under '${grp}'`, 'success');
                    await refreshAccountList(created?.id);
                  } catch (e) {
                    toast('Failed to add account to FRAM', 'error');
                    addFramBtn.disabled = false;
                  }
                };
                return addFramBtn;
              })()
            ]),
            el('div', { style: 'display:grid; grid-template-columns:1fr 1fr; gap:8px; width:100%; margin-top:4px;' }, [
              el('div', {}, [el('b', {}, [document.createTextNode('Username: ')]), document.createTextNode(username)]),
              el('div', {}, [el('b', {}, [document.createTextNode('Display Name: ')]), document.createTextNode(displayName || 'None')]),
              el('div', {}, [el('b', {}, [document.createTextNode('Roblox User ID: ')]), document.createTextNode(String(userId))]),
              el('div', {}, [el('b', {}, [document.createTextNode('Joined: ')]), document.createTextNode(joinDate || 'N/A')])
            ]),
            (() => {
              const copyCBtn = el('button', { class: 'btn btn-secondary btn-sm', style: 'padding:2px 8px; font-size:11px; margin-top:4px;' }, [document.createTextNode('Copy Cookie')]);
              copyCBtn.onclick = () => { navigator.clipboard.writeText(cookie); toast('Cookie copied', 'info'); };
              return copyCBtn;
            })()
          ]);
          resultWrap.appendChild(resBox);
        } else {
          const reason = sr.reason || sr.error || res.message || 'Invalid or expired cookie';
          resultWrap.appendChild(el('div', { style: 'color:#f87171; font-weight:600; padding:10px; background:rgba(248,113,113,0.1); border-radius:6px;' }, [
            document.createTextNode(`❌ Validation Failed: ${reason}`)
          ]));
        }
      } else {
        const msg = res?.message || 'Invalid or expired cookie';
        resultWrap.appendChild(el('div', { style: 'color:#f87171; font-weight:600; padding:10px; background:rgba(248,113,113,0.1); border-radius:6px;' }, [
          document.createTextNode(`❌ ${msg}`)
        ]));
      }
    } catch (err: any) {
      toast(`Checker error: ${err?.message || err}`, 'error');
    } finally {
      checkBtn.disabled = false;
      checkBtn.textContent = 'Validate Cookie Now';
    }
  });

  card.appendChild(checkBtn);
  card.appendChild(resultWrap);
  parent.appendChild(card);
}

function renderBloxgenBottingTab(parent: HTMLElement) {
  const apiKey = state.settings.bloxgenApiKey || '';
  const card = el('div', { class: 'card', style: 'padding:20px; display:flex; flex-direction:column; gap:16px; background:var(--card); border:1px solid var(--border); border-radius:8px; max-width:640px;' }, [
    el('div', { style: 'border-bottom:1px solid var(--border-soft); padding-bottom:12px;' }, [
      el('h3', { style: 'font-size:15px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('Social Growth / Roblox Followers')])
    ])
  ]);

  const pricingBox = el('div', { id: 'bloxgen-botting-pricing-box', style: 'padding:12px; border-radius:6px; background:var(--bg-2); border:1px solid var(--border); font-size:12px; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center;' }, [
    el('div', { id: 'bloxgen-pricing-text' }, [document.createTextNode('Loading live botting pricing & balance...')]),
    el('button', { class: 'btn btn-secondary btn-sm', style: 'font-size:11px; padding:3px 8px;' }, [document.createTextNode('Refresh')])
  ]);
  const refreshPricingBtn = pricingBox.querySelector('button');
  const loadPricing = async () => {
    if (!apiKey) {
      const pText = document.getElementById('bloxgen-pricing-text');
      if (pText) pText.textContent = 'API key required to fetch live pricing and order history.';
      return;
    }
    try {
      const res = await apiService.getBloxgenBottingPricing(apiKey);
      const pText = document.getElementById('bloxgen-pricing-text');
      if (pText && res) {
        if (res.success && res.pricing) {
          const p = res.pricing;
          const rate = p.rate || p.price_per_100 || 'Standard';
          const min = p.min || 10;
          const max = p.max || 10000;
          pText.textContent = `Followers Rate: ${rate} credits/100 • Min: ${min} • Max: ${max}`;
        } else if (res.message) {
          pText.textContent = `Pricing: ${res.message}`;
        }
      }
    } catch (_) {
      const pText = document.getElementById('bloxgen-pricing-text');
      if (pText) pText.textContent = 'Standard Followers Rate: 100 followers per order';
    }
  };
  refreshPricingBtn?.addEventListener('click', loadPricing);
  card.appendChild(pricingBox);
  setTimeout(loadPricing, 50);

  const targetGroup = el('div', { class: 'form-group', style: 'display:flex; flex-direction:column; gap:6px;' }, [
    el('label', { style: 'font-size:12px; font-weight:600; color:var(--muted);' }, [document.createTextNode('Target Roblox Username or User ID')]),
    el('div', { style: 'display:flex; gap:8px;' }, [])
  ]);
  const targetInputWrap = targetGroup.querySelector('div') as HTMLElement;
  const targetInput = el('input', { id: 'bloxgen-bot-target', class: 'form-control', placeholder: 'e.g. RobloxUser123', style: 'background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px; flex:1;' }, []) as HTMLInputElement;
  const verifyTargetBtn = el('button', { class: 'btn btn-secondary', type: 'button', style: 'font-size:12px; flex-shrink:0;' }, [document.createTextNode('Verify Account')]) as HTMLButtonElement;
  const verifyResult = el('div', { id: 'bloxgen-target-verify-result', style: 'font-size:11.5px; margin-top:2px;' }, []);
  targetInputWrap.appendChild(targetInput);
  targetInputWrap.appendChild(verifyTargetBtn);
  targetGroup.appendChild(verifyResult);
  card.appendChild(targetGroup);

  verifyTargetBtn.addEventListener('click', async () => {
    const currentApiKey = state.settings.bloxgenApiKey || '';
    const target = targetInput.value.trim();
    if (!target) {
      toast('Enter a username or user ID to verify first', 'error');
      return;
    }
    verifyTargetBtn.disabled = true;
    verifyTargetBtn.textContent = 'Checking...';
    verifyResult.innerHTML = '';
    try {
      const res = await apiService.checkBloxgenBottingAccount(currentApiKey, target);
      if (res && res.success) {
        const d = res.data || res.account || {};
        verifyResult.style.color = '#4ade80';
        verifyResult.textContent = `✓ Valid target account: @${d.username || target} (User ID: ${d.id || d.user_id || 'Verified'}, Followers: ${d.followers_count ?? 'N/A'})`;
      } else {
        verifyResult.style.color = '#f87171';
        verifyResult.textContent = `❌ ${res?.message || 'Target account could not be resolved on Roblox'}`;
      }
    } catch (err: any) {
      verifyResult.style.color = '#f87171';
      verifyResult.textContent = `❌ Check failed: ${err?.message || err}`;
    } finally {
      verifyTargetBtn.disabled = false;
      verifyTargetBtn.textContent = 'Verify Account';
    }
  });

  const amountGroup = el('div', { class: 'form-group', style: 'display:flex; flex-direction:column; gap:6px;' }, [
    el('label', { style: 'font-size:12px; font-weight:600; color:var(--muted);' }, [document.createTextNode('Followers Amount')]),
    el('input', { id: 'bloxgen-bot-amount', class: 'form-control', type: 'number', value: '100', min: '10', style: 'background:var(--bg-2); border:1px solid var(--border); padding:8px 12px; border-radius:6px; color:var(--fg); font-size:13px;' }, [])
  ]);
  card.appendChild(amountGroup);

  const orderBtn = el('button', { class: 'btn btn-primary', type: 'button' }, [document.createTextNode('Create Followers Order')]) as HTMLButtonElement;
  const botResultWrap = el('div', { id: 'bloxgen-botting-result-wrap', style: 'margin-top:10px;' }, []);

  const loadOrderStatus = async () => {
    const currentApiKey = state.settings.bloxgenApiKey || '';
    if (!currentApiKey) {
      const oList = document.getElementById('bloxgen-botting-orders-list');
      if (oList) oList.textContent = 'Set API key in Overview tab to view orders.';
      return;
    }
    try {
      const res = await apiService.getBloxgenBottingStatus(currentApiKey);
      const oList = document.getElementById('bloxgen-botting-orders-list');
      if (!oList) return;
      oList.innerHTML = '';
      const orders = res?.orders || res?.data || (Array.isArray(res) ? res : []);
      if (Array.isArray(orders) && orders.length > 0) {
        orders.slice(0, 5).forEach((ord: any) => {
          const ordRow = el('div', { style: 'display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--border-soft); font-size:12px;' }, [
            el('span', { style: 'font-weight:600; color:var(--fg);' }, [document.createTextNode(`@${ord.target || ord.username || 'Account'}`)]),
            el('span', {}, [document.createTextNode(`${ord.amount || ord.followers || 0} followers`)]),
            el('span', { class: 'badge badge-success', style: 'font-size:10.5px;' }, [document.createTextNode(ord.status || 'Active')])
          ]);
          oList.appendChild(ordRow);
        });
      } else {
        oList.textContent = 'No active or recent botting orders found.';
      }
    } catch (_) {
      const oList = document.getElementById('bloxgen-botting-orders-list');
      if (oList) oList.textContent = 'No active orders found.';
    }
  };

  orderBtn.addEventListener('click', async () => {
    const currentApiKey = state.settings.bloxgenApiKey || '';
    const amountInput = document.getElementById('bloxgen-bot-amount') as HTMLInputElement | null;
    const target = targetInput.value.trim();
    const amount = Number(amountInput?.value || 100);

    if (!target) {
      toast('Please enter a target account username or user ID', 'error');
      return;
    }

    orderBtn.disabled = true;
    orderBtn.textContent = 'Submitting order...';
    try {
      const res = await apiService.createBloxgenBottingOrder(currentApiKey, target, amount);
      botResultWrap.innerHTML = '';
      if (res && res.success) {
        toast('Order submitted');
        botResultWrap.appendChild(el('div', { style: 'color:#4ade80; font-weight:600;' }, [
          document.createTextNode(`✓ Followers order created for ${target} (${amount} followers).`)
        ]));
        await fetchBloxgenOverviewData(currentApiKey);
        loadOrderStatus();
      } else {
        const msg = res?.message || 'Order failed';
        botResultWrap.appendChild(el('div', { style: 'color:#f87171; font-weight:600;' }, [document.createTextNode(`❌ ${msg}`)]));
      }
    } catch (err: any) {
      toast(`Order error: ${err?.message || err}`, 'error');
    } finally {
      orderBtn.disabled = false;
      orderBtn.textContent = 'Create Followers Order';
    }
  });

  card.appendChild(orderBtn);
  card.appendChild(botResultWrap);

  const statusBox = el('div', { style: 'margin-top:16px; border-top:1px solid var(--border-soft); padding-top:12px;' }, [
    el('div', { style: 'display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;' }, [
      el('h4', { style: 'font-size:13px; font-weight:600; margin:0; color:var(--text-bright);' }, [document.createTextNode('Recent Orders Status')]),
      el('button', { class: 'btn btn-secondary btn-sm', style: 'font-size:11px; padding:2px 8px;' }, [document.createTextNode('Refresh Orders')])
    ]),
    el('div', { id: 'bloxgen-botting-orders-list', style: 'font-size:12px; color:var(--text-muted);' }, [document.createTextNode('Checking order status...')])
  ]);
  const refreshStatusBtn = statusBox.querySelector('button');
  refreshStatusBtn?.addEventListener('click', loadOrderStatus);
  card.appendChild(statusBox);
  setTimeout(loadOrderStatus, 100);

  parent.appendChild(card);
}

// Start the app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initApp();
    loadFromBackend(); // Load data from Python backend
  });
} else {
  initApp();
  loadFromBackend(); // Load data from Python backend
}
