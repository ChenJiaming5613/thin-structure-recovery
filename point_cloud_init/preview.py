"""Preview supplementary thin-structure points.

Writes into <scene>/thin_init/preview/:
  * reproj_<frame>.png  : thin points (red) and original COLMAP points (dim blue) projected onto frames
  * preview.html        : standalone interactive 3D viewer (no dependencies, open in any browser)

Example:
  python tools/thin_init/preview.py -s dataset/tandt/truck --frames 5,11,18 --crop 450 0 760 140
"""
import argparse
import base64
import json
import os

import numpy as np
from PIL import Image, ImageDraw

import common


def occlusion_zbuffer(K, W, H, v, xyz, radius=4):
    """Approximate per-pixel visible depth from the COLMAP cloud (min depth, dilated)."""
    u, w, z = common.project(K, v.R, v.t, xyz)
    ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
    zb = np.full((H, W), np.inf, np.float32)
    np.minimum.at(zb, (w[ok].astype(int), u[ok].astype(int)), z[ok].astype(np.float32))
    from scipy import ndimage as ndi
    zb = ndi.grey_erosion(zb, size=(2 * radius + 1, 2 * radius + 1))
    return zb


def reproj_image(scene, v, thin, orig, crop, dot=2, occ_ratio=0.97):
    K, W, H = scene["K"], scene["W"], scene["H"]
    im = Image.open(os.path.join(scene["img_dir"], v.name)).convert("RGB")
    base = np.asarray(im).astype(np.float32)
    dimmed = Image.fromarray((base * 0.55).astype(np.uint8))
    zb = occlusion_zbuffer(K, W, H, v, orig)
    u, w, z = common.project(K, v.R, v.t, thin)
    ok = (z > 1e-3) & (u >= 0) & (u < W) & (w >= 0) & (w < H)
    ui, wi = np.clip(u.astype(int), 0, W - 1), np.clip(w.astype(int), 0, H - 1)
    occluded = ok & (z > zb[wi, ui] / occ_ratio)
    visible = ok & ~occluded
    panels = []
    for layer in ("orig", "thin", "both"):
        canvas = dimmed.copy()
        dr = ImageDraw.Draw(canvas)
        if layer in ("orig", "both"):
            uo, wo, zo = common.project(K, v.R, v.t, orig)
            oko = (zo > 1e-3) & (uo >= 0) & (uo < W) & (wo >= 0) & (wo < H)
            for a, b in zip(uo[oko], wo[oko]):
                dr.point((a, b), fill=(80, 160, 255))
        if layer in ("thin", "both"):
            if layer == "thin":  # occluded thin points in a dim colour, only in the thin-only panel
                for a, b in zip(u[occluded], w[occluded]):
                    dr.point((a, b), fill=(150, 70, 150))
            for a, b in zip(u[visible], w[visible]):
                dr.rectangle((a - dot / 2, b - dot / 2, a + dot / 2, b + dot / 2), fill=(255, 40, 40))
        panels.append(canvas)
    if crop:
        x0, y0, x1, y1 = crop
        sc = max(1, 1300 // (x1 - x0))
        src = [im] + panels
        tiles = [p.crop((x0, y0, x1, y1)).resize(((x1 - x0) * sc, (y1 - y0) * sc), Image.NEAREST) for p in src]
        out = Image.new("RGB", (tiles[0].width, sum(t.height for t in tiles)))
        y = 0
        for t in tiles:
            out.paste(t, (0, y))
            y += t.height
        return out
    out = Image.new("RGB", (W * 2, H * 2))
    for k, p in enumerate([im] + panels):
        out.paste(p, ((k % 2) * W, (k // 2) * H))
    return out


HTML = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>thin_init preview</title>
<style>
 html,body{margin:0;height:100%;overflow:hidden;background:#111;font:13px/1.4 system-ui,sans-serif;color:#ddd}
 canvas{display:block;width:100%;height:100%}
 #ui{position:absolute;top:10px;left:10px;background:rgba(20,20,24,.86);padding:10px 12px;border-radius:8px;min-width:250px}
 #ui label{display:block;margin:4px 0} #ui input[type=range]{width:140px;vertical-align:middle}
 #ui button{margin:6px 4px 0 0;background:#333;color:#eee;border:1px solid #555;border-radius:4px;padding:3px 8px;cursor:pointer}
 .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}
 #help{color:#999;margin-top:6px;font-size:12px}
</style></head><body>
<canvas id="c"></canvas>
<div id="ui">
 <b>补充初始点预览</b><div id="stat"></div>
 <label><input type="checkbox" id="showThin" checked><span class="sw" style="background:#ff3030"></span>补充点 (thin)</label>
 <label><input type="checkbox" id="showNear"><span class="sw" style="background:#ffb000"></span>补充但靠近原有点 (被过滤)</label>
 <label><input type="checkbox" id="showOrig" checked><span class="sw" style="background:#888"></span>原始 COLMAP 点</label>
 <label><input type="checkbox" id="origRGB">原始点用真实颜色</label>
 <label><input type="checkbox" id="showCam" checked><span class="sw" style="background:#3af"></span>相机位置</label>
 <label>补充点大小 <input type="range" id="sThin" min="1" max="12" value="4"></label>
 <label>原始点大小 <input type="range" id="sOrig" min="1" max="8" value="1"></label>
 <label>原始点透明度 <input type="range" id="aOrig" min="5" max="100" value="45"></label>
 <button id="focus">聚焦补充点</button><button id="reset">重置视角</button>
 <div id="help">左键旋转 · 右键/Shift+左键平移 · 滚轮缩放</div>
</div>
<script>
const DATA = __DATA__;
function dec(b64, T){const s=atob(b64);const u=new Uint8Array(s.length);for(let i=0;i<s.length;i++)u[i]=s.charCodeAt(i);return new T(u.buffer);}
const L = {};
for (const k of ["orig","thin","near","cam"]) {
  const d = DATA[k]; L[k] = {n:d.n, pos:dec(d.pos, Float32Array), col:d.col?dec(d.col, Uint8Array):null};
}
document.getElementById("stat").innerHTML =
  `补充点 <b style="color:#ff6060">${L.thin.n}</b> · 被过滤 ${L.near.n} · 原始 ${DATA.orig_total}${DATA.orig_total>L.orig.n?` (显示 ${L.orig.n})`:""}`;

const cv=document.getElementById("c"); const gl=cv.getContext("webgl",{antialias:true});
const vs=`attribute vec3 p;attribute vec3 c;uniform mat4 M;uniform float S;uniform vec3 U;uniform float useC;varying vec3 vc;
void main(){gl_Position=M*vec4(p,1.0);gl_PointSize=S;vc=mix(U,c/255.0,useC);}`;
const fs=`precision mediump float;varying vec3 vc;uniform float A;uniform float round;
void main(){vec2 q=gl_PointCoord-0.5;if(round>0.5&&dot(q,q)>0.25)discard;gl_FragColor=vec4(vc,A);}`;
function sh(t,s){const o=gl.createShader(t);gl.shaderSource(o,s);gl.compileShader(o);if(!gl.getShaderParameter(o,gl.COMPILE_STATUS))throw gl.getShaderInfoLog(o);return o;}
const pr=gl.createProgram();gl.attachShader(pr,sh(gl.VERTEX_SHADER,vs));gl.attachShader(pr,sh(gl.FRAGMENT_SHADER,fs));gl.linkProgram(pr);gl.useProgram(pr);
const loc={p:gl.getAttribLocation(pr,"p"),c:gl.getAttribLocation(pr,"c"),M:gl.getUniformLocation(pr,"M"),S:gl.getUniformLocation(pr,"S"),
 U:gl.getUniformLocation(pr,"U"),useC:gl.getUniformLocation(pr,"useC"),A:gl.getUniformLocation(pr,"A"),round:gl.getUniformLocation(pr,"round")};
for (const k in L){const o=L[k];o.pb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,o.pb);gl.bufferData(gl.ARRAY_BUFFER,o.pos,gl.STATIC_DRAW);
 if(o.col){o.cb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,o.cb);gl.bufferData(gl.ARRAY_BUFFER,o.col,gl.STATIC_DRAW);}}

// ---- camera (orbit around target, scene up = DATA.up)
const V=(x,y,z)=>[x,y,z], add=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]], sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]],
 mul=(a,s)=>[a[0]*s,a[1]*s,a[2]*s], dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2],
 cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]], nrm=a=>mul(a,1/Math.hypot(...a));
const up=nrm(DATA.up); let ref=nrm(cross(up, Math.abs(up[0])<0.9?V(1,0,0):V(0,1,0))); const ref2=cross(up,ref);
let cam={};
function resetCam(){cam={t:DATA.center.slice(),d:DATA.radius*2.2,yaw:0.6,pitch:0.45};}
function focusThin(){ if(!L.thin.n) return; cam.t=DATA.thin_center.slice(); cam.d=Math.max(DATA.thin_radius*2.5,DATA.radius*0.15);}
resetCam();
function eye(){const cp=Math.cos(cam.pitch),sp=Math.sin(cam.pitch);
 const dir=add(add(mul(ref,cp*Math.cos(cam.yaw)),mul(ref2,cp*Math.sin(cam.yaw))),mul(up,sp));return add(cam.t,mul(dir,cam.d));}
function matMul(a,b){const r=new Float32Array(16);for(let i=0;i<4;i++)for(let j=0;j<4;j++){let s=0;for(let k=0;k<4;k++)s+=a[k*4+j]*b[i*4+k];r[i*4+j]=s;}return r;}
function lookAt(e,t,u){const z=nrm(sub(e,t)),x=nrm(cross(u,z)),y=cross(z,x);
 return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,e),-dot(y,e),-dot(z,e),1]);}
function persp(f,a,n,fa){const t=1/Math.tan(f/2);return new Float32Array([t/a,0,0,0,0,t,0,0,0,0,(fa+n)/(n-fa),-1,0,0,2*fa*n/(n-fa),0]);}

const $=id=>document.getElementById(id);
function draw(){
 const w=cv.clientWidth*devicePixelRatio,h=cv.clientHeight*devicePixelRatio; if(cv.width!==w||cv.height!==h){cv.width=w;cv.height=h;}
 gl.viewport(0,0,w,h);gl.clearColor(0.07,0.07,0.08,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
 gl.enable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
 const M=matMul(persp(0.9,w/h,cam.d*0.002,cam.d*50),lookAt(eye(),cam.t,up));gl.uniformMatrix4fv(loc.M,false,M);
 const dpr=devicePixelRatio;
 function layer(o,size,color,alpha,useCol,round,depthWrite){ if(!o.n)return;
  gl.depthMask(depthWrite);
  gl.bindBuffer(gl.ARRAY_BUFFER,o.pb);gl.enableVertexAttribArray(loc.p);gl.vertexAttribPointer(loc.p,3,gl.FLOAT,false,0,0);
  if(o.cb&&useCol){gl.bindBuffer(gl.ARRAY_BUFFER,o.cb);gl.enableVertexAttribArray(loc.c);gl.vertexAttribPointer(loc.c,3,gl.UNSIGNED_BYTE,false,0,0);}
  else{gl.disableVertexAttribArray(loc.c);gl.vertexAttrib3f(loc.c,0,0,0);}
  gl.uniform1f(loc.S,size*dpr);gl.uniform3fv(loc.U,color);gl.uniform1f(loc.useC,useCol&&o.cb?1:0);gl.uniform1f(loc.A,alpha);gl.uniform1f(loc.round,round?1:0);
  gl.drawArrays(gl.POINTS,0,o.n);}
 if($("showOrig").checked) layer(L.orig,+$("sOrig").value,[0.55,0.55,0.58],$("aOrig").value/100,$("origRGB").checked,false,false);
 if($("showCam").checked) layer(L.cam,5,[0.2,0.65,1.0],1,false,true,true);
 if($("showNear").checked) layer(L.near,+$("sThin").value,[1.0,0.7,0.0],1,false,true,true);
 if($("showThin").checked) layer(L.thin,+$("sThin").value,[1.0,0.19,0.19],1,false,true,true);
 requestAnimationFrame(draw);}
requestAnimationFrame(draw);

let drag=null;
cv.addEventListener("contextmenu",e=>e.preventDefault());
cv.addEventListener("mousedown",e=>{drag={x:e.clientX,y:e.clientY,pan:e.button===2||e.shiftKey};});
window.addEventListener("mouseup",()=>drag=null);
window.addEventListener("mousemove",e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;
 if(drag.pan){const e3=eye(),z=nrm(sub(e3,cam.t)),x=nrm(cross(up,z)),y=cross(z,x),s=cam.d*0.0015;
  cam.t=add(cam.t,add(mul(x,-dx*s),mul(y,dy*s)));}
 else{cam.yaw-=dx*0.006;cam.pitch=Math.max(-1.55,Math.min(1.55,cam.pitch+dy*0.006));}});
cv.addEventListener("wheel",e=>{e.preventDefault();cam.d*=Math.exp(e.deltaY*0.0012);},{passive:false});
$("focus").onclick=focusThin;$("reset").onclick=resetCam;
</script></body></html>
"""


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def write_html(path, scene, thin, near, max_orig):
    orig, orig_rgb = scene["xyz"], scene["rgb"]
    # drop extreme outliers for the view bounds
    C = np.stack([v.C for v in scene["views"]])
    center = np.median(C, 0)
    radius = float(np.percentile(np.linalg.norm(C - center, axis=1), 90))
    if len(orig) > max_orig:
        sel = np.random.default_rng(0).choice(len(orig), max_orig, replace=False)
        orig_s, rgb_s = orig[sel], orig_rgb[sel]
    else:
        orig_s, rgb_s = orig, orig_rgb
    up = np.mean([v.up for v in scene["views"]], 0)
    thin_c = np.median(thin, 0) if len(thin) else center
    thin_r = float(np.percentile(np.linalg.norm(thin - thin_c, axis=1), 90)) if len(thin) else radius
    data = dict(
        orig=dict(n=len(orig_s), pos=b64(orig_s.astype(np.float32)), col=b64(rgb_s.astype(np.uint8))),
        thin=dict(n=len(thin), pos=b64(thin.astype(np.float32))),
        near=dict(n=len(near), pos=b64(near.astype(np.float32))),
        cam=dict(n=len(C), pos=b64(C.astype(np.float32))),
        orig_total=len(orig), center=center.tolist(), radius=radius, up=up.tolist(),
        thin_center=thin_c.tolist(), thin_radius=thin_r,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(HTML.replace("__DATA__", json.dumps(data)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--scene", required=True)
    ap.add_argument("--images", default="images")
    ap.add_argument("--thin_dir", default=None, help="default: <scene>/thin_init")
    ap.add_argument("--frames", default="11", help="frames to reproject onto (1-based)")
    ap.add_argument("--crop", type=int, nargs=4, default=None)
    ap.add_argument("--max_orig", type=int, default=300000)
    args = ap.parse_args()

    d = args.thin_dir or os.path.join(args.scene, "thin_init")
    out = os.path.join(d, "preview")
    os.makedirs(out, exist_ok=True)
    scene = common.load_scene(args.scene, args.images)
    a = common.read_ply(os.path.join(d, "thin_points.ply"))
    thin = np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)
    pn = os.path.join(d, "thin_points_near_existing.ply")
    if os.path.exists(pn):
        b = common.read_ply(pn)
        near = np.stack([b["x"], b["y"], b["z"]], 1).astype(np.float64)
    else:
        near = np.zeros((0, 3))
    print(f"thin points: {len(thin)}, near-existing (filtered): {len(near)}")

    for i in common.parse_frames(args.frames, len(scene["views"])):
        v = scene["views"][i]
        img = reproj_image(scene, v, thin, scene["xyz"], args.crop)
        p = os.path.join(out, f"reproj_{os.path.splitext(v.name)[0]}.png")
        img.save(p)
        print("wrote", p)
    write_html(os.path.join(out, "preview.html"), scene, thin, near, args.max_orig)
    print("wrote", os.path.join(out, "preview.html"))

    # colour-coded cloud for external viewers (CloudCompare / MeshLab):
    # original COLMAP = grey, supplementary = red; scalar field 'is_thin' (0/1) for filtering
    xyz = np.concatenate([scene["xyz"], thin], 0)
    rgb = np.concatenate([np.full((len(scene["xyz"]), 3), 150, np.uint8),
                          np.tile(np.array([[255, 30, 30]], np.uint8), (len(thin), 1))], 0)
    flag = np.concatenate([np.zeros(len(scene["xyz"]), np.uint8), np.ones(len(thin), np.uint8)])
    p = os.path.join(out, "compare_colored.ply")
    common.write_ply(p, xyz, rgb, extra=dict(is_thin=flag))
    print("wrote", p)


if __name__ == "__main__":
    main()
