# CareerPulse Landing Page Redesign

## Goal
Redesign the landing page with full crypto presale energy: 3D carousel, particle effects, animated mesh gradients, glassmorphism, holographic cards, neon glow accents.

## Color Palette
Cyan/green/purple — Matrix-meets-crypto. Electric green highlights, cyan accents, purple depth.
- Background: #0a0a0f
- Cyan: #00f0ff
- Green: #22ff88
- Purple: #8b5cf6
- Animated gradient text: cyan → green → purple cycling

## Hero
- Animated mesh gradient layer (slow-morphing blobs of cyan/green/purple at ~10% opacity) — canvas-based
- Particle constellation overlay (dots + connecting lines, mouse-reactive) — canvas-based
- Glowing animated gradient headline text
- Neon glow CTA buttons with pulse on hover
- 3D carousel below headline: 8 screenshots in circular ring, CSS preserve-3d + rotateY, auto-rotates ~20s/rev, draggable, front image 1.2x scale with cyan/green glow, mouse tilt via perspective shifts

## Feature Cards
- Glassmorphism: rgba(255,255,255,0.03), backdrop-filter blur(12px), border rgba(255,255,255,0.06)
- Hover: cyan/green glow border, 3D tilt tracking mouse position
- Icons: cyan neon outlined strokes with glow filter
- Section headers: animated gradient text (subtler than hero)
- Alternating sections: pure dark vs faint radial gradient spotlight

## Showcase Rows
- Side-by-side layout preserved
- Screenshots get holographic animated border (cycling cyan/green/purple shimmer)
- Hover: scale + glow intensify
- Checkmarks: cyan neon dots with pulse
- Theme comparison: glow divider line

## Holographic Stat Cards
- Glass background, backdrop-filter blur(16px)
- Rainbow/holographic shimmer border on hover (animated conic-gradient behind mask)
- Numbers count up from 0 on scroll (IntersectionObserver)
- Cyan text glow on completion with pulse

## How It Works
- Neon-outlined step number rings
- Animated dashed connecting line with cyan glow trail (stroke-dashoffset animation)
- Muted gray descriptions, white titles

## Sources & Tech
- Source chips: glassmorphism + cyan border glow on hover
- Tech cards: glass style + green accent line on left
- CTA: large glass card, animated mesh gradient background (saturated), glowing border, neon green CTA button with pulse
- Footer: dark, muted gray, cyan link hovers

## Tech
- All vanilla JS, no libraries
- Canvas for particles + mesh gradient
- CSS transforms for 3D carousel
- IntersectionObserver for scroll animations
- Single index.html file
