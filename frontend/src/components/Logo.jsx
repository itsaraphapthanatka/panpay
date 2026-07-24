import { useId } from "react";

/** PUNPAY wordmark — transparent SVG, scales to any height.
 *  - default: navy→teal "PUN" + green "PAY" (for light backgrounds)
 *  - light:   white "PUN" + green "PAY" (for dark backgrounds, e.g. the sidebar)
 *  A subtle network-node motif is clipped inside the "PUN" letters. */
export default function Logo({ height = 30, light = false, style, className }) {
  const uid = useId().replace(/:/g, "");
  const blue = `blue-${uid}`;
  const green = `green-${uid}`;
  const clip = `punclip-${uid}`;

  const FONT = "'Arial Black', 'Helvetica Neue', Arial, sans-serif";
  const punFill = light ? "#ffffff" : `url(#${blue})`;
  const nodeColor = light ? "#1b8fb3" : "#a5ecff";

  // network nodes (within the PUN bounding box), clipped to the glyphs
  const nodes = [
    [40, 24], [78, 18], [70, 46], [104, 30], [120, 52], [96, 60],
  ];
  const links = [[0, 1], [0, 2], [1, 3], [2, 3], [3, 4], [2, 5], [4, 5]];

  return (
    <svg
      viewBox="0 0 250 72"
      height={height}
      role="img"
      aria-label="PUNPAY"
      style={{ display: "block", width: "auto", ...style }}
      className={className}
    >
      <defs>
        <linearGradient id={blue} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#0a3d8f" />
          <stop offset="1" stopColor="#1b8fb3" />
        </linearGradient>
        <linearGradient id={green} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#16a34a" />
          <stop offset="1" stopColor="#2ecc56" />
        </linearGradient>
        {/* clip = the SAME wordmark geometry, so nodes land exactly inside the glyphs */}
        <clipPath id={clip}>
          <text x="4" y="57" textLength="242" lengthAdjust="spacingAndGlyphs"
                fontFamily={FONT} fontWeight="900" fontSize="62" letterSpacing="-1">PUNPAY</text>
        </clipPath>
      </defs>

      {/* PUNPAY — one continuous word, locked to textLength so it never overflows/clips */}
      <text x="4" y="57" textLength="242" lengthAdjust="spacingAndGlyphs"
            fontFamily={FONT} fontWeight="900" fontSize="62" letterSpacing="-1">
        <tspan fill={punFill}>PUN</tspan>
        <tspan fill={`url(#${green})`}>PAY</tspan>
      </text>

      {/* network motif clipped inside the PUN letters */}
      <g clipPath={`url(#${clip})`} stroke={nodeColor} strokeWidth="1.6" opacity="0.85">
        {links.map(([a, b], i) => (
          <line key={i} x1={nodes[a][0]} y1={nodes[a][1]} x2={nodes[b][0]} y2={nodes[b][1]} />
        ))}
        {nodes.map(([cx, cy], i) => (
          <circle key={i} cx={cx} cy={cy} r="3.4" fill={nodeColor} stroke="none" />
        ))}
      </g>
    </svg>
  );
}
