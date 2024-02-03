# GeoData support for FreeCAD


## What's New

Import_osm map dialogue box can also accept links from following sites in addition to (latitude, longitude)

* OpenStreetMap  
e.g. https://www.openstreetmap.org/#map=15/30.8611/75.8610
* Google Maps  
e.g. https://www.google.co.in/maps/@30.8611,75.8610,5z
* Bing Map  
e.g. https://www.bing.com/maps?osid=339f4dc6-92ea-4f25-b25c-f98d8ef9bc45&cp=30.8611~75.8610&lvl=17&v=2&sV=2&form=S00027
* Here Map  
e.g. https://wego.here.com/?map=30.8611,75.8610,15,normal
* (latitude,longitude)


## Prerequisites
* FreeCAD
* Git

Install prerequisites by running following command:  
````sudo apt-get install git-core freecad````


## How to use

1. Download the source files using following command:  
````git clone https://github.com/SurajDadral/geodata.git geodata````
1. Copy these files into FreeCAD directory:  
````cp -r geodata ~/.FreeCAD/Mod/geodata````
1. Restart the FreeCAD.

**Have Fun**

## QT Designer

```shell
pip install pyqt5-tools
pyqt5-tools designer
# & '%AppData_DIR%\Roaming\Python\Python310\Scripts\pyqt5-tools.exe' designer
```
