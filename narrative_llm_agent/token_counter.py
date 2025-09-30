from datetime import datetime
from pydantic import BaseModel, Field, computed_field

class TokenCount(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @computed_field()
    @property
    def total_tokens(self) -> int:
        """Automatically calculate total tokens."""
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: 'TokenCount') -> 'TokenCount':
        """Add two TokenCount instances together."""
        return TokenCount(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )

class TokenCounter(BaseModel):
    session_id: str
    last_updated: datetime = Field(default_factory=datetime.now)
    counts: dict[str, TokenCount] = Field(default_factory=dict)

    def update_tokens(self, llm_name: str, new_count: TokenCount) -> None:
        """Update token counts for a specific LLM."""
        if llm_name in self.counts:
            self.counts[llm_name] = self.counts[llm_name] + new_count
        else:
            self.counts[llm_name] = new_count

        self.last_updated = datetime.now()

    def get_total_tokens(self) -> TokenCount:
        """Get total tokens across all LLMs."""
        total = TokenCount()
        for count in self.counts.values():
            total = total + count
        return total

class TokenCounterStore(BaseModel):
    sessions: dict[str, TokenCounter]

    def update(self, session_id: str, llm_name: str, new_count: TokenCount):
        if session_id not in self.sessions:
            self.sessions[session_id] = TokenCounter(session_id=session_id)
        self.sessions[session_id].update_tokens(llm_name, new_count)
