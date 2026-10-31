// The brand kit every template reads its defaults from: edit brand.json, and titles, captions, looks and
// layouts follow; a prop still overrides any of it. Keys missing from brand.json keep the defaults below.
// Fonts are CSS stacks: load the first family in the project; the rest are macOS faces it falls back to.
// `logo` is a path under public/ for staticFile(); `handle` is the account name as it should read on screen.
// Remotion's bundler imports JSON as is; for tsc set "resolveJsonModule": true in tsconfig.json.
import brandJson from './brand.json';

export type Brand = {
	fonts: {sans: string; serif: string; display: string; caption: string};
	/** text: words over footage. accent: shapes behind text (highlight box, counter, sticker chip).
	 *  highlight: the word being said. paper/ink: cards and the text on them. shadow: a CSS text-shadow. */
	colors: {text: string; accent: string; highlight: string; paper: string; ink: string; shadow: string};
	caption: {size: number; weight: number; lowercase: boolean};
	handle: string;
	logo: string;
};

export const DEFAULTS: Brand = {
	fonts: {
		sans: '"TikTok Sans", "SF Pro Display", -apple-system, Arial, sans-serif',
		serif: '"Playfair Display", "Bodoni 72", Didot, Georgia, serif',
		display: '"Bodoni Moda", "Bodoni 72", Didot, "Playfair Display", serif',
		caption: '"TikTok Sans", "SF Pro Display", -apple-system, Arial, sans-serif',
	},
	colors: {
		text: '#FFFFFF',
		accent: '#6C4DF6',
		highlight: '#FFD84D',
		paper: '#F4EEE3',
		ink: '#1B1B1B',
		shadow: '0 1px 3px rgba(0, 0, 0, 0.35), 0 2px 14px rgba(0, 0, 0, 0.45)',
	},
	caption: {size: 76, weight: 700, lowercase: false},
	handle: '',
	logo: '',
};

type Loose<T> = {[K in keyof T]?: T[K] | null};

/** `base` with every key `top` sets (null and missing keys keep the base). */
const over = <T extends object>(base: T, top?: Loose<T> | null): T => {
	const out = {...base};
	for (const [k, v] of Object.entries(top ?? {})) {
		if (v !== null && v !== undefined && k in base) (out as Record<string, unknown>)[k] = v;
	}
	return out;
};

const json = brandJson as {
	fonts?: Loose<Brand['fonts']>;
	colors?: Loose<Brand['colors']>;
	caption?: Loose<Brand['caption']>;
	handle?: string | null;
	logo?: string | null;
};

export const BRAND: Brand = {
	fonts: over(DEFAULTS.fonts, json.fonts),
	colors: over(DEFAULTS.colors, json.colors),
	caption: over(DEFAULTS.caption, json.caption),
	handle: json.handle ?? DEFAULTS.handle,
	logo: json.logo ?? DEFAULTS.logo,
};

/** Where text may sit on a 1080x1920 frame: under the platforms' top bar, above their caption and username,
 *  left of the right-hand buttons. Components keep text inside it unless a prop moves it. */
export const SAFE = {x0: 90, x1: 890, y0: 290, y1: 1400};
