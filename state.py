# owner should be the members contract

S = Hash()


@export
def get_state():
    assert_owner()
    return S


@export
def change_owner(new_owner: str):
    assert_owner()
    owner.set(new_owner)


def assert_owner():
    assert ctx.caller == owner.get(), 'Only owner can call!'