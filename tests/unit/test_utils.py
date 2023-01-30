from unittest.mock import Mock

from proton.vpn.app.gtk.utils import glib
from proton.vpn.app.gtk.utils.search import normalize
from tests.unit.utils import process_gtk_events


def test_idle_add_once():
    mock = Mock()
    mock.return_value = True

    glib.idle_add_once(mock, "arg1", "arg2")

    process_gtk_events()

    mock.assert_called_once_with("arg1", "arg2")


def test_normalize():
    input_string = "CH-PT#1 "
    normalized_string = normalize(input_string)
    assert normalized_string == "ch-pt#1"
