# Contributing to TheWallflower

Thank you for your interest in contributing!

## Development Setup

1. Fork and clone the repository
2. Set up the backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set up the frontend:
   ```bash
   cd frontend
   npm install
   ```

## Running Locally

**Backend:**
```bash
cd backend
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm run dev
```

## Code Style

- **Python:** Follow PEP 8, use type hints
- **TypeScript/Svelte:** Use Prettier for formatting

## Pull Requests

1. Create a feature branch from `main`
2. Make your changes
3. Write/update tests as needed
4. Ensure all tests pass
5. Submit a pull request

## Commit Messages

Use conventional commits format:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code refactoring

## Questions?

Open an issue for discussion!
