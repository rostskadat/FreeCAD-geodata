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

__title__="FreeCAD Geodata Toolkit"
__author__ = "Thomas Gundermann"
__url__ = "http://www.freecadbuch.de"
__vers__ ="py3.01"

import os
import FreeCAD
import FreeCADGui

import sys
if sys.version_info[0] !=2:
    from importlib import reload
reload(sys)

try:
    import cv2
except:
    FreeCAD.Console.PrintWarning("Geodat WB: Cannot import module named cv2. Some import might not be available.\n")

try:
    import gdal
    import gdalconst
except:
    FreeCAD.Console.PrintWarning("Geodat WB: Cannot import module named gdal gdalconst. Some import might not be available.\n")

class GeoDataWorkbench(FreeCADGui.Workbench):
    """The GeoData workbench definition."""

    def __init__(self):
        from PySide.QtCore import QT_TRANSLATE_NOOP

        __dirname__ = os.path.join(FreeCAD.getResourceDir(), "Mod", "FreeCAD-geodata")
        if not os.path.isdir(__dirname__):
            __dirname__ = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "FreeCAD-geodata")
        if not os.path.isdir(__dirname__):
            FreeCAD.Console.PrintError("Failed to determine the install location of the GeoData workbench. Check your installation.\n")
        _tooltip = ("The GeoData workbench is used to import GeoData materials")
        self.__class__.ResourceDir = os.path.join(__dirname__, "Resources")
        self.__class__.Icon = os.path.join(self.ResourceDir, "icons", "GeoData_Workbench.svg")
        self.__class__.MenuText = QT_TRANSLATE_NOOP("GeoData", "GeoData")
        self.__class__.ToolTip = QT_TRANSLATE_NOOP("GeoData", _tooltip)
        self.__class__.Version = "0.0.1"

    def Initialize(self):
        """When the workbench is first loaded."""

        from PySide.QtCore import QT_TRANSLATE_NOOP

        import GeoData

        self.geodata_toolbar = [ "GeoData_Import", ]

        # Set up toolbars
        from draftutils.init_tools import init_toolbar, init_menu
        init_toolbar(self, QT_TRANSLATE_NOOP("Workbench", "GeoData tools"), self.geodata_toolbar)
        init_menu(self, QT_TRANSLATE_NOOP("Workbench", "GeoData"), self.geodata_toolbar)
        FreeCAD.Console.PrintLog('Initialized GeoData workbench.\n')

    def Activated(self):
        """When entering the workbench."""
        import importlib
        modules = [module for name,module in sys.modules.items() if 'GeoData' in name]
        list(map(lambda module: importlib.reload(module), modules))
        FreeCAD.Console.PrintLog("GeoData workbench activated.\n")

    def Deactivated(self):
        """When leaving the workbench."""
        FreeCAD.Console.PrintLog("GeoData workbench deactivated.\n")

    def GetClassName(self):
        """Type of workbench."""
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(GeoDataWorkbench)
