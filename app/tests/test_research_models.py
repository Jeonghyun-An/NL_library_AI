from models.research import JOB_STATUSES, STEP_KINDS, ResearchJob, ResearchStep


class TestResearchModelShape:
    def test_job_statuses_cover_full_lifecycle(self):
        assert JOB_STATUSES == (
            "created", "planning", "awaiting_approval",
            "running", "completed", "failed", "canceled",
        )

    def test_step_kinds(self):
        assert STEP_KINDS == ("plan", "search", "critique", "synthesize")

    def test_job_table_columns(self):
        cols = set(ResearchJob.__table__.columns.keys())
        assert {"id", "question", "status", "params", "plan", "report"} <= cols

    def test_step_table_columns(self):
        cols = set(ResearchStep.__table__.columns.keys())
        assert {"job_id", "seq", "kind", "subq_idx", "title",
                "detail", "status", "result", "updated_at"} <= cols

    def test_step_has_job_seq_index(self):
        names = {ix.name for ix in ResearchStep.__table__.indexes}
        assert "ix_research_steps_job_seq" in names
