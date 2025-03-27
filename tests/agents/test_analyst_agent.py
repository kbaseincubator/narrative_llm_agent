from narrative_llm_agent.agents.analyst import AnalystAgent
import os
import pytest

token = "not_a_token"
FAKE_OPENAI_KEY = "fake_openai_api_key"
FAKE_OPENAI_KEY_ENVVAR = "not_an_openai_key_environment"
OPENAI_KEY = "OPENAI_API_KEY"
FAKE_CBORG_KEY = "fake_cborg_api_key"
FAKE_CBORG_KEY_ENVVAR = "not_a_cborg_key_environment"
CBORG_KEY = "CBORG_API_KEY"
FAKE_TOOLS_MODEL = "fake_model_name"

@pytest.fixture(autouse=True)
def automock_api_key(monkeypatch):
    monkeypatch.setenv(OPENAI_KEY, FAKE_OPENAI_KEY_ENVVAR)
    monkeypatch.setenv(CBORG_KEY, FAKE_CBORG_KEY_ENVVAR)


def test_init_ok(mock_llm):
    wa = AnalystAgent(llm=mock_llm,tools_model= FAKE_TOOLS_MODEL, token=token, cborg_api_key=FAKE_CBORG_KEY)
    assert wa.role == "KBase Analyst and Information Provider"
    assert wa._token == token
    assert wa._cborg_key == FAKE_CBORG_KEY


def test_init_with_env_var(mock_llm):
    wa = AnalystAgent(llm=mock_llm, tools_model= FAKE_TOOLS_MODEL, token=token)
    assert wa.role == "KBase Analyst and Information Provider"
    assert wa._token == token


def test_init_fail_without_envvar(mock_llm, monkeypatch):
    if OPENAI_KEY in os.environ:
        monkeypatch.delenv(OPENAI_KEY)
    if CBORG_KEY in os.environ:
        monkeypatch.delenv(CBORG_KEY)
    with pytest.raises(KeyError):
        AnalystAgent(mock_llm,tools_model= FAKE_TOOLS_MODEL, token=token)


DB_ARGS = ["catalog_db_dir", "docs_db_dir", "tutorial_db_dir"]


@pytest.mark.parametrize("db_arg", DB_ARGS)
def test_init_fail_missing_db_dirs(mock_llm, db_arg):
    missing_dir = "foo"
    with pytest.raises(
        RuntimeError, match=f"Database directory {missing_dir} not found"
    ):
        AnalystAgent(mock_llm, tools_model=FAKE_TOOLS_MODEL, token=token, cborg_api_key=FAKE_CBORG_KEY, **{db_arg: missing_dir})


@pytest.mark.parametrize("db_arg", DB_ARGS)
def test_init_fail_missing_db_file(mock_llm, tmp_path, db_arg):
    tmp_dir = tmp_path / "some_db_dir"
    tmp_dir.mkdir()
    with pytest.raises(
        RuntimeError, match=f"Database file {tmp_dir}/chroma.sqlite3 not found"
    ):
        AnalystAgent(mock_llm, tools_model=FAKE_TOOLS_MODEL, token=token,cborg_api_key=FAKE_CBORG_KEY, **{db_arg: tmp_dir})


@pytest.mark.parametrize("db_arg", DB_ARGS)
def test_init_fail_db_dir_is_file(mock_llm, tmp_path, db_arg):
    tmp_dir = tmp_path / "some_db_dir"
    tmp_dir.mkdir()
    tmp_file = tmp_dir / "should_be_dir"
    tmp_file.write_text("junk")
    with pytest.raises(
        RuntimeError, match=f"Database directory {tmp_file} is not a directory"
    ):
        AnalystAgent(mock_llm, tools_model=FAKE_TOOLS_MODEL, token=token,cborg_api_key=FAKE_CBORG_KEY, **{db_arg: tmp_file})
