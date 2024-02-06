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
from PySide2 import QtGui, QtCore, QtWidgets
from pivy import coin
import WebGui
from NetworkManager import HAVE_QTNETWORK, InitializeNetworkManager
from ConnectionChecker import ConnectionChecker
import xml.etree.ElementTree as ET
from geodat.transversmercator import TransverseMercator
import geodat.inventortools as inventortools
import Part
from math import pow
import urllib.request
import urllib.parse

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
GCP_ELEVATION_API_KEY = None
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

def _call_external_service(base_url, params):
    if params:
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
    else:
        url = base_url    

    status_code = 400
    data = None
    try:
        with urllib.request.urlopen(url) as response:
            status_code = response.getcode()
            if status_code == 200:
                data = response.read()
    except urllib.error.URLError as e:
        print(f"Error: {e}")
    finally:
        return status_code, data

def _download_from_osm(latitude, longitude, osm_zoom, cache_file):
    delta_degree = 360 / pow(2, osm_zoom)

    (latitude_1, longitude_1) = (latitude-delta_degree, longitude-delta_degree)
    (latitude_2, longitude_2) = (latitude+delta_degree, longitude+delta_degree)
    FreeCAD.Console.PrintLog(f"@download p1=({latitude_1},{longitude_1}), p2=({latitude_2},{longitude_2})\n")
    params = {
        "bbox": f"{longitude_1},{latitude_1},{longitude_2},{latitude_2}"
    }
    FreeCAD.Console.PrintLog(f"Downloading OSM data from {OSM_API_URL}, {params} ...\n")
    status_code, data = _call_external_service(OSM_API_URL, params)
    if status_code == 200:
        cache_dir = os.path.dirname(cache_file)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir)
        FreeCAD.Console.PrintLog(f"Writing OSM data to {cache_file} ...\n")
        with open(cache_file, 'wb') as f:
            f.write(data)
        return status_code, data.decode('utf-8')
    return status_code, data

def _get_altitude(latitude, longitude):
    """Returns the altitude of a single point with latitude and longitude

    Args:
        latitude (float): the latitude
        longitude (float): the longitude

    Returns:
        float: the altitude
    """
    if not GCP_ELEVATION_API_KEY:
        FreeCAD.Console.PrintWarning(f"Altitude information not available. Specify a valid GCP_ELEVATION_API_KEY\n")
        return 0
    retry = 0
    while retry < API_MAX_RETRY:
        params = {
            "locations":f"{latitude},{longitude}",
            "key": GCP_ELEVATION_API_KEY
        }
        status_code, data = (200, '{"status":"OK","results":[{"elevation":314}]}'.encode()) #_call_external_service(OSM_API_URL, params)
        if status_code == 200:
            payload = json.loads(data.decode('utf-8'))
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

def _get_altitudes(osm_nodes):
    """Returns the altitude of a list of point (with latitude and longitude)

    Args:
        osm_nodes (list): the list of point (latitude, longitude)

    Returns:
        dict: the dict of altitude by
    """
    if not GCP_ELEVATION_API_KEY:
        FreeCAD.Console.PrintWarning(f"Altitude information not available. Specify a valid GCP_ELEVATION_API_KEY\n")
        return {}

    heights = {}
    chunk_size = 100 # 100 location at once...
    chunks = [osm_nodes[i:i + chunk_size] for i in range(0, len(osm_nodes), chunk_size)]
    for chunk in chunks:
        locations = [ f"{osm_node.get('lat')},{osm_node.get('lon')}" for osm_node in chunk ]
        params = {
            "locations": '|'.join(locations),
            "key": GCP_ELEVATION_API_KEY
        }
        status_code, data = _call_external_service(OSM_API_URL, params)
        if status_code == 200:
            payload = json.loads(data.decode('utf-8'))
            status = payload['status']
            if status == "OK":
                # elevation is in meter
                # TODO: Needs to match the lat and lon to the corresponding node
                for r in payload['results']:
                    key="%0.7f" %(r['location']['lat']) + " " + "%0.7f" %(r['location']['lng'])
                    heights[key]=r['elevation']
            elif status == "OVER_QUERY_LIMIT":
                retry += 1
                time.sleep(5)
            else:
                FreeCAD.Console.PrintWarning(f"Failed to download altitude data: {payload['error_message']}\n")
                break
    return heights

def _setup_area(active_document, minlat, minlon, maxlat, maxlon):
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
    FreeCADGui.SendMsgToActiveView("ViewFit")

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
    extrusion = FreeCAD.ActiveDocument.addObject("Part::Extrusion", name)
    extrusion.Base = feature
    extrusion.ViewObject.LineColor = (0.00,.00,1.00)
    extrusion.ViewObject.LineWidth = 10
    extrusion.Dir = (0,0,0.2)
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
        status_code, content = _download_from_osm(latitude, longitude, osm_zoom, cache_file)
    else:
        FreeCAD.Console.PrintLog(f"Reading OSM data from cache '{cache_file}'...\n")
        with open(cache_file,"r", encoding='utf-8') as f:
            content = f.read()
        status_code = 200
    if status_code != 200:
        _set_status(status, "Download failed. Increase the zoom.")
        return

    _set_status(status, "Downloading altitude from googleapis ...")
    if download_altitude:
        base_altitude = _get_altitude(latitude, longitude)
    else:
        base_altitude = 0

    _set_status(status, "Parsing data ...")
    root = ET.fromstring(content)

    _set_status(status, "Transforming data ...")

    # osm_nodes: a dict of OSM node w/ node id as key
    osm_nodes = { node.get('id'): node for node in root.findall('node') }
    osm_ways = list(root.findall('way'))

    # fc_points: map all nodes to xy-plane FC vector
    tm = TransverseMercator()
    (center_x, center_y) = tm.fromGeographic(latitude, longitude)
    def __to_fc_vector(node):
        (x, y) = tm.fromGeographic(float(node.get('lat')), float(node.get('lon')))
        return FreeCAD.Vector(x-center_x, y-center_y, 0.0)
    fc_points = { id: __to_fc_vector(node) for id, node in osm_nodes.items() }

    FreeCAD.Console.PrintLog(f"Found {len(osm_nodes.keys())} node(s) and {len(osm_ways)} way(s)...\n")

    _set_status(status, "Creating visualizations ...")

    # TODO: Is that correct? should we create a new document or just update the ActiveDocument?
    #FreeCAD.newDocument("OSM Map")
    active_document = FreeCAD.ActiveDocument

    FreeCAD.Console.PrintLog("Setting up Area ...\n")
    bounds = root.find('bounds')
    _setup_area(active_document, float(bounds.get('minlat')),float(bounds.get('minlon')),float(bounds.get('maxlat')),float(bounds.get('maxlon')))

    FreeCAD.Console.PrintLog("Setting up light ...\n")
    _setup_light(active_document)

    FreeCAD.Console.PrintLog("Setting up camera ...\n")
    _setup_camera(active_document, osm_zoom)

    FreeCAD.Console.PrintLog("Setting up groups ...\n")
    highway_group = active_document.addObject("App::DocumentObjectGroup","GRP_highways")
    landuse_group = active_document.addObject("App::DocumentObjectGroup","GRP_landuses")
    building_group = active_document.addObject("App::DocumentObjectGroup","GRP_buildings")
    path_group = active_document.addObject("App::DocumentObjectGroup","GRP_paths")

    way_count = len(osm_ways)
    for i, way in enumerate(osm_ways):
        way_id = way.get('id')

        _set_progress(progressBar, int(100.0*i/way_count))

        if not len(way.findall('tag')): 
            FreeCAD.Console.PrintLog(f"Skipping untagged way {way_id} ...\n")
            continue
        
        # tags: get a hash of all tags for the current way
        tags = { tag.get('k'): tag.get('v') for tag in way.findall('tag') }
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
            name = tags.get('name', highway.title())
        if not name:
            name= f"{tags}"

        if download_altitude:
            way_osm_nodes = [ osm_nodes[node.get('ref')] for node in way.findall('nd') ]
            altitudes = _get_altitudes(way_osm_nodes)

        way_fc_points = [ fc_points[node.get('ref')] for node in way.findall('nd') ]

        polygon_fc_points = []
        for way_fc_point in way_fc_points:
            if download_altitude and building:
                altitude = altitudes[way_fc_point.get('lat')+' '+way_fc_point.get('lon')]*1000 - base_altitude
                way_fc_point.z = altitude
            polygon_fc_points.append(way_fc_point)

        # create 2D map
        polygon = Part.makePolygon(polygon_fc_points)
        Part.show(polygon)
        feature = active_document.ActiveObject
        feature.Label = f"w_{way_id}"
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
        self.dialog.osmLocationPresets.currentIndexChanged.connect(self.onOsmLocationPresetSelected)
        self.dialog.osmOpenBrowserWindow.clicked.connect(self.onOsmOpenBrowserWindow)
        self.dialog.osmGetCoordFromBrowser.clicked.connect(self.onOsmGetCoordFromBrowser)
        self.dialog.osmUrl.textChanged.connect(self.onOsmUrlChanged)
        self.dialog.osmZoom.valueChanged.connect(self.onOsmZoomChanged)
        self.dialog.osmLatitude.valueChanged.connect(self.onOsmLatitudeChanged)
        self.dialog.osmLongitude.valueChanged.connect(self.onOsmLongitudeChanged)
        self.dialog.osmLongitude.valueChanged.connect(self.onOsmLongitudeChanged)
        self.dialog.osmLongitude.valueChanged.connect(self.onOsmLongitudeChanged)

        self.dialog.csvSelectFile.clicked.connect(self.onCsvSelectFile)

        self.dialog.btnImport.clicked.connect(self.onImport)
        self.dialog.btnClose.clicked.connect(self.onClose)
        self.dialog.progressBar.setVisible(False)

        # restore window geometry from stored state
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        #self.dialog.resize(pref.GetInt("WindowWidth", 800), pref.GetInt("WindowHeight", 600))
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
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmCoordinates(self.Zoom, self.Latitude, self.Longitude)

    def onOsmOpenBrowserWindow(self):
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
        self.updateOsmUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmCoordinates(self.Zoom, self.Latitude, self.Longitude)

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
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmCoordinates(self.Zoom, self.Latitude, self.Longitude)
        
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
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmCoordinates(self.Zoom, self.Latitude, self.Longitude)

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
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmCoordinates(self.Zoom, self.Latitude, self.Longitude)

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
        self.updateBrowserUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmUrl(self.Zoom, self.Latitude, self.Longitude)
        self.updateOsmCoordinates(self.Zoom, self.Latitude, self.Longitude)

    def onCsvSelectFile(self):
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/GeoData")
        home_dir = os.path.expanduser('~')
        csv_dirname = pref.GetString("LastCsvSelectDirname", home_dir)
        if not os.path.isdir(csv_dirname):
            csv_dirname = home_dir
        csv_filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.dialog, 
            QT_TRANSLATE_NOOP("GeoData", "Open CSV"), 
            csv_dirname,
            QT_TRANSLATE_NOOP("GeoData", "CSV Files (*.csv *.tsv)")
        )
        pref.SetString("LastCsvSelectDirname", os.path.dirname(csv_filename))

    def onImport(self):
        self.dialog.progressBar.setVisible(True)
        global GCP_ELEVATION_API_KEY
        if self.dialog.osmDownloadAltitude.isChecked() and not GCP_ELEVATION_API_KEY:
            FreeCAD.Console.PrintWarning(f"Altitude information not available because no GCP API key provided.\n")
        import_osm(self.Latitude,
                   self.Longitude,
                   self.Zoom,
                   GCP_ELEVATION_API_KEY and self.dialog.osmDownloadAltitude.isChecked(),
                   self.dialog.progressBar,
                   self.dialog.status)
        self.dialog.progressBar.setVisible(False)

    def onClose(self):
        FreeCAD.Console.PrintLog(f"Closing {self.dialog}\n")
        self.dialog.done(0)

    def updateBrowserUrl(self, zoom, latitude, longitude):
        """Update both the browser URL and the URL field with the zoom, 
        latitude and longitude.
        """
        url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        if self.Browser and self.Browser.url() != url:
            self.Browser.load(url)

    def updateOsmUrl(self, zoom, latitude, longitude):
        """Update both the browser URL and the URL field with the zoom, 
        latitude and longitude.
        """
        url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        self.dialog.osmUrl.setText(url)

    def updateOsmCoordinates(self, zoom, latitude, longitude):
        """Update the dialog coordinate fields with the the zoom, latitude
        and longitude.

        Args:
            zoom (int): the zoom of the map
            latitude (float): the latitude of the map
            longitude (float): the longitude of the map
        """
        self.dialog.osmZoom.setValue(zoom)
        self.dialog.osmLatitude.setValue(latitude)
        self.dialog.osmLongitude.setValue(longitude)

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
