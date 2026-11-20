# Business case and data design

> **Status: approved on 20 November 2026.** `src/generate_data.py` implements
> this document.

Everything here is fictional. The operator, the events and every number are invented. The
proportions are chosen to resemble a South African mobile market; they are not any real
operator's figures.

## The question

**Is the prepaid recovery real?**

The viewer is the Analytics Lead reading the October 2026 month-end pack for the commercial
performance forum. The headline looks healthy: revenue is up on last year, gross additions
are at a record and the base is stable. The pack shows what sits underneath.

## The operator

Kopano Mobile (placeholder name) is a large national operator defending a mostly prepaid
consumer base. The data is a scaled sample that opens with 35,000 SIMs: roughly 85% prepaid
and 15% contract.

## Storyline: one causal chain

1. **Two shocks land together in Gauteng (March 2026).** A competitor launches a voice-heavy
   prepaid bundle across the province. In the same month a severe storm damages a network
   hub serving one high-usage district, and service there is degraded for about two months.
2. **The data separates the two causes.** The competitor effect is province-wide but limited
   to voice-heavy prepaid customers. The network effect is limited to one district but hits
   every segment, contract included, and shows up as a usage drop within days.
3. **Revenue at risk drives operational urgency.** Recharge activity falls immediately, while
   reported churn (a 90-day rule) will not move for three months. Sizing the district's
   revenue at risk early is the case for prioritising the repair. Service is restored in May
   and the district's activity recovers.
4. **Response one: refill the base (April to August 2026).** Commercial raises commissions
   through informal trade. Gross additions hit a record, but many are existing customers on
   new SIMs, or SIMs that never recharge.
5. **Response two: a retention offer (June to August 2026).** At-risk prepaid customers in
   Gauteng get a personalised bundle at 25% below standard price, with a randomised control
   group held out.
6. **Result (October 2026).** Revenue growth comes mostly from the contract price increase.
   Prepaid ARPU is diluted by low-value SIMs, so the recovery is weaker than the headline.

**How the offer ends.** Churn falls against control. Net margin is negative across the whole
test group, because customers who would have paid full price took the cheaper offer. It is
positive in the highest-risk group. The evidence supports retargeting, not extending as is.
The damaged district is held out of the offer so the two effects do not mix.

## Prepaid mechanics the data respects

- **A subscriber is a SIM, not a person.** A device identifier lets the analysis spot the same
  handset reappearing on a new SIM.
- **Churn is a definition.** A prepaid SIM is churned after three consecutive months with no
  recharge. A contract SIM churns when the contract is cancelled.
- **Gross additions can be manufactured.** Commission per activation and starter-pack deals
  inflate gross additions and churn together.
- **ARPU falls through mix alone.** Adding low-spend SIMs lowers ARPU with no change in
  existing customers' behaviour.
- **Usage growth is not revenue growth.** Data volume grows faster than data revenue.
- **Retention offers cannibalise.** The main cost is full-price spend given up, not the
  discount itself.

## Event timeline

| When | Event | What it does in the data |
|------|-------|--------------------------|
| Nov 2024 to Jan 2026 | Baseline | Prepaid revenue drifts down about 1.5% a year; data usage grows about 25% a year |
| Feb 2026 | Contract price increase of 6% | Contract ARPU steps up; no volume change |
| Mar 2026 | Competitor voice bundle, Gauteng | Voice-heavy prepaid SIMs recharge less or stop |
| Mar to Apr 2026 | Storm damage to a hub in one Gauteng district | Network availability falls to about 82%, then 93%; usage and recharges drop for all segments in that district |
| May 2026 | Network restored | District activity recovers to near baseline |
| Apr to Aug 2026 | Informal trade commission push | Gross additions up about 40%; quality rate falls |
| Jun to Aug 2026 | Retention offer, test and control | Lower churn in test; cannibalised revenue in low-risk customers |
| Jun to Aug 2026 | Reported churn peaks | The 90-day rule catches the SIMs that went silent from March |
| Sep to Oct 2026 | "Recovery" | Base stable, revenue up on last year, prepaid ARPU down |

## Target numbers and what the generator produces

Figures in the last column come from the default run (`--seed 20261125`).

| Measure | Normal level | During the events | Generated |
|---------|--------------|-------------------|-----------|
| Prepaid ARPU | About R60 | Lower by Oct 2026 | About R58 before the events, about R54 by Aug 2026 |
| Contract ARPU | About R300 | About 6% higher from Feb 2026 | About R318, then about R338 |
| Prepaid monthly churn | 4% to 5% | 7% to 8% in Gauteng prepaid, Jun to Aug 2026 | About 4.4% normally; 8% to 9% in Gauteng prepaid |
| Prepaid gross additions | About 4.5% of base a month | About 40% higher, Apr to Aug 2026 | About 1,500 a month, then about 2,200 |
| Quality addition rate, informal trade | About 55% | About 35% | About 56%, then about 43%; about 28% once SIM swaps are excluded |
| SIM swaps among informal trade additions | Under 5% | About 25% of the extra additions | About 3% normally; about 15% of all informal additions during the push |
| Damaged district | About 8% of the base | Revenue about 35% down in March, 15% down in April | About 8% of the base; about 30% and 16% down |
| Retention offer | About 4,000 eligible SIMs | Churn about 3 points lower in test; margin slightly negative overall, positive in the highest-risk group | About 2,500 eligible; churn about 2 points lower overall and about 10 points lower in the high-risk group |
| Total revenue, Oct 2026 against Oct 2025 | | About 3% higher, mostly from contract price | About 6% higher: contract about 10%, prepaid about 2% |
| Revenue against budget | | Ahead | 2% to 3% ahead from April 2026 |

The offer's overall margin effect is small compared with random variation between SIMs. The
high-risk result is the robust one. The analysis must show that uncertainty and not overstate
the overall figure.

## Definitions (this project's assumptions)

- **Active base (reporting):** prepaid SIMs with a recharge in the last 90 days, plus contract SIMs not cancelled.
- **Churn:** prepaid SIM with three consecutive months of no recharge; contract cancellation.
- **Quality gross addition:** a new SIM that recharged in at least two of its first three months.
- **SIM swap:** a new activation on a device already seen on another SIM in the prior 90 days.

## Pages

| Page | The viewer can answer |
|------|-----------------------|
| Movement bridge | Why did revenue and ARPU move against last month, last year and budget? How much came from price, volume, mix and migrations? |
| Acquisition quality (on the bridge page) | Are we adding customers who stay? What does a quality addition cost by channel, and how fast does it pay back? |
| Diagnosis and revenue at risk | What caused the Gauteng decline: competitor or network? How much revenue was at risk in the damaged district, and what did restoring it recover? |
| Initiative measurement | Did the offer reduce churn against control? What was the net margin effect by risk group? |
| Controls and lineage | Do reported numbers match billing within tolerance? What broke, how big, and what was fixed? |
| Cohort, scenario and lifetime value | Optional, built only if time allows |

## Investment-experience elements

1. **Attribution as the revenue bridge.** The bridge sums exactly to the total movement.
2. **Acquisition spend as capital allocation.** Payback and return per rand by channel.
3. **Data that triggers an intervention.** Sizing revenue at risk early enough to change an
   operational priority, then measuring what the intervention recovered.
4. **Reconciliation with materiality.** Tolerance thresholds, a break log and an escalation rule.

Lifetime value as a discounted cash flow is optional.
