from riskmesh.attestation import sign_decision, verify_decision


def test_signed_decision_detects_tampering(monkeypatch):
    monkeypatch.setenv("RISK_MESH_SIGNING_KEY", "demo-signing-key-with-more-than-32-characters")
    envelope = sign_decision({"tenant": "alpha", "score": 70})
    assert verify_decision(envelope)
    envelope["document"]["payload"]["score"] = 1
    assert not verify_decision(envelope)
