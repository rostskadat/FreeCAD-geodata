#***************************************************************************
#*                                                                        *
#*   Copyright (c) 2016                                                     *  
#*   <microelly2@freecadbuch.de>                                         * 
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify*
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of    *
#*   the License, or (at your option) any later version.                *
#*   for detail see the LICENCE text file.                                *
#*                                                                        *
#*   This program is distributed in the hope that it will be useful,    *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the        *
#*   GNU Library General Public License for more details.                *
#*                                                                        *
#*   You should have received a copy of the GNU Library General Public    *
#*   License along with this program; if not, write to the Free Software*
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307*
#*   USA                                                                *
#*                                                                        *
#************************************************************************

import json
import os
import pivy
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

import FreeCAD
import FreeCADGui
import Part

from .TransverseMercator import TransverseMercator
from .inventortools import setcolors2

API_MAX_RETRY = 4
GCP_ELEVATION_API_KEY = None
GCP_ELEVATION_API_URL = "https://maps.googleapis.com/maps/api/elevation/json"
OSM_API_URL = "https://www.openstreetmap.org/api/0.6/map"

def import_osm(latitude, longitude, osm_zoom, download_altitude=False, progress_callback=None):
    """Import Data from OSM at the latitude / longitude / zoom specified.

    Aditionally update the progress_bar and status widget if given.

    Args:
        latitude (float): the latitude of the data to download
        longitude (float): the longitude of the data to download
        osm_zoom (int): the OpenStreetMap zoom, as a proxy for the size of the area to download
        download_altitude (bool, optional): whether to download the altitude. Defaults to False.
        progress_callback (func): a function to set the progress porcentage and the status. Defaults to None.
    """
    # REF: we use https://wiki.openstreetmap.org/wiki/Zoom_levels to switch
    #   between OSM zoom level and º in longitude / latitude

    if not progress_callback:
        def progress_callback(progress, status):
            FreeCAD.Console.PrintLog(f"{status} ({progress}/100)\n")
    progress_callback(0, "Downloading data from openstreetmap.org ...")

    cache_file = _get_cache_file(latitude, longitude, osm_zoom)
    if not os.path.exists(cache_file):
        status_code, content = _download_from_osm(latitude, longitude, osm_zoom, cache_file)
    else:
        FreeCAD.Console.PrintLog(f"Reading OSM data from cache '{cache_file}'...\n")
        with open(cache_file,"r", encoding='utf-8') as f:
            content = f.read()
        status_code = 200
    if status_code != 200:
        progress_callback(0, "Download failed. Increase the zoom.")
        return

    progress_callback(0, "Downloading altitude from googleapis ...")
    if download_altitude:
        base_altitude = _get_altitude(latitude, longitude)
    else:
        base_altitude = 0

    progress_callback(0, "Parsing data ...")
    root = ET.fromstring(content)

    progress_callback(0, "Transforming data ...")

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

    progress_callback(0, "Creating visualizations ...")

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

        progress_callback(int(100.0*i/way_count), "Creating visualizations ...")

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
            setcolors2(extrusion)
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
    progress_callback(100, "Successfully imported data.")

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
    light = pivy.coin.SoDirectionalLight()
    light.color.setValue(pivy.coin.SbColor(0,1,0))
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
