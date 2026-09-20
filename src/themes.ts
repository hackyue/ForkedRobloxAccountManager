import { updateAppThemeIcons } from './colorWashIcon';

export interface ThemeColors {
  bg: string;
  bg2: string;
  card: string;
  cardAlt: string;
  border: string;
  borderSoft: string;
  fg: string;
  fg2: string;
  fg3: string;
  muted: string;
  primary: string;
  primaryDim: string;
  accent: string;
  accentAlt: string;
  hoverBg: string;
  listBg: string;
  listSelect: string;
}

export interface CustomBackgroundSettings {
  enabled: boolean;
  type: 'none' | 'preset' | 'custom' | 'url';
  presetId?: string;
  customImage?: string;
  blur: number;
  opacity: number;
  glassmorphism: 'none' | 'subtle' | 'medium' | 'high';
  fit: 'cover' | 'contain' | 'repeat' | 'center';
}

export interface Theme {
  id: string;
  name: string;
  category: 'Modern' | 'Cyber' | 'Vibrant' | 'OLED' | 'Retro' | 'Custom';
  description: string;
  author?: string;
  isCustom?: boolean;
  colors: ThemeColors;
  accentSwatches: string[];
  background?: Partial<CustomBackgroundSettings>;
}

export const THEMES: Record<string, Theme> = {
  'default-dark': {
    id: 'default-dark',
    name: 'Default Dark',
    category: 'Modern',
    description: 'Clean obsidian dark with electric blue accents',
    colors: {
      bg: '#0d0f12',
      bg2: '#15181d',
      card: '#15181d',
      cardAlt: '#1a1e24',
      border: '#262b33',
      borderSoft: '#20242b',
      fg: '#e7e9ec',
      fg2: '#a1a7b3',
      fg3: '#7d8590',
      muted: '#7d8590',
      primary: '#4f8ef7',
      primaryDim: 'rgba(79, 142, 247, 0.15)',
      accent: '#4f8ef7',
      accentAlt: '#38bdf8',
      hoverBg: '#1f242c',
      listBg: '#111418',
      listSelect: 'rgba(79, 142, 247, 0.18)'
    },
    accentSwatches: ['#4f8ef7', '#34d399', '#f472b6', '#f59e0b', '#a78bfa', '#38bdf8']
  },
  'synapse-neon': {
    id: 'synapse-neon',
    name: 'Synapse Neon',
    category: 'Cyber',
    description: 'Midnight violet with glowing neon cyan and electric purple',
    colors: {
      bg: '#05050b',
      bg2: '#0f0f1c',
      card: '#13132b',
      cardAlt: '#1c1c3a',
      border: '#5f2eea',
      borderSoft: '#2a2456',
      fg: '#f6f7fb',
      fg2: '#d3d5f0',
      fg3: '#b7b9d6',
      muted: '#8b8da8',
      primary: '#8d5cf7',
      primaryDim: 'rgba(141, 92, 247, 0.18)',
      accent: '#18e0ff',
      accentAlt: '#8d5cf7',
      hoverBg: '#1f1f39',
      listBg: '#161631',
      listSelect: 'rgba(24, 224, 255, 0.18)'
    },
    accentSwatches: ['#8d5cf7', '#18e0ff', '#f43f5e', '#a855f7', '#06b6d4', '#ec4899']
  },
  'scriptware-minimal': {
    id: 'scriptware-minimal',
    name: 'ScriptWare Minimal',
    category: 'Modern',
    description: 'Sleek gunmetal slate with crisp sky blue accents',
    colors: {
      bg: '#111217',
      bg2: '#16171d',
      card: '#1d1f26',
      cardAlt: '#22242c',
      border: '#2a2d36',
      borderSoft: '#20222a',
      fg: '#f0f2f7',
      fg2: '#d0d4e0',
      fg3: '#c8ccd8',
      muted: '#858b99',
      primary: '#6ab0ff',
      primaryDim: 'rgba(106, 176, 255, 0.16)',
      accent: '#6ab0ff',
      accentAlt: '#d9dde8',
      hoverBg: '#272a34',
      listBg: '#1c1e25',
      listSelect: 'rgba(106, 176, 255, 0.18)'
    },
    accentSwatches: ['#6ab0ff', '#60a5fa', '#34d399', '#818cf8', '#f472b6', '#38bdf8']
  },
  'vapor': {
    id: 'vapor',
    name: 'Vapor Wave',
    category: 'Cyber',
    description: 'Deep ocean teal with vivid radiant cyan glows',
    colors: {
      bg: '#042f33',
      bg2: '#0a3f4b',
      card: '#0e4c5c',
      cardAlt: '#135b6d',
      border: '#4ef0ff',
      borderSoft: '#186d80',
      fg: '#e7fbff',
      fg2: '#c5f2fa',
      fg3: '#b9e6f0',
      muted: '#7cb5c2',
      primary: '#4ef0ff',
      primaryDim: 'rgba(78, 240, 255, 0.18)',
      accent: '#4ef0ff',
      accentAlt: '#8efaf2',
      hoverBg: '#136374',
      listBg: '#0b3b47',
      listSelect: 'rgba(78, 240, 255, 0.22)'
    },
    accentSwatches: ['#4ef0ff', '#22d3ee', '#38bdf8', '#2dd4bf', '#a78bfa', '#f472b6']
  },
  'potassium-ion': {
    id: 'potassium-ion',
    name: 'Potassium Ion',
    category: 'Vibrant',
    description: 'Rich dark amethyst with radiant energetic gold highlights',
    colors: {
      bg: '#050406',
      bg2: '#0b0a0f',
      card: '#120f18',
      cardAlt: '#1d1723',
      border: '#ffd500',
      borderSoft: '#3a2d47',
      fg: '#fef9c3',
      fg2: '#faeab3',
      fg3: '#fcd34d',
      muted: '#a39563',
      primary: '#ffd500',
      primaryDim: 'rgba(255, 213, 0, 0.18)',
      accent: '#ffd500',
      accentAlt: '#fffd8c',
      hoverBg: '#251c2d',
      listBg: '#151019',
      listSelect: 'rgba(255, 213, 0, 0.22)'
    },
    accentSwatches: ['#ffd500', '#f59e0b', '#fbbf24', '#f97316', '#eab308', '#ec4899']
  },
  'midnight-matrix': {
    id: 'midnight-matrix',
    name: 'Midnight Matrix',
    category: 'Cyber',
    description: 'True black matrix terminal with glowing emerald green',
    colors: {
      bg: '#000000',
      bg2: '#030b0c',
      card: '#041416',
      cardAlt: '#062024',
      border: '#00ff7f',
      borderSoft: '#0c353a',
      fg: '#9cffc7',
      fg2: '#b8ffda',
      fg3: '#5dd39b',
      muted: '#3b8a65',
      primary: '#00ff7f',
      primaryDim: 'rgba(0, 255, 127, 0.18)',
      accent: '#00ff7f',
      accentAlt: '#6bffa8',
      hoverBg: '#082d32',
      listBg: '#031214',
      listSelect: 'rgba(0, 255, 127, 0.22)'
    },
    accentSwatches: ['#00ff7f', '#10b981', '#22c55e', '#34d399', '#06b6d4', '#84cc16']
  },
  'aurora-fade': {
    id: 'aurora-fade',
    name: 'Aurora Fade',
    category: 'Vibrant',
    description: 'Deep plum twilight with ethereal pastel pink & lavender',
    colors: {
      bg: '#2b153d',
      bg2: '#311846',
      card: '#381d52',
      cardAlt: '#432263',
      border: '#f472b6',
      borderSoft: '#562a7e',
      fg: '#f9e8ff',
      fg2: '#eed4f7',
      fg3: '#d8b4fe',
      muted: '#a88fc2',
      primary: '#ff99d6',
      primaryDim: 'rgba(255, 153, 214, 0.2)',
      accent: '#ff99d6',
      accentAlt: '#b8a2ff',
      hoverBg: '#4b2670',
      listBg: '#341b4c',
      listSelect: 'rgba(255, 153, 214, 0.25)'
    },
    accentSwatches: ['#ff99d6', '#f472b6', '#c084fc', '#e879f9', '#a855f7', '#fb7185']
  },
  'chromepulse': {
    id: 'chromepulse',
    name: 'ChromePulse',
    category: 'Modern',
    description: 'Steel titanium alloy with electric sky blue pulse',
    colors: {
      bg: '#1a1c20',
      bg2: '#212428',
      card: '#262a2f',
      cardAlt: '#2d3238',
      border: '#7dd3ff',
      borderSoft: '#3d444d',
      fg: '#f2f5ff',
      fg2: '#d8dfed',
      fg3: '#cdd5e0',
      muted: '#87919e',
      primary: '#58c5ff',
      primaryDim: 'rgba(88, 197, 255, 0.18)',
      accent: '#58c5ff',
      accentAlt: '#88d8ff',
      hoverBg: '#343941',
      listBg: '#24282e',
      listSelect: 'rgba(88, 197, 255, 0.22)'
    },
    accentSwatches: ['#58c5ff', '#38bdf8', '#60a5fa', '#22d3ee', '#818cf8', '#4ade80']
  },
  'stardust-os': {
    id: 'stardust-os',
    name: 'Stardust OS',
    category: 'Cyber',
    description: 'Cosmic nebula black with vivid starlight lavender glow',
    colors: {
      bg: '#05030a',
      bg2: '#0b0714',
      card: '#100a1c',
      cardAlt: '#170f29',
      border: '#d8b4fe',
      borderSoft: '#301c4e',
      fg: '#f0e7ff',
      fg2: '#dccaff',
      fg3: '#cdb4ff',
      muted: '#8e7aa8',
      primary: '#b46bff',
      primaryDim: 'rgba(180, 107, 255, 0.18)',
      accent: '#b46bff',
      accentAlt: '#7dd3ff',
      hoverBg: '#1f1435',
      listBg: '#0f0a1b',
      listSelect: 'rgba(180, 107, 255, 0.22)'
    },
    accentSwatches: ['#b46bff', '#a855f7', '#c084fc', '#818cf8', '#ec4899', '#38bdf8']
  },
  'tokyo-night': {
    id: 'tokyo-night',
    name: 'Tokyo Night',
    category: 'Modern',
    description: 'Atmospheric Tokyo indigo with neon blue and cyan accents',
    colors: {
      bg: '#1a1b26',
      bg2: '#1f2335',
      card: '#24283b',
      cardAlt: '#2f354a',
      border: '#414868',
      borderSoft: '#292e42',
      fg: '#c0caf5',
      fg2: '#a9b1d6',
      fg3: '#7aa2f7',
      muted: '#565f89',
      primary: '#7aa2f7',
      primaryDim: 'rgba(122, 162, 247, 0.16)',
      accent: '#7dcfff',
      accentAlt: '#bb9af7',
      hoverBg: '#282e44',
      listBg: '#1e2233',
      listSelect: 'rgba(122, 162, 247, 0.18)'
    },
    accentSwatches: ['#7aa2f7', '#7dcfff', '#bb9af7', '#73daca', '#ff9e64', '#f7768e']
  },
  'oled-black': {
    id: 'oled-black',
    name: 'OLED Pure Black',
    category: 'OLED',
    description: 'Pure zero-pixel black with high-contrast razor sharp borders',
    colors: {
      bg: '#000000',
      bg2: '#0a0a0a',
      card: '#121212',
      cardAlt: '#181818',
      border: '#282828',
      borderSoft: '#1e1e1e',
      fg: '#ffffff',
      fg2: '#e0e0e0',
      fg3: '#a0a0a0',
      muted: '#707070',
      primary: '#3b82f6',
      primaryDim: 'rgba(59, 130, 246, 0.2)',
      accent: '#60a5fa',
      accentAlt: '#ffffff',
      hoverBg: '#202020',
      listBg: '#0a0a0a',
      listSelect: 'rgba(59, 130, 246, 0.25)'
    },
    accentSwatches: ['#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#ffffff']
  },
  'crimson-abyss': {
    id: 'crimson-abyss',
    name: 'Crimson Abyss',
    category: 'Cyber',
    description: 'Deep obsidian red with fiery crimson glow',
    colors: {
      bg: '#0d0505',
      bg2: '#160909',
      card: '#200d0d',
      cardAlt: '#2a1212',
      border: '#ef4444',
      borderSoft: '#451a1a',
      fg: '#ffe4e4',
      fg2: '#fca5a5',
      fg3: '#f87171',
      muted: '#994444',
      primary: '#ef4444',
      primaryDim: 'rgba(239, 68, 68, 0.18)',
      accent: '#f87171',
      accentAlt: '#ff8888',
      hoverBg: '#351616',
      listBg: '#180a0a',
      listSelect: 'rgba(239, 68, 68, 0.22)'
    },
    accentSwatches: ['#ef4444', '#dc2626', '#f97316', '#fb7185', '#e11d48', '#f43f5e']
  },
  'nord-arctic': {
    id: 'nord-arctic',
    name: 'Nord Arctic',
    category: 'Modern',
    description: 'Scandinavian arctic night with polar ice blue accents',
    colors: {
      bg: '#242933',
      bg2: '#2e3440',
      card: '#3b4252',
      cardAlt: '#434c5e',
      border: '#4c566a',
      borderSoft: '#3b4252',
      fg: '#eceff4',
      fg2: '#e5e9f0',
      fg3: '#d8dee9',
      muted: '#7e889b',
      primary: '#88c0d0',
      primaryDim: 'rgba(136, 192, 208, 0.18)',
      accent: '#81a1c1',
      accentAlt: '#8fbcbb',
      hoverBg: '#4c566a',
      listBg: '#2e3440',
      listSelect: 'rgba(136, 192, 208, 0.2)'
    },
    accentSwatches: ['#88c0d0', '#81a1c1', '#5e81ac', '#8fbcbb', '#a3be8c', '#b48ead']
  },
  'dracula': {
    id: 'dracula',
    name: 'Dracula Dark',
    category: 'Retro',
    description: 'Famous vampire palette with vibrant purple, pink and cyan',
    colors: {
      bg: '#1e1f29',
      bg2: '#282a36',
      card: '#343746',
      cardAlt: '#44475a',
      border: '#6272a4',
      borderSoft: '#3e4254',
      fg: '#f8f8f2',
      fg2: '#e2e2dc',
      fg3: '#bd93f9',
      muted: '#6272a4',
      primary: '#bd93f9',
      primaryDim: 'rgba(189, 147, 249, 0.18)',
      accent: '#ff79c6',
      accentAlt: '#8be9fd',
      hoverBg: '#44475a',
      listBg: '#282a36',
      listSelect: 'rgba(189, 147, 249, 0.22)'
    },
    accentSwatches: ['#bd93f9', '#ff79c6', '#8be9fd', '#50fa7b', '#ffb86c', '#ff5555']
  }
};

export interface BackgroundPreset {
  id: string;
  name: string;
  css: string;
  previewGradient: string;
}

export const BACKGROUND_PRESETS: BackgroundPreset[] = [
  {
    id: 'space-nebula',
    name: 'Deep Space Nebula',
    css: 'radial-gradient(ellipse at 20% 20%, rgba(99, 102, 241, 0.25) 0%, transparent 50%), radial-gradient(ellipse at 80% 80%, rgba(236, 72, 153, 0.2) 0%, transparent 50%), radial-gradient(ellipse at 50% 50%, rgba(14, 165, 233, 0.15) 0%, transparent 70%), #060810',
    previewGradient: 'linear-gradient(135deg, #060810 0%, #312e81 40%, #db2777 75%, #0284c7 100%)'
  },
  {
    id: 'cyber-mesh',
    name: 'Cyber Mesh',
    css: 'radial-gradient(circle at 10% 20%, rgba(0, 240, 255, 0.2) 0%, transparent 40%), radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.25) 0%, transparent 45%), linear-gradient(180deg, #080a12 0%, #0c0f1c 100%)',
    previewGradient: 'linear-gradient(135deg, #080a12 0%, #00f0ff 50%, #a855f7 100%)'
  },
  {
    id: 'aurora',
    name: 'Ambient Aurora',
    css: 'radial-gradient(circle at 50% 0%, rgba(52, 211, 153, 0.22) 0%, transparent 55%), radial-gradient(circle at 85% 30%, rgba(99, 102, 241, 0.22) 0%, transparent 60%), #070d14',
    previewGradient: 'linear-gradient(135deg, #070d14 0%, #34d399 50%, #6366f1 100%)'
  },
  {
    id: 'abstract-waves',
    name: 'Abstract Waves',
    css: 'radial-gradient(at 0% 100%, rgba(244, 63, 94, 0.2) 0px, transparent 50%), radial-gradient(at 100% 0%, rgba(14, 165, 233, 0.25) 0px, transparent 50%), #0d1117',
    previewGradient: 'linear-gradient(135deg, #0d1117 0%, #f43f5e 50%, #0ea5e9 100%)'
  },
  {
    id: 'carbon',
    name: 'Carbon Grid',
    css: 'radial-gradient(#1f293d 1px, transparent 1px), radial-gradient(#1f293d 1px, #0b0e14 1px)',
    previewGradient: 'linear-gradient(135deg, #0b0e14 0%, #1f293d 100%)'
  },
  {
    id: 'hexagons',
    name: 'Tech Hex',
    css: 'radial-gradient(circle at 50% 50%, rgba(79, 142, 247, 0.15) 0%, transparent 65%), linear-gradient(135deg, #090b10 0%, #111520 100%)',
    previewGradient: 'linear-gradient(135deg, #090b10 0%, #1e3a8a 100%)'
  },
  {
    id: 'sunset-glow',
    name: 'Sunset Glow',
    css: 'radial-gradient(circle at 50% 100%, rgba(249, 115, 22, 0.24) 0%, transparent 60%), radial-gradient(circle at 20% 20%, rgba(168, 85, 247, 0.22) 0%, transparent 50%), #0e0a17',
    previewGradient: 'linear-gradient(135deg, #0e0a17 0%, #f97316 50%, #a855f7 100%)'
  },
  {
    id: 'matrix-dots',
    name: 'Matrix Flow',
    css: 'radial-gradient(circle at 50% 0%, rgba(0, 255, 102, 0.2) 0%, transparent 50%), radial-gradient(circle at 100% 100%, rgba(16, 185, 129, 0.16) 0%, transparent 50%), #040906',
    previewGradient: 'linear-gradient(135deg, #040906 0%, #00ff66 50%, #10b981 100%)'
  }
];

let currentThemeId = 'default-dark';
let currentCustomAccent: string | null = null;
const listeners: Array<(theme: Theme) => void> = [];

export function loadCustomThemes(): Record<string, Theme> {
  try {
    const raw = localStorage.getItem('fram_custom_themes');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return parsed;
      }
    }
  } catch (e) {
  }
  return {};
}

export let CUSTOM_THEMES: Record<string, Theme> = loadCustomThemes();

export function reloadCustomThemes(): void {
  CUSTOM_THEMES = loadCustomThemes();
}

export function saveCustomTheme(theme: Theme): void {
  theme.isCustom = true;
  if (!theme.category) theme.category = 'Custom';
  CUSTOM_THEMES[theme.id] = theme;
  try {
    localStorage.setItem('fram_custom_themes', JSON.stringify(CUSTOM_THEMES));
  } catch (e) {
  }
}

export function deleteCustomTheme(id: string): boolean {
  if (CUSTOM_THEMES[id]) {
    delete CUSTOM_THEMES[id];
    try {
      localStorage.setItem('fram_custom_themes', JSON.stringify(CUSTOM_THEMES));
    } catch (e) {
    }
    if (currentThemeId === id) {
      applyTheme('default-dark');
    }
    return true;
  }
  return false;
}

export function exportThemeJson(theme: Theme): string {
  const exportData = {
    fram_theme_version: 1,
    id: theme.id,
    name: theme.name,
    category: theme.category || 'Custom',
    description: theme.description || '',
    author: theme.author || 'Community Creator',
    colors: theme.colors,
    accentSwatches: theme.accentSwatches || [theme.colors.primary, theme.colors.accent],
    background: theme.background || undefined
  };
  return JSON.stringify(exportData, null, 2);
}

export function importThemeJson(jsonStr: string): Theme {
  const data = JSON.parse(jsonStr);
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid theme file format');
  }
  if (!data.name || typeof data.name !== 'string') {
    throw new Error('Theme is missing a valid name');
  }
  if (!data.colors || typeof data.colors !== 'object') {
    throw new Error('Theme is missing color definitions');
  }

  const reqColors = ['bg', 'bg2', 'card', 'cardAlt', 'border', 'fg', 'primary', 'accent'];
  for (const c of reqColors) {
    if (!data.colors[c]) {
      throw new Error('Theme is missing required color: ' + c);
    }
  }

  const cleanId = (data.id && typeof data.id === 'string')
    ? 'custom-' + data.id.replace(/^custom-/, '').toLowerCase().replace(/[^a-z0-9-_]/g, '-')
    : 'custom-' + Date.now().toString(36);

  const newTheme: Theme = {
    id: cleanId,
    name: data.name.trim(),
    category: 'Custom',
    description: (data.description || 'Custom community theme').trim(),
    author: (data.author || 'Community Creator').trim(),
    isCustom: true,
    colors: {
      bg: data.colors.bg,
      bg2: data.colors.bg2 || data.colors.bg,
      card: data.colors.card || data.colors.bg2,
      cardAlt: data.colors.cardAlt || data.colors.card,
      border: data.colors.border,
      borderSoft: data.colors.borderSoft || data.colors.border,
      fg: data.colors.fg,
      fg2: data.colors.fg2 || data.colors.fg,
      fg3: data.colors.fg3 || data.colors.fg2 || data.colors.fg,
      muted: data.colors.muted || data.colors.fg2 || '#7d8590',
      primary: data.colors.primary,
      primaryDim: data.colors.primaryDim || hexToRgba(data.colors.primary, 0.16),
      accent: data.colors.accent || data.colors.primary,
      accentAlt: data.colors.accentAlt || data.colors.primary,
      hoverBg: data.colors.hoverBg || data.colors.cardAlt || '#1f242c',
      listBg: data.colors.listBg || data.colors.bg,
      listSelect: data.colors.listSelect || hexToRgba(data.colors.primary, 0.2)
    },
    accentSwatches: Array.isArray(data.accentSwatches) && data.accentSwatches.length > 0
      ? data.accentSwatches
      : [data.colors.primary, data.colors.accent, '#38bdf8', '#34d399', '#f472b6', '#f59e0b'],
    background: data.background
  };

  saveCustomTheme(newTheme);
  return newTheme;
}

export function getCustomThemes(): Theme[] {
  return Object.values(CUSTOM_THEMES);
}

export function getTheme(id: string): Theme {
  return CUSTOM_THEMES[id] || THEMES[id] || THEMES['default-dark'];
}

export function getAllThemes(): Theme[] {
  return [...Object.values(THEMES), ...Object.values(CUSTOM_THEMES)];
}

export function getCurrentThemeId(): string {
  return currentThemeId;
}

export function getCurrentCustomAccent(): string | null {
  return currentCustomAccent;
}

export function getCurrentTheme(): Theme {
  return getTheme(currentThemeId);
}

export function subscribeThemeChange(callback: (theme: Theme) => void): () => void {
  listeners.push(callback);
  return () => {
    const idx = listeners.indexOf(callback);
    if (idx !== -1) listeners.splice(idx, 1);
  };
}

const DEFAULT_BG_SETTINGS: CustomBackgroundSettings = {
  enabled: false,
  type: 'none',
  presetId: 'space-nebula',
  customImage: '',
  blur: 0,
  opacity: 100,
  glassmorphism: 'medium',
  fit: 'cover'
};

export function getBackgroundSettings(): CustomBackgroundSettings {
  try {
    const raw = localStorage.getItem('fram_custom_bg');
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...DEFAULT_BG_SETTINGS, ...parsed };
    }
  } catch (e) {
  }
  return { ...DEFAULT_BG_SETTINGS };
}

export function saveBackgroundSettings(settings: CustomBackgroundSettings): void {
  try {
    localStorage.setItem('fram_custom_bg', JSON.stringify(settings));
  } catch (e) {
  }
  applyBackground(settings);
}

function updateThemeGlassVariables(settings: CustomBackgroundSettings): void {
  const root = document.documentElement;
  const theme = getCurrentTheme();
  const colors = theme.colors;

  const isEnabled = settings.enabled && settings.type !== 'none' && (settings.type !== 'custom' || !!settings.customImage);

  if (!isEnabled) {
    root.style.setProperty('--bg', colors.bg);
    root.style.setProperty('--bg-2', colors.bg2);
    root.style.setProperty('--card', colors.card);
    root.style.setProperty('--card-alt', colors.cardAlt);
    root.style.setProperty('--border', colors.border);
    root.style.setProperty('--border-soft', colors.borderSoft);
    return;
  }

  const level = settings.glassmorphism || 'medium';
  let bgAlpha = 0.22;
  let bg2Alpha = 0.18;
  let cardAlpha = 0.20;
  let cardAltAlpha = 0.15;
  let borderAlpha = 0.20;
  let borderSoftAlpha = 0.12;

  if (level === 'subtle') {
    bgAlpha = 0.40;
    bg2Alpha = 0.35;
    cardAlpha = 0.36;
    cardAltAlpha = 0.30;
    borderAlpha = 0.28;
    borderSoftAlpha = 0.18;
  } else if (level === 'high') {
    bgAlpha = 0.08;
    bg2Alpha = 0.05;
    cardAlpha = 0.08;
    cardAltAlpha = 0.05;
    borderAlpha = 0.12;
    borderSoftAlpha = 0.08;
  } else if (level === 'none') {
    bgAlpha = 0.28;
    bg2Alpha = 0.22;
    cardAlpha = 0.25;
    cardAltAlpha = 0.18;
    borderAlpha = 0.22;
    borderSoftAlpha = 0.14;
  }

  root.style.setProperty('--bg', hexToRgba(colors.bg, bgAlpha));
  root.style.setProperty('--bg-2', hexToRgba(colors.bg2, bg2Alpha));
  root.style.setProperty('--card', hexToRgba(colors.card, cardAlpha));
  root.style.setProperty('--card-alt', hexToRgba(colors.cardAlt, cardAltAlpha));
  root.style.setProperty('--border', hexToRgba(colors.border, borderAlpha));
  root.style.setProperty('--border-soft', hexToRgba(colors.borderSoft, borderSoftAlpha));
}

export function applyBackground(settingsInput?: Partial<CustomBackgroundSettings>): void {
  const settings = { ...getBackgroundSettings(), ...(settingsInput || {}) };
  const root = document.documentElement;

  let bgLayer = document.getElementById('custom-bg-layer');
  if (!bgLayer) {
    bgLayer = document.createElement('div');
    bgLayer.id = 'custom-bg-layer';
    document.body.prepend(bgLayer);
  }

  const blurVal = Math.max(0, Math.round(settings.blur || 0));
  root.setAttribute('data-glass', settings.glassmorphism || 'none');
  root.setAttribute('data-bg-blur', String(blurVal));

  if (!settings.enabled || settings.type === 'none' || (settings.type === 'custom' && !settings.customImage)) {
    bgLayer.style.display = 'none';
    bgLayer.style.backgroundImage = 'none';
    bgLayer.style.background = 'none';
    document.body.classList.remove('has-custom-bg');
    root.removeAttribute('data-has-custom-bg');
    root.removeAttribute('data-bg-blur');
    root.setAttribute('data-glass', 'none');
    updateThemeGlassVariables(settings);
    return;
  }

  bgLayer.style.display = 'block';
  bgLayer.style.opacity = String(Math.max(0.05, Math.min(1, (settings.opacity ?? 100) / 100)));
  bgLayer.style.filter = blurVal > 0 ? `blur(${blurVal}px)` : 'none';

  if (settings.type === 'preset') {
    const preset = BACKGROUND_PRESETS.find(p => p.id === settings.presetId) || BACKGROUND_PRESETS[0];
    bgLayer.style.background = preset.css;
    bgLayer.style.backgroundSize = 'cover';
    bgLayer.style.backgroundPosition = 'center';
    bgLayer.style.backgroundRepeat = 'no-repeat';
    document.body.classList.add('has-custom-bg');
    root.setAttribute('data-has-custom-bg', 'true');
  } else if (settings.type === 'custom' || settings.type === 'url') {
    if (settings.customImage) {
      bgLayer.style.background = '';
      bgLayer.style.backgroundImage = `url("${settings.customImage}")`;
      if (settings.fit === 'repeat') {
        bgLayer.style.backgroundSize = 'auto';
        bgLayer.style.backgroundPosition = 'top left';
        bgLayer.style.backgroundRepeat = 'repeat';
      } else if (settings.fit === 'center') {
        bgLayer.style.backgroundSize = 'auto';
        bgLayer.style.backgroundPosition = 'center';
        bgLayer.style.backgroundRepeat = 'no-repeat';
      } else if (settings.fit === 'contain') {
        bgLayer.style.backgroundSize = 'contain';
        bgLayer.style.backgroundPosition = 'center';
        bgLayer.style.backgroundRepeat = 'no-repeat';
      } else {
        bgLayer.style.backgroundSize = 'cover';
        bgLayer.style.backgroundPosition = 'center';
        bgLayer.style.backgroundRepeat = 'no-repeat';
      }
      document.body.classList.add('has-custom-bg');
      root.setAttribute('data-has-custom-bg', 'true');
    } else {
      bgLayer.style.display = 'none';
      document.body.classList.remove('has-custom-bg');
      root.removeAttribute('data-has-custom-bg');
    }
  }

  updateThemeGlassVariables(settings);
}

export function applyTheme(themeId: string, customAccent?: string, force: boolean = false): Theme {
  const theme = getTheme(themeId);
  const targetAccent = customAccent || null;

  if (!force && currentThemeId === theme.id && currentCustomAccent === targetAccent) {
    return theme;
  }

  currentThemeId = theme.id;
  currentCustomAccent = targetAccent;

  const root = document.documentElement;
  const colors = theme.colors;
  const primaryColor = customAccent || colors.primary;

  let primaryDim = colors.primaryDim;
  if (customAccent) {
    primaryDim = hexToRgba(customAccent, 0.16);
  }

  root.style.setProperty('--bg', colors.bg);
  root.style.setProperty('--bg-2', colors.bg2);
  root.style.setProperty('--card', colors.card);
  root.style.setProperty('--card-alt', colors.cardAlt);
  root.style.setProperty('--border', colors.border);
  root.style.setProperty('--border-soft', colors.borderSoft);
  root.style.setProperty('--fg', colors.fg);
  root.style.setProperty('--fg-2', colors.fg2);
  root.style.setProperty('--fg-3', colors.fg3);
  root.style.setProperty('--muted', colors.muted);
  root.style.setProperty('--primary', primaryColor);
  root.style.setProperty('--primary-dim', primaryDim);
  root.style.setProperty('--accent', customAccent || colors.accent);
  root.style.setProperty('--accent-alt', colors.accentAlt);
  root.style.setProperty('--hover-bg', colors.hoverBg);
  root.style.setProperty('--list-bg', colors.listBg);
  root.style.setProperty('--list-select', customAccent ? hexToRgba(customAccent, 0.2) : colors.listSelect);

  root.setAttribute('data-theme', theme.id);

  try {
    localStorage.setItem('fram_theme_id', theme.id);
    if (customAccent) {
      localStorage.setItem('fram_accent_color', customAccent);
    } else {
      localStorage.removeItem('fram_accent_color');
    }
  } catch (e) {
  }

  applyBackground();

  for (const fn of listeners) {
    fn(theme);
  }

  updateAppThemeIcons(theme.id, primaryColor).catch(() => { });

  return theme;
}

export function initThemeFromStorage(): Theme {
  try {
    reloadCustomThemes();
    applyBackground();
    const savedTheme = localStorage.getItem('fram_theme_id') || 'default-dark';
    const savedAccent = localStorage.getItem('fram_accent_color') || undefined;
    return applyTheme(savedTheme, savedAccent);
  } catch (e) {
    return applyTheme('default-dark');
  }
}

export function hexToRgba(hex: string, alpha: number): string {
  let c = hex.replace('#', '');
  if (c.length === 3) {
    c = c.split('').map(x => x + x).join('');
  }
  const num = parseInt(c, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
