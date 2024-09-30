# -*- coding: utf-8 -*-
#-------------------------------------------------
#-- osm map importer
#--
#-- microelly 2016 v 0.4
#--
#-- GNU Lesser General Public License (LGPL)
#-------------------------------------------------
'''import data from openstreetmap'''


#http://api.openstreetmap.org/api/0.6/map?bbox=11.74182,50.16413,11.74586,50.16561
#http://api.openstreetmap.org/api/0.6/way/384013089
#http://api.openstreetmap.org/api/0.6/node/3873106739

#\cond
from geodat.say import *


import time, json, os

import sys
if sys.version_info[0] !=2:
	from importlib import reload
	import urllib.request

#from say import *

import time, json, os

try:
	import urllib2
except:
	import urllib

import pivy
from pivy import coin


import geodat.my_xmlparser
reload (geodat.my_xmlparser)

import geodat.transversmercator
from  geodat.transversmercator import TransverseMercator

import geodat.inventortools as inventortools

import geodat.xmltodict
from  geodat.xmltodict import parse
#\endcond

#------------------------------
#
# microelly 2016 ..
#
#------------------------------

import time

## get the elevation height of a single point
def getHeight(b,l):
	''' get height of a single point with latitude b, longitude l'''
	anz=0
	while anz<4:
			source="https://maps.googleapis.com/maps/api/elevation/json?locations="+str(b)+','+str(l)
			try:
				response = urllib2.urlopen(source)
			except:
				response = urllib.request.urlopen(source)
			ans=response.read()
			if ans.find("OVER_QUERY_LIMIT"):
				anz += 1
				time.sleep(5)
			else:
				anz=10
	s=json.loads(ans)
	res=s['results']
	for r in res:
		return round(r['elevation']*1000,2)

## get the heights for a list of points

def getHeights(points):
	''' get heights for a list of points'''
	i=0
	size=len(points)
	while i<size:
		source="https://maps.googleapis.com/maps/api/elevation/json?locations="
		ii=0
		if i>0:
			time.sleep(1)
		while ii < 20 and i < size:
			p=points[i]
			ss= p[1]+','+p[2] + '|'
			source += ss
			i += 1
			ii += 1
		source += "60.0,10.0"
		response = urllib.request.urlopen(source)
		ans=response.read()
		s=json.loads(ans)
		res=s['results']
		heights= {}
		for r in res:
			key="%0.7f" %(r['location']['lat']) + " " + "%0.7f" %(r['location']['lng'])
			heights[key]=r['elevation']
	return heights


def organize():
	'''create groups for the different object types
	GRP_highways, GRP_building, GRP_landuse
	'''
	highways=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_highways")
	landuse=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_landuse")
	buildings=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_building")
	pathes=App.activeDocument().addObject("App::DocumentObjectGroup","GRP_pathes")

	for oj in App.activeDocument().Objects:
		if oj.Label.startswith('building'):
			buildings.addObject(oj)
			# oj.ViewObject.Visibility=False
		if oj.Label.startswith('highway') or oj.Label.startswith('way'):
			highways.addObject(oj)
			oj.ViewObject.Visibility=False
		if oj.Label.startswith('landuse'):
			landuse.addObject(oj)
			oj.ViewObject.Visibility=False
		if oj.Label.startswith('w_'):
			pathes.addObject(oj)
			oj.ViewObject.Visibility=False

#---------------------
from geodat.say import *
import re

#fn='/home/thomas/.FreeCAD//geodat3/50.340722-11.232647-0.015'
#fn='/home/thomas/.FreeCAD/system.cfg'

debug=False



#--------------------


## core method to download and import the data
#

#def import_osm(b,l,bk,progressbar,status):
#	import_osm2(b,l,bk,progressbar,status,False)

def import_osm2(b,l,bk,progressbar,status,elevation):


	dialog=False
	debug=False

	if progressbar:
			progressbar.setValue(0)

	if status:
		status.setText("get data from openstreetmap.org ...")
		FreeCADGui.updateGui()
	content=''

	bk=0.5*bk
	dn=FreeCAD.ConfigGet("UserAppData") + "/geodat3/"
	fn=dn+str(b)+'-'+str(l)+'-'+str(bk)
	import os
	if not os.path.isdir(dn):
		os.makedirs(dn)


	try:
		say("I try to read data from cache file ... ")
		say(fn)
		f=open(fn,"r")
		content=f.read()
	#	say(content)
	#	raise Exception("to debug:force load from internet")
	except:
		sayW("no cache file, so I connect to  openstreetmap.org...")
		lk=bk #
		b1=b-bk/1113*10
		l1=l-lk/713*10
		b2=b+bk/1113*10
		l2=l+lk/713*10
		source='http://api.openstreetmap.org/api/0.6/map?bbox='+str(l1)+','+str(b1)+','+str(l2)+','+str(b2)
		say(source)

		import requests
		response = requests.get(source)
		data = response.text
		lines=response.text.split('\n')
		FreeCAD.t=response
		
		
		f=open(fn,"w")
#		f.write(response.text)
		if response.status_code == 200:
			with open(fn, 'wb') as f:
				for chunk in response.iter_content(1024):
					f.write(chunk)
		f.close()
#		print("huhu");return


		if 0:
			try:
				say("read--")
				response = urllib.request.urlopen(source)
				#import ssl
				#ssl._create_default_https_context = ssl._create_unverified_context
				#response = urllib.request.urlopen(source)

	#			import requests
	#			response = requests.get(source)

				say(response)
				say("2huu")
				first=True
				content=''
				f=open(fn,"w")
				l=0
				z=0
				ct=0
				
				say("2wkkw")
				#say(response.text)
		#		lines=response.text.split('\n')
		#		say(len(lines))
				say("ll")
				# for line in lines:
				for line in response:	
					print ("Y",line)
					if status:
						if z>5000:
							status.setText("read data ..." + str(l))
							z=0
						FreeCADGui.updateGui()
						l+=1
						z+=1
					if first:
						first=False
					else:
						content += line
						f.write(line)
				f.close()
				if status:
					status.setText("FILE CLOSED ..." + str(l))
					FreeCADGui.updateGui()
				response.close()
			except:
				sayErr( "Fehler beim Lesen")

			if status:
				status.setText("got data from openstreetmap.org ...")
				FreeCADGui.updateGui()
			sayW("Beeenden - im zweiten versuch daten auswerten")

			return False


	if elevation:
		baseheight=getHeight(b,l)
	else:
		baseheight=0

	if debug:
		say( "-------Data---------")
		say(content)

	if status:
		status.setText("parse data ...")
		FreeCADGui.updateGui()

	say("------------------------------")
	say(fn)

#	fn='/home/thomas/.FreeCAD//geodat3/50.340722-11.232647-0.015'
	say(fn)

	tree=geodat.my_xmlparser.getData(fn)

#	for element in tree.getiterator('node'):
#		say(element.params)

#	say("ways")
#	for element in tree.getiterator('way'):
#		say(element.params)
#	say("relations")
#	for element in tree.getiterator('relation'):
#		say(element.params)




	if 0:
		try:
			sd=parse(content)
		except:
			sayexc("Problem parsing data - abort")
			status.setText("Problem parsing data - aborted, for details see Report view")
			return

	if debug: say(json.dumps(sd, indent=4))

	if status:
		status.setText("transform data ...")
		FreeCADGui.updateGui()

	relations=tree.getiterator('relation')
	nodes=tree.getiterator('node')
	ways=tree.getiterator('way')
	bounds=tree.getiterator('bounds')[0]

	# center of the scene
	minlat=float(bounds.params['minlat'])
	minlon=float(bounds.params['minlon'])
	maxlat=float(bounds.params['maxlat'])
	maxlon=float(bounds.params['maxlon'])

	tm=TransverseMercator()
	tm.lat=0.5*(minlat+maxlat)
	tm.lon=0.5*(minlon+maxlon)

	center=tm.fromGeographic(tm.lat,tm.lon)
	corner=tm.fromGeographic(minlat,minlon)
	size=[center[0]-corner[0],center[1]-corner[1]]

	# map all points to xy-plane
	points={}
	nodesbyid={}
	for n in nodes:
		nodesbyid[n.params['id']]=n
		ll=tm.fromGeographic(float(n.params['lat']),float(n.params['lon']))
		points[str(n.params['id'])]=FreeCAD.Vector(ll[0]-center[0],ll[1]-center[1],0.0)

#	say(points)
#	say("abbruch3 -hier daten uebernehmen !!");return

	# hack to catch deutsche umlaute
	def beaustring(string):
		res=''
		for tk in zz:
			try:
				res += str(tk)
			except:

				if ord(tk)==223:
					res += 'ß'
				elif ord(tk)==246:
					res += 'ö'
				elif ord(tk)==196:
					res += 'Ä'
				elif ord(tk)==228:
					res += 'ä'
				elif ord(tk)==242:
					res += 'ü'
				else:
					sayErr(["error sign",tk,ord(tk),string])
					res +="#"
		return res

	if status:
		status.setText("create visualizations  ...")
		FreeCADGui.updateGui()

	App.newDocument("OSM Map")
	say("Datei erzeugt")
	area=App.ActiveDocument.addObject("Part::Plane","area")
	obj = FreeCAD.ActiveDocument.ActiveObject
	say("grundflaeche erzeugt")
	try:
		viewprovider = obj.ViewObject
		root=viewprovider.RootNode
		myLight = coin.SoDirectionalLight()
		myLight.color.setValue(coin.SbColor(0,1,0))
		root.insertChild(myLight, 0)
		say("beleuchtung auf grundobjekt eingeschaltet")
	except:
		sayexc("Beleuchtung 272")

	cam='''#Inventor V2.1 ascii
	OrthographicCamera {
	  viewportMapping ADJUST_CAMERA
	  orientation 0 0 -1.0001  0.001
	  nearDistance 0
	  farDistance 10000000000
	  aspectRatio 100
	  focalDistance 1
	'''
	x=0
	y=0
	height=1000000
	height=200*bk*10000/0.6
	cam += '\nposition ' +str(x) + ' ' + str(y) + ' 999\n '
	cam += '\nheight ' + str(height) + '\n}\n\n'
	FreeCADGui.activeDocument().activeView().setCamera(cam)
	FreeCADGui.activeDocument().activeView().viewAxonometric()
	say("Kamera gesetzt")

	area.Length=size[0]*2
	area.Width=size[1]*2
	area.Placement=FreeCAD.Placement(FreeCAD.Vector(-size[0],-size[1],0.00),FreeCAD.Rotation(0.00,0.00,0.00,1.00))
	say("Area skaliert")
	wn=-1
	coways=len(ways)
	starttime=time.time()
	refresh=1000
	for w in ways:
		wid=w.params['id']

#		say(w.params)
#		say("way content")
#		for c in w.content:
#			say(c)

		building=False
		landuse=False
		highway=False
		wn += 1

		# nur teile testen
		#if wn <2000: continue

		nowtime=time.time()
		if wn!=0 and (nowtime-starttime)/wn > 0.5: 
			say(("way ---- # " + str(wn) + "/" + str(coways) + " time per house: " +  str(round((nowtime-starttime)/wn,2))))
		if progressbar:
			progressbar.setValue(int(0+100.0*wn/coways))

		st=""
		st2=""
		nr=""
		h=0
		ci=""

		for t in w.getiterator('tag'):
					try:
						if debug: say(t)
#						say(t.params['k'])
#						say(t.params['v'])

						if str(t.params['k'])=='building':
							building=True
							if st == '':
								st='building'

						if str(t.params['k'])=='landuse':
							landuse=True
							st=t.params['k']
							nr=t.params['v']

						if str(t.params['k'])=='highway':
							highway=True
							st=t.params['k']

						if str(t.params['k'])=='addr:city':
							ci=t.params['v']

						if str(t.params['k'])=='name':
							zz=t.params['v']
							nr=beaustring(zz)
						if str(t.params['k'])=='ref':
							zz=t.params['v']
							nr=beaustring(zz)+" /"

						if str(t.params['k'])=='addr:street':
							zz=t.params['v']
							st2=" "+beaustring(zz)
						if str(t.params['k'])=='addr:housenumber':
							nr=str(t.params['v'])

						if str(t.params['k'])=='building:levels':
							if h==0:
								h=int(str(t.params['v']))*1000*3
						if str(t.params['k'])=='building:height':
							h=int(str(t.params['v']))*1000

					except:
						sayErr("unexpected error ######################################################")

		name=str(st) + " " + str(nr)
		name=str(st) + st2+ " " + str(nr) 
		if name==' ':
			name='landuse xyz'
		if debug: say(("name ",name))
		#say(name,zz,nr,ci)

		#generate pointlist of the way
		polis=[]
		height=None

		llpoints=[]
#		say("get nodes",w)
		for n in w.getiterator('nd'):
#			say(n.params)
			m=nodesbyid[n.params['ref']]
			llpoints.append([n.params['ref'],m.params['lat'],m.params['lon']])
		if elevation:
			say("get heights for " + str(len(llpoints)))
			heights=getHeights(llpoints)

		for n in w.getiterator('nd'):
			p=points[str(n.params['ref'])]
			if building and elevation:
				if not height:
					try:
						height=heights[m.params['lat']+' '+m.params['lon']]*1000 - baseheight
					except:
						sayErr("---no height avaiable for " + m.params['lat']+' '+m.params['lon'])
						height=0
				p.z=height
			polis.append(p)

		#create 2D map
		pp=Part.makePolygon(polis)
		Part.show(pp)
		z=App.ActiveDocument.ActiveObject
		z.Label="w_"+wid

		if name==' ':
			g=App.ActiveDocument.addObject("Part::Extrusion",name)
			g.Base = z
			g.ViewObject.ShapeColor = (1.00,1.00,0.00)
			g.Dir = (0,0,10)
			g.Solid=True
			g.Label='way ex '

		if building:
			g=App.ActiveDocument.addObject("Part::Extrusion",name)
			g.Base = z
			g.ViewObject.ShapeColor = (1.00,1.00,1.00)

			if h==0:
				h=10000
			g.Dir = (0,0,h)
			g.Solid=True
			g.Label=name

			obj = FreeCAD.ActiveDocument.ActiveObject
			inventortools.setcolors2(obj)

		if landuse:
			g=App.ActiveDocument.addObject("Part::Extrusion",name)
			g.Base = z
			if nr == 'residential':
				g.ViewObject.ShapeColor = (1.00,.60,.60)
			elif nr == 'meadow':
				g.ViewObject.ShapeColor = (0.00,1.00,0.00)
			elif nr == 'farmland':
				g.ViewObject.ShapeColor = (.80,.80,.00)
			elif nr == 'forest':
				g.ViewObject.ShapeColor = (1.0,.40,.40)
			g.Dir = (0,0,0.1)
			g.Label=name
			g.Solid=True

		if highway:
			g=App.ActiveDocument.addObject("Part::Extrusion","highway")
			g.Base = z
			g.ViewObject.LineColor = (0.00,.00,1.00)
			g.ViewObject.LineWidth = 10
			g.Dir = (0,0,0.2)
			g.Label=name
		refresh += 1
		if os.path.exists("/tmp/stop"):

			sayErr("notbremse gezogen")
			FreeCAD.w=w
			raise Exception("Notbremse Manager main loop")

		if refresh >3:
			FreeCADGui.updateGui()
			# FreeCADGui.SendMsgToActiveView("ViewFit")
			refresh=0


	FreeCAD.activeDocument().recompute()
	FreeCADGui.updateGui()
	FreeCAD.activeDocument().recompute()

	if status:
		status.setText("import finished.")
	if progressbar:
			progressbar.setValue(100)

	organize()

	endtime=time.time()
	say(("running time ", int(endtime-starttime),  " count ways ", coways))
	return True



import FreeCAD,FreeCADGui
import WebGui


#import geodat.import_osm
#reload(geodat.import_osm)

'''
{
   "error_message" : "You have exceeded your daily request quota for this API. We recommend registering for a key at the Google Developers Console: https://console.developers.google.com/",
   "results" : [],
   "status" : "OVER_QUERY_LIMIT"
}

'''

## the dialog layout as miki string
#

s6='''
#VerticalLayoutTab:
MainWindow:
#DockWidget:
	VerticalLayout:
		id:'main'
		setFixedHeight: 600
		setFixedWidth: 730
		setFixedWidth: 654
		move:  PySide.QtCore.QPoint(3000,100)


		HorizontalLayout:
			setFixedHeight: 50
			QtGui.QLabel:
				setFixedWidth: 600

		QtGui.QLabel:
			setText:"C o n f i g u r a t i o n s"
			setFixedHeight: 20
		QtGui.QLineEdit:
			setText:"50.340722, 11.232647"
#			setText:"50.3736049,11.191643"
#			setText:"50.3377879,11.2104096"
			id: 'bl'
			setFixedHeight: 20
			textChanged.connect: app.getSeparator
		QtGui.QLabel:
		QtGui.QLabel:
			setText:"S e p a r a t o r"
			setFixedHeight: 20
		QtGui.QLineEdit:
			id:'sep'
			setPlaceholderText:"Enter separators separated by symbol: |   example: @|,|:"
			setToolTip:"<nobr>Enter separators separated by symbol: |</nobr><br>example: @|,|:"
			setFixedHeight: 20

		QtGui.QPushButton:
			setText:"Help"
			setFixedHeight: 20
			clicked.connect: app.showHelpBox

		QtGui.QLabel:
		QtGui.QPushButton:
			setText:"Get Coordinates "
			setFixedHeight: 20
			clicked.connect: app.getCoordinate



		QtGui.QLabel:	
		HorizontalLayout:
			setFixedHeight: 50
			QtGui.QLabel:
				setFixedWidth: 150
			QtGui.QLineEdit:
				id:'lat'
				setText:"50.340722"
				setFixedWidth: 100
			QtGui.QPushButton:
				id:'swap'
				setText:"swap"
				setFixedWidth: 50
				clicked.connect: app.swap
			QtGui.QLineEdit:
				id:'long'
				setText:"11.232647"
				setFixedWidth: 100
		
		HorizontalLayout:
			setFixedHeight: 50
			QtGui.QLabel:
				setFixedWidth: 155
			QtGui.QLabel:
				setText:"Latitude"
				setFixedWidth: 100
			QtGui.QLabel:
				setFixedWidth: 50
			QtGui.QLabel:
				setText:"Longitude"
				setFixedWidth: 100

		QtGui.QLabel:
		QtGui.QLabel:
		QtGui.QCheckBox:
			id:'elevation'
			setText: 'Process Elevation Data'

		QtGui.QLabel:
		QtGui.QLabel:
			setText:"Length of the Square 0 km ... 4 km, default 0.5 km  "

		QtGui.QLabel:
			setText:"Distance is 0.5 km."
			id: "showDistanceLabel"
		QtGui.QSlider:
			id:'s'
			setFixedHeight: 20
			setOrientation: PySide.QtCore.Qt.Orientation.Horizontal
			setMinimum: 0
			setMaximum: 40
			setTickInterval: 1
			setValue: 5
			setTickPosition: QtGui.QSlider.TicksBothSides
			valueChanged.connect: app.showDistanceOnLabel

		QtGui.QLabel:
		QtGui.QLabel:
			id:'running'
			setText:"R u n n i n g   Please Wait  "
			setVisible: False

		QtGui.QPushButton:
			id:'runbl1'
			setText: "Download values"
			setFixedHeight: 20
			clicked.connect: app.downloadData
			setVisible: True

		QtGui.QPushButton:
			id:'runbl2'
			setText: "Apply values"
			setFixedHeight: 20
			clicked.connect: app.applyData
			setVisible: False


		QtGui.QPushButton:
			setText: "Show openstreet map in web browser"
			clicked.connect: app.showMap
			setFixedHeight: 20

		QtGui.QLabel:
		QtGui.QLabel:
			setText:"P r e d e f i n e d   L o c a t i o n s"
#		QtGui.QLabel:

		QtGui.QRadioButton:
			setText: "Sonneberg Outdoor Inn"
			clicked.connect: app.run_sternwarte

		QtGui.QRadioButton:
			setText: "Coburg university and school "
			clicked.connect: app.run_co2

		QtGui.QRadioButton:
			setText: "Berlin Alexanderplatz/Haus des Lehrers"
			clicked.connect: app.run_alex

		QtGui.QRadioButton:
			setText: "Berlin Spandau"
			clicked.connect: app.run_spandau

		QtGui.QRadioButton:
			setText: "Paris Rue de Seine"
			clicked.connect: app.run_paris

		QtGui.QRadioButton:
			setText: "Tokyo near tower"
			clicked.connect: app.run_tokyo

		QtGui.QLabel:
		QtGui.QLabel:
			setText:"P r o c e s s i n g:"
			id: "status"
			setFixedHeight: 20

		QtGui.QLabel:
			setText:"---"
			id: "status"
		QtGui.QProgressBar:
			id: "progb"
			setFixedHeight: 20

'''


## the gui backend

class MyApp(object):
	'''execution layer of the Gui'''


	def run(self,b,l):
		'''run(self,b,l) imports area with center coordinates latitude b, longitude l'''
		s=self.root.ids['s'].value()
		key="%0.7f" %(b) + "," + "%0.7f" %(l)
		self.root.ids['bl'].setText(key)
		import_osm2(b,l,float(s)/10,self.root.ids['progb'],self.root.ids['status'],False)

	def run_alex(self):
		'''imports Berlin Aleancderplatz'''
		self.run(52.52128,l=13.41646)

	def run_paris(self):
		'''imports Paris'''
		self.run(48.85167,2.33669)

	def run_tokyo(self):
		'''imports Tokyo near tower'''
		self.run(35.65905,139.74991)

	def run_spandau(self):
		'''imports Berlin Spandau'''
		self.run(52.508,13.18)

	def run_co2(self):
		'''imports  Coburg Univerity and School'''
		self.run(50.2631171, 10.9483)

	def run_sternwarte(self):
		'''imports Sonneberg Neufang observatorium'''
		self.run(50.3736049,11.191643)


	def showHelpBox(self):
		msg=PySide.QtGui.QMessageBox()
		msg.setText("<b>Help</b>")
		msg.setInformativeText("Import_osm map dialogue box can also accept links from following sites in addition to (latitude, longitude)<ul><li>OpenStreetMap</li><br>e.g. https://www.openstreetmap.org/#map=15/30.8611/75.8610<br><li>Google Maps</li><br>e.g. https://www.google.co.in/maps/@30.8611,75.8610,5z<br><li>Bing Map</li><br>e.g. https://www.bing.com/maps?osid=339f4dc6-92ea-4f25-b25c-f98d8ef9bc45&cp=30.8611~75.8610&lvl=17&v=2&sV=2&form=S00027<br><li>Here Map</li><br>e.g. https://wego.here.com/?map=30.8611,75.8610,15,normal<br><li>(latitude,longitude)</li><br>e.g. 30.8611,75.8610</ul><br>If in any case, the latitude & longitudes are estimated incorrectly, you can use different separators in separator box or can put latitude & longitude directly into their respective boxes.")
		msg.exec_()

	def showHelpBoxY(self):
		#self.run_sternwarte()
		say("showHelpBox called")

	def getSeparator(self):
		bl=self.root.ids['bl'].text()
		if bl.find('openstreetmap.org') != -1:
			self.root.ids['sep'].setText('/')
		elif bl.find('google.co') != -1:
			self.root.ids['sep'].setText('@|,')
		elif bl.find('bing.com') != -1:
			self.root.ids['sep'].setText('=|~|&')
		elif bl.find('wego.here.com') != -1:
			self.root.ids['sep'].setText('=|,')
		elif bl.find(',') != -1:
			self.root.ids['sep'].setText(',')
		elif bl.find(':') != -1:
			self.root.ids['sep'].setText(':')
		elif bl.find('/') != -1:
			self.root.ids['sep'].setText('/')



	def getCoordinate(self):
		sep=self.root.ids['sep'].text()
		bl=self.root.ids['bl'].text()
		import re
		spli=re.split(sep, bl)
		flag='0'
		for x in spli:
			try:
				float(x)
				if x.find('.') != -1:
					if flag=='0':
						self.root.ids['lat'].setText(x)
						flag='1'
					elif flag=='1':
						self.root.ids['long'].setText(x)
						flag='2'
			except:
				flag=flag
		



	def swap(self):
		tmp1=self.root.ids['lat'].text()
		tmp2=self.root.ids['long'].text()
		self.root.ids['long'].setText(tmp1)
		self.root.ids['lat'].setText(tmp2)



	def downloadData(self):
		'''download data from osm'''
		button=self.root.ids['runbl1']
		button.hide()
		br=self.root.ids['running']
		br.show()


		bl_disp=self.root.ids['lat'].text()
		b=float(bl_disp)
		bl_disp=self.root.ids['long'].text()
		l=float(bl_disp)


		s=self.root.ids['s'].value()
		elevation=self.root.ids['elevation'].isChecked()

		rc= import_osm2(float(b),float(l),float(s)/10,self.root.ids['progb'],self.root.ids['status'],elevation)
		if not rc:
			button=self.root.ids['runbl2']
			button.show()
		else:
			button=self.root.ids['runbl1']
			button.show()
		br.hide()



	def applyData(self):
		'''apply downloaded or cached data to create the FreeCAD models'''
		button=self.root.ids['runbl2']
		button.hide()
		br=self.root.ids['running']
		br.show()
		
		bl_disp=self.root.ids['lat'].text()
		b=float(bl_disp)
		bl_disp=self.root.ids['long'].text()
		l=float(bl_disp)
		

		s=self.root.ids['s'].value()
		elevation=self.root.ids['elevation'].isChecked()

		import_osm2(float(b),float(l),float(s)/10,self.root.ids['progb'],self.root.ids['status'],elevation)
		button=self.root.ids['runbl1']
		button.show()
		br.hide()



	def showMap(self):
		'''open a webbrowser window and display the openstreetmap presentation of the area'''

		bl_disp=self.root.ids['lat'].text()
		b=float(bl_disp)
		bl_disp=self.root.ids['long'].text()
		l=float(bl_disp)

		s=self.root.ids['s'].value()
		WebGui.openBrowser( "http://www.openstreetmap.org/#map=16/"+str(b)+'/'+str(l))

	def showDistanceOnLabel(self):
		distance=self.root.ids['s'].value()
		showDistanceLabel=self.root.ids['showDistanceLabel']
		showDistanceLabel.setText('Distance is '+str(float(distance)/10)+'km.')

## the gui startup

def mydialog():
	''' starts the gui dialog '''
	app=MyApp()

	import geodat.miki as miki
	reload(miki)


	miki=miki.Miki()
	miki.app=app
	app.root=miki

	miki.parse2(s6)
	miki.run(s6)
	return miki


def importOSM():
	mydialog()



'''
#-----------------
# verarbeiten 

import xml.etree.ElementTree as ET

fn='/home/thomas/.FreeCAD//geodat3/50.340722-11.232647-0.015'
#tree = ET.parse(fn)

data_as_string=''<?xml version="1.0"?><data>
    <country name="Liechtenstein">
        <rank>1</rank>
        <year>2008</year>
        <gdppc>141100</gdppc>
        <neighbor name="Austria" direction="E"/>
        <neighbor name="Switzerland" direction="W"/>
    </country>
    <country name="Singapore">
        <rank>4</rank>
        <year>2011</year>
        <gdppc>59900</gdppc>
        <neighbor name="Malaysia" direction="N"/>
    </country>
    <country name="Panama">
        <rank>68</rank>
        <year>2011</year>
        <gdppc>13600</gdppc>
        <neighbor name="Costa Rica" direction="W"/>
        <neighbor name="Colombia" direction="E"/>
    </country>
</data>
''

root = ET.fromstring(data_as_string)


for element in tree.getiterator('node'):
    print(element.attrib)


root = tree.getroot()
ET.dump(root)

for elem in root:
	print (elem.tag,elem.attrib)
#----------------
'''

