# -*- coding: utf-8 -*-

# ddump - dump truetype font for use in OpenSCAD 3d, for 3d printing
# public domain. don b, 2011

# this only works with trutype fonts, and their 'quadratic beziers'
# (3 control points, aka conic arc beziers aka parabolics )
#
# it needs freetype-py from Nicolas Rougier:
# http://code.google.com/p/freetype-py/
#
#
# please see the following:
# http://en.wikipedia.org/wiki/B%C3%A9zier_curve
# http://www.freetype.org/freetype2/docs/glyphs/glyphs-6.html
# http://www.thingiverse.com/thing:8443
#
# especially 
# http://en.wikipedia.org/wiki/File:Bezier_2_big.gif by Phil Tregoning
#
# and for inner/outer contours (clockwise/counterclockwise)
# http://lists.gnu.org/archive/html/freetype/2001-11/msg00055.html
# Henry Maddocks' FTGL, especially Contour.cpp , Sam H and Éric B
# https://sourceforge.net/apps/mediawiki/ftgl/index.php?title=Main_Page

# this depends on:
# freetype-py by Nicolas Rougier
# http://code.google.com/p/freetype-py/
# if you can't get freetype-py 'setup.py' to work on your system, 
# go into its 'init' portion and # comment out the offending labels
# it might work. 


#
# Terminology 
#
# glyph: the 'image', or 'picture', of a character
#
# glyphs are made of various parts, called 'contours'
#
# contour: an object consisting of a sequence of points for polygons,
#   as well as some curves for making bezier curves. 
# points: the points of the main 'skeleton' of the contour
# tags: a number assinged to each point in a contour to give info about it
#
# curve: a sequence of 3 points, to make a bezier curve with
# curve_tags: a number assigned to each curve in a sequence of curves 
#  to give info about it
#

#
# 
# Bugs
#
# anything with 'intersecting polygons' does not work when
# opened in OpenSCAD. 
#
# examples: 
# 0x1f024 Mahjong tile, bamboo etc
# 0x1d49f math cursive D

# good character to test bugs with:
# unicode, name
# 0x26c3 draughs puck
# 0x263a smiley face
# 0x1f019 Mahjong tile
# 0x0044  Basic Latin D
# 0x2619 floral heart bullet

import os, sys, math
from freetype import *
from optparse import OptionParser

VERSION = "0.1"

def halfway_between(p1,p2):
	newx = (p1[0]+p2[0])/2.0
	newy = (p1[1]+p2[1])/2.0
	return (newx,newy)

def scad_format(s):
	return str(s).replace('(','[').replace(')',']')

def r2d(angl):
	return angl/(2*math.pi)*360.0

def getangle(vector):
        x,y=vector[0],vector[1]
        anglerad=0
        if x==0:
                if y>0: anglerad = math.pi/2.0
                elif y<0: anglerad = -math.pi/2.0
        else:
                anglerad = math.atan(float(y)/float(x))
                if x<0 and y>=0: anglerad=math.pi+anglerad
                elif x<0 and y<0: anglerad=-math.pi+anglerad
        return anglerad

def rotate(vector,radians):
        x,y=vector[0],vector[1]
        newx=x*math.cos(radians) - y*math.sin(radians)
        newy=x*math.sin(radians) + y*math.cos(radians)
        return [newx,newy]

def getdiff(point1,point2):
	return [point2[0]-point1[0],point2[1]-point1[1]]

debug_angle = False
def getangle_change(p0,p1,p2):
	vect1 = getdiff(p0,p1)
	angle1 = getangle(vect1)
	p1new = rotate(p1,-angle1)
	p2new = rotate(p2,-angle1)
	vectnew = getdiff(p1new,p2new)
	angle2 = getangle(vectnew)
	if debug_angle:
		print p0,p1,p2, ':',r2d(angle1), 
		print r2d(getangle(getdiff(p1,p2))),
		print r2d(angle2)
	return angle2

def curvesleft(p0,p1,p2):
	# does the line betwen p1 and p2 curve 'left' of where p0-p1 was heading?
	result = True
	angle_change = r2d(getangle_change(p0,p1,p2))
	if angle_change<0: 
		result = False
	else:
		result = True
	# print '//', p0, p1, p2, angle1, angle2, angle2-angle1
	return result

def testmath():
	testa = 3.14159/6
	for theta in range(0,360,30):
		angl = (theta/360.0)*2*3.14159
		y=math.sin(angl)*1
		x=math.cos(angl)*1
		print theta,angl,findangle(x,y),x,y,compareangle(testa,angl)

VPOINT_SKIPME=3
debug_virtual_points = False
def create_virtual_points(points,tags):
	dbg = debug_virtual_points
	if dbg: print 'creating virtual "on the line" points'
	np = len(points)
	newpoints = []
	newtags = []
	for i in range(0,len(points)):
		#print i,points[i]
		newpoints+=[points[i]]
		newtags+=[tags[i]]
		if tags[i]==0 and tags[(i+1)%np]==0: # curve
			newpoints+=[halfway_between(points[i],points[(i+1)%np])]
			newtags+=[2]
		if tags[i]==1 and tags[(i+1)%np]==1: # straight line segment
			newpoints+=[halfway_between(points[i],points[(i+1)%np])]
			newtags+=[VPOINT_SKIPME]
	if newtags[0]==0:
		if dbg: print 'rotating. tags: ',newtags,'\npts: ',newpoints
		newtags.insert(0,newtags.pop())
		newpoints.insert(0,newpoints.pop())
		if dbg: print 'rotated. tags: ',newtags,'\npts: ',newpoints
	if dbg:
		print 'points:   ',points
		print 'newpoints:',newpoints
		print 'tags:   ',tags
		print 'newtags:',newtags
	return newpoints, newtags

def create_curves(newpoints,newtags):
	dbg = debug_curves
	if dbg: print 'creating bezier curve triplets, from points + tags'
	np = len(newpoints)
	curves = []
	curvetags = []
	for i in range(0,len(newpoints),2):
		triplet = [newtags[i],newtags[(i+1)%np],newtags[(i+2)%np]]
		if triplet[1]==VPOINT_SKIPME:
			continue
		else:
			p0 = newpoints[i]
			p1 = newpoints[(i+1)%np]
			p2 = newpoints[(i+2)%np]
			curves += [[ p0,p1,p2 ] ]
			if curvesleft(p0,p1,p2): 
				curvetags+=['l']
			else: 
				curvetags+=['r']
	if dbg: print 'pts: ',newpoints,'\ncurves: ',curves
	if dbg: print 'pt tags: ',newtags,'\ncurvetags: ',curvetags
	return curves, curvetags


def openscad_base():
	basetxt = '''include <font_base.scad>'''
	return basetxt.strip()

def make_openscad_polygon(tabs,points,height):
	s='translate([0,0,-' + str(height) + '/2]) '
	s+= tabs+'linear_extrude(height='+str(height)+') polygon( points=[' +os.linesep
	#s+= tabs+'polygon( points=[' +os.linesep
	for i in range(0,len(points)-2,3):
		s+=tabs+'\t'
		s+=scad_format(points[i])+', '
		s+=scad_format(points[i+1])+', '
		s+=scad_format(points[i+2])+', '
		s+=os.linesep
	s+=tabs+'\t'
	for j in range(i+3,len(points)):
		s+=scad_format(points[j])+','
	s=s.rstrip(os.linesep)
	s+= ' ]);' + os.linesep
	return s

def make_openscad_curves(tabs,curves,height):
	s='translate([0,0,-' + str(height) + '/2]){ '+os.linesep
	for curve in curves:
		triplet = str(curve).strip('[').strip(']')
		s+= tabs+'BezConic('
		s+= scad_format(triplet) 
		s+= ',steps,'+str(height)+');' + os.linesep
	s+='}'+os.linesep
	return s

debug_composite=False
def make_chunks(contours):
	# composite glyphs. 
	# how it works
	# 0. clockwise contour = 'body', countercc = 'hole'
	# assume composites are ordered as follows:
	# cw, ccw, cw, cw, ccw, cw, ccw, ccw, ccw
	# i.e., each string of 'body...hole' is a separate 'chunk'
	# paint the chunks one by one, this will do the 'filling' properly
	dbg=debug_composite
	chunks={}
	i=0
	last=False
	prev_cw=contours[0].clockwise
	if dbg: 
		for c in contours:
			print str(c.clockwise)[0],
		for d in chunks.keys(): 
			num = len(chunks[d])
			vals = chunks[d]
			print '+=chunk',d,', num contours:',num
			for v in vals:	
				print '+===',v

	for c in contours:
		if prev_cw == False and c.clockwise==True:
			if dbg: print 'new ccw chunk, inc ',i,'to',i+1
			i+=1
		elif prev_cw == True and c.clockwise==True:
			if dbg: print 'no hole. new ccw chunk, inc ',i,'to',i+1
			i+=1
		else: # False, False   or   True, False
			if dbg: print 'stay in chunk',prev_cw,c.clockwise
		if chunks.has_key(i):
			if dbg: print 'had key',i,c.clockwise,',add to chunk'
			chunks[i] += [c]
		else:
			if dbg: print 'no key',i,c.clockwise, ',make new chunk'
			chunks[i] = [c]
		prev_cw = c.clockwise
	return chunks

def make_openscad_contour(contour,height):
	dbg = debug_contour_string = True
	s='module '+contour.name+'_skeleton() {\n'
	s+=make_openscad_polygon('\t',contour.points,height)
	s+='}\n\n'

	additive_curves,subtractive_curves =[],[]
	for i in range(0,len(contour.curves)):
		if contour.curvetags[i]=='l':
			additive_curves+=[contour.curves[i]]
		else:
			subtractive_curves+=[contour.curves[i]]

	s+='module '+contour.name+'_additive_curves(steps=2) {\n'
	s+=make_openscad_curves('\t',additive_curves,height)
	s+='}\n\n'

	s+='module '+contour.name+'_subtractive_curves(steps=2) {\n'
	s+=make_openscad_curves('\t',subtractive_curves,height)
	s+='}\n\n'

	s2='''module contourname(steps=2) {
	difference() {
		union() {
			contourname_skeleton();
			contourname_additive_curves(steps);
		}
		scale([1,1,1.1]) contourname_subtractive_curves(steps);
	}
}

'''
	s2=s2.replace('contourname',contour.name)
	if not contour.clockwise:
		s2=s2.replace('subtractive','xxxxxxx')
		s2=s2.replace('additive','subtractive')
		s2=s2.replace('xxxxxxx','additive')
	s+=s2
	return s

def make_openscad_chunk(chunkname,bodies,holes):
	s='''module chunkname(steps=2) {
	difference() {
		///body
		///holes
	}
}

'''
	s=s.replace('chunkname',chunkname)
	bs,hs='',''
	for contour in bodies:
		bs+=contour.name+'(steps);\n\t'
	for contour in holes:
		hs+='scale([1,1,1.1]) '+contour.name+'(steps);\n\t'
	s=s.replace('///body',bs.rstrip())
	s=s.replace('///holes',hs.rstrip())
	return s

debug_chunks=True

def make_openscad_commands(charcode, module, contours, chunks, bbox,height):
	s=''
	dbg = debug_chunks
	dbgs = ''

	for c in contours:
		s+=make_openscad_contour(c,height)

	counter=0
	for k in chunks.keys():
		chunk = chunks[k]
		chunkname = module + '_chunk'+str(k)+charcode
		bodies,holes = [],[]
		for contour in chunk:
			if contour.clockwise: bodies+=[contour]
			else: holes+=[contour]

		s+=make_openscad_chunk(chunkname,bodies,holes)
		#s+=make_openscad_chunk_debug_module(chunkname,bodies,holes)

	s+= module + '_bbox'+charcode+'='+str(bbox)+';\n\n'

	s+= 'module '+ module + '_letter'+charcode+'(detail=2) {'+os.linesep
	for key in chunks.keys():
		chunkname = module + '_chunk'+str(key)+charcode
		s+= '\t'+chunkname+'(steps=detail);'+os.linesep
	s+='} //end skeleton' + os.linesep*2
	# end composite handling

	#s+='letter();'+os.linesep
	#s+='letter_debug();'+os.linesep
	#s+='linear_extrude(height=10) letter();'+os.linesep
	return dbgs + s

debug_contours=False
def split_contours(charcode,module,points,point_tags,contour_indexes):
	contours = []
	if debug_contours: 
		print '//number of contours:', len(contour_indexes)
		print '//contour indexes:', contour_indexes
		print '//number of points:', len(points)
		print '//points',points
		print '//point tags',point_tags
		print '// point #, contour #, coords, tags:'
	counter = 0 
	for i in range(0,len(contour_indexes)):
		contour = Contour([],[])
		for j in range(counter,contour_indexes[i]+1):
			if debug_contours: print j,i,points[j],point_tags[j]
			contour.points+=[points[j]]
			contour.tags+=[point_tags[j]]
			counter += 1
		contour.name += module + '_contour'+str(i)+charcode
		contours += [contour]
	if debug_contours:
		for c in contours:
			print '---'
			print c
	return contours
	
class Contour:
	curves,curvetags,points,tags=[],[],[],[]
	clockwise,name = False,''
	def __init__(self,points=[],tags=[]):
		self.points,self.tags=points,tags
	def __repr__(self):
		s= 'contour. name: ' + self.name 
		s+= '\npoints: '+str(self.points)
		s+= '\npoint tags: '+str(self.tags)
		s+= '\ncurves:'+str(self.curves)
		s+= '\ncurve tags:'+str(self.curvetags)
		s+= '\nnpoints: '+str(len(self.points))
		s+= ' numtags: '+str(len(self.tags))
		s+= ' numcurves: '+str(len(self.curves))
		s+= ' numcurvetags: '+str(len(self.curvetags))
		s+= ' clockwise: '+str(self.clockwise)
		return s

debug_clockwise = False
def is_clockwise(contour):
	# loosely based on Henry Maddocks' FTGL, Contour.cpp, Sam H and Éric B
	# https://sourceforge.net/apps/mediawiki/ftgl/index.php?title=Main_Page
	# basically you go along the polygon, considering two vectors at a time.
	# one's head at the tail of the next. 
	# to figure out the 'change of direction' you rotate both vectors
	# until the first vector is 'flat' at angle 0. then find
	# the angle the second vector is resting vs the 0-line (axis)
	# if you add up all the 'change of direction' angles, you get
	# a negative or a positive number (-2*pi, 2pi ????). 
	# this tells you if its clockwise or ccw
	dbg = debug_clockwise
	if dbg: print 'clockwise? ',contour.name,'\npoints: ',contour.points
	angle_total=0
	ps = contour.points
	np = len(ps)
	for i in range(0,len(contour.points)):
		change = getangle_change(ps[i],ps[(i+1)%np],ps[(i+2)%np])
		if abs(change-math.pi)<0.000001:
			if abs(angle_total+math.pi)<0.00001:
				if dbg: '180 deg turn, guessing...'
				change=-1*change
		angle_total += change
		if dbg: 
			print 'pts:',ps[i],ps[(i+1)%np],ps[(i+2)%np]
			print 'change:',r2d(change), 'new tot:', r2d(angle_total)
	if dbg: print 'returning ',r2d(angle_total),'as', angle_total<=0
	return angle_total<=0
	
def calc_real_bbox(points):
	smallx = 100;
	smally = 100;
	largex = -100;
	largey = -100;
	for p in points:
		if p[0] > largex:
			largex = p[0]
		if p[0] < smallx:
			smallx = p[0]
		if p[1] > largey:
			largey = p[1]
		if p[1] < smally:
			smally = p[1]
	return [[smallx, smally],[largex,largey]]	
	
def loadttf(ttf_file,characteri,font_size):
	# step 1 - load points from truetype font file
	face = Face(ttf_file)
	face.set_char_size( font_size,font_size )
	#face.load_glyph(face.get_char_index(character))
	#face.load_char('a')
	#characteri = ord(u'爻')
	#characteri = ord(u'渴')
	#characteri = ord(u'祖')
	glyph_index = face.get_char_index(characteri)
	face.load_glyph(glyph_index);
	slot = face.glyph
	#print slot.format
	f = slot.outline.flags 
	#bbox = [[face.bbox.xMin,face.bbox.yMin],[face.bbox.xMax,face.bbox.yMax]]
	if debug_freetype_py:
		print 'flags:', f
		print 0b11111111 & f
		print 'outline owner', FT_OUTLINE_OWNER & f
		print 'even odd fill', FT_OUTLINE_EVEN_ODD_FILL & f
		print 'reverse fill', FT_OUTLINE_REVERSE_FILL & f
	#print slot.outline
		for i in dir(face):
			print i
		print '--'
		print 'bbox',bbox
		for i in dir(face.glyph):
			print i
		print '---'
		print face.glyph.format
		print FT_GLYPH_FORMAT_OUTLINE
		print FT_GLYPH_FORMAT_COMPOSITE
		print FT_GLYPH_FORMAT_BITMAP

		#print face.glyph.outline.contours
	
		#print slot.outline.n_contours 
		#print slot.outline.contours 
		#print dir(slot.outline)
		#print dir(face.charmaps[0])
		#for i in face.charmaps:
		#	print i.encoding_name
			#print i.cmap_format
			#print i.index
			#print i.encoding
		#print face.charmap.encoding_name

	points = slot.outline.points
	contourlist = slot.outline.contours
	tags= slot.outline.tags
	bbox = calc_real_bbox(points)
	#points = points+[points[0]]+[points[1]]
	#tags = tags+[tags[0]]+[tags[1]]
	return points,tags,contourlist,bbox

def create_letter_if(charcode,module,height):
	if charcode >= 33  and charcode <= 126:
		out = chr(charcode);
		if out == '"' or out == '\\':
			out = '\\' +  out
		letter_output = '    if (charcode == "' + hex(charcode) + '" || charcode == ' + str(charcode) + ' || charcode=="' + out + '"){'+os.linesep
	else:
		letter_output = '    if (charcode == "' + hex(charcode) + '" || charcode == ' + str(charcode) + '){'+os.linesep
	letter_output += '        if(center==true){'+os.linesep
	letter_output += '            translate([-' + module + '_bbox' + hex(charcode) + '[1][0]/2,0,0]) ' + module + '_letter' + hex(charcode) + '(steps);'+os.linesep
	letter_output += '        }else{'+os.linesep
	letter_output += '            translate([0,0,' + str(height) + '/2]) ' + module + '_letter' + hex(charcode) + '(steps);'+os.linesep
	letter_output += '        }'+os.linesep
	#letter_output += '        for (i = [0 : $children-1])'+os.linesep
	#letter_output += '            translate([' + module + '_bbox' + hex(charcode) + '[1][0],0,0]) child(0);'+os.linesep
	letter_output += '    }' + os.linesep
	return letter_output

def create_string_if(string,bboxes,module,height,spacing,space,spacewidth):
	string_full_output = '    if(charcode == "' + string + '"){'+os.linesep
	string_output = ''
	offset = 0
	for character in string:
		if character == ' ':
			charcodex = ord(space)
			if spacewidth != -999:
				offset += spacewidth
			else:
				offset += bboxes[charcodex][1][0] + spacing
		else:
			charcode = ord(character)
			string_output += '                translate([' + str(offset) + ',0,0]) ' + module + '_letter' + hex(charcode) + '(steps);'+os.linesep
			offset += bboxes[charcode][1][0] + spacing
		
	string_full_output += '        if(center==true){'+os.linesep
	string_full_output += '            translate([-' + str(offset) + '/2,0,0]){'+os.linesep
	string_full_output += string_output
	string_full_output += '            }'+os.linesep
	string_full_output += '        }else{'+os.linesep
	string_full_output += '            translate([0,0,' + str(height) + '/2]){'+os.linesep
	string_full_output += string_output
	string_full_output += '            }'+os.linesep
	string_full_output += '        }'+os.linesep
	
	string_full_output += '    }'+os.linesep	
	return string_full_output
	
debug = False
debug_angle = False
debug_virtual_points = False
debug_curves = False
debug_composite = False
debug_chunks = False
debug_contours = False
debug_clockwise = False
debug_freetype_py = False

if __name__ == '__main__':
	parser = OptionParser(version = '%prog ' + VERSION, epilog = 'some stuff?')
	parser.add_option('-f','--font', dest='font', default='./FreeSerif.ttf', help='use FONT file to load glyphs');
	parser.add_option('--startcode', dest='startcode', default='021', help='start code');
	parser.add_option('--endcode', dest='endcode', default='07E', help='end code');
	parser.add_option('--size', dest='size', default='12', help='size');
	parser.add_option('-o','--output', dest='output', default='FreeSerif.scad', help='output file');
	parser.add_option('-m','--module', dest='module', default='FreeSerif', help='module name');
	parser.add_option('--strings', dest='stringsfile', default='', help='strings file');
	parser.add_option('--height', dest='height', default='10', help='height');
	parser.add_option('--spacing', dest='spacing', default='0', help='height');
	parser.add_option('--space', dest='space', default='x', help='height');
	parser.add_option('--spacewidth', dest='spacewidth', default='-999', help='height');

	(options, _) = parser.parse_args()

	output = ''
	
	# bezier curve code
	output+= openscad_base()+os.linesep*2
	module_output = 'module ' + options.module + '(charcode,center=true, steps=2){'+os.linesep
	bboxes = {}
	
	for i in range(int(options.startcode,16),int(options.endcode,16)+1):
		try:
			charcode = i
			points,tags,contourlist,bbox = loadttf(options.font,charcode,int(options.size,10))
			bboxes[i] = bbox;
			contours =  split_contours(hex(charcode),options.module, points,tags,contourlist)
			
			for c in contours:
				newpoints, newtags = create_virtual_points(c.points,c.tags)
				c.points = newpoints
				c.tags = newtags
			for c in contours:
				c.curves, c.curvetags = create_curves(c.points, c.tags)
				c.clockwise = is_clockwise(c)
			chunks = make_chunks(contours)
			output += make_openscad_commands(hex(charcode),options.module, contours,chunks,bbox,int(options.height,10))
			module_output += create_letter_if(charcode,options.module,int(options.height,10))

			print '// unicode:',hex(charcode)#,' render:',unichr(charcode)
			print '// number of contours:',len(contours)
			print '// number of chunks:',len(chunks)
		except IndexError:
			print '// unable to output character:',hex(charcode)

	if options.stringsfile != '':
		file = open(options.stringsfile)

		while 1:
			line = file.readline().rstrip()
			if not line:
				break
			module_output += create_string_if(line,bboxes,options.module,int(options.height,10),int(options.spacing,10),options.space,int(options.spacewidth,10))
		
	module_output += '}'
	output += os.linesep*2 + module_output

	f=open(options.output,'w')
	f.write(output)
	f.close()

	#print output

