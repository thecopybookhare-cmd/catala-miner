from app import youtube


def test_progress_dash_fragments():
    # 3cat / HLS: total_bytes ausente, pero hay fragmentos
    frac, msg = youtube.progress_of({
        "status": "downloading", "total_bytes": None,
        "total_bytes_estimate": 507860.0, "downloaded_bytes": 5_000_000,
        "fragment_index": 379, "fragment_count": 758})
    assert abs(frac - 0.9 * 379 / 758) < 1e-6         # por fragmentos
    assert "50%" in msg or "379" in msg


def test_progress_http_total_bytes():
    frac, msg = youtube.progress_of({
        "status": "downloading", "total_bytes": 1000, "downloaded_bytes": 500})
    assert abs(frac - 0.9 * 0.5) < 1e-6
    assert "%" in msg


def test_progress_estimate_only():
    frac, _ = youtube.progress_of({
        "status": "downloading", "total_bytes_estimate": 1000,
        "downloaded_bytes": 250})
    assert abs(frac - 0.9 * 0.25) < 1e-6


def test_progress_unknown_total_shows_mb():
    # ni total ni fragmentos -> sin fracción, pero mensaje con MB
    frac, msg = youtube.progress_of({
        "status": "downloading", "downloaded_bytes": 2_500_000})
    assert frac is None
    assert "2.5" in msg and "MB" in msg


def test_progress_finished_phase():
    frac, msg = youtube.progress_of({"status": "finished"})
    assert frac == 0.9
    assert msg
