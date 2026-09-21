import pytest

from services.research.scoring import blend_score, impact_per_year, parse_pub_year


class TestParsePubYear:
    @pytest.mark.parametrize("raw,expected", [
        ("2008-06", 2008),
        ("2008", 2008),
        ("200806", 2008),
        ("", None),
        (None, None),
        ("연도미상", None),
    ])
    def test_parse(self, raw, expected):
        assert parse_pub_year(raw) == expected


class TestImpactPerYear:
    def test_zero_citations(self):
        assert impact_per_year(0, 2008, now_year=2026) == 0.0

    def test_missing_year_gives_zero(self):
        assert impact_per_year(50, None, now_year=2026) == 0.0

    def test_same_year_does_not_divide_by_zero(self):
        assert impact_per_year(4, 2026, now_year=2026) == 4.0

    def test_normalization_flips_raw_order(self):
        """생피인용은 2002년 논문이 크지만 연간으로는 2024년 논문이 크다."""
        old = impact_per_year(50, 2002, now_year=2026)    # 50 / 25 = 2.0
        new = impact_per_year(40, 2024, now_year=2026)    # 40 / 3  = 13.3
        assert new > old

    def test_future_year_is_clamped(self):
        assert impact_per_year(10, 2030, now_year=2026) == 10.0


class TestBlendScore:
    def test_zero_weight_leaves_rerank_untouched(self):
        assert blend_score(0.8, impact=13.3, weight=0.0) == pytest.approx(0.8)

    def test_impact_raises_score(self):
        assert blend_score(0.8, impact=13.3, weight=0.2) > 0.8

    def test_zero_impact_leaves_score_untouched(self):
        assert blend_score(0.8, impact=0.0, weight=0.2) == pytest.approx(0.8)

    def test_growth_is_damped(self):
        """영향력 10배가 점수 10배가 되면 안 된다 — 의미 유사도가 주여야 한다."""
        low = blend_score(0.8, impact=1.0, weight=0.2)
        high = blend_score(0.8, impact=100.0, weight=0.2)
        assert high < low * 5
