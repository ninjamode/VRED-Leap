# Sample scripts in this file are not supported under any Autodesk standard support program or service.
# The sample scripts are provided without warranty of any kind.
# Autodesk disclaims all implied warranties including, without limitation, any implied warranties of merchantability or of fitness for a particular purpose.
# The entire risk arising out of the use or performance of the sample scripts and documentation remains with you.

from PySide2 import QtWidgets
from PySide2 import QtCore
from vrAEBase import vrAEBase
import vrController, vrCamera, vrFileIO, vrScenegraph, vrNodeUtils, vrOptimize, vrConstraints
import uiTools
import os, sys, math
from os.path import expanduser


# Look for Leap Library in C:\Autodesk\ or ~\Autodesk\
home = expanduser("~")
arch = '/lib-leap/x64' if sys.maxsize > 2 ** 32 else '/lib-leap/x86'
hlib_dir = home + '/Autodesk/lib-leap/'
harch_dir = home + '/Autodesk' + arch
glib_dir = 'C:/Autodesk/lib-leap/'
garch_dir = 'C:/Autodesk' + arch

sys.path.insert(0, os.path.abspath(glib_dir))
sys.path.insert(0, os.path.abspath(garch_dir))
sys.path.insert(0, os.path.abspath(hlib_dir))
sys.path.insert(0, os.path.abspath(harch_dir))

import Leap
from Leap import Finger, Bone

# Hide hands that are currently not visible, otherwise hands
# stay at the last known location
hide_invisible_hands = True

# Adjust settings for head mounted mode
# Desktop mode (not on a hmd) is not tested!
hmd_mounted = True


# Will add nodes to this camera
# Leave empty to use the currently selected camera
vr_cam_name = ""


def vredMainWindow(id):
    from shiboken2 import wrapInstance
    return wrapInstance(id, QtWidgets.QMainWindow)

def plugin_path():
    version = vrController.getVredVersion()
    path = os.path.join(os.path.expanduser('~'), "Documents", "Autodesk", "VRED-" + version, "ScriptPlugins", "LeapVRED")
    return path

def distance(a, b):
    ''' Euclidean distance between 2 points, given as a list of floats '''
    return math.sqrt((a[0]-b[0]) ** 2 + (a[1]-b[1]) ** 2 + (a[2]-b[2]) ** 2)

# create missing keys in dict on the fly

class Vividict(dict):
    def __missing__(self, key):
        value = self[key] = type(self)()
        return value


# Use the ui file to populate the automatically generated Scripts->Leap menu button with some text
leap_form, leap_base = uiTools.loadUiType(plugin_path() + '\\leapGUI.ui')
class LeapControl(leap_form, leap_base):
    def __init__(self, mw, parent = None):
        super(LeapControl, self).__init__(parent)
        parent.layout().addWidget(self)
        self.parent = parent
        self.setupUi(self)

        self.add_menu(mw)
        self.paused = True
        self.initialized = False

        parent.layout().addWidget(self)
        self.parent = parent
        self.setupUi(self)


    def __del__(self):
        self.mw.menuBar().removeAction(self.menu.menuAction())


    def add_menu(self, mw):
        self.mw = mw     
        
        self.connect_leap_action = QtWidgets.QAction(mw.tr("Start Leap Motion"), mw)
        self.connect_leap_action.triggered.connect(self.connect)
        
        self.stop_leap_action = QtWidgets.QAction(mw.tr("Stop Leap Motion"), mw)
        self.stop_leap_action.triggered.connect(self.stop)
        
        self.menu = QtWidgets.QMenu(mw.tr("Leap Motion"), mw)
        self.menu.addAction(self.connect_leap_action)
        self.menu.addAction(self.stop_leap_action)
        
        # insert Leap menu before Help.
        actions = mw.menuBar().actions()
        for action in actions:
            if action.text() == mw.tr("&Help"):
                mw.menuBar().insertAction(action, self.menu.menuAction())
                break
    
    def init_leap(self):
        self.leap_fetcher = LeapDataFetcher(self)
        self.leap_listener = LeapListener(self.leap_fetcher)
        self.leap_controller = Leap.Controller(self.leap_listener)
        self.leap_controller.set_policy(Leap.Controller.POLICY_ALLOW_PAUSE_RESUME)
        if hmd_mounted: self.leap_controller.set_policy(Leap.Controller.POLICY_OPTIMIZE_HMD)
        self.leap_controller.set_paused(self.paused)
        self.initialized = True


    def build_hand_structure(self):

        # Build hand structure as a dictionary to match Leaps internal data structure
        self.hand_dict = Vividict()

        self.hands = ["Left", "Right"]
        self.fingers = {Finger.TYPE_THUMB: "Thumb", Finger.TYPE_INDEX: "Index",
                Finger.TYPE_MIDDLE: "Middle", Finger.TYPE_RING: "Ring", Finger.TYPE_PINKY: "Pinky"}
        self.bones = {Bone.TYPE_PROXIMAL: "Proximal", Bone.TYPE_INTERMEDIATE: "Intermediate",
                Bone.TYPE_DISTAL: "Distal", Bone.TYPE_METACARPAL: "Metacarpal"}

        # Visualisation
        self.connections = {"Intermediate": "Proximal", "Distal": "Intermediate", "Proximal": "Metacarpal"}
        self.contour_connections = {"PinkyBase": "ThumbMetacarpal", "ThumbMetacarpal": "IndexMetacarpal", "IndexMetacarpal": "MiddleMetacarpal",
                                    "MiddleMetacarpal": "RingMetacarpal", "RingMetacarpal": "PinkyMetacarpal", "PinkyMetacarpal": "PinkyBase"}

        self.left_hand_root = vrScenegraph.findNode("LeftHand")
        self.right_hand_root = vrScenegraph.findNode("RightHand")

        self.left_hand_palm = vrScenegraph.findNode("LeftHandPalm")
        self.right_hand_palm = vrScenegraph.findNode("RightHandPalm")

        #self.wrist = vrScenegraph.findNode("leap_wrist")

        # Big invisible collider
        self.left_hand_collider = vrScenegraph.findNode("LeftHandCollider")
        vrConstraints.createAimConstraint(["LeftIndexDistal"], ["leap_up"], "LeftHandCollider")
        self.right_hand_collider = vrScenegraph.findNode("RightHandCollider")
        vrConstraints.createAimConstraint(["RightIndexDistal"], ["leap_up"], "RightHandCollider")

        for hand in self.hands:
            for finger in self.fingers.values():
                for bone in self.bones.values():
                    name = "{}{}{}".format(hand,finger,bone)
                    node = vrScenegraph.findNode(name)
                    bone_vis_dict = {}
                    if bone in self.connections.keys():
                        bone_vis_dict = self.build_bone_visual("{}{}{}".format(hand,finger,self.connections[bone]), name, hand)
                    bone_vis_dict['joint'] = node

                    self.hand_dict[hand][finger][bone] = bone_vis_dict


        # Hand contours
        self.contours = []
        for hand in self.hands:
            # Use pinky metacarpal base as hand contour anchor
            self.hand_dict[hand]['pinky_base'] = vrScenegraph.findNode("{}PinkyBase".format(hand))

            for joint in self.contour_connections.items():
                # create contour
                name = "{}{}{}{}".format(hand, joint[0], hand, joint[1])
                node = vrScenegraph.findNode(name)
                vrConstraints.createAimConstraint([hand + joint[1]], ["leap_up"], name)
                self.contours.append({'bone': node, 'start': vrScenegraph.findNode(hand+joint[0]), 'end': vrScenegraph.findNode(hand+joint[1])})
        

    def build_bone_visual(self, start, end, hand):
        ''' Create visual bones '''
        node = vrScenegraph.findNode("bonevis_" + end)
        bone_ele = {'bone': node, 'start': vrScenegraph.findNode(start), 'end': vrScenegraph.findNode(end)}
        vrConstraints.createAimConstraint([end], ["leap_up"], "bonevis_" + end)
        return bone_ele


    def connect(self):
        if not self.paused:
            print "Already connected"
            return

        if not self.initialized:
            print "Init Leap"
            self.init_leap()

        print "Starting Leap"

        # Check if there are actually hands in the scene, and add hands if not
        # Only checks for hand root, not each bone
        if vrScenegraph.findNode("Hands").isValid():
            print "Hands found"
        else:
            print "Import hands structure"
            if vr_cam_name:
                cam_node = vrScenegraph.findNode(vr_cam_name)
            else:
                cam_node = vrCamera.getActiveCameraNode()
            vrFileIO.load(filenames = [os.path.join(plugin_path(), "Hands.osb")], parent = cam_node, newFile = False, showImportOptions = False)


        self.build_hand_structure()
        self.paused = False
        self.leap_controller.set_paused(self.paused)
    
    def stop(self):
        print "Stopping Leap"
        self.paused = True
        self.leap_controller.set_paused(self.paused)


class LeapListener(Leap.Listener):
    def __init__(self, fetcher=None):
        super(LeapListener, self).__init__()
        self.fetcher = fetcher

    def on_init(self, controller):
        print "Leap Listener initialized"

    def on_connect(self, controller):
        print "Leap connected"
        self.fetcher.connected = True

    def on_disconnect(self, controller):
        print "Leap disconnected"
        self.fetcher.connected = False


class LeapDataFetcher(vrAEBase):
    def __init__(self, lc, connected = False):
        vrAEBase.__init__(self)
        self.leap_control = lc
        self.connected = connected
        self.last_frame_id = 0
        self.addLoop()

    def recEvent(self, state):
        vrAEBase.recEvent(self, state)

    def loop(self):
        if self.connected and not self.leap_control.paused:
            frame = self.leap_control.leap_controller.frame()
            if frame.id != self.last_frame_id:
                self.apply_hand_transforms(frame)
                self.last_frame_id = frame.id


    def apply_hand_transforms(self, frame):
        mount_factor = -1 if hmd_mounted else 1

        if hide_invisible_hands:
            self.leap_control.left_hand_root.setActive(False)
            self.leap_control.right_hand_root.setActive(False)

        for i in range(0, min(2, len(frame.hands))):
            hand = frame.hands[i]
            palm_pos = hand.palm_position

            hand_side = ""

            #wrist_pos = hand.arm.wrist_position
            #self.leap_control.wrist.setTranslation(wrist_pos.x *mount_factor, -wrist_pos.z, wrist_pos.y *mount_factor)

            # Palm rotation unstable at the moment in hmd mode

            if hand.is_left:
                self.leap_control.left_hand_root.setActive(True)
                self.leap_control.left_hand_palm.setTranslation(palm_pos.x *mount_factor, -palm_pos.z, palm_pos.y *mount_factor)
                #self.leap_control.left_hand_palm.setRotation(math.degrees(hand.direction.pitch), -math.degrees(hand.palm_normal.roll), -math.degrees(hand.direction.yaw) *mount_factor)
                hand_side = "Left"

                self.leap_control.left_hand_collider.setTranslation(palm_pos.x *mount_factor, -palm_pos.z, palm_pos.y *mount_factor)
                target = self.leap_control.hand_dict[hand_side]["Index"]["Distal"]["joint"]
                dist = distance(target.getTranslation(), self.leap_control.left_hand_collider.getTranslation())
                self.leap_control.left_hand_collider.setScale(15, 15, dist + 5)
                

            if hand.is_right:
                self.leap_control.right_hand_root.setActive(True)
                self.leap_control.right_hand_palm.setTranslation(palm_pos.x *mount_factor, -palm_pos.z, palm_pos.y *mount_factor)
                #self.leap_control.right_hand_palm.setRotation(math.degrees(hand.direction.pitch), -math.degrees(hand.palm_normal.roll), -math.degrees(hand.direction.yaw) *mount_factor)
                hand_side = "Right"

                self.leap_control.right_hand_collider.setTranslation(palm_pos.x *mount_factor, -palm_pos.z, palm_pos.y *mount_factor)
                target = self.leap_control.hand_dict[hand_side]["Index"]["Distal"]["joint"]
                dist = distance(target.getTranslation(), self.leap_control.right_hand_collider.getTranslation())
                self.leap_control.right_hand_collider.setScale(15, 15, dist + 5)

            # contour stuff
            leap_bone = hand.fingers.finger_type(Finger.TYPE_PINKY)[0].bone(Bone.TYPE_METACARPAL)
            pos = leap_bone.prev_joint
            bone_scale = leap_bone.width / 2
            pinky = self.leap_control.hand_dict[hand_side]['pinky_base']
            pinky.setTranslation(pos.x *mount_factor, -pos.z, pos.y *mount_factor)
            pinky.setScale(bone_scale, bone_scale, bone_scale)

            for c in self.leap_control.contours:
                self.update_joint(c, bone_scale)

            for finger in self.leap_control.fingers.items():
                for bone in self.leap_control.bones.items():
                    leap_bone = hand.fingers.finger_type(finger[0])[0].bone(bone[0])

                    pos = leap_bone.next_joint
                    bone_scale = leap_bone.width / 2
                    bone_dict = self.leap_control.hand_dict[hand_side][finger[1]][bone[1]]
                    bone_dict['joint'].setTranslation(pos.x *mount_factor, -pos.z, pos.y *mount_factor)
                    bone_dict['joint'].setScale(bone_scale, bone_scale, bone_scale)
                    
                    if 'start' in bone_dict:
                        self.update_joint(bone_dict, bone_scale)
                        
                    # Could read and apply leap motion supplied orientation data here


    def update_joint(self, bone_dict, bone_scale):
        pos = bone_dict['start'].getTranslation()
        dist = distance(pos, bone_dict['end'].getTranslation())
        bone_dict['bone'].setScale(bone_scale * 0.95, bone_scale * 0.95, dist)
        bone_dict['bone'].setTranslation(pos[0], pos[1], pos[2])


leap_control = LeapControl(vredMainWindow(VREDMainWindowId), parent = VREDPluginWidget)

# Script by Constantin Kleinbeck, supported by Simon Nagel
