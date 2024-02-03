import sys
import FreeCAD
if FreeCAD.GuiUp:
    import FreeCADGui
    from PySide import QtGui

def printMessage( message ):
    FreeCAD.Console.PrintMessage( message )
    if FreeCAD.GuiUp :
        if sys.version_info.major < 3:
            message = message.decode("utf8")
        QtGui.QMessageBox.information( None , "" , message )

def printWarning( message ):
    FreeCAD.Console.PrintMessage( message )
    if FreeCAD.GuiUp :
        if sys.version_info.major < 3:
            message = message.decode("utf8")
        QtGui.QMessageBox.warning( None , "" , message )

