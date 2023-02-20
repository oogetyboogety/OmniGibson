"""This module contains vr utility functions and classes."""

import time
import os

import numpy as np
from omnigibson.utils.config_utils import dump_config, parse_config, parse_str_config


# List of all VR button idx/press combos, which will be used to form a compact binary representation
# These are taken from the openvr.h header file
VR_BUTTON_COMBOS = [
    (0, 0),
    (0, 1),
    (1, 0),
    (1, 1),
    (2, 0),
    (2, 1),
    (3, 0),
    (3, 1),
    (4, 0),
    (4, 1),
    (5, 0),
    (5, 1),
    (6, 0),
    (6, 1),
    (7, 0),
    (7, 1),
    (31, 0),
    (31, 1),
    (32, 0),
    (32, 1),
    (33, 0),
    (33, 1),
    (34, 0),
    (34, 1),
    (35, 0),
    (35, 1),
    (36, 0),
    (36, 1),
]
VR_BUTTON_COMBO_NUM = 28

# List of VR controllers and devices
VR_CONTROLLERS = ["left_controller", "right_controller"]
VR_DEVICES = ["left_controller", "right_controller", "hmd"]


# Overlay classes


class VrOverlayBase(object):
    """
    Base class representing a VR overlay. Use one of the subclasses to create a specific overlay.
    """

    def __init__(self, overlay_name, vrsys, width=1, pos=[0, 0, -1]):
        """
        :param overlay_name: the name of the overlay - must be a unique string
        :param vrsys: instance of VRRenderingContext
        :param width: width of the overlay quad in meters
        :param pos: location of overlay quad - x is left, y is up and z is away from camera in VR headset space
        """
        self.overlay_name = overlay_name
        self.vrsys = vrsys
        self.width = width
        self.pos = pos
        self.show_state = False
        # Note: overlay will only be instantiated in subclasses

    def set_overlay_show_state(self, show):
        """
        Sets show state of an overlay
        :param state: True to show, False to hide
        """
        self.show_state = show
        if self.show_state:
            self.vrsys.showOverlay(self.overlay_name)
        else:
            self.vrsys.hideOverlay(self.overlay_name)

    def get_overlay_show_state(self):
        """
        Returns show state of an overlay
        """
        return self.show_state


class VrHUDOverlay(VrOverlayBase):
    """
    Class that renders all Text objects with render_to_tex=True to a Vr overlay. Can be used for rendering user instructions, for example.
    Text should not be rendered to the non-VR screen, as it will then appear as part of the VR image!
    There should only be one of these VrHUDOverlays per scene, as it will render all text. HUD stands for heads-up-display.
    """

    def __init__(self, overlay_name, vrsys, width=1, pos=[0, 0, -1]):
        """
        :param overlay_name: the name of the overlay - must be a unique string
        :param vrsys: instance of VRRenderingContext
        :param width: width of the overlay quad in meters
        :param pos: location of overlay quad - x is left, y is up and z is away from camera in VR headset space
        """
        super().__init__(overlay_name, vrsys, width=width, pos=pos)
        self.vrsys.createOverlay(self.overlay_name, self.width, self.pos[0], self.pos[1], self.pos[2], "")

    def refresh_text(self):
        """
        Updates VR overlay texture with new text.
        """
        # Skip update if there is no text to render
        if len(self.renderer.texts) == 0:
            return
        r_tex = self.renderer.text_manager.get_render_tex()
        self.vrsys.updateOverlayTexture(self.overlay_name, r_tex)


class VrStaticImageOverlay(VrOverlayBase):
    """
    Class that renders a static image to the VR overlay a single time.
    """

    def __init__(self, overlay_name, vrsys, image_fpath, width=1, pos=[0, 0, -1]):
        """
        :param overlay_name: the name of the overlay - must be a unique string
        :param vrsys: instance of VRRenderingContext
        :param image_fpath: path to image to render to overlay
        :param width: width of the overlay quad in meters
        :param pos: location of overlay quad - x is left, y is up and z is away from camera in VR headset space
        """
        super().__init__(overlay_name, vrsys, width=width, pos=pos)
        self.image_fpath = image_fpath
        self.vrsys.createOverlay(
            self.overlay_name, self.width, self.pos[0], self.pos[1], self.pos[2], self.image_fpath
        )


class VrSettings(object):
    """
    Class containing VR settings pertaining to both the VRSys
    and VR functionality in the simulator/of VR objects
    """

    def __init__(self):
        """
        Initializes VR settings.
        """
        # Simulation is reset at start by default
        self.reset_sim = True
        # No frame save path by default
        self.frame_save_path = None

        cur_folder = os.path.abspath(os.path.dirname(__file__))
        self.vr_config_path = os.path.join(cur_folder, "..", "vr_config.yaml")
        self.load_vr_config()

    def load_vr_config(self):
        """
        Loads in VR config and sets all settings accordingly.
        """
        self.vr_config = parse_config(self.vr_config_path)

        shared_settings = self.vr_config["shared_settings"]
        self.touchpad_movement = shared_settings["touchpad_movement"]
        self.movement_controller = shared_settings["movement_controller"]
        assert self.movement_controller in ["left", "right"]
        self.relative_movement_device = shared_settings["relative_movement_device"]
        assert self.relative_movement_device in ["hmd", "left_controller", "right_controller"]
        self.movement_speed = shared_settings["movement_speed"]
        self.hud_width = shared_settings["hud_width"]
        self.hud_pos = shared_settings["hud_pos"]
        self.height_bounds = shared_settings["height_bounds"]
        self.store_only_first_button_event = shared_settings["store_only_first_button_event"]
        self.use_tracked_body = shared_settings["use_tracked_body"]
        self.torso_tracker_serial = shared_settings["torso_tracker_serial"]
        # Both body-related values need to be set in order to use the torso-tracked body
        self.using_tracked_body = self.use_tracked_body and bool(self.torso_tracker_serial)
        if self.torso_tracker_serial == "":
            self.torso_tracker_serial = None

        device_settings = self.vr_config["device_settings"]
        curr_device_candidate = self.vr_config["current_device"]
        if curr_device_candidate not in device_settings.keys():
            self.curr_device = "OTHER_VR"
        else:
            self.curr_device = curr_device_candidate
        # Disable waist tracker by default for Oculus
        if self.curr_device == "OCULUS":
            self.torso_tracker_serial = None
        self.action_button_map = device_settings[self.curr_device]["action_button_map"]
        self.gen_button_action_map()

    def dump_vr_settings(self):
        """
        Returns a string version of the vr settings
        """
        return dump_config(self.vr_config)

    def gen_button_action_map(self):
        """
        Generates a button_action_map, which is needed to convert from
        (button_idx, press_id) tuples back to actions.
        """
        self.button_action_map = {}
        for k, v in self.action_button_map.items():
            self.button_action_map[tuple(v)] = k


# ----- Utility classes ------


class VrData(object):
    """
    A class that holds VR data for a given frame. This is a clean way to pass
    around VR data that has been produced/saved, either in MUVR or in data replay.
    The class contains a dictionary with the following key/value pairs:
    Key: hmd, left_controller, right_controller
    Values: is_valid, trans, rot, right, up, forward, left/right model rotation quaternion
    Key: torso_tracker
    Values: is_valid, trans, rot
    Key: left_controller_button, right_controller_button
    Values: trig_frac, touch_x, touch_y, button_pressed_bitvector
    Key: eye_data
    Values: is_valid, origin, direction, left_pupil_diameter, right_pupil_diameter
    Key: reset_actions
    Values: left_reset bool, right_reset bool
    Key: event_data
    Values: list of lists, where each sublist is a device, (button, status) pair
    Key: vr_positions
    Values: vr_pos (world position of VR in iGibson), vr_offset (offset of VR system from origin)
    Key: vr_settings
    Values: touchpad_movement, movement_controller, movement_speed, relative_movement_device
    """

    def __init__(self, data_dict=None):
        """
        Constructs VrData object
        :param s: reference to simulator
        :param data_dict: dictionary containing all information necessary to fill out VrData class
        """
        # All internal data is stored in a dictionary
        self.vr_data_dict = data_dict if data_dict else dict()

    def query(self, q):
        """
        Queries VrData object and returns values. Please see class description for
        possible values that can be queried.
        q is the input query and must be a string corresponding to one of the keys of the self.vr_data_dict object
        """
        if q not in self.vr_data_dict.keys():
            raise RuntimeError("ERROR: Key {} does not exist in VR data dictionary!".format(q))

        return self.vr_data_dict[q]

    def refresh_action_replay_data(self, ar_data, frame_num):
        """
        Updates the vr dictionary with data from action replay.
        :param ar_data: data from action replay
        :param frame_num: frame to recover action replay data on
        """
        for device in VR_DEVICES:
            device_data = ar_data["vr/vr_device_data/{}".format(device)][frame_num].tolist()
            self.vr_data_dict[device] = [
                device_data[0],
                device_data[1:4],
                device_data[4:8],
                device_data[8:11],
                device_data[11:14],
                device_data[14:17],
                device_data[17:21],
            ]
            # TODO: Remove!!!
            if device in VR_CONTROLLERS:
                # Check if we have stored model rotations for an agent
                if len(device_data) > 18:
                    self.vr_data_dict["{}_model_rotation".format(device)] = device_data[17:21]
                self.vr_data_dict["{}_button".format(device)] = ar_data["vr/vr_button_data/{}".format(device)][
                    frame_num
                ].tolist()

        torso_tracker_data = ar_data["vr/vr_device_data/torso_tracker"][frame_num].tolist()
        self.vr_data_dict["torso_tracker"] = [torso_tracker_data[0], torso_tracker_data[1:4], torso_tracker_data[4:]]

        eye_data = ar_data["vr/vr_eye_tracking_data"][frame_num].tolist()
        self.vr_data_dict["eye_data"] = [eye_data[0], eye_data[1:4], eye_data[4:7], eye_data[7], eye_data[8]]

        events = []
        for controller in VR_CONTROLLERS:
            for button_press_data in convert_binary_to_button_data(
                ar_data["vr/vr_event_data/{}".format(controller)][frame_num]
            ):
                events.append((controller, button_press_data))
        self.vr_data_dict["event_data"] = events
        self.vr_data_dict["reset_actions"] = [
            bool(x) for x in list(ar_data["vr/vr_event_data/reset_actions"][frame_num])
        ]

        pos_data = ar_data["vr/vr_device_data/vr_position_data"][frame_num].tolist()
        self.vr_data_dict["vr_positions"] = [pos_data[:3], pos_data[3:]]
        # Action replay does not use VR settings, so we leave this as an empty list
        self.vr_data_dict["vr_settings"] = []

    def to_dict(self):
        """
        Returns dictionary form of the VrData class - perfect for sending over networks
        """
        return self.vr_data_dict

    def print_data(self):
        """Utility function to print VrData object in a pretty fashion."""
        for k, v in self.vr_data_dict.items():
            print("{}: {}".format(k, v))


# ----- Utility functions ------


def calc_z_dropoff(theta, t_min, t_max):
    """
    Calculates and returns the dropoff coefficient for a z rotation (used in both VR body and Fetch VR).
    The dropoff is 1 if theta > t_max, falls of quadratically between t_max and t_min and is then clamped to 0 thereafter.
    """
    z_mult = 1.0
    if t_min < theta and theta < t_max:
        # Apply the following quadratic to get faster falloff closer to the poles:
        # y = -1/(min_z - max_z)^2 * x*2 + 2 * max_z / (min_z - max_z) ^2 * x + (min_z^2 - 2 * min_z * max_z) / (min_z - max_z) ^2
        d = (t_min - t_max) ** 2
        z_mult = -1 / d * theta ** 2 + 2 * t_max / d * theta + (t_min ** 2 - 2 * t_min * t_max) / d
    elif theta < t_min:
        z_mult = 0.0

    return z_mult


def calc_z_rot_from_right(right):
    """
    Calculates z rotation of an object based on its right vector, relative to the positive x axis,
    which represents a z rotation euler angle of 0. This is used for objects that need to rotate
    with the HMD (eg. VrBody), but which need to be robust to changes in orientation in the HMD.
    """
    # Project right vector onto xy plane
    r = np.array([right[0], right[1], 0])
    z_zero_vec = np.array([1, 0, 0])
    # Get angle in radians
    z = np.arccos(np.dot(r, z_zero_vec))
    # Flip sign if on the right side of the xy plane
    if r[1] < 0:
        z *= -1
    # Add pi/2 to get forward direction, but need to deal with jumping
    # over quadrant boundaries
    if np.pi / 2 < z <= np.pi:
        return -np.pi * 3 / 2 + z
    return np.pi / 2 + z


def convert_button_data_to_binary(bdata):
    """
    Converts a list of button data tuples of the form (button_idx, press_id) to a binary list,
    where a 1 at index i indicates that the data at index i in VR_BUTTON_COMBOS was triggered
    :param bdata: list of button data tuples
    """
    bin_events = [0] * VR_BUTTON_COMBO_NUM
    for d in bdata:
        event_idx = VR_BUTTON_COMBOS.index(d)
        bin_events[event_idx] = 1

    return bin_events


def convert_binary_to_button_data(bin_events):
    """
    Converts a list of binary vr events to (button_idx, press_id) tuples.
    :param bin_events: binarized list, where a 1 at index i indicates that the data at index i in VR_BUTTON_COMBOS was triggered
    """
    button_press_data = []
    for i in range(VR_BUTTON_COMBO_NUM):
        if bin_events[i] == 1:
            button_press_data.append(VR_BUTTON_COMBOS[i])

    return button_press_data


def calc_offset(s, curr_offset, touch_x, touch_y, movement_speed, relative_device):
    right, _, forward = s.vr_sys.getDeviceCoordinateSystem(relative_device)
    vr_offset_vec = np.array([right[i] * touch_x + forward[i] * touch_y for i in range(3)])
    vr_offset_vec[2] = 0
    length = np.linalg.norm(vr_offset_vec)
    if length != 0:
        vr_offset_vec /= length
    return [curr_offset[i] + vr_offset_vec[i] * movement_speed for i in range(3)]
