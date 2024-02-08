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

import FreeCAD
import FreeCADGui

try:
    import cv2
except:
    FreeCAD.Console.PrintWarning("Geodat WB: Cannot import module named cv2\n")

try:
    import gdal
    import gdalconst
except:
    FreeCAD.Console.PrintWarning("Geodat WB: Cannot import module named gdal gdalconst\n")

# the menu entry list
FreeCAD.tcmdsGeodat = []
def Activated(self):
    import re
    FreeCAD.ActiveDocument.openTransaction(self.name)
    if self.command != '':
        if self.modul != '':
            modul = self.modul
        else:
            modul = self.name
        if sys.version_info[0] !=2:
            Gui.doCommand("from importlib import reload")
        
        Gui.doCommand("import " + modul)
        Gui.doCommand("import " + self.lmod)
        Gui.doCommand("reload(" + self.lmod + ")")
        docstring = "print();print(" + re.sub(r'\(.*\)', '.__doc__'+")", self.command)
        Gui.doCommand(docstring)
        Gui.doCommand(self.command)
    FreeCAD.ActiveDocument.commitTransaction()
    FreeCAD.ActiveDocument.recompute()
