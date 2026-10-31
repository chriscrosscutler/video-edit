// Set pieces for when a brand asks for energy: zooms, title styles and overlays. One per video, two at most,
// and each shows what is said (the number she says grows as a chart, the app she names sits in a phone).
// Frames are local: place each inside a <Sequence>. `person` props take the cutout from matte.swift --person
// (<OffthreadVideo src={staticFile('person.webm')} transparent />) laid over the same footage.
// Fonts are CSS stacks: load the first family in the project; the rest are macOS faces it falls back to.
// Fonts and colours come from brand.ts (FONTS.didone is the brand's display face); props override them.
import React from 'react';
import {AbsoluteFill, Easing, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND, SAFE} from './brand';

const W = 1080;
const H = 1920;
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const land = Easing.bezier(0.16, 1, 0.3, 1); // soft landing for things arriving
const glide = Easing.bezier(0.65, 0, 0.35, 1); // in-out for camera moves
const SHADOW = BRAND.colors.shadow;
const WHITE = BRAND.colors.text;
export const FONTS = {
	sans: BRAND.fonts.sans,
	serif: BRAND.fonts.serif,
	didone: BRAND.fonts.display,
};

/** [x, y] as fractions of the frame: put zooms and orbits on the face (faces.swift) or the product. */
export type Point = [number, number];
/** [frame, scale] */
export type Key = [number, number];

const at = (p: Point) => `${p[0] * 100}% ${p[1] * 100}%`;

/** Camera moves on the footage inside, eased between keys.
 *  Slow push: [[0, 1], [end, 1.06]]. Punch-in to hide a jump: [[0, 1.12]].
 *  Digital zoom: [[0, 1], [4, 1.3], [14, 1.3], [18, 1.7], [40, 1.7], [48, 1]]. */
export const Zoom: React.FC<{children: React.ReactNode; keys: Key[]; origin?: Point}> = ({
	children,
	keys,
	origin = [0.5, 0.4],
}) => {
	const frame = useCurrentFrame();
	const scale =
		keys.length < 2
			? keys[0][1]
			: interpolate(frame, keys.map((k) => k[0]), keys.map((k) => k[1]), {...clamp, easing: glide});
	return (
		<AbsoluteFill style={{overflow: 'hidden'}}>
			<AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: at(origin)}}>{children}</AbsoluteFill>
		</AbsoluteFill>
	);
};

/** A cut hidden inside a fast push: `a` rushes in to 3x with blur, `b` lands from 1.6x. `cut` is the frame of
 *  the cut and `frames` (12) the whole move. Wrap a video `b` in <Sequence from={cut}> so it starts there. */
export const ZoomThrough: React.FC<{
	a: React.ReactNode;
	b: React.ReactNode;
	cut: number;
	frames?: number;
	origin?: Point;
}> = ({a, b, cut, frames = 12, origin = [0.5, 0.5]}) => {
	const frame = useCurrentFrame();
	const into = interpolate(frame, [cut - frames / 2, cut], [0, 1], {...clamp, easing: Easing.in(Easing.cubic)});
	const out = interpolate(frame, [cut, cut + frames / 2], [1, 0], {...clamp, easing: Easing.out(Easing.cubic)});
	const [node, scale, blur] = frame < cut ? [a, 1 + 2 * into, 14 * into] : [b, 1 + 0.6 * out, 14 * out];
	return (
		<AbsoluteFill style={{overflow: 'hidden'}}>
			<AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: at(origin), filter: `blur(${blur}px)`}}>
				{node}
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

/** Dolly zoom: the room falls away while she holds still. Both layers start at `scale` (1.25) so the room has
 *  space to shrink; the room eases to 1 over the sequence and the cutout stays put. 1.5-3 s, origin on her face. */
export const Vertigo: React.FC<{background: React.ReactNode; person: React.ReactNode; scale?: number; origin?: Point}> = ({
	background,
	person,
	scale = 1.25,
	origin = [0.5, 0.4],
}) => {
	const frame = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const p = interpolate(frame, [0, durationInFrames - 1], [0, 1], {...clamp, easing: glide});
	return (
		<AbsoluteFill style={{overflow: 'hidden'}}>
			<AbsoluteFill style={{transform: `scale(${scale + (1 - scale) * p})`, transformOrigin: at(origin)}}>
				{background}
			</AbsoluteFill>
			<AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: at(origin)}}>{person}</AbsoluteFill>
		</AbsoluteFill>
	);
};

/** The footage shrinks into a phone on a plain backdrop and keeps playing: for an app, a page or a post she
 *  shows. Settles in `inFrames` (18); `scale` 0.62 leaves room for a caption above or below. */
export const PhoneMockup: React.FC<{children: React.ReactNode; scale?: number; inFrames?: number; backdrop?: string}> = ({
	children,
	scale = 0.62,
	inFrames = 18,
	backdrop = '#EDE6DC',
}) => {
	const frame = useCurrentFrame();
	const p = interpolate(frame, [0, inFrames], [0, 1], {...clamp, easing: land});
	return (
		<AbsoluteFill style={{backgroundColor: backdrop}}>
			<div
				style={{
					position: 'absolute',
					width: W,
					height: H,
					transform: `scale(${1 + (scale - 1) * p})`,
					borderRadius: 150 * p,
					overflow: 'hidden',
					boxShadow: `0 0 0 ${30 * p}px #141414, 0 60px 140px rgba(0, 0, 0, ${0.35 * p})`,
				}}
			>
				{children}
				<div
					style={{
						position: 'absolute',
						top: 46,
						left: W / 2 - 160,
						width: 320,
						height: 92,
						borderRadius: 46,
						backgroundColor: '#000',
						opacity: p,
					}}
				/>
			</div>
		</AbsoluteFill>
	);
};

export type Bar = {label: string; value: number; color?: string};

/** Bars grow from the baseline, 4 frames apart, while their numbers count up: for a figure she says out loud.
 *  Each takes 0.8 s and holds. Values keep their decimals (4.5 counts up as 0.0 ... 4.5). The default box
 *  (y 300-720) clears a face in a medium shot; check the sheet. */
export const ChartGrow: React.FC<{bars: Bar[]; unit?: string; max?: number; top?: number; height?: number}> = ({
	bars,
	unit = '',
	max,
	top = 300,
	height = 420,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const [x0, x1, gap] = [130, 890, 40];
	const peak = max ?? Math.max(...bars.map((b) => b.value));
	const w = (x1 - x0 - gap * (bars.length - 1)) / bars.length;
	const label = {position: 'absolute', width: w, textAlign: 'center', fontFamily: FONTS.sans, fontWeight: 700,
		color: WHITE, textShadow: SHADOW} as const;
	return (
		<AbsoluteFill>
			{bars.map((b, i) => {
				const p = interpolate(frame, [i * 4, i * 4 + 0.8 * fps], [0, 1], {...clamp, easing: land});
				const h = (b.value / peak) * height * p;
				const x = x0 + i * (w + gap);
				const dp = (String(b.value).split('.')[1] ?? '').length;
				return (
					<React.Fragment key={b.label}>
						<div
							style={{
								position: 'absolute',
								left: x,
								top: top + height - h,
								width: w,
								height: h,
								borderRadius: '20px 20px 0 0',
								backgroundColor: b.color ?? WHITE,
								boxShadow: '0 8px 30px rgba(0, 0, 0, 0.3)',
							}}
						/>
						<div style={{...label, left: x, top: top + height - h - 100, fontSize: 76, opacity: Math.min(1, p * 3)}}>
							{(b.value * p).toFixed(dp)}
							{unit}
						</div>
						<div style={{...label, left: x, top: top + height + 22, fontSize: 44}}>{b.label}</div>
					</React.Fragment>
				);
			})}
		</AbsoluteFill>
	);
};

/** Press clippings stack down the screen, one every `every` frames (10), each tilted a little. Black serif on
 *  paper; put her own claim in the last card. Cards stack in flow, so a headline that wraps pushes the rest
 *  down: four one-line cards end near y 720, so check the sheet for the face when lines run long. */
export const HeadlineWall: React.FC<{lines: string[]; every?: number; top?: number; size?: number}> = ({
	lines,
	every = 10,
	top = 250,
	size = 56,
}) => {
	const frame = useCurrentFrame();
	return (
		<AbsoluteFill>
			<div style={{position: 'absolute', top, left: 100, width: 820, display: 'flex', flexDirection: 'column', gap: 16}}>
				{lines.map((text, i) => {
					const p = interpolate(frame, [i * every, i * every + 8], [0, 1], {...clamp, easing: land});
					const x = (random(`wall-x-${i}`) - 0.5) * 60;
					const tilt = (random(`wall-r-${i}`) - 0.5) * 5;
					return (
						<div
							key={text}
							style={{
								transform: `translateX(${x}px) rotate(${tilt}deg) scale(${1.08 - 0.08 * p})`,
								opacity: p,
								padding: '22px 30px',
								backgroundColor: '#F6F1E7',
								color: '#141414',
								fontFamily: FONTS.serif,
								fontWeight: 800,
								fontSize: size,
								lineHeight: 1.05,
								boxShadow: '0 14px 34px rgba(0, 0, 0, 0.35)',
							}}
						>
							{text}
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

/** A title on a torn paper strip that drops in and settles at a slight tilt: scrapbook, recipe, DIY. */
export const PaperCut: React.FC<{text: string; top?: number; size?: number; tilt?: number; paper?: string; ink?: string}> = ({
	text,
	top = 320,
	size = 96,
	tilt = -3,
	paper = BRAND.colors.paper,
	ink = BRAND.colors.ink,
}) => {
	const frame = useCurrentFrame();
	const p = interpolate(frame, [0, 12], [0, 1], {...clamp, easing: land});
	const edge: string[] = [];
	for (let x = 0; x <= 100; x += 2) edge.push(`${x}% ${random(`${text}-t${x}`) * 9}%`);
	for (let x = 100; x >= 0; x -= 2) edge.push(`${x}% ${100 - random(`${text}-b${x}`) * 9}%`);
	return (
		<AbsoluteFill>
			<div
				style={{
					position: 'absolute',
					top,
					left: 0,
					width: W,
					textAlign: 'center',
					opacity: p,
					transform: `translateY(${-50 * (1 - p)}px) rotate(${tilt * p}deg)`,
					filter: 'drop-shadow(0 10px 18px rgba(0, 0, 0, 0.4))',
				}}
			>
				<span
					style={{
						display: 'inline-block',
						maxWidth: 840,
						padding: '44px 64px',
						backgroundColor: paper,
						color: ink,
						fontFamily: FONTS.serif,
						fontWeight: 800,
						fontSize: size,
						lineHeight: 1.05,
						clipPath: `polygon(${edge.join(', ')})`,
					}}
				>
					{text}
				</span>
			</div>
		</AbsoluteFill>
	);
};

/** Words circle the head on a tilted ring, passing behind her and in front. One turn every `turn` seconds (6);
 *  keep it to 3-5 short words. */
export const Orbit: React.FC<{
	background: React.ReactNode;
	person: React.ReactNode;
	words: string[];
	center?: Point;
	rx?: number;
	ry?: number;
	turn?: number;
	size?: number;
}> = ({background, person, words, center = [0.5, 0.3], rx = 400, ry = 80, turn = 6, size = 60}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const show = interpolate(frame, [0, 0.3 * fps], [0, 1], {...clamp, easing: land});
	const spin = (frame / (turn * fps)) * 2 * Math.PI;
	const items = words.map((word, i) => {
		const a = spin + (i / words.length) * 2 * Math.PI;
		return {word, i, x: center[0] * W + rx * Math.cos(a), y: center[1] * H + ry * Math.sin(a), depth: Math.sin(a)};
	});
	const draw = (front: boolean) =>
		items
			.filter((it) => it.depth >= 0 === front)
			.map((it) => (
				<div
					key={it.i}
					style={{
						position: 'absolute',
						left: it.x,
						top: it.y,
						transform: `translate(-50%, -50%) scale(${0.8 + 0.2 * it.depth})`,
						opacity: show * (0.6 + 0.4 * it.depth),
						fontFamily: FONTS.sans,
						fontWeight: 700,
						fontSize: size,
						color: WHITE,
						textShadow: SHADOW,
						whiteSpace: 'nowrap',
					}}
				>
					{it.word}
				</div>
			));
	return (
		<AbsoluteFill>
			{background}
			{draw(false)}
			{person}
			{draw(true)}
		</AbsoluteFill>
	);
};

/** A magazine cover: masthead behind the head, cover lines down the left, a dateline on top. The head may
 *  cover part of a letter or two, never a word: set `top` from the sheet. */
export const MagazineCover: React.FC<{
	background: React.ReactNode;
	person: React.ReactNode;
	title: string;
	lines?: string[];
	issue?: string;
	top?: number;
	size?: number;
	linesTop?: number;
	ink?: string;
}> = ({background, person, title, lines = [], issue, top = 260, size = 300, linesTop = 1150, ink = WHITE}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const fade = (from: number) => interpolate(frame, [from, from + 0.4 * fps], [0, 1], {...clamp, easing: land});
	const text = {position: 'absolute', color: ink, textShadow: SHADOW} as const;
	return (
		<AbsoluteFill>
			{background}
			<div
				style={{
					...text,
					top,
					left: 0,
					width: W,
					textAlign: 'center',
					fontFamily: FONTS.didone,
					fontWeight: 900,
					fontSize: size,
					lineHeight: 0.9,
					letterSpacing: -6,
					opacity: fade(0),
					transform: `scale(${1.04 - 0.04 * fade(0)})`,
				}}
			>
				{title}
			</div>
			{person}
			{issue ? (
				<div style={{...text, top: top - 50, left: 0, width: W, textAlign: 'center', fontFamily: FONTS.sans,
					fontWeight: 700, fontSize: 30, letterSpacing: 6, opacity: fade(6)}}>
					{issue.toUpperCase()}
				</div>
			) : null}
			<div style={{...text, left: 70, top: linesTop, width: 460, display: 'flex', flexDirection: 'column', gap: 30}}>
				{lines.map((line, i) => (
					<div
						key={line}
						style={{fontFamily: FONTS.sans, fontWeight: 700, fontSize: i === 0 ? 54 : 40, lineHeight: 1.1,
							opacity: fade(10 + i * 6)}}
					>
						{line}
					</div>
				))}
			</div>
		</AbsoluteFill>
	);
};

export type UiItem = {
	text: string;
	/** Centre, as fractions of the frame. */
	x: number;
	y: number;
	kind?: 'note' | 'chat' | 'like' | 'search';
	/** Frame it eases in. */
	from?: number;
	/** Under the person cutout instead of over it. */
	behind?: boolean;
};

/** App UI floats around her: a notification, a chat bubble, a like count, a search bar, each easing in at its
 *  `from` frame and drifting a few px. For a story about an app, a message or going viral. */
export const UiWorld: React.FC<{items: UiItem[]; background?: React.ReactNode; person?: React.ReactNode}> = ({
	items,
	background,
	person,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const look: Record<NonNullable<UiItem['kind']>, React.CSSProperties> = {
		note: {backgroundColor: 'rgba(250, 250, 250, 0.92)', color: '#111', borderRadius: 38, padding: '28px 34px'},
		chat: {backgroundColor: '#0A84FF', color: '#FFF', borderRadius: 44, padding: '24px 36px'},
		like: {backgroundColor: '#FFFFFF', color: '#FF2D55', borderRadius: 60, padding: '20px 34px'},
		search: {backgroundColor: '#FFFFFF', color: '#333', borderRadius: 60, padding: '24px 40px', minWidth: 520},
	};
	const draw = (under: boolean) =>
		items
			.map((it, i) => ({it, i}))
			.filter(({it}) => Boolean(it.behind) === under)
			.map(({it, i}) => {
				const p = interpolate(frame, [it.from ?? i * 8, (it.from ?? i * 8) + 10], [0, 1], {...clamp, easing: land});
				const drift = Math.sin((frame / fps) * 1.3 + i) * 6;
				return (
					<div
						key={i}
						style={{
							position: 'absolute',
							left: it.x * W,
							top: it.y * H,
							transform: `translate(-50%, calc(-50% + ${drift}px)) scale(${0.92 + 0.08 * p})`,
							opacity: p,
							fontFamily: FONTS.sans,
							fontWeight: 600,
							fontSize: 40,
							whiteSpace: 'nowrap',
							boxShadow: '0 18px 40px rgba(0, 0, 0, 0.28)',
							...look[it.kind ?? 'note'],
						}}
					>
						{it.kind === 'like' ? `♥ ${it.text}` : it.kind === 'search' ? `⌕  ${it.text}` : it.text}
					</div>
				);
			});
	return (
		<AbsoluteFill>
			{background}
			{draw(true)}
			{person}
			{draw(false)}
		</AbsoluteFill>
	);
};

/** A title typed on one character at a time. `frames[i]` is the frame character i appears on: take it
 *  from typeon.py, which writes the key sounds from the same schedule, so each click lands on its letter
 *  (without it, characters arrive evenly at `cps` and no sound matches). The whole text is laid out from
 *  frame 0 with unshown characters invisible, so lines never reflow as it types. The cursor stays solid
 *  while typing, blinks once typing ends (`cursor={false}` hides it), and the title fades out over its
 *  last 0.17 s. For the typewriter look pass a monospace `font`. */
export const TypeOn: React.FC<{
	text: string;
	frames?: number[];
	cps?: number;
	size?: number;
	top?: number;
	x0?: number;
	x1?: number;
	align?: 'left' | 'center';
	font?: string;
	color?: string;
	cursor?: boolean;
}> = ({
	text,
	frames,
	cps = 14,
	size = 80,
	top = 300,
	x0 = SAFE.x0,
	x1 = SAFE.x1,
	align = 'center',
	font = FONTS.sans,
	color = WHITE,
	cursor = true,
}) => {
	const frame = useCurrentFrame();
	const {fps, durationInFrames} = useVideoConfig();
	const when = (i: number) => frames?.[i] ?? Math.round((i * fps) / cps);
	const chars = Array.from(text);
	const shown = chars.filter((_, i) => when(i) <= frame).length;
	const typing = shown < chars.length;
	const done = when(chars.length - 1);
	const blinkOn = typing || Math.floor(((frame - done) / fps) * 2) % 2 === 0;
	const outF = Math.round(0.17 * fps);
	const opacity = interpolate(frame, [durationInFrames - outF, durationInFrames], [1, 0], clamp);
	const bar = (
		<span style={{position: 'relative'}}>
			<span
				style={{
					position: 'absolute',
					left: '0.04em',
					top: '0.12em',
					width: '0.07em',
					height: '1em',
					background: color,
					boxShadow: '0 2px 10px rgba(0,0,0,0.35)',
					opacity: cursor && blinkOn ? 1 : 0,
				}}
			/>
		</span>
	);
	return (
		<AbsoluteFill style={{pointerEvents: 'none', opacity}}>
			<div
				style={{
					position: 'absolute',
					top,
					left: x0,
					width: x1 - x0,
					textAlign: align,
					whiteSpace: 'pre-wrap',
					fontFamily: font,
					fontWeight: 700,
					fontSize: size,
					lineHeight: 1.2,
					color,
					textShadow: SHADOW,
				}}
			>
				{shown === 0 ? bar : null}
				{chars.map((ch, i) => (
					<React.Fragment key={i}>
						<span style={{opacity: i < shown ? 1 : 0}}>{ch}</span>
						{i === shown - 1 ? bar : null}
					</React.Fragment>
				))}
			</div>
		</AbsoluteFill>
	);
};
