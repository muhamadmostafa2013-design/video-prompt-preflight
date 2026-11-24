import pytest

from vpp.acoustic_models import collapse_phones


def test_ctc_collapses_only_consecutive_ids_before_removing_blank():
    vocab = {"<pad>": 0, "a": 1, "n": 2, "<unk>": 3}
    assert collapse_phones([1, 1, 0, 1, 2, 2, 3], vocab, 0) == ["a", "a", "n", "[uncertain:<unk>]"]
    with pytest.raises(ValueError):
        collapse_phones([9], vocab, 0)
