import Link from "next/link";
import { buttonVariants } from "@/components/ui";
import { LandingNav } from "@/components/layout/landing-nav";
import { APP_NAME, APP_DESCRIPTION, ROUTES, BACKEND_URL } from "@/lib/constants";
import { cn } from "@/lib/utils";
import {
  Bot,
  Zap,
  Database,
  Shield,
  LayoutDashboard,
  Server,
  ArrowRight,
  ChevronRight,
  ChevronDown,
} from "lucide-react";

const features = [
  {
    icon: Bot,
    title: "AI-Powered Chat",
    desc: "Conversational AI assistant with real-time streaming, conversation history, and tool-calling capabilities.",
    href: ROUTES.CHAT,
  },
  {
    icon: Database,
    title: "Knowledge Base",
    desc: "Vector search across your documents with retrieval-augmented generation. Ingest PDFs, DOCX, and more.",
    href: ROUTES.RAG,
  },
  {
    icon: Shield,
    title: "Secure Authentication",
    desc: "JWT-based auth with refresh tokens, OAuth integration, session management, and role-based access control.",
  },
  {
    icon: LayoutDashboard,
    title: "Dashboard",
    desc: "System health monitoring, user management, and collection statistics at a glance.",
    href: ROUTES.DASHBOARD,
  },
  {
    icon: Server,
    title: "REST API",
    desc: "Auto-documented FastAPI backend with OpenAPI specs, versioned endpoints, and async database access.",
  },
  {
    icon: Zap,
    title: "Real-time",
    desc: "WebSocket-powered streaming for instant AI responses and live updates across the application.",
  },
];

const techItems = [
  "Next.js 15", "React 19", "TypeScript", "Tailwind CSS", "FastAPI", "PydanticAI",
  "SQLAlchemy", "PostgreSQL", "Redis", "Taskiq", "Docker", "JWT Auth",
  "WebSockets", "Logfire", "OpenTelemetry", "PyMuPDF", "Pydantic v2",
  "Alembic", "Zustand", "TanStack Query", "Vitest",
];

export default function HomePage() {
  return (
    <div className="bg-background min-h-screen">
      <LandingNav
        signInLabel="Sign In"
        getStartedLabel="Get Started"
        dashboardLabel="Dashboard"
      />

      <main>
        {/* Hero */}
        <section className="relative flex min-h-svh items-center justify-center overflow-hidden px-4 sm:px-6">
          <div className="grid-bg pointer-events-none absolute inset-0" />
          <div className="pointer-events-none absolute inset-0">
            <div className="bg-brand/[0.12] absolute top-[5%] left-1/2 h-[400px] w-[500px] -translate-x-1/2 rounded-full blur-[120px] sm:h-[600px] sm:w-[800px] sm:blur-[200px]" />
            <div className="bg-brand-muted/[0.08] absolute top-[15%] left-[30%] h-[300px] w-[350px] -translate-x-1/2 rounded-full blur-[100px] sm:h-[400px] sm:w-[500px] sm:blur-[160px]" />
          </div>
          <div className="from-background pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t to-transparent" />

          <div className="relative mx-auto max-w-4xl text-center">
            <div className="border-brand/20 bg-brand/[0.06] text-muted-foreground mb-8 inline-flex items-center rounded-full border px-4 py-1.5 text-sm">
              <span className="bg-brand mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full" />
              {APP_DESCRIPTION}
            </div>

            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              Build Intelligent{" "}
              <span className="from-brand to-brand-hover bg-gradient-to-r bg-clip-text text-transparent">
                Applications
              </span>
              <br />
              with Confidence
            </h1>

            <p className="text-muted-foreground mx-auto mt-6 max-w-2xl text-lg leading-relaxed">
              A production-ready full-stack platform with AI-powered chat, knowledge base retrieval, secure authentication, and a modern dashboard.
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href={ROUTES.REGISTER}
                className="bg-brand text-brand-foreground hover:bg-brand-hover inline-flex items-center gap-2 rounded-full px-8 py-3 text-base font-semibold transition-all hover:shadow-lg"
              >
                Get Started
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href={ROUTES.LOGIN}
                className="border-border bg-background/50 hover:border-border/80 hover:bg-background/80 inline-flex items-center rounded-full border px-8 py-3 text-base font-semibold backdrop-blur-sm transition-all"
              >
                Sign In
              </Link>
            </div>
          </div>

          <a
            href="#features"
            className="scroll-arrow border-border bg-card text-muted-foreground hover:border-brand hover:text-brand absolute bottom-8 left-1/2 flex h-10 w-10 -translate-x-1/2 items-center justify-center rounded-full border transition-colors"
          >
            <ChevronDown className="h-5 w-5" />
          </a>
        </section>

        {/* Features */}
        <section id="features" className="flex min-h-screen items-center px-4 py-20 sm:px-6 sm:py-28">
          <div className="mx-auto w-full max-w-6xl">
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {features.map((feature) => {
                const Icon = feature.icon;
                return (
                  <div key={feature.title} className="glass-card group rounded-xl p-6">
                    <div className="bg-brand/10 mb-4 flex h-12 w-12 items-center justify-center rounded-lg transition-transform group-hover:scale-110">
                      <Icon className="text-brand h-6 w-6" />
                    </div>
                    <h3 className="mb-2 text-lg font-semibold">{feature.title}</h3>
                    <p className="text-muted-foreground text-sm leading-relaxed">{feature.desc}</p>
                    {feature.href && (
                      <Link
                        href={feature.href}
                        className="text-brand hover:text-brand-hover mt-4 inline-flex items-center gap-1 text-sm font-medium transition-colors"
                      >
                        Learn More
                        <ChevronRight className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Tech Stack Marquee */}
        <section className="border-border/50 overflow-hidden border-t py-16">
          <div className="mx-auto max-w-5xl px-4 text-center sm:px-6">
            <h2 className="text-muted-foreground mb-10 text-xs font-semibold tracking-widest uppercase">
              Built with modern technologies
            </h2>
          </div>
          <div className="marquee-container">
            <div className="marquee-track marquee-left">
              {[...techItems, ...techItems].map((tech, i) => (
                <span
                  key={`${tech}-${i}`}
                  className="border-border/60 bg-card text-foreground/80 inline-flex shrink-0 items-center rounded-lg border px-5 py-2.5 text-sm font-medium"
                >
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="px-4 py-20 sm:px-6">
          <div className="border-border/50 bg-card relative mx-auto max-w-4xl overflow-hidden rounded-2xl border px-4 py-16 text-center sm:px-6">
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="bg-brand/[0.06] h-[300px] w-[500px] rounded-full blur-[100px]" />
            </div>
            <div className="relative">
              <h2 className="mb-4 text-3xl font-bold tracking-tight">Ready to get started?</h2>
              <p className="text-muted-foreground mx-auto mb-8 max-w-lg">Create your account and start exploring the platform.</p>
              <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
                <Link
                  href={ROUTES.REGISTER}
                  className="bg-brand text-brand-foreground hover:bg-brand-hover inline-flex items-center gap-2 rounded-full px-8 py-3 text-base font-semibold transition-all hover:shadow-lg"
                >
                  Create Account
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <a
                  href={`${BACKEND_URL}/docs`}
                  className={cn(
                    buttonVariants({ variant: "outline", size: "lg" }),
                    "rounded-full px-8",
                  )}
                >
                  Explore API
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-border/50 border-t">
        <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <div className="flex flex-col gap-8 sm:flex-row sm:justify-between">
            <div className="max-w-xs">
              <p className="text-lg font-bold tracking-tight">{APP_NAME}</p>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
                Full-stack AI application platform with enterprise-grade features.
              </p>
            </div>
            <div className="flex gap-16">
              <div>
                <h4 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wider uppercase">
                  Product
                </h4>
                <ul className="space-y-2">
                  <li>
                    <Link href={ROUTES.DASHBOARD} className="text-muted-foreground hover:text-foreground text-sm transition-colors">
                      Dashboard
                    </Link>
                  </li>
                  <li>
                    <Link href={ROUTES.CHAT} className="text-muted-foreground hover:text-foreground text-sm transition-colors">
                      Chat
                    </Link>
                  </li>
                  <li>
                    <Link href={ROUTES.RAG} className="text-muted-foreground hover:text-foreground text-sm transition-colors">
                      Knowledge Base
                    </Link>
                  </li>
                </ul>
              </div>
              <div>
                <h4 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wider uppercase">
                  Resources
                </h4>
                <ul className="space-y-2">
                  <li>
                    <a href={`${BACKEND_URL}/docs`} className="text-muted-foreground hover:text-foreground text-sm transition-colors">
                      API Docs
                    </a>
                  </li>
                  <li>
                    <Link href={ROUTES.LOGIN} className="text-muted-foreground hover:text-foreground text-sm transition-colors">
                      Sign In
                    </Link>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
        <div className="border-border/50 border-t">
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
            <p className="text-muted-foreground text-center text-xs">
              &copy; {new Date().getFullYear()} {APP_NAME}. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
