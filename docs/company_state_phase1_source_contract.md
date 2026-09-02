# Company State Phase 1 — Source Contract Audit

Status: **Audit complete; implementation blocked on provider/cache and sampling-basis decisions.**

Audit date: 2026-09-02. Scope is high-frequency market state only. No
fundamentals, valuation, events, benchmarks, scoring, strategy, or hypothesis
export is authorized here.

## Evidence audited

- Installed/frozen wrapper: AKShare `1.17.87`.
- Primary current adapter: `stock_zh_a_hist`, backed by Eastmoney
  `push2his.eastmoney.com/api/qt/stock/kline/get`, `klt=101`, `fqt=1` for qfq.
- Pinned source file SHA-256:
  `B12EEABFA90DBD2DFA62C62DC777C25F6416FC7047EA3BB57C78BE28C9B9A7E4`.
- Candidate Sina wrapper: `stock_zh_a_daily`; pinned source SHA-256:
  `F8B6C1364AACDA2FC0009EFB3F295F81744ADBAA6345EB021DF337E7F9FEEC6F`.
- AKShare interface documentation:
  `https://akshare.akfamily.xyz/data/stock/stock.html` (retrieved 2026-09-02).
- Existing Observatory cache: immutable CSV keyed by provider/version/ticker/
  date range/qfq, but containing only `date,close` after adapter projection.

Current online AKShare documentation is newer than the pinned wrapper. The
pinned source code governs implementation behavior; current documentation is
supporting evidence for field descriptions and limitations, not proof that the
historical upstream data are revision-free.

## Provider audit conclusion

The same Eastmoney historical endpoint already used by Observatory returns
daily open/high/low/close, volume, trading amount, amplitude, percentage change,
change amount, and turnover rate. Official AKShare documentation states volume
is in **hands (手)**, amount in **CNY**, and turnover in **percent**. A read-only
600031 sample for 2023-01-03 through 2023-01-10 produced identical volume,
amount, and turnover under `adjust=""` and `adjust="qfq"`.

However, Observatory currently discards every field except qfq close before
caching. Those discarded provider fields cannot be reconstructed from the
existing cache. Adding them requires a new versioned raw schema and refetch; it
must not overwrite or reinterpret existing cache files.

The endpoint supplies no row-level publication timestamp, revision timestamp,
or upstream snapshot identifier. Observatory can preserve retrieval time,
request parameters, wrapper version, source-code hash, response hash, and
trading/effective date, but cannot prove what Eastmoney returned at an earlier
retrieval time.

## Field-level source contract

`provider` below means pinned AKShare 1.17.87 over the named upstream endpoint.
All locally derived quarterly metrics must retain input artifact hashes and
formula/version identifiers.

| Variable | Definition | Raw vs derived | Provider / endpoint | Timestamp semantics | Adjustment dependence | Point-in-time validity | Missingness | Units | Transformation | Known limitations / status |
|---|---|---|---|---|---|---|---|---|---|---|
| trading date | Exchange trading date attached to a returned daily row | Provider field | Eastmoney `stock_zh_a_hist` | Effective date = row date; availability assumed after close; retrieval recorded locally | None | Dated observation is historical, but upstream revisions are not timestamped | Missing row is not by itself proof of suspension | date | Parse provider date | No exchange/calendar provenance in current cache |
| qfq close | Provider forward-adjusted close for the row date | Provider-computed field | Existing frozen endpoint, `fqt=1` | Effective date = row date; retrieval time local | Fully adjustment-dependent | Valid for retrospective exploration only; qfq history is revised by later corporate actions and is not a frozen “known then” series | Missing remains missing; no fill | CNY/share-equivalent adjusted price | Numeric parse only | Existing cache has this field; qfq may change on later retrieval |
| unadjusted close | Actual historical close needed for price-level quantities such as market cap/limit checks | Provider field candidate | Same endpoint, `fqt=0` | Same as row date/retrieval | Unadjusted | Historically dated, but would require a separate immutable request/cache identity | Unavailable in current cache | CNY/share | Numeric parse only | Not approved/fetched; second adjustment request would be required |
| volume | Daily traded quantity | Provider field candidate | Same endpoint `成交量` | Effective = trading date; available after close; retrieval local | Empirically invariant to qfq on audited sample | Defensible as a dated provider value, subject to unknown upstream revisions | Missing stays null; absent row not zero | hands (`手`); 1 hand normally 100 shares, but raw unit remains hands | No conversion in raw; optional derived shares = hands × 100 with explicit rule | Not present in current cache; odd-lot/unit edge cases make raw hands canonical |
| trading amount | Daily traded monetary amount | Provider field candidate | Same endpoint `成交额` | Effective = trading date; available after close; retrieval local | Empirically invariant to qfq on audited sample | Defensible as dated provider value, subject to revisions | Missing stays null; absent row not zero | CNY | No transformation | Not present in current cache; provider rounding/coverage undocumented |
| turnover rate | Provider daily turnover percentage | Provider field candidate | Same endpoint `换手率` | Effective = trading date; available after close; retrieval local | Empirically invariant to qfq on audited sample | Usable descriptively if preserved as provider-supplied; denominator definition/history is not exposed | Missing stays null; never derive from present shares | percent | Store raw percent; decimal = percent/100 only in derived layer | Exact denominator (free float vs circulating shares and historical revisions) is not documented by endpoint |
| adjusted log return | `ln(qfq_close_t/qfq_close_t-1)` on the chosen observation sequence | Locally derived | Existing qfq cache | Assigned to date `t`; computation/retrieval timestamps in manifest | Fully qfq-dependent | Retrospective descriptive validity; not revision-as-of valid | Null for first sequence row or missing/nonpositive input | dimensionless log return | Fixed formula | Sequence basis (company-local vs pair-common) requires decision |
| quarter return | Log change from first to last valid qfq close associated with the quarter | Locally derived | Existing qfq cache | Quarter attribution by close dates | qfq-dependent | Same qfq limitation | Null if fewer than 2 valid closes | dimensionless log return | `ln(P_last/P_first)` | Must not be expressed as a ratio between stocks; pair comparison should be B−A log-return difference |
| realized volatility | Sample standard deviation of daily adjusted log returns dated in quarter | Locally derived | Existing qfq cache | Return assigned by current-row date; quarter contains those dates | qfq-dependent | Same qfq limitation | Null if fewer than 2 returns | log-return per daily session | `std(r, ddof=1)` | No annualization in Phase 1; sequence basis requires decision |
| average / median volume | Arithmetic mean / median of valid daily raw volume rows in quarter | Locally derived from proposed provider field | Same endpoint | Quarter by row date | None | Defensible after versioned refetch | Null if no valid rows; do not insert zeros for absent dates | hands | `mean(volume)`, `median(volume)` | Current cache cannot support it |
| average / median trading amount | Arithmetic mean / median of valid daily raw amounts in quarter | Locally derived from proposed provider field | Same endpoint | Quarter by row date | None | Defensible after versioned refetch | Null if no valid rows | CNY | `mean(amount)`, `median(amount)` | Current cache cannot support it |
| average / median turnover | Mean / median of valid provider turnover percentages | Locally derived from proposed provider field | Same endpoint | Quarter by row date | None | Descriptive only; denominator limitation must display | Null if no valid rows | percent | `mean(turnover_pct)`, `median(turnover_pct)` | Do not substitute `volume/current shares` |
| maximum drawdown | Largest peak-to-subsequent-trough decline of quarter-local qfq normalized path | Locally derived | Existing qfq cache | Quarter-local path by row date | qfq-dependent | Retrospective descriptive validity | Null if no closes | decimal return (display %) | `min_t(P_t/max_{s<=t}P_s - 1)` | Resets at quarter start; not a full-history drawdown |
| large-move count | Count of dates with `abs(adjusted log return)>=0.03` | Locally derived | Existing qfq cache | Event belongs to current return date | qfq-dependent | Same qfq limitation | Count valid returns only; report valid-return denominator | count | Fixed existing 3% rule | Sequence basis requires decision; threshold is unchanged |
| valid trading-observation count | Count of non-null provider daily rows passing field validation in quarter | Locally derived | Relevant immutable daily artifact | Quarter by row date | None | Defensible for observed rows | Report field-specific counts; do not treat absent row as zero | count | `count(valid field)` | Not equivalent to scheduled trading days or “days not suspended” |
| suspension / trading status | Explicit scheduled trading-day status and suspension reason | Provider field, separate candidate | Eastmoney `stock_tfp_em` | Query date plus suspension start/end; retrieval local | None | **Not yet defensible for historical panel**: endpoint is date-query based and provides no documented archival completeness/revision history | Unavailable, not inferred from missing price row | categorical / day count | None until source approved | Missing price can also reflect listing dates, data gaps, or provider issues; requires exchange calendar and validated historical suspension archive |
| limit-up status | Whether stock was validly limit-up under rules applicable that day | Provider field or rule-derived candidate | `stock_zt_pool_em` is recent-only | Date query/retrieval | Must use unadjusted prices and day-specific rules | **Unavailable historically** from audited interface; recent-only pool is not suitable for 2023–2026 complete history | Unavailable | boolean/count | None | Cannot infer reliably from a universal return threshold because board/ST/IPO/rule regimes differ |
| limit-down status | Whether stock was validly limit-down under rules applicable that day | Provider field or rule-derived candidate | `stock_zt_pool_dtgc_em` | Date query/retrieval | Must use unadjusted prices and day-specific rules | **Unavailable historically**; pinned implementation enforces a recent ~30-day window | Unavailable | boolean/count | None | Same rule-regime problem as limit-up |
| total market capitalization | Unadjusted close × contemporaneous total shares, or provider historical total cap | Raw+derived candidate | Current spot endpoint provides only current snapshot; historical endpoint does not provide total shares/cap | Needs row-date shares with known availability | Must use unadjusted close | **Unavailable under current contract** | Unavailable | CNY | Would be `unadjusted close × total shares` | Never substitute current market cap or current shares for historical quarters |
| float market capitalization | Unadjusted close × contemporaneous circulating shares, or provider historical float cap | Raw+derived candidate | Sina `stock_zh_a_daily` exposes `outstanding_share`; different provider | Needs historical share effective/availability dates | Must use unadjusted close | Candidate only, not approved; wrapper forward-fills share series and is documented as IP-fragile | Unavailable until validated | CNY | Would be `unadjusted close × outstanding_share` | Second provider, forward-fill logic, and revision provenance are material risks |

## Pair-relative comparison contract

- Quarter return comparison: `return_B - return_A`; log-return units. Never divide
  returns because values can be zero or negative.
- Volatility ratio: `vol_B / vol_A`; dimensionless, null when `vol_A<=0`.
- Volume ratio: `mean_volume_B / mean_volume_A`; both inputs in hands and the
  denominator label must be visible.
- Trading-amount ratio: `mean_amount_B / mean_amount_A`; both inputs in CNY.
- Turnover comparison: default to `turnover_B - turnover_A` in percentage
  points. A ratio may be displayed only with explicit denominator and null when
  A is zero.
- Drawdown comparison: `max_drawdown_B - max_drawdown_A` in percentage points;
  both inputs use the same quarter-local definition.
- Counts: show A and B counts with their own valid-observation denominators;
  count ratios are not approved by default.
- Market-cap ratio is unavailable until a point-in-time market-cap source is
  approved.

## Material decisions required before implementation

1. **Cache/schema migration.** Approve a new immutable daily-market artifact
   version that retains all provider fields from `stock_zh_a_hist`, plus request,
   retrieval, wrapper-source hash, and response hash. Existing `date,close`
   cache files remain immutable and continue to reproduce old runs.
2. **Observation basis.** Choose whether Company State metrics use each
   company’s own valid daily rows (recommended for company state) or pair-common
   rows (consistent with pair plots). Both can be stored, but labels and
   denominators must be distinct; silent mixing is prohibited.
3. **Market capitalization.** Either approve and validate a separate historical
   share/capital source with point-in-time provenance, or keep total/float market
   cap unavailable. Current snapshots are rejected.
4. **Suspension/status.** Approve a historically complete suspension source and
   exchange trading calendar, or keep suspension counts/status unavailable.
5. **Limit status.** Approve a historically complete rule-aware source, or keep
   limit-up/down fields unavailable. Recent Eastmoney pools cannot support the
   requested history.

Implementation stops here pending these decisions. No Phase 1 panel or data
refetch is authorized by this audit.
