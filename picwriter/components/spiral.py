#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
@author: DerekK88
"""

from __future__ import absolute_import, division, print_function, unicode_literals
import numpy as np
import gdspy
import uuid
import picwriter.toolkit as tk
from picwriter.components.waveguide import Waveguide

class Spiral(gdspy.Cell):
    def __init__(self, wgt, width, height, length, spacing=None, parity=1, center=(0,0)):
        """
        First initiate super properties (gdspy.Cell)
        wgt = WaveguideTemplate
        width = MAX width of the outermost part of the spiral
        height = MAX height of the outermost part of the spiral
        length = desired length of the waveguide
        spacing = distance between parallel waveguides
        parity = If 1 spiral on right side, if -1 spiral on left side (mirror flip)
        center = Center of the entire spiral structure
        """
        gdspy.Cell.__init__(self, "Spiral--"+str(uuid.uuid4()))

        self.portlist = {}

        self.width = width
        self.height = height
        self.length = length
        self.parity = parity
        self.center = center
        self.spacing=3*wgt.clad_width if spacing==None else spacing

        self.resist = wgt.resist
        self.wgt = wgt
        self.bend_radius = wgt.bend_radius
        self.spec = {'layer': wgt.layer, 'datatype': wgt.datatype}
        self.direction_input = "SOUTH"
        self.direction_output = "NORTH"

        self.build_cell()
        self.build_ports()

    def get_dh(self, corner_dl, n):
        """
        find the height or width difference required to make the spiral length exactly = to 'length'
        """
        from scipy.optimize import fsolve
        func = lambda h0 : self.length - self.spiral_length(h0, corner_dl, n)
        hnew = fsolve(func, self.height)
        return hnew[0]

    def get_number_of_spirals(self, corner_dl):
        """
        Find the number of loops required to make the spiral length close to the desired length input
        w=outer spiral width, h=outer spiral height, s=spacing between parallel waveguides, c=corner length difference
        """
        nmax = 0
        lengthmin = 0
        for n in xrange(50): # Do not exceed 50 iterations
            n = n+1 #start with 1
            ml = self.spiral_length(self.height, corner_dl, n)
            print("spiral length n="+str(n)+" is "+str(ml))
            if n==1:
                lengthmin = ml
            if self.length <= ml:
                nmax = n
                break
        if nmax == 0:
            raise ValueError("max_length appears to be greater than length.  Either length is too large or program is broken.")
        return nmax, lengthmin

    def spiral_length(self, h, corner_dl, n):
        w = self.width
        s = self.spacing
        c = corner_dl
        length = w + 2*(w-s) + sum([2*(w-s-2*(i+1)*s) for i in range(n-1)]) + (w-2*n*s)
        length += h + (h-s) + sum([2*(h-2*(i+1)*s) for i in range(n)]) + (h-s-2*n*s)
        length = length - 6*c - 4*n*c
        return length

    def build_cell(self):
        """
        Determine the correct set of waypoints, then feed this over to a
        Waveguide() class.
        I'm sure there's better ways of generating spiral structures, though
        this seems to work, so... ¯\_(ツ)_/¯
        """
        width = self.width
        height = self.height
        length = self.length
        bend_radius = self.wgt.bend_radius
        spacing = self.spacing
        corner_dl = 2*bend_radius- 0.25*(2*np.pi*bend_radius)
        n, lengthmin = self.get_number_of_spirals(corner_dl)
        print("length="+str(length)+" lengthmin="+str(lengthmin))

        if length < lengthmin:
            raise ValueError("Spiral length is too small for desired spiral width/height.  Please specify either (1) smaller height/width or (2) larger spiral length inputs.")

        hnew = self.get_dh(corner_dl, n)
        height = hnew
        if self.parity==1:
            x0, y0 = self.center[0]-self.width/2.0, self.center[1]
        else:
            x0, y0 = self.center[0]+self.width/2.0, self.center[1]
        y0 = y0 - hnew/2.0
        h, w, s = height, width, spacing
        p = self.parity
        start_points = [(x0, y0),
                        (x0, y0 + h-s),
                        (x0+p*(w-s), y0 + h-s),
                        (x0+p*(w-s), y0+s)]
        end_points = [(x0+p*s, y0+h-2*s),
                      (x0+p*s, y0),
                      (x0+p*w, y0),
                      (x0+p*w, y0+h),
                      (x0, y0+h),
                      (x0, y0+h+self.bend_radius)]
        self.portlist_input = (x0, y0)
        self.portlist_output = (x0, y0+h+self.bend_radius)

        """ Now solve for the middle points given n loops """
        mid_points = []
        x0p, y0p, hp, wp = x0+p*s, y0+s, h-3*s, w-2*s
        cur_point = (x0p+p*wp, y0p)
        """ Spiral inwards """
        for i in xrange(int(n-1)):
            i = i+1 #start at 1
            if i%2==1: #ODD
                cur_point = (cur_point[0] - p*(wp + s - 2*i*s), cur_point[1])
                mid_points.append(cur_point)
                cur_point = (cur_point[0], cur_point[1] + (hp+s-2*i*s))
                mid_points.append(cur_point)
            elif i%2==0: #EVEN
                cur_point = (cur_point[0] + p*(wp + s - 2*i*s), cur_point[1])
                mid_points.append(cur_point)
                cur_point = (cur_point[0], cur_point[1] - (hp+s-2*i*s))
                mid_points.append(cur_point)
        """ Middle points """
        if n%2==1: #ODD -> upwards
            cur_point = (x0p + p*wp/2.0, cur_point[1])
            mid_points.append(cur_point)
            cur_point = (x0p + p*wp/2.0, cur_point[1] + (hp - (n-1)*2*s))
            mid_points.append(cur_point)
        elif n%2==0: #EVEN
            cur_point = (x0p + p*wp/2.0, cur_point[1])
            mid_points.append(cur_point)
            cur_point = (x0p + p*wp/2.0, cur_point[1] - (hp - (n-1)*2*s))
            mid_points.append(cur_point)
        """ Spiral outwards (first do other version of inwards, then reverse list) """
        cur_point = (x0p, y0p + hp)
        mid_points2 = []
        for i in xrange(int(n-1)):
            i = i+1 #start at 1
            if i%2==1: #ODD
                cur_point = (cur_point[0] + p*(wp + s - 2*i*s), cur_point[1])
                mid_points2.append(cur_point)
                cur_point = (cur_point[0], cur_point[1] - (hp+s-2*i*s))
                mid_points2.append(cur_point)
            elif i%2==0: #EVEN
                cur_point = (cur_point[0] - p*(wp + s - 2*i*s), cur_point[1])
                mid_points2.append(cur_point)
                cur_point = (cur_point[0], cur_point[1] + (hp+s-2*i*s))
                mid_points2.append(cur_point)
        mid_points2.reverse()

        waypoints = start_points+mid_points+mid_points2+end_points
        self.add(Waveguide(waypoints, self.wgt))

    def build_ports(self):
        """ Portlist format:
            example:  {'port':(x_position, y_position), 'direction': 'NORTH'}
        """
        self.portlist["input"] = {'port':self.portlist_input,
                                    'direction':self.direction_input}
        self.portlist["output"] = {'port':self.portlist_output,
                                    'direction':self.direction_output}

if __name__ == "__main__":
    from picwriter.components.waveguide import WaveguideTemplate
    top = gdspy.Cell("top")
    wgt = WaveguideTemplate(bend_radius=50, resist='-')

    sp1 = Spiral(wgt, 1000.0, 1000.0, 10000.0)
    top.add(sp1)

    gdspy.LayoutViewer()
