from app import config, share


def test_status_shape_when_stopped():
    s = share.status()
    assert s["running"] is False
    assert s["port"] == config.PORT + 1 == share.SHARE_PORT
    assert s["urls"] == []                       # sin servidor, sin URLs
    assert isinstance(s["tailscale"], bool)


def test_qr_svg_is_svg():
    svg = share.qr_svg("http://192.168.1.20:8978")
    assert "<svg" in svg and "svg" in svg[:200].lower()


def test_lan_ips_returns_list():
    ips = share._lan_ips()
    assert isinstance(ips, list)
    assert all("127." not in ip for ip in ips)   # nunca loopback
