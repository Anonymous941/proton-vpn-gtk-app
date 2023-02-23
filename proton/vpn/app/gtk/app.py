"""
This module defines the main App class.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional

from gi.repository import GObject, Gtk

from proton.vpn.app.gtk.controller import Controller
from proton.vpn import logging
from proton.vpn.app.gtk.widgets.main.tray_indicator import TrayIndicator, TrayIndicatorNotSupported
from proton.vpn.app.gtk.widgets.main.main_window import MainWindow

logger = logging.getLogger(__name__)


class App(Gtk.Application):
    """
    Proton VPN GTK application.

    It inherits a set of common app functionality from Gtk.Application:
    https://docs.gtk.org/gtk3/class.Application.html.

    For example:
     - It guarantees that only one instance of the application is
       allowed (new app instances exit immediately if there is already
       an instance running).
     - It manages the windows associated to the application. The application
       exits automatically when the last one is closed.
     - It allows desktop shell integration by exporting actions and menus.
    """

    def __init__(
            self,
            thread_pool_executor: ThreadPoolExecutor,
            controller: Controller = None
    ):
        super().__init__(application_id="proton.vpn.app.gtk")
        logger.info(f"{self=}", category="APP", event="PROCESS_START")
        self._controller = controller or Controller(
            thread_pool_executor=thread_pool_executor
        )
        self.window = None
        self.tray_indicator = None
        self._signal_connect_queue = []

    def do_activate(self):  # pylint: disable=W0221
        """
        Method called by Gtk.Application when the default first window should
        be shown to the user.
        """
        if not self.window:
            self.window = MainWindow(self, self._controller)
            # Process signal connection requests asap.
            self._process_signal_connect_queue()
            # Windows are associated with the application like this.
            # When the last one is closed, the application shuts down.
            self.add_window(self.window)
            # The behaviour of the button to close the window is configured
            # depending on whether the tray indicator is shown or not.
            self.tray_indicator = self._build_tray_indicator_if_possible(
                self._controller, self.window
            )
            self.window.configure_close_button_behaviour(
                tray_indicator_enabled=(self.tray_indicator is not None)
            )
            self.window.show_all()

        self.window.present()
        self.emit("app-ready")

    @property
    def error_dialogs(self) -> List[Gtk.MessageDialog]:
        """
        Gives access to currently opened error message dialogs. This method
        was made available for testing purposes.
        :return: The list of currently opened error message dialogs.
        """
        return self.window.main_widget.notifications.error_dialogs  # pylint: disable=W0212

    @GObject.Signal(name="app-ready")
    def app_ready(self):
        """Signal emitted when the app is ready for interaction."""

    def queue_signal_connect(self, signal_spec: str, callback: Callable):
        """Queues a request to connect a callback to a signal.

        This method should only be used by tests that need to connect a
        callback to a widget signal before the app window, which contains
        all app widgets, has been created.

        Note that the window is not created in the Gtk.Application constructor
        but when the app receives the ``activate`` signal. Fore more info:
        https://wiki.gnome.org/HowDoI/GtkApplication

        While testing, we might want to use this method to make sure that we
        are able to connect our callback **before** the signal has already
        fired. This method allows the app to queue a
        request to connect a callback to one of the widgets' signals. The queued
        request will be processed as soon as the app window (with all its
        children widgets) have been created.

        Usage example:
        .. code-block:: python
            with ThreadPoolExecutor() as thread_pool_executor:
                app = App(thread_pool_executor)
                app.queue_signal_connect(
                    signal_spec="main_widget.vpn_widget.servers_widget::server-list-ready",
                    callback=my_func
                )
                sys.exit(app.run(sys.argv))

        The widget/signal the callback should be connected to is specified
        with the ``signal_spec`` parameter, which should have the following
        form: ``widget_attr.[widget_attr.]::signal-name``.

        ``widget_attr`` refers to a widget attribute from the app window
        which, in turn, can contain other widget attributes. The ``signal-name``
        after the double colon is the name of the signal to attach the callback
        to.

        So in the example above, the resulting action once the app window is
        created will be to run the following code:

        .. code-block:: python
            app.window.main_widget.vpn_widget.servers.connect(
                "server-list-ready", my_func
            )

        :param signal_spec: signal specification.
        :param callback: Callback to connect to the specified signal.
        """
        self._signal_connect_queue.append((signal_spec, callback))
        if self.window:
            # if the window already exist then the queue is processed instantly
            self._process_signal_connect_queue()

    def _process_signal_connect_queue(self):
        """Processes all signal connection requests queued by calling
        ``queue_signal_connect``."""
        for _ in range(len(self._signal_connect_queue)):
            signal_spec, callback = self._signal_connect_queue.pop(0)
            widget_path, signal_name = signal_spec.split("::")
            obj = self.window
            for widget_path_segment in widget_path.split("."):
                obj = getattr(obj, widget_path_segment)

            assert isinstance(obj, GObject.Object), \
                f"{type(obj)} does not inherit from GObject.Object."
            obj.connect(signal_name, callback)

    @staticmethod
    def _build_tray_indicator_if_possible(
        controller: Controller, main_window: MainWindow
    ) -> Optional[TrayIndicator]:
        """Returns a tray indicator instance if the required dependencies
        are met, otherwise None is returned instead. """
        try:
            return TrayIndicator(controller, main_window)
        except TrayIndicatorNotSupported as error:
            logger.info(f"{error}")
            return None
