import { MarketingLayout } from "@/components/landing/MarketingLayout";

export default function AboutPage() {
  return (
    <MarketingLayout>
      <h1 className="font-display font-bold text-4xl md:text-5xl tracking-tight">
        About PetroLedger
      </h1>
      <p className="mt-6 text-lg text-slate-300 leading-relaxed">
        PetroLedger is built for Indian petrol-pump dealers who want to run
        their forecourt with the same discipline as a modern retail business.
      </p>
      <div className="prose prose-invert mt-10 max-w-none text-slate-300 leading-relaxed space-y-6">
        <section>
          <h2 className="text-2xl font-semibold text-white">Our story</h2>
          <p>
            We started PetroLedger after watching family-run pumps lose
            thousands of rupees every month to silent shrinkage, fleet-card
            disputes, and end-of-day cash mismatches that nobody had time to
            chase down. Spreadsheets, paper logbooks, and WhatsApp groups can
            only carry an operation so far.
          </p>
        </section>
        <section>
          <h2 className="text-2xl font-semibold text-white">What we do</h2>
          <p>
            We take meter readings, fleet-card statements, POS settlements, and
            physical cash declarations, and reconcile them automatically into a
            single trustworthy daily ledger. Variances and anomalies surface on
            the owner's dashboard before they become problems.
          </p>
        </section>
        <section>
          <h2 className="text-2xl font-semibold text-white">Where we are</h2>
          <p>
            Built and operated from India. We support BPCL, HPCL, IOCL, Reliance
            and Nayara dealer networks, with deeper FMS integrations rolling
            out across 2026.
          </p>
        </section>
        <section>
          <h2 className="text-2xl font-semibold text-white">Get in touch</h2>
          <p>
            PetroLedger is built by Concilio Solutions. Reach us at{" "}
            <a
              className="text-amber-400 hover:text-amber-300"
              href="mailto:official.concilio@gmail.com"
            >
              official.concilio@gmail.com
            </a>
            ,{" "}
            <a
              className="text-amber-400 hover:text-amber-300"
              href="tel:+918840268280"
            >
              +91 88402 68280
            </a>
            , or visit{" "}
            <a
              className="text-amber-400 hover:text-amber-300"
              href="https://concilio.solutions"
              target="_blank"
              rel="noopener noreferrer"
            >
              concilio.solutions
            </a>
            .
          </p>
        </section>
      </div>
    </MarketingLayout>
  );
}
