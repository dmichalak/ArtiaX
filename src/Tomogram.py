import sys
import numpy as np
import math as ma
from copy import copy

from chimerax.core.commands import run
from chimerax.core.models import Model
from chimerax.map import Volume, open_map, VolumeImage
from chimerax.map_data import GridData
from chimerax.map_data.fileformats import open_file
from chimerax.geometry import inner_product
from chimerax.graphics import Drawing
from chimerax.map_data.tom_em.em_grid import EMGrid

from .VolumePlus import VolumePlus

class Tomogram(VolumePlus):

    def __init__(self, session, data, rendering_options=None):
        VolumePlus.__init__(self, session, data, rendering_options=rendering_options)

        # # Stats
        # self.min = 0
        # self.max = 0
        # self.mean = 0
        # self.median = 0
        # self.std = 1
        # self.size = self.data.size
        # self._compute_stats()

        # Image Levels
        self.default_levels = None
        self._compute_default_levels()
        self.set_parameters(image_levels=self.default_levels)

        # Origin
        self.data.origin = np.array([0, 0, 0])
        if isinstance(self.data, EMGrid):
            self.pixelsize = 1
        #self._cached_position_bounds = None

        # Update display
        self.update_drawings()

    @property
    def pixelsize(self):
        return self.data.step

    @pixelsize.setter
    def pixelsize(self, value):
        if not isinstance(value, tuple):
            value = (value, value, value)

        self.data.set_step(value)
        self.update_drawings()

    @property
    def contrast_center(self):
        return self.image_levels[1][0]

    @contrast_center.setter
    def contrast_center(self, value):
        self._set_levels(center=value, width=self.contrast_width)

    @property
    def contrast_width(self):
        return self.image_levels[2][0] - self.image_levels[0][0]

    @contrast_width.setter
    def contrast_width(self, value):
        self._set_levels(center=self.contrast_center, width=value)

    @property
    def normal(self):
        return self.rendering_options.tilted_slab_axis

    @property
    def min_offset(self):
        return self._get_min_offset()

    @property
    def max_offset(self):
        return self._get_max_offset()

    @property
    def center_offset(self):
        min = self.min_offset
        max = self.max_offset
        return (max-min)/2

    @property
    def slab_count(self):
        return ma.ceil((self.max_offset - self.min_offset)/self.pixelsize[0])

    @property
    def slab_position(self):
        return self.rendering_options.tilted_slab_offset

    @slab_position.setter
    def slab_position(self, value):
        self._set_slab_offset(offset=value)

    @property
    def integer_slab_position(self):
        return ma.ceil((self.slab_position - self.min_offset)/self.pixelsize[0])

    @integer_slab_position.setter
    def integer_slab_position(self, value):
        self._set_integer_slice(slice=value)

    def _set_levels(self, center=None, width=None):

        if center is None:
            center = self.contrast_center

        if width is None:
            width = self.contrast_width

        if center + width / 2 > self.max:
            if center - width / 2 < self.min:
                position = (center - self.min) / (self.max - self.min)
            else:
                position = width / (2 * (self.max - center + width / 2))
        else:
            if center - width / 2 < self.min:
                position = (center - self.min) / (center + width / 2 - self.min)
            else:
                position = 0.5

        #TODO: command log
        l1 = center - width / 2
        l2 = center
        l3 = center + width / 2
        levels = [(l1, 0), (l2, position), (l3, 1)]

        self.set_parameters(image_levels=levels)

    def _set_integer_slice(self, slice=None):
        if slice is None:
            slice = self.integer_slab_position

        offset = slice * self.pixelsize[0] + self.min_offset
        self.slab_position = offset


    def _set_slab_offset(self, offset):
        if offset is None:
            offset = self.slab_position

        id = self.id_string

        run(self.session,
            'volume #{} region {},{},{},{},{},{} step 1 style image imageMode "tilted slab" tiltedSlabAxis {},{},{} tiltedSlabPlaneCount 1 tiltedSlabOffset {} colorMode l16'.format(
                id, 0, 0, 0, self.size[0], self.size[1], self.size[2], self.normal[0],
                self.normal[1], self.normal[2], offset), log=False)

    def _get_min_offset(self):
        corners = self.corners()#self.bounds().box_corners()

        prods = []
        for i in range(8):
            prods.append(inner_product(corners[i, :], self.normal))

        return min(prods)

    def _get_max_offset(self):
        corners = self.corners()#self.bounds().box_corners()

        prods = []
        for i in range(8):
            prods.append(inner_product(corners[i, :], self.normal))

        return max(prods)



    # def _compute_stats(self):
    #     arr = self.data.matrix(ijk_size=self.data.size)
    #     self.min = np.min(arr)
    #     self.max = np.max(arr)
    #     self.mean = np.mean(arr)
    #     self.median = np.median(arr)
    #     self.std = np.std(arr)
    #     self.range = self.max - self.min

    def _compute_default_levels(self):
        center = self.median
        width = self.mean + 12.5 * self.std

        if center + width / 2 > self.max:
            if center - width / 2 < self.min:
                position = (center - self.min) / (self.max - self.min)
            else:
                position = width / (2 * (self.max - center + width / 2))
        else:
            if center - width / 2 < self.min:
                position = (center - self.min) / (center + width / 2 - self.min)
            else:
                position = 0.5

        l1 = center - width / 2
        l2 = center
        l3 = center + width / 2
        self.default_levels = [(l1, 0), (l2, position), (l3, 1)]

    def _tomogram_set_position(self, pos):
        """Tomogram has static position at the origin."""
        return

    position = property(Drawing.position.fget, _tomogram_set_position)

    def _tomogram_set_positions(self, positions):
        """Tomogram has static position at the origin."""
        return

    positions = property(Drawing.positions.fget, _tomogram_set_positions)


def orthoplane_cmd(tomogram, axes, offset=None):

    size = tomogram.size
    spacing = tomogram.pixelsize[0]
    cmd = 'volume #{} region {},{},{},{},{},{} step 1 style image imageMode "tilted slab" tiltedSlabAxis {},{},{} tiltedSlabPlaneCount 1 tiltedSlabOffset {} tilted_slab_spacing {} colorMode l16'

    if offset is None:
        offset = tomogram.center_offset#(size[2] / 2) * spacing
        print(offset)

    if axes == 'xy':
        cmd = cmd.format(tomogram.id_string, 0, 0, 0, size[0], size[1], size[2], 0, 0, 1, offset, spacing)
    elif axes == 'xz':
        cmd = cmd.format(tomogram.id_string, 0, 0, 0, size[0], size[1], size[2], 0, 1, 0, offset, spacing)
    elif axes == 'yz':
        cmd = cmd.format(tomogram.id_string, 0, 0, 0, size[0], size[1], size[2], 1, 0, 0, offset, spacing)
    else:
        raise ValueError("orthoplane_cmd: Unknown Axes argument {}".format(axes))

    return cmd
