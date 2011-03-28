#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2009-2011 Rosen Diankov (rosen.diankov@gmail.com)
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Opens a GUI window showing the images from the camera sensors attached on a robot.

.. examplepre-block:: testcamerasensor

Description
-----------

The :ref:`sensor-basecamera` interface has a simple implementation of a pinhole camera. This example shows a robot
with a camera attached to its wrist. The example opens ``data/testwamcamera.env.xml`` and
queries image data from the sensor as fast as possible. The image will change in real-time as the
robot is moved around the scene. The wireframe frustum rendered next to the robot shows the camera's
field of view.

The OpenRAVE XML required to attach a camera to the robot similar to the example above is:

.. code-block:: xml

  <Robot>
    <AttachedSensor>
      <link>wam4</link>
      <translation>0 -0.2 0</translation>
      <rotationaxis>0 1 0 -90</rotationaxis>
      <sensor type="BaseCamera" args="">
        <KK>640 480 320 240</KK>
        <width>640</width>
        <height>480</height>
        <framerate>5</framerate>
        <color>0.5 0.5 1</color>
      </sensor>
    </AttachedSensor>
  </Robot>

See `Sensor Concepts`_ for more infromation on sensors.

.. examplepost-block:: testcamerasensor
"""
from __future__ import with_statement # for python 2.5
__author__ = 'Rosen Diankov'

import time, threading
from openravepy import __build_doc__
if not __build_doc__:
    from openravepy import *
    from numpy import *

try:
    from Tkinter import *
    import tkFileDialog
    import Image, ImageDraw, ImageTk
except ImportError:
    pass

class CameraViewerGUI(threading.Thread):
    class Container:
        pass
    def __init__(self,sensor,title='Camera Viewer'):
        threading.Thread.__init__(self)
        self.sensor = sensor
        self.title = title
        self.lastid = -1
        self.imagelck = threading.Lock()

    def updateimage(self):
        data = self.sensor.GetSensorData()
        if data is not None and not self.lastid == data.stamp:
            width = data.imagedata.shape[1]
            height = data.imagedata.shape[0]
            self.imagelck.acquire()
            self.image = Image.frombuffer('RGB',[width,height], data.imagedata.tostring(), 'raw','RGB',0,1)
            self.imagelck.release()

            photo = ImageTk.PhotoImage(self.image)
            if self.container is None:
                self.container = self.Container()
                self.container.width = width
                self.container.height = height
                self.container.main = self.main
                self.container.canvas = Canvas(self.main, width=width, height=height)
                self.container.canvas.pack(expand=1, fill=BOTH)#side=TOP,fill=X)#
                self.container.obr = None

            self.container.canvas.create_image(self.container.width/2, self.container.height/2, image=photo)
            self.container.obr = photo
            self.lastid = data.stamp
        self.main.after(100,self.updateimage)

    def saveimage(self,filename):
        self.imagelck.acquire()
        self.image.save(filename)
        self.imagelck.release()

    def run(self):
        self.main = Tk()
        self.main.title(self.title)      # window title
        self.main.resizable(width=True, height=True)
        self.container = None
        self.main.after(0,self.updateimage)
        self.main.mainloop()

class OpenRAVEScene:
    def __init__(self,env,scenefilename,robotname=None):
        self.orenv = env
        if not self.orenv.Load(scenefilename):
            raise ValueError('failed to open %s openrave file'%scenefilename)
        if len(self.orenv.GetRobots()) == 0:
            raise ValueError('no robots found in scene %s'%scenefilename)

        with env:
            sensors = []
            if robotname is None:
                self.robot = self.orenv.GetRobots()[0]
            else:
                self.robot = [r for r in self.orenv.GetRobots() if r.GetName()==robotname][0]

            # create a camera viewer for every camera sensor
            self.viewers = []
            for attachedsensor in self.robot.GetAttachedSensors():
                if attachedsensor.GetSensor() is not None and attachedsensor.GetSensor().Supports(Sensor.Type.Camera):
                    attachedsensor.GetSensor().Configure(Sensor.ConfigureCommand.PowerOn)
                    sensors.append(attachedsensor)
        time.sleep(1) # wait a while for sensors to initialize
        with env:
            for attachedsensor in sensors:
                sensordata = attachedsensor.GetSensor().GetSensorData(Sensor.Type.Camera)
                if sensordata is not None:
                    title = attachedsensor.GetName()
                    if len(title) == 0:
                        title = attachedsensor.GetSensor().GetName()
                        if len(title) == 0:
                            title = 'Camera Sensor'
                    self.viewers.append(CameraViewerGUI(sensor=attachedsensor.GetSensor(),title=title))
        print 'found %d camera sensors on robot %s'%(len(self.viewers),self.robot.GetName())
        for viewer in self.viewers:
            viewer.start()
    
    def quitviewers(self):
        for viewer in self.viewers:
            viewer.main.quit()
    def __del__(self):
        self.quitviewers()

def main(env,options):
    "Main example code."
    scene = OpenRAVEScene(env,options.scene,options.robotname)
    try:
        while(True):
            cmd = raw_input('Enter command (q-quit,c-capture image): ')
            if cmd == 'q':
                break
            elif cmd == 'c':
                for i,viewer in enumerate(scene.viewers):
                    print 'saving image%d.png'%i
                    viewer.saveimage('image%d.png'%i)
    finally:
        scene.quitviewers()
    
from optparse import OptionParser
from openravepy import OpenRAVEGlobalArguments, with_destroy

@with_destroy
def run(args=None):
    """Command-line execution of the example.

    :param args: arguments for script to parse, if not specified will use sys.argv
    """
    parser = OptionParser(description='Displays all images of all camera sensors attached to a robot.')
    OpenRAVEGlobalArguments.addOptions(parser)
    parser.add_option('--scene',
                      action="store",type='string',dest='scene',default='data/testwamcamera.env.xml',
                      help='OpenRAVE scene to load')
    parser.add_option('--robotname',
                      action="store",type='string',dest='robotname',default=None,
                      help='Specific robot sensors to display (otherwise first robot found will be displayed)')
    (options, leftargs) = parser.parse_args(args=args)
    env = OpenRAVEGlobalArguments.parseAndCreate(options,defaultviewer=True)
    main(env,options)

if __name__=='__main__':
    run()
