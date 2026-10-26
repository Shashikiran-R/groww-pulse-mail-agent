# Problem Statement — Groww App Review Pulse

## 🎯 Goal

Turn **raw mobile-store feedback** for the Groww platform ([Google Play](https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN) & [App Store](https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703)) into a **weekly pulse** your team can scan in minutes — covering what users care about, what they actually said, and what to do next.

Reviews are already public; the system must **aggregate, theme, summarize, and deliver** that insight through familiar surfaces:

| Surface        | Purpose                                          |
| -------------- | ------------------------------------------------ |
| **Google Docs** | Written weekly pulse for stakeholders            |
| **Gmail**       | Draft email you can send yourself (or an alias)  |

> [!IMPORTANT]
> No manual credential handling or raw REST wiring — the agent handles integration end-to-end.

---

## 🔄 End-to-End Flow (What "Done" Looks Like)

1. **Pull** recent App Store and Play Store reviews for Groww (within the rules below).
2. **Cluster** them into a small set of themes and distil a one-page weekly note.
3. **Publish** that note where stakeholders can read it (Google Docs).
4. **Draft** an email to yourself (or an alias) that contains or links to the pulse (Gmail).

---

## 📦 Deliverables

### Weekly One-Page Pulse Must Include

| Section              | Details                                                        |
| -------------------- | -------------------------------------------------------------- |
| **Top Themes**       | What people are talking about most                             |
| **Real User Quotes** | Verbatim snippets from reviews — no invented wording           |
| **3 Action Ideas**   | Concrete next steps grounded in the themes                     |

**Finally:** send yourself a draft email containing this weekly note (or a clear pointer to it).

---

## 👥 Who This Helps

| Audience              | Why                                                              |
| --------------------- | ---------------------------------------------------------------- |
| **Product / Growth**  | Prioritise fixes and improvements from real signals              |
| **Support**           | Align messaging with what users are actually saying              |
| **Leadership**        | One-page health check without drowning in raw reviews            |

---

## 🛠️ What You Must Build

1. **Import reviews** from roughly the last **8–12 weeks** (fields such as rating, title, text, date — whatever the export provides).
2. **Group reviews** into at most **5 themes** (examples: onboarding, KYC, payments, statements, withdrawals — pick what fits the product).
3. **Generate a weekly one-page note** with:
   - Top **3 themes** (subset of the themes as appropriate)
   - **3 user quotes** (verbatim)
   - **3 action ideas**
4. **Draft an email** with the note to yourself or an alias.

---

## 🔗 Reference

- **Target App (Google Play):** [Groww — Stocks, Mutual Fund, IPO](https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN)
- **Target App (App Store):** [Groww — Stocks, Mutual Fund, IPO](https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703)
