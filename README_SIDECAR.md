# RAY God Mode Agent - Sidecar Application

A full-stack AI research assistant packaged as a Docker Compose sidecar application.

## Overview

This sidecar provides:
- **Backend**: FastAPI server with LangGraph orchestration (port 8002)
- **Frontend**: React/Vite UI with AI chat interface (port 3000)
- **Features**: AI-powered research, visual artifact generation, document creation, persistent memory

## Components

### Backend Services
- **FastAPI Server**: Handles chat requests, orchestrates AI workflow
- **LangGraph Pipeline**: Multi-step AI processing with conditional routing
- **Multiple LLM Providers**: Groq, OpenRouter, Sarvam integration
- **Research Tools**: DuckDuckGo search, Firecrawl web scraping
- **Memory System**: Persistent conversation and behavioral memory
- **Artifact Storage**: Saves generated documents, charts, diagrams

### Frontend Application
- **React 19 + Vite**: Modern UI framework
- **Vercel AI SDK**: Streaming chat interface
- **Visual Rendering**: Mermaid diagrams, charts, tables, timelines
- **Structured Content**: AI-generated visual artifacts rendered inline
- **Responsive Design**: Works on desktop and mobile

## Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose v2+
- API keys for at least one LLM provider (Groq recommended)

### Configuration
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your API keys:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   SARVAM_API_KEY=your_sarvam_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

### Start the Application
```bash
# Start both backend and frontend
docker compose -f docker-compose.sidecar.yml up -d

# View logs
docker compose -f docker-compose.sidecar.yml logs -f

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8002
```

## Development

### Rebuild Services
```bash
# Rebuild and restart
docker compose -f docker-compose.sidecar.yml up -d --build

# Restart only backend
docker compose -f docker-compose.sidecar.yml restart backend

# Restart only frontend
docker compose -f docker-compose.sidecar.yml restart frontend
```

### Access Logs
```bash
# Backend logs
docker compose -f docker-compose.sidecar.yml logs backend

# Frontend logs
docker compose -f docker-compose.sidecar.yml logs frontend
```

### Access Shells
```bash
# Backend shell
docker compose -f docker-compose.sidecar.yml exec backend /bin/bash

# Frontend shell
docker compose -f docker-compose.sidecar.yml exec frontend /bin/sh
```

## API Endpoints

### Chat Interface
```
POST /api/chat
Content-Type: application/json

{
  "messages": [{"role": "user", "content": "Your question here"}],
  "model": "groq/llama-3.3-70b-versatile",
  "mode": "standard",
  "temperature": 0.1,
  "visualsEnabled": false,
  "sessionId": "optional-session-id"
}
```

### Health Check
```
GET /api/health
```

### Model Listing
```
GET /api/models
```

### Artifact Management
```
GET /api/artifacts          # List artifacts
POST /api/artifacts         # Save artifact
GET /api/artifacts/{id}     # Get artifact
```

### Research Sessions
```
GET /api/research           # List research sessions
GET /api/research/{id}      # Get research session
```

### Thread Management
```
GET /api/threads            # List chat threads
POST /api/threads           # Save thread
GET /api/threads/{id}       # Get thread
DELETE /api/threads/{id}    # Delete thread
```

### Settings
```
GET /api/settings           # Get current settings
POST /api/settings          # Update settings
```

## Visual Artifact Types

The AI can generate these visual artifacts automatically:

1. **Mermaid Diagrams** - Flowcharts, sequence diagrams, class diagrams
2. **Charts** - Bar, line, area, pie charts with customizable styling
3. **Tables** - Comparison tables, data grids
4. **Timelines** - Event-based temporal visualizations
5. **Scoreboards** - Rankings, leaderboards, performance metrics
6. **Node Graphs** - Concept maps, entity relationships
7. **Heatmaps** - Matrix data visualizations
8. **Donut Charts** - Distribution and proportion visualizations
9. **Math Equations** - LaTeX-rendered mathematical expressions
10. **Physics Visualizations** - Waveforms, fields, spectra, orbitals

## Environment Variables

### Backend (.env)
```
GROQ_API_KEY=your_groq_key
SARVAM_API_KEY=your_sarvam_key
OPENROUTER_API_KEY=your_openrouter_key
RAY_ENV=development  # or production
```

### Frontend (docker-compose)
```
VITE_API_URL=http://backend:8002  # Internal service URL
```

## Production Deployment

For production use:
```bash
# Use production configuration
docker compose -f docker-compose.sidecar.yml -f docker-compose.prod.yml up -d

# Set production environment
RAY_ENV=production
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**
   ```bash
   # Check what's using ports 3000 and 8002
   lsof -i :3000
   lsof -i :8002
   
   # Kill conflicting processes
   kill -9 <PID>
   ```

2. **API Key Errors**
   - Verify keys are correctly set in .env
   - Check backend logs for authentication errors
   - Ensure account has sufficient credits/quota

3. **Memory Issues**
   - Increase Docker memory allocation in settings
   - Monitor container memory usage:
     ```bash
     docker stats
     ```

4. **Build Failures**
   ```bash
   # Clear Docker cache and rebuild
   docker compose -f docker-compose.sidecar.yml build --no-cache
   ```

### Log Analysis
```bash
# Follow backend logs in real-time
docker compose -f docker-compose.sidecar.yml logs -f backend

# Follow frontend logs
docker compose -f docker-compose.sidecar.yml logs -f frontend

# Get recent logs only
docker compose -f docker-compose.sidecar.yml logs --tail=100 backend
```

## Maintenance

### Updates
```bash
# Pull latest images (if using pre-built)
docker compose -f docker-compose.sidecar.yml pull

# Rebuild with latest code
docker compose -f docker-compose.sidecar.yml build

# Restart services
docker compose -f docker-compose.sidecar.yml up -d
```

### Data Persistence
Data is stored in:
- `./godmode-agent/data/` - Threads, artifacts, research sessions
- Docker volumes for external services (ChromaDB, Qdrant, etc.)

### Backup
```bash
# Backup application data
tar -czf ray-backup-$(date +%Y%m%d).tar.gz godmode-agent/data

# Restore
tar -xzf ray-backup-*.tar.gz
```

## Security Notes

1. **API Keys**: Never commit .env files to version control
2. **Network Isolation**: Services communicate only via Docker network
3. **File System**: Containerized filesystem limits host exposure
4. **Updates**: Regularly rebuild images to get security patches

## Extension Points

### Adding New LLM Providers
1. Add to `services/orchestrator/llm_factory.py`
2. Update `services/orchestrator/runtime.py` configuration
3. Add model entries in `/api/models` endpoint

### Custom Visual Components
1. Add new component to `apps/web/src/App.tsx`
2. Update `parseStructuredContent()` regex patterns
3. Add renderer in `StructuredContent` component
4. Update `visual_output.py` with new format specification

### External Integrations
- Add new API endpoints in `apps/api/server.py`
- Extend LangGraph state in `services/orchestrator/state.py`
- Add new nodes to `services/orchestrator/nodes/`

## License

MIT License - see LICENSE file for details.

## Support

For issues, questions, or contributions:
- Check existing documentation
- Review source code comments
- Contact maintainers through project channels