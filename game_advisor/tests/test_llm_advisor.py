# game_advisor/tests/test_llm_advisor.py
import json
import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from unittest.mock import MagicMock, patch
from game_state import BoardCard, GameState, HandCard, Player
from llm_advisor import LLMAdvisor, _claude_cli_available, _complete_via_claude_cli


def _make_state() -> GameState:
    attacker = BoardCard(
        name="Goblin Blast-Runner", arena_id="0", instance_id=1,
        power=2, toughness=1, keywords=["haste"],
    )
    spell = HandCard(
        name="Lightning Strike", arena_id="1", instance_id=2,
        mana_cost="{1}{R}", cmc=2, colors=["R"], castable=True,
    )
    you = Player(seat_id=1, life=18, board=[attacker], hand=[spell],
                 mana_available=2, mana_colors=["R", "R"])
    opp_creature = BoardCard(
        name="Warden of the Inner Sky", arena_id="2", instance_id=3,
        power=2, toughness=2, keywords=["flying"],
    )
    opp = Player(seat_id=2, life=20, board=[opp_creature], hand=[])
    return GameState(turn=3, phase="Main 1", active_seat=1, you=you, opponent=opp)


def _mock_openai_response(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def test_request_advice_sync_returns_text():
    state = _make_state()
    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            _mock_openai_response("Kill the Warden with Lightning Strike.")
        )
        advisor = LLMAdvisor(api_key="test-key")
        result = advisor._call_api(state)
        assert "Warden" in result or "Lightning" in result or len(result) > 0


def test_caching_skips_duplicate_api_call():
    state = _make_state()
    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            _mock_openai_response("Attack with Blast-Runner.")
        )
        advisor = LLMAdvisor(api_key="test-key")
        result1 = advisor._call_api(state)
        result2 = advisor._call_api(state)  # same state — should use cache
        assert mock_client.chat.completions.create.call_count == 1
        assert result1 == result2


def test_rate_limit_blocks_rapid_calls():
    state1 = _make_state()
    # Slightly different state (different life total) to bypass state-hash cache
    you2 = Player(seat_id=1, life=15, board=[], hand=[], mana_available=0, mana_colors=[])
    opp2 = Player(seat_id=2, life=20, board=[], hand=[])
    state2 = GameState(turn=3, phase="Main 1", active_seat=1, you=you2, opponent=opp2)

    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = (
            _mock_openai_response("Hold your spells.")
        )
        advisor = LLMAdvisor(api_key="test-key", min_interval_seconds=60)
        advisor._call_api(state1)
        result2 = advisor._call_api(state2)  # rate-limited — same cached result
        assert mock_client.chat.completions.create.call_count == 1
        assert result2 is not None


def test_api_timeout_returns_fallback():
    state = _make_state()
    with patch("llm_advisor.openai.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("timeout")
        advisor = LLMAdvisor(api_key="test-key")
        result = advisor._call_api(state)
        assert result == LLMAdvisor.OFFLINE_MESSAGE


def test_build_prompt_contains_key_info():
    state = _make_state()
    advisor = LLMAdvisor(api_key="test-key")
    prompt = advisor._build_prompt(state)
    assert "T3" in prompt             # turn (compressed format)
    assert "18" in prompt             # your life
    assert "Goblin Blast-Runner" in prompt
    assert "Lightning Strike" in prompt
    assert "Warden of the Inner Sky" in prompt


def _mock_cli_proc(returncode: int = 0, result: str = "", is_error: bool = False,
                    stdout: str = None, stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout if stdout is not None else json.dumps(
        {"result": result, "is_error": is_error}
    )
    proc.stderr = stderr
    return proc


def test_claude_cli_available_reflects_shutil_which():
    with patch("llm_advisor.shutil.which", return_value="/usr/bin/claude"):
        assert _claude_cli_available() is True
    with patch("llm_advisor.shutil.which", return_value=None):
        assert _claude_cli_available() is False


def test_complete_via_claude_cli_returns_result_text():
    with patch("llm_advisor.shutil.which", return_value="/usr/bin/claude"), \
         patch("llm_advisor.subprocess.run", return_value=_mock_cli_proc(result="Attack now.")) as mock_run:
        result = _complete_via_claude_cli("system prompt", "user prompt", timeout=10)
        assert result == "Attack now."
        assert mock_run.call_args.kwargs["input"] == "system prompt\n\n---\n\nuser prompt"


def test_complete_via_claude_cli_scrubs_anthropic_env_vars(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-leak")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    with patch("llm_advisor.shutil.which", return_value="/usr/bin/claude"), \
         patch("llm_advisor.subprocess.run", return_value=_mock_cli_proc(result="ok")) as mock_run:
        _complete_via_claude_cli("sys", "user", timeout=10)
        passed_env = mock_run.call_args.kwargs["env"]
        assert "ANTHROPIC_API_KEY" not in passed_env
        assert "CLAUDE_CODE_USE_BEDROCK" not in passed_env


def test_complete_via_claude_cli_raises_when_cli_missing():
    with patch("llm_advisor.shutil.which", return_value=None):
        try:
            _complete_via_claude_cli("sys", "user", timeout=10)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "not found on PATH" in str(exc)


def test_complete_via_claude_cli_retries_once_then_raises():
    with patch("llm_advisor.shutil.which", return_value="/usr/bin/claude"), \
         patch("llm_advisor.subprocess.run", return_value=_mock_cli_proc(returncode=1, stderr="boom")), \
         patch("llm_advisor.time.sleep"):
        try:
            _complete_via_claude_cli("sys", "user", timeout=10)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "failed after retry" in str(exc)


def test_llm_advisor_claude_backend_skips_openai_client():
    advisor = LLMAdvisor(backend="claude")
    assert advisor._client is None


def test_llm_advisor_claude_backend_returns_cli_result():
    state = _make_state()
    with patch("llm_advisor.shutil.which", return_value="/usr/bin/claude"), \
         patch("llm_advisor.subprocess.run", return_value=_mock_cli_proc(result="Cast Lightning Strike.")):
        advisor = LLMAdvisor(backend="claude")
        result = advisor._call_api(state)
        assert result == "Cast Lightning Strike."


def test_llm_advisor_claude_backend_falls_back_offline_on_cli_error():
    state = _make_state()
    with patch("llm_advisor.shutil.which", return_value=None):
        advisor = LLMAdvisor(backend="claude")
        result = advisor._call_api(state)
        assert result == LLMAdvisor.OFFLINE_MESSAGE
