"""
Pete avatar builder — PubCast AI v5.6
Pure Python (stdlib + numpy). No pygltflib class API required.
Valid GLB 2.0 / GLTF 2.0 output.
Rear View Foresight LLC 2026  |  Feic Mo Chroí™
"""
import json, struct, math, os
import numpy as np

# ── PALETTE ───────────────────────────────────────────────────────────────────
SKIN   = [0.785, 0.545, 0.365, 1.0]
HAIR   = [0.831, 0.408, 0.478, 1.0]
JACKET = [0.102, 0.102, 0.102, 1.0]
TANK   = [0.165, 0.165, 0.165, 1.0]
JEANS  = [0.357, 0.478, 0.557, 1.0]
BOOTS  = [0.067, 0.067, 0.067, 1.0]
EYE    = [0.243, 0.620, 0.604, 1.0]
BELT   = [0.118, 0.098, 0.082, 1.0]
ZIPPER = [0.706, 0.659, 0.498, 1.0]

MATS = {
    'skin':   {'base':SKIN,   'metal':0.0, 'rough':0.75,'emit':[0,0,0]},
    'hair':   {'base':HAIR,   'metal':0.0, 'rough':0.65,'emit':[0,0,0]},
    'jacket': {'base':JACKET, 'metal':0.0, 'rough':0.32,'emit':[0,0,0]},
    'jeans':  {'base':JEANS,  'metal':0.0, 'rough':0.88,'emit':[0,0,0]},
    'boots':  {'base':BOOTS,  'metal':0.05,'rough':0.58,'emit':[0,0,0]},
    'eye':    {'base':EYE,    'metal':0.0, 'rough':0.08,'emit':[0.06,0.18,0.18]},
    'belt':   {'base':BELT,   'metal':0.02,'rough':0.55,'emit':[0,0,0]},
    'holo':   {'base':[0.24,0.62,0.60,0.55],'metal':0.0,'rough':0.0,
               'emit':[0.24,0.62,0.60],'alpha':'BLEND'},
}
MNAMES = list(MATS.keys())
MIDX   = {n:i for i,n in enumerate(MNAMES)}

# ── PROPORTIONS (5'7" = 1.702 m) ──────────────────────────────────────────────
TH = 1.702
HEAD_H, NECK_H, TORSO_H = TH*0.130, TH*0.045, TH*0.290
PELVIS_H, THIGH_H, SHIN_H, FOOT_H = TH*0.095, TH*0.240, TH*0.220, TH*0.060
UPPER_ARM, LOWER_ARM, HAND = TH*0.175, TH*0.145, TH*0.100
HW, SW = 0.340, 0.385
foot_y=0; shin_y=foot_y+FOOT_H; thigh_y=shin_y+SHIN_H
pelvis_y=thigh_y+THIGH_H; spine_y=pelvis_y+PELVIS_H
neck_y=pelvis_y+PELVIS_H+TORSO_H; head_y=neck_y+NECK_H
shldr_y=spine_y+TORSO_H*0.72
hdx=HW*0.5; sdx=SW*0.5; ez=0.065; ex=0.030

# ── 89 BONES ──────────────────────────────────────────────────────────────────
BONES=[
  (0,"root",-1,[0,0,0]),
  (1,"pelvis",0,[0,pelvis_y,0]),
  (2,"spine_01",1,[0,PELVIS_H,0]),
  (3,"spine_02",2,[0,TORSO_H*.22,0]),
  (4,"spine_03",3,[0,TORSO_H*.22,0]),
  (5,"neck_01",4,[0,TORSO_H*.30,0]),
  (6,"head",5,[0,NECK_H,0]),
  (7,"jaw",6,[0,HEAD_H*.10,ez*.8]),
  (8,"eye_l",6,[ex,HEAD_H*.35,ez]),
  (9,"eye_r",6,[-ex,HEAD_H*.35,ez]),
  (10,"clavicle_l",4,[sdx*.35,TORSO_H*.28,0]),
  (11,"upperarm_l",10,[sdx*.65,0,0]),
  (12,"lowerarm_l",11,[UPPER_ARM,0,0]),
  (13,"hand_l",12,[LOWER_ARM,0,0]),
  (14,"thumb_01_l",13,[HAND*.10,-.010,.020]),
  (15,"thumb_02_l",14,[.025,0,0]),
  (16,"thumb_03_l",15,[.020,0,0]),
  (17,"index_metacarpal_l",13,[HAND*.45,-.005,.015]),
  (18,"index_01_l",17,[.030,0,0]),
  (19,"index_02_l",18,[.025,0,0]),
  (20,"index_03_l",19,[.018,0,0]),
  (21,"middle_metacarpal_l",13,[HAND*.45,-.005,.005]),
  (22,"middle_01_l",21,[.032,0,0]),
  (23,"middle_02_l",22,[.026,0,0]),
  (24,"middle_03_l",23,[.020,0,0]),
  (25,"ring_metacarpal_l",13,[HAND*.44,-.005,-.008]),
  (26,"ring_01_l",25,[.030,0,0]),
  (27,"ring_02_l",26,[.024,0,0]),
  (28,"ring_03_l",27,[.018,0,0]),
  (29,"pinky_metacarpal_l",13,[HAND*.42,-.006,-.020]),
  (30,"pinky_01_l",29,[.026,0,0]),
  (31,"pinky_02_l",30,[.020,0,0]),
  (32,"pinky_03_l",31,[.015,0,0]),
  (33,"clavicle_r",4,[-sdx*.35,TORSO_H*.28,0]),
  (34,"upperarm_r",33,[-sdx*.65,0,0]),
  (35,"lowerarm_r",34,[-UPPER_ARM,0,0]),
  (36,"hand_r",35,[-LOWER_ARM,0,0]),
  (37,"thumb_01_r",36,[-HAND*.10,-.010,-.020]),
  (38,"thumb_02_r",37,[-.025,0,0]),
  (39,"thumb_03_r",38,[-.020,0,0]),
  (40,"index_metacarpal_r",36,[-HAND*.45,-.005,-.015]),
  (41,"index_01_r",40,[-.030,0,0]),
  (42,"index_02_r",41,[-.025,0,0]),
  (43,"index_03_r",42,[-.018,0,0]),
  (44,"middle_metacarpal_r",36,[-HAND*.45,-.005,-.005]),
  (45,"middle_01_r",44,[-.032,0,0]),
  (46,"middle_02_r",45,[-.026,0,0]),
  (47,"middle_03_r",46,[-.020,0,0]),
  (48,"ring_metacarpal_r",36,[-HAND*.44,-.005,.008]),
  (49,"ring_01_r",48,[-.030,0,0]),
  (50,"ring_02_r",49,[-.024,0,0]),
  (51,"ring_03_r",50,[-.018,0,0]),
  (52,"pinky_metacarpal_r",36,[-HAND*.42,-.006,.020]),
  (53,"pinky_01_r",52,[-.026,0,0]),
  (54,"pinky_02_r",53,[-.020,0,0]),
  (55,"pinky_03_r",54,[-.015,0,0]),
  (56,"thigh_l",1,[hdx,0,0]),
  (57,"calf_l",56,[0,-THIGH_H,0]),
  (58,"foot_l",57,[0,-SHIN_H,0]),
  (59,"ball_l",58,[0,-FOOT_H*.35,FOOT_H*.55]),
  (60,"toe_l",59,[0,0,.04]),
  (61,"thigh_r",1,[-hdx,0,0]),
  (62,"calf_r",61,[0,-THIGH_H,0]),
  (63,"foot_r",62,[0,-SHIN_H,0]),
  (64,"ball_r",63,[0,-FOOT_H*.35,FOOT_H*.55]),
  (65,"toe_r",64,[0,0,.04]),
  (66,"ik_foot_l",0,[hdx,0,0]),
  (67,"ik_foot_r",0,[-hdx,0,0]),
  (68,"ik_hand_gun",0,[.35,shldr_y,.15]),
  (69,"ik_hand_l",13,[0,0,0]),
  (70,"ik_hand_r",36,[0,0,0]),
  (71,"breast_l",4,[.08,TORSO_H*.15,.06]),
  (72,"breast_r",4,[-.08,TORSO_H*.15,.06]),
  (73,"hair_top",6,[0,HEAD_H*.55,0]),
  (74,"hair_side_l",6,[.07,HEAD_H*.30,0]),
  (75,"hair_side_r",6,[-.07,HEAD_H*.30,0]),
  (76,"hair_back",6,[0,HEAD_H*.10,-.06]),
  (77,"hair_fringe",6,[0,HEAD_H*.55,.05]),
  (78,"collar_l",4,[.06,TORSO_H*.38,.04]),
  (79,"collar_r",4,[-.06,TORSO_H*.38,.04]),
  (80,"brow_l",6,[.035,HEAD_H*.48,ez*.85]),
  (81,"brow_r",6,[-.035,HEAD_H*.48,ez*.85]),
  (82,"cheek_l",6,[.055,HEAD_H*.22,ez*.75]),
  (83,"cheek_r",6,[-.055,HEAD_H*.22,ez*.75]),
  (84,"lip_upper",7,[0,.010,.015]),
  (85,"lip_lower",7,[0,-.010,.012]),
  (86,"lip_corner_l",7,[.025,0,.010]),
  (87,"lip_corner_r",7,[-.025,0,.010]),
  (88,"camera_bone",6,[0,HEAD_H*.40,.15]),
]
assert len(BONES)==89

# ── GEOMETRY HELPERS ──────────────────────────────────────────────────────────
def sphere(r,s=14):
    V,N,UV,I=[],[],[],[]
    for j in range(s+1):
        p=math.pi*j/s
        for i in range(s+1):
            t=2*math.pi*i/s
            x=math.sin(p)*math.cos(t)*r; y=math.cos(p)*r; z=math.sin(p)*math.sin(t)*r
            V.append([x,y,z]); N.append([x/r,y/r,z/r]); UV.append([i/s,j/s])
    for j in range(s):
        for i in range(s):
            a=j*(s+1)+i; I.extend([a,a+1,a+s+2,a,a+s+2,a+s+1])
    return np.array(V,np.float32),np.array(N,np.float32),np.array(UV,np.float32),np.array(I,np.uint16)

def cylinder(r,h,s=12):
    V,N,UV,I=[],[],[],[]
    hh=h/2
    for j in range(2):
        y=-hh+j*h
        for i in range(s+1):
            a=2*math.pi*i/s
            x=math.cos(a)*r; z=math.sin(a)*r
            V.append([x,y,z]); N.append([math.cos(a),0,math.sin(a)]); UV.append([i/s,j])
    for i in range(s):
        a=i; I.extend([a,a+1,a+s+2,a,a+s+2,a+s+1])
    # caps
    for sign,ny in [(-1,-hh),(1,hh)]:
        ci=len(V); V.append([0,ny,0]); N.append([0,sign,0]); UV.append([.5,.5])
        for i in range(s):
            a2=2*math.pi*i/s
            V.append([math.cos(a2)*r,ny,math.sin(a2)*r]); N.append([0,sign,0])
            UV.append([.5+.5*math.cos(a2),.5+.5*math.sin(a2)])
        for i in range(s):
            if sign>0: I.extend([ci,ci+1+i,ci+1+(i+1)%s])
            else:      I.extend([ci,ci+1+(i+1)%s,ci+1+i])
    return np.array(V,np.float32),np.array(N,np.float32),np.array(UV,np.float32),np.array(I,np.uint16)

def box(w,h,d):
    hw,hh,hd=w/2,h/2,d/2
    faces=[
        ([[-hw,-hh,hd],[hw,-hh,hd],[hw,hh,hd],[-hw,hh,hd]],[0,0,1]),
        ([[hw,-hh,-hd],[-hw,-hh,-hd],[-hw,hh,-hd],[hw,hh,-hd]],[0,0,-1]),
        ([[-hw,-hh,-hd],[-hw,-hh,hd],[-hw,hh,hd],[-hw,hh,-hd]],[-1,0,0]),
        ([[hw,-hh,hd],[hw,-hh,-hd],[hw,hh,-hd],[hw,hh,hd]],[1,0,0]),
        ([[-hw,hh,hd],[hw,hh,hd],[hw,hh,-hd],[-hw,hh,-hd]],[0,1,0]),
        ([[-hw,-hh,-hd],[hw,-hh,-hd],[hw,-hh,hd],[-hw,-hh,hd]],[0,-1,0]),
    ]
    uvc=[[0,0],[1,0],[1,1],[0,1]]
    V,N,UV,I=[],[],[],[]; base=0
    for pts,nrm in faces:
        for k,p in enumerate(pts): V.append(p); N.append(nrm); UV.append(uvc[k])
        I.extend([base,base+1,base+2,base,base+2,base+3]); base+=4
    return np.array(V,np.float32),np.array(N,np.float32),np.array(UV,np.float32),np.array(I,np.uint16)

def tx(v,px=0,py=0,pz=0,sx=1,sy=1,sz=1):
    v=v.copy(); v[:,0]=v[:,0]*sx+px; v[:,1]=v[:,1]*sy+py; v[:,2]=v[:,2]*sz+pz; return v

def merge(*gs):
    Vs,Ns,Us,Is,off=[],[],[],[],0
    for v,n,u,i in gs:
        Vs.append(v);Ns.append(n);Us.append(u);Is.append(i+off);off+=len(v)
    return np.concatenate(Vs),np.concatenate(Ns),np.concatenate(Us),np.concatenate(Is)

# ── PETE GEOMETRY ─────────────────────────────────────────────────────────────
def pete_parts():
    P=[]
    def add(geo,mat,bone): P.append((*geo,mat,bone))

    # HEAD
    v,n,u,i=sphere(HEAD_H*.47,16); v=tx(v,py=head_y+HEAD_H*.47,sx=1.06,sz=.90)
    add((v,n,u,i),'skin',6)
    # NECK
    v,n,u,i=cylinder(.044,NECK_H,10); v=tx(v,py=neck_y+NECK_H*.5)
    add((v,n,u,i),'skin',5)
    # TORSO (shaped)
    v,n,u,i=cylinder(.155,TORSO_H,16)
    yt=v[:,1]/(TORSO_H/2); wt=np.clip(1-.26*np.abs(yt),.74,1.)
    v[:,0]*=(1+.20*yt)*wt; v[:,2]*=wt*.88; v=tx(v,py=spine_y+TORSO_H*.5)
    add((v,n,u,i),'jacket',3)
    # PELVIS
    v,n,u,i=cylinder(.150,PELVIS_H,14); v=tx(v,py=pelvis_y+PELVIS_H*.5)
    add((v,n,u,i),'jeans',1)
    # THIGHS + SHINS
    for s,tb,sb in[(1,56,57),(-1,61,62)]:
        v,n,u,i=cylinder(.078,THIGH_H,12); v=tx(v,px=s*hdx,py=thigh_y-THIGH_H*.5)
        add((v,n,u,i),'jeans',tb)
        v,n,u,i=cylinder(.060,SHIN_H,10); v=tx(v,px=s*hdx,py=shin_y-SHIN_H*.5)
        add((v,n,u,i),'jeans',sb)
    # COMBAT BOOTS
    for s,bone in[(1,58),(-1,63)]:
        bv,bn,bu,bi=box(.098,FOOT_H*1.5,.230); bv=tx(bv,px=s*hdx,py=FOOT_H*.75,pz=.020)
        sv,sn,su,si=box(.106,FOOT_H*.18,.238); sv=tx(sv,px=s*hdx,py=FOOT_H*.09,pz=.020)
        add(merge((bv,bn,bu,bi),(sv,sn,su,si)),'boots',bone)
    # UPPER ARMS
    for s,bone in[(1,11),(-1,34)]:
        v,n,u,i=cylinder(.052,UPPER_ARM,10); v=tx(v,px=s*(sdx+UPPER_ARM*.5),py=shldr_y)
        add((v,n,u,i),'jacket',bone)
    # FOREARMS
    for s,bone in[(1,12),(-1,35)]:
        v,n,u,i=cylinder(.042,LOWER_ARM,10); v=tx(v,px=s*(sdx+UPPER_ARM+LOWER_ARM*.5),py=shldr_y)
        add((v,n,u,i),'skin',bone)
    # HANDS
    for s,bone in[(1,13),(-1,36)]:
        v,n,u,i=box(HAND*.88,.024,.080); v=tx(v,px=s*(sdx+UPPER_ARM+LOWER_ARM+HAND*.44),py=shldr_y)
        add((v,n,u,i),'skin',bone)
    # HAIR (pink bob)
    v,n,u,i=sphere(HEAD_H*.51,14); v=tx(v,py=head_y+HEAD_H*.53,sx=1.09,sz=.93)
    add((v,n,u,i),'hair',6)
    for s in[1,-1]:
        v,n,u,i=box(.036,HEAD_H*.48,.092); v=tx(v,px=s*.090,py=head_y+HEAD_H*.22)
        add((v,n,u,i),'hair',6)
    # EYES
    for s,bone in[(1,8),(-1,9)]:
        v,n,u,i=sphere(.013,8); v=tx(v,px=s*ex,py=head_y+HEAD_H*.35,pz=ez*1.12,sy=.78,sz=.58)
        add((v,n,u,i),'eye',bone)
    # BELT + BUCKLE
    bv,bn,bu,bi=box(.33,.032,.175); bv=tx(bv,py=pelvis_y+PELVIS_H*.72)
    kv,kn,ku,ki=box(.040,.036,.018); kv=tx(kv,py=pelvis_y+PELVIS_H*.72,pz=.090)
    add(merge((bv,bn,bu,bi),(kv,kn,ku,ki)),'belt',1)
    # LAPELS
    for s in[1,-1]:
        v,n,u,i=box(.042,TORSO_H*.30,.028); v=tx(v,px=s*.058,py=spine_y+TORSO_H*.68,pz=.105)
        add((v,n,u,i),'jacket',4)
    return P

# ── GLB PACKER ────────────────────────────────────────────────────────────────
class Bin:
    def __init__(self): self._d=[]; self._off=0; self.bv=[]; self.acc=[]
    def push(self,data,target=None):
        p=(-len(data))%4; self._d.append(data+b'\x00'*p)
        bv={'buffer':0,'byteOffset':self._off,'byteLength':len(data)}
        if target: bv['target']=target
        i=len(self.bv); self.bv.append(bv); self._off+=len(data)+p; return i
    def mk_acc(self,bv,ct,cnt,typ,mn=None,mx=None):
        a={'bufferView':bv,'componentType':ct,'count':cnt,'type':typ}
        if mn: a['min']=[float(x) for x in mn]
        if mx: a['max']=[float(x) for x in mx]
        i=len(self.acc); self.acc.append(a); return i
    def blob(self): return b''.join(self._d)

def build_glb(path):
    b=Bin(); nodes=[]; meshes=[]; mesh_ni=[]

    gmat=[]
    for nm in MNAMES:
        m=MATS[nm]
        gm={'name':nm,'pbrMetallicRoughness':{'baseColorFactor':m['base'],
            'metallicFactor':m['metal'],'roughnessFactor':m['rough']},
            'emissiveFactor':m['emit'],'doubleSided':False}
        if m.get('alpha')=='BLEND': gm['alphaMode']='BLEND'
        gmat.append(gm)

    parts=pete_parts()
    for pi,(v,n,u,idx,mat,bone) in enumerate(parts):
        nv=len(v); AB=34902; EB=34963
        pa=b.mk_acc(b.push(v.tobytes(),AB),5126,nv,'VEC3',v.min(0),v.max(0))
        na=b.mk_acc(b.push(n.tobytes(),AB),5126,nv,'VEC3')
        ua=b.mk_acc(b.push(u.tobytes(),AB),5126,nv,'VEC2')
        i16=idx.astype(np.uint16)
        ia=b.mk_acc(b.push(i16.tobytes(),EB),5123,len(idx),'SCALAR')
        J=np.full((nv,4),[bone,0,0,0],np.uint16)
        W=np.full((nv,4),[1.,0.,0.,0.],np.float32)
        ja=b.mk_acc(b.push(J.tobytes(),AB),5123,nv,'VEC4')
        wa=b.mk_acc(b.push(W.tobytes(),AB),5126,nv,'VEC4')
        prim={'attributes':{'POSITION':pa,'NORMAL':na,'TEXCOORD_0':ua,'JOINTS_0':ja,'WEIGHTS_0':wa},
              'indices':ia,'material':MIDX[mat],'mode':4}
        mi=len(meshes); meshes.append({'name':f'p{pi:02d}_{mat}','primitives':[prim]})
        ni=len(nodes); nodes.append({'name':f'm{pi:02d}','mesh':mi,'skin':0}); mesh_ni.append(ni)

    # skeleton
    bs=len(nodes)
    for _,name,_,lp in BONES:
        nodes.append({'name':name,'translation':[float(x) for x in lp],
                      'rotation':[0.,0.,0.,1.],'scale':[1.,1.,1.]})
    for idx_b,_,par,_ in BONES:
        if par>=0: nodes[bs+par].setdefault('children',[]).append(bs+idx_b)

    ibm=np.tile(np.eye(4,dtype=np.float32).flatten(),len(BONES)).tobytes()
    ibm_bv=b.push(ibm); ibm_acc=b.mk_acc(ibm_bv,5126,len(BONES),'MAT4')
    skin={'name':'pete_rig_89','joints':list(range(bs,bs+len(BONES))),
          'inverseBindMatrices':ibm_acc,'skeleton':bs}

    arm_i=len(nodes)
    nodes.append({'name':'pete_armature','children':mesh_ni+[bs]})

    blob=b.blob()
    gltf={'asset':{'version':'2.0',
                   'generator':'Rear View Foresight PubCast AI v5.6',
                   'copyright':'2026 Rear View Foresight LLC  Feic Mo Chroi'},
          'scene':0,'scenes':[{'name':'Pete','nodes':[arm_i]}],
          'nodes':nodes,'meshes':meshes,'materials':gmat,'skins':[skin],
          'buffers':[{'byteLength':len(blob)}],
          'bufferViews':b.bv,'accessors':b.acc,
          'extras':{'character':'Pete','height_m':TH,'height':'5\'7"',
                    'rig':'UE5-89-bone','parallax_depth':0.45,
                    'holo_mat_idx':MIDX['holo'],
                    'pubcast':'5.6',
                    'quote':'A world of stories is waiting... I just need to capture them.'}}

    jb=json.dumps(gltf,separators=(',',':')).encode(); jb+=b' '*((-len(jb))%4)
    total=12+8+len(jb)+8+len(blob)
    glb=(struct.pack('<III',0x46546C67,2,total)+
         struct.pack('<II',len(jb),0x4E4F534A)+jb+
         struct.pack('<II',len(blob),0x004E4942)+blob)
    with open(path,'wb') as f: f.write(glb)
    return len(glb),len(meshes)

if __name__=='__main__':
    out='/mnt/user-data/outputs/pete_avatar_pubcast_v56.glb'
    os.makedirs(os.path.dirname(out),exist_ok=True)
    print("Building Pete GLB...")
    sz,mc=build_glb(out)
    print(f"  Bones: {len(BONES)}")
    print(f"  Mesh parts: {mc}")
    print(f"  Size: {sz/1024:.1f} KB")
    print(f"  Output: {out}")
    print("Done.")
