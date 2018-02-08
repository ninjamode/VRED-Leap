# Leap Motion support for Autodesk VRED

Requires at least VRED 2018.4





## Features

- Left and right hand
- Hand outlines
- Finger size and diameter based on actual Leap data
- Start and end of collision callbacks (can also be used without Leap)



This plugin does not try to read joint rotation, only position. Might cause instabilities (not compiled with VS 2015 for VRED).

## Installation

- Install Leap Motion Orion drivers
- Put the lib-leap folder (see releases) into either `~\Autodesk` or `C:\Autodesk\`
- Copy the "plugin" folder in your VRED plugin directory
  - This path depends on your VRED version. For 2018.4, it's `C:/Users/<username>/Documents/Autodesk/VRED-10.2/ScriptPlugins` (internal version 10.2).

## Usage

This plugin will add a "Leap Motion" item to your menu bar. Press "Start Leap Motion" under this menu item to connect to the Leap service and start receiving hand data. This will also automatically add hands to your scene if not already present (under your camera node).

Also see the demo scene and the `Collider.py` script for examples on how to add hand interaction to your scene. The collider script extends the VRED build in collider with start and end of collision callbacks, which you can use to trigger interaction.