import { invoke } from '@tauri-apps/api/tauri';

const API_BASE_URL = 'http://127.0.0.1:5050';

export type AccountStatus = 'valid' | 'expired' | 'banned';

export interface Account {
  id: number;
  username: string;
  display_name?: string;
  avatar_url?: string;
  user_id?: string;
  status: AccountStatus;
  group: string;
  note: string;
  password: string;
  cookie: string;
  vip_server?: string;
  vip_place_id?: string;
  vip_game_name?: string;
  auto_rejoin_enabled?: boolean;
  anti_afk_enabled?: boolean;
  added_date?: string;
}

export interface Game {
  id: string;
  name: string;
  placeId: string;
  serverId?: string;
  serverMode?: 'vip' | 'jobid' | 'subplace';
  placeMode?: 'place' | 'user';
  icon_url?: string;
}

export interface RobloxVersion {
  path: string;
  version: string;
  source: string;
}

export interface InstallerVersionEntry {
  version: string;
  status: string;
  date?: string;
  download_channel?: string;
  source?: string;
  label?: string;
}

export interface WeaoExploitItem {
  _id?: string;
  title: string;
  version?: string;
  updatedDate?: string;
  uncStatus?: boolean;
  free?: boolean;
  detected?: boolean;
  rbxversion?: string;
  updateStatus?: boolean;
  websitelink?: string;
  discordlink?: string;
  platform?: string;
  extype?: string;
  cost?: string;
  uncPercentage?: number;
  suncPercentage?: number;
  [key: string]: any;
}

export interface RobloxInstanceProcess {
  pid: number;
  name: string;
  status: string;
  memory_mb: number;
  cpu_percent?: number;
  created_at: string;
  process_type?: 'game' | 'crash_handler' | 'bootstrapper';
  username?: string;
  display_name?: string;
  avatar_url?: string;
  user_id?: string;
  place_id?: string;
  is_hidden?: boolean;
}

export interface RunningInstancesResponse {
  success: boolean;
  instances: RobloxInstanceProcess[];
  crashHandlers?: RobloxInstanceProcess[];
  otherInstances?: RobloxInstanceProcess[];
  count: number;
  crashHandlerCount?: number;
  totalCpuPercent?: number;
  systemCpuPercent?: number;
  multiInstanceEnabled: boolean;
  autoTrimEnabled?: boolean;
  autoTrimInterval?: number;
  mutexActive: boolean;
  error?: string;
}

export interface SavedUser {
  id: string;
  username: string;
  display_name?: string;
  user_id?: string;
  icon_url?: string;
}

export interface InstallerClientEntry {
  id: string;
  name: string;
  versions_path: string;
}

export interface InstallerStatus {
  active: boolean;
  status: string;
  progress: number;
  success?: boolean;
  error?: string;
  version?: string;
  client_name?: string;
}

export interface UpdateCheckResult {
  success: boolean;
  update_available: boolean;
  current_version: string;
  latest_version: string;
  latest_tag?: string;
  release_title?: string;
  release_notes?: string;
  published_at?: string;
  html_url?: string;
  asset_name?: string;
  asset_size?: number;
  download_url?: string;
  sha256?: string;
  repo?: string;
  error?: string;
  prerelease?: boolean;
}

export interface UpdateDownloadStatus {
  active: boolean;
  status: string;
  progress: number;
  downloaded_bytes: number;
  total_bytes: number;
  success: boolean | null;
  error: string | null;
  file_path?: string | null;
  asset_name?: string;
}

export interface Settings {
  firstLaunch: boolean;
  multiSelect: boolean;
  activeIndicator: boolean;
  disableSuccessPopups: boolean;
  confirmBeforeLaunch: boolean;
  autoCloseCrashHandlers?: boolean;
  compactRows: boolean;
  showTableAvatars?: boolean;
  downloadAvatarIcons?: boolean;
  showSavedGamesBar?: boolean;
  showDetailPanel?: boolean;
  layoutPreset?: 'standard' | 'swapped';
  defaultStartupView?: 'accounts' | 'instances' | 'vip' | 'settings';
  toastPosition?: 'bottom-right' | 'top-right' | 'bottom-left' | 'top-left' | 'top-center';
  toastDuration?: number;
  enableSoundEffects?: boolean;
  showLaunchNotifications?: boolean;
  showErrorNotifications?: boolean;
  accentIndex: number;
  selectedTheme?: string;
  accentColor?: string;
  customThemes?: any[];
  customBackground?: any;
  robloxPath: string;
  launchClient: 'standard' | 'player';
  autoUpdateCheck: boolean;
  autoUpdateToPreReleases?: boolean;
  autoUpdateToLatestRelease?: boolean;
  autoCheckRobloxUpdates?: boolean;
  disableExecutorPresets?: boolean;
  encryptionEnabled: boolean;
  encryptionMethod: 'none' | 'password' | 'hardware';
  preferredBrowser: 'auto' | 'chrome' | 'edge' | 'firefox' | 'waterfox' | 'chromium';
  credentialImportInstances?: number;
  multiInstance: boolean;
  autoValidateOnLaunch?: boolean;
  autoSortAccounts?: 'status' | 'username' | 'none';
  multiLaunchDelay?: number;
  confirmBulkDelete?: boolean;
  autoKillRobloxOnExit?: boolean;
  minimizeToTray?: boolean;
  startAtStartup?: boolean;
  streamerMode?: boolean;
  streamerHideUsernames?: boolean;
  streamerHideAvatars?: boolean;
  streamerHideSensitiveInfo?: boolean;
  streamerHideGroupsAndNotes?: boolean;
  streamerBlurLevel?: 'light' | 'medium' | 'heavy';
  streamerRevealOnHover?: boolean;
  autoMemoryTrimEnabled?: boolean;
  autoMemoryTrimIntervalMinutes?: number;
  headlessMode?: boolean;
  headlessTrimMemory?: boolean;
  headlessIdlePriority?: boolean;
  headlessDetectionDelaySeconds?: number;
  autoRejoinEnabled?: boolean;
  autoRejoinDelaySeconds?: number;
  autoRejoinMaxAttempts?: number;
  autoRejoinLaunchBehavior?: 'rejoin_same_server' | 'rejoin_same_game';
  antiAfkEnabled?: boolean;
  antiAfkIntervalMinutes?: number;
  antiAfkKeyName?: string;
  antiAfkKeyCode?: number;
  antiAfkDuration?: number;
  antiAfkShowNextLabel?: boolean;
  lastPlaceId?: string;
  lastUserId?: string;
  lastServerId?: string;
  lastVipServerId?: string;
  lastJobId?: string;
  lastSubplaceId?: string;
  lastPlaceMode?: 'place' | 'user';
  lastServerMode?: 'vip' | 'jobid' | 'subplace';
  autoSaveLaunchDetails?: boolean;
  autoArrangeScope?: 'both' | 'primary' | 'secondary';
  autoArrangeDimensionMode?: 'auto' | 'target_size';
  autoArrangeTargetWidth?: number;
  autoArrangeTargetHeight?: number;
  keepClientsArranged?: boolean;
  preferredRegion?: string;
  serverPerAccount?: boolean;
  bloxgenApiKey?: string;
  bloxgenAutoAddAccounts?: boolean;
  bloxgenDefaultGroup?: string;
  enableTopmost?: boolean;
  autoRelaunchEnabled?: boolean;
  autoRelaunchIntervalMinutes?: number;
  autoRelaunchGroup?: string;
  customKeybinds?: Record<string, string>;
  swapPreserveSettings?: boolean;
  swapPreserveFastflags?: boolean;
  swapPreserveAppSettings?: boolean;
  swapDeleteStudio?: boolean;
  swapPurgeAuth?: boolean;
  swapCreateRestorePoint?: boolean;
  swapSpoofMac?: boolean;
  swapSpoofHwid?: boolean;
  swapSpoofVolume?: boolean;
  swapOuiMirror?: boolean;
  swapDhcpRefresh?: boolean;
  swapCleanBeforeRun?: boolean;
  swapAutoReinstallRoblox?: boolean;
}

export interface AntiAfkStatus {
  success: boolean;
  enabled: boolean;
  interval_minutes: number;
  key_name: string;
  key_code: number;
  duration_seconds?: number;
  roblox_instance_count: number;
  last_run_ts?: number;
  next_run_ts?: number;
  seconds_until_next_run?: number;
  last_pass_summary?: {
    total_windows: number;
    successful_windows: number;
    failed_windows: number;
  };
  in_progress?: boolean;
  error?: string;
}

export interface QuickSignInStartResponse {
  success: boolean;
  session_id: string;
  status: string;
  status_message?: string;
  error?: string;
}

export interface AutoArrangeResult {
  success: boolean;
  count: number;
  monitors?: number;
  message?: string;
  error?: string;
}

export interface AutoArrangeMonitor {
  id: number;
  is_primary: boolean;
  width: number;
  height: number;
  work_area: [number, number, number, number];
}

export interface AutoArrangeStatus {
  success: boolean;
  keepClientsArranged: boolean;
  activeRobloxWindows: number;
  monitorsCount: number;
  scope: 'both' | 'primary' | 'secondary';
  dimensionMode: 'auto' | 'target_size';
  targetWidth: number;
  targetHeight: number;
  error?: string;
}

export interface AutoRelaunchStatus {
  success: boolean;
  enabled: boolean;
  interval_minutes: number;
  group: string;
  accounts_in_group: number;
  next_run_ts: number | null;
  last_run_ts: number | null;
  seconds_until_next_run: number;
  in_progress: boolean;
  last_summary?: string;
  error?: string;
}


export interface QuickSignInResult {
  success: boolean;
  username: string;
  display_name?: string;
  user_id?: string;
  avatar_url?: string;
  code?: string;
  error?: string;
}

export interface QuickSignInStatusResponse {
  session_id: string;
  status: 'starting' | 'code_ready' | 'completed' | 'cancelled' | 'error';
  status_message: string;
  code: string;
  qr_image_url: string;
  time_elapsed: number;
  result?: QuickSignInResult;
  error?: string;
}

export interface BrowserExtension {
  key: string;
  name: string;
  source: string;
  display_source: string;
  extension_id: string;
  folder_name: string;
  enabled: boolean;
  installed_at: string;
  directory: string;
  manifest_version: number;
}

export interface ExtensionsResponse {
  success: boolean;
  extensions?: BrowserExtension[];
  error?: string;
}

class ApiService {
  private static readonly GAME_INFO_CACHE_MAX_SIZE = 500;
  private static readonly GAME_INFO_CACHE_TTL = 300000;
  private gameInfoCache: Map<string, { data: any; timestamp: number }> = new Map();
  private _authToken: string | null = null;
  private _tokenPromise: Promise<string> | null = null;

  private async _getAuthToken(): Promise<string> {
    if (this._authToken) return this._authToken;
    if (this._tokenPromise) return this._tokenPromise;

    this._tokenPromise = (async () => {
      try {
        const token = await invoke<string>('get_api_token');
        if (token) {
          this._authToken = token;
          return token;
        }
      } catch (_) { }

      try {
        const resp = await fetch(`${API_BASE_URL}/api/auth/token`);
        if (resp.ok) {
          const data = await resp.json();
          if (data.token) {
            this._authToken = data.token;
            return data.token;
          }
        }
      } catch (_) { }

      this._tokenPromise = null;
      return '';
    })();

    return this._tokenPromise;
  }

  private async request<T>(
    endpoint: string,
    method: string = 'GET',
    body?: any
  ): Promise<T> {
    const formattedEndpoint = endpoint.startsWith('/api/')
      ? endpoint.slice(1)
      : endpoint.startsWith('/')
        ? `api${endpoint}`
        : `api/${endpoint}`;

    try {
      const bodyStr = body ? JSON.stringify(body) : undefined;
      const resStr = await invoke<string>('python_backend_request', {
        endpoint: formattedEndpoint,
        method,
        body: bodyStr,
      });
      const parsed = JSON.parse(resStr);
      if (parsed && typeof parsed === 'object' && parsed.error === 'Unauthorized') {
        this._authToken = null;
      }
      return parsed as T;
    } catch (error: any) {
      if (error && String(error.message || error).includes('Unauthorized')) {
        this._authToken = null;
      }
      console.error('Tauri IPC request failed, attempting fetch fallback:', error);
    }

    let token = await this._getAuthToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['X-FRAM-Token'] = token;
    }

    const options: RequestInit = {
      method,
      headers,
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      let response = await fetch(`${API_BASE_URL}/${formattedEndpoint}`, options);

      if (response.status === 401) {
        this._authToken = null;
        token = await this._getAuthToken();
        if (token) {
          headers['X-FRAM-Token'] = token;
          options.headers = headers;
          response = await fetch(`${API_BASE_URL}/${formattedEndpoint}`, options);
        }
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Request failed' }));
        const errorMsg = errorData.error || errorData.details || `HTTP ${response.status} ${response.statusText}`;
        console.error(`[API Error] HTTP ${response.status} ${method} /${formattedEndpoint}:`, {
          status: response.status,
          statusText: response.statusText,
          endpoint: formattedEndpoint,
          method,
          error: errorMsg,
          details: errorData
        });
        throw new Error(errorMsg);
      }

      return await response.json();
    } catch (error: any) {
      console.error(`[API Request Exception] ${method} /${formattedEndpoint}:`, {
        message: error?.message || String(error),
        stack: error?.stack,
        endpoint: formattedEndpoint,
        method
      });
      throw error;
    }
  }


  // Account methods
  async getAccounts(): Promise<Account[]> {
    return this.request<Account[]>('/accounts');
  }

  async createAccount(account: Partial<Account>): Promise<Account> {
    return this.request<Account>('/accounts', 'POST', account);
  }

  async bulkImportCookies(
    accounts: Array<{ username?: string; cookie: string; password?: string; group?: string; note?: string }>,
    defaultGroup?: string,
    defaultNote?: string
  ): Promise<{ success: boolean; imported_count: number; failed_count: number; accounts: Account[]; errors?: string[] }> {
    return this.request('/accounts/bulk-import-cookies', 'POST', {
      accounts,
      default_group: defaultGroup || '',
      default_note: defaultNote || ''
    });
  }

  async getAccount(id: number): Promise<Account> {
    return this.request<Account>(`/accounts/${id}`);
  }

  async updateAccount(id: number, account: Partial<Account>): Promise<Account> {
    return this.request<Account>(`/accounts/${id}`, 'PUT', account);
  }

  async deleteAccount(id: number): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/accounts/${id}`, 'DELETE');
  }

  async bulkDeleteAccounts(ids: number[]): Promise<{ message: string }> {
    return this.request<{ message: string }>('/accounts/bulk-delete', 'POST', { ids });
  }

  async reorderAccounts(params: { ids?: number[]; usernames?: string[] }): Promise<{ success: boolean; accounts: Account[] }> {
    return this.request('/accounts/reorder', 'POST', params);
  }

  async bulkUpdateVip(mapping: Record<string, string>): Promise<{ success: boolean; changed: number }> {
    return this.request<{ success: boolean; changed: number }>('/accounts/bulk-vip', 'POST', { mapping });
  }

  async launchAccount(params: { username: string; placeId?: string; serverId?: string; serverMode?: string; version?: string; launchMode?: string }): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/accounts/launch', 'POST', params);
  }

  async launchHome(params: { username: string; preferredBrowser?: string }): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/accounts/launch-home', 'POST', params);
  }

  async getRobloxVersions(): Promise<{ success: boolean; versions: RobloxVersion[]; error?: string }> {
    return this.request<{ success: boolean; versions: RobloxVersion[]; error?: string }>('/roblox/versions');
  }

  async launchRobloxApp(params?: { versionPath?: string; version?: string }): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/launch-app', 'POST', params || {});
  }

  async uninstallRobloxVersion(path: string, version?: string): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/uninstall-version', 'POST', { path, version });
  }

  async killRobloxProcess(): Promise<{ success: boolean; message?: string; killed?: number; error?: string }> {
    return this.request<{ success: boolean; message?: string; killed?: number; error?: string }>('/roblox/kill', 'POST');
  }

  async killAllCrashHandlers(): Promise<{ success: boolean; killed?: number; message?: string; error?: string }> {
    return this.request<{ success: boolean; killed?: number; message?: string; error?: string }>('/instances/kill-crash-handlers', 'POST');
  }

  async trimRobloxMemory(): Promise<{ success: boolean; trimmed?: number; trimmedCount?: number; savedMb?: number; total_processes?: number; message?: string; error?: string }> {
    return this.request<{ success: boolean; trimmed?: number; trimmedCount?: number; savedMb?: number; total_processes?: number; message?: string; error?: string }>('/roblox/trim-memory', 'POST');
  }

  async validateAllAccounts(): Promise<{ accounts: Account[]; summary: { total: number; valid: number; expired: number; banned: number } }> {
    return this.request<{ accounts: Account[]; summary: { total: number; valid: number; expired: number; banned: number } }>('/accounts/validate-all', 'POST');
  }

  async getSystemLogs(): Promise<{ success: boolean; logs: { timestamp: string; time?: number; message: string; level: string; category?: string; source?: string }[] }> {
    return this.request<{ success: boolean; logs: { timestamp: string; time?: number; message: string; level: string; category?: string; source?: string }[] }>('/system/logs');
  }

  async validateAccount(id: number): Promise<{ account: Account; status: AccountStatus; valid: boolean }> {
    return this.request<{ account: Account; status: AccountStatus; valid: boolean }>(`/accounts/${id}/validate`, 'POST');
  }

  // Game methods
  async getGames(): Promise<Game[]> {
    return this.request<Game[]>('/games');
  }

  async createGame(game: Partial<Game>): Promise<Game> {
    return this.request<Game>('/games', 'POST', game);
  }

  async deleteGame(id: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/games/${id}`, 'DELETE');
  }

  // Saved Users methods
  async getSavedUsers(): Promise<SavedUser[]> {
    return this.request<SavedUser[]>('/saved-users');
  }

  async createSavedUser(user: Partial<SavedUser>): Promise<SavedUser> {
    return this.request<SavedUser>('/saved-users', 'POST', user);
  }

  async deleteSavedUser(id: string): Promise<{ message: string; success: boolean }> {
    return this.request<{ message: string; success: boolean }>(`/saved-users/${id}`, 'DELETE');
  }

  // Settings methods
  async getSettings(): Promise<Settings> {
    return this.request<Settings>('/settings');
  }

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    return this.request<Settings>('/settings', 'PUT', settings);
  }

  // Utility methods
  async exportData(includeCredentials = true, filePath?: string): Promise<any> {
    if (filePath) {
      return this.request('/export', 'POST', {
        include_credentials: includeCredentials,
        file_path: filePath
      });
    }
    return this.request<{ accounts: Account[]; games: Game[]; settings: Settings }>(`/export?include_credentials=${includeCredentials}`);
  }

  async importData(data: any): Promise<{ message: string }> {
    return this.request<{ message: string }>('/import', 'POST', data);
  }

  async clearAllData(): Promise<{ message: string; settings?: Settings }> {
    return this.request<{ message: string; settings?: Settings }>('/clear-all', 'POST');
  }

  async uninstall(): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>('/app/uninstall', 'POST');
  }

  async clearAccounts(): Promise<{ message: string }> {
    return this.request<{ message: string }>('/clear-accounts', 'POST');
  }

  async completeSetup(data: any): Promise<{ success: boolean; message?: string; settings?: Settings; error?: string }> {
    return this.request<{ success: boolean; message?: string; settings?: Settings; error?: string }>('/setup/complete', 'POST', data);
  }

  async getEncryptionStatus(): Promise<{ encryptionEnabled: boolean; encryptionMethod: string }> {
    return this.request<{ encryptionEnabled: boolean; encryptionMethod: string }>('/setup/encryption-status');
  }

  async getBrowserStatus(): Promise<{ manager_available: boolean; browsers_available: string[]; has_supported_browser: boolean; is_running: boolean; accounts_count: number; active_instances?: number; user_closed?: boolean; last_close_reason?: string | null; error?: string }> {
    return this.request<{ manager_available: boolean; browsers_available: string[]; has_supported_browser: boolean; is_running: boolean; accounts_count: number; active_instances?: number; user_closed?: boolean; last_close_reason?: string | null; error?: string }>('/browser/status');
  }

  async addAccountBrowser(amount: number, website: string, preferredBrowser: string): Promise<{ status: string }> {
    return this.request<{ status: string }>('/accounts/add-browser', 'POST', { amount, website, preferredBrowser });
  }

  async startQuickSignIn(preferredBrowser: string = 'auto'): Promise<QuickSignInStartResponse> {
    return this.request<QuickSignInStartResponse>('/accounts/add-quick-signin', 'POST', { preferredBrowser });
  }

  async getQuickSignInStatus(sessionId: string): Promise<QuickSignInStatusResponse> {
    return this.request<QuickSignInStatusResponse>(`/quick-signin/status/${sessionId}`);
  }

  async cancelQuickSignIn(sessionId: string): Promise<{ success: boolean; message?: string }> {
    return this.request<{ success: boolean; message?: string }>(`/quick-signin/cancel/${sessionId}`, 'POST');
  }

  async addAccountQuickSignIn(preferredBrowser: string): Promise<{ success: boolean; username?: string; error?: string }> {
    return this.request<{ success: boolean; username?: string; error?: string }>('/accounts/add-quick-signin', 'POST', { preferredBrowser });
  }

  async addAccountCredentials(credentials: [string, string][], preferredBrowser: string, maxConcurrent: number = 1): Promise<{ status: string }> {
    return this.request<{ status: string }>('/accounts/add-credentials', 'POST', { credentials, preferredBrowser, max_concurrent: maxConcurrent });
  }

  // Roblox API methods
  async validateCookie(cookie: string): Promise<{ valid: boolean; status?: AccountStatus; is_banned?: boolean; username?: string; user_id?: string; display_name?: string; avatar_url?: string; error?: string }> {
    return this.request<{ valid: boolean; status?: AccountStatus; is_banned?: boolean; username?: string; user_id?: string; display_name?: string; avatar_url?: string; error?: string }>('/roblox/validate-cookie', 'POST', { cookie });
  }

  async getUserInfo(username: string): Promise<{
    username: string;
    user_id: string;
    display_name: string;
    avatar_url?: string;
    joinable?: boolean;
    presence_type?: number;
    location?: string;
    error?: string;
  }> {
    return this.request<{
      username: string;
      user_id: string;
      display_name: string;
      avatar_url?: string;
      joinable?: boolean;
      presence_type?: number;
      location?: string;
      error?: string;
    }>('/roblox/user-info', 'POST', { username });
  }

  async getGameInfo(placeId?: string, universeId?: string, forceRefresh: boolean = false): Promise<{ place_id: string; universe_id: string; name: string; icon_url?: string; error?: string }> {
    const key = `${(placeId || '').trim()}_${(universeId || '').trim()}`;
    if (!forceRefresh && key && this.gameInfoCache.has(key)) {
      const cached = this.gameInfoCache.get(key)!;
      if (Date.now() - cached.timestamp < ApiService.GAME_INFO_CACHE_TTL) {
        return cached.data;
      }
      this.gameInfoCache.delete(key);
    }
    const result = await this.request<{ place_id: string; universe_id: string; name: string; icon_url?: string; error?: string }>('/roblox/game-info', 'POST', { placeId, universeId, forceRefresh });
    if (result && !result.error && key) {
      if (this.gameInfoCache.size >= ApiService.GAME_INFO_CACHE_MAX_SIZE) {
        const now = Date.now();
        for (const [k, v] of this.gameInfoCache) {
          if (now - v.timestamp >= ApiService.GAME_INFO_CACHE_TTL) {
            this.gameInfoCache.delete(k);
          }
        }
        if (this.gameInfoCache.size >= ApiService.GAME_INFO_CACHE_MAX_SIZE) {
          const oldest = this.gameInfoCache.keys().next().value;
          if (oldest !== undefined) this.gameInfoCache.delete(oldest);
        }
      }
      this.gameInfoCache.set(key, { data: result, timestamp: Date.now() });
    }
    return result;
  }

  async clearIconCache(): Promise<{ success: boolean; message?: string }> {
    this.gameInfoCache.clear();
    return this.request<{ success: boolean; message?: string }>('/roblox/clear-icon-cache', 'POST');
  }

  async getIconCacheStats(): Promise<{ success: boolean; stats: Record<string, any> }> {
    return this.request<{ success: boolean; stats: Record<string, any> }>('/roblox/icon-cache/stats');
  }

  async getSubplaces(placeId: string): Promise<{
    success: boolean;
    place_id: string;
    subplaces: Array<{ id: number; name: string; description?: string }>;
    error?: string;
  }> {
    return this.request(`/roblox/subplaces/${encodeURIComponent(placeId)}`);
  }

  async resolvePrivateServer(input: string, cookie?: string): Promise<{
    input: string;
    resolved: string;
    link_code?: string;
    access_code?: string;
    place_id?: string;
    url?: string;
    error?: string;
  }> {
    return this.request<{
      input: string;
      resolved: string;
      link_code?: string;
      access_code?: string;
      place_id?: string;
      url?: string;
      error?: string;
    }>('/roblox/private-server-resolve', 'POST', { input, cookie });
  }

  async getMultiInstanceStatus(): Promise<{ success: boolean; enabled: boolean; active: boolean }> {
    return this.request<{ success: boolean; enabled: boolean; active: boolean }>('/multi-instance/status');
  }

  async toggleMultiInstance(enabled?: boolean): Promise<{ success: boolean; enabled: boolean; active: boolean; message?: string }> {
    return this.request<{ success: boolean; enabled: boolean; active: boolean; message?: string }>('/multi-instance/toggle', 'POST', { enabled });
  }

  async getHeadlessStatus(): Promise<{ success: boolean; enabled: boolean; active: boolean; pids: number[]; pid_count: number; hidden_count: number }> {
    return this.request<{ success: boolean; enabled: boolean; active: boolean; pids: number[]; pid_count: number; hidden_count: number }>('/headless/status');
  }

  async toggleHeadlessMode(enabled?: boolean): Promise<{ success: boolean; enabled: boolean; message?: string }> {
    return this.request<{ success: boolean; enabled: boolean; message?: string }>('/headless/toggle', 'POST', { enabled });
  }

  async applyHeadlessNow(): Promise<{ success: boolean; pids: number; hidden: number; priority: number; trimmed: number; message?: string; error?: string }> {
    return this.request<{ success: boolean; pids: number; hidden: number; priority: number; trimmed: number; message?: string; error?: string }>('/headless/apply', 'POST');
  }

  async restoreHeadlessWindows(): Promise<{ success: boolean; restored: number; priority: number; message?: string; error?: string }> {
    return this.request<{ success: boolean; restored: number; priority: number; message?: string; error?: string }>('/headless/restore', 'POST');
  }

  async getAntiAfkStatus(): Promise<AntiAfkStatus> {
    return this.request<AntiAfkStatus>('/anti-afk/status');
  }

  async updateAntiAfkSettings(settings: {
    antiAfkEnabled?: boolean;
    antiAfkIntervalMinutes?: number;
    antiAfkKeyName?: string;
    antiAfkDuration?: number;
    antiAfkShowNextLabel?: boolean;
  }): Promise<AntiAfkStatus> {
    return this.request<AntiAfkStatus>('/anti-afk/settings', 'POST', settings);
  }

  async triggerAntiAfk(): Promise<{
    success: boolean;
    total_windows: number;
    successful_windows: number;
    failed_windows: number;
    key_used: string;
    timestamp: number;
    error?: string;
  }> {
    return this.request('/anti-afk/trigger', 'POST');
  }

  async getAutoRelaunchStatus(): Promise<AutoRelaunchStatus> {
    return this.request<AutoRelaunchStatus>('/auto-relaunch/status');
  }

  async updateAutoRelaunchSettings(settings: {
    autoRelaunchEnabled?: boolean;
    autoRelaunchIntervalMinutes?: number;
    autoRelaunchGroup?: string;
  }): Promise<AutoRelaunchStatus> {
    return this.request<AutoRelaunchStatus>('/auto-relaunch/settings', 'POST', settings);
  }

  async triggerAutoRelaunch(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request('/auto-relaunch/trigger', 'POST');
  }

  async autoArrangeClients(options?: { scope?: string; dimensionMode?: string; targetWidth?: number; targetHeight?: number }): Promise<AutoArrangeResult> {
    return this.request<AutoArrangeResult>('/roblox/auto-arrange', 'POST', options || {});
  }

  async getAutoArrangeMonitors(): Promise<{ success: boolean; monitors: AutoArrangeMonitor[]; error?: string }> {
    return this.request<{ success: boolean; monitors: AutoArrangeMonitor[]; error?: string }>('/roblox/auto-arrange/monitors');
  }

  async getAutoArrangeStatus(): Promise<AutoArrangeStatus> {
    return this.request<AutoArrangeStatus>('/roblox/auto-arrange/status');
  }

  async toggleAutoArrange(enabled?: boolean): Promise<{ success: boolean; enabled: boolean; message?: string }> {
    return this.request<{ success: boolean; enabled: boolean; message?: string }>('/roblox/auto-arrange/toggle', 'POST', { enabled });
  }


  async getRunningInstances(): Promise<RunningInstancesResponse> {
    return this.request<RunningInstancesResponse>('/instances');
  }

  async killInstanceProcess(pid: number, username?: string): Promise<{ success: boolean; message?: string; error?: string; username?: string; auto_rejoin_disabled?: boolean }> {
    return this.request<{ success: boolean; message?: string; error?: string; username?: string; auto_rejoin_disabled?: boolean }>('/instances/kill', 'POST', { pid, username });
  }

  async relaunchInstance(params: { pid?: number; username?: string; placeId?: string; serverId?: string; serverMode?: string; version?: string; launchMode?: string }): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/instances/relaunch', 'POST', params);
  }

  async focusInstance(pid: number): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/instances/focus', 'POST', { pid });
  }

  async hideInstance(pid: number): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/instances/hide', 'POST', { pid });
  }

  async unhideInstance(pid: number): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/instances/unhide', 'POST', { pid });
  }

  async trimInstanceMemory(pid: number): Promise<{ success: boolean; savedMb?: number; message?: string; error?: string }> {
    return this.request<{ success: boolean; savedMb?: number; message?: string; error?: string }>('/instances/trim', 'POST', { pid });
  }

  async getAuthStatus(): Promise<{ encryptionEnabled: boolean; encryptionMethod: string; locked: boolean }> {
    return this.request<{ encryptionEnabled: boolean; encryptionMethod: string; locked: boolean }>('/auth/status');
  }

  async unlockApp(password: string): Promise<{ success: boolean; unlocked?: boolean; error?: string }> {
    return this.request<{ success: boolean; unlocked?: boolean; error?: string }>('/auth/unlock', 'POST', { password });
  }

  async lockApp(): Promise<{ success: boolean; locked?: boolean }> {
    return this.request<{ success: boolean; locked?: boolean }>('/auth/lock', 'POST');
  }

  async switchEncryption(params: {
    method: 'password' | 'hardware' | 'none';
    current_password?: string;
    new_password?: string;
  }): Promise<{ success: boolean; encryptionEnabled: boolean; encryptionMethod: string; settings?: Settings; error?: string }> {
    return this.request('/auth/switch-encryption', 'POST', params);
  }

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.request('/health');
  }

  async relaunchBackend(): Promise<{ started: boolean; reason: string }> {
    this._authToken = null;
    this._tokenPromise = null;
    try {
      const res = await invoke<{ started: boolean; reason: string }>('relaunch_backend');
      return res;
    } catch (e: any) {
      return { started: false, reason: e?.message || String(e) };
    }
  }

  async getInstallerAvailableVersions(): Promise<{ success: boolean; versions: InstallerVersionEntry[]; error?: string }> {
    return this.request<{ success: boolean; versions: InstallerVersionEntry[]; error?: string }>('/installer/available-versions');
  }

  async getInstallerClients(): Promise<{ success: boolean; clients: InstallerClientEntry[]; error?: string }> {
    return this.request<{ success: boolean; clients: InstallerClientEntry[]; error?: string }>('/installer/clients');
  }

  async startInstallerDownload(version_entry: InstallerVersionEntry, client_id: string, overwrite: boolean = false): Promise<{ success: boolean; already_exists?: boolean; target_dir?: string; client_name?: string; version?: string; message?: string; error?: string }> {
    return this.request<{ success: boolean; already_exists?: boolean; target_dir?: string; client_name?: string; version?: string; message?: string; error?: string }>('/installer/start', 'POST', { version_entry, client_id, overwrite });
  }

  async getInstallerStatus(): Promise<{ success: boolean; status: InstallerStatus; error?: string }> {
    return this.request<{ success: boolean; status: InstallerStatus; error?: string }>('/installer/status');
  }

  async getWeaoExploits(): Promise<{ success: boolean; exploits: WeaoExploitItem[]; error?: string }> {
    try {
      const res = await this.request<{ success: boolean; exploits: WeaoExploitItem[]; error?: string }>('/installer/weao-exploits');
      if (res && res.success && Array.isArray(res.exploits) && res.exploits.length > 0) {
        return res;
      }
    } catch {
      // Fallback
    }

    const candidateUrls = [
      'https://whatexpsare.online/api/status/exploits',
      'https://weao.gg/api/status/exploits'
    ];

    for (const url of candidateUrls) {
      try {
        const resp = await fetch(url, { headers: { 'User-Agent': 'WEAO-3PService' } });
        if (resp.ok) {
          const list = await resp.json();
          if (Array.isArray(list)) {
            return { success: true, exploits: list };
          }
        }
      } catch {
        continue;
      }
    }

    return { success: false, exploits: [], error: 'Failed to fetch WEAO exploits data' };
  }

  async getRobloxGlobalSettings(): Promise<{
    exists: boolean;
    file_path: string;
    is_roblox_running: boolean;
    settings: Record<string, any>;
    specs: Record<string, any[]>;
    error?: string;
  }> {
    return this.request('/roblox/global-settings');
  }

  async updateRobloxGlobalSettings(settings: Record<string, any>): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/global-settings', 'POST', { settings });
  }

  async getRobloxIxpSettings(): Promise<{
    success: boolean;
    exists: boolean;
    file_path: string;
    settings: Record<string, string>;
    error?: string;
  }> {
    return this.request('/roblox/ixp-settings');
  }

  async updateRobloxIxpSettings(settings: Record<string, string>): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/ixp-settings', 'POST', { settings });
  }

  async resetRobloxIxpSettings(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/ixp-settings', 'DELETE');
  }

  async getRobloxFastFlags(): Promise<{
    success: boolean;
    exists: boolean;
    file_path: string;
    flags: Record<string, string>;
    error?: string;
  }> {
    return this.request('/roblox/fastflags');
  }

  async updateRobloxFastFlags(flags: Record<string, string>): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/fastflags', 'POST', { flags });
  }

  async validateRobloxFastFlag(name: string): Promise<{ success: boolean; valid: boolean; message: string; error?: string }> {
    return this.request<{ success: boolean; valid: boolean; message: string; error?: string }>('/roblox/fastflags/validate', 'POST', { name });
  }

  async backupRobloxFastFlags(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/fastflags/backup', 'POST');
  }

  async restoreRobloxFastFlags(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/fastflags/restore', 'POST');
  }

  async resetRobloxFastFlags(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/roblox/fastflags/reset', 'POST');
  }

  async selectFolderDialog(): Promise<{ success: boolean; path?: string; cancelled?: boolean; error?: string }> {
    return this.request('/setup/select-folder', 'POST');
  }

  async previewFRAMData(path: string, password?: string): Promise<{
    success: boolean;
    valid: boolean;
    path?: string;
    accounts_count?: number;
    games_count?: number;
    users_count?: number;
    has_settings?: boolean;
    has_themes?: boolean;
    has_webhooks?: boolean;
    is_encrypted?: boolean;
    requires_password?: boolean;
    error?: string;
  }> {
    return this.request('/setup/preview-framdata', 'POST', { path, password: password || '' });
  }

  async importFRAMData(path: string, password?: string): Promise<{
    success: boolean;
    accounts_imported?: number;
    games_imported?: number;
    users_imported?: number;
    settings_imported?: boolean;
    webhooks_imported?: boolean;
    themes_imported?: boolean;
    requires_password?: boolean;
    message?: string;
    error?: string;
  }> {
    return this.request('/setup/import-framdata', 'POST', { path, password: password || '' });
  }

  async getLastError(): Promise<{
    has_error: boolean;
    exception_name?: string;
    exception_message?: string;
    source?: string;
    traceback?: string;
    github_issue_url?: string;
    title?: string;
    body?: string;
  }> {
    return this.request('/system/last-error');
  }

  async getWebhookConfig(): Promise<{ success: boolean; config?: any; history?: any[]; error?: string }> {
    return this.request('/webhook/config');
  }

  async saveWebhookConfig(config: any): Promise<{ success: boolean; config?: any; message?: string; error?: string }> {
    return this.request('/webhook/config', 'POST', config);
  }

  async testWebhook(webhook_url?: string): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request('/webhook/test', 'POST', { webhook_url });
  }

  async testWebhookScreenshot(webhook_url?: string, all_monitors?: boolean): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request('/webhook/test-screenshot', 'POST', { webhook_url, all_monitors });
  }

  async testWebhookInstances(webhook_url?: string): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request('/webhook/test-instances', 'POST', { webhook_url });
  }

  async getExtensions(): Promise<ExtensionsResponse> {
    return this.request('/extensions');
  }

  async toggleExtension(key: string, enabled: boolean): Promise<{ success: boolean; key?: string; enabled?: boolean; error?: string }> {
    return this.request('/extensions/toggle', 'POST', { key, enabled });
  }

  async deleteExtension(key: string): Promise<{ success: boolean; key?: string; error?: string }> {
    return this.request('/extensions/delete', 'POST', { key });
  }

  async addExtension(source: string, pathOrId: string): Promise<{ success: boolean; extension?: BrowserExtension; error?: string }> {
    return this.request('/extensions/add', 'POST', { source, path_or_id: pathOrId });
  }

  async browseExtensionFolder(): Promise<{ success: boolean; path?: string; cancelled?: boolean; error?: string }> {
    return this.request('/extensions/browse-folder', 'POST');
  }

  async browseExtensionFile(fileType: 'crx' | 'xpi' | 'any' = 'any'): Promise<{ success: boolean; path?: string; cancelled?: boolean; error?: string }> {
    return this.request('/extensions/browse-file', 'POST', { file_type: fileType });
  }

  async getBloxgenBalance(apiKey: string): Promise<any> {
    return this.request(`/bloxgen/balance?apiKey=${encodeURIComponent(apiKey)}`);
  }

  async getBloxgenPrices(apiKey: string): Promise<any> {
    return this.request(`/bloxgen/prices?apiKey=${encodeURIComponent(apiKey)}`);
  }

  async getBloxgenDailyLimit(apiKey: string): Promise<any> {
    return this.request(`/bloxgen/daily-limit?apiKey=${encodeURIComponent(apiKey)}`);
  }

  async getBloxgenStock(apiKey: string): Promise<any> {
    return this.request(`/bloxgen/stock?apiKey=${encodeURIComponent(apiKey)}`);
  }

  async generateBloxgenAccount(apiKey: string, type: string, region?: string, continent?: string): Promise<any> {
    const payload: Record<string, any> = { apiKey, type };
    if (continent) {
      payload.continent = continent;
    } else if (region) {
      payload.region = region;
    }
    return this.request('/bloxgen/generate', 'POST', payload);
  }

  async checkBloxgenSingleCookie(apiKey: string, cookie: string): Promise<any> {
    return this.request('/bloxgen/checker/single', 'POST', { apiKey, cookie });
  }

  async getBloxgenCheckerAccess(apiKey: string): Promise<any> {
    return this.request(`/bloxgen/checker/access?apiKey=${encodeURIComponent(apiKey)}`);
  }

  async getBloxgenBottingStatus(apiKey: string): Promise<any> {
    return this.request(`/bloxgen/botting/status?apiKey=${encodeURIComponent(apiKey)}`);
  }

  async getBloxgenBottingPricing(apiKey: string): Promise<any> {
    return this.request(`/bloxgen/botting/pricing?apiKey=${encodeURIComponent(apiKey)}`);
  }

  async checkBloxgenBottingAccount(apiKey: string, account: string): Promise<any> {
    return this.request(`/bloxgen/botting/check?apiKey=${encodeURIComponent(apiKey)}&account=${encodeURIComponent(account)}`);
  }

  async createBloxgenBottingOrder(apiKey: string, target: string, amount: number): Promise<any> {
    return this.request('/bloxgen/botting/create', 'POST', { apiKey, target, amount });
  }

  async checkForUpdates(force = false, options?: { prerelease?: boolean; latest?: boolean }): Promise<UpdateCheckResult> {
    let url = `/updater/check?force=${force}`;
    if (options && options.prerelease !== undefined) {
      url += `&prerelease=${options.prerelease}`;
    }
    if (options && options.latest !== undefined) {
      url += `&latest=${options.latest}`;
    }
    return this.request<UpdateCheckResult>(url);
  }

  async getGithubReleases(force = false): Promise<{ success: boolean; releases?: any[]; error?: string }> {
    return this.request<{ success: boolean; releases?: any[]; error?: string }>(`/updater/releases?force=${force}`);
  }

  async startUpdateDownload(options?: { download_url?: string; asset_name?: string; sha256?: string; total_bytes?: number }): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/updater/download', 'POST', options || {});
  }

  async getUpdateStatus(): Promise<{ success: boolean; status: UpdateDownloadStatus; error?: string }> {
    return this.request<{ success: boolean; status: UpdateDownloadStatus; error?: string }>('/updater/status');
  }

  async applyUpdate(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/updater/apply', 'POST');
  }

  async getRblxSwapStatus(): Promise<RblxSwapStatus> {
    return this.request<RblxSwapStatus>('/api/rblxswap/status');
  }

  async cleanRblxTraces(options: RblxSwapCleanOptions): Promise<RblxSwapCleanResult> {
    return this.request<RblxSwapCleanResult>('/api/rblxswap/clean', 'POST', options);
  }

  async getRblxSwapCleanStatus(): Promise<{ success: boolean; status: RblxSwapCleanStatus; error?: string }> {
    return this.request<{ success: boolean; status: RblxSwapCleanStatus; error?: string }>('/api/rblxswap/clean-status');
  }

  async getRblxSwapAdapters(): Promise<{ success: boolean; adapters: RblxSwapAdapter[]; error?: string }> {
    return this.request<{ success: boolean; adapters: RblxSwapAdapter[]; error?: string }>('/api/rblxswap/adapters');
  }

  async spoofRblxMac(options: {
    adapter_desc?: string;
    adapter_name?: string;
    mac?: string;
    all_adapters?: boolean;
    mirror_oui?: boolean;
    restart?: boolean;
  }): Promise<{ success: boolean; mac?: string; results?: any[]; error?: string }> {
    return this.request('/api/rblxswap/spoof-mac', 'POST', options);
  }

  async resetRblxMac(options: {
    adapter_desc?: string;
    adapter_name?: string;
    all_adapters?: boolean;
    restart?: boolean;
  }): Promise<{ success: boolean; results?: any[]; error?: string }> {
    return this.request('/api/rblxswap/reset-mac', 'POST', options);
  }

  async restartRblxAdapter(adapterName: string): Promise<{ success: boolean; error?: string }> {
    return this.request('/api/rblxswap/restart-adapter', 'POST', { adapter_name: adapterName });
  }

  async dhcpRblxRefresh(): Promise<{ success: boolean; error?: string }> {
    return this.request('/api/rblxswap/dhcp-refresh', 'POST');
  }

  async spoofRblxHwid(options: { guids?: boolean; volume?: boolean }): Promise<{ success: boolean; results?: any[]; error?: string }> {
    return this.request('/api/rblxswap/spoof-hwid', 'POST', options);
  }

  async restoreRblxIdentifiers(options: { guids?: boolean; mac?: boolean; volume?: boolean }): Promise<any> {
    return this.request('/api/rblxswap/restore', 'POST', options);
  }

  async createRblxRestorePoint(desc?: string): Promise<{ ok?: boolean; message?: string; error?: string }> {
    return this.request('/api/rblxswap/restore-point', 'POST', { desc });
  }

  async spoofRblxAll(options: {
    guids?: boolean;
    volume?: boolean;
    mac?: boolean;
    all_adapters?: boolean;
    adapter_desc?: string;
    adapter_name?: string;
    custom_mac?: string;
    mirror_oui?: boolean;
    restart?: boolean;
    create_restore_point?: boolean;
    restore_point_desc?: string;
  }): Promise<{
    success: boolean;
    restore_point?: any;
    hwid?: any[];
    mac?: any[];
    single_mac?: string;
    error?: string;
  }> {
    return this.request('/api/rblxswap/spoof-all', 'POST', options);
  }

  async getChromiumStatus(): Promise<{ success: boolean; status: ChromiumStatus; error?: string }> {
    return this.request<{ success: boolean; status: ChromiumStatus; error?: string }>('/browser/chromium/status');
  }

  async startChromiumDownload(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/browser/chromium/download', 'POST');
  }

  async uninstallChromium(): Promise<{ success: boolean; message?: string; error?: string }> {
    return this.request<{ success: boolean; message?: string; error?: string }>('/browser/chromium/uninstall', 'POST');
  }
}

export interface ChromiumStatus {
  installed: boolean;
  version: string;
  binary_path: string;
  driver_path: string;
  downloading: boolean;
  status_text: string;
  progress: number;
  downloaded_bytes: number;
  total_bytes: number;
  success?: boolean | null;
  error?: string | null;
}

export interface RblxSwapAdapter {
  name: string;
  description: string;
  mac: string;
  status: string;
  spoofed: boolean;
  network_address?: string;
}

export interface RblxSwapAnticheat {
  name: string;
  service?: string;
  process?: string;
  steps: string[];
}

export interface RblxSwapBackupInfo {
  exists: boolean;
  saved_at?: string;
  has?: {
    guids: boolean;
    mac: boolean;
    volume: boolean;
  };
  serials?: {
    machine_guid?: string;
    volume?: string;
  };
}

export interface RblxSwapStatus {
  success: boolean;
  elevated: boolean;
  backup: RblxSwapBackupInfo;
  anticheats: RblxSwapAnticheat[];
  error?: string;
}

export interface RblxSwapCleanOptions {
  preserve_settings?: boolean;
  preserve_fastflags?: boolean;
  preserve_app_settings?: boolean;
  delete_studio?: boolean;
  purge_auth?: boolean;
  weblauncher_dir?: string;
}

export interface RblxSwapCleanLog {
  level: 'info' | 'success' | 'warn' | 'error';
  msg: string;
}

export interface RblxSwapCleanResult {
  success: boolean;
  logs: RblxSwapCleanLog[];
  error?: string;
}

export interface RblxSwapCleanStatus {
  active: boolean;
  progress: number;
  step: string;
  logs?: RblxSwapCleanLog[];
  error?: string;
}

export const apiService = new ApiService();