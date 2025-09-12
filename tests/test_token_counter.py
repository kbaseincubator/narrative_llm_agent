from datetime import datetime

from narrative_llm_agent.token_counter import TokenCount, TokenCounter


class TestTokenCount:
    """Test suite for TokenCount model."""

    def test_token_count_creation_with_defaults(self):
        """Test creating TokenCount with default values."""
        count = TokenCount()
        assert count.prompt_tokens == 0
        assert count.completion_tokens == 0
        assert count.total_tokens == 0

    def test_token_count_creation_with_values(self):
        """Test creating TokenCount with specific values."""
        count = TokenCount(prompt_tokens=100, completion_tokens=50)
        assert count.prompt_tokens == 100
        assert count.completion_tokens == 50
        assert count.total_tokens == 150

    def test_total_tokens_computed_automatically(self):
        """Test that total_tokens is automatically calculated."""
        count = TokenCount(prompt_tokens=75, completion_tokens=25)
        assert count.total_tokens == 100

    def test_total_tokens_cannot_be_set(self):
        """Test that total_tokens cannot be manually set."""
        count = TokenCount(prompt_tokens=100, completion_tokens=50, total_tokens=999)
        count.total_tokens == 150

    def test_token_count_addition(self):
        """Test adding two TokenCount instances."""
        count1 = TokenCount(prompt_tokens=100, completion_tokens=50)
        count2 = TokenCount(prompt_tokens=20, completion_tokens=10)

        result = count1 + count2

        assert result.prompt_tokens == 120
        assert result.completion_tokens == 60
        assert result.total_tokens == 180

    def test_token_count_addition_with_zeros(self):
        """Test adding TokenCount with zero values."""
        count1 = TokenCount(prompt_tokens=100, completion_tokens=50)
        count2 = TokenCount()  # All zeros

        result = count1 + count2

        assert result.prompt_tokens == 100
        assert result.completion_tokens == 50
        assert result.total_tokens == 150

    def test_negative_token_values(self):
        """Test that negative token values are allowed (for corrections)."""
        count = TokenCount(prompt_tokens=-10, completion_tokens=20)
        assert count.prompt_tokens == -10
        assert count.completion_tokens == 20
        assert count.total_tokens == 10

    def test_token_count_serialization(self):
        """Test that TokenCount can be serialized to dict."""
        count = TokenCount(prompt_tokens=100, completion_tokens=50)
        data = count.model_dump()

        expected = {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'total_tokens': 150
        }
        assert data == expected


class TestTokenCounter:
    """Test suite for TokenCounter model."""

    def test_token_counter_creation_with_session_id(self):
        """Test creating TokenCounter with session ID."""
        counter = TokenCounter(session_id="test_session")

        assert counter.session_id == "test_session"
        assert isinstance(counter.last_updated, datetime)
        assert counter.counts == {}

    def test_token_counter_creation_with_custom_timestamp(self):
        """Test creating TokenCounter with custom timestamp."""
        custom_time = datetime(2023, 1, 1, 12, 0, 0)
        counter = TokenCounter(session_id="test", last_updated=custom_time)

        assert counter.last_updated == custom_time

    def test_update_tokens_new_llm(self):
        """Test updating tokens for a new LLM."""
        counter = TokenCounter(session_id="test")
        initial_time = counter.last_updated

        # Wait a bit to ensure timestamp changes
        import time
        time.sleep(0.01)

        new_count = TokenCount(prompt_tokens=100, completion_tokens=50)
        counter.update_tokens("gpt-4", new_count)

        assert "gpt-4" in counter.counts
        assert counter.counts["gpt-4"].prompt_tokens == 100
        assert counter.counts["gpt-4"].completion_tokens == 50
        assert counter.counts["gpt-4"].total_tokens == 150
        assert counter.last_updated > initial_time

    def test_update_tokens_existing_llm(self):
        """Test updating tokens for an existing LLM."""
        counter = TokenCounter(session_id="test")

        # Add initial count
        initial_count = TokenCount(prompt_tokens=100, completion_tokens=50)
        counter.update_tokens("gpt-4", initial_count)

        # Add more tokens
        additional_count = TokenCount(prompt_tokens=20, completion_tokens=10)
        counter.update_tokens("gpt-4", additional_count)

        assert counter.counts["gpt-4"].prompt_tokens == 120
        assert counter.counts["gpt-4"].completion_tokens == 60
        assert counter.counts["gpt-4"].total_tokens == 180

    def test_update_tokens_multiple_llms(self):
        """Test updating tokens for multiple LLMs."""
        counter = TokenCounter(session_id="test")

        gpt_count = TokenCount(prompt_tokens=100, completion_tokens=50)
        claude_count = TokenCount(prompt_tokens=80, completion_tokens=40)

        counter.update_tokens("gpt-4", gpt_count)
        counter.update_tokens("claude", claude_count)

        assert len(counter.counts) == 2
        assert "gpt-4" in counter.counts
        assert "claude" in counter.counts
        assert counter.counts["gpt-4"].total_tokens == 150
        assert counter.counts["claude"].total_tokens == 120

    def test_get_total_tokens_empty(self):
        """Test getting total tokens when no counts exist."""
        counter = TokenCounter(session_id="test")
        total = counter.get_total_tokens()

        assert total.prompt_tokens == 0
        assert total.completion_tokens == 0
        assert total.total_tokens == 0

    def test_get_total_tokens_single_llm(self):
        """Test getting total tokens with one LLM."""
        counter = TokenCounter(session_id="test")
        count = TokenCount(prompt_tokens=100, completion_tokens=50)
        counter.update_tokens("gpt-4", count)

        total = counter.get_total_tokens()

        assert total.prompt_tokens == 100
        assert total.completion_tokens == 50
        assert total.total_tokens == 150

    def test_get_total_tokens_multiple_llms(self):
        """Test getting total tokens across multiple LLMs."""
        counter = TokenCounter(session_id="test")

        gpt_count = TokenCount(prompt_tokens=100, completion_tokens=50)
        claude_count = TokenCount(prompt_tokens=80, completion_tokens=40)

        counter.update_tokens("gpt-4", gpt_count)
        counter.update_tokens("claude", claude_count)

        total = counter.get_total_tokens()

        assert total.prompt_tokens == 180
        assert total.completion_tokens == 90
        assert total.total_tokens == 270

    def test_token_counter_serialization(self):
        """Test that TokenCounter can be serialized."""
        counter = TokenCounter(session_id="test")
        count = TokenCount(prompt_tokens=100, completion_tokens=50)
        counter.update_tokens("gpt-4", count)

        data = counter.model_dump()

        assert data["session_id"] == "test"
        assert "last_updated" in data
        assert "counts" in data
        assert data["counts"]["gpt-4"]["total_tokens"] == 150

    def test_token_counter_deserialization(self):
        """Test that TokenCounter can be created from dict."""
        data = {
            "session_id": "test",
            "last_updated": "2023-01-01T12:00:00",
            "counts": {
                "gpt-4": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50
                }
            }
        }

        counter = TokenCounter.model_validate(data)

        assert counter.session_id == "test"
        assert counter.counts["gpt-4"].total_tokens == 150


class TestIntegration:
    """Integration tests for the complete system."""

    def test_full_workflow(self):
        """Test a complete workflow of token tracking."""
        # Create counter
        counter = TokenCounter(session_id="integration_test")

        # Simulate multiple API calls
        api_calls = [
            ("gpt-4", TokenCount(prompt_tokens=100, completion_tokens=50)),
            ("claude", TokenCount(prompt_tokens=80, completion_tokens=40)),
            ("gpt-4", TokenCount(prompt_tokens=20, completion_tokens=10)),
            ("claude", TokenCount(prompt_tokens=15, completion_tokens=5)),
        ]

        for llm_name, count in api_calls:
            counter.update_tokens(llm_name, count)

        # Verify final state
        assert counter.counts["gpt-4"].prompt_tokens == 120
        assert counter.counts["gpt-4"].completion_tokens == 60
        assert counter.counts["claude"].prompt_tokens == 95
        assert counter.counts["claude"].completion_tokens == 45

        total = counter.get_total_tokens()
        assert total.prompt_tokens == 215
        assert total.completion_tokens == 105
        assert total.total_tokens == 320
