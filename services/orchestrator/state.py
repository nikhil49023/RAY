from typing import TypedDict, List, Dict, Any, Literal


class Evidence(TypedDict):
    claim: str
    source: str
    confidence: float
    timestamp: str


class AgentState(TypedDict):
    # Input
    user_query: str
    session_id: str
    
    # Intent classification
    intent: Literal["chat", "research", "coding", "dashboard", "artifact"]
    
    # Memory
    behavioral_rules: List[str]
    applied_rules: List[str]
    
    # Planning
    plan: Dict[str, Any]
    subtasks: List[Dict[str, Any]]
    
    # Evidence collection
    doc_rag_results: List[Dict[str, Any]]
    web_rag_results: List[Dict[str, Any]]
    code_results: List[Dict[str, Any]]
    
    # Verification
    evidence: List[Evidence]
    verification_status: Literal["PENDING", "PASSED", "FAILED"]
    verification_reason: str
    
    # Composition
    final_answer: str
    artifact_path: str
    
    # Metadata
    model_name: str
    checkpoint_mode: Literal["sync", "async"]
    error: str
