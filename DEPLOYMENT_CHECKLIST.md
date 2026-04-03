# LangGraph Migration: Deployment Checklist

## Pre-Deployment

### Environment Setup
- [ ] Python 3.10+ installed
- [ ] Docker and Docker Compose installed
- [ ] Virtual environment created (`.venv`)
- [ ] All dependencies installed (`requirements-langgraph.txt`)

### Service Health
- [ ] LiteLLM proxy running on :4000
- [ ] ChromaDB running on :8000
- [ ] Ollama running on :11434
- [ ] Firecrawl (optional) running on :3002

### Configuration
- [ ] `.env` file configured with API keys
- [ ] `configs/graph.yaml` reviewed
- [ ] `configs/memory.yaml` reviewed
- [ ] Checkpoint directory exists (`data/checkpoints/`)

### Memory Collections
- [ ] `ray_docs` collection exists (or will be created)
- [ ] `ray_behavior` collection initialized
- [ ] `ray_execution` collection initialized
- [ ] Ollama embedding model pulled (`nomic-embed-text`)

## Testing

### Unit Tests
- [ ] `python tests/test_memory_promotion.py` passes
- [ ] `python tests/test_verifier_coverage.py` passes

### Integration Tests
- [ ] `python tests/test_graph_execution.py` passes
- [ ] Simple chat query works
- [ ] Research query with evidence works
- [ ] Behavioral memory injection works
- [ ] Error handling graceful

### Performance Tests
- [ ] Chat response < 5s
- [ ] Research response < 20s
- [ ] Artifact generation < 10s
- [ ] Memory retrieval < 1s

## Deployment

### Initial Launch
- [ ] Run `./scripts/start_langgraph_workspace.sh`
- [ ] Chainlit UI accessible at http://localhost:8001
- [ ] No errors in console
- [ ] ScoreCard shows services ready

### Smoke Tests
- [ ] Send test query: "Hello"
- [ ] Send research query: "Research LangGraph benefits"
- [ ] Send artifact query: "Generate a PDF report"
- [ ] Toggle `/crewai` and `/langgraph` commands
- [ ] Check memory badge appears

### Data Persistence
- [ ] Checkpoint database created (`data/checkpoints/graph.db`)
- [ ] Behavioral rules persisted (`data/memory/behavior_rules.jsonl`)
- [ ] Execution history logged (`data/memory/execution_history.jsonl`)
- [ ] Artifacts saved (`data/artifacts/`)

## Monitoring

### Health Checks
- [ ] Monitor LiteLLM fallback usage
- [ ] Monitor Chroma query latency
- [ ] Monitor checkpoint database size
- [ ] Monitor memory collection growth

### Error Tracking
- [ ] Check for verification failures
- [ ] Check for RAG unavailability
- [ ] Check for LLM provider errors
- [ ] Check for checkpoint corruption

### Performance Metrics
- [ ] Average response time per intent
- [ ] Evidence retrieval success rate
- [ ] Memory promotion rate
- [ ] Artifact generation success rate

## Post-Deployment

### Week 1: Parallel Operation
- [ ] LangGraph mode default
- [ ] CrewAI fallback available
- [ ] Compare response quality
- [ ] Monitor error rates
- [ ] Collect user feedback

### Week 2: Optimization
- [ ] Tune verification thresholds
- [ ] Adjust memory promotion rules
- [ ] Optimize checkpoint frequency
- [ ] Review fallback chain

### Week 3: Validation
- [ ] LangGraph stability confirmed
- [ ] Performance targets met
- [ ] Memory system working correctly
- [ ] No critical issues

### Week 4: CrewAI Removal
- [ ] Remove CrewAI orchestrator
- [ ] Remove `/crewai` command
- [ ] Update documentation
- [ ] Archive old code

## Rollback Plan

### If Critical Issues Arise
1. [ ] Switch default to CrewAI mode
2. [ ] Investigate LangGraph errors
3. [ ] Fix issues in development
4. [ ] Re-test thoroughly
5. [ ] Re-deploy when stable

### Rollback Commands
```bash
# Emergency rollback to CrewAI
# In chainlit_app.py, change:
cl.user_session.set("use_langgraph", False)  # Default to CrewAI

# Or via chat command:
/crewai
```

## Success Criteria

### Functional
- [x] All 8 graph nodes execute correctly
- [x] Verification enforces evidence requirements
- [x] Memory promotion filters ephemeral facts
- [x] Inline UI elements render correctly
- [x] Artifacts generate successfully

### Performance
- [ ] Chat: < 3s average
- [ ] Research: < 15s average
- [ ] Artifact: < 8s average
- [ ] Memory retrieval: < 1s

### Reliability
- [ ] Uptime > 99%
- [ ] Error rate < 1%
- [ ] Fallback success rate > 95%
- [ ] Checkpoint recovery works

### User Experience
- [ ] Behavioral memory improves responses
- [ ] Evidence table provides transparency
- [ ] Timeline shows progress clearly
- [ ] Artifacts are downloadable

## Documentation

### Updated Files
- [x] `LANGGRAPH_README.md` - Complete guide
- [x] `ARCHITECTURE.md` - System diagrams
- [x] `IMPLEMENTATION_SUMMARY.md` - What was built
- [x] `MIGRATION_ROADMAP.md` - Day-by-day plan
- [ ] Update main `README.md` with LangGraph info

### User Guides
- [ ] How to use LangGraph mode
- [ ] How to interpret evidence tables
- [ ] How to manage behavioral memory
- [ ] How to generate artifacts

### Developer Guides
- [ ] How to add new graph nodes
- [ ] How to modify verification rules
- [ ] How to create custom UI elements
- [ ] How to extend memory system

## Maintenance

### Daily
- [ ] Check service health
- [ ] Monitor error logs
- [ ] Review checkpoint database size

### Weekly
- [ ] Analyze performance metrics
- [ ] Review memory promotion quality
- [ ] Check artifact generation success
- [ ] Update fallback model list

### Monthly
- [ ] Optimize memory collections
- [ ] Archive old checkpoints
- [ ] Update dependencies
- [ ] Review and tune configurations

## Sign-Off

### Development Team
- [ ] Code review complete
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Ready for deployment

### Operations Team
- [ ] Infrastructure ready
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Rollback plan tested

### Product Team
- [ ] Features validated
- [ ] User experience approved
- [ ] Performance acceptable
- [ ] Ready for users

---

**Deployment Date**: _____________

**Deployed By**: _____________

**Sign-Off**: _____________
