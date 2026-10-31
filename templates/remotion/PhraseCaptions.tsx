// Phrase captions from scripts/captions.py (-f json --fps 30): one phrase at a time, up to two
// lines, each fading in whole with no word picked out. A phrase may carry `place` (moved off a
// face by the placer); otherwise it sits with its bottom edge at `bottom`, clear of the
// platforms' username and caption, and left of the right-hand buttons. Font, size, weight, case
// and colours come from brand.ts. `highlight` (energy, off by default) picks out the word being
// said from the phrase's `words`; a phrase without them shows plain.
import React from 'react';
import {AbsoluteFill, interpolate, interpolateColors, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND, SAFE} from './brand';
import {TEXT} from './CalmText';

/** captions.py writes startFrame/endFrame with --fps, and start/end in seconds always. */
export type Word = {text: string; startFrame?: number; endFrame?: number; start?: number; end?: number};

export type Phrase = {
	startFrame: number;
	endFrame: number;
	lines: string[];
	words?: Word[];
	place?: {x0: number; x1: number; top?: number; bottom?: number};
};

/** 'color' turns the word being said `active`; 'box' sets a rounded `box` behind it; 'pop' springs it up a
 *  little; 'karaoke' fills each word with `active`, left to right, as it is said. */
export type Highlight = 'none' | 'color' | 'box' | 'pop' | 'karaoke';

export type PhraseCaptionsProps = {
	phrases: Phrase[];
	size?: number;
	bottom?: number;
	x0?: number;
	x1?: number;
	lowercase?: boolean;
	highlight?: Highlight;
	font?: string;
	weight?: number;
	color?: string;
	/** The said word's colour ('color', 'karaoke'). */
	active?: string;
	/** The fill behind the said word ('box'). */
	box?: string;
};

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

type Timed = {text: string; s: number; e: number; k: number};

/** The phrase's words in frames, split into its lines; null when they don't match the lines. */
const wordRows = (cap: Phrase, fps: number): Timed[][] | null => {
	if (!cap.words?.length) return null;
	const words = cap.words.map((w, k) => {
		const s = w.startFrame ?? Math.round((w.start ?? 0) * fps);
		return {text: w.text, s, e: Math.max(s + 1, w.endFrame ?? Math.round((w.end ?? 0) * fps)), k};
	});
	const rows: Timed[][] = [];
	let i = 0;
	for (const line of cap.lines) {
		const n = line.split(/\s+/).filter(Boolean).length;
		rows.push(words.slice(i, i + n));
		i += n;
	}
	return i === words.length ? rows : null;
};

export const PhraseCaptions: React.FC<PhraseCaptionsProps> = ({
	phrases,
	size = BRAND.caption.size,
	bottom = SAFE.y1,
	x0 = SAFE.x0,
	x1 = SAFE.x1,
	lowercase = BRAND.caption.lowercase,
	highlight = 'none',
	font = BRAND.fonts.caption,
	weight = BRAND.caption.weight,
	color = TEXT.color,
	active = BRAND.colors.highlight,
	box = BRAND.colors.accent,
}) => {
	const frame = useCurrentFrame();
	const {fps, height} = useVideoConfig();
	const cap = phrases.find((p) => frame >= p.startFrame && frame < p.endFrame);
	if (!cap) return null;
	const at = cap.place ?? {x0, x1, bottom};
	const fade = Math.min(4, Math.floor((cap.endFrame - cap.startFrame) / 3));
	const rows = highlight === 'none' ? null : wordRows(cap, fps);
	const starts = rows?.flat().map((w) => w.s) ?? [];
	// 0 → 1 as a word starts, back to 0 as the next one starts: the said word holds through pauses.
	const ramp = (from: number) => interpolate(frame, [from, from + 3], [0, 1], clamp);
	const bounce = (from: number) => spring({frame, fps, delay: from, config: {damping: 12, stiffness: 220, mass: 0.6}});
	const lit = (k: number, rise: (from: number) => number) =>
		rise(starts[k]) - (k + 1 < starts.length ? rise(starts[k + 1]) : 0);
	const word = (w: Timed) => {
		const on = lit(w.k, highlight === 'pop' ? bounce : ramp);
		const fill = interpolate(frame, [w.s, w.e], [0, 1], clamp);
		return (
			<span
				style={{
					position: 'relative',
					zIndex: 0,
					display: 'inline-block',
					color: highlight === 'color' ? interpolateColors(on, [0, 1], [color, active]) : color,
					// A pop word gets a little room each side so the grown word never meets its neighbours.
					...(highlight === 'pop' ? {margin: '0 0.06em', transform: `scale(${1 + 0.1 * on})`, transformOrigin: '50% 60%'} : {}),
				}}
			>
				{highlight === 'box' ? (
					<span
						style={{
							position: 'absolute',
							inset: '0.04em -0.16em',
							zIndex: -1,
							borderRadius: '0.2em',
							backgroundColor: box,
							boxShadow: '0 4px 14px rgba(0, 0, 0, 0.25)',
							opacity: on,
							transform: `scale(${0.9 + 0.1 * on})`,
						}}
					/>
				) : null}
				{w.text}
				{highlight === 'karaoke' ? (
					<span
						aria-hidden
						style={{
							position: 'absolute',
							left: 0,
							top: 0,
							whiteSpace: 'nowrap',
							color: active,
							textShadow: 'none',
							clipPath: `inset(0 ${100 - 100 * fill}% 0 0)`,
						}}
					>
						{w.text}
					</span>
				) : null}
			</span>
		);
	};
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					left: at.x0,
					width: at.x1 - at.x0,
					...(at.bottom === undefined ? {top: at.top} : {bottom: height - at.bottom}),
					textAlign: 'center',
					fontFamily: font,
					fontWeight: weight,
					fontSize: size,
					lineHeight: TEXT.lineHeight,
					color,
					textShadow: TEXT.shadow,
					textTransform: lowercase ? 'lowercase' : 'none',
					opacity: fade ? interpolate(frame - cap.startFrame, [0, fade], [0, 1], {extrapolateRight: 'clamp'}) : 1,
				}}
			>
				{rows
					? rows.map((row, i) => (
							<div key={i}>
								{row.map((w, j) => (
									<React.Fragment key={w.k}>
										{j ? ' ' : null}
										{word(w)}
									</React.Fragment>
								))}
							</div>
						))
					: cap.lines.map((l, i) => <div key={i}>{l}</div>)}
			</div>
		</AbsoluteFill>
	);
};
