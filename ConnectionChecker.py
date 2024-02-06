import FreeCAD
import NetworkManager
from PySide2 import QtGui, QtCore, QtWidgets

if FreeCAD.GuiUp:
    import FreeCADGui
    from draftutils.translate import translate
    from PySide.QtCore import QT_TRANSLATE_NOOP
else:
    # \cond
    def translate(ctxt,txt):
        return txt
    def QT_TRANSLATE_NOOP(ctxt,txt):
        return txt
    # \endcond

class ConnectionChecker(QtCore.QThread):
    """Helper class to enforce a functioning Internet connection before proceeding

    Args:
        QtCore (_type_): _description_
    """

    success = QtCore.Signal()
    failure = QtCore.Signal(str)

    def __init__(self, url):
        QtCore.QThread.__init__(self)
        self.url = url

    def run(self):
        FreeCAD.Console.PrintLog(f"Checking network connection to {self.url} ...\n")
        result = NetworkManager.AM_NETWORK_MANAGER.blocking_get(self.url)
        if QtCore.QThread.currentThread().isInterruptionRequested():
            return
        if not result:
            self.failure.emit(
                translate(
                    "GeoData",
                    f"Unable to read data from {self.url}: check your internet connection and proxy settings and try again.",
                )
            )
            return
        self.success.emit()
