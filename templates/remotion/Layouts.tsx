// Layouts: how footage, a cutout and labels share the frame. Calm by default (fades, slow pushes, nothing
// bounces); the spring options are there when a brand asks for energy. Frames are local: place each inside a
// <Sequence>. `person` props take the cutout from matte.swift --person
// (<OffthreadVideo src={staticFile('person.webm')} transparent muted />) laid over the same footage.
// Fonts and colours come from brand.ts; text stays inside SAFE unless a prop moves it.
import React, {useMemo} from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND, SAFE} from './brand';
import type {Key, Point} from './Looks';

const W = 1080;
const H = 1920;
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const land = Easing.bezier(0.16, 1, 0.3, 1); // soft landing for things arriving
const glide = Easing.bezier(0.65, 0, 0.35, 1); // in-out for camera moves
const SHADOW = BRAND.colors.shadow;
const LIFT = '0 10px 30px rgba(0, 0, 0, 0.25)'; // under chips and cards

export type Safe = typeof SAFE;

const at = (p: Point) => `${p[0] * 100}% ${p[1] * 100}%`;
const within = (v: number, lo: number, hi: number) => (lo > hi ? (lo + hi) / 2 : Math.min(hi, Math.max(lo, v)));
/** Rough width of a line of bold sans: about 0.56 em a character. */
const wide = (text: string, size: number) => Array.from(text).length * size * 0.56;
/** The size at which `text` fits in `width` on one line, never above `size`. */
const fit = (text: string, size: number, width: number) => Math.min(size, width / (Array.from(text).length * 0.56));

/** 0 → 1 over `inS` seconds from frame `from`, back to 0 over the last `outS` seconds (exits run shorter). */
const useFade = (inS = 0.3, outS = 0.17, from = 0) => {
	const frame = useCurrentFrame();
	const {fps, durationInFrames} = useVideoConfig();
	const fadeIn = inS > 0 ? interpolate(frame, [from, from + inS * fps], [0, 1], {...clamp, easing: land}) : 1;
	const fadeOut =
		outS > 0 ? interpolate(frame, [durationInFrames - outS * fps, durationInFrames], [1, 0], {...clamp, easing: land}) : 1;
	return Math.min(fadeIn, fadeOut);
};

/** A cutout over a new background (a screenshot, a page, other footage). `position` is where the cutout's
 *  bottom centre lands (fractions, [0.5, 1] keeps it on the bottom edge); `push` (0.04) eases the background in. */
export const GreenScreen: React.FC<{
	person: React.ReactNode;
	background: React.ReactNode;
	position?: Point;
	scale?: number;
	shadow?: boolean;
	push?: number;
	origin?: Point;
}> = ({person, background, position = [0.5, 1], scale = 1, shadow = true, push = 0.04, origin = [0.5, 0.5]}) => {
	const frame = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const p = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [0, 1], {...clamp, easing: glide});
	return (
		<AbsoluteFill style={{overflow: 'hidden', backgroundColor: BRAND.colors.ink}}>
			<AbsoluteFill style={{transform: `scale(${1 + push * p})`, transformOrigin: at(origin)}}>{background}</AbsoluteFill>
			<AbsoluteFill
				style={{
					transform: `translate(${position[0] * W - W / 2}px, ${position[1] * H - H}px) scale(${scale})`,
					transformOrigin: '50% 100%',
					filter: shadow ? 'drop-shadow(0 24px 40px rgba(0, 0, 0, 0.45))' : undefined,
				}}
			>
				{person}
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

const Label: React.FC<{text: string; x0: number; x1: number; top: number; align?: 'left' | 'center' | 'right'; size: number; opacity: number}> = ({
	text,
	x0,
	x1,
	top,
	align = 'center',
	size,
	opacity,
}) => (
	<div
		style={{
			position: 'absolute',
			left: x0,
			width: x1 - x0,
			top,
			textAlign: align,
			whiteSpace: 'nowrap',
			fontFamily: BRAND.fonts.sans,
			fontWeight: 700,
			fontSize: fit(text, size, x1 - x0),
			lineHeight: 1.2,
			color: BRAND.colors.text,
			textShadow: SHADOW,
			opacity,
		}}
	>
		{text}
	</div>
);

/** Two shots share the frame: 'side' by side, 'stack'ed, or 'wipe' (before/after: `b` is revealed left of a
 *  divider that moves across on `keys` [[frame, x 0-1]]). Panes crop to their centre; `focus` slides each crop. */
export const SplitScreen: React.FC<{
	a: React.ReactNode;
	b: React.ReactNode;
	mode?: 'side' | 'stack' | 'wipe';
	labels?: [string, string];
	gap?: number;
	focus?: [number, number];
	keys?: Key[];
	size?: number;
}> = ({a, b, mode = 'side', labels, gap = 8, focus = [0.5, 0.5], keys, size = 52}) => {
	const frame = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	const show = useFade();
	if (mode === 'wipe') {
		const k = keys ?? [
			[Math.round(durationInFrames * 0.15), 0],
			[Math.round(durationInFrames * 0.85), 1],
		];
		const p = k.length < 2 ? k[0][1] : interpolate(frame, k.map((x) => x[0]), k.map((x) => x[1]), {...clamp, easing: glide});
		const x = p * W;
		const edge = interpolate(Math.min(p, 1 - p), [0, 0.03], [0, 1], clamp);
		return (
			<AbsoluteFill style={{overflow: 'hidden'}}>
				<AbsoluteFill>{a}</AbsoluteFill>
				<AbsoluteFill style={{clipPath: `inset(0 ${W - x}px 0 0)`}}>{b}</AbsoluteFill>
				<div
					style={{
						position: 'absolute',
						left: x - 3,
						top: 0,
						width: 6,
						height: H,
						backgroundColor: BRAND.colors.text,
						boxShadow: '0 0 18px rgba(0, 0, 0, 0.35)',
						opacity: edge,
					}}
				/>
				<svg
					width={72}
					height={72}
					viewBox="0 0 72 72"
					style={{position: 'absolute', left: x - 36, top: H * 0.5 - 36, opacity: edge, filter: 'drop-shadow(0 6px 14px rgba(0, 0, 0, 0.35))'}}
				>
					<circle cx={36} cy={36} r={34} fill={BRAND.colors.text} />
					<path d="M30 25 L20 36 L30 47 M42 25 L52 36 L42 47" stroke={BRAND.colors.ink} strokeWidth={5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
				</svg>
				{labels ? (
					<>
						<Label text={labels[0]} x0={W / 2} x1={SAFE.x1} top={SAFE.y0 + 10} align="right" size={size} opacity={show * interpolate(1 - p, [0, 0.25], [0, 1], clamp)} />
						<Label text={labels[1]} x0={SAFE.x0} x1={W / 2} top={SAFE.y0 + 10} align="left" size={size} opacity={show * interpolate(p, [0, 0.25], [0, 1], clamp)} />
					</>
				) : null}
			</AbsoluteFill>
		);
	}
	const side = mode === 'side';
	const pw = side ? (W - gap) / 2 : W;
	const ph = side ? H : (H - gap) / 2;
	const pane = (node: React.ReactNode, i: 0 | 1) => (
		<div
			style={{
				position: 'absolute',
				left: side ? i * (pw + gap) : 0,
				top: side ? 0 : i * (ph + gap),
				width: pw,
				height: ph,
				overflow: 'hidden',
			}}
		>
			<div style={{position: 'absolute', left: -(W - pw) * focus[i], top: -(H - ph) * focus[i], width: W, height: H}}>{node}</div>
		</div>
	);
	const tag = (text: string, i: 0 | 1) =>
		side ? (
			<Label key={i} text={text} x0={i ? W / 2 + gap / 2 + 20 : SAFE.x0} x1={i ? SAFE.x1 : W / 2 - gap / 2 - 20} top={SAFE.y0 + 10} size={size} opacity={show} />
		) : (
			<Label key={i} text={text} x0={SAFE.x0} x1={SAFE.x1} top={i ? Math.min(SAFE.y1 - size * 1.2, ph + gap + 40) : SAFE.y0 + 10} size={size} opacity={show} />
		);
	return (
		<AbsoluteFill style={{backgroundColor: BRAND.colors.text}}>
			{pane(a, 0)}
			{pane(b, 1)}
			{labels ? [tag(labels[0], 0), tag(labels[1], 1)] : null}
		</AbsoluteFill>
	);
};

/** The same shot with its background blurred behind a sharp cutout of her: pulls the eye in without a cut.
 *  The blur eases in over `inFrames` (12; 0 starts blurred) and `dim` (0.15) darkens the backdrop a touch. */
export const BlurBackground: React.FC<{footage: React.ReactNode; person: React.ReactNode; blur?: number; dim?: number; inFrames?: number}> = ({
	footage,
	person,
	blur = 24,
	dim = 0.15,
	inFrames = 12,
}) => {
	const frame = useCurrentFrame();
	const p = inFrames > 0 ? interpolate(frame, [0, inFrames], [0, 1], {...clamp, easing: land}) : 1;
	return (
		<AbsoluteFill style={{overflow: 'hidden', backgroundColor: BRAND.colors.ink}}>
			{/* Scaled just enough that the blur's soft edge stays off the frame. */}
			<AbsoluteFill style={{filter: `blur(${blur * p}px)`, transform: `scale(${1 + (4 * blur * p) / W})`}}>{footage}</AbsoluteFill>
			<AbsoluteFill style={{backgroundColor: `rgba(0, 0, 0, ${dim * p})`}} />
			<AbsoluteFill>{person}</AbsoluteFill>
		</AbsoluteFill>
	);
};

/** One tracker sample, as track.swift writes it: [frame, [x0, y0, x1, y1, confidence]], fractions of the
 *  frame, origin top-left. */
export type TrackSample = [number, [number, number, number, number, number]];

/** Field `i` of the track at frame `f`, linear between samples and held past either end. */
const sampleAt = (track: TrackSample[], f: number, i: number) => {
	if (f <= track[0][0]) return track[0][1][i];
	const last = track[track.length - 1];
	if (f >= last[0]) return last[1][i];
	let lo = 0;
	let hi = track.length - 1;
	while (hi - lo > 1) {
		const mid = (lo + hi) >> 1;
		if (track[mid][0] <= f) lo = mid;
		else hi = mid;
	}
	const [fa, va] = track[lo];
	const [fb, vb] = track[hi];
	return va[i] + ((vb[i] - va[i]) * (f - fa)) / (fb - fa);
};

/** A triangle-weighted average over `s` frames each side: takes the tracker's jitter out. */
const smoothAt = (track: TrackSample[], f: number, i: number, s: number) => {
	let sum = 0;
	let weights = 0;
	for (let d = -s; d <= s; d++) {
		const w = s + 1 - Math.abs(d);
		sum += w * sampleAt(track, f + d, i);
		weights += w;
	}
	return sum / weights;
};

/** Where a ray from (x, y) toward (tx, ty) leaves a box of half-size hw x hh grown by `pad`; null if the target
 *  is inside it. */
const exit = (x: number, y: number, hw: number, hh: number, tx: number, ty: number, pad: number): Point | null => {
	const [dx, dy] = [tx - x, ty - y];
	const t = Math.min(dx ? (hw + pad) / Math.abs(dx) : Infinity, dy ? (hh + pad) / Math.abs(dy) : Infinity);
	return t >= 1 ? null : [x + dx * t, y + dy * t];
};

/** A label tied to a moving thing by a leader line (or `arrow`), following a track.swift track. Low-confidence
 *  samples are bridged, jitter is smoothed over `smooth` frames (6) each side, the label sits `offset` px off
 *  the box toward `side` (a name or degrees, 0 = right, 90 = down) and never leaves `safe`; it fades where the
 *  track is unsure. `trackFrom` is the track frame at this sequence's frame 0. */
export const Callout: React.FC<{
	track: TrackSample[];
	text: string;
	side?: 'above' | 'below' | 'left' | 'right' | number;
	offset?: number;
	arrow?: boolean;
	anchor?: 'edge' | 'center';
	trackFrom?: number;
	smooth?: number;
	minConfidence?: number;
	size?: number;
	chip?: boolean;
	safe?: Safe;
}> = ({
	track,
	text,
	side = 'above',
	offset = 120,
	arrow = false,
	anchor = 'edge',
	trackFrom = 0,
	smooth = 6,
	minConfidence = 0.3,
	size = 48,
	chip = false,
	safe = SAFE,
}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const show = useFade();
	const all = useMemo(() => [...track].sort((p, q) => p[0] - q[0]), [track]);
	const sure = useMemo(() => all.filter((s) => s[1][4] >= minConfidence), [all, minConfidence]);
	if (!sure.length) return null;
	const f = frame + trackFrom;
	const [x0, y0, x1, y1] = [0, 1, 2, 3].map((i) => smoothAt(sure, f, i, smooth) * (i % 2 ? H : W));
	const trust = interpolate(smoothAt(all, f, 4, smooth), [minConfidence, minConfidence + 0.2], [0, 1], clamp);
	const [cx, cy, hw, hh] = [(x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2];
	// The label: `offset` px past the box's edge along `side`, then pulled back inside the safe zone.
	const deg = typeof side === 'number' ? side : {right: 0, below: 90, left: 180, above: -90}[side];
	const [ux, uy] = [Math.cos((deg * Math.PI) / 180), Math.sin((deg * Math.PI) / 180)];
	const reach = (w: number, h: number) => Math.min(Math.abs(ux) > 1e-6 ? w / Math.abs(ux) : Infinity, Math.abs(uy) > 1e-6 ? h / Math.abs(uy) : Infinity);
	const pad: [number, number] = chip ? [size * 0.45, size * 0.22] : [0, 0];
	const lw = Math.min(wide(text, size) + 2 * pad[0], safe.x1 - safe.x0);
	const lh = size * 1.2 + 2 * pad[1];
	const dist = reach(hw, hh) + offset + reach(lw / 2, lh / 2);
	const lx = within(cx + ux * dist, safe.x0 + lw / 2, safe.x1 - lw / 2);
	const ly = within(cy + uy * dist, safe.y0 + lh / 2, safe.y1 - lh / 2);
	// The line: from the label's edge to the box's edge (or centre), drawn on as the label fades in.
	const end = anchor === 'center' ? ([cx, cy] as Point) : exit(cx, cy, hw, hh, lx, ly, 10);
	const start = end ? exit(lx, ly, lw / 2, lh / 2, end[0], end[1], 14) : null;
	const draw = interpolate(frame, [2, 2 + 0.4 * fps], [0, 1], {...clamp, easing: land});
	const line = start && end && Math.hypot(end[0] - start[0], end[1] - start[1]) > 24 ? {start, end} : null;
	const tip = line ? ([line.start[0] + (line.end[0] - line.start[0]) * draw, line.start[1] + (line.end[1] - line.start[1]) * draw] as Point) : null;
	const angle = line ? Math.atan2(line.end[1] - line.start[1], line.end[0] - line.start[0]) : 0;
	const ink = chip ? BRAND.colors.paper : BRAND.colors.text;
	return (
		<AbsoluteFill style={{pointerEvents: 'none', opacity: show * trust}}>
			{line && tip ? (
				<svg width={W} height={H} style={{position: 'absolute', inset: 0, filter: 'drop-shadow(0 2px 6px rgba(0, 0, 0, 0.45))'}}>
					<line x1={line.start[0]} y1={line.start[1]} x2={tip[0]} y2={tip[1]} stroke={ink} strokeWidth={5} strokeLinecap="round" />
					{arrow ? (
						<path
							d="M0 0 L-26 -13 L-26 13 Z"
							fill={ink}
							opacity={draw}
							transform={`translate(${tip[0]} ${tip[1]}) rotate(${(angle * 180) / Math.PI})`}
						/>
					) : (
						<circle cx={tip[0]} cy={tip[1]} r={9 * draw} fill={ink} />
					)}
				</svg>
			) : null}
			<div
				style={{
					position: 'absolute',
					left: lx,
					top: ly,
					transform: 'translate(-50%, -50%)',
					maxWidth: safe.x1 - safe.x0,
					whiteSpace: 'nowrap',
					fontFamily: BRAND.fonts.sans,
					fontWeight: 700,
					fontSize: size,
					lineHeight: 1.2,
					...(chip
						? {padding: `${pad[1]}px ${pad[0]}px`, borderRadius: size * 0.4, backgroundColor: BRAND.colors.paper, color: BRAND.colors.ink, boxShadow: LIFT}
						: {color: BRAND.colors.text, textShadow: SHADOW}),
				}}
			>
				{text}
			</div>
		</AbsoluteFill>
	);
};

/** A numbered badge for a list, "3" or "3/5" with `total`: a chip in a corner of the safe zone (or centred on
 *  `at`). Give `count` as [[frame, n], ...] and the number rolls up at each change. */
export const ListCounter: React.FC<{
	count: number | Array<[number, number]>;
	total?: number;
	corner?: 'tl' | 'tr' | 'bl' | 'br';
	at?: Point;
	prefix?: string;
	size?: number;
	background?: string;
	color?: string;
}> = ({count, total, corner = 'tl', at: centre, prefix = '', size = 56, background = BRAND.colors.accent, color = BRAND.colors.text}) => {
	const frame = useCurrentFrame();
	const steps: Array<[number, number]> = typeof count === 'number' ? [[0, count]] : count;
	const out = useFade(0, 0.17);
	if (!steps.length || frame < steps[0][0]) return null;
	let k = 0;
	steps.forEach((s, i) => {
		if (s[0] <= frame) k = i;
	});
	const show = interpolate(frame, [steps[0][0], steps[0][0] + 9], [0, 1], {...clamp, easing: land});
	const t = k ? interpolate(frame, [steps[k][0], steps[k][0] + 10], [0, 1], {...clamp, easing: land}) : 1;
	const place: React.CSSProperties = centre
		? {left: centre[0] * W, top: centre[1] * H}
		: {
				...(corner[1] === 'l' ? {left: SAFE.x0} : {right: W - SAFE.x1}),
				...(corner[0] === 't' ? {top: SAFE.y0} : {bottom: H - SAFE.y1}),
			};
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					...place,
					transform: `${centre ? 'translate(-50%, -50%) ' : ''}scale(${0.94 + 0.06 * show})`,
					opacity: show * out,
					display: 'flex',
					alignItems: 'baseline',
					gap: '0.12em',
					padding: '0.14em 0.55em',
					borderRadius: size,
					backgroundColor: background,
					color,
					fontFamily: BRAND.fonts.sans,
					fontWeight: 700,
					fontSize: size,
					lineHeight: 1.15,
					fontVariantNumeric: 'tabular-nums',
					boxShadow: LIFT,
				}}
			>
				{prefix ? <span>{prefix}</span> : null}
				<span style={{display: 'inline-grid', overflow: 'hidden', height: '1.15em'}}>
					{k && t < 1 ? (
						<span style={{gridArea: '1 / 1', transform: `translateY(${-0.9 * t}em)`, opacity: 1 - t}}>{steps[k - 1][1]}</span>
					) : null}
					<span style={{gridArea: '1 / 1', transform: `translateY(${0.9 * (1 - t)}em)`, opacity: t}}>{steps[k][1]}</span>
				</span>
				{total === undefined ? null : <span style={{opacity: 0.7}}>/{total}</span>}
			</div>
		</AbsoluteFill>
	);
};

/** A calm chapter title over the footage: a 'lower' third on a soft shade, or 'full' frame with the footage
 *  blurred and dimmed behind it. A thin rule draws under `kicker` ("Step 2"); the title rises 16 px as it
 *  fades in, holds still and fades out. */
export const ChapterCard: React.FC<{
	title: string;
	kicker?: string;
	mode?: 'lower' | 'full';
	size?: number;
	font?: string;
	blur?: number;
}> = ({title, kicker, mode = 'lower', size, font = BRAND.fonts.serif, blur = 16}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const card = useFade(0.5, 0.25);
	const words = useFade(0.5, 0.25, 0.15 * fps);
	const rule = interpolate(frame, [0.1 * fps, 0.7 * fps], [0, 1], {...clamp, easing: land});
	const full = mode === 'full';
	const px = size ?? (full ? 104 : 84);
	const width = SAFE.x1 - SAFE.x0;
	const block = (
		<div style={{display: 'flex', flexDirection: 'column', alignItems: full ? 'center' : 'flex-start', gap: px * 0.24, width, textAlign: full ? 'center' : 'left'}}>
			{kicker ? (
				<div
					style={{
						fontFamily: BRAND.fonts.sans,
						fontWeight: 700,
						fontSize: Math.round(px * 0.34),
						letterSpacing: '0.22em',
						textTransform: 'uppercase',
						color: BRAND.colors.text,
						textShadow: SHADOW,
						opacity: card,
					}}
				>
					{kicker}
				</div>
			) : null}
			<div
				style={{
					width: px * 1.2,
					height: 4,
					borderRadius: 2,
					backgroundColor: BRAND.colors.text,
					boxShadow: '0 1px 6px rgba(0, 0, 0, 0.35)',
					transform: `scaleX(${rule})`,
					transformOrigin: full ? '50% 50%' : '0 50%',
					opacity: card,
				}}
			/>
			<div
				style={{
					fontFamily: font,
					fontWeight: 700,
					fontSize: px,
					lineHeight: 1.05,
					color: BRAND.colors.text,
					textShadow: SHADOW,
					opacity: words,
					transform: `translateY(${16 * (1 - words)}px)`,
				}}
			>
				{title}
			</div>
		</div>
	);
	return full ? (
		<AbsoluteFill style={{pointerEvents: 'none', backdropFilter: `blur(${blur * card}px)`, backgroundColor: `rgba(0, 0, 0, ${0.35 * card})`}}>
			<div style={{position: 'absolute', left: SAFE.x0, top: SAFE.y0, width, height: SAFE.y1 - SAFE.y0, display: 'flex', alignItems: 'center'}}>
				{block}
			</div>
		</AbsoluteFill>
	) : (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<AbsoluteFill style={{background: 'linear-gradient(to bottom, rgba(0, 0, 0, 0) 45%, rgba(0, 0, 0, 0.5) 85%)', opacity: card}} />
			<div style={{position: 'absolute', left: SAFE.x0, bottom: H - SAFE.y1}}>{block}</div>
		</AbsoluteFill>
	);
};

/** An emoji or a short word stuck on the frame: 'fade' (default) eases it in; 'pop' springs it in with a
 *  little overshoot, for energy. Words sit on a chip; `at` is its centre (fractions), kept inside the safe zone. */
export const Sticker: React.FC<{
	text: string;
	at?: Point;
	mode?: 'fade' | 'pop';
	size?: number;
	tilt?: number;
	chip?: boolean;
	background?: string;
	color?: string;
}> = ({text, at: centre = [0.72, 0.3], mode = 'fade', size, tilt = -6, chip, background = BRAND.colors.accent, color = BRAND.colors.text}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const fade = useFade(0.3, 0.17);
	const quick = useFade(0.07, 0.17);
	const emoji = /^[\p{Extended_Pictographic}‍️\s]+$/u.test(text);
	const card = chip ?? !emoji;
	const px = size ?? (emoji ? 140 : 64);
	const pop = spring({frame, fps, config: {damping: 9, stiffness: 170, mass: 0.7}});
	const energetic = mode === 'pop';
	const n = Array.from(text.replace(/[‍️]/g, '')).length;
	const w = emoji ? n * px * 1.2 : wide(text, px) + (card ? px * 0.9 : 0);
	const h = px * 1.25 + (card ? px * 0.4 : 0);
	const x = within(centre[0] * W, SAFE.x0 + w / 2, SAFE.x1 - w / 2);
	const y = within(centre[1] * H, SAFE.y0 + h / 2, SAFE.y1 - h / 2);
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					left: x,
					top: y,
					transform: `translate(-50%, -50%) rotate(${energetic ? tilt - 14 * (1 - pop) : tilt}deg) scale(${energetic ? pop : 0.96 + 0.04 * fade})`,
					opacity: energetic ? quick : fade,
					whiteSpace: 'nowrap',
					fontFamily: emoji ? '"Apple Color Emoji", "Noto Color Emoji", "Segoe UI Emoji", sans-serif' : BRAND.fonts.sans,
					fontWeight: 700,
					fontSize: px,
					lineHeight: 1.25,
					...(card
						? {padding: '0.2em 0.45em', borderRadius: '0.35em', backgroundColor: background, color, boxShadow: LIFT}
						: {color, filter: 'drop-shadow(0 8px 16px rgba(0, 0, 0, 0.3))'}),
				}}
			>
				{text}
			</div>
		</AbsoluteFill>
	);
};
