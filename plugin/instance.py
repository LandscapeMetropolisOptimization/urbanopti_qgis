# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UrbanOptimizer
                                 A QGIS plugin
 Design Urban Mobility networks via Optimization
                              -------------------
        begin                : 2020-11-23
        git sha              : $Format:%H$
        copyright            : (C) 2020 by Pietro Belotti
        email                : pietro.belotti@polimi.it
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

"""

import os

from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *

import numpy as np
import math

from urbanopti.greentransport.optmodel import add_point_layer, add_segment_layer

# The layers used by the current settings use different CRS,
# so we must convert them to a given one. We choose 25832.

sys_25832 = QgsCoordinateReferenceSystem('EPSG:25832')


def aggregate_demand_points(point_dem, nDemAggr):
    """Given a nx3 array whose rows are x,y,d, create a set of nDemAggr
    aggregator each representing the closest points and with aggregate
    demand being the sum over all aggregated points.  Aggregator at
    iteration 0 is the farthest from point indexed 0, aggregator at
    iteration i is the farthest from the i-th point.
    """

    nDemands = point_dem.shape[0]

    point_aggr = []
    selected = -np.ones(nDemands)

    # Select initial point as furthest from any point (take 0th)
    ind0 = np.argmax(np.sqrt((point_dem[:, 0] - point_dem[0, 0])**2 +
                             (point_dem[:, 1] - point_dem[0, 1])**2))

    for iAggr in range(nDemAggr):

        # ind0 is the new anti-attractor. Gather all nearby points
        distances = \
            np.sqrt(((point_dem[:, 0] - point_dem[ind0, 0])**2 + \
                     (point_dem[:, 1] - point_dem[ind0, 1])**2))

        tmp = distances[:]
        tmp = tmp[selected == -1]
        tmp.sort()

        limit_dist = tmp[int(nDemands / nDemAggr)] if iAggr < nDemAggr - 1 else tmp[-1]

        selected[(distances <= limit_dist) & (selected == -1)] = iAggr
        point_aggr.append((point_dem[ind0, 0], point_dem[ind0, 1], np.sum(point_dem[:, 2][selected == iAggr])))

        distances[selected != -1] = 0

        if iAggr < nDemAggr - 1:
            ind0 = np.argmax(distances)

    return point_aggr


class UrbanData():
    """Class for urban design. Contains linestrings for biking trails,
    railways, canals, points for stations, harbors, and information on
    (point-to-point or single-point) traffic demand.
    """

    def __init__(self, iface, **options):

        self.iface = iface

        if 'debug' in options and options['debug'] == 'yes':
            print("Options:")
            for i in options:
                print(f"{i}: {options[i]}")

        iface.messageBar().pushMessage(
            "Info", "Constructing connection network",
            level=Qgis.Info, duration=1)

        if not set(['trafficLayer',
                    'trafficOD',
                    'trailPointLayer',
                    'trailLineLayer',
                    'trailAccess',
                    'railwayPointLayer',
                    'railwayLineLayer',
                    'railwayAccess',
                    'canalPointLayer',
                    'canalLineLayer',
                    'canalAccess']) <= set(options.keys()):
            raise RuntimeError("Must specify all layers for canal, bike trails, railway, and traffic demand")

        layer_canal_edge = options['canalLineLayer']
        layer_canal_node = options['canalPointLayer']

        layer_trail_edge = options['trailLineLayer']
        layer_trail_node = options['trailPointLayer']

        layer_railway_edge = options['railwayLineLayer']
        layer_railway_node = options['railwayPointLayer']

        isCanalPointAccessed = options['canalAccess']
        isTrailPointAccessed = options['trailAccess']
        isRailwayPointAccessed = options['trailAccess']

        if options['trafficOD']:
            layers_od = options['trafficLayer']
            layers_demand = None
        else:
            layers_od = None
            layers_demand = options['trafficLayer']


        ######################################################################################
        # Vertices
        #

        self.iface.messageBar().pushMessage(
            "Info", "Processing nodes",
            level=Qgis.Info, duration=1)

        nodes = {}

        feature_price_name = {"canal": "costo",
                              "trail": "Prezzo",
                              "railway": "COSTO_INT"}

        for key, name in {"canal":   layer_canal_node,
                          "trail":   layer_trail_node,
                          "railway": layer_railway_node}.items():

            layer = QgsProject.instance().mapLayersByName(name)

            if len(layer) > 1:
                raise RuntimeError('Multiple layers with matching name')
            elif len(layer) < 1:
                raise RuntimeError('Node layer not found')

            nodes[key] = self.collect_nodes (layer[0], feature_price_name[key])

        self.iface.messageBar().pushMessage(
            "Info", "Processing traffic demands",
            level=Qgis.Info, duration=1)

        ####################################################################################################
        # s-t demands
        #

        if options['trafficOD']:

            demand_layer_name = options['trafficLayer']

        else:
            # Group s-t demands

            demand = {}

            self.iface.messageBar().pushMessage(
                "Info", "Aggregating demands",
                level=Qgis.Info, duration=1)

            layer = QgsProject.instance().mapLayersByName(options['trafficLayer'])
            demand[name] = self.collect_nodes(layer[0], 'Saliti_Sal')

            point_dem = np.array([[tup[0], tup[1], tup[2]] for tup in demand[name] for name in layers_demand])

            nDemAggr = 8

            if 'number_aggregate' in options and options['number_aggregate'] > 1:
                nDemAggr = options['number_aggregate']

            point_aggr = aggregate_demand_points (point_dem, nDemAggr)

            # Visualize aggregate demand points and value

            if 'visualize_aggregate' in options and options['visualize_aggregate'] == 'yes':
                add_point_layer(None, point_aggr, ['Aggr_demand'], 'Aggregate Demand')

            add_segment_layer(None, [list(p1[:2]) + list(p2[:2]) + [max(p1[2], p2[2])]
                               for i1,p1 in enumerate(point_aggr) for i2,p2 in enumerate(point_aggr) if i1<i2],
                              attributes=['volume'], groupname='Demand')

            demand_layer_name = 'Demand segments'

        # Regardless of demand aggregation, collect demand data in a
        # 6-tuple with the QGIS feature as the 6th element.

        layer = QgsProject.instance().mapLayersByName(demand_layer_name)

        demand = self.collect_edges (layer[0], 'volume')

        ############################################################################
        # Edges
        #

        edges = {}

        feature_price_name = {"canal": None,
                              "trail": "Costo tot",
                              "railway": None}

        for key, name in {"canal": layer_canal_edge,
                          "trail": layer_trail_edge,
                          "railway": layer_railway_edge}.items():

            layer = QgsProject.instance().mapLayersByName(name)

            if len(layer) > 1:
                raise RuntimeError('Multiple layers with matching name')
            elif len(layer) < 1:
                raise RuntimeError('Edge layer not found')

            edges[key] = self.collect_edges (layer[0], feature_price_name[key])

        # Summarize all input data in one dictionary.

        self.data = {"nodes": nodes, "edges": edges, "demand": demand}


    def instance(self):
        return self.data


    def collect_edges(self, layer, feature_name=None):

        edges = []

        lname = layer.name()

        xform = QgsCoordinateTransform(layer.dataProvider().crs(), sys_25832, QgsProject.instance())

        field_list = [field.name() for field in layer.fields()]

        for feature in layer.getFeatures():

            if 'NAVIGAB_' in field_list and \
               feature['NAVIGAB_'] in [None, 'NO']:
                continue

            geom = feature.geometry().asPolyline()
            if len(geom) < 1:
                continue

            start_point_crs = QgsPointXY(geom[0])
            end_point_crs   = QgsPointXY(geom[-1])

            start_point = xform.transform(start_point_crs)
            end_point   = xform.transform(  end_point_crs)

            x1, y1 = start_point.x(), start_point.y()
            x2, y2 =   end_point.x(),   end_point.y()

            cost = 0

            if feature_name and \
               feature_name in field_list and \
               type(feature[feature_name]) in [int, float]:
                cost = feature[feature_name]

            edges.append((x1, y1, x2, y2, cost, feature))

        return edges


    def collect_nodes (self, layer, feature_name=None):

        nodes = []

        lname = layer.name()

        xform = QgsCoordinateTransform(layer.dataProvider().crs(), sys_25832, QgsProject.instance())

        field_list = [field.name() for field in layer.fields()]

        for feature in layer.getFeatures():

            point_crs = feature.geometry().asPoint()

            point = xform.transform(point_crs)

            x = point.x()
            y = point.y()

            cost = 0

            if feature_name and \
               feature_name in field_list and \
               type(feature[feature_name]) in [int, float]:
                cost = feature[feature_name]

            nodes.append((x, y, cost, feature))

        return nodes
