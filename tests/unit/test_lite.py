from random import randrange
import pytest

from tion_btle.light_family import TionLiteFamily


def generator(_len: int) -> bytearray:
    """Generate random bytes bytearray wit len size."""
    result = []
    for i in range(_len):
        result.append(randrange(0xFF))
    return bytearray(result)


@pytest.mark.parametrize(
    "target_length",
    [0, 1, 10, 30, 90]
)
def test_generator(target_length):
    assert len(generator(target_length)) == target_length


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(generator(10), id="len=10"),
        pytest.param(generator(20), id="len=20"),
        pytest.param(generator(30), id="len=30"),
        pytest.param(generator(40), id="len=40"),
        pytest.param(generator(50), id="len=50"),
    ]
)
def test_split_command(command: bytearray):
    tion = TionLiteFamily(mac="")
    splitted = tion.split_command(request=command.copy())
    joined = bytearray()

    for i in range(len(splitted)):
        assert len(splitted[i]) <= 20
        if i == 0:
            if len(command) <= 20:
                assert splitted[i][0] == TionLiteFamily.SINGLE_PACKET_ID
            else:
                assert splitted[i][0] == TionLiteFamily.FIRST_PACKET_ID
        elif i == len(splitted)-1:
            assert splitted[i][0] == TionLiteFamily.END_PACKET_ID
        else:
            assert splitted[i][0] == TionLiteFamily.MIDDLE_PACKET_ID
        joined += splitted[i][1:]

    assert command[1:] == joined


