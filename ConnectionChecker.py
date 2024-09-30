# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2016 <microelly2@freecadbuch.de>                        *
# *   Copyright (c) 2024 Julien Masnada <rostskadat@gmail.com>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import FreeCAD as App
import NetworkManager
from PySide2 import QtGui, QtCore, QtWidgets

if App.GuiUp:
    from PySide.QtCore import QT_TRANSLATE_NOOP
else:
    # \cond
    def QT_TRANSLATE_NOOP(ctxt, txt):
        return txt
    # \endcond


class ConnectionChecker(QtCore.QThread):
    """Helper class to enforce a functioning Internet connection before proceeding

    Args:
        QtCore (_type_): _description_
    """

    success = QtCore.Signal()
    failure = QtCore.Signal(str)

    def __init__(self, url):
        QtCore.QThread.__init__(self)
        self.url = url

    def run(self):
        App.Console.PrintLog(f"Checking network connection to {self.url} ...\n")
        result = NetworkManager.AM_NETWORK_MANAGER.blocking_get(self.url)
        if QtCore.QThread.currentThread().isInterruptionRequested():
            self.success.emit()
            return
        if not result:
            self.failure.emit(
                QT_TRANSLATE_NOOP(
                    "GeoData2",
                    f"Unable to read data from {self.url}: check your internet connection and proxy settings and try again.",
                )
            )
            return
        self.success.emit()
