async () => {
  const v=window.__intermedia;
  if(!v?.state.model)throw Error("Model not loaded");
  const results=[];
  const check=(name,value)=>{results.push({name,passed:!!value});if(!value)throw Error(name);};
  const equal=(a,b,epsilon=1e-6)=>a.length===b.length&&a.every((x,i)=>Math.abs(x-b[i])<epsilon);
  const belongsToSelectedBuilding=n=>{for(let p=n;p;p=p.parent)if(p.userData.building_id===v.state.building)return true;return false;};
  const roots=()=>{const list=[];v.state.model.traverse(n=>{if(n.userData.role==="floor"&&n.userData.building_id==="A")list.push(n);});return list;};
  const renderedMatches=()=>{
    v.state.model.updateMatrixWorld(true);
    for(const {batch,instances} of v.batches)for(const {node,id} of instances){
      const m=node.matrixWorld.clone();batch.getMatrixAt(id,m);
      if(!equal(m.elements,node.matrixWorld.elements,1e-5)||batch.getVisibleAt(id)!==v.visible(node))return false;
    }
    return true;
  };
  v.reset();
  check("English is the default language",document.documentElement.lang==="en"&&document.querySelector("#language-picker-value")?.textContent==="🇬🇧");
  check("Language picker uses branded listbox",document.querySelector("#language-picker-button")?.getAttribute("aria-haspopup")==="listbox"&&document.querySelector("#language-list")?.getAttribute("role")==="listbox");
  document.querySelector("#language-picker-button").click();
  check("Language picker opens from the top bar",!document.querySelector("#language-list").hidden&&document.querySelector("#language-picker-button").getAttribute("aria-expanded")==="true");
  document.querySelector("[data-language=ro]").click();
  check("Language picker switches to Romanian",document.documentElement.lang==="ro"&&document.querySelector("#language-picker-value")?.textContent==="🇷🇴");
  document.querySelector("[data-language=en]").click();
  check("Language picker switches back to English",document.documentElement.lang==="en"&&document.querySelector("#language-picker-value")?.textContent==="🇬🇧");
  window.intermediaSetView({language:"ro"});
  check("Romanian localization switches the app",document.documentElement.lang==="ro"&&document.querySelector("#language-picker-value")?.textContent==="🇷🇴"&&document.querySelector("[data-mode=exploded]")?.textContent==="Explodat");
  check("Romanian apartment cards are translated",document.querySelector("[data-i18n='unit.Studio.name']")?.textContent==="Garsonieră"&&document.querySelector("[data-i18n='unit.2Room.name']")?.textContent==="2 camere");
  check("Romanian quality and axis options are translated",document.querySelector("[data-quality=high]")?.textContent==="Înaltă"&&document.querySelector("[data-axis=z]")?.textContent==="Față ↔ spate"&&document.querySelector("[data-axis=x]")?.textContent==="Stânga ↔ dreapta");
  document.querySelector("#quality-picker-button").click();document.querySelector("[data-quality=high]").click();
  check("Romanian selected quality value is translated",document.querySelector("#quality-picker-value")?.textContent==="Înaltă");
  window.intermediaSetView({language:"en"});
  check("English localization can be restored",document.documentElement.lang==="en"&&document.querySelector("#language-picker-value")?.textContent==="🇬🇧"&&document.querySelector("[data-mode=exploded]")?.textContent==="Exploded"&&document.querySelector("#quality-picker-value")?.textContent==="High");
  check("Only one functional layer slider",document.querySelectorAll('input[type="range"]').length===1);
  check("Component picker uses branded listbox",document.querySelector("#component-picker-button")?.getAttribute("aria-haspopup")==="listbox"&&document.querySelector("#component-list")?.getAttribute("role")==="listbox"&&!document.querySelector("select#component-list"));
  check("Quality picker uses branded listbox",document.querySelector("#quality-picker-button")?.getAttribute("aria-haspopup")==="listbox"&&document.querySelector("#quality-list")?.getAttribute("role")==="listbox"&&!document.querySelector("select#quality-select"));
  check("Section orientation uses branded listbox",document.querySelector("#axis-picker-button")?.getAttribute("aria-haspopup")==="listbox"&&document.querySelector("#axis-list")?.getAttribute("role")==="listbox"&&!document.querySelector("select#section-axis"));
  check("Marketing stays in the scene",!document.querySelector(".promo-banner")&&v.meshList.some(n=>n.name.includes("SITE_EntranceMarketing")));
  const base=new Map();v.state.model.traverse(n=>base.set(n,n.position.toArray()));
  for(const amount of [0,.25,.5,1,0]){
    window.intermediaSetView({mode:"exploded",explosion:amount});
    check("Exploded mode enables context by default",v.state.context===true);
    for(const floor of roots()){
      const index=Number(floor.userData.floor_index);
      check("Floor "+index+" actual height at "+amount,Math.abs(floor.position.y-base.get(floor)[1]-index*4.8*amount)<1e-5);
    }
    check("Rendered batch geometry matches logical transforms at "+amount,renderedMatches());
  }
  check("Zero explosion restores every original transform",[...base].every(([n,p])=>equal(n.position.toArray(),p)));
  window.intermediaSetView({mode:"exploded",explosion:.4});
  const camera=v.camera.position.toArray(),target=v.controls.target.toArray();
  const slider=document.querySelector("#layer-range");slider.value="75";slider.dispatchEvent(new Event("input",{bubbles:true}));
  check("Dragging explosion does not move camera",equal(camera,v.camera.position.toArray())&&equal(target,v.controls.target.toArray()));
  check("Ceilings remain present in explosion",v.meshList.filter(n=>n.userData.role==="ceiling"&&n.name.startsWith("BLK-A")).every(v.visible));
  const floor=roots().find(n=>n.userData.floor_index===2);
  const part=[];floor.traverse(n=>{if(n.isMesh)part.push(n);});
  check("Floor descendants retain owning floor",part.length>10&&part.every(n=>{for(let p=n;p;p=p.parent)if(p===floor)return true;return false;}));
  for(const axis of ["x","z"]){
    for(const position of [.25,.5,.75]){
      window.intermediaSetView({mode:"cutaway",sectionAxis:axis,section:position});
      check("Structural caps exist "+axis+position,v.state.sectionCaps.children.length>0);
      let maxArea=0;
      v.state.sectionCaps.traverse(n=>{
        if(!n.isMesh)return;n.geometry.computeBoundingBox();const b=n.geometry.boundingBox;
        maxArea=Math.max(maxArea,(b.max.y-b.min.y)*(axis==="x"?b.max.z-b.min.z:b.max.x-b.min.x));
      });
      check("Caps do not fill room voids "+axis+position,maxArea<60);
      check("Clipped render batches retain visibility ownership",renderedMatches());
      for(let x=350;x<innerWidth-50;x+=100)for(let y=180;y<innerHeight-180;y+=90){
        const hit=v.pickAt(x,y);
        if(hit&&belongsToSelectedBuilding(hit.object))check("Picking excludes removed half-space",v.clipPlane.distanceToPoint(hit.point)>=-.0001);
      }
    }
  }
  for(const building of ["A","B","C"])for(const level of [0,1,2,3]){
    window.intermediaSetView({mode:"floors",building,floor:level});
    check("Etaje enables context by default "+building+level,v.state.context===true);
    const levels=[];v.state.model.traverse(n=>{
      if(n.userData.building_id===building&&n.userData.role==="floor")levels.push(n);
      if(n.userData.building_id===building&&n.userData.role==="roof")check("Roof hidden "+building+level,!v.visible(n));
    });
    check("Complete floor visibility "+building+level,levels.every(n=>v.visible(n)===(n.userData.floor_index<=level)));
  }
  window.intermediaSetView({mode:"exploded",building:"A",explosion:.75});
  let selectedHit=null;
  for(let x=350;x<innerWidth-50&&!selectedHit;x+=50)for(let y=180;y<innerHeight-180&&!selectedHit;y+=40)selectedHit=v.pickAt(x,y);
  check("Exploded geometry can be ray-picked",!!selectedHit);
  v.select(selectedHit.object);
  check("Selected component inspector keeps a stable element ID",!document.querySelector("#inspector").hidden&&document.querySelector("#component-meta").textContent.includes(selectedHit.object.name));
  check("Selected component has a visible spatial marker",v.selectionMarker.visible&&v.selectionMarker.children.length>0);
  document.querySelector("#close-inspector").click();
  check("Closing inspector preserves explosion",v.state.explosion===.75);
  v.select(selectedHit.object);document.querySelector("#isolate-component").click();
  check("Isolated render batches match visibility",renderedMatches());
  window.intermediaSetView({language:"ro"});
  check("Language switching preserves component isolation",v.state.isolated===selectedHit.object&&v.visible(selectedHit.object)&&document.querySelector("#isolate-component").textContent==="Arată ansamblul");
  window.intermediaSetView({language:"en"});
  check("Language switching refreshes selected inspector",document.querySelector("#isolate-component").textContent==="Show assembly");
  document.querySelector("#isolate-component").click();
  check("Restoring isolation restores control label",document.querySelector("#isolate-component").textContent==="Isolate");
  v.reset();
  check("Reset restores all transforms",[...base].every(([n,p])=>equal(n.position.toArray(),p)));
  check("Reset clears clipping",v.meshList.every(n=>(Array.isArray(n.material)?n.material:[n.material]).every(m=>m.clippingPlanes.length===0)));
  window.intermediaSetView({mode:"apartment",unit:"Studio"});
  document.querySelector("#walk-toggle").click();
  check("Walkthrough enters the selected apartment",v.state.walking&&v.state.mode==="apartment"&&document.querySelector("#walk-hint").classList.contains("is-visible"));
  window.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape"}));
  check("Escape exits walkthrough",!v.state.walking&&!document.querySelector("#walk-hint").classList.contains("is-visible"));
  return {passed:results.length,failed:results.filter(r=>!r.passed),groups:["slider","real transforms","render batches","caps","picking","floors","isolation","reset"]};
}
