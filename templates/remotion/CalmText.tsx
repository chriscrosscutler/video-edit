// A title, hook or CTA that fades in, holds still and fades out: nothing bounces, slides or pops.
// Plain white bold sans with a soft shadow (no outline, no card) reads over bright footage; the font and
// colours come from brand.ts. Place it inside a <Sequence from={start} durationInFrames={length}>; frames
// here are local.
import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {BRAND, SAFE} from './brand';

export const TEXT = {
	font: BRAND.fonts.sans,
	weight: 700,
	color: BRAND.colors.text,
	lineHeight: 1.2,
	shadow: BRAND.colors.shadow,
	/** Seconds: a soft landing in, a shorter exit (exits run 40-50% shorter than entrances). */
	fadeIn: 0.3,
	fadeOut: 0.17,
};

export type CalmTextProps = {
	text: string;
	/** Font size in px at 1080 wide. */
	size?: number;
	/** Top edge in px; the default sits in the title band clear of the platforms' top bar. */
	top?: number;
	/** Left and right edges in px: keep clear of the right-hand button rail. */
	x0?: number;
	x1?: number;
	/** Rise in px while fading in; 0 holds it dead still. */
	rise?: number;
	font?: string;
	color?: string;
};

export const CalmText: React.FC<CalmTextProps> = ({
	text,
	size = 80,
	top = 300,
	x0 = SAFE.x0,
	x1 = SAFE.x1,
	rise = 0,
	font = TEXT.font,
	color = TEXT.color,
}) => {
	const frame = useCurrentFrame();
	const {durationInFrames, fps} = useVideoConfig();
	const inF = Math.round(TEXT.fadeIn * fps);
	const outF = Math.round(TEXT.fadeOut * fps);
	const ease = Easing.bezier(0.16, 1, 0.3, 1);
	const fadeIn = interpolate(frame, [0, inF], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: ease,
	});
	const fadeOut = interpolate(frame, [durationInFrames - outF, durationInFrames], [1, 0], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: ease,
	});
	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					position: 'absolute',
					top: top + rise * (1 - fadeIn),
					left: x0,
					width: x1 - x0,
					textAlign: 'center',
					fontFamily: font,
					fontWeight: TEXT.weight,
					fontSize: size,
					lineHeight: TEXT.lineHeight,
					color,
					textShadow: TEXT.shadow,
					opacity: Math.min(fadeIn, fadeOut),
				}}
			>
				{text}
			</div>
		</AbsoluteFill>
	);
};
