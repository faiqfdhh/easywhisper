from datetime import timedelta

import srt

from src.subtitles import read_srt, write_srt


def test_round_trip(tmp_path):
    subs = [
        srt.Subtitle(index=1, start=timedelta(0), end=timedelta(seconds=1.5), content="hello"),
        srt.Subtitle(index=2, start=timedelta(seconds=2), end=timedelta(seconds=3.25), content="world"),
    ]
    path = tmp_path / "subs.srt"
    write_srt(path, subs)
    assert path.exists()
    assert read_srt(path) == subs
