from app import app


def test_generated_passcode_has_no_leading_zero(monkeypatch):
    """Generated passcodes should be six digits without leading zeros."""
    import app as app_module

    def fake_randbelow(limit):
        assert limit == 900000
        return 123

    monkeypatch.setattr(app_module.secrets, "randbelow", fake_randbelow)

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["uploaded_filename"] = "demo.pdf"
            sess["copies"] = 1
            sess["print_type"] = "bw"
            sess["paper_size"] = "a4"
            sess["number_of_pages"] = 1
            sess["total_price"] = 2
            sess["payment_status"] = "paid"

        client.post("/payment")
        with client.session_transaction() as sess:
            passcode = sess["passcode"]

    assert len(passcode) == 6
    assert passcode.isdigit()
    assert not passcode.startswith("0")
