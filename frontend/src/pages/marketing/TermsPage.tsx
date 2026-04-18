import { MarketingLayout } from "@/components/landing/MarketingLayout";

export default function TermsPage() {
  return (
    <MarketingLayout>
      <h1 className="font-display font-bold text-4xl md:text-5xl tracking-tight">
        Terms of Service
      </h1>
      <p className="mt-3 text-sm text-slate-500">
        Last updated: 18 April 2026
      </p>

      <div className="mt-10 space-y-8 text-slate-300 leading-relaxed">
        <section>
          <h2 className="text-xl font-semibold text-white">1. Acceptance</h2>
          <p className="mt-2">
            By creating an account or using the PetroLedger service, you agree
            to be bound by these Terms of Service. If you do not agree, do not
            use the service.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">2. The service</h2>
          <p className="mt-2">
            PetroLedger provides a hosted reconciliation, reporting, and
            workforce-management platform for petrol-pump dealers. Available
            features depend on your subscription plan.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">
            3. Accounts and access
          </h2>
          <p className="mt-2">
            You are responsible for maintaining the confidentiality of your
            account credentials and for every action taken under your account.
            Notify us immediately of any unauthorised use.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">4. Subscriptions</h2>
          <p className="mt-2">
            Subscriptions are billed monthly in advance. Plan upgrades take
            effect immediately; downgrades take effect at the end of the
            current billing period. Subscriptions auto-renew unless cancelled.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">5. Acceptable use</h2>
          <p className="mt-2">
            You agree not to (a) reverse-engineer the service; (b) attempt to
            gain unauthorised access to other tenants' data; (c) use the
            service for any unlawful purpose; (d) resell access without our
            written consent.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">6. Data ownership</h2>
          <p className="mt-2">
            You retain ownership of all operational data you submit. We
            process it solely to provide the service and as described in our
            Privacy Policy.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">
            7. Limitation of liability
          </h2>
          <p className="mt-2">
            To the maximum extent permitted by law, PetroLedger's aggregate
            liability for any claim arising out of these Terms is limited to
            the fees paid by you in the twelve months preceding the claim.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">8. Termination</h2>
          <p className="mt-2">
            Either party may terminate the agreement on 30 days' notice. We
            may suspend or terminate immediately for material breach,
            non-payment, or activity that endangers the service.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">9. Governing law</h2>
          <p className="mt-2">
            These Terms are governed by the laws of India. Disputes shall be
            subject to the exclusive jurisdiction of the courts of Bengaluru,
            Karnataka.
          </p>
        </section>
        <section>
          <h2 className="text-xl font-semibold text-white">10. Contact</h2>
          <p className="mt-2">
            Questions about these terms can be sent to{" "}
            <a
              className="text-amber-400 hover:text-amber-300"
              href="mailto:official.concilio@gmail.com"
            >
              official.concilio@gmail.com
            </a>
            .
          </p>
        </section>
      </div>
    </MarketingLayout>
  );
}
