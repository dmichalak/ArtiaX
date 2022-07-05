# vim: set expandtab shiftwidth=4 softtabstop=4:

# General
import numpy as np
from functools import partial

# Qt
from Qt.QtCore import Qt, Signal
from Qt.QtGui import QColor
from Qt.QtWidgets import (
    QWidget,
    QStackedLayout,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QToolButton,
    QGroupBox,
    QLabel,
    QLineEdit,
    QLayout,
    QSizePolicy
)

# This package
from .LabelEditSlider import LabelEditSlider
from .LabelEditRangeSlider import LabelEditRangeSlider
from .DegreeButtons import DegreeButtons


class CurvedLineOptions(QWidget):
    def __init__(self, session, parent=None):
        super().__init__(parent=parent)

        self.session = session
        self.line = None

        layout = QVBoxLayout()
        line_options_label = QLabel("Curved Line Options")
        layout.addWidget(line_options_label)

        # Fitting options
        self.fitting_checkbox = QGroupBox("Change line fitting:")
        self.fitting_checkbox.setCheckable(True)
        fitting_checkbox_layout = QVBoxLayout()

        self.degree_buttons = DegreeButtons(5)
        fitting_checkbox_layout.addWidget(self.degree_buttons)

        self.resolution_slider = LabelEditRangeSlider([100, 1000], "Resolution", step_size=10, min=10)
        fitting_checkbox_layout.addWidget(self.resolution_slider)

        self.smoothing_checkbox = QGroupBox("Smoothen line:")
        self.smoothing_checkbox.setCheckable(True)
        self.smoothing_checkbox.setChecked(False)
        smoothing_checkbox_layout = QHBoxLayout()
        self.smoothing_slider = LabelEditRangeSlider([10, 20], "Smoothing", step_size=1, min=0)
        smoothing_checkbox_layout.addWidget(self.smoothing_slider)
        self.smoothing_checkbox.setLayout(smoothing_checkbox_layout)
        fitting_checkbox_layout.addWidget(self.smoothing_checkbox)

        self.fitting_checkbox.setLayout(fitting_checkbox_layout)
        layout.addWidget(self.fitting_checkbox)

        # Populate line with particles
        self.spacing_checkbox = QGroupBox("Populate line with evenly spaced particles:")
        self.spacing_checkbox.setCheckable(True)
        self.spacing_checkbox.setChecked(False)

        spacing_checkbox_layout = QVBoxLayout()

        self.spacing_slider = LabelEditRangeSlider((1, 100), "Spacing [Å]:", min=0.1)
        spacing_checkbox_layout.addWidget(self.spacing_slider)

        self.create_particle_button = QPushButton("Create particles")
        spacing_checkbox_layout.addWidget(self.create_particle_button)

        spacing_checkbox_layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.spacing_checkbox.setLayout(spacing_checkbox_layout)

        layout.addWidget(self.spacing_checkbox)

        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._connect()

    def set_line(self, line):
        self.spacing_slider.blockSignals(True)
        self.fitting_checkbox.blockSignals(True)
        self.degree_buttons.blockSignals(True)
        self.resolution_slider.blockSignals(True)
        self.smoothing_slider.blockSignals(True)

        if self.line is not None:
            self.spacing_checkbox.setChecked(line.has_particles)
            self.spacing_slider.set_range(line.spacing_edit_range)
            self.spacing_slider.value = line.spacing

        else:
            line.spacing_edit_range = self.spacing_slider.get_range()
            line.spacing = self.spacing_slider.value

        self.fitting_checkbox.setChecked(line.fitting_options)
        self.degree_buttons.degree = line.degree
        self.degree_buttons.max_degree = len(line.particles) - 1

        if self.line != line:
            self.resolution_slider.set_range(line.resolution_edit_range)
            self.resolution_slider.value = line.resolution

            self.smoothing_slider.set_range(line.smooth_edit_range)
            self.smoothing_slider.value = line.smooth

        self.spacing_slider.blockSignals(False)
        self.fitting_checkbox.blockSignals(False)
        self.degree_buttons.blockSignals(False)
        self.resolution_slider.blockSignals(False)
        self.smoothing_slider.blockSignals(False)
        self.line = line

    def _connect(self):
        self.spacing_checkbox.clicked.connect(self._spacing_toggled)
        self.spacing_slider.valueChanged.connect(self.spacing_value_changed)
        #self.spacing_slider.editingFinished.connect(self._range_changed)
        self.create_particle_button.clicked.connect(self._create_particles)

        self.fitting_checkbox.clicked.connect(self._fitting_toggled)
        self.degree_buttons.valueChanged.connect(self._change_degree)
        self.resolution_slider.valueChanged.connect(self._resolution_changed)
        self.smoothing_checkbox.clicked.connect(self._smoothing_toggled)
        self.smoothing_slider.valueChanged.connect(self._smoothing_changed)

    def _spacing_toggled(self):
        if self.spacing_checkbox.isChecked():
            if not self.line.has_particles:
                self.line.spacing = self.spacing_slider.value
                self.line.spacing_edit_range = self.spacing_slider.get_range()
                self.line.create_spheres()
        else:
            if self.line.has_particles:
                self.line.remove_spheres()

    def spacing_value_changed(self):
        if self.line.has_particles:
            self.line.spacing = self.spacing_slider.value
            self.line.create_spheres()
            self.line.spacing_edit_range = self.spacing_slider.get_range()

    def _range_changed(self):
        if self.spacing_checkbox.isChecked():
            self.line.spacing_edit_range = self.spacing_slider.get_range()

    def _create_particles(self):
        if self.spacing_checkbox.isChecked():
            self.line.create_particle_list()

    def _fitting_toggled(self):
        if self.line is not None:
            self.line.fitting_options = self.fitting_checkbox.isChecked()

    def _change_degree(self):
        if self.line is not None and self.fitting_checkbox.isChecked():
            self.line.change_degree(self.degree_buttons.degree)

    def _resolution_changed(self):
        if self.line is not None and self.fitting_checkbox.isChecked():
            self.line.change_resolution(self.resolution_slider.value)
            self.line.resolution_edit_range = self.resolution_slider.get_range()

    def _smoothing_toggled(self):
        if self.smoothing_checkbox.isChecked():
            self.line.change_smoothing(self.smoothing_slider.value)
        else:
            self.line.change_smoothing(0)

    def _smoothing_changed(self):
        if self.line is not None and self.fitting_checkbox.isChecked() and self.smoothing_checkbox.isChecked():
            self.line.change_smoothing(self.smoothing_slider.value)
            self.line.smooth_edit_range = self.smoothing_slider.get_range()
