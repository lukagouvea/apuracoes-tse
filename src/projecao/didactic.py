"""Synthetic, inspectable worked examples evaluated by the production estimators."""
import math
import pandas as pd
from .models import Config,History,Snapshot,predict


def _history(ufs,regions,shares,counts):
    return History(pd.DataFrame({'uf':ufs,'municipality':[str(i+1) for i in range(len(ufs))],
        'region':regions,'n_sections':counts,'ref_share':shares,'ref_per_section':[100.]*len(ufs),
        'ref_size':[100.*n for n in counts],'matched':[True]*len(ufs)}))


def poststrat_case(nx,ny):
    if not 0<=nx<=10 or not 0<=ny<=20:raise ValueError('Invalid section counts')
    history=_history(['SP','SP'],['SE','SE'],[.5,.5],[10,20])
    a=60*nx+40*ny;valid=100*(nx+ny)
    snapshot=Snapshot(pd.DataFrame({'uf':['SP','SP'],'municipality':['1','2'],
        'n_observed':[nx,ny],'votes_a':[60*nx,40*ny],'votes_b':[40*nx,60*ny]}))
    p=predict(snapshot,history,Config(method='poststrat'))
    baseline=a/valid if valid else None
    sx=.6 if nx else (baseline if valid else .5)
    sy=.4 if ny else (baseline if valid else .5)
    remaining_x=(10-nx)*100;remaining_y=(20-ny)*100
    assert math.isclose(p.votes_a,a+sx*remaining_x+sy*remaining_y,abs_tol=1e-8)
    return {'nx':nx,'ny':ny,'share_x':sx,'share_y':sy,'baseline':baseline,'projection':p.share_a,
        'observed_a':a,'observed_valid':valid,'remaining_x':remaining_x,'remaining_y':remaining_y,
        'remaining_valid':remaining_x+remaining_y,'remaining_a':p.votes_a-a,'projected_a':p.votes_a,
        'total_valid':p.votes_a+p.votes_b,'fraction_sections':p.fraction_sections}


def swing_case(shift_pp):
    if not -10<=shift_pp<=10:raise ValueError('Example shift outside supported range')
    shares=[.3,.5,.7,.4];shift=shift_pp/100
    history=_history(['SP']*4,['SE']*4,shares,[10]*4)
    current=[p+shift for p in shares[:3]]
    a=[round(p*1000) for p in current]
    snapshot=Snapshot(pd.DataFrame({'uf':['SP']*3,'municipality':['1','2','3'],
        'n_observed':[10]*3,'votes_a':a,'votes_b':[1000-v for v in a]}))
    p=predict(snapshot,history,Config(method='swing'))
    target=(p.votes_a-sum(a))/1000
    assert math.isclose(target,.4+shift,abs_tol=1e-10)
    return {'shift_pp':shift_pp,'historical':shares,'observed_shares':current,'target_prediction':target,
        'projection':p.share_a,'baseline':sum(a)/3000,'observed_a':sum(a),'observed_valid':3000,
        'remaining_valid':1000,'remaining_a':p.votes_a-sum(a),'projected_a':p.votes_a,'total_valid':4000}


def hierarchy_case(n_sp,lambda_uf):
    if not 0<=n_sp<=100 or lambda_uf<=0:raise ValueError('Invalid hierarchy example controls')
    history=_history(['SP','MG','BA'],['SE','SE','NE'],[.5]*3,[100]*3)
    snapshot=Snapshot(pd.DataFrame({'uf':['SP','MG','BA'],'municipality':['1','2','3'],
        'n_observed':[n_sp,100,100],'votes_a':[70*n_sp,5000,4500],'votes_b':[30*n_sp,5000,5500]}))
    cfg=Config(method='hierarchical',lambda_region=3000.,lambda_uf=float(lambda_uf))
    p=predict(snapshot,history,cfg)
    a=70*n_sp+9500;valid=100*n_sp+20000
    national_swing=a/valid-.5
    regional_swing=(100*n_sp*.2+cfg.lambda_region*national_swing)/(100*n_sp+10000+cfg.lambda_region)
    weight=100*n_sp/(100*n_sp+lambda_uf)
    state_swing=weight*.2+(1-weight)*regional_swing
    target=.5+state_swing;remaining=(100-n_sp)*100
    assert math.isclose(p.votes_a,a+target*remaining,abs_tol=1e-7)
    return {'n_sp':n_sp,'lambda_uf':lambda_uf,'lambda_region':cfg.lambda_region,'weight':weight,
        'national_swing':national_swing,'region_swing':regional_swing,'state_swing':state_swing,
        'target_prediction':target,'observed_sp_share':.7 if n_sp else None,
        'projection':p.share_a,'baseline':a/valid,'observed_a':a,'observed_valid':valid,
        'remaining_valid':remaining,'remaining_a':p.votes_a-a,'projected_a':p.votes_a,'total_valid':30000,
        'fraction_sections':p.fraction_sections}
