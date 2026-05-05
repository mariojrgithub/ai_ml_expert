"""Chunk 12 tests — multi-turn eval runner."""
from unittest.mock import patch
from app.evals.runner import run_eval_case


def _mock_run(session_id, user_input):
    return {
        'validated_output': f'Answer for: {user_input}',
        'warnings': [],
        'trace': [],
        'run_metadata': {'grounded': True, 'abstain': False},
    }


def test_run_eval_case_single_turn():
    case = {
        'id': 'test-single',
        'task_type': 'CODE',
        'input': 'Write hello world',
        'required_keywords': ['Answer'],
        'forbidden_keywords': ['DROP TABLE'],
    }
    with patch('app.evals.runner.run_agent_with_trace', side_effect=_mock_run):
        result = run_eval_case(case)

    assert result['id'] == 'test-single'
    assert 'Answer' in result['answer']
    assert result.get('multi_turn') is None


def test_run_eval_case_multi_turn_calls_agent_for_each_turn():
    case = {
        'id': 'test-multi',
        'task_type': 'CODE',
        'multi_turn': True,
        'turns': [
            {'input': 'first turn', 'required_keywords': [], 'forbidden_keywords': []},
            {'input': 'second turn', 'required_keywords': ['Answer'], 'forbidden_keywords': []},
        ],
    }
    call_inputs = []

    def tracking_run(session_id, user_input):
        call_inputs.append(user_input)
        return _mock_run(session_id, user_input)

    with patch('app.evals.runner.run_agent_with_trace', side_effect=tracking_run):
        result = run_eval_case(case)

    assert call_inputs == ['first turn', 'second turn']
    assert result['multi_turn'] is True


def test_run_eval_case_multi_turn_uses_same_session_for_all_turns():
    case = {
        'id': 'test-session',
        'task_type': 'CODE',
        'multi_turn': True,
        'turns': [
            {'input': 'turn A', 'required_keywords': [], 'forbidden_keywords': []},
            {'input': 'turn B', 'required_keywords': [], 'forbidden_keywords': []},
        ],
    }
    session_ids = []

    def tracking_run(session_id, user_input):
        session_ids.append(session_id)
        return _mock_run(session_id, user_input)

    with patch('app.evals.runner.run_agent_with_trace', side_effect=tracking_run):
        run_eval_case(case)

    assert session_ids[0] == session_ids[1], "All turns should share the same session_id"


def test_run_eval_case_multi_turn_scores_final_turn():
    case = {
        'id': 'test-score',
        'task_type': 'CODE',
        'multi_turn': True,
        'turns': [
            {'input': 'first', 'required_keywords': [], 'forbidden_keywords': []},
            {'input': 'second', 'required_keywords': ['Answer'], 'forbidden_keywords': ['DROP TABLE']},
        ],
    }
    with patch('app.evals.runner.run_agent_with_trace', side_effect=_mock_run):
        result = run_eval_case(case)

    assert result['score']['passed'] is True


def test_run_eval_case_multi_turn_no_turns_fails_gracefully():
    case = {
        'id': 'test-empty',
        'task_type': 'CODE',
        'multi_turn': True,
        'turns': [],
    }
    with patch('app.evals.runner.run_agent_with_trace', side_effect=_mock_run):
        result = run_eval_case(case)

    assert result['score']['passed'] is False
    assert result['score']['failure_category'] == 'no_turns'
