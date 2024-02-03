# -*- coding: utf-8 -*-
#-------------------------------------------------
#-- osm map importer
#--
#-- microelly 2016 v 0.4
#--
#-- GNU Lesser General Public License (LGPL)
#-------------------------------------------------
'''import data from openstreetmap'''


#http://api.openstreetmap.org/api/0.6/map?bbox=11.74182,50.16413,11.74586,50.16561
#http://api.openstreetmap.org/api/0.6/way/384013089
#http://api.openstreetmap.org/api/0.6/node/3873106739

#\cond
import os
import FreeCAD
import FreeCADGui
import Draft
from PySide2 import QtGui, QtCore, QtWidgets
import NetworkManager
from NetworkManager import HAVE_QTNETWORK, InitializeNetworkManager

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


def importOSM(e): 
    FreeCAD.Console.PrintLog(f"importOSM({e})\n")


class _CommandImport:

    "the GeoData Import command definition"

    def GetResources(self):
        return {'Pixmap'  : 'GeoData_Import',
                'MenuText': QT_TRANSLATE_NOOP("GeoData","Import Geo Data."),
                'Accel': "I, O",
                'ToolTip': QT_TRANSLATE_NOOP("GeoData","Import Geo data.")}

    def IsActive(self):
        FreeCAD.Console.PrintLog(f"_CommandImport.IsActive == {not FreeCAD.ActiveDocument is None}.\n")
        return not FreeCAD.ActiveDocument is None

    def Activated(self):
        InitializeNetworkManager()
        self.connection_checker = ConnectionChecker()
        self.connection_checker.success.connect(self.launch)
        self.connection_checker.failure.connect(self.network_connection_failed)
        self.connection_checker.start()        
        # If it takes longer than a half second to check the connection, show a message:
        self.connection_message_timer = QtCore.QTimer.singleShot(
            500, self.show_connection_check_message
        )

    def launch(self) -> None:
        """Shows the GeoData Import UI"""
        self.dialog = FreeCADGui.PySideUic.loadUi(
            os.path.join(os.path.dirname(__file__), "GeoDataImportDialog.ui")
        )

        # restore window geometry from stored state
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Addons")
        w = pref.GetInt("WindowWidth", 800)
        h = pref.GetInt("WindowHeight", 600)
        self.dialog.resize(w, h)
        self.dialog.setWindowIcon(QtGui.QIcon(":/GeoData_Import.svg"))


    # def run_alex(self):
    #     '''imports Berlin Aleancderplatz'''
    #     self.run(52.52128,l=13.41646)

    # def run_paris(self):
    #     '''imports Paris'''
    #     self.run(48.85167,2.33669)

    # def run_tokyo(self):
    #     '''imports Tokyo near tower'''
    #     self.run(35.65905,139.74991)

    # def run_spandau(self):
    #     '''imports Berlin Spandau'''
    #     self.run(52.508,13.18)

    # def run_co2(self):
    #     '''imports  Coburg Univerity and School'''
    #     self.run(50.2631171, 10.9483)

    # def run_sternwarte(self):
    #     '''imports Sonneberg Neufang observatorium'''
    #     self.run(50.3736049,11.191643)


        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Select a location ..."))
        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Sonneberg Neufang observatorium"))
        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Coburg university and school"))
        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Berlin Alexanderplatz/Haus des Lehrers"))
        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Berlin Spandau"))
        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Paris Rue de Seine"))
        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Tokyo near tower"))
        self.dialog.locationPresets.currentIndexChanged.connect(self.setLocationPreset)

        self.dialog.buttonImport.setIcon(
            QtGui.QIcon.fromTheme("edit-undo", QtGui.QIcon(":/Resources/icons/GeoData_Import.svg"))
        )
        # center the dialog over the FreeCAD window
        mw = FreeCADGui.getMainWindow()
        self.dialog.move(
            mw.frameGeometry().topLeft()
            + mw.rect().center()
            - self.dialog.rect().center()
        )
        self.dialog.exec_()

    def show_connection_check_message(self):
        if not self.connection_checker.isFinished():
            self.connection_check_message = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Information,
                QT_TRANSLATE_NOOP("GeoData", "Checking connection"),
                QT_TRANSLATE_NOOP("GeoData", "Checking for connection to GitHub..."),
                QtWidgets.QMessageBox.Cancel,
            )
            self.connection_check_message.buttonClicked.connect(
                self.cancel_network_check
            )
            self.connection_check_message.show()

    def cancel_network_check(self, button):
        if not self.connection_checker.isFinished():
            self.connection_checker.success.disconnect(self.launch)
            self.connection_checker.failure.disconnect(self.network_connection_failed)
            self.connection_checker.requestInterruption()
            self.connection_checker.wait(500)
            self.connection_check_message.close()
        
    def network_connection_failed(self, message: str) -> None:
        # This must run on the main GUI thread
        if hasattr(self, "connection_check_message") and self.connection_check_message:
            self.connection_check_message.close()
        if HAVE_QTNETWORK:
            QtWidgets.QMessageBox.critical(
                None, QT_TRANSLATE_NOOP("GeoData", "Connection failed"), message
            )
        else:
            QtWidgets.QMessageBox.critical(
                None,
                QT_TRANSLATE_NOOP("GeoData", "Missing dependency"),
                QT_TRANSLATE_NOOP("GeoData", "Could not import QtNetwork -- see Report View for details. Addon Manager unavailable.",),
            )

    def setLocationPreset(self, i):
        """Simple callback for the interactive mode gui widget to set location preset."""
        if i == 0:
            self.LocationPreset = None
            del FreeCAD.LastLocationPreset
        elif i <= len(self.LocationPresets):
            self.LocationPreset = self.LocationPresets[i-1]
            #FreeCAD.LastLocationPreset = self.LocationPreset.Name
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        pref.SetInt("LocationPreset", i)

    def setLatitude(self,d):
        """Simple callback for the interactive mode gui widget to set Latitude."""
        self.Latitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Latitude",d)

    def setLongitude(self,d):
        """Simple callback for the interactive mode gui widget to set Longitude."""
        self.Longitude = d
        #self.tracker.longitude(d)
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Longitude",d)

class ConnectionChecker(QtCore.QThread):

    success = QtCore.Signal()
    failure = QtCore.Signal(str)

    def __init__(self):
        QtCore.QThread.__init__(self)

    def run(self):
        FreeCAD.Console.PrintLog("Checking network connection...\n")
        url = "https://www.openstreetmap.org"
        result = NetworkManager.AM_NETWORK_MANAGER.blocking_get(url)
        if QtCore.QThread.currentThread().isInterruptionRequested():
            return
        if not result:
            self.failure.emit(
                translate(
                    "GeoData",
                    "Unable to read data from openstreetmap.org: check your internet connection and proxy settings and try again.",
                )
            )
            return
        self.success.emit()

if FreeCAD.GuiUp:
    FreeCAD.Console.PrintLog('addCommand(GeoData_Import)\n')
    FreeCADGui.addCommand('GeoData_Import', _CommandImport())
