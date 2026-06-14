from van_eck import van_eck


# First 30 terms of Van Eck's sequence (OEIS A181391).
EXPECTED_30 = [
    0, 0, 1, 0, 2, 0, 2, 2, 1, 6,
    0, 5, 0, 2, 6, 5, 4, 0, 5, 3,
    0, 3, 2, 9, 0, 4, 9, 3, 6, 14,
]


class TestVanEck:
    def test_zero_length(self):
        assert van_eck(0) == []

    def test_negative_length(self):
        assert van_eck(-5) == []

    def test_single_term(self):
        assert van_eck(1) == [0]

    def test_first_few_terms(self):
        result = van_eck(10)
        expected = [0, 0, 1, 0, 2, 0, 2, 2, 1, 6]
        assert result == expected, f"Expected {expected}, got {result}"

    def test_first_twenty_terms(self):
        result = van_eck(20)
        expected = EXPECTED_30[:20]
        assert result == expected, f"Mismatch in first 20 terms: {result}"

    def test_thirty_terms(self):
        result = van_eck(30)
        assert result == EXPECTED_30, (
            f"Mismatch in 30 terms.\nExpected: {EXPECTED_30}\nGot:      {result}"
        )

    def test_recurrence_relation_holds(self):
        """Verify the recurrence definition for the generated sequence."""
        n = 60
        seq = van_eck(n)

        for i in range(1, n):
            prev = seq[i - 1]
            # Find the most recent index j < i-1 where seq[j] == prev.
            most_recent = None
            for j in range(i - 2, -1, -1):
                if seq[j] == prev:
                    most_recent = j
                    break

            if most_recent is None:
                expected = 0
            else:
                expected = (i - 1) - most_recent

            assert seq[i] == expected, (
                f"Recurrence broken at index {i}: got {seq[i]}, "
                f"expected {expected} for prev={prev}"
            )

    def test_first_term_is_zero(self):
        assert van_eck(5)[0] == 0

    def test_returns_list(self):
        assert isinstance(van_eck(10), list)

    def test_correct_length(self):
        for length in [1, 2, 5, 10, 25, 100]:
            assert len(van_eck(length)) == length