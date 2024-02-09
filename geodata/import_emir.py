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

import FreeCAD
import FreeCADGui
import Draft

from .TransverseMercator import TransverseMercator
from .inventortools import setcolors2

def import_emir(emir_filename, progress_callback=None):
    """Import Data from EMIR (CIVIL3D?) content at the latitude / longitude.

    Aditionally update the progress_bar and status widget if given.

    ```text
    ncols        5
    nrows        6
    xllcorner    260.000000000000
    yllcorner    120.000000000000
    cellsize     10.000000000000
    10 10 10 10 10 10 
    10 11 12 13 10 10 
    10 11 11 8 10 10 
    10 11 11 9 10 10 
    10 10 10 10 10 10
    ```

    Args:
        emir_filename (str): the CIVIL 3D content
        progress_callback (func): a function to set the progress porcentage and the status. Defaults to None.
    """
    if not progress_callback:
        def progress_callback(progress, status):
            FreeCAD.Console.PrintLog(f"{status} ({progress}/100)\n")
    progress_callback(0, "Parsing data ...")

    lines = []
    if os.path.isfile(emir_filename):
        with open(emir_filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    props = {}
    for line in lines[:5]:
        (header, value) = line.split()[0:2]
        props[header] = value

    xllcorner = float(props['xllcorner'])*1000
    yllcorner = float(props['yllcorner'])*1000
    cellsize = float(props['cellsize'])*1000
    ncols = int(props['ncols'])
    nrows = int(props['nrows'])

    progress_callback(25, "Transforming data ...")

    def __to_fc_point(i, j, value):
        return FreeCAD.Vector(xllcorner+i*cellsize, yllcorner+j*cellsize, float(value)*1000)

    fc_points = []
    for i in range(ncols):
        fc_points.append([ __to_fc_point(i, j, value) for j, value in enumerate(lines[5+i].split()) ])

    progress_callback(50, "Creating visualizations ...")

    active_document = FreeCAD.ActiveDocument
    group = active_document.addObject("App::DocumentObjectGroup","GRP_EmirImport")

    # Then create a BSpline for each column and row
    for i in range(ncols):
        Draft.makeBSpline(fc_points[i])
        group.addObject(active_document.ActiveObject)

    for i in range(nrows):
        Draft.makeBSpline([ col[i] for col in fc_points ])
        group.addObject(active_document.ActiveObject)

    FreeCAD.activeDocument().recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")

    progress_callback(100, "Successfully imported data.")
