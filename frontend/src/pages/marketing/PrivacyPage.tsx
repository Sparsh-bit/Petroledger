import { MarketingLayout } from "@/components/landing/MarketingLayout";

export default function PrivacyPage() {
  return (
    <MarketingLayout>
      <h1 className="font-display font-bold text-4xl md:text-5xl tracking-tight">
        Privacy Policy
      </h1>
      <p className="mt-3 text-sm text-slate-500">
        Last updated: 18 April 2026
      </p>
      <p className="mt-2 text-sm text-slate-400">
        Data controller: Concilio Solutions —{" "}
        <a className="text-amber-400 hover:text-amber-300" href="mailto:official.concilio@gmail.com">
          official.concilio@gmail.com
        </a>{" "}
        ·{" "}
        <a className="text-amber-400 hover:text-amber-300" href="tel:+918840268280">
          +91 88402 68280
        </a>{" "}
        ·{" "}
        <a
          className="text-amber-400 hover:text-amber-300"
          href="https://concilio.solutions"
          target="_blank"
          rel="noopener noreferrer"
        >
          concilio.solutions
        </a>
      </p>

      <div className="mt-10 space-y-8 text-slate-300 leading-relaxed">
        <section>
          <h2 className="text-xl font-semibold text-white">1. Introduction</h2>
          <p className="mt-2">
            This Privacy Policy explains how PetroLedger ("we", "us") collects,
            uses, and safeguards information when you use our software-as-a-
            service offering at petroledger.in (the "Service").
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">
            2. Information we collect
          </h2>
          <p className="mt-2">
            We collect (a) account information you provide directly — name,
            email, phone, business details; (b) operational data you upload —
            meter readings, fleet-card statements, POS settlements, cash
            entries; (c) device and usage telemetry — IP address, browser
            user-agent, timestamps of activity.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">
            3. How we use your information
          </h2>
          <p className="mt-2">
            We use information to operate the Service, reconcile your daily
            books, surface anomalies, send transactional notifications, and
            improve product quality. We do not sell personal information.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">4. Cookies</h2>
          <p className="mt-2">
            We use first-party cookies strictly for authentication session
            management. We do not use third-party advertising cookies.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">5. Data retention</h2>
          <p className="mt-2">
            Operational records are retained for the lifetime of your active
            subscription plus seven years to satisfy Indian tax and audit
            requirements. Account closure requests are honoured within 30 days
            of receipt.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">6. Security</h2>
          <p className="mt-2">
            All data is encrypted in transit (TLS 1.2+) and at rest. Access is
            scoped per tenant and per role. We retain audit logs of all
            privileged operations.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">7. Your rights</h2>
          <p className="mt-2">
            You may request access, correction, or deletion of your personal
            information at any time by writing to{" "}
            <a
              className="text-amber-400 hover:text-amber-300"
              href="mailto:official.concilio@gmail.com"
            >
              official.concilio@gmail.com
            </a>
            .
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">8. Contact</h2>
          <p className="mt-2">
            Questions about this policy can be directed to the email above or
            via our <a className="text-amber-400" href="/contact">contact form</a>.
          </p>
        </section>
      </div>
    </MarketingLayout>
  );
}
