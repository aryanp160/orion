# Contributing to ORION

Thank you for contributing to ORION (On-chain Routing & Intelligence for Optimal Notional Execution).

## Code Quality Standards

1. **Type Safety**:
   - Backend: All functions and data schemas must be fully typed (Python 3.12 + Pydantic v2 + strict typing).
   - Frontend: Strict TypeScript checking (`noImplicitAny: true`, strict null checks).
2. **Determinism**:
   - Execution cost calculations must be deterministic.
   - Use `Decimal` or exact integer/fixed-point representations for monetary calculations and basis points.
3. **Testing**:
   - Unit tests are required for all cost models, router filtering, risk controls, and paper accounting.
   - Integration tests must run against offline deterministic fixtures and verified mock providers.
4. **Git Hygiene**:
   - Write clear, conventional commit messages (`feat:`, `fix:`, `chore:`, `test:`, `docs:`).
   - Never commit API keys, private keys, or `.env` files.
