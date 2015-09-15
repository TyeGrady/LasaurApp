#
# new dxf parser using dxfgrabber.  Loosely based on work by Stephan
# and the lasersaur team.
#
#
__author__ = 'jet <jet@allartburns.org>'

import math
import io
import StringIO

import dxfgrabber

import sys
import linecache

class DXFParser:
    """Parse DXF using dxfgrabber-0.7.4

    Usage:
    reader = DXFParser(tolerance)
    returns dictionary of layers using found colors
    """

    def __init__(self, tolerance):
        self.debug = True
        # tolerance settings, used in tessalation, path simplification, etc         
        self.tolerance = tolerance
        self.tolerance2 = tolerance**2

        # parsed path data, paths by color
        # {'#ff0000': [[path0, path1, ..], [path0, ..], ..]}
        # Each path is a list of vertices which is a list of two floats.        
        # using iso pen colors from dxfwrite
        # 0 is undefined in DXF, it specifies no color, not black
        # 1 red
        # 2 yellow
        # 3 green
        # 4 cyan
        # 5 blue
        # 6 magenta
        # 7 black
        # TODO: support up to 255 colors
        

        self.colorLayers = {'#FF0000':[],
                          '#FFFF00':[],
                          '#00FF00':[],
                          '#00FFFF':[],
                          '#0000FF':[],
                          '#CC33CC':[],
                          '#000000':[]}

        self.red_colorLayer = self.colorLayers['#FF0000']
        self.yellow_colorLayer = self.colorLayers['#FFFF00']
        self.green_colorLayer = self.colorLayers['#00FF00']
        self.cyan_colorLayer = self.colorLayers['#00FFFF']
        self.blue_colorLayer = self.colorLayers['#0000FF']
        self.magenta_colorLayer = self.colorLayers['#CC33CC']
        self.black_colorLayer = self.colorLayers['#000000']
        
        #Original snippets from stefanix dxf reader
        self.boundarys = {'#FF0000':[], 
                          '#FFFF00':[],
                          '#00FF00':[],
                          '#00FFFF':[],
                          '#0000FF':[],
                          '#CC33CC':[],
                          '#000000':[]}
        
        #Added snippets for multiple color 'boundarys'
        self.red_boundarys = self.boundarys['#FF0000']
        self.yellow_boundarys = self.boundarys['#FFFF00']
        self.cyan_boundarys = self.boundarys['#00FFFF']
        self.blue_boundarys = self.boundarys['#0000FF']
        self.magenta_boundarys = self.boundarys['#CC33CC']
        self.green_boundarys = self.boundarys['#00FF00']
        self.black_boundarys = self.boundarys['#000000']
        
        self.metricflag = 1
        self.linecount = 0
        self.line = ''
        self.dxfcode = ''

    def parse(self, dxfInput):
        dxfStripped = dxfInput.replace('\r\n','\n')
        dxfStream = io.StringIO(unicode(dxfStripped.replace('\r\n','\n')))
        
        infile = dxfgrabber.read(dxfStream)
        if not infile:
            print ("DXFGRABBER FAIL")
            raise ValueError

        # set up unit conversion
        self.units = infile.header.setdefault('$INSUNITS', 1)
        if self.units == 0:
            self.unitsString = "undefined, assuming inches"
        elif self.units == 1:
            self.unitsString = "inches"
        elif self.units == 4:
            self.unitsString = "mm"
        else:
            print("DXF units: ", self.units, " unsupported")
            raise ValueError
        
        if self.debug:
            print("DXF version: {}".format(infile.dxfversion))
            print("header var count: ", len(infile.header))
            print("layer count: ", len(infile.layers)) 
            print("block def count: ", len(infile.blocks))
            print("entitiy count: ", len(infile.entities))
            print("units: ", self.unitsString)
        
        #Iterate through and print layers name
        global Layer_names
        Layer_names = infile.layers.names()
        if self.debug:
            print("Layer Names: ", Layer_names)
            i = 1
            n = len(infile.layers)
            while i < n:
                print("iter value:", i)
                print("layer name: ", Layer_names[i])
                i = i + 1
        
        for entity in infile.entities:
            if entity.dxftype == "LINE":
                if self.debug:
                    print("Line Entity")
                    print("Entity Layer:", entity.layer)
                self.addLine(entity)
            elif entity.dxftype == "ARC":
                if self.debug:
                    print("Arc Entity")
                    print("Entity Layer:", entity.layer)
                self.addArc(entity)
            elif entity.dxftype == "CIRCLE":
                if self.debug:
                    print("Circle Entity")
                    print("Entity Layer:", entity.layer)
                self.addCircle(entity)
            elif entity.dxftype == "LWPOLYLINE":
                if self.debug:
                    print("LWPolyLine Entity")
                    print("Entity Layer:", entity.layer)
                self.addPolyLine(entity)
            elif entity.dxftype == "SPLINE":
                if self.debug:
                    print("Spline Entity")
                    print("Entity Layer:", entity.layer)
                print("TODO ADD: ", entity.dxftype)
                #self.addSpline(entity)
            else:
                if self.debug:
                    print("unknown entity: ", entity.dxftype)
                    print("Entity Layer:", entity.layer)

                
        print "Done!"
        
        #TODO: teach the UI to report units read in the file
        #return {'boundarys':self.returnColorLayers, 'units':self.unitsString}
        
        #Original snippets from stefanif dxfreader
        return {'boundarys':self.boundarys}

    ################
    # Translate each type of entity (line, circle, arc, lwpolyline)

    def addLine(self, entity):
        path = [[self.unitize(entity.start[0]),
                 self.unitize(entity.start[1])],
                [self.unitize(entity.end[0]),
                 self.unitize(entity.end[1])]]
        self.add_path_by_layer (entity.layer, path)

    def addArc(self, entity):
        cx = self.unitize(entity.center[0])
        cy = self.unitize(entity.center[1])
        r = self.unitize(entity.radius)
        theta1deg = entity.startangle
        theta2deg = entity.endangle
        thetadiff = theta2deg - theta1deg
        if thetadiff < 0 :
            thetadiff = thetadiff + 360
        large_arc_flag = int(thetadiff >= 180)
        sweep_flag = 1
        theta1 = theta1deg/180.0 * math.pi;
        theta2 = theta2deg/180.0 * math.pi;
        x1 = cx + r * math.cos(theta1)
        y1 = cy + r * math.sin(theta1)
        x2 = cx + r * math.cos(theta2)
        y2 = cy + r * math.sin(theta2)
        path = []
        self.makeArc(path, x1, y1, r, r, 0, large_arc_flag, sweep_flag, x2, y2)
        self.add_path_by_layer (entity.layer, path)

    def addCircle(self, entity):
        cx = self.unitize(entity.center[0])
        cy = self.unitize(entity.center[1])
        r = self.unitize(entity.radius)
        path = []
        self.makeArc(path, cx-r, cy, r, r, 0, 0, 0, cx, cy+r)
        self.makeArc(path, cx, cy+r, r, r, 0, 0, 0, cx+r, cy)
        self.makeArc(path, cx+r, cy, r, r, 0, 0, 0, cx, cy-r)
        self.makeArc(path, cx, cy-r, r, r, 0, 0, 0, cx-r, cy)
        self.add_path_by_layer (entity.layer, path)

    def addPolyLine(self, entity):
        path = []
        for point in entity.points:
            path.append([self.unitize(point[0]),
                        self.unitize(point[1])])
        self.add_path_by_layer(entity.layer, path)

    def add_path_by_layer(self, layer, path):
        print("Trying to add path.")
        string = str(layer)
        list = Layer_names
        for s in list:
            if string in str(s):
                layer_index = list.index(s) + 1
                if self.debug:
                    print(layer)
                    print("Layer Index:", layer_index)
        
        if layer_index == 1:
            #self.red_colorLayer.append(path)
            self.red_boundarys.append(path)
        elif layer_index == 2:
            #self.yellow_colorLayer.append(path)
            self.yellow_boundarys.append(path)
        elif layer_index == 3:
            #self.green_colorLayer.append(path)
            self.green_boundarys.append(path)
        elif layer_index == 4:
            #self.cyan_colorLayer.append(path)
            self.cyan_boundarys.append(path)
        elif layer_index == 5:
            #self.blue_colorLayer.append(path)
            self.blue_boundarys.append(path)
        elif layer_index == 6:
            #self.magenta_colorLayer.append(path)
            self.magenta_boundarys.append(path)
        elif layer_index == 7:
            #self.black_colorLayer.append(path)
            self.black_boundarys.append(path)
        else:
            print("More than 7 layers.... TBD")
            print("Making it magenta...")
            self.magenta_colorLayer.append(path)
            
    def complain_spline(self):
        print "Encountered a SPLINE at line", self.linecount
        print "This program cannot handle splines at present."
        print "Convert the spline to an LWPOLYLINE using Save As options in SolidWorks."
        raise ValueError

    def complain_invalid(self):
        print "Skipping unrecognized element '" + self.line + "' on line", self.linecount

    def makeArc(self, path, x1, y1, rx, ry, phi, large_arc, sweep, x2, y2):
        # Implemented based on the SVG implementation notes
        # plus some recursive sugar for incrementally refining the
        # arc resolution until the requested tolerance is met.
        # http://www.w3.org/TR/SVG/implnote.html#ArcImplementationNotes
        cp = math.cos(phi)
        sp = math.sin(phi)
        dx = 0.5 * (x1 - x2)
        dy = 0.5 * (y1 - y2)
        x_ = cp * dx + sp * dy
        y_ = -sp * dx + cp * dy
        r2 = ((rx*ry)**2-(rx*y_)**2-(ry*x_)**2) / ((rx*y_)**2+(ry*x_)**2)
        if r2 < 0:
            r2 = 0
        r = math.sqrt(r2)
        if large_arc == sweep:
            r = -r
        cx_ = r*rx*y_ / ry
        cy_ = -r*ry*x_ / rx
        cx = cp*cx_ - sp*cy_ + 0.5*(x1 + x2)
        cy = sp*cx_ + cp*cy_ + 0.5*(y1 + y2)
        
        def _angle(u, v):
            a = math.acos((u[0]*v[0] + u[1]*v[1]) /
                            math.sqrt(((u[0])**2 + (u[1])**2) *
                            ((v[0])**2 + (v[1])**2)))
            sgn = -1
            if u[0]*v[1] > u[1]*v[0]:
                sgn = 1
            return sgn * a
    
        psi = _angle([1,0], [(x_-cx_)/rx, (y_-cy_)/ry])
        delta = _angle([(x_-cx_)/rx, (y_-cy_)/ry], [(-x_-cx_)/rx, (-y_-cy_)/ry])
        if sweep and delta < 0:
            delta += math.pi * 2
        if not sweep and delta > 0:
            delta -= math.pi * 2
        
        def _getVertex(pct):
            theta = psi + delta * pct
            ct = math.cos(theta)
            st = math.sin(theta)
            return [cp*rx*ct-sp*ry*st+cx, sp*rx*ct+cp*ry*st+cy]        
        
        # let the recursive fun begin
        def _recursiveArc(t1, t2, c1, c5, level, tolerance2):
            def _vertexDistanceSquared(v1, v2):
                return (v2[0]-v1[0])**2 + (v2[1]-v1[1])**2
            
            def _vertexMiddle(v1, v2):
                return [ (v2[0]+v1[0])/2.0, (v2[1]+v1[1])/2.0 ]

            if level > 18:
                # protect from deep recursion cases
                # max 2**18 = 262144 segments
                return

            tRange = t2-t1
            tHalf = t1 + 0.5*tRange
            c2 = _getVertex(t1 + 0.25*tRange)
            c3 = _getVertex(tHalf)
            c4 = _getVertex(t1 + 0.75*tRange)
            if _vertexDistanceSquared(c2, _vertexMiddle(c1,c3)) > tolerance2:
                _recursiveArc(t1, tHalf, c1, c3, level+1, tolerance2)
            path.append(c3)
            if _vertexDistanceSquared(c4, _vertexMiddle(c3,c5)) > tolerance2:
                _recursiveArc(tHalf, t2, c3, c5, level+1, tolerance2)
                
        t1Init = 0.0
        t2Init = 1.0
        c1Init = _getVertex(t1Init)
        c5Init = _getVertex(t2Init)
        path.append(c1Init)
        _recursiveArc(t1Init, t2Init, c1Init, c5Init, 0, self.tolerance2)
        path.append(c5Init)

    def unitize(self, value):
        if self.units == 0 or self.units == 1:
            return value * 25.4
        elif self.units == 4:
            return value
        print ("don't know how to convert units ", units)
        raise ValueError
