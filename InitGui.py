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

__title__="FreeCAD GeoData2 Toolkit"
__author__ = "Thomas Gundermann"
__url__ = "http://www.freecadbuch.de"
__vers__ ="py3.01"

import os
import FreeCAD as App
import FreeCADGui as Gui

import sys
if sys.version_info[0] !=2:
    from importlib import reload
reload(sys)

try:
    import cv2
except:
    App.Console.PrintWarning("GeoData2 WB: Cannot import module named cv2. Some import might not be available.\n")

try:
    import gdal
    import gdalconst
except:
    App.Console.PrintWarning("GeoData2 WB: Cannot import module named gdal gdalconst. Some import might not be available.\n")

class GeoData2Workbench(Gui.Workbench):
    """The GeoData2 workbench definition."""

    def __init__(self):
        from PySide.QtCore import QT_TRANSLATE_NOOP

        __dirname__ = os.path.join(App.getResourceDir(), "Mod", "FreeCAD-geodata2")
        if not os.path.isdir(__dirname__):
            __dirname__ = os.path.join(App.getUserAppDataDir(), "Mod", "FreeCAD-geodata2")
        if not os.path.isdir(__dirname__):
            App.Console.PrintError("Failed to determine the install location of the GeoData2 workbench. Check your installation.\n")
        _tooltip = ("The GeoData2 workbench is used to import GeoData2 materials")
        self.__class__.ResourceDir = os.path.join(__dirname__, "Resources")
        self.__class__.Icon = os.path.join(self.ResourceDir, "icons", "GeoData2_Workbench.svg")
        self.__class__.MenuText = QT_TRANSLATE_NOOP("GeoData2", "GeoData2")
        self.__class__.ToolTip = QT_TRANSLATE_NOOP("GeoData2", _tooltip)
        self.__class__.Version = "0.0.1"

    def Initialize(self):
        """When the workbench is first loaded."""
        from PySide.QtCore import QT_TRANSLATE_NOOP

        from draftutils.init_tools import init_toolbar, init_menu
        import GeoData2

        # Set up toolbars
        self.toolbar = [ "GeoData2_Import", ]
        init_toolbar(self, QT_TRANSLATE_NOOP("Workbench", "GeoData2 tools"), self.toolbar)
        init_menu(self, QT_TRANSLATE_NOOP("Workbench", "GeoData2"), self.toolbar)

        # FreeCADGui.addIconPath(":/icons")
        # FreeCADGui.addLanguagePath(":/translations")
        App.Console.PrintLog('Initialized GeoData2 workbench.\n')

    def Activated(self):
        """When entering the workbench."""
        import importlib
        modules = [module for name,module in sys.modules.items() if 'geodata2' in name]
        list(map(lambda module: importlib.reload(module), modules))
        App.Console.PrintLog("GeoData2 workbench activated.\n")

    def Deactivated(self):
        """When leaving the workbench."""
        App.Console.PrintLog("GeoData2 workbench deactivated.\n")

    def GetClassName(self):
        """Type of workbench."""
        return "Gui::PythonWorkbench"

Gui.addWorkbench(GeoData2Workbench)
