import main


class _FakeSession:
    def __init__(self):
        self.questions = []

    def chat(self, question):
        self.questions.append(question)
        return {
            "answer": f"Echo: {question}",
            "citations": [
                {
                    "source_type": "knowledge_base",
                    "title": "Test Paper",
                    "locator": "outputs/papers/test.json",
                }
            ],
            "freshness_note": "Answer grounded primarily in audited local records.",
        }


def test_chat_loop_handles_single_question_and_exit(monkeypatch, capsys):
    fake_session = _FakeSession()

    monkeypatch.setattr(main.agent, "ResearchSession", lambda: fake_session)

    prompts = iter(["What does the knowledge base say?", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(prompts))

    result = main._run_chat_loop()
    captured = capsys.readouterr()

    assert result == 0
    assert fake_session.questions == ["What does the knowledge base say?"]
    assert "Interactive chat mode" in captured.out
    assert "Echo: What does the knowledge base say?" in captured.out
    assert "Citations:" in captured.out
