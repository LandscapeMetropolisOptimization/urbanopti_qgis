# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UrbanOptiPlugin
                                 A QGIS plugin
 Description
                             -------------------
        copyright            : (C) 2021 by Pietro Belotti
        email                : petr7b6@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load UrbanOptiPlugin class from file UrbanOptiPlugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .urbanopti_plugin import UrbanOptiPlugin
    return UrbanOptiPlugin(iface)
