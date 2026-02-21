from state.state_machine import JarvisState, StateController


def test_state_machine_transitions() -> None:
    controller = StateController()
    assert controller.state == JarvisState.STANDBY
    controller.transition_to(JarvisState.ANNOUNCE)
    assert controller.state == JarvisState.ANNOUNCE
