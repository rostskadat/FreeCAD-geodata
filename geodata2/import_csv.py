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

import csv
import io

import FreeCAD as App
import FreeCADGui as Gui
import Draft

from .TransverseMercator import TransverseMercator

def import_csv(latitude, longitude, csv_content, has_headers=False, progress_callback=None):
    """Import Data from CSV content at the latitude / longitude.

    Aditionally update the progress_bar and status widget if given.

    Args:
        latitude (float): the latitude of the data to download
        longitude (float): the longitude of the data to download
        csv_content (str): the CSV content
        has_headers (bool, optional): whether the CSV content first row are headers or not.
        progress_callback (func): a function to set the progress porcentage and the status. Defaults to None.
    """
    if not progress_callback:
        def progress_callback(progress, status):
            App.Console.PrintLog(f"{status} ({progress}/100)\n")
    progress_callback(0, "Parsing data ...")

    tm = TransverseMercator()
    (center_x, center_y) = tm.fromGeographic(latitude, longitude)

    progress_callback(25, "Parsing data ...")

    fc_points = []
    with io.StringIO(csv_content) as f:
        dialect = csv.Sniffer().sniff(f.read(1024))
        f.seek(0)
        reader = csv.reader(f, dialect)
        for i,row in enumerate(reader):
            progress_callback(i, "Parsing data ...")
            (x, y) = tm.fromGeographic(float(row[0]), float(row[1]))
            fc_points.append(App.Vector(x-center_x, y-center_y, 0.0))

    # Let's close the wire
    fc_points.append(fc_points[0])

    progress_callback(50, "Creating visualizations ...")

    Draft.makeWire(fc_points)
    active_object = App.ActiveDocument.ActiveObject
    active_object.ViewObject.LineColor=(1.0,0.0,0.0)
    App.activeDocument().recompute()
    Gui.SendMsgToActiveView("ViewFit")

    progress_callback(100, "Successfully imported data.")
