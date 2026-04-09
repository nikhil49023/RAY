
@app.get("/api/skills")
async def list_skills():
    try:
        from core.skills import AVAILABLE_SKILLS
        return {
            "skills": [
                {"name": s.name, "description": s.description}
                for s in AVAILABLE_SKILLS
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class SkillExecutionRequest(BaseModel):
    name: str
    prompt: str
    params: dict = {}

@app.post("/api/skills/execute")
async def execute_skill(body: SkillExecutionRequest):
    try:
        from core.skills import get_skill
        skill = get_skill(body.name)
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        
        result = skill.execute(prompt=body.prompt, **body.params)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Failed to execute skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))
