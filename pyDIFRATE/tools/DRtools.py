#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright 2021 Albert Smith-Penzel

This file is part of Frames Theory Archive (FTA).

FTA is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

FTA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with FTA.  If not, see <https://www.gnu.org/licenses/>.


Questions, contact me at:
albert.smith-penzel@medizin.uni-leipzig.de


Created on Fri Nov  8 13:44:13 2019

@author: albertsmith
"""

import os
import numpy as np
import pandas as pd
import re
from scipy.stats import mode

#%% Some useful tools (Gyromagnetic ratios, spins, dipole couplings)
def NucInfo(Nuc=None,info='gyro'):
    """ Returns the gyromagnetic ratio for a given nucleus. Usually, should be 
    called with the nucleus and mass number, although will default first to 
    spin 1/2 nuclei if mass not specified, and second to the most abundant 
    nucleus. A second argument, info, can be specified to request the 
    gyromagnetic ratio ('gyro'), the spin ('spin'), the abundance ('abund'), or 
    if the function has been called without the mass number, one can return the 
    default mass number ('mass'). If called without any arguments, a pandas 
    object is returned containing all nuclear info ('nuc','mass','spin','gyro',
    'abund')
    """
    
    Nucs=[]
    MassNum=[]
    spin=[]
    g=[]
    Abund=[]

    dir_path = os.path.dirname(os.path.realpath(__file__))
    
    with open(dir_path+"/GyroRatio") as f:
        data=f.readlines()
        for line in data:
            line=line.strip().split()
            MassNum.append(int(line[1]))
            Nucs.append(line[3])
            spin.append(float(line[5]))
            g.append(float(line[6]))
            Abund.append(float(line[7]))
    
    NucData=pd.DataFrame({'nuc':Nucs,'mass':MassNum,'spin':spin,'gyro':g,'abund':Abund})
    
    
    if Nuc==None:
        return NucData
    else:
        
        if Nuc=='D':
            Nuc='2H'
        
        mass=re.findall(r'\d+',Nuc)
        if not mass==[]:
            mass=int(mass[0])
            
        
        Nuc=re.findall(r'[A-Z]',Nuc.upper())
        
        if np.size(Nuc)>1:
            Nuc=Nuc[0].upper()+Nuc[1].lower()
        else:
            Nuc=Nuc[0]
            
            
            
        NucData=NucData[NucData['nuc']==Nuc]
       
        if not mass==[]:    #Use the given mass number
            NucData=NucData[NucData['mass']==mass]
        elif any(NucData['spin']==0.5): #Ambiguous input, take spin 1/2 nucleus if exists
            NucData=NucData[NucData['spin']==0.5] #Ambiguous input, take most abundant nucleus
        elif any(NucData['spin']>0):
            NucData=NucData[NucData['spin']>0]
        
        NucData=NucData[NucData['abund']==max(NucData['abund'])]
            
        
        h=6.6260693e-34
        muen=5.05078369931e-27
        
        NucData['gyro']=float(NucData['gyro'])*muen/h
#        spin=float(NucData['spin'])
#        abund=float(NucData['abund'])
#        mass=float(NucData['spin'])
        if info[:3]=='all':
            return NucData
        else:
            return float(NucData[info])

def dipole_coupling(r,Nuc1,Nuc2):
    """ Returns the dipole coupling between two nuclei ('Nuc1','Nuc2') 
    separated by a distance 'r' (in nm). Result in Hz (gives full anisotropy,
    not b12, that is 2x larger than b12)
    """
    
    gamma1=NucInfo(Nuc1)
    gamma2=NucInfo(Nuc2)
    
    h=6.6260693e-34 #Plancks constant in J s
    mue0 = 12.56637e-7  #Permeability of vacuum [T^2m^3/J]
    
    return h*2*mue0/(4*np.pi*(r/1e9)**3)*gamma1*gamma2

def corr_SVD_switching(data0,data_in):
    """
    Identifies sign switching in data objects that have been processed only 
    with un-optimized r matrices (r_no_opt). Will resort the R data, and 
    average the results
    """
    rhoz0=data0.sens._rho_eff(mdl_num=None)[0]
    
    R=list()
    Rvar=list()
    
    for d in data_in:
        mat=np.dot(rhoz0,d.sens._rho_eff(mdl_num=None)[0].T)
        R.append(np.dot(mat,d.R.T).T)
        Rvar.append(np.dot(mat,d.R_std.T**2).T)
     
    return np.array(R),np.array(Rvar)
    
#%% Tool for averaging data classes
def avg_data(data_in,weighted=True,weight=None,r_no_opt=False):
    """
    Averages together a list of data objects generated by pyDIFRATE. Performs
    a quick check that the sensitivities are the same for each object, and will
    perform sign flips for detectors that don't match (this may happen for
    detectors generated using the r_no_opt option- the sign of the SVD is not
    numerically stable). If detectors exhibit a mismatch, a warning will
    be printed (no warning will occur for a difference in sign). If weighting
    is included, then data will be averaged, considering the standard deviation
    of the data.
    
    Data produced with unoptimized r matrices may have sign swaps and occasional
    scrambling of the detectors. This can be corrected, set r_no_opt=True
    """
    if isinstance(data_in,dict):
        data_in,_=dict2list(data_in)
        
    try:
        data=data_in[0].copy()
    except:
        data=data_in[0].__class__()
        data.sens=data_in[0].sens
        data.R=data_in[0].R.copy()
        print('Warning: deep copy failed')
            
    

    
    if r_no_opt:
        R,Rvar=corr_SVD_switching(data,data_in)            
    else:
        R=list()
        Rvar=list()
        SZ=data.R.shape
        
        sign=sens_sign_check(data,data_in)
    
        for k,(d,s) in enumerate(zip(data_in,sign)):
            R.append(s*d.R)
            Rvar.append((d.R_std**2))
            
            R[-1]=R[-1].reshape(np.prod(SZ))
            Rvar[-1]=Rvar[-1].reshape(np.prod(SZ))
                    
        R=np.array(R)
        Rvar=np.array(Rvar)
    if weighted:
        if weight is None:
            wt=1/Rvar
            wt=(wt/wt.sum(axis=0))        
        else:
            wt=np.array(weight)
            wt=wt/wt.sum(axis=0)
    else:
        wt=1/R.shape[0]
    R=(R*wt).sum(axis=0)
    Rvar=(Rvar*(wt**2)).sum(axis=0)       

    if r_no_opt:
        data.R=R
        data.R_std=np.sqrt(Rvar)
    else:
        data.R=R.reshape(SZ)
        data.R_std=np.sqrt(Rvar.reshape(SZ))
    data.R_u=None
    data.R_l=None

    return data

#%% Appends data classes together
def append_data(data_in,labels=None,index=None):
    """
    Appends a list of data objects. A second argument, labels, may contain a list,
    the same length as data_in, which will be appended to the existing labels 
    for an object.
    
    One may also input a dictionary, containing data objects. In this case, the
    keys will be used as labels, unless the user inputs their own labels (or sets
    labels='' to override this functionality)
    
    One may  re-sort the result by providing an index to re-order all data. 
    """
    
    if isinstance(data_in,dict):
        data_in,dict_label=dict2list(data_in)
        if labels is None and labels!='':
            labels=dict_label
        elif labels=='':
            labels=None
    
    data=data_in[0].copy()
    
    sign=sens_sign_check(data,data_in)
    
    
    flds=['R','R_std','R_u','R_l','Rc','Rin','Rin_std','S2','S2in','S2in_std','S2c']
    R=dict()
    label=list()
    for f in flds:R[f]=list()
    
    for k,(d,s) in enumerate(zip(data_in,sign)):
        for f in flds:
            x=getattr(d,f)
            if x is not None: R[f].append(x)
        if labels is None:
            label.append(d.label)
        else:
            label.append([str(labels[k])+str(l) for l in d.label])
    
    
    for f in flds:
        if len(R[f])!=0:
            try:
                setattr(data,f,np.concatenate(R[f],axis=0))
            except:
                print('Warning: Data sizes for "{0}" do not match and have been omitted'.format(f))    
    data.label=np.concatenate(label,axis=0)
    
    if index is not None:
        for f in flds:
            x=getattr(data,f)            
            if x is not None:
                x0=np.zeros(x.shape)
                x0[index]=x
                setattr(data,f,x0)
        if data.label is not None:
            lbl=np.empty(data.label.shape,dtype=data.label.dtype)
            lbl[index]=data.label
            data.label=lbl
#    R=list()
#    R_std=list()
#    R_u=list()
#    R_l=list()
#    Rc=list()
#    Rin=list()
#    Rin_std=list()
#    label=list()
    
#    for k,(d,s) in enumerate(zip(data_in,sign)):
#        R.append(s*d.R)
#        R_std.append(d.R_std)
#        if d.Rc is not None:
#            Rc.append(d.Rc)
#        if d.R_u is not None:
#            R_u.append(d.R_u)
#        if d.R_l is not None:
#            R_l.append(d.R_l)
#        if d.Rin is not None:
#            Rin.append(d.Rin)
#        if d.Rin_std is not None:
#            
#        if labels is None:
#            label.append(d.label)
#        else:
#            label.append([str(labels[k])+str(l) for l in d.label])
            
#    data.R=np.concatenate(R,axis=0)
#    data.R_std=np.concatenate(R_std,axis=0)
#    if len(Rc)>0:
#        data.Rc=np.concatenate(Rc,axis=0)
#    if len(R_u)>0:
#        data.R_u=np.concatenate(R_u,axis=0)
#    if len(R_l)>0:
#        data.R_l=np.concatenate(R_l,axis=0)
#    data.label=np.concatenate(label,axis=0)
    
    return data
    
def dict2list(data_in):
    """
    If data is provided in a dictionary, this function returns all instances
    of data found in that dictionary, and also returns labels based on the keys
    
    """
    
    labels=list()
    data=list()
    
    for l,d in data_in.items():
        if hasattr(d,'R') and hasattr(d,'R_std') and hasattr(d,'label'):
            labels.append(l)
            data.append(d)
    return data,labels

def sens_sign_check(data0,data_in):
    """
    Compares the sensitivities for a reference data object and a list of other
    objects. Returns a list of "signs" which indicate how to switch the sign
    on the detector responses, in case the sign on the sensitivities is switched.
    
    Also returns warnings if the sensitivities cannot be resolved between two
    data objects.
    """
    
    if data0.sens is not None:
        "We'll use the sensitivity of the first object to compare to the rest, and switch signs accordingly"
        rhoz0=data0.sens._rho_eff(mdl_num=None)[0]
        step=np.array(rhoz0.shape[1]/10).astype(int)
        rhoz0=rhoz0[:,::step]
        z0=data0.sens.tc()[[0,-1]]
    else:
        rhoz0=None
    
    sign=list()
    nd=data0.R.shape[1]
    
    for k,d in enumerate(data_in):
        if rhoz0 is not None and d.sens is not None:
            rhoz=d.sens._rho_eff(mdl_num=None)[0][:,::step]

            if rhoz0.shape==rhoz.shape and np.all(z0==d.sens.tc()[[0,-1]]):
                test=rhoz0/rhoz

                if np.any(np.abs(np.abs(test)-1)>1e-3):
                    print('Sensitivities disagree for the {}th data object'.format(k))
                    sign.append(np.ones(nd))
                else:
                    
                    sign.append(np.squeeze(mode(np.sign(test),axis=1)[0]))  
                    """
                    #Just in case we come up with some nan, we use mode, 
                    which gets rid of them. 
                    Also, could fix average out spurious sign changes near 0
                    """ 
            else:
                print('Sensitivity shapes or ranges do not match for the {}th data object'.format(k))
                sign.append(np.ones(nd))
                
        else:
            sign.append(np.ones(nd))
        sign[-1][np.isnan(sign[-1])]=1

            
    return sign

#%% Take the product of two data classes (in correlation function space)
def prod_mat(r1,r2=None,r=None):
    """
    Calculates a matrix that allows one to take the product of two sets of 
    detectors.
    
    That is, suppose C(t)=C0(t)*C1(t). We have detector analyzes of C1(t) and
    C2(t), where C0(t) and C1(t) are of the same resolution, and therefore have
    r matrices of the same size
    
    Given the detector analysis of C1(t) and C2(t), we calculate a product matrix:
        
    p01=
    [[p0_0*p1_0,p0_1*p1_0,p0_2*p1_0,...],
     [p0_1*p1_0,p0_1*p1_1,p0_2*p1_1,...],
     [p0_2*p1_0,p0_1*p1_2,p0_2*p1_2,...],
     ...]
    
    Expanding this into a single vector, say p01, we may multiply 
    p=np.dot(pr,p01)
    Where p is the detector analysis result of C(t)
    
    Note 1: p01=np.dot(np.atleast_2d(p1).T,np.atleast(2d(p0))).reshape(n**2), 
    where n is the number of detectors
    
    Note 2: The matrices need to be the same size, but do not need to be the 
    same matrix. If they are the same, one argument is required. If they are
    different, two arguments are required. One may finally provide a 3rd r
    if the final set of detectors is different than the initial set (the third
    r matrix will be th final matrix)
    
    pr = calc_prod_mat(r1,r2=None,r=None)
    """
    
    if hasattr(r1,'r'):
        r1=r1.r()
    if r2 is None:
        r2=r1
    elif hasattr(r2,'r'):
        r2=r2.r()
    if r is None:
        r=r1
    elif hasattr(r,'r'):
        r=r.r()
    
    n1=r1.shape[1]
    n2=r2.shape[1]
    pr0=np.array([np.dot(np.atleast_2d(row2).T,np.atleast_2d(row1)).reshape(n1*n2)\
                  for row1,row2 in zip(r1,r2)])
    
    pr=np.linalg.lstsq(r,pr0,rcond=None)[0]
#    pr=np.dot(np.linalg.pinv(r),pr0)
    
    return pr

def calc_prod(data,r,nf=None):
    """
    Takes the product of a data sets, where two or more detector analyses are 
    assumed to be analyzing individual correlation functions such that
    C(t)=C0(t)*C1(t)
    
    One may input a list of data objects, where the product of all is returned
    or one may input a single object, for which multiple analyzes are contained
    (usually, this is the result of an iRED/frame analysis)
    
    In case a single data object is used, the user must provide the number of
    different frames used (nf)
    
    In case the list of data has different detectors, the detectors from the
    first element of the list will be used (all data must come from correlation
    functions having the same resolution)
    
    out=calc_prod(data_list)     
    
        or
    
    out=calc_prod(data,nf)
    
    """
    
    "User input check"
    if not(isinstance(data,list)) and nf is None:
        print('If a list of data is not provided, then the number of frames must be given')
        return
    
    
    R=list()
    R_std=list()
    "I wish that we didn't have to provide r manually, especially "
#    r0=list()
    
    "Prepare the data"
    if nf is None:
        out=data[0].copy()
#        r=data[0].detect
        for d in data:
            R.append(d.R)
            R_std.append(d.R_std)
#            r0.append(d.detect)
    else:
        out=data.copy()
#        r=data.detect
        n=int(data.R.shape[0]/nf)
        for k in range(nf):
            R.append(data.R[k*n:(k+1)*n,:])
            R_std.append(data.R_std[k*n:(k+1)*n,:])
#            r0.append(data.detect)
            
            
    "Make sure r0 is a list"
    if isinstance(r,list):
        r0=r
    else:
        r0=[r for k in range(len(R))]
    
    "If r is detector object, get out the r matrix itself"
    r0=[r.r() if hasattr(r,'r') else r for r in r0]
    r=r0[0]
    
    R1=R.pop()
    r1=r0.pop()
    R1_var=R_std.pop()**2


    while len(R)>0:
        "Calculate the product matrix"
        r2=r0.pop()
        n1=r1.shape[1]
        n2=r2.shape[1]
        pr=prod_mat(r1,r2,r)
        r1=r
        "Calculate the product of detectors"
        R2=R.pop()
        p1p2=np.array([np.dot(np.atleast_2d(row2).T,np.atleast_2d(row1)).reshape(n1*n2)\
                       for row1,row2 in zip(R1,R2)]).T
        R1=np.dot(pr,p1p2).T
       
        "Calculate the variance of the product of detector responses"
        R2_var=R_std.pop()**2
        p1p2_var=list()
        for row1,row2,var1,var2,f in zip(R1,R2,R1_var,R2_var,p1p2.T):
            
            x=np.atleast_2d(var1/row1).T.repeat(n2,axis=1).reshape(n1*n2)
            y=np.atleast_2d(var2/row2).repeat(n1,axis=0).reshape(n1*n2)

            p1p2_var.append(f**2*(x+y))
        
        "Calculate the variance of the product matrix with individual variances"
        R1_var=np.dot(pr,np.array(p1p2_var).T).T
            
    out.R=R1
    out.R_std=np.sqrt(R1_var)    
    
    return out
 

def linear_ex(x0,I0,x,dim=None,mode='last_slope'):
    """
    Takes some initial data, I0, that is a function a function of x0 in some
    dimension of I0 (by default, we search for a matching dimension- if more than
    one dimension match, then the first matching dimension will be used)
    
    Then, we extrapolate I0 between the input points such that we return a new
    I with axis x. 
    
    This is a simple linear extrapolation– just straight lines between points.
    If points in x fall outside of points in x0, we will use the two end points
    to calculate a slope and extrapolate from there.
    
    x0 must be sorted in ascending or descending order. x does not need to be sorted.
    
    If values of x fall outside of the range of x0, by default, we will take the
    slope at the ends of the given range. Alternatively, set mode to 'last_value'
    to just take the last value in x0
    """
    
    assert all(np.diff(x0)>=0) or all(np.diff(x0)<=0),"x0 is not sorted in ascending/descending order"
    
    
    
    x0=np.array(x0)
    I0=np.array(I0)
    ndim=np.ndim(x)
    x=np.atleast_1d(x)
    
    "Determine what dimension we should extrapolate over"
    if dim is None:
        i=np.argwhere(x0.size==np.array(I0.shape)).squeeze()
        assert i.size!=0,"No dimensions of I0 match the size of x0"
        dim=i if i.ndim==0 else i[0]
    

    "Swap dimensions of I0"
    I0=I0.swapaxes(0,dim)
    if np.any(np.diff(x0)<0):
#        i=np.argwhere(np.diff(x0)<0)[0,0]    
#        x0=x0[:i]
#        I0=I0[:i]    
        x0,I0=x0[::-1],I0[::-1]
    
    "Deal with x being extend beyond x0 limits"
    if x.min()<=x0[0]:
        I0=np.insert(I0,0,np.zeros(I0.shape[1:]),axis=0)
        x0=np.concatenate(([x.min()-1],x0),axis=0)
        if mode.lower()=='last_slope':
            run=x0[2]-x0[1]
            rise=I0[2]-I0[1]
            slope=rise/run 
            I0[0]=I0[1]-slope*(x0[1]-x0[0])
        else:
            I0[0]=I0[1]
    if x.max()>=x0[-1]:
        I0=np.concatenate((I0,[np.zeros(I0.shape[1:])]),axis=0)
        x0=np.concatenate((x0,[x.max()+1]),axis=0)
        if mode.lower()=='last_slope':
            run=x0[-3]-x0[-2]
            rise=I0[-3]-I0[-2]
            slope=rise/run
            I0[-1]=I0[-2]-slope*(x0[-2]-x0[-1])
        else:
            I0[-1]=I0[-2]
        
    "Index for summing"
    i=np.digitize(x,x0)
    
    I=((I0[i-1].T*(x0[i]-x)+I0[i].T*(x-x0[i-1]))/(x0[i]-x0[i-1])).T
    
    if ndim==0:
        return I[0]
    else:
        return I.swapaxes(0,dim)
    
    
        
#%% Some classes for making nice labels with units and unit prefixes   
        
class Default2Parent(object):
    def __init__(self,varname):
        self.value=list()
        self.varname=varname
    def __get__(self,instance,owner):
        if not(self.varname in instance.index):
            instance.index[self.varname]=len(self.value)
            self.value.append(None)
        i=instance.index[self.varname]
        if self.value[i] is not None:return self.value[i]
        return getattr(instance.parent,self.varname)
    def __set__(self,instance,value):
        if not(self.varname in instance.index):
            instance.index[self.varname]=len(self.value)
            self.value.append(None)
        i=instance.index[self.varname]
        self.value[i]=value
    def __repr__(self):
        return str(self.__get__())
    
class NiceStr():
    unit=Default2Parent('unit')
    include_space=Default2Parent('include_space')
    no_prefix=Default2Parent('no_prefix')
    
    def __init__(self,value,parent):
        self.value=value
        self.parent=parent
        self.range=False
        self.index={}
        
#        self.unit
#        self.include_space
#        self.no_prefix
 
    def __repr__(self):
        return self.value

    def prefix(self,value):
        if value==0:
            return '',0,1    
        pwr=np.log10(np.abs(value))
        x=np.concatenate((np.arange(-15,18,3),[np.inf]))
        pre=['a','f','p','n',r'$\mu$','m','','k','M','G','T']
        #Probably the mu doesn't work
        for x0,pre0 in zip(x,pre):
            if pwr<x0:return '' if self.no_prefix else pre0,value*10**(-x0+3),10**(-x0+3)
            
    def format(self,*args,**kwargs):        
        string=self.value
        count=0
        space=' ' if self.parent.include_space else ''
        unit=self.unit if self.unit else ''
        parity=True
        while ':q' in string and count<10:
            parity=not(parity)
            count+=1
            
            #Find the 'q' tagged formating strings
            i=string.find(':q')
            #Extract the correct value from args and kwargs
            if string[i-1]=='{':
                v=args[0]
                start=i-1
            else:
                i1=string[:i].rfind('{')
                start=i1
                try:
                    v=args[int(string[i1+1:i])]
                except:
                    v=kwargs[string[i1+1:i]]
            #If we are specifying ranges, we only put units on every other number (fairly restricted implementation)
            if self.range and parity:  #Second steps only
                i1=string[i:].find('}')+i
                end=i1+1
                bd=1 if v==0 else np.floor(np.log10(np.abs(v))).astype(int)+1
                dec=np.max([prec-bd,0])
                if dec==0:v=np.round(v,prec-bd)
                v*=scaling #Use the same scaling as the previous step               
            else:

                if string[i+2]=='}':
                    prec=2
                    end=i+3
                else:
                    i1=string[i:].find('}')+i
                    end=i1+1
                    prec=int(string[i+2:i1])
                
                pre,v,scaling=self.prefix(v)
                
                bd=1 if v==0 else np.floor(np.log10(np.abs(v))).astype(int)+1
                dec=np.max([prec-bd,0])
                if dec==0:v=np.round(v,prec-bd)
                
            if not(self.range) or parity: #Second steps
                string=string[:start]+('0' if v==0 else '{{:.{}f}}'.format(dec).format(v))+space+pre+unit+string[end:]
            else: #First steps only
                string=string[:start]+('0' if v==0 else '{{:.{}f}}'.format(dec).format(v))+string[end:]  

        return string.format(*args,**kwargs)
        



class Strings(object):
    def __init__(self,unit=None,include_space=True,no_prefix=False):
        self.unit=unit
        self.include_space=include_space
        self.no_prefix=False
        self._index=-1
    def __setattr__(self,name,value):
        if name in ['unit','include_space','no_prefix','_index']:
            super().__setattr__(name,value)
        else:
            super().__setattr__(name,NiceStr(value,self))
    def __call__(self,string):
        self._index+=1
        setattr(self,'_{}'.format(self._index),string)
        return getattr(self,'_{}'.format(self._index))


nice_str=Strings()

       