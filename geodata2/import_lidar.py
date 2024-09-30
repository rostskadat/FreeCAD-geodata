#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2016 <microelly2@freecadbuch.de>                        *
#*   Copyright (c) 2024 Julien Masnada <rostskadat@gmail.com>              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

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

def import_lidar(lidar_filename, progress_bar=None, status=None):
    """Import Data from LIDAR content at the latitude / longitude.

    Aditionally update the progress_bar and status widget if given.

    Args:
        lidar_filename (str): the CIVIL 3D content
        progress_callback (func): a function to set the progress porcentage and the status. Defaults to None.
    """
    if not progress_callback:
        def progress_callback(progress, status):
            FreeCAD.Console.PrintLog(f"{status} ({progress}/100)\n")
    progress_callback(0, "Parsing data ...")

    FreeCAD.activeDocument().recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")

    progress_callback(100, "Successfully imported data.")
