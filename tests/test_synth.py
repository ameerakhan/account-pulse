from pulse import config, synth


def test_generation_is_deterministic():
    a = synth.generate(synth.SynthSpec(seed=3, n_accounts=30))
    b = synth.generate(synth.SynthSpec(seed=3, n_accounts=30))
    for name in a:
        assert a[name].equals(b[name]), name


def test_referential_integrity(built):
    _, _, t = built
    acc = t["accounts"]
    assert acc["account_id"].is_unique
    assert set(acc["hub_id"]) <= set(t["hubs"]["hub_id"])
    assert set(acc["sector_id"]) <= set(t["sectors"]["sector_id"])
    assert set(acc["programme_id"]) <= set(t["programmes"]["programme_id"])
    assert set(t["activities"]["account_id"]) <= set(acc["account_id"])
    assert set(t["activities"]["activity_type"]) <= set(config.ACTIVITY_TYPES)


def test_programmes_belong_to_the_account_hub(built):
    _, _, t = built
    merged = t["accounts"].merge(t["programmes"], on="programme_id", suffixes=("", "_prog"))
    assert (merged["hub_id"] == merged["hub_id_prog"]).all()


def test_no_activity_before_onboarding(built):
    _, _, t = built
    m = t["activities"].merge(t["accounts"][["account_id", "onboarded_date"]], on="account_id")
    assert (m["activity_date"] >= m["onboarded_date"]).all()
