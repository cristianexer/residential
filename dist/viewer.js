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

const translations = {
  en: {
    app:{title:"INTERMEDIA / 3D explorer",description:"3D explorer for the INTERMEDIA residential complex."},
    brand: {subtitle:"real estate · 3D explorer"},
    viewport:"INTERMEDIA 3D view", project: {meta:"P+3 · 03 blocks"},
    mode:{label:"View mode",exterior:"Exterior",exploded:"Exploded",cutaway:"Cutaway",floors:"Floors"},
    sidebar:{eyebrow:"Residential complex / illustration",intro:"Explore the three blocks, landscaped parking and representative interiors.",chooseBlock:"Choose a block",apartmentType:"Apartment type",quickViews:"Quick views"},
    headline:{line1:"A place for",line2:"everyday life."},
    stats:{configuration:"Configuration",configurationValue:"3 blocks · P+3",parking:"Parking",parkingValue:"Surface",types:"Types",typesValue:"Studio · 2 · 3 rooms",studio:"Studio",studioValue:"30.30 + 6.60 m²"},
    unit:{Studio:{name:"Studio",note:"30.30 m² usable + 6.60 m² balcony"},"2Room":{name:"2 rooms",note:"Representative plan, illustrative"},"3Room":{name:"3 rooms",note:"Representative plan, illustrative"}},
    view:{overview:"Overview",courtyard:"Courtyard",facade:"Façade"},
    inspector:{eyebrow:"In detail",selected:"Selected element",buildingDescription:"Element from the reference-based architectural reconstruction. Layout and construction details are illustrative.",siteDescription:"Illustrative site and landscape element."},
    action:{walkthrough:"Walkthrough",frame:"Frame",isolate:"Isolate",showAssembly:"Show assembly",closeDetails:"Close details"},
    dock:{initial:"INTERMEDIA complex",kicker:"Explore the model",layerSeparation:"Layer separation",sectionPosition:"Section position",floorLevel:"Floor level",thisFloor:"This floor only",context:"Context",illustrative:"illustrative model",exploded:"Separated layers",explodedHelp:"Roof, floors and façades · click any element",sectionHelp:"A real section through walls and slabs · click for details",defaultHelp:"Drag to orbit · scroll to zoom · click for details",explodedDetail:"Reversible positions · 0% = assembled",sectionDetail:"Solid sections, open rooms",floorDetail:"Selected floor plan",apartmentDetail:"Illustrative furnishing",exteriorDetail:"Exterior view"},
    axis:{label:"Section orientation",frontBack:"Front ↔ back",leftRight:"Left ↔ right"},
    floor:{ground:"Ground floor",label:"Floor"},
    meta:{building:"Building",level:"Level",element:"Element",id:"ID",courtyard:"Courtyard",none:"—"},
    role:{component:"Architectural component",exterior_wall:"Exterior wall",interior_partition:"Interior wall",window_glazing:"Window glazing",window_frame:"Window frame",window_curtain:"Curtain",balcony_parapet:"Brick balcony parapet",balcony_slab:"Balcony slab",balcony_rail:"Balcony railing",balcony_door_glazing:"Balcony door glazing",balcony_threshold:"Balcony threshold",balcony_coping:"Balcony coping",floor_slab:"Floor slab",floor:"Floor level",apartment_floor:"Apartment floor",roof_panel:"Roof covering",roof:"Roof",roof_seam:"Roof seam",roof_downpipe:"Downpipe",roof_gutter:"Gutter",roof_surface:"Roof surface",ceiling:"Ceiling",facade:"Façade section",facade_trim:"Façade trim",apartment_shell:"Apartment envelope",building:"Building",detailed_apartment:"Furnished apartment",entrance:"Entrance",entrance_post:"Entrance canopy post",entrance_canopy:"Entrance canopy",entrance_glazing:"Entrance glazing",entrance_step:"Entrance step",circulation:"Circulation",stairwell_wall:"Stairwell wall",stair_tread:"Stair tread",stair_riser:"Stair riser",stair_landing:"Stair landing",stair_handrail:"Stair handrail",stair_handrail_post:"Handrail post",vehicle:"Vehicle",vehicle_body:"Car body",vehicle_bumper:"Car bumper",vehicle_glazing:"Car windows",vehicle_handle:"Car handle",vehicle_hub:"Wheel hub",vehicle_light:"Car light",vehicle_mirror:"Side mirror",vehicle_pillar:"Car pillar",vehicle_plate:"License plate",vehicle_rim:"Wheel rim",vehicle_roof:"Car roof",vehicle_sill:"Door sill",vehicle_wheel:"Tire",parking_bay:"Parking bay",parking_marking:"Parking marking",tree_canopy:"Tree canopy",tree_trunk:"Tree trunk",landscape_tree:"Landscape tree",interior_plant_leaf:"Plant leaf",interior_plant_pot:"Plant pot",interior_plant_stem:"Plant stem",site:"Site",site_ground:"Site ground",landscape_context:"Landscape context",public_street:"Public street",sidewalk:"Sidewalk",access_court:"Access court",planted_island:"Planted island",perimeter_fence:"Perimeter fence",site_bin:"Waste bin",marketing_banner:"Marketing banner",marketing_banner_panel:"INTERMEDIA sign panel",marketing_banner_text:"INTERMEDIA message",marketing_banner_frame:"Banner frame",marketing_banner_post:"Banner post",marketing_banner_foot:"Banner footing",kitchen_handle:"Kitchen handle",kitchen_upper_cabinet:"Upper kitchen cabinet",fitted_kitchen:"Fitted kitchen",kitchen_counter:"Kitchen worktop",kitchen_backsplash:"Kitchen backsplash",kitchen_oven:"Oven",kitchen_sink:"Kitchen sink",kitchen_tap:"Kitchen tap",refrigerator:"Refrigerator",under_cabinet_light:"Under-cabinet light",dining_chair:"Dining chair",dining_table:"Dining table",dining_table_leg:"Table leg",sofa:"Sofa",sofa_cushion:"Sofa cushion",rug:"Rug",bed_frame:"Bed frame",bed_headboard:"Headboard",bed_linen:"Bed linen",bed_mattress:"Mattress",bed_pillow:"Pillow",desk:"Desk",desk_chair:"Desk chair",desk_leg:"Desk leg",computer_monitor:"Monitor",television:"Television",bathroom_tile:"Bathroom tile",bathroom_floor:"Bathroom floor",bathroom_mirror:"Bathroom mirror",bathroom_sink:"Bathroom sink",bathroom_vanity:"Bathroom vanity",shower_glass:"Shower glass",shower_fitting:"Shower fitting",toilet:"Toilet",interior_door:"Interior door",interior_curtain:"Curtain",curtain_track:"Curtain track",collision:"Collision volume",collision_root:"Collision geometry",overview_camera:"Camera",project:"Project",furniture:"Furniture"},
    model:{loading:"loading…",elements:"elements"}, quality:{label:"Quality",ultra:"Ultra",high:"High",balanced:"Balanced"}, component:{label:"Visible components",placeholder:"Select a component…"},
    loading:{copy:"Loading architecture, textures and grounds…",retry:"Retry",model:"The model could not be loaded. Check the connection and try again.",manifest:"The model manifest is unavailable. Try again.",gpu:"The graphics connection was interrupted. Reload the explorer.",file:"Open the explorer through a local HTTP server or its GitHub Pages address, not as a file."},
    walkthrough:{hint:"Click the model to control · WASD / arrows · Esc to exit",interior:"Interior · "},
    camera:{label:"Camera controls",zoomIn:"Zoom in",zoomOut:"Zoom out",reset:"Reset view",auto:"Auto orbit"},
    language:{label:"Language",english:"English",romanian:"Română"}
  },
  ro: {
    app:{title:"INTERMEDIA / explorator 3D",description:"Explorator 3D pentru ansamblul rezidențial INTERMEDIA."},
    brand: {subtitle:"imobiliare · explorator 3D"},
    viewport:"Vizualizare 3D INTERMEDIA", project: {meta:"P+3 · 03 blocuri"},
    mode:{label:"Mod de vizualizare",exterior:"Exterior",exploded:"Explodat",cutaway:"Secțiune",floors:"Etaje"},
    sidebar:{eyebrow:"Ansamblu rezidențial / ilustrație",intro:"Explorează cele trei blocuri, parcarea amenajată și interioarele reprezentative.",chooseBlock:"Alege un bloc",apartmentType:"Tip de apartament",quickViews:"Vederi rapide"},
    headline:{line1:"Un loc pentru",line2:"viața de zi cu zi."},
    stats:{configuration:"Configurație",configurationValue:"3 blocuri · P+3",parking:"Parcare",parkingValue:"Supraterană",types:"Tipuri",typesValue:"Garsonieră · 2 · 3 camere",studio:"Garsonieră",studioValue:"30,30 + 6,60 m²"},
    unit:{Studio:{name:"Garsonieră",note:"30,30 m² utili + balcon 6,60 m²"},"2Room":{name:"2 camere",note:"Plan reprezentativ, ilustrativ"},"3Room":{name:"3 camere",note:"Plan reprezentativ, ilustrativ"}},
    view:{overview:"Ansamblu",courtyard:"Curte",facade:"Fațadă"},
    inspector:{eyebrow:"În detaliu",selected:"Element selectat",buildingDescription:"Element al reconstrucției arhitecturale bazate pe referințe. Compartimentarea și detaliile constructive sunt ilustrative.",siteDescription:"Element ilustrativ al curții și peisajului."},
    action:{walkthrough:"Tur interior",frame:"Încadrează",isolate:"Izolează",showAssembly:"Arată ansamblul",closeDetails:"Închide detaliile"},
    dock:{initial:"Ansamblu INTERMEDIA",kicker:"Explorează modelul",layerSeparation:"Separarea straturilor",sectionPosition:"Poziția secțiunii",floorLevel:"Nivelul",thisFloor:"Doar acest etaj",context:"Context",illustrative:"model ilustrativ",exploded:"Straturi separate",explodedHelp:"Acoperiș, etaje și fațade · click pe orice element",sectionHelp:"Un plan real prin pereți și planșee · click pentru detalii",defaultHelp:"Trage pentru orbitare · scroll pentru zoom · click pentru detalii",explodedDetail:"Poziții reversibile · 0% = asamblat",sectionDetail:"Secțiuni solide, camere deschise",floorDetail:"Planul nivelului selectat",apartmentDetail:"Amenajare ilustrativă",exteriorDetail:"Vedere exterioară"},
    axis:{label:"Orientarea secțiunii",frontBack:"Față ↔ spate",leftRight:"Stânga ↔ dreapta"},
    floor:{ground:"Parter",label:"Etaj"},
    meta:{building:"Clădire",level:"Nivel",element:"Element",id:"ID",courtyard:"Curte",none:"—"},
    role:{component:"Componentă arhitecturală",exterior_wall:"Perete exterior",interior_partition:"Perete interior",window_glazing:"Vitraj",window_frame:"Tâmplărie",window_curtain:"Draperie",balcony_parapet:"Parapet de cărămidă",balcony_slab:"Planșeu balcon",balcony_rail:"Balustradă balcon",balcony_door_glazing:"Vitraj ușă balcon",balcony_threshold:"Prag balcon",balcony_coping:"Coping balcon",floor_slab:"Planșeu",floor:"Nivel",apartment_floor:"Pardoseală",roof_panel:"Învelitoare",roof:"Acoperiș",roof_seam:"Îmbinare acoperiș",roof_downpipe:"Jgheab vertical",roof_gutter:"Jgheab",roof_surface:"Suprafață acoperiș",ceiling:"Tavan",facade:"Travee fațadă",facade_trim:"Profil fațadă",apartment_shell:"Anvelopă apartament",building:"Clădire",detailed_apartment:"Apartament mobilat",entrance:"Intrare",entrance_post:"Stâlp copertină",entrance_canopy:"Copertină intrare",entrance_glazing:"Vitraj intrare",entrance_step:"Treaptă intrare",circulation:"Circulație",stairwell_wall:"Perete casa scării",stair_tread:"Treaptă",stair_riser:"Contratreaptă",stair_landing:"Podest scară",stair_handrail:"Mână curentă",stair_handrail_post:"Stâlp balustradă",vehicle:"Vehicul",vehicle_body:"Caroserie",vehicle_bumper:"Bară protecție",vehicle_glazing:"Geamuri mașină",vehicle_handle:"Mâner mașină",vehicle_hub:"Butuc roată",vehicle_light:"Far / stop",vehicle_mirror:"Oglindă laterală",vehicle_pillar:"Stâlp caroserie",vehicle_plate:"Număr de înmatriculare",vehicle_rim:"Jantă",vehicle_roof:"Plafon mașină",vehicle_sill:"Prag ușă",vehicle_wheel:"Anvelopă",parking_bay:"Loc de parcare",parking_marking:"Marcaj parcare",tree_canopy:"Coroană copac",tree_trunk:"Trunchi copac",landscape_tree:"Copac peisagistic",interior_plant_leaf:"Frunză plantă",interior_plant_pot:"Ghiveci",interior_plant_stem:"Tulpină plantă",site:"Amplasament",site_ground:"Teren",landscape_context:"Context peisagistic",public_street:"Stradă publică",sidewalk:"Trotuar",access_court:"Curte de acces",planted_island:"Insulă plantată",perimeter_fence:"Gard perimetral",site_bin:"Coș de gunoi",marketing_banner:"Banner INTERMEDIA",marketing_banner_panel:"Panou INTERMEDIA",marketing_banner_text:"Mesaj INTERMEDIA",marketing_banner_frame:"Cadru banner",marketing_banner_post:"Stâlp banner",marketing_banner_foot:"Fundație banner",kitchen_handle:"Mâner bucătărie",kitchen_upper_cabinet:"Corp superior bucătărie",fitted_kitchen:"Bucătărie echipată",kitchen_counter:"Blat bucătărie",kitchen_backsplash:"Placare bucătărie",kitchen_oven:"Cuptor",kitchen_sink:"Chiuvetă bucătărie",kitchen_tap:"Robinet bucătărie",refrigerator:"Frigider",under_cabinet_light:"Lumină sub corp",dining_chair:"Scaun dining",dining_table:"Masă dining",dining_table_leg:"Picior masă",sofa:"Canapea",sofa_cushion:"Pernă canapea",rug:"Covor",bed_frame:"Cadru pat",bed_headboard:"Tăblie pat",bed_linen:"Lenjerie pat",bed_mattress:"Saltea",bed_pillow:"Pernă",desk:"Birou",desk_chair:"Scaun birou",desk_leg:"Picior birou",computer_monitor:"Monitor",television:"Televizor",bathroom_tile:"Gresie baie",bathroom_floor:"Pardoseală baie",bathroom_mirror:"Oglindă baie",bathroom_sink:"Lavoar",bathroom_vanity:"Mobilier baie",shower_glass:"Sticlă duș",shower_fitting:"Baterie duș",toilet:"Vas WC",interior_door:"Ușă interioară",interior_curtain:"Draperie",curtain_track:"Sită / șină perdea",collision:"Volum de coliziune",collision_root:"Geometrie coliziune",overview_camera:"Cameră",project:"Proiect",furniture:"Mobilier"},
    model:{loading:"se încarcă…",elements:"elemente"}, quality:{label:"Calitate",ultra:"Ultra",high:"Înaltă",balanced:"Echilibrat"}, component:{label:"Elemente vizibile",placeholder:"Selectează un element…"},
    loading:{copy:"Se încarcă arhitectura, texturile și curtea…",retry:"Reîncearcă",model:"Modelul nu a putut fi încărcat. Verifică conexiunea și reîncearcă.",manifest:"Manifestul modelului nu este disponibil. Reîncearcă.",gpu:"Conexiunea cu placa grafică a fost întreruptă. Reîncarcă exploratorul.",file:"Deschide exploratorul printr-un server HTTP local sau adresa GitHub Pages, nu ca fișier."},
    walkthrough:{hint:"Click pe model pentru control · WASD / săgeți · Esc pentru ieșire",interior:"Interior · "},
    camera:{label:"Controale cameră",zoomIn:"Apropie",zoomOut:"Depărtează",reset:"Resetează",auto:"Orbitare automată"},
    language:{label:"Limbă",english:"English",romanian:"Română"}
  }
};
function t(key) {
  const read = source => key.split(".").reduce((value,part)=>value?.[part],source);
  return read(translations[state.language]) ?? read(translations.en) ?? key;
}
function buildingLabel(id) { return `${state.language === "ro" ? "Bloc" : "Block"} ${id}`; }
function floorLabel(index) { return Number(index)===0 ? t("floor.ground") : `${t("floor.label")} ${index}`; }
function unitLabel(kind) { return t(`unit.${kind}.name`); }
function localeTag() { return state.language === "ro" ? "ro-RO" : "en-US"; }

const state = {
  mode:"exterior", building:"A", floor:3, unit:null, explosion:0, section:.75,
  sectionAxis:"z", isolateFloor:false, context:false, auto:false, walking:false,
  language:"en", model:null, base:new Map(), selected:null, isolated:null, sectionCaps:null,
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
  const name=floorsMode?floorLabel(state.floor):sectionMode?t("mode.cutaway"):state.explosion>0?t("dock.exploded"):t("mode.exterior");
  $("#dock-heading").textContent=unitMode?t("walkthrough.interior")+unitLabel(state.unit):name+" · "+(state.mode==="exterior"&&state.explosion===0?"INTERMEDIA":buildingLabel(state.building));
  $("#dock-help").textContent=sectionMode?t("dock.sectionHelp"):state.explosion>0?t("dock.explodedHelp"):t("dock.defaultHelp");
  $("#building-label").textContent=buildingLabel(state.building);
  document.querySelectorAll("[data-building]").forEach(n=>n.textContent=buildingLabel(n.dataset.building));
  $("#mode-detail").textContent=unitMode?t("dock.apartmentDetail"):floorsMode?t("dock.floorDetail"):sectionMode?t("dock.sectionDetail"):state.explosion>0?t("dock.explodedDetail"):t("dock.exteriorDetail");
  const slider=$("#layer-range");
  slider.hidden=unitMode;$("#layer-control").style.display=unitMode?"none":"flex";
  slider.max=floorsMode?"3":"100";slider.step="1";
  slider.value=String(floorsMode?state.floor:Math.round((sectionMode?state.section:state.explosion)*100));
  $("#layer-output").textContent=floorsMode?name:slider.value+"%";
  const label=floorsMode?t("dock.floorLevel"):sectionMode?t("dock.sectionPosition"):t("dock.layerSeparation");
  $("#layer-label").textContent=label;slider.setAttribute("aria-label",label);
  axisPicker.hidden=!sectionMode;
  axisPickerValue.textContent=state.sectionAxis==="x"?t("axis.leftRight"):t("axis.frontBack");
  axisPickerButton.setAttribute("aria-label",t("axis.label"));axisList.setAttribute("aria-label",t("axis.label"));
  axisList.querySelectorAll('[role="option"]').forEach(option=>option.setAttribute("aria-selected",String(option.dataset.axis===state.sectionAxis)));
  $("#isolate-label").hidden=!floorsMode;$("#isolate-floor").checked=state.isolateFloor;
  $("#context-label").hidden=unitMode||(state.mode==="exterior"&&state.explosion===0);$("#show-context").checked=state.context;
  $("#isolate-component").textContent=t("action.isolate");
  document.querySelectorAll("[data-mode]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.mode==="exploded"?state.explosion>0:n.dataset.mode===state.mode&&(state.mode!=="exterior"||state.explosion===0))));
  document.querySelectorAll("[data-building]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.building===state.building)));
  document.querySelectorAll("[data-unit]").forEach(n=>n.setAttribute("aria-pressed",String(n.dataset.unit===state.unit)));
  refreshCatalogue();
}
function title(n) { const key=role(n),translated=translations[state.language]?.role?.[key]||translations.en.role?.[key];return translated||t("role.component"); }
function select(n) {
  if(!n||!visible(n))return;
  state.selected=n;
  outline.box.copy(new THREE.Box3().setFromObject(n));outline.visible=true;
  updateSelectionMarker(n);
  $("#inspector").hidden=false;
  $("#component-title").textContent=title(n);
  $("#component-description").textContent=building(n)?t("inspector.buildingDescription"):t("inspector.siteDescription");
  const dl=$("#component-meta");dl.replaceChildren();
  for(const [key,value] of [[t("meta.building"),building(n)?buildingLabel(building(n)):t("meta.courtyard")],[t("meta.level"),level(n)===null?t("meta.none"):floorLabel(level(n))],[t("meta.element"),title(n)],[t("meta.id"),n.name]]){
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
  $("#isolate-component").textContent=t("action.showAssembly");
};
const componentPicker=document.createElement("div");componentPicker.className="component-picker";
componentPicker.innerHTML='<button type="button" class="component-picker-button" id="component-picker-button" aria-haspopup="listbox" aria-expanded="false" aria-label="Visible components"><span id="component-picker-value">Select a component…</span><span class="component-picker-chevron" aria-hidden="true">⌄</span></button><div class="component-list" id="component-list" role="listbox" aria-label="Visible components" hidden></div>';
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
  const placeholder=document.createElement("div");placeholder.className="component-option";placeholder.setAttribute("role","option");placeholder.setAttribute("aria-disabled","true");placeholder.textContent=t("component.placeholder");catalogue.append(placeholder);
  for(const n of meshList)if(visible(n)&&building(n)===state.building){const option=document.createElement("button");option.type="button";option.className="component-option";option.setAttribute("role","option");option.setAttribute("aria-selected",String(state.selected?.uuid===n.uuid));option.dataset.uuid=n.uuid;option.textContent=title(n);option.onclick=()=>{select(n);setPickerOpen(false);pickerButton.focus();};catalogue.append(option);}
  pickerValue.textContent=state.selected&&visible(state.selected)?title(state.selected):t("component.placeholder");
  $("#isolate-component").textContent=state.isolated?t("action.showAssembly"):t("action.isolate");guides.visible=true;
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
  $("#quality-picker-value").textContent=t("quality."+state.quality);
  document.querySelectorAll(".quality-option").forEach(option=>{option.textContent=t("quality."+option.dataset.quality);option.setAttribute("aria-selected",String(option.dataset.quality===state.quality));});
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
const languagePicker=$("#language-picker"),languagePickerButton=$("#language-picker-button"),languageList=$("#language-list"),languagePickerValue=$("#language-picker-value");
function setLanguageOpen(open){languagePickerButton.setAttribute("aria-expanded",String(open));languageList.hidden=!open;if(open)languageList.querySelector('[role="option"]')?.focus();}
function localizeStatic(){
  document.documentElement.lang=state.language;
  document.title=t("app.title");$("meta[name=description]").setAttribute("content",t("app.description"));
  $("#viewport").setAttribute("aria-label",t("viewport"));
  document.querySelectorAll("[data-i18n]").forEach(element=>element.textContent=t(element.dataset.i18n));
  document.querySelectorAll("[data-i18n-aria]").forEach(element=>element.setAttribute("aria-label",t(element.dataset.i18nAria)));
  $("#building-label").textContent=buildingLabel(state.building);
  document.querySelectorAll("[data-building]").forEach(element=>element.textContent=buildingLabel(element.dataset.building));
  $("#dock-heading").textContent=t("dock.initial");$("#mode-detail").textContent=t("dock.exteriorDetail");
  $("#layer-label").textContent=t("dock.layerSeparation");$("#layer-range").setAttribute("aria-label",t("dock.layerSeparation"));
  languagePickerValue.textContent=state.language==="ro"?"🇷🇴":"🇬🇧";
  languagePickerButton.setAttribute("aria-label",t("language.label"));languagePickerButton.title=t("language.label");languageList.setAttribute("aria-label",t("language.label"));
  qualityPickerButton.setAttribute("aria-label",t("quality.label"));qualityList.setAttribute("aria-label",t("quality.label"));
  $("#quality-picker-value").textContent=t("quality."+state.quality);
  qualityList.querySelectorAll(".quality-option").forEach(option=>option.textContent=t("quality."+option.dataset.quality));
  pickerButton.setAttribute("aria-label",t("component.label"));catalogue.setAttribute("aria-label",t("component.label"));
  $("#inspector").setAttribute("aria-label",t("inspector.selected"));$("#close-inspector").setAttribute("aria-label",t("action.closeDetails"));
  $(".right-tools").setAttribute("aria-label",t("camera.label"));$("#zoom-in").setAttribute("aria-label",t("camera.zoomIn"));$("#zoom-out").setAttribute("aria-label",t("camera.zoomOut"));$("#reset-view").setAttribute("aria-label",t("camera.reset"));$("#auto-view").setAttribute("aria-label",t("camera.auto"));
  $("#walk-hint").textContent=t("walkthrough.hint");$("#loading-copy").textContent=t("loading.copy");
  $("#model-status-prefix").textContent=t("dock.illustrative");
  $("#model-status").textContent=t("model.loading");
  axisPickerValue.textContent=state.sectionAxis==="x"?t("axis.leftRight"):t("axis.frontBack");
  axisList.querySelectorAll(".axis-option").forEach(option=>option.textContent=option.dataset.axis==="x"?t("axis.leftRight"):t("axis.frontBack"));
}
function updateModelStatus(){if(state.model)$("#model-status").textContent=meshList.length.toLocaleString(localeTag())+" "+t("model.elements");}
function setLanguage(language){
  if(!["en","ro"].includes(language)||language===state.language){setLanguageOpen(false);return;}
  const selected=state.selected;
  state.language=language;setLanguageOpen(false);localizeStatic();
  languageList.querySelectorAll('[role="option"]').forEach(option=>option.setAttribute("aria-selected",String(option.dataset.language===language)));
  if(state.model){updateUI();updateModelStatus();refreshCatalogue(true);if(selected&&visible(selected))select(selected);}
  languagePickerButton.focus();
}
languagePickerButton.onclick=()=>setLanguageOpen(languageList.hidden);
languagePickerButton.onkeydown=e=>{if(["Enter"," ","ArrowDown"].includes(e.key)){e.preventDefault();setLanguageOpen(true);}if(e.key==="Escape")setLanguageOpen(false);};
languageList.onkeydown=e=>{const options=[...languageList.querySelectorAll('[role="option"]')],index=options.indexOf(document.activeElement);if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();options[(index+(e.key==="ArrowDown"?1:-1)+options.length)%options.length]?.focus();}if(e.key==="Escape"){setLanguageOpen(false);languagePickerButton.focus();}if(e.key==="Enter"||e.key===" "){e.preventDefault();document.activeElement?.click();}};
languageList.querySelectorAll('[role="option"]').forEach(option=>option.onclick=()=>{setLanguage(option.dataset.language);languageList.querySelectorAll('[role="option"]').forEach(item=>item.setAttribute("aria-selected",String(item===option)));});
document.addEventListener("pointerdown",e=>{if(!languagePicker.contains(e.target))setLanguageOpen(false);});

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
localizeStatic();
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
  buildBatches();reset();updateModelStatus();
  $("#loading").classList.add("is-hidden");
}
function error(message){
  $("#loading").classList.remove("is-hidden");
  $("#loading-copy").textContent=message;$("#loading-copy").classList.add("error-message");
  const retry=document.createElement("button");retry.textContent=t("loading.retry");retry.className="pill-button";retry.onclick=()=>location.reload();$(".loading-card").append(retry);
}
if(location.protocol==="file:")error(t("loading.file"));
else fetch("./assets/intermedia-residential.json",{cache:"no-store"}).then(r=>{
  if(!r.ok)throw Error("Manifest unavailable");return r.json();
}).then(manifest=>{
  new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load("./assets/intermedia-residential.glb?v="+encodeURIComponent(manifest.assetRevision||manifest.sceneVersion),
    g=>prepare(g.scene),
    p=>{if(p.total)$("#loading-copy").textContent=t("model.loading")+" "+Math.round(p.loaded/p.total*100)+"%";},
    ()=>error(t("loading.model")));
}).catch(()=>error(t("loading.manifest")));
renderer.domElement.addEventListener("webglcontextlost",e=>{e.preventDefault();error(t("loading.gpu"));});
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
  if(command.language!==undefined){if(!["en","ro"].includes(command.language))throw Error("Unknown language");state.language=command.language;localizeStatic();languageList.querySelectorAll('[role="option"]').forEach(option=>option.setAttribute("aria-selected",String(option.dataset.language===state.language)));}
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
  if(command.language!==undefined&&Object.keys(command).every(key=>key==="language")){
    updateUI();updateModelStatus();if(state.selected&&visible(state.selected))select(state.selected);return;
  }
  renderState({frame:command.frame!==false});
};
window.__intermedia={scene,renderer,camera,controls,state,sky,clipPlane,pickAt,select,setLanguage,visible,meshList,batches,selectionMarker,reset};
