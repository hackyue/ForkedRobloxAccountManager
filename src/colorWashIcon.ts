export interface ColorWashOptions {
  intensity?: number;
  accentColor?: string;
}

class ColorWashIconEngine {
  private cache: Map<string, string> = new Map();
  private imageExistenceCache: Map<string, boolean> = new Map();
  private colorCache: Map<string, { r: number; g: number; b: number }> = new Map();
  private scratchCanvas: HTMLCanvasElement | null = null;
  private scratchCtx: CanvasRenderingContext2D | null = null;
  private baseImage: HTMLImageElement | null = null;
  private isLoaded: boolean = false;
  private loadPromise: Promise<void> | null = null;

  private async loadBaseImage(): Promise<void> {
    if (this.isLoaded && this.baseImage) return;
    if (this.loadPromise) return this.loadPromise;

    this.loadPromise = new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'Anonymous';
      img.onload = () => {
        this.baseImage = img;
        this.isLoaded = true;
        resolve();
      };
      img.onerror = () => {
        this.isLoaded = false;
        resolve();
      };
      img.src = '/app-logo.png';
    });

    return this.loadPromise;
  }

  private parseCssColorToRgb(colorStr: string): { r: number; g: number; b: number } {
    const cached = this.colorCache.get(colorStr);
    if (cached) return cached;

    try {
      if (!this.scratchCanvas) {
        this.scratchCanvas = document.createElement('canvas');
        this.scratchCanvas.width = 1;
        this.scratchCanvas.height = 1;
        this.scratchCtx = this.scratchCanvas.getContext('2d', { willReadFrequently: true });
      }
      if (!this.scratchCtx) return { r: 79, g: 142, b: 247 };

      this.scratchCtx.fillStyle = colorStr;
      this.scratchCtx.fillRect(0, 0, 1, 1);
      const data = this.scratchCtx.getImageData(0, 0, 1, 1).data;
      const res = { r: data[0], g: data[1], b: data[2] };
      this.colorCache.set(colorStr, res);
      return res;
    } catch (e) {
      return { r: 79, g: 142, b: 247 };
    }
  }

  public async checkImageExists(url: string): Promise<boolean> {
    if (this.imageExistenceCache.has(url)) {
      return this.imageExistenceCache.get(url)!;
    }

    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        this.imageExistenceCache.set(url, true);
        resolve(true);
      };
      img.onerror = () => {
        this.imageExistenceCache.set(url, false);
        resolve(false);
      };
      img.src = url;
    });
  }

  public async getWashedIconDataUrl(color: string, intensity: number = 0.85): Promise<string> {
    const clampedIntensity = Math.max(0, Math.min(1, intensity));
    const cacheKey = `${color.toLowerCase()}_${clampedIntensity.toFixed(2)}`;

    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!;
    }

    await this.loadBaseImage();
    if (!this.baseImage) return '/app-logo.png';

    const width = this.baseImage.naturalWidth || 256;
    const height = this.baseImage.naturalHeight || 256;

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (!ctx) return '/app-logo.png';

    ctx.drawImage(this.baseImage, 0, 0);
    const imgData = ctx.getImageData(0, 0, width, height);
    const data = imgData.data;

    const targetRgb = this.parseCssColorToRgb(color);
    const { r: Tr, g: Tg, b: Tb } = targetRgb;

    for (let i = 0; i < data.length; i += 4) {
      const a = data[i + 3];
      if (a === 0) continue;

      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];

      const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;

      let wr: number, wg: number, wb: number;
      if (lum <= 0.5) {
        const factor = lum / 0.5;
        wr = Tr * factor;
        wg = Tg * factor;
        wb = Tb * factor;
      } else {
        const factor = (lum - 0.5) / 0.5;
        wr = Tr + (255 - Tr) * factor;
        wg = Tg + (255 - Tg) * factor;
        wb = Tb + (255 - Tb) * factor;
      }

      data[i] = Math.round(r * (1 - clampedIntensity) + wr * clampedIntensity);
      data[i + 1] = Math.round(g * (1 - clampedIntensity) + wg * clampedIntensity);
      data[i + 2] = Math.round(b * (1 - clampedIntensity) + wb * clampedIntensity);
    }

    ctx.putImageData(imgData, 0, 0);
    const dataUrl = canvas.toDataURL('image/png');
    this.cache.set(cacheKey, dataUrl);
    return dataUrl;
  }
}

export const colorWashEngine = new ColorWashIconEngine();

const THEME_ICON_FILE_MAP: Record<string, string> = {
  'default-dark': '/ThemeIcons/ICON-modified.png',
  'aurora-fade': '/ThemeIcons/iconAURORAFADE.png',
  'chromepulse': '/ThemeIcons/iconCHROMEPULSE.png',
  'crimson-abyss': '/ThemeIcons/iconCRIMSONABYSS.png',
  'dracula': '/ThemeIcons/iconDACULADARK.png',
  'midnight-matrix': '/ThemeIcons/iconMIDNIGHTMATRIX.png',
  'nord-arctic': '/ThemeIcons/iconNORDARCTIC.png',
  'oled-black': '/ThemeIcons/iconOLEDPUREBLACK.png',
  'potassium-ion': '/ThemeIcons/iconPOTASSIUMION.png',
  'scriptware-minimal': '/ThemeIcons/iconSCRIPTWAREMINIMAL.png',
  'stardust-os': '/ThemeIcons/iconSTARDUSTOS.png',
  'synapse-neon': '/ThemeIcons/iconSYNAPSENEON.png',
  'tokyo-night': '/ThemeIcons/iconTOKYONIGHT.png',
  'vapor': '/ThemeIcons/iconVAPORWAVE.png'
};

let lastAppliedThemeIconTarget = '';

const iconBytesCache = new Map<string, Uint8Array>();
let setIconDebounceTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleWindowIconUpdate(targetSrc: string): void {
  if (setIconDebounceTimer) {
    clearTimeout(setIconDebounceTimer);
    setIconDebounceTimer = null;
  }

  setIconDebounceTimer = setTimeout(async () => {
    try {
      const { appWindow } = await import('@tauri-apps/api/window');
      if (appWindow && appWindow.setIcon) {
        let iconBytes = iconBytesCache.get(targetSrc);
        if (!iconBytes) {
          if (targetSrc.startsWith('data:')) {
            const base64 = targetSrc.split(',')[1];
            if (base64) {
              const binaryString = atob(base64);
              const len = binaryString.length;
              const bytes = new Uint8Array(len);
              for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              iconBytes = bytes;
              iconBytesCache.set(targetSrc, bytes);
            }
          } else {
            const res = await fetch(targetSrc);
            if (res.ok) {
              const buffer = await res.arrayBuffer();
              iconBytes = new Uint8Array(buffer);
              iconBytesCache.set(targetSrc, iconBytes);
            }
          }
        }

        if (iconBytes && iconBytes.length > 0) {
          await appWindow.setIcon(iconBytes);
        }
      }
    } catch (e) {
      console.warn('Failed to update window taskbar icon:', e);
    }
  }, 250);
}

export function getThemeIconUrl(themeId?: string): string {
  if (themeId && THEME_ICON_FILE_MAP[themeId]) {
    return THEME_ICON_FILE_MAP[themeId];
  }
  return '/ThemeIcons/ICON-modified.png';
}

export async function updateAppThemeIcons(themeId?: string, accentColor?: string, intensity: number = 0.85): Promise<void> {
  try {
    let targetSrc = '';

    if (themeId) {
      if (THEME_ICON_FILE_MAP[themeId]) {
        targetSrc = THEME_ICON_FILE_MAP[themeId];
      } else {
        const pngPath = `/theme-icons/${themeId}.png`;
        const icoPath = `/theme-icons/${themeId}.ico`;
        const capPngPath = `/ThemeIcons/${themeId}.png`;
        if (await colorWashEngine.checkImageExists(pngPath)) {
          targetSrc = pngPath;
        } else if (await colorWashEngine.checkImageExists(capPngPath)) {
          targetSrc = capPngPath;
        } else if (await colorWashEngine.checkImageExists(icoPath)) {
          targetSrc = icoPath;
        }
      }
    }

    if (!targetSrc && accentColor) {
      targetSrc = await colorWashEngine.getWashedIconDataUrl(accentColor, intensity);
    }

    if (!targetSrc) {
      targetSrc = getThemeIconUrl(themeId);
    }

    const selectors = '.logo-icon, .loader-app-logo, .setup-brand-icon, .setup-brand img, .titlebar .logo img';
    const elements = document.querySelectorAll<HTMLElement>(selectors);
    elements.forEach(el => {
      if (el.tagName.toLowerCase() === 'img') {
        const img = el as HTMLImageElement;
        if (img.getAttribute('src') !== targetSrc) {
          img.src = targetSrc;
        }
      } else {
        el.style.backgroundImage = `url('${targetSrc}')`;
        el.style.backgroundSize = 'contain';
        el.style.backgroundRepeat = 'no-repeat';
        el.style.backgroundPosition = 'center';
      }
    });

    if (targetSrc !== lastAppliedThemeIconTarget) {
      lastAppliedThemeIconTarget = targetSrc;

      let favicon = document.getElementById('app-favicon') as HTMLLinkElement | null;
      if (!favicon) {
        favicon = document.querySelector('link[rel="icon"], link[rel="shortcut icon"]');
        if (!favicon) {
          favicon = document.createElement('link');
          favicon.id = 'app-favicon';
          favicon.rel = 'icon';
          document.head.appendChild(favicon);
        }
      }
      if (favicon) {
        favicon.href = targetSrc;
      }

      scheduleWindowIconUpdate(targetSrc);
    }
  } catch (e) { }
}

