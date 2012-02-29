from gi.repository import Gio, Gtk, Notify

from landscape.ui.model.configuration.proxy import ConfigurationProxy
from landscape.ui.model.configuration.state import ConfigurationModel
from landscape.ui.model.configuration.uisettings import UISettings
from landscape.ui.view.configuration import ClientSettingsDialog
from landscape.ui.controller.configuration import ConfigController


APPLICATION_ID = "com.canonical.landscape-client.settings.ui"


class SettingsApplicationController(Gtk.Application):
    """
    Core application controller for the landscape settings application.
    """

    def __init__(self, args=[]):
        super(SettingsApplicationController, self).__init__(
            application_id=APPLICATION_ID)
        self._args = args
        self.connect("activate", self.setup_ui)

    def get_config(self):
        return ConfigurationProxy()

    def get_uisettings(self):
        return UISettings(Gio.Settings)

    def on_notify(self, message):
        notification = Notify.new(APPLICATION_ID, message, 
                                  Gtk.STOCK_DIALOG_INFO)
        notification.show()

    def on_error(self, message):
        notification = Notify.new(APPLICATION_ID, message, 
                                  Gtk.STOCK_DIALOG_ERROR)
        notification.show()

    def on_succeed(self):
        notification = Notify.new(APPLICATION_ID, "Success", 
                                  Gtk.STOCK_DIALOG_INFO)
        notification.show()

    def on_fail(self):
        notification = Notify.new(APPLICATION_ID, "Fail", 
                                  Gtk.STOCK_DIALOG_ERROR)
        notification.show()

    def setup_ui(self, data=None):
        Notify.init(APPLICATION_ID)
        config = self.get_config()
        uisettings = self.get_uisettings()
        model = ConfigurationModel(proxy=config, proxy_loadargs=self._args,
                                   uisettings=uisettings)
        controller = ConfigController(model)
        controller.load()
        self.settings_dialog = ClientSettingsDialog(controller)
        if self.settings_dialog.run() == Gtk.ResponseType.OK:
            self.settings_dialog.persist()
            controller.register(self.on_notify, self.on_error, self.on_succeed,
                                self.on_fail)
        self.settings_dialog.destroy()
            
