# General imports
import math

import numpy as np
from scipy.spatial import Delaunay
from collections import defaultdict
from statistics import median

# ChimeraX imports
from chimerax.bild.bild import _BildFile
from chimerax.atomic import AtomicShapeDrawing

# ArtiaX imports
from .GeoModel import GeoModel


class Boundary(GeoModel):
    """Triangulated Plane"""

    def __init__(self, name, session, triangles, particles, particle_pos, alpha):
        super().__init__(name, session)

        self.tri = triangles
        self.particles = particles
        self.particle_pos = particle_pos
        self.alpha = alpha

        self.fitting_options = True

        self.update()

    def define_surface(self):
        b = _BildFile(self.session, 'dummy')

        for triangle in self.tri:
            b.polygon_command(
                ".polygon {} {} {} {} {} {} {} {} {}".format(*triangle[0], *triangle[1], *triangle[2]).split())

        d = AtomicShapeDrawing('shapes')
        d.add_shapes(b.shapes)

        return d.vertices, d.normals, d.triangles

    def update(self):
        vertices, normals, triangles = self.define_surface()
        self.set_geometry(vertices, normals, triangles)
        self.vertex_colors = np.full((len(vertices), 4), self.color)

    def recalc_and_update(self):
        for i, particle in enumerate(self.particles):
            self.particle_pos[i] = [particle.coord[0], particle.coord[1], particle.coord[2]]
        self.tri = get_triangles(self.particle_pos, self.alpha)
        self.update()

    def change_alpha(self, alpha):
        if alpha != self.alpha and 0 <= alpha <= 1:
            self.alpha = alpha
            self.recalc_and_update()


def get_triangles(particle_pos, alpha=0.7):
    tetra = Delaunay(particle_pos, furthest_site=False)
    """ Taken mostly from stack overflow: https://stackoverflow.com/a/58113037
    THANK YOU @Geun, this is pretty clever. """
    # Find radius of the circumsphere.
    # By definition, radius of the sphere fitting inside the tetrahedral needs
    # to be smaller than alpha value
    # http://mathworld.wolfram.com/Circumsphere.html
    tetrapos = np.take(particle_pos, tetra.simplices, axis=0)
    normsq = np.sum(tetrapos ** 2, axis=2)[:, :, None]
    ones = np.ones((tetrapos.shape[0], tetrapos.shape[1], 1))
    a = np.linalg.det(np.concatenate((tetrapos, ones), axis=2))
    Dx = np.linalg.det(np.concatenate((normsq, tetrapos[:, :, [1, 2]], ones), axis=2))
    Dy = -np.linalg.det(np.concatenate((normsq, tetrapos[:, :, [0, 2]], ones), axis=2))
    Dz = np.linalg.det(np.concatenate((normsq, tetrapos[:, :, [0, 1]], ones), axis=2))
    c = np.linalg.det(np.concatenate((normsq, tetrapos), axis=2))
    r = np.sqrt(Dx ** 2 + Dy ** 2 + Dz ** 2 - 4 * a * c) / (2 * np.abs(a))

    # Translate alpha value from 0-1 to shortest-longest
    sorted_r = np.sort(r)
    alpha = math.floor(alpha*len(r))
    if alpha == len(r):
        alpha -= 1
    alpha = sorted_r[alpha]

    # Find tetrahedrals
    tetras = tetra.simplices[r <= alpha, :]
    # triangles
    TriComb = np.array([(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)])
    triangles = tetras[:, TriComb].reshape(-1, 3)
    triangles = np.sort(triangles, axis=1)
    # Remove triangles that occurs twice, because they are within shapes
    TrianglesDict = defaultdict(int)
    for tri in triangles:
        TrianglesDict[tuple(tri)] += 1
    triangles = np.array([particle_pos[np.asarray(tri)] for tri in TrianglesDict if TrianglesDict[tri] == 1])

    return triangles
