from brain.memory import ConversationMemory


def test_memory_truncates_to_last_10_exchanges() -> None:
    memory = ConversationMemory(max_exchanges=10)
    for i in range(12):
        memory.add(user=f"u{i}", assistant=f"a{i}")

    history = memory.history()
    assert len(history) == 10
    assert history[0].user == "u2"
    assert history[-1].assistant == "a11"
