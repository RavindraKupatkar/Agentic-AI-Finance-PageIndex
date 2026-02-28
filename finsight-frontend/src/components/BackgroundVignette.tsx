"use client";

import { useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform, useMotionTemplate } from "framer-motion";

export function BackgroundVignette() {
    const mouseX = useMotionValue(0.5);
    const mouseY = useMotionValue(0.5);

    // Smooth the mouse values
    const smoothX = useSpring(mouseX, { damping: 50, stiffness: 400 });
    const smoothY = useSpring(mouseY, { damping: 50, stiffness: 400 });

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            mouseX.set(e.clientX / window.innerWidth);
            mouseY.set(e.clientY / window.innerHeight);
        };

        window.addEventListener("mousemove", handleMouseMove);
        return () => window.removeEventListener("mousemove", handleMouseMove);
    }, [mouseX, mouseY]);

    // useMotionTemplate to dynamically generate the background string
    const xPct = useTransform(smoothX, [0, 1], ["0%", "100%"]);
    const yPct = useTransform(smoothY, [0, 1], ["0%", "100%"]);
    const radialBg = useMotionTemplate`radial-gradient(circle 800px at ${xPct} ${yPct}, rgba(255,255,240,0.04) 0%, rgba(0,0,0,0) 100%)`;

    return (
        <div className="fixed inset-0 z-[-50] pointer-events-none overflow-hidden bg-[#080808]">
            {/* The base dark background is slightly darker than #111111 to make the glows pop */}

            {/* Edge Vignette Glows (Static but breathing) */}
            <motion.div
                className="absolute -top-[40%] -left-[20%] w-[80%] h-[80%] rounded-full mix-blend-screen blur-[120px]"
                style={{ background: "radial-gradient(circle, rgba(139,154,109,0.3) 0%, rgba(0,0,0,0) 70%)" }}
                animate={{ scale: [1, 1.05, 1], opacity: [0.4, 0.6, 0.4] }}
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            />

            <motion.div
                className="absolute -bottom-[40%] -right-[20%] w-[80%] h-[80%] rounded-full mix-blend-screen blur-[120px]"
                style={{ background: "radial-gradient(circle, rgba(0,180,216,0.15) 0%, rgba(0,0,0,0) 70%)" }}
                animate={{ scale: [1, 1.1, 1], opacity: [0.4, 0.7, 0.4] }}
                transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
            />

            {/* Mouse tracking glow */}
            <motion.div
                className="absolute inset-0 mix-blend-screen"
                style={{ background: radialBg }}
            />

            {/* Film Grain Texture overlay to match Landio style */}
            <div className="absolute inset-0 opacity-[0.04] mix-blend-overlay pointer-events-none" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}></div>
        </div>
    );
}
