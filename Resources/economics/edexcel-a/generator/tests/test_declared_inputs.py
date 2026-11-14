"""Built-in papers must not discover optional notes in a source checkout."""

from pathlib import Path
from unittest.mock import patch

import pytest
from pastpapergen.generator import build_paper_blueprint
from pastpapergen.ollama_client import build_question_prompt
from pastpapergen.paper_configs import load_builtin_paper_config
from pastpapergen.render_pdf import _specific_answer_points
from pastpapergen.syllabus import load_syllabus


@pytest.mark.parametrize("paper,seed", [("paper_1", 26080118), ("paper_2", 26080119)])
def test_paper_and_marking_use_only_declared_inputs(paper, seed):
    read_text = Path.read_text

    def reject_notes(path, *args, **kwargs):
        assert "notes" not in path.parts, f"Read undeclared input: {path}"
        return read_text(path, *args, **kwargs)

    with patch.object(Path, "read_text", reject_notes):
        syllabus = load_syllabus(Path("data/syllabus_seed.json"))
        config = load_builtin_paper_config(paper)
        blueprint = build_paper_blueprint(config, syllabus, seed)
        topics = {topic.id: topic for topic in syllabus.topics}
        for question in blueprint.questions:
            topic = topics[question.topic_id]
            assert topic.title in build_question_prompt(question, topic)
            _specific_answer_points(question, topic)
