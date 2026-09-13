import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { Sky } from "three/addons/objects/Sky.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

const $ = s => document.querySelector(s);
const scene = new THREE.Scene();
scene.background = new THREE.Color("#c6e3f7");
scene.fog = new THREE.Fog("#d4e7ef", 180, 380);
const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, .1, 600);
const renderer = new THREE.WebGLRenderer({antialias:true, powerPreference:"high-performance"});
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.shadowMap.autoUpdate = false;
renderer.shadowMap.needsUpdate = true;
renderer.localClippingEnabled = true;
$("#viewport").appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = .08;
controls.minDistance = .6;
controls.maxDistance = 230;
controls.maxPolarAngle = Math.PI * .49;
const sky = new Sky();
sky.scale.setScalar(450);
sky.material.uniforms.turbidity.value = 3.2;
sky.material.uniforms.rayleigh.value = 1.5;
sky.material.uniforms.mieCoefficient.value = .004;
const sunDirection = new THREE.Vector3(-.7, .95, .6).normalize();
sky.material.uniforms.sunPosition.value.copy(sunDirection);
scene.add(sky);
// One calibrated light rig. Blender's exported watt-to-lux light conversion is
// deliberately not used here: it was washing out the dark reference façades.
const hemi = new THREE.HemisphereLight(0xe3f1ff, 0x85856b, 2.0);
const sun = new THREE.DirectionalLight(0xffefd7, 3.0);
sun.position.copy(sunDirection).multiplyScalar(90);
sun.target.position.set(0,0,-15);
sun.castShadow = true;
Object.assign(sun.shadow.camera, {left:-55,right:55,top:65,bottom:-65,near:.5,far:220});
sun.shadow.bias = -.00008;
sun.shadow.normalBias = .025;
scene.add(hemi, sun, sun.target);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(sky, .04, .1, 500).texture;
pmrem.dispose();
// Camera-visible sky is exposure-independent; environment lighting is separate.
sky.material.dispose();
sky.material=new THREE.ShaderMaterial({
  side:THREE.BackSide,depthWrite:false,
  vertexShader:`varying vec3 direction;void main(){vec4 p=modelMatrix*vec4(position,1.);direction=p.xyz-cameraPosition;gl_Position=projectionMatrix*viewMatrix*p;}`,
  fragmentShader:`varying vec3 direction;
  float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}
  void main(){vec3 d=normalize(direction);float h=max(d.y,0.);vec3 col=mix(vec3(.76,.88,.95),vec3(.23,.52,.82),pow(h,.45));vec2 uv=d.xz/(max(d.y,.08)+.15)*2.;float n=noise(uv)*.57+noise(uv*2.1)*.28+noise(uv*4.3)*.15;float cloud=smoothstep(.57,.8,n)*smoothstep(.01,.22,h)*.7;col=mix(col,vec3(.96,.97,.99),cloud);gl_FragColor=vec4(col,1.);}`,
  toneMapped:false
});

const state = {
  mode:"exterior", building:"A", floor:3, unit:null, explosion:0, section:.75,
  sectionAxis:"z", isolateFloor:false, context:false, auto:false, walking:false,
  model:null, base:new Map(), selected:null, isolated:null, sectionCaps:null,
  quality:innerWidth<700?"balanced":"ultra", keys:new Set(), yaw:0, pitch:0
};
const meshList = [], sectionSources = [];
const batches=[];
function buildBatches(){
  // Logical GLB objects remain intact for metadata, clipping, caps and picking.
  // GPU batches are a render-only projection of those same world transforms.
  if(!renderer.extensions.has("WEBGL_multi_draw"))return;
  const groups=new Map();
  for(const n of meshList){
    if(Array.isArray(n.material)||role(n)==="collision"||n.matrixWorld.determinant()<0)continue;
    const key=n.material.uuid+":"+n.castShadow+":"+Object.keys(n.geometry.attributes).sort().join(",")+":"+!!n.geometry.index;
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(n);
  }
  for(const nodes of groups.values()){
    if(nodes.length<3)continue;
    const geometries=[...new Set(nodes.map(n=>n.geometry))];
    const vertices=geometries.reduce((s,g)=>s+g.attributes.position.count,0);
    const indices=geometries.reduce((s,g)=>s+(g.index?.count||0),0);
    const batch=new THREE.BatchedMesh(nodes.length,vertices,indices||vertices*2,nodes[0].material);
    batch.name="RenderBatch_"+nodes[0].material.name;
    batch.castShadow=nodes[0].castShadow;batch.receiveShadow=true;batch.frustumCulled=false;
    const ids=new Map(geometries.map(g=>[g,batch.addGeometry(g)]));
    const instances=nodes.map(n=>{
      n.layers.set(1);
      return {node:n,id:batch.addInstance(ids.get(n.geometry))};
    });
    scene.add(batch);batches.push({batch,instances});
  }
  syncBatches();
}
function syncBatches(){
  state.model?.updateMatrixWorld(true);
  for(const {batch,instances} of batches)for(const {node,id} of instances){
    batch.setMatrixAt(id,node.matrixWorld);
    batch.setVisibleAt(id,visible(node));
  }
}
const outline = new THREE.Box3Helper(new THREE.Box3(), 0x002d96);
outline.visible = false;
outline.material.depthTest = false;
outline.material.transparent = true;
outline.material.opacity = .9;
outline.renderOrder = 20;
scene.add(outline);
const selectionMarker = new THREE.Group();
selectionMarker.name = "INTERMEDIA_SELECTED_ELEMENT";
selectionMarker.visible = false;
selectionMarker.renderOrder = 21;
scene.add(selectionMarker);
const guides = new THREE.Group();
scene.add(guides);
function semantic(node,key) {
  for(let p=node;p;p=p.parent) if(p.userData[key]!==undefined) return p.userData[key];
  return null;
}
const role = n => semantic(n,"role");
const building = n => semantic(n,"building_id");
const level = n => semantic(n,"floor_index");
const ownRole = n => n.userData.role;
function collect(predicate) {
  const found=[]; state.model?.traverse(n=>{if(predicate(n))found.push(n);}); return found;
}
function visible(n) {
  for(let p=n;p;p=p.parent) if(!p.visible)return false;
  return true;
}
const materials = n => Array.isArray(n.material)?n.material:[n.material];
const buildingRoot = () => collect(n=>ownRole(n)==="building"&&building(n)===state.building)[0];
const unitRoot = () => collect(n=>ownRole(n)==="detailed_apartment"&&semantic(n,"unit_kind")===state.unit)[0];
const structural = n => /wall|partition|slab|ceiling|plinth|foundation/.test(role(n)||"");
function disposeGroup(group) {
  if(!group)return;
  group.traverse(n=>{n.geometry?.dispose();if(n.material)materials(n).forEach(m=>m.dispose());});
  group.removeFromParent();
}
function clearSelection() {
  state.selected=null; outline.visible=false; selectionMarker.visible=false; $("#inspector").hidden=true;
  if(typeof refreshCatalogue === "function")refreshCatalogue(true);
}
function updateSelectionMarker(n=state.selected) {
  while(selectionMarker.children.length){const child=selectionMarker.children[0];selectionMarker.remove(child);child.geometry?.dispose();child.material?.dispose();}
  if(!n||!visible(n)){selectionMarker.visible=false;return;}
  const box=new THREE.Box3().setFromObject(n),size=box.getSize(new THREE.Vector3());
  const volumeSize=new THREE.Vector3(Math.max(size.x,.18),Math.max(size.y,.18),Math.max(size.z,.18));
  const volume=new THREE.Mesh(new THREE.BoxGeometry(...volumeSize.toArray()),new THREE.MeshBasicMaterial({color:0xffc857,transparent:true,opacity:.13,depthTest:false,depthWrite:false}));
  volume.position.copy(box.getCenter(new THREE.Vector3()));volume.frustumCulled=false;volume.renderOrder=21;selectionMarker.add(volume);
  const length=Math.max(.16,Math.min(.38,Math.min(size.x,size.y,size.z)*.24));
  const corners=[];
  for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z])corners.push(new THREE.Vector3(x,y,z));
  const points=[];
  for(const corner of corners)for(const axis of ["x","y","z"]){const end=corner.clone();end[axis]+=corner[axis]===box.min[axis]?length:-length;points.push(corner,end);}
  const line=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:0x91652e,transparent:true,opacity:1,depthTest:false,depthWrite:false}));
  line.frustumCulled=false;line.renderOrder=22;selectionMarker.add(line);selectionMarker.visible=true;
}
function restore() {
  guides.visible=true;
  disposeGroup(state.sectionCaps); state.sectionCaps=null;
  while(guides.children.length)disposeGroup(guides.children[0]);
  state.base.forEach((base,n)=>{
    n.position.copy(base.position); n.quaternion.copy(base.quaternion); n.visible=base.visible;
  });
  for(const n of meshList) for(const m of materials(n))m.clippingPlanes=[];
  clearSelection();
}
function boundsOf(predicate) {
  const bounds=new THREE.Box3();
  state.model?.updateMatrixWorld(true);
  for(const n of meshList) if(visible(n)&&predicate(n)) {
    n.geometry.computeBoundingBox();
    bounds.union(n.geometry.boundingBox.clone().applyMatrix4(n.matrixWorld));
  }
  return bounds;
}
function resize() {
  renderer.setSize(innerWidth,innerHeight);
  camera.aspect=innerWidth/innerHeight;
  const left=innerWidth>900?280:innerWidth>560?240:0;
  // Optical centre is the free canvas, not the area behind the project panel.
  camera.setViewOffset(innerWidth,innerHeight,-left/2,42,innerWidth,innerHeight);
  camera.updateProjectionMatrix();
}
function frameBounds(bounds, direction=new THREE.Vector3(1,.78,1.25)) {
  if(bounds.isEmpty())return;
  const center=bounds.getCenter(new THREE.Vector3());
  const d=direction.clone().normalize();
  const right=new THREE.Vector3().crossVectors(camera.up,d).normalize();
  const up=new THREE.Vector3().crossVectors(d,right);
  const tanV=Math.tan(THREE.MathUtils.degToRad(camera.fov/2));
  const usableHeight=Math.max(230,innerHeight-(innerWidth<560?380:250));
  const usableWidth=Math.max(230,innerWidth-(innerWidth>560?340:35));
  let distance=2;
  for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z]){
    const p=new THREE.Vector3(x,y,z).sub(center);
    distance=Math.max(distance,p.dot(d)+Math.abs(p.dot(up))/(tanV*usableHeight/innerHeight),
      p.dot(d)+Math.abs(p.dot(right))/(tanV*camera.aspect*usableWidth/innerWidth));
  }
  camera.position.copy(center).addScaledVector(d,distance*1.08);
  controls.target.copy(center); controls.update();
}
function frameScene() {
  let b=boundsOf(n=>building(n)!==null||/parking|vehicle/.test(role(n)||""));
  if(state.mode!=="exterior"||state.explosion>0)b=boundsOf(n=>building(n)===state.building);
  if(state.mode==="apartment")b=boundsOf(n=>belongs(n,unitRoot()));
  if(state.explosion>0){
    // Reserve room for 100% before dragging, so the camera stays still during input.
    b.max.y+=18*(1-state.explosion);
    b.expandByVector(new THREE.Vector3(4*(1-state.explosion),0,4*(1-state.explosion)));
  }
  const direction=state.mode==="cutaway"
    ?(state.sectionAxis==="x"?new THREE.Vector3(1.7,.3,.45):new THREE.Vector3(.3,.32,1.7))
    :state.mode==="floors"||state.mode==="apartment"?new THREE.Vector3(.45,1.6,1):new THREE.Vector3(1,.8,1.35);
  frameBounds(b,direction);
}
function belongs(n,root) { for(let p=n;p;p=p.parent)if(p===root)return true;return false; }
function focusBuilding() {
  for(const n of collect(n=>ownRole(n)==="building"))n.visible=building(n)===state.building||state.context;
  // A focused inspection should not have foreground trees hiding the sections.
  for(const n of collect(n=>ownRole(n)==="site"))n.visible=state.context;
}
function moveWorld(n,offset) {
  const base=state.base.get(n);
  const q=n.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
  n.position.copy(base.position).add(offset.clone().applyQuaternion(q));
}
function explode() {
  focusBuilding();
  for(const n of collect(n=>building(n)===state.building)) {
    const r=ownRole(n), f=Number(level(n)||0), t=state.explosion;
    if(r==="floor")moveWorld(n,new THREE.Vector3(0,f*4.8*t,0));
    if(r==="roof")moveWorld(n,new THREE.Vector3(0,19.2*t,0));
    if(r==="facade") {
      const dir={front:[0,0,1],back:[0,0,-1],left:[-1,0,0],right:[1,0,0]}[semantic(n,"facade_side")];
      if(dir)moveWorld(n,new THREE.Vector3(...dir).multiplyScalar(4.6*t));
    }
    if(r==="balcony")moveWorld(n,new THREE.Vector3(0,0,4.6*t));
    if(r==="ceiling"&&t>0)moveWorld(n,new THREE.Vector3(0,2.4*t,0));
  }
  state.model.updateMatrixWorld(true);
  if(state.explosion>0) for(const f of collect(n=>ownRole(n)==="floor"&&building(n)===state.building)) {
    const end=f.getWorldPosition(new THREE.Vector3());
    const start=end.clone();start.y-=Number(level(f)||0)*4.8*state.explosion;
    for(const x of [-14,14]){
      const a=start.clone().add(new THREE.Vector3(x,0,0)),b=end.clone().add(new THREE.Vector3(x,0,0));
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([a,b]),new THREE.LineDashedMaterial({color:0x91652e,dashSize:.22,gapSize:.18,transparent:true,opacity:.55}));
      line.computeLineDistances();guides.add(line);
    }
  }
}
// Convex cross-sections are generated from actual triangle/plane intersections
// for each structural solid. There is never a building-sized masking rectangle.
function convexHull(points) {
  const sorted=points.sort((a,b)=>a.x-b.x||a.y-b.y).filter((p,i,a)=>i===0||p.distanceToSquared(a[i-1])>1e-9);
  if(sorted.length<3)return [];
  const cross=(o,a,b)=>(a.x-o.x)*(b.y-o.y)-(a.y-o.y)*(b.x-o.x);
  const lower=[],upper=[];
  for(const p of sorted){while(lower.length>1&&cross(lower.at(-2),lower.at(-1),p)<=1e-9)lower.pop();lower.push(p);}
  for(const p of sorted.toReversed()){while(upper.length>1&&cross(upper.at(-2),upper.at(-1),p)<=1e-9)upper.pop();upper.push(p);}
  lower.pop();upper.pop();return lower.concat(upper);
}
const clipPlane=new THREE.Plane();
function section() {
  focusBuilding();
  const b=boundsOf(n=>building(n)===state.building),axis=state.sectionAxis;
  const cut=THREE.MathUtils.lerp(b.min[axis],b.max[axis],state.section);
  clipPlane.set(axis==="x"?new THREE.Vector3(-1,0,0):new THREE.Vector3(0,0,-1),cut);
  for(const n of meshList)if(building(n)===state.building)
    for(const m of materials(n)){m.clippingPlanes=[clipPlane];m.clipShadows=true;}
  const caps=new THREE.Group(); caps.name="STRUCTURAL_SECTION_CAPS";
  const capMat=new THREE.MeshStandardMaterial({color:0xb89872,roughness:1,side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-1,polygonOffsetUnits:-2});
  for(const source of sectionSources) {
    if(building(source.node)!==state.building||!visible(source.node))continue;
    if(cut<=source.bounds.min[axis]+.0001||cut>=source.bounds.max[axis]-.0001)continue;
    const points=[];
    const verts=source.vertices,idx=source.indices;
    for(let i=0;i<idx.length;i+=3) {
      const tri=[verts[idx[i]],verts[idx[i+1]],verts[idx[i+2]]];
      for(let e=0;e<3;e++){
        const a=tri[e],b=tri[(e+1)%3],da=a[axis]-cut,db=b[axis]-cut;
        if(da*db>0||Math.abs(da-db)<1e-10)continue;
        const p=a.clone().lerp(b,da/(da-db));
        points.push(new THREE.Vector2(axis==="x"?p.z:p.x,p.y));
      }
    }
    const hull=convexHull(points);
    if(hull.length<3)continue;
    const shape=new THREE.Shape(hull);
    const geometry=new THREE.ShapeGeometry(shape);
    const pos=geometry.attributes.position;
    for(let i=0;i<pos.count;i++){const u=pos.getX(i),v=pos.getY(i);pos.setXYZ(i,axis==="x"?cut+.00001:u,v,axis==="x"?u:cut+.00001);}
    geometry.computeVertexNormals();
    const cap=new THREE.Mesh(geometry,capMat);
    cap.name="Section_"+source.node.name; cap.userData.source=source.node.uuid;
    caps.add(cap);
  }
  if(!caps.children.length)capMat.dispose();
  state.sectionCaps=caps;scene.add(caps);
}
function floors() {
  focusBuilding();
  for(const n of collect(n=>building(n)===state.building)){
    if(ownRole(n)==="roof")n.visible=false;
    if(ownRole(n)==="floor")n.visible=state.isolateFloor?Number(level(n))===state.floor:Number(level(n))<=state.floor;
    if(role(n)==="ceiling"&&Number(level(n))===state.floor)n.visible=false;
  }
}
function apartment() {
  const root=unitRoot(); if(!root)return;
  state.building=building(root);
  for(const n of meshList)n.visible=belongs(n,root)&&!["ceiling","collision"].includes(role(n));
  // A dollhouse removes its front envelope, not the objects inside.
  for(const n of meshList)if(belongs(n,root)&&/FrontWall|Ceiling/.test(n.name))n.visible=false;
}
function renderState({frame=false}={}) {
  if(!state.model)return;
  restore(); state.isolated=null;
  if(state.mode==="cutaway")section();
  else if(state.mode==="floors")floors();
  else if(state.mode==="apartment")apartment();
  else if(state.explosion>0)explode();
  if(frame)frameScene();
  updateUI();syncBatches();renderer.shadowMap.needsUpdate=true;
}
function setMode(mode) {
  stopWalking();
  if(mode==="exploded"){state.mode="exterior";state.explosion=state.explosion||.65;state.context=true;}
  else {state.mode=mode;state.explosion=0;if(mode==="floors")state.context=true;}
  state.unit=null;renderState({frame:true});
}
function updateUI() {
  const floorsMode=state.mode==="floors",sectionMode=state.mode==="cutaway",unitMode=state.mode==="apartment";
  const name=floorsMode?(state.floor===0?"Parter":"Etaj "+state.floor):sectionMode?"Secțiune":state.explosion>0?"Straturi separate":"Ansamblul";
  $("#dock-heading").textContent=unitMode?"Interior · "+state.unit:name+" · "+(state.mode==="exterior"&&state.explosion===0?"INTERMEDIA":"Bloc "+state.building);
  $("#dock-help").textContent=sectionMode?"Un plan real prin pereți și planșee · click pentru detalii":state.explosion>0?"Acoperiș, etaje și fațade · click pe orice element":"Trage pentru orbitare · scroll pentru zoom · click pentru detalii";
  $("#building-label").textContent="Bloc "+state.building;
  $("#mode-detail").textContent=unitMode?"Amenajare ilustrativă":floorsMode?"Planul nivelului selectat":sectionMode?"Secțiuni solide, camere deschise":state.explosion>0?"Poziții reversibile · 0% = asamblat":"Vedere exterioară";
  const slider=$("#layer-range");
  slider.hidden=unitMode;$("#layer-control").style.display=unitMode?"none":"flex";
  slider.max=floorsMode?"3":"100";slider.step="1";
  slider.value=String(floorsMode?state.floor:Math.round((sectionMode?state.section:state.explosion)*100));
  $("#layer-output").textContent=floorsMode?name:slider.value+"%";
  const label=floorsMode?"Nivel":sectionMode?"Poziția secțiunii":"Separarea straturilor";
  $("#layer-label").textContent=label;slider.setAttribute("aria-label",label);
  axisPicker.hidden=!sectionMode;
  axisPickerValue.textContent=state.sectionAxis==="x"?"Stânga ↔ dreapta":"Față ↔ spate";
  axisList.querySelectorAll('[role="option"]').forEach(option=>option.setAttribute("aria-selected",String(option.dataset.axis===state.sectionAxis)));
  $("#isolate-label").hidden=!floorsMode;$("#isolate-floor").checked=state.isolateFloor;
  $("#context-label").hidden=unitMode||(state.mode==="exterior"&&state.explosion===0);$("#show-context").checked=state.context;
  $("#isolate-component").textContent="Izolează";
  document.querySelectorAll("[data-mode]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.mode==="exploded"?state.explosion>0:n.dataset.mode===state.mode&&(state.mode!=="exterior"||state.explosion===0))));
  document.querySelectorAll("[data-building]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.building===state.building)));
  document.querySelectorAll("[data-unit]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.unit===state.unit)));
  refreshCatalogue();
}
const roleNames={exterior_wall:"Mur exterior",interior_partition:"Perete interior",window_glazing:"Vitraj",window_frame:"Tâmplărie",balcony_parapet:"Parapet de cărămidă",balcony_slab:"Planșeu balcon",floor_slab:"Planșeu",roof_panel:"Învelitoare",roof:"Acoperiș",ceiling:"Tavan",vehicle_body:"Caroserie",parking_marking:"Marcaj parcare",apartment_floor:"Pardoseală",stair_tread:"Treaptă",furniture:"Mobilier",marketing_banner_panel:"Panou INTERMEDIA",marketing_banner_text:"Mesaj INTERMEDIA",marketing_banner_frame:"Cadru banner"};
function title(n) { return roleNames[role(n)]||n.name.replace(/^BLK-[ABC]_F\d_/,"").replaceAll("_"," "); }
function select(n) {
  if(!n||!visible(n))return;
  state.selected=n;
  outline.box.copy(new THREE.Box3().setFromObject(n));outline.visible=true;
  updateSelectionMarker(n);
  $("#inspector").hidden=false;
  $("#component-title").textContent=title(n);
  $("#component-description").textContent=building(n)?"Element al reconstrucției de referință. Compartimentarea și detaliile constructive sunt ilustrative.":"Element de amenajare a curții, cu poziție ilustrativă.";
  const dl=$("#component-meta");dl.replaceChildren();
  for(const [key,value] of [["Clădire",building(n)?"Bloc "+building(n):"Curte"],["Nivel",level(n)===null?"—":Number(level(n))===0?"Parter":"Etaj "+level(n)],["Element",n.name]]){
    const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=key;dd.textContent=value;dl.append(dt,dd);
  }
  refreshCatalogue(true);
}
function pickAt(clientX,clientY) {
  camera.updateMatrixWorld(true);state.model?.updateMatrixWorld(true);
  const rect=renderer.domElement.getBoundingClientRect();
  picker.setFromCamera(new THREE.Vector2((clientX-rect.left)/rect.width*2-1,-(clientY-rect.top)/rect.height*2+1),camera);
  const hit=picker.intersectObjects([...meshList,...(state.sectionCaps?.children||[])],false).find(hit=>visible(hit.object)&&role(hit.object)!=="collision"&&
    !(state.mode==="cutaway"&&building(hit.object)===state.building&&clipPlane.distanceToPoint(hit.point)<-.0001));
  if(hit?.object.userData.source)return {...hit,object:meshList.find(n=>n.uuid===hit.object.userData.source),sectionCap:true};
  return hit;
}
const picker=new THREE.Raycaster();
picker.layers.enable(1);
let pointerStart=null;
renderer.domElement.addEventListener("pointerdown",e=>pointerStart={x:e.clientX,y:e.clientY});
renderer.domElement.addEventListener("pointerup",e=>{
  if(state.walking||!pointerStart||Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>5)return;
  const hit=pickAt(e.clientX,e.clientY);
  if(hit)select(hit.object);else clearSelection();
});
$("#close-inspector").onclick=clearSelection;
$("#frame-component").onclick=()=>{if(state.selected)frameBounds(new THREE.Box3().setFromObject(state.selected));};
$("#isolate-component").onclick=()=>{
  const selected=state.selected;if(!selected)return;
  if(state.isolated){renderState({frame:true});return;}
  state.isolated=selected;
  for(const n of meshList)n.visible=n===selected;
  if(state.sectionCaps)state.sectionCaps.visible=false;
  guides.visible=false;select(selected);frameBounds(new THREE.Box3().setFromObject(selected));
  syncBatches();renderer.shadowMap.needsUpdate=true;
  $("#isolate-component").textContent="Arată ansamblul";
};
const componentPicker=document.createElement("div");componentPicker.className="component-picker";
componentPicker.innerHTML='<button type="button" class="component-picker-button" id="component-picker-button" aria-haspopup="listbox" aria-expanded="false"><span id="component-picker-value">Selectează un element…</span><span class="component-picker-chevron" aria-hidden="true">⌄</span></button><div class="component-list" id="component-list" role="listbox" aria-label="Lista elementelor vizibile" hidden></div>';
$(".side-panel").append(componentPicker);
const pickerButton=$("#component-picker-button"),catalogue=$("#component-list"),pickerValue=$("#component-picker-value");
function setPickerOpen(open){pickerButton.setAttribute("aria-expanded",String(open));catalogue.hidden=!open;if(open)catalogue.querySelector('[role="option"]:not([aria-disabled="true"])')?.focus();}
pickerButton.onclick=()=>setPickerOpen(catalogue.hidden);
pickerButton.onkeydown=e=>{if(["Enter"," ","ArrowDown"].includes(e.key)){e.preventDefault();setPickerOpen(true);}if(e.key==="Escape")setPickerOpen(false);};
catalogue.onkeydown=e=>{const options=[...catalogue.querySelectorAll('[role="option"]:not([aria-disabled="true"])')];const index=options.indexOf(document.activeElement);if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();options[(index+(e.key==="ArrowDown"?1:-1)+options.length)%options.length]?.focus();}if(e.key==="Escape"){setPickerOpen(false);pickerButton.focus();}if(e.key==="Enter"||e.key===" "){e.preventDefault();document.activeElement?.click();}};
document.addEventListener("pointerdown",e=>{if(!componentPicker.contains(e.target))setPickerOpen(false);});
function refreshCatalogue(force=false) {
  const key=[state.mode,state.building,state.floor,state.isolateFloor,state.explosion>0,state.unit,state.selected?.uuid||""].join(":");
  if(!force&&catalogue.dataset.stateKey===key)return;
  catalogue.dataset.stateKey=key;catalogue.replaceChildren();
  const placeholder=document.createElement("div");placeholder.className="component-option";placeholder.setAttribute("role","option");placeholder.setAttribute("aria-disabled","true");placeholder.textContent="Selectează un element…";catalogue.append(placeholder);
  for(const n of meshList)if(visible(n)&&building(n)===state.building){const option=document.createElement("button");option.type="button";option.className="component-option";option.setAttribute("role","option");option.setAttribute("aria-selected",String(state.selected?.uuid===n.uuid));option.dataset.uuid=n.uuid;option.textContent=title(n);option.onclick=()=>{select(n);setPickerOpen(false);pickerButton.focus();};catalogue.append(option);}
  pickerValue.textContent=state.selected&&visible(state.selected)?title(state.selected):"Selectează un element…";
  $("#isolate-component").textContent="Izolează";guides.visible=true;
}
$("#layer-range").addEventListener("input",e=>{
  const value=Number(e.target.value),wasExploded=state.explosion>0;
  if(state.mode==="cutaway")state.section=value/100;
  else if(state.mode==="floors")state.floor=value;
  else {state.explosion=value/100;if(state.explosion>0&&!wasExploded)state.context=true;}
  // Frame once when activating explosion, never continuously during a drag.
  renderState({frame:!wasExploded&&state.explosion>0});
});
$("#isolate-floor").onchange=e=>{state.isolateFloor=e.target.checked;renderState();};
$("#show-context").onchange=e=>{state.context=e.target.checked;renderState();};
document.querySelectorAll("[data-mode]").forEach(n=>n.onclick=()=>setMode(n.dataset.mode));
document.querySelectorAll("[data-building]").forEach(n=>n.onclick=()=>{state.building=n.dataset.building;state.unit=null;if(state.mode==="apartment")state.mode="exterior";renderState({frame:true});});
document.querySelectorAll("[data-unit]").forEach(n=>n.onclick=()=>{stopWalking();state.unit=n.dataset.unit;state.mode="apartment";state.explosion=0;renderState({frame:true});});
document.querySelectorAll("[data-view]").forEach(n=>n.onclick=()=>{
  setMode("exterior");
  if(n.dataset.view==="courtyard"){camera.position.set(34,13,43);controls.target.set(0,3,13);}
  if(n.dataset.view==="facade"){camera.position.set(28,13,39);controls.target.set(0,7,4);}
  controls.update();
});
function reset(){
  stopWalking();Object.assign(state,{mode:"exterior",building:"A",floor:3,unit:null,explosion:0,section:.75,sectionAxis:"z",isolateFloor:false,context:false,auto:false});
  $("#auto-view").setAttribute("aria-pressed","false");renderState({frame:true});
}
$("#reset-view").onclick=reset;
$("#zoom-in").onclick=()=>{camera.position.lerp(controls.target,.15);controls.update();};
$("#zoom-out").onclick=()=>{camera.position.sub(controls.target).multiplyScalar(1.18).add(controls.target);controls.update();};
$("#auto-view").onclick=()=>{state.auto=!state.auto;$("#auto-view").setAttribute("aria-pressed",String(state.auto));};
function quality(preset) {
  state.quality=["ultra","high","balanced"].includes(preset)?preset:"balanced";
  const q={ultra:[2,4096],high:[1.5,2048],balanced:[1,1024]}[state.quality];
  renderer.setPixelRatio(Math.min(devicePixelRatio,q[0]));
  renderer.shadowMap.enabled=true;
  sun.shadow.mapSize.set(q[1],q[1]);sun.shadow.map?.dispose();sun.shadow.map=null;
  $("#quality-picker-value").textContent={ultra:"Ultra",high:"High",balanced:"Balanced"}[state.quality];
  document.querySelectorAll(".quality-option").forEach(option=>option.setAttribute("aria-selected",String(option.dataset.quality===state.quality)));
  resize();
}
const qualityPicker=$("#quality-picker"),qualityPickerButton=$("#quality-picker-button"),qualityList=$("#quality-list");
function setQualityOpen(open){qualityPickerButton.setAttribute("aria-expanded",String(open));qualityList.hidden=!open;if(open)qualityList.querySelector('[role="option"]')?.focus();}
qualityPickerButton.onclick=()=>setQualityOpen(qualityList.hidden);
qualityPickerButton.onkeydown=e=>{if(["Enter"," ","ArrowDown"].includes(e.key)){e.preventDefault();setQualityOpen(true);}if(e.key==="Escape")setQualityOpen(false);};
qualityList.onkeydown=e=>{const options=[...qualityList.querySelectorAll('[role="option"]')],index=options.indexOf(document.activeElement);if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();options[(index+(e.key==="ArrowDown"?1:-1)+options.length)%options.length]?.focus();}if(e.key==="Escape"){setQualityOpen(false);qualityPickerButton.focus();}if(e.key==="Enter"||e.key===" "){e.preventDefault();document.activeElement?.click();}};
qualityList.querySelectorAll('[role="option"]').forEach(option=>option.onclick=()=>{quality(option.dataset.quality);setQualityOpen(false);qualityPickerButton.focus();});
document.addEventListener("pointerdown",e=>{if(!qualityPicker.contains(e.target))setQualityOpen(false);});
const axisPicker=$("#axis-picker"),axisPickerButton=$("#axis-picker-button"),axisList=$("#axis-list"),axisPickerValue=$("#axis-picker-value");
function setAxisOpen(open){axisPickerButton.setAttribute("aria-expanded",String(open));axisList.hidden=!open;if(open)axisList.querySelector('[role="option"]')?.focus();}
axisPickerButton.onclick=()=>setAxisOpen(axisList.hidden);
axisPickerButton.onkeydown=e=>{if(["Enter"," ","ArrowDown"].includes(e.key)){e.preventDefault();setAxisOpen(true);}if(e.key==="Escape")setAxisOpen(false);};
axisList.onkeydown=e=>{const options=[...axisList.querySelectorAll('[role="option"]')],index=options.indexOf(document.activeElement);if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();options[(index+(e.key==="ArrowDown"?1:-1)+options.length)%options.length]?.focus();}if(e.key==="Escape"){setAxisOpen(false);axisPickerButton.focus();}if(e.key==="Enter"||e.key===" "){e.preventDefault();document.activeElement?.click();}};
axisList.querySelectorAll('[role="option"]').forEach(option=>option.onclick=()=>{state.sectionAxis=option.dataset.axis;setAxisOpen(false);axisPickerButton.focus();renderState({frame:true});});
document.addEventListener("pointerdown",e=>{if(!axisPicker.contains(e.target))setAxisOpen(false);});

// Ground and apartment walking use the visible solids, not the giant site
// boundary proxy. A downward ray supplies floor height; horizontal rays preserve
// a 36 cm clearance from walls at knee and chest height.
const collisionRay=new THREE.Raycaster();
collisionRay.layers.enable(1);
function stopWalking(){
  state.walking=false;state.keys.clear();controls.enabled=true;
  $("#walk-hint").classList.remove("is-visible");$("#walk-toggle").classList.remove("is-active");
  if(document.pointerLockElement===renderer.domElement)document.exitPointerLock();
}
function startWalking() {
  const requested=state.mode==="apartment"?unitRoot():null;
  const interior=Boolean(requested);
  state.mode=interior?"apartment":"exterior";state.explosion=0;if(!interior)state.unit=null;renderState();
  if(requested){
    const b=new THREE.Box3().setFromObject(requested),c=b.getCenter(new THREE.Vector3());
    let threshold=null;requested.traverse(n=>{if(!threshold&&role(n)==="balcony_door_glazing")threshold=n;});
    const doorBounds=threshold?new THREE.Box3().setFromObject(threshold):null;
    // Start just inside the balcony threshold, looking through the room. This
    // avoids spawning behind a parapet or inside furniture while preserving a
    // clear first-person route into the apartment.
    const entryZ=doorBounds?doorBounds.min.z-.7:c.z-1.0;
    const gazeZ=doorBounds?doorBounds.min.z-3.0:c.z-2.0;
    camera.position.set(c.x,b.min.y+1.72,entryZ);controls.target.set(c.x,camera.position.y,gazeZ);
  }else{camera.position.set(0,1.9,24);controls.target.set(0,1.9,4);}
  camera.lookAt(controls.target);
  const e=new THREE.Euler().setFromQuaternion(camera.quaternion,"YXZ");state.yaw=e.y;state.pitch=e.x;
  state.walking=true;state.auto=false;controls.enabled=false;
  $("#walk-hint").classList.add("is-visible");$("#walk-toggle").classList.add("is-active");
  try{const pointerLock=renderer.domElement.requestPointerLock?.();pointerLock?.catch?.(()=>{});}catch{}
}
$("#walk-toggle").onclick=()=>state.walking?stopWalking():startWalking();
function walk(delta){
  if(!state.walking)return;
  const forward=new THREE.Vector3(-Math.sin(state.yaw),0,-Math.cos(state.yaw));
  const right=new THREE.Vector3(-forward.z,0,forward.x),step=new THREE.Vector3();
  if(state.keys.has("KeyW")||state.keys.has("ArrowUp"))step.add(forward);
  if(state.keys.has("KeyS")||state.keys.has("ArrowDown"))step.sub(forward);
  if(state.keys.has("KeyD")||state.keys.has("ArrowRight"))step.add(right);
  if(state.keys.has("KeyA")||state.keys.has("ArrowLeft"))step.sub(right);
  if(!step.lengthSq())return;
  const solids=meshList.filter(n=>visible(n)&&role(n)!=="collision"&&!/glazing|curtain|leaf/.test(role(n)||""));
  step.normalize().multiplyScalar(delta*3.2);
  const origin=camera.position.clone();
  let blocked=false;
  for(const h of [.3,1.2]){
    const start=origin.clone();start.y-=1.72-h;
    collisionRay.set(start,step.clone().normalize());collisionRay.far=step.length()+.36;
    if(collisionRay.intersectObjects(solids,false).length){blocked=true;break;}
  }
  if(blocked)return;
  const next=origin.add(step);
  collisionRay.set(next.clone().add(new THREE.Vector3(0,-1.15,0)),new THREE.Vector3(0,-1,0));collisionRay.far=1.2;
  const ground=collisionRay.intersectObjects(solids,false).find(h=>h.face.normal.clone().transformDirection(h.object.matrixWorld).y>.55);
  if(!ground)return;
  const targetY=ground.point.y+1.72;
  if(Math.abs(targetY-camera.position.y)>.5)return;
  next.y=THREE.MathUtils.lerp(camera.position.y,targetY,Math.min(1,delta*15));
  camera.position.copy(next);
}
addEventListener("keydown",e=>{
  if(e.key==="Escape"){stopWalking();clearSelection();return;}
  if(["INPUT","SELECT","TEXTAREA"].includes(document.activeElement?.tagName))return;
  if(state.walking&&/^(Arrow|Key[WASD])/.test(e.code))e.preventDefault();
  state.keys.add(e.code);
});
addEventListener("keyup",e=>state.keys.delete(e.code));
addEventListener("blur",()=>state.keys.clear());
addEventListener("mousemove",e=>{
  if(!state.walking||document.pointerLockElement!==renderer.domElement)return;
  state.yaw-=e.movementX*.002;state.pitch=THREE.MathUtils.clamp(state.pitch-e.movementY*.002,-1.3,1.3);
  camera.rotation.set(state.pitch,state.yaw,0,"YXZ");
});
renderer.domElement.addEventListener("click",()=>{if(state.walking)renderer.domElement.requestPointerLock?.();});
addEventListener("resize",resize);
quality(state.quality);

function prepare(model) {
  state.model=model;scene.add(model);model.updateMatrixWorld(true);
  const materialCache=new Map();
  model.traverse(n=>{
    if(n.isLight||n.isCamera||role(n)==="collision"||role(n)==="collision_root")n.visible=false;
    state.base.set(n,{position:n.position.clone(),quaternion:n.quaternion.clone(),visible:n.visible});
    if(!n.isMesh)return;
    // Shared by building boundary: clipping cannot leak into site/context.
    const mapped=materials(n).map(m=>{
      const key=m.uuid+":"+building(n);
      if(!materialCache.has(key)){
        const copy=m.clone();copy.clippingPlanes=[];copy.clipShadows=true;
        if(copy.map)copy.map.anisotropy=renderer.capabilities.getMaxAnisotropy();
        materialCache.set(key,copy);
      }
      return materialCache.get(key);
    });
    n.material=Array.isArray(n.material)?mapped:mapped[0];
    n.castShadow=!/glazing|collision/.test(role(n)||"");n.receiveShadow=true;
    meshList.push(n);
    if(!structural(n))return;
    if(n.userData.section_cells_json){
      const cells=JSON.parse(n.userData.section_cells_json);
      const indices=[0,3,2,0,2,1,4,5,6,4,6,7,0,1,5,0,5,4,1,2,6,1,6,5,2,3,7,2,7,6,3,0,4,3,4,7];
      for(const [x0,x1,y0,y1,z0,z1] of cells){
        // Extras remain in Blender coordinates; geometry was exported Y-up.
        const vertices=[[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]]
          .map(([x,y,z])=>new THREE.Vector3(x,z,-y).applyMatrix4(n.matrixWorld));
        sectionSources.push({node:n,vertices,indices,bounds:new THREE.Box3().setFromPoints(vertices)});
      }
      return;
    }
    const p=n.geometry.attributes.position,vertices=[];
    for(let i=0;i<p.count;i++)vertices.push(new THREE.Vector3().fromBufferAttribute(p,i).applyMatrix4(n.matrixWorld));
    const indices=n.geometry.index?Array.from(n.geometry.index.array):vertices.map((_,i)=>i);
    sectionSources.push({node:n,vertices,indices,bounds:new THREE.Box3().setFromPoints(vertices)});
  });
  buildBatches();reset();
  $("#model-status").textContent=meshList.length.toLocaleString("ro-RO")+" elemente";
  $("#loading").classList.add("is-hidden");
}
function error(message){
  $("#loading").classList.remove("is-hidden");
  $("#loading-copy").textContent=message;$("#loading-copy").classList.add("error-message");
  const retry=document.createElement("button");retry.textContent="Reîncearcă";retry.className="pill-button";retry.onclick=()=>location.reload();$(".loading-card").append(retry);
}
if(location.protocol==="file:")error("Deschide exploratorul prin serverul HTTP local sau adresa GitHub Pages, nu ca fișier.");
else fetch("./assets/intermedia-residential.json",{cache:"no-store"}).then(r=>{
  if(!r.ok)throw Error("Manifest unavailable");return r.json();
}).then(manifest=>{
  new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load("./assets/intermedia-residential.glb?v="+encodeURIComponent(manifest.assetRevision||manifest.sceneVersion),
    g=>prepare(g.scene),
    p=>{if(p.total)$("#loading-copy").textContent="Se încarcă modelul… "+Math.round(p.loaded/p.total*100)+"%";},
    ()=>error("Modelul nu a putut fi încărcat. Verifică conexiunea și reîncearcă."));
}).catch(()=>error("Manifestul modelului nu este disponibil. Reîncearcă."));
renderer.domElement.addEventListener("webglcontextlost",e=>{e.preventDefault();error("Conexiunea cu placa grafică a fost întreruptă. Reîncarcă exploratorul.");});
const clock=new THREE.Clock();
function animate(){
  requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.05);
  if(state.auto&&!state.walking&&!matchMedia("(prefers-reduced-motion: reduce)").matches){
    camera.position.sub(controls.target).applyAxisAngle(new THREE.Vector3(0,1,0),dt*.1).add(controls.target);
  }
  walk(dt);if(!state.walking)controls.update();renderer.render(scene,camera);
}
animate();
window.intermediaSetView=(command={})=>{
  stopWalking();
  if(command.building!==undefined){if(!["A","B","C"].includes(command.building))throw Error("Unknown building");state.building=command.building;}
  for(const [key,min,max] of [["floor",0,3],["explosion",0,1],["section",0,1]]){
    if(command[key]!==undefined){if(!Number.isFinite(command[key]))throw Error("Invalid "+key);state[key]=THREE.MathUtils.clamp(command[key],min,max);}
  }
  state.floor=Math.round(state.floor);
  if(command.sectionAxis!==undefined){if(!["x","z"].includes(command.sectionAxis))throw Error("Invalid section axis");state.sectionAxis=command.sectionAxis;}
  if(command.isolateFloor!==undefined)state.isolateFloor=Boolean(command.isolateFloor);
  if(command.context!==undefined)state.context=Boolean(command.context);
  if(command.mode!==undefined){
    if(!["exterior","exploded","cutaway","floors","apartment"].includes(command.mode))throw Error("Unknown mode");
    state.mode=command.mode==="exploded"?"exterior":command.mode;
    if(state.mode!=="exterior")state.explosion=0;
    if(command.mode==="exploded"&&command.context===undefined)state.context=true;
    if(command.mode==="floors"&&command.context===undefined)state.context=true;
    if(command.mode==="exploded"&&command.explosion===undefined){state.explosion=.65;if(command.context===undefined)state.context=true;}
    if(command.mode==="exterior"&&command.explosion===undefined)state.explosion=0;
  }
  if(command.unit!==undefined){
    if(![null,"Studio","2Room","3Room"].includes(command.unit))throw Error("Unknown apartment");
    state.unit=command.unit;if(command.unit)state.mode="apartment";
  }
  renderState({frame:command.frame!==false});
};
window.__intermedia={scene,renderer,camera,controls,state,sky,clipPlane,pickAt,select,visible,meshList,batches,selectionMarker,reset};
