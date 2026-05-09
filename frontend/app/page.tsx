"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowRight,
  Shield,
  Zap,
  Languages,
  FileSearch,
  CheckCircle2,
  Brain,
  Globe,
  Lock,
  Sparkles,
  FileText,
  Users
} from "lucide-react"

const heroSlides = [
  {
    headline: "Translate pharmaceutical documents",
    emphasis: "with confidence",
    description: "AI-powered translation with built-in quality assurance for PIL, SPC, labels, and regulatory documents."
  },
  {
    headline: "Quality checks that",
    emphasis: "catch critical errors",
    description: "Automatic detection of negation flips, unit conversions, and terminology inconsistencies."
  },
  {
    headline: "From source to delivery",
    emphasis: "in minutes, not days",
    description: "Streamlined workflows reduce turnaround time while maintaining pharmaceutical-grade accuracy."
  }
]

export default function LandingPage() {
  const router = useRouter()
  const [currentSlide, setCurrentSlide] = useState(0)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    setIsVisible(true)
    const interval = setInterval(() => {
      setCurrentSlide(prev => (prev + 1) % heroSlides.length)
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  const features = [
    {
      icon: <Brain size={24} />,
      title: "AI-Powered Translation",
      description: "Advanced language models fine-tuned for pharmaceutical terminology ensure accurate, context-aware translations."
    },
    {
      icon: <Shield size={24} />,
      title: "Quality Assurance Built-In",
      description: "Automatic detection of critical errors like negation flips, unit conversions, and terminology inconsistencies."
    },
    {
      icon: <Globe size={24} />,
      title: "Multi-Language Support",
      description: "Translate to multiple languages simultaneously while maintaining consistency across all target markets."
    },
    {
      icon: <FileSearch size={24} />,
      title: "Side-by-Side Review",
      description: "Compare source and target segments with color-coded quality indicators for efficient review workflows."
    },
    {
      icon: <Zap size={24} />,
      title: "Rapid Turnaround",
      description: "Process documents in minutes, not days. Automated workflows reduce time while maintaining quality."
    },
    {
      icon: <Lock size={24} />,
      title: "Enterprise Security",
      description: "Your data stays private. On-premise deployment options and SOC 2 compliant cloud infrastructure."
    }
  ]

  const howItWorks = [
    {
      step: "1",
      title: "Upload Your Document",
      description: "Support for PDF, Word, and XLIFF formats. Documents are automatically segmented for translation."
    },
    {
      step: "2",
      title: "Configure Translation",
      description: "Select target languages, domain (pharmaceutical, medical devices), and any specific terminology requirements."
    },
    {
      step: "3",
      title: "AI Translation & QA",
      description: "TransMax Agent translates each segment with built-in quality checks for accuracy and regulatory compliance."
    },
    {
      step: "4",
      title: "Review & Approve",
      description: "Review translations in a side-by-side editor. Issues are highlighted for quick resolution."
    },
    {
      step: "5",
      title: "Export Deliverables",
      description: "Download translated documents in your preferred format, ready for regulatory submission or publication."
    }
  ]

  return (
    <div className="landing-page">
      {/* Header */}
      <header className="landing-header">
        <div className="landing-header-content">
          <div className="landing-logo">
            <div className="landing-logo-icon">
              <Sparkles size={20} />
            </div>
            <span>TransMax</span>
          </div>
          <nav className="landing-nav">
            <a href="#features">Features</a>
            <a href="#how-it-works">How It Works</a>
            <a href="#about">About</a>
          </nav>
          <Link href="/workspace" className="header-cta">
            Try TransMax <ArrowRight size={16} />
          </Link>
        </div>
      </header>

      {/* Hero Section with Slides */}
      <section className="hero-section">
        <motion.div
          className="hero-content"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : 30 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          {/* Slide Indicators */}
          <div className="slide-indicators">
            {heroSlides.map((_, index) => (
              <button
                key={index}
                className={`slide-indicator ${index === currentSlide ? 'active' : ''}`}
                onClick={() => setCurrentSlide(index)}
              />
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={currentSlide}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.4 }}
              className="hero-slide"
            >
              <h1 className="hero-title">
                {heroSlides[currentSlide].headline}{" "}
                <span className="hero-emphasis">{heroSlides[currentSlide].emphasis}</span>
              </h1>

              <p className="hero-subtitle">
                {heroSlides[currentSlide].description}
              </p>
            </motion.div>
          </AnimatePresence>

          <div className="hero-actions">
            <Link href="/workspace" className="btn-hero-primary">
              <Sparkles size={18} />
              Get Started
            </Link>
            <a href="#how-it-works" className="btn-hero-secondary">
              Learn More
            </a>
          </div>

          <div className="hero-trust">
            <div className="trust-item">
              <CheckCircle2 size={16} />
              <span>FDA/EMA compliant</span>
            </div>
            <div className="trust-item">
              <CheckCircle2 size={16} />
              <span>ICH E6(R2) terminology</span>
            </div>
            <div className="trust-item">
              <CheckCircle2 size={16} />
              <span>Audit trail</span>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Features Section */}
      <section id="features" className="features-section">
        <div className="section-header">
          <h2>What TransMax provides</h2>
          <p>Built specifically for life sciences translation with quality and compliance in mind.</p>
        </div>

        <div className="features-grid">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              className="feature-card"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              viewport={{ once: true }}
            >
              <div className="feature-icon">{feature.icon}</div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="how-it-works-section">
        <div className="section-header">
          <h2>How it works</h2>
          <p>A streamlined workflow from document upload to delivery.</p>
        </div>

        <div className="steps-container">
          {howItWorks.map((item, index) => (
            <motion.div
              key={index}
              className="step-item"
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.15 }}
              viewport={{ once: true }}
            >
              <div className="step-number">{item.step}</div>
              <div className="step-content">
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <div className="cta-content">
          <h2>Ready to streamline your translation workflow?</h2>
          <p>Start with a document and see the quality difference.</p>
          <Link href="/workspace" className="btn-cta">
            <Sparkles size={18} />
            Open Workspace
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="landing-logo">
              <div className="landing-logo-icon">
                <Sparkles size={20} />
              </div>
              <span>TransMax</span>
            </div>
            <p>AI-powered pharmaceutical translation with built-in quality assurance.</p>
          </div>
          <div className="footer-links">
            <div className="footer-column">
              <h4>Product</h4>
              <a href="#features">Features</a>
              <a href="#how-it-works">How It Works</a>
              <Link href="/workspace">Workspace</Link>
            </div>
            <div className="footer-column">
              <h4>Resources</h4>
              <a href="#">Documentation</a>
              <a href="#">API Reference</a>
              <a href="#">Support</a>
            </div>
            <div className="footer-column">
              <h4>Company</h4>
              <a href="#about">About</a>
              <a href="#">Contact</a>
              <a href="#">Privacy</a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p>© 2026 TransMax. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
