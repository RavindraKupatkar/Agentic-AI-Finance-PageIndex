"use client";

import { useEffect, useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Link from "next/link";
import {
  ArrowRight,
  Search,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Zap,
  Layers,
  FileText,
  BarChart3,
  Upload,
  MessageSquare,
  CheckCircle2,
  Lock,
  Trash2,
  Eye,
  AlertTriangle,
  Globe,
  Database,
  FileWarning,
  Bot,
  Github,
  Linkedin,
  Mail,
} from "lucide-react";

gsap.registerPlugin(ScrollTrigger);

/* ═══════════════════════════════════════════════════════════
   MAGNETIC HOVER WRAPPER
   ═══════════════════════════════════════════════════════════ */
function MagneticHover({
  children,
  className,
  depth = 50,
}: {
  children: React.ReactNode;
  className?: string;
  depth?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const mx = useSpring(x, { stiffness: 150, damping: 15, mass: 0.1 });
  const my = useSpring(y, { stiffness: 150, damping: 15, mass: 0.1 });
  const rotateX = useTransform(my, [-0.5, 0.5], ["12deg", "-12deg"]);
  const rotateY = useTransform(mx, [-0.5, 0.5], ["-12deg", "12deg"]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    x.set((e.clientX - rect.left) / rect.width - 0.5);
    y.set((e.clientY - rect.top) / rect.height - 0.5);
  };

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => {
        x.set(0);
        y.set(0);
      }}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
      className={className}
    >
      <div style={{ transform: `translateZ(${depth}px)` }}>{children}</div>
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════════════════════ */
export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLHeadingElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      /* Hero parallax */
      gsap.to(textRef.current, {
        yPercent: -40,
        ease: "none",
        scrollTrigger: {
          trigger: heroRef.current,
          start: "top top",
          end: "bottom top",
          scrub: true,
        },
      });

      /* Stack-scroll cards */
      const cards = document.querySelectorAll(".stack-card");
      cards.forEach((card, i) => {
        gsap.to(card, {
          scale: 0.9 + i * 0.01,
          scrollTrigger: {
            trigger: card,
            start: "top 15%",
            end: "bottom 15%",
            scrub: true,
          },
        });
      });

      /* How It Works steps stagger */
      gsap.fromTo(
        ".hiw-step",
        { y: 60, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.15,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: {
            trigger: "#how-it-works",
            start: "top 70%",
            toggleActions: "play none none reverse",
          },
        }
      );

      /* Security cards */
      gsap.fromTo(
        ".security-card",
        { y: 50, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.12,
          duration: 0.7,
          ease: "power3.out",
          scrollTrigger: {
            trigger: "#security",
            start: "top 70%",
            toggleActions: "play none none reverse",
          },
        }
      );

      /* Limitations cards */
      gsap.fromTo(
        ".limit-card",
        { y: 40, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          stagger: 0.1,
          duration: 0.6,
          ease: "power3.out",
          scrollTrigger: {
            trigger: "#limitations",
            start: "top 75%",
            toggleActions: "play none none reverse",
          },
        }
      );
    });

    return () => ctx.revert();
  }, []);

  /* ─── Feature data ─── */
  const features = [
    {
      icon: Search,
      title: "Semantic Search Engine",
      desc: "Find answers across thousands of pages using natural language queries. Understand context, not just keywords.",
      color: "#00F0FF",
      extra: null,
    },
    {
      icon: ShieldAlert,
      title: "Compliance & Risk Detection",
      desc: "Proactively identify regulatory risks and non-compliance issues in real-time across all documents.",
      color: "#8B9A6D",
      extra: (
        <div className="flex gap-2 mt-6">
          {["Pass", "Flag", "Pass", "Warn"].map((label, i) => (
            <span
              key={i}
              className={`px-3 py-1 rounded-full text-xs font-mono uppercase tracking-wider border ${label === "Pass"
                ? "bg-accent/10 text-accent border-accent/30"
                : label === "Flag"
                  ? "bg-destructive/10 text-destructive border-destructive/30"
                  : "bg-yellow-500/10 text-yellow-400 border-yellow-500/30"
                }`}
            >
              {label}
            </span>
          ))}
        </div>
      ),
    },
    {
      icon: BarChart3,
      title: "Automated Financial Modeling",
      desc: "Extract data points and build dynamic models instantly. Reduce manual entry by 90%.",
      color: "#FF2A6D",
      extra: (
        <div className="mt-6 w-full overflow-hidden rounded-xl border border-white/10">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 bg-white/3">
                <th className="px-4 py-2 text-left text-white/40 font-mono text-xs uppercase">
                  Metric
                </th>
                <th className="px-4 py-2 text-center text-white/40 font-mono text-xs uppercase">
                  Q1
                </th>
                <th className="px-4 py-2 text-center text-white/40 font-mono text-xs uppercase">
                  Q2
                </th>
                <th className="px-4 py-2 text-center text-white/40 font-mono text-xs uppercase">
                  Q3
                </th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Revenue", "2.1B", "2.4B", "2.8B"],
                ["EBITDA", "420M", "510M", "580M"],
                ["Net Inc.", "180M", "210M", "260M"],
              ].map((row, i) => (
                <tr key={i} className="border-b border-white/5">
                  <td className="px-4 py-2 text-white/70 font-medium">
                    {row[0]}
                  </td>
                  <td className="px-4 py-2 text-center text-white/50">
                    {row[1]}
                  </td>
                  <td className="px-4 py-2 text-center text-white/50">
                    {row[2]}
                  </td>
                  <td className="px-4 py-2 text-center text-accent font-semibold">
                    {row[3]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ),
    },
    {
      icon: Layers,
      title: "Comparison & Trend Analysis",
      desc: "Instantly compare key metrics across different periods and documents to uncover trends.",
      color: "#D4A574",
      extra: null,
    },
  ];

  const securityItems = [
    {
      icon: Lock,
      title: "End-to-End Encryption",
      desc: "All data encrypted in transit and at rest. Documents never exposed.",
    },
    {
      icon: Eye,
      title: "Zero Data Sharing",
      desc: "Processed privately. Nothing shared, sold, or used for training.",
    },
    {
      icon: Trash2,
      title: "Full Data Ownership",
      desc: "Delete anytime — permanently removed. You're always in control.",
    },
  ];

  const limitations = [
    {
      icon: FileText,
      title: "PDF-Only Input",
      desc: "Currently supports PDF documents only. Word, Excel, and image-based scans are not yet supported.",
    },
    {
      icon: Globe,
      title: "English Language Focus",
      desc: "Best accuracy with English-language financial documents. Multi-language support is on the roadmap.",
    },
    {
      icon: Database,
      title: "No Real-Time Data",
      desc: "Answers are based on uploaded documents only — no live market data or external API feeds.",
    },
    {
      icon: AlertTriangle,
      title: "LLM Hallucination Risk",
      desc: "While citations reduce risk, AI-generated answers should always be verified against source documents.",
    },
    {
      icon: FileWarning,
      title: "Document Size Limits",
      desc: "Individual PDFs are capped at 100MB / 1000 pages for optimal processing speed.",
    },
  ];

  return (
    <div className="w-full relative text-foreground overflow-hidden">
      {/* ═══ NAV ═══ */}
      <motion.nav
        className="fixed top-0 left-0 right-0 h-20 z-50 flex items-center justify-between px-6 md:px-10 glass-panel"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full border border-white/20 flex items-center justify-center text-white backdrop-blur-md bg-white/5">
            <Bot size={18} />
          </div>
          <span className="font-bold text-xl tracking-widest uppercase">
            FinSight
          </span>
        </div>

        <div className="hidden md:flex items-center gap-8 text-sm text-white/50 font-medium tracking-wide">
          <a
            href="#features"
            className="hover:text-white transition-colors duration-300"
          >
            Features
          </a>
          <a
            href="#how-it-works"
            className="hover:text-white transition-colors duration-300"
          >
            How It Works
          </a>
          <a
            href="#security"
            className="hover:text-white transition-colors duration-300"
          >
            Security
          </a>
          <a
            href="#cta"
            className="hover:text-white transition-colors duration-300"
          >
            Get Started
          </a>
        </div>

        <MagneticHover depth={30}>
          <Link
            href="/chat"
            className="flex items-center gap-2 bg-white text-black px-6 py-3 rounded-full text-sm font-bold uppercase tracking-wider hover:bg-accent hover:text-white transition-all duration-300"
          >
            Launch System <ArrowRight size={16} />
          </Link>
        </MagneticHover>
      </motion.nav>

      {/* ═══ HERO ═══ */}
      <section
        ref={heroRef}
        className="relative min-h-screen flex flex-col items-center justify-center pt-20 px-6"
      >
        <h1
          ref={textRef}
          className="relative z-10 text-5xl md:text-7xl lg:text-[7rem] font-bold text-center leading-[0.95] tracking-tighter"
        >
          From annual reports
          <br />
          to{" "}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent via-white to-primary opacity-90 inline-block">
            instant answers.
          </span>
        </h1>

        <motion.p
          className="relative z-10 mt-10 text-lg md:text-xl text-white/50 max-w-2xl text-center font-light leading-relaxed"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 1 }}
        >
          Unlocking financial intelligence from unstructured documents with
          unprecedented speed and accuracy. Powered by advanced AI.
        </motion.p>

        {/* Stat pills */}
        <motion.div
          className="relative z-10 flex flex-wrap gap-4 mt-12 justify-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.2, duration: 0.8 }}
        >
          <div className="stat-pill px-6 py-3 rounded-full flex items-center gap-3">
            <span className="text-accent font-bold text-lg">99.2%</span>
            <span className="text-white/60 text-sm font-medium">
              Citation Accuracy
            </span>
          </div>
          <div className="stat-pill px-6 py-3 rounded-full flex items-center gap-3">
            <Layers size={16} className="text-accent" />
            <span className="text-white/60 text-sm font-medium">
              Multi-PDF Analysis
            </span>
          </div>
          <div className="stat-pill px-6 py-3 rounded-full flex items-center gap-3">
            <Shield size={16} className="text-accent" />
            <span className="text-white/60 text-sm font-medium">
              Enterprise Security
            </span>
          </div>
        </motion.div>
      </section>

      {/* ═══ FEATURES — STACK SCROLL ═══ */}
      <section
        ref={featuresRef}
        id="features"
        className="relative px-6 max-w-5xl mx-auto pt-20 pb-10 z-10"
      >
        <motion.h2
          className="text-4xl md:text-5xl font-bold text-center mb-6 tracking-tight"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          Features
        </motion.h2>
        <p className="text-white/40 text-center mb-20 max-w-lg mx-auto font-light">
          Intelligent tools built for modern financial workflows
        </p>

        <div className="relative">
          {features.map((feat, i) => (
            <div
              key={i}
              className="stack-card mb-8"
              style={{ zIndex: features.length - i }}
            >
              <MagneticHover className="w-full" depth={25}>
                <div className="glass-panel p-8 md:p-12 rounded-[2rem] border border-white/10 bg-black/50 hover:bg-black/70 transition-colors group relative overflow-hidden grain-overlay">
                  <div
                    className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"
                    style={{
                      background: `radial-gradient(circle at 30% 30%, ${feat.color}15, transparent 70%)`,
                    }}
                  />
                  <div className="flex flex-col md:flex-row gap-8 items-start relative z-10">
                    <div
                      className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform duration-500"
                      style={{ color: feat.color }}
                    >
                      <feat.icon size={28} />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-2xl font-semibold mb-3 text-white">
                        {feat.title}
                      </h3>
                      <p className="text-white/50 leading-relaxed font-light">
                        {feat.desc}
                      </p>
                      {feat.extra}
                    </div>
                  </div>
                </div>
              </MagneticHover>
            </div>
          ))}
        </div>
      </section>

      <div className="section-divider my-20" />

      {/* ═══ HOW IT WORKS ═══ */}
      <section
        id="how-it-works"
        className="relative px-6 py-20 max-w-6xl mx-auto grain-overlay"
      >
        <h2 className="text-4xl md:text-5xl font-bold text-center mb-4 tracking-tight relative z-10">
          How It Works
        </h2>
        <p className="text-white/40 text-center mb-16 font-light relative z-10">
          Three steps to instant intelligence
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative z-10">
          {/* Connecting line */}
          <div className="hidden md:block absolute top-1/2 left-[15%] right-[15%] h-px bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-y-1/2" />

          {[
            {
              num: "01",
              icon: Upload,
              title: "Upload Documents",
              desc: "Drag and drop financial PDFs — annual reports, 10-Ks, earnings calls. Multiple files at once.",
            },
            {
              num: "02",
              icon: Zap,
              title: "AI Indexes Everything",
              desc: "Text, tables, and structure extracted. Hierarchical tree index built with summaries.",
            },
            {
              num: "03",
              icon: MessageSquare,
              title: "Ask & Get Cited Answers",
              desc: "Ask across all documents. Precise, page-cited responses with confidence scores.",
            },
          ].map((step, i) => (
            <MagneticHover key={i} depth={20}>
              <div className="hiw-step glass-panel p-8 rounded-[2rem] text-center hover:bg-white/5 transition-colors group relative overflow-hidden">
                <span className="absolute top-6 right-6 text-5xl font-bold text-white/[0.03] tracking-tighter">
                  {step.num}
                </span>
                <div className="w-16 h-16 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-8 group-hover:scale-110 group-hover:bg-accent/10 transition-all duration-500">
                  <step.icon
                    size={24}
                    className="text-white/50 group-hover:text-accent transition-colors"
                  />
                </div>
                <h3 className="text-xl font-semibold mb-3 text-white">
                  {step.title}
                </h3>
                <p className="text-white/40 text-sm font-light leading-relaxed">
                  {step.desc}
                </p>
              </div>
            </MagneticHover>
          ))}
        </div>
      </section>

      <div className="section-divider my-20" />

      {/* ═══ SECURITY — LIQUID GLASS ═══ */}
      <section id="security" className="relative px-6 py-20 max-w-6xl mx-auto">
        <h2 className="text-4xl md:text-5xl font-bold text-center mb-4 tracking-tight">
          Security
        </h2>
        <p className="text-white/40 text-center mb-16 font-light">
          Your data. Your control.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {securityItems.map((item, i) => (
            <MagneticHover key={i} depth={25}>
              <div className="security-card liquid-glass p-8 rounded-[2rem] text-center group hover:border-accent/30 transition-all duration-500 h-full">
                <div className="w-16 h-16 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-8 group-hover:scale-110 group-hover:bg-accent/10 transition-all duration-500">
                  <item.icon
                    size={24}
                    className="text-white/50 group-hover:text-accent transition-colors"
                  />
                </div>
                <h3 className="text-xl font-semibold mb-3 text-white">
                  {item.title}
                </h3>
                <p className="text-white/40 text-sm font-light leading-relaxed">
                  {item.desc}
                </p>
              </div>
            </MagneticHover>
          ))}
        </div>
      </section>

      <div className="section-divider my-20" />

      {/* ═══ LIMITATIONS ═══ */}
      <section
        id="limitations"
        className="relative px-6 py-20 max-w-5xl mx-auto"
      >
        <h2 className="text-4xl md:text-5xl font-bold text-center mb-4 tracking-tight">
          Current Limitations
        </h2>
        <p className="text-white/40 text-center mb-16 font-light max-w-lg mx-auto">
          We believe in transparency. Here is what FinSight cannot do yet.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {limitations.map((lim, i) => (
            <div
              key={i}
              className="limit-card glass-panel p-6 rounded-2xl border border-white/5 hover:border-destructive/20 transition-colors group"
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-destructive/10 border border-destructive/20 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                  <lim.icon size={18} className="text-destructive" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white mb-1">
                    {lim.title}
                  </h4>
                  <p className="text-white/35 text-xs font-light leading-relaxed">
                    {lim.desc}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="section-divider my-20" />

      {/* ═══ CTA ═══ */}
      <section
        id="cta"
        className="relative px-6 py-32 text-center grain-overlay"
      >
        <div className="relative z-10 max-w-3xl mx-auto">
          <h2 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight">
            Ready to transform your
            <br />
            document analysis?
          </h2>
          <p className="text-white/40 mb-12 text-lg font-light">
            Try FinSight — upload a financial document and get instant, cited
            answers.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <MagneticHover depth={30}>
              <Link
                href="/chat"
                className="inline-flex items-center gap-3 bg-white text-black px-8 py-4 rounded-full font-bold uppercase tracking-wider hover:bg-accent hover:text-white transition-all duration-300 text-sm"
              >
                Try the Demo <ArrowRight size={18} />
              </Link>
            </MagneticHover>
            <MagneticHover depth={30}>
              <Link
                href="/chat"
                className="inline-flex items-center gap-3 border border-white/20 text-white px-8 py-4 rounded-full font-bold uppercase tracking-wider hover:bg-white/10 transition-all duration-300 text-sm"
              >
                <Upload size={16} /> Upload a Document
              </Link>
            </MagneticHover>
          </div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="border-t border-white/5 px-6 py-16">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-start gap-10">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <Bot size={20} className="text-accent" />
              <span className="font-bold text-lg tracking-widest uppercase">
                FinSight
              </span>
            </div>
            <p className="text-white/30 text-sm font-light">
              &copy; FinSight AI Inc. 2026
            </p>
          </div>

          <div className="flex gap-16">
            <div className="flex flex-col gap-3">
              <a
                href="#features"
                className="text-white/40 text-sm hover:text-white transition-colors"
              >
                Features
              </a>
              <a
                href="#how-it-works"
                className="text-white/40 text-sm hover:text-white transition-colors"
              >
                How It Works
              </a>
              <a
                href="#security"
                className="text-white/40 text-sm hover:text-white transition-colors"
              >
                Security
              </a>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <a
              href="#"
              aria-label="Email Address"
              title="Email Address"
              className="w-10 h-10 rounded-full border border-white/10 flex items-center justify-center text-white/40 hover:text-white hover:border-white/30 transition-all"
            >
              <Mail size={16} />
            </a>
            <a
              href="#"
              aria-label="GitHub Profile"
              title="GitHub Profile"
              className="w-10 h-10 rounded-full border border-white/10 flex items-center justify-center text-white/40 hover:text-white hover:border-white/30 transition-all"
            >
              <Github size={16} />
            </a>
            <a
              href="#"
              aria-label="LinkedIn Profile"
              title="LinkedIn Profile"
              className="w-10 h-10 rounded-full border border-white/10 flex items-center justify-center text-white/40 hover:text-white hover:border-white/30 transition-all"
            >
              <Linkedin size={16} />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
