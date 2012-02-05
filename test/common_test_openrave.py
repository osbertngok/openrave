# -*- coding: utf-8 -*-
# Copyright (C) 2011 Rosen Diankov <rosen.diankov@gmail.com>
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
from __future__ import with_statement # for python 2.5

from openravepy import *
from openravepy import misc
import numpy
from numpy import *

from itertools import izip, combinations
import nose
from nose.tools import assert_raises
import fnmatch
import time
import os
import cPickle as pickle
_multiprocess_can_split_ = True

g_epsilon = 1e-7
g_jacobianstep = 0.01
g_envfiles = ['data/lab1.env.xml','data/pr2wam_test1.env.xml','data/hanoi_complex.env.xml']
g_robotfiles = ['robots/pr2-beta-static.zae','robots/barrettsegway.robot.xml','robots/neuronics-katana.zae','robots/pa10schunk.robot.xml','robots/barrettwam-dual.robot.xml']

def setup_module(module):
    dbdir = os.path.join(os.getcwd(),'.openravetest')
    os.environ['OPENRAVE_DATABASE'] = dbdir
    os.environ['OPENRAVE_HOME'] = dbdir
    RaveInitialize(load_all_plugins=True, level=int32(DebugLevel.Info)|int32(DebugLevel.VerifyPlans))
    assert(os.path.samefile(RaveGetHomeDirectory(),dbdir))
    
def teardown_module(module):
    RaveDestroy()

def transdist(list0,list1):
    assert(len(list0)==len(list1))
    return sum([sum(abs(item0-item1)) for item0, item1 in izip(list0,list1)])

def axisangledist(axis0,axis1):
    return arccos(numpy.minimum(1.0,abs(dot(quatFromAxisAngle(axis0),quatFromAxisAngle(axis1)))))

def randtrans():
    T = matrixFromAxisAngle(random.rand(3)*6-3)
    T[0:3,3] = random.rand(3)-0.5            
    return T

def randquat(N=1):
    L = 0
    while any(L == 0):
        q = random.rand(N,4)-0.5
        L = sqrt(sum(q**2,1))
    return q/tile(L,(4,1)).transpose()

def randpose(N=1):
    poses = random.rand(N,7)-0.5
    poses[:,0:4] /= tile(sqrt(sum(poses[:,0:4]**2,1)),(4,1)).transpose()
    return poses

def randlimits(lower,upper):
    return lower+random.rand(len(lower))*(upper-lower)

def bodymaxjointdist(link,localtrans):
    body = link.GetParent()
    joints = body.GetChain(0,link.GetIndex(),returnjoints=True)
    baseanchor = joints[0].GetAnchor()
    eetrans = transformPoints(link.GetTransform(),[localtrans])
    armlength = 0
    for j in body.GetDependencyOrderedJoints()[::-1]:
        armlength += sqrt(sum((eetrans-j.GetAnchor())**2))
        eetrans = j.GetAnchor()    
    return armlength

def locate(pattern, root=os.curdir):
    """Locate all files matching supplied filename pattern in and below supplied root directory.
    """
    for path, dirs, files in os.walk(os.path.abspath(root)):
        for filename in fnmatch.filter(files, pattern):
            yield os.path.join(path, filename)

class EnvironmentSetup(object):
    __name__='openrave_common_test'
    def setup(self):
        self.env=Environment()
        self.env.StopSimulation()
    def teardown(self):
        self.env.Destroy()
        self.env=None
    def LoadDataEnv(self,*args,**kwargs):
        print 'LoadDataEnv'
        assert(self.env.LoadData(*args,**kwargs))
        self._PreprocessEnv()
    
    def LoadEnv(self,*args,**kwargs):
        print 'LoadEnv',args,kwargs
        assert(self.env.Load(*args,**kwargs))
        self._PreprocessEnv()

    def LoadRobot(self,*args,**kwargs):
        print 'LoadRobot',args,kwargs
        robot=self.env.ReadRobotURI(*args,**kwargs)
        self.env.AddRobot(robot,True)
        self._PreprocessRobot(robot)
        return robot

    def LoadRobotData(self,*args,**kwargs):
        robot=self.env.ReadRobotData(*args,**kwargs)
        self.env.AddRobot(robot,True)
        self._PreprocessRobot(robot)
        return robot

    def RunTrajectory(self,robot,traj):
        assert(traj is not None)
        robot.GetController().SetPath(traj)
        while not robot.GetController().IsDone():
            self.env.StepSimulation(0.01)
        
    def _PreprocessEnv(self):
        for robot in self.env.GetRobots():
            self._PreprocessRobot(robot)

    def _PreprocessRobot(self,robot):
        if robot.GetController() is not None and robot.GetController().GetXMLId().lower() == 'idealcontroller':
            # need to throw exceptions so test fails
            robot.GetController().SendCommand('SetThrowExceptions 1')
            