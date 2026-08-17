# Add Industries to Portfolio (Option A)

## Feature

The Portfolio page (`/portfolio`) includes a **View** selector:

- **My Portfolio** — saved portfolio stocks with add/remove actions (unchanged).
- **Industry name** — all stocks assigned to that industry via Admin, shown in the same metrics grid (Performance, Valuation, etc.) without add/remove.

Industry assignments are managed at `/admin/industries` (`stock_industry` table).

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/portfolio/grid` | Grid rows for portfolio symbols |
| `GET /api/admin/industries/{industry}/grid` | Grid rows for an industry's symbols |
| `GET /api/admin/industries` | Industry names + symbol lists (used by view selector) |

Both grid endpoints return `{ rows, errors }`; industry grid also includes `industry`.

## Implementation notes

- Shared row building lives in `backend/services/grid_service.py`.
- `PortfolioGrid` accepts `view: { mode: 'portfolio' } | { mode: 'industry', industry: string }`.
- Industry view hides Add Stock and remove-column actions.

## Verification

```bash
curl http://127.0.0.1:8000/api/admin/industries
curl "http://127.0.0.1:8000/api/admin/industries/YOUR_INDUSTRY/grid"
```

Open http://localhost:3002/portfolio, switch View to an industry, confirm grid loads with same tabs/columns.
