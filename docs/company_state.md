# Company and Market Context

Company A and B are displayed side by side without treating similarity as pair
quality. Three groups remain separate:

1. High-frequency market state: size, quarter return, realized volatility,
   volume/amount, turnover, drawdown, large moves, suspensions, and defensible
   liquidity proxies.
2. Operating/fundamental state: revenue, income, margins, returns on capital,
   leverage, cash flow, capex, assets, segments/products, and geographic mix.
3. Valuation/expectation state: point-in-time P/E, P/B, EV/EBITDA, dividend
   yield, and other sourced descriptors.

Industry/market context may contain sector/broad benchmarks, returns,
volatility, activity, and sourced policy/macro context. The interface helps a
human ask whether moves were common or stock-specific but never answers
causally.

Schema: `schemas/company_state.schema.json`. Availability rules are mandatory.
