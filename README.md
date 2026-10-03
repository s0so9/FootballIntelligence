# Football Intelligence Platform

Professional football analytics, prediction, and live analysis platform.

## Overview

Football Intelligence is a comprehensive football analytics system capable of:

- Collecting and storing football data
- Analyzing teams, players, and matches
- Calculating statistical features
- Generating predictions using multiple models
- Calibrating probabilities
- Backtesting prediction models
- Comparing predictions with market information
- Updating predictions during live matches
- Explaining predictions using a local AI Analyst

## Architecture

The platform consists of three main components:

### Backend (Python + FastAPI)
- RESTful API server
- Prediction engine with multiple models
- Feature engineering layer
- Database abstraction (PostgreSQL-ready)
- Provider abstraction for data sources
- AI Analyst integration (Ollama)

### Frontend (React + TypeScript + Vite)
- Professional dark-themed web interface
- Turkish-first UI
- Real-time prediction display
- Analytics workspace
- Backtesting visualization

### Database (PostgreSQL)
- Match and team data
- Historical statistics
- Prediction results
- Model performance metrics

## Project Structure

```
FootballIntelligence/
├── backend/           # Python FastAPI backend
├── frontend/          # React TypeScript frontend
├── database/          # Database schemas and migrations
├── scripts/           # Utility scripts
├── docs/              # Documentation
├── PROJECT_SPEC.md    # Master product specification
├── AGENTS.md          # Agent operational rules
└── README.md          # This file
```

## Technology Stack

### Backend
- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- NumPy/SciPy
- PostgreSQL

### Frontend
- React 18
- TypeScript
- Vite
- React Router

### AI
- Ollama (qwen3-coder:30b)
- Local inference only

## Getting Started

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
copy .env.example .env

# Run development server
uvicorn app.main:app --reload
```

Backend will be available at: http://localhost:8000

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend will be available at: http://localhost:5173

## Development Principles

1. **Numerical Engine First**: All predictions derive from mathematical models
2. **AI as Explanation Layer**: AI Analyst explains, never invents statistics
3. **Data Integrity**: Mock data must be clearly labeled
4. **Modular Architecture**: Clean separation of concerns
5. **Type Safety**: Full type coverage in both backend and frontend
6. **Progressive Testing**: Test critical components as they're built
7. **Verification**: Always verify implementation works

## Core Principles

- The numerical/statistical engine is the source of truth
- The AI Analyst is an explanation layer only
- Never invent statistics, probabilities, or predictions
- Missing data must be explicitly represented as unavailable
- Development/mock data must be clearly labeled

## Documentation

- `PROJECT_SPEC.md` - Complete product specification
- `AGENTS.md` - Operational rules for autonomous agents
- `docs/PROGRESS.md` - Implementation progress log
- `backend/README.md` - Backend documentation
- `frontend/README.md` - Frontend documentation

## Development Status

🚧 **Under Active Development**

Currently implementing PHASE 1:
- Project structure setup
- Basic backend architecture
- Basic frontend architecture
- Development data providers
- First prediction models (Poisson)
- AI Analyst integration

See `docs/PROGRESS.md` for detailed progress tracking.

## License

Proprietary - All Rights Reserved

## Notes

- Keep technical identifiers in English
- User-facing text primarily in Turkish
- PostgreSQL-ready architecture (SQLite for development)
- No external AI APIs (Ollama only)
