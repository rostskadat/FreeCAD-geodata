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

import os
import xml.etree.ElementTree as ET

import FreeCAD
import FreeCADGui
import Draft

from .TransverseMercator import TransverseMercator

def import_gpx(latitude, longitude, altitude, gpx_filename, generate_nodes=False, progress_callback=None):
    """Import Data from GPX content at the latitude / longitude.

    Aditionally update the progress_bar and status widget if given.

    Args:
        latitude (float): the latitude of the data to download
        longitude (float): the longitude of the data to download
        gpx_content (str): the GPX content
        generate_nodes (bool, optional): ???
        progress_callback (func): a function to set the progress porcentage and the status. Defaults to None.
    """
    if not progress_callback:
        def progress_callback(progress, status):
            FreeCAD.Console.PrintLog(f"{status} ({progress}/100)\n")
    progress_callback(0, "Parsing data ...")

    tm = TransverseMercator()
    (center_x, center_y) = tm.fromGeographic(latitude, longitude)

    gpx_content = None
    if os.path.isfile(gpx_filename):
        with open(gpx_filename, "r", encoding="utf-8") as f:
            gpx_content = f.read()

    root = ET.fromstring(gpx_content)

    progress_callback(25, "Transforming data ...")

    # What about different trkseg???
    ns = root.tag[0:root.tag.index('}')+1]
    trk = root.find(f"{ns}trk")

    gpx_points = [ trkpt for trkpt in trk.find(f"{ns}trkseg").findall(f"{ns}trkpt") ]
    def __to_fc_vector(gpx_point):
        (x, y) = tm.fromGeographic(float(gpx_point.get('lat')), float(gpx_point.get('lon')))
        z = float(gpx_point.find(f"{ns}ele").text)*1000.0
        return FreeCAD.Vector(x-center_x, y-center_y, z)
    fc_points = [ __to_fc_vector(gpx_point) for gpx_point in gpx_points ]

    # Let's close the wire
    progress_callback(50, "Creating visualizations ...")

    Draft.makeWire(fc_points)
    active_object = FreeCAD.ActiveDocument.ActiveObject
    active_object.ViewObject.LineColor = (1.0,0.0,0.0)
    active_object.Placement.Base = FreeCAD.Vector(center_x, center_y, altitude*1000)
    active_object.Label = trk.find(f"{ns}name").text
    FreeCAD.activeDocument().recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")

    progress_callback(100, "Successfully imported data.")
