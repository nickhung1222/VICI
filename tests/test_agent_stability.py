import agent


def test_tool_result_status_marks_empty_search():
    assert agent._tool_result_status("search_arxiv", "[]") == "empty"


def test_tool_result_status_marks_tool_errors():
    assert agent._tool_result_status("download_pdf", "Error downloading PDF for 1234.56789: timeout") == "error"


def test_tool_result_status_marks_saved_report():
    assert agent._tool_result_status("save_report", "/tmp/report.md") == "saved"
