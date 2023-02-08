# General imports
import time

import numpy as np
import math
from scipy import interpolate

# ChimeraX imports
from chimerax.geometry import z_align, rotation, translation
from chimerax.bild.bild import _BildFile
from chimerax.atomic import AtomicShapeDrawing

# ArtiaX imports
from .GeoModel import GEOMODEL_CHANGED
from .PopulatedModel import PopulatedModel
from ..particle.SurfaceCollectionModel import SurfaceCollectionModel, MODELS_MOVED


class CurvedLine(PopulatedModel):
    """
    Fits a curved line through the given particles. Can be used to create particles along the line.
    Calculates the points and tangents if not provided.
    """

    def __init__(self, name, session, particle_pos, degree, smooth, resolution, surface_collection_models=None, particles=None, points=None,
                 der_points=None):
        super().__init__(name, session)

        self.particles = particles
        """n-long list containing all particles used to define the sphere."""
        self.particle_pos = particle_pos
        """(n x 3) list containing all xyz positions of the particles."""

        if points is None or der_points is None:
            self.points, self.der_points = get_points(particle_pos, smooth, degree, resolution)
        else:
            self.points = points
            self.der_points = der_points
        """(3 x n) list with all the points/derivatives used to define the line. points[0] contains all the x values, 
        points[1] all y values etc"""

        self.degree = degree
        """Polynomial degree used to fit line."""
        self.smooth = smooth
        """Decides how much to smooth the polynomial. smooth = 0 forces the line to go through all particles."""
        self.smooth_edit_range = [math.floor(len(particle_pos) - math.sqrt(2 * len(particle_pos))),
                                  math.ceil(len(particle_pos) + math.sqrt(2 * len(particle_pos)))]
        self.resolution = resolution
        """How many points to define the line by."""
        self.resolution_edit_range = (50, 500)

        self.fitting_options = True
        self.display_options = True
        self.radius = 1
        """Line (which is drawn as a cylinder) radius"""
        self.radius_edit_range = (0, 2)

        self.spacing_edit_range = (1, 100)
        self.spacing = (self.spacing_edit_range[1] + self.spacing_edit_range[0]) / 2
        """Spacing between created particles."""
        self.rotate = False
        """Whether to rotate particles around the line."""
        self.rotation = 0
        """Degrees to rotate per Angstrom"""
        self.rotation_edit_range = (0, 1)
        self.start_rotation = 0
        """Rotation of first particle."""

        self.update_on_move = False
        self.camera_options = False
        self.backwards = False
        self.no_frames_edit_range = (1, self.resolution)
        self.no_frames = 60
        self.distance_behind_camera_edit_range = (0, 1000)
        self.distance_behind_camera = (self.distance_behind_camera_edit_range[1] + self.distance_behind_camera_edit_range[0]) / 2
        self.top_rotation = 0
        self.facing_rotation = 0
        self.camera_axes_options = True
        self.no_camera_axes_edit_range = (1, resolution)
        self.no_camera_axes = 30
        self.has_camera_markers = False
        self.camera_axes_size = 15
        self.camera_axes_size_edit_range = (10, 20)
        if surface_collection_models is not None:
            for scm in surface_collection_models:
                scm.triggers.add_handler(MODELS_MOVED, self._particle_moved)
        self.move_along_line_collection_model = SurfaceCollectionModel('Camera', session)
        self.add([self.move_along_line_collection_model])
        self.move_along_line_collection_model.add_collection('camera_markers')
        v, n, t, vc = self.get_camera_marker_surface()
        self.move_along_line_collection_model.set_surface('camera_markers', v, n, t, vertex_colors=vc)
        self.camera_marker_indices = []

        self.update()
        session.logger.info("Created a Curved line through {} particles.".format(len(particle_pos)))

    def _particle_moved(self, name, data):
        if self.update_on_move and self.visible:
            self.recalc_and_update()
        # TODO: make the camera markers update when moving particle

    def update(self):
        """Redraws the line."""
        vertices, normals, triangles, vertex_colors = self.define_curved_line()
        self.set_geometry(vertices, normals, triangles)
        self.vertex_colors = np.full(np.shape(vertex_colors), self.color)

    def recalc_and_update(self):
        """Recalculates the points and derivatives that define the line before redrawing the line."""
        if self.particles is not None:
            for i, particle in enumerate(self.particles):
                self.particle_pos[i] = [particle.coord[0], particle.coord[1], particle.coord[2]]
        self.points, self.der_points = get_points(self.particle_pos, self.smooth, self.degree, self.resolution)
        self.update()

    def define_curved_line(self):
        b = _BildFile(self.session, 'dummy')

        for i in range(0, len(self.points[0]) - 1):
            b.cylinder_command(".cylinder {} {} {} {} {} {} {}".format(self.points[0][i], self.points[1][i],
                                                                       self.points[2][i], self.points[0][i + 1],
                                                                       self.points[1][i + 1],
                                                                       self.points[2][i + 1], self.radius).split())

        d = AtomicShapeDrawing('shapes')
        d.add_shapes(b.shapes)

        return d.vertices, d.normals, d.triangles, d.vertex_colors

    def change_radius(self, r):
        if self.radius != r:
            self.radius = r
            self.update()

    def create_spheres(self):
        """Creates sphere markers with axes to show how particles would be created."""
        self.has_particles = True
        self.triggers.activate_trigger(GEOMODEL_CHANGED, self)
        # Remove old spheres if any exist
        if len(self.indices):
            self.collection_model.delete_places(self.indices)
        self.spheres_places = []

        # Set first manually to avoid special cases in loop:
        first_pos = np.array([self.points[0][0], self.points[1][0], self.points[2][0]])
        der = [self.der_points[0][0], self.der_points[1][0], self.der_points[2][0]]
        tangent = der / np.linalg.norm(der)
        rotation_to_z = z_align(first_pos, first_pos + tangent)
        rotation_along_line = rotation_to_z.zero_translation().inverse()
        rot = rotation_along_line
        if self.rotate:
            rotation_around_z = rotation(rotation_along_line.z_axis(), self.start_rotation)
            rot = rotation_around_z * rotation_along_line

        place = translation(first_pos) * rot
        self.spheres_places = np.append(self.spheres_places, place)

        n = rot.transform_vector((1, 0, 0))
        n = n / np.linalg.norm(n)
        normals = np.array([n])

        total_dist = 0
        distance_since_last = 0
        for i in range(1, len(self.points[0])):
            curr_pos = np.array([self.points[0][i], self.points[1][i], self.points[2][i]])
            last_pos = np.array([self.points[0][i - 1], self.points[1][i - 1], self.points[2][i - 1]])
            step_dist = np.linalg.norm(curr_pos - last_pos)
            der = [self.der_points[0][i], self.der_points[1][i], self.der_points[2][i]]
            tangent = der / np.linalg.norm(der)
            total_dist += step_dist
            distance_since_last += step_dist

            # calculate normal using projection normal method found in "Normal orientation methods for 3D offset
            # curves, sweep surfaces and skinning" by Pekka  Siltanen  and Charles  Woodward
            n = normals[-1] - (np.dot(normals[-1], tangent)) * tangent
            n = n / np.linalg.norm(n)
            normals = np.append(normals, [n], axis=0)

            # create marker
            if distance_since_last >= self.spacing:
                distance_since_last = 0

                rotation_along_line = z_align(curr_pos, curr_pos + tangent).zero_translation().inverse()
                x_axes = rotation_along_line.transform_vector((1, 0, 0))
                cross = np.cross(n, x_axes)
                theta = math.acos(np.dot(n, x_axes)) * 180 / math.pi
                if np.linalg.norm(cross + tangent) > 1:
                    theta = -theta
                helix_rotate = 0
                if self.rotate:
                    helix_rotate = total_dist * self.rotation
                rotation_around_z = rotation(rotation_along_line.z_axis(), theta + helix_rotate)

                rot = rotation_around_z * rotation_along_line

                place = translation(curr_pos) * rot
                self.spheres_places = np.append(self.spheres_places, place)

        self.indices = [str(i) for i in range(0, len(self.spheres_places))]
        self.collection_model.add_places(self.indices, self.spheres_places)
        self.collection_model.color = self.color

    def change_rotation(self, rot):
        if self.rotation == rot:
            return
        else:
            self.rotation = rot
            self.create_spheres()

    def change_start_rotation(self, rot):
        if self.start_rotation == rot:
            return
        else:
            self.start_rotation = rot
            self.create_spheres()

    def change_degree(self, degree):
        if self.degree == degree:
            return
        else:
            self.degree = degree
            self.recalc_and_update()

    def change_resolution(self, res):
        if self.resolution == res:
            return
        else:
            self.resolution = res
            self.recalc_and_update()

    def change_smoothing(self, s):
        if self.smooth == s:
            return
        else:
            self.smooth = s
            self.recalc_and_update()

    def get_camera_marker_surface(self):
        b = _BildFile(self.session, 'dummy')

        b.color_command('.color 1 1 0'.split())
        b.arrow_command(".arrow 0 0 0 0 {} 0 {} {}".format(self.camera_axes_size, self.camera_axes_size / 15,
                                                           self.camera_axes_size / 15 * 4).split())
        b.color_command('.color 0 0 1'.split())
        b.arrow_command(".arrow 0 0 0 0 0 {} {} {}".format(self.camera_axes_size, self.camera_axes_size / 15,
                                                           self.camera_axes_size / 15 * 4).split())

        d = AtomicShapeDrawing('shapes')
        d.add_shapes(b.shapes)

        return d.vertices, d.normals, d.triangles, d.vertex_colors

    def move_camera_along_line(self, draw=False, no_frames=None, backwards=False, distance_behind=10000, x_rotation=0, z_rotation=0):
        points = np.transpose(self.points)
        ders = np.transpose(self.der_points)
        if no_frames is not None:
            points = points[::int(len(points)/(no_frames-1))]
            ders = ders[::int(len(ders)/(no_frames-1))]
        if backwards:
            points = np.flip(points, 0)
            ders = np.flip(-ders, 0)

        tangent = - ders[0] / np.linalg.norm(ders[0])
        rotation_to_z = z_align(points[0], points[0] + tangent)

        rotation_along_line = rotation_to_z.zero_translation().inverse()
        rotation_around_z = rotation(rotation_along_line.z_axis(), x_rotation)
        rot = rotation_around_z * rotation_along_line
        rotation_around_y = rotation(rot.transform_vector((0, 1, 0)), z_rotation)
        rot = rotation_around_y * rot

        if draw:
            if len(self.camera_marker_indices):
                self.move_along_line_collection_model.delete_places(self.camera_marker_indices)
            rotation_around_x = rotation(rot.transform_vector((0, 1, 0)), 180)
            place = translation(points[0]) * rotation_around_x * rot
            camera_markers_places = [place]
        else:
            point = points[0] + rot.z_axis() * distance_behind
            place = translation(point) * rot
            self.session.view.camera.position = place
            self.session.update_loop.draw_new_frame()

        n = rot.transform_vector((0, 1, 0))
        n = n / np.linalg.norm(n)
        normals = np.array([n])
        for point, der in zip(points[1:], ders[1:]):
            n = normals[-1] - (np.dot(normals[-1], tangent)) * tangent
            n = n / np.linalg.norm(n)
            normals = np.append(normals, [n], axis=0)
            tangent = - der / np.linalg.norm(der)
            rotation_along_line = z_align(point, point + tangent).zero_translation().inverse()
            y_axes = rotation_along_line.transform_vector((0, 1, 0))
            cross = np.cross(n, y_axes)
            theta = math.acos(np.dot(n, y_axes)) * 180 / math.pi
            if np.linalg.norm(cross + tangent) > 1:
                theta = -theta
            rotation_around_z = rotation(rotation_along_line.z_axis(), theta)
            rot = rotation_around_z * rotation_along_line
            rotation_around_y = rotation(rot.transform_vector((0, 1, 0)), z_rotation)
            rot = rotation_around_y * rot
            if draw:
                rotation_around_x = rotation(rot.transform_vector((0, 1, 0)), 180)
                place = translation(point) * rotation_around_x * rot
                camera_markers_places.append(place)
            else:
                point = point + rot.z_axis() * distance_behind
                place = translation(point) * rot
                self.session.view.camera.position = place
                self.session.update_loop.draw_new_frame()
        if draw:
            self.has_camera_markers = True
            self.camera_marker_indices = [str(i) for i in range(0, len(camera_markers_places))]
            self.move_along_line_collection_model.add_places(self.camera_marker_indices, camera_markers_places)
            self.move_along_line_collection_model.color = self.color

    def create_camera_markers(self):
        self.move_camera_along_line(draw=True, no_frames=self.no_camera_axes, backwards=self.backwards,
                                    distance_behind=self.distance_behind_camera, x_rotation=self.top_rotation,
                                    z_rotation=self.facing_rotation)

    def remove_camera_markers(self):
        self.has_camera_markers = False
        if len(self.camera_marker_indices):
            self.move_along_line_collection_model.delete_places(self.camera_marker_indices)
            self.camera_marker_indices = []

    def change_camera_axes_size(self, s):
        if self.camera_axes_size != s:
            self.camera_axes_size = s
            v, n, t, vc = self.get_camera_marker_surface()
            self.move_along_line_collection_model.set_surface('camera_markers', v, n, t, vertex_colors=vc)

    def write_file(self, file_name):
        with open(file_name, 'wb') as file:
            np.savez(file, model_type="CurvedLine", particle_pos=self.particle_pos, degree=self.degree,
                     smooth=self.smooth, resolution=self.resolution, points=self.points, der_points=self.der_points)


def get_points(pos, smooth, degree, resolution):
    """Uses scipy to interpolate a line through the points

    Parameters
    ----------
    pos: (n x 3) list of floats with n coordinates
    smooth: how much to smoothen the line.
    degree: which degree polynomial to fit the line with.
    resolution: how many points to return.

    Returns
    -------
    points: (m x 3) list of floats with m coordinates. n=resolution
    der_points: same as points but the derivatives.
    """
    # Find particles
    x = pos[:,0]
    y = pos[:,1]
    z = pos[:,2]

    # s=0 means it will go through all points, s!=0 means smoother, good value between m+-sqrt(2m) (m=no. points)
    # degree can be 1,3, or 5
    tck, u = interpolate.splprep([x, y, z], s=smooth, k=degree)
    un = np.arange(0, 1 + 1 / resolution, 1 / resolution)
    points = interpolate.splev(un, tck)
    der_points = interpolate.splev(un, tck, der=1)

    return points, der_points
