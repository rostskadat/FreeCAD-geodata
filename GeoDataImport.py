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
from io import BytesIO, TextIOWrapper
import json
import os
import re
import time
import FreeCAD
import FreeCADGui
import geodat
from PySide2 import QtGui, QtCore, QtWidgets
from pivy import coin
import WebGui
from NetworkManager import HAVE_QTNETWORK, InitializeNetworkManager
from ConnectionChecker import ConnectionChecker
import xmltodict
from geodat.transversmercator import TransverseMercator
import geodat.inventortools as inventortools
import Part
from datetime import datetime
import requests
from math import cos, radians, pow

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

API_MAX_RETRY = 4
GCP_API_KEY = "AIzaSyCXbsFPJniFW-5WTe9R7sqghyvwlhh8lY8"
GCP_ELEVATION_API_URL = "https://maps.googleapis.com/maps/api/elevation/json"
OSM_API_URL = "https://www.openstreetmap.org/api/0.6/map"
LIST_ELEMENTS = ('node', 'tag', 'way', 'nd', 'relation', 'member')
EARTH_CIRCUMFERENCE = 40075016.686 # in meters
TILE_SIZE_IN_PIXEL = 256

def _set_progress(progressBar, value):
    if FreeCAD.GuiUp and progressBar:
        progressBar.setValue(value)

def _set_status(status, text):
    if FreeCAD.GuiUp and status:
        status.setText(text)
        FreeCADGui.updateGui()

def _get_cache_file(latitude, longitude, osm_zoom):
    """Given a map coordinate, returns the coresponding cache file.

    The cache file will hold the data retrieved from the OSM server at these coordinate.

    Args:
        latitude (float): the latitude
        longitude (float): the longitude
        osm_zoom (int): the OSM zoom level

    Returns:
        str: the cache file name
    """
    return os.path.join(FreeCAD.ConfigGet("UserAppData"), "GeoData", f"{latitude}_{longitude}_{osm_zoom}")

def _download_from_osm(latitude, longitude, osm_zoom, cache_file):
    delta_degree = 360 / pow(2, osm_zoom)

    (latitude_1, longitude_1) = (latitude-delta_degree, longitude-delta_degree)
    (latitude_2, longitude_2) = (latitude+delta_degree, longitude+delta_degree)
    FreeCAD.Console.PrintLog(f"@download p1=({latitude_1},{longitude_1}), p2=({latitude_2},{longitude_2})\n")
    params = {
        "bbox": f"{longitude_1},{latitude_1},{longitude_2},{latitude_2}"
    }
    FreeCAD.Console.PrintLog(f"Downloading OSM data from {OSM_API_URL}, {params} ...\n")
    response = requests.get(OSM_API_URL, params=params)
    if response.status_code == 200:
        cache_dir = os.path.dirname(cache_file)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir)

        FreeCAD.Console.PrintLog(f"Writing OSM data to {cache_file} ...\n")
        buffer = BytesIO()
        with open(cache_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                buffer.write(chunk)
        buffer.seek(0)
        return  TextIOWrapper(buffer, encoding='utf-8').read()
    
    FreeCAD.Console.PrintWarning(f"Failed to download OSM data: {response}\n")
    return None

def _get_altitude(latitude, longitude):
    """Returns the altitude of a single point with latitude and longitude

    Args:
        latitude (float): the latitude
        longitude (float): the longitude

    Returns:
        float: the altitude
    """
    retry = 0
    while retry < API_MAX_RETRY:
        params = {
            "locations":f"{latitude},{longitude}",
            "key": GCP_API_KEY
        }
        response = requests.get(GCP_ELEVATION_API_URL, params=params)
        if response.status_code == 200:
            payload = response.json()
            status = payload['status']
            if status == "OK":
                # elevation is in meter
                return round(payload['results'][0]['elevation']*1000, 2)
            elif status == "OVER_QUERY_LIMIT":
                retry += 1
                time.sleep(5)
            else:
                FreeCAD.Console.PrintWarning(f"Failed to download altitude data: {payload['error_message']}\n")
                break
    return 0

def _get_altitudes(points):
    """Returns the altitude of a list of point (with latitude and longitude)

    Args:
        points (list): the list of point (latitude, longitude)

    Returns:
        dict: the dict of altitude by
    """
    heights = {}
    i=0
    size=len(points)
    while i<size:
        # slice 20 by 20 "lat,long|..."
        ii=0
        if i>0:
            time.sleep(1)
        while ii < 20 and i < size:
            p=points[i]
            ss= p[1]+','+p[2] + '|'
            url += ss
            i += 1
            ii += 1
        params = {
            "locations": ss,
            "key": GCP_API_KEY
        }
        response = requests.get(GCP_ELEVATION_API_URL, params=params)
        if response.status_code == 200:
            payload = response.json()
            status = payload['status']
            if status == "OK":
                # elevation is in meter
                for r in res:
                    key="%0.7f" %(r['location']['lat']) + " " + "%0.7f" %(r['location']['lng'])
                    heights[key]=r['elevation']
            elif status == "OVER_QUERY_LIMIT":
                retry += 1
                time.sleep(5)
            else:
                FreeCAD.Console.PrintWarning(f"Failed to download altitude data: {payload['error_message']}\n")
                break
    return heights

def _setup_area(active_document, bounds):
    minlat = float(bounds['@minlat'])
    minlon = float(bounds['@minlon'])
    maxlat = float(bounds['@maxlat'])
    maxlon = float(bounds['@maxlon'])

    FreeCAD.Console.PrintLog(f"@area p1=({minlat},{minlon}), p2=({maxlat},{maxlon})\n")

    # NOTE: The downloaded are will not be squared...
    tm = TransverseMercator()
    (x1, y1) = tm.fromGeographic(minlat, minlon)
    (x2, y2) = tm.fromGeographic(maxlat, maxlon)
    area = active_document.addObject("Part::Plane", "area")
    area.Length = x2 - x1
    area.Width = y2 - y1
    area.Placement = FreeCAD.Placement(
        FreeCAD.Vector(-(x2 - x1)/2, -(y2 - y1)/2, 0.0),
        FreeCAD.Rotation(0.0, 0.0, 0.0, 1.0)
    )

def _setup_light(active_document):
    # ??? area = FreeCAD.ActiveDocument.ActiveObject
    root = active_document.ActiveObject.ViewObject.RootNode
    light = coin.SoDirectionalLight()
    light.color.setValue(coin.SbColor(0,1,0))
    root.insertChild(light, 0)

def _setup_camera(active_document, osm_zoom):
    height = 1000000
    height = 200*osm_zoom*10000/0.6
    camera_definition = """#Inventor V2.1 ascii
    OrthographicCamera {
        viewportMapping ADJUST_CAMERA
        orientation 0 0 -1.0001  0.001
        nearDistance 0
        farDistance 10000000000
        aspectRatio 100
        focalDistance 1
        position 0 0 999
        height %d
    }
    """ % height
    active_view = FreeCADGui.activeDocument().activeView()
    active_view.setCamera(camera_definition)
    active_view.setCameraType("Orthographic")
    # FreeCADGui.SendMsgToActiveView("ViewFit")

def _add_building(name, feature, building_height):
    extrusion = FreeCAD.ActiveDocument.addObject("Part::Extrusion",name)
    extrusion.Base = feature
    extrusion.ViewObject.ShapeColor = (1.00,1.00,1.00)
    if building_height == 0:
        building_height = 10000
    extrusion.Dir = (0,0,building_height)
    extrusion.Solid = True
    extrusion.Label = name
    return extrusion

def _add_landuse(name, feature, landuse):
    extrusion = FreeCAD.ActiveDocument.addObject("Part::Extrusion", name)
    extrusion.Base = feature
    color = (1.00,.60,.60)
    if landuse == 'residential':
        color = (1.0,.6,.6)
    elif landuse == 'meadow':
        color = (0.0,1.0,0.0)
    elif landuse == 'farmland':
        color = (.8,.8,.0)
    elif landuse == 'forest':
        color = (1.0,.4,.4)
    elif landuse == 'grass':
        color = (0.0,.8,.5)
    extrusion.ViewObject.ShapeColor = color
    extrusion.Dir = (0,0,0.1)
    extrusion.Solid = True
    extrusion.Label = name
    return extrusion

def _add_highway(name, feature):
    extrusion = FreeCAD.ActiveDocument.addObject("Part::Extrusion","highway")
    extrusion.Base = feature
    extrusion.ViewObject.LineColor = (0.00,.00,1.00)
    extrusion.ViewObject.LineWidth = 10
    extrusion.Dir = (0,0,0.2)
    extrusion.Solid = True
    extrusion.Label = name
    return extrusion

def import_osm(latitude, longitude, osm_zoom, download_altitude=False, progressBar=None, status=None):
    """Import Data from OSM at the latitude / longitude / zoom specified.

    Aditionally update the progressBar and status widget if given.

    Args:
        latitude (float): the latitude of the data to download
        longitude (float): the longitude of the data to download
        osm_zoom (int): the OpenStreetMap zoom, as a proxy for the size of the area to download
        downloadAltitude (bool, optional): whether to download the altitude. Defaults to False.
        progressBar (QProgressBar, optional): the progress bar to update. Defaults to None.
        status (QLabel, optional): the status widget. Defaults to None.
    """
    # REF: we use https://wiki.openstreetmap.org/wiki/Zoom_levels to switch 
    #   between OSM zoom level and º in longitude / latitude

    _set_progress(progressBar, 0)
    _set_status(status, "Downloading data from openstreetmap.org ...")

    cache_file = _get_cache_file(latitude, longitude, osm_zoom)
    if not os.path.exists(cache_file):
        content = _download_from_osm(latitude, longitude, osm_zoom, cache_file)
    else:
        FreeCAD.Console.PrintLog(f"Reading OSM data from cache '{cache_file}'...\n")
        with open(cache_file,"r") as f:
            content = f.read()

    if download_altitude:
        FreeCAD.Console.PrintWarning(f"Download or Altitude is not implemented.\n")
        download_altitude = False

    if download_altitude:
        base_altitude = _get_altitude(latitude, longitude)
    else:
        base_altitude = 0

    _set_status(status, "Parsing data ...")
    tree = xmltodict.parse(content, force_list=LIST_ELEMENTS)['osm']

    _set_status(status, "Transform data ...")

    # osm_nodes: a dict of OSM node w/ node id as key
    osm_nodes = { node['@id']: node for node in tree['node'] }

    # fc_points: map all nodes to xy-plane FC vector
    tm = TransverseMercator()
    (center_x, center_y) = tm.fromGeographic(latitude, longitude)
    def __to_fc_vector(node):
        (x, y) = tm.fromGeographic(float(node['@lat']), float(node['@lon']))
        return FreeCAD.Vector(x-center_x, y-center_y, 0.0)
    fc_points = { node['@id']: __to_fc_vector(node) for node in tree['node'] }

    _set_status(status, "Creating visualizations ...")

    # TODO: Is that correct? should we create a new document or just update the ActiveDocument?
    #FreeCAD.newDocument("OSM Map")
    active_document = FreeCAD.ActiveDocument

    FreeCAD.Console.PrintLog("Setting up Area ...\n")
    _setup_area(active_document, tree['bounds'])

    FreeCAD.Console.PrintLog("Setting up light ...\n")
    _setup_light(active_document)

    FreeCAD.Console.PrintLog("Setting up camera ...\n")
    _setup_camera(active_document, osm_zoom)

    FreeCAD.Console.PrintLog("Setting up groups ...\n")
    highway_group = active_document.addObject("App::DocumentObjectGroup","GRP_highways")
    landuse_group = active_document.addObject("App::DocumentObjectGroup","GRP_landuses")
    building_group = active_document.addObject("App::DocumentObjectGroup","GRP_buildings")
    path_group = active_document.addObject("App::DocumentObjectGroup","GRP_paths")

    way_count = len(tree['way'])
    for i, way in enumerate(tree['way']):

        _set_progress(progressBar, int(100.0*i/way_count))

        # tags: get a hash of all tags for the current way
        if 'tag' not in way: 
            continue
        
        tags = { tag['@k']: tag['@v'] for tag in way['tag'] }
        building = tags.get('building', None)
        landuse = tags.get('landuse', None)
        highway = tags.get('highway', None)
        addr_city = tags.get('addr:city', None)
        addr_street = tags.get('addr:street', None)
        addr_housenumber = tags.get('addr:housenumber', None)
        building_levels = int(tags.get('building:levels', 0))*1000*3
        building_height = int(tags.get('building:height', 0))*1000
        name = tags.get('name', None)
        nr = tags.get('ref', None)

        if building:
            type = tags.get('building', 'yes')
            name = tags.get('name', type.title() if type != 'yes' else "Building")
        if landuse:
            name = landuse.title()
        if highway:
            name = f"{tags}"
        if not name:
            name= f"{tags}"

        if download_altitude:
            way_osm_nodes = [ osm_nodes[node['@ref']] for node in way['nd'] ]
            altitudes = _get_altitudes(way_osm_nodes)

        way_fc_points = [ fc_points[node['@ref']] for node in way['nd'] ]

        polygon_fc_points = []
        for way_fc_point in way_fc_points:
            if download_altitude and building:
                altitude = altitudes[way_fc_point['@lat']+' '+way_fc_point['@lon']]*1000 - base_altitude
                way_fc_point.z = altitude
            polygon_fc_points.append(way_fc_point)

        # create 2D map
        polygon = Part.makePolygon(polygon_fc_points)
        Part.show(polygon)
        feature = active_document.ActiveObject
        feature.Label = "w_"+way['@id']
        feature.ViewObject.Visibility = False
        path_group.addObject(feature)

        # if name==' ':
        #     extrusion = active_document.addObject("Part::Extrusion",name)
        #     extrusion.Base = feature
        #     extrusion.ViewObject.ShapeColor = (1.00,1.00,0.00)
        #     extrusion.Dir = (0,0,10)
        #     extrusion.Solid = True
        #     extrusion.Label = 'way ex'

        if building:
            extrusion = _add_building(name, feature, building_height)
            inventortools.setcolors2(extrusion)
            building_group.addObject(extrusion)

        if landuse:
            extrusion = _add_landuse(name, feature, landuse)
            extrusion.ViewObject.Visibility = False
            landuse_group.addObject(extrusion)

        if highway:
            extrusion = _add_highway(name, feature)
            extrusion.ViewObject.Visibility = True
            highway_group.addObject(extrusion)

        if i % 10:
            FreeCADGui.updateGui()
            # FreeCADGui.SendMsgToActiveView("ViewFit")

    active_document.recompute()
    FreeCADGui.updateGui()
    active_document.recompute()

    _set_status(status, "Successfully imported OSM data.")
    _set_progress(progressBar, 100)


# Greenwich
STD_ZOOM = 17
STD_LATITUDE = 51.47786
STD_LONGITUDE = 0

class _CommandImport:
    """GeoData Import command definition

    Returns:
        _type_: _description_
    """
    def GetResources(self):
        return {'Pixmap'  : 'GeoData_Import',
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
        self.hasAltitude = False

        self.dialog = FreeCADGui.PySideUic.loadUi(
            os.path.join(os.path.dirname(__file__), "GeoDataImportDialog.ui")
        )
        self.dialog.locationPresets.currentIndexChanged.connect(self.onLocationPresetSelected)
        self.dialog.btnOpenBrowserWindow.clicked.connect(self.onOpenBrowserWindow)
        self.dialog.btnGetCoordFromBrowser.clicked.connect(self.onGetCoordFromBrowser)
        self.dialog.url.textChanged.connect(self.onUrlChanged)
        self.dialog.zoom.valueChanged.connect(self.onZoomChanged)
        self.dialog.latitude.valueChanged.connect(self.onLatitudeChanged)
        self.dialog.longitude.valueChanged.connect(self.onLongitudeChanged)
        self.dialog.btnImport.clicked.connect(self.onImport)

        # restore window geometry from stored state
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        self.dialog.resize(pref.GetInt("WindowWidth", 800), pref.GetInt("WindowHeight", 600))
        self.dialog.setWindowIcon(QtGui.QIcon(":/GeoData_Import.svg"))

        self.dialog.locationPresets.addItem(QT_TRANSLATE_NOOP("GeoData", "Select a location ..."))
        self.LocationPresets = []
        resource_dir = FreeCADGui.activeWorkbench().ResourceDir
        with open(os.path.join(resource_dir, 'Presets', 'osm.json')) as f:
            presets = json.load(f)
            for preset in presets["osm"]:
                self.LocationPresets.append(preset)
                self.dialog.locationPresets.addItem(preset['name'])
        self.dialog.locationPresets.setCurrentIndex(pref.GetInt("LocationPresetIndex", 0))

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

    def onLocationPresetSelected(self, i):
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
        self.onOpenBrowserWindow()
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateUrlField(self.Zoom, self.Latitude, self.Longitude)
        self.updateDialogCoordinate(self.Zoom, self.Latitude, self.Longitude)

    def onOpenBrowserWindow(self):
        """Open a Browser windows in order to for the User to navigate to
        the desired map location
        """
        if not self.Browser:
            self.Browser = WebGui.openBrowserWindow(f"OSM")
        try:
            self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        except RuntimeError as e:
            # If the User has deleted the browser window we have this error
            self.Browser = None
            self.onOpenBrowserWindow()

    def onGetCoordFromBrowser(self):
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
        self.updateUrlField(self.Zoom, self.Latitude, self.Longitude)
        self.updateDialogCoordinate(self.Zoom, self.Latitude, self.Longitude)

    def onUrlChanged(self, url):
        """Callback when the URL field has changed

        Args:
            url (str): The url to parse
        """
        (ok, zoom, latitude, longitude) = self._extract_coordinate_from_url(url)
        if ok:
            self.Zoom = zoom
            self.Latitude = latitude
            self.Longitude = longitude
        self.onOpenBrowserWindow()
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateDialogCoordinate(self.Zoom, self.Latitude, self.Longitude)
        
    def onZoomChanged(self,i):
        """Callback when the Zoom field has changed

        NOTE: as this callback can be called from the direct change of the 
        control or through a change of a related control, we check that both
        value match and refresh the browser window if needed.

        Args:
            i (int): the zoom
        """
        self.Zoom = int(i) if i else STD_ZOOM
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetInt("Zoom", self.Zoom)
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateUrlField(self.Zoom, self.Latitude, self.Longitude)
        self.updateDialogCoordinate(self.Zoom, self.Latitude, self.Longitude)

    def onLatitudeChanged(self,d):
        """Callback to set the Latitude

        NOTE: as this callback can be called from the direct change of the 
        control or through a change of a related control, we check that both
        value match and refresh the browser window if needed.

        Args:
            d (float): the latitude
        """
        self.Latitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Latitude", self.Latitude)
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateUrlField(self.Zoom, self.Latitude, self.Longitude)
        self.updateDialogCoordinate(self.Zoom, self.Latitude, self.Longitude)

    def onLongitudeChanged(self,d):
        """Callback to set the Longitude

        NOTE: as this callback can be called from the direct change of the 
        control or through a change of a related control, we check that both
        value match and refresh the browser window if needed.

        Args:
            d (float): the longitude
        """
        self.Longitude = d
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData").SetFloat("Longitude", self.Longitude)
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateUrlField(self.Zoom, self.Latitude, self.Longitude)
        self.updateDialogCoordinate(self.Zoom, self.Latitude, self.Longitude)

    def onImport(self):
        max_zoom_in_km = 0.1
        min_zoom_in_km = 3.0
        min_zoom = 15.0
        zoom_in_km = min_zoom_in_km + (min_zoom - float(self.Zoom)) * (min_zoom_in_km - max_zoom_in_km)/min_zoom_in_km 
        # geodat.import_osm.import_osm2(
        #     self.Latitude,
        #     self.Longitude,
        #     zoom_in_km,
        #     self.dialog.progressBar,
        #     self.dialog.status,
        #     self.dialog.downloadAltitude.isChecked())
        
        import_osm(self.Latitude,
                   self.Longitude,
                   self.Zoom,
                   self.dialog.downloadAltitude.isChecked(),
                   self.dialog.progressBar,
                   self.dialog.status)

    def updateBrowserUrl(self, zoom, latitude, longitude):
        """Update both the browser URL and the URL field with the zoom, 
        latitude and longitude.
        """
        url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        if self.Browser.url() != url:
            self.Browser.load(url)

    def updateUrlField(self, zoom, latitude, longitude):
        """Update both the browser URL and the URL field with the zoom, 
        latitude and longitude.
        """
        url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        self.dialog.url.setText(url)

    def updateDialogCoordinate(self, zoom, latitude, longitude):
        """Update the dialog coordinate fields with the the zoom, latitude
        and longitude.

        Args:
            zoom (int): the zoom of the map
            latitude (float): the latitude of the map
            longitude (float): the longitude of the map
        """
        self.dialog.zoom.setValue(zoom)
        self.dialog.latitude.setValue(latitude)
        self.dialog.longitude.setValue(longitude)

    def _extract_coordinate_from_url(self, url):
        pattern = re.compile(r'https?://www.openstreetmap.org/#map=(\d+)/([\d,.-]+)/([\d,.-]+)')
        matches  = re.findall(pattern, url)
        if len(matches) == 1:
            (zoom, latitude, longitude) = matches[0]
            return True, int(zoom), float(latitude), float(longitude)
        return False, None, None, None

if FreeCAD.GuiUp:
    FreeCAD.Console.PrintLog('addCommand(GeoData_Import)\n')
    FreeCADGui.addCommand('GeoData_Import', _CommandImport())
