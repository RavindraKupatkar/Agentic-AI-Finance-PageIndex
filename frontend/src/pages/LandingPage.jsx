import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView } from 'framer-motion';
import {
    ArrowRight, Bot, Sparkles, Search, ShieldAlert, BarChart3, GitCompare,
    Lock, Eye, ShieldCheck, Target, Files, ShieldHalf,
    Mail, Github, Linkedin, Check, ChevronRight, MessageSquare, FileText,
    Clock, FileSearch, Shield, Zap,
} from 'lucide-react';
import '../styles/landing.css';

/* ─── Animated counter ─── */
function useCounter(end, duration = 2000) {
    const [count, setCount] = useState(0);
    const ref = useRef(null);
    const inView = useInView(ref, { once: true, margin: '-80px' });
    useEffect(() => {
        if (!inView) return;
        let start = 0;
        const step = end / (duration / 16);
        const timer = setInterval(() => {
            start += step;
            if (start >= end) { setCount(end); clearInterval(timer); }
            else setCount(Math.floor(start));
        }, 16);
        return () => clearInterval(timer);
    }, [inView, end, duration]);
    return [ref, count];
}

/* ─── Animation variants ─── */
const fadeUp = {
    hidden: { opacity: 0, y: 30 },
    visible: (d = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, delay: d, ease: [0.22, 1, 0.36, 1] } }),
};
const scaleIn = {
    hidden: { opacity: 0, scale: 0.92 },
    visible: (d = 0) => ({ opacity: 1, scale: 1, transition: { duration: 0.6, delay: d, ease: [0.22, 1, 0.36, 1] } }),
};
const stagger = { visible: { transition: { staggerChildren: 0.1 } } };

export default function LandingPage() {
    const [statRef, count1] = useCounter(99, 1500);

    return (
        <div className="lp">

            {/* ═══ NAV ═══ */}
            <motion.nav className="lp-nav" initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
                <Link to="/" className="lp-nav-logo">
                    <img src="/logo.png" alt="FinSight" width={26} height={26} style={{ borderRadius: '50%' }} />
                    <span>FinSight</span>
                </Link>
                <div className="lp-nav-center">
                    <a href="#features">Features</a>
                    <a href="#how">How It Works</a>
                    <a href="#security">Security</a>
                </div>
                <Link to="/chat" className="lp-nav-cta">Get Started <ArrowRight size={14} /></Link>
            </motion.nav>

            {/* ═══ HERO ═══ */}
            <section className="lp-hero">
                {/* 3D Orbs */}
                <div className="lp-orb lp-orb-1" />
                <div className="lp-orb lp-orb-2" />
                <div className="lp-orb lp-orb-3" />
                {/* Smaller accent orbs */}
                <div className="lp-orb-sm lp-orb-sm-1" />
                <div className="lp-orb-sm lp-orb-sm-2" />
                <div className="lp-orb-sm lp-orb-sm-3" />

                <div className="lp-hero-content">
                    <motion.h1 variants={fadeUp} initial="hidden" animate="visible" custom={0.2}>
                        From annual reports<br />
                        to <span className="lp-glow-text">instant</span> answers.
                    </motion.h1>

                    <motion.p className="lp-hero-sub" variants={fadeUp} initial="hidden" animate="visible" custom={0.4}>
                        Unlocking financial intelligence from unstructured documents with
                        unprecedented speed and accuracy. Powered by advanced AI.
                    </motion.p>

                    {/* ─── Stat Pills (matching mockup) ─── */}
                    <motion.div className="lp-stat-row" variants={fadeUp} initial="hidden" animate="visible" custom={0.6}>
                        <div className="lp-stat-pill" ref={statRef}>
                            <div className="lp-stat-pill-icon lp-stat-pill-icon-violet"><Check size={18} strokeWidth={3} /></div>
                            <div className="lp-stat-pill-body">
                                <span className="lp-stat-pill-val">{count1}.2%</span>
                                <span className="lp-stat-pill-label">Citation Accuracy</span>
                            </div>
                        </div>
                        <div className="lp-stat-pill">
                            <div className="lp-stat-pill-icon lp-stat-pill-icon-cyan"><Files size={16} /></div>
                            <div className="lp-stat-pill-body">
                                <span className="lp-stat-pill-val">Multi-PDF Analysis</span>
                                <span className="lp-stat-pill-label">Simultaneous processing of complex financial documents</span>
                            </div>
                        </div>
                        <div className="lp-stat-pill">
                            <div className="lp-stat-pill-icon lp-stat-pill-icon-emerald"><ShieldHalf size={16} /></div>
                            <div className="lp-stat-pill-body">
                                <span className="lp-stat-pill-val">Enterprise Security</span>
                                <span className="lp-stat-pill-label">End-to-end encryption and data privacy compliance</span>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* ═══ FEATURES (2×2 Grid with Dashboard Previews) ═══ */}
            <section className="lp-section" id="features">
                <div className="lp-container">
                    <motion.div className="lp-feature-grid" variants={stagger} initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-60px' }}>

                        {/* Card 1 — Semantic Search */}
                        <motion.div className="lp-fcard" variants={scaleIn} custom={0.1}>
                            <div className="lp-fcard-glow" />
                            <div className="lp-fcard-inner">
                                <div className="lp-fcard-text">
                                    <div className="lp-fcard-icon" style={{ '--fc': '#7C5CFC' }}><Search size={18} /></div>
                                    <h3>Semantic Search Engine</h3>
                                    <p>Find answers across thousands of pages using natural language queries. Understand context, not just keywords.</p>
                                </div>
                                <div className="lp-fcard-preview">
                                    <div className="lp-preview-mock">
                                        <div className="lp-pm-bar"><span /><span /><span /></div>
                                        <div className="lp-pm-body">
                                            <div className="lp-pm-sidebar">
                                                <div className="lp-pm-line w60" /><div className="lp-pm-line w40" /><div className="lp-pm-line w80" /><div className="lp-pm-line w50" />
                                            </div>
                                            <div className="lp-pm-main">
                                                <div className="lp-pm-chart">
                                                    <div className="lp-pm-bar-v" style={{ height: '60%', '--bc': '#7C5CFC' }} />
                                                    <div className="lp-pm-bar-v" style={{ height: '80%', '--bc': '#5B3FD9' }} />
                                                    <div className="lp-pm-bar-v" style={{ height: '45%', '--bc': '#7C5CFC' }} />
                                                    <div className="lp-pm-bar-v" style={{ height: '90%', '--bc': '#5B3FD9' }} />
                                                    <div className="lp-pm-bar-v" style={{ height: '55%', '--bc': '#7C5CFC' }} />
                                                    <div className="lp-pm-bar-v" style={{ height: '70%', '--bc': '#5B3FD9' }} />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>

                        {/* Card 2 — Compliance */}
                        <motion.div className="lp-fcard" variants={scaleIn} custom={0.2}>
                            <div className="lp-fcard-glow" />
                            <div className="lp-fcard-inner">
                                <div className="lp-fcard-text">
                                    <div className="lp-fcard-icon" style={{ '--fc': '#00D4FF' }}><ShieldAlert size={18} /></div>
                                    <h3>Compliance & Risk Detection</h3>
                                    <p>Proactively identify regulatory risks and non-compliance issues in real-time across all documents.</p>
                                </div>
                                <div className="lp-fcard-preview">
                                    <div className="lp-preview-mock">
                                        <div className="lp-pm-bar"><span /><span /><span /></div>
                                        <div className="lp-pm-body">
                                            <div className="lp-pm-main lp-pm-full">
                                                <div className="lp-pm-rows">
                                                    <div className="lp-pm-row"><div className="lp-pm-dot green" /><div className="lp-pm-line w60" /><div className="lp-pm-badge green">Pass</div></div>
                                                    <div className="lp-pm-row"><div className="lp-pm-dot red" /><div className="lp-pm-line w80" /><div className="lp-pm-badge red">Flag</div></div>
                                                    <div className="lp-pm-row"><div className="lp-pm-dot green" /><div className="lp-pm-line w50" /><div className="lp-pm-badge green">Pass</div></div>
                                                    <div className="lp-pm-row"><div className="lp-pm-dot yellow" /><div className="lp-pm-line w70" /><div className="lp-pm-badge yellow">Warn</div></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>

                        {/* Card 3 — Financial Modeling */}
                        <motion.div className="lp-fcard" variants={scaleIn} custom={0.3}>
                            <div className="lp-fcard-glow" />
                            <div className="lp-fcard-inner">
                                <div className="lp-fcard-text">
                                    <div className="lp-fcard-icon" style={{ '--fc': '#F59E0B' }}><BarChart3 size={18} /></div>
                                    <h3>Automated Financial Modeling</h3>
                                    <p>Extract data points and build dynamic models instantly. Reduce manual entry by 90%.</p>
                                </div>
                                <div className="lp-fcard-preview">
                                    <div className="lp-preview-mock">
                                        <div className="lp-pm-bar"><span /><span /><span /></div>
                                        <div className="lp-pm-body">
                                            <div className="lp-pm-main lp-pm-full">
                                                <div className="lp-pm-table">
                                                    <div className="lp-pm-trow lp-pm-thead"><span>Metric</span><span>Q1</span><span>Q2</span><span>Q3</span></div>
                                                    <div className="lp-pm-trow"><span>Revenue</span><span>2.1B</span><span>2.4B</span><span>2.8B</span></div>
                                                    <div className="lp-pm-trow"><span>EBITDA</span><span>420M</span><span>510M</span><span>580M</span></div>
                                                    <div className="lp-pm-trow"><span>Net Inc.</span><span>180M</span><span>210M</span><span>260M</span></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>

                        {/* Card 4 — Comparison */}
                        <motion.div className="lp-fcard" variants={scaleIn} custom={0.4}>
                            <div className="lp-fcard-glow" />
                            <div className="lp-fcard-inner">
                                <div className="lp-fcard-text">
                                    <div className="lp-fcard-icon" style={{ '--fc': '#EC4899' }}><GitCompare size={18} /></div>
                                    <h3>Comparison & Trend Analysis</h3>
                                    <p>Instantly compare key metrics across different periods and documents to uncover trends.</p>
                                </div>
                                <div className="lp-fcard-preview">
                                    <div className="lp-preview-mock">
                                        <div className="lp-pm-bar"><span /><span /><span /></div>
                                        <div className="lp-pm-body">
                                            <div className="lp-pm-main lp-pm-full">
                                                <div className="lp-pm-sparklines">
                                                    <svg viewBox="0 0 120 40" className="lp-sparkline lp-sparkline-1">
                                                        <polyline points="0,35 20,28 40,30 60,18 80,12 100,8 120,5" />
                                                    </svg>
                                                    <svg viewBox="0 0 120 40" className="lp-sparkline lp-sparkline-2">
                                                        <polyline points="0,30 20,32 40,25 60,28 80,20 100,15 120,10" />
                                                    </svg>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </motion.div>
                </div>
            </section>

            {/* ═══ HOW IT WORKS ═══ */}
            <section className="lp-section lp-section-alt" id="how">
                <div className="lp-container">
                    <motion.div className="lp-tag" variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>How It Works</motion.div>
                    <motion.h2 className="lp-title" variants={fadeUp} initial="hidden" whileInView="visible" custom={0.1} viewport={{ once: true }}>
                        Three steps to <span className="lp-glow-text">instant intelligence</span>
                    </motion.h2>

                    <div className="lp-steps">
                        {[
                            { n: '01', title: 'Upload Documents', desc: 'Drag and drop financial PDFs — annual reports, 10-Ks, earnings calls. Multiple files at once.', icon: Files },
                            { n: '02', title: 'AI Indexes Everything', desc: 'Text, tables, and structure extracted. Hierarchical tree index built with summaries.', icon: Zap },
                            { n: '03', title: 'Ask & Get Cited Answers', desc: 'Ask across all documents. Precise, page-cited responses with confidence scores.', icon: Target },
                        ].map(({ n, title, desc, icon: Icon }, i) => (
                            <motion.div key={n} className="lp-step" variants={fadeUp} initial="hidden" whileInView="visible" custom={i * 0.12} viewport={{ once: true }}>
                                <div className="lp-step-num">{n}</div>
                                <div className="lp-step-body">
                                    <div className="lp-step-ic"><Icon size={18} /></div>
                                    <h3>{title}</h3>
                                    <p>{desc}</p>
                                </div>
                                {i < 2 && <div className="lp-step-line" />}
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ═══ SECURITY ═══ */}
            <section className="lp-section" id="security">
                <div className="lp-container">
                    <motion.div className="lp-tag" variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>Security</motion.div>
                    <motion.h2 className="lp-title" variants={fadeUp} initial="hidden" whileInView="visible" custom={0.1} viewport={{ once: true }}>
                        Your data. <span className="lp-glow-text">Your control.</span>
                    </motion.h2>

                    <motion.div className="lp-sec-grid" variants={stagger} initial="hidden" whileInView="visible" viewport={{ once: true }}>
                        {[
                            { icon: Lock, title: 'End-to-End Encryption', desc: 'All data encrypted in transit and at rest. Documents never exposed.', color: '#7C5CFC' },
                            { icon: Eye, title: 'Zero Data Sharing', desc: 'Processed privately. Nothing shared, sold, or used for training.', color: '#10B981' },
                            { icon: ShieldCheck, title: 'Full Data Ownership', desc: 'Delete anytime — permanently removed. You\'re always in control.', color: '#00D4FF' },
                        ].map(({ icon: Icon, title, desc, color }, i) => (
                            <motion.div key={title} className="lp-sec-card" variants={scaleIn} custom={i * 0.1}>
                                <div className="lp-sec-icon" style={{ '--sc': color }}><Icon size={20} /></div>
                                <h3>{title}</h3>
                                <p>{desc}</p>
                            </motion.div>
                        ))}
                    </motion.div>
                </div>
            </section>

            {/* ═══ CTA ═══ */}
            <section className="lp-cta">
                <div className="lp-cta-glow" />
                <motion.div className="lp-cta-inner" variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
                    <h2>Ready to transform your <span className="lp-glow-text">document analysis</span>?</h2>
                    <p>Try FinSight — upload a financial document and get instant, cited answers.</p>
                    <div className="lp-cta-btns">
                        <Link to="/chat" className="lp-btn lp-btn-glow">Try the Demo <ArrowRight size={16} /></Link>
                        <Link to="/documents" className="lp-btn lp-btn-ghost">Upload a Document</Link>
                    </div>
                </motion.div>
            </section>

            {/* ═══ FOOTER ═══ */}
            <footer className="lp-footer">
                <div className="lp-footer-inner">
                    <span className="lp-footer-copy">© FinSight AI Inc. 2026</span>
                    <div className="lp-footer-links">
                        <a href="mailto:contact@syncroai.com">Email</a>
                        <a href="https://github.com" target="_blank" rel="noopener noreferrer">GitHub</a>
                        <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer">LinkedIn</a>
                    </div>
                    <div className="lp-footer-links">
                        <a href="#features">Features</a>
                        <a href="#how">How It Works</a>
                        <a href="#security">Security</a>
                    </div>
                </div>
            </footer>
        </div>
    );
}
