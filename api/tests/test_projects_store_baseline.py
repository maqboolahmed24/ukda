from app.projects.store import ProjectStore


def test_baseline_policy_snapshot_hash_is_stable_for_same_seeded_rules() -> None:
    first = ProjectStore._baseline_snapshot_hash()
    second = ProjectStore._baseline_snapshot_hash()

    assert first == second
    assert len(first) == 64

