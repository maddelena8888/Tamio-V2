import {
  AbsoluteFill,
  Audio,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
  staticFile,
} from 'remotion';

// ============================================================================
// Brand Colors & Constants
// ============================================================================

const COLORS = {
  tomato: '#FF4F3F',
  coral: '#ff6b5b',
  mintCream: '#F2F8F5',
  gunmetal: '#112331',
  darkBg: '#1a2332',
  mimiPink: '#FFD6F0',
  lime: '#C5FF35',
  white: '#FFFFFF',
  muted: '#6B7B8A',
  green: '#22C55E',
  amber: '#F59E0B',
  xeroBlue: '#13B5EA',
  slackPurple: '#4A154B',
};

const glassStyle = {
  background: 'rgba(255, 255, 255, 0.95)',
  backdropFilter: 'blur(20px)',
  border: '1px solid rgba(255, 255, 255, 0.3)',
  boxShadow: '0 8px 32px rgba(17, 35, 49, 0.1)',
};

const fontFamily = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif';

// ============================================================================
// Tamio Logo Component
// ============================================================================

const TamioLogo: React.FC<{ color?: string; size?: number }> = ({
  color = COLORS.gunmetal,
  size = 200
}) => {
  const aspectRatio = 2745 / 679;
  const width = size * aspectRatio;

  return (
    <svg width={width} height={size} viewBox="0 0 2745 679" fill="none">
      <path
        d="M2.16067e-07 256.5H70V87.9999H220.5V256.5H312.5V381.5H220.5V496C220.5 513 223 526.833 228 537.5C233 547.833 242.167 553 255.5 553C264.5 553 272.167 551 278.5 547C284.833 543 288.667 540.333 290 539L342 647C339.667 649 332.333 652.667 320 658C308 663.333 292.667 668.167 274 672.5C255.333 676.833 234.5 679 211.5 679C170.5 679 136.667 667.5 110 644.5C83.3333 621.167 70 585.333 70 537V381.5H2.16067e-07V256.5ZM716.781 667V600.5C713.781 607.167 706.115 616.833 693.781 629.5C681.781 642.167 665.781 653.667 645.781 664C625.781 674 602.448 679 575.781 679C535.781 679 500.781 669.333 470.781 650C440.781 630.333 417.448 604.167 400.781 571.5C384.115 538.5 375.781 502 375.781 462C375.781 422 384.115 385.667 400.781 353C417.448 320 440.781 293.667 470.781 274C500.781 254.333 535.781 244.5 575.781 244.5C601.448 244.5 623.948 248.667 643.281 257C662.615 265 678.281 274.667 690.281 286C702.281 297 710.615 307.167 715.281 316.5V256.5H866.281V667H716.781ZM524.781 462C524.781 480.667 529.115 497.5 537.781 512.5C546.448 527.167 557.948 538.667 572.281 547C586.948 555.333 603.115 559.5 620.781 559.5C639.115 559.5 655.281 555.333 669.281 547C683.281 538.667 694.281 527.167 702.281 512.5C710.615 497.5 714.781 480.667 714.781 462C714.781 443.333 710.615 426.667 702.281 412C694.281 397 683.281 385.333 669.281 377C655.281 368.333 639.115 364 620.781 364C603.115 364 586.948 368.333 572.281 377C557.948 385.333 546.448 397 537.781 412C529.115 426.667 524.781 443.333 524.781 462ZM1527.23 244.5C1558.23 244.5 1585.57 251 1609.23 264C1632.9 276.667 1651.4 296.333 1664.73 323C1678.4 349.667 1685.23 384 1685.23 426V667H1535.73V449C1535.73 420.333 1531.4 397.167 1522.73 379.5C1514.07 361.833 1496.9 353 1471.23 353C1455.9 353 1442.4 357 1430.73 365C1419.07 373 1410.07 384.167 1403.73 398.5C1397.4 412.5 1394.23 429.333 1394.23 449V667H1254.73V449C1254.73 420.333 1249.9 397.167 1240.23 379.5C1230.9 361.833 1214.23 353 1190.23 353C1174.9 353 1161.4 357 1149.73 365C1138.07 372.667 1129.07 383.667 1122.73 398C1116.73 412 1113.73 429 1113.73 449V667H962.734V256.5H1113.73V315C1117.73 304.667 1126.4 294.167 1139.73 283.5C1153.4 272.5 1170.23 263.333 1190.23 256C1210.23 248.333 1231.4 244.5 1253.73 244.5C1278.07 244.5 1298.4 248.167 1314.73 255.5C1331.07 262.5 1344.4 272 1354.73 284C1365.4 296 1373.9 309 1380.23 323C1384.9 311 1394.07 299 1407.73 287C1421.73 274.667 1439.07 264.5 1459.73 256.5C1480.73 248.5 1503.23 244.5 1527.23 244.5ZM1778.28 667V256.5H1930.28V667H1778.28ZM1856.28 172C1832.28 172 1811.95 163.667 1795.28 147C1778.61 130 1770.28 109.833 1770.28 86.5C1770.28 63.1666 1778.61 43 1795.28 26C1812.28 8.66662 1832.61 -5.53131e-05 1856.28 -5.53131e-05C1871.95 -5.53131e-05 1886.28 3.99995 1899.28 12C1912.28 19.6666 1922.78 30 1930.78 43C1938.78 56 1942.78 70.5 1942.78 86.5C1942.78 109.833 1934.28 130 1917.28 147C1900.28 163.667 1879.95 172 1856.28 172ZM2244 679C2199 679 2159 669.833 2124 651.5C2089.33 632.833 2062 607.333 2042 575C2022.33 542.333 2012.5 505 2012.5 463C2012.5 421 2022.33 383.667 2042 351C2062 318 2089.33 292 2124 273C2159 254 2199 244.5 2244 244.5C2289 244.5 2328.67 254 2363 273C2397.33 292 2424.17 318 2443.5 351C2462.83 383.667 2472.5 421 2472.5 463C2472.5 505 2462.83 542.333 2443.5 575C2424.17 607.333 2397.33 632.833 2363 651.5C2328.67 669.833 2289 679 2244 679ZM2244 554C2261.33 554 2276.33 550.167 2289 542.5C2301.67 534.833 2311.5 524 2318.5 510C2325.5 496 2329 480.167 2329 462.5C2329 444.5 2325.5 428.5 2318.5 414.5C2311.5 400.5 2301.67 389.5 2289 381.5C2276.33 373.5 2261.33 369.5 2244 369.5C2226.67 369.5 2211.5 373.5 2198.5 381.5C2185.83 389.5 2175.83 400.5 2168.5 414.5C2161.5 428.5 2158 444.5 2158 462.5C2158 480.167 2161.5 496 2168.5 510C2175.83 524 2185.83 534.833 2198.5 542.5C2211.5 550.167 2226.67 554 2244 554ZM2653.6 679C2628.93 679 2607.6 670.167 2589.6 652.5C2571.93 634.5 2563.1 613.167 2563.1 588.5C2563.1 563.167 2571.93 541.667 2589.6 524C2607.6 506 2628.93 497 2653.6 497C2678.93 497 2700.43 506 2718.1 524C2735.77 541.667 2744.6 563.167 2744.6 588.5C2744.6 613.167 2735.77 634.5 2718.1 652.5C2700.43 670.167 2678.93 679 2653.6 679Z"
        fill={color}
      />
    </svg>
  );
};

// ============================================================================
// Icon Components
// ============================================================================

const CheckIcon: React.FC<{ size?: number; color?: string }> = ({ size = 24, color = COLORS.green }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);

const AlertIcon: React.FC<{ size?: number; color?: string }> = ({ size = 24, color = COLORS.coral }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/>
    <line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);

const XeroIcon: React.FC<{ size?: number }> = ({ size = 48 }) => (
  <div style={{
    width: size,
    height: size,
    borderRadius: size * 0.25,
    background: COLORS.xeroBlue,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: size * 0.4,
    fontWeight: 700,
    color: COLORS.white,
  }}>
    X
  </div>
);

const BankIcon: React.FC<{ size?: number }> = ({ size = 48 }) => (
  <div style={{
    width: size,
    height: size,
    borderRadius: size * 0.25,
    background: COLORS.gunmetal,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }}>
    <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="none" stroke={COLORS.white} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="6" width="22" height="15" rx="2" ry="2"/>
      <line x1="1" y1="10" x2="23" y2="10"/>
    </svg>
  </div>
);

const PayrollIcon: React.FC<{ size?: number }> = ({ size = 48 }) => (
  <div style={{
    width: size,
    height: size,
    borderRadius: size * 0.25,
    background: COLORS.green,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }}>
    <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="none" stroke={COLORS.white} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
      <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  </div>
);

const ClockIcon: React.FC<{ size?: number; color?: string }> = ({ size = 48, color = COLORS.white }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <polyline points="12 6 12 12 16 14"/>
  </svg>
);

const CursorIcon: React.FC<{ size?: number; color?: string }> = ({ size = 24, color = COLORS.gunmetal }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
    <path d="M4 4l7.07 17 2.51-7.39L21 11.07z"/>
  </svg>
);

const SendIcon: React.FC<{ size?: number; color?: string }> = ({ size = 24, color = COLORS.white }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);

// ============================================================================
// SECTION 1: Opening Page 1 (0-2.5s = 75 frames)
// "Your finance tools show you problems. They don't fix them."
// ============================================================================

const OpeningPage1Scene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Line 1: "Your finance tools show you problems." - dramatic entrance
  const line1Opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  const line1Y = interpolate(frame, [0, 20], [40, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const line1Scale = interpolate(frame, [0, 20], [0.95, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const line1Blur = interpolate(frame, [0, 15], [8, 0], { extrapolateRight: 'clamp' });

  // Line 2: "They don't fix them." - punchy entrance with glow
  const line2Delay = 27;
  const line2Opacity = interpolate(frame, [line2Delay, line2Delay + 18], [0, 1], { extrapolateRight: 'clamp' });
  const line2Y = interpolate(frame, [line2Delay, line2Delay + 18], [30, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const line2Scale = interpolate(frame, [line2Delay, line2Delay + 18], [0.9, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Glow pulse for line 2 after it appears
  const glowIntensity = frame > line2Delay + 18
    ? interpolate(frame % 60, [0, 30, 60], [0.4, 0.7, 0.4])
    : interpolate(frame, [line2Delay, line2Delay + 18], [0, 0.5], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: COLORS.darkBg, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      <div style={{ textAlign: 'center', maxWidth: 1100, padding: 40 }}>
        {/* Line 1 */}
        <div style={{
          opacity: line1Opacity,
          transform: `translateY(${line1Y}px) scale(${line1Scale})`,
          filter: `blur(${line1Blur}px)`,
          fontSize: 64,
          fontWeight: 600,
          color: COLORS.white,
          marginBottom: 28,
          lineHeight: 1.2,
          textShadow: `0 0 40px rgba(255,255,255,0.1)`,
        }}>
          Your finance tools show you problems.
        </div>

        {/* Line 2 - bolder, coral emphasis with glow */}
        <div style={{
          opacity: line2Opacity,
          transform: `translateY(${line2Y}px) scale(${line2Scale})`,
          fontSize: 72,
          fontWeight: 700,
          color: COLORS.coral,
          lineHeight: 1.2,
          textShadow: `0 0 ${30 + glowIntensity * 40}px ${COLORS.coral}${Math.floor(glowIntensity * 99).toString().padStart(2, '0')}`,
        }}>
          They don't fix them.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 2: Opening Page 2 (2.5-5s = 75 frames)
// "You're always reacting. Always behind. Always too late."
// Staggered triple beat - builds to the punch
// ============================================================================

const OpeningPage2Scene: React.FC = () => {
  const frame = useCurrentFrame();

  // Line 1: "You're always reacting." - dramatic entrance
  const line1Opacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: 'clamp' });
  const line1Y = interpolate(frame, [0, 18], [30, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const line1Scale = interpolate(frame, [0, 18], [0.95, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const line1Blur = interpolate(frame, [0, 12], [6, 0], { extrapolateRight: 'clamp' });

  // Line 2: "Always behind." - faster, more urgent
  const line2Delay = 28;
  const line2Opacity = interpolate(frame, [line2Delay, line2Delay + 15], [0, 1], { extrapolateRight: 'clamp' });
  const line2Y = interpolate(frame, [line2Delay, line2Delay + 15], [25, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const line2Scale = interpolate(frame, [line2Delay, line2Delay + 15], [0.95, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const line2Blur = interpolate(frame, [line2Delay, line2Delay + 10], [5, 0], { extrapolateRight: 'clamp' });

  // Line 3: "Always too late." - THE PUNCH with intense glow
  const line3Delay = 55;
  const line3Opacity = interpolate(frame, [line3Delay, line3Delay + 15], [0, 1], { extrapolateRight: 'clamp' });
  const line3Scale = interpolate(frame, [line3Delay, line3Delay + 15], [0.85, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Intense glow pulse for the punch line
  const glowIntensity = frame > line3Delay + 15
    ? interpolate(frame % 45, [0, 22, 45], [0.5, 0.9, 0.5])
    : interpolate(frame, [line3Delay, line3Delay + 15], [0, 0.7], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: COLORS.darkBg, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      <div style={{ textAlign: 'center', maxWidth: 1100, padding: 40 }}>
        {/* Line 1 */}
        <div style={{
          opacity: line1Opacity,
          transform: `translateY(${line1Y}px) scale(${line1Scale})`,
          filter: `blur(${line1Blur}px)`,
          fontSize: 56,
          fontWeight: 600,
          color: COLORS.white,
          marginBottom: 20,
          lineHeight: 1.2,
          textShadow: '0 0 30px rgba(255,255,255,0.1)',
        }}>
          You're always reacting.
        </div>

        {/* Line 2 */}
        <div style={{
          opacity: line2Opacity,
          transform: `translateY(${line2Y}px) scale(${line2Scale})`,
          filter: `blur(${line2Blur}px)`,
          fontSize: 64,
          fontWeight: 700,
          color: COLORS.white,
          marginBottom: 24,
          lineHeight: 1.2,
          textShadow: '0 0 30px rgba(255,255,255,0.15)',
        }}>
          Always behind.
        </div>

        {/* Line 3 - THE PUNCH - largest, coral/red with intense glow */}
        <div style={{
          opacity: line3Opacity,
          transform: `scale(${line3Scale})`,
          fontSize: 80,
          fontWeight: 700,
          color: COLORS.coral,
          lineHeight: 1.1,
          textShadow: `0 0 ${40 + glowIntensity * 60}px ${COLORS.coral}${Math.floor(glowIntensity * 99).toString().padStart(2, '0')}, 0 0 ${20 + glowIntensity * 30}px ${COLORS.coral}60`,
        }}>
          Always too late.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 3: Alert Hits (6-9s = 90 frames)
// ============================================================================

const AlertHitsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Alert SLAMS in (not gentle fade)
  const slamProgress = spring({ frame, fps, config: { damping: 8, stiffness: 200 } });
  const alertScale = interpolate(slamProgress, [0, 1], [1.3, 1]);
  const alertOpacity = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: 'clamp' });

  // Pulsing indicator
  const pulseScale = interpolate(frame % 30, [0, 15, 30], [1, 1.2, 1]);
  const pulseOpacity = interpolate(frame % 30, [0, 15, 30], [0.6, 1, 0.6]);

  return (
    <AbsoluteFill style={{ background: COLORS.darkBg, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Alert card that SLAMS in */}
      <div style={{
        opacity: alertOpacity,
        transform: `scale(${alertScale})`,
        ...glassStyle,
        padding: 40,
        borderRadius: 24,
        border: `3px solid ${COLORS.coral}50`,
        maxWidth: 650,
        boxShadow: `0 20px 80px rgba(0, 0, 0, 0.4), 0 0 60px ${COLORS.coral}40`,
      }}>
        {/* Header with pulsing dot */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <div style={{
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: COLORS.coral,
            opacity: pulseOpacity,
            transform: `scale(${pulseScale})`,
            boxShadow: `0 0 20px ${COLORS.coral}80`,
          }} />
          <span style={{ fontSize: 14, fontWeight: 700, color: COLORS.coral, textTransform: 'uppercase', letterSpacing: 2 }}>
            Attention Required
          </span>
        </div>

        {/* Headline */}
        <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.gunmetal, marginBottom: 10 }}>
          Payroll at Risk
        </div>
        <div style={{ fontSize: 20, color: COLORS.muted, marginBottom: 28 }}>
          Friday's payroll will be $12K short
        </div>

        {/* Why section */}
        <div style={{ fontSize: 14, fontWeight: 600, color: COLORS.muted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
          Why:
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 18, color: COLORS.gunmetal }}>
            <span style={{ color: COLORS.coral }}>•</span>
            RetailCo invoice 14 days overdue (<span style={{ fontWeight: 700, color: COLORS.coral }}>$52K</span>)
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 18, color: COLORS.gunmetal }}>
            <span style={{ color: COLORS.coral }}>•</span>
            Quarterly VAT due tomorrow (<span style={{ fontWeight: 700, color: COLORS.coral }}>$18K</span>)
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 4: The Pivot - Just "Introducing" + Logo
// ============================================================================

const PivotScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // "Introducing" fades in
  const introducingOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });
  const introducingY = interpolate(frame, [0, 20], [15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Logo springs in after
  const logoScale = spring({ frame: frame - 30, fps, config: { damping: 15, stiffness: 100 } });

  return (
    <AbsoluteFill style={{ background: COLORS.darkBg, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          opacity: introducingOpacity,
          transform: `translateY(${introducingY}px)`,
          fontSize: 24,
          fontWeight: 500,
          color: 'rgba(255,255,255,0.6)',
          marginBottom: 32,
          letterSpacing: 4,
          textTransform: 'uppercase',
        }}>
          Introducing
        </div>
        <div style={{ transform: `scale(${Math.max(0, logoScale)})` }}>
          <TamioLogo color={COLORS.white} size={160} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 5: Connect Once (14-18s = 120 frames) - VERTICAL LIST
// ============================================================================

const ConnectScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Heading appears first
  const headingOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const headingY = interpolate(frame, [0, 15], [15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  const connections = [
    { icon: XeroIcon, label: 'Accounting', delay: 20 },
    { icon: BankIcon, label: 'Banking', delay: 45 },
    { icon: PayrollIcon, label: 'Payroll', delay: 70 },
  ];

  return (
    <AbsoluteFill style={{ background: COLORS.mintCream, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Heading */}
      <div style={{
        position: 'absolute',
        top: 200,
        opacity: headingOpacity,
        transform: `translateY(${headingY}px)`,
        fontSize: 44,
        fontWeight: 700,
        color: COLORS.gunmetal,
      }}>
        Connect once
      </div>

      {/* Vertical list of connections */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 60 }}>
        {connections.map((conn, i) => {
          const rowOpacity = interpolate(frame, [conn.delay, conn.delay + 15], [0, 1], { extrapolateRight: 'clamp' });
          const rowX = interpolate(frame, [conn.delay, conn.delay + 15], [-30, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

          // Checkmark appears after row
          const checkDelay = conn.delay + 20;
          const checkScale = spring({ frame: frame - checkDelay, fps, config: { damping: 10, stiffness: 150 } });
          const checkOpacity = interpolate(frame, [checkDelay, checkDelay + 10], [0, 1], { extrapolateRight: 'clamp' });

          const Icon = conn.icon;

          return (
            <div
              key={i}
              style={{
                opacity: rowOpacity,
                transform: `translateX(${rowX}px)`,
                ...glassStyle,
                padding: '20px 32px',
                borderRadius: 16,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                minWidth: 450,
                border: checkOpacity > 0.5 ? `2px solid ${COLORS.green}50` : '1px solid rgba(255, 255, 255, 0.3)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                <Icon size={48} />
                <span style={{ fontSize: 22, fontWeight: 600, color: COLORS.gunmetal }}>{conn.label}</span>
              </div>

              <div style={{
                opacity: checkOpacity,
                transform: `scale(${Math.max(0, checkScale)})`,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                color: COLORS.green,
                fontWeight: 600,
                fontSize: 16,
              }}>
                <CheckIcon size={22} color={COLORS.green} />
                Connected
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 6: Forecast (18-21s = 90 frames) - "See what's coming"
// ============================================================================

const ForecastScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Heading
  const headingOpacity = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const headingY = interpolate(frame, [0, 12], [15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Card
  const cardScale = spring({ frame: frame - 10, fps, config: { damping: 15, stiffness: 100 } });

  // Chart draws itself
  const forecastData = [420, 440, 455, 448, 470, 485, 478, 495, 510, 502, 525, 540, 482];
  const chartWidth = 550;
  const chartHeight = 140;
  const minValue = 400;
  const maxValue = 560;

  const getX = (i: number) => (i / (forecastData.length - 1)) * chartWidth;
  const getY = (value: number) => chartHeight - ((value - minValue) / (maxValue - minValue)) * chartHeight;

  const lineProgress = interpolate(frame, [25, 70], [0, 1], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const pathD = forecastData.map((value, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(value)}`).join(' ');

  // Number counts up
  const displayAmount = Math.round(interpolate(frame, [40, 75], [420, 482], { extrapolateRight: 'clamp' }));

  return (
    <AbsoluteFill style={{ background: COLORS.mintCream, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Heading */}
      <div style={{
        position: 'absolute',
        top: 200,
        opacity: headingOpacity,
        transform: `translateY(${headingY}px)`,
        fontSize: 44,
        fontWeight: 700,
        color: COLORS.gunmetal,
      }}>
        See what's coming
      </div>

      {/* Forecast card */}
      <div style={{
        ...glassStyle,
        padding: 36,
        borderRadius: 24,
        transform: `scale(${Math.max(0, cardScale)})`,
        marginTop: 60,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.gunmetal }}>13-Week Cash Forecast</div>
            <div style={{ fontSize: 14, color: COLORS.muted }}>Rolling projection</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 42, fontWeight: 700, color: COLORS.gunmetal }}>${displayAmount}K</div>
          </div>
        </div>

        {/* Chart */}
        <svg width={chartWidth} height={chartHeight} style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.lime} stopOpacity="0.3" />
              <stop offset="100%" stopColor={COLORS.lime} stopOpacity="0.05" />
            </linearGradient>
          </defs>

          <path
            d={pathD + ` L ${chartWidth} ${chartHeight} L 0 ${chartHeight} Z`}
            fill="url(#areaGrad)"
            style={{ clipPath: `inset(0 ${100 - lineProgress * 100}% 0 0)` }}
          />

          <path
            d={pathD}
            fill="none"
            stroke={COLORS.lime}
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="1000"
            strokeDashoffset={1000 - 1000 * lineProgress}
          />

          {lineProgress >= 0.95 && (
            <circle
              cx={getX(forecastData.length - 1)}
              cy={getY(482)}
              r={10}
              fill={COLORS.lime}
              stroke={COLORS.white}
              strokeWidth="3"
            />
          )}
        </svg>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 7: Alert + Actions (21-25s = 120 frames) - "Spot issues in real-time"
// ============================================================================

const AlertActionsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Heading
  const headingOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const headingY = interpolate(frame, [0, 15], [15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Alert card
  const alertScale = spring({ frame: frame - 15, fps, config: { damping: 12, stiffness: 120 } });

  // Actions appear staggered
  const actions = [
    { label: 'Chase RetailCo invoice', tag: null },
    { label: 'Delay vendor payment by 5 days', tag: 'Recommended', recommended: true },
    { label: 'Draw from credit line', tag: 'Last resort' },
  ];

  // Cursor animation
  const cursorVisible = frame > 85 && frame < 110;
  const cursorX = interpolate(frame, [85, 100], [150, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const cursorY = interpolate(frame, [85, 100], [80, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Selection happens at frame 105
  const selected = frame > 105;

  return (
    <AbsoluteFill style={{ background: COLORS.mintCream, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Heading - CHANGED */}
      <div style={{
        position: 'absolute',
        top: 160,
        opacity: headingOpacity,
        transform: `translateY(${headingY}px)`,
        fontSize: 44,
        fontWeight: 700,
        color: COLORS.gunmetal,
      }}>
        Spot issues in real-time
      </div>

      {/* Alert card with actions */}
      <div style={{
        ...glassStyle,
        padding: 36,
        borderRadius: 24,
        transform: `scale(${Math.max(0, alertScale)})`,
        marginTop: 40,
        maxWidth: 600,
        border: `2px solid ${COLORS.coral}30`,
      }}>
        {/* Alert header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <AlertIcon size={22} color={COLORS.coral} />
          <span style={{ fontSize: 22, fontWeight: 700, color: COLORS.gunmetal }}>Payroll at Risk</span>
        </div>
        <div style={{ fontSize: 16, color: COLORS.muted, marginBottom: 28 }}>
          Friday's payroll will be $12K short
        </div>

        {/* Recommended actions */}
        <div style={{ fontSize: 14, fontWeight: 600, color: COLORS.muted, marginBottom: 14, textTransform: 'uppercase', letterSpacing: 1 }}>
          Recommended actions:
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, position: 'relative' }}>
          {actions.map((action, i) => {
            const actionDelay = 40 + i * 10;
            const actionOpacity = interpolate(frame, [actionDelay, actionDelay + 10], [0, 1], { extrapolateRight: 'clamp' });
            const isThisSelected = selected && action.recommended;

            return (
              <div
                key={i}
                style={{
                  opacity: actionOpacity,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 18px',
                  borderRadius: 12,
                  background: isThisSelected ? `${COLORS.green}15` : action.recommended ? `${COLORS.lime}10` : 'transparent',
                  border: isThisSelected ? `2px solid ${COLORS.green}` : action.recommended ? `2px solid ${COLORS.lime}` : `1px solid ${COLORS.gunmetal}15`,
                  transform: isThisSelected ? 'scale(1.02)' : 'scale(1)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  {isThisSelected ? (
                    <div style={{ width: 20, height: 20, borderRadius: '50%', background: COLORS.green, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <CheckIcon size={14} color={COLORS.white} />
                    </div>
                  ) : (
                    <div style={{ width: 20, height: 20, borderRadius: '50%', border: `2px solid ${action.recommended ? COLORS.lime : COLORS.muted}` }} />
                  )}
                  <span style={{ fontSize: 16, fontWeight: 500, color: COLORS.gunmetal }}>{action.label}</span>
                </div>
                {action.tag && (
                  <span style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: action.recommended ? COLORS.green : COLORS.muted,
                    padding: '4px 10px',
                    background: action.recommended ? `${COLORS.green}15` : 'transparent',
                    borderRadius: 20,
                  }}>
                    {action.tag}
                  </span>
                )}
              </div>
            );
          })}

          {/* Cursor */}
          {cursorVisible && (
            <div style={{
              position: 'absolute',
              top: 55,
              left: 30,
              transform: `translate(${cursorX}px, ${cursorY}px)`,
            }}>
              <CursorIcon size={24} color={COLORS.gunmetal} />
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 8: Scenario Modeling (25-29s = 120 frames) - "Model any decision"
// ============================================================================

const ScenarioScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Heading
  const headingOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const headingY = interpolate(frame, [0, 15], [15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Card
  const cardScale = spring({ frame: frame - 15, fps, config: { damping: 12, stiffness: 100 } });

  // Typing animation
  const question = "What happens if I delay vendor payment by 5 days?";
  const typedLength = Math.min(question.length, Math.floor(interpolate(frame, [20, 55], [0, question.length], { extrapolateRight: 'clamp' })));
  const typedText = question.slice(0, typedLength);
  const showCursor = frame < 60 && frame % 20 < 10;

  // Metrics appear
  const metricsOpacity = interpolate(frame, [58, 70], [0, 1], { extrapolateRight: 'clamp' });
  const metricsScale = spring({ frame: frame - 58, fps, config: { damping: 12, stiffness: 100 } });

  // Insights appear one by one
  const insights = [
    "Within vendor's 30-day payment terms",
    "No late fees apply",
    "Covers Friday payroll gap",
  ];

  // Approve button
  const buttonOpacity = interpolate(frame, [95, 105], [0, 1], { extrapolateRight: 'clamp' });
  const buttonScale = spring({ frame: frame - 95, fps, config: { damping: 10, stiffness: 120 } });

  // Cursor clicks approve
  const approveClick = frame > 112;
  const approveCursorVisible = frame > 105 && frame < 118;
  const approveCursorX = interpolate(frame, [105, 112], [100, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  return (
    <AbsoluteFill style={{ background: COLORS.mintCream, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Heading */}
      <div style={{
        position: 'absolute',
        top: 140,
        opacity: headingOpacity,
        transform: `translateY(${headingY}px)`,
        fontSize: 44,
        fontWeight: 700,
        color: COLORS.gunmetal,
      }}>
        Model any decision
      </div>

      {/* Scenario card */}
      <div style={{
        ...glassStyle,
        padding: 36,
        borderRadius: 24,
        transform: `scale(${Math.max(0, cardScale)})`,
        marginTop: 40,
        maxWidth: 650,
      }}>
        {/* Question with typing */}
        <div style={{
          padding: 20,
          background: `${COLORS.gunmetal}08`,
          borderRadius: 14,
          marginBottom: 24,
        }}>
          <div style={{ fontSize: 20, color: COLORS.gunmetal, fontWeight: 500 }}>
            "{typedText}{showCursor && <span style={{ color: COLORS.coral }}>|</span>}"
          </div>
        </div>

        {/* Metrics */}
        <div style={{
          display: 'flex',
          gap: 16,
          opacity: metricsOpacity,
          transform: `scale(${Math.max(0, metricsScale)})`,
          marginBottom: 20,
        }}>
          <div style={{ flex: 1, padding: 18, background: COLORS.white, borderRadius: 14, border: `1px solid ${COLORS.gunmetal}10` }}>
            <div style={{ fontSize: 13, color: COLORS.muted, marginBottom: 4 }}>Cash Impact</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: COLORS.green }}>+$18K buffer</div>
          </div>
          <div style={{ flex: 1, padding: 18, background: COLORS.white, borderRadius: 14, border: `1px solid ${COLORS.gunmetal}10` }}>
            <div style={{ fontSize: 13, color: COLORS.muted, marginBottom: 4 }}>Runway</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: COLORS.gunmetal }}>52 wks (no change)</div>
          </div>
        </div>

        {/* Insights */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
          {insights.map((insight, i) => {
            const insightDelay = 75 + i * 6;
            const insightOpacity = interpolate(frame, [insightDelay, insightDelay + 6], [0, 1], { extrapolateRight: 'clamp' });
            const insightX = interpolate(frame, [insightDelay, insightDelay + 6], [-15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

            return (
              <div key={i} style={{
                opacity: insightOpacity,
                transform: `translateX(${insightX}px)`,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 15,
                color: COLORS.green,
              }}>
                <CheckIcon size={18} color={COLORS.green} />
                {insight}
              </div>
            );
          })}
        </div>

        {/* Approve button */}
        <div style={{
          opacity: buttonOpacity,
          transform: `scale(${Math.max(0, buttonScale)})`,
          display: 'flex',
          justifyContent: 'center',
          position: 'relative',
        }}>
          <div style={{
            padding: '14px 32px',
            background: approveClick ? COLORS.green : COLORS.coral,
            borderRadius: 12,
            fontSize: 16,
            fontWeight: 600,
            color: COLORS.white,
            boxShadow: `0 6px 20px ${approveClick ? COLORS.green : COLORS.coral}40`,
            transform: approveClick ? 'scale(0.98)' : 'scale(1)',
          }}>
            {approveClick ? 'Approved ✓' : 'Approve this action'}
          </div>

          {/* Cursor */}
          {approveCursorVisible && (
            <div style={{
              position: 'absolute',
              top: 10,
              right: 80,
              transform: `translateX(${approveCursorX}px)`,
            }}>
              <CursorIcon size={22} color={COLORS.gunmetal} />
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 9: Email Execution (29-33s = 120 frames) - "Execute in one click"
// ============================================================================

const EmailExecutionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Heading appears first
  const headingOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
  const headingY = interpolate(frame, [0, 15], [15, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Email UI appears
  const emailScale = spring({ frame: frame - 15, fps, config: { damping: 15, stiffness: 100 } });

  // Email content types out
  const emailBody = `Hi Accounts Team,

We'd like to adjust our payment timeline for invoice #4521 from Jan 28 to Feb 2. Please confirm this works on your end.

Best,
Sarah`;

  const typedLength = Math.min(emailBody.length, Math.floor(interpolate(frame, [20, 75], [0, emailBody.length], { extrapolateRight: 'clamp' })));
  const typedBody = emailBody.slice(0, typedLength);

  // Send button pulses
  const buttonReady = frame > 78;
  const buttonPulse = buttonReady ? interpolate(frame % 30, [0, 15, 30], [1, 1.05, 1]) : 1;

  // Cursor clicks send
  const sendCursorVisible = frame > 85 && frame < 105;
  const sendCursorY = interpolate(frame, [85, 95], [60, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  // Sent confirmation
  const sent = frame > 100;
  const sentScale = spring({ frame: frame - 100, fps, config: { damping: 8, stiffness: 150 } });

  return (
    <AbsoluteFill style={{ background: COLORS.mintCream, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Heading - NEW */}
      <div style={{
        position: 'absolute',
        top: 140,
        opacity: headingOpacity,
        transform: `translateY(${headingY}px)`,
        fontSize: 44,
        fontWeight: 700,
        color: COLORS.gunmetal,
      }}>
        Execute in one click
      </div>

      {/* Email composer */}
      <div style={{
        ...glassStyle,
        padding: 0,
        borderRadius: 20,
        transform: `scale(${Math.max(0, emailScale)})`,
        width: 580,
        overflow: 'hidden',
        boxShadow: '0 20px 60px rgba(17, 35, 49, 0.15)',
        marginTop: 60,
      }}>
        {/* Email header */}
        <div style={{ padding: '16px 24px', borderBottom: `1px solid ${COLORS.gunmetal}10`, background: `${COLORS.gunmetal}03` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: COLORS.gunmetal }}>New Message</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FF5F56' }} />
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FFBD2E' }} />
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#27CA40' }} />
            </div>
          </div>
        </div>

        {/* To/Subject */}
        <div style={{ padding: '16px 24px', borderBottom: `1px solid ${COLORS.gunmetal}10` }}>
          <div style={{ display: 'flex', marginBottom: 10 }}>
            <span style={{ fontSize: 14, color: COLORS.muted, width: 60 }}>To:</span>
            <span style={{ fontSize: 14, color: COLORS.gunmetal }}>accounts@vendor.com</span>
          </div>
          <div style={{ display: 'flex' }}>
            <span style={{ fontSize: 14, color: COLORS.muted, width: 60 }}>Subject:</span>
            <span style={{ fontSize: 14, color: COLORS.gunmetal, fontWeight: 500 }}>Payment timing adjustment</span>
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: 24, minHeight: 160 }}>
          <div style={{ fontSize: 15, color: COLORS.gunmetal, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
            {typedBody}
            {frame < 80 && <span style={{ color: COLORS.coral }}>|</span>}
          </div>
        </div>

        {/* Send button area */}
        <div style={{ padding: '16px 24px', borderTop: `1px solid ${COLORS.gunmetal}10`, display: 'flex', justifyContent: 'flex-end', position: 'relative' }}>
          {sent ? (
            <div style={{
              transform: `scale(${Math.max(0, sentScale)})`,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '12px 24px',
              background: `${COLORS.green}15`,
              borderRadius: 10,
              color: COLORS.green,
              fontWeight: 600,
              fontSize: 15,
            }}>
              <CheckIcon size={20} color={COLORS.green} />
              Sent
            </div>
          ) : (
            <div style={{
              padding: '12px 28px',
              background: COLORS.coral,
              borderRadius: 10,
              fontSize: 15,
              fontWeight: 600,
              color: COLORS.white,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              transform: `scale(${buttonPulse})`,
              boxShadow: buttonReady ? `0 4px 16px ${COLORS.coral}40` : 'none',
            }}>
              <SendIcon size={18} color={COLORS.white} />
              Send
            </div>
          )}

          {/* Cursor */}
          {sendCursorVisible && (
            <div style={{
              position: 'absolute',
              right: 60,
              bottom: 20,
              transform: `translateY(${sendCursorY}px)`,
            }}>
              <CursorIcon size={22} color={COLORS.gunmetal} />
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 10: Resolution - Crisis Averted (33-36s = 90 frames) - NEW
// ============================================================================

const ResolutionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Card appears
  const cardScale = spring({ frame, fps, config: { damping: 12, stiffness: 120 } });
  const cardOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' });

  // Checkmark animation
  const checkScale = spring({ frame: frame - 20, fps, config: { damping: 8, stiffness: 150 } });

  // Action items appear
  const action1Opacity = interpolate(frame, [35, 45], [0, 1], { extrapolateRight: 'clamp' });
  const action2Opacity = interpolate(frame, [45, 55], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ background: COLORS.darkBg, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Resolved card - same design as alert but GREEN */}
      <div style={{
        opacity: cardOpacity,
        transform: `scale(${Math.max(0, cardScale)})`,
        ...glassStyle,
        padding: 40,
        borderRadius: 24,
        border: `3px solid ${COLORS.green}50`,
        maxWidth: 650,
        boxShadow: `0 20px 80px rgba(0, 0, 0, 0.4), 0 0 60px ${COLORS.green}30`,
      }}>
        {/* Header with checkmark */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <div style={{
            transform: `scale(${Math.max(0, checkScale)})`,
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: COLORS.green,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <CheckIcon size={18} color={COLORS.white} />
          </div>
          <span style={{ fontSize: 14, fontWeight: 700, color: COLORS.green, textTransform: 'uppercase', letterSpacing: 2 }}>
            Resolved
          </span>
        </div>

        {/* Headline - now positive */}
        <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.green, marginBottom: 10 }}>
          Payroll is Safe
        </div>
        <div style={{ fontSize: 20, color: COLORS.muted, marginBottom: 28 }}>
          Friday's payroll is fully covered
        </div>

        {/* Action taken section */}
        <div style={{ fontSize: 14, fontWeight: 600, color: COLORS.muted, marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
          Action taken:
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{
            opacity: action1Opacity,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontSize: 18,
            color: COLORS.gunmetal
          }}>
            <CheckIcon size={20} color={COLORS.green} />
            Vendor payment delayed by 5 days
          </div>
          <div style={{
            opacity: action2Opacity,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontSize: 18,
            color: COLORS.gunmetal
          }}>
            <CheckIcon size={20} color={COLORS.green} />
            Email sent to accounts@vendor.com
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 11: Benefit Statement (36-40s = 120 frames)
// ============================================================================

const BenefitScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Clock animation
  const pulseScale = interpolate(frame % 45, [0, 22, 45], [1, 1.1, 1]);
  const clockOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });

  // Text sequence
  const text1Opacity = interpolate(frame, [15, 30], [0, 1], { extrapolateRight: 'clamp' });
  const text1Y = interpolate(frame, [15, 30], [20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  const text2Opacity = interpolate(frame, [40, 55], [0, 1], { extrapolateRight: 'clamp' });
  const text2Y = interpolate(frame, [40, 55], [20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  const text3Opacity = interpolate(frame, [65, 80], [0, 1], { extrapolateRight: 'clamp' });
  const text3Scale = spring({ frame: frame - 65, fps, config: { damping: 10, stiffness: 120 } });

  return (
    <AbsoluteFill style={{ background: COLORS.darkBg, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      {/* Clock icon */}
      <div style={{
        position: 'absolute',
        top: 280,
        opacity: clockOpacity,
        transform: `scale(${pulseScale})`,
      }}>
        <div style={{
          padding: 24,
          background: `${COLORS.lime}20`,
          borderRadius: '50%',
        }}>
          <ClockIcon size={48} color={COLORS.lime} />
        </div>
      </div>

      {/* Text */}
      <div style={{ textAlign: 'center', marginTop: 150 }}>
        <div style={{
          opacity: text1Opacity,
          transform: `translateY(${text1Y}px)`,
          fontSize: 48,
          fontWeight: 600,
          color: COLORS.white,
          marginBottom: 16,
        }}>
          Decide faster.
        </div>
        <div style={{
          opacity: text2Opacity,
          transform: `translateY(${text2Y}px)`,
          fontSize: 48,
          fontWeight: 600,
          color: COLORS.coral,
          marginBottom: 16,
        }}>
          Operate smarter.
        </div>
        <div style={{
          opacity: text3Opacity,
          transform: `scale(${Math.max(0, text3Scale)})`,
          fontSize: 64,
          fontWeight: 700,
          color: COLORS.lime,
        }}>
          24/7.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// SECTION 12: Close (40-46s = 180 frames)
// ============================================================================

const CloseScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({ frame, fps, config: { damping: 15, stiffness: 100 } });

  const taglineOpacity = interpolate(frame, [35, 55], [0, 1], { extrapolateRight: 'clamp' });
  const taglineY = interpolate(frame, [35, 55], [20, 0], { extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  const ctaOpacity = interpolate(frame, [80, 100], [0, 1], { extrapolateRight: 'clamp' });
  const ctaScale = spring({ frame: frame - 80, fps, config: { damping: 15, stiffness: 100 } });

  return (
    <AbsoluteFill style={{ background: COLORS.darkBg, justifyContent: 'center', alignItems: 'center', fontFamily }}>
      <div style={{ textAlign: 'center' }}>
        {/* Logo */}
        <div style={{ transform: `scale(${Math.max(0, logoScale)})`, marginBottom: 50 }}>
          <TamioLogo color={COLORS.white} size={160} />
        </div>

        {/* Tagline */}
        <div style={{
          opacity: taglineOpacity,
          transform: `translateY(${taglineY}px)`,
          marginBottom: 60,
        }}>
          <span style={{ fontSize: 48, fontWeight: 600, color: COLORS.white }}>Forecast. </span>
          <span style={{ fontSize: 48, fontWeight: 600, color: COLORS.coral }}>Decide. </span>
          <span style={{ fontSize: 48, fontWeight: 600, color: COLORS.lime }}>Execute.</span>
        </div>

        {/* CTA */}
        <div style={{
          opacity: ctaOpacity,
          transform: `scale(${Math.max(0, ctaScale)})`,
        }}>
          <div style={{
            display: 'inline-block',
            padding: '18px 40px',
            background: COLORS.coral,
            borderRadius: 16,
            fontSize: 20,
            fontWeight: 600,
            color: COLORS.white,
            boxShadow: `0 8px 32px ${COLORS.coral}40`,
          }}>
            Get started →
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// Main Composition
// ============================================================================

export const TamioDemo: React.FC = () => {
  // REVISED NARRATIVE - ~46 seconds at 30fps = 1380 frames
  //
  // SECTION 1:  Opening Page 1 (0-2.5s)       = frames 0-75
  //             "Your finance tools show you problems. They don't fix them."
  // SECTION 2:  Opening Page 2 (2.5-5.5s)     = frames 75-165 (slower triple beat)
  //             "You're always reacting. Always behind. Always too late."
  // SECTION 3:  Alert Hits (5.5-7s)           = frames 165-210 (shorter - just SLAM and hold)
  // SECTION 4:  The Pivot (7-10s)             = frames 210-300 (just Introducing + Logo)
  // SECTION 5:  Connect Once (10-14s)         = frames 300-420
  // SECTION 6:  Forecast (14-17s)             = frames 420-510
  // SECTION 7:  Alert + Actions (17-21s)      = frames 510-630
  // SECTION 8:  Scenario Modeling (21-25s)    = frames 630-750
  // SECTION 9:  Email Execution (25-29s)      = frames 750-870
  // SECTION 10: Resolution (29-32s)           = frames 870-960
  // SECTION 11: Benefit Statement (32-36s)    = frames 960-1080
  // SECTION 12: Close (36-46s)                = frames 1080-1380

  return (
    <AbsoluteFill>
      {/* ===== AUDIO TRACKS ===== */}

      {/* Background music - plays throughout */}
      <Audio src={staticFile('audio/technology-422298.mp3')} volume={0.25} />

      {/* Whoosh + notification when alert SLAMS in (frame 165) */}
      <Sequence from={165}>
        <Audio src={staticFile('audio/simple-whoosh-382724.mp3')} volume={0.6} />
      </Sequence>
      <Sequence from={168}>
        <Audio src={staticFile('audio/notification-sound-effect-372475.mp3')} volume={0.5} />
      </Sequence>

      {/* Logo intro sound when Tamio logo springs in (frame 232) */}
      <Sequence from={232}>
        <Audio src={staticFile('audio/brand-logo-intro-352299.mp3')} volume={0.5} />
      </Sequence>

      {/* Clicks for Connect scene "Connected" ticks */}
      <Sequence from={340}>
        <Audio src={staticFile('audio/click-sound-432501.mp3')} volume={0.4} />
      </Sequence>
      <Sequence from={365}>
        <Audio src={staticFile('audio/click-sound-432501.mp3')} volume={0.4} />
      </Sequence>
      <Sequence from={390}>
        <Audio src={staticFile('audio/click-sound-432501.mp3')} volume={0.4} />
      </Sequence>

      {/* Click: Select "Delay vendor payment" in Alert+Actions (frame 615) */}
      <Sequence from={615}>
        <Audio src={staticFile('audio/click-sound-432501.mp3')} volume={0.5} />
      </Sequence>

      {/* Typing for Scenario Modeling question (frames 650-685, ~1.2s) */}
      <Sequence from={650} durationInFrames={35}>
        <Audio src={staticFile('audio/keyboard-typing-sound-effect-335503.mp3')} volume={0.35} />
      </Sequence>

      {/* Click: Approve action in Scenario (frame 742) */}
      <Sequence from={742}>
        <Audio src={staticFile('audio/click-sound-432501.mp3')} volume={0.5} />
      </Sequence>

      {/* Typing for Email body (frames 770-825, ~1.8s) */}
      <Sequence from={770} durationInFrames={55}>
        <Audio src={staticFile('audio/keyboard-typing-sound-effect-335503.mp3')} volume={0.35} />
      </Sequence>

      {/* Click: Send email (frame 850) */}
      <Sequence from={850}>
        <Audio src={staticFile('audio/click-sound-432501.mp3')} volume={0.5} />
      </Sequence>

      {/* Notification for resolution success (frame 870) */}
      <Sequence from={870}>
        <Audio src={staticFile('audio/notification-sound-effect-372475.mp3')} volume={0.5} />
      </Sequence>

      {/* SECTION 1: Opening Page 1 */}
      <Sequence from={0} durationInFrames={75}>
        <OpeningPage1Scene />
      </Sequence>

      {/* SECTION 2: Opening Page 2 - Triple Beat (slower) */}
      <Sequence from={75} durationInFrames={90}>
        <OpeningPage2Scene />
      </Sequence>

      {/* SECTION 3: Alert SLAMS in (shorter) */}
      <Sequence from={165} durationInFrames={45}>
        <AlertHitsScene />
      </Sequence>

      {/* SECTION 4: The Pivot - Introducing Tamio */}
      <Sequence from={210} durationInFrames={90}>
        <PivotScene />
      </Sequence>

      {/* SECTION 5: Connect Once */}
      <Sequence from={300} durationInFrames={120}>
        <ConnectScene />
      </Sequence>

      {/* SECTION 6: Forecast */}
      <Sequence from={420} durationInFrames={90}>
        <ForecastScene />
      </Sequence>

      {/* SECTION 7: Alert + Recommended Actions */}
      <Sequence from={510} durationInFrames={120}>
        <AlertActionsScene />
      </Sequence>

      {/* SECTION 8: Scenario Modeling */}
      <Sequence from={630} durationInFrames={120}>
        <ScenarioScene />
      </Sequence>

      {/* SECTION 9: Email Execution */}
      <Sequence from={750} durationInFrames={120}>
        <EmailExecutionScene />
      </Sequence>

      {/* SECTION 10: Resolution - Crisis Averted */}
      <Sequence from={870} durationInFrames={90}>
        <ResolutionScene />
      </Sequence>

      {/* SECTION 11: Benefit Statement */}
      <Sequence from={960} durationInFrames={120}>
        <BenefitScene />
      </Sequence>

      {/* SECTION 12: Close */}
      <Sequence from={1080} durationInFrames={300}>
        <CloseScene />
      </Sequence>
    </AbsoluteFill>
  );
};
