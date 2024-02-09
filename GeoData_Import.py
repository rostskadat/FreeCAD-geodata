# -*- coding: utf-8 -*-
#-------------------------------------------------
#-- osm map importer
#--
#-- microelly 2016 v 0.4
#--
#-- GNU Lesser General Public License (LGPL)
#-------------------------------------------------
'''The FreeCADGui Command to import Geo Data'''


#http://api.openstreetmap.org/api/0.6/map?bbox=11.74182,50.16413,11.74586,50.16561
#http://api.openstreetmap.org/api/0.6/way/384013089
#http://api.openstreetmap.org/api/0.6/node/3873106739

#\cond
import json
import os
import re
import FreeCAD
import FreeCADGui
import WebGui

from PySide2 import QtGui, QtCore, QtWidgets
from NetworkManager import HAVE_QTNETWORK, InitializeNetworkManager
from ConnectionChecker import ConnectionChecker

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

GCP_ELEVATION_API_KEY = None

# Greenwich
STD_ZOOM = 17
STD_LATITUDE = 51.47786
STD_LONGITUDE = 0.0

class GeoData_Import:
    """GeoData Import command definition

    Returns:
        _type_: _description_
    """
    def GetResources(self):
        __dirname__ = os.path.join(FreeCAD.getResourceDir(), "Mod", "FreeCAD-geodata")
        if not os.path.isdir(__dirname__):
            __dirname__ = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "FreeCAD-geodata")
        if not os.path.isdir(__dirname__):
            FreeCAD.Console.PrintError("Failed to determine the install location of the GeoData workbench. Check your installation.\n")
        return {'Pixmap'  : os.path.join(__dirname__, "Resources", "icons", "GeoData_Import.svg"),
                'MenuText': QT_TRANSLATE_NOOP("GeoData","Import Geo Data."),
                'Accel': "I, O",
                'ToolTip': QT_TRANSLATE_NOOP("GeoData","Import Geo data.")}

    def IsActive(self):
        return not FreeCAD.ActiveDocument is None

    def Activated(self):
        InitializeNetworkManager()
        self.connection_checker = ConnectionChecker("https://www.openstreetmap.org")
        self.connection_checker.success.connect(self.launch)
        self.connection_checker.failure.connect(self.network_connection_failed)
        self.connection_checker.start()
        # If it takes longer than a half second to check the connection, show a message:
        self.connection_message_timer = QtCore.QTimer.singleShot(
            500, self.show_connection_check_message
        )

    def launch(self) -> None:
        """Shows the GeoData Import UI"""
        self.Browser = None
        self.Zoom = STD_ZOOM
        self.Latitude = STD_LATITUDE
        self.Longitude = STD_LONGITUDE
        self.Altitude = 0.0
        self.CsvContent = f"{STD_LATITUDE};{STD_LONGITUDE}"
        self.CsvFilename = None
        self.GpxFilename = None
        self.EmirFilename = None
        self.LidarFilename = None

        self.dialog = FreeCADGui.PySideUic.loadUi(
            os.path.join(os.path.dirname(__file__), "GeoData_Import.ui")
        )

        self.dialog.tabs.currentChanged.connect(self.onTabBarClicked)
        self.dialog.osmLocationPresets.currentIndexChanged.connect(self.onOsmLocationPresetSelected)
        self.dialog.osmOpenBrowserWindow.clicked.connect(self.onOsmOpenBrowserWindow)
        self.dialog.osmGetCoordFromBrowser.clicked.connect(self.onOsmGetCoordFromBrowser)
        self.dialog.osmUrl.textChanged.connect(self.onOsmUrlChanged)
        self.dialog.osmZoom.valueChanged.connect(self.onOsmZoomChanged)
        self.dialog.osmLatitude.valueChanged.connect(self.onOsmLatitudeChanged)
        self.dialog.osmLongitude.valueChanged.connect(self.onOsmLongitudeChanged)

        self.dialog.csvLatitude.valueChanged.connect(self.onCsvLatitudeChanged)
        self.dialog.csvLongitude.valueChanged.connect(self.onCsvLongitudeChanged)
        self.dialog.csvSelectFile.clicked.connect(self.onCsvSelectFile)
        self.dialog.csvFilename.textChanged.connect(self.onCsvFilenameChanged)

        self.dialog.gpxLatitude.valueChanged.connect(self.onGpxLatitudeChanged)
        self.dialog.gpxLongitude.valueChanged.connect(self.onGpxLongitudeChanged)
        self.dialog.gpxAltitude.valueChanged.connect(self.onGpxAltitudeChanged)
        self.dialog.gpxSelectFile.clicked.connect(self.onGpxSelectFile)
        self.dialog.gpxFilename.textChanged.connect(self.onGpxFilenameChanged)

        self.dialog.emirSelectFile.clicked.connect(self.onEmirSelectFile)
        self.dialog.emirFilename.textChanged.connect(self.onEmirFilenameChanged)

        self.dialog.lidarSelectFile.clicked.connect(self.onLidarSelectFile)
        self.dialog.lidarFilename.textChanged.connect(self.onLidarFilenameChanged)

        self.dialog.btnImport.clicked.connect(self.onImport)
        self.dialog.btnClose.clicked.connect(self.onClose)
        self.dialog.progressBar.setVisible(False)
        self.dialog.status.setVisible(False)

        # restore window geometry from stored state
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        self.dialog.resize(pref.GetInt("WindowWidth", 800), pref.GetInt("WindowHeight", 600))
        self.dialog.tabs.setCurrentIndex(pref.GetInt("ImportDialogLastOpenTab", 0))
        self.dialog.setWindowIcon(QtGui.QIcon(":Resources/icons/GeoData_Import.svg"))

        global GCP_ELEVATION_API_KEY
        GCP_ELEVATION_API_KEY = pref.GetString("GCP_ELEVATION_API_KEY")

        self.dialog.osmLocationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Select a location ..."))
        self.LocationPresets = []
        resource_dir = FreeCADGui.activeWorkbench().ResourceDir
        with open(os.path.join(resource_dir, 'Presets', 'osm.json')) as f:
            presets = json.load(f)
            for preset in presets["osm"]:
                self.LocationPresets.append(preset)
                self.dialog.osmLocationPresets.addItem(preset['name'])
        self.dialog.osmLocationPresets.setCurrentIndex(pref.GetInt("LocationPresetIndex", 0))

        self.updateCsvFields()
        self.updateCsvCoordinates()
        self.updateGpxFields()
        self.updateGpxCoordinates()
        self.updateEmirFields()

        self.dialog.btnImport.setIcon(
            QtGui.QIcon.fromTheme("edit-undo", QtGui.QIcon(":/Resources/icons/GeoData_Import.svg"))
        )
        # center the dialog over the FreeCAD window
        mw = FreeCADGui.getMainWindow()
        self.dialog.move(
            mw.frameGeometry().topLeft()
            + mw.rect().center()
            - self.dialog.rect().center()
        )
        # Non-modal
        self.dialog.show()

    def show_connection_check_message(self):
        if not self.connection_checker.isFinished():
            self.connection_check_message = QtWidgets.QMessageBox(
                QtWidgets.QMessageBox.Information,
                QT_TRANSLATE_NOOP("GeoData", "Checking connection"),
                QT_TRANSLATE_NOOP("GeoData", "Checking for connection to Internet..."),
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

    def onTabBarClicked(self, i):
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        pref.SetInt("ImportDialogLastOpenTab", i)

    def onOsmLocationPresetSelected(self, i):
        """Callback when the Location Preset Combo has changed

        Args:
            i (int): The selected index of the Location Preset Combo
        """
        if i == 0:
            self.LocationPreset = None
            if hasattr(FreeCAD, "LastLocationPreset"):
                del FreeCAD.LastLocationPreset
        elif i <= len(self.LocationPresets):
            self.LocationPreset = self.LocationPresets[i-1]
            FreeCAD.LastLocationPreset = self.LocationPreset['name']
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        pref.SetInt("LocationPresetIndex", i)
        if self.LocationPreset:
            self.Zoom = int(self.LocationPreset['zoom'])
            self.Latitude = float(self.LocationPreset['latitude'])
            self.Longitude = float(self.LocationPreset['longitude'])
        self.updateBrowserUrl()
        self.updateOsmUrl()
        self.updateOsmCoordinates()

    def onOsmOpenBrowserWindow(self):
        """Open a Browser windows in order to for the User to navigate to
        the desired map location
        """
        if not self.Browser:
            self.Browser = WebGui.openBrowserWindow(f"OSM")
        try:
            self.updateBrowserUrl()
        except RuntimeError as e:
            # If the User has deleted the browser window we have this error
            self.Browser = None
            self.onOsmOpenBrowserWindow()

    def onOsmGetCoordFromBrowser(self):
        """Return the URL of the browser window and set the URL field
        accordingly.

        NOTE: Updating the URL field will in turn trigger the update of
        the different other components (zoom, latitude, longitude)

        Returns:
            str: the browser URL
        """
        if not hasattr(self, "Browser"):
            return
        url = self.Browser.url()
        (ok, zoom, latitude, longitude) = self._extract_coordinate_from_url(url)
        if ok:
            self.Zoom = zoom
            self.Latitude = latitude
            self.Longitude = longitude
        self.updateOsmUrl()
        self.updateOsmCoordinates()

    def onOsmUrlChanged(self, url):
        """Callback when the URL field has changed

        Args:
            url (str): The url to parse
        """
        (ok, zoom, latitude, longitude) = self._extract_coordinate_from_url(url)
        if ok:
            self.Zoom = zoom
            self.Latitude = latitude
            self.Longitude = longitude
        self.updateBrowserUrl()
        self.updateOsmCoordinates()

    def onOsmZoomChanged(self,i):
        """Callback when the Zoom field has changed

        NOTE: as this callback can be called from the direct change of the
        control or through a change of a related control, we check that both
        value match and refresh the browser window if needed.

        Args:
            i (int): the zoom
        """
        self.Zoom = int(i) if i else STD_ZOOM
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetInt("Zoom", self.Zoom)
        self.updateBrowserUrl()
        self.updateOsmUrl()
        self.updateOsmCoordinates()

    def onOsmLatitudeChanged(self,d):
        """Callback to set the Latitude

        NOTE: as this callback can be called from the direct change of the
        control or through a change of a related control, we check that both
        value match and refresh the browser window if needed.

        Args:
            d (float): the latitude
        """
        self.Latitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Latitude", self.Latitude)
        self.updateBrowserUrl()
        self.updateOsmUrl()
        self.updateOsmCoordinates()

    def onOsmLongitudeChanged(self,d):
        """Callback to set the Longitude

        NOTE: as this callback can be called from the direct change of the
        control or through a change of a related control, we check that both
        value match and refresh the browser window if needed.

        Args:
            d (float): the longitude
        """
        self.Longitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Longitude", self.Longitude)
        self.updateBrowserUrl()
        self.updateOsmUrl()
        self.updateOsmCoordinates()

    def onCsvLatitudeChanged(self,d):
        """Callback to set the Latitude

        Args:
            d (float): the latitude
        """
        self.Latitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Latitude", self.Latitude)
        self.updateCsvCoordinates()

    def onCsvLongitudeChanged(self,d):
        """Callback to set the Longitude

        Args:
            d (float): the longitude
        """
        self.Longitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Longitude", self.Longitude)
        self.updateCsvCoordinates()

    def onCsvSelectFile(self):
        """Callback to open the file picker
        """
        self._onSelectFile("CSV Files (*.csv *.tsv)", "LastCsvSelectDirname", "CsvFilename", _CommandImport.updateCsvFields)
        if os.path.isfile(self.CsvFilename):
            with open(self.CsvFilename, "r") as f:
                self.CsvContent = f.read()
            self.updateCsvFields()

    def onCsvFilenameChanged(self, filename):
        self._onFilenameChanged(filename, "LastCsvSelectDirname", "CsvFilename", _CommandImport.updateCsvFields)
        if os.path.isfile(self.CsvFilename):
            with open(self.CsvFilename, "r") as f:
                self.CsvContent = f.read()
            self.updateCsvFields()

    def onCsvContent(self, text):
        self.CsvContent = text

    def onGpxLatitudeChanged(self,d):
        """Callback to set the Latitude

        Args:
            d (float): the latitude
        """
        self.Latitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Latitude", self.Latitude)
        self.updateGpxCoordinates()

    def onGpxLongitudeChanged(self,d):
        """Callback to set the Longitude

        Args:
            d (float): the longitude
        """
        self.Longitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Longitude", self.Longitude)
        self.updateGpxCoordinates()

    def onGpxAltitudeChanged(self,d):
        """Callback to set the altitude

        Args:
            d (float): the altitude
        """
        self.Altitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Altitude", self.Altitude)
        self.updateGpxCoordinates()

    def onGpxSelectFile(self):
        """Callback to open the file picker
        """
        self._onSelectFile("GPX Files (*.gpx)", "LastGpxSelectDirname", "GpxFilename", _CommandImport.updateGpxFields)

    def onGpxFilenameChanged(self, filename):
        """Callback when the file has changed
        """
        self._onFilenameChanged(filename, "LastGpxSelectDirname", "GpxFilename", _CommandImport.updateGpxFields)

    def onEmirSelectFile(self):
        """Callback to open the file picker
        """
        self._onSelectFile("EMIR Files (*.dat)", "LastEmirSelectDirname", "EmirFilename", _CommandImport.updateEmirFields)

    def onEmirFilenameChanged(self, filename):
        """Callback when the file has changed
        """
        self._onFilenameChanged(filename, "LastEmirSelectDirname", "EmirFilename", _CommandImport.updateEmirFields)

    def onLidarSelectFile(self):
        """Callback to open the file picker
        """
        self._onSelectFile("LIDAR Files (*.las)", "LastLidarSelectDirname", "LidarFilename", _CommandImport.updateLidarFields)

    def onLidarFilenameChanged(self, lidar_filename):
        """Callback when the file has changed
        """
        self._onFilenameChanged(lidar_filename, "LastLidarSelectDirname", "LidarFilename", _CommandImport.updateLidarFields)

    def _onSelectFile(self, file_type, pref_name, attr_name, upd_function):
        """Call the file picker for the specified file.

        Args:
            file_type (str): The file type description used in the file picker UI
            pref_name (str): The preference name to set to remember the last user path
            attr_name (str): The attribute name to set on succeful file selection
            upd_function (func): The argument less function to call when the file has been updated
        """

        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        home_dir = os.path.expanduser('~')
        file_dirname = pref.GetString(pref_name, home_dir)
        if not os.path.isdir(file_dirname):
            file_dirname = home_dir
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.dialog,
            QT_TRANSLATE_NOOP("GeoData", "Import File"),
            file_dirname,
            QT_TRANSLATE_NOOP("GeoData", file_type)
        )
        pref.SetString(pref_name, os.path.dirname(filename))
        if os.path.isfile(filename):
            setattr(self, attr_name, filename)
            upd_function(self)

    def _onFilenameChanged(self, filename, pref_name, attr_name, upd_function):
        if os.path.isfile(filename):
            pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
            pref.SetString(pref_name, os.path.dirname(filename))
            setattr(self, attr_name, filename)
            upd_function(self)

    def onImport(self):
        self.dialog.progressBar.setVisible(True)
        self.dialog.status.setVisible(True)
        current_tab = self.dialog.tabs.currentIndex()
        if current_tab == 0:
            # OSM
            global GCP_ELEVATION_API_KEY
            if self.dialog.osmDownloadAltitude.isChecked() and not GCP_ELEVATION_API_KEY:
                FreeCAD.Console.PrintWarning(f"Altitude information not available because no GCP API key provided.\n")
            import geodata
            geodata.import_osm(
                self.Latitude,
                self.Longitude,
                self.Zoom,
                GCP_ELEVATION_API_KEY and self.dialog.osmDownloadAltitude.isChecked(),
                self.onImportProgress)
        elif current_tab == 1:
            # CSV
            import geodata
            geodata.import_csv(
                self.Latitude,
                self.Longitude,
                self.CsvContent,
                self.dialog.csvHasHeaders.isChecked(),
                self.onImportProgress)
        elif current_tab == 2:
            # GPX
            import geodata
            geodata.import_gpx(
                self.Latitude,
                self.Longitude,
                self.Altitude,
                self.GpxFilename,
                self.dialog.gpxGenerateDataNodes.isChecked(),
                self.onImportProgress)
        elif current_tab == 4:
            # EMIR
            import geodata
            geodata.import_emir(
                self.EmirFilename,
                self.onImportProgress)
        elif current_tab == 8:
            # LIDAR
            import geodata
            geodata.import_lidar(
                self.LidarFilename,
                self.onImportProgress)
        else:
            self.dialog.status.setVisible(False)
        self.dialog.progressBar.setVisible(False)

    def onClose(self):
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        pref.SetInt("WindowWidth", self.dialog.frameSize().width())
        pref.SetInt("WindowHeight", self.dialog.frameSize().height())
        self.dialog.done(0)

    def onImportProgress(self, progress, status):
        if FreeCAD.GuiUp:
            self.dialog.progressBar.setValue(progress)
            if status:
                self.dialog.status.setText(status)
            FreeCADGui.updateGui()

    def updateBrowserUrl(self):
        """Update both the browser URL and the URL field with the zoom,
        latitude and longitude.
        """
        url = f"https://www.openstreetmap.org/#map={self.Zoom}/{self.Latitude}/{self.Longitude}"
        if self.Browser and self.Browser.url() != url:
            self.Browser.load(url)

    def updateOsmUrl(self):
        """Update both the browser URL and the URL field with the zoom,
        latitude and longitude.
        """
        url = f"https://www.openstreetmap.org/#map={self.Zoom}/{self.Latitude}/{self.Longitude}"
        self.dialog.osmUrl.setText(url)

    def updateOsmCoordinates(self):
        """Update the dialog coordinate fields with the the zoom, latitude
        and longitude.
        """
        self.dialog.osmZoom.setValue(self.Zoom)
        self.dialog.osmLatitude.setValue(self.Latitude)
        self.dialog.osmLongitude.setValue(self.Longitude)

    def updateCsvFields(self):
        """Update the dialog filename.
        """
        self.dialog.csvFilename.setText(self.CsvFilename)
        self.dialog.csvContent.setPlainText(self.CsvContent)

    def updateCsvCoordinates(self):
        """Update the dialog coordinate fields with the the latitude
        and longitude.
        """
        self.dialog.csvLatitude.setValue(self.Latitude)
        self.dialog.csvLongitude.setValue(self.Longitude)

    def updateGpxFields(self):
        """Update the dialog filename.
        """
        self.dialog.gpxFilename.setText(self.GpxFilename)

    def updateGpxCoordinates(self):
        """Update the dialog coordinate fields with the the latitude
        and longitude.
        """
        self.dialog.gpxLatitude.setValue(self.Latitude)
        self.dialog.gpxLongitude.setValue(self.Longitude)
        self.dialog.gpxAltitude.setValue(self.Altitude)

    def updateEmirFields(self):
        """Update the dialog filename.
        """
        self.dialog.emirFilename.setText(self.EmirFilename)

    def updateLidarFields(self):
        """Update the dialog filename.
        """
        self.dialog.lidarFilename.setText(self.LidarFilename)

    def _extract_coordinate_from_url(self, url):
        pattern = re.compile(r'https?://www.openstreetmap.org/#map=(\d+)/([\d.-]+)/([\d.-]+)')
        matches  = re.findall(pattern, url)
        if len(matches) == 1:
            (zoom, latitude, longitude) = matches[0]
            return True, int(zoom), float(latitude), float(longitude)
        pattern = re.compile(r'https://www.google.com/maps/@([\d.-]+),([\d.-]+),([\d.-]+)z?')
        matches  = re.findall(pattern, url)
        if len(matches) == 1:
            (latitude, longitude, zoom) = matches[0]
            return True, int(zoom), float(latitude), float(longitude)
        pattern = re.compile(r'https://www.bing.com/maps/\?cp=([\d.-]+)~([\d.-]+)&lvl([\d.]+)')
        matches  = re.findall(pattern, url)
        if len(matches) == 1:
            (latitude, longitude, zoom) = matches[0]
            return True, int(zoom), float(latitude), float(longitude)
        pattern = re.compile(r'https://wego.here.com/\?map=([\d.-]+),([\d.-]+),([\d.]+).*')
        matches  = re.findall(pattern, url)
        if len(matches) == 1:
            (latitude, longitude, zoom) = matches[0]
            return True, int(zoom), float(latitude), float(longitude)
        return False, None, None, None

if FreeCAD.GuiUp:
    FreeCADGui.addCommand('GeoData_Import', GeoData_Import())
